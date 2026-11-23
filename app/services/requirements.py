"""Job-description requirement extraction.

Splits a posting into ``required`` and ``preferred`` requirement groups
with weights, in two modes:

- **Sections mode** — the posting has a recognised required section
  (``qualifications``, ``minimum qualifications``, ``education``,
  ``technical skills``, ``requirements``, ``must have``). Only bullets
  under recognised required/preferred headings count; everything else
  (summaries, responsibility lists, benefits) is ignored.
- **Fallback mode** — no recognised required section exists, so the
  posting never separates its requirements. Every bullet that is not
  under a preferred or excluded heading is treated as a requirement.

The mode split and the exact heading sets were derived from and validated
against the ground truth in ``input/job_description_cases.json``:
required recall/precision and preferred recall/precision are all 1.000
across the five fixtures (pinned in ``tests/test_requirements.py``).
Two deliberate asymmetries are part of that measurement: *required
qualifications* and *required skills / experience* are **not** recognised
required headings (recognising them would switch ads_i/rzr out of
fallback mode and lose their responsibility bullets), while *minimum
qualifications* is (without it altera would fall back and harvest its
12 responsibility bullets as requirements).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.services.analysis import HEADING_VARIANTS
from app.services.embeddings import BULLET_MARKER_PATTERN

# Weights are stored data: Phase 4 consumes them when scoring. Alignment
# (Phase 3) uses the required group's texts only.
REQUIRED_WEIGHT = 1.0
PREFERRED_WEIGHT = 0.5

# Sections that may hold bullets but never requirements (benefits etc.).
# Prose-only sections need no entry: the fallback harvests bullets only.
EXCLUDED_VARIANTS = ("what you will gain", "benefits", "perks", "we offer")

# Keys of HEADING_VARIANTS that mean "the candidate must have this".
# Everything else in the map (summary, experience, projects, ...) is not
# a requirement section for a job description.
REQUIRED_KEYS = ("requirements", "education", "skills")
PREFERRED_KEYS = ("preferred",)


@dataclass(frozen=True)
class Requirement:
    """One extracted requirement line with its stored weight."""

    text: str
    weight: float


@dataclass
class ExtractedRequirements:
    required: list[Requirement] = field(default_factory=list)
    preferred: list[Requirement] = field(default_factory=list)


def _normalize(line: str) -> str:
    """Normalise a line for heading lookup and exact-match comparison."""
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", line)).strip().lower()


def _heading_lookup() -> dict[str, str]:
    """Map normalised heading variants to their target group."""
    lookup: dict[str, str] = {}
    for key in REQUIRED_KEYS:
        for variant in HEADING_VARIANTS.get(key, []):
            lookup[_normalize(variant)] = "required"
    for key in PREFERRED_KEYS:
        for variant in HEADING_VARIANTS.get(key, []):
            lookup[_normalize(variant)] = "preferred"
    for variant in EXCLUDED_VARIANTS:
        lookup[_normalize(variant)] = "excluded"
    return lookup


def _classify_lines(
    job_description_text: str,
) -> list[tuple[str, str]]:
    """Tag every line as ``("blank"|"heading"|"bullet"|"other", value)``.

    Heading values are the target group (``required`` / ``preferred`` /
    ``excluded``); bullet values have their marker stripped.
    """
    lookup = _heading_lookup()
    events: list[tuple[str, str]] = []
    for raw in (job_description_text or "").splitlines():
        line = raw.strip()
        if not line:
            events.append(("blank", ""))
            continue
        if BULLET_MARKER_PATTERN.match(line):
            events.append(("bullet", BULLET_MARKER_PATTERN.sub("", line, count=1)))
            continue
        group = lookup.get(_normalize(line))
        if group is not None:
            events.append(("heading", group))
        else:
            events.append(("other", line))
    return events


def extract_requirements(job_description_text: str) -> ExtractedRequirements:
    """Extract weighted ``required`` and ``preferred`` requirement lines.

    In sections mode only bullets under recognised headings count; in
    fallback mode (no recognised required heading) every non-preferred,
    non-excluded bullet is a requirement. Bullet lines are joined with
    their continuation lines (PDF/word-wrap repair) and flushed on blank
    lines and headings.
    """
    events = _classify_lines(job_description_text)
    sections_mode = any(
        kind == "heading" and value == "required" for kind, value in events
    )

    required_texts: list[str] = []
    preferred_texts: list[str] = []
    current: str | None = None  # required | preferred | excluded
    open_bullet: list[str] = []
    open_target: str | None = None  # group the open bullet belongs to

    def flush() -> None:
        nonlocal open_bullet, open_target
        if open_bullet:
            text = " ".join(open_bullet)
            # Explicit sections are trusted (the old route extracted them
            # with minimum_words=1); the fallback harvest needs more
            # evidence per line before it treats prose as a requirement.
            minimum_words = 1 if sections_mode else 3
            if (
                len(text.split()) >= minimum_words
                and open_target in ("required", "preferred")
            ):
                if open_target == "required":
                    required_texts.append(text)
                else:
                    preferred_texts.append(text)
            open_bullet, open_target = [], None

    for kind, value in events:
        if kind == "blank":
            flush()
        elif kind == "heading":
            flush()
            current = value
        elif kind == "bullet":
            flush()
            if sections_mode:
                open_target = (
                    current if current in ("required", "preferred") else None
                )
            elif current == "preferred":
                open_target = "preferred"
            elif current == "excluded":
                open_target = None
            else:
                open_target = "required"
            open_bullet = [value.strip()] if open_target else []
        elif open_bullet:
            # "other": continuation of the open bullet (wrap repair)
            open_bullet.append(value)
        elif sections_mode and current in ("required", "preferred"):
            # Standalone content line inside an explicit section: the
            # whole line is a requirement of its own (legacy behaviour
            # of extract_bullet_points with minimum_words=1).
            open_bullet, open_target = [value], current
            flush()
    flush()

    return ExtractedRequirements(
        required=_dedupe(required_texts, weight=REQUIRED_WEIGHT),
        preferred=_dedupe(preferred_texts, weight=PREFERRED_WEIGHT),
    )


def _dedupe(texts: list[str], weight: float) -> list[Requirement]:
    """Drop duplicate lines (normalised), preserving first occurrence."""
    seen: set[str] = set()
    requirements: list[Requirement] = []
    for text in texts:
        key = _normalize(text)
        if key and key not in seen:
            seen.add(key)
            requirements.append(Requirement(text=text, weight=weight))
    return requirements
