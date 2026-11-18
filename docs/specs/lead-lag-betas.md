# factordesk specification: lead-lag (non-synchronous trading) betas

Status: specification for a new feature, written 2026-11-18. Not yet implemented.
Audience: engineers implementing `backend/factordesk/analytics/lead_lag.py` (new) and the schema additions; reviewers checking the code against it.
Companions: `docs/methodology.md` (M0-M16, D1-D31, cited unchanged; the residual quality gate is M3.6), `docs/research-protocol.md` (checklist, Appendix A registry, Appendix B power), `docs/test-oracle.md` (style and seed policy), `docs/methodology-datasets.md` (D14 timing), `docs/validation/spy-slice-validation.md` (section 3), `docs/data-source-comparison.md` (sections 3.5, 4, 7).
Section ids: LL0-LL12. Decisions: LLD1-LLD9 (LL10). Tests: TLL01-TLL20 (LL11). Registry entries: LL12.

Rule of precedence: every M0 convention (units, stamping, HAC per M0.5, BH per M0.6, status values, `SampleInfo`, labels) applies unchanged. This document adds two BH families (F10, F11, proposed in LL10.3) and **never changes a headline number or tag**: the daily full-sample regression of M3 and the tag rule of M3.2/M3.6 stay as they are. Proposed changes to `docs/methodology.md` are listed in LL10.3 for the owner; this document does not edit it.

Evidence markers: **[V]** = verified by a computation run for this document (scripts and outputs in the session scratchpad, folder `specs-ll-fr`, not part of the repo), or by a source checked on 2026-11-18 as stated; **[U]** = unverified.

---

## LL0. Scope, notation, classification

### LL0.1 What the feature shows

A same-day beta measures how a stock's return on day `t` moves with the factor returns of day `t`. When the stock's closing price and the factor returns are not recorded at the same moment, part of the co-movement lands on the previous or the next factor day, and the same-day beta misses it. Three mechanisms matter for factordesk:

1. **Stale stock price** (thin trading, slow price discovery): today's close still reflects yesterday's news, so the stock loads on the factors' **previous** day.
2. **Late stock close** (a close recorded after the 4:00 pm factor day ends, or a cross-region factor file whose markets close earlier): the stock's day contains part of the factors' **next** day.
3. **Stale factor portfolios** (the long-short factor portfolios contain small, thinly traded stocks whose prices react with a delay): a synchronous stock leads the factor, so it loads on the factors' **next** day.

Lead-lag betas add each factor's previous-day and next-day return to the regression and sum the three coefficients per factor (Dimson 1979). The sum measures the total exposure, wherever in the three days it lands.

What the feature does **not** do: it does not remove transient price noise. A close that is off by a random amount which reverses the next day (`e_t = w_t + u_t - u_{t-1}`, M3.6) produces negative residual autocorrelation whether or not betas are biased. That noise is handled by the 5-day estimate of M3.6, which stays. The SPY demonstration (LL8) shows both cases side by side.

### LL0.2 Notation (additions to M0.1)

| Symbol | Meaning |
| --- | --- |
| `d_t` | calendar date of row `t` of `S` (M2) |
| `f^-_t`, `f^+_t` | factor vectors of the French dates immediately **before** and immediately **after** `d_t` in the French calendar (not the previous and next rows of `S`) |
| `S_LL` | rows of `S` whose `f^+_t` is dated `<= T_end` (LL2.2); `n_LL` = its number of rows |
| `b^-_i`, `b^0_i`, `b^+_i` | lag, same-day and lead coefficients on factor `i` in the lead-lag regression |
| `beta^LL_i` | summed (aggregated) beta `b^-_i + b^0_i + b^+_i` |
| `tau_i` | timing adjustment `b^-_i + b^+_i = beta^LL_i - b^0_i` |
| `alpha^LL` | intercept of the lead-lag regression |
| `beta^SW` | Scholes-Williams-type estimate (LL4), cross-check only |
| `K_LL = 16` | parameters of the lead-lag regression (1 + 3 x 5) |

### LL0.3 Classification of every output

| Output | Class | Stamp |
| --- | --- | --- |
| Lead-lag coefficients, summed betas, timing adjustments, `alpha^LL`, `R^2_LL`, residual diagnostics | in-sample, full window (like M3) | `T_end` |
| Timing test F11 (computed for every ticker) | in-sample test | `T_end` |
| Scholes-Williams cross-check | in-sample | `T_end` |
| Any per-date (rolling, ex-ante) lead-lag series | **not produced in v1** (LL5.3) | - |

---

## LL1. Literature (checked 2026-11-18)

| Reference | Bibliographic check | What we rely on |
| --- | --- | --- |
| Scholes, M., and Williams, J. (1977). Estimating betas from nonsynchronous data. *Journal of Financial Economics* 5(3), 309-327. doi:10.1016/0304-405X(77)90041-1 | [V] Crossref API and IDEAS/RePEc record (volume 5, issue 3, pages 309-327, December 1977) | The estimator `beta^SW = (b_-1 + b_0 + b_+1) / (1 + 2 rho_m)`, with `b_k` the **simple** regression slopes of `r_t` on `m_{t+k}` and `rho_m` the market's lag-1 autocorrelation, is the form in which the paper is universally cited [U: the paper's text was not accessible; RePEc says "No abstract is available", Semantic Scholar reports the abstract elided by the publisher, ScienceDirect returned HTTP 403]. Its consistency in our settings is checked by simulation instead (LL7) [V]. |
| Dimson, E. (1979). Risk measurement when shares are subject to infrequent trading. *Journal of Financial Economics* 7(2), 197-226. doi:10.1016/0304-405X(79)90013-8 | [V] Crossref and IDEAS/RePEc (volume 7, issue 2, pages 197-226, June 1979) | The aggregated-coefficients method: one **multiple** regression on lagged, same-day and leading market returns; beta is the sum of the slopes. [V, secondary]: Chung (2024, p. 6) describes it as "It first estimates the contemporaneous beta, the lagged beta, and the lead beta from r = alpha + b_cont r_m,d + b_lag r_m,d-1 + b_lead r_m,d+1 + e ... The synchronicity-adjusted beta is b_dim = b_cont + b_lag + b_lead." The paper's own empirical conclusions are [U] (text not accessible, same reasons). |
| Fowler, D. J., and Rorke, C. H. (1983). Risk measurement when shares are subject to infrequent trading: Comment. *Journal of Financial Economics* 12(2), 279-283. doi:10.1016/0304-405X(83)90039-9 | [V] Crossref and IDEAS/RePEc (title with ": Comment", pages 279-283, August 1983) | Commonly cited as showing that the plain Dimson sum is inconsistent when the market index itself is autocorrelated, and that weights restore consistency [U: text not accessible]. Our simulation LL7 (DGP-LL3) reproduces a bias of that kind in our setting [V]. |
| Cohen, K. J., Hawawini, G. A., Maier, S. F., Schwartz, R. A., and Whitcomb, D. K. (1983). Friction in the trading process and the estimation of systematic risk. *Journal of Financial Economics* 12(2), 263-278. doi:10.1016/0304-405X(83)90038-7 | [V] Crossref | Related work only; nothing below depends on it [U content]. |
| Chung, L. T. D. (2024). Simply better market betas around the globe. Manuscript dated March 12, 2024, retrieved from `cfr.ivo-welch.org/forthcoming/papers/chung2024simply.pdf` | [V] text read (30 pages); publication venue [U] | p. 17: daily betas "are susceptible to errors-in-variables biases induced by missing daily returns in infrequently traded stocks (Scholes and Williams, 1977; Dimson, 1979)" and "the conventional b_ols estimator can severely underestimate the market betas of thinly traded stocks." p. 3: for **forecasting** future betas, "the Dimson (1979) synchronicity adjustment ... do[es] more harm than good". factordesk's use is descriptive (LL5), not a forecast, so this finding does not argue against the feature, but it does argue against ever using lead-lag betas as ex-ante exposures. |

What each conclusion means here: OLS same-day betas are biased under non-synchronous prices (both papers, [V] via Chung's summary of them); aggregating lead and lag coefficients is the standard remedy. The direction of the bias depends on the mechanism (LL0.1): a stale stock's same-day beta is too low, a beta on a stale factor can be too high (LL7 shows both) [V for our DGPs].

---

## LL2. Model

### LL2.1 Regression (primary estimator: Dimson, per factor, one lag and one lead)

For `t in S_LL`:

`y_t = alpha^LL + sum_i ( b^-_i f^-_{i,t} + b^0_i f_{i,t} + b^+_i f^+_{i,t} ) + e_t`

OLS with intercept and HAC per M0.5 with `L(n_LL)`, using the M0.5 reference call on the 16-column design `[1, f, f^-, f^+]` (columns in that order, factors in canonical order inside each block). The M3.1 design guard is applied to the 16-column design.

Outputs:
- `beta^LL_i = r_i' theta`, `se(beta^LL_i) = sqrt(r_i' V_hat r_i)`, `z = beta^LL_i / se`, two-sided normal `p`, `CI95`, where `r_i` selects the three coefficients of factor `i`. Equivalently `res.t_test(R)` on the reference fit (oracle TLL04). This is the delta method for a linear combination, which is exact.
- `tau_i = b^-_i + b^+_i` with its HAC se and `z` (F11, LL3.2).
- The six individual lag and lead coefficients that drive the wording: `b^-_i`, `b^+_i` with se.
- `alpha^LL` (LL2.4), `R^2_LL`, adjusted `R^2_LL = 1 - (1 - R^2)(n_LL - 1)/(n_LL - 16)`, residual lag-1 autocorrelation and robust z with the M3.5 formulas, 5-day variance ratio of the residuals (LL6.3).
- The joint Wald statistic of all 10 lag and lead coefficients (chi-square, 10 df), **informational only** (LLD8).

### LL2.2 Building the lagged and leading factors (calendar, sample end)

- `f^-_t` and `f^+_t` come from the **French calendar**: the factor rows dated immediately before and after `d_t` in the factor file in use, found by `searchsorted` on the French index. They are not the previous and next rows of `S`: when M2 excludes a stock row (for example `multi_day_return`), the neighbouring stock row still gets its true neighbouring factor days.
- **Sample-end rule.** A row is in `S_LL` only if its `f^+_t` is dated `<= T_end` (the last date of `S`). In practice this removes the last row of `S` (its next factor day is after `T_end` or not yet published). The removed row is listed in `SampleInfo.excluded` with reason `lead_after_sample_end`. No row is removed at the start: the French file begins in 1963 and every `S` row has a previous factor day.
- With this rule every input of the estimate is dated `<= T_end`, which is what M0.2 item 1 requires of an output stamped `T_end` (LL5).

### LL2.3 Why per factor, and why one lag and one lead

Decision LLD1 (per factor, not market only) and LLD2 (one lag, one lead, fixed). Evidence:

- A stale price delays the **whole** price, so it shifts every factor exposure, not only the market's. In the stale-stock simulation (LL7, DGP-LL1, `theta = 0.3`), market-only Dimson recovers the market beta (1.128 against 1.10) but leaves the style betas at `(1 - theta)` of their true value (SMB 0.21 against 0.30, HML -0.28 against -0.40; 95% interval coverage 23% and 18%). Dimson with leads and lags on every factor recovers all five (coverage 92-94%) [V].
- On real data the style lead and lag terms are not zero: SPY 1993-02-01..2008-12-30, Wald test of the 8 style lead and lag coefficients, chi-square 59.3 with 8 df, `p = 6e-10`; full sample `p = 6e-7` [V]. With market-only leads and lags the HML beta stays at -0.019 (same-day -0.021); with per-factor leads and lags it is +0.046 [V].
- The French style factors have their own lag-1 autocorrelation, large before about 2000 (HML +0.22 to +0.34, CMA +0.20 to +0.28 in 1963-1997 blocks; LL7.4) [V]. A stock regressed on such factors loads on their neighbouring days whatever its own trading.
- **One lag and one lead.** The three mechanisms of LL0.1 are within one trading day for listed securities with daily closes: a late close is minutes to hours, a cross-region factor file is one calendar day off (D14: Japan same-day correlation with North America 0.040 against 0.413 with the previous US day), and stale prices of exchange-listed stocks rarely persist beyond a day. The number is fixed before seeing any result and is never tuned per ticker or chosen by an information criterion (a choice made on the data is a test, protocol item 2).
- Sensitivity, recorded and not shipped: two lags and two leads on SPY (full sample) give market 0.999 against 1.013 and alpha -0.42% against -0.57% a year [V]. The difference is about 3 standard errors of the summed market beta, so the lag count is not innocuous; it is fixed at one by LLD2 and the two-lag result is a registry line (LL12), not an option.
- Cost: 10 extra parameters. With serially uncorrelated factors and residuals the summed beta has about `sqrt(3) = 1.73` times the standard error of the same-day beta (simulation DGP-LL0: 0.0440 against 0.0255 for the market, 0.0749 against 0.0430 for SMB) [V]. On SPY the ratio is 0.74-1.28 across the three periods of LL8, because the same-day HAC standard errors are already inflated by the reversal noise [V]. Power consequence in LL6.5.

### LL2.4 Alpha in the lead-lag model

`alpha^LL` is the intercept of LL2.1, annualised by `A` (M0.4). Because OLS residuals with an intercept sum to zero on `S_LL`:

`alpha^LL = mean(y) - sum_i ( b^-_i mean(f^-_i) + b^0_i mean(f_i) + b^+_i mean(f^+_i) )` exactly (identity, TLL05; SPY full sample difference `1.5e-18` [V]).

Since the means of `f^-`, `f` and `f^+` over `S_LL` differ only by edge terms of order `(f_last - f_first)/n_LL`, `alpha^LL` equals `mean(y) - beta^LL' mean(f)` up to those edge terms (SPY full sample: `8.9e-6` a year; pre-2009 `5.3e-5` a year) [V]. Reading: the same "average unexplained return" as M3, with the exposure measured in total over the three days. It differs from the M3 alpha mainly through `(beta^LL - beta) ' mean(f)`.

`alpha^LL` is a single test at 5% (like M3), informational: it never changes the alpha tag of M3.2/M3.6.

---

## LL3. Inference, families and tags

### LL3.1 Summed betas: family F10

`H0: beta^LL_i = 0`, HAC z from LL2.1, BH within **F10** (`m = 5`, M0.6). Tag shown in the lead-lag column only: "reliable (lead-lag)" or "noise (lead-lag)". F10 tags never replace the headline tags (LLD6).

### LL3.2 Timing adjustment: family F11 (computed for every ticker)

`H0: tau_i = b^-_i + b^+_i = 0` (the summed beta equals the same-day coefficient of the same regression), HAC z, BH within **F11** (`m = 5`). This is the direct test of "does timing change this factor's beta". It is computed for every report, because it is also the second trigger of the display (LL6.1). Its size and power [V, LL7.3]:

| DGP (n) | Gate M3.6 fires | F11 rejects at least one factor |
| --- | --- | --- |
| Synchronous, no noise (504 / 2520) | 0.000 / 0.000 | 0.065 / 0.046 |
| Stale stock `theta = 0.1` (504 / 2520) | 0.000 / 0.000 | 0.204 / 0.786 |
| Stale stock `theta = 0.3` (504 / 2520) | 0.000 / 0.000 | 1.000 / 1.000 |
| Late close `kappa = 0.05` plus transient noise sd 0.006 (504 / 2520) | 0.094 / 0.002 | 0.070 / 0.162 |
| Transient close noise only, sd 0.006 (504 / 2520) | 0.199 / 0.037 | 0.055 / 0.048 |

`R = 1000` per cell; binomial standard error at 0.05 is 0.0069. F11 holds its size (0.046-0.065), detects stale prices that the gate cannot see, and does not fire on pure close noise, which is the gate's job.

The reason the gate cannot see stale prices: a stale price makes residuals **positively** autocorrelated (mean `rho_1` +0.105 at `theta = 0.1`, +0.31 at `theta = 0.3` [V]); the M3.6 gate fires only on negative autocorrelation.

The difference between `beta^LL_i` and the M3 same-day beta `beta_i` is shown but not tested: they come from different regressions, and when factors are autocorrelated the same-day coefficient itself moves once leads and lags enter (SPY full sample, HML: M3 beta 0.007, same-day coefficient in LL2.1 0.008, `tau` 0.028) [V].

### LL3.3 Joint Wald of all leads and lags (informational)

Over-sized in finite samples: under the synchronous DGP it rejects at nominal 5% in 11.5% of samples at `n = 504` and 6.3% at `n = 2520` (`R = 2000`, binomial se 0.0049) [V]. It is shown in the drawer with that caveat and drives nothing (LLD8). The summed-beta interval keeps its coverage at `n = 504` (non-coverage 6.5% for the market sum) [V].

### LL3.4 Interaction with the headline tags

Headline tags stay exactly as M3.2 and M3.6 define them (daily test, and under the gate also the 5-day test). Lead-lag results never enter the M3.6 conjunction: a third set of tests in the conjunction would make "reliable" depend on which estimates happen to be shown. When a headline tag and the F10 tag disagree, the report says so in words (LL9.3) and keeps the headline tag.

---

## LL4. Scholes-Williams cross-check (drawer, needs an owner decision)

Multivariate Scholes-Williams in instrumental-variable form: instrument `z_t = (1, f^-_t + f_t + f^+_t)'`, regressor `x_t = (1, f_t')'`, just identified:

`theta^SW = (Z'X)^-1 Z'y`, `V^SW = (Z'X)^-1 S_z (X'Z)^-1`, `S_z` = the M0.5 Bartlett meat of `z_t e^SW_t` with `L(n_LL)`.

- For one factor this is the classical formula up to edge terms: SPY CAPM, `(b_-1 + b_0 + b_+1)/(1 + 2 rho_m)` against the IV form: 0.9878 vs 0.9870 (1993-2008), 0.9618 vs 0.9622 (2010-2026), 0.9767 vs 0.9767 (full sample) [V].
- Its alpha satisfies `alpha^SW = mean(y) - beta^SW' mean(f)` exactly (the instrument contains the constant), so it fits the M6.1 identity.
- It is consistent in all three mechanisms of LL0.1 in our simulations, including the stale-factor case where the Dimson sum is biased (LL7, DGP-LL3: Dimson market 1.073, SW 1.100, truth 1.10; coverage 0.895 vs 0.945) [V].
- Why it is not the primary estimator (LLD3): it is not OLS (CODING_STANDARDS section 4 requires OLS with intercept for every regression), it does not separate the lag from the lead (the wording of LL9 needs both), and in every DGP except the stale-factor one it agrees with the Dimson sum to Monte Carlo precision [V].
- Display: one row in the drawer, "Scholes-Williams (cross-check)". Disagreement note when `|beta^LL_i - beta^SW_i| > 2 se(beta^LL_i)` for any factor (no test; a pre-specified display rule): "The two lead-lag methods disagree for {factors}. The factor's own daily returns are autocorrelated ({ac1:+.2f} over this sample), a case where the summed-coefficient method is biased; read the cross-check row." On SPY no factor triggers it (largest ratio 0.71, market, 1993-2008; 0.34 in the full sample) [V].
- If the owner does not grant the exception to CODING_STANDARDS section 4, LL4 is dropped; nothing else depends on it.

---

## LL5. The look-ahead question

### LL5.1 Why a lead in a full-sample descriptive estimate is not look-ahead

M0.2 defines look-ahead by stamps: an output stamped `s` may use only rows dated `<= s`. The full-sample lead-lag regression is stamped `T_end` and, by the sample-end rule of LL2.2, uses only `y` dated `<= T_end - 1 row` and factors dated `<= T_end`. Every input precedes or equals the stamp, so the output is computable at `T_end` exactly as M3 is.

Inside the sample, the coefficient on `f^+_t` describes a realised co-movement: how the return recorded for day `t` moved with the factor return of the following day. It answers "how were these prices recorded relative to the factor day?", not "what will the factor do tomorrow?". Nobody can act on it at `t`, and nothing in the report uses it to explain or predict any day. This is the same status as the M3 betas, which also use day `t`'s own factor return to describe day `t`.

Look-ahead in the forecasting sense means a value attached to date `t` that uses information dated after `t`. A lead becomes exactly that the moment a lead-lag estimate is attached to a date earlier than its last lead.

### LL5.2 What is forbidden

1. No output stamped `s` may use any `f^+` dated after `s`. For the full-sample estimate this is guaranteed by the sample-end rule (`s = T_end`); removing that rule (for example using the next French row after `T_end` when the French file extends beyond the requested end) is a look-ahead bug (TLL02).
2. No lead-lag beta may be used as an ex-ante exposure (M4 `beta_tilde`, M6.3 tilt/timing, residual analysis R4 of `docs/methodology-residual-analysis.md`). Those uses explain day `t` and need inputs dated `<= t - 1` (M0.2 item 3); a lead-lag window ending at `t - 1` would need `f^+` of `t - 1`, which is dated `t`, the day being explained. Test TLL14 asserts that all ex-ante series are bitwise identical with and without this module.
3. v1 produces **no** rolling or per-date lead-lag series. If one is added later: a window whose rows are `s-W+1 .. s` uses leads up to the French day after `s`, so it must be stamped with the date of its last lead (`d(f^+_s)`), never with `d_s`; it must pass the T102/T103 perturbation and truncation tests with that stamp; and it may be used ex ante only for days strictly after that stamp.

### LL5.3 Static-scan exception (proposal)

M0.2 item 4 and T104 forbid negative shifts. The lead is built without `shift(-1)`: one function, `factor_at_offset(factors, dates, offset, t_end)` in `analytics/lead_lag.py`, looks up French rows by `searchsorted` and raises `LookAheadError` if any returned row is dated after `t_end`. Proposal (LL10.3): T104 gains an allowlist with exactly this function, and TLL02/TLL13 test it. No other analytics code may index the French frame forward.

---

## LL6. When it is shown: the trigger, and the quality gate

### LL6.1 Trigger (pre-specified)

The lead-lag section has status `ok` and is shown next to the daily betas iff **either**:

- **(A) the residual quality gate fires** (M3.6; the section reads `quality_gate.fired` from the report and does not re-implement the gate, so a later change of the gate's condition, for example the variance-ratio condition proposed in `docs/data-source-comparison.md` section 7 item 5, applies automatically); **or**
- **(B) F11 rejects for at least one factor** (LL3.2).

Otherwise status `not_applicable`, reason "Timing between the stock's closes and the factor data shows no effect on betas (no factor's timing adjustment is significant) and the residual quality gate did not fire." The F11 result itself is always in the drawer, so the decision is visible.

Why not always shown: the same reason M3.6 gives for the 5-day estimate. A second set of betas on every report invites picking whichever looks better. Why (B) is needed: the gate is built for transient noise (negative autocorrelation) and never fires on stale prices (LL3.2 table), which is the case Dimson's method exists for.

Future trigger (C), for the dataset work (D14 item 3): a factor dataset whose markets close in other time zones than the listing. It needs its own decision when regional datasets ship.

### LL6.2 What the report shows when the gate fires

- The 5-day estimate of M3.6 stays and keeps its role in the tags. Lead-lag betas are shown **beside** the daily and 5-day betas, as a third column, with their own F10 tags.
- The two remedies answer different questions. The 5-day estimate removes transient close noise from residual variance (it telescopes within a block). The lead-lag estimate removes bias in the betas from exposure that lands on a neighbouring factor day. The wording (LL9.2) tells the user which one the data point to, from F11.

### LL6.3 What lead-lag cannot fix (evidence from SPY)

Residual lag-1 autocorrelation and the 5-day variance ratio `VR5 = var(5-row block sums of e) / (5 var(e))` (non-overlapping blocks anchored at the first row, as M3.6) are essentially unchanged by adding leads and lags [V]:

| SPY period | `rho_1` daily -> lead-lag | `VR5` daily -> lead-lag | F11 rejections | Wald(10) p |
| --- | --- | --- | --- | --- |
| 1993-02-01..2008-12-30 (n 4,010) | -0.416 -> -0.427 | 0.28 -> 0.26 | none | 5e-14 |
| 2010-01-04..2026-09-29 (n 4,210) | -0.253 -> -0.250 | 0.57 -> 0.58 | none | 0.58 |
| 2023-01-03..2026-09-29 (n 938) | -0.353 -> -0.371 | 0.31 -> 0.31 | none | 0.64 |
| 1993-02-01..2026-09-29 (n 8,473) | -0.404 -> -0.408 | 0.30 -> 0.30 | none | 2e-10 |

The 2023-2026 row matters. `docs/data-source-comparison.md` (sections 3.5 and 4) found that Yahoo's SPY close equals the NYSE Arca closing auction (as recorded in Alpaca's SIP feed) on 99.6-100% of days in each year 2017-2022 (its section 3.5 table; the 98.8% in that table is AAPL in 2020) and that from 2023 both vendors give returns equal to the official auction, yet the residual autocorrelation is still -0.35 with `VR5` 0.31 (its values: -0.352, 0.31; ours on the same dates -0.353, 0.31) [V, consistent]. Lead-lag finds no timing effect there (F11: no rejection; market `tau` -0.019, z -1.4). So the reversal is noise in the ETF's closing price relative to the 4 pm factor data (premium/discount, auction noise), not a delayed exposure. Wording must not blame the data vendor (LL9.2).

### LL6.4 Status values and minimum samples (M0.7)

| Condition | Status | Reason |
| --- | --- | --- |
| Neither trigger | `not_applicable` | LL6.1 text |
| `n_LL < 500` | `insufficient_data` | "Lead-lag betas need at least 500 days (16 coefficients); {n_LL} available." |
| Design guard of M3.1 fails on the 16-column design | `failed` | the factor block named |
| Otherwise | `ok` | - |

Minimum 500: about 31 rows per coefficient. At `n = 504` the summed-beta interval keeps coverage (non-coverage 6.5%) [V]. The report minimum `n >= 504` gives `n_LL >= 503`, so the minimum is met by every report. F11 has the same minimum; below it F11 is `insufficient_data`, it is left out of any decision, and trigger (B) is false.

### LL6.5 Power (protocol item 6)

With serially uncorrelated data the minimum detectable summed beta is about `1.73` times the same-day MDE of protocol Appendix B. For US FF5, 20% residual volatility, 10 years, `a = 0.01`: Mkt, SMB, HML, RMW, CMA about 0.14, 0.24, 0.22, 0.29, 0.36 (Appendix B row times 1.73; arithmetic [V], Appendix B values as published there). F11 detects a stale component of `theta = 0.1` in 20% of 2-year samples and 79% of 10-year samples, and `theta = 0.3` always (LL3.2) [V]. A non-rejection of F11 is worded "no timing effect detected", never "no timing effect".

### LL6.6 Schema (`report/schema.py`; optional sub-models per the schema v3 contract)

`LeadLagSection` (field `lead_lag` of `FactorReport`, always present):

| Field | Type | Meaning |
| --- | --- | --- |
| `status`, `reason` | M0.7 | LL6.4 |
| `sample` | `SampleInfo` | `n = n_LL`, actual dates of `S_LL`; `excluded` contains the `lead_after_sample_end` row |
| `trigger` | `{"gate": bool, "timing_test": bool}` | which trigger(s) fired (LL6.1); filled whatever the status |
| `gate_ref` | str | `"M3.6"`: the gate result is read from `FactorReport.quality_gate`, not copied |
| `hac_lags` | int | `L(n_LL)` |
| `n_params` | int | 16 |
| `timing_test` | `TimingTest` | F11, always computed when `n_LL >= 500` (below) |
| `betas` | `list[LeadLagBeta]` (5, canonical order) | `null` unless `status == ok` |
| `alpha` | `LeadLagAlpha` | `null` unless `ok` |
| `r2`, `r2_adj` | float | of the 16-regressor fit |
| `resid_rho1`, `resid_rho1_z`, `resid_vr5` | float | M3.5 formulas on lead-lag residuals; VR5 as LL6.3 |
| `resid_rho1_daily`, `resid_vr5_daily` | float | the same for the M3 residuals, for the side-by-side |
| `joint_wald` | `{"stat", "df": 10, "p", "informational": true}` | LL3.3 |
| `sw_crosscheck` | `SWCrossCheck` or `null` | LL4; `null` if the owner drops LL4 |
| `sentences` | list[str] | LL9.2 / LL9.3, generated in the analytics layer |
| `labels` | list[str] | `["L-DESC", "L-LEADLAG"]` (LL9.1 text as new label key) |

`LeadLagBeta`: `factor`; `lag`, `same_day`, `lead` (each `{est, se, z, p}`); `summed` (`{est, se, z, p, ci95}`); `tag_f10` (`"reliable" | "noise"`); `p_adj_f10`; `daily_beta` and `daily_tag` (copied from M3/M3.6 for display, never recomputed); `tags_disagree` (bool).
`TimingTest`: `status`, `reason`, `m`, and per factor `{factor, tau, se, z, p, p_adj, rejected}`; `any_rejected` (bool).
`LeadLagAlpha`: `alpha_daily`, `alpha_ann`, `se_ann`, `z`, `p`, `ci95_ann`, `edge_term_ann` (`alpha^LL - (mean(y) - beta^LL' mean(f))`, annualised; LL2.4).
`SWCrossCheck`: `betas` (5 x `{est, se}`), `alpha_ann`, `disagree_factors` (list), `factor_ac1` (5 floats over `S_LL`), `note` (str or `null`).

---

## LL7. Simulations [V]

DGP-A factors (test-oracle 0.4: `n = 2520`, daily sds 1.0, 0.6, 0.6, 0.4, 0.4%, same correlations), `beta = (1.10, 0.30, -0.40, 0.25, 0.15)`, `alpha = 2e-4`, `sigma_e = 0.012`, `R = 400` per DGP, seeds `20261118 + 900..903`. True synchronous return `R_t = alpha + beta' f_t + e_t`. Estimators on rows with a lag and a lead: daily OLS, market-only Dimson, per-factor Dimson (primary), Scholes-Williams IV, 5-day non-overlapping sums.

### LL7.1 DGPs

- **DGP-LL0, synchronous:** observed `r_t = R_t`.
- **DGP-LL1, stale stock price** (a known one-day stale component): `r_t = (1 - theta) R_t + theta R_{t-1}`, `theta = 0.3`. The true beta is `beta`; the same-day OLS beta converges to `(1 - theta) beta`.
- **DGP-LL2, late close plus transient noise:** `r_t = (1 - kappa) R_t + kappa R_{t+1} + w_t - w_{t-1}`, `kappa = 0.05`, `w ~ N(0, 0.006^2)`.
- **DGP-LL3, stale market factor, synchronous stock:** `r_t = R_t`; the observed market factor is `(1 - phi) M_t + phi M_{t-1}`, `phi = 0.15` (lag-1 autocorrelation 0.17, similar to the French Mkt-RF in the 1960s-1980s, LL7.4).

### LL7.2 Results (mean estimate; bias in units of the mean se; 95% coverage)

| DGP | Estimator | Mkt | SMB | HML | RMW | CMA | Coverage (5 betas) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| LL0 | daily | 1.101 | 0.297 | -0.396 | 0.246 | 0.142 | 0.93-0.95 |
| LL0 | Dimson per factor | 1.100 | 0.304 | -0.393 | 0.252 | 0.142 | 0.93-0.96 |
| LL1 | daily | **0.772** (bias -15.7 se) | 0.211 | -0.280 | 0.177 | 0.103 | 0.00, 0.31, 0.23, 0.72, 0.88 |
| LL1 | Dimson market only | 1.128 (+0.74) | **0.210** | **-0.280** | 0.177 | 0.103 | 0.88, 0.23, 0.18, 0.68, 0.88 |
| LL1 | **Dimson per factor** | **1.103** (+0.08) | 0.297 | -0.404 | 0.250 | 0.151 | 0.94, 0.93, 0.94, 0.92, 0.93 |
| LL1 | Scholes-Williams IV | 1.103 | 0.297 | -0.404 | 0.250 | 0.152 | 0.94-0.96 |
| LL1 | 5-day sums | 1.038 (-1.13) | 0.280 | -0.378 | 0.238 | 0.144 | 0.79, 0.93, 0.93, 0.95, 0.96 |
| LL2 | daily | 1.047 (-1.74) | 0.284 | -0.373 | 0.236 | 0.133 | 0.58, 0.93-0.96 |
| LL2 | Dimson per factor | 1.101 | 0.294 | -0.392 | 0.248 | 0.143 | 0.93-0.97 |
| LL2 | 5-day sums | 1.092 | 0.290 | -0.394 | 0.243 | 0.139 | 0.93-0.95 |
| LL3 | daily | **1.249** (+5.0) | 0.315 | -0.426 | 0.259 | 0.172 | 0.00, 0.92-0.96 |
| LL3 | Dimson per factor | 1.073 (**-0.58**) | 0.301 | -0.405 | 0.251 | 0.153 | **0.895**, 0.94-0.96 |
| LL3 | Scholes-Williams IV | **1.100** (0.00) | 0.303 | -0.408 | 0.254 | 0.156 | 0.945, 0.94-0.96 |
| LL3 | 5-day sums | 1.121 (+0.36) | 0.310 | -0.409 | 0.261 | 0.159 | 0.91, 0.94-0.96 |

Mean se, market: daily 0.0255 (LL0), Dimson 0.0440, SW 0.0442, 5-day 0.0565. Alpha: unbiased for Dimson and SW in all four DGPs (bias at most 0.05 se); the daily alpha is off by 0.5 se in LL1. Which estimator recovers the known beta of the stale stock: **per-factor Dimson and Scholes-Williams**, not the daily beta, not market-only Dimson, and only partly the 5-day sums (`beta (1 - theta/5) = 1.034`; observed 1.038).

### LL7.3 Trigger simulation

See the table in LL3.2 (`sim_trigger.py`, seeds `20261118 + 1000..1041`).

### LL7.4 Lag-1 autocorrelation of the French daily factors [V]

| Block | Mkt-RF | SMB | HML | RMW | CMA |
| --- | --- | --- | --- | --- | --- |
| 1963-1972 | +0.292 | +0.397 | +0.241 | +0.159 | +0.213 |
| 1973-1982 | +0.232 | +0.138 | +0.335 | +0.244 | +0.256 |
| 1983-1992 | +0.121 | -0.070 | +0.310 | +0.201 | +0.281 |
| 1993-1997 | +0.089 | +0.055 | +0.220 | +0.101 | +0.204 |
| 1998-2002 | +0.019 | +0.096 | +0.100 | +0.201 | +0.094 |
| 2003-2008 | -0.107 | -0.032 | +0.027 | +0.123 | +0.087 |
| 2009-2014 | -0.073 | -0.035 | -0.105 | -0.077 | +0.029 |
| 2015-2020 | -0.199 | -0.011 | +0.078 | +0.032 | +0.029 |
| 2021-2026 | -0.020 | -0.015 | +0.023 | +0.036 | +0.053 |

Before about 2000 the factors are as autocorrelated as DGP-LL3, so for long histories the Dimson sum can carry the LL3-type bias of about half a standard error; the Scholes-Williams cross-check (LL4) exists for that case.

---

## LL8. Demonstration on SPY [V]

Inputs: French US daily 5-factor zip downloaded 2026-11-18 11:25Z, `Last-Modified: Tue, 27 Oct 2026 15:18:47 GMT`, SHA-256 `e58577223032aa45071a46686f7068900c371b516c9eb04e28e974c34264f84f`, 15,918 rows 1963-07-01..2026-09-30. SPY from yfinance 1.8.0, `Ticker("SPY").history(period="max", interval="1d", auto_adjust=False, actions=True, repair=False)`, 8,509 bars 1993-01-29..2026-11-17, dates in America/New_York. M2 alignment gives `n = 8,474`, 1993-02-01..2026-09-30. Reproduction check: alpha -0.5765% a year, z -2.2367, `R^2` 0.96734, `rho_1` -0.404, as in `docs/validation/spy-slice-validation.md` section 4; HAC se equal to the statsmodels reference call to `7e-14` relative.

Daily rows below are refitted on `S_LL` (one row fewer than `S`) so that both columns use identical rows. Betas with HAC se in brackets.

### LL8.1 1993-02-01..2008-12-30 (n 4,010, L 9)

| Spec | Mkt | SMB | HML | RMW | CMA | Alpha %/yr (z) | `R^2` | `rho_1` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Daily FF5 | 1.0231 (0.0106) | -0.1858 (0.0102) | -0.0212 (0.0215) | 0.1255 (0.0156) | 0.0964 (0.0220) | -0.834 (-1.68) | 0.9442 | -0.416 |
| Dimson per factor 1/1 | 1.0320 (0.0095) | -0.1849 (0.0130) | 0.0456 (0.0199) | 0.0864 (0.0148) | 0.0484 (0.0223) | -0.784 (-1.58) | 0.9462 | -0.427 |
| Dimson market only | 1.0324 (0.0122) | -0.1867 | -0.0187 | 0.1217 | 0.0951 | -0.861 (-1.72) | 0.9445 | -0.417 |
| Dimson 2/2 (not shipped) | 1.0156 | -0.1661 | 0.0303 | 0.0922 | 0.0574 | -0.734 (-1.43) | - | -0.429 |
| Scholes-Williams IV | 1.0253 (0.0102) | -0.1813 | 0.0398 | 0.0948 | 0.0539 | -0.806 (-1.60) | - | -0.425 |
| 5-day sums (M3.6) | 1.0277 (0.0113) | -0.1675 | 0.0164 | 0.1009 | 0.1015 | -0.961 (-2.54) | 0.9806 | -0.373 (blocks) |

Market lag -0.0128 (z -1.9), lead +0.0191 (z +2.9); style lag coefficients HML +0.067 (z 3.5), RMW -0.055 (z -3.8), CMA -0.050 (z -2.8). Timing adjustments `tau` (F11): 0.006, -0.000, 0.067, -0.041, -0.040, z 0.7, -0.0, 2.2, -2.2, -1.3: none rejected after BH (the smallest p, 0.03, is above its BH threshold 0.01).

### LL8.2 2010-01-04..2026-09-29 (n 4,210, L 9)

| Spec | Mkt | SMB | HML | RMW | CMA | Alpha %/yr (z) | `R^2` | `rho_1` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Daily FF5 | 0.9870 (0.0047) | -0.1092 (0.0035) | 0.0211 (0.0048) | 0.0447 (0.0049) | 0.0313 (0.0069) | -0.128 (-0.59) | 0.9950 | -0.253 |
| Dimson per factor 1/1 | 0.9929 (0.0040) | -0.1106 (0.0042) | 0.0264 (0.0045) | 0.0529 (0.0056) | 0.0244 (0.0066) | -0.213 (-0.95) | 0.9950 | -0.250 |
| Dimson market only | 0.9920 (0.0033) | -0.1095 | 0.0212 | 0.0448 | 0.0317 | -0.194 (-0.89) | 0.9950 | -0.250 |
| Dimson 2/2 (not shipped) | 0.9827 | -0.1115 | 0.0272 | 0.0518 | 0.0179 | -0.077 (-0.35) | - | -0.250 |
| Scholes-Williams IV | 0.9941 (0.0061) | -0.1113 | 0.0267 | 0.0532 | 0.0244 | -0.231 (-0.98) | - | -0.262 |
| 5-day sums (M3.6) | 0.9869 (0.0028) | -0.1079 | 0.0192 | 0.0504 | 0.0255 | -0.132 (-0.64) | 0.9970 | -0.117 (blocks) |

No lead or lag coefficient has `|z| > 1.9`; Wald(10) p 0.58; F11 none rejected.

### LL8.3 Full sample 1993-02-01..2026-09-29 (n 8,473, L 10)

| Spec | Mkt | SMB | HML | RMW | CMA | Alpha %/yr (z) | `R^2` | `rho_1` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Daily FF5 | 1.0093 (0.0066) | -0.1476 (0.0062) | 0.0071 (0.0087) | 0.0878 (0.0094) | 0.0607 (0.0112) | -0.579 (-2.25) | 0.9673 | -0.404 |
| Dimson per factor 1/1 | 1.0130 (0.0049) | -0.1522 (0.0070) | 0.0363 (0.0083) | 0.0740 (0.0092) | 0.0360 (0.0115) | -0.574 (-2.23) | 0.9679 | -0.408 |
| Dimson 2/2 (not shipped) | 0.9986 | -0.1452 | 0.0337 | 0.0715 | 0.0320 | -0.419 (-1.58) | - | -0.410 |
| Scholes-Williams IV | 1.0123 (0.0055) | -0.1515 | 0.0356 | 0.0771 | 0.0375 | -0.581 (-2.22) | - | -0.409 |
| 5-day sums (M3.6) | 1.0076 (0.0064) | -0.1441 | 0.0221 | 0.0775 | 0.0597 | -0.562 (-2.55) | 0.9879 | -0.335 (blocks) |

F11: `tau` 0.003, -0.004, 0.028, -0.012, -0.022 (z 0.5, -0.5, 2.3, -1.2, -1.4); none rejected.

### LL8.4 Reading

1. The gate fires for SPY (M3.6), so the lead-lag column would be shown. Its message is that timing does not reliably change any beta (F11 rejects nothing in any period), and that the reversal (`rho_1` -0.40, `VR5` 0.30) is untouched by leads and lags. The 5-day estimate is the relevant remedy.
2. One tag would differ: HML is "noise" on the daily test (z 0.81) and "reliable (lead-lag)" in F10 (z 4.4), because the HML coefficients on the neighbouring days are significant before 2009 while the HML factor itself was autocorrelated (+0.10 to +0.22 in 1993-2002, LL7.4). F11 does not reject HML (p 0.02 > BH threshold 0.01), so the report shows the disagreement (LL9.3) and keeps the headline tag.
3. Alpha barely moves (-0.579 to -0.574% a year): as LL2.4 says, alpha changes only through `(beta^LL - beta)' mean(f)`.

---

## LL9. User-facing labels and wording

### LL9.1 Names

- Section title: "Timing-adjusted betas (lead-lag)".
- Column header: "Lead-lag beta". Tooltip: "Same-day beta plus the stock's co-movement with the factor's previous and next trading day (Dimson method)."
- Drawer rows: "Previous-day coefficient", "Same-day coefficient", "Next-day coefficient", "Timing adjustment (previous + next)", "Scholes-Williams (cross-check)".
- Labels: L-DESC + "In-sample, uses the whole window. The next-day coefficient describes how this stock's recorded closes line up with the factor day; it is not a forecast."

### LL9.2 Generated sentences (exactly one opening sentence, chosen by the first rule that applies)

1. Trigger (B), some factor rejected in F11, with `b^-_i` the larger of the two in absolute value: "{Factor}: part of this stock's exposure shows up a day late (previous-day coefficient {b^-:+.2f}). Its prices react with a delay, so the same-day beta {b0:.2f} understates the exposure; the lead-lag beta is {bLL:.2f}."
2. Same, with `b^+_i` larger: "{Factor}: part of this stock's exposure shows up on the factor's next day (next-day coefficient {b^+:+.2f}). Either the stock's close is recorded after the factor day ends, or the factor's own prices react with a delay. The lead-lag beta is {bLL:.2f} against a same-day {b0:.2f}."
3. Trigger (A) only (gate fired, F11 rejects nothing): "Adding the factors' previous and next day changes no beta reliably. The day-to-day reversal flagged above is noise in the closing price relative to the factor data (for an ETF, its closing price can differ from its index value), not a delayed reaction; the 5-day estimate is the relevant check."
4. Always appended when shown: "Lead-lag betas carry about 1.7 times the uncertainty of same-day betas, so small differences are not meaningful."

### LL9.3 Tag disagreement

When the headline tag (M3.2/M3.6) and the F10 tag differ for a factor: "{Factor}: {reliable / noise} on same-day data, {reliable / noise} with lead-lag betas. The headline keeps the same-day result; the difference comes from co-movement on neighbouring days{, which is not itself significant (timing adjustment p {p})}." The bracketed clause appears when F11 does not reject that factor.

---

## LL10. Decisions, proposals, open questions

### LL10.1 Decisions

- **LLD1 Leads and lags on every factor**, not the market only (LL2.3: DGP-LL1; SPY style Wald p 6e-10; factor autocorrelation).
- **LLD2 One lag and one lead, fixed** (LL2.3). Never tuned; the two-lag result is a registry line only.
- **LLD3 Dimson per-factor sum is the shown estimator**; Scholes-Williams IV is a drawer cross-check, subject to an exception to CODING_STANDARDS section 4 (LL4).
- **LLD4 Neighbouring factor days come from the French calendar**; rows whose lead is after `T_end` are excluded and reported (LL2.2).
- **LLD5 Display trigger = gate (M3.6) or F11.** F11 is computed for every report; the gate is read, not re-implemented (LL6.1).
- **LLD6 Headline numbers and tags never change.** F10 tags live in the lead-lag column; no conjunction with M3.6 (LL3.4).
- **LLD7 No per-date lead-lag series in v1**; stamping rule for any later one fixed in LL5.2 item 3.
- **LLD8 The joint Wald of 10 coefficients is informational** (over-sized at small `n`, LL3.3).
- **LLD9 Alpha^LL is informational** (single test, never a tag).

### LL10.2 Dependencies

M3.6 (gate, `quality_gate.fired`), M3.5 formulas (`rho_1`, robust z), M3.1 design guard, schema v3 contract (optional sub-models).

### LL10.3 Proposed additions to `docs/methodology.md` (for the owner; not made here)

1. M0.6 families: **F10** (lead-lag summed betas, `m = 5`, shown when LL6.1 triggers) and **F11** (timing adjustments, `m = 5`, every report).
2. M0.7 row: lead-lag `n_LL >= 500`.
3. M0.2 item 4 / T104: allowlist for `analytics/lead_lag.factor_at_offset` (LL5.3).
4. M3.6 wording: the caveat names "a close recorded after the 4:00 pm index close" as the example. `docs/data-source-comparison.md` shows SPY on official closes still fires from 2023; the caveat should add the ETF premium/discount explanation, as that document's section 7 item 5 proposes.
5. A short new M-section pointing to this document (Definition of Done).

### LL10.4 Open questions for the owner

1. Allow the Scholes-Williams IV cross-check (an exception to "OLS everywhere"), or drop LL4?
2. Should a stale-price finding (trigger B with a significant previous-day coefficient) ever replace the headline beta, or always stay beside it (current spec)?
3. Trigger (C) for cross-time-zone factor datasets: adopt with European mode?

---

## LL11. Test oracle (TLL01-TLL20)

Seeds per `docs/test-oracle.md` 0.2 (`rng = default_rng(20261118 + 400 + k)` for TLLk, to avoid colliding with T-numbers). Tolerances per 0.3: identities `1e-10`-`1e-12`; recovery `4 SE`; Monte Carlo rates with 3.5 binomial SE.

### DGPs

- **DGP-LL0/1/2/3** as LL7.1, built on DGP-A factors with `n = 2520`. Fixture builders return `PriceFrame` and `FactorFrame`; for DGP-LL1/2 the price path is `100 * cumprod(1 + r)` of the observed returns; the factor frame has two extra French rows (one before the first and one after the last price date) so every row has neighbours, unless a test says otherwise.
- **Theoretical se** for recovery tests: the HAC se of the fit itself (4 SE bounds).

### Construction and identities (deterministic)

- **TLL01 Calendar neighbours.** French dates `D1..D10`; stock trades `D1..D10` except `D5` (so `D6` is `multi_day_return` and excluded by M2). For the row `D7`: `f^-` equals French `D6` (not `D4`, the previous row of `S`), `f^+` equals `D8`. Exact.
- **TLL02 Sample-end rule.** (a) French file ends at `T_end`: the last row of `S` is excluded with reason `lead_after_sample_end`; `n_LL = n - 1`. (b) `requested_end` earlier than the French last date: same exclusion, and replacing every French row dated after `T_end` with random values leaves every output bitwise unchanged. (c) Calling `factor_at_offset(..., offset=+1, t_end)` for the last row raises `LookAheadError`.
- **TLL03 Reference call.** Coefficients, se, p equal `sm.OLS(y, X16, missing="raise").fit(cov_type="HAC", cov_kwds={"maxlags": L(n_LL), "kernel": "bartlett", "use_correction": False}, use_t=False)` to `1e-10` relative.
- **TLL04 Summed betas and timing adjustments.** `beta^LL`, `tau` and their se equal `res.t_test(R)` for the selection matrices of LL2.1 (`1e-10` relative).
- **TLL05 Alpha identity.** `alpha^LL == mean(y) - theta[1:]' mean(X16[:, 1:])` within `1e-12` absolute; `|alpha^LL - (mean(y) - beta^LL' mean(f))| <= sum_i |b^-_i| |mean(f^-_i) - mean(f_i)| + |b^+_i| |mean(f^+_i) - mean(f_i)| + 1e-12` (edge-term bound, exact inequality).
- **TLL06 Scholes-Williams identities.** `theta^SW == solve(Z'X, Z'y)` (`1e-12`); `alpha^SW == mean(y) - beta^SW' mean(f)` (`1e-12`); with one factor, `|beta^SW - (b_-1 + b_0 + b_+1)/(1 + 2 rho_m)| <= 5e-3` on DGP-LL0 (`n = 2520`; observed differences on SPY `1e-5` to `8e-4` [V]).

### Recovery on DGPs (fixed seed, plus the nightly seed sweep)

- **TLL07 Synchronous.** DGP-LL0: each `|beta^LL_i - beta_i| <= 4 se`; each `|tau_i| <= 4 se(tau_i)`.
- **TLL08 Stale stock.** DGP-LL1 (`theta = 0.3`): daily market beta within `4 se` of `(1 - theta) 1.10 = 0.77` and more than `4 se` below 1.10 (expected gap about 15 se, LL7.2); every `beta^LL_i` within `4 se` of `beta_i`; each lag coefficient within `4 se` of `theta beta_i`; F11 rejects the market (expected z about 13). Market-only Dimson: HML within `4 se` of `0.7 x (-0.40)` (shows why LLD1).
- **TLL09 Late close.** DGP-LL2: market lead coefficient within `4 se` of `kappa 1.10 = 0.055`; `beta^LL_mkt` within `4 se` of 1.10.
- **TLL10 Stale factor (documents the known bias, `slow`).** DGP-LL3, `R = 200`: mean Dimson market sum minus 1.10 in `[-0.040, -0.014]` (observed -0.027 with Monte Carlo se 0.0023 at `R = 400`; band = 3.5 MC se at `R = 200` plus 0.002 for the seed sweep); mean SW market estimate within `[1.085, 1.115]`.
- **TLL11 Size and power of F11 (`slow`).** `R = 1000`: synchronous DGP, share with any F11 rejection `<= 0.09` at `n = 504` and `<= 0.074` at `n = 2520` (observed 0.065 and 0.046; bounds 0.05 + 3.5 x 0.0069 + 0.015 slack for BH dependence at small `n`); stale `theta = 0.3`: `>= 0.99` at both sizes; stale `theta = 0.1`, `n = 2520`: `>= 0.70` (observed 0.786, 3.5 SE = 0.045).
- **TLL12 Summed-beta coverage (`slow`).** DGP-LL0, `n = 504`, `R = 2000`: non-coverage of the 95% interval of the summed market beta in `[0.030, 0.085]` (observed 0.065).

### Trigger, gate interaction, statuses

- **TLL13 Trigger table (pure function).** Inputs `(gate_fired, f11_any, n_LL)`: `(F, F, 8000)` gives `not_applicable` with the LL6.1 reason; `(T, F, 8000)`, `(F, T, 8000)`, `(T, T, 8000)` give `ok`; `(T, T, 499)` gives `insufficient_data`; F11 `insufficient_data` counts as not rejected. Exact.
- **TLL14 Gate blind spot is covered.** DGP-LL1 (`theta = 0.3`): gate does not fire (`rho_1 > 0`), F11 rejects, section status `ok`.
- **TLL15 Headline invariance.** On DGP-LL1 and on a gate-firing fixture (DGP-LL2 with noise sd 0.010): every M3 number, every M3.2/M3.6 tag, every M4 rolling series and every ex-ante beta is bitwise identical with the lead-lag module enabled and disabled.
- **TLL16 Families.** F10 and F11 rejections equal `multipletests(p, alpha=0.05, method="fdr_bh")` on the five p-values; `m = 5`; a factor whose design-guard check fails is left out with `m` reduced (M0.6).
- **TLL17 Minimum sample and guard.** `n_LL = 499`: `insufficient_data`, numbers `null`; `n_LL = 500`: `ok`. A factor file with HML duplicated into CMA: `failed`, factor named.

### No look-ahead

- **TLL18 Truncation and perturbation.** DGP-LL1 with `t* = 1800`: the report truncated at `t*` has all lead-lag outputs stamped `t*`, `n_LL = t* - 1` rows (of a sample starting at row 1), and replacing every price and factor row after `t*` leaves the truncated outputs bitwise unchanged.
- **TLL19 No stamped series and static scan.** The schema has no per-date lead-lag field (introspection). The T104 scan of `analytics/` finds forward indexing only inside `lead_lag.factor_at_offset`.

### Wording

- **TLL20 Sentence selection.** Pure function on `(trigger, F11 rejections, b^-, b^+)`: each LL9.2 case produces exactly its sentence; LL9.3 appears iff the headline and F10 tags differ, with the bracketed clause iff F11 does not reject that factor.

Live smoke (`live`, non-blocking, outside the numbering above): SPY full history: gate fires, F11 rejects none, section `ok` via trigger (A), lead-lag market beta in `[0.98, 1.05]`, `|rho_1(lead-lag) - rho_1(daily)| <= 0.03`.

---

## LL12. Registry entries (demonstrations run for this document)

Format: protocol Appendix A. Listed here because this task writes documents only; they must be appended to `docs/registry/tests.jsonl` (with fresh `test_id`s if these collide) in the change that adds this spec. Nothing was pre-registered: the specifications were chosen while writing this document, so every line has status `run` and split role `in_sample_only`, and no confirmatory claim is made. Common fields: `created_at` 2026-11-18; `code_version` none (scratch scripts `common.py`, `check_common.py`, `ll_spy.py`, `ll_vr5.py`, `ll_size_ac.py`, `sim_ll.py`, `sim_trigger.py` in the scratchpad folder `specs-ll-fr/scripts`); dataset `us_ff5_daily` stamp 202609 SHA-256 `e58577223032aa45071a46686f7068900c371b516c9eb04e28e974c34264f84f`; SPY yfinance 1.8.0, downloaded 2026-11-18; HAC per M0.5 with `L(m)`.

Hypothesis ids: `H-201` "For SPY, lead-lag (Dimson per factor, 1/1) betas differ from same-day betas" (descriptive; F11 per period is the test). `H-202` "Per-factor Dimson and SW recover the known betas of a stale stock; market-only Dimson and daily OLS do not" (simulation, no p-value). `H-203` "F11 has nominal size and detects stale prices that the M3.6 gate misses" (simulation). `H-204` "French factors are autocorrelated before 2000" (descriptive).

| test_id | hypothesis_id | Spec | Result | Notes |
| --- | --- | --- | --- | --- |
| T-20261118-200 | - | Reproduction of the validation SPY fit, n 8474 | alpha -0.5765%/yr, z -2.2367; se = statsmodels to 7e-14 | pipeline check, not a test |
| T-20261118-201..207 | H-201 | SPY 1993-02-01..2008-12-30, n 4010: daily, Dimson 1/1 (+Wald 10, style Wald 8, F11), Dimson market-only, Dimson 2/2, SW IV, CAPM SW classic vs IV, 5-day sums | LL8 table; F11 none rejected; Wald p 5e-14; style Wald p 6e-10 | 7 lines |
| T-20261118-208..214 | H-201 | Same 7 specs, 2010-01-04..2026-09-29, n 4210 | LL8; F11 none; Wald p 0.58 | 7 lines |
| T-20261118-215..221 | H-201 | Same 7 specs, 1993-02-01..2026-09-29, n 8473 | LL8; F11 none; Wald p 2e-10 | 7 lines |
| T-20261118-222 | H-201 | 2023-01-03..2026-09-29, n 938: daily and Dimson 1/1, `rho_1`, VR5, F11 | `rho_1` -0.353 -> -0.371; VR5 0.31; F11 none; Wald p 0.64 | added after the coordinator pointed to `docs/data-source-comparison.md` |
| T-20261118-223 | H-201 | `rho_1` and VR5 of daily and Dimson residuals, three periods above | LL6.3 | |
| T-20261118-224 | H-204 | Lag-1 autocorrelation of 5 factors, 9 blocks 1963-2026 | LL7.4 | 45 values, descriptive |
| T-20261118-225..228 | H-202 | Simulation DGP-LL0..LL3, n 2520, R 400, seeds +900..903, 5 estimators each | LL7.2 | |
| T-20261118-229..230 | H-203 | Wald(10) size and summed-beta coverage, synchronous DGP, n 504 and 2520, R 2000, seeds +904, +905 | 0.1145 / 0.063; non-coverage 0.065 / 0.0435 | |
| T-20261118-231..240 | H-203 | Gate and F11 rates, 5 DGPs x n {504, 2520}, R 1000, seeds +1000..+1041 | LL3.2 table | |

Sources checked on 2026-11-18: Crossref API records for the four JFE papers; IDEAS/RePEc pages <https://ideas.repec.org/a/eee/jfinec/v5y1977i3p309-327.html>, <https://ideas.repec.org/a/eee/jfinec/v7y1979i2p197-226.html>, <https://ideas.repec.org/a/eee/jfinec/v12y1983i2p279-283.html>; Semantic Scholar API (abstracts elided by the publisher); Chung (2024) PDF via <https://cfr.ivo-welch.org/forthcoming/papers/chung2024simply.pdf>. ScienceDirect pages returned HTTP 403.

## Owner decisions (2026-11-18)

1. **Scholes-Williams cross-check:** approved. It is shown as a secondary estimate next to the Dimson betas.
2. **Fragility warning threshold** (fixed at k ≤ 5 or scaled with sample size): postponed. See `docs/specs/fragility-score.md`.
3. **Whether a lead-lag beta may ever replace the headline beta:** postponed. Until decided, it never does.
4. **Quality-gate caveat wording:** approved. The caveat must not blame late vendor closes, because the reversal persists on official closing prices.
