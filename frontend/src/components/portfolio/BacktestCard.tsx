import type { PortfolioBacktestSection } from "../../api/types";
import type { Currency } from "../../state/currency";
import { count, dateShort } from "../../format";

function pct(x: number, digits = 1): string {
  return `${(x * 100).toFixed(digits)}%`;
}

/** "IGOV" or "IGOV and EMB" or "A, B and C". */
function names(list: readonly string[]): string {
  // The API names a holding "IEF (IEF)" when label and ticker agree.
  const clean = list.map((name) => {
    const same = /^(\S+) \((\S+)\)$/.exec(name);
    return same !== null && same[1] === same[2] ? same[1] : name;
  });
  if (clean.length <= 1) return clean[0] ?? "none";
  return `${clean.slice(0, -1).join(", ")} and ${clean[clean.length - 1]}`;
}

/**
 * The compact "Backtest" card at the top of a portfolio report: the window and the instruments that
 * limit its start, the rebalances, the cost, any unallocated weight or skipped trading days, and the
 * survivorship note that every backtest carries.
 */
export function BacktestCard({ section, currency = "USD" }: { section: PortfolioBacktestSection; currency?: Currency }) {
  const rows: [string, string][] = [
    ["Window", `${dateShort(section.window_start)} to ${dateShort(section.window_end)}`],
    ["Starts when", `${names(section.start_limited_by)} begins`],
    ["Instruments", count(section.n_instruments)],
    ["Rebalances", `${count(section.n_rebalances)} monthly`],
    [
      "Cost",
      `${section.cost_bps} bps one way, ${pct(section.total_cost, 2)} paid in total (average turnover ${pct(section.average_turnover)})`,
    ],
  ];
  // Rows that would only say "None" are left out.
  if (section.unallocated_weight > 0) {
    rows.push(["Unallocated", `${pct(section.unallocated_weight)} held as USD cash`]);
  }
  if (section.n_dates_dropped > 0) {
    rows.push(["Skipped days", `${count(section.n_dates_dropped)} trading days without a full set of prices`]);
  }
  return (
    <section className="panel sumcard" aria-labelledby="backtest-title" id="backtest" data-testid="backtest-card">
      <div className="panel-head">
        <h2 id="backtest-title">Backtest</h2>
        <div className="pm">Monthly rebalancing, in {currency === "EUR" ? "euros" : "US dollars"}</div>
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
