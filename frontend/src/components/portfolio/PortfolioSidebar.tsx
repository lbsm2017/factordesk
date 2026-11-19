import { useEffect, useId, useRef, useState } from "react";
import type { FormEvent } from "react";
import { lineCount } from "../../portfolio/composer";
import { PRESETS } from "../../portfolio/presets";
import type { PresetId } from "../../portfolio/presets";
import type { PortfolioStore } from "../../portfolio/usePortfolioStore";
import { Icon } from "../shell/icons";

export interface PortfolioSidebarProps {
  store: PortfolioStore;
  /** The library has loaded, so a preset can be built. */
  ready: boolean;
  /** Create a portfolio from a preset under a name (blank text means the preset's name). */
  onCreate: (preset: PresetId, name: string) => void;
}

function lines(n: number): string {
  return `${n} ${n === 1 ? "line" : "lines"}`;
}

/**
 * The sidebar of the portfolio mode: the saved portfolios (open, duplicate, rename, delete) and the
 * form for a new one (a name and a preset). The list is in browser storage only, and says so.
 */
export function PortfolioSidebar({ store, ready, onCreate }: PortfolioSidebarProps) {
  const { state, active } = store;
  const [renaming, setRenaming] = useState(false);
  const [renameText, setRenameText] = useState("");
  const [name, setName] = useState("");
  const [preset, setPreset] = useState<PresetId>("blank");
  const [startOpen] = useState(state.portfolios.length === 0);
  const renameRef = useRef<HTMLInputElement>(null);
  const renameId = useId();
  const nameId = useId();

  useEffect(() => {
    if (renaming) renameRef.current?.select();
  }, [renaming]);

  // Another portfolio: a rename in progress belongs to the old one.
  const activeId = active?.id ?? null;
  const [seen, setSeen] = useState(activeId);
  if (seen !== activeId) {
    setSeen(activeId);
    setRenaming(false);
  }

  const submitRename = (event: FormEvent) => {
    event.preventDefault();
    if (active !== null) store.rename(active.id, renameText);
    setRenaming(false);
    window.setTimeout(() => document.getElementById("pf-act-rename")?.focus(), 0);
  };

  return (
    <>
      <div className="side-group">
        <h2 className="side-label" id="saved-title">
          Saved portfolios
        </h2>
        {state.portfolios.length === 0 ? (
          <p className="side-note pf-empty">Nothing saved yet. Create a portfolio below.</p>
        ) : (
          <ul className="pf-list" aria-labelledby="saved-title">
            {state.portfolios.map((p) => (
              <li key={p.id}>
                <button
                  type="button"
                  aria-current={p.id === active?.id ? "true" : undefined}
                  onClick={() => store.select(p.id)}
                >
                  <Icon name="pie" />
                  <span className="nav-label">{p.tree.name}</span>
                  <span className="nav-meta">{lines(lineCount(p.tree))}</span>
                </button>
              </li>
            ))}
          </ul>
        )}
        {renaming && active !== null ? (
          <form className="pf-rename" onSubmit={submitRename}>
            <div className="controls">
              <div className="ctl-name">
                <label className="side-label" htmlFor={renameId}>
                  Portfolio name
                </label>
                <input
                  id={renameId}
                  ref={renameRef}
                  type="text"
                  autoComplete="off"
                  maxLength={80}
                  value={renameText}
                  onChange={(event) => setRenameText(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === "Escape") setRenaming(false);
                  }}
                />
              </div>
            </div>
            <div className="row controls">
              <button type="submit" className="btn" disabled={renameText.trim() === ""}>
                Save name
              </button>
              <button type="button" className="btn btn-quiet" onClick={() => setRenaming(false)}>
                Cancel
              </button>
            </div>
          </form>
        ) : (
          <div className="side-actions">
            <button
              type="button"
              className="linkbtn"
              disabled={active === null}
              onClick={() => active !== null && store.duplicate(active.id)}
            >
              <Icon name="copy" />
              Duplicate
            </button>
            <button
              type="button"
              id="pf-act-rename"
              className="linkbtn"
              disabled={active === null}
              onClick={() => {
                setRenameText(active?.tree.name ?? "");
                setRenaming(true);
              }}
            >
              <Icon name="edit" />
              Rename
            </button>
            <button
              type="button"
              className="linkbtn"
              disabled={active === null}
              onClick={() => active !== null && store.remove(active.id)}
            >
              <Icon name="trash" />
              Delete
            </button>
          </div>
        )}
        <p className="side-note pf-hint">Saved in this browser only.</p>
      </div>

      <details className="side-group side-details" open={startOpen}>
        <summary>New portfolio</summary>
        <form
          className="controls"
          aria-label="New portfolio"
          onSubmit={(event) => {
            event.preventDefault();
            if (ready) onCreate(preset, name);
            setName("");
          }}
        >
          <div className="ctl-name">
            <label className="side-label" htmlFor={nameId}>
              Name
            </label>
            <input
              id={nameId}
              type="text"
              autoComplete="off"
              maxLength={80}
              placeholder={PRESETS.find((p) => p.id === preset)?.label ?? "Portfolio"}
              value={name}
              onChange={(event) => setName(event.target.value)}
            />
          </div>
          <fieldset className="ctl-range">
            <legend className="side-label">Start from</legend>
            <div className="preset-grid">
              {PRESETS.map((p) => (
                <label key={p.id} className="preset">
                  <input
                    type="radio"
                    name="preset"
                    value={p.id}
                    checked={preset === p.id}
                    onChange={() => setPreset(p.id)}
                  />
                  <span>
                    {p.label}
                    <small>{p.lines.length === 0 ? "No lines" : lines(p.lines.length)}</small>
                  </span>
                </label>
              ))}
            </div>
          </fieldset>
          <button type="submit" className="btn" disabled={!ready}>
            <Icon name="plus" />
            Create portfolio
          </button>
          <p className="side-note">{ready ? "Every preset stays editable." : "Loading the library."}</p>
        </form>
      </details>
    </>
  );
}
