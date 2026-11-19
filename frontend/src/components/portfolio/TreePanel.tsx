import { useId, useState } from "react";
import type { FormEvent, KeyboardEvent, ReactNode, RefObject } from "react";
import { useTickerSuggestions } from "../../api/queries";
import type { LibraryLine } from "../../api/types";
import {
  isShortHistory,
  nudge,
  removeNode,
  renameTree,
  yearOf,
} from "../../portfolio/composer";
import {
  addInstrument,
  remainder,
  rename,
  rollUp,
  setWeight,
  swapInstrument,
  totalWeight,
} from "../../portfolio/tree";
import type { Instrument, PortfolioTree, SubAssetClassGroup } from "../../portfolio/tree";
import { useRecent } from "../../state/recent";
import { checkTicker } from "../../state/url";
import { TickerSearch } from "../controls/TickerSearch";
import { Icon } from "../shell/icons";
import { assetClassColor, cssVars } from "./assetClass";
import { RowMenu } from "./RowMenu";
import { WeightInput } from "./WeightInput";

export interface TreePanelProps {
  tree: PortfolioTree;
  library: ReadonlyMap<string, LibraryLine>;
  libraryCount: { classes: number; lines: number };
  onChange: (tree: PortfolioTree) => void;
  onOpenPicker: () => void;
  /** Set on the Add button so the page can return focus to it after the picker closes. */
  pickerButtonId: string;
  headingRef: RefObject<HTMLHeadingElement | null>;
}

type Pop = { kind: "swap" | "add" | "rename"; id: string };

function pctText(weight: number): string {
  return `${(weight * 100).toFixed(1)}%`;
}

function focusLater(id: string): void {
  window.setTimeout(() => document.getElementById(id)?.focus(), 0);
}

// ------------------------------------------------------------------ the pop-up row under a line

function TickerPop({
  mode,
  onPick,
  onCancel,
  idBase,
}: {
  mode: "swap" | "add";
  onPick: (ticker: string) => void;
  onCancel: () => void;
  idBase: string;
}) {
  const [query, setQuery] = useState("");
  const [error, setError] = useState<string | null>(null);
  const recent = useRecent();
  const suggestions = useTickerSuggestions(query);
  return (
    <div className="pop-body">
      <TickerSearch
        value=""
        recent={recent}
        suggestions={suggestions.data?.items ?? []}
        error={error}
        focusOnMount
        slashFocus={false}
        inputId={`${idBase}-ticker`}
        label={mode === "swap" ? "New ticker" : "Ticker to add"}
        submitLabel={mode === "swap" ? "Swap" : "Add"}
        onQueryChange={(q) => {
          setError(null);
          setQuery(q);
        }}
        onSubmit={(text) => {
          const checked = checkTicker(text);
          if (!checked.ok) {
            setError(checked.message);
            return;
          }
          onPick(checked.ticker);
        }}
      />
      <button type="button" className="btn-outline" onClick={onCancel}>
        Cancel
      </button>
      <p className="hint">Any ticker listed in US dollars. The run checks the listing and the start date.</p>
    </div>
  );
}

function RenamePop({ initial, onSave, onCancel }: { initial: string; onSave: (name: string) => void; onCancel: () => void }) {
  const [text, setText] = useState(initial);
  const id = useId();
  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (text.trim() !== "") onSave(text.trim().slice(0, 80));
  };
  return (
    <form className="pop-body" onSubmit={submit}>
      <div className="pop-field">
        <label className="cap" htmlFor={id}>
          Name
        </label>
        <input
          id={id}
          className="field"
          type="text"
          autoComplete="off"
          maxLength={80}
          value={text}
          // eslint-disable-next-line jsx-a11y/no-autofocus
          autoFocus
          onFocus={(event) => event.currentTarget.select()}
          onChange={(event) => setText(event.target.value)}
        />
      </div>
      <button type="submit" className="btn" disabled={text.trim() === ""}>
        Save name
      </button>
      <button type="button" className="btn-outline" onClick={onCancel}>
        Cancel
      </button>
    </form>
  );
}

// ------------------------------------------------------------------------------------- the tree

/**
 * The left half of the composer: the allocation tree. Asset classes collapse and show read-only
 * totals; each line shows its library name, proxy ticker and start year, and each instrument has a
 * typed percent field with a share bar. Swap, add an instrument, rename and remove are on the row.
 */
export function TreePanel({ tree, library, libraryCount, onChange, onOpenPicker, pickerButtonId, headingRef }: TreePanelProps) {
  const [collapsed, setCollapsed] = useState<ReadonlySet<string>>(new Set());
  const [pop, setPop] = useState<Pop | null>(null);
  const baseId = useId();
  const totals = rollUp(tree);
  const total = totalWeight(tree);
  const rest = remainder(tree);
  const over = total - 1 > 1e-9;

  const toggle = (id: string) =>
    setCollapsed((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  const closePop = (focusId?: string) => {
    setPop(null);
    if (focusId !== undefined) focusLater(focusId);
  };

  const onPopKey = (event: KeyboardEvent) => {
    if (event.key === "Escape" && pop !== null) {
      event.stopPropagation();
      const kind = pop.kind;
      closePop(`pf-${kind === "rename" ? "more" : kind}-${pop.id}`);
    }
  };

  const remove = (nodeId: string) => {
    onChange(removeNode(tree, nodeId));
    setPop(null);
    window.setTimeout(() => headingRef.current?.focus(), 0);
  };

  /** The sub line of an instrument: ticker, start year, tags. */
  const detail = (line: LibraryLine | undefined, inst: Instrument, showTicker = true): ReactNode => {
    if (inst.kind === "cash") {
      const year = yearOf(line?.first_date);
      return (
        <>
          Risk-free rate{year !== null ? <> · from {year}</> : null}
        </>
      );
    }
    if (inst.ticker === null) return <>No proxy yet</>;
    const isProxy = line !== undefined && line.proxy === inst.ticker;
    if (!isProxy || line === undefined) {
      return (
        <>
          {showTicker ? <b>{inst.ticker}</b> : null}
          {showTicker ? " · chosen by you" : "Chosen by you"}
          <span className="tag">swapped</span>
        </>
      );
    }
    const year = yearOf(line.first_date);
    const late = isShortHistory(line);
    return (
      <>
        {showTicker ? <b>{inst.ticker}</b> : <>Library proxy</>}
        {year !== null ? (
          <>
            {" · "}
            <span className={late ? "late" : undefined}>from {year}</span>
          </>
        ) : null}
        {line.proxy_kind === "listed_proxy" ? <span className="tag">listed proxy</span> : null}
        {late ? <span className="tag warn">short history</span> : null}
      </>
    );
  };

  const popRow = (kind: Pop["kind"], id: string, current: string, instRow: boolean): ReactNode => {
    if (pop === null || pop.kind !== kind || pop.id !== id) return null;
    return (
      // The keyboard handler only closes the row on Escape.
      // eslint-disable-next-line jsx-a11y/no-static-element-interactions
      <div className={instRow ? "t-row pop inst-pop" : "t-row pop"} onKeyDown={onPopKey}>
        {kind === "rename" ? (
          <RenamePop
            initial={current}
            onCancel={() => closePop(`pf-more-${id}`)}
            onSave={(name) => {
              onChange(id === tree.root.id ? renameTree(tree, name) : rename(tree, id, name));
              closePop(`pf-more-${id}`);
            }}
          />
        ) : (
          <TickerPop
            mode={kind}
            idBase={`${baseId}-${id}`}
            onCancel={() => closePop(`pf-${kind}-${id}`)}
            onPick={(ticker) => {
              if (kind === "swap") onChange(swapInstrument(tree, id, ticker));
              else onChange(addInstrument(tree, id, ticker));
              closePop(`pf-${kind}-${id}`);
            }}
          />
        )}
      </div>
    );
  };

  const weightCell = (inst: Instrument, name: string) => (
    <div className="wcell">
      <WeightInput
        value={inst.weight}
        label={`Weight of ${name}, percent`}
        onChange={(w) => onChange(setWeight(tree, inst.id, w))}
        onNudge={(steps) => onChange(nudge(tree, inst.id, steps))}
      />
    </div>
  );

  const shareBar = (weight: number, color: string) => (
    <div className="bar" aria-hidden="true">
      <div className="sbar" style={cssVars({ "--p": `${Math.min(100, weight * 100)}%`, "--c": color })}>
        <i />
      </div>
    </div>
  );

  const subRows = (sub: SubAssetClassGroup, color: string): ReactNode => {
    const line = library.get(sub.library_id);
    const subTotal = totals[sub.id] ?? 0;
    const single = sub.children.length === 1 ? sub.children[0] : undefined;
    if (single !== undefined) {
      return (
        <li key={sub.id}>
          <div className="t-row line">
            <div className="label">
              <div className="txt">
                <span className="nm">{sub.label}</span>
                <span className="sb">{detail(line, single)}</span>
              </div>
            </div>
            {weightCell(single, sub.label)}
            {shareBar(subTotal, color)}
            <div className="acts">
              <button
                type="button"
                id={`pf-swap-${single.id}`}
                className="ib"
                aria-label={`Swap the ticker of ${sub.label}`}
                aria-expanded={pop?.kind === "swap" && pop.id === single.id}
                disabled={single.kind === "cash"}
                onClick={() => setPop({ kind: "swap", id: single.id })}
              >
                <Icon name="swap" />
              </button>
              <button
                type="button"
                id={`pf-add-${sub.id}`}
                className="ib"
                aria-label={`Add an instrument to ${sub.label}`}
                aria-expanded={pop?.kind === "add" && pop.id === sub.id}
                onClick={() => setPop({ kind: "add", id: sub.id })}
              >
                <Icon name="plus" />
              </button>
              <RowMenu
                id={`pf-more-${sub.id}`}
                label={`Actions for ${sub.label}`}
                items={[
                  { label: "Rename", icon: "edit", onSelect: () => setPop({ kind: "rename", id: sub.id }) },
                  { label: "Remove", icon: "trash", danger: true, onSelect: () => remove(sub.id) },
                ]}
              />
            </div>
          </div>
          {popRow("swap", single.id, "", false)}
          {popRow("add", sub.id, "", false)}
          {popRow("rename", sub.id, sub.label, false)}
        </li>
      );
    }
    const proxyYear = yearOf(line?.first_date);
    return (
      <li key={sub.id}>
        <div className="t-row line multi">
          <div className="label">
            <div className="txt">
              <span className="nm">{sub.label}</span>
              <span className="sb">
                {sub.children.length} instruments
                {line?.proxy ? (
                  <>
                    {" · library proxy "}
                    <b>{line.proxy}</b>
                    {proxyYear !== null ? <>, from {proxyYear}</> : null}
                  </>
                ) : null}
              </span>
            </div>
          </div>
          <div className="wcell">
            <span className="ro">{pctText(subTotal)}</span>
          </div>
          {shareBar(subTotal, color)}
          <div className="acts">
            <RowMenu
              id={`pf-more-${sub.id}`}
              label={`Actions for ${sub.label}`}
              items={[
                { label: "Rename", icon: "edit", onSelect: () => setPop({ kind: "rename", id: sub.id }) },
                { label: "Remove line", icon: "trash", danger: true, onSelect: () => remove(sub.id) },
              ]}
            />
          </div>
        </div>
        {popRow("rename", sub.id, sub.label, false)}
        <ul>
          {sub.children.map((inst) => {
            const name = inst.label;
            const own = inst.ticker !== null && inst.label !== inst.ticker;
            return (
              <li key={inst.id}>
                <div className="t-row inst">
                  <div className="label">
                    <div className="txt">
                      <span className="nm">{name}</span>
                      <span className="sb">{detail(line, inst, own)}</span>
                    </div>
                  </div>
                  {weightCell(inst, name)}
                  {shareBar(inst.weight, color)}
                  <div className="acts">
                    <button
                      type="button"
                      id={`pf-swap-${inst.id}`}
                      className="ib"
                      aria-label={`Swap the ticker of ${name}`}
                      aria-expanded={pop?.kind === "swap" && pop.id === inst.id}
                      disabled={inst.kind === "cash"}
                      onClick={() => setPop({ kind: "swap", id: inst.id })}
                    >
                      <Icon name="swap" />
                    </button>
                    <RowMenu
                      id={`pf-more-${inst.id}`}
                      label={`Actions for ${name}`}
                      items={[
                        { label: "Rename", icon: "edit", onSelect: () => setPop({ kind: "rename", id: inst.id }) },
                        { label: "Remove", icon: "trash", danger: true, onSelect: () => remove(inst.id) },
                      ]}
                    />
                  </div>
                </div>
                {popRow("swap", inst.id, "", true)}
                {popRow("rename", inst.id, inst.label, true)}
              </li>
            );
          })}
        </ul>
        <div className="t-row add-inst">
          <div className="label">
            <button
              type="button"
              id={`pf-add-${sub.id}`}
              className="textbtn"
              aria-expanded={pop?.kind === "add" && pop.id === sub.id}
              onClick={() => setPop({ kind: "add", id: sub.id })}
            >
              <Icon name="plus" />
              instrument
              <span className="vh"> in {sub.label}</span>
            </button>
          </div>
        </div>
        {popRow("add", sub.id, "", true)}
      </li>
    );
  };

  return (
    <section className="panel tree-panel" aria-labelledby={`${baseId}-title`}>
      <div className="panel-head">
        <h2 id={`${baseId}-title`} tabIndex={-1} ref={headingRef}>
          Allocation
        </h2>
        <div className="pm">
          Type a weight, or press <kbd>↑</kbd> <kbd>↓</kbd> to nudge it by 0.5. Totals are read-only.
        </div>
      </div>
      <div className="t-head" aria-hidden="true">
        <span>Asset class, sub-asset class and instrument</span>
        <span className="r">Weight</span>
        <span>Share</span>
        <span />
      </div>
      {tree.root.children.length === 0 ? (
        <p className="tree-empty">No lines yet. Add a sub-asset class from the library to start.</p>
      ) : (
        <ul className="tree">
          {tree.root.children.map((ac) => {
            const color = assetClassColor(ac.label);
            const open = !collapsed.has(ac.id);
            const bodyId = `${baseId}-${ac.id}`;
            return (
              <li key={ac.id}>
                <div className="t-row group">
                  <div className="label">
                    <button
                      type="button"
                      className="caret"
                      aria-expanded={open}
                      aria-controls={bodyId}
                      aria-label={`${open ? "Collapse" : "Expand"} ${ac.label}`}
                      onClick={() => toggle(ac.id)}
                    >
                      <Icon name="caret" />
                    </button>
                    <span className="key-sq" aria-hidden="true" style={cssVars({ "--c": color })} />
                    <span className="nm">
                      {ac.label}
                      <span className="cnt">
                        {ac.children.length} {ac.children.length === 1 ? "line" : "lines"}
                      </span>
                    </span>
                  </div>
                  <div className="wcell">
                    <span className="ro">{pctText(totals[ac.id] ?? 0)}</span>
                  </div>
                  {shareBar(totals[ac.id] ?? 0, color)}
                  <div className="acts" />
                </div>
                <ul id={bodyId} className="group-body" hidden={!open}>
                  {ac.children.map((sub) => subRows(sub, color))}
                </ul>
              </li>
            );
          })}
        </ul>
      )}
      {rest > 0 ? (
        <div className="t-row unalloc">
          <div className="label">
            <span className="key-hatch" aria-hidden="true" />
            <div className="txt">
              <span className="nm">Unallocated</span>
              <span className="sb">Goes to USD cash when you run the backtest</span>
            </div>
          </div>
          <div className="wcell">
            <span className="ro">{pctText(rest)}</span>
          </div>
          <div className="bar" aria-hidden="true">
            <div className="sbar hatch" />
          </div>
          <div className="acts" />
        </div>
      ) : null}
      <div className="t-row total">
        <div className="label">
          <span className="nm">Total</span>
          {over ? <span className="sb"> · {pctText(total - 1)} over 100%</span> : null}
        </div>
        <div className="wcell">
          <span className="ro">{pctText(total)}</span>
        </div>
        <div className="bar" />
        <div className="acts" />
      </div>
      <div className="tree-foot">
        <button type="button" id={pickerButtonId} className="btn-outline" aria-haspopup="dialog" onClick={onOpenPicker}>
          <Icon name="plus" />
          Add sub-asset class
        </button>
        <span className="hint">
          From the library: {libraryCount.classes} asset classes, {libraryCount.lines} sub-asset classes.
        </span>
      </div>
    </section>
  );
}
