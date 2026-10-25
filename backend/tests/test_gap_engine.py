import pytest
import uuid
from schemas import PaperSchema, EvidencePassageSchema, ResearchGapSchema, SupportingPaperSchema
from gap_engine import (
    extract_paper_evidence,
    synthesize_corpus_gaps,
    deduplicate_gaps,
    validate_gaps,
    rank_gaps,
    cluster_passages_by_semantic_similarity,
    CATEGORY_EVALUATION,
    CATEGORY_DATASET,
    CATEGORY_METHODOLOGICAL,
    CATEGORY_GENERALIZATION,
    CATEGORY_FUTURE_DIRECTION,
    CATEGORY_CONFLICTING,
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
    evidence = extract_paper_evidence(paper, inspect_full_text=False)
    assert len(evidence) >= 1
    categories = [e.category for e in evidence]
    assert CATEGORY_EVALUATION in categories or CATEGORY_DATASET in categories
    for e in evidence:
        assert len(e.passage) > 20
        assert e.paper.id == paper.id
        assert e.source_scope == "abstract_only"


# 1. Regression test: Abstracts with no explicit limitation
def test_abstract_with_no_explicit_limitation():
    positive_paper = PaperSchema(
        id=str(uuid.uuid4()),
        external_id="ext-pos-1",
        title="High Accuracy Neural Text Classification on Standard Corpora",
        authors=["John Doe"],
        year=2023,
        venue="ACL",
        abstract=(
            "We introduce a novel transformer architecture for text classification. "
            "Our model achieves state-of-the-art accuracy across five standard benchmarks. "
            "Extensive experiments confirm superior convergence speed and accuracy. "
            "In conclusion, our method proves highly effective for deep textual representation."
        ),
        citation_count=12,
    )
    # Must NOT invent future-work or limitation evidence from the concluding sentences
    evidence = extract_paper_evidence(positive_paper, inspect_full_text=False)
    assert len(evidence) == 0, "Engine must not treat pure positive conclusion sentences as limitations or future work"

    gaps = synthesize_corpus_gaps([positive_paper], query="neural text classification", inspect_full_text=False)
    assert len(gaps) == 0, "No gaps should be generated when papers contain zero reported limitations"


# 2. Regression test: Explicit author-stated limitations
def test_explicit_author_stated_limitation():
    paper = PaperSchema(
        id=str(uuid.uuid4()),
        external_id="ext-explicit-1",
        title="Empirical Analysis of Model Compression",
        authors=["Jane Smith"],
        year=2023,
        abstract="However, our compression algorithm suffers from significant accuracy degradation on long context windows.",
        citation_count=20,
    )
    evidence = extract_paper_evidence(paper, inspect_full_text=False)
    assert len(evidence) >= 1
    assert "accuracy degradation on long context windows" in evidence[0].passage

    gaps = synthesize_corpus_gaps([paper], query="model compression", inspect_full_text=False)
    assert len(gaps) >= 1
    explicit_gaps = [g for g in gaps if g.origin == "explicit"]
    assert len(explicit_gaps) >= 1
    assert "accuracy degradation" in explicit_gaps[0].statement


# 3. Regression test: Multiple unrelated limitations in the same category
def test_multiple_unrelated_limitations_in_same_category():
    # Two papers both categorized as 'methodological', but completely different topics
    paper_a = PaperSchema(
        id="paper-a",
        external_id="ext-a",
        title="FPGA Hardware Acceleration of Neural Networks",
        authors=["Engineer A"],
        year=2023,
        abstract="However, our hardware design suffers from extreme thermal dissipation overhead and high latency under peak clock speeds.",
        citation_count=5,
    )
    paper_b = PaperSchema(
        id="paper-b",
        external_id="ext-b",
        title="Differential Privacy in Graph Convolutional Networks",
        authors=["Theorist B"],
        year=2023,
        abstract="However, our privacy mechanism relies on unrealistic simplifying assumptions regarding gradient bounded sensitivity.",
        citation_count=5,
    )
    # The two passages should NOT be grouped into the same semantic cluster
    ev_a = extract_paper_evidence(paper_a, inspect_full_text=False)
    ev_b = extract_paper_evidence(paper_b, inspect_full_text=False)
    assert len(ev_a) == 1
    assert len(ev_b) == 1
    assert ev_a[0].category == CATEGORY_METHODOLOGICAL
    assert ev_b[0].category == CATEGORY_METHODOLOGICAL

    clusters = cluster_passages_by_semantic_similarity(ev_a + ev_b, similarity_threshold=0.25)
    # Because FPGA thermal dissipation and differential privacy sensitivity are unrelated, they must be in separate clusters
    assert len(clusters) == 2, "Unrelated limitations in the same broad category must not be clustered together"

    gaps = synthesize_corpus_gaps([paper_a, paper_b], query="machine learning", inspect_full_text=False)
    inferred_gaps = [g for g in gaps if g.origin == "cross_paper_inference"]
    assert len(inferred_gaps) == 0, "Must not generate a cross-paper inferred gap between completely unrelated limitations"


# 4. Regression test: Genuine recurring limitations across independent papers
def test_genuine_recurring_limitations_across_independent_papers():
    paper_1 = PaperSchema(
        id="paper-rec-1",
        external_id="ext-rec-1",
        title="Cold-Start Modeling in E-Commerce Recommenders",
        authors=["Author One"],
        year=2023,
        abstract="However, severe dataset sparsity in sparse user interaction benchmarks causes catastrophic cold-start recommendation failure.",
        citation_count=30,
    )
    paper_2 = PaperSchema(
        id="paper-rec-2",
        external_id="ext-rec-2",
        title="Graph Embeddings for Cold-Start Items",
        authors=["Author Two"],
        year=2024,
        abstract="However, extreme data sparsity in sparse item interactions severely limits cold-start recommendation accuracy.",
        citation_count=20,
    )
    gaps = synthesize_corpus_gaps([paper_1, paper_2], query="cold-start recommendation", inspect_full_text=False)
    inferred = [g for g in gaps if g.origin == "cross_paper_inference"]
    assert len(inferred) >= 1, "Must synthesize cross-paper inferred gap when papers share genuine recurring limitations"
    assert inferred[0].supporting_paper_count == 2
    assert "sparsity" in inferred[0].title.lower() or "cold-start" in inferred[0].title.lower()


# 5. Regression test: Contradictory evidence
def test_contradictory_evidence():
    paper = PaperSchema(
        id="paper-conf-1",
        external_id="ext-conf-1",
        title="Re-evaluating Collaborative Filtering vs Deep Recommenders",
        authors=["Scholar C"],
        year=2023,
        abstract="While previous work reported that deep architectures outperform simple heuristics, our mixed results and conflicting findings show contrary results under standardized metrics.",
        citation_count=50,
    )
    evidence = extract_paper_evidence(paper, inspect_full_text=False)
    assert len(evidence) >= 1
    assert any(e.category == CATEGORY_CONFLICTING for e in evidence)


# 6. Regression test: Missing full text graceful fallback
def test_missing_full_text_graceful_fallback():
    paper_no_pdf = PaperSchema(
        id="paper-no-pdf",
        external_id="ext-no-pdf",
        title="Closed Access Scholarly Study",
        authors=["Scholar D"],
        year=2022,
        abstract="However, the evaluation protocol lacks real-world user-study validation under non-stationary traffic.",
        citation_count=10,
        pdf_url=None,  # No PDF available
    )
    evidence = extract_paper_evidence(paper_no_pdf, inspect_full_text=True)
    assert len(evidence) >= 1
    assert evidence[0].source_scope == "abstract_only"
    assert "Abstract" in evidence[0].section


# 7. Regression test: Invalid or mismatched source passages rejected
def test_invalid_or_mismatched_source_passages():
    paper = PaperSchema(
        id="valid-paper-id",
        external_id="ext-valid",
        title="Valid Paper",
        authors=["Scholar E"],
        year=2023,
        abstract="However, our model struggles with computational complexity when scaling.",
        citation_count=10,
    )
    paper_map = {paper.id: paper}

    # Gap with mismatched paper ID
    mismatched_gap = ResearchGapSchema(
        gap_id="gap-mismatch",
        title="Mismatched Gap",
        statement="Some statement",
        why_it_matters="Some why",
        category="methodological",
        origin="explicit",
        evidence_strength="preliminary",
        supporting_paper_count=1,
        supporting_papers=[
            SupportingPaperSchema(
                paper_id="ghost-id-does-not-exist",
                title="Ghost Paper",
                authors=[],
                evidence_passages=[EvidencePassageSchema(text="A long valid text passage that is not in the corpus")],
            )
        ],
    )
    validated = validate_gaps([mismatched_gap], paper_map)
    assert len(validated) == 0, "Gaps with mismatched or missing paper IDs must be rejected"


# 8. Regression test: Duplicate gap candidates deduplication
def test_duplicate_gap_candidates_deduplication():
    paper = PaperSchema(
        id="p1",
        external_id="ext-1",
        title="Cold-Start Recommenders",
        authors=["Author A"],
        year=2023,
        abstract="However, severe dataset sparsity in public benchmarks prevents accurate cold-start modeling.",
        citation_count=15,
    )
    gap1 = ResearchGapSchema(
        gap_id="gap-1",
        title="Severe Benchmark Sparsity In Cold-Start Recommenders",
        statement="Statement 1",
        why_it_matters="Why 1",
        category="dataset",
        origin="cross_paper_inference",
        evidence_strength="moderate",
        supporting_paper_count=1,
        supporting_papers=[
            SupportingPaperSchema(
                paper_id="p1",
                title="Cold-Start Recommenders",
                evidence_passages=[EvidencePassageSchema(text="However, severe dataset sparsity in public benchmarks prevents accurate cold-start modeling.")],
            )
        ],
    )
    gap2 = ResearchGapSchema(
        gap_id="gap-2",
        title="Severe Benchmark Sparsity in Cold-Start Recommenders",  # Duplicate title
        statement="Statement 2",
        why_it_matters="Why 2",
        category="dataset",
        origin="cross_paper_inference",
        evidence_strength="moderate",
        supporting_paper_count=1,
        supporting_papers=[
            SupportingPaperSchema(
                paper_id="p1",
                title="Cold-Start Recommenders",
                evidence_passages=[EvidencePassageSchema(text="However, severe dataset sparsity in public benchmarks prevents accurate cold-start modeling.")],
            )
        ],
    )
    deduped = deduplicate_gaps([gap1, gap2])
    assert len(deduped) == 1, "Duplicate gap candidates must be merged cleanly"
