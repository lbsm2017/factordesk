import type { CSSProperties } from "react";

/** The colour token of an asset class in the composer (the `--ac-*` palette of tokens.css). */
const TOKENS: Record<string, string> = {
  Equities: "var(--ac-equities)",
  "Fixed Income": "var(--ac-fixed)",
  Alternatives: "var(--ac-alts)",
  "Real Estate": "var(--ac-real)",
  Commodities: "var(--ac-comm)",
  Cash: "var(--ac-cash)",
};

export function assetClassColor(name: string): string {
  return TOKENS[name] ?? "var(--ac-other)";
}

/** Inline custom properties (`--c`, `--p`, `--v`) for the key squares, bars and stacked segments. */
export function cssVars(vars: Record<string, string | number>): CSSProperties {
  return vars as CSSProperties;
}
