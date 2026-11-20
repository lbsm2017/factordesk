import { useId, useState } from "react";
import type { LibraryLine } from "../../api/types";
import { dateShort } from "../../format";
import { checks, classTotals, earliestCommonStart, lineCount, runnable } from "../../portfolio/composer";
import type { CheckTone } from "../../portfolio/composer";
import { instruments, remainder, totalWeight } from "../../portfolio/tree";
import type { PortfolioTree } from "../../portfolio/tree";
import { Icon } from "../shell/icons";
import type { IconName } from "../shell/icons";
import { assetClassColor, cssVars } from "./assetClass";

export interface LivePanelProps {
  tree: PortfolioTree;
  library: ReadonlyMap<string, LibraryLine>;
  /** Today, for the length of the history. */
  now: Date;
  running: boolean;
  onCost: (bps: number) => void;
  onNormalise: () => void;
  onRemainderToCash: () => void;
  /** The reference currency: unallocated weight is held as cash of that currency. */
  currency: "USD" | "EUR";
  onRun: () => void;
}

const TONE_ICON: Record<CheckTone, { icon: IconName; cls: string }> = {
  warn: { icon: "warn", cls: "warn" },
  error: { icon: "warn", cls: "errc" },
  ok: { icon: "check", cls: "okc" },
  info: { icon: "info", cls: "infoc" },
};

function pct1(weight: number): string {
  return `${(weight * 100).toFixed(1)}%`;
}

const NOTE = "Prices come from Yahoo Finance. Past data, not a forecast.";

/** The total and the gap badge, shared by the live panel and the phone dock. */
export function totalBadge(tree: PortfolioTree): { text: string; tone: "ok" | "warn" | "over"; icon: IconName } {
  const total = totalWeight(tree);
  if (total - 1 > 1e-9) return { text: `${pct1(total - 1)} over 100%`, tone: "over", icon: "warn" };
  const rest = remainder(tree);
  if (rest > 0) return { text: `${pct1(rest)} unallocated`, tone: "warn", icon: "warn" };
  return { text: "100% allocated", tone: "ok", icon: "check" };
}

/**
 * The right half of the composer: the live check of the tree. It shows the total and the gap, a
 * stacked bar and ranked list by asset class, the checks, the earliest common start (naming the
 * leaf that sets it), the trading cost, and the three actions. Every figure is also text, so the
 * colour of a bar or a badge is never the only carrier of meaning.
 */
export function LivePanel({ tree, library, currency, now, running, onCost, onNormalise, onRemainderToCash, onRun }: LivePanelProps) {
  const costId = useId();
  const noteId = useId();
  const [costDraft, setCostDraft] = useState<string | null>(null);
  const total = totalWeight(tree);
  const rest = remainder(tree);
  const classes = classTotals(tree);
  const badge = totalBadge(tree);
  const start = earliestCommonStart(tree, library);
  const list = checks(tree, library, currency);
  const run = runnable(tree);
  const years =
    start.date === null ? null : (now.getTime() - Date.parse(`${start.date}T00:00:00Z`)) / (365.25 * 86_400_000);
  const stackLabel = `Weight by asset class: ${[
    ...classes.filter((c) => c.weight > 0).map((c) => `${c.label} ${pct1(c.weight)}`),
    ...(rest > 0 ? [`unallocated ${pct1(rest)}`] : []),
  ].join(", ")}`;
  const atHundred = Math.abs(total - 1) <= 1e-9;

  return (
    <aside className="live" aria-label="Live portfolio check">
      <section className="panel">
        <div className="panel-head">
          <h2>Portfolio check</h2>
          <div className="pm">
            {lineCount(tree)} {lineCount(tree) === 1 ? "line" : "lines"} · {instruments(tree).length}{" "}
            {instruments(tree).length === 1 ? "instrument" : "instruments"}
          </div>
        </div>

        <div className="total-row" aria-live="polite">
          <div>
            <div className="pm">Total weight</div>
            <div className="total-fig">{pct1(total)}</div>
          </div>
          <span className={badge.tone === "ok" ? "pill ok" : badge.tone === "over" ? "pill over" : "pill"}>
            <Icon name={badge.icon} />
            <span>{badge.text}</span>
          </span>
        </div>

        <div className="stack" role="img" aria-label={stackLabel}>
          {classes
            .filter((c) => c.weight > 0)
            .map((c) => (
              <i key={c.id} style={cssVars({ "--v": c.weight * 100, "--c": assetClassColor(c.label) })} />
            ))}
          {rest > 0 ? <i className="gap" style={cssVars({ "--v": rest * 100 })} /> : null}
        </div>
        <ul className="rank">
          {classes.map((c) => (
            <li key={c.id}>
              <span className="sq" aria-hidden="true" style={cssVars({ "--c": assetClassColor(c.label) })} />
              <span className="n">{c.label}</span>
              <span className="v">{pct1(c.weight)}</span>
            </li>
          ))}
          {rest > 0 ? (
            <li className="gap">
              <span className="sq" aria-hidden="true" />
              <span className="n">Unallocated (to {currency} cash)</span>
              <span className="v">{pct1(rest)}</span>
            </li>
          ) : null}
        </ul>

        <h3>Checks</h3>
        <ul className="checks">
          {list.map((c) => (
            <li key={c.id}>
              <Icon name={TONE_ICON[c.tone].icon} className={`icon ${TONE_ICON[c.tone].cls}`} />
              <span className="txt">
                <b>{c.title}</b>
                {c.detail !== undefined ? <span className="sub">{c.detail}</span> : null}
              </span>
            </li>
          ))}
        </ul>

        <h3>Backtest window</h3>
        <dl className="kv">
          <div>
            <dt>Earliest common start</dt>
            <dd>
              {start.date === null ? "Not known yet" : dateShort(start.date)}
              {start.by !== null ? <span className="sub">Limited by {start.by}</span> : null}
            </dd>
          </div>
          <div>
            <dt>History</dt>
            <dd>{years === null ? "Not known yet" : `${years.toFixed(1)} years`}</dd>
          </div>
          <div>
            <dt>Rebalancing</dt>
            <dd>Monthly</dd>
          </div>
          <div>
            <dt>
              <label htmlFor={costId}>Trading cost</label>
              <span className="sub">One way, on turnover</span>
            </dt>
            <dd>
              <span className="cost-in">
                <span className="w">
                  <input
                    id={costId}
                    type="text"
                    inputMode="decimal"
                    autoComplete="off"
                    value={costDraft ?? String(tree.cost_bps)}
                    onFocus={(event) => event.currentTarget.select()}
                    onChange={(event) => {
                      const text = event.target.value;
                      setCostDraft(text);
                      const n = Number(text.replace(",", "."));
                      if (text.trim() !== "" && Number.isFinite(n) && n >= 0 && n <= 1000) onCost(n);
                    }}
                    onBlur={() => setCostDraft(null)}
                  />
                  <span className="u">bps</span>
                </span>
              </span>
            </dd>
          </div>
        </dl>

        <div className="live-actions">
          <button type="button" className="btn-outline" onClick={onNormalise} disabled={!(total > 0) || atHundred}>
            Normalise to 100%
          </button>
          <button type="button" className="btn-outline" onClick={onRemainderToCash} disabled={rest <= 0}>
            Put remainder in USD cash
          </button>
          <button
            type="button"
            className="btn run"
            onClick={onRun}
            disabled={!run.ok || running}
            aria-describedby={noteId}
            aria-busy={running}
          >
            <Icon name="play" />
            {running ? "Running…" : "Run backtest"}
          </button>
        </div>
        <p className={run.ok ? "run-note" : "run-note why"} id={noteId}>
          {run.ok ? NOTE : run.reason}
        </p>
      </section>
    </aside>
  );
}

/** The bar docked at the bottom of a phone screen: the total and Run stay in reach. */
export function RunDock({ tree, running, canRun, onRun }: { tree: PortfolioTree; running: boolean; canRun: boolean; onRun: () => void }) {
  const badge = totalBadge(tree);
  return (
    <div className="run-dock">
      <div className="dock-tot" aria-live="polite">
        <b>{pct1(totalWeight(tree))}</b>
        <span className={badge.tone === "ok" ? "ok" : undefined}>{badge.text}</span>
      </div>
      <button type="button" className="btn" onClick={onRun} disabled={!canRun || running} aria-busy={running}>
        <Icon name="play" />
        {running ? "Running…" : "Run backtest"}
      </button>
    </div>
  );
}
