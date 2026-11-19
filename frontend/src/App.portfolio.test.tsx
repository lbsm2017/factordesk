import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "./App";
import { LIBRARY } from "./portfolio/testLibrary";
import { STORAGE_KEY } from "./portfolio/store";
import { resetRecentCache } from "./state/recent";
import { monthlyReport } from "./test/fixture";
import { server, setupMockApi } from "./test/mockApi";

// The panels need ECharts; this file tests the composer around them.
vi.mock("./components/report/ReportView", () => ({
  ReportView: (props: { report: { ticker: string }; downloadHref: string | null }) => (
    <main data-testid="report-region">
      <span data-testid="report-ticker">{props.report.ticker}</span>
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

const bodies: Record<string, unknown>[] = [];

function mockPortfolioApi(refuse = false) {
  server.use(
    http.get("*/api/portfolio/library", () => HttpResponse.json({ version: 1, lines: LIBRARY })),
    http.post("*/api/report/portfolio", async ({ request }) => {
      const body = (await request.json()) as Record<string, unknown>;
      bodies.push(body);
      if (refuse) {
        return HttpResponse.json(
          { code: "unknown_ticker", message: "No prices were returned for XYZ.", action: "Check the ticker symbol." },
          { status: 404 },
        );
      }
      const tree = body["tree"] as { name: string };
      return HttpResponse.json({ ...monthlyReport, ticker: tree.name });
    }),
  );
}

beforeEach(() => {
  window.localStorage.clear();
  resetRecentCache();
  bodies.length = 0;
});

/** Create a portfolio from the sidebar form and wait for the composer. */
async function createFrom(preset: string, name: string) {
  const create = await screen.findByRole("button", { name: "Create portfolio" });
  await waitFor(() => expect((create as HTMLButtonElement).disabled).toBe(false));
  fireEvent.change(screen.getByLabelText("Name", { selector: "#" + screen.getByLabelText("Name").id }), {
    target: { value: name },
  });
  fireEvent.click(screen.getByRole("radio", { name: new RegExp(`^${preset}`) }));
  fireEvent.click(create);
  return screen.findByTestId("composer");
}

describe("the portfolio mode", () => {
  it("is the third mode of the switch, with m=portfolio, and shows the landing with no saved portfolio", () => {
    mockPortfolioApi();
    renderAt("/");
    fireEvent.click(screen.getByRole("radio", { name: "Portfolio" }));
    expect(window.location.search).toBe("?m=portfolio");
    expect(screen.getByTestId("portfolio-landing")).toBeTruthy();
    expect(screen.queryByRole("combobox", { name: "Ticker" })).toBeNull();
  });

  it("builds a 60/40 preset with the library names and proxies", async () => {
    mockPortfolioApi();
    renderAt("/?m=portfolio");
    const composer = within(await createFrom("60/40", "My 60/40"));
    expect(composer.getByText("Equity N. America - Large Cap")).toBeTruthy();
    expect(composer.getByText("IVV")).toBeTruthy();
    expect(composer.getByText("IEF")).toBeTruthy();
    expect(composer.getByText("from 2002")).toBeTruthy();
    expect((screen.getByLabelText("Weight of Equity N. America - Large Cap, percent") as HTMLInputElement).value).toBe("60.0");
    const live = within(screen.getByRole("complementary", { name: "Live portfolio check" }));
    expect(live.getByText("100% allocated")).toBeTruthy();
    expect(live.getByText("Limited by IEF")).toBeTruthy();
    // It is saved under a versioned key.
    const stored = JSON.parse(window.localStorage.getItem(STORAGE_KEY) ?? "{}") as { portfolios: { tree: { name: string } }[] };
    expect(stored.portfolios[0]?.tree.name).toBe("My 60/40");
  });

  it("adds a line from the picker, types a weight and nudges it with the arrow keys", async () => {
    mockPortfolioApi();
    renderAt("/?m=portfolio");
    await createFrom("Blank", "Mine");
    fireEvent.click(screen.getByRole("button", { name: "Add sub-asset class" }));
    const dialog = within(screen.getByRole("dialog", { name: "Add sub-asset class" }));
    // A line with no proxy is listed and cannot be added.
    expect(dialog.getAllByText("No proxy yet").length).toBeGreaterThan(0);
    expect(dialog.queryByRole("button", { name: "Add Venture Capital" })).toBeNull();
    expect(dialog.getAllByText("short history").length).toBeGreaterThan(0);
    fireEvent.change(dialog.getByLabelText("Search the library"), { target: { value: "gold" } });
    fireEvent.click(dialog.getByRole("button", { name: "Add Gold" }));
    expect(dialog.getByText("In portfolio")).toBeTruthy();
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByRole("dialog")).toBeNull();

    const input = screen.getByLabelText("Weight of Gold, percent") as HTMLInputElement;
    fireEvent.change(input, { target: { value: "20" } });
    fireEvent.keyDown(input, { key: "ArrowUp" });
    fireEvent.keyDown(input, { key: "ArrowUp" });
    expect(input.value).toBe("21.0");
    fireEvent.keyDown(input, { key: "ArrowDown" });
    expect(input.value).toBe("20.5");
    const live = within(screen.getByRole("complementary", { name: "Live portfolio check" }));
    expect(live.getByText("79.5% unallocated")).toBeTruthy();

    fireEvent.click(live.getByRole("button", { name: "Put remainder in USD cash" }));
    expect(live.getByText("100% allocated")).toBeTruthy();
    fireEvent.change(input, { target: { value: "abc" } });
    expect(input.getAttribute("aria-invalid")).toBe("true");
  });

  it("runs with the tree, the cost, the model and the range, then folds the composer above the report", async () => {
    mockPortfolioApi();
    renderAt("/?m=portfolio&range=5Y&model=ff5");
    await createFrom("60/40", "Folded");
    const live = within(screen.getByRole("complementary", { name: "Live portfolio check" }));
    fireEvent.change(live.getByLabelText("Trading cost"), { target: { value: "25" } });
    fireEvent.click(live.getByRole("button", { name: "Run backtest" }));
    expect(await screen.findByTestId("report-ticker")).toHaveProperty("textContent", "Folded");
    expect(bodies).toHaveLength(1);
    const body = bodies[0] as { tree: { name: string; cost_bps: number }; cost_bps: number; model: string; range: string };
    expect(body).toMatchObject({ cost_bps: 25, model: "ff5", range: "5Y" });
    expect(body.tree).toMatchObject({ name: "Folded", cost_bps: 25 });
    const fold = within(screen.getByRole("group", { name: "Portfolio summary" }));
    expect(fold.getByText("Folded")).toBeTruthy();
    expect(fold.getByText("2 lines")).toBeTruthy();
    expect(fold.getByText("100% allocated")).toBeTruthy();
    expect(screen.queryByTestId("composer")).toBeNull();
    fireEvent.click(fold.getByRole("button", { name: "Edit" }));
    expect(screen.getByTestId("composer")).toBeTruthy();
    expect(screen.queryByTestId("report-ticker")).toBeNull();
  });

  it("shows the message of the API when it refuses", async () => {
    mockPortfolioApi(true);
    renderAt("/?m=portfolio");
    await createFrom("60/40", "Refused");
    const live = within(screen.getByRole("complementary", { name: "Live portfolio check" }));
    fireEvent.click(live.getByRole("button", { name: "Run backtest" }));
    const error = await screen.findByTestId("portfolio-error");
    expect(error.textContent).toContain("No prices were returned for XYZ.");
    expect(error.textContent).toContain("Check the ticker symbol.");
    expect(screen.getByTestId("composer")).toBeTruthy();
  });

  it("swaps a ticker with the ticker search and keeps the weight", async () => {
    mockPortfolioApi();
    renderAt("/?m=portfolio");
    await createFrom("60/40", "Swap");
    fireEvent.click(screen.getByRole("button", { name: "Swap the ticker of Equity N. America - Large Cap" }));
    const field = screen.getByRole("combobox", { name: "New ticker" });
    fireEvent.change(field, { target: { value: "spy" } });
    fireEvent.click(screen.getByRole("button", { name: "Swap"}));
    const row = screen.getByText("Equity N. America - Large Cap").closest(".t-row") as HTMLElement;
    expect(within(row).getByText("SPY")).toBeTruthy();
    expect(within(row).getByText("swapped")).toBeTruthy();
    expect((screen.getByLabelText("Weight of Equity N. America - Large Cap, percent") as HTMLInputElement).value).toBe("60.0");
  });

  it("duplicates, renames and deletes at once with an Undo toast", async () => {
    mockPortfolioApi();
    renderAt("/?m=portfolio");
    await createFrom("60/40", "Growth");
    fireEvent.click(screen.getByRole("button", { name: "Duplicate" }));
    const list = within(screen.getByRole("list", { name: "Saved portfolios" }));
    expect(list.getByRole("button", { name: /Growth copy/ })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Rename" }));
    fireEvent.change(screen.getByLabelText("Portfolio name"), { target: { value: "Renamed" } });
    fireEvent.click(screen.getByRole("button", { name: "Save name" }));
    expect(list.getByRole("button", { name: /Renamed/ })).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Delete" }));
    const toast = screen.getByTestId("undo-region");
    expect(toast.textContent).toContain("Deleted Renamed");
    expect(list.queryByRole("button", { name: /Renamed/ })).toBeNull();
    fireEvent.click(within(toast).getByRole("button", { name: "Undo" }));
    expect(list.getByRole("button", { name: /Renamed/ })).toBeTruthy();
    expect(screen.getByTestId("undo-region").textContent).toBe("");
  });

  it("drops the toast after a few seconds", async () => {
    mockPortfolioApi();
    renderAt("/?m=portfolio");
    await createFrom("Blank", "Gone");
    vi.useFakeTimers({ shouldAdvanceTime: true });
    try {
      fireEvent.click(screen.getByRole("button", { name: "Delete" }));
      expect(screen.getByTestId("undo-region").textContent).toContain("Deleted Gone");
      await act(async () => {
        await vi.advanceTimersByTimeAsync(9000);
      });
      expect(screen.getByTestId("undo-region").textContent).toBe("");
    } finally {
      vi.useRealTimers();
    }
  });

  it("starts empty when storage is blocked", async () => {
    mockPortfolioApi();
    const spy = vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    try {
      renderAt("/?m=portfolio");
      expect(screen.getByTestId("portfolio-landing")).toBeTruthy();
    } finally {
      spy.mockRestore();
    }
  });
});
