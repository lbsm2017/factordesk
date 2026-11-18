import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { FactorReport, KalmanBetaSeries } from "../../../api/types";
import { cloneReport, mockReport } from "../../../test/fixture";
import { withSection } from "../../../test/sectionFixtures";
import {
  KalmanPanel,
  MAX_DRAWN_POINTS,
  buildKalmanModel,
  thinIndices,
} from "./KalmanPanel";

const MINUS = "−";

function withKalman(edit?: (s: KalmanBetaSeries) => void): FactorReport {
  const report = withSection(cloneReport(), "kalman_betas");
  if (edit && report.kalman_betas) edit(report.kalman_betas);
  return report;
}

function renderPanel(report: FactorReport) {
  return render(<KalmanPanel report={report} />);
}

function rowOf(container: HTMLElement, name: string): HTMLElement {
  return container.querySelector(`tr[data-factor="${name}"]`) as HTMLElement;
}

function cells(row: HTMLElement): string[] {
  return Array.from(row.querySelectorAll("td")).map((td) => td.textContent ?? "");
}

describe("KalmanPanel absent or not ok", () => {
  it("renders nothing while the section is null", () => {
    const { container } = renderPanel(mockReport);
    expect(container.firstChild).toBeNull();
  });

  it.each([
    ["insufficient_data", "Insufficient data: kalman_needs_504_rows"],
    ["failed", "Failed: singular_burn_in"],
  ] as const)("shows the reason as the empty state for status %s, with one next step and no numbers", (status, reason) => {
    const report = withKalman((s) => {
      s.status = status;
      s.reason = reason;
    });
    const { container } = renderPanel(report);
    expect(screen.getByText(reason)).toBeTruthy();
    expect(container.querySelector(".empty-do")?.textContent).toMatch(/earlier start date/);
    expect(container.querySelector("table")).toBeNull();
    expect(container.textContent).not.toMatch(/\d\.\d{3}/);
  });

  it("says warm-up when an ok section has no value yet", () => {
    const report = withKalman((s) => {
      for (const name of Object.keys(s.betas)) {
        s.betas[name] = s.betas[name]!.map(() => null);
        s.band_low[name] = s.band_low[name]!.map(() => null);
        s.band_high[name] = s.band_high[name]!.map(() => null);
      }
    });
    const { container } = renderPanel(report);
    expect(container.querySelector(".empty-what")?.textContent).toMatch(/warm-up/);
  });
});

describe("KalmanPanel numbers", () => {
  it("prints the latest beta, sd and band of every factor as in the fixture", () => {
    const { container } = renderPanel(withKalman());
    expect(cells(rowOf(container, "Mkt-RF")).slice(1)).toEqual(["+1.154", "0.0736", "1.010 to 1.298"]);
    expect(cells(rowOf(container, "SMB")).slice(1)).toEqual(["+0.722", "0.126", "0.475 to 0.969"]);
    expect(cells(rowOf(container, "HML")).slice(1)).toEqual(["" + MINUS + "0.329", "0.165", MINUS + "0.652 to " + MINUS + "0.006"]);
    expect(cells(rowOf(container, "RMW")).slice(1)[0]).toBe("+0.396");
    expect(cells(rowOf(container, "CMA")).slice(1)).toEqual(["+0.623", "0.226", "0.180 to 1.066"]);
    expect(container.textContent).not.toContain("-0.329");
  });

  it("lists the four vintages: rows, lambda, equivalent window, residual volatility, validity", () => {
    renderPanel(withKalman());
    const table = screen.getByRole("table", { name: "Yearly re-estimates of the drift rate" });
    const body = Array.from(table.querySelectorAll("tbody tr")).map((tr) =>
      Array.from(tr.children).map((c) => c.textContent ?? ""),
    );
    expect(body.map((r) => r[0])).toEqual(["504 rows", "756 rows", "1,008 rows", "1,260 rows"]);
    expect(body.map((r) => r[2])).toEqual(["2,052 days", "854 days", "580 days", "611 days"]);
    expect(body.map((r) => r[3])).toEqual(["18.4%", "18.4%", "18.7%", "19.0%"]);
    expect(body.map((r) => r[4])).toEqual(["2023-09-12", "2024-08-29", "2025-08-18", "2026-08-05"]);
    expect(body[0]?.[1]).toBe("9.5e-07");
    expect(body.every((r) => r[6] === "Within limits.")).toBe(true);
  });

  it("flags a lambda at the bound in words and shows the warning text in the folded part", () => {
    const report = withKalman((s) => {
      const v = s.vintages[2]!;
      v.lam_at_bound = "upper";
      v.lam = 0.01;
      s.vintages[1]!.lam_at_bound = "zero";
      s.vintages[1]!.lam = 0;
      s.vintages[1]!.w_eq = null;
      s.warnings = ["kalman_lambda_at_upper_bound"];
    });
    const { container } = renderPanel(report);
    const rows = container.querySelectorAll(".kalman-vt tbody tr");
    expect(rows[2]?.textContent).toMatch(/At the upper limit: the filter follows daily noise/);
    expect(rows[2]?.classList.contains("bound")).toBe(true);
    expect(rows[1]?.textContent).toMatch(/At zero: no drift detected/);
    expect(rows[1]?.textContent).toMatch(/All data so far/);
    const how = container.querySelector("details.how") as HTMLElement;
    expect(how.textContent).toMatch(/the estimate is not meaningful/);
  });

  it("puts the label texts of the report in the folded How this is computed part", () => {
    const report = withKalman();
    report.label_text = { ...report.label_text, "L-KF": "KF label text.", "L-KBAND": "KBAND label text." };
    const { container } = renderPanel(report);
    const how = container.querySelector("details.how") as HTMLElement;
    expect(how.querySelector("summary")?.textContent).toBe("How this is computed");
    expect(how.textContent).toContain("KF label text.");
    expect(how.textContent).toContain("KBAND label text.");
    expect(container.querySelector(".foot > p")?.textContent).not.toContain("KF label text.");
  });
});

describe("KalmanPanel chart", () => {
  it("draws from the first non-null value: warm-up rows leave no point and no line segment", () => {
    const s = withKalman().kalman_betas as KalmanBetaSeries;
    const firstStamp = s.betas["Mkt-RF"]!.findIndex((v) => v !== null);
    expect(firstStamp).toBe(503);
    const model = buildKalmanModel(withKalman(), s)!;
    expect(model.first).toBe(s.dates[503]);
    for (const row of model.rows) expect(row.total).toBe(s.dates.length - 503);
    const { container } = renderPanel(withKalman());
    const d = container.querySelector('[data-testid="kalman-chart-Mkt-RF"] path.rline')?.getAttribute("d") ?? "";
    expect(d.startsWith("M0.00 ")).toBe(true);
    expect(d).not.toMatch(/NaN|null/);
    expect(container.querySelector(".xl-wrap .xl")?.textContent).toMatch(/\d{4}/);
  });

  it("gives every row the same vertical span, centred on its own band", () => {
    const report = withKalman();
    const model = buildKalmanModel(report, report.kalman_betas as KalmanBetaSeries)!;
    const spans = model.rows.map((r) => r.hi - r.lo);
    for (const sp of spans) expect(sp).toBeCloseTo(spans[0]!, 9);
    for (const row of model.rows) {
      const s = report.kalman_betas as KalmanBetaSeries;
      const lows = s.band_low[row.name]!.filter((v): v is number => v !== null);
      const highs = s.band_high[row.name]!.filter((v): v is number => v !== null);
      expect(row.lo).toBeLessThan(Math.min(...lows));
      expect(row.hi).toBeGreaterThan(Math.max(...highs));
    }
  });

  it("uses the factor hues f1 to f5 in factor order", () => {
    const { container } = renderPanel(withKalman());
    ["Mkt-RF", "SMB", "HML", "RMW", "CMA"].forEach((name, i) => {
      const row = rowOf(container, name);
      expect(row.querySelector(`path.rline.c${i + 1}`)).toBeTruthy();
      expect(row.querySelector(`path.band.c${i + 1}`)).toBeTruthy();
    });
  });

  it("marks the yearly re-estimates with one line per vintage after the first", () => {
    const { container } = renderPanel(withKalman());
    expect(container.querySelectorAll('[data-testid="kalman-chart-SMB"] line.cutline')).toHaveLength(3);
  });
});

describe("thinning keeps spikes", () => {
  it("returns a short series whole", () => {
    expect(thinIndices([[1, 2, 3]])).toEqual([0, 1, 2]);
  });

  it("keeps a one-day spike and a one-day dip in a long series, and stays small", () => {
    const n = 8500;
    const beta = Array.from({ length: n }, (_, i) => 1 + 0.001 * Math.sin(i / 50));
    beta[4321] = 9;
    beta[6000] = -7;
    const low = beta.map((v) => v - 0.1);
    const high = beta.map((v) => v + 0.1);
    const keep = thinIndices([beta, low, high]);
    expect(keep).toContain(4321);
    expect(keep).toContain(6000);
    expect(keep[0]).toBe(0);
    expect(keep[keep.length - 1]).toBe(n - 1);
    expect(keep.length).toBeLessThan(MAX_DRAWN_POINTS * 1.5);
    expect([...keep].sort((a, b) => a - b)).toEqual(keep);
  });

  it("draws the spike in the path of a long series and keeps its number in the text", () => {
    const report = withKalman((s) => {
      const extra = 6000;
      const last = new Date(s.dates[s.dates.length - 1] + "T00:00:00Z");
      const dates = [...s.dates];
      const grow = <T,>(a: T[], fill: (i: number) => T) => [...a, ...Array.from({ length: extra }, (_, i) => fill(i))];
      for (let i = 1; i <= extra; i++) dates.push(new Date(last.getTime() + i * 86_400_000).toISOString().slice(0, 10));
      s.dates = dates;
      s.alpha = grow(s.alpha, () => 0);
      s.vintage_index = grow(s.vintage_index, () => 3);
      for (const name of Object.keys(s.betas)) {
        s.betas[name] = grow(s.betas[name]!, () => 1);
        s.band_low[name] = grow(s.band_low[name]!, () => 0.5);
        s.band_high[name] = grow(s.band_high[name]!, () => 1.5);
        s.ex_ante_betas[name] = grow(s.ex_ante_betas[name]!, () => 1);
      }
      const at = 1300 + 2500;
      s.betas["Mkt-RF"]![at] = 4;
      s.band_high["Mkt-RF"]![at] = 4.2;
    });
    const s = report.kalman_betas as KalmanBetaSeries;
    const model = buildKalmanModel(report, s)!;
    const row = model.rows[0]!;
    expect(row.name).toBe("Mkt-RF");
    expect(row.total).toBe(6797);
    expect(row.drawn).toBeLessThan(2000);
    const ys = [...row.line.matchAll(/[ML][\d.]+ ([\d.]+)/g)].map((m) => Number(m[1]));
    const spikeY = ((row.hi - 4) / (row.hi - row.lo)) * 100;
    expect(Math.min(...ys)).toBeCloseTo(spikeY, 1);
    expect(row.max).toBe(4);
    const { container } = renderPanel(report);
    expect(container.querySelector('[data-testid="kalman-chart-Mkt-RF"] path.rline')).toBeTruthy();
    expect(rowOf(container, "Mkt-RF").textContent).toContain("highest +4.000");
    expect(rowOf(container, "Mkt-RF").textContent).toContain("+1.154");
  });
});

describe("KalmanPanel accessibility", () => {
  it("names the section, its tables and every row, and hides the drawing and the axis", () => {
    const { container } = renderPanel(withKalman());
    const section = screen.getByRole("region", { name: "Kalman-filter betas" });
    expect(section.id).toBe("kalman");
    const main = within(section).getAllByRole("table")[0] as HTMLElement;
    expect(main.querySelector("caption")?.textContent).toMatch(/Kalman-filter beta per factor/);
    expect(within(main).getAllByRole("rowheader").map((h) => h.textContent)).toEqual(
      expect.arrayContaining([expect.stringContaining("Mkt-RF"), expect.stringContaining("CMA")]),
    );
    expect(within(main).getAllByRole("columnheader").map((h) => h.textContent)).toEqual([
      "Factor",
      "Chart",
      "Latest beta",
      "sd",
      "Band low to high",
    ]);
    for (const svg of container.querySelectorAll("svg.kalman-svg")) expect(svg.getAttribute("aria-hidden")).toBe("true");
    expect(container.querySelector("tfoot tr.axis-row")?.getAttribute("aria-hidden")).toBe("true");
    // The chart is also a table: each row carries its range as text.
    expect(rowOf(container, "Mkt-RF").querySelector(".vh")?.textContent).toMatch(
      /Mkt-RF Kalman beta from 12 Sep 2023 to 30 Sep 2026: lowest [+−]\d\.\d{3}, highest [+−]\d\.\d{3}/,
    );
  });

  it("keeps the fold reachable by keyboard and uses true minus signs only", () => {
    const { container } = renderPanel(withKalman());
    const summary = container.querySelector("details.how > summary") as HTMLElement;
    expect(summary.tabIndex).toBe(0);
    expect(container.textContent).not.toMatch(/-\d\.\d/);
    expect(container.textContent).toContain(MINUS + "0.329");
  });

  it("has no scroll region that would take a focus stop (the tables fit the page)", () => {
    const { container } = renderPanel(withKalman());
    expect(container.querySelectorAll("[tabindex]")).toHaveLength(0);
  });
});
