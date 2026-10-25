"use client";

import { useState } from "react";

interface EvidenceMeterProps {
  strength: "strong" | "moderate" | "preliminary";
  showLabel?: boolean;
}

export function EvidenceMeter({ strength, showLabel = true }: EvidenceMeterProps) {
  const [showTooltip, setShowTooltip] = useState(false);

  const dots = {
    strong: 3,
    moderate: 2,
    preliminary: 1,
  }[strength] || 2;

  const label = {
    strong: "Strong evidence",
    moderate: "Moderate evidence",
    preliminary: "Preliminary evidence",
  }[strength] || "Moderate evidence";

  return (
    <div
      className="relative inline-flex items-center gap-1.5 cursor-help"
      onMouseEnter={() => setShowTooltip(true)}
      onMouseLeave={() => setShowTooltip(false)}
      onFocus={() => setShowTooltip(true)}
      onBlur={() => setShowTooltip(false)}
      tabIndex={0}
      aria-label={`Evidence strength: ${label}`}
    >
      <div className="flex items-center gap-1">
        {[1, 2, 3].map((idx) => {
          const filled = idx <= dots;
          return (
            <span
              key={idx}
              className={`w-1.5 h-1.5 rounded-full transition-colors ${
                filled
                  ? "bg-[var(--color-accent)]"
                  : "bg-[var(--color-border)]"
              }`}
            />
          );
        })}
      </div>

      {showLabel && (
        <span className="text-[12px] text-[var(--color-text-muted)] font-normal">
          {label}
        </span>
      )}

      {/* Tooltip */}
      {showTooltip && (
        <div className="absolute bottom-full mb-1.5 left-1/2 -translate-x-1/2 z-50 px-2 py-1 bg-[var(--color-surface-2)] text-[var(--color-text)] border border-[var(--color-border)] rounded-[4px] text-[11px] whitespace-nowrap shadow-sm pointer-events-none">
          {dots === 3 && "Corroborated by 3+ independent peer-reviewed publications."}
          {dots === 2 && "Reported with direct supporting passages across 2 papers."}
          {dots === 1 && "Observed as an emerging direction or single-study author finding."}
        </div>
      )}
    </div>
  );
}
