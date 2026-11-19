import { useCombobox } from "downshift";
import { useEffect, useState } from "react";
import type { KeyboardEvent as ReactKeyboardEvent, MouseEvent } from "react";
import type { TickerSuggestion } from "../../api/types";
import { dateLong } from "../../format";

export interface TickerSearchProps {
  /** Ticker in the URL, shown in the field after a submit. */
  value: string;
  recent: string[];
  suggestions: TickerSuggestion[];
  /** Inline sentence for a client-side invalid ticker. */
  error: string | null;
  onQueryChange: (query: string) => void;
  /** Enter or a chosen suggestion; the text is not yet upper-cased or validated. */
  onSubmit: (text: string) => void;
  /** Focus the field on mount (the landing page). */
  focusOnMount?: boolean;
}

interface Row {
  ticker: string;
  note: string;
}

const INPUT_ID = "ticker-input";
const ERROR_ID = "ticker-error";

/** Input types that take no typed text: "/" from one of these still focuses the search field. */
const NON_TEXT_INPUTS = new Set(["radio", "checkbox", "button", "submit", "reset", "image", "range", "color", "file"]);

/** True when a key press came from a place where "/" is just a character. */
function isTextTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  if (target.isContentEditable) return true;
  const tag = target.tagName;
  if (tag === "INPUT") return !NON_TEXT_INPUTS.has((target as HTMLInputElement).type);
  return tag === "TEXTAREA" || tag === "SELECT";
}

/**
 * Ticker search (dashboard spec DB6.3): an upper-case combobox. An empty field lists the recent
 * tickers; text lists server suggestions. Enter submits the field's text, choosing a row submits
 * that ticker, Escape closes the list, and "/" focuses the field from anywhere outside a text field.
 */
export function TickerSearch({
  value,
  recent,
  suggestions,
  error,
  onQueryChange,
  onSubmit,
  focusOnMount = false,
}: TickerSearchProps) {
  const [text, setText] = useState(value);
  const [seen, setSeen] = useState(value);
  if (seen !== value) {
    setSeen(value);
    setText(value);
  }
  const [input, setInput] = useState<HTMLInputElement | null>(null);

  const typed = text.trim().toUpperCase();
  const rows: Row[] =
    typed === ""
      ? recent.map((ticker) => ({ ticker, note: "recent" }))
      : suggestions
          .filter((s) => s.ticker.toUpperCase().startsWith(typed))
          .map((s) => ({ ticker: s.ticker, note: `fetched ${dateLong(s.last_fetched)}` }));

  const { isOpen, highlightedIndex, getInputProps, getMenuProps, getItemProps, openMenu, closeMenu } = useCombobox<Row>({
    items: rows,
    itemToString: (row) => row?.ticker ?? "",
    inputValue: text,
    selectedItem: null,
    inputId: INPUT_ID,
    onInputValueChange: ({ inputValue }) => {
      const next = (inputValue ?? "").toUpperCase();
      setText(next);
      onQueryChange(next);
    },
    // Selection is handled below (click and Enter), so downshift never keeps a selected item or
    // rewrites the field when focus leaves.
    stateReducer: (state, { type, changes }) => ({
      ...changes,
      selectedItem: null,
      ...(type === useCombobox.stateChangeTypes.InputBlur ? { inputValue: state.inputValue } : {}),
    }),
  });

  useEffect(() => {
    if (focusOnMount) input?.focus();
  }, [focusOnMount, input]);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== "/" || event.ctrlKey || event.metaKey || event.altKey) return;
      if (isTextTarget(event.target)) return;
      event.preventDefault();
      input?.focus();
      input?.select();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [input]);

  const submit = (submitted: string) => {
    closeMenu();
    onSubmit(submitted);
  };
  const choose = (row: Row) => {
    setText(row.ticker);
    submit(row.ticker);
  };

  const showList = isOpen && rows.length > 0;
  const inputProps = getInputProps({
    ref: setInput,
    type: "text",
    autoComplete: "off",
    autoCapitalize: "characters",
    spellCheck: false,
    maxLength: 12,
    "aria-invalid": error !== null,
    ...(error !== null ? { "aria-describedby": ERROR_ID } : {}),
    onFocus: () => {
      if (!isOpen) openMenu();
    },
    onKeyDown: (event: ReactKeyboardEvent<HTMLInputElement>) => {
      if (event.key === "Enter") {
        event.preventDefault();
        (event as unknown as { preventDownshiftDefault: boolean }).preventDownshiftDefault = true;
        const row = highlightedIndex >= 0 ? rows[highlightedIndex] : undefined;
        if (row) choose(row);
        else submit(text);
      }
      if (event.key === "Escape" && !isOpen) {
        // Closed list: Escape keeps the typed text (downshift would clear it).
        (event as unknown as { preventDownshiftDefault: boolean }).preventDownshiftDefault = true;
      }
    },
  });

  return (
    <div className="ctl-ticker">
      <form
        className="ctl-search"
        role="search"
        onSubmit={(event) => {
          event.preventDefault();
          submit(text);
        }}
      >
        <label className="side-label" htmlFor={INPUT_ID}>
          Ticker
        </label>
        <div className="ctl-combo">
          <input {...inputProps} />
          <ul
            {...getMenuProps({ "aria-label": typed === "" ? "Recent tickers" : "Matching tickers" })}
            className="ctl-list"
            hidden={!showList}
          >
            {showList
              ? rows.map((row, index) => (
                  <li
                    key={row.ticker}
                    {...getItemProps({
                      item: row,
                      index,
                      onClick: (event: MouseEvent<HTMLLIElement>) => {
                        (event as unknown as { preventDownshiftDefault: boolean }).preventDownshiftDefault = true;
                        choose(row);
                      },
                    })}
                    className={index === highlightedIndex ? "ctl-opt on" : "ctl-opt"}
                  >
                    <span className="ctl-sym">{row.ticker}</span>
                    <span className="ctl-note">{row.note}</span>
                  </li>
                ))
              : null}
          </ul>
        </div>
        <button type="submit" className="btn">
          Factor it
        </button>
      </form>
      {error !== null ? (
        <p className="ctl-err" id={ERROR_ID} role="alert">
          {error}
        </p>
      ) : null}
    </div>
  );
}
