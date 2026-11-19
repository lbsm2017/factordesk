import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { cloneReport, mockReport } from "../../test/fixture";
import { Colophon } from "./Colophon";
import { DataNotes } from "./DataNotes";
import { GateEvidence } from "./GateEvidence";
import { Header } from "./Header";

/** Opens the Details of the data notes and waits for the lazy chunk behind it. */
async function openDetails(): Promise<void> {
  fireEvent.click(screen.getByRole("button", { name: "Details" }));
  await waitFor(() => expect(document.querySelector(".notes-details li")).not.toBeNull());
}

const HREF = "/api/report/SPY/html?range=3Y";

describe("Header", () => {
  it("shows the ticker, the factor-data chip, the warnings chip and the download link", () => {
    const { container } = render(<Header report={mockReport} downloadHref={HREF} />);
    expect(screen.getByRole("heading", { level: 1 }).textContent).toContain("SPY");
    expect(screen.getByText("Factor data ends 30 Sep 2026 (49 days ago)")).toBeTruthy();
    const warn = screen.getByRole("link", { name: "2 warnings" });
    expect(warn.getAttribute("href")).toBe("#notice");
    const dl = screen.getByRole("link", { name: "Download report" });
    expect(dl.getAttribute("href")).toBe(HREF);
    expect(dl.hasAttribute("download")).toBe(true);
    expect(dl.className).toBe("btn-secondary");
    expect(container.querySelector(".ticker")?.textContent).toBe("SPY");
  });

  it("drops the warnings chip when there is nothing to warn about, and singularises", () => {
    const r = cloneReport();
    r.warnings = [];
    r.quality_gate.fired = false;
    r.data.factors_days_behind = 1;
    render(<Header report={r} downloadHref={HREF} />);
    expect(screen.queryByRole("link", { name: /warning/ })).toBeNull();
    expect(screen.getByText("Factor data ends 30 Sep 2026 (1 day ago)")).toBeTruthy();
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
