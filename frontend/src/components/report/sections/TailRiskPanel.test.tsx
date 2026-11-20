import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { FactorReport } from "../../../api/types";
import { cloneReport, monthlyReport } from "../../../test/fixture";
import { TAIL_RISK_MONTHLY, withSection } from "../../../test/sectionFixtures";
import { TailRiskPanel } from "./TailRiskPanel";
import {
  basedOn,
  CAPTION,
  forecastOf,
  GAUSSIAN_NOTE,
  groupsOf,
  levelName,
  loss,
  oneIn,
  place,
  rowLabel,
  rowsOf,
  scaleOf,
  shownFigures,
  tickText,
  ticksOf,
  whatItMeans,
} from "./tailRiskModel";

type Section = NonNullable<FactorReport["tail_risk"]>;
type Horizon = NonNullable<Section["by_horizon"]>[number];

/** Daily fixture: daily and monthly horizons are ok, the quarterly one has too few quarters. */
function daily(edit?: (s: Section) => void): FactorReport {
  const report = withSection(cloneReport(), "tail_risk");
  if (edit && report.tail_risk) edit(report.tail_risk);
  return report;
}

/** Monthly fixture (60 months): monthly and quarterly horizons, no daily one. */
function monthly(edit?: (s: Section) => void): FactorReport {
  const report = structuredClone(monthlyReport);
  report.tail_risk = structuredClone(TAIL_RISK_MONTHLY) as Section;
  if (edit) edit(report.tail_risk);
  return report;
}

function horizonOf(report: FactorReport, name: Horizon["horizon"]): Horizon {
  const h = report.tail_risk?.by_horizon?.find((x) => x.horizon === name);
  if (h === undefined) throw new Error(`no ${name} horizon in the fixture`);
  return h;
}

function select(name: string) {
  fireEvent.click(screen.getByRole("radio", { name }));
}

/** The bar row whose table name starts with `name` ("VaR 95%, Historical", "CVaR 97.5%, Forecast"). */
function rowOf(name: string): HTMLElement {
  const head = screen.getAllByRole("rowheader").find((h) => (h.textContent ?? "").startsWith(name));
  const row = head?.closest<HTMLElement>('[role="row"]');
  if (row === undefined || row === null) throw new Error(`no row named ${name}`);
  return row;
}

const tipOf = (row: HTMLElement): string => row.querySelector(".tr-tip")?.textContent ?? "";
const cellsOf = (row: HTMLElement): string[] => Array.from(row.querySelectorAll('[role="cell"]')).map((c) => c.textContent ?? "");
const levels = (c: HTMLElement): (string | null)[] => Array.from(c.querySelectorAll(".tr-lv b")).map((b) => b.textContent);

describe("TailRiskPanel", () => {
  it("renders nothing while the section is null", () => {
    const { container } = render(<TailRiskPanel report={cloneReport()} />);
    expect(container.innerHTML).toBe("");
  });

  it("draws a VaR group and a CVaR group, one level per row, two bars per level", () => {
    const { container } = render(<TailRiskPanel report={daily()} />);
    expect(container.querySelector("section#tail-risk h2")?.textContent).toBe("Tail risk");
    expect(screen.getAllByRole("rowgroup").map((g) => g.getAttribute("aria-label"))).toEqual(["VaR", "CVaR"]);
    expect(levels(container)).toEqual(["99%", "97.5%"]);
    const bars = Array.from(container.querySelectorAll(".tr-row")).map((r) => r.getAttribute("data-bar"));
    expect(bars).toEqual(["historical", "forecast", "historical", "forecast"]);
    expect(container.querySelector(".foot")?.textContent).toContain(CAPTION);
    expect(container.querySelector(".tr-badge")).toBeNull();
  });

  it("names the two bars once, in one legend", () => {
    const { container } = render(<TailRiskPanel report={daily()} />);
    const legends = container.querySelectorAll(".tr-legend");
    expect(legends).toHaveLength(1);
    const items = Array.from(legends[0]?.querySelectorAll("li") ?? []).map((li) => li.textContent);
    expect(items).toEqual(["Historical", "Forecast (Cornish-Fisher)", "90% band from resampling"]);
    expect(legends[0]?.querySelectorAll('[data-bar="historical"], [data-bar="forecast"]')).toHaveLength(2);
  });

  it("puts every bar on one scale and draws one axis for the whole panel", () => {
    const report = daily();
    const { container } = render(<TailRiskPanel report={report} />);
    const figures = report.tail_risk?.figures ?? [];
    const scale = scaleOf(shownFigures(groupsOf(figures)));
    const find = (measure: string, method: string) => figures.find((f) => f.measure === measure && f.method === method);
    for (const [name, f] of [
      ["VaR 99%, Historical", find("var", "historical")],
      ["VaR 99%, Forecast", find("var", "cornish_fisher")],
      ["CVaR 97.5%, Historical", find("cvar", "historical")],
      ["CVaR 97.5%, Forecast", find("cvar", "cornish_fisher")],
    ] as const) {
      const row = rowOf(name);
      const bar = row.querySelector(".tr-bar") as HTMLElement;
      expect(parseFloat(bar.style.width), name).toBeCloseTo(place(f?.value ?? 0, scale), 3);
      const band = row.querySelector(".tr-band") as HTMLElement;
      expect(parseFloat(band.style.left), name).toBeCloseTo(place(f?.band?.low ?? 0, scale), 3);
    }
    expect(container.querySelectorAll(".tr-axis")).toHaveLength(1);
    expect(container.querySelectorAll(".tr-grid")).toHaveLength(1);
    expect(container.textContent).not.toMatch(/Scale 0/);
    const ticks = Array.from(container.querySelectorAll(".tr-axis span:not(.tr-axis-t)")).map((s) => s.textContent);
    expect(ticks[0]).toBe("0");
    expect(ticks.length).toBeGreaterThan(2);
    expect(ticks.length).toBeLessThanOrEqual(5);
  });

  it("prints the value at the bar end: Historical and Forecast, with Gaussian left to the table", () => {
    const { container } = render(<TailRiskPanel report={daily()} />);
    expect(Array.from(container.querySelectorAll(".tr-val")).map((v) => v.textContent)).toEqual(["2.65%", "2.74%", "2.74%", "2.75%"]);
    expect(Array.from(container.querySelectorAll(".tr-track, .tr-tip")).map((t) => t.textContent).join(" ")).not.toContain("2.81%");
    const gaussian = rowOf("VaR 99%, Gaussian");
    expect(cellsOf(gaussian)).toEqual(["2.81%", "2.67% to 2.96%", expect.stringContaining("90% band")]);
    expect(gaussian.className).toBe("vh");
    expect(gaussian.querySelector(".tr-bar")).toBeNull();
  });

  it("starts on the daily horizon for a daily subject and counts the days", () => {
    const { container } = render(<TailRiskPanel report={daily()} />);
    expect(screen.getByRole("radio", { name: "Daily" })).toHaveProperty("checked", true);
    expect(container.querySelector(".pm")?.textContent).toBe("Based on 720 days");
    expect(container.querySelector(".q")?.textContent).toBe("How large a loss does a bad day bring?");
    expect(tipOf(rowOf("VaR 99%, Historical"))).toContain("Exceeded on 1 day in 100");
  });

  it("switches to the monthly horizon: its own bars, its own count, the 95% levels first", () => {
    const report = daily();
    const { container } = render(<TailRiskPanel report={report} />);
    select("Monthly");
    expect(screen.getByRole("radio", { name: "Monthly" })).toHaveProperty("checked", true);
    const months = horizonOf(report, "monthly").series?.n_obs ?? 0;
    expect(months).toBeGreaterThan(12);
    expect(container.querySelector(".pm")?.textContent).toBe(`Based on ${months} months`);
    expect(container.querySelector(".q")?.textContent).toBe("How large a loss does a bad month bring?");
    expect(levels(container)).toEqual(["95%", "99%", "95%", "97.5%"]);
    expect(tipOf(rowOf("VaR 95%, Historical"))).toContain("Exceeded on 1 month in 20");
    select("Daily");
    expect(container.querySelector(".pm")?.textContent).toBe("Based on 720 days");
    expect(levels(container)).toEqual(["99%", "97.5%"]);
  });

  it("shows the reason of a horizon with too few periods instead of the chart", () => {
    const { container } = render(<TailRiskPanel report={daily()} />);
    select("Quarterly");
    expect(container.querySelector(".tr-gap")?.textContent).toContain("at least 12 quarterly returns");
    expect(container.querySelector(".tr-chart")).toBeNull();
    expect(container.querySelector(".tr-legend")).toBeNull();
    expect(container.querySelector(".pm")).toBeNull();
    expect(screen.getByRole("radio", { name: "Quarterly" })).toHaveProperty("checked", true);
  });

  it("flags an indicative Forecast with a striped bar and a caution mark, and gives the reason in the tooltip", () => {
    const { container } = render(<TailRiskPanel report={daily()} />);
    select("Monthly");
    const row = rowOf("VaR 99%, Forecast");
    expect(row.querySelector(".tr-bar")?.className).toContain("ind");
    expect(row.querySelector(".tr-val .tr-ind-ic")).not.toBeNull();
    expect(tipOf(row)).toContain("Indicative: not monotone on z in [-3.5, 3.5] (Maillard 2012); indicative only.");
    expect(tipOf(row)).toContain("Method: Cornish-Fisher.");
    const legend = container.querySelector(".tr-legend")?.textContent ?? "";
    expect(legend).toContain("Indicative: use with care");
    const plain = rowOf("VaR 99%, Gaussian");
    expect(plain.querySelector(".tr-ind-ic")).toBeNull();
  });

  it("keeps a far-from-historical reason in the tooltip of the flagged figure", () => {
    const reason = "far from historical (10.2% vs 5.0%)";
    const report = daily((s) => {
      // The panel reads the daily horizon; the top-level figures are the same list in the fixture.
      for (const list of [s.figures, s.by_horizon?.find((h) => h.horizon === "daily")?.figures]) {
        const f = list?.find((x) => x.method === "cornish_fisher" && x.measure === "var");
        if (f) Object.assign(f, { indicative: true, reason });
      }
    });
    render(<TailRiskPanel report={report} />);
    const row = rowOf("VaR 99%, Forecast");
    expect(row.querySelector(".tr-ind-ic")).not.toBeNull();
    expect(tipOf(row)).toContain("Indicative: far from historical (10.2% vs 5.0%).");
  });

  it("marks approximate bands in the tooltip and leaves validated ones alone", () => {
    render(<TailRiskPanel report={daily()} />);
    expect(tipOf(rowOf("VaR 99%, Forecast"))).toContain("approximate (tends to be narrow)");
    expect(tipOf(rowOf("VaR 99%, Historical"))).not.toContain("approximate");
    expect(cellsOf(rowOf("VaR 99%, Gaussian"))[2]).not.toContain("approximate");
  });

  it("shows a figure whose band is hidden without a band overlay, with the reason in the tooltip", () => {
    render(<TailRiskPanel report={monthly()} />);
    const row = rowOf("CVaR 97.5%, Forecast");
    expect(row.querySelector(".tr-val")?.textContent).toBe("10.9%");
    expect(row.querySelector(".tr-band")).toBeNull();
    expect(row.querySelector(".tr-bar")).not.toBeNull();
    expect(row.querySelector(".tr-val .tr-info")).not.toBeNull();
    expect(tipOf(row)).toContain("No band: only 507 of 1000 resamples inside the valid range");
  });

  it("lets the keyboard reach the bars with one tab stop and the arrow keys, and Escape hides a tooltip", () => {
    const { container } = render(<TailRiskPanel report={daily()} />);
    const rows = Array.from(container.querySelectorAll<HTMLElement>(".tr-row"));
    expect(rows.filter((r) => r.tabIndex === 0)).toHaveLength(1);
    expect(rows[0]?.tabIndex).toBe(0);
    rows[0]?.focus();
    fireEvent.keyDown(rows[0] as HTMLElement, { key: "ArrowDown" });
    expect(document.activeElement).toBe(rows[1]);
    expect(rows.filter((r) => r.tabIndex === 0)).toEqual([rows[1]]);
    fireEvent.keyDown(rows[1] as HTMLElement, { key: "End" });
    expect(document.activeElement).toBe(rows[3]);
    fireEvent.keyDown(rows[3] as HTMLElement, { key: "Home" });
    expect(document.activeElement).toBe(rows[0]);
    fireEvent.keyDown(rows[0] as HTMLElement, { key: "Escape" });
    expect(rows[0]?.dataset.esc).toBe("1");
    fireEvent.blur(rows[0] as HTMLElement);
    expect(rows[0]?.dataset.esc).toBeUndefined();
    expect(tipOf(rows[0] as HTMLElement)).toContain("Estimate 2.65%");
    expect(rows[0]?.querySelector(".tr-tip")?.getAttribute("aria-hidden")).toBe("true");
  });

  it("is also a table: every method of every level, with the estimate, the band and the notes", () => {
    render(<TailRiskPanel report={daily()} />);
    const table = screen.getByRole("table");
    expect(within(table).getAllByRole("columnheader").map((c) => c.textContent)).toEqual(["Level and method", "Estimate", "Band", "Notes"]);
    const names = within(table)
      .getAllByRole("rowheader")
      .map((h) => h.textContent);
    expect(names).toEqual([
      "VaR 99%, Historical",
      "VaR 99%, Forecast (Cornish-Fisher)",
      "VaR 99%, Gaussian",
      "CVaR 97.5%, Historical",
      "CVaR 97.5%, Forecast (Cornish-Fisher)",
      "CVaR 97.5%, Gaussian",
    ]);
    expect(cellsOf(rowOf("VaR 99%, Historical"))[0]).toBe("2.65%");
    expect(cellsOf(rowOf("VaR 99%, Historical"))[1]).toBe("2.48% to 3.15%");
  });

  it("lists all three methods with their bands in How this is computed", () => {
    const { container } = render(<TailRiskPanel report={monthly()} />);
    const how = container.querySelector("details.how") as HTMLElement;
    const text = how.textContent ?? "";
    expect(text).toContain("All three methods, with their 90% bands");
    const row = Array.from(how.querySelectorAll(".tr-all-row")).find((r) => r.querySelector("b")?.textContent === "VaR 99%");
    expect(row?.textContent).toBe("VaR 99% Historical n/a; Gaussian 11.2% (9.1% to 13.1%); Cornish-Fisher 11.0% (8.7% to 12.6%)");
    expect(how.querySelectorAll(".tr-all-row")).toHaveLength(4);
    expect(text).toContain("Gaussian tag");
  });
});

describe("TailRiskPanel on a monthly record", () => {
  it("starts on the monthly horizon and has no daily switch", () => {
    const { container } = render(<TailRiskPanel report={monthly()} />);
    expect(screen.getAllByRole("radio").map((r) => (r as HTMLInputElement).labels?.[0]?.textContent)).toEqual([
      "Monthly",
      "Quarterly",
    ]);
    expect(screen.queryByRole("radio", { name: "Daily" })).toBeNull();
    expect(screen.getByRole("radio", { name: "Monthly" })).toHaveProperty("checked", true);
    expect(container.querySelector(".pm")?.textContent).toBe("Based on 60 months");
    expect(levels(container)).toEqual(["95%", "99%", "95%", "97.5%"]);
    expect(container.querySelector(".tr-lines")?.textContent).not.toContain(" day");
  });

  it("shows a muted n/a marker where the historical figure has too few tail months, with the reason in the tooltip", () => {
    const { container } = render(<TailRiskPanel report={monthly()} />);
    for (const name of ["VaR 99%, Historical", "CVaR 97.5%, Historical"]) {
      const row = rowOf(name);
      expect(row.querySelector(".tr-na")?.textContent).toBe("n/a");
      expect(row.querySelector(".tr-bar")).toBeNull();
      expect(row.querySelector(".tr-band")).toBeNull();
      expect(cellsOf(row)[0]).toBe("n/a");
      expect(tipOf(row)).toContain("expected tail observations");
    }
    expect(tipOf(rowOf("VaR 99%, Historical"))).toContain("0.6 expected tail observations");
    // A reason is never a row of its own: nothing but the bars and the n/a marker is in the chart rows.
    expect(container.querySelector(".tr-note")).toBeNull();
    expect(container.querySelectorAll(".tr-na")).toHaveLength(2);
    expect(rowOf("VaR 95%, Historical").querySelector(".tr-val")?.textContent).toBe("8.6%");
    expect(rowOf("VaR 99%, Forecast").querySelector(".tr-val")?.textContent).toBe("11.0%");
  });

  it("switches to quarters: the count, the question, n/a Historical and a Gaussian Forecast where Cornish-Fisher is n/a", () => {
    const report = monthly();
    const { container } = render(<TailRiskPanel report={report} />);
    select("Quarterly");
    expect(container.querySelector(".pm")?.textContent).toBe("Based on 20 quarters");
    expect(container.querySelector(".q")?.textContent).toBe("How large a loss does a bad quarter bring?");
    expect(rowOf("VaR 99%, Historical").querySelector(".tr-na")).not.toBeNull();
    expect(tipOf(rowOf("VaR 99%, Historical"))).toContain("0.2 expected tail observations");
    expect(tipOf(rowOf("VaR 95%, Historical"))).toContain("Exceeded on 1 quarter in 20");
    // Cornish-Fisher is n/a for CVaR, so the Forecast bar is the Gaussian figure, tagged.
    const row = rowOf("CVaR 97.5%, Forecast (Gaussian)");
    expect(row.querySelector(".tr-val")?.textContent).toBe("15.7%Gaussian");
    expect(row.querySelector(".tr-tag")?.textContent).toBe("Gaussian");
    expect(tipOf(row)).toContain(GAUSSIAN_NOTE);
    expect(tipOf(row)).toContain("Method: Gaussian.");
    expect(row.querySelector(".tr-bar")).not.toBeNull();
    const hidden = rowOf("CVaR 97.5%, Cornish-Fisher");
    expect(cellsOf(hidden)[0]).toBe("n/a");
    expect(cellsOf(hidden)[2]).toContain("Outside the valid range of the expansion");
    // The tag has room, and the legend explains it.
    expect(container.querySelector<HTMLElement>(".tr-chart")?.style.getPropertyValue("--tr-end")).toBe("128px");
    expect(container.querySelector(".tr-legend")?.textContent).toContain("Shown where Cornish-Fisher is n/a");
    expect(rowOf("VaR 99%, Forecast").querySelector(".tr-tag")).toBeNull();
  });

  it("keeps the tag room and the tag legend out of a chart that has no Gaussian stand-in", () => {
    const { container } = render(<TailRiskPanel report={monthly()} />);
    expect(container.querySelector(".tr-tag")).toBeNull();
    expect(container.querySelector<HTMLElement>(".tr-chart")?.style.getPropertyValue("--tr-end")).toBe("72px");
    expect(container.querySelector(".tr-legend")?.textContent).not.toContain("Gaussian");
  });

  it("shows only its own figures when the report has no by_horizon field", () => {
    const report = monthly((s) => {
      delete s.by_horizon;
    });
    const { container } = render(<TailRiskPanel report={report} />);
    expect(screen.queryAllByRole("radio")).toHaveLength(0);
    expect(container.querySelector(".pm")?.textContent).toBe("Based on 60 months");
    expect(container.querySelectorAll(".tr-level")).toHaveLength(4);
  });

  it("shows the reason as the empty state when the section is not ok", () => {
    const report = structuredClone(monthlyReport);
    report.tail_risk = {
      status: "insufficient_data",
      reason: "Insufficient data: VaR and CVaR need at least 12 monthly returns; this series has 8.",
      sample: (TAIL_RISK_MONTHLY as Section).sample,
      frequency: null,
      series: null,
      figures: null,
    };
    const { container } = render(<TailRiskPanel report={report} />);
    expect(container.querySelector(".empty-what")?.textContent).toContain("need at least 12 monthly returns");
    expect(container.querySelector(".tr-chart")).toBeNull();
  });
});

describe("tail risk model", () => {
  it("names rows, losses, sample sizes and what each level means", () => {
    expect(rowLabel("var", 0.99)).toBe("VaR 99%");
    expect(rowLabel("cvar", 0.975)).toBe("CVaR 97.5%");
    expect(rowLabel("cvar", 0.95)).toBe("CVaR 95%");
    expect(levelName(0.975)).toBe("97.5%");
    expect(oneIn(0.95, "monthly")).toBe("1 month in 20");
    expect(oneIn(0.99, "daily")).toBe("1 day in 100");
    expect(loss(0.02649)).toBe("2.65%");
    expect(loss(0.0517, 1)).toBe("5.2%");
    expect(loss(-0.004)).toBe("−0.40%");
    expect(basedOn(1, "daily")).toBe("1 day");
    expect(basedOn(1234, "daily")).toBe("1,234 days");
    expect(basedOn(60, "monthly")).toBe("60 months");
    expect(basedOn(1, "quarterly")).toBe("1 quarter");
    expect(basedOn(20, "quarterly")).toBe("20 quarters");
    expect(whatItMeans("var", 0.99, "daily")).toBe("Exceeded on 1 day in 100");
    expect(whatItMeans("var", 0.95, "monthly")).toBe("Exceeded on 1 month in 20");
    expect(whatItMeans("cvar", 0.975, "quarterly")).toBe("Average loss in the worst 1 quarter in 40");
  });

  it("groups figures by measure and level in the order sent", () => {
    const figures = (TAIL_RISK_MONTHLY as Section).figures ?? [];
    expect(rowsOf(figures).map((r) => r.label)).toEqual(["VaR 99%", "CVaR 97.5%", "VaR 95%", "CVaR 95%"]);
    expect(rowsOf(figures)[0]?.cells.gaussian?.value).toBeCloseTo(0.1124, 3);
  });

  it("builds a VaR group and a CVaR group, lowest level first, each level with a Historical and a Forecast bar", () => {
    const figures = (TAIL_RISK_MONTHLY as Section).figures ?? [];
    const groups = groupsOf(figures);
    expect(groups.map((g) => [g.label, g.levels.map((l) => l.label)])).toEqual([
      ["VaR", ["VaR 95%", "VaR 99%"]],
      ["CVaR", ["CVaR 95%", "CVaR 97.5%"]],
    ]);
    for (const l of groups.flatMap((g) => g.levels)) expect(l.bars.map((b) => b.key)).toEqual(["historical", "forecast"]);
  });

  it("takes Cornish-Fisher for the Forecast, Gaussian where it has no value, and tags only that case", () => {
    const cells = rowsOf((TAIL_RISK_MONTHLY as Section).figures ?? [])[0]?.cells;
    if (!cells) throw new Error("fixture has no figures");
    expect(forecastOf(cells)).toMatchObject({ source: "cornish_fisher", fallback: false });
    const noCf = { ...cells, cornish_fisher: cells.cornish_fisher && { ...cells.cornish_fisher, value: null } };
    expect(forecastOf(noCf)).toMatchObject({ source: "gaussian", fallback: true });
    expect(forecastOf(noCf).figure?.value).toBeCloseTo(0.1124, 3);
    const none = { ...noCf, gaussian: noCf.gaussian && { ...noCf.gaussian, value: null } };
    expect(forecastOf(none)).toMatchObject({ source: "cornish_fisher", fallback: false });
    expect(forecastOf(none).figure?.value).toBeNull();
  });

  it("builds one round scale that covers every shown value and band end, with at most four axis steps", () => {
    const figures = (TAIL_RISK_MONTHLY as Section).figures ?? [];
    const shown = shownFigures(groupsOf(figures));
    const scale = scaleOf(shown);
    expect(scale.lo).toBe(0);
    const largest = Math.max(...shown.flatMap((f) => [f.value ?? 0, f.band?.high ?? 0]));
    expect(scale.hi).toBeGreaterThanOrEqual(largest);
    expect(scale.hi - largest).toBeLessThan(0.05);
    expect(Math.round(scale.hi * 1000) / 10).toBeCloseTo(scale.hi * 100, 9);
    expect(scaleOf([])).toEqual({ lo: 0, hi: 0.005 });
    expect(place(0.09, { lo: 0, hi: 0.18 })).toBeCloseTo(50, 9);
    expect(place(0.5, { lo: 0, hi: 0.18 })).toBe(100);
    expect(ticksOf({ lo: 0, hi: 0.14 })).toEqual([0, 0.05, 0.1]);
    expect(ticksOf({ lo: 0, hi: 0.035 })).toEqual([0, 0.01, 0.02, 0.03]);
    expect(ticksOf({ lo: -0.02, hi: 0.1 }).length).toBeLessThanOrEqual(5);
    expect(ticksOf({ lo: 0, hi: 0.05 })).toEqual([0, 0.02, 0.04]);
    expect(tickText(0)).toBe("0");
    expect(tickText(0.025)).toBe("2.5%");
    expect(tickText(0.1)).toBe("10%");
  });

  it("extends the scale below zero for a figure that is a gain", () => {
    const [f] = (TAIL_RISK_MONTHLY as Section).figures ?? [];
    if (!f) throw new Error("fixture has no figures");
    const scale = scaleOf([{ ...f, value: -0.012, band: null }]);
    expect(scale.lo).toBeLessThan(0);
    expect(scale.lo).toBeLessThanOrEqual(-0.012);
  });
});
