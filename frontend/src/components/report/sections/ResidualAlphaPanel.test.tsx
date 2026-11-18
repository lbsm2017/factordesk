import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { cloneReport } from "../../../test/fixture";
import { withSection } from "../../../test/sectionFixtures";
import { ResidualAlphaPanel } from "./ResidualAlphaPanel";

describe("ResidualAlphaPanel (lazy wrapper)", () => {
  it("renders nothing while the section is null", () => {
    const { container } = render(<ResidualAlphaPanel report={cloneReport()} />);
    expect(container.innerHTML).toBe("");
  });

  it("holds its place with the frame at once, then shows the body", async () => {
    const { container } = render(<ResidualAlphaPanel report={withSection(cloneReport(), "residual")} />);
    // Synchronously: the section element with its id, title and question, and no numbers yet.
    const frame = container.querySelector("section#residual");
    expect(frame).not.toBeNull();
    expect(frame?.querySelector("h2")?.textContent).toBe("Residual return");
    expect(frame?.querySelector(".q")?.textContent).toMatch(/^What did this stock return/);
    expect(frame?.querySelector("table")).toBeNull();
    // Then the chunk arrives and the same element holds the table.
    expect(await screen.findByRole("table", { name: /Residual return of the stock, in-sample against point-in-time/ })).not.toBeNull();
    expect(container.querySelectorAll("section#residual")).toHaveLength(1);
  });
});
