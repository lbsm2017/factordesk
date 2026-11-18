/** Plain-language text ported from docs/design/prototype/build_prototype.py (design gaps H.2, H.3, H.9). */
import type { FactorStat, ReportWarning } from "../api/types";
import { num, signed } from "../format/numbers";

/** Plain factor names (H.3). */
export const PLAIN: Record<string, string> = {
  "Mkt-RF": "Market",
  SMB: "Size",
  HML: "Value",
  RMW: "Profitability",
  CMA: "Investment",
};

/** Plain one-sentence warning summaries by code (H.9). Unknown codes fall back to `message`. */
export const WARN_PLAIN: Record<string, string> = {
  residual_reversal:
    "Prices look out of step with the factor data, so R² is probably understated and residual volatility overstated.",
  short_history: "The history is short, so the betas rest on a small sample.",
  collinearity: "Some factors move together in this sample, so single betas are less precise.",
  audit_errors:
    "The price audit found errors, so the headline numbers are not interpretable until they are explained; see Data and audit.",
  audit_warnings: "The price audit flagged some unusual price moves; see Data and audit.",
  factor_data_lag:
    "The factor data stops before the latest prices, so the newest days are charted but not analysed.",
};

/** [positive beta, negative beta] tilt phrases (H.2). The market factor has its own wording. */
export const TILT: Record<string, readonly [string, string]> = {
  SMB: ["small companies", "large companies"],
  HML: ["value stocks", "growth stocks"],
  RMW: ["highly profitable firms", "weakly profitable firms"],
  CMA: ["firms that invest conservatively", "firms that invest aggressively"],
};

/** Reader-facing word for an estimate tag: "significant" or "not significant" (never "reliable" or "noise"). */
export function tagText(tag: string | null | undefined): string {
  if (tag === "reliable") return "significant";
  if (tag === "noise") return "not significant";
  return "n/a";
}

export function plainName(name: string): string {
  return PLAIN[name] ?? name;
}

export function warningText(warning: ReportWarning): string {
  return WARN_PLAIN[warning.code] ?? warning.message;
}

/** Summary of up to the first two warnings, joined by a space. */
export function warningSummary(warnings: readonly ReportWarning[]): string {
  return warnings.slice(0, 2).map(warningText).join(" ");
}

/** The reading line of the exposures panel (H.2). */
export function exposureReading(factors: readonly FactorStat[]): string {
  const parts: string[] = [];
  const quiet: string[] = [];
  for (const f of factors) {
    const { name, beta } = f;
    if (f.tag !== "reliable" || beta === null) {
      quiet.push(`${plainName(name).toLowerCase()} (${name})`);
      continue;
    }
    if (name === "Mkt-RF") {
      if (Math.abs(beta - 1) < 0.1) parts.push(`moves roughly one-for-one with the market (beta ${num(beta)})`);
      else if (beta > 1) parts.push(`amplifies market moves (beta ${num(beta)})`);
      else parts.push(`moves less than the market (beta ${num(beta)})`);
    } else {
      const tilt = TILT[name];
      if (tilt) parts.push(`leans toward ${tilt[beta > 0 ? 0 : 1]} (${name} ${signed(beta)})`);
    }
  }
  let s = "";
  if (parts.length) {
    const body = parts.length > 1 ? `${parts.slice(0, -1).join(", ")} and ${parts[parts.length - 1]}` : parts[0];
    s = `Over this window the stock ${body}.`;
  }
  if (quiet.length) {
    const q = quiet.length > 1 ? `${quiet.slice(0, -1).join(", ")} or ${quiet[quiet.length - 1]}` : quiet[0];
    s += ` There is no clear tilt to ${q}.`;
  }
  return s.trim();
}
