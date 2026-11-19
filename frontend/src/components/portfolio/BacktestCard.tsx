import type { PortfolioBacktestSection } from "../../api/types";
import { count, dateShort } from "../../format";

function pct(x: number, digits = 1): string {
  return `${(x * 100).toFixed(digits)}%`;
}

/** "IGOV" or "IGOV and EMB" or "A, B and C". */
function names(list: readonly string[]): string {
  if (list.length <= 1) return list[0] ?? "none";
  return `${list.slice(0, -1).join(", ")} and ${list[list.length - 1]}`;
}

/**
 * The compact "Backtest" card at the top of a portfolio report: the window and the instruments that
 * limit it, the rebalances, the cost, the unallocated weight, any skipped trading days, and the
 * survivorship note that every backtest carries.
 */
export function BacktestCard({ section }: { section: PortfolioBacktestSection }) {
  const rows: [string, string][] = [
    ["Window", `${dateShort(section.window_start)} to ${dateShort(section.window_end)}`],
    ["Starts when", `${names(section.start_limited_by)} begins`],
    ["Ends when", `${names(section.end_limited_by)} ends`],
    ["Instruments", count(section.n_instruments)],
    ["Rebalances", `${count(section.n_rebalances)} monthly`],
    [
      "Cost",
      `${section.cost_bps} bps one way, ${pct(section.total_cost, 2)} paid in total (average turnover ${pct(section.average_turnover)})`,
    ],
    ["Unallocated", section.unallocated_weight > 0 ? `${pct(section.unallocated_weight)} held as USD cash` : "None"],
    [
      "Skipped days",
      section.n_dates_dropped > 0 ? `${count(section.n_dates_dropped)} trading days without a full set of prices` : "None",
    ],
  ];
  return (
    <section className="panel sumcard" aria-labelledby="backtest-title" id="backtest" data-testid="backtest-card">
      <div className="panel-head">
        <h2 id="backtest-title">Backtest</h2>
        <div className="pm">Monthly rebalancing, in US dollars</div>
      </div>
      <dl className="kv">
        {rows.map(([term, value]) => (
          <div key={term}>
            <dt>{term}</dt>
            <dd>{value}</dd>
          </div>
        ))}
      </dl>
      {section.data_note ? <p className="foot-note">{section.data_note}</p> : null}
      <div className="foot">
        <p>{section.survivorship_note}</p>
      </div>
    </section>
  );
}
