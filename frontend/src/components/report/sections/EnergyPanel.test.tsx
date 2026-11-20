import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { FactorReport } from "../../../api/types";
import { signed } from "../../../format";
import { tickLabel, valueDigits } from "../exposureModel";
import { cloneReport } from "../../../test/fixture";
import { withSection } from "../../../test/sectionFixtures";
import { EnergyPanel, INTRO, moveFor, overlaps, RISE, sentence, VIF_WARN, whisker } from "./EnergyPanel";

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

describe("EnergyPanel", () => {
  it("renders nothing while the section is absent", () => {
    const { container } = render(<EnergyPanel report={cloneReport()} />);
    expect(container.innerHTML).toBe("");
  });

  it("shows the long model and the carbon model, each with its legs in plain words", () => {
    const r = report();
    const { container } = render(<EnergyPanel report={r} />);
    const models = Array.from(container.querySelectorAll(".en-model"));
    expect(models.map((m) => m.getAttribute("data-model"))).toEqual(["long", "carbon"]);
    const labels = (m: Element | undefined) =>
      Array.from(m?.querySelectorAll("tbody .en-label") ?? []).map((n) => n.textContent);
    expect(labels(models[0])).toEqual(["Market", "Oil", "Natural gas", "Natural gas without the 5 largest days"]);
    expect(labels(models[1])).toEqual(["Market", "Oil", "Natural gas", "Natural gas without the 5 largest days", "Carbon"]);
    expect(container.querySelector(".reading")?.textContent).toBe(INTRO);
  });

  it("labels the carbon model as a short sample, mainly EU carbon", () => {
    const { container } = render(<EnergyPanel report={report()} />);
    const start = section(report()).carbon_model?.start ?? "";
    expect(container.querySelector('[data-model="carbon"] .en-tag')?.textContent).toMatch(
      /^short sample, since [A-Z][a-z]{2} \d{4}, mainly EU carbon$/,
    );
    expect(start).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    expect(container.querySelector('[data-model="long"] .en-tag')).toBeNull();
  });

  it("shows the sensitivity, t and the VIF of every leg", () => {
    const r = report();
    const { container } = render(<EnergyPanel report={r} />);
    const s = section(r);
    const long = s.long_model;
    expect(long).not.toBeNull();
    const rows = Array.from(container.querySelectorAll('[data-model="long"] tbody tr'));
    // market, oil, gas, gas without the 5 largest, in that order; carbon has a fifth row in its own table
    expect(rows).toHaveLength(4);
    const vifCells = Array.from(container.querySelectorAll('[data-model="long"] .en-vif')).map((c) => c.textContent);
    expect(vifCells).toHaveLength(3); // one per leg; the robustness row has no VIF of its own
    expect(vifCells).toEqual((long?.rows ?? []).map((row) => row.vif.toFixed(2)));
  });

  it("shows the gas sensitivity again without the five largest moves, with its t", () => {
    const r = report();
    const { container } = render(<EnergyPanel report={r} />);
    const gas = section(r).long_model?.gas_robust;
    expect(gas?.n_excluded).toBe(5);
    const row = container.querySelector('[data-model="long"] tr.en-robust');
    expect(row).not.toBeNull();
    expect(row?.querySelectorAll("td")[0]?.textContent).toMatch(/^[+−]?[0-9.]+$/);
    expect(container.querySelector('[data-model="long"] tr.en-robust .en-vif')).toBeNull();
  });

  it("calls the daily gas sensitivity descriptive and keeps the caveat as the footnote", () => {
    const r = report();
    const { container } = render(<EnergyPanel report={r} />);
    expect(container.querySelector('[data-model="long"] tbody .en-note')?.textContent).toContain("daily figures are descriptive");
    expect(container.querySelector(".foot > p")?.textContent).toBe(section(r).gas_note);
    expect(section(r).gas_note).toContain("descriptive");
  });

  it("counts months, not days, for a monthly section", () => {
    const r = report((s) => {
      s.frequency = "monthly";
    });
    const { container } = render(<EnergyPanel report={r} />);
    expect(container.querySelector('[data-model="long"] tbody .en-robust .en-label')?.textContent).toBe(
      "Natural gas without the 5 largest months",
    );
    expect(container.querySelector('[data-model="long"] tbody .en-note')?.textContent).not.toContain("descriptive");
  });

  it("writes the sentence of the owner's example: a 10% rise in oil and the move in the subject", () => {
    expect(RISE).toBe(0.1);
    // Oil is a log change: a 10% rise is ln(1.10). Carbon is a plain return: 0.10.
    expect(moveFor("oil", 0.2)).toBeCloseTo(0.2 * Math.log(1.1), 12);
    expect(moveFor("co2", 0.2)).toBeCloseTo(0.02, 12);
    const text = sentence({ code: "oil", beta: 0.2, tag: "reliable" }, "SPY");
    expect(text).toBe("A 10% rise in oil went with a +1.9% move in SPY, after the market.");
    expect(sentence({ code: "mkt_rf", beta: 1, tag: "reliable" }, "SPY")).toBeNull();
    expect(sentence({ code: "gas", beta: 0.001, tag: "noise" }, "SPY")).toBe(
      "A 10% rise in natural gas went with a 0.0% move in SPY, after the market. The link is too weak to rely on.",
    );
    const { container } = render(<EnergyPanel report={report()} />);
    const lines = Array.from(container.querySelectorAll('[data-model="long"] .en-says li')).map((li) => li.textContent ?? "");
    expect(lines.length).toBeGreaterThanOrEqual(3);
    expect(lines[0]).toMatch(/^A 10% rise in oil went with a [+−]?[0-9.]+% move in .+, after the market/);
    expect(lines.join(" ")).not.toMatch(/beta|ln\(|±|\bSE\b/);
  });

  it("uses no formula on screen and calls the numbers sensitivities", () => {
    const { container } = render(<EnergyPanel report={report()} />);
    const visible = (container.textContent ?? "").replace(/Benjamini-Hochberg/g, "");
    expect(visible).not.toMatch(/beta/i);
    expect(visible).not.toMatch(/ln\(|±|1\.96/);
    expect(container.querySelector("thead")?.textContent).toContain("Sensitivity");
  });

  it("draws one dot per chart row and none for the market, on one shared scale", () => {
    const { container } = render(<EnergyPanel report={report()} />);
    const rows = Array.from(container.querySelectorAll('[data-model="long"] tbody tr'));
    const market = rows[0];
    expect(market?.querySelectorAll("circle.en-dot")).toHaveLength(0);
    expect(market?.querySelector(".en-control")?.textContent).toBe("controlled for");
    for (const tr of rows.slice(1)) {
      expect(tr.querySelectorAll("circle.en-dot")).toHaveLength(1);
      expect(tr.querySelectorAll("line.zero")).toHaveLength(1);
      expect(tr.querySelector("svg")?.getAttribute("aria-hidden")).toBe("true");
    }
    const gridX = (tr: Element | undefined) =>
      Array.from(tr?.querySelectorAll("line.grid, line.zero") ?? []).map((l) => l.getAttribute("x1"));
    expect(gridX(rows[1])).toEqual(gridX(rows[3]));
  });

  it("takes the line as the sensitivity ± 1.96 standard errors", () => {
    const w = whisker({ beta: 0.4, se: 0.05 });
    expect(w?.low).toBeCloseTo(0.4 - 1.96 * 0.05, 10);
    expect(w?.high).toBeCloseTo(0.4 + 1.96 * 0.05, 10);
    expect(whisker({ beta: 0.4, se: null as unknown as number })).toBeNull();
  });

  it("gives a VIF the caution style only above 5", () => {
    expect(VIF_WARN).toBe(5);
    expect(overlaps({ vif: 5 })).toBe(false);
    expect(overlaps({ vif: 5.01 })).toBe(true);
    const r = report((s) => {
      const rows = s.long_model?.rows ?? [];
      for (const row of rows) row.vif = 1.5;
      if (rows[1]) rows[1].vif = 7.34;
    });
    const { container } = render(<EnergyPanel report={r} />);
    const warn = Array.from(container.querySelectorAll('[data-model="long"] .en-vif.warn'));
    expect(warn.map((b) => b.textContent)).toEqual(["7.34"]);
    expect(warn[0]?.closest("tr")?.querySelector(".en-label")?.textContent).toBe("Oil");
  });

  it("names the leg that limits the window", () => {
    const r = report((s) => {
      if (s.carbon_model) s.carbon_model.window_limited_by = "KRBN";
    });
    const { container } = render(<EnergyPanel report={r} />);
    expect(container.querySelector('[data-model="carbon"] .en-limit')?.textContent).toContain("KRBN");
    expect(container.querySelector('[data-model="long"] .en-limit')).toBeNull();
    const how = container.querySelector("details.how")?.textContent ?? "";
    expect(how).toContain("the window starts when KRBN begins");
  });

  it("shows the note when an older cached copy of Brent or Henry Hub was used", () => {
    const r = report((s) => {
      s.fred_note = "Brent: used the copy of 2026-11-18";
    });
    const { container } = render(<EnergyPanel report={r} />);
    expect(container.querySelector(".en-fred-note")?.textContent).toBe("Brent: used the copy of 2026-11-18");
    expect(render(<EnergyPanel report={report()} />).container.querySelector(".en-fred-note")).toBeNull();
  });

  it("hides the carbon model and says why when it has too little data", () => {
    const r = report((s) => {
      s.carbon_model = null;
      s.carbon_note = "The carbon model is hidden: this window holds only 300 trading days of carbon data, and at least 2 years are needed.";
    });
    const { container } = render(<EnergyPanel report={r} />);
    expect(container.querySelectorAll(".en-model")).toHaveLength(1);
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
