# Decision: how the cointegration panel works

Date: 2026-11-18
Status: Decided-pending-implementation

## In one sentence

The cointegration panel tests whether a stock drifts together with each factor index or with peer tickers over the long run, labels the result "exploratory", and requires a result to hold on data it was not fitted on.

## What we decided

- Pairs: the stock against five cumulative factor indices, plus up to 8 peers (default SPY, QQQ, IWM and one sector fund).
- Per pair: Engle-Granger test, hedge ratio, Johansen test (as confirmation only), half-life of the gap, and a split-sample test.
- Multiple testing: two Benjamini-Hochberg families, one for in-sample p-values and one for out-of-sample p-values.
- Status "Long-run link (exploratory)" needs both families to reject and a finite half-life.

Not implemented as of 2026-11-18 (no cointegration module in the code).

## Why

Cointegration between a stock and cumulative factor indices has no established economic meaning and gives false positives on short or single-regime samples, so the panel must be hard to over-read. The plan's single "BH across all tests" would mix two kinds of p-value; we rejected it for two families. We rejected reporting the standard in-sample residual ADF p-value because it uses critical values that are wrong when the hedge ratio was fitted on the same data. We rejected `log(price)` for factor pairs because price includes a risk-free drift; we use the stock's excess-return index there (peer pairs keep log adjusted prices).

## How it works

- Split-sample test: fit the hedge ratio on the first 60% of rows, freeze it, and test the gap on the last 40%. Standard critical values then apply.
- Half-life: if the gap shrinks by 5% a day (`phi = -0.05`), half-life is `-ln 2 / ln(0.95)`, about 13.5 trading days. A half-life between 5 and 60 days is flagged "in band".
- Johansen has critical values but no p-value, so it is shown as "agrees" or "disagrees", outside the corrections.
- Each pair needs at least 504 common rows.

## What it costs us

- It is a descriptive curiosity, not a trading signal; readers may still treat it as one.
- Splitting 60/40 spends data; short histories may show nothing.
- Fixed settings (one lagged difference, 5 to 60 day band) are conventions.
- Peers must pass the price audit, and peer pairs inherit the data problems of Yahoo prices.

## What would change our mind

An economic argument for using factor indices (or a better-motivated pair set), simulations showing the two-family correction is too strict or too loose, or the panel producing few usable results in practice.

## Sources

- [docs/methodology.md](../docs/methodology.md), M11, D10, D11, M0.6 (F7, F8).
- [docs/PLAN.md](../docs/PLAN.md), "Cointegration" and sprint plan (cut order).
- [docs/test-oracle.md](../docs/test-oracle.md), section 13 (cointegration tests, from T82).

## Related decisions

- [Which betas count as reliable](decision-which-betas-count-as-reliable.md)
- [Drift alerts and regime betas](decision-drift-alerts-and-regime-betas.md)
- [Prices from Yahoo with adjusted-close care](decision-prices-from-yahoo-with-adjusted-close-care.md)
