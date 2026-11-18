# Decision: which betas count as reliable

Date: 2026-11-18
Status: Decided

## In one sentence

We call a beta "reliable" only if it passes a Benjamini-Hochberg test run across all five betas together, not if its t-statistic merely exceeds 2.

## What we decided

- Beta tags come from one rule: two-sided Newey-West p-values for the five betas, corrected by Benjamini-Hochberg (BH) at a 5% false-discovery rate. Rejected means "reliable"; otherwise "noise".
- Alpha is a single test: reliable if its p-value is below 0.05.
- Explanatory text is generated only for reliable coefficients.

## Why

The plan used two rules that disagree: "BH across the 5 tests" and "reliable if |t| is at least 2". A lone p-value of 0.03 passes the second and fails the first, so the project needed one rule (decision D1 in the methodology). We rejected the simple |t| over 2 rule because testing five betas at once gives about a 1 in 4 chance of at least one false "hit" when nothing is real. The sources do not record why the stricter Bonferroni correction was not chosen; the usual reason is that it loses power, whereas BH controls the share of false discoveries instead of the chance of any one.

## How it works

- Sort the five p-values from smallest to largest. Compare the k-th smallest with `k x 0.05 / 5`. Every beta up to the last one that passes is reliable.
- Worked example: p-values 0.030, 0.40, 0.55, 0.70, 0.90. The smallest is compared with 0.01 and fails, so no beta is reliable. A |t| over 2 rule (p below about 0.045) would have called the first one reliable.
- Real case, SPY report of 2026-11-18: HML has z = 0.81 and is noise; the other four betas have |z| above 5 and are reliable.
- The bar chart shows plain 95% intervals while the tags use BH, so an interval that excludes zero can still be tagged noise. The tooltip says so.

## What it costs us

- BH is less sensitive than a plain test: a real but modest beta can be tagged noise.
- Five factors is a convention. Adding momentum or a currency term changes the family to six tests.
- The alpha test is not corrected. The independent review of 2026-11-18 judged the word "reliable" on alpha too strong for a borderline single test and recommended "significant at 5% (single test, in-sample)"; that wording change is pending.
- BH assumes tests behave in a certain way when they are correlated; the factors overlap (value, profitability and investment), which the report flags with a collinearity warning.

## What would change our mind

Simulations showing the BH family misbehaves with correlated factors, a switch to a model with a different number of factors, or evidence that readers misread "noise" as "zero".

## Sources

- [docs/methodology.md](../docs/methodology.md), M0.6, M3.2, M3.3, D1.
- [docs/PLAN.md](../docs/PLAN.md), "Regression" and "Lessons from GitHub analogs" (the earlier |t| rule).
- [docs/validation/spy-slice-validation.md](../docs/validation/spy-slice-validation.md), F2 and section 4.
- [docs/references.md](../docs/references.md): Benjamini and Hochberg (1995).

## Related decisions

- [Daily returns and robust errors](decision-daily-returns-and-robust-errors.md)
- [Residual alpha analysis](decision-residual-alpha-analysis.md)
- [Drift alerts and regime betas](decision-drift-alerts-and-regime-betas.md)
