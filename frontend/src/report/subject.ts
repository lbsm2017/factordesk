/** What a report is about, and the words that follow from it (next-stage spec E0). A report with
 * no `subject` is a daily ticker report; one with a monthly subject counts months, not trading days. */
import type { FactorReport } from "../api/types";
import { count } from "../format";

/** The report is on monthly returns (an uploaded track record). */
export function isMonthly(report: FactorReport): boolean {
  return report.subject?.frequency === "monthly";
}

/** The report is about an uploaded track record or a portfolio, not a ticker. */
export function isSubjectReport(report: FactorReport): boolean {
  return report.subject != null && report.subject.kind !== "ticker";
}

/** "1 trading day" / "412 trading days", or "1 month" / "84 months" for a monthly report. */
export function observations(report: FactorReport, n: number): string {
  const [one, many] = isMonthly(report) ? ["month", "months"] : ["trading day", "trading days"];
  return `${count(n)} ${n === 1 ? one : many}`;
}

/** "price days" in a daily report, "months" in a monthly one (the dates around the factor data). */
export function periodWord(report: FactorReport): string {
  return isMonthly(report) ? "months" : "price days";
}

/** The data-quality check: the price audit of a ticker, the data audit of a record. */
export function auditWord(report: FactorReport): string {
  return isSubjectReport(report) ? "data" : "price";
}

/** "day-to-day" or "month-to-month". */
export function stepWord(report: FactorReport): string {
  return isMonthly(report) ? "month-to-month" : "day-to-day";
}

/** The frequency of the returns in a sentence: "daily" or "monthly". */
export function frequencyWord(report: FactorReport): string {
  return isMonthly(report) ? "monthly" : "daily";
}

const FEES: Record<string, string> = { gross: "before fees", net: "after fees" };

/** "Uploaded track record, after fees, in US dollars"; null for a ticker report. */
export function subjectLine(report: FactorReport): string | null {
  const s = report.subject;
  if (s == null || s.kind === "ticker") return null;
  const parts = [s.kind === "upload" ? "Uploaded track record" : "Portfolio"];
  if (s.gross_net) parts.push(`returns ${FEES[s.gross_net] ?? s.gross_net}`);
  if (s.currency === "USD") parts.push("in US dollars");
  return parts.join(", ");
}
