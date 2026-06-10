from fastapi import APIRouter
from app.services.analysis import analyze_resume

router = APIRouter()

@router.post("/analyze")
def analyze(resume: str, job_description: str):
    result = analyze_resume(resume, job_description)
    return result