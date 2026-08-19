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

# Synonyms map various surface forms to a canonical skill/token name. Keep this small and
# high-value; it can be expanded over time or loaded from an external taxonomy.
SYNONYMS = {
    "etl": "data pipeline",
    "data pipelines": "data pipeline",
    "data engineering": "data pipeline",
    "aws": "amazon web services",
    "aws lambda": "amazon web services",
    "gcp": "google cloud",
    "ci/cd": "ci cd",
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


def parse_sections(text: str):
    """Split a resume-like text into high-level sections using common headings.

    Returns an ordered dict-like mapping of section_name -> section_text.
    If no headings are detected, returns {'body': text}.
    """
    if not text or not text.strip():
        return {"body": ""}

    headings = {
        "summary": ["summary", "professional summary", "profile"],
        "skills": ["skills", "technical skills", "skillset"],
        "experience": ["experience", "work experience", "professional experience"],
        "projects": ["projects", "personal projects"],
        "education": ["education", "academic"],
        "certifications": ["certifications", "licenses"],
        "requirements": ["requirements", "qualifications"],
        "preferred": ["nice to have", "nice-to-have", "preferred", "nice to haves"],
    }

    heading_lookup = {}
    for key, variants in headings.items():
        for v in variants:
            heading_lookup[v] = key

    sections = {}
    current = None
    lines = text.splitlines()
    for raw in lines:
        line = raw.strip()
        if not line:
            # preserve paragraph breaks inside a section
            if current:
                sections[current] += "\n"
            continue

        low = re.sub(r"[^\w\s]", " ", line).strip().lower()
        key = None
        # detect heading if the line equals or starts with a known heading phrase
        for variant, section_key in heading_lookup.items():
            if low == variant or low.startswith(variant + " ") or low.startswith(variant + ":"):
                key = section_key
                break

        if key:
            current = key
            if current not in sections:
                sections[current] = ""
            continue

        if current is None:
            # initialize the first implicit section
            current = "summary"
            sections[current] = ""

        sections[current] += (line + "\n")

    # fallback: if only a single empty section or none, return the whole text as body
    if not sections:
        return {"body": text}

    return sections


def extract_section_keywords(text: str):
    """Return a mapping section_name -> set(keywords) for the provided resume text."""
    sections = parse_sections(text)
    section_keywords = {}
    for name, body in sections.items():
        section_keywords[name] = extract_keywords(body or "")
    return section_keywords


def extract_job_keywords(job_text: str):
    """Extract job-description-driven keywords and mark required vs preferred.

    Simple heuristic: if the job description contains a `requirements` or `qualifications`
    section, treat keywords in that section as `required`, and everything else as `preferred`.
    Otherwise, all extracted keywords are `preferred`.
    """
    sections = parse_sections(job_text)
    required = set()
    preferred = set()

    for name, body in sections.items():
        kws = extract_keywords(body or "")
        if name == "requirements":
            required.update(kws)
        else:
            preferred.update(kws)

    # if no explicit requirements, consider all as preferred
    if not required:
        return {"required": set(), "preferred": preferred}

    # ensure required are not duplicated in preferred
    preferred = preferred - required
    return {"required": required, "preferred": preferred}

STOPWORDS = {
    "the", "and", "with", "for", "a", "an", "to", "of", "in", "on", "is"
}

# Expanded stopwords to filter resume noise; kept conservative to avoid removing meaningful tokens.
STOPWORDS.update({
    "experience", "responsible", "responsible for", "team", "teams", "worked", "work",
    "years", "year", "month", "months", "worked", "including", "using", "used",
    "knowledge", "skills", "skill", "proven", "strong", "demonstrated",
})

# Phrases that are resume fluff and should not be treated as keywords even if they match phrase patterns.
PHRASE_BLACKLIST = {
    "responsible for",
    "team",
    "worked at",
    "experience in",
}

def tokenize(text: str):
    words = text.split()
    return [w for w in words if w not in STOPWORDS]

def extract_keywords(text: str):
    cleaned = clean_text(text)
    expanded = expand_abbreviations(cleaned)

    keywords = set()
    phrases = match_phrases(expanded)
    # Filter out any blacklisted phrases
    phrases = {p for p in phrases if p not in PHRASE_BLACKLIST}
    keywords.update(phrases)

    token_text = expanded
    for phrase in phrases:
        # Remove phrase hits before tokenizing so the same words are not counted twice.
        token_text = re.sub(rf"\b{re.escape(phrase)}\b", " ", token_text)

    tokens = tokenize(token_text)
    keywords.update(tokens)

    # Canonicalize keywords via synonym mapping so different surface forms collapse
    def canonicalize(k: str) -> str:
        low = k.lower().strip()
        if low in SYNONYMS:
            return SYNONYMS[low]
        return low

    # Canonicalize keywords via synonym mapping so different surface forms collapse
    canonical = set()
    for k in keywords:
        c = canonicalize(k)
        # filter short tokens, numeric-only tokens, and stopwords
        if len(c) <= 1:
            continue
        if c.isdigit():
            continue
        if c in STOPWORDS:
            continue
        canonical.add(c)

    return canonical

def compare_keywords(resume_keywords, job_keywords):
    matched = resume_keywords & job_keywords
    missing = job_keywords - resume_keywords

    score = len(matched) / max(len(job_keywords), 1)

    return matched, missing, score

def compute_weighted_alignment(resume_section_kws: dict, job_kws: dict, section_weights: dict | None = None):
    """Compute a weighted alignment score between resume sections and job keywords.

    Returns (matched_set, missing_set, score_float_between_0_and_1)
    """
    # default section importance weights
    default_weights = {
        "skills": 2.0,
        "experience": 1.5,
        "summary": 1.2,
        "projects": 1.1,
        "education": 0.8,
        "certifications": 0.6,
        "body": 1.0,
    }

    if section_weights is None:
        section_weights = default_weights

    required = job_kws.get("required", set())
    preferred = job_kws.get("preferred", set())

    matched = set()
    total_possible = 0.0
    total_matched = 0.0

    # helper to find best evidence weight for a keyword across sections
    def best_section_weight_for(k):
        best = 0.0
        for sec, kws in resume_section_kws.items():
            if k in kws:
                w = section_weights.get(sec, section_weights.get("body", 1.0))
                if w > best:
                    best = w
        return best

    # scoring parameters
    required_multiplier = 3.0
    preferred_multiplier = 1.0
    phrase_bonus = 1.5  # multiply weight when matched keyword is a multi-word phrase

    # Compute totals for required
    max_w = max(section_weights.values())
    for k in required:
        total_possible += (max_w * phrase_bonus if " " in k else max_w) * required_multiplier

        best_w = best_section_weight_for(k)
        if best_w > 0:
            boost = phrase_bonus if " " in k else 1.0
            total_matched += best_w * boost * required_multiplier
            matched.add(k)

    # Compute totals for preferred
    for k in preferred:
        total_possible += (max_w * phrase_bonus if " " in k else max_w) * preferred_multiplier

        best_w = best_section_weight_for(k)
        if best_w > 0:
            boost = phrase_bonus if " " in k else 1.0
            total_matched += best_w * boost * preferred_multiplier
            matched.add(k)

    score = total_matched / max(total_possible, 1.0)

    # missing are job keywords not present in matched
    missing = set(list(required | preferred)) - matched

    return matched, missing, score


def analyze_resume(resume: str, job_description: str, supplemental: str):
    # Section-aware keywords from the resume
    resume_section_kws = extract_section_keywords(resume)

    # Job-driven required/preferred keywords
    job_kws = extract_job_keywords(job_description)

    supplemental_keywords = extract_keywords(supplemental) if supplemental else set()

    matched, missing, score = compute_weighted_alignment(
        resume_section_kws, job_kws
    )

    # counts for diagnostics and frontend display
    resume_keyword_count = sum(len(v) for v in resume_section_kws.values())
    job_keyword_count = len(job_kws.get("required", set()) | job_kws.get("preferred", set()))

    return AnalysisResult(
        matched_skills=list(matched),
        missing_skills=list(missing),
        alignment_score=round(score, 2),
        resume_keyword_count=resume_keyword_count,
        job_keyword_count=job_keyword_count,
        supplemental_keyword_count=len(supplemental_keywords),
        supplemental_used=bool(supplemental_keywords & (job_kws.get("required", set()) | job_kws.get("preferred", set()))),
    )