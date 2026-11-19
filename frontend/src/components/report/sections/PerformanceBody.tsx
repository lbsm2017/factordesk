import type { PerformanceSection } from "../../../api/types";
import { count, dateLong, pct } from "../../../format";
import { isMonthly } from "../../../report/subject";
import { drawdownOutcome } from "../../../text/outcomeDeep";
import { Panel } from "../Panel";
import type { ReportPanelProps } from "../types";
import { chartGeometry, episodeDays, xLabels, yAxis } from "./performanceModel";
import "../signColor.css";
import "./PerformancePanel.css";

type Drawdown = NonNullable<PerformanceSection["drawdown"]>;

export const TITLE = "Drawdown";
export const CAPTION = "Past performance over the analysed range. It does not predict future returns.";
const NOT_RECOVERED = "not recovered";

const HOW = [
  "Each day's distance below the highest adjusted close so far, over the analysed range: the same trading days as the factor regression, simple daily total returns.",
  "An episode runs from a high until the price first regains it; the table lists the five deepest, which do not overlap. Days are trading days from the peak to the recovery, or to the end of the data when the price has not recovered.",
  "Return a year is the compound growth rate, not the simple average of daily returns times 252. That average is higher when returns swing widely, because large swings cut compound growth, and it is not what an investor earned.",
].join(" ");

const HOW_MONTHLY = [
  "Each month's distance below the highest level so far, over the analysed range: the same months as the factor regression, simple monthly returns.",
  "An episode runs from a high until the level first regains it; the table lists the five deepest, which do not overlap. Months are counted from the peak to the recovery, or to the end of the data when the level has not recovered.",
  "Return a year is the compound growth rate, not the simple average of monthly returns times 12. That average is higher when returns swing widely, because large swings cut compound growth, and it is not what an investor earned.",
].join(" ");

function nextStep(s: PerformanceSection): string {
  if (s.status === "insufficient_data") return "Widen the date range and run the report again.";
  if (s.status === "failed") return "Run the report again later; the rest of the report is not affected.";
  return "The rest of the report is not affected.";
}

function Chart({ dd, monthly }: { dd: Drawdown; monthly: boolean }) {
  const { dates, values } = dd.series;
  const axis = yAxis(dd.max_drawdown);
  const geo = chartGeometry(dates, values, axis.bottom);
  const labels = xLabels(dates[0] as string, dates[dates.length - 1] as string);
  return (
    <div
      className="dd-chart"
      role="img"
      aria-label={`Underwater chart: how far the ${monthly ? "level" : "price"} sat below its previous high in each ${monthly ? "month" : "day"}, from 0% to ${pct(axis.bottom, 0, false)}. Deepest fall ${pct(dd.max_drawdown, 1)}.`}
    >
      <svg className="dd-svg" viewBox="0 0 1000 100" preserveAspectRatio="none" aria-hidden="true">
        {axis.ticks.map((t) => {
          const y = (t / axis.bottom) * 100;
          return <line key={t} className={t === 0 ? "dd-zero" : "dd-grid"} x1="0" x2="1000" y1={y} y2={y} />;
        })}
        {geo.area ? <path className="dd-area" d={geo.area} /> : null}
        {geo.line ? <path className="dd-line" d={geo.line} /> : null}
      </svg>
      <div className="dd-y" aria-hidden="true">
        {axis.ticks.map((t) => (
          <span key={t} style={{ top: `${(t / axis.bottom) * 100}%` }}>
            {t === 0 ? "0%" : pct(t, 0, false)}
          </span>
        ))}
      </div>
      <div className="dd-x" aria-hidden="true">
        {labels.map((l) => (
          <span key={l.text + l.left} style={{ left: `${l.left}%` }}>
            {l.text}
          </span>
        ))}
      </div>
    </div>
  );
}

function FallsTable({ dd, monthly }: { dd: Drawdown; monthly: boolean }) {
  const rows = dd.episodes.slice(0, 5);
  if (rows.length === 0) return null;
  return (
    <>
      <h3>Largest falls</h3>
      <div className="dd-table-wrap">
        <table className="dd-table">
          <caption className="vh">
            {rows.length === 1 ? "The largest fall" : `The ${rows.length} largest falls`} from a high, deepest first
          </caption>
          <thead>
            <tr>
              <th scope="col" className="num" title="Largest fall from a previous high, close to close">
                Fall
              </th>
              <th scope="col">Peak</th>
              <th scope="col" className="hide-s">
                Low
              </th>
              <th scope="col">Recovered</th>
              <th scope="col" className="num hide-s" title={`${monthly ? "Months" : "Trading days"} from peak to recovery, or to the end of the data`}>
                {monthly ? "Months" : "Days"}
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map((e) => {
              const days = episodeDays(e, dd.series.dates);
              return (
                <tr key={`${e.peak_date}-${e.trough_date}`}>
                  <td className="num strong num-neg">{pct(e.depth, 1)}</td>
                  <td>{dateLong(e.peak_date)}</td>
                  <td className="hide-s">{dateLong(e.trough_date)}</td>
                  <td>{e.recovery_date === null ? NOT_RECOVERED : dateLong(e.recovery_date)}</td>
                  <td className="num hide-s">{days === null ? "n/a" : count(days)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </>
  );
}

/** Body of the Drawdown panel (section `performance`). Renders nothing while the section is null. */
export function PerformanceBody({ report }: ReportPanelProps) {
  const s = report.performance;
  if (s === null) return null;
  if (s.status !== "ok" || s.drawdown === null) {
    return (
      <Panel
        id="performance"
        title={TITLE}
        empty={{ reason: s.reason ?? "Performance could not be computed for this range.", action: nextStep(s) }}
      />
    );
  }
  const dd = s.drawdown;
  const monthly = isMonthly(report);
  return (
    <Panel
      id="performance"
      title={TITLE}
      legend={<div className="pm">{`Max drawdown ${dd.max_drawdown === 0 ? "0%" : pct(dd.max_drawdown, 1)}`}</div>}
      outcome={drawdownOutcome(report, s)}
      footnote={CAPTION}
      how={monthly ? HOW_MONTHLY : HOW}
    >
      {dd.series.dates.length > 1 ? <Chart dd={dd} monthly={monthly} /> : null}
      <FallsTable dd={dd} monthly={monthly} />
    </Panel>
  );
}
