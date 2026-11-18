import { useCallback, useEffect, useState } from "react";
import { applyPatch, parseUrl, toSearch } from "./url";
import type { UrlState } from "./url";

function currentSearch(): string {
  return window.location.search;
}

function pathWith(search: string): string {
  return `${window.location.pathname}${search}${window.location.hash}`;
}

/**
 * The URL is the state (dashboard spec DB6.1). Invalid values in the first URL are dropped and the
 * cleaned URL replaces the current entry; a commit pushes an entry; Back and Forward come in
 * through `popstate`.
 */
export function useUrlState(): [UrlState, (patch: Partial<UrlState>) => void] {
  const [state, setState] = useState<UrlState>(() => parseUrl(currentSearch()));

  useEffect(() => {
    const cleaned = toSearch(parseUrl(currentSearch()));
    if (cleaned !== currentSearch()) window.history.replaceState(null, "", pathWith(cleaned));
    const onPop = () => setState(parseUrl(currentSearch()));
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);

  const commit = useCallback((patch: Partial<UrlState>) => {
    const next = applyPatch(parseUrl(currentSearch()), patch);
    const search = toSearch(next);
    if (search !== toSearch(parseUrl(currentSearch()))) window.history.pushState(null, "", pathWith(search));
    setState(next);
  }, []);

  return [state, commit];
}
