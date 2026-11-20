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
  // Macro runs on US-dollar legs until Sprint 3 S3-9 converts them: it is left out of the euro view.
  if (reportCurrency(report) === "EUR") hidden.add("macro");
  return hidden;
}
