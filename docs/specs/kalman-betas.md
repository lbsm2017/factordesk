# factordesk specification: Kalman-filter (time-varying) betas

Status: specification for a new feature, written 2026-11-18. Not yet implemented.
Audience: engineers implementing `backend/factordesk/analytics/kalman.py` (new) and the schema additions; reviewers checking the code against it.
Companions: `docs/methodology.md` (M0-M16, D1-D20, cited unchanged; M4 rolling betas is the benchmark), `docs/research-protocol.md` (checklist, Appendix A registry), `docs/test-oracle.md` (style, seed policy, T102-T104 look-ahead tests), `docs/validation/spy-slice-validation.md` (SPY timing noise, gate G1).
Section ids: KB0-KB12. Tests: TKB01-TKB24 (KB11). Registry entries: KB12.

Rule of precedence: every M0 convention applies unchanged (units, M0.2 stamping and look-ahead, M0.3 trailing windows for the rolling benchmark, M0.5 HAC for every OLS quantity, M0.7 statuses, M0.8 `SampleInfo`, M0.9 labels). The Kalman betas are an **additional** series. They do not replace the rolling betas of M4 in any downstream statistic (tilt/timing M6.3, dominance M8, drift M9 keep the rolling betas). Proposed additions to `docs/methodology.md` are in KB10.3; this document does not edit it.

Evidence markers: **[V]** = verified by a computation run for this document (scripts and outputs in the session scratchpad, folder `specs-kb-sb`, not part of the repo) or by a source checked on 2026-11-18; **[U]** = unverified.

---

## KB0. Scope, notation, classification

### KB0.1 What the feature shows

A daily series of the five betas (and a constant alpha) estimated by a Kalman filter: each day's estimate combines the previous day's estimate with that day's return, and how much weight the new day gets is learned from the stock's own past. Compared with a rolling window it has no hard window edge (an old day does not suddenly drop out), it is smoother when betas are stable, and it comes with a model-based uncertainty band. It is shown on the rolling-beta chart as one more line, never instead of the rolling lines.

### KB0.2 Notation (additions to M0.1)

| Symbol | Meaning |
| --- | --- |
| `theta_t = (alpha_t, beta_t')'` | State at row `t` (6-vector; `k = 6`) |
| `R` | Observation (residual) variance, decimal^2 per day |
| `Q` | State-noise covariance: `Q = blockdiag(0, lambda * R * M)` |
| `lambda` | Signal-to-noise hyperparameter (scalar, `>= 0`) |
| `M` | `Sigma_f^-1`, inverse sample covariance (`ddof = 1`) of the five factors over the vintage's estimation rows |
| `a_{t|t-1}`, `P_{t|t-1}` | Predicted state mean and covariance (uses rows `<= t-1`) |
| `a_{t|t}`, `P_{t|t}` | **Filtered** state mean and covariance (uses rows `<= t`) |
| `a_{t|n}`, `P_{t|n}` | Smoothed state (uses all rows, including rows after `t`) |
| `v_t`, `F_t` | Innovation `y_t - x_t' a_{t|t-1}` and its variance `x_t' P_{t|t-1} x_t + R` |
| `b` | Burn-in rows for initialisation, `b = 21` |
| `B0` | Training rows for the first hyperparameter estimate, `B0 = 504` |
| `h` | Re-estimation step, `h = 252` rows |
| `j` | Vintage index; vintage `j` is estimated on rows `1 .. m_j`, `m_j = B0 + j h` |
| `W_eq` | Equivalent rolling window, `2 / sqrt(lambda)` rows (KB2.5) |

All row indices are positions in `S` (M2), 1-based as in M0.3.

### KB0.3 Classification of every output

| Output | Class | Stamp |
| --- | --- | --- |
| Filtered betas, alpha, band at `t` (`a_{t|t}`, `P_{t|t}`) | point-in-time: rows `<= t`, hyperparameters from rows `<= t` (KB2.4) | `t` |
| Ex-ante (predicted) betas for explaining day `t` (`a_{t|t-1}`) | point-in-time: rows `<= t-1` | `t` |
| `lambda_j`, `R_j`, `W_eq,j` of vintage `j` | point-in-time: rows `1 .. m_j` | date of row `m_j` |
| Smoothed betas (retrospective view, KB4.2) | **uses later data**; never point-in-time | `T_end` (whole series) |
| Summary statistics of the filtered series (for example its time sd, KB9) | summary of a point-in-time series | `T_end` |

---

## KB1. Model

### KB1.1 State-space form

Observation: `y_t = x_t' theta_t + e_t`, `e_t ~ N(0, R)`, `x_t = (1, f_t')'`.
Transition: `theta_t = theta_{t-1} + eta_t`, `eta_t ~ N(0, Q)`, `Q = blockdiag(0, lambda R M)`.

- **Betas follow a random walk.** **Alpha is a constant state** (zero state noise): it is re-estimated every day from all rows so far, but the model does not let it drift.
- `Q` has one free parameter. Its shape `M = Sigma_f^-1` makes the drift of each beta proportional to how precisely the data measure it, exactly as a rolling window applies one common window length to all five betas. With this shape the filter behaves like an exponentially weighted regression with one effective window `W_eq = 2 / sqrt(lambda)` (KB2.5), which gives users a direct comparison with the 126- and 252-day lines.

### KB1.2 Decision: random walk, not a mean-reverting AR(1)

The AR(1) alternative is `beta_t - mu = phi (beta_{t-1} - mu) + eta_t`. Evidence and reasons:

1. **In-sample likelihood favours a fast-reverting AR(1), but for the wrong reason** [V]. On the 504 training rows, with `mu` fixed at the training OLS betas and `lambda` maximised on the grid for each `phi`, the log-likelihood rises steadily as `phi` falls: SPY 2378.16 (`phi = 1`) to 2386.99 (`phi = 0.9`), MSTR 588.96 to 609.55. A `phi = 0.9` model with large state noise is a random-coefficient model: it makes the residual variance proportional to `f_t' Q f_t`, so it fits the fact that residuals are larger on days with large factor moves (heteroskedasticity; the SPY validation found `corr(|e_t|, |Mkt_t|) = 0.25-0.32`). It also uses a `mu` fitted on the same rows. Neither is evidence that betas revert to a mean.
2. **A point-in-time AR(1) needs a mean from the past.** For a stock whose business changes (MSTR in 2020, KB9.2) any past mean is the wrong anchor, and the filter would keep pulling the estimate back to it.
3. **The random walk nests constant betas** (`lambda = 0`, the false-drift check KB7.1); the AR(1) nests them only at `phi = 0` with zero noise or at `mu` known.
4. At daily frequency the relevant `phi` is close to 1 (`phi = 0.99` has a half-life of 69 trading days), where the two models are hard to tell apart on 504 rows.

Out-of-sample comparison of a point-in-time AR(1) (mean from an expanding window) against the random walk was not run [U]; it is listed in KB10.4.

### KB1.3 Decision: one scalar `lambda`, not five separate state variances

A diagonal `Q` with five free variances was fitted with statsmodels `MLEModel` (L-BFGS-B, three starting points, log-variance bounds) [V]:

| Ticker, rows | Log-likelihood scalar / diagonal | LR (4 extra parameters) | AIC difference (diagonal minus scalar) | Diagonal estimates |
| --- | --- | --- | --- | --- |
| SPY, 504 training rows | 2378.17 / 2380.34 | 4.35 | +3.6 (scalar preferred) | Mkt variance at the lower bound (0), SMB at the upper bound |
| MSTR, 504 training rows | 588.96 / 590.60 | 3.27 | +4.7 (scalar preferred) | Mkt at the lower bound, SMB at the upper bound |
| SPY, all 8474 rows | 40415.5 / 40458.2 | 85.4 | -77.4 (diagonal preferred) | Mkt and HML at the upper bound |
| MSTR, all 7119 rows | 12540.4 / 12567.7 | 54.6 | -46.6 (diagonal preferred) | SMB and RMW at the upper bound |

On a training sample the diagonal model is not supported and its estimates sit on the bounds (weakly identified). On 30 years it fits better in-sample, but the estimates still hit the bounds, and full-sample estimation is not available point-in-time. The scalar model is the default; a diagonal `Q` is open question Q2 (KB10.4).

### KB1.4 Error distribution

Gaussian by default. A Student-t weighted update is specified as a variant and evaluated in KB6.

---

## KB2. Hyperparameters: estimation without look-ahead

### KB2.1 Concentrated likelihood

Run the filter in "scale form" (`R = 1`, so `Q = blockdiag(0, lambda M)`). With innovations `v_t` and scaled variances `F_t` over rows `t = b+1 .. m` (`N = m - b` rows):

- `R_hat(lambda) = (1/N) sum v_t^2 / F_t`
- `logL_c(lambda) = -N/2 (ln 2 pi + ln R_hat + 1) - 1/2 sum ln F_t`

The likelihood is conditional on the `b` burn-in rows (KB3).

### KB2.2 Maximisation

- Grid: `lambda in {0} U {10^-9, 10^-8.875, ..., 10^-2}` (57 log-spaced values, 8 per decade, plus 0). `10^-2` is `W_eq = 20` rows, `10^-9` is `W_eq = 63,246` rows.
- Take the grid maximiser. If it is an interior positive point, refine with one parabolic step in `log10 lambda` through the three neighbouring grid points, clipped to one grid step.
- `lambda = 0` is kept exactly when it is the maximiser (the filter is then expanding OLS, TKB01). No lower bound above 0.
- Rationale: one dimension, so a grid is robust (no local optimum is missed, the boundary is handled exactly) and the grid evaluates in one batched numpy pass (KB8).

### KB2.3 Training sample and first output

- Vintage 0 uses rows `1 .. B0`, `B0 = 504` (the report minimum, M0.7).
- The first filtered output is stamped at row `B0`. Rows `1 .. B0 - 1` are warm-up: no Kalman value is shown for them; in the series payload they are `null` (KB8.3). The M0.7 status values apply to the whole series object, not to single stamps.

### KB2.4 Re-estimation over time (expanding, every 252 rows)

- Vintages at rows `m_j = 504 + 252 j`, `j = 0, 1, ...` while `m_j <= n`. Vintage `j` estimates `lambda_j`, `R_j` and `M_j` on rows `1 .. m_j` only.
- **Each vintage re-runs the filter from row 1** with its own hyperparameters. Outputs stamped at rows `m_j .. m_{j+1} - 1` come from vintage `j`; the last vintage covers `m_J .. n`.
- The predicted state for row `t` (ex-ante beta) comes from the vintage valid at row `t - 1`. Because vintage `j+1` uses rows up to `m_{j+1}`, its prediction for row `m_{j+1} + 1` uses only earlier rows. Hence every output stamped `t` uses rows `<= t` only (TKB15-TKB16 verify it).
- Consequence (disclosed in the chart): the filtered line can **jump at vintage boundaries**, because the new vintage's hyperparameters rewrite the whole state path. Boundaries are marked on the chart. In the STEP simulation (`R = 50`) the mean absolute jump in the Mkt-RF beta at a boundary was 0.038, against a mean daily change of 0.0029; with constant betas 0.0062 against 0.0012 [V]. KB7.3 discusses this.
- The frozen alternative (vintage 0 used forever) was evaluated and rejected: in the random-walk simulation its RMSE was 10% higher and its band coverage 0.87 instead of 0.93 [V, KB7.1].
- The re-estimation step `h = 252` is a fixed constant. A quarterly step was evaluated (KB7.3).

### KB2.5 Equivalent window

For a scalar regressor with second moment `s^2` and `Q = lambda R / s^2`, the steady-state scaled posterior variance `p = P s^2 / R` solves `p^2 + lambda p - lambda = 0`, so `p ~ sqrt(lambda)` and the gain is about `sqrt(lambda)`. That is an exponentially weighted regression with forgetting `1 - sqrt(lambda)`, whose noise and mean lag match a rolling window of about `2 / sqrt(lambda)` rows. Check by simulation (constant betas, fixed `lambda`, DGP-A factors with zero correlation, 100 replications, 3000 rows) [V]: the filter's RMSE divided by the RMSE of a rolling window of `W_eq` rows is 0.941 (`lambda = 1e-3`, `W_eq = 63`), 0.979 (`1e-4`, 200) and 0.987 (`2.5e-5`, 400). The label reports `W_eq` rounded to 10 rows, as "behaves like a {W_eq}-day window". With `lambda = 0` the label says "no drift detected: uses all data so far".

---

## KB3. Initialisation and warm-up

- **Burn-in OLS (exact diffuse equivalent).** OLS on rows `1 .. b` (`b = 21`) gives `a_{b|b}` and `P_{b|b} = R (X_b' X_b)^-1`. This is exactly the posterior under a diffuse prior when no state noise acts during the burn-in rows. The filter then runs rows `b+1 .. n`, adding `Q` at every transition.
- Verified [V]: (i) with `lambda = 0`, every filtered state equals OLS on rows `1 .. t` to 1.1e-15 and equals statsmodels `RecursiveLS` to 6.7e-13; (ii) for `lambda` in `{0, 1e-6, 1e-4}`, filtered states, filtered covariances and the conditional log-likelihood equal a statsmodels `MLEModel` with `initialization="diffuse"` (exact diffuse) and time-varying `state_cov` (zero for the burn-in transitions). The match is 6.7e-13 (states), 3.5e-13 relative (covariances) and equal to 6 decimals (log-likelihood) on 1000 SPY rows.
- **Rejected: approximate diffuse prior** (`P_0 = kappa I`, `kappa = 1e6` in scale units). On the same SPY rows it left a ridge-type bias of 6.4e-5 in the betas at row 1000 [V]. In scale units the prior standard deviation is `sqrt(kappa R)`, about 1.8 for SPY, which is not diffuse relative to beta precision. The value of `kappa` would be a tuning choice; the burn-in OLS is exact and has none.
- Warm-up: rows `1 .. B0 - 1` produce no output (KB2.3).

---

## KB4. Filtered versus smoothed

### KB4.1 Rule

Every Kalman value shown at a date, used in a sentence, compared with the rolling betas, or exported as a time series is **filtered** (`a_{t|t}`, `P_{t|t}`) or **predicted** (`a_{t|t-1}`). The smoother is not called in the point-in-time code path (static check TKB20).

### KB4.2 Retrospective (smoothed) view

The Rauch-Tung-Striebel smoother uses rows after `t`. It may be offered only as follows:

- Off by default, in the details drawer, never on the main chart and never in exports without the `retrospective` flag.
- Hyperparameters estimated on all `n` rows (one vintage), stamped `T_end` as one full-sample output (M0.2 item 2).
- Dashed line, label **L-KSMOOTH**: "Retrospective: each point uses data from after that date. It shows where exposure changed with hindsight and must not be read as what was knowable at the time."
- Excluded from the look-ahead tests, with a test that proves it would fail them (TKB17).

Why this matters, MSTR around the 2020-08-11 announcement [V]: the smoothed Mkt-RF beta is 1.14 on the announcement day, 1.02 twenty trading days earlier and 0.81 sixty-two trading days earlier. The filtered beta at the same dates is 0.63, 0.66 and 0.67. The smoother moves the change earlier than the event that caused it.

Recommendation: do not ship the smoothed view in v1 (open question Q4).

---

## KB5. Uncertainty bands

- Band: `a_{t|t,j} +/- 1.959964 sqrt(R_j P_{t|t,jj})` (scale form times the vintage's `R_hat`), pointwise.
- What it is: the posterior spread of the **current** beta under the model. It includes the uncertainty from possible drift, so it is wider than the HAC interval of a rolling window, which measures the window-average beta. SPY at 2026-09-30, Mkt-RF: Kalman sd 0.029 against the HAC se 0.0066 of the 252-day window. MSTR: 0.60 against 0.44 [V].
- Caveats (label **L-KBAND**): "Model-based 95% band. It assumes normal, independent daily errors with constant variance and treats the estimated drift rate as known. It is not a Newey-West (HAC) interval and is not comparable to the rolling-beta bands. After a sudden change it is too narrow."
- Coverage of the true beta in simulation (KB7.1) [V]: random-walk betas 0.925-0.934 (frozen variant 0.87); constant betas 0.964-0.972 (slightly conservative); after a step break the Mkt-RF and HML bands cover only 0.83 and 0.85; with MA(1) timing noise {{MA_COV}}.
- Not a test: no p-value, no BH family, never used for an alert.

---

## KB6. Fat tails, heteroskedasticity and the SPY timing noise

### KB6.1 Student-t weighted update (variant)

Masreliez and Martin (1977) robustify the Kalman update for heavy-tailed observation errors [V: bibliographic record and abstract, IEEE Trans. Automatic Control 22(3), 361-371; derivation not read, U]. The variant specified here is a simple version in that spirit, an approximation and not their estimator:

- Standardised innovation `z_t^2 = v_t^2 / (R_hat F_t)`.
- Weight `w_t = max(1, (nu + z_t^2) / (nu + 1))`, `nu = 5` (fixed, not estimated).
- Update with observation variance `w_t` (scale form) instead of 1: `F_t = x_t' P x_t + w_t`. Outliers get less weight; ordinary days are unchanged.
- Hyperparameters are those of the Gaussian ML (KB2); `nu -> infinity` gives the Gaussian filter exactly (TKB12).

Pre-registered adoption rule (before any run): adopt as default iff simulated RMSE falls by at least 5% under t(3) errors for both the random-walk and the step DGP, **and** rises by at most 2% under Gaussian errors. Result [V]: {{T5_RESULT}}

Real data, one-day point-in-time prediction error (KB7.2) [V]: SPY MSE 4.347 vs 4.352 (x1e-6; DM z -0.08); MSTR MSE 1487.9 vs 1500.1 (DM z -1.80, p 0.072); MSTR mean absolute error 219.8 vs 222.9 bp (z -6.67). Descriptive only (not part of the H-704 family).

### KB6.2 Heteroskedasticity and volatility regimes

Constant `R` is a misspecification for daily returns. Two checks [V]:

- **Common volatility regimes** (factor and residual volatility switching 1x / 3x in 126-row blocks, DGP-KB otherwise, 100 replications, seeds `20261118 + 970/971`): with **constant** betas, `lambda_hat = 0` at the last vintage in only 15% of replications (60% without regimes, KB7.1), median `lambda_hat` 4.3e-6 (`W_eq` about 960 rows). Heteroskedasticity therefore creates some spurious drift, but a slow one: the KF's tracking RMSE is still 0.168 against 0.230 for rolling 252, and its path sd 0.063 against 0.097. With random-walk betas: KF 0.337, rolling 252 0.352. Band coverage stays 0.93-0.96 in both cases [V].
- **Point-in-time volatility scaling** (divide `y_t` and `x_t` by the standard deviation of Mkt-RF over the 21 French rows ending `t-1`, as in M10.2; a weighted regression): no improvement in the same simulation (RMSE 0.174 vs 0.168 with constant betas, 0.333 vs 0.337 with random-walk betas; share of `lambda_hat = 0` 0.18) [V]. Not adopted. On real data it changed little: SPY prediction MSE 4.326 vs 4.352 (DM p 0.62), MSTR 1501.7 vs 1500.1 (p 0.83). SPY's `lambda` path became flatter (`W_eq` 297-533 across vintages, instead of 128-501 with the jump in 2009) [V].
- **Idiosyncratic variance jumps are not handled.** MSTR's residual volatility rose from 25.5% to 80.6% a year after 2020-08-11 [V]. With a constant `R` estimated mostly on the calm years, large post-event residuals are partly read as noise and the filter adapts slowly (KB7.3).

### KB6.3 SPY timing noise (validation report section 3)

Before about 2009 the Yahoo SPY close contains post-4 pm market movement that reverses the next day (MA(1) residuals, lag-1 autocorrelation -0.40). Effects on the filter:

- The innovations are serially correlated, which the model ignores. Bands are then too narrow. In the MA(1) simulation (noise share 0.8 of residual variance, lag-1 autocorrelation -0.4) the band coverage was {{MA_COV2}} [V].
- The Student-t update does not help: the problem is serial correlation, not tails.
- Recommendation: when gate G1 of the validation report fires, the Kalman panel shows the same caveat ("daily price changes partly reverse the next day ...") and the band label adds "too narrow for this ticker". No separate fix in v1; the lead-lag betas feature (ROADMAP) is the place for one.

---

## KB7. Comparison with rolling betas

### KB7.1 Simulations with known beta paths

DGP-KB: DGP-A factors (`docs/test-oracle.md` 0.4: iid normal, same means, sds, correlations), `alpha = 0.0002`, `sigma_e = 0.012`, `n = 2520`, `R = 200` replications per row, seeds `20261118 + 900 + case`. Truth:

- **RW**: betas start at DGP-A values and follow the model's own random walk with `lambda_true = 1e-4` (`W_eq = 200`; annual sd of the drift 0.20, 0.34, 0.43, 0.52, 0.61 for the five betas [V]).
- **STEP**: DGP-A betas; at row 1261 Mkt-RF jumps 1.10 -> 1.60 and HML -0.40 -> +0.20.
- **CONST**: DGP-A betas throughout (the false-drift check).
- Errors: Gaussian; t(3) scaled to the same variance; MA(1) "timing noise" `e_t = w_t + u_t - u_{t-1}` with `var(u) = 0.4 sigma_e^2`, `var(w) = 0.2 sigma_e^2` (lag-1 autocorrelation -0.4, as SPY).

Estimators compared at every stamp `t = 504 .. 2520` (all point-in-time at `t`): KF (default, annual expanding re-estimation), KF frozen, KF-t5, rolling OLS 126 and 252 (M4), expanding OLS.

Tracking RMSE (root mean squared error against the true beta, averaged over stamps, replications and the five betas) [V]:

{{SIM_TABLE}}

### KB7.2 Real data: one-day point-in-time prediction

No true beta exists for real stocks. The point-in-time criterion is how well the ex-ante betas explain the next day: `u_t = y_t - x_t' theta_hat_{t|t-1}`, with `theta_hat` the Kalman prediction `a_{t|t-1}` or the rolling OLS at stamp `t-1` (M4 ex-ante beta). Sample: rows 505..n. Diebold-Mariano: HAC (M0.5, `L(m)`) z-test on the mean of `d_t = u_KF,t^2 - u_other,t^2`, two-sided. Family H-704 (4 tests, BH `q = 0.05`), pre-registered [V]:

| Ticker (rows, dates) | Comparison | Mean `d` (x1e-6) | z | p | BH-adjusted p | Rejected |
| --- | --- | --- | --- | --- | --- | --- |
| SPY (7970, 1995-01-30..2026-09-30) | KF vs rolling 252 | -0.042 | -1.71 | 0.087 | 0.087 | no |
| SPY | KF vs rolling 126 | -0.169 | -4.55 | 5.4e-6 | 2.1e-5 | **yes** |
| MSTR (6615, 2000-06-12..2026-09-30) | KF vs rolling 252 | -19.1 | -2.05 | 0.040 | 0.054 | no |
| MSTR | KF vs rolling 126 | -53.4 | -3.64 | 2.7e-4 | 5.4e-4 | **yes** |

Prediction MSE (x1e-6): SPY KF 4.352, rolling 252 4.394, rolling 126 4.520, expanding 4.583, KF frozen 4.394; MSTR KF 1500.1, rolling 252 1519.3, rolling 126 1553.5, expanding 1530.3, KF frozen 1504.9 [V]. The Kalman ex-ante betas explain the next day better than the 126-day window on both tickers; against the 252-day window the difference has the same sign but is not significant after correction.

### KB7.3 Abrupt changes: the Kalman filter is slow

Simulation (DGP-KB STEP, Gaussian, `R = 200`) [V]: median number of rows after the break until the Mkt-RF estimate first exceeds the midpoint 1.35: rolling 126: 54; rolling 252: 117; **KF default: 251**; KF-t5: 251; KF frozen: 372. The KF value is exactly one re-estimation period: the break falls at row 1261, the vintage estimated on rows 1..1260 has seen only constant betas, so its `lambda_hat` is 0 or tiny (0 in 55% of replications already at the first vintage), and the filter is close to expanding OLS until the next vintage (rows 1..1512) sees the break and re-runs the path. Overall tracking RMSE is still lower for the KF (0.166 vs 0.191 for rolling 252), because the betas are constant most of the time, but for the Mkt-RF beta alone rolling 252 is better (0.131 vs 0.167), and the KF band covers the truth only 83% of the time.

MSTR, a change with a known date [V]: MicroStrategy announced on 2020-08-11 that it had bought 21,454 bitcoins as its primary treasury reserve asset (press release, Nasdaq, 2020-08-11), after a capital-allocation plan announced on 2020-07-28. Pre-registered test H-701 (pooled interaction regression on the 504 rows before and the 504 rows after the announcement day, design of M9 (c), HAC `L(1008) = 6`, single test): the Mkt-RF beta rose from 0.700 (2018-08-09..2020-08-10) to 2.171 (2020-08-12..2022-08-11), difference 1.471, z 6.77, p 1.3e-11. Not pre-registered and descriptive: RMW changed by -1.82 (z -4.19); residual volatility rose from 25.5% to 80.6% a year.

Trading days after the announcement until the Mkt-RF estimate first exceeds the midpoint 1.436 of the two OLS betas (H-702, descriptive) [V]:

| Estimator | Days |
| --- | --- |
| Rolling 126 | 112 |
| KF frozen (vintage 0 only) | 124 |
| Smoothed (retrospective, uses later data) | 143 |
| Rolling 252 | 191 |
| **KF default** | **222** (at the 2021-06-23 re-estimation; the line jumps there) |
| KF-t5 | 233 |
| KF volatility-scaled | 240 |

Mkt-RF beta on the announcement day and 22, 64, 127 and 253 trading days after it (about 1, 3, 6 and 12 months): KF 0.63, 0.76, 0.94, 0.97, 1.60; rolling 126: 0.68, 0.60, 0.92, 1.80, 1.73; rolling 252: 0.66, 0.69, 0.70, 0.79, 1.74 [V]. The KF reaches 2.74 at 2022-08-11, 504 rows after the announcement.

Interpretation: with hyperparameters learned on years of slowly drifting betas, the random-walk filter treats a sudden change as many small ones and needs many months to follow it. It catches up mainly at the next re-estimation, through a visible jump. This is a property of the model (Gaussian random-walk state noise), not a bug. Hence:

- the Kalman line is labelled as a smooth tracker of gradual change (L-KF), and the 126-day rolling line stays on the same chart as the reference for sudden changes;
- drift alerts (M9) stay on rolling betas;
- re-estimating every 63 rows instead of 252 (H-709, exploratory, added after seeing the lag above; `R = 50`) [V] shortened the median step lag from 251 to 188 rows (inter-decile 125-251), lowered STEP RMSE from 0.166 to 0.158, cut the mean jump at vintage boundaries from 0.038 to 0.011, and changed nothing under constant betas (RMSE 0.0881 vs 0.0887, `lambda_hat = 0` in 46% of replications either way). It costs about 2.5 times the run time in this implementation. All real-data numbers in this document use 252. Recommendation: switch to 63 once the runtime work of KB10.2 lands (open question Q1).

---

## KB8. Computation

### KB8.1 numpy implementation (no new dependency)

- Batched recursion in numpy over a leading axis (grid values of `lambda`, or simulation replications): per row, `P = P + Q`; `Px = P x`; `F = x'Px + 1`; `v = y - x'a`; `K = Px / F`; `a = a + K v`; `P = P - K Px'`; symmetrise `P = (P + P')/2`. Cost `O(n k^2)` per series; the loop over rows is in Python, everything inside is vectorised over the batch.
- Measured [V]: 58 grid values x 1000 rows in 0.03 s; the default SPY run (8474 rows, 32 vintages, grid estimation for each vintage plus one output pass per vintage) 31.9 s on the development machine (12 logical cores, single-threaded numpy loop). Target for the product: below 10 s (KB10.2: coarser grid or reuse of passes).
- Numerical guards: `F_t > 0` (always, since `R = 1` in scale form); `cond(X_b' X_b) < 1e12` for the burn-in, else status `failed` with reason `singular_burn_in` (inherits validation finding F3).

### KB8.2 What statsmodels 0.15.0 offers, and whether it fits [V]

| Component | What it does | Fit for this feature |
| --- | --- | --- |
| `tsa.statespace.mlemodel.MLEModel` | General linear Gaussian state space: time-varying design (1 x k x n), time-varying `state_cov`, exact diffuse initialisation, filter, RTS smoother, `loglike`, `fit` | Fits the Gaussian model exactly and is the **test oracle** (TKB02). Its filter takes 5-9 ms per 1000-row pass, comparable to ours. Not the production path: the vintage logic, the boundary `lambda = 0`, the concentrated grid likelihood and the t-weighted update need custom code around it anyway. |
| `regression.recursive_ls.RecursiveLS` | Recursive least squares (constant coefficients), CUSUM | Equals our filter at `lambda = 0` (TKB01). |
| `tsa.statespace.structural.UnobservedComponents` | Regression coefficients either estimated by ML (constant) or "estimated by recursive OLS, included in the state vector" (docstring) | No time-varying regression coefficients with state noise: does not fit. |
| Robust or Student-t filtering | Not present: the only "robust" in `tsa/statespace` (non-test files) refers to quasi-ML covariance of parameter estimates (`cov_type="robust"`) | Our own code (KB6.1). |

Decision: implement in numpy in `analytics/kalman.py` (pure functions, typed inputs and outputs per `CODING_STANDARDS.md` section 4); use statsmodels `MLEModel` and `RecursiveLS` only in tests. No new dependency.

### KB8.3 Outputs, labels, status values, minimum samples, schema

Status values (M0.7):

| Condition | Status | Reason |
| --- | --- | --- |
| `n < 504` | `insufficient_data` | `kalman_needs_504_rows` (the report is refused anyway) |
| Burn-in design singular | `failed` | `singular_burn_in` |
| A vintage's grid maximiser is the largest grid value `1e-2` | `ok` with warning `kalman_lambda_at_upper_bound` ("the filter follows daily noise; the estimate is not meaningful") | - |
| Otherwise | `ok` | - |

Per-stamp series values for rows `< 504` are `null` (warm-up), never NaN.

Labels (proposed M0.9 keys):

- **L-KF** (chart legend and footnote): "Kalman-filter beta: each point uses only data up to that date. It follows gradual changes smoothly and behaves like a {W_eq}-day window for this stock, but reacts slowly to sudden changes; compare with the 126-day line. The drift rate is re-estimated once a year from past data; the line can jump at those dates (marked)."
- **L-KBAND**: KB5.
- **L-KSMOOTH**: KB4.2 (only if the retrospective view ships).
- **L-KTAIL** (only when gate G1 fires): KB6.3.

Schema (`report/schema.py`, optional sub-models per the schema v3 contract):

```text
KalmanVintage
  index: int; estimated_through: date; rows: int      # rows 1..m_j
  lam: float; lam_at_bound: Literal["zero", "upper", "none"]
  resid_var: float                                     # R_hat, decimal^2/day
  resid_vol_ann: float                                 # sqrt(252 R_hat)
  w_eq: float | None                                   # null when lam == 0
  valid_from: date; valid_to: date                     # stamps it produced

KalmanBetaSeries
  status; reason; sample: SampleInfo
  model: Literal["rw_betas_const_alpha_v1"]
  error_model: Literal["gaussian", "student_t5"]       # default gaussian
  burn_in_rows: int (21); training_rows: int (504); reestimate_every: int (252)
  dates: list[date]                                    # shared date axis (F12 of the validation)
  alpha: list[float | None]; betas: dict[factor, list[float | None]]          # filtered a_{t|t}
  band_low, band_high: dict[factor, list[float | None]]
  ex_ante_betas: dict[factor, list[float | None]]      # a_{t|t-1}
  vintage_index: list[int | None]                      # which vintage produced each stamp
  vintages: list[KalmanVintage]
  latest: dict[factor, {beta, sd, band_low, band_high}]    # stamp T_end
  labels: list[str]; warnings: list[str]

KalmanRetrospective (only if shipped; flag retrospective = true)
  status; reason; sample; lam; dates; betas_smoothed; band_low; band_high; stamped: date (T_end)
```

Minimum samples: 504 rows (first stamp at row 504). The latest values need nothing more.

---

## KB9. Demonstrations [V]

Inputs as in `docs/specs/shrunk-betas.md` SB8 (French US daily 5 factors, SHA-256 `e5857722...`, last date 2026-09-30; yfinance 1.8.0 `Ticker.history(period="max", auto_adjust=False, actions=True, repair=False)`, downloaded 2026-11-18; M2 alignment; Python 3.13.14 in the project `.venv`, numpy 2.5.5, statsmodels 0.15.0).

### KB9.1 SPY (near-constant true betas, known timing noise)

`n = 8474`, 1993-02-01..2026-09-30, 32 vintages.

| | Mkt-RF | SMB | HML | RMW | CMA |
| --- | --- | --- | --- | --- | --- |
| KF at 2026-09-30 | 0.988 | -0.104 | 0.023 | 0.006 | 0.003 |
| KF sd (model) | 0.029 | 0.042 | 0.041 | 0.043 | 0.056 |
| Rolling 252 at 2026-09-30 (HAC se) | 0.990 (0.007) | -0.102 (0.023) | 0.026 (0.015) | 0.011 (0.014) | -0.006 (0.010) |
| Rolling 126 | 0.985 | -0.118 | 0.038 | -0.002 | -0.011 |
| Full sample OLS (M3) | 1.009 | -0.148 | 0.007 | 0.088 | 0.061 |
| Time sd of the series, KF / rolling 252 / rolling 126 | 0.027 / 0.027 / 0.035 | 0.073 / 0.074 / 0.079 | 0.047 / 0.055 / 0.066 | 0.049 / 0.050 / 0.068 | 0.062 / 0.065 / 0.083 |

`lambda` by vintage: `W_eq` 294 rows at the first vintage (1995-01-27), 433-501 in 1996-1999, 250-293 in 2000-2008, then 128-147 from 2009-02-02 on, after 2008 entered the estimation sample. Residual volatility estimate 2.6-4.8% a year [V]. Reading: on SPY the filter behaves like a 130-300-day window. Its path is about as variable as the 252-day window's, and its next-day fit is better than the 126-day window's (KB7.2).

### KB9.2 MSTR (known exposure change)

Choice, made before fetching data: MSTR has a business-model change with a public date independent of its prices (KB7.3). It also has three splits (2:1 on 2000-01-27, 1:10 on 2002-07-31, 10:1 on 2024-08-08 in `Stock Splits` [V]) and extreme tails (2000 crash), so it exercises the tail and split handling. `n = 7119`, 1998-06-12..2026-09-30, 27 vintages.

| | Mkt-RF | SMB | HML | RMW | CMA |
| --- | --- | --- | --- | --- | --- |
| KF at 2026-09-30 | 2.27 | -0.49 | -1.44 | -0.68 | -0.24 |
| KF sd (model) | 0.60 | 0.87 | 0.83 | 0.89 | 1.16 |
| KF-t5 | 2.07 | 0.02 | -1.29 | -0.87 | 0.09 |
| Rolling 252 (HAC se) | 2.19 (0.44) | 0.17 (0.62) | -1.07 (0.47) | -1.25 (0.40) | 0.64 (0.64) |
| Rolling 126 | 2.36 | -0.46 | -1.78 | -0.31 | 0.39 |
| Full sample OLS | 1.15 | 0.80 | -0.79 | -1.53 | -0.33 |

`W_eq` 183-352 rows through the 2020-06-23 vintage, then 126-132 from the 2021-06-23 vintage on (the first one that sees the post-announcement year) [V].

### KB9.3 Simulations

KB7.1 (tracking), KB2.5 (equivalent window), KB6 (tails, heteroskedasticity, MA(1)), KB7.3 (step lag).

---

## KB10. Decisions, proposals, open questions

### KB10.1 Decisions

- **KD1 Random-walk betas, constant alpha** (KB1.2).
- **KD2 One hyperparameter**, `Q = lambda R Sigma_f^-1`, concentrated ML on a grid, `lambda = 0` allowed (KB1.3, KB2).
- **KD3 Training 504 rows, expanding re-estimation every 252 rows, each vintage re-run from row 1** (KB2.4). Jumps at vintage boundaries are disclosed and marked. A 63-row step is recommended once runtime allows (KB7.3, Q1).
- **KD4 Burn-in OLS initialisation** (exact diffuse equivalent), `b = 21` (KB3).
- **KD5 Filtered only for anything dated**; smoothed only as a labelled retrospective view, not in v1 (KB4).
- **KD6 Model-based band, labelled as such** (KB5).
- **KD7 Gaussian errors by default**; {{KD7}}
- **KD8 Kalman line is additional**: rolling 126/252 stay; no downstream statistic uses Kalman betas (KB7.3).
- **KD9 numpy implementation, statsmodels as test oracle** (KB8.2).

### KB10.2 Engineering items

Runtime target below 10 s per ticker (grid of 4 per decade, or reuse the grid pass of vintage `j` for rows `<= m_j` when `M` is frozen per vintage); shared date axis in the payload; series thinning as in validation F11-F12.

### KB10.3 Proposed additions to `docs/methodology.md` (for the owner; not made here)

A new section after M4 ("M4K Kalman betas") summarising KB1-KB5; M0.9 labels L-KF, L-KBAND, L-KSMOOTH, L-KTAIL; M0.7 row (504 rows); M15 constants (`b = 21`, `B0 = 504`, `h = 252`, grid, `nu = 5`); a T104 extension that forbids smoother calls in `analytics/kalman.py` outside the retrospective function.

### KB10.4 Open questions for the owner

1. **Slow reaction to sudden changes** (KB7.3). (a) Switch the re-estimation step to 63 rows (better in simulation, about 2.5x run time); (b) accept the residual slowness with the 126-day line as the reference for breaks, or invest in a break-aware model (heavy-tailed state noise or a change-point mixture), which is a larger piece of work.
2. **Diagonal `Q`** fits SPY and MSTR better over 30 years in-sample (KB1.3) but is weakly identified on training samples. Revisit after a panel study?
3. **Point-in-time AR(1)** (mean from past data) versus random walk, out of sample (KB1.2): run before release, or accept the random walk on the stated reasons?
4. **Retrospective smoothed view**: ship in the drawer with L-KSMOOTH, or not at all?
5. **Runtime** of about 30 s for a 33-year ticker: acceptable for v1, or require the 10 s target first?

---

## KB11. Test oracle (TKB01-TKB24)

Conventions as in `docs/test-oracle.md` section 0: seed `20261118 + k` for test `k`, here `k = 600 + NN` for TKB`NN`; tolerances from standard errors; markers `slow` and `live`. Target module `analytics/kalman.py` unless stated. DGPs: DGP-A and DGP-B of the test oracle; DGP-KB (KB7.1) with `n = 2520`.

### Identities and reference implementations (deterministic)

- **TKB01 `lambda = 0` is expanding OLS.** DGP-A, `lambda = 0`: filtered state at every row `t >= 21` equals OLS on rows `1 .. t` (1e-10 absolute; observed 1.1e-15 on SPY [V]) and statsmodels `RecursiveLS(y, X).fit().recursive_coefficients.filtered` (1e-10; observed 6.7e-13 [V]).
- **TKB02 statsmodels reference.** DGP-A, 1000 rows, `lambda` in `{1e-6, 1e-4, 1e-2}`: filtered states and covariances (`R_hat * P`) equal `MLEModel` with `initialization="diffuse"`, design `x_t'`, transition and selection identity, `obs_cov = R_hat`, `state_cov[:, :, t] = 0` for `t < b - 1` and `blockdiag(0, lambda R_hat M)` from `t = b - 1` on. Tolerances 1e-10 absolute (states) and 1e-8 relative (covariances). Our conditional log-likelihood equals `res.llf_obs[b:].sum()` to 1e-8 relative. (Observed 6.7e-13, 3.5e-13, 6 decimals [V].)
- **TKB03 Burn-in.** `a_{b|b}` equals OLS on rows `1 .. 21`; `P_{b|b} = (X_b' X_b)^-1` (scale form) (1e-12).
- **TKB04 Concentration.** For fixed `lambda`, `R_hat = mean(v_t^2 / F_t)` maximises the full Gaussian log-likelihood in `R`: perturbing `R_hat` by +/-1% lowers it (exact inequality); `logL_c` equals the full log-likelihood at `R_hat` (1e-10 relative).
- **TKB05 Scale form.** Running the filter with true-unit `R = R_hat` and `Q = lambda R_hat M` gives the same `a_{t|t}` and `R_hat P_{t|t}` as the scale form (1e-12).
- **TKB06 Smoother end point.** `a_{n|n} == a_{n|n}^smoothed` and the smoothed covariance at `n` equals the filtered one (1e-12): the retrospective view and the latest filtered value agree on the last date.

### Hyperparameters and vintages

- **TKB07 Grid and refinement.** Pure function on a synthetic log-likelihood `-(log10 lambda + 4.3)^2`: the refined maximiser is `10^-4.3` within 1e-9 in `log10`. A log-likelihood decreasing in `lambda` returns exactly 0. A maximiser at `1e-2` returns `1e-2` and warning `kalman_lambda_at_upper_bound`.
- **TKB08 Vintage schedule.** `n = 2520`: vintages at rows 504, 756, ..., 2520 (9 vintages, exact). Stamps 504..755 carry `vintage_index = 0`; rows 1..503 are null; each vintage's `M` equals `inv(cov(F[1..m_j], ddof=1))` (1e-12).
- **TKB09 Equivalent window.** DGP-KB CONST with uncorrelated factors, fixed `lambda` in `{1e-3, 1e-4}`, 100 replications, 3000 rows: RMSE(KF) / RMSE(rolling `round(2/sqrt(lambda))`) in `[0.90, 1.05]` (observed 0.941 and 0.979 [V]; the band allows the approximation error of the steady-state argument plus about 4 Monte Carlo standard errors of the ratio, which is about 0.005 at this size).
- **TKB10 ML recovery (`slow`).** DGP-KB RW, `R = 200`: median over replications of `lambda_hat / lambda_true` at the last vintage in `[0.85, 1.18]` (observed 1.02; inter-decile range 0.73-1.40 [V]; the median's Monte Carlo se in `log` is about 0.022, so the band is about 7 se plus room for small-sample ML bias).
- **TKB11 False drift (`slow`).** DGP-KB CONST, Gaussian, `R = 200`: (a) share of replications with `lambda_hat = 0` at the last vintage `>= 0.45` (observed 0.60; binomial se 0.035, so the bound is about 4 se below); (b) mean over replications of the time sd of the Mkt-RF Kalman path `<= 0.5 x` that of rolling 252 (observed 0.024 vs 0.074, ratio 0.32); (c) RMSE(KF) `<= 1.25 x` RMSE(expanding OLS), the best possible estimator here (observed 0.088 vs 0.078, ratio 1.13) [V].

### Robust variant

- **TKB12 t-weights.** `nu = 1e12` reproduces the Gaussian filter (1e-10). Weight formula on hand inputs: `z^2 = 0.5` gives `w = 1`; `z^2 = 16`, `nu = 5` gives `w = 21/6 = 3.5` (exact). One injected `+20 sigma_e` residual at row 1500 of DGP-A: the Gaussian filter's Mkt-RF beta moves by more than 3 times the t-filter's move at that row.

### Look-ahead (point-in-time)

- **TKB13 Filtered and predicted are causal.** Extends T102: DGP-A, `t* = 1800`; every row after `t*` replaced (returns, factors, RF, plus a dividend and a split after `t*`). Unchanged for all stamps `<= t*`: filtered betas, alpha, bands, ex-ante betas, `vintage_index`, and all vintages with `m_j <= t*` (`lambda`, `R_hat`, `M`) (1e-12 absolute; observed 4.8e-16 on SPY rows with `t* = 2000` [V]).
- **TKB14 Truncation.** Extends T103: running on rows `1 .. t*` gives identical values for every stamp `<= t*` (exact; observed 0.0 [V]).
- **TKB15 Vintage boundary.** With `t* = m_j - 1` (the row before a re-estimation): perturbing rows `>= m_j` leaves every stamp `<= m_j - 1` unchanged, and the stamp `m_j` changes (proves the test reaches the boundary).
- **TKB16 Ex-ante lag.** Multiplying `y` and `f` on row `t` by 10 leaves `a_{t|t-1}` unchanged and changes `a_{t|t}`.
- **TKB17 Smoothed fails, on purpose.** The retrospective series at `t* - 1` changes under the TKB13 perturbation by more than 1e-6. This proves the look-ahead test would catch a smoother in the point-in-time path.
- **TKB18 Static scan.** T104 extended: in `analytics/kalman.py`, `smooth`, `smoothed_state`, backward recursions and any index `> t` inside the forward loop are allowed only in the function `retrospective_smoothed`, which the report builder calls only when the flag is set.

### Simulation properties (`slow`)

- **TKB19 Beats rolling on drifting betas.** DGP-KB RW, Gaussian, `R = 200`: RMSE(KF) `<` RMSE(rolling 252) and `<` RMSE(rolling 126), each by at least 3% (observed 8.0% and 8.9% lower [V]). The Monte Carlo se of these RMSE ratios is well below 1% at `R = 200` (common random numbers).
- **TKB20 Band coverage, correct model.** DGP-KB RW, Gaussian: per-factor coverage of the filtered 95% band in `[0.90, 0.96]` (observed 0.925-0.934 [V]; below 0.95 because `lambda` is estimated; binomial se of the pooled rate is small, but stamps are strongly dependent within a replication, so the band is wide).
- **TKB21 Slow step response is documented.** DGP-KB STEP, Gaussian: median lag to the Mkt-RF midpoint, KF default `>=` rolling 252 (observed 251 vs 117 rows [V]). If a code change makes the filter faster than rolling 252 here, L-KF and KB7.3 must be revised in the same change.

### Status, schema and live

- **TKB22 Status and nulls.** `n = 503`: `insufficient_data`; `n = 504`: exactly one stamp; warm-up rows are `null` in JSON (`allow_nan=False` passes); a singular burn-in (constant factor column over rows 1..21) gives `failed / singular_burn_in`.
- **TKB23 Downstream isolation.** A DGP-A report with and without the Kalman module: all M3-M10 numbers bitwise identical; `analytics/attribution.py`, `dominance.py`, `drift.py` do not import `kalman`.
- **TKB24 Live smoke (`live`).** SPY from 2010-01-04: latest Mkt-RF Kalman beta in `[0.90, 1.10]`, `W_eq` of the last vintage in `[60, 2000]`. MSTR: Kalman Mkt-RF beta 504 rows after 2020-08-11 exceeds the value at 2020-08-10 by at least 0.5 (observed 0.63 on 2020-08-11 and 2.74 on 2022-08-11 [V]).

---

## KB12. Registry entries (demonstrations run for this document)

Format: protocol Appendix A. These lines must be appended to `docs/registry/tests.jsonl` (renumbered if the ids collide) in the change that adds this spec. A pre-registration note (tickers, H-701 to H-707, the t-filter adoption rule, the model specification) was written in the scratchpad before any data were downloaded or simulated. It was not committed, so every line has status `run` and says so in `notes`. H-708 and H-709 were added **after** seeing earlier results and are exploratory. Common fields: `created_at` 2026-11-18; `code_version` none (scratch scripts `verify_kf.py`, `sim_kf.py`, `real_kf.py`, `kf_checks.py`, `sim_kf_het.py`, `real_kf_vs.py`, `sim_kf_q.py`); dataset `us_ff5_daily` stamp 202609 SHA-256 `e58577223032aa45071a46686f7068900c371b516c9eb04e28e974c34264f84f`; prices yfinance 1.8.0, downloaded 2026-11-18; split role `in_sample_only` (no estimation/confirmation split; the H-704 test is a point-in-time prediction comparison over the whole sample).

| test_id | hypothesis_id | Spec | Result | Notes |
| --- | --- | --- | --- | --- |
| T-20261118-701 | H-701 | MSTR Mkt-RF beta, 504 rows before vs after 2020-08-11, pooled interaction, HAC L(1008)=6, two-sided, m = 1 | delta 1.471, z 6.77, p 1.3e-11 | confirmed; other 4 deltas descriptive |
| T-20261118-702 | H-702 | MSTR days to cross midpoint 1.436: KF, KF frozen, KF-t5, rolling 126, rolling 252, smoothed (6 lines) | 222, 124, 233, 112, 191, 143 | descriptive |
| T-20261118-703 | H-703 | Simulation R = 10 smoke run of all DGP x error cases | inspected | **looked at before the R = 200 run**; no parameter was changed after it |
| T-20261118-704..711 | H-703 | Simulation R = 200: RW, STEP, CONST x Gaussian; RW, STEP, CONST x t(3); RW, CONST x MA(1) (8 lines) | KB7.1 | |
| T-20261118-712..715 | H-704 | DM: KF vs rolling 252 and 126, SPY and MSTR (family m = 4, BH) | KB7.2 | 2 of 4 rejected |
| T-20261118-716..719 | H-704D | DM descriptive: KF vs expanding, KF-t5 vs KF (MSE and absolute), SPY and MSTR | KB6.1, KB7.2 | not in the family |
| T-20261118-720..735 | H-705 | AR(1) vs RW, `phi` in {0.9, 0.95, 0.98, 0.99, 0.995, 0.998, 0.999, 1}, 504 training rows, SPY and MSTR (16 lines) | KB1.2 | descriptive; confounded by heteroskedasticity |
| T-20261118-736..739 | H-705 | Diagonal vs scalar `Q`, 504 rows and full sample, SPY and MSTR (4 lines) | KB1.3 | optimiser bounds hit |
| T-20261118-740 | H-706 | t-filter adoption rule (pre-registered) evaluated on T-704..711 | KB6.1 | |
| T-20261118-741 | H-707 | Band coverage, from T-704..711 | KB5 | |
| T-20261118-742..744 | H-710 | Equivalent window, `lambda` in {1e-3, 1e-4, 2.5e-5} | KB2.5 | |
| T-20261118-745 | H-711 | Look-ahead perturbation and truncation on SPY rows 1..3000 | TKB13-14 | implementation check |
| T-20261118-746 | H-712 | Initialisation: approximate diffuse `kappa = 1e6`, SPY 1000 rows | bias 6.4e-5 at row 1000 | **abandoned** specification |
| T-20261118-747 | H-712 | Burn-in OLS vs statsmodels exact diffuse and RecursiveLS | KB3 | adopted |
| T-20261118-748..749 | H-708 | Volatility regimes, CONST and RW, KF vs volatility-scaled vs rolling 252, R = 100 | KB6.2 | exploratory, added after results |
| T-20261118-750..751 | H-708 | Volatility-scaled KF on SPY and MSTR (prediction MSE, DM vs KF and rolling 252, MSTR days to cross) | KB6.2, KB7.3 | exploratory |
| T-20261118-752..753 | H-709 | Re-estimation every 63 vs 252 rows, STEP and CONST Gaussian, R = 50 | KB7.3 | exploratory, added after results |
| T-20261118-754 | H-713 | statsmodels 0.15.0 feature check (source scan and docstrings) | KB8.2 | not a statistical test |

Hypotheses: H-701 "MSTR's Mkt-RF beta rose after the bitcoin treasury announcement"; H-702 "the Kalman filter crosses the midpoint sooner than rolling windows" (not supported); H-703 "Kalman tracks known beta paths better than rolling windows, and does not invent drift when betas are constant"; H-704 "Kalman ex-ante betas explain the next day better than rolling ex-ante betas"; H-705 model-form comparisons; H-706 robust-filter adoption; H-707 band calibration; H-708 heteroskedasticity and volatility scaling; H-709 re-estimation frequency; H-710 equivalent window; H-711 look-ahead implementation; H-712 initialisation; H-713 software capabilities.

Sources checked on 2026-11-18: MicroStrategy press release "MicroStrategy Adopts Bitcoin as Primary Treasury Reserve Asset", <https://www.nasdaq.com/press-release/microstrategy-adopts-bitcoin-as-primary-treasury-reserve-asset-2020-08-11> (dated 2020-08-11; 21,454 bitcoins; follows the 2020-07-28 capital-allocation plan; read via search summary); Masreliez and Martin (1977), record <https://www.bohrium.com/paper-details/robust-bayesian-estimation-for-the-linear-model-and-robustifying-the-kalman-filter/812353355929092097-2478>; statsmodels 0.15.0 installed in the project `.venv` (source and docstrings read). Durbin and Koopman, *Time Series Analysis by State Space Methods* (2nd ed., Oxford University Press, 2012), is the standard reference for the filter, the exact diffuse initialisation and the smoother [U: not re-checked in this session].
