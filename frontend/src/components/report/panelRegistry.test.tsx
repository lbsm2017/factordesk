import { render } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { cloneReport } from "../../test/fixture";
import { SECTION_FIELDS, withSection } from "../../test/sectionFixtures";
import { orderedPanels, PANELS } from "./panelRegistry";
import type { PanelEntry } from "./panelRegistry";
import { ReportView } from "./ReportView";

/** Panel order of the schema v3 contract (SC4). */
const ORDER = [
  "header",
  "notice",
  "equation",
  "kpis",
  "price",
  "performance",
  "exposures",
  "lead_lag",
  "shrunk",
  "fragility",
  "returns",
  "risk",
  "residual_alpha",
  "rolling",
  "kalman",
  "data",
  "regression_detail",
  "colophon",
];

/** Element id each optional section's panel uses, and the core panel it follows. */
const SECTION_PANELS = {
  performance: { id: "performance", after: "price" },
  lead_lag: { id: "lead-lag", after: "exposures" },
  shrunk_betas: { id: "shrunk", after: "lead-lag" },
  fragility: { id: "fragility", after: "shrunk" },
  residual: { id: "residual", after: "risk" },
  kalman_betas: { id: "kalman", after: "rolling" },
} as const;

function ids(container: HTMLElement): string[] {
  return Array.from(container.querySelectorAll("main > [id]")).map((el) => el.id);
}

describe("panel registry", () => {
  it("orders the panels as the contract fixes them", () => {
    expect(orderedPanels().map((p) => p.name)).toEqual(ORDER);
    expect(orderedPanels().map((p) => p.position)).toEqual(
      [...PANELS].map((p) => p.position).sort((a, b) => a - b),
    );
  });

  it("refuses a name or a position used twice", () => {
    const first = PANELS[0] as PanelEntry;
    expect(() => orderedPanels([...PANELS, { ...first, position: 9999 }])).toThrow(/name/);
    expect(() => orderedPanels([...PANELS, { ...first, name: "other" }])).toThrow(/position/);
  });

  it("draws no optional panel while the sections are null", () => {
    const { container } = render(
      <ReportView report={cloneReport()} downloadHref="#" win={null} onWinChange={vi.fn()} />,
    );
    for (const { id } of Object.values(SECTION_PANELS)) {
      expect(container.querySelector(`#${id}`)).toBeNull();
    }
  });

  it("draws each present section at its place, with the empty state of a placeholder", () => {
    let report = cloneReport();
    for (const field of SECTION_FIELDS) report = withSection(report, field);
    const { container } = render(<ReportView report={report} downloadHref="#" win={null} onWinChange={vi.fn()} />);
    const order = ids(container);
    for (const field of SECTION_FIELDS) {
      const { id, after } = SECTION_PANELS[field];
      expect(order.indexOf(id)).toBe(order.indexOf(after) + 1);
      // A feature with a populated fixture (residual) has no placeholder state to check.
      if (field === "residual") continue;
      const panel = container.querySelector(`#${id}`);
      // A feature that has filled its fixture in no longer shows the placeholder empty state.
      const value = report[field] as unknown;
      const items = (Array.isArray(value) ? value : [value]) as { reason?: string | null }[];
      if (items.some((item) => item.reason?.startsWith("Placeholder (schema v3 contract)"))) {
        expect(panel?.querySelector(".empty-what")?.textContent).toMatch(/^Placeholder \(schema v3 contract\)/);
      } else {
        expect(panel).not.toBeNull();
      }
    }
  });
});
