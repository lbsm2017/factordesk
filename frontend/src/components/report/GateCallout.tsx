import { num, signed, tstat } from "../../format";
import { fin } from "./leadHelpers";
import type { ReportPanelProps } from "./types";
import "./lead.css";

/**
 * The residual quality gate (M3.6) with its numbers, shown only when it fired. The notice carries
 * the plain sentence; this callout adds the evidence and points to the 5-day estimate.
 */
export function GateCallout({ report }: ReportPanelProps) {
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
    <section className="gate-callout" id="gate" aria-labelledby="gate-title">
      <svg className="glyph" aria-hidden="true" viewBox="0 0 16 16">
        <circle cx="8" cy="8" r="6.5" />
        <path className="cut" d="M8 7v4.5M8 4.6v.9" />
      </svg>
      <div>
        <h2 id="gate-title">Residual quality gate</h2>
        <p>
          {measured}
          {shareText} R² and residual volatility are probably understated; the 5-day estimate under{" "}
          <a href="#regression-detail">Regression detail</a> is less affected.
        </p>
      </div>
    </section>
  );
}
