import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { PortfolioBacktestSection } from "../../api/types";
import section from "@fixtures/sections/portfolio_backtest.json";
import { BacktestCard } from "./BacktestCard";

const base = section as unknown as PortfolioBacktestSection;

describe("BacktestCard", () => {
  it("shows the window, the limiting instruments, rebalances, cost, unallocated weight and the survivorship note", () => {
    render(<BacktestCard section={base} />);
    const card = within(screen.getByTestId("backtest-card"));
    expect(card.getByRole("heading", { name: "Backtest" })).toBeTruthy();
    expect(card.getByText("Jan 2010 to Oct 2012")).toBeTruthy();
    expect(card.getByText("Emerging Markets Bonds (EMB) begins")).toBeTruthy();
    expect(card.queryByText("Ends when")).toBeNull();
    expect(card.queryByText("Skipped days")).toBeNull();
    expect(card.getByText("33 monthly")).toBeTruthy();
    expect(card.getByText(/5 bps one way, 0.21% paid in total/)).toBeTruthy();
    expect(card.getByText("10.0% held as USD cash")).toBeTruthy();
    expect(card.getByText(/only|Past delisted/)).toBeTruthy();
  });

  it("names several limiting instruments, and the skipped days when there are some", () => {
    render(
      <BacktestCard
        section={{ ...base, start_limited_by: ["A", "B", "C"], unallocated_weight: 0, n_dates_dropped: 4, data_note: "Four days were skipped." }}
      />,
    );
    const card = within(screen.getByTestId("backtest-card"));
    expect(card.getByText("A, B and C begins")).toBeTruthy();
    expect(card.queryByText("Unallocated")).toBeNull();
    expect(card.queryByText("None", { selector: "dd" })).toBeNull();
    expect(card.getByText("4 trading days without a full set of prices")).toBeTruthy();
    expect(card.getByText("Four days were skipped.")).toBeTruthy();
  });

  it("shows a holding once when its label and ticker agree", () => {
    render(<BacktestCard section={{ ...base, start_limited_by: ["IEF (IEF)"] }} />);
    expect(screen.getByText("IEF begins")).toBeTruthy();
  });
});
