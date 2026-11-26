#!/usr/bin/env python3
"""Compare candidate scoring rules for the R1 slot-dilution decision.

Each arm scores the same alignment evidence differently:

    A  current rule           mean over all slots (uncovered = 0.0)
    B  covered-only mean      uncovered slots are ignored            (alpha = 0)
    C  alpha = 0.3 / 0.5      mean(covered) * coverage^alpha
    D  top-k mean (k = 2, 3)  mean of the k best slot scores

Evidence comes from the isolated path (ground-truth requirements injected),
matching ``tests/test_optimization.py::test_alignment_against_job_description_cases``.

The hand labels below are the calibration set: a ``present`` requirement must
not classify ``missing`` and an ``absent`` requirement must classify
``missing``. Edit LABELS directly to disagree with a judgment.

    conda run -n resume-ai python scripts/score_experiment.py
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.models.schemas import AlignmentEvidence  # noqa: E402

# Hand labels: does the reference resume contain qualifying evidence?
# "index" is the position in the fixture's expected_requirements list.
LABELS: list[dict] = [
    # --- present ---
    {
        "case_id": "genai_engineer_python",
        "index": 1,
        "label": "present",
        "reason": "Python, Pandas, NumPy and PyTorch are all listed in SKILLS",
    },
    {
        "case_id": "genai_engineer_python",
        "index": 2,
        "label": "present",
        "reason": "coursework 'Data Structures & Algorithms' + tutoring bullet",
    },
    {
        "case_id": "data_scientist_altera",
        "index": 3,
        "label": "present",
        "reason": "statistical analysis, EDA, ML, Tableau across many bullets",
    },
    {
        "case_id": "ai_engineer_memverge",
        "index": 9,
        "label": "present",
        "reason": "research role and three project bullets are direct evidence",
    },
    {
        "case_id": "machine_learning_engineer_rzr_global",
        "index": 3,
        "label": "present",
        "reason": "'end-to-end ML pipelines' + 'exploratory data pipelines' bullets",
    },
    # --- absent ---
    {
        "case_id": "machine_learning_engineer_rzr_global",
        "index": 0,
        "label": "absent",
        "reason": "no programmatic-advertising domain (bid landscapes, fraud)",
    },
    {
        "case_id": "machine_learning_engineer_rzr_global",
        "index": 1,
        "label": "absent",
        "reason": "collaboration exists, but no model-to-production integration",
    },
    {
        "case_id": "ai_data_science_engineer_i",
        "index": 1,
        "label": "absent",
        "reason": "no cloud deployment (AWS/Azure/GCP), APIs or model serving",
    },
    {
        "case_id": "ai_data_science_engineer_i",
        "index": 6,
        "label": "absent",
        "reason": "no schema design, data governance or cloud architecture",
    },
    {
        "case_id": "ai_engineer_memverge",
        "index": 3,
        "label": "absent",
        "reason": "no production-feature delivery evidence in the resume",
    },
    # --- batch 2: extend to 20 labels before deciding (plan tie-break rule) ---
    # present
    {
        "case_id": "data_scientist_altera",
        "index": 1,
        "label": "present",
        "reason": "research role + projects + tutoring span well over a year",
    },
    {
        "case_id": "ai_engineer_memverge",
        "index": 7,
        "label": "present",
        "reason": "LLM eval contract + embeddings project satisfy the any-of list",
    },
    {
        "case_id": "machine_learning_engineer_rzr_global",
        "index": 10,
        "label": "present",
        "reason": "hypothesis testing, statistics, model evaluation in skills",
    },
    {
        "case_id": "ai_data_science_engineer_i",
        "index": 4,
        "label": "present",
        "reason": "Copilot is listed in SKILLS (Windsurf/Cursor absent but any-of)",
    },
    {
        "case_id": "genai_engineer_python",
        "index": 0,
        "label": "present",
        "reason": "BS in Data Science is a related field",
    },
    # absent (judgment calls — adjust if you disagree)
    {
        "case_id": "machine_learning_engineer_rzr_global",
        "index": 5,
        "label": "absent",
        "reason": "no experiment documentation or reproducibility evidence",
    },
    {
        "case_id": "machine_learning_engineer_rzr_global",
        "index": 2,
        "label": "absent",
        "reason": "analyzes features for business decisions, not model impact",
    },
    {
        "case_id": "machine_learning_engineer_rzr_global",
        "index": 4,
        "label": "absent",
        "reason": "tested model architectures, not new ML tools/methodologies",
    },
    {
        "case_id": "ai_data_science_engineer_i",
        "index": 0,
        "label": "absent",
        "reason": "pipelines/insights present but no deployment of AI applications",
    },
    {
        "case_id": "ai_engineer_memverge",
        "index": 4,
        "label": "absent",
        "reason": "no collaboration with professional engineers; student orgs only",
    },
]

ARMS = ("A", "B", "C3", "C5", "D2", "D3")
ARM_LABELS = {
    "A": "current (all-slot mean)",
    "B": "covered-only mean (a=0)",
    "C3": "covered mean * cov^0.3",
    "C5": "covered mean * cov^0.5",
    "D2": "top-2 mean",
    "D3": "top-3 mean",
}

MATCHED_ALIGNMENT_THRESHOLD = 0.70
UNDERREPRESENTED_ALIGNMENT_THRESHOLD = 0.45


def _load_cases() -> list[dict]:
    import json

    path = PROJECT_ROOT / "input" / "job_description_cases.json"
    return json.loads(path.read_text(encoding="utf-8"))["cases"]


def _read_resume_text() -> str:
    import asyncio

    from fastapi import UploadFile

    from app.services.ingestion import extract_upload_text

    resume_path = PROJECT_ROOT / "input" / "Bhuvan_Balagar_Resume-1.pdf"
    with resume_path.open("rb") as handle:
        upload = UploadFile(filename=resume_path.name, file=handle)
        return asyncio.run(extract_upload_text(upload))


def _build_resume_evidence(resume_text: str) -> dict[str, list[str]]:
    from app.services.analysis import (
        _flatten_entities,
        extract_domain_entities,
        preprocess_for_semantic_extraction,
    )
    from app.services.embeddings import (
        embed_document,
        extract_evidence_lines,
        extract_keyphrases,
    )

    extraction_text = preprocess_for_semantic_extraction(resume_text)
    embedded = embed_document(extraction_text)
    keyphrases = extract_keyphrases(extraction_text, embedded_document=embedded)
    entities = _flatten_entities(extract_domain_entities(extraction_text))
    bullets = extract_evidence_lines(resume_text, {"experience", "projects"})[
        "bulletpoints"
    ]
    return {"ner": entities, "keybert": keyphrases, "bulletpoints": bullets}


def _slot_bests(
    evidence: list[AlignmentEvidence],
) -> dict[str, dict[str, float]]:
    """{requirement: {sub_requirement: best alignment}} (placeholders = 0.0)."""
    bests: dict[str, dict[str, float]] = {}
    for item in evidence:
        slots = bests.setdefault(item.requirement, {})
        slots[item.sub_requirement] = max(
            slots.get(item.sub_requirement, 0.0), item.alignment
        )
    return bests


def _has_citation(evidence: list[AlignmentEvidence]) -> set[tuple[str, str]]:
    return {
        (item.requirement, item.sub_requirement)
        for item in evidence
        if item.evidence.strip()
    }


def _score_arm(
    arm: str,
    requirement: str,
    slot_scores: dict[str, float],
    cited: set[tuple[str, str]],
) -> float:
    all_bests = sorted(slot_scores.values(), reverse=True)
    covered = [
        score for slot, score in slot_scores.items() if (requirement, slot) in cited
    ]
    if not covered:
        return 0.0
    coverage = len(covered) / len(all_bests)
    covered_mean = sum(covered) / len(covered)
    if arm == "A":
        return sum(all_bests) / len(all_bests)
    if arm == "B":
        return covered_mean
    if arm == "C3":
        return covered_mean * coverage**0.3
    if arm == "C5":
        return covered_mean * coverage**0.5
    if arm == "D2":
        return sum(all_bests[:2]) / min(2, len(all_bests))
    if arm == "D3":
        return sum(all_bests[:3]) / min(3, len(all_bests))
    raise ValueError(f"unknown arm {arm}")


def _classify(score: float) -> str:
    if score >= MATCHED_ALIGNMENT_THRESHOLD:
        return "matched"
    if score >= UNDERREPRESENTED_ALIGNMENT_THRESHOLD:
        return "under"
    return "missing"


def main() -> int:
    from app.services.analysis import (
        _summarize_alignment,
        alignment_machine,
        decompose_requirements,
    )

    cases = _load_cases()
    resume_text = _read_resume_text()
    resume_evidence = _build_resume_evidence(resume_text)

    # (case_id, requirement) -> arm -> score
    scores: dict[tuple[str, str], dict[str, float]] = {}
    # (case_id, requirement) -> slot stats for the detail table
    slot_stats: dict[tuple[str, str], tuple[int, int]] = {}
    arm_a_scores: dict[tuple[str, str], float] = {}
    population: dict[str, dict[str, int]] = {arm: {} for arm in ARMS}
    baseline_scores: dict[str, float] = {}

    for case in cases:
        evidence = alignment_machine(
            resume_evidence,
            case["expected_requirements"],
            requirement_subrequirements=decompose_requirements(
                case["expected_requirements"]
            ),
        )
        # Arm A must reproduce the production rule exactly.
        baseline_scores[case["case_id"]] = _summarize_alignment(evidence)[3]

        bests = _slot_bests(evidence)
        cited = _has_citation(evidence)
        for requirement, slot_scores in bests.items():
            key = (case["case_id"], requirement)
            covered = sum(1 for slot in slot_scores if (requirement, slot) in cited)
            slot_stats[key] = (len(slot_scores), covered)
            for arm in ARMS:
                score = _score_arm(arm, requirement, slot_scores, cited)
                scores.setdefault(key, {})[arm] = score
                if arm == "A":
                    arm_a_scores[key] = score
                population[arm][_classify(score)] = (
                    population[arm].get(_classify(score), 0) + 1
                )

    # ---- Sanity: arm A's overall mean matches production scoring ------
    print("== Sanity check: arm A vs _summarize_alignment ==")
    for case in cases:
        req_scores = [
            scores[(cid, req)]["A"]
            for cid, req in arm_a_scores
            if cid == case["case_id"]
        ]
        arm_a_mean = round(sum(req_scores) / len(req_scores), 2)
        status = (
            "OK"
            if abs(arm_a_mean - baseline_scores[case["case_id"]]) <= 0.011
            else "MISMATCH"
        )
        case_id = case["case_id"]
        print(
            f"  {case_id:40s} armA={arm_a_mean:.2f}  "
            f"prod={baseline_scores[case_id]:.2f}  {status}"
        )

    # ---- Label accuracy ----------------------------------------------
    cases_by_id = {case["case_id"]: case for case in cases}
    print("\n== Label accuracy ==")
    header = (
        f"{'arm':6s} {'correct':>9s} {'present->missing':>18s} "
        f"{'absent->not missing':>21s}"
    )
    print(header)
    print("-" * len(header))
    for arm in ARMS:
        correct = present_fail = absent_fail = 0
        for entry in LABELS:
            requirement = cases_by_id[entry["case_id"]]["expected_requirements"][
                entry["index"]
            ]
            classification = _classify(scores[(entry["case_id"], requirement)][arm])
            ok = (
                classification != "missing"
                if entry["label"] == "present"
                else classification == "missing"
            )
            correct += ok
            if entry["label"] == "present" and classification == "missing":
                present_fail += 1
            if entry["label"] == "absent" and classification != "missing":
                absent_fail += 1
        print(
            f"{arm:6s} {correct}/{len(LABELS):<7d} "
            f"{present_fail:>18d} {absent_fail:>21d}"
        )

    # ---- Per-label detail --------------------------------------------
    print("\n== Per-label detail (score / classification per arm) ==")
    for entry in LABELS:
        requirement = cases_by_id[entry["case_id"]]["expected_requirements"][
            entry["index"]
        ]
        slots, covered = slot_stats[(entry["case_id"], requirement)]
        cells = "  ".join(
            f"{arm}:{scores[(entry['case_id'], requirement)][arm]:.2f}"
            f"/{_classify(scores[(entry['case_id'], requirement)][arm])[:4]}"
            for arm in ARMS
        )
        snippet = requirement if len(requirement) <= 58 else requirement[:55] + "..."
        print(
            f"  [{entry['label']:7s}] cov={covered}/{slots} "
            f"{entry['case_id']} :: {snippet}"
        )
        print(f"           {cells}")

    # ---- Population stats --------------------------------------------
    print("\n== Classification counts across all requirements (5 fixtures) ==")
    header = f"{'arm':6s} {'matched':>8s} {'under':>7s} {'missing':>8s}"
    print(header)
    print("-" * len(header))
    for arm in ARMS:
        counts = population[arm]
        print(
            f"{arm:6s} {counts.get('matched', 0):>8d} "
            f"{counts.get('under', 0):>7d} {counts.get('missing', 0):>8d}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
