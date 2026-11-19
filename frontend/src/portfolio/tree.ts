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
