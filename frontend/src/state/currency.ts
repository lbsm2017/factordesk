import { useCallback, useState } from "react";

/**
 * The reference currency of the page: USD (the default) or EUR (Sprint 3). The URL parameter
 * `ccy=EUR` wins; without it the last choice is read from browser storage; without that it is USD.
 * Choosing a currency writes the storage, and puts `ccy=EUR` in the URL (USD is the default, so a
 * USD choice clears the parameter).
 */
export const CURRENCIES = ["USD", "EUR"] as const;
export type Currency = (typeof CURRENCIES)[number];
export const DEFAULT_CURRENCY: Currency = "USD";

/** `localStorage` key of the last choice. */
export const CURRENCY_KEY = "factordesk.currency";

/** The currency named by a URL value or a stored value (case-insensitive), or null for anything else. */
export function parseCurrency(value: string | null | undefined): Currency | null {
  if (value === null || value === undefined) return null;
  const upper = value.trim().toUpperCase();
  return (CURRENCIES as readonly string[]).includes(upper) ? (upper as Currency) : null;
}

/** The stored choice, or null when there is none or the storage throws (private windows, blocked site data). */
export function readStoredCurrency(): Currency | null {
  try {
    return parseCurrency(window.localStorage.getItem(CURRENCY_KEY));
  } catch {
    return null;
  }
}

export function writeStoredCurrency(currency: Currency): void {
  try {
    window.localStorage.setItem(CURRENCY_KEY, currency);
  } catch {
    /* storage is a convenience: the choice still works for this page view */
  }
}

/** The effective currency: the URL wins over the stored choice, which wins over the default. */
export function resolveCurrency(fromUrl: Currency | null, stored: Currency | null): Currency {
  return fromUrl ?? stored ?? DEFAULT_CURRENCY;
}

/**
 * The effective currency and its setter. `fromUrl` is `ccy` of the URL state and `commit` writes it
 * back to the URL: only `EUR` is written, because USD is the default.
 */
export function useCurrency(
  fromUrl: Currency | null,
  commit: (patch: { ccy: Currency | null }) => void,
): [Currency, (next: Currency) => void] {
  const [stored, setStored] = useState<Currency | null>(readStoredCurrency);
  const choose = useCallback(
    (next: Currency) => {
      writeStoredCurrency(next);
      setStored(next);
      commit({ ccy: next === DEFAULT_CURRENCY ? null : next });
    },
    [commit],
  );
  return [resolveCurrency(fromUrl, stored), choose];
}
