import { useState } from "react";
import type { ReactNode } from "react";
import type { components } from "../../../api/types.gen";
import type { FactorReport, ResidualAnalysis } from "../../../api/types";
import { dateLong, MINUS, num, pct, pval, signed } from "../../../format";
import { finite } from "../../../report/derive";
import { Panel } from "../Panel";
import type { ReportPanelProps } from "../types";
import { firstFiniteIndex, LinePlot } from "./ResidualAlphaChart";
import { DEFAULT_QUESTION, TITLE } from "./ResidualAlphaPanel";
import "./ResidualAlphaPanel.css";

type Stats = components["schemas"]["ResidualStats"];
type Gap = components["schemas"]["ResidualGap"];
type Diagnostics = components["schemas"]["ResidualAlphaDiagnostics"];
type Severity = NonNullable<Gap["severity"]>;

const NA = "n/a";

/*
 * The words of this panel are the words of the static panel
 * (backend/factordesk/report/panels/residual_alpha.py). Change one, change the other: a test on
 * each side reads backend/factordesk/tests/fixtures/sections/residual_alpha_wording.json.
 */

/** Headings, in panel order. */
export const HEADINGS = {
  compare: "In-sample against point-in-time",
  chart: "Cumulative residual return",
  gap: "In-sample against point-in-time, same days",
  stable: "Is the alpha stable?",
  rolling: "Rolling one-year alpha",
  windows: "Separate one-year windows",
  split: "First half against second half",
  years: "Calendar years",
  checks: "Checks on the residual returns",
  caveats: "What to keep in mind",
} as const;

/** State texts when a block has no reason of its own. */
export const NOT_AVAILABLE = {
  compare: "Not available.",
  chart: "The chart is not available.",
  rolling: "The rolling alpha is not available.",
  windows: "The one-year windows are not available.",
  split: "The split-half alphas are not available.",
  years: "The calendar-year sums are not available.",
  checks: "Not available.",
  panel: "Residual analysis is unavailable.",
} as const;

/** What the reader can do when the whole section failed (R8.4). */
export const NEXT_STEP = "Choose a longer date range or another ticker, then run the report again.";
/** What the reader can do when only the point-in-time part lacks days. */
export const PIT_NEXT_STEP = "Choose a shorter beta window or a longer period.";
export const WARMUP_CAPTION = "Warm-up: the first {w} trading days are used to estimate the first point-in-time betas.";
export const WARMUP_SHADED = " Shaded on the chart.";
const UNCOVERED_MEMO = "No factor data after {last}: the residual is unknown for the last {n} trading days.";
const EXCLUDED_NOTE = "Skips {n} excluded days (listed under sample details).";
/** R5.5, the footer of the stability section. */
export const STABILITY_CAUTION =
  "The halves and calendar years are fixed in advance. If you search for the year or split date that looks best, " +
  "the p-values stop meaning what they say: with 10 years to choose from, the best year has a nominal p below 0.05 " +
  "about 40% of the time even when nothing changed.";
/** R6, the line under the checks. */
export const CHECKS_NOTE =
  "With thousands of days these tests detect even small departures. A rejection makes intervals approximate, not wrong.";
/** R5.4 reading rule. */
export const YEARS_READING = "A year within two noise standard deviations of zero is ordinary for a stock with no alpha.";
const NOISE_NOTE = "Pure noise with this volatility typically falls about {ref}.";
const DRAG_NOTE =
  "The line compounds daily. It sits below the residual return in the table by about half the residual variance a year ({drag} here).";
/** Word shown with the glyph of a message (a shape plus a word, never colour alone). */
export const SEVERITY_WORD: Record<Severity, string> = { info: "Note", warning: "Warning", error: "Error" };
/** Footnote keys shown under "How this is computed", in order. */
const FOLD_LABELS = ["L-DESC-PIT", "L-INSAMPLE", "L-PIT", "L-HEDGE", "L-VINTAGE", "L-BAND", "L-OVERLAP"] as const;

/** Reading rules of R3.5, shown as tooltips on the row names. */
export const READING: Record<string, string> = {
  "Residual return, a year":
    "What the stock earned per year beyond its factor exposures, alpha included. In-sample it equals the regression alpha exactly.",
  "t-statistic":
    "Distance of the residual return from zero in standard errors. Between −2 and 2 (p above 0.05), you cannot tell it from zero.",
  "Residual volatility, a year":
    "How much the stock moves for reasons the five factors do not explain. Higher volatility makes alpha harder to measure.",
  "Residual Sharpe (information ratio)":
    "Residual return per unit of residual risk. Do not compare it with a total-return Sharpe. 0.5 for 10 years is only about 1.6 standard errors.",
  "Cumulative (compounded)": "What the daily-rebalanced paper hedge compounded to, before costs.",
  "Compound growth, a year":
    "Lower than the residual return by about half the residual variance a year. Shown beside the arithmetic values, never added to them.",
  "Hit rate": "Share of days the residual was positive. Near 50% is normal; it says how often, not how much.",
  "Max drawdown": "Worst fall of the cumulative residual line from a previous high.",
  Skew: "Below 0: rare large residual losses. Above 0: rare large gains, often earnings days.",
  "Excess kurtosis":
    "Above 0: more extreme days than a normal distribution. Intervals here are then approximate.",
};

// ---------------------------------------------------------------------------- formatting

/** "+27.2%": signed percent, one decimal. */
function sp(x: number | null | undefined): string {
  return x == null ? NA : pct(x, 1);
}
/** "10.3%": unsigned percent (a minus sign only when negative), one decimal. */
function up(x: number | null | undefined): string {
  return x == null ? NA : pct(x, 1, false);
}
function n2(x: number | null | undefined): string {
  return x == null ? NA : num(x, 2);
}
function s2(x: number | null | undefined): string {
  return x == null ? NA : signed(x, 2);
}
function pv(p: number | null | undefined): string {
  return p == null ? NA : pval(p);
}

/** Magnitude of a ratio in percent, to the nearest 5 points, halves away from zero (TR18).
 * The same rule as `factordesk/rounding.py`, with the same 1e-9 tolerance on the half point. */
export function round5(x: number): number {
  return Math.floor(Math.abs(x * 100) / 5 + 0.5 + 1e-9) * 5;
}

/** Share of the in-sample residual kept (R4.7): "100% kept", "more than 200% kept", or a reversed sign. */
export function keptText(ratio: number | null | undefined): string {
  if (ratio == null || !Number.isFinite(ratio)) return NA;
  if (ratio > 2) return "more than 200% kept";
  const pts = round5(ratio);
  if (ratio < 0 && pts > 0) return `${MINUS}${pts}% kept (the sign reversed)`;
  return `${pts}% kept`;
}

/** A share of the full-period alpha, to the nearest 5 points. */
export function shareText(q: number | null | undefined): string {
  if (q == null || !Number.isFinite(q)) return NA;
  if (q > 2) return "more than 200%";
  const pts = round5(q);
  return `${q < 0 && pts > 0 ? MINUS : ""}${pts}%`;
}

/** Printed for the share and the kept rows when the verdict says the alpha is noise. */
export const NOT_DISTINGUISHABLE = "n/a, the in-sample alpha is not distinguishable from zero";
const NO_ALPHA_VERDICTS: readonly (string | null)[] = ["no_reliable_alpha", "point_in_time_only"];

function days(n: number): string {
  return `${n} ${n === 1 ? "day" : "days"}`;
}

function span(start: string | null, end: string | null): string {
  return start && end ? `${dateLong(start)} to ${dateLong(end)}` : NA;
}

/** "95% interval 15.4% to 39.1%", or nothing when an end is missing. */
function interval(lo: number | null | undefined, hi: number | null | undefined, as: (x: number) => string): string {
  return lo == null || hi == null ? "" : `95% interval ${as(lo)} to ${as(hi)}`;
}

function fill(template: string, values: Record<string, string>): string {
  return template.replace(/\{(\w+)\}/g, (_m, k: string) => values[k] ?? "");
}

function lastFinite(values: readonly (number | null)[]): number | null {
  for (let i = values.length - 1; i >= 0; i--) {
    const v = values[i];
    if (typeof v === "number" && Number.isFinite(v)) return v;
  }
  return null;
}

// ---------------------------------------------------------------------------- small parts

/** Glyph by severity: a shape plus a word, never colour alone (design D). */
function SeverityGlyph({ severity }: { severity: Severity }) {
  if (severity === "warning") {
    return (
      <svg className="glyph" aria-hidden="true" viewBox="0 0 16 16">
        <path d="M8 1.5 15 14.5H1z" />
        <path className="cut" d="M8 6v4M8 11.6v1" />
      </svg>
    );
  }
  return (
    <svg className="glyph" aria-hidden="true" viewBox="0 0 16 16">
      <circle cx="8" cy="8" r="6.5" />
      <path className="cut" d="M8 7v4.5M8 4.6v.9" />
    </svg>
  );
}

function Tag({ tag }: { tag: "reliable" | "noise" | null }) {
  if (tag === null) return null;
  return <span className={`res-tag ${tag}`}>{tag}</span>;
}

/** A value with quieter lines under it. */
function Cell({ main, subs = [], extra }: { main: ReactNode; subs?: readonly (string | null | undefined)[]; extra?: ReactNode }) {
  return (
    <>
      <span className="res-main">
        {main}
        {extra}
      </span>
      {subs.map((t, i) =>
        t ? (
          <span key={i} className="res-subl">
            {t}
          </span>
        ) : null,
      )}
    </>
  );
}

/** A block whose own status is not "ok": the reason, in a small sunk box. */
function Unavailable({ reason, fallback, action }: { reason: string | null; fallback: string; action?: string }) {
  return (
    <div className="res-empty">
      <p className="empty-what">{reason ?? fallback}</p>
      {action ? <p className="empty-do">{action}</p> : null}
    </div>
  );
}

function Scroll({ label, children }: { label: string; children: ReactNode }) {
  return (
    // A keyboard user has to be able to scroll a wide table, so the region takes focus.
    // eslint-disable-next-line jsx-a11y/no-noninteractive-tabindex
    <div className="scroll-x res-scroll" tabIndex={0} role="region" aria-label={`${label}, scrolls sideways`}>
      {children}
    </div>
  );
}

/** A block of the stability section under its own heading. */
function Sub({ heading, children }: { heading: string; children: ReactNode }) {
  return (
    <div className="res-sub">
      <h4>{heading}</h4>
      {children}
    </div>
  );
}

function Note({ children }: { children: ReactNode }) {
  return children ? <p className="res-cap">{children}</p> : null;
}

/** The legend and table swatch of a chart line: ink, grey or a dash pattern. */
function Key({ line }: { line: "full" | "ins" | "pit" }) {
  return (
    <svg className="sw" aria-hidden="true" viewBox="0 0 22 8">
      <line className={`res-key ${line}`} x1="0" x2="22" y1="4" y2="4" />
    </svg>
  );
}

// ---------------------------------------------------------------------------- the table

function drawdownSubs(s: Stats): string[] {
  const subs: string[] = [];
  if (s.max_drawdown_trough === null) {
    subs.push("No fall from a previous high.");
  } else {
    const peak = s.max_drawdown_peak ? dateLong(s.max_drawdown_peak) : "the start";
    const rec = s.max_drawdown_recovery ? `recovered ${dateLong(s.max_drawdown_recovery)}` : "not recovered";
    subs.push(`Peak ${peak}, trough ${dateLong(s.max_drawdown_trough)}, ${rec}.`);
  }
  if (s.noise_drawdown_reference != null) {
    subs.push(fill(NOISE_NOTE, { ref: up(s.noise_drawdown_reference) }));
  }
  return subs;
}

interface Row {
  label: string;
  cell: (s: Stats) => ReactNode;
}

const ROWS: Row[] = [
  {
    label: "Period",
    cell: (s) => <Cell main={span(s.sample.start, s.sample.end)} subs={[`${s.sample.n} trading days`]} />,
  },
  {
    label: "Residual return, a year",
    cell: (s) => (
      <Cell
        main={sp(s.residual_return_annual)}
        subs={[interval(s.residual_return_ci_low_annual, s.residual_return_ci_high_annual, up)]}
      />
    ),
  },
  {
    label: "t-statistic",
    cell: (s) => <Cell main={n2(s.z)} extra={s.tag ? <Tag tag={s.tag} /> : null} />,
  },
  { label: "Residual volatility, a year", cell: (s) => <Cell main={up(s.residual_vol_annual)} /> },
  {
    label: "Residual Sharpe (information ratio)",
    cell: (s) => (
      <Cell
        main={n2(s.information_ratio)}
        subs={[interval(s.information_ratio_ci_low, s.information_ratio_ci_high, (x) => num(x, 2))]}
      />
    ),
  },
  { label: "Cumulative (compounded)", cell: (s) => <Cell main={sp(s.cumulative_return)} /> },
  { label: "Compound growth, a year", cell: (s) => <Cell main={sp(s.compound_growth_annual)} /> },
  { label: "Hit rate", cell: (s) => <Cell main={up(s.hit_rate)} /> },
  {
    label: "Max drawdown",
    cell: (s) => (s.max_drawdown == null ? <Cell main={NA} /> : <Cell main={sp(s.max_drawdown)} subs={drawdownSubs(s)} />),
  },
  { label: "Skew", cell: (s) => <Cell main={s2(s.skew)} /> },
  { label: "Excess kurtosis", cell: (s) => <Cell main={s2(s.excess_kurtosis)} /> },
];

/** A column whose statistic is not "ok": one tall cell with the reason and, if any, one next step. */
function MissingColumn({ s, action }: { s: Stats; action: string }) {
  return (
    <td className="res-missing" rowSpan={ROWS.length} data-basis={s.basis}>
      <p className="empty-what">{s.reason ?? NOT_AVAILABLE.compare}</p>
      {action ? <p className="empty-do">{action}</p> : null}
    </td>
  );
}

/** The two-column table: in-sample against point-in-time, one row per statistic. */
function StatsTable({ section }: { section: ResidualAnalysis }) {
  const { in_sample: ins, point_in_time: pit, beta_window: w } = section;
  return (
    <>
      <h3>{HEADINGS.compare}</h3>
      <table className="res-table" aria-labelledby="residual-table-cap">
        <caption id="residual-table-cap" className="vh">
          Residual return of the stock, in-sample against point-in-time
        </caption>
        <thead>
          <tr>
            <th scope="col" className="lab">
              <span className="vh">Measure</span>
            </th>
            <th scope="col">In-sample (static betas)</th>
            <th scope="col">Point-in-time (trailing {w}-day betas)</th>
          </tr>
        </thead>
        <tbody>
          {ROWS.map((row, r) => (
            <tr key={row.label}>
              <th scope="row" title={READING[row.label]}>
                {row.label}
              </th>
              {ins.status === "ok" ? (
                <td>{row.cell(ins)}</td>
              ) : r === 0 ? (
                <MissingColumn s={ins} action="" />
              ) : null}
              {pit.status === "ok" ? (
                <td>{row.cell(pit)}</td>
              ) : r === 0 ? (
                <MissingColumn s={pit} action={pit.status === "insufficient_data" ? PIT_NEXT_STEP : ""} />
              ) : null}
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}

// ---------------------------------------------------------------------------- gap

function GapBlock({ gap, pit }: { gap: Gap; pit: Stats }) {
  // The point-in-time column already says why when that part is missing; no second message.
  if (gap.status !== "ok" && pit.status !== "ok") return null;
  if (gap.status !== "ok") {
    return (
      <div className="res-gap">
        <h3>{HEADINGS.gap}</h3>
        <Unavailable reason={gap.reason} fallback={NOT_AVAILABLE.checks} />
      </div>
    );
  }
  const severity: Severity = gap.severity ?? "info";
  const noAlpha = NO_ALPHA_VERDICTS.includes(gap.verdict);
  const rows: [string, ReactNode][] = [
    ["Days compared", <Cell main={span(gap.sample.start, gap.sample.end)} subs={[days(gap.sample.n)]} />],
    ["In-sample betas, same days", <Cell main={`${sp(gap.in_sample_same_days_annual)} a year`} />],
    ["Point-in-time betas", <Cell main={`${sp(gap.point_in_time_annual)} a year`} />],
    [
      "Gap",
      <Cell main={`${sp(gap.gap_annual)} a year`} subs={[`Approximate: z ${n2(gap.gap_z)}, p ${pv(gap.gap_p)}.`]} />,
    ],
    ["Share of the full-period alpha earned on these days", <Cell main={noAlpha ? NOT_DISTINGUISHABLE : shareText(gap.comparison_share_of_alpha)} />],
    ["Kept with point-in-time betas", <Cell main={noAlpha ? NOT_DISTINGUISHABLE : keptText(gap.survival_ratio)} />],
  ];
  return (
    <div className="res-gap">
      <h3 id="residual-gap-h">{HEADINGS.gap}</h3>
      {gap.message ? (
        <div className={`res-verdict ${severity}`} data-verdict={gap.verdict ?? "none"}>
          <SeverityGlyph severity={severity} />
          <p>
            <strong className="res-sev">{SEVERITY_WORD[severity]}</strong> {gap.message}
          </p>
        </div>
      ) : null}
      <dl className="res-facts" aria-labelledby="residual-gap-h">
        {rows.map(([name, value]) => (
          <div key={name}>
            <dt>{name}</dt>
            <dd>{value}</dd>
          </div>
        ))}
      </dl>
      <Note>{gap.caption}</Note>
    </div>
  );
}

// ---------------------------------------------------------------------------- chart

type View = "both" | "full";

function ChartBlock({ section }: { section: ResidualAnalysis }) {
  const [view, setView] = useState<View>("both");
  const { chart, in_sample: ins, point_in_time: pit, gap, beta_window: w } = section;
  if (chart.status !== "ok" || chart.dates.length < 2) {
    return (
      <div className="res-chart">
        <h3>{HEADINGS.chart}</h3>
        <Unavailable reason={chart.reason} fallback={NOT_AVAILABLE.chart} />
      </div>
    );
  }
  const pitOk = chart.point_in_time_status === "ok" && chart.comparison_start !== null;
  const found = pitOk ? chart.dates.indexOf(chart.comparison_start as string) : -1;
  const anchor = pitOk ? (found >= 0 ? found : Math.max(firstFiniteIndex(chart.point_in_time_compare), 0)) : 0;
  const shown: View = pitOk ? view : "full";
  const lastCovered = section.sample.factor_vintage.last_date;

  // The same-days line is drawn wide and light, then the point-in-time line thin and dark on top,
  // so the dashes stay visible where the two coincide.
  const lines =
    shown === "both"
      ? [
          { id: "in_sample_compare", className: "ins", values: chart.in_sample_compare },
          { id: "point_in_time_compare", className: "pit", values: chart.point_in_time_compare },
        ]
      : [{ id: "in_sample_full", className: "full", values: chart.in_sample_full }];

  const drag = shown === "both" ? pit.residual_vol_annual : ins.residual_vol_annual;
  const wipeouts = section.warnings.filter((x) => x.code === "residual_wipeout");
  const excluded = chart.n_excluded_in_span;

  return (
    <div className="res-chart">
      <div className="res-chart-head">
        <h3 id="residual-chart-h">{HEADINGS.chart}</h3>
        {pitOk ? (
          <div className="seg" role="group" aria-label="Residual chart view">
            <span className="seg-btns">
              <input
                type="radio"
                name="residual-view"
                id="residual-view-both"
                checked={shown === "both"}
                onChange={() => setView("both")}
              />
              <label htmlFor="residual-view-both">Same days, both lines</label>
              <input
                type="radio"
                name="residual-view"
                id="residual-view-full"
                checked={shown === "full"}
                onChange={() => setView("full")}
              />
              <label htmlFor="residual-view-full">Full period, in-sample</label>
            </span>
          </div>
        ) : null}
      </div>
      {wipeouts.map((x) => (
        <div key={x.message} className="res-verdict warning" data-warning={x.code}>
          <SeverityGlyph severity="warning" />
          <p>
            <strong className="res-sev">Warning</strong> {x.message}
          </p>
        </div>
      ))}
      <ul className="legend res-legend" aria-label="Legend">
        {shown === "both" ? (
          <>
            <li>
              <Key line="ins" />
              In-sample, same days as point-in-time
            </li>
            <li>
              <Key line="pit" />
              Point-in-time
            </li>
          </>
        ) : (
          <li>
            <Key line="full" />
            In-sample, whole period
          </li>
        )}
      </ul>
      <LinePlot
        dates={chart.dates}
        from={shown === "both" ? anchor : 0}
        lines={lines}
        shadeTo={shown === "full" && pitOk ? anchor : undefined}
        tail={chart.n_uncovered}
        testId="residual-chart"
      />
      <Scroll label="Cumulative residual return by line">
        <table className="res-mini">
          <caption className="vh">
            Cumulative residual return at the end of each line, with the yearly residual return and its t-statistic
          </caption>
          <thead>
            <tr>
              <th scope="col">Line</th>
              <th scope="col" className="num">
                Cumulative at the end
              </th>
              <th scope="col" className="num">
                Residual return, a year
              </th>
              <th scope="col" className="num">
                t-statistic
              </th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <th scope="row">
                <span className="res-lab">
                  <Key line="full" />
                  In-sample, whole period
                </span>
                <span className="res-subl">from {dateLong(chart.dates[0] as string)}</span>
              </th>
              <td className="num">
                <Cell main={sp(lastFinite(chart.in_sample_full))} />
              </td>
              <td className="num">
                <Cell main={sp(ins.residual_return_annual)} />
              </td>
              <td className="num">
                <Cell main={n2(ins.z)} />
              </td>
            </tr>
            {pitOk ? (
              <>
                <tr>
                  <th scope="row">
                    <span className="res-lab">
                      <Key line="ins" />
                      In-sample, same days
                    </span>
                    <span className="res-subl">from {dateLong(chart.comparison_start as string)}</span>
                  </th>
                  <td className="num">
                    <Cell main={sp(lastFinite(chart.in_sample_compare))} />
                  </td>
                  <td className="num">
                    <Cell main={sp(gap.in_sample_same_days_annual)} />
                  </td>
                  <td className="num">
                    <Cell main={NA} />
                  </td>
                </tr>
                <tr>
                  <th scope="row">
                    <span className="res-lab">
                      <Key line="pit" />
                      Point-in-time
                    </span>
                    <span className="res-subl">from {dateLong(chart.comparison_start as string)}</span>
                  </th>
                  <td className="num">
                    <Cell main={sp(lastFinite(chart.point_in_time_compare))} />
                  </td>
                  <td className="num">
                    <Cell main={sp(pit.residual_return_annual)} />
                  </td>
                  <td className="num">
                    <Cell main={n2(pit.z)} />
                  </td>
                </tr>
              </>
            ) : (
              <tr>
                <th scope="row">
                  <span className="res-lab">Point-in-time</span>
                </th>
                <td className="res-missing" colSpan={3}>
                  <p className="empty-what">{chart.point_in_time_reason ?? pit.reason ?? NOT_AVAILABLE.compare}</p>
                  {chart.point_in_time_status === "insufficient_data" ? (
                    <p className="empty-do">{PIT_NEXT_STEP}</p>
                  ) : null}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </Scroll>
      <Note>{chart.caption}</Note>
      {drag != null ? <Note>{fill(DRAG_NOTE, { drag: up((drag * drag) / 2) })}</Note> : null}
      {pitOk && shown === "full" ? <Note>{fill(WARMUP_CAPTION, { w: String(w) }) + WARMUP_SHADED}</Note> : null}
      {chart.n_uncovered > 0 ? (
        <Note>{fill(UNCOVERED_MEMO, { last: dateLong(lastCovered), n: String(chart.n_uncovered) })}</Note>
      ) : null}
      {excluded > 0 ? <Note>{fill(EXCLUDED_NOTE, { n: String(excluded) })}</Note> : null}
    </div>
  );
}

// ---------------------------------------------------------------------------- stability

function RollingBlock({ section }: { section: ResidualAnalysis }) {
  const ra = section.rolling_alpha;
  const from = ra.status === "ok" ? firstFiniteIndex(ra.alpha_annual) : -1;
  if (ra.status !== "ok" || from < 0 || ra.dates.length - from < 2) {
    return (
      <Sub heading={HEADINGS.rolling}>
        <Unavailable reason={ra.reason} fallback={NOT_AVAILABLE.rolling} />
      </Sub>
    );
  }
  const present: { i: number; a: number; lo: number | null; hi: number | null }[] = [];
  ra.alpha_annual.forEach((a, i) => {
    if (typeof a === "number") present.push({ i, a, lo: ra.ci_low_annual[i] ?? null, hi: ra.ci_high_annual[i] ?? null });
  });
  const latest = present[present.length - 1];
  const alphas = present.map((p) => p.a);
  const share = finite(ra.share_excluding_zero);
  return (
    <Sub heading={HEADINGS.rolling}>
      <LinePlot
        dates={ra.dates}
        from={from}
        lines={[{ id: "rolling_alpha", className: "roll", values: ra.alpha_annual }]}
        band={{ low: ra.ci_low_annual, high: ra.ci_high_annual }}
        testId="residual-rolling-chart"
      />
      <dl className="res-facts" aria-label="Rolling one-year alpha, summary of the estimates">
        {latest ? (
          <>
            <div>
              <dt>Latest one-year alpha</dt>
              <dd>
                <Cell
                  main={`${sp(latest.a)} a year`}
                  subs={[`Pointwise band ${up(latest.lo)} to ${up(latest.hi)}, ending ${dateLong(ra.dates[latest.i] as string)}.`]}
                />
              </dd>
            </div>
            <div>
              <dt>Lowest and highest</dt>
              <dd>
                <Cell main={`${up(Math.min(...alphas))} to ${up(Math.max(...alphas))}`} />
              </dd>
            </div>
          </>
        ) : null}
        <div>
          <dt>Windows whose 95% band excludes zero</dt>
          <dd>
            <Cell main={share === null ? NA : up(share)} subs={["A descriptive count, not a test."]} />
          </dd>
        </div>
      </dl>
      <Note>{ra.caption}</Note>
    </Sub>
  );
}

function WindowsBlock({ section }: { section: ResidualAnalysis }) {
  const no = section.non_overlapping;
  if (no.status !== "ok") {
    return (
      <Sub heading={HEADINGS.windows}>
        <Unavailable reason={no.reason} fallback={NOT_AVAILABLE.windows} />
      </Sub>
    );
  }
  return (
    <Sub heading={HEADINGS.windows}>
      <p className="res-sentence">
        {no.n_reliable} of {no.family_size} separate one-year windows show an alpha different from zero, after
        correcting for testing {no.family_size} windows.
      </p>
      <Scroll label="Separate one-year windows">
        <table className="res-mini wide">
          <caption className="vh">Separate one-year windows: alpha, standard error, z, p, adjusted p and reading</caption>
          <thead>
            <tr>
              <th scope="col">Window</th>
              <th scope="col" className="num">
                Alpha, a year
              </th>
              <th scope="col" className="num">
                z
              </th>
              <th scope="col" className="num">
                Adjusted p
              </th>
              <th scope="col" className="num">
                Reading
              </th>
            </tr>
          </thead>
          <tbody>
            {no.windows.map((win) => (
              <tr key={win.start}>
                <th scope="row">
                  {span(win.start, win.end)}
                  <span className="res-subl">{days(win.n)}</span>
                </th>
                <td className="num">
                  <Cell main={sp(win.alpha_annual)} subs={[`std. error ${up(win.se_annual)}`]} />
                </td>
                <td className="num">
                  <Cell main={n2(win.z)} subs={[`p ${pv(win.p)}`]} />
                </td>
                <td className="num">
                  <Cell main={pv(win.p_adj_bh)} />
                </td>
                <td className="num">
                  <Cell main={win.tag ?? NA} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Scroll>
      <Note>{no.caption}</Note>
    </Sub>
  );
}

function SplitBlock({ section }: { section: ResidualAnalysis }) {
  const sh = section.split_half;
  if (sh.status !== "ok") {
    return (
      <Sub heading={HEADINGS.split}>
        <Unavailable reason={sh.reason} fallback={NOT_AVAILABLE.split} />
      </Sub>
    );
  }
  const half = (
    start: string,
    end: string,
    n: number,
    alpha: number | null,
    lo: number | null,
    hi: number | null,
  ): ReactNode => (
    <td className="num">
      <Cell main={sp(alpha)} subs={[interval(lo, hi, up), `${span(start, end)}, ${days(n)}`]} />
    </td>
  );
  return (
    <Sub heading={HEADINGS.split}>
      <p className="res-sentence">
        Second-half alpha minus first-half alpha: {sp(sh.difference_annual)} a year (p = {pv(sh.difference_p)}).
      </p>
      <Scroll label="First half against second half">
        <table className="res-mini">
          <caption className="vh">Alpha in each half of the period</caption>
          <thead>
            <tr>
              <th scope="col">
                <span className="vh">Measure</span>
              </th>
              <th scope="col" className="num">
                First half
              </th>
              <th scope="col" className="num">
                Second half
              </th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <th scope="row">Alpha, a year</th>
              {half(
                sh.first_start,
                sh.first_end,
                sh.n_first,
                sh.alpha_first_annual,
                sh.alpha_first_ci_low_annual,
                sh.alpha_first_ci_high_annual,
              )}
              {half(
                sh.second_start,
                sh.second_end,
                sh.n_second,
                sh.alpha_second_annual,
                sh.alpha_second_ci_low_annual,
                sh.alpha_second_ci_high_annual,
              )}
            </tr>
          </tbody>
        </table>
      </Scroll>
      <Note>{sh.caption}</Note>
    </Sub>
  );
}

/** Sum as a decimal for the tooltip of a calendar-year cell, with a plain minus as the backend writes it. */
function sumTip(sum: number, sd: number): string {
  return `Sum ${sum.toFixed(4)}, noise standard deviation ${sd.toFixed(4)}`;
}

function YearsBlock({ section }: { section: ResidualAnalysis }) {
  const cy = section.calendar_years;
  if (cy.status !== "ok" || cy.years.length === 0) {
    return (
      <Sub heading={HEADINGS.years}>
        <Unavailable reason={cy.reason} fallback={NOT_AVAILABLE.years} />
      </Sub>
    );
  }
  return (
    <Sub heading={HEADINGS.years}>
      <Scroll label="Calendar years">
        <table className="res-mini">
          <caption className="vh">Sum of daily residual returns in each calendar year</caption>
          <thead>
            <tr>
              <th scope="col">Year</th>
              <th scope="col" className="num">
                In-sample sum
              </th>
              <th scope="col" className="num">
                Point-in-time sum
              </th>
            </tr>
          </thead>
          <tbody>
            {cy.years.map((y) => (
              <tr key={y.year}>
                <th scope="row">
                  {y.year}
                  <span className="res-subl">
                    {days(y.n)}
                    {y.partial ? ", partial year" : ""}
                  </span>
                </th>
                <td className="num" title={sumTip(y.in_sample_sum, y.in_sample_noise_sd)}>
                  <Cell main={sp(y.in_sample_sum)} subs={[`noise ${up(y.in_sample_noise_sd)}`]} />
                </td>
                {y.point_in_time_sum == null || y.point_in_time_noise_sd == null ? (
                  <td className="num">
                    <Cell main={NA} subs={["No point-in-time days."]} />
                  </td>
                ) : (
                  <td className="num" title={sumTip(y.point_in_time_sum, y.point_in_time_noise_sd)}>
                    <Cell
                      main={sp(y.point_in_time_sum)}
                      subs={[`noise ${up(y.point_in_time_noise_sd)}, ${days(y.n_point_in_time)}`]}
                    />
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </Scroll>
      <Note>{cy.caption}</Note>
      <Note>{YEARS_READING}</Note>
    </Sub>
  );
}

const CHECK_NAMES = ["Ljung-Box", "Jarque-Bera", "ARCH"] as const;

function checkP(d: Diagnostics): (number | null)[] {
  return [d.ljung_box_p, d.jarque_bera_p, d.arch_lm_p];
}

function ChecksBlock({ section }: { section: ResidualAnalysis }) {
  if (section.diagnostics.length === 0) return null;
  const caption = section.diagnostics.find((d) => d.caption)?.caption ?? "";
  return (
    <div className="res-checks-block">
      <h3>{HEADINGS.checks}</h3>
      <div className="res-checks">
        {section.diagnostics.map((d) => (
          <div key={d.basis}>
            <h4>{d.basis === "in_sample" ? "In-sample" : "Point-in-time"}</h4>
            {d.status !== "ok" ? (
              <Unavailable reason={d.reason} fallback={NOT_AVAILABLE.checks} />
            ) : (
              <ul className="notes">
                {d.findings.map((f, i) => {
                  const named = d.findings.length === CHECK_NAMES.length;
                  return (
                    <li key={f}>
                      {f}
                      {named ? ` (${CHECK_NAMES[i]}, p = ${pv(checkP(d)[i])})` : ""}
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
        ))}
      </div>
      <Note>{caption}</Note>
      <Note>{CHECKS_NOTE}</Note>
    </div>
  );
}

function Stability({ section }: { section: ResidualAnalysis }) {
  return (
    <details className="res-stab" open>
      <summary>
        <h3>{HEADINGS.stable}</h3>
      </summary>
      <RollingBlock section={section} />
      <WindowsBlock section={section} />
      <SplitBlock section={section} />
      <YearsBlock section={section} />
      <p className="res-caution">{STABILITY_CAUTION}</p>
    </details>
  );
}

// ---------------------------------------------------------------------------- panel

/** Method detail folded into "How this is computed": the captions, then the label texts of the section. */
function howText(report: FactorReport, section: ResidualAnalysis): string {
  const texts = report.label_text ?? {};
  const paras: (string | null | undefined)[] = [section.in_sample.caption];
  if (section.point_in_time.status === "ok") paras.push(section.point_in_time.caption);
  for (const key of FOLD_LABELS) paras.push(texts[key]);
  const seen: string[] = [];
  for (const t of paras) if (t && !seen.includes(t)) seen.push(t);
  return seen.join(" ");
}

/** The whole panel once its chunk has loaded; `ResidualAlphaPanel` loads it on demand. */
export function ResidualAlphaBody({ report }: ReportPanelProps) {
  const section = report.residual;
  if (section === null) return null;
  const question = section.question || DEFAULT_QUESTION;
  if (section.status !== "ok") {
    return (
      <Panel
        id="residual"
        title={TITLE}
        question={question}
        empty={{ reason: section.reason ?? NOT_AVAILABLE.panel, action: NEXT_STEP }}
      />
    );
  }
  const others = section.warnings.filter((x) => x.code !== "residual_wipeout");
  return (
    <Panel id="residual" title={TITLE} question={question} how={howText(report, section)}>
      <StatsTable section={section} />
      <ChartBlock section={section} />
      <GapBlock gap={section.gap} pit={section.point_in_time} />
      <Stability section={section} />
      <ChecksBlock section={section} />
      <h3>{HEADINGS.caveats}</h3>
      <ul className="notes res-caveats" aria-label="Caveats">
        {section.caveats.map((c) => (
          <li key={c}>{c}</li>
        ))}
        {others.map((x) => (
          <li key={`${x.code}-${x.message}`} data-warning={x.code}>
            {x.message}
          </li>
        ))}
      </ul>
    </Panel>
  );
}
