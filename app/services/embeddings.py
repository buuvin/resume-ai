from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import numpy as np
from keyphrase_vectorizers import KeyphraseCountVectorizer

MODEL_NAME = "all-MiniLM-L6-v2"


@dataclass
class EmbeddedDocument:
    """Line-level text and vectors retained for later KeyBERT processing."""

    lines: list[str]
    embeddings: list[list[float]]


@dataclass
class BulletMatch:
    resume_bullet: str
    job_description_bullet: str
    similarity_score: float


@dataclass
class BulletSimilarityResult:
    resume_bullets: list[str]
    job_description_bullets: list[str]
    similarity_matrix: list[list[float]]
    top_matches: list[BulletMatch]
    lowest_matches: list[BulletMatch]
    average_similarity: float


def split_document_lines(text: str) -> list[str]:
    return [line.strip() for line in (text or "").splitlines() if line.strip()]


def extract_bullet_points(text: str, section_names: set[str]) -> list[str]:
    """Return parsed section lines containing more than two words.

    The historical name is retained for compatibility. Section membership and line
    length determine which lines are embedded; bullet punctuation is ignored.
    """
    from app.services.analysis import parse_sections

    bullets = []
    for section_name, section_text in parse_sections(text).items():
        if section_name not in section_names:
            continue
        for line in section_text.splitlines():
            cleaned_line = line.strip()
            if len(cleaned_line.split()) > 2:
                bullets.append(cleaned_line)
    return bullets


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


def compare_bullet_embeddings(
    resume_text: str,
    job_description_text: str,
    model: Any | None = None,
    top_n: int = 5,
) -> BulletSimilarityResult:
    """Compare resume experience/project bullets with job requirement bullets."""
    resume_bullets = extract_bullet_points(
        resume_text, {"experience", "projects", "skills"}
    )
    job_bullets = extract_bullet_points(
        job_description_text, {"requirements", "preferred", "skills"}
    )
    if not resume_bullets or not job_bullets:
        return BulletSimilarityResult(
            resume_bullets=resume_bullets,
            job_description_bullets=job_bullets,
            similarity_matrix=[],
            top_matches=[],
            lowest_matches=[],
            average_similarity=0.0,
        )

    embedding_model = model or get_embedding_model()
    resume_vectors = np.asarray(
        embedding_model.encode(
            resume_bullets,
            normalize_embeddings=False,
            convert_to_numpy=True,
        ),
        dtype=float,
    )
    job_vectors = np.asarray(
        embedding_model.encode(
            job_bullets,
            normalize_embeddings=False,
            convert_to_numpy=True,
        ),
        dtype=float,
    )
    resume_norms = np.linalg.norm(resume_vectors, axis=1, keepdims=True)
    job_norms = np.linalg.norm(job_vectors, axis=1, keepdims=True)
    resume_unit = np.divide(
        resume_vectors,
        resume_norms,
        out=np.zeros_like(resume_vectors),
        where=resume_norms != 0,
    )
    job_unit = np.divide(
        job_vectors,
        job_norms,
        out=np.zeros_like(job_vectors),
        where=job_norms != 0,
    )
    matrix = np.clip(resume_unit @ job_unit.T, -1.0, 1.0)

    pairs = [
        BulletMatch(
            resume_bullets[row],
            job_bullets[column],
            float(matrix[row, column]),
        )
        for row in range(len(resume_bullets))
        for column in range(len(job_bullets))
    ]
    return BulletSimilarityResult(
        resume_bullets=resume_bullets,
        job_description_bullets=job_bullets,
        similarity_matrix=matrix.tolist(),
        top_matches=sorted(
            pairs, key=lambda pair: pair.similarity_score, reverse=True
        )[:top_n],
        lowest_matches=sorted(pairs, key=lambda pair: pair.similarity_score)[:top_n],
        average_similarity=float(matrix.mean()),
    )


def print_bullet_similarity(result: BulletSimilarityResult) -> None:
    """Print a human-readable report while retaining structured data for the pipeline."""
    print("[embeddings] resume/JD bullet similarity", flush=True)
    if not result.similarity_matrix:
        print("[embeddings] no matching resume or JD bullet sections found", flush=True)
        return
    print(f"[embeddings] average similarity: {result.average_similarity:.4f}", flush=True)
    for label, matches in (("top", result.top_matches), ("lowest", result.lowest_matches)):
        print(f"[embeddings] {label} matches:", flush=True)
        for match in matches:
            print(
                f"  {match.similarity_score:.4f} | resume: {match.resume_bullet} | JD: {match.job_description_bullet}",
                flush=True,
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