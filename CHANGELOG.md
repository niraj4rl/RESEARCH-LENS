# Changelog — ResearchLens Production Redesign & Hardening

All notable changes made to ResearchLens as part of the editorial redesign and production-hardening initiative.

## [2.0.0] - 2026-10-25

### Design Direction & Aesthetic ("Quiet Research Library at Night")
- **Monochrome & Amber Color System**: Replaced rainbow badges, glow borders, glassmorphic blurs, and saturated badge pills with a restrained palette. Single accent color: muted ink-gold/amber (`#D9A441` dark, `#B07A12` light).
- **Persistent Theme Toggle**: Seamless light/dark mode switcher with zero-flash inline script before hydration, stored in `localStorage`.
- **Editorial Typography**: Integrated `Newsreader` (editorial serif) for headlines and gap titles, `Inter` for UI body, and `JetBrains Mono` for tabular numeric metadata (years, citations, IDs).
- **Single-Column Editorial List**: Replaced 3-column boxed card grid with a clean, single-column editorial list. Each item features an index number (`01`, `02`), serif title, 2-line clamped statement, and right-aligned metadata.
- **3-Dot Evidence Meter**: Replaced rainbow confidence pills with a 3-dot accent meter (`●●● strong`, `●●○ moderate`, `●○○ preliminary`) accompanied by an explanatory scoring tooltip.
- **Quiet Landing Page**: Centered layout with a single serif headline, focused search input with popover query filters, underlined example topics, and an expandable "How it works" methodology note. Honest source attribution moved to the footer.

### Motion & Micro-Interactions (`motion`)
- **Vertical Pipeline Stepper**: Replaced generic spinner with a 4-step real-time pipeline stepper (Retrieving → Extracting evidence → Synthesising gaps → Verifying citations) with active progress lines, checkmarks, and live ticking paper counts.
- **Matching Skeleton Pulse**: Skeleton placeholder rows mirror the exact single-column list layout with a gentle 1.6s opacity pulse.
- **Slide-Over Evidence Drawer**: Right-side sheet (`min(720px, 90vw)`) with collapsible paper citations and verbatim extracted passages.
- **Inspect Literature Drawer**: Dedicated drawer to inspect all raw papers retrieved in the corpus with venue and citation stats.
- **Keyboard Navigation**:
  - `/` : Focuses search input.
  - `j` / `k` : Move up and down through research gaps.
  - `Enter` : Opens evidence drawer for the selected gap.
  - `Esc` : Closes open drawers or modals.
  - `?` : Opens the keyboard shortcuts cheatsheet modal.

### Backend Gap Discovery & Quality Upgrades
- **Natural Sentence Titles**: Replaced raw keyword tuples (e.g., `"Methodological Bottlenecks in Scale, Large, Based"`) with n-gram phrase extraction and natural sentence gap generation.
- **TF-IDF Semantic Relevance Filtering**: Integrated query-to-paper cosine similarity scoring to eliminate semantic outliers (such as mechanical lathe tools appearing for "machine learning").
- **Evidence-Grounded Extraction**: Extracted passages are grounded strictly in paper abstracts, requiring verbatim sentence support.
- **Deduplication**: Gap claims are clustered and de-duplicated by cosine similarity to prevent repetitive entries.

### Export & Sharing
- **Multi-Format Export Menu**:
  - BibTeX (`.bib`) export for LaTeX bibliographies.
  - CSV (`.csv`) export for spreadsheet review.
  - Markdown (`.md`) formatted synthesis summary.
  - Permalink copying for sharing analyses.
- **One-Click Citation Copying**: Format-compliant citation copying for any supporting paper.

### Architecture, Security & Testing
- **Unified One-Command Startup**: Root `run.py`, `start.bat`, and `start.ps1` launch both FastAPI and Next.js concurrently.
- **Database Resilience**: Auto-migration ensures existing Postgres and SQLite databases migrate seamlessly with fallback connection logic.
- **Security Headers**: Added `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin`, and `Permissions-Policy`.
- **Automated Test Suite**: Full pytest suite covering API health, query validation, end-to-end analysis flow, evidence extraction, cross-paper synthesis, and deduplication (`9 passed`). Next.js production build passes with zero TypeScript errors.

---

### Items Outside Current Scope / Future Enhancements
- Live background worker queue via Celery / Redis (currently uses FastAPI background tasks with Server-Sent Events / progress polling, which works reliably in single-node setup).
- Official Google Scholar API integration (omitted because Google Scholar provides no official public API; OpenAlex, arXiv, and Semantic Scholar are the active compliant providers).
