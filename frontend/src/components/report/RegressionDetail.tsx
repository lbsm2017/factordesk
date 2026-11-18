import type { ReactNode } from "react";
import type { FactorReport, FactorStat, MultiDayRegression, ResidualDiagnostics } from "../../api/types";
import { num, pct, pval, signed, tstat } from "../../format";
import { EmptyState } from "./EmptyState";
import { Panel } from "./Panel";
import type { ReportPanelProps } from "./types";

const NA = "n/a";

/** Format a nullable number; a missing or non-finite value reads "n/a" (as the static report does). */
function or(x: number | null | undefined, f: (v: number) => string): string {
  return x === null || x === undefined || !Number.isFinite(x) ? NA : f(x);
}

const sgn = (x: number | null | undefined, digits = 3) => or(x, (v) => signed(v, digits));
const plain = (x: number | null | undefined, digits = 3) => or(x, (v) => num(v, digits));
const pctText = (x: number | null | undefined, digits = 2, withSign = true) =>
  or(x, (v) => pct(v, digits, withSign));
const pText = (x: number | null | undefined) => or(x, pval);
const tText = (x: number | null | undefined) => or(x, tstat);

interface TableProps {
  /** Accessible name of the scroll region; ", scrolls sideways" is appended. */
  label: string;
  heads: readonly string[];
  /** Index of the left-aligned reading column, if any. */
  readingCol?: number;
  children: ReactNode;
}

/** A table inside a focusable, labelled scroll region: the only thing that scrolls sideways. */
function RegTable({ label, heads, readingCol, children }: TableProps) {
  return (
    // A keyboard user has to be able to scroll the table, so the region takes focus.
    // eslint-disable-next-line jsx-a11y/no-noninteractive-tabindex
    <div className="scroll-x" tabIndex={0} role="region" aria-label={`${label}, scrolls sideways`}>
      <table className="reg">
        <thead>
          <tr>
            {heads.map((h, i) => (
              <th key={h} scope="col" className={i === 0 ? undefined : i === readingCol ? "rd" : "num"}>
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>{children}</tbody>
      </table>
    </div>
  );
}

interface TermFit {
  alpha_annual: number | null;
  alpha_se_annual: number | null;
  alpha_z: number | null;
  alpha_p: number | null;
  alpha_ci_low_annual: number | null;
  alpha_ci_high_annual: number | null;
  alpha_tag: "reliable" | "noise" | null;
  factors: readonly FactorStat[];
}

/** Alpha row, then one row per factor. `vif` is null for the 5-day table, which has no VIF column. */
function TermRows({ fit, vif }: { fit: TermFit; vif: Record<string, number | null> | null }) {
  const alphaNs = fit.alpha_tag !== "reliable";
  return (
    <>
      <tr className={alphaNs ? "ns" : ""}>
        <th scope="row">Alpha, a year</th>
        <td className="num">{pctText(fit.alpha_annual)}</td>
        <td className="num">{pctText(fit.alpha_se_annual, 2, false)}</td>
        <td className="num">{tText(fit.alpha_z)}</td>
        <td className="num">{pText(fit.alpha_p)}</td>
        <td className="num">single test</td>
        <td className="num">
          {pctText(fit.alpha_ci_low_annual)} to {pctText(fit.alpha_ci_high_annual)}
        </td>
        {vif !== null ? <td className="num">{"–"}</td> : null}
        <td className="num sig">{alphaNs ? "No" : "Yes"}</td>
      </tr>
      {fit.factors.map((s) => {
        const ns = s.tag !== "reliable";
        return (
          <tr key={s.name} className={ns ? "ns" : ""}>
            <th scope="row">{s.name}</th>
            <td className="num">{sgn(s.beta)}</td>
            <td className="num">{plain(s.se, 4)}</td>
            <td className="num">{tText(s.z)}</td>
            <td className="num">{pText(s.p)}</td>
            <td className="num">{pText(s.p_adj_bh)}</td>
            <td className="num">
              {sgn(s.ci_low)} to {sgn(s.ci_high)}
            </td>
            {vif !== null ? <td className="num">{plain(vif[s.name], 2)}</td> : null}
            <td className="num sig">{ns ? "No" : "Yes"}</td>
          </tr>
        );
      })}
    </>
  );
}

const MAIN_HEADS = ["Term", "Estimate", "Std. error", "t", "p", "p, adjusted", "95% interval", "VIF", "Significant"];
const FIVE_HEADS = ["Term", "Estimate", "Std. error", "t", "p", "p, adjusted", "95% interval", "Significant"];

/** The 5-day estimate (M3.6): present only when the quality gate fired. */
function FiveDayTable({ five }: { five: MultiDayRegression }) {
  if (five.status !== "ok") return null;
  const caption =
    `${five.caption} R² ${plain(five.r2, 4)}, residual volatility ` +
    `${pctText(five.sigma_e_annual, 2, false)} a year, Newey-West lags ${five.hac_lags}.`;
  return (
    <>
      <h3 className="reg-title">5-day estimate ({five.n_blocks.toLocaleString("en-US")} blocks)</h3>
      <RegTable label="5-day estimate table" heads={FIVE_HEADS}>
        <TermRows fit={five} vif={null} />
      </RegTable>
      <p className="foot">{caption}</p>
    </>
  );
}

/** Residual diagnostics (M3.5) with their plain-language readings. */
function DiagnosticsTable({ rd }: { rd: ResidualDiagnostics }) {
  if (rd.status !== "ok") {
    return (
      <>
        <h3 className="reg-title">Residual diagnostics</h3>
        <EmptyState
          reason={rd.reason ?? "Residual diagnostics are not available."}
          action="Choose a longer date range to run them."
        />
      </>
    );
  }
  return (
    <>
      <h3 className="reg-title">Residual diagnostics</h3>
      <RegTable
        label="Residual diagnostics table"
        heads={["Test", "Statistic", "Reference", "p", "Reading"]}
        readingCol={4}
      >
        <tr>
          <th scope="row">Lag-1 autocorrelation</th>
          <td className="num">{sgn(rd.lag1_autocorrelation)}</td>
          <td className="num">z {tText(rd.lag1_z)}</td>
          <td className="num">{pText(rd.lag1_p)}</td>
          <td className="rd">{rd.lag1_reading ?? ""}</td>
        </tr>
        {rd.tests.map((t) => (
          <tr key={t.code}>
            <th scope="row">{t.name}</th>
            <td className="num">{plain(t.statistic, 2)}</td>
            <td className="num">{t.df === null ? "" : `df ${t.df}`}</td>
            <td className="num">{pText(t.p)}</td>
            <td className="rd">{t.reading}</td>
          </tr>
        ))}
      </RegTable>
      <p className="foot">
        {rd.note} {rd.caption}
      </p>
    </>
  );
}

function labelTexts(report: FactorReport, keys: readonly string[]): string[] {
  const texts = report.label_text;
  return keys.filter((k) => k !== "L-DESC" && k in texts).map((k) => texts[k] ?? "");
}

/** Regression detail table, its readings, the 5-day estimate and the residual diagnostics. */
export function RegressionDetail({ report }: ReportPanelProps) {
  const rg = report.regression;
  const title = "Regression detail";
  const question = "OLS with an intercept and Newey-West standard errors.";
  if (rg.status !== "ok") {
    return (
      <Panel
        id="regression-detail"
        title={title}
        question={question}
        empty={{
          reason: rg.reason ?? "The regression is not available.",
          action: "Choose a longer date range, or try another ticker.",
        }}
      />
    );
  }
  const reads = rg.factors.flatMap((s) => (s.interpretation ? [s.interpretation] : []));
  const pairs = rg.high_corr_pairs.map((p) => `${p.a}/${p.b} ${sgn(p.corr, 2)}`).join(", ");
  const footnote =
    `R² ${plain(rg.r2, 4)}, adjusted ${plain(rg.adj_r2, 4)}. Residual volatility ` +
    `${pctText(rg.sigma_e_annual, 2, false)} a year. Newey-West lags ${rg.hac_lags}.`;
  const how = [
    rg.caption,
    `Condition number of the factor correlation matrix ${plain(rg.condition_number, 2)}` +
      (pairs ? `; pairs with |correlation| above 0.6: ${pairs}.` : "."),
    ...labelTexts(report, rg.labels),
  ]
    .filter(Boolean)
    .join(" ");
  return (
    <Panel id="regression-detail" title={title} question={question} footnote={footnote} how={how}>
      <RegTable label="Regression detail table" heads={MAIN_HEADS}>
        <TermRows fit={rg} vif={rg.vif} />
      </RegTable>
      {rg.alpha_sentence ? <p className="reading">{rg.alpha_sentence}</p> : null}
      {reads.length ? (
        <>
          <h3 className="reg-title">Reading the significant betas</h3>
          <ul className="notes">
            {reads.map((t) => (
              <li key={t}>{t}</li>
            ))}
          </ul>
        </>
      ) : null}
      <FiveDayTable five={report.five_day_regression} />
      <DiagnosticsTable rd={report.residual_diagnostics} />
    </Panel>
  );
}
