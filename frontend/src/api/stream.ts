/**
 * The progress stream of a report run: server-sent events read with `fetch` (one parser for the
 * three endpoints `GET /api/report/{ticker}/stream`, `POST /api/report/portfolio/stream` and
 * `POST /api/report/upload/stream`).
 *
 * Events: `step` (a `ProgressStep`), `report` (the `FactorReport`) and `error` (an `ApiErrorEvent`).
 * Comment lines (`: keep-alive`) are skipped. If the stream cannot be used before its first event
 * (no stream route, a network failure, an answer that is not an event stream), the plain endpoint
 * is called instead and the run has no step list. A refusal with a JSON `ApiError` body (a bad
 * value, a file over 1 MB) is an error, not a reason to fall back.
 */
import { ApiRequestError, apiRequest, apiUrl, internalError, isApiError, NETWORK_ERROR } from "./client";
import type { Query, RequestOptions } from "./client";
import type { FactorReport, ProgressStep, ProgressStepId } from "./types";

export interface SseMessage {
  /** The `event:` field; `message` when the block has none. */
  event: string;
  /** The `data:` lines joined with a line feed. */
  data: string;
}

/**
 * Splits a byte stream into server-sent event messages. Handles chunks that end anywhere (inside a
 * line, inside a multi-byte character, between a carriage return and its line feed), `\n`, `\r\n`
 * and `\r` line ends, comment lines and blocks with several `data:` lines.
 */
export async function* parseSse(body: ReadableStream<Uint8Array>): AsyncGenerator<SseMessage> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let event = "";
  let data: string[] = [];
  let pending = false;

  const line = (text: string): SseMessage | null => {
    if (text === "") {
      const out = pending ? { event: event || "message", data: data.join("\n") } : null;
      event = "";
      data = [];
      pending = false;
      return out;
    }
    if (text.startsWith(":")) return null;
    const colon = text.indexOf(":");
    const field = colon === -1 ? text : text.slice(0, colon);
    let value = colon === -1 ? "" : text.slice(colon + 1);
    if (value.startsWith(" ")) value = value.slice(1);
    if (field === "event") {
      event = value;
      pending = true;
    } else if (field === "data") {
      data.push(value);
      pending = true;
    }
    return null;
  };

  try {
    for (;;) {
      const { done, value } = await reader.read();
      buffer += decoder.decode(value, { stream: !done });
      // A trailing carriage return may be the first half of a CRLF: keep it for the next chunk.
      const hold = !done && buffer.endsWith("\r") ? 1 : 0;
      const usable = buffer.slice(0, buffer.length - hold);
      const parts = usable.split(/\r\n|\n|\r/);
      buffer = (parts.pop() ?? "") + buffer.slice(buffer.length - hold);
      for (const part of parts) {
        const message = line(part);
        if (message !== null) yield message;
      }
      if (done) break;
    }
    if (buffer !== "") {
      const message = line(buffer);
      if (message !== null) yield message;
    }
    const last = line("");
    if (last !== null) yield last;
  } finally {
    reader.releaseLock();
  }
}

const STEP_IDS: readonly ProgressStepId[] = ["prices", "fx", "factors", "models", "sections"];

function isStep(value: unknown): value is ProgressStep {
  if (typeof value !== "object" || value === null) return false;
  const v = value as Record<string, unknown>;
  return (
    typeof v["step"] === "string" &&
    (STEP_IDS as readonly string[]).includes(v["step"]) &&
    typeof v["label"] === "string" &&
    typeof v["index"] === "number" &&
    typeof v["total"] === "number"
  );
}

function parseJson(text: string): unknown {
  try {
    return JSON.parse(text) as unknown;
  } catch {
    return undefined;
  }
}

/** The `error` event as a thrown error: the ApiError, and the status the plain endpoint would send. */
function errorFromEvent(text: string): ApiRequestError {
  const body = parseJson(text);
  const status = typeof body === "object" && body !== null ? (body as { status?: unknown }).status : undefined;
  const code = typeof status === "number" ? status : null;
  return new ApiRequestError(isApiError(body) ? body : internalError(code ?? 500), code);
}

export interface StreamHooks {
  /** A `step` event arrived. */
  onStep?: (step: ProgressStep) => void;
  /** The stream could not be used before its first event, so the plain endpoint runs instead. */
  onFallback?: () => void;
  signal?: AbortSignal;
}

async function plainJsonError(response: Response): Promise<ApiRequestError> {
  let body: unknown;
  try {
    body = await response.json();
  } catch {
    body = undefined;
  }
  return new ApiRequestError(isApiError(body) ? body : internalError(response.status), response.status);
}

/**
 * Runs one report request through its stream endpoint and resolves with the report. `plainPath`
 * is the plain endpoint with the same parameters, used when the stream cannot be used.
 */
export async function streamReport(
  streamPath: string,
  plainPath: string,
  options: RequestOptions,
  hooks: StreamHooks = {},
): Promise<FactorReport> {
  const fallback = (): Promise<FactorReport> => {
    hooks.onFallback?.();
    return apiRequest<FactorReport>(plainPath, options);
  };
  const query: Query | undefined = options.query;
  let response: Response;
  try {
    response = await fetch(apiUrl(streamPath, query), {
      method: options.method ?? "GET",
      headers: {
        Accept: "text/event-stream",
        ...(options.json !== undefined ? { "Content-Type": "application/json" } : {}),
      },
      ...(options.body ? { body: options.body } : {}),
      ...(options.json !== undefined ? { body: JSON.stringify(options.json) } : {}),
      ...(hooks.signal ? { signal: hooks.signal } : {}),
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    return fallback();
  }

  if (!response.ok) {
    if (response.status === 404 || response.status === 405) return fallback();
    throw await plainJsonError(response);
  }
  const type = response.headers.get("content-type") ?? "";
  if (!type.includes("text/event-stream") || response.body === null) return fallback();

  let seen = false;
  try {
    for await (const message of parseSse(response.body)) {
      seen = true;
      if (message.event === "step") {
        const step = parseJson(message.data);
        if (isStep(step)) hooks.onStep?.(step);
      } else if (message.event === "report") {
        const report = parseJson(message.data);
        if (typeof report === "object" && report !== null) return report as FactorReport;
        throw new ApiRequestError(internalError(response.status), response.status);
      } else if (message.event === "error") {
        throw errorFromEvent(message.data);
      }
    }
  } catch (error) {
    if (error instanceof ApiRequestError) throw error;
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    if (!seen) return fallback();
    throw new ApiRequestError(NETWORK_ERROR, null);
  }
  if (!seen) return fallback();
  throw new ApiRequestError(NETWORK_ERROR, null);
}
