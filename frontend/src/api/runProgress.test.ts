import { describe, expect, it } from "vitest";
import { barFraction, expectedPlan, NO_PROGRESS, recordFallback, recordStep, runView, startRun, getRunProgress } from "./runProgress";
import type { RunProgress } from "./runProgress";
import type { ProgressStep } from "./types";

const labels = {
  prices: "Downloading prices",
  fx: "Loading exchange rates",
  factors: "Loading factor data",
  models: "Fitting the models",
  sections: "Building the sections",
} as const;
const ev = (index: number, total: number, id: keyof typeof labels): ProgressStep => ({ step: id, label: labels[id], index, total });
const progress = (...steps: ProgressStep[]): RunProgress => ({ steps, plain: false });
const states = (p: RunProgress, plan = expectedPlan({ prices: true, fx: true }), failed = false) => runView(p, plan, failed).rows.map((r) => r.state);

describe("expectedPlan", () => {
  it("leaves out the exchange rates in USD and the prices of an upload", () => {
    expect(expectedPlan({ prices: true, fx: false })).toEqual(["prices", "factors", "models", "sections"]);
    expect(expectedPlan({ prices: true, fx: true })).toHaveLength(5);
    expect(expectedPlan({ prices: false, fx: true })).toEqual(["fx", "factors", "models", "sections"]);
    expect(expectedPlan({ prices: false, fx: false })).toEqual(["factors", "models", "sections"]);
  });
});

describe("runView step states", () => {
  it("shows every step as waiting before the first event", () => {
    const view = runView(NO_PROGRESS, expectedPlan({ prices: true, fx: true }));
    expect(view.rows.map((r) => r.state)).toEqual(["waiting", "waiting", "waiting", "waiting", "waiting"]);
    expect(view.rows.map((r) => r.label)).toEqual(Object.values(labels));
    expect(view.current).toBe(0);
  });

  it("the latest event is the running step, the steps before it are done, the rest wait", () => {
    const p = progress(ev(1, 5, "prices"), ev(2, 5, "fx"), ev(3, 5, "factors"));
    const view = runView(p, expectedPlan({ prices: true, fx: true }));
    expect(view.rows.map((r) => r.state)).toEqual(["done", "done", "running", "waiting", "waiting"]);
    expect(view.rows[3]?.label).toBe("Fitting the models");
    expect(view.done).toBe(2);
    expect(view.current).toBe(3);
    expect(view.currentLabel).toBe("Loading factor data");
    expect(barFraction(view)).toBeCloseTo(0.4);
  });

  it("a skipped step counts as done when a later step arrives", () => {
    const p = progress(ev(1, 4, "prices"), ev(3, 4, "models"));
    expect(states(p, expectedPlan({ prices: true, fx: false }))).toEqual(["done", "done", "running", "waiting"]);
  });

  it("an upload has no prices step: the total and the order come from the events", () => {
    const p = progress(ev(1, 3, "factors"));
    const view = runView(p, expectedPlan({ prices: false, fx: false }));
    expect(view.rows.map((r) => r.label)).toEqual(["Loading factor data", "Fitting the models", "Building the sections"]);
    expect(view.total).toBe(3);
  });

  it("takes the total from the events when the expected plan differs", () => {
    const view = runView(progress(ev(1, 4, "prices")), expectedPlan({ prices: true, fx: true }));
    expect(view.total).toBe(4);
    expect(view.rows).toHaveLength(4);
  });

  it("a failure marks the running step failed and the later ones not run", () => {
    const p = progress(ev(1, 4, "prices"), ev(2, 4, "factors"));
    const view = runView(p, expectedPlan({ prices: true, fx: false }), true);
    expect(view.rows.map((r) => r.state)).toEqual(["done", "failed", "not-run", "not-run"]);
    expect(view.current).toBe(2);
  });

  it("with no step list (the plain endpoint) there are no rows and no bar", () => {
    const view = runView({ steps: [], plain: true }, expectedPlan({ prices: true, fx: false }));
    expect(view.rows).toEqual([]);
    expect(barFraction(view)).toBe(0);
  });

  it("the bar never drops under 4 percent", () => {
    expect(barFraction(runView(progress(ev(1, 5, "prices")), expectedPlan({ prices: true, fx: true })))).toBe(0.04);
  });
});

describe("the progress store", () => {
  it("keeps the steps per run key and starts over for a new run", () => {
    startRun("a");
    recordStep("a", ev(1, 4, "prices"));
    recordStep("a", ev(2, 4, "factors"));
    expect(getRunProgress("a").steps).toHaveLength(2);
    expect(getRunProgress("b")).toBe(NO_PROGRESS);
    recordFallback("a");
    expect(getRunProgress("a")).toEqual({ steps: [], plain: true });
    startRun("a");
    expect(getRunProgress("a")).toBe(NO_PROGRESS);
  });
});
