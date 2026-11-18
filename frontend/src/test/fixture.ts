/** The committed mock report (backend fixture, synthetic data) typed as FactorReport. */
import type { FactorReport } from "../api/types";
import raw from "@fixtures/mock_report.json";

export const mockReport = raw as unknown as FactorReport;

/** A deep copy that tests can mutate (for empty states and other variants). */
export function cloneReport(): FactorReport {
  return structuredClone(mockReport);
}
