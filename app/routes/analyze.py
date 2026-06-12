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
    return AnalyzeResponse(analysis=analysis, improvements=ImprovementResult())