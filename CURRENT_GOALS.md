Current Goals — Resume AI

Overview

This document captures the current state of the project, what has been implemented, short-term next steps, and longer-term goals so you (or another machine) can pick up work consistently.

Where to look

- Analysis engine: app/services/analysis.py
- API + server: app/main.py and app/routes/analyze.py
- Models (request/response shapes): app/models/schemas.py
- Frontend static demo: app/static/index.html, app/static/app.js, app/static/styles.css
- Tests: tests/*.py
- Run instructions: README.md

What is implemented (summary)

- FastAPI backend with POST /analyze and static frontend serving at /.
- Frontend UI that accepts resume text, job description, and supplemental context; posts JSON to /analyze and renders structured results.
- Analysis pipeline (app/services/analysis.py):
  - Text normalization: Unicode NFKC, lowercasing, punctuation cleanup.
  - Abbreviation expansion (e.g., `ml` -> `machine learning`).
  - Phrase detection (COMMON_PHRASES) with multi-word phrase handling.
  - Synonym/alias canonicalization (SYNONYMS map e.g., `etl` -> `data pipeline`).
  - Stopword filtering and PHRASE_BLACKLIST to reduce resume fluff/noise.
  - Section-aware parsing (parse_sections) to detect `skills`, `experience`, `summary`, `projects`, `education`, `requirements`/`preferred` headings.
  - Job-description keyword extraction distinguishing `required` vs `preferred` keywords.
  - Weighted scoring (compute_weighted_alignment) that weights section evidence, gives phrase bonuses, and prioritizes required keywords.
- Tests covering endpoint, phrase/synonym extraction, section parsing, and filters. All tests pass in the dev environment.

Short-term next tasks (prioritized)

1. Prototype alternate keyword extractors (NER, embeddings) to generate candidate phrases from resumes and job descriptions. Use them for candidate generation and ranking.
2. Implement an embeddings fallback (local sentence-transformers or OpenAI embeddings) for semantic matching of unresolved high-priority job keywords to resume sentences. Keep embeddings as a fallback to control cost and preserve explainability.
3. Add server-side file ingestion for PDF and DOCX uploads (pdfplumber, python-docx) and wire file upload support in the frontend so users can upload resumes.
4. Add more diagnostic tests and example fixtures (example resume/job pairs) to evaluate scoring behavior and tune weights.

Long-term goals

- Add an MLP or learned ranking model that combines deterministic features (exact matches, section evidence, keyBERT) with embedding similarities to produce a final alignment score.
- Implement LLM-driven refinement (LLM only for rewriting bullets after deterministic analysis), ensuring explainability and no hallucination.
- Productionize: CI, Docker image, secrets management for API keys, performance testing, and optional indexing (FAISS) for fast embedding lookups.
- UX: richer frontend for uploading files, showing sentence-level evidence for matches, and exporting improved resume content.

Notes for picking this up on another machine

1. Clone the repo and open it.
2. Create and activate a Python virtual environment (recommended path: /app/venv as the repo Dockerfile suggests):

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

3. Run tests:

```bash
python -m pytest
```

4. Run the dev server and open the UI at http://127.0.0.1:8000/:

```bash
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

5. Environment variables: if you later integrate OpenAI or other APIs, set the appropriate keys (e.g., OPENAI_API_KEY) in the environment or .env.

6. Useful quick files to inspect when resuming:
- app/services/analysis.py: main analysis logic and helpers
- app/static/*: frontend demo and wiring
- tests/: automated checks and examples

Implementation notes and conventions

- Keep the analysis-first rule: deterministic analysis before any LLM refinement.
- Prefer explainable, rule-based scoring and only use learnable or embedding-based models as fallbacks or for reranking.
- Add unit tests for any change to analysis logic; keep test fixtures small and focused.

If you'd like, I can now implement one of the short-term tasks in order (TF‑IDF & RAKE prototype, or embeddings fallback, or PDF/DOCX ingestion). Tell me which to start next and I'll add a small plan and tests.