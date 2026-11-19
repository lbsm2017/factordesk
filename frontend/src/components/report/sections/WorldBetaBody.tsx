/* The table roles below are explicit on purpose: narrow screens restyle the rows as grids, which
   can drop the native table semantics (design DB7). */
/* eslint-disable jsx-a11y/no-redundant-roles, jsx-a11y/no-interactive-element-to-noninteractive-role */
import type { CSSProperties } from "react";
import type { WorldBetaSection } from "../../../api/types";
import { count, dateLong, num, signed } from "../../../format";
import { useShowStats } from "../../../state/stats";
import { position } from "../../charts/BarCell";
import { niceDomain } from "../exposureModel";
import type { NiceDomain } from "../exposureModel";
import { AxisRow } from "../barParts";
import { Panel } from "../Panel";
import type { ReportPanelProps } from "../types";
import { europeOk, outcomeLine, sameFit } from "./worldBetaModel";
import type { BetaFit, ProxyBeta } from "./worldBetaModel";
import "./WorldBetaPanel.css";

export const TITLE = "World beta";
const CAPTION = "Beta against the world and against the US market, with 95% intervals, R squared and days";
const DEFAULT_DESC = "Descriptive, in-sample, not predictive.";
const QUICK = "A quick estimate.";
const PROXY_SHORT = "ACWI is an ETF used as a stand-in for the MSCI ACWI index.";
const EUROPE_PROXY = "Europe uses IEUR, the iShares Core MSCI Europe ETF, as a stand-in for the MSCI Europe index.";
const EUROPE_SUB = "IEUR, MSCI Europe stand-in";

interface Row {
  key: string;
  label: string;
  tip: string;
  fit: BetaFit;
  days: string;
  sub?: string;
}

function nextStep(s: WorldBetaSection): string {
  if (s.status === "insufficient_data") return "Choose a longer range.";
  if (s.status === "failed") return "Try again later.";
  return "The rest of the report is not affected.";
}

function domainOf(rows: readonly Row[]): NiceDomain {
  const values = [0, 1];
  for (const r of rows) values.push(r.fit.ci_low, r.fit.ci_high, r.fit.beta);
  return niceDomain(Math.min(...values), Math.max(...values), 4);
}

function interval(fit: BetaFit): string {
  return `${num(fit.ci_low, 2)} to ${num(fit.ci_high, 2)}`;
}

function textOf(row: Row): string {
  return `${row.label}: beta ${signed(row.fit.beta, 2)}, 95% interval ${interval(row.fit)}, R squared ${num(row.fit.r2, 2)}`;
}

function BetaPlot({ row, domain }: { row: Row; domain: NiceDomain }) {
  const { lo, hi, ticks } = domain;
  const a = position(row.fit.ci_low, lo, hi);
  const b = position(row.fit.ci_high, lo, hi);
  return (
    <svg className="bar-svg" aria-hidden="true">
      <title>{textOf(row)}</title>
      {ticks.map((t) => {
        const x = `${position(t, lo, hi)}%`;
        return <line key={t} className={Math.abs(t) < 1e-12 ? "zero" : "grid"} x1={x} x2={x} y1="0" y2="100%" />;
      })}
      <line className="ci" x1={`${a}%`} x2={`${b}%`} y1="50%" y2="50%" />
      {b - a >= 1.2 ? (
        <>
          <line className="ci" x1={`${a}%`} x2={`${a}%`} y1="42%" y2="58%" />
          <line className="ci" x1={`${b}%`} x2={`${b}%`} y1="42%" y2="58%" />
        </>
      ) : null}
      <circle className="wb-dot" cx={`${position(row.fit.beta, lo, hi)}%`} cy="50%" r="4.5" />
    </svg>
  );
}

function footnote(report: ReportPanelProps["report"], s: WorldBetaSection): string {
  const texts = report.label_text;
  const e = s.europe ?? null;
  const parts = [
    texts["L-DESC"] ?? DEFAULT_DESC,
    QUICK,
    texts["L-WORLD-PROXY"] ?? PROXY_SHORT,
    e ? EUROPE_PROXY : "",
    s.acwi_last_date ? `ACWI data ends ${dateLong(s.acwi_last_date)}.` : "",
    s.acwi_note ?? "",
    e?.last_date ? `IEUR data ends ${dateLong(e.last_date)}.` : "",
    e?.note ?? "",
  ];
  return parts.filter(Boolean).join(" ");
}

function howEurope(e: ProxyBeta): string[] {
  const first = e.start ? dateLong(e.start) : "n/a";
  const last = e.end ? dateLong(e.end) : "n/a";
  const out = [
    `The Europe row is the same regression with IEUR in place of ACWI, on its own ${count(e.n_days)} days, ${first} to ${last}: ` +
      "the days of the analysed sample that IEUR also has. When those days differ from the ACWI days, the US market beta on them is shown in its own row.",
  ];
  if (e.n_not_in_benchmark) {
    out.push(
      `${count(e.n_not_in_benchmark)} days of the analysed sample were left out of the Europe row because IEUR has no usable return for them.`,
    );
  }
  return [...out, ...e.audit_warnings];
}

function how(report: ReportPanelProps["report"], s: WorldBetaSection, europe: ProxyBeta | null): string {
  const first = s.sample.start ? dateLong(s.sample.start) : "n/a";
  const last = s.sample.end ? dateLong(s.sample.end) : "n/a";
  const method =
    "Each beta is the slope of a regression of the stock's daily excess return (return minus the daily US risk-free rate) " +
    "on one daily excess return, with an intercept: the ACWI ETF's in the first row, the US market factor Mkt-RF of the " +
    `Fama-French file in the second. Both use the same ${count(s.sample.n)} days, ${first} to ${last}: the days of the ` +
    `analysed sample that ACWI also has. Standard errors are Newey-West with ${s.hac_lags ?? "n/a"} lags; intervals are 95% and normal.`;
  const reading =
    "The comparison says about the same when the two intervals overlap, and otherwise which beta is higher. It is an " +
    "informal reading of the intervals, not a test of the difference: both betas use the same stock returns.";
  const extra = s.n_not_in_benchmark
    ? `${count(s.n_not_in_benchmark)} days of the analysed sample were left out because ACWI has no usable return for them.`
    : "";
  const timing = report.label_text["L-WORLD-ASYNC"] ?? "";
  const more = europe ? howEurope(europe) : [];
  return [method, reading, extra, timing, ...s.audit_warnings, ...more].filter(Boolean).join(" ");
}

/** Body of the World beta panel (section `world_beta`). Renders nothing while the section is null. */
export function WorldBetaBody({ report }: ReportPanelProps) {
  const stats = useShowStats();
  const s = report.world_beta;
  if (s === null) return null;
  const europe = europeOk(s);
  const world = s.status === "ok" && s.world !== null && s.us_market !== null;
  if (!world && europe === null) {
    return (
      <Panel
        id="world-beta"
        title={TITLE}
        empty={{ reason: s.reason ?? "The world beta could not be computed for this range.", action: nextStep(s) }}
      />
    );
  }
  const rows: Row[] = [];
  if (s.world !== null && s.us_market !== null && world) {
    rows.push({ key: "acwi", label: "ACWI", tip: "ACWI ETF, a stand-in for the MSCI ACWI index", fit: s.world, days: count(s.n_sample) });
  }
  if (europe?.benchmark) {
    rows.push({
      key: "europe",
      label: "Europe",
      sub: EUROPE_SUB,
      tip: "iShares Core MSCI Europe ETF, a stand-in for the MSCI Europe index",
      fit: europe.benchmark,
      days: count(europe.n_days),
    });
  }
  if (world && s.us_market !== null) {
    rows.push({ key: "us", label: "US market", tip: "Fama-French market factor, Mkt-RF", fit: s.us_market, days: "same" });
  }
  if (europe?.us_market && !(s.us_market && sameFit(europe.us_market, s.us_market))) {
    rows.push({
      key: "us-europe",
      label: "US market, same days as Europe",
      tip: "Fama-French market factor, Mkt-RF, on the days Europe has",
      fit: europe.us_market,
      days: count(europe.n_days),
    });
  }
  const europeReading = europe?.comparison_text ?? null;
  const domain = domainOf(rows);
  const numberColumns = stats ? 4 : 2;
  const style = { "--wb-cols": numberColumns } as CSSProperties;
  return (
    <Panel
      id="world-beta"
      title={TITLE}
      legend={<div className="pm">{`Quick estimate, ${count(world ? s.n_sample : (europe?.n_days ?? 0))} days, one-factor`}</div>}
      reading={world ? (outcomeLine(s) ?? undefined) : undefined}
      footnote={footnote(report, s)}
      how={how(report, s, europe)}
    >
      {europeReading ? <p className="reading">{europeReading}</p> : null}
      <table role="table" className="bars wb" style={style}>
        <caption className="vh">{CAPTION}</caption>
        <thead role="rowgroup">
          <tr role="row">
            <th role="columnheader" scope="col">
              Against
            </th>
            <th role="columnheader" scope="col" className="plot-h">
              <span className="vh">Chart</span>
            </th>
            <th role="columnheader" scope="col" className="num" title="Sensitivity to the index: +1 means a one-for-one move">
              Beta
            </th>
            {stats ? (
              <th role="columnheader" scope="col" className="num wide" title="95% confidence interval">
                95% interval
              </th>
            ) : null}
            {stats ? (
              <th role="columnheader" scope="col" className="num" title="Share of daily moves explained by this one index">
                R²
              </th>
            ) : null}
            <th role="columnheader" scope="col" className="num" title="Days of the analysed sample used">
              Days
            </th>
          </tr>
        </thead>
        <tbody role="rowgroup">
          {rows.map((r) => (
            <tr key={r.key} role="row" id={`world-beta-${r.key}`}>
              <th role="rowheader" scope="row" title={r.tip}>
                <span className="fname">{r.label}</span>
                {r.sub ? <span className="sub"> {r.sub}</span> : null}
              </th>
              <td role="cell" className="plot-cell">
                <BetaPlot row={r} domain={domain} />
                <span className="vh">{textOf(r)}</span>
              </td>
              <td role="cell" className="num strong" data-label="Beta">
                {signed(r.fit.beta, 2)}
              </td>
              {stats ? (
                <td role="cell" className="num wide" data-label="95% interval">
                  {interval(r.fit)}
                </td>
              ) : null}
              {stats ? (
                <td role="cell" className="num" data-label="R²">
                  {num(r.fit.r2, 2)}
                </td>
              ) : null}
              <td role="cell" className="num" data-label="Days">
                {r.days}
              </td>
            </tr>
          ))}
        </tbody>
        <tfoot role="rowgroup">
          <AxisRow
            ticks={domain.ticks}
            lo={domain.lo}
            hi={domain.hi}
            format={(t) => (Math.abs(t) < 1e-12 ? "0" : signed(t, 2))}
            columns={numberColumns}
          />
        </tfoot>
      </table>
    </Panel>
  );
}
