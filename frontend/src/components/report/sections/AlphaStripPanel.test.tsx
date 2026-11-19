import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { FactorReport } from "../../../api/types";
import { cloneReport } from "../../../test/fixture";
import { withSection } from "../../../test/sectionFixtures";
import { AlphaStripPanel, droppedText } from "./AlphaStripPanel";

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

  it("shows four rows in the fixed order with alpha, t, R² and adjusted R²", () => {
    const r = report();
    render(<AlphaStripPanel report={r} />);
    const table = screen.getByRole("table");
    const heads = within(table).getAllByRole("columnheader").map((h) => h.textContent);
    expect(heads).toEqual(["Model", "Alpha a year", "t", "R²", "Adjusted R²"]);
    const rows = within(table).getAllByRole("row").slice(1);
    expect(rows.map((tr) => within(tr).getByRole("rowheader").textContent)).toEqual(["CAPM", "FF3", "FF5", "FF6"]);
    for (const tr of rows) expect(within(tr).getAllByRole("cell")).toHaveLength(4);
  });

  it("ranks and highlights no model", () => {
    const { container } = render(<AlphaStripPanel report={report()} />);
    const rows = Array.from(container.querySelectorAll("tbody tr"));
    expect(rows).toHaveLength(4);
    for (const tr of rows) {
      expect(tr.getAttribute("class")).toBeNull();
      expect(tr.getAttribute("aria-current")).toBeNull();
      for (const cell of Array.from(tr.querySelectorAll("td"))) expect(cell.className).toBe("num");
    }
    expect(container.querySelector("strong, mark, .best, .num-pos, .num-neg")).toBeNull();
    expect(container.textContent).not.toMatch(/\bbest\b|\bwinner\b|\bpreferred\b/i);
  });

  it("carries the E9a caption, the model note and the dropped-row count", () => {
    const r = report((s) => {
      s.n_dropped = 3;
    });
    const { container } = render(<AlphaStripPanel report={r} />);
    expect(container.querySelector(".foot > p")?.textContent).toBe(
      "A higher R² does not make a model more correct. Alpha depends on the model.",
    );
    expect(container.textContent).toContain(r.alpha_strip?.model_note ?? "missing");
    expect(container.textContent).toContain(droppedText(3));
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
