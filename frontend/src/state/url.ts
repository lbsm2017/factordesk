import type { RangePreset } from "../api/types";

/**
 * URL state contract (dashboard spec DB6.1). T3 fixes the types; T4 implements `parseUrl` and
 * `toSearch` with their tests. Panels read `win` through props, never from `location`.
 */

/** Presets shown as chips (owner decision 1): the API lists exactly these three. */
export const PRESETS = ["3Y", "5Y", "FULL"] as const satisfies readonly RangePreset[];
export type Preset = (typeof PRESETS)[number];

export type RollingWindowDays = 126 | 252;

export interface UrlState {
  /** Upper-case ticker, or null on the landing page. */
  ticker: string | null;
  /** Preset range. Null when custom dates are used, or when the URL has none (means FULL). */
  range: Preset | null;
  /** Custom start, ISO date. */
  start: string | null;
  /** Custom end, ISO date. */
  end: string | null;
  /** Rolling window of the exposure-over-time panel; null means the report's primary window. */
  win: RollingWindowDays | null;
}

export const EMPTY_URL_STATE: UrlState = { ticker: null, range: null, start: null, end: null, win: null };

/** TODO(T4): parse and clean `location.search`. */
export function parseUrl(_search: string): UrlState {
  return EMPTY_URL_STATE;
}

/** TODO(T4): serialise a state to a query string (with the leading "?", or "" when empty). */
export function toSearch(_state: UrlState): string {
  return "";
}
