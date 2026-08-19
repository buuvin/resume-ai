from typing import List, Optional

from pydantic import BaseModel, Field

class AnalyzeRequest(BaseModel):
    resume_text: str = Field(..., min_length=1)
    job_description_text: str = Field(..., min_length=1)
    supplemental_text: Optional[str] = None

class AnalysisResult(BaseModel):
    matched_skills: List[str]
    missing_skills: List[str]
    alignment_score: float
    resume_keyword_count: int
    job_keyword_count: int
    supplemental_keyword_count: int
    supplemental_used: bool

class ImprovementResult(BaseModel):
    rewritten_summary: str = ""
    rewritten_bullets: List[str] = []
    explanations: List[str] = []

class AnalyzeResponse(BaseModel):
    analysis: AnalysisResult
    improvements: ImprovementResult