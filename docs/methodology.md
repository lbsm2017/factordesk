# factordesk methodology specification

Status: v1 specification, written 2026-11-18 from the approved `docs/PLAN.md` (v1 panels plus "Added scope").
Audience: engineers implementing `backend/factordesk/`, and reviewers checking the code against it.
Companion: `docs/test-oracle.md` gives the tests that prove each section. Section numbers (M0, M1.2, ...) are referenced from there.

Rule of precedence: where this document and `docs/PLAN.md` differ, this document wins. Every such difference is listed in **M16 Decisions and deviations from the plan**. Any new statistic must be added here before it ships (Definition of Done).

---

## M0. Global conventions (apply to every section)

### M0.1 Units and notation

| Symbol | Meaning | Unit |
| --- | --- | --- |
| `t = 1..n` | Position of a row in the analysis sample `S` (M2). Positional, not calendar. | - |
| `P_t` | Yahoo `Adj Close` (split- and distribution-adjusted) | price |
| `C_t` | Yahoo `Close` (split-adjusted, NOT dividend-adjusted) | price |
| `D_t`, `G_t` | Cash dividend, capital-gains distribution with ex-date `t` (`Dividends`, `Capital Gains`) | price per share |
| `s_t` | `Stock Splits` value on `t` (new shares per old share; 0 or 1 means no split) | ratio |
| `r_t` | Simple daily total return `P_t / P_{t-1} - 1` | decimal |
| `RF_t` | French daily risk-free rate / 100 | decimal per day |
| `f_t` | Factor vector `(mkt_rf, smb, hml, rmw, cma)'`, French values / 100. `K = 5`. | decimal per day |
| `y_t` | Excess return `r_t - RF_t` | decimal |
| `x_t` | Regressor vector `(1, f_t')'`, so `k = 6` parameters | - |
| `theta` | `(alpha, beta')'`; `beta_i` is the loading on factor `i` | alpha in decimal/day, betas unitless |
| `A` | Annualisation constant, `A = 252` | days/year |

- All returns everywhere in the backend are **simple, daily, decimal** (0.01 = 1%). Percent exists only in the UI formatting layer and in the raw French file.
- Canonical factor order and code names: `mkt_rf, smb, hml, rmw, cma` (+ `rf`). Display names: `Mkt-RF, SMB, HML, RMW, CMA`. Every tie in this document is broken by this order.
- "Style factors" = `smb, hml, rmw, cma`.
- Variances and standard deviations are sample statistics with `ddof = 1` unless a formula says otherwise.

### M0.2 Date stamping and the no-look-ahead rule

1. Every output that carries a date `t` (a "stamped" output) must be a function only of input rows whose date is `<= t`. Prices, dividends, splits, factors and RF after `t` must not influence it in any way (including through normalisation, medians, ranks or smoothing).
2. Full-sample outputs (full-sample regression, attribution, cointegration, CUSUM, VIF, ...) are stamped with the last date of the sample they use, `T_end`. They are explicitly labelled "in-sample: uses the whole window".
3. Where a quantity is used to *explain* day `t` (ex-ante beta for timing, volatility regime of day `t`), it must be computed from rows `<= t-1`. This is done with a positive positional lag (`shift(1)`), never with a negative shift.
4. Forbidden anywhere in analytics: `shift(-k)` for `k > 0`, `rolling(..., center=True)`, `bfill`, `interpolate`, filters or smoothers that use future rows, and any `fillna` on returns, prices, factors or betas.
5. "Point-in-time" in this project means "no future rows of the data vintage we hold". Ken French revises history; we keep one vintage (the latest) and log revisions (M1.1). Label: "Uses the current Fama-French data vintage; historical factor values can be revised."

### M0.3 Trailing windows

A trailing window of length `W` stamped at position `t` contains exactly the rows `t-W+1, ..., t` of the sample it runs on: **exactly `W` observations, including row `t`**.

- The first stamp is position `W` (the W-th row). The number of stamps is `n - W + 1`. No window is computed with fewer than `W` rows (`min_periods = W`).
- Windows are positional on the sample rows, not calendar days. Each stamped result exposes the calendar span of its window (first and last date).
- pandas: `.rolling(window=W, min_periods=W)` with the default `closed="right"`. statsmodels `RollingOLS(window=W)` follows the same convention; the oracle verifies both (T48).
- Windows run on `S` (the stock-aligned sample) unless the section says they run on the full French history (M10.2, M12, M13).

### M0.4 Annualisation

- Mean: `mean_ann = A * mean_daily` (arithmetic, not compounded).
- Volatility: `vol_ann = sqrt(A) * sd_daily` (`ddof = 1`).
- Sharpe: `mean_ann / vol_ann`. For factors no RF is subtracted (they are already excess or zero-cost returns).
- Alpha: `alpha_ann = A * alpha_hat`, `se(alpha_ann) = A * se(alpha_hat)`; the z-statistic is unchanged.
- Contributions are `A * daily mean` (M6.1) or within-year sums (M6.2); never compounded.
- Cumulative returns (`prod(1 + r) - 1`, factor indices, drawdowns) are labelled "cumulative (compounded)" and are never added to arithmetic contributions.

### M0.5 Inference: OLS with Newey-West HAC

Every regression in this project is OLS **with an intercept**. No regularisation, no zero-intercept fits, no weighting.

- Lag rule: `L(m) = floor(4 * (m / 100) ** (2/9))`, where `m` is the number of observations **in that regression** (not in the whole sample). Reference values: `L(126) = 4, L(252) = 4, L(504) = 5, L(750) = 6, L(1000) = 6, L(2520) = 8, L(5000) = 9`.
- Covariance (Bartlett kernel, no small-sample correction):
  `V_hat = (X'X)^-1 S_hat (X'X)^-1`,
  `S_hat = sum_t e_t^2 x_t x_t' + sum_{l=1..L} w_l sum_{t=l+1..m} e_t e_{t-l} (x_t x_{t-l}' + x_{t-l} x_t')`, `w_l = 1 - l/(L+1)`,
  with `e_t` the OLS residuals (sums, not means).
- Reference call, with every argument explicit:
  `sm.OLS(y, X, missing="raise").fit(cov_type="HAC", cov_kwds={"maxlags": L, "kernel": "bartlett", "use_correction": False}, use_t=False)`.
  `X` must contain the constant column (`sm.add_constant(F, has_constant="add")`). `missing="raise"` is a last-line guard: with the statsmodels default (`missing="none"`) one NaN in `y` turns every coefficient into NaN without an error. M2 already keeps NaN out of `S`; the option changes no number.
- statsmodels has no default HAC lag (`fit(cov_type="HAC")` without `maxlags` raises `KeyError`), so `L(m)` is always passed. Never compute HAC after the fit with `results.get_robustcov_results(...)`: it inherits `use_t=True` from a plain fit and silently switches p-values and intervals to the t distribution.
- `se = sqrt(diag(V_hat))`, `z = theta_hat / se`, two-sided `p = 2 * (1 - Phi(|z|))` (standard normal), `CI95 = theta_hat +/- 1.959964 * se`. With `use_t=False` statsmodels returns exactly this p (`2 * norm.sf(|z|)`); our implementation computes the same quantity as `erfc(|z| / sqrt(2))`, which stays accurate in the far tail.
- Rolling windows: statsmodels `RollingOLS` has no HAC option, so rolling HAC is our own vectorised implementation of the formula above. It must match the reference call on any single window to relative `1e-8` (T50).
- Wald test of `R theta = q`: `Wald = (R theta_hat - q)' (R V_hat R')^-1 (R theta_hat - q)`, chi-square with `rank(R)` degrees of freedom. For one restriction this is `z^2`.

### M0.6 Multiple testing: Benjamini-Hochberg

- Level `q = 0.05` everywhere (not tunable).
- Procedure for a family of `m` p-values: sort ascending `p_(1) <= ... <= p_(m)`; let `k* = max{k : p_(k) <= k q / m}`; reject the `k*` smallest. Adjusted p-values via `statsmodels.stats.multitest.multipletests(p, alpha=0.05, method="fdr_bh")`.
- Tests that could not be run (status not `ok`) are left out of the family; `m` is reduced and reported.
- Families (each is corrected separately):

| ID | Family | m | Section |
| --- | --- | --- | --- |
| F1 | Full-sample betas, `H0: beta_i = 0` | 5 | M3 |
| F2a, F2b | Betas of the current window and of the window one year earlier (sign-flip condition) | 5 each | M9 |
| F3 | Drift Wald, latest window vs window one year earlier, per factor | 5 | M9 |
| F4 | Up vs down market beta difference | 5 | M10.1 |
| F5 | High vs low volatility beta difference | 5 | M10.2 |
| F6-GFC, F6-COVID, F6-2022 | Crisis vs rest-of-sample beta difference, one family per window | 5 each | M10.3 |
| F7 | Engle-Granger p-values, all pairs in the cointegration table | 5 + peers | M11 |
| F8 | Out-of-sample ADF p-values, all pairs in the table | 5 + peers | M11 |
| F9 | 5-day betas, `H0: beta_i = 0`, computed only when the residual quality gate fires | 5 | M3.6 |

- Single tests at nominal 5%, not corrected: alpha (M3), 5-day alpha (M3.6), joint drift Wald (M9), CUSUM (M9), residual diagnostics (M3.5). Rolling confidence bands are not tests and are never corrected.

### M0.7 Status values and minimum samples

Every statistic object has `status` in `{"ok", "insufficient_data", "not_applicable", "failed"}` and a human-readable `reason` when not `ok`. When status is not `ok`, numeric fields are `null`. NaN and infinity are never serialised.

| Statistic | Minimum | If not met |
| --- | --- | --- |
| Whole `FactorReport` | `n >= 504` rows in `S` | Request refused: error `insufficient_history` with `n` and `504`. Warning `short_history` if `n < 750`. |
| Rolling betas, window `W` | `n >= W` | Window series empty, status `insufficient_data` |
| Average beta | at least 1 stamp of the primary window (always true when `n >= 504`) | - |
| Tilt/timing | `n > W_p` | `insufficient_data` |
| Dominance | `n >= W_p + M - 1` (to confirm a first label) | Unshaded, status `insufficient_data` |
| Drift (c) Wald, sign flip (b) | `n >= 2W` | condition `insufficient_data` |
| Drift (a) z-score | `n >= 2W + 251` (at least 252 history stamps) | condition `insufficient_data` |
| Drift-norm z-score | `n >= 3W + 251` | norm shown, z `insufficient_data` |
| Regime betas (each split) | `>= 60` rows in **each** regime | `insufficient_data` for that split |
| Crisis window | `>= 60` rows of `S` inside the window | `insufficient_data` (badge "not covered" or "partial (n)") |
| Cointegration pair | `>= 504` common rows | pair `insufficient_data`, excluded from F7/F8 |
| Factor dashboard rolling Sharpe, 1y percentile | 252 rows | first 251 stamps empty |
| Stretch z (h = 252 / 756) | `>= 2520` stamps of the h-window | `insufficient_data` |
| 5-day estimate (M3.6) | `m >= 100` non-overlapping 5-day blocks (500 rows of `S`; always met when `n >= 504`) | `insufficient_data` |

### M0.8 Sample metadata on every result

Every statistic (or group sharing one sample) carries a `SampleInfo`:
`n`, `start`, `end` (actual first and last dates used), `requested_start`, `requested_end`, `window` (if any), `n_excluded` and the list of excluded `(date, reason)`, and `factor_vintage` (`last_date`, `downloaded_at`). The UI shows "requested vs actual" whenever they differ, so truncation by the inner join is never silent.

### M0.9 Standard labels (footnotes)

- **L-DESC** (every panel): "Descriptive, in-sample, not predictive."
- **L-ARITH**: "Arithmetic contributions (not compounded); they add up exactly."
- **L-BAND**: "Pointwise 95% band. Even with a constant true beta, about 1 point in 20 falls outside."
- **L-OVERLAP**: "Overlapping windows: consecutive values share most of their data."
- **L-EXPL**: "Exploratory long-run link, not a trading signal."
- **L-PROXY**: "Return-based proxy, not a valuation spread."
- **L-VINTAGE**: see M0.2 item 5.

---

## M1. Data inputs (`data/factors.py`, `data/prices.py`, `data/audit.py`)

### M1.1 French factor file (`data/factors.py`)

Source of truth for all factor data: the Kenneth R. French Data Library,
<https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html> (see `docs/references.md`).
When this document, another source and the library disagree about a factor's definition, the library wins.

File: `https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Research_Data_5_Factors_2x3_daily_CSV.zip`.

Parser (pure function `bytes -> FactorFrame | error`; `SchemaError` below is `FactorDataError` in the code; the parser reads no clock, so the "last date in the future" check runs only when the caller passes `today`, see D28):
1. Open the zip in memory. Exactly one member whose name ends in `.csv` (case-insensitive), else `SchemaError`.
2. Decode as **latin-1** (the footer contains byte `0xA9`). Split with universal newlines (CRLF and LF).
3. Header = first line whose stripped text starts with `,`. Tokens (split on `,`, each stripped) must be exactly `["", "Mkt-RF", "SMB", "HML", "RMW", "CMA", "RF"]`, else `SchemaError` naming the tokens found.
4. Data rows = lines after the header matching `^\s*\d{8}\s*,`. Each must have exactly 7 fields after stripping. Date parsed strictly as `YYYYMMDD` (invalid calendar date = `SchemaError` with line number).
5. The data block is contiguous. The first non-blank, non-matching line after at least one data row ends it (the copyright footer). Any matching row after the block ends = `SchemaError("unexpected second data block")`.
6. Values parsed with `float`; an empty cell is not a number and is a `SchemaError` (only the sentinels below stand for missing values). A value equal to `-99.99` or `-999` (any trailing zeros) is a **sentinel**: set to NaN and record `(date, column)` (logged as a warning). Other negative values (for example the real `-17.44` on 1987-10-19) are kept.
7. Divide all values by 100 (percent to decimal).
8. Validate: dates strictly increasing and unique; `|factor| <= 0.5`; `RF` in `[-0.0001, 0.002]`. Violation = `SchemaError`.
9. Rows with any sentinel are kept in the stored file with NaN; the analysis sample excludes them with reason `factor_missing` (M2).
10. Revisions: on refresh, for dates in both old and new files, a cell is "revised" when `|new - old| > 5e-5` (half of the last published digit, 0.01% = 1e-4). Log count, max absolute change, and date range of revised cells.
11. Atomic write: write parquet to a temp file in the same directory, flush and fsync, then `os.replace`. `meta.json` holds `last_date`, `downloaded_at` (UTC ISO 8601), `source_url`, `sha256` of the zip, `http_last_modified`, `last_attempt_at`, `last_attempt_ok`. A failed download or a parse error never replaces the previous file. (Not yet aligned: the cache currently writes `last_download_at`, `last_modified`, `rows`, `first_date` and keeps the last attempt in memory only; deferred with M1.2, see D28.)
12. Minimum size: fewer than 15,000 data rows is a `SchemaError` (the real file has about 15,900 rows from 1963-07-01; a truncated download must not replace a good cache).

### M1.2 Staleness and refresh (`data/factors.py`)

Pure function of `(today, now_utc, meta)` with an injected clock:
- `days_behind = (today - last_date).days`; `stale = days_behind > 40`.
- Automatic refresh is attempted iff `stale` AND `now_utc - last_attempt_at > 12 hours` (or no attempt recorded). Checked on app start and on every Factor it.
- Automatic refresh first sends `HEAD`; if `Last-Modified` is not newer than `http_last_modified`, it records the attempt and stops.
- Manual refresh always downloads (no HEAD shortcut, no 12-hour rule).
- No parquet on disk = stale with no prior attempt.
- Note: with a typical one-month publication lag, `days_behind` is often above 40 between releases. The 12-hour rule then limits automatic attempts to two cheap HEAD requests a day. This is intended.

### M1.3 Prices and returns (`data/prices.py`)

- One `yfinance` call per ticker with every argument explicit: `auto_adjust=False, actions=True, repair=False`, full history. Columns used: `Close`, `Adj Close`, `Dividends`, `Stock Splits`, `Capital Gains` (funds only).
- Index: take the timestamp in the **exchange time zone** and keep its calendar date (do not convert to UTC first; an Asian midnight bar would move to the previous day). Result: tz-naive, normalised, unique, strictly increasing `DatetimeIndex` named `date`.
- Duplicate dates (a date delivered more than once, after the time-zone step): the first bar in the vendor's order is kept, and every such date is recorded on the `PriceHistory` (`duplicate_dates`, also kept in the price cache) and reported by the audit as an A1 error `duplicate_index`. A duplicate is never dropped silently (D29). A price history injected without this step is collapsed the same way by the report pipeline.
- Drop any row with date `>=` today in the exchange time zone (today's bar may be incomplete; dropping it always costs nothing because factors lag by weeks).
- Empty or all-NaN result = error `unknown_or_delisted_ticker`.
- `Close` is already split-adjusted. `Stock Splits` is used only by the audit (M1.4), never to rescale prices.
- Returns: `r_t = P_t / P_{t-1} - 1` computed with an explicit `shift(1)` on the ticker's own row index. Never `pct_change()` with its default fill. A NaN or non-positive `P` makes the return of that row and of the next row NaN (excluded and reported in M2).

### M1.4 Adjusted-close audit (`data/audit.py`)

The audit never modifies prices or returns. It returns an `AuditReport` of findings `(date, kind, severity, observed, expected, tolerance)` with overall status `clean | warnings | errors`. Regression returns always come from `Adj Close`. An audit with errors does not block the analysis; it shows a banner and is reported in the status bar.

Definitions: `rho_t = C_t / C_{t-1}` (close ratio), `g_t = P_t / P_{t-1}` (adjusted ratio), rounding tolerance `tau_t = 1e-4 + 0.01 / C_{t-1}` (two half-cent rounding errors in `Close`, plus float noise).

| Check | Rule | Severity |
| --- | --- | --- |
| A1 sanity | `C` or `P` NaN or `<= 0`; duplicate dates (in the frame, or recorded at ingestion, M1.3); non-increasing dates | error |
| A2 gap | a run of more than 7 consecutive missing business days, or more than 10% of business days missing between the first and last date (see D25) | warning |
| A3 stale run | 5 or more consecutive identical `C`: warning when a volume column exists, info without one (a genuinely flat price cannot be told from a halt, D26) | warning / info |
| A4 extreme | `abs(g_t - 1) > 0.40` or `abs(rho_t - 1) > 0.40` (flag only; the row stays in the sample, D26) | warning |
| A5 missing split | on rows with `s_t` not in `{0, 1}`: `|ln(rho_t * s_t)| < 0.15` and `|ln(rho_t * s_t)| < |ln rho_t|` (the close jumped by the share-count ratio, so `Close` was not split-adjusted) | error |
| A5b unrecorded split | rows with `s_t` in `{0, 1}`, `|g_t - 1| > 0.40`, and `|ln rho_t - ln(1/k)| < 0.03` for some `k` in `{2, 3, 4, 5, 8, 10, 15, 20, 1/2, 1/3, 1/4, 1/5, 1/8, 1/10, 1/15, 1/20}` | warning |
| A6 distribution event | for each row with `D_t > 0` or `G_t > 0`, see below | error if no convention matches |
| A7 non-event day | rows with `D_t = G_t = 0` and no split: `|ln g_t - ln rho_t| > tau_t` (adjustment placed on the wrong day) | warning |
| A8 calendar year | see below | error |

A6 detail. The adjustment Yahoo applies (CRSP method) multiplies earlier prices by `1 - Dist_t / C_{t-1}`, which gives the expected adjusted ratio
`g^c_t = C_t / (C_{t-1} - Dist^c_t)`
for a distribution convention `c`. Conventions: `div` with `Dist = D_t` (all tickers); `div+cg` with `Dist = D_t + G_t` (only when a `Capital Gains` column exists). The event discrepancy is `delta^c_t = ln g_t - ln g^c_t`. The event passes if `min_c |delta^c_t| <= tau_t`; the matching convention is recorded. If none matches, the finding reports the dividend implied by `Adj Close`, `D_implied = C_{t-1} - C_t / g_t`. For funds, if different events match different conventions, add warning `inconsistent_capital_gains_treatment` (one source of double counting). The plan's total-return formula `(C_t + D_t)/C_{t-1}` is **not** reported: its difference from `Adj Close` is a convention gap of about `(D/C) r` per event, not a data error, and a figure built on it misleads (D9; validation finding F6: SPY showed 2.52 bp with that formula against 0.010 bp with the convention above). An informational summary finding states the number of events checked, the largest `min_c abs(delta^c_t)`, the range of `tau_t` on event days, the largest non-event discrepancy (A7), the largest `abs(Delta_Y)` (A8) and the cumulative drift.

A8 detail. For each calendar year `Y`: `Delta_Y = sum_{t in Y} (ln g_t - ln e_t)` where `e_t` is `rho_t` on non-event days and the matched `g^c_t` on event days (unmatched events use convention `div`). Error if `|Delta_Y| > tau_Y = 1e-3 + (N_Y + 1) * 0.01 / min_{t in Y} C_t`, where `N_Y` is the number of distribution events in the year. (Rounding errors in log close ratios telescope, so they are bounded by the segment end points rather than accumulating with the number of days.) This, together with A6, means one bad dividend cannot hide in a cumulative number. Cumulative full-history drift `sum_t (ln g_t - ln e_t)` is reported for information.

### M1.5 Ticker metadata caveats

- `currency != "USD"`: warning `currency_mismatch` ("returns are in XXX, factors in USD"). v1 still computes (see open question in M16).
- Non-US listing (exchange country not US, or currency not USD): caveat "US factors applied to a non-US stock: betas mix factor exposure with currency and local-market effects."
- Always: survivorship note "Only tickers that exist today can be analysed. Results for survivors are not representative of companies that were delisted."

---

## M2. Analysis sample and excess returns (`analytics/sample.py`, new, see D16)

Input: ticker price frame (M1.3), factor frame (M1.1), `requested_start`, `requested_end` (defaults: earliest available, latest available).

1. Compute `r_t` on the ticker's own rows (M1.3).
2. **Calendar alignment.** For each ticker row `t` with a previous ticker row `t-1`, collect the French dates in the half-open interval `(date_{t-1}, date_t]`.
   - Exactly one French date and it equals `date_t`: aligned.
   - Two or more French dates: the ticker skipped a day the factor file has, so `r_t` spans several factor days. Exclude row, reason `multi_day_return`.
   - `date_t` not in the French file: exclude row, reason `no_factor_row`.
3. Exclude rows where `r_t`, `RF_t` or any factor is NaN (reasons `price_missing`, `factor_missing`). Nothing is filled.
4. Restrict to `requested_start <= date <= min(requested_end, factor last_date)`. The return on the first kept date uses the previous ticker price, which is earlier data, so there is no look-ahead.
5. `y_t = r_t - RF_t` for every row of `S`. Factors are used as published (`mkt_rf` is already excess; the others are zero-cost).
6. **Uncovered tail.** Ticker dates after the factor `last_date` (and within the requested range) are not in `S`. Report `n_uncovered`, their first and last date, and the ticker's compounded raw return over them. They are shown greyed on the price chart and as a memo row in attribution (M6.4). They never enter any statistic.
7. Guards: `n < 504` = refusal; `n < 750` = warning (M0.7). A price that does not move is also a refusal (`degenerate_input`): if `sd(r_t over S, ddof=1) < 1e-8` per day, the regression would only describe RF and rounding (validation F3: a constant price produced R² = -1154.9). The bound is far below any traded price (a one-cent move on a 1,000 price is 1e-5) and well above float noise.

`S` is the only sample used by M3-M11 (cointegration peers use their own join, M11.1). Its `SampleInfo` (M0.8) lists every excluded row and reason.

---

## M3. Full-sample regression (`analytics/regression.py`)

### M3.1 Model and estimates

`y_t = alpha + sum_i beta_i f_{i,t} + e_t`, `t in S`, OLS with intercept, HAC per M0.5 with `L = L(n)`.

Outputs: `alpha_hat`, `beta_hat` (5), their `se`, `z`, `p`, `CI95`; `alpha_ann = A alpha_hat` with `se` and `CI95` scaled by `A`; `R^2`; adjusted `R^2 = 1 - (1 - R^2)(n - 1)/(n - 6)`; residual volatility `sigma_e_ann = sqrt(A) * sd(e_hat, ddof=1)`; `n`, `L`, `SampleInfo`. Stamped `T_end`.

Design guard (before any fit, also inside every rolling window and the 5-day fit of M3.6). With `X = [1, f]` and its QR decomposition `X = QR` (columns in canonical order), the share of factor `j`'s centred variation not explained by the constant and the factors before it is `u_j = R_jj^2 / sum_t (f_jt - mean f_j)^2`. The design is degenerate when a factor has zero sample variance, or when `min_j u_j < 1e-6` (that factor is a linear combination of the others up to one part in a million: sequential VIF above `1e6`). Genuine French factors have VIF below 3 in every sample seen; a degenerate design means corrupted or duplicated factor data. Full sample: refusal `degenerate_input` with the factor named. Rolling window: the window gets no estimate, and the rolling section has status `failed` with the number of such windows and the first one (never NaN after warm-up). A constant `y` (zero total sum of squares) is also refused, so `R^2` always lies in `[0, 1]`.

### M3.2 Significance tags (the only rule, see D1)

- Betas: two-sided HAC p-values, BH family F1. Rejected = tag **reliable**; otherwise **noise**.
- Alpha: single test, **reliable** iff `p < 0.05`.
- Interpretation text is generated only for reliable coefficients.
- When the residual quality gate fires (M3.6), a coefficient is tagged reliable only if the daily rule above **and** the same rule on the 5-day estimate both reject.
- Large-but-insignificant alpha sentence, shown when `|alpha_ann| >= 0.03` and `p >= 0.05`: "Alpha of {alpha_ann} a year cannot be told apart from zero: residual volatility is {sigma_e_ann} a year over {n/252:.1f} years, so the standard error of annual alpha is {se_ann}." (`se_ann` is the HAC value; the intuition is `se_ann ~ sigma_e_ann / sqrt(years)`.)

### M3.3 Positive/negative beta panel

Diverging bars of `beta_hat_i` with unadjusted HAC `CI95` (L-BAND wording adapted: "95% interval for each beta on its own"). Reliable = solid, noise = muted/hatched. Because tags use BH and the bars show unadjusted intervals, a bar whose interval excludes zero can still be tagged noise; the tooltip says so ("not significant after correcting for testing 5 betas").

### M3.4 Collinearity: VIF and condition number

- `VIF_j = 1 / (1 - R^2_j)`, where `R^2_j` is from OLS of factor `j` on a constant and the other 4 factors, over `S`. Cross-check: `variance_inflation_factor(exog, j)` with `exog` **including** a constant column (without it the function returns wrong values).
- Condition number: `kappa = sqrt(lambda_max / lambda_min)` of the 5x5 factor correlation matrix over `S`. This is the report's `condition_number` field. Never use statsmodels' `results.condition_number`: it is computed on the raw design including the constant column, so with daily factors (about 0.01 in size next to a column of ones) it is large even for uncorrelated factors (about 360 on daily FF5 1963-2024, where `kappa` is 2.15), and the usual 20-30 thresholds would fire on every regression.
- Warnings: any `VIF > 5` = "Factors {list} overlap strongly (typically HML/CMA/RMW). Their individual betas are imprecise; the combined exposure is better determined." `VIF > 10` = strong warning. `kappa > 30` = warning. Also list factor pairs with `|corr| > 0.6`.

### M3.5 Residual diagnostics (details drawer, informational; `analytics/diagnostics.py`)

HAC standard errors are prespecified for every regression (M0.5). The diagnostics below describe the full-sample OLS residuals `e_hat` of M3.1 (positional rows of `S`). They neither justify nor select the covariance estimator: on daily returns a rejection can come from volatility clustering alone, and choosing the covariance after a pretest changes the size of every later test. Nominal 5%, not corrected. They never drive tags or alerts, with one exception: the lag-1 autocorrelation feeds the data-quality gate of M3.6.

| Statistic | Definition and call | Reading |
| --- | --- | --- |
| Lag-1 autocorrelation | `rho_1 = sum_{t=2..n} e_t e_{t-1} / sum_{t=1..n} e_t^2`. Heteroskedasticity-robust standard error under no autocorrelation: `s_rho = sqrt(sum_{t=2..n} e_t^2 e_{t-1}^2) / sum_{t=1..n} e_t^2`; `z_rho = rho_1 / s_rho`, two-sided normal p. | Negative: part of a day's unexplained return reverses the next day. Positive: unexplained returns persist. |
| Ljung-Box | `acorr_ljungbox(e_hat, lags=[10], model_df=0)`: one test at lag 10 (`lags=10` would return ten tests); `model_df` stays 0 because the regressors are not lags of `y`. Chi-square, 10 df. | Assumes constant variance. Under volatility clustering it rejects far more often than 5% even without autocorrelation (skill review finding 1: 49.7% at nominal 5% under GARCH(1,1)-t5), so it is shown with that caveat. |
| Robust Breusch-Godfrey | Auxiliary OLS on rows `t = 11..n`: `e_t = a + c' f_t + sum_{l=1..10} g_l e_{t-l} + u_t` with HC0 covariance; Wald statistic of `g = 0`, chi-square with 10 df. Own implementation (statsmodels' `acorr_breusch_godfrey` has no robust option and rejected 47% under the same GARCH null); cross-checked against `sm.OLS(e[10:], Z, missing="raise").fit(cov_type="HC0").wald_test(R, scalar=True, use_f=False)`. | Autocorrelation test that stays valid under volatility clustering (5.3% size under the GARCH null in the skill review). |
| ARCH-LM | `het_arch(e_hat, nlags=5, result_object=True)`, fields `lm`, `lmpval` (chi-square, 5 df). | Volatility clustering: calm and turbulent periods alternate. |
| Jarque-Bera | `jarque_bera(e_hat)` returns `(stat, p, skew, kurtosis)`; chi-square, 2 df. | Fat tails or skew: normal-based intervals are approximate. |
| Durbin-Watson | `durbin_watson(e_hat)`; no p-value. `DW` is about `2 (1 - rho_1)`. | Near 2: little first-order autocorrelation; above 2: negative, below 2: positive. |

API rules (statsmodels 0.15): `het_arch`, `acorr_breusch_godfrey` and `adfuller` must be called with `result_object=True` and read by field name; their tuple returns emit `FutureWarning`, and CODING_STANDARDS section 8 forbids silenced warnings. `acorr_ljungbox`, `jarque_bera` and `durbin_watson` return without warnings. Computing the diagnostics must emit no warning (T47).

Plain-language readings (one generated sentence per row; `{p}` formatted as in the report):
- Lag-1: "Lag-1 autocorrelation of the residuals is {rho_1:+.2f} (robust z {z:+.1f})." followed by "Part of each day's unexplained return reverses the next day." if `p < 0.05` and `rho_1 < 0`; "Unexplained returns tend to persist into the next day." if `p < 0.05` and `rho_1 > 0`; otherwise "No clear day-to-day pattern."
- Ljung-Box: "Ljung-Box (10 lags) {rejects / does not reject} no autocorrelation (p {p}). It assumes constant variance, so it rejects too often on daily returns; read the robust test below."
- Robust Breusch-Godfrey: "Autocorrelation test robust to changing volatility (10 lags): {autocorrelation present / no autocorrelation detected} (p {p})."
- ARCH-LM: "Volatility clustering (ARCH-LM, 5 lags): {present / not detected} (p {p})."
- Jarque-Bera: "Residual tails: {fatter than normal or skewed / consistent with a normal distribution} (Jarque-Bera p {p}, skew {skew:+.2f}, excess kurtosis {kurtosis - 3:.1f}){; normal-based intervals are approximate}."
- Durbin-Watson: "Durbin-Watson {dw:.2f}: near 2 means little first-order autocorrelation; above 2 points to negative, below 2 to positive autocorrelation."
- Always: "Standard errors are Newey-West HAC for every regression whatever these tests show; the tests are informational."

Status: `ok` whenever M3.1 is ok (`n >= 504` leaves far more rows than the 10 lags), except for an exact fit: when `1 - R^2 < 1e-12` the residuals are rounding noise, the diagnostics and the gate of M3.6 are `not_applicable` with that reason (the ARCH-LM auxiliary regression is singular there), and the 5-day estimate is `not_applicable`.

### M3.6 Residual quality gate: non-synchronous prices (`analytics/diagnostics.py`)

**Why.** When a ticker's closing prices are not synchronous with the factor data (for example an ETF close recorded after the 4:00 pm index close, or stale and bid-ask-bounce prices), each day's residual contains a transient price error that reverses the next day: `e_t = w_t + u_t - u_{t-1}`. Then `cov(e_t, e_{t-1}) = -var(u)` and `rho_1 = -var(u) / (2 var(u) + var(w))`, so the share of residual variance that is transient noise is `s = 2 var(u) / var(e) = -2 rho_1` (at most 1, reached at `rho_1 = -0.5`). The noise inflates the residual variance, so `R^2` falls and residual volatility and the idiosyncratic share overstate stock-specific risk; the part of a move recorded after the factor day's close also biases daily betas. Because the error telescopes, it moves the sample mean, and hence alpha, by at most `(u_n - u_1)/n`, but it changes alpha's standard error. Validation (docs/validation/spy-slice-validation.md section 3) found exactly this in SPY before about 2009.

**Statistic.** `rho_1` and `z_rho` from M3.5.

**Sampling uncertainty.** With no autocorrelation and constant variance, `sd(rho_1)` is about `1/sqrt(n)`: 0.045 at the minimum `n = 504`, 0.020 at `n = 2520`, 0.011 at `n = 8474`. Under volatility clustering the robust `s_rho` is larger (SPY full sample: 0.031 against 0.011), so a point estimate alone could cross the threshold by chance in a short, volatile sample. The second condition below guards against that.

**Rule (pre-specified, fixed constants, M15).** The gate fires iff `rho_1 < -0.2` **and** `z_rho < -4` (both strict). This is the validator's rule G1 adopted by the owner (D22).
- `-0.2`: at this value about 40% of the residual variance is transient noise (`s = 0.4`), so residual volatility is overstated by a factor of about `1/sqrt(1 - 0.4) = 1.29`; that is where `R^2`, residual volatility and the idiosyncratic share stop describing the stock.
- `-4`: a false alarm from sampling error alone has probability `Phi(-4) = 3.2e-5` per ticker when there is no autocorrelation.
- The threshold is a documented heuristic. It was written down in the validation review from the noise-share argument above and checked against five S&P 500 products only (full-sample `rho_1`: SPY -0.40, IVV -0.40, VOO -0.20, VFINX -0.11, S&P 500 total-return index -0.06). It was not adjusted to make any ticker fire; SPY lies far beyond it. Its false-alarm rate on single stocks, small caps and ADRs is unknown until a panel calibration has been run and registered (pending). The constants change only through a new D-entry and a registry line (`docs/registry/tests.jsonl`).

**What happens when it fires.**
1. Report warning `residual_reversal`, listed first among the warnings and shown at the top of the report: "Daily price changes partly reverse the next day: the lag-1 autocorrelation of the regression residuals is {rho_1:+.2f} (robust z {z:+.1f}). The closing prices are probably not synchronous with the factor data (for example a close recorded after the 4:00 pm index close). Under a simple model of a price error that reverses the next day, about {s:.0%} of the residual variance is such noise, so R², residual volatility and the idiosyncratic share overstate stock-specific risk. Alpha and betas are also estimated from 5-day returns; a coefficient is tagged reliable only if the daily and the 5-day tests both reject." (`s = min(1, -2 rho_1)`.)
2. The 5-day estimate below is computed and shown next to the daily one.
3. Tags follow M3.2 with the conjunction rule: alpha is reliable iff the daily alpha p and the 5-day alpha p are both below 0.05; beta `i` is reliable iff it is rejected in F1 (daily) and in F9 (5-day). Interpretation sentences and the M7 risk sentences use these combined tags.
4. Nothing else changes: the headline (daily, full-sample) numbers are shown as computed and the sample is never cut to a "cleaner" period (D21).

When the gate does not fire, the 5-day estimate has status `not_applicable` (reason "the residual quality gate did not fire") and M3.2 applies unchanged. Showing a second set of numbers for every ticker would invite choosing whichever looks better.

**5-day estimate.**
- Blocks: non-overlapping blocks of 5 consecutive rows of `S`, anchored at the first row: block `b` holds rows `5b-4 .. 5b`, `b = 1..m`, `m = floor(n/5)`. The last `n - 5m` rows (0 to 4) are not used and are reported. Rows are positional, as in M0.5.
- `Y_b = sum_{t in b} y_t`, `F_b = sum_{t in b} f_t` (simple sums, not compounded, so the daily model sums exactly: `Y_b = 5 alpha + beta' F_b + E_b`).
- OLS with intercept and HAC per M0.5 with `L(m)` (design guard of M3.1 included). Betas are directly comparable with the daily ones; `alpha_ann = (A/5) * alpha_5`, with its se and CI scaled the same way. `R^2` and residual volatility `sqrt(A/5) * sd(E_hat, ddof=1)` are reported.
- Tags: alpha single test at 5%; betas BH within family F9.
- Why non-overlapping and not overlapping 5-day sums with HAC: overlapping sums make the errors MA(4) by construction; Newey-West with Bartlett weights down-weights exactly those lags (`w_4 = 0.6` at `L = 9`), so it underestimates the long-run variance and over-rejects in finite samples (Hodrick 1992; Britten-Jones, Neuberger and Nolte 2011). Non-overlapping blocks need no correction beyond M0.5. Within a block the transient error telescopes (`E_b` contains `u_{5b} - u_{5b-5}` once instead of five reversing pairs), so its share of the residual variance falls about five-fold. The cost is about one fifth of the observations, hence wider intervals.
- Why anchored at the first row: a longer sample (a new factor vintage) only appends blocks; earlier blocks never change, so results are reproducible. The point estimate does depend on which 5 rows form a block (SPY alpha: -0.56% a year anchored at the first row, -0.45% anchored at the last row, against a 5-day standard error of about 0.22%); the phase is fixed by this rule and never chosen per ticker.
- Minimum: `m >= 100` blocks (500 rows). The report minimum `n >= 504` always meets it; below it the estimate is `insufficient_data`.

Labels: L-DESC + "Sums of daily returns over non-overlapping blocks of 5 trading days; computed because the residual quality gate fired."

Not adopted: the validator's second gate (G2, residual-variance stability with a break test) needs the same panel calibration and is deferred.

---

## M4. Rolling betas (`analytics/rolling.py`)

- Windows: `W in {126, 252}` always computed (overlaid in the UI, opacity by window length). The primary window `W_p = beta_window` (API parameter, allowed `{126, 252, 504}`, default 252, see D17) drives M5, M6.3, M8 and M9; if `W_p = 504` it is computed in addition.
- At each stamp `t >= W`: OLS of `y` on `x` over rows `t-W+1..t` of `S` (M0.3); HAC with `L(W)` (4 for both 126 and 252; 5 for 504).
- Per stamp outputs: `alpha_hat_t`, `beta_hat_t`, `se`, `CI95` (pointwise), `R^2_t`, `sigma2_e_t = sum(e^2)/(W - 1)` (window residuals, see M7), `Sigma_f_t` (`ddof = 1`), window first/last date.
- Ex-ante beta for explaining day `t`: `beta_tilde_t = beta_hat_{t-1}` (positional lag of one row of `S`).
- Label: "Each point uses the previous {W} trading days, ending on that date." + L-BAND + L-OVERLAP.

## M5. Average beta (`analytics/rolling.py`)

For each factor, over all stamps of `W_p`: mean, `sd` (`ddof = 1`), 10th and 90th percentiles (linear interpolation), min, max, number of stamps, share of stamps with `beta_hat > 0`; shown beside the full-sample `beta_hat` (M3) with a sparkline of the rolling series. Stamped `T_end`.

Label: "Average of {N} overlapping {W_p}-day estimates. The spread shows how exposure moved over time; it is not a standard error. The average of rolling betas generally differs from the full-sample beta."

---

## M6. Return contribution (`analytics/attribution.py`)

### M6.1 Static, full sample (waterfall)

Because OLS with an intercept makes residuals sum to zero:
`mean(y) = alpha_hat + sum_i beta_hat_i mean(f_i)` exactly, over `S`.
Rows (all `x A`): `contrib_i = A beta_hat_i mean(f_i)`; `alpha_ann = A alpha_hat`; `residual = A mean(e_hat)` (zero to machine precision; shown as "0 by construction"); `total = A mean(y)`.
Identity: `sum_i contrib_i + alpha_ann + residual = total`, tolerance `1e-10` absolute. Label L-ARITH + "uses full-sample betas".

### M6.2 Per calendar year (table)

For calendar year `Y` with `n_Y` rows of `S`, using the full-sample `alpha_hat`, `beta_hat`, `e_hat`:
`sum_{t in Y} y_t = n_Y alpha_hat + sum_i beta_hat_i sum_{t in Y} f_{i,t} + sum_{t in Y} e_hat_t` exactly.
Table entries are these **within-year sums** of daily decimal returns (not annualised, not compounded; see D7). Each row shows `n_Y`; years with `n_Y < 200` are marked "partial year". The residual column is generally non-zero within a year. Label: "Sum of daily contributions within the year (not compounded), using betas from the whole sample."

### M6.3 Tilt vs timing (dynamic)

Sample `S_dyn` = rows `W_p + 1 .. n` (rows where an ex-ante beta exists), `n_d = n - W_p`. With `beta_tilde_{i,t} = beta_hat_{i,t-1}` from the `W_p` window:
- Dynamic contribution `Dyn_i = A * mean_t(beta_tilde_{i,t} f_{i,t})`.
- Tilt `Tilt_i = A * mean_t(beta_tilde_{i,t}) * mean_t(f_{i,t})`.
- Timing `Timing_i = Dyn_i - Tilt_i = A * cov_pop(beta_tilde_i, f_i)` (population covariance, divisor `n_d`).
- Unattributed `U = A * mean_t(y_t) - sum_i Dyn_i` (contains alpha, residual and rolling-estimation error).
- Identity: `sum_i (Tilt_i + Timing_i) + U = A * mean_{S_dyn}(y)`, tolerance `1e-10`.

The ex-ante lag matters: the beta of the window that contains day `t` is partly estimated from day `t`'s own stock return, so it is not an exposure anyone held before day `t` (look-ahead). Label: "Timing shows whether the exposure estimated from the previous {W_p} days was higher before the factor did well. It is noisy and has no significance test. Sample: {S_dyn dates} (the first {W_p} days are used to estimate the first beta)."

### M6.4 Unattributed and uncovered rows

- The waterfall and the tables never fold anything into alpha. Alpha, residual (M6.2), and `U` (M6.3) are separate rows.
- Memo row below the identity (not part of any sum, see D8): "Not covered by factor data: {n_uncovered} trading days after {last_date}; stock return {x} (compounded, raw, not excess). Not attributed." Plus "Excluded rows: {n_excluded}" with the reasons from M2.

---

## M7. Risk contribution (`analytics/attribution.py`)

Full sample `S`, using the full-sample OLS:
- `Sigma_f` = sample covariance of `f` over `S`, `ddof = 1`.
- `sigma2_e = sum_t e_hat_t^2 / (n - 1)` (`ddof = 1`, not `n - 6`; see D5).
- `V = beta_hat' Sigma_f beta_hat + sigma2_e`. Because OLS residuals have zero mean and zero sample covariance with every factor, **`V` equals the sample variance of `y` exactly** (tolerance `1e-12` relative).
- Euler contributions (shares of variance): `RC_i = beta_hat_i (Sigma_f beta_hat)_i / V`; `RC_idio = sigma2_e / V`. Identity `sum_i RC_i + RC_idio = 1` (tolerance `1e-10`). Also `1 - RC_idio = R^2` exactly.
- `RC_i` is also factor `i`'s share of volatility: `sigma_y = sqrt(V)` is homogeneous of degree one in `(beta, sigma_e)`, and `beta_i d sigma_y / d beta_i = RC_i sigma_y`.
- `RC_i` can be negative (the exposure offsets others). Bars are diverging, sorted by `RC_i` descending, idiosyncratic shown last as its own bar. `vol_ann = sqrt(A V)`.

Exposure x volatility x correlation (tooltip): `sigma_i = sqrt(Sigma_f[i,i])`, systematic return `F_sys,t = beta_hat' f_t`, `sigma_sys = sqrt(beta_hat' Sigma_f beta_hat)`, `rho_i,sys = (Sigma_f beta_hat)_i / (sigma_i sigma_sys)`. Exact identity: `RC_i V = beta_hat_i * sigma_i * rho_i,sys * sigma_sys`. Tooltip shows `beta_hat_i`, `sqrt(A) sigma_i`, `rho_i,sys`, `RC_i`. If `sigma_sys = 0`, `rho` is `null` with status `not_applicable`.

Disagreement sentence: among **reliable** betas only, rank by `|beta_hat_i|` (1 = largest) and by `RC_i` (1 = largest). If some factor has `rank_RC <= rank_beta - 2`, emit one sentence for the factor with the largest gap (ties: canonical order): "{Factor} ranks #{rank_RC} by risk but only #{rank_beta} by beta size: the factor is volatile or moves with your other exposures." If a reliable beta has `RC_i < 0`: "{Factor} reduces total risk because it offsets your other exposures."

Label: L-DESC + "Shares of variance over {dates}; they add to 100%."

---

## M8. Dominant-factor shading (`analytics/dominance.py`)

Three parameters (M15): `W_p` (beta_window, default 252), `M` (min_run, default 10), `include_market` (default false).

1. **Raw rolling risk contribution.** At each stamp `t >= W_p`, compute M7 on the window rows `t-W_p+1..t`: `beta_hat_t`, `Sigma_f_t`, `sigma2_e_t` (all `ddof = 1`), `V_t`, `RC_{i,t}`. Identity per stamp: `sum_i RC_{i,t} + RC_idio,t = 1`.
2. **Raw label.** Candidate set `Cset` = style factors, or all five if `include_market`. `R_t = argmax_{i in Cset} RC_{i,t}` if that maximum is `> 0`, else `NONE`. Ties: canonical order. Sign of beta does not matter (sign-agnostic); a factor that reduces risk (`RC < 0`) cannot dominate.
3. **Confirmation filter (causal, replaces the bidirectional min-run merge, see D3).** Deterministic state machine over stamps in order:

```
D = UNSET; cand = None; k = 0
for t in stamps (ascending):
    r = R[t]
    if r == D:            cand, k = None, 0
    elif r == cand:       k += 1
    else:                 cand, k = r, 1
    if cand is not None and k >= M:
        D, cand, k = cand, None, 0
    L[t] = D               # displayed label at t
```
   Properties (all tested): `L_t` depends only on `R_1..R_t`; every displayed run except the last has length `>= M`; a change of `L` at `t` implies `R` was the new label on each of the `M` rows ending at `t`; with `M = 1`, `L = R` after the first stamp. Example, `M = 3`: `R = AAABAABBBCCAAA` gives `L = UUAAAAAABBBBBA` (`U` = UNSET).
4. **Display.** `UNSET` and `NONE` are unshaded. Stamps before `W_p` (warm-up) are unshaded. The uncovered tail (M2 step 6) is greyed as "no factor data". Shaded share `s_t = max(0, RC_{L_t,t})`; recommended opacity `0.10 + 0.30 * min(1, s_t / 0.30)` (UI constant, not a parameter).
5. **Payload per stamp:** `raw_label`, `label`, `share`, full `RC` vector and `RC_idio` (for tooltips).

Label: "Shading = the style factor that explained the largest share of this stock's variance over the previous {W_p} trading days, shown once it has led for {M} days in a row. Describes the past year at each date; boundaries lag by up to {M-1} days. Not a forecast." With `include_market` on, replace "style factor" by "factor".

---

## M9. Drift alerts (`analytics/drift.py`, new, see D16)

Window `W = W_p`; current stamp `T = n`. Window A = rows `T-W+1..T`; window B = rows `T-2W+1..T-W` (non-overlapping, ending exactly one window earlier).

- **(a) Deviation from own history.** History `H_i = {beta_hat_{i,s} : W <= s <= T-W}` (every rolling estimate that shares no data with window A; needs `|H| >= 252`). `z_a,i = (beta_hat_{i,T} - mean(H_i)) / sd(H_i)`. Condition: `|z_a,i| > 2`. Descriptive only: rolling betas are strongly autocorrelated, so this is not a test and has no p-value. `sd(H_i) = 0` = `not_applicable`.
- **(b) Significant sign flip.** `beta^A_i = beta_hat_{i,T}`, `beta^B_i = beta_hat_{i,T-W}` (stamp `T-W` is exactly window B). Condition: both are BH-reliable within their own window (families F2a, F2b, HAC with `L(W)`) and `sign(beta^A_i) != sign(beta^B_i)`.
- **(c) HAC Wald test of equal betas.** Pooled regression on the `2W` rows of A and B:
  `y_t = alpha + beta' f_t + gamma d_t + delta' (d_t f_t) + e_t`, `d_t = 1` on window A rows, 0 on B rows.
  HAC with `L(2W)` (5 for `W = 252`). Full interaction means `delta_hat_i = beta^A_i - beta^B_i` exactly (same point estimates as two separate regressions). Per factor `z = delta_hat_i / se(delta_hat_i)`, family F3 (BH). Condition: rejected. Also report the joint Wald `delta = 0` (chi-square, 5 df) as "overall style change" (single test).
- **Alert levels per factor:** count of conditions met among (a), (b), (c). One = "alert"; two or more = **strong alert** (plan's risk mitigation). Conditions with status not `ok` count as not met, and the UI says which could not be evaluated. KPI strip: number of strong alerts and factor names.
- **CUSUM (whole sample).** `breaks_cusumolsresid(e_hat, ddof=6)` on the full-sample OLS residuals (M3); returns `(sup_stat, p, crit)`. Flag if `p < 0.05`. Label: "Checks whether the average unexplained return (alpha) shifted during the sample (OLS-CUSUM). It cannot detect changes in betas; the drift alerts do that. It assumes residuals with constant variance and no autocorrelation, which daily returns violate, so it rejects too often; indicative only." OLS-CUSUM detects intercept shifts and has almost no power against beta changes when the factors have mean near zero, as daily factors do (skill review finding 2: 5.3% rejection for a market-beta break from 1.0 to 1.5 against 99.7% for an alpha shift; Ploberger and Kramer 1992). Not part of the alert count.
- **Style-drift magnitude.** `Delta_t = || beta_hat_t - beta_hat_{t-W} ||_2` over the 5 betas of the `W` window, for stamps `t >= 2W`. KPI: `Delta_T`. z-score against history `{Delta_s : 2W <= s <= T-W}` (every value computed without window A's data; needs at least 252 values): `z_Delta = (Delta_T - mean) / sd`. Label: "Size of the change in the five betas versus one year earlier; z compares it with this stock's own history of year-on-year changes. Descriptive; the overall-style-change p-value is the formal test."

All drift outputs are stamped `T`.

---

## M10. Regime-conditional betas (`analytics/regimes.py`, new, see D16)

Common estimator for a 0/1 regime indicator `g_t`, over `S` (or the rows of `S` where `g_t` is defined):
`y_t = alpha + beta' f_t + gamma g_t + delta' (g_t f_t) + e_t`, HAC with `L(n_used)`.
Regime-0 betas `beta_hat`; regime-1 betas `beta_hat + delta_hat` with `Var = V_bb + V_dd + 2 V_bd` from the joint HAC matrix (point estimates equal two separate regressions). Test `delta_i = 0` per factor, BH within the split's family. Minimum `n_g >= 60` in each regime, else that split is `insufficient_data`. UI: small-multiple bars per factor (regime 0 vs regime 1, CI95), with "insufficient data" states.

### M10.1 Up vs down market
`g_t = 1[mkt_rf_t < 0]` (exact zero counts as up). Family F4. Downside beta = regime-1 beta. Label: "Down-market beta: exposure on days the market fell. Conditions on the same day's market return, so it describes asymmetry, not predictability."

### M10.2 High vs low volatility (point-in-time)
Computed on the **full French history** (not on `S`), so the stock sample is not consumed by warm-up:
- `v_t = sd(mkt_rf over the 21 French rows ending at t-1)` (`ddof = 1`; excludes day `t`).
- `med_t = median(v_s over the 252 French rows ending at t)` (each `v_s` itself uses data up to `s-1`).
- `g_t = 1[v_t > med_t]` (high volatility; ties = low).
Join `g` onto `S`. Rows without `g` (first 272 French rows, 1963-1964) are excluded and counted. Family F5. Label: "High-volatility days: market volatility over the previous 21 days was above its median of the previous year. Uses only information available before each day. The split is relative: in a year that is calm (or turbulent) throughout, about half its days are still classed as high."

Note for reviewers: because the threshold is a trailing median, about half of all days are "high" by construction, and classification near regime switches lags by roughly 10 days. The estimated difference is therefore attenuated towards zero relative to the true high/low difference (see test T80).

### M10.3 Crisis windows (fixed constants, inclusive dates; see D14)

| ID | Start | End | Definition |
| --- | --- | --- | --- |
| GFC | 2007-10-09 | 2009-03-09 | S&P 500 closing peak to closing trough |
| COVID | 2020-02-19 | 2020-06-30 | S&P 500 peak, through the end of Q2 2020 (crash and rebound) |
| 2022 | 2022-01-03 | 2022-10-12 | S&P 500 closing peak to closing trough |

`g_t = 1[date_t in window]` over all of `S`; regime-1 betas are the crisis betas, regime 0 is the rest of the sample. Families F6-*. Shown only if `n_crisis >= 60`. Regime-coverage badge (KPI strip): "covered" if `n_crisis >= 60`, "partial (n)" if `0 < n_crisis < 60`, "not covered" if 0. Label: "Crisis betas from {n} days; wide intervals are expected."

---

## M11. Cointegration (`analytics/cointegration.py`)

Parameters (M15): split fraction 0.60, half-life band [5, 60] trading days, peer list.

### M11.1 Series and pairs
- **Factor pairs (5).** On `S`: `Y_t = sum_{s<=t} ln(1 + y_s)` (stock excess-return index, log), `X_{j,t} = sum_{s<=t} ln(1 + f_{j,s})`. Both legs are excess or zero-cost return indices (see D10).
- **Peer pairs.** Default peers SPY, QQQ, IWM and one SPDR sector ETF mapped from the ticker's yfinance `sector` (`Technology->XLK, Financial Services->XLF, Healthcare->XLV, Energy->XLE, Industrials->XLI, Consumer Cyclical->XLY, Consumer Defensive->XLP, Utilities->XLU, Basic Materials->XLB, Real Estate->XLRE, Communication Services->XLC`; unmapped = none). User-editable, maximum 8. A peer equal to the ticker is skipped. Series: `Y_t = ln P_t` (ticker), `X_t = ln P^peer_t` on the inner join of both tickers' rows within the requested range (both audited, M1.4; a peer whose audit has errors gets pair status `failed`).
- The ticker is always the dependent variable `Y`.
- Each pair needs `>= 504` common rows (M0.7).

### M11.2 Per-pair statistics
1. **Engle-Granger.** `coint(Y, X, trend="c", method="aeg", maxlag=None, autolag="aic")` returns a `CointResult` (a tuple subclass, no warning); read it by field name: `coint_t` (stat), `pvalue`, `critical_values`. `pvalue` (MacKinnon approximate) goes into family F7.
2. **Hedge ratio.** `c, h` from OLS `Y_t = c + h X_t + u_t` over the pair sample. Residual `u_hat_t`.
3. **Residual ADF.** The reported in-sample residual ADF statistic is the EG `stat` with the EG `p`. Do **not** report `adfuller(u_hat)` p-values in-sample: they use Dickey-Fuller critical values, which are wrong when the hedge ratio was estimated on the same data.
4. **Johansen (confirmation).** `coint_johansen(np.column_stack([Y, X]), det_order=0, k_ar_diff=1)`. Agrees iff `trace_stat[0] > trace_stat_crit_vals[0, 1]` (95%) and `trace_stat[1] <= trace_stat_crit_vals[1, 1]` (rank exactly one). No p-value exists, so it is not in a BH family; it is a column "Johansen agrees / disagrees".
5. **Half-life.** OLS `Delta u_hat_t = a + phi u_hat_{t-1} + eta_t` (nonrobust se). If `-1 < phi_hat < 0`: `HL = -ln(2) / ln(1 + phi_hat)` trading days (exact formula, not the `-ln 2/phi` approximation); report `phi_hat`, `se(phi_hat)`, `HL`. Otherwise `HL = null`, reason "no mean reversion". Flag "in band" if `5 <= HL <= 60`.
6. **Split-sample test.** `n1 = floor(0.6 n_pair)`. Fit `c1, h1` on rows `1..n1` only. Out-of-sample residual `u^o_t = Y_t - c1 - h1 X_t` for rows `n1+1..n_pair`. `adfuller(u^o, regression="c", autolag="AIC", result_object=True).pvalue` goes into family F8 (without `result_object=True` statsmodels 0.15 emits a `FutureWarning`, which CODING_STANDARDS section 8 does not allow to be silenced). Here standard Dickey-Fuller critical values are correct because the vector was fixed before seeing these rows.

### M11.3 Status per pair
- **"Long-run link (exploratory)"**: F7 rejects AND F8 rejects AND `HL` is finite.
- **"In-sample only"**: F7 rejects, F8 does not.
- **"No evidence"**: otherwise. `failed` / `insufficient_data` as in M0.7.
Append "(Johansen disagrees)" when the Johansen column disagrees with the status.

Spread chart: `u_hat_t` over the full pair sample (labelled "in-sample spread: hedge ratio fitted on the whole period") and `u^o_t` on the last 40% (labelled "out-of-sample, ratio frozen on the first 60%").

Panel label: L-EXPL + "Cointegration between a stock and cumulative factor indices has no established economic meaning and produces false positives on short or single-regime samples."

---

## M12. Factor dashboard (`analytics/factor_dashboard.py`, new, see D16)

Ticker-independent; runs on the full French history (rows with NaN excluded and listed). For each factor `j`, rows `u = 1..N`:
- **Cumulative index** `I_{j,u} = prod_{s<=u} (1 + f_{j,s})`, `I_{j,0} = 1`. Log-scale chart. Label: "Long-short paper portfolio before costs; Mkt-RF is the market's excess return."
- **Drawdown** `DD_{j,u} = I_{j,u} / max_{s<=u} I_{j,s} - 1` (`<= 0`); max drawdown with peak and trough dates; current drawdown `DD_{j,N}`.
- **Rolling Sharpe** at `u >= 252`: `A mean / (sqrt(A) sd)` over rows `u-251..u` (`ddof = 1`), no RF subtraction. L-OVERLAP.
- **Full-history** annualised mean, vol, Sharpe (M0.4).
- **Correlation matrix**: Pearson over full history and over the 252 rows ending at `last_date`, each with `n` and dates.
- **Trailing 1y return percentile**: `R_{j,u} = prod_{s=u-251..u}(1 + f_{j,s}) - 1` for `u >= 252`. Current percentile `100 * (1/(N-251)) * sum_{u=252..N} 1[R_{j,u} <= R_{j,N}]` (empirical CDF, includes the current value). Label: "Rank of the latest 1-year return among all overlapping 1-year periods since 1963; not a forecast."

All series are stamped at `u` and use rows `<= u`.

## M13. Crowding / stretch proxy (`analytics/factor_dashboard.py`)

For `h in {252, 756}` (12 and 36 months of trading days): `Lr^h_{j,u} = sum_{s=u-h+1..u} ln(1 + f_{j,s})`. Expanding (point-in-time) distribution `{Lr^h_{j,v} : h <= v <= u}`; `z^h_{j,u} = (Lr^h_{j,u} - mean) / sd` (`ddof = 1`), shown only when at least 2520 values are available. Report current `z^252`, `z^756`, their percentiles, and current drawdown `DD_{j,N}` (M12). Display tag "stretched" when `|z| >= 2`.

Label: L-PROXY + "How unusual the recent run is versus this factor's own history. Not a holdings-based crowding measure and not a timing signal. Windows overlap: since 1963 there are only about 60 independent 1-year and 20 independent 3-year periods."

---

## M14. API exposure (`report/schema.py`, `api/main.py`)

- Each statistic above maps to a pydantic model with `status`, `reason`, `SampleInfo`, and the label key(s) from M0.9.
- `FactorReport` additionally carries `warnings` (short history, currency mismatch, non-US, collinearity, audit status) and the regime-coverage badges.
- Floats are decimals. NaN/inf are converted to `null` with a status, never serialised.
- Size of the JSON file (D31): it is written without indentation, and the per-stamp rolling series (betas and their HAC standard errors) are rounded to 6 significant digits (relative error at most 5e-6, so a beta of about 1 moves by at most 5e-6, about 1/2000 of its typical standard error of 1e-2; Yahoo `Adj Close` revisions move daily returns by about 2e-6). Every other number is kept at full precision. Nothing is dropped: the HTML draws at most 500 points per series, the JSON keeps every stamp.

## M15. Tunable parameters and constants

| Feature | Tunable (max 3) | Default | Fixed constants (not exposed) |
| --- | --- | --- | --- |
| Regression | none | - | `L(m)` rule, `q = 0.05`, `A = 252`; diagnostics lags 10 (Ljung-Box, robust Breusch-Godfrey) and 5 (ARCH-LM); quality gate `rho_1 < -0.2` and `z_rho < -4`; 5-day blocks anchored at the first row, minimum 100 blocks; design guard `1e-6`; price-movement guard `1e-8` |
| Rolling / average beta | `beta_window` | 252 (allowed 126, 252, 504) | overlays 126 and 252 |
| Return / risk contribution | none (uses `beta_window` for tilt/timing) | - | - |
| Dominance | `beta_window`, `min_run`, `include_market` | 252, 10, false | opacity map |
| Drift | `beta_window` | 252 | `|z| > 2`, two of three for strong |
| Regimes | none | - | 21 / 252 vol windows, `n >= 60`, crisis dates |
| Cointegration | split fraction, half-life band, peers | 0.60, [5, 60], SPY/QQQ/IWM/sector | `k_ar_diff = 1`, `>= 504` |
| Factor dashboard / stretch | none | - | 252, 756, 2520 |
| Data | none | - | 504/750 guards, 40-day / 12-hour refresh, audit tolerances |

---

## M16. Decisions and deviations from the plan

Each entry: what was decided, and why. Entries marked **[plan issue]** flag something I believe is wrong or internally inconsistent in `docs/PLAN.md`.

- **D1 [plan issue] One significance rule.** The plan uses both "BH across the 5 tests" and "reliable if |HAC t| >= 2". These disagree (for example a lone p = 0.03). Decision: BH (q = 0.05) on HAC p-values is the only rule for beta tags; alpha is a single nominal test.
- **D2 HAC settings.** Classic Newey-West (Bartlett), no small-sample correction, normal reference distribution, lag from each regression's own `m`. Bartlett weights, `use_correction=False` and the normal reference (`use_t=False`) are what statsmodels uses once a lag is given, but statsmodels has **no default lag**: `fit(cov_type="HAC")` without `maxlags` raises `KeyError`. So `L(m)` is always passed, together with every other option (`kernel`, `use_correction`, `use_t`), so that a library change cannot move results. p-values are two-sided from the standard normal: statsmodels returns `2 * norm.sf(abs(z))` with `use_t=False`; our code computes the same value as `erfc(abs(z) / sqrt(2))`. `get_robustcov_results` is never used (it inherits `use_t=True` from a plain fit).
- **D3 [plan issue] Causal confirmation filter replaces the 10-day min-run merge.** A merge that relabels short runs by looking at their neighbours uses future rows, which contradicts the plan's own "point-in-time" definition and would fail the look-ahead test. The filter keeps `M = 10` as the minimum displayed run, but shading changes lag by up to `M-1` days. If the owner prefers the retrospective merge, the deterministic version is: run-length encode `R` within each contiguous segment; while a run shorter than `M` exists in a segment with more than one run, take the shortest (ties: earliest); if both neighbours share a label merge all three into it, else merge into the only neighbour, else into the longer neighbour (ties: left). It must then be labelled "retrospective (uses later data)" and excluded from the look-ahead test.
- **D4 Dominance needs positive risk share.** A factor with `RC <= 0` cannot dominate; `NONE` is allowed. Otherwise a factor with 0.5% of variance could be "dominant".
- **D5 Euler idiosyncratic variance uses `SSR/(n-1)`.** With `ddof = 1` throughout, model variance equals the sample variance of excess returns exactly and the systematic share equals R², so the 100% identity is exact rather than approximate.
- **D6 Tilt/timing uses ex-ante betas (`t-1`).** pyfolio-style splits use the beta of the window containing day `t`, which is partly fitted on day `t`'s own return (look-ahead). Unattributed = alpha + residual + estimation noise, reported as one row.
- **D7 Per-year table uses within-year sums,** not `x252` means, so partial years are not extrapolated. The full-sample waterfall keeps the plan's `x252`.
- **D8 [plan issue] Uncovered dates are a memo row, not part of "unattributed".** The plan puts "dates without factor coverage" inside the attribution, but RF and factors are unknown on those dates, so no excess return or identity exists there.
- **D9 [plan issue] Audit formula.** The plan's `(Close_t + Div_t)/Close_{t-1} - 1` is a valid total return but not what Yahoo's `Adj Close` encodes (`Close_t / (Close_{t-1} - Div_t)`, CRSP method). They differ by about `(D/C) * r` per event (around 2e-4 for a 1% dividend on a 2% move). Checking against the plan's formula would cause false failures or force a tolerance loose enough to hide small dividend errors. The audit checks the Yahoo convention. Update after validation (finding F6): the first implementation compared `Adj Close` with the plan's formula at a fixed 5 bp tolerance and reported "max abs diff on a dividend date 2.52 bps" for SPY; with the CRSP convention the largest SPY discrepancy is 0.010 bp and all 136 events pass. The evidence shows the document was right, so the code now implements A5-A8 as written in M1.4, and the plan's figure is no longer reported at all (it is a formula artefact, not information about the data).
- **D10 Factor-pair cointegration uses the stock's excess-return index,** not `log(price)`. The factor indices are excess or zero-cost, and the price includes an RF drift that the EG constant does not absorb. Peer pairs keep log adjusted prices (both legs total return).
- **D11 Cointegration testing families.** "BH across all tests in the table" is implemented as two families over all pairs: F7 (EG p) and F8 (OOS ADF p). In-sample `adfuller` p-values are not reported (wrong distribution). Johansen gives critical values only, so it is a confirmation column outside BH. `k_ar_diff = 1` fixed.
- **D12 [plan issue] Only the Wald condition is BH-corrected.** The plan says "alerts are BH-corrected across the 5 factors", but conditions (a) and (b) are not tests with valid p-values (overlapping rolling estimates). (b) uses BH-reliable betas; (c) is BH across 5; "strong" = two of three. History for (a) and the drift-norm z excludes every estimate that shares data with the current window.
- **D13 Volatility regime uses volatility up to `t-1`, on the full French history.** Including day `t` would put the biggest market moves mechanically into the high-vol bucket; using French history avoids spending 272 stock rows on warm-up.
- **D14 Crisis windows fixed.** GFC and 2022 are S&P 500 peak-to-trough. COVID peak-to-trough (2020-02-19 to 2020-03-23) is only 23 trading days, below the plan's `n >= 60` rule, so it is extended to 2020-06-30 and labelled "crash and rebound". The coverage badge uses the same `n >= 60` rule.
- **D15 [plan issue] SPY expectation.** The plan's oracle says SPY gives "other betas ~0". SPY is large-cap relative to the all-CRSP market, so its SMB beta is reliably negative (around -0.1 to -0.2) with tiny standard errors. The smoke test (test-oracle T109) uses bounds that allow this.
- **D16 New modules.** Alignment, drift, regimes and the factor dashboard have no home in the plan's architecture. Proposed: `analytics/sample.py`, `analytics/drift.py`, `analytics/regimes.py`, `analytics/factor_dashboard.py` (dashboard + stretch proxy).
- **D17 `beta_window` scope.** Restricted to `{126, 252, 504}`. It drives dominance, average beta, drift and tilt/timing; the 126/252 overlay is always shown.
- **D18 Multi-day returns are excluded,** not aligned to a single factor day (M2). Today's bar is always dropped.
- **D19 Stretch proxy uses log returns** (symmetric, additive) and an expanding history, so its value at each date is point-in-time.
- **D20 CUSUM is indicative only.** OLS-CUSUM assumes homoskedastic, serially uncorrelated errors and over-rejects on daily returns; it is excluded from the alert count. It detects shifts in alpha only, not in betas (M9), and is labelled that way.
- **D21 SPY headline alpha is shown, with a caveat (owner decision, 2026-11-18).** The full-sample daily alpha stays the headline even though the pre-2009 SPY closes carry non-synchronous noise. Cutting the sample to 2010 because the residuals look better there would be a forking-paths choice made after seeing the data, and 2010-2026 is a different estimand. The caveat comes from the pre-specified gate of M3.6, applied to every ticker.
- **D22 Residual quality gate adopted (owner decision, 2026-11-18).** The validator's rule G1 (`rho_1 < -0.2` with robust `z < -4`) with its consequences in M3.6. The threshold is a documented heuristic from the noise-share argument, not tuned on SPY, and is pending a panel calibration. The owner's wording was "below -0.2"; the robust-z condition is part of the validator's rule and is kept because of the sampling uncertainty of `rho_1` in short volatile samples (M3.6).
- **D23 5-day estimate: non-overlapping blocks anchored at the first row.** Chosen over overlapping 5-day sums with HAC because overlap induces MA(4) errors that Bartlett weights under-correct; anchoring at the first row keeps earlier blocks fixed as the sample grows. Minimum 100 blocks. Computed only when the gate fires.
- **D24 Audit follows M1.4 A5-A8 (document right).** The code had the plan's dividend formula, a fixed 5 bp tolerance with severity `warn`, a ratio tolerance for missing splits (F16), no unrecorded-split check (A5b) and a 25 bp yearly drift tolerance. Evidence: SPY's 136 events match the CRSP convention to 0.010 bp against `tau_t` of 1.1-3.2 bp (0 failures, largest non-event discrepancy 0.015 bp, largest yearly drift 8e-7 against `tau_Y >= 1.06e-3`), while the plan formula gives 2.52 bp. Code changed to the document (see D9).
- **D25 Gap rule A2: code right, document changed.** The document's "more than 5 calendar days apart" fires on genuine exchange closures (SPY: 2001-09-10 to 2001-09-17, 7 days), which the factor file shares, so every US ticker would carry a warning that says nothing about its data. The code's rule (a run of more than 7 consecutive missing business days, or more than 10% of business days missing) ignores such closures and still catches missing stretches. M1.4 now states the code's rule.
- **D26 Stale-run severity and extreme-move ratio (A3, A4): code right, document changed.** A run of identical closes is a warning only when a volume column exists; without volume a flat price cannot be told from a halt, so it is information. A4 also checks the close ratio: an unadjusted split moves `Close` and `Adj Close` together, and flagging either is harmless.
- **D27 Rows dated today or later are dropped (M1.3, code changed).** The code dropped only a last bar dated exactly today; a bar dated after today (clock skew, vendor bug) survived (validation F9). It now drops every row dated on or after today in the exchange time zone, which M1.3 already required; this was needed for D29 (a duplicated "today" bar must not survive as a historical duplicate).
- **D28 French parser follows M1.1 (document right, except where stated).** Changed in the code: the header must be exactly `["", "Mkt-RF", "SMB", "HML", "RMW", "CMA", "RF"]` in order (reordered columns were accepted); the header line is found after stripping leading spaces (T01 failed before); dates must already be strictly increasing (they were sorted with a warning); `abs(factor) <= 0.5` and RF in `[-0.0001, 0.002]` raise (values only warned above 1.0); a data row after the block has ended raises "unexpected second data block" (a second block was concatenated); an empty cell raises (it silently became NaN); a bad date names its line; the revision tolerance is `5e-5` (it was `1e-12`, so rounding-only changes were logged as revisions); the parser no longer reads the wall clock (the future-date check needs an explicit `today`, passed by the refresh). Evidence that the stricter rules are safe: the current French file passes them (largest `abs(factor)` 0.1744, RF in `[0, 0.0006]`, no sentinels) and the validator's independent parser reproduced the cache exactly. Kept from the code and added to M1.1: the 15,000-row minimum (item 12). Deferred: the `meta.json` keys and the persisted last attempt of item 11 belong to the cache and refresh logic of M1.2, which this change does not touch.
- **D29 Duplicate dates are kept as the first bar and reported, never dropped silently.** The code kept the last bar and only logged it, so the audit never saw the duplicate (validation F5). Now the first bar in vendor order is kept (a later repeat is typically a live intraday bar), the dates are carried on `PriceHistory.duplicate_dates` and in the price cache, and the audit reports A1 `duplicate_index` (error). A provider that returns duplicates directly gets the same treatment in the pipeline instead of an uncaught `ValueError`.
- **D30 Degenerate inputs are refused or reported, never shipped as "ok".** Validation F3: a zero-variance factor crashed with `LinAlgError`, a constant factor gave alpha of -2.6e13 and VIF 0.11 before crashing, and a constant price shipped `R^2 = -1154.9` as "ok". Rules: the price-movement guard (M2 step 7), the design guard (M3.1) for the full sample, every rolling window and the 5-day fit, and a constant-`y` guard. Full-sample cases end in the refusal `degenerate_input` (CLI: one line, exit 1); rolling windows end in a section status `failed` with a reason. Any other numerical error that still escapes becomes a one-line CLI error (exit 1), never a traceback.
- **D31 JSON size.** The SPY report JSON was 6.4 MB (indented; rolling series at full precision). It is now written without indentation and the rolling betas and standard errors are rounded to 6 significant digits (M14). Every value the report displays is unchanged at the precision displayed; no stamp is dropped. Schema version 3 (new diagnostics, gate and 5-day sections).

**Open questions for the project owner**
1. Shading: accept the causal filter (lagged boundaries, provably no look-ahead) or prefer the retrospective merge (cleaner boundaries, labelled as using later data)? (D3)
2. Non-USD tickers: warn and compute (current spec) or refuse until currency conversion exists?
