import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { mockReport } from "../../test/fixture";
import { ExposuresPanel } from "./ExposuresPanel";
import { narrowTicks, RollingPanel } from "./RollingPanel";
import { ReturnPanel } from "./ReturnPanel";

vi.mock("../charts/echartsCore", () => ({
  init: vi.fn(() => ({
    group: "",
    setOption: vi.fn(),
    resize: vi.fn(),
    dispose: vi.fn(),
    isDisposed: vi.fn(() => false),
    on: vi.fn(),
    off: vi.fn(),
    getOption: vi.fn(() => ({})),
    dispatchAction: vi.fn(),
  })),
  connect: vi.fn(),
  disconnect: vi.fn(),
}));

describe("rolling panel accessibility (A1, A6)", () => {
  it("hides the whole axis row from assistive technology, not only one cell", () => {
    const { container } = render(<RollingPanel report={mockReport} win={252} onWinChange={vi.fn()} />);
    const row = container.querySelector("tfoot tr.axis-row");
    expect(row?.getAttribute("aria-hidden")).toBe("true");
    // The cell itself needs no flag of its own: the row carries it for every child.
    expect(row?.querySelector("td.axis")?.getAttribute("aria-hidden")).toBeNull();
  });

  it("repeats the Middle 80% detail as text, not only as a title", () => {
    const { container } = render(<RollingPanel report={mockReport} win={252} onWinChange={vi.fn()} />);
    const cell = container.querySelector("tbody tr td.range") as HTMLElement;
    const hidden = cell.querySelector(".vh");
    expect(hidden?.textContent).toMatch(/Spread \d\.\d{3}, lowest [+−]\d\.\d{3}, highest [+−]\d\.\d{3}, above zero in \d+% of windows/);
    expect(cell.getAttribute("title")).toContain("Spread");
  });
});

describe("narrowTicks (DF8)", () => {
  it("keeps the first and the last label and the major ones that fit", () => {
    const ticks = [
      { x: 6, major: false },
      { x: 30, major: true },
      { x: 55, major: false },
      { x: 80, major: true },
      { x: 97, major: false },
    ];
    expect([...narrowTicks(ticks)].sort()).toEqual([0, 1, 4]);
  });

  it("drops a major label that crowds the last one and keeps both ends", () => {
    const ticks = [
      { x: 4, major: false },
      { x: 50, major: true },
      { x: 90, major: true },
      { x: 98, major: false },
    ];
    expect([...narrowTicks(ticks)].sort()).toEqual([0, 1, 3]);
  });

  it("copes with one tick and with none", () => {
    expect([...narrowTicks([{ x: 50, major: false }])]).toEqual([0]);
    expect([...narrowTicks([])]).toEqual([]);
  });

  it("marks kept labels with a keep class in the panel", () => {
    const { container } = render(<RollingPanel report={mockReport} win={252} onWinChange={vi.fn()} />);
    const labels = Array.from(container.querySelectorAll("tfoot .xl"));
    expect(labels.length).toBeGreaterThan(1);
    expect(labels[0]?.classList.contains("keep")).toBe(true);
    expect(labels[labels.length - 1]?.classList.contains("keep")).toBe(true);
  });
});

describe("Significant column header (A2)", () => {
  it("keeps the full word in the header and hides only the abbreviation", () => {
    for (const ui of [<ExposuresPanel key="e" report={mockReport} />, <ReturnPanel key="r" report={mockReport} />]) {
      const { container, unmount } = render(ui);
      const th = screen.getAllByRole("columnheader", { name: /Significant/ })[0] as HTMLElement;
      expect(th.querySelector(".long")?.textContent).toBe("Significant");
      expect(th.querySelector(".long")?.closest("[aria-hidden='true']")).toBeNull();
      expect(th.querySelector(".short")?.getAttribute("aria-hidden")).toBe("true");
      expect(container.querySelector("thead")).not.toBeNull();
      unmount();
    }
  });
});
