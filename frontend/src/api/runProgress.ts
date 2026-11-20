/**
 * Progress of the report runs: the step events each run has received, kept outside React Query so
 * a query function or a mutation can report into it and any component can read it. One entry per
 * run key; a new run under the same key starts from an empty entry.
 */
import { useSyncExternalStore } from "react";
import type { ProgressStep, ProgressStepId } from "./types";

export interface RunProgress {
  /** The step events in the order they arrived. */
  steps: readonly ProgressStep[];
  /** The stream could not be used, so the run goes on without steps. */
  plain: boolean;
}

export const NO_PROGRESS: RunProgress = { steps: [], plain: false };

const runs = new Map<string, RunProgress>();
const listeners = new Set<() => void>();

function publish(key: string, next: RunProgress): void {
  runs.set(key, next);
  for (const listener of [...listeners]) listener();
}

/** A new run under `key`: the earlier steps are dropped. */
export function startRun(key: string): void {
  publish(key, NO_PROGRESS);
}

/** The run ended with a report: its steps are no longer needed (a failed run keeps them for the error page). */
export function clearRun(key: string): void {
  if (runs.delete(key)) for (const listener of [...listeners]) listener();
}

export function recordStep(key: string, step: ProgressStep): void {
  const now = runs.get(key) ?? NO_PROGRESS;
  publish(key, { ...now, steps: [...now.steps, step] });
}

export function recordFallback(key: string): void {
  publish(key, { steps: [], plain: true });
}

export function getRunProgress(key: string | null): RunProgress {
  return (key !== null ? runs.get(key) : undefined) ?? NO_PROGRESS;
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

/** The progress of the run under `key`; empty when there is none. */
export function useRunProgress(key: string | null): RunProgress {
  return useSyncExternalStore(
    subscribe,
    () => getRunProgress(key),
    () => NO_PROGRESS,
  );
}

/** The queries and mutations of the three modes record under these keys (a report query uses its query key). */
export const UPLOAD_RUN = "run:upload";
export const PORTFOLIO_RUN = "run:portfolio";

/** The run key of a report query. */
export function reportRunKey(queryKey: readonly unknown[]): string {
  return `report:${JSON.stringify(queryKey)}`;
}

// ---- Step rows: what the step card shows --------------------------------------------------------

export type StepState = "done" | "running" | "waiting" | "failed" | "not-run";

export interface StepRow {
  id: ProgressStepId | null;
  label: string;
  state: StepState;
}

export interface RunView {
  rows: StepRow[];
  /** Steps finished: the bar width is `done / total`. */
  done: number;
  total: number;
  /** The step that is running or that failed, counted from 1; 0 before the first event. */
  current: number;
  currentLabel: string | null;
}

/** The label of each step, used for the steps that have not been announced yet. */
export const STEP_LABELS: Readonly<Record<ProgressStepId, string>> = {
  prices: "Downloading prices",
  fx: "Loading exchange rates",
  factors: "Loading factor data",
  models: "Fitting the models",
  sections: "Building the sections",
};

const ORDER = Object.keys(STEP_LABELS) as ProgressStepId[];

/** The steps a run is expected to have, in order: an upload has no prices; exchange rates only in euros. */
export function expectedPlan({ prices, fx }: { prices: boolean; fx: boolean }): ProgressStepId[] {
  return ORDER.filter((id) => (id !== "prices" || prices) && (id !== "fx" || fx));
}

/**
 * The rows of the step card. The events decide: the latest one is the step that runs (or failed),
 * the steps before it are done (a skipped step is done too), the ones after it wait (or were not
 * run). A step that has not been announced yet takes its name from the expected plan; the total
 * comes from the events once there is one.
 */
export function runView(progress: RunProgress, plan: readonly ProgressStepId[], failed = false): RunView {
  if (progress.plain) return { rows: [], done: 0, total: 0, current: 0, currentLabel: null };
  const last = progress.steps.at(-1);
  const total = last?.total ?? plan.length;
  const byIndex = new Map(progress.steps.map((s) => [s.index, s]));
  const seen = new Set(progress.steps.map((s) => s.step));
  const lastId = last?.step;
  const rest = plan.filter((id) => !seen.has(id) && (lastId === undefined || ORDER.indexOf(id) > ORDER.indexOf(lastId)));
  let next = 0;
  const current = last?.index ?? 0;
  const rows: StepRow[] = [];
  for (let index = 1; index <= total; index++) {
    const event = byIndex.get(index);
    let id: ProgressStepId | null = event?.step ?? null;
    let label = event?.label ?? "";
    if (event === undefined) {
      const fill = rest[next++];
      if (fill !== undefined) {
        id = fill;
        label = STEP_LABELS[fill];
      } else {
        label = `Step ${index}`;
      }
    }
    const state: StepState =
      index < current ? "done" : index === current ? (failed ? "failed" : "running") : failed ? "not-run" : "waiting";
    rows.push({ id, label, state });
  }
  const done = Math.max(0, current - 1);
  return { rows, done, total, current, currentLabel: rows[current - 1]?.label ?? null };
}

/** The bar fill, 0 to 1: finished steps over all steps, never under 4%. */
export function barFraction(view: RunView): number {
  return view.total === 0 ? 0 : Math.max(0.04, view.done / view.total);
}
