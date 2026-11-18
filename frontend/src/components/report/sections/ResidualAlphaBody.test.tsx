import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { FactorReport, ResidualAnalysis } from "../../../api/types";
import { cloneReport } from "../../../test/fixture";
import { withSection } from "../../../test/sectionFixtures";
import { ResidualAlphaBody as ResidualAlphaPanel, keptText } from "./ResidualAlphaBody";

/** The label texts the backend adds to a report that has the residual section (SC3.1). */
const LABELS = {
  "L-INSAMPLE": "In-sample: betas are fitted on this same period.",
  "L-PIT": "Point-in-time: each day uses betas estimated only from earlier days.",
  "L-DESC-PIT": "Descriptive and point-in-time, not predictive.",
  "L-HEDGE":
    "Compounded daily: a paper long-short hedge, rebalanced daily, before trading costs, financing and borrowing fees.",
};

function reportWith(edit?: (section: ResidualAnalysis, report: FactorReport) => void): FactorReport {
  const report = withSection(cloneReport(), "residual");
  report.label_text = { ...report.label_text, ...LABELS };
  if (edit) edit(report.residual as ResidualAnalysis, report);
  return report;
}

function mount(edit?: (section: ResidualAnalysis, report: FactorReport) => void) {
  return render(<ResidualAlphaPanel report={reportWith(edit)} />);
}

/** Text of the cells of the table row whose header starts with `label`. */
function rowText(container: HTMLElement, label: string): string[] {
  const th = Array.from(container.querySelectorAll<HTMLElement>(".res-table tbody th")).find((t) =>
    (t.textContent ?? "").startsWith(label),
  );
  if (!th) throw new Error(`no row ${label}`);
  return Array.from(th.parentElement?.querySelectorAll("td") ?? []).map((c) => c.textContent ?? "");
}

/** Set every number and date of a statistic to null, as the backend does when it is not ok. */
function blank(stat: object, keep: string[]): void {
  const rec = stat as Record<string, unknown>;
  for (const key of Object.keys(rec)) {
    if (keep.includes(key)) continue;
    if (typeof rec[key] === "number" || (typeof rec[key] === "string" && /^\d{4}-\d{2}-\d{2}$/.test(rec[key] as string))) {
      rec[key] = null;
    } else if (Array.isArray(rec[key]) && key === "findings") {
      rec[key] = [];
    }
  }
}

const STATS_KEEP = ["sample", "labels", "caption", "basis", "beta_window", "wiped_out", "status", "reason"];

function pitUnavailable(section: ResidualAnalysis): void {
  const reason = "Point-in-time residual needs at least 756 trading days; this period has 559.";
  section.point_in_time.status = "insufficient_data";
  section.point_in_time.reason = reason;
  blank(section.point_in_time, STATS_KEEP);
  section.gap.status = "insufficient_data";
  section.gap.reason = reason;
  blank(section.gap, ["sample", "labels", "caption", "beta_window", "status", "reason"]);
  section.gap.verdict = null;
  section.gap.severity = null;
  section.gap.message = null;
  section.chart.point_in_time_status = "insufficient_data";
  section.chart.point_in_time_reason = reason;
  section.chart.comparison_start = null;
  section.chart.in_sample_compare = section.chart.dates.map(() => null);
  section.chart.point_in_time_compare = section.chart.dates.map(() => null);
  section.calendar_years.years = section.calendar_years.years.map((y) => ({
    ...y,
    n_point_in_time: 0,
    point_in_time_sum: null,
    point_in_time_noise_sd: null,
  }));
}

describe("ResidualAlphaPanel: frame", () => {
  it("renders nothing while the section is null", () => {
    const { container } = render(<ResidualAlphaPanel report={cloneReport()} />);
    expect(container.innerHTML).toBe("");
  });

  it("has the title, the question and the element id of the contract", () => {
    const { container } = mount();
    const panel = container.querySelector("section#residual");
    expect(panel?.getAttribute("aria-labelledby")).toBe("residual-title");
    expect(screen.getByRole("heading", { level: 2 }).textContent).toBe("Residual return");
    expect(container.querySelector(".q")?.textContent).toBe(
      "What did this stock return beyond its factor exposures, and does it hold up without hindsight?",
    );
  });
});

describe("ResidualAlphaPanel: in-sample against point-in-time table", () => {
  it("prints both columns as the fixture says", () => {
    const { container } = mount();
    expect(rowText(container, "Residual return, a year")).toEqual([
      "+27.2% (15.4% to 39.1%)",
      "+25.4% (8.0% to 42.9%)",
    ]);
    expect(rowText(container, "t-statistic")).toEqual(["4.51 reliable", "2.86 reliable"]);
    expect(rowText(container, "Residual volatility")).toEqual(["10.3%", "10.9%"]);
    expect(rowText(container, "Residual Sharpe")).toEqual(["2.64 (1.50 to 3.79)", "2.33 (0.73 to 3.93)"]);
    expect(rowText(container, "Cumulative")).toEqual(["+80.8%", "+35.3%"]);
    expect(rowText(container, "Compound growth")).toEqual(["+30.6%", "+28.2%"]);
    expect(rowText(container, "Hit rate")).toEqual(["56.7%", "55.0%"]);
    expect(rowText(container, "Skew")).toEqual(["−0.13", "−0.14"]);
    expect(rowText(container, "Excess kurtosis")).toEqual(["0.56", "0.71"]);
  });

  it("states each column's dates and number of days", () => {
    const { container } = mount();
    expect(rowText(container, "Period")).toEqual([
      "8 Aug 2024 to 30 Sep 2026, 559 days",
      "29 Jul 2025 to 30 Sep 2026, 307 days",
    ]);
    const heads = Array.from(container.querySelectorAll(".res-table thead th")).map((h) => h.textContent);
    expect(heads).toContain("In-sample (static betas)");
    expect(heads).toContain("Point-in-time (trailing 252-day betas)");
  });

  it("gives the drawdown with true minus signs, its three dates and the noise reference as text", () => {
    const { container } = mount();
    const [ins, pit] = rowText(container, "Max drawdown");
    expect(ins).toBe("−6.5%Peak 22 Dec 2025Trough 12 Jan 2026Recovered 19 May 2026");
    expect(pit).toBe("−6.4%Peak 22 Dec 2025Trough 12 Jan 2026Recovered 15 May 2026");
    expect(rowText(container, "Drawdown of pure noise")).toEqual(["−17.5%", "−14.0%"]);
    expect(container.textContent).not.toMatch(/(^|[\s(])-\d/);
  });

  it("says a drawdown is not recovered and that a null peak is the start of the period", () => {
    const { container } = mount((s) => {
      s.in_sample.max_drawdown_peak = null;
      s.in_sample.max_drawdown_recovery = null;
    });
    const [ins] = rowText(container, "Max drawdown");
    expect(ins).toContain("Peak start of period");
    expect(ins).toContain("Not recovered");
  });

  it("marks a series with no drawdown without dates", () => {
    const { container } = mount((s) => {
      s.in_sample.max_drawdown = 0;
      s.in_sample.max_drawdown_peak = null;
      s.in_sample.max_drawdown_trough = null;
      s.in_sample.max_drawdown_recovery = null;
    });
    expect(rowText(container, "Max drawdown")[0]).toBe("0.0%");
  });

  it("uses a word, not colour, for the tag", () => {
    const { container } = mount((s) => {
      s.point_in_time.tag = "noise";
    });
    expect(rowText(container, "t-statistic")[1]).toBe("2.86 noise");
  });

  it("shows the reading rules as tooltips on the row names", () => {
    const { container } = mount();
    const th = Array.from(container.querySelectorAll(".res-table tbody th")).find((t) =>
      (t.textContent ?? "").startsWith("t-statistic"),
    );
    expect(th?.getAttribute("title")).toMatch(/you cannot tell it from zero/);
  });
});

describe("ResidualAlphaPanel: gap and verdict", () => {
  it("prints the same-days numbers, the gap, the share and what is kept", () => {
    const { container } = mount();
    const gap = container.querySelector(".res-gap") as HTMLElement;
    const facts = Array.from(gap.querySelectorAll(".res-facts > div")).map((d) => [
      d.querySelector("dt")?.textContent,
      d.querySelector("dd")?.textContent,
    ]);
    expect(facts).toEqual([
      ["Same days", "29 Jul 2025 to 30 Sep 2026, 307 days"],
      ["In-sample on these days", "+25.8% a year"],
      ["Point-in-time", "+25.4% a year"],
      ["Gap", "+0.4% a year (approximate test: z 0.42, p 0.675)"],
      ["Share of the full-period alpha (+27.2%) earned on these days", "95%"],
      ["Kept with point-in-time betas", "100% kept"],
    ]);
  });

  it("shows the verdict message with a glyph and a word", () => {
    const { container } = mount();
    const verdict = container.querySelector(".res-verdict") as HTMLElement;
    expect(verdict.className).toContain("info");
    expect(verdict.querySelector("svg.glyph")).not.toBeNull();
    expect(verdict.querySelector(".res-sev")?.textContent).toBe("Note");
    expect(verdict.querySelector("p")?.textContent).toBe(
      "Note In-sample alpha holds up out-of-sample with point-in-time betas (100% kept) and is distinguishable from zero. This rules out hindsight in the betas, not luck.",
    );
  });

  it("gives a warning verdict the word Warning and the warning style", () => {
    const { container } = mount((s) => {
      s.gap.verdict = "mostly_disappears";
      s.gap.severity = "warning";
      s.gap.survival_ratio = 0.3;
      s.gap.message =
        "In-sample alpha mostly disappears out-of-sample: point-in-time betas keep 30% of it (+7.8% a year against +25.8% on the same days).";
    });
    const verdict = container.querySelector(".res-gap .res-verdict") as HTMLElement;
    expect(verdict.className).toContain("warning");
    expect(verdict.querySelector(".res-sev")?.textContent).toBe("Warning");
    expect(verdict.textContent).toContain("mostly disappears out-of-sample");
    expect(container.querySelector(".res-facts")?.textContent).toContain("30% kept");
  });

  it("copes with a null verdict, message and ratios", () => {
    const { container } = mount((s) => {
      s.gap.verdict = null;
      s.gap.severity = null;
      s.gap.message = null;
      s.gap.survival_ratio = null;
      s.gap.comparison_share_of_alpha = null;
    });
    expect(container.querySelector(".res-gap .res-verdict")).toBeNull();
    const facts = container.querySelector(".res-gap .res-facts")?.textContent ?? "";
    expect(facts).toContain("Kept with point-in-time betasn/a");
    expect(facts).toContain("earned on these daysn/a");
  });

  it("rounds what is kept to 5 points and caps it at more than 200%", () => {
    expect(keptText(0.9837)).toBe("100% kept");
    expect(keptText(0.47)).toBe("45% kept");
    expect(keptText(-0.36)).toBe("−35% kept");
    expect(keptText(2.4)).toBe("more than 200% kept");
    expect(keptText(null)).toBe("n/a");
  });
});

describe("ResidualAlphaPanel: chart that is also a table", () => {
  it("draws the two comparison lines as React SVG, with no ECharts container", () => {
    const { container } = mount();
    const plot = screen.getByTestId("residual-chart");
    expect(plot.querySelector("svg")?.getAttribute("aria-hidden")).toBe("true");
    expect(Array.from(plot.querySelectorAll("path[data-line]")).map((p) => p.getAttribute("data-line"))).toEqual([
      "in_sample_compare",
      "point_in_time_compare",
    ]);
    for (const p of Array.from(plot.querySelectorAll("path[data-line]"))) {
      expect((p.getAttribute("d") ?? "").length).toBeGreaterThan(100);
    }
    expect(container.querySelector(".zero")).not.toBeNull();
  });

  it("starts both comparison lines at the anchor: no warm-up is drawn in the default view", () => {
    mount();
    const plot = screen.getByTestId("residual-chart");
    expect(plot.textContent).not.toContain("Warm-up");
    // 307 rows from the anchor, both lines start at the left edge (x = 0) at value 0.
    const d = plot.querySelector("path[data-line='point_in_time_compare']")?.getAttribute("d") ?? "";
    expect(d.startsWith("M0.00 ")).toBe(true);
  });

  it("switches to the full-period line, with the warm-up shaded and explained", () => {
    const { container } = mount();
    fireEvent.click(screen.getByLabelText("Full period, in-sample"));
    const plot = screen.getByTestId("residual-chart");
    expect(Array.from(plot.querySelectorAll("path[data-line]")).map((p) => p.getAttribute("data-line"))).toEqual([
      "in_sample_full",
    ]);
    expect(plot.textContent).toContain("Warm-up");
    expect(container.textContent).toContain(
      "Warm-up: the first 252 trading days are used to estimate the first point-in-time betas.",
    );
    fireEvent.click(screen.getByLabelText("Same days, both lines"));
    expect(screen.getByTestId("residual-chart").querySelectorAll("path[data-line]")).toHaveLength(2);
  });

  it("has a real radio group for the view, reachable by keyboard", () => {
    mount();
    const group = screen.getByRole("group", { name: "Residual chart view" });
    const radios = within(group).getAllByRole("radio");
    expect(radios.map((r) => (r as HTMLInputElement).checked)).toEqual([true, false]);
    expect(radios.every((r) => (r as HTMLInputElement).tabIndex !== -1)).toBe(true);
  });

  it("carries the line values in a table: lowest, highest and the end", () => {
    const report = reportWith();
    const { container } = render(<ResidualAlphaPanel report={report} />);
    const table = Array.from(container.querySelectorAll("table.res-mini")).find((t) =>
      (t.querySelector("caption")?.textContent ?? "").startsWith("Lowest, highest"),
    ) as HTMLElement;
    const rows = Array.from(table.querySelectorAll("tbody tr"));
    expect(rows).toHaveLength(3);
    const chart = (report.residual as ResidualAnalysis).chart;
    const last = (xs: (number | null)[]) => xs.filter((x): x is number => x !== null).slice(-1)[0] as number;
    const fmt = (x: number) => (x < 0 ? "−" : "+") + (Math.abs(x) * 100).toFixed(1) + "%";
    const ends = rows.map((r) => r.querySelector("td.strong")?.textContent);
    expect(ends).toEqual([
      fmt(last(chart.in_sample_full)),
      fmt(last(chart.in_sample_compare)),
      fmt(last(chart.point_in_time_compare)),
    ]);
    // The ends match the table's cumulative returns.
    expect(ends[0]).toBe("+80.8%");
    expect(ends[2]).toBe("+35.3%");
  });

  it("annotates the lines with the same-days rates and t-statistics", () => {
    const { container } = mount();
    const legend = container.querySelector(".res-legend")?.textContent ?? "";
    expect(legend).toContain("In-sample (static betas): +25.8% a year on these days (full-period alpha +27.2%, t = 4.51)");
    expect(legend).toContain("Point-in-time: +25.4% a year, t = 2.86");
  });

  it("states the compounding drag and the chart caption", () => {
    const { container } = mount();
    expect(container.textContent).toContain(
      "It sits below the residual return in the table by about half the residual variance a year (0.6% here).",
    );
    expect(container.textContent).toContain("Cumulative residual return, compounded daily.");
  });

  it("states the uncovered tail and shades it", () => {
    const { container } = mount((s) => {
      s.chart.n_uncovered = 12;
      s.chart.uncovered_from = "2026-10-01";
    });
    expect(container.textContent).toContain(
      "No factor data after 30 Sep 2026: the residual is unknown for the last 12 trading days.",
    );
    expect(screen.getByTestId("residual-chart").textContent).toContain("No factor data");
  });

  it("shows a wipe-out warning above the chart", () => {
    const { container } = mount((s) => {
      s.warnings.push({
        code: "residual_wipeout",
        message: "The hedged position lost all its capital on 2026-01-12; later days are not compounded.",
      });
    });
    const banner = container.querySelector("[data-warning='residual_wipeout']") as HTMLElement;
    expect(banner.className).toContain("warning");
    expect(banner.textContent).toContain("lost all its capital on 2026-01-12");
    // Above the chart, not in the caveat list.
    const chart = screen.getByTestId("residual-chart");
    expect(banner.compareDocumentPosition(chart) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(container.querySelector(".res-caveats [data-warning='residual_wipeout']")).toBeNull();
  });

  it("foots excluded days", () => {
    const { container } = mount((s) => {
      s.chart.n_excluded_in_span = 3;
    });
    expect(container.querySelector(".foot > p")?.textContent).toBe(
      "Skips 3 excluded days (listed under sample details).",
    );
  });
});

describe("ResidualAlphaPanel: stability", () => {
  it("is a native disclosure that is open", () => {
    const { container } = mount();
    const stab = container.querySelector("details.res-stab") as HTMLDetailsElement;
    expect(stab.open).toBe(true);
    expect(stab.querySelector("summary")).not.toBeNull();
  });

  it("draws the rolling alpha with its band and prints the summary", () => {
    const { container } = mount();
    const plot = screen.getByTestId("residual-rolling-chart");
    expect(plot.querySelector("path.res-band")?.getAttribute("d")?.length).toBeGreaterThan(100);
    expect(plot.querySelector("path[data-line='rolling_alpha']")).not.toBeNull();
    const dds = Array.from(container.querySelectorAll("dl[aria-label='Rolling one-year alpha, summary'] > div")).map(
      (d) => [d.querySelector("dt")?.textContent, d.querySelector("dd")?.textContent],
    );
    expect(dds[3]).toEqual(["Points whose 95% band excludes zero", "97.7%"]);
    expect(dds[0]?.[1]).toMatch(/^[+−]\d+\.\d% \(/);
    expect(container.textContent).toContain("Pointwise 95% band.");
  });

  it("lists the separate one-year windows with the corrected p and the count sentence", () => {
    const { container } = mount();
    expect(container.textContent).toContain(
      "2 of 2 separate one-year windows show an alpha different from zero, after correcting for testing 2 windows.",
    );
    const rows = Array.from(container.querySelectorAll("table[aria-labelledby='residual-windows-h'] tbody tr")).map(
      (r) => Array.from(r.children).map((c) => c.textContent),
    );
    expect(rows).toEqual([
      ["14 Oct 2025 to 30 Sep 2026252 days", "+19.5%", "9.4%", "2.09", "0.037", "0.037", "reliable"],
      ["24 Oct 2024 to 13 Oct 2025252 days", "+34.6%", "9.0%", "3.83", "<0.001", "<0.001", "reliable"],
    ]);
  });

  it("shows the split halves, their difference and the sentence", () => {
    const { container } = mount();
    const rows = Array.from(container.querySelectorAll("table[aria-labelledby='residual-split-h'] tbody tr")).map((r) =>
      Array.from(r.children).map((c) => c.textContent),
    );
    expect(rows[0]).toEqual(["First half8 Aug 2024 to 3 Sep 2025, 279 days", "+32.2%", "16.4% to 48.0%"]);
    expect(rows[1]).toEqual(["Second half4 Sep 2025 to 30 Sep 2026, 280 days", "+23.5%", "5.4% to 41.6%"]);
    expect(rows[2]).toEqual(["Second minus first", "−8.7%", "z −0.71, p 0.477"]);
    expect(container.textContent).toContain("Second-half alpha minus first-half alpha: −8.7% a year (p = 0.477).");
  });

  it("sums residuals by calendar year with the noise sd, marking partial years", () => {
    const { container } = mount();
    const rows = Array.from(container.querySelectorAll("table[aria-labelledby='residual-years-h'] tbody tr")).map((r) =>
      Array.from(r.children).map((c) => c.textContent),
    );
    expect(rows).toEqual([
      ["2024103 days, partial year", "+0.1703", "0.0658", "none", "n/a"],
      ["2025261 days", "+0.3001", "0.1048", "+0.1778112 days, partial", "0.0727"],
      ["2026195 days, partial year", "+0.1337", "0.0906", "+0.1320195 days, partial", "0.0960"],
    ]);
    expect(container.textContent).toContain(
      "A year within two noise standard deviations of zero is ordinary for a stock with no alpha.",
    );
  });

  it("lists the diagnostics findings for both series with their p-values", () => {
    const { container } = mount();
    const lists = container.querySelectorAll(".res-checks .notes");
    expect(lists).toHaveLength(2);
    expect(lists[0]?.textContent).toContain("No clear day-to-day correlation in residual returns.");
    expect(lists[0]?.textContent).toContain(
      "Residual returns have more extreme days than a normal distribution. Intervals are approximate. (Jarque-Bera, p = 0.013)",
    );
    expect(lists[1]?.textContent).toContain("No clear clustering of residual volatility. (ARCH, p = 0.978)");
    expect(container.textContent).toContain("Informational checks at the 5% level");
    expect(container.textContent).toContain("A rejection makes intervals approximate, not wrong.");
  });

  it("ends the section with the caution about searching for the best year", () => {
    const { container } = mount();
    expect(container.querySelector(".res-caution")?.textContent).toMatch(/^The halves and calendar years are fixed in advance\./);
    expect(container.querySelector(".res-caution")?.textContent).toContain("about 40% of the time even when nothing changed");
  });

  it("shows the reason of a stability block that is not ok, and keeps the others", () => {
    const { container } = mount((s) => {
      s.non_overlapping.status = "insufficient_data";
      s.non_overlapping.reason = "Too short for two separate windows.";
      s.non_overlapping.windows = [];
      s.non_overlapping.n_reliable = 0;
      s.non_overlapping.family_size = 0;
    });
    expect(container.textContent).toContain("Too short for two separate windows.");
    expect(container.querySelector("table[aria-labelledby='residual-windows-h']")).toBeNull();
    expect(container.querySelector("table[aria-labelledby='residual-split-h']")).not.toBeNull();
  });
});

describe("ResidualAlphaPanel: caveats and label texts", () => {
  it("lists the five caveats in order", () => {
    const { container } = mount();
    const items = Array.from(container.querySelectorAll(".res-caveats li")).map((li) => li.textContent);
    expect(items.slice(0, 5)).toEqual((reportWith().residual as ResidualAnalysis).caveats);
    expect(items[0]).toBe("You see the stock's return after removing what its five factor exposures explain. It includes alpha.");
    expect(items[4]).toBe("Past residual return does not predict future residual return.");
    // The fixture's own report-level warning follows the caveats.
    expect(items).toHaveLength(6);
  });

  it("folds the four label texts into How this is computed", () => {
    const { container } = mount();
    const how = container.querySelector("details.how") as HTMLDetailsElement;
    expect(how.open).toBe(false);
    expect(how.querySelector("summary")?.textContent).toBe("How this is computed");
    for (const text of Object.values(LABELS)) expect(how.textContent).toContain(text);
  });

  it("leaves out a label text the report does not carry", () => {
    const report = reportWith();
    report.label_text = {};
    const { container } = render(<ResidualAlphaPanel report={report} />);
    expect(container.querySelector("details.how")?.textContent).not.toContain("In-sample: betas are fitted");
  });
});

describe("ResidualAlphaPanel: statuses", () => {
  it("shows the reason and one next step, and no number, when the section failed", () => {
    const reason = "Residual analysis is unavailable because the regression could not be computed.";
    const { container } = mount((s) => {
      s.status = "failed";
      s.reason = reason;
    });
    expect(container.querySelector(".empty-what")?.textContent).toBe(reason);
    expect(container.querySelectorAll(".empty-do")).toHaveLength(1);
    expect(container.querySelector("table")).toBeNull();
    expect(container.querySelector("svg.line-svg")).toBeNull();
    expect(container.querySelector(".foot")).toBeNull();
    expect(container.querySelector(".q")?.textContent).toMatch(/^What did this stock return/);
    expect(container.textContent).not.toMatch(/\d\.\d/);
  });

  it("does the same for not_applicable", () => {
    const { container } = mount((s) => {
      s.status = "not_applicable";
      s.reason = "Residual is constant.";
    });
    expect(container.querySelector(".empty-what")?.textContent).toBe("Residual is constant.");
    expect(container.querySelector("table")).toBeNull();
  });

  it("keeps the in-sample parts when point-in-time has too little data", () => {
    const { container } = mount(pitUnavailable);
    const reason = "Point-in-time residual needs at least 756 trading days; this period has 559.";
    // In-sample column intact.
    expect(rowText(container, "Residual return, a year")).toEqual(["+27.2% (15.4% to 39.1%)"]);
    expect(rowText(container, "Cumulative")).toEqual(["+80.8%"]);
    // The point-in-time column is one cell with the reason and a next step, no numbers.
    const missing = container.querySelector("td.res-missing") as HTMLElement;
    expect(missing.getAttribute("rowspan")).toBe("12");
    expect(missing.querySelector(".empty-what")?.textContent).toBe(reason);
    expect(missing.querySelector(".empty-do")?.textContent).toBe("Choose a shorter beta window or a longer period.");
    expect(missing.textContent).not.toMatch(/\d\.\d/);
  });

  it("drops the gap statement and the toggle, and draws only the in-sample line, when point-in-time is missing", () => {
    const { container } = mount(pitUnavailable);
    expect(container.querySelector(".res-gap")).toBeNull();
    expect(container.querySelector(".res-verdict")).toBeNull();
    expect(screen.queryByRole("group", { name: "Residual chart view" })).toBeNull();
    const plot = screen.getByTestId("residual-chart");
    expect(Array.from(plot.querySelectorAll("path[data-line]")).map((p) => p.getAttribute("data-line"))).toEqual([
      "in_sample_full",
    ]);
    expect(plot.textContent).not.toContain("Warm-up");
    expect(container.querySelector(".res-chart .res-empty")?.textContent).toContain("needs at least 756 trading days");
    // The chart table lists only the in-sample line.
    const miniRows = container.querySelectorAll(".res-chart table.res-mini tbody tr");
    expect(miniRows).toHaveLength(1);
    // Stability stays: the rolling alpha and the calendar years (point-in-time cells empty).
    expect(screen.getByTestId("residual-rolling-chart")).not.toBeNull();
    expect(container.textContent).toContain("2025261 days");
  });

  it("shows the gap reason when the gap alone is not ok", () => {
    const { container } = mount((s) => {
      s.gap.status = "failed";
      s.gap.reason = "The gap could not be computed.";
      blank(s.gap, ["sample", "labels", "caption", "beta_window", "status", "reason"]);
      s.gap.verdict = null;
      s.gap.severity = null;
      s.gap.message = null;
    });
    expect(container.querySelector(".res-gap")?.textContent).toContain("The gap could not be computed.");
  });

  it("shows the reason of a missing in-sample column and keeps point-in-time", () => {
    const { container } = mount((s) => {
      s.in_sample.status = "not_applicable";
      s.in_sample.reason = "Residual is constant.";
      blank(s.in_sample, STATS_KEEP);
    });
    expect(container.querySelector("td.res-missing[data-basis='in_sample']")?.textContent).toContain("Residual is constant.");
    expect(rowText(container, "Residual return, a year")).toEqual(["+25.4% (8.0% to 42.9%)"]);
  });

  it("shows a chart that is not ok as its reason", () => {
    const { container } = mount((s) => {
      s.chart.status = "failed";
      s.chart.reason = "No chart.";
      s.chart.dates = [];
    });
    expect(container.querySelector(".res-chart .res-empty")?.textContent).toContain("No chart.");
    expect(screen.queryByTestId("residual-chart")).toBeNull();
  });
});

describe("ResidualAlphaPanel: accessibility and layout", () => {
  it("gives every table a caption or a name, and scoped headers", () => {
    const { container } = mount();
    const tables = Array.from(container.querySelectorAll("table"));
    expect(tables).toHaveLength(5);
    for (const t of tables) {
      const named = t.querySelector("caption") !== null || t.hasAttribute("aria-labelledby") || t.hasAttribute("aria-label");
      expect(named).toBe(true);
      for (const th of Array.from(t.querySelectorAll("th"))) expect(th.getAttribute("scope")).toMatch(/^(row|col)$/);
    }
  });

  it("puts every wide table in a focusable, labelled scroll region", () => {
    const { container } = mount();
    const regions = Array.from(container.querySelectorAll<HTMLElement>("[role='region'].scroll-x"));
    expect(regions).toHaveLength(4);
    for (const r of regions) {
      expect(r.tabIndex).toBe(0);
      expect(r.getAttribute("aria-label")).toMatch(/, scrolls sideways$/);
    }
  });

  it("hides the chart marks from assistive technology and uses no inline colour", () => {
    const { container } = mount();
    for (const svg of Array.from(container.querySelectorAll("svg.line-svg"))) {
      expect(svg.getAttribute("aria-hidden")).toBe("true");
    }
    expect(container.querySelector("[style*='color']")).toBeNull();
    expect(container.innerHTML).not.toMatch(/#[0-9a-f]{3,6}\b|rgb\(/i);
  });

  it("uses only the true minus sign in numbers", () => {
    const { container } = mount();
    expect(container.textContent).toContain("−8.7%");
    expect(container.textContent).not.toMatch(/(^|[\s(])-\d/);
  });

  it("keeps the chart's y labels and date ticks out of the accessibility tree", () => {
    mount();
    const plot = screen.getByTestId("residual-chart");
    expect(plot.querySelector(".ylabels")?.getAttribute("aria-hidden")).toBe("true");
    expect(plot.querySelector(".xlabels")?.getAttribute("aria-hidden")).toBe("true");
    expect(plot.querySelectorAll(".xlabels .xl").length).toBeGreaterThan(1);
    // The first and the last date label stay on a phone.
    const labels = Array.from(plot.querySelectorAll(".xlabels .xl"));
    expect(labels[0]?.classList.contains("keep")).toBe(true);
    expect(labels[labels.length - 1]?.classList.contains("keep")).toBe(true);
  });
});
