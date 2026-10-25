from sqlalchemy import Column, String, Integer, Text, ForeignKey, DateTime, Float, Boolean, Table
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from database import Base

# Junction tables
paper_authors = Table(
    'paper_authors', Base.metadata,
    Column('paper_id', String, ForeignKey('research_papers.id', ondelete='CASCADE'), primary_key=True),
    Column('author_id', String, ForeignKey('authors.id', ondelete='CASCADE'), primary_key=True)
)

paper_topics = Table(
    'paper_topics', Base.metadata,
    Column('paper_id', String, ForeignKey('research_papers.id', ondelete='CASCADE'), primary_key=True),
    Column('topic_id', String, ForeignKey('topics.id', ondelete='CASCADE'), primary_key=True)
)

class Analysis(Base):
    __tablename__ = "analyses"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    query = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    status = Column(String, default="pending")
    stage = Column(String, default="queued")
    error_message = Column(Text, nullable=True)
    failed_stage = Column(String, nullable=True)
    
    # Corpus summary metadata
    papers_retrieved = Column(Integer, default=0)
    papers_analysed = Column(Integer, default=0)
    raw_provider_results = Column(Integer, default=0)
    deduplicated_papers = Column(Integer, default=0)
    retained_papers = Column(Integer, default=0)
    full_text_analysed = Column(Integer, default=0)
    year_start = Column(Integer, nullable=True)
    year_end = Column(Integer, nullable=True)

    papers = relationship("Paper", back_populates="analysis", cascade="all, delete-orphan")
    gaps = relationship("ResearchGap", back_populates="analysis", cascade="all, delete-orphan")

class Paper(Base):
    __tablename__ = "research_papers"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    analysis_id = Column(String, ForeignKey("analyses.id", ondelete="CASCADE"))
    external_id = Column(String, index=True)
    title = Column(String, nullable=False)
    year = Column(Integer, nullable=True)
    abstract = Column(Text, nullable=True)
    venue = Column(String, nullable=True)
    citation_count = Column(Integer, default=0)
    open_access_status = Column(String, nullable=True)
    
    # Traceability fields
    doi = Column(String, nullable=True)
    url = Column(String, nullable=True)
    pdf_url = Column(String, nullable=True)
    source = Column(String, nullable=True) # e.g. OpenAlex, arXiv, Semantic Scholar, Google Scholar
    
    analysis = relationship("Analysis", back_populates="papers")
    authors = relationship("Author", secondary="paper_authors", back_populates="papers")
    topics = relationship("Topic", secondary="paper_topics", back_populates="papers")
    embeddings = relationship("Embedding", back_populates="paper", cascade="all, delete-orphan")
    evidence_items = relationship("GapEvidence", back_populates="paper", cascade="all, delete-orphan")

class Author(Base):
    __tablename__ = "authors"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    papers = relationship("Paper", secondary="paper_authors", back_populates="authors")

class Topic(Base):
    __tablename__ = "topics"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False, unique=True)
    papers = relationship("Paper", secondary="paper_topics", back_populates="topics")

class Embedding(Base):
    __tablename__ = "embeddings"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    paper_id = Column(String, ForeignKey("research_papers.id"))
    chunk_text = Column(Text)
    vector = Column(Text) # Temporarily stored as Text since pgvector is removed
    type = Column(String) # 'abstract', 'limitation', 'future_work'
    
    paper = relationship("Paper", back_populates="embeddings")

class ResearchGap(Base):
    __tablename__ = "research_gaps"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    analysis_id = Column(String, ForeignKey("analyses.id", ondelete="CASCADE"), nullable=False)
    title = Column(String, nullable=False)
    statement = Column(Text, nullable=False)
    why_it_matters = Column(Text, nullable=False)
    category = Column(String, nullable=False) # methodological, evaluation, dataset, theoretical, application_domain, generalization, conflicting_findings, future_direction, other
    origin = Column(String, default="cross_paper_inference") # explicit vs cross_paper_inference
    evidence_strength = Column(String, default="moderate") # strong, moderate, preliminary
    supporting_paper_count = Column(Integer, default=1)
    source_coverage = Column(Text, nullable=True)
    qualifications = Column(Text, nullable=True)
    reasoning = Column(Text, nullable=True)
    counterevidence = Column(Text, nullable=True) # JSON string if present
    created_at = Column(DateTime, default=datetime.utcnow)

    analysis = relationship("Analysis", back_populates="gaps")
    evidence = relationship("GapEvidence", back_populates="gap", cascade="all, delete-orphan")

class GapEvidence(Base):
    __tablename__ = "gap_evidence"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    gap_id = Column(String, ForeignKey("research_gaps.id", ondelete="CASCADE"), nullable=False)
    paper_id = Column(String, ForeignKey("research_papers.id", ondelete="CASCADE"), nullable=False)
    passage = Column(Text, nullable=False)
    section = Column(String, default="Limitations")
    page = Column(Integer, nullable=True)
    source_scope = Column(String, default="abstract_only") # abstract_only vs full_text
    relevance_note = Column(Text, nullable=True)
    
    gap = relationship("ResearchGap", back_populates="evidence")
    paper = relationship("Paper", back_populates="evidence_items")
