import { render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { cloneReport, mockReport } from "../../test/fixture";
import { withSection } from "../../test/sectionFixtures";
import { SummaryPanel } from "./SummaryPanel";

vi.mock("../../state/stats", () => ({ useShowStats: vi.fn(() => false), StatsProvider: ({ children }: { children: unknown }) => children }));
import { useShowStats } from "../../state/stats";

const full = withSection(withSection(mockReport, "performance"), "world_beta");

function rowOf(container: HTMLElement, label: string): HTMLTableRowElement {
  const th = Array.from(container.querySelectorAll("tbody th")).find((el) => el.textContent === label);
  if (!th?.parentElement) throw new Error(`no row ${label}`);
  return th.parentElement as HTMLTableRowElement;
}

describe("SummaryPanel", () => {
  it("shows the title row, the verdict, the data notes and both tables", () => {
    const { container } = render(<SummaryPanel report={full} />);
    expect(container.querySelector("section#summary h2")?.textContent).toBe("Summary");
    expect(container.querySelector(".pm")?.textContent).toBe("8 Aug 2024 to 30 Sep 2026. Past data, not a forecast.");
    const verdictText = container.querySelector(".verdict")?.textContent ?? "";
    expect(verdictText).toContain("SPY moves with the market (about one-for-one)");
    expect(verdictText).toContain("probably understated");
    expect(container.querySelector("#notice .notes-line b")?.textContent).toBe("2 data notes:");
    expect(screen.getByRole("heading", { name: "Performance" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Factor model" })).toBeTruthy();
    expect(container.querySelector(".foot")?.textContent).toContain(
      "Annualised from daily data. ACWI is an ETF used as a stand-in for the MSCI ACWI index.",
    );
    const head = Array.from(container.querySelectorAll("thead")[0]?.querySelectorAll("th") ?? []).map((th) => th.textContent);
    expect(head).toEqual(["Metric", "Value", "Reading"]);
  });

  it("fills the performance and factor model rows from the report", () => {
    const { container } = render(<SummaryPanel report={full} />);
    const cells = (label: string) => Array.from(rowOf(container, label).querySelectorAll("td")).map((td) => td.textContent);
    expect(cells("Annualised return")).toEqual(["−7.2%", "–"]);
    expect(cells("Volatility")).toEqual(["22.9%", "–"]);
    expect(cells("Sharpe ratio")).toEqual(["−0.36", "Could be noise"]);
    expect(cells("Max drawdown")).toEqual(["−41.0%", "Not recovered"]);
    expect(cells("Alpha (annual)")).toEqual(["+0.81%", "Could be noise"]);
    expect(cells("R²")).toEqual(["99.9%", "Probably understated"]);
    expect(cells("Residual volatility")).toEqual(["0.6%", "Probably overstated"]);
    expect(cells("Market beta (five-factor)")).toEqual(["+1.00", "Clear evidence"]);
    expect(cells("Beta to ACWI")).toEqual(["+0.93", "Clear evidence"]);
  });

  it("colours only returns, Sharpe, drawdown and alpha; betas stay neutral", () => {
    const { container } = render(<SummaryPanel report={full} />);
    const valueClass = (label: string) => rowOf(container, label).querySelector("td")?.className ?? "";
    expect(valueClass("Annualised return")).toContain("num-neg");
    expect(valueClass("Sharpe ratio")).toContain("num-neg");
    expect(valueClass("Max drawdown")).toContain("num-neg");
    expect(valueClass("Alpha (annual)")).toContain("num-pos");
    for (const label of ["Volatility", "R²", "Residual volatility", "Market beta (five-factor)", "Beta to ACWI"]) {
      expect(valueClass(label), label).not.toMatch(/num-(pos|neg)/);
    }
  });

  it("weights clear-evidence rows and leaves could-be-noise rows normal", () => {
    const { container } = render(<SummaryPanel report={full} />);
    expect(rowOf(container, "Alpha (annual)").className).toBe("is-noise");
    expect(rowOf(container, "Sharpe ratio").className).toBe("is-noise");
    expect(rowOf(container, "Market beta (five-factor)").className).toBe("");
  });

  it("explains in the title that the market beta here is the five-factor one", () => {
    const { container } = render(<SummaryPanel report={full} />);
    const tip = rowOf(container, "Market beta (five-factor)").querySelector(".tip")?.getAttribute("title") ?? "";
    expect(tip).toContain("one-factor");
    expect(container.textContent).not.toContain("Beta to US market");
  });

  it("gives every metric label a title and the table heads an explanation", () => {
    const { container } = render(<SummaryPanel report={full} />);
    for (const span of container.querySelectorAll("tbody th .tip")) {
      expect(span.getAttribute("title"), span.textContent ?? "").toBeTruthy();
    }
    expect(screen.getAllByText("Reading")[0]?.getAttribute("title")).toContain("Clear evidence");
  });

  it("adds t and the 95% interval columns when statistics are shown", () => {
    vi.mocked(useShowStats).mockReturnValue(true);
    const { container } = render(<SummaryPanel report={full} />);
    vi.mocked(useShowStats).mockReturnValue(false);
    const head = Array.from(container.querySelectorAll("thead")[1]?.querySelectorAll("th") ?? []).map((th) => th.textContent);
    expect(head).toEqual(["Metric", "Value", "Reading", "t", "95% interval"]);
    const cells = Array.from(rowOf(container, "Alpha (annual)").querySelectorAll("td")).map((td) => td.textContent);
    expect(cells.slice(2)).toEqual(["0.8", "−1.5% to +3.2%"]);
    const sharpe = Array.from(rowOf(container, "Sharpe ratio").querySelectorAll("td")).map((td) => td.textContent);
    expect(sharpe.slice(2)).toEqual(["–", "−1.68 to +0.96"]);
  });

  it("shows dashes and a short reason when performance and world beta are missing", () => {
    const { container } = render(<SummaryPanel report={cloneReport()} />);
    expect(rowOf(container, "Annualised return").querySelector("td")?.textContent).toBe("–");
    expect(rowOf(container, "Beta to ACWI").querySelector("td")?.textContent).toBe("–");
    expect(container.querySelector(".sum-reason")?.textContent).toBe(
      "Performance is not in this report. The ACWI beta is not in this report.",
    );
  });

  it("shows the section reason when a section is not ok, and a failed fit without crashing", () => {
    const r = withSection(withSection(mockReport, "performance"), "world_beta");
    if (r.performance) {
      r.performance.status = "insufficient_data";
      r.performance.reason = "Too few days.";
    }
    if (r.world_beta) {
      r.world_beta.status = "failed";
      r.world_beta.reason = "The world fund's prices could not be fetched.";
    }
    r.regression.status = "failed";
    r.regression.reason = "No usable rows";
    const { container } = render(<SummaryPanel report={r} />);
    expect(container.querySelector(".sum-reason")?.textContent).toBe(
      "Too few days. No usable rows. The world fund's prices could not be fetched.",
    );
    expect(container.querySelector(".verdict")?.textContent).toBe(
      "factordesk could not fit the five-factor model for SPY over this range: No usable rows.",
    );
    const alpha = rowOf(container, "Alpha (annual)");
    expect(within(alpha).getAllByText("–").length).toBeGreaterThan(0);
  });

  it("opens the full note list under Details and keeps the #notice anchor", () => {
    const { container } = render(<SummaryPanel report={full} />);
    expect(container.querySelector("#notice")).not.toBeNull();
    expect(container.querySelector("#notice-details")?.hasAttribute("hidden")).toBe(true);
  });

  it("has no data notes line without warnings", () => {
    const r = cloneReport();
    r.warnings = [];
    r.quality_gate.fired = false;
    const { container } = render(<SummaryPanel report={r} />);
    expect(container.querySelector("#notice")).toBeNull();
  });
});
