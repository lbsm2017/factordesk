import { render, screen } from "@testing-library/react";
import type { ReactElement } from "react";
import { describe, expect, it, vi } from "vitest";
import { mockReport } from "../../test/fixture";
import { EmptyState } from "./EmptyState";
import { Panel } from "./Panel";
import { ReportView } from "./ReportView";
import { ReturnPanel } from "./ReturnPanel";
import { RiskPanel } from "./RiskPanel";
import { RollingPanel } from "./RollingPanel";

const report = mockReport;

const stubs: [string, string, () => ReactElement][] = [
  ["ReturnPanel", "Where the return came from", () => <ReturnPanel report={report} />],
  ["RiskPanel", "Where the risk comes from", () => <RiskPanel report={report} />],
  ["RollingPanel", "Exposure over time", () => <RollingPanel report={report} win={252} onWinChange={vi.fn()} />],
];

describe("stubs", () => {
  it.each(stubs)("%s renders a titled, empty Panel", (_name, title, make) => {
    const { container } = render(make());
    expect(screen.getByRole("heading", { level: 2, name: title })).toBeTruthy();
    const section = container.querySelector("section.panel");
    expect(section).not.toBeNull();
    expect(section?.querySelector(".foot")).toBeNull();
    expect(section?.querySelector("table")).toBeNull();
  });
});

describe("ReportView", () => {
  it("places every report panel in order inside one region", () => {
    const { container } = render(<ReportView report={report} downloadHref="#" win={null} onWinChange={vi.fn()} />);
    const ids = Array.from(container.querySelectorAll("main > [id]")).map((el) => el.id);
    expect(ids).toEqual([
      "header",
      "notice",
      "equation",
      "kpis",
      "gate",
      "price",
      "exposures",
      "returns",
      "risk",
      "rolling",
      "data",
      "regression-detail",
      "colophon",
    ]);
    expect(container.querySelector("main")?.getAttribute("aria-busy")).toBe("false");
  });

  it("marks the region busy while a request runs", () => {
    const { container } = render(
      <ReportView report={report} downloadHref="#" win={null} onWinChange={vi.fn()} busy />,
    );
    expect(container.querySelector("main")?.getAttribute("aria-busy")).toBe("true");
  });
});

describe("Panel", () => {
  it("shows the footnote and the folded method detail", () => {
    const { container } = render(
      <Panel id="x" title="T" question="Q?" reading="Reading." footnote="Note." how="Method.">
        <p>body</p>
      </Panel>,
    );
    expect(screen.getByText("Q?")).toBeTruthy();
    expect(screen.getByText("Reading.")).toBeTruthy();
    expect(container.querySelector(".foot > p")?.textContent).toBe("Note.");
    expect(container.querySelector("details.how summary")?.textContent).toBe("How this is computed");
  });

  it("replaces the body and drops the footnote when the statistic is not ok", () => {
    const { container } = render(
      <Panel id="x" title="T" footnote="Note." empty={{ reason: "Too few days.", action: "Choose Full history." }}>
        <p>body</p>
      </Panel>,
    );
    expect(screen.getByText("Too few days.")).toBeTruthy();
    expect(screen.getByText("Choose Full history.")).toBeTruthy();
    expect(screen.queryByText("body")).toBeNull();
    expect(container.querySelector(".foot")).toBeNull();
  });

  it("EmptyState shows the reason and one next step", () => {
    const { container } = render(<EmptyState reason="Why." action="Do this." />);
    expect(container.querySelector(".empty-what")?.textContent).toBe("Why.");
    expect(container.querySelector(".empty-do")?.textContent).toBe("Do this.");
  });
});
