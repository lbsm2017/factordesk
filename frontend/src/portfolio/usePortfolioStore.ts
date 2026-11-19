import { useCallback, useEffect, useReducer } from "react";
import { loadStore, newPortfolioId, reduce, saveStore } from "./store";
import type { SavedPortfolio, StoreState } from "./store";
import type { PortfolioTree } from "./tree";

export interface PortfolioStore {
  state: StoreState;
  active: SavedPortfolio | null;
  /** Save a new portfolio and open it; returns its id. */
  create: (tree: PortfolioTree) => string;
  select: (id: string) => void;
  edit: (id: string, tree: PortfolioTree) => void;
  duplicate: (id: string) => void;
  rename: (id: string, name: string) => void;
  remove: (id: string) => void;
  undo: () => void;
  dismissUndo: () => void;
}

/** The saved portfolios, read from browser storage once and saved again after every change. */
export function usePortfolioStore(): PortfolioStore {
  const [state, dispatch] = useReducer(reduce, undefined, () => loadStore());
  const { portfolios, activeId } = state;

  useEffect(() => {
    saveStore({ portfolios, activeId, deleted: null });
  }, [portfolios, activeId]);

  const create = useCallback((tree: PortfolioTree) => {
    const id = newPortfolioId();
    dispatch({ type: "create", id, tree });
    return id;
  }, []);
  const select = useCallback((id: string) => dispatch({ type: "select", id }), []);
  const edit = useCallback((id: string, tree: PortfolioTree) => dispatch({ type: "edit", id, tree }), []);
  const duplicate = useCallback((id: string) => dispatch({ type: "duplicate", id, newId: newPortfolioId() }), []);
  const rename = useCallback((id: string, name: string) => dispatch({ type: "rename", id, name }), []);
  const remove = useCallback((id: string) => dispatch({ type: "delete", id }), []);
  const undo = useCallback(() => dispatch({ type: "undo" }), []);
  const dismissUndo = useCallback(() => dispatch({ type: "dismissUndo" }), []);

  const active = portfolios.find((p) => p.id === activeId) ?? null;
  return { state, active, create, select, edit, duplicate, rename, remove, undo, dismissUndo };
}
