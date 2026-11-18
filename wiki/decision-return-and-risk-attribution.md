# Decision: return and risk attribution that adds up exactly

Date: 2026-11-18
Status: Decided

## In one sentence

We split a stock's return into factor pieces that sum exactly to the total, and its risk into shares that sum to 100% with a separate "idiosyncratic" row, instead of using methods whose parts do not add up.

## What we decided

- Return contribution is arithmetic: each factor's beta times the factor's average return, times 252, plus alpha. These add to the average excess return exactly.
- Risk contribution uses the Euler method: each factor's share of the stock's variance, plus an idiosyncratic share. These add to 100%.
- Nothing is folded into alpha. Residual, alpha, unattributed and uncovered days are separate rows.

## Why

Readers trust a breakdown only if the pieces add up. We rejected compounding each piece separately because compounded parts do not sum (seen in pyfolio-style and other tools); we label compounded numbers separately and never add them to arithmetic ones. We rejected factor-risk methods whose shares do not add up (seen in the equity-risk-model project). We rejected hiding alpha, residual and dates without factor data inside one bucket; skfolio's explicit "unattributed" row was the model.

## How it works

- OLS with an intercept forces residuals to average zero, so the return identity is exact (tested to 1e-10).
- Variance of the stock equals the factor part plus the leftover part, so each factor's share is `beta x (factor covariance x betas) / variance`. The idiosyncratic share is 1 minus R-squared.
- SPY, full sample to 2026-09-30 (independent recomputation, 2026-11-18). Return, per year: market 9.74%, size -0.06%, value 0.02%, profitability 0.30%, investment 0.13%, alpha -0.58%, total 9.54%. Risk shares: market 98.40%, size 0.08%, value -0.02%, profitability -1.08%, investment -0.65%, idiosyncratic 3.27%, summing to 100%. Rounded figures can differ from the totals in the last digit.
- Risk shares can be negative: a factor that offsets other exposures reduces total risk.

## What it costs us

- Arithmetic contributions are not the stock's compounded growth. Labels say so.
- Full-sample betas assume exposure stayed constant. Per-year tables and the tilt-versus-timing split (which uses betas from the day before) are specified but not implemented as of 2026-11-18.
- Contributions describe the past in-sample; they do not forecast.
- Idiosyncratic variance uses a divisor of n-1 rather than n-6, so the identity is exact; the methodology notes this is a deliberate choice (D5).

## What would change our mind

A requirement for compounded attribution (for example matching a fund's published performance), in which case we would add a separate, clearly labelled table. A broader factor model with more factors would extend the same method rather than replace it.

## Sources

- [docs/methodology.md](../docs/methodology.md), M6, M7, D5 to D8.
- [docs/PLAN.md](../docs/PLAN.md), "Lessons from GitHub analogs" (adopt and avoid lists).
- [docs/validation/spy-slice-validation.md](../docs/validation/spy-slice-validation.md), section 4 (numbers and identity checks).

## Related decisions

- [No look-ahead rule](decision-no-look-ahead-rule.md)
- [Residual alpha analysis](decision-residual-alpha-analysis.md)
- [Report design: colour is evidence](decision-report-design-colour-is-evidence.md)
