# Decision: drift alerts and regime-conditional betas

Date: 2026-11-18
Status: Decided-pending-implementation

## In one sentence

We will flag when a stock's factor exposure has changed, using three separate conditions and an alert only when two agree, and show how betas differ between up and down markets, calm and turbulent periods, and three crisis windows.

## What we decided

- Drift alert per factor, three conditions: (a) the latest rolling beta is more than 2 standard deviations from its own history; (b) a significant beta flipped sign versus one year earlier; (c) a robust Wald test rejects equal betas against the window one year earlier. One condition is an "alert"; two or more is a "strong alert".
- A whole-sample stability check (CUSUM) is shown but not counted.
- Regime betas for up versus down market (market return below zero), high versus low volatility, and three crisis windows.

Not implemented as of 2026-11-18 (no drift or regime modules in the code).

## Why

The plan wanted alerts "BH-corrected", but conditions (a) and (b) are not tests with valid p-values because rolling estimates overlap. We rejected correcting everything and instead correct only the Wald condition and require two of three conditions for "strong", the plan's own false-alarm mitigation. We rejected a volatility rule that includes the current day, because that puts the biggest moves in the high-volatility bucket by construction. We rejected the plan's COVID window (peak to trough is only 23 trading days, below our 60-day minimum) and extended it.

## How it works

- Windows A and B are the latest 252 days and the 252 before them, with no shared data.
- Volatility regime: market volatility over the previous 21 days versus its median over the previous year. Day `t` itself is excluded. About half of all days are "high" by construction.
- Crisis windows are fixed: 2007-10-09 to 2009-03-09, 2020-02-19 to 2020-06-30 ("crash and rebound"), 2022-01-03 to 2022-10-12. A window is shown only with at least 60 days of data.
- Example: a beta of -0.8 that becomes +1.0 over the last year should trigger all three conditions (the oracle tests this).

## What it costs us

- Condition (a) is descriptive: rolling betas are strongly autocorrelated, so it has no p-value.
- Splits with fewer than 60 days in a regime show "insufficient data".
- The volatility split lags regime switches by about 10 days, which pulls estimated differences towards zero.
- CUSUM rejects too often on daily returns, so it is indicative only.
- Crisis windows are US-dated; for non-US stocks they are labelled as such.
- Many tests across many panels still raise the odds of a spurious alert.

## What would change our mind

A measured false-alarm rate above the target in simulations, users ignoring or misreading alerts, or a better-motivated change-point method that can be validated.

## Sources

- [docs/methodology.md](../docs/methodology.md), M9, M10, D12 to D14, M0.6.
- [docs/PLAN.md](../docs/PLAN.md), "Added scope" and Risks.
- [docs/test-oracle.md](../docs/test-oracle.md), drift tests T69 to T75.

## Related decisions

- [Which betas count as reliable](decision-which-betas-count-as-reliable.md)
- [No look-ahead rule](decision-no-look-ahead-rule.md)
- [Cointegration design](decision-cointegration-design.md)
