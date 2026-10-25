import requests
import uuid
from typing import List
from .base import ScholarProvider
from schemas import PaperSchema

class SemanticScholarProvider(ScholarProvider):
    BASE_URL = "https://api.semanticscholar.org/graph/v1/paper/search"

    def search_papers(self, query: str, limit: int = 50) -> List[PaperSchema]:
        params = {
            "query": query,
            "limit": limit,
            "fields": "title,authors,year,venue,abstract,citationCount,isOpenAccess,url,externalIds,openAccessPdf"
        }
        
        try:
            # S2 often rate limits heavily for free tiers, timeout handles blocking
            response = requests.get(self.BASE_URL, params=params, timeout=10)
            response.raise_for_status()
        except requests.RequestException:
            # Fallback gracefully if S2 rate limits us
            return []
            
        data = response.json()
        results = data.get("data", [])
        
        papers = []
        for item in results:
            authors = [a.get("name") for a in item.get("authors", []) if a.get("name")]
            
            paper_id = item.get("paperId")
            landing_url = item.get("url") or (f"https://www.semanticscholar.org/paper/{paper_id}" if paper_id else None)
            external_id = landing_url or str(uuid.uuid4())
            ext_ids = item.get("externalIds") or {}
            doi = ext_ids.get("DOI")
            oa_pdf = item.get("openAccessPdf") or {}
            pdf_url = oa_pdf.get("url")

            papers.append(PaperSchema(
                id=str(uuid.uuid4()),
                external_id=external_id,
                title=item.get("title") or "Untitled",
                authors=authors,
                year=item.get("year"),
                venue=item.get("venue"),
                abstract=item.get("abstract") or "",
                citation_count=item.get("citationCount", 0),
                open_access_status="oa" if item.get("isOpenAccess") else "closed",
                doi=doi,
                url=landing_url,
                pdf_url=pdf_url,
                source="Semantic Scholar"
            ))
            
        return papers
