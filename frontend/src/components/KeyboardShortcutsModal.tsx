"use client";

interface KeyboardShortcutsModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export function KeyboardShortcutsModal({ isOpen, onClose }: KeyboardShortcutsModalProps) {
  if (!isOpen) return null;

  const shortcuts = [
    { key: "/", desc: "Focus topic search input" },
    { key: "j / k", desc: "Navigate next / previous gap row" },
    { key: "Enter", desc: "Open supporting evidence drawer for selected gap" },
    { key: "Esc", desc: "Close drawer or dismiss modal" },
    { key: "?", desc: "Toggle this shortcut cheatsheet" },
  ];

  return (
    <div
      className="fixed inset-0 z-50 bg-black/40 backdrop-blur-[2px] flex items-center justify-center p-4 animate-fade-in"
      onClick={onClose}
    >
      <div
        className="w-full max-w-sm bg-[var(--color-surface)] border border-[var(--color-border)] rounded-[8px] p-6 shadow-sm space-y-4"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-[var(--color-border)] pb-3">
          <h3 className="font-serif-editorial text-[18px] text-[var(--color-text)]">
            Keyboard Shortcuts
          </h3>
          <button
            onClick={onClose}
            className="text-[var(--color-text-faint)] hover:text-[var(--color-text)] text-xs p-1"
            aria-label="Close"
          >
            ✕
          </button>
        </div>

        <div className="space-y-2.5 text-[13px]">
          {shortcuts.map((s) => (
            <div key={s.key} className="flex items-center justify-between">
              <span className="text-[var(--color-text-muted)]">{s.desc}</span>
              <kbd className="font-mono text-[11px] bg-[var(--color-surface-2)] text-[var(--color-text)] border border-[var(--color-border)] px-1.5 py-0.5 rounded-[4px] tabular-nums">
                {s.key}
              </kbd>
            </div>
          ))}
        </div>

        <div className="pt-2 text-right">
          <button
            onClick={onClose}
            className="text-[12px] text-[var(--color-text-muted)] hover:text-[var(--color-text)] px-3 py-1 border border-[var(--color-border)] rounded-[6px]"
          >
            Dismiss
          </button>
        </div>
      </div>
    </div>
  );
}
