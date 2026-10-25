"use client";

import { useState } from "react";

interface SupportingPaper {
  paper_id: string;
  title: string;
  authors: string[];
  year: number | null;
  venue?: string | null;
  doi?: string | null;
  url?: string | null;
  citation_count: number;
}

interface ResearchGap {
  gap_id: string;
  title: string;
  statement: string;
  why_it_matters: string;
  category: string;
  origin: string;
  evidence_strength: string;
  supporting_paper_count: number;
  supporting_papers: SupportingPaper[];
}

interface ExportMenuProps {
  query: string;
  gaps: ResearchGap[];
}

export function ExportMenu({ query, gaps }: ExportMenuProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [copied, setCopied] = useState(false);

  // 1. Export Markdown
  const exportMarkdown = () => {
    let md = `# ResearchLens Gap Discovery: ${query}\n\n`;
    md += `*Generated on ${new Date().toLocaleDateString()} with ${gaps.length} discovered research gaps.*\n\n---\n\n`;

    gaps.forEach((gap, idx) => {
      md += `### ${idx + 1}. ${gap.title}\n\n`;
      md += `**Category:** ${gap.category} | **Origin:** ${gap.origin} | **Strength:** ${gap.evidence_strength}\n\n`;
      md += `**Gap Statement:**\n> ${gap.statement}\n\n`;
      md += `**Why It Matters:**\n${gap.why_it_matters}\n\n`;
      md += `**Supporting Literature (${gap.supporting_papers.length} papers):**\n`;
      gap.supporting_papers.forEach((p) => {
        const link = p.doi ? `https://doi.org/${p.doi}` : p.url || "";
        md += `- ${p.title} (${p.year || "n.d."}) — ${p.authors.join(", ")} [${link}](${link})\n`;
      });
      md += `\n---\n\n`;
    });

    const blob = new Blob([md], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `researchlens-gaps-${query.replace(/\s+/g, "_").toLowerCase()}.md`;
    a.click();
    URL.revokeObjectURL(url);
    setIsOpen(false);
  };

  // 2. Export CSV
  const exportCSV = () => {
    const headers = ["Index", "Title", "Category", "Origin", "Evidence_Strength", "Supporting_Papers_Count", "Statement", "Why_It_Matters"];
    const rows = gaps.map((g, idx) => [
      idx + 1,
      `"${g.title.replace(/"/g, '""')}"`,
      `"${g.category}"`,
      `"${g.origin}"`,
      `"${g.evidence_strength}"`,
      g.supporting_paper_count,
      `"${g.statement.replace(/"/g, '""')}"`,
      `"${g.why_it_matters.replace(/"/g, '""')}"`,
    ]);

    const csvContent = [headers.join(","), ...rows.map((r) => r.join(","))].join("\n");
    const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `researchlens-gaps-${query.replace(/\s+/g, "_").toLowerCase()}.csv`;
    a.click();
    URL.revokeObjectURL(url);
    setIsOpen(false);
  };

  // 3. Export BibTeX
  const exportBibTeX = () => {
    const seenPaperIds = new Set<string>();
    let bib = `% ResearchLens BibTeX Export for query: ${query}\n\n`;

    gaps.forEach((g) => {
      g.supporting_papers.forEach((p) => {
        if (!seenPaperIds.has(p.paper_id)) {
          seenPaperIds.add(p.paper_id);
          const firstAuthor = (p.authors[0] || "Author").split(" ").pop()?.toLowerCase() || "scholar";
          const citeKey = `${firstAuthor}${p.year || "2024"}_${p.paper_id.slice(0, 4)}`;
          bib += `@article{${citeKey},\n`;
          bib += `  title = {${p.title}},\n`;
          bib += `  author = {${p.authors.join(" and ")}},\n`;
          if (p.year) bib += `  year = {${p.year}},\n`;
          if (p.venue) bib += `  journal = {${p.venue}},\n`;
          if (p.doi) bib += `  doi = {${p.doi}},\n`;
          if (p.url) bib += `  url = {${p.url}},\n`;
          bib += `}\n\n`;
        }
      });
    });

    const blob = new Blob([bib], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `researchlens-citations-${query.replace(/\s+/g, "_").toLowerCase()}.bib`;
    a.click();
    URL.revokeObjectURL(url);
    setIsOpen(false);
  };

  const copyPermalink = () => {
    if (typeof window !== "undefined") {
      navigator.clipboard.writeText(window.location.href);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
      setIsOpen(false);
    }
  };

  return (
    <div className="relative">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="text-[13px] text-[var(--color-text-muted)] hover:text-[var(--color-text)] transition-colors px-2.5 py-1.5 rounded-[6px] border border-[var(--color-border)] hover:border-[var(--color-border-subtle)] bg-[var(--color-surface)] flex items-center gap-1.5"
        aria-label="Export options"
      >
        <span>Export</span>
        <svg className="w-3 h-3 text-[var(--color-text-faint)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {isOpen && (
        <div
          className="absolute right-0 mt-1 w-48 bg-[var(--color-surface)] border border-[var(--color-border)] rounded-[6px] shadow-sm py-1 z-50 text-[13px]"
          onMouseLeave={() => setIsOpen(false)}
        >
          <button
            onClick={exportMarkdown}
            className="w-full text-left px-3 py-1.5 hover:bg-[var(--color-surface-2)] text-[var(--color-text)] transition-colors flex items-center justify-between"
          >
            <span>Markdown report (.md)</span>
          </button>
          <button
            onClick={exportCSV}
            className="w-full text-left px-3 py-1.5 hover:bg-[var(--color-surface-2)] text-[var(--color-text)] transition-colors flex items-center justify-between"
          >
            <span>Spreadsheet table (.csv)</span>
          </button>
          <button
            onClick={exportBibTeX}
            className="w-full text-left px-3 py-1.5 hover:bg-[var(--color-surface-2)] text-[var(--color-text)] transition-colors flex items-center justify-between"
          >
            <span>BibTeX citations (.bib)</span>
          </button>
          <div className="border-t border-[var(--color-border)] my-1" />
          <button
            onClick={copyPermalink}
            className="w-full text-left px-3 py-1.5 hover:bg-[var(--color-surface-2)] text-[var(--color-accent)] transition-colors flex items-center justify-between"
          >
            <span>{copied ? "Link copied!" : "Copy permalink"}</span>
          </button>
        </div>
      )}
    </div>
  );
}
