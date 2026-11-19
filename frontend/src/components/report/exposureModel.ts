/** Pure values for the factor exposures panel (design D5), ported from `_exposures_panel` in render_html.py. */
import type { AverageBetaPanel, FactorReport, FactorStat } from "../../api/types";
import { pval, signed, tstat } from "../../format";
import { position } from "../charts/BarCell";

export interface NiceDomain {
  lo: number;
  hi: number;
  ticks: number[];
}

function niceStep(span: number, target: number): number {
  const raw = span / Math.max(target, 1);
  const mag = 10 ** Math.floor(Math.log10(raw));
  for (const m of [1, 2, 2.5, 5, 10]) {
    if (raw <= m * mag) return m * mag;
  }
  return 10 * mag;
}

/** A round-number domain covering [lo, hi], with its tick values (port of `_nice_domain`). */
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
  return { lo: Number(nlo.toFixed(10)), hi: Number(nhi.toFixed(10)), ticks };
}

export interface AxisLabel {
  value: number;
  /** Text of the tick label ("0" for zero, else a signed number with 2 decimals). */
  text: string;
  /** Percentage from the left edge of the plot. */
  left: number;
  /** "edge-l" and "edge-r" anchor labels at the plot edges inward; "alt" hides every second label on narrow screens. */
  className: string;
}

/** Tick labels under the plot; the zero label always survives the narrow-screen thinning. */
export function axisLabels({ lo, hi, ticks }: NiceDomain): AxisLabel[] {
  const zeroAt = Math.max(
    ticks.findIndex((t) => Math.abs(t) < 1e-12),
    0,
  );
  return ticks.map((value, k) => {
    const left = position(value, lo, hi);
    const classes: string[] = [];
    if (left < 3) classes.push("edge-l");
    else if (left > 97) classes.push("edge-r");
    if ((k - zeroAt) % 2 !== 0 && ticks.length > 5) classes.push("alt");
    return { value, text: value === 0 ? "0" : signed(value, 2), left, className: classes.join(" ") };
  });
}

function finite(x: number | null | undefined): number | null {
  return typeof x === "number" && Number.isFinite(x) ? x : null;
}

export interface ExposureRow {
  name: string;
  beta: number | null;
  ci: { low: number; high: number } | null;
  /** Mean rolling beta (the Avg column); drawn as the diamond when the beta exists. */
  average: number | null;
  /** Not significant (tag is not "reliable"): faded marks, "No" in the Significant column. */
  faded: boolean;
  /** Native tooltip of the plot cell. */
  title: string;
  betaText: string;
  tText: string;
  significantText: "Yes" | "No";
  averageText: string;
}

export interface ExposureModel {
  domain: NiceDomain;
  rows: ExposureRow[];
  /** Window of the average rolling beta, in days. */
  window: number;
  /** True when at least one diamond is drawn. */
  hasAverages: boolean;
}

/** The panel has nothing to draw: the regression is not ok, or no factor has a finite beta. */
export function exposuresUnavailable(report: FactorReport): boolean {
  const g = report.regression;
  return g.status !== "ok" || g.factors.length === 0 || g.factors.every((f) => finite(f.beta) === null);
}

function averages(panel: AverageBetaPanel): Map<string, number> {
  const out = new Map<string, number>();
  if (panel.status !== "ok") return out;
  for (const a of panel.factors) {
    const mean = finite(a.mean);
    if (mean !== null) out.set(a.name, mean);
  }
  return out;
}

function sgn(x: number | null): string {
  return x === null ? "n/a" : signed(x);
}

function row(stat: FactorStat, average: number | null): ExposureRow {
  const beta = finite(stat.beta);
  const low = finite(stat.ci_low);
  const high = finite(stat.ci_high);
  const faded = stat.tag !== "reliable";
  const z = finite(stat.z);
  const p = finite(stat.p_adj_bh);
  const title =
    beta === null
      ? `${stat.name}: no estimate`
      : `${stat.name}: beta ${sgn(beta)}, 95% interval ${sgn(low)} to ${sgn(high)}, ` +
        `t ${z === null ? "n/a" : tstat(z)}, adjusted p ${p === null ? "n/a" : pval(p)}`;
  return {
    name: stat.name,
    beta,
    ci: beta !== null && low !== null && high !== null ? { low, high } : null,
    average,
    faded,
    title,
    betaText: beta === null ? "–" : signed(beta),
    tText: z === null ? "–" : tstat(z),
    significantText: faded ? "No" : "Yes",
    averageText: average === null ? "–" : signed(average),
  };
}

/** Rows, domain and texts of the exposures table. Call only when `exposuresUnavailable` is false. */
export function exposureModel(report: FactorReport): ExposureModel {
  const avg = averages(report.average_beta);
  const stats = report.regression.factors;
  const values = [0];
  for (const s of stats) {
    for (const v of [finite(s.beta), finite(s.ci_low), finite(s.ci_high), avg.get(s.name) ?? null]) {
      if (v !== null) values.push(v);
    }
  }
  const domain = niceDomain(Math.min(...values), Math.max(...values), 5);
  const rows = stats.map((s) => row(s, avg.get(s.name) ?? null));
  return {
    domain,
    rows,
    window: report.average_beta.window,
    hasAverages: rows.some((r) => r.average !== null),
  };
}
