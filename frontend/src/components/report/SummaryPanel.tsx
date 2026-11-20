import { currencyOf, reportCurrency } from "../../api/currency";
import type { FactorReport } from "../../api/types";
import { dateLong, pct, signed, tstat } from "../../format";
import { useShowStats } from "../../state/stats";
import {
  alphaReading,
  betaReading,
  drawdownReading,
  pctRange,
  r2Reading,
  residualVolReading,
  sharpeReading,
  signedRange,
  verdict,
  worldBetaReading,
} from "../../text/verdict";
import type { Reading } from "../../text/verdict";
import { countWord, factorCount } from "../../report/derive";
import { frequencyWord, isSubjectReport } from "../../report/subject";
import { Icon } from "../shell/icons";
import { DataNotes } from "./DataNotes";
import { Panel } from "./Panel";
import type { ReportPanelProps } from "./types";
import "./summary.css";

/** One table row; a null `value` prints a dash. The sign colour applies only where `signed` is set. */
interface Row {
  label: string;
  tip: string;
  value: string | null;
  /** Colour the sign: set only for signed returns, alpha, Sharpe and drawdown. */
  signed?: true;
  reading: Reading;
  t: string | null;
  interval: string | null;
  /** The currency code printed after a key figure (euro view only). */
  unit?: string;
  /** A small line under the label, for example "against EUR cash". */
  sub?: string;
}

const DASH = "–";
const NO_TEST: Reading = { word: DASH, evidence: "none" };

/** Label and one-line explanation of every metric. */
const METRIC = {
  ret: ["Annualised return", "Compound growth a year, dividends reinvested, before costs and taxes"],
  vol: ["Volatility", "Standard deviation of daily returns, scaled to a year"],
  sharpe: ["Sharpe ratio", "Return above the risk-free rate per unit of volatility, a year"],
  dd: ["Max drawdown", "Largest fall from a previous high, close to close"],
  alpha: ["Alpha (annual)", "Return a year that the five factor exposures do not explain"],
  r2: ["R²", "Share of daily moves explained by the five factors"],
  resid: ["Residual volatility", "Volatility a year of the returns the factors do not explain"],
  us: ["Market beta (five-factor)", "Exposure to the US market factor (Mkt-RF) with the other four factors held fixed; the World beta panel shows a one-factor US market beta, which can differ"],
  acwi: ["Beta to ACWI", "One-factor exposure to the ACWI ETF, a stand-in for the MSCI ACWI index"],
} as const;

function fin(x: number | null | undefined): x is number {
  return typeof x === "number" && Number.isFinite(x);
}

/** `fmt(x)` when x is a finite number, else null. */
function show(x: number | null | undefined, fmt: (n: number) => string): string | null {
  return fin(x) ? fmt(x) : null;
}

function range(lo: number | null | undefined, hi: number | null | undefined, fmt: (a: number, b: number) => string) {
  return fin(lo) && fin(hi) ? fmt(lo, hi) : null;
}

function row(key: keyof typeof METRIC, o: Partial<Omit<Row, "label" | "tip">> = {}): Row {
  const [label, tip] = METRIC[key];
  return { label, tip, value: null, reading: NO_TEST, t: null, interval: null, ...o };
}

/** The performance rows; every value is a dash while the section is absent or not ok. */
function performanceRows(report: FactorReport): { rows: Row[]; reason: string | null } {
  // The euro view puts the currency code on the key figures (return, worst fall) and names the cash behind the Sharpe ratio.
  const eur = reportCurrency(report) === "EUR";
  const unit = eur ? ({ unit: "EUR" } as const) : {};
  const section = report.performance;
  const ok = section?.status === "ok" ? section : null;
  const sh = ok?.sharpe ?? null;
  const cagr = ok?.returns?.cagr;
  const ratio = sh?.ratio_annual;
  const dd = ok?.drawdown?.max_drawdown;
  return {
    reason: ok ? null : section ? (section.reason ?? "Performance could not be computed.") : "Performance is not in this report.",
    rows: [
      row("ret", { value: show(cagr, (n) => pct(n, 1)), signed: true, ...unit }),
      row("vol", { value: show(ok?.volatility_annual, (n) => pct(n, 1, false)) }),
      row("sharpe", {
        value: show(ratio, (n) => signed(n, 2)),
        signed: true,
        reading: ok ? sharpeReading(sh, report) : NO_TEST,
        interval: range(sh?.ci95_low, sh?.ci95_high, signedRange),
        ...(eur ? { sub: "against EUR cash" } : {}),
      }),
      row("dd", { value: show(dd, (n) => pct(n, 1)), signed: true, reading: ok ? drawdownReading(ok) : NO_TEST, ...unit }),
    ],
  };
}

/** The factor model rows; every value is a dash while the fit or the world beta is missing. */
function modelRows(report: FactorReport): { rows: Row[]; reasons: string[] } {
  const reg = report.regression;
  const rg = reg.status === "ok" ? reg : null;
  const mkt = rg?.factors.find((f) => f.name === "Mkt-RF");
  const wb = report.world_beta;
  const w = wb?.status === "ok" ? wb.world : null;
  const reasons: string[] = [];
  if (!rg) reasons.push(reg.reason ?? `The ${countWord(factorCount(report))}-factor model could not be fitted.`);
  if (!w && !isSubjectReport(report)) {
    reasons.push(wb ? (wb.reason ?? "The ACWI beta could not be computed.") : "The ACWI beta is not in this report.");
  }
  return {
    reasons,
    rows: [
      row("alpha", {
        value: show(rg?.alpha_annual, (n) => pct(n, 2)),
        signed: true,
        reading: rg ? alphaReading(report) : NO_TEST,
        t: show(rg?.alpha_z, tstat),
        interval: range(rg?.alpha_ci_low_annual, rg?.alpha_ci_high_annual, pctRange),
      }),
      row("r2", { value: show(rg?.r2, (n) => pct(n, 1, false)), reading: rg ? r2Reading(report) : NO_TEST }),
      row("resid", { value: show(rg?.sigma_e_annual, (n) => pct(n, 1, false)), reading: rg ? residualVolReading(report) : NO_TEST }),
      row("us", {
        value: show(mkt?.beta, (n) => signed(n, 2)),
        reading: rg ? betaReading(report, "Mkt-RF") : NO_TEST,
        t: show(mkt?.z, tstat),
        interval: range(mkt?.ci_low, mkt?.ci_high, signedRange),
      }),
      // An uploaded record has no ACWI beta (daily data only): the row is left out, not shown as a dash.
      ...(isSubjectReport(report)
        ? []
        : [
            row("acwi", {
              value: show(w?.beta, (n) => signed(n, 2)),
              reading: wb && w ? worldBetaReading(wb, report) : NO_TEST,
              t: w && w.se > 0 ? tstat(w.beta / w.se) : null,
              interval: range(w?.ci_low, w?.ci_high, signedRange),
            }),
          ]),
    ],
  };
}

/** Sign colour from the printed value: "+" is positive, the true minus is negative. */
function signClass(r: Row): string {
  return r.signed && r.value ? (r.value.startsWith("+") ? " num-pos" : r.value.startsWith("−") ? " num-neg" : "") : "";
}

function KvTable({ id, title, rows, stats }: { id: string; title: string; rows: Row[]; stats: boolean }) {
  return (
    <div>
      <h3 id={id}>{title}</h3>
      <div className="tw">
        <table className="tbl kv" aria-labelledby={id}>
          <thead>
            <tr>
              <th scope="col">Metric</th>
              <th scope="col" className="num">
                Value
              </th>
              <th
                scope="col"
                title="Clear evidence: the 95% interval excludes zero after correcting for testing all the betas at once. Could be noise: it does not. The test protects against noise only; it does not show that a factor caused the returns."
              >
                Reading
              </th>
              {stats ? (
                <>
                  <th scope="col" className="num">
                    t
                  </th>
                  <th scope="col" className="num">
                    95% interval
                  </th>
                </>
              ) : null}
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.label} className={r.reading.evidence === "noise" ? "is-noise" : undefined}>
                <th scope="row">
                  <span className="tip" title={r.tip}>
                    {r.label}
                  </span>
                  {r.sub ? <span className="ccy-sub">{r.sub}</span> : null}
                </th>
                <td className={`num v${r.value === null ? " na" : signClass(r)}`}>
                  {r.value ?? DASH}
                  {r.value !== null && r.unit ? <span className="ccy">{r.unit}</span> : null}
                </td>
                <td className={`rd${r.reading.evidence === "none" ? " na" : ""}`} title={r.reading.note}>
                  {r.reading.word}
                </td>
                {stats ? (
                  <>
                    <td className={`num${r.t === null ? " na" : ""}`}>{r.t ?? DASH}</td>
                    <td className={`num${r.interval === null ? " na" : ""}`}>{r.interval ?? DASH}</td>
                  </>
                ) : null}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

/** The Summary of dashboard v2 (prototype v4a): verdict, data notes, and the two key-metric tables. */
export function SummaryPanel({ report }: ReportPanelProps) {
  const stats = useShowStats();
  const v = verdict(report);
  const perf = performanceRows(report);
  const model = modelRows(report);
  // The one-line explanations name the frequency of the returns.
  // and the number of factors of the model (five for FF5, six for FF6).
  const k = factorCount(report);
  const worded = (rows: Row[]): Row[] =>
    rows.map((r) => ({
      ...r,
      tip: r.tip
        .replace("daily", frequencyWord(report))
        .replace("the risk-free rate", reportCurrency(report) === "EUR" ? "the euro cash rate" : "the risk-free rate")
        .replace("five", countWord(k))
        .replace("other four", `other ${countWord(k - 1)}`),
      label: r.label.replace("five-factor", `${countWord(k)}-factor`),
    }));
  const currency = currencyOf(report);
  const notes = currency?.reference === "EUR" ? (currency.notes ?? []).filter((n) => n.trim() !== "") : [];
  const { actual_start: start, actual_end: end } = report.data;
  const period = start && end ? `${dateLong(start)} to ${dateLong(end)}. ` : "";
  const reasons = [...(perf.reason ? [perf.reason] : []), ...model.reasons];
  return (
    <Panel
      id="summary"
      title="Summary"
      legend={
        <div className="pm">
          {currency?.reference === "EUR" ? "Figures in EUR. " : ""}
          {period}Past data, not a forecast.
        </div>
      }
      footnote={`Annualised from ${frequencyWord(report)} data.${isSubjectReport(report) ? "" : " ACWI is an ETF used as a stand-in for the MSCI ACWI index."}`}
    >
      <p className="verdict">
        {v.headline}
        {v.hedge ? <span className="hedge"> {v.hedge}</span> : null}
      </p>
      <DataNotes report={report} />
      {notes.length > 0 ? (
        <ul className="cur-notes" aria-label="Currency notes">
          {notes.map((n) => (
            <li key={n}>
              <Icon name="info" />
              <span>{n}</span>
            </li>
          ))}
        </ul>
      ) : null}
      <div className="sum-tables">
        <KvTable id="sum-perf" title="Performance" rows={worded(perf.rows)} stats={stats} />
        <KvTable id="sum-model" title="Factor model" rows={worded(model.rows)} stats={stats} />
      </div>
      {reasons.length > 0 ? (
        <p className="sum-reason" role="note">
          {reasons.map((r) => r.replace(/\.*$/, ".")).join(" ")}
        </p>
      ) : null}
    </Panel>
  );
}
