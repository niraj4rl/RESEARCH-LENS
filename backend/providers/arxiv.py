import requests
import uuid
from typing import List
import xml.etree.ElementTree as ET
from .base import ScholarProvider, create_http_session
from schemas import PaperSchema

class ArxivProvider(ScholarProvider):
    BASE_URL = "https://export.arxiv.org/api/query"

    def search_papers(self, query: str, limit: int = 50) -> List[PaperSchema]:
        params = {
            "search_query": f"all:{query}",
            "start": 0,
            "max_results": limit,
            "sortBy": "relevance",
            "sortOrder": "descending"
        }
        
        try:
            response = create_http_session().get(self.BASE_URL, params=params, timeout=20)
            response.raise_for_status()
        except requests.RequestException as exc:
            print(f"arXiv request failed after retries: {exc}")
            return []
            
        return self._parse_atom_xml(response.text)
        
    def _parse_atom_xml(self, xml_text: str) -> List[PaperSchema]:
        papers = []
        try:
            root = ET.fromstring(xml_text)
            # arXiv XML uses the Atom namespace
            ns = {'atom': 'http://www.w3.org/2005/Atom'}
            
            for entry in root.findall('atom:entry', ns):
                title = entry.find('atom:title', ns)
                title_text = title.text.strip().replace('\n', ' ') if title is not None else "Untitled"
                
                abstract = entry.find('atom:summary', ns)
                abstract_text = abstract.text.strip().replace('\n', ' ') if abstract is not None else ""
                
                published = entry.find('atom:published', ns)
                year = int(published.text[:4]) if published is not None else None
                
                authors = []
                for author in entry.findall('atom:author', ns):
                    name = author.find('atom:name', ns)
                    if name is not None:
                        authors.append(name.text)
                        
                id_tag = entry.find('atom:id', ns)
                external_id = id_tag.text.strip() if id_tag is not None and id_tag.text else ""
                
                # Check for DOI in arxiv namespace
                arxiv_ns = {'arxiv': 'http://arxiv.org/schemas/atom'}
                doi_tag = entry.find('arxiv:doi', arxiv_ns)
                doi = doi_tag.text.strip() if doi_tag is not None and doi_tag.text else None
                
                # Extract PDF link or construct from arXiv ID
                pdf_url = None
                for link in entry.findall('atom:link', ns):
                    if link.attrib.get('title') == 'pdf' or link.attrib.get('type') == 'application/pdf':
                        pdf_url = link.attrib.get('href')
                        break
                if not pdf_url and external_id:
                    pdf_url = external_id.replace('/abs/', '/pdf/')
                    if not pdf_url.endswith('.pdf'):
                        pdf_url += '.pdf'
                
                url = external_id
                if url.startswith("http://"):
                    url = "https://" + url[7:]
                if pdf_url and pdf_url.startswith("http://"):
                    pdf_url = "https://" + pdf_url[7:]
                
                papers.append(PaperSchema(
                    id=str(uuid.uuid4()),
                    external_id=external_id,
                    title=title_text,
                    authors=authors,
                    year=year,
                    venue="arXiv",
                    abstract=abstract_text,
                    citation_count=0, # arXiv API doesn't provide citation counts directly
                    open_access_status="oa", # arXiv is always open access
                    doi=doi,
                    url=url,
                    pdf_url=pdf_url,
                    source="arXiv"
                ))
        except ET.ParseError:
            pass
            
        return papers
