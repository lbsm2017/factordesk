import { render } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { NO_PROGRESS, runView } from "../../api/runProgress";
import { Shell } from "../shell/Shell";
import { PlaceholderPage } from "./PlaceholderPage";
import { PANELS } from "./panelRegistry";
import { placeholderPanels } from "./placeholders";
import type { ReportMode } from "./placeholders";

const css = readFileSync(resolve(process.cwd(), "src/styles/frame.css"), "utf8");
const MODES: ReportMode[] = ["ticker", "track", "portfolio"];
const view = runView(NO_PROGRESS, ["prices", "factors", "models", "sections"]);

describe("the placeholder lists", () => {
  it.each(MODES)("%s: every panel is in the registry, in the registry's order, without Summary or the Colophon", (mode) => {
    const position = new Map(PANELS.map((p) => [p.name, p.position]));
    const names = placeholderPanels(mode).map((p) => p.name);
    for (const name of names) expect(position.has(name), name).toBe(true);
    const order = names.map((n) => position.get(n) ?? 0);
    expect(order).toEqual([...order].sort((a, b) => a - b));
    expect(names).not.toContain("summary");
    expect(names).not.toContain("colophon");
  });

  it("the ticker list has the titles and heights of the spec", () => {
    const rows = placeholderPanels("ticker").map((p) => [p.title, p.height]);
    expect(rows).toEqual([
      ["Price", 420],
      ["Drawdown", 420],
      ["Tail risk", 360],
      ["Factor exposures", 520],
      ["Alpha across models", 300],
      ["World beta", 300],
      ["Macro sensitivities", 420],
      ["Energy & carbon", 420],
      ["Return sources", 560],
      ["Risk sources", 560],
      ["Exposure over time", 600],
      ["Beyond the factors", 280],
      ["Tracked day by day", 480],
      ["Adjusted for noise", 480],
      ["Timing-adjusted betas (lead-lag)", 320],
      ["Fragility", 320],
      ["Data and audit", 560],
      ["Regression detail", 900],
    ]);
  });

  it("the portfolio list adds Holdings after Price; the track record list is the eight of the spec", () => {
    expect(placeholderPanels("portfolio").map((p) => p.title).slice(0, 3)).toEqual(["Price", "Holdings", "Drawdown"]);
    expect(placeholderPanels("portfolio").find((p) => p.title === "Holdings")?.height).toBe(520);
    expect(placeholderPanels("track").map((p) => p.title)).toEqual([
      "Growth of 100",
      "Factor exposures",
      "Return sources",
      "Risk sources",
      "Exposure over time",
      "Data and audit",
      "Regression detail",
    ]);
  });
});

describe("PlaceholderPage", () => {
  it("holds the header, the run card, and one aria-hidden panel per placeholder with its real title", () => {
    const { container } = render(<PlaceholderPage mode="ticker" title="SPY" view={view} />);
    expect(container.querySelector("main")?.getAttribute("aria-busy")).toBe("true");
    expect(container.querySelector("h1 .ticker")?.textContent).toBe("SPY");
    expect(container.querySelectorAll(".abar > div")).toHaveLength(4);
    expect(container.querySelector(".run-card h2")?.textContent).toBe("Building the report for SPY");
    const panels = container.querySelectorAll("section.ph-panel");
    expect(panels).toHaveLength(placeholderPanels("ticker").length);
    for (const panel of panels) {
      expect(panel.getAttribute("aria-hidden")).toBe("true");
      expect(panel.id).toBe("");
      expect(panel.querySelector("[id]")).toBeNull();
    }
    expect([...container.querySelectorAll("section.ph-panel h2")].slice(0, 2).map((h) => h.textContent)).toEqual(["Price", "Drawdown"]);
  });

  it("pairs Price with Drawdown as the real panels do", () => {
    const { container } = render(<PlaceholderPage mode="ticker" title="SPY" view={view} />);
    expect(container.querySelector('[data-placeholder="price"]')?.classList.contains("s-7")).toBe(true);
    expect(container.querySelector('[data-placeholder="performance"]')?.classList.contains("s-5")).toBe(true);
  });

  it("gives the sidebar section list nothing to list", () => {
    const { container } = render(
      <Shell sidebar={<p>controls</p>} ticker="SPY">
        <PlaceholderPage mode="ticker" title="SPY" view={view} />
      </Shell>,
    );
    expect(container.querySelector("aside#sidebar")).not.toBeNull();
    expect(container.querySelector("main")?.closest("#report")).not.toBeNull();
    expect(container.querySelectorAll("nav a")).toHaveLength(0);
  });

  it("sets each final height through one custom property, in the spec order of the table", () => {
    const { container } = render(<PlaceholderPage mode="ticker" title="SPY" view={view} />);
    const heights = [...container.querySelectorAll<HTMLElement>("section.ph-panel")].map((p) => p.style.getPropertyValue("--h"));
    expect(heights[0]).toBe("420px");
    expect(heights.at(-1)).toBe("900px");
    expect(css).toMatch(/\.ph-panel\s*\{[^}]*min-height:\s*var\(--h/);
  });
});
