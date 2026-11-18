import type { FactorReport } from "../../api/types";
import { num, pct, pval, tstat } from "../../format";
import { tagText, warningText } from "../../text/plain";
import { GateEvidence } from "./GateEvidence";
import { fin, noticeItems } from "./leadHelpers";
import type { ReportPanelProps } from "./types";
import "./lead.css";

const GLYPH_WARN = (
  <svg className="glyph" aria-hidden="true" viewBox="0 0 16 16">
    <path d="M8 1.5 15 14.5H1z" />
    <path className="cut" d="M8 6v4M8 11.6v1" />
  </svg>
);

/** The 5-day estimate line under Details; only when the quality gate fired (M3.6). */
function GateDetail({ report }: ReportPanelProps) {
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

/** Two-line plain summary of the first two distinct warnings, with the raw messages under Details. */
export function summaryOf(items: { code: string; message: string }[]): string {
  const plain: string[] = [];
  for (const it of items) {
    const text = warningText(it);
    if (!plain.includes(text)) plain.push(text);
  }
  let summary = plain.slice(0, 2).join(" ");
  if (plain.length > 2) summary += ` ${plain.length - 2} more are listed under Details.`;
  return summary;
}

export function Notice({ report }: { report: FactorReport }) {
  const items = noticeItems(report);
  if (items.length === 0) return null;
  return (
    <aside className="notice" id="notice" aria-label="Data quality">
      {GLYPH_WARN}
      <div>
        <p className="notice-sum">
          <span className="vh">Warning: </span>
          {summaryOf(items)}
        </p>
        <details className="how">
          <summary>Details</summary>
          <ul>
            {items.map((it, i) => (
              <li key={`${it.code}-${i}`}>{it.message}</li>
            ))}
          </ul>
          <GateEvidence report={report} />
          <GateDetail report={report} />
        </details>
      </div>
    </aside>
  );
}
