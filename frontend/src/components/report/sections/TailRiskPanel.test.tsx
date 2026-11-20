import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { FactorReport } from "../../../api/types";
import { cloneReport, monthlyReport } from "../../../test/fixture";
import { TAIL_RISK_MONTHLY, withSection } from "../../../test/sectionFixtures";
import { TailRiskPanel } from "./TailRiskPanel";
import { basedOn, CAPTION, loss, place, rowLabel, rowsOf, scaleOf, scaleText, whatItMeans } from "./tailRiskModel";

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

/** The labels of the groups on show, in order ("VaR 99%", "CVaR 97.5%", ...). */
function groupNames(container: HTMLElement): (string | null)[] {
  return Array.from(container.querySelectorAll(".tr-group")).map((g) => g.getAttribute("aria-label"));
}

/** The line of one method inside the group of one measure and level. */
function lineOf(group: string, method: string): HTMLElement {
  const g = screen.getByRole("group", { name: group });
  const badge = within(g).getByText(method, { selector: ".tr-badge" });
  return badge.closest("li") as HTMLElement;
}

describe("TailRiskPanel", () => {
  it("renders nothing while the section is null", () => {
    const { container } = render(<TailRiskPanel report={cloneReport()} />);
    expect(container.innerHTML).toBe("");
  });

  it("shows one line per method and level, with the three method badges", () => {
    const { container } = render(<TailRiskPanel report={daily()} />);
    expect(container.querySelector("section#tail-risk h2")?.textContent).toBe("Tail risk");
    expect(groupNames(container)).toEqual(["VaR 99%", "CVaR 97.5%"]);
    for (const group of ["VaR 99%", "CVaR 97.5%"]) {
      const g = screen.getByRole("group", { name: group });
      expect(Array.from(g.querySelectorAll(".tr-badge")).map((b) => b.textContent)).toEqual([
        "Historical",
        "Gaussian",
        "Cornish-Fisher",
      ]);
    }
    expect(container.querySelector(".foot")?.textContent).toContain(CAPTION);
    expect(container.querySelector("table")).toBeNull();
  });

  it("draws the band as a whisker and the estimate as a dot, named for screen readers", () => {
    const { container } = render(<TailRiskPanel report={daily()} />);
    const line = lineOf("VaR 99%", "Gaussian");
    const whisker = line.querySelector(".tr-wh") as HTMLElement;
    expect(whisker.getAttribute("role")).toBe("img");
    expect(whisker.getAttribute("aria-label")).toMatch(/^Estimate \d\.\d\d%, 90% band \d\.\d\d% to \d\.\d\d%$/);
    const band = whisker.querySelector(".tr-band") as HTMLElement;
    const dot = whisker.querySelector(".tr-dot") as HTMLElement;
    const left = parseFloat(band.style.left);
    const width = parseFloat(band.style.width);
    const at = parseFloat(dot.style.left);
    expect(width).toBeGreaterThan(0);
    expect(at).toBeGreaterThanOrEqual(left);
    expect(at).toBeLessThanOrEqual(left + width);
    expect(line.textContent).toContain("2.81%");
    expect(line.textContent).not.toContain("−");
    expect(container.querySelector(".tr-flag")).toBeNull();
  });

  it("puts the dot where the figure sits on the scale shared by the measure", () => {
    const report = daily();
    render(<TailRiskPanel report={report} />);
    const figures = report.tail_risk?.figures ?? [];
    const scale = scaleOf(figures.filter((f) => f.measure === "var"));
    const gaussian = figures.find((f) => f.method === "gaussian" && f.measure === "var");
    expect(gaussian?.value).toBeDefined();
    const dot = lineOf("VaR 99%", "Gaussian").querySelector(".tr-dot") as HTMLElement;
    expect(parseFloat(dot.style.left)).toBeCloseTo(place(gaussian?.value ?? 0, scale), 3);
    expect(screen.getByRole("group", { name: "VaR 99%" }).textContent).toContain(scaleText(scale));
  });

  it("starts on the daily horizon for a daily subject and counts the days", () => {
    const { container } = render(<TailRiskPanel report={daily()} />);
    expect(screen.getByRole("radio", { name: "Daily" })).toHaveProperty("checked", true);
    expect(container.querySelector(".pm")?.textContent).toBe("Based on 720 days");
    expect(container.querySelector(".q")?.textContent).toBe("How large a loss does a bad day bring?");
    expect(screen.getByRole("group", { name: "VaR 99%" }).textContent).toContain("Exceeded on 1 day in 100");
  });

  it("switches to the monthly horizon: its own lines, its own count, the 95% rows", () => {
    const report = daily();
    const { container } = render(<TailRiskPanel report={report} />);
    select("Monthly");
    expect(screen.getByRole("radio", { name: "Monthly" })).toHaveProperty("checked", true);
    const months = horizonOf(report, "monthly").series?.n_obs ?? 0;
    expect(months).toBeGreaterThan(12);
    expect(container.querySelector(".pm")?.textContent).toBe(`Based on ${months} months`);
    expect(container.querySelector(".q")?.textContent).toBe("How large a loss does a bad month bring?");
    expect(groupNames(container)).toEqual([
      "VaR 99%",
      "CVaR 97.5%",
      "VaR 95%",
      "CVaR 95%",
    ]);
    expect(screen.getByRole("group", { name: "VaR 95%" }).textContent).toContain("Exceeded on 1 month in 20");
    select("Daily");
    expect(container.querySelector(".pm")?.textContent).toBe("Based on 720 days");
  });

  it("shows the reason of a horizon with too few periods instead of lines", () => {
    const report = daily();
    const { container } = render(<TailRiskPanel report={report} />);
    select("Quarterly");
    expect(container.querySelector(".tr-gap")?.textContent).toContain("at least 12 quarterly returns");
    expect(container.querySelectorAll(".tr-group")).toHaveLength(0);
    expect(container.querySelector(".pm")).toBeNull();
    expect(screen.getByRole("radio", { name: "Quarterly" })).toHaveProperty("checked", true);
  });

  it("labels an indicative figure and shows its reason underneath", () => {
    render(<TailRiskPanel report={daily()} />);
    select("Monthly");
    const line = lineOf("VaR 95%", "Cornish-Fisher");
    expect(within(line).getByText("Indicative")).toBeTruthy();
    expect(line.querySelector(".tr-why")?.textContent).toBe(
      "Not monotone on z in [-3.5, 3.5] (Maillard 2012); indicative only",
    );
    expect(line.querySelector(".tr-wh")?.className).toContain("ind");
    const other = lineOf("VaR 95%", "Gaussian");
    expect(other.querySelector(".tr-flag")).toBeNull();
    expect(other.querySelector(".tr-wh")?.className).not.toContain("ind");
  });

  it("shows a far-from-historical reason in sentence case", () => {
    const reason = "far from historical (10.2% vs 5.0%)";
    const report = daily((s) => {
      // The panel reads the daily horizon; the top-level figures are the same list in the fixture.
      for (const list of [s.figures, s.by_horizon?.find((h) => h.horizon === "daily")?.figures]) {
        const f = list?.find((x) => x.method === "cornish_fisher" && x.measure === "var");
        if (f) Object.assign(f, { indicative: true, reason });
      }
    });
    render(<TailRiskPanel report={report} />);
    const line = lineOf("VaR 99%", "Cornish-Fisher");
    expect(within(line).getByText("Indicative")).toBeTruthy();
    expect(within(line).getByText("Far from historical (10.2% vs 5.0%)")).toBeTruthy();
  });

  it("marks approximate bands in the tooltip of the range and leaves validated ones alone", () => {
    render(<TailRiskPanel report={daily()} />);
    expect(lineOf("VaR 99%", "Cornish-Fisher").querySelector(".tr-r")?.getAttribute("title")).toBe(
      "approximate (tends to be narrow)",
    );
    expect(lineOf("VaR 99%", "Gaussian").querySelector(".tr-r")?.getAttribute("title")).toBeNull();
  });

  it("shows the reason of a hidden band under the line, with no whisker bar", () => {
    render(<TailRiskPanel report={monthly()} />);
    const line = lineOf("CVaR 97.5%", "Cornish-Fisher");
    expect(line.textContent).toContain("10.9%");
    expect(line.querySelector(".tr-band")).toBeNull();
    expect(line.querySelector(".tr-dot")).not.toBeNull();
    expect(line.textContent).toContain("no band");
    expect(line.querySelector(".tr-why")?.textContent).toContain("Only 507 of 1000 resamples inside the valid range");
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
    expect(groupNames(container)).toEqual([
      "VaR 99%",
      "CVaR 97.5%",
      "VaR 95%",
      "CVaR 95%",
    ]);
    expect(container.querySelector(".tr-lines")?.textContent).not.toContain("day");
  });

  it("shows n/a with its reason where the historical figure has too few tail months", () => {
    render(<TailRiskPanel report={monthly()} />);
    for (const group of ["VaR 99%", "CVaR 97.5%"]) {
      const line = lineOf(group, "Historical");
      expect(line.textContent).toContain("n/a");
      expect(line.textContent).toContain("expected tail observations");
      expect(line.querySelector(".tr-dot")).toBeNull();
      expect(line.querySelector(".tr-wh")?.getAttribute("aria-label")).toBe("No figure");
    }
    expect(lineOf("VaR 99%", "Historical").textContent).toContain("0.6 expected tail observations");
    expect(lineOf("VaR 99%", "Gaussian").textContent).toContain("11.2%");
    expect(lineOf("VaR 95%", "Historical").textContent).toContain("8.6%");
  });

  it("switches to quarters: the count, the question and the n/a rows of the quarterly horizon", () => {
    const report = monthly();
    const { container } = render(<TailRiskPanel report={report} />);
    select("Quarterly");
    expect(container.querySelector(".pm")?.textContent).toBe("Based on 20 quarters");
    expect(container.querySelector(".q")?.textContent).toBe("How large a loss does a bad quarter bring?");
    const hist = lineOf("VaR 99%", "Historical");
    expect(hist.textContent).toContain("n/a");
    expect(hist.textContent).toContain("0.2 expected tail observations");
    const cf = lineOf("CVaR 95%", "Cornish-Fisher");
    expect(cf.textContent).toContain("n/a");
    expect(cf.querySelector(".tr-why")?.textContent).toContain("Outside the valid range of the expansion");
    expect(screen.getByRole("group", { name: "VaR 95%" }).textContent).toContain("Exceeded on 1 quarter in 20");
  });

  it("shows only its own figures when the report has no by_horizon field", () => {
    const report = monthly((s) => {
      delete s.by_horizon;
    });
    const { container } = render(<TailRiskPanel report={report} />);
    expect(screen.queryAllByRole("radio")).toHaveLength(0);
    expect(container.querySelector(".pm")?.textContent).toBe("Based on 60 months");
    expect(groupNames(container)).toHaveLength(4);
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
    expect(container.querySelector(".tr-lines")).toBeNull();
  });
});

describe("tail risk model", () => {
  it("names rows, losses, sample sizes and what each level means", () => {
    expect(rowLabel("var", 0.99)).toBe("VaR 99%");
    expect(rowLabel("cvar", 0.975)).toBe("CVaR 97.5%");
    expect(rowLabel("cvar", 0.95)).toBe("CVaR 95%");
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

  it("builds one round scale per measure that covers every value and band end", () => {
    const figures = (TAIL_RISK_MONTHLY as Section).figures ?? [];
    for (const measure of ["var", "cvar"] as const) {
      const part = figures.filter((f) => f.measure === measure);
      const scale = scaleOf(part);
      expect(scale.lo).toBe(0);
      const largest = Math.max(...part.flatMap((f) => [f.value ?? 0, f.band?.high ?? 0]));
      expect(scale.hi).toBeGreaterThanOrEqual(largest);
      expect(scale.hi - largest).toBeLessThan(0.05);
      expect(Math.round(scale.hi * 1000) / 10).toBeCloseTo(scale.hi * 100, 9);
    }
    expect(scaleText({ lo: 0, hi: 0.18 })).toBe("Scale 0 to 18%");
    expect(scaleText(scaleOf([]))).toBe("Scale 0 to 0.5%");
    expect(place(0.09, { lo: 0, hi: 0.18 })).toBeCloseTo(50, 9);
    expect(place(0.5, { lo: 0, hi: 0.18 })).toBe(100);
  });

  it("extends the scale below zero for a figure that is a gain", () => {
    const [f] = (TAIL_RISK_MONTHLY as Section).figures ?? [];
    if (!f) throw new Error("fixture has no figures");
    const scale = scaleOf([{ ...f, value: -0.012, band: null }]);
    expect(scale.lo).toBeLessThan(0);
    expect(scale.lo).toBeLessThanOrEqual(-0.012);
  });
});
