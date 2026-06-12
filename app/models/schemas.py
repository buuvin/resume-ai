from pydantic import BaseModel, Field
from typing import List, Optional

class AnalyzeRequest(BaseModel):
    resume_text: str = Field(..., min_length=1)
    job_description_text: str = Field(..., min_length=1)
    supplemental_text: Optional[str] = None

class AnalysisResult(BaseModel):
    matched_skills: List[str]
    missing_skills: List[str]
    alignment_score: float

class ImprovementResult(BaseModel):
    rewritten_summary: str = ""
    rewritten_bullets: List[str] = []
    explanations: List[str] = []

class AnalyzeResponse(BaseModel):
    analysis: AnalysisResult
    improvements: ImprovementResult