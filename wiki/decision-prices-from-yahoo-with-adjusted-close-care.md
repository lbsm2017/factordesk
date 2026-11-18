# Decision: prices from Yahoo, with extra care over adjusted close

Date: 2026-11-18
Status: Decided

## In one sentence

We take daily prices only from Yahoo Finance (through the yfinance library), download the raw bars, compute total return from the adjusted close, and recompute that adjustment independently as a check.

## What we decided

- v1 uses yfinance only. An Alpaca adapter is a stub: keys are placeholders and nothing is called.
- Each ticker is fetched with every option set explicitly: `auto_adjust=False`, `actions=True`, `repair=False`, full history.
- Regression returns come from `Adj Close` (total return, which includes dividends, to match the factors). An audit recomputes the adjustment and reports problems; it never changes prices.
- We keep our own same-day cache and always re-download full history, because adjusted history changes at each dividend.

## Why

The owner chose yfinance "for now" (the plan does not give a longer reason); it needs no API key, and the plan notes Alpaca keys are not needed for v1. Alpaca is deferred to the "Next" horizon. We rejected `auto_adjust=True` because it hides the raw close that the audit needs, and library defaults changed in version 0.2.51. We rejected `repair=True` because the repair feature has had its own 100x bugs; we report problems rather than silently fixing them. We rejected multiplying by the split column, because Yahoo's `Close` is already split-adjusted.

## How it works

- Yahoo's adjusted price scales earlier prices by `1 - dividend / previous close`.
- Illustrative numbers: close 100, then 101 with a 1.00 dividend that day. Price return is +1.00%. Yahoo's adjusted return is `101 / (100 - 1) - 1 = +2.02%`. The plan's simpler formula `(101 + 1) / 100 - 1` gives +2.00%.
- The audit checks Yahoo's convention per dividend event and per calendar year, so one bad dividend cannot hide in a cumulative total. It also flags returns above 40%, gaps, stale runs and unrecorded splits.
- An independent recomputation on 2026-11-18 matched all 136 SPY dividend events to within 0.009 basis points.
- Dates use the exchange time zone; today's incomplete bar is dropped.

## What it costs us

- Yahoo data is scraped and unofficial; it can break or rate-limit. Mitigations are the cache, clear errors and frozen test fixtures.
- Two same-day downloads differed by up to 1.8e-4 in adjusted close (about 1e-7 effect on betas), so reports are not bit-for-bit reproducible unless the input is hashed. That fix is recommended, not done.
- Only tickers that exist today can be analysed (survivorship), so results say nothing about delisted companies.
- Contradiction: the plan's audit formula differs from the Yahoo-convention audit in the methodology (D9). The 2026-11-18 validation found the code still uses the plan's formula, so its reported "2.52 bps" dividend gap is a formula artefact. Fix pending.

## What would change our mind

Yahoo breaking repeatedly or changing its adjustment method; the Alpaca cross-check showing material disagreement; or a licensed feed becoming affordable.

## Sources

- [docs/methodology.md](../docs/methodology.md), M1.3, M1.4, D9.
- [docs/PLAN.md](../docs/PLAN.md), "Prices (adjusted-close care)" and Risks.
- [docs/validation/spy-slice-validation.md](../docs/validation/spy-slice-validation.md), findings F6, F8 and section 3.4.
- [CODING_STANDARDS.md](../CODING_STANDARDS.md), section 3.

## Related decisions

- [Independent validation and mutation testing](decision-independent-validation-and-mutation-testing.md)
- [No data and no secrets in the repository](decision-no-data-and-no-secrets-in-the-repo.md)
- [European mode and currency](decision-european-mode-and-currency.md)
