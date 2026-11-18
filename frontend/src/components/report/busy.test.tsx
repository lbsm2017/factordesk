import { render } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it, vi } from "vitest";
import { mockReport } from "../../test/fixture";
import { ReportView } from "./ReportView";

const css = readFileSync(resolve(process.cwd(), "src/styles/frame.css"), "utf8");

/** The selectors of the rule that blanks figures while a request runs. */
function busySelectors(): string[] {
  const block = /(\[aria-busy="true"\][^{]*)\{/.exec(css);
  expect(block, "busy rule").not.toBeNull();
  return (block?.[1] ?? "")
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
}

describe("busy placeholders (review S3)", () => {
  it("blank the ticker, the KPI values and notes, and the equation terms and annotations", () => {
    const selectors = busySelectors();
    expect(selectors.map((s) => s.replace('[aria-busy="true"] ', ""))).toEqual(
      expect.arrayContaining([".ticker", ".kpis .kpi .v", ".kpis .kpi .n", ".model .term .m", ".model .term .ann span"]),
    );
    const { container } = render(<ReportView report={mockReport} downloadHref="#" win={null} onWinChange={vi.fn()} busy />);
    for (const selector of selectors) {
      expect(container.querySelectorAll(selector).length, selector).toBeGreaterThan(0);
    }
  });

  it("match nothing once the request is done", () => {
    const { container } = render(<ReportView report={mockReport} downloadHref="#" win={null} onWinChange={vi.fn()} />);
    for (const selector of busySelectors()) expect(container.querySelectorAll(selector), selector).toHaveLength(0);
  });
});
