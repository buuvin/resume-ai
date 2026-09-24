from app.services.analysis import _alignment_normalize, alignment_machine


def test_alignment_normalize_expands_and_canonicalizes_aliases():
    assert _alignment_normalize("AWS") == "amazon web services"
    assert _alignment_normalize("AWS Lambda") == "amazon web services"


def test_alignment_machine_returns_best_evidence_for_each_requirement(monkeypatch):
    class FakeEmbedding:
        def __init__(self, vectors):
            self.embeddings = vectors

    vectors = {
        "Python": [1.0, 0.0],
        "PostgreSQL": [0.0, 1.0],
        "AWS": [1.0, 0.0],
    }

    def fake_embed_document(text):
        return FakeEmbedding([vectors[item] for item in text.split("\n")])

    monkeypatch.setattr(
        "app.services.embeddings.embed_document",
        fake_embed_document,
    )

    alignments = alignment_machine(
        "ner",
        ["Python", "PostgreSQL"],
        ["AWS", "PostgreSQL"],
    )

    assert [(item.requirement, item.evidence) for item in alignments] == [
        ("AWS", "Python"),
        ("PostgreSQL", "PostgreSQL"),
    ]
    assert [item.alignment for item in alignments] == [1.0, 1.0]
    assert [item.exact_match for item in alignments] == [False, True]


def test_alignment_machine_rejects_unknown_sources():
    try:
        alignment_machine("keywords", ["Python"], ["Python"])
    except ValueError as error:
        assert str(error) == "source must be 'ner', 'keybert', or 'bulletpoints'"
    else:
        raise AssertionError("alignment_machine accepted an unknown source")