/* eslint-disable jsx-a11y/no-redundant-roles, jsx-a11y/no-interactive-element-to-noninteractive-role --
   DB7 asks for explicit table roles: the narrow-screen CSS restyles rows as blocks, which can drop table semantics. */
import type { ReactNode } from "react";
import type { FactorReport, FactorStat, MultiDayRegression, ResidualDiagnostics } from "../../api/types";
import { num, pct, pval, signed, tstat } from "../../format";
import { useShowStats } from "../../state/stats";
import "./regression.css";
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
const pctText = (x: number | null | undefined, digits = 2, withSign = true) => or(x, (v) => pct(v, digits, withSign));
const pText = (x: number | null | undefined) => or(x, pval);
const tText = (x: number | null | undefined) => or(x, tstat);

interface TableProps {
  /** Accessible name of the scroll region; ", scrolls sideways" is appended. */
  label: string;
  heads: readonly string[];
  /** Index of the left-aligned reading column, if any. */
  readingCol?: number;
  /**
   * Put the table in the focusable scroll region. Only the main regression table does (DB5);
   * the 5-day and diagnostics tables fit the page and wrap their cells on a phone.
   */
  scroll?: boolean;
  children: ReactNode;
}

/** A regression-style table; the main one sits in a focusable, labelled scroll region, the only one that scrolls sideways. */
function RegTable({ label, heads, readingCol, scroll = false, children }: TableProps) {
  const table = (
    <table role="table" className={scroll ? "reg" : "reg fit"} aria-label={scroll ? undefined : label}>
      <thead role="rowgroup">
        <tr role="row">
          {heads.map((h, i) => (
            <th
              key={h}
              role="columnheader"
              scope="col"
              className={i === 0 ? undefined : i === readingCol ? "rd" : "num"}
            >
              {h}
            </th>
          ))}
        </tr>
      </thead>
      <tbody role="rowgroup">{children}</tbody>
    </table>
  );
  // A keyboard user has to be able to scroll the table, so the region takes focus.
  return scroll ? (
    // eslint-disable-next-line jsx-a11y/no-noninteractive-tabindex
    <div className="scroll-x" tabIndex={0} role="region" aria-label={`${label}, scrolls sideways`}>
      {table}
    </div>
  ) : (
    table
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

/** One number cell; `label` is the column name, shown beside the value on a phone (regression.css). */
function Num({ label, className = "", children }: { label: string; className?: string; children: ReactNode }) {
  return (
    <td role="cell" data-label={label} className={`num${className}`}>
      {children}
    </td>
  );
}

/**
 * Alpha row, then one row per factor. `vif` is null for the 5-day table, which has no VIF column.
 * With statistics off only the term, the estimate and Significant are shown (dashboard spec DV5).
 */
function TermRows({ fit, vif, stats }: { fit: TermFit; vif: Record<string, number | null> | null; stats: boolean }) {
  const alphaNs = fit.alpha_tag !== "reliable";
  return (
    <>
      <tr role="row" className={alphaNs ? "ns" : ""}>
        <th role="rowheader" scope="row">
          Alpha, a year
        </th>
        <Num label="Estimate">{pctText(fit.alpha_annual)}</Num>
        {stats ? (
          <>
            <Num label="Std. error">{pctText(fit.alpha_se_annual, 2, false)}</Num>
            <Num label="t">{tText(fit.alpha_z)}</Num>
            <Num label="p">{pText(fit.alpha_p)}</Num>
            <Num label="p, adjusted">single test</Num>
            <Num label="95% interval">
              {pctText(fit.alpha_ci_low_annual)} to {pctText(fit.alpha_ci_high_annual)}
            </Num>
            {vif !== null ? <Num label="VIF">{"–"}</Num> : null}
          </>
        ) : null}
        <Num label="Significant" className=" sig">
          {alphaNs ? "No" : "Yes"}
        </Num>
      </tr>
      {fit.factors.map((s) => {
        const ns = s.tag !== "reliable";
        return (
          <tr key={s.name} role="row" className={ns ? "ns" : ""}>
            <th role="rowheader" scope="row">
              {s.name}
            </th>
            <Num label="Estimate">{sgn(s.beta)}</Num>
            {stats ? (
              <>
                <Num label="Std. error">{plain(s.se, 4)}</Num>
                <Num label="t">{tText(s.z)}</Num>
                <Num label="p">{pText(s.p)}</Num>
                <Num label="p, adjusted">{pText(s.p_adj_bh)}</Num>
                <Num label="95% interval">
                  {sgn(s.ci_low)} to {sgn(s.ci_high)}
                </Num>
                {vif !== null ? <Num label="VIF">{plain(vif[s.name], 2)}</Num> : null}
              </>
            ) : null}
            <Num label="Significant" className=" sig">
              {ns ? "No" : "Yes"}
            </Num>
          </tr>
        );
      })}
    </>
  );
}

const MAIN_HEADS = ["Term", "Estimate", "Std. error", "t", "p", "p, adjusted", "95% interval", "VIF", "Significant"];
const FIVE_HEADS = ["Term", "Estimate", "Std. error", "t", "p", "p, adjusted", "95% interval", "Significant"];
const PLAIN_HEADS = ["Term", "Estimate", "Significant"];
const DIAG_HEADS = ["Test", "Statistic", "Reference", "p", "Reading"];
const DIAG_PLAIN_HEADS = ["Test", "Reading"];

/** The 5-day estimate (M3.6): present only when the quality gate fired. */
function FiveDayTable({ five, stats }: { five: MultiDayRegression; stats: boolean }) {
  if (five.status !== "ok") return null;
  const caption =
    `${five.caption} R² ${plain(five.r2, 4)}, residual volatility ` +
    `${pctText(five.sigma_e_annual, 2, false)} a year, Newey-West lags ${five.hac_lags}.`;
  return (
    <>
      <h3 className="reg-title">5-day estimate ({five.n_blocks.toLocaleString("en-US")} blocks)</h3>
      <RegTable label="5-day estimate table" heads={stats ? FIVE_HEADS : PLAIN_HEADS}>
        <TermRows fit={five} vif={null} stats={stats} />
      </RegTable>
      <p className="foot">{caption}</p>
    </>
  );
}

/** Residual diagnostics (M3.5) with their plain-language readings. */
function DiagnosticsTable({ rd, stats }: { rd: ResidualDiagnostics; stats: boolean }) {
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
        heads={stats ? DIAG_HEADS : DIAG_PLAIN_HEADS}
        readingCol={stats ? 4 : 1}
      >
        <tr role="row">
          <th role="rowheader" scope="row">
            Lag-1 autocorrelation
          </th>
          {stats ? (
            <>
              <Num label="Statistic">{sgn(rd.lag1_autocorrelation)}</Num>
              <Num label="Reference">z {tText(rd.lag1_z)}</Num>
              <Num label="p">{pText(rd.lag1_p)}</Num>
            </>
          ) : null}
          <td role="cell" className="rd">
            {rd.lag1_reading ?? ""}
          </td>
        </tr>
        {rd.tests.map((t) => (
          <tr key={t.code} role="row">
            <th role="rowheader" scope="row">
              {t.name}
            </th>
            {stats ? (
              <>
                <Num label="Statistic">{plain(t.statistic, 2)}</Num>
                <Num label="Reference">{t.df === null ? "" : `df ${t.df}`}</Num>
                <Num label="p">{pText(t.p)}</Num>
              </>
            ) : null}
            <td role="cell" className="rd">
              {t.reading}
            </td>
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
  const stats = useShowStats();
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
      <RegTable label="Regression detail table" heads={stats ? MAIN_HEADS : PLAIN_HEADS} scroll>
        <TermRows fit={rg} vif={rg.vif} stats={stats} />
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
      <FiveDayTable five={report.five_day_regression} stats={stats} />
      <DiagnosticsTable rd={report.residual_diagnostics} stats={stats} />
    </Panel>
  );
}
