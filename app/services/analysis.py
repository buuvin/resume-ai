import re

def clean_text(text: str) -> str:
    text = text.lower()
    text = re.sub(r'[^\w\s]', ' ', text)  # remove punctuation
    return text

STOPWORDS = {
    "the", "and", "with", "for", "a", "an", "to", "of", "in", "on", "is"
}

def tokenize(text: str):
    words = text.split()
    return [w for w in words if w not in STOPWORDS]


COMMON_PHRASES = [
    "machine learning",
    "deep learning",
    "data science",
    "natural language processing",
    "computer vision"
]

def extract_keywords(text: str):
    cleaned = clean_text(text)

    keywords = set()
    tokens = tokenize(cleaned)
    return set(tokens)

def compare_keywords(resume_keywords, job_keywords):
    matched = resume_keywords & job_keywords
    missing = job_keywords - resume_keywords

    score = len(matched) / max(len(job_keywords), 1)

    return matched, missing, score

def analyze_resume(resume: str, job_description: str):
    resume_keywords = extract_keywords(resume)
    job_keywords = extract_keywords(job_description)

    matched, missing, score = compare_keywords(
        resume_keywords, job_keywords
    )

    return {
        "matched_skills": list(matched),
        "missing_skills": list(missing),
        "alignment_score": round(score, 2)
    }