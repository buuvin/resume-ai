from app.models.schemas import AnalyzeRequest, AnalyzeResponse, ImprovementResult
from fastapi import APIRouter
from app.services.analysis import analyze_resume

router = APIRouter()

@router.post("/analyze", response_model=AnalyzeResponse)
def analyze(request: AnalyzeRequest):
    analysis = analyze_resume(
        request.resume_text, 
        request.job_description_text,
        request.supplemental_text or ""
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