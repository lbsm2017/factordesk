/** Thin fetch wrapper. Any non-2xx answer becomes an ApiRequestError that holds an ApiError. */
import type { ApiError, ErrorCode } from "./types";

export class ApiRequestError extends Error {
  readonly apiError: ApiError;
  readonly status: number | null;

  constructor(apiError: ApiError, status: number | null) {
    super(apiError.message);
    this.name = "ApiRequestError";
    this.apiError = apiError;
    this.status = status;
  }
}

export const NETWORK_ERROR: ApiError = {
  code: "network",
  message: "The factordesk server did not answer.",
  action: "Check that 'factordesk serve' is running, then try again.",
};

const KNOWN_CODES: readonly ErrorCode[] = [
  "invalid_ticker",
  "unknown_ticker",
  "bad_range",
  "insufficient_history",
  "degenerate_input",
  "unsupported_currency",
  "factor_data_invalid",
  "network",
  "upstream_refused",
  "not_found",
  "internal",
  "bad_request",
  "invalid_upload",
  "upload_too_large",
  "invalid_portfolio",
];

function isApiError(value: unknown): value is ApiError {
  if (typeof value !== "object" || value === null) return false;
  const v = value as Record<string, unknown>;
  return (
    typeof v["message"] === "string" &&
    typeof v["action"] === "string" &&
    typeof v["code"] === "string" &&
    (KNOWN_CODES as readonly string[]).includes(v["code"])
  );
}

function internalError(status: number): ApiError {
  return {
    code: "internal",
    message: `The server answered with an unexpected response (status ${status}).`,
    action: "Try again. If it happens again, report it with this page's address.",
  };
}

export type Query = Record<string, string | number | undefined | null>;

/** Build a path plus query string; empty values are dropped. */
export function apiUrl(path: string, query?: Query): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query ?? {})) {
    if (value !== undefined && value !== null && value !== "") params.set(key, String(value));
  }
  const qs = params.toString();
  return qs ? `${path}?${qs}` : path;
}

export interface RequestOptions {
  method?: "GET" | "POST";
  query?: Query;
  signal?: AbortSignal;
  /** A multipart body (the track-record upload); the browser sets the content type and boundary. */
  body?: FormData;
  /** A JSON body (the portfolio run); sent with the JSON content type. Not together with `body`. */
  json?: unknown;
}

export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetch(apiUrl(path, options.query), {
      method: options.method ?? "GET",
      headers: {
        Accept: "application/json",
        ...(options.json !== undefined ? { "Content-Type": "application/json" } : {}),
      },
      ...(options.body ? { body: options.body } : {}),
      ...(options.json !== undefined ? { body: JSON.stringify(options.json) } : {}),
      ...(options.signal ? { signal: options.signal } : {}),
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    throw new ApiRequestError(NETWORK_ERROR, null);
  }
  let body: unknown;
  try {
    body = await response.json();
  } catch {
    body = undefined;
  }
  if (!response.ok) {
    throw new ApiRequestError(isApiError(body) ? body : internalError(response.status), response.status);
  }
  if (body === undefined) throw new ApiRequestError(internalError(response.status), response.status);
  return body as T;
}
