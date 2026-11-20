/** The Factor it flow against a progress stream (Sprint 4 mockup 1): steps, reveal, re-run, errors, cache hit, reduced motion. */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "./App";
import { resetRecentCache } from "./state/recent";
import { cloneReport } from "./test/fixture";
import { server, setupMockApi, sse } from "./test/mockApi";

// The panels need ECharts; this file tests the flow around them. The mock passes the new props through.
vi.mock("./components/report/ReportView", () => ({
  ReportView: (props: { report: { ticker: string }; busy?: boolean; dim?: boolean; reveal?: boolean }) => (
    <main
      data-testid="report-region"
      aria-busy={props.busy ?? false}
      inert={props.dim}
      data-dim={String(props.dim ?? false)}
      data-reveal={String(props.reveal ?? false)}
    >
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

const encoder = new TextEncoder();
const labels = {
  prices: "Downloading prices",
  fx: "Loading exchange rates",
  factors: "Loading factor data",
  models: "Fitting the models",
  sections: "Building the sections",
} as const;
const step = (index: number, total: number, id: keyof typeof labels) => sse("step", { step: id, label: labels[id], index, total });

/** A stream the test feeds by hand: `push` sends blocks, `end` closes it. */
function openStream(ticker: string) {
  let controller!: ReadableStreamDefaultController<Uint8Array>;
  const body = new ReadableStream<Uint8Array>({
    start(c) {
      controller = c;
    },
  });
  server.use(
    http.get(`*/api/report/${ticker}/stream`, () => new Response(body, { status: 200, headers: { "Content-Type": "text/event-stream" } })),
  );
  return {
    push: (...blocks: string[]) => act(() => controller.enqueue(encoder.encode(blocks.join("")))),
    end: () => act(() => controller.close()),
  };
}

const reportBlock = (ticker: string) => sse("report", { ...cloneReport(), ticker });
const stateOf = (name: string) => screen.getByText(name).closest("li")?.getAttribute("data-state");

beforeEach(() => {
  window.localStorage.clear();
  resetRecentCache();
});
afterEach(() => vi.unstubAllGlobals());

describe("a first run on a stream", () => {
  it("shows the run card and the step states as the events arrive, then the report with the reveal", async () => {
    const stream = openStream("SPY");
    renderAt("/?t=SPY");
    stream.push(step(1, 4, "prices"));
    expect(await screen.findByRole("heading", { name: "Building the report for SPY" })).toBeTruthy();
    expect(stateOf("Downloading prices")).toBe("running");
    expect(stateOf("Loading factor data")).toBe("waiting");
    expect(screen.getByText("Step 1 of 4")).toBeTruthy();
    // The busy button keeps focus semantics and shows the bar.
    const button = screen.getByRole("button", { name: "Factoring…" });
    expect(button.getAttribute("aria-disabled")).toBe("true");
    expect(button.querySelector(".btn-prog")).not.toBeNull();
    // The region is busy and the placeholders are hidden from assistive technology.
    const frame = screen.getByTestId("loading-frame");
    expect(frame.getAttribute("aria-busy")).toBe("true");
    expect(frame.querySelectorAll("section.ph-panel[aria-hidden='true']").length).toBeGreaterThan(5);
    // The polite status line says the step that started.
    expect(screen.getByTestId("run-status").textContent).toBe("Step 1 of 4: Downloading prices.");

    stream.push(step(2, 4, "factors"), step(3, 4, "models"));
    await waitFor(() => expect(stateOf("Fitting the models")).toBe("running"));
    expect(stateOf("Downloading prices")).toBe("done");
    expect(stateOf("Loading factor data")).toBe("done");
    expect(stateOf("Building the sections")).toBe("waiting");
    expect(screen.getByText("Step 3 of 4")).toBeTruthy();
    expect(screen.getByTestId("run-status").textContent).toBe("Step 3 of 4: Fitting the models.");

    stream.push(reportBlock("SPY"));
    stream.end();
    expect(await screen.findByTestId("report-ticker")).toHaveProperty("textContent", "SPY");
    expect(screen.queryByTestId("run-card")).toBeNull();
    expect(screen.getByTestId("report-region").getAttribute("data-reveal")).toBe("true");
    expect(screen.getByTestId("run-status").textContent).toBe("The report for SPY is ready.");
    expect(screen.getByRole("button", { name: "Factor it" })).toBeTruthy();
  });

  it("lists the exchange-rate step in EUR only", async () => {
    const stream = openStream("SPY");
    renderAt("/?t=SPY&ccy=EUR");
    stream.push(step(1, 5, "prices"));
    await screen.findByRole("heading", { name: "Building the report for SPY" });
    expect(screen.getByText("Loading exchange rates")).toBeTruthy();
    expect(screen.getByText("Step 1 of 5")).toBeTruthy();
    stream.push(reportBlock("SPY"));
    stream.end();
    await screen.findByTestId("report-ticker");
  });

  it("opens a cached report at once: no run card, no reveal", async () => {
    const stream = openStream("SPY");
    renderAt("/?t=SPY");
    stream.push(reportBlock("SPY"));
    stream.end();
    expect(await screen.findByTestId("report-ticker")).toBeTruthy();
    expect(screen.queryByTestId("run-card")).toBeNull();
    expect(screen.getByTestId("report-region").getAttribute("data-reveal")).toBe("false");
  });

  it("a stream that is not there falls back to the plain endpoint: the card has a heading and no step list", async () => {
    renderAt("/?t=SPY"); // the default mock answers 404 on the stream route
    expect(await screen.findByRole("heading", { name: "Building the report for SPY" })).toBeTruthy();
    expect(screen.queryByRole("list")).toBeNull();
    expect(screen.getByTestId("run-card").querySelector(".run-bar")).toBeNull();
    expect(await screen.findByTestId("report-ticker")).toBeTruthy();
  });

  it("an error event ends in the error page: the failed step, the steps not run, Try again and Change ticker", async () => {
    const stream = openStream("XYZQ");
    renderAt("/?t=XYZQ");
    stream.push(
      step(1, 4, "prices"),
      sse("error", {
        code: "unknown_ticker",
        message: "We could not find XYZQ. The price source has no data for this ticker.",
        action: "Check the spelling, or add the exchange suffix, for example VOD.L. Then press Factor it.",
        status: 404,
      }),
    );
    stream.end();
    const page = await screen.findByTestId("report-error");
    expect(within(page).getByRole("heading", { level: 1 }).textContent).toBe("XYZQ");
    const alert = within(page).getByRole("alert");
    expect(alert.textContent).toContain("We could not find XYZQ.");
    expect(alert.textContent).toContain("Check the spelling");
    expect(within(page).getByRole("button", { name: "Try again" })).toBeTruthy();
    expect(within(page).getByRole("button", { name: "Change ticker" })).toBeTruthy();
    expect(within(page).getByRole("heading", { name: "The report for XYZQ stopped" })).toBeTruthy();
    expect(within(page).getByText("Stopped at step 1 of 4")).toBeTruthy();
    expect(screen.getByText("Downloading prices").closest("li")?.getAttribute("data-state")).toBe("failed");
    expect(screen.getByText("Loading factor data").closest("li")?.getAttribute("data-state")).toBe("not-run");
    // The notice takes focus; the button is back to Factor it; the status line stays quiet.
    await waitFor(() => expect(document.activeElement).toBe(alert));
    expect(screen.getByRole("button", { name: "Factor it" })).toBeTruthy();
    expect(screen.getByTestId("run-status").textContent).toBe("");
  });

  it("a refusal before the run starts (plain JSON error) is an error, not a fallback", async () => {
    server.use(
      http.get("*/api/report/BAD/stream", () =>
        HttpResponse.json({ code: "bad_request", message: "The range is not valid.", action: "Choose another range." }, { status: 400 }),
      ),
    );
    renderAt("/?t=BAD");
    const page = await screen.findByTestId("report-error");
    expect(page.textContent).toContain("The range is not valid.");
    expect(within(page).queryByRole("list")).toBeNull();
  });
});

describe("a re-run on a stream", () => {
  async function loadSpyThenAskFor(ticker: string) {
    renderAt("/?t=SPY");
    await screen.findByTestId("report-ticker");
    const input = screen.getByRole("combobox", { name: "Ticker" });
    fireEvent.change(input, { target: { value: ticker } });
    fireEvent.keyDown(input, { key: "Enter" });
  }

  it("keeps the old report, dimmed and inert, with a sticky bar and a chip that names the new request", async () => {
    const stream = openStream("QQQ");
    await loadSpyThenAskFor("qqq");
    stream.push(step(1, 4, "prices"), step(2, 4, "factors"));
    const chip = await screen.findByTestId("rerun-chip");
    expect(chip.textContent).toContain("Updating QQQ");
    expect(chip.textContent).toContain("Loading factor data, step 2 of 4");
    expect(screen.getByTestId("rerun-bar").getAttribute("style")).toContain("--p: 25%");
    const region = screen.getByTestId("report-region");
    expect(region.getAttribute("data-dim")).toBe("true");
    expect(region.hasAttribute("inert")).toBe(true);
    expect(region.getAttribute("aria-busy")).toBe("true");
    expect(screen.getByTestId("report-ticker").textContent).toBe("SPY");
    // No run card and no placeholder page: nothing in the page moves.
    expect(screen.queryByTestId("run-card")).toBeNull();
    expect(screen.queryByTestId("loading-frame")).toBeNull();
    expect(screen.getByTestId("run-status").textContent).toBe("Step 2 of 4: Loading factor data.");

    stream.push(reportBlock("QQQ"));
    stream.end();
    await waitFor(() => expect(screen.getByTestId("report-ticker").textContent).toBe("QQQ"));
    expect(screen.queryByTestId("rerun-chip")).toBeNull();
    const after = screen.getByTestId("report-region");
    expect(after.getAttribute("data-dim")).toBe("false");
    expect(after.hasAttribute("inert")).toBe(false);
    expect(after.getAttribute("data-reveal")).toBe("true");
  });

  it("a failed re-run lifts the dim and puts a banner over the old report", async () => {
    const stream = openStream("QQQ");
    await loadSpyThenAskFor("qqq");
    stream.push(
      step(1, 4, "prices"),
      sse("error", { code: "upstream_refused", message: "The price source did not answer in time. Your ticker is fine.", action: "Press Try again.", status: 502 }),
    );
    stream.end();
    const banner = await screen.findByTestId("rerun-error");
    expect(banner.textContent).toContain("The price source did not answer in time.");
    expect(banner.textContent).toContain("The report below is the previous one, for SPY.");
    const region = screen.getByTestId("report-region");
    expect(region.getAttribute("data-dim")).toBe("false");
    expect(region.hasAttribute("inert")).toBe(false);
    expect(region.getAttribute("aria-busy")).toBe("false");
    expect(screen.queryByTestId("rerun-chip")).toBeNull();
    expect(screen.getByRole("button", { name: "Factor it" })).toBeTruthy();
  });

  it("ignores a second submit while the run is on its way", async () => {
    const stream = openStream("QQQ");
    await loadSpyThenAskFor("qqq");
    stream.push(step(1, 4, "prices"));
    await screen.findByTestId("rerun-chip");
    const calls = () => screen.queryAllByTestId("rerun-chip").length;
    const input = screen.getByRole("combobox", { name: "Ticker" });
    fireEvent.change(input, { target: { value: "IWM" } });
    fireEvent.keyDown(input, { key: "Enter" });
    expect(window.location.search).toContain("t=QQQ");
    expect(calls()).toBe(1);
    stream.push(reportBlock("QQQ"));
    stream.end();
    await waitFor(() => expect(screen.getByTestId("report-ticker").textContent).toBe("QQQ"));
  });
});

describe("reduced motion", () => {
  it("styles switch every animation and transition of the flow off", async () => {
    const { readFileSync } = await import("node:fs");
    const { resolve } = await import("node:path");
    const css = readFileSync(resolve(process.cwd(), "src/styles/frame.css"), "utf8");
    const block = /@media \(prefers-reduced-motion: reduce\)\s*\{([^]*)\}\s*$/.exec(css)?.[1] ?? "";
    for (const piece of [".report-region.reveal > *", "animation: none", ".run-bar i", ".rr-bar i", ".report-region.dim", ".rr-chip .dot", ".st-mark::after"]) {
      expect(block, piece).toContain(piece);
    }
    const controls = readFileSync(resolve(process.cwd(), "src/styles/controls.css"), "utf8");
    expect(controls).toMatch(/prefers-reduced-motion: reduce\)\s*\{\s*\.btn-prog i \{ transition: none; \}/);
  });
});
