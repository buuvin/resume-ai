# Current Goals — Resume AI

This document captures the **verified** state of the project, what is still broken,
the short-term plan to a demoable MVP, and longer-term goals. It is intended to let
you (or another machine) pick the work up without re-deriving the context.

Read `PROJECT_CONTEXT.md` for the product vision and architectural philosophy.
Read this file for what is true *today*.

---

## Immediate next steps — Phase 2.5, then Phase 3

**Do this next. Phases 0, 1 and 2 are complete and committed.**

Phase 0 (`b014ec8`) unblocked the build. Phase 1 (`1ba0f94`, `68d999e`) fixed the
resume evidence pool. Phase 2 rebuilt the alignment machine: per-source similarity
matrices, NER restored as an evidence source, an emission floor at `0.50`,
cross-source de-duplication, and mean-over-sub-requirements scoring.

### Phase 2.5 — evidence density (decisions locked, not yet executed)

Measured on the **isolated path** (the fixture test injects `expected_requirements`
directly, so extraction is *not* the cause there): slot coverage is only 8–27 % across
the five fixtures (65 qualifying pairs at the 0.50 floor). Causes, ranked:

1. **Floor 0.50 sits above the data.** The bullet channel — the spec's primary matrix —
   tops out at 0.42–0.56 across all five cases; only **2 pairs** in total reach 0.50.
   At 0.40 there are **208** qualifying pairs (bullets 22, keybert 113, ner 73).
   KeyBERT/NER ceilings are 0.715–1.0 — those channels are healthy at 0.50.
2. **Slot inflation under R1:** each requirement decomposes into ~6–10 sub-requirement
   slots, so means land ≈ 0.1 and everything classifies `missing`.
3. Cross-source de-duplication is a minor contributor, not the driver.

**Decisions:**

- Replace `MINIMUM_ALIGNMENT_FLOOR = 0.50` with per-source floors:
  `EMISSION_FLOORS = {"bulletpoints": 0.40, "keybert": 0.50, "ner": 0.50}` in
  `app/services/analysis.py`; placeholder rows stay as they are (added after the floor).
- Re-measure coverage/row counts on all five fixtures and **report the numbers before
  changing any classification threshold** — `MATCHED_ALIGNMENT_THRESHOLD` (0.70) and
  `UNDERREPRESENTED_ALIGNMENT_THRESHOLD` (0.45) stay untouched until reviewed.
- If R1 slot dilution still dominates after the floor fix, bring options back with
  measurements rather than improvising a threshold change.

### Phase 3 — JD requirement extraction (planned)

See the **Phase 3** checklist in the MVP plan below for the full steps. Decisions
locked during planning:

- Extractor returns **both** required and preferred groups with weights (weights are
  stored data; consuming them in scoring is Phase 4); alignment consumes **required
  only**; preferred surfaces as a new optional `AnalysisResult` field; both groups are
  validated against `expected_requirements` / `expected_preferred` ground truth.
- `parse_sections` hardening (bullet-marker lines never headings, whole-line matches
  only) and an extended `HEADING_VARIANTS` map, plus a new
  `app/services/requirements.py` with a fallback harvest derived from memverge's
  ground truth.
- The fixture test's ground-truth injection (`test_alignment_against_job_description_cases`)
  stays untouched — analysis and extraction remain isolated from each other.

### Verification

```bash
python -m pytest
python scripts/demo.py
ruff check .
```

`scripts/demo.py` runs all five fixture job descriptions against the reference resume
and prints the summary table. Expect four rows at `0.00 / 0` until the extractor is
fixed — that is the Phase 3 gap, not a pipeline failure. `data_scientist_altera`
shows a small row count (33 as of Phase 2) with a low score: its extracted
requirements are degree boilerplate that the resume only partially matches.

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

- Branch `main`, tracking `origin/main`. Last commit: `85b7bb0`
  *chore: move goal docs into docs/ and add AGENTS.md*.
- **Phase 0 is complete** (`b014ec8`) — test collection unblocked, `en_core_web_sm`
  pinned into the Docker image, `pyproject.toml` added, whitespace-only diffs stripped.
- **Phase 1 is complete** (`1ba0f94`, `68d999e`) — PDF line-wrap fragments are joined
  back into their parent bullets, headings and `Label: value` subheaders are stripped
  before NER/KeyBERT, and title lines are tagged as a separate `titles` source.
  Verified: 21 bullets, 7 titles, 0 wrap fragments, 0 headings in the evidence pool;
  heading-cited rows dropped 131 → 0.
- **Phase 2 is complete** (`dcfc255`, `6eec2cf`) — per-source similarity matrices, NER
  restored as an evidence source, `MINIMUM_ALIGNMENT_FLOOR = 0.50`, cross-source
  de-duplication within a requirement, and mean-over-sub-requirements scoring.
  Verified: `data_scientist_altera` rows 280 → 33 (3 real citations, the rest
  placeholders), fixture test passes for all five cases with ground-truth
  requirements.
- **41 tests pass** in the conda development environment.
- **The development environment is a conda env, not Docker.** See *Environment setup*.
  The Docker build is reserved for the final MVP (Phase 9).
- The remaining substantive work is **Phase 3** — see *Immediate next steps* at the top
  of this file. The known gaps that Phase 3 closes are listed below.

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
- **Alignment machine** (`alignment_machine`): builds one cosine similarity matrix per
  source and compares the JD side of a source only against the resume side of that
  same source (bullets ↔ bullets, KeyBERT ↔ KeyBERT, NER ↔ NER). Rows below
  `MINIMUM_ALIGNMENT_FLOOR` (0.50) are never emitted, evidence is de-duplicated
  within a requirement across sources, and every sub-requirement without a surviving
  citation gets a placeholder row (`evidence=""`).
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

Four modules, 39 tests, covering the endpoint, upload ingestion, section parsing,
heading/subheader preprocessing, embeddings, KeyBERT wiring, bullet joining, normalisation,
alignment-machine behaviour and a fixture-driven run over all five job descriptions.

> All tests pass as of the Phase 0/1 work (verified in the container: 39 passed).

---

## Known gaps and defects (verified)

These were confirmed by running the pipeline, not inferred from reading the code.

### 1. The product path returns nothing for most real job descriptions — critical

Running `/analyze` against the five fixtures in `input/job_description_cases.json`
with the reference resume:

| Fixture | `alignment_evidence` rows | `alignment_score` |
| --- | --- | --- |
| `genai_engineer_python` | **0** | 0.00 |
| `data_scientist_altera` | 33 | 0.04 |
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

**✅ RESOLVED in Phase 2** (`dcfc255`). `MINIMUM_ALIGNMENT_FLOOR = 0.50` drops rows
below it (separate from the 0.45 classification threshold), and a requirement's score
is now the mean of the best alignment across *all* its sub-requirements, with
uncovered sub-requirements counting as `0.0`. Rows for `data_scientist_altera`
280 → 33; only 3 of those clear the floor as real citations.

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
matches it. Two decisions were resolved during implementation: the emission floor is
`0.50` (higher than the 0.45 classification threshold, as the spec asks), and the
scoring mean runs over *all* sub-requirements with uncovered ones counting as `0.0`
— the explicit "scores `0.0`" case below then holds trivially.

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
      threshold. A row at exactly 0.50 is kept; 0.493 is not.
- [x] De-duplicate evidence within a requirement across sources, on the normalised
      evidence string with a fixed source-priority tie-break.
- [x] Exclude heading-like evidence strings from matching. *Done ahead of Phase 2 via
      `preprocess_for_semantic_extraction` (heading-line removal + `Label: value`
      separation); heading-cited rows dropped 131 → 0. Residual single-word keybert
      phrases from genuine body content (e.g. `keywords`) are left to the evidence
      floor, not source filtering.*
- [x] Apply the scoring rule above (mean over sub-requirements, floor applied).
      Uncovered sub-requirements count as `0.0` via placeholder rows, so the
      denominator is every sub-requirement.
- [x] Strengthen the fixture test: assert requirement coverage, row volume, and that
      no cited evidence is a heading or a wrap fragment. *Now also asserts at least
      one real citation per case (placeholders made the old non-empty check
      vacuous), the per-slot cap, exact coverage in both directions, and
      wrap-fragment heuristics.*

### Phase 3 — Finish the paused JD extraction (~2.5 h)

*Prerequisite: Phase 2.5 (evidence-density fix) — see* Immediate next steps *above.*

- [ ] New `app/services/requirements.py`.
- [ ] Extend the heading map: *what you will do*, *what we are looking for*,
      *key responsibilities*, *minimum qualifications*, *preferred qualifications*,
      *technical skills*, *role overview*, *bonus points*, *nice to have*, *must have*.
- [ ] Fix `parse_sections`: a line beginning with `-`, `•`, `●` or `*` is never a
      heading; heading matches must be whole-line, not prefix.
- [ ] Treat *Minimum Qualifications* / *Preferred Qualifications* as headings.
- [ ] Fallback: harvest requirement-shaped lines when no requirements section exists.
      Derive the heuristic from memverge's ground truth (`ai_engineer_memverge` has no
      recognized heading); gate it behind the precision test so it cannot reintroduce
      junk requirements.
- [ ] Group requirements as `required` vs `preferred`, with weights. *Decision: the
      extractor returns both groups; alignment consumes **required only** (aligning
      preferred too would double slot counts and worsen the R1 dilution); preferred
      surfaces as a new optional `AnalysisResult` field; weights are stored data —
      consuming them in scoring is Phase 4.*
- [ ] Wire the route: required lines feed `compare_bullet_embeddings` through an
      optional `job_bullets` parameter so alignment and the similarity matrix see
      identical strings; drop `job_section_names={"requirements"}` from
      `app/routes/analyze.py`.
- [ ] Validate the extractor directly against `expected_requirements` **and**
      `expected_preferred` in `input/job_description_cases.json` — that file is the
      ground truth. *Measure recall/precision first, then pin thresholds.* The fixture
      test's ground-truth injection stays untouched (analysis/extraction isolation).

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
