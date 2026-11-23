#!/usr/bin/env python3
"""Run every collected job description against the reference resume.

This is the demo artefact: it exercises the same code path as ``POST
/analyze``/``/analyze-upload``, prints a summary table, and writes the
per-case evidence JSONs into ``output/``.

    python scripts/demo.py                # all cases
    python scripts/demo.py --case genai_engineer_python
    python scripts/demo.py --verbose       # keep the pipeline's own logging

Note: ``output/`` is git-ignored. Run this script to regenerate it.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import io
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
INPUT_DIR = PROJECT_ROOT / "input"
OUTPUT_DIR = PROJECT_ROOT / "output"

# Allow "python scripts/demo.py" to import the app package from the repo root.
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _load_cases() -> list[dict]:
    cases_path = INPUT_DIR / "job_description_cases.json"
    if not cases_path.exists():
        raise SystemExit(f"Missing fixture file: {cases_path}")
    return json.loads(cases_path.read_text(encoding="utf-8"))["cases"]


def _find_resume() -> Path:
    preferred = INPUT_DIR / "resume.pdf"
    if preferred.exists():
        return preferred
    pdfs = sorted(INPUT_DIR.glob("*.pdf"))
    if not pdfs:
        raise SystemExit(f"No resume PDF found in {INPUT_DIR}")
    return pdfs[0]


def _read_resume_text(resume_path: Path) -> str:
    from fastapi import UploadFile

    from app.services.ingestion import extract_upload_text

    with resume_path.open("rb") as handle:
        upload = UploadFile(filename=resume_path.name, file=handle)
        return asyncio.run(extract_upload_text(upload))


def _run_case(resume_text: str, case: dict, verbose: bool) -> dict:
    from app.routes.analyze import build_response
    from app.services.analysis import write_alignment_evidence

    buffer = io.StringIO()
    if verbose:
        response = build_response(resume_text, case["job_description"], "")
    else:
        with contextlib.redirect_stdout(buffer):
            response = build_response(resume_text, case["job_description"], "")

    analysis = response.analysis
    write_alignment_evidence(
        analysis.alignment_evidence,
        OUTPUT_DIR / f"alignment_evidence_{case['case_id']}.json",
    )

    return {
        "case_id": case["case_id"],
        "title": case.get("title", ""),
        "company": case.get("company", ""),
        "score": analysis.alignment_score,
        "matched": len(analysis.matched_skills),
        "underrepresented": len(analysis.underrepresented_skills),
        "missing": len(analysis.missing_skills),
        "rows": len(analysis.alignment_evidence),
    }


def _print_table(rows: list[dict]) -> None:
    headers = ("case", "score", "matched", "under", "missing", "rows")
    widths = [
        max(len(headers[0]), *(len(row["case_id"]) for row in rows)),
        len(headers[1]),
        len(headers[2]),
        len(headers[3]),
        len(headers[4]),
        len(headers[5]),
    ]

    def line(cells: list[str]) -> str:
        return "  ".join(cell.ljust(width) for cell, width in zip(cells, widths))

    print(line(list(headers)))
    print(line(["-" * width for width in widths]))
    for row in rows:
        print(
            line(
                [
                    row["case_id"],
                    f"{row['score']:.2f}",
                    str(row["matched"]),
                    str(row["underrepresented"]),
                    str(row["missing"]),
                    str(row["rows"]),
                ]
            )
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", help="run a single case by its case_id")
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="keep the pipeline's own console output",
    )
    args = parser.parse_args()

    cases = _load_cases()
    if args.case:
        cases = [case for case in cases if case["case_id"] == args.case]
        if not cases:
            raise SystemExit(f"No case matched {args.case!r}")

    resume_path = _find_resume()
    print(f"Resume: {resume_path.name}")
    print(f"Cases:  {len(cases)}\n")

    resume_text = _read_resume_text(resume_path)
    rows = [_run_case(resume_text, case, args.verbose) for case in cases]

    print()
    _print_table(rows)

    print(f"\nArtefacts written to {OUTPUT_DIR.relative_to(PROJECT_ROOT)}/")
    empty_cases = [row for row in rows if row["rows"] == 0]
    if empty_cases:
        print(
            "Note: zero rows for "
            + ", ".join(row["case_id"] for row in empty_cases)
            + " means the requirement extractor found nothing for that "
            "posting — check the heading map and the fallback harvest."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
