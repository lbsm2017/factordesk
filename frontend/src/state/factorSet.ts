/**
 * The factor set of the page (Sprint 4): the US Fama-French factors (the default) or the Developed
 * Europe ones. It lives in the URL only: `fs=europe` names Europe, and the US set leaves the
 * parameter out, as USD leaves out `ccy`. Nothing is stored, so a shared link always means the same.
 */
export const FACTOR_SETS = ["us", "europe"] as const;
export type FactorSet = (typeof FACTOR_SETS)[number];
export const DEFAULT_FACTOR_SET: FactorSet = "us";

/** What each set is called in the sidebar, the header and the status line. */
export const FACTOR_SET_LABELS: Record<FactorSet, string> = { us: "US", europe: "Europe" };

/** The set named by a URL value (case-insensitive). Anything else, or nothing, is the US set. */
export function parseFactorSet(value: string | null | undefined): FactorSet {
  if (value === null || value === undefined) return DEFAULT_FACTOR_SET;
  const lower = value.trim().toLowerCase();
  return (FACTOR_SETS as readonly string[]).includes(lower) ? (lower as FactorSet) : DEFAULT_FACTOR_SET;
}

/** `factor_set=europe` for the Europe set; nothing for the US set, which is the API default. */
export function factorSetParam(set: FactorSet): Record<string, string> {
  return set === DEFAULT_FACTOR_SET ? {} : { factor_set: set };
}
