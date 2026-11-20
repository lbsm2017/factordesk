/** The factor set pieces (Sprint 4, S4-4 and S4-6): switch, header pill, top-bar chip, summary note, and the "What EUR changes" dialog. */
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { FactorReport } from "../api/types";
import { cloneReport, mockReport } from "../test/fixture";
import { withSection } from "../test/sectionFixtures";
import { FactorSetSwitch } from "./controls/FactorSetSwitch";
import { Header } from "./report/Header";
import { SummaryPanel } from "./report/SummaryPanel";
import { Shell } from "./shell/Shell";

const CURRENCY = { reference: "EUR", fx_source: "a", rate_source: "b", notes: [] };

function report(patch: Record<string, unknown> = {}): FactorReport {
  return { ...withSection(cloneReport(), "performance"), ...patch } as FactorReport;
}

afterEach(cleanup);

describe("FactorSetSwitch", () => {
  it("is a US | Europe radio group that reports the choice, with the note as a tooltip for Europe", () => {
    const onSelect = vi.fn();
    const { rerender } = render(<FactorSetSwitch factorSet="us" onSelect={onSelect} />);
    const group = within(screen.getByRole("radiogroup", { name: "Factor set" }));
    expect((group.getByRole("radio", { name: "US" }) as HTMLInputElement).checked).toBe(true);
    expect(screen.queryByText(/Developed Europe/)).toBeNull();
    expect(screen.getByText("Factor set").getAttribute("title")).toBeNull();
    fireEvent.click(group.getByRole("radio", { name: "Europe" }));
    expect(onSelect).toHaveBeenCalledWith("europe");
    rerender(<FactorSetSwitch factorSet="europe" onSelect={onSelect} />);
    expect((screen.getByRole("radio", { name: "Europe" }) as HTMLInputElement).checked).toBe(true);
    const label = screen.getByText("Factor set");
    const note = "Factors: Developed Europe, five factors plus momentum. Macro, energy and world beta keep their US inputs.";
    expect(label.getAttribute("title")).toBe(note);
    expect(label.classList.contains("has-tip")).toBe(true);
    expect(document.querySelector(".fs-note")).toBeNull(); // no caption on screen
    const hidden = screen.getByText(note);
    expect(hidden.classList.contains("vh")).toBe(true); // screen readers still get it
    expect(screen.getByRole("radiogroup", { name: "Factor set" }).getAttribute("aria-describedby")).toBe(hidden.id);
  });
});

describe("the top-bar chip", () => {
  it("shows Europe for the Europe set only, beside the currency chip", () => {
    const { container, rerender } = render(
      <Shell sidebar={<p>controls</p>} ticker="SPY" currency="EUR" factorSet="europe">
        <p>page</p>
      </Shell>,
    );
    expect(container.querySelector(".topbar .ccy-chip")?.textContent).toBe("EUR");
    expect(container.querySelector(".topbar .set-chip")?.textContent).toBe("Europe");
    rerender(
      <Shell sidebar={<p>controls</p>} ticker="SPY" currency="EUR" factorSet="us">
        <p>page</p>
      </Shell>,
    );
    expect(container.querySelector(".topbar .set-chip")).toBeNull();
  });
});

describe("the header pill", () => {
  it("names the set: quiet for US, accent for Europe, and adds a Factor set item", () => {
    const { container, rerender } = render(<Header report={mockReport} downloadHref="#" />);
    const pill = container.querySelector(".set-pill");
    expect(pill?.textContent).toBe("US factors");
    expect(pill?.classList.contains("plain")).toBe(true);
    const items = () =>
      Array.from(container.querySelectorAll(".abar > div")).map((d) => [d.querySelector("dt")?.textContent, d.querySelector("dd")?.textContent]);
    expect(items()).toContainEqual(["Factor set", "US"]);
    rerender(<Header report={report({ factor_set: "europe" })} downloadHref="#" />);
    const europe = container.querySelector(".set-pill");
    expect(europe?.textContent).toBe("Europe factors");
    expect(europe?.classList.contains("plain")).toBe(false);
    expect(items()).toContainEqual(["Factor set", "Developed Europe"]);
  });

  it("adds the Europe note to the Summary and nothing for the US set", () => {
    const { container, rerender } = render(<SummaryPanel report={report({ factor_set: "europe" })} />);
    expect(within(container).getByRole("list", { name: "Factor set note" }).textContent).toContain("Developed Europe");
    rerender(<SummaryPanel report={report()} />);
    expect(container.querySelector(".cur-notes")).toBeNull();
  });
});

describe("What EUR changes", () => {
  const eur = () => report({ currency: CURRENCY });

  it("is offered in the euro view only", () => {
    const { rerender } = render(<Header report={eur()} downloadHref="#" />);
    expect(screen.getByRole("button", { name: "What EUR changes" })).toBeTruthy();
    rerender(<Header report={mockReport} downloadHref="#" />);
    expect(screen.queryByRole("button", { name: "What EUR changes" })).toBeNull();
  });

  it("opens an accessible dialog, moves focus to Close, keeps Tab inside, and Escape returns focus to the link", () => {
    render(<Header report={eur()} downloadHref="#" />);
    const trigger = screen.getByRole("button", { name: "What EUR changes" });
    trigger.focus();
    expect(screen.queryByRole("dialog")).toBeNull();
    fireEvent.click(trigger);
    const dialog = screen.getByRole("dialog", { name: "What EUR changes" });
    expect(dialog.getAttribute("aria-modal")).toBe("true");
    const close = within(dialog).getByRole("button", { name: "Close" });
    expect(document.activeElement).toBe(close);
    // Close is the only control: Tab and Shift+Tab stay on it.
    fireEvent.keyDown(document, { key: "Tab" });
    expect(document.activeElement).toBe(close);
    fireEvent.keyDown(document, { key: "Tab", shiftKey: true });
    expect(document.activeElement).toBe(close);
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(document.activeElement).toBe(trigger);
  });

  it("closes with the Close button and with a click on the overlay, returning focus each time", () => {
    const { container } = render(<Header report={eur()} downloadHref="#" />);
    const trigger = screen.getByRole("button", { name: "What EUR changes" });
    fireEvent.click(trigger);
    fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Close" }));
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(document.activeElement).toBe(trigger);
    fireEvent.click(trigger);
    const scrim = document.querySelector(".eur-scrim");
    if (scrim === null) throw new Error("no overlay");
    fireEvent.click(scrim);
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(document.activeElement).toBe(trigger);
    expect(container.contains(document.querySelector(".eur-layer"))).toBe(false);
  });

  it("says nothing is hedged for a ticker, and which bond funds are hedged for a portfolio", () => {
    const { rerender } = render(<Header report={eur()} downloadHref="#" />);
    fireEvent.click(screen.getByRole("button", { name: "What EUR changes" }));
    let dialog = screen.getByRole("dialog");
    expect(dialog.textContent).toContain("Prices are converted to euros every day, at the ECB reference rate.");
    expect(dialog.textContent).toContain("Cash earns the euro overnight rate (€STR), not the US rate.");
    expect(dialog.textContent).toContain("Nothing is hedged: a US ticker still moves with the dollar.");
    expect(dialog.textContent).toContain("A portfolio view hedges its US dollar bond lines.");
    fireEvent.keyDown(document, { key: "Escape" });
    const portfolio = report({ currency: CURRENCY, portfolio_backtest: { weights: [] } });
    rerender(<Header report={portfolio} downloadHref="#" />);
    fireEvent.click(screen.getByRole("button", { name: "What EUR changes" }));
    dialog = screen.getByRole("dialog");
    expect(dialog.textContent).toContain("US dollar bond funds (IEF, LQD, HYG, EMB, TIP) are hedged to the euro.");
    expect(dialog.textContent).toContain("The hedge is an estimate from the rate gap, not a fund's own hedge.");
  });
});
