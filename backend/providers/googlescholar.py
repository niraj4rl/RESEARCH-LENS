import logging
import os
import uuid
from typing import List
from .base import ScholarProvider
from schemas import PaperSchema

logger = logging.getLogger(__name__)


class GoogleScholarProvider(ScholarProvider):
    """Best-effort Google Scholar adapter using the scholarly client.

    Google Scholar has no public official search API and may require a proxy
    when it presents a CAPTCHA. ``SCHOLARLY_PROXY`` can configure one.
    """

    def search_papers(self, query: str, limit: int = 20) -> List[PaperSchema]:
        try:
            from scholarly import scholarly
        except ImportError as exc:
            logger.error("Google Scholar dependency is unavailable: %s", exc)
            return []

        proxy = os.getenv("SCHOLARLY_PROXY")
        if not proxy:
            # Google Scholar blocks direct non-proxied automated scraping with CAPTCHA
            logger.info("Google Scholar proxy (SCHOLARLY_PROXY) not configured; skipping provider to avoid latency.")
            return []

        try:
            scholarly.set_proxy(proxy)
        except Exception:
            logger.exception("Could not configure SCHOLARLY_PROXY")
            return []

        papers: List[PaperSchema] = []
        try:
            for index, result in enumerate(scholarly.search_pubs(query)):
                if index >= limit:
                    break
                publication = result.get("bib", {})
                authors = publication.get("author", [])
                if isinstance(authors, str):
                    authors = [authors]
                raw_year = publication.get("pub_year")
                try:
                    year = int(raw_year) if raw_year is not None else None
                except (TypeError, ValueError):
                    year = None
                pub_url = result.get("pub_url")
                eprint_url = result.get("eprint")
                papers.append(PaperSchema(
                    id=str(uuid.uuid4()),
                    external_id=pub_url or eprint_url or str(uuid.uuid4()),
                    title=publication.get("title") or "Untitled",
                    authors=[str(author) for author in authors],
                    year=year,
                    venue=publication.get("venue"),
                    abstract=publication.get("abstract", ""),
                    citation_count=int(result.get("num_citations", 0) or 0),
                    open_access_status="oa" if eprint_url else None,
                    doi=None,
                    url=pub_url,
                    pdf_url=eprint_url,
                    source="Google Scholar",
                ))
        except Exception as exc:
            logger.warning("Google Scholar unavailable (CAPTCHA/proxy/network): %s", exc)
        return papers
