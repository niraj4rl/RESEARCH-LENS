import requests
import uuid
import os
from typing import List
from .base import ScholarProvider, create_http_session
from schemas import PaperSchema

class OpenAlexProvider(ScholarProvider):
    BASE_URL = "https://api.openalex.org/works"

    def search_papers(self, query: str, limit: int = 100) -> List[PaperSchema]:
        params = {
            "search": query,
            "per-page": limit,
            # Fetch highly relevant and cited works
            "sort": "relevance_score:desc"
        }
        mailto = os.getenv("OPENALEX_MAILTO")
        if mailto:
            params["mailto"] = mailto
        
        try:
            response = create_http_session().get(self.BASE_URL, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as e:
            print(f"OpenAlex request failed after retries: {e}")
            return []
        
        results = data.get("results", [])
        
        papers = []
        for item in results:
            authors = [a.get("author", {}).get("display_name") for a in item.get("authorships", []) if a.get("author", {}).get("display_name")]
            abstract = self._reconstruct_abstract(item.get("abstract_inverted_index"))
            
            primary_loc = item.get("primary_location") or {}
            source_obj = primary_loc.get("source") or {}
            raw_doi = item.get("doi")
            doi_clean = raw_doi.replace("https://doi.org/", "") if raw_doi else None
            landing_url = primary_loc.get("landing_page_url") or raw_doi or item.get("id")
            
            # Use OA URL if available, else primary location
            oa = item.get("open_access", {})
            oa_status = oa.get("oa_status", "closed")
            pdf_url = oa.get("oa_url") or primary_loc.get("pdf_url")
            
            paper = PaperSchema(
                id=str(uuid.uuid4()),
                external_id=item.get("id") or str(uuid.uuid4()),
                title=item.get("title") or "Untitled",
                authors=authors,
                year=item.get("publication_year"),
                venue=source_obj.get("display_name") if source_obj else None,
                abstract=abstract,
                citation_count=item.get("cited_by_count", 0) or 0,
                open_access_status=oa_status,
                doi=doi_clean,
                url=landing_url,
                pdf_url=pdf_url,
                source="OpenAlex"
            )
            papers.append(paper)
            
        return papers

    def _reconstruct_abstract(self, inverted_index: dict) -> str:
        if not inverted_index or not isinstance(inverted_index, dict):
            return ""
        
        # Inverted index: {"Word": [0, 15], "Another": [1]}
        # Reconstruct string by placing words at indices
        word_index = []
        for word, indices in inverted_index.items():
            if isinstance(indices, list):
                for idx in indices:
                    word_index.append((idx, word))
                
        word_index.sort(key=lambda x: x[0])
        return " ".join([w[1] for w in word_index])
