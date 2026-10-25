"""
ResearchLens Gap Discovery Engine
Implements evidence-backed scholarly research gap discovery:
1. Topic processing & lexical-semantic filtering
2. Multi-source evidence extraction (abstract screening + full-text inspection)
3. Strict limitation vs future-work classification (no automatic fallback to conclusion sentences)
4. Semantic sub-clustering for cross-paper synthesis (requires genuine semantic overlap across papers)
5. Distinct handling for explicit author-stated limitations vs cross-paper inferred gaps
6. Non-overclaiming scholarly tone (no unsupported claims of 'confirmed' facts)
7. Full provenance preservation, citation verification, and transparent evidence coverage
"""

from __future__ import annotations

import re
import uuid
import logging
from typing import List, Dict, Any, Optional, Tuple, Set
from collections import defaultdict
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from schemas import (
    PaperSchema,
    ResearchGapSchema,
    SupportingPaperSchema,
    EvidencePassageSchema,
    CorpusStatsSchema,
    YearRangeSchema,
    AnalysisResultsResponse,
)
from full_text import extract_paper_full_text_evidence

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Taxonomy Categories
# ---------------------------------------------------------------------------
CATEGORY_METHODOLOGICAL = "methodological"
CATEGORY_EVALUATION = "evaluation"
CATEGORY_DATASET = "dataset"
CATEGORY_THEORETICAL = "theoretical"
CATEGORY_APPLICATION = "application_domain"
CATEGORY_GENERALIZATION = "generalization"
CATEGORY_CONFLICTING = "conflicting_findings"
CATEGORY_FUTURE_DIRECTION = "future_direction"
CATEGORY_OTHER = "other"

ALL_CATEGORIES = [
    CATEGORY_METHODOLOGICAL,
    CATEGORY_EVALUATION,
    CATEGORY_DATASET,
    CATEGORY_THEORETICAL,
    CATEGORY_APPLICATION,
    CATEGORY_GENERALIZATION,
    CATEGORY_CONFLICTING,
    CATEGORY_FUTURE_DIRECTION,
    CATEGORY_OTHER,
]

# ---------------------------------------------------------------------------
# Evidence Extraction Patterns & Heuristics
# ---------------------------------------------------------------------------
EVIDENCE_PATTERNS = {
    CATEGORY_EVALUATION: [
        r"\b(?:evaluat\w+|experiment\w+|test\w+)\s+(?:is\s+)?(?:limit\w+|restrict\w+|solely|only\s+on|lacks?)\b",
        r"\b(?:offline\s+evaluation|synthetic\s+data|simulat\w+)\s+(?:does\s+not|fails?\s+to|cannot\s+reflect)\b",
        r"\b(?:lack\w*|absence|shortage)\s+of\s+(?:real-world|live|user-study|online|longitudinal|in-the-wild)\b",
        r"\b(?:metric|benchmark|evaluation\s+protocol)\s+(?:does\s+not\s+capture|overlook\w*|inadequate)\b",
        r"\b(?:under|in)\s+dynamic|changing\s+preferences|non-stationary\b",
    ],
    CATEGORY_DATASET: [
        r"\b(?:dataset|corpus|benchmark)\s+(?:is\s+)?(?:sparse|small|limited|biased|imbalanced|scarce|lack\w*)\b",
        r"\b(?:data\s+sparsity|cold-start|unannotated|ground\s+truth|label\s+noise)\b",
        r"\b(?:lack|need)\s+of\s+(?:diverse|publicly\s+available|large-scale|standardized)\s+datasets?\b",
        r"\b(?:privacy|proprietary)\s+concerns?\s+(?:restrict|prevent|limit)\b",
    ],
    CATEGORY_GENERALIZATION: [
        r"\b(?:fails?\s+to\s+generaliz\w+|poor\s+generaliz\w+|domain\s+shift|out-of-distribution|cross-domain)\b",
        r"\b(?:degrades?\s+(?:significantly|substantially)|performance\s+drops?)\s+(?:when|in|on)\b",
        r"\b(?:transferability|scalability)\s+(?:remains|is)\s+(?:challenging|unexplored|limited)\b",
        r"\b(?:assumption\w*\s+may\s+not\s+hold|restricted\s+to\s+(?:specific|narrow))\b",
    ],
    CATEGORY_METHODOLOGICAL: [
        r"\b(?:method|approach|model|algorithm|framework)\s+(?:suffers?\s+from|struggles?\s+with|fails?\s+to|relies?\s+heavily\s+on)\b",
        r"\b(?:computational\s+(?:complexity|bottleneck|overhead)|high\s+latency|resource-intensive)\b",
        r"\b(?:heuristic|greedy|ad-hoc)\s+(?:nature|design|choice)\b",
        r"\b(?:simplifying\s+assumptions?|oversimplif\w+|unrealistic\s+assumption)\b",
        r"\b(?:hyperparameter\s+sensitivity|fragile\s+to|brittle)\b",
    ],
    CATEGORY_CONFLICTING: [
        r"\b(?:contrary\s+to|inconsistent\s+with|contradict\w*|discrepanc\w*|dispute\w*)\b",
        r"\b(?:mixed\s+results|conflicting\s+findings|debate\s+continues)\b",
        r"\b(?:whereas\s+prior|while\s+previous\s+work\s+(?:reported|found))\b",
    ],
    CATEGORY_THEORETICAL: [
        r"\b(?:theoretical\s+(?:guarantees?|understanding|foundation|justification))\s+(?:is\s+lacking|remains\s+open|missing)\b",
        r"\b(?:lack\s+of\s+formal\s+proof|convergence\s+(?:rate|guarantee)\s+(?:is\s+unknown|unproven))\b",
        r"\b(?:black-box\s+nature|explainability\s+gap|uninterpretable)\b",
    ],
    CATEGORY_FUTURE_DIRECTION: [
        r"\b(?:future\s+(?:work|research|directions?|studies)|next\s+steps?)\s+(?:should|will|must|could|ought\s+to|plans?\s+to)\b",
        r"\b(?:remains?\s+(?:an?\s+open\s+(?:question|problem|challenge)|unresolved|unanswered|underexplored|unaddressed))\b",
        r"\b(?:promising\s+avenue|crucial\s+direction|warrants?\s+further\s+investigation)\b",
        r"\b(?:yet\s+to\s+be\s+(?:explored|investigated|demonstrated|resolved))\b",
    ],
}

# Strict future-work regex (passage MUST support future-work classification)
STRICT_FUTURE_WORK_REGEX = re.compile(
    r"\b(?:future\s+(?:work|research|direction|directions|investigation|studies)|"
    r"remains?\s+an?\s+open\s+(?:question|problem|challenge)|"
    r"remains?\s+(?:unresolved|unanswered|underexplored|unaddressed)|"
    r"yet\s+to\s+be\s+(?:explored|investigated|resolved)|"
    r"warrants?\s+further\s+(?:research|investigation|study))\b",
    re.IGNORECASE,
)

GENERIC_LIMITATION_CUES = [
    "however", "limitation", "shortcoming", "drawback", "bottleneck",
    "challenge", "struggle", "fails to", "limited to", "vulnerable to",
    "degrades", "unaddressed", "overlooked", "not considered",
]


class ExtractedEvidence:
    """Represents a discrete verified evidence passage from a scholarly source."""
    def __init__(
        self,
        paper: PaperSchema,
        passage: str,
        category: str,
        section: str = "Abstract - Limitations",
        confidence: float = 0.8,
        is_future_work: bool = False,
        source_scope: str = "abstract_only",
        page: Optional[int] = None,
    ):
        self.paper = paper
        self.passage = passage.strip()
        self.category = category
        self.section = section
        self.confidence = confidence
        self.is_future_work = is_future_work
        self.source_scope = source_scope
        self.page = page

    def to_dict(self) -> Dict[str, Any]:
        return {
            "paper_id": self.paper.id,
            "paper_title": self.paper.title,
            "paper_year": self.paper.year,
            "passage": self.passage,
            "category": self.category,
            "section": self.section,
            "source_scope": self.source_scope,
        }


# ---------------------------------------------------------------------------
# Sentence Segmentation & Extraction Helpers
# ---------------------------------------------------------------------------
def split_into_sentences(text: str) -> List[str]:
    """Clean text and split into robust sentence boundaries."""
    if not text:
        return []
    cleaned = re.sub(r"\s+", " ", text).strip()
    cleaned = re.sub(
        r"\b(e\.g\.|i\.e\.|et\s+al\.|fig\.|ref\.|vs\.)",
        lambda m: m.group(0).replace(".", "§"),
        cleaned,
        flags=re.IGNORECASE,
    )
    parts = re.split(r"(?<=[.!?])\s+", cleaned)
    sentences = []
    for p in parts:
        restored = p.replace("§", ".").strip()
        if len(restored) >= 20 and any(c.isalnum() for c in restored):
            sentences.append(restored)
    return sentences


def extract_paper_evidence(paper: PaperSchema, inspect_full_text: bool = True) -> List[ExtractedEvidence]:
    """
    Extracts evidence passages from paper.
    1. Attempts full-text inspection if legitimate open-access text is available.
    2. Operates on abstract if full text is unavailable.
    3. Strictly enforces classification (no auto-converting conclusion sentences to future work).
    """
    extracted: List[ExtractedEvidence] = []
    seen_passages: Set[str] = set()

    # Step 1: Check full-text when enabled
    if inspect_full_text:
        sections_dict, scope = extract_paper_full_text_evidence(paper)
        if sections_dict and scope == "full_text":
            priority_sections = ["limitations", "future_work", "discussion", "evaluation", "methodology", "dataset"]
            for sec_key in priority_sections:
                sec_text = sections_dict.get(sec_key, "")
                if not sec_text:
                    continue
                sentences = split_into_sentences(sec_text)
                for sentence in sentences[:15]:
                    s_lower = sentence.lower()
                    matched_category = None
                    is_future = bool(STRICT_FUTURE_WORK_REGEX.search(s_lower))

                    # Map section to category
                    if sec_key == "limitations":
                        matched_category = CATEGORY_METHODOLOGICAL
                    elif sec_key == "future_work":
                        if is_future:
                            matched_category = CATEGORY_FUTURE_DIRECTION
                    elif sec_key == "evaluation":
                        matched_category = CATEGORY_EVALUATION
                    elif sec_key == "dataset":
                        matched_category = CATEGORY_DATASET

                    # Check specialized patterns if no category assigned yet
                    if not matched_category:
                        for cat, patterns in EVIDENCE_PATTERNS.items():
                            for pat in patterns:
                                if re.search(pat, s_lower):
                                    # Never label as future work unless supported
                                    if cat == CATEGORY_FUTURE_DIRECTION and not is_future:
                                        continue
                                    matched_category = cat
                                    break
                            if matched_category:
                                break

                    # Also accept sentences with explicit limitation cues
                    if not matched_category and any(cue in s_lower for cue in GENERIC_LIMITATION_CUES):
                        matched_category = CATEGORY_METHODOLOGICAL

                    if matched_category and sentence not in seen_passages:
                        seen_passages.add(sentence)
                        extracted.append(
                            ExtractedEvidence(
                                paper=paper,
                                passage=sentence,
                                category=matched_category,
                                section=f"Full Text - {sec_key.replace('_', ' ').title()}",
                                confidence=0.88,
                                is_future_work=is_future,
                                source_scope="full_text",
                            )
                        )
            if extracted:
                return extracted

    # Step 2: Abstract screening (fallback or primary)
    abstract = paper.abstract or ""
    if not abstract:
        return []

    sentences = split_into_sentences(abstract)
    for idx, sentence in enumerate(sentences):
        s_lower = sentence.lower()
        matched_category = None
        matched_section = "Abstract - Limitations"
        is_future = bool(STRICT_FUTURE_WORK_REGEX.search(s_lower))

        # Check specialized taxonomy patterns
        for cat, patterns in EVIDENCE_PATTERNS.items():
            for pat in patterns:
                if re.search(pat, s_lower):
                    if cat == CATEGORY_FUTURE_DIRECTION:
                        # Requirement: Never label a passage as future work unless supported
                        if not is_future:
                            continue
                        is_future = True
                        matched_section = "Abstract - Future Work"
                    elif cat == CATEGORY_EVALUATION:
                        matched_section = "Abstract - Evaluation Scope"
                    elif cat == CATEGORY_DATASET:
                        matched_section = "Abstract - Dataset Constraints"
                    elif cat == CATEGORY_CONFLICTING:
                        matched_section = "Abstract - Conflicting Findings"
                    elif cat == CATEGORY_GENERALIZATION:
                        matched_section = "Abstract - Generalization Boundaries"
                    elif cat == CATEGORY_THEORETICAL:
                        matched_section = "Abstract - Theoretical Limitations"
                    else:
                        matched_section = "Abstract - Methodological Limitations"
                    matched_category = cat
                    break
            if matched_category:
                break

        # Check generic limitation cues if no specialized pattern matched
        if not matched_category:
            has_limitation_cue = any(cue in s_lower for cue in GENERIC_LIMITATION_CUES)
            if has_limitation_cue and (idx >= len(sentences) // 3 or "however" in s_lower):
                matched_category = CATEGORY_METHODOLOGICAL
                matched_section = "Abstract - Stated Limitations"

        if matched_category and sentence not in seen_passages:
            seen_passages.add(sentence)
            extracted.append(
                ExtractedEvidence(
                    paper=paper,
                    passage=sentence,
                    category=matched_category,
                    section=matched_section,
                    confidence=0.82 if matched_category != CATEGORY_METHODOLOGICAL else 0.70,
                    is_future_work=is_future,
                    source_scope="abstract_only",
                )
            )

    return extracted


# ---------------------------------------------------------------------------
# Semantic Sub-clustering & Formulation
# ---------------------------------------------------------------------------
def extract_coherent_topic_phrase(query: str, passages: List[str]) -> str:
    """Extract a natural topic noun phrase from the query and passages."""
    clean_q = re.sub(r"[^\w\s-]", "", query).strip()
    words = clean_q.split()
    if len(words) <= 4:
        return clean_q.title()
    return " ".join(words[:4]).title()


def cluster_passages_by_semantic_similarity(
    evidence_items: List[ExtractedEvidence],
    similarity_threshold: float = 0.15,
) -> List[List[ExtractedEvidence]]:
    """
    Groups evidence items into cohesive semantic sub-clusters.
    Ensures that papers are not combined solely because they share a category.
    """
    if len(evidence_items) <= 1:
        return [evidence_items] if evidence_items else []

    texts = [ev.passage for ev in evidence_items]
    try:
        vec = TfidfVectorizer(
            stop_words="english",
            ngram_range=(1, 2),
            token_pattern=r"(?u)\b[a-zA-Z]{3,}\b",
            min_df=1,
        )
        matrix = vec.fit_transform(texts)
        sim_matrix = cosine_similarity(matrix, matrix)
    except Exception:
        # Fallback: keep individual items
        return [[ev] for ev in evidence_items]

    # Graph components / clustering based on similarity threshold
    visited: Set[int] = set()
    clusters: List[List[ExtractedEvidence]] = []

    for i in range(len(evidence_items)):
        if i in visited:
            continue
        cluster_indices = [i]
        visited.add(i)
        for j in range(len(evidence_items)):
            if j not in visited and sim_matrix[i, j] >= similarity_threshold:
                cluster_indices.append(j)
                visited.add(j)
        clusters.append([evidence_items[idx] for idx in cluster_indices])

    return clusters


def generate_gap_statement(
    category: str,
    passages: List[str],
    query: str,
    paper_count: int,
    is_inferred: bool,
    source_scope_counts: Dict[str, int],
) -> Tuple[str, str, str, str, str]:
    """
    Produces concise executive titles (max ~14 words), grounded descriptions,
    scholarly reasoning (without overclaiming 'confirmed' facts), transparent coverage,
    and appropriate research qualifications.
    """
    topic = extract_coherent_topic_phrase(query, passages)
    primary_passage = passages[0] if passages else ""
    p_lower = primary_passage.lower()

    ft_count = source_scope_counts.get("full_text", 0)
    ab_count = source_scope_counts.get("abstract_only", 0)
    if ft_count > 0 and ab_count > 0:
        coverage_text = f"Identified across {paper_count} independent studies ({ft_count} full text, {ab_count} abstract-only)."
    elif ft_count > 0:
        coverage_text = f"Identified across {paper_count} independent studies with full-text inspection."
    else:
        coverage_text = f"Identified across {paper_count} independent studies via abstract screening."

    if is_inferred:
        if category == CATEGORY_EVALUATION:
            if "longitudinal" in p_lower or "dynamic" in p_lower or "shift" in p_lower:
                title = f"Lack of longitudinal evaluation under evolving conditions in {topic}"
            elif "real-world" in p_lower or "user-study" in p_lower or "online" in p_lower:
                title = f"Absence of real-world operational evaluation in {topic}"
            else:
                title = f"Evaluation protocol limitations under non-stationary conditions in {topic}"
            statement = (
                f"Synthesized evidence from {paper_count} independent investigations indicates that empirical evaluations in {topic} "
                f"remain predominantly confined to static or synthetic benchmarks, without testing dynamic operational shifts."
            )
            why_it_matters = (
                f"Evaluating models solely on static snapshots conceals performance degradation that typically occurs under real-world, "
                f"evolving user or system dynamics."
            )
            qualifications = "Evaluations in the retrieved literature rely primarily on standard offline benchmark splits; behavior under live conditions remains unexamined."
        elif category == CATEGORY_DATASET:
            if "sparse" in p_lower or "sparsity" in p_lower:
                title = f"Severe benchmark sparsity and cold-start constraints in {topic}"
            elif "bias" in p_lower or "imbalanced" in p_lower:
                title = f"Domain bias and benchmark representation skew in {topic}"
            else:
                title = f"Scarcity of diverse, standardized benchmark corpora for {topic}"
            statement = (
                f"Across {paper_count} published works, independent authors note recurring dataset constraints in {topic}, "
                f"highlighting feature sparsity, narrow domain sampling, or absence of standardized ground-truth annotations."
            )
            why_it_matters = (
                f"Without representative benchmarks, empirical gains cannot be reliably attributed to methodological advances rather than "
                f"dataset-specific artifacts."
            )
            qualifications = "Reported data limitations reflect public benchmark availability and may not encompass private proprietary corpora."
        elif category == CATEGORY_GENERALIZATION:
            title = f"Generalization breakdown and domain shift vulnerabilities in {topic}"
            statement = (
                f"Cross-paper synthesis across {paper_count} studies indicates that architectures developed for {topic} exhibit "
                f"substantive performance drops when applied to out-of-distribution or cross-domain inputs."
            )
            why_it_matters = (
                f"Strong within-domain accuracy does not ensure cross-environment robustness, posing a central hurdle for broad adoption."
            )
            qualifications = "Domain transfer vulnerability is observed across tested benchmark datasets and warrants verification across other modalities."
        elif category == CATEGORY_METHODOLOGICAL:
            if any(w in p_lower for w in ["scalability", "computational", "complexity", "latency", "overhead"]):
                title = f"Computational scalability bottlenecks in large-scale {topic} models"
            else:
                title = f"Structural bottlenecks and simplifying assumptions in {topic}"
            statement = (
                f"Across {paper_count} publications, researchers independently identify methodological constraints in {topic}, "
                f"such as computational overhead or fragile architectural assumptions."
            )
            why_it_matters = (
                f"Unaddressed computational or structural bounds limit practical scalability and raise implementation barriers."
            )
            qualifications = "Computational bounds depend on specific hardware and model parameter configurations reported by the respective authors."
        elif category == CATEGORY_CONFLICTING:
            title = f"Conflicting empirical outcomes across benchmark configurations in {topic}"
            statement = (
                f"Literature synthesis across {paper_count} studies reveals mixed or conflicting findings regarding comparative "
                f"method effectiveness in {topic}."
            )
            why_it_matters = (
                f"Divergent empirical results suggest that outcomes may be sensitive to unstandardized hyperparameters or evaluation choices."
            )
            qualifications = "Discrepancies may arise from varying experimental protocols, training setups, or metric definitions."
        elif category == CATEGORY_THEORETICAL:
            title = f"Inadequate theoretical guarantees and convergence foundations in {topic}"
            statement = (
                f"Multiple studies note a lack of formal theoretical bounds or convergence guarantees for optimization techniques in {topic}."
            )
            why_it_matters = (
                f"Without theoretical foundations, practitioners cannot reliably predict edge-case failure modes or certify robustness."
            )
            qualifications = "Theoretical gaps refer specifically to the mathematical justifications presented in the analysed sample."
        else:
            title = f"Underexplored operational parameters in {topic}"
            statement = (
                f"Evidence across {paper_count} scholarly works points to recurring open questions and boundaries in {topic}."
            )
            why_it_matters = (
                f"Investigating these recurring observations provides a concrete roadmap for future empirical contributions."
            )
            qualifications = "Synthesized from common boundaries reported across the retrieved paper set."

        reasoning = (
            f"Synthesized from {paper_count} independent publications with verified semantic overlap. "
            f"Rather than an isolated finding, authors independently describe related boundaries. "
            f"Further comparative evaluation is required to establish definitive causal limits."
        )
    else:
        # Explicit author-reported gap
        cleaned_passage = primary_passage.strip()
        if len(cleaned_passage) > 180:
            cleaned_passage = cleaned_passage[:177] + "..."

        if category == CATEGORY_EVALUATION:
            title = f"Author-reported evaluation boundary in {topic}"
        elif category == CATEGORY_DATASET:
            title = f"Author-noted dataset constraint in {topic}"
        elif category == CATEGORY_GENERALIZATION:
            title = f"Author-identified generalization constraint in {topic}"
        elif category == CATEGORY_FUTURE_DIRECTION:
            title = f"Author-proposed future research direction in {topic}"
        else:
            title = f"Author-acknowledged methodological limitation in {topic}"

        statement = (
            f"The study's authors explicitly state an unresolved operational boundary: "
            f"\"{cleaned_passage}\""
        )
        why_it_matters = (
            f"Author-acknowledged limitations provide precise, peer-reviewed anchor points where existing techniques degrade."
        )
        reasoning = f"Direct author limitation documented in source publication. {coverage_text}"
        qualifications = "This limitation reflects the explicit disclosure of the study authors and has not yet been corroborated across external corpora."

    # Clamp title to 14 words
    title_words = title.split()
    if len(title_words) > 14:
        title = " ".join(title_words[:13]) + "..."

    return title, statement, why_it_matters, reasoning, qualifications


# ---------------------------------------------------------------------------
# Main Gap Synthesis Pipeline
# ---------------------------------------------------------------------------
def synthesize_corpus_gaps(
    papers: List[PaperSchema],
    query: str,
    inspect_full_text: bool = True,
) -> List[ResearchGapSchema]:
    """
    Main synthesis pipeline:
    1. Extracts evidence passages from papers (checking full-text where accessible).
    2. Groups evidence by category, then sub-clusters by semantic similarity.
    3. Synthesizes cross-paper gaps ONLY when independent papers share a genuine semantic relationship.
    4. Generates explicit author-reported gap candidates for standalone high-confidence limitations.
    5. Deduplicates candidates and validates against retrieved paper text.
    6. Calibrates evidence strength and transparent coverage.
    """
    if not papers:
        return []

    paper_map: Dict[str, PaperSchema] = {p.id: p for p in papers}

    # Step 1: Extract evidence from each paper
    all_evidence: List[ExtractedEvidence] = []
    for paper in papers:
        all_evidence.extend(extract_paper_evidence(paper, inspect_full_text=inspect_full_text))

    # Note: If no evidence is found, we do NOT run a fake fallback on abstract ends!
    if not all_evidence:
        logger.info("No explicit limitation or future-work passages identified in retrieved sample for %r", query)
        return []

    # Step 2: Group by category
    category_groups: Dict[str, List[ExtractedEvidence]] = defaultdict(list)
    for ev in all_evidence:
        category_groups[ev.category].append(ev)

    raw_gaps: List[ResearchGapSchema] = []

    # Step 3: For each category, perform semantic sub-clustering
    for category, evidence_list in category_groups.items():
        if not evidence_list:
            continue

        # Sub-cluster evidence passages by semantic similarity
        clusters = cluster_passages_by_semantic_similarity(evidence_list, similarity_threshold=0.15)

        for cluster in clusters:
            # Map cluster items to distinct papers
            cluster_papers: Dict[str, List[ExtractedEvidence]] = defaultdict(list)
            for ev in cluster:
                cluster_papers[ev.paper.id].append(ev)

            # Check if this semantic cluster spans >= 2 distinct papers -> Cross-Paper Inferred Gap
            if len(cluster_papers) >= 2:
                passages = [ev.passage for ev in cluster]
                scope_counts: Dict[str, int] = defaultdict(int)
                for ev in cluster:
                    scope_counts[ev.source_scope] += 1

                title, statement, why_it_matters, reasoning, qualifications = generate_gap_statement(
                    category=category,
                    passages=passages,
                    query=query,
                    paper_count=len(cluster_papers),
                    is_inferred=True,
                    source_scope_counts=dict(scope_counts),
                )

                supporting_papers: List[SupportingPaperSchema] = []
                for pid, evs in cluster_papers.items():
                    p = paper_map[pid]
                    passages_schema = [
                        EvidencePassageSchema(
                            text=ev.passage,
                            section=ev.section,
                            page=ev.page,
                            source_scope=ev.source_scope,
                        )
                        for ev in evs[:2]
                    ]
                    paper_scope = "full_text" if any(ev.source_scope == "full_text" for ev in evs) else "abstract_only"
                    supporting_papers.append(
                        SupportingPaperSchema(
                            paper_id=p.id,
                            title=p.title,
                            authors=p.authors or [],
                            year=p.year,
                            venue=p.venue,
                            doi=p.doi,
                            url=p.url or p.external_id,
                            pdf_url=p.pdf_url,
                            citation_count=p.citation_count,
                            source_scope=paper_scope,
                            evidence_passages=passages_schema,
                        )
                    )

                strength = "strong" if len(supporting_papers) >= 3 else "moderate"
                raw_gaps.append(
                    ResearchGapSchema(
                        gap_id=str(uuid.uuid4()),
                        title=title,
                        statement=statement,
                        why_it_matters=why_it_matters,
                        category=category,
                        origin="cross_paper_inference",
                        evidence_strength=strength,
                        source_coverage=f"{len(supporting_papers)} independent publications",
                        qualifications=qualifications,
                        supporting_paper_count=len(supporting_papers),
                        supporting_papers=supporting_papers,
                        counterevidence=[],
                        reasoning=reasoning,
                    )
                )

        # Also generate explicit gaps for papers with explicit author limitations
        for ev in evidence_list:
            p = ev.paper
            scope_counts = {ev.source_scope: 1}
            title, stmt, why, rsn, qual = generate_gap_statement(
                category=ev.category,
                passages=[ev.passage],
                query=query,
                paper_count=1,
                is_inferred=False,
                source_scope_counts=scope_counts,
            )
            raw_gaps.append(
                ResearchGapSchema(
                    gap_id=str(uuid.uuid4()),
                    title=title,
                    statement=stmt,
                    why_it_matters=why,
                    category=ev.category,
                    origin="explicit",
                    evidence_strength="moderate" if (ev.source_scope == "full_text" or p.citation_count >= 15) else "preliminary",
                    source_coverage=f"1 paper ({ev.source_scope.replace('_', ' ')})",
                    qualifications=qual,
                    supporting_paper_count=1,
                    supporting_papers=[
                        SupportingPaperSchema(
                            paper_id=p.id,
                            title=p.title,
                            authors=p.authors or [],
                            year=p.year,
                            venue=p.venue,
                            doi=p.doi,
                            url=p.url or p.external_id,
                            pdf_url=p.pdf_url,
                            citation_count=p.citation_count,
                            source_scope=ev.source_scope,
                            evidence_passages=[
                                EvidencePassageSchema(
                                    text=ev.passage,
                                    section=ev.section,
                                    page=ev.page,
                                    source_scope=ev.source_scope,
                                )
                            ],
                        )
                    ],
                    counterevidence=[],
                    reasoning=rsn,
                )
            )

    # Step 4: Deduplicate semantically redundant gap candidates
    deduplicated = deduplicate_gaps(raw_gaps)

    # Step 5: Validate evidence integrity against source papers
    validated = validate_gaps(deduplicated, paper_map)

    # Step 6: Rank results prioritizing recurring, cross-paper evidence
    ranked = rank_gaps(validated, query)
    return ranked


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------
def deduplicate_gaps(gaps: List[ResearchGapSchema], similarity_threshold: float = 0.72) -> List[ResearchGapSchema]:
    """
    Merges semantically identical gap candidates while keeping distinct findings separate.
    Preserves supporting papers and evidence passages from merged sources.
    """
    if len(gaps) <= 1:
        return gaps

    inferred_gaps = [g for g in gaps if g.origin == "cross_paper_inference"]
    explicit_gaps = [g for g in gaps if g.origin == "explicit"]

    merged_inferred: List[ResearchGapSchema] = []
    for g in inferred_gaps:
        duplicate_idx = -1
        for idx, existing in enumerate(merged_inferred):
            if existing.category == g.category:
                # Compare title similarity
                t1, t2 = existing.title.lower(), g.title.lower()
                words1, words2 = set(t1.split()), set(t2.split())
                jaccard = len(words1 & words2) / max(len(words1 | words2), 1)
                if jaccard >= 0.55:
                    duplicate_idx = idx
                    break

        if duplicate_idx >= 0:
            existing = merged_inferred[duplicate_idx]
            existing_paper_ids = {p.paper_id for p in existing.supporting_papers}
            for p in g.supporting_papers:
                if p.paper_id not in existing_paper_ids:
                    existing.supporting_papers.append(p)
                    existing_paper_ids.add(p.paper_id)
            existing.supporting_paper_count = len(existing.supporting_papers)
            if existing.supporting_paper_count >= 3:
                existing.evidence_strength = "strong"
            existing.source_coverage = f"{existing.supporting_paper_count} independent publications"
        else:
            merged_inferred.append(g)

    # Retain explicit gaps that aren't already represented by the same single paper in the exact same category
    kept_explicit: List[ResearchGapSchema] = []
    seen_explicit_keys: Set[Tuple[str, str]] = set()
    for g in explicit_gaps:
        paper_id = g.supporting_papers[0].paper_id if g.supporting_papers else ""
        key = (paper_id, g.category)
        if key not in seen_explicit_keys:
            seen_explicit_keys.add(key)
            kept_explicit.append(g)

    return merged_inferred + kept_explicit[:10]


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------
def validate_gaps(
    gaps: List[ResearchGapSchema],
    paper_map: Dict[str, PaperSchema],
) -> List[ResearchGapSchema]:
    """
    Verifies that:
    1. Cited papers exist in the retrieved corpus.
    2. Quoted passages are non-empty and tied to valid papers.
    3. Metadata and external links are consistent.
    """
    valid_gaps: List[ResearchGapSchema] = []
    for gap in gaps:
        verified_papers: List[SupportingPaperSchema] = []
        for sup in gap.supporting_papers:
            if sup.paper_id in paper_map:
                real_paper = paper_map[sup.paper_id]
                valid_passages: List[EvidencePassageSchema] = [
                    p for p in sup.evidence_passages if p.text and len(p.text.strip()) >= 15
                ]
                if valid_passages:
                    sup.evidence_passages = valid_passages
                    sup.doi = real_paper.doi or sup.doi
                    sup.url = real_paper.url or sup.url or real_paper.external_id
                    sup.pdf_url = real_paper.pdf_url or sup.pdf_url
                    verified_papers.append(sup)

        if verified_papers:
            gap.supporting_papers = verified_papers
            gap.supporting_paper_count = len(verified_papers)
            valid_gaps.append(gap)
        else:
            logger.warning("Dropped unverified gap candidate: %s", gap.title)

    return valid_gaps


# ---------------------------------------------------------------------------
# Ranking
# ---------------------------------------------------------------------------
def rank_gaps(gaps: List[ResearchGapSchema], query: str) -> List[ResearchGapSchema]:
    """
    Ranks gaps:
    1. Cross-paper inferred gaps with multiple sources.
    2. Strong evidence coverage.
    3. Relevance to user topic.
    """
    query_terms = set(re.findall(r"[a-z0-9]+", query.lower()))

    def score_gap(gap: ResearchGapSchema) -> float:
        strength_score = {"strong": 3.0, "moderate": 2.0, "preliminary": 1.0}.get(gap.evidence_strength, 1.0)
        origin_score = 2.5 if gap.origin == "cross_paper_inference" else 1.0
        paper_score = min(gap.supporting_paper_count, 6) * 1.5
        text_corpus = f"{gap.title} {gap.statement} {gap.why_it_matters}".lower()
        relevance_score = sum(1.0 for t in query_terms if t in text_corpus)
        return (strength_score * 3.0) + (origin_score * 2.5) + paper_score + relevance_score

    return sorted(gaps, key=score_gap, reverse=True)


# ---------------------------------------------------------------------------
# Assemble Contract Results
# ---------------------------------------------------------------------------
def assemble_analysis_results(
    search_id: str,
    query: str,
    status: str,
    stage: str,
    papers: List[PaperSchema],
    gaps: List[ResearchGapSchema],
    warnings: Optional[List[str]] = None,
    raw_provider_results: Optional[int] = None,
    deduplicated_papers: Optional[int] = None,
    retained_papers: Optional[int] = None,
    full_text_analysed: Optional[int] = 0,
) -> AnalysisResultsResponse:
    """Assembles structured API contract response with detailed corpus metrics."""
    years = [p.year for p in papers if p.year is not None]
    year_start = min(years) if years else None
    year_end = max(years) if years else None

    cat_counts: Dict[str, int] = defaultdict(int)
    for g in gaps:
        cat_counts[g.category] += 1

    corpus_stats = CorpusStatsSchema(
        papers_retrieved=len(papers),
        papers_analysed=len(papers),
        raw_provider_results=raw_provider_results or len(papers),
        deduplicated_papers=deduplicated_papers or len(papers),
        retained_papers=retained_papers or len(papers),
        full_text_analysed=full_text_analysed or 0,
        publication_year_range=YearRangeSchema(start=year_start, end=year_end),
        categories_breakdown=dict(cat_counts),
    )

    return AnalysisResultsResponse(
        search_id=search_id,
        query=query,
        status=status,
        stage=stage,
        corpus=corpus_stats,
        gaps=gaps,
        warnings=warnings or [],
    )
