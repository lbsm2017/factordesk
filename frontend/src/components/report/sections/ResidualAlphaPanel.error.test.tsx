import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cloneReport } from "../../../test/fixture";
import { withSection } from "../../../test/sectionFixtures";
import { ResidualAlphaPanel } from "./ResidualAlphaPanel";

vi.mock("./ResidualAlphaBody", () => ({
  ResidualAlphaBody: () => {
    throw new Error("body failed");
  },
}));

describe("ResidualAlphaPanel when its body fails", () => {
  beforeEach(() => {
    vi.spyOn(console, "error").mockImplementation(() => undefined);
  });
  afterEach(() => vi.restoreAllMocks());

  it("shows a plain notice in its own frame and keeps the rest of the page", async () => {
    render(
      <main>
        <p>sibling</p>
        <ResidualAlphaPanel report={withSection(cloneReport(), "residual")} />
      </main>,
    );
    expect(await screen.findByText("This section could not be shown.")).not.toBeNull();
    expect(screen.getByRole("heading", { name: "Beyond the factors" })).not.toBeNull();
    expect(screen.getByText("sibling")).not.toBeNull();
  });
});
