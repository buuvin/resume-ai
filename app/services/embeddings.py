import re
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

import numpy as np
from keyphrase_vectorizers import KeyphraseCountVectorizer

from app.services.analysis import clean_text

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
    resume_title_lines: list[str] = field(default_factory=list)


BULLET_MARKER_PATTERN = re.compile(r"^(?:[●•◦*‣⁃]\s*|[-–—]\s+)")
MONTH_DATE_PATTERN = re.compile(
    r"\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]* \d{4}\b"
)
SEASON_DATE_PATTERN = re.compile(r"\b(?:spring|summer|fall|winter) \d{4}\b")
YEAR_TO_PRESENT_PATTERN = re.compile(r"\b\d{4}\b.*\bpresent\b|\bpresent\b.*\b\d{4}\b")


def split_document_lines(text: str) -> list[str]:
    return [line.strip() for line in (text or "").splitlines() if line.strip()]


def _strip_bullet_marker(line: str) -> str:
    """Remove a leading bullet marker; return the line unchanged otherwise."""
    return BULLET_MARKER_PATTERN.sub("", line, count=1)


def _is_title_line(line: str) -> bool:
    """Detect job-title / company / date-range metadata lines.

    A title line has no bullet marker, contains a pipe separator, and carries a
    date-range token (month year, season year, a year range, or an explicit
    'in progress' marker for ongoing work).
    """
    if _strip_bullet_marker(line) != line:
        return False
    if "|" not in line:
        return False
    normalized = clean_text(line)
    return bool(
        MONTH_DATE_PATTERN.search(normalized)
        or SEASON_DATE_PATTERN.search(normalized)
        or YEAR_TO_PRESENT_PATTERN.search(normalized)
        or re.search(r"\bin progress\b", normalized)
    )


def extract_evidence_lines(
    text: str,
    section_names: set[str],
    minimum_words: int = 3,
) -> dict[str, list[str]]:
    """Join wrapped bullet lines and classify them into tagged evidence sources.

    Lines starting with a bullet marker begin a bullet; following lines without
    a marker are continuations of the open bullet (PDF line-wrapping repair).
    Orphan lines are classified: title/metadata lines are tagged separately,
    other content lines stand alone. The minimum-word filter applies to the
    joined result, never to individual wrapped fragments.
    """
    from app.services.analysis import parse_sections

    bullets: list[str] = []
    titles: list[str] = []
    for section_name, section_text in parse_sections(text).items():
        if section_name not in section_names:
            continue

        open_bullet: list[str] = []

        def flush_open_bullet() -> None:
            nonlocal open_bullet
            if open_bullet:
                joined = " ".join(open_bullet)
                if len(joined.split()) >= minimum_words:
                    bullets.append(joined)
                open_bullet = []

        for line in section_text.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            markerless = _strip_bullet_marker(stripped)
            if markerless != stripped:
                flush_open_bullet()
                open_bullet = [markerless]
            elif open_bullet:
                if _is_title_line(stripped):
                    flush_open_bullet()
                    titles.append(stripped)
                else:
                    open_bullet.append(stripped)
            elif _is_title_line(stripped):
                titles.append(stripped)
            elif len(stripped.split()) >= minimum_words:
                bullets.append(stripped)
        flush_open_bullet()

    return {"bulletpoints": bullets, "titles": titles}


def extract_bullet_points(
    text: str,
    section_names: set[str],
    minimum_words: int = 3,
) -> list[str]:
    """Return joined bullet lines for the requested sections.

    The historical name is retained for compatibility. Wrapped lines are joined
    into their parent bullet and title/metadata lines are excluded; see
    extract_evidence_lines for the tagged variant.
    """
    return extract_evidence_lines(text, section_names, minimum_words)["bulletpoints"]


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
    job_section_names: set[str] | None = None,
    job_minimum_words: int = 3,
) -> BulletSimilarityResult:
    """Compare resume experience/project bullets with job requirement bullets."""
    resume_evidence = extract_evidence_lines(
        resume_text, {"experience", "projects"}
    )
    resume_bullets = resume_evidence["bulletpoints"]
    resume_title_lines = resume_evidence["titles"]
    job_bullets = extract_bullet_points(
        job_description_text,
        job_section_names or {"requirements", "preferred", "skills"},
        minimum_words=job_minimum_words,
    )
    if not resume_bullets or not job_bullets:
        return BulletSimilarityResult(
            resume_bullets=resume_bullets,
            job_description_bullets=job_bullets,
            similarity_matrix=[],
            top_matches=[],
            lowest_matches=[],
            average_similarity=0.0,
            resume_title_lines=resume_title_lines,
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
        resume_title_lines=resume_title_lines,
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
        keyphrase_ngram_range=(2, 4),
        stop_words="english",
        top_n=top_n,
        doc_embeddings=document_embedding,
        use_mmr=True,
        diversity=0.5,
        vectorizer=vectorizer
    )
    return [phrase for phrase, _score in phrases]