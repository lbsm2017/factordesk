/** Rows and wording of the World beta panel. */
import type { WorldBetaSection } from "../../../api/types";

export type BetaFit = NonNullable<WorldBetaSection["world"]>;
export type Comparison = NonNullable<WorldBetaSection["comparison"]>;

export interface EuropeRow {
  fit: BetaFit;
  days: number | null;
  proxy: string;
}

const LINES: Record<Comparison, string> = {
  about_the_same: "About the same against the world as against the US market.",
  higher: "Higher against the world than against the US market.",
  lower: "Lower against the world than against the US market.",
};

/** The reading of two 95% intervals: overlap is always "about the same", whatever the point estimates. */
export function compareFits(world: BetaFit, us: BetaFit): Comparison {
  if (world.ci_low <= us.ci_high && us.ci_low <= world.ci_high) return "about_the_same";
  return world.beta > us.beta ? "higher" : "lower";
}

/**
 * The outcome line. The reading is computed from the two intervals whenever both fits are there, so a
 * difference is never claimed from overlapping intervals (DV4.8), even if the category says otherwise;
 * the backend's category is the fallback.
 */
export function outcomeLine(s: WorldBetaSection): string | null {
  const category = s.world && s.us_market ? compareFits(s.world, s.us_market) : s.comparison;
  return category === null ? null : LINES[category];
}

function isFit(x: unknown): x is BetaFit {
  const f = x as Partial<BetaFit> | null;
  return typeof f === "object" && f !== null && typeof f.beta === "number" && typeof f.ci_low === "number" && typeof f.ci_high === "number";
}

/**
 * The Europe row, when the report has one. The block follows the shape of the ACWI block: the fit
 * sits in `europe.world` (or is `europe` itself), the days in `europe.n_sample`. A block whose status
 * is not "ok", or without a fit, gives no row.
 */
export function europeRow(s: WorldBetaSection): EuropeRow | null {
  const raw = (s as unknown as { europe?: Record<string, unknown> | null }).europe;
  if (raw === undefined || raw === null || typeof raw !== "object") return null;
  if (raw["status"] !== undefined && raw["status"] !== "ok") return null;
  const fit = [raw["world"], raw["fit"], raw].find(isFit);
  if (!fit) return null;
  const days = [raw["n_sample"], (raw["sample"] as { n?: unknown } | undefined)?.n, raw["n"]].find((d) => typeof d === "number");
  return {
    fit,
    days: typeof days === "number" ? days : null,
    proxy: typeof raw["proxy"] === "string" ? raw["proxy"] : "IEUR",
  };
}
