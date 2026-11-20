/**
 * Reads of the reference-currency contract (Sprint 3): the report's `currency` block, the hedge
 * flags of a library line, and the euro cash line's id. The fields come from the generated types.
 */
import type { CurrencyInfo, FactorReport, LibraryLine } from "./types";
import type { Currency } from "../state/currency";

/** The optional top-level `currency` of a report: absent in the USD view. */
export type ReportCurrency = CurrencyInfo;

/** The currency block of a report, or null (always null in the USD view). */
export function currencyOf(report: FactorReport): ReportCurrency | null {
  const value = report.currency;
  return value && (value.reference as string) === "EUR" ? value : null;
}

/** The reference currency a report is in: its `currency.reference`, else USD. */
export function reportCurrency(report: FactorReport): Currency {
  return currencyOf(report)?.reference ?? "USD";
}

/** The hedge facts of a library line. */
export function hedgeFlags(line: LibraryLine | undefined): { hedgeEur: boolean; multiCurrency: boolean } {
  return { hedgeEur: line?.hedge_eur === true, multiCurrency: line?.multi_currency === true };
}

/** The id of the library's euro cash line: in the euro view it earns the euro overnight rate. */
export const EUR_CASH_ID = "cash_eur";
