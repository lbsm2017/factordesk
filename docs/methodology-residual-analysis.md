# factordesk methodology: residual (alpha) analysis

Status: specification for a new feature, written 2026-11-18. Not yet implemented.
Audience: engineers implementing `backend/factordesk/analytics/residual.py`, `backend/factordesk/analytics/residual_stability.py` and the schema additions; reviewers checking the code against it.
Companion: `docs/test-oracle-residual-analysis.md` (tests TR01-TR40). Section ids here are R0-R9; ids from the main specification (`docs/methodology.md`: M0-M16, D1-D20) and its oracle (`docs/test-oracle.md`: T01-T115) are cited unchanged.

Rule of precedence: every convention of `docs/methodology.md` M0 (units, date stamping, trailing windows, annualisation, HAC inference, multiple testing, status values, sample metadata, labels) applies here unchanged. Where this document needs something the main specification does not yet say, it is listed as a proposal in R9.2; this document does not override the main specification.

Owner decisions this specification implements:
- No forecast column. Nothing in this feature predicts future residual returns.
- No benchmark comparison yet. A later feature compares the stock's residual with SPY's own residual.
- The feature runs on the selected analysis sample `S` (M2) of the analysed ticker, with the full-sample regression of M3.

---

## R0. Scope, notation and classification

### R0.1 What the feature shows

The residual return is the part of the stock's daily excess return that the five factor exposures do not explain. The feature shows it twice:

1. **In-sample (static betas).** Betas are the full-sample OLS betas of M3, fitted on the same period they are applied to. This is the conventional "cumulative residual return from static betas of the selected period". Its average is the regression alpha by construction (R1).
2. **Point-in-time (trailing betas).** Each day's betas come from the `W_p` trading days that end the day before. Nothing estimated with that day or any later day enters that day's residual (R4).

A summary table, a cumulative chart with both lines on one date axis, a gap statement that says how much of the in-sample alpha survives point-in-time betas, a stability section and residual diagnostics complete the panel.

### R0.2 Notation (additions to M0.1)

All M0.1 symbols keep their meaning (`y_t`, `f_t`, `x_t`, `theta`, `A = 252`, `K = 5`, `n`, `S`).

| Symbol | Meaning | Unit |
| --- | --- | --- |
| `alpha_hat`, `beta_hat` | Full-sample OLS estimates over `S` (M3.1) | decimal/day, unitless |
| `e_hat_t` | Full-sample OLS residual `y_t - alpha_hat - beta_hat' f_t` (M3) | decimal/day |
| `u_t` | **In-sample residual return** `y_t - beta_hat' f_t = alpha_hat + e_hat_t`, `t in S` | decimal/day |
| `W` | Point-in-time beta window, equal to `W_p = beta_window` (M4, M15) | rows |
| `beta_tilde_t` | Ex-ante beta of M4: the OLS betas of the `W` rows `t-W .. t-1` (rolling stamp `t-1`) | unitless |
| `u_tilde_t` | **Point-in-time residual return** `y_t - beta_tilde_t' f_t`, defined for `t = W+1 .. n` | decimal/day |
| `S_c` | Comparison span: rows `W+1 .. n` of `S`; `m_c = n - W` rows. Identical to `S_dyn` of M6.3. | - |
| `gap_t` | `u_t - u_tilde_t = (beta_tilde_t - beta_hat)' f_t`, `t in S_c` | decimal/day |
| `Q_t` | Residual wealth index (compounded), R2 | ratio, starts at 1 |
| `CR_t` | Cumulative residual return `Q_t - 1` | decimal |

`u_t` is not the OLS residual `e_hat_t`: it keeps the intercept. `u_t` and `u_tilde_t` are unrelated to the cointegration residual `u_hat_t` of M11.

### R0.3 In-sample versus point-in-time: classification of every output

"In-sample" = uses betas (or alpha) estimated on rows that include the row being described, including later rows. "Point-in-time" = each daily value uses only rows dated `<= t`, and the betas applied to day `t` use only rows `<= t-1` (M0.2 items 1 and 3).

| Output | Class | Stamp (M0.2) |
| --- | --- | --- |
| `u_t`, in-sample statistics (R3 on `S`), in-sample chart lines | in-sample | `T_end` (full-sample output) |
| `u_tilde_t` and the point-in-time chart line value at `t` | point-in-time | `t` |
| Point-in-time summary statistics (R3 on `S_c`) | summary of a point-in-time series: every daily input is point-in-time; the summary uses all of `S_c` | `T_end` |
| Gap, survival ratio, verdict (R4.6-R4.8) | in-sample (it uses `beta_hat`) | `T_end` |
| Rolling 252-day alpha at `t` (R5.1) | in-window: betas and alpha fitted on rows `t-251 .. t`; as a series it uses no row after `t` | `t` |
| Non-overlapping window alphas, split-half alphas (R5.2, R5.3) | in-sample within each window or half | `T_end` |
| Calendar-year table (R5.4) | in-sample column and point-in-time column, labelled per column | `T_end` |
| Diagnostics (R6) | per basis, as above | `T_end` |

"Point-in-time" is subject to the data-vintage caveat of M0.2 item 5 (label L-VINTAGE): we hold one, latest, French vintage.

### R0.4 Parameters

This feature adds **no new tunable parameter**. It uses `beta_window` (M4, M15; allowed `{126, 252, 504}`, default 252) as `W`. Reason: the point-in-time residual mean over `S_c` then equals the "Unattributed" row `U` of the tilt/timing split (M6.3) exactly (R4.4), so the two panels can never disagree.

Fixed constants (not exposed): `A = 252`; rolling alpha window 252 (R5.1); minimum point-in-time span `m_c >= 252`; survival threshold 0.5 and warm-up-share threshold 0.5 (R4.8); significance level 0.05 and BH `q = 0.05` (M0.6); Ljung-Box lag 10, ARCH lag 5 (R6); partial-year threshold `n_Y < 200` (M6.2); `z_0.975 = 1.959964`.

---

## R1. In-sample residual return (static betas) — `analytics/residual.py`

### R1.1 Definition

For every row `t` of `S`, with `alpha_hat`, `beta_hat` from the full-sample regression of M3.1 (OLS with intercept, HAC per M0.5, `L = L(n)`):

`u_t = y_t - sum_i beta_hat_i f_{i,t} = alpha_hat + e_hat_t`.

`y_t = r_t - RF_t` is the excess return (M2 step 5). The residual return therefore **includes alpha**. It is never computed from raw returns `r_t` (that would add `RF_t` to every value; see test TR31).

### R1.2 Identities (exact, from the OLS normal equations with an intercept)

The normal equations give `sum_t e_hat_t = 0` and `sum_t e_hat_t f_{i,t} = 0` for each `i`. Hence, over `S`:

1. **Mean equals alpha.** `mean(u) = alpha_hat + mean(e_hat) = alpha_hat`. Annualised: `A mean(u) = alpha_ann` (M3.1).
2. **Arithmetic drift equals alpha.** `sum_{t=1..n} u_t = n alpha_hat`. The chord of the arithmetic cumulative sum from its start to its end has slope exactly `alpha_hat` per day. This is what "the cumulative drift of the static residual is alpha by construction" means.
3. **No in-sample factor exposure.** The sample covariance of `u` with each factor is zero: `sum_t (u_t - mean u)(f_{i,t} - mean f_i) = sum_t e_hat_t f_{i,t} - mean(f_i) sum_t e_hat_t = 0`.
4. **Volatility equals the regression's residual volatility.** `sd(u, ddof=1) = sd(e_hat, ddof=1)`, so `sqrt(A) sd(u) = sigma_e_ann` of M3.1 and `A var(u) = A sigma2_e` of M7.
5. **Variance split.** `var(y) = beta_hat' Sigma_f beta_hat + var(u)` (all `ddof = 1`), the M7 identity.

### R1.3 What is mechanical and what is informative

| Feature of the in-sample series | Mechanical or informative | Why |
| --- | --- | --- |
| Its mean, its annualised residual return, the end point of its arithmetic cumulative sum | Mechanical: a restatement of `alpha_hat` (M3) | Identities 1-2 |
| Its zero correlation with every factor | Mechanical | Identity 3; OLS chooses `beta_hat` to make it so on this sample |
| Its volatility | Mechanical: equals `sigma_e_ann` (M3) | Identity 4. It is also biased low: OLS minimises in-sample residual variance, `E[SSR/(n-1)] = sigma_e^2 (n-6)/(n-1)` under the model |
| Its t-statistic | Mechanical: the M3 alpha z (R3.4) | Same hypothesis |
| The **path**: when the residual return accrued (steadily or in a few episodes), its drawdowns | Informative | Not determined by `alpha_hat` |
| The **distribution**: hit rate, skew, kurtosis, autocorrelation, volatility clustering | Informative | Not determined by `alpha_hat` |
| Sub-period behaviour (R5) | Informative, with the caveat that a static beta leaks factor exposure into sub-periods when the true beta moved (R4.2, TR21) | |
| Comparison with the point-in-time series (R4) | Informative | Measures how much of `alpha_hat` depends on betas fitted with hindsight |

### R1.4 Why a drifting line is not evidence of skill

`sum_{s<=t} u_s` is a random walk whose end point is pinned to `n alpha_hat`. With zero true alpha, `alpha_hat` is still non-zero: under the model its annualised standard error is about `sigma_e_ann / sqrt(n / A)`. For a stock with 19% residual volatility over 10 years that is about 6% a year, so the typical in-sample line ends `sqrt(2/pi) x 6% = 4.8%` a year away from zero, and about 62% of zero-alpha stocks show `|alpha_ann| >= 3%` (TR20 measures 0.621 over 1000 simulated stocks). The in-sample line always drifts; only the t-statistic says whether the drift is larger than noise of this size.

If the true betas move over time, `alpha_hat` also absorbs the average of `(beta_t - beta_hat)' f_t`, including any co-movement of the beta with the factor's own return (the "timing" of M6.3). In-sample residual return can therefore be factor exposure that the static betas failed to remove (R4.2, TR22).

### R1.5 Labels

Every in-sample output carries L-DESC, L-VINTAGE and the new key **L-INSAMPLE** (R7.1): "In-sample: betas are fitted on this same period." The in-sample statistics add (caption): "The in-sample residual return equals the regression alpha exactly, because the betas were fitted on these same days."

---

## R2. Cumulative residual return — `analytics/residual.py`

### R2.1 Convention

For a residual series `x_1 .. x_m` (either `u` or `u_tilde`) over a span, the residual wealth index and cumulative residual return are

`Q_0 = 1`, `Q_j = prod_{i=1..j} (1 + x_i)`, `CR_j = Q_j - 1`, labelled "cumulative (compounded)" (M0.4).

**Portfolio it represents.** Hold capital `K_{t-1}` at the close of day `t-1`. Invest it at `RF`; buy `K_{t-1}` of the stock financed at `RF`; short `beta_mkt K_{t-1}` of the market with the proceeds earning `RF`; and take `-beta_i K_{t-1}` notional in each zero-cost long-short style factor. The day-`t` gain is

`K_{t-1} [ RF_t + (r_t - RF_t) - beta_mkt (R_m,t - RF_t) - sum_style beta_i f_{i,t} ] = K_{t-1} (RF_t + x_t)`.

Its return relative to cash is `(1 + RF_t + x_t)/(1 + RF_t) - 1 = x_t / (1 + RF_t)`. So `Q_j` is the growth of this book relative to cash up to a relative error of at most `max RF_t` (below `2e-4`, M1.1 bound) per day's residual.

**Why compounding is legitimate here.** The positions are reset to the current capital every day (daily rebalancing at fixed hedge ratios). The return on capital on day `t` is then `x_t` whatever happened before, so the capital after `j` days is exactly `prod (1 + x_i)` of the starting capital. Without daily rebalancing, the stock and hedge legs would drift apart with relative performance and the book's return would no longer be `x_t`. Compounding a residual is therefore a statement about this specific paper strategy, not about the stock.

**What it ignores.** Trading costs of rebalancing every leg every day; the cost of replicating the factor legs (the French factors are paper portfolios of many stocks, rebuilt once a year, not instruments you can trade at zero cost); financing at broker rates instead of `RF`; short rebates and stock borrowing fees on every short leg; margin, leverage limits and gross exposure of about `1 + sum |beta_i|`; taxes; execution at closing prices; and, for the in-sample line only, the fact that `beta_hat` was not known until the end of the period.

### R2.2 Compounded line versus arithmetic table value

The table's residual return is arithmetic (`A mean(x)`, R3.1); the chart compounds. They differ by the compounding drag, and they are never added together (M0.4).

- Exact: `ln Q_m = sum_i ln(1 + x_i)`.
- Expansion: `A mean(ln(1 + x)) = A mean(x) - (A/2) mean(x^2) + R`, with `|R| <= A mean(|x|^3 / (3 (1 - |x|)^3))` for `|x| < 1` (TR07 checks the inequality, not a tolerance).
- Since `(A/2) mean(x^2) = vol_ann^2 (m-1)/(2m) + (A/2) mean(x)^2`, the log growth rate of the line is about `A mean(x) - vol_ann^2 / 2`. For 30% residual volatility this is 4.5% a year: a stock with zero alpha has a falling compounded residual line.
- In-sample, the line's log growth rate is therefore about `alpha_ann - sigma_e_ann^2 / 2`, by construction. Caption: "The line compounds daily. It sits below the residual return in the table by about half the residual variance a year ({drag} here)", with `drag = vol_ann^2 / 2` of the series shown.

### R2.3 Spans and starting values

Three cumulative series are produced (R7.4), all aligned to the dates of `S`:

| Series | Span | Start |
| --- | --- | --- |
| `in_sample_full` | all rows of `S` | `Q_0 = 1` sits before row 1 and has no date; row 1 carries `CR_1 = u_1` |
| `in_sample_compare` | rows `W .. n` | anchor: value `0.0` at row `W`; row `t > W` carries `prod_{s=W+1..t} (1 + u_s) - 1`; rows `< W` are null |
| `point_in_time_compare` | rows `W .. n` | anchor `0.0` at row `W`; row `t > W` carries `prod_{s=W+1..t} (1 + u_tilde_s) - 1`; rows `< W` are null |

The two comparison lines start at zero on the same date (the last warm-up row `W`) so their levels can be compared. The anchor value `0.0` uses no data. Rebasing identity: `1 + in_sample_compare_t = Q^full_t / Q^full_W` (TR06).

The anchor is at the start, positionally fixed by `W`; truncating the sample later never moves it, so `point_in_time_compare` stays point-in-time (TR15).

### R2.4 Excluded rows and NaN

- `S` contains no NaN by construction (M2 step 3). Residuals exist only on rows of `S`. Excluded rows (M2: `multi_day_return`, `no_factor_row`, `price_missing`, `factor_missing`) have no residual and are **not filled**: the compounded series moves from the previous row of `S` to the next one, and the chart draws a straight segment across the gap. Nothing is set to zero.
- Caption when `n_excluded > 0`: "Skips {n_excluded} excluded days (listed under sample details)."
- Warm-up rows have `u_tilde = null`, never `0`.
- Analytics functions validate their inputs: a non-finite value in `y`, `f`, `beta_hat` or a non-warm-up `beta_tilde` raises `ValueError` (contract violation, as `rolling_ols_hac` does). No `fillna`, `bfill`, `interpolate` or `dropna` inside `analytics/residual*.py` (static scan T104/TR35).

### R2.5 Uncovered tail

Ticker dates after the factor file's `last_date` (M2 step 6) have no `RF` and no factors, so no residual exists there. All residual series end at `T_end <= last_date`. The chart object carries `n_uncovered` and `uncovered_from` so the UI can grey the tail and show the memo: "No factor data after {last_date}: the residual is unknown for the last {n_uncovered} trading days." The tail never enters a statistic (TR29).

### R2.6 Wipe-out rule

If `1 + x_t <= 0` on some row (a daily residual loss of 100% or more, possible only with extreme moves and large betas), the paper book has lost all capital: set `Q = 0` (`CR = -1`) from that row on, `compound_growth_annual = -1`, `max_drawdown = -1`, `wiped_out = true`, and add the warning `residual_wipeout` ("The hedged position lost all its capital on {date}; later days are not compounded."). Arithmetic statistics (R3.1-R3.5) are unaffected (TR10).

---

## R3. Summary statistics — `analytics/residual.py`

### R3.1 Definitions

For a residual series `x_1 .. x_m` over a span (in-sample: `x = u`, span `S`, `m = n`; point-in-time: `x = u_tilde`, span `S_c`, `m = m_c`). `sd` uses `ddof = 1` (M0.1).

| Field | Definition | Unit |
| --- | --- | --- |
| `residual_return_annual` | `A mean(x)` (arithmetic, M0.4) | decimal/year |
| `residual_return_se_annual` | `A se(mean x)`, se per R3.2 | decimal/year |
| `residual_return_ci_low_annual`, `_high_` | `A mean(x) -/+ 1.959964 A se` | decimal/year |
| `z`, `p` | `mean(x) / se`; two-sided `p = 2 (1 - Phi(abs(z)))` | -, - |
| `tag` | `"reliable"` iff `p < 0.05` (single test), else `"noise"` | - |
| `residual_vol_annual` | `sqrt(A) sd(x)` | decimal/year |
| `information_ratio` | `residual_return_annual / residual_vol_annual = sqrt(A) mean(x) / sd(x)` | per sqrt(year) |
| `information_ratio_ci_low`, `_high` | `residual_return_ci_{low,high}_annual / residual_vol_annual` (approximate, R3.3) | - |
| `cumulative_return` | `Q_m - 1` (R2.1, wipe-out rule R2.6) | decimal |
| `compound_growth_annual` | `Q_m ^ (A/m) - 1` (`-1` if wiped out) | decimal/year |
| `hit_rate` | `#{i : x_i > 0} / m` (a zero is not a hit) | share |
| `max_drawdown` | `min_j (Q_j / max_{0<=i<=j} Q_i - 1)` with `Q_0 = 1` included, so a loss from the start counts | decimal, `<= 0` |
| `max_drawdown_peak` | date of the latest `i <= trough` with `Q_i = max_{0<=k<=trough} Q_k`; `null` if that is `Q_0` (the start) | date |
| `max_drawdown_trough` | date of the first `j` attaining the minimum | date |
| `max_drawdown_recovery` | first date after the trough with `Q_j >= Q_peak`; `null` if not recovered | date |
| `noise_drawdown_reference` | `-(1 - exp(-sqrt(pi/2) residual_vol_annual sqrt(m/A)))` | decimal, `<= 0` |
| `skew` | `m3 / m2^1.5`, central moments with divisor `m` (the values `jarque_bera` returns) | - |
| `excess_kurtosis` | `m4 / m2^2 - 3`, same moments | - |

If `max_drawdown = 0`, the three drawdown dates are `null`. For the comparison span, `Q_0` is the anchor at row `W` and a `null` peak means "the start of the comparison span".

If `sd(x) = 0` the series is degenerate: the statistic has status `not_applicable`, reason "residual is constant".

### R3.2 Inference on the mean

- **In-sample:** `se`, `z`, `p`, CI and `tag` are **copied from M3** (`alpha_se_annual / A`, `alpha_z`, `alpha_p`, alpha CI, `alpha_tag`). Do **not** run a separate t-test on the series `u`. A location test on `u` treats `beta_hat` as known, but it was estimated on the same rows: for OLS standard errors the exact relation is `Var(alpha_hat) = (s^2 / n) (1 + fbar' Sigma_pop^-1 fbar)` (`Sigma_pop` = factor covariance with divisor `n`), so a test on `u` alone omits the factor-mean term and overstates `|z|` slightly. One hypothesis, one number: the residual table and the regression KPI must show the same t.
- **Point-in-time:** `beta_tilde_t` is fixed before day `t`, so `u_tilde_t` is the realised return of a strategy specified in advance. A HAC location test is valid: OLS of `u_tilde` on a constant only over `S_c`, Newey-West per M0.5 with `L = L(m_c)`. Reference call: `sm.OLS(x, np.ones(m)).fit(cov_type="HAC", cov_kwds={"maxlags": L(m), "use_correction": False}, use_t=False)`. Estimation noise in `beta_tilde` is part of the strategy's return and is therefore inside the HAC variance.

### R3.3 Residual Sharpe = residual information ratio

The panel label is "Residual Sharpe (information ratio)". It is the annualised residual return per unit of annualised residual volatility, `IR = sqrt(A) mean(x) / sd(x)`, annualised like M0.4 Sharpe (`mean_ann / vol_ann`; no `RF` is subtracted because `x` is already an excess, hedged return).

- **Not comparable with a total-return Sharpe ratio.** The numerator excludes all factor returns, including the equity premium, and the denominator excludes all factor risk. A stock with a total-return Sharpe of 0.5 can have a residual IR of 0, and the reverse.
- **Relation to the alpha t-statistic.** With OLS standard errors the identity is exact:
  `z_OLS(alpha_hat) = (IR / sqrt(A)) sqrt(n) sqrt((n - 6)/(n - 1)) / sqrt(1 + fbar' Sigma_pop^-1 fbar)` (TR04).
  The last factor is 1 plus the squared maximum daily Sharpe ratio of the factors (about `1/A` to `4/A`), so in practice `z ≈ IR sqrt(years)`. With HAC standard errors the relation is approximate. Reading: an IR of 0.5 held for 10 years gives `z ≈ 1.6`, still not distinguishable from zero.
- **Confidence interval.** The IR interval divides the mean's HAC interval by the estimated volatility. It ignores the sampling error of the volatility. For iid returns the delta method (Lo, 2002) gives `Var(IR_hat_daily) ≈ (1 - skew IR_daily + (kurtosis - 1) IR_daily^2 / 4) / m`, where the 1 is the part this interval keeps. For `|IR| < 1` a year (`|IR_daily| < 0.063`), `|skew| < 1` and kurtosis below 10, the omitted terms add less than 10% to the variance, so the interval is at most about 5% too narrow. It is labelled "approximate".
- **No interval** is given for volatility (a normal-theory chi-square interval is wrong under the fat tails and volatility clustering R6 typically finds), hit rate (it is not a test of alpha: skewed residuals can have a positive mean and a hit rate below 50%), or maximum drawdown (path-dependent; the noise reference is the reading aid instead).

### R3.4 Noise drawdown reference

For a driftless Brownian motion with volatility `sigma`, the expected maximum drawdown over `T` years is `sqrt(pi/2) sigma sqrt(T) ≈ 1.2533 sigma sqrt(T)` in log units (Magdon-Ismail, Atiya, Pratap and Abu-Mostafa, 2004). `noise_drawdown_reference` converts this to a simple return. It is a rough yardstick: daily residuals are fat-tailed and the compounded line also has the `-sigma^2/2` log drift (R2.2), so pure noise often falls further. Example: 25% residual volatility over 10 years gives about -63%.

### R3.5 Reading rules (one line each; shown as tooltips)

| Statistic | Reading rule |
| --- | --- |
| Residual return | What the stock earned per year beyond its factor exposures, alpha included. In-sample it equals the regression alpha exactly. |
| t-statistic | Distance of the residual return from zero in standard errors. Between -2 and 2 (p above 0.05), you cannot tell it from zero. |
| 95% interval | Range of residual returns consistent with the data. If it spans zero, the sign is not established. |
| Residual volatility | How much the stock moves for reasons the five factors do not explain. Higher volatility makes alpha harder to measure. |
| Residual Sharpe (IR) | Residual return per unit of residual risk. Do not compare it with a total-return Sharpe. 0.5 for 10 years is only about 1.6 standard errors. |
| Cumulative / compound growth | What the daily-rebalanced paper hedge compounded to, before costs. Lower than the residual return by about half the residual variance a year. |
| Hit rate | Share of days the residual was positive. Near 50% is normal; it says how often, not how much. |
| Max drawdown | Worst fall of the cumulative residual line from a previous high. Pure noise with this volatility typically falls about {noise_drawdown_reference}. |
| Skew | Below 0: rare large residual losses. Above 0: rare large gains, often earnings days. |
| Excess kurtosis | Above 0: more extreme days than a normal distribution. Intervals here are then approximate. |

### R3.6 Minimum samples (additions to M0.7)

| Statistic | Minimum | If not met |
| --- | --- | --- |
| In-sample residual statistics, chart line, diagnostics | the `FactorReport` minimum, `n >= 504` | request refused (M0.7) |
| Point-in-time residual statistics, comparison lines, gap, point-in-time diagnostics, point-in-time column of the calendar table | `m_c = n - W >= 252` (so `n >= 504` for `W in {126, 252}`, `n >= 756` for `W = 504`) | status `insufficient_data`, reason "Point-in-time residual needs at least {W + 252} trading days; this period has {n}." |
| Rolling 252-day alpha | `n >= 252` (always met) | - |
| Non-overlapping windows family | `J = floor(n / 252) >= 2` (always met) | - |
| Split-half alphas | each half `>= 252` rows (always met when `n >= 504`) | - |

If the M3 regression has status other than `ok`, every residual statistic has status `failed`, reason "Full-sample regression unavailable".

---

## R4. Point-in-time residual — `analytics/residual.py`

### R4.1 Definition

For `t = W+1 .. n` (positions in `S`):

`u_tilde_t = y_t - sum_i beta_tilde_{i,t} f_{i,t}`, with `beta_tilde_t = beta_hat^{(W)}_{t-1}`,

the M4 rolling OLS betas of the window stamped at row `t-1`, which contains exactly the `W` rows `t-W .. t-1` (M0.3). Reuse `rolling.ex_ante_betas(rolling_betas(sample, W))`; do not refit. The window's own intercept is **not** subtracted: like `u_t`, `u_tilde_t` includes alpha. Rows `1 .. W` are the warm-up: `u_tilde` is null there.

Windows are positional on the rows of `S`. If excluded rows fall inside a window, the window still has `W` rows of `S` and spans more calendar days (M0.3); its first and last dates are in the M4 output.

### R4.2 Choice of window and properties

`W = beta_window`, default 252, as in M4/M15. The trade-off, under constant true betas and iid errors, with `K = 5`:

| `W` | Extra residual variance from beta estimation, about `K / W` | Residual volatility inflation | Warm-up lost | Lag to absorb half a beta break |
| --- | --- | --- | --- | --- |
| 126 | 4.0% | +2.0% | 126 rows | about 63 rows |
| 252 (default) | 2.0% | +1.0% | 252 rows | about 126 rows |
| 504 | 1.0% | +0.5% | 504 rows (needs `n >= 756`) | about 252 rows |

Derivation: `u_tilde_t = alpha + e_t + (beta - beta_tilde_t)' f_t`. With `beta_tilde_t` independent of `f_t` and `Cov(beta_tilde) ≈ sigma_e^2 Sigma_f^-1 / W`, the last term has mean `(beta - E beta_tilde)' mu_f = 0` and variance `≈ sigma_e^2 tr(Sigma_f^-1 Sigma_f)/W = sigma_e^2 K / W`. So:

- `E[mean(u_tilde)] = alpha`: the point-in-time residual return is unbiased for alpha under constant betas.
- `Var(u_tilde) ≈ sigma_e^2 (1 + K/W)`, while the in-sample residual variance is biased low by `(n - 6)/(n - 1)`. Expected ratio of volatilities `≈ sqrt((1 + K/W)(n - 1)/(n - 6))`, 1.011 for `n = 2520, W = 252` (TR19 measures 1.011, sd 0.005).
- When the true betas move, the static `beta_hat` mis-hedges and leaks factor exposure into `u_t` within sub-periods; `beta_tilde` follows the move with a lag of about `W/2` rows, so `u_tilde` carries little leftover exposure once the window has passed the change (TR21: after a market-beta break from 0.5 to 1.5, the in-sample residual keeps a market slope of about +0.50; the point-in-time residual about 0.00).

**What the point-in-time residual does not do.** It removes hindsight from the betas. It does **not** give a fresh sample for alpha: both series are built from the same days and the same stock-specific shocks `e_t`. Under constant betas their means differ only by beta-estimation noise, with an annualised standard deviation of about `sigma_e_ann sqrt(K/W) / sqrt(m_c / A)` (0.6-0.9% a year in the oracle DGPs, against an alpha standard error of about 6% a year). So the comparison detects in-sample alpha that comes from hindsight betas or moving exposures; it cannot detect luck. In 1000 simulated zero-alpha stocks, 5.0% had a reliable in-sample alpha and 3.2% had a reliable in-sample alpha that also survived point-in-time betas (TR20). The word "out-of-sample" in user copy refers to the betas only, and the caveat copy (R8.5) says so.

### R4.3 Statistics

All fields of R3.1 are computed for `u_tilde` over `S_c` with `m = m_c`, inference per R3.2 (HAC location test, `L(m_c)`). Labels: L-DESC-PIT (R7.1), L-VINTAGE.

### R4.4 Identity with the tilt/timing split

`S_c = S_dyn` of M6.3 and `U = A mean_{S_dyn}(y) - sum_i Dyn_i = A mean_{S_c}(y - beta_tilde' f) = A mean_{S_c}(u_tilde)`. Hence `point_in_time.residual_return_annual == U` exactly (tolerance `1e-10`, TR13). The M6.3 label calls `U` "alpha, residual and rolling-estimation error"; this panel is its decomposition over time.

### R4.5 Warm-up period

Rows `1 .. W` have no point-in-time residual. They are null in `point_in_time_compare` and `in_sample_compare` (the comparison lines start at the anchor, row `W`). The chart shades rows `1 .. W-1` with the caption "Warm-up: the first {W} trading days are used to estimate the first point-in-time betas." The in-sample statistics and `in_sample_full` still cover them.

### R4.6 Side-by-side presentation

- **Table:** two columns, "In-sample (static betas)" over `S` and "Point-in-time (trailing {W}-day betas)" over `S_c`. The header row states each column's dates and `n`. The in-sample column therefore matches the regression KPI exactly (alpha, t, residual volatility).
- **Chart:** `in_sample_compare` and `point_in_time_compare`, both starting at zero at row `W`, over the same days. A toggle shows `in_sample_full` alone ("Full period, in-sample").
- **Gap statement:** one sentence under the chart (R4.8), computed on the same days `S_c` for both series.

### R4.7 Gap statistics (span `S_c`)

| Field | Definition |
| --- | --- |
| `in_sample_same_days_annual` | `a_c = A mean_{S_c}(u)` (the in-sample residual on the comparison days; not exactly `alpha_ann` because the residuals sum to zero over `S`, not over `S_c`) |
| `point_in_time_annual` | `a_pit = A mean_{S_c}(u_tilde)` |
| `gap_annual` | `a_c - a_pit = A mean_{S_c}(gap_t)` |
| `gap_se_annual`, `gap_z`, `gap_p` | HAC location test on `gap_t` over `S_c`, `L(m_c)`. Approximate: it treats `beta_hat` as fixed although it was estimated using these rows. Reported, not used by the verdict. |
| `comparison_share_of_alpha` | `q = a_c / alpha_ann` (null if `alpha_ann = 0`): how much of the full-period alpha rate is present on the comparison days |
| `survival_ratio` | `s = a_pit / a_c` (null if `a_c = 0`): share of the same-days in-sample residual return that survives point-in-time betas. UI shows it as a percentage, rounded to 5 points, capped at "more than 200%". |

### R4.8 Verdict (first matching rule wins)

Inputs: M3 alpha p-value `p_is` and `alpha_ann`; `a_c`, `a_pit`, `q`, `s`; point-in-time p-value `p_pit`. The verdict exists only when both residual statistics are `ok`; otherwise the gap statistic is `insufficient_data` (or `failed`) with the point-in-time reason.

| # | Condition | `verdict` | Severity | Message (exact copy; `{}` are filled, percentages to 1 decimal, ratios to 5 points) |
| --- | --- | --- | --- | --- |
| G1 | `p_is >= 0.05` and `p_pit >= 0.05` | `no_reliable_alpha` | info | "Neither residual return can be told apart from zero. Read both lines as noise." |
| G2 | `p_is >= 0.05` and `p_pit < 0.05` | `point_in_time_only` | info | "The point-in-time residual return is reliably {positive/negative} ({a_pit} a year), but the full-period alpha is not. This usually means the betas moved; check the Exposures section." |
| G3 | `alpha_ann * a_c <= 0` or `q < 0.5` | `concentrated_in_warmup` | info | "Most of the in-sample alpha comes from the first {W} trading days ({start} to {end}), before any point-in-time residual exists. You cannot check it here." |
| G4 | `s < 0` | `reversed` | warning | "In-sample alpha does not survive out-of-sample: with point-in-time betas the residual return has the opposite sign ({a_pit} a year against {a_c} on the same days)." |
| G5 | `s < 0.5` | `mostly_disappears` | warning | "In-sample alpha mostly disappears out-of-sample: point-in-time betas keep {s} of it ({a_pit} a year against {a_c} on the same days)." |
| G6 | `p_pit >= 0.05` | `survives_not_significant` | info | "Most of the in-sample alpha survives point-in-time betas ({s} kept), but the point-in-time residual return cannot be told apart from zero." |
| G7 | otherwise | `survives` | info | "In-sample alpha holds up with point-in-time betas ({s} kept) and is distinguishable from zero. This rules out hindsight in the betas, not luck." |

Justification of the thresholds:
- **0.05** is the project's single-test level (M0.6). "Survives" (G7) requires both the in-sample and the point-in-time test to reject with the same sign. This intersection-union rule has size at most 0.05 without correction; it is not much smaller than 0.05 because the two tests share the same shocks (measured 3.2%, R4.2).
- **`s < 0.5`** is the plain meaning of "mostly disappears" (less than half is kept). It is also far outside the noise of `s` under constant betas: when G3 does not fire and the in-sample alpha is reliable, `|a_c| >= 0.5 |alpha_ann| >= 0.98 se(alpha_ann)`, and the gap noise is about `0.15 se(alpha_ann)` (R4.2), so `s < 0.5` implies a gap of more than 3 noise standard deviations. In simulations with constant betas, G4/G5 fired in 0 of 1200 stocks (TR19, TR20); with a beta that rose while the market rallied, they fired in all 200 (TR22).
- **`q < 0.5`** stops the ratio `s` from being read when the comparison days carry less than half the full-period alpha rate; then the alpha was earned mainly in the warm-up and the comparison has nothing to test.

The verdict appears in the panel only. It is not part of the KPI strip or of the drift alert count (M9).

### R4.9 Labels

Point-in-time outputs carry L-DESC-PIT, L-VINTAGE and the new key **L-PIT**: "Point-in-time: each day uses betas estimated only from earlier days." The comparison chart and the gap carry both L-INSAMPLE and L-PIT.

---

## R5. Stability — `analytics/residual_stability.py`

### R5.1 Rolling 252-day alpha

At each stamp `t >= 252`: `alpha_ann_t = A alpha_hat^{(252)}_t`, the intercept of the M4 window of 252 rows `t-251 .. t` (already computed by M4 for `W = 252`; reuse it), with pointwise band `A (alpha_hat_t -/+ 1.959964 se_HAC,t)`, `L(252) = 4`. The window is fixed at 252 regardless of `beta_window`, so "one year" means one year.

- Descriptive count: `share_excluding_zero` = share of stamps whose band excludes zero. Not a test. Under zero alpha its expected value is about 5%, but consecutive stamps share 251 of 252 rows, so the realised share varies widely (often 0% or 20%).
- Labels: L-BAND (wording "Pointwise 95% band. Even with a constant true alpha, about 1 point in 20 falls outside."), L-OVERLAP, L-DESC, and "Each point uses the previous 252 trading days, ending on that date; alpha and betas are both refitted in each window."

### R5.2 Non-overlapping windows (the test of "how many years are significant")

Tile the sample from the end: `J = floor(n / 252)` windows, window `j = 0 .. J-1` = rows `n - 252(j+1) + 1 .. n - 252 j`. The first `n - 252 J` rows are not used. Window `j`'s alpha, se, z and p are those of the M4 stamp at row `n - 252 j` (identical by construction). The `J` p-values form BH family **FR1** (q = 0.05, M0.6). Report `n_reliable` = number rejected, `J`, and each window's dates, `alpha_annual`, `se_annual`, `z`, `p`, `p_adj_bh`, tag.

Copy: "{n_reliable} of {J} separate one-year windows show an alpha different from zero, after correcting for testing {J} windows."

Calibration note: each window's HAC test uses 252 rows and the normal reference (M0.5, D2) and over-rejects slightly (measured size 5.8% at nominal 5%, 0.74% at 0.5%). Under zero alpha, the probability that FR1 rejects at least one window is about 7% for `J = 10` rather than 5% (TR26).

### R5.3 Split-half alpha (one prespecified split)

`n_1 = floor(n / 2)`; first half rows `1 .. n_1`, second half `n_1 + 1 .. n`. Use the M10 common estimator with `g_t = 1[t > n_1]`:
`y_t = alpha + beta' f_t + gamma g_t + delta' (g_t f_t) + e_t`, HAC with `L(n)`.
First-half alpha `alpha_hat`; second-half alpha `alpha_hat + gamma_hat` with `Var = V_aa + V_gg + 2 V_ag`; both equal separate regressions on each half (point estimates). Difference test `gamma = 0`: single prespecified test, nominal 5%. Report both halves' dates, `n`, annualised alphas with CI95, the annualised difference, its `z` and `p`.

Copy: "Second-half alpha minus first-half alpha: {diff} a year (p = {p})." Caption: "One split, fixed in advance at the middle of the period. Betas are refitted in each half."

### R5.4 Calendar-year residual table

For each calendar year `Y` with `n_Y` rows of `S`:
- `in_sample_sum_Y = sum_{t in Y} u_t` (within-year sum of daily decimals, not annualised, not compounded; D7). Identity with M6.2: `in_sample_sum_Y = n_Y alpha_hat + sum_{t in Y} e_hat_t`, the alpha column plus the residual column of M6.2 (TR28). Across years, `sum_Y in_sample_sum_Y = n alpha_hat`.
- `point_in_time_sum_Y = sum_{t in Y cap S_c} u_tilde_t` with its own count `n_Y^pit`; null when `n_Y^pit = 0`. Across years they add to `m_c mean_{S_c}(u_tilde)`.
- `in_sample_noise_sd_Y = sd(u over S) sqrt(n_Y)`, `point_in_time_noise_sd_Y = sd(u_tilde over S_c) sqrt(n_Y^pit)`: the standard deviation of a year's sum for a stock with no alpha.
- `partial = n_Y < 200`; `point_in_time_partial = n_Y^pit < 200`.

No p-values per year. Reason: one year has too little data (the standard error of a year's residual return is about the residual volatility itself, typically 15-40%), and per-year tests invite picking the best year. Reading rule: "A year within two noise standard deviations of zero is ordinary for a stock with no alpha." Caption: "Sum of daily residual returns within the year (not compounded). In-sample column: betas from the whole period. Point-in-time column: betas from the previous {W} days."

### R5.5 Subsample mining and multiple testing

Caution copy (stability section footer): "The halves and calendar years are fixed in advance. If you search for the year or split date that looks best, the p-values stop meaning what they say: with 10 years to choose from, the best year has a nominal p below 0.05 about 40% of the time even when nothing changed." (`1 - 0.95^10 = 0.40`.)

| Output | Handling |
| --- | --- |
| In-sample alpha (M3) | single test, nominal 5% (unchanged) |
| Point-in-time mean residual | single test, nominal 5% |
| Verdict G7 "survives" | intersection-union of the two single tests; size <= 5% |
| Gap z | reported, approximate, drives nothing |
| Rolling 252-day band, `share_excluding_zero` | not tests, never corrected (M0.6) |
| Non-overlapping windows | family FR1, BH q = 0.05, `m = J` |
| Split-half difference | single prespecified test, nominal 5% |
| Calendar years | no tests |
| Residual diagnostics | nominal 5%, informational |

### R5.6 Deferred (not in this feature)

- The full out-of-sample stability score of `docs/PLAN.md` "Later": walk-forward refits with a scoring rule, rolling-origin evaluation, probability of backtest overfitting, deflated Sharpe ratio.
- Break tests with an unknown date (sup-Wald with Andrews critical values, Bai-Perron). Searching for the break date with the split-half test is exactly the mining R5.5 warns against.
- Comparison with SPY's residual (owner: later feature); forecasts of any kind (owner: never in this feature); cost models for the hedge; alpha persistence across horizons.

---

## R6. Residual diagnostics — `analytics/residual.py`

Run on the **demeaned** series (Engle's ARCH test is computed on squares and is not invariant to adding a constant):
- in-sample: `e_hat` (equals `u - alpha_hat`; Ljung-Box and Jarque-Bera values equal M3.5's exactly, reuse them);
- point-in-time: `u_tilde - mean_{S_c}(u_tilde)` over `S_c`.

| Test | Call (every argument explicit) | What it justifies | Wording if p < 0.05 | Wording otherwise |
| --- | --- | --- | --- | --- |
| Ljung-Box, lag 10 | `acorr_ljungbox(x, lags=[10], return_df=True)`: `lb_stat`, `lb_pvalue` | Serial correlation in residuals: why every t-statistic here is HAC; with positive autocorrelation the line trends more than daily volatility suggests | "Residual returns are correlated from day to day. The t-statistics allow for this." | "No clear day-to-day correlation in residual returns." |
| Jarque-Bera | `jarque_bera(x)`: statistic, p, skew, kurtosis | Fat tails or skew: normal-based intervals and the IR interval are approximate; drawdowns can exceed the noise reference | "Residual returns have more extreme days than a normal distribution. Intervals are approximate." | "No clear departure from a normal distribution." |
| Engle ARCH LM, 5 lags | `het_arch(x, nlags=5, ddof=0, store=False, result_object=True)`: `lm`, `lmpval` | Volatility clustering: one volatility number averages calm and turbulent periods; HAC standard errors remain valid; yearly noise bands are rough | "Residual volatility comes in clusters: calm and turbulent periods alternate. One volatility number averages them." | "No clear clustering of residual volatility." |

Nominal 5%, not corrected, never used by the verdict, tags or alerts (M3.5). For daily stock returns over several years, Jarque-Bera and ARCH almost always reject; the drawer says so: "With thousands of days these tests detect even small departures. A rejection makes intervals approximate, not wrong." Durbin-Watson stays in M3.5 only.

---

## R7. Schema additions — `backend/factordesk/report/schema.py`

Conventions of the existing module apply: frozen, strict, `extra="forbid"`, `allow_inf_nan=False`; every statistic subclasses `_Statistic` (`status`, `reason`, `sample`, `labels`, `caption`) and therefore carries **no float at all** when its status is not `ok`. Field names follow the module's `_annual` suffix (existing `alpha_annual`, `sigma_e_annual`). All returns are decimals; dates are ISO dates.

### R7.1 Label keys and texts (extend `LabelKey` and `LABEL_TEXT`)

| Key | Text |
| --- | --- |
| `L-INSAMPLE` | "In-sample: betas are fitted on this same period." |
| `L-PIT` | "Point-in-time: each day uses betas estimated only from earlier days." |
| `L-DESC-PIT` | "Descriptive and point-in-time, not predictive." |
| `L-HEDGE` | "Compounded daily: a paper long-short hedge, rebalanced daily, before trading costs, financing and borrowing fees." |

### R7.2 New type aliases

```python
ResidualBasis = Literal["in_sample", "point_in_time"]
GapVerdict = Literal[
    "no_reliable_alpha", "point_in_time_only", "concentrated_in_warmup",
    "reversed", "mostly_disappears", "survives_not_significant", "survives",
]
```

### R7.3 Summary statistics (R3, R4.3)

```python
class ResidualStats(_Statistic):
    """Summary of one residual series (R3). In-sample: span S. Point-in-time: span S_c."""
    basis: ResidualBasis
    beta_window: int | None            # None for in_sample; W for point_in_time
    hac_lags: int | None               # in_sample: L(n) of M3; point_in_time: L(m_c); None if not ok
    residual_return_annual: float | None          # decimal/year, A x mean
    residual_return_se_annual: float | None       # decimal/year (HAC)
    residual_return_ci_low_annual: float | None
    residual_return_ci_high_annual: float | None
    z: float | None
    p: float | None                    # two-sided, normal reference
    tag: Tag | None                    # "reliable" iff p < 0.05
    residual_vol_annual: float | None  # decimal/year, sqrt(A) x sd (ddof=1)
    information_ratio: float | None    # per sqrt(year)
    information_ratio_ci_low: float | None   # approximate (R3.3)
    information_ratio_ci_high: float | None
    cumulative_return: float | None    # decimal, compounded over the span (R2)
    compound_growth_annual: float | None     # decimal/year, Q^(A/m) - 1
    hit_rate: float | None             # share in [0, 1]
    max_drawdown: float | None         # decimal in [-1, 0]
    max_drawdown_peak: date | None     # None: the start of the span, or no drawdown
    max_drawdown_trough: date | None
    max_drawdown_recovery: date | None # None: not recovered, or no drawdown
    noise_drawdown_reference: float | None   # decimal in [-1, 0]
    skew: float | None
    excess_kurtosis: float | None
    wiped_out: bool                    # R2.6
```

Nullable rules when `status == "ok"`: `information_ratio*` null only if `residual_vol_annual == 0` (cannot happen with `ok`, R3.1); drawdown dates per R3.1; all other floats non-null. In-sample values of `residual_return_*`, `z`, `p`, `tag` are copied from `Regression` (equal bitwise, TR02).

### R7.4 Chart series (R2.3)

```python
class ResidualChart(_Statistic):
    """Cumulative (compounded) residual lines on the dates of S (R2.3)."""
    dates: list[date]                              # every row of S, ascending
    in_sample_full: list[float | None]             # CR over S; no None when ok
    comparison_start: date | None                  # date of row W (anchor); None if PIT not ok
    in_sample_compare: list[float | None]          # None before row W, 0.0 at row W
    point_in_time_compare: list[float | None]      # None before row W, 0.0 at row W
    point_in_time_status: Status
    point_in_time_reason: str | None
    n_excluded_in_span: int                        # excluded rows between first and last date
    n_uncovered: int                               # trading days after factor last_date (M2)
    uncovered_from: date | None                    # first uncovered date; None if n_uncovered == 0
```

Validators: every list has `len(dates)`; `point_in_time_reason is None` iff `point_in_time_status == "ok"`; when `point_in_time_status != "ok"`, both comparison lists are all `None` and `comparison_start is None`; when ok, both comparison lists are `None` exactly on rows `< W` and `0.0` at row `W`.

### R7.5 Gap (R4.7-R4.8)

```python
class ResidualGap(_Statistic):
    """Same-days comparison of in-sample and point-in-time residual returns on S_c (R4.7)."""
    beta_window: int
    in_sample_same_days_annual: float | None
    point_in_time_annual: float | None
    gap_annual: float | None
    gap_se_annual: float | None        # approximate (R4.7)
    gap_z: float | None
    gap_p: float | None
    comparison_share_of_alpha: float | None   # q; None if alpha_ann == 0
    survival_ratio: float | None              # s; None if a_c == 0
    verdict: GapVerdict | None                # None iff status != "ok"
    severity: Severity | None                 # "info" or "warning"
    message: str | None                       # exact copy of R4.8, filled
```

### R7.6 Stability (R5)

```python
class RollingResidualAlpha(_Statistic):
    """Trailing 252-row alpha from M4 (R5.1). Lists align with dates; None in warm-up."""
    window: int                        # 252
    hac_lags: int                      # L(252) = 4
    n_stamps: int
    dates: list[date]                  # every row of S
    alpha_annual: list[float | None]
    ci_low_annual: list[float | None]
    ci_high_annual: list[float | None]
    share_excluding_zero: float | None # descriptive (R5.1)

class AlphaWindow(_Frozen):
    start: date
    end: date
    n: int
    alpha_annual: float | None
    se_annual: float | None
    z: float | None
    p: float | None
    p_adj_bh: float | None
    tag: Tag | None

class NonOverlappingAlpha(_Statistic):
    """Family FR1 (R5.2): disjoint 252-row windows tiled from the end of S."""
    window: int                        # 252
    family_size: int                   # J
    n_reliable: int
    windows: list[AlphaWindow]         # most recent first

class SplitHalfAlpha(_Statistic):
    """One prespecified split at the middle of S (R5.3)."""
    first_start: date
    first_end: date
    second_start: date
    second_end: date
    n_first: int
    n_second: int
    hac_lags: int                      # L(n)
    alpha_first_annual: float | None
    alpha_first_ci_low_annual: float | None
    alpha_first_ci_high_annual: float | None
    alpha_second_annual: float | None
    alpha_second_ci_low_annual: float | None
    alpha_second_ci_high_annual: float | None
    difference_annual: float | None
    difference_se_annual: float | None
    difference_z: float | None
    difference_p: float | None

class ResidualYear(_Frozen):
    year: int
    n: int
    partial: bool                      # n < 200
    in_sample_sum: float               # within-year sum, decimal
    in_sample_noise_sd: float          # decimal
    n_point_in_time: int
    point_in_time_partial: bool        # n_point_in_time < 200
    point_in_time_sum: float | None    # None iff n_point_in_time == 0 or PIT not ok
    point_in_time_noise_sd: float | None

class ResidualYears(_Statistic):
    """Calendar-year residual sums (R5.4). Arithmetic within-year sums, no tests."""
    years: list[ResidualYear]          # ascending
```

`ResidualYears` with status not `ok` has an empty `years` list (the base validator forbids floats).

### R7.7 Diagnostics (R6)

```python
class ResidualDiagnostics(_Statistic):
    basis: ResidualBasis
    ljung_box_lags: int                # 10
    ljung_box_stat: float | None
    ljung_box_p: float | None
    jarque_bera_stat: float | None
    jarque_bera_p: float | None
    arch_lags: int                     # 5
    arch_lm_stat: float | None
    arch_lm_p: float | None
    findings: list[str]                # one plain-language sentence per test (R6)
```

### R7.8 Panel container and report field

```python
class ResidualAnalysis(_Frozen):
    """Residual (alpha) analysis panel (methodology-residual-analysis.md)."""
    question: str                      # R8.1 subtitle
    beta_window: int                   # W
    in_sample: ResidualStats           # basis "in_sample"
    point_in_time: ResidualStats       # basis "point_in_time"
    gap: ResidualGap
    chart: ResidualChart
    rolling_alpha: RollingResidualAlpha
    non_overlapping: NonOverlappingAlpha
    split_half: SplitHalfAlpha
    calendar_years: ResidualYears
    diagnostics: list[ResidualDiagnostics]   # [in_sample, point_in_time]
    caveats: list[str]                 # R8.5, in display order
    warnings: list[ReportWarning]      # e.g. residual_wipeout
```

- `FactorReport` gains `residual: ResidualAnalysis`.
- `STATISTIC_MODELS` gains `ResidualStats, ResidualChart, ResidualGap, RollingResidualAlpha, NonOverlappingAlpha, SplitHalfAlpha, ResidualYears, ResidualDiagnostics` (so T105 covers them).
- `SCHEMA_VERSION` becomes `"3"`.
- `SampleInfo` per statistic: in-sample objects and the chart: `S` with `window = None`; point-in-time objects and the gap: `S_c` (`n = m_c`, `start` = date of row `W+1`, `window = W`); rolling alpha: `S` with `window = 252`; non-overlapping: rows covered by the windows, `window = 252`; split-half and calendar years: `S`.

### R7.9 Captions (the `caption` field, exact)

| Model | Caption |
| --- | --- |
| `ResidualStats` in-sample | "Residual return = excess return minus factor exposures, alpha included. In-sample: betas fitted on {start} to {end}, so the residual return equals the regression alpha exactly." |
| `ResidualStats` point-in-time | "Residual return with each day's betas estimated from the previous {W} trading days only. Covers {start} to {end}; the first {W} days are warm-up." |
| `ResidualChart` | "Cumulative residual return, compounded daily. Both lines start at zero on {comparison_start} and cover the same days. In-sample uses betas fitted on the whole period; point-in-time uses betas from the previous {W} days." |
| `ResidualGap` | "Same days ({start} to {end}) for both series. Out-of-sample here refers to the betas; both series share the same days and stock-specific news." |
| `RollingResidualAlpha` | "Each point uses the previous 252 trading days, ending on that date; alpha and betas are both refitted in each window." |
| `NonOverlappingAlpha` | "Separate one-year windows counted back from {end}. Corrected for testing {J} windows (Benjamini-Hochberg)." |
| `SplitHalfAlpha` | "One split, fixed in advance at the middle of the period. Betas are refitted in each half." |
| `ResidualYears` | "Sum of daily residual returns within the year (not compounded). In-sample column: betas from the whole period. Point-in-time column: betas from the previous {W} days." |
| `ResidualDiagnostics` | "Informational checks at the 5% level, not corrected for multiple testing." |

---

## R8. Panel content — frontend, Ticker view, Attribution sub-tab (after Return and Risk contribution)

### R8.1 Title and question

Title: "Residual return". Subtitle (the `question` field): "What did this stock return beyond its factor exposures, and does it hold up without hindsight?"

### R8.2 Table

| Row | In-sample (static betas) | Point-in-time (trailing {W}-day betas) |
| --- | --- | --- |
| Period | {start} to {end}, {n} days | {start_c} to {end}, {m_c} days |
| Residual return (a year) | value with 95% interval | value with 95% interval |
| t-statistic | value; "reliable" or "noise" chip | same |
| Residual volatility (a year) | value | value |
| Residual Sharpe (information ratio) | value | value |
| Cumulative (compounded) | value | value |
| Max drawdown | value, dates on hover, noise reference on hover | same |
| Hit rate | value | value |

Skew, excess kurtosis, compound growth and the diagnostics go in the details drawer. Formats: returns and volatilities in percent with 1 decimal and a sign; t and IR with 2 decimals; hit rate in percent with 1 decimal. Red/green only with `+`/`-` glyphs (PLAN design rules).

### R8.3 Chart

- Two lines from `comparison_start`: in-sample (static) and point-in-time, same y-axis (cumulative, percent), zero line marked. Warm-up rows shaded with the R4.5 caption. Uncovered tail greyed with the R2.5 memo.
- End-of-line annotations: "In-sample {a_c} a year on these days (full-period alpha {alpha_ann}, t = {z_is})" and "Point-in-time {a_pit} a year, t = {z_pit}". The in-sample t belongs to the full-period alpha (M3), so the annotation names it as such.
- Gap statement below the chart: the R4.8 message, with a warning style for G4/G5 and neutral style otherwise.
- Toggle "Full period, in-sample" shows `in_sample_full` alone from the first date of `S`.
- Stability section below (collapsible): rolling alpha chart with band and the FR1 sentence; split-half row; calendar-year table; R5.5 caution as its footer.

### R8.4 Empty and insufficient-data states

| Situation | What the panel shows |
| --- | --- |
| Report refused (`n < 504`) | Panel not rendered; the report-level refusal applies (M0.7). |
| Regression failed | "Residual analysis is unavailable because the regression could not be computed." No table or chart. |
| Point-in-time `insufficient_data` (`W = 504`, `n < 756`) | Table shows the in-sample column; the point-in-time column shows "Needs at least {W + 252} trading days; this period has {n}. Choose a shorter beta window or a longer period." Chart shows `in_sample_full` only. No gap statement. |
| `residual_wipeout` warning | Banner above the chart with the R2.6 text. |
| `n_excluded > 0` | Footnote "Skips {n_excluded} excluded days (listed under sample details)." |

### R8.5 Caveat copy (exact, shown under the panel, in this order)

1. "You see the stock's return after removing what its five factor exposures explain. It includes alpha."
2. "In-sample: betas are fitted on this same period, so the in-sample line always drifts by the regression alpha. A line ending above zero is not evidence of skill; check the t-statistic."
3. "Point-in-time: each day uses betas from the previous {W} trading days only. It removes hindsight in the betas, but it uses the same days, so it cannot rule out luck."
4. "The lines compound a paper long-short hedge, rebalanced daily, before trading costs, financing and borrowing fees."
5. "Past residual return does not predict future residual return."

Plus the standard footnotes from the `labels` fields (L-DESC or L-DESC-PIT, L-INSAMPLE, L-PIT, L-HEDGE, L-VINTAGE).

---

## R9. Decisions, deviations and proposals

### R9.1 Decisions (each with its reason)

- **RD1 Residual keeps alpha.** `u_t = y_t - beta_hat' f_t`, not `e_hat_t`. The feature exists to show alpha's path; `e_hat` has mean zero by construction and would show nothing.
- **RD2 In-sample inference is the M3 alpha test.** A location test on `u` ignores that `beta_hat` was estimated on the same rows (R3.2). One hypothesis, one number across panels.
- **RD3 Table arithmetic, chart compounded.** The arithmetic mean is the alpha estimate and is what the t-statistic tests; the geometric rate mixes alpha with residual variance and penalises volatile stocks for risk, not return. The chart compounds because a cumulative line means the growth of the daily-rebalanced paper hedge (M0.4 label). The drag is stated in the caption; the two are never summed.
- **RD4 `W = beta_window`, no new parameter.** Consistency with M4/M6.3 (exact identity `point_in_time.residual_return_annual = U`) and the 3-parameter discipline. 252 balances beta noise (+1% volatility) against warm-up and adaptation lag (R4.2).
- **RD5 Point-in-time minimum `m_c >= 252`.** One year of honest residuals is the least that gives an annual number; it is always met for `W <= 252` under the 504-row report minimum.
- **RD6 Comparison on the same days.** Both lines start at zero on row `W`, and the gap uses `S_c` for both. Comparing lines with different starts confuses accumulation with performance. The in-sample table column stays on `S` so it matches the regression KPI; its header states the dates.
- **RD7 Point-in-time ≠ holdout.** We do not call the point-in-time series a validation of alpha. It shares the shocks of the in-sample series (measured: 3.2% of zero-alpha stocks "survive"). User copy says it rules out hindsight in betas, not luck.
- **RD8 Verdict thresholds fixed** at `p = 0.05`, `s = 0.5`, `q = 0.5` (R4.8), not tunable. Tunable thresholds on a verdict invite tuning until it says what one hoped.
- **RD9 Rolling alpha reuses the M4 252-row intercept,** not a trailing mean of `u_tilde`. It is the standard rolling alpha, already computed, with a HAC band; window fixed at 252 so it always means one year.
- **RD10 "How many windows are significant" uses disjoint windows with BH (FR1).** Overlapping stamps are not independent tests; their share is descriptive only.
- **RD11 Calendar years: within-year sums, no tests.** Same convention as M6.2 (D7); the in-sample column reconciles exactly with M6.2's alpha + residual columns.
- **RD12 Diagnostics on demeaned series, ARCH added.** `het_arch` uses squares, which a constant shifts. Ljung-Box and Jarque-Bera in-sample equal M3.5 and are reused.
- **RD13 Wipe-out rule** (R2.6) rather than a failed status: the arithmetic statistics remain valid; only the compounded path stops.
- **RD14 No forecast, no benchmark** (owner decisions). The "survives" message explicitly says it is not a prediction.

### R9.2 Proposed changes to existing documents and code (not made here)

- **P1 M0.9 labels.** L-DESC says "in-sample", which is wrong for point-in-time outputs. Add `L-DESC-PIT`, `L-INSAMPLE`, `L-PIT`, `L-HEDGE` (R7.1) to M0.9 and to `LabelKey`/`LABEL_TEXT`.
- **P2 M0.6.** Add family FR1 (non-overlapping 252-row window alphas, `m = J`) to the family table; add "point-in-time mean residual (R4) and split-half alpha difference (R5.3)" to the list of single tests; note the intersection-union verdict.
- **P3 M0.7.** Add the R3.6 rows to the minimum-sample table.
- **P4 M0.4.** Add the geometric convention `Q^(A/m) - 1` ("compound growth, a year") and state that it is reported beside, never combined with, arithmetic annual values.
- **P5 M3.5.** Add Engle's ARCH LM test (5 lags, demeaned residuals, `result_object=True` passed explicitly), and pass `return_df=True` explicitly to Ljung-Box so a library default change cannot alter the output type (as D2 does for HAC).
- **P6 M6.3.** Add to the tilt/timing label: "Unattributed equals the point-in-time residual return of the Residual panel."
- **P7 M14 / schema.** The existing `RollingWindow` model exposes betas but not the rolling alpha and its standard error that `analytics/rolling.py` already computes; either add `alpha_annual` and `alpha_se_annual` there (then `RollingResidualAlpha` can reference it) or keep `RollingResidualAlpha` as specified. `SCHEMA_VERSION` to `"3"`.
- **P8 M15.** Add a row "Residual analysis | none (uses `beta_window`) | - | rolling 252, `m_c >= 252`, `s`/`q` thresholds 0.5, LB 10, ARCH 5".
- **P9 M16.** Add a pointer entry ("D21 Residual analysis: see `docs/methodology-residual-analysis.md`, RD1-RD14") so the Definition of Done rule "any new statistic must be added here" is satisfied.
- **P10 `docs/test-oracle.md` T102/T103.** Add to the list of outputs checked for look-ahead: `u_tilde`, `point_in_time_compare`, rolling 252-day alpha series (TR15 specifies them here).
- **P11 `CODING_STANDARDS.md` §1 vs `schema.py`.** The standard says suffix `_ann`; the schema uses `_annual`. This specification follows the schema for API fields. Proposal: state that `_ann` applies to backend series names and `_annual` to API fields, or unify.
- **P12 `docs/PLAN.md`.** The "Later: out-of-sample stability score" item should reference R5.6 for the boundary between this feature and that one.

### R9.3 Open questions for the owner

1. **Default chart view.** Specified: the two comparison lines (same start) by default, with a toggle to the full-period in-sample line that matches the inspiration. Do you want the full-period line as the default instead?
2. **Warm-up before a user-chosen start.** When you pick a start date later than the ticker's first available date, the point-in-time betas for the first `W` days could use data before your start (still point-in-time). This recovers the warm-up year but means the panel uses data outside the selected period. Allow it, and label it?
3. **Placement.** Specified as a section of the Attribution sub-tab. Do you want the verdict (G4/G5 warning) also in the KPI strip?
4. **Wording "survives".** It means "not an artefact of hindsight betas", not "validated". Is that wording acceptable, or should G7 read "holds up with point-in-time betas" without the word "survives" in the code name shown to users?

## Owner decisions (2026-11-18)

Resolving the four open questions from the specification:

1. **Opening view:** the residual chart opens on both lines (in-sample and point-in-time) from the
   same starting point. A toggle shows the full-period in-sample line alone.
2. **Start date:** when the user picks a later start date, the first year of point-in-time betas
   may use data from before that date. This uses past data only, so it is not look-ahead. The
   footnote must say that earlier data was used.
3. **Warning placement:** the "in-sample alpha mostly disappears out-of-sample" warning appears only
   in the residual panel, not in the KPI strip.
4. **Wording:** use "holds up out-of-sample" instead of "survives" in every user-facing string.

## Owner decisions (2026-11-19)

5. **Wording of rule G2 (R4.8):** "check the Exposures tab" becomes "check the Exposures section",
   because the dashboard is one scrolling page with no tabs. Only the last words of the message
   change; the rule, its threshold and its code are unchanged. The test oracle (TR line for G2),
   the verdict message and its test carry the same wording.
