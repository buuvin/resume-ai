import json
import re
import unicodedata
from pathlib import Path

import numpy as np

from app.models.schemas import (
    AlignmentEvidence,
    AnalysisResult,
    RequirementItem,
)

ABBREVIATIONS = {
    "ml": "machine learning",
    "dl": "deep learning",
    "ds": "data science",
    "nlp": "natural language processing",
    "cv": "computer vision",
    "js": "javascript",
    "py": "python",
    "postgres": "postgresql",
    "aws": "amazon web services",
    "gcp": "google cloud",
    "k8s": "kubernetes",
    "llm": "large language model",
    "rag": "retrieval augmented generation"
}

DOMAIN_ENTITY_TAXONOMY = {
    "languages": {
        "c": "c",
        "go": "go",
        "java": "java",
        "javascript": "javascript",
        "kotlin": "kotlin",
        "python": "python",
        "r": "r",
        "rust": "rust",
        "scala": "scala",
        "swift": "swift",
        "typescript": "typescript",
    },
    "frameworks": {
        "angular": "angular",
        "django": "django",
        "fastapi": "fastapi",
        "flask": "flask",
        "keras": "keras",
        "next js": "next.js",
        "pytorch": "pytorch",
        "react": "react",
        "scikit learn": "scikit-learn",
        "spring": "spring",
        "tensorflow": "tensorflow",
        "vue": "vue",
    },
    "platforms": {
        "amazon web services": "aws",
        "azure": "azure",
        "databricks": "databricks",
        "google cloud": "gcp",
        "heroku": "heroku",
        "kubernetes": "kubernetes",
        "snowflake": "snowflake",
        "tableau": "tableau",
    },
    "tools": {
        "airflow": "airflow",
        "docker": "docker",
        "git": "git",
        "github": "github",
        "gitlab": "gitlab",
        "jenkins": "jenkins",
        "jupyter": "jupyter",
        "kubeflow": "kubeflow",
        "mlflow": "mlflow",
        "pandas": "pandas",
        "spark": "spark",
    },
    "databases": {
        "bigquery": "bigquery",
        "dynamodb": "dynamodb",
        "elasticsearch": "elasticsearch",
        "mongodb": "mongodb",
        "mysql": "mysql",
        "postgresql": "postgresql",
        "redis": "redis",
        "sqlite": "sqlite",
    },
    "concepts": {
        "artificial intelligence": "artificial intelligence",
        "computer vision": "computer vision",
        "data engineering": "data engineering",
        "data science": "data science",
        "deep learning": "deep learning",
        "generative ai": "generative ai",
        "large language model": "large language model",
        "neural networks": "neural networks",
        "machine learning": "machine learning",
        "natural language processing": "natural language processing",
        "prompt engineering": "prompt engineering",
        "reinforcement learning": "reinforcement learning",
        "retrieval augmented generation": "retrieval augmented generation",
        "supervised learning": "supervised learning",
        "unsupervised learning": "unsupervised learning",
    },
}

SYNONYMS = {
    "aws": "amazon web services",
    "aws lambda": "amazon web services",
    "gcp": "google cloud",
}

MATCHED_ALIGNMENT_THRESHOLD = 0.70
UNDERREPRESENTED_ALIGNMENT_THRESHOLD = 0.45
# R1 slot-dilution decision (scripts/score_experiment.py, 20 hand labels):
# a requirement's score is mean(best alignment over COVERED slots) *
# coverage^COVERAGE_ALPHA. alpha=1 was the old all-slot mean (uncovered
# slots punished the score; 9/10 present requirements misclassified as
# missing), alpha=0 lets one lucky match carry a whole requirement (9/10
# absent requirements leaked). alpha=0.3 fixed 3 of the 9 dilution
# failures while keeping absent requirements mostly missing (5/10).
# A requirement with zero covered slots still scores 0.0.
COVERAGE_ALPHA = 0.3
# Emission floor per source: rows below their source's floor are never
# cited. Deliberately separate from the classification thresholds above —
# 0.45 decides how a requirement is labelled, the floor decides whether a
# piece of evidence is strong enough to appear at all. Per-source because
# the channels operate at different granularities: bullet-channel pairs
# (whole sentences) measure 0.42-0.56 on genuine matches, while KeyBERT
# phrases and NER entities reach 0.7-1.0 (measured across the five
# fixture cases in input/job_description_cases.json).
EMISSION_FLOORS = {"bulletpoints": 0.40, "keybert": 0.50, "ner": 0.50}
# Fixed tie-break order when two sources cite the same evidence string at
# the same alignment. The requirement channel wins, then KeyBERT, then NER.
SOURCE_PRIORITY = ("bulletpoints", "keybert", "ner")
ALIGNMENT_EVIDENCE_OUTPUT = (
    Path(__file__).resolve().parents[2] / "output" / "alignment_evidence.json"
)
RESUME_EVIDENCE_OUTPUT = (
    Path(__file__).resolve().parents[2] / "output" / "resume_evidence.json"
)

def clean_text(text: str) -> str:
    # Normalize visually similar Unicode characters so matching is consistent
    # across copy/pasted text.
    text = unicodedata.normalize("NFKC", text or "")
    text = text.lower()
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def expand_abbreviations(text: str) -> str:
    expanded_text = text
    for abbreviation, replacement in ABBREVIATIONS.items():
        # Replace short aliases like "nlp" before phrase and token matching runs.
        expanded_text = re.sub(
            rf"\b{re.escape(abbreviation)}\b",
            replacement,
            expanded_text,
        )
    return expanded_text


def extract_domain_entities(text: str) -> dict[str, list[str]]:
    """Extract canonical computer science and ML entities from normalized text."""
    normalized = expand_abbreviations(clean_text(text))
    entities = {category: set() for category in DOMAIN_ENTITY_TAXONOMY}

    for category, terms in DOMAIN_ENTITY_TAXONOMY.items():
        for term, canonical_name in terms.items():
            if re.search(rf"\b{re.escape(term)}\b", normalized):
                entities[category].add(canonical_name)

    return {
        category: sorted(found_entities)
        for category, found_entities in entities.items()
    }


MAX_SUBHEADER_LABEL_WORDS = 4


def strip_subheader_labels(text: str) -> str:
    """Separate 'Label: value' lines and keep only the value side.

    Category subheaders such as 'Programming & Tools' or 'Degree' are document
    furniture, not evidence, so they must not surface as keyphrases or
    entities. A line is treated as label:value only when the label is short
    (<= MAX_SUBHEADER_LABEL_WORDS words); longer labels indicate a sentence
    with a mid-line colon and are left untouched.
    """
    kept_lines = []
    for line in (text or "").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        colon_index = stripped.find(":")
        if colon_index == -1:
            kept_lines.append(stripped)
            continue
        label = stripped[:colon_index]
        value = stripped[colon_index + 1 :].strip()
        if not value:
            # A bare 'Label:' line is a heading; drop it entirely.
            continue
        if len(label.split()) <= MAX_SUBHEADER_LABEL_WORDS:
            kept_lines.append(value)
        else:
            kept_lines.append(stripped)
    return "\n".join(kept_lines)


def strip_heading_lines(text: str) -> str:
    """Remove standalone heading lines from text before semantic extraction.

    Only exact heading matches are removed (never prefix matches) so that
    requirement bullets beginning with words like 'experience' survive.
    """
    heading_lookup = {
        variant
        for variants in HEADING_VARIANTS.values()
        for variant in variants
    }
    kept_lines = []
    for line in (text or "").splitlines():
        normalized = re.sub(r"[^\w\s]", " ", line).strip().lower()
        if normalized in heading_lookup:
            continue
        if line.strip():
            kept_lines.append(line.strip())
    return "\n".join(kept_lines)


def preprocess_for_semantic_extraction(text: str) -> str:
    """Clean text before NER and KeyBERT run on it.

    Heading lines and subheader labels are document furniture; feeding them to
    KeyBERT lets salient tokens like 'skills' rank as keyphrases and pollute
    the evidence pool.
    """
    return strip_subheader_labels(strip_heading_lines(text))


HEADING_VARIANTS = {
    "summary": ["summary", "professional summary", "profile"],
    "skills": ["skills", "technical skills", "skillset"],
    "experience": [
        "experience",
        "work experience",
        "professional experience",
        "leadership experience",
    ],
    "projects": ["projects", "personal projects", "project experience"],
    "education": ["education", "academic"],
    "certifications": ["certifications", "licenses"],
    "requirements": [
        "requirements",
        "requirement",
        "qualifications",
        "qualification",
        "minimum qualifications",
        "minimum qualification",
        "must have",
    ],
    "preferred": [
        "nice to have",
        "nice-to-have",
        "preferred",
        "nice to haves",
        "preferred qualifications",
        "soft skills",
        "bonus points",
    ],
}


def parse_sections(text: str):
    """Split a resume-like text into high-level sections using common headings.

    Returns an ordered dict-like mapping of section_name -> section_text.
    If no headings are detected, returns {'body': text}.

    A line is a heading only when its normalised form *equals* a known
    variant — never when it merely starts with one — and a line that
    begins with a bullet marker is content whatever it says. Both rules
    matter for job descriptions: prefix matching used to swallow
    requirement bullets like "Experience with Git ..." and any line
    starting with "skills ..." lost its content to the heading branch.
    """
    from app.services.embeddings import BULLET_MARKER_PATTERN

    if not text or not text.strip():
        return {"body": ""}

    heading_lookup = {}
    for key, variants in HEADING_VARIANTS.items():
        for v in variants:
            heading_lookup[v] = key

    sections = {}
    current = None
    lines = text.splitlines()
    for raw in lines:
        line = raw.strip()
        if not line:
            # preserve paragraph breaks inside a section
            if current:
                sections[current] += "\n"
            continue

        key = None
        if not BULLET_MARKER_PATTERN.match(line):
            low = re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", line)).strip().lower()
            key = heading_lookup.get(low)

        if key:
            current = key
            if current not in sections:
                sections[current] = ""
            continue

        if current is None:
            # initialize the first implicit section
            current = "summary"
            sections[current] = ""

        sections[current] += (line + "\n")

    # fallback: if only a single empty section or none, return the whole text as body
    if not sections:
        return {"body": text}

    return sections


def _unique_strings(values: list[str] | set[str] | None) -> list[str]:
    return list(
        dict.fromkeys(
            value.strip() for value in values or [] if value and value.strip()
        )
    )


def _alignment_normalize(text: str) -> str:
    normalized = clean_text(text)
    normalized = SYNONYMS.get(normalized, normalized)
    normalized = expand_abbreviations(normalized)
    return SYNONYMS.get(normalized, normalized)


def decompose_requirements(
    requirements: list[str],
) -> dict[str, dict[str, list[str]]]:
    """Split each requirement into its KeyBERT phrases and NER entities.

    Returns ``{requirement: {source: [sub-requirements]}}`` for the
    decomposition sources only (``keybert`` and ``ner``). The
    ``bulletpoints`` channel is not decomposed — a JD bullet *is* a
    requirement, so its sub-requirement is the requirement itself;
    ``alignment_machine`` fills that channel in.
    """
    from app.services.embeddings import extract_keyphrases

    decomposed = {}
    for requirement in _unique_strings(requirements):
        decomposed[requirement] = {
            "keybert": _unique_strings(extract_keyphrases(requirement)),
            "ner": _unique_strings(
                _flatten_entities(extract_domain_entities(requirement))
            ),
        }
    return decomposed


def alignment_machine(
    resume_evidence: dict[str, list[str]],
    requirements: list[str],
    max_evidence_per_requirement: int = 10,
    requirement_subrequirements: dict[str, dict[str, list[str]]] | None = None,
) -> list[AlignmentEvidence]:
    """Rank resume evidence against decomposed requirements, per source.

    Every source is only ever compared within itself: JD bullets against
    resume bullets, JD KeyBERT phrases against resume KeyBERT phrases, JD
    NER entities against resume NER entities. Rows below their source's
    ``EMISSION_FLOORS`` entry are never emitted, evidence is
    de-duplicated within a requirement across sources so one resume
    sentence cannot be cited twice, and each sub-requirement that ends up
    with no cited evidence gets a placeholder row (``evidence=""``) so
    scoring can count it as ``0.0``.
    """
    unknown_sources = set(resume_evidence) - set(SOURCE_PRIORITY)
    if unknown_sources:
        raise ValueError("resume_evidence contains an unknown source")

    from app.services.embeddings import embed_document

    requirement_strings = _unique_strings(requirements)
    if not requirement_strings or max_evidence_per_requirement < 1:
        return []

    decomposition = requirement_subrequirements or {}

    # The JD side of each source, per requirement. A missing or empty
    # decomposition falls back to the requirement itself, which guarantees
    # every requirement has at least the bullet channel to stand on.
    slots_by_requirement: dict[str, dict[str, list[str]]] = {}
    for requirement in requirement_strings:
        given = decomposition.get(requirement) or {}
        slots_by_requirement[requirement] = {
            source: _unique_strings(given.get(source)) or [requirement]
            for source in SOURCE_PRIORITY
        }

    # Embed each source once: the union of its JD sub-requirements and its
    # resume evidence. embed_document normalises its lines, so a dot
    # product between the two sides is the cosine similarity.
    jd_vectors_by_source: dict[str, dict[str, list[float]]] = {}
    resume_by_source: dict[str, tuple[list[str], np.ndarray]] = {}
    for source in SOURCE_PRIORITY:
        jd_strings = _unique_strings(
            [
                slot
                for requirement in requirement_strings
                for slot in slots_by_requirement[requirement][source]
            ]
        )
        resume_strings = _unique_strings(resume_evidence.get(source))
        if not jd_strings or not resume_strings:
            continue

        jd_document = embed_document("\n".join(jd_strings))
        resume_document = embed_document("\n".join(resume_strings))
        if not jd_document.embeddings or not resume_document.embeddings:
            continue

        jd_vectors_by_source[source] = dict(zip(jd_strings, jd_document.embeddings))
        resume_by_source[source] = (
            resume_strings,
            np.asarray(resume_document.embeddings, dtype=float),
        )

    alignments: list[AlignmentEvidence] = []
    for requirement in requirement_strings:
        # Every floor-passing row for this requirement, across sources.
        candidates: list[AlignmentEvidence] = []
        for source in SOURCE_PRIORITY:
            resume_entry = resume_by_source.get(source)
            jd_vectors = jd_vectors_by_source.get(source)
            if resume_entry is None or jd_vectors is None:
                continue
            resume_strings, resume_matrix = resume_entry
            slot_strings = slots_by_requirement[requirement][source]
            jd_matrix = np.asarray(
                [jd_vectors[slot] for slot in slot_strings], dtype=float
            )
            similarity = np.clip(jd_matrix @ resume_matrix.T, -1.0, 1.0)
            for slot_index, slot in enumerate(slot_strings):
                for evidence_index, evidence_item in enumerate(resume_strings):
                    alignment = float(similarity[slot_index, evidence_index])
                    if alignment < EMISSION_FLOORS[source]:
                        continue
                    candidates.append(
                        AlignmentEvidence(
                            source=source,
                            requirement=requirement,
                            sub_requirement=slot,
                            evidence=evidence_item,
                            alignment=alignment,
                            exact_match=(
                                _alignment_normalize(slot)
                                == _alignment_normalize(evidence_item)
                            ),
                        )
                    )

        # De-duplicate across sources within this requirement: a single
        # resume sentence is cited by whichever row aligns with it most
        # strongly, and never twice.
        candidates.sort(
            key=lambda item: (
                -item.alignment,
                SOURCE_PRIORITY.index(item.source),
                item.evidence,
                item.sub_requirement,
            )
        )
        seen_evidence: set[str] = set()
        deduped: list[AlignmentEvidence] = []
        for candidate in candidates:
            normalized_evidence = _alignment_normalize(candidate.evidence)
            if normalized_evidence in seen_evidence:
                continue
            seen_evidence.add(normalized_evidence)
            deduped.append(candidate)

        # Keep the top rows of each sub-requirement for the audit
        # artefact; scoring only ever reads a sub-requirement's best row.
        selected_by_sub_requirement: dict[str, list[AlignmentEvidence]] = {}
        for candidate in deduped:
            rows = selected_by_sub_requirement.setdefault(
                candidate.sub_requirement, []
            )
            if len(rows) < max_evidence_per_requirement:
                rows.append(candidate)

        # Emit each sub-requirement once, in a stable order, and give the
        # ones with no cited evidence a placeholder so they still count.
        emitted_sub_requirements: list[str] = []
        for source in SOURCE_PRIORITY:
            for slot in slots_by_requirement[requirement][source]:
                if slot not in emitted_sub_requirements:
                    emitted_sub_requirements.append(slot)

        for slot in emitted_sub_requirements:
            rows = selected_by_sub_requirement.get(slot)
            if rows:
                alignments.extend(rows)
                continue
            alignments.append(
                AlignmentEvidence(
                    source="bulletpoints",
                    requirement=requirement,
                    sub_requirement=slot,
                    evidence="",
                    alignment=0.0,
                    exact_match=False,
                )
            )
    return alignments


def _flatten_entities(entities: dict[str, list[str]]) -> list[str]:
    return _unique_strings(
        [entity for category in entities.values() for entity in category]
    )


def write_alignment_evidence(
    alignment_evidence: list[AlignmentEvidence],
    output_path: Path = ALIGNMENT_EVIDENCE_OUTPUT,
) -> None:
    """Write all requirement evidence once after alignment has completed."""
    evidence_by_requirement = {}
    for item in alignment_evidence:
        evidence_by_requirement.setdefault(item.requirement, []).append(
            {
                "source": item.source,
                "sub_requirement": item.sub_requirement,
                "evidence": item.evidence,
                "alignment": item.alignment,
                "exact_match": item.exact_match,
            }
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(
            {
                "requirements": [
                    {
                        "requirement": requirement,
                        "evidence": evidence,
                    }
                    for requirement, evidence in evidence_by_requirement.items()
                ]
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def write_resume_evidence(
    resume_entities: dict[str, list[str]],
    resume_keyphrases: list[str] | set[str],
    resume_bullets: list[str],
    output_path: Path = RESUME_EVIDENCE_OUTPUT,
    *,
    resume_title_lines: list[str] | set[str] | None = None,
) -> None:
    """Write all collected resume evidence without requirement alignment data."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(
            {
                "resume_evidence": {
                    "ner": resume_entities,
                    "keybert": _unique_strings(resume_keyphrases),
                    "bulletpoints": _unique_strings(resume_bullets),
                    "titles": _unique_strings(resume_title_lines),
                }
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def _summarize_alignment(
    alignment_evidence: list[AlignmentEvidence],
) -> tuple[list[str], list[str], list[str], float]:
    """Summarize semantic evidence without falling back to token extraction.

    A requirement's score is the mean best alignment across its *covered*
    sub-requirements (those with cited evidence), discounted by
    ``coverage ** COVERAGE_ALPHA`` where coverage is the fraction of its
    sub-requirements that are covered. A placeholder row (no cited
    evidence) contributes to the coverage denominator only; a requirement
    with zero covered sub-requirements scores ``0.0``. The overall score
    is the mean of those requirement scores.
    """
    best_alignment_by_sub_requirement: dict[tuple[str, str], float] = {}
    covered_slots: set[tuple[str, str]] = set()
    for item in alignment_evidence:
        key = (item.requirement, item.sub_requirement)
        best_alignment_by_sub_requirement[key] = max(
            best_alignment_by_sub_requirement.get(key, 0.0),
            item.alignment,
        )
        if item.evidence.strip():
            covered_slots.add(key)

    slots_by_requirement: dict[str, list[tuple[str, float]]] = {}
    for (requirement, sub_requirement), alignment in (
        best_alignment_by_sub_requirement.items()
    ):
        slots_by_requirement.setdefault(requirement, []).append(
            (sub_requirement, alignment)
        )

    best_alignment_by_requirement: dict[str, float] = {}
    for requirement, slots in slots_by_requirement.items():
        covered_scores = [
            alignment
            for sub_requirement, alignment in slots
            if (requirement, sub_requirement) in covered_slots
        ]
        if not covered_scores:
            best_alignment_by_requirement[requirement] = 0.0
            continue
        coverage = len(covered_scores) / len(slots)
        covered_mean = sum(covered_scores) / len(covered_scores)
        best_alignment_by_requirement[requirement] = (
            covered_mean * coverage**COVERAGE_ALPHA
        )

    matched = {
        requirement
        for requirement, alignment in best_alignment_by_requirement.items()
        if alignment >= MATCHED_ALIGNMENT_THRESHOLD
    }
    underrepresented = {
        requirement
        for requirement, alignment in best_alignment_by_requirement.items()
        if UNDERREPRESENTED_ALIGNMENT_THRESHOLD
        <= alignment
        < MATCHED_ALIGNMENT_THRESHOLD
    }
    missing = set(best_alignment_by_requirement) - matched - underrepresented
    score = (
        sum(best_alignment_by_requirement.values())
        / len(best_alignment_by_requirement)
        if best_alignment_by_requirement
        else 0.0
    )
    return sorted(matched), sorted(underrepresented), sorted(missing), round(score, 2)

def analyze_resume(
    resume: str,
    job_description: str,
    supplemental: str,
    resume_keyphrases: set[str] | None = None,
    jd_keyphrases: set[str] | None = None,
    supplemental_keyphrases: set[str] | None = None,
    bullet_similarity: object | None = None,
    preferred_requirements: list[RequirementItem] | None = None,
):
    resume_entities = extract_domain_entities(resume)
    jd_entities = extract_domain_entities(job_description)

    requirement_strings = getattr(bullet_similarity, "job_description_bullets", [])
    alignment_evidence = alignment_machine(
        {
            "ner": _flatten_entities(resume_entities),
            "keybert": list(resume_keyphrases or []),
            "bulletpoints": getattr(bullet_similarity, "resume_bullets", []),
        },
        requirement_strings,
        requirement_subrequirements=decompose_requirements(requirement_strings),
    )

    matched, underrepresented, missing, score = _summarize_alignment(alignment_evidence)

    return AnalysisResult(
        matched_skills=list(matched),
        underrepresented_skills=list(underrepresented),
        missing_skills=list(missing),
        resume_keyphrases=sorted(resume_keyphrases or set()),
        job_description_keyphrases=sorted(jd_keyphrases or set()),
        supplemental_keyphrases=sorted(supplemental_keyphrases or set()),
        alignment_score=round(score, 2),
        resume_entities=resume_entities,
        job_description_entities=jd_entities,
        supplemental_entities=extract_domain_entities(supplemental),
        alignment_evidence=alignment_evidence,
        resume_title_lines=getattr(bullet_similarity, "resume_title_lines", []),
        preferred_requirements=list(preferred_requirements or []),
    )