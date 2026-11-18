import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { BarCell, MIN_CAP_SPAN_PCT, position } from "./BarCell";

const base = { lo: -1, hi: 1, ticks: [-1, 0, 1] as const, fill: "sign" as const, title: "t" };

describe("BarCell", () => {
  it("places marks with percentage coordinates", () => {
    expect(position(0, -1, 1)).toBe(50);
    expect(position(0.5, -1, 1)).toBe(75);
  });

  it("draws a positive bar to the right of the zero line at 36% of the row height", () => {
    const { container } = render(<BarCell {...base} value={0.5} />);
    const rect = container.querySelector("rect.pos");
    expect(rect?.getAttribute("x")).toBe("50%");
    expect(rect?.getAttribute("width")).toBe("25%");
    expect(rect?.getAttribute("height")).toBe("36%");
    expect(container.querySelector("line.zero")?.getAttribute("x1")).toBe("50%");
    expect(container.querySelectorAll("line.grid")).toHaveLength(2);
  });

  it("draws a negative bar to the left, faded when not significant", () => {
    const { container } = render(<BarCell {...base} value={-0.5} faded />);
    const rect = container.querySelector("rect.neg.faded");
    expect(rect?.getAttribute("x")).toBe("25%");
    expect(rect?.getAttribute("width")).toBe("25%");
  });

  it("drops whisker caps for an interval narrower than 1.2% of the plot width", () => {
    const wide = render(<BarCell {...base} value={0.5} ci={{ low: 0.4, high: 0.6 }} />);
    expect(wide.container.querySelectorAll("line.ci")).toHaveLength(3);
    wide.unmount();
    // The domain spans 2 units, so 1.2% of the width is 0.024 units; this interval is 0.02 wide.
    const narrow = render(<BarCell {...base} value={0.5} ci={{ low: 0.5, high: 0.52 }} />);
    expect(MIN_CAP_SPAN_PCT).toBe(1.2);
    expect(narrow.container.querySelectorAll("line.ci")).toHaveLength(1);
  });

  it("draws the average-beta diamond on the centre line", () => {
    const { container } = render(<BarCell {...base} value={0.5} marker={0.5} />);
    const svg = container.querySelector("svg.avgm");
    expect(svg?.getAttribute("x")).toBe("75%");
    expect(svg?.getAttribute("y")).toBe("50%");
  });

  it("uses the hatch class for residual and a total rule with a cap", () => {
    const hatched = render(<BarCell {...base} fill="hatch" value={0.2} />);
    expect(hatched.container.querySelector("rect.hatch")).not.toBeNull();
    hatched.unmount();
    const total = render(<BarCell {...base} value={null} total={0.5} />);
    expect(total.container.querySelector("line.total-line")).not.toBeNull();
    expect(total.container.querySelector("line.total-cap")?.getAttribute("x1")).toBe("75%");
  });

  it("hides itself from assistive technology and carries a title", () => {
    const { container } = render(<BarCell {...base} value={0.1} title="Mkt-RF: beta +0.100" />);
    expect(container.querySelector("svg")?.getAttribute("aria-hidden")).toBe("true");
    expect(container.querySelector("title")?.textContent).toBe("Mkt-RF: beta +0.100");
  });
});
