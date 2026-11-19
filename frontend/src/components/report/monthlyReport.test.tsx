import { render, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { monthlyReport } from "../../test/fixture";
import { ReportView } from "./ReportView";

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

  it("names the record and has no download link", () => {
    const { container } = view();
    expect(container.querySelector("h1")?.textContent).toContain("Example Fund");
    expect(container.querySelector(".listing")?.textContent).toBe("Uploaded track record, returns after fees, in US dollars");
    expect(container.querySelector("a[download]")).toBeNull();
  });
});

describe("the lazy panels of a monthly record", () => {
  it("counts months in the drawdown table and leaves out the daily-only estimates", async () => {
    const { container } = render(
      <ReportView report={monthlyReport} downloadHref={null} win={null} onWinChange={vi.fn()} />,
    );
    await waitFor(() => expect(container.querySelector("#performance th[scope=col].num.hide-s")).not.toBeNull(), { timeout: 10_000 });
    expect(container.querySelector("#performance")?.textContent).toContain("Months");
    expect(container.querySelector("#performance")?.textContent).not.toContain("trading day");
    await waitFor(() => expect(container.querySelector("#regression-detail table")).not.toBeNull(), { timeout: 10_000 });
    const text = container.querySelector("#regression-detail")?.textContent ?? "";
    expect(text).not.toContain("5-day estimate");
    expect(container.querySelector("#exposures")?.textContent).not.toContain("NaN");
  }, 30_000);
});
