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
    concepts: List[str] = Field(default_factory=list)

class AlignmentEvidence(BaseModel):
    source: Literal["ner", "keybert", "bulletpoints"]
    requirement: str
    evidence: str
    alignment: float
    exact_match: bool

class AnalysisResult(BaseModel):
    matched_skills: List[str]
    underrepresented_skills: List[str]
    missing_skills: List[str]
    resume_keyphrases: List[str]
    job_description_keyphrases: List[str]
    supplemental_keyphrases: List[str]
    alignment_score: float
    resume_entities: DomainEntities
    job_description_entities: DomainEntities
    supplemental_entities: DomainEntities
    alignment_evidence: List[AlignmentEvidence] = Field(default_factory=list)

class ImprovementResult(BaseModel):
    rewritten_summary: str = ""
    rewritten_bullets: List[str] = []
    explanations: List[str] = []

class AnalyzeResponse(BaseModel):
    analysis: AnalysisResult
    improvements: ImprovementResult