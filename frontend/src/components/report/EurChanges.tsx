import { useEffect, useId, useRef } from "react";
import type { RefObject } from "react";
import { createPortal } from "react-dom";
import { Icon } from "../shell/icons";
import "./eurChanges.css";

export interface EurChangesProps {
  /** The portfolio view hedges its US dollar bond lines; a ticker or a track record is not hedged. */
  portfolio: boolean;
  onClose: () => void;
  /** The button that opened the panel: focus returns to it when the panel closes. */
  returnFocus: RefObject<HTMLElement | null>;
}

const FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]), [tabindex]:not([tabindex="-1"])';

/**
 * "What EUR changes": a right-hand dialog of about 60 words (Sprint 4 mockup 3). Focus goes to the
 * Close button on open and stays inside; Escape, the Close button and a click on the overlay close
 * it; on close focus returns to the button that opened it. It is drawn on the page body, so no
 * panel of the report can clip it.
 */
export function EurChanges({ portfolio, onClose, returnFocus }: EurChangesProps) {
  const titleId = useId();
  const sheet = useRef<HTMLElement>(null);
  const close = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    close.current?.focus();
    const back = returnFocus.current;
    return () => back?.focus();
  }, [returnFocus]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onClose();
        return;
      }
      const panel = sheet.current;
      if (event.key !== "Tab" || panel === null) return;
      const list = [...panel.querySelectorAll<HTMLElement>(FOCUSABLE)];
      const head = list[0];
      const tail = list[list.length - 1];
      if (head === undefined || tail === undefined) return;
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
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [onClose]);

  return createPortal(
    <div className="eur-layer">
      <div className="eur-scrim" aria-hidden="true" onClick={onClose} />
      <aside ref={sheet} className="eur-sheet" role="dialog" aria-modal="true" aria-labelledby={titleId}>
        <div className="sh-head">
          <h2 id={titleId}>What EUR changes</h2>
          <button ref={close} type="button" className="sh-close" onClick={onClose}>
            <Icon name="close" />
            <span className="vh">Close</span>
          </button>
        </div>
        <div className="sh-body">
          <ul className="sh-list">
            <li>
              <Icon name="check" />
              <span>
                Prices are converted to euros <b>every day</b>, at the ECB reference rate.
              </span>
            </li>
            <li>
              <Icon name="check" />
              <span>
                Cash earns the <b>euro overnight rate</b> (€STR), not the US rate.
              </span>
            </li>
            <li>
              <Icon name="check" />
              {portfolio ? (
                <span>
                  US dollar bond funds (IEF, LQD, HYG, EMB, TIP) are <b>hedged</b> to the euro. Shares, gold and European or global bond funds
                  are not.
                </span>
              ) : (
                <span>
                  Nothing is <b>hedged</b>: a US ticker still moves with the dollar.
                </span>
              )}
            </li>
          </ul>
          <p className="sh-foot">
            {portfolio
              ? "The hedge is an estimate from the rate gap, not a fund's own hedge."
              : "A portfolio view hedges its US dollar bond lines."}
          </p>
        </div>
      </aside>
    </div>,
    document.body,
  );
}
