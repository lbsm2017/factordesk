# factordesk specification: shrunk (Bayesian) betas

Status: specification for a new feature, written 2026-11-18. Not yet implemented.
Audience: engineers implementing `backend/factordesk/analytics/shrinkage.py` (new), the prior-data loader and the schema additions; reviewers checking the code against it.
Companions: `docs/methodology.md` (M0-M16, D1-D20, cited unchanged), `docs/research-protocol.md` (checklist, Appendix A registry, Appendix B power), `docs/test-oracle.md` (style and seed policy), `docs/methodology-datasets.md` (dataset registry D2, vintages D5).
Section ids: SB0-SB12. Tests: TSB01-TSB20 (SB11). Registry entries: SB12.

Rule of precedence: every M0 convention (units, stamping and look-ahead, HAC, BH families, status values, `SampleInfo`, labels) applies unchanged. This feature adds **no hypothesis test and no BH family**. Shrunk betas never replace the OLS betas of M3/M4 anywhere: tags (M3.2), attribution (M6), risk (M7), dominance (M8), drift (M9) and regimes (M10) keep using OLS. Proposed changes to `docs/methodology.md` are listed in SB10.3 for the owner; this document does not edit it.

Evidence markers: **[V]** = verified by a computation run for this document (scripts and outputs in the session scratchpad, folder `specs-kb-sb`, not part of the repo) or by a source checked on 2026-11-18; **[U]** = unverified.

---

## SB0. Scope, notation, classification

### SB0.1 What the feature shows

For the full-sample regression (M3) and for the latest window of the primary rolling regression (M4, stamp `T_end`), the report adds a second set of five betas: the OLS betas pulled toward a stated reference, by an amount that depends on how noisy each OLS beta is. Noisy betas (short history, high residual volatility, collinear factors) move a lot; precise betas do not move. It also adds a **power statement** per style factor: the smallest beta the report's own test would detect, and how much more data would be needed to detect a beta of 0.05.

### SB0.2 Notation (additions to M0.1)

| Symbol | Meaning |
| --- | --- |
| `b` | OLS betas (5-vector) of the regression being shrunk (M3 full sample, or M4 latest window) |
| `V` | HAC covariance of `b`: the 5x5 beta block of `V_hat` of M0.5, with `L(m)` of that regression |
| `m0` | Prior centre (5-vector) |
| `tau` | Prior standard deviations (5-vector); `T0 = diag(tau^2)` |
| `b_post`, `V_post` | Posterior mean and covariance (SB3) |
| `S_w` | Prior-weight matrix `V_post T0^-1`; `b_post = (I - S_w) b + S_w m0` |
| `pull_j` | `S_w[j, j]`, the share of the way factor `j` is pulled toward its prior centre (display "pulled {pull_j:.0%} toward typical") |
| `k80` | `z(1 - a/2) + z(0.80)`; `a = 0.01` (BH-of-5 worst case, protocol Appendix B): `k80 = 3.41745` [V] |

### SB0.3 Classification of every output

| Output | Class | Stamp |
| --- | --- | --- |
| Shrunk full-sample betas, intervals, pull | in-sample (uses the whole window, like M3) | `T_end` |
| Shrunk latest-window betas | in-window, rows `T_end - W_p + 1 .. T_end` | `T_end` |
| Prior (`m0`, `tau`) | point-in-time: estimated from French rows dated `<= T_end` only (SB2.3) | `T_end` |
| MDE and "years to detect" | in-sample (uses the HAC se of the same regression) | `T_end` |

No shrunk value is computed for earlier rolling stamps in v1 (SB10.1, decision SD7).

---

## SB1. Model and the likelihood approximation

### SB1.1 Approximate likelihood

The daily regression errors are heteroskedastic and serially correlated (that is why M0.5 uses HAC), so an iid Gaussian likelihood for `y` would be wrong. The posterior is therefore built on the large-sample distribution of the estimator, not on the likelihood of the data:

`b | beta ~ N(beta, V)`, with `V` the HAC covariance of M0.5 (Bartlett, `L(m)`, no small-sample correction).

This is the "artificial normal posterior centred at the estimator with sandwich covariance" studied by Müller (2013), who shows that under misspecification it has lower asymptotic frequentist risk than the posterior of the (wrong) parametric likelihood [V: abstract, Econometrica 81(5), 1805-1849, DOI 10.3982/ECTA9097; full text not read, U for anything beyond the abstract].

### SB1.2 Alpha

Alpha is not shrunk and the shrunk view reports no alpha. Reasons: (a) a prior on alpha is a claim about expected abnormal returns, which this product does not make; (b) with a flat prior on alpha and the joint normal approximation, the conditional posterior mean of alpha would shift by `V_ab V_bb^-1 (b_post - b)`, an "alpha implied by shrunk betas" that users would read as a second alpha estimate. The M3 alpha stays the only alpha.

### SB1.3 Consequences of the approximation (stated in the methods drawer)

1. It is not the posterior of any generative model. It is valid only where `b` is approximately normal with covariance `V`; the report minimum `n >= 504` (M0.7) is kept unchanged.
2. Because `V` is the HAC covariance, the data count as **less** informative when residuals are serially correlated. For SPY the HAC/OLS standard-error ratio is 3.0 for Mkt-RF and 1.6-2.3 for the style betas over 1993-2026, and 4.1 for Mkt-RF over the last 504 rows [V, SB8.1]. An iid likelihood would under-shrink and give credible intervals that are too narrow.
3. `V` is itself estimated. In short samples the Bartlett estimator is biased downward (test-oracle T40 allows 0.01 for this), so shrinkage is slightly too weak and intervals slightly too narrow. Simulation with serially correlated errors (SB8.3): credible-interval coverage 0.92-0.94 with HAC `V` against 0.86-0.91 with the OLS `V` [V].
4. The full matrix `V` is used. With correlated estimates (collinear factors, VIF, M3.4) a coefficient can move **away** from its own prior centre because a correlated coefficient was pulled (RDDT SMB: OLS 0.309, posterior 0.326, SB8.2 [V]). The tooltip says so.

---

## SB2. The prior

### SB2.1 Centre: the market portfolio's betas (default)

`m0 = (1, 0, 0, 0, 0)` (Mkt-RF, SMB, HML, RMW, CMA).

Justification. Regressing Mkt-RF on the five factors gives exactly these betas, and betas are linear in portfolio weights, so the value-weighted average stock of the factor universe has these betas. The centre is therefore "a stock that behaves like the market". [V for the algebra; U that the CRSP universe of the Mkt factor equals the value-weighted universe of the user's tickers.] It is not the equal-weighted average stock: equal-weighted cross-sections tilt small (positive SMB). The 49 industry portfolios average SMB 0.26 and the 75 size-sorted portfolios average SMB 0.62 over the last 2520 rows [V, SB8.4]. The centre is fixed, not estimated, so it uses no data and cannot look ahead.

### SB2.2 Strength: method-of-moments dispersion from public Ken French cross-sections

`tau` is not tuned on the ticker's result. It is the dispersion of true betas around `m0` in public, reproducible cross-sections of daily portfolios from the same library.

Daily portfolio files that exist on the library page (P1 of `docs/datasets.md`), verified on 2026-11-18 from the `href="ftp/..."` links [V]: `5/10/12/17/30/38/48/49_Industry_Portfolios_daily_CSV.zip`; `25_Portfolios_5x5_Daily_CSV.zip` (ME x BE/ME); `25_Portfolios_ME_OP_5x5_daily_CSV.zip`; `25_Portfolios_ME_INV_5x5_daily_CSV.zip`; `25_Portfolios_BEME_OP_5x5_daily`, `25_Portfolios_BEME_INV_5x5_daily`, `25_Portfolios_OP_INV_5x5_daily`; `100_Portfolios_10x10_Daily`, `100_Portfolios_ME_OP_10x10_daily`, `100_Portfolios_ME_INV_10x10_daily`; `6_Portfolios_2x3_daily` (and ME_OP, ME_INV); `Portfolios_Formed_on_ME/BE-ME/OP/INV_Daily`; momentum and reversal sorts; regional equivalents. All carry a value-weighted and an equal-weighted block; missing cells are `-99.99` or `-999`.

Files used (downloaded 2026-11-18, all `Last-Modified` 2026-10-27, created from the 202609 CRSP database) [V]:

| Cross-section | File | SHA-256 (prefix) | Block | Portfolios |
| --- | --- | --- | --- | --- |
| A: 49 industries | `49_Industry_Portfolios_daily_CSV.zip` | `b9d36d57...` | Average Value Weighted Returns -- Daily | 49 (from 1926; some `-99.99` before 1970) |
| B: 75 size-characteristic | `25_Portfolios_5x5_Daily_CSV.zip`, `25_Portfolios_ME_OP_5x5_daily_CSV.zip`, `25_Portfolios_ME_INV_5x5_daily_CSV.zip` | `820936bd...`, `1b588736...`, `b4a29993...` | Average Value Weighted Returns -- Daily | 25 + 25 + 25 (OP and INV from 1963-07-01) |

Estimator (per cross-section `c` in {A, B}, per factor `j`):

1. Window: the 2520 French rows ending at `T_end` (the last date of the ticker's analysis sample). Portfolios with any missing value in the window are dropped and counted.
2. For each portfolio `i`: excess return (portfolio minus French `RF`), OLS on the five factors with intercept, HAC per M0.5 (`L(2520) = 8`). Keep `b_ij` and `V_i,jj`.
3. `tau_c,j^2 = mean_i (b_ij - m0_j)^2 - mean_i V_i,jj` (second moment around the prior centre minus average sampling variance; Vasicek-style empirical Bayes; Vasicek 1973, Journal of Finance 28(5), 1233-1239 [V: bibliographic record; the paper's text not read, U for its details]).
4. Default: `tau_j = max(tau_A,j, tau_B,j, 0.05)`. The maximum is the conservative choice (weaker shrinkage); the floor 0.05 prevents a near-dogmatic prior if a cross-section is degenerate. The rule was fixed before computing (SB12, line T-20261118-801).

Current values (window 2016-09-21 .. 2026-09-30, 2520 rows) [V]:

| | Mkt-RF | SMB | HML | RMW | CMA |
| --- | --- | --- | --- | --- | --- |
| A, 49 industries (49 portfolios) | 0.209 | 0.408 | 0.341 | 0.281 | 0.254 |
| B, 75 size-characteristic (75) | 0.063 | 0.764 | 0.329 | 0.329 | 0.221 |
| **Default `tau` (max)** | **0.209** | **0.764** | **0.341** | **0.329** | **0.254** |

Stability across decades (each 10-year window, A / B) [V]:

| Window | Mkt-RF | SMB | HML | RMW | CMA |
| --- | --- | --- | --- | --- | --- |
| 1966-1975 | 0.22 / 0.09 | 0.46 / 0.72 | 0.22 / 0.25 | 0.33 / 0.20 | 0.24 / 0.20 |
| 1976-1985 | 0.17 / 0.10 | 0.44 / 0.68 | 0.30 / 0.23 | 0.45 / 0.26 | 0.17 / 0.20 |
| 1986-1995 | 0.18 / 0.09 | 0.37 / 0.67 | 0.42 / 0.26 | 0.33 / 0.25 | 0.49 / 0.24 |
| 1996-2005 | 0.20 / 0.12 | 0.34 / 0.68 | 0.38 / 0.36 | 0.44 / 0.29 | 0.34 / 0.23 |
| 2006-2015 | 0.23 / 0.05 | 0.37 / 0.69 | 0.33 / 0.27 | 0.31 / 0.27 | 0.44 / 0.23 |
| 2016-2026-09 | 0.21 / 0.06 | 0.40 / 0.76 | 0.34 / 0.33 | 0.28 / 0.33 | 0.26 / 0.22 |

The default (max) moves within about 0.17-0.23 (Mkt-RF), 0.67-0.76 (SMB), 0.25-0.42 (HML), 0.26-0.45 (RMW), 0.20-0.49 (CMA) across decades. That is stable enough to use, but not constant, so it is recomputed per report (SB2.3) instead of frozen.

### SB2.3 Point-in-time and vintage

- The prior for a report ending at `T_end` uses only French portfolio rows dated `<= T_end` (SB2.2 step 1). Perturbing portfolio rows after `T_end` cannot change it (TSB15).
- The portfolio files are new datasets: each needs a `DatasetSpec` in the registry of `docs/methodology-datasets.md` D2, the shared parser D3 (the portfolio files have several blocks; only the value-weighted block is read), and a vintage record D5 (SHA-256, CRSP stamp, `Last-Modified`). The prior object carries those stamps.
- One vintage per dataset (protocol section 8). The portfolio vintage must be the same CRSP stamp as the factor vintage (both "202609" today [V]); if they differ, status `failed` with reason `prior_vintage_mismatch`.

### SB2.4 Known weakness: portfolio dispersion understates single-stock dispersion

A portfolio's beta is an average of its members' betas, so the dispersion of portfolio betas is smaller than the dispersion of single-stock betas. Using it for single stocks makes the prior **too strong**. Simulation with true dispersion twice the assumed `tau` (SB8.3): shrunk MSE is 11-35% **worse** than OLS per factor (total +19%), and 95% credible intervals cover only 0.77-0.91 [V]. How large the single-stock dispersion actually is cannot be verified without a stock universe [U]. This is the main reason for SD3 (OLS stays primary) and for the peer prior (SB2.5). Open question Q1 in SB10.4.

### SB2.5 How the peer prior plugs in later

When the peer feature (ROADMAP "Next") exists, a `PeerPrior` replaces the reference prior through the same interface:

- Peers: the peer list of that feature, excluding the ticker itself. Each peer is regressed on the **same rows** as the ticker's regression (same window, same `S` dates; a peer missing any of those rows is dropped and counted), so the prior uses no row the ticker's estimate does not use and stays point-in-time.
- `m0_j = mean_p b_pj`; `tau_j^2 = var_p(b_pj) (ddof 1) - mean_p V_p,jj`, floored at `0.05^2` (Vasicek / empirical Bayes; Efron-Morris type) [U: no peer data available to test].
- Requires at least 10 peers with regression status `ok`; otherwise fall back to the reference prior with `prior.fallback_reason = "too_few_peers"`.
- Schema: `prior.source` in `{"reference_ff_portfolios_v1", "peer_empirical_bayes_v1"}`; everything else unchanged.

---

## SB3. Posterior, credible intervals, prior weight

`V_post = (V^-1 + T0^-1)^-1`, `b_post = V_post (V^-1 b + T0^-1 m0)`, `S_w = V_post T0^-1`.
Identities (TSB01-TSB03): `b_post = (I - S_w) b + S_w m0`; `V_post V^-1 + S_w = I`; `tau -> infinity` gives `b_post = b`, `V_post = V` (flat prior: the credible interval equals the HAC CI95 of M3.3 exactly); `tau -> 0` gives `b_post = m0`.

- Credible interval: `b_post,j +/- 1.959964 sqrt(V_post[j, j])`, labelled "95% credible interval under the stated prior".
- `pull_j = S_w[j, j]`, in `[0, 1]` for a diagonal `V`; with correlated estimates it can be slightly outside, so it is displayed clipped to `[0, 1]` and the unclipped value is in the payload.
- Numerical method: solve with `numpy.linalg.solve` on the symmetric positive definite matrices; reject (`failed`, reason `singular_covariance`) if the condition number of `V` exceeds `1e12` (inherits the M3 rank guard of validation finding F3).

No p-value, no "reliable" tag and no BH family is attached to shrunk betas (SD5). A credible interval excluding 0 is not a significance claim and is never worded as one.

---

## SB4. Interaction with HAC (summary for reviewers)

| Choice | Consequence | Evidence |
| --- | --- | --- |
| `V` = HAC block, `L(m)` of that regression | Shrinkage reflects the real (autocorrelation-adjusted) uncertainty | SPY: HAC/OLS se ratio 1.6-3.0 (full), up to 4.1 (last 504) [V] |
| Normal approximation of `b` | Requires `n >= 504` | report minimum unchanged |
| HAC estimated with error, biased low in short samples | Slight under-shrinkage and under-coverage | serial DGP: coverage 0.92-0.94 (HAC `V`) vs 0.86-0.91 (OLS `V`) [V] |
| Sandwich posterior, not a full-likelihood posterior | Not a generative-model posterior; justified by Müller (2013) | abstract [V] |
| Shrinkage of the latest rolling window uses `L(W_p)` | Same rule as M4 | - |

---

## SB5. Power: minimum detectable effect and data needed

Per style factor `j`, from the same regression's HAC standard error `se_j`:

- `MDE_j = k80 * se_j`, `k80 = 3.41745` (`a = 0.01`, the BH-of-5 worst case of protocol Appendix B, power 80%, normal approximation). For a single test (`a = 0.05`), `k = 2.80159` [V].
- Data needed to detect `delta` (default `delta = 0.05`): `n_req = n * (k80 * se_j / delta)^2` rows; additional years `= max(0, n_req - n) / 252`.
- Assumption (stated in the tooltip): `se` shrinks like `1/sqrt(n)`, that is, factor variances, residual variance and autocorrelation stay as they were in the sample. With trending residual volatility the statement is approximate.
- Templates:
  - "With {years:.1f} years of data, a {Factor} beta of {MDE:.2f} or larger would be detected with 80% power (after correcting for testing 5 betas)."
  - If additional years `<= 50`: "Detecting a {Factor} beta of 0.05 would take about {extra:.1f} more years of similar data." If `0`: "A beta of 0.05 is already detectable." If `> 50`: "A {Factor} beta of 0.05 is not detectable for this stock with daily data (it would take more than 50 years)."
- Market beta: the MDE is shown in the drawer only; the "years" sentence is omitted (the report tests `beta = 0`, which is always rejected for equities).
- The MDE describes the **OLS test** that drives the tags; it says nothing about the shrunk estimate.
- Hand example (TSB10): `n = 504`, `se = 0.02` gives `MDE = 0.06835`, `n_req = 941.79`, extra `1.737` years [V].

---

## SB6. Showing shrunk and unshrunk betas together

Design rules (SD3):

1. **OLS is primary.** The beta panel (M3.3), tags, attribution, risk, drift and all other panels show OLS. Shrunk betas appear as a secondary marker on the same row (hollow diamond), with the credible interval as a thin line, never as a bar.
2. A row only shows the marker when `pull_j >= 0.05`. When every `pull_j < 0.05`, the panel shows one line instead: "Shrinkage moves no beta by a visible amount: this sample is long enough." (SPY full sample: max pull 0.002 [V].)
3. Colour and words: the OLS bar keeps its reliable/noise styling; the shrunk marker is neutral grey and is called "pulled toward typical", never "true", "adjusted" or "corrected".
4. Sorting and ranking text (M7 disagreement sentence, dominance) never use shrunk values.
5. Exports: the JSON carries both; CSV export columns are `beta_ols_*` and `beta_shrunk_*` (never an unnamed `beta`).

Labels (proposed keys for M0.9):

- **L-SHRINK** (panel footnote): "Pulled toward typical: each beta is moved toward the beta of the market portfolio (Mkt-RF 1, others 0), more when it is noisy. How far depends on how much betas differ across Ken French industry and size portfolios. A model-based view, not a test; the bars show the estimates from this stock's data."
- **L-SHRINK-PRIOR** (tooltip): "Prior: centre {m0}, spread {tau} (from {n_A} industry and {n_B} size portfolios, {start} to {end}). Portfolios differ less than single stocks, so this pull may be too strong for unusual stocks."
- **L-CRED**: "95% credible interval under the stated prior; based on the HAC (Newey-West) uncertainty of the estimate."
- **L-CORR-MOVE** (shown when `sign(b_post,j - b_j) != sign(m0_j - b_j)`): "Moved away from its typical value because it is estimated jointly with correlated factors."
- **L-MDE**: the SB5 templates.

---

## SB7. Status values, minimum samples, schema

### SB7.1 Status (M0.7 values)

| Condition | Status | Reason |
| --- | --- | --- |
| Underlying regression not `ok` | same status as the regression | inherited |
| Portfolio files unavailable (download failed, never cached) | `failed` | `prior_unavailable` |
| Fewer than 40 usable portfolios in either cross-section, or fewer than 2520 French rows ending at `T_end` | `insufficient_data` | `prior_cross_section_too_small` |
| Portfolio vintage differs from factor vintage | `failed` | `prior_vintage_mismatch` |
| `cond(V) > 1e12` | `failed` | `singular_covariance` |
| Otherwise | `ok` | - |

Minimum samples: the regression's own minimum (`n >= 504` for full sample; `W_p` rows for the latest window, which always holds when the report exists). The French window needs 2520 rows ending at `T_end` (true for any `T_end >= 1973-08`).

### SB7.2 Schema (`report/schema.py`, all new models optional sub-models per the schema v3 contract)

```text
ShrinkagePrior
  source: Literal["reference_ff_portfolios_v1", "peer_empirical_bayes_v1"]
  centre: list[float]            # 5, canonical factor order
  tau: list[float]               # 5
  tau_by_cross_section: dict[str, list[float]] | None   # {"industry49": [...], "size_char75": [...]}
  n_portfolios: dict[str, int]   # usable portfolios per cross-section
  window_start: date; window_end: date; window_rows: int
  datasets: list[DatasetStamp]   # key, crsp_stamp, sha256, last_modified
  fallback_reason: str | None

ShrunkBeta (one per factor)
  factor: Literal["mkt_rf","smb","hml","rmw","cma"]
  beta_ols: float; se_hac: float
  beta_shrunk: float | None; sd_post: float | None
  cred95_low: float | None; cred95_high: float | None
  pull: float | None             # S_w[j,j], unclipped
  moved_away: bool | None        # L-CORR-MOVE condition

PowerStatement (one per factor)
  factor; mde80: float | None; alpha_level: float   # 0.01
  delta: float                   # 0.05
  extra_years_to_detect_delta: float | None
  text: str | None

ShrunkBetas
  status; reason; sample: SampleInfo; scope: Literal["full_sample", "latest_window"]
  window: int | None; hac_lags: int
  prior: ShrinkagePrior | None
  betas: list[ShrunkBeta]; power: list[PowerStatement]
  labels: list[str]              # L-SHRINK, L-SHRINK-PRIOR, L-CRED, ...
```

Numeric fields are `null` whenever `status != "ok"`; NaN and infinity are never serialised (M14).

---

## SB8. Demonstrations [V]

Inputs: French US daily 5 factors (`F-F_Research_Data_5_Factors_2x3_daily_CSV.zip`, SHA-256 `e5857722...`, identical to the repo cache, last date 2026-09-30); Yahoo via yfinance 1.8.0 `Ticker.history(period="max", auto_adjust=False, actions=True, repair=False)`, downloaded 2026-11-18; alignment per M2; HAC per M0.5. Environment: `uv run` resolves the project `.venv`, which runs Python 3.13.14 (not the 3.12 named in the project brief), numpy 2.5.5, scipy 1.18.1, pandas 3.1.1, statsmodels 0.15.0 [V].

### SB8.1 SPY (long history)

| | Mkt-RF | SMB | HML | RMW | CMA |
| --- | --- | --- | --- | --- | --- |
| Full sample 1993-02-01..2026-09-30, `n = 8474`, `L = 10`: OLS | 1.0093 | -0.1476 | 0.0071 | 0.0878 | 0.0607 |
| HAC se (OLS se) | 0.0066 (0.0022) | 0.0062 (0.0039) | 0.0087 (0.0038) | 0.0094 (0.0051) | 0.0112 (0.0064) |
| Shrunk | 1.0092 | -0.1475 | 0.0072 | 0.0876 | 0.0606 |
| pull | 0.001 | 0.000 | 0.001 | 0.001 | 0.002 |
| MDE80 (a = 0.01) | 0.023 | 0.021 | 0.030 | 0.032 | 0.038 |
| Last 504 rows 2024-09-26..2026-09-30, `L = 5`: OLS | 1.0116 | -0.0893 | 0.0075 | 0.0282 | 0.0236 |
| HAC se (OLS se) | 0.0195 (0.0047) | 0.0131 (0.0075) | 0.0120 (0.0068) | 0.0140 (0.0070) | 0.0123 (0.0085) |
| Shrunk | 1.0114 | -0.0893 | 0.0075 | 0.0281 | 0.0235 |
| pull | 0.009 | 0.000 | 0.001 | 0.002 | 0.002 |
| MDE80 (a = 0.01) | 0.067 | 0.045 | 0.041 | 0.048 | 0.042 |

Reading: for SPY shrinkage is invisible (max pull 0.9%); the panel would show the one-line message of SB6 rule 2. Even on 504 rows, style betas of 0.04-0.05 are detectable, because SPY's residual volatility is small (1.5%/yr over the last 504 rows). The full-sample SPY numbers match the validation report (`docs/validation/spy-slice-validation.md` section 4) to the printed digits.

### SB8.2 RDDT (short history)

Choice: RDDT (Reddit, Inc.) listed 2024-03-21; it was the pre-registered short-history ticker (fewer than 3 years, above the 504-row minimum). Sample 2024-03-22..2026-09-30, `n = 633`, `L = 6`, residual volatility 72.7%/yr.

| | Mkt-RF | SMB | HML | RMW | CMA |
| --- | --- | --- | --- | --- | --- |
| OLS | 1.484 | 0.309 | -1.015 | -0.828 | -0.155 |
| HAC se | 0.222 | 0.263 | 0.292 | 0.358 | 0.543 |
| HAC z | 6.68 | 1.18 | -3.48 | -2.31 | -0.29 |
| Shrunk | 1.327 | 0.326 | -0.793 | -0.571 | -0.120 |
| Posterior sd | 0.149 | 0.235 | 0.208 | 0.233 | 0.228 |
| 95% credible interval | [1.035, 1.620] | [-0.135, 0.787] | [-1.200, -0.386] | [-1.028, -0.114] | [-0.567, 0.326] |
| pull (HAC `V`) | 0.51 | 0.10 | 0.37 | 0.50 | 0.81 |
| pull if the OLS `V` were used | 0.48 | 0.13 | 0.41 | 0.46 | 0.68 |
| MDE80 (a = 0.01) | 0.76 | 0.90 | 1.00 | 1.22 | 1.86 |
| Extra years to detect 0.05 | (not shown) | 807 | 998 | 1500 | 3457 |

Reading: RDDT's style betas are so noisy that the prior moves them by 10-81%. SMB moves **up**, away from its centre 0, because it is estimated jointly with the HML and RMW betas, which are pulled hard (L-CORR-MOVE fires). The power sentence would read: "With 2.5 years of data, an SMB beta of 0.90 or larger would be detected with 80% power ...; an SMB beta of 0.05 is not detectable for this stock with daily data."

### SB8.3 Simulations with known betas (MSE of shrunk vs OLS)

DGP-SB: DGP-A factors of `docs/test-oracle.md` 0.4 (iid normal, same means, sds, correlations), `alpha = 0.0002`, iid normal residuals with volatility 30%/yr (`0.30 / sqrt(252)` daily), `R = 4000` simulated stocks per row, true betas drawn per stock from `N(m0 + shift, diag((c * tau)^2))` with the default `tau` above unless fixed. The estimator always uses `m0` and the default `tau`. Seed `20261118 + 950`. MSE ratio = shrunk MSE / OLS MSE (below 1 = shrinkage helps).

| Case | n | MSE ratio Mkt, SMB, HML, RMW, CMA | Total MSE OLS -> shrunk | Credible coverage (95%) |
| --- | --- | --- | --- | --- |
| Prior correct (`c = 1`) | 252 | 0.73, 0.88, 0.47, 0.48, 0.28 | 0.405 -> 0.184 | 0.936-0.943 |
| Prior correct | 504 | 0.83, 0.92, 0.61, 0.65, 0.45 | 0.197 -> 0.119 | 0.936-0.946 |
| Prior correct | 756 | 0.86, 0.96, 0.69, 0.76, 0.55 | 0.131 -> 0.091 | 0.937-0.947 |
| Prior correct | 2520 | 0.94, 0.98, 0.86, 0.89, 0.79 | 0.039 -> 0.034 | 0.942-0.951 |
| True spread 2x the prior (`c = 2`) | 504 | **1.23, 1.16, 1.15, 1.35, 1.11** | 0.200 -> **0.238** | **0.77-0.91** |
| True spread half the prior (`c = 0.5`) | 504 | 0.73, 0.88, 0.49, 0.49, 0.26 | 0.195 -> 0.090 | 0.943-0.986 |
| True centre SMB +0.5 | 504 | 0.83, 0.94, 0.60, 0.67, 0.43 | 0.198 -> 0.119 | 0.937-0.948 |
| Fixed unusual stock (1.3, 1.0, -0.8, 0, 0) | 504 | 0.77, 0.91, 0.95, 0.48, 0.29 | 0.201 -> 0.111 | HML 0.888, others 0.95-0.98 |
| Fixed reference stock `m0` | 504 | 0.69, 0.85, 0.43, 0.44, 0.21 | 0.198 -> 0.081 | 0.954-0.993 |
| Serially correlated (DGP-B style: factors and residuals AR(1) 0.5), prior correct, `R = 2000` | 504 | 0.75, 0.89, 0.52, 0.53, 0.34 | 0.329 -> 0.166 | HAC `V`: 0.920-0.941; OLS `V`: 0.864-0.908 |

What this shows:

- When the prior spread is right or too wide, shrinkage roughly halves the total MSE at 1-2 years of data, and the gain fades with more data (only about 14% at 10 years).
- When true betas are twice as dispersed as the prior assumes, shrinkage is **worse than OLS** for every factor and its intervals under-cover badly. SB2.4 explains why this is plausible for single stocks.
- A wrong centre for one factor (SMB +0.5, about 0.65 prior sd) costs little.
- For one unusual stock, the pulled coefficient (HML -0.8, 2.3 prior sd from 0) loses coverage (0.888) but still has lower MSE at this noise level; at lower noise or more extreme betas this reverses (Bayes risk is an average over stocks, not a promise for each one).
- HAC `V` keeps intervals close to nominal under serial correlation; OLS `V` does not.

### SB8.4 Cross-sectional means (why the centre is not estimated from these portfolios)

Mean betas over the last 2520 rows [V]: 49 industries (equal-weighted across portfolios) 0.946, 0.259, 0.143, 0.082, 0.094; 75 size-characteristic portfolios 0.994, 0.619, 0.161, -0.090, 0.033. Both are equal-weighted across portfolios and so tilt toward small firms. Using either as the centre would pull every large-cap stock toward a small-cap SMB loading, which is why the centre is `m0` and these cross-sections set only the spread.

---

## SB9. Decisions

- **SD1 Reference prior now, peer prior later.** Default `m0 = (1,0,0,0,0)`, `tau = max(tau_A, tau_B, 0.05)` from the 2520 French rows ending at `T_end`. The peer prior replaces it through `ShrinkagePrior` (SB2.5) when the peer feature ships.
- **SD2 Sandwich (HAC) likelihood.** Justified in SB1 and SB4.
- **SD3 OLS stays primary.** The shrunk betas are a secondary, labelled view. Reason: SB2.4 and the `c = 2` simulation (shrinkage can hurt when the prior is too tight, and we cannot yet verify the right spread for single stocks).
- **SD4 Alpha not shrunk, no implied alpha.** SB1.2.
- **SD5 No test, no tag, no BH family** on shrunk betas.
- **SD6 Prior recomputed per report** (point-in-time), not frozen, because `tau` varies by decade (SB2.2).
- **SD7 Scope v1:** full sample and latest `W_p` window only. Shrinking every rolling stamp needs a prior per stamp (each from the 2520 French rows ending at that stamp) and is deferred.
- **SD8 g-prior rejected.** Zellner's g-prior with unit information (`g = n`) shrinks by `1/(1+n)`, about 0.2% at `n = 504`, which is invisible. Any other `g` is a tuning choice with no public anchor. It also shrinks all betas by the same fraction, ignoring that style betas are noisier.

---

## SB10. Proposals and open questions

### SB10.1 Deferred

Shrunk rolling series (SD7); shrinkage of regime betas (M10); hierarchical estimation of `tau` jointly with a stock universe.

### SB10.2 Dependencies

Dataset registry entries for the 4 portfolio files (D2 of `docs/methodology-datasets.md`); the schema v3 contract (ROADMAP).

### SB10.3 Proposed additions to `docs/methodology.md` (for the owner; not made here)

M0.9 labels L-SHRINK, L-SHRINK-PRIOR, L-CRED, L-CORR-MOVE, L-MDE; M0.7 rows for SB7.1; M14 schema mention; M15 constants (`delta = 0.05`, floor 0.05, 2520-row prior window, 40-portfolio minimum, pull display threshold 0.05).

### SB10.4 Open questions for the owner

1. **Prior spread for single stocks.** Portfolio dispersion understates single-stock dispersion (SB2.4), and the simulation shows the cost when the prior is too tight. Options: (a) ship as specified with the caveat; (b) inflate `tau` by a fixed factor (for example 2) until peers exist, which is a tuning choice we cannot verify today; (c) ship only the power statement now and the shrunk betas with the peer prior. Recommendation: (a) with the caveat, because the view is secondary and the `c = 0.5` case shows a conservative spread costs little.
2. **Download size.** The prior needs 4 extra files (about 13.4 MB zipped, 76 MB unzipped [V]) per vintage. Acceptable?
3. **`delta = 0.05`** for the "years to detect" sentence: keep fixed, or let the user choose (it would be a fourth tunable for the regression panel; M15 allows none today)?

---

## SB11. Test oracle (TSB01-TSB20)

Conventions as in `docs/test-oracle.md` section 0 (seed `20261118 + k` for test `k`, here `k = 700 + NN` for TSB`NN`; tolerances from standard errors; markers `slow`, `live`). Target module: `analytics/shrinkage.py` unless stated; the prior loader lives in `data/` (pure parser) and `analytics/shrinkage_prior.py` (pure estimator).

### Identities (deterministic)

- **TSB01 Flat-prior limit.** Random SPD `V` (5x5, eigenvalues in `[1e-4, 1e-1]`), random `b`. With `tau = 1e8` everywhere: `b_post == b` (1e-10 absolute) and `V_post == V` (1e-10 relative). The credible interval equals the HAC CI95 of M3.3 to 1e-10.
- **TSB02 Dogmatic limit.** `tau = 1e-8`: `|b_post - m0| <= 1e-6`, `V_post <= 1e-15` elementwise.
- **TSB03 Weight identities.** For random inputs: `b_post == (I - S_w) b + S_w m0` and `V_post V^-1 + S_w == I` (1e-12).
- **TSB04 Scalar hand example.** One factor with `V = 0.04`, `tau^2 = 0.04`, `b = 0.6`, `m0 = 0`: `pull = 0.5`, `b_post = 0.3`, `V_post = 0.02` (1e-15). Diagonal 5x5 version: each coordinate equals the scalar formula `b_post = (tau^2 b + V m0)/(tau^2 + V)` (1e-12).
- **TSB05 Correlated move away.** `V = [[0.04, 0.036], [0.036, 0.04]]` (correlation 0.9), `tau = (10, 0.1)` (first coefficient nearly free), `b = (0.5, 0.5)`, `m0 = (0, 0)`. Assert the first posterior coefficient moves away from 0 (`b_post[0] > 0.5`) and `moved_away` is true for it, false for the second. This pins L-CORR-MOVE.
- **TSB06 HAC block.** On DGP-A, `V` passed to the posterior equals the `[1:, 1:]` block of the reference call of M0.5 with `L(n)` (1e-10 relative); for the latest window it uses `L(W_p)`.

### Prior estimation

- **TSB07 Method of moments on a synthetic cross-section.** 200 synthetic portfolios over 2520 rows of DGP-A factors; true betas drawn from `N(m0, diag(tau_true^2))`, `tau_true = (0.2, 0.5, 0.3, 0.3, 0.25)`; residual sd 0.004 daily (portfolio-like). (a) Recovery: `|tau_hat_j^2 - tau_true_j^2| <= 4 * sqrt(2 / 200) * (tau_true_j^2 + mean_i V_i,jj)` for each `j` (the standard error of a sample second moment of `N` normal deviations with variance `s^2` is `sqrt(2/N) s^2`; here `s^2 = tau^2 + V`). (b) Algebra: `tau_hat_j^2` equals `mean_i (b_ij - m0_j)^2 - mean_i V_i,jj` computed directly from the per-portfolio fits (1e-12).
- **TSB08 Max rule and floor.** Pure function on raw squared spreads: `tau_A^2 = (0.04, 0.16, 0.09, 0.0004, 0.01)`, `tau_B^2 = (0.0036, 0.64, 0.09, -0.001, 0.0001)`. Result `tau = (0.2, 0.8, 0.3, 0.05, 0.1)`: a negative raw value maps to 0 before the maximum, and the RMW maximum 0.02 is raised to the floor 0.05. Exact.
- **TSB09 Missing portfolios.** A portfolio column with one `-99.99` in the window is excluded and counted in `n_portfolios`; a column with `-99.99` only before the window is kept. Fewer than 40 usable portfolios gives `insufficient_data` with reason `prior_cross_section_too_small`.
- **TSB10 MDE and years.** `n = 504`, `se = 0.02`: `MDE = 0.0683490` (1e-6), `n_req = 941.792` (1e-3), extra years `1.7373` (1e-4). `se = 0.001, n = 2520`: extra years `0` and the text "already detectable". `se = 0.9, n = 633`: text "not detectable ... more than 50 years". Market factor: no years sentence. `k80 = norm.ppf(0.995) + norm.ppf(0.8)` (1e-12).
- **TSB11 Block parsing.** The portfolio parser reads only the block titled "Average Value Weighted Returns -- Daily" (fixture with 3 blocks: VW, EW, number of firms); EW values never enter. Latin-1 decoding (the ME_OP file contains a non-ASCII apostrophe in its preamble [V]).

### Simulations (`slow`)

- **TSB12 Bayes risk, prior correct.** DGP-SB, `n = 504`, `R = 4000`. Assert total shrunk MSE `< 0.8 *` total OLS MSE (observed 0.61, [V]). Margin: the MC standard error of the ratio is below 0.02 at `R = 4000` (per-factor MSE relative se `sqrt(2/R) = 0.022`); 0.8 is more than 8 standard errors above the observed value.
- **TSB13 Credible coverage, prior correct.** Same run: per-factor coverage in `[0.925, 0.965]` (binomial se 0.0034 at R = 4000, 3.5 se = 0.012 around 0.95, plus 0.01 downward allowance for Bartlett bias as in T40; observed 0.936-0.946 [V]).
- **TSB14 Prior too tight is detected as harmful.** `c = 2`: total shrunk MSE `>` total OLS MSE (observed ratio 1.19 [V]). Documents SB2.4; if a code change makes this test fail, the documentation of SD3 must be revisited, not the test loosened.
- **TSB15 HAC versus OLS covariance under serial correlation.** Serial DGP (`R = 2000`, `n = 504`): mean credible coverage over the five factors with HAC `V` exceeds that with OLS `V` by at least 0.02 (observed 0.930 vs 0.891 [V]); HAC coverage `>= 0.90`.

### No look-ahead and isolation

- **TSB16 Prior perturbation after `T_end`.** Replace every French portfolio and factor row dated after `T_end` with new random values: `tau`, `n_portfolios`, `b_post`, `V_post` unchanged (1e-12). Replace a row dated `<= T_end` inside the 2520-row window: `tau` changes (proves the test bites).
- **TSB17 Truncation.** Prior computed from files truncated at `T_end` equals the prior from full files (exact).
- **TSB18 OLS untouched.** A full DGP-A report with and without the shrinkage module: every M3-M10 number bitwise identical; tags identical; no shrunk value reaches attribution, risk or dominance (static check: `analytics/attribution.py`, `dominance.py`, `drift.py` do not import `shrinkage`).
- **TSB19 Status and schema.** Missing portfolio file gives `failed / prior_unavailable` with null numbers; vintage mismatch gives `failed / prior_vintage_mismatch`; payload serialises with `allow_nan=False`; every model has `status`, `reason`, `sample`.

### Live smoke (`live`, non-blocking)

- **TSB20 SPY and a recent listing.** SPY from 2010-01-04: max `pull < 0.02` for all factors. A ticker listed 2-3 years before factor `last_date` (recorded in the fixture when written): at least one style factor with `pull > 0.2`. Portfolio files parse with 49 and 75 usable portfolios on the last 2520 rows.

---

## SB12. Registry entries (demonstrations run for this document)

Format: protocol Appendix A. Entries are listed here because this task writes documents only; they must be appended to `docs/registry/tests.jsonl` (with fresh `test_id`s if these collide) in the change that adds this spec. The pre-registration note (tickers, hypotheses, prior rule) was written in the scratchpad before any data were downloaded; it was not committed, so the status of every line is `run` with that fact in `notes`. Common fields: `created_at` 2026-11-18; `code_version` none (scratch scripts `sb_tau.py`, `sb_demo.py`); datasets `us_ff5_daily` stamp 202609 SHA-256 `e58577223032aa45071a46686f7068900c371b516c9eb04e28e974c34264f84f`, `ind49_daily` `b9d36d571e968d71f7b03207e7fed6398554f953719b8c1bf3ee3ad8d00e7520`, `me_bm25_daily` `820936bd308756c3f66afbb211c9a2a929fed5f8fcf6253fc8a1dfbe2f7c7276`, `me_op25_daily` `1b588736e17711e11f7b50487a8a8ad88ae8793a54df072e85b067faaa3d780e`, `me_inv25_daily` `b4a299935b890e47310ccca52dd5bdde82b38414774526970a95f7494705c151`; split role `in_sample_only` (descriptive demonstrations; no confirmatory claim is made).

| test_id | hypothesis_id | Spec | Result | Notes |
| --- | --- | --- | --- | --- |
| T-20261118-801 | H-801 | Prior rule fixed before computing: `m0 = (1,0,0,0,0)`, `tau = max(A, B, 0.05)`, MoM, HAC L(2520)=8, window last 2520 rows | `tau = (0.209, 0.764, 0.341, 0.329, 0.254)` | descriptive |
| T-20261118-802..813 | H-802 | `tau` by 10-year window, 6 windows x 2 cross-sections (12 lines) | SB2.2 table | stability check, descriptive |
| T-20261118-814..815 | H-802 | `tau` on the last 504 rows (2024-09-26..2026-09-30), A and B | A: 0.367, 0.430, 0.314, 0.421, 0.312; B: 0.086, 0.781, 0.346, 0.345, 0.260 | looked at, not used |
| T-20261118-816 | H-803 | SPY full sample shrinkage and MDE, n 8474, 1993-02-01..2026-09-30 | SB8.1 | descriptive |
| T-20261118-817 | H-803 | SPY last 504 rows | SB8.1 | descriptive |
| T-20261118-818 | H-803 | RDDT full sample, n 633, 2024-03-22..2026-09-30 | SB8.2 | descriptive |
| T-20261118-819 | H-803 | Same three regressions with OLS (non-HAC) `V` in the posterior | pulls in SB8.2 / SB8.1 | comparison for SB4 |
| T-20261118-820..823 | H-801S | Simulation, prior correct, n = 252, 504, 756, 2520 (R = 4000 each), seed 20261118+950 | SB8.3 | MSE vs OLS |
| T-20261118-824..828 | H-801S | Misspecified: `c = 2`, `c = 0.5`, centre SMB +0.5, fixed unusual stock, fixed reference stock (n = 504, R = 4000) | SB8.3 | |
| T-20261118-829 | H-801S | Serially correlated DGP, n = 504, R = 2000, HAC vs OLS `V` | SB8.3 | |

`H-801`: "A Vasicek-style prior with spread from public French portfolio cross-sections gives stable `tau` across decades" (descriptive). `H-801S`: "Shrunk betas have lower MSE than OLS when the prior is correct and worse when the prior is twice too tight" (simulation; no p-value). `H-802`: stability windows. `H-803`: real-ticker demonstrations (descriptive; no family, no claim of significance).

Sources checked on 2026-11-18: Ken French Data Library page <https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html> (daily file list, `Last-Modified` 2026-10-27); Müller (2013) record <https://econpapers.repec.org/RePEc:ecm:emetrp:v:81:y:2013:i:5:p:1805-1849>; Vasicek (1973) record <https://econpapers.repec.org/RePEc:bla:jfinan:v:28:y:1973:i:5:p:1233-39>.
