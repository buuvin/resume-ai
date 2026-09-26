import asyncio
import json
from pathlib import Path

import pytest
from fastapi import UploadFile

from app.models.schemas import AlignmentEvidence
from app.services.analysis import (
    _alignment_normalize,
    _flatten_entities,
    alignment_machine,
    extract_domain_entities,
    write_alignment_evidence,
    write_resume_evidence,
)
from app.services.embeddings import embed_document, extract_bullet_points, extract_keyphrases
from app.services.ingestion import extract_upload_text

PROJECT_ROOT = Path(__file__).resolve().parents[1]


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


def test_alignment_machine_returns_strongest_evidence_across_sources(monkeypatch):
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

    alignments = alignment_machine(
        {
            "ner": ["Python"],
            "keybert": ["PostgreSQL"],
            "bulletpoints": ["AWS"],
        },
        ["Python backend development"],
    )

    assert [(item.source, item.evidence) for item in alignments] == [
        ("ner", "Python"),
        ("bulletpoints", "AWS"),
    ]
    assert [item.alignment for item in alignments] == [1.0, 1.0]
    assert all(item.requirement == "Python backend development" for item in alignments)


def test_alignment_machine_rejects_unknown_sources():
    try:
        alignment_machine({"keywords": ["Python"]}, ["Python"])
    except ValueError as error:
        assert str(error) == "resume_evidence contains an unknown source"
    else:
        raise AssertionError("alignment_machine accepted an unknown source")


def test_alignment_machine_allows_empty_sources_and_returns_zero_match(monkeypatch):
    class FakeEmbedding:
        embeddings = [[1.0, 0.0]]

    monkeypatch.setattr(
        "app.services.embeddings.embed_document",
        lambda _text: FakeEmbedding(),
    )

    alignments = alignment_machine(
        {"ner": [], "keybert": [], "bulletpoints": []},
        ["Python backend development"],
    )

    assert len(alignments) == 1
    assert alignments[0].evidence == ""
    assert alignments[0].alignment == 0.0


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
    )

    output = json.loads(output_path.read_text(encoding="utf-8"))

    assert output == {
        "resume_evidence": {
            "ner": {"languages": ["python"], "concepts": ["machine learning"]},
            "keybert": ["python developer"],
            "bulletpoints": ["Built Python APIs"],
        }
    }


def test_alignment_against_job_description_cases():
    """Run every collected job description against the configured resume PDF."""
    resume_path = _find_resume_pdf()
    if resume_path is None:
        pytest.skip("Add a resume PDF to input/ to run the fixture-driven alignment test")

    resume_text = _extract_resume_pdf(resume_path)
    assert resume_text, f"No text could be extracted from {resume_path}"

    embedded_resume = embed_document(resume_text)
    resume_keyphrases = extract_keyphrases(
        resume_text,
        embedded_document=embedded_resume,
    )
    resume_entities = extract_domain_entities(resume_text)
    resume_bullets = extract_bullet_points(
        resume_text,
        {"experience", "projects", "skills"},
    )
    resume_evidence = {
        "ner": _flatten_entities(resume_entities),
        "keybert": resume_keyphrases,
        "bulletpoints": resume_bullets,
    }
    write_resume_evidence(
        resume_entities,
        resume_keyphrases,
        resume_bullets,
    )

    output_dir = PROJECT_ROOT / "output"
    failures = []
    for case in _load_job_description_cases():
        evidence = alignment_machine(
            resume_evidence,
            case["expected_requirements"],
        )

        write_alignment_evidence(
            evidence,
            output_dir / f"alignment_evidence_{case['case_id']}.json",
        )
        if not evidence:
            failures.append(f"{case['case_id']}: no alignment evidence produced")
        elif not all(item.requirement and item.source for item in evidence):
            failures.append(f"{case['case_id']}: malformed alignment evidence")

    assert not failures, "Fixture alignment failures:\n" + "\n".join(failures)