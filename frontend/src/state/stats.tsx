import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { parseUrl, toSearch } from "./url";

/**
 * The "Show statistics" switch (dashboard spec DV6, design K.1). Off by default: plain words,
 * bars and verdicts. On: t-statistics, p-values, intervals, standard errors and VIF columns.
 *
 * The value lives in the URL as `stats=1`. A change replaces the history entry (a view
 * preference, not a navigation), and Back and Forward bring the value of their entry back.
 * Panels read it with `useShowStats()` only.
 */
interface StatsValue {
  on: boolean;
  setOn: (on: boolean) => void;
}

const StatsContext = createContext<StatsValue>({ on: false, setOn: () => undefined });

function fromUrl(): boolean {
  return parseUrl(window.location.search).stats;
}

export interface StatsProviderProps {
  children: ReactNode;
  /** Start value instead of the URL's (tests and the static demo page). */
  initial?: boolean;
}

export function StatsProvider({ children, initial }: StatsProviderProps) {
  const [on, setState] = useState<boolean>(() => initial ?? fromUrl());

  useEffect(() => {
    const onPop = () => setState(fromUrl());
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);

  const setOn = useCallback((next: boolean) => {
    setState(next);
    const search = toSearch({ ...parseUrl(window.location.search), stats: next });
    if (search !== window.location.search) {
      window.history.replaceState(null, "", `${window.location.pathname}${search}${window.location.hash}`);
    }
  }, []);

  const value = useMemo(() => ({ on, setOn }), [on, setOn]);
  return <StatsContext.Provider value={value}>{children}</StatsContext.Provider>;
}

/** True when the statistics columns are shown. Without a provider: false. */
export function useShowStats(): boolean {
  return useContext(StatsContext).on;
}

/** The value and its setter, for the switch in the sidebar. */
export function useStatsSwitch(): [boolean, (on: boolean) => void] {
  const { on, setOn } = useContext(StatsContext);
  return [on, setOn];
}
