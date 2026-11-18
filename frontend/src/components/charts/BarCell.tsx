/**
 * One bar-table plot cell (design D5): an SVG with percentage coordinates, so marks stay crisp
 * without a distorting viewBox. Mark sizes follow design Rev 2: the bar is 36% of the row height,
 * the whisker is 1.5 px with 3 px caps (dropped when the interval is under 1.2% of the plot
 * width), and the average-beta diamond is 7 px on the row's centre line.
 */

/** Position of `value` in the domain, as a percentage of the plot width (3 decimals). */
export function position(value: number, lo: number, hi: number): number {
  return Math.round(((value - lo) / (hi - lo)) * 100 * 1000) / 1000;
}

/** Whisker caps are drawn only when the interval spans at least this share of the plot width. */
export const MIN_CAP_SPAN_PCT = 1.2;

export type BarFill = "sign" | "factor" | "hatch";

export interface BarCellProps {
  /** Domain of the plot (data units). */
  lo: number;
  hi: number;
  /** Gridline positions; the tick at 0 becomes the zero line. */
  ticks: readonly number[];
  /** Bar from zero to `value`; null draws no bar. */
  value: number | null;
  /** "sign": blue (positive) or copper (negative). "factor": factor hue `factorSlot`. "hatch": residual. */
  fill: BarFill;
  /** 1 to 5, the factor's categorical hue (fill "factor"). */
  factorSlot?: 1 | 2 | 3 | 4 | 5;
  /** Not significant: faded fill plus full-colour outline (fill "sign" only). */
  faded?: boolean;
  /** 95% interval whisker. */
  ci?: { low: number; high: number } | null;
  /** Average rolling beta, drawn as an ink diamond. */
  marker?: number | null;
  /** Total: a 2 px rule from zero with a 3 px cap, instead of a bar. */
  total?: number | null;
  /** Native tooltip text; also the text a pointer user gets. */
  title: string;
}

function barClass(fill: BarFill, value: number, faded: boolean, slot: number | undefined): string {
  if (fill === "hatch") return "hatch";
  if (fill === "factor") return `cat c${slot ?? 1}`;
  return (value >= 0 ? "pos" : "neg") + (faded ? " faded" : "");
}

export function BarCell({ lo, hi, ticks, value, fill, factorSlot, faded = false, ci, marker, total, title }: BarCellProps) {
  const zero = position(0, lo, hi);
  const bar =
    value === null || total != null
      ? null
      : (() => {
          const [a = 0, b = 0] = [zero, position(value, lo, hi)].sort((x, y) => x - y);
          return (
            <rect
              className={barClass(fill, value, faded, factorSlot)}
              x={`${a}%`}
              y="32%"
              width={`${Math.max(b - a, 0)}%`}
              height="36%"
              rx="2"
            />
          );
        })();

  let whisker = null;
  if (ci) {
    const a = position(ci.low, lo, hi);
    const b = position(ci.high, lo, hi);
    whisker = (
      <>
        <line className="ci" x1={`${a}%`} x2={`${b}%`} y1="50%" y2="50%" />
        {b - a >= MIN_CAP_SPAN_PCT ? (
          <>
            <line className="ci" x1={`${a}%`} x2={`${a}%`} y1="46.5%" y2="53.5%" />
            <line className="ci" x1={`${b}%`} x2={`${b}%`} y1="46.5%" y2="53.5%" />
          </>
        ) : null}
      </>
    );
  }

  let totalMark = null;
  if (total != null) {
    const tx = position(total, lo, hi);
    totalMark = (
      <>
        <line className="total-line" x1={`${Math.min(zero, tx)}%`} x2={`${Math.max(zero, tx)}%`} y1="50%" y2="50%" />
        <line className="total-cap" x1={`${tx}%`} x2={`${tx}%`} y1="22%" y2="78%" />
      </>
    );
  }

  return (
    <svg className="bar-svg" aria-hidden="true">
      <title>{title}</title>
      {ticks.map((t) => {
        const x = `${position(t, lo, hi)}%`;
        return <line key={t} className={Math.abs(t) < 1e-12 ? "zero" : "grid"} x1={x} x2={x} y1="0" y2="100%" />;
      })}
      {bar}
      {totalMark}
      {whisker}
      {marker != null ? (
        <svg className="avgm" x={`${position(marker, lo, hi)}%`} y="50%" overflow="visible" aria-hidden="true">
          <path d="M0 -3.6 3.6 0 0 3.6-3.6 0z" />
        </svg>
      ) : null}
    </svg>
  );
}
