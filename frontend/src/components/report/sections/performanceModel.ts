/** Numbers behind the Drawdown panel: chart points, axes and the rows of the largest-falls table. */
import type { PerformanceSection } from "../../../api/types";
import { dateTicks, isoMs } from "../../../report/derive";

type Drawdown = NonNullable<PerformanceSection["drawdown"]>;
type Episode = Drawdown["episodes"][number];

/** Most points drawn in the underwater chart. */
export const MAX_POINTS = 600;

/**
 * Indexes of at most `max` points to draw. The first and last point always stay; every other
 * bucket of consecutive points keeps its lowest one, so a trough is never smoothed away.
 */
export function sampleIndexes(values: readonly number[], max = MAX_POINTS): number[] {
  const n = values.length;
  if (n <= max) return values.map((_, i) => i);
  const keep: number[] = [0];
  const buckets = max - 2;
  const size = (n - 2) / buckets;
  for (let b = 0; b < buckets; b++) {
    const from = 1 + Math.floor(b * size);
    const to = Math.min(1 + Math.floor((b + 1) * size), n - 1);
    let low = from;
    for (let i = from; i < to; i++) if ((values[i] as number) < (values[low] as number)) low = i;
    if (to > from) keep.push(low);
  }
  keep.push(n - 1);
  return keep;
}

export interface YAxis {
  /** Lowest value shown (negative, a multiple of the step). */
  bottom: number;
  /** 0 and then the negative ticks, top to bottom. */
  ticks: number[];
}

/** Axis from 0 down to a round value at or below the deepest fall, with at most four intervals. */
export function yAxis(deepest: number): YAxis {
  const depth = Math.abs(Math.min(deepest, 0));
  const step = [0.01, 0.02, 0.05, 0.1, 0.2, 0.25, 0.5, 1].find((s) => Math.ceil(depth / s - 1e-9) <= 4) ?? 1;
  const count = Math.max(Math.ceil(depth / step - 1e-9), 1);
  const ticks: number[] = [];
  for (let k = 0; k <= count; k++) ticks.push(Number((-k * step).toFixed(10)));
  return { bottom: ticks[ticks.length - 1] as number, ticks };
}

export interface ChartGeometry {
  /** Closed path of the filled area, in a 1000 by 100 box. */
  area: string;
  /** Open path of the line. */
  line: string;
  points: number;
}

function xy(date: string, value: number, t0: number, span: number, bottom: number): string {
  const x = span > 0 ? ((isoMs(date) - t0) / span) * 1000 : 0;
  const y = Math.min(Math.max((value / bottom) * 100, 0), 100);
  return `${x.toFixed(1)},${y.toFixed(1)}`;
}

/** Paths of the underwater chart in a 1000 by 100 box (x by date, y 0 at the top). */
export function chartGeometry(dates: readonly string[], values: readonly number[], bottom: number): ChartGeometry {
  const n = Math.min(dates.length, values.length);
  if (n === 0) return { area: "", line: "", points: 0 };
  const t0 = isoMs(dates[0] as string);
  const span = isoMs(dates[n - 1] as string) - t0;
  const picked = sampleIndexes(values.slice(0, n));
  const pts = picked.map((i) => xy(dates[i] as string, values[i] as number, t0, span, bottom));
  const last = pts[pts.length - 1]?.split(",")[0] ?? "1000";
  return { area: `M0,0 L${pts.join(" L")} L${last},0Z`, line: `M${pts.join(" L")}`, points: picked.length };
}

export interface XLabel {
  left: number;
  text: string;
}

/** Calendar labels under the chart, placed by date. */
export function xLabels(first: string, last: string): XLabel[] {
  const t0 = isoMs(first);
  const t1 = isoMs(last);
  const span = t1 - t0;
  if (span <= 0) return [];
  const all = dateTicks(t0, t1).map((t) => ({ left: ((t.ms - t0) / span) * 100, text: t.label, major: t.major }));
  const shown = all.length > 8 ? all.filter((t) => t.major) : all;
  return shown.filter((t) => t.left >= 1 && t.left <= 99).map((t) => ({ left: Math.round(t.left * 100) / 100, text: t.text }));
}

/** Trading days from the peak to the recovery, or to the end of the series when not recovered. */
export function episodeDays(e: Episode, dates: readonly string[]): number | null {
  if (e.recovery_date !== null) {
    return e.days_trough_to_recovery === null ? null : e.days_peak_to_trough + e.days_trough_to_recovery;
  }
  const at = dates.indexOf(e.peak_date);
  return at < 0 ? null : dates.length - 1 - at;
}
