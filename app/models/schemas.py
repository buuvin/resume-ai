from typing import List, Literal, Optional

from pydantic import BaseModel, Field

class AnalyzeRequest(BaseModel):
    resume_text: str = Field(..., min_length=1)
    job_description_text: str = Field(..., min_length=1)
    supplemental_text: Optional[str] = None

class DomainEntities(BaseModel):
    languages: List[str] = Field(default_factory=list)
    frameworks: List[str] = Field(default_factory=list)
    platforms: List[str] = Field(default_factory=list)
    tools: List[str] = Field(default_factory=list)
    databases: List[str] = Field(default_factory=list)

class Requirement(BaseModel):
    keyword: str
    priority: Literal["required", "preferred"]

class ResumeEvidence(BaseModel):
    keyword: str
    sections: List[str] = Field(default_factory=list)
    prominence: Literal["prominent", "supporting"]

class RequirementCoverage(BaseModel):
    requirement: Requirement
    status: Literal["covered", "underrepresented", "missing"]
    coverage_score: float
    evidence: List[ResumeEvidence] = Field(default_factory=list)

class GapAnalysis(BaseModel):
    action: Literal["reframe", "swap", "augment", "remove", "promote"]
    requirement: Requirement
    rationale: str
    suggested_change: str

class AnalysisResult(BaseModel):
    matched_skills: List[str]
    missing_skills: List[str]
    resume_keyphrases: List[str]
    job_description_keyphrases: List[str]
    supplemental_keyphrases: List[str]
    alignment_score: float
    resume_keyword_count: int
    job_keyword_count: int
    supplemental_keyword_count: int
    supplemental_used: bool
    resume_entities: DomainEntities
    job_description_entities: DomainEntities
    supplemental_entities: DomainEntities
    requirements: List[Requirement] = Field(default_factory=list)
    resume_evidence: List[ResumeEvidence] = Field(default_factory=list)
    requirement_coverage: List[RequirementCoverage] = Field(default_factory=list)
    gap_analysis: List[GapAnalysis] = Field(default_factory=list)

class ImprovementResult(BaseModel):
    rewritten_summary: str = ""
    rewritten_bullets: List[str] = []
    explanations: List[str] = []

class AnalyzeResponse(BaseModel):
    analysis: AnalysisResult
    improvements: ImprovementResult