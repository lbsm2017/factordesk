import { num, signed, tstat } from "../../format";
import { fin } from "./leadHelpers";
import type { ReportPanelProps } from "./types";

/**
 * The residual quality gate (M3.6) with its numbers, shown inside the notice's Details and only
 * when the gate fired. The notice summary carries the plain sentence; this paragraph adds the
 * evidence, so nothing extra sits above the first chart (review DF1).
 */
export function GateEvidence({ report }: ReportPanelProps) {
  const gate = report.quality_gate;
  if (gate.status !== "ok" || !gate.fired) return null;
  const rho = fin(gate.lag1_autocorrelation);
  const z = fin(gate.lag1_z);
  const rhoMax = fin(gate.rho_threshold);
  const zMax = fin(gate.z_threshold);
  const share = fin(gate.noise_share);
  const measured =
    rho !== null && z !== null
      ? `The lag-1 autocorrelation of the residuals is ${signed(rho, 2)} (robust z ${tstat(z)})` +
        (rhoMax !== null && zMax !== null ? `, past the gate at ${signed(rhoMax, 2)} and z ${tstat(zMax)}.` : ".")
      : "The residuals reverse from one day to the next.";
  const shareText =
    share !== null
      ? ` Under the simple model of the method, about ${num(share * 100, 0)}% of residual variance is a price error that reverses the next day.`
      : "";
  return (
    <p className="gate-evidence">
      {measured}
      {shareText}
    </p>
  );
}
