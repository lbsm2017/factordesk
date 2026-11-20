import { useCallback, useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { flushSync } from "react-dom";
import type { FactorReport } from "../../api/types";
import type { Currency } from "../../state/currency";
import "../../styles/shell.css";
import { Icon, Mark } from "./icons";
import { Sidebar } from "./Sidebar";

export interface ShellProps {
  /** Controls placed in the sidebar above the section navigation. */
  sidebar: ReactNode;
  /** The report on screen (section badge), if any. */
  report?: FactorReport | undefined;
  /** Ticker shown in the phone top bar. */
  ticker?: string | null;
  /** The reference currency; a small chip in the phone top bar shows it without opening the drawer. */
  currency?: Currency;
  /** The page's `<main>`; every report panel is a direct child of it. */
  children: ReactNode;
}

const NARROW = "(max-width: 899px)";
const FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])';

/**
 * App shell (design J, prototype v4a): skip link, the navy sidebar, and the canvas that holds
 * `<main>`. The sidebar is outside `<main>`, so the panels stay its direct children. Under 900 px
 * the sidebar is a drawer opened from the top bar: focus moves into it and is kept there, Escape
 * or the close button closes it, and focus returns to the menu button.
 */
export function Shell({ sidebar, report, ticker = null, currency, children }: ShellProps) {
  const [open, setOpen] = useState(false);
  const [canvas, setCanvas] = useState<HTMLDivElement | null>(null);
  const aside = useRef<HTMLElement>(null);
  const menu = useRef<HTMLButtonElement>(null);

  const close = useCallback((restore: boolean) => {
    flushSync(() => setOpen(false));
    if (restore) menu.current?.focus();
  }, []);

  useEffect(() => {
    if (!open) return;
    const panel = aside.current;
    const first = panel?.querySelector<HTMLElement>("#ticker-input") ?? panel?.querySelector<HTMLElement>(FOCUSABLE);
    first?.focus();
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        close(true);
        return;
      }
      if (event.key !== "Tab" || !panel) return;
      const list = [...panel.querySelectorAll<HTMLElement>(FOCUSABLE)];
      const head = list[0];
      const tail = list[list.length - 1];
      if (!head || !tail) return;
      const current = document.activeElement;
      if (!panel.contains(current)) {
        event.preventDefault();
        head.focus();
      } else if (event.shiftKey && current === head) {
        event.preventDefault();
        tail.focus();
      } else if (!event.shiftKey && current === tail) {
        event.preventDefault();
        head.focus();
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, close]);

  // A drawer left open while the window widens past 900 px would leave the page inert.
  useEffect(() => {
    if (typeof window.matchMedia !== "function") return;
    const query = window.matchMedia(NARROW);
    const onChange = () => {
      if (!query.matches) setOpen(false);
    };
    query.addEventListener("change", onChange);
    return () => query.removeEventListener("change", onChange);
  }, []);

  return (
    <div className={open ? "shell drawer-open" : "shell"}>
      <a className="skip" href="#report">
        Skip to the report
      </a>
      <header className="topbar" inert={open}>
        <button
          ref={menu}
          type="button"
          className="menu-btn"
          aria-expanded={open}
          aria-controls="sidebar"
          onClick={() => setOpen(true)}
        >
          <Icon name="menu" />
          <span className="vh">Menu</span>
        </button>
        <span className="mark">
          <Mark />
          <span translate="no">factordesk</span>
        </span>
        {ticker || currency ? (
          <p className="where" translate="no">
            {ticker}
            {currency ? <span className={currency === "EUR" ? "ccy-chip eur" : "ccy-chip"}>{currency}</span> : null}
          </p>
        ) : null}
      </header>
      {open ? (
        // The scrim is a pointer shortcut only; Escape and the close button do the same by keyboard.
        <div className="scrim" aria-hidden="true" onClick={() => close(true)} />
      ) : null}
      <Sidebar
        ref={aside}
        open={open}
        root={canvas}
        report={report}
        onClose={() => close(true)}
        onNavigate={() => {
          if (open) close(false);
        }}
      >
        {sidebar}
      </Sidebar>
      <div className="canvas" id="report" ref={setCanvas} tabIndex={-1} inert={open}>
        {children}
      </div>
    </div>
  );
}
