"""Streamlit interface for ResearchLens.

The scholarly retrieval and evidence synthesis pipeline remains in ``backend``.
This module provides the interactive UI and runs that pipeline in-process so
ResearchLens can be deployed as a single Streamlit application.
"""

from __future__ import annotations

import json
import inspect
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

import streamlit as st

ROOT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


def _prepare_fastapi_compatibility() -> None:
    """Allow the legacy API module to load with newer global Starlette builds.

    Streamlit only reuses the API module's pipeline functions; it does not
    serve FastAPI routes. Newer Starlette versions removed the deprecated
    ``on_startup`` and ``on_shutdown`` Router arguments while FastAPI 0.111
    still passes them during APIRouter construction.
    """
    from starlette.routing import Router

    if "on_startup" in inspect.signature(Router.__init__).parameters:
        return

    original_init = Router.__init__

    def compatible_init(self: Any, *args: Any, **kwargs: Any) -> None:
        kwargs.pop("on_startup", None)
        kwargs.pop("on_shutdown", None)
        original_init(self, *args, **kwargs)

    Router.__init__ = compatible_init


_prepare_fastapi_compatibility()

from api.router import get_analysis_papers, get_analysis_results, run_analysis_task  # noqa: E402
from database import SessionLocal  # noqa: E402
from models import Analysis  # noqa: E402

MAX_QUERY_LENGTH = 500
SOURCE_OPTIONS = {
    "OpenAlex": "openalex",
    "arXiv": "arxiv",
    "Semantic Scholar": "semanticscholar",
    "Google Scholar": "googlescholar",
}
CATEGORY_NAMES = {
    "methodological": "Methodological",
    "evaluation": "Evaluation",
    "dataset": "Dataset",
    "generalization": "Generalization",
    "theoretical": "Theoretical",
    "application_domain": "Domain Application",
    "conflicting_findings": "Conflicting Findings",
    "future_direction": "Future Direction",
    "other": "Open Inquiry",
}

st.set_page_config(
    page_title="ResearchLens",
    page_icon="🔎",
    layout="wide",
    initial_sidebar_state="expanded",
)


def _new_analysis(query: str, year_min: int | None, limit: int, sources: list[str]) -> str:
    analysis_id = str(uuid.uuid4())
    db = SessionLocal()
    try:
        db.add(
            Analysis(
                id=analysis_id,
                query=query,
                status="pending",
                stage="queued",
                created_at=datetime.utcnow(),
            )
        )
        db.commit()
    finally:
        db.close()

    run_analysis_task(
        analysis_id,
        query,
        year_min=year_min,
        limit=limit,
        requested_sources=sources,
    )
    return analysis_id


def _load_results(analysis_id: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    db = SessionLocal()
    try:
        results = get_analysis_results(analysis_id, db)
        papers = get_analysis_papers(analysis_id, db)
        return results.model_dump(mode="json"), [
            paper.model_dump(mode="json") for paper in papers
        ]
    finally:
        db.close()


def _paper_link(paper: dict[str, Any]) -> str | None:
    doi = paper.get("doi")
    if doi:
        return f"https://doi.org/{doi}"
    return paper.get("url") or paper.get("pdf_url")


def _render_gap(gap: dict[str, Any], index: int) -> None:
    category = CATEGORY_NAMES.get(gap.get("category", ""), "Open Gap")
    strength = str(gap.get("evidence_strength", "preliminary")).title()
    origin = "Cross-paper inference" if gap.get("origin") == "cross_paper_inference" else "Author-reported"
    title = f"{index + 1:02d} · {gap.get('title', 'Research gap')}"

    with st.container(border=True):
        st.markdown(f"#### {title}")
        st.caption(
            f"{category}  ·  {strength} evidence  ·  {origin}  ·  "
            f"{gap.get('supporting_paper_count', 0)} supporting papers"
        )
        st.write(gap.get("statement", ""))
        if gap.get("why_it_matters"):
            st.markdown("**Why it matters**")
            st.write(gap["why_it_matters"])
        if gap.get("qualifications"):
            st.info(gap["qualifications"])

        with st.expander("Inspect evidence"):
            if gap.get("reasoning"):
                st.markdown("**Synthesis reasoning**")
                st.write(gap["reasoning"])
            papers = gap.get("supporting_papers", [])
            if not papers:
                st.caption("No supporting paper passages were persisted for this gap.")
            for paper in papers:
                link = _paper_link(paper)
                paper_title = paper.get("title", "Untitled paper")
                if link:
                    st.markdown(f"**[{paper_title}]({link})**")
                else:
                    st.markdown(f"**{paper_title}**")
                metadata = " · ".join(
                    str(value)
                    for value in (paper.get("venue"), paper.get("year"))
                    if value
                )
                if metadata:
                    st.caption(metadata)
                for passage in paper.get("evidence_passages", []):
                    section = passage.get("section") or "Evidence"
                    scope = passage.get("source_scope") or "abstract_only"
                    st.markdown(f"> **{section}** ({scope})  \n> {passage.get('text', '')}")


def _render_sidebar() -> tuple[str, int | None, int, list[str], str]:
    with st.sidebar:
        st.markdown("## ResearchLens")
        st.caption("Evidence-backed scholarly research-gap discovery")
        st.divider()
        st.markdown("### Analysis settings")
        year_filter = st.selectbox(
            "Publication window",
            ["All years", "Last 3 years", "Last 5 years"],
        )
        current_year = datetime.now().year
        year_min = {
            "Last 3 years": current_year - 3,
            "Last 5 years": current_year - 5,
        }.get(year_filter)
        limit = st.slider("Results per source", min_value=15, max_value=75, value=50, step=5)
        source_labels = st.multiselect(
            "Scholarly sources",
            list(SOURCE_OPTIONS),
            default=["OpenAlex", "arXiv", "Semantic Scholar"],
        )
        sources = [SOURCE_OPTIONS[label] for label in source_labels]
        st.divider()
        st.markdown("### About")
        st.caption(
            "ResearchLens retrieves scholarly metadata, extracts limitations and "
            "future directions, then validates gaps against cited evidence."
        )
        return year_filter, year_min, limit, sources, ", ".join(source_labels)


def main() -> None:
    _, year_min, limit, sources, _ = _render_sidebar()
    st.title("Discover what existing research has yet to answer.")
    st.write(
        "Synthesize unresolved limitations, evaluation boundaries, and conflicting "
        "findings across peer-reviewed literature."
    )

    with st.form("research_form"):
        query = st.text_input(
            "Research topic or scholarly question",
            placeholder="Try: cold-start recommendation under preference shifts",
            max_chars=MAX_QUERY_LENGTH,
        )
        submitted = st.form_submit_button("Analyze literature", type="primary", use_container_width=True)

    examples = [
        "Cold-start recommendation under preference shifts",
        "Explainable artificial intelligence in clinical oncology",
        "Multimodal misinformation detection benchmarks",
    ]
    st.caption("Try an example: " + " · ".join(examples))

    if submitted:
        normalized_query = query.strip()
        if not normalized_query:
            st.error("Please enter a research topic or scholarly question.")
        elif not sources:
            st.error("Select at least one scholarly source.")
        elif len(normalized_query) > MAX_QUERY_LENGTH:
            st.error(f"Topic query exceeds {MAX_QUERY_LENGTH} characters.")
        else:
            with st.spinner("Retrieving papers and synthesizing evidence…"):
                analysis_id = _new_analysis(normalized_query, year_min, limit, sources)
                results, papers = _load_results(analysis_id)
            st.session_state["analysis_id"] = analysis_id
            st.session_state["results"] = results
            st.session_state["papers"] = papers

    results = st.session_state.get("results")
    papers = st.session_state.get("papers", [])
    if not results:
        st.info("Enter a research topic above to begin a literature-gap analysis.")
        return

    if results["status"] == "failed":
        st.error("Analysis failed: " + "; ".join(results.get("warnings", [])))
        return

    corpus = results.get("corpus", {})
    st.divider()
    metric_columns = st.columns(4)
    metric_columns[0].metric("Papers retrieved", corpus.get("papers_retrieved", 0))
    metric_columns[1].metric("Papers analyzed", corpus.get("papers_analysed", 0))
    metric_columns[2].metric("Research gaps", len(results.get("gaps", [])))
    year_range = corpus.get("publication_year_range", {})
    metric_columns[3].metric(
        "Publication range",
        f"{year_range.get('start') or '—'}–{year_range.get('end') or '—'}",
    )

    tab_gaps, tab_papers, tab_export = st.tabs(["Research gaps", "Literature", "Export"])
    with tab_gaps:
        gaps = results.get("gaps", [])
        if not gaps:
            st.warning("No evidence-backed research gaps were identified for this corpus.")
        else:
            filter_columns = st.columns(4)
            search_text = filter_columns[0].text_input("Search gaps", placeholder="Title, statement, paper…")
            category = filter_columns[1].selectbox(
                "Category",
                ["All categories"] + sorted({CATEGORY_NAMES.get(g["category"], g["category"]) for g in gaps}),
            )
            strength = filter_columns[2].selectbox("Evidence strength", ["All", "Strong", "Moderate", "Preliminary"])
            origin = filter_columns[3].selectbox("Origin", ["All", "Cross-paper inference", "Author-reported"])

            filtered_gaps = []
            for gap in gaps:
                searchable = json.dumps(gap).lower()
                gap_category = CATEGORY_NAMES.get(gap.get("category", ""), gap.get("category", ""))
                gap_origin = "Cross-paper inference" if gap.get("origin") == "cross_paper_inference" else "Author-reported"
                if search_text.lower() not in searchable:
                    continue
                if category != "All categories" and gap_category != category:
                    continue
                if strength != "All" and str(gap.get("evidence_strength", "")).title() != strength:
                    continue
                if origin != "All" and gap_origin != origin:
                    continue
                filtered_gaps.append(gap)
            st.caption(f"Showing {len(filtered_gaps)} of {len(gaps)} gaps")
            for index, gap in enumerate(filtered_gaps):
                _render_gap(gap, index)

    with tab_papers:
        st.subheader("Retrieved literature")
        for paper in papers:
            link = _paper_link(paper)
            title = paper.get("title", "Untitled paper")
            if link:
                st.markdown(f"### [{title}]({link})")
            else:
                st.markdown(f"### {title}")
            authors = ", ".join(paper.get("authors", [])) or "Authors unavailable"
            st.caption(f"{authors} · {paper.get('year') or 'Year unavailable'} · {paper.get('source') or 'Unknown source'}")
            if paper.get("abstract"):
                with st.expander("Abstract"):
                    st.write(paper["abstract"])

    with tab_export:
        st.download_button(
            "Download analysis JSON",
            data=json.dumps({"results": results, "papers": papers}, indent=2),
            file_name=f"researchlens-{results['search_id']}.json",
            mime="application/json",
            use_container_width=True,
        )


if __name__ == "__main__":
    main()
