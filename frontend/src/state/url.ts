import { isIsoDate } from "../format/dates";
import type { RangePreset } from "../api/types";
import { parseCurrency } from "./currency";
import type { Currency } from "./currency";
import { DEFAULT_FACTOR_SET, parseFactorSet } from "./factorSet";
import type { FactorSet } from "./factorSet";

/**
 * URL state contract (dashboard spec DB6.1). Shapes: `/?t=SPY&range=3Y`,
 * `/?t=SPY&start=2023-01-01&end=2026-09-30`, plus an optional `win=126`, `stats=1`, `m=track` (the
 * track-record mode) or `m=portfolio` (the portfolio composer); no `m` means ticker mode and `model=ff5|ff6`; `ccy=EUR|USD` names the reference currency and overrides the stored choice; `fs=europe` picks the Developed Europe factors (no `fs` means the US set, and the US set is never written). Owner decision of 2026-11-19: no
 * `range` means 10Y and no `model` means FF6, and a default is never written. Full history is written
 * `range=FULL`, FF5 is written `model=ff5`. Every explicit parameter of an older URL keeps its meaning.
 * Panels read `win` through props and `stats` through `useShowStats()`, never from `location`.
 */

/** Presets of the range control (owner decisions of 2026-11-18 and 2026-11-19): the API lists exactly these four. */
export const PRESETS = ["3Y", "5Y", "10Y", "FULL"] as const satisfies readonly RangePreset[];
export type Preset = (typeof PRESETS)[number];

export type RollingWindowDays = 126 | 252;

/** Factor models: FF5 and FF6 = FF5 + momentum (the dashboard default; the API default stays FF5). */
export const MODELS = ["ff5", "ff6"] as const;
export type FactorModel = (typeof MODELS)[number];

/** What the dashboard shows when the URL says nothing (owner decision of 2026-11-19). */
export const DEFAULT_RANGE: Preset = "10Y";
export const DEFAULT_MODEL: FactorModel = "ff6";

export interface UrlState {
  /** Upper-case ticker, or null on the landing page. */
  ticker: string | null;
  /** Preset range; 10Y when the URL has none. Null only when custom dates are used. */
  range: Preset | null;
  /** Custom start, ISO date. */
  start: string | null;
  /** Custom end, ISO date. */
  end: string | null;
  /** Rolling window of the exposure-over-time panel; null means the report's primary window. */
  win: RollingWindowDays | null;
  /** The "Show statistics" switch (dashboard spec DV6): `stats=1` when on, absent when off. */
  stats: boolean;
  /** The sidebar mode: a ticker report (no `m`), an uploaded track record (`m=track`) or a portfolio (`m=portfolio`). */
  mode: Mode;
  /** The factor model: FF6 when the URL has no `model`; `model=ff5` for FF5. */
  model: FactorModel;
  /** The reference currency named by the URL (`ccy=EUR` or `ccy=USD`); null when the URL says nothing, so the stored choice or USD applies. */
  ccy: Currency | null;
  /** The factor set: `europe` for `fs=europe`; the US set when the URL has no `fs`. */
  fs: FactorSet;
}

export type Mode = "ticker" | "track" | "portfolio";

export const EMPTY_URL_STATE: UrlState = {
  ticker: null,
  range: DEFAULT_RANGE,
  start: null,
  end: null,
  win: null,
  stats: false,
  mode: "ticker",
  model: DEFAULT_MODEL,
  ccy: null,
  fs: DEFAULT_FACTOR_SET,
};

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

function parseModel(value: string | null): FactorModel {
  if (value === null) return DEFAULT_MODEL;
  const lower = value.trim().toLowerCase();
  return (MODELS as readonly string[]).includes(lower) ? (lower as FactorModel) : DEFAULT_MODEL;
}

function parseMode(value: string | null): Mode {
  return value === "track" || value === "portfolio" ? value : "ticker";
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
    range: custom ? null : (parsePreset(params.get("range")) ?? DEFAULT_RANGE),
    start,
    end,
    win: parseWin(params.get("win")),
    stats: params.get("stats") === "1",
    mode: parseMode(params.get("m")),
    model: parseModel(params.get("model")),
    ccy: parseCurrency(params.get("ccy")),
    fs: parseFactorSet(params.get("fs")),
  };
}

/** Serialise a state to a query string (with the leading "?", or "" when empty). */
export function toSearch(state: UrlState): string {
  const params = new URLSearchParams();
  if (state.ticker) params.set("t", state.ticker.toUpperCase());
  if (state.start || state.end) {
    if (state.start) params.set("start", state.start);
    if (state.end) params.set("end", state.end);
  } else if (state.range && state.range !== DEFAULT_RANGE) {
    params.set("range", state.range);
  }
  if (state.win !== null) params.set("win", String(state.win));
  if (state.stats) params.set("stats", "1");
  if (state.mode !== "ticker") params.set("m", state.mode);
  if (state.model !== DEFAULT_MODEL) params.set("model", state.model);
  if (state.ccy !== null) params.set("ccy", state.ccy);
  if (state.fs !== DEFAULT_FACTOR_SET) params.set("fs", state.fs);
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
  if (next.range === null && !next.start && !next.end) next.range = DEFAULT_RANGE;
  if (next.ticker !== null) next.ticker = next.ticker.toUpperCase();
  return next;
}
