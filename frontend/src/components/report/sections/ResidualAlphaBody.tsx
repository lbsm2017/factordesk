import { useState } from "react";
import type { ReactNode } from "react";
import type { components } from "../../../api/types.gen";
import type { FactorReport, ResidualAnalysis } from "../../../api/types";
import { count, dateLong, num, pct, pval } from "../../../format";
import { finite, labelTexts } from "../../../report/derive";
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

/** R5.5, the footer of the stability section. */
const MINING_CAUTION =
  "The halves and calendar years are fixed in advance. If you search for the year or split date that looks best, " +
  "the p-values stop meaning what they say: with 10 years to choose from, the best year has a nominal p below 0.05 " +
  "about 40% of the time even when nothing changed.";
/** R6, the drawer line under the checks. */
const CHECKS_NOTE =
  "With thousands of days these tests detect even small departures. A rejection makes intervals approximate, not wrong.";
/** R5.4 reading rule. */
const YEAR_RULE = "A year within two noise standard deviations of zero is ordinary for a stock with no alpha.";

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
function interval(lo: number | null | undefined, hi: number | null | undefined, as: (x: number) => string): string {
  return lo == null || hi == null ? NA : `${as(lo)} to ${as(hi)}`;
}
function dec4(x: number | null | undefined): string {
  return x == null ? NA : num(x, 4);
}
function sdec4(x: number | null | undefined): string {
  return x == null ? NA : (x > 0 ? "+" : "") + num(x, 4);
}
function pv(p: number | null | undefined): string {
  return p == null ? NA : pval(p);
}

/** Share of the in-sample residual kept (R4.7): to the nearest 5 points, "more than 200%" above 2. */
export function keptText(s: number | null | undefined): string {
  if (s == null) return NA;
  if (s > 2) return "more than 200% kept";
  return `${num(Math.round(s * 20) * 5, 0)}% kept`;
}

function days(n: number): string {
  return `${count(n)} ${n === 1 ? "day" : "days"}`;
}

function span(start: string | null, end: string | null, n: number): string {
  return start && end ? `${dateLong(start)} to ${dateLong(end)}, ${days(n)}` : NA;
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

/** A block whose own status is not "ok": the reason, in a small sunk box. */
function Unavailable({ reason, action }: { reason: string | null; action?: string }) {
  return (
    <div className="res-empty">
      <p className="empty-what">{reason ?? "Not available for this period."}</p>
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

// ---------------------------------------------------------------------------- the table

interface Row {
  key: string;
  label: string;
  /** Reading rule (R3.5), shown as a tooltip. */
  hint?: string;
  cell: (s: Stats) => ReactNode;
}

function drawdownDates(s: Stats): ReactNode {
  if (s.max_drawdown_trough === null) return null;
  return (
    <>
      <span className="ci d">Peak {s.max_drawdown_peak ? dateLong(s.max_drawdown_peak) : "start of period"}</span>
      <span className="ci d">Trough {dateLong(s.max_drawdown_trough)}</span>
      <span className="ci d">
        {s.max_drawdown_recovery ? `Recovered ${dateLong(s.max_drawdown_recovery)}` : "Not recovered"}
      </span>
    </>
  );
}

const ROWS: Row[] = [
  {
    key: "period",
    label: "Period",
    cell: (s) => span(s.sample.start, s.sample.end, s.sample.n),
  },
  {
    key: "ret",
    label: "Residual return, a year",
    hint: "What the stock earned per year beyond its factor exposures, alpha included. In-sample it equals the regression alpha exactly.",
    cell: (s) => (
      <>
        <span className="strong">{sp(s.residual_return_annual)}</span>{" "}
        <span className="ci">({interval(s.residual_return_ci_low_annual, s.residual_return_ci_high_annual, up)})</span>
      </>
    ),
  },
  {
    key: "t",
    label: "t-statistic",
    hint: "Distance of the residual return from zero in standard errors. Between −2 and 2 (p above 0.05), you cannot tell it from zero.",
    cell: (s) => (
      <>
        {n2(s.z)} <Tag tag={s.tag} />
      </>
    ),
  },
  {
    key: "vol",
    label: "Residual volatility, a year",
    hint: "How much the stock moves for reasons the five factors do not explain. Higher volatility makes alpha harder to measure.",
    cell: (s) => up(s.residual_vol_annual),
  },
  {
    key: "ir",
    label: "Residual Sharpe (information ratio)",
    hint: "Residual return per unit of residual risk. Do not compare it with a total-return Sharpe.",
    cell: (s) => (
      <>
        <span className="strong">{n2(s.information_ratio)}</span>{" "}
        <span className="ci">({interval(s.information_ratio_ci_low, s.information_ratio_ci_high, (x) => num(x, 2))})</span>
      </>
    ),
  },
  {
    key: "cum",
    label: "Cumulative (compounded)",
    hint: "What the daily-rebalanced paper hedge compounded to, before costs.",
    cell: (s) => sp(s.cumulative_return),
  },
  {
    key: "growth",
    label: "Compound growth, a year",
    hint: "Lower than the residual return by about half the residual variance a year. Shown beside the arithmetic values, never added to them.",
    cell: (s) => sp(s.compound_growth_annual),
  },
  {
    key: "hit",
    label: "Hit rate",
    hint: "Share of days the residual was positive. Near 50% is normal; it says how often, not how much.",
    cell: (s) => up(s.hit_rate),
  },
  {
    key: "dd",
    label: "Max drawdown",
    hint: "Worst fall of the cumulative residual line from a previous high.",
    cell: (s) => (
      <>
        <span className="strong">{sp(s.max_drawdown)}</span>
        {drawdownDates(s)}
      </>
    ),
  },
  {
    key: "noise",
    label: "Drawdown of pure noise",
    hint: "Pure noise with this volatility typically falls about this far.",
    cell: (s) => sp(s.noise_drawdown_reference),
  },
  {
    key: "skew",
    label: "Skew",
    hint: "Below 0: rare large residual losses. Above 0: rare large gains, often earnings days.",
    cell: (s) => n2(s.skew),
  },
  {
    key: "kurt",
    label: "Excess kurtosis",
    hint: "Above 0: more extreme days than a normal distribution. Intervals here are then approximate.",
    cell: (s) => n2(s.excess_kurtosis),
  },
];

/** A column whose statistic is not "ok": one tall cell with the reason and one next step. */
function MissingColumn({ s, action }: { s: Stats; action: string }) {
  return (
    <td className="res-missing" rowSpan={ROWS.length} data-basis={s.basis}>
      <p className="empty-what">{s.reason ?? "Not available for this period."}</p>
      <p className="empty-do">{action}</p>
    </td>
  );
}

/** The two-column table: in-sample against point-in-time, one row per statistic. */
function StatsTable({ section }: { section: ResidualAnalysis }) {
  const { in_sample: ins, point_in_time: pit, beta_window: w } = section;
  return (
    <table className="res-table" aria-labelledby="residual-table-cap">
      <caption id="residual-table-cap" className="vh">
        Residual return, in-sample with static betas against point-in-time with trailing {w}-day betas
      </caption>
      <thead>
        <tr>
          <th scope="col" className="lab">
            <span className="vh">Statistic</span>
          </th>
          <th scope="col">In-sample (static betas)</th>
          <th scope="col">Point-in-time (trailing {w}-day betas)</th>
        </tr>
      </thead>
      <tbody>
        {ROWS.map((row, r) => (
          <tr key={row.key}>
            <th scope="row" title={row.hint}>
              {row.label}
            </th>
            {ins.status === "ok" ? (
              <td>{row.cell(ins)}</td>
            ) : r === 0 ? (
              <MissingColumn s={ins} action="Choose a longer period." />
            ) : null}
            {pit.status === "ok" ? (
              <td>{row.cell(pit)}</td>
            ) : r === 0 ? (
              <MissingColumn s={pit} action="Choose a shorter beta window or a longer period." />
            ) : null}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

// ---------------------------------------------------------------------------- gap

function GapBlock({ gap, inSample, pit }: { gap: Gap; inSample: Stats; pit: Stats }) {
  // The point-in-time column already says why when that part is missing; no second message.
  if (gap.status !== "ok" && pit.status !== "ok") return null;
  if (gap.status !== "ok") {
    return (
      <div className="res-gap">
        <h3>In-sample against point-in-time</h3>
        <Unavailable reason={gap.reason} />
      </div>
    );
  }
  const severity: Severity = gap.severity ?? "info";
  return (
    <div className="res-gap">
      <h3 id="residual-gap-h">In-sample against point-in-time, same days</h3>
      <dl className="res-facts" aria-labelledby="residual-gap-h">
        <div>
          <dt>Same days</dt>
          <dd>{span(gap.sample.start, gap.sample.end, gap.sample.n)}</dd>
        </div>
        <div>
          <dt>In-sample on these days</dt>
          <dd>{sp(gap.in_sample_same_days_annual)} a year</dd>
        </div>
        <div>
          <dt>Point-in-time</dt>
          <dd>{sp(gap.point_in_time_annual)} a year</dd>
        </div>
        <div>
          <dt>Gap</dt>
          <dd>
            {sp(gap.gap_annual)} a year{" "}
            <span className="ci">
              (approximate test: z {n2(gap.gap_z)}, p {pv(gap.gap_p)})
            </span>
          </dd>
        </div>
        <div>
          <dt>Share of the full-period alpha ({sp(inSample.residual_return_annual)}) earned on these days</dt>
          <dd>{gap.comparison_share_of_alpha == null ? NA : pct(gap.comparison_share_of_alpha, 0, false)}</dd>
        </div>
        <div>
          <dt>Kept with point-in-time betas</dt>
          <dd>{keptText(gap.survival_ratio)}</dd>
        </div>
      </dl>
      {gap.message ? (
        <div className={`res-verdict ${severity}`} data-verdict={gap.verdict ?? "none"}>
          <SeverityGlyph severity={severity} />
          <p>
            <strong className="res-sev">{severity === "warning" ? "Warning" : "Note"}</strong> {gap.message}
          </p>
        </div>
      ) : null}
    </div>
  );
}

// ---------------------------------------------------------------------------- chart

type View = "both" | "full";

function lineStats(values: readonly (number | null)[]): { lo: number; hi: number; end: number } | null {
  const v = values.filter((x): x is number => typeof x === "number" && Number.isFinite(x));
  if (v.length === 0) return null;
  return { lo: Math.min(...v), hi: Math.max(...v), end: v[v.length - 1] as number };
}

function ChartBlock({ report, section }: { report: FactorReport; section: ResidualAnalysis }) {
  const [view, setView] = useState<View>("both");
  const { chart, in_sample: ins, point_in_time: pit, gap, beta_window: w } = section;
  if (chart.status !== "ok" || chart.dates.length < 2) {
    return (
      <div className="res-chart">
        <h3>Cumulative residual return</h3>
        <Unavailable reason={chart.reason} />
      </div>
    );
  }
  const pitOk = chart.point_in_time_status === "ok" && chart.comparison_start !== null;
  const found = pitOk ? chart.dates.indexOf(chart.comparison_start as string) : -1;
  const anchor = pitOk ? (found >= 0 ? found : Math.max(firstFiniteIndex(chart.point_in_time_compare), 0)) : 0;
  const shown: View = pitOk ? view : "full";
  const lastCovered = section.sample.factor_vintage.last_date;

  const lines =
    shown === "both"
      ? [
          { id: "in_sample_compare", className: "ins", values: chart.in_sample_compare },
          { id: "point_in_time_compare", className: "pit", values: chart.point_in_time_compare },
        ]
      : [{ id: "in_sample_full", className: "full", values: chart.in_sample_full }];

  const tableRows = [
    { id: "in_sample_full", label: "In-sample, full period", from: chart.dates[0] as string, values: chart.in_sample_full },
    ...(pitOk
      ? [
          {
            id: "in_sample_compare",
            label: "In-sample, same days",
            from: chart.comparison_start as string,
            values: chart.in_sample_compare,
          },
          {
            id: "point_in_time_compare",
            label: "Point-in-time",
            from: chart.comparison_start as string,
            values: chart.point_in_time_compare,
          },
        ]
      : []),
  ];

  const drag = shown === "both" ? pit.residual_vol_annual : ins.residual_vol_annual;
  const dragText =
    drag == null
      ? null
      : `The line compounds daily. It sits below the residual return in the table by about half the residual variance a year (${up((drag * drag) / 2)} here).`;

  const wipeouts = section.warnings.filter((x) => x.code === "residual_wipeout");

  return (
    <div className="res-chart">
      <div className="res-chart-head">
        <h3 id="residual-chart-h">Cumulative residual return</h3>
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
      {!pitOk ? (
        <Unavailable
          reason={chart.point_in_time_reason ?? pit.reason}
          action="Only the in-sample line is shown. Choose a shorter beta window or a longer period."
        />
      ) : null}
      <LinePlot
        dates={chart.dates}
        from={shown === "both" ? anchor : 0}
        lines={lines}
        shadeTo={shown === "full" && pitOk ? anchor : undefined}
        tail={chart.n_uncovered}
        testId="residual-chart"
      />
      <ul className="legend res-legend" aria-label="Legend">
        {shown === "both" ? (
          <>
            <li>
              <svg className="sw" aria-hidden="true">
                <line className="res-key ins" x1="0" x2="16" y1="5" y2="5" />
              </svg>
              In-sample (static betas): {sp(gap.in_sample_same_days_annual)} a year on these days (full-period alpha{" "}
              {sp(ins.residual_return_annual)}, t = {n2(ins.z)})
            </li>
            <li>
              <svg className="sw" aria-hidden="true">
                <line className="res-key pit" x1="0" x2="16" y1="5" y2="5" />
              </svg>
              Point-in-time: {sp(pit.residual_return_annual)} a year, t = {n2(pit.z)}
            </li>
          </>
        ) : (
          <li>
            <svg className="sw" aria-hidden="true">
              <line className="res-key full" x1="0" x2="16" y1="5" y2="5" />
            </svg>
            In-sample, full period: alpha {sp(ins.residual_return_annual)} a year, t = {n2(ins.z)}
          </li>
        )}
      </ul>
      <Scroll label="Cumulative residual return by line">
        <table className="res-mini">
          <caption className="vh">Lowest, highest and final value of each cumulative residual line</caption>
          <thead>
            <tr>
              <th scope="col">
                <span className="vh">Line</span>
              </th>
              <th scope="col" className="num">
                Lowest
              </th>
              <th scope="col" className="num">
                Highest
              </th>
              <th scope="col" className="num">
                End
              </th>
            </tr>
          </thead>
          <tbody>
            {tableRows.map((r) => {
              const st = lineStats(r.values);
              return (
                <tr key={r.id}>
                  <th scope="row">
                    {r.label}
                    <span className="sub">from {dateLong(r.from)}</span>
                  </th>
                  <td className="num">{st ? sp(st.lo) : NA}</td>
                  <td className="num">{st ? sp(st.hi) : NA}</td>
                  <td className="num strong">{st ? sp(st.end) : NA}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </Scroll>
      <p className="res-cap">{chart.caption}</p>
      {dragText ? <p className="res-cap">{dragText}</p> : null}
      {shown === "full" && pitOk ? (
        <p className="res-cap">Warm-up: the first {w} trading days are used to estimate the first point-in-time betas.</p>
      ) : null}
      {chart.n_uncovered > 0 ? (
        <p className="res-cap">
          No factor data after {dateLong(lastCovered)}: the residual is unknown for the last {count(chart.n_uncovered)}{" "}
          trading days.
        </p>
      ) : null}
      <p className="res-cap">{labelTexts(report, chart.labels).join(" ")}</p>
    </div>
  );
}

// ---------------------------------------------------------------------------- stability

function RollingBlock({ report, section }: { report: FactorReport; section: ResidualAnalysis }) {
  const ra = section.rolling_alpha;
  const from = ra.status === "ok" ? firstFiniteIndex(ra.alpha_annual) : -1;
  if (ra.status !== "ok" || from < 0 || ra.dates.length - from < 2) {
    return (
      <div className="res-sub">
        <h3>Rolling one-year alpha</h3>
        <Unavailable reason={ra.reason} />
      </div>
    );
  }
  const alpha = ra.alpha_annual.filter((x): x is number => typeof x === "number");
  const lo = ra.ci_low_annual.filter((x): x is number => typeof x === "number");
  const hi = ra.ci_high_annual.filter((x): x is number => typeof x === "number");
  const share = finite(ra.share_excluding_zero);
  return (
    <div className="res-sub">
      <h3>Rolling one-year alpha</h3>
      <LinePlot
        dates={ra.dates}
        from={from}
        lines={[{ id: "rolling_alpha", className: "roll", values: ra.alpha_annual }]}
        band={{ low: ra.ci_low_annual, high: ra.ci_high_annual }}
        testId="residual-rolling-chart"
      />
      <dl className="res-facts" aria-label="Rolling one-year alpha, summary">
        <div>
          <dt>Latest</dt>
          <dd>
            {sp(alpha[alpha.length - 1])}{" "}
            <span className="ci">
              ({interval(lo[lo.length - 1], hi[hi.length - 1], up)}, {dateLong(ra.dates[ra.dates.length - 1] as string)})
            </span>
          </dd>
        </div>
        <div>
          <dt>Lowest</dt>
          <dd>{sp(Math.min(...alpha))}</dd>
        </div>
        <div>
          <dt>Highest</dt>
          <dd>{sp(Math.max(...alpha))}</dd>
        </div>
        <div>
          <dt>Points whose 95% band excludes zero</dt>
          <dd>{share === null ? NA : up(share)}</dd>
        </div>
      </dl>
      <p className="res-cap">
        {ra.caption} {labelTexts(report, ra.labels).join(" ")}
      </p>
    </div>
  );
}

function WindowsBlock({ section }: { section: ResidualAnalysis }) {
  const no = section.non_overlapping;
  if (no.status !== "ok") {
    return (
      <div className="res-sub">
        <h3>Separate one-year windows</h3>
        <Unavailable reason={no.reason} />
      </div>
    );
  }
  return (
    <div className="res-sub">
      <h3 id="residual-windows-h">Separate one-year windows</h3>
      <p className="res-sentence">
        {no.n_reliable} of {no.family_size} separate one-year windows show an alpha different from zero, after
        correcting for testing {no.family_size} windows.
      </p>
      <Scroll label="Separate one-year windows">
        <table className="res-mini wide" aria-labelledby="residual-windows-h">
          <thead>
            <tr>
              <th scope="col">Window</th>
              <th scope="col" className="num">
                Alpha, a year
              </th>
              <th scope="col" className="num">
                Standard error
              </th>
              <th scope="col" className="num">
                z
              </th>
              <th scope="col" className="num">
                p
              </th>
              <th scope="col" className="num">
                Adjusted p
              </th>
              <th scope="col">Reading</th>
            </tr>
          </thead>
          <tbody>
            {no.windows.map((win) => (
              <tr key={win.start}>
                <th scope="row">
                  {dateLong(win.start)} to {dateLong(win.end)}
                  <span className="sub">{days(win.n)}</span>
                </th>
                <td className="num strong">{sp(win.alpha_annual)}</td>
                <td className="num">{up(win.se_annual)}</td>
                <td className="num">{n2(win.z)}</td>
                <td className="num">{pv(win.p)}</td>
                <td className="num">{pv(win.p_adj_bh)}</td>
                <td>
                  <Tag tag={win.tag} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Scroll>
      <p className="res-cap">{no.caption}</p>
    </div>
  );
}

function SplitBlock({ section }: { section: ResidualAnalysis }) {
  const sh = section.split_half;
  if (sh.status !== "ok") {
    return (
      <div className="res-sub">
        <h3>First half against second half</h3>
        <Unavailable reason={sh.reason} />
      </div>
    );
  }
  return (
    <div className="res-sub">
      <h3 id="residual-split-h">First half against second half</h3>
      <Scroll label="First half against second half">
        <table className="res-mini" aria-labelledby="residual-split-h">
          <thead>
            <tr>
              <th scope="col">Half</th>
              <th scope="col" className="num">
                Alpha, a year
              </th>
              <th scope="col" className="num">
                95% interval
              </th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <th scope="row">
                First half
                <span className="sub">{span(sh.first_start, sh.first_end, sh.n_first)}</span>
              </th>
              <td className="num strong">{sp(sh.alpha_first_annual)}</td>
              <td className="num">{interval(sh.alpha_first_ci_low_annual, sh.alpha_first_ci_high_annual, up)}</td>
            </tr>
            <tr>
              <th scope="row">
                Second half
                <span className="sub">{span(sh.second_start, sh.second_end, sh.n_second)}</span>
              </th>
              <td className="num strong">{sp(sh.alpha_second_annual)}</td>
              <td className="num">{interval(sh.alpha_second_ci_low_annual, sh.alpha_second_ci_high_annual, up)}</td>
            </tr>
            <tr>
              <th scope="row">Second minus first</th>
              <td className="num strong">{sp(sh.difference_annual)}</td>
              <td className="num">
                z {n2(sh.difference_z)}, p {pv(sh.difference_p)}
              </td>
            </tr>
          </tbody>
        </table>
      </Scroll>
      <p className="res-sentence">
        Second-half alpha minus first-half alpha: {sp(sh.difference_annual)} a year (p = {pv(sh.difference_p)}).
      </p>
      <p className="res-cap">{sh.caption}</p>
    </div>
  );
}

function YearsBlock({ section }: { section: ResidualAnalysis }) {
  const cy = section.calendar_years;
  if (cy.status !== "ok" || cy.years.length === 0) {
    return (
      <div className="res-sub">
        <h3>Calendar years</h3>
        <Unavailable reason={cy.reason} />
      </div>
    );
  }
  return (
    <div className="res-sub">
      <h3 id="residual-years-h">Calendar years</h3>
      <Scroll label="Calendar years">
        <table className="res-mini" aria-labelledby="residual-years-h">
          <thead>
            <tr>
              <th scope="col">Year</th>
              <th scope="col" className="num">
                In-sample sum
              </th>
              <th scope="col" className="num">
                Noise sd
              </th>
              <th scope="col" className="num">
                Point-in-time sum
              </th>
              <th scope="col" className="num">
                Noise sd
              </th>
            </tr>
          </thead>
          <tbody>
            {cy.years.map((y) => (
              <tr key={y.year}>
                <th scope="row">
                  {y.year}
                  <span className="sub">
                    {days(y.n)}
                    {y.partial ? ", partial year" : ""}
                  </span>
                </th>
                <td className="num strong">{sdec4(y.in_sample_sum)}</td>
                <td className="num">{dec4(y.in_sample_noise_sd)}</td>
                <td className="num strong">
                  {y.point_in_time_sum == null ? "none" : sdec4(y.point_in_time_sum)}
                  {y.point_in_time_sum != null ? (
                    <span className="sub">
                      {days(y.n_point_in_time)}
                      {y.point_in_time_partial ? ", partial" : ""}
                    </span>
                  ) : null}
                </td>
                <td className="num">{y.point_in_time_noise_sd == null ? NA : dec4(y.point_in_time_noise_sd)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Scroll>
      <p className="res-sentence">{YEAR_RULE}</p>
      <p className="res-cap">{cy.caption}</p>
    </div>
  );
}

const CHECK_NAMES = ["Ljung-Box", "Jarque-Bera", "ARCH"] as const;

function checkP(d: Diagnostics): (number | null)[] {
  return [d.ljung_box_p, d.jarque_bera_p, d.arch_lm_p];
}

function ChecksBlock({ section }: { section: ResidualAnalysis }) {
  return (
    <div className="res-sub">
      <h3>Checks on the residuals</h3>
      <div className="res-checks">
        {section.diagnostics.map((d) => (
          <div key={d.basis}>
            <h4>{d.basis === "in_sample" ? "In-sample" : "Point-in-time"}</h4>
            {d.status !== "ok" ? (
              <Unavailable reason={d.reason} />
            ) : (
              <ul className="notes">
                {d.findings.map((f, i) => {
                  const p = d.findings.length === CHECK_NAMES.length ? checkP(d)[i] : null;
                  return (
                    <li key={f}>
                      {f}
                      {p != null ? (
                        <span className="ci">
                          {" "}
                          ({CHECK_NAMES[i]}, p = {pval(p)})
                        </span>
                      ) : null}
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
        ))}
      </div>
      <p className="res-cap">{section.diagnostics.find((d) => d.status === "ok")?.caption ?? ""}</p>
      <p className="res-cap">{CHECKS_NOTE}</p>
    </div>
  );
}

function Stability({ report, section }: { report: FactorReport; section: ResidualAnalysis }) {
  return (
    <details className="res-stab" open>
      <summary>How stable is it? Rolling alpha, separate years, halves and checks</summary>
      <RollingBlock report={report} section={section} />
      <WindowsBlock section={section} />
      <SplitBlock section={section} />
      <YearsBlock section={section} />
      <ChecksBlock section={section} />
      <p className="res-caution">{MINING_CAUTION}</p>
    </details>
  );
}

// ---------------------------------------------------------------------------- panel

const FAILED_ACTION = "Widen the date range or choose another ticker.";

/** Method detail folded into "How this is computed" (the rules, then the label texts of the section). */
function howText(report: FactorReport, section: ResidualAnalysis): string {
  const keys = ["L-INSAMPLE", "L-PIT", "L-DESC-PIT", "L-HEDGE"];
  const texts = report.label_text ?? {};
  const labels = keys.filter((k) => k in texts).map((k) => texts[k] as string);
  return [
    "Residual return is the daily excess return minus what the five factor exposures explain; it keeps alpha.",
    "Residual return a year, its interval and the t-statistic use the average daily residual times the trading days in a year, with standard errors that allow for day-to-day correlation.",
    "Cumulative and compound growth compound the daily residuals and are never added to the arithmetic values.",
    "Residual Sharpe is the residual return divided by the residual volatility; its interval is approximate.",
    `Point-in-time uses, on each day, betas from the previous ${section.beta_window} trading days only.`,
    ...labels,
  ].join(" ");
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
        empty={{
          reason: section.reason ?? "Residual analysis is not available for this report.",
          action: FAILED_ACTION,
        }}
      />
    );
  }
  const skipped = section.chart.n_excluded_in_span;
  const footnote = skipped > 0 ? `Skips ${count(skipped)} excluded days (listed under sample details).` : undefined;
  const others = section.warnings.filter((x) => x.code !== "residual_wipeout");
  return (
    <Panel id="residual" title={TITLE} question={question} footnote={footnote} how={howText(report, section)}>
      <StatsTable section={section} />
      <GapBlock gap={section.gap} inSample={section.in_sample} pit={section.point_in_time} />
      <ChartBlock report={report} section={section} />
      <Stability report={report} section={section} />
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
