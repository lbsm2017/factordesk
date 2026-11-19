# factordesk test oracle: residual (alpha) analysis

Status: written 2026-11-18, for the feature specified in `docs/methodology-residual-analysis.md` (sections R0-R9, decisions RD1-RD14). Companion to `docs/test-oracle.md` (T01-T115), whose conventions in section 0 apply here unless stated.
Every test is automatable with `pytest`. Each states its **target module**, the **setup**, the **assertion**, and the **tolerance with its derivation**. A test that cannot be implemented as written is a spec bug: raise it, do not loosen it silently.

Target modules (proposed in R1-R7):
- `analytics/residual.py`: residual series (R1, R4), cumulative series (R2), summary statistics (R3), gap and verdict (R4.7-R4.8), diagnostics (R6).
- `analytics/residual_stability.py`: rolling alpha, non-overlapping windows, split-half alpha, calendar-year table (R5).
- `report/schema.py`: models of R7.
- Reused, not modified: `analytics/regression.py` (M3), `analytics/rolling.py` (`rolling_betas`, `ex_ante_betas`), `analytics/attribution.py` (M6.2, M6.3).

---

## 0. Conventions

### 0.1 Markers, seeds, tolerances

- Markers as in `docs/test-oracle.md` 0.1: none (blocking), `slow` (Monte Carlo, nightly and before release), `live` (network, non-blocking).
- Seeds: test `TRk` uses `rng = numpy.random.default_rng(20261118 + 500 + k)`. Monte Carlo replication `r` of test `TRk` uses `numpy.random.default_rng([20261118 + 500 + k, r])` (a `SeedSequence` entropy list), `r = 0 .. R-1`. These never collide with the `T` seeds (`20261118 + k`, `k <= 115`).
- Tolerances follow `docs/test-oracle.md` 0.2-0.3: identities `1e-10` absolute on values of order 0.01-1 (annualised values, sums), `1e-12` relative where stated; two computations of the same quantity `1e-10` relative; recovery of a true parameter `4 SE`; Monte Carlo rates `3.5` binomial SE; labels, counts, dates, statuses exact.
- Calibration: where a bound uses a Monte Carlo standard deviation rather than a closed form, the calibration was run with 200-1000 independent seeds **outside** the test seed range, and the bound is at least 4 such standard deviations from the measured mean (stated per test). The nightly seed sweep of `docs/test-oracle.md` 0.2 applies to every fixed-seed test here.

### 0.2 Data-generating processes

All DGPs reuse **DGP-A** of `docs/test-oracle.md` 0.4 (dates `pd.bdate_range("2010-01-04", periods=n)`, factor means, volatilities and correlations, `RF_t`, betas `(1.10, 0.30, -0.40, 0.25, 0.15)`, prices built as `100 cumprod(1 + r)`, no dividends or splits) and override only what is listed. Default `n = 2520`, `W = beta_window = 252`. Calendar facts for `n = 2520`: last date 2019-08-30; row 253 is 2010-12-22; row 505 is 2011-12-09; rows per year 2010: 260, 2011: 260, 2012-2016: 261, 2017: 260, 2018: 261, 2019: 174.

| DGP | Overrides | Purpose |
| --- | --- | --- |
| **DGP-A** | none (`alpha = 0.0002`/day, `sigma_e = 0.012`) | identities |
| **DGP-R0** | `alpha = 0`, `sigma_e = 0.012` | zero true alpha |
| **DGP-R+** | `alpha = 0.0012`/day (30.24% a year), `sigma_e = 0.008` | strong, stable alpha |
| **DGP-RB** | `alpha = 0`, `sigma_e = 0.008`, `beta_mkt = 0.5` on rows 1-1260 and `1.5` on rows 1261-2520 | structural break in beta |
| **DGP-RT** | `alpha = 0`, `sigma_e = 0.005`; `mkt_rf` drawn as in DGP-A then shifted so its mean is `-0.0015` on rows 1-1260 and `+0.0015` on rows 1261-2520; `beta_mkt = 0.0` on rows 1-1260 and `2.0` after; other betas as DGP-A | alpha that is really a moving exposure (hindsight alpha) |

Useful theoretical values (DGP-A factor moments; `K = 5`):
- `mu' Sigma_f^-1 mu = 0.00253`, so `1 + fbar' Sigma_pop^-1 fbar` is about `1.003` plus sampling noise (about `K/n = 0.002`).
- DGP-R0: `sigma_e_ann = 0.1905`; `se(alpha_ann) ≈ 252 x 0.012 / sqrt(2520) = 0.0602`.
- Point-in-time variance inflation `≈ 1 + K/W = 1.0198` for `W = 252` (R4.2).
- HAC lags: `L(252) = 4`, `L(756) = 6`, `L(1008) = 6`, `L(1260) = 7`, `L(2016) = 7`, `L(2268) = 8` (the formula gives 8.004: compute it exactly as M0.5 states, no rounding before `floor`), `L(2394) = 8`, `L(2520) = 8`.

Fixture builders for DGP-R0, DGP-R+, DGP-RB and DGP-RT live in `backend/factordesk/tests/fixtures/` beside the existing DGP builders and return the same typed inputs (`PriceFrame`, `FactorFrame`).

---

## 1. In-sample residual (`analytics/residual.py`, R1, R3.2)

- **TR01 Residual identities.** DGP-A. Compute `u = y - F beta_hat` from the module and `alpha_hat`, `e_hat` from `analytics/regression.py`. Assert:
  (a) `|u_t - (alpha_hat + e_hat_t)| <= 1e-14` for every row (two float paths to the same number; values of order 0.01, float error about `1e-17`);
  (b) `|252 mean(u) - alpha_ann| <= 1e-10` (R1.2 item 1);
  (c) `|sum(u) - n alpha_hat| <= 1e-10` (item 2; the sum is of order 0.5);
  (d) for each factor, `|corr(u, f_i)| <= 1e-10` (item 3; measured about `1e-16`);
  (e) `sqrt(252) sd(u, ddof=1) == Regression.sigma_e_annual` within `1e-12` relative (item 4).
- **TR02 In-sample statistics are the regression's.** DGP-A. In `ResidualStats` with `basis = "in_sample"`: `residual_return_annual`, `residual_return_se_annual`, `residual_return_ci_low_annual`, `residual_return_ci_high_annual`, `z`, `p`, `tag` equal `Regression.alpha_annual`, `alpha_se_annual`, `alpha_ci_low_annual`, `alpha_ci_high_annual`, `alpha_z`, `alpha_p`, `alpha_tag` **bitwise** (they are copies, RD2); `hac_lags == 8`; `residual_vol_annual == sigma_e_annual` within `1e-12` relative; `information_ratio == alpha_annual / sigma_e_annual` within `1e-12` relative.
- **TR03 Variance factor of the intercept.** DGP-A, design `X = [1, F]`. Assert `[(X'X)^-1]_{11} == (1 + fbar' Sigma_pop^-1 fbar) / n` within `1e-10` relative, with `Sigma_pop = np.cov(F.T, ddof=0)` (partitioned-inverse identity behind R3.2 and R3.3). Also assert `fbar' Sigma_pop^-1 fbar > 0`.
- **TR04 Information ratio and t-statistic.** DGP-A. With the nonrobust OLS fit `sm.OLS(y, X).fit()` (`s^2 = SSR/(n-6)`): `z_OLS(alpha_hat) == (IR / sqrt(252)) sqrt(n) sqrt((n - 6)/(n - 1)) / sqrt(1 + fbar' Sigma_pop^-1 fbar)` within `1e-10` relative, with `IR` the module's in-sample `information_ratio` (R3.3; measured agreement `4e-12`). This test pins the documented relation, not the reported HAC z.

## 2. Cumulative series and summary statistics (`analytics/residual.py`, R2, R3)

- **TR05 Hand examples (pure function on a residual array and dates `d1, d2, ...`).** Tolerance `1e-12` absolute.
  - (a) `x = (0.10, -0.10, 0.0, 0.2222222222222222)`: `Q = (1.1, 0.99, 0.99, 1.21)`, `CR = (0.1, -0.01, -0.01, 0.21)`, `cumulative_return = 0.21`, `hit_rate = 0.5` (the zero is not a hit), `max_drawdown = -0.1`, peak `d1`, trough `d2` (first of the tied rows 2 and 3), recovery `d4`, `compound_growth_annual = 1.21^63 - 1` (`m = 4`, `A/m = 63`; `1e-10` relative).
  - (b) `x = (-0.05, 0.02, 0.04)`: `max_drawdown = -0.05`, peak `null` (the starting value `Q_0 = 1`), trough `d1`, recovery `d3` (`Q_3 = 1.0078 >= 1`).
  - (c) `x = (0.01, 0.02)`: `max_drawdown = 0`, peak, trough and recovery all `null`.
  - (d) `x = (0.1, -0.2)`: `max_drawdown = -0.2`, peak `d1`, trough `d2`, recovery `null`.
  - (e) `x = (0.1, 0.0, -0.1)`: peak `d2` (latest row attaining the running maximum before the trough), `max_drawdown = -0.1`.
- **TR06 Product relation, anchors and rebasing.** DGP-A, `W = 252`.
  - `1 + in_sample_full_t == cumprod(1 + u)_t` within `1e-12` relative, every row; `log1p(in_sample_full_n) == sum(log1p(u))` within `1e-10`.
  - `in_sample_compare` and `point_in_time_compare` are `None` on rows 1-251, exactly `0.0` on row 252 (`comparison_start == 2010-12-21`, the date of row 252), and non-null on rows 253-2520.
  - Rebasing: `1 + in_sample_compare_t == (1 + in_sample_full_t) / (1 + in_sample_full_252)` within `1e-12` relative for `t > 252`.
  - `1 + point_in_time_compare_t == prod_{s=253..t}(1 + u_tilde_s)` within `1e-12` relative.
  - `ResidualStats.cumulative_return` equals the last value of `in_sample_full` (in-sample) and of `point_in_time_compare` (point-in-time), bitwise.
- **TR07 Compounding drag (deterministic inequality).** DGP-A, both series. With `x` the series and `m` its length:
  `|252 mean(log1p(x)) - 252 mean(x) + 126 mean(x^2)| <= 252 mean(|x|^3 / (3 (1 - |x|)^3)) + 1e-12` (R2.2; Taylor remainder bound, valid for `|x| < 1`; measured left side up to `2.5e-5`, right side about `1.5e-4`).
  Also `126 mean(x^2) == residual_vol_annual^2 (m - 1)/(2m) + 126 mean(x)^2` within `1e-12` relative, and `1 + compound_growth_annual == exp(252 mean(log1p(x)))` within `1e-12` relative.
- **TR08 Annualisation of the ratio and its interval.** DGP-A, both series. `information_ratio == sqrt(252) mean(x) / sd(x, ddof=1)` and `== residual_return_annual / residual_vol_annual`, each within `1e-12` relative; `information_ratio_ci_low == residual_return_ci_low_annual / residual_vol_annual` (same for high), `1e-12` relative. `noise_drawdown_reference` hand value: `residual_vol_annual = 0.25`, `m = 2520` gives `-(1 - exp(-sqrt(pi/2) x 0.25 x sqrt(10))) = -0.6287322670` (`1e-9`).
- **TR09 Skew and kurtosis.** Pure input `x = (1, 2, 3, 10)`: central moments with divisor 4 are `m2 = 12.5`, `m3 = 45`, `m4 = 348.5`; `skew = 45 / 12.5^1.5 = 1.0182337649`, `excess_kurtosis = 348.5 / 156.25 - 3 = -0.7696` (`1e-9`). On DGP-A both equal `jarque_bera(x)[2]` and `jarque_bera(x)[3] - 3` within `1e-12`.
- **TR10 Wipe-out rule.** Pure input `x = (0.1, -1.2, 0.05)`: `CR = (0.1, -1.0, -1.0)`, `wiped_out = true`, `compound_growth_annual = -1`, `max_drawdown = -1`, warning `residual_wipeout` naming `d2`; `residual_return_annual == 252 mean(x)` (arithmetic statistics unaffected). `x = (-1.0, 0.1)` also wipes out (`1 + x <= 0` includes zero). `x = (-0.999, 0.1)` does not.
- **TR11 Excluded rows are skipped, not filled.** DGP-A with three ticker dates removed (rows 600, 1400 and 2100 of the price index), so the following rows are excluded with reason `multi_day_return` (M2). Assert: `chart.dates` equals the dates of `S` (the six affected dates are absent); no value of `u` or `u_tilde` is exactly `0.0`; `in_sample_full` equals `cumprod(1 + u) - 1` over the rows of `S` (`1e-12` relative, no extra factor for the gaps); `n_excluded_in_span == 3`; the chart caption contains "Skips 3 excluded days".

## 3. Point-in-time residual (`analytics/residual.py`, R4)

- **TR12 Exact lag and window (no look-ahead in betas).** DGP-A, for each `W in {126, 252, 504}`:
  - `u_tilde_t` is `None` for rows `1 .. W` (never `0.0`) and non-null for rows `W+1 .. n`; `m_c = n - W`.
  - For 5 rows `t` drawn with the test rng from `W+1 .. n`: `beta_tilde_t` equals the OLS slope vector of `y` on `[1, F]` over exactly the `W` rows `t-W .. t-1` (`np.linalg.lstsq`, `1e-10` relative), and `|u_tilde_t - (y_t - beta_tilde_t' f_t)| <= 1e-12`.
  - Off-by-one guard: recomputing with the window `t-W+1 .. t` (which contains day `t`) gives `max_t |u_tilde_t - u_tilde^{wrong}_t| > 1e-6` (expected about `3e-5`), so an implementation that includes day `t` fails.
  - `beta_tilde` is obtained from `rolling.ex_ante_betas` (assert equality, bitwise, with `ex_ante_betas(rolling_betas(sample, W))`).
- **TR13 Equals the tilt/timing unattributed row.** DGP-A, `W in {126, 252, 504}`: `point_in_time.residual_return_annual == U` of M6.3 within `1e-10` (R4.4), and the point-in-time `SampleInfo.start` equals the first date of `S_dyn`.
- **TR14 HAC reference calls and gap construction.** DGP-A, `W = 252`.
  - Point-in-time `residual_return_se_annual / 252`, `z`, `p` equal `sm.OLS(x, np.ones(m)).fit(cov_type="HAC", cov_kwds={"maxlags": 8, "use_correction": False}, use_t=False)` on `x = u_tilde` over `S_c` (`m = 2268`, `L(2268) = 8`) within `1e-10` relative; `hac_lags == 8`.
  - `gap_t == u_t - u_tilde_t` within `1e-15` on `S_c`; `gap_annual == in_sample_same_days_annual - point_in_time_annual` within `1e-12`; `gap_se_annual`, `gap_z`, `gap_p` equal the same reference call on `gap_t` within `1e-10` relative.
  - `in_sample_same_days_annual == 252 mean_{S_c}(u)` and differs from `alpha_annual` (it is not forced to equal it; assert `!=`).
- **TR15 Look-ahead: perturbation, row change and truncation.** DGP-A, `n = 2520`, `t* = 1800`, `W = 252`.
  - (a) Perturbation after `t*` exactly as T102 (new returns, factors, RF, a dividend and a 2:1 split after `t*`; rows `<= t*` identical). Assert unchanged within `1e-12` absolute: `beta_tilde_t` for `t <= t* + 1` (the betas for day `t*+1` use rows `<= t*` only), `u_tilde_t` and `point_in_time_compare_t` for `t <= t*`, rolling 252-day `alpha_annual`, `ci_low_annual`, `ci_high_annual` for `t <= t*`. Teeth: `u_tilde_{t*+1}` changes (it uses day `t*+1`'s return), and the in-sample `u_1` changes by more than `1e-8` (the full-sample betas move), proving the test can see a change.
  - (b) Row change: multiply `y_t` and `f_t` on row `t = 1500` by 10. `beta_tilde_1500` is unchanged bitwise; `u_tilde_s` for `s < 1500` is unchanged bitwise; `u_tilde_1500 == y'_1500 - beta_tilde_1500' f'_1500` (`1e-12`).
  - (c) Truncation at `t*` (as T103): every point-in-time series stamped `<= t*` equals the full run within `1e-12`; `comparison_start` is identical; all full-sample residual outputs of the truncated run (in-sample statistics, gap, verdict, split-half, non-overlapping windows) have `SampleInfo.end == date(t*)`.
- **TR16 Warm-up and short history.** DGP-A truncated to `n` rows.
  - `n = 504`, `W = 252`: point-in-time `ok`, `m_c = 252`, `hac_lags == L(252) == 4`, `SampleInfo.window == 252`.
  - `n = 504`, `W = 126`: `m_c = 378`.
  - `n = 755`, `W = 504`: `point_in_time.status == "insufficient_data"`, `reason == "Point-in-time residual needs at least 756 trading days; this period has 755."`, every float field `None`, `hac_lags is None`; `chart.point_in_time_status == "insufficient_data"`, both comparison lists all `None`, `comparison_start is None`, `in_sample_full` complete; `gap.status == "insufficient_data"`, `verdict is None`; every `ResidualYear.point_in_time_sum is None`; the point-in-time `ResidualDiagnostics` is `insufficient_data`; every in-sample object is `ok`.
  - `n = 756`, `W = 504`: point-in-time `ok` with `m_c = 252`.
- **TR17 Verdict decision table (pure function).** Inputs `(alpha_ann, p_is, a_c, a_pit, p_pit)`; dyadic values so ratios are exact. Exact expected codes:

| Case | Inputs | Verdict | Why |
| --- | --- | --- | --- |
| 1 | `(0.125, 0.20, 0.125, 0.0625, 0.30)` | `no_reliable_alpha` | G1 |
| 2 | `(0.125, 0.20, 0.125, 0.0625, 0.01)` | `point_in_time_only` | G2 |
| 3 | `(0.125, 0.05, 0.125, 0.125, 0.01)` | `point_in_time_only` | `p_is = 0.05` is not `< 0.05` |
| 4 | `(0.125, 0.01, 0.0625 - 2^-20, 0.0625, 0.01)` | `concentrated_in_warmup` | `q < 0.5` |
| 5 | `(0.125, 0.01, -0.03125, 0.0625, 0.01)` | `concentrated_in_warmup` | opposite sign |
| 6 | `(0.125, 0.01, 0.0, 0.0625, 0.01)` | `concentrated_in_warmup` | `alpha_ann x a_c = 0`; `survival_ratio is None` |
| 7 | `(0.125, 0.01, 0.0625, -0.0078125, 0.60)` | `reversed` | `q = 0.5` passes G3; `s < 0` |
| 8 | `(0.125, 0.01, 0.125, 0.0625 - 2^-20, 0.30)` | `mostly_disappears` | `s` just below 0.5 |
| 9 | `(0.125, 0.01, 0.125, 0.0625, 0.30)` | `survives_not_significant` | `s = 0.5` exactly |
| 10 | `(0.125, 0.01, 0.125, 0.109375, 0.01)` | `survives` | G7 |
| 11 | `(-0.125, 0.01, -0.125, -0.109375, 0.01)` | `survives` | negative alpha, same sign |
| 12 | `(0.125, 0.01, 0.125, 0.0625, 0.05)` | `survives_not_significant` | `p_pit = 0.05` is not `< 0.05` |

  Severities: cases 7 and 8 `warning`, all others `info`.
- **TR18 Verdict copy.** Exact strings (R4.8 table, percentages with sign and 1 decimal, ratios to the nearest 5 points with halves away from zero):
  - G5 with `a_c = 0.04`, `a_pit = 0.018` (`s = 0.45`): "In-sample alpha mostly disappears out-of-sample: point-in-time betas keep 45% of it (+1.8% a year against +4.0% on the same days)."
  - G2 with `a_pit = -0.052`: "The point-in-time residual return is reliably negative (-5.2% a year), but the full-period alpha is not. This usually means the betas moved; check the Exposures section."
  - G7 with `s = 2.5`: the ratio renders as "more than 200%".
  - G3 with `W = 252` on DGP-A dates: the message names "the first 252 trading days (2010-01-04 to 2010-12-21)".

## 4. Behaviour on DGPs with known truth (`analytics/residual.py`, R4.2, R4.8)

- **TR19 Strong stable alpha survives.** DGP-R+ (`alpha = 0.0012`, `sigma_e = 0.008`, constant betas). Assert:
  (a) `|alpha_annual - 0.3024| <= 4 alpha_se_annual` (in-sample; expected z about 7.5);
  (b) `|point_in_time.residual_return_annual - 0.3024| <= 4 point_in_time.residual_return_se_annual`;
  (c) `verdict == "survives"`. Failure needs the point-in-time `|z| < 1.96`; its mean is 6.9 with sd about 1 (200 calibration seeds, minimum 4.4), so `P ≈ P(Z < -4.9) < 1e-6`;
  (d) `survival_ratio` in `[0.85, 1.15]`. Calibration: mean 1.000, sd 0.020 over 200 seeds; the bound is 7 sd. Theory: the gap's annual sd is `sigma_e_ann sqrt(K/W) / sqrt(m_c/252) ≈ 0.006`, divided by `a_c ≈ 0.30`;
  (e) volatility ratio `point_in_time.residual_vol_annual / in_sample.residual_vol_annual` in `[0.989, 1.033]`. Theory `sqrt((1 + 5/252)(2519/2514)) = 1.0109`; calibration mean 1.0109, sd 0.0054; bound = theory `+/- 4` sd;
  (f) `|point_in_time.residual_vol_annual - 0.12825| <= 0.0076` (theory `0.008 sqrt(1 + 5/252) sqrt(252) = 0.12825`; SE of a normal sd estimate `0.12825 / sqrt(2 x 2267) = 0.0019`; 4 SE);
  (g) `|gap_annual| <= 0.03` (calibration sd 0.0059; 5 sd).
- **TR20 Zero true alpha: honest residual is noise, in-sample line still drifts.** DGP-R0.
  - Fixed seed (blocking): `|point_in_time.z| <= 4` (correct implementation fails with `P = 6.3e-5`); the in-sample arithmetic drift is exactly the noisy alpha: `|sum(u) - n alpha_hat| <= 1e-10` and `in_sample_full` last value `!= 0`.
  - Monte Carlo (`slow`), `R = 1000`. Rates with 3.5 binomial SE (`sqrt(p(1-p)/1000)`), calibration values in brackets:
    - point-in-time rejection rate `p_pit < 0.05`: in `[0.026, 0.074]` [0.046];
    - in-sample (M3 alpha) rejection rate: in `[0.026, 0.074]` [0.050];
    - share with `|alpha_annual| >= 0.03`: in `[0.564, 0.672]` (theory `P(|Z| >= 0.03 / 0.0602) = 0.618`) [0.621]. This is the "line drifts with no true alpha" rate quoted in R1.4;
    - share with verdict `survives` (both tests reject, same sign): in `[0.013, 0.074]` [0.032]. The upper bound is the intersection-union size; the lower bound documents RD7 (the point-in-time check does not remove luck, because both series share the same shocks);
    - number of replications with verdict `reversed` or `mostly_disappears`: `<= 5` [0]. Under constant betas these verdicts require a gap of more than 3 noise sd given a reliable in-sample alpha (R4.8);
    - empirical sd of `gap_annual` across replications: in `[0.0070, 0.0105]` (theory `0.1905 x sqrt(5/252) / sqrt(9) = 0.0089`; the sd of an sd estimate over 1000 draws is 2.2%, 3.5 SE = 8%, plus 10% for the approximations in the theory) [0.0085].
- **TR21 Structural break: static residual leaks exposure, point-in-time adapts.** DGP-RB (`beta_mkt` 0.5 then 1.5 at row 1261, `alpha = 0`, `sigma_e = 0.008`, `W = 252`). Spans: pre = rows 253-1260, post = rows 1513-2520 (1008 rows each; the point-in-time windows lie entirely within one regime). On each span, regress the residual on `[1, F]` with HAC `L(1008) = 6` and read the `mkt_rf` slope `c` and its se.
  - (a) Full-sample `beta_hat_mkt` in `[0.90, 1.10]` (calibration mean 1.000, sd 0.020; 5 sd).
  - (b) In-sample residual: post `c` in `[0.35, 0.65]` and `c / se >= 8`; pre `c` in `[-0.65, -0.35]` and `c / se <= -8`. Theory `+/-(1.5 - 1.0)`, `+/-0.5`; calibration mean `+/-0.502`, sd 0.025 (bound 6 sd); `c / se` mean about 19, minimum 13 over 200 seeds.
  - (c) Point-in-time residual: `|c| <= 4 se` on both spans (calibration: `|c / se|` maximum 0.98 over 200 seeds).
  - (d) Post span: `sd(u_tilde) / sd(u) <= 0.93` (theory `sqrt(0.008^2 (1 + 5/252) / (0.008^2 + 0.5^2 x 0.010^2)) = 0.856`; calibration mean 0.855, sd 0.012; 6 sd).
  This is the "in-sample residual is biased, point-in-time adapts" test: the static residual carries a market exposure of about `-0.5` before and `+0.5` after the break.
- **TR22 Hindsight alpha disappears.** DGP-RT (the beta rises from 0 to 2 just as the market's drift turns from negative to positive; true alpha 0). Theory: `beta_hat_mkt ≈ 1.0`, `alpha_hat ≈ 0.0015`/day (37.8% a year, all of it moving exposure); point-in-time residual mean is about zero except during the 252-row adaptation after the break. Assert:
  - (a) in-sample `tag == "reliable"` (calibration z mean 6.75, minimum 3.87 over 200 seeds; failure needs `z < 1.96`, `P < 1e-6`);
  - (b) `verdict in {"mostly_disappears", "reversed"}` and `survival_ratio < 0.5` (calibration: mean 0.111, sd 0.091, maximum 0.33; 0.5 is 4.3 sd above the mean). Calibration verdicts: 183 `mostly_disappears`, 17 `reversed`, out of 200;
  - (c) on rows 253-1260 and 1513-2520 together (excluding the adaptation rows 1261-1512), the HAC location z of `u_tilde` satisfies `|z| <= 4`.

## 5. Stability (`analytics/residual_stability.py`, R5)

- **TR23 Rolling 252-day alpha.** DGP-A, any `beta_window`. `alpha_annual_t == 252 x RollingBetas(252).alpha_t` and the band `252 x (alpha_t -/+ 1.959964 x alpha_se_t)`, within `1e-12` relative; `None` on rows 1-251; first non-null row 252; `n_stamps == 2269`; `hac_lags == 4`; every stamp's `window_start` is exactly 251 rows earlier; `share_excluding_zero == (number of stamps with ci_low > 0 or ci_high < 0) / 2269` exactly. Unchanged when `beta_window` changes to 126 or 504 (fixed window, RD9).
- **TR24 Non-overlapping tiling and BH.**
  - `n = 2520`: `J = 10`; windows (most recent first) rows 2269-2520, 2017-2268, ..., 1-252; disjoint; each exactly 252 rows.
  - `n = 2600`: `J = 10`; the first 80 rows unused; the most recent window ends on row 2600.
  - Each window's `alpha_annual`, `se_annual`, `z`, `p` equal the M4 stamp at its end row (bitwise) and the reference HAC call on its 252 rows (`maxlags = 4`; `1e-10` relative).
  - `p_adj_bh` equals `multipletests(p, alpha=0.05, method="fdr_bh")[1]`; `n_reliable` equals the number rejected.
  - Pure BH example, `J = 4`, `p = (0.001, 0.02, 0.04, 0.5)`: thresholds `(0.0125, 0.025, 0.0375, 0.05)`, so `n_reliable = 2` (0.04 > 0.0375). Exact.
- **TR25 Recent alpha is found.** DGP-A betas, `sigma_e = 0.008`, `alpha = 0` on rows 1-1764 and `0.0035`/day on rows 1765-2520 (exactly the three most recent windows). Assert windows `j = 0, 1, 2` are tagged reliable and `n_reliable >= 3`. Derivation: per-window se about `0.008 / sqrt(252) = 5.0e-4`, z about 7; BH rejects them whenever each `p <= 3 x 0.05 / 10 = 0.015` (`|z| >= 2.43`), failure `P(Z < 2.43 - 7) ≈ 2.5e-6` per window. No assertion on the seven null windows (BH may reject one of them).
- **TR26 Family rate under zero alpha (`slow`).** DGP-R0, `R = 1000`. Share of replications where FR1 rejects at least one window: `<= 0.10`. Derivation: with exact, independent tests BH gives 0.05; each 252-row HAC test with the normal reference over-rejects (calibration: size 5.8% at 5%, 0.74% at 0.5%), giving a measured family rate of 0.072; `0.072 + 3.5 sqrt(0.072 x 0.928 / 1000) = 0.101`. A rate above 0.10 means the per-window test is worse than documented in R5.2.
- **TR27 Split-half alpha.** DGP-A: `n_first = 1260`, `n_second = 1260` (`n = 2521` gives 1260 and 1261); `alpha_first_annual` and `alpha_second_annual` equal separate OLS intercepts on each half x 252 (`1e-10` relative); `difference_z` and `difference_p` equal the `g` coefficient's z and p in the reference pooled HAC fit (design `[1, F, g, g F]`, `maxlags = L(n) = 8`, `1e-10` relative); the second-half se equals `res.t_test` on `const + g` from that fit (`1e-10` relative). Known shift: DGP-A betas, `sigma_e = 0.008`, `alpha = 0` on the first half and `0.002`/day on the second: `difference_p < 0.05` and `|difference_annual - 0.504| <= 4 difference_se_annual`. Derivation: se of the difference about `sqrt(2) x 0.008 / sqrt(1260) = 3.2e-4`, z about 6.3, failure `P(Z < 1.96 - 6.3) < 1e-5`.
- **TR28 Calendar-year table.** DGP-A, `W = 252`.
  - Years 2010-2019; `partial` true only for 2019 (`n = 174`).
  - `sum_Y in_sample_sum_Y == n alpha_hat` (`1e-10`); for each year, `in_sample_sum_Y == ` M6.2 alpha column + M6.2 residual column for that year (`1e-10`).
  - 2010: `n_point_in_time = 8` (rows 253-260), `point_in_time_partial` true; other full years have `n_point_in_time == n`; `sum_Y point_in_time_sum_Y == m_c mean_{S_c}(u_tilde)` (`1e-10`).
  - `in_sample_noise_sd_Y == sd(u, ddof=1) sqrt(n_Y)` and `point_in_time_noise_sd_Y == sd(u_tilde over S_c, ddof=1) sqrt(n_point_in_time_Y)` (`1e-12` relative).
  - With `W = 504`: 2010 has `n_point_in_time = 0` and `point_in_time_sum is None`; 2011 has `n_point_in_time = 16` (rows 505-520).

## 6. Regression tests for the plan's "Avoid" list (named for reviewers)

- **TR29 Uncovered tail.** As T33: ticker prices extend 30 rows beyond the factor `last_date`. Assert `chart.dates[-1] == last_date`, `chart.n_uncovered == 30`, `chart.uncovered_from` is the first date after `last_date`, and every residual statistic and series is identical (bitwise) to the run with the tail deleted.
- **TR30 No `fillna(0)`.** DGP-A with NaN injected into 3 prices, 2 factor cells and 1 RF cell (as T95). Assert: the excluded dates have no residual row; no row of `S` has `u_t == y_t` exactly (what a zero-filled factor row would give); every residual output equals the run on clean DGP-A data with the same rows removed from `S` (`1e-10`); calling the module's series function directly with a NaN in `y` or `f` raises `ValueError`.
- **TR31 RF subtracted.** DGP-A variant with `RF = 0.0004` constant, `alpha = 0`, `sigma_e = 0.0024`. Assert `u == (r - RF) - F beta_hat` within `1e-15` (deterministic), and `|in_sample.z| <= 4`, `|point_in_time.z| <= 4`. Derivation: a residual built from raw returns is shifted by `RF = 0.0004`/day; with se about `0.0024 sqrt(1.02) / sqrt(2268) = 5.1e-5` its point-in-time z would be about 7.9 (in-sample about 8.4), so the wrong implementation fails with probability above `1 - 6e-5`, while a correct one fails with `P = 6.3e-5`.
- **TR32 Off-by-one windows.** Named test collecting the window-length assertions: point-in-time betas use exactly `W` rows ending at `t-1` (TR12); rolling alpha windows have exactly 252 rows ending at `t` (TR23); non-overlapping windows have exactly 252 rows and are disjoint (TR24). Assert `len(window) == W` (or 252) for every stamp.
- **TR33 No mixing of compounded and arithmetic values.** DGP-A: calendar-year in-sample sums add exactly to `n alpha_hat` (TR28) while the per-year compounded products `prod(1 + u) - 1` do not add to the compounded total (difference `> 1e-6`); `residual_return_annual - compound_growth_annual > 1e-3` for the in-sample series (drag about `0.19^2 / 2 = 1.8%`); no schema field is the sum or difference of an arithmetic and a compounded value (review check: the field list of R7 has none). Labels: the chart carries `L-HEDGE`; the calendar caption contains "not compounded".
- **TR34 Extreme rows kept.** DGP-A with a consistent `+60%` day at row 1500 (as T100). The row is in `S` (audit warning A4), `u_1500 == y_1500 - beta_hat' f_1500` and `u_tilde_1500 == y_1500 - beta_tilde_1500' f_1500` (`1e-12`, no clipping), and it enters `hit_rate`, `max_drawdown` and the cumulative series.
- **TR35 Static scan.** The T104 AST scan covers `analytics/residual.py` and `analytics/residual_stability.py`, and additionally fails on any `fillna(`, `dropna(`, `clip(` or `np.nan_to_num(` call in these two modules, and on any `shift(` call whose argument is not the literal `1`.

## 7. Diagnostics (`analytics/residual.py`, R6)

- **TR36 Reference calls and demeaning.** DGP-R+.
  - In-sample: `ljung_box_stat`, `ljung_box_p` equal `acorr_ljungbox(e_hat, lags=[10], return_df=True)` at lag 10 and equal the M3.5 values; `jarque_bera_stat`, `jarque_bera_p` equal `jarque_bera(e_hat)`; `arch_lm_stat`, `arch_lm_p` equal `het_arch(e_hat, nlags=5, ddof=0, store=False, result_object=True)` `.lm`, `.lmpval`. All `1e-12` relative.
  - Point-in-time: the same calls on `u_tilde - mean_{S_c}(u_tilde)` (`1e-12` relative). Teeth: `het_arch` on the non-demeaned `u_tilde` gives an LM statistic that differs by more than `1e-6` (the mean 0.0012 is 15% of the daily sd), so an implementation that forgets to demean fails.
  - `ljung_box_lags == 10`, `arch_lags == 5`; each `findings` entry equals the R6 wording for its p-value (exact strings).
- **TR37 Diagnostics behaviour.**
  - GARCH(1,1) residuals: DGP-A factors and betas, `alpha = 0`, `e_t = sqrt(h_t) z_t`, `h_t = 0.05 x 0.012^2 + 0.10 e_{t-1}^2 + 0.85 h_{t-1}`, `h_0 = 0.012^2`, `z_t ~ N(0, 1)`. In-sample `arch_lm_p < 1e-3` and the finding reads "Residual volatility comes in clusters ...". Calibration: LM minimum 33.9, median 169 over 200 seeds, against the `chi2(5)` 0.1% critical value 20.5.
  - iid Student-t residuals (5 degrees of freedom, scaled to sd 0.012): `jarque_bera_p < 1e-3` (population excess kurtosis 6; even a sample excess kurtosis of 1 gives `JB >= 2520/24 = 105`).
  - `slow`, `R = 400` iid Student-t(5) replications: share with `arch_lm_p < 0.05` `<= 0.05 + 3.5 sqrt(0.0475 / 400) = 0.088` (calibration 0.04 over 200 seeds).

## 8. Schema, labels and copy (`report/schema.py`, R7, R8)

- **TR38 Schema validators and serialisation.**
  - A `FactorReport` from DGP-A truncated to 600 rows with `beta_window = 504` (point-in-time `insufficient_data`) serialises with `json.dumps(..., allow_nan=False)`; every not-ok residual statistic has `null` floats and a `reason`; `SCHEMA_VERSION == "3"`.
  - `STATISTIC_MODELS` contains `ResidualStats`, `ResidualChart`, `ResidualGap`, `RollingResidualAlpha`, `NonOverlappingAlpha`, `SplitHalfAlpha`, `ResidualYears`, `ResidualDiagnostics`; T105 passes for each (status, reason, `sample: SampleInfo`).
  - Construction fails (pydantic `ValidationError`) for: a chart list whose length differs from `dates`; `point_in_time_status = "ok"` with a non-null `point_in_time_reason`; `point_in_time_status != "ok"` with a non-null comparison value; an `ok` comparison list that is not `None` before the anchor or not `0.0` at it; a `ResidualStats` with `status = "ok"` and a NaN; a `ResidualGap` with `status = "insufficient_data"` and a non-null `survival_ratio`.
  - Round trip: from the JSON of a full DGP-A report, `in_sample.residual_return_annual == regression.alpha_annual` (bitwise) and `point_in_time.residual_return_annual` equals M6.3 `U` within `1e-10`.
  - `SampleInfo`: in-sample objects `n = 2520`, `window = None`; point-in-time objects and the gap `n = 2268`, `start = 2010-12-22`, `window = 252`; rolling alpha `window = 252`.
- **TR39 Labels, captions and caveats.** DGP-A report. In-sample `ResidualStats` labels `{L-DESC, L-INSAMPLE, L-VINTAGE}`; point-in-time `{L-DESC-PIT, L-PIT, L-VINTAGE}`; chart `{L-INSAMPLE, L-PIT, L-HEDGE, L-VINTAGE}`; gap `{L-INSAMPLE, L-PIT, L-VINTAGE}`; rolling alpha `{L-DESC, L-BAND, L-OVERLAP}`. `LABEL_TEXT` for the four new keys equals R7.1 exactly. `question` equals R8.1; `caveats` equals the five R8.5 strings in order with `{W}` filled; each `caption` equals R7.9 with its placeholders filled. Exact string comparison.

## 9. Live smoke (`live`, non-blocking; same sample as T109-T111)

- **TR40 SPY and AAPL.** SPY: `in_sample.residual_vol_annual <= 0.06` (with `R^2 >= 0.97`, residual volatility is below about `sqrt(0.03) x 0.20 = 0.035`); `|point_in_time.residual_return_annual| <= 0.03`; `wiped_out` false. AAPL: point-in-time `ok`, `wiped_out` false. For both: TR01 (b)-(c), TR13 and TR28 identities hold in the JSON payload within `1e-10`; `verdict` is one of the seven codes; every `findings` string is one of the R6 wordings. Bounds are loose on purpose: they catch broken pipelines (RF, alignment, lag, units), not estimates.

---

## Coverage map (methodology section to tests)

| Section | Tests |
| --- | --- |
| R1 in-sample residual | TR01-TR04, TR31 |
| R2 cumulative series, NaN, tail, wipe-out | TR05-TR07, TR10, TR11, TR29, TR30, TR33 |
| R3 statistics, reading values | TR02, TR05, TR07-TR09 |
| R4 point-in-time, gap, verdict | TR12-TR22 |
| R5 stability | TR23-TR28 |
| R6 diagnostics | TR36, TR37 |
| R7 schema | TR38 |
| R8 copy | TR18, TR39 |
| Look-ahead (M0.2) | TR12, TR15, TR35 |
| Plan "Avoid" list | TR29-TR35 (off-by-one TR32, `fillna(0)` TR30, RF TR31, separate compounding TR33, extreme rows TR34) |
