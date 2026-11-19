/** The committed mock report (backend fixture, synthetic data) typed as FactorReport. */
import type { FactorReport } from "../api/types";
import raw from "@fixtures/mock_report.json";
import rawMonthly from "@fixtures/monthly_report.json";

export const mockReport = raw as unknown as FactorReport;

/** The committed monthly report of an uploaded track record (84 months, synthetic), typed as FactorReport. */
export const monthlyReport = rawMonthly as unknown as FactorReport;

/** A deep copy that tests can mutate (for empty states and other variants). */
export function cloneReport(): FactorReport {
  return structuredClone(mockReport);
}
