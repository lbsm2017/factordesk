/**
 * The saved portfolios of the composer: a reducer for the list (create, select, edit, duplicate,
 * rename, delete with undo) and the browser-storage round trip. Storage is one JSON value under a
 * versioned key; every read and write is wrapped, so a blocked or full storage never breaks the
 * page, it only stops saving.
 */
import { renameTree } from "./composer";
import { TREE_VERSION } from "./tree";
import type { PortfolioTree } from "./tree";

export const STORAGE_KEY = "factordesk.portfolios.v1";
const STORE_VERSION = 1;
export const MAX_SAVED = 50;

export interface SavedPortfolio {
  id: string;
  tree: PortfolioTree;
}

/** What Undo brings back: the deleted portfolio and its place in the list. */
export interface Deleted {
  item: SavedPortfolio;
  index: number;
}

export interface StoreState {
  portfolios: SavedPortfolio[];
  activeId: string | null;
  /** The last deletion, or null. Never saved to storage. */
  deleted: Deleted | null;
}

export const EMPTY_STORE: StoreState = { portfolios: [], activeId: null, deleted: null };

export type StoreAction =
  | { type: "create"; id: string; tree: PortfolioTree }
  | { type: "select"; id: string }
  | { type: "edit"; id: string; tree: PortfolioTree }
  | { type: "duplicate"; id: string; newId: string }
  | { type: "rename"; id: string; name: string }
  | { type: "delete"; id: string }
  | { type: "undo" }
  | { type: "dismissUndo" };

/** The name of a copy: "Growth copy", then "Growth copy 2", and so on, never one that is taken. */
export function copyName(name: string, taken: readonly string[]): string {
  const base = name.replace(/ copy( \d+)?$/, "");
  let candidate = `${base} copy`;
  for (let n = 2; taken.includes(candidate); n += 1) candidate = `${base} copy ${n}`;
  return candidate.slice(0, 80);
}

/** The name clipped to the 1 to 80 characters the tree allows; blank text is refused (null). */
export function cleanName(text: string): string | null {
  const name = text.trim().slice(0, 80).trim();
  return name === "" ? null : name;
}

export function reduce(state: StoreState, action: StoreAction): StoreState {
  const { portfolios } = state;
  switch (action.type) {
    case "create": {
      if (portfolios.length >= MAX_SAVED) return state;
      return { portfolios: [...portfolios, { id: action.id, tree: action.tree }], activeId: action.id, deleted: null };
    }
    case "select":
      return portfolios.some((p) => p.id === action.id) ? { ...state, activeId: action.id } : state;
    case "edit":
      return {
        ...state,
        portfolios: portfolios.map((p) => (p.id === action.id ? { ...p, tree: action.tree } : p)),
      };
    case "duplicate": {
      const source = portfolios.find((p) => p.id === action.id);
      if (source === undefined || portfolios.length >= MAX_SAVED) return state;
      const name = copyName(source.tree.name, portfolios.map((p) => p.tree.name));
      const copy = { id: action.newId, tree: renameTree(source.tree, name) };
      const at = portfolios.indexOf(source) + 1;
      return { portfolios: [...portfolios.slice(0, at), copy, ...portfolios.slice(at)], activeId: copy.id, deleted: null };
    }
    case "rename": {
      const name = cleanName(action.name);
      if (name === null) return state;
      return {
        ...state,
        portfolios: portfolios.map((p) => (p.id === action.id ? { ...p, tree: renameTree(p.tree, name) } : p)),
      };
    }
    case "delete": {
      const index = portfolios.findIndex((p) => p.id === action.id);
      const item = portfolios[index];
      if (item === undefined) return state;
      const rest = portfolios.filter((p) => p.id !== action.id);
      const activeId =
        state.activeId === action.id ? (rest[Math.min(index, rest.length - 1)]?.id ?? null) : state.activeId;
      return { portfolios: rest, activeId, deleted: { item, index } };
    }
    case "undo": {
      const { deleted } = state;
      if (deleted === null) return state;
      const at = Math.min(deleted.index, portfolios.length);
      return {
        portfolios: [...portfolios.slice(0, at), deleted.item, ...portfolios.slice(at)],
        activeId: deleted.item.id,
        deleted: null,
      };
    }
    case "dismissUndo":
      return state.deleted === null ? state : { ...state, deleted: null };
  }
}

// ------------------------------------------------------------------------------------ storage

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

/** A light shape check: enough that the screen can draw the tree. The run does the full check. */
export function looksLikeTree(value: unknown): value is PortfolioTree {
  if (!isObject(value) || value["version"] !== TREE_VERSION) return false;
  if (typeof value["name"] !== "string" || typeof value["cost_bps"] !== "number") return false;
  const root = value["root"];
  if (!isObject(root) || typeof root["id"] !== "string" || !Array.isArray(root["children"])) return false;
  return root["children"].every(
    (ac) =>
      isObject(ac) &&
      typeof ac["id"] === "string" &&
      typeof ac["label"] === "string" &&
      Array.isArray(ac["children"]) &&
      ac["children"].every(
        (sub) =>
          isObject(sub) &&
          typeof sub["id"] === "string" &&
          typeof sub["label"] === "string" &&
          typeof sub["library_id"] === "string" &&
          Array.isArray(sub["children"]) &&
          sub["children"].every(
            (inst) =>
              isObject(inst) &&
              typeof inst["id"] === "string" &&
              typeof inst["label"] === "string" &&
              typeof inst["weight"] === "number" &&
              (inst["kind"] === "holding" || inst["kind"] === "cash") &&
              (inst["ticker"] === null || typeof inst["ticker"] === "string"),
          ),
      ),
  );
}

/** The text that goes into storage. */
export function serialise(state: StoreState): string {
  return JSON.stringify({ version: STORE_VERSION, activeId: state.activeId, portfolios: state.portfolios });
}

/** Read a stored text back; anything that is not a valid store gives the empty store, and a bad entry is dropped. */
export function parseStored(text: string | null): StoreState {
  if (text === null) return EMPTY_STORE;
  let data: unknown;
  try {
    data = JSON.parse(text);
  } catch {
    return EMPTY_STORE;
  }
  if (!isObject(data) || data["version"] !== STORE_VERSION || !Array.isArray(data["portfolios"])) return EMPTY_STORE;
  const seen = new Set<string>();
  const portfolios: SavedPortfolio[] = [];
  for (const entry of data["portfolios"] as unknown[]) {
    if (!isObject(entry) || typeof entry["id"] !== "string" || seen.has(entry["id"])) continue;
    if (!looksLikeTree(entry["tree"])) continue;
    seen.add(entry["id"]);
    portfolios.push({ id: entry["id"], tree: entry["tree"] });
  }
  const wanted = data["activeId"];
  const activeId = typeof wanted === "string" && seen.has(wanted) ? wanted : (portfolios[0]?.id ?? null);
  return { portfolios: portfolios.slice(0, MAX_SAVED), activeId, deleted: null };
}

export function loadStore(storage: Pick<Storage, "getItem"> | null = browserStorage()): StoreState {
  if (storage === null) return EMPTY_STORE;
  try {
    return parseStored(storage.getItem(STORAGE_KEY));
  } catch {
    return EMPTY_STORE;
  }
}

/** Save the portfolios; false when the browser refused (private window, full or blocked storage). */
export function saveStore(state: StoreState, storage: Pick<Storage, "setItem"> | null = browserStorage()): boolean {
  if (storage === null) return false;
  try {
    storage.setItem(STORAGE_KEY, serialise(state));
    return true;
  } catch {
    return false;
  }
}

/** `window.localStorage`, or null when even touching it throws. */
export function browserStorage(): Storage | null {
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

let counter = 0;
/** A new id for a saved portfolio. */
export function newPortfolioId(): string {
  counter += 1;
  try {
    return crypto.randomUUID();
  } catch {
    return `p${Date.now().toString(36)}${counter}`;
  }
}
