/**
 * Section fixtures of the schema v3 contract (docs/specs/schema-v3-contract.md SC3.4): one JSON file
 * per optional section in `backend/factordesk/tests/fixtures/sections/`, shared with the backend
 * tests. Each feature replaces its own JSON file; this module does not change.
 */
import type { FactorReport } from "../api/types";
import alphaStrip from "@fixtures/sections/alpha_strip.json";
import fragility from "@fixtures/sections/fragility.json";
import labels from "@fixtures/sections/label_text.json";
import kalman from "@fixtures/sections/kalman.json";
import leadLag from "@fixtures/sections/lead_lag.json";
import macro from "@fixtures/sections/macro.json";
import performanceFixture from "@fixtures/sections/performance.json";
import residual from "@fixtures/sections/residual_alpha.json";
import shrunk from "@fixtures/sections/shrunk.json";
import tailRisk from "@fixtures/sections/tail_risk.json";
import tailRiskMonthly from "@fixtures/sections/tail_risk_monthly.json";
import worldBeta from "@fixtures/sections/world_beta.json";

/** The `FactorReport` fields of the optional sections, in panel order. */
export const SECTION_FIELDS = [
  "world_beta",
  "performance",
  "lead_lag",
  "shrunk_betas",
  "fragility",
  "residual",
  "kalman_betas",
  "tail_risk",
  "alpha_strip",
  "macro",
] as const;
export type SectionField = (typeof SECTION_FIELDS)[number];

const PAYLOADS: Record<SectionField, unknown> = {
  performance: performanceFixture,
  lead_lag: leadLag,
  shrunk_betas: shrunk,
  fragility,
  world_beta: worldBeta,
  residual,
  kalman_betas: kalman,
  tail_risk: tailRisk,
  alpha_strip: alphaStrip,
  macro,
};

/** The monthly (60 months) tail risk section, for a report with a monthly subject. */
export const TAIL_RISK_MONTHLY: unknown = tailRiskMonthly;

/** A deep copy of `report` with the fixture of `field` attached and the footnote texts of that section added. */
export function withSection<F extends SectionField>(report: FactorReport, field: F): FactorReport {
  const copy = structuredClone(report);
  copy[field] = structuredClone(PAYLOADS[field]) as FactorReport[F];
  copy.label_text = { ...copy.label_text, ...(labels as Record<string, Record<string, string>>)[field] };
  return copy;
}
