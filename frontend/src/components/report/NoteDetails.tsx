import type { FactorReport } from "../../api/types";
import { num, pct, pval, tstat } from "../../format";
import { tagText } from "../../text/plain";
import { GateEvidence } from "./GateEvidence";
import { fin } from "./leadHelpers";
import type { NoticeItem } from "./leadHelpers";

/** The 5-day estimate line under Details; only when the quality gate fired (M3.6). */
function GateDetail({ report }: { report: FactorReport }) {
  const { quality_gate: gate, five_day_regression: five } = report;
  if (!gate.fired) return null;
  if (five.status === "ok") {
    const alpha = fin(five.alpha_annual);
    const z = fin(five.alpha_z);
    const p = fin(five.alpha_p);
    const r2 = fin(five.r2);
    return (
      <p>
        5-day estimate ({five.n_blocks.toLocaleString("en-US")} blocks): alpha {alpha === null ? "n/a" : pct(alpha)} a
        year, t {z === null ? "n/a" : tstat(z)}, p {p === null ? "n/a" : pval(p)}, {tagText(five.alpha_tag)}; R²{" "}
        {r2 === null ? "n/a" : num(r2, 4)}. The full table is under <a href="#regression-detail">Regression detail</a>.
      </p>
    );
  }
  return five.reason ? <p>5-day estimate: {five.reason}.</p> : null;
}

/** The opened Details of the data notes: every raw message, the gate evidence and the 5-day line. */
export function NoteDetails({ report, items }: { report: FactorReport; items: NoticeItem[] }) {
  return (
    <>
      <ul>
        {items.map((it, i) => (
          <li key={`${it.code}-${i}`}>{it.message}</li>
        ))}
      </ul>
      <GateEvidence report={report} />
      <GateDetail report={report} />
    </>
  );
}
