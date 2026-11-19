import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { pval, signed, tstat } from "../../format";
import { cloneReport, mockReport } from "../../test/fixture";
import { position } from "../charts/BarCell";
import { ExposuresPanel } from "./ExposuresPanel";
import { axisLabels, exposureModel, exposuresUnavailable, niceDomain } from "./exposureModel";

const report = mockReport;

function rowOf(container: HTMLElement, name: string): HTMLElement {
  const el = container.querySelector<HTMLElement>(`tr#beta-${name}`);
  if (!el) throw new Error(`no row for ${name}`);
  return el;
}

describe("niceDomain and axisLabels (ported from render_html.py)", () => {
  it("matches the static renderer", () => {
    expect(niceDomain(-0.141, 1.048, 5)).toEqual({ lo: -0.25, hi: 1.25, ticks: [-0.25, 0, 0.25, 0.5, 0.75, 1, 1.25] });
    expect(niceDomain(-0.3, 0.3, 5)).toEqual({ lo: -0.4, hi: 0.4, ticks: [-0.4, -0.2, 0, 0.2, 0.4] });
    expect(niceDomain(0, 0, 5).lo).toBeCloseTo(-0.6, 10);
  });

  it("labels zero as 0, others as signed with 2 decimals, and anchors the edges inward", () => {
    const labels = axisLabels(niceDomain(-0.3, 1.2, 5));
    expect(labels.map((l) => l.text)).toEqual(["−0.50", "0", "+0.50", "+1.00", "+1.50"]);
    expect(labels.map((l) => l.left)).toEqual([0, 25, 50, 75, 100]);
    expect(labels[0]?.className).toBe("edge-l");
    expect(labels[4]?.className).toBe("edge-r");
  });

  it("thins every second label on narrow screens (class alt) but keeps zero", () => {
    const labels = axisLabels({ lo: -0.25, hi: 1.25, ticks: [-0.25, 0, 0.25, 0.5, 0.75, 1, 1.25] });
    expect(labels).toHaveLength(7);
    const zero = labels.find((l) => l.value === 0);
    expect(zero?.className ?? "").not.toContain("alt");
    expect(labels.filter((l) => l.className.includes("alt")).length).toBe(4);
  });
});

describe("ExposuresPanel table", () => {
  it("carries every number in text columns", () => {
    const { container } = render(<ExposuresPanel report={report} />);
    const g = report.regression;
    const avg = new Map(report.average_beta.factors.map((a) => [a.name, a.mean]));
    expect(g.factors).toHaveLength(5);
    for (const f of g.factors) {
      const cells = within(rowOf(container, f.name)).getAllByRole("cell");
      // cells: plot (marks only), beta, t, significant, average
      expect(cells.slice(1).map((c) => c.textContent)).toEqual([
        signed(f.beta as number),
        tstat(f.z as number),
        f.tag === "reliable" ? "Yes" : "No",
        signed(avg.get(f.name) as number),
      ]);
    }
    const heads = screen.getAllByRole("columnheader").map((h) => h.textContent);
    expect(heads).toEqual(["Factor", "Chart", "Beta", "t", "SignificantSig.", "Avg 252d"]);
  });

  it("names every factor in plain words and the first factor Market", () => {
    const { container } = render(<ExposuresPanel report={report} />);
    expect(rowOf(container, "Mkt-RF").querySelector(".sub")?.textContent).toBe("Market");
    expect(rowOf(container, "RMW").querySelector(".sub")?.textContent).toBe("Profitability");
  });

  it("gives every plot cell a native title with beta, interval, t and adjusted p", () => {
    const { container } = render(<ExposuresPanel report={report} />);
    const f = report.regression.factors[0];
    if (!f) throw new Error("no factor");
    const title = rowOf(container, f.name).querySelector("svg.bar-svg > title")?.textContent;
    expect(title).toBe(
      `${f.name}: beta ${signed(f.beta as number)}, 95% interval ${signed(f.ci_low as number)} to ` +
        `${signed(f.ci_high as number)}, t ${tstat(f.z as number)}, adjusted p ${pval(f.p_adj_bh as number)}`,
    );
  });

  it("fades non-significant betas and says No in the Significant column", () => {
    const { container } = render(<ExposuresPanel report={report} />);
    const hml = rowOf(container, "HML");
    expect(hml.className).toBe("ns");
    expect(hml.querySelector("rect.faded")).not.toBeNull();
    expect(within(hml).getAllByRole("cell")[3]?.textContent).toBe("No");
    const mkt = rowOf(container, "Mkt-RF");
    expect(mkt.querySelector("rect.faded")).toBeNull();
    expect(within(mkt).getAllByRole("cell")[3]?.textContent).toBe("Yes");
  });

  it("draws every beta bar in neutral ink, never green or red, and bolds the Yes word", () => {
    const { container } = render(<ExposuresPanel report={report} />);
    expect(container.querySelector("rect.pos, rect.neg, rect.bar-pos, rect.bar-neg")).toBeNull();
    expect(container.querySelectorAll("tbody rect.ink").length).toBe(report.regression.factors.length);
    expect(container.querySelectorAll("td.num-pos, td.num-neg")).toHaveLength(0);
    expect(rowOf(container, "Mkt-RF").querySelector("td.sig.yes")?.textContent).toBe("Yes");
    expect(rowOf(container, "HML").querySelector("td.sig.yes")).toBeNull();
  });

  it("draws the bar 36% of the row, a 7 px diamond on the centre line, and a 3 px interval cap", () => {
    const { container } = render(<ExposuresPanel report={report} />);
    const row = rowOf(container, "SMB");
    expect(row.querySelector("rect.ink")?.getAttribute("height")).toBe("36%");
    const diamond = row.querySelector("svg.avgm");
    expect(diamond?.getAttribute("y")).toBe("50%");
    expect(diamond?.querySelector("path")?.getAttribute("d")).toBe("M0 -3.6 3.6 0 0 3.6-3.6 0z");
    // 7 percent of a 44 px row is 3.08 px; the caps run from 46.5% to 53.5%.
    const caps = Array.from(row.querySelectorAll("line.ci")).filter((l) => l.getAttribute("x1") === l.getAttribute("x2"));
    expect(caps).toHaveLength(2);
    expect(caps[0]?.getAttribute("y1")).toBe("46.5%");
    expect(caps[0]?.getAttribute("y2")).toBe("53.5%");
  });

  it("centres each diamond on the average rolling beta", () => {
    const { container } = render(<ExposuresPanel report={report} />);
    const model = exposureModel(report);
    const { lo, hi } = model.domain;
    for (const r of model.rows) {
      const x = rowOf(container, r.name).querySelector("svg.avgm")?.getAttribute("x");
      expect(x).toBe(`${position(r.average as number, lo, hi)}%`);
    }
  });

  it("omits the interval caps on a very narrow interval", () => {
    const r = cloneReport();
    const cma = r.regression.factors.find((f) => f.name === "CMA");
    if (!cma) throw new Error("no CMA");
    cma.ci_low = (cma.beta as number) - 0.0005;
    cma.ci_high = (cma.beta as number) + 0.0005;
    const { container } = render(<ExposuresPanel report={r} />);
    expect(rowOf(container, "CMA").querySelectorAll("line.ci")).toHaveLength(1);
    expect(rowOf(container, "SMB").querySelectorAll("line.ci")).toHaveLength(3);
  });

  it("explains the marks in the legend, with the window in the diamond entry", () => {
    render(<ExposuresPanel report={report} />);
    const legend = screen.getByRole("list", { name: "Legend" });
    const items = within(legend)
      .getAllByRole("listitem")
      .map((li) => li.textContent);
    expect(items).toEqual([
      "Beta",
      "Faded: not significant",
      "95% interval",
      `Average ${report.average_beta.window}d beta`,
    ]);
  });

  it("shows the reading line, the footnote and the folded method detail", () => {
    const { container } = render(<ExposuresPanel report={report} />);
    expect(container.querySelector(".reading")?.textContent).toMatch(/^Over this window the stock moves roughly one-for-one with the market/);
    expect(container.querySelector(".foot > p")?.textContent).toMatch(/Significant means the adjusted p is below 0\.05\.$/);
    expect(container.querySelector("details.how")?.textContent).toContain("Benjamini-Hochberg");
  });

  it("hides the average column values and the legend entry when the average beta is not ok", () => {
    const r = cloneReport();
    r.average_beta.status = "insufficient_data";
    r.average_beta.reason = "Too few rolling windows.";
    const { container } = render(<ExposuresPanel report={r} />);
    expect(container.querySelector("svg.avgm")).toBeNull();
    const cells = within(rowOf(container, "Mkt-RF")).getAllByRole("cell");
    expect(cells[4]?.textContent).toBe("–");
    expect(screen.queryByText(/^Average \d+d beta$/)).toBeNull();
  });

  it("keeps the rows in the report's order and links each row id for the equation", () => {
    const { container } = render(<ExposuresPanel report={report} />);
    const ids = Array.from(container.querySelectorAll("tbody tr")).map((el) => el.id);
    expect(ids).toEqual(report.regression.factors.map((f) => `beta-${f.name}`));
    expect(rowOf(container, "SMB").getAttribute("tabindex")).toBe("-1");
  });
});

describe("ExposuresPanel empty state", () => {
  it("shows the reason and one next step when the regression is not ok", () => {
    const r = cloneReport();
    r.regression.status = "insufficient_data";
    r.regression.reason = "Only 120 aligned days; at least 504 are needed.";
    const { container } = render(<ExposuresPanel report={r} />);
    expect(screen.getByText("Only 120 aligned days; at least 504 are needed.")).toBeTruthy();
    expect(screen.getByText("Widen the date range and run the report again.")).toBeTruthy();
    expect(container.querySelector("table")).toBeNull();
    expect(container.querySelector(".foot")).toBeNull();
    expect(exposuresUnavailable(r)).toBe(true);
  });

  it("falls back to a stated reason when no beta is finite", () => {
    const r = cloneReport();
    for (const f of r.regression.factors) f.beta = null;
    r.regression.reason = null;
    render(<ExposuresPanel report={r} />);
    expect(screen.getByText("Insufficient data: no factor betas available.")).toBeTruthy();
  });
});
