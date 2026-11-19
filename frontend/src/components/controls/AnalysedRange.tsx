import { useId } from "react";
import type { FactorReport } from "../../api/types";
import { count, dateLong } from "../../format";
import { isMonthly, observations, periodWord } from "../../report/subject";

/** A range preset the server marks as unavailable for the ticker, with its reason. */
export interface UnavailablePreset {
  preset: string;
  reason: string;
}

export interface AnalysedRangeProps {
  /** undefined before the first report. */
  report: FactorReport | undefined;
  /** Presets that cannot be chosen, for the one-line note; the full reasons go in the details. */
  unavailable?: readonly UnavailablePreset[];
  /** Id of the one-line note, so the range chips can point at it with aria-describedby. */
  noteId?: string;
  /** A small label above the summary (the track-record mode has no date inputs above it). */
  label?: string;
}

/** The three parts of the price history, in time order, with their size in price days or months. */
export interface Coverage {
  /** Price days before the analysed window, the base price of the first return included (muted). */
  before: number;
  /** Rows in the analysed window (solid accent). */
  analysed: number;
  /** Price days after the factor data end: charted, not analysed (hatched). */
  after: number;
  /** Of `before`, those that count as "not analysed" in words (the base price is not a gap). */
  skipped: number;
}

export function coverage(report: FactorReport): Coverage {
  const d = report.data;
  const before = report.price_series.dates.filter((x) => x < d.actual_start).length;
  return { before, analysed: d.n_obs, after: d.uncovered.n, skipped: Math.max(before - 1, 0) };
}

function plural(n: number, one: string, many: string): string {
  return `${count(n)} ${n === 1 ? one : many}`;
}

/** The static report's range line (render_html `_range_line`), split into the bold part and the rest. */
export function rangeLine(report: FactorReport): { head: string; tail: string } {
  const d = report.data;
  const head = `Analysed ${dateLong(d.actual_start)} to ${dateLong(d.actual_end)}, ${observations(report, d.n_obs)}.`;
  const words = periodWord(report);
  const one = isMonthly(report) ? "month" : "price day";
  const parts: string[] = [];
  const { skipped, after } = coverage(report);
  if (after === 1) parts.push(`The last ${one} is charted but not analysed.`);
  else if (after > 0) parts.push(`The last ${count(after)} ${words} are charted but not analysed.`);
  if (skipped === 1) parts.push(`The first ${one} is also not analysed.`);
  else if (skipped > 1) parts.push(`The first ${count(skipped)} ${words} are also not analysed.`);
  return { head, tail: parts.join(" ") };
}

/** The line under the bar: "3 Oct 2016 → 30 Sep 2026" and "2,512 days" (months for a monthly record). */
export function summaryParts(report: FactorReport): { span: string; size: string } {
  const d = report.data;
  const [one, many] = isMonthly(report) ? ["month", "months"] : ["day", "days"];
  return { span: `${dateLong(d.actual_start)} → ${dateLong(d.actual_end)}`, size: plural(d.n_obs, one, many) };
}

/** The text alternative of the bar: what each part holds, in the report's own words. */
export function barLabel(report: FactorReport): string {
  const c = coverage(report);
  const words = periodWord(report);
  const parts = [`${count(c.analysed)} ${isMonthly(report) ? "months" : "trading days"} analysed`];
  if (c.skipped > 0) parts.push(`${count(c.skipped)} ${words} before the window, not analysed`);
  if (c.after > 0) parts.push(`${count(c.after)} ${words} after the factor data end, not analysed`);
  return `Price history: ${parts.join("; ")}.`;
}

function presetList(names: string[]): string {
  if (names.length < 2) return names.join("");
  return `${names.slice(0, -1).join(", ")} and ${names[names.length - 1]}`;
}

/** One line: which presets cannot be chosen. The reasons are in the details. */
export function noteLine(unavailable: readonly UnavailablePreset[]): string {
  const names = unavailable.map((u) => (u.preset === "FULL" ? "Full history" : u.preset));
  return `${presetList(names)} ${names.length === 1 ? "needs" : "need"} more history.`;
}

/** The thin timeline: muted before, solid accent for the analysed window, hatched after. */
function Bar({ report }: { report: FactorReport }) {
  const c = coverage(report);
  const parts: { key: "before" | "analysed" | "after"; n: number }[] = [
    { key: "before", n: c.before },
    { key: "analysed", n: c.analysed },
    { key: "after", n: c.after },
  ];
  return (
    <div className="cov-bar" role="img" aria-label={barLabel(report)}>
      {parts
        .filter((p) => p.n > 0)
        .map((p) => (
          <span key={p.key} className={`cov-seg ${p.key}`} data-part={p.key} style={{ flexGrow: p.n }} />
        ))}
    </div>
  );
}

/**
 * The analysed range in the sidebar, in one glance: a thin timeline of the whole price history
 * (before the window, the analysed window, the days after the factor data end), one line with the
 * dates and the size of the window, a one-line note when a preset cannot be chosen, and a "Details"
 * disclosure with the full sentences. The summary line is announced politely when it changes
 * (dashboard spec DB6.3).
 */
export function AnalysedRange({ report, unavailable = [], noteId, label }: AnalysedRangeProps) {
  const detailsId = useId();
  const line = report ? rangeLine(report) : null;
  const parts = report ? summaryParts(report) : null;
  return (
    <div className="cov" id="analysed-range">
      {label ? <span className="side-label">{label}</span> : null}
      {report && parts ? (
        <>
          <Bar report={report} />
          <p className="cov-line" aria-live="polite" aria-atomic="true">
            <span className="cov-span">{parts.span}</span>
            <span className="cov-size">{parts.size}</span>
          </p>
        </>
      ) : (
        <p className="side-note" aria-live="polite" aria-atomic="true">
          No range analysed yet.
        </p>
      )}
      {unavailable.length > 0 ? (
        <p className="cov-note side-note" id={noteId}>
          {noteLine(unavailable)}
        </p>
      ) : null}
      {line || unavailable.length > 0 ? (
        <details className="cov-more">
          <summary aria-controls={detailsId}>Details</summary>
          <div id={detailsId} className="cov-full side-note">
            {line ? (
              <p>
                <b>{line.head}</b>
                {line.tail ? ` ${line.tail}` : ""}
              </p>
            ) : null}
            {unavailable.map((u) => (
              <p key={u.preset}>{u.reason}</p>
            ))}
          </div>
        </details>
      ) : null}
    </div>
  );
}
