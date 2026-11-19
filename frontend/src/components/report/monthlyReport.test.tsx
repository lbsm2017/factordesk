import { render } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { mockReport, monthlyReport } from "../../test/fixture";
import { summaryOf } from "./DataNotes";
import { RegressionDetail } from "./RegressionDetail";
import { ReportView } from "./ReportView";
import { PerformanceBody } from "./sections/PerformanceBody";

describe("ReportView on an uploaded monthly record", () => {
  const view = () => render(<ReportView report={monthlyReport} downloadHref={null} win={null} onWinChange={vi.fn()} />);

  it("leaves out the panels that do not apply and keeps the rest in order", () => {
    const { container } = view();
    const ids = Array.from(container.querySelectorAll("main > [id]")).map((el) => el.id);
    expect(ids).toEqual(["header", "summary", "price", "performance", "exposures", "returns", "risk", "data", "regression-detail", "colophon"]);
    for (const gone of ["rolling", "world-beta", "residual-alpha", "kalman", "shrunk", "lead-lag", "fragility"]) {
      expect(container.querySelector(`#${gone}`)).toBeNull();
    }
  });

  it("counts months, not trading days", () => {
    const { container } = view();
    const bar = container.querySelector(".abar")?.textContent ?? "";
    expect(bar).toContain("84 months");
    expect(bar).not.toContain("trading day");
    expect(bar).not.toContain("Benchmark");
    expect(container.querySelector("#data")?.textContent).toContain("84 months");
    expect(container.querySelector("#data")?.textContent).not.toContain("trading day");
    expect(container.querySelector("#summary")?.textContent).toContain("Annualised from monthly data.");
    expect(container.querySelector("#summary")?.textContent).not.toContain("ACWI");
    expect(container.querySelector("#risk")?.textContent).toContain("month-to-month");
  });

  it("annualises the return sources with 12, not 252", () => {
    const { container } = view();
    const how = container.querySelector("#returns details.how")?.textContent ?? "";
    expect(how).toContain("times 12.");
    expect(how).not.toContain("252");
    expect(container.querySelector("#returns")?.textContent).not.toMatch(/\bdaily\b|trading day/);
  });

  it("words the factor-lag data note in months", () => {
    const lag = { code: "factor_data_lag", message: "raw" };
    expect(summaryOf([lag], true)).toBe(
      "The factor data stops before the latest returns, so the newest months are charted but not analysed.",
    );
    expect(summaryOf([lag])).toContain("newest days");
    const r = structuredClone(monthlyReport);
    r.warnings = [{ code: "factor_data_lag", message: "raw" }];
    const { container } = render(<ReportView report={r} downloadHref={null} win={null} onWinChange={vi.fn()} />);
    expect(container.querySelector(".notes-line")?.textContent).toContain("newest months");
  });

  it("uses subject-neutral words, and a ticker report keeps the stock wording", () => {
    const upload = structuredClone(monthlyReport);
    upload.data.factors_downloaded_at = null;
    const rec = render(<ReportView report={upload} downloadHref={null} win={null} onWinChange={vi.fn()} />).container;
    expect(rec.querySelector("#price caption")?.textContent).toBe("Data points");
    expect(rec.querySelector("#risk")?.textContent).toContain("specific to this record");
    expect(rec.querySelector("#risk")?.textContent).toContain("Specific to this record");
    expect(rec.querySelector("#data")?.textContent).toContain("Uploaded, not downloaded");
    for (const gone of ["Price points", "tock-specific", "Injected"]) {
      expect(rec.textContent).not.toContain(gone);
    }
    const tick = structuredClone(mockReport);
    tick.data.factors_downloaded_at = null;
    const t = render(<ReportView report={tick} downloadHref={null} win={null} onWinChange={vi.fn()} />).container;
    expect(t.querySelector("#price caption")?.textContent).toBe("Price points");
    expect(t.querySelector("#risk")?.textContent).toContain("Stock-specific");
    expect(t.querySelector("#data")?.textContent).toContain("Injected, not downloaded");
  });

  it("names the record and has no download link", () => {
    const { container } = view();
    expect(container.querySelector("h1")?.textContent).toContain("Example Fund");
    expect(container.querySelector(".listing")?.textContent).toBe("Uploaded track record, returns after fees, in US dollars");
    expect(container.querySelector("a[download]")).toBeNull();
  });
});

describe("the lazy panels of a monthly record, rendered directly", () => {
  it("counts months in the drawdown table", () => {
    const { container } = render(<PerformanceBody report={monthlyReport} />);
    expect(container.querySelector("#performance th[scope=col].num.hide-s")?.textContent).toBe("Months");
    expect(container.querySelector("#performance")?.textContent).not.toContain("trading day");
  });

  it("shows no 5-day estimate in the regression detail", () => {
    const { container } = render(<RegressionDetail report={monthlyReport} />);
    expect(container.querySelector("table")).not.toBeNull();
    expect(container.textContent).not.toContain("5-day estimate");
    expect(container.textContent).toContain("No clear month-to-month pattern.");
    expect(container.textContent).not.toMatch(/\bday\b|\bdaily\b|day-to-day/);
  });
});
