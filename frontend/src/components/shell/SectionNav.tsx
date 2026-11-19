import { useEffect, useState } from "react";
import type { MouseEvent } from "react";
import type { FactorReport } from "../../api/types";
import { Icon } from "./icons";
import type { IconName } from "./icons";

interface NavItem {
  /** Element id of the panel (a direct child of `<main>`). */
  id: string;
  label: string;
  icon: IconName;
  /** "Deeper checks" items follow the sub-heading of that name. */
  deeper?: boolean;
}

/**
 * Section items of prototype v4a. An item shows only while its panel is on the page, so a panel
 * that renders nothing (an optional section that is null) has no item, and a panel added later
 * (summary, performance, world beta) gets its item as soon as an element with its id renders.
 */
export const NAV_ITEMS: readonly NavItem[] = [
  { id: "summary", label: "Summary", icon: "summary" },
  { id: "price", label: "Price", icon: "price" },
  { id: "performance", label: "Drawdown", icon: "drawdown" },
  { id: "tail-risk", label: "Tail risk", icon: "risk" },
  { id: "exposures", label: "Factor exposures", icon: "exposures" },
  { id: "alpha-strip", label: "Alpha across models", icon: "residual" },
  { id: "world-beta", label: "World beta", icon: "world" },
  { id: "macro", label: "Macro sensitivities", icon: "exposures" },
  { id: "returns", label: "Return sources", icon: "returns" },
  { id: "risk", label: "Risk sources", icon: "risk" },
  { id: "rolling", label: "Exposure over time", icon: "rolling" },
  { id: "residual", label: "Beyond the factors", icon: "residual", deeper: true },
  { id: "kalman", label: "Tracked day by day", icon: "kalman", deeper: true },
  { id: "shrunk", label: "Adjusted for noise", icon: "shrunk", deeper: true },
  { id: "lead-lag", label: "Lead-lag betas", icon: "leadlag", deeper: true },
  { id: "fragility", label: "Fragility", icon: "fragility", deeper: true },
  { id: "data", label: "Data and audit", icon: "data", deeper: true },
  { id: "regression-detail", label: "Regression detail", icon: "detail", deeper: true },
];

/** Report field behind each optional section; its item is hidden while the field is null or absent. */
const SECTION_FIELD: Readonly<Record<string, keyof FactorReport>> = {
  performance: "performance",
  "tail-risk": "tail_risk",
  "alpha-strip": "alpha_strip",
  "world-beta": "world_beta",
  macro: "macro",
  residual: "residual",
  kalman: "kalman_betas",
  shrunk: "shrunk_betas",
  "lead-lag": "lead_lag",
  fragility: "fragility",
};

/** The label of an item: the price item reads "Growth of 100" for a report with a subject (an uploaded record). */
export function navLabel(item: NavItem, report: FactorReport | undefined): string {
  return item.id === "price" && report?.subject != null ? "Growth of 100" : item.label;
}

/** True when the item's section has data in `report` (always true for items with no optional field). */
export function sectionHasData(report: FactorReport | undefined, id: string): boolean {
  const field = SECTION_FIELD[id];
  if (report === undefined || field === undefined) return true;
  return (report as unknown as Record<string, unknown>)[field] != null;
}

/** Audit findings with severity warning or error, and whether any is an error. */
export function auditBadge(report: FactorReport | undefined): { count: number; error: boolean } {
  const findings = report?.data.audit_findings ?? [];
  const serious = findings.filter((f) => f.severity === "warning" || f.severity === "error");
  return { count: serious.length, error: serious.some((f) => f.severity === "error") };
}

interface Entry {
  item: NavItem;
  el: HTMLElement;
}

/** The items whose panel is inside `root`, with their elements, in page order. */
function presentEntries(root: HTMLElement): Entry[] {
  const found = NAV_ITEMS.flatMap((item) => {
    const el = document.getElementById(item.id);
    return el && root.contains(el) ? [{ item, el }] : [];
  });
  return found.sort((a, b) => (a.el.compareDocumentPosition(b.el) & Node.DOCUMENT_POSITION_FOLLOWING ? -1 : 1));
}

/** Same items on the same elements (a lazy panel replaces its placeholder element). */
function sameEntries(a: readonly Entry[], b: readonly Entry[]): boolean {
  return a.length === b.length && a.every((e, i) => e.item === b[i]?.item && e.el === b[i]?.el);
}

function reducedMotion(): boolean {
  return typeof window.matchMedia === "function" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

export interface SectionNavProps {
  /** The element that holds `<main>`; null until it mounts. */
  root: HTMLElement | null;
  /** The report on screen, for the badge on "Data and audit". */
  report: FactorReport | undefined;
  /** Called before the page scrolls to a section (the drawer closes). */
  onNavigate?: () => void;
}

/**
 * Section navigation with scroll-spy (design J.3): one IntersectionObserver marks the panel whose
 * top has passed 20% of the viewport with `aria-current="location"`. Activating an item scrolls
 * to the panel, moves focus to its heading and updates the hash without a new history entry.
 */
export function SectionNav({ root, report, onNavigate }: SectionNavProps) {
  const [entries, setEntries] = useState<Entry[]>([]);
  const [active, setActive] = useState<string | null>(null);

  useEffect(() => {
    if (root === null) return;
    const scan = () => {
      const next = presentEntries(root);
      setEntries((prev) => (sameEntries(prev, next) ? prev : next));
    };
    scan();
    const observer = new MutationObserver(scan);
    observer.observe(root, { childList: true, subtree: true });
    return () => observer.disconnect();
  }, [root]);

  useEffect(() => {
    if (entries.length === 0 || typeof IntersectionObserver === "undefined") return;
    const ordered = entries.map((e) => e.el);
    let frame = 0;
    const pick = () => {
      frame = 0;
      const line = window.innerHeight * 0.2;
      let current = ordered[0]?.id ?? null;
      for (const el of ordered) if (el.getBoundingClientRect().top <= line + 1) current = el.id;
      const bottom = window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - 2;
      if (bottom && ordered.length > 0) current = ordered[ordered.length - 1]?.id ?? current;
      setActive(current);
    };
    const schedule = () => {
      if (frame === 0) frame = window.requestAnimationFrame(pick);
    };
    const observer = new IntersectionObserver(schedule, { rootMargin: "-20% 0px -70% 0px" });
    for (const el of ordered) observer.observe(el);
    window.addEventListener("scroll", schedule, { passive: true });
    pick();
    return () => {
      observer.disconnect();
      window.removeEventListener("scroll", schedule);
      if (frame !== 0) window.cancelAnimationFrame(frame);
    };
  }, [entries]);

  const go = (event: MouseEvent<HTMLAnchorElement>, id: string) => {
    const target = document.getElementById(id);
    if (target === null) return;
    event.preventDefault();
    onNavigate?.();
    target.scrollIntoView?.({ behavior: reducedMotion() ? "auto" : "smooth", block: "start" });
    const heading = target.querySelector<HTMLElement>("h2, h1");
    if (heading) {
      if (!heading.hasAttribute("tabindex")) heading.setAttribute("tabindex", "-1");
      heading.focus({ preventScroll: true });
    }
    const { pathname, search } = window.location;
    window.history.replaceState(window.history.state, "", `${pathname}${search}#${id}`);
    setActive(id);
  };

  if (entries.length === 0) return null;
  const listed = entries.map((e) => e.item).filter((i) => sectionHasData(report, i.id));
  if (listed.length === 0) return null;
  // Page order for the main sections; the deeper checks keep the order of NAV_ITEMS.
  const items = [
    ...listed.filter((i) => !i.deeper),
    ...NAV_ITEMS.filter((i) => i.deeper && listed.includes(i)),
  ];
  const badge = auditBadge(report);
  const firstDeeper = items.findIndex((i) => i.deeper);
  return (
    <nav className="side-group nav" aria-labelledby="nav-title">
      <h2 className="vh" id="nav-title">
        Sections
      </h2>
      <ul>
        {items.map((item, index) => (
          <li key={item.id}>
            {index === firstDeeper ? (
              <p className="nav-sub" aria-hidden="true">
                Deeper checks
              </p>
            ) : null}
            <a
              href={`#${item.id}`}
              aria-current={active === item.id ? "location" : undefined}
              onClick={(event) => go(event, item.id)}
            >
              <Icon name={item.icon} />
              <span className="nav-label">{navLabel(item, report)}</span>
              {item.id === "data" && badge.count > 0 ? (
                <span className={badge.error ? "nav-badge error" : "nav-badge"}>
                  {badge.count}
                  <span className="vh">{badge.count === 1 ? " audit finding" : " audit findings"}</span>
                </span>
              ) : null}
            </a>
          </li>
        ))}
      </ul>
    </nav>
  );
}
