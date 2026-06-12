import re
import unicodedata

from app.models.schemas import AnalysisResult

COMMON_PHRASES = [
    "machine learning",
    "deep learning",
    "data science",
    "natural language processing",
    "computer vision",
]

ABBREVIATIONS = {
    "ml": "machine learning",
    "dl": "deep learning",
    "ds": "data science",
    "nlp": "natural language processing",
    "cv": "computer vision",
    "js": "javascript",
    "py": "python",
    "postgres": "postgresql",
}

PHRASE_PATTERN = re.compile(
    # Match any known multi-word skill phrase as a whole, not as separate tokens.
    r"\b(?:" + "|".join(re.escape(phrase) for phrase in sorted(COMMON_PHRASES, key=len, reverse=True)) + r")\b"
)

def clean_text(text: str) -> str:
    # Normalize visually similar Unicode characters so matching is consistent across copy/pasted text.
    text = unicodedata.normalize("NFKC", text or "")
    text = text.lower()
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def expand_abbreviations(text: str) -> str:
    expanded_text = text
    for abbreviation, replacement in ABBREVIATIONS.items():
        # Replace short aliases like "nlp" before phrase and token matching runs.
        expanded_text = re.sub(
            rf"\b{re.escape(abbreviation)}\b",
            replacement,
            expanded_text,
        )
    return expanded_text


def match_phrases(text: str):
    matched_phrases = set()
    for match in PHRASE_PATTERN.finditer(text):
        # Collect exact phrase matches so they can be scored separately from single-word tokens.
        matched_phrases.add(match.group(0))
    return matched_phrases

STOPWORDS = {
    "the", "and", "with", "for", "a", "an", "to", "of", "in", "on", "is"
}

def tokenize(text: str):
    words = text.split()
    return [w for w in words if w not in STOPWORDS]

def extract_keywords(text: str):
    cleaned = clean_text(text)
    expanded = expand_abbreviations(cleaned)

    keywords = set()
    phrases = match_phrases(expanded)
    keywords.update(phrases)

    token_text = expanded
    for phrase in phrases:
        # Remove phrase hits before tokenizing so the same words are not counted twice.
        token_text = re.sub(rf"\b{re.escape(phrase)}\b", " ", token_text)

    tokens = tokenize(token_text)
    keywords.update(tokens)
    return keywords

def compare_keywords(resume_keywords, job_keywords):
    matched = resume_keywords & job_keywords
    missing = job_keywords - resume_keywords

    score = len(matched) / max(len(job_keywords), 1)

    return matched, missing, score

def analyze_resume(resume: str, job_description: str, supplemental: str):
    resume_keywords = extract_keywords(resume)
    job_keywords = extract_keywords(job_description)

    matched, missing, score = compare_keywords(
        resume_keywords, job_keywords
    )

    return AnalysisResult(
        matched_skills=list(matched),
        missing_skills=list(missing),
        alignment_score=round(score, 2)
    )