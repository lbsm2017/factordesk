# Kalman-filter betas: handoff to independent validation

Written 2026-11-18 on branch `feat/kalman-betas` (stage 3 of the chain, after the analytics and section, the two panels, and this step). Spec: `docs/specs/kalman-betas.md` (the owner's; not edited here). Companion decision page: `wiki/decision-kalman-betas.md` (status Decided-pending-implementation until the validator signs off).

Everything below that says "measured" was measured on this branch on 2026-11-18 on a Windows 11 machine with 12 logical cores that other work was also using (CPU load 32 to 38 percent from other processes when sampled). Timings are therefore upper-ish and noisy; they are given as ranges.

## After validation (2026-11-18)

The independent validation (`docs/reviews/kalman-betas-validation-2026-11-18.md`, branch `validate/kalman-betas`) found the statistics correct and asked for four fixes. What was done on `feat/kalman-betas`:

- **F1 (hook could stop the whole report).** `build_kalman_betas` now catches any error of the filter and any error or non-finite value (NaN or infinity in a stamped series, `latest` or a vintage) when the section is built, logs it, and returns a `failed` section with a reason (`kalman_error` or `kalman_invalid_output`). The report builds as before. Tests: a `RuntimeError` from the filter, NaN and infinity in four result fields, and a NaN hyperparameter. A guard in `pipeline.py` that adds a report-level notice is still a proposal for the owner (contract file, SC3.2).
- **F2 (wrong drift-rate sentence).** The panel text (`kalman_text.json` and its frontend copy) and the wiki page no longer say the drift rate is the weight of a new day. The weight is roughly the square root of the rate (spec KB2.5): a rate of 0.0001 gives a new day a weight of about 0.01. The two copies are equal and their tests pass. Section 3 below shows the old sentence and is superseded on this point.
- **F3 (drift term untested in CI).** The validator's two tests with drifting betas are kept. Two more were added: the output pass equals statsmodels at lambda > 0 (states and bands, every vintage), and the grid pass picks the maximiser of the single-path likelihood (itself tied to statsmodels by TKB02). With each of M3, M4 and M5 applied by hand, the new tests fail without cached data.
- **F6 (payload).** Owner decision of 2026-11-18: `ex_ante_betas` is dropped from the served section (model, hook, fixture, tests, OpenAPI document and TypeScript types). The ex-ante beta for day t is the filtered beta of day t-1 (`betas[t-1]`); the analytics result `KalmanResult.ex_ante` stays for the look-ahead tests. Neither panel read the field. Size on the cached SPY history now: section 1,445,350 bytes (was 1,849,618), 37.7 percent of a 3,831,628-byte report (was 43.7 percent of 4,236,076); the report gzips to 1,173,770 bytes. Section 7 and the first decision in section 9 are superseded.

Left for the owner (not changed here):

- **F4: accepted by the owner (2026-11-18).** The edits to contract files (`test_schema_contract.py` with the `BUILT_SECTIONS` tuple, `test_panel_registry.py`, `panelRegistry.test.tsx`, `panel_registry.py`) stay as they are. The merge order with `feat/shrunk-betas` and `feat/residual-alpha`, which edit the same three test files, is still to be agreed.
- **The L-KF window clause: decided by the owner (2026-11-18), as a proposal only.** Proposal for the spec (KB8.3, `docs/specs/kalman-betas.md`, not edited here): remove the clause "behaves like a {W_eq}-day window for this stock" from the `L-KF` label, so the spec matches the implemented label; the window stays in the vintage table. The code is unchanged.
- The five unfilled spec markers, the stale spec header and KB8.1 runtime (validation F8), the screen-reader strings that differ between the panels (F7), and the MSTR half of TKB24 as a test.
- Proposed for `docs/methodology.md` at the fold-in: the corrected definition of the drift rate (weight of a new day roughly the square root of the rate).

## 1. What was built

| Piece | Where | Status |
| --- | --- | --- |
| Filter, hyperparameter grid, yearly vintages, Student-t variant | `backend/factordesk/analytics/kalman.py` (`kalman_betas`, `filter_path`, `refine_lambda`, `vintage_rows`, `equivalent_window`, `t_weight`) | Built. Forward filter only; no smoother. |
| Section model, labels, warning texts | `backend/factordesk/report/sections/kalman.py` (`KalmanBetaSeries`, `KalmanVintage`, `KalmanLatest`, `KALMAN_SECTION`) | Built, registered in the schema v3 contract slot `kalman_betas`. |
| Pipeline hook | `backend/factordesk/section_hooks/kalman.py` (`build_kalman_betas`, `section_from_result`, `not_ok_section`) | Built; called by `assemble_report`; Gaussian errors only. |
| Static panel | `backend/factordesk/report/panels/kalman.py` (position 810, id `kalman`) | Built. |
| React panel | `frontend/src/components/report/sections/KalmanPanel.tsx` and `.css` | Built. |
| Shared wording | `backend/factordesk/report/kalman_text.json` (source), `kalman_text.py` (loader), `frontend/src/text/kalman.json` (checked-in copy), `frontend/scripts/sync-kalman-text.mjs` (`npm run sync:kalman-text`) | Built in this step. |
| OpenAPI and TS types | `frontend/src/api/openapi.json`, `types.gen.ts` | Regenerated in stage 1. |
| Live tests on real SPY | `backend/factordesk/tests/test_kalman_live.py` (marker `live`) | Built in this step. |

Constants (spec KB2, KB3, KB6): burn-in `b = 21`, first estimate and first stamp at row `B0 = 504`, re-estimate every `h = 252` rows, grid `{0} U 10^(-9 + k/8)` for `k = 0..56` (58 values, top value `1e-2`), `nu = 5`.

## 2. Gates, and two causes found in this step

Gate counts at handoff are in section 11. Two failures that siblings saw once and not on the re-run were traced:

1. **`ruff format --check` flagged 3 files (`report/panel_registry.py`, `report/panels/fragility.py`, `report/panels/lead_lag.py`).** It is not nondeterministic and not a race. Commit `cb9f8ca` on the parent branch committed those files wrapped at the ruff default of 88 columns, while `pyproject.toml` sets `line-length = 100`. Every checkout of that commit fails the check the same way (run 4 times, with and without the ruff cache, same 3 files). A sibling "re-run was clean" because some process had run `ruff format backend` in that worktree in between, which silently fixes them. CI runs `ruff check` but never `ruff format --check`, so nothing stopped it. Fix: the three files are formatted, and `.github/workflows/ci.yml` now runs `uv run ruff format --check backend` after `ruff check`. Commit `1841b86`. Not changed: `CONTRIBUTING.md` and `docs/release-checklist.md` list the gates; the owner may want the format check added there (the main checkout has uncommitted edits to `CONTRIBUTING.md`, so it was left alone).
2. **The browser smoke test failed on a first run and passed on the second.** Cause: the test, not the product. The first report of each run is computed from scratch by the fake backend (a 2490-row synthetic series). It takes about 5 s on a quiet machine now that the Kalman section is part of it (0.4 to 0.7 s for the later range requests). `expect.timeout` was 15 s, so a machine 3 to 4 times slower than idle (other worktrees running tests) timed out waiting for `#kpis`. Reproduced on demand by starting 24 busy processes on the 12 cores: the first run failed on `#kpis` with `Timeout: 15000ms`, the next passed once the server was warm. It was not a port clash (the port is already derived from the checkout path, 8917 here, and `reuseExistingServer` is false) and not build freshness (the fake app serves `frontend/dist`, which the `build` step had just written). Fix: `expect.timeout` 30 s, test timeout 180 s, and 120 s for the first report wait. With 36 busy processes the test then passed on the first run (1.0 min including server start-up). Commit `2016bbf`.

Observation for the owner (not changed): the e2e test needs `npm run build` first; `npm run e2e` does not build.

## 3. Wording of the two panels, chosen once

The spec has no panel text, so two agents wrote different versions. One version of each is now in `kalman_text.json`; both panels read it. Test on each side: `backend/factordesk/tests/test_kalman_text.py` and `frontend/src/text/kalman.test.tsx` assert (a) the frontend copy equals the backend file, (b) every string is printed by that side's panel (drawn panel with limits and a warning, both empty states, warm-up). Rule used: the shorter, plainer text in the report design language (`docs/design/report-design.md`: sentence case, plain words, one next step, footnotes of one or two sentences, method detail folded).

Chosen texts, as proposals for the spec (the spec owns them; `{x}` marks a value filled in at draw time):

| Item | Chosen text |
| --- | --- |
| Title and question | "Kalman-filter betas" / "How did the exposures move, using only data up to each date?" |
| Reading line | "Each day's estimate combines the previous day's estimate with that day's return, so every point uses only data up to its date. Compare the lines with the rolling betas." |
| Legend | "Kalman-filter beta", "Model-based 95% band", "Yearly re-estimate" |
| Table caption (hidden, for screen readers) | "Kalman-filter beta per factor with a model-based 95% band, latest at {last date}: latest beta, standard deviation, and the band from low to high" |
| Beta table headers | "Factor", "Chart" (hidden), "Latest", "sd" (tooltip "Model standard deviation of the latest beta"), "95% band" |
| Visible footnote | "The chart starts at {first date}, the first date with {504} trading days of history; latest is stamped {last date}. Dashed lines mark the yearly re-estimates, where a line can jump." |
| Vintage table title | "Yearly re-estimates of the drift rate" |
| Vintage table headers | "Rows used", "Drift rate", "Equivalent window, days", "Residual volatility, a year", "Valid from", "Valid to" |
| Window when the drift rate is zero | "All data so far" |
| Flag, drift rate at zero | "At zero: no drift found." |
| Flag, drift rate at the upper limit | "At the upper limit: the filter follows daily noise." (shown under the number; a rate within limits has no flag) |
| Empty state, fewer than 504 rows | next step: "This view needs a longer history. Choose an earlier start date so the sample has at least {504} trading days." |
| Empty state, failed | next step: "Check the price and factor data for gaps or constant values, or choose a different date range." |
| Empty state, reason missing | "The Kalman-filter betas were not computed." |
| Warm-up only (ok but no value drawn) | reason "No estimate yet: every date is still in warm-up." next step "Choose an earlier start date so the sample is longer." |
| Fold: same span | "Every row uses the same vertical span, centred on its own band, so wiggles compare across factors." |
| Fold: thinning | "The chart draws a thinned copy of the daily series that keeps every high and low; the numbers use all of it." |
| Fold: drift rate | "The drift rate is the weight the filter gives to a new day. It is re-estimated each year from the data up to that date. The equivalent window is the rolling window that smooths about as much. Each table row gives the estimate in force between its two dates." |
| Warning `kalman_lambda_at_upper_bound` | "For at least one yearly re-estimate the filter follows daily noise; the estimate is not meaningful." |

Fold order (both panels): L-KF, L-KBAND, fold sentences above (same span, thinning, drift rate), L-KTAIL when the gate fired, then the warning sentences.

Number formats made equal: drift rate as a plain decimal to two significant digits (`0.00000095`; the static panel's rule, ported to the React panel, which had printed `9.5e-07`), the window as a bare number under "Equivalent window, days", dates as "27 Jan 1995" with a `time` element, rows as "1,008". The React panel's seventh "Limit" column (with "Within limits." on every row) became the flag under the drift rate, as in the static panel. The static panel gained the legend and the reading line the React panel had.

Two spec observations for the owner:

- The implemented `L-KF` text (in `sections/kalman.py`, travels in the report payload) omits the spec's "behaves like a {W_eq}-day window for this stock" (KB8.3). The window is in the vintage table instead. Either amend the spec label or restore the clause.
- The spec still contains unfilled template markers: `{{MA_COV}}` (KB5), `{{T5_RESULT}}` (KB6.1), `{{MA_COV2}}` (KB6.3), `{{SIM_TABLE}}` (KB7.1), `{{KD7}}` (KB10.1).

## 4. Tests and ids

Default suite, selected by id (files `backend/factordesk/tests/test_kalman.py` unless stated):

| Spec id | Test | Status |
| --- | --- | --- |
| TKB01 | `test_tkb01_lambda_zero_is_expanding_ols` | pass |
| TKB02 | `test_tkb02_statsmodels_reference` (3 values of lambda), `test_tkb02b_naive_matrix_recursion_matches_filter_path` | pass |
| TKB03 to TKB05 | `test_tkb03_...`, `test_tkb04_...`, `test_tkb05_...` | pass |
| TKB06 | not done (there is no smoother, spec KB4.1; the retrospective view is not built) | not built |
| TKB07, TKB08 | `test_tkb07_grid_and_parabolic_refinement`, `test_tkb08_vintage_schedule` | pass |
| TKB09, TKB10, TKB11, TKB19, TKB20, TKB21 | `slow` tests, see section 5 | pass at 100 and 200 replications |
| TKB12 | `test_tkb12_t_weights`, `test_student_t_variant_runs_and_differs_from_gaussian` | pass |
| TKB13 to TKB18 | `test_tkb13_...` to `test_tkb18_static_scan_...` | pass |
| TKB22 | `test_tkb22_status_and_nulls` | pass |
| TKB23 | `test_section_kalman.py::test_tkb23_no_core_number_changes`, `test_tkb23_downstream_statistics_do_not_import_kalman` | pass |
| TKB24 | `test_kalman_live.py::test_tkb24_spy_since_2010` (marker `live`, cached data, no network). The MSTR half is not run: no MSTR history is cached. | SPY half pass |
| (added) | `test_kalman_live.py`: full-history SPY against KB9.1, latest beta between the rolling betas, look-ahead (TKB13, TKB14, TKB16, TKB17 repeated on real returns) | pass |

Other test files: `test_section_kalman.py` (23 tests: schema, nulls, rounding, hook, statuses), `test_panel_kalman.py` (17, static panel: numbers, statuses, warm-up, wording, payload size), `test_kalman_text.py` (8, shared wording), `frontend/src/components/report/sections/KalmanPanel.test.tsx` (19) and `frontend/src/text/kalman.test.tsx` (4).

Registry: stage 1 appended the spec's 54 lines (`T-20261118-701` to `754`). This step appends `T-20261118-755` to `761` (hypothesis ids `H-714` implementation checks, `H-715` runtime and size), status `run`, code version the commit that ran them.

## 5. Slow tests at 200 replications

The six slow tests ran with 100 replications in stage 1 (the spec says 200). The replication count is now read from `FACTORDESK_KB_REPS` (default 100; commit `4252e87`); the first 100 replications of a 200 run are the same draws as the 100 run. Command: `FACTORDESK_KB_REPS=200 uv run pytest backend/factordesk/tests/test_kalman.py -m slow -q --durations=0`.

Result, run on 2026-11-18 on the loaded machine: **7 passed** (TKB09 at both lambda values, TKB10, TKB11, TKB19, TKB20, TKB21) in 648.8 s in total, with no threshold changed. Durations: TKB21 218 s, TKB11 195 s, TKB10 91 s, TKB19 53 s, TKB09 50 s and 35 s, TKB20 under 1 s (it reuses the TKB10 simulation). Every test is under 4 minutes, so the full set fits the "about 10 minutes each" budget easily. The tests assert thresholds and do not print the statistics; the registry line `T-20261118-757` records the pass.

## 6. Real SPY run (cached series, no network)

Inputs: `data/prices/SPY_2026-11-18.parquet` (8509 rows, 1993-01-29 to 2026-11-17, SHA-256 `5223e94ffa5ba9122e6503bdf36116f7bf61979674da9def427a4b3c7d4a5b58`) and `data/factors/ff5_daily.parquet` (15918 rows, 1963-07-01 to 2026-09-30, SHA-256 of the file `0165744897146d1a0b328bbf961e2c29bdb117cc235eabc30d044ce3f5430b78`; source zip SHA-256 `e58577223032aa45071a46686f7068900c371b516c9eb04e28e974c34264f84f`, the spec's value). Both are copies of the owner's local cache and are not committed (`/data/` is ignored). Analysis sample: 8474 rows, 1993-02-01 to 2026-09-30. Status `ok`, no warnings, quality gate fired (so the tail label `L-KTAIL` is present).

**Added runtime of the hook** (`assemble_report` on the full SPY history, hook replaced by a function returning `None` for "without"; six alternating runs each, loaded machine):

| | Runs (s) | Median | Minimum |
| --- | --- | --- | --- |
| Without the Kalman hook | 1.69, 1.89, 1.08, 1.36, 1.30, 1.35 | 1.35 | 1.08 |
| With the Kalman hook | 3.60, 2.56, 3.10, 4.70, 3.81, 3.62 | 3.61 | 2.56 |
| Added | | 2.3 | 1.5 |

Inside the hook: `kalman_betas` alone 1.95 to 3.15 s in three runs (0.7 s at the quietest, in a separate run), building the section model 0.17 to 0.28 s. An earlier cold run of the same comparison read 5.0 and 3.2 s without against 13.2 and 9.3 s with the hook, on a busier moment; treat single runs on this machine as unreliable. The spec's figure of 31.9 s for this series (KB8.1) is out of date: the grid pass now runs all vintages in one loop over rows. The spec's 10 s target (KB10.2) is met by a wide margin.

**Section size in the JSON** (compact `model_dump_json`): 1,849,618 bytes for `kalman_betas`; the whole report is 4,236,074 bytes, so the section is 43.7 percent of it (2,386,414 bytes without it). Per key (compact, bytes): `betas` 404,228, `ex_ante_betas` 404,204, `band_low` 406,153, `band_high` 379,091, `dates` 110,163, `alpha` 105,230, `vintage_index` 23,909, `vintages` 8,132.

**Latest values, 2026-09-30** (Kalman = filtered `a_{t|t}`; band = model-based 95 percent; "full" = full-sample OLS of the report; rolling = the report's 126 and 252 day windows):

| | Kalman | sd | Band | Full sample | Rolling 126 | Rolling 252 (HAC se) |
| --- | --- | --- | --- | --- | --- | --- |
| Mkt-RF | +0.9876 | 0.0293 | +0.9302 to +1.0449 | +1.0093 | +0.9849 | +0.9899 (0.0066) |
| SMB | -0.1043 | 0.0421 | -0.1868 to -0.0218 | -0.1476 | -0.1184 | -0.1021 (0.0227) |
| HML | +0.0225 | 0.0405 | -0.0568 to +0.1019 | +0.0071 | +0.0377 | +0.0265 (0.0147) |
| RMW | +0.0059 | 0.0434 | -0.0792 to +0.0910 | +0.0878 | -0.0023 | +0.0109 (0.0137) |
| CMA | +0.0030 | 0.0563 | -0.1074 to +0.1133 | +0.0607 | -0.0111 | -0.0061 (0.0095) |

These agree with spec KB9.1 to the digits the spec prints. The Kalman band is wider than the 252-day HAC interval (for Mkt-RF 0.029 against 0.0066 as a standard deviation), as KB5 says it should be. Full-sample R-squared of the report is 0.9673.

**Vintages** (32; `lam` = drift rate, window = `2 / sqrt(lam)` rows, residual volatility a year; none is at a bound; first and last shown, the rest are in the validator table in section 10):

| j | Rows | Estimated through | lam | Window | Residual vol | Valid |
| --- | --- | --- | --- | --- | --- | --- |
| 0 | 504 | 1995-01-27 | 4.640e-05 | 294 | 2.72% | 1995-01-27 to 1996-01-25 |
| 1 | 756 | 1996-01-26 | 1.592e-05 | 501 | 2.63% | 1996-01-26 to 1997-01-23 |
| 5 | 1764 | 2000-01-25 | 6.39e-05 | 250 | 4.03% | 2000-01-25 to 2001-01-23 |
| 13 | 3780 | 2008-02-01 | 4.66e-05 | 293 | 4.21% | 2008-02-01 to 2009-01-30 |
| 14 | 4032 | 2009-02-02 | 2.14e-04 | 137 | 4.35% | 2009-02-02 to 2010-02-01 |
| 25 | 6804 | 2020-02-06 | 2.40e-04 | 129 | 3.41% | 2020-02-06 to 2021-02-04 |
| 31 | 8316 | 2026-02-12 | 1.907e-04 | 145 | 3.15% | 2026-02-12 to 2026-09-30 |

Windows run 250 to 501 rows through 2009-01-30 and 128 to 147 from 2009-02-02 on (the drop appears when 2008 enters the estimation sample), as in KB9.1. The first stamp is row 504, 1995-01-27.

**Look-ahead on the real series** (`test_kalman_live.py`): the future rows after row 2000 of the first 3000 SPY rows were replaced by a distorted copy of the real returns (`y -> -3y + 0.002`, factors doubled and reversed in time). Filtered betas, alpha, bands, ex-ante betas, vintage index and the hyperparameters of the six finished vintages stay unchanged to 1e-12 (observed at most 1.1e-15), and run on rows 1..2000 alone gives the same values (TKB14). Multiplying row 1400 by 10 leaves the ex-ante beta of that row unchanged and moves the filtered one (TKB16). A Rauch-Tung-Striebel smoother run as an oracle in the test changes by more than 1e-6 under the same perturbation (TKB17), so the check would catch a smoother. Not bit-identical: two runs on equal values held in different arrays differ in the last bits (about 1e-16 in the betas, observed on the real series; a run on the very same array repeats exactly). The batched numpy matrix products are sensitive to memory layout. The spec's tolerance is 1e-12, so this is within the spec, but "bit-identical" is not a true statement and the validator should not demand it. At 6 significant digits (the payload) the two runs are expected to agree except in rare rounding ties; this was not tested.

## 7. Payload size question (owner decision; nothing implemented)

`ex_ante_betas` is the beta series shifted by one row: for every factor and every row `t` from 505, `ex_ante_betas[t] == betas[t-1]` exactly in the payload (compared at the 6 significant digits it holds: 0 mismatches over 5 factors times 8473 rows, across all 31 vintage boundaries). Its first non-null position is row 505, one after the first filtered value. It carries no new information.

Measured on the real SPY section (compact JSON):

| | Section bytes | Section gzip | Whole report bytes | Whole report gzip |
| --- | --- | --- | --- | --- |
| As built | 1,842,081 (1,849,618 as `model_dump_json`) | 576,939 | 4,236,076 | 1,309,031 |
| Without `ex_ante_betas` | 1,437,860 (-22.0%) | 441,452 (-23.5%) | 3,824,270 (-9.7%) | 1,173,431 (-10.4%) |
| Report without the whole section | | | 2,386,414 | 732,216 |

(gzip level 6; level 9 gives 571,773 and 437,418 for the section.) The shortest further cuts, measured on top of dropping `ex_ante_betas`: also dropping `alpha` (105 KB raw) gives 1,332,621 bytes, 415,556 gzip; additionally rounding betas and bands to 5 significant digits gives 1,213,281 and 342,197; to 4 digits 1,093,634 and 262,352. The panels draw at most 300 points per row, so the full daily series is carried for the numbers and the downloads, not for the drawing.

Recommendation: remove `ex_ante_betas` from the served section (schema change, regenerate OpenAPI and the TS types) and document that the ex-ante beta for day `t` is the filtered beta of day `t - 1`; keep the function result in `analytics/kalman.py`, where the look-ahead tests use it. It saves 22 percent of the section and about 10 percent of the whole report, raw or compressed, with no loss of information and no effect on either panel (neither reads it). If the owner wants the field for external consumers, keep it behind an opt-in request parameter rather than in every report. A compression layer on the server would cut the section to about a third (577 KB), so the saving matters most on slow links and for stored copies. The remaining weight is the five betas and the two bands (about 1.2 MB); rounding them to 5 digits would save a further 8 percent, an owner decision on precision (methodology D31 sets 6 digits for the rolling betas).

## 8. Known limits

- **TKB06 is not done**: there is no smoother and no `KalmanRetrospective` model (spec KB4.2, open question Q4). `student_t5` exists in `analytics/kalman.py` (`kalman_betas(..., error_model="student_t5")`, tested by TKB12 and a differs-from-Gaussian test) but the pipeline hook always runs Gaussian, so the section's `error_model` is always `gaussian` and the t variant has no payload or panel.
- **Slow reaction to sudden changes** is a property of the model (spec KB7.3, TKB21 documents it: median step lag 251 rows against 117 for the 252-day window). The re-estimation step is 252; the spec recommends 63 once runtime allows. With the runtime now 1.5 to 3 s on a loaded machine the 2.5-fold cost the spec quotes would still be affordable. Not built.
- **Bands** are model-based, not HAC, and too narrow after a sudden change and under SPY's timing noise (spec KB5, KB6.3). The `L-KTAIL` label says so when the gate fires.
- **Jumps at vintage boundaries** are real (spec KB2.4). The chart marks them with dashed lines; on a 33-year series that is 31 lines plus the year gridlines, and a 32-row vintage table. Looked at on the real SPY report (screenshot taken, not committed because it is real data): the lines are dense but readable; an owner decision whether to show only the last few vintages in the table and fold the rest.
- **Last-bit differences** between runs on arrays with different memory layout (section 6).
- **Not run**: the MSTR half of TKB24 (no cached MSTR); the point-in-time AR(1) comparison (Q3); the diagonal `Q` (Q2); any other ticker than SPY on real data.
- The Kalman values feed nothing downstream (spec KD8, TKB23): tilt/timing, dominance and drift alerts still use the rolling betas.

## 9. Open owner decisions

1. Payload: drop `ex_ante_betas` (recommended), `alpha`, and/or reduce precision (section 7).
2. Panel wording: adopt the texts of section 3 into the spec; decide the `L-KF` clause on the window; fill the five unresolved template markers in the spec.
3. Spec questions still open from KB10.4: Q1 re-estimation step 63 (runtime no longer the obstacle), Q2 diagonal `Q`, Q3 point-in-time AR(1), Q4 retrospective view (TKB06), Q5 runtime (now met).
4. Whether the hook should offer the Student-t variant (the code exists).
5. Vintage table length on long histories (32 rows for SPY).
6. Add the format check to `CONTRIBUTING.md` and the release checklist (CI has it now).

## 10. What the independent validator must recompute, without reading the implementation

Do not read `backend/factordesk/analytics/kalman.py` or `section_hooks/kalman.py`. Work from `docs/specs/kalman-betas.md` (KB1 to KB3, KB5, KB8) and `docs/methodology.md` (M0, M2) only. Use statsmodels `MLEModel` and `RecursiveLS` or plain numpy as references.

**Inputs.** The two files of section 6, copied from the owner's cache (check both SHA-256 values first). Build the analysis sample by methodology M2: total return from `adj_close`, minus `RF`, on the dates where the factor file has a row; expected result: 8474 rows, first 1993-02-01, last 2026-09-30 (price rows after the factor file's last date are dropped). `y` is that excess return (decimal per day); `f` are the five factor columns in the order Mkt-RF, SMB, HML, RMW, CMA (decimal per day, as stored). If the validator's sample differs from these three anchors, stop and report that before anything else.

**Recompute.**

1. The recursion, spec KB1.1 and KB3: state `(alpha, beta')'`, random-walk betas, constant alpha, `Q = blockdiag(0, lambda R M)`, `M` = inverse of the sample covariance (`ddof = 1`) of the five factors over rows `1 .. m_j`, burn-in OLS on rows 1..21 as the exact diffuse start, filter from row 22 on.
2. The hyperparameters, spec KB2.1 to KB2.4: concentrated log-likelihood over rows `22 .. m_j`, grid `{0} U {10^(-9 + k/8), k = 0..56}`, grid maximiser with one parabolic step in `log10(lambda)` through the three neighbouring grid points, clipped to one grid step; vintages `m_j = 504 + 252 j` while `m_j <= 8474` (32 vintages, last `m_31 = 8316`); each vintage re-runs the filter from row 1; stamps `m_j .. m_{j+1} - 1` come from vintage `j`.
3. The band, spec KB5: `beta +/- 1.959964 sqrt(R_hat P_jj)` with `R_hat` the vintage's concentrated residual variance.

**Expected values** (from the run of section 6; 6 significant digits):

| Quantity | Expected | Tolerance |
| --- | --- | --- |
| Filtered betas on row 504 (1995-01-27, vintage 0) | 0.995895, -0.398461, -0.032614, -0.0098405, 0.0984441 (alpha 1.41535e-06) | absolute 1e-5 on betas |
| Row 1806 (2000-03-24, vintage 5) | 0.98956, -0.14955, -0.0518475, 0.207765, 0.109136 | 1e-5 |
| Row 3947 (2008-09-30, vintage 13) | 0.947324, -0.133443, -0.0537299, 0.0805053, 0.0516862 | 1e-5 |
| Row 4032 (2009-02-02, vintage 14) | 1.00384, -0.143388, -0.00893026, -0.0115208, -0.0809223 | 1e-5 |
| Row 6830 (2020-03-16, vintage 25) | 0.964778, -0.0790472, 0.00300349, 0.0684284, 0.0555752 | 1e-5 |
| Row 8474 (2026-09-30, vintage 31) | 0.98755, -0.104327, 0.0225088, 0.00588826, 0.0029552 (alpha -1.63113e-05) | 1e-5 |
| Latest sd | 0.0292705, 0.0420977, 0.0404826, 0.0434077, 0.0563138 | relative 1e-4 |
| Latest band (low, high) | Mkt-RF 0.930181, 1.04492; SMB -0.186837, -0.0218168; HML -0.0568356, 0.101853; RMW -0.0791893, 0.0909658; CMA -0.107418, 0.113328 | 1e-4 |
| Number of vintages, none at a bound, no warning | 32, yes, none | exact |

Vintage table (all 32; `lam` the drift rate, window `2 / sqrt(lam)` rows, `R_hat` the residual variance in decimal squared a day, vol `sqrt(252 R_hat)`):

| j | rows | lam | window | R_hat | vol a year |
| --- | --- | --- | --- | --- | --- |
| 0 | 504 | 4.64021e-05 | 293.6 | 2.9464e-06 | 0.02725 |
| 1 | 756 | 1.59174e-05 | 501.3 | 2.74854e-06 | 0.02632 |
| 2 | 1008 | 1.77351e-05 | 474.9 | 3.33612e-06 | 0.02899 |
| 3 | 1260 | 1.82495e-05 | 468.2 | 4.23382e-06 | 0.03266 |
| 4 | 1512 | 2.13843e-05 | 432.5 | 5.16949e-06 | 0.03609 |
| 5 | 1764 | 6.38899e-05 | 250.2 | 6.44052e-06 | 0.04029 |
| 6 | 2016 | 5.65675e-05 | 265.9 | 8.66174e-06 | 0.04672 |
| 7 | 2268 | 6.04032e-05 | 257.3 | 9.01324e-06 | 0.04766 |
| 8 | 2520 | 5.9747e-05 | 258.7 | 9.03809e-06 | 0.04772 |
| 9 | 2772 | 5.40971e-05 | 271.9 | 8.54387e-06 | 0.04640 |
| 10 | 3024 | 5.14529e-05 | 278.8 | 8.07013e-06 | 0.04510 |
| 11 | 3276 | 5.14792e-05 | 278.7 | 7.61031e-06 | 0.04379 |
| 12 | 3528 | 4.88103e-05 | 286.3 | 7.24153e-06 | 0.04272 |
| 13 | 3780 | 4.66052e-05 | 293.0 | 7.03941e-06 | 0.04212 |
| 14 | 4032 | 0.000213689 | 136.8 | 7.5165e-06 | 0.04352 |
| 15 | 4284 | 0.00020574 | 139.4 | 7.2318e-06 | 0.04269 |
| 16 | 4536 | 0.000204619 | 139.8 | 6.85384e-06 | 0.04156 |
| 17 | 4788 | 0.000205611 | 139.5 | 6.51485e-06 | 0.04052 |
| 18 | 5040 | 0.000215109 | 136.4 | 6.19081e-06 | 0.03950 |
| 19 | 5292 | 0.00022684 | 132.8 | 5.89681e-06 | 0.03855 |
| 20 | 5544 | 0.000238315 | 129.6 | 5.62458e-06 | 0.03765 |
| 21 | 5796 | 0.000239852 | 129.1 | 5.38878e-06 | 0.03685 |
| 22 | 6048 | 0.000240406 | 129.0 | 5.17053e-06 | 0.03610 |
| 23 | 6300 | 0.000243463 | 128.2 | 4.9655e-06 | 0.03537 |
| 24 | 6552 | 0.000239305 | 129.3 | 4.79165e-06 | 0.03475 |
| 25 | 6804 | 0.00024046 | 129.0 | 4.62103e-06 | 0.03412 |
| 26 | 7056 | 0.000225704 | 133.1 | 4.52517e-06 | 0.03377 |
| 27 | 7308 | 0.000208495 | 138.5 | 4.39609e-06 | 0.03328 |
| 28 | 7560 | 0.000196318 | 142.7 | 4.27661e-06 | 0.03283 |
| 29 | 7812 | 0.000189944 | 145.1 | 4.15044e-06 | 0.03234 |
| 30 | 8064 | 0.000184028 | 147.4 | 4.03611e-06 | 0.03189 |
| 31 | 8316 | 0.000190661 | 144.8 | 3.93702e-06 | 0.03150 |

Tolerances: `lam` agrees to relative 1e-6 if the validator uses the spec's grid and parabolic step; an independent maximiser of the concentrated likelihood (for example a fine grid) must give a `lam` inside one grid step (a factor of 1.33) of the table value and a log-likelihood within 0.1 of the table value's. `R_hat` relative 1e-6 at the table `lam`.

**Checks beyond the numbers.**

- At `lambda = 0` the filtered state at every row equals OLS on rows `1 .. t` (1e-10) and `RecursiveLS` (1e-10); with the vintage `lam` and `M`, the filtered states and covariances equal an `MLEModel` with exact diffuse initialisation (1e-10 absolute on states, 1e-8 relative on covariances), `obs_cov = R_hat`, `state_cov = 0` for the first 20 transitions then `blockdiag(0, lam R_hat M)`.
- No look-ahead: change every row after row 2000 (any change); every stamp up to row 2000 and the first six vintages must be unchanged to 1e-12. Truncate to rows 1 to 2000: the same. Compute the smoothed betas on the same data and show that they do fail this check, so the check has teeth.
- Ex-ante: `a_{t|t-1}` equals `a_{t-1|t-1}` of the vintage valid at row `t - 1` (random walk); the section's `ex_ante_betas[t]` equals `betas[t-1]` at 6 digits.
- Look at one number that depends on the spec's choice and not on arithmetic: the 6-significant-digit rounding of the series (methodology D31) and the `null` warm-up for rows 1 to 503.

**Acceptance.** All tolerances above met; any miss is a finding, with the row, the quantity and the size of the difference. Report separately anything the spec leaves undetermined (the first positive grid value is kept unrefined by the implementation when it is the maximiser; the spec says "interior positive point", so this boundary case is a point to confirm).

## 11. Gate counts at handoff

On branch `feat/kalman-betas`, 2026-11-18, after the last code commit (`4252e87`): `uv run pytest -q` 613 passed, 218 deselected (slow and live); `ruff check backend` clean; `ruff format --check backend` 85 files already formatted; `pyright` 0 errors; frontend `typecheck` and `lint` clean, `test` 407 passed (29 files), `build` ok, `size` within budget (385.7 kB raw, 118.0 kB gzip against 400 and 125), `e2e` 1 passed. Live tests: 6 passed with `-m live`. Slow tests: 7 passed at 200 replications.

## 12. Reproduce

```text
uv sync
uv run pytest -q
uv run ruff check backend
uv run ruff format --check backend
uv run pyright
uv run pytest backend/factordesk/tests/test_kalman_live.py -m live -q     # needs data/ with the two files
FACTORDESK_KB_REPS=200 uv run pytest backend/factordesk/tests/test_kalman.py -m slow -q
npm --prefix frontend ci
npm --prefix frontend run typecheck && npm --prefix frontend run lint && npm --prefix frontend test
npm --prefix frontend run build && npm --prefix frontend run size && npm --prefix frontend run e2e
```
