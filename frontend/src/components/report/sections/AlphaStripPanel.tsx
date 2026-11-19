import type { AlphaStrip, AlphaStripRow } from "../../../api/types";
import { count, num, pct, tstat } from "../../../format";
import { observations } from "../../../report/subject";
import { Panel } from "../Panel";
import type { ReportPanelProps } from "../types";
import "./AlphaStripPanel.css";

export const TITLE = "Alpha across models";
export const QUESTION = "How does alpha change when the model has more factors?";

/** The count of sample rows the strip left out, in words. */
export function droppedText(n: number): string {
  if (n === 0) return "No rows of the sample were left out.";
  return `${count(n)} ${n === 1 ? "row" : "rows"} of the sample left out: a factor of one of the models has no value there, so every model uses the same rows.`;
}

function finite(x: number | null | undefined): x is number {
  return typeof x === "number" && Number.isFinite(x);
}

function how(s: AlphaStrip, rows: string): string {
  const reference =
    s.t_reference === "student_t"
      ? "p-values use Student-t with n − k degrees of freedom, k the parameters of each model"
      : "p-values use the normal reference";
  return [
    `Every model is fitted by OLS on the same ${rows}, with Newey-West HAC standard errors (${s.hac_lags} lags); ${reference}.`,
    "Alpha is the intercept times the observations a year. R² is the share of the variance of the excess return that co-moved with the model's factors; adjusted R² charges for the number of factors.",
    "CAPM uses the market factor only; FF3 adds size and value; FF5 adds profitability and investment; FF6 adds momentum.",
  ].join(" ");
}

function Row({ row }: { row: AlphaStripRow }) {
  return (
    <tr>
      <th scope="row" title={row.factors.join(", ")}>
        {row.label}
      </th>
      <td className="num">{finite(row.alpha_annual) ? pct(row.alpha_annual, 2) : "n/a"}</td>
      <td className="num">{finite(row.alpha_t) ? tstat(row.alpha_t) : "n/a"}</td>
      <td className="num">{finite(row.r2) ? num(row.r2, 3) : "n/a"}</td>
      <td className="num">{finite(row.adj_r2) ? num(row.adj_r2, 3) : "n/a"}</td>
    </tr>
  );
}

/**
 * Panel of the `alpha_strip` section (E1, E9a): alpha, its t-statistic, R² and adjusted R² under
 * CAPM, FF3, FF5 and FF6 on the same rows. The rows keep the server's fixed order and all look the
 * same: no row is ranked, coloured or highlighted. Registered in `panelRegistry.ts` at position 502,
 * right after Factor exposures. Renders nothing when the section is absent.
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
  return (
    <Panel id="alpha-strip" title={TITLE} question={QUESTION} reading={s.intro} footnote={s.caption} how={how(s, rows)}>
      <div className="as-wrap">
        <table className="as-table">
          <caption className="vh">Alpha a year, its t-statistic, R² and adjusted R² of each model, on the same {rows}</caption>
          <thead>
            <tr>
              <th scope="col">Model</th>
              <th scope="col" className="num">
                Alpha a year
              </th>
              <th scope="col" className="num">
                t
              </th>
              <th scope="col" className="num">
                R²
              </th>
              <th scope="col" className="num">
                Adjusted R²
              </th>
            </tr>
          </thead>
          <tbody>
            {s.rows.map((row) => (
              <Row key={row.model} row={row} />
            ))}
          </tbody>
        </table>
      </div>
      <p className="as-note">{s.model_note}</p>
      <p className="as-note">{droppedText(s.n_dropped)}</p>
    </Panel>
  );
}
