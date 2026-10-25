import pytest
import uuid
from schemas import PaperSchema, EvidencePassageSchema
from gap_engine import (
    extract_paper_evidence,
    synthesize_corpus_gaps,
    deduplicate_gaps,
    validate_gaps,
    rank_gaps,
    CATEGORY_EVALUATION,
    CATEGORY_DATASET,
    CATEGORY_METHODOLOGICAL,
    CATEGORY_GENERALIZATION,
    CATEGORY_FUTURE_DIRECTION,
)

@pytest.fixture
def sample_papers():
    return [
        PaperSchema(
            id=str(uuid.uuid4()),
            external_id="https://openalex.org/W1",
            title="Cold-Start Recommendation Under Dynamic User Preferences",
            authors=["Alice Smith", "Bob Jones"],
            year=2023,
            venue="KDD",
            abstract=(
                "Cold-start recommender systems struggle to accurately model user preferences with minimal interactions. "
                "However, existing evaluation is limited to static user profiles and lacks real-world user-study validation. "
                "Furthermore, dataset sparsity in public benchmarks prevents rigorous assessment of sudden preference shifts."
            ),
            citation_count=45,
            doi="10.1145/1234567",
            url="https://doi.org/10.1145/1234567",
            pdf_url="https://arxiv.org/pdf/2301.00001.pdf",
            source="OpenAlex",
        ),
        PaperSchema(
            id=str(uuid.uuid4()),
            external_id="https://openalex.org/W2",
            title="Graph Neural Networks for Few-Shot Item Recommendation",
            authors=["Carol Danvers", "David Miller"],
            year=2024,
            venue="SIGIR",
            abstract=(
                "We propose a graph-based few-shot recommendation framework. "
                "While our approach achieves strong results on offline benchmarks, the evaluation does not reflect "
                "non-stationary user interactions in production environments. "
                "In addition, computational bottleneck remains an open challenge when scaling to millions of nodes."
            ),
            citation_count=18,
            doi="10.1145/7654321",
            url="https://doi.org/10.1145/7654321",
            pdf_url=None,
            source="OpenAlex",
        ),
        PaperSchema(
            id=str(uuid.uuid4()),
            external_id="https://arxiv.org/abs/2402.12345",
            title="Benchmarking Cold-Start Bias Across Diverse Domains",
            authors=["Elena Rostova"],
            year=2024,
            venue="arXiv",
            abstract=(
                "This study investigates dataset bias in recommender system benchmarks. "
                "We demonstrate that benchmark datasets are limited to narrow movie and e-commerce domains, "
                "and models fail to generalize when deployed under out-of-distribution domain shift."
            ),
            citation_count=5,
            doi=None,
            url="https://arxiv.org/abs/2402.12345",
            pdf_url="https://arxiv.org/pdf/2402.12345.pdf",
            source="arXiv",
        ),
    ]

def test_extract_paper_evidence(sample_papers):
    paper = sample_papers[0]
    evidence = extract_paper_evidence(paper)
    assert len(evidence) >= 1
    categories = [e.category for e in evidence]
    assert CATEGORY_EVALUATION in categories or CATEGORY_DATASET in categories
    for e in evidence:
        assert len(e.passage) > 20
        assert e.paper.id == paper.id

def test_cross_paper_synthesis(sample_papers):
    query = "recommender systems for cold-start users"
    gaps = synthesize_corpus_gaps(sample_papers, query=query)
    
    assert len(gaps) >= 1
    # Check that at least one cross-paper inferred gap was generated
    inferred = [g for g in gaps if g.origin == "cross_paper_inference"]
    assert len(inferred) >= 1
    
    # Check gap structure
    gap = inferred[0]
    assert gap.title
    assert gap.statement
    assert gap.why_it_matters
    assert gap.category in [CATEGORY_EVALUATION, CATEGORY_DATASET, CATEGORY_METHODOLOGICAL, CATEGORY_GENERALIZATION, CATEGORY_FUTURE_DIRECTION]
    assert gap.supporting_paper_count >= 2
    assert len(gap.supporting_papers) >= 2
    
    # Verify traceability: check that supporting papers have exact passages
    first_supporting = gap.supporting_papers[0]
    assert len(first_supporting.evidence_passages) >= 1
    assert len(first_supporting.evidence_passages[0].text) > 10

def test_evidence_strength_calibration(sample_papers):
    query = "recommender systems"
    gaps = synthesize_corpus_gaps(sample_papers, query=query)
    for g in gaps:
        if g.supporting_paper_count >= 3:
            assert g.evidence_strength == "strong"
        elif g.supporting_paper_count == 2:
            assert g.evidence_strength in ["moderate", "strong"]
        else:
            assert g.evidence_strength in ["preliminary", "moderate"]

def test_deduplicate_gaps(sample_papers):
    query = "recommender systems"
    gaps = synthesize_corpus_gaps(sample_papers, query=query)
    # Ensure there are no duplicate gap IDs
    gap_ids = [g.gap_id for g in gaps]
    assert len(gap_ids) == len(set(gap_ids))

def test_validation_rejects_hallucinated_papers():
    paper = PaperSchema(
        id="real-id-1",
        external_id="ext-1",
        title="Valid Paper",
        authors=["Author One"],
        year=2023,
        venue="Conference",
        abstract="However, the proposed method struggles with high computational complexity in production.",
        citation_count=10,
    )
    paper_map = {paper.id: paper}
    
    gaps = synthesize_corpus_gaps([paper], query="test")
    # Verify valid gaps exist
    assert len(gaps) >= 1
    
    # Manually tamper with a gap to reference a non-existent paper
    from schemas import ResearchGapSchema, SupportingPaperSchema
    fake_gap = ResearchGapSchema(
        gap_id="fake-id",
        title="Fabricated Gap",
        statement="Fabricated statement",
        why_it_matters="Does not matter",
        category="methodological",
        origin="explicit",
        evidence_strength="preliminary",
        supporting_paper_count=1,
        supporting_papers=[
            SupportingPaperSchema(
                paper_id="non-existent-id",
                title="Ghost Paper",
                authors=[],
                evidence_passages=[EvidencePassageSchema(text="Ghost passage with sufficient length")],
            )
        ],
    )
    
    validated = validate_gaps([fake_gap], paper_map)
    # The fake gap should be rejected because paper_id is not in paper_map
    assert len(validated) == 0
