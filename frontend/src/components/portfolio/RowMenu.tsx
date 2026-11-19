import { useEffect, useRef, useState } from "react";
import type { KeyboardEvent } from "react";
import { Icon } from "../shell/icons";
import type { IconName } from "../shell/icons";

export interface RowMenuItem {
  label: string;
  icon: IconName;
  danger?: boolean;
  onSelect: () => void;
}

export interface RowMenuProps {
  /** Id of the "⋯" button, so the page can return focus to it. */
  id: string;
  /** "Actions for Gold". */
  label: string;
  items: RowMenuItem[];
}

/**
 * The "⋯" menu of a row. The button opens a small menu; arrow keys move between the items, Escape
 * or a click outside closes it and focus goes back to the button. Choosing an item runs it.
 */
export function RowMenu({ id, label, items }: RowMenuProps) {
  const [open, setOpen] = useState(false);
  const box = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    if (!open) return;
    box.current?.querySelector<HTMLElement>('[role="menuitem"]')?.focus();
    const onDown = (event: MouseEvent) => {
      if (box.current !== null && !box.current.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, [open]);

  const close = (restore: boolean) => {
    setOpen(false);
    if (restore) document.getElementById(id)?.focus();
  };

  const onKeyDown = (event: KeyboardEvent) => {
    if (!open) return;
    if (event.key === "Escape") {
      event.preventDefault();
      event.stopPropagation();
      close(true);
      return;
    }
    if (event.key === "Tab") {
      setOpen(false);
      return;
    }
    if (event.key !== "ArrowDown" && event.key !== "ArrowUp") return;
    event.preventDefault();
    const list = [...(box.current?.querySelectorAll<HTMLElement>('[role="menuitem"]') ?? [])];
    const at = list.indexOf(document.activeElement as HTMLElement);
    const next = event.key === "ArrowDown" ? (at + 1) % list.length : (at - 1 + list.length) % list.length;
    list[next]?.focus();
  };

  return (
    <span className="more" ref={box} role="presentation" onKeyDown={onKeyDown}>
      <button
        type="button"
        id={id}
        className="ib"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label={label}
        onClick={() => setOpen((o) => !o)}
      >
        <Icon name="more" />
      </button>
      {open ? (
        <div className="menu" role="menu" aria-label={label}>
          {items.map((item) => (
            <button
              key={item.label}
              type="button"
              role="menuitem"
              className={item.danger ? "danger" : undefined}
              onClick={() => {
                setOpen(false);
                item.onSelect();
              }}
            >
              <Icon name={item.icon} />
              {item.label}
            </button>
          ))}
        </div>
      ) : null}
    </span>
  );
}
