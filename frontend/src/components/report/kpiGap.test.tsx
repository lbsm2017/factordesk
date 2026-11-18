import { render } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it, vi } from "vitest";
import { cloneReport } from "../../test/fixture";
import { ReportView } from "./ReportView";

const css = readFileSync(resolve(process.cwd(), "src/styles/frame.css"), "utf8");

/** Selectors of the rule that spaces the KPI strip from what precedes it. */
function gapSelectors(): string[] {
  const rule = /((?:[.\w#]+ \+ \.kpis,?\s*)+)\{([^}]*)\}/.exec(css);
  expect(rule?.[2]).toMatch(/margin-top:\s*var\(--s-4\)/);
  return (rule?.[1] ?? "").split(",").map((s) => s.trim()).filter(Boolean);
}

describe("gap between the notice and the KPI empty state (review DF7)", () => {
  it("applies when the regression failed, the equation is omitted and the KPI strip follows the notice", () => {
    const r = cloneReport();
    r.regression.status = "insufficient_data";
    const { container } = render(<ReportView report={r} downloadHref="#" win={null} onWinChange={vi.fn()} />);
    expect(container.querySelector("#equation")).toBeNull();
    expect(container.querySelector("#kpis .empty")).not.toBeNull();
    expect(container.querySelector("#kpis")?.previousElementSibling?.id).toBe("notice");
    const matches = gapSelectors().filter((s) => container.querySelector(s) !== null);
    expect(matches).toContain(".notice + .kpis");
  });

  it("also applies when there is no notice, so the strip never touches the header", () => {
    const r = cloneReport();
    r.regression.status = "insufficient_data";
    r.warnings = [];
    r.quality_gate.fired = false;
    const { container } = render(<ReportView report={r} downloadHref="#" win={null} onWinChange={vi.fn()} />);
    expect(container.querySelector("#notice")).toBeNull();
    expect(container.querySelector("#kpis")?.previousElementSibling?.id).toBe("header");
    expect(gapSelectors().filter((s) => container.querySelector(s) !== null)).toContain(".masthead + .kpis");
  });
});
