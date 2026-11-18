import { pct } from "../../../format";
import { dateTicks, isoMs, niceDomain } from "../../../report/derive";
import { narrowTicks } from "../RollingPanel";

/** One drawn line; `null` values break the line (warm-up rows, rows before the anchor). */
export interface PlotLine {
  id: string;
  /** CSS class of the path (colour and dash come from ResidualAlphaPanel.css). */
  className: string;
  values: readonly (number | null)[];
}

export interface PlotBand {
  low: readonly (number | null)[];
  high: readonly (number | null)[];
}

export interface LinePlotProps {
  /** ISO dates of every row; the values of each line align with them. */
  dates: readonly string[];
  /** Index of the first row drawn. */
  from: number;
  lines: readonly PlotLine[];
  band?: PlotBand | undefined;
  /** Rows from `from` up to (not including) this index are shaded as warm-up. */
  shadeTo?: number | undefined;
  /** Trading days after the last row that have no factor data (shaded, to scale). */
  tail?: number | undefined;
  testId: string;
}

const W = 1000;
const H = 100;

/** SVG path of the runs of non-null points (each run its own sub-path). */
export function linePath(values: readonly (number | null)[], from: number, x: (i: number) => number, y: (v: number) => number): string {
  const parts: string[] = [];
  let open = false;
  for (let i = from; i < values.length; i++) {
    const v = values[i];
    if (v === null || v === undefined || !Number.isFinite(v)) {
      open = false;
      continue;
    }
    parts.push(`${open ? "L" : "M"}${x(i - from).toFixed(2)} ${y(v).toFixed(2)}`);
    open = true;
  }
  return parts.join("");
}

/** Closed polygons between `low` and `high` for each run where both exist. */
export function bandPath(band: PlotBand, from: number, x: (i: number) => number, y: (v: number) => number): string {
  const parts: string[] = [];
  let run: number[] = [];
  const flush = () => {
    if (run.length > 1) {
      const up = run.map((i) => `${x(i - from).toFixed(2)} ${y(band.high[i] as number).toFixed(2)}`);
      const down = [...run].reverse().map((i) => `${x(i - from).toFixed(2)} ${y(band.low[i] as number).toFixed(2)}`);
      parts.push(`M${up.join("L")}L${down.join("L")}Z`);
    }
    run = [];
  };
  for (let i = from; i < band.low.length; i++) {
    const lo = band.low[i];
    const hi = band.high[i];
    if (typeof lo === "number" && typeof hi === "number" && Number.isFinite(lo) && Number.isFinite(hi)) run.push(i);
    else flush();
  }
  flush();
  return parts.join("");
}

/** First index in `ms[from..]` at or after `t`. */
function lowerBound(ms: readonly number[], from: number, t: number): number {
  let lo = from;
  let hi = ms.length;
  while (lo < hi) {
    const mid = (lo + hi) >> 1;
    if ((ms[mid] as number) < t) lo = mid + 1;
    else hi = mid;
  }
  return lo;
}

/** First index of the line set with a finite value, or -1. */
export function firstFiniteIndex(values: readonly (number | null)[]): number {
  return values.findIndex((v) => typeof v === "number" && Number.isFinite(v));
}

/**
 * A line chart as plain SVG on a row-index axis (trading days), with the date ticks, y labels in
 * percent, a zero line and optional band, warm-up and uncovered-tail shading. The chart is
 * decoration: every number on it is also in the table beside it, so the SVG is hidden from
 * assistive technology.
 */
export function LinePlot({ dates, from, lines, band, shadeTo, tail = 0, testId }: LinePlotProps) {
  const rows = dates.length - from;
  if (rows < 2) return null;
  const finiteVals: number[] = [0];
  for (const l of lines) for (let i = from; i < l.values.length; i++) {
    const v = l.values[i];
    if (typeof v === "number" && Number.isFinite(v)) finiteVals.push(v);
  }
  if (band) {
    for (const arr of [band.low, band.high]) for (let i = from; i < arr.length; i++) {
      const v = arr[i];
      if (typeof v === "number" && Number.isFinite(v)) finiteVals.push(v);
    }
  }
  const dom = niceDomain(Math.min(...finiteVals), Math.max(...finiteVals));
  const step = dom.ticks.length > 1 ? (dom.ticks[1] as number) - (dom.ticks[0] as number) : 0.1;
  const digits = Math.abs(Math.round(step * 1000) / 10 - Math.round(step * 100)) > 1e-9 ? 1 : 0;
  const span = rows - 1 + Math.max(tail, 0);
  const x = (i: number) => (i / span) * W;
  const y = (v: number) => ((dom.hi - v) / (dom.hi - dom.lo)) * H;
  const yPct = (v: number) => (y(v) / H) * 100;

  const ms = dates.map(isoMs);
  const ticks = dateTicks(ms[from] as number, ms[ms.length - 1] as number).map((t) => ({
    ...t,
    x: ((lowerBound(ms, from, t.ms) - from) / span) * 100,
  }));
  const keep = narrowTicks(ticks.map((t) => ({ x: t.x, major: t.major })));
  const shadeWidth = shadeTo !== undefined && shadeTo > from ? x(shadeTo - from) : 0;
  const tailStart = tail > 0 ? x(rows - 1) : W;

  return (
    <div className="res-plot plot" data-testid={testId}>
      <svg className="line-svg" viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" aria-hidden="true" focusable="false">
        {shadeWidth > 0 ? <rect className="tailzone" x={0} y={0} width={shadeWidth} height={H} /> : null}
        {tail > 0 ? <rect className="tailzone" x={tailStart} y={0} width={W - tailStart} height={H} /> : null}
        {dom.ticks.map((t) => (
          <line key={t} className={Math.abs(t) < 1e-12 ? "zero" : "grid"} x1={0} x2={W} y1={y(t)} y2={y(t)} />
        ))}
        {band ? <path className="res-band" d={bandPath(band, from, x, y)} /> : null}
        {lines.map((l) => (
          <path key={l.id} className={`res-line ${l.className}`} d={linePath(l.values, from, x, y)} data-line={l.id} />
        ))}
      </svg>
      <div className="ylabels" aria-hidden="true">
        {dom.ticks.map((t) => (
          <span key={t} className="yl" style={{ top: `${yPct(t).toFixed(2)}%` }}>
            {pct(t, digits)}
          </span>
        ))}
      </div>
      {shadeWidth > 0 ? (
        <span className="res-zone l" aria-hidden="true">
          Warm-up
        </span>
      ) : null}
      {tail > 0 ? (
        <span className="res-zone r" aria-hidden="true">
          No factor data
        </span>
      ) : null}
      <div className="xlabels" aria-hidden="true">
        {ticks.map((t, i) => (
          <span
            key={t.ms}
            className={`xl${t.major ? "" : " minor"}${keep.has(i) ? " keep" : ""}${t.x < 3 ? " edge-l" : t.x > 97 ? " edge-r" : ""}`}
            style={{ left: `${t.x.toFixed(2)}%` }}
          >
            {t.label}
          </span>
        ))}
      </div>
    </div>
  );
}
