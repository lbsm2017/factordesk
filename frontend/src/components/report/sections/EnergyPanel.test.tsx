import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { FactorReport } from "../../../api/types";
import { signed } from "../../../format";
import { tickLabel, valueDigits } from "../exposureModel";
import { cloneReport } from "../../../test/fixture";
import { withSection } from "../../../test/sectionFixtures";
import { EnergyPanel, legsOf, moveFor, overlaps, RISE, sentence, VIF_WARN, whisker } from "./EnergyPanel";

type Section = NonNullable<FactorReport["energy"]>;

function report(edit?: (s: Section) => void): FactorReport {
  const r = withSection(cloneReport(), "energy");
  if (edit && r.energy) edit(r.energy);
  return r;
}

function section(r: FactorReport): Section {
  if (r.energy == null) throw new Error("fixture has no energy section");
  return r.energy;
}

function says(container: HTMLElement): string[] {
  return Array.from(container.querySelectorAll(".en-says li")).map((li) => li.textContent ?? "");
}

describe("EnergyPanel", () => {
  it("renders nothing while the section is absent", () => {
    const { container } = render(<EnergyPanel report={cloneReport()} />);
    expect(container.innerHTML).toBe("");
  });

  it("shows one table with one row per price: oil, gas and carbon, and no market row", () => {
    const { container } = render(<EnergyPanel report={report()} />);
    expect(container.querySelectorAll("table")).toHaveLength(1);
    const labels = Array.from(container.querySelectorAll("tbody .en-label")).map((n) => n.textContent);
    expect(labels).toEqual(["Oil", "Natural gas", "Carbon"]);
    expect(container.textContent).not.toContain("controlled for");
    expect(container.querySelector("tbody")?.textContent).not.toContain("largest");
    expect(container.querySelector(".reading")).toBeNull();
    expect(container.querySelector(".foot > p")).toBeNull();
  });

  it("takes oil and gas from the long model and carbon from the carbon model", () => {
    const s = section(report());
    const legs = legsOf(s);
    expect(legs.map((l) => l.code)).toEqual(["oil", "gas", "co2"]);
    expect(legs[0]?.beta).toBe(s.long_model?.rows.find((x) => x.code === "oil")?.beta);
    expect(legs[1]?.beta).toBe(s.long_model?.rows.find((x) => x.code === "gas")?.beta);
    expect(legs[2]?.beta).toBe(s.carbon_model?.rows.find((x) => x.code === "co2")?.beta);
  });

  it("gives only the carbon row a note: the start of its shorter window", () => {
    const { container } = render(<EnergyPanel report={report()} />);
    expect(container.querySelector('tr[data-leg="co2"] .en-note')?.textContent).toMatch(/^since [A-Z][a-z]{2} \d{4}$/);
    expect(container.querySelectorAll("tbody .en-note")).toHaveLength(1);
  });

  it("shows the sensitivity and t of every row, and keeps the market and the VIFs in the fold", () => {
    const { container } = render(<EnergyPanel report={report()} />);
    expect(container.querySelectorAll("tbody tr")).toHaveLength(3);
    expect(container.querySelectorAll("thead th")).toHaveLength(4);
    expect(container.querySelector("thead")?.textContent).not.toContain("VIF");
    const how = container.querySelector("details.how")?.textContent ?? "";
    expect(how).toContain("variance inflation factor");
    expect(how).toContain("Market");
  });

  it("writes a sentence for each reliable price and nothing for the weak ones", () => {
    const r = report((s) => {
      for (const m of [s.long_model, s.carbon_model]) for (const row of m?.rows ?? []) row.tag = row.code === "oil" ? "reliable" : "noise";
    });
    const lines = says(render(<EnergyPanel report={r} />).container);
    expect(lines).toHaveLength(1);
    expect(lines[0]).toMatch(/^A 10% rise in oil went with a [+−]?[0-9.]+% move in .+, after the market\.$/);
    expect(lines.join(" ")).not.toMatch(/beta|ln\(|±|\bSE\b/);
  });

  it("writes the sentence of the owner's example: a 10% rise in oil and the move in the subject", () => {
    expect(RISE).toBe(0.1);
    // Oil is a log change: a 10% rise is ln(1.10). Carbon is a plain return: 0.10.
    expect(moveFor("oil", 0.2)).toBeCloseTo(0.2 * Math.log(1.1), 12);
    expect(moveFor("co2", 0.2)).toBeCloseTo(0.02, 12);
    expect(sentence({ code: "oil", beta: 0.2, tag: "reliable" }, "SPY")).toBe(
      "A 10% rise in oil went with a +1.9% move in SPY, after the market.",
    );
    expect(sentence({ code: "mkt_rf", beta: 1, tag: "reliable" }, "SPY")).toBeNull();
  });

  it("shows two decimals when the move is below 0.05% and one decimal otherwise", () => {
    // Oil beta 0.004 gives a move of 0.004 * ln(1.10), about 0.038%, so it reads "+0.04%" not "+0.0%".
    expect(sentence({ code: "oil", beta: 0.004, tag: "reliable" }, "SPY")).toContain("went with a +0.04% move");
    expect(sentence({ code: "oil", beta: 0.004, tag: "reliable" }, "SPY")).not.toContain("0.0%");
    // Carbon is a plain return: beta 0.004 gives a move of 0.0004, which is 0.04%.
    expect(sentence({ code: "co2", beta: 0.004, tag: "reliable" }, "SPY")).toContain("went with a +0.04% move");
    // Oil beta 0.02 gives about +0.19%, which is above the bar and keeps one decimal.
    expect(sentence({ code: "oil", beta: 0.02, tag: "reliable" }, "SPY")).toContain("went with a +0.2% move");
  });

  it("uses no formula on screen and calls the numbers sensitivities", () => {
    const { container } = render(<EnergyPanel report={report()} />);
    const visible = (container.textContent ?? "").replace(/Benjamini-Hochberg/g, "");
    expect(visible).not.toMatch(/beta/i);
    expect(visible).not.toMatch(/ln\(|±|1\.96/);
    expect(container.querySelector("thead")?.textContent).toContain("Sensitivity");
  });

  it("draws one dot per row, all on one shared scale", () => {
    const { container } = render(<EnergyPanel report={report()} />);
    const rows = Array.from(container.querySelectorAll("tbody tr"));
    for (const tr of rows) {
      expect(tr.querySelectorAll("circle.en-dot")).toHaveLength(1);
      expect(tr.querySelectorAll("line.zero")).toHaveLength(1);
      expect(tr.querySelector("svg")?.getAttribute("aria-hidden")).toBe("true");
    }
    const gridX = (tr: Element | undefined) =>
      Array.from(tr?.querySelectorAll("line.grid, line.zero") ?? []).map((l) => l.getAttribute("x1"));
    expect(gridX(rows[0])).toEqual(gridX(rows[2]));
  });

  it("takes the line as the sensitivity ± 1.96 standard errors", () => {
    const w = whisker({ beta: 0.4, se: 0.05 });
    expect(w?.low).toBeCloseTo(0.4 - 1.96 * 0.05, 10);
    expect(w?.high).toBeCloseTo(0.4 + 1.96 * 0.05, 10);
    expect(whisker({ beta: 0.4, se: null as unknown as number })).toBeNull();
  });

  it("adds a caution line only when a price overlaps with the others above a VIF of 5", () => {
    expect(VIF_WARN).toBe(5);
    expect(overlaps({ vif: 5 })).toBe(false);
    expect(overlaps({ vif: 5.01 })).toBe(true);
    expect(render(<EnergyPanel report={report()} />).container.querySelector(".en-overlap")).toBeNull();
    const r = report((s) => {
      for (const row of s.long_model?.rows ?? []) row.vif = row.code === "oil" ? 7.34 : 1.5;
    });
    const { container } = render(<EnergyPanel report={r} />);
    expect(container.querySelector(".en-overlap")?.textContent).toMatch(/^Oil overlaps with the other prices/);
  });

  it("keeps the series that limits the window and the gas caveat in the fold", () => {
    const r = report((s) => {
      if (s.long_model) s.long_model.window_limited_by = "DHHNGSP";
      if (s.carbon_model) s.carbon_model.window_limited_by = "KRBN";
    });
    const { container } = render(<EnergyPanel report={r} />);
    const how = container.querySelector("details.how")?.textContent ?? "";
    expect(how).toContain("the window starts when DHHNGSP begins");
    expect(how).toContain("the window starts when KRBN begins");
    expect(how).toContain(section(r).gas_note);
  });

  it("shows the note when an older cached copy of Brent or Henry Hub was used", () => {
    const r = report((s) => {
      s.fred_note = "Brent: used the copy of 2026-11-18";
    });
    const { container } = render(<EnergyPanel report={r} />);
    expect(container.querySelector(".en-fred-note")?.textContent).toBe("Brent: used the copy of 2026-11-18");
    expect(render(<EnergyPanel report={report()} />).container.querySelector(".en-fred-note")).toBeNull();
  });

  it("hides the carbon row and says why when it has too little data", () => {
    const r = report((s) => {
      s.carbon_model = null;
      s.carbon_note = "The carbon model is hidden: this window holds only 300 trading days of carbon data, and at least 2 years are needed.";
    });
    const { container } = render(<EnergyPanel report={r} />);
    expect(container.querySelectorAll("tbody tr")).toHaveLength(2);
    expect(container.querySelector(".en-carbon-note")?.textContent).toContain("at least 2 years");
  });

  it("keeps the details in the fold", () => {
    const { container } = render(<EnergyPanel report={report()} />);
    const how = container.querySelector("details.how")?.textContent ?? "";
    expect(how).toContain("Newey-West");
    expect(how).toContain("No lagged terms");
    expect(how).toContain("Without the largest gas moves");
    expect(how).toContain("Nothing is trimmed or capped");
    expect(how).toContain("Series start:");
    expect(how).toContain("R²");
    expect(container.querySelector("table")?.textContent ?? "").not.toContain("Newey-West");
  });

  it("shows the notice and no table when the section could not be computed (FRED down)", () => {
    const r = report((s) => {
      s.status = "failed";
      s.reason = "The Brent or Henry Hub price series could not be fetched from FRED, so the energy and carbon section is not shown.";
      s.long_model = null;
      s.carbon_model = null;
    });
    render(<EnergyPanel report={r} />);
    expect(screen.getByText(/could not be fetched from FRED/).textContent).toContain("energy and carbon section");
    expect(screen.queryByRole("table")).toBeNull();
    expect(screen.getByText(/rest of the report is not affected/i)).toBeTruthy();
  });
});

describe("EnergyPanel with small sensitivities", () => {
  function small(r: FactorReport): void {
    const s = section(r);
    for (const m of [s.long_model, s.carbon_model]) {
      if (!m) continue;
      for (const row of m.rows) {
        row.beta = row.beta * 0.001;
        row.se = row.se * 0.001;
      }
      m.gas_robust.beta = m.gas_robust.beta * 0.001;
      m.gas_robust.se = m.gas_robust.se * 0.001;
    }
  }

  it("labels distinct axis ticks and shows at least two significant digits", () => {
    const r = report();
    small(r);
    const { container } = render(<EnergyPanel report={r} />);
    const axes = Array.from(container.querySelectorAll(".en-axis .axis"));
    expect(axes.length).toBeGreaterThan(0);
    for (const axis of axes) {
      const texts = Array.from(axis.querySelectorAll("span")).map((n) => n.textContent ?? "");
      expect(new Set(texts).size).toBe(texts.length);
    }
    const betas = Array.from(container.querySelectorAll("tbody td.num:nth-child(2)")).map((n) => n.textContent ?? "");
    expect(betas.length).toBeGreaterThan(0);
    for (const b of betas) expect(b).not.toMatch(/^[+−]?0\.000$/);
  });
});

describe("axis and value formats", () => {
  it("tickLabel keeps ticks apart at a tiny scale and is unchanged at a normal one", () => {
    const tiny = [-0.001, -0.0005, 0, 0.0005, 0.001];
    const texts = tiny.map((t) => tickLabel(t, tiny, 2));
    expect(new Set(texts).size).toBe(tiny.length);
    expect(texts[2]).toBe("0");
    const normal = [-1, -0.5, 0, 0.5, 1];
    expect(normal.map((t) => tickLabel(t, normal, 2))).toEqual(["−1", "−0.50", "0", "0.50", "1"]);
  });

  it("valueDigits gives two significant digits, never fewer than the minimum", () => {
    expect(signed(0.0021, valueDigits(0.0021, 3))).toBe("+0.0021");
    expect(signed(0.0000123, valueDigits(0.0000123, 3))).toBe("+0.000012");
    expect(signed(0.412, valueDigits(0.412, 3))).toBe("+0.412");
    expect(valueDigits(0, 3)).toBe(3);
  });
});
