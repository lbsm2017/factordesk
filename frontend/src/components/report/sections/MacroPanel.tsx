import type { MacroRow, MacroSection } from "../../../api/types";
import { count, dateLong, dateShort, num, pval, signed, tstat } from "../../../format";
import { observations } from "../../../report/subject";
import { position } from "../../charts/BarCell";
import { niceDomain } from "../exposureModel";
import type { NiceDomain } from "../exposureModel";
import { Panel } from "../Panel";
import type { ReportPanelProps } from "../types";
import "./MacroPanel.css";

export const TITLE = "Macro sensitivities";
export const QUESTION = "How has the return moved with rates, credit, commodities, inflation and the dollar?";
/** One line above the table; the method detail is in "How this is computed". */
export const INTRO = "A separate regression on six macro factors. Betas are raw: the factors overlap.";
/** Two-sided 95% normal quantile, for the whisker beta ± 1.96 · SE. */
const Z95 = 1.96;
/** A variance inflation factor above this gets a badge (the same bar as the warning of the main regression). */
export const VIF_WARN = 5;

function finite(x: number | null | undefined): x is number {
  return typeof x === "number" && Number.isFinite(x);
}

/** The whisker of a row: beta ± 1.96 · SE. Null without a usable standard error. */
export function whisker(row: Pick<MacroRow, "beta" | "se">): { low: number; high: number } | null {
  if (!finite(row.beta) || !finite(row.se)) return null;
  return { low: row.beta - Z95 * row.se, high: row.beta + Z95 * row.se };
}

/** True when the row's variance inflation factor is above the warning bar. */
export function overlaps(row: Pick<MacroRow, "vif">): boolean {
  return finite(row.vif) && row.vif > VIF_WARN;
}

function domainOf(rows: readonly MacroRow[]): NiceDomain {
  const values = [0];
  for (const row of rows) {
    if (finite(row.beta)) values.push(row.beta);
    const w = whisker(row);
    if (w) values.push(w.low, w.high);
  }
  return niceDomain(Math.min(...values), Math.max(...values), 3);
}

function tickText(t: number): string {
  if (Math.abs(t) < 1e-12) return "0";
  return num(t, Math.abs(t) >= 1 && Number.isInteger(t) ? 0 : 1);
}

function textOf(row: MacroRow): string {
  const w = whisker(row);
  const tail = w ? `, approximate 95% range ${signed(w.low, 2)} to ${signed(w.high, 2)}` : "";
  const vif = overlaps(row) ? `, overlaps strongly with the other factors (VIF ${num(row.vif, 1)})` : "";
  return `${row.label}: beta ${signed(row.beta, 2)}${tail}${vif}`;
}

function pair(codes: readonly string[], labels: Map<string, string>, matrix: readonly (readonly number[])[]): string {
  const out: string[] = [];
  for (let i = 0; i < codes.length; i++) {
    for (let j = i + 1; j < codes.length; j++) {
      const r = matrix[i]?.[j];
      if (finite(r)) out.push(`${labels.get(codes[i] ?? "")} and ${labels.get(codes[j] ?? "")} ${signed(r, 2)}`);
    }
  }
  return out.join("; ");
}

/** The first dates of the funds behind the factors, in words. */
function legsText(s: MacroSection): string {
  return s.legs
    .map((l) => `${l.ticker} from ${l.first_date ? dateLong(l.first_date) : "an unknown date"}`)
    .join(", ");
}

function windowText(s: MacroSection): string {
  const start = s.sample.start;
  const end = s.sample.end;
  if (!start || !end) return "";
  const limit = s.window_limited_by
    ? ` The window starts at the latest first date among the funds (${s.window_limited_by}) or the start of the data, whichever is later.`
    : "";
  return `Window used: ${dateLong(start)} to ${dateLong(end)}.${limit}`;
}

function how(s: MacroSection, rows: string): string {
  const reference =
    s.t_reference === "student_t"
      ? "p-values use Student-t with n − k degrees of freedom (monthly data, small-sample correction)"
      : "p-values use the normal reference";
  const labels = new Map(s.rows.map((r) => [r.code, r.label]));
  const parts = [
    `${s.model_note}`,
    `The excess return is fitted by OLS on the same ${rows} for every factor, with Newey-West HAC standard errors (${s.hac_lags} lags); ${reference}. Adjusted R² charges for the number of factors.`,
    s.r2 != null && s.adj_r2 != null ? `R² ${num(s.r2, 3)}, adjusted R² ${num(s.adj_r2, 3)}.` : "",
    "The dot is the beta and the line is an approximate 95% range, beta ± 1.96 · SE. All rows share one scale, with a line at zero.",
    "Factors: " + s.rows.map((r) => `${r.label} = ${r.definition}${r.note ? ` (${r.note})` : ""}`).join("; ") + ".",
    s.usd_lag_note
      ? `${s.usd_lag_note} The dollar row is the sum of the same-day and previous-day betas, with the standard error of the sum from the HAC covariance.`
      : "",
    s.rows
      .filter((r) => r.beta_same_day != null && r.beta_lag != null)
      .map((r) => `${r.label}: same day ${signed(r.beta_same_day ?? 0, 3)}, previous day ${signed(r.beta_lag ?? 0, 3)}.`)
      .join(" "),
    `A VIF badge shows when the variance inflation factor is above ${VIF_WARN}: that factor overlaps strongly with the others and its beta is imprecise.`,
    "Tag of each factor (Benjamini-Hochberg across these factors): " +
      s.rows.map((r) => `${r.label} ${r.tag}, p ${pval(r.p)}, VIF ${num(r.vif, 2)}`).join("; ") +
      ".",
    `Correlations of the factors: ${pair(s.correlation_codes, labels, s.correlation)}.`,
    windowText(s),
    `Funds start: ${legsText(s)}.`,
    s.usd_note ? `Dollar: ${s.usd_note}.` : "",
    `${count(s.n_sample - s.n_obs)} of ${count(s.n_sample)} rows of the analysis sample are left out because a fund or ${s.legs.some((l) => l.ticker === "USD/EUR") ? "the exchange rate" : "the dollar index"} has no value there.`,
  ];
  return parts.filter((p) => p !== "").join(" ");
}

function MacroPlot({ row, domain }: { row: MacroRow; domain: NiceDomain }) {
  const { lo, hi, ticks } = domain;
  const w = whisker(row);
  const a = w ? position(w.low, lo, hi) : 0;
  const b = w ? position(w.high, lo, hi) : 0;
  return (
    <svg className="bar-svg" aria-hidden="true">
      <title>{textOf(row)}</title>
      {ticks.map((t) => {
        const x = `${position(t, lo, hi)}%`;
        return <line key={t} className={Math.abs(t) < 1e-12 ? "zero" : "grid"} x1={x} x2={x} y1="0" y2="100%" />;
      })}
      {w ? (
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
      {finite(row.beta) ? <circle className="mc-dot" cx={`${position(row.beta, lo, hi)}%`} cy="50%" r="4" /> : null}
    </svg>
  );
}

function Row({ row, domain }: { row: MacroRow; domain: NiceDomain }) {
  const title = `${row.definition}${row.note ? `; ${row.note}` : ""}`;
  return (
    <tr>
      <th scope="row" title={title}>
        <span className="mc-label">{row.label}</span>
        {row.note ? <span className="mc-note">{row.note}</span> : null}
      </th>
      <td className="num">{finite(row.beta) ? signed(row.beta, 2) : "n/a"}</td>
      <td className="mc-plot">
        <MacroPlot row={row} domain={domain} />
        <span className="vh">{textOf(row)}</span>
      </td>
      <td className="num">{finite(row.t) ? tstat(row.t) : "n/a"}</td>
      <td className="mc-vif-cell">
        {overlaps(row) ? (
          <span className="mc-vif" title={`Variance inflation factor ${num(row.vif, 1)}: this factor overlaps strongly with the others, so its beta is imprecise.`}>
            VIF {num(row.vif, 1)}
          </span>
        ) : null}
      </td>
    </tr>
  );
}

/**
 * Panel of the `macro` section (E4): one row per factor of the separate macro regression (Market,
 * Rates, Credit, Commodities, Inflation, US dollar) with the raw beta, a dot and an approximate
 * 95% range on one scale with a line at zero, the t-statistic, and a VIF badge when the factor
 * overlaps strongly with the others (VIF above 5). The fixed model note is the footnote; the
 * window, the definitions, R², the tags and the correlation matrix are in "How this is computed".
 * Registered in `panelRegistry.ts` at position 508, right after World beta. Renders nothing when
 * the section is absent.
 */
export function MacroPanel({ report }: ReportPanelProps) {
  const s = report.macro;
  if (s == null) return null;
  if (s.status !== "ok") {
    return (
      <Panel
        id="macro"
        title={TITLE}
        question={QUESTION}
        empty={{
          reason: s.reason ?? "The macro sensitivities could not be computed for this range.",
          action: "The rest of the report is not affected.",
        }}
      />
    );
  }
  const rows = observations(report, s.n_obs);
  const domain = domainOf(s.rows);
  const start = s.sample.start;
  const end = s.sample.end;
  return (
    <Panel
      id="macro"
      title={TITLE}
      question={QUESTION}
      aside={start && end ? `${dateShort(start)} to ${dateShort(end)}` : undefined}
      reading={s.usd_included ? INTRO : `${INTRO} ${s.usd_note ?? "dollar index unavailable"}.`}
      footnote={s.model_note}
      how={how(s, rows)}
    >
      <div className="mc-wrap">
        <table className="mc-table">
          <caption className="vh">Beta of each macro factor with an approximate 95% range and its t-statistic, on {rows}</caption>
          <thead>
            <tr>
              <th scope="col">Factor</th>
              <th scope="col" className="num">
                Beta
              </th>
              <th scope="col" className="mc-plot-h">
                <span className="vh">Chart: beta and approximate 95% range</span>
              </th>
              <th scope="col" className="num">
                t
              </th>
              <th scope="col" className="mc-vif-h">
                <span className="vh">Overlap with the other factors</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {s.rows.map((row) => (
              <Row key={row.code} row={row} domain={domain} />
            ))}
          </tbody>
          <tfoot aria-hidden="true">
            <tr>
              <td />
              <td />
              <td className="mc-axis">
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
