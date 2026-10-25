from pydantic import BaseModel, ConfigDict, Field
from typing import List, Optional, Dict, Any
from datetime import datetime

class PaperSchema(BaseModel):
    id: str
    title: str
    authors: List[str] = Field(default_factory=list)
    year: Optional[int] = None
    venue: Optional[str] = None
    abstract: Optional[str] = None
    citation_count: int = 0
    open_access_status: Optional[str] = None
    external_id: str
    doi: Optional[str] = None
    url: Optional[str] = None
    pdf_url: Optional[str] = None
    source: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

class AnalysisCreate(BaseModel):
    query: str
    year_min: Optional[int] = None
    year_max: Optional[int] = None
    limit: Optional[int] = 50
    sources: Optional[List[str]] = None

class AnalysisResponse(BaseModel):
    id: str
    query: str
    status: str
    stage: Optional[str] = None
    error_message: Optional[str] = None
    failed_stage: Optional[str] = None
    papers_retrieved: Optional[int] = 0
    papers_analysed: Optional[int] = 0
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

class EvidencePassageSchema(BaseModel):
    text: str
    section: Optional[str] = "Limitations"
    page: Optional[int] = None
    source_scope: Optional[str] = "abstract_only"  # 'abstract_only' or 'full_text'

class SupportingPaperSchema(BaseModel):
    paper_id: str
    title: str
    authors: List[str] = Field(default_factory=list)
    year: Optional[int] = None
    venue: Optional[str] = None
    doi: Optional[str] = None
    url: Optional[str] = None
    pdf_url: Optional[str] = None
    citation_count: int = 0
    source_scope: Optional[str] = "abstract_only"  # 'abstract_only' or 'full_text'
    evidence_passages: List[EvidencePassageSchema] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)

class ResearchGapSchema(BaseModel):
    gap_id: str
    title: str
    statement: str
    why_it_matters: str
    category: str  # methodological, evaluation, dataset, theoretical, application_domain, generalization, conflicting_findings, future_direction, other
    origin: str  # explicit | cross_paper_inference
    evidence_strength: str  # strong | moderate | preliminary
    source_coverage: Optional[str] = None
    qualifications: Optional[str] = None
    supporting_paper_count: int
    supporting_papers: List[SupportingPaperSchema] = Field(default_factory=list)
    counterevidence: List[str] = Field(default_factory=list)
    reasoning: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

class YearRangeSchema(BaseModel):
    start: Optional[int] = None
    end: Optional[int] = None

class CorpusStatsSchema(BaseModel):
    papers_retrieved: int
    papers_analysed: int
    raw_provider_results: Optional[int] = None
    deduplicated_papers: Optional[int] = None
    retained_papers: Optional[int] = None
    full_text_analysed: Optional[int] = 0
    publication_year_range: YearRangeSchema
    categories_breakdown: Optional[Dict[str, int]] = None

class AnalysisResultsResponse(BaseModel):
    search_id: str
    query: str
    status: str
    stage: Optional[str] = None
    corpus: CorpusStatsSchema
    gaps: List[ResearchGapSchema] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)
