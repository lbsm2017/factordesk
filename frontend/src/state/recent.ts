import { useSyncExternalStore } from "react";
import { checkTicker } from "./url";

/** Recent tickers (dashboard spec DB6.3): `localStorage` key `factordesk.recent`, 8, newest first. */
export const RECENT_KEY = "factordesk.recent";
export const RECENT_MAX = 8;

const EMPTY: string[] = [];
let cache: string[] | null = null;
const listeners = new Set<() => void>();

/** Every storage access is wrapped: private windows and blocked site data throw. */
function read(): string[] {
  try {
    const raw = window.localStorage.getItem(RECENT_KEY);
    if (raw === null) return EMPTY;
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) return EMPTY;
    const out: string[] = [];
    for (const item of parsed) {
      if (typeof item !== "string") continue;
      const checked = checkTicker(item);
      if (checked.ok && !out.includes(checked.ticker)) out.push(checked.ticker);
    }
    return out.slice(0, RECENT_MAX);
  } catch {
    return EMPTY;
  }
}

function write(list: string[]): void {
  try {
    window.localStorage.setItem(RECENT_KEY, JSON.stringify(list));
  } catch {
    /* storage is a convenience: the list still works for this page view */
  }
}

export function getRecent(): string[] {
  cache ??= read();
  return cache;
}

/** Put a ticker first; call only after a successful report. */
export function addRecent(ticker: string): void {
  const upper = ticker.toUpperCase();
  const current = getRecent();
  if (current[0] === upper) return;
  cache = [upper, ...current.filter((t) => t !== upper)].slice(0, RECENT_MAX);
  write(cache);
  listeners.forEach((fn) => fn());
}

/** Forget the in-memory copy so the next read goes to storage again (tests, and the `storage` event). */
export function resetRecentCache(): void {
  cache = null;
  listeners.forEach((fn) => fn());
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  const onStorage = (event: StorageEvent) => {
    if (event.key === RECENT_KEY || event.key === null) resetRecentCache();
  };
  window.addEventListener("storage", onStorage);
  return () => {
    listeners.delete(listener);
    window.removeEventListener("storage", onStorage);
  };
}

export function useRecent(): string[] {
  return useSyncExternalStore(subscribe, getRecent, () => EMPTY);
}
