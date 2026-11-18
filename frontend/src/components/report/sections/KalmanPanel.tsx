import type { ReportPanelProps } from "../types";
import { Panel } from "../Panel";

/**
 * Panel of the `kalman_betas` section (contract SC2.3; spec `docs/specs/kalman-betas.md`).
 * Registered in `panelRegistry.ts` at position 810. Owned by the feature branch, which
 * replaces this placeholder body. Renders nothing when the section is absent (null).
 */
export function KalmanPanel({ report }: ReportPanelProps) {
  const section = report.kalman_betas;
  if (section === null) return null;
  const empty = section.status === "ok" ? {} : { empty: { reason: section.reason ?? "", action: "" } };
  return (
    <Panel
      id="kalman"
      title="Kalman-filter betas"
      question="How did the exposures move, using only data up to each date?"
      {...empty}
    />
  );
}
