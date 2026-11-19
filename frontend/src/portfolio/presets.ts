/**
 * Preset portfolios of the composer: Blank, 60/40, Balanced SAA and Growth. Each one is a list of
 * library lines with a weight in percent, built into a tree with the library's own proxies. The
 * lines of Balanced SAA and Growth all have a proxy that starts before 2010, so a preset never
 * shortens the backtest window much. Every preset stays editable.
 */
import type { LibraryLine } from "../api/types";
import { addLineWithWeight } from "./composer";
import { emptyTree } from "./tree";
import type { PortfolioTree } from "./tree";

export type PresetId = "blank" | "6040" | "saa" | "growth";

interface PresetLine {
  /** The id of a library line. */
  line: string;
  /** Percent of the portfolio. */
  pct: number;
}

export interface Preset {
  id: PresetId;
  label: string;
  lines: readonly PresetLine[];
}

export const PRESETS: readonly Preset[] = [
  { id: "blank", label: "Blank", lines: [] },
  {
    id: "6040",
    label: "60/40",
    lines: [
      { line: "eq_na_large", pct: 60 }, // IVV
      { line: "fi_na_gov", pct: 40 }, // IEF
    ],
  },
  {
    id: "saa",
    label: "Balanced SAA",
    lines: [
      { line: "cash_usd", pct: 2 },
      { line: "fi_na_gov", pct: 10 }, // IEF
      { line: "fi_na_ig", pct: 10 }, // LQD
      { line: "fi_tips", pct: 5 }, // TIP
      { line: "fi_na_hy", pct: 3 }, // HYG
      { line: "eq_na_large", pct: 33 }, // IVV
      { line: "eq_eur_large", pct: 8 }, // IEV
      { line: "eq_japan_pacific", pct: 4 }, // VPL
      { line: "eq_em", pct: 6 }, // EEM
      { line: "eq_usa_small", pct: 4 }, // IJR
      { line: "alt_pe", pct: 4 }, // PSP, a listed proxy
      { line: "alt_real_estate", pct: 6 }, // VNQ, a listed proxy
      { line: "com_gold", pct: 5 }, // GLD
    ],
  },
  {
    id: "growth",
    label: "Growth",
    lines: [
      { line: "eq_na_large", pct: 35 }, // IVV
      { line: "eq_thematic", pct: 10 }, // QQQ
      { line: "eq_usa_small", pct: 8 }, // IJR
      { line: "eq_eur_large", pct: 10 }, // IEV
      { line: "eq_japan_pacific", pct: 5 }, // VPL
      { line: "eq_em", pct: 10 }, // EEM
      { line: "alt_pe", pct: 5 }, // PSP, a listed proxy
      { line: "alt_real_estate", pct: 5 }, // VNQ, a listed proxy
      { line: "fi_na_gov", pct: 5 }, // IEF
      { line: "fi_na_hy", pct: 3 }, // HYG
      { line: "com_gold", pct: 4 }, // GLD
    ],
  },
];

export function presetById(id: PresetId): Preset {
  const found = PRESETS.find((p) => p.id === id);
  if (found === undefined) throw new Error(`unknown preset ${id}`);
  return found;
}

/** The tree of a preset under `name`. A line the library does not have is left out. */
export function buildPreset(id: PresetId, name: string, library: readonly LibraryLine[]): PortfolioTree {
  const byId = new Map(library.map((line) => [line.id, line]));
  let tree = emptyTree(name, 10);
  for (const { line, pct } of presetById(id).lines) {
    const found = byId.get(line);
    if (found !== undefined && found.proxy !== null) tree = addLineWithWeight(tree, found, pct / 100);
  }
  return tree;
}
