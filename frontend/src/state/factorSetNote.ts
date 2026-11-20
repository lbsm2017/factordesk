import { useState } from "react";
import { FACTOR_SET_LABELS } from "./factorSet";
import type { FactorSet } from "./factorSet";

/**
 * The polite sentence for a factor set change (`Factor set: Europe. Updating the report.`). It is
 * said from the choice until the run ends; the status line shows it while no step has started yet,
 * and the steps and "ready" sentences take over after that.
 */
export function useFactorSetNote(pending: boolean): [string, (next: FactorSet) => void] {
  const [note, setNote] = useState("");
  const [wasPending, setWasPending] = useState(pending);
  if (wasPending !== pending) {
    setWasPending(pending);
    if (!pending && note !== "") setNote("");
  }
  return [note, (next) => setNote(`Factor set: ${FACTOR_SET_LABELS[next]}. Updating the report.`)];
}
