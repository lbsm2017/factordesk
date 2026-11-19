/**
 * Stand-in for the "Show statistics" switch state (the shell branch supplies the real one; same
 * names). Off by default; the integrator replaces this file.
 */
import type { ReactNode } from "react";

export function useShowStats(): boolean {
  return false;
}

export function StatsProvider({ children }: { children: ReactNode }) {
  return <>{children}</>;
}
