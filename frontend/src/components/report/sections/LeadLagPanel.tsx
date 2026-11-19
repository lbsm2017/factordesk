import type { ReportPanelProps } from "../types";
import { Panel } from "../Panel";

/**
 * Panel of the `lead_lag` section (contract SC2.2; spec `docs/specs/lead-lag-betas.md`).
 * Registered in `panelRegistry.ts` at position 510. Owned by the feature branch, which
 * replaces this placeholder body. Renders nothing when the section is absent (null).
 */
export function LeadLagPanel({ report }: ReportPanelProps) {
  const section = report.lead_lag;
  if (section == null) return null;
  const empty = section.status === "ok" ? {} : { empty: { reason: section.reason ?? "", action: "" } };
  return (
    <Panel
      id="lead-lag"
      title="Timing-adjusted betas (lead-lag)"
      question="Does part of the exposure show up on the factors' previous or next day?"
      {...empty}
    />
  );
}
