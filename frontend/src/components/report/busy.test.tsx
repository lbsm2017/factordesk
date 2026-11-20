import { render, screen } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { act } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { mockReport } from "../../test/fixture";
import { ReportView } from "./ReportView";

const css = readFileSync(resolve(process.cwd(), "src/styles/frame.css"), "utf8");

describe("a re-run keeps the old figures (Sprint 4 mockup 1, frame e)", () => {
  it("no rule blanks the ticker, the analysis bar or the summary figures while a request runs", () => {
    expect(css).not.toMatch(/\[aria-busy="true"\]/);
  });

  it("dims the old report and makes it inert, with the figures still in the page", () => {
    const { container } = render(<ReportView report={mockReport} downloadHref="#" win={null} onWinChange={vi.fn()} busy dim />);
    const region = screen.getByTestId("report-region");
    expect(region.getAttribute("aria-busy")).toBe("true");
    expect(region.hasAttribute("inert")).toBe(true);
    expect(region.classList.contains("dim")).toBe(true);
    expect(container.querySelector(".ticker")?.textContent).toBe(mockReport.ticker);
    expect(container.querySelectorAll(".abar dd")[0]?.textContent).not.toBe("");
  });

  it("is plain and active once the request is done", () => {
    render(<ReportView report={mockReport} downloadHref="#" win={null} onWinChange={vi.fn()} />);
    const region = screen.getByTestId("report-region");
    expect(region.getAttribute("aria-busy")).toBe("false");
    expect(region.hasAttribute("inert")).toBe(false);
    expect(region.classList.contains("dim")).toBe(false);
  });
});

function matchMedia(reduced: boolean) {
  vi.stubGlobal("matchMedia", (query: string) => ({
    matches: reduced && query.includes("prefers-reduced-motion"),
    media: query,
    addEventListener: () => undefined,
    removeEventListener: () => undefined,
  }));
}

describe("the reveal (Sprint 4 mockup 1, frame d)", () => {
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it("marks the region while the panels appear, then clears it and the busy flag", () => {
    vi.useFakeTimers();
    matchMedia(false);
    render(<ReportView report={mockReport} downloadHref="#" win={null} onWinChange={vi.fn()} reveal />);
    const region = screen.getByTestId("report-region");
    expect(region.classList.contains("reveal")).toBe(true);
    expect(region.getAttribute("aria-busy")).toBe("true");
    act(() => {
      vi.advanceTimersByTime(750);
    });
    expect(region.classList.contains("reveal")).toBe(false);
    expect(region.getAttribute("aria-busy")).toBe("false");
  });

  it("with reduced motion every panel appears at once: no reveal class, not busy", () => {
    matchMedia(true);
    render(<ReportView report={mockReport} downloadHref="#" win={null} onWinChange={vi.fn()} reveal />);
    const region = screen.getByTestId("report-region");
    expect(region.classList.contains("reveal")).toBe(false);
    expect(region.getAttribute("aria-busy")).toBe("false");
  });

  it("no reveal without the prop (a cached report opens at once)", () => {
    render(<ReportView report={mockReport} downloadHref="#" win={null} onWinChange={vi.fn()} />);
    expect(screen.getByTestId("report-region").classList.contains("reveal")).toBe(false);
  });
});
