import { act, fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { cloneReport, mockReport } from "../../test/fixture";
import { ReportView } from "../report/ReportView";
import { auditBadge, NAV_ITEMS, sectionHasData } from "./SectionNav";
import { Shell } from "./Shell";

function page(report = mockReport) {
  return render(
    <Shell
      report={report}
      ticker={report.ticker}
      sidebar={
        <div className="side-group">
          <label htmlFor="ticker-input">Ticker</label>
          <input id="ticker-input" />
        </div>
      }
    >
      <ReportView report={report} downloadHref="#" win={null} onWinChange={vi.fn()} />
    </Shell>,
  );
}

describe("SectionNav", () => {
  it("lists the panels on the page, in page order, with the deeper checks after their sub-heading", async () => {
    page();
    const nav = await screen.findByRole("navigation", { name: "Sections" });
    const labels = Array.from(nav.querySelectorAll("a")).map((a) => a.querySelector(".nav-label")?.textContent);
    expect(labels).toEqual([
      "Summary",
      "Price",
      "Factor exposures",
      "Return sources",
      "Risk sources",
      "Exposure over time",
      "Data and audit",
      "Regression detail",
    ]);
    const hrefs = Array.from(nav.querySelectorAll("a")).map((a) => a.getAttribute("href"));
    expect(hrefs).toEqual(["#summary", "#price", "#exposures", "#returns", "#risk", "#rolling", "#data", "#regression-detail"]);
    const sub = nav.querySelector(".nav-sub");
    expect(sub?.textContent).toBe("Deeper checks");
    expect(sub?.closest("li")?.querySelector("a")?.getAttribute("href")).toBe("#data");
    for (const a of nav.querySelectorAll("a")) expect(a.querySelector("svg")?.getAttribute("aria-hidden")).toBe("true");
  });

  it("titles every listed panel with the label of its nav item", async () => {
    page();
    const nav = await screen.findByRole("navigation", { name: "Sections" });
    for (const a of nav.querySelectorAll("a")) {
      const id = (a.getAttribute("href") ?? "").slice(1);
      expect(document.querySelector(`#${id} h2`)?.textContent, id).toBe(a.querySelector(".nav-label")?.textContent);
    }
  });

  it("hides the item of a section that is null or absent in the report", () => {
    const r = cloneReport();
    expect(sectionHasData(r, "lead-lag")).toBe(false);
    expect(sectionHasData(r, "fragility")).toBe(false);
    expect(sectionHasData(r, "summary")).toBe(true);
    expect(sectionHasData(undefined, "lead-lag")).toBe(true);
    delete (r as { kalman_betas?: unknown }).kalman_betas;
    expect(sectionHasData(r, "kalman")).toBe(false);
    r.shrunk_betas = [];
    expect(sectionHasData(r, "shrunk")).toBe(true);
  });

  it("never lists Lead-lag or Fragility for a report without those sections", async () => {
    page();
    const nav = await screen.findByRole("navigation", { name: "Sections" });
    const labels = Array.from(nav.querySelectorAll(".nav-label")).map((n) => n.textContent ?? "");
    expect(labels.join("|")).not.toMatch(/Lead-lag|Fragility/);
  });

  it("names a label and an icon for every item, and a target id once only", () => {
    const ids = NAV_ITEMS.map((i) => i.id);
    expect(new Set(ids).size).toBe(ids.length);
    expect(ids).toEqual(expect.arrayContaining(["summary", "performance", "world-beta"]));
  });

  it("counts audit warnings and errors on Data and audit, with hidden words", async () => {
    page();
    const nav = await screen.findByRole("navigation", { name: "Sections" });
    const link = nav.querySelector('a[href="#data"]') as HTMLElement;
    expect(link.querySelector(".nav-badge")?.textContent).toBe("1 audit finding");
    expect(link.querySelector(".nav-badge")?.classList.contains("error")).toBe(false);
    const r = cloneReport();
    r.data.audit_findings = [
      { code: "a", severity: "error", message: "x", dates: [] },
      { code: "b", severity: "warning", message: "y", dates: [] },
      { code: "c", severity: "info", message: "z", dates: [] },
    ];
    expect(auditBadge(r)).toEqual({ count: 2, error: true });
    r.data.audit_findings = [];
    expect(auditBadge(r)).toEqual({ count: 0, error: false });
  });

  it("moves focus to the panel heading, marks the item current and replaces the hash", async () => {
    page();
    const before = window.history.length;
    const link = await screen.findByRole("link", { name: "Risk sources" });
    fireEvent.click(link);
    expect(document.activeElement?.textContent).toBe(document.querySelector("#risk h2")?.textContent);
    expect(document.activeElement?.getAttribute("tabindex")).toBe("-1");
    expect(link.getAttribute("aria-current")).toBe("location");
    expect(window.location.hash).toBe("#risk");
    expect(window.history.length).toBe(before);
  });
});

describe("drawer (under 900 px)", () => {
  it("opens from the menu button, moves focus into the sidebar, closes on Escape and returns focus", async () => {
    page();
    const menu = screen.getByRole("button", { name: "Menu" });
    expect(menu.getAttribute("aria-expanded")).toBe("false");
    expect(menu.getAttribute("aria-controls")).toBe("sidebar");
    fireEvent.click(menu);
    expect(menu.getAttribute("aria-expanded")).toBe("true");
    expect(document.activeElement?.id).toBe("ticker-input");
    expect(document.querySelector(".canvas")?.hasAttribute("inert")).toBe(true);
    act(() => {
      fireEvent.keyDown(document, { key: "Escape" });
    });
    expect(menu.getAttribute("aria-expanded")).toBe("false");
    expect(document.activeElement).toBe(menu);
    expect(document.querySelector(".canvas")?.hasAttribute("inert")).toBe(false);
  });

  it("keeps Tab inside the sidebar while open", () => {
    page();
    fireEvent.click(screen.getByRole("button", { name: "Menu" }));
    const close = screen.getByRole("button", { name: "Close menu" });
    const links = screen.getAllByRole("link").filter((a) => a.closest("#sidebar"));
    const last = links[links.length - 1] as HTMLElement;
    last.focus();
    fireEvent.keyDown(document, { key: "Tab" });
    expect(document.activeElement).toBe(close);
    fireEvent.keyDown(document, { key: "Tab", shiftKey: true });
    expect(document.activeElement).toBe(last);
  });

  it("closes when a section is chosen", async () => {
    page();
    const menu = screen.getByRole("button", { name: "Menu" });
    fireEvent.click(menu);
    fireEvent.click(await screen.findByRole("link", { name: "Price" }));
    expect(menu.getAttribute("aria-expanded")).toBe("false");
    expect(document.activeElement?.textContent).toBe("Price");
  });
});
