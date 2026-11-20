import { useState } from "react";
import type { ReactNode } from "react";
import type { HoldingRow, HoldingsSection } from "../../../api/types";
import { dateLong } from "../../../format";
import { assetClassColor, cssVars } from "../../portfolio/assetClass";
import { Icon } from "../../shell/icons";
import { Panel } from "../Panel";
import type { ReportPanelProps } from "../types";
import "../../../styles/portfolio.css";
import "./HoldingsPanel.css";
import {
  HOLDINGS_HELP,
  HOLDINGS_HOW,
  buildTree,
  holdingsText,
  outcomeSentence,
  points,
  rowId,
  tops,
  totals,
  treeLines,
  weight,
} from "./holdingsModel";
import type { Line } from "./holdingsModel";

export const TITLE = "Holdings";

function signClass(x: number): string {
  return x > 0 ? "num-pos" : x < 0 ? "num-neg" : "";
}

type Figures = Pick<HoldingRow, "target_weight" | "end_weight" | "contribution" | "risk_share">;

interface CellsProps {
  figures: Figures;
  /** The section has no risk shares: show a dash. */
  noRisk: boolean;
  color: string;
}

/** The four figure cells of a row: target, end, return and risk share with its bar. */
function Cells({ figures, noRisk, color }: CellsProps) {
  const { target_weight: t, end_weight: e, contribution: c } = figures;
  const r = noRisk ? null : figures.risk_share;
  return (
    <>
      <div role="cell" className="tgt" data-l="Target">
        <span className={t === null ? "hn dash" : "hn"}>{weight(t)}</span>
      </div>
      <div role="cell" className="end" data-l="End">
        <span className={e === null ? "hn dash" : "hn"}>{weight(e)}</span>
      </div>
      <div role="cell" className="con" data-l="Return (pp)">
        <span className={`hn ${signClass(c)}`.trim()}>{points(c)}</span>
      </div>
      <div role="cell" className="risk" data-l="Risk share">
        <div className="rs">
          <span className={r === null ? "hn dash" : "hn"}>{r === null ? "–" : weight(r)}</span>
          {r === null ? null : (
            <div
              className="sbar"
              aria-hidden="true"
              style={cssVars({ "--p": `${Math.min(100, Math.max(0, r * 100))}%`, "--c": color })}
            >
              <i />
            </div>
          )}
        </div>
      </div>
    </>
  );
}

interface TreeRowProps {
  line: Line;
  open: boolean;
  onToggle: () => void;
  color: string;
  noRisk: boolean;
}

function TreeRow({ line, open, onToggle, color, noRisk }: TreeRowProps) {
  const { row } = line.node;
  const only = line.single;
  let sub: ReactNode = null;
  if (line.style === "inst") {
    sub = row.label;
  } else if (only !== null) {
    // A sub-asset class with one holding is one row: the ticker goes on its sub-line.
    sub = (
      <>
        <b>{only.ticker ?? only.label}</b>
        {only.ticker !== null && only.label !== row.label ? ` ${only.label}` : ""}
      </>
    );
  } else if (line.multi) {
    sub = holdingsText(line.holdings);
  } else if (row.kind === "holding") {
    sub = <b>{row.ticker ?? ""}</b>;
  }
  const name = line.style === "inst" ? (row.ticker ?? row.label) : row.label;
  return (
    <div
      role="row"
      id={rowId(row.id)}
      className={`t-row ${line.style}${line.multi ? " multi" : ""}`}
      data-row={row.id}
    >
      <div role="rowheader" className="label">
        {line.style === "group" ? (
          <>
            {line.foldable ? (
              <button
                type="button"
                className="caret"
                aria-expanded={open}
                aria-controls={line.controls.join(" ")}
                aria-label={row.label}
                onClick={onToggle}
              >
                <Icon name="caret" />
              </button>
            ) : null}
            <span className="key-sq" aria-hidden="true" style={cssVars({ "--c": color })} />
            <span className="nm">
              {row.label} <span className="cnt">{holdingsText(line.holdings)}</span>
            </span>
          </>
        ) : (
          <div className="txt">
            <span className="nm">{name}</span>
            {sub === null ? null : <span className="sb">{sub}</span>}
          </div>
        )}
      </div>
      <Cells figures={row} noRisk={noRisk} color={color} />
    </div>
  );
}

/** What a cash row holds: in the euro view the unallocated weight is euro cash and USD cash is apart. */
function cashNote(row: HoldingRow, eurCash: boolean): string {
  if (row.id === "usd_cash") return "USD cash instruments, converted to euros";
  if (row.id === "cash" && eurCash) return "Any unallocated weight, held as euro cash";
  return "USD cash instruments and any unallocated weight";
}

function PlainRow({ row, noRisk, eurCash }: { row: HoldingRow; noRisk: boolean; eurCash: boolean }) {
  const cash = row.kind === "cash";
  const color = assetClassColor("Cash");
  return (
    <div role="row" id={rowId(row.id)} className={`t-row plain-row${cash ? " sep" : ""}`}>
      <div role="rowheader" className="label">
        {cash ? (
          <span className="key-sq" aria-hidden="true" style={cssVars({ "--c": color })} />
        ) : (
          <span className="key-ring" aria-hidden="true" />
        )}
        <div className="txt">
          <span className="nm">{row.label}</span>
          <span className="sb">
            {cash ? cashNote(row, eurCash) : "Trading cost of the rebalances"}
          </span>
        </div>
      </div>
      <Cells figures={row} noRisk={noRisk} color={color} />
    </div>
  );
}

function Loaded({ section, eurCash }: { section: HoldingsSection; eurCash: boolean }) {
  const roots = buildTree(section.rows);
  const { classes, plain } = tops(roots);
  const [folded, setFolded] = useState<ReadonlySet<string>>(new Set());
  const foldable = classes.filter((n) => n.children.length > 0).map((n) => n.row.id);
  const noRisk = section.risk_share_reason !== null;
  const sums = totals(section, roots);
  const lines = treeLines(classes, folded);
  const colorOf = (rootId: string) => assetClassColor(classes.find((n) => n.row.id === rootId)?.row.label ?? "");
  const toggle = (id: string) =>
    setFolded((prev) => {
      const next = new Set(prev);
      if (!next.delete(id)) next.add(id);
      return next;
    });
  const tools = (
    <div className="hold-tools">
      <button type="button" className="textbtn" onClick={() => setFolded(new Set())}>
        Expand all
      </button>
      <button type="button" className="textbtn" onClick={() => setFolded(new Set(foldable))}>
        Collapse all
      </button>
    </div>
  );
  return (
    <Panel
      id="holdings"
      title={TITLE}
      question="What did each holding add to the result, and how much risk did it carry?"
      outcome={outcomeSentence(section, classes)}
      legend={tools}
      footnote={HOLDINGS_HELP}
      how={HOLDINGS_HOW}
    >
      <div role="table" className="tree" aria-label="Holdings by asset class">
        <div role="row" className="t-head">
          <span role="columnheader" className="hl">
            Holding
          </span>
          <span role="columnheader" className="r">
            Target
          </span>
          <span role="columnheader" className="r">
            End
          </span>
          <span role="columnheader" className="r">
            Return (pp)
          </span>
          <span role="columnheader" className="hl">
            Risk share
          </span>
        </div>
        {lines.map((line) => (
          <TreeRow
            key={line.node.row.id}
            line={line}
            open={!folded.has(line.node.row.id)}
            onToggle={() => toggle(line.node.row.id)}
            color={colorOf(line.rootId)}
            noRisk={noRisk}
          />
        ))}
        {plain.map((node) => (
          <PlainRow key={node.row.id} row={node.row} noRisk={noRisk} eurCash={eurCash} />
        ))}
        <div role="row" className="t-row total">
          <div role="rowheader" className="label">
            <div className="txt">
              <span className="nm">Total</span>
            </div>
          </div>
          <Cells
            figures={{
              target_weight: sums.target,
              end_weight: sums.end,
              contribution: sums.total_return,
              risk_share: sums.risk,
            }}
            noRisk={noRisk}
            color="var(--ink)"
          />
        </div>
      </div>
      <p className="total-note">
        Total return after cost: <b className={signClass(sums.total_return)}>{`${points(sums.total_return)}%`}</b> over{" "}
        {dateLong(section.window_start)} to {dateLong(section.window_end)}
      </p>
      {section.risk_share_reason ? <p className="foot-note">{section.risk_share_reason}</p> : null}
    </Panel>
  );
}

/**
 * Panel of the `holdings` section (what each holding, group, cash and trading cost did for a
 * portfolio; backend `report/sections/holdings.py`). Registered in `panelRegistry.ts` at position
 * 420, after Growth of 100. Renders nothing while the section is absent, as for a ticker report.
 */
export function HoldingsPanel({ report }: ReportPanelProps) {
  const s = report.holdings;
  if (s == null) return null;
  return <Loaded section={s} eurCash={report.portfolio_backtest?.unallocated_currency === "EUR"} />;
}
