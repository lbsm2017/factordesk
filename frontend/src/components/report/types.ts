import type { FactorReport } from "../../api/types";

/** Props of every report panel. A panel with a statistic whose status is not "ok" shows EmptyState. */
export interface ReportPanelProps {
  report: FactorReport;
}
