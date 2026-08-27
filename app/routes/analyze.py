from app.models.schemas import AnalyzeRequest, AnalyzeResponse, ImprovementResult
from app.services.embeddings import embed_document, extract_keyphrases
from app.services.ingestion import extract_upload_text
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from app.services.analysis import analyze_resume

router = APIRouter()

def build_response(resume_text: str, job_description_text: str, supplemental_text: str):
    keyphrases = {}
    try:
        documents = {
            "resume": resume_text,
            "job description": job_description_text,
            "supplemental": supplemental_text,
        }
        for document_name, document_text in documents.items():
            embedded_document = embed_document(document_text)
            keyphrases[document_name] = extract_keyphrases(
                document_text, embedded_document=embedded_document
            )
            if embedded_document.lines:
                print( 
                    f"[embeddings] {document_name} first sentence: {embedded_document.lines[0]}",
                    flush=True,
                )
                print(
                    f"[embeddings] {document_name} embedding: {embedded_document.embeddings[0]}",
                    flush=True,
                )
    except ModuleNotFoundError as error:
        print(
            f"[embeddings] unavailable: install the embedding and KeyBERT dependencies ({error.name})",
            flush=True,
        )

    analysis = analyze_resume(
        resume_text,
        job_description_text,
        supplemental_text,
        resume_keyphrases=set(keyphrases.get("resume", [])),
        job_keyphrases=set(keyphrases.get("job description", [])),
        supplemental_keyphrases=set(keyphrases.get("supplemental", [])),
    )
    if analysis.missing_skills:
        top_gap_list = ", ".join(analysis.missing_skills[:3])
        rewritten_summary = f"Emphasize direct experience with {top_gap_list} if it is supported by the resume or supplemental context."
        explanations = [
            "The backend is still using a deterministic baseline, so this summary only points to gaps identified from the submitted text.",
        ]
    else:
        rewritten_summary = "The current resume already matches the submitted job description closely."
        explanations = [
            "This is a baseline analysis result and can later be replaced with an MLP or LLM-driven rewrite step.",
        ]

    return AnalyzeResponse(
        analysis=analysis,
        improvements=ImprovementResult(
            rewritten_summary=rewritten_summary,
            rewritten_bullets=[],
            explanations=explanations,
        ),
    )


@router.post("/analyze", response_model=AnalyzeResponse)
def analyze(request: AnalyzeRequest):
    return build_response(
        request.resume_text,
        request.job_description_text,
        request.supplemental_text or "",
    )


@router.post("/analyze-upload", response_model=AnalyzeResponse)
async def analyze_upload(
    resume_text: str = Form(""),
    job_description_text: str = Form(""),
    supplemental_text: str = Form(""),
    resume_file: UploadFile | None = File(None),
    job_description_file: UploadFile | None = File(None),
    supplemental_file: UploadFile | None = File(None),
):
    try:
        if resume_file:
            resume_text = await extract_upload_text(resume_file)
        if job_description_file:
            job_description_text = await extract_upload_text(job_description_file)
        if supplemental_file:
            supplemental_text = await extract_upload_text(supplemental_file)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    if not resume_text.strip() or not job_description_text.strip():
        raise HTTPException(
            status_code=422,
            detail="Resume and job description text or files are required.",
        )

    return build_response(
        resume_text.strip(),
        job_description_text.strip(),
        supplemental_text.strip(),
    )