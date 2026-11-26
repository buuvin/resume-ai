# Current Goals — Resume AI

This document captures the **verified** state of the project, what is still broken,
the short-term plan to a demoable MVP, and longer-term goals. It is intended to let
you (or another machine) pick the work up without re-deriving the context.

Read `PROJECT_CONTEXT.md` for the product vision and architectural philosophy.
Read this file for what is true *today*.

---

## Immediate next steps — Phase 4

**Do this next. Phases 0, 1, 2, 2.5 and 3 are complete and committed.**

Phase 0 (`b014ec8`) unblocked the build. Phase 1 (`1ba0f94`, `68d999e`) fixed the
resume evidence pool. Phase 2 rebuilt the alignment machine (per-source similarity
matrices, NER restored, emission floor, cross-source de-duplication,
mean-over-sub-requirements scoring). Phase 2.5 calibrated the floor per source.
Phase 3 landed the job-description requirement extractor — the product path now
produces evidence for **all five fixtures** (previously 4 of 5 returned zero rows).

### Phase 3 — JD requirement extraction — complete (`a73af2c`, `687e8eb`)

- New `app/services/requirements.py` → `extract_requirements(jd)` returns required
  and preferred groups with stored weights (1.0 / 0.5). Sections mode when the
  posting has a recognised required heading; fallback harvest when it does not
  (memverge has none).
- Validated against `input/job_description_cases.json`: **recall 1.000 /
  precision 1.000** for both groups across all five fixtures — pinned in
  `tests/test_requirements.py` at recall ≥ 0.95, precision ≥ 0.90.
- `parse_sections` hardened: bullet-marker lines are never headings, heading
  matches are whole-line only. This was gap #1's cause — prefix matching swallowed
  requirement bullets like "Experience with Git …" and dropped their text.
- Route wiring: required texts feed `compare_bullet_embeddings` through the new
  `job_bullets` parameter, so the similarity matrix and the alignment machine see
  identical strings; preferred surfaces as `AnalysisResult.preferred_requirements`.

| demo case | before Phase 3 | after Phase 3 |
| --- | --- | --- |
| `genai_engineer_python` | 0 rows | 19 rows, 0.23 |
| `data_scientist_altera` | 33 rows, 0.06 | 50 rows, 0.10 |
| `ai_engineer_memverge` | 0 rows | 62 rows, 0.09 |
| `machine_learning_engineer_rzr_global` | 0 rows | 97 rows, 0.24 |
| `ai_data_science_engineer_i` | 0 rows | 86 rows, 0.14 |

### R1 slot dilution — resolved (C3 scoring)

Scores were low (0.09–0.24) because of the Phase 2.5 finding (cause 2): each
requirement decomposes into ~6–10 sub-requirement slots, so the all-slot mean
landed at ≈ 0.1–0.2 and most requirements classified `missing` even with correct
evidence. Decided with measurements in `scripts/score_experiment.py` (arms A/B/
C3/C5/D2/D3 over **20 hand labels**, 10 present / 10 absent, embedded in the
script with reasons):

- **Adopted: C3** — `score = mean(best over covered slots) × coverage^0.3`,
  zero covered slots still `0.0`. Implemented as `COVERAGE_ALPHA = 0.3` in
  `_summarize_alignment` (`app/services/analysis.py`).
- Label accuracy: A 10/20, C5 10/20 (both by classifying almost everything
  `missing` — 9/10 present requirements misclassified), **C3 9/20** with the
  best failure balance (6 present→missing, 5 absent→not-missing), B (α=0) 9/20
  but unusable (9/10 absent requirements leaked, one at `matched` 0.86), D2 7/20,
  D3 8/20. No arm separates present from absent better than ≈55 % on current
  features — C3 is the best of a mediocre field, not a solved problem.
- Demo scores after C3: 0.49 / 0.34 / 0.21 / 0.46 / 0.44 (was 0.23 / 0.10 /
  0.09 / 0.24 / 0.14); matched counts 1/0/1/1/0 (was 0/0/0/0/0).

**Measurement limitation (agreed 2026-11-26):** the calibration set runs
**one resume — a new-grad resume — against all five fixture JDs**. Consequences:
labels reflect what *this* resume can evidence, so "present/absent" judgments
are biased toward new-grad-profile requirements, the absent class is mostly
"senior/production skills a new grad wouldn't have", and the 20 labels are not
a representative sample of real screening decisions. Any of: more resumes
(including a senior one), more JDs, or a re-label pass on a resume with
deliberate gaps, would likely change the winner between A/C3/C5. Re-run
`scripts/score_experiment.py` (edit `LABELS`) before trusting C3 elsewhere.

Two scoring-independent gaps surfaced by the same experiment (no scoring rule
can fix these — follow-ups):

1. **Matcher/decomposition holes:** `memverge[9]` ("Evidence that you build
   things…") and `memverge[7]` ("LLMs, APIs, prompting, embeddings, RAG…") have
   **0/9 covered slots** — every arm scores them `0.00`.
2. **Generic slots create false bests:** an absent cloud requirement scores
   `matched` (0.86) via a generic "machine learning models" slot.

### Phase 2.5 — evidence density — complete (`23ff9a2`, `82acb68`)

Measured on the **isolated path** (the fixture test injects `expected_requirements`
directly, so extraction is *not* the cause there): slot coverage was only 8–27 %
across the five fixtures (65 qualifying pairs at the uniform 0.50 floor). Causes,
ranked:

1. **Floor 0.50 sat above the data.** The bullet channel — the spec's primary matrix —
   tops out at 0.42–0.56 across all five cases; only **2 pairs** in total reached 0.50.
   At 0.40 there are **208** qualifying pairs (bullets 22, keybert 113, ner 73).
   KeyBERT/NER ceilings are 0.715–1.0 — those channels are healthy at 0.50.
2. **Slot inflation under R1:** each requirement decomposes into ~6–10 sub-requirement
   slots, so means land ≈ 0.1 and everything classifies `missing`.
3. Cross-source de-duplication is a minor contributor, not the driver.

**Outcome** — `MINIMUM_ALIGNMENT_FLOOR = 0.50` replaced by
`EMISSION_FLOORS = {"bulletpoints": 0.40, "keybert": 0.50, "ner": 0.50}` in
`app/services/analysis.py`; classification thresholds (0.70 / 0.45) untouched.
Placeholder rows unchanged (added after the floor).

| metric (isolated path, 5 fixtures) | before | after |
| --- | --- | --- |
| slots with evidence | 50 / 286 (17.5 %) | 62 / 286 (21.7 %) |
| per-case coverage | 8–27 % | 10–34 % |
| real citation rows | 70 | 90 (bulletpoints 22, keybert 29, ner 39) |
| demo `data_scientist_altera` | 33 rows, 0.04 | 33 rows, 0.06 |

The 22 bullet rows match the predicted qualifying-pair count at 0.40 exactly (the
channel contributed ≤ 2 rows before). The R1 dilution half of the finding was
resolved later with the C3 rule — see *R1 slot dilution — resolved* above.

### Verification

```bash
python -m pytest
python scripts/demo.py
ruff check .
```

`scripts/demo.py` runs all five fixture job descriptions against the reference resume
and prints the summary table. All five rows are non-zero since Phase 3; scores are
0.21–0.49 under the C3 rule (see *R1 slot dilution — resolved* above), not the
0.09–0.24 of the old all-slot mean.

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
| Environment spec | `environment.yml`, `requirements.txt` |
| Environment bootstrap script | `scripts/setup_env.sh` |
| Demo runner | `scripts/demo.py` |
| Docker build context rules | `.dockerignore` |

---

## Current repository status

- Branch `main`, tracking `origin/main`. Last commit: `687e8eb`
  *test: validate the requirement extractor against fixture ground truth*.
- **Phase 0 is complete** (`b014ec8`) — test collection unblocked, `en_core_web_sm`
  pinned into the Docker image, `pyproject.toml` added, whitespace-only diffs stripped.
- **Phase 1 is complete** (`1ba0f94`, `68d999e`) — PDF line-wrap fragments are joined
  back into their parent bullets, headings and `Label: value` subheaders are stripped
  before NER/KeyBERT, and title lines are tagged as a separate `titles` source.
  Verified: 21 bullets, 7 titles, 0 wrap fragments, 0 headings in the evidence pool;
  heading-cited rows dropped 131 → 0.
- **Phase 2 is complete** (`dcfc255`, `6eec2cf`) — per-source similarity matrices, NER
  restored as an evidence source, an emission floor, cross-source de-duplication
  within a requirement, and mean-over-sub-requirements scoring.
  Verified: `data_scientist_altera` rows 280 → 33 (3 real citations, the rest
  placeholders), fixture test passes for all five cases with ground-truth
  requirements.
- **Phase 2.5 is complete** (`23ff9a2`, `82acb68`) — per-source emission floors
  (`bulletpoints 0.40`, `keybert/ner 0.50`) replace the uniform 0.50. Verified on the
  isolated path: slots with evidence 50 → 62 of 286, real citation rows 70 → 90
  (bulletpoints 0 → 22), per-case coverage 8–27 % → 10–34 %; classification
  thresholds (0.70 / 0.45) deliberately untouched.
- **Phase 3 is complete** (`a73af2c`, `687e8eb`) — new
  `app/services/requirements.py` extracts required and preferred requirement groups
  (sections mode under recognised headings, fallback harvest otherwise); validated
  against fixture ground truth at recall 1.000 / precision 1.000 for both groups;
  `parse_sections` hardened so bullet lines are never headings. Verified: demo 5/5
  non-zero (previously 4 of 5 at zero rows).
- **51 tests pass** in the conda development environment.
- **The development environment is a conda env, not Docker.** See *Environment setup*.
  The Docker build is reserved for the final MVP (Phase 9).
- The remaining substantive work is **Phase 4** — see *Immediate next steps* at the top
  of this file. The R1 slot-dilution decision is **resolved** (C3 scoring); remaining
  open decisions are listed under *Open decisions*.

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
  (aliases: *requirement*, *qualifications*, *qualification*, *minimum qualifications*,
  *must have*) and `preferred` (incl. *preferred qualifications*, *soft skills*,
  *bonus points*). Heading matches are whole-line only and bullet-marker lines are
  never headings.
- **JD requirement extraction** (`app/services/requirements.py`,
  `extract_requirements`): splits a posting into `required` (weight 1.0) and
  `preferred` (weight 0.5) groups. Sections mode when a recognised required heading
  exists (bullets and plain content lines under required/preferred headings count);
  fallback harvest otherwise (every non-preferred, non-excluded bullet). Validated
  against `input/job_description_cases.json`: recall/precision 1.000 for both
  groups across all five fixtures. The route feeds the required texts into
  `compare_bullet_embeddings` via `job_bullets`, and preferred surfaces as
  `AnalysisResult.preferred_requirements` (weights stored for Phase 4).
- **Text normalisation**: Unicode NFKC, lowercasing, punctuation stripping, abbreviation
  expansion (`ml` → *machine learning*, `aws` → *amazon web services*, …), and a small
  synonym canonicalisation map (`SYNONYMS`).
- **Alignment machine** (`alignment_machine`): builds one cosine similarity matrix per
  source and compares the JD side of a source only against the resume side of that
  same source (bullets ↔ bullets, KeyBERT ↔ KeyBERT, NER ↔ NER). Rows below their
  source's `EMISSION_FLOORS` entry (bulletpoints 0.40, keybert/ner 0.50) are never
  emitted, evidence is de-duplicated within a requirement across sources, and every
  sub-requirement without a surviving citation gets a placeholder row (`evidence=""`).
- **Scoring** (`_summarize_alignment`): best alignment per sub-requirement → mean
  across *all* of a requirement's sub-requirements (uncovered ones count as `0.0`) →
  `matched` (≥ 0.70), `underrepresented` (0.45–0.70), `missing` (< 0.45);
  `alignment_score` = mean of the per-requirement scores.
- **Extraction preprocessing** (`preprocess_for_semantic_extraction`): heading lines and
  `Label: value` subheader labels are removed before NER and KeyBERT run, so document
  furniture cannot rank as salient keyphrases.
- **Bullet extraction** (`extract_evidence_lines`): joins PDF line-wrap fragments into
  parent bullets, strips bullet markers, and tags title/company/date lines as a separate
  `titles` evidence source (surfaced in `AnalysisResult.resume_title_lines` and
  `output/resume_evidence.json`, excluded from requirement comparison).
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

Five modules, 51 tests, covering the endpoint, upload ingestion, section parsing,
heading/subheader preprocessing, embeddings, KeyBERT wiring, bullet joining, normalisation,
alignment-machine behaviour, a fixture-driven run over all five job descriptions, and the
requirement extractor's recall/precision against that same fixture's ground truth.

> All 51 tests pass as of the C3 scoring change (verified 2026-11-26).

---

## Known gaps and defects (verified)

These were confirmed by running the pipeline, not inferred from reading the code.

### 1. The product path returns nothing for most real job descriptions — ✅ RESOLVED (Phase 3)

**✅ RESOLVED in Phase 3** (`a73af2c`, `687e8eb`). All three causes are closed:

1. The route now calls `extract_requirements()` — the single source of truth for JD
   requirements — and passes the required texts to `compare_bullet_embeddings` via the
   new `job_bullets` parameter. Sections mode handles recognised headings (*Qualifications*,
   *Minimum Qualifications*, *Technical Skills*, …); a fallback harvest handles postings
   with no recognised required heading (`ai_engineer_memverge`).
2. `parse_sections` no longer prefix-matches headings: a bullet-marker line is never a
   heading and heading matches are whole-line only, so requirement bullets like
   *Experience with statistical analysis, …* survive with their text intact.
3. *Minimum Qualifications* (and *must have*, *preferred qualifications*, *soft skills*,
   *bonus points*) were added to `HEADING_VARIANTS`.

Verified against `input/job_description_cases.json` ground truth: **recall 1.000 /
precision 1.000** for both required and preferred groups across all five fixtures
(pinned in `tests/test_requirements.py` at recall ≥ 0.95, precision ≥ 0.90). Demo after
Phase 3:

| Fixture | `alignment_evidence` rows | `alignment_score` |
| --- | --- | --- |
| `genai_engineer_python` | 19 | 0.23 |
| `data_scientist_altera` | 50 | 0.10 |
| `ai_engineer_memverge` | 62 | 0.09 |
| `machine_learning_engineer_rzr_global` | 97 | 0.24 |
| `ai_data_science_engineer_i` | 86 | 0.14 |

The scores above (0.09–0.24) were produced under the old all-slot mean. The C3
rule (`mean(covered) × coverage^0.3`) replaced it; re-run `scripts/demo.py` for
current numbers (0.21–0.49 at the time of writing). The low scores were an open
decision, not an extraction failure — the decision is now resolved above.

<details>
<summary>Original diagnosis (superseded, kept for context)</summary>

1. **Only one JD section was read.** The route called
   `compare_bullet_embeddings(..., job_section_names={"requirements"})`. Real job
   descriptions use *Qualifications*, *Technical Skills*, *Minimum Qualifications*,
   *What We are Looking For*, or no recognised heading at all. `ai_engineer_memverge`
   had no recognised heading, so nothing was extracted even with a broader section set.
2. **Bullets were misclassified as section headings.** `parse_sections` matched a heading
   when the normalised line *started with* a heading word, so the bullet
   `- Experience with statistical analysis, …` matched the `experience` variant and
   **terminated the requirements section**. Seven bullets across four fixtures were
   swallowed this way.
3. **`Minimum Qualifications` was treated as a requirement** rather than a heading, and
   therefore appeared as a scored requirement in the output.

The fixture test did not catch this: `test_alignment_against_job_description_cases`
injects `case["expected_requirements"]` directly, bypassing the extractor. That
isolation is deliberate and remains (analysis and extraction are validated
independently) — the extractor now has its own ground-truth tests in
`tests/test_requirements.py`.

</details>

### 2. The resume evidence pool is mostly garbage — ✅ RESOLVED (Phase 1)

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

**✅ RESOLVED in Phase 1** (`1ba0f94`, `68d999e`). `extract_evidence_lines()` now joins
PDF line-wrap fragments into their parent bullet and strips bullet markers;
`preprocess_for_semantic_extraction()` removes heading lines and `Label: value`
subheader labels before NER and KeyBERT run; title/company/date lines are tagged as a
separate `titles` source instead of competing as evidence. Verified: 21 bullets, 7 titles,
0 wrap fragments, 0 headings in the pool; heading-cited rows 131 → 0. The *consequences*
above (row volume, degenerate classification) were closed by **Phase 2** — the emission
floor and per-slot cap took `data_scientist_altera` from 280 rows to 33.

### 3. No evidence floor, and selection by max-over-many — resolved

`alignment_machine` no longer filters out low-similarity candidates, so every
requirement/sub-requirement pair produces a row regardless of relevance. Because the
best score per requirement is a **max over ~56 candidates**, the three-way
classification is close to degenerate: across the five fixtures `matched` is 0–2,
`underrepresented` is 2–9, and `missing` is almost never reached.

**✅ RESOLVED in Phase 2** (`dcfc255`). An emission floor drops rows below it
(separate from the 0.45 classification threshold), and a requirement's score is now
the mean of the best alignment across *all* its sub-requirements, with uncovered
sub-requirements counting as `0.0`. Rows for `data_scientist_altera` 280 → 33.
**Calibrated in Phase 2.5** (`23ff9a2`): the floor is per source —
`EMISSION_FLOORS = {"bulletpoints": 0.40, "keybert": 0.50, "ner": 0.50}` — because
the uniform 0.50 sat above the bullet channel's measured range (0.42–0.56); isolated-
path real citations went 70 → 90. The R1 slot-dilution half of this gap (cause 2
above) was **resolved after this phase** with the C3 rule — see *R1 slot dilution
— resolved* at the top of this file.

### 4. NER was removed as an evidence source but is still specified — resolved

`alignment_machine` rejects `ner` as a resume-evidence source
(`valid_sources = {"keybert", "bulletpoints"}`), while the design intent recorded in
this file and in `PROJECT_CONTEXT.md` is that NER is a **first-class evidence source
compared within itself**. The removal was a reaction to NER *displacing JD bullet
points as the requirements* — the fix is to keep JD bullets as the requirements and
restore NER as its own evidence channel, not to drop NER.

**✅ RESOLVED in Phase 2** (`dcfc255`). `ner` is a valid source again, JD bullets stay
the requirements, and `analyze_resume` now passes resume entities as NER evidence. In
the current demo run NER is the strongest channel (two `1.0` citations: `data science`,
`python`).

### 5. NER is not spaCy

`spacy` is in `requirements.txt` but is never imported by the application; it is only
pulled in by `keyphrase-vectorizers`. Entity extraction is regex against
`DOMAIN_ENTITY_TAXONOMY`, so it is limited to the listed terms and will miss
anything outside the taxonomy.

### 6. Smaller items

- `black` and `ruff` are in `requirements.txt`; `ruff` is the one worth keeping.
- `python-dotenv` and `openai` are installed but unused — there is no LLM code yet.
- `pypdf2` is unused (`pdfplumber` handles PDFs).
- `output/` is git-ignored, so analysis artefacts are not versioned. Regenerate them
  with `python scripts/demo.py`.
- ✅ `.gitignore` no longer blanket-ignores `input/`. It now ignores `input/*` with
  explicit negations for the two tracked fixtures, so a *new* fixture is committed by
  adding its own negation line rather than by accident.
- ✅ `.dockerignore` added, so the Phase 9 Docker build cannot pull local environments,
  caches, generated artefacts or `.git/` into the image.


---

## Design spec: the alignment machine

**✅ Implemented in Phase 2** (`dcfc255`). This is the design as stated; the code now
matches it, with one later amendment: the scoring rule was replaced by the C3 rule
(see *R1 slot dilution — resolved* at the top) — `mean(covered) × coverage^0.3`
instead of the all-slot mean. The emission floor decision is unchanged: per-source
`EMISSION_FLOORS` since Phase 2.5 (higher than the 0.45 classification threshold,
as the spec asks).

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

**Scoring rule (current decision — C3)**

A requirement's score is the **mean of the best alignment across its *covered*
sub-requirements (those with cited evidence), multiplied by `coverage^0.3`**
(`COVERAGE_ALPHA = 0.3`), where coverage is the fraction of sub-requirements with
cited evidence. Uncovered (placeholder) slots count only in the coverage
denominator, never as `0.0` in the mean; a requirement with zero covered slots
scores `0.0`. Evidence must pass the source's emission floor, with cross-source
de-duplication applied first. Thresholds: `MATCHED_ALIGNMENT_THRESHOLD = 0.70`,
`UNDERREPRESENTED_ALIGNMENT_THRESHOLD = 0.45`. *Chosen over five arms on 20 hand
labels — measurements and limitations in* R1 slot dilution — resolved.

---

## Short-term goals — MVP plan

Ordered by dependency. Phases 0–3 make the pipeline *correct*; 4–6 make it *presentable*.

### Phase 0 — Unblock the build (~30 min)

**Complete** — committed as `b014ec8`. All 39 tests pass.

- [x] Fix the `tests/test_analyze.py:39` syntax error so pytest can collect.
- [x] Add `RUN python -m spacy download en_core_web_sm` to `.devcontainer/Dockerfile`
      so the model is baked into the image rather than downloaded lazily at request time.
- [x] Add `pyproject.toml` with ruff + pytest configuration and `pythonpath = ["."]`,
      so `pytest` works without depending on `python -m pytest` path behaviour.
- [x] Strip the whitespace-only edits so the diff shows only meaningful changes.
- [x] Commit a green baseline.

### Phase 1 — Real resume bullets (~1.5 h)

- [x] Join PDF line-wrap fragments back into their parent bullet (`●`, `-`, `•` markers).
- [x] Exclude section headings and sub-labels from the evidence pool.
- [x] Decide how job-title / company lines are handled (exclude, or tag as a distinct
      source) so they cannot win a match. *Decision: kept as a tagged `titles` source —
      surfaced in `resume_evidence.json` and `AnalysisResult.resume_title_lines`; not
      used in requirement comparison.*
- [x] Target: evidence pool drops from 46 mixed strings to ~21 genuine bullets.
      *Verified: 21 bullets, 7 titles tagged, 0 wrap fragments, 0 headings in the pool.*

> Verified follow-on for Phase 2: after the subheader-noise fix (heading-line
> removal + `Label: value` separation via `preprocess_for_semantic_extraction`),
> zero alignment rows cite heading strings. The keybert channel can still surface
> single body-content words (e.g. `keywords` from "identify critical skills,
> keywords, ...") — legitimate but thin evidence, which is exactly what the
> emission floor and cross-source de-duplication now handle. *Phase 2 landed:
> `data_scientist_altera` row volume 280 → 33.*

### Phase 2 — Rebuild the alignment machine (~3 h) — complete

**✅ Complete** (`dcfc255`, `6eec2cf`). The design and decisions are recorded under
*Design spec: the alignment machine* above.

- [x] Implement per-source similarity matrices, compared within themselves.
- [x] Restore NER as a valid evidence source; remove the test asserting it raises.
      The test now asserts NER rows are emitted with `source="ner"`.
- [x] Restore the minimum alignment floor so irrelevant rows are never emitted.
      `MINIMUM_ALIGNMENT_FLOOR = 0.50`, separate from the 0.45 classification
      threshold. A row at exactly 0.50 is kept; 0.493 is not. *Superseded in Phase
      2.5 (`23ff9a2`) by per-source `EMISSION_FLOORS` — see* Immediate next steps.
- [x] De-duplicate evidence within a requirement across sources, on the normalised
      evidence string with a fixed source-priority tie-break.
- [x] Exclude heading-like evidence strings from matching. *Done ahead of Phase 2 via
      `preprocess_for_semantic_extraction` (heading-line removal + `Label: value`
      separation); heading-cited rows dropped 131 → 0. Residual single-word keybert
      phrases from genuine body content (e.g. `keywords`) are left to the evidence
      floor, not source filtering.*
- [x] Apply the scoring rule above (mean over sub-requirements, floor applied).
      Uncovered sub-requirements count as `0.0` via placeholder rows, so the
      denominator is every sub-requirement. *Superseded by the C3 rule — covered-
      only mean × `coverage^0.3` — see* R1 slot dilution *at the top.*
- [x] Strengthen the fixture test: assert requirement coverage, row volume, and that
      no cited evidence is a heading or a wrap fragment. *Now also asserts at least
      one real citation per case (placeholders made the old non-empty check
      vacuous), the per-slot cap, exact coverage in both directions, and
      wrap-fragment heuristics.*

### Phase 3 — Finish the paused JD extraction (~2.5 h) — complete (`a73af2c`, `687e8eb`)

*Prerequisite: Phase 2.5 (evidence-density fix) — see* Immediate next steps *above.*

- [x] New `app/services/requirements.py`.
- [x] Extend the heading map: *minimum qualifications*, *must have*,
      *preferred qualifications*, *soft skills*, *bonus points*. *Deliberately not
      added:* responsibility-style headings (*key responsibilities*, *role overview*,
      *what you will do*, *what we are looking for*) — they must stay unclaimed so
      sections mode ignores them and the fallback can harvest them.*
- [x] Fix `parse_sections`: a line beginning with `-`, `•`, `●` or `*` is never a
      heading; heading matches must be whole-line, not prefix.
- [x] Treat *Minimum Qualifications* / *Preferred Qualifications* as headings.
- [x] Fallback: harvest requirement-shaped lines when no requirements section exists.
      Derived from memverge's ground truth; gated behind the precision test so it
      cannot reintroduce junk requirements (precision 1.000 measured).
- [x] Group requirements as `required` vs `preferred`, with weights. *Decision: the
      extractor returns both groups; alignment consumes **required only** (aligning
      preferred too would double slot counts and worsen the R1 dilution); preferred
      surfaces as `AnalysisResult.preferred_requirements`; weights are stored data —
      consuming them in scoring is Phase 4.*
- [x] Wire the route: required lines feed `compare_bullet_embeddings` through the
      optional `job_bullets` parameter so alignment and the similarity matrix see
      identical strings; `job_section_names={"requirements"}` dropped from
      `app/routes/analyze.py`.
- [x] Validate the extractor directly against `expected_requirements` **and**
      `expected_preferred` in `input/job_description_cases.json`. *Measured
      recall/precision 1.000/1.000 for both groups; pinned at recall ≥ 0.95,
      precision ≥ 0.90.* The fixture test's ground-truth injection stays untouched
      (analysis/extraction isolation).

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
- [x] `scripts/demo.py` — runs all five fixtures and prints a summary table. This is
      the demo artefact.
- [x] `.gitignore`: stop ignoring the tracked `input/` fixtures.
- [ ] Trim `requirements.txt` (drop `black`, `pypdf2`; keep `spacy` but document the
      model download).

### Phase 9 — Final Docker build for reproducibility (~1 h)

**The Docker build is reserved for the end of the MVP.** Development happens in the
conda environment; the image exists so the finished project can be reproduced and
shipped by someone else.

- [ ] Decide the layout: keep `.devcontainer/Dockerfile`, or promote it to a root-level
      `Dockerfile` (the conventional shippable form) and retire `devcontainer.json`.
- [ ] Review `.devcontainer/Dockerfile` against the conda-era reality: it still assumes
      a devcontainer workflow and its `CMD` was removed.
- [ ] Add a non-root user and a pinned base image.
- [ ] `docker build` and verify the image starts, serves `/health`, and answers
      `/analyze` with the spaCy model present.
- [ ] Document the build and run commands in `README.md`.

---

## Long-term goals (deliberately deferred)

Not in scope for the MVP. Listed so they are not lost.

- **Learned ranking.** An MLP or ranking model combining deterministic features
  (exact matches, section evidence, KeyBERT presence) with embedding similarities to
  produce the final alignment score.
- **Full LLM refinement.** LLM rewriting of bullets and summary *after* deterministic
  analysis, with explainability and no hallucination.
- **Productionisation.** Secrets management for API keys, performance testing, and
  optional FAISS indexing for fast embedding lookups. *(The Docker image is Phase 9,
  not deferred — see the MVP plan.)*
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
- **Docker is the final artefact, not the development loop.** Day-to-day work happens
  in the conda environment. The image is built once at the end of the MVP so the
  finished project can be reproduced by someone else.

---

## Environment setup

**Development uses a conda environment. Docker is reserved for the final MVP build
(Phase 9).** The environment lives outside the repository, so it never appears in the
working tree.

```bash
# One-time bootstrap — creates the env, installs the deps, installs the spaCy model.
./scripts/setup_env.sh

# Or do it by hand:
conda create -n resume-ai python=3.10
conda activate resume-ai
pip install -r requirements.txt
python -m spacy download en_core_web_sm

# Run
python -m pytest
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Open http://127.0.0.1:8000/ for the UI.

`environment.yml` describes the same environment declaratively. `requirements.txt`
remains the single source of truth for Python dependencies, so the conda environment
and the Docker image can never drift apart.

### The spaCy model — required, and easy to forget

`keyphrase-vectorizers` loads `en_core_web_sm`, which **is not a PyPI dependency and is
not a conda package**. It must be downloaded separately:

```bash
python -m spacy download en_core_web_sm
```

Without it, `spacy.load("en_core_web_sm")` raises `OSError [E050]` and **every KeyBERT
call fails** — the API still responds, but with no keyphrases and degraded evidence.
`environment.yml` cannot carry this step, so `scripts/setup_env.sh` does it for you.
The Dockerfile performs the same download.

Verify it at any time:

```bash
python -c "import spacy; spacy.load('en_core_web_sm'); print('OK')"
```

### Other setup facts

- The first request loads the `all-MiniLM-L6-v2` model and is slow. Subsequent requests
  reuse the cached model (`lru_cache` on `get_embedding_model`).
- Environment variables: set `OPENAI_API_KEY` only if you want the OpenAI refinement
  provider. The default local provider needs nothing.
- `output/` is git-ignored and regenerated by `python scripts/demo.py`.

### Docker (Phase 9 — not the dev loop)

`.devcontainer/Dockerfile` is the image recipe. It is **not** used for day-to-day
development; it is built once the MVP is finished, so the project can be reproduced
and shipped. `.dockerignore` keeps local environments, caches, generated artefacts and
`.git/` out of the build context. See Phase 9 in the MVP plan for the remaining
decisions (root `Dockerfile` vs `.devcontainer/`, non-root user, verification).

---

## Open decisions

1. ~~**R1 slot dilution (blocks Phase 4 design)**~~ — **✅ RESOLVED.** Adopted
   **C3** (`mean(covered) × coverage^0.3`, `COVERAGE_ALPHA = 0.3`) over 20 hand
   labels in `scripts/score_experiment.py`; measurements, limitations (single
   new-grad resume) and the two matcher gaps recorded under *R1 slot dilution —
   resolved* at the top of this file.
2. **Preferred requirements** — score them at a lower weight (extractor stores 0.5), or
   exclude them from the score and surface them only in the optimization queue? Each
   fixture has 1–22 `expected_preferred` entries, so this materially changes the
   headline number. *Current assumption: lower weight; consumption is Phase 4.*
   **✅ extraction half resolved in Phase 3** — both groups are extracted and validated.
3. **Supplemental text** — currently extracted for entities and keyphrases but never
   enters the alignment. Either feed it in as a separate, flagged evidence source, or
   document it as analysis-only context.
4. **Resume evidence sources** — `ner`, `keybert`, `bulletpoints` are the channels.
   Confirm whether job-title/company lines deserve their own source.

**Resolved:** evidence-floor value — the single `0.45` constant was replaced by
per-source `EMISSION_FLOORS` (`bulletpoints 0.40`, `keybert/ner 0.50`) in Phase 2.5.
