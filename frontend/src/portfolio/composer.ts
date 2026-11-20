/**
 * Pure helpers of the portfolio composer: weight text and nudging, the numbers of the live panel
 * (class totals, checks, earliest common start) and a few tree edits the screen needs on top of
 * `tree.ts`. No React and no I/O, so every rule here has a unit test.
 */
import type { LibraryLine } from "../api/types";
import { addLine, instruments, remove, rollUp, setWeight, totalWeight, validate } from "./tree";
import type { PortfolioTree, SubAssetClassGroup } from "./tree";

/** The step of the arrow keys on a weight input, in percentage points. */
export const NUDGE_STEP = 0.5;
/** A proxy whose first price is after this year is a "short history". */
export const LATE_YEAR = 2010;

// ------------------------------------------------------------------------------------ weights

/** Parse typed percent text ("12", "12.5", "12,5", "12 %") to a decimal fraction; null when it is not a number from 0 to 100. */
export function parsePercent(text: string): number | null {
  const cleaned = text.trim().replace(/%$/, "").trim().replace(",", ".");
  if (cleaned === "" || !/^\d*\.?\d*$/.test(cleaned) || cleaned === ".") return null;
  const pct = Number(cleaned);
  if (!Number.isFinite(pct) || pct < 0 || pct > 100) return null;
  return Math.round(pct * 1e6) / 1e8;
}

/** A weight as percent text: one decimal ("24.0"), two when the weight needs them ("33.33"). */
export function formatPercent(weight: number): string {
  const pct = weight * 100;
  const one = pct.toFixed(1);
  return Math.abs(Number(one) - pct) < 1e-9 ? one : pct.toFixed(2);
}

/** The weight moved by `steps` x 0.5 percentage points, kept between 0 and 100% and free of float drift. */
export function nudgeWeight(weight: number, steps: number): number {
  const pct = Math.round(weight * 1e4) / 100 + steps * NUDGE_STEP;
  return Math.min(100, Math.max(0, Math.round(pct * 100) / 100)) / 100;
}

/** Nudge one instrument of a tree (an unknown id changes nothing). */
export function nudge(tree: PortfolioTree, instrumentId: string, steps: number): PortfolioTree {
  const inst = instruments(tree).find((i) => i.id === instrumentId);
  return inst === undefined ? tree : setWeight(tree, instrumentId, nudgeWeight(inst.weight, steps));
}

// ----------------------------------------------------------------------------------- the library

export function libraryById(library: readonly LibraryLine[]): Map<string, LibraryLine> {
  return new Map(library.map((line) => [line.id, line]));
}

/** The year of an ISO date, or null. */
export function yearOf(isoDate: string | null | undefined): number | null {
  if (!isoDate) return null;
  const year = Number(isoDate.slice(0, 4));
  return Number.isInteger(year) ? year : null;
}

/** True when the proxy started after 2010 (shown in amber, "short history" in the picker). */
export function isShortHistory(line: Pick<LibraryLine, "first_date">): boolean {
  const year = yearOf(line.first_date);
  return year !== null && year > LATE_YEAR;
}

// --------------------------------------------------------------------------------- tree edits

/** Add a library line with a weight (the preset builder and the tests use it). */
export function addLineWithWeight(tree: PortfolioTree, line: LibraryLine, weight: number): PortfolioTree {
  const added = addLine(tree, line);
  if (added === tree) return tree;
  const sub = added.root.children.flatMap((ac) => ac.children).find((s) => s.library_id === line.id);
  const first = sub?.children[0];
  return first === undefined ? added : setWeight(added, first.id, weight);
}

/**
 * Remove a node. A sub-asset class that would be left without instruments is removed with its last
 * instrument, so the tree never holds an empty line.
 */
export function removeNode(tree: PortfolioTree, nodeId: string): PortfolioTree {
  const owner = tree.root.children
    .flatMap((ac) => ac.children)
    .find((sub) => sub.children.length === 1 && sub.children[0]?.id === nodeId);
  return remove(tree, owner === undefined ? nodeId : owner.id);
}

/** Rename the portfolio: the tree name and the label of its root. */
export function renameTree(tree: PortfolioTree, name: string): PortfolioTree {
  return { ...tree, name, root: { ...tree.root, label: name } };
}

/** The trading cost in basis points, kept between 0 and the maximum. */
export function withCost(tree: PortfolioTree, bps: number): PortfolioTree {
  return Number.isFinite(bps) ? { ...tree, cost_bps: Math.min(1000, Math.max(0, bps)) } : tree;
}

// -------------------------------------------------------------------------------- the live panel

export interface ClassTotal {
  id: string;
  label: string;
  weight: number;
  lines: number;
}

/** The asset classes with their totals, largest first (ties keep the tree order). */
export function classTotals(tree: PortfolioTree): ClassTotal[] {
  const totals = rollUp(tree);
  return tree.root.children
    .map((ac, index) => ({ index, item: { id: ac.id, label: ac.label, weight: totals[ac.id] ?? 0, lines: ac.children.length } }))
    .sort((a, b) => b.item.weight - a.item.weight || a.index - b.index)
    .map(({ item }) => item);
}

export function lineCount(tree: PortfolioTree): number {
  return tree.root.children.reduce((n, ac) => n + ac.children.length, 0);
}

export type CheckTone = "warn" | "ok" | "info" | "error";

export interface Check {
  id: string;
  tone: CheckTone;
  title: string;
  detail?: string;
}

export interface StartInfo {
  /** ISO date of the earliest common start, or null when no weighted line has a known start. */
  date: string | null;
  /** The ticker that sets it. */
  by: string | null;
}

interface Leaf {
  sub: SubAssetClassGroup;
  instrumentId: string;
  ticker: string | null;
  label: string;
  weight: number;
  /** The library line when this leaf still holds the library proxy; null for a swapped or added ticker. */
  line: LibraryLine | null;
  kind: "holding" | "cash";
}

function leaves(tree: PortfolioTree, library: ReadonlyMap<string, LibraryLine>): Leaf[] {
  return tree.root.children.flatMap((ac) =>
    ac.children.flatMap((sub) =>
      sub.children.map((inst) => {
        const line = library.get(sub.library_id) ?? null;
        const isProxy =
          line !== null &&
          (inst.kind === "cash" ? line.proxy_kind === "risk_free" : inst.ticker !== null && inst.ticker === line.proxy);
        return {
          sub,
          instrumentId: inst.id,
          ticker: inst.ticker,
          label: inst.label,
          weight: inst.weight,
          line: isProxy ? line : null,
          kind: inst.kind,
        };
      }),
    ),
  );
}

/** The latest first date among the leaves with a weight above 0 (a 0% line never shortens the window). */
export function earliestCommonStart(tree: PortfolioTree, library: ReadonlyMap<string, LibraryLine>): StartInfo {
  let best: StartInfo = { date: null, by: null };
  for (const leaf of leaves(tree, library)) {
    if (!(leaf.weight > 0) || leaf.line === null || leaf.line.first_date === null) continue;
    if (best.date === null || leaf.line.first_date > best.date) {
      best = { date: leaf.line.first_date, by: leaf.ticker ?? leaf.line.proxy ?? leaf.label };
    }
  }
  return best;
}

function joinNames(names: string[]): string {
  return names.join(", ");
}

/** The checks of the live panel, in reading order. */
export function checks(tree: PortfolioTree, library: ReadonlyMap<string, LibraryLine>, currency: "USD" | "EUR" = "USD"): Check[] {
  const out: Check[] = [];
  const all = leaves(tree, library);
  const weighted = all.filter((l) => l.weight > 0);
  const total = totalWeight(tree);
  const { errors } = validate(tree);

  if (all.length === 0) {
    out.push({ id: "empty", tone: "info", title: "No lines yet.", detail: "Add a sub-asset class from the library to start." });
  } else if (weighted.length === 0) {
    out.push({ id: "no-weight", tone: "info", title: "No weight yet.", detail: "Give at least one line a weight above 0%." });
  }
  const over = total > 1 + 1e-9;
  if (over) {
    out.push({
      id: "over",
      tone: "error",
      title: `Weights add up to ${(total * 100).toFixed(1)}%.`,
      detail: "That is more than 100%. Lower a weight, or use Normalise to 100%.",
    });
  } else if (total > 0 && 1 - total > 1e-9) {
    out.push({
      id: "unallocated",
      tone: "warn",
      title: `Unallocated ${((1 - total) * 100).toFixed(1)}% to ${currency} cash.`,
      detail: "Held as cash in the backtest. Move it into a line to invest it.",
    });
  }
  for (const message of errors) {
    if (message.startsWith("the weights add up")) continue;
    out.push({ id: `error-${message}`, tone: "error", title: message });
  }
  const late = weighted.filter((l) => l.line !== null && isShortHistory(l.line));
  for (const leaf of late) {
    const year = yearOf(leaf.line?.first_date);
    out.push({
      id: `late-${leaf.instrumentId}`,
      tone: "warn",
      title: `${leaf.ticker ?? leaf.label} starts ${year}.`,
      detail: "It sets the common start. Weights of 0% never shorten the window.",
    });
  }
  const listed = weighted.filter((l) => l.line?.proxy_kind === "listed_proxy").map((l) => l.ticker ?? l.label);
  if (listed.length > 0) {
    out.push({
      id: "listed",
      tone: "info",
      title: `${joinNames(listed)}: listed ${listed.length === 1 ? "proxy" : "proxies"}.`,
      detail: "The smoother returns of private assets are not captured.",
    });
  }
  const swapped = all.filter((l) => l.kind === "holding" && l.line === null && l.ticker !== null);
  if (all.length > 0) {
    if (swapped.length === 0) {
      out.push({
        id: "usd",
        tone: "ok",
        title: `All ${all.length} ${all.length === 1 ? "instrument is" : "instruments are"} USD-listed.`,
      });
    } else {
      out.push({
        id: "usd-run",
        tone: "info",
        title: `${joinNames(swapped.map((l) => l.ticker ?? l.label))}: chosen by you.`,
        detail: "The run checks that they are listed in US dollars and when they start.",
      });
    }
  }
  return out;
}

export interface Runnable {
  ok: boolean;
  /** Why not, in one sentence. */
  reason: string | null;
}

/** Whether the tree can be sent: it needs a weight, no rule broken, and a ticker on every weighted line. */
export function runnable(tree: PortfolioTree): Runnable {
  const { errors } = validate(tree);
  if (instruments(tree).length === 0) return { ok: false, reason: "Add a sub-asset class first." };
  if (!(totalWeight(tree) > 0)) return { ok: false, reason: "Give at least one line a weight above 0%." };
  const first = errors[0];
  if (first !== undefined) return { ok: false, reason: `${first.charAt(0).toUpperCase()}${first.slice(1)}.` };
  return { ok: true, reason: null };
}
