"use client";

import { useEffect, useState } from "react";

export function ThemeToggle() {
  const [theme, setTheme] = useState<"dark" | "light">("dark");
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    const isDark = document.documentElement.classList.contains("dark");
    setTheme(isDark ? "dark" : "light");
  }, []);

  const toggleTheme = () => {
    const nextTheme = theme === "dark" ? "light" : "dark";
    setTheme(nextTheme);
    if (nextTheme === "dark") {
      document.documentElement.classList.add("dark");
      document.documentElement.classList.remove("light");
    } else {
      document.documentElement.classList.remove("dark");
      document.documentElement.classList.add("light");
    }
    localStorage.setItem("researchlens_theme", nextTheme);
  };

  if (!mounted) {
    return <div className="w-12 h-6" />;
  }

  return (
    <button
      onClick={toggleTheme}
      type="button"
      className="text-xs text-[var(--color-text-muted)] hover:text-[var(--color-text)] transition-colors px-2 py-1 rounded-[6px] border border-[var(--color-border)] hover:border-[var(--color-border-subtle)] bg-[var(--color-surface)] flex items-center gap-1.5 focus:outline-none focus:ring-1 focus:ring-[var(--color-accent)]"
      aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
    >
      <span className="w-1.5 h-1.5 rounded-full bg-[var(--color-accent)]" />
      <span className="capitalize">{theme === "dark" ? "Light" : "Dark"}</span>
    </button>
  );
}
