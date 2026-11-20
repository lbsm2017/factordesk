/**
 * Portfolio CSV: export a tree to text and import it back. Pure functions, no React and no I/O.
 *
 *   # name: Balanced SAA
 *   # cost_bps: 10
 *   asset_class,sub_asset_class,line_id,ticker,weight_pct
 *   Cash,USD Cash,cash_usd,RF,2
 *   Equities,Equity N. America - Large Cap,eq_na_large,IVV,33
 *
 * One row per instrument. `weight_pct` is in percent. A cash line has the ticker `RF`, as in the
 * library. The import builds the tree with the same tree functions and the same `validate` the
 * composer uses, and reports every bad row with its CSV line number. The export keeps the
 * structure, tickers, weights, name and cost. The ids are made again on import (`<line>_i_1`, ...)
 * and a hand-made label of a group or instrument is not saved, so the tree comes back the same
 * except for those two things. The group names in the file are for the reader: the library line
 * gives them back.
 */
import { addInstrument, addLine, emptyTree, instruments, validate, MAX_COST_BPS } from "./tree";
import type { Instrument, LibraryLineLike, PortfolioTree } from "./tree";

export const CSV_COLUMNS = ["asset_class", "sub_asset_class", "line_id", "ticker", "weight_pct"] as const;
type Column = (typeof CSV_COLUMNS)[number];
/** The ticker of a USD cash line, as in the library. */
export const CASH_TICKER = "RF";
/** The trading cost of a file that gives none: the same as the composer presets. */
export const DEFAULT_COST_BPS = 10;
/** The byte order mark that Excel writes and expects at the start of a UTF-8 file. */
export const BOM = String.fromCharCode(0xfeff);
const MAX_NAME = 80;
const TICKER_RE = /^[A-Za-z0-9.^=-]{1,12}$/;
const NUMBER_RE = /^[+-]?(\d+\.?\d*|\.\d+)$/;
/** Decimal places of a percent weight in the file. */
const PCT_DECIMALS = 10;

export interface CsvError {
  /** The CSV line (the first line is 1), or null for a problem of the whole file. */
  line: number | null;
  message: string;
}

export type CsvImport = { ok: true; tree: PortfolioTree } | { ok: false; errors: CsvError[] };

/** "Line 7: weight is not a number", or the bare message for a problem of the whole file. */
export function formatCsvError(error: CsvError): string {
  return error.line === null ? error.message : `Line ${error.line}: ${error.message}`;
}

// ------------------------------------------------------------------------------------ export

function quoted(value: string): string {
  return /[",\n\r]/.test(value) || value !== value.trim() ? `"${value.replace(/"/g, '""')}"` : value;
}

/** A weight as percent text with no float noise and no trailing zeros: 0.33 gives "33". */
export function weightToPct(weight: number): string {
  const text = (weight * 100).toFixed(PCT_DECIMALS);
  return text.replace(/0+$/, "").replace(/\.$/, "");
}

/** The tree as CSV text (LF line endings, no byte order mark). */
export function treeToCsv(tree: PortfolioTree): string {
  const oneLine = (text: string) => text.replace(/[\r\n]+/g, " ");
  const out = [`# name: ${oneLine(tree.name)}`, `# cost_bps: ${tree.cost_bps}`, CSV_COLUMNS.join(",")];
  for (const ac of tree.root.children) {
    for (const sub of ac.children) {
      for (const inst of sub.children) {
        out.push(
          [
            quoted(ac.label),
            quoted(sub.label),
            quoted(sub.library_id),
            quoted(inst.kind === "cash" ? CASH_TICKER : (inst.ticker ?? "")),
            weightToPct(inst.weight),
          ].join(","),
        );
      }
    }
  }
  return `${out.join("\n")}\n`;
}

// ------------------------------------------------------------------------------------ parsing

type Item =
  | { kind: "comment"; line: number; text: string }
  | { kind: "row"; line: number; fields: string[] };

/**
 * Split CSV text into comment lines (starting with #) and rows of fields. Handles quoted fields
 * with commas, doubled quotes and line breaks. A row has the line number it starts on. Blank rows
 * are skipped.
 */
function tokenise(raw: string): { items: Item[]; errors: CsvError[] } {
  const text = (raw.startsWith(BOM) ? raw.slice(1) : raw).replace(/\r\n?/g, "\n");
  const items: Item[] = [];
  const errors: CsvError[] = [];
  const n = text.length;
  let i = 0;
  let line = 1;
  while (i < n) {
    if (text[i] === "\n") {
      i += 1;
      line += 1;
      continue;
    }
    if (text[i] === "#") {
      let j = i;
      while (j < n && text[j] !== "\n") j += 1;
      items.push({ kind: "comment", line, text: text.slice(i, j) });
      i = j;
      continue;
    }
    const startLine = line;
    const fields: string[] = [];
    let broken = false;
    for (;;) {
      let value = "";
      if (text[i] === '"') {
        const openLine = line;
        i += 1;
        let closed = false;
        while (i < n) {
          const c = text[i] as string;
          if (c === '"') {
            if (text[i + 1] === '"') {
              value += '"';
              i += 2;
              continue;
            }
            i += 1;
            closed = true;
            break;
          }
          if (c === "\n") line += 1;
          value += c;
          i += 1;
        }
        if (!closed) {
          errors.push({ line: openLine, message: "a quoted field is not closed" });
          return { items, errors };
        }
        if (i < n && text[i] !== "," && text[i] !== "\n") {
          errors.push({ line, message: "unexpected text after a closing quote" });
          while (i < n && text[i] !== "\n") i += 1;
          broken = true;
        }
      } else {
        const from = i;
        while (i < n && text[i] !== "," && text[i] !== "\n") i += 1;
        value = text.slice(from, i);
      }
      fields.push(value.trim());
      if (broken || i >= n) break;
      if (text[i] === ",") {
        i += 1;
        continue;
      }
      break; // a line break
    }
    if (i < n && text[i] === "\n") {
      i += 1;
      line += 1;
    }
    if (!broken && !fields.every((f) => f === "")) items.push({ kind: "row", line: startLine, fields });
  }
  return { items, errors };
}

/** Percent text ("12", "12.5", "12,5", "12 %") as a decimal fraction; null when it is not a number. */
function parseWeightPct(text: string): number | null {
  const cleaned = text.replace(/%$/, "").trim().replace(",", ".");
  if (!NUMBER_RE.test(cleaned)) return null;
  const pct = Number(cleaned);
  return Number.isFinite(pct) ? Math.round(pct * 10 ** PCT_DECIMALS) / 10 ** (PCT_DECIMALS + 2) : null;
}

function capitalise(text: string): string {
  return `${text.charAt(0).toUpperCase()}${text.slice(1)}`;
}

interface Row {
  libraryId: string;
  ticker: string | null;
  cash: boolean;
  weight: number;
}

function withRow(inst: Instrument, row: Row): Instrument {
  if (row.cash) return { ...inst, kind: "cash", ticker: null, label: "Risk-free rate", weight: row.weight };
  return { ...inst, kind: "holding", ticker: row.ticker, label: row.ticker ?? "No proxy yet", weight: row.weight };
}

/**
 * Read CSV text into a tree. Every row is checked and every problem comes back with its line
 * number; the tree is built only when there is none. `fallbackName` is the name when the file has
 * no `# name:` line.
 */
export function parsePortfolioCsv(
  text: string,
  library: readonly LibraryLineLike[],
  fallbackName: string,
): CsvImport {
  const { items, errors } = tokenise(text);
  const byId = new Map(library.map((l) => [l.id, l]));
  let name = fallbackName.trim();
  let cost = DEFAULT_COST_BPS;
  let header: { index: Record<string, number>; width: number } | null = null;
  const rows: Row[] = [];

  for (const item of items) {
    if (item.kind === "comment") {
      const match = /^#\s*(name|cost_bps)\s*:\s*(.*)$/i.exec(item.text);
      if (match === null) continue;
      const value = (match[2] ?? "").trim();
      if ((match[1] ?? "").toLowerCase() === "name") {
        if (value.length > MAX_NAME) errors.push({ line: item.line, message: `name is longer than ${MAX_NAME} characters` });
        else if (value !== "") name = value;
      } else if (!NUMBER_RE.test(value)) {
        errors.push({ line: item.line, message: "cost_bps is not a number" });
      } else if (Number(value) < 0 || Number(value) > MAX_COST_BPS) {
        errors.push({ line: item.line, message: `cost_bps must be between 0 and ${MAX_COST_BPS}` });
      } else {
        cost = Number(value);
      }
      continue;
    }
    if (header === null) {
      const index: Record<string, number> = {};
      item.fields.forEach((f, k) => {
        const key = f.toLowerCase();
        if (!(key in index)) index[key] = k;
      });
      const missing = CSV_COLUMNS.filter((c) => !(c in index));
      if (missing.length > 0) {
        errors.push({ line: item.line, message: `the header row is missing ${missing.join(", ")}` });
        return { ok: false, errors };
      }
      header = { index, width: item.fields.length };
      continue;
    }
    const { index, width } = header;
    if (item.fields.length !== width) {
      errors.push({
        line: item.line,
        message: `expected ${width} columns but found ${item.fields.length} (a field with a comma needs quotes)`,
      });
      continue;
    }
    const get = (column: Column) => item.fields[index[column] as number] ?? "";
    const before = errors.length;
    const libraryId = get("line_id");
    const line = byId.get(libraryId);
    if (libraryId === "") {
      errors.push({ line: item.line, message: "line_id is missing" });
    } else if (line === undefined) {
      errors.push({ line: item.line, message: `line_id ${JSON.stringify(libraryId)} is not in the Asset Class Library` });
    }
    const tickerText = get("ticker");
    const cash = tickerText.toUpperCase() === CASH_TICKER;
    const ticker = cash || tickerText === "" ? null : tickerText;
    if (cash && line !== undefined && line.proxy_kind !== "risk_free") {
      errors.push({ line: item.line, message: `ticker ${CASH_TICKER} (the risk-free rate) is only for a cash line` });
    }
    if (ticker !== null && !TICKER_RE.test(ticker)) {
      errors.push({ line: item.line, message: `ticker ${JSON.stringify(ticker)} is not a valid ticker` });
    }
    const weightText = get("weight_pct");
    const weight = parseWeightPct(weightText);
    if (weight === null) {
      errors.push({ line: item.line, message: weightText === "" ? "weight is missing" : "weight is not a number" });
    } else if (weight < 0 || weight > 1) {
      errors.push({ line: item.line, message: "weight must be from 0 to 100" });
    } else if (!cash && ticker === null && weight > 0) {
      errors.push({ line: item.line, message: "a line with no ticker cannot take a weight" });
    }
    if (errors.length === before && weight !== null) rows.push({ libraryId, ticker, cash, weight });
  }

  if (header === null && errors.length === 0) {
    errors.push({ line: null, message: `The file has no header row. Expected ${CSV_COLUMNS.join(",")}.` });
  }
  if (errors.length > 0) return { ok: false, errors };

  // Build with the tree functions, then give each new instrument its ticker, kind and weight.
  let tree = emptyTree(name === "" ? "Imported portfolio" : name, cost);
  const byInstrument = new Map<string, Row>();
  for (const row of rows) {
    const line = byId.get(row.libraryId) as LibraryLineLike;
    const exists = tree.root.children.some((ac) => ac.children.some((s) => s.library_id === line.id));
    const known = new Set(instruments(tree).map((i) => i.id));
    tree = exists ? addInstrument(tree, `sub_${line.id}`, row.ticker ?? "") : addLine(tree, line);
    const added = instruments(tree).find((i) => !known.has(i.id));
    if (added !== undefined) byInstrument.set(added.id, row);
  }
  tree = {
    ...tree,
    root: {
      ...tree.root,
      children: tree.root.children.map((ac) => ({
        ...ac,
        children: ac.children.map((sub) => ({
          ...sub,
          children: sub.children.map((inst) => {
            const row = byInstrument.get(inst.id);
            return row === undefined ? inst : withRow(inst, row);
          }),
        })),
      })),
    },
  };

  const problems = validate(tree).errors;
  if (problems.length > 0) {
    return { ok: false, errors: problems.map((message) => ({ line: null, message: `${capitalise(message)}.` })) };
  }
  return { ok: true, tree };
}

/** A name that no saved portfolio uses: "Growth", then "Growth (2)", "Growth (3)", and so on. */
export function uniqueName(name: string, taken: readonly string[]): string {
  if (!taken.includes(name)) return name;
  for (let n = 2; ; n += 1) {
    const suffix = ` (${n})`;
    const candidate = `${name.slice(0, MAX_NAME - suffix.length)}${suffix}`;
    if (!taken.includes(candidate)) return candidate;
  }
}
