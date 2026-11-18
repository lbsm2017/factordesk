import type { FactorReport } from "../../api/types";
import { dateLong } from "../../format";

export interface AnalysedRangeProps {
  /** undefined before the first report. */
  report: FactorReport | undefined;
}

function plural(n: number, one: string, many: string): string {
  return `${n.toLocaleString("en-US")} ${n === 1 ? one : many}`;
}

/** The static report's range line (render_html `_range_line`), split into the bold part and the rest. */
export function rangeLine(report: FactorReport): { head: string; tail: string } {
  const d = report.data;
  const head = `Analysed ${dateLong(d.actual_start)} to ${dateLong(d.actual_end)}, ${plural(d.n_obs, "trading day", "trading days")}.`;
  const parts: string[] = [];
  const tailN = d.uncovered.n;
  if (tailN === 1) parts.push("The last price day is charted but not analysed.");
  else if (tailN > 0) parts.push(`The last ${tailN} price days are charted but not analysed.`);
  // The price day just before the first return is that return's base price, not a gap.
  const headN = Math.max(report.price_series.dates.filter((x) => x < d.actual_start).length - 1, 0);
  if (headN === 1) parts.push("The first price day is also not analysed.");
  else if (headN > 1) parts.push(`The first ${headN} price days are also not analysed.`);
  return { head, tail: parts.join(" ") };
}

/** Always visible and announced politely when it changes (dashboard spec DB6.3). */
export function AnalysedRange({ report }: AnalysedRangeProps) {
  const line = report ? rangeLine(report) : null;
  return (
    <p className="ctl-label" id="analysed-range" aria-live="polite" aria-atomic="true">
      {line ? (
        <>
          <b>{line.head}</b>
          {line.tail ? ` ${line.tail}` : ""}
        </>
      ) : (
        "No range analysed yet."
      )}
    </p>
  );
}
