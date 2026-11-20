import { render, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { cloneReport } from "../../test/fixture";
import { SECTION_FIELDS, withSection } from "../../test/sectionFixtures";
import { orderedPanels, PANELS } from "./panelRegistry";
import type { PanelEntry } from "./panelRegistry";
import { NAV_ITEMS } from "../shell/SectionNav";
import { ReportView } from "./ReportView";

/** Panel order of the schema v3 contract (SC4), without `equation` and `kpis` (dashboard v2, DV1). */
const ORDER = [
  "header",
  "summary",
  "price",
  "performance",
  "tail_risk",
  "exposures",
  "alpha_strip",
  "world_beta",
  "macro",
  "energy",
  "returns",
  "risk",
  "rolling",
  "residual_alpha",
  "kalman",
  "shrunk",
  "lead_lag",
  "fragility",
  "data",
  "regression_detail",
  "colophon",
];

/** Element id each optional section's panel uses, and the core panel it follows. */
const SECTION_PANELS = {
  performance: { id: "performance", after: "price" },
  tail_risk: { id: "tail-risk", after: "performance" },
  lead_lag: { id: "lead-lag", after: "shrunk" },
  shrunk_betas: { id: "shrunk", after: "kalman" },
  fragility: { id: "fragility", after: "lead-lag" },
  world_beta: { id: "world-beta", after: "alpha-strip" },
  alpha_strip: { id: "alpha-strip", after: "exposures" },
  macro: { id: "macro", after: "world-beta" },
  energy: { id: "energy", after: "macro" },
  residual: { id: "residual", after: "rolling" },
  kalman_betas: { id: "kalman", after: "residual" },
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

  it("draws the panels in the same order as the sidebar items", () => {
    const registryName = (navId: string) => (navId === "residual" ? "residual_alpha" : navId.replace(/-/g, "_"));
    const names = orderedPanels().map((p) => p.name);
    const navNames = NAV_ITEMS.map((item) => registryName(item.id));
    for (const n of navNames) expect(names, n).toContain(n);
    expect(names.filter((n) => navNames.includes(n))).toEqual(navNames);
  });

  it("no longer registers the equation or the KPI strip (owner, dashboard v2)", () => {
    const names = PANELS.map((p) => p.name);
    expect(names).not.toContain("equation");
    expect(names).not.toContain("kpis");
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

  it("shows an outcome sentence under the title of every panel it covers (DV4.9)", async () => {
    let report = cloneReport();
    for (const field of SECTION_FIELDS) report = withSection(report, field);
    const { container } = render(<ReportView report={report} downloadHref="#" win={null} onWinChange={vi.fn()} />);
    await waitFor(() => expect(container.querySelector("#world-beta > p.q.outcome")).not.toBeNull(), { timeout: 12_000 });
    await waitFor(() => expect(container.querySelector("#performance > p.q.outcome")).not.toBeNull(), { timeout: 12_000 });
    await waitFor(() => expect(container.querySelector("#regression-detail > p.q.outcome")).not.toBeNull(), { timeout: 12_000 });
    for (const id of ["price", "performance", "exposures", "world-beta", "returns", "risk", "rolling", "data", "regression-detail"]) {
      const line = container.querySelector(`#${id} > p.q.outcome`);
      expect(line, id).not.toBeNull();
      expect(line?.textContent?.length, id).toBeGreaterThan(30);
    }
  }, 30_000);

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
