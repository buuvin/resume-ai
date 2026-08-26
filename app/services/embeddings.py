from dataclasses import dataclass
from functools import lru_cache
from typing import Any

MODEL_NAME = "all-MiniLM-L6-v2"


@dataclass
class EmbeddedDocument:
    """Line-level text and vectors retained for later KeyBERT processing."""

    lines: list[str]
    embeddings: list[list[float]]


def split_document_lines(text: str) -> list[str]:
    return [line.strip() for line in (text or "").splitlines() if line.strip()]


@lru_cache(maxsize=1)
def get_embedding_model() -> Any:
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(MODEL_NAME)


def embed_document(text: str, model: Any | None = None) -> EmbeddedDocument:
    lines = split_document_lines(text)
    if not lines:
        return EmbeddedDocument(lines=[], embeddings=[])

    embedding_model = model or get_embedding_model()
    vectors = embedding_model.encode(
        lines,
        normalize_embeddings=True,
        convert_to_numpy=True,
    )

    return EmbeddedDocument(
        lines=lines,
        embeddings=[list(vector) for vector in vectors],
    )