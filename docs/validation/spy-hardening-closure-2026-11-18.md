# SPY slice hardening: closure of the validation findings

Date: 2026-11-18. Branch `fix/spy-hardening-closure`, based on `feat/report-ui-feedback` at `6ba7a26`.
Source: `docs/validation/spy-slice-validation.md` (verdict "ship with changes"), sections 2, 3 and 6.
Roadmap item closed: "Hardening of the SPY slice" (numbers must never mislead: diagnostics, quality
gate, clean errors).

Each finding was checked against the code and tests on this branch. Status values:

- **Fixed before**: fixed in the code before this closure. All such fixes are in commit `948dc5b`
  (the initial commit, which already carried the hardening: residual diagnostics and quality gate,
  `DegenerateInputError`, duplicate-date reporting, the M1.4 audit and the M1.1 parser), and are
  recorded in `docs/methodology.md` M16 as D22-D31.
- **Fixed now**: fixed on this branch, one commit per fix, each with a regression test that fails
  when the fix is reverted (section 3).
- **Deferred**: not fixed, with the reason and the decision or follow-up it waits for (section 2).

No statistical definition in `docs/methodology.md` was changed. `report/schema.py`,
`analytics/rolling.py` and the frontend were not touched.

## 1. Closure table

Line numbers refer to this branch after the last fix commit. Tests are in `backend/factordesk/tests/`.

| Id | Severity | Finding (short) | Evidence in code | Tests that pin it | Status | Commit |
| --- | --- | --- | --- | --- | --- | --- |
| Critical | - | None reported | - | - | Nothing to do | - |
| F1 | Major | M3.5 diagnostics missing; report cannot disclose SPY timing noise | `analytics/diagnostics.py:110` (lag-1, robust z), `:124` (robust Breusch-Godfrey), `:214` (all M3.5 tests), `:246-265` (gate rule `RHO_GATE = -0.2`, `Z_GATE = -4.0` at `:58-60`), `:320` (5-day blocks); `pipeline.py:659` (warning `residual_reversal` first), `:747` (`apply_gate`) | `test_diagnostics.py`: `test_t47_diagnostics_equal_statsmodels_and_emit_no_warning`, `test_t47_robust_bg_standalone_matches_reference`, `test_t121_gate_rule_boundaries`, `test_t122_gate_on_known_noise`, `test_t122_gate_quiet_without_noise`, `test_t123_*`, `test_t125_gate_in_the_report`; `test_pipeline.py::test_live_spy` (R2 below 0.97 now requires the gate to fire; the docstring-only explanation and the loosened bound are gone) | Fixed before (M3.5, M3.6, D21-D23) | `948dc5b` |
| G1 | Major (part of F1) | Pre-specified non-synchronous-price gate | as F1 | as F1 | Fixed before (D22) | `948dc5b` |
| F2 | Major | "reliable" on the alpha tile over-claims | `report/render_html.py:614-615` (alpha note "Distinguishable from zero at 5%"; "single test" in the regression table at `:1391`); `analytics/diagnostics.py:351-359` (conjunction of daily and 5-day tags when the gate fires, M3.2) | `test_diagnostics.py`: `test_t124_tag_conjunction`, `test_t124_apply_gate_combines_alpha_and_betas`, `test_t124_pure_alpha_cases`; `test_report.py::test_render_five_kpi_cells` | Fixed before | `948dc5b`, `28e00ed` |
| F3 | Major | Degenerate inputs crash or ship R2 = -1154.9 as ok | `analytics/sample.py:42`, `:277` (price-movement guard); `analytics/regression.py:62`, `:186-191` (design guard, constant-y guard); `cli.py:214-241` (one line for `DegenerateInputError` and any leftover `ValueError`/`ArithmeticError`; `LinAlgError` subclasses `ValueError`) | `test_cli.py::test_t126_degenerate_inputs_end_cleanly` (9 cases), `test_cli.py::test_unexpected_numerical_error_is_one_line`, `test_regression.py::test_t126_design_guard_names_the_factor`, `test_regression.py::test_constant_dependent_variable_is_refused`, `test_rolling.py::test_t126_singular_windows_get_no_estimate_and_no_warning` | Fixed before (D30) | `948dc5b` |
| F4 | Major | Audit errors leave a usable-looking headline; no influence diagnostic | Headline: `report/render_html.py:608-613` (fitted tiles muted, alpha note "Not interpretable: the price audit found errors"), `:59-62` (notice summary), `pipeline.py:673-685` (warning text). Influence: none | `test_report.py::test_render_audit_errors_mute_the_headline`; `test_cli.py::test_t126_degenerate_inputs_end_cleanly[duplicate_dates-0]` (warning says "not interpretable") | Headline: **fixed now**. Influence diagnostic: **deferred** (D-1) | `7ad2fbf` |
| F5 | Major | Duplicate dates silently dropped | `data/prices.py:222-232` (`collapse_duplicate_dates`, keep first, list dates), `:78` (`PriceHistory.duplicate_dates`); `pipeline.py:864` (injected providers); `data/audit.py:386-402` (A1 `duplicate_index`, error) | `test_prices.py::test_t117_duplicate_dates_are_recorded_not_dropped_silently`, `test_prices.py::test_collapse_duplicate_dates_keeps_first_and_lists_dates`, `test_audit.py::test_duplicates_recorded_at_ingestion_are_reported`, `test_audit.py::test_t29_duplicates_and_order`, `test_cli.py::test_t126_degenerate_inputs_end_cleanly[duplicate_dates-0]` | Fixed before (D29) | `948dc5b` |
| F6 | Major | Audit uses the plan's dividend formula, not M1.4 | `data/audit.py:93` (`tau_t`), `:264-285` (A6, CRSP convention), `:518-544` (A5 log rule, A5b), `:454` (A2), A7/A8 in the same module | `test_audit.py`: `test_t22_*` to `test_t30_adjustment_on_the_wrong_day`, `test_t119_a6_tolerance_literal`, `test_t119_a7_tolerance_literal`, `test_t119_a8_tolerance_literal`, `test_t119_a5b_literal` | Fixed before (D9, D24-D26) | `948dc5b` |
| F7 | Major | French parser looser than M1.1 | `data/factors.py:45` (`REVISION_TOLERANCE = 5e-5`), `:146` (second data block), header, order, bounds, empty cells, no clock | `test_factors.py`: `test_t01_*`, `test_t02_wrong_or_reordered_header_raises`, `test_t06_second_data_block_raises`, `test_t07_*`, `test_t10_value_bounds`, `test_t11_revision_tolerance`, `test_t116_*` | Fixed before (D28), except `meta.json` keys of M1.1 item 11: **deferred** (D-2) | `948dc5b` |
| F8 | Minor | Yahoo Adj Close not reproducible; no input hash in the report | No price-frame hash in `DataInfo` (only the factor zip hash, `data/factors.py:318`) | - | **Deferred** (D-3) | - |
| F9 | Minor | Only a bar dated exactly today is dropped | `data/prices.py:277-279` (drop every row dated on or after today, exchange time zone) | `test_prices.py::test_t118_bars_on_or_after_today_are_dropped`, `test_prices.py::test_today_is_judged_in_exchange_timezone` | Fixed before (D27) | `948dc5b` |
| F10 | Minor | No requested-date control in the CLI | `cli.py:69-74` (`_iso_date`), `:95-108` (`--start`, `--end`), `:198-202` (start after end is a usage error), `:211-213` (passed to `build_report`); requested vs actual already in `DataInfo` and the KPI strip | `test_cli.py::test_report_start_and_end_reach_the_report`, `test_cli.py::test_report_range_usage_errors` | **Fixed now** | `46d4707` |
| F11 | Minor | HTML thins rolling series by stride and can hide spikes | `report/render_html.py:248-270` (`_decimate`: min-max per bucket, first and last kept), used for the price line and the rolling bands | `test_report.py::test_decimation_keeps_one_day_spikes` | **Fixed now** | `05cafc0` |
| F12 | Minor | JSON is 6.4 MB | `report/schema.py:608` (`dump_report`, compact), rolling betas and se at 6 significant digits | `test_pipeline.py::test_t128_json_precision_and_size`, `test_report.py::test_dump_is_compact_and_round_trips` | Fixed before (D31) | `948dc5b` |
| F13 | Minor | M1.5 currency check not implemented, no D-entry | Disclosed in the US-factors note, `pipeline.py:106-109` | - | **Deferred** (D-4) | - |
| F14 | Minor | All-NaN and no-overlap both say "0 daily returns line up" | `analytics/sample.py:48-60` (`InsufficientHistoryError.detail`), `:163-179` (`_no_rows_detail`), `cli.py:214-219`, `api/errors.py:105-112` | `test_cli.py::test_zero_aligned_rows_name_their_cause`, `test_cli.py::test_too_short_history` (no cause claimed when causes are mixed), `test_api_basic.py::test_error_messages_follow_the_spec_wording` | **Fixed now** | `1ef0587`, `4c1cb7c` |
| F15 | Minor | "A 1-point move" is ambiguous | `analytics/regression.py:270-271` ("A 1 percentage-point move in the {name} return") | `test_regression.py::test_tags_and_interpretation_only_for_reliable` | Fixed before | `948dc5b` |
| F16 | Minor | A5 split check uses a ratio tolerance | `data/audit.py:38` (`MISSING_SPLIT_LOG = 0.15`), `:526` (log rule of M1.4) | `test_audit.py::test_t23_missing_split_adjustment`, `test_audit.py::test_missing_reverse_split_adjustment`, `test_audit.py::test_properly_adjusted_reverse_split_is_fine` | Fixed before (D24) | `948dc5b` |
| G2 | Recommendation (section 3.6) | Residual-variance stability gate with a break test | Not implemented; M3.6 records it as not adopted | - | **Deferred** (D-5) | - |
| Gate calibration | Unverified (section 7) | Gate thresholds checked on five S&P 500 products only | M3.6 "pending" paragraph | - | **Deferred** (D-5) | - |
| S1 | Test gap (section 6) | T62 never tests a rank gap of exactly 2 | - | `test_attribution.py::test_t62_disagreement_sentence` (gap of exactly 2) | Fixed before | `948dc5b` |
| S2 | Test gap | Audit tolerances tested relative to the constant | - | `test_audit.py::test_t119_a6_tolerance_literal`, `test_t119_a7_tolerance_literal`, `test_t119_a8_tolerance_literal`, `test_t119_a5b_literal` | Fixed before | `948dc5b` |
| S3 | Test gap | Condition number tested only where `kappa = kappa^2` | - | `test_regression.py::test_t45_condition_number_known_correlation` | Fixed before | `948dc5b` |
| S4 | Test gap | T44 has no case at the 0.03 and 0.05 boundaries | - | `test_regression.py::test_t44_boundaries` | Fixed before | `948dc5b` |
| S5 | Test gap | A test asserted the silent duplicate drop | - | replaced by `test_prices.py::test_t117_duplicate_dates_are_recorded_not_dropped_silently` | Fixed before | `948dc5b` |
| S6 | Test gap | High-correlation pair tested only at about 0.95 | - | `test_regression.py::test_t46_pair_threshold` (0.65 listed, 0.55 not) | Fixed before | `948dc5b` |
| T47 | Test gap | Residual diagnostics untested | as F1 | `test_diagnostics.py::test_t47_*` | Fixed before | `948dc5b` |
| T22-T30 | Test gap | Audit oracle tests missing | as F6 | `test_audit.py::test_t22_*` to `test_t30_*` | Fixed before | `948dc5b` |
| T01-T13 | Test gap | Parser oracle tests partly missing | as F7 | `test_factors.py::test_t01_*` to `test_t11_*`, `test_t116_*` | Fixed before | `948dc5b` |
| T54-T56 | Test gap | Per-year attribution and tilt/timing | M6.2 and M6.3 are not implemented; they are outside the SPY slice | - | **Deferred** (D-6) | - |
| N1 | Found during closure | The notice summary for the gate said "R² and residual volatility are probably understated"; M3.6 says residual volatility is **overstated** | `report/render_html.py:53-56`; `docs/design/report-design.md:273` | `test_report.py::test_render_header_chips_and_notice_details` | **Fixed now** (static report and design spec); dashboard text: follow-up (FU-2) | `26275e0` |

Counts over the 29 finding rows (F1-F16, G1, G2, the gate calibration, S1-S6 and the test gaps T47,
T22-T30, T01-T13, T54-T56): **fixed before 20**, **fixed now 4** (F4 headline, F10, F11, F14),
**deferred 5** (F8, F13, G2, the gate calibration, T54-T56). Two parts of rows counted as fixed are
also deferred: the influence diagnostic of F4 (D-1) and the `meta.json` keys of F7 (D-2). Found
during closure and fixed now: 1 (N1). Every critical and major finding is fixed; what remains is
minor, a recommendation that needs calibration, or outside the slice.

## 2. Deferred items and the decision each waits for

| Ref | Item | Why it is not done here | Decision or follow-up needed |
| --- | --- | --- | --- |
| D-1 | F4 influence diagnostic (share of SSR from the largest row, alpha change without it) | It is a new statistic: it needs a methodology section, a schema field and oracle tests (CODING_STANDARDS section 6). `docs/specs/fragility-score.md` already specifies influence lists and leave-one-out flip counts that cover it, "never used to drop rows". | No new owner decision. Delivered by the roadmap item "Fragility score" after the schema v3 contract. |
| D-2 | F7 `meta.json` keys `http_last_modified`, `last_attempt_at`, `last_attempt_ok` (M1.1 item 11) | Belongs to the cache and refresh logic of M1.2 (D28 deferred it). It changes no number: the parsed frame matched the validator's parser exactly. | Engineering follow-up FU-4; no owner decision. |
| D-3 | F8 input hash in the report; reproducible total returns | The hash needs a new `DataInfo` field, and `report/schema.py` is being restructured for schema v3 in parallel. Deriving total returns from Close and Dividends changes the return definition (M1.3). | Schema follow-up FU-1 (`DataInfo.price_sha256`). The return change is already the roadmap item "Total returns from Close + Dividends" (owner decision 2026-11-18), which waits for a methodology update. |
| D-4 | F13 currency check (M1.5 `currency_mismatch`) | Needs the ticker currency from Yahoo metadata and an answer to M16 open question 2. | **Owner decision:** for a non-USD ticker, warn and compute (current M1.5 text) or refuse until currency conversion exists (European mode)? Then add the D-entry and the check. |
| D-5 | G2 variance-stability gate; calibration of the G1 thresholds on a panel | Both need a panel calibration so that false-alarm rates are known before release (validation section 3.6; M3.6 says G2 is not adopted). Changing the gate would change methodology. | Roadmap item "Placebo calibration" (`factordesk calibrate`). **Owner decision** after the calibration: adopt G2 or not, keep or move the G1 thresholds (new D-entry and registry line). |
| D-6 | T54-T56 (per-year attribution, tilt/timing) | M6.2 and M6.3 are not implemented; they are not part of the SPY slice. | Scheduled with those modules; no owner decision. |

## 3. Mutation check of the fixes made now

Each new test was run with the code change reverted (tests kept, code file restored to the parent
commit, nothing committed), then with the fix restored.

| Fix | Reverted file(s) | Result with the fix reverted | Result with the fix |
| --- | --- | --- | --- |
| F4 (`7ad2fbf`) | `report/render_html.py`, `pipeline.py` | 2 failed: `test_render_audit_errors_mute_the_headline` (notice still says "the analysis still uses prices as published"), `test_t126_degenerate_inputs_end_cleanly[duplicate_dates-0]` (warning lacks "not interpretable") | 2 passed |
| N1 (`26275e0`) | `report/render_html.py` | 1 failed: `test_render_header_chips_and_notice_details` | 1 passed |
| F10 (`46d4707`) | `cli.py` | 2 failed: `test_report_start_and_end_reach_the_report`, `test_report_range_usage_errors` (unknown option, exit 2 with the wrong message) | 2 passed |
| F14 (`1ef0587`) | `analytics/sample.py`, `cli.py` | 1 failed: `test_zero_aligned_rows_name_their_cause`; `test_too_short_history` still passed (it checks that no cause is claimed) | 2 passed |
| F14 API (`4c1cb7c`) | `api/errors.py` | 1 failed: `test_error_messages_follow_the_spec_wording` (zero-row case) | 18 passed |
| F11 (`05cafc0`) | `_decimate` body replaced by the old stride rule (signature kept, so the test fails on content, not on a call error) | 1 failed: `test_decimation_keeps_one_day_spikes` (spike at index 4321 missing; stride 20 keeps 4320 and 4340) | 1 passed |

## 4. Follow-ups outside this branch

- **FU-1 (schema v3):** add `DataInfo.price_sha256` (sha256 of the price frame used, F8). Optional:
  an `audit_blocks_headline` flag, so both renderers read one field instead of re-deriving F4 from
  `audit_status`.
- **FU-2 (frontend):** mirror F4 and N1 in the dashboard. `frontend/src/components/report/KpiStrip.tsx`
  should mute the R², residual volatility and alpha tiles and show "Not interpretable: the price audit
  found errors" when `data.audit_status` is `errors`; `frontend/src/text/plain.ts` should carry the new
  `audit_errors` summary and the corrected `residual_reversal` summary ("R² is probably understated
  and residual volatility overstated"). The prototype text in `docs/design/prototype/build_prototype.py`
  has the same wrong `residual_reversal` sentence; regenerate the prototype after changing it.
- **FU-3:** the HTML sample `docs/samples/spy_report.html` predates these changes; regenerate it when
  sample reports are next refreshed (real-data samples stay out of the public repository).
- **FU-4:** the `meta.json` keys of D-2, with the M1.2 refresh work.

## 5. Gates on this branch

Run at commit `4c1cb7c` (last code commit), Windows, Python environment from `uv sync`:

| Command | Result |
| --- | --- |
| `uv run pytest -q` | 488 passed, 205 deselected (baseline before the fixes: 482 passed) |
| `uv run ruff check backend` | All checks passed |
| `uv run pyright` | 0 errors, 0 warnings |

`uv run pytest -q -m slow` also passed (202 passed). The live test set was not run (no network).
