/** Chart colours come from the CSS custom properties of tokens.css, never from literals. */
import { useEffect, useState } from "react";

export interface ChartTokens {
  surface: string;
  sunk: string;
  grid: string;
  axis: string;
  ink: string;
  ink2: string;
  ink3: string;
  pos: string;
  neg: string;
  /** Factor hues f1 to f5 in canonical order (Mkt-RF, SMB, HML, RMW, CMA). */
  factors: readonly [string, string, string, string, string];
  sans: string;
}

/** Smallest text size in px anywhere on the page, chart text included (design rev 3). */
export const CHART_FONT_PX = 14;

const FALLBACK = "currentColor";

/** Read the tokens from `element` (default: the document root). Empty values fall back to currentColor. */
export function readChartTokens(element: Element = document.documentElement): ChartTokens {
  const style = getComputedStyle(element);
  const get = (name: string): string => style.getPropertyValue(name).trim() || FALLBACK;
  return {
    surface: get("--surface"),
    sunk: get("--sunk"),
    grid: get("--grid"),
    axis: get("--axis"),
    ink: get("--ink"),
    ink2: get("--ink-2"),
    ink3: get("--ink-3"),
    pos: get("--pos"),
    neg: get("--neg"),
    factors: [get("--f1"), get("--f2"), get("--f3"), get("--f4"), get("--f5")],
    sans: get("--sans"),
  };
}

/** Tokens at mount, re-read when `prefers-color-scheme` changes. */
export function useChartTokens(): ChartTokens {
  const [tokens, setTokens] = useState<ChartTokens>(() => readChartTokens());
  useEffect(() => {
    if (typeof window.matchMedia !== "function") return;
    const query = window.matchMedia("(prefers-color-scheme: dark)");
    const update = () => setTokens(readChartTokens());
    query.addEventListener("change", update);
    return () => query.removeEventListener("change", update);
  }, []);
  return tokens;
}
