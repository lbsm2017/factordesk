/** The US | Europe switch through the whole page (Sprint 4, S4-4): state, URL, and the factor_set of every request kind. */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { File as NodeFile } from "node:buffer";
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "./App";
import { LIBRARY } from "./portfolio/testLibrary";
import { resetRecentCache } from "./state/recent";
import { monthlyReport } from "./test/fixture";
import { requests, server, setupMockApi, sse } from "./test/mockApi";

// The panels need ECharts; this file tests the page around them.
vi.mock("./components/report/ReportView", () => ({
  ReportView: (props: { report: { ticker: string }; downloadHref: string | null }) => (
    <main data-testid="report-region">
      <span data-testid="report-ticker">{props.report.ticker}</span>
      <span data-testid="report-download">{String(props.downloadHref)}</span>
    </main>
  ),
}));

setupMockApi();

function renderAt(url: string) {
  window.history.replaceState(null, "", url);
  const client = new QueryClient({ defaultOptions: { queries: { gcTime: 0 } } });
  return render(
    <QueryClientProvider client={client}>
      <App />
    </QueryClientProvider>,
  );
}

const group = () => within(screen.getByRole("radiogroup", { name: "Factor set" }));
const radio = (name: string) => group().getByRole("radio", { name }) as HTMLInputElement;
const plain = () => requests.filter((r) => /^\/api\/report\/SPY\?/.test(r));

beforeAll(async () => {
  // jsdom's FormData cannot be sent by Node's fetch; use Node's own class (see App.track.test.tsx).
  const parsed = await new Response("a=b", { headers: { "content-type": "application/x-www-form-urlencoded" } }).formData();
  vi.stubGlobal("FormData", parsed.constructor);
});

beforeEach(() => {
  window.localStorage.clear();
  resetRecentCache();
});
afterEach(() => vi.restoreAllMocks());

describe("factor set state", () => {
  it("defaults to US, sends no factor_set and shows no Europe chip", async () => {
    renderAt("/?t=SPY&range=3Y");
    await screen.findByTestId("report-ticker");
    expect(radio("US").checked).toBe(true);
    expect(radio("Europe").checked).toBe(false);
    expect(requests).toContain("/api/report/SPY?range=3Y&model=ff6");
    expect(requests.some((r) => r.includes("factor_set"))).toBe(false);
    expect(document.querySelector(".topbar .set-chip")).toBeNull();
    expect(screen.queryByText(/Macro, energy and world beta keep their US inputs/)).toBeNull();
  });

  it("reads fs=europe from the URL and sends it to the report, the ranges and the download link", async () => {
    renderAt("/?t=SPY&range=3Y&fs=europe");
    await screen.findByTestId("report-ticker");
    expect(radio("Europe").checked).toBe(true);
    expect(requests).toContain("/api/report/SPY?range=3Y&model=ff6&factor_set=europe");
    await waitFor(() => expect(requests).toContain("/api/report/SPY/ranges?factor_set=europe"));
    expect(screen.getByTestId("report-download").textContent).toBe("/api/report/SPY/html?range=3Y&model=ff6&factor_set=europe");
    expect(document.querySelector(".topbar .set-chip")?.textContent).toBe("Europe");
    expect(screen.getByText(/Macro, energy and world beta keep their US inputs/)).toBeTruthy();
    expect(window.location.search).toBe("?t=SPY&range=3Y&fs=europe");
  });

  it("asks the stream endpoint for the Europe set too", async () => {
    server.use(
      http.get("*/api/report/:ticker/stream", ({ params }) => {
        const body = sse("report", { ...monthlyReport, ticker: String(params["ticker"]) });
        return new Response(body, { status: 200, headers: { "Content-Type": "text/event-stream" } });
      }),
    );
    renderAt("/?t=SPY&range=3Y&fs=europe");
    await screen.findByTestId("report-ticker");
    expect(requests).toContain("/api/report/SPY/stream?range=3Y&model=ff6&factor_set=europe");
  });
});

describe("switching the factor set", () => {
  it("reruns the ticker report with factor_set=europe and puts it in the URL", async () => {
    renderAt("/?t=SPY&range=3Y");
    await screen.findByTestId("report-ticker");
    fireEvent.click(radio("Europe"));
    expect(window.location.search).toBe("?t=SPY&range=3Y&fs=europe");
    await waitFor(() => expect(plain()).toContain("/api/report/SPY?range=3Y&model=ff6&factor_set=europe"));
    expect(document.querySelector(".topbar .set-chip")?.textContent).toBe("Europe");
    // Back to US: the parameter leaves the URL and the chip leaves the top bar.
    fireEvent.click(radio("US"));
    expect(window.location.search).toBe("?t=SPY&range=3Y");
    expect(document.querySelector(".topbar .set-chip")).toBeNull();
  });

  it("keeps the set when the currency changes", async () => {
    renderAt("/?t=SPY&range=3Y&fs=europe");
    await screen.findByTestId("report-ticker");
    fireEvent.click(within(screen.getByRole("radiogroup", { name: "Currency" })).getByRole("radio", { name: "EUR" }));
    expect(window.location.search).toBe("?t=SPY&range=3Y&ccy=EUR&fs=europe");
    await waitFor(() => expect(plain()).toContain("/api/report/SPY?range=3Y&model=ff6&ccy=EUR&factor_set=europe"));
  });
});

describe("track record", () => {
  it("sends factor_set in the upload form and reruns the same record when the set changes", async () => {
    const bodies: string[] = [];
    server.use(
      http.post("*/api/report/upload", async ({ request }) => {
        bodies.push(await request.text());
        return HttpResponse.json({ ...monthlyReport, ticker: "Fund" });
      }),
    );
    renderAt("/?m=track&fs=europe");
    const input = document.querySelector<HTMLInputElement>("input[type=file]");
    if (input === null) throw new Error("no file input");
    const file = new NodeFile(["date,return\n2021-01-31,0.012\n"], "record.csv", { type: "text/csv" }) as unknown as File;
    fireEvent.change(input, { target: { files: [file] } });
    fireEvent.click(screen.getByRole("button", { name: "Factor it" }));
    await screen.findByTestId("report-ticker");
    expect(bodies).toHaveLength(1);
    expect(bodies[0]).toMatch(/name="factor_set"\r\n\r\neurope\r\n/);
    fireEvent.click(radio("US"));
    await waitFor(() => expect(bodies).toHaveLength(2));
    expect(bodies[1]).not.toMatch(/name="factor_set"/);
  });
});

describe("portfolio", () => {
  it("sends factor_set in the body and reruns the folded report when the set changes", async () => {
    const sent: Record<string, unknown>[] = [];
    server.use(
      http.get("*/api/portfolio/library", () => HttpResponse.json({ version: 1, lines: LIBRARY })),
      http.post("*/api/report/portfolio", async ({ request }) => {
        const body = (await request.json()) as Record<string, unknown>;
        sent.push(body);
        return HttpResponse.json({ ...monthlyReport, ticker: String(body["name"]) });
      }),
    );
    renderAt("/?m=portfolio&fs=europe");
    const create = await screen.findByRole("button", { name: "Create portfolio" });
    await waitFor(() => expect((create as HTMLButtonElement).disabled).toBe(false));
    fireEvent.click(screen.getByRole("radio", { name: /^60\/40/ }));
    fireEvent.click(create);
    const live = within(await screen.findByRole("complementary", { name: "Live portfolio check" }));
    fireEvent.click(live.getByRole("button", { name: "Run backtest" }));
    await screen.findByTestId("report-ticker");
    expect(sent).toHaveLength(1);
    expect(sent[0]?.["factor_set"]).toBe("europe");
    expect(document.querySelector(".topbar .set-chip")?.textContent).toBe("Europe");
    fireEvent.click(radio("US"));
    await waitFor(() => expect(sent).toHaveLength(2));
    expect(sent[1]).not.toHaveProperty("factor_set");
  });
});
