"use client";

import { motion } from "motion/react";

export interface EvidencePassage {
  text: string;
  section?: string | null;
  page?: number | null;
  source_scope?: string | null;
}

export interface SupportingPaper {
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

export interface ResearchGap {
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

export const CATEGORY_NAMES: Record<string, string> = {
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

export interface GapCardProps {
  gap: ResearchGap;
  index: number;
  isActive: boolean;
  onSelect: () => void;
  categoryNames?: Record<string, string>;
}

export function GapCard({
  gap,
  index,
  isActive,
  onSelect,
  categoryNames = CATEGORY_NAMES,
}: GapCardProps) {
  const indexLabel = String(index + 1).padStart(2, "0");
  const catLabel = categoryNames[gap.category] || "Open Gap";

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.24, delay: Math.min(index * 0.04, 0.4) }}
      onClick={onSelect}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onSelect();
        }
      }}
      className={`group p-5 rounded-[8px] border transition-all cursor-pointer flex flex-col justify-between space-y-4 ${
        isActive
          ? "bg-[var(--color-surface)] border-[var(--color-accent)] ring-1 ring-[var(--color-accent)]"
          : "bg-[var(--color-surface)] border-[var(--color-border)] hover:border-[var(--color-accent)]"
      }`}
      tabIndex={0}
      role="button"
      aria-label={`Gap ${indexLabel}: ${gap.title}`}
    >
      {/* Top Meta Row - Clean header with index and category only */}
      <div className="space-y-2">
        <div className="flex items-center gap-2 text-[12px]">
          <span className="font-mono text-[var(--color-text-faint)] text-[11px] tabular-nums">
            {indexLabel}
          </span>
          <span className="font-medium text-[var(--color-text)]">
            {catLabel}
          </span>
        </div>

        {/* Gap Title */}
        <h3 className="text-[17px] font-serif-editorial text-[var(--color-text)] group-hover:text-[var(--color-accent)] transition-colors leading-snug">
          {gap.title}
        </h3>

        {/* Concise Gap Statement (Clamped) */}
        <p className="text-[13.5px] text-[var(--color-text-muted)] line-clamp-3 leading-relaxed">
          {gap.statement}
        </p>
      </div>

      {/* Supporting Paper Information & Clickable Paper Titles */}
      <div className="pt-2 border-t border-[var(--color-border-subtle)] space-y-2">
        <div className="text-[11px] font-mono text-[var(--color-text-faint)] flex items-center justify-between">
          <span>
            {gap.supporting_paper_count} {gap.supporting_paper_count === 1 ? "paper" : "papers"}
          </span>
          {gap.source_coverage && (
            <span className="truncate max-w-[150px]">{gap.source_coverage}</span>
          )}
        </div>

        {/* Clickable paper links */}
        <div className="space-y-1">
          {gap.supporting_papers.slice(0, 2).map((p) => {
            const verifiedLink = p.doi ? `https://doi.org/${p.doi}` : p.url || p.pdf_url;
            return (
              <div key={p.paper_id} className="text-[12px] truncate">
                {verifiedLink ? (
                  <a
                    href={verifiedLink}
                    target="_blank"
                    rel="noopener noreferrer"
                    onClick={(e) => e.stopPropagation()}
                    className="text-[var(--color-text-muted)] hover:text-[var(--color-accent)] hover:underline inline-flex items-center gap-1 truncate max-w-full"
                    title={p.title}
                  >
                    <span className="shrink-0 text-[10px]">↗</span>
                    <span className="truncate">{p.title}</span>
                    {p.year && <span className="text-[var(--color-text-faint)] shrink-0">({p.year})</span>}
                  </a>
                ) : (
                  <span className="text-[var(--color-text-muted)] truncate block" title={p.title}>
                    • {p.title} {p.year && `(${p.year})`}
                  </span>
                )}
              </div>
            );
          })}
          {gap.supporting_papers.length > 2 && (
            <span className="text-[11px] text-[var(--color-text-faint)] block">
              +{gap.supporting_papers.length - 2} more supporting {gap.supporting_papers.length - 2 === 1 ? "study" : "studies"}
            </span>
          )}
        </div>

        {/* Card Action */}
        <div className="pt-2 flex items-center justify-between text-[12px] text-[var(--color-text-faint)]">
          <span>Inspect evidence</span>
          <span className="text-[var(--color-accent)] group-hover:translate-x-1 transition-transform">→</span>
        </div>
      </div>
    </motion.div>
  );
}
