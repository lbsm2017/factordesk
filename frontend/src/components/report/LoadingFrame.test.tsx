import { render } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { LoadingFrame } from "./LoadingFrame";

const css = readFileSync(resolve(process.cwd(), "src/styles/frame.css"), "utf8");

/** Every custom property a loading block takes its final height from. */
const VARS = [
  "head",
  "notice",
  "eq",
  "kpis",
  "price",
  "exposures",
  "returns",
  "risk",
  "rolling",
  "data",
  "regression",
  "colophon",
].map((name) => `--sk-${name}`);

/** The `:root { ... }` declarations of the base rule and of each width tier. */
function tiers(): string[] {
  return [...css.matchAll(/:root\s*\{([^}]*)\}/g)].map((m) => m[1] ?? "");
}

describe("LoadingFrame (layout shift, review S2)", () => {
  it("holds a block for the header, notice, equation, KPI cells, seven panels and the colophon", () => {
    const { container } = render(<LoadingFrame ticker="SPY" />);
    for (const cls of ["sk-head", "sk-notice", "sk-eq", "sk-kpis", "sk-colophon"]) {
      expect(container.querySelector(`.${cls}`), cls).not.toBeNull();
    }
    expect(container.querySelectorAll("section.sk-panel")).toHaveLength(7);
    expect(container.querySelectorAll(".kpi")).toHaveLength(5);
    // The KPI cells carry a note line, as the real strip does, so their height matches.
    expect(container.querySelectorAll(".kpi .n")).toHaveLength(5);
    // The equation block reuses the report's own margins.
    expect(container.querySelector(".sk-eq")?.classList.contains("model")).toBe(true);
  });

  it("sets the final height of every block in the widest tier and in each narrower tier", () => {
    const all = tiers();
    expect(all.length).toBeGreaterThanOrEqual(5);
    for (const [i, decls] of all.entries()) {
      for (const v of VARS) expect(decls, `tier ${i} lacks ${v}`).toMatch(new RegExp(String.raw`${v}:\s*\d+px`));
    }
  });

  it("gives every placeholder a min-height from its variable, so content can grow past it", () => {
    const { container } = render(<LoadingFrame ticker="SPY" />);
    const panelClasses = [...container.querySelectorAll("section.sk-panel")].map(
      (el) => [...el.classList].find((c) => c !== "sk-panel" && c !== "panel") as string,
    );
    for (const cls of ["sk-head", "sk-notice", "sk-eq", "sk-kpis", "sk-colophon", ...panelClasses]) {
      expect(css, cls).toMatch(new RegExp(String.raw`\.${cls}\b[^{}]*\{[^}]*min-height:\s*var\(--${cls}\)`));
    }
  });
});
