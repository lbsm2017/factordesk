# Independent validation of the rolling-regression speed-up, 2026-11-18

Change under review: commit `752b856` "Speed up rolling regression with Gram-matrix batches and batched HAC sums" (merged into `feat/report-ui-feedback` at `f53fe5a`). Files: `backend/factordesk/analytics/rolling.py`, `backend/factordesk/tests/test_rolling_equivalence.py`, `backend/factordesk/tests/fixtures/reference.py`.

Claim tested: about 5x faster, with betas, standard errors and R2 unchanged to at most 1e-12 on real SPY and identical NaN positions.

Reviewer did not write the change. No source or test file was edited. Validation scripts live outside the repo (a scratch folder); they import the old implementation from `git show 752b856^:backend/factordesk/analytics/rolling.py` exported verbatim, not from the copy in `tests/fixtures/reference.py`. No network: SPY prices from `data/prices/SPY_2026-11-18.parquet` (same-day cache), factors from `data/factors/ff5_daily.parquet` (French file, data through 2026-09-30). Aligned SPY sample: 8,474 rows, 1993-02-01 to 2026-09-30. Environment: numpy 2.5.5, statsmodels 0.15.0, Windows 11.

Three references are used:

- **old**: the previous per-window QR implementation (`752b856^`).
- **statsmodels**: `sm.OLS(y, add_constant(F, has_constant="add"), missing="raise").fit(cov_type="HAC", cov_kwds={"maxlags": L, "kernel": "bartlett", "use_correction": False}, use_t=False)` with `L = hac_lags(W)` (4 for 126 and 252, 5 for 504). The shorter call `cov_kwds={"maxlags": L}` gives identical standard errors (max difference 0.0).
- **exact**: the M0.5 formula evaluated in exact rational arithmetic (Python `Fraction`) on the float inputs, rounded to float only at the end. Used for the windows where old and new disagree most, to say which one is right.

## Verdict

**ACCEPT WITH CONDITIONS.**

The claim holds as stated (real SPY, absolute differences): betas 6.95e-13, standard errors 1.11e-13, R2 1.1e-16, NaN positions identical, speed-up 4.5x to 6.8x. No look-ahead was found. The full SPY report JSON is identical except 30 full-precision `average_beta` statistics that move by at most 1.3e-13. Nothing found blocks the merge.

Conditions (none changes a reported number today):

1. **Correct the precision wording.** The new path is less accurate than the old one, by about three orders of magnitude, though still far below anything the report shows. On SPY, against the exact reference, the worst beta relative error is 1e-10 (new) vs 1e-13 (old). On synthetic inputs that still pass the fast-path guard (factors with means 20 to 30 times their spread, or 60x volatility regime shifts over 8,600 rows), beta errors reach 2e-8 relative (6.7e-9 of a standard error) and standard-error errors reach 1e-9. That is outside "1e-12" and outside the 1e-10 `rtol` that T48 uses for betas. The review note in `real-data-smoke-2026-11-18.md` and the docstrings should say "about 1e-12 absolute on real factor data; at most a few 1e-8 relative on adversarial designs the fast-path guard admits", not "unchanged".
2. **Record that a window now depends, at rounding level, on rows before it.** Cumulative sums mean a stamp's value changes in the last bits when an earlier row outside its window changes (up to 7e-15 measured) or when the requested start date changes (up to 7.9e-13 on SPY, against exactly 0 for the old code). This is not look-ahead and is invisible after the 6-significant-digit rounding of the JSON. But the M0.3 property ("exactly W rows") now holds mathematically, not bit for bit. A test that compares rolling values across different start dates with a tolerance of 0 would fail.
3. **Add one adversarial case to `test_rolling_equivalence.py`**: non-zero-mean factors near the `_FAST_MIN_CENTRED` limit on a long series with a volatility regime. The existing tests never come within a factor of 10 of the fast-path thresholds on the fast side, so they cannot detect a loosened threshold.

## Check 1. Independent statsmodels recomputation per window

Method: for each window length, pick the first and last stamp, 200 random stamps, the 25 fast-path windows closest to a fast-path threshold, the 25 exact-path windows closest to the threshold (when there are any), and the 25 windows with the smallest exact M3.1 share that still pass the guard. Routing is replicated in the script by copying the `healthy` expression from HEAD `rolling.py` (read-only). Fit each window with the statsmodels call above. Compare alpha, betas, their SEs and R2 with new and old. Windows where the new code returns NaN were checked against the exact guard: every one has share < 1e-6 or a constant factor, and no NaN appeared where the guard passes.

| Case | W | windows compared | new vs sm: beta abs | se abs | se rel | R2 abs | old vs sm: beta abs | se rel |
|---|---|---|---|---|---|---|---|---|
| SPY real | 126 | 227 | 5.6e-13 | 1.3e-13 | 5.3e-12 | 1.1e-16 | 3.8e-15 | 4.1e-12 |
| SPY real | 252 | 227 | 3.4e-13 | 6.6e-14 | 4.7e-12 | 1.1e-16 | 2.4e-15 | 1.7e-12 |
| SPY real | 504 | 226 | 1.5e-13 | 2.6e-14 | 2.0e-12 | 1.1e-16 | 3.4e-15 | 2.1e-12 |
| Synthetic guard-edge (constant, collinear, near-collinear stretches) | 126 | 247 (+20 NaN, all correctly guarded) | 4.9e-12 | 2.8e-11 | 2.8e-11 | 4.4e-16 | 4.8e-14 | 2.5e-11 |
| Synthetic guard-edge | 252 | 221 | 1.1e-13 | 7.6e-14 | 3.7e-13 | 6.7e-16 | 3.7e-15 | 3.7e-13 |

Relative beta differences are larger (up to 2.7e-9 on SPY, for both implementations alike), but only where a beta is close to zero. Alpha relative differences reach 8e-9 for the same reason (alpha about 1e-5 daily).

Result: every window is well inside the T50 tolerance (SE relative 1e-8). The SEs are as close to statsmodels as the old code's. The betas are about 100x farther from statsmodels than the old code's, still below 6e-13 absolute on SPY. Every SPY window at every window length takes the fast path, so on real data the exact path is never used.

Extra T48-style check on SPY (betas against `RollingOLS`, `rtol = 1e-10` as in `test_rolling.py`): both implementations fail it on a small number of near-zero betas. New: 261 of 41,745 elements at W=126, 166 of 41,115 at W=252, 38 at W=504. Old: 109, 110, 28. Smallest |beta| among the failures is about 5e-6. The test cannot tell the two apart; `RollingOLS` has its own rounding error.

## Check 2. Old vs new `rolling_betas`, end to end

Method: `rolling_betas(sample, W)` from both modules on `AnalysisSample`s built with `build_sample`. Raw `rolling_ols_hac` was used where no sample can be built (NaN input, too few rows). The script compares every stamp, the NaN maps, `window`, `lags`, `window_start`, `n_stamps` and `stamps`.

| Case | W | beta abs | SE abs | SE rel | R2 abs | NaN map | metadata |
|---|---|---|---|---|---|---|---|
| SPY real, n=8,474 | 126 | 6.95e-13 | 1.11e-13 | 9.1e-12 | 1.1e-16 | same | same |
| SPY real | 252 | 3.36e-13 | 6.60e-14 | 5.9e-12 | 1.1e-16 | same | same |
| SPY real | 504 | 1.75e-13 | 2.14e-14 | 1.5e-12 | 2.2e-16 | same | same |
| dgp_a seeds 101/202/303 (true betas 1.10, 0.30, -0.40, 0.25, 0.15), n=2,520 | 126 / 252 | <= 6.3e-14 | <= 2.5e-14 | <= 5.9e-14 | <= 5.6e-16 | same | same |
| SMB = 0 for 300 rows | 126 / 252 | 4.7e-13 | 1.7e-13 | 9.8e-14 | 5.6e-16 | same | same |
| RMW = 0.0021 (constant, non-zero) for 300 rows | 126 | 4.5e-11 | **1.1e+02** | **1.9e-3** | 4.4e-16 | same | same |
| same | 252 | 3.2e-12 | **1.0e+03** | **2.6e-2** | 4.4e-16 | same | same |
| HML/CMA correlation 0.999 over whole sample | 126 / 252 | 0 (bit-equal) | 4.7e-12 | 1.4e-12 | 0 | same | same |
| +300% return day | 126 / 252 | 9.6e-14 | 1.0e-13 | 2.9e-14 | 4.4e-16 | same | same |
| Mkt-RF = +50% day | 126 / 252 | 9.0e-14 | 1.3e-14 | 2.3e-13 | 4.4e-16 | same | same |
| exactly W rows (126, 252, 504) | W | <= 1.6e-15 | <= 5.6e-16 | <= 4.0e-15 | <= 2.2e-16 | same | same |
| W+1 rows (127, 253, 505) | W | <= 2.2e-15 | <= 3.3e-16 | <= 2.1e-15 | <= 2.2e-16 | same | same |
| minimum sample n=504 | 126/252/504 | <= 6.9e-15 | <= 1.7e-15 | <= 6.9e-15 | <= 4.4e-16 | same | same |
| n = W-1 | 126 | no stamps in both | | | | same | |

Errors are identical in type and text, old and new. NaN in y, NaN in a factor and inf in a factor raise `ValueError: inputs must be finite; excluded rows are removed upstream`. W=6 raises `ValueError: window 6 must exceed the number of parameters 6`. An all-NaN input shorter than W returns all-NaN without an error in both.

Speed (single run, this machine, `rolling_betas` only): SPY W=126 0.70 s to 0.16 s (4.5x), W=252 2.04 s to 0.30 s (6.8x), W=504 5.63 s to 1.05 s (5.4x). The 5x claim holds.

The RMW-constant case is the largest disagreement found. Old and new disagree by up to 2.6% in standard errors there. The affected windows are the ones that contain only a few rows where RMW varies. They pass the M3.1 guard, because the guard share is relative to the factor's own (tiny) variation. Their RMW SE is about 4e4 to 6e4 because the design is nearly singular. The exact reference shows both implementations are inaccurate there and the new one is the closer:

| Window | exact RMW SE | new rel error | old rel error | statsmodels rel error |
|---|---|---|---|---|
| row 724, W=126 (exact path) | 6.1e4 | 8.8e-4 | 1.5e-3 | 8.8e-4 |
| row 850, W=252 (exact path) | 3.7e4 | 2.3e-2 | 3.8e-2 | 2.9e-2 |

This is conditioning of the problem, not a regression. Those windows go to the per-window QR path in the new code, as intended; the difference comes from summing the Newey-West meat in a different order. It does refute "SEs unchanged" as a general statement. Such windows need a factor that is constant for months. That does not happen in the French data, but M3.1 lets these windows through with meaningless SEs in both implementations (a separate, pre-existing issue).

Exact reference on SPY, at the windows with the largest new-vs-old gaps (W=126 rows 6299 to 6301 and 7871/7874; W=252 rows 6292 to 6305):

| | beta rel error vs exact | SE rel error vs exact |
|---|---|---|
| new | 2e-11 to 3.2e-10 | 3e-13 to 9.1e-12 |
| old | 9e-15 to 6.3e-13 | 9e-16 to 2.5e-14 |
| statsmodels | 6e-14 to 7.2e-11 | 3e-15 to 8e-14 |

## Check 3. Look-ahead

Method (SPY real, n = 8,474): pick cutoffs `t`. For W=126: 137 cutoffs, every new-code chunk boundary (256 stamps) at offsets -1, 0 and +1, the first stamp, the last two rows and 40 random rows. For W=252: 44 cutoffs. Change every row after `t` in five ways and require every output at rows `<= t` (alpha, betas, SEs, R2, NaN map) to be bit-identical with `np.array_equal`. The five changes are:

- y + 0.05 and factors x 7;
- y and factors redrawn at 20x the scale with non-zero means;
- HML constant after `t`, which re-routes later windows in the same chunk to the exact path, or to NaN;
- CMA = 2 x HML after `t` (guard failure);
- y and factors x 1e6 (the cumulative sums explode).

The routing changes matter because they alter which windows of the same batch are solved together.

| Test | W=126 | W=252 |
|---|---|---|
| Mutation runs, new not bit-equal | 0 of 685 | 0 of 220 |
| Same runs, old not bit-equal | 0 of 685 | 0 of 220 |
| Non-vacuous: stamp `t+1` moves by | 0.42 | 0.021 |
| Truncation at `t` (T103 style, the sample ends at `t`), stamps `<= t` not bit-equal | 0 of 137 | 0 of 44 |
| Ex-ante shift (`ex_ante_betas` = betas `shift(1)`) | unchanged code, covered by T102 and T103 (pass) | |
| Synthetic dgp_a n=900 (repo-style mutation, every 7th row as cutoff) | 0 of 111 not bit-equal | |

Window membership (exactly W rows, M0.3). Perturbing the first row of the window at stamp `t` (y + 0.01) moves its betas by 8.7e-3 (W=126) and 1.4e-2 (W=252), so the window does contain that row. Perturbing the row just before the window moves the old code by exactly 0, and the new code by **6.6e-15 (W=126) and 2.7e-15 (W=252)**, with SEs moving by 8e-17. Starting the sample 3,000 rows later changes the new code's values on the shared stamps by up to **7.9e-13 (W=126) and 4.8e-13 (W=252)**, against exactly 0 for the old code. This is the cumulative-sum differencing. It is not look-ahead: no later row can enter. But the stamp is no longer a function of its W rows alone at the last-bits level (condition 2).

Result: no look-ahead. Outputs at dates `<= t` are bit-identical under every future change tried, including changes that re-route later windows in the same batch.

## Check 4. Numerical stability of the cumulative-sum Gram path

Method: 8,600-row synthetic series (true betas 1.10, 0.30, -0.40, 0.25, 0.15, sigma_e 0.012) under ten stress scenarios. W = 126 and 252. For each: share of stamps on the fast path (routing replicated from the HEAD code, read-only), whether every window routed to the exact path has betas bit-identical to the old QR code (evidence that the fallback really is the QR path), worst new-vs-old drift, and for the worst W=252 window, the error of each implementation against the exact reference.

| Scenario | W | fast share | exact-path windows bit-equal to old | beta abs | beta drift / own SE | SE rel | worst window vs exact: new / old beta rel |
|---|---|---|---|---|---|---|---|
| French-like means and spreads | 126 / 252 | 1.00 | n/a (none) | 1.5e-13 | 1.3e-12 | 1.4e-13 | (below 1e-11) |
| means = 5 sd | 252 | 1.00 | n/a | 7.9e-12 | 4.7e-11 | 6.0e-12 | 1.2e-10 / 1.6e-14 |
| means = 30 sd (css/sq about 1.1e-3, limit 1e-3) | 126 | 0.30 | yes (5,899) | 5.6e-10 | 2.5e-9 | 4.6e-10 | |
| same | 252 | 0.53 | yes (3,968) | 4.6e-10 | 2.5e-9 | 2.1e-10 | 1.3e-8 / 6.6e-14 |
| means = 40 sd (outside limit) | 126 / 252 | 0.00 | yes (all) | 0 | 0 | 1.4e-11 | |
| magnitudes 1e-4 to 1e3 across factors, means 3 sd | 252 | 1.00 | n/a | 1.5e-6 (betas up to 1e4) | 1.0e-9 | 4.0e-11 | 7.9e-10 / 1.5e-13 |
| y offset +1.0 | 252 | 1.00 | n/a | 2.6e-12 | 1.5e-11 | 1.7e-12 | 2.0e-11 / 2.2e-13 |
| first 7,000 rows 30x more volatile | 252 | 0.84 | yes (1,352) | 3.9e-11 | 5.1e-11 | 1.8e-11 | 2.4e-11 / 1.1e-14 |
| first 8,000 rows 60x more volatile, means 20 sd | 126 | 1.00 | n/a | 6.3e-10 | 6.7e-9 | 6.1e-10 | |
| same | 252 | 1.00 | n/a | 3.6e-10 | 4.8e-9 | 4.1e-10 | **2.1e-8** / 5.1e-14 |
| first 8,000 rows 80x more volatile, means 30 sd | 126 | 0.97 | yes (272) | 9.2e-10 | 5.1e-9 | 7.2e-10 | |
| same | 252 | 0.995 | yes (42) | 5.1e-10 | 6.4e-9 | 4.5e-10 | 1.2e-8 / 7.6e-14 |
| first 8,000 rows 95x more volatile, means 30 sd | 252 | 0.96 | yes (321) | 5.6e-10 | 4.3e-9 | 6.4e-10 | 6.9e-9 / 1.3e-14 |

Worst drift found: beta 2.1e-8 relative to the exact value (6.7e-9 of its own standard error), SE 1.0e-9 relative (W=126 of the 95x scenario). It occurs at windows whose fast-path margin is about 0 (log10 0.00 to 0.37), that is, windows that only just qualify. The fallback works as claimed. Every window the guard rejects is solved by the QR path with betas bit-identical to the old code, and NaN maps were identical in every scenario. The thresholds do not hold the claimed twelve digits, though: they hold about eight in the worst case. Those inputs are unlike French daily factors (means about 0.03 sd) but within what the API accepts for any factor frame. The 6-significant-digit JSON rounding (relative 5e-6) hides all of it.

## Check 5. Full pipeline equivalence

Method: `git worktree add --detach` of `752b856^` into the scratch folder (removed afterwards). The same script ran `assemble_report` there (`PYTHONPATH` pointing at the worktree; `factordesk.__file__` confirmed) and at HEAD, with fixed `now` and `factors_downloaded_at`, and dumped `model_dump(mode="json")`. Between `752b856^` and HEAD, the only backend change that reaches `assemble_report` is `rolling.py` (the others are API, CLI and HTML rendering).

| Case | leaves | differing leaves | fields that differ | max abs | max rel |
|---|---|---|---|---|---|
| SPY, default windows (126, 252; primary 252) | 220,844 | 30 | `average_beta.factors[*].{mean, sd, p10, p90, min, max}` | 1.3e-13 | 5.0e-12 |
| SPY, primary window 504 | 322,551 | 30 | same | 9.3e-14 | 4.3e-11 |
| SPY, start 2015-01-02 | 88,291 | 29 | same | 1.4e-14 | 1.3e-12 |
| dgp_a, n=3,000 | 78,404 | 30 | same | 2.3e-14 | 1.4e-13 |
| dgp_g (fat tails, GARCH), n=3,000 | 78,404 | 30 | same | 1.3e-14 | 3.0e-13 |

Every rolling series (betas, SEs, R2, dates, statuses), the regression, attribution, diagnostics, gate, warnings and audit are identical. The 6-significant-digit rounding produced no flip in any of the about 780,000 compared leaves. `average_beta` is kept at full precision, so it shows the 1e-13-level drift. `share_positive` and `n_stamps` are unchanged.

## Check 6. Repository tests

`uv run pytest backend/factordesk/tests/test_rolling_equivalence.py backend/factordesk/tests/test_rolling.py backend/factordesk/tests/test_lookahead.py -q`: 38 passed, 50 deselected (the `slow` marker is excluded by `addopts`). With `-m "not live"`: 88 passed. `ruff check` and `pyright` on `rolling.py`: clean.

Note on the new tests: `test_rolling_equivalence.py` compares with a tolerance of 1e-9 (1e-8 on guard windows). That is looser than the 1e-12 in the claim. Given Check 4 it is about right, but the review note should quote the tolerance the tests enforce.

## Not checked

- Exact-rational reference only for 21 windows (it takes 2 to 6 s per window). Every other comparison is against statsmodels or the old code.
- W=504 was covered in Checks 1, 2 and 5, not in the stress scenarios of Check 4 or the mutation runs of Check 3.
- Other BLAS/LAPACK builds, other CPUs, Linux or macOS: bit-identity statements (look-ahead, fallback equal to the old QR) were measured on this Windows numpy 2.5.5 build only.
- The `slow` property-based sweeps were run once, not with extra seeds.
- Timing used one run per case on a machine with other jobs; the speed-up figures are indicative.
- No real ticker other than SPY was available offline, so the claim on real data rests on one series (n = 8,474).
- Memory use of the new chunking was not measured.

## Conditions met, 2026-11-18

Branch `fix/rolling-validation-conditions`. Gates: `pytest`, `ruff check`, `pyright` pass.

1. **Precision wording.** The docstrings of `rolling.py`, `docs/methodology.md` (M0.5 and decision D32), `docs/test-oracle.md` (tolerance table, T50) and the status line of `real-data-smoke-2026-11-18.md` now state the measured numbers: about 1e-12 absolute on real data (SPY 6.9e-13 on betas, 1.1e-13 on standard errors against the QR path; about 1e-10 relative from exact at the worst windows) and at most a few 1e-11 on designs the guard admits. The guard was tightened: factor variance at least 1e-2 of its mean square (was 1e-3), and the window's centred sum of squares at least 1e-3 of the running sum of squares (was 1e-4 of the uncentred sum). Speed cost: none measurable. On SPY (W = 126, 252, 504) and on an 8,600-row synthetic series (`dgp_a`) every window still takes the fast path (0 windows to QR), the outputs are bit-identical to those of the earlier thresholds, and timings agree within run-to-run noise (SPY W = 126: 0.49 s before, 0.46 s after; W = 252: 0.79 s and 0.78 s; W = 504: 1.37 s and 1.43 s; the previous QR code takes 2.4 s, 4.3 s and 9.2 s). Worst error on 11 volatility-regime designs (vol ratio 30 to 1,000, factor means 0 to 30 standard deviations, W = 126 and 252): 7.8e-12 absolute on betas and 8.5e-12 relative on standard errors against the QR implementation, against up to 5.1e-9 on betas and 3.4e-8 on standard errors with the earlier thresholds on the same designs.
2. **Start-date dependence.** Documented in the same places (no document of the dashboard claims bit-identical results across ranges, so the dashboard documents are unchanged). Tests `test_start_date_effect_is_rounding_level` (DGP-A and DGP-G, starts 1 to 3,000, bound 1e-11 on betas and standard errors, measured 1e-13) and `test_start_date_effect_on_a_volatility_regime` (bound 1e-10, measured 3e-11).
3. **Adversarial cases.** `test_rolling_adversarial.py`: correlation 0.99, 0.999, 0.9999; factor means of 5, 8 and 30 standard deviations; one huge outlier in `y` or in a factor; factor scales 1e-8 to 1e4. Each is compared with the previous QR implementation and with statsmodels, and routing is observed by a recording wrapper of `_exact_windows`; the cases that must fall back are asserted to reach QR for every window. Bounds are about ten times the measured errors and are stated in each test. Restoring the earlier thresholds, or loosening the pivot share to 1e-5, makes the tests fail.
