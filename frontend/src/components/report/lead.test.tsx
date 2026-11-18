import { readFileSync } from "node:fs";
import { join } from "node:path";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { cloneReport, mockReport } from "../../test/fixture";
import { Colophon } from "./Colophon";
import { Equation } from "./Equation";
import { GateEvidence } from "./GateEvidence";
import { Header } from "./Header";
import { KpiStrip } from "./KpiStrip";
import { Notice } from "./Notice";

const HREF = "/api/report/SPY/html?range=3Y";

describe("Header", () => {
  it("shows the ticker, the factor-data chip, the warnings chip and the download link", () => {
    const { container } = render(<Header report={mockReport} downloadHref={HREF} />);
    expect(screen.getByRole("heading", { level: 1 }).textContent).toContain("SPY");
    expect(screen.getByText("Factor data ends 30 Sep 2026 (49 days ago)")).toBeTruthy();
    const warn = screen.getByRole("link", { name: "2 warnings" });
    expect(warn.getAttribute("href")).toBe("#notice");
    const dl = screen.getByRole("link", { name: "Download report" });
    expect(dl.getAttribute("href")).toBe(HREF);
    expect(dl.hasAttribute("download")).toBe(true);
    expect(dl.className).toBe("btn-secondary");
    expect(container.querySelector(".ticker")?.textContent).toBe("SPY");
  });

  it("drops the warnings chip when there is nothing to warn about, and singularises", () => {
    const r = cloneReport();
    r.warnings = [];
    r.quality_gate.fired = false;
    r.data.factors_days_behind = 1;
    render(<Header report={r} downloadHref={HREF} />);
    expect(screen.queryByRole("link", { name: /warning/ })).toBeNull();
    expect(screen.getByText("Factor data ends 30 Sep 2026 (1 day ago)")).toBeTruthy();
  });
});

describe("Notice", () => {
  it("gives a plain summary with a hidden Warning prefix and the raw messages under Details", () => {
    const { container } = render(<Notice report={mockReport} />);
    const sum = container.querySelector(".notice-sum");
    expect(sum?.querySelector(".vh")?.textContent).toBe("Warning: ");
    expect(sum?.textContent).toContain("Prices look out of step with the factor data");
    expect(sum?.textContent).toContain("The history is short");
    const details = container.querySelector("details.how");
    expect(details?.querySelector("summary")?.textContent).toBe("Details");
    const items = Array.from(details?.querySelectorAll("li") ?? []).map((li) => li.textContent);
    expect(items).toEqual((mockReport.warnings ?? []).map((w) => w.message));
    expect(details?.textContent).toContain("5-day estimate (111 blocks): alpha +0.73% a year");
    expect(details?.querySelector("a")?.getAttribute("href")).toBe("#regression-detail");
  });

  it("adds the gate caveat when it fired without a residual_reversal warning", () => {
    const r = cloneReport();
    r.warnings = [{ code: "short_history", message: "short" }];
    const { container } = render(<Notice report={r} />);
    expect(container.querySelectorAll("details li")).toHaveLength(2);
  });

  it("counts the rest under Details when there are more than two distinct summaries", () => {
    const r = cloneReport();
    r.warnings = [
      { code: "a", message: "First." },
      { code: "b", message: "Second." },
      { code: "c", message: "Third." },
    ];
    r.quality_gate.fired = false;
    const { container } = render(<Notice report={r} />);
    expect(container.querySelector(".notice-sum")?.textContent).toBe("Warning: First. Second. 1 more are listed under Details.");
  });

  it("renders nothing without warnings", () => {
    const r = cloneReport();
    r.warnings = [];
    r.quality_gate.fired = false;
    const { container } = render(<Notice report={r} />);
    expect(container.firstChild).toBeNull();
  });
});

describe("Equation", () => {
  it("typesets the model with italic variables and terms that link to their rows", () => {
    const { container } = render(<Equation report={mockReport} />);
    expect(container.querySelectorAll(".lhs var")).toHaveLength(2);
    expect(container.querySelector(".eps var")?.textContent).toBe("ε");
    const hrefs = Array.from(container.querySelectorAll("a.term")).map((a) => a.getAttribute("href"));
    expect(hrefs).toEqual(["#ret-alpha", "#beta-Mkt-RF", "#beta-SMB", "#beta-HML", "#beta-RMW", "#beta-CMA"]);
    const text = container.querySelector(".terms")?.textContent ?? "";
    expect(text).toContain("+0.998Mkt-RF");
    expect(text).toContain("−0.141SMB");
    expect(text).toContain("0.81%");
  });

  it("fades and words the terms that are not significant", () => {
    const { container } = render(<Equation report={mockReport} />);
    const ns = Array.from(container.querySelectorAll("a.term.ns")).map((a) => a.getAttribute("href"));
    expect(ns).toEqual(["#ret-alpha", "#beta-HML", "#beta-CMA"]);
    expect(container.querySelector('a[href="#beta-HML"] .ann')?.textContent).toBe("valuenot significant, t 1.2");
    expect(container.querySelector('a[href="#beta-SMB"] .ann')?.textContent).toBe("sizesignificant, t −13.8");
  });

  it("carries a full aria-label", () => {
    const { container } = render(<Equation report={mockReport} />);
    const label = container.querySelector("figure")?.getAttribute("aria-label") ?? "";
    expect(label).toContain("alpha +0.81% a year");
    expect(label).toContain("+0.998 times Mkt-RF");
    expect(label).toContain("−0.141 times SMB");
    expect(label.endsWith("plus a residual.")).toBe(true);
  });

  it("focuses the row a term links to", () => {
    const { container } = render(
      <>
        <Equation report={mockReport} />
        <table>
          <tbody>
            <tr id="beta-SMB">
              <th>SMB</th>
            </tr>
          </tbody>
        </table>
      </>,
    );
    const row = document.getElementById("beta-SMB");
    fireEvent.click(container.querySelector('a[href="#beta-SMB"]') as Element);
    expect(row?.getAttribute("tabindex")).toBe("-1");
    expect(document.activeElement).toBe(row);
  });

  it("is omitted when the regression is not ok", () => {
    const r = cloneReport();
    r.regression.status = "insufficient_data";
    const { container } = render(<Equation report={r} />);
    expect(container.firstChild).toBeNull();
  });

  it("keeps the brackets and wraps at 390 px (stylesheet rules)", () => {
    const css = readFileSync(join(import.meta.dirname, "..", "..", "styles", "report.css"), "utf8");
    expect(css).toMatch(/\.term \.ann::before, \.term \.ann::after/);
    expect(css).toMatch(/\.terms \{[^}]*flex-wrap: wrap/);
    expect(css).toMatch(/max-width: 719px\)[\s\S]*\.eq \{ grid-template-columns: 1fr/);
  });
});

describe("KpiStrip", () => {
  it("shows five cells, each with one plain line", () => {
    const { container } = render(<KpiStrip report={mockReport} />);
    const cells = Array.from(container.querySelectorAll(".kpi"));
    expect(cells).toHaveLength(5);
    const rows = cells.map((c) => [c.querySelector("dt")?.textContent, c.querySelector(".v")?.textContent, c.querySelector(".n")?.textContent]);
    expect(rows).toEqual([
      ["Alpha, a year", "+0.81%", "Not distinguishable from zero"],
      ["R²", "0.9987", "Share of daily variance the factors explain"],
      ["Residual volatility", "0.6%", "A year, left unexplained by the factors"],
      ["Observations", "559", "Trading days; 1 excluded"],
      ["Analysed range", "Aug 2024 to Sep 2026", "Requested 1 Nov 2024 to 13 Nov 2026"],
    ]);
    expect(cells[0]?.classList.contains("ns")).toBe(true);
    expect(cells[4]?.classList.contains("dates")).toBe(true);
  });

  it("words a reliable alpha and no exclusions", () => {
    const r = cloneReport();
    r.regression.alpha_tag = "reliable";
    r.data.n_excluded = 0;
    const { container } = render(<KpiStrip report={r} />);
    expect(container.querySelector(".kpi .n")?.textContent).toBe("Distinguishable from zero at 5%");
    expect(container.querySelector(".kpi:nth-child(4) .n")?.textContent).toBe("Trading days; none excluded");
  });

  it("shows an empty state when the regression is not ok", () => {
    const r = cloneReport();
    r.regression.status = "insufficient_data";
    r.regression.reason = "Too few days.";
    const { container } = render(<KpiStrip report={r} />);
    expect(container.querySelector(".kpi")).toBeNull();
    expect(container.querySelector(".empty-what")?.textContent).toBe("Too few days.");
    expect(container.querySelector(".empty-do")?.textContent).toContain("Widen the date range");
  });
});

describe("Gate evidence inside the notice", () => {
  it("is a paragraph under Details, with no separate block or heading", () => {
    const { container } = render(<Notice report={mockReport} />);
    const text = container.querySelector("details.how .gate-evidence")?.textContent ?? "";
    expect(text).toContain("−0.31 (robust z −6.2)");
    expect(text).toContain("62%");
    expect(container.querySelector(".gate-callout")).toBeNull();
    expect(screen.queryByRole("heading", { name: "Residual quality gate" })).toBeNull();
    expect(container.querySelector("a")?.getAttribute("href")).toBe("#regression-detail");
  });

  it("keeps the evidence before the 5-day line", () => {
    const { container } = render(<Notice report={mockReport} />);
    const paras = Array.from(container.querySelectorAll("details.how > p")).map((p) => p.className || p.textContent);
    expect(paras[0]).toBe("gate-evidence");
    expect(paras[1]).toContain("5-day estimate");
  });

  it("prints the 5-day tag as a plain word, never the raw tag", () => {
    const { container } = render(<Notice report={mockReport} />);
    const text = container.querySelector("details.how")?.textContent ?? "";
    expect(text).not.toMatch(/reliable|noise/);
    expect(text).toMatch(/, (not )?significant; R²/);
  });

  it("renders nothing on its own when the gate did not fire", () => {
    const r = cloneReport();
    r.quality_gate.fired = false;
    const { container } = render(<GateEvidence report={r} />);
    expect(container.firstChild).toBeNull();
  });
});

describe("Colophon", () => {
  it("states the schema, the generated time and the disclaimer", () => {
    const { container } = render(<Colophon report={mockReport} />);
    expect(container.querySelector("footer.colophon p")?.textContent).toBe(
      "factordesk report, schema v3, generated 18 Nov 2026, 09:30 UTC. Descriptive statistics on past data; nothing here is a forecast or advice.",
    );
  });
});
