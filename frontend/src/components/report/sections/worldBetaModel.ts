/** Rows and wording of the World beta panel. */
import type { WorldBetaSection } from "../../../api/types";

export type BetaFit = NonNullable<WorldBetaSection["world"]>;
export type Comparison = NonNullable<WorldBetaSection["comparison"]>;

export type ProxyBeta = NonNullable<WorldBetaSection["europe"]>;

/** The reading of two 95% intervals: overlap is always "about the same", whatever the point estimates. */
export function compareFits(world: BetaFit, us: BetaFit): Comparison {
  if (world.ci_low <= us.ci_high && us.ci_low <= world.ci_high) return "about_the_same";
  return world.beta > us.beta ? "higher" : "lower";
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
