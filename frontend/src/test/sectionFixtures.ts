/**
 * Section fixtures of the schema v3 contract (docs/specs/schema-v3-contract.md SC3.4): one JSON file
 * per optional section in `backend/factordesk/tests/fixtures/sections/`, shared with the backend
 * tests. Each feature replaces its own JSON file; this module does not change.
 */
import type { FactorReport } from "../api/types";
import fragility from "@fixtures/sections/fragility.json";
import kalman from "@fixtures/sections/kalman.json";
import leadLag from "@fixtures/sections/lead_lag.json";
import residual from "@fixtures/sections/residual_alpha.json";
import shrunk from "@fixtures/sections/shrunk.json";

/** The `FactorReport` fields of the optional sections, in panel order. */
export const SECTION_FIELDS = ["lead_lag", "shrunk_betas", "fragility", "residual", "kalman_betas"] as const;
export type SectionField = (typeof SECTION_FIELDS)[number];

const PAYLOADS: Record<SectionField, unknown> = {
  lead_lag: leadLag,
  shrunk_betas: shrunk,
  fragility,
  residual,
  kalman_betas: kalman,
};

/** A deep copy of `report` with the fixture of `field` attached. */
export function withSection<F extends SectionField>(report: FactorReport, field: F): FactorReport {
  const copy = structuredClone(report);
  copy[field] = structuredClone(PAYLOADS[field]) as FactorReport[F];
  return copy;
}
