# Decision: build one thin slice on SPY before the dashboard

Date: 2026-11-18
Status: Decided

## In one sentence

We built one working path from end to end (factors, SPY prices, date matching, analysis, report) and checked it hard before building the dashboard or the other panels.

## What we decided

- The first deliverable is a single-ticker report, written as a static HTML page and a JSON file, produced from a command-line tool.
- It covers factor download, SPY prices, date alignment, the regression, rolling betas, return and risk attribution, and the report page.
- The dashboard, drift alerts, regime betas, cointegration and the residual panel come after the slice has been reviewed.

## Why

The plan's first sprint is called "Trustworthy numbers": get one validated report for a few tickers before any user interface exists. SPY is a good first case because its answer is roughly known (a market beta near 1) and its history is long. We rejected building the full dashboard first because a polished screen on top of unchecked numbers makes errors harder to see and costlier to fix. We rejected building all analytics modules before running anything end to end, because problems in data handling (date matching, dividends, time zones) only appear when real data flows through. The sources do not record a longer written rationale; this reasoning is taken from the plan's sprint structure.

## How it works

- The slice reads the Ken French file and SPY prices, matches dates, fits the five-factor regression, and writes `docs/samples/spy_report.json` and `.html`.
- An independent reviewer then rebuilt the SPY report from raw inputs with separate code. On 2026-11-18 every headline number matched the report to about 1e-7, and the return and risk identities held to about 1e-16.
- The same pass found a real surprise: SPY's R-squared was 0.967, not 0.995. That led to the timing-noise investigation and the quality gate.
- It also found the plan's expected "other betas near zero" for SPY was wrong: size beta is about -0.15 with a tiny error.

## What it costs us

- The slice delays visible features; as of 2026-11-18 the dashboard is not built.
- A single ticker can hide problems that other tickers show. Edge cases (flat prices, bad splits, duplicate dates) crashed or passed as "ok" in testing; those fixes are listed as conditions for shipping.
- Several specified modules (per-year attribution, tilt versus timing, diagnostics) sit outside the slice.
- The README still says analytics are not built (a stale statement as of 2026-11-18).

## What would change our mind

If the slice approach delayed learning about the user interface so much that real users could not react to it, we would ship a thinner dashboard earlier. A new data source or model would repeat the slice approach on its own first ticker.

## Sources

- [docs/PLAN.md](../docs/PLAN.md), sprint plan (S1 and S2) and Verification.
- [docs/validation/spy-slice-validation.md](../docs/validation/spy-slice-validation.md), sections 1, 2, 4 and 5.
- [docs/samples/spy_report.json](../docs/samples/spy_report.json) and [docs/samples/spy_report.html](../docs/samples/spy_report.html).
- [README.md](../README.md).

## Related decisions

- [SPY timing noise and the quality gate](decision-spy-timing-noise-and-the-quality-gate.md)
- [Independent validation and mutation testing](decision-independent-validation-and-mutation-testing.md)
- [Report design: colour is evidence](decision-report-design-colour-is-evidence.md)
