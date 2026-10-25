"use client";

import { useEffect, useState, use, useMemo, useRef } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { motion, AnimatePresence } from "motion/react";
import { ThemeToggle } from "@/components/ThemeToggle";
import { EvidenceMeter } from "@/components/EvidenceMeter";
import { LoadingStepper } from "@/components/LoadingStepper";
import { ExportMenu } from "@/components/ExportMenu";
import { KeyboardShortcutsModal } from "@/components/KeyboardShortcutsModal";
import { GapCard } from "@/components/GapCard";

interface EvidencePassage {
  text: string;
  section?: string | null;
  page?: number | null;
  source_scope?: string | null;
}

interface SupportingPaper {
  paper_id: string;
  title: string;
  authors: string[];
  year: number | null;
  venue?: string | null;
  doi?: string | null;
  url?: string | null;
  pdf_url?: string | null;
  citation_count: number;
  source_scope?: string | null;
  evidence_passages: EvidencePassage[];
}

interface ResearchGap {
  gap_id: string;
  title: string;
  statement: string;
  why_it_matters: string;
  category: string;
  origin: "explicit" | "cross_paper_inference";
  evidence_strength: "strong" | "moderate" | "preliminary";
  source_coverage?: string | null;
  qualifications?: string | null;
  supporting_paper_count: number;
  supporting_papers: SupportingPaper[];
  counterevidence: string[];
  reasoning?: string | null;
}

interface CorpusStats {
  papers_retrieved: number;
  papers_analysed: number;
  raw_provider_results?: number;
  deduplicated_papers?: number;
  retained_papers?: number;
  full_text_analysed?: number;
  publication_year_range: {
    start: number | null;
    end: number | null;
  };
  categories_breakdown?: Record<string, number>;
}

interface AnalysisResults {
  search_id: string;
  query: string;
  status: "pending" | "running" | "completed" | "failed" | "no_results";
  stage?: string | null;
  corpus: CorpusStats;
  gaps: ResearchGap[];
  warnings: string[];
}

interface RawPaper {
  id: string;
  title: string;
  authors: string[];
  year: number | null;
  venue?: string | null;
  abstract?: string | null;
  citation_count: number;
  open_access_status?: string | null;
  doi?: string | null;
  url?: string | null;
  pdf_url?: string | null;
  source?: string | null;
}

const CATEGORY_NAMES: Record<string, string> = {
  methodological: "Methodological",
  evaluation: "Evaluation",
  dataset: "Dataset",
  generalization: "Generalization",
  theoretical: "Theoretical",
  application_domain: "Domain Application",
  conflicting_findings: "Conflicting Findings",
  future_direction: "Future Direction",
  other: "Open Inquiry",
};

export default function AnalysisResultsPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const router = useRouter();

  const [results, setResults] = useState<AnalysisResults | null>(null);
  const [papers, setPapers] = useState<RawPaper[]>([]);
  const [selectedGap, setSelectedGap] = useState<ResearchGap | null>(null);
  const [showLiteratureDrawer, setShowLiteratureDrawer] = useState(false);
  const [showShortcuts, setShowShortcuts] = useState(false);
  const [expandedPaperIds, setExpandedPaperIds] = useState<Set<string>>(new Set());
  const [copiedCitationId, setCopiedCitationId] = useState<string | null>(null);

  // Filters
  const [searchFilter, setSearchFilter] = useState("");
  const [categoryFilter, setCategoryFilter] = useState<string>("all");
  const [strengthFilter, setStrengthFilter] = useState<string>("all");
  const [originFilter, setOriginFilter] = useState<string>("all");

  // Keyboard active index
  const [activeRowIndex, setActiveRowIndex] = useState<number>(0);
  const [retrying, setRetrying] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const drawerRef = useRef<HTMLDivElement | null>(null);
  const previousActiveElement = useRef<HTMLElement | null>(null);

  // Fetch results and poll if active
  useEffect(() => {
    let cancelled = false;

    const fetchAnalysis = async () => {
      try {
        const res = await fetch(`/api/research/${id}/results`, { cache: "no-store" });
        if (!res.ok) {
          if (res.status === 404) {
            setErrorMessage("Analysis job not found.");
            return;
          }
          throw new Error(`Server returned HTTP ${res.status}`);
        }
        const data: AnalysisResults = await res.json();
        if (cancelled) return;
        setResults(data);

        if (data.status === "completed" || data.status === "no_results") {
          const pRes = await fetch(`/api/research/${id}/papers`, { cache: "no-store" });
          if (pRes.ok && !cancelled) {
            const paperList = await pRes.json();
            setPapers(paperList);
          }
        }
      } catch (err) {
        if (!cancelled) {
          setErrorMessage(err instanceof Error ? err.message : "Network error");
        }
      }
    };

    fetchAnalysis();

    const interval = setInterval(async () => {
      if (cancelled) return;
      if (results?.status === "completed" || results?.status === "failed" || results?.status === "no_results") {
        clearInterval(interval);
        return;
      }
      await fetchAnalysis();
    }, 2000);

    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [id, results?.status]);

  // Filtered gaps list
  const gaps = results?.gaps;
  const filteredGaps = useMemo(() => {
    if (!gaps) return [];
    return gaps.filter((gap) => {
      if (categoryFilter !== "all" && gap.category !== categoryFilter) return false;
      if (strengthFilter !== "all" && gap.evidence_strength !== strengthFilter) return false;
      if (originFilter !== "all" && gap.origin !== originFilter) return false;
      if (searchFilter.trim()) {
        const query = searchFilter.toLowerCase();
        const text = `${gap.title} ${gap.statement} ${gap.why_it_matters} ${gap.supporting_papers.map((p) => p.title).join(" ")}`.toLowerCase();
        if (!text.includes(query)) return false;
      }
      return true;
    });
  }, [gaps, categoryFilter, strengthFilter, originFilter, searchFilter]);

  // Keyboard navigation
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Don't intercept when typing in search input
      if (["INPUT", "TEXTAREA"].includes((document.activeElement as HTMLElement)?.tagName)) {
        if (e.key === "Escape") {
          (document.activeElement as HTMLElement)?.blur();
        }
        return;
      }

      if (e.key === "Escape") {
        if (selectedGap) {
          setSelectedGap(null);
          previousActiveElement.current?.focus();
        } else if (showLiteratureDrawer) {
          setShowLiteratureDrawer(false);
        } else if (showShortcuts) {
          setShowShortcuts(false);
        }
      } else if (e.key === "j" || e.key === "ArrowDown") {
        e.preventDefault();
        setActiveRowIndex((prev) => Math.min(filteredGaps.length - 1, prev + 1));
      } else if (e.key === "k" || e.key === "ArrowUp") {
        e.preventDefault();
        setActiveRowIndex((prev) => Math.max(0, prev - 1));
      } else if (e.key === "Enter" && !selectedGap) {
        if (filteredGaps[activeRowIndex]) {
          e.preventDefault();
          previousActiveElement.current = document.activeElement as HTMLElement;
          setSelectedGap(filteredGaps[activeRowIndex]);
        }
      } else if (e.key === "?") {
        e.preventDefault();
        setShowShortcuts((prev) => !prev);
      } else if (e.key === "/") {
        e.preventDefault();
        router.push("/");
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [selectedGap, showLiteratureDrawer, showShortcuts, filteredGaps, activeRowIndex, router]);

  // Supporting paper accordion toggle
  const togglePaperExpanded = (paperId: string) => {
    setExpandedPaperIds((prev) => {
      const next = new Set(prev);
      if (next.has(paperId)) next.delete(paperId);
      else next.add(paperId);
      return next;
    });
  };

  // Copy citation helper
  const copyCitation = (paper: SupportingPaper | RawPaper) => {
    const authors = paper.authors.length > 0 ? paper.authors.join(", ") : "Anonymous";
    const text = `${authors} (${paper.year || "n.d."}). "${paper.title}". ${paper.venue || "Scholarly Record"}. ${paper.doi ? `https://doi.org/${paper.doi}` : paper.url || ""}`.trim();
    navigator.clipboard.writeText(text);
    const idToCopy = "paper_id" in paper ? paper.paper_id : paper.id;
    setCopiedCitationId(idToCopy);
    setTimeout(() => setCopiedCitationId(null), 2000);
  };

  const handleRetry = async () => {
    setRetrying(true);
    try {
      const res = await fetch(`/api/research/${id}/retry`, { method: "POST" });
      if (res.ok) {
        setResults((prev) => (prev ? { ...prev, status: "pending", stage: "queued" } : null));
        setErrorMessage(null);
      }
    } catch {
      // ignore
    } finally {
      setRetrying(false);
    }
  };

  return (
    <div className="min-h-screen bg-[var(--color-bg)] text-[var(--color-text)] flex flex-col selection:bg-[var(--color-accent-soft)]">
      {/* Top Quiet Navigation */}
      <header className="border-b border-[var(--color-border)] bg-[var(--color-bg)] sticky top-0 z-30 px-6 sm:px-12 py-3.5 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link href="/" className="font-serif-editorial text-[18px] text-[var(--color-text)] flex items-center gap-2 hover:opacity-85 transition-opacity">
            <span className="w-2 h-2 rounded-full bg-[var(--color-accent)]" />
            ResearchLens
          </Link>
          <span className="text-[var(--color-border)] text-xs">/</span>
          <span className="text-[13px] text-[var(--color-text-muted)] font-mono truncate max-w-[200px] sm:max-w-sm">
            {results?.query || id.slice(0, 8)}
          </span>
        </div>

        <div className="flex items-center gap-3 text-[13px]">
          {results?.status === "completed" && (
            <>
              <button
                onClick={() => setShowLiteratureDrawer(true)}
                className="text-[var(--color-text-muted)] hover:text-[var(--color-text)] px-2.5 py-1.5 rounded-[6px] border border-[var(--color-border)] hover:border-[var(--color-border-subtle)] bg-[var(--color-surface)] transition-colors flex items-center gap-1.5"
              >
                <span>Literature ({results.corpus.papers_analysed})</span>
              </button>

              <ExportMenu query={results.query} gaps={results.gaps} />
            </>
          )}

          <ThemeToggle />

          <Link
            href="/"
            className="text-[var(--color-text)] hover:text-[var(--color-accent)] transition-colors ml-1"
          >
            New search
          </Link>
        </div>
      </header>

      {/* Main Canvas */}
      <main className="flex-1 max-w-[1120px] w-full mx-auto px-6 sm:px-12 py-10">
        {/* Loading State: Vertical Stepper & List Skeletons */}
        {results && (results.status === "pending" || results.status === "running") && (
          <LoadingStepper
            stage={results.stage}
            papersRetrieved={results.corpus?.papers_retrieved || 0}
            papersAnalysed={results.corpus?.papers_analysed || 0}
            query={results.query}
          />
        )}

        {/* Failed State */}
        {(errorMessage || results?.status === "failed") && (
          <div className="py-20 max-w-lg mx-auto text-left space-y-4">
            <span className="text-xs font-mono text-[var(--color-text-faint)] uppercase tracking-wider block">
              Analysis Interrupted
            </span>
            <h2 className="text-2xl font-serif-editorial text-[var(--color-text)]">
              Unable to complete literature synthesis
            </h2>
            <p className="text-[14px] text-[var(--color-text-muted)] leading-relaxed">
              {errorMessage || results?.warnings?.[0] || "Retrieval or synthesis pipeline failed unexpectedly."}
            </p>
            <div className="pt-2 flex items-center gap-3">
              <button
                onClick={handleRetry}
                disabled={retrying}
                className="px-3.5 py-1.5 bg-[var(--color-accent)] text-black text-[13px] font-medium rounded-[4px] hover:opacity-90 transition-opacity"
              >
                {retrying ? "Retrying..." : "Retry Analysis"}
              </button>
              <Link
                href="/"
                className="px-3.5 py-1.5 border border-[var(--color-border)] text-[var(--color-text-muted)] hover:text-[var(--color-text)] text-[13px] rounded-[4px] transition-colors"
              >
                Return to Search
              </Link>
            </div>
          </div>
        )}

        {/* No Results State */}
        {results?.status === "no_results" && (
          <div className="py-20 max-w-lg mx-auto text-left space-y-4">
            <span className="text-xs font-mono text-[var(--color-text-faint)] uppercase tracking-wider block">
              Literature Query Boundary
            </span>
            <h2 className="text-2xl font-serif-editorial text-[var(--color-text)]">
              No index matches found
            </h2>
            <p className="text-[14px] text-[var(--color-text-muted)] leading-relaxed">
              OpenAlex, arXiv, and Semantic Scholar returned insufficient peer-reviewed records for &quot;{results.query}&quot;.
              Consider removing specific acronyms or searching a broader disciplinary term.
            </p>
            <div className="pt-2">
              <Link
                href="/"
                className="px-3.5 py-1.5 bg-[var(--color-accent)] text-black text-[13px] font-medium rounded-[4px] hover:opacity-90 inline-block"
              >
                Refine Query
              </Link>
            </div>
          </div>
        )}

        {/* Completed Results: Single-Column Editorial List */}
        {results?.status === "completed" && (
          <div className="space-y-8">
            {/* Editorial Title & Scope Header */}
            <div className="border-b border-[var(--color-border)] pb-6 space-y-3">
              <div className="flex flex-col sm:flex-row sm:items-baseline justify-between gap-2">
                <h1 className="text-3xl sm:text-4xl font-serif-editorial text-[var(--color-text)] tracking-tight">
                  {results.query}
                </h1>
                <span className="text-[12px] font-mono text-[var(--color-text-faint)] tabular-nums">
                  ID: {results.search_id.slice(0, 8)}
                </span>
              </div>

              {/* Scope line (plain typography, no rainbow badges) */}
              <div className="flex items-center gap-3 text-[13px] text-[var(--color-text-muted)] flex-wrap">
                {results.corpus.raw_provider_results ? (
                  <span className="tabular-nums">{results.corpus.raw_provider_results} papers retrieved</span>
                ) : (
                  <span className="tabular-nums">{results.corpus.papers_retrieved} papers retrieved</span>
                )}
                <span>·</span>
                <span className="tabular-nums">{results.corpus.papers_analysed} examined</span>
                {Boolean(results.corpus.full_text_analysed && results.corpus.full_text_analysed > 0) && (
                  <>
                    <span>·</span>
                    <span className="tabular-nums text-[var(--color-accent)]">{results.corpus.full_text_analysed} full-text inspected</span>
                  </>
                )}
                {results.corpus.publication_year_range.start && results.corpus.publication_year_range.end && (
                  <>
                    <span>·</span>
                    <span className="tabular-nums">{results.corpus.publication_year_range.start}–{results.corpus.publication_year_range.end}</span>
                  </>
                )}
                <span>·</span>
                <span className="text-[var(--color-text)] font-medium">{results.gaps.length} research gaps identified</span>
              </div>
            </div>

            {/* Filter Toolbar (Subtle, Clean) */}
            <div className="py-2 flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 text-[13px]">
              <div className="flex items-center gap-3 flex-1 max-w-md">
                <input
                  type="text"
                  value={searchFilter}
                  onChange={(e) => setSearchFilter(e.target.value)}
                  placeholder="Filter gaps or keywords..."
                  className="w-full bg-[var(--color-surface)] border border-[var(--color-border)] rounded-[4px] px-3 py-1.5 text-[13px] text-[var(--color-text)] placeholder-[var(--color-text-faint)] outline-none focus:border-[var(--color-accent)]"
                />
              </div>

              <div className="flex items-center gap-3 flex-wrap">
                {/* Category select */}
                <select
                  value={categoryFilter}
                  onChange={(e) => setCategoryFilter(e.target.value)}
                  className="bg-[var(--color-surface)] border border-[var(--color-border)] rounded-[4px] px-2.5 py-1.5 text-[12px] text-[var(--color-text-muted)] outline-none focus:border-[var(--color-accent)]"
                >
                  <option value="all">All Categories</option>
                  {Object.entries(CATEGORY_NAMES).map(([key, label]) => {
                    const count = results.gaps.filter((g) => g.category === key).length;
                    if (count === 0) return null;
                    return (
                      <option key={key} value={key}>
                        {label} ({count})
                      </option>
                    );
                  })}
                </select>

                {/* Strength select */}
                <select
                  value={strengthFilter}
                  onChange={(e) => setStrengthFilter(e.target.value)}
                  className="bg-[var(--color-surface)] border border-[var(--color-border)] rounded-[4px] px-2.5 py-1.5 text-[12px] text-[var(--color-text-muted)] outline-none focus:border-[var(--color-accent)]"
                >
                  <option value="all">All Strengths</option>
                  <option value="strong">Strong evidence</option>
                  <option value="moderate">Moderate evidence</option>
                  <option value="preliminary">Preliminary evidence</option>
                </select>

                {/* Origin select */}
                <select
                  value={originFilter}
                  onChange={(e) => setOriginFilter(e.target.value)}
                  className="bg-[var(--color-surface)] border border-[var(--color-border)] rounded-[4px] px-2.5 py-1.5 text-[12px] text-[var(--color-text-muted)] outline-none focus:border-[var(--color-accent)]"
                >
                  <option value="all">All Origins</option>
                  <option value="cross_paper_inference">Inferred</option>
                  <option value="explicit">Author-reported</option>
                </select>

                {(categoryFilter !== "all" || strengthFilter !== "all" || originFilter !== "all" || searchFilter) && (
                  <button
                    onClick={() => {
                      setCategoryFilter("all");
                      setStrengthFilter("all");
                      setOriginFilter("all");
                      setSearchFilter("");
                    }}
                    className="text-[12px] text-[var(--color-accent)] hover:underline"
                  >
                    Reset
                  </button>
                )}
              </div>
            </div>

            {/* Results Counter */}
            <div className="text-[12px] text-[var(--color-text-faint)] tabular-nums">
              Showing {filteredGaps.length} of {results.gaps.length} gaps
            </div>

            {/* RESPONSIVE GRID OF RESEARCH-GAP CARDS */}
            {filteredGaps.length === 0 ? (
              <div className="py-16 text-center text-[var(--color-text-muted)] border-t border-[var(--color-border-subtle)]">
                No gaps match your filter criteria.
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 pt-2">
                {filteredGaps.map((gap, idx) => (
                  <GapCard
                    key={gap.gap_id}
                    gap={gap}
                    index={idx}
                    isActive={activeRowIndex === idx}
                    onSelect={() => {
                      setActiveRowIndex(idx);
                      setSelectedGap(gap);
                    }}
                    categoryNames={CATEGORY_NAMES}
                  />
                ))}
              </div>
            )}
          </div>
        )}
      </main>

      {/* DEDICATED EVIDENCE DRAWER SHEET (Right-side sheet, min(720px, 90vw)) */}
      <AnimatePresence>
        {selectedGap && (
          <div className="fixed inset-0 z-50 overflow-hidden flex justify-end">
            {/* 40% dim + 4px blur backdrop */}
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.2 }}
              className="fixed inset-0 bg-black/40 backdrop-blur-[4px]"
              onClick={() => setSelectedGap(null)}
            />

            {/* Solid Surface Sheet */}
            <motion.div
              ref={drawerRef}
              initial={{ x: "100%" }}
              animate={{ x: 0 }}
              exit={{ x: "100%" }}
              transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
              className="relative w-full max-w-[min(720px,95vw)] bg-[var(--color-surface)] border-l border-[var(--color-border)] h-full overflow-y-auto p-6 sm:p-10 space-y-8 z-10 text-[14px]"
              onClick={(e) => e.stopPropagation()}
            >
              {/* Drawer Header */}
              <div className="flex items-start justify-between gap-4 border-b border-[var(--color-border)] pb-5">
                <div className="space-y-1.5 flex-1">
                  <div className="text-[12px] text-[var(--color-text-muted)] flex items-center gap-2 flex-wrap">
                    <span className="font-medium text-[var(--color-text)]">
                      {CATEGORY_NAMES[selectedGap.category] || "Research Gap"}
                    </span>
                    <span>·</span>
                    <span className="text-[var(--color-text-faint)]">
                      {selectedGap.origin === "cross_paper_inference" ? "Cross-paper inference" : "Author-reported"}
                    </span>
                    <span>·</span>
                    <EvidenceMeter strength={selectedGap.evidence_strength} />
                  </div>

                  <h2 className="text-2xl font-serif-editorial text-[var(--color-text)] tracking-tight leading-snug">
                    {selectedGap.title}
                  </h2>
                </div>

                <button
                  onClick={() => setSelectedGap(null)}
                  className="p-1.5 rounded-[4px] border border-[var(--color-border)] text-[var(--color-text-faint)] hover:text-[var(--color-text)] hover:bg-[var(--color-surface-2)] transition-colors shrink-0"
                  aria-label="Close evidence drawer"
                >
                  ✕
                </button>
              </div>

              {/* Full Gap Statement */}
              <div className="space-y-2">
                <h4 className="text-[11px] font-mono uppercase tracking-wider text-[var(--color-text-faint)]">
                  Evidence-Backed Gap Formulation
                </h4>
                <div className="p-4 bg-[var(--color-surface-2)] border border-[var(--color-border)] rounded-[6px] text-[14px] text-[var(--color-text)] leading-relaxed">
                  {selectedGap.statement}
                </div>
              </div>

              {/* Why This Matters */}
              <div className="space-y-2">
                <h4 className="text-[11px] font-mono uppercase tracking-wider text-[var(--color-text-faint)]">
                  Research Significance & Why It Matters
                </h4>
                <p className="text-[14px] text-[var(--color-text-muted)] leading-relaxed">
                  {selectedGap.why_it_matters}
                </p>
              </div>

              {/* Scope Qualifications & Boundaries */}
              {selectedGap.qualifications && (
                <div className="space-y-2">
                  <h4 className="text-[11px] font-mono uppercase tracking-wider text-[var(--color-text-faint)]">
                    Scope Qualifications & Empirical Boundaries
                  </h4>
                  <div className="p-3.5 bg-[var(--color-bg)] border border-[var(--color-border-subtle)] rounded-[6px] text-[13px] text-[var(--color-text-muted)] leading-relaxed">
                    {selectedGap.qualifications}
                  </div>
                </div>
              )}

              {/* Cross-Paper Synthesis Reasoning */}
              {selectedGap.reasoning && (
                <div className="space-y-2">
                  <h4 className="text-[11px] font-mono uppercase tracking-wider text-[var(--color-text-faint)]">
                    Literature Relationship & Synthesis
                  </h4>
                  <div className="p-3 bg-[var(--color-bg)] border border-[var(--color-border-subtle)] rounded-[6px] text-[13px] text-[var(--color-text-muted)] leading-relaxed">
                    {selectedGap.reasoning}
                  </div>
                </div>
              )}

              {/* Supporting Literature & Verbatim Passages */}
              <div className="space-y-4 pt-2">
                <div className="flex items-center justify-between border-b border-[var(--color-border)] pb-2">
                  <h4 className="text-[11px] font-mono uppercase tracking-wider text-[var(--color-text-faint)]">
                    Supporting Literature & Extracted Evidence ({selectedGap.supporting_papers.length})
                  </h4>
                  <span className="text-[11px] text-[var(--color-text-faint)]">Click to expand quotes</span>
                </div>

                <div className="space-y-3">
                  {selectedGap.supporting_papers.map((paper) => {
                    const isExpanded = expandedPaperIds.has(paper.paper_id);

                    return (
                      <div
                        key={paper.paper_id}
                        className="border border-[var(--color-border)] rounded-[6px] bg-[var(--color-surface-2)] transition-all overflow-hidden"
                      >
                        {/* Summary Bar */}
                        <div
                          onClick={() => togglePaperExpanded(paper.paper_id)}
                          className="p-3.5 flex items-start justify-between gap-3 cursor-pointer hover:bg-[var(--color-surface)] transition-colors"
                        >
                          <div className="space-y-1 flex-1">
                            <h5 className="font-medium text-[14px] text-[var(--color-text)] leading-snug">
                              {paper.title}
                            </h5>
                            <div className="text-[12px] text-[var(--color-text-faint)] flex items-center gap-2 flex-wrap">
                              <span>{paper.authors.slice(0, 2).join(", ")}{paper.authors.length > 2 ? " et al." : ""}</span>
                              {paper.year && <span>• {paper.year}</span>}
                              {paper.venue && <span>• {paper.venue}</span>}
                              {paper.citation_count > 0 && <span className="tabular-nums">• {paper.citation_count} citations</span>}
                              <span className="font-mono text-[11px] px-1.5 py-0.2 rounded border border-[var(--color-border)] text-[var(--color-text-faint)]">
                                {paper.source_scope === "full_text" ? "Full text" : "Abstract"}
                              </span>
                            </div>
                          </div>

                          <span className="text-[13px] text-[var(--color-text-faint)] pt-1">
                            {isExpanded ? "–" : "+"}
                          </span>
                        </div>

                        {/* Collapsible Details */}
                        {isExpanded && (
                          <div className="p-3.5 pt-0 border-t border-[var(--color-border-subtle)] space-y-3 animate-fade-in text-[13px]">
                            {/* Action Links */}
                            <div className="flex items-center gap-3 pt-2 text-[12px] flex-wrap">
                              {paper.doi && (
                                <a
                                  href={`https://doi.org/${paper.doi}`}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="text-[var(--color-accent)] hover:underline"
                                >
                                  DOI: {paper.doi} ↗
                                </a>
                              )}
                              {paper.url && (
                                <a
                                  href={paper.url}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="text-[var(--color-text-muted)] hover:text-[var(--color-text)] underline"
                                >
                                  Publisher Page ↗
                                </a>
                              )}
                              {paper.pdf_url && (
                                <a
                                  href={paper.pdf_url}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="text-[var(--color-accent)] hover:underline"
                                >
                                  Open-Access PDF ↗
                                </a>
                              )}
                              <button
                                onClick={() => copyCitation(paper)}
                                className="text-[var(--color-text-faint)] hover:text-[var(--color-text)] ml-auto"
                              >
                                {copiedCitationId === paper.paper_id ? "Citation copied" : "Copy citation"}
                              </button>
                            </div>

                            {/* Extracted Passages */}
                            {paper.evidence_passages.length > 0 && (
                              <div className="space-y-2 pt-2">
                                <span className="text-[11px] font-mono text-[var(--color-text-faint)] uppercase block">
                                  Verbatim Extracted Passages:
                                </span>
                                {paper.evidence_passages.map((ev, idx) => (
                                  <blockquote
                                    key={idx}
                                    className="border-l-2 border-[var(--color-accent)] pl-3 py-1 text-[13px] text-[var(--color-text-muted)] italic bg-[var(--color-bg)] rounded-r"
                                  >
                                    &quot;{ev.text}&quot;
                                    {ev.section && (
                                      <span className="block mt-1 not-italic font-mono text-[11px] text-[var(--color-text-faint)]">
                                        Location: {ev.section}
                                      </span>
                                    )}
                                  </blockquote>
                                ))}
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Close Button */}
              <div className="pt-6 border-t border-[var(--color-border)] flex justify-between items-center text-[12px] text-[var(--color-text-faint)]">
                <span>Press Esc to close</span>
                <button
                  onClick={() => setSelectedGap(null)}
                  className="px-3 py-1.5 border border-[var(--color-border)] rounded-[4px] hover:bg-[var(--color-surface-2)] text-[var(--color-text)] transition-colors"
                >
                  Done
                </button>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      {/* LITERATURE INSPECTION SHEET */}
      <AnimatePresence>
        {showLiteratureDrawer && (
          <div className="fixed inset-0 z-50 overflow-hidden flex justify-end">
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="fixed inset-0 bg-black/40 backdrop-blur-[4px]"
              onClick={() => setShowLiteratureDrawer(false)}
            />

            <motion.div
              initial={{ x: "100%" }}
              animate={{ x: 0 }}
              exit={{ x: "100%" }}
              transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
              className="relative w-full max-w-[min(720px,95vw)] bg-[var(--color-surface)] border-l border-[var(--color-border)] h-full overflow-y-auto p-6 sm:p-10 space-y-6 z-10 text-[14px]"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="flex items-start justify-between border-b border-[var(--color-border)] pb-4">
                <div>
                  <h2 className="text-2xl font-serif-editorial text-[var(--color-text)]">
                    Retrieved Scholarly Literature
                  </h2>
                  <p className="text-[13px] text-[var(--color-text-muted)] mt-1">
                    {papers.length} peer-reviewed publications examined for &quot;{results?.query}&quot;
                  </p>
                </div>
                <button
                  onClick={() => setShowLiteratureDrawer(false)}
                  className="p-1.5 rounded-[4px] border border-[var(--color-border)] text-[var(--color-text-faint)] hover:text-[var(--color-text)]"
                >
                  ✕
                </button>
              </div>

              <div className="space-y-4">
                {papers.map((p) => (
                  <div
                    key={p.id}
                    className="p-4 border border-[var(--color-border)] rounded-[6px] bg-[var(--color-surface-2)] space-y-2 text-[13px]"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <h4 className="font-medium text-[14px] text-[var(--color-text)] leading-snug">
                        {p.title}
                      </h4>
                      {p.source && (
                        <span className="font-mono text-[11px] text-[var(--color-text-faint)] px-1.5 py-0.5 border border-[var(--color-border)] rounded-[4px] shrink-0">
                          {p.source}
                        </span>
                      )}
                    </div>

                    <div className="text-[12px] text-[var(--color-text-faint)] flex items-center gap-2 flex-wrap">
                      <span>{p.authors.join(", ")}</span>
                      {p.year && <span>• {p.year}</span>}
                      {p.venue && <span>• {p.venue}</span>}
                      {p.citation_count > 0 && <span className="tabular-nums">• {p.citation_count} citations</span>}
                    </div>

                    {p.abstract && (
                      <p className="text-[13px] text-[var(--color-text-muted)] line-clamp-3 leading-relaxed pt-1">
                        {p.abstract}
                      </p>
                    )}

                    <div className="flex items-center gap-3 pt-2 text-[12px] flex-wrap">
                      {p.doi && (
                        <a
                          href={`https://doi.org/${p.doi}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-[var(--color-accent)] hover:underline"
                        >
                          DOI ↗
                        </a>
                      )}
                      {p.url && (
                        <a
                          href={p.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-[var(--color-text-muted)] hover:text-[var(--color-text)] underline"
                        >
                          Publisher Page ↗
                        </a>
                      )}
                      {p.pdf_url && (
                        <a
                          href={p.pdf_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-[var(--color-accent)] hover:underline"
                        >
                          Open-Access PDF ↗
                        </a>
                      )}
                      <button
                        onClick={() => copyCitation(p)}
                        className="text-[var(--color-text-faint)] hover:text-[var(--color-text)] ml-auto"
                      >
                        {copiedCitationId === p.id ? "Citation copied" : "Copy citation"}
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      {/* Keyboard Shortcuts Modal */}
      <KeyboardShortcutsModal isOpen={showShortcuts} onClose={() => setShowShortcuts(false)} />
    </div>
  );
}
