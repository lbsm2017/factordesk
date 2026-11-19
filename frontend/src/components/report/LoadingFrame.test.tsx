import { render } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { Shell } from "../shell/Shell";
import { LoadingFrame } from "./LoadingFrame";

const css = readFileSync(resolve(process.cwd(), "src/styles/frame.css"), "utf8");

describe("LoadingFrame (dashboard v2)", () => {
  it("holds the header, the analysis bar and eight panels, with the ticker as the page heading", () => {
    const { container } = render(<LoadingFrame ticker="SPY" />);
    expect(container.querySelector("h1 .ticker")?.textContent).toBe("SPY");
    expect(container.querySelectorAll(".abar > div")).toHaveLength(4);
    expect(container.querySelectorAll("section.sk-panel")).toHaveLength(8);
    expect(container.querySelector("main")?.getAttribute("aria-busy")).toBe("true");
    expect(container.querySelector('[role="status"]')?.textContent).toBe("Loading the report for SPY.");
  });

  it("uses one set of panel heights, with no width tiers", () => {
    expect(css).not.toMatch(/@media/);
    expect(css).not.toMatch(/--sk-/);
    const { container } = render(<LoadingFrame ticker="SPY" />);
    for (const el of container.querySelectorAll("section.sk-panel")) {
      const cls = [...el.classList].find((c) => c !== "sk-panel" && c !== "panel") as string;
      expect(css, cls).toMatch(new RegExp(String.raw`\.${cls}\s*\{\s*min-height:\s*\d+px;\s*\}`));
    }
  });

  it("sits in the shell beside the sidebar", () => {
    const { container } = render(
      <Shell sidebar={<p>controls</p>} ticker="SPY">
        <LoadingFrame ticker="SPY" />
      </Shell>,
    );
    const main = container.querySelector("main") as HTMLElement;
    expect(container.querySelector("aside#sidebar")).not.toBeNull();
    expect(main.closest("#report")).not.toBeNull();
  });
});
