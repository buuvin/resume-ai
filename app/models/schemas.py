from typing import Literal

from pydantic import BaseModel, Field


class AnalyzeRequest(BaseModel):
    resume_text: str = Field(..., min_length=1)
    job_description_text: str = Field(..., min_length=1)
    supplemental_text: str | None = None

class DomainEntities(BaseModel):
    languages: list[str] = Field(default_factory=list)
    frameworks: list[str] = Field(default_factory=list)
    platforms: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
    databases: list[str] = Field(default_factory=list)
    concepts: list[str] = Field(default_factory=list)

class AlignmentEvidence(BaseModel):
    source: Literal["ner", "keybert", "bulletpoints"]
    requirement: str
    sub_requirement: str = ""
    evidence: str
    alignment: float
    exact_match: bool

class AnalysisResult(BaseModel):
    matched_skills: list[str]
    underrepresented_skills: list[str]
    missing_skills: list[str]
    resume_keyphrases: list[str]
    job_description_keyphrases: list[str]
    supplemental_keyphrases: list[str]
    alignment_score: float
    resume_entities: DomainEntities
    job_description_entities: DomainEntities
    supplemental_entities: DomainEntities
    alignment_evidence: list[AlignmentEvidence] = Field(default_factory=list)
    resume_title_lines: list[str] = Field(default_factory=list)

class ImprovementResult(BaseModel):
    rewritten_summary: str = ""
    rewritten_bullets: list[str] = []
    explanations: list[str] = []

class AnalyzeResponse(BaseModel):
    analysis: AnalysisResult
    improvements: ImprovementResult