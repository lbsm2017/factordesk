import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { File as NodeFile } from "node:buffer";
import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "./App";
import { RECENT_KEY, resetRecentCache } from "./state/recent";
import { monthlyReport } from "./test/fixture";
import { requests, server, setupMockApi } from "./test/mockApi";

// The panels need ECharts; this file tests the track-record mode around them.
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

// Node's File, so that Node's fetch sends it as a file part (jsdom's File would be sent as text).
const csv = (text = "date,return\n2021-01-31,0.012\n") =>
  new NodeFile([text], "record.csv", { type: "text/csv" }) as unknown as File;

function chooseFile(file: File) {
  const input = document.querySelector<HTMLInputElement>("input[type=file]");
  if (input === null) throw new Error("no file input");
  fireEvent.change(input, { target: { files: [file] } });
}

interface Seen {
  file: string | null;
  name: string | null;
  grossNet: string | null;
  model: string | null;
}
const seen: Seen[] = [];

/** The text of one form field in a multipart body, or null when the field is absent. */
function field(body: string, name: string): string | null {
  const found = new RegExp(`name="${name}"(?:; filename="[^"]*")?\r\n(?:[^\r\n]+\r\n)*\r\n([^\r]*)\r\n--`).exec(body);
  return found?.[1] ?? null;
}

function answerUpload(status = 200) {
  server.use(
    http.post("*/api/report/upload", async ({ request }) => {
      const body = await request.text();
      const file = /filename="([^"]*)"/.exec(body)?.[1] ?? null;
      const name = field(body, "name");
      seen.push({ file, name, grossNet: field(body, "gross_net"), model: field(body, "model") });
      if (status === 200) return HttpResponse.json({ ...monthlyReport, ticker: name ?? "Uploaded track record" });
      return HttpResponse.json(
        {
          code: "invalid_upload",
          message: "The file cannot be used: months must be consecutive: no return for 2021-03.",
          action: "Send a CSV with a date and a return column.",
        },
        { status },
      );
    }),
  );
}

beforeAll(async () => {
  // jsdom's FormData cannot be sent by Node's fetch; the app builds its body with Node's own class,
  // which a form parsed by Node's Response gives away.
  const parsed = await new Response("a=b", { headers: { "content-type": "application/x-www-form-urlencoded" } }).formData();
  vi.stubGlobal("FormData", parsed.constructor);
});

beforeEach(() => {
  window.localStorage.clear();
  resetRecentCache();
  seen.length = 0;
});

describe("mode switch", () => {
  it("starts in ticker mode and leaves old URLs alone", () => {
    renderAt("/?t=SPY&range=3Y");
    expect(window.location.search).toBe("?t=SPY&range=3Y");
    const mode = within(screen.getByRole("group", { name: "Analyse" }));
    expect((mode.getByRole("radio", { name: "Ticker" }) as HTMLInputElement).checked).toBe(true);
    expect(screen.getByRole("combobox", { name: "Ticker" })).toBeTruthy();
  });

  it("switches to the track record with m=track and back", async () => {
    renderAt("/?t=SPY");
    await screen.findByTestId("report-ticker");
    fireEvent.click(screen.getByRole("radio", { name: "Track record" }));
    expect(window.location.search).toBe("?t=SPY&m=track");
    expect(screen.getByTestId("track-landing")).toBeTruthy();
    expect(screen.queryByRole("combobox", { name: "Ticker" })).toBeNull();
    fireEvent.click(screen.getByRole("radio", { name: "Ticker" }));
    expect(window.location.search).toBe("?t=SPY");
    expect(await screen.findByTestId("report-ticker")).toHaveProperty("textContent", "SPY");
  });

  it("opens in the track-record mode from the URL and asks the server for no ticker", async () => {
    renderAt("/?m=track&t=SPY");
    expect(screen.getByTestId("track-landing")).toBeTruthy();
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(requests.filter((r) => /^\/api\/report\//.test(r))).toEqual([]);
  });
});

describe("track-record upload", () => {
  it("sends the file with the name and the fee basis and shows the report without a download link", async () => {
    answerUpload();
    renderAt("/?m=track");
    chooseFile(csv());
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: " Example Fund " } });
    fireEvent.click(screen.getByRole("radio", { name: "Net" }));
    fireEvent.click(screen.getByRole("button", { name: "Factor it" }));
    expect(await screen.findByTestId("report-ticker")).toHaveProperty("textContent", "Example Fund");
    expect(screen.getByTestId("report-download").textContent).toBe("null");
    expect(seen).toEqual([{ file: "record.csv", name: "Example Fund", grossNet: "net", model: "ff6" }]);
    // Nothing is remembered: no recent ticker, no stored report.
    expect(window.localStorage.getItem(RECENT_KEY)).toBeNull();
    expect(window.location.search).toBe("?m=track");
  });

  it("summarises the analysed months in the sidebar once the record is analysed, and not before", async () => {
    answerUpload();
    renderAt("/?m=track");
    expect(document.querySelector("#analysed-range")).toBeNull();
    chooseFile(csv());
    fireEvent.click(screen.getByRole("button", { name: "Factor it" }));
    await screen.findByTestId("report-ticker");
    const summary = document.querySelector("#analysed-range") as HTMLElement;
    expect(summary.querySelector(".cov-size")?.textContent).toBe("84 months");
    expect(summary.querySelector("[data-part='analysed']")).toBeTruthy();
    expect(summary.textContent).not.toContain("trading day");
  });

  it("leaves the name and fee basis out when they are not given", async () => {
    answerUpload();
    renderAt("/?m=track");
    chooseFile(csv());
    fireEvent.click(screen.getByRole("button", { name: "Factor it" }));
    await screen.findByTestId("report-ticker");
    expect(seen).toEqual([{ file: "record.csv", name: null, grossNet: null, model: "ff6" }]);
  });

  it("sends model=ff5 when the URL asks for FF5, and keeps it in the URL", async () => {
    answerUpload();
    renderAt("/?m=track&model=ff5");
    chooseFile(csv());
    fireEvent.click(screen.getByRole("button", { name: "Factor it" }));
    await screen.findByTestId("report-ticker");
    expect(seen).toEqual([{ file: "record.csv", name: null, grossNet: null, model: "ff5" }]);
    expect(window.location.search).toBe("?m=track&model=ff5");
  });

  it("asks for a file before it sends anything", () => {
    renderAt("/?m=track");
    fireEvent.click(screen.getByRole("button", { name: "Factor it" }));
    expect(screen.getByRole("alert").textContent).toBe("Choose a CSV file first.");
    expect(seen).toEqual([]);
  });

  it("shows the message and the action of a refused file", async () => {
    answerUpload(422);
    renderAt("/?m=track");
    chooseFile(csv());
    fireEvent.click(screen.getByRole("button", { name: "Factor it" }));
    const error = await screen.findByTestId("report-error");
    expect(error.textContent).toContain("months must be consecutive: no return for 2021-03");
    expect(error.textContent).toContain("Send a CSV with a date and a return column.");
    await waitFor(() => expect(screen.queryByTestId("report-region")).toBeNull());
  });

  it("takes a dropped file", async () => {
    answerUpload();
    renderAt("/?m=track");
    const zone = document.querySelector(".ctl-drop") as HTMLElement;
    fireEvent.dragOver(zone);
    expect(zone.className).toContain("over");
    fireEvent.drop(zone, { dataTransfer: { files: [csv()] } });
    expect(zone.textContent).toBe("record.csv");
    fireEvent.click(screen.getByRole("button", { name: "Factor it" }));
    await screen.findByTestId("report-ticker");
    expect(seen).toHaveLength(1);
  });
});
