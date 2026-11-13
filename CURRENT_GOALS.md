# Current Goals — Resume AI

This document captures the **verified** state of the project, what is still broken,
the short-term plan to a demoable MVP, and longer-term goals. It is intended to let
you (or another machine) pick the work up without re-deriving the context.

Read `PROJECT_CONTEXT.md` for the product vision and architectural philosophy.
Read this file for what is true *today*.

---

## Immediate next steps — Phase 0

**Do this first. Nothing else can be validated until it is done.**

Right now `python -m pytest` aborts during collection, so **no test in the project runs**.
Fixing that is a two-character edit plus one missing image step.

### 1. Fix the test collection blocker

`tests/test_analyze.py:39` has a stray `w` typed after the call, which is a `SyntaxError`
and aborts pytest collection for the whole session:

```python
# current — broken
response = client.post("/analyze", json=payload) w

# fixed
response = client.post("/analyze", json=payload)
```

*Verification:* `python -m pytest` should collect 4 modules instead of erroring out.

### 2. Bake the spaCy model into the container image

`keyphrase-vectorizers` loads `en_core_web_sm`, which is **not** a normal PyPI
dependency. The Dockerfile installs only `requirements.txt`, so a freshly built image
raises on every KeyBERT call (spaCy tries to download the model lazily at request time
and needs network access to do it).

Add to `.devcontainer/Dockerfile`, after the `pip install -r requirements.txt` line:

```dockerfile
# Download the spaCy model required by keyphrase-vectorizers.
# Not available as a regular PyPI dependency.
RUN python -m spacy download en_core_web_sm
```

*Verification:* rebuild the image, then confirm `python -c "import spacy; spacy.load('en_core_web_sm')"`
succeeds inside the container.

### 3. Add a project configuration file

There is no `pyproject.toml` or `pytest.ini`, so `pytest` currently only resolves the
`app` package by accident of how `sys.path` is set up when it is invoked as
`python -m pytest`. Add one so the suite runs the same way regardless of invocation:

```toml
[tool.pytest.ini_options]
pythonpath = ["."]
testpaths = ["tests"]

[tool.ruff]
line-length = 88
target-version = "py310"

[tool.ruff.lint]
select = ["E", "F", "I", "UP"]
```

*Verification:* `pytest` (not `python -m pytest`) works from the repository root.

### 4. Strip the whitespace-only edits

Three files carry trailing-whitespace changes that dilute the diff and make the real
work harder to review:

- `.devcontainer/Dockerfile` — `RUN pip install --upgrade pip  `
- `CURRENT_GOALS.md` — the blank line before *Short-term next tasks*
- `app/services/analysis.py:304` — `sub_requirement=subrequirement,  `

*Verification:* `git diff` shows only meaningful changes.

### 5. Commit a green baseline

```bash
python -m pytest          # expect 24 passed
git add -A && git commit -m "Unblock test collection and pin the spaCy model"
```

**Expected result after this phase:** 24 tests pass, the container can serve a request
end to end without a network call for the model, and the repository has a clean
baseline to build the remaining phases on top of.

> Do not start Phase 1 (resume bullet extraction) until this is green. The bullet
> extraction work changes what every downstream test observes, and it needs a passing
> suite to be judged against.

---

## Where to look

| Area | File |
| --- | --- |
| Analysis engine, alignment machine, scoring | `app/services/analysis.py` |
| Embeddings, KeyBERT, bullet similarity | `app/services/embeddings.py` |
| File ingestion (PDF / DOCX / TXT / MD / RTF) | `app/services/ingestion.py` |
| API routes | `app/routes/analyze.py` |
| App + static serving | `app/main.py` |
| Request/response models | `app/models/schemas.py` |
| Frontend demo | `app/static/index.html`, `app/static/app.js`, `app/static/styles.css` |
| Tests | `tests/test_analyze.py`, `tests/test_embeddings.py`, `tests/test_optimization.py`, `tests/test_section_parsing.py` |
| Job-description fixtures (ground truth) | `input/job_description_cases.json` |
| Reference resume | `input/Bhuvan_Balagar_Resume-1.pdf` |
| Analysis artefacts (git-ignored) | `output/alignment_evidence.json`, `output/resume_evidence.json` |

---

## Current repository status

- Branch `main`, tracking `origin/main`. Last commit: `6e50e01` *metadata updates*.
- **Uncommitted work in the tree** (6 files) is a requirement-decomposition restructure of
  the alignment machine: `decompose_requirements()` splits each requirement into
  KeyBERT sub-phrases + NER entities; `alignment_machine()` embeds those sub-requirements
  and returns up to `max_evidence_per_requirement` (now `10`) evidence rows per
  sub-requirement; `AlignmentEvidence` gained a `sub_requirement` field.
  This work is **incomplete and not yet correct** — see *Known gaps* below.
- `tests/test_analyze.py` contains a **syntax error** (stray `w` after
  `client.post(...)`) that aborts pytest collection, so **no test currently runs**.
- The container image is missing the spaCy model `en_core_web_sm`, which
  `keyphrase-vectorizers` requires. Without it, every KeyBERT call raises.

---

## What is actually implemented

### Service layer

- **FastAPI app** with `CORSMiddleware`, static asset mounting, and a health check.
- **Ingestion** (`app/services/ingestion.py`): extracts text from `.txt`, `.md`, `.rtf`,
  `.pdf` (pdfplumber), `.docx` (python-docx); rejects unsupported extensions with a 400.
- **Embeddings** (`app/services/embeddings.py`): `all-MiniLM-L6-v2` sentence embeddings
  (normalised), line-level `EmbeddedDocument`, KeyBERT keyphrase extraction with MMR
  diversity, and a bullet-to-bullet cosine similarity matrix with top/low matches.
- **Domain entity extraction** (`app/services/analysis.py`): a hand-rolled taxonomy
  (`DOMAIN_ENTITY_TAXONOMY`) covering languages, frameworks, platforms, tools, databases
  and concepts. **This is regex matching, not spaCy NER** — spaCy is only a transitive
  dependency of `keyphrase-vectorizers`.
- **Section parsing** (`parse_sections`): splits a document into `summary`, `skills`,
  `experience`, `projects`, `education`, `certifications`, `requirements`
  (aliases: *requirement*, *qualifications*, *qualification*) and `preferred`.
- **Text normalisation**: Unicode NFKC, lowercasing, punctuation stripping, abbreviation
  expansion (`ml` → *machine learning*, `aws` → *amazon web services*, …), and a small
  synonym canonicalisation map (`SYNONYMS`).
- **Alignment machine** (`alignment_machine`): embeds the requirements and the resume
  evidence for each source, builds a cosine similarity matrix per source, and emits
  `AlignmentEvidence` rows.
- **Scoring** (`_summarize_alignment`): best alignment per requirement →
  `matched` (≥ 0.70), `underrepresented` (0.45–0.70), `missing` (< 0.45);
  `alignment_score` = mean of the per-requirement best alignments.
- **Artefact writing**: `write_alignment_evidence()` groups evidence by requirement into
  `output/alignment_evidence.json`; `write_resume_evidence()` dumps the raw resume
  evidence into `output/resume_evidence.json`.

### API layer

| Endpoint | Method | Body | Status |
| --- | --- | --- | --- |
| `/` | GET | — | serves the static frontend |
| `/health` | GET | — | `{"status": "ok"}` |
| `/analyze` | POST | JSON `AnalyzeRequest` | implemented |
| `/analyze-upload` | POST | multipart form (text and/or files) | implemented |
| `/optimize` | POST | — | **planned** (Phase 4/5) |

`AnalyzeRequest` = `resume_text`, `job_description_text`, optional `supplemental_text`.
`AnalyzeResponse` = `{ analysis: AnalysisResult, improvements: ImprovementResult }`.

### Frontend

Static single-page demo. Accepts pasted text **or** uploaded files for resume, job
description and supplemental context, posts multipart `FormData` to **`/analyze-upload`**,
and renders the response as cards: alignment score, matched / missing / underrepresented
chips, KeyBERT phrases, domain entities, and a stub improvement summary.

### Tests

Four modules, 24 tests, covering the endpoint, upload ingestion, section parsing,
embeddings, KeyBERT wiring, normalisation, alignment-machine behaviour and a
fixture-driven run over all five job descriptions.

> These tests **pass** once (a) the `tests/test_analyze.py` syntax error is fixed and
> (b) `en_core_web_sm` is installed. Both are outstanding Phase 0 items.

---

## Known gaps and defects (verified)

These were confirmed by running the pipeline, not inferred from reading the code.

### 1. The product path returns nothing for most real job descriptions — critical

Running `/analyze` against the five fixtures in `input/job_description_cases.json`
with the reference resume:

| Fixture | `alignment_evidence` rows | `alignment_score` |
| --- | --- | --- |
| `genai_engineer_python` | **0** | 0.00 |
| `data_scientist_altera` | 280 | 0.66 |
| `ai_engineer_memverge` | **0** | 0.00 |
| `machine_learning_engineer_rzr_global` | **0** | 0.00 |
| `ai_data_science_engineer_i` | **0** | 0.00 |

Three compounding causes:

1. **Only one JD section is read.** `app/routes/analyze.py` calls
   `compare_bullet_embeddings(..., job_section_names={"requirements"})`. Real job
   descriptions use *Qualifications*, *Technical Skills*, *Minimum Qualifications*,
   *What We are Looking For*, or no recognised heading at all. `ai_engineer_memverge`
   has no recognised heading, so nothing is extracted even with a broader section set.
2. **Bullets are misclassified as section headings.** `parse_sections` matches a heading
   when the normalised line *starts with* a heading word. Because normalisation strips
   punctuation, the bullet `- Experience with statistical analysis, …` becomes
   `experience with statistical analysis …`, matches the `experience` variant, and
   **terminates the requirements section**. Seven bullets across four fixtures are
   swallowed this way.
3. **`Minimum Qualifications` is treated as a requirement** rather than a heading, and
   therefore appears as a scored requirement in the output.

> The fixture test does not catch this: `test_alignment_against_job_description_cases`
> injects `case["expected_requirements"]` directly, bypassing the extractor entirely.
> That was deliberate — the JD extraction was paused while the analysis core was being
> validated — but it means the extractor is currently untested against ground truth.

### 2. The resume evidence pool is mostly garbage — critical

`extract_bullet_points` returns **46** strings for the reference resume, of which only
**21 are real bullets**. The other **25 are PDF line-wrap fragments** such as
`cleaning, normalization, and feature extraction`, and section headings such as
`skills` and `project experience` are also emitted as content.

Consequences, measured on `ai_engineer_memverge` with correct requirements injected:

- **500 evidence rows for 11 requirements**, using only 50 distinct strings.
- **96 %** of rows sit below the 0.45 alignment threshold.
- **80 %** cite a line-wrap fragment.
- The most-reused "evidence" in the whole run is the heading `project experience`
  (0.51–0.65), and `skills` (0.55–0.69). Only **4 of 11** top-ranked matches are
  genuine resume bullets.

This makes the system unexplainable: it can report that a resume matches
*"Strong programming skills in Python"* citing *"project experience"*.

### 3. No evidence floor, and selection by max-over-many

`alignment_machine` no longer filters out low-similarity candidates, so every
requirement/sub-requirement pair produces a row regardless of relevance. Because the
best score per requirement is a **max over ~56 candidates**, the three-way
classification is close to degenerate: across the five fixtures `matched` is 0–2,
`underrepresented` is 2–9, and `missing` is almost never reached.

### 4. NER was removed as an evidence source but is still specified

The uncommitted work rejects `ner` as a resume-evidence source
(`valid_sources = {"keybert", "bulletpoints"}`), while the design intent recorded in
this file and in `PROJECT_CONTEXT.md` is that NER is a **first-class evidence source
compared within itself**. The removal was a reaction to NER *displacing JD bullet
points as the requirements* — the fix is to keep JD bullets as the requirements and
restore NER as its own evidence channel, not to drop NER.

### 5. NER is not spaCy

`spacy` is in `requirements.txt` but is never imported by the application; it is only
pulled in by `keyphrase-vectorizers`. Entity extraction is regex against
`DOMAIN_ENTITY_TAXONOMY`, so it is limited to the listed terms and will miss
anything outside the taxonomy.

### 6. Smaller items

- `requirements.txt` lists `spacy` but not the `en_core_web_sm` model the code needs.
- `black` and `ruff` are in `requirements.txt`; `ruff` is the one worth keeping.
- `python-dotenv` and `openai` are installed but unused — there is no LLM code yet.
- `pypdf2` is unused (`pdfplumber` handles PDFs).
- `.gitignore` ignores `input/`, but the two fixtures under it are already tracked.
  Any *new* fixture would silently not be committed.
- `output/` is git-ignored, so analysis artefacts are not versioned.

---

## Design spec: the alignment machine

This is the intended design, stated precisely. The current implementation does not yet
match it.

**Inputs**

- `requirements`: the job description's requirement lines. These come from the JD
  *requirements* group (see *Known gaps* #1) and are the unit of analysis. JD bullet
  points are the requirements — they are specific and representative. NER terms are too
  broad and are never allowed to stand in for a requirement.
- `resume_evidence`: a mapping of source → list of original strings, for sources
  `ner`, `keybert`, `bulletpoints`.

**Method**

1. Embed every requirement *and* every piece of resume evidence, keeping the original
   strings alongside their vectors.
2. Build **one cosine-similarity matrix per source**, comparing the JD side of that
   source against the resume side of the same source — i.e. the sources are compared
   *within themselves*:
   - JD bullet points ↔ resume bullet points
   - JD KeyBERT phrases ↔ resume KeyBERT phrases
   - JD NER entities ↔ resume NER entities
3. For each JD requirement, and for each of its decomposed sub-requirements within a
   source, select the strongest matching resume evidence from that source.
4. Emit an `AlignmentEvidence` object per selection.

**Output contract — `AlignmentEvidence`** (`app/models/schemas.py`)

| Field | Type | Meaning |
| --- | --- | --- |
| `source` | `ner` \| `keybert` \| `bulletpoints` | which evidence channel produced this row |
| `requirement` | `str` | the JD requirement this row belongs to |
| `sub_requirement` | `str` | the decomposed part of the requirement that was matched |
| `evidence` | `str` | the original resume string that matched |
| `alignment` | `float` | cosine similarity of the selected match |
| `exact_match` | `bool` | normalised string equality of requirement and evidence |

**Invariants**

- Sources stay distinguishable — a KeyBERT match is never reported as a bullet match.
- Empty sources are handled without raising and without inflating scores.
- Duplicate evidence is de-duplicated **within a requirement, across sources**, so a
  single resume sentence cannot be cited twice and inflate the score.
- Evidence below the minimum alignment threshold is not emitted.
- Scores are deterministic and derived only from the cited evidence.

**Scoring rule (current decision)**

A requirement's score is the **mean of the best alignment across its sub-requirements**,
computed over evidence that passes the floor, with cross-source de-duplication applied
first. If no sub-requirement has qualifying evidence the requirement scores `0.0`.
Thresholds: `MATCHED_ALIGNMENT_THRESHOLD = 0.70`,
`UNDERREPRESENTED_ALIGNMENT_THRESHOLD = 0.45`.

---

## Short-term goals — MVP plan

Ordered by dependency. Phases 0–3 make the pipeline *correct*; 4–6 make it *presentable*.

### Phase 0 — Unblock the build (~30 min)

**Step-by-step instructions, verification commands and the exact edits are in
[Immediate next steps](#immediate-next-steps--phase-0) at the top of this document.
Do that work first; this checklist is the summary.**

- [ ] Fix the `tests/test_analyze.py:39` syntax error so pytest can collect.
- [ ] Add `RUN python -m spacy download en_core_web_sm` to `.devcontainer/Dockerfile`
      so the model is baked into the image rather than downloaded lazily at request time.
- [ ] Add `pyproject.toml` with ruff + pytest configuration and `pythonpath = ["."]`,
      so `pytest` works without depending on `python -m pytest` path behaviour.
- [ ] Strip the whitespace-only edits so the diff shows only meaningful changes.
- [ ] Commit a green baseline.

### Phase 1 — Real resume bullets (~1.5 h)

- [ ] Join PDF line-wrap fragments back into their parent bullet (`●`, `-`, `•` markers).
- [ ] Exclude section headings and sub-labels from the evidence pool.
- [ ] Decide how job-title / company lines are handled (exclude, or tag as a distinct
      source) so they cannot win a match.
- [ ] Target: evidence pool drops from 46 mixed strings to ~21 genuine bullets.

### Phase 2 — Rebuild the alignment machine (~3 h)

- [ ] Implement per-source similarity matrices, compared within themselves.
- [ ] Restore NER as a valid evidence source; remove the test asserting it raises.
- [ ] Restore the minimum alignment floor so irrelevant rows are never emitted.
- [ ] De-duplicate evidence within a requirement across sources.
- [ ] Exclude heading-like evidence strings from matching.
- [ ] Apply the scoring rule above (mean over sub-requirements, floor applied).
- [ ] Strengthen the fixture test: assert requirement coverage, row volume, and that
      no cited evidence is a heading or a wrap fragment.

### Phase 3 — Finish the paused JD extraction (~2.5 h)

- [ ] New `app/services/requirements.py`.
- [ ] Extend the heading map: *what you will do*, *what we are looking for*,
      *key responsibilities*, *minimum qualifications*, *preferred qualifications*,
      *technical skills*, *role overview*, *bonus points*, *nice to have*, *must have*.
- [ ] Fix `parse_sections`: a line beginning with `-`, `•`, `●` or `*` is never a
      heading; heading matches must be whole-line, not prefix.
- [ ] Treat *Minimum Qualifications* / *Preferred Qualifications* as headings.
- [ ] Fallback: harvest requirement-shaped lines when no requirements section exists.
- [ ] Group requirements as `required` vs `preferred`, with weights.
- [ ] Validate the extractor directly against `expected_requirements` in
      `input/job_description_cases.json` — that file is the ground truth.

### Phase 4 — Optimization layer (~3 h)

- [ ] New `app/services/optimization.py` with deterministic, rule-based logic.
- [ ] Produce ranked `ImprovementAction`s: `add_evidence`, `strengthen`, `reword`,
      `remove`, `reinforce`.
- [ ] Prioritise required over preferred; weight by gap severity.
- [ ] Each action carries the requirement, the reason, the cited evidence, and a
      suggested target section.
- [ ] Populate `ImprovementResult.actions`, replacing the current string template.

### Phase 5 — LLM refinement, no API key required (~2 h)

- [ ] New `app/services/refinement.py` with a `RefinementProvider` interface.
- [ ] `OpenAIProvider` — used only when `OPENAI_API_KEY` is set; strict prompt that
      forbids introducing unsupported experience.
- [ ] `LocalGroundedProvider` — the default. Rewrites by promoting requirement terms
      *already present* in the bullet. Adds no facts, so the no-hallucination rule
      holds without any network access.
- [ ] `POST /optimize` endpoint.

### Phase 6 — Frontend (~3 h)

- [ ] Render the alignment evidence: requirement → score bar → cited evidence →
      source badge → exact-match flag.
- [ ] Render the recommended-changes list.
- [ ] Wire an *Optimize* button to `POST /optimize` and show the rewritten bullets.
- [ ] Bump the `app.js` cache-buster.

### Phase 7 — Documentation (~1 h)

- [x] This document — rewritten to match the codebase.
- [x] `PROJECT_CONTEXT.md` — corrected against the implementation.
- [ ] `README.md` — currently states the browser posts JSON to `POST /analyze`, which is
      false: the page posts multipart `FormData` to `/analyze-upload`. Document
      `/analyze`, `/analyze-upload`, `/optimize`, `/health`, supported file formats,
      and the `en_core_web_sm` requirement.

### Phase 8 — Polish (~1 h)

- [ ] CI workflow running ruff + pytest.
- [ ] `scripts/demo.py` — runs all five fixtures and prints a summary table. This is
      the demo artefact.
- [ ] `.gitignore`: stop ignoring the tracked `input/` fixtures.
- [ ] Trim `requirements.txt` (drop `black`, `pypdf2`; keep `spacy` but document the
      model download).

---

## Long-term goals (deliberately deferred)

Not in scope for the MVP. Listed so they are not lost.

- **Learned ranking.** An MLP or ranking model combining deterministic features
  (exact matches, section evidence, KeyBERT presence) with embedding similarities to
  produce the final alignment score.
- **Full LLM refinement.** LLM rewriting of bullets and summary *after* deterministic
  analysis, with explainability and no hallucination.
- **Productionisation.** Secrets management for API keys, performance testing,
  optional FAISS indexing for fast embedding lookups, container hardening.
- **Richer UX.** Sentence-level evidence display, resume export, better file-upload
  flows.
- **Real NER.** Replace the regex taxonomy with a spaCy or transformer NER pass if
  coverage beyond the taxonomy proves necessary.

---

## Conventions and invariants

These hold across every change and are the core of the project's value proposition.

- **Analysis first.** Deterministic analysis before any LLM refinement. The LLM only
  rewrites; it never decides whether something is present.
- **No hallucination.** Never introduce experience, metrics, employers or technologies
  that are not present in the resume or supplemental context.
- **Explainability.** Every score must be traceable to a cited piece of evidence.
  A score without a citation is a bug.
- **Determinism.** The same inputs must produce the same analysis. No hidden model
  behaviour in the scoring path.
- **Tests.** Any change to analysis logic gets a focused test. Keep fixtures small.
- **Documentation.** This file and `PROJECT_CONTEXT.md` are updated in the same commit
  as the code they describe.

---

## Environment setup

The project runs inside the dev container. Dependencies are installed **globally** into
the container image — there is no virtual environment in the container or on the host.

```bash
# Rebuild the container image after changing requirements.txt or the Dockerfile.
# Then, inside the container:
python -m pytest
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Open http://127.0.0.1:8000/ for the UI.

Two setup facts worth remembering:

- `en_core_web_sm` must be installed for KeyBERT to work. It is **not** on PyPI as a
  normal dependency and is downloaded by `python -m spacy download en_core_web_sm`.
  The Dockerfile does this as of Phase 0.
- The first request loads the `all-MiniLM-L6-v2` model and is slow. Subsequent requests
  reuse the cached model (`lru_cache` on `get_embedding_model`).

Environment variables: set `OPENAI_API_KEY` only if you want the OpenAI refinement
provider. The default local provider needs nothing.

---

## Open decisions

1. **Preferred requirements** — score them at a lower weight, or exclude them from the
   score and surface them only in the optimization queue? Each fixture has 6–8
   `expected_preferred` entries, so this materially changes the headline number.
   *Current assumption: lower weight.*
2. **Evidence floor value** — `0.45` is inherited from the old classification
   thresholds. It may want to be a separate, higher constant once resume bullets are
   clean.
3. **Supplemental text** — currently extracted for entities and keyphrases but never
   enters the alignment. Either feed it in as a separate, flagged evidence source, or
   document it as analysis-only context.
4. **Resume evidence sources** — `ner`, `keybert`, `bulletpoints` are the channels.
   Confirm whether job-title/company lines deserve their own source.
