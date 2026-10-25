"use client";

import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ThemeToggle } from "@/components/ThemeToggle";
import { KeyboardShortcutsModal } from "@/components/KeyboardShortcutsModal";

const MAX_QUERY_LENGTH = 500;
const RECENT_TOPICS_KEY = "researchlens_recent_topics";
const MAX_RECENT = 5;

interface FilterOptions {
  yearRange: "all" | "3y" | "5y";
  limit: number;
  sources: string[];
}

function loadRecentTopics(): string[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = localStorage.getItem(RECENT_TOPICS_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function saveRecentTopics(topics: string[]): void {
  try {
    localStorage.setItem(RECENT_TOPICS_KEY, JSON.stringify(topics));
  } catch {
    // Fail silently
  }
}

function addRecentTopic(topic: string, existing: string[]): string[] {
  const trimmed = topic.trim();
  const filtered = existing.filter((t) => t.toLowerCase() !== trimmed.toLowerCase());
  return [trimmed, ...filtered].slice(0, MAX_RECENT);
}

export default function HomePage() {
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [showFilters, setShowFilters] = useState(false);
  const [showHowItWorks, setShowHowItWorks] = useState(false);
  const [showShortcuts, setShowShortcuts] = useState(false);
  const [filters, setFilters] = useState<FilterOptions>({
    yearRange: "all",
    limit: 50,
    sources: ["openalex", "arxiv", "semanticscholar"],
  });
  const [error, setError] = useState<string | null>(null);
  const [recentTopics, setRecentTopics] = useState<string[]>([]);
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    setRecentTopics(loadRecentTopics());

    // Global keyboard listener
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "/" && document.activeElement !== inputRef.current) {
        e.preventDefault();
        inputRef.current?.focus();
      } else if (e.key === "?" && !["INPUT", "TEXTAREA"].includes((document.activeElement as HTMLElement)?.tagName)) {
        e.preventDefault();
        setShowShortcuts((prev) => !prev);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  const exampleTopics = [
    "Cold-start recommendation under preference shifts",
    "Explainable artificial intelligence in clinical oncology",
    "Multimodal misinformation detection benchmarks",
  ];

  const handleSearch = async (e?: React.FormEvent, directQuery?: string) => {
    if (e) e.preventDefault();
    const searchQuery = (directQuery ?? query).trim();

    if (!searchQuery) {
      setError("Please enter a research topic or scholarly question.");
      inputRef.current?.focus();
      return;
    }

    if (searchQuery.length > MAX_QUERY_LENGTH) {
      setError(`Topic query exceeds ${MAX_QUERY_LENGTH} characters.`);
      return;
    }

    if (abortRef.current) {
      abortRef.current.abort();
    }
    const controller = new AbortController();
    abortRef.current = controller;

    setLoading(true);
    setError(null);

    const currentYear = new Date().getFullYear();
    const yearMin = filters.yearRange === "3y" ? currentYear - 3 : filters.yearRange === "5y" ? currentYear - 5 : undefined;

    try {
      const res = await fetch("/api/research/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query: searchQuery,
          year_min: yearMin,
          limit: filters.limit,
          sources: filters.sources,
        }),
        signal: controller.signal,
      });

      if (!res.ok) {
        let errMessage = `Server error (${res.status})`;
        try {
          const errData = await res.json();
          if (errData?.detail) errMessage = errData.detail;
        } catch {
          // generic fallback
        }
        setError(errMessage);
        return;
      }

      const data = await res.json();
      if (!data?.id) {
        setError("Unexpected response from backend.");
        return;
      }

      setRecentTopics((prev) => {
        const updated = addRecentTopic(searchQuery, prev);
        saveRecentTopics(updated);
        return updated;
      });

      router.push(`/analysis/${data.id}`);
    } catch (err: unknown) {
      if (err instanceof DOMException && err.name === "AbortError") {
        setError("Request was cancelled.");
      } else {
        setError(err instanceof Error ? err.message : "Failed to connect to backend API.");
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[var(--color-bg)] text-[var(--color-text)] flex flex-col justify-between selection:bg-[var(--color-accent-soft)]">
      {/* Editorial Top Navigation */}
      <header className="border-b border-[var(--color-border)] py-4 px-6 sm:px-12 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link href="/" className="font-serif-editorial text-[19px] tracking-tight text-[var(--color-text)] flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-[var(--color-accent)]" />
            ResearchLens
          </Link>
        </div>

        <div className="flex items-center gap-4 text-[13px] text-[var(--color-text-muted)]">
          <button
            onClick={() => setShowShortcuts(true)}
            className="hover:text-[var(--color-text)] transition-colors hidden sm:flex items-center gap-1 font-mono text-[11px] text-[var(--color-text-faint)]"
            title="Keyboard shortcuts (?)"
          >
            <kbd className="px-1 py-0.5 border border-[var(--color-border)] rounded-[4px] bg-[var(--color-surface)]">?</kbd>
          </button>
          <ThemeToggle />
          <a
            href="https://github.com/taniavithayathil/ResearchLens"
            target="_blank"
            rel="noopener noreferrer"
            className="text-[var(--color-text-muted)] hover:text-[var(--color-text)] transition-colors"
          >
            Repository
          </a>
        </div>
      </header>

      {/* Main Focused Search Canvas */}
      <main className="flex-1 max-w-[720px] w-full mx-auto px-6 py-16 sm:py-24 flex flex-col justify-center">
        <div className="space-y-4 mb-8 text-left">
          <h1 className="text-3xl sm:text-5xl font-serif-editorial text-[var(--color-text)] tracking-tight leading-[1.15]">
            Discover what existing research has yet to answer.
          </h1>
          <p className="text-[15px] text-[var(--color-text-muted)] leading-relaxed max-w-[620px]">
            Synthesising unresolved limitations, evaluation boundaries, and conflicting findings across peer-reviewed literature.
          </p>
        </div>

        {/* Search Input Box */}
        <div className="relative">
          <form onSubmit={(e) => handleSearch(e)} className="relative flex items-center">
            <input
              ref={inputRef}
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Try: cold-start recommendation"
              disabled={loading}
              className="w-full bg-[var(--color-surface)] border border-[var(--color-border)] rounded-[6px] pl-4 pr-32 py-3.5 text-[15px] text-[var(--color-text)] placeholder-[var(--color-text-faint)] outline-none focus:border-[var(--color-accent)] focus:ring-2 focus:ring-[var(--color-accent-soft)] transition-all"
              aria-label="Research topic or question"
              autoFocus
            />

            <div className="absolute right-2 flex items-center gap-1.5">
              <button
                type="button"
                onClick={() => setShowFilters(!showFilters)}
                className={`text-[12px] px-2.5 py-1.5 rounded-[4px] border transition-colors ${
                  showFilters
                    ? "bg-[var(--color-surface-2)] border-[var(--color-accent)] text-[var(--color-text)]"
                    : "border-transparent text-[var(--color-text-faint)] hover:text-[var(--color-text-muted)]"
                }`}
              >
                Filters
              </button>

              <button
                type="submit"
                disabled={loading || !query.trim()}
                className="bg-[var(--color-accent)] hover:opacity-90 active:translate-y-[1px] text-black font-medium text-[13px] px-3.5 py-1.5 rounded-[4px] transition-all disabled:opacity-40 disabled:cursor-not-allowed disabled:active:translate-y-0"
              >
                {loading ? "Searching..." : "Search"}
              </button>
            </div>
          </form>

          {/* Quiet Filters Popover */}
          {showFilters && (
            <div className="mt-2 p-4 bg-[var(--color-surface)] border border-[var(--color-border)] rounded-[6px] text-[13px] grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-[var(--color-text-muted)] text-[12px] mb-1">Publication Year</label>
                <select
                  value={filters.yearRange}
                  onChange={(e) => setFilters({ ...filters, yearRange: e.target.value as FilterOptions["yearRange"] })}
                  className="w-full bg-[var(--color-surface-2)] border border-[var(--color-border)] rounded-[4px] px-2.5 py-1.5 text-[var(--color-text)] outline-none focus:border-[var(--color-accent)]"
                >
                  <option value="all">All publication years</option>
                  <option value="3y">Past 3 years (Recent)</option>
                  <option value="5y">Past 5 years</option>
                </select>
              </div>

              <div>
                <label className="block text-[var(--color-text-muted)] text-[12px] mb-1">Corpus Limit</label>
                <select
                  value={filters.limit}
                  onChange={(e) => setFilters({ ...filters, limit: Number(e.target.value) })}
                  className="w-full bg-[var(--color-surface-2)] border border-[var(--color-border)] rounded-[4px] px-2.5 py-1.5 text-[var(--color-text)] outline-none focus:border-[var(--color-accent)]"
                >
                  <option value={25}>25 papers (Fast)</option>
                  <option value={50}>50 papers (Standard)</option>
                  <option value={75}>75 papers (Comprehensive)</option>
                </select>
              </div>
            </div>
          )}
        </div>

        {/* Error Notification */}
        {error && (
          <div className="mt-3 text-[13px] text-red-500 flex items-center gap-1.5">
            <span>•</span>
            <span>{error}</span>
          </div>
        )}

        {/* Quiet Underlined Example Topics */}
        <div className="mt-8 space-y-2 text-left">
          <span className="text-[12px] text-[var(--color-text-faint)] block">
            Suggested investigations:
          </span>
          <div className="flex flex-col sm:flex-row flex-wrap gap-x-5 gap-y-2 text-[13px]">
            {exampleTopics.map((topic) => (
              <button
                key={topic}
                onClick={() => {
                  setQuery(topic);
                  handleSearch(undefined, topic);
                }}
                disabled={loading}
                className="link-editorial text-[var(--color-text-muted)] hover:text-[var(--color-text)] text-left"
              >
                {topic}
              </button>
            ))}
          </div>
        </div>

        {/* Recent Searches */}
        {recentTopics.length > 0 && (
          <div className="mt-6 pt-4 border-t border-[var(--color-border-subtle)] flex items-center gap-3 text-[12px] text-[var(--color-text-faint)] flex-wrap">
            <span>Recent:</span>
            {recentTopics.map((item) => (
              <button
                key={item}
                onClick={() => {
                  setQuery(item);
                  handleSearch(undefined, item);
                }}
                disabled={loading}
                className="hover:text-[var(--color-text)] text-[var(--color-text-muted)] transition-colors"
              >
                {item}
              </button>
            ))}
          </div>
        )}

        {/* Single Quiet Expandable "How it works" */}
        <div className="mt-12 pt-6 border-t border-[var(--color-border-subtle)] text-[12px] text-[var(--color-text-muted)]">
          <button
            onClick={() => setShowHowItWorks(!showHowItWorks)}
            className="flex items-center gap-1.5 hover:text-[var(--color-text)] transition-colors"
          >
            <span>{showHowItWorks ? "– Hide methodology note" : "+ How ResearchLens synthesises gaps"}</span>
          </button>
          {showHowItWorks && (
            <div className="mt-3 text-[13px] text-[var(--color-text-faint)] leading-relaxed space-y-2 max-w-[640px]">
              <p>
                ResearchLens retrieves open-access records from OpenAlex, arXiv, and Semantic Scholar.
                The engine segments abstracts to detect empirical limitations, benchmark assumptions, and future directions.
              </p>
              <p>
                Gaps occurring across multiple papers are synthesised as inferred cross-paper boundaries, while single-paper limitations
                are attributed directly to study authors. Every claim is verified against verbatim source passages.
              </p>
            </div>
          )}
        </div>
      </main>

      {/* Editorial Footer */}
      <footer className="border-t border-[var(--color-border)] py-4 px-6 sm:px-12 text-[12px] text-[var(--color-text-faint)] flex flex-col sm:flex-row items-center justify-between gap-2">
        <div>
          Sources queried: OpenAlex • arXiv • Semantic Scholar.
        </div>
        <div>
          Grounded exclusively in peer-reviewed literature.
        </div>
      </footer>

      {/* Keyboard Shortcuts Modal */}
      <KeyboardShortcutsModal isOpen={showShortcuts} onClose={() => setShowShortcuts(false)} />
    </div>
  );
}
