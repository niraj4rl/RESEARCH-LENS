"""
Extraction module for ResearchLens.
Bridges to the 7-stage Gap Discovery Engine in gap_engine.py.
Preserves backwards compatibility for existing tests/callers while providing
rigorous evidence extraction and research-gap discovery.
"""

from typing import List, Dict, Any
from schemas import PaperSchema
from gap_engine import (
    extract_paper_evidence,
    synthesize_corpus_gaps,
    CATEGORY_METHODOLOGICAL,
    CATEGORY_FUTURE_DIRECTION,
    CATEGORY_EVALUATION,
    CATEGORY_DATASET,
)

def analyze_corpus_gaps(papers: List[Any], query: str = "") -> Dict[str, Any]:
    """
    Analyzes corpus papers to produce both structured research gaps and categorized evidence lists.
    Accepts ORM Paper objects or PaperSchema objects.
    """
    if not papers:
        return {
            "gaps": [],
            "limitations": [],
            "future_work": [],
            "methods": [],
            "datasets": [],
        }

    # Normalize to PaperSchema
    paper_schemas: List[PaperSchema] = []
    for p in papers:
        if isinstance(p, PaperSchema):
            paper_schemas.append(p)
        else:
            authors = [a.name if hasattr(a, "name") else str(a) for a in getattr(p, "authors", [])]
            paper_schemas.append(
                PaperSchema(
                    id=getattr(p, "id", ""),
                    external_id=getattr(p, "external_id", "") or getattr(p, "id", ""),
                    title=getattr(p, "title", "Untitled"),
                    authors=authors,
                    year=getattr(p, "year", None),
                    venue=getattr(p, "venue", None),
                    abstract=getattr(p, "abstract", "") or "",
                    citation_count=getattr(p, "citation_count", 0) or 0,
                    open_access_status=getattr(p, "open_access_status", None),
                    doi=getattr(p, "doi", None),
                    url=getattr(p, "url", None),
                    pdf_url=getattr(p, "pdf_url", None),
                    source=getattr(p, "source", None),
                )
            )

    # 1. Run synthesis
    synthesized_gaps = synthesize_corpus_gaps(paper_schemas, query=query or "Scholarly Topic")

    # 2. Extract legacy categorized evidence lists for backwards compatibility
    all_limitations = []
    all_future = []
    all_methods = []
    all_datasets = []

    for p in paper_schemas:
        evidence_list = extract_paper_evidence(p)
        for ev in evidence_list:
            item = {
                "text": ev.passage,
                "paper_id": p.id,
                "paper_title": p.title,
                "paper_url": p.url or p.external_id,
                "type": ev.category,
                "section": ev.section,
            }
            if ev.category in [CATEGORY_METHODOLOGICAL, CATEGORY_EVALUATION]:
                all_limitations.append(item)
            elif ev.category == CATEGORY_FUTURE_DIRECTION:
                all_future.append(item)
            elif ev.category == CATEGORY_DATASET:
                all_datasets.append(item)
            else:
                all_methods.append(item)

    return {
        "gaps": [g.model_dump() for g in synthesized_gaps],
        "limitations": all_limitations[:25],
        "future_work": all_future[:25],
        "methods": all_methods[:25],
        "datasets": all_datasets[:25],
    }
