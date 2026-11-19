import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { cloneReport, mockReport } from "../../test/fixture";
import { DataAuditPanel } from "./DataAuditPanel";

function facts(container: HTMLElement): Record<string, string> {
  const out: Record<string, string> = {};
  container.querySelectorAll("dl.facts > div").forEach((row) => {
    out[row.querySelector("dt")?.textContent ?? ""] = row.querySelector("dd")?.textContent ?? "";
  });
  return out;
}

describe("DataAuditPanel", () => {
  it("lists the coverage facts with the fixture's numbers", () => {
    const { container } = render(<DataAuditPanel report={mockReport} />);
    expect(screen.getByRole("heading", { level: 2, name: "Data and audit" })).toBeTruthy();
    const f = facts(container);
    expect(f["Requested"]).toBe("1 Nov 2024 to 13 Nov 2026");
    expect(f["Analysed"]).toBe("8 Aug 2024 to 30 Sep 2026, 559 trading days");
    expect(f["Excluded inside the range"]).toBe("1 (1 return spans several factor days)");
    expect(f["After factor data"]).toBe("32 price days (raw return +1.23%, not analysed)");
    expect(f["Before factor data"]).toBe("0 price days");
    expect(f["Factor data ends"]).toBe("30 Sep 2026, 49 days before the report");
    expect(f["Factor file downloaded"]).toBe("1 Nov 2026, 00:00 UTC");
    expect(f["Prices"]).toBe("MOCK price source (Adj Close)");
  });

  it("writes the download time like the other dates, never as an ISO stamp", () => {
    const { container } = render(<DataAuditPanel report={mockReport} />);
    const f = facts(container);
    expect(f["Factor file downloaded"]).not.toMatch(/\d{4}-\d{2}-\d{2}/);
  });

  it("shows the factor source URL as plain text, not a link", () => {
    const { container } = render(<DataAuditPanel report={mockReport} />);
    expect(facts(container)["Factors"]).toBe("https://example.invalid/factors.zip");
    expect(container.querySelector("a")).toBeNull();
  });

  it("shows each finding with a glyph, a severity word, the message and its dates", () => {
    const { container } = render(<DataAuditPanel report={mockReport} />);
    const items = container.querySelectorAll("ul.findings > li");
    expect(items).toHaveLength(2);
    const [info, warning] = Array.from(items) as HTMLElement[];
    expect(info?.className).toBe("sev-info");
    expect(info?.querySelector("svg.glyph")?.getAttribute("aria-hidden")).toBe("true");
    expect(info?.querySelector(".sev")?.textContent).toBe("Info");
    expect(info?.querySelector(".msg")?.textContent).toBe("MOCK: no splits in window.");
    expect(warning?.className).toBe("sev-warning");
    expect(warning?.querySelector("svg.glyph")).not.toBeNull();
    expect(warning?.querySelector(".sev")?.textContent).toBe("Warning");
    expect(warning?.querySelector(".msg")?.textContent).toBe("MOCK: one 4-day gap in the series. (15 May 2025)");
    expect(warning?.querySelector(".dates")?.textContent).toBe(" (15 May 2025)");
  });

  it("caps the dates at six and counts the rest", () => {
    const report = cloneReport();
    report.data.audit_findings = [
      {
        code: "gaps",
        severity: "error",
        message: "Gaps.",
        dates: ["2025-01-02", "2025-01-03", "2025-01-06", "2025-01-07", "2025-01-08", "2025-01-09", "2025-01-10", "2025-01-13"],
      },
    ];
    const { container } = render(<DataAuditPanel report={report} />);
    const li = container.querySelector("ul.findings > li");
    expect(li?.querySelector(".sev")?.textContent).toBe("Error");
    expect(li?.querySelector(".dates")?.textContent).toBe(
      " (2 Jan 2025, 3 Jan 2025, 6 Jan 2025, 7 Jan 2025, 8 Jan 2025, 9 Jan 2025 and 2 more)",
    );
  });

  it("says so when there are no findings", () => {
    const report = cloneReport();
    report.data.audit_findings = [];
    const { container } = render(<DataAuditPanel report={report} />);
    expect(screen.getByText("No findings. Prices passed every check.")).toBeTruthy();
    const items = container.querySelectorAll("ul.findings > li");
    expect(items).toHaveLength(1);
    expect(items[0]?.className).toBe("sev-none");
    expect(items[0]?.querySelector("svg")).toBeNull();
  });

  it("lists the caveats, adding the vintage text once", () => {
    const { container } = render(<DataAuditPanel report={mockReport} />);
    const items = Array.from(container.querySelectorAll("ul.notes > li")).map((li) => li.textContent);
    const notes = mockReport.notes ?? [];
    expect(items.slice(0, notes.length)).toEqual(notes);
    const vintage = mockReport.label_text?.["L-VINTAGE"];
    expect(vintage).toBeTruthy();
    expect(items.filter((t) => t === vintage)).toHaveLength(1);

    const again = cloneReport();
    const v = again.label_text?.["L-VINTAGE"] ?? "";
    again.notes = [...(again.notes ?? []), v];
    const second = render(<DataAuditPanel report={again} />);
    const texts = Array.from(second.container.querySelectorAll("ul.notes > li")).map((li) => li.textContent);
    expect(texts.filter((t) => t === v)).toHaveLength(1);
  });

  it("reads 'none' after the factor data when no price days were cut, and 'Injected' when not downloaded", () => {
    const report = cloneReport();
    report.data.uncovered.n = 0;
    report.data.factors_downloaded_at = null;
    report.data.n_excluded = 0;
    report.data.excluded_by_reason = {};
    const { container } = render(<DataAuditPanel report={report} />);
    const f = facts(container);
    expect(f["After factor data"]).toBe("none");
    expect(f["Factor file downloaded"]).toBe("Injected, not downloaded");
    expect(f["Excluded inside the range"]).toBe("0");
  });

  it("groups thousands in counts, as the KPI strip does (real Full-history SPY run)", () => {
    const report = cloneReport();
    report.data.n_obs = 8474;
    report.data.uncovered.n = 1034;
    report.data.dropped_price_dates_before_factors = 2500;
    const { container } = render(<DataAuditPanel report={report} />);
    const f = facts(container);
    expect(f["Analysed"]).toMatch(/, 8,474 trading days$/);
    expect(f["After factor data"]).toMatch(/^1,034 price days/);
    expect(f["Before factor data"]).toBe("2,500 price days");
  });

  it("closes with the note that findings are never acted on", () => {
    const { container } = render(<DataAuditPanel report={mockReport} />);
    const foot = container.querySelector(".foot");
    expect(foot).not.toBeNull();
    expect(within(foot as HTMLElement).getByText(/Audit findings are reported, never acted on/)).toBeTruthy();
  });
});
