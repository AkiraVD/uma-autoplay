import { useEffect, useState } from "react";

export type Theme = "light" | "dark" | "system";

// index.html reads the same key and default in a small inline script, so the
// page is dark before React loads instead of flashing white first. Keep the
// two in step.
export const THEME_STORAGE_KEY = "uma-theme";
export const DEFAULT_THEME: Theme = "dark";

const darkQuery = () => window.matchMedia("(prefers-color-scheme: dark)");

function readStoredTheme(): Theme {
  try {
    const stored = localStorage.getItem(THEME_STORAGE_KEY);
    if (stored === "light" || stored === "dark" || stored === "system") return stored;
  } catch {
    // Storage can be blocked (a private window); use the default instead.
  }
  return DEFAULT_THEME;
}

function applyTheme(theme: Theme) {
  const dark = theme === "dark" || (theme === "system" && darkQuery().matches);
  document.documentElement.classList.toggle("dark", dark);
}

export function useTheme() {
  const [theme, setTheme] = useState<Theme>(readStoredTheme);

  useEffect(() => {
    applyTheme(theme);
    try {
      localStorage.setItem(THEME_STORAGE_KEY, theme);
    } catch {
      // Not remembered for the next visit, but still applied for this one.
    }
    if (theme !== "system") return;
    // Follow the OS switching between light and dark while the page is open.
    const query = darkQuery();
    const onChange = () => applyTheme("system");
    query.addEventListener("change", onChange);
    return () => query.removeEventListener("change", onChange);
  }, [theme]);

  return { theme, setTheme };
}
