import type { ReportPanelProps } from "../types";
import { Panel } from "../Panel";

/**
 * Panel of the `residual` section (contract SC2.5; spec `docs/methodology-residual-analysis.md`).
 * Registered in `panelRegistry.ts` at position 710. Owned by the feature branch, which
 * replaces this placeholder body. Renders nothing when the section is absent (null).
 */
export function ResidualAlphaPanel({ report }: ReportPanelProps) {
  const section = report.residual;
  if (section === null) return null;
  const empty = section.status === "ok" ? {} : { empty: { reason: section.reason ?? "", action: "" } };
  return (
    <Panel
      id="residual"
      title="Residual return"
      question="What did this stock return beyond its factor exposures, and does it hold up without hindsight?"
      {...empty}
    />
  );
}
