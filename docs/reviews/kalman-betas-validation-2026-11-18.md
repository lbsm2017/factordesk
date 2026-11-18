# Kalman-filter betas: independent validation

Date: 2026-11-18. Branch under review: `feat/kalman-betas` at `afacc76`, checked out as `validate/kalman-betas`.

What I read first: the spec `docs/specs/kalman-betas.md`, the handoff `docs/validation/kalman-betas-handoff-2026-11-18.md`, and the contract `docs/specs/schema-v3-contract.md`. Then the code: `analytics/kalman.py`, `report/sections/kalman.py`, `section_hooks/kalman.py`, `report/panels/kalman.py`, `report/kalman_text.json`, `KalmanPanel.tsx` and the tests.

Inputs:

- `data/prices/SPY_2026-11-18.parquet` and `data/factors/ff5_daily.parquet`, copied from the main checkout. Their SHA-256 values match the handoff (`5223e94f...` and `01657448...`).
- MSTR was not cached anywhere. I downloaded it once with the project's own yfinance call: 7,154 price rows, 1998-06-11 to 2026-11-17, with splits on 2000-01-27, 2002-07-31 and 2024-08-08, as KB9.2 says. The file is in the ignored `data/` folder and is not committed.

Environment: Python 3.13.14, numpy 2.5.5, statsmodels 0.15.0, pandas 3.1.1, Windows 11. Other work was running on the machine, so timings are noisy.

Scratch scripts (outside git): `indep.py` (my own filter), `compare_synth.py`, `compare_spy.py`, `contract_checks.py`, `mutate.py`, `mstr.py`.

**Verdict: merge with conditions.**

The statistics are right. I wrote my own implementation from the spec, with a different structure. It matches the module to within 3e-13 on the betas and 1e-11 (relative) on the drift rates, both on synthetic data and on all 8,474 SPY rows. Filtered and ex-ante values use no later data. The section-size and runtime claims hold.

Four things must be fixed before merge (section 6):

- one wrong sentence that both panels print;
- a hook that can stop the whole report from building;
- a test gap: the default test suite (the one CI runs) never checked the drift term;
- the owner has not yet signed off the edits to contract files.

---

## 1. Findings, most severe first

### F1 (medium). The hook catches errors only around the filter call

Where: `backend/factordesk/section_hooks/kalman.py:179-186`.

The `try` block wraps only `kalman_betas(y, f)`, and it catches only `ValueError`. `section_from_result` runs outside the `try`. The pipeline (`pipeline.py:843`) calls the hooks without any guard. So two kinds of failure stop `assemble_report` for the whole report, core sections included:

- **Any error from the filter that is not a `ValueError`.** I replaced `kalman_betas` with a function that raises `RuntimeError`. `assemble_report` raised `RuntimeError`.
- **One non-finite value in the section model.** I put one NaN into `band_low` at the last row. `assemble_report` raised a pydantic `ValidationError` from `KalmanLatest`.

No real input that I tried causes either failure. SPY and MSTR give finite output. So do six adversarial inputs, or they give a clean `failed` section:

- a factor that goes flat after row 600;
- returns multiplied by 1e4;
- factors multiplied by 1e-6;
- a +500% day;
- near-collinear factors (gives `failed / singular_burn_in`);
- a fit with no noise.

But this is the largest numerical hook in the report. Contract SC3.2 forbids raising only "for data reasons". It has no notice mechanism, so the report cannot today show the section as missing with a notice.

Fix: in the hook (a Kalman-owned file), wrap both the filter call and `section_from_result` in `except Exception`. Return `not_ok_section("failed", ...)` and log the exception. The general fix would be a guard in the pipeline that adds a notice to the report. `pipeline.py` is a contract file, so that is a proposal for the owner.

### F2 (medium). The panels describe the drift rate wrongly

Where: `backend/factordesk/report/kalman_text.json:40` (`fold.drift_rate`, printed by both panels). The same claim is in `wiki/decision-kalman-betas.md`: "One number, the drift rate (lambda), says how much weight a new day gets".

The panel text says: "The drift rate is the weight the filter gives to a new day." That is not what lambda is:

- Lambda is the ratio of the state-noise variance to the observation-noise variance.
- The weight of a new day is the gain. The spec's own KB2.5 shows the gain is about `sqrt(lambda)`.
- For SPY's last vintage, lambda is 0.00019. The scalar steady state of KB2.5 gives a gain of 0.0137, which is 72 times the number in the "Drift rate" column.

A reader who reads 0.00019 as "the weight of a new day" is wrong by almost two orders of magnitude.

Fix:

1. Rewrite the sentence, for example: "The drift rate says how fast the model lets the betas wander compared with daily noise; a higher rate gives a new day more weight and a shorter equivalent window."
2. Run `npm run sync:kalman-text` to copy the change to the frontend.
3. Correct the sentence on the wiki page.

### F3 (medium). CI never checks the drift term of the production path

The production code runs in batched passes (`_grid_pass` and `_output_pass`). The default suite compares them with the simple reference filter only on DGP-A data, where the betas are constant. On that data the grid picks lambda = 0, or very close to 0, and the drift term has no effect:

- `test_pipeline_matches_a_naive_reference_end_to_end`: both vintages have lambda 0.
- `test_batched_filter_equals_single_filter`: the last vintage has lambda 0.
- The TKB13 and TKB14 data: every vintage has lambda 0.

Mutation evidence (section 4): three broken versions of the drift term pass the default suite:

- M3: the `P += Q` step removed from the output pass;
- M4: `Q` doubled in the grid pass only;
- M5: `Q` rescaled in the output pass.

Only the `live` tests on the cached real SPY data catch them. CI runs neither the `live` nor the `slow` tests.

Fix: I added two tests in a separate commit (`2b86c50`). They use drifting betas, where every vintage has lambda > 1e-6:

- `test_kalman.py::test_pipeline_matches_a_naive_reference_with_drifting_betas`
- `test_kalman.py::test_tkb13_causal_with_drifting_betas`

With these tests, M3, M4 and M5 each fail the default suite: the new reference test catches every one. The tests take about 3 s.

### F4 (low). Contract and sibling files were edited without asking first

SC7 says a branch that needs to change a file outside its own row stops and asks. This branch changes these files outside the Kalman row:

- **Contract ("nobody") files:** `tests/test_schema_contract.py` (new `BUILT_SECTIONS` tuple), `tests/test_panel_registry.py`, `frontend/src/components/report/panelRegistry.test.tsx`, and `report/panel_registry.py` (formatting only).
- **Other features' panels:** `report/panels/fragility.py` and `report/panels/lead_lag.py` (formatting only).
- **Shared tooling:** `.github/workflows/ci.yml` (adds `ruff format --check`), `frontend/playwright.config.ts`, `frontend/e2e/smoke.spec.ts`, `frontend/package.json`.
- **New shared-text files:** `report/kalman_text.py` and `.json`, `frontend/src/text/kalman.*`, `frontend/scripts/sync-kalman-text.mjs`.

The edits are sensible, and the handoff discloses them. But `feat/shrunk-betas` and `feat/residual-alpha` edit the same three contract test files in the same places, so the merges will conflict.

No `docs/methodology*` file was edited. `openapi.json` and `types.gen.ts` were regenerated, and `test_openapi_is_current` passes.

Fix: the owner signs off the edits and agrees one form of the `BUILT_SECTIONS` tuple that each branch appends to.

### F5 (low). TKB13 was not tested at report level

The spec's TKB13 also replaces RF and adds a dividend and a split after `t*`. The branch's test changes only the `y` and `f` passed to `kalman_betas`. The core T102 test does not look at the Kalman section.

I added `test_section_kalman.py::test_tkb13_report_level_perturbation_with_dividend_and_split` in commit `2b86c50`. It reuses the T102 inputs, in both the redraw and the back-adjusted variant. It checks that every Kalman payload value stamped up to `t*`, and every finished vintage, is unchanged. It passes.

### F6 (low, owner decision). `ex_ante_betas` duplicates `betas`

Confirmed on SPY:

- In the module arrays, `ex_ante[t] == betas[t-1]` exactly for every row from 505 (`np.array_equal` is true).
- In the payload, 0 mismatches over 5 x 7,970 values. Row 504 is null.
- At a vintage boundary, the ex-ante value comes from the old vintage. That is correct (KB2.4).

Sizes on SPY (compact `model_dump_json`):

- The Kalman section is 1,849,618 bytes, 43.7% of the 4,236,076-byte report.
- `ex_ante_betas` is 404,204 bytes: 22.3% of the section and 9.7% of the report.
- The whole report gzips to 1,309,040 bytes with the field and 1,173,442 without it (10.4% less).

Neither panel reads the field.

Recommendation:

- Drop `ex_ante_betas` from the served section. Document that the ex-ante beta for day t is the filtered beta of day t-1.
- Keep it in `KalmanResult`, where the look-ahead tests use it.

This is a schema change, so the OpenAPI document and the TS types need regenerating. It does not block the merge.

### F7 (low). The screen-reader strings differ between the panels

Two screen-reader strings are not in `kalman_text.json`, and the panels word them differently:

- static `aria-label`: "Kalman-filter beta to {name}, with a 95 percent band" (`report/panels/kalman.py:191`);
- React hidden summary: "{name} Kalman beta from {first} to {last}: lowest ..., highest ..." (`KalmanPanel.tsx:252-254`).

Every visible string is the same in both panels. Both print it from the shared JSON. The backend file and the frontend copy are byte-identical, and each side has a test for that.

### F8 (info). State of the spec

- **Template markers:** five are still unfilled, as the builder says: `{{MA_COV}}` (KB5), `{{T5_RESULT}}` (KB6.1), `{{MA_COV2}}` (KB6.3), `{{SIM_TABLE}}` (KB7.1) and `{{KD7}}` (KB10.1).
- **Stale text:** the header still says "Not yet implemented". KB8.1's runtime of 31.9 s is out of date.
- **The L-KF label:** the caller's brief says the spec's L-KF omits the window clause. It is the other way round. The spec's L-KF (KB8.3) contains "behaves like a {W_eq}-day window for this stock". The implemented `L_KF` (`report/sections/kalman.py:36-40`) drops it, and the window appears only in the vintage table.

None of this blocks the merge. Before the methodology fold-in (KB10.3), the owner should:

- either amend the spec label or restore the clause;
- fill the five markers, or mark them `[U]`.

A small wording point in KB7.3: the spec says MSTR's crossing on day 222 happens "at the 2021-06-23 re-estimation". The day count is right, but the crossing is on 2021-06-29, four trading days after the vintage switch. On 2021-06-23 the line jumps from 1.19 to 1.38, still below the midpoint of 1.436.

### F9 (info). Points checked and found fine

- **First positive grid value:** when 1e-9 wins, the code keeps it without the parabolic step. Its left neighbour is 0, which has no log10, so this is a reasonable reading of "interior positive point".
- **TKB09 seed:** it uses `20261118 + 609 + k`, a small departure from the spec's seed policy. It does not matter.

## 2. Statistical correctness

### 2.1 The model, re-derived and compared with the code

From KB1 to KB3 and KB5, the filter is as follows:

- **State and noise.** The state is `theta = (alpha, beta')'`, with an identity transition. `Q = blockdiag(0, lambda R M)`, where `M = inv(cov(f[1..m_j], ddof=1))`. The model runs in scale form, with `R = 1`.
- **Burn-in.** OLS on rows 1 to 21 gives `a_{21|21}`, and `P_{21|21} = (X'X)^-1`.
- **Each row from row 22.** `P += Q`, `v = y - x'a`, `F = x'Px + 1`, `a += Px v / F`, `P -= Px Px' / F`.
- **Concentrated likelihood**, over rows 22 to `m_j`: `R_hat = mean(v^2/F)` and `logL_c = -N/2 (ln 2pi + ln R_hat + 1) - 1/2 sum ln F`.
- **Grid search.** Grid `{0} U 10^(-9 + k/8)` for k = 0 to 56, then one parabolic step in log10, clipped to one grid step.
- **Vintages.** At `m_j = 504 + 252 j`. Each vintage re-runs the filter from row 1 and stamps rows `m_j` to `m_{j+1}-1`.
- **Band.** `beta +/- 1.959964 sqrt(R_hat_j P_jj)`.

`kalman.py` matches this line by line:

| Step | Code |
| --- | --- |
| Burn-in | `_burn_in` (lines 160-172) |
| Drift shape `M` | `_drift_shape` (175-186) |
| Batched passes | 200-253 and 266-341 |
| Grid refinement | `refine_lambda` (135-157) |
| Likelihood | 481-489 |
| Vintage schedule and picks | 494-505 |
| Bands and output | `_assemble` (524-580) |

In the batched passes, `s = Px / sqrt(F)`, so `P - s s'` equals `P - Px Px'/F`.

The hyperparameter is fixed and estimated by grid maximum likelihood, not by EM, as the spec says. The code has no smoother. The handoff and the TKB18 static scan both say so.

### 2.2 My own implementation

I wrote `indep.py` from the spec only. It is built differently from the module:

- the batch is on the leading axis, with einsum;
- it uses the Joseph-form covariance update;
- each vintage runs its own filter, with no shared pass and no compaction;
- the parabola is fitted with `np.polyfit`.

Synthetic data, 1,800 rows, correlated factors (max differences, module against mine):

| Case | Drift rate (relative) | Betas | Bands | Ex-ante | Note |
| --- | --- | --- | --- | --- | --- |
| Random-walk betas, true lambda 1e-4 | 6e-13 | 1.4e-13 | 2.2e-13 | 1.4e-13 | fitted lambdas 7.8e-5 to 1.2e-4; the band covers the true beta 94.3% of the time |
| Constant betas | 3e-12 | 2.0e-13 | 3.7e-13 | 2.0e-13 | lambda = 0 in the first 3 vintages |

Constant betas should converge to OLS:

- At lambda = 0, the filter's last state equals full-sample OLS to 9.4e-16.
- With the small fitted lambda (1.5e-6), the last betas are within 0.11 of OLS, as expected for an effective window of about 1,600 rows.

Real SPY (8,474 rows, 1993-02-01 to 2026-09-30, 32 vintages), module against mine:

- lambda within 7.1e-12 (relative) and R_hat within 7.7e-14;
- betas within 2.9e-13, bands within 4.4e-13, alpha within 3.1e-17;
- on the six anchor rows of the handoff (504, 1806, 3947, 4032, 6830, 8474), mine are within 3.9e-6 of the printed values, which is their 6-digit rounding;
- the latest sd equals the handoff: 0.0292705, 0.0420977, 0.0404826, 0.0434077, 0.0563138.

Is the spec's grid finding the maximum? I ran an independent maximiser on vintages 0, 13, 14 and 31: a grid with 32 points per decade and no parabolic step. It lands within a factor of 1.034 of the spec's lambda, with a log-likelihood within 0.004.

I also built the excess return myself, by the M2 rule: `adj_close` returns minus RF, on the French dates. It equals `build_sample` exactly on all 8,474 rows.

### 2.3 MSTR (the second half of TKB24): run and passing

7,119 rows, 1998-06-12 to 2026-09-30, 27 vintages, status `ok`.

| Date | Mkt-RF Kalman beta |
| --- | --- |
| 2020-08-10 | 0.693 |
| 2020-08-11 | 0.630 |
| 22 days later | 0.757 |
| 64 days later | 0.939 |
| 127 days later | 0.965 |
| 253 days later | 1.599 |
| 504 days later (2022-08-11) | 2.744 |

The rise over 504 rows is 2.05. TKB24 needs at least 0.5.

Other values:

- latest betas: 2.27, -0.49, -1.44, -0.68, -0.24, with sd 0.60, 0.87, 0.83, 0.89, 1.16;
- equivalent window: 183 to 352 rows up to the 2020 vintage, then 126 to 132;
- the line crosses 1.436 after 222 days.

All of this equals KB7.3 and KB9.2. It is not committed as a test, because it needs data that is not committed.

## 3. Look-ahead

- **Filtered values.** TKB13 (at module level and, with the new test, at report level), TKB14 and TKB15 pass. Every mutation that leaks later data is caught:
  - M6: `M` from the whole sample;
  - M7: `R_hat` from rows after `m_j`;
  - M8: each vintage stamping one row early.
- **Ex-ante values.** TKB16 passes, and five tests catch M2 (ex-ante not lagged). At the first row of a new vintage, the ex-ante value comes from the old vintage, which is correct.
- **Smoothed betas.** None exist. `KalmanResult`, the section and both panels carry filtered values only, and nothing is labelled "smoothed" or "retrospective". TKB17 shows that a smoother written as a test oracle would fail the look-ahead check, so the check really can catch a smoother. TKB18 bans smoother names in `kalman.py`.
- **Displayed numbers and sentences.**
  - The latest values are stamped at the last date.
  - The chart's vertical span and the hidden "lowest/highest" summary use the whole filtered series. That is a summary of a point-in-time series stamped `T_end`, which KB0.3 allows.
  - No sentence calls a value a forecast.
  - "Ex-ante" appears only in the description of the payload field, which says "from rows before it only".

## 4. Mutation results

I ran each mutation against `test_kalman.py`, `test_section_kalman.py`, `test_panel_kalman.py` and `test_kalman_live.py` (live tests included, slow tests excluded). Unmutated baseline: 70 passed.

| Mutation | Caught by |
| --- | --- |
| M1 sign of the innovation flipped (output pass) | 7 tests: batched equals single, simple reference, 5 live |
| M2 ex-ante not lagged | 5: TKB16, TKB22, simple reference, the n=504 section, live ex-ante |
| M3 predict step (`P += Q`) removed from the output pass | 2, **live only** |
| M4 `Q` doubled in the grid pass only | 2, **live only** |
| M5 `Q` rescaled in the output pass | 2, **live only** |
| M6 `M` from the whole sample (look-ahead) | 5: TKB14, TKB15, 3 live |
| M7 `R_hat` from rows after `m_j` (look-ahead in the band) | 4: TKB13, TKB14, simple reference, live look-ahead |
| M8 each vintage stamps one row early (look-ahead) | 7 tests plus 4 errors: TKB08, TKB22, TKB23, TKB24, section tests |
| M9 lower band uses z = 1.645 | 1: simple reference |
| M10 sign of the parabolic step flipped | 2: TKB07, live |
| M11 burn-in uses 22 rows, so row 22 counts twice | 5: simple reference, batched equals single, TKB22, section, live |
| M12 likelihood row count off by one | 3: simple reference, 2 live |
| M13 latest sd taken from the first stamp | 2: simple reference, live |

All 13 mutations are caught by at least one test. But M3, M4 and M5 are caught only by `live` tests, which need data that is not committed and do not run in CI (F3). I re-ran M3, M4, M5 and M9 with live tests excluded and the added tests present. The new test `test_pipeline_matches_a_naive_reference_with_drifting_betas` caught each one.

Coverage of the spec's test list:

- Tested, and the tests have teeth: TKB01-05, 07, 08, 12-18, 22, 23.
- Slow, run on demand: TKB09-11 and 19-21.
- Cannot be tested in v1: TKB06 (there is no smoother).
- Half in the suite: TKB24. The SPY half is a live test; I ran the MSTR half by hand (section 2.3).

TKB01-05 test `filter_path`, the single-path code. The batched production path is tied to them by the two reference tests.

## 5. Gates (run by me on this worktree)

| Gate | Result |
| --- | --- |
| `uv run pytest -q` at `afacc76` | 613 passed, 218 deselected (199 s) |
| same, with the added tests (`2b86c50`) | 617 passed, 218 deselected (162 s) |
| `uv run ruff check backend` | all checks passed (also with the added tests) |
| `uv run ruff format --check backend` | 85 files already formatted |
| `uv run pyright` | 0 errors, 0 warnings (also with the added tests) |
| live (`test_kalman_live.py`, cached SPY) | 6 passed (part of the mutation baseline) |
| slow, 2 of 7, default 100 replications | TKB10 and TKB20: 2 passed in 90 s |
| `npm ci` | ok |
| `npm run typecheck` | exit 0 |
| `npm run lint` | exit 0 |
| `npm test` | 407 passed |
| `npm run build` | ok |
| `npm run size` | 387.1 kB raw, 118.6 kB gzip; budget 400 / 125 (handoff: 385.7 / 118.0) |
| `npm run e2e` | 1 passed in 32.5 s, on this checkout's port 8833; the server exited afterwards |

Runtime on SPY (one run each, busy machine):

- `kalman_betas`: 3.8 s.
- `assemble_report`: 7.1 s with the hook and 2.1 s without, so the hook adds 5.0 s.

That is slower than the handoff's median of 1.5 to 2.3 s, but of the same order. It is well under the spec's 10 s target, and far below the spec's out-of-date 31.9 s.

MSTR `kalman_betas`: 4.2 s.

On real SPY data, every core field of the report is identical with and without the Kalman hook (TKB23).

## 6. Conditions before merge

1. **F1.** Inside `build_kalman_betas`, catch every exception from the filter and from building the section, and return a `failed` section. Add a test that makes `kalman_betas` raise `RuntimeError` and checks that the report still builds.
2. **F2.** Replace the drift-rate sentence in `kalman_text.json`, sync the frontend copy, and correct the wiki decision page.
3. **F3 and F5.** Keep the added tests (commit `2b86c50`) or equivalent ones, so CI checks the drift term and the report-level TKB13.
4. **F4.** The owner signs off the edits to contract and sibling files, and sets a merge order for the three contract test files that `feat/shrunk-betas` and `feat/residual-alpha` also edit.

Owner decisions that do not block the merge:

- Drop `ex_ante_betas` from the payload (F6). It saves 22% of the section and 10% of the report.
- Decide the L-KF window clause, and fill the five spec markers (F8).
- Move the screen-reader strings into the shared JSON (F7).
- Turn the MSTR half of TKB24 into a test once an MSTR cache is part of the live data.

Proposed for `docs/methodology.md` (not edited here): KB10.3 as written, plus the corrected definition of the drift rate (F2) in the M0.9 label text.
