import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "./App";
import { RECENT_KEY, resetRecentCache } from "./state/recent";
import { cloneReport } from "./test/fixture";
import { mockStatus, requests, server, setRefreshResult, setupMockApi } from "./test/mockApi";

// The panels belong to other tickets and need ECharts; this file tests the shell around them.
vi.mock("./components/report/ReportView", () => ({
  ReportView: (props: {
    report: { ticker: string };
    downloadHref: string;
    win: number | null;
    busy?: boolean;
    onWinChange: (win: 126 | 252) => void;
  }) => (
    <main data-testid="report-region" aria-busy={props.busy ?? false}>
      <span data-testid="report-ticker">{props.report.ticker}</span>
      <a href={props.downloadHref}>Download report</a>
      <span data-testid="report-win">{String(props.win)}</span>
      <button type="button" onClick={() => props.onWinChange(126)}>
        win 126
      </button>
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

const reportCalls = () => requests.filter((r) => /^\/api\/report\/[^/]+(\?|$)/.test(r));

beforeEach(() => {
  window.localStorage.clear();
  resetRecentCache();
});

describe("landing", () => {
  it("shows the strip with focus in the search field, the factor-data line and one sentence", async () => {
    renderAt("/");
    expect(screen.getByText("Type a ticker and press Factor it, for example SPY.")).toBeTruthy();
    expect(document.activeElement).toBe(screen.getByRole("combobox", { name: "Ticker" }));
    expect(await screen.findByText("Factor data ends 30 Sep 2026, so later dates cannot be chosen.")).toBeTruthy();
    expect(reportCalls()).toEqual([]);
    expect(screen.queryByTestId("report-region")).toBeNull();
  });

  it("offers recent tickers, as chips and in the list, and opens one", async () => {
    window.localStorage.setItem(RECENT_KEY, JSON.stringify(["QQQ", "SPY"]));
    resetRecentCache();
    renderAt("/");
    fireEvent.click(screen.getByRole("button", { name: "QQQ" }));
    expect(window.location.search).toBe("?t=QQQ");
    expect(await screen.findByTestId("report-ticker")).toHaveProperty("textContent", "QQQ");
  });
});

describe("first load", () => {
  it("shows the page frame with the ticker from the URL, then the report", async () => {
    renderAt("/?t=SPY&range=3Y");
    const frame = screen.getByTestId("loading-frame");
    expect(frame.getAttribute("aria-busy")).toBe("true");
    expect(frame.querySelector(".ticker")?.textContent).toBe("SPY");
    expect(frame.querySelectorAll(".abar > div")).toHaveLength(4);
    expect(frame.querySelectorAll("section.panel").length).toBeGreaterThan(5);
    // The sidebar stays outside <main> in every state.
    expect(document.querySelector("aside#sidebar main")).toBeNull();
    expect(frame.closest("#report")).not.toBeNull();

    expect(await screen.findByTestId("report-ticker")).toHaveProperty("textContent", "SPY");
    expect(screen.queryByTestId("loading-frame")).toBeNull();
    expect(requests).toContain("/api/report/SPY?range=3Y&model=ff6");
    expect(requests).toContain("/api/report/SPY/ranges");
  });

  it("opens a ticker without range and model on 10Y and FF6, and always sends the model", async () => {
    renderAt("/?t=SPY");
    await screen.findByTestId("report-ticker");
    expect(window.location.search).toBe("?t=SPY");
    expect(requests).toContain("/api/report/SPY?range=10Y&model=ff6");
    expect(screen.getByRole("radio", { name: "10Y" })).toHaveProperty("checked", true);
    expect(within(screen.getByRole("group", { name: "Factor model" })).getByRole("radio", { name: "FF6" })).toHaveProperty("checked", true);
  });

  it("keeps an old URL with explicit params: its range and model are requested as written", async () => {
    renderAt("/?t=SPY&range=FULL&model=ff5&win=126&stats=1");
    await screen.findByTestId("report-ticker");
    expect(window.location.search).toBe("?t=SPY&range=FULL&win=126&stats=1&model=ff5");
    expect(requests).toContain("/api/report/SPY?range=FULL&model=ff5");
    expect(screen.getByRole("radio", { name: "Full history" })).toHaveProperty("checked", true);
    expect(within(screen.getByRole("group", { name: "Factor model" })).getByRole("radio", { name: "FF5" })).toHaveProperty("checked", true);
  });

  it("writes model=ff5 to the URL when FF5 is chosen, and drops it again for FF6", async () => {
    renderAt("/?t=SPY");
    await screen.findByTestId("report-ticker");
    const toggle = within(screen.getByRole("group", { name: "Factor model" }));
    fireEvent.click(toggle.getByRole("radio", { name: "FF5" }));
    expect(window.location.search).toBe("?t=SPY&model=ff5");
    await waitFor(() => expect(requests).toContain("/api/report/SPY?range=10Y&model=ff5"));
    fireEvent.click(toggle.getByRole("radio", { name: "FF6" }));
    expect(window.location.search).toBe("?t=SPY");
  });

  it("passes custom dates through and points the download at the same range", async () => {
    renderAt("/?t=SPY&start=2023-01-01&end=2026-09-30");
    await screen.findByTestId("report-ticker");
    expect(requests).toContain("/api/report/SPY?start=2023-01-01&end=2026-09-30&model=ff6");
    expect(screen.getByRole("link", { name: "Download report" }).getAttribute("href")).toBe(
      "/api/report/SPY/html?start=2023-01-01&end=2026-09-30&model=ff6",
    );
  });

  it("cleans an invalid URL with replaceState and does not add a history entry", async () => {
    const before = window.history.length;
    renderAt("/?t=spy&range=junk&win=7");
    expect(window.location.search).toBe("?t=SPY");
    await screen.findByTestId("report-ticker");
    expect(window.history.length).toBe(before);
  });

  it("fills the analysed-range label and the date fields from the report", async () => {
    renderAt("/?t=SPY&range=3Y");
    await screen.findByTestId("report-ticker");
    expect(document.querySelector("#analysed-range .cov-line")?.textContent).toContain("8 Aug 2024 → 30 Sep 2026");
    expect(document.querySelector("#analysed-range details")?.textContent).toContain(
      "Analysed 8 Aug 2024 to 30 Sep 2026, 559 trading days.",
    );
    expect((screen.getByLabelText("From") as HTMLInputElement).value).toBe("2024-08-08");
  });

  it("disables a chip, says so in one line and keeps the reason in the details, once the ranges arrive", async () => {
    renderAt("/?t=SPY");
    expect(await screen.findByText(/need more history\./)).toBeTruthy();
    expect(screen.getByText("5Y has 400 trading days; a regression needs at least 504.")).toBeTruthy();
    expect((screen.getByRole("radio", { name: "5Y" }) as HTMLInputElement).disabled).toBe(true);
  });

  it("remembers a ticker only after its report succeeded", async () => {
    renderAt("/?t=XYZ");
    await screen.findByTestId("report-error");
    expect(window.localStorage.getItem(RECENT_KEY)).toBeNull();
    act(() => window.history.pushState(null, "", "/?t=SPY"));
    act(() => window.dispatchEvent(new PopStateEvent("popstate")));
    await screen.findByTestId("report-ticker");
    await waitFor(() => expect(JSON.parse(window.localStorage.getItem(RECENT_KEY) ?? "[]")).toEqual(["SPY"]));
  });
});

describe("errors", () => {
  it("replaces the report with the message and the action, in plain sentences", async () => {
    renderAt("/?t=XYZ");
    const notice = await screen.findByTestId("report-error");
    expect(notice.textContent).toContain("No prices were returned for XYZ.");
    expect(notice.textContent).toContain("Check the ticker symbol.");
    expect(screen.queryByTestId("report-region")).toBeNull();
    expect(screen.queryByTestId("loading-frame")).toBeNull();
  });

  it("shows the API's named cause for zero aligned rows unchanged (F14)", async () => {
    const body = {
      code: "insufficient_history",
      message:
        "SPY has 0 trading days in this range that line up with the factor data; at least 504 (about two years) are needed: every price in the requested range is missing.",
      action: "Choose a longer range or Full history.",
    };
    server.use(http.get("*/api/report/:ticker", () => HttpResponse.json(body, { status: 422 })));
    renderAt("/?t=SPY");
    const notice = await screen.findByTestId("report-error");
    expect(notice.querySelector(".notice-sum")?.textContent).toBe(`Error: ${body.message}`);
    expect(notice.querySelector(".notice-do")?.textContent).toBe(body.action);
  });

  it("never shows the previous report under an error", async () => {
    renderAt("/?t=SPY");
    await screen.findByTestId("report-ticker");
    const input = screen.getByRole("combobox", { name: "Ticker" });
    fireEvent.change(input, { target: { value: "xyz" } });
    fireEvent.keyDown(input, { key: "Enter" });
    await screen.findByTestId("report-error");
    expect(screen.queryByTestId("report-ticker")).toBeNull();
  });

  it("explains a missing server in the words of the spec", async () => {
    server.use(http.get("*/api/report/:ticker", () => HttpResponse.error()));
    renderAt("/?t=SPY");
    const notice = await screen.findByTestId("report-error");
    expect(notice.textContent).toContain("The factordesk server did not answer.");
    expect(notice.textContent).toContain("Check that 'factordesk serve' is running, then try again.");
  });
});

describe("committing changes", () => {
  it("pushes a history entry on submit, keeps the range, and follows Back", async () => {
    renderAt("/?t=SPY&range=3Y");
    await screen.findByTestId("report-ticker");
    const before = window.history.length;
    const input = screen.getByRole("combobox", { name: "Ticker" });
    fireEvent.change(input, { target: { value: "qqq" } });
    expect(window.location.search).toBe("?t=SPY&range=3Y"); // typing does not change the URL
    fireEvent.keyDown(input, { key: "Enter" });
    expect(window.location.search).toBe("?t=QQQ&range=3Y");
    expect(window.history.length).toBe(before + 1);
    await waitFor(() => expect(screen.getByTestId("report-ticker").textContent).toBe("QQQ"));

    act(() => window.history.back());
    await waitFor(() => expect(window.location.search).toBe("?t=SPY&range=3Y"));
    await waitFor(() => expect(screen.getByTestId("report-ticker").textContent).toBe("SPY"));
    expect((screen.getByRole("combobox", { name: "Ticker" }) as HTMLInputElement).value).toBe("SPY");
  });

  it("does not push the same state twice", async () => {
    renderAt("/?t=SPY&range=3Y");
    await screen.findByTestId("report-ticker");
    const before = window.history.length;
    fireEvent.click(screen.getByRole("radio", { name: "3Y" }));
    expect(window.history.length).toBe(before);
  });

  it("commits a chip to the URL and requests that range", async () => {
    renderAt("/?t=SPY&range=3Y");
    await screen.findByTestId("report-ticker");
    fireEvent.click(screen.getByRole("radio", { name: "Full history" }));
    expect(window.location.search).toBe("?t=SPY&range=FULL");
    await waitFor(() => expect(requests).toContain("/api/report/SPY?range=FULL&model=ff6"));
  });

  it("commits custom dates, which clears the chip", async () => {
    renderAt("/?t=SPY&range=3Y");
    await screen.findByTestId("report-ticker");
    fireEvent.change(screen.getByLabelText("From"), { target: { value: "2025-01-02" } });
    expect(window.location.search).toBe("?t=SPY&range=3Y");
    fireEvent.blur(screen.getByLabelText("From"));
    expect(window.location.search).toBe("?t=SPY&start=2025-01-02&end=2026-09-30");
    for (const radio of within(screen.getByRole("group", { name: "Date range" })).getAllByRole("radio")) {
      expect((radio as HTMLInputElement).checked).toBe(false);
    }
    await waitFor(() => expect(requests).toContain("/api/report/SPY?start=2025-01-02&end=2026-09-30&model=ff6"));
  });

  it("writes the rolling window to the URL", async () => {
    renderAt("/?t=SPY&range=3Y");
    await screen.findByTestId("report-ticker");
    expect(screen.getByTestId("report-win").textContent).toBe("null");
    fireEvent.click(screen.getByRole("button", { name: "win 126" }));
    expect(window.location.search).toBe("?t=SPY&range=3Y&win=126");
    expect(screen.getByTestId("report-win").textContent).toBe("126");
  });

  it("sends nothing for an invalid ticker and says why", async () => {
    renderAt("/?t=SPY");
    await screen.findByTestId("report-ticker");
    const calls = reportCalls().length;
    const input = screen.getByRole("combobox", { name: "Ticker" });
    fireEvent.change(input, { target: { value: "BRK B" } });
    fireEvent.keyDown(input, { key: "Enter" });
    expect(screen.getByRole("alert").textContent).toContain("BRK B is not a valid ticker.");
    expect(window.location.search).toBe("?t=SPY");
    expect(reportCalls()).toHaveLength(calls);
  });

  it("keeps the previous report on screen, marked busy, while a new one loads", async () => {
    let release: () => void = () => undefined;
    const gate = new Promise<void>((resolve) => {
      release = resolve;
    });
    server.use(
      http.get("*/api/report/QQQ", async () => {
        await gate;
        return HttpResponse.json({ ...cloneReport(), ticker: "QQQ" });
      }),
    );
    renderAt("/?t=SPY");
    await screen.findByTestId("report-ticker");
    const input = screen.getByRole("combobox", { name: "Ticker" });
    fireEvent.change(input, { target: { value: "QQQ" } });
    fireEvent.keyDown(input, { key: "Enter" });
    await waitFor(() => expect(screen.getByTestId("report-region").getAttribute("aria-busy")).toBe("true"));
    expect(screen.getByTestId("report-ticker").textContent).toBe("SPY");
    expect(screen.getAllByRole("status").map((s) => s.textContent)).toContain("Loading the report.");
    release();
    await waitFor(() => expect(screen.getByTestId("report-ticker").textContent).toBe("QQQ"));
    expect(screen.getByTestId("report-region").getAttribute("aria-busy")).toBe("false");
  });
});

describe("Show statistics", () => {
  it("starts off, turns on with stats=1 replacing the history entry, and keeps it across a range change", async () => {
    renderAt("/?t=SPY");
    await screen.findByTestId("report-ticker");
    const toggle = screen.getByRole("switch", { name: "Show statistics" });
    expect(toggle.getAttribute("aria-checked")).toBe("false");
    const before = window.history.length;
    fireEvent.click(toggle);
    expect(toggle.getAttribute("aria-checked")).toBe("true");
    expect(window.location.search).toBe("?t=SPY&stats=1");
    expect(window.history.length).toBe(before);
    fireEvent.click(screen.getByRole("radio", { name: "3Y" }));
    expect(window.location.search).toBe("?t=SPY&range=3Y&stats=1");
    fireEvent.click(toggle);
    expect(window.location.search).toBe("?t=SPY&range=3Y");
  });

  it("reads stats=1 from the first URL", async () => {
    renderAt("/?t=SPY&stats=1");
    expect(screen.getByRole("switch", { name: "Show statistics" }).getAttribute("aria-checked")).toBe("true");
    await screen.findByTestId("report-ticker");
    expect(window.location.search).toBe("?t=SPY&stats=1");
  });
});

describe("suggestions", () => {
  it("asks the server after the debounce and lists the matches", async () => {
    renderAt("/");
    const input = screen.getByRole("combobox", { name: "Ticker" });
    fireEvent.focus(input);
    fireEvent.change(input, { target: { value: "sp" } });
    expect(requests.some((r) => r.startsWith("/api/tickers"))).toBe(false);
    const option = await screen.findByRole("option", { name: /SPXL/ });
    expect(option).toBeTruthy();
    expect(requests).toContain("/api/tickers?q=SP&limit=8");
    expect(screen.queryByRole("option", { name: /QQQ/ })).toBeNull();
  });
});

describe("factor data refresh", () => {
  it("refreshes, announces the result and reloads the ranges and the report", async () => {
    setRefreshResult({ ...mockStatus, last_date: "2026-10-30" });
    renderAt("/?t=SPY");
    await screen.findByTestId("report-ticker");
    const calls = reportCalls().length;
    fireEvent.click(await screen.findByRole("button", { name: "Check for newer factor data" }));
    expect(await screen.findByText("Factor data updated. It now ends 30 Oct 2026.")).toBeTruthy();
    await waitFor(() => expect(reportCalls().length).toBeGreaterThan(calls));
    expect(requests.filter((r) => r === "/api/report/SPY/ranges").length).toBeGreaterThan(1);
    expect(screen.getByText("Factor data ends 30 Oct 2026, so later dates cannot be chosen.")).toBeTruthy();
  });

  it("says plainly when nothing newer exists", async () => {
    renderAt("/");
    fireEvent.click(await screen.findByRole("button", { name: "Check for newer factor data" }));
    expect(await screen.findByText("No newer factor data is available. It still ends 30 Sep 2026.")).toBeTruthy();
  });

  it("explains a failed refresh with the message and the action", async () => {
    server.use(
      http.post("*/api/factors/refresh", () =>
        HttpResponse.json(
          { code: "network", message: "factordesk could not reach the data source.", action: "Check your network connection, then try again." },
          { status: 503 },
        ),
      ),
    );
    renderAt("/");
    fireEvent.click(await screen.findByRole("button", { name: "Check for newer factor data" }));
    expect(
      await screen.findByText("factordesk could not reach the data source. Check your network connection, then try again."),
    ).toBeTruthy();
  });
});
