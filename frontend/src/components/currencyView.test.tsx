/** The euro view of the pieces (Sprint 3, S3-5): switch, top-bar chip, header pill, key figures, composer badges, backtest subtitle, credits. */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { FactorReport, LibraryLine } from "../api/types";
import section from "@fixtures/sections/portfolio_backtest.json";
import type { PortfolioBacktestSection } from "../api/types";
import { buildPreset } from "../portfolio/presets";
import { addLineWithWeight, libraryById } from "../portfolio/composer";
import type { PortfolioTree } from "../portfolio/tree";
import { LIBRARY } from "../portfolio/testLibrary";
import type { Currency } from "../state/currency";
import { hiddenPanels } from "../report/applicability";
import { cloneReport, mockReport } from "../test/fixture";
import { withSection } from "../test/sectionFixtures";
import { BacktestCard } from "./portfolio/BacktestCard";
import { TreePanel } from "./portfolio/TreePanel";
import { CurrencySwitch } from "./controls/CurrencySwitch";
import { Colophon } from "./report/Colophon";
import { Header } from "./report/Header";
import { SummaryPanel } from "./report/SummaryPanel";
import { Shell } from "./shell/Shell";

const CURRENCY = {
  reference: "EUR",
  fx_source: "Exchange rates: European Central Bank, euro foreign exchange reference rates.",
  rate_source: "Euro short-term rate and EONIA: European Central Bank, ECB Data Portal.",
  notes: ["Cash earns the euro overnight rate, not the US rate."],
};

function eurReport(): FactorReport {
  return { ...withSection(cloneReport(), "performance"), currency: CURRENCY } as FactorReport;
}

describe("CurrencySwitch", () => {
  it("is a USD | EUR radio group that reports the choice, with the note as a tooltip in the euro view", () => {
    const onSelect = vi.fn();
    const { rerender } = render(<CurrencySwitch currency="USD" onSelect={onSelect} />);
    const group = within(screen.getByRole("radiogroup", { name: "Currency" }));
    expect((group.getByRole("radio", { name: "USD" }) as HTMLInputElement).checked).toBe(true);
    expect((group.getByRole("radio", { name: "EUR" }) as HTMLInputElement).checked).toBe(false);
    expect(screen.queryByText(/US bond lines are hedged to EUR/)).toBeNull();
    expect(screen.getByText("Currency").getAttribute("title")).toBeNull();
    expect(screen.getByText("Currency").classList.contains("has-tip")).toBe(false);
    fireEvent.click(group.getByRole("radio", { name: "EUR" }));
    expect(onSelect).toHaveBeenCalledWith("EUR");
    rerender(<CurrencySwitch currency="EUR" onSelect={onSelect} />);
    expect((screen.getByRole("radio", { name: "EUR" }) as HTMLInputElement).checked).toBe(true);
    const label = screen.getByText("Currency");
    const note = "Returns, factors and cash in EUR. US bond lines are hedged to EUR.";
    expect(label.getAttribute("title")).toBe(note);
    expect(label.classList.contains("has-tip")).toBe(true);
    expect(document.querySelector(".ccy-note")).toBeNull(); // no caption on screen
    const hidden = screen.getByText(note);
    expect(hidden.classList.contains("vh")).toBe(true); // screen readers still get it
    expect(screen.getByRole("radiogroup", { name: "Currency" }).getAttribute("aria-describedby")).toBe(hidden.id);
  });
});

describe("the top-bar chip", () => {
  it("shows the active currency next to the subject, in both views", () => {
    const { container, rerender } = render(
      <Shell sidebar={<p>controls</p>} ticker="Balanced SAA" currency="EUR">
        <p>page</p>
      </Shell>,
    );
    const chip = container.querySelector(".topbar .ccy-chip");
    expect(chip?.textContent).toBe("EUR");
    expect(chip?.classList.contains("eur")).toBe(true);
    rerender(
      <Shell sidebar={<p>controls</p>} ticker="Balanced SAA" currency="USD">
        <p>page</p>
      </Shell>,
    );
    expect(container.querySelector(".topbar .ccy-chip")?.textContent).toBe("USD");
    expect(container.querySelector(".topbar .ccy-chip")?.classList.contains("eur")).toBe(false);
  });
});

describe("Header", () => {
  it("shows the Figures in EUR pill and a Currency item in the euro view only", () => {
    const { container, rerender } = render(<Header report={eurReport()} downloadHref="#" />);
    expect(container.querySelector(".ccy-pill")?.textContent).toBe("Figures in EUR");
    const items = Array.from(container.querySelectorAll(".abar > div")).map((d) => [
      d.querySelector("dt")?.textContent,
      d.querySelector("dd")?.textContent,
    ]);
    expect(items).toContainEqual(["Currency", "EUR"]);
    rerender(<Header report={mockReport} downloadHref="#" />);
    expect(container.querySelector(".ccy-pill")).toBeNull();
    expect(container.textContent).not.toContain("Currency");
  });
});

describe("SummaryPanel", () => {
  it("puts the currency code on the key figures only, names the cash behind Sharpe and shows the notes", () => {
    const report = eurReport();
    const { container } = render(<SummaryPanel report={report} />);
    const rows = new Map(
      Array.from(container.querySelectorAll("#sum-perf ~ .tw tbody tr")).map((tr) => [
        tr.querySelector("th")?.textContent ?? "",
        tr,
      ]),
    );
    expect(rows.get("Annualised return")?.querySelector(".ccy")?.textContent).toBe("EUR");
    expect(rows.get("Max drawdown")?.querySelector(".ccy")?.textContent).toBe("EUR");
    expect(rows.get("Volatility")?.querySelector(".ccy")).toBeNull();
    expect(container.querySelectorAll(".ccy").length).toBe(2);
    expect(rows.get("Sharpe ratioagainst EUR cash")?.querySelector(".ccy-sub")?.textContent).toBe("against EUR cash");
    expect(container.querySelector(".pm")?.textContent).toContain("Figures in EUR.");
    const notes = within(screen.getByRole("list", { name: "Currency notes" }));
    expect(notes.getByText("Cash earns the euro overnight rate, not the US rate.")).toBeTruthy();
  });

  it("is unchanged in the USD view", () => {
    const { container } = render(<SummaryPanel report={mockReport} />);
    expect(container.querySelector(".ccy")).toBeNull();
    expect(container.querySelector(".ccy-sub")).toBeNull();
    expect(container.querySelector(".cur-notes")).toBeNull();
    expect(container.textContent).not.toContain("EUR");
  });
});

describe("Colophon", () => {
  it("credits the exchange-rate and cash-rate sources when the report has them", () => {
    const { container, rerender } = render(<Colophon report={eurReport()} />);
    // Each credit shows once, as the backend wrote it: no doubled label, no doubled full stop.
    const lines = Array.from(container.querySelectorAll(".credits .credit")).map((n) => n.textContent);
    expect(lines).toEqual([CURRENCY.fx_source, CURRENCY.rate_source]);
    const text = container.querySelector(".credits")?.textContent ?? "";
    expect(text.match(/Exchange rates:/g)).toHaveLength(1);
    expect(text).not.toContain("..");
    rerender(<Colophon report={{ ...eurReport(), currency: { reference: "EUR" } } as FactorReport} />);
    expect(container.querySelector(".credits")).toBeNull();
    rerender(<Colophon report={mockReport} />);
    expect(container.querySelector(".credits")).toBeNull();
  });
});

describe("BacktestCard subtitle", () => {
  const base = section as unknown as PortfolioBacktestSection;
  it("says US dollars or euros", () => {
    const { rerender } = render(<BacktestCard section={base} />);
    expect(screen.getByText("Monthly rebalancing, in US dollars")).toBeTruthy();
    rerender(<BacktestCard section={base} currency="EUR" />);
    expect(screen.getByText("Monthly rebalancing, in euros")).toBeTruthy();
  });

  it("says where the unallocated weight is held", () => {
    const { rerender } = render(<BacktestCard section={base} />);
    expect(screen.getByText("10.0% held as USD cash")).toBeTruthy();
    rerender(<BacktestCard section={base} currency="EUR" />);
    expect(screen.getByText("10.0% held as EUR cash")).toBeTruthy();
  });
});

describe("hidden panels", () => {
  it("keeps Macro and Energy in the euro view: their legs are converted", () => {
    expect(hiddenPanels(eurReport()).has("macro")).toBe(false);
    expect(hiddenPanels(eurReport()).has("energy")).toBe(false);
  });

  it("follows the response, not the page: no currency block means USD labels", () => {
    // The page may be in EUR (the switch), but an older backend answers without a currency block.
    const { container } = render(<Header report={mockReport} downloadHref="#" />);
    expect(container.querySelector(".ccy-pill")).toBeNull();
    expect(hiddenPanels(mockReport).has("macro")).toBe(false);
  });
});

/** The library with the hedge facts the backend adds. */
const FLAGGED: LibraryLine[] = LIBRARY.map((line) => {
  if (line.id === "fi_na_gov") return { ...line, hedge_eur: true } as LibraryLine;
  if (line.id === "fi_eur_ig") return { ...line, multi_currency: true } as LibraryLine;
  return line;
});

function renderTree(currency: Currency) {
  let tree: PortfolioTree = buildPreset("saa", "Balanced SAA", FLAGGED);
  // The EUR Cash line and the multi-currency bond line, beside the preset's USD Cash and IEF.
  for (const id of ["cash_eur", "fi_eur_ig"]) {
    const line = FLAGGED.find((l) => l.id === id);
    if (line === undefined) throw new Error(id);
    tree = addLineWithWeight(tree, line, 0.01);
  }
  const client = new QueryClient();
  return render(
    <QueryClientProvider client={client}>
      <TreePanel
        tree={tree}
        library={libraryById(FLAGGED)}
        currency={currency}
        libraryCount={{ classes: 8, lines: FLAGGED.length }}
        onChange={vi.fn()}
        onOpenPicker={vi.fn()}
        pickerButtonId="pick"
        headingRef={{ current: null }}
      />
    </QueryClientProvider>,
  );
}

function rowOf(name: string): HTMLElement {
  const row = screen.getByText(name, { selector: ".nm" }).closest(".t-row");
  if (row === null) throw new Error(`no row ${name}`);
  return row as HTMLElement;
}

describe("unallocated weight in the composer", () => {
  function renderUnallocated(currency: Currency) {
    const line = FLAGGED.find((l) => l.id === "fi_na_gov");
    if (line === undefined) throw new Error("no line");
    const tree = addLineWithWeight(buildPreset("blank", "Half", FLAGGED), line, 0.5);
    render(
      <QueryClientProvider client={new QueryClient()}>
        <TreePanel
          tree={tree}
          library={libraryById(FLAGGED)}
          currency={currency}
          libraryCount={{ classes: 8, lines: FLAGGED.length }}
          onChange={vi.fn()}
          onOpenPicker={vi.fn()}
          pickerButtonId="pick"
          headingRef={{ current: null }}
        />
      </QueryClientProvider>,
    );
  }

  it("goes to EUR cash in the euro view and to USD cash otherwise", () => {
    renderUnallocated("EUR");
    expect(screen.getByText("Goes to EUR cash when you run the backtest")).toBeTruthy();
    cleanup();
    renderUnallocated("USD");
    expect(screen.getByText("Goes to USD cash when you run the backtest")).toBeTruthy();
  });
});

describe("composer rows in the euro view", () => {
  it("badges hedged lines, multi-currency lines and the cash lines", () => {
    renderTree("EUR");
    expect(within(rowOf("N. American Government Bonds")).getByText("hedged to EUR")).toBeTruthy();
    expect(within(rowOf("European Corporate Investment Grade Bonds")).getByText("not hedged: several currencies")).toBeTruthy();
    expect(within(rowOf("USD Cash")).getByText("USD cash, not hedged")).toBeTruthy();
    expect(within(rowOf("EUR Cash")).getByText("earns the EUR overnight rate")).toBeTruthy();
    // A line without the flags carries no currency badge.
    const equity = rowOf("Equity N. America - Large Cap");
    expect(within(equity).queryByText(/hedged/)).toBeNull();
  });

  it("shows none of the badges in the USD view", () => {
    renderTree("USD");
    expect(screen.queryByText("hedged to EUR")).toBeNull();
    expect(screen.queryByText("not hedged: several currencies")).toBeNull();
    expect(screen.queryByText("USD cash, not hedged")).toBeNull();
    expect(screen.queryByText("earns the EUR overnight rate")).toBeNull();
  });
});
