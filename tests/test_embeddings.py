from app.services.embeddings import (
    EmbeddedDocument,
    embed_document,
    extract_keyphrases,
    split_document_lines,
)


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