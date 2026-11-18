import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { ApiError } from "../../api/types";
import { ErrorFrame } from "./ErrorFrame";
import { LoadingFrame } from "./LoadingFrame";

const error: ApiError = { code: "unknown_ticker", message: "No price data returned for XYZ.", action: "Check the ticker." };

describe("one page heading in every state (review A4)", () => {
  it("the error state has an h1 with the ticker above the alert", () => {
    render(<ErrorFrame ticker="XYZ" error={error} />);
    const h1 = screen.getByRole("heading", { level: 1 });
    expect(h1.textContent).toBe("XYZ");
    const alert = screen.getByRole("alert");
    expect(h1.compareDocumentPosition(alert) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(alert.textContent).toContain("No price data returned for XYZ.");
    expect(alert.textContent).toContain("Check the ticker.");
  });

  it("the loading state has one h1 with the ticker, outside the aria-hidden part", () => {
    const { container } = render(<LoadingFrame ticker="SPY" />);
    const h1s = screen.getAllByRole("heading", { level: 1 });
    expect(h1s).toHaveLength(1);
    expect(h1s[0]?.textContent).toContain("SPY");
    expect(h1s[0]?.closest('[aria-hidden="true"]')).toBeNull();
    // The placeholder panel titles stay hidden from the outline.
    expect(container.querySelectorAll('[aria-hidden="true"] h2')).toHaveLength(7);
  });
});
