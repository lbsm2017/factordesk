/** TanStack Query hooks and request helpers (dashboard spec DB6.2). */
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { dateLong } from "../format";
import { DEFAULT_CURRENCY } from "../state/currency";
import type { Currency } from "../state/currency";
import { DEFAULT_FACTOR_SET, factorSetParam } from "../state/factorSet";
import type { FactorSet } from "../state/factorSet";
import { DEFAULT_MODEL, DEFAULT_RANGE, isSuggestQuery } from "../state/url";
import type { FactorModel, UrlState } from "../state/url";
import { ApiRequestError, apiRequest, NETWORK_ERROR } from "./client";
import { PORTFOLIO_RUN, recordFallback, recordStep, reportRunKey, startRun, UPLOAD_RUN } from "./runProgress";
import { streamReport } from "./stream";
import type {
  ApiError,
  AssetClassLibrary,
  FactorDataStatus,
  RangeOptions,
  TickerSuggestions,
} from "./types";
import type { PortfolioTree } from "../portfolio/tree";

const SUGGEST_LIMIT = 8;
export const SUGGEST_DEBOUNCE_MS = 150;

/** The dashboard always names the model, because its default (FF6) differs from the API default (FF5). */
function modelParam(model: FactorModel | undefined): Record<string, string> {
  return { model: model ?? DEFAULT_MODEL };
}

/** `ccy=EUR` in the euro view; nothing in the USD view, which is the API default. */
function ccyParam(ccy: Currency): Record<string, string> {
  return ccy === DEFAULT_CURRENCY ? {} : { ccy };
}

/**
 * Query parameters of the report endpoints: custom dates win over a preset; neither means the
 * default range. The model is always sent. `ccy=EUR` is added in the euro view only: USD is the
 * default and the USD request stays as it was. `factor_set=europe` is added for the Europe set only,
 * the same way. `ccy` is the effective currency of the page (URL, then stored choice, then USD),
 * not the raw URL value.
 */
export function reportParams(state: UrlState, ccy: Currency = state.ccy ?? DEFAULT_CURRENCY): Record<string, string> {
  if (state.start || state.end) {
    return {
      ...(state.start ? { start: state.start } : {}),
      ...(state.end ? { end: state.end } : {}),
      ...modelParam(state.model),
      ...ccyParam(ccy),
      ...factorSetParam(state.fs),
    };
  }
  return { range: state.range ?? DEFAULT_RANGE, ...modelParam(state.model), ...ccyParam(ccy), ...factorSetParam(state.fs) };
}

/** The `rangeOrDates` part of the report query key. */
export function reportRangeKey(state: UrlState): string {
  if (state.start || state.end) return `${state.start ?? ""}..${state.end ?? ""}`;
  return state.range ?? DEFAULT_RANGE;
}

/** `/api/report/{t}/html?{same range}` for the Download link (dashboard spec DB6.5). */
export function downloadHref(state: UrlState, ccy?: Currency): string {
  if (state.ticker === null) return "#";
  const qs = new URLSearchParams(reportParams(state, ccy)).toString();
  return `/api/report/${encodeURIComponent(state.ticker)}/html?${qs}`;
}

export function useFactorStatus() {
  return useQuery({
    queryKey: ["factors", "status"],
    queryFn: ({ signal }) => apiRequest<FactorDataStatus>("/api/factors/status", { signal }),
    staleTime: 60_000,
  });
}

function useDebounced<T>(value: T, ms: number): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const id = window.setTimeout(() => setDebounced(value), ms);
    return () => window.clearTimeout(id);
  }, [value, ms]);
  return debounced;
}

/** Server suggestions for the typed prefix; nothing is requested for an empty or unsafe query. */
export function useTickerSuggestions(text: string) {
  const q = useDebounced(text.trim().toUpperCase(), SUGGEST_DEBOUNCE_MS);
  const enabled = q !== "" && isSuggestQuery(q);
  return useQuery({
    queryKey: ["tickers", q],
    queryFn: ({ signal }) => apiRequest<TickerSuggestions>("/api/tickers", { signal, query: { q, limit: SUGGEST_LIMIT } }),
    enabled,
    staleTime: 60_000,
    placeholderData: keepPreviousData,
  });
}

export function useRanges(ticker: string | null, factorSet: FactorSet = DEFAULT_FACTOR_SET) {
  return useQuery({
    queryKey: ["ranges", ticker, factorSet],
    queryFn: ({ signal }) =>
      apiRequest<RangeOptions>(`/api/report/${encodeURIComponent(ticker ?? "")}/ranges`, {
        signal,
        query: factorSetParam(factorSet),
      }),
    enabled: ticker !== null,
    staleTime: 5 * 60_000,
    retry: false,
  });
}

/** The query key of a report: ticker, range, model, currency and factor set. */
export function reportQueryKey(state: UrlState, ccy: Currency = state.ccy ?? DEFAULT_CURRENCY): readonly unknown[] {
  return ["report", state.ticker, reportRangeKey(state), state.model ?? DEFAULT_MODEL, ccy, state.fs];
}

/** The key under which the steps of a report run are kept (see `useRunProgress`). */
export function reportProgressKey(state: UrlState, ccy: Currency = state.ccy ?? DEFAULT_CURRENCY): string {
  return reportRunKey(reportQueryKey(state, ccy));
}

export function useReport(state: UrlState, ccy: Currency = state.ccy ?? DEFAULT_CURRENCY) {
  const { ticker } = state;
  const queryKey = reportQueryKey(state, ccy);
  const runKey = reportRunKey(queryKey);
  return useQuery({
    queryKey,
    queryFn: ({ signal }) => {
      startRun(runKey);
      const path = `/api/report/${encodeURIComponent(ticker ?? "")}`;
      return streamReport(
        `${path}/stream`,
        path,
        { signal, query: reportParams(state, ccy) },
        { signal, onStep: (step) => recordStep(runKey, step), onFallback: () => recordFallback(runKey) },
);
    },
    enabled: ticker !== null,
    staleTime: Infinity,
    placeholderData: keepPreviousData,
    retry: false,
  });
}

/** The ApiError inside any thrown value, so the UI always has a message and an action. */
export function toApiError(error: unknown): ApiError {
  if (error instanceof ApiRequestError) return error.apiError;
  return NETWORK_ERROR;
}

/** One plain sentence for the polite refresh announcement. */
export function refreshMessage(before: FactorDataStatus | undefined, after: FactorDataStatus): string {
  if (!after.available || after.last_date === null) return "No factor data is available yet.";
  const ends = dateLong(after.last_date);
  if (before?.available && before.last_date === after.last_date) {
    return `No newer factor data is available. It still ends ${ends}.`;
  }
  return `Factor data updated. It now ends ${ends}.`;
}

/** Forced factor download; on success it refreshes factors, ranges and reports (dashboard spec DB6.2). */
export function useRefreshFactors(onMessage: (message: string) => void) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => apiRequest<FactorDataStatus>("/api/factors/refresh", { method: "POST" }),
    onSuccess: async (status) => {
      const before = queryClient.getQueryData<FactorDataStatus>(["factors", "status"]);
      onMessage(refreshMessage(before, status));
      queryClient.setQueryData(["factors", "status"], status);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["ranges"] }),
        queryClient.invalidateQueries({ queryKey: ["report"] }),
      ]);
    },
    onError: (error) => {
      const { message, action } = toApiError(error);
      onMessage(`${message} ${action}`);
    },
  });
}

export type GrossNet = "gross" | "net" | "";

export interface UploadInput {
  file: File;
  /** Display name of the record; empty lets the server use its default. */
  name: string;
  /** Whether the returns are before or after fees; empty means not stated. */
  grossNet: GrossNet;
  /** The factor model; the dashboard always sends it. */
  model?: FactorModel;
  /** The currency the record itself is in (`record_currency`); USD when not given. */
  recordCurrency?: Currency;
  /** The reference currency of the report (`ccy`); USD when not given. */
  ccy?: Currency;
  /** The factor set (`factor_set`); the US set when not given. */
  factorSet?: FactorSet;
}

/**
 * The multipart body of `POST /api/report/upload`: the file, then the optional name and fee basis,
 * the model, the record's own currency (`record_currency`, always sent: the user declares it) and,
 * in the euro view only, the reference currency (`ccy=EUR`) and, for the Europe set only, `factor_set=europe`.
 */
export function uploadBody({ file, name, grossNet, model, recordCurrency, ccy, factorSet }: UploadInput): FormData {
  const body = new FormData();
  body.append("file", file);
  if (name.trim() !== "") body.append("name", name.trim());
  if (grossNet !== "") body.append("gross_net", grossNet);
  body.append("model", model ?? DEFAULT_MODEL);
  body.append("record_currency", recordCurrency ?? DEFAULT_CURRENCY);
  if (ccy !== undefined && ccy !== DEFAULT_CURRENCY) body.append("ccy", ccy);
  if (factorSet !== undefined && factorSet !== DEFAULT_FACTOR_SET) body.append("factor_set", factorSet);
  return body;
}

/** Runs a monthly track record through the API. The result is held by the hook only: never cached, never stored. */
export function useUploadReport() {
  return useMutation({
    mutationFn: (input: UploadInput) => {
      startRun(UPLOAD_RUN);
      return streamReport(
        "/api/report/upload/stream",
        "/api/report/upload",
        { method: "POST", body: uploadBody(input) },
        { onStep: (step) => recordStep(UPLOAD_RUN, step), onFallback: () => recordFallback(UPLOAD_RUN) },
);
    },
    retry: false,
  });
}

/** The Asset Class Library: 44 lines with their proxies. It never changes while the server runs. */
export function useLibrary() {
  return useQuery({
    queryKey: ["portfolio", "library"],
    queryFn: ({ signal }) => apiRequest<AssetClassLibrary>("/api/portfolio/library", { signal }),
    staleTime: Infinity,
    retry: false,
  });
}

export interface PortfolioRunInput {
  tree: PortfolioTree;
  /** The factor model; the dashboard always sends it. */
  model: FactorModel;
  /** The reference currency of the report; USD when not given. */
  currency?: Currency;
  /** The factor set of the report; the US set when not given. */
  factorSet?: FactorSet;
  /** The range of the page: a preset, or custom dates (which win over it). */
  range: string | null;
  start: string | null;
  end: string | null;
}

/** The query of `POST /api/report/portfolio`: the model, and custom dates or the range preset. The tree is the body. */
export function portfolioQuery({ model, range, start, end }: PortfolioRunInput): Record<string, string> {
  return {
    model,
    ...(start || end ? { ...(start ? { start } : {}), ...(end ? { end } : {}) } : { range: range ?? DEFAULT_RANGE }),
  };
}

/**
 * The JSON body of `POST /api/report/portfolio`: the tree, plus `reference_currency` in the euro view
 * only and `factor_set` for the Europe set only (the set is a field of the tree).
 */
export function portfolioBody({
  tree,
  currency,
  factorSet,
}: PortfolioRunInput): PortfolioTree & { reference_currency?: Currency; factor_set?: FactorSet } {
  const euro = currency !== undefined && currency !== DEFAULT_CURRENCY;
  const europe = factorSet !== undefined && factorSet !== DEFAULT_FACTOR_SET;
  if (!euro && !europe) return tree;
  return { ...tree, ...(euro ? { reference_currency: currency } : {}), ...(europe ? { factor_set: factorSet } : {}) };
}

/** Runs a portfolio through the API. Like the upload, the result is held by the hook only and never cached. */
export function usePortfolioReport() {
  return useMutation({
    mutationFn: (input: PortfolioRunInput) => {
      startRun(PORTFOLIO_RUN);
      return streamReport(
        "/api/report/portfolio/stream",
        "/api/report/portfolio",
        { method: "POST", query: portfolioQuery(input), json: portfolioBody(input) },
        { onStep: (step) => recordStep(PORTFOLIO_RUN, step), onFallback: () => recordFallback(PORTFOLIO_RUN) },
);
    },
    retry: false,
  });
}
