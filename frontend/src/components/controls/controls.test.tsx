import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { FactorDataStatus } from "../../api/types";
import { EMPTY_URL_STATE } from "../../state/url";
import type { UrlState } from "../../state/url";
import { cloneReport, mockReport } from "../../test/fixture";
import { mockRanges, mockStatus, mockTickers } from "../../test/mockApi";
import { AnalysedRange, rangeLine } from "./AnalysedRange";
import { ControlsStrip } from "./ControlsStrip";
import type { ControlsStripProps } from "./ControlsStrip";
import { CustomRange } from "./CustomRange";
import { FactorDataLine } from "./FactorDataLine";
import { RangeChips } from "./RangeChips";
import { TickerSearch } from "./TickerSearch";

function search(props: Partial<React.ComponentProps<typeof TickerSearch>> = {}) {
  const onQueryChange = vi.fn();
  const onSubmit = vi.fn();
  render(
    <TickerSearch
      value=""
      recent={["SPY", "QQQ"]}
      suggestions={[]}
      error={null}
      onQueryChange={onQueryChange}
      onSubmit={onSubmit}
      {...props}
    />,
  );
  const input = screen.getByRole("combobox", { name: "Ticker" }) as HTMLInputElement;
  return { input, onQueryChange, onSubmit };
}

const options = () => screen.queryAllByRole("option").map((o) => o.textContent);

describe("TickerSearch", () => {
  it("lists the recent tickers when the empty field has focus", () => {
    const { input } = search();
    expect(options()).toEqual([]);
    fireEvent.focus(input);
    expect(options()).toEqual(["SPYrecent", "QQQrecent"]);
    expect(screen.getByRole("listbox", { name: "Recent tickers" })).toBeTruthy();
  });

  it("lists server suggestions for typed text, upper-cased, and reports the query", () => {
    const { input, onQueryChange } = search({ suggestions: mockTickers });
    fireEvent.focus(input);
    fireEvent.change(input, { target: { value: "sp" } });
    expect(input.value).toBe("SP");
    expect(onQueryChange).toHaveBeenLastCalledWith("SP");
    expect(options()).toEqual(["SPYfetched 13 Nov 2026", "SPXLfetched 10 Nov 2026"]);
  });

  it("submits the text of the field on Enter", () => {
    const { input, onSubmit } = search();
    fireEvent.change(input, { target: { value: "brk-b" } });
    fireEvent.keyDown(input, { key: "Enter" });
    expect(onSubmit).toHaveBeenCalledTimes(1);
    expect(onSubmit).toHaveBeenCalledWith("BRK-B");
  });

  it("submits from the Factor it button", () => {
    const { input, onSubmit } = search();
    fireEvent.change(input, { target: { value: "spy" } });
    fireEvent.click(screen.getByRole("button", { name: "Factor it" }));
    expect(onSubmit).toHaveBeenCalledWith("SPY");
  });

  it("submits a chosen suggestion, by click and by arrow keys with Enter", () => {
    const { input, onSubmit } = search({ suggestions: mockTickers });
    fireEvent.focus(input);
    fireEvent.change(input, { target: { value: "SP" } });
    fireEvent.click(screen.getByRole("option", { name: /SPXL/ }));
    expect(onSubmit).toHaveBeenLastCalledWith("SPXL");

    fireEvent.change(input, { target: { value: "SP" } });
    fireEvent.keyDown(input, { key: "ArrowDown" });
    fireEvent.keyDown(input, { key: "ArrowDown" });
    fireEvent.keyDown(input, { key: "Enter" });
    expect(onSubmit).toHaveBeenLastCalledWith("SPXL");
    expect(onSubmit).toHaveBeenCalledTimes(2);
  });

  it("closes the list on Escape and keeps the text", () => {
    const { input } = search();
    fireEvent.focus(input);
    expect(options()).toHaveLength(2);
    fireEvent.keyDown(input, { key: "Escape" });
    expect(options()).toEqual([]);
    fireEvent.change(input, { target: { value: "AB" } });
    fireEvent.keyDown(input, { key: "Escape" });
    expect(input.value).toBe("AB");
  });

  it("focuses the field on /, unless focus is already in a text field", () => {
    const { input } = search();
    expect(document.activeElement).not.toBe(input);
    fireEvent.keyDown(document.body, { key: "/" });
    expect(document.activeElement).toBe(input);

    const other = document.createElement("input");
    document.body.append(other);
    other.focus();
    const event = new KeyboardEvent("keydown", { key: "/", bubbles: true, cancelable: true });
    other.dispatchEvent(event);
    expect(event.defaultPrevented).toBe(false);
    expect(document.activeElement).toBe(other);
    other.remove();
  });

  it("shows an inline sentence for an error and marks the field invalid", () => {
    const { input } = search({ error: "BRK B is not a valid ticker." });
    expect(screen.getByRole("alert").textContent).toBe("BRK B is not a valid ticker.");
    expect(input.getAttribute("aria-invalid")).toBe("true");
  });

  it("takes focus on mount when asked to (landing)", () => {
    const { input } = search({ focusOnMount: true });
    expect(document.activeElement).toBe(input);
  });

  it("follows the ticker in the URL", () => {
    const { input } = search({ value: "SPY" });
    expect(input.value).toBe("SPY");
  });
});

describe("RangeChips", () => {
  it("renders native radios in a fieldset with the hidden legend Date range", () => {
    render(<RangeChips options={mockRanges("SPY").options} selected="FULL" onSelect={vi.fn()} />);
    const group = screen.getByRole("group", { name: "Date range" });
    const radios = within(group).getAllByRole("radio");
    expect(radios.map((r) => (r as HTMLInputElement).value)).toEqual(["3Y", "5Y", "FULL"]);
    expect(screen.getByRole("radio", { name: "Full history" })).toHaveProperty("checked", true);
  });

  it("disables an unavailable preset and enables the others", () => {
    const onSelect = vi.fn();
    render(<RangeChips options={mockRanges("SPY").options} selected={null} onSelect={onSelect} />);
    const five = screen.getByRole("radio", { name: "5Y" }) as HTMLInputElement;
    expect(five.disabled).toBe(true);
    expect(five.closest("label")?.className).toContain("off");
    fireEvent.click(screen.getByRole("radio", { name: "3Y" }));
    expect(onSelect).toHaveBeenCalledWith("3Y");
  });

  it("leaves every chip usable while the options are loading", () => {
    render(<RangeChips options={undefined} selected={null} onSelect={vi.fn()} />);
    for (const radio of screen.getAllByRole("radio")) expect((radio as HTMLInputElement).disabled).toBe(false);
  });
});

describe("CustomRange", () => {
  const dates = (inputs: HTMLElement[]) => inputs.map((i) => (i as HTMLInputElement).value);

  it("fills From and To and sets max to the last factor date", () => {
    render(<CustomRange start="2024-08-08" end="2026-09-30" max="2026-09-30" onCommit={vi.fn()} />);
    const from = screen.getByLabelText("From") as HTMLInputElement;
    const to = screen.getByLabelText("To") as HTMLInputElement;
    expect(dates([from, to])).toEqual(["2024-08-08", "2026-09-30"]);
    expect(from.max).toBe("2026-09-30");
    expect(to.max).toBe("2026-09-30");
  });

  it("commits a complete, valid pair on change", () => {
    const onCommit = vi.fn();
    render(<CustomRange start="2024-08-08" end="2026-09-30" max="2026-09-30" onCommit={onCommit} />);
    fireEvent.change(screen.getByLabelText("From"), { target: { value: "2025-01-02" } });
    expect(onCommit).toHaveBeenCalledWith("2025-01-02", "2026-09-30");
  });

  it("sends nothing for an incomplete date", () => {
    const onCommit = vi.fn();
    render(<CustomRange start="2024-08-08" end="2026-09-30" max={null} onCommit={onCommit} />);
    fireEvent.change(screen.getByLabelText("From"), { target: { value: "" } });
    expect(onCommit).not.toHaveBeenCalled();
  });

  it("explains a start after the end and sends nothing", () => {
    const onCommit = vi.fn();
    render(<CustomRange start="2024-08-08" end="2026-09-30" max="2026-09-30" onCommit={onCommit} />);
    fireEvent.change(screen.getByLabelText("From"), { target: { value: "2026-10-01" } });
    expect(onCommit).not.toHaveBeenCalled();
    expect(screen.getByRole("alert").textContent).toContain("is after");
  });

  it("explains a date after the factor data and sends nothing", () => {
    const onCommit = vi.fn();
    render(<CustomRange start="2024-08-08" end="2026-09-30" max="2026-09-30" onCommit={onCommit} />);
    fireEvent.change(screen.getByLabelText("To"), { target: { value: "2026-12-01" } });
    expect(onCommit).not.toHaveBeenCalled();
    expect(screen.getByRole("alert").textContent).toBe(
      "Factor data ends 30 Sep 2026, so 1 Dec 2026 cannot be chosen. Choose an earlier date.",
    );
  });

  it("follows new props, for example when a chip fills the dates", () => {
    const { rerender } = render(<CustomRange start="2024-08-08" end="2026-09-30" max={null} onCommit={vi.fn()} />);
    rerender(<CustomRange start="2023-09-30" end="2026-09-30" max={null} onCommit={vi.fn()} />);
    expect((screen.getByLabelText("From") as HTMLInputElement).value).toBe("2023-09-30");
  });
});

describe("AnalysedRange", () => {
  it("is a polite live region that is present before any report", () => {
    render(<AnalysedRange report={undefined} />);
    const label = screen.getByText("No range analysed yet.");
    expect(label.getAttribute("aria-live")).toBe("polite");
  });

  it("uses the static report's range-line wording", () => {
    render(<AnalysedRange report={mockReport} />);
    const label = document.querySelector("[aria-live='polite']");
    expect(label?.textContent).toBe(
      "Analysed 8 Aug 2024 to 30 Sep 2026, 559 trading days. The last 32 price days are charted but not analysed.",
    );
    expect(label?.querySelector("b")?.textContent).toBe("Analysed 8 Aug 2024 to 30 Sep 2026, 559 trading days.");
  });

  it("words one price day and an untouched tail", () => {
    const report = cloneReport();
    report.data.uncovered.n = 1;
    expect(rangeLine(report).tail).toContain("The last price day is charted but not analysed.");
    report.data.uncovered.n = 0;
    expect(rangeLine(report).tail).not.toContain("The last");
  });
});

describe("FactorDataLine", () => {
  it("says where the factor data ends and offers a quiet refresh", () => {
    const onRefresh = vi.fn();
    render(<FactorDataLine status={mockStatus} refreshing={false} message={null} onRefresh={onRefresh} />);
    expect(screen.getByText("Factor data ends 30 Sep 2026, so later dates cannot be chosen.")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Check for newer factor data" }));
    expect(onRefresh).toHaveBeenCalledTimes(1);
  });

  it("disables the button while refreshing and announces the result politely", () => {
    render(<FactorDataLine status={mockStatus} refreshing message="Factor data updated." onRefresh={vi.fn()} />);
    expect((screen.getByRole("button") as HTMLButtonElement).disabled).toBe(true);
    expect(screen.getByRole("status").textContent).toBe("Factor data updated.");
  });

  it("copes with unknown and empty status", () => {
    const empty: FactorDataStatus = { ...mockStatus, available: false, first_date: null, last_date: null };
    const { rerender } = render(<FactorDataLine status={undefined} refreshing={false} message={null} onRefresh={vi.fn()} />);
    expect(screen.getByText("Checking the factor data.")).toBeTruthy();
    rerender(<FactorDataLine status={empty} refreshing={false} message={null} onRefresh={vi.fn()} />);
    expect(screen.getByText(/No factor data is stored yet/)).toBeTruthy();
  });
});

function strip(props: Partial<ControlsStripProps> = {}) {
  const onCommit = vi.fn();
  const onQueryChange = vi.fn();
  const onRefreshFactors = vi.fn();
  const state: UrlState = { ...EMPTY_URL_STATE, ticker: "SPY" };
  const all: ControlsStripProps = {
    state,
    recent: [],
    suggestions: [],
    ranges: mockRanges("SPY"),
    factorStatus: mockStatus,
    report: mockReport,
    busy: false,
    refreshing: false,
    refreshMessage: null,
    onQueryChange,
    onCommit,
    onRefreshFactors,
    ...props,
  };
  const view = render(<ControlsStrip {...all} />);
  return { onCommit, onQueryChange, onRefreshFactors, view, all };
}

describe("ControlsStrip", () => {
  it("shows the reason for a disabled chip as visible text, not only a tooltip", () => {
    strip();
    const reason = screen.getByText("5Y has 400 trading days; a regression needs at least 504.");
    expect(reason.closest("[id]")?.id).toBe("ctl-why");
    expect(screen.getByRole("group", { name: "Date range" }).getAttribute("aria-describedby")).toBe("ctl-why");
    expect((screen.getByRole("radio", { name: "5Y" }) as HTMLInputElement).disabled).toBe(true);
  });

  it("shows no reason line when every preset is available", () => {
    const ranges = mockRanges("SPY");
    ranges.options = ranges.options.map((o) => ({ ...o, available: true, reason: null }));
    strip({ ranges });
    expect(document.getElementById("ctl-why")).toBeNull();
  });

  it("selects Full history when the URL has no range, and the preset when it has one", () => {
    const { view, all } = strip();
    expect(screen.getByRole("radio", { name: "Full history" })).toHaveProperty("checked", true);
    view.rerender(<ControlsStrip {...all} state={{ ...all.state, range: "3Y" }} />);
    expect(screen.getByRole("radio", { name: "3Y" })).toHaveProperty("checked", true);
  });

  it("clears the chip when custom dates are in the URL", () => {
    strip({ state: { ...EMPTY_URL_STATE, ticker: "SPY", start: "2024-01-02", end: "2025-01-02" } });
    for (const radio of screen.getAllByRole("radio")) expect((radio as HTMLInputElement).checked).toBe(false);
    expect((screen.getByLabelText("From") as HTMLInputElement).value).toBe("2024-01-02");
  });

  it("fills From and To with the analysed dates when a chip is chosen", () => {
    strip();
    expect((screen.getByLabelText("From") as HTMLInputElement).value).toBe("2024-08-08");
    expect((screen.getByLabelText("To") as HTMLInputElement).value).toBe("2026-09-30");
    expect((screen.getByLabelText("From") as HTMLInputElement).max).toBe("2026-09-30");
  });

  it("commits a chip as a preset and drops custom dates", () => {
    const { onCommit } = strip();
    fireEvent.click(screen.getByRole("radio", { name: "3Y" }));
    expect(onCommit).toHaveBeenCalledWith({ range: "3Y", start: null, end: null });
  });

  it("commits complete custom dates, which clears the chip", () => {
    const { onCommit } = strip();
    fireEvent.change(screen.getByLabelText("From"), { target: { value: "2025-03-03" } });
    expect(onCommit).toHaveBeenCalledWith({ range: null, start: "2025-03-03", end: "2026-09-30" });
  });

  it("sends nothing when From is after To", () => {
    const { onCommit } = strip();
    fireEvent.change(screen.getByLabelText("To"), { target: { value: "2024-01-01" } });
    expect(onCommit).not.toHaveBeenCalled();
    expect(screen.getByRole("alert").textContent).toContain("Choose a start date before the end date.");
  });

  it("commits a valid ticker, upper-cased", () => {
    const { onCommit } = strip();
    const input = screen.getByRole("combobox", { name: "Ticker" });
    fireEvent.change(input, { target: { value: "brk-b" } });
    fireEvent.keyDown(input, { key: "Enter" });
    expect(onCommit).toHaveBeenCalledWith({ ticker: "BRK-B" });
  });

  it("shows an inline sentence for an invalid ticker, sends nothing, and clears it on typing", () => {
    const { onCommit } = strip();
    const input = screen.getByRole("combobox", { name: "Ticker" });
    fireEvent.change(input, { target: { value: "BRK B" } });
    fireEvent.keyDown(input, { key: "Enter" });
    expect(onCommit).not.toHaveBeenCalled();
    expect(screen.getByRole("alert").textContent).toBe(
      "BRK B is not a valid ticker. Use 1 to 12 letters, digits or . ^ = - (for example SPY or BRK-B).",
    );
    fireEvent.change(input, { target: { value: "BRK-B" } });
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("puts the analysed-range label and the factor-data line in the strip", () => {
    const { onRefreshFactors } = strip();
    expect(document.querySelector("[aria-live='polite']")?.textContent).toContain("Analysed 8 Aug 2024 to 30 Sep 2026");
    fireEvent.click(screen.getByRole("button", { name: "Check for newer factor data" }));
    expect(onRefreshFactors).toHaveBeenCalledTimes(1);
  });

  it("announces loading politely while a request runs", () => {
    strip({ busy: true });
    expect(screen.getAllByRole("status").map((s) => s.textContent)).toContain("Loading the report.");
  });

  it("focuses the search field on the landing page only", () => {
    strip({ state: EMPTY_URL_STATE, report: undefined, ranges: undefined });
    expect(document.activeElement).toBe(screen.getByRole("combobox", { name: "Ticker" }));
  });
});
