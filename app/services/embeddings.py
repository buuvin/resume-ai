from dataclasses import dataclass
from functools import lru_cache
from keyphrase_vectorizers import KeyphraseCountVectorizer
from typing import Any

import numpy as np

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


@lru_cache(maxsize=1)
def get_keybert_model() -> Any:
    from keybert import KeyBERT

    return KeyBERT(model=get_embedding_model())


def extract_keyphrases(
    text: str,
    embedded_document: EmbeddedDocument | None = None,
    model: Any | None = None,
    top_n: int = 10,
) -> list[str]:
    """Extract KeyBERT phrases while reusing the document's existing embeddings."""
    embedded = embedded_document or embed_document(text)
    if not embedded.lines:
        return []

    document_embedding = np.mean(np.asarray(embedded.embeddings), axis=0).reshape(1, -1)
    keybert_model = model or get_keybert_model()
    vectorizer = KeyphraseCountVectorizer()
    phrases = keybert_model.extract_keywords(
        text,
        keyphrase_ngram_range=(1, 3),
        stop_words="english",
        top_n=top_n,
        doc_embeddings=document_embedding,
        use_mmr=True,
        diversity=0.5,
        vectorizer=vectorizer
    )
    return [phrase for phrase, _score in phrases]