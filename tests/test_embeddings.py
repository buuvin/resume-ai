from typing import ClassVar

from app.services.embeddings import (
    EmbeddedDocument,
    compare_bullet_embeddings,
    embed_document,
    extract_bullet_points,
    extract_keyphrases,
    split_document_lines,
)
from app.services.analysis import parse_sections


class FakeEmbeddingModel:
    def encode(self, lines, normalize_embeddings, convert_to_numpy):
        assert normalize_embeddings is True
        assert convert_to_numpy is True
        return [[float(index), float(len(line))] for index, line in enumerate(lines)]


class FakeKeyBERTModel:
    def extract_keywords(self, text, keyphrase_ngram_range, stop_words, top_n, doc_embeddings):
        assert text == "Python data pipelines"
        assert keyphrase_ngram_range == (1, 3)
        assert stop_words == "english"
        assert top_n == 10
        assert doc_embeddings.shape == (1, 2)
        return [("data pipelines", 0.9), ("python", 0.8)]


class FakeBulletEmbeddingModel:
    vectors: ClassVar[dict[str, list[float]]] = {
        "- Built APIs in Python": [1.0, 0.0],
        "- Improved service latency": [0.0, 1.0],
        "- Python backend development": [1.0, 0.0],
        "- Optimize SQL queries": [0.0, 1.0],
    }

    def encode(self, texts, normalize_embeddings, convert_to_numpy):
        assert normalize_embeddings is False
        assert convert_to_numpy is True
        return [self.vectors[text] for text in texts]


def test_split_document_lines_omits_blank_lines():
    assert split_document_lines("Skills\n\nPython\n  SQL  ") == ["Skills", "Python", "SQL"]


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
        "- Built APIs in Python",
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
    assert result.top_matches[0].resume_bullet == "- Built APIs in Python"
    assert result.top_matches[0].job_description_bullet == "- Python backend development"
    assert result.lowest_matches[0].similarity_score == 0.0


def test_compare_bullet_embeddings_handles_missing_bullets():
    result = compare_bullet_embeddings(
        "Summary\nNo bullet marker",
        "Requirements\n- Python",
        model=FakeBulletEmbeddingModel(),
    )

    assert result.similarity_matrix == []
    assert result.average_similarity == 0.0