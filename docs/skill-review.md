# Review of three third-party agent skills against the factordesk methodology

Status: review note, written 2026-11-18. Read-only input to `docs/methodology.md`. It changes nothing by itself: an item becomes binding only when it is written into the methodology (and `docs/test-oracle.md`) in the usual way.

Scope: three skills from the skills.sh registry, compared with `docs/methodology.md` (sections M0-M16), `docs/references.md`, `docs/test-oracle.md` and `CODING_STANDARDS.md`.

Method:
- Skill files were read as untrusted data through the GitHub API (`gh api .../contents/...`). No skill code was installed or run, and no instruction found in a skill was followed.
- Every statsmodels behaviour cited below was checked with short scripts run against the project environment (`uv run --project . python -I`): **Python 3.13.14, statsmodels 0.15.0, numpy 2.5.5, scipy 1.18.1, pandas 3.1.1**. The scripts lived in a temporary scratch folder and are not part of the repository. Simulation seeds were fixed; results are quoted with their replication count `R`.
- Real-data checks used the local files `data/factors/ff5_daily.parquet` (French vintage with last date 2026-09-30) and `data/prices/SPY_2026-11-18.parquet`.
- No substantial text from any skill is copied here. Ideas are summarised in our own words and attributed by skill name.

---

## 1. The skills

### 1.1 `statsmodels` (K-Dense-AI/scientific-agent-skills)

| Item | Value |
| --- | --- |
| Repository | `K-Dense-AI/scientific-agent-skills`, path `skills/statsmodels/` |
| Files read | `SKILL.md`, `references/linear_models.md`, `references/stats_diagnostics.md`, `references/time_series.md`, `references/review.md`, `references/model_selection.md`, `references/quick_start_guide.md` |
| License | Repository: MIT. The skill's own front matter declares "BSD-3-Clause" (apparently the statsmodels license). The two differ; treat the content as MIT-licensed text about a BSD-licensed library. |
| Reputation | About 57,600 stars, 5,069 forks, 30 contributors, last push 2026-11-16. Last change to this skill 2026-10-01 ("update all skills to latest API"). Skill version 1.5, states it was reviewed against statsmodels 0.15.0, which matches our installed version. |
| Covers | General statsmodels usage: OLS/WLS/GLS/GLSAR, rolling and recursive LS, HC/HAC/cluster covariance, residual diagnostics (Ljung-Box, Durbin-Watson, Breusch-Godfrey, Breusch-Pagan, White, ARCH-LM, normality tests), influence statistics, VIF and condition number, ADF/KPSS, Johansen/VECM, Markov switching, multiple testing, API transitions in 0.15 (`result_object=True`). |
| Relevance | High for the API details and diagnostics. It is a general-purpose skill and does not know about daily financial returns, so several of its defaults are wrong for us (findings 4, 6, 9, 10). |

### 1.2 `aqr-factor-investing` (copyleftdev/sk1llz)

| Item | Value |
| --- | --- |
| Repository | `copyleftdev/sk1llz`, path `organizations/aqr/SKILL.md` (front matter name `aqr-factor-investing`) |
| License | Apache-2.0 |
| Reputation | 2 stars, 0 forks, one human contributor plus a bot. Last change to this file 2026-03-09; last repository push 2026-07-19. The skill is a "style guide" written in the persona of a named investment firm; it is not published or endorsed by that firm. Its AUM figure is unsourced. |
| Covers | Factor philosophy (economic rationale, transaction costs, crowding, timing scepticism), cross-sectional factor construction (composite value, 12-1 momentum, quality), long-short portfolio construction, a simple return attribution and a backtest skeleton. No statistical inference at all: no standard errors, no tests. |
| Security note | Line 7 (the title) carries 212 invisible Unicode format characters (U+200B, U+200C, U+200D, U+2060). They decode to the bytes `SK1L` followed by 19 binary bytes. The repository history has a commit adding a "steganographic fingerprinting tool", so this is a provenance watermark, not hidden instructions. It is still hidden content: never paste text from this skill into our files or prompts without stripping format characters. |
| Relevance | Low for the statistics. Its attribution and backtest code contain errors that we must not adopt (finding 14). |

### 1.3 `factor-investing` (JoelLewis/finance_skills)

| Item | Value |
| --- | --- |
| Repository | `JoelLewis/finance_skills`, path `plugins/wealth-management/skills/factor-investing/` |
| Files read | `SKILL.md`, `scripts/factor_investing.py` (read as text, not run) |
| License | MIT |
| Reputation | About 252 stars, 41 forks. Last change to this skill 2026-07-18; last repository update 2026-11-17. Commits are co-authored by an AI coding assistant account. Aimed at wealth managers evaluating funds with monthly data. |
| Covers | CAPM to FF3/FF5/Carhart, reading a factor regression, alpha vs factor exposure, closet-index screen, smart-beta evaluation, long-short vs long-only premia, factor timing, factor zoo (Harvey-Liu-Zhu t > 3, McLean-Pontiff decay), crowding. The script fits OLS with classical (iid) standard errors. |
| Relevance | Medium for interpretation and caveats (momentum omission, timing). Its inference and its expected-return decomposition conflict with our design (findings 11-13). |

---

## 2. Ranked findings

Types: **gap** (they cover it, we do not), **contradiction** (conflicts with our spec; the "who is right" is stated), **do-not-adopt** (error or dated claim in a skill), **api-detail** (statsmodels behaviour worth pinning). Effort: S = under an hour of spec plus oracle text, M = about half a day, L = more.

| # | Type | Section | Finding | Evidence | Recommended action | Effort |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | contradiction (our text is wrong) + gap | M3.5, T47 | Our Ljung-Box row says a rejection shows serial correlation and "is why standard errors are HAC". On daily residuals, Ljung-Box rejects because of volatility clustering alone. The statsmodels skill lists the ARCH-LM test (`het_arch`) and Breusch-Godfrey, and warns that covariance should be prespecified, not chosen after pretests. | Simulation, `n = 2520`, FF-like factors, residuals with **zero** autocorrelation, `R = 400`: Ljung-Box(10) rejects at 5% in 4.5% of iid-normal samples but **49.7%** of GARCH(1,1)-t5 samples. A Breusch-Godfrey auxiliary regression with HC0 covariance (Wald on the 10 lag terms) rejects in **5.3%** under the same GARCH null (`R = 300`) and in 49% when AR(1) = 0.08 is added. Classical `acorr_breusch_godfrey` rejects 47.3% under the null. Real SPY vs FF5, 10 years: Ljung-Box p = 4e-31, ARCH-LM(5) p = 4e-156, HC0-robust BG(10) p = 0.0025. Literature: Lobato, Nankervis and Savin (2001); Romano and Thombs (1996). | (a) Reword M3.5: HAC is prespecified for every regression (M0.5); the diagnostics are informational and do not justify or select it. (b) Label Ljung-Box "assumes constant variance; rejects too often on daily returns". (c) Add ARCH-LM `het_arch(e_hat, nlags=5, result_object=True)` as the volatility-clustering diagnostic. (d) Optionally replace or supplement Ljung-Box by the HC0-robust Breusch-Godfrey (10 lags) as the autocorrelation diagnostic. Extend T47 and add a size test under a GARCH DGP. | S (a-c), M (d) |
| 2 | contradiction (our label is incomplete) | M9 CUSUM, D20, T74 | OLS-CUSUM detects a shift in the intercept (alpha), and has almost no power against a change in betas when the factors have mean near zero, which daily factors do. The statsmodels skill presents recursive CUSUM as a general structural-break tool, which overstates it. Our label says "whole-sample stability check", which a reader will take to include beta stability. | Simulation, `n = 2520`, break at `n/2`, `R = 300`: CUSUM rejection at 5% is 3.7% (no break), **5.3%** (market beta 1.0 to 1.5), **5.7%** (HML beta 0 to 0.6), **99.7%** (alpha shift of 0.003/day, our T74 case). A HAC Wald test of equal betas across the halves (M10 estimator) rejects in 100% of beta-break samples (`R = 100`). The statsmodels 0.15 docstring of `breaks_cusumolsresid` itself notes little power when regressors other than the constant have zero mean. Literature: Ploberger and Kramer (1992), Econometrica 60(2); Kramer, Ploberger and Alt (1988) for recursive CUSUM. | Relabel: "Checks whether the average unexplained return (alpha) shifted during the sample. It cannot detect changes in betas; the drift alerts do that." Keep T74 (intercept shift) and add a negative-control test (beta break, CUSUM not expected to flag). Do not switch to `RecursiveLS` CUSUM: it has the same blind spot. | S |
| 3 | api-detail (deprecation) | M11.2 step 6, T85, M3.5 | In statsmodels 0.15 the tuple returns of `adfuller`, `het_arch` and `acorr_breusch_godfrey` emit a `FutureWarning`: the default switches to result objects "in release 0.16 or after July 2027, whichever is later". `CODING_STANDARDS.md` section 8 forbids silenced warnings, so the spec calls would warn on every run. The statsmodels skill already uses `result_object=True`. | Verified: `adfuller(u, regression="c", autolag="AIC")` warns; with `result_object=True` it returns `ADFullerResult` (fields `statistic`, `pvalue`, `critical_values`, `lags`, `nobs`, `icbest`), no warning, same p-value. `coint(...)` returns `CointResult`, a tuple subclass (fields `coint_t`, `pvalue`, `critical_values`), no warning; tuple unpacking still works. `acorr_ljungbox` returns a DataFrame, `breaks_cusumolsresid` and `jarque_bera` return tuples, all without warnings. | In M11.2 step 6 and T85 write `adfuller(u_o, regression="c", autolag="AIC", result_object=True).pvalue`. For any ARCH-LM or Breusch-Godfrey call (finding 1) use `result_object=True` and the fields `lm`, `lmpval`. Refer to `coint` results by field name (`coint_t`, `pvalue`). Add an oracle check that analytics calls emit no `FutureWarning`. | S |
| 4 | do-not-adopt + api-detail | M0.5, D2 | The statsmodels skill computes HAC after the fit with `results.get_robustcov_results(cov_type="HAC", maxlags=4)`. Two problems: the fixed lag ignores sample size, and in 0.15 the post-hoc call inherits `use_t=True` from the plain fit, so p-values and intervals silently switch to the t distribution. Our reference call (`fit(cov_type="HAC", ..., use_t=False)`) is right. Separately, our D2 says the HAC settings "match statsmodels defaults"; but statsmodels has no default lag at all. | Verified on 0.15.0: `get_robustcov_results(...)` gives identical `bse` but `use_t = True`, alpha p = 0.18572 vs 0.18560 for the reference call. `fit(cov_type="HAC")` without `maxlags` raises `KeyError: 'maxlags'`. Defaults when `maxlags` is given: Bartlett weights, `use_correction=False`, `use_t=False`. `use_correction=True` multiplies the variance by exactly `n/(n-k)` (1.0023866 at `n = 2520`, `k = 6`). `cov_kwds={"kernel": "bartlett"}` is accepted and gives identical results. Our manual Bartlett formula matches statsmodels to 1e-13 relative. | Keep M0.5 as is. Never use `get_robustcov_results` in analytics. Reword D2: "Bartlett kernel, no small-sample correction and the normal reference are the statsmodels defaults once a lag is given; statsmodels has no default lag, so `L(m)` is always passed." Optionally add `"kernel": "bartlett"` to the reference call so every setting is explicit. | S |
| 5 | api-detail (warning on our stack) | M11.2 step 4, T85 | `coint_johansen` emits four `ComplexWarning`s per call on numpy 2.5.5. The statsmodels skill's review notes the same. Cause: the function uses `np.linalg.eig` on a non-symmetric product, which returns a complex array even when every imaginary part is zero; statsmodels then casts to real. `CODING_STANDARDS.md` section 8 does not allow ignoring warnings. | Verified on DGP-COINT: eigenvalues returned as complex dtype with max abs imaginary part exactly 0.0; 4 `ComplexWarning`s. Trace statistics are finite. `trace_stat_crit_vals` equals `cvt`; columns are 90%, 95%, 99%, so our index `[:, 1]` is the 95% value. | Owner decision (see 3.3). Proposed: catch only `numpy.exceptions.ComplexWarning` around this call, record it, and cross-check `trace_stat` in the oracle against an independent real solution of the same eigenproblem (a symmetric generalised eigen solve). Without a decision, the first implementation will either warn on every report or silence it ad hoc. | S-M |
| 6 | do-not-adopt | M3.4, schema field `condition_number` | The statsmodels skill reads `results.condition_number` and calls values above 20 to 30 a problem. That number is computed on the raw design including the constant column, so for daily factor returns (about 0.01 in size next to a column of ones) it is large even when the factors are uncorrelated. Our kappa (from the factor correlation matrix) is the right quantity. | Real FF5 daily, 1963-07 to 2024-12: `results.condition_number` = **360.5**, our kappa = **2.15**, all VIF between 1.14 and 1.62. Synthetic uncorrelated factors: 103.4 vs 1.05. The skill's thresholds would fire on every regression. | Keep M3.4. Never read `results.condition_number`. Rename the schema field to something like `factor_corr_condition_number`, or state the definition in its description, so nobody later "fixes" it with the statsmodels value. | S |
| 7 | api-detail (gap) | M0.5, M2, CODING_STANDARDS 3 | statsmodels' default `missing="none"` does not check for NaN: one NaN in `y` makes every coefficient NaN without an error. The statsmodels skill recommends `missing="raise"`. Our M2 should prevent NaN reaching the fit, but the reference call has no last-line guard. | Verified: `sm.OLS(y_with_one_nan, X).fit().params` is all NaN, no warning; with `missing="raise"` it raises `MissingDataError`. | Add `missing="raise"` to the reference call in M0.5 (`sm.OLS(y, X, missing="raise")`) and to the oracle fixture. It changes no numbers. | S |
| 8 | gap | M3.2, M0.9 | The finance skill stresses that much apparent alpha disappears once momentum is controlled for. FF5 has no momentum factor. `docs/references.md` mentions this, but no label in the methodology does, so a user can read FF5 alpha as skill. | Carhart (1997); Fama and French (2015) leave momentum out of FF5. The Carhart toggle is in the "Next" horizon of the plan, not in v1. | Add one sentence to the alpha interpretation text in M3.2 until the momentum toggle exists: "Alpha is measured against the five Fama-French factors, which do not include momentum; part of it may be momentum exposure." | S |
| 9 | gap (owner decision) + do-not-adopt (threshold) | M3 (new), M1.4 A4 | The statsmodels skill recommends influence diagnostics (leverage, Cook's distance, DFFITS) with cut-offs such as Cook's D > 4/n. We have none. A few days (earnings, crashes) can move a single-stock beta noticeably; our audit flags extreme returns (A4) but not influential ones. The 4/n cut-off itself is useless on daily returns. | Real SPY vs FF5, 10 years, `n = 2512`: Cook's D > 4/n flags **144 days (5.7%)**. | If adopted: report, for each beta, the 5 days with the largest absolute DFBETAS (from `results.get_influence()` on the plain OLS fit) as an informational list. No threshold, no exclusion (rows are never dropped, CODING_STANDARDS section 3). | M |
| 10 | do-not-adopt | M0.2, M10 | The statsmodels skill's regime example reads `smoothed_marginal_probabilities` from `MarkovRegression`. Smoothed regime probabilities use later rows (two-sided Kim smoother), which breaks our no-look-ahead rule. Only `filtered_marginal_probabilities` are point-in-time. | Verified on a series with a variance break at row 250: at row 250 the filtered probability is 0.997, the smoothed one 0.530. The difference comes only from rows after 250. | No change now (our regimes are deterministic and lagged, M10.2). If Markov regimes are ever added, the spec must say "filtered probabilities only" and the look-ahead tests T102-T104 must cover them. | - |
| 11 | contradiction (we are right) / do-not-adopt | M0.5, D1 | The finance skill (and its script) judge loadings and alpha with classical iid OLS standard errors and an "absolute t above about 2" rule. Our spec uses Newey-West HAC and BH-corrected p-values (D1). On daily returns, classical errors are wrong in both directions. | Real SPY vs FF5, 10 years: HAC/OLS standard-error ratio is 0.74 for alpha and 1.66 to **4.35** for the five betas. Newey and West (1987); our T40/T41 already prove coverage. | No change. Do not copy the script or its rule. | - |
| 12 | contradiction (we are right) | M7, D5 | The finance skill's script estimates residual volatility with divisor `n-k-1` but its own tracking-error identity uses `sigma_fund * sqrt(1 - R^2)`, which is exact only with the same divisor for both, as in our D5 (`n-1`). | Algebra: with residuals of zero mean, `SSR/(n-1) = Var(y) (1 - R^2)` exactly. With `n-k-1` the identity is off by `sqrt((n-1)/(n-k-1))`, 2.6% for the skill's own 60-month, 3-factor example. | No change. Optionally cite this in D5 as the reason for `n-1`. | - |
| 13 | do-not-adopt | M6.1, M0.9 L-DESC, M12 | The finance skill decomposes expected return with assumed forward premia (loading times an assumed premium per factor) and calls the remainder "implied alpha". That is a forecast and conflicts with our descriptive, realised-mean attribution (M6.1) and with the rule that the report never says a factor "should" pay. Its premium table (1963-2024) is also partly off. | Our arithmetic daily means x 252, 1963-07 to 2024-12: Mkt-RF 7.14%, SMB 1.63%, HML **3.56%**, RMW 3.49%, CMA 3.05%. The skill gives 6-7%, 1.5-2%, **2.5-3%**, about 3%, about 3%. For 2015-2024 the same means are SMB -2.01%, HML -2.39%, CMA -1.26%, which shows how unstable "premia" are. | Do not add assumed-premia decompositions. Keep M6.1 (realised means). | - |
| 14 | do-not-adopt | M6.1, M6.4, M0.4, D6 | The AQR-style skill's attribution code: (a) defines alpha as total return minus factor contributions, folding the residual into alpha (our M6.4 keeps them separate); (b) divides each contribution by the total return, which explodes when the total is near zero; (c) labels a plain sum of simple returns "Total Return" (our M0.4 separates arithmetic sums from compounded returns); (d) multiplies exposures and factor returns of the same date, which is look-ahead when exposures are estimated from windows containing that date (our D6). Its 12-1 momentum indexes the first row of a 13-month window, so it measures about 13-1 months; its backtest subtracts trading costs from capital twice. | Code reading of `organizations/aqr/SKILL.md` (FactorAttribution, FactorBuilder.build_momentum_factor, RealisticBacktest.run_backtest). | No change. Our M6 already does each of these correctly; the list is a check for reviewers. | - |
| 15 | api-detail | M3.5 | `acorr_ljungbox(x, lags=10)` (as in the statsmodels skill) returns 10 tests, one per lag 1..10; `lags=[10]` (our spec) returns one. The skill's `model_df=2` applies to ARMA residuals; for regression residuals with exogenous regressors `model_df=0` (the default) is correct. | Verified: 10 rows vs 1 row. | Keep `lags=[10]`. Add to M3.5: "Use `lags=[10]` (one test). `model_df` stays 0: the regressors are not lagged values of `y`." | S |
| 16 | gap (owner decision) | M11.2 | The statsmodels skill's time-series workflow tests the order of integration before modelling. Engle-Granger assumes both legs are I(1); if a leg is stationary, a "cointegration" result is meaningless. We never check this. | Engle and Granger (1987). For log prices and cumulative excess-return indices I(1) is usually true, so this is a guard, not a frequent failure. | If adopted: per pair, an informational `adfuller(level, regression="ct", autolag="AIC", result_object=True)` on each leg and on its first difference; status `not_applicable` when a leg looks I(0). Not in any BH family. | S-M |
| 17 | do-not-adopt | M11.2 | The statsmodels skill pairs ADF with KPSS. KPSS on estimated cointegrating residuals needs special critical values (Shin 1994); standard `kpss` p-values are wrong there, for the same reason we drop in-sample `adfuller` p-values (M11.2 step 3). | Shin (1994), Econometric Theory 10(1). | Do not add KPSS to the cointegration panel. | - |
| 18 | api-detail (clarification) | M3.4 | Our M3.4 says `variance_inflation_factor` without a constant column "returns wrong values". That is true in principle (uncentred R-squared), but daily factor means are near zero, so the difference is negligible on French data. The statsmodels skill loops VIF over every column including the constant, which gives a meaningless VIF for the constant. | Real FF5 daily: VIF with and without a constant column agree to 4 decimals (1.2000, 1.1373, 1.4836, 1.1553, 1.6170). | Keep the rule (include the constant, report VIF only for columns 1-5). Optionally soften "wrong values" to "values that are not the textbook VIF; small for daily factors, large for monthly or level data". | S |
| 19 | gap (documentation) | M0.5, M2 | The statsmodels time-series reference warns against silently compressing time when rows are missing. Our HAC and Ljung-Box treat consecutive rows of `S` as adjacent, even when M2 excluded a row between them. | Follows from M0.3 and M2 (positional rows). Exclusions are rare, so the numerical effect is small. | Add one sentence to M0.5: "Lags are positional on `S`; an excluded row is skipped, not filled. The number of exclusions is in `SampleInfo`." | S |
| 20 | gap (references) | `docs/references.md` | Our references cite Newey and West (1987) only. The lag rule `floor(4 (m/100)^(2/9))` is the rule-of-thumb from Newey and West (1994). CUSUM, Engle-Granger p-values and Johansen have no reference. | Spec text M0.5, M9, M11. | Add Newey and West (1994), Review of Economic Studies 61(4); Ploberger and Kramer (1992); MacKinnon (1994, 2010) for the `coint` p-values; Johansen (1991). | S |

### 2.1 Items considered and dropped

- Breusch-Pagan and White heteroskedasticity tests (statsmodels skill): they would reject on every daily series and change nothing, because HAC is already robust to heteroskedasticity. ARCH-LM (finding 1) is the informative version.
- GLSAR or feasible GLS for autocorrelated errors (statsmodels skill): changes the estimator, not only the inference; conflicts with "OLS everywhere" (M0.5, CODING_STANDARDS section 4).
- Closet-index screen and breakeven information ratio (finance skill): fund concepts, not meaningful for a single stock.
- Harvey-Liu-Zhu "t > 3" (finance skill): a hurdle for discovering new factors, not for testing loadings on five pre-specified ones. BH within each family (M0.6) is the right tool here.
- Composite value, quality and long-short construction (AQR-style skill): we consume the French library's factors; we do not build factors.

---

## 3. Decision lists

### 3.1 Adopt

1. Rewrite the M3.5 Ljung-Box justification, label it as size-distorted under volatility clustering, and add ARCH-LM with `result_object=True` (finding 1 a-c).
2. Relabel the M9 CUSUM as an alpha-shift check and add a beta-break negative-control test to the oracle (finding 2).
3. Use `result_object=True` and named fields for `adfuller` (M11.2 step 6, T85) and any `het_arch` or `acorr_breusch_godfrey` call; refer to `coint` fields by name; add a "no FutureWarning" check (finding 3).
4. Reword D2 (statsmodels has no default HAC lag) and optionally add `"kernel": "bartlett"` to the reference call; state that `get_robustcov_results` is not used (finding 4).
5. Never use `results.condition_number`; make the schema field name or description say "factor correlation matrix" (finding 6).
6. Add `missing="raise"` to the OLS reference call (finding 7).
7. Add the "no momentum factor" sentence to the alpha interpretation (finding 8).
8. Pin Ljung-Box semantics (`lags=[10]`, `model_df=0`) in M3.5 (finding 15).
9. Document positional lags across excluded rows (finding 19).
10. Add the missing references (finding 20).

### 3.2 Reject

1. Post-hoc `get_robustcov_results` and a fixed HAC lag (finding 4).
2. Condition-number thresholds of 20/30 on the raw design (finding 6).
3. Cook's distance > 4/n or any automatic influence cut-off (finding 9).
4. Smoothed Markov regime probabilities (finding 10).
5. Classical OLS standard errors and the "|t| > 2" rule (finding 11).
6. Residual volatility with divisor `n-k-1` in the risk decomposition (finding 12).
7. Assumed-premia expected-return decomposition and the skill's premium table (finding 13).
8. The AQR-style attribution, momentum and backtest code (finding 14).
9. KPSS on cointegrating residuals (finding 17).
10. Breusch-Pagan, White and GLSAR (section 2.1).

### 3.3 Need owner decision

1. **Johansen `ComplexWarning`** (finding 5): allow one narrowly scoped, documented catch of `ComplexWarning` around `coint_johansen` plus an oracle cross-check of the trace statistic, or compute the Johansen eigenproblem ourselves. `CODING_STANDARDS.md` section 8 has to name the exception either way.
2. **Robust autocorrelation diagnostic** (finding 1 d): replace Ljung-Box by the HC0-robust Breusch-Godfrey (our own short auxiliary regression; statsmodels has no robust option in `acorr_breusch_godfrey`), or show both.
3. **Influential days** (finding 9): add an informational "top 5 days by DFBETAS per beta" list to the regression drawer, or leave influence out of v1.
4. **I(1) precondition for Engle-Granger** (finding 16): add per-leg ADF checks as an informational column with `not_applicable` status, or rely on the label L-EXPL.

---

## 4. Reviewer observations not taken from the skills

These came up while checking the skills. They are listed so they are not lost; they are outside the three skills' content.

- **European mode, non-synchronous closes.** The plan's European mode regresses European stock returns (converted to USD) on French factors. If US factors are ever used for a European stock, the closing times differ by several hours and same-day betas are biased towards zero; Dimson (1979) lead-lag betas or weekly returns are the standard fixes. With the French **Europe** factor file the problem mostly disappears, but the currency regressor needs the same check (the time stamp of the FX rate used for conversion).
- **Local data files vs spec.** `data/factors/ff5_daily.parquet` uses the display column names (`Mkt-RF`, `SMB`, ...) and `meta.json` uses keys (`last_download_at`, `last_modified`, `rows`, `first_date`) that differ from M1.1 (`downloaded_at`, `http_last_modified`, `last_attempt_at`, `last_attempt_ok`) and from CODING_STANDARDS section 1 (`mkt_rf, smb, ...`). The SPY price file uses `adj_close` rather than `Adj Close`. These may be outputs from before the spec; worth a check against M1.1 when the data layer is next touched.

---

## 5. Sources and attribution

- `statsmodels` skill, K-Dense-AI/scientific-agent-skills (MIT; front matter says BSD-3-Clause), version 1.5, reviewed 2026-10-01.
- `aqr-factor-investing` skill, copyleftdev/sk1llz (Apache-2.0), file last changed 2026-03-09.
- `factor-investing` skill, JoelLewis/finance_skills (MIT), last changed 2026-07-18.
- statsmodels 0.15.0 docstrings and observed behaviour in this repository's environment.
- Literature cited: Newey and West (1987, 1994); Ploberger and Kramer (1992); Kramer, Ploberger and Alt (1988); Lobato, Nankervis and Savin (2001); Romano and Thombs (1996); Engle and Granger (1987); MacKinnon (1994, 2010); Johansen (1991); Shin (1994); Carhart (1997); Fama and French (2015); Dimson (1979).
