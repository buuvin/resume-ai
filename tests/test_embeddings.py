from pathlib import Path
from typing import ClassVar

import pytest

from app.services.analysis import parse_sections
from app.services.embeddings import (
    EmbeddedDocument,
    compare_bullet_embeddings,
    embed_document,
    extract_bullet_points,
    extract_evidence_lines,
    extract_keyphrases,
    split_document_lines,
)


class FakeEmbeddingModel:
    def encode(self, lines, normalize_embeddings, convert_to_numpy):
        assert normalize_embeddings is True
        assert convert_to_numpy is True
        return [[float(index), float(len(line))] for index, line in enumerate(lines)]


class FakeKeyBERTModel:
    def extract_keywords(
        self,
        text,
        keyphrase_ngram_range,
        stop_words,
        top_n,
        doc_embeddings,
        use_mmr,
        diversity,
        vectorizer,
    ):
        assert text == "Python data pipelines"
        assert keyphrase_ngram_range == (2, 4)
        assert stop_words == "english"
        assert top_n == 10
        assert doc_embeddings.shape == (1, 2)
        assert use_mmr is True
        assert diversity == 0.5
        assert vectorizer is not None
        return [("data pipelines", 0.9), ("python", 0.8)]


class FakeBulletEmbeddingModel:
    vectors: ClassVar[dict[str, list[float]]] = {
        "Built APIs in Python": [1.0, 0.0],
        "Improved service latency": [0.0, 1.0],
        "Python backend development": [1.0, 0.0],
        "Optimize SQL queries": [0.0, 1.0],
    }

    def encode(self, texts, normalize_embeddings, convert_to_numpy):
        assert normalize_embeddings is False
        assert convert_to_numpy is True
        return [self.vectors[text] for text in texts]


def test_split_document_lines_omits_blank_lines():
    assert split_document_lines("Skills\n\nPython\n  SQL  ") == [
        "Skills",
        "Python",
        "SQL",
    ]


def test_embed_document_stores_each_line_and_vector():
    document = embed_document(
        "Skills\n\nPython\nSQL",
        model=FakeEmbeddingModel(),
    )

    assert document.lines == ["Skills", "Python", "SQL"]
    assert document.embeddings == [[0.0, 6.0], [1.0, 6.0], [2.0, 3.0]]
    assert len(document.lines) == len(document.embeddings)


def test_embed_empty_document_without_loading_model():
    document = embed_document("\n  ")

    assert document.lines == []
    assert document.embeddings == []


def test_extract_keyphrases_passes_existing_embeddings_to_keybert():
    phrases = extract_keyphrases(
        "Python data pipelines",
        embedded_document=EmbeddedDocument(
            lines=["Python", "data pipelines"],
            embeddings=[[1.0, 0.0], [0.0, 1.0]],
        ),
        model=FakeKeyBERTModel(),
    )

    assert phrases == ["data pipelines", "python"]


def test_extract_bullet_points_is_limited_to_requested_sections():
    text = """
    Summary
    - Ignore this bullet
    Experience
    - Built APIs in Python
    Projects
    1. Improved service latency
    Skills
    - Also ignore this bullet
    """

    assert extract_bullet_points(text, {"experience", "projects"}) == [
        "Built APIs in Python",
        "1. Improved service latency",
    ]


def test_extract_bullet_points_keeps_lines_longer_than_two_words():
    text = """
    Experience
    Python
    Built APIs in Python
    Improved latency significantly
    """

    assert extract_bullet_points(text, {"experience"}) == [
        "Built APIs in Python",
        "Improved latency significantly",
    ]


def test_qualifications_are_parsed_as_requirements():
    sections = parse_sections("Qualifications\nPython\nRequirements\nSQL")

    assert sections["requirements"] == "Python\nSQL\n"


def test_compare_bullet_embeddings_returns_ranked_pairs_and_matrix():
    result = compare_bullet_embeddings(
        "Experience\n- Built APIs in Python\n- Improved service latency",
        "Requirements\n- Python backend development\n- Optimize SQL queries",
        model=FakeBulletEmbeddingModel(),
    )

    assert result.similarity_matrix == [[1.0, 0.0], [0.0, 1.0]]
    assert result.average_similarity == 0.5
    assert result.top_matches[0].resume_bullet == "Built APIs in Python"
    assert result.top_matches[0].job_description_bullet == "Python backend development"
    assert result.lowest_matches[0].similarity_score == 0.0


def test_compare_bullet_embeddings_handles_missing_bullets():
    result = compare_bullet_embeddings(
        "Summary\nNo bullet marker",
        "Requirements\n- Python",
        model=FakeBulletEmbeddingModel(),
    )

    assert result.similarity_matrix == []
    assert result.average_similarity == 0.0


def test_extract_bullet_points_joins_wrapped_lines():
    text = """
    Experience
    Student Researcher | Chapman University Sept 2025 - Present
    ● Designed and implemented end-to-end ML pipelines for noisy data, including data
    cleaning, normalization, and feature extraction
    """

    assert extract_bullet_points(text, {"experience"}) == [
        "Designed and implemented end-to-end ML pipelines for noisy data, "
        "including data cleaning, normalization, and feature extraction"
    ]


def test_extract_bullet_points_excludes_headings():
    text = """
    Experience
    ● Built APIs in Python
    Project Experience
    ● Improved service latency
    """

    bullets = extract_bullet_points(text, {"experience", "projects"})

    assert bullets == ["Built APIs in Python", "Improved service latency"]
    assert not any("experience" in bullet.lower() for bullet in bullets)


def test_extract_bullet_points_excludes_title_lines():
    text = """
    Experience
    ● Built APIs in Python
    AI Trainer (Contract) | Data Annotation Summer 2025 - Present
    ● Improved service latency
    """

    assert extract_bullet_points(text, {"experience"}) == [
        "Built APIs in Python",
        "Improved service latency",
    ]


def test_extract_bullet_points_excludes_skills_label_lines():
    text = """
    Skills
    Programming & Tools: Python, SQL, Git, Docker, Copilot
    Experience
    ● Built APIs in Python
    """

    assert extract_bullet_points(text, {"experience"}) == ["Built APIs in Python"]


def test_extract_bullet_points_supports_all_bullet_markers():
    text = """
    Experience
    ● Circle bullet in Python
    • Solid bullet with SQL
    - Dash bullet with Git
    * Star bullet with Docker
    """

    assert extract_bullet_points(text, {"experience"}) == [
        "Circle bullet in Python",
        "Solid bullet with SQL",
        "Dash bullet with Git",
        "Star bullet with Docker",
    ]


def test_extract_bullet_points_keeps_short_continuations():
    text = """
    Experience
    ● Tutored Data Structures and guided students in problem-solving strategies for
    coursework
    """

    assert extract_bullet_points(text, {"experience"}) == [
        "Tutored Data Structures and guided students in problem-solving strategies "
        "for coursework"
    ]


def test_extract_bullet_points_joins_around_title_line_boundaries():
    text = """
    Experience
    ● Built APIs in Python for service reliability.
    Tutor | Chapman University Sept 2022 – May 2023
    ● Led Calculus I review sessions
    """

    assert extract_bullet_points(text, {"experience"}) == [
        "Built APIs in Python for service reliability.",
        "Led Calculus I review sessions",
    ]


def test_extract_evidence_lines_tags_title_lines_separately():
    text = """
    Experience
    Student Researcher | Chapman University Sept 2025 - Present
    ● Built APIs in Python
    ● Built dashboards | Spring 2025 for inventory decisions
    """

    evidence = extract_evidence_lines(text, {"experience"})

    assert evidence["bulletpoints"] == [
        "Built APIs in Python",
        "Built dashboards | Spring 2025 for inventory decisions",
    ]
    assert evidence["titles"] == [
        "Student Researcher | Chapman University Sept 2025 - Present"
    ]


def test_reference_resume_bullet_pool_has_21_bullets():
    pdfplumber = pytest.importorskip("pdfplumber")

    pdf_path = (
        Path(__file__).resolve().parents[1] / "input" / "Bhuvan_Balagar_Resume-1.pdf"
    )
    with pdfplumber.open(pdf_path) as pdf:
        resume_text = "\n".join(page.extract_text() or "" for page in pdf.pages)

    bullets = extract_bullet_points(resume_text, {"experience", "projects"})

    assert len(bullets) == 21
    # No standalone wrap fragments survived; they must be joined into parents.
    assert not any(
        bullet.startswith("cleaning, normalization, and feature extraction")
        for bullet in bullets
    )
    # No headings, no title/metadata lines.
    assert not any(
        bullet.strip().lower() in {"skills", "project experience", "work experience"}
        for bullet in bullets
    )
    assert not any("|" in bullet for bullet in bullets)