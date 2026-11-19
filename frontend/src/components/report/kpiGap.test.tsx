import { render } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it, vi } from "vitest";
import { cloneReport } from "../../test/fixture";
import { ReportView } from "./ReportView";

const css = readFileSync(resolve(process.cwd(), "src/styles/report.css"), "utf8");

/** Body of the first rule that starts a line with `selector {`. */
function rule(selector: string): string {
  const at = css.indexOf(`\n${selector} {`);
  expect(at, selector).toBeGreaterThanOrEqual(0);
  const open = css.indexOf("{", at);
  return css.slice(open + 1, css.indexOf("}", open));
}

/**
 * Review DF7 asked that no block of the report touches the one before it, whatever is omitted.
 * Dashboard v2 spaces every block with the gap of the report grid, so an omitted panel (the
 * equation and the KPI strip are gone; an empty optional section renders nothing) never leaves
 * two blocks without space between them.
 */
describe("gap between the blocks of the report (review DF7)", () => {
  it("comes from the grid gap of the report region, not from per-block margins", () => {
    expect(rule(".report-region")).toMatch(/display:\s*grid/);
    expect(rule(".report-region")).toMatch(/gap:\s*var\(--gap\)/);
    expect(rule(".panel")).not.toMatch(/(^|[\s;])margin(-top)?:/);
  });

  it("puts every block, the notice and the empty states included, in the grid", () => {
    const r = cloneReport();
    r.regression.status = "insufficient_data";
    const { container } = render(<ReportView report={r} downloadHref="#" win={null} onWinChange={vi.fn()} />);
    const main = container.querySelector("main.report-region") as HTMLElement;
    const ids = Array.from(main.querySelectorAll(":scope > [id]")).map((el) => el.id);
    expect(ids.slice(0, 3)).toEqual(["header", "notice", "price"]);
    expect(main.querySelector(":scope > #exposures .empty")).not.toBeNull();
  });
});
