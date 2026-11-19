import { cleanup, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { cloneReport, mockReport } from "../../test/fixture";
import { Colophon } from "./Colophon";
import { GateEvidence } from "./GateEvidence";
import { Header, listingLine } from "./Header";
import { KpiStrip } from "./KpiStrip";
import { Notice } from "./Notice";

const HREF = "/api/report/SPY/html?range=3Y";

describe("Header", () => {
  it("shows the ticker, the download link at the right and the analysis bar", () => {
    const { container } = render(<Header report={mockReport} downloadHref={HREF} />);
    expect(screen.getByRole("heading", { level: 1 }).textContent).toBe("SPY");
    const dl = screen.getByRole("link", { name: "Download report" });
    expect(dl.getAttribute("href")).toBe(HREF);
    expect(dl.hasAttribute("download")).toBe(true);
    expect(dl.closest(".head-actions")).not.toBeNull();
    expect(container.querySelector(".ticker")?.textContent).toBe("SPY");
    expect(container.querySelector("dl.abar")?.getAttribute("aria-label")).toBe("Analysis settings");
    const pairs = Array.from(container.querySelectorAll(".abar > div")).map((d) => [
      d.querySelector("dt")?.textContent,
      d.querySelector("dd")?.textContent,
    ]);
    expect(pairs).toEqual([
      ["Analysis period", "8 Aug 2024 to 30 Sep 2026"],
      ["Observations", "559 trading days"],
      ["Factor data", "To 30 Sep 2026"],
      ["Benchmark", "ACWI"],
    ]);
    expect(container.querySelector(".abar dd[title]")?.getAttribute("title")).toBe("49 days old");
  });

  it("falls back to the ticker alone when the report has no security field", () => {
    const { container } = render(<Header report={mockReport} downloadHref={HREF} />);
    expect(container.querySelector(".nm")).toBeNull();
    expect(container.querySelector(".badge")).toBeNull();
    expect(container.querySelector(".listing")).toBeNull();
  });

  it("shows the company name, the type badge and the listing line when the security is known", () => {
    const r = cloneReport();
    (r.data as { security?: unknown }).security = {
      name: "SPDR S&P 500 ETF Trust",
      exchange: "NYSE Arca",
      currency: "USD",
      quote_type: "ETF",
    };
    const { container } = render(<Header report={r} downloadHref={HREF} />);
    expect(screen.getByRole("heading", { level: 1 }).textContent).toBe("SPYSPDR S&P 500 ETF Trust");
    expect(container.querySelector(".badge")?.textContent).toBe("ETF");
    expect(container.querySelector(".listing")?.textContent).toBe("Listed on NYSE Arca, priced in US dollars");
  });

  it("leaves out the parts Yahoo did not give", () => {
    expect(listingLine({ exchange: "NasdaqGS" })).toBe("Listed on NasdaqGS");
    expect(listingLine({ currency: "EUR" })).toBe("Priced in EUR");
    expect(listingLine({ name: "X" })).toBeNull();
    const r = cloneReport();
    (r.data as { security?: unknown }).security = { name: null, quote_type: "MUTUALFUND" };
    const { container } = render(<Header report={r} downloadHref={HREF} />);
    expect(container.querySelector(".nm")).toBeNull();
    expect(container.querySelector(".badge")).toBeNull();
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

  it("summarises audit errors in the static report's words (F4)", () => {
    const r = cloneReport();
    r.quality_gate.fired = false;
    r.warnings = [{ code: "audit_errors", message: "The price audit reported 1 error finding(s)." }];
    const { container } = render(<Notice report={r} />);
    expect(container.querySelector(".notice-sum")?.textContent).toBe(
      "Warning: The price audit found errors, so the headline numbers are not interpretable until they are explained; see Data and audit.",
    );
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

  it("mutes the fitted tiles and says alpha is not interpretable when the price audit found errors (F4)", () => {
    const r = cloneReport();
    r.regression.alpha_tag = "reliable";
    r.data.audit_status = "errors";
    const { container } = render(<KpiStrip report={r} />);
    const cells = Array.from(container.querySelectorAll(".kpi"));
    expect(cells[0]?.querySelector(".n")?.textContent).toBe("Not interpretable: the price audit found errors");
    expect(cells.map((c) => c.classList.contains("ns"))).toEqual([true, true, true, false, false]);
    expect(cells[0]?.querySelector(".v")?.textContent).toBe("+0.81%");
  });

  it("leaves the fitted tiles alone for warnings and a clean audit (F4)", () => {
    for (const status of ["clean", "warnings"] as const) {
      const r = cloneReport();
      r.regression.alpha_tag = "reliable";
      r.data.audit_status = status;
      const { container } = render(<KpiStrip report={r} />);
      const cells = Array.from(container.querySelectorAll(".kpi"));
      expect(cells[0]?.querySelector(".n")?.textContent).toBe("Distinguishable from zero at 5%");
      expect(cells.map((c) => c.classList.contains("ns"))).toEqual([false, false, false, false, false]);
      cleanup();
    }
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
      "factordesk report, schema v4, generated 18 Nov 2026, 09:30 UTC. Descriptive statistics on past data; nothing here is a forecast or advice.",
    );
  });
});
