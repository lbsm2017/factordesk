# Decision: daily returns with robust (Newey-West) errors

Date: 2026-11-18
Status: Decided

## In one sentence

We fit each stock on daily data and measure uncertainty with Newey-West (HAC) standard errors, instead of using monthly data with plain textbook errors.

## What we decided

- Every regression uses daily excess returns, ordinary least squares with an intercept, and Newey-West errors with the lag rule `floor(4 * (m/100)^(2/9))`, where `m` is the number of observations in that regression.
- The settings are passed explicitly to the statistics library so that a library update cannot move results.
- No regularised or no-intercept fits.

## Why

A single stock has only about 120 monthly observations in ten years, which gives wide, unstable estimates; daily data gives about 2,520 in the same span. We rejected plain OLS errors because daily returns are not independent draws: volatility clusters and some series have day-to-day correlation, and plain errors then understate uncertainty. We rejected monthly data with plain errors because it combines both weaknesses: few points and unreliable error bars. We rejected lasso-style or no-intercept fits (seen in another open-source tool) because they hide alpha or shrink betas.

## How it works

- The lag rule gives 4 lags for 252 days, 8 for 2,520 days and 10 for the 8,474-day SPY sample.
- Newey-West errors add up the correlation of errors across nearby days, with weights that fade to zero. The point estimates are unchanged; only the error bars change.
- Worked example, from the independent check of the SPY report (2026-11-18): the alpha z-statistic is -1.00 with plain errors and -2.24 with Newey-West errors. Robust errors can make a result more significant as well as less.
- Alpha is annualised by multiplying by 252, an arithmetic convention that every label states.

## What it costs us

- Daily data brings noise that monthly data hides: closing prices that are not synchronised with the factor data (see the SPY investigation) and a risk-free rate published only to 0.01% a day.
- Newey-West errors are an approximation. With a 252-day window the test rejected at 5.8% when it should reject at 5% in the project's simulations, so rolling-window results are slightly over-eager.
- Rolling windows need our own implementation because the standard library's rolling regression has no robust-error option.
- A single global lag rule is a convention, not an optimum.

## What would change our mind

Simulations showing a materially better error estimator for daily stock data, evidence that the lag rule misbehaves on a class of tickers, or a data feed whose daily noise is large enough that weekly returns become the better default.

## Sources

- [docs/methodology.md](../docs/methodology.md), sections M0.5 and D2.
- [docs/references.md](../docs/references.md): Newey and West (1987); the small-sample point.
- [docs/validation/spy-slice-validation.md](../docs/validation/spy-slice-validation.md), section 3.5 (plain versus robust z).
- [docs/methodology-residual-analysis.md](../docs/methodology-residual-analysis.md), R5.2 (size of the 252-day test).

## Related decisions

- [Which betas count as reliable](decision-which-betas-count-as-reliable.md)
- [SPY timing noise and the quality gate](decision-spy-timing-noise-and-the-quality-gate.md)
- [Factor data source](decision-factor-data-source-french-library.md)
