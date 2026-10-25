from __future__ import annotations

import concurrent.futures
import difflib
import logging
import math
import re
import uuid
from collections import defaultdict
from datetime import datetime
from typing import List, Optional, Dict

import requests
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from database import SessionLocal, get_db
from models import Analysis, Author, Paper, ResearchGap, GapEvidence
from providers.arxiv import ArxivProvider
from providers.googlescholar import GoogleScholarProvider
from providers.openalex import OpenAlexProvider
from providers.semanticscholar import SemanticScholarProvider
from schemas import (
    AnalysisCreate,
    AnalysisResponse,
    PaperSchema,
    ResearchGapSchema,
    SupportingPaperSchema,
    EvidencePassageSchema,
    AnalysisResultsResponse,
    CorpusStatsSchema,
    YearRangeSchema,
)
import analytics
import gap_engine

router = APIRouter()
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Maximum allowed query length (prevents abuse / DB column overflow)
# ---------------------------------------------------------------------------
MAX_QUERY_LENGTH = 500

COMMON_QUERY_CORRECTIONS = {
    "reccomendation": "recommendation",
    "recomendation": "recommendation",
    "recommedation": "recommendation",
    "recomendations": "recommendations",
    "reccomendations": "recommendations",
    "machne": "machine",
    "lernning": "learning",
    "learnng": "learning",
    "federeted": "federated",
    "federatd": "federated",
    "vulnerabilty": "vulnerability",
    "vulnerablity": "vulnerability",
    "explainble": "explainable",
    "cryptograpy": "cryptography",
    "knoledge": "knowledge",
}


def normalize_query_for_retrieval(query: str) -> str:
    """Correct high-confidence domain typos without changing displayed input."""
    known_words = list(COMMON_QUERY_CORRECTIONS)

    def correct_word(word: str) -> str:
        lower_word = word.lower()
        if lower_word in COMMON_QUERY_CORRECTIONS:
            corrected = COMMON_QUERY_CORRECTIONS[lower_word]
        else:
            matches = difflib.get_close_matches(lower_word, known_words, n=1, cutoff=0.9)
            corrected = COMMON_QUERY_CORRECTIONS[matches[0]] if matches else word
        return corrected.capitalize() if word[:1].isupper() else corrected

    return " ".join(correct_word(word) for word in query.split())


# ---------------------------------------------------------------------------
# Background task — executes the 7-stage gap discovery pipeline
# ---------------------------------------------------------------------------
def run_analysis_task(
    analysis_id: str,
    query: str,
    year_min: Optional[int] = None,
    year_max: Optional[int] = None,
    limit: Optional[int] = 50,
    requested_sources: Optional[List[str]] = None,
) -> None:
    db = SessionLocal()
    analysis = None
    current_stage = "queued"

    def set_stage(stage: str) -> None:
        nonlocal current_stage
        current_stage = stage
        if analysis is not None:
            analysis.stage = stage
            analysis.status = "running"
            db.commit()

    try:
        analysis = db.query(Analysis).filter(Analysis.id == analysis_id).first()
        if not analysis:
            return

        # Stage 1 & 2: Retrieval
        set_stage("retrieving")
        retrieval_query = normalize_query_for_retrieval(query)
        if retrieval_query != query:
            logger.info("Corrected retrieval query from %r to %r", query, retrieval_query)

        available_providers = {
            "openalex": OpenAlexProvider(),
            "arxiv": ArxivProvider(),
            "semanticscholar": SemanticScholarProvider(),
            "googlescholar": GoogleScholarProvider(),
        }

        if requested_sources:
            selected_providers = [
                prov for key, prov in available_providers.items()
                if key in [s.lower().replace(" ", "") for s in requested_sources]
            ] or list(available_providers.values())
        else:
            selected_providers = list(available_providers.values())

        limit_per_provider = max(15, min(limit or 50, 75))

        def fetch_from_provider(provider):
            try:
                return provider.search_papers(retrieval_query, limit=limit_per_provider)
            except Exception as exc:
                logger.exception("Provider %s failed: %s", provider.__class__.__name__, exc)
                return []

        all_papers_data: list[PaperSchema] = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(selected_providers)) as executor:
            futures = {executor.submit(fetch_from_provider, p): p for p in selected_providers}
            completed, timed_out = concurrent.futures.wait(futures, timeout=45)
            for future in completed:
                try:
                    all_papers_data.extend(future.result())
                except Exception:
                    logger.exception("Provider future execution failed")
            for future in timed_out:
                prov = futures[future]
                future.cancel()
                logger.warning("Provider %s timed out", prov.__class__.__name__)

        # Deduplicate papers by normalized title and DOI with semantic relevance ranking
        seen_titles: set[str] = set()
        seen_dois: set[str] = set()
        clean_q = retrieval_query.lower().strip()
        query_terms = [
            term
            for term in re.findall(r"[a-z0-9]+", clean_q)
            if term not in {"a", "an", "and", "for", "in", "of", "on", "the", "to", "with"}
        ]

        # Semantic relevance filtering via TF-IDF cosine similarity
        filtered_candidates: list[PaperSchema] = []
        if all_papers_data:
            corpus_texts = [f"{p.title or ''} {p.abstract or ''}".lower() for p in all_papers_data]
            try:
                from sklearn.feature_extraction.text import TfidfVectorizer
                from sklearn.metrics.pairwise import cosine_similarity
                tfidf = TfidfVectorizer(stop_words="english", ngram_range=(1, 2))
                mat = tfidf.fit_transform(corpus_texts)
                q_vec = tfidf.transform([clean_q])
                scores = cosine_similarity(q_vec, mat)[0]
            except Exception:
                scores = [1.0] * len(all_papers_data)

            scored = sorted(
                zip(all_papers_data, scores),
                key=lambda x: (x[1], x[0].citation_count),
                reverse=True,
            )
            max_score = max(scores) if len(scores) > 0 else 0.0
            for p_cand, score in scored:
                # If query has solid matches elsewhere, drop semantic outliers below threshold
                if max_score > 0.15 and score < 0.04:
                    continue
                filtered_candidates.append(p_cand)
        else:
            filtered_candidates = all_papers_data

        minimum_matches = max(1, math.ceil(len(query_terms) / 3))

        persisted_papers: list[Paper] = []
        for p_data in filtered_candidates:
            # Check year filters
            if p_data.year is not None:
                if year_min and p_data.year < year_min:
                    continue
                if year_max and p_data.year > year_max:
                    continue

            # Check DOI duplicate
            clean_doi = (p_data.doi or "").strip().lower()
            if clean_doi and clean_doi in seen_dois:
                continue

            # Check title duplicate
            title_key = re.sub(r"[^a-z0-9]", "", (p_data.title or "").lower())
            if not title_key or title_key in seen_titles:
                continue

            searchable_text = f"{p_data.title or ''} {p_data.abstract or ''}".lower()
            if query_terms and sum(term in searchable_text for term in query_terms) < minimum_matches:
                continue

            seen_titles.add(title_key)
            if clean_doi:
                seen_dois.add(clean_doi)

            existing = (
                db.query(Paper)
                .filter(Paper.external_id == p_data.external_id, Paper.analysis_id == analysis_id)
                .first()
            )
            if existing:
                persisted_papers.append(existing)
                continue

            paper = Paper(
                id=p_data.id,
                analysis_id=analysis_id,
                external_id=p_data.external_id,
                title=p_data.title,
                year=p_data.year,
                abstract=p_data.abstract,
                venue=p_data.venue,
                citation_count=p_data.citation_count,
                open_access_status=p_data.open_access_status,
                doi=p_data.doi,
                url=p_data.url or p_data.external_id,
                pdf_url=p_data.pdf_url,
                source=p_data.source,
            )

            for author_name in (p_data.authors or []):
                clean_name = str(author_name).strip()
                if not clean_name:
                    continue
                author = db.query(Author).filter(Author.name == clean_name).first()
                if not author:
                    author = Author(name=clean_name)
                    db.add(author)
                paper.authors.append(author)

            db.add(paper)
            persisted_papers.append(paper)

        db.commit()

        # Update stats on analysis
        analysis.papers_retrieved = len(all_papers_data)
        analysis.papers_analysed = len(persisted_papers)
        years = [p.year for p in persisted_papers if p.year is not None]
        analysis.year_start = min(years) if years else None
        analysis.year_end = max(years) if years else None
        db.commit()

        if not persisted_papers:
            analysis.status = "no_results"
            analysis.stage = "retrieving"
            analysis.error_message = "No papers found matching the research topic. Try broader search terms."
            analysis.failed_stage = None
            db.commit()
            return

        # Stage 3: Topic analysis
        set_stage("analyzing")
        try:
            analytics.extract_topics(persisted_papers)
        except Exception:
            logger.exception("Topic extraction note")

        # Stage 4, 5, 6, 7: Gap synthesis, deduplication, validation, ranking
        set_stage("synthesizing")
        paper_schemas = [
            PaperSchema(
                id=p.id,
                title=p.title,
                authors=[a.name for a in p.authors],
                year=p.year,
                venue=p.venue,
                abstract=p.abstract,
                citation_count=p.citation_count,
                open_access_status=p.open_access_status,
                external_id=p.external_id,
                doi=p.doi,
                url=p.url or p.external_id,
                pdf_url=p.pdf_url,
                source=p.source,
            )
            for p in persisted_papers
        ]

        synthesized_gaps = gap_engine.synthesize_corpus_gaps(paper_schemas, query=query)

        # Clear any existing gaps for this analysis
        db.query(GapEvidence).filter(
            GapEvidence.gap_id.in_(
                db.query(ResearchGap.id).filter(ResearchGap.analysis_id == analysis_id)
            )
        ).delete(synchronize_session=False)
        db.query(ResearchGap).filter(ResearchGap.analysis_id == analysis_id).delete(synchronize_session=False)
        db.commit()

        # Persist synthesized gaps and evidence
        for gap_data in synthesized_gaps:
            gap_orm = ResearchGap(
                id=gap_data.gap_id,
                analysis_id=analysis_id,
                title=gap_data.title,
                statement=gap_data.statement,
                why_it_matters=gap_data.why_it_matters,
                category=gap_data.category,
                origin=gap_data.origin,
                evidence_strength=gap_data.evidence_strength,
                supporting_paper_count=gap_data.supporting_paper_count,
                reasoning=gap_data.reasoning,
            )
            db.add(gap_orm)
            db.flush()

            for sup in gap_data.supporting_papers:
                for passage in sup.evidence_passages:
                    ev_orm = GapEvidence(
                        id=str(uuid.uuid4()),
                        gap_id=gap_orm.id,
                        paper_id=sup.paper_id,
                        passage=passage.text,
                        section=passage.section or "Limitations",
                        page=passage.page,
                    )
                    db.add(ev_orm)

        analysis.status = "completed"
        analysis.stage = "completed"
        analysis.error_message = None
        analysis.failed_stage = None
        db.commit()
        logger.info("Analysis %s completed successfully with %d gaps", analysis_id, len(synthesized_gaps))

    except Exception as exc:
        logger.exception("Analysis %s failed", analysis_id)
        db.rollback()
        try:
            analysis = db.query(Analysis).filter(Analysis.id == analysis_id).first()
            if analysis:
                analysis.status = "failed"
                analysis.stage = "failed"
                analysis.failed_stage = current_stage
                analysis.error_message = str(exc)[:500]
                db.commit()
        except Exception:
            logger.exception("Could not persist failure for analysis %s", analysis_id)
            db.rollback()
    finally:
        db.close()


# ---------------------------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------------------------

@router.post("/analyze", response_model=AnalysisResponse, status_code=202)
def analyze(
    payload: AnalysisCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Kicks off an asynchronous research gap discovery job.
    Accepts topic query and optional filters for publication years and source limits.
    """
    query = (payload.query or "").strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query must be a non-empty string.")
    if len(query) > MAX_QUERY_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"Query is too long (max {MAX_QUERY_LENGTH} characters).",
        )

    analysis_id = str(uuid.uuid4())
    analysis = Analysis(
        id=analysis_id,
        query=query,
        status="pending",
        stage="queued",
        created_at=datetime.utcnow(),
    )
    db.add(analysis)
    db.commit()
    db.refresh(analysis)

    background_tasks.add_task(
        run_analysis_task,
        analysis.id,
        analysis.query,
        payload.year_min,
        payload.year_max,
        payload.limit,
        payload.sources,
    )
    return analysis


@router.get("/{analysis_id}", response_model=AnalysisResponse)
def get_analysis_status(analysis_id: str, db: Session = Depends(get_db)):
    """Returns the current processing status and live stage of an analysis job."""
    analysis = db.query(Analysis).filter(Analysis.id == analysis_id).first()
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found.")
    return analysis


@router.get("/{analysis_id}/results", response_model=AnalysisResultsResponse)
def get_analysis_results(analysis_id: str, db: Session = Depends(get_db)):
    """
    Returns the comprehensive structured gap discovery results.
    Adheres strictly to the primary research-gap API response contract.
    """
    analysis = db.query(Analysis).filter(Analysis.id == analysis_id).first()
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found.")

    papers = db.query(Paper).filter(Paper.analysis_id == analysis_id).all()
    paper_map = {p.id: p for p in papers}

    years = [p.year for p in papers if p.year is not None]
    year_start = min(years) if years else None
    year_end = max(years) if years else None

    # Load persisted gaps from DB
    orm_gaps = db.query(ResearchGap).filter(ResearchGap.analysis_id == analysis_id).all()
    gaps_schema: List[ResearchGapSchema] = []

    for g in orm_gaps:
        # Group evidence by paper
        paper_ev_map: Dict[str, List[EvidencePassageSchema]] = defaultdict(list)
        for ev in g.evidence:
            paper_ev_map[ev.paper_id].append(
                EvidencePassageSchema(
                    text=ev.passage,
                    section=ev.section or "Limitations",
                    page=ev.page,
                )
            )

        supporting_papers: List[SupportingPaperSchema] = []
        for pid, passages in paper_ev_map.items():
            if pid in paper_map:
                p = paper_map[pid]
                supporting_papers.append(
                    SupportingPaperSchema(
                        paper_id=p.id,
                        title=p.title,
                        authors=[a.name for a in p.authors],
                        year=p.year,
                        venue=p.venue,
                        doi=p.doi,
                        url=p.url or p.external_id,
                        pdf_url=p.pdf_url,
                        citation_count=p.citation_count,
                        evidence_passages=passages,
                    )
                )

        gaps_schema.append(
            ResearchGapSchema(
                gap_id=g.id,
                title=g.title,
                statement=g.statement,
                why_it_matters=g.why_it_matters,
                category=g.category,
                origin=g.origin,
                evidence_strength=g.evidence_strength,
                supporting_paper_count=len(supporting_papers) or g.supporting_paper_count,
                supporting_papers=supporting_papers,
                counterevidence=[],
                reasoning=g.reasoning,
            )
        )

    # If completed but DB gaps were empty (e.g. before schema update), synthesize on the fly
    if analysis.status == "completed" and not gaps_schema and papers:
        schemas = [
            PaperSchema(
                id=p.id,
                title=p.title,
                authors=[a.name for a in p.authors],
                year=p.year,
                venue=p.venue,
                abstract=p.abstract,
                citation_count=p.citation_count,
                open_access_status=p.open_access_status,
                external_id=p.external_id,
                doi=p.doi,
                url=p.url or p.external_id,
                pdf_url=p.pdf_url,
                source=p.source,
            )
            for p in papers
        ]
        gaps_schema = gap_engine.synthesize_corpus_gaps(schemas, query=analysis.query)

    # Categories breakdown
    cat_counts: Dict[str, int] = defaultdict(int)
    for g in gaps_schema:
        cat_counts[g.category] += 1

    return AnalysisResultsResponse(
        search_id=analysis.id,
        query=analysis.query,
        status=analysis.status,
        stage=analysis.stage,
        corpus=CorpusStatsSchema(
            papers_retrieved=analysis.papers_retrieved or len(papers),
            papers_analysed=analysis.papers_analysed or len(papers),
            publication_year_range=YearRangeSchema(start=year_start, end=year_end),
            categories_breakdown=dict(cat_counts),
        ),
        gaps=gaps_schema,
        warnings=[analysis.error_message] if analysis.error_message and analysis.status != "completed" else [],
    )


@router.get("/{analysis_id}/gaps")
def get_analysis_gaps(analysis_id: str, db: Session = Depends(get_db)):
    """Returns research gaps for the analysis session."""
    results = get_analysis_results(analysis_id=analysis_id, db=db)
    return results.gaps


@router.get("/{analysis_id}/papers", response_model=List[PaperSchema])
def get_analysis_papers(analysis_id: str, db: Session = Depends(get_db)):
    """Returns all retrieved and analyzed scholarly papers with full verified links and metadata."""
    papers = db.query(Paper).filter(Paper.analysis_id == analysis_id).all()
    return [
        PaperSchema(
            id=p.id,
            title=p.title,
            authors=[a.name for a in p.authors],
            year=p.year,
            venue=p.venue,
            abstract=p.abstract,
            citation_count=p.citation_count,
            open_access_status=p.open_access_status,
            external_id=p.external_id,
            doi=p.doi,
            url=p.url or p.external_id,
            pdf_url=p.pdf_url,
            source=p.source,
        )
        for p in papers
    ]


@router.post("/{analysis_id}/retry", response_model=AnalysisResponse, status_code=202)
def retry_analysis(
    analysis_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Retries a failed or stalled analysis job."""
    analysis = db.query(Analysis).filter(Analysis.id == analysis_id).first()
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found.")
    if analysis.status in {"pending", "running"}:
        raise HTTPException(status_code=409, detail="Analysis is already running.")

    analysis.status = "pending"
    analysis.stage = "queued"
    analysis.error_message = None
    analysis.failed_stage = None
    db.commit()
    db.refresh(analysis)
    background_tasks.add_task(run_analysis_task, analysis.id, analysis.query)
    return analysis


@router.get("/{analysis_id}/topics")
def get_analysis_topics(analysis_id: str, db: Session = Depends(get_db)):
    """Returns thematic clusters from the corpus."""
    analysis = db.query(Analysis).filter(Analysis.id == analysis_id).first()
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found.")
    if analysis.status not in {"completed", "no_results"}:
        raise HTTPException(status_code=400, detail="Analysis is not yet complete.")

    papers = db.query(Paper).filter(Paper.analysis_id == analysis_id).all()
    return analytics.extract_topics(papers)


@router.get("/debug/search")
def debug_search(q: str):
    """Probes OpenAlex endpoint directly for network validation."""
    try:
        response = requests.get(
            "https://api.openalex.org/works",
            params={"search": q, "per-page": 5, "sort": "relevance_score:desc"},
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()
        return {"results": len(data.get("results", [])), "meta": data.get("meta")}
    except Exception as exc:
        return {"error": str(exc)}
