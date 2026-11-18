# Performance section: handoff to the independent validator (2026-11-18)

Branch `feat/performance` (from `dev` at `4ad6d2e`). Status of the section: built, tested by its author, **not independently validated**. This document says what exists, what the author's tests show, where the author is unsure, and what the validator must recompute without reading the implementation.

Request: the owner (2026-11-18, with a screenshot of the headline strip) asked to show the stock's historical annualised return, volatility, Sharpe ratio and maximum drawdown next to the regression numbers. The definitions below are the owner-approved wording. There is no separate specification; the definitions here and in the docstring of `analytics/performance.py` stand in for it. Contract note (a sixth optional section, the shared files touched): `docs/validation/performance-contract-note-2026-11-18.md`. Decision page: `wiki/decision-performance-metrics.md`.

## 1. What was built

| Layer | File | Contents |
| --- | --- | --- |
| Calculation | `backend/factordesk/analytics/performance.py` | `performance_stats`, `compound_path`, `drawdown_episodes`, `top_episodes`, `MIN_OBS = 60`, `SD_FLOOR = 1e-8` |
| Section model | `backend/factordesk/report/sections/performance.py` | `PerformanceSection` (status, reason, sample, `periods`, `returns`, `volatility_annual`, `sharpe`, `drawdown`), nested `PerformancePeriods`, `PerformanceReturns`, `PerformanceSharpe`, `PerformanceDrawdown`, `DrawdownEpisodeInfo`; spec `PERFORMANCE_SECTION` (field `performance`, no labels, no nested statistic models) |
| Hook | `backend/factordesk/section_hooks/performance.py` | `build_performance`; statuses `ok`, `insufficient_data` (n < 60), `failed` (non-finite value or any error; logged, never raised) |
| Static panel | `backend/factordesk/report/panels/performance.py` | position 450, element id `performance`, right after Price; four-cell strip, one sentence on the window, table of the top three falls, one footnote, folded "How this is computed" |
| React | `frontend/src/components/report/sections/PerformancePanel.tsx`, `panelRegistry.ts` entry | placeholder only: nothing when the field is null, the panel frame (and the reason when not ok) otherwise. The real panel is built later by someone else |
| Wiring | `report/schema.py`, `pipeline.py`, `report/panels/__init__.py`, fixture list | one more entry beside the five existing sections (see the contract note) |
| Contract files | `frontend/src/api/openapi.json`, `types.gen.ts`, `tests/fixtures/mock_report.json`, `tests/fixtures/sections/performance.json` | regenerated, with the repo generators |

Report format version stays `"4"`: the field is additive and feature branches do not bump (contract SC5). A version 4 file written earlier has no `performance` key and loads with `None`. Section statuses are the M0.7 values.

## 2. Definitions (implement exactly; all over the analysed sample S, the regression's trading days)

`r_t` is the daily simple total return of the stock, `AnalysisSample.ret` (adjusted close, M1.3). The sample builds the excess return as `x_t = r_t - RF_t` (M2 step 5), so `r_t = x_t + RF_t`; the section uses `ret` and `rf` directly. `n` is the number of rows of S; `A = 252`.

| Statistic | Definition |
| --- | --- |
| `returns.cagr` | `(prod(1 + r_t))^(A / n) - 1` |
| `returns.cumulative_return` | `prod(1 + r_t) - 1` |
| `returns.mean_return_annual` | `A x mean(r_t)` (arithmetic, secondary) |
| `volatility_annual` | `sqrt(A) x sd(r_t)`, `ddof = 1` |
| `sharpe.ratio_annual` | `sqrt(A) x mean(x_t) / sd(x_t)`, `ddof = 1`; `None` when `sd(r_t) < 1e-8` or `sd(x_t) < 1e-8` |
| `sharpe.sharpe_se_iid` | `sqrt(A) x sqrt((1 + SR_d^2 / 2) / n)`, `SR_d` the daily Sharpe ratio (Lo 2002, iid, approximate) |
| `sharpe.ci95_low`, `ci95_high` | `ratio_annual -/+ 1.959963984540054 x sharpe_se_iid` |
| `sharpe.ci_includes_zero` | `ci95_low <= 0 <= ci95_high`; `None` when the ratio is undefined |
| `drawdown` | path `W_0 = 1`, `W_j = prod_{i<=j}(1 + r_i)`; drawdown `W_j / max_{i<=j} W_i - 1`; an episode runs from a running peak until the path first reaches `W >= peak`; open when it never does; depth is the lowest drawdown inside the episode, trough its first date on a tie; `episodes` are the three deepest, deepest first, non-overlapping; `max_drawdown` is the first depth (0.0 and no dates when there is no episode); `days_*` are trading days of the path (point positions) |
| `drawdown` start date | point 0 of the path is dated at the price date before the first analysed return (so a fall from day one has a real peak date); `performance_stats` without an origin dates it at the first analysed date |
| `periods` | `n_days = n`, `start`, `end` (first and last analysed date), `years = n / 252` |

Rows excluded from S (M2: multi-day returns and so on) are not in the path: the compounding runs over the analysed days only.

## 3. Tests and ids

Register: `docs/registry/tests.jsonl`, hypothesis `H-1001`, ids `T-20261118-1001` to `1008` (one line per group below; 1007 and 1008 are the real-data runs). All outcomes pass.

| Ids | File | Notes |
| --- | --- | --- |
| TP01 to TP24 | `backend/factordesk/tests/test_performance.py` (28 tests, TP10 has five cases) | hand oracles with the arithmetic in comments and a plain-python loop; edge cases; properties |
| TP25 to TP40 | `backend/factordesk/tests/test_section_performance.py` (16 tests) | schema, older files, parts-when-ok rule, NaN rejection, pipeline against an independent computation, origin date, range, core unchanged, `insufficient_data`, `failed` |
| TP41 to TP51 | `backend/factordesk/tests/test_panel_performance.py` (11 tests) | wording, states, position, no other panel changes, existing classes only |
| Contract | `test_schema_contract.py`, `test_panel_registry.py`, `frontend/src/components/report/panelRegistry.test.tsx`, `frontend/src/test/sectionFixtures.test.ts` | the sixth field and panel |

Hand-computed oracles in the tests (the validator can redo them on paper):

- Path `[+10%, -20%, +30%, +10%, -50%, +30%]` gives `1, 1.1, 0.88, 1.144, 1.2584, 0.6292, 0.81796`: episode one peak 1.1, trough 0.88, depth -0.2, regained at point 3; episode two peak 1.2584, trough 0.6292, depth -0.5, open.
- 60 days alternating +1% and -1%, RF 0: Sharpe 0, volatility `sqrt(252) x 0.01 x sqrt(60/59)`, standard error `sqrt(252 / 60)`, cumulative return `0.9999^30 - 1`.
- 30 days of +0.01 then 30 of -0.005, RF 0.0001: daily excess mean 0.0024, daily sd `sqrt(60 x 0.0075^2 / 59)`.
- A constant daily return `r` gives CAGR `(1 + r)^252 - 1` for every `n`.
- One crash of -30% after 30 days at +1%, then 8 days at +5%: depth -0.30, recovery after 8 days (`1.05^8 = 1.4775 > 1/0.7`); with 7 days at +5% it is not recovered.

Gate results (2026-11-18, final state of the branch): see the last section.

## 4. What the validator must recompute

Without reading the implementation, from the cached or downloaded adjusted close and the French file:

1. On SPY from 1993 and on one volatile stock (ZM), build the analysed sample: returns on dates present in the French file (excluding the multi-day returns and missing rows of M2), `RF` from the file, and recompute CAGR, volatility, Sharpe ratio, its standard error and interval, the maximum drawdown with its three dates, and the next two episodes. The author's numbers (all matched an independent pandas calculation to the last digit):

| | SPY 1993-02-01 to 2026-09-30 (8,474 days) | ZM 2019-04-22 to 2026-09-30 (1,872 days) |
| --- | --- | --- |
| Return a year (compound) | 10.8258% | 5.2654% |
| Total return | 3070.55% | 46.40% |
| Mean x 252 | 11.9985% | 19.4704% |
| Volatility a year | 18.5293% | 54.0272% |
| Sharpe ratio, se (iid), interval | 0.5150, 0.1725, 0.177 to 0.853 | 0.3076, 0.3669, -0.412 to 1.027 |
| Worst fall | -55.1894%, peak 2007-10-09, trough 2009-03-09, recovered 2012-08-16 (355 and 869 days) | -90.2664%, peak 2020-10-19, trough 2024-08-12, not recovered (958 days) |
| Second fall | -47.5158%, 2000-03-24 to 2002-10-09, recovered 2006-10-26 | -39.6711%, 2019-06-12 to 2019-10-22, recovered 2020-02-19 |
| Third fall | -33.7173%, 2020-02-19 to 2020-03-23, recovered 2020-08-10 | -28.7102%, 2020-03-23 to 2020-04-07, recovered 2020-04-23 |

SPY on the 5-year range from 2021-11-18 (1,220 days): 12.1444% a year, volatility 17.3284%, Sharpe 0.5239 (interval -0.367 to 1.415), worst fall -24.4964% (2022-01-03 to 2022-10-12, recovered 2023-12-13).

2. Confirm the claim "moves with the range chips": a 3-year or 5-year request recomputes every number on the shorter sample.
3. Check the Sharpe interval and the "includes zero" wording against the formula, and that no text calls a Sharpe ratio significant or speaks about the future.
4. Check that the section never changes a core number (`test_tp33`) and that a failed or short section still lets the report build.

## 5. Proposals for `docs/methodology.md` (the owner folds them in; contract SC6 item 11)

- **P1. Performance statistics.** The definitions of section 2, as a new numbered section after M7, with the annualisation constant A of M0.
- **P2. Sharpe ratio standard error.** `SE(SR_annual) = sqrt(A) x sqrt((1 + SR_d^2 / 2) / n)`, Lo (2002), valid for iid returns only; the interval is labelled approximate. HAC or bootstrap versions are a later option.
- **P3. Drawdown episodes.** The episode definition, the regained-peak rule (`W >= peak`), the path origin date, trading-day counts.
- **P4. Undefined Sharpe ratio.** `None` when the stock's or the excess return's daily sd is below 1e-8 (the floor of M2 step 7).
- **P5. Panel position.** SC4 gains `450 performance` after `400 price`.

## 6. Open questions for the owner

1. **Version number.** Kept at `"4"` (additive field, contract SC5). Nothing to decide unless the owner wants a bump.
2. **Sharpe definition.** This section subtracts the risk-free rate. The planned factor dashboard (`methodology.md` M12) has a rolling Sharpe with no RF subtraction. If both ship, one definition should win.
3. **Window default.** A stock with a long history (SPY from 1993) shows a very long window by default. Should the panel show a fixed set of windows (1, 3, 5 years and full) side by side? Today it shows the window of the range chips only, as requested.
4. **Peak date at the start.** The path starts on the price date before the first analysed return. The residual section's drawdown (`analytics/residual.py`) reports `None` when the peak is the start of the span. The two conventions differ; one could follow the other.
5. **Excluded rows.** The path skips rows excluded from S (multi-day returns), as every other statistic does, so a drawdown that spans an excluded row is measured over the analysed days only.
6. **iid interval.** The interval ignores autocorrelation and fat tails. Should the section carry a robust (HAC) interval instead, at the price of a methodology addition?
7. **Panel redesign.** The static panel uses existing classes, with a stylesheet that only changes the strip from five to four cells. The larger redesign will restyle it. The React panel is a placeholder.

## 7. Gates (final state)

See `docs/registry/tests.jsonl` lines `T-20261118-1001` to `1008` for the test results. Gate counts at the end of the work are in the report of the branch author (pytest, ruff, pyright, typecheck, lint, vitest, build, size, e2e all pass).

## 8. After validation (2026-11-19)

Review: `docs/reviews/performance-validation-2026-11-19.md` (merge with conditions; the validator's tests TP52 to TP54 are merged). Changes made on this branch in answer:

- **F1 (recovery tolerance).** `analytics/performance.py` compares the path with the running peak using `PEAK_TOLERANCE = 1e-9` (relative), in the regained-peak test and in the peak update (the peak value keeps the larger of the two, the peak date moves to the later day). TP53 is no longer an expected failure and passes; TP55 pins that a real shortfall (0.007%) is still "not recovered". Add the tolerance to P3 when the methodology is written: an episode ends at the first point with `W >= peak x (1 - 1e-9)`.
- **F2 (dashboard needs).** Owner option (a) applied: `drawdown.series` (`dates`, `values`) holds the drawdown `W_j / max W - 1` at each of the n + 1 path points (the origin, then every analysed date), values rounded to 4 decimals, dates as ISO dates like the other series; `TOP_EPISODES` is 5 and `drawdown.episodes` keeps its name. Both are additive; `SCHEMA_VERSION` stays "4". On real SPY from 1993: 8,475 points, 173,551 bytes of JSON (35,013 bytes gzip) in a report of 4,783,987 bytes. Tests TP56 to TP59. The OpenAPI document, the generated types and the section fixture are regenerated.
- **F3 (arithmetic average).** The window sentence no longer quotes `mean_return_annual` (still in the data). The fold says it is higher than the compound figure when returns swing widely because large swings cut compound growth, and that it is not what an investor earned. TP61.
- **F4 (wording).** Sharpe note and worst-fall note use the strings of DV4.7 of dashboard-v2 (TP43, TP44, TP46, TP60). The tile still reads "Worst fall" where DV4.7 says "Largest fall"; the label was left as is.
- **Not done here.** F6 (note on excluded days) and F9 (methodology text) follow later; the React panel is still a placeholder (it can now read `drawdown.series` for the L.6 chart).
