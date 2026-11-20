import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { FactorReport } from "../../../api/types";
import { cloneReport, monthlyReport } from "../../../test/fixture";
import { TAIL_RISK_MONTHLY, withSection } from "../../../test/sectionFixtures";
import { TailRiskPanel } from "./TailRiskPanel";
import { basedOn, CAPTION, loss, rowLabel, rowsOf } from "./tailRiskModel";

type Section = NonNullable<FactorReport["tail_risk"]>;

function daily(edit?: (s: Section) => void): FactorReport {
  const report = withSection(cloneReport(), "tail_risk");
  if (edit && report.tail_risk) edit(report.tail_risk);
  return report;
}

function monthly(edit?: (s: Section) => void): FactorReport {
  const report = structuredClone(monthlyReport);
  report.tail_risk = structuredClone(TAIL_RISK_MONTHLY) as Section;
  if (edit) edit(report.tail_risk);
  return report;
}

function cellOf(row: string, column: string): HTMLElement {
  const table = screen.getByRole("table");
  const col = within(table)
    .getAllByRole("columnheader")
    .findIndex((h) => h.textContent === column);
  const tr = within(table).getByRole("row", { name: new RegExp(`^${row}`) });
  return within(tr).getAllByRole("cell")[col - 1] as HTMLElement;
}

describe("TailRiskPanel", () => {
  it("renders nothing while the section is null", () => {
    const { container } = render(<TailRiskPanel report={cloneReport()} />);
    expect(container.innerHTML).toBe("");
  });

  it("shows the daily rows, the three method columns and the caption", () => {
    const { container } = render(<TailRiskPanel report={daily()} />);
    expect(container.querySelector("section#tail-risk h2")?.textContent).toBe("Tail risk");
    expect(screen.getAllByRole("columnheader").map((h) => h.textContent)).toEqual([
      "Measure",
      "Historical",
      "Gaussian",
      "Cornish-Fisher",
    ]);
    expect(screen.getAllByRole("rowheader").map((h) => h.textContent)).toEqual(["VaR 99%", "CVaR 97.5%"]);
    expect(container.querySelector(".foot")?.textContent).toContain(
      "Losses are shown as positive numbers. Results are at the series' own frequency, with no scaling to other horizons.",
    );
    expect(CAPTION).toBe(
      "Losses are shown as positive numbers. Results are at the series' own frequency, with no scaling to other horizons.",
    );
  });

  it("shows the loss as a positive percentage, the 90% band and the number of days", () => {
    render(<TailRiskPanel report={daily()} />);
    const cell = cellOf("VaR 99%", "Gaussian");
    expect(cell.textContent).toContain("2.81%");
    expect(cell.textContent).toContain("90% band");
    expect(cell.textContent).toMatch(/band \d\.\d\d% to \d\.\d\d%/);
    expect(cell.textContent).toContain("based on 720 days");
    expect(cell.textContent).not.toContain("−");
    expect(cell.textContent).not.toContain("approximate");
  });

  it("labels approximate bands and leaves validated ones alone", () => {
    render(<TailRiskPanel report={daily()} />);
    expect(cellOf("VaR 99%", "Cornish-Fisher").textContent).toContain("approximate (tends to be narrow)");
    expect(cellOf("CVaR 97.5%", "Historical").textContent).toContain("approximate (tends to be narrow)");
    expect(cellOf("VaR 99%", "Historical").textContent).not.toContain("approximate");
    expect(cellOf("CVaR 97.5%", "Gaussian").textContent).not.toContain("approximate");
  });

  it("labels an indicative Cornish-Fisher figure", () => {
    const report = daily((s) => {
      const f = s.figures?.find((x) => x.method === "cornish_fisher" && x.measure === "var");
      if (f) Object.assign(f, { indicative: true, reason: "not monotone on z in [-3.5, 3.5] (Maillard 2012); indicative only" });
    });
    render(<TailRiskPanel report={report} />);
    expect(cellOf("VaR 99%", "Cornish-Fisher").textContent).toContain("indicative");
    expect(cellOf("VaR 99%", "Gaussian").textContent).not.toContain("indicative");
  });

  it("gives the reason of an indicative figure as the tooltip of its label", () => {
    const reason = "far from historical (10.2% vs 5.0%)";
    const report = daily((s) => {
      const f = s.figures?.find((x) => x.method === "cornish_fisher" && x.measure === "var");
      if (f) Object.assign(f, { indicative: true, reason });
    });
    render(<TailRiskPanel report={report} />);
    const flag = within(cellOf("VaR 99%", "Cornish-Fisher")).getByText("indicative");
    expect(flag.getAttribute("title")).toBe(reason);
  });

  it("shows the reason of a hidden band in place of the band", () => {
    render(<TailRiskPanel report={monthly()} />);
    const cell = cellOf("CVaR 97.5%", "Cornish-Fisher");
    expect(cell.textContent).toContain("10.92%");
    expect(cell.textContent).toContain("only 507 of 1000 resamples inside the valid range");
    expect(cell.textContent).not.toContain("band 0");
  });
});

describe("TailRiskPanel on a monthly record", () => {
  it("adds the 95% rows and counts months", () => {
    render(<TailRiskPanel report={monthly()} />);
    expect(screen.getAllByRole("rowheader").map((h) => h.textContent)).toEqual([
      "VaR 99%",
      "CVaR 97.5%",
      "VaR 95%",
      "CVaR 95%",
    ]);
    const cell = cellOf("VaR 95%", "Historical");
    expect(cell.textContent).toContain("8.58%");
    expect(cell.textContent).toContain("based on 60 months");
    expect(cell.textContent).not.toContain("days");
  });

  it("shows n/a with the reason as text where the historical figure has too few tail months", () => {
    render(<TailRiskPanel report={monthly()} />);
    for (const row of ["VaR 99%", "CVaR 97.5%"]) {
      const cell = cellOf(row, "Historical");
      expect(cell.textContent).toContain("n/a");
      expect(cell.textContent).toContain("expected tail observations");
      expect(cell.textContent).not.toContain("based on");
    }
    expect(cellOf("VaR 99%", "Historical").textContent).toContain("0.6 expected tail observations");
    expect(cellOf("VaR 99%", "Gaussian").textContent).toContain("11.24%");
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
    expect(container.querySelector("table")).toBeNull();
  });
});

describe("tail risk model", () => {
  it("names rows, losses and sample sizes", () => {
    expect(rowLabel("var", 0.99)).toBe("VaR 99%");
    expect(rowLabel("cvar", 0.975)).toBe("CVaR 97.5%");
    expect(rowLabel("cvar", 0.95)).toBe("CVaR 95%");
    expect(loss(0.02649)).toBe("2.65%");
    expect(loss(-0.004)).toBe("−0.40%");
    expect(basedOn(1, false)).toBe("1 day");
    expect(basedOn(1234, false)).toBe("1,234 days");
    expect(basedOn(60, true)).toBe("60 months");
  });

  it("groups figures by measure and level in the order sent", () => {
    const figures = (TAIL_RISK_MONTHLY as Section).figures ?? [];
    expect(rowsOf(figures).map((r) => r.label)).toEqual(["VaR 99%", "CVaR 97.5%", "VaR 95%", "CVaR 95%"]);
    expect(rowsOf(figures)[0]?.cells.gaussian?.value).toBeCloseTo(0.1124, 3);
  });
});
