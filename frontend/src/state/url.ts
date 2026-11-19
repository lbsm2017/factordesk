import { isIsoDate } from "../format/dates";
import type { RangePreset } from "../api/types";

/**
 * URL state contract (dashboard spec DB6.1). Shapes: `/?t=SPY&range=3Y`,
 * `/?t=SPY&start=2023-01-01&end=2026-09-30`, plus an optional `win=126`, `stats=1`, `m=track` (the
 * track-record mode; no `m` means ticker mode) and `model=ff6` (FF5 plus momentum; no `model` means
 * FF5), so every older URL keeps its meaning. Panels
 * read `win` through props and `stats` through `useShowStats()`, never from `location`.
 */

/** Presets of the range control (owner decisions of 2026-11-18 and 2026-11-19): the API lists exactly these four. */
export const PRESETS = ["3Y", "5Y", "10Y", "FULL"] as const satisfies readonly RangePreset[];
export type Preset = (typeof PRESETS)[number];

export type RollingWindowDays = 126 | 252;

/** Factor models of the model toggle: FF5 (the default) and FF6 = FF5 + momentum. */
export const MODELS = ["ff5", "ff6"] as const;
export type FactorModel = (typeof MODELS)[number];

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
  /** The "Show statistics" switch (dashboard spec DV6): `stats=1` when on, absent when off. */
  stats: boolean;
  /** The sidebar mode: a ticker report (no `m` in the URL) or an uploaded track record (`m=track`). */
  mode: Mode;
  /** The factor model: FF5 (no `model` in the URL) or FF6 (`model=ff6`). */
  model: FactorModel;
}

export type Mode = "ticker" | "track";

export const EMPTY_URL_STATE: UrlState = { ticker: null, range: null, start: null, end: null, win: null, stats: false, mode: "ticker", model: "ff5" };

/** The server's ticker pattern (`validate_ticker`): 1 to 12 of letters, digits and . ^ = -, not starting with a dot. */
const TICKER_PATTERN = /^[A-Za-z0-9.^=-]{1,12}$/;

export type TickerCheck = { ok: true; ticker: string } | { ok: false; message: string };

/** Client-side ticker check with the server's rule and wording (dashboard spec DB2.3). */
export function checkTicker(text: string): TickerCheck {
  const trimmed = text.trim();
  if (trimmed === "") return { ok: false, message: "Type a ticker first, for example SPY." };
  if (!TICKER_PATTERN.test(trimmed) || trimmed.startsWith(".")) {
    return {
      ok: false,
      message: `${trimmed} is not a valid ticker. Use 1 to 12 letters, digits or . ^ = - (for example SPY or BRK-B).`,
    };
  }
  return { ok: true, ticker: trimmed.toUpperCase() };
}

/** True when the text is safe to send to the suggestion endpoint (a prefix of a valid ticker). */
export function isSuggestQuery(text: string): boolean {
  return TICKER_PATTERN.test(text) && !text.startsWith(".");
}

function parsePreset(value: string | null): Preset | null {
  if (value === null) return null;
  const upper = value.trim().toUpperCase();
  return (PRESETS as readonly string[]).includes(upper) ? (upper as Preset) : null;
}

function parseDate(value: string | null): string | null {
  if (value === null) return null;
  const trimmed = value.trim();
  return isIsoDate(trimmed) ? trimmed : null;
}

function parseWin(value: string | null): RollingWindowDays | null {
  return value === "126" ? 126 : value === "252" ? 252 : null;
}

/** Parse and clean `location.search`: invalid values are dropped; `start`/`end` win over `range`. */
export function parseUrl(search: string): UrlState {
  const params = new URLSearchParams(search);
  const rawTicker = params.get("t");
  const checked = rawTicker === null ? null : checkTicker(rawTicker);
  const start = parseDate(params.get("start"));
  const end = parseDate(params.get("end"));
  const custom = start !== null || end !== null;
  return {
    ticker: checked?.ok ? checked.ticker : null,
    range: custom ? null : parsePreset(params.get("range")),
    start,
    end,
    win: parseWin(params.get("win")),
    stats: params.get("stats") === "1",
    mode: params.get("m") === "track" ? "track" : "ticker",
    model: params.get("model")?.trim().toLowerCase() === "ff6" ? "ff6" : "ff5",
  };
}

/** Serialise a state to a query string (with the leading "?", or "" when empty). */
export function toSearch(state: UrlState): string {
  const params = new URLSearchParams();
  if (state.ticker) params.set("t", state.ticker.toUpperCase());
  if (state.start || state.end) {
    if (state.start) params.set("start", state.start);
    if (state.end) params.set("end", state.end);
  } else if (state.range) {
    params.set("range", state.range);
  }
  if (state.win !== null) params.set("win", String(state.win));
  if (state.stats) params.set("stats", "1");
  if (state.mode === "track") params.set("m", "track");
  if (state.model === "ff6") params.set("model", "ff6");
  const text = params.toString();
  return text === "" ? "" : `?${text}`;
}

/** Merge a patch into a state. A custom date or a preset in the patch clears the other form. */
export function applyPatch(state: UrlState, patch: Partial<UrlState>): UrlState {
  const next: UrlState = { ...state, ...patch };
  if ("start" in patch || "end" in patch) {
    if (patch.start || patch.end) next.range = null;
  }
  if (patch.range) {
    next.start = null;
    next.end = null;
  }
  if (next.ticker !== null) next.ticker = next.ticker.toUpperCase();
  return next;
}
