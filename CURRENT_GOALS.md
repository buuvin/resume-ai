Current Goals — Resume AI

Overview

This document captures the current state of the project, what has been implemented, short-term next steps, and longer-term goals so you (or another machine) can pick up work consistently.

Where to look

- Analysis engine: app/services/analysis.py
- Embeddings & keybert: app/services/embeddings.py
- PDF ingestion: app/services/ingestion.py
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
  - Embedding documents that are uploaded through the website, used for keybert for extracting key phrases
  - Entity recognition to categorize keywords into relevant sections for software related fields
- Tests covering endpoint, phrase/synonym extraction, section parsing, and filters. All tests pass in the dev environment.

Short-term next tasks (prioritized)

1. Gap detection to understand where the resume falters compared to the jd, eventually feeds into LLM to better fine tune the resume
2. Develop a structure for utilizing embeddings, keybert keyphrases, and NER entities to determine whether requirements from the job description are met. Current implementation derives keywords to determine whether requirements are met. Next step should be to implement semantic understnading to see how the most relevant resume evidence relates to the requirements through embeddings as well.

Long-term goals:

- Add an MLP or learned ranking model that combines deterministic features (exact matches, section evidence, keyBERT) with embedding similarities to produce a final alignment score.
- Implement LLM-driven refinement (LLM only for rewriting bullets after deterministic analysis), ensuring explainability and no hallucination.
- Reorganize requirements to ensure a holistic deterministic analysis so that all extracted information is consolidated into main ideas that the LLM can digest easier to prevent hallucination and misdirection.
Prompt:
i want to completely rebuild the optimization process.  I already changed the name of the normalization method to alignment machine, but havent rebuilt it yet, and i want to rebuild the opmization process method as well. What I want to do is this:
1. Alignment machine: Embed both keybert and ner keyphrases/entities so i have the original listof strings and a a list of embeddings. Then in the method, a similarity matrix should be created for ner, keybert, and the bullet points, which is the embeddings of the resume ner/keybert/bullet points against the embeddings of the jd ner/keybert/bullet points. and the matrix values should be filled with the cosine similarity of those embeddings, so im comparing the ner/keybert/bullet points of the resume and jd semantically. Then for each of the job description requirements, which is the ner/keybert/bullet points, identify which of the resume ner/keybert/bullet points most matches each one, and create an alignment evidence object, which should have these parameters(source(ner/keybert/bulletpoints), requirement(str), evidence(str), alignment(float), exact_match(bool))  where the requirement is whatever the string is of the ner/keybert/bulletpoint, and the evidence is the most matching one frm the resume, alignment score being the cosine similarity of the most matching evidence from the resume. ner keybert and bullet points should all be contained and compared within themselves. You can build helper methods to avoid repetition, and also add/change the alignment evidence object in schemas.py to work under this alignemnt machine method. the method should take in three things (source(str), evidence(list[str]), requirement(list[str])) where the source specifies whether what is being converted into an aligned object is the ner, keybert or bullet points. the method shoudl return an a list of alignment objects which is specified before. before rebuilding the alignment method, outline what yo uare going to do so i can validate it and specify other requirements to make sure this is executed correctly
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