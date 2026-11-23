import asyncio
import json
from pathlib import Path

import pytest
from fastapi import UploadFile

from app.models.schemas import AlignmentEvidence
from app.services.analysis import (
    _alignment_normalize,
    _flatten_entities,
    _summarize_alignment,
    alignment_machine,
    decompose_requirements,
    extract_domain_entities,
    preprocess_for_semantic_extraction,
    write_alignment_evidence,
    write_resume_evidence,
)
from app.services.embeddings import (
    embed_document,
    extract_evidence_lines,
    extract_keyphrases,
)
from app.services.ingestion import extract_upload_text

PROJECT_ROOT = Path(__file__).resolve().parents[1]
# alignment_machine's default max_evidence_per_requirement.
MAX_EVIDENCE_PER_SLOT = 10


def _load_job_description_cases() -> list[dict]:
    input_cases = PROJECT_ROOT / "input" / "job_description_cases.json"
    test_cases = PROJECT_ROOT / "tests" / "job_description_cases.json"
    cases_path = input_cases if input_cases.exists() else test_cases
    return json.loads(cases_path.read_text(encoding="utf-8"))["cases"]


def _find_resume_pdf() -> Path | None:
    input_dir = PROJECT_ROOT / "input"
    preferred_path = input_dir / "resume.pdf"
    if preferred_path.exists():
        return preferred_path

    pdf_files = sorted(input_dir.glob("*.pdf"))
    return pdf_files[0] if pdf_files else None


def _extract_resume_pdf(resume_path: Path) -> str:
    with resume_path.open("rb") as resume_file:
        upload = UploadFile(filename=resume_path.name, file=resume_file)
        return asyncio.run(extract_upload_text(upload))


def test_alignment_normalize_expands_and_canonicalizes_aliases():
    assert _alignment_normalize("AWS") == "amazon web services"
    assert _alignment_normalize("AWS Lambda") == "amazon web services"


def test_alignment_machine_separates_sources(monkeypatch):
    class FakeEmbedding:
        def __init__(self, vectors):
            self.embeddings = vectors

    vectors = {
        "Python": [1.0, 0.0],
        "PostgreSQL": [0.0, 1.0],
        "AWS": [1.0, 0.0],
        "Python backend development": [1.0, 0.0],
    }

    def fake_embed_document(text):
        return FakeEmbedding([vectors[item] for item in text.split("\n")])

    monkeypatch.setattr(
        "app.services.embeddings.embed_document",
        fake_embed_document,
    )
    # Drop the emission floors so a 0.0-alignment row survives: this test
    # is about source separation, not emission strength (the floors have
    # their own tests below).
    monkeypatch.setattr(
        "app.services.analysis.EMISSION_FLOORS",
        {"bulletpoints": 0.0, "keybert": 0.0, "ner": 0.0},
    )

    alignments = alignment_machine(
        {"keybert": ["PostgreSQL"], "bulletpoints": ["AWS"]},
        ["Python backend development"],
    )

    assert [(item.source, item.evidence) for item in alignments] == [
        ("bulletpoints", "AWS"),
        ("keybert", "PostgreSQL"),
    ]
    assert [item.alignment for item in alignments] == [1.0, 0.0]
    assert all(item.requirement == "Python backend development" for item in alignments)
    assert all(
        item.sub_requirement == "Python backend development"
        for item in alignments
    )


def test_alignment_machine_rejects_unknown_sources():
    try:
        alignment_machine({"keywords": ["Python"]}, ["Python"])
    except ValueError as error:
        assert str(error) == "resume_evidence contains an unknown source"
    else:
        raise AssertionError("alignment_machine accepted an unknown source")


def test_alignment_machine_accepts_ner_evidence(monkeypatch):
    class FakeEmbedding:
        def __init__(self, vectors):
            self.embeddings = vectors

    vectors = {
        "Python backend development": [1.0, 0.0],
        "Python": [1.0, 0.0],
    }

    monkeypatch.setattr(
        "app.services.embeddings.embed_document",
        lambda text: FakeEmbedding([vectors[item] for item in text.split("\n")]),
    )

    alignments = alignment_machine(
        {"ner": ["Python"]},
        ["Python backend development"],
    )

    assert [(item.source, item.evidence) for item in alignments] == [
        ("ner", "Python")
    ]
    assert alignments[0].alignment == 1.0
    assert alignments[0].sub_requirement == "Python backend development"


def test_alignment_machine_allows_empty_sources_and_returns_zero_match(monkeypatch):
    class FakeEmbedding:
        embeddings = [[1.0, 0.0]]

    monkeypatch.setattr(
        "app.services.embeddings.embed_document",
        lambda _text: FakeEmbedding(),
    )

    alignments = alignment_machine(
        {"keybert": [], "bulletpoints": []},
        ["Python backend development"],
    )

    assert len(alignments) == 1
    assert alignments[0].evidence == ""
    assert alignments[0].alignment == 0.0


def test_alignment_machine_drops_rows_below_floor(monkeypatch):
    class FakeEmbedding:
        def __init__(self, vectors):
            self.embeddings = vectors

    # Unit vectors, so the dot product against "Requirement" [1.0, 0.0] is
    # exactly the cosine similarity: 1.0, 0.8, 0.5 (exactly at the floor,
    # kept), 0.4 and -1.0 (both dropped).
    vectors = {
        "Requirement": [1.0, 0.0],
        "Strong match": [1.0, 0.0],
        "Weak match": [0.8, 0.6],
        "Borderline match": [0.5, 0.8660254037844387],
        "Below floor match": [0.4, 0.9165151389911681],
        "Negative match": [-1.0, 0.0],
    }

    monkeypatch.setattr(
        "app.services.embeddings.embed_document",
        lambda text: FakeEmbedding([vectors[item] for item in text.split("\n")]),
    )

    alignments = alignment_machine(
        {
            "keybert": [
                "Strong match",
                "Weak match",
                "Borderline match",
                "Below floor match",
                "Negative match",
            ]
        },
        ["Requirement"],
    )

    assert [item.evidence for item in alignments] == [
        "Strong match",
        "Weak match",
        "Borderline match",
    ]
    assert alignments[-1].alignment == 0.5

    # The per-sub-requirement cap still applies to what survives the floor.
    for index in range(12):
        vectors[f"Match number {index}"] = [1.0, 0.0]

    capped = alignment_machine(
        {"keybert": [f"Match number {index}" for index in range(12)]},
        ["Requirement"],
    )
    assert len(capped) == 10


def test_alignment_machine_applies_per_source_floors(monkeypatch):
    class FakeEmbedding:
        def __init__(self, vectors):
            self.embeddings = vectors

    # Both sources offer a 0.45 match. The bullet floor (0.40) keeps it;
    # the KeyBERT floor (0.50) drops it. Requirement is the JD side of
    # both channels (the decomposition falls back to the requirement), so
    # its vector is [1.0, 0.0] and each dot product is just the evidence
    # vector's first component.
    vectors = {
        "Requirement": [1.0, 0.0],
        "Bullet match": [0.45, 0.893],
        "Phrase match": [0.45, 0.893],
    }

    monkeypatch.setattr(
        "app.services.embeddings.embed_document",
        lambda text: FakeEmbedding([vectors[item] for item in text.split("\n")]),
    )

    alignments = alignment_machine(
        {"bulletpoints": ["Bullet match"], "keybert": ["Phrase match"]},
        ["Requirement"],
    )

    assert [(item.source, item.evidence, item.alignment) for item in alignments] == [
        ("bulletpoints", "Bullet match", 0.45)
    ]


def test_decompose_requirements_combines_keybert_and_ner(monkeypatch):
    monkeypatch.setattr(
        "app.services.embeddings.extract_keyphrases",
        lambda _text: ["machine learning", "Python APIs"],
    )
    monkeypatch.setattr(
        "app.services.analysis.extract_domain_entities",
        lambda _text: {"concepts": ["machine learning"], "languages": ["python"]},
    )

    assert decompose_requirements(["Build machine learning APIs"]) == {
        "Build machine learning APIs": {
            "keybert": ["machine learning", "Python APIs"],
            "ner": ["machine learning", "python"],
        }
    }


def test_alignment_machine_dedupes_evidence_across_sources_within_requirement(
    monkeypatch,
):
    class FakeEmbedding:
        def __init__(self, vectors):
            self.embeddings = vectors

    vectors = {
        "Python backend development": [1.0, 0.0],
        "Python": [1.0, 0.0],
        "Python backend": [1.0, 0.0],
    }

    monkeypatch.setattr(
        "app.services.embeddings.embed_document",
        lambda text: FakeEmbedding([vectors[item] for item in text.split("\n")]),
    )

    # The same resume string offered by two sources is cited once, by the
    # higher-priority source (bulletpoints wins the tie).
    alignments = alignment_machine(
        {"keybert": ["Python"], "bulletpoints": ["Python"]},
        ["Python backend development"],
    )
    cited = [item.evidence for item in alignments]
    assert cited.count("Python") == 1
    assert alignments[0].source == "bulletpoints"

    # The same resume string claimed by two sub-requirements of one
    # requirement is also cited once; the starved sub-requirement falls
    # back to a placeholder and is scored as 0.0.
    alignments = alignment_machine(
        {"keybert": ["Python"]},
        ["Python backend development"],
        requirement_subrequirements={
            "Python backend development": {
                "keybert": ["Python", "Python backend"],
                "ner": [],
            }
        },
    )
    cited = [item.evidence for item in alignments if item.evidence]
    assert cited.count("Python") == 1
    assert sum(1 for item in alignments if not item.evidence) == 2


def test_summarize_alignment_scores_mean_of_best_sub_requirements():
    def row(requirement, sub_requirement, alignment, evidence):
        return AlignmentEvidence(
            source="keybert",
            requirement=requirement,
            sub_requirement=sub_requirement,
            evidence=evidence,
            alignment=alignment,
            exact_match=False,
        )

    evidence = [
        # Best row for "part one" is 0.9, not 0.6.
        row("Requirement A", "part one", 0.9, "evidence one"),
        row("Requirement A", "part one", 0.6, "evidence two"),
        row("Requirement A", "part two", 0.8, "evidence three"),
        # Placeholder: no cited evidence for this sub-requirement -> 0.0.
        row("Requirement A", "part three", 0.0, ""),
        # Single-sub-requirement requirements: 0.95 -> matched.
        row("Requirement B", "Requirement B", 0.95, "solid match"),
        # Placeholder-only requirement -> missing, not silently absent.
        row("Requirement C", "Requirement C", 0.0, ""),
    ]

    matched, underrepresented, missing, score = _summarize_alignment(evidence)

    # R1: mean over ALL sub-requirements, uncovered ones count as 0.0.
    # Requirement A = (0.9 + 0.8 + 0.0) / 3 = 0.5667 -> underrepresented.
    assert matched == ["Requirement B"]
    assert underrepresented == ["Requirement A"]
    assert missing == ["Requirement C"]
    # Overall = mean of (0.5667, 0.95, 0.0) = 0.5056 -> 0.51.
    assert score == 0.51


def test_write_alignment_evidence_groups_all_matches_by_requirement(tmp_path):
    output_path = tmp_path / "alignment_evidence.json"
    write_alignment_evidence(
        [
            AlignmentEvidence(
                source="ner",
                requirement="Python backend development",
                evidence="Python",
                alignment=0.8,
                exact_match=False,
            ),
            AlignmentEvidence(
                source="bulletpoints",
                requirement="Python backend development",
                evidence="Built Python APIs",
                alignment=0.9,
                exact_match=False,
            ),
        ],
        output_path,
    )

    output = json.loads(output_path.read_text(encoding="utf-8"))

    assert output["requirements"][0]["requirement"] == "Python backend development"
    assert len(output["requirements"][0]["evidence"]) == 2


def test_write_resume_evidence_keeps_sources_separate(tmp_path):
    output_path = tmp_path / "resume_evidence.json"
    write_resume_evidence(
        {"languages": ["python"], "concepts": ["machine learning"]},
        {"python developer"},
        ["Built Python APIs"],
        output_path,
        resume_title_lines=["Tutor | Chapman University Sept 2022 - May 2023"],
    )

    output = json.loads(output_path.read_text(encoding="utf-8"))

    assert output == {
        "resume_evidence": {
            "ner": {"languages": ["python"], "concepts": ["machine learning"]},
            "keybert": ["python developer"],
            "bulletpoints": ["Built Python APIs"],
            "titles": ["Tutor | Chapman University Sept 2022 - May 2023"],
        }
    }


def test_alignment_against_job_description_cases():
    """Run every collected job description against the configured resume PDF."""
    resume_path = _find_resume_pdf()
    if resume_path is None:
        pytest.skip(
            "Add a resume PDF to input/ to run the fixture-driven alignment test"
        )

    resume_text = _extract_resume_pdf(resume_path)
    assert resume_text, f"No text could be extracted from {resume_path}"

    extraction_text = preprocess_for_semantic_extraction(resume_text)
    embedded_resume = embed_document(extraction_text)
    resume_keyphrases = extract_keyphrases(
        extraction_text,
        embedded_document=embedded_resume,
    )
    resume_entities = extract_domain_entities(extraction_text)
    resume_evidence_lines = extract_evidence_lines(
        resume_text,
        {"experience", "projects"},
    )
    resume_bullets = resume_evidence_lines["bulletpoints"]
    resume_title_lines = resume_evidence_lines["titles"]
    resume_evidence = {
        "ner": _flatten_entities(resume_entities),
        "keybert": resume_keyphrases,
        "bulletpoints": resume_bullets,
    }
    write_resume_evidence(
        resume_entities,
        resume_keyphrases,
        resume_bullets,
        resume_title_lines=resume_title_lines,
    )

    output_dir = PROJECT_ROOT / "output"
    failures = []
    for case in _load_job_description_cases():
        evidence = alignment_machine(
            resume_evidence,
            case["expected_requirements"],
            requirement_subrequirements=decompose_requirements(
                case["expected_requirements"]
            ),
        )

        write_alignment_evidence(
            evidence,
            output_dir / f"alignment_evidence_{case['case_id']}.json",
        )
        if not evidence:
            failures.append(f"{case['case_id']}: no alignment evidence produced")
            continue
        if not all(item.requirement and item.source for item in evidence):
            failures.append(f"{case['case_id']}: malformed alignment evidence")

        # Every expected requirement must be accounted for, and none
        # invented: coverage is exact in both directions.
        covered = {item.requirement for item in evidence}
        expected = set(case["expected_requirements"])
        if covered != expected:
            failures.append(
                f"{case['case_id']}: requirement coverage mismatch "
                f"(missing={sorted(expected - covered)}, "
                f"unexpected={sorted(covered - expected)})"
            )

        # After the emission floor, placeholder rows would make a plain
        # "non-empty" check vacuous: demand at least one real citation.
        if not any(item.evidence.strip() for item in evidence):
            failures.append(f"{case['case_id']}: only placeholder rows produced")

        # No sub-requirement may emit more than the cap — this is the
        # guard against the historical row-count explosion.
        per_slot: dict[tuple[str, str], int] = {}
        for item in evidence:
            key = (item.requirement, item.sub_requirement)
            per_slot[key] = per_slot.get(key, 0) + 1
        overcrowded = sorted(
            key for key, count in per_slot.items() if count > MAX_EVIDENCE_PER_SLOT
        )
        if overcrowded:
            failures.append(
                f"{case['case_id']}: sub-requirements over the evidence cap: "
                f"{overcrowded}"
            )

        # 'skills' and 'project experience' can only enter the keybert channel
        # from heading lines, which preprocess_for_semantic_extraction removes.
        # 'keywords' is excluded from this set deliberately: the word appears
        # in genuine resume content ("identify critical skills, keywords, ...").
        heading_like_phrases = {"skills", "project experience"}
        # A PDF line-wrap leaves a continuation fragment: it starts with a
        # lowercase connective, or ends on a hyphenation break.
        continuation_starts = {
            "and",
            "or",
            "but",
            "with",
            "the",
            "to",
            "of",
            "in",
            "at",
            "for",
            "by",
            "from",
            "into",
            "onto",
            "as",
            "on",
            "is",
            "are",
            "was",
            "were",
            "this",
            "that",
            "these",
            "those",
        }
        cited_evidence = {
            item.evidence.strip().lower()
            for item in evidence
            if item.evidence.strip()  # placeholders carry no citation
        }
        if cited_evidence & heading_like_phrases:
            failures.append(
                f"{case['case_id']}: heading-like strings cited as evidence: "
                f"{sorted(cited_evidence & heading_like_phrases)}"
            )

        fragments = sorted(
            cited
            for cited in cited_evidence
            if len(cited) < 3
            or cited.endswith("-")
            or cited.split()[0] in continuation_starts
        )
        if fragments:
            failures.append(
                f"{case['case_id']}: wrap-fragment evidence cited: {fragments}"
            )

    assert not failures, "Fixture alignment failures:\n" + "\n".join(failures)