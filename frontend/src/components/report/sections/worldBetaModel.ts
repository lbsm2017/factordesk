/** Rows and wording of the World beta panel. */
import type { WorldBetaSection } from "../../../api/types";

export type BetaFit = NonNullable<WorldBetaSection["world"]>;
export type Comparison = NonNullable<WorldBetaSection["comparison"]>;

export type ProxyBeta = NonNullable<WorldBetaSection["europe"]>;

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

/** The Europe block when it carries a result (status ok, both fits), else null. */
export function europeOk(s: WorldBetaSection): ProxyBeta | null {
  const e = s.europe;
  if (e === null || e === undefined || e.status !== "ok" || e.benchmark === null || e.us_market === null) return null;
  return e;
}

/** Same fit to the digits shown; used to decide whether the Europe days need their own US market row. */
export function sameFit(a: BetaFit, b: BetaFit): boolean {
  return a.beta === b.beta && a.ci_low === b.ci_low && a.ci_high === b.ci_high && a.r2 === b.r2;
}
