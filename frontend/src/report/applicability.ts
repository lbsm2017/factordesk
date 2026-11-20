/** Which panels a report leaves out. A panel whose section is null already renders nothing; this
 * covers the sections that are present but `not_applicable`, which would only show an empty state
 * (an uploaded monthly record has no rolling windows). Ticker reports are never touched. */
import type { FactorReport } from "../api/types";
import { reportCurrency } from "../api/currency";
import { isSubjectReport } from "./subject";

/** Names (from the panel registry) of the panels to leave out. */
export function hiddenPanels(report: FactorReport): ReadonlySet<string> {
  const hidden = new Set<string>();
  if (isSubjectReport(report) && report.rolling.every((w) => w.status === "not_applicable")) hidden.add("rolling");
  // Macro and Energy run on US-dollar legs until Sprint 3 S3-9 converts them: both are left out of the
  // euro view. The key "energy" is the name the energy panel registers; hiding an absent key is harmless.
  if (reportCurrency(report) === "EUR") {
    hidden.add("macro");
    hidden.add("energy");
  }
  return hidden;
}
