# Shrunk betas: independent validation

Date: 2026-11-18. Branch under review: `feat/shrunk-betas` at `73d2e01` (code as of `b1331d8`), checked out as `validate/shrunk-betas`.
Inputs: the cached files in `data/` of this worktree. The SHA-256 values of all six parquet files equal the hand-off table (section 7.1). All files are CRSP vintage 202609 and end on 2026-09-30. No network was used.
Environment: Python 3.13.14, numpy 2.5.5, scipy 1.18.1, statsmodels 0.15.0, pandas 3.1.1.
Scratch scripts (outside git): `validate-shrunk-betas-scratch/recompute.py`, `handcases.py`, `compare.py`, `adversarial.py`, `freshness.py`, `sim.py`.

**Verdict: ACCEPT WITH CONDITIONS.** Every number in the section matches an independent recomputation to between 1e-15 and 4e-10. The statuses, the look-ahead protection, the vintage checks and the cache paths behave as the spec says. The conditions concern wording only: what the "Pull" column claims to mean, and one label text. No condition blocks the merge if the owner accepts them as follow-ups (section 7).

---

## 1. Method

1. Before reading any implementation file I read only the hand-off, `docs/specs/shrunk-betas.md`, `docs/research-protocol.md`, `docs/methodology.md` (M0, M2, M4) and `docs/test-oracle.md`.
2. I wrote my own recomputation (`recompute.py`). It reads the parquet files with pandas and does not import `factordesk`. It covers:
   - the M2 sample: `adj_close` returns, the French-date alignment rule, and excess returns;
   - the M0.5 reference call `sm.OLS(...).fit(cov_type="HAC", maxlags=L, kernel="bartlett", use_correction=False, use_t=False)`. I cross-checked it with my own Bartlett sandwich (betas agree to 7e-15, covariance to 3e-12 relative);
   - the prior of SB2.2, the posterior of SB3 and the power numbers of SB5.
3. I produced the report with `uv run factordesk report SPY --json --out <scratch>/run1`, then again into `run2`, and compared the `shrunk_betas` list with my numbers.
4. After that comparison I read the code and ran the adversarial checks through `pipeline.assemble_report`, with the real cached files injected as `SectionInputs`.

## 2. Recomputation against the hand-off and the report

### 2.1 Sample, lags, prior

| Quantity | Mine | Hand-off | Report |
| --- | --- | --- | --- |
| n, first, last | 8474, 1993-02-01, 2026-09-30, 0 excluded | same | same |
| L(8474), L(504), L(252), L(2520) | 10, 5, 4, 8 | same | `hac_lags` 10 (full), 4 (window) |
| Prior window | 2016-09-21 to 2026-09-30, 2520 rows | same | same |
| Usable portfolios | 49 industry, 75 size (0 dropped) | same | `{"industry49": 49, "size_char75": 75}` |
| tau A (49 industries) | 0.209349, 0.407894, 0.341372, 0.280467, 0.253599 | same | max diff 3.3e-16 |
| tau B (75 size-characteristic) | 0.063014, 0.764220, 0.328910, 0.328693, 0.220502 | same | max diff 6.7e-16 |
| Default tau | 0.209349, 0.764220, 0.341372, 0.328693, 0.253599 | same | max diff 6.7e-16 |
| Mean betas, A / B (SB8.4) | 0.946, 0.259, 0.143, 0.082, 0.094 / 0.994, 0.619, 0.161, -0.090, 0.033 | SB8.4 same | - |

### 2.2 SPY regressions (my values; all equal the hand-off section 3.2 to the 6 printed digits)

| Scope | Factor | OLS | se HAC | Shrunk | sd post | Pull | 95% credible interval | MDE80 | Extra years | moved_away |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Full, L 10 | Mkt-RF | 1.009307 | 0.006648 | 1.009238 | 0.006642 | 0.001007 | [0.996219, 1.022257] | 0.022719 | (none) | F |
| | SMB | -0.147573 | 0.006168 | -0.147548 | 0.006167 | 0.000065 | [-0.159635, -0.135461] | 0.021079 | 0 | F |
| | HML | 0.007112 | 0.008729 | 0.007206 | 0.008720 | 0.000653 | [-0.009885, 0.024298] | 0.029830 | 0 | **T** |
| | RMW | 0.087762 | 0.009364 | 0.087647 | 0.009358 | 0.000810 | [0.069307, 0.105988] | 0.032002 | 0 | F |
| | CMA | 0.060741 | 0.011204 | 0.060586 | 0.011190 | 0.001947 | [0.038655, 0.082517] | 0.038290 | 0 | F |
| Last 504, L 5 | Mkt-RF | 1.011590 | 0.019482 | 1.011382 | 0.019383 | 0.008572 | [0.973393, 1.049372] | 0.066580 | (none) | F |
| | SMB | -0.089326 | 0.013065 | -0.089283 | 0.013049 | 0.000292 | [-0.114858, -0.063707] | 0.044648 | 0 | F |
| | HML | 0.007472 | 0.011972 | 0.007494 | 0.011958 | 0.001227 | [-0.015943, 0.030931] | 0.040915 | 0 | **T** |
| | RMW | 0.028211 | 0.013991 | 0.028128 | 0.013959 | 0.001803 | [0.000770, 0.055487] | 0.047813 | 0 | F |
| | CMA | 0.023622 | 0.012340 | 0.023502 | 0.012296 | 0.002351 | [-0.000598, 0.047602] | 0.042172 | 0 | F |
| Last 252, L 4 | Mkt-RF | 0.989937 | 0.006603 | 0.989928 | 0.006596 | 0.000993 | [0.977001, 1.002855] | 0.022564 | (none) | **T** |
| | SMB | -0.102140 | 0.022655 | -0.102042 | 0.022609 | 0.000875 | [-0.146354, -0.057729] | 0.077422 | 1.397656 | F |
| | HML | 0.026463 | 0.014720 | 0.026394 | 0.014691 | 0.001852 | [-0.002400, 0.055188] | 0.050306 | 0.012281 | F |
| | RMW | 0.010865 | 0.013685 | 0.010921 | 0.013658 | 0.001726 | [-0.015847, 0.037690] | 0.046768 | 0 | **T** |
| | CMA | -0.006103 | 0.009454 | -0.006102 | 0.009445 | 0.001387 | [-0.024614, 0.012411] | 0.032310 | 0 | F |

Identities `b_post = (I - S_w) b + S_w m0` and `V_post V^-1 + S_w = I` hold to 3.6e-15 in all three fits. cond(V) is 15, 45 and 87.

### 2.3 Report JSON against my numbers (both scopes; tolerance from hand-off section 7.3)

| Field | Max abs diff | Max rel diff | Tolerance | Pass |
| --- | --- | --- | --- | --- |
| prior.tau, tau_by_cross_section | 6.7e-16 | 1.3e-15 | 1e-6 | yes |
| beta_ols | 1.1e-15 | 5.6e-14 | 1e-8 | yes |
| se_hac | 2.1e-15 | 2.3e-13 | 1e-8 | yes |
| beta_shrunk | 7.5e-15 | 2.4e-13 | 1e-8 | yes |
| sd_post | 2.1e-15 | 2.3e-13 | (none stated) | yes |
| pull | 6.3e-16 | 4.5e-13 | 1e-8 | yes |
| cred95_low, cred95_high | 3.5e-10 | 9.5e-08 | 1e-6 | yes (1) |
| mde80 | 7.3e-15 | 2.3e-13 | 1e-8 | yes |
| extra_years_to_detect_delta (style factors) | 2.3e-13 | 8.6e-12 | 1e-5 | yes |
| moved_away | identical | | exact | yes |
| status / reason | `ok` / null for both scopes | | exact | yes |
| hac_lags, window | 10 / null; 4 / 252 | | exact | yes |
| labels | `L-DESC, L-SHRINK, L-SHRINK-PRIOR, L-CRED, L-MDE, L-CORR-MOVE` for both scopes (L-CORR-MOVE because at least one `moved_away` is true, as SB6 says) | | | yes |

(1) The spec rounds the multiplier to 1.959964. The code uses the exact normal quantile, which explains the 1e-10 difference.

Power sentences: all ten sentences match SB5 in years, MDE and extra-years values. They match the hand-off examples word for word: "about 1.4 more years" (252-row SMB), "less than 0.1 more years" (252-row HML) and "An SMB beta of 0.05 is already detectable". Mkt-RF gets the MDE sentence and no years sentence. One wording difference: SB5 says "A beta of 0.05 is already detectable."; the code names the factor ("An SMB beta of ..."). This reads better, but the spec should be updated to match.

The 504-row fit is not a report scope. It matches the hand-off and SB8.1.

### 2.4 Spec worked examples

- **SB8.1 (SPY):** reproduced (table above).
- **SB8.2 (RDDT):** reproduced from the cached `RDDT_2026-11-18.parquet` (n 633, 2024-03-22 to 2026-09-30, L 6).
  - OLS 1.483, 0.309, -1.015, -0.828, -0.155; se 0.222, 0.263, 0.292, 0.358, 0.543.
  - Shrunk 1.327, 0.326, -0.793, -0.571, -0.120; posterior sd 0.149, 0.235, 0.208, 0.233, 0.228.
  - Intervals: [1.035, 1.620], [-0.135, 0.787], [-1.200, -0.386], [-1.028, -0.114], [-0.567, 0.326].
  - Pull (HAC V) 0.508, 0.095, 0.370, 0.504, 0.806; with the OLS V 0.48, 0.13, 0.41, 0.46, 0.68.
  - MDE80 0.76, 0.90, 1.00, 1.22, 1.86; extra years 807, 998, 1500, 3457. Only SMB has `moved_away`.
  - All of these equal SB8.2 to the printed digits.
- **TSB04, TSB08, TSB10:** reproduced exactly.
  - TSB04: pull 0.5, b_post 0.3, V_post 0.02.
  - TSB08: tau = (0.2, 0.8, 0.3, 0.05, 0.1).
  - TSB10: MDE 0.068349, n_req 941.792, extra 1.73727; 0 for se 0.001 with n 2520; 9502 years ("not detectable") for se 0.9 with n 633.
- **TSB05 correction:** I checked it with exact rational arithmetic (`fractions`), with V = [[0.04, 0.036], [0.036, 0.04]], tau = (10, 0.1), m0 = 0:
  - Original input b = (0.5, 0.5): b_post = (21875/156272, 125005/1250176) = (0.13998, 0.09999). The first coefficient moves **toward** 0, so `moved_away` is (False, False). The first-draft assertion `b_post[0] > 0.5` was wrong, as the hand-off says.
  - Corrected input b = (0.5, -0.5): b_post = (134375/156272, -125095/1250176) = (0.85988, -0.10006), and `moved_away` is (True, False). This matches the corrected spec ("about 0.86") and the test in `test_shrinkage.py`.
  - The pull is (0.00014, 0.79995) in both cases.
  - **The correction is right.**
- **SB8.3 with a fresh seed** (own code, DGP-SB, n 504, R 4000, seed 777001):

  | Case | Per-factor MSE ratio | Total ratio | Coverage | SB8.3 says |
  | --- | --- | --- | --- | --- |
  | Prior correct | 0.82, 0.92, 0.61, 0.66, 0.44 | 0.604 | 0.940 to 0.946 | 0.61; 0.936 to 0.946 |
  | c = 2 | 1.24, 1.11, 1.14, 1.29, 1.13 | 1.179 | 0.768 to 0.918 | 1.19; 0.77 to 0.91 |

  Both claims hold.

### 2.5 The 252-row and 504-row HAC standard errors (hand-off section 5)

I confirmed that the cause sits in the data.

- In the last 504 rows, the lag-1 autocorrelation of `e_t * Mkt-RF_t` is 0.37. It is dominated by 2025-04-03 to 2025-04-10: 2025-04-09 alone contributes 0.00067, about ten times any other day.
- Without April 2025 that autocorrelation falls to 0.03, and the Mkt-RF HAC se falls from 0.0195 to 0.0054.
- The last 252 rows start on 2025-09-30, after that stretch.

## 3. Determinism

Two CLI runs give byte-identical HTML. The JSON files differ only in `generated_at`. Two in-process runs give identical sections. The section built through `assemble_report` with injected inputs equals the CLI section (apart from `sample`, which is the same object). The cache files were unchanged after the runs (same SHA-256 before and after).

## 4. Adversarial checks (after reading the code)

| Check | Result |
| --- | --- |
| Look-ahead, pipeline level: report with `end=2024-12-31`; every factor row and every portfolio row after that date replaced with noise | Both scopes are identical to the run without noise. Prior window 2014-12-26 to 2024-12-31. My independent prior for that end date agrees to 1.1e-16 |
| The same check bites: one portfolio row inside the window changed (2023-06-01) | tau changes |
| Latest window uses only its window: SPY prices before 2025-06-30 multiplied by noise | `latest_window` is identical; `full_sample` changes |
| CRSP stamp mismatch between portfolio files (one file set to 202610) | Both scopes `failed`, reason names the stamps and `prior_vintage_mismatch` |
| Factor frame carrying stamp 202608 | `failed`, `prior_vintage_mismatch` |
| One portfolio file one row shorter (ends 2026-09-29) | `failed`, `prior_vintage_mismatch` |
| Factor file ending 2026-08-31, portfolios ending 2026-09-30 | `failed`, `prior_vintage_mismatch` |
| No stamps known, same last dates | `ok`. The last-date check is the only check left, as documented in `vintage_problem` |
| One file missing; empty mapping | `failed`, `prior_unavailable` |
| 39 usable industry portfolios (10 columns with a NaN inside the window) | `insufficient_data`, `prior_cross_section_too_small` |
| 40 usable portfolios | `ok`, `n_portfolios.industry49 = 40` |
| NaN only before the window | Column kept (49) |
| Factor file starting 2016-10-01 (2512 rows to T_end) | `insufficient_data`, "Only 2512 factor rows ... needs 2520" |
| Singular V (rank one plus 1e-17) | `SingularCovarianceError`. cond 1e11 is accepted. The hook path is pinned by `test_singular_covariance_is_failed` |
| Every scope that is not `ok` | 0 floats outside `sample`; `prior` null; `betas` and `power` empty; labels `["L-DESC"]`. `hac_lags` is an integer |
| Short history: DGP-A stock with 600 rows, sigma_e 0.03, true beta (1.3, 0.8, -0.6, -0.4, 0.2), on the last 600 French dates, with the real prior | Both scopes `ok` (n 600, L 5; window 252, L 4). Pulls are 0.29, 0.06, 0.25, 0.33, 0.52 (full) and 0.57, 0.15, 0.45, 0.41, 0.75 (252 rows). They are visible and ordered by noise, and largest for CMA, the noisiest. Every field equals my recomputation to 5e-9. SMB has `moved_away` in both scopes. The power sentences say "not detectable ... more than 50 years" |
| Panels: `moved_away` and L-CORR-MOVE shown only where pull >= 0.05 | SPY static panel: no "Moved away", no L-CORR-MOVE text, the no-pull line once per scope. Short-history panel: "Moved away from typical" twice (SMB in each scope, pulls 0.06 and 0.15) and the L-CORR-MOVE text in "How this is computed". The React panel applies the same rule (`movedAway: marked && moved_away`, with the pull clipped to [0, 1] before the 0.05 test, as in the static panel) |

Freshness, with a fake fetcher and a copy of the cache in scratch:

| Path | Result |
| --- | --- |
| Fresh cache (2026-11-01) | No fetch |
| Stale cache, server answers 304 | Each file is requested with `If-Modified-Since` equal to its cached `Last-Modified`. Parquet files are unchanged and only `downloaded_at` in the sidecar moves. A second load one hour later makes no request (12 h gate) |
| Stale cache, fetch fails | Old cache served, all files byte-identical, no `.tmp` left |
| Stale cache, garbage payload | Parse fails, old cache served, files identical |
| No cache, fetch fails | Key absent, so the hook reports `prior_unavailable` |
| `factor_last_date` after the cached last date | All four files re-requested |
| New-vintage zip (stamp 202610, with an extra equal-weighted block) | Cache replaced; stamp 202610 and the SHA-256 of the zip recorded; value-weighted values equal to the source; equal-weighted block not read |
| `os.replace` failing during the write | Error raised; old parquet intact; no temporary file left. Through `load_portfolio_frames` the old cache is served |
| Manual refresh with the second file failing | Conditional requests, stops after the failure, raises `PortfolioError` with a plain sentence, parquet files intact |
| Downloads one after the other | 1 s pause between downloads |
| `http_fetch` over an httpx mock transport | Sends `If-Modified-Since` only when given; a 304 returns `(None, Last-Modified)` |

## 5. Test runs

- `uv run pytest test_shrinkage.py test_shrinkage_prior.py test_portfolios.py test_section_shrunk.py test_panel_shrunk.py -q`: **108 passed**, 4 deselected (27 s).
- `uv run pytest backend/factordesk/tests -m slow -k shrink -q`: **3 passed** (TSB12/13, TSB14, TSB15; 29 s).
- vitest `ShrunkBetasPanel.test.tsx` and `panelRegistry.test.tsx`: **20 passed**. These ran on a copy of the frontend in the scratch folder, using the `node_modules` of the `feat-shrunk-betas` worktree (same lockfile). Vitest wrote 57 transform-cache files into that ignored `node_modules/.vitest-cache`. I deleted them afterwards; nothing tracked was touched.

## 6. Findings

1. **"Pull" does not mean what the panel note says when V is not diagonal (spec-level, display wording).**
   - SB0.2 and the pull note say: "Pull is the share of the way from the OLS beta to its typical value". But `S_w[j, j]` is the weight on the prior for this beta alone. The actual share `(b_post - b) / (m0 - b)` also contains the moves of the correlated coefficients.
   - RDDT: CMA pull 0.81 against an actual share of 0.22; Mkt-RF 0.51 against 0.32; RMW 0.50 against 0.31; HML 0.37 against 0.22; SMB 0.09 against -0.06 (moved away).
   - Short-history synthetic stock (section 4): SMB shows "Pull 6.0%" next to "Moved away from typical".
   - The React tooltip reads "pulled toward typical to +0.468 ... pull 6.0%; moved away from its typical value".
   - No number is wrong. Only the sentence is.
2. **L-SHRINK-PRIOR text differs from SB6 and refers to a table that does not exist.**
   - The code text is "... spread from the Ken French industry and size portfolios (values in the table)". Neither panel has a prior table any more: the values are in the sentence just before it.
   - SB6 has a template with `{m0}`, `{tau}`, `{n_A}`, `{n_B}`, `{start}`, `{end}`.
   - So hand-off 7.3(c), "texts equal SB6", holds for L-SHRINK, L-CRED and L-CORR-MOVE, but not for L-SHRINK-PRIOR. L-MDE is a definition sentence; the SB5 templates are in the `power` texts.
   - L-SHRINK still says "bars" (open owner decision 3).
3. **The CLI path does not pass `factor_last_date`** (`build_report` calls `load_section_inputs`, which calls `load_shrinkage_inputs(now, offline=...)`); the dashboard path (`api/deps.py`) does. The effect is small: French releases come more than 40 days after the previous last date, so the stale rule triggers the re-download anyway. In the worst case the section is `failed / prior_vintage_mismatch`, never a mixed-vintage number. Minor.
4. **The vintage check compares the factor file's CRSP stamp only when the factor frame carries one**, and the factor loader does not record one today. The last-date comparison catches every realistic mismatch (tested). Minor, and documented in the code.
5. **`latest_window.sample` describes the whole sample** (n 8474, start 1993-02-01), with `window` = 252. M0.8 asks for the actual first and last dates used. This is already listed in hand-off section 5. Minor.

## 7. Conditions

1. **C1 (wording, owner text).** Make the pull note and the marker tooltip true for correlated estimates. Two options:
   - say that the pull is the weight the prior gets for this beta on its own, and that the actual move can be smaller, larger or away from typical with correlated factors; or
   - also show the actual share `(b_post - b) / (m0 - b)`.

   Remove "pulled toward typical" from the tooltip of rows that moved away. Update SB0.2 to match.
2. **C2 (wording).** Replace "(values in the table)" in L-SHRINK-PRIOR, either by the SB6 template filled from the prior or by "(values above)". Then either align SB6 with the code, or the code with SB6. Sync the SB5 "already detectable" sentence with the factor-named form the code uses.
3. **C3 (small, may follow the merge).** Pass `factor_last_date` on the CLI path too, so both entry points follow SB10.4 Q2 in the same way.

None of C1 to C3 changes a number. C1 and C2 concern the owner's texts. If the owner prefers to merge first, C1 should still be done before the panel is shown to users with short histories, because that is where the pull is visible.

## 8. What I could not check

- TSB20 (live) and any download from the Ken French site: no network was used. The freshness paths were tested only with fake fetchers and a mock transport.
- The frontend typecheck, lint, build, size budget and browser smoke test, and the full Python and vitest suites. I ran only the listed files and two vitest files.
- How the React panel looks: I tested its rule by reading the code and running its tests, not in a browser.
- The decade stability table of SB2.2, the SB8.3 rows other than c = 1 and c = 2, and the serially correlated DGP. TSB15 passed in the repo's slow test; I did not re-simulate it.
- The RDDT numbers rest on the cached RDDT file (SHA-256 `9fe2d18e...`), which is not listed in the hand-off.
- TSB18 (OLS untouched) beyond the repo test: I did not diff a full report with and without the section. The shrunk section's `beta_ols` equals my independent OLS.

## 9. Conditions met (2026-11-18)

The three conditions of section 7 were met on branch `feat/shrunk-betas`, one commit each, with no change to any number:

- **C1** (commit `350ff34`): the pull note, the legend, the React marker tooltip and the schema description of `pull` now say that pull is the weight the prior gets on a beta by itself, and that the beta can move less, more or away from typical when factors are estimated together. A row that moved away is no longer called "pulled toward typical". Tests on both panels pin the words.
- **C2** (commit `781dce7`): L-SHRINK-PRIOR says "(values above)", which is where the prior values are. Proposed spec edits for SB6 and the SB5 "already detectable" sentence are in section 9 of `shrunk-betas-handoff-2026-11-18.md`; the spec itself is not edited.
- **C3** (this commit): the CLI path passes `factor_last_date`, as the dashboard does; test in `test_cli.py`.

Gates after the three commits: pytest 651 passed (209 `slow` and `live` deselected), ruff and pyright clean, frontend typecheck and lint clean, vitest 399 passed, build, size budget and the browser smoke test pass.
