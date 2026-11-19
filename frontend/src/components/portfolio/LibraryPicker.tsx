import { useEffect, useMemo, useRef, useState } from "react";
import type { LibraryLine } from "../../api/types";
import { isShortHistory, yearOf } from "../../portfolio/composer";
import { Icon } from "../shell/icons";
import { assetClassColor, cssVars } from "./assetClass";

export interface LibraryPickerProps {
  library: readonly LibraryLine[];
  /** Ids of the library lines already in the tree. */
  inTree: ReadonlySet<string>;
  onAdd: (line: LibraryLine) => void;
  onClose: () => void;
}

const FOCUSABLE = 'button:not([disabled]), input:not([disabled]), [tabindex]:not([tabindex="-1"])';

function matches(line: LibraryLine, query: string): boolean {
  if (query === "") return true;
  const hay = `${line.sub_asset_class} ${line.asset_class} ${line.proxy ?? ""}`.toLowerCase();
  return query
    .toLowerCase()
    .split(/\s+/)
    .every((word) => hay.includes(word));
}

/**
 * The searchable library (a modal dialog): the lines grouped by asset class, each with its proxy
 * ticker and start year. A line with no proxy yet is shown and cannot be added. The list stays
 * open after an add, so several lines can be chosen one after the other; Escape or Close ends it.
 */
export function LibraryPicker({ library, inTree, onAdd, onClose }: LibraryPickerProps) {
  const [query, setQuery] = useState("");
  const [announce, setAnnounce] = useState("");
  const dialog = useRef<HTMLElement>(null);
  const search = useRef<HTMLInputElement>(null);

  useEffect(() => {
    search.current?.focus();
  }, []);

  const groups = useMemo(() => {
    const out: { name: string; lines: LibraryLine[] }[] = [];
    for (const line of library) {
      if (!matches(line, query.trim())) continue;
      const last = out[out.length - 1];
      if (last !== undefined && last.name === line.asset_class) last.lines.push(line);
      else out.push({ name: line.asset_class, lines: [line] });
    }
    return out;
  }, [library, query]);
  const shown = groups.reduce((n, g) => n + g.lines.length, 0);
  const withProxy = library.filter((l) => l.proxy !== null).length;

  // Escape closes and Tab stays inside the dialog.
  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onClose();
        return;
      }
      if (event.key !== "Tab" || dialog.current === null) return;
      const list = [...dialog.current.querySelectorAll<HTMLElement>(FOCUSABLE)];
      const head = list[0];
      const tail = list[list.length - 1];
      if (head === undefined || tail === undefined) return;
      if (!dialog.current.contains(document.activeElement)) {
        event.preventDefault();
        head.focus();
      } else if (event.shiftKey && document.activeElement === head) {
        event.preventDefault();
        tail.focus();
      } else if (!event.shiftKey && document.activeElement === tail) {
        event.preventDefault();
        head.focus();
      }
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [onClose]);

  return (
    <div className="pick-layer">
      <div className="pick-scrim" aria-hidden="true" onClick={onClose} />
      <section
        ref={dialog}
        className="picker"
        role="dialog"
        aria-modal="true"
        aria-labelledby="pick-title"
      >
        <div className="pick-head">
          <h2 id="pick-title">Add sub-asset class</h2>
          <button type="button" className="ib" onClick={onClose} aria-label="Close library">
            <Icon name="close" />
          </button>
        </div>
        <div className="pick-search">
          <label htmlFor="pick-q">Search the library</label>
          <div className="sbox">
            <Icon name="search" />
            <input
              id="pick-q"
              ref={search}
              type="search"
              placeholder="Name, ticker or asset class"
              autoComplete="off"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
            />
          </div>
        </div>
        <div className="pick-list" role="group" aria-label="Library lines">
          {groups.length === 0 ? <p className="pick-empty">No line matches “{query}”.</p> : null}
          {groups.map((group) => (
            <div key={group.name}>
              <div className="pick-grp">
                <span className="key-sq" style={cssVars({ "--c": assetClassColor(group.name) })} />
                <b>{group.name}</b>
                <span>{group.lines.length === 1 ? "1 line" : `${group.lines.length} lines`}</span>
              </div>
              {group.lines.map((line) => {
                const year = yearOf(line.first_date);
                const late = isShortHistory(line);
                const added = inTree.has(line.id);
                if (line.proxy === null) {
                  return (
                    <div key={line.id} className="pick-row off">
                      <div>
                        <div className="nm">{line.sub_asset_class}</div>
                        <div className="why">{line.note || "Benchmark to be added"}</div>
                      </div>
                      <span className="nmark">No proxy yet</span>
                    </div>
                  );
                }
                return (
                  <div key={line.id} className="pick-row">
                    <div>
                      <div className="nm">{line.sub_asset_class}</div>
                      <div className="sb">
                        <b>{line.proxy === "RF" ? "Risk-free rate" : line.proxy}</b>
                        {year !== null ? (
                          <>
                            {" · "}
                            <span className={late ? "late" : undefined}>from {year}</span>
                          </>
                        ) : null}
                        {line.proxy_kind === "listed_proxy" ? <span className="tag">listed proxy</span> : null}
                        {late ? <span className="tag warn">short history</span> : null}
                      </div>
                    </div>
                    {added ? (
                      <span className="done">
                        <Icon name="check" />
                        In portfolio
                      </span>
                    ) : (
                      <button
                        type="button"
                        className="add"
                        aria-label={`Add ${line.sub_asset_class}`}
                        onClick={() => {
                          onAdd(line);
                          setAnnounce(`${line.sub_asset_class} added.`);
                          search.current?.focus();
                        }}
                      >
                        <Icon name="plus" />
                        Add
                      </button>
                    )}
                  </div>
                );
              })}
            </div>
          ))}
        </div>
        <div className="pick-foot">
          <span>
            {library.length} lines, {withProxy} with a proxy
            {query.trim() !== "" ? `. ${shown} shown` : ""}
          </span>
          <span>Greyed lines have no proxy yet.</span>
        </div>
        <span className="vh" role="status">
          {announce}
        </span>
      </section>
    </div>
  );
}
