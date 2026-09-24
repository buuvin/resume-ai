import re
import unicodedata

import numpy as np

from app.models.schemas import (
    AnalysisResult,
    AlignmentEvidence,
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

def clean_text(text: str) -> str:
    # Normalize visually similar Unicode characters so matching is consistent across copy/pasted text.
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


def parse_sections(text: str):
    """Split a resume-like text into high-level sections using common headings.

    Returns an ordered dict-like mapping of section_name -> section_text.
    If no headings are detected, returns {'body': text}.
    """
    if not text or not text.strip():
        return {"body": ""}

    headings = {
        "summary": ["summary", "professional summary", "profile"],
        "skills": ["skills", "technical skills", "skillset"],
        "experience": ["experience", "work experience", "professional experience"],
        "projects": ["projects", "personal projects"],
        "education": ["education", "academic"],
        "certifications": ["certifications", "licenses"],
        "requirements": ["requirements", "requirement", "qualifications", "qualification"],
        "preferred": ["nice to have", "nice-to-have", "preferred", "nice to haves"],
    }

    heading_lookup = {}
    for key, variants in headings.items():
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

        low = re.sub(r"[^\w\s]", " ", line).strip().lower()
        key = None
        # detect heading if the line equals or starts with a known heading phrase
        for variant, section_key in heading_lookup.items():
            if low == variant or low.startswith(variant + " ") or low.startswith(variant + ":"):
                key = section_key
                break

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
    return list(dict.fromkeys(value.strip() for value in values or [] if value and value.strip()))


def _alignment_normalize(text: str) -> str:
    normalized = clean_text(text)
    normalized = SYNONYMS.get(normalized, normalized)
    normalized = expand_abbreviations(normalized)
    return SYNONYMS.get(normalized, normalized)


def alignment_machine(
    source: str,
    evidence: list[str],
    requirement: list[str],
) -> list[AlignmentEvidence]:
    """Match every job requirement to its strongest same-source resume evidence."""
    if source not in {"ner", "keybert", "bulletpoints"}:
       raise ValueError("source must be 'ner', 'keybert', or 'bulletpoints'")

    from app.services.embeddings import embed_document

    evidence_strings = _unique_strings(evidence)
    requirement_strings = _unique_strings(requirement)
    if not requirement_strings:
        return []

    evidence_document = embed_document("\n".join(evidence_strings))
    requirement_document = embed_document("\n".join(requirement_strings))
    evidence_vectors = np.asarray(evidence_document.embeddings, dtype=float)
    requirement_vectors = np.asarray(requirement_document.embeddings, dtype=float)

    if not evidence_strings or evidence_vectors.size == 0:
        return [
            AlignmentEvidence(
                source=source,
                requirement=item,
                evidence="",
                alignment=0.0,
                exact_match=False,
            )
            for item in requirement_strings
        ]

    similarity_matrix = np.clip(requirement_vectors @ evidence_vectors.T, -1.0, 1.0)
    alignments = []
    for index, requirement_item in enumerate(requirement_strings):
        evidence_index = int(np.argmax(similarity_matrix[index]))
        evidence_item = evidence_strings[evidence_index]
        alignments.append(
            AlignmentEvidence(
                source=source,
                requirement=requirement_item,
                evidence=evidence_item,
                alignment=float(similarity_matrix[index, evidence_index]),
                exact_match=(
                    _alignment_normalize(requirement_item)
                    == _alignment_normalize(evidence_item)
                ),
            )
        )
    return alignments


def _flatten_entities(entities: dict[str, list[str]]) -> list[str]:
    return _unique_strings(
        [entity for category in entities.values() for entity in category]
    )


def _summarize_alignment(
    alignment_evidence: list[AlignmentEvidence],
) -> tuple[list[str], list[str], list[str], float]:
    """Summarize semantic evidence without falling back to token extraction."""
    best_alignment_by_requirement = {}
    for item in alignment_evidence:
        best_alignment_by_requirement[item.requirement] = max(
            best_alignment_by_requirement.get(item.requirement, 0.0),
            item.alignment,
        )

    matched = {
        requirement
        for requirement, alignment in best_alignment_by_requirement.items()
        if alignment >= MATCHED_ALIGNMENT_THRESHOLD
    }
    underrepresented = {
        requirement
        for requirement, alignment in best_alignment_by_requirement.items()
        if UNDERREPRESENTED_ALIGNMENT_THRESHOLD <= alignment < MATCHED_ALIGNMENT_THRESHOLD
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
):
    resume_entities = extract_domain_entities(resume)
    jd_entities = extract_domain_entities(job_description)

    alignment_evidence = []
    alignment_evidence.extend(
        alignment_machine("ner", _flatten_entities(resume_entities), _flatten_entities(jd_entities))
    )
    alignment_evidence.extend(
        alignment_machine("keybert", list(resume_keyphrases or []), list(jd_keyphrases or []))
    )
    alignment_evidence.extend(
        alignment_machine(
            "bulletpoints",
            getattr(bullet_similarity, "resume_bullets", []),
            getattr(bullet_similarity, "job_description_bullets", []),
        )
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
    )