/** The USD | EUR switch through the whole page (Sprint 3, S3-5): state, the request, and the rerun. */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { File as NodeFile } from "node:buffer";
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "./App";
import { LIBRARY } from "./portfolio/testLibrary";
import { CURRENCY_KEY } from "./state/currency";
import { resetRecentCache } from "./state/recent";
import { monthlyReport } from "./test/fixture";
import { requests, server, setupMockApi } from "./test/mockApi";

// The panels need ECharts; this file tests the page around them.
vi.mock("./components/report/ReportView", () => ({
  ReportView: (props: { report: { ticker: string; currency?: { reference: string } }; downloadHref: string | null }) => (
    <main data-testid="report-region">
      <span data-testid="report-ticker">{props.report.ticker}</span>
      <span data-testid="report-ccy">{props.report.currency?.reference ?? "none"}</span>
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

const radio = (name: string) => screen.getByRole("radio", { name }) as HTMLInputElement;
const reportRequests = () => requests.filter((r) => /^\/api\/report\/SPY\?/.test(r));

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

describe("currency state", () => {
  it("defaults to USD and sends no ccy", async () => {
    renderAt("/?t=SPY&range=3Y");
    await screen.findByTestId("report-ticker");
    expect(radio("USD").checked).toBe(true);
    expect(radio("EUR").checked).toBe(false);
    expect(requests).toContain("/api/report/SPY?range=3Y&model=ff6");
    expect(document.querySelector(".topbar .ccy-chip")?.textContent).toBe("USD");
  });

  it("lets ccy=EUR in the URL win over a stored USD, and sends ccy=EUR", async () => {
    window.localStorage.setItem(CURRENCY_KEY, "USD");
    renderAt("/?t=SPY&range=3Y&ccy=EUR");
    await screen.findByTestId("report-ticker");
    expect(radio("EUR").checked).toBe(true);
    expect(requests).toContain("/api/report/SPY?range=3Y&model=ff6&ccy=EUR");
    expect(window.location.search).toBe("?t=SPY&range=3Y&ccy=EUR");
    expect(document.querySelector(".topbar .ccy-chip")?.textContent).toBe("EUR");
    expect(screen.getByTestId("report-download").textContent).toBe("/api/report/SPY/html?range=3Y&model=ff6&ccy=EUR");
  });

  it("lets ccy=USD in the URL win over a stored EUR", async () => {
    window.localStorage.setItem(CURRENCY_KEY, "EUR");
    renderAt("/?t=SPY&range=3Y&ccy=USD");
    await screen.findByTestId("report-ticker");
    expect(radio("USD").checked).toBe(true);
    expect(requests).toContain("/api/report/SPY?range=3Y&model=ff6");
  });

  it("falls back to the stored choice when the URL says nothing", async () => {
    window.localStorage.setItem(CURRENCY_KEY, "EUR");
    renderAt("/?t=SPY&range=3Y");
    await screen.findByTestId("report-ticker");
    expect(radio("EUR").checked).toBe(true);
    expect(requests).toContain("/api/report/SPY?range=3Y&model=ff6&ccy=EUR");
  });

  it("works when browser storage throws", async () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    renderAt("/?t=SPY&range=3Y");
    await screen.findByTestId("report-ticker");
    expect(radio("USD").checked).toBe(true);
    fireEvent.click(radio("EUR"));
    expect(radio("EUR").checked).toBe(true);
    await waitFor(() => expect(reportRequests()).toContain("/api/report/SPY?range=3Y&model=ff6&ccy=EUR"));
  });
});

describe("switching the currency", () => {
  it("reruns the ticker report with ccy=EUR, remembers the choice, and puts it in the URL", async () => {
    server.use(
      http.get("*/api/report/:ticker", ({ params, request }) => {
        const eur = new URL(request.url).searchParams.get("ccy") === "EUR";
        const base = { ...monthlyReport, ticker: String(params["ticker"]) };
        return HttpResponse.json(eur ? { ...base, currency: { reference: "EUR", notes: [] } } : base);
      }),
    );
    renderAt("/?t=SPY&range=3Y");
    await screen.findByTestId("report-ticker");
    expect(screen.getByTestId("report-ccy").textContent).toBe("none");
    fireEvent.click(radio("EUR"));
    expect(window.location.search).toBe("?t=SPY&range=3Y&ccy=EUR");
    expect(window.localStorage.getItem(CURRENCY_KEY)).toBe("EUR");
    await waitFor(() => expect(screen.getByTestId("report-ccy").textContent).toBe("EUR"));
    expect(reportRequests()).toContain("/api/report/SPY?range=3Y&model=ff6&ccy=EUR");
    // Back to USD: the parameter leaves the URL and the stored choice follows.
    fireEvent.click(radio("USD"));
    expect(window.location.search).toBe("?t=SPY&range=3Y");
    expect(window.localStorage.getItem(CURRENCY_KEY)).toBe("USD");
    await waitFor(() => expect(screen.getByTestId("report-ccy").textContent).toBe("none"));
  });
});

describe("track record", () => {
  it("sends record_currency from the form and ccy=EUR from the switch, and reruns on a switch", async () => {
    const bodies: string[] = [];
    server.use(
      http.post("*/api/report/upload", async ({ request }) => {
        bodies.push(await request.text());
        return HttpResponse.json({ ...monthlyReport, ticker: "Fund" });
      }),
    );
    renderAt("/?m=track");
    const input = document.querySelector<HTMLInputElement>("input[type=file]");
    if (input === null) throw new Error("no file input");
    const file = new NodeFile(["date,return\n2021-01-31,0.012\n"], "record.csv", { type: "text/csv" }) as unknown as File;
    fireEvent.change(input, { target: { files: [file] } });
    fireEvent.click(within(screen.getByRole("group", { name: "Record is in" })).getByRole("radio", { name: "EUR" }));
    fireEvent.click(within(screen.getByRole("radiogroup", { name: "Currency" })).getByRole("radio", { name: "EUR" }));
    fireEvent.click(screen.getByRole("button", { name: "Factor it" }));
    await screen.findByTestId("report-ticker");
    expect(bodies).toHaveLength(1);
    expect(bodies[0]).toMatch(/name="record_currency"\r\n\r\nEUR\r\n/);
    expect(bodies[0]).toMatch(/name="ccy"\r\n\r\nEUR\r\n/);
    // Switching back to USD reruns the same record without ccy.
    fireEvent.click(within(screen.getByRole("radiogroup", { name: "Currency" })).getByRole("radio", { name: "USD" }));
    await waitFor(() => expect(bodies).toHaveLength(2));
    expect(bodies[1]).toMatch(/name="record_currency"\r\n\r\nEUR\r\n/);
    expect(bodies[1]).not.toMatch(/name="ccy"/);
  });
});

describe("portfolio", () => {
  const sent: { body: Record<string, unknown> }[] = [];

  function mockPortfolioApi() {
    server.use(
      http.get("*/api/portfolio/library", () => HttpResponse.json({ version: 1, lines: LIBRARY })),
      http.post("*/api/report/portfolio", async ({ request }) => {
        const body = (await request.json()) as Record<string, unknown>;
        sent.push({ body });
        return HttpResponse.json({
          ...monthlyReport,
          ticker: String(body["name"]),
          ...(body["reference_currency"] === "EUR" ? { currency: { reference: "EUR", notes: [] } } : {}),
        });
      }),
    );
  }

  it("sends reference_currency in the body, and reruns the folded report when the currency changes", async () => {
    sent.length = 0;
    mockPortfolioApi();
    renderAt("/?m=portfolio&ccy=EUR");
    const create = await screen.findByRole("button", { name: "Create portfolio" });
    await waitFor(() => expect((create as HTMLButtonElement).disabled).toBe(false));
    fireEvent.click(screen.getByRole("radio", { name: /^60\/40/ }));
    fireEvent.click(create);
    const live = within(await screen.findByRole("complementary", { name: "Live portfolio check" }));
    fireEvent.click(live.getByRole("button", { name: "Run backtest" }));
    await screen.findByTestId("report-ticker");
    expect(sent).toHaveLength(1);
    expect(sent[0]?.body["reference_currency"]).toBe("EUR");
    expect(screen.getByTestId("report-ccy").textContent).toBe("EUR");
    // Back to USD: the same portfolio runs again, without the field.
    fireEvent.click(within(screen.getByRole("radiogroup", { name: "Currency" })).getByRole("radio", { name: "USD" }));
    await waitFor(() => expect(sent).toHaveLength(2));
    expect(sent[1]?.body).not.toHaveProperty("reference_currency");
    await waitFor(() => expect(screen.getByTestId("report-ccy").textContent).toBe("none"));
  });
});
