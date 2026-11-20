import { useEffect, useId, useRef, useState } from "react";
import type { FormEvent } from "react";
import type { LibraryLine } from "../../api/types";
import { lineCount } from "../../portfolio/composer";
import { MAX_SAVED } from "../../portfolio/store";
import { BOM, formatCsvError, parsePortfolioCsv, treeToCsv, uniqueName } from "../../portfolio/csv";
import type { CsvError } from "../../portfolio/csv";
import type { PortfolioTree } from "../../portfolio/tree";
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
  /** The library, to check the lines of an imported CSV file. */
  library: readonly LibraryLine[];
  /** Save the tree of an imported CSV file as a new portfolio and open it. */
  onImport: (tree: PortfolioTree) => void;
}

const SHOWN_ERRORS = 8;

/** Save text as a UTF-8 file (with a byte order mark, so Excel reads it right). */
function download(text: string, filename: string): void {
  const url = URL.createObjectURL(new Blob([BOM, text], { type: "text/csv;charset=utf-8" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function fileSlug(name: string): string {
  return name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "") || "portfolio";
}

function lines(n: number): string {
  return `${n} ${n === 1 ? "line" : "lines"}`;
}

/**
 * The sidebar of the portfolio mode: the saved portfolios (open, duplicate, rename, delete) and the
 * form for a new one (a name and a preset). The list is in browser storage only, and says so.
 */
export function PortfolioSidebar({ store, ready, onCreate, library, onImport }: PortfolioSidebarProps) {
  const { state, active } = store;
  const [renaming, setRenaming] = useState(false);
  const [renameText, setRenameText] = useState("");
  const [name, setName] = useState("");
  const [preset, setPreset] = useState<PresetId>("blank");
  const [startOpen] = useState(state.portfolios.length === 0);
  const [importErrors, setImportErrors] = useState<CsvError[] | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
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

  const importFile = async (file: File | undefined) => {
    if (file === undefined) return;
    if (state.portfolios.length >= MAX_SAVED) {
      setImportErrors([{ line: null, message: `You have ${MAX_SAVED} saved portfolios. Delete one before you import.` }]);
      return;
    }
    let text: string;
    try {
      text = await file.text();
    } catch {
      setImportErrors([{ line: null, message: "The file could not be read." }]);
      return;
    }
    const result = parsePortfolioCsv(text, library, file.name.replace(/[.][^.]*$/, ""));
    if (!result.ok) {
      setImportErrors(result.errors);
      return;
    }
    setImportErrors(null);
    const name = uniqueName(
      result.tree.name,
      state.portfolios.map((p) => p.tree.name),
    );
    onImport({ ...result.tree, name, root: { ...result.tree.root, label: name } });
  };

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
            <button
              type="button"
              className="linkbtn"
              disabled={active === null}
              onClick={() => active !== null && download(treeToCsv(active.tree), `${fileSlug(active.tree.name)}.csv`)}
            >
              <Icon name="download" />
              Export CSV
            </button>
            <button type="button" className="linkbtn" disabled={!ready} onClick={() => fileRef.current?.click()}>
              <Icon name="upload" />
              Import CSV
            </button>
          </div>
        )}
        <input
          ref={fileRef}
          type="file"
          accept=".csv,text/csv"
          hidden
          aria-label="Import a portfolio from a CSV file"
          onChange={(event) => {
            const file = event.target.files?.[0];
            event.target.value = "";
            void importFile(file);
          }}
        />
        {importErrors !== null && (
          <div className="pf-import-errors" role="alert">
            <p className="side-note">
              <b>The file was not imported.</b> Nothing was saved.
            </p>
            <ul>
              {importErrors.slice(0, SHOWN_ERRORS).map((error, k) => (
                <li key={k}>{formatCsvError(error)}</li>
              ))}
            </ul>
            {importErrors.length > SHOWN_ERRORS && (
              <p className="side-note">and {importErrors.length - SHOWN_ERRORS} more.</p>
            )}
            <button type="button" className="linkbtn" onClick={() => setImportErrors(null)}>
              Dismiss
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
