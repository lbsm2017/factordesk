/** TanStack Query hooks and request helpers (dashboard spec DB6.2). */
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { dateLong } from "../format";
import { DEFAULT_MODEL, DEFAULT_RANGE, isSuggestQuery } from "../state/url";
import type { FactorModel, UrlState } from "../state/url";
import { ApiRequestError, apiRequest, NETWORK_ERROR } from "./client";
import type {
  ApiError,
  AssetClassLibrary,
  FactorDataStatus,
  FactorReport,
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

/** Query parameters of the report endpoints: custom dates win over a preset; neither means the default range. The model is always sent. */
export function reportParams(state: UrlState): Record<string, string> {
  if (state.start || state.end) {
    return {
      ...(state.start ? { start: state.start } : {}),
      ...(state.end ? { end: state.end } : {}),
      ...modelParam(state.model),
    };
  }
  return { range: state.range ?? DEFAULT_RANGE, ...modelParam(state.model) };
}

/** The `rangeOrDates` part of the report query key. */
export function reportRangeKey(state: UrlState): string {
  if (state.start || state.end) return `${state.start ?? ""}..${state.end ?? ""}`;
  return state.range ?? DEFAULT_RANGE;
}

/** `/api/report/{t}/html?{same range}` for the Download link (dashboard spec DB6.5). */
export function downloadHref(state: UrlState): string {
  if (state.ticker === null) return "#";
  const qs = new URLSearchParams(reportParams(state)).toString();
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

export function useRanges(ticker: string | null) {
  return useQuery({
    queryKey: ["ranges", ticker],
    queryFn: ({ signal }) =>
      apiRequest<RangeOptions>(`/api/report/${encodeURIComponent(ticker ?? "")}/ranges`, { signal }),
    enabled: ticker !== null,
    staleTime: 5 * 60_000,
    retry: false,
  });
}

export function useReport(state: UrlState) {
  const { ticker } = state;
  return useQuery({
    queryKey: ["report", ticker, reportRangeKey(state), state.model ?? DEFAULT_MODEL],
    queryFn: ({ signal }) =>
      apiRequest<FactorReport>(`/api/report/${encodeURIComponent(ticker ?? "")}`, {
        signal,
        query: reportParams(state),
      }),
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
}

/** The multipart body of `POST /api/report/upload`: the file, then the optional name and fee basis, and the model (always sent). */
export function uploadBody({ file, name, grossNet, model }: UploadInput): FormData {
  const body = new FormData();
  body.append("file", file);
  if (name.trim() !== "") body.append("name", name.trim());
  if (grossNet !== "") body.append("gross_net", grossNet);
  body.append("model", model ?? DEFAULT_MODEL);
  return body;
}

/** Runs a monthly track record through the API. The result is held by the hook only: never cached, never stored. */
export function useUploadReport() {
  return useMutation({
    mutationFn: (input: UploadInput) =>
      apiRequest<FactorReport>("/api/report/upload", { method: "POST", body: uploadBody(input) }),
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

/** Runs a portfolio through the API. Like the upload, the result is held by the hook only and never cached. */
export function usePortfolioReport() {
  return useMutation({
    mutationFn: (input: PortfolioRunInput) =>
      apiRequest<FactorReport>("/api/report/portfolio", {
        method: "POST",
        query: portfolioQuery(input),
        json: input.tree,
      }),
    retry: false,
  });
}
