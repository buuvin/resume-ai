# Resume AI

FastAPI + static frontend for comparing a resume against a job description.

## Setup

Development runs in a conda environment. The Docker image is a final artefact, built
once the MVP is finished — it is not part of the development loop.

```bash
./scripts/setup_env.sh
conda activate resume-ai
```

The bootstrap script creates the env, installs the Python dependencies, and installs
the spaCy model that KeyBERT needs.

> **`en_core_web_sm` is required.** It is not a PyPI dependency and not a conda
> package. Without it every KeyBERT call fails with `OSError [E050]`. If you ever
> rebuild the environment by hand, run:
>
> ```bash
> python -m spacy download en_core_web_sm
> ```

`environment.yml` describes the environment declaratively; `requirements.txt` stays
the single source of truth for Python dependencies.

## Run the app

```bash
python -m uvicorn app.main:app --reload
```

Then open:

```text
http://127.0.0.1:8000/
```

## Tests

```bash
python -m pytest
```

## Demo

```bash
python scripts/demo.py
```

Runs all five collected job descriptions against the reference resume, prints a
summary table, and regenerates the per-case evidence JSONs in `output/`.

## Endpoints

| Endpoint | Method | Body |
| --- | --- | --- |
| `/` | GET | serves the frontend |
| `/health` | GET | `{"status": "ok"}` |
| `/analyze` | POST | JSON `AnalyzeRequest` |
| `/analyze-upload` | POST | multipart form — text and/or files |
| `/optimize` | POST | planned |

`AnalyzeRequest` carries `resume_text`, `job_description_text` and an optional
`supplemental_text`.

## What the page sends

The browser form posts **multipart `FormData`** to `POST /analyze-upload`, with the
text fields `resume_text`, `job_description_text` and `supplemental_text`, plus
optional file parts `resume_file`, `job_description_file` and `supplemental_file`.

Supported file types: `.txt`, `.md`, `.rtf`, `.pdf`, `.docx`.

`POST /analyze` is the programmatic path and takes the same inputs as JSON.

## Project layout

| Path | Purpose |
| --- | --- |
| `app/services/` | ingestion, embeddings, analysis engine |
| `app/routes/` | API routes |
| `app/models/` | request/response schemas |
| `app/static/` | frontend demo (no build step) |
| `tests/` | pytest suite |
| `input/` | job-description fixtures and the reference resume |
| `output/` | generated analysis artefacts (git-ignored) |
| `scripts/` | environment bootstrap and demo runner |

`docs/CURRENT_GOALS.md` tracks the current state and the MVP plan.
`docs/PROJECT_CONTEXT.md` describes the architecture and the design philosophy.
