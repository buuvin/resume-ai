"""Validate the JD requirement extractor against the fixture ground truth.

``input/job_description_cases.json`` is the ground truth: every posting
authored ``expected_requirements`` and ``expected_preferred``. Measured
2026-11-23, the extractor scores recall 1.000 / precision 1.000 for both
groups across all five fixtures. The thresholds below leave a small
margin so a single line of drift passes while any section-level
regression (losing fallback mode, harvesting a responsibility list)
fails loudly.
"""

import json
from pathlib import Path

from app.services.requirements import (
    PREFERRED_WEIGHT,
    REQUIRED_WEIGHT,
    extract_requirements,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CASES_PATH = PROJECT_ROOT / "input" / "job_description_cases.json"

RECALL_THRESHOLD = 0.95
PRECISION_THRESHOLD = 0.90


def _load_cases() -> list[dict]:
    data = json.loads(CASES_PATH.read_text())
    return data["cases"] if isinstance(data, dict) else data


def _normalize(text: str) -> str:
    return " ".join(text.split()).casefold()


def _score(extracted: list[str], expected: list[str]) -> tuple[float, float]:
    got = {_normalize(text) for text in extracted}
    want = {_normalize(text) for text in expected}
    true_positives = len(got & want)
    recall = true_positives / len(want) if want else 1.0
    precision = true_positives / len(got) if got else 1.0
    return recall, precision


def test_required_requirements_match_ground_truth():
    failures = []
    for case in _load_cases():
        extracted = extract_requirements(case["job_description"])
        if not extracted.required:
            failures.append(f"{case['case_id']}: no required requirements")
            continue
        recall, precision = _score(
            [item.text for item in extracted.required],
            case["expected_requirements"],
        )
        if recall < RECALL_THRESHOLD:
            failures.append(
                f"{case['case_id']}: required recall {recall:.3f} "
                f"({len(case['expected_requirements'])} expected)"
            )
        if precision < PRECISION_THRESHOLD:
            failures.append(f"{case['case_id']}: required precision {precision:.3f}")
    assert not failures, "\n".join(failures)


def test_preferred_requirements_match_ground_truth():
    failures = []
    for case in _load_cases():
        expected = case.get("expected_preferred", [])
        if not expected:
            continue
        extracted = extract_requirements(case["job_description"])
        recall, precision = _score(
            [item.text for item in extracted.preferred], expected
        )
        if recall < RECALL_THRESHOLD:
            failures.append(
                f"{case['case_id']}: preferred recall {recall:.3f} "
                f"({len(expected)} expected)"
            )
        if precision < PRECISION_THRESHOLD:
            failures.append(f"{case['case_id']}: preferred precision {precision:.3f}")
    assert not failures, "\n".join(failures)


def test_sections_mode_ignores_unrecognised_sections():
    # altera/genai shape: an explicit required section exists, so
    # responsibilities and benefits bullets are not requirements.
    job_description = (
        "Key Responsibilities\n"
        "- Ship features daily\n"
        "\n"
        "Minimum Qualifications\n"
        "- Proficient in Python\n"
        "\n"
        "What You will Gain\n"
        "- Stock options and growth\n"
    )

    extracted = extract_requirements(job_description)

    assert [item.text for item in extracted.required] == ["Proficient in Python"]
    assert extracted.preferred == []


def test_fallback_mode_harvests_bullets_without_a_required_section():
    # memverge shape: no recognised required heading, so every
    # non-preferred, non-excluded bullet counts.
    job_description = (
        "About the job\n"
        "- Build LLM features for the product\n"
        "- Prototype with RAG pipelines\n"
        "\n"
        "Bonus Points\n"
        "- Experience with LangChain and agents\n"
        "\n"
        "What You will Gain\n"
        "- Stock options and growth\n"
    )

    extracted = extract_requirements(job_description)

    assert [item.text for item in extracted.required] == [
        "Build LLM features for the product",
        "Prototype with RAG pipelines",
    ]
    assert [item.text for item in extracted.preferred] == [
        "Experience with LangChain and agents"
    ]


def test_sections_mode_trusts_plain_content_lines():
    # The /analyze tests post "Requirements\nPython": plain lines inside
    # an explicit required section are requirements of their own.
    extracted = extract_requirements("Requirements\nPython\nSQL experience")

    assert [item.text for item in extracted.required] == [
        "Python",
        "SQL experience",
    ]


def test_extract_requirements_stores_group_weights():
    extracted = extract_requirements(
        "Requirements\n- Build data pipelines for analytics\n"
        "\n"
        "Preferred\n- Experience with Airflow orchestration\n"
    )

    assert [item.weight for item in extracted.required] == [REQUIRED_WEIGHT]
    assert [item.weight for item in extracted.preferred] == [PREFERRED_WEIGHT]
    assert REQUIRED_WEIGHT == 1.0
    assert PREFERRED_WEIGHT == 0.5
