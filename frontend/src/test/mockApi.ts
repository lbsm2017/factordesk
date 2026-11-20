/**
 * MSW server for tests that go through `fetch` (dashboard spec DB8.2): unhandled requests fail the
 * test, and the data is the committed mock report. Call `setupMockApi()` once at the top of a test file.
 */
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, vi } from "vitest";
import type { FactorDataStatus, RangeOptions, TickerSuggestion } from "../api/types";
import { cloneReport } from "./fixture";

export const mockStatus: FactorDataStatus = {
  available: true,
  first_date: "1963-07-01",
  last_date: "2026-09-30",
  days_behind: 49,
  last_download_at: "2026-11-01T00:00:00Z",
  stale: false,
  source_url: "https://example.invalid/factors.zip",
};

export function mockRanges(ticker: string): RangeOptions {
  return {
    ticker,
    first_return_date: "2024-08-08",
    last_price_date: "2026-11-13",
    factors_last_date: "2026-09-30",
    min_obs: 504,
    options: [
      { preset: "3Y", start: "2023-09-30", n_obs: 559, available: true, reason: null },
      {
        preset: "5Y",
        start: "2021-09-30",
        n_obs: 559,
        available: false,
        reason: `5Y has 400 trading days; a regression needs at least 504.`,
      },
      {
        preset: "10Y",
        start: "2016-10-01",
        n_obs: 559,
        available: false,
        reason: "10Y needs prices from 1 Oct 2016, but the history starts 8 Aug 2024. Full history covers all of it.",
      },
      { preset: "FULL", start: null, n_obs: 559, available: true, reason: null },
    ],
  };
}

export const mockTickers: TickerSuggestion[] = [
  { ticker: "SPY", last_fetched: "2026-11-13", name: null },
  { ticker: "SPXL", last_fetched: "2026-11-10", name: null },
  { ticker: "QQQ", last_fetched: "2026-11-12", name: null },
];

/** Every request path (with query) the app made, in order. */
export const requests: string[] = [];

let status = mockStatus;
let refreshed: FactorDataStatus | null = null;
export function setRefreshResult(next: FactorDataStatus | null): void {
  refreshed = next;
}

function noStream(): Response {
  return HttpResponse.json({ code: "not_found", message: "Not found.", action: "Check the address." }, { status: 404 });
}

/** One server-sent event block. */
export function sse(event: string, data: unknown): string {
  return `event: ${event}
data: ${JSON.stringify(data)}

`;
}

/** A `text/event-stream` answer made of ready blocks (see `sse`). */
export function sseResponse(blocks: string[]): Response {
  return new Response(blocks.join(""), { status: 200, headers: { "Content-Type": "text/event-stream" } });
}

export const handlers = [
  http.get("*/api/factors/status", () => HttpResponse.json(status)),
  http.post("*/api/factors/refresh", () => {
    if (refreshed !== null) status = refreshed;
    return HttpResponse.json(status);
  }),
  http.get("*/api/tickers", ({ request }) => {
    const q = (new URL(request.url).searchParams.get("q") ?? "").toUpperCase();
    return HttpResponse.json({ items: mockTickers.filter((t) => t.ticker.startsWith(q)) });
  }),
  http.get("*/api/report/:ticker/ranges", ({ params }) => HttpResponse.json(mockRanges(String(params["ticker"])))),
  // The default backend has no stream routes: a 404 sends the app to the plain endpoint (no step list).
  http.get("*/api/report/:ticker/stream", noStream),
  http.post("*/api/report/portfolio/stream", noStream),
  http.post("*/api/report/upload/stream", noStream),
  http.get("*/api/report/:ticker", ({ params }) => {
    const ticker = String(params["ticker"]);
    if (ticker === "XYZ") {
      return HttpResponse.json(
        { code: "unknown_ticker", message: "No prices were returned for XYZ.", action: "Check the ticker symbol." },
        { status: 404 },
      );
    }
    return HttpResponse.json({ ...cloneReport(), ticker });
  }),
];

export const server = setupServer(...handlers);

export function setupMockApi(): void {
  beforeAll(() => {
    server.listen({ onUnhandledFrame: "error" });
    // Node's fetch rejects relative URLs; the browser resolves them against the page.
    const interceptedFetch = globalThis.fetch;
    vi.stubGlobal("fetch", (input: RequestInfo | URL, init?: RequestInit) => {
      const target = typeof input === "string" ? new URL(input, window.location.href) : input;
      requests.push(typeof input === "string" ? input : String(input));
      return interceptedFetch(target, init);
    });
  });
  afterEach(() => {
    server.resetHandlers();
    requests.length = 0;
    status = mockStatus;
    refreshed = null;
  });
  afterAll(() => {
    server.close();
    vi.unstubAllGlobals();
  });
}
