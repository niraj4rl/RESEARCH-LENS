# ResearchLens — Evidence-Backed Scholarly Research-Gap Discovery System

ResearchLens is an AI-assisted scholarly research-gap discovery platform. Given a research domain or query (e.g. *"Recommender systems for cold-start users"*), the system retrieves peer-reviewed papers from multiple scholarly sources, extracts empirical limitations and future research cues, performs cross-paper synthesis, and surfaces evidence-backed research gaps with verified citation provenance.

---

## Core Product Architecture

ResearchLens replaces generic AI summaries and disconnected analytics dashboards with a focused research-gap discovery workflow:

```
[ Researcher Query ]
         │
         ▼
[ Stage 1: Topic Processing ] ── Query normalization, typo correction, optional year/source filters
         │
         ▼
[ Stage 2: Scholarly Retrieval ] ── Multi-provider concurrent fetch (OpenAlex, arXiv, Semantic Scholar, Google Scholar)
         │
         ▼
[ Stage 3: Evidence Extraction ] ── Extract limitations, future directions, benchmark constraints, and assumptions
         │
         ▼
[ Stage 4: Cross-Paper Synthesis ] ── Formulate recurring inferred gaps (multi-paper) vs author-reported explicit boundaries
         │
         ▼
[ Stage 5: Gap Deduplication ] ── Cluster semantically related candidates and aggregate citation evidence
         │
         ▼
[ Stage 6: Evidence Validation ] ── Verify that every cited paper, DOI, URL, and quoted passage exists in the corpus
         │
         ▼
[ Stage 7: Strength Calibration ] ── Calibrate evidence (Strong, Moderate, Preliminary) & rank by recurrence and relevance
         │
         ▼
[ Primary Frontend Canvas ] ── Responsive research-gap cards + slide-over evidence inspection panel + literature drawer
```

---

## Gap Classification Taxonomy

Every discovered research gap is classified along two primary dimensions:

### 1. Gap Category
- **Methodological Gap**: Algorithmic bottlenecks, computational scalability constraints, or heuristic approximations.
- **Evaluation Gap**: Offline-only evaluation, absence of longitudinal or dynamic user studies, or metric mismatch.
- **Dataset Gap**: Benchmark sparsity, domain bias, lack of public benchmarks, or annotation limitations.
- **Generalization Gap**: Performance degradation under domain shift, out-of-distribution transfer, or cross-domain failures.
- **Theoretical Gap**: Missing formal convergence guarantees or unproven theoretical foundations.
- **Application / Domain Gap**: Untested operational domains or restricted deployment settings.
- **Conflicting Findings**: Empirical discrepancies or diverging outcomes across independent published studies.
- **Future Research Direction**: Explicit unresolved directions called out by study authors.

### 2. Gap Origin & Evidence Calibration
- **Origin**:
  - `cross_paper_inference`: Synthesized from recurring constraints observed across 2 or more independent papers.
  - `explicit`: Directly identified by the authors of a published study in their limitations/future work sections.
- **Evidence Strength**:
  - `strong`: 3+ supporting papers, or multiple independent sources confirming the constraint.
  - `moderate`: 2 supporting papers or 1 highly cited author limitation with clear operational boundaries.
  - `preliminary`: Single emerging study or early research direction with narrow corpus coverage.

---

## Structured API Contract

### `GET /api/research/{analysis_id}/results`

Returns the comprehensive research discovery payload:

```json
{
  "search_id": "8fa21e64-325b-402a-9cb0-bf55d5bb6b42",
  "query": "recommender systems for cold-start users",
  "status": "completed",
  "stage": "completed",
  "corpus": {
    "papers_retrieved": 25,
    "papers_analysed": 25,
    "publication_year_range": {
      "start": 2012,
      "end": 2026
    },
    "categories_breakdown": {
      "evaluation": 2,
      "dataset": 3,
      "methodological": 4
    }
  },
  "gaps": [
    {
      "gap_id": "c1f7b889-436f-42a9-b36e-d922bc305372",
      "title": "Limited Real-World & Longitudinal Evaluation in Cold-Start Recommenders",
      "statement": "Across 3 retrieved studies, existing literature reveals recurring constraints regarding static user profiles. While individual works propose distinct techniques, evidence indicates that evaluation under dynamic user preferences remains unexamined in live environments.",
      "why_it_matters": "When multiple independent works encounter similar limitations, it signals a systemic boundary in current methodology rather than an isolated shortcoming.",
      "category": "evaluation",
      "origin": "cross_paper_inference",
      "evidence_strength": "strong",
      "supporting_paper_count": 3,
      "supporting_papers": [
        {
          "paper_id": "d8201fa4-a4f6-41f2-bf6d-aefd83151b74",
          "title": "Performance Evaluation and Factor Analysis of Multimodal Recommender Systems",
          "authors": ["Author One", "Author Two"],
          "year": 2026,
          "venue": "KTCP",
          "doi": "10.5626/ktcp.2026.32.4.178",
          "url": "https://doi.org/10.5626/ktcp.2026.32.4.178",
          "pdf_url": null,
          "citation_count": 12,
          "evidence_passages": [
            {
              "text": "However, existing evaluation protocols rely on static benchmark snapshots...",
              "section": "Evaluation Limitations",
              "page": null
            }
          ]
        }
      ],
      "counterevidence": [],
      "reasoning": "Synthesized from 3 independent scholarly publications demonstrating analogous evaluation limitations."
    }
  ],
  "warnings": []
}
```

---

## Running Locally

### Prerequisites
- Python 3.10+
- Node.js 18+
- (Optional) Docker for PostgreSQL + pgvector. *If Docker is not installed or running, ResearchLens automatically falls back to an embedded zero-configuration SQLite database (`researchlens.db`).*

### Quick Start (Streamlit)

ResearchLens now runs as a single Streamlit application. Install the Python
dependencies and launch it with any **one** of the following commands:

**Option A (Command Prompt / Windows Explorer):**
```cmd
start.bat
```

**Option B (PowerShell):**
```powershell
.\start.ps1
```

**Option C (Cross-Platform Python):**
```bash
python run.py
```

**Option D (npm):**
```bash
npm start
```

If dependencies are not installed yet:

```bash
python -m pip install -r requirements.txt
```

On Windows, if multiple Python installations are present, use the same
interpreter for installation and launch:

```powershell
.\venv\Scripts\python.exe -m pip install -r requirements.txt
.\venv\Scripts\python.exe -m streamlit run streamlit_app.py
```

The pinned `starlette` version is required for compatibility with the
FastAPI-backed retrieval pipeline. Running `streamlit` directly from another
Python installation can load an incompatible global FastAPI/Starlette pair.

The app opens at `http://localhost:8501`. It initializes the existing database
automatically, retrieves papers from the selected scholarly sources, and runs
the evidence and gap synthesis pipeline in-process. The legacy FastAPI and
Next.js clients remain in the repository for API compatibility, but are no
longer required to use ResearchLens.

---

## Manual Step-by-Step Setup

### Legacy API Setup
```bash
cd backend
python -m venv venv

# Windows
.\venv\Scripts\activate

# Linux / macOS
source venv/bin/activate

pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### Frontend Setup
```bash
cd frontend
npm install
npm run dev
```

Visit `http://localhost:3000` to start discovering research gaps.

---

## Running Verification Tests

### Backend Unit & Integration Tests
```bash
cd backend
pytest tests/ -v
```

All 9 test suites verify:
- Health checks
- Query validation & length bounds
- Asynchronous analysis lifecycle
- Evidence extraction heuristics
- Cross-paper gap synthesis
- Evidence strength calibration
- Gap candidate deduplication
- Programmatic rejection of fabricated citations

### Frontend Type-Checking & Production Build
```bash
cd frontend
npm run type-check
npm run build
```
