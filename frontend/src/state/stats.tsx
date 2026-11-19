/**
 * Stand-in of the "Show statistics" state (dashboard v2). The shell branch replaces this file with
 * the version that reads the URL; panels only call `useShowStats()`.
 */
import { createContext, useContext } from "react";
import type { ReactNode } from "react";

const StatsContext = createContext(false);

export function StatsProvider({ value = false, children }: { value?: boolean; children?: ReactNode }) {
  return <StatsContext.Provider value={value}>{children}</StatsContext.Provider>;
}

/** True when the Show statistics switch is on. */
export function useShowStats(): boolean {
  return useContext(StatsContext);
}
