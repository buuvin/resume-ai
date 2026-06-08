Resume AI — End‑to‑End Resume Rewriting System
1. Project Overview
Resume AI is an end‑to‑end system that takes:

A resume (PDF or DOCX)

A job description (text)

Extra context about the candidate (text)

and produces:

A rewritten, job‑aligned resume section

Improved bullet points

A rewritten professional summary

A structured JSON output that can be used by the frontend

The system must always remain honest, non‑hallucinatory, and grounded in the provided inputs.

This project uses:

FastAPI for the backend

OpenAI API for the LLM rewriting pipeline

Python for parsing and logic

Docker Dev Containers for consistent development environments

VS Code as the development interface

No local LLMs are used.
All LLM inference happens through OpenAI’s API.

2. High‑Level Architecture
A. Ingestion Layer
Responsible for extracting clean text from:

PDF resumes

DOCX resumes

Job descriptions

Extra context

Libraries used (subject to change):

pdfplumber for PDFs

python-docx for DOCX

Custom cleaning utilities

Output:

Code
{
  "resume_text": "...",
  "job_description_text": "...",
  "extra_context_text": "..."
}
B. LLM Rewriting Pipeline (Core Logic)
This is the heart of the system.

Inputs:

resume_text

job_description_text

extra_context_text

The pipeline:

Extracts key job requirements

Extracts relevant experience from the resume

Rewrites resume sections honestly

Generates improved bullet points

Produces a rewritten summary

Returns structured JSON

The LLM must:

Never hallucinate

Never invent experience

Only rewrite based on provided inputs

Follow the JSON output format strictly

Model used:
gpt-4o-mini (or similar OpenAI model)

C. Backend Layer (FastAPI)
FastAPI exposes endpoints such as:

POST /upload-resume

POST /rewrite

POST /analyze

Responsibilities:

Accept file uploads

Parse resume + job description

Call the LLM pipeline

Return structured JSON to the frontend

The backend runs inside a VS Code Dev Container.

D. Frontend Layer (Future)
The frontend will:

Allow users to upload resumes

Paste job descriptions

Provide extra context

Display rewritten resume content

Allow downloading the rewritten resume

Framework:
React or simple HTML/CSS (TBD)

3. Development Environment (Dev Container)
This project uses a VS Code Dev Container to ensure identical environments across machines.

The environment is defined by:

.devcontainer/devcontainer.json

Dockerfile

requirements.txt

Key rules:

The container is temporary; the image is persistent

Code lives on the host machine, not inside the container

Every time VS Code reopens the project, it creates a new container instance

All Python packages must be added to requirements.txt after installation

Code
pip freeze > requirements.txt
4. LLM Prompting Rules
The system prompt must enforce:

Honesty

No hallucinations

No invented experience

Only rewriting, reorganizing, and clarifying

Structured JSON output

The user prompt must include:

Resume text

Job description

Extra context

Required JSON output format

5. JSON Output Format (Strict)
The LLM must always return:

json
{
  "job_requirements": [],
  "matched_experience": [],
  "rewritten_summary": "",
  "rewritten_experience": [],
  "improved_bullet_points": []
}
If the LLM returns invalid JSON, the backend must handle it gracefully.

6. Project Goals
Build a reliable, honest resume rewriting engine

Provide structured, predictable output

Build a clean backend API

Build a simple frontend for user interaction

Deploy the system (Render + Vercel recommended)

7. Non‑Goals
Running local LLMs

Heavy ML training

GPU‑based inference

ATS scoring or ranking (future feature)

8. Switching Between Machines
This project is designed to be worked on from:

Windows PC

MacBook

Workflow:

Commit + push from one machine

Pull on the other

Reopen in Dev Container

Continue working

Copilot will use this file as the authoritative context.

9. How Copilot Should Behave
Copilot should:

Use this file as the source of truth

Never assume features not listed here

Never hallucinate capabilities

Follow the architecture described

Follow the JSON format strictly

Keep all rewriting honest and grounded