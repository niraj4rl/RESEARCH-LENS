"""
Full-Text Fetching and Section Extraction Module for ResearchLens.
Provides safe, rate-limited, and graceful extraction of scholarly sections
from legitimate open-access PDFs and HTML sources.
"""

from __future__ import annotations

import io
import re
import logging
from typing import Optional, Dict, Tuple, List
import requests
from schemas import PaperSchema

logger = logging.getLogger(__name__)

# Request settings
MAX_PDF_SIZE_BYTES = 15 * 1024 * 1024  # 15 MB limit
REQUEST_TIMEOUT_SECONDS = 7
USER_AGENT = "ResearchLens/2.0 (Scholarly Gap Discovery; mailto:researchlens-dev@example.com)"

# Priority sections to look for in full text
SECTION_HEADERS = {
    "limitations": re.compile(r"^(?:\d+[\.\s]+)?(?:limitations?|threats\s+to\s+validity|weaknesses|delimitations)", re.IGNORECASE),
    "future_work": re.compile(r"^(?:\d+[\.\s]+)?(?:future\s+(?:work|research|directions?)|next\s+steps|open\s+(?:problems|questions))", re.IGNORECASE),
    "discussion": re.compile(r"^(?:\d+[\.\s]+)?(?:discussion|general\s+discussion)", re.IGNORECASE),
    "evaluation": re.compile(r"^(?:\d+[\.\s]+)?(?:experiments?|evaluation|empirical\s+results?|experimental\s+(?:setup|results?))", re.IGNORECASE),
    "methodology": re.compile(r"^(?:\d+[\.\s]+)?(?:methodology|proposed\s+(?:method|framework|approach)|methods?|model\s+formulation)", re.IGNORECASE),
    "dataset": re.compile(r"^(?:\d+[\.\s]+)?(?:datasets?|benchmarks?|data\s+collection|corpus)", re.IGNORECASE),
    "conclusion": re.compile(r"^(?:\d+[\.\s]+)?(?:conclusions?|concluding\s+remarks)", re.IGNORECASE),
}


def is_open_access_accessible(paper: PaperSchema) -> bool:
    """Checks if paper has a plausible open-access PDF link."""
    if not paper.pdf_url:
        return False
    url = paper.pdf_url.lower()
    return url.startswith("http://") or url.startswith("https://")


def fetch_pdf_text_safe(pdf_url: str) -> Optional[str]:
    """
    Safely downloads and extracts text from an open-access PDF.
    Enforces timeout, size limits, and graceful error handling.
    """
    try:
        headers = {"User-Agent": USER_AGENT}
        response = requests.get(pdf_url, headers=headers, timeout=REQUEST_TIMEOUT_SECONDS, stream=True)
        if response.status_code != 200:
            return None

        content_length = response.headers.get("Content-Length")
        if content_length and int(content_length) > MAX_PDF_SIZE_BYTES:
            logger.info("PDF exceeds size limit (%s bytes): %s", content_length, pdf_url)
            return None

        # Read streamed content up to max size
        chunks = []
        downloaded = 0
        for chunk in response.iter_content(chunk_size=65536):
            downloaded += len(chunk)
            if downloaded > MAX_PDF_SIZE_BYTES:
                logger.info("Streamed PDF exceeded size limit: %s", pdf_url)
                return None
            chunks.append(chunk)

        pdf_bytes = b"".join(chunks)

        # Parse with pypdf
        import pypdf
        reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
        num_pages = len(reader.pages)
        if num_pages == 0:
            return None

        # Extract text from pages (focus on first 2 and last 5 pages where intro/limitations/discussion appear)
        extracted_pages = []
        pages_to_check = set(range(min(2, num_pages))).union(range(max(0, num_pages - 5), num_pages))
        for page_idx in sorted(pages_to_check):
            try:
                page_text = reader.pages[page_idx].extract_text()
                if page_text:
                    extracted_pages.append(f"--- PAGE {page_idx + 1} ---\n{page_text}")
            except Exception:
                continue

        return "\n\n".join(extracted_pages) if extracted_pages else None

    except Exception as exc:
        logger.debug("Safe PDF extraction skipped for %s: %s", pdf_url, exc)
        return None


def segment_full_text_sections(text: str) -> Dict[str, str]:
    """
    Segments full text into relevant scholarly sections:
    limitations, future_work, discussion, evaluation, methodology, dataset.
    """
    if not text:
        return {}

    lines = [line.strip() for line in text.split("\n") if line.strip()]
    sections: Dict[str, List[str]] = {k: [] for k in SECTION_HEADERS}
    current_section: Optional[str] = None

    for line in lines:
        matched_sec = None
        for sec_name, pattern in SECTION_HEADERS.items():
            if len(line) < 60 and pattern.match(line):
                matched_sec = sec_name
                break

        if matched_sec:
            current_section = matched_sec
        elif current_section:
            sections[current_section].append(line)

    return {
        sec_name: "\n".join(lines_list)
        for sec_name, lines_list in sections.items()
        if lines_list
    }


def extract_paper_full_text_evidence(paper: PaperSchema) -> Tuple[Optional[Dict[str, str]], str]:
    """
    Attempts full-text extraction if an open-access PDF URL is present.
    Returns (section_dict, source_scope).
    source_scope is 'full_text' if full text was parsed, otherwise 'abstract_only'.
    """
    if not is_open_access_accessible(paper):
        return None, "abstract_only"

    pdf_text = fetch_pdf_text_safe(paper.pdf_url)
    if not pdf_text or len(pdf_text) < 300:
        return None, "abstract_only"

    sections = segment_full_text_sections(pdf_text)
    # If we found at least one recognized section, return full_text
    if sections:
        return sections, "full_text"

    # Even if sections weren't explicitly segmented, full text was parsed
    return {"body": pdf_text}, "full_text"
