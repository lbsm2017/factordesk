/**
 * Values the page derives from a FactorReport instead of reading them from a field (design H.13),
 * ported from backend/factordesk/report/render_html.py: nice axis domains, calendar ticks, factor
 * order and colour slots, and the rolling-beta summary (latest, mean, middle 80%, spread, lowest,
 * highest, share above zero) that the static report computes for the window with no
 * `average_beta` entry. For the primary window the report's own numbers are used and this module
 * only has to agree with them (tested within 1e-5).
 */
import type { FactorReport, RollingWindow } from "../api/types";
import { FACTOR_NAMES } from "../api/types";
import { parseIsoDate } from "../format/dates";

/** Normal quantile for a 95% band when the report carries none (backend HAC_DEFAULT_Z). */
export const DEFAULT_Z = 1.959963984540054;

/** Name of the stock-specific row in the risk table (backend IDIO). */
export const IDIO = "Idiosyncratic";

/** A finite number, else null (handles null, undefined, NaN and the infinities). */
export function finite(x: number | null | undefined): number | null {
  return typeof x === "number" && Number.isFinite(x) ? x : null;
}

// ---------------------------------------------------------------------------- factors

/** Factor names in display order: the regression's, else the return contribution's keys. */
export function factorOrder(report: FactorReport): string[] {
  const names = report.regression.factors.map((f) => f.name);
  return names.length ? names : Object.keys(report.return_contribution.factors);
}

/** Colour slot of a factor: 1 to 6, one per hue token f1 to f6. */
export type FactorSlot = 1 | 2 | 3 | 4 | 5 | 6;

/** Colour slot 1 to 6: canonical position (Mom is 6), else order of appearance. */
export function slotOf(name: string, order: readonly string[]): FactorSlot {
  const canonical = (FACTOR_NAMES as readonly string[]).indexOf(name);
  const k = canonical >= 0 ? canonical : Math.max(order.indexOf(name), 0) % FACTOR_NAMES.length;
  return (k + 1) as FactorSlot;
}

const COUNT_WORDS = ["no", "one", "two", "three", "four", "five", "six", "seven"] as const;

/** A small count in words ("five"); larger numbers as digits. */
export function countWord(n: number): string {
  return COUNT_WORDS[n] ?? String(n);
}

/** The number of factors of the report's model: 5 for FF5, 6 for FF6 (from the fit, else the model). */
export function factorCount(report: FactorReport): number {
  const n = report.regression.factors.length;
  return n > 0 ? n : report.model === "ff6" ? 6 : 5;
}

/** Standard footnote texts for `keys`, without the one shown in the open (default L-DESC). */
export function labelTexts(report: FactorReport, keys: readonly string[], skip = "L-DESC"): string[] {
  const texts = report.label_text ?? {};
  return keys.filter((k) => k !== skip && k in texts).map((k) => texts[k] as string);
}

/** The standard "descriptive, in-sample" sentence that opens most footnotes. */
export function describe(report: FactorReport): string {
  return report.label_text?.["L-DESC"] ?? "Descriptive, in-sample, not predictive.";
}

/** "1.0e-17" the way Python prints `{x:.1e}`: two-digit exponent. */
export function sci(x: number): string {
  const [mantissa = "0", exp = "0"] = x.toExponential(1).split("e");
  const sign = exp.startsWith("-") ? "-" : "+";
  return `${mantissa}e${sign}${exp.replace(/^[+-]/, "").padStart(2, "0")}`;
}

// ---------------------------------------------------------------------------- scales

function niceStep(span: number, target: number): number {
  const raw = span / Math.max(target, 1);
  const mag = 10 ** Math.floor(Math.log10(raw));
  for (const m of [1, 2, 2.5, 5, 10]) if (raw <= m * mag) return m * mag;
  return 10 * mag;
}

export interface NiceDomain {
  lo: number;
  hi: number;
  ticks: number[];
}

/** A round-number domain covering [lo, hi], with its tick values. */
export function niceDomain(lo: number, hi: number, target = 4): NiceDomain {
  if (hi - lo < 1e-12) {
    hi += 0.5;
    lo -= 0.5;
  }
  const step = niceStep(hi - lo, target);
  const nlo = Math.floor(lo / step - 1e-9) * step;
  const nhi = Math.ceil(hi / step + 1e-9) * step;
  const ticks: number[] = [];
  for (let t = nlo; t <= nhi + step / 2; t += step) ticks.push(Number(t.toFixed(10)));
  return { lo: nlo, hi: nhi, ticks };
}

/** Linear-interpolation quantile (the prototype's `_quantile`; numpy's default). */
export function quantile(xs: readonly number[], q: number): number {
  const s = [...xs].sort((a, b) => a - b);
  const k = (s.length - 1) * q;
  const f = Math.floor(k);
  const c = Math.min(f + 1, s.length - 1);
  return (s[f] as number) + ((s[c] as number) - (s[f] as number)) * (k - f);
}

// ---------------------------------------------------------------------------- dates

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"] as const;

/** Milliseconds since the epoch (UTC midnight) of an ISO date. Throws on a malformed date. */
export function isoMs(iso: string): number {
  const p = parseIsoDate(iso);
  if (!p) throw new RangeError(`Not an ISO date: ${iso}`);
  return Date.UTC(p.year, p.month - 1, p.day);
}

export interface DateTick {
  ms: number;
  label: string;
  major: boolean;
  /** True for 1 January: the rolling chart draws a vertical gridline there. */
  january: boolean;
}

const DAY_MS = 86_400_000;

/** Calendar ticks between two instants: quarterly for short spans, yearly for long ones. */
export function dateTicks(fromMs: number, toMs: number): DateTick[] {
  const d0 = new Date(fromMs);
  const months = Math.max((toMs - fromMs) / DAY_MS, 1) / 30.44;
  const step = [3, 6, 12, 24, 60, 120].find((k) => months / k <= 14) ?? 120;
  const found: { ms: number; year: number; month: number }[] = [];
  let year = d0.getUTCFullYear();
  let month = d0.getUTCMonth() + 1;
  for (;;) {
    const aligned = step < 12 ? (month - 1) % step === 0 : month === 1 && year % (step / 12) === 0;
    const ms = Date.UTC(year, month - 1, 1);
    if (ms > toMs) break;
    if (aligned && ms >= fromMs) found.push({ ms, year, month });
    month += 1;
    if (month > 12) {
      year += 1;
      month = 1;
    }
  }
  return found.map((t, i) =>
    step < 12
      ? { ms: t.ms, label: `${MONTHS[t.month - 1]} ${t.year}`, major: t.month === 1, january: t.month === 1 }
      : { ms: t.ms, label: String(t.year), major: i % 2 === 0 || found.length <= 6, january: t.month === 1 },
  );
}

// ---------------------------------------------------------------------------- rolling betas

/** One stamp with a beta and a standard error. */
export interface RollingPoint {
  /** Index into `RollingWindow.dates`. */
  index: number;
  beta: number;
  se: number;
}

/** The stamps of one factor that have both a beta and a standard error (warm-up stamps drop out). */
export function rollingPoints(w: RollingWindow, name: string): RollingPoint[] {
  const betas = w.betas[name] ?? [];
  const ses = w.se[name] ?? [];
  const out: RollingPoint[] = [];
  const n = Math.min(betas.length, ses.length);
  for (let i = 0; i < n; i++) {
    const beta = finite(betas[i]);
    const se = finite(ses[i]);
    if (beta !== null && se !== null) out.push({ index: i, beta, se });
  }
  return out;
}

/** First date with a full window for any listed factor, or null. */
export function firstFullWindow(w: RollingWindow, names: readonly string[]): string | null {
  let first: number | null = null;
  for (const name of names) {
    const p = rollingPoints(w, name)[0];
    if (p && (first === null || p.index < first)) first = p.index;
  }
  return first === null ? null : (w.dates[first] ?? null);
}

export interface BetaStats {
  /** Number of stamps. */
  n: number;
  latest: number;
  mean: number;
  /** Standard deviation, ddof = 1 (a spread, not a standard error). */
  sd: number;
  /** 10th and 90th percentile: the middle 80%. */
  p10: number;
  p90: number;
  min: number;
  max: number;
  /** Share of stamps with beta above zero, 0 to 1. */
  shareAbove: number;
}

/** Summary of a series of rolling betas; null for an empty series. */
export function betaStats(values: readonly number[]): BetaStats | null {
  const n = values.length;
  if (n === 0) return null;
  const mean = values.reduce((a, b) => a + b, 0) / n;
  const sd = Math.sqrt(values.reduce((a, b) => a + (b - mean) ** 2, 0) / Math.max(n - 1, 1));
  return {
    n,
    latest: values[n - 1] as number,
    mean,
    sd,
    p10: quantile(values, 0.1),
    p90: quantile(values, 0.9),
    min: Math.min(...values),
    max: Math.max(...values),
    shareAbove: values.filter((v) => v > 0).length / n,
  };
}

/** Rolling-beta summary computed from a window's own series; null when the factor has no stamps. */
export function derivedStats(w: RollingWindow, name: string): BetaStats | null {
  return betaStats(rollingPoints(w, name).map((p) => p.beta));
}

/**
 * Summary shown in the table for one factor and window. The primary window (the one
 * `average_beta` describes) uses the report's own numbers where all are present, as the static
 * report does; any other window is derived. `latest` always comes from the series.
 */
export function windowStats(report: FactorReport, w: RollingWindow, name: string): BetaStats | null {
  const derived = derivedStats(w, name);
  const ab = report.average_beta;
  if (!derived || ab.status !== "ok" || ab.window !== w.window) return derived;
  const a = ab.factors.find((f) => f.name === name);
  const mean = finite(a?.mean);
  const p10 = finite(a?.p10);
  const p90 = finite(a?.p90);
  const sd = finite(a?.sd);
  const min = finite(a?.min);
  const max = finite(a?.max);
  const share = finite(a?.share_positive);
  if (mean === null || p10 === null || p90 === null || sd === null || min === null || max === null) return derived;
  return { ...derived, mean, p10, p90, sd, min, max, shareAbove: share ?? derived.shareAbove };
}
