import type { ReportPanelProps } from "../types";
import { Panel } from "../Panel";

/**
 * Panel of the `fragility` section (contract SC2.1; spec `docs/specs/fragility-score.md`).
 * Registered in `panelRegistry.ts` at position 530. Owned by the feature branch, which
 * replaces this placeholder body. Renders nothing when the section is absent (null).
 */
export function FragilityPanel({ report }: ReportPanelProps) {
  const section = report.fragility;
  if (section === null) return null;
  const empty = section.status === "ok" ? {} : { empty: { reason: section.reason ?? "", action: "" } };
  return (
    <Panel
      id="fragility"
      title="Fragility"
      question="How many trading days does each significant result rest on?"
      {...empty}
    />
  );
}
