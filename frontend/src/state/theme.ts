import { useCallback, useState } from "react";

/** The three choices of the theme switch. `system` follows the operating system setting. */
export type ThemeChoice = "system" | "light" | "dark";

export const THEME_CHOICES: readonly ThemeChoice[] = ["system", "light", "dark"];

/** `localStorage` key of the last choice. */
export const THEME_KEY = "factordesk.theme";

export function parseTheme(raw: string | null): ThemeChoice {
  return raw === "light" || raw === "dark" ? raw : "system";
}

/** The stored choice. Storage can throw (private windows, blocked site data): then it is `system`. */
export function readTheme(): ThemeChoice {
  try {
    return parseTheme(window.localStorage.getItem(THEME_KEY));
  } catch {
    return "system";
  }
}

function writeTheme(choice: ThemeChoice): void {
  try {
    if (choice === "system") window.localStorage.removeItem(THEME_KEY);
    else window.localStorage.setItem(THEME_KEY, choice);
  } catch {
    /* the choice still holds for this page view */
  }
}

/**
 * Put the choice on `<html data-theme>`. With `system` the attribute is removed, and tokens.css
 * follows `prefers-color-scheme` by itself.
 */
export function applyTheme(choice: ThemeChoice): void {
  const root = document.documentElement;
  if (choice === "system") root.removeAttribute("data-theme");
  else root.setAttribute("data-theme", choice);
}

/** The theme choice and its setter; a change is applied to the page and stored at once. */
export function useTheme(): readonly [ThemeChoice, (choice: ThemeChoice) => void] {
  const [choice, setChoice] = useState<ThemeChoice>(readTheme);
  const select = useCallback((next: ThemeChoice) => {
    setChoice(next);
    applyTheme(next);
    writeTheme(next);
  }, []);
  return [choice, select];
}
