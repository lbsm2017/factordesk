/**
 * Outcome line of each panel (dashboard v2 spec DV4.9): one sentence under the panel title, a pure
 * function of `FactorReport`. Descriptive only: no forecast or causal words, and significance comes
 * from the tags the report already carries. The Drawdown and World beta lines live in
 * `outcomeDeep.ts`, next to the lazy panels that show them.
 */
import type { FactorReport, FactorStat } from "../api/types";
import { count, dateLong, num, pct } from "../format";
import { factorOrder, finite, IDIO, windowStats } from "../report/derive";
import { PLAIN } from "./plain";

const NUMBER_WORDS = ["None", "One", "Two", "Three", "Four", "Five"] as const;

function pct1(x: number): string {
  return pct(Math.abs(x), 1, false);
}

function plain(name: string): string {
  return PLAIN[name] ?? name;
}

/** "a", "a and b", "a, b and c". */
export function list(items: readonly string[]): string {
  if (items.length <= 1) return items.join("");
  return `${items.slice(0, -1).join(", ")} and ${items[items.length - 1]}`;
}

/** "1 day", "32 days". */
export function plural(n: number, one: string, many: string): string {
  return `${count(n)} ${n === 1 ? one : many}`;
}

function capital(text: string): string {
  return text.charAt(0).toUpperCase() + text.slice(1);
}

function priceAt(report: FactorReport, date: string): number | null {
  const { dates, adj_close } = report.price_series;
  const i = dates.indexOf(date);
  return i < 0 ? null : finite(adj_close[i]);
}

/** Price: the change over the analysed range, and the uncharted tail. Null when a price is missing. */
export function priceOutcome(report: FactorReport): string | null {
  const d = report.data;
  const a = priceAt(report, d.actual_start);
  const b = priceAt(report, d.actual_end);
  if (a === null || b === null || a === 0) return null;
  const ch = b / a - 1;
  const move = pct1(ch) === "0.0%" ? "ended where it started" : `${ch > 0 ? "rose" : "fell"} ${pct1(ch)}`;
  let text = `With dividends reinvested, ${report.ticker} ${move} over the analysed range (${dateLong(d.actual_start)} to ${dateLong(d.actual_end)}).`;
  if (d.uncovered.n > 0) {
    const n = d.uncovered.n;
    text += ` The last ${n} price ${n === 1 ? "day is" : "days are"} charted but not analysed.`;
  }
  return text;
}

function isClear(f: FactorStat): boolean {
  return f.tag === "reliable";
}

/** Factor exposures: how many of the five betas are clear, and which. */
export function exposuresOutcome(report: FactorReport): string | null {
  const fs = report.regression.factors;
  if (report.regression.status !== "ok" || fs.length === 0) return null;
  const clear = fs.filter(isClear).map((f) => plain(f.name).toLowerCase());
  const rest = fs.filter((f) => !isClear(f)).map((f) => plain(f.name).toLowerCase());
  if (clear.length === 0) return "None of the five exposures is distinguishable from zero over this range.";
  const k = clear.length;
  let text = `${NUMBER_WORDS[k] ?? String(k)} of the five exposures ${k === 1 ? "is" : "are"} clear (${list(clear)})`;
  text += rest.length > 0 ? `; ${list(rest)} ${rest.length === 1 ? "is" : "are"} not distinguishable from zero.` : ".";
  return text;
}

/** Return sources: the largest source, and whether it can be told apart from zero. */
export function returnsOutcome(report: FactorReport): string | null {
  const rc = report.return_contribution;
  const reg = report.regression;
  const total = finite(rc.total_annualised_mean_excess_return);
  if (rc.status !== "ok" || total === null) return null;
  const tags = new Map(reg.factors.map((f) => [f.name, f.tag]));
  const sources = [
    ...Object.entries(rc.factors).map(([name, v]) => ({ name, value: finite(v), alpha: false })),
    { name: "alpha", value: finite(rc.alpha), alpha: true },
  ].flatMap((s) => (s.value === null ? [] : [{ ...s, value: s.value }]));
  const top = sources.reduce<(typeof sources)[number] | null>(
    (best, s) => (best === null || Math.abs(s.value) > Math.abs(best.value) ? s : best),
    null,
  );
  if (top === null) return null;
  const label = top.alpha ? "the return beyond its exposures" : `${plain(top.name).toLowerCase()} exposure`;
  const side = total >= 0 ? "above" : "below";
  const clear = top.alpha ? reg.alpha_tag === "reliable" : tags.get(top.name) === "reliable";
  const amount = `${pct1(total)} a year ${report.ticker} earned ${side} cash`;
  const largest = pct(top.value, 1);
  const most = Math.abs(top.value) >= 0.5 * Math.abs(total);
  const head = most
    ? `${capital(label)} accounts for most of the ${amount} (${largest})`
    : `No single source accounts for most of the ${amount}; the largest is ${label} (${largest})`;
  if (clear) return `${head}.`;
  return top.alpha ? `${head}, and it is not distinguishable from zero.` : `${head}, but that exposure is not distinguishable from zero.`;
}

/** Risk sources: the largest share of day-to-day risk. */
export function riskOutcome(report: FactorReport): string | null {
  const rk = report.risk_contribution;
  const idio = finite(rk.idiosyncratic);
  if (rk.status !== "ok" || idio === null) return null;
  const t = report.ticker;
  const top = rk.order[0];
  if (top === undefined || top === IDIO) {
    return `Most of ${t}'s day-to-day risk is specific to ${t} (${pct1(idio)}).`;
  }
  const share = finite(rk.factors[top]);
  if (share === null) return null;
  return `${plain(top)} exposure drives ${pct1(share)} of ${t}'s day-to-day risk; ${pct1(idio)} is specific to ${t}.`;
}

/** Exposure over time: the middle 80% of the market beta, and the style factors that crossed zero. */
export function rollingOutcome(report: FactorReport, win: number): string | null {
  const w = report.rolling.find((r) => r.window === win && r.status === "ok" && r.dates.length > 0);
  if (!w) return null;
  const mkt = windowStats(report, w, "Mkt-RF");
  if (!mkt) return null;
  let text = `In 80% of the ${win}-day windows the market beta was between ${num(mkt.p10, 2)} and ${num(mkt.p90, 2)}.`;
  const crossing = factorOrder(report)
    .filter((n) => n !== "Mkt-RF")
    .filter((n) => {
      const s = windowStats(report, w, n);
      return s !== null && s.p10 < 0 && s.p90 > 0;
    })
    .map((n) => plain(n).toLowerCase());
  if (crossing.length > 0) {
    text += ` The ${list(crossing)} ${crossing.length === 1 ? "exposure" : "exposures"} spent long stretches on both sides of zero.`;
  }
  return text;
}

/** Data and audit: the audit result and the days analysed. */
export function dataOutcome(report: FactorReport): string {
  const d = report.data;
  const e = d.audit_findings.filter((f) => f.severity === "error").length;
  const w = d.audit_findings.filter((f) => f.severity === "warning").length;
  let audit: string;
  if (d.audit_status === "errors" || e > 0) {
    audit = `The price audit found ${plural(e, "error", "errors")}; the results above are not interpretable until ${e === 1 ? "it is" : "they are"} explained.`;
  } else if (d.audit_status === "warnings" || w > 0) {
    audit = `The price audit flagged ${plural(w, "unusual item", "unusual items")}; none stops the analysis.`;
  } else {
    audit = "The price audit found no problems.";
  }
  const excluded = d.n_excluded > 0 ? count(d.n_excluded) : "none";
  return `${audit} ${count(d.n_obs)} trading days analysed, ${excluded} excluded.`;
}

/** Regression detail: betas significant after the multiple-test correction, and the alpha tag. */
export function regressionOutcome(report: FactorReport): string | null {
  const reg = report.regression;
  if (reg.status !== "ok") return null;
  const k = reg.factors.filter(isClear).length;
  const kText = NUMBER_WORDS[k] ?? String(k);
  const alpha = reg.alpha_tag === "reliable" ? "distinguishable" : "not distinguishable";
  let text = `${kText} of the five betas ${k === 1 ? "is" : "are"} significant after allowing for testing five at once; the return beyond the exposures is ${alpha} from zero.`;
  if (report.quality_gate.fired) {
    text += " Because the quality gate fired, a term counts as significant only when the 5-day estimate agrees.";
  }
  return text;
}
