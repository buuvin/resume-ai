# Resume AI

Basic FastAPI + static frontend setup for comparing a resume against a job description.

## Run the app

```bash
python -m uvicorn app.main:app --reload
```

Then open:

```text
http://127.0.0.1:8000/
```

## What the page sends

The browser form posts JSON to `POST /analyze` with:

- `resume_text`
- `job_description_text`
- `supplemental_text`
