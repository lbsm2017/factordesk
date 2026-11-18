import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { PanelBoundary } from "./PanelBoundary";

function Thrower(): never {
  throw new Error("boom");
}

describe("PanelBoundary", () => {
  beforeEach(() => {
    // React and the boundary both log the caught error; keep the test output clean.
    vi.spyOn(console, "error").mockImplementation(() => undefined);
  });
  afterEach(() => vi.restoreAllMocks());

  it("shows its children when nothing fails", () => {
    render(
      <PanelBoundary id="x" title="X" question="Q?">
        <p>fine</p>
      </PanelBoundary>,
    );
    expect(screen.getByText("fine")).not.toBeNull();
  });

  it("replaces a throwing child with a plain notice and leaves its siblings alone", () => {
    render(
      <main>
        <p>sibling</p>
        <PanelBoundary id="x" title="Panel title" question="A question?">
          <Thrower />
        </PanelBoundary>
      </main>,
    );
    expect(screen.getByText("sibling")).not.toBeNull();
    expect(screen.getByRole("heading", { name: "Panel title" })).not.toBeNull();
    expect(screen.getByText("This section could not be shown.")).not.toBeNull();
    expect(screen.queryByText("boom")).toBeNull();
  });
});
