/**
 * The portfolio tree: the JSON shape shared with the backend. This module mirrors
 * `backend/factordesk/api/portfolio_models.py`, rule for rule.
 *
 *   {version: 1, name, cost_bps, root: {id, kind: "group", label, children: [asset class groups]}}
 *
 * Level 1 is an asset class group, level 2 a sub-asset class group (with a `library_id`), level 3
 * an instrument. Weights exist only on instruments and are decimal fractions (0.25 is 25%).
 * Group totals are computed (`rollUp`) and never stored.
 */

export const TREE_VERSION = 1;
export const MAX_INSTRUMENTS = 50;
export const MAX_COST_BPS = 1000;
/** Library id of the USD cash line: the unallocated remainder goes there. */
export const USD_CASH_LIBRARY_ID = "cash_usd";
/** Weights may add up to at most `1 + WEIGHT_TOLERANCE` (same constant as the backtest). */
export const WEIGHT_TOLERANCE = 1e-9;

export type InstrumentKind = "holding" | "cash";

export interface Instrument {
  id: string;
  kind: InstrumentKind;
  /** The Yahoo symbol; null for the cash leaf and for a line with no proxy yet. */
  ticker: string | null;
  label: string;
  /** Target weight as a decimal fraction. */
  weight: number;
}

export interface SubAssetClassGroup {
  id: string;
  kind: "group";
  label: string;
  /** The line of the Asset Class Library this group comes from. */
  library_id: string;
  children: Instrument[];
}

export interface AssetClassGroup {
  id: string;
  kind: "group";
  label: string;
  children: SubAssetClassGroup[];
}

export interface RootGroup {
  id: string;
  kind: "group";
  label: string;
  children: AssetClassGroup[];
}

export interface PortfolioTree {
  version: 1;
  name: string;
  cost_bps: number;
  root: RootGroup;
}

/** The part of a library line the tree functions need (the generated `LibraryLine` fits it). */
export interface LibraryLineLike {
  id: string;
  asset_class: string;
  sub_asset_class: string;
  /** A ticker, "RF" for the risk-free rate, or null when there is no proxy yet. */
  proxy: string | null;
  proxy_kind: "etf" | "risk_free" | "listed_proxy" | "none";
}

const TICKER_RE = /^[A-Za-z0-9.^=-]{1,12}$/;
const ID_RE = /^[A-Za-z0-9_.:-]{1,64}$/;

// ----------------------------------------------------------------------------------- helpers

function slug(text: string): string {
  return (
    text
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "_")
      .replace(/^_+|_+$/g, "") || "x"
  );
}

function allIds(tree: PortfolioTree): Set<string> {
  const ids = new Set<string>([tree.root.id]);
  for (const ac of tree.root.children) {
    ids.add(ac.id);
    for (const sub of ac.children) {
      ids.add(sub.id);
      for (const inst of sub.children) ids.add(inst.id);
    }
  }
  return ids;
}

function freshId(tree: PortfolioTree, prefix: string): string {
  const used = allIds(tree);
  for (let n = 1; ; n += 1) {
    const id = `${prefix}_${n}`;
    if (!used.has(id)) return id;
  }
}

/** All instruments in tree order. */
export function instruments(tree: PortfolioTree): Instrument[] {
  return tree.root.children.flatMap((ac) => ac.children.flatMap((sub) => sub.children));
}

/** The sum of all weights. */
export function totalWeight(tree: PortfolioTree): number {
  return instruments(tree).reduce((sum, inst) => sum + inst.weight, 0);
}

/** The unallocated weight; 0 when within tolerance of 100% or over it. */
export function remainder(tree: PortfolioTree): number {
  const rest = 1 - totalWeight(tree);
  return rest > WEIGHT_TOLERANCE ? rest : 0;
}

function mapSubs(
  tree: PortfolioTree,
  fn: (sub: SubAssetClassGroup) => SubAssetClassGroup,
): PortfolioTree {
  return {
    ...tree,
    root: {
      ...tree.root,
      children: tree.root.children.map((ac) => ({ ...ac, children: ac.children.map(fn) })),
    },
  };
}

function mapInstruments(tree: PortfolioTree, fn: (inst: Instrument) => Instrument): PortfolioTree {
  return mapSubs(tree, (sub) => ({ ...sub, children: sub.children.map(fn) }));
}

function findSub(tree: PortfolioTree, test: (sub: SubAssetClassGroup) => boolean) {
  return tree.root.children.flatMap((ac) => ac.children).find(test);
}

// ------------------------------------------------------------------------------------ queries

/**
 * The computed total of every node, by id: the own weight of an instrument, and for a group the
 * sum of its instruments. Nothing is stored in the tree, so a group total always equals the sum
 * of its leaves.
 */
export function rollUp(tree: PortfolioTree): Record<string, number> {
  const totals: Record<string, number> = {};
  let all = 0;
  for (const ac of tree.root.children) {
    let acTotal = 0;
    for (const sub of ac.children) {
      let subTotal = 0;
      for (const inst of sub.children) {
        totals[inst.id] = inst.weight;
        subTotal += inst.weight;
      }
      totals[sub.id] = subTotal;
      acTotal += subTotal;
    }
    totals[ac.id] = acTotal;
    all += acTotal;
  }
  totals[tree.root.id] = all;
  return totals;
}

// ----------------------------------------------------------------------------------- edits
// Every edit returns a new tree and never changes its argument.

/** A tree with no lines. */
export function emptyTree(name: string, costBps = 0): PortfolioTree {
  return {
    version: TREE_VERSION,
    name,
    cost_bps: costBps,
    root: { id: "root", kind: "group", label: name, children: [] },
  };
}

function defaultInstrument(line: LibraryLineLike, id: string): Instrument {
  if (line.proxy_kind === "risk_free") {
    return { id, kind: "cash", ticker: null, label: "Risk-free rate", weight: 0 };
  }
  if (line.proxy === null) {
    return { id, kind: "holding", ticker: null, label: "No proxy yet", weight: 0 };
  }
  return { id, kind: "holding", ticker: line.proxy, label: line.proxy, weight: 0 };
}

/**
 * Add a line of the library with its proxy at weight 0, under its asset class group (created at
 * the end when missing). A line already in the tree is not added twice: the tree comes back as is.
 */
export function addLine(tree: PortfolioTree, line: LibraryLineLike): PortfolioTree {
  if (findSub(tree, (sub) => sub.library_id === line.id) !== undefined) return tree;
  const sub: SubAssetClassGroup = {
    id: `sub_${line.id}`,
    kind: "group",
    label: line.sub_asset_class,
    library_id: line.id,
    children: [defaultInstrument(line, freshId(tree, `${line.id}_i`))],
  };
  const acId = `ac_${slug(line.asset_class)}`;
  const exists = tree.root.children.some((ac) => ac.id === acId);
  const children = exists
    ? tree.root.children.map((ac) =>
        ac.id === acId ? { ...ac, children: [...ac.children, sub] } : ac,
      )
    : [
        ...tree.root.children,
        { id: acId, kind: "group" as const, label: line.asset_class, children: [sub] },
      ];
  return { ...tree, root: { ...tree.root, children } };
}

/** Add an instrument at weight 0 under a sub-asset class group; unchanged when the group is unknown. */
export function addInstrument(
  tree: PortfolioTree,
  subId: string,
  ticker: string,
  label: string = ticker,
): PortfolioTree {
  const sub = findSub(tree, (s) => s.id === subId);
  if (sub === undefined) return tree;
  const inst: Instrument = {
    id: freshId(tree, `${sub.library_id}_i`),
    kind: "holding",
    ticker,
    label,
    weight: 0,
  };
  return mapSubs(tree, (s) => (s.id === subId ? { ...s, children: [...s.children, inst] } : s));
}

/**
 * Give an instrument another ticker (it becomes a holding) and keep its weight. A null ticker
 * means "no proxy", so the weight is set to 0.
 */
export function swapInstrument(
  tree: PortfolioTree,
  instrumentId: string,
  ticker: string | null,
  label: string = ticker ?? "No proxy yet",
): PortfolioTree {
  return mapInstruments(tree, (inst) =>
    inst.id === instrumentId
      ? { ...inst, kind: "holding", ticker, label, weight: ticker === null ? 0 : inst.weight }
      : inst,
  );
}

/** Change the label of any node, the root included. */
export function rename(tree: PortfolioTree, nodeId: string, label: string): PortfolioTree {
  return {
    ...tree,
    root: {
      ...tree.root,
      label: tree.root.id === nodeId ? label : tree.root.label,
      children: tree.root.children.map((ac) => ({
        ...ac,
        label: ac.id === nodeId ? label : ac.label,
        children: ac.children.map((sub) => ({
          ...sub,
          label: sub.id === nodeId ? label : sub.label,
          children: sub.children.map((inst) => (inst.id === nodeId ? { ...inst, label } : inst)),
        })),
      })),
    },
  };
}

/**
 * Remove an instrument, a sub-asset class group (with its instruments) or an asset class group.
 * An asset class group that this call leaves without lines is removed too. The root cannot be
 * removed.
 */
export function remove(tree: PortfolioTree, nodeId: string): PortfolioTree {
  const children = tree.root.children
    .filter((ac) => ac.id !== nodeId)
    .map((ac) => ({
      before: ac.children.length,
      ac: {
        ...ac,
        children: ac.children
          .filter((sub) => sub.id !== nodeId)
          .map((sub) => ({ ...sub, children: sub.children.filter((inst) => inst.id !== nodeId) })),
      },
    }))
    .filter(({ before, ac }) => !(before > 0 && ac.children.length === 0))
    .map(({ ac }) => ac);
  return { ...tree, root: { ...tree.root, children } };
}

/** Set the weight of an instrument (decimal fraction). A non-finite value changes nothing. */
export function setWeight(
  tree: PortfolioTree,
  instrumentId: string,
  weight: number,
): PortfolioTree {
  if (!Number.isFinite(weight)) return tree;
  return mapInstruments(tree, (inst) => (inst.id === instrumentId ? { ...inst, weight } : inst));
}

/**
 * Scale every weight so that they add up to 100%. A tree with no weight at all comes back as is
 * (there is nothing to scale).
 */
export function normalise(tree: PortfolioTree): PortfolioTree {
  const total = totalWeight(tree);
  if (!(total > 0)) return tree;
  return mapInstruments(tree, (inst) => ({ ...inst, weight: inst.weight / total }));
}

/**
 * Put the unallocated weight into USD cash: the first cash instrument of the USD cash line, which
 * is added from `library` when the tree has no such line. A tree at 100% (or over) comes back as is.
 */
export function remainderToCash(
  tree: PortfolioTree,
  library: readonly LibraryLineLike[],
): PortfolioTree {
  const rest = remainder(tree);
  if (rest <= 0) return tree;
  let next = tree;
  let sub = findSub(next, (s) => s.library_id === USD_CASH_LIBRARY_ID);
  if (sub === undefined) {
    const line = library.find((l) => l.id === USD_CASH_LIBRARY_ID);
    if (line === undefined) return tree;
    next = addLine(next, line);
    sub = findSub(next, (s) => s.library_id === USD_CASH_LIBRARY_ID);
    if (sub === undefined) return tree;
  }
  const subId = sub.id;
  const cash = sub.children.find((inst) => inst.kind === "cash");
  if (cash === undefined) {
    const inst: Instrument = {
      id: freshId(next, `${USD_CASH_LIBRARY_ID}_i`),
      kind: "cash",
      ticker: null,
      label: "Risk-free rate",
      weight: rest,
    };
    return mapSubs(next, (s) => (s.id === subId ? { ...s, children: [...s.children, inst] } : s));
  }
  return mapInstruments(next, (inst) =>
    inst.id === cash.id ? { ...inst, weight: inst.weight + rest } : inst,
  );
}

// ------------------------------------------------------------------------------- validation

export interface Validation {
  /** Reasons the tree cannot be run. Empty when it can. */
  errors: string[];
  /** Plain-words notices for a runnable tree. */
  notices: string[];
}

function pct(x: number): string {
  return `${(x * 100).toFixed(2)}%`;
}

/**
 * The same rules as the backend model (`portfolio_models.py`): weights from 0 to 1, a total of at
 * most 100% (the remainder is held in USD cash, with a notice), at most 50 instruments, no weight
 * on a holding without a ticker, no ticker on cash, unique ids. The same ticker may appear in two
 * lines. The currency of a ticker is not checked here: the run checks it.
 */
export function validate(tree: PortfolioTree): Validation {
  const errors: string[] = [];
  const notices: string[] = [];
  if (tree.version !== TREE_VERSION) errors.push(`version must be ${TREE_VERSION}`);
  if (tree.name.length < 1 || tree.name.length > 80) errors.push("name must be 1 to 80 characters");
  if (!Number.isFinite(tree.cost_bps) || tree.cost_bps < 0 || tree.cost_bps > MAX_COST_BPS) {
    errors.push(`cost_bps must be between 0 and ${MAX_COST_BPS}`);
  }
  const seen = new Set<string>();
  const checkNode = (id: string, label: string): void => {
    if (!ID_RE.test(id)) errors.push(`id ${JSON.stringify(id)} is not a valid id`);
    if (seen.has(id)) errors.push(`id ${JSON.stringify(id)} is used twice`);
    seen.add(id);
    if (label.length < 1 || label.length > 80) {
      errors.push(`label of ${JSON.stringify(id)} must be 1 to 80 characters`);
    }
  };
  checkNode(tree.root.id, tree.root.label);
  for (const ac of tree.root.children) {
    checkNode(ac.id, ac.label);
    for (const sub of ac.children) {
      checkNode(sub.id, sub.label);
      if (!ID_RE.test(sub.library_id)) {
        errors.push(`group ${JSON.stringify(sub.id)} has an invalid library_id`);
      }
      for (const inst of sub.children) {
        checkNode(inst.id, inst.label);
        const who = JSON.stringify(inst.id);
        if (!Number.isFinite(inst.weight)) {
          errors.push(`weight of instrument ${who} must be a finite number`);
        } else if (inst.weight < 0) {
          errors.push(`weight of instrument ${who} must be 0 or more`);
        } else if (inst.weight > 1) {
          errors.push(`weight of instrument ${who} must be 1 or less`);
        }
        if (inst.kind === "cash" && inst.ticker !== null) {
          errors.push(`cash instrument ${who} cannot have a ticker`);
        }
        if (inst.ticker !== null && !TICKER_RE.test(inst.ticker)) {
          errors.push(`instrument ${who} has an invalid ticker`);
        }
        if (inst.kind === "holding" && inst.ticker === null && inst.weight > 0) {
          errors.push(`instrument ${who} has no proxy yet, so it cannot take a weight`);
        }
      }
    }
  }
  const count = instruments(tree).length;
  if (count > MAX_INSTRUMENTS) {
    errors.push(`at most ${MAX_INSTRUMENTS} instruments are allowed, got ${count}`);
  }
  const total = totalWeight(tree);
  if (total > 1 + WEIGHT_TOLERANCE) {
    errors.push(`the weights add up to ${pct(total)}, which is more than 100%`);
  }
  const rest = remainder(tree);
  if (rest > 0) {
    notices.push(`${pct(rest)} is not allocated; it is held in USD cash.`);
  }
  return { errors, notices };
}
