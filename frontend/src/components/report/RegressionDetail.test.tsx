import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { cloneReport, mockReport } from "../../test/fixture";
import { RegressionDetail } from "./RegressionDetail";

function rowsOf(region: HTMLElement): string[][] {
  return Array.from(region.querySelectorAll("tbody tr")).map((tr) =>
    Array.from(tr.querySelectorAll("th, td")).map((c) => c.textContent ?? ""),
  );
}

describe("RegressionDetail", () => {
  it("renders the detail table inside a labelled, focusable region", () => {
    render(<RegressionDetail report={mockReport} />);
    const region = screen.getByRole("region", { name: "Regression detail table, scrolls sideways" });
    expect(region.getAttribute("tabindex")).toBe("0");
    expect(region.querySelector("table.reg")).not.toBeNull();
    const heads = Array.from(region.querySelectorAll("thead th")).map((h) => h.textContent);
    expect(heads).toEqual([
      "Term",
      "Estimate",
      "Std. error",
      "t",
      "p",
      "p, adjusted",
      "95% interval",
      "VIF",
      "Significant",
    ]);
  });

  it("shows the fixture's numbers, with true minus signs", () => {
    render(<RegressionDetail report={mockReport} />);
    const rows = rowsOf(screen.getByRole("region", { name: /Regression detail table/ }));
    expect(rows).toHaveLength(6);
    const [alpha, mkt, smb] = rows;
    expect(alpha?.slice(0, 2)).toEqual(["Alpha, a year", "+0.81%"]);
    expect(alpha?.[6]).toBe("−1.54% to +3.16%");
    expect(alpha?.[7]).toBe("–");
    expect(alpha?.[8]).toBe("No");
    expect(mkt?.slice(0, 5)).toEqual(["Mkt-RF", "+0.998", "0.0021", "475", "<0.001"]);
    expect(mkt?.[8]).toBe("Yes");
    expect(smb?.[1]).toBe("−0.141");
    expect(smb?.[3]).toBe("−13.8");
    expect(smb?.join(" ")).not.toContain("-0");
    expect(smb?.[7]).toMatch(/^\d+\.\d{2}$/);
  });

  it("marks a not significant row", () => {
    const { container } = render(<RegressionDetail report={mockReport} />);
    const hml = Array.from(container.querySelectorAll("tbody tr")).find(
      (tr) => tr.querySelector("th")?.textContent === "HML",
    );
    expect(hml?.className).toBe("ns");
    expect(hml?.querySelector("td.sig")?.textContent).toBe("No");
  });

  it("renders the 5-day and diagnostics tables in their own labelled regions", () => {
    render(<RegressionDetail report={mockReport} />);
    const five = screen.getByRole("region", { name: "5-day estimate table, scrolls sideways" });
    expect(five.getAttribute("tabindex")).toBe("0");
    expect(rowsOf(five)).toHaveLength(6);
    expect(screen.getByRole("heading", { level: 3, name: /^5-day estimate \(111 blocks\)$/ })).toBeTruthy();
    const diag = screen.getByRole("region", { name: "Residual diagnostics table, scrolls sideways" });
    const rows = rowsOf(diag);
    expect(rows[0]?.slice(0, 4)).toEqual(["Lag-1 autocorrelation", "−0.310", "z −6.2", "<0.001"]);
    expect(rows[0]?.[4]).toBe("MOCK: lag-1 autocorrelation of the residuals is -0.31.");
    expect(rows[1]).toEqual(["Ljung-Box", "88.00", "df 10", "<0.001", "MOCK: Ljung-Box rejects."]);
    expect(rows).toHaveLength(1 + mockReport.residual_diagnostics.tests.length);
  });

  it("omits the 5-day table when that estimate is not available", () => {
    const report = cloneReport();
    report.five_day_regression.status = "not_applicable";
    render(<RegressionDetail report={report} />);
    expect(screen.queryByRole("region", { name: /5-day estimate/ })).toBeNull();
    expect(screen.queryByRole("heading", { name: /5-day estimate/ })).toBeNull();
  });

  it("shows an empty state for the diagnostics when they are not ok", () => {
    const report = cloneReport();
    report.residual_diagnostics.status = "insufficient_data";
    report.residual_diagnostics.reason = "Too few days for the tests.";
    const { container } = render(<RegressionDetail report={report} />);
    expect(screen.queryByRole("region", { name: /Residual diagnostics/ })).toBeNull();
    expect(screen.getByRole("heading", { level: 3, name: "Residual diagnostics" })).toBeTruthy();
    expect(container.querySelector(".empty-what")?.textContent).toBe("Too few days for the tests.");
    expect(screen.getByRole("region", { name: /Regression detail table/ })).toBeTruthy();
  });

  it("replaces the whole panel body with an empty state when the regression is not ok", () => {
    const report = cloneReport();
    report.regression.status = "insufficient_data";
    report.regression.reason = "Only 120 aligned days; at least 504 are needed.";
    const { container } = render(<RegressionDetail report={report} />);
    expect(screen.getByRole("heading", { level: 2, name: "Regression detail" })).toBeTruthy();
    expect(container.querySelector(".empty-what")?.textContent).toBe("Only 120 aligned days; at least 504 are needed.");
    expect(container.querySelector(".empty-do")?.textContent).toBeTruthy();
    expect(container.querySelector("table")).toBeNull();
    expect(container.querySelector(".foot")).toBeNull();
  });

  it("reads n/a for a missing number instead of NaN", () => {
    const report = cloneReport();
    const first = report.regression.factors[0];
    if (!first) throw new Error("fixture has no factors");
    first.se = null;
    first.p = null;
    const { container } = render(<RegressionDetail report={report} />);
    expect(container.textContent).not.toContain("NaN");
    const rows = rowsOf(screen.getByRole("region", { name: /Regression detail table/ }));
    expect(rows[1]?.[2]).toBe("n/a");
    expect(rows[1]?.[4]).toBe("n/a");
  });

  it("gives the fit summary as the footnote and the method detail folded", () => {
    const { container } = render(<RegressionDetail report={mockReport} />);
    const foot = container.querySelector("div.foot") as HTMLElement;
    expect(within(foot).getByText(/^R² 0\.9987, adjusted 0\.9987\. Residual volatility 0\.60% a year\. Newey-West lags 6\.$/)).toBeTruthy();
    const how = foot.querySelector("details.how");
    expect(how?.textContent).toContain("Condition number of the factor correlation matrix");
  });

  it("lists the readings of the significant betas", () => {
    render(<RegressionDetail report={mockReport} />);
    expect(screen.getByRole("heading", { level: 3, name: "Reading the significant betas" })).toBeTruthy();
    expect(screen.getByText("MOCK reading of Mkt-RF.")).toBeTruthy();
  });
});
