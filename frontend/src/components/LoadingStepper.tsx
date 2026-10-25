"use client";

import { motion } from "motion/react";

interface LoadingStepperProps {
  stage?: string | null;
  papersRetrieved?: number;
  papersAnalysed?: number;
  query: string;
}

const STAGES = [
  { id: "retrieving", label: "Retrieving literature across OpenAlex, arXiv & Semantic Scholar", detail: "Querying peer-reviewed repositories" },
  { id: "analyzing", label: "Extracting evidence & limitations", detail: "Parsing problem formulations, constraints & benchmarks" },
  { id: "synthesizing", label: "Synthesising cross-paper research gaps", detail: "Clustering recurring constraints across independent studies" },
  { id: "validating", label: "Verifying citation provenance", detail: "Grounding claims directly in verified paper passages" },
];

export function LoadingStepper({
  stage,
  papersRetrieved = 0,
  papersAnalysed = 0,
  query,
}: LoadingStepperProps) {
  // Determine current active step index
  const stageOrder = ["queued", "retrieving", "analyzing", "synthesizing", "validating", "completed"];
  const currentIdx = Math.max(0, stageOrder.indexOf(stage || "queued") - 1);

  return (
    <div className="max-w-2xl mx-auto py-12 px-4 space-y-10">
      {/* Header */}
      <div className="space-y-2 text-left">
        <span className="text-[12px] font-mono text-[var(--color-text-faint)] uppercase tracking-wider">
          Scholarly Synthesis in Progress
        </span>
        <h2 className="text-2xl sm:text-3xl font-serif-editorial text-[var(--color-text)]">
          {query}
        </h2>
      </div>

      {/* Vertical Stepper */}
      <div className="space-y-6 border-l border-[var(--color-border)] pl-6 relative">
        {STAGES.map((s, idx) => {
          const isDone = currentIdx > idx;
          const isActive = currentIdx === idx;
          const isPending = currentIdx < idx;

          return (
            <div key={s.id} className="relative group">
              {/* Step indicator dot/check on the line */}
              <div
                className={`absolute -left-[31px] top-1 w-4 h-4 rounded-full flex items-center justify-center transition-all ${
                  isDone
                    ? "bg-[var(--color-accent)] text-black"
                    : isActive
                    ? "bg-[var(--color-surface)] border-2 border-[var(--color-accent)]"
                    : "bg-[var(--color-surface)] border border-[var(--color-border)]"
                }`}
              >
                {isDone ? (
                  <svg className="w-2.5 h-2.5 stroke-black" viewBox="0 0 12 12" fill="none">
                    <path
                      d="M2.5 6L5 8.5L9.5 3.5"
                      strokeWidth="2"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                  </svg>
                ) : isActive ? (
                  <span className="w-1.5 h-1.5 rounded-full bg-[var(--color-accent)] animate-pulse" />
                ) : null}
              </div>

              {/* Step Text */}
              <div className="space-y-0.5">
                <div className="flex items-center gap-3">
                  <p
                    className={`text-[14px] font-medium transition-colors ${
                      isActive
                        ? "text-[var(--color-text)]"
                        : isDone
                        ? "text-[var(--color-text-muted)]"
                        : "text-[var(--color-text-faint)]"
                    }`}
                  >
                    {s.label}
                  </p>
                  {isActive && (
                    <span className="text-[11px] font-mono text-[var(--color-accent)] bg-[var(--color-accent-soft)] px-1.5 py-0.5 rounded-[4px]">
                      active
                    </span>
                  )}
                </div>

                <p className="text-[12px] text-[var(--color-text-faint)]">
                  {s.detail}
                </p>

                {/* Live Count Ticks on Retrieval */}
                {s.id === "retrieving" && (papersRetrieved > 0 || isActive) && (
                  <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    className="text-[12px] font-mono text-[var(--color-text-muted)] pt-1 tabular-nums"
                  >
                    → {papersRetrieved} papers retrieved from scholarly indices
                  </motion.div>
                )}

                {/* Live Count Ticks on Analysis */}
                {s.id === "analyzing" && (papersAnalysed > 0 || isDone) && (
                  <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    className="text-[12px] font-mono text-[var(--color-text-muted)] pt-1 tabular-nums"
                  >
                    → {papersAnalysed} candidate abstracts examined
                  </motion.div>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* Skeletons Matching Final Single-Column List */}
      <div className="pt-6 border-t border-[var(--color-border)] space-y-4">
        <span className="text-[11px] font-mono text-[var(--color-text-faint)] uppercase tracking-wider block">
          Generating editorial gaps
        </span>

        {[1, 2, 3].map((sk) => (
          <div
            key={sk}
            className="py-4 border-b border-[var(--color-border-subtle)] flex items-start justify-between gap-6 animate-pulse opacity-60"
            style={{ animationDuration: "1.6s" }}
          >
            <div className="flex items-start gap-4 flex-1">
              <span className="text-[12px] font-mono text-[var(--color-text-faint)]">0{sk}</span>
              <div className="space-y-2 flex-1">
                <div className="h-4 bg-[var(--color-surface-2)] rounded w-3/4" />
                <div className="h-3 bg-[var(--color-surface)] rounded w-full" />
                <div className="h-3 bg-[var(--color-surface)] rounded w-1/2" />
              </div>
            </div>
            <div className="w-20 h-3 bg-[var(--color-surface-2)] rounded shrink-0" />
          </div>
        ))}
      </div>
    </div>
  );
}
