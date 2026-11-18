import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { FactorReport, ShrunkBetas } from "../../../api/types";
import { signed } from "../../../format";
import { cloneReport } from "../../../test/fixture";
import { withSection } from "../../../test/sectionFixtures";
import { ShrunkBetasPanel } from "./ShrunkBetasPanel";

const LABELS: Record<string, string> = {
  "L-SHRINK": "Pulled toward typical: each beta is moved toward the beta of the market portfolio.",
  "L-SHRINK-PRIOR": "Prior: centre 1 for Mkt-RF and 0 for the other betas.",
  "L-CRED": "95% credible interval under the stated prior.",
  "L-CORR-MOVE": "Moved away from its typical value because it is estimated jointly with correlated factors.",
  "L-MDE": "Smallest beta that the test behind the reliable tags would detect with 80% power.",
};

function reportWith(edit?: (s: ShrunkBetas[]) => void): FactorReport {
  const report = withSection(cloneReport(), "shrunk_betas");
  report.label_text = { ...report.label_text, ...LABELS };
  if (edit && report.shrunk_betas) edit(report.shrunk_betas);
  return report;
}

function scopeOf(container: HTMLElement, scope: "full_sample" | "latest_window"): HTMLElement {
  const h = container.querySelector(`#shrunk-${scope}-h`);
  const block = h?.closest<HTMLElement>(".shrunk-scope");
  if (!block) throw new Error(`no block for ${scope}`);
  return block;
}

function cells(block: HTMLElement, factor: string): string[] {
  const row = block.querySelector<HTMLElement>(`tr[id$="-${factor}"]`);
  if (!row) throw new Error(`no row for ${factor}`);
  return within(row)
    .getAllByRole("cell")
    .map((c) => c.textContent ?? "");
}

describe("ShrunkBetasPanel", () => {
  it("renders nothing while the field is null", () => {
    const report = cloneReport();
    report.shrunk_betas = null;
    const { container } = render(<ShrunkBetasPanel report={report} />);
    expect(container.firstChild).toBeNull();
  });

  it("shows the full sample: unchanged betas, the no-visible-pull line, no markers", () => {
    const { container } = render(<ShrunkBetasPanel report={reportWith()} />);
    const full = scopeOf(container, "full_sample");
    expect(within(full).getByText("Shrinkage moves no beta by a visible amount: this sample is long enough.")).toBeTruthy();
    const mkt = cells(full, "Mkt-RF");
    // plot (marks only), OLS, se, shrunk, interval, pull
    expect(mkt.slice(1)).toEqual(["+1.009", "0.007", "+1.009", "[+0.996, +1.022]", "0.1%"]);
    expect(full.querySelector(".shrm")).toBeNull();
    expect(full.querySelector("line.cred")).toBeNull();
    expect(full.querySelector(".moved")).toBeNull();
  });

  it("shows the latest window: marker, interval, pull and the moved-away word", () => {
    const { container } = render(<ShrunkBetasPanel report={reportWith()} />);
    const win = scopeOf(container, "latest_window");
    expect(win.querySelector(".reading")).toBeNull();
    expect(cells(win, "Mkt-RF").slice(1)).toEqual(["+1.484", "0.222", "+1.227", "[+0.929, +1.526]", "53.0%"]);
    expect(cells(win, "SMB").slice(1)[2]).toBe("+0.563");
    expect(cells(win, "CMA").slice(1)).toEqual(["−0.155", "0.543", "+0.042", "[−0.404, +0.488]", "80.3%"]);
    expect(win.querySelectorAll(".shrm")).toHaveLength(5);
    expect(win.querySelectorAll("tbody line.cred").length).toBe(15);
  });

  it("marks a moved-away beta with words as well as a glyph, and only that beta", () => {
    const { container } = render(<ShrunkBetasPanel report={reportWith()} />);
    const win = scopeOf(container, "latest_window");
    const moved = win.querySelectorAll(".moved");
    expect(moved).toHaveLength(1);
    expect(moved[0]?.closest("tr")?.id).toBe("shrunk-latest_window-SMB");
    expect(moved[0]?.textContent).toMatch(/Moved away from typical/);
    expect(moved[0]?.querySelector('[aria-hidden="true"]')?.textContent).toBe("↗");
    expect(win.querySelector("#shrunk-latest_window-SMB .vh")?.textContent).toContain("moved away from its typical value");
  });

  it("draws a marker only for a pull of at least 0.05", () => {
    const report = reportWith((s) => {
      const b = s[1]?.betas;
      if (b?.[0]) b[0].pull = 0.0499;
      if (b?.[1]) b[1].pull = 0.05;
    });
    const { container } = render(<ShrunkBetasPanel report={report} />);
    const win = scopeOf(container, "latest_window");
    expect(win.querySelector("#shrunk-latest_window-Mkt-RF .shrm")).toBeNull();
    expect(win.querySelector("#shrunk-latest_window-SMB .shrm")).not.toBeNull();
    // Mkt-RF still has its numbers in the columns
    expect(cells(win, "Mkt-RF")[3]).toBe("+1.227");
  });

  it("clips a pull above 1 to 100% and below 0 to 0%", () => {
    const report = reportWith((s) => {
      const b = s[1]?.betas;
      if (b?.[0]) b[0].pull = 1.7;
      if (b?.[1]) b[1].pull = -0.2;
    });
    const { container } = render(<ShrunkBetasPanel report={report} />);
    const win = scopeOf(container, "latest_window");
    expect(cells(win, "Mkt-RF")[5]).toBe("100.0%");
    expect(cells(win, "SMB")[5]).toBe("0.0%");
    expect(win.querySelector("#shrunk-latest_window-SMB .shrm")).toBeNull();
  });

  it("prints the power statements of each scope as the model wrote them", () => {
    const report = reportWith();
    const { container } = render(<ShrunkBetasPanel report={report} />);
    const win = scopeOf(container, "latest_window");
    const items = within(win).getAllByRole("listitem").map((li) => li.textContent);
    expect(items).toEqual((report.shrunk_betas?.[1]?.power ?? []).map((p) => p.text));
    expect(items[1]).toContain("An SMB beta of 0.05 is not detectable for this stock with daily data");
    const mde = (report.shrunk_betas?.[1]?.power ?? []).map((p) => (p.mde80 ?? 0).toFixed(3));
    expect(mde).toEqual(["0.759", "0.899", "0.998", "1.223", "1.856"]);
    const full = scopeOf(container, "full_sample");
    expect(within(full).getAllByRole("listitem")[1]?.textContent).toContain("An SMB beta of 0.05 is already detectable.");
  });

  it("uses the true minus sign and the shared signed format in every beta column", () => {
    const { container } = render(<ShrunkBetasPanel report={reportWith()} />);
    const win = scopeOf(container, "latest_window");
    const hml = cells(win, "HML");
    expect(hml[1]).toBe(signed(-1.015));
    expect(hml[1]?.startsWith("−")).toBe(true);
    expect(hml[3]).toBe("−0.568");
    expect(hml[4]).toBe("[−0.956, −0.181]");
    expect(container.textContent).not.toMatch(/-\d\.\d{3}/);
  });

  it("folds the labels into How this is computed, from label_text, with the prior values", () => {
    const { container } = render(<ShrunkBetasPanel report={reportWith()} />);
    const how = container.querySelector("details.how");
    expect(how).not.toBeNull();
    const text = how?.textContent ?? "";
    for (const k of ["L-SHRINK", "L-SHRINK-PRIOR", "L-CRED", "L-MDE", "L-CORR-MOVE"]) expect(text).toContain(LABELS[k]);
    expect(text).toContain("Mkt-RF 1.000 and 0.209");
    expect(text).toContain("49 industry and 75 size portfolios");
    // the descriptive label is the footnote, not part of the fold
    expect(container.querySelector(".foot > p")?.textContent).toMatch(/Descriptive, in-sample, not predictive\./);
  });

  it("shows the reason and one next step for a scope that is not ok, with no numbers", () => {
    const report = reportWith((s) => {
      const w = s[1];
      if (!w) return;
      w.status = "insufficient_data";
      w.reason = "Insufficient data: the latest window needs 252 rows.";
      w.betas = [];
      w.power = [];
      w.prior = null;
    });
    const { container } = render(<ShrunkBetasPanel report={report} />);
    const win = scopeOf(container, "latest_window");
    expect(within(win).getByText("Insufficient data: the latest window needs 252 rows.")).toBeTruthy();
    expect(within(win).getByText("Widen the date range and run the report again.")).toBeTruthy();
    expect(win.querySelector("table")).toBeNull();
    expect(win.querySelector("svg")).toBeNull();
    expect(win.textContent).not.toMatch(/\d\.\d{2,}/);
    // the other scope is unaffected
    expect(scopeOf(container, "full_sample").querySelector("table")).not.toBeNull();
  });

  it("exposes landmarks, a labelled table, column headers and hidden decoration", () => {
    const { container } = render(<ShrunkBetasPanel report={reportWith()} />);
    expect(screen.getByRole("region", { name: "Pulled toward typical" })).toBeTruthy();
    expect(screen.getByRole("heading", { level: 2, name: "Pulled toward typical" })).toBeTruthy();
    expect(screen.getByRole("heading", { level: 3, name: "Latest 252-day window" })).toBeTruthy();
    const tables = screen.getAllByRole("table");
    expect(tables).toHaveLength(2);
    expect(screen.getByRole("table", { name: "Full sample (559 days)" })).toBeTruthy();
    const heads = within(tables[1] as HTMLElement)
      .getAllByRole("columnheader")
      .map((h) => h.textContent);
    expect(heads).toEqual(["Factor", "Chart", "OLS beta", "se", "Shrunk beta", "95% credible interval", "Pull"]);
    expect(within(tables[1] as HTMLElement).getAllByRole("rowheader")).toHaveLength(5);
    for (const svg of container.querySelectorAll("tbody svg.bar-svg")) expect(svg.getAttribute("aria-hidden")).toBe("true");
    expect(container.querySelector("tfoot tr.axis-row")?.getAttribute("aria-hidden")).toBe("true");
    // marker text for screen readers repeats the numbers
    expect(container.querySelector("#shrunk-latest_window-Mkt-RF .vh")?.textContent).toMatch(
      /pulled toward typical to \+1\.227, 95% credible interval \+0\.929 to \+1\.526, pull 53\.0%/,
    );
    // rows can take focus from a link target, as in the other panels
    expect(container.querySelector("tbody tr")?.getAttribute("tabindex")).toBe("-1");
  });

  it("draws the moved-away word and L-CORR-MOVE only where the pull marker is drawn", () => {
    // SMB moved away but its pull is below 0.05; HML in the full sample (pull 0.0007) is flagged too.
    const report = reportWith((s) => {
      const hml = s[0]?.betas[2];
      if (hml) hml.moved_away = true;
      s[0]?.labels.push("L-CORR-MOVE");
      const smb = s[1]?.betas[1];
      if (smb) smb.pull = 0.04;
    });
    const { container } = render(<ShrunkBetasPanel report={report} />);
    expect(container.querySelector(".moved")).toBeNull();
    expect(container.textContent).not.toContain("Moved away from typical");
    expect(container.querySelector("details.how")?.textContent).not.toContain(LABELS["L-CORR-MOVE"]);
  });

  it("shows the moved-away word and the label again once the pull reaches 0.05", () => {
    const report = reportWith((s) => {
      const smb = s[1]?.betas[1];
      if (smb) smb.pull = 0.05;
    });
    const { container } = render(<ShrunkBetasPanel report={report} />);
    expect(container.querySelectorAll(".moved")).toHaveLength(1);
    expect(container.querySelector("details.how")?.textContent).toContain(LABELS["L-CORR-MOVE"]);
  });

  it("uses the same words as the static panel", () => {
    const { container } = render(<ShrunkBetasPanel report={reportWith()} />);
    const text = container.textContent ?? "";
    // headings
    expect(screen.getByRole("heading", { level: 3, name: "Full sample (559 days)" })).toBeTruthy();
    expect(screen.getAllByRole("heading", { level: 4 }).map((h) => h.textContent)).toEqual([
      "What the test behind the reliable tags could detect",
      "What the test behind the reliable tags could detect",
    ]);
    // legend, pull note, interval format, no-pull line
    expect(container.querySelector(".legend")?.textContent).toContain("Pulled 5% or more toward typical");
    expect(text).toContain(
      "Pull is the share of the way from the OLS beta to its typical value: 0% means no move, 100% means all the way.",
    );
    expect(text).toContain("[+0.996, +1.022]");
    expect(text).toContain("Shrinkage moves no beta by a visible amount: this sample is long enough.");
    // the prior sentence, then the model labels, inside the fold
    expect(container.querySelector("details.how p")?.textContent).toMatch(
      /^Prior centre and spread per factor: Mkt-RF 1\.000 and 0\.209; SMB 0\.000 and 0\.764; HML 0\.000 and 0\.341; RMW 0\.000 and 0\.329; CMA 0\.000 and 0\.254\. The spread comes from 49 industry and 75 size portfolios, 2016-09-21 to 2026-09-30\. Pulled toward typical:/,
    );
    expect(container.querySelector("caption.vh")?.textContent).toBe(
      "OLS and shrunk betas with standard errors, 95% credible intervals and pull; a marker is drawn only where the pull is at least 5%",
    );
  });

  it("names a next step by status for a scope that is not ok", () => {
    const failed = reportWith((s) => {
      const w = s[1];
      if (!w) return;
      w.status = "failed";
      w.reason = "The prior files are missing.";
      w.betas = [];
      w.power = [];
      w.prior = null;
    });
    const { container } = render(<ShrunkBetasPanel report={failed} />);
    expect(
      within(scopeOf(container, "latest_window")).getByText(
        "Run the report again; if it repeats, check the factor data in Data and audit.",
      ),
    ).toBeTruthy();
  });

  it("draws no footnote or legend when no scope is ok", () => {
    const report = reportWith((s) => {
      for (const w of s) {
        w.status = "failed";
        w.reason = "The prior files are missing.";
        w.betas = [];
        w.power = [];
        w.prior = null;
        w.labels = [];
      }
    });
    const { container } = render(<ShrunkBetasPanel report={report} />);
    expect(container.querySelector(".foot")).toBeNull();
    expect(container.querySelector(".legend")).toBeNull();
    expect(container.querySelectorAll(".empty")).toHaveLength(2);
  });
});
