# factordesk test oracle

Status: v1, written 2026-11-18. Companion to `docs/methodology.md` (sections cited as M0.5, M7, ...; decisions as D1-D20).
Every test below is automatable with `pytest`. Each states its **target module** (names from the `docs/PLAN.md` Architecture section, plus the four new modules proposed in D16), the **setup**, the **assertion**, and the **tolerance with its derivation**. A test that cannot be implemented as written is a spec bug: raise it, do not loosen it silently.

---

## 0. Conventions

### 0.1 Markers and where tests run

| Marker | Meaning | Runs in |
| --- | --- | --- |
| (none) | Deterministic unit or fixed-seed DGP test | every `uv run pytest` (blocking) |
| `slow` | Monte Carlo (hundreds of replications) | CI nightly and before release (blocking for release) |
| `live` | Network: yfinance / Ken French site | manual and scheduled smoke (non-blocking) |

### 0.2 Seed policy

- Test number `k` uses `rng = numpy.random.default_rng(20261118 + k)`. No global `np.random.seed`, no unseeded draws.
- Tolerances are set from standard errors so that a correct implementation fails with probability below about `1e-4` per assertion for **any** seed (a 4-SE two-sided bound has `P(|Z| > 4) = 6.3e-5`). Tests must not be tuned to their seed.
- Nightly seed sweep: every fixed-seed DGP test is also run with seeds `1..50` (marker `slow`). With the bounds above, the expected number of failures across the sweep is below 0.1; any failure is investigated, never "re-seeded".
- Monte Carlo rates use the binomial standard error `sqrt(p(1-p)/R)` and a 3.5-SE band (two-sided `4.7e-4`).

### 0.3 Tolerance policy

| Kind | Tolerance | Why |
| --- | --- | --- |
| Algebraic identity on values of order 0.01-1 | `1e-10` absolute | Float error in these sums is around `1e-15`; `1e-10` leaves room for summation order, not for a wrong formula. |
| Same computation two ways (ours vs statsmodels reference call) | `1e-10` relative (`1e-8` for our vectorised rolling HAC) | Same maths, different summation order. The rolling fast path (cumulative-sum Gram matrices) measures `1e-12` absolute on real data and at most `1e-11` on adversarial designs its guard admits, so `1e-8` leaves three orders of margin; the earlier thresholds reached `2e-8` on betas. |
| Recovery of a true parameter from a DGP | `4 * SE` (HAC SE from the fit, or the theoretical SE when stated) | See 0.2. |
| Labels, counts, dates, statuses | exact | - |

### 0.4 Standard data-generating processes

**DGP-A (static five-factor).** `n = 2520` rows (10 years). Dates: `pd.bdate_range("2010-01-04", periods=n)`; the price series has one extra leading date `2009-12-31` so there are `n` returns. The synthetic French frame uses the same dates.

- Factors `f_t ~ iid N(mu, Sigma_f)`, `mu = (0.0003, 0.0001, 0.0001, 0.0001, 0.0001)`, daily sds `(0.010, 0.006, 0.006, 0.004, 0.004)`, correlations `corr(mkt,smb) = 0.2`, `corr(mkt,hml) = -0.2`, `corr(hml,cma) = 0.6`, `corr(smb,rmw) = -0.3`, `corr(hml,rmw) = 0.2`, others 0 (positive definite; smallest eigenvalue 0.31).
- `RF_t = 0.0001 * (1 + 0.5 * sin(2 pi t / 1260))`.
- `beta = (1.10, 0.30, -0.40, 0.25, 0.15)`, `alpha = 0.0002` per day, `e_t ~ iid N(0, 0.012^2)`.
- `r_t = RF_t + alpha + beta' f_t + e_t`; `Close = Adj Close = 100 * cumprod(1 + r)` starting at 100; no dividends, no splits.
- Theoretical `SE(beta_hat) = sigma_e * sqrt(diag(Sigma_f^-1) / n) = (0.0255, 0.0432, 0.0538, 0.0656, 0.0769)`. Theoretical `SE(alpha_hat)` is about `sigma_e / sqrt(n) = 0.00024`.

**DGP-B (serially correlated).** As DGP-A with `n = 1000`, but `f_t = 0.5 f_{t-1} + sqrt(0.75) nu_t` (`nu_t ~ N(0, Sigma_f)`, same marginal covariance) and `e_t = 0.5 e_{t-1} + sqrt(0.75) * 0.012 * eps_t`. The scores `f_t e_t` then have lag-l autocorrelation `0.25^l`; the long-run variance ratio is `(1 + 0.25)/(1 - 0.25) = 1.667`, so OLS standard errors are too small by a factor of about `1.29`.

**DGP-COINT.** `n = 1500`; `x_t = sum of N(0, 0.01^2)` steps; `u_t = 0.90 u_{t-1} + N(0, 0.005^2)`, `u_0 = 0`; `Y_t = 0.2 + 1.5 x_t + u_t`. True half-life `-ln 2 / ln 0.9 = 6.58` days. Long-run variance of `u`: `lrv_u = 0.005^2 / (1 - 0.9)^2 = 0.0025`.

**DGP-N (non-synchronous price noise, M3.6).** As DGP-A, but the daily return carries a transient price error that reverses the next day: `r_t = RF_t + alpha + beta' f_t + w_t + u_t - u_{t-1}`, `w_t ~ N(0, 0.006^2)`, `u_t ~ N(0, 0.006^2)` iid, `u_0 = 0`. Population lag-1 residual autocorrelation `-var(u) / (2 var(u) + var(w)) = -1/3`; noise share of residual variance `2/3`. With `n = 2520` the robust z of `rho_1` is about `-0.333 / 0.017 = -19`.

**DGP-G (volatility clustering, no autocorrelation).** Residuals `e_t = sigma_t z_t`, `sigma_t^2 = 1e-6 + 0.10 e_{t-1}^2 + 0.85 sigma_{t-1}^2` (GARCH(1,1), started at the unconditional variance `2e-5`), `z_t` Student t with 5 df scaled to unit variance; `r_t = RF_t + alpha + beta' f_t + e_t` with DGP-A factors. No autocorrelation in `e`; strong ARCH effects.

Fixture builders for these DGPs live in `backend/factordesk/tests/fixtures/` and return the same typed inputs (`PriceFrame`, `FactorFrame`) as the real providers.

---

## 1. French factor file (`data/factors.py`, M1.1)

Fixtures are small hand-written CSV texts zipped in memory, plus one frozen copy of the real zip.

- **T01 Header detection.** Text with 4 preamble lines (e.g. "This file was created by CMPT_ME_BEME_OP_INV_RETS_DAILY using the 202609 CRSP database."), 2 blank lines, then `"  ,Mkt-RF,SMB,HML,RMW,CMA,RF"` (leading spaces), then 3 data rows. Assert columns `mkt_rf, smb, hml, rmw, cma, rf` and 3 rows. Exact.
- **T02 Wrong header.** Same with `RMW` missing, and separately with `HML` and `CMA` swapped. Assert `SchemaError` naming the tokens found.
- **T03 Percent to decimal.** Row `19630701,   -0.67,    0.00,   -0.34,   -0.01,    0.16,    0.012`. Assert `mkt_rf == -0.0067`, `rmw == -0.0001`, `rf == 0.00012` within `1e-15`.
- **T04 Sentinels.** Cells `-99.99`, `-999`, `-999.00` become NaN and are listed as `(date, column)`. Cells `-9.99` and the real 1987-10-19 `Mkt-RF` value `-17.44` are kept (`-0.0999`, `-0.1744`). Exact.
- **T05 Footer and latin-1.** Data block followed by a blank line and `b"\xa9 2026 Eugene F. Fama and Kenneth R. French"` (latin-1 byte). Assert parse succeeds, row count is exact, footer not parsed. Assert the parser does not decode as UTF-8 (the same bytes decoded as UTF-8 raise).
- **T06 Second data block.** An 8-digit row after the footer. Assert `SchemaError("unexpected second data block")`.
- **T07 Bad dates.** Separately: `20230230` (invalid) gives `SchemaError` with its line number; a duplicated date and a decreasing date each give `SchemaError`.
- **T08 Line endings.** Same content with CRLF and with LF parses to identical frames (`DataFrame.equals`).
- **T09 Zip members and memory-only.** Zip with 0 CSV members and with 2 CSV members: `SchemaError`. For a valid zip, assert no file is created on disk during parsing (compare a temp directory listing before and after; the parser receives bytes).
- **T10 Value bounds.** A factor of `75.00` (0.75 after conversion) or an RF of `0.50` gives `SchemaError`.
- **T11 Revision diff.** Old and new frames identical except one cell changed by `0.0001` (one published digit) and another by `1e-6`. Assert exactly 1 revision logged, with its max change `0.0001`.
- **T12 Atomic write and failed download.** (a) Monkeypatch the parquet writer to raise after writing part of the temp file: the previous parquet is byte-identical (sha256) and no temp file remains. (b) Mock HTTP 500 and, separately, a zip that fails T02: previous parquet and `meta.json` are unchanged except `last_attempt_at` / `last_attempt_ok = false`.
- **T13 Frozen real file.** A frozen copy of the real zip (fixture, with its download date in the filename) parses; first date `1963-07-01`; seven columns; `last_date` equals the value recorded with the fixture; no sentinels.
- **T116 Pure parser and empty cells (D28).** Parsing the same bytes gives identical frames whatever the system clock says (the clock is never read; a last date 60 days after the passed `today` raises, and the same file parses when `today` is not passed). An empty cell in a data row gives `SchemaError` naming its line. A sentinel is logged with its date and column.

## 2. Staleness (`data/factors.py`, M1.2)

- **T14 Refresh decision table.** Pure function with injected `today`, `now_utc`, `meta`. Exact expected outputs:

| days_behind | last attempt age | HEAD says newer | trigger | expected |
| --- | --- | --- | --- | --- |
| 41 | 13 h | yes | auto | download |
| 41 | 13 h | no | auto | no download, `last_attempt_at` updated |
| 41 | 11 h | - | auto | nothing |
| 40 | 13 h | - | auto | nothing (not stale) |
| no parquet | none | - | auto | download |
| 5 | 1 h | - | manual | download (no HEAD) |

## 3. Prices and returns (`data/prices.py`, M1.3)

- **T15 Time zone to date.** Index `2024-01-04 00:00+09:00` (Asia/Tokyo) gives date `2024-01-04` (not `2024-01-03`); `2024-01-02 00:00-05:00` (America/New_York) gives `2024-01-02`. Exact.
- **T16 Today's bar.** With injected clock at `2026-11-18 15:00` exchange time and a bar dated `2026-11-18`, the bar is dropped; a bar dated `2026-11-17` is kept.
- **T17 Unknown ticker.** Mocked `yfinance.download` returning an empty frame, and one returning all-NaN rows: error `unknown_or_delisted_ticker`. No exception from pandas leaks.
- **T18 Explicit arguments and columns.** Mock `yfinance.download`; assert it was called with `auto_adjust=False`, `actions=True`, `repair=False` explicitly. Two-level columns `(field, ticker)` are normalised to single-level `Close, Adj Close, Dividends, Stock Splits[, Capital Gains]`.
- **T19 Returns with gaps, no fill.** `P = [100, 101, NaN, 103, 104]`. Assert `r = [NaN, 0.01, NaN, NaN, 104/103 - 1]` (1e-15), no zeros, and that index 3 is NOT `103/101 - 1` (what `pct_change()` with a pad fill would give). Rows 2 and 3 appear in the excluded list with reason `price_missing`.
- **T20 Splits not re-applied.** Mock data with `Stock Splits = 4` on one date and an already-adjusted `Close`. Assert returned `Close` and `Adj Close` equal the mock input (no rescaling).
- **T21 Currency and listing caveats.** Metadata `currency = "EUR"` gives warning `currency_mismatch` and the non-US caveat; `USD` on a US exchange gives neither; the survivorship note is always present.
- **T117 Duplicate dates are reported, never dropped silently (D29).** A raw Yahoo frame with one date repeated (second bar with a different `Close`): the normalised frame is unique, keeps the **first** bar, and `PriceHistory.duplicate_dates` lists that date; it survives a cache round trip. The report built from it has audit status `errors` with an A1 `duplicate_index` finding naming the date. The same frame injected through a provider (no normalisation) gives the same report instead of an exception.
- **T118 Rows on or after today (D27).** With the clock at `2026-03-10 17:00` New York, bars dated `2026-03-10` and `2026-03-11` are both dropped; `2026-03-09` is kept.

## 4. Adjusted-close audit (`data/audit.py`, M1.4)

Fixture construction (CRSP method): build a split-adjusted `Close` path (geometric random walk, daily sd 0.015, 3 years, start 100), quarterly dividends `D = 0.005 * C_{t-1}`, then `Adj Close_t = Close_t * prod_{ex-dates tau > t} (1 - D_tau / C_{tau-1})`. Round `Close` to cents and `Adj Close` to 6 decimals.

- **T22 Clean series.** The fixture above plus a 4:1 split (recorded in `Stock Splits`, `Close` already adjusted). Assert status `clean`, zero warning or error findings (the informational summary is allowed). Also assert, in the test, that the plan's figure `(C_t + D_t)/C_{t-1}` differs from the adjusted ratio by more than `tau_t / 10` on at least one event (shows why D9 exists), and that no finding mentions it.
- **T23 Missing split.** Same fixture but `Close` and `Adj Close` before the split date left unadjusted (multiplied by 4). Assert an A5 `missing split adjustment` error on the split date (`rho_t = 1/4`, so `ln(rho_t * 4) = 0 < 0.15`) and an A4 extreme-move warning on the same date. No A5b finding (the split is recorded).
- **T24 Wrong dividend.** Build `Adj Close` with `D = 0.50` at one ex-date (price near 100) while `Dividends` says `0.05`. Assert exactly one A6 error, on that date, with `D_implied` within `0.011` of `0.50` (two half-cent roundings of `Close` enter `D_implied = C_{t-1} - C_t / g_t`; the earlier `1e-3` was tighter than the fixture's own rounding), and one A8 error for that year only; other events and years clean. Margin: `delta = ln((C - 0.05)/(C - 0.50))` about `0.0045`, versus `tau_t` about `2e-4` and `tau_Y` about `1.5e-3`.
- **T25 Fund capital gains.** One fund ex-date with income `0.30` and capital gains `2.00`, price near 50:
  (a) `Adj Close` built with 2.30, `Dividends = 0.30`, `Capital Gains = 2.00`: clean, convention `div+cg`.
  (b) `Adj Close` built with 2.30, `Dividends = 2.30` (already includes gains), `Capital Gains = 2.00`: clean, convention `div` (adding gains again would double count).
  (c) Two events, one as (a) and one as (b): warning `inconsistent_capital_gains_treatment`.
  (d) `Adj Close` built with 6.30 (an amount no convention explains), `Dividends = 2.30`, `Capital Gains = 2.00`: A6 error with `D_implied` within `0.011` of 6.30. (The earlier text used 4.30, "provider double counted"; but 4.30 = `Dividends + Capital Gains` matches convention `div+cg`, so a single such event passes A6 by design. Double counting across events is what (c) detects.)
- **T26 Rounding at low prices.** Fixture rescaled to start at 5.00 (cents rounding is 0.2% of price). Assert status `clean` (no false positives). Derivation: rounding error per ratio is at most `0.01 / C_{t-1}`, which `tau_t` contains.
- **T27 Extreme real move.** A consistent `-45%` day (both `Close` and `Adj Close`). Assert A4 warning, and that the row is in the analysis sample `S` (`n` unchanged versus the same series without the flag check).
- **T28 Unrecorded split.** A day with `rho = 0.5`, `Stock Splits = 0`. Assert A5b warning `possible unrecorded split`.
- **T29 Gaps, stale runs, duplicates.** A run of 8 missing business days gives an A2 `gap_run` warning, 7 do not; more than 10% of business days missing (none consecutive) gives `gaps_fraction`; a 7-calendar-day exchange closure (4 business days, as in September 2001) gives no A2 finding (D25). 5 identical closes give an A3 warning with a volume column and info without; a duplicated date gives A1 error.
- **T30 Adjustment on the wrong day.** Apply a dividend's adjustment one row late in `Adj Close`. Assert A6 error on the ex-date and A7 warning on the next row.
- **T119 Tolerances pinned to M1.4 (literal numbers).** With `C_{t-1} = 100` (so `tau_t = 1e-4 + 0.01/100 = 2e-4`): an event whose log discrepancy is `1.5e-4` passes A6 and one with `2.5e-4` is an error; the same two values on a non-event day give no A7 finding and an A7 warning. A calendar year with summed discrepancy `0.8 * tau_Y` passes A8 and `1.2 * tau_Y` is an error, with `tau_Y = 1e-3 + (N_Y + 1) 0.01 / min C`. An unrecorded close ratio of `0.5` on a `|g - 1| > 0.40` day gives A5b; `0.46` does not (`abs(ln 0.46 - ln 0.5) = 0.083 > 0.03`). The values are literals, not expressions of the module constants, so a wrong constant fails the test.

## 5. Analysis sample (`analytics/sample.py`, M2)

- **T31 Multi-day return.** Ticker calendar missing a date the French file has. Assert the next ticker row is excluded with reason `multi_day_return`, appears in `SampleInfo.excluded`, and the row after it is aligned.
- **T32 Day without factor row.** Ticker trades on a date absent from the French file. Assert that row is excluded (`no_factor_row`) and the following row is aligned (its interval contains exactly one French date).
- **T33 Uncovered tail.** Ticker prices extend 30 rows beyond factor `last_date`. Assert `S` ends at `last_date`, `n_uncovered = 30`, and the memo return equals `prod(1 + r) - 1` over those 30 rows (1e-12). No statistic uses them (n unchanged when the tail is deleted).
- **T34 Requested vs actual dates.** `requested_start = 2010-01-01` (a holiday) and `requested_end` after `last_date`. Assert actual start `2010-01-04`, actual end `last_date`, both requested values preserved in `SampleInfo`. The return on the first kept date uses the `2009-12-31` price.
- **T35 Guards.** DGP-A truncated to 503 aligned rows: refusal `insufficient_history` with `n = 503, required = 504`. 504 rows: ok with warning `short_history`. 750 rows: ok, no warning.
- **T36 Excess return.** `y` equals `r - RF` bitwise for every row of DGP-A.

## 6. Full-sample regression (`analytics/regression.py`, M3)

- **T37 Parameter recovery.** DGP-A. Assert for alpha and each beta `|theta_hat - theta| <= 4 * se_HAC` and `<= 4 * SE_theoretical` (values in 0.4).
- **T38 statsmodels cross-check.** DGP-A. Our `params, bse, pvalues, conf_int, rsquared, rsquared_adj` equal the reference call of M0.5 (`maxlags = L(2520) = 8`, `use_correction=False`, `use_t=False`) to `1e-10` relative.
- **T39 Lag rule.** `L(100)=4, L(126)=4, L(252)=4, L(504)=5, L(750)=6, L(756)=6, L(1000)=6, L(2520)=8, L(5000)=9`. Exact.
- **T40 HAC coverage (slow).** DGP-B, `R = 1000` replications. Coverage of the 95% HAC interval for `beta_mkt` and `beta_hml` in `[0.910, 0.975]`. Derivation: binomial SE `0.0069`, 3.5 SE = 0.024; the lower bound subtracts a further `0.01` for Bartlett truncation bias at `L = 6` (expected long-run factor 1.54 vs true 1.667, giving expected coverage about 0.94). Also assert nonrobust OLS coverage is lower than HAC coverage by at least 0.03 (expected about 0.87).
- **T41 HAC exceeds OLS when it should.** DGP-B, one replication. `bse_HAC / bse_OLS` for `beta_mkt` in `[1.10, 1.40]` (expected 1.24 with `L = 6`).
- **T42 Annualisation.** `alpha_ann == 252 * alpha_hat`, `se_ann == 252 * se`, z unchanged; adjusted R² equals `1 - (1 - R^2)(n - 1)/(n - 6)`; `sigma_e_ann == sqrt(252) * sd(e_hat, ddof=1)`. 1e-12 relative.
- **T43 Significance tags (D1).** Pure function on p-values. `p = (1e-6, 0.03, 0.40, 0.50, 0.70)`: tags `reliable, noise, noise, noise, noise` (BH thresholds 0.01, 0.02, ...; 0.03 > 0.02), even though `|z| = 2.17` for the second. `p = (0.01, 0.02, 0.03, 0.04, 0.05)`: all reliable. Exact.
- **T44 Large insignificant alpha sentence.** `alpha_ann = 0.08`, `p = 0.30`: sentence present with the HAC `se_ann`. `alpha_ann = 0.02`, `p = 0.30`: absent. `alpha_ann = 0.08`, `p = 0.01`: absent. Boundaries (M3.2 says `>= 0.03` and `p >= 0.05`): `alpha_ann = 0.03` and `alpha_ann = -0.03` with `p = 0.30` present; `alpha_ann = 0.08` with `p = 0.05` present; `alpha_ann = 0.0299` absent.
- **T45 VIF, orthogonal factors.** Factors made exactly orthogonal and zero-mean in sample (QR on centred DGP-A draws). All VIF `= 1` and `kappa = 1` within `1e-12`. Known correlation: the same orthonormal columns with CMA replaced by `0.6 q_HML + 0.8 q_CMA` have sample correlation exactly 0.6 between HML and CMA and 0 elsewhere, so the correlation matrix has eigenvalues `1.6, 0.4, 1, 1, 1` and `kappa = sqrt(1.6 / 0.4) = 2` (`1e-12`); `kappa^2 = 4` would fail.
- **T46 VIF, collinear factors.** DGP-A with `cma = 0.95 * hml_scaled + sqrt(1 - 0.9025) * noise` (population R² of CMA on HML 0.9025, VIF about 10.3). Assert our VIF equals `1/(1 - R^2_j)` from a direct OLS (`1e-10`), equals `variance_inflation_factor(exog_with_constant, j)` (`1e-10`), and the strong-collinearity warning fires and names HML and CMA. Pair threshold (`abs(corr) > 0.6`): constructed as in T45 with sample correlation exactly 0.65 the pair is listed; with 0.55 it is not.
- **T47 Residual diagnostics.** On DGP-A residuals: `rho_1` equals `acf(e, nlags=1, fft=False)[1]` and its robust se equals the formula of M3.5 computed directly (`1e-12`); Ljung-Box equals `acorr_ljungbox(e, lags=[10], model_df=0)`; ARCH-LM equals `het_arch(e, nlags=5, result_object=True)` fields `lm`, `lmpval`; Jarque-Bera and Durbin-Watson equal `jarque_bera(e)` and `durbin_watson(e)` (all `1e-12` relative); the robust Breusch-Godfrey statistic and p equal the HC0 Wald test of the auxiliary regression in statsmodels (`1e-10` relative). Computing the diagnostics emits no warning of any kind (`warnings.simplefilter("error")`). Every reading sentence is present.

- **T120 Diagnostics under volatility clustering (slow).** DGP-G, `n = 2520`, `R = 300`. Rejection rate at 5% of the robust Breusch-Godfrey test in `[0.006, 0.094]` (3.5 binomial SE around 0.05), while ARCH-LM rejects in at least 90% of replications. Ljung-Box is expected to over-reject here and is not bounded.
- **T121 Gate rule (pure, boundaries).** `fires(rho, z)` is true for `(-0.21, -5)`; false for `(-0.20, -50)` (strict), `(-0.5, -4.0)` (strict), `(-0.5, -3.9)` and `(-0.19, -10)`. The noise share is `min(1, -2 rho)`: `0.8` at `rho = -0.4`, `1.0` at `rho = -0.6`.
- **T122 Gate on known noise.** DGP-N: `rho_1` within 4 robust SE of `-1/3`; the gate fires; the 5-day betas are within 4 HAC SE of the true betas. DGP-A (no noise): the gate does not fire and the 5-day estimate has status `not_applicable`. Margin: under DGP-A `rho_1` has SE about 0.02, so reaching -0.2 would take a 10-SE draw.
- **T123 5-day construction.** For `n = 2523`: `m = 504` blocks, 3 unused rows at the end; `Y_b` equals the sum of rows `5b-4..5b` (`1e-15`); the fit equals the reference HAC call (M0.5) on the block sums with `maxlags = L(504) = 5` (`1e-10`); `alpha_ann == (252/5) alpha_5`. With `n = 499` (fewer than 100 blocks) the estimate is `insufficient_data`. Appending 5 rows to the sample leaves every earlier block sum unchanged (anchoring at the first row).
- **T124 Tag conjunction (pure).** Daily alpha `p = 0.01` with 5-day `p = 0.20`: noise; both below 0.05: reliable; daily `p = 0.06` with 5-day `p = 0.001`: noise. Betas: daily BH tags `(R, R, N, R, N)` with 5-day `(R, N, R, R, N)` give `(R, N, N, R, N)`; interpretation sentences exist only for the combined reliable betas.
- **T125 Gate in the report.** DGP-N through `build_report`: warning `residual_reversal` is the first warning and its message contains the rounded `rho_1`, the robust z and the noise share; `five_day_regression.status == "ok"`; `regression.alpha_tag` follows T124 given the two p-values; the HTML contains the warning text and the 5-day table. DGP-A: no such warning, `five_day_regression.status == "not_applicable"`.
- **T126 Degenerate inputs (D30).** Through `cli.main` with injected providers, each case ends with exit code 1 and exactly one stderr line, or with exit 0 and a report whose statuses say what happened; never a traceback, never `R^2` outside `[0, 1]`: (a) a factor column of zeros; (b) a constant non-zero factor column; (c) CMA equal to HML; (d) CMA equal to HML plus noise of relative size `1e-4` (unexplained share `1e-8`); (e) constant price with constant RF; (f) constant price with varying RF; (g) a factor column that is zero for 130 consecutive rows in the middle (full sample fine): exit 0, the 126-day rolling section `failed` with a reason, the 252-day section `ok`; (h) NaN gaps in prices and in factor cells: exit 0 with the rows excluded and listed; (i) duplicate dates injected through a provider: exit 0 with an A1 error (T117); (j) an exact fit (DGP-A with `alpha = 0`, `sigma_e = 0`): no warning of any kind, residual diagnostics, gate and 5-day estimate `not_applicable` with a reason. `ols_hac` on (a)-(d) raises `DegenerateInputError` naming the factor.

## 7. Rolling betas and average beta (`analytics/rolling.py`, M4-M5)

- **T48 Exact window length (pyfolio off-by-one).** On DGP-A with `W = 252`: number of stamps `n - W + 1 = 2269`; first stamp at row 252 (1-based); each stamp's window has exactly 252 rows, first row `t - 251`. The estimate at stamp `t` equals `sm.OLS` on rows `t-251..t` (`1e-10`) and differs from OLS on rows `t-252..t` (253 rows) by more than `1e-6`. Same for `W = 126`. Also compare with `RollingOLS(window=W)` params (`1e-10`).
- **T49 Structural break recovery.** DGP-A with `beta_mkt = 0.5` on rows 1-1260 and `1.5` after. Stamp 1260 equals OLS on rows 1009-1260 exactly (`1e-10`) and `|beta_hat - 0.5| <= 4 se`; stamp 1512 has `|beta_hat - 1.5| <= 4 se`.
- **T50 Vectorised rolling HAC.** Five stamps drawn with the test rng, for `W = 126` and `252`: our se equals the reference statsmodels call on that window (`maxlags = L(W) = 4`) to `1e-8` relative (measured `5e-12` on DGP-A and `1e-11` on SPY; T129 bounds the guard-edge designs).
- **T51 Ex-ante beta.** `beta_tilde_t` equals `beta_hat_{t-1}` bitwise; multiplying `f_t` and `y_t` on one row `t` by 10 leaves `beta_tilde_t` unchanged.
- **T52 Average beta statistics.** Mean, sd (`ddof=1`), p10, p90, min, max, share positive equal numpy on the rolling series (`1e-12`); stamp count equals `n - W_p + 1`.

## 8. Return contribution (`analytics/attribution.py`, M6)

- **T53 Static identity.** DGP-A and the frozen SPY fixture: `sum_i contrib_i + alpha_ann + residual == 252 * mean(y)` within `1e-10`; `|residual| <= 1e-12`.
- **T54 Per-year identity.** For each year: `factor sums + n_Y alpha + residual sum == sum y` within `1e-10`. A sample starting 2010-07-01 marks 2010 as partial (`n_Y < 200`). Values are sums, not `x252` (D7): assert the 2011 total equals `sum(y over 2011)`.
- **T55 Tilt/timing by hand.** Pure function with `beta_tilde = (1, 2, 3)`, `f = (0.01, 0.02, 0.03)`, `A = 1`: `Dyn = 0.0466667`, `Tilt = 0.04`, `Timing = 0.0066667 = population cov` (1e-12).
- **T56 Tilt/timing identity.** DGP-A with `W_p = 252`: `sum(Tilt + Timing) + U == 252 * mean(y over S_dyn)` within `1e-10`; `S_dyn` starts at row 253; `n_d = 2268`.
- **T57 Memo rows.** With a 30-row uncovered tail and 2 excluded rows: the memo row exists, its value is not part of any identity sum, and alpha is unchanged when the tail is deleted.

## 9. Risk contribution (`analytics/attribution.py`, M7)

- **T58 Variance identities.** DGP-A: `V == var(y, ddof=1)` (`1e-12` relative); `sum RC_i + RC_idio == 1` (`1e-10`); `1 - RC_idio == R^2` (`1e-10`).
- **T59 Exposure x volatility x correlation.** `RC_i V == beta_i sigma_i rho_i,sys sigma_sys` for every factor (`1e-12` relative).
- **T60 Euler property.** `sigma(b, s_e) = sqrt(b' Sigma_f b + s_e^2)`. Central finite difference with `h = 1e-6`: `beta_i * d sigma / d beta_i == RC_i * sigma` within `1e-6` relative.
- **T61 Negative contribution.** Pure inputs (no randomness): sds `0.010` (mkt), `0.006` (smb), `corr = 0.8`, `beta = (1, -1, 0, 0, 0)`, `sigma_e = 0.01`. `(Sigma_f b)_smb = 0.8*0.010*0.006 - 0.006^2 = 1.2e-5`, so `RC_smb = -1.2e-5 / V < 0`. Assert `RC_smb < 0`, that SMB is the last factor bar in the descending sort, that the shares still sum to 1, and that the negative-share sentence fires only when SMB is tagged reliable (tags passed in).
- **T62 Disagreement sentence.** Pure inputs: reliable betas with `|beta|` ranks `(1, 2, 3, 4, 5)` and RC ranks `(1, 4, 2, 3, 5)` (factor ranked 3 by beta is 2 by RC: gap 1, no sentence); change to RC ranks `(2, 3, 4, 1, 5)` (factor 4: gap 3): exactly one sentence, naming factor 4. Boundary (`rank_RC <= rank_beta - 2`): RC ranks `(2, 3, 1, 4, 5)` (factor 3: gap exactly 2): exactly one sentence, naming factor 3.

## 10. Dominant-factor shading (`analytics/dominance.py`, M8)

- **T63 Filter, hand example.** `M = 3`, `R = AAABAABBBCCAAA` gives `L = UUAAAAAABBBBBA`. Exact.
- **T64 Filter, M = 1.** Random label sequences: `L == R` at every stamp.
- **T65 Filter properties.** 1000 sequences of length 300 over `{SMB, HML, RMW, CMA, NONE}` drawn from a sticky Markov chain (stay probability 0.9), `M = 10`. Assert: (i) every maximal run of displayed labels except the last has length `>= M`; (ii) every change of `L` at `t` has `R[t-M+1..t]` all equal to the new label; (iii) causality: replacing `R[t:]` with random labels leaves `L[:t]` unchanged, for 20 random `t` per sequence.
- **T66 Raw label rules.** Pure RC vectors: all style RC `<= 0` gives `NONE`; tie between HML and RMW gives HML (canonical order); `mkt_rf` largest with `include_market = false` gives the best style factor, with `true` gives `Mkt-RF`.
- **T67 Per-stamp identity.** DGP-A, every stamp: `sum_i RC_{i,t} + RC_idio,t == 1` within `1e-10`; each window `V_t` equals `var(y over window, ddof=1)` (`1e-12` relative).
- **T68 Regime switch.** DGP-A factors, `alpha = 0`, `sigma_e = 0.008`, `beta = (1, 0, 1.5, 0, 0)` on rows 1-1260 and `(1, 0, 0, 1.5, 0)` after; `W_p = 252`, `M = 10`, style only. Assert displayed label HML on every stamp in `[W_p + M - 1, 1260]`, RMW on every stamp in `[1260 + W_p, 2520]`, and exactly one change (HML to RMW) in between. Margin: within a pure regime RC of the 1.5-beta factor is about `1.5^2 * Var(f)` against about `(4 SE)^2 * Var(f)` for the zero-beta factor with SE about 0.12, an order of magnitude apart.

## 11. Drift alerts (`analytics/drift.py`, M9)

- **T69 Pooled equals separate.** DGP-A, `W = 252`: `delta_hat_i == beta^A_i - beta^B_i` (`1e-12`), with `beta^A`, `beta^B` from separate OLS on windows A and B; `beta^B` equals rolling stamp `T - W` (`1e-10`).
- **T70 Wald construction.** Our per-factor z equals the reference HAC call on the pooled design (`maxlags = L(504) = 5`) to `1e-10`; joint Wald equals `res.wald_test(R, scalar=True)` on that fit (`1e-8`).
- **T71 Known drift.** DGP-A with `beta_hml = -0.8` on all rows except the last 252, where it is `+1.0`. Assert for HML: (a), (b) and (c) all true, strong alert. Margins (theoretical): `SE(beta_hml, 252 rows) = 0.17`; window-B `z` about `-4.7`, window-A `z` about `5.9`, Wald `z` about `1.8 / 0.24 = 7.5`; `z_a` about `1.8 / 0.17 = 10`. No assertion on other factors (they are null).
- **T72 Null false-alarm rate (slow).** DGP-A with constant betas, `n = 756`, `R = 400`. Share of replications with at least one F3 rejection `<= 0.05 + 3.5 * sqrt(0.0475/400) = 0.088` (BH controls FDR, which equals the family-wise rate under the global null). Same bound for "any strong alert".
- **T73 Alert levels.** Pure function: condition tuples `(T,F,F)` gives alert, `(T,T,F)` strong, `(F,F,F)` none, `(insufficient, T, T)` strong with the insufficient condition listed.
- **T74 CUSUM.** Our flag uses exactly `breaks_cusumolsresid(resid, ddof=6)` (values equal, `1e-12`). DGP-A with an intercept shift from 0 to `0.003` at row 1000 of `n = 2000`: flagged. Margin: expected statistic about `delta sqrt(n) / (4 sigma_e) = 0.003 * 44.7 / 0.048 = 2.8` against 5% critical value 1.36.
- **T75 Drift norm.** `Delta_T == ||beta_hat_T - beta_hat_{T-W}||_2` (`1e-12`); history count equals `T - 3W + 1` (exact) and contains no stamp `> T - W`.
- **T76 Minimum samples.** `n = 600`: (b), (c) ok; (a) `insufficient_data` (needs 755); norm z `insufficient_data` (needs 1007). `n = 1007`: everything ok.
- **T127 CUSUM negative control (M9 label).** DGP-A with `beta_mkt` changing from 1.0 to 1.5 at row 1000 of `n = 2000` and no intercept shift: the CUSUM is not expected to flag (do not assert a flag; assert only that the label says it checks alpha shifts and cannot detect beta changes), while the drift Wald (c) for Mkt-RF rejects.

## 12. Regime-conditional betas (`analytics/regimes.py`, M10)

- **T77 Pooled estimator.** For a random `g`: regime betas equal separate OLS on each regime (`1e-10`); our regime-1 variance `V_bb + V_dd + 2 V_bd` equals `res.t_test` on `beta + delta` from the reference HAC fit (`1e-10`).
- **T78 Up/down.** DGP-A with `beta_mkt = 0.8` when `mkt_rf >= 0` and `1.4` when `< 0`. Both recovered within `4 se`; F4 rejects for Mkt-RF. Margin: SE about `0.012 / (0.006 * sqrt(1260)) = 0.056` per regime (the sd of a sign-truncated normal is `0.60 sigma`), difference 0.6, about 7.6 SE. Also: a row with `mkt_rf == 0.0` is classed up.
- **T79 Volatility regime is point-in-time.** `v_t` equals the sd of French `mkt_rf` rows `t-21..t-1` (`1e-15`); multiplying `mkt_rf_t` by 10 leaves `g_t` unchanged (it may change `g_{t+1}`); the first 272 French rows have no `g`.
- **T80 Volatility regime, known effect.** French-length synthetic market with sd alternating `0.006` / `0.018` in blocks of 126 rows, `n = 4032`; `beta_mkt = 1.0` in calm blocks and `1.6` in turbulent blocks (truth by block). Assert `delta_hat_mkt > 0`, F5 rejects, and `delta_hat_mkt` in `[0.15, 0.60]`. Derivation: about 10% of days are misclassified (21-day lookback lags switches), and misclassified turbulent days carry 9 times the factor variance, so the low-regime beta is pulled up; the expected `delta_hat` is about 0.3 with SE about 0.05 (checked on several seeds). The upper bound is the true difference.
- **T81 Crisis windows and badges.** Constants equal M10.3 exactly. On a Mon-Fri synthetic sample starting `2009-01-02`: GFC `n = 47`, badge `partial (47)`, status `insufficient_data`; COVID and 2022 covered with `n >= 60`. On a sample starting 2015: GFC `not covered`.

## 13. Cointegration (`analytics/cointegration.py`, M11)

- **T82 Known cointegration.** DGP-COINT. Assert: EG `p < 1e-3`; `|h - 1.5| <= 4 sqrt(lrv_u / sum (x_t - mean x)^2)` (conditional SE of the superconsistent estimator given the realised `x` path); `|HL - 6.58| <= 4 se_HL` with `se_HL = ln 2 * se(phi_hat) / ((1 + phi_hat) ln(1 + phi_hat)^2)` (delta method); OOS ADF `p < 0.01` (expected DF statistic about `-5.6` on 600 rows); status `long-run link`; Johansen agrees; HL in the 5-60 band.
- **T83 Link breaks out of sample.** DGP-COINT, but for rows after `n1 = 900` the residual becomes a random walk with drift `0.003` per row (sd 0.005). Assert OOS ADF `p > 0.10` (drift of 1.8 against noise of about 0.12: the frozen residual trends) and status is not `long-run link`.
- **T84 Null size (slow).** `R = 300` pairs of independent random walks, `n = 1000`. EG rejection rate at 5% in `[0.006, 0.094]` (3.5 binomial SE). Tables of 9 independent null pairs (`R = 300`): share with any `long-run link` `<= 0.094`.
- **T85 Reference calls.** EG stat and p equal `coint(Y, X, trend="c", method="aeg", maxlag=None, autolag="aic")`; OOS p equals `adfuller(u_o, regression="c", autolag="AIC", result_object=True).pvalue` (no `FutureWarning`); EG values are read from `coint(...)` by field name (`coint_t`, `pvalue`); Johansen uses `det_order=0, k_ar_diff=1` (values equal, `1e-12`). The payload has no in-sample `adfuller` p-value field. The ticker is always `Y` (swapping inputs in the call is a test failure).
- **T86 BH families.** `p = (0.001, 0.008, 0.039, 0.041, 0.042, 0.06, 0.074, 0.205, 0.212)`: exactly the first two rejected. `p = (0.01, 0.02, 0.03, 0.04, 0.05)` plus one `insufficient_data` pair: all five rejected with `m = 5` (treating the missing pair as `p = 1` with `m = 6` would reject none). Equal to `multipletests(..., method="fdr_bh")`.
- **T87 Series construction.** Factor pairs: `Y_t == cumsum(log1p(y))` (excess index, D10) and `X == cumsum(log1p(f_j))` (`1e-12`). Peer pairs: `log(Adj Close)` on the inner join. Peer equal to the ticker is skipped; more than 8 peers is a validation error; sector `Technology` maps to `XLK`.
- **T88 Pair minimum and failed peer.** A peer with 400 common rows: pair `insufficient_data`, excluded from F7/F8 (`m` reduced). A peer whose audit has errors: pair `failed`.

## 14. Factor dashboard and stretch proxy (`analytics/factor_dashboard.py`, M12-M13)

- **T89 Drawdown by hand.** `f = (0.10, -0.10, 0.0, 0.2222222)`: index `(1.1, 0.99, 0.99, 1.21)`, drawdown `(0, -0.1, -0.1, 0)`, max drawdown `-0.1` with peak date row 1 and trough row 2 (`1e-7`).
- **T90 Rolling Sharpe.** First value at row 252; three random stamps equal `252 mean / (sqrt(252) sd)` over the 252 rows ending at the stamp (`1e-12`).
- **T91 Correlations.** Full-history and trailing-252 matrices equal `np.corrcoef` on the same rows (`1e-12`), each with `n` and dates.
- **T92 Percentile by hand.** Trailing returns `(0.10, 0.20, 0.05, 0.15)` with current `0.15`: percentile 75. Exact.
- **T93 Stretch z.** The number of `h`-window values at the last row is `N - h + 1`, and z needs at least 2520. Synthetic factor with `N = 3000`: `z^252` is ok (2749 values) and equals the formula on trailing sums of `log1p(f)` with the expanding distribution (`1e-12`); `z^756` is `insufficient_data` (2245 values). With `N = 3300`: both ok (3049 and 2545 values).

## 15. Regression tests for the plan's "Avoid" list

Each is a named test so a reviewer can find it.

- **T94 Rolling window off by one.** See T48; this test name exists to assert `len(window) == W` for every stamp of both windows.
- **T95 No `fillna(0)`.** DGP-A with NaN injected into 3 prices, 2 factor cells and 1 RF cell. Assert: the number of exact zeros in returns and betas is unchanged from the clean run; the affected rows are excluded with reasons; full-sample betas equal OLS on the clean data with those rows removed (`1e-10`). Static check: no `fillna(` call in `backend/factordesk/analytics/` or in return computations of `backend/factordesk/data/` (AST scan).
- **T96 No separate compounding.** Per-year rows (T54) add up to the arithmetic total exactly, while compounding each component separately and multiplying does not (asserted difference `> 1e-6` on DGP-A 2011), showing why arithmetic is used. Labels contain the L-ARITH key.
- **T97 RF subtracted.** DGP-A variant with `RF = 0.0004` constant, `alpha = 0`, `sigma_e = 0.004`. Assert `|alpha_hat| <= 4 se` (expected |z| about 0). A regression on raw returns would give `alpha_hat` about `0.0004`, about 5 SE (`se = 0.004 / sqrt(2520) = 8e-5`) away; assert the pipeline's z for alpha is below 3 so that mistake fails the test.
- **T98 Risk adds up.** DGP-A: our shares sum to 1 (T58); the naive `beta_i^2 Var(f_i) / V` shares plus idiosyncratic do not (difference `> 1e-3`, because factors are correlated), proving the DGP would catch a non-Euler implementation.
- **T99 Intercept, no regularisation.** DGP-A with `alpha = 0.001`: alpha and betas recovered within 4 se. Static check: no `sklearn` import and no `fit_regularized` / `hasconst=False` / missing `add_constant` in `analytics/`.
- **T100 Extreme rows kept.** See T27; additionally a `+60%` day is kept and flagged.
- **T101 Cache expiry and currency.** See T14 (a cache older than 40 days triggers a refresh) and T21 (currency mismatch warning).

## 16. Look-ahead (all `analytics/*` and `data/audit.py`)

- **T102 Perturbation after `t*`.** DGP-A with `n = 2520`, `t* = 1800`. Build a perturbed copy where every row after `t*` is replaced: new independent stock returns (prices rebuilt from row `t*`), new factor and RF draws, and a dividend plus a 2:1 split added after `t*`. Rows `<= t*` are identical in all inputs. Run the full pipeline on both. Assert every output stamped `<= t*` is unchanged: rolling 126/252 alpha, betas, se, CI; ex-ante betas; rolling RC vectors; raw and displayed dominance labels and shares; `v_t`, `med_t`, `g_t`; factor indices, drawdowns, rolling Sharpe, 1y percentile series, stretch-z series; drift-norm series `Delta_t`; row-level audit findings. Floats within `1e-12` absolute, labels and counts exact. Variant: also multiply all `Adj Close <= t*` by 0.97 (what a later dividend's back-adjustment does): returns change only by float rounding, so the same assertions hold within `1e-10`.
- **T103 Truncation.** Run the pipeline on DGP-A truncated at `t*`. Every series stamped `<= t*` equals the full run (same tolerances), and all full-sample outputs of the truncated run are stamped `t*`.
- **T104 Static scan.** AST scan of `backend/factordesk/analytics/` and `backend/factordesk/data/` fails on: `shift(` with a negative argument or a unary minus, `center=True`, `bfill`, `backfill`, `fillna(method=...)`, `interpolate(`, `pct_change(` without `fill_method=None`.

## 17. API and schemas (`report/schema.py`, `api/main.py`)

- **T105 Sample metadata everywhere.** Introspect all pydantic statistic models: each has `status`, `reason`, and `sample: SampleInfo` (`n, start, end, requested_start, requested_end, n_excluded, excluded, factor_vintage`).
- **T106 No NaN in JSON.** A `FactorReport` built from DGP-A truncated to 600 rows (some statuses `insufficient_data`) serialises with `json.dumps(..., allow_nan=False)`; every not-ok statistic has `null` numbers and a `reason`.
- **T107 Identities in the payload.** From the JSON of a DGP-A report: return identity (T53) and risk identity (T58) hold within `1e-10` after a round trip.
- **T108 Refusal.** `POST /api/factor-it` on 503 aligned rows returns the typed error `insufficient_history` with `n` and `required`, HTTP 422.
- **T128 JSON size and precision (D31).** `dump_report` writes no indentation (no line starts with a space). Every rolling beta and se in the written JSON equals its value rounded to 6 significant digits, and differs from the unrounded analytics value by at most `5e-6` relative (half a unit in the sixth significant digit when the leading digit is 1); all other floats (regression, attribution, diagnostics) equal the analytics values exactly. `load_report(dump_report(r)) == r`. The number of stamps per window is unchanged.
- **T129 Fast-path guard, adversarial designs (D32).** `test_rolling_adversarial.py`, 1,500 rows of DGP-A, `W = 126` and `252`, each compared with the previous per-window QR implementation on every window and with the statsmodels HAC fit on 7 spot windows (errors in reference standard errors for betas, relative for standard errors), with the routing observed through a recording wrapper of `_exact_windows`. Factor pair at correlation 0.999 and 0.9999: every window reaches QR, drift `1e-10` at most. Correlation 0.99: at most 5% reach QR, drift `1e-10`. Factor means of 5 and 8 standard deviations: no window reaches QR, betas `4e-10`, standard errors `1e-10`; means of 30: every window reaches QR. One `+10` return, or one `+5` market day, at row 400: windows after it reach QR, drift `3e-10`. Factor scales `1e-8` to `1e4`: no window reaches QR, `1e-11` against QR and `1e-8` against statsmodels. Measured errors are in the test's docstrings; bounds are about ten times the measurement. Restoring the earlier thresholds, or a pivot share of `1e-5`, makes the test fail.
- **T130 Start-date effect on rolling values (D32).** DGP-A and DGP-G with `n = 4000`, `W = 126` and `252`: the rolling betas and standard errors of the sample starting at row 1, 500, 2000 or 3000 equal the full sample's on every shared stamp to `1e-11` absolute (measured `1e-13` at most; exactly 0 was the old per-window behaviour and is not required). The 60-fold volatility regime with factor means of 20 standard deviations: `1e-10` (measured `3e-11`).

## 18. Live smoke tests (`live`, non-blocking; data/prices.py, data/factors.py, data/audit.py, analytics/regression.py)

Sample: `2010-01-04` to factor `last_date`. Bounds are loose on purpose: they catch broken pipelines (units, RF, alignment, split handling), not small changes in estimates.

- **T109 SPY.** `beta_mkt` in `[0.93, 1.05]`; `beta_smb` in `[-0.30, 0.00]` (SPY is large-cap; a reliably negative SMB beta is expected, D15); `|beta_hml|, |beta_rmw|, |beta_cma| <= 0.20`; `R^2 >= 0.97`; `|alpha_ann| <= 0.02` (alpha tagged reliable is reported as a warning, not a failure); audit has no errors; `n >= 3000`.
- **T110 AAPL.** `beta_mkt` in `[0.9, 1.5]`; `R^2` in `[0.25, 0.75]`; `beta_hml <= 0.10`; splits 2014-06-09 (7:1) and 2020-08-31 (4:1) present in `Stock Splits` with no A5 error; audit has no errors.
- **T111 NVDA.** `beta_mkt` in `[1.2, 2.4]`; `R^2` in `[0.15, 0.65]`; `beta_hml <= 0`; splits 2021-07-20 (4:1) and 2024-06-10 (10:1) present with no A5 error; audit has no errors.
- **T112 Invalid ticker.** `ZZZZQX` gives `unknown_or_delisted_ticker`.
- **T113 Recent IPO.** A ticker listed less than 18 months before factor `last_date` (chosen when the test is written and recorded in the fixture file) gives `insufficient_history`.
- **T114 French live.** Download succeeds, header validates, `last_date` is within 120 days of today, and the live file agrees with the frozen fixture (T13) on all overlapping dates except logged revisions.
- **T115 Live identities.** For T109-T111 payloads: T53 and T58 identities hold within `1e-10`.
