import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { FactorReport } from "../../../api/types";
import { cloneReport } from "../../../test/fixture";
import { withSection } from "../../../test/sectionFixtures";
import { WorldBetaBody } from "./WorldBetaBody";
import { WorldBetaPanel } from "./WorldBetaPanel";
import { compareFits, europeOk } from "./worldBetaModel";

const state = vi.hoisted(() => ({ stats: false }));
vi.mock("../../../state/stats", () => ({ useShowStats: () => state.stats }));

function reportWith(edit?: (s: NonNullable<FactorReport["world_beta"]>) => void): FactorReport {
  const report = withSection(cloneReport(), "world_beta");
  if (edit && report.world_beta) edit(report.world_beta);
  return report;
}

function setEurope(s: NonNullable<FactorReport["world_beta"]>, edit: (e: NonNullable<typeof s.europe>) => void) {
  if (!s.europe) throw new Error("the fixture has no Europe block");
  edit(s.europe);
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
    expect(container.querySelector(".q")?.textContent).toBe(
      "Against world stocks, SPY's beta was 0.93 over 8 Aug 2024 to 30 Sep 2026 (540 days), about the same as its beta against the US market on the same days (1.00).",
    );
    expect(container.querySelector(".pm")?.textContent).toBe("Quick estimate, 540 days, one-factor");
  });

  it("counts the days of the fit, not the analysis-wide sample, in the aside and the rows", () => {
    const report = reportWith((s) => {
      s.n_sample = 8474;
      s.sample.n = 4656;
    });
    const { container } = render(<WorldBetaBody report={report} />);
    expect(container.querySelector(".pm")?.textContent).toBe("Quick estimate, 4,656 days, one-factor");
    expect(cells(container, "acwi")[2]).toBe("4,656");
    expect(cells(container, "us")[2]).toBe("4,656");
    expect(container.textContent).not.toContain("8,474");
  });

  it("labels the US market rows one-factor and explains the difference from the summary in a title", () => {
    const { container } = render(<WorldBetaBody report={reportWith()} />);
    const head = container.querySelector("#world-beta-us th");
    expect(head?.textContent).toBe("US market, one-factor, same days");
    expect(head?.getAttribute("title")).toMatch(/five-factor market beta/);
    const heads = Array.from(container.querySelectorAll("tbody th")).map((h) => h.textContent);
    expect(heads.join(" ")).not.toContain("US market beta");
  });

  it("says lower or higher when the intervals are apart", () => {
    const report = reportWith((s) => {
      if (s.world) Object.assign(s.world, { beta: 0.7, ci_low: 0.6, ci_high: 0.8 });
    });
    const { container } = render(<WorldBetaBody report={report} />);
    expect(container.querySelector(".q")?.textContent).toContain(", lower than its beta against the US market on the same days (1.00).");
  });

  it("never claims a difference from overlapping intervals, even when the category says so", () => {
    const report = reportWith((s) => {
      s.comparison = "higher";
    });
    const { container } = render(<WorldBetaBody report={report} />);
    expect(container.querySelector(".q")?.textContent).toContain(", about the same as its beta against the US market");
  });

  it("with statistics off shows Against, chart, Beta and Days only, on three rows with Europe in the middle", () => {
    const { container } = render(<WorldBetaBody report={reportWith()} />);
    expect(heads(container)).toEqual(["Against", "Chart", "Beta", "Days"]);
    expect(cells(container, "acwi")).toEqual(["ACWI", "+0.93", "540"]);
    expect(cells(container, "us")).toEqual(["US market, one-factor, same days", "+1.00", "540"]);
    expect(cells(container, "europe")).toEqual(["Europe IEUR, MSCI Europe stand-in", "+0.80", "540"]);
    expect(Array.from(container.querySelectorAll("tbody tr")).map((r) => r.id)).toEqual([
      "world-beta-acwi",
      "world-beta-europe",
      "world-beta-us",
    ]);
    expect(container.querySelectorAll(".reading")).toHaveLength(1);
    expect(container.querySelector(".reading")?.textContent).toMatch(/^Lower against Europe/);
  });

  it("with statistics on adds the 95% interval and R squared columns", () => {
    state.stats = true;
    const { container } = render(<WorldBetaBody report={reportWith()} />);
    expect(heads(container)).toEqual(["Against", "Chart", "Beta", "95% interval", "R²", "Days"]);
    expect(cells(container, "acwi")).toEqual(["ACWI", "+0.93", "0.85 to 1.01", "0.81", "540"]);
    expect(cells(container, "us")).toEqual(["US market, one-factor, same days", "+1.00", "0.96 to 1.04", "0.97", "540"]);
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

  it("shows the Europe row on the same axis with its interval and R squared when statistics are on", () => {
    state.stats = true;
    const { container } = render(<WorldBetaBody report={reportWith()} />);
    expect(cells(container, "europe")).toEqual(["Europe IEUR, MSCI Europe stand-in", "+0.80", "0.72 to 0.88", "0.64", "540"]);
    expect(container.querySelector("details.how")?.textContent).toContain("IEUR");
  });

  it("adds the US market on the Europe days as its own row when its fit differs from the ACWI days", () => {
    const report = reportWith((s) => setEurope(s, (e) => {
      if (e.us_market) Object.assign(e.us_market, { beta: 0.98, ci_low: 0.93, ci_high: 1.03 });
    }));
    const { container } = render(<WorldBetaBody report={report} />);
    expect(Array.from(container.querySelectorAll("tbody tr")).map((r) => r.id)).toEqual([
      "world-beta-acwi",
      "world-beta-europe",
      "world-beta-us",
      "world-beta-us-europe",
    ]);
    expect(cells(container, "us-europe")).toEqual(["US market, one-factor, same days as Europe", "+0.98", "540"]);
  });

  it("leaves the Europe row out when the block is absent, null or not ok", () => {
    const edits: Array<(s: NonNullable<FactorReport["world_beta"]>) => void> = [
      (s) => {
        s.europe = null;
      },
      (s) => setEurope(s, (e) => {
        e.status = "failed";
        e.benchmark = null;
        e.us_market = null;
      }),
    ];
    for (const edit of edits) {
      const { container, unmount } = render(<WorldBetaBody report={reportWith(edit)} />);
      expect(container.querySelector("#world-beta-europe")).toBeNull();
      expect(container.querySelectorAll("tbody tr")).toHaveLength(2);
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
      s.europe = null;
      s.status = "insufficient_data";
      s.reason = "Too few days overlap with the world fund: 90, at least 252 needed.";
    });
    const a = render(<WorldBetaBody report={short} />);
    expect(screen.getByText("Too few days overlap with the world fund: 90, at least 252 needed.")).not.toBeNull();
    expect(screen.getByText("Choose a longer range.")).not.toBeNull();
    expect(a.container.querySelector("table, .foot")).toBeNull();
    a.unmount();
    const failed = reportWith((s) => {
      s.europe = null;
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

  it("gives the Europe block only when it is ok and carries both fits", () => {
    const s = reportWith().world_beta;
    if (!s) throw new Error("no fixture");
    expect(europeOk(s)?.proxy).toBe("IEUR");
    expect(europeOk({ ...s, europe: null })).toBeNull();
    expect(europeOk({ ...s, europe: s.europe && { ...s.europe, status: "failed" } })).toBeNull();
  });
});
