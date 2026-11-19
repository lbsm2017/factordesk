import type { AlphaStrip, AlphaStripRow } from "../../../api/types";
import { count, MINUS, num, pct, tstat } from "../../../format";
import { observations } from "../../../report/subject";
import { position } from "../../charts/BarCell";
import { niceDomain } from "../exposureModel";
import type { NiceDomain } from "../exposureModel";
import { Panel } from "../Panel";
import type { ReportPanelProps } from "../types";
import "./AlphaStripPanel.css";

export const TITLE = "Alpha across models";
export const QUESTION = "How does alpha change when the model has more factors?";
/** One line above the table; the server's longer intro moves into "How this is computed". */
export const INTRO = "Alpha of four models fitted on the same rows. Listed by number of factors, not ranked.";
/** Two-sided 95% normal quantile, for the approximate range drawn from the t-statistic. */
const Z95 = 1.96;

/** The count of sample rows the strip left out, in words. */
export function droppedText(n: number): string {
  if (n === 0) return "No rows of the sample were left out.";
  return `${count(n)} ${n === 1 ? "row" : "rows"} of the sample left out: a factor of one of the models has no value there, so every model uses the same rows.`;
}

function finite(x: number | null | undefined): x is number {
  return typeof x === "number" && Number.isFinite(x);
}

/** Approximate 95% range of the annual alpha, alpha ± 1.96 · |alpha / t| (the standard error is recovered from the t-statistic). Null without a usable t. */
export function alphaRange(row: AlphaStripRow): { low: number; high: number } | null {
  if (!finite(row.alpha_annual) || !finite(row.alpha_t) || row.alpha_t === 0) return null;
  const half = Z95 * Math.abs(row.alpha_annual / row.alpha_t);
  return { low: row.alpha_annual - half, high: row.alpha_annual + half };
}

function domainOf(rows: readonly AlphaStripRow[]): NiceDomain {
  const values = [0];
  for (const row of rows) {
    if (finite(row.alpha_annual)) values.push(row.alpha_annual);
    const range = alphaRange(row);
    if (range) values.push(range.low, range.high);
  }
  return niceDomain(Math.min(...values), Math.max(...values), 3);
}

function tickText(t: number): string {
  if (Math.abs(t) < 1e-12) return "0";
  const points = Math.abs(t) * 100;
  return `${t < 0 ? MINUS : ""}${num(points, Number.isInteger(Number(points.toFixed(6))) ? 0 : 1)}%`;
}

function textOf(row: AlphaStripRow): string {
  if (!finite(row.alpha_annual)) return `${row.label}: alpha n/a`;
  const range = alphaRange(row);
  const tail = range ? `, approximate 95% range ${pct(range.low, 2)} to ${pct(range.high, 2)}` : "";
  return `${row.label}: alpha ${pct(row.alpha_annual, 2)} a year${tail}`;
}

function how(s: AlphaStrip, rows: string): string {
  const reference =
    s.t_reference === "student_t"
      ? "p-values use Student-t with n − k degrees of freedom, k the parameters of each model"
      : "p-values use the normal reference";
  const r2 = s.rows.map((r) => `${r.label} ${finite(r.r2) ? num(r.r2, 3) : "n/a"}`).join(", ");
  return [
    s.intro,
    `Every model is fitted by OLS on the same ${rows}, with Newey-West HAC standard errors (${s.hac_lags} lags); ${reference}.`,
    "Alpha is the intercept times the observations a year. R² is the share of the variance of the excess return that co-moved with the model's factors; adjusted R² charges for the number of factors, so the table shows adjusted R² only.",
    `R² of each model: ${r2}.`,
    "The dot is the alpha of the row and the line is an approximate 95% range, alpha ± 1.96 · |alpha / t|, which assumes a normal reference. All rows share one scale, with a line at zero.",
    "CAPM uses the market factor only; FF3 adds size and value; FF5 adds profitability and investment; FF6 adds momentum.",
    s.model_note,
    droppedText(s.n_dropped),
  ].join(" ");
}

function AlphaPlot({ row, domain }: { row: AlphaStripRow; domain: NiceDomain }) {
  const { lo, hi, ticks } = domain;
  const range = alphaRange(row);
  const a = range ? position(range.low, lo, hi) : 0;
  const b = range ? position(range.high, lo, hi) : 0;
  return (
    <svg className="bar-svg" aria-hidden="true">
      <title>{textOf(row)}</title>
      {ticks.map((t) => {
        const x = `${position(t, lo, hi)}%`;
        return <line key={t} className={Math.abs(t) < 1e-12 ? "zero" : "grid"} x1={x} x2={x} y1="0" y2="100%" />;
      })}
      {range ? (
        <>
          <line className="ci" x1={`${a}%`} x2={`${b}%`} y1="50%" y2="50%" />
          {b - a >= 1.2 ? (
            <>
              <line className="ci" x1={`${a}%`} x2={`${a}%`} y1="40%" y2="60%" />
              <line className="ci" x1={`${b}%`} x2={`${b}%`} y1="40%" y2="60%" />
            </>
          ) : null}
        </>
      ) : null}
      {finite(row.alpha_annual) ? <circle className="as-dot" cx={`${position(row.alpha_annual, lo, hi)}%`} cy="50%" r="4" /> : null}
    </svg>
  );
}

function Row({ row, domain }: { row: AlphaStripRow; domain: NiceDomain }) {
  return (
    <tr>
      <th scope="row" title={row.factors.join(", ")}>
        {row.label}
      </th>
      <td className="num">{finite(row.alpha_annual) ? pct(row.alpha_annual, 2) : "n/a"}</td>
      <td className="as-plot">
        <AlphaPlot row={row} domain={domain} />
        <span className="vh">{textOf(row)}</span>
      </td>
      <td className="num">{finite(row.alpha_t) ? tstat(row.alpha_t) : "n/a"}</td>
      <td className="num">{finite(row.adj_r2) ? num(row.adj_r2, 3) : "n/a"}</td>
    </tr>
  );
}

/**
 * Panel of the `alpha_strip` section (E1, E9a): alpha, its t-statistic and adjusted R² under
 * CAPM, FF3, FF5 and FF6 on the same rows, with a dot and an approximate 95% range per row on one
 * scale. The rows keep the server's fixed order and all look the same: no row is ranked, coloured
 * or highlighted. Plain R², the model note and the dropped-row count are in "How this is computed".
 * Registered in `panelRegistry.ts` at position 502, right after Factor exposures, and shares a row
 * with World beta (`Panel.tsx`). Renders nothing when the section is absent.
 */
export function AlphaStripPanel({ report }: ReportPanelProps) {
  const s = report.alpha_strip;
  if (s == null) return null;
  if (s.status !== "ok") {
    return (
      <Panel
        id="alpha-strip"
        title={TITLE}
        question={QUESTION}
        empty={{
          reason: s.reason ?? "The alpha strip could not be computed for this range.",
          action: "The rest of the report is not affected.",
        }}
      />
    );
  }
  const rows = observations(report, s.n_obs);
  const domain = domainOf(s.rows);
  return (
    <Panel id="alpha-strip" title={TITLE} question={QUESTION} reading={INTRO} footnote={s.caption} how={how(s, rows)}>
      <div className="as-wrap">
        <table className="as-table">
          <caption className="vh">
            Alpha a year with an approximate 95% range, its t-statistic and adjusted R² of each model, on the same {rows}
          </caption>
          <thead>
            <tr>
              <th scope="col">Model</th>
              <th scope="col" className="num">
                Alpha a year
              </th>
              <th scope="col" className="as-plot-h">
                <span className="vh">Chart: alpha and approximate 95% range</span>
              </th>
              <th scope="col" className="num">
                t
              </th>
              <th scope="col" className="num">
                Adjusted R²
              </th>
            </tr>
          </thead>
          <tbody>
            {s.rows.map((row) => (
              <Row key={row.model} row={row} domain={domain} />
            ))}
          </tbody>
          <tfoot aria-hidden="true">
            <tr>
              <td />
              <td />
              <td className="as-axis">
                <div className="axis">
                  {domain.ticks.map((t) => (
                    <span key={t} style={{ left: `${position(t, domain.lo, domain.hi)}%` }}>
                      {tickText(t)}
                    </span>
                  ))}
                </div>
              </td>
              <td />
              <td />
            </tr>
          </tfoot>
        </table>
      </div>
    </Panel>
  );
}
