import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { FactorReport } from "../../../api/types";
import { cloneReport } from "../../../test/fixture";
import { withSection } from "../../../test/sectionFixtures";
import { WorldBetaBody } from "./WorldBetaBody";
import { WorldBetaPanel } from "./WorldBetaPanel";
import { compareFits, europeRow, outcomeLine } from "./worldBetaModel";

const state = vi.hoisted(() => ({ stats: false }));
vi.mock("../../../state/stats", () => ({ useShowStats: () => state.stats }));

const EUROPE = {
  proxy: "IEUR",
  n_sample: 480,
  world: { beta: 0.71, se: 0.05, ci_low: 0.61, ci_high: 0.81, r2: 0.55, correlation: 0.74, alpha_annual: 0.01, alpha_t: 0.3 },
};

function reportWith(edit?: (s: NonNullable<FactorReport["world_beta"]>) => void): FactorReport {
  const report = withSection(cloneReport(), "world_beta");
  if (edit && report.world_beta) edit(report.world_beta);
  return report;
}

function withEurope(s: NonNullable<FactorReport["world_beta"]>) {
  (s as unknown as { europe: unknown }).europe = structuredClone(EUROPE);
}

function heads(container: HTMLElement): string[] {
  return Array.from(container.querySelectorAll("thead th")).map((h) => h.textContent ?? "");
}

/** Texts of a row's cells without the chart cell (the second one). */
function cells(container: HTMLElement, id: string): string[] {
  const row = container.querySelector<HTMLElement>(`#world-beta-${id}`);
  if (!row) throw new Error(`no row ${id}`);
  return Array.from(row.querySelectorAll("th, td"))
    .filter((_, i) => i !== 1)
    .map((c) => c.textContent ?? "");
}

beforeEach(() => {
  state.stats = false;
});

describe("WorldBetaPanel (lazy wrapper)", () => {
  it("renders nothing while the section is null", () => {
    const { container } = render(<WorldBetaPanel report={cloneReport()} />);
    expect(container.innerHTML).toBe("");
  });

  it("holds its place with the titled frame, then shows the body", async () => {
    const { container } = render(<WorldBetaPanel report={reportWith()} />);
    expect(container.querySelector("section#world-beta h2")?.textContent).toBe("World beta");
    expect(await screen.findByRole("table")).not.toBeNull();
    expect(container.querySelectorAll("section#world-beta")).toHaveLength(1);
  });
});

describe("WorldBetaBody", () => {
  it("states the comparison in one line and the quick-estimate aside", () => {
    const { container } = render(<WorldBetaBody report={reportWith()} />);
    expect(screen.getByRole("heading", { level: 2, name: "World beta" })).not.toBeNull();
    // the fixture's two intervals overlap, so the line is about the same whatever its category says
    expect(container.querySelector(".reading")?.textContent).toBe("About the same against the world as against the US market.");
    expect(container.querySelector(".pm")?.textContent).toBe("Quick estimate, 559 days, one-factor");
  });

  it("says lower or higher when the intervals are apart", () => {
    const report = reportWith((s) => {
      if (s.world) Object.assign(s.world, { beta: 0.7, ci_low: 0.6, ci_high: 0.8 });
    });
    const { container } = render(<WorldBetaBody report={report} />);
    expect(container.querySelector(".reading")?.textContent).toBe("Lower against the world than against the US market.");
  });

  it("never claims a difference from overlapping intervals, even when the category says so", () => {
    const report = reportWith((s) => {
      s.comparison = "higher";
    });
    const { container } = render(<WorldBetaBody report={report} />);
    expect(container.querySelector(".reading")?.textContent).toBe("About the same against the world as against the US market.");
  });

  it("with statistics off shows Against, chart, Beta and Days only, on two rows", () => {
    const { container } = render(<WorldBetaBody report={reportWith()} />);
    expect(heads(container)).toEqual(["Against", "Chart", "Beta", "Days"]);
    expect(cells(container, "acwi")).toEqual(["ACWI", "+0.93", "559"]);
    expect(cells(container, "us")).toEqual(["US market", "+1.00", "same"]);
    expect(container.querySelectorAll("tbody tr")).toHaveLength(2);
    expect(container.querySelector("#world-beta-europe")).toBeNull();
  });

  it("with statistics on adds the 95% interval and R squared columns", () => {
    state.stats = true;
    const { container } = render(<WorldBetaBody report={reportWith()} />);
    expect(heads(container)).toEqual(["Against", "Chart", "Beta", "95% interval", "R²", "Days"]);
    expect(cells(container, "acwi")).toEqual(["ACWI", "+0.93", "0.85 to 1.01", "0.81", "559"]);
    expect(cells(container, "us")).toEqual(["US market", "+1.00", "0.96 to 1.04", "0.97", "same"]);
  });

  it("draws every beta as a neutral ink dot with its interval on one shared axis, never green or red", () => {
    const { container } = render(<WorldBetaBody report={reportWith()} />);
    const rows = Array.from(container.querySelectorAll("tbody tr"));
    for (const r of rows) {
      expect(r.querySelectorAll("circle.wb-dot")).toHaveLength(1);
      expect(r.querySelectorAll("line.ci").length).toBeGreaterThanOrEqual(1);
      expect(r.querySelector(".num-pos, .num-neg, rect.pos, rect.neg")).toBeNull();
    }
    const gridX = (r: Element) => Array.from(r.querySelectorAll("line.grid, line.zero")).map((l) => l.getAttribute("x1"));
    expect(gridX(rows[0] as Element)).toEqual(gridX(rows[1] as Element));
    expect(container.querySelector("tr.axis-row")?.getAttribute("aria-hidden")).toBe("true");
  });

  it("adds the Europe row when the section has it, on the same axis", () => {
    state.stats = true;
    const { container } = render(<WorldBetaBody report={reportWith(withEurope)} />);
    expect(container.querySelectorAll("tbody tr")).toHaveLength(3);
    expect(cells(container, "europe")).toEqual(["Europe (IEUR)", "+0.71", "0.61 to 0.81", "0.55", "480"]);
    expect(container.querySelector("details.how")?.textContent).toContain("IEUR");
  });

  it("leaves the Europe row out when the block is absent, null or not ok", () => {
    for (const europe of [undefined, null, { status: "failed", reason: "x", proxy: "IEUR" }]) {
      const report = reportWith((s) => {
        (s as unknown as { europe: unknown }).europe = europe;
      });
      const { container, unmount } = render(<WorldBetaBody report={report} />);
      expect(container.querySelector("#world-beta-europe")).toBeNull();
      unmount();
    }
  });

  it("carries the quick-estimate footnote with the stand-in notes and the fold", () => {
    const { container } = render(<WorldBetaBody report={reportWith()} />);
    const foot = container.querySelector(".foot > p")?.textContent ?? "";
    expect(foot).toContain("A quick estimate.");
    expect(foot).toContain("stand-in for the MSCI ACWI index");
    expect(foot).toContain("ACWI data ends 30 Sep 2026.");
    const how = container.querySelector("details.how")?.textContent ?? "";
    expect(how).toContain("not a test of the difference");
    expect(how).toContain("Newey-West with 6 lags");
    expect(how).toContain("19 days of the analysed sample were left out");
  });

  it("shows the reason and the action when the status is not ok", () => {
    const short = reportWith((s) => {
      s.status = "insufficient_data";
      s.reason = "Too few days overlap with the world fund: 90, at least 252 needed.";
    });
    const a = render(<WorldBetaBody report={short} />);
    expect(screen.getByText("Too few days overlap with the world fund: 90, at least 252 needed.")).not.toBeNull();
    expect(screen.getByText("Choose a longer range.")).not.toBeNull();
    expect(a.container.querySelector("table, .foot")).toBeNull();
    a.unmount();
    const failed = reportWith((s) => {
      s.status = "failed";
      s.reason = "The world fund could not be fetched.";
    });
    render(<WorldBetaBody report={failed} />);
    expect(screen.getByText("Try again later.")).not.toBeNull();
  });

  it("renders nothing while the section is null", () => {
    const { container } = render(<WorldBetaBody report={cloneReport()} />);
    expect(container.innerHTML).toBe("");
  });

  it("names every row and its numbers for screen readers", () => {
    const { container } = render(<WorldBetaBody report={reportWith()} />);
    expect(container.querySelector("#world-beta-acwi .vh")?.textContent).toMatch(/^ACWI: beta \+0\.93, 95% interval 0\.85 to 1\.01/);
  });
});

describe("world beta model", () => {
  const fit = (beta: number, lo: number, hi: number) => ({ beta, se: 0, ci_low: lo, ci_high: hi, r2: 0.9, correlation: 0.9, alpha_annual: 0, alpha_t: 0 });

  it("says about the same whenever the intervals overlap, whatever the point estimates", () => {
    expect(compareFits(fit(1.2, 1.0, 1.4), fit(0.95, 0.85, 1.05))).toBe("about_the_same");
    expect(compareFits(fit(0.8, 0.7, 1.0), fit(1.2, 1.0, 1.4))).toBe("about_the_same");
  });

  it("says higher or lower only when the intervals are apart", () => {
    expect(compareFits(fit(1.3, 1.2, 1.4), fit(1.0, 0.9, 1.1))).toBe("higher");
    expect(compareFits(fit(0.7, 0.6, 0.8), fit(1.0, 0.9, 1.1))).toBe("lower");
  });

  it("uses the category when a fit is missing", () => {
    const s = reportWith().world_beta;
    if (!s) throw new Error("no fixture");
    expect(outcomeLine({ ...s, us_market: null, comparison: "lower" })).toBe("Lower against the world than against the US market.");
    expect(outcomeLine({ ...s, us_market: null, comparison: null })).toBeNull();
  });

  it("reads the Europe block in either shape", () => {
    const s = reportWith().world_beta;
    if (!s) throw new Error("no fixture");
    expect(europeRow(s)).toBeNull();
    const flat = { ...s, europe: { ...EUROPE.world, proxy: "IEUR", n_sample: 12 } } as unknown as typeof s;
    expect(europeRow(flat)?.days).toBe(12);
    const nested = { ...s, europe: EUROPE } as unknown as typeof s;
    expect(europeRow(nested)?.fit.beta).toBe(0.71);
  });
});
