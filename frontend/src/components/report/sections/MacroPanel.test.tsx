import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { FactorReport } from "../../../api/types";
import { cloneReport } from "../../../test/fixture";
import { withSection } from "../../../test/sectionFixtures";
import { INTRO, MacroPanel, overlaps, VIF_WARN, whisker } from "./MacroPanel";

type Section = NonNullable<FactorReport["macro"]>;

function report(edit?: (s: Section) => void): FactorReport {
  const r = withSection(cloneReport(), "macro");
  if (edit && r.macro) edit(r.macro);
  return r;
}

describe("MacroPanel", () => {
  it("renders nothing while the section is absent", () => {
    const { container } = render(<MacroPanel report={cloneReport()} />);
    expect(container.innerHTML).toBe("");
  });

  it("shows one row per factor with its plain label, beta and t, and a chart column", () => {
    render(<MacroPanel report={report()} />);
    const table = screen.getByRole("table");
    const heads = within(table).getAllByRole("columnheader").map((h) => h.textContent);
    expect(heads).toEqual(["Factor", "Beta", "Chart: beta and approximate 95% range", "t", "Overlap with the other factors"]);
    const rows = within(table).getAllByRole("row").slice(1);
    expect(rows.map((tr) => within(tr).getByRole("rowheader").querySelector(".mc-label")?.textContent)).toEqual([
      "Market",
      "Rates",
      "Credit",
      "Commodities",
      "Inflation",
      "US dollar",
    ]);
    for (const tr of rows) expect(within(tr).getAllByRole("cell")).toHaveLength(4);
  });

  it("labels DEF as not duration-matched and INFL as a breakeven proxy, in the rows", () => {
    const { container } = render(<MacroPanel report={report()} />);
    const notes = Array.from(container.querySelectorAll("tbody .mc-note")).map((n) => n.textContent);
    expect(notes).toContain("credit minus rates, not duration-matched");
    expect(notes).toContain("breakeven proxy");
  });

  it("draws one dot per row and a zero line on one shared scale, and names each row for screen readers", () => {
    const { container } = render(<MacroPanel report={report()} />);
    const rows = Array.from(container.querySelectorAll("tbody tr"));
    expect(rows).toHaveLength(6);
    for (const tr of rows) {
      expect(tr.querySelectorAll("circle.mc-dot")).toHaveLength(1);
      expect(tr.querySelectorAll("line.zero")).toHaveLength(1);
      expect(tr.querySelector("svg")?.getAttribute("aria-hidden")).toBe("true");
      expect(tr.querySelector(".vh")?.textContent).toMatch(/: beta [+−]?[0-9.]+, approximate 95% range/);
    }
    const gridX = (tr: Element) => Array.from(tr.querySelectorAll("line.grid, line.zero")).map((l) => l.getAttribute("x1"));
    expect(gridX(rows[0] as Element)).toEqual(gridX(rows[5] as Element));
  });

  it("takes the whisker as beta ± 1.96 · SE", () => {
    const w = whisker({ beta: 0.4, se: 0.05 });
    expect(w?.low).toBeCloseTo(0.4 - 1.96 * 0.05, 10);
    expect(w?.high).toBeCloseTo(0.4 + 1.96 * 0.05, 10);
    expect(whisker({ beta: 0.4, se: null as unknown as number })).toBeNull();
  });

  it("shows a VIF badge only when the VIF is above 5", () => {
    expect(VIF_WARN).toBe(5);
    expect(overlaps({ vif: 5 })).toBe(false);
    expect(overlaps({ vif: 5.01 })).toBe(true);
    const r = report((s) => {
      for (const row of s.rows) row.vif = 1.5;
      (s.rows[1] as Section["rows"][number]).vif = 7.34;
    });
    const { container } = render(<MacroPanel report={r} />);
    const badges = Array.from(container.querySelectorAll(".mc-vif"));
    expect(badges.map((b) => b.textContent)).toEqual(["VIF 7.3"]);
    expect(badges[0]?.closest("tr")?.querySelector(".mc-label")?.textContent).toBe("Rates");
    const clean = render(
      <MacroPanel
        report={report((s) => {
          for (const row of s.rows) row.vif = 2;
        })}
      />,
    );
    expect(clean.container.querySelector(".mc-vif")).toBeNull();
  });

  it("keeps the fixed model note visible and the details in the fold", () => {
    const r = report();
    const { container } = render(<MacroPanel report={r} />);
    expect(container.querySelector(".foot > p")?.textContent).toBe(
      "Separate regression. Raw betas: correlated factors share explanatory power. Not the headline alpha.",
    );
    expect(container.querySelector(".reading")?.textContent).toBe(INTRO);
    const how = container.querySelector("details.how")?.textContent ?? "";
    expect(how).toContain("Window used:");
    expect(how).toContain("Correlations of the factors:");
    expect(how).toContain("Rates and Credit");
    expect(how).toContain("R²");
    expect(how).toContain("IEF minus RF");
    expect(how).toContain("Funds start:");
    expect(container.querySelector("table")?.textContent ?? "").not.toContain("Correlations");
  });

  it("names the dollar against the euro and the exchange rate in the euro view", () => {
    const r = report((s) => {
      s.model_note = "Separate regression, in euros. Raw betas: correlated factors share explanatory power. Not the headline alpha.";
      s.legs = [...s.legs.filter((l) => l.ticker !== "DTWEXBGS"), { ticker: "USD/EUR", role: "USD = return of the US dollar measured in euros", first_date: "1999-01-04" }];
      s.rows = s.rows.map((row) => (row.code === "usd" ? { ...row, label: "US dollar against the euro" } : row));
    });
    const { container } = render(<MacroPanel report={r} />);
    expect(container.textContent).toContain("US dollar against the euro");
    const how = container.querySelector("details.how")?.textContent ?? "";
    expect(how).toContain("in euros");
    expect(how).toContain("the exchange rate has no value there");
    expect(how).not.toContain("the dollar index has no value there");
  });

  it("says the dollar index is unavailable and shows no dollar row", () => {
    const r = report((s) => {
      s.usd_included = false;
      s.usd_note = "dollar index unavailable";
      s.usd_lag_note = null;
      s.rows = s.rows.filter((row) => row.code !== "usd");
      s.correlation_codes = s.correlation_codes.filter((c) => c !== "usd");
      s.correlation = s.correlation.slice(0, 5).map((row) => row.slice(0, 5));
    });
    const { container } = render(<MacroPanel report={r} />);
    expect(container.querySelectorAll("tbody tr")).toHaveLength(5);
    expect(container.querySelector(".reading")?.textContent).toContain("dollar index unavailable");
    expect(container.textContent).not.toContain("US dollar");
  });

  it("shows the reason when the section could not be computed", () => {
    const r = report((s) => {
      s.status = "insufficient_data";
      s.reason = "The macro regression needs more data: only 80 rows.";
      s.rows = [];
      s.correlation = [];
      s.correlation_codes = [];
    });
    render(<MacroPanel report={r} />);
    expect(screen.getByText(/needs more data/).textContent).toContain("only 80 rows");
    expect(screen.queryByRole("table")).toBeNull();
  });
});

describe("MacroPanel with small betas", () => {
  it("labels distinct axis ticks and keeps two significant digits", () => {
    const r = report((s) => {
      for (const row of s.rows) {
        row.beta = row.beta * 0.001;
        row.se = row.se * 0.001;
      }
    });
    const { container } = render(<MacroPanel report={r} />);
    const texts = Array.from(container.querySelectorAll(".mc-axis .axis span, tfoot .axis span")).map((n) => n.textContent ?? "");
    expect(texts.length).toBeGreaterThan(2);
    expect(new Set(texts).size).toBe(texts.length);
    const betas = Array.from(container.querySelectorAll("tbody td.num:nth-child(2)")).map((n) => n.textContent ?? "");
    for (const b of betas) expect(b).not.toMatch(/^[+−]?0\.00$/);
  });
});
