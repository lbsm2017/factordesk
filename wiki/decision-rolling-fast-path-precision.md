# Decision: say how precise the fast rolling regression is, and tighten its safety check

Date: 2026-11-18
Status: Decided-pending-implementation (becomes Decided when the change is merged)

## In one sentence

The fast way of computing rolling betas is not bit-for-bit the same as the slow, exact way, so we document the real numbers and tightened the check that decides which windows may use the fast way, at no cost in speed on real data.

## What we decided

An independent review of the rolling-regression speed-up (`docs/reviews/rolling-speedup-validation-2026-11-18.md`) accepted it with three conditions. This page covers the first two.

- The documents now say what was measured. On real SPY data the fast path differs from the slow exact path by about 1e-12 (an absolute amount; a beta is about 1). Against exact arithmetic, the worst real windows are off by about 1e-10 relative, where the slow path is off by about 1e-13. We no longer write "unchanged".
- A window may use the fast path only if its factors keep at least 1% of their variance around their own mean (before: 0.1%), and if the spread of the window is at least 0.1% of the running total of squares up to that day, measured around the window's mean (before: 0.01%, measured without removing the mean). Every other window goes to the exact path.
- A window's value now depends, in the last digits, on earlier rows, because the fast path subtracts running totals. A different start date moves a value by up to about 1e-12 (measured 7.9e-13 on SPY). It never depends on later rows, and the report rounds to six digits, so nothing visible changes.

## Why

The review found designs the old check let through where the fast path was off by 2e-8 on betas. They are not like French factor data, but the program accepts any factor table. We measured the tightened check on SPY and on a long synthetic series: every window still takes the fast path, the results are identical to before, and the time is unchanged. On the hard designs the error fell to about 1e-11.

We rejected loosening the claim only (documenting 2e-8 and moving on), because the tighter check was free. We rejected sending everything to the exact path because that is five times slower for no gain on real data.

## What it costs us

- A series with a very quiet stretch after a very loud one now takes the slower exact path for some windows. That is correct, only slower.
- Results at the 1e-12 level can differ between start dates. No test may compare rolling values across start dates with zero tolerance. A test bounds the effect instead.
