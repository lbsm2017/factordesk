import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { ApiError } from "../../api/types";
import { ErrorFrame } from "./ErrorFrame";
import { PlaceholderPage } from "./PlaceholderPage";
import { runView } from "../../api/runProgress";
import type { RunProgress } from "../../api/runProgress";

const error: ApiError = { code: "unknown_ticker", message: "No price data returned for XYZ.", action: "Check the ticker." };
const NO_STEPS: RunProgress = { steps: [], plain: false };

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

  it("the placeholder page has one h1 with the ticker, outside the aria-hidden part", () => {
    const { container } = render(<PlaceholderPage mode="track" title="SPY" view={runView(NO_STEPS, ["prices"])} />);
    const h1s = screen.getAllByRole("heading", { level: 1 });
    expect(h1s).toHaveLength(1);
    expect(h1s[0]?.textContent).toContain("SPY");
    expect(h1s[0]?.closest('[aria-hidden="true"]')).toBeNull();
    // The placeholder panel titles stay hidden from the outline.
    expect(container.querySelectorAll('[aria-hidden="true"] h2').length).toBeGreaterThan(0);
  });
});
