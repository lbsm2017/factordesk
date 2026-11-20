import type { TailRiskSection } from "../../../api/types";
import { isMonthly } from "../../../report/subject";
import { Panel } from "../Panel";
import type { ReportPanelProps } from "../types";
import { APPROXIMATE, bandName, basedOn, CAPTION, INDICATIVE, loss, METHODS, rowsOf } from "./tailRiskModel";
import type { TailFigure } from "./tailRiskModel";
import "./TailRiskPanel.css";

export const TITLE = "Tail risk";

const HOW = [
  "Value at risk (VaR) is the loss that is exceeded on only 1 day in 100 (99% level), or 1 month in 20 (95% level). CVaR, also called expected shortfall, is the average loss on the days beyond the 97.5% (or 95%) level. Losses are computed from simple returns and shown as positive percentages.",
  "Historical uses the observed returns directly and shows n/a when the sample holds too few tail observations. Gaussian uses the average and the standard deviation of the returns. Cornish-Fisher adjusts the Gaussian figure for skew and fat tails, and shows n/a where its formula is not valid; a figure marked indicative passes the check only on the range it uses, or differs from the historical figure by more than half of it (hover the label for the reason). Where Cornish-Fisher VaR is n/a, its CVaR is n/a too.",
  "Each band is a 90% bootstrap band: the returns are resampled 1,000 times (in blocks for daily returns), and the band holds the middle 90% of the resulting figures. Bands for Gaussian and for historical VaR matched their coverage on simulated data; the others tend to be narrow.",
].join(" ");

interface CellProps {
  figure: TailFigure | undefined;
  n: number;
  monthly: boolean;
  bandLevel: number;
}

function Cell({ figure, n, monthly, bandLevel }: CellProps) {
  if (figure === undefined) return <td />;
  if (figure.value === null) {
    return (
      <td>
        <span className="tr-na">n/a</span>
        <span className="tr-note">{figure.reason}</span>
      </td>
    );
  }
  const tail =
    figure.tail_count === null
      ? undefined
      : `${figure.tail_count} observations in the tail; ${figure.expected_tail_obs.toFixed(1)} expected`;
  return (
    <td title={tail}>
      <span className="tr-value">{loss(figure.value)}</span>
      {figure.band ? (
        <span className="tr-note">
          {bandName(bandLevel)} band {loss(figure.band.low)} to {loss(figure.band.high)}
        </span>
      ) : (
        <span className="tr-note">{figure.band_reason}</span>
      )}
      {figure.band && figure.band_quality === "approximate" ? <span className="tr-flag">{APPROXIMATE}</span> : null}
      {figure.indicative ? <span className="tr-flag" title={figure.reason ?? undefined}>{INDICATIVE}</span> : null}
      <span className="tr-note">based on {basedOn(n, monthly)}</span>
    </td>
  );
}

function Body({ section, monthly }: { section: TailRiskSection; monthly: boolean }) {
  const rows = rowsOf(section.figures ?? []);
  const n = section.series?.n_obs ?? 0;
  const bandLevel = section.series?.band_level ?? 0.9;
  return (
    <div className="tr-wrap">
      <table className="tr-table">
        <caption className="vh">
          {monthly ? "Monthly" : "Daily"} value at risk and expected shortfall by method, as a loss in percent
        </caption>
        <thead>
          <tr>
            <th scope="col">Measure</th>
            {METHODS.map((m) => (
              <th key={m.key} scope="col">
                {m.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.key}>
              <th scope="row">{row.label}</th>
              {METHODS.map((m) => (
                <Cell key={m.key} figure={row.cells[m.key]} n={n} monthly={monthly} bandLevel={bandLevel} />
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/**
 * Panel of the `tail_risk` section (VaR and CVaR; backend `report/sections/tail_risk.py`, spec E7).
 * Registered in `panelRegistry.ts` at position 460, right after Drawdown. Renders nothing when the
 * section is absent (null).
 */
export function TailRiskPanel({ report }: ReportPanelProps) {
  const s = report.tail_risk;
  if (s == null) return null;
  const monthly = isMonthly(report);
  if (s.status !== "ok") {
    return (
      <Panel
        id="tail-risk"
        title={TITLE}
        empty={{
          reason: s.reason ?? "Tail risk could not be computed for this range.",
          action: "The rest of the report is not affected.",
        }}
      />
    );
  }
  return (
    <Panel
      id="tail-risk"
      title={TITLE}
      question={monthly ? "How large a loss does a bad month bring?" : "How large a loss does a bad day bring?"}
      footnote={CAPTION}
      how={HOW}
    >
      <Body section={s} monthly={monthly} />
    </Panel>
  );
}
