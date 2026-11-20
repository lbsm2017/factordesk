/**
 * Small hooks that decide what the Factor it flow shows (Sprint 4 mockup 1): whether the run page
 * is visible yet, whether the report that arrived gets the reveal, and which report stays on screen
 * while the next one is built.
 */
import { useEffect, useState } from "react";
import { clearRun } from "../api/runProgress";
import type { RunProgress } from "../api/runProgress";

/** Without a step event or a fallback, a run that lasts this long shows its page anyway. */
export const VISIBLE_AFTER_MS = 250;

/**
 * True while a run is on its way and its page should show: from the first step event, from the
 * fallback to the plain endpoint, or after `VISIBLE_AFTER_MS`. A cached report answers before any of
 * these, so it opens at once with no run card and no fade.
 */
export function useRunVisible(pending: boolean, progress: RunProgress): boolean {
  const [late, setLate] = useState(false);
  if (!pending && late) setLate(false);
  useEffect(() => {
    if (!pending) return;
    const id = window.setTimeout(() => setLate(true), VISIBLE_AFTER_MS);
    return () => window.clearTimeout(id);
  }, [pending]);
  return pending && (late || progress.plain || progress.steps.length > 0);
}

/**
 * True for the report that arrives at the end of a run whose page was visible: only then do the
 * panels appear one after another. A report that comes from the cache is shown at once.
 */
export function useReveal(report: object | undefined, running: boolean, visible: boolean): boolean {
  const [armed, setArmed] = useState(false);
  const [wasRunning, setWasRunning] = useState(false);
  const [revealed, setRevealed] = useState<object | null>(null);
  if (running !== wasRunning) {
    setWasRunning(running);
    if (running) setArmed(false);
  }
  if (running && visible && !armed) setArmed(true);
  if (!running && armed && report !== undefined) {
    setArmed(false);
    setRevealed(report);
  }
  return revealed !== null && revealed === report;
}

/** The latest report that was defined: it stays on screen while the next request runs or fails. */
export function useKept<T>(value: T | undefined): T | undefined {
  const [kept, setKept] = useState<T | undefined>(value);
  if (value !== undefined && value !== kept) setKept(value);
  return value ?? kept;
}

/** Drops the steps of a run that ended with a report, so the next run under the same key starts clean. A failed run keeps them for the error page. */
export function useClearFinishedRun(key: string, finished: boolean): void {
  useEffect(() => {
    if (finished) clearRun(key);
  }, [key, finished]);
}

/**
 * The sentence for the page's polite status line: the step that has just started, or the report
 * that is ready. Empty on an error (the error notice has its own alert) and before the first step.
 */
export function runAnnouncement(pending: boolean, progress: RunProgress, readyFor: string | null): string {
  if (pending) {
    const last = progress.steps.at(-1);
    return last === undefined ? "" : `Step ${last.index} of ${last.total}: ${last.label}.`;
  }
  return readyFor === null ? "" : `The report for ${readyFor} is ready.`;
}
