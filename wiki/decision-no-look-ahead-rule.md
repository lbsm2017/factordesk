# Decision: no look-ahead, ever

Date: 2026-11-18
Status: Decided

## In one sentence

Any result stamped with a date may use only data from that date or earlier, and the shading of the dominant factor uses a delayed, causal filter instead of a retrospective clean-up.

## What we decided

- A result dated `t` is a function only of rows dated `t` or earlier. This covers normalisation, medians, ranks and smoothing.
- Trailing windows hold exactly `W` rows, including day `t`. Quantities used to explain day `t` (such as a beta for timing) come from rows up to `t-1`.
- Forbidden in the analytics code: negative shifts, centred windows, back-fill, interpolation and any fill of missing returns.
- The plan's "10-day minimum-run merge" for factor-dominance shading is replaced by a causal confirmation filter (decision D3). On 2026-11-18 the owner delegated the choice and accepted the filter: region edges lag the true change by up to 9 days, which is invisible on a multi-year chart, and the no-look-ahead promise holds. The retrospective merge was rejected because it uses later data. Implementation is pending.
- Related: non-USD tickers get a warning, not a refusal, until European mode ships.

## Why

A chart that looks smoother or more insightful because it peeked at the future is a form of cheating, and look-ahead bias is the most common way backtests flatter themselves. The plan's merge relabelled short runs by looking at their neighbours, which uses later days and contradicts the plan's own "point-in-time" definition. We rejected the merge as the default because it would fail our own look-ahead test. We rejected loose conventions ("remember to avoid peeking") because bugs seen in other open-source tools (windows off by one, `fillna(0)` collapsing betas) each became a test instead.

## How it works

- Rolling window example: with `W = 252`, the point at row 300 uses rows 49 to 300. The first point exists at row 252.
- Causal filter: a new dominant factor is displayed only after it has led on `M` consecutive days (default 10). With `M = 3`, raw labels `AAABAABBBCCAAA` display as `UUAAAAAABBBBBA`, where `U` means "not yet set". Each displayed label depends only on earlier raw labels.
- Tests perturb data after a date and confirm earlier outputs do not move. A static scan rejects forbidden calls.
- Whole-sample results (such as the full regression) are stamped with the last date and labelled "in-sample".

## What it costs us

- Shading boundaries lag by up to `M-1` days, so they look later than a retrospective chart would.
- "Point-in-time" here means "no future rows of the data we hold". The Ken French library revises history, and we keep one vintage, so a past value may differ from what was published then.
- Whole-sample numbers are still in-sample; this rule does not make them predictive.
- Rolling windows start late: the first 251 days have no estimate.

## What would change our mind

If the lag proves a problem in use, a retrospective merge could be added if labelled "retrospective (uses later data)" and excluded from the look-ahead test; the methodology gives a deterministic version. Nothing would justify unlabelled look-ahead.

## Sources

- [docs/methodology.md](../docs/methodology.md), M0.2, M0.3, M8, D3, and open question 1.
- [CODING_STANDARDS.md](../CODING_STANDARDS.md), section 2.
- [docs/PLAN.md](../docs/PLAN.md), "Chart shading" and "Avoid (bugs seen in the wild)".
- [docs/validation/spy-slice-validation.md](../docs/validation/spy-slice-validation.md), section 2 (window and lag checks, 2026-11-18).

## Related decisions

- [Return and risk attribution](decision-return-and-risk-attribution.md)
- [Residual alpha analysis](decision-residual-alpha-analysis.md)
- [Drift alerts and regime betas](decision-drift-alerts-and-regime-betas.md)
