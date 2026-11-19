import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { FactorReport } from "../../../api/types";
import { cloneReport } from "../../../test/fixture";
import { withSection } from "../../../test/sectionFixtures";
import { alphaRange, AlphaStripPanel, droppedText, INTRO } from "./AlphaStripPanel";

type Section = NonNullable<FactorReport["alpha_strip"]>;

function report(edit?: (s: Section) => void): FactorReport {
  const r = withSection(cloneReport(), "alpha_strip");
  if (edit && r.alpha_strip) edit(r.alpha_strip);
  return r;
}

describe("AlphaStripPanel", () => {
  it("renders nothing while the section is absent", () => {
    const { container } = render(<AlphaStripPanel report={cloneReport()} />);
    expect(container.innerHTML).toBe("");
  });

  it("shows four rows in the fixed order with alpha, t and adjusted R², and a chart column", () => {
    const r = report();
    render(<AlphaStripPanel report={r} />);
    const table = screen.getByRole("table");
    const heads = within(table).getAllByRole("columnheader").map((h) => h.textContent);
    expect(heads).toEqual(["Model", "Alpha a year", "Chart: alpha and approximate 95% range", "t", "Adjusted R²"]);
    const rows = within(table).getAllByRole("row").slice(1);
    expect(rows.map((tr) => within(tr).getByRole("rowheader").textContent)).toEqual(["CAPM", "FF3", "FF5", "FF6"]);
    for (const tr of rows) expect(within(tr).getAllByRole("cell")).toHaveLength(4);
  });

  it("keeps plain R² out of the table and in the fold, with the one-line intro", () => {
    const r = report();
    const { container } = render(<AlphaStripPanel report={r} />);
    expect(Array.from(container.querySelectorAll("th")).map((h) => h.textContent)).not.toContain("R²");
    expect(container.querySelector(".reading")?.textContent).toBe(INTRO);
    const how = container.querySelector("details.how")?.textContent ?? "";
    for (const row of r.alpha_strip?.rows ?? []) expect(how).toContain(`${row.label} ${row.r2.toFixed(3)}`);
  });

  it("draws one dot per row on one shared scale with a zero line, and names each row for screen readers", () => {
    const { container } = render(<AlphaStripPanel report={report()} />);
    const rows = Array.from(container.querySelectorAll("tbody tr"));
    for (const tr of rows) {
      expect(tr.querySelectorAll("circle.as-dot")).toHaveLength(1);
      expect(tr.querySelectorAll("line.zero")).toHaveLength(1);
      expect(tr.querySelector("svg")?.getAttribute("aria-hidden")).toBe("true");
      expect(tr.querySelector(".vh")?.textContent).toMatch(/^(CAPM|FF3|FF5|FF6): alpha [+−]?[0-9.]+% a year, approximate 95% range/);
    }
    const gridX = (tr: Element) => Array.from(tr.querySelectorAll("line.grid, line.zero")).map((l) => l.getAttribute("x1"));
    expect(gridX(rows[0] as Element)).toEqual(gridX(rows[3] as Element));
    expect(container.querySelector("tfoot")?.getAttribute("aria-hidden")).toBe("true");
  });

  it("takes the approximate range from the t-statistic: alpha ± 1.96 · |alpha / t|", () => {
    const row = { model: "capm", label: "CAPM", factors: ["Mkt-RF"], alpha_annual: 0.04, alpha_t: 2, r2: 0.5, adj_r2: 0.5 } as Parameters<typeof alphaRange>[0];
    const range = alphaRange(row);
    expect(range?.low).toBeCloseTo(0.04 - 1.96 * 0.02, 10);
    expect(range?.high).toBeCloseTo(0.04 + 1.96 * 0.02, 10);
    expect(alphaRange({ ...row, alpha_t: 0 })).toBeNull();
    expect(alphaRange({ ...row, alpha_t: null as unknown as number })).toBeNull();
  });

  it("ranks and highlights no model", () => {
    const { container } = render(<AlphaStripPanel report={report()} />);
    const rows = Array.from(container.querySelectorAll("tbody tr"));
    expect(rows).toHaveLength(4);
    for (const tr of rows) {
      expect(tr.getAttribute("class")).toBeNull();
      expect(tr.getAttribute("aria-current")).toBeNull();
      for (const cell of Array.from(tr.querySelectorAll("td"))) expect(["num", "as-plot"]).toContain(cell.className);
    }
    expect(container.querySelector("strong, mark, .best, .num-pos, .num-neg")).toBeNull();
    expect(container.textContent).not.toMatch(/\bbest\b|\bwinner\b|\bpreferred\b/i);
  });

  it("keeps the E9a caption visible and puts the model note and the dropped-row count in the fold", () => {
    const r = report((s) => {
      s.n_dropped = 3;
    });
    const { container } = render(<AlphaStripPanel report={r} />);
    expect(container.querySelector(".foot > p")?.textContent).toBe(
      "A higher R² does not make a model more correct. Alpha depends on the model.",
    );
    expect(container.querySelector("details.how")?.textContent).toContain(r.alpha_strip?.model_note ?? "missing");
    expect(container.querySelector("details.how")?.textContent).toContain(droppedText(3));
    expect(container.querySelector(".foot > p")?.textContent).not.toContain(droppedText(3));
    expect(container.querySelector("p.as-note")).toBeNull();
    expect(droppedText(0)).toBe("No rows of the sample were left out.");
  });

  it("shows the reason when the strip could not be computed", () => {
    const r = report((s) => {
      s.status = "failed";
      s.reason = "The alpha strip could not be computed: singular design.";
      s.rows = [];
    });
    render(<AlphaStripPanel report={r} />);
    expect(screen.getByText(/singular design/).textContent).toContain("singular design");
    expect(screen.queryByRole("table")).toBeNull();
  });
});
