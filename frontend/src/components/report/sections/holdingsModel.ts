/** Pure helpers of the Holdings panel: the tree, the visible rows, the totals and the outcome sentence. */
import type { HoldingRow, HoldingsSection } from "../../../api/types";
import { num, pct, signed } from "../../../format";

export interface HoldingNode {
  row: HoldingRow;
  children: HoldingNode[];
}

/** One line of the table, with the way it is drawn. */
export interface Line {
  node: HoldingNode;
  /** 1 asset class, cash or cost; 2 sub-asset class; 3 holding under a sub-asset class (ARIA level). */
  level: number;
  /** group: asset class; line: sub-asset class or a holding directly under an asset class; inst: holding under a sub-asset class. */
  style: "group" | "line" | "inst" | "cash" | "cost";
  /** The sub-asset class has more than one holding, which show below it. */
  multi: boolean;
  /** Only asset classes with members can be folded. */
  foldable: boolean;
  /** Holdings below the row (a holding counts itself as zero). */
  holdings: number;
  /** A sub-asset class with a single holding shows the ticker of that holding on its sub-line. */
  single: HoldingRow | null;
  /** Id of the asset class the row sits in, for the colour. */
  rootId: string;
}

/** The rows as a forest, in the order of `section.rows` (a group comes before its members). */
export function buildTree(rows: readonly HoldingRow[]): HoldingNode[] {
  const byId = new Map<string, HoldingNode>();
  const roots: HoldingNode[] = [];
  for (const row of rows) {
    const node: HoldingNode = { row, children: [] };
    byId.set(row.id, node);
    const parent = row.parent_id === null ? undefined : byId.get(row.parent_id);
    if (parent) parent.children.push(node);
    else roots.push(node);
  }
  return roots;
}

function holdingCount(node: HoldingNode): number {
  return node.children.reduce((n, c) => n + (c.row.kind === "holding" ? 1 : holdingCount(c)), 0);
}

/** The asset class rows (groups at the top), then the cash and cost rows of the section. */
export function tops(roots: readonly HoldingNode[]): { classes: HoldingNode[]; plain: HoldingNode[] } {
  return {
    classes: roots.filter((n) => n.row.kind === "group"),
    plain: roots.filter((n) => n.row.kind !== "group"),
  };
}

/** The visible lines of the tree (asset classes in `folded` hide their members), in table order. */
export function treeLines(classes: readonly HoldingNode[], folded: ReadonlySet<string>): Line[] {
  const out: Line[] = [];
  const walk = (node: HoldingNode, level: number, rootId: string) => {
    const holdings = holdingCount(node);
    const only = node.children.length === 1 ? node.children[0] : undefined;
    const single = level === 2 && only?.row.kind === "holding" ? only.row : null;
    const style = level === 1 ? "group" : level === 2 ? "line" : "inst";
    out.push({
      node,
      level,
      style,
      multi: level === 2 && node.children.length > 0 && single === null,
      foldable: level === 1 && node.children.length > 0,
      holdings,
      single,
      rootId,
    });
    if (single !== null) return;
    if (level === 1 && folded.has(node.row.id)) return;
    for (const child of node.children) walk(child, level + 1, rootId);
  };
  for (const root of classes) walk(root, 1, root.row.id);
  return out;
}

export function holdingsText(n: number): string {
  return `${n} ${n === 1 ? "holding" : "holdings"}`;
}

const sum = (rows: readonly HoldingNode[], pick: (r: HoldingRow) => number | null): number =>
  rows.reduce((total, n) => total + (pick(n.row) ?? 0), 0);

export interface Totals {
  target: number;
  end: number;
  /** Net return of the portfolio over the window (the section's own figure). */
  total_return: number;
  /** Sum of the risk shares of the top rows; null when no share is defined. */
  risk: number | null;
}

export function totals(section: HoldingsSection, roots: readonly HoldingNode[]): Totals {
  return {
    target: sum(roots, (r) => r.target_weight),
    end: sum(roots, (r) => r.end_weight),
    total_return: section.total_return,
    risk: section.risk_share_reason !== null ? null : sum(roots, (r) => r.risk_share),
  };
}

/** Weight as a percentage with one decimal: 0.595 is "59.5%". */
export function weight(x: number | null): string {
  return x === null ? "–" : pct(x, 1, false);
}

/** Return in percentage points of the starting value: "+25.8", "−0.7". */
export function points(x: number): string {
  return signed(x * 100, 1);
}

/** Figures of the outcome sentence in points: whole numbers from 10 points of total return up, else one decimal. */
function pointsText(x: number, digits: number): string {
  return num(x * 100, digits);
}

/**
 * "Equities gave 26 of the 33 points of return and 72% of the risk." The asset class is the one with
 * the largest contribution. Null when the section has no asset class. When the portfolio did not
 * gain, or the leader did not, the sentence names the leader's points without a share of the total.
 */
export function outcomeSentence(section: HoldingsSection, classes: readonly HoldingNode[]): string | null {
  const top = [...classes].sort((a, b) => b.row.contribution - a.row.contribution)[0];
  if (top === undefined) return null;
  const total = section.total_return;
  const digits = Math.abs(total) >= 0.1 ? 0 : 1;
  const risk =
    section.risk_share_reason === null && top.row.risk_share !== null
      ? ` and ${pct(top.row.risk_share, 0, false)} of the risk`
      : "";
  if (total > 0 && top.row.contribution > 0) {
    return `${top.row.label} gave ${pointsText(top.row.contribution, digits)} of the ${pointsText(total, digits)} points of return${risk}.`;
  }
  return `The portfolio returned ${points(total)} points. ${top.row.label} did best with ${points(top.row.contribution)} points${risk}.`;
}

export const HOLDINGS_HELP =
  "Return is in percentage points (pp) of the starting value, and the lines add up to the portfolio's total return. Risk share is each line's part of the portfolio's total risk; the shares add up to 100%. Target is the weight you set, end is the weight at the end of the period.";

export const HOLDINGS_HOW =
  "Each holding's return is linked through the rebalances, so the contributions add up exactly to the total return. Group rows are the sums of their holdings. Cash and cost are shown on their own rows and are not part of any asset class. Risk share splits the portfolio's volatility by holding, using each holding's weight and how it moves with the rest of the portfolio.";
