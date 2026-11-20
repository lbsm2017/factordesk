/**
 * Verdict sentence and "Reading" words of the Summary panel (dashboard v2 spec DV4). Pure
 * functions of `FactorReport`. Significance comes only from the tags the report already carries
 * (`tag`, `alpha_tag`, the Sharpe interval flag); nothing here tests anything.
 */
import type { FactorReport, FactorStat, PerformanceSection, WorldBetaSection } from "../api/types";
import { dateLong, num, pct, signed } from "../format";
import { countWord, factorCount } from "../report/derive";
import { isLean, TILT } from "./plain";

const STYLE_ORDER = ["SMB", "HML", "RMW", "CMA"] as const;
const WORD_LIMIT = 40;

const GATE_HEDGE =
  "Its closing prices look out of step with the factor data, so the share the model explains is probably understated.";

function fin(x: number | null | undefined): x is number {
  return typeof x === "number" && Number.isFinite(x);
}

function times(b: number): string {
  return num(b, 2);
}

/** Two items "a and b"; three or more "a, b and c" (no serial comma). */
function list(items: readonly string[]): string {
  if (items.length <= 1) return items.join("");
  return `${items.slice(0, -1).join(", ")} and ${items[items.length - 1]}`;
}

/** Headline join: the parts contain "and" themselves, so three parts take a serial comma. */
function headlineJoin(parts: readonly string[]): string {
  if (parts.length <= 1) return parts.join("");
  if (parts.length === 2) return `${parts[0]} and ${parts[1]}`;
  return `${parts.slice(0, -1).join(", ")}, and ${parts[parts.length - 1]}`;
}

function wordCount(text: string): number {
  return text.split(" ").filter(Boolean).length;
}

function factorOf(report: FactorReport, name: string): FactorStat | undefined {
  return report.regression.factors.find((f) => f.name === name);
}

export function auditErrors(report: FactorReport): boolean {
  return report.data.audit_status === "errors";
}

/** The market beta reading band (DV4.2 item 6). Null when the beta or its tag is missing. */
export function marketPhrase(beta: number | null, tag: FactorStat["tag"]): string | null {
  if (beta === null || tag === null) return null;
  if (tag !== "reliable") return "shows no reliable link to the market";
  if (Math.abs(beta - 1) < 0.1 - 1e-9) return "moves with the market (about one-for-one)";
  if (beta >= 1.1) return `amplifies market moves (about ${times(beta)} times as much)`;
  if (beta > 0 && beta <= 0.9) return `moves less than the market (about ${times(beta)} times as much)`;
  if (beta < 0) return `tends to move against the market (about ${times(Math.abs(beta))} times as much, in the opposite direction)`;
  // A beta of exactly 0 has no band.
  return "shows no reliable link to the market";
}

interface Tilt {
  name: string;
  text: string;
  abs: number;
}

function reliableTilts(report: FactorReport): Tilt[] {
  const out: Tilt[] = [];
  for (const name of STYLE_ORDER) {
    const f = factorOf(report, name);
    const pair = TILT[name];
    // The lean floor of the exposures reading: reliable and not negligible (|beta| >= MIN_LEAN).
    if (!f || !pair || !isLean(f) || !fin(f.beta)) continue;
    out.push({ name, text: pair[f.beta > 0 ? 0 : 1], abs: Math.abs(f.beta) });
  }
  return out;
}

function stylePart(tilts: readonly Tilt[]): string {
  if (tilts.length === 0) return "has no clear tilt toward size, value, profitability or investment";
  return `leans toward ${list(tilts.map((t) => t.text))}`;
}

/** Part S shortened to the largest tilts (canonical order) and a count of the others. */
function shortStylePart(tilts: readonly Tilt[], keepCount: number): string {
  const keep = new Set(
    [...tilts]
      .sort((a, b) => b.abs - a.abs)
      .slice(0, keepCount)
      .map((t) => t.name),
  );
  const shown = tilts.filter((t) => keep.has(t.name)).map((t) => t.text);
  const others = tilts.length - shown.length;
  if (others > 0) shown.push(`${others} other style ${others === 1 ? "tilt" : "tilts"}`);
  return `leans toward ${list(shown)}`;
}

function alphaPart(report: FactorReport): string | null {
  const { alpha_annual: a, alpha_tag: tag } = report.regression;
  if (!fin(a)) return null;
  if (tag === "reliable" && a > 0) return `earned ${pct(a, 1, false)} a year more than its exposures explain over this range`;
  if (tag === "reliable" && a < 0) {
    return `earned ${pct(Math.abs(a), 1, false)} a year less than its exposures explain over this range`;
  }
  return "shows no reliable return beyond its exposures";
}

export interface Verdict {
  /** The headline sentence (or the audit-error pair of sentences, or the could-not-fit sentence). */
  headline: string;
  /** The quality-gate hedge sentence, or null. */
  hedge: string | null;
  /** Headline and hedge as one text. */
  text: string;
}

function done(headline: string, hedge: string | null): Verdict {
  return { headline, hedge, text: hedge ? `${headline} ${hedge}` : headline };
}

/** The verdict of DV4.4. */
export function verdict(report: FactorReport): Verdict {
  const t = report.ticker;
  const reg = report.regression;
  if (reg.status !== "ok") {
    const reason = (reg.reason ?? "no reason was given").replace(/\.+$/, "");
    return done(`factordesk could not fit the ${countWord(factorCount(report))}-factor model for ${t} over this range: ${reason}.`, null);
  }
  const mkt = factorOf(report, "Mkt-RF");
  const m = marketPhrase(mkt?.beta ?? null, mkt?.tag ?? null);
  const tilts = reliableTilts(report);
  const s = stylePart(tilts);

  if (auditErrors(report)) {
    const parts = [m, s].filter((p): p is string => p !== null);
    return done(
      `The price audit found errors in ${t}'s prices, so these results are not interpretable until the errors are explained. ` +
        `Taken at face value, ${t} ${headlineJoin(parts)}.`,
      null,
    );
  }

  const a = alphaPart(report);
  const build = (style: string): string => {
    const parts = [m, style, a].filter((p): p is string => p !== null);
    return `${t} ${headlineJoin(parts)}.`;
  };
  let headline = build(s);
  if (wordCount(headline) > WORD_LIMIT && tilts.length > 2) headline = build(shortStylePart(tilts, 2));
  if (wordCount(headline) > WORD_LIMIT && tilts.length > 1) headline = build(shortStylePart(tilts, 1));
  return done(headline, report.quality_gate.fired ? GATE_HEDGE : null);
}

// ---------------------------------------------------------------- Reading column

/** `clear` rows are drawn in weight 600, `noise` rows in normal weight, `none` rows carry no test. */
export type Evidence = "clear" | "noise" | "none";

export interface Reading {
  word: string;
  evidence: Evidence;
  /** One-line detail for the title attribute. */
  note?: string | undefined;
}

const AUDIT_NOTE = "The price audit found errors, so this is not interpretable.";
const GATE_NOTE = "Closing prices look out of step with the factor data.";
const NO_TEST: Reading = { word: "–", evidence: "none" };

/** Clear evidence or could be noise from an existing tag; audit errors replace both with "Unconfirmed". */
function judged(clear: boolean | null, audit: boolean, note?: string): Reading {
  if (audit) return { word: "Unconfirmed", evidence: "noise", note: AUDIT_NOTE };
  if (clear === null) return { word: "n/a", evidence: "none", note: "Significance is not available." };
  return { word: clear ? "Clear evidence" : "Could be noise", evidence: clear ? "clear" : "noise", note };
}

const isClear = (tag: FactorStat["tag"]): boolean | null => (tag === null ? null : tag === "reliable");

export function alphaReading(report: FactorReport): Reading {
  const tag = report.regression.alpha_tag;
  return judged(isClear(tag), auditErrors(report), tag === "noise" ? (report.regression.alpha_sentence ?? undefined) : undefined);
}

export function betaReading(report: FactorReport, name: string): Reading {
  return judged(isClear(factorOf(report, name)?.tag ?? null), auditErrors(report));
}

/** Gate and audit hedges for the two figures the quality gate biases; `bands` reads the plain value. */
function hedged(report: FactorReport, understated: boolean, band: () => string): Reading {
  if (auditErrors(report)) return { word: "Unconfirmed", evidence: "none", note: AUDIT_NOTE };
  if (report.quality_gate.fired) {
    return { word: understated ? "Probably understated" : "Probably overstated", evidence: "none", note: GATE_NOTE };
  }
  return { word: band(), evidence: "none" };
}

/** R-squared: bands are descriptive reading words; the gate hedge replaces them (DV4.5). */
export function r2Reading(report: FactorReport): Reading {
  const r2 = report.regression.r2;
  return fin(r2) ? hedged(report, true, () => (r2 >= 0.9 ? "Very high" : r2 >= 0.7 ? "High" : r2 >= 0.4 ? "Moderate" : "Low")) : NO_TEST;
}

/** Residual volatility against the total volatility of the stock. */
export function residualVolReading(report: FactorReport): Reading {
  const s = report.regression.sigma_e_annual;
  const total = report.risk_contribution?.total_vol_annual;
  if (!fin(s) || !fin(total) || total <= 0) return NO_TEST;
  return hedged(report, false, () => (s / total < 0.25 ? "Low" : s / total < 0.5 ? "Moderate" : "High"));
}

/** Sharpe ratio: "Could be noise" whenever the 95% interval includes zero (owner rule). */
export function sharpeReading(sharpe: PerformanceSection["sharpe"], report?: FactorReport): Reading {
  const zero = sharpe?.ci_includes_zero;
  if (!sharpe || !fin(sharpe.ratio_annual) || typeof zero !== "boolean") {
    return { word: "–", evidence: "none", note: "No interval available." };
  }
  const note = zero ? "Cannot be told apart from zero." : `${(sharpe.ci95_low ?? 0) > 0 ? "Above" : "Below"} zero at the 5% level.`;
  return judged(!zero, report ? auditErrors(report) : false, note);
}

/** Largest fall: "Recovered" or "Not recovered", with the dates in the note (DV4.7). */
export function drawdownReading(section: PerformanceSection): Reading {
  const d = section.drawdown;
  if (!d?.peak_date || !d.trough_date) return NO_TEST;
  const span = `From ${dateLong(d.peak_date)} to ${dateLong(d.trough_date)}; `;
  if (d.recovery_date) return { word: "Recovered", evidence: "none", note: `${span}back at the peak by ${dateLong(d.recovery_date)}` };
  const end = section.periods?.end;
  return { word: "Not recovered", evidence: "none", note: `${span}not recovered${end ? ` by ${dateLong(end)}` : ""}` };
}

const COMPARED = { higher: "higher than", lower: "lower than", about_the_same: "about the same as" } as const;

/** The beta against the ACWI fund: the backend's interval decides, as for the Sharpe ratio. */
export function worldBetaReading(section: WorldBetaSection, report: FactorReport): Reading {
  const w = section.world;
  if (!w) return NO_TEST;
  const us = section.us_market?.beta;
  const phrase = section.comparison ? COMPARED[section.comparison] : null;
  const note = phrase && fin(us) ? `${phrase} its one-factor US market beta of ${times(us)}` : undefined;
  return judged(w.ci_low > 0 || w.ci_high < 0, auditErrors(report), note);
}

// ---------------------------------------------------------------- number formats for the tables

/** "−1.5% to +3.2%" */
export function pctRange(lo: number, hi: number, digits = 1): string {
  return `${pct(lo, digits)} to ${pct(hi, digits)}`;
}

/** "+0.99 to +1.00" */
export function signedRange(lo: number, hi: number, digits = 2): string {
  return `${signed(lo, digits)} to ${signed(hi, digits)}`;
}
