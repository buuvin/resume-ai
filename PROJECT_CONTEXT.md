Resume AI — Intelligent Resume Optimization System
1. Project Overview

Resume AI is an end-to-end system designed to analyze, optimize, and refine resumes for specific job roles.
Inputs:

- Resume (PDF or DOCX)
- Job Description (text)
- Optional Supplemental Experience Document (text containing additional background)

Outputs:

- Structured analysis of resume vs job alignment
- Identification of strengths, gaps, and opportunities
- Suggested resume improvements
- LLM-assisted rewritten bullets and summary
- Structured JSON output for frontend integration


2. Core Philosophy
This system follows an analysis-first architecture.
Key Principles:

- Structured reasoning before generation
- No hallucination or fabrication of experience
- Controlled and explainable outputs
- LLMs are used only for refinement, not reasoning

System Rule:
The system must perform all reasoning using structured logic before invoking the LLM.

3. High-Level Architecture
Pipeline
Input
→ Parsing
→ Structured Analysis
→ Optimization Logic
→ LLM Refinement
→ Output

4. System Components

4.1 Ingestion Layer
Responsibilities

Extract clean text from:

- PDF resumes (pdfplumber)
- DOCX resumes (python-docx)
- Job descriptions
- Supplemental documents



Output:
JSON{  "resume_text": "...",  "job_description_text": "...",  "supplemental_text": "..."}Show more lines

4.2 Structured Analysis Engine (Core System)
This is the primary intelligence layer.
Responsibilities

Extract:

- Skills
- Tools
- Keywords
- Role signals


Compare resume against job description
Identify:

- Matching skills
- Missing skills
- Underrepresented experience
- Low-value or redundant content



Output Example:
JSON{  "matched_skills": [],  "missing_skills": [],  "underrepresented_skills": [],  "alignment_score": 0.0}Show more lines

4.3 Supplemental Experience Integration
Purpose:
Allow users to provide additional experience not included in their one-page resume.

Examples:

- Extra projects
- Coursework
- Technical implementations
- Extended descriptions of roles

System Design:
- The supplemental document acts as a high-recall contextual memory, not a second resume.

Behavior:
- Extract relevant signals (skills, tools, domains)
- Link supplemental data to resume content
- Use only when it improves job alignment
- Do not automatically merge or expand resume content

Trust Constraints:

- No fabrication of experience
- No assumptions beyond provided data
- Must indicate when supplemental data is used


4.4 Optimization Logic Layer
This layer determines what changes should be made.
Responsibilities:

Identify:
- Which bullets should be rewritten
- Which skills should be emphasized
- Which content should be removed or replaced


Deterministic and rule-based (non-LLM)


4.5 LLM Refinement Layer
The LLM is used only after analysis and optimization.
Reponsibilities:
- Rewrite selected resume bullets
- Improve wording and clarity
- Adjust tone to match the job description

Constraints:

- No hallucination
- No adding unsupported experience
- Only rewrite based on provided inputs
- Must follow structured output format

Model:

OpenAI API (e.g., gpt-4o-mini)


4.6 Output Layer
Output Format:
JSON{  "analysis": {    "matched_skills": [],    "missing_skills": [],    "alignment_score": 0.0  },  "improvements": {    "rewritten_summary": "",    "rewritten_bullets": [],    "explanations": []  }}Show more lines

5. Backend Layer (FastAPI)
Responsibilities:

- Accept resume, job description, and supplemental input
- Run ingestion, analysis, optimization, and LLM pipeline
- Return structured JSON output

Initial Endpoints:

- POST /analyze
- POST /optimize (future)
- POST /upload-resume (future)


6. Frontend Layer (Future)
Features:

- Upload resume
- Input job description
- Upload supplemental experience
- Display structured analysis
- Display improvement suggestions
- Export updated resume


7. Development Environment
Tools:

- Docker Dev Containers
- FastAPI backend
- Python virtual environment inside container
- requirements.txt for dependencies

Rules:

- Environment must be reproducible
- No manual dependency installs outside venv
- Environment setup handled via Dockerfile
- Code resides on host machine


8. Project Goals

- Build an explainable resume optimization system
- Demonstrate applied NLP and pipeline design
- Show controlled LLM usage
- Create a usable tool for real job applications


9. Non-Goals

- Full ATS scoring systems
- Training custom ML models
- GPU-based inference
- Complex frontend UX (initially)


10. Development Strategy
Implementation Order:

- Input ingestion (start with plain text)
- Structured analysis engine
- API endpoint (/analyze)
- Optimization logic
- LLM refinement
- Frontend integration


11. Copilot Instructions
Copilot must:

- Follow the analysis-first architecture
- Avoid building LLM-first systems
- Prioritize structured logic over generation
- Ensure outputs are explainable
- Maintain strict JSON formatting
- Never introduce hallucinated features