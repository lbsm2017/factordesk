/**
 * Hand-written types for the reference-currency contract (Sprint 3, S3-5). The backend lane adds
 * these fields to the OpenAPI schema; until the generated types carry them this module reads them
 * loosely, the way `securityOf` reads `data.security`. When `types.gen.ts` has them, delete the
 * casts here and read the fields directly.
 */
import type { FactorReport, LibraryLine } from "./types";
import type { Currency } from "../state/currency";

/** The optional top-level `currency` of a report: absent in the USD view. */
export interface ReportCurrency {
  reference: Currency;
  /** Credit for the exchange-rate source, e.g. "ECB euro reference rates". */
  fx_source?: string | null;
  /** Credit for the cash-rate source, e.g. "ECB euro short-term rate (EONIA before 2019)". */
  rate_source?: string | null;
  /** Plain-language notes on what the euro view did. */
  notes?: string[] | null;
}

/** The currency block of a report, or null (always null in the USD view). */
export function currencyOf(report: FactorReport): ReportCurrency | null {
  const value = (report as { currency?: ReportCurrency | null }).currency;
  return value && (value.reference === "EUR" || value.reference === "USD") ? value : null;
}

/** The reference currency a report is in: its `currency.reference`, else USD. */
export function reportCurrency(report: FactorReport): Currency {
  return currencyOf(report)?.reference ?? "USD";
}

/** The hedge facts of a library line (optional booleans of the API; absent means false). */
export function hedgeFlags(line: LibraryLine | undefined): { hedgeEur: boolean; multiCurrency: boolean } {
  const v = (line ?? {}) as { hedge_eur?: boolean | null; multi_currency?: boolean | null };
  return { hedgeEur: v.hedge_eur === true, multiCurrency: v.multi_currency === true };
}

/** The id of the library's euro cash line: in the euro view it earns the euro overnight rate. */
export const EUR_CASH_ID = "cash_eur";
