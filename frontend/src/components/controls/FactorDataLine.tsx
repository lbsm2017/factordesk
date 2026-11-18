import type { FactorDataStatus } from "../../api/types";
import { Panel } from "../report/Panel";

export interface FactorDataLineProps {
  status: FactorDataStatus | undefined;
  refreshing: boolean;
  /** Result of the last refresh, announced politely. */
  message: string | null;
  onRefresh: () => void;
}

/** STUB (T4): fill in this file only. Props are fixed by T3. */
export function FactorDataLine(_props: FactorDataLineProps) {
  return <Panel id="factor-data" title="Factor data" />;
}
