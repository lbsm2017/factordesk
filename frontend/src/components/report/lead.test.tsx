import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { cloneReport, mockReport } from "../../test/fixture";
import { Colophon } from "./Colophon";
import { DataNotes } from "./DataNotes";
import { GateEvidence } from "./GateEvidence";
import { Header, listingLine } from "./Header";

/** Opens the Details of the data notes and waits for the lazy chunk behind it. */
async function openDetails(): Promise<void> {
  fireEvent.click(screen.getByRole("button", { name: "Details" }));
  await waitFor(() => expect(document.querySelector(".notes-details li")).not.toBeNull());
}

const HREF = "/api/report/SPY/html?range=3Y";

describe("Header", () => {
  it("shows the ticker, the download link at the right and the analysis bar", () => {
    const { container } = render(<Header report={mockReport} downloadHref={HREF} />);
    expect(screen.getByRole("heading", { level: 1 }).textContent).toBe("SPYExample Corp");
    const dl = screen.getByRole("link", { name: "Download report" });
    expect(dl.getAttribute("href")).toBe(HREF);
    expect(dl.hasAttribute("download")).toBe(true);
    expect(dl.closest(".head-actions")).not.toBeNull();
    expect(container.querySelector(".ticker")?.textContent).toBe("SPY");
    expect(container.querySelector("dl.abar")?.getAttribute("aria-label")).toBe("Analysis settings");
    const pairs = Array.from(container.querySelectorAll(".abar > div")).map((d) => [
      d.querySelector("dt")?.textContent,
      d.querySelector("dd")?.textContent,
    ]);
    expect(pairs).toEqual([
      ["Analysis period", "8 Aug 2024 to 30 Sep 2026"],
      ["Observations", "559 trading days"],
      ["Factor data", "To 30 Sep 2026"],
      ["Benchmark", "ACWI"],
    ]);
    expect(container.querySelector(".abar dd[title]")?.getAttribute("title")).toBe("49 days old");
  });

  it("falls back to the ticker alone when the report has no security field", () => {
    const r = cloneReport();
    delete (r.data as { security?: unknown }).security;
    const { container } = render(<Header report={r} downloadHref={HREF} />);
    expect(container.querySelector(".nm")).toBeNull();
    expect(container.querySelector(".badge")).toBeNull();
    expect(container.querySelector(".listing")).toBeNull();
  });

  it("shows the company name, the type badge and the listing line when the security is known", () => {
    const r = cloneReport();
    (r.data as { security?: unknown }).security = {
      name: "SPDR S&P 500 ETF Trust",
      exchange: "NYSE Arca",
      currency: "USD",
      quote_type: "ETF",
    };
    const { container } = render(<Header report={r} downloadHref={HREF} />);
    expect(screen.getByRole("heading", { level: 1 }).textContent).toBe("SPYSPDR S&P 500 ETF Trust");
    expect(container.querySelector(".badge")?.textContent).toBe("ETF");
    expect(container.querySelector(".listing")?.textContent).toBe("Listed on NYSE Arca, priced in US dollars");
  });

  it("leaves out the parts Yahoo did not give", () => {
    expect(listingLine({ exchange: "NasdaqGS" })).toBe("Listed on NasdaqGS");
    expect(listingLine({ currency: "EUR" })).toBe("Priced in EUR");
    expect(listingLine({ name: "X" })).toBeNull();
    const r = cloneReport();
    (r.data as { security?: unknown }).security = { name: null, quote_type: "MUTUALFUND" };
    const { container } = render(<Header report={r} downloadHref={HREF} />);
    expect(container.querySelector(".nm")).toBeNull();
    expect(container.querySelector(".badge")).toBeNull();
  });
});

describe("DataNotes", () => {
  it("gives a counted plain summary and the raw messages under Details", async () => {
    const { container } = render(<DataNotes report={mockReport} />);
    const sum = container.querySelector(".notes-line");
    expect(sum?.querySelector("b")?.textContent).toBe("2 data notes:");
    expect(container.querySelector("#notice")).not.toBeNull();
    expect(sum?.textContent).toContain("Prices look out of step with the factor data");
    expect(sum?.textContent).toContain("The history is short");
    const details = container.querySelector(".notes-details");
    expect(sum?.querySelector("button")?.textContent).toBe("Details");
    expect(details?.hasAttribute("hidden")).toBe(true);
    await openDetails();
    expect(details?.hasAttribute("hidden")).toBe(false);
    const items = Array.from(details?.querySelectorAll("li") ?? []).map((li) => li.textContent);
    expect(items).toEqual((mockReport.warnings ?? []).map((w) => w.message));
    expect(details?.textContent).toContain("5-day estimate (111 blocks): alpha +0.73% a year");
    expect(details?.querySelector("a")?.getAttribute("href")).toBe("#regression-detail");
  });

  it("summarises audit errors in the static report's words (F4)", () => {
    const r = cloneReport();
    r.quality_gate.fired = false;
    r.warnings = [{ code: "audit_errors", message: "The price audit reported 1 error finding(s)." }];
    const { container } = render(<DataNotes report={r} />);
    expect(container.querySelector(".notes-line")?.textContent).toContain(
      "1 data note: The price audit found errors, so the headline numbers are not interpretable until they are explained; see Data and audit.",
    );
  });

  it("adds the gate caveat when it fired without a residual_reversal warning", async () => {
    const r = cloneReport();
    r.warnings = [{ code: "short_history", message: "short" }];
    const { container } = render(<DataNotes report={r} />);
    await openDetails();
    expect(container.querySelectorAll(".notes-details li")).toHaveLength(2);
  });

  it("counts the rest under Details when there are more than two distinct summaries", () => {
    const r = cloneReport();
    r.warnings = [
      { code: "a", message: "First." },
      { code: "b", message: "Second." },
      { code: "c", message: "Third." },
    ];
    r.quality_gate.fired = false;
    const { container } = render(<DataNotes report={r} />);
    expect(container.querySelector(".notes-line")?.textContent).toContain("3 data notes: First. Second. 1 more are listed under Details.");
  });

  it("renders nothing without warnings", () => {
    const r = cloneReport();
    r.warnings = [];
    r.quality_gate.fired = false;
    const { container } = render(<DataNotes report={r} />);
    expect(container.firstChild).toBeNull();
  });
});

describe("Gate evidence inside the notice", () => {
  it("is a paragraph under Details, with no separate block or heading", async () => {
    const { container } = render(<DataNotes report={mockReport} />);
    await openDetails();
    const text = container.querySelector(".notes-details .gate-evidence")?.textContent ?? "";
    expect(text).toContain("−0.31 (robust z −6.2)");
    expect(text).toContain("62%");
    expect(container.querySelector(".gate-callout")).toBeNull();
    expect(screen.queryByRole("heading", { name: "Residual quality gate" })).toBeNull();
    expect(container.querySelector("a")?.getAttribute("href")).toBe("#regression-detail");
  });

  it("keeps the evidence before the 5-day line", async () => {
    const { container } = render(<DataNotes report={mockReport} />);
    await openDetails();
    const paras = Array.from(container.querySelectorAll(".notes-details > p")).map((p) => p.className || p.textContent);
    expect(paras[0]).toBe("gate-evidence");
    expect(paras[1]).toContain("5-day estimate");
  });

  it("prints the 5-day tag as a plain word, never the raw tag", async () => {
    const { container } = render(<DataNotes report={mockReport} />);
    await openDetails();
    const text = container.querySelector(".notes-details")?.textContent ?? "";
    expect(text).not.toMatch(/reliable|noise/);
    expect(text).toMatch(/, (not )?significant; R²/);
  });

  it("renders nothing on its own when the gate did not fire", () => {
    const r = cloneReport();
    r.quality_gate.fired = false;
    const { container } = render(<GateEvidence report={r} />);
    expect(container.firstChild).toBeNull();
  });
});

describe("Colophon", () => {
  it("states the schema, the generated time and the disclaimer", () => {
    const { container } = render(<Colophon report={mockReport} />);
    expect(container.querySelector("footer.colophon p")?.textContent).toBe(
      "factordesk report, schema v4, generated 18 Nov 2026, 09:30 UTC. Descriptive statistics on past data; nothing here is a forecast or advice.",
    );
  });
});
