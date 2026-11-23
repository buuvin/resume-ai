# Resume AI — Intelligent Resume Optimization System

> **How to read this document.** Sections 1–3 define the product and its philosophy and
> are the stable frame for every decision. Sections 4–6 describe the architecture and
> are annotated with the **current implementation status**. Sections 7–11 cover the
> environment, goals, non-goals and working conventions.
>
> For the verified day-to-day state, the known defects, and the ordered MVP plan, see
> `CURRENT_GOALS.md`. The two documents are kept in sync.

---

## 1. Project Overview

Resume AI is an end-to-end system designed to analyze, optimize and refine resumes for
specific job roles.

**Inputs**

- Resume (PDF or DOCX, or plain text)
- Job Description (text or file)
- Optional Supplemental Experience Document (text containing additional background)

**Outputs**

- Structured analysis of resume vs job alignment
- Identification of strengths, gaps, and opportunities
- Suggested resume improvements
- LLM-assisted rewritten bullets and summary
- Structured JSON output for frontend integration

---

## 2. Core Philosophy

This system follows an **analysis-first** architecture.

**Key Principles**

- Structured reasoning before generation
- No hallucination or fabrication of experience
- Controlled and explainable outputs
- LLMs are used only for refinement, not reasoning

**System Rule**

> The system must perform all reasoning using structured logic before invoking the LLM.

The practical test for this rule: every number the system reports must be traceable to
a specific piece of text that was actually present in the input. A score that cannot be
cited is a bug.

---

## 3. High-Level Architecture

```
Input
  → Parsing / Ingestion
  → Structured Analysis  (deterministic: entities, keyphrases, bullets, embeddings)
  → Alignment Machine    (source-specific cosine similarity → cited evidence)
  → Optimization Logic   (deterministic: ranked, actionable changes)
  → LLM Refinement       (rewrite only; never decides what is present)
  → Output
```

The alignment machine is the boundary between deterministic analysis and everything
downstream of it. It is the component that must be trustworthy, because both the
optimization logic and the LLM consume its output.

---

## 4. System Components

### 4.1 Ingestion Layer

**Responsibilities**

Extract clean text from:

- PDF resumes (pdfplumber)
- DOCX resumes (python-docx)
- Job descriptions
- Supplemental documents

**Output**

```json
{
  "resume_text": "...",
  "job_description_text": "...",
  "supplemental_text": "..."
}
```

> **Current status: implemented.** `app/services/ingestion.py` supports `.txt`, `.md`,
> `.rtf`, `.pdf` and `.docx`; unsupported extensions return HTTP 400. Plain-text
> pastes are the primary path — file upload is an alternative, not a requirement.
>
> **PDF line breaks are now repaired.** Text extracted from PDFs preserves the source
> line breaks, so a bullet that wraps across three printed lines used to arrive as
> three separate lines and be treated as three separate pieces of evidence.
> `extract_evidence_lines()` now joins wrapped fragments back into their parent bullet
> and strips the bullet marker. Title, company and date lines are recognised and
> tagged as a distinct `titles` source rather than competing as evidence.

---

### 4.2 Structured Analysis Engine (Core System)

This is the primary intelligence layer.

**Responsibilities**

Extract:

- Skills
- Tools
- Keywords
- Role signals

Compare the resume against the job description and identify:

- Matching skills
- Missing skills
- Underrepresented experience
- Low-value or redundant content

**Output**

```json
{
  "matched_skills": [],
  "underrepresented_skills": [],
  "missing_skills": [],
  "alignment_score": 0.0,
  "resume_keyphrases": [],
  "job_description_keyphrases": [],
  "supplemental_entities": {},
  "alignment_evidence": [
    {
      "source": "bulletpoints",
      "requirement": "",
      "sub_requirement": "",
      "evidence": "",
      "alignment": 0.0,
      "exact_match": false
    }
  ]
}
```

> **Current status: implemented, with known defects.** See `CURRENT_GOALS.md` →
> *Known gaps and defects* for the verified list. In summary:
>
> - **Closed.** The resume evidence pool is clean. PDF line-wrap fragments are joined
>   into their parent bullets, headings and `Label: value` subheaders are stripped
>   before NER and KeyBERT run, and title lines are tagged as their own source.
>   Verified: 21 bullets, 7 titles, 0 wrap fragments, 0 headings; heading-cited
>   evidence rows dropped 131 → 0.
> - **Open.** The job-description requirement extractor only recognises one section
>   heading, so four of the five fixture postings yield no requirements at all.
> - **Resolved (Phase 2, `dcfc255`).** The alignment machine now has an emission
>   floor (`MINIMUM_ALIGNMENT_FLOOR = 0.50`, deliberately separate from the 0.45
>   classification threshold) and scores each requirement as the mean of the best
>   alignment across *all* its sub-requirements instead of max-over-many, so the
>   matched / underrepresented / missing split reflects real coverage.
>
> **Entity extraction is regex-based**, matching against a hand-maintained taxonomy of
> languages, frameworks, platforms, tools, databases and concepts. It is not spaCy NER,
> and it will not find anything outside the taxonomy. This is a deliberate simplicity
> trade-off for now; replacing it with a real NER pass is a long-term goal.

---

### 4.3 Supplemental Experience Integration

**Purpose**

Allow users to provide additional experience not included in their one-page resume.

Examples:

- Extra projects
- Coursework
- Technical implementations
- Extended descriptions of roles

**System Design**

- The supplemental document acts as a **high-recall contextual memory**, not a second
  resume.
- Extract relevant signals (skills, tools, domains)
- Link supplemental data to resume content
- Use only when it improves job alignment
- Do not automatically merge or expand resume content

**Trust Constraints**

- No fabrication of experience
- No assumptions beyond provided data
- Must indicate when supplemental data is used

> **Current status: partially implemented.** Supplemental text is ingested, and its
> domain entities and KeyBERT phrases are extracted and returned in the API response.
> It does **not** yet feed the alignment machine — supplemental evidence is not
> matched against requirements and does not influence `alignment_score`.
>
> The decision of whether it should enter alignment as a separately flagged evidence
> source, or remain analysis-only context, is open. See `CURRENT_GOALS.md` →
> *Open decisions*.

---

### 4.4 Optimization Logic Layer

This layer determines what changes should be made.

**Responsibilities**

Identify:

- Which bullets should be rewritten
- Which skills should be emphasized
- Which content should be removed or replaced

Deterministic and rule-based (non-LLM).

**Design**

The layer consumes the alignment machine's output — the cited evidence per requirement —
and converts it into a ranked, actionable list. Each action names the requirement, the
reason, the evidence that supports the reason, and the section the change belongs in.
Actions are prioritised: a required requirement with no evidence outranks a preferred
requirement with partial evidence.

> **Current status: stubbed.** `app/routes/analyze.py` currently produces a single
> template string naming the top three missing skills, plus a placeholder explanation.
> `ImprovementResult.rewritten_bullets` is always empty. Rebuilding this layer is
> Phase 4 of the MVP plan.

---

### 4.5 LLM Refinement Layer

The LLM is used only after analysis and optimization.

**Responsibilities**

- Rewrite selected resume bullets
- Improve wording and clarity
- Adjust tone to match the job description

**Constraints**

- No hallucination
- No adding unsupported experience
- Only rewrite based on provided inputs
- Must follow structured output format

**Provider model**

The layer is defined behind a `RefinementProvider` interface with two implementations:

- `OpenAIProvider` — used when `OPENAI_API_KEY` is set. Uses a small, fast model
  (`gpt-4o-mini`) at temperature 0, with a prompt that forbids introducing any
  technology, metric, employer or accomplishment not present in the input.
- `LocalGroundedProvider` — the default, used when no API key is configured. Performs a
  strictly grounded rewrite: it promotes requirement terms that are *already present* in
  the bullet and otherwise leaves the wording untouched. It cannot introduce facts, so
  the no-hallucination constraint holds with no network access at all.

> **Current status: not implemented.** `openai` and `python-dotenv` are present in
> `requirements.txt` but there is no LLM code in the project. Building this layer with
> the provider abstraction and a working no-API-key default is Phase 5 of the MVP plan.
>
> The point of the local provider is that the system is demonstrable end to end —
> including the LLM stage — on a machine with no credentials, while keeping the
> production path a one-line configuration change.

---

### 4.6 Output Layer

**Output Format**

```json
{
  "analysis": {
    "matched_skills": [],
    "missing_skills": [],
    "alignment_score": 0.0
  },
  "improvements": {
    "rewritten_summary": "",
    "rewritten_bullets": [],
    "explanations": []
  }
}
```

> **Current status: implemented** as `AnalyzeResponse` in `app/models/schemas.py`, with
> `alignment_evidence` added to `AnalysisResult` and `actions` planned for
> `ImprovementResult`. The frontend renders the analysis cards but does **not** yet
> render the evidence rows — see Phase 6 of the MVP plan.

---

## 5. Backend Layer (FastAPI)

**Responsibilities**

- Accept resume, job description, and supplemental input
- Run ingestion, analysis, optimization, and LLM pipeline
- Return structured JSON output

**Endpoints**

| Endpoint | Method | Body | Status |
| --- | --- | --- | --- |
| `/` | GET | — | serves the static frontend |
| `/health` | GET | — | `{"status": "ok"}` |
| `/analyze` | POST | JSON `AnalyzeRequest` | implemented |
| `/analyze-upload` | POST | multipart form, text and/or files | implemented |
| `/optimize` | POST | `AnalyzeRequest` | planned |

> The frontend posts multipart `FormData` to `/analyze-upload`; `/analyze` (JSON) is the
> programmatic path. The README previously stated the browser posts JSON to
> `/analyze`, which is incorrect — corrected in Phase 7 of the MVP plan.

---

## 6. Frontend Layer

**Features**

- Upload resume, or paste the text directly
- Input job description
- Upload supplemental experience
- Display structured analysis: alignment score, matched / missing / underrepresented
  skills, KeyBERT phrases, domain entities
- Display improvement suggestions
- Export updated resume — *not yet built*

> **Current status: implemented** as a static single-page demo (`app/static/`) with no
> build step and no framework. It reads well and shows the shape of the product, but it
> does not yet surface the alignment evidence or the recommended changes — the two
> things that actually demonstrate the system's value. Adding them is Phase 6.

---

## 7. Development Environment

**Development runs in a conda environment. Docker is reserved for the final MVP build.**

**Tools**

- Conda environment `resume-ai` (Python 3.10), located **outside** the repository
- FastAPI backend
- `requirements.txt` for Python dependencies — the single source of truth, shared by
  the conda environment and the Docker image so the two cannot drift apart
- `environment.yml` describing the conda environment declaratively
- `scripts/setup_env.sh` for one-command bootstrapping
- spaCy model `en_core_web_sm` (required by `keyphrase-vectorizers`)

**Rules**

- The environment must be reproducible: `environment.yml` plus `requirements.txt`
- No manual dependency installs outside the conda environment
- The conda environment is disposable — it can be deleted and rebuilt from
  `environment.yml` at any time
- The Docker image is **not** part of the development loop. It is built once the MVP is
  finished, so the project can be reproduced and shipped by someone else

**Setup**

```bash
./scripts/setup_env.sh

conda activate resume-ai
python -m pytest
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

> **`en_core_web_sm` is required and easy to forget.** It is not a PyPI dependency and
> not a conda package; it must be fetched with `python -m spacy download
> en_core_web_sm`. Without it `spacy.load("en_core_web_sm")` raises `OSError [E050]`
> and every KeyBERT call fails — the API still responds, but with no keyphrases and
> degraded evidence. `environment.yml` cannot carry this step, so
> `scripts/setup_env.sh` performs it, and the Dockerfile performs the same download.

> **Why not Docker for development?** The Docker configuration caused repeated friction
> during development (rebuild latency, cache invalidation, environment drift between
> the image and the host). The image is now treated as a final artefact rather than a
> development dependency. The remaining Docker decisions — root `Dockerfile` vs
> `.devcontainer/`, non-root user, verification — are Phase 9 of the MVP plan.

---

## 8. Project Goals

- Build an explainable resume optimization system
- Demonstrate applied NLP and pipeline design
- Show controlled LLM usage
- Create a usable tool for real job applications

---

## 9. Non-Goals

- Full ATS scoring systems
- GPU-based inference
- Complex frontend UX (initially)
- Training custom ML models **in the MVP** — a learned ranker remains a long-term goal,
  but it is explicitly deferred rather than ruled out

---

## 10. Development Strategy

**Implemented order**

1. Input ingestion (plain text first)
2. Structured analysis engine
3. API endpoint (`/analyze`)
4. Embeddings, KeyBERT and NER extraction
5. Alignment machine with cited evidence
6. Clean resume evidence: bullet joining, heading/subheader stripping, tagged titles
7. Finish the alignment machine: per-source matrices, NER restored as an evidence
   source, evidence floor, cross-source de-duplication, mean-over-sub-requirements
   scoring

**Remaining for the MVP**

8. — *currently here* — Correct the job-description requirement extraction
9. Rebuild the optimization layer
10. Add the LLM refinement layer with a working no-API-key default
11. Surface evidence and recommendations in the frontend
12. Align the documentation with the code
13. Produce the final Docker image for reproducibility

---

## 11. Working Instructions for AI Assistants

When working in this repository:

- Follow the analysis-first architecture — never build an LLM-first path
- Prioritise structured logic over generation
- Ensure every output is explainable and every score is citable
- Maintain strict JSON formatting in schemas and API responses
- Never introduce hallucinated features or unsupported resume content
- Update `CURRENT_GOALS.md` and this document in the same commit as the code they
  describe; the docs are part of the deliverable, not an afterthought
- Add a focused test for any change to analysis logic
- Run the suite with `python -m pytest` inside the conda env `resume-ai`; do not
  reinstall dependencies into the system Python
- `en_core_web_sm` must be present in the environment
  (`python -m spacy download en_core_web_sm`). If KeyBERT starts raising
  `OSError [E050]`, this is why
