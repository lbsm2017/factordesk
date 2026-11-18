# Decision: European mode, regional factors and currency

Date: 2026-11-18
Status: Proposed

## In one sentence

For European tickers we propose using the library's Europe 5-factor file, converting the stock's return to US dollars, and optionally adding the currency move as a sixth regressor; non-US tickers outside the supported regions would be refused.

## What we decided

The owner confirmed on 2026-11-18 that European mode comes first after v1, then other regions. The design in the dataset methodology is a proposal: it lists owner questions still open (below). Until it ships, non-USD tickers get a warning only, and as of 2026-11-18 the slice does not yet check currency at all.

Proposed rules: regional factors of the stock's listing region by default; ticker suffix (`.DE`, `.L`, `.T` and so on) picks the region; unknown suffixes are refused with a reason; holiday gaps are excluded, not filled.

## Why

Regional files exist for Europe, Japan, North America, Asia Pacific ex Japan, Developed and Developed ex US. We rejected US factors for non-US stocks because they mix factor exposure with currency and local-market effects. We rejected the Developed set by default because it mixes markets that close at different times: Japan's same-day correlation with North America is 0.040, against 0.413 with the previous day. We rejected a silent default for unknown suffixes because a wrong default yields confident wrong numbers. We rejected compounding factors over holiday gaps because a compounded long-short factor is not its multi-day return.

## How it works

- Verified on 2026-11-18: regional files are quoted in US dollars; Great Britain is inside Europe; the risk-free rate is the US one-month T-bill; the Europe file has 9,458 daily rows from 1990-07-02 to 2026-09-30.
- USD return = `(1 + local return) x (1 + currency return) - 1`. Example: stock +1.0%, euro +0.5% against the dollar, gives +1.505%.
- Model B adds the currency return as a sixth regressor. Measured correlation of currency with Europe's market factor is 0.14 to 0.26, so overlap is low.
- Currency source: ECB reference rates first, Yahoo FX as a labelled fallback, with an audit for spikes.

## What it costs us

- Open items (owner decisions): use a monthly-derived risk-free rate (removes up to about 1 point a year of alpha noise)? ECB as the primary FX source? Model B on by default? Accept North America factors for Canadian tickers?
- Unverified: how the library converts to dollars, when each country joined, the source of the regional T-bill series, whether files always update together, ECB data access, and exact closing times.
- History starts in 1990, so fewer independent windows than the US file, and the cited papers test portfolio average returns, not single-stock exposures.

## What would change our mind

A currency convention in the library that conflicts with our conversion, ECB access failing, owner rejection of the open items, or tests showing the currency regressor adds noise rather than information.

## Sources

- [docs/datasets.md](../docs/datasets.md), sections 2 to 8 (verified facts and unverified items U1 to U8).
- [docs/methodology-datasets.md](../docs/methodology-datasets.md), D7 to D10, D16.
- [docs/PLAN.md](../docs/PLAN.md), "Deferred".
- [docs/validation/spy-slice-validation.md](../docs/validation/spy-slice-validation.md), F13.
- ECB reference rates: <https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/index.en.html>

## Related decisions

- [Factor data source](decision-factor-data-source-french-library.md)
- [Prices from Yahoo with adjusted-close care](decision-prices-from-yahoo-with-adjusted-close-care.md)
- [Drift alerts and regime betas](decision-drift-alerts-and-regime-betas.md)
