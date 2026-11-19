import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { FactorReport } from "../../../api/types";
import { cloneReport } from "../../../test/fixture";
import { withSection } from "../../../test/sectionFixtures";
import { PerformanceBody } from "./PerformanceBody";
import { PerformancePanel } from "./PerformancePanel";
import { chartGeometry, episodeDays, MAX_POINTS, sampleIndexes, xLabels, yAxis } from "./performanceModel";

function reportWith(edit?: (p: NonNullable<FactorReport["performance"]>) => void): FactorReport {
  const report = withSection(cloneReport(), "performance");
  if (edit && report.performance) edit(report.performance);
  return report;
}

describe("PerformancePanel (lazy wrapper)", () => {
  it("renders nothing while the section is null", () => {
    const { container } = render(<PerformancePanel report={cloneReport()} />);
    expect(container.innerHTML).toBe("");
  });

  it("holds its place with the titled frame, then shows the body", async () => {
    const { container } = render(<PerformancePanel report={reportWith()} />);
    expect(container.querySelector("section#performance h2")?.textContent).toBe("Drawdown");
    expect(await screen.findByRole("table")).not.toBeNull();
    expect(container.querySelectorAll("section#performance")).toHaveLength(1);
  });
});

describe("PerformanceBody", () => {
  it("shows the title, the max drawdown aside and the outcome line of a fall that is not recovered", () => {
    const { container } = render(<PerformanceBody report={reportWith()} />);
    expect(screen.getByRole("heading", { level: 2, name: "Drawdown" })).not.toBeNull();
    expect(container.querySelector(".pm")?.textContent).toBe("Max drawdown −41.0%");
    expect(container.querySelector(".q")?.textContent).toBe(
      "SPY shrank 7.2% a year over the analysed range; its largest fall was 41.0%, from 2 Jan 2025 to 12 Mar 2026, and it had not recovered by 30 Sep 2026.",
    );
  });

  it("says recovered with the date when the price is back at the peak", () => {
    const report = reportWith((p) => {
      if (p.drawdown) p.drawdown.recovery_date = "2026-08-03";
    });
    const { container } = render(<PerformanceBody report={report} />);
    expect(container.querySelector(".q")?.textContent).toContain("and it was back at the peak by 3 Aug 2026.");
  });

  it("says the price never fell when there is no episode", () => {
    const report = reportWith((p) => {
      if (!p.drawdown) return;
      Object.assign(p.drawdown, { max_drawdown: 0, peak_date: null, trough_date: null, recovery_date: null, episodes: [] });
    });
    const { container } = render(<PerformanceBody report={report} />);
    expect(container.querySelector(".q")?.textContent).toBe(
      "SPY shrank 7.2% a year over the analysed range; its price never fell below an earlier high.",
    );
    expect(container.querySelector(".pm")?.textContent).toBe("Max drawdown 0%");
    expect(container.querySelector("table")).toBeNull();
  });

  it("draws the underwater chart: red line, light area, 0% axis down to a round depth, date labels", () => {
    const { container } = render(<PerformanceBody report={reportWith()} />);
    const chart = container.querySelector(".dd-chart");
    expect(chart?.getAttribute("role")).toBe("img");
    expect(chart?.getAttribute("aria-label")).toContain("Deepest fall −41.0%");
    expect(chart?.querySelector("path.dd-line")).not.toBeNull();
    expect(chart?.querySelector("path.dd-area")?.getAttribute("d")).toMatch(/^M0,0 L.*Z$/);
    const y = Array.from(chart?.querySelectorAll(".dd-y span") ?? []).map((e) => e.textContent);
    expect(y[0]).toBe("0%");
    expect(y).toEqual(["0%", "−20%", "−40%", "−60%"]);
    expect(chart?.querySelectorAll(".dd-x span").length).toBeGreaterThan(0);
  });

  it("lists the largest falls with fall, peak, low, recovered and days", () => {
    const { container } = render(<PerformanceBody report={reportWith()} />);
    expect(screen.getByRole("heading", { level: 3, name: "Largest falls" })).not.toBeNull();
    const heads = Array.from(container.querySelectorAll("thead th")).map((h) => h.textContent);
    expect(heads).toEqual(["Fall", "Peak", "Low", "Recovered", "Days"]);
    const rows = Array.from(container.querySelectorAll("tbody tr"));
    expect(rows).toHaveLength(5);
    const first = within(rows[0] as HTMLElement).getAllByRole("cell");
    expect(first.map((c) => c.textContent)).toEqual(["−41.0%", "2 Jan 2025", "12 Mar 2026", "not recovered", expect.stringMatching(/^\d+$/)]);
    expect(first[0]?.classList.contains("num-neg")).toBe(true);
    const second = within(rows[1] as HTMLElement).getAllByRole("cell");
    expect(second.map((c) => c.textContent)).toEqual(["−10.1%", "22 Nov 2024", "13 Dec 2024", "24 Dec 2024", "22"]);
  });

  it("shows at most five falls", () => {
    const report = reportWith((p) => {
      const d = p.drawdown;
      if (d) d.episodes = [...d.episodes, ...d.episodes];
    });
    const { container } = render(<PerformanceBody report={report} />);
    expect(container.querySelectorAll("tbody tr")).toHaveLength(5);
  });

  it("carries the past-performance caption and a fold with the compound-versus-arithmetic note", () => {
    const { container } = render(<PerformanceBody report={reportWith()} />);
    expect(container.querySelector(".foot > p")?.textContent).toBe("Past performance over the analysed range. It does not predict future returns.");
    const how = container.querySelector("details.how");
    expect(how?.querySelector("summary")?.textContent).toBe("How this is computed");
    expect(how?.textContent).toContain("compound growth rate, not the simple average");
    expect(how?.textContent).toContain("highest adjusted close so far");
  });

  it("shows the reason and one next step when the status is not ok", () => {
    const report = reportWith((p) => {
      p.status = "insufficient_data";
      p.reason = "Only 40 daily observations; at least 60 are needed.";
    });
    const { container } = render(<PerformanceBody report={report} />);
    expect(screen.getByText("Only 40 daily observations; at least 60 are needed.")).not.toBeNull();
    expect(screen.getByText("Widen the date range and run the report again.")).not.toBeNull();
    expect(container.querySelector("table, svg.dd-svg, .foot")).toBeNull();
  });

  it("shows the failed reason with a retry step", () => {
    const report = reportWith((p) => {
      p.status = "failed";
      p.reason = "The calculation failed.";
    });
    render(<PerformanceBody report={report} />);
    expect(screen.getByText("The calculation failed.")).not.toBeNull();
    expect(screen.getByText(/Run the report again later/)).not.toBeNull();
  });

  it("renders nothing while the section is null", () => {
    const { container } = render(<PerformanceBody report={cloneReport()} />);
    expect(container.innerHTML).toBe("");
  });

});

describe("performance model", () => {
  it("keeps every point up to the limit and at most 600 beyond it, first, last and the deepest included", () => {
    expect(sampleIndexes([0, -0.1, -0.2])).toEqual([0, 1, 2]);
    const values = Array.from({ length: 5000 }, (_, i) => -Math.abs(Math.sin(i / 90)) * 0.2);
    values[2345] = -0.5;
    const picked = sampleIndexes(values);
    expect(picked.length).toBeLessThanOrEqual(MAX_POINTS);
    expect(picked[0]).toBe(0);
    expect(picked[picked.length - 1]).toBe(4999);
    expect(picked).toContain(2345);
    expect([...picked].sort((a, b) => a - b)).toEqual(picked);
  });

  it("draws a long series with no more than 600 points", () => {
    const n = 3000;
    const dates = Array.from({ length: n }, (_, i) => new Date(Date.UTC(2015, 0, 1) + i * 86_400_000).toISOString().slice(0, 10));
    const values = Array.from({ length: n }, (_, i) => -((i % 100) / 100) * 0.3);
    const geo = chartGeometry(dates, values, -0.4);
    expect(geo.points).toBeLessThanOrEqual(MAX_POINTS);
    expect(geo.line.split(" L").length).toBe(geo.points);
  });

  it("picks round axes from 0 down to the deepest fall", () => {
    expect(yAxis(-0.245).ticks).toEqual([0, -0.1, -0.2, -0.3]);
    expect(yAxis(-0.41).ticks).toEqual([0, -0.2, -0.4, -0.6]);
    expect(yAxis(-0.4).bottom).toBe(-0.4);
    expect(yAxis(-0.03).ticks).toEqual([0, -0.01, -0.02, -0.03]);
    expect(yAxis(0).ticks.length).toBe(2);
    expect(yAxis(-0.9).bottom).toBe(-1);
  });

  it("places date labels inside the plot", () => {
    const labels = xLabels("2024-08-07", "2026-09-30");
    expect(labels.length).toBeGreaterThan(0);
    for (const l of labels) {
      expect(l.left).toBeGreaterThanOrEqual(1);
      expect(l.left).toBeLessThanOrEqual(99);
    }
  });

  it("counts days to the recovery, or to the end of the data when not recovered", () => {
    const dates = ["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05", "2024-01-08"];
    const base = { depth: -0.1, peak_date: "2024-01-03", trough_date: "2024-01-04", days_peak_to_trough: 1 };
    expect(episodeDays({ ...base, recovery_date: "2024-01-08", days_trough_to_recovery: 2 }, dates)).toBe(3);
    expect(episodeDays({ ...base, recovery_date: null, days_trough_to_recovery: null }, dates)).toBe(3);
    expect(episodeDays({ ...base, peak_date: "2023-01-01", recovery_date: null, days_trough_to_recovery: null }, dates)).toBeNull();
  });
});
