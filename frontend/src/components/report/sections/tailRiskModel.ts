import type { TailRiskSection } from "../../../api/types";
import { count, pct } from "../../../format";

export type TailFigure = NonNullable<TailRiskSection["figures"]>[number];
export type TailMethod = TailFigure["method"];
export type TailHorizon = NonNullable<TailRiskSection["by_horizon"]>[number];
export type Horizon = TailHorizon["horizon"];

export const METHODS: readonly { key: TailMethod; label: string }[] = [
  { key: "historical", label: "Historical" },
  { key: "gaussian", label: "Gaussian" },
  { key: "cornish_fisher", label: "Cornish-Fisher" },
];

/** The two bars of each level: the observed figure, and the model figure (Cornish-Fisher, or Gaussian where that is n/a). */
export type BarKey = "historical" | "forecast";
export const BARS: readonly { key: BarKey; label: string }[] = [
  { key: "historical", label: "Historical" },
  { key: "forecast", label: "Forecast" },
];

interface HorizonInfo {
  key: Horizon;
  label: string;
  one: string;
  many: string;
  question: string;
}

/** The horizons in switch order, with the words each one needs. */
export const HORIZONS: readonly HorizonInfo[] = [
  { key: "daily", label: "Daily", one: "day", many: "days", question: "How large a loss does a bad day bring?" },
  { key: "monthly", label: "Monthly", one: "month", many: "months", question: "How large a loss does a bad month bring?" },
  {
    key: "quarterly",
    label: "Quarterly",
    one: "quarter",
    many: "quarters",
    question: "How large a loss does a bad quarter bring?",
  },
];

export const APPROXIMATE = "approximate (tends to be narrow)";
export const INDICATIVE = "Indicative";
export const GAUSSIAN = "Gaussian";
export const GAUSSIAN_NOTE = "Cornish-Fisher not available here; normal approximation used";
export const CAPTION =
  "Losses are shown as positive numbers. Each horizon uses its own returns over whole days, months or quarters. Nothing is scaled up from daily, so quarterly figures rest on fewer observations.";

export function horizonInfo(h: Horizon): HorizonInfo {
  return HORIZONS.find((x) => x.key === h) ?? (HORIZONS[0] as HorizonInfo);
}

/** One group of lines: a measure at a confidence level, one cell per method. */
export interface TailRow {
  key: string;
  measure: TailFigure["measure"];
  level: number;
  label: string;
  cells: Record<TailMethod, TailFigure | undefined>;
}

/** "VaR 99%", "CVaR 97.5%". */
export function rowLabel(measure: TailFigure["measure"], level: number): string {
  const percent = Number((level * 100).toFixed(1));
  return `${measure === "var" ? "VaR" : "CVaR"} ${percent}%`;
}

/** The figures grouped by measure and level, in the order the backend sends them. */
export function rowsOf(figures: readonly TailFigure[]): TailRow[] {
  const rows: TailRow[] = [];
  for (const f of figures) {
    const key = `${f.measure}-${f.level}`;
    let row = rows.find((r) => r.key === key);
    if (row === undefined) {
      row = {
        key,
        measure: f.measure,
        level: f.level,
        label: rowLabel(f.measure, f.level),
        cells: { historical: undefined, gaussian: undefined, cornish_fisher: undefined },
      };
      rows.push(row);
    }
    row.cells[f.method] = f;
  }
  return rows;
}

/** "90%" from the band level 0.9. */
export function bandName(level: number): string {
  return `${Number((level * 100).toFixed(1))}%`;
}

/** "720 days", "1 day", "60 months", "20 quarters". */
export function basedOn(n: number, horizon: Horizon): string {
  const info = horizonInfo(horizon);
  return `${count(n)} ${n === 1 ? info.one : info.many}`;
}

/** What the level means in plain words ("Exceeded on 1 day in 100"). */
export function whatItMeans(measure: TailFigure["measure"], level: number, horizon: Horizon): string {
  const unit = horizonInfo(horizon).one;
  const every = Math.round(1 / (1 - level));
  return measure === "var" ? `Exceeded on 1 ${unit} in ${every}` : `Average loss in the worst 1 ${unit} in ${every}`;
}

/** A loss as a positive percentage ("2.65%"). */
export function loss(x: number, digits = 2): string {
  return pct(x, digits, false);
}

/** The shared axis of one measure: from `lo` to `hi`, as fractions of value (`lo` is 0 unless a figure is a gain). */
export interface Scale {
  lo: number;
  hi: number;
}

/** Round step of the scale, in percent, for a given largest figure (in percent). */
function niceStep(largestPercent: number): number {
  if (largestPercent <= 5) return 0.5;
  if (largestPercent <= 10) return 1;
  if (largestPercent <= 30) return 2;
  if (largestPercent <= 80) return 5;
  return 10;
}

/**
 * The scale shared by every line of one measure (all VaR lines, or all CVaR lines): it covers every
 * value and every band end, starts at 0, and ends on a round percentage. A figure that is a gain
 * (a negative loss) extends the scale below 0.
 */
export function scaleOf(figures: readonly TailFigure[]): Scale {
  let lo = 0;
  let hi = 0;
  for (const f of figures) {
    for (const v of [f.value, f.band?.low, f.band?.high]) {
      if (v === null || v === undefined || !Number.isFinite(v)) continue;
      lo = Math.min(lo, v);
      hi = Math.max(hi, v);
    }
  }
  const step = niceStep(Math.max(hi, -lo) * 100);
  const top = Math.max(step, Math.ceil((hi * 100) / step - 1e-9) * step);
  const bottom = lo < 0 ? Math.floor((lo * 100) / step + 1e-9) * step : 0;
  return { lo: bottom / 100, hi: top / 100 };
}

/** Position of `x` on the scale, as a percentage of the track width (clamped to 0..100). */
export function place(x: number, s: Scale): number {
  const span = s.hi - s.lo;
  if (span <= 0) return 0;
  return Math.min(100, Math.max(0, ((x - s.lo) / span) * 100));
}

/** Decimals for the losses of a measure: two while its scale ends below 4%, one above. */
export function digitsFor(s: Scale): number {
  return s.hi < 0.04 ? 2 : 1;
}

/** One bar of a level: the figure it shows, and which method it comes from. */
export interface TailBar {
  key: BarKey;
  label: string;
  /** The figure on show; its `value` is null when the bar is n/a, and it is undefined when the report holds none. */
  figure: TailFigure | undefined;
  source: TailMethod;
  /** True for a Forecast bar that shows the Gaussian figure because Cornish-Fisher is n/a. */
  fallback: boolean;
}

/** One level of one measure ("VaR 95%"): its two bars, and the figure of every method for the table. */
export interface TailLevel extends TailRow {
  bars: [TailBar, TailBar];
}

/** One measure with its levels, from the lowest level to the highest. */
export interface TailGroup {
  measure: TailFigure["measure"];
  label: string;
  levels: TailLevel[];
}

/** The Forecast figure of a level: Cornish-Fisher when it has a value, else Gaussian, else the n/a Cornish-Fisher figure. */
export function forecastOf(cells: TailRow["cells"]): Omit<TailBar, "key" | "label"> {
  const cf = cells.cornish_fisher;
  const gauss = cells.gaussian;
  if (cf?.value != null) return { figure: cf, source: "cornish_fisher", fallback: false };
  if (gauss?.value != null) return { figure: gauss, source: "gaussian", fallback: true };
  return { figure: cf ?? gauss, source: "cornish_fisher", fallback: false };
}

/** The figures as a VaR group and a CVaR group, levels in ascending order, each with its Historical and Forecast bar. */
export function groupsOf(figures: readonly TailFigure[]): TailGroup[] {
  const rows = rowsOf(figures);
  const out: TailGroup[] = [];
  for (const measure of ["var", "cvar"] as const) {
    const levels = rows
      .filter((r) => r.measure === measure)
      .sort((a, b) => a.level - b.level)
      .map<TailLevel>((r) => ({
        ...r,
        bars: [
          { key: "historical", label: BARS[0]?.label ?? "", figure: r.cells.historical, source: "historical", fallback: false },
          { key: "forecast", label: BARS[1]?.label ?? "", ...forecastOf(r.cells) },
        ],
      }));
    if (levels.length > 0) out.push({ measure, label: measure === "var" ? "VaR" : "CVaR", levels });
  }
  return out;
}

/** The figures that the bars show (Gaussian only where it stands in for Cornish-Fisher): they set the shared scale. */
export function shownFigures(groups: readonly TailGroup[]): TailFigure[] {
  return groups.flatMap((g) => g.levels.flatMap((l) => l.bars.flatMap((b) => (b.figure ? [b.figure] : []))));
}

/** "95%", "97.5%". */
export function levelName(level: number): string {
  return `${Number((level * 100).toFixed(1))}%`;
}

/** "1 month in 20". */
export function oneIn(level: number, horizon: Horizon): string {
  return `1 ${horizonInfo(horizon).one} in ${Math.round(1 / (1 - level))}`;
}

/** Tick values of the shared axis: a round step that gives at most four intervals, from the scale's low end to its high end. */
export function ticksOf(s: Scale): number[] {
  const span = (s.hi - s.lo) * 100;
  const steps = [0.1, 0.2, 0.25, 0.5, 1, 2, 2.5, 5, 10, 20, 25, 50, 100];
  const step = steps.find((x) => span / x <= 4) ?? 100;
  const out: number[] = [];
  for (let k = Math.ceil((s.lo * 100) / step - 1e-9); k * step <= s.hi * 100 + 1e-9; k++) out.push((k * step) / 100 || 0);
  return out;
}

/** "0", "5%", "0.5%". */
export function tickText(x: number): string {
  return x === 0 ? "0" : `${Number((x * 100).toFixed(2))}%`;
}
