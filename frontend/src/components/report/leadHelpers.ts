/** Small pieces shared by Header, Notice, KpiStrip, Equation and GateCallout (T5). */
import type { FactorReport } from "../../api/types";

/** The value when it is a finite number, else null (handles null, NaN and infinities). */
export function fin(x: number | null | undefined): number | null {
  return typeof x === "number" && Number.isFinite(x) ? x : null;
}

/** "1 day" / "49 days". */
export function plural(n: number, one: string, many: string): string {
  return `${n} ${n === 1 ? one : many}`;
}

export interface NoticeItem {
  code: string;
  message: string;
}

/**
 * Every warning, including the quality-gate caveat when it fired and no `residual_reversal`
 * warning already carries it (same rule as the static renderer's `_notice_items`).
 */
export function noticeItems(report: FactorReport): NoticeItem[] {
  const items: NoticeItem[] = report.warnings.map((w) => ({ code: w.code, message: w.message }));
  const gate = report.quality_gate;
  if (gate.fired && gate.message && !items.some((i) => i.code === "residual_reversal")) {
    items.unshift({ code: "residual_reversal", message: gate.message });
  }
  return items;
}
