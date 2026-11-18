import type { ReportPanelProps } from "../types";
import { Panel } from "../Panel";

/**
 * Panel of the `performance` section (contract note `docs/validation/performance-contract-note-2026-11-18.md`;
 * numbers and wording: `docs/validation/performance-handoff-2026-11-18.md`). Registered in
 * `panelRegistry.ts` at position 450, right after Price. Placeholder: the React panel is built
 * later. Renders nothing when the section is absent (null).
 */
export function PerformancePanel({ report }: ReportPanelProps) {
  const section = report.performance;
  if (section === null) return null;
  const empty = section.status === "ok" ? {} : { empty: { reason: section.reason ?? "", action: "" } };
  return (
    <Panel
      id="performance"
      title="Performance"
      question="How has the stock performed over the analysed window?"
      {...empty}
    />
  );
}
