import type { FactorDataStatus } from "../../api/types";
import { dateLong } from "../../format";

export interface FactorDataLineProps {
  status: FactorDataStatus | undefined;
  refreshing: boolean;
  /** Result of the last refresh, announced politely. */
  message: string | null;
  onRefresh: () => void;
}

function sentence(status: FactorDataStatus | undefined): string {
  if (status === undefined) return "Checking the factor data.";
  if (!status.available || status.last_date === null) {
    return "No factor data is stored yet. It downloads with your first report.";
  }
  return `Factor data ends ${dateLong(status.last_date)}, so later dates cannot be chosen.`;
}

/** Where the factor data ends, plus a quiet button that asks the server for a newer file. */
export function FactorDataLine({ status, refreshing, message, onRefresh }: FactorDataLineProps) {
  return (
    <p className="ctl-factors">
      <span>{sentence(status)}</span>{" "}
      <button type="button" className="btn-quiet" onClick={onRefresh} disabled={refreshing}>
        {refreshing ? "Checking for newer factor data" : "Check for newer factor data"}
      </button>{" "}
      <span className="ctl-msg" role="status" aria-live="polite">
        {message ?? ""}
      </span>
    </p>
  );
}
