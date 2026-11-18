# Performance section: independent validation

Date: 2026-11-19. Branch under review: `feat/performance` at `cba2599`, checked out as `validate/performance`.
Inputs, read only: `data/prices/SPY_2026-11-18.parquet` and `data/factors/ff5_daily.parquet` of the main checkout (SHA-256 `5223e94f...` and `01657448...`), and two cached ZM files (`ZM_2026-11-18.parquet`, one from an earlier scratch run, SHA-256 `79a2a679...`, one from the `run-dev` worktree, `0be5301e...`; both give the same numbers to the last digit). No network was used.
Environment: Python 3.13.14, numpy 2.5.5, pandas 3.1.1, Node 26.13.0, Windows 11.
Scratch scripts (outside git): `myperf.py` (my own implementation, written from the definitions before I opened the code), `real_mine.py`, `compare.py`, `roundtrip.py`, `rt2.py`, `mutate.py`, `render_check.py`, `se_compare.py`.

**Verdict: MERGE WITH CONDITIONS.** The statistics are right. My own plain-numpy code, written from the owner-approved definitions before I read `analytics/performance.py`, reproduces every number the builder claims for SPY (full history and the 5-year range) and ZM to the last printed digit. It also agrees with the module on 14 synthetic cases with known answers and on 300 random series (some with many ties), with no mismatch. The CAGR, volatility (`ddof = 1`), Sharpe ratio (RF subtracted), Lo (2002) iid standard error, interval, drawdown dates and non-overlapping top-3 rule are all as defined. The existing tests catch 18 of my 21 mutants. I added three tests (separate commit) that catch the other three, plus one strict-xfail test that records F1. The conditions are small. A price that returns exactly to its old high can be reported "not recovered" (F1). The window sentence puts an arithmetic "times 252" figure next to the compound return without saying why they differ (F3). The owner must decide whether this section is also the backend of the dashboard-v2 panel, which needs a drawdown series and five episodes (F2).

---

## 1. Findings, ranked by severity

### F1 (medium): a price back exactly at its old high can be reported "not recovered"

- **Where:** `backend/factordesk/analytics/performance.py:141` (`if value >= peak_value:`), on the path built by `compound_path` (`performance.py:125`, `cumprod(1 + r)`).
- **What is wrong:** the regained-peak test is an exact float comparison on a path compounded from returns. When the price returns exactly to its earlier high, the path built from the product of `P_t / P_{t-1}` ratios can end one unit in the last place below the earlier peak. The episode then stays open: the panel prints "not recovered" (or a later recovery date), although the price is back at the high.
- **Evidence:** `roundtrip.py`: of 2,000 random two-decimal price paths that return exactly to their running-high price, 521 leave the compounded path just below the peak (relative gap below 1e-12). `rt2.py` gives a concrete case. Closing prices 11.96, 105.40, 95.91, 183.85, 127.70, 105.25, 183.85 give a peak `W` of `15.372073578595316` and a final `W` of `15.372073578595314`. The module reports the -42.75% fall with `recovery_date=None`. The test `test_tp53_a_price_back_exactly_at_its_old_high_counts_as_recovered` (strict xfail) records this case.
- **Likelihood:** low for any one report. It is real for stocks without dividends and with two-decimal prices (ZM has no dividends, so its adjusted close equals its close). An exactly equal closing high is not rare there. The builder's TP04 passes only because `0.9 x (1/0.9)` happens to round back to exactly 1.0.
- **Suggested fix:** compare with a relative tolerance, for example `value >= peak_value * (1.0 - 1e-12)`, in both the regained test and the peak update. Document the tolerance in P3 of the hand-off. Then drop the xfail marker from TP53; with `strict=True` it fails the suite as soon as the fix lands. `analytics/residual.py:186` uses the same exact comparison on its residual wealth path. There it matters less, because a residual path does not come from rounded prices.

### F2 (medium, owner decision): the section does not yet carry what the dashboard-v2 panel asks for

- **Where:** `report/sections/performance.py` against `docs/specs/dashboard-v2.md` on `feat/ui-v2-spec` (DV2.5, ticket V13, design L.6 in `docs/design/report-design.md` on the same branch).
- **What differs:**
  1. DV2.5 lists `drawdown_series` ("dates and drawdown values for the chart"). Design L.6 draws a drawdown chart from it. The section has no series, so V14 cannot build that chart from this section.
  2. DV2.5 and L.6 ask for "the largest falls (up to five)". The section keeps three (`TOP_EPISODES = 3`). My brief and the hand-off say three.
  3. The field names differ (`cagr` against `cagr_annual`, `volatility_annual` against `vol_annual`, `drawdown.recovery_date` against `max_drawdown_recovery`, and so on). DV2.5 allows this ("V14 maps any rename"), so this is not a defect.
- **Suggested fix:** the owner chooses, before V14 starts:
  - **(a)** Add `drawdown.series` (dates and `W_j / max W - 1` over the path, n + 1 points; about 8,500 for SPY) and raise `TOP_EPISODES` to 5. Both are additive under SC5.
  - **(b)** V14 drops the chart and shows three falls.

  This does not block this merge, because either option is additive. The choice must be recorded.

### F3 (medium): the window sentence sets a "times 252" average beside the compound return without explaining it

- **Where:** `backend/factordesk/report/panels/performance.py:136-138` (window line) and the second paragraph of `HOW` (`performance.py:52-55`).
- **What is wrong:** for a volatile stock the two "a year" figures differ widely. ZM reads "Return a year +5.3%" in the strip, then "the average daily return times 252 is +19.5%" in the sentence under it. A reader who does not know about the loss that volatility causes to compound growth can take 19.5% as the yearly return. The "How this is computed" fold then calls the three numbers "the two other ways to state the same history". That is not accurate: the arithmetic mean ignores compounding and does not describe the realised history.
- **Suggested fix:** remove the arithmetic figure from the visible sentence, and keep it in the fold with one plain line: "The average daily return times 252 is higher than the compound figure because large swings reduce compound growth; it is not what an investor earned." Alternatively, keep it in the sentence with that explanation.

### F4 (low): the Sharpe wording is weaker than the spec

- **Where:** `report/panels/performance.py:44` and `:96`.
- **What differs from DV4.7:**
  - The Sharpe note reads "Return above the risk-free rate per unit of risk; the interval includes zero". DV4.7 asks for "Return above the factor file's risk-free rate, per unit of volatility. Cannot be told apart from zero." The current text is a hedge, but a technical one.
  - DV4.7 also says that the Sharpe ratio is "always 'above the factor file's risk-free rate'".
  - The worst-fall note reads "not recovered". DV4.7 asks for "not recovered by {date(end)}".
- **Note:** the static panel is not bound by DV4.7 (that section is the React copy), but the two should not disagree.
- **Suggested fix:** use the DV4.7 strings in the static panel too: "Cannot be told apart from zero.", "Above zero at the 5% level." and "Below zero at the 5% level.", plus "not recovered by 30 Sep 2026".

### F5 (low): test gaps on the date conventions (closed by the added tests)

The builder tests did not pin which day is the peak when the path is flat at a high, or which day is the trough when it is flat at a low (mutants M7 and M8 survived). Nor did they pin that an interval ending exactly at 0 counts as including zero (M20). Only TP04 catches "recovery = strictly above the peak" (M6), and only TP06 catches a missing 1/2 in the standard error (M10). Commit `ffd3a42` adds TP52 (flat top and flat bottom) and TP54 (interval boundary at zero). Section 4 has the details.

### F6 (low): rows excluded from S are skipped in the path (builder question 5)

- **Where:** `section_hooks/performance.py:117`, which uses `ctx.sample.ret`, the rows of S only.
- **What it means:** when M2 excludes a row (for example a multi-day return), that price move is missing from the compounded path. The total return and CAGR can then differ from the change in adjusted close over the same dates. SPY and ZM have 0 excluded rows, so the numbers above are unaffected.
- **Check:** for ZM, the price panel shows 62.00 on 18 Apr 2019 (the path origin) and 90.77 on 30 Sep 2026. `90.77 / 62.00 - 1 = 46.40%`, which equals the section's total return.
- **Suggested fix:** keep the rule (every statistic uses S). When `data.n_excluded > 0`, add one sentence: "{k} excluded days are not in the return path."

### F7 (information): without an origin, point 0 and point 1 share one date

`performance_stats(..., origin=None)` dates the starting point at the first analysed date (`performance.py:208`). A fall on day one then has the same peak and trough date. The docstring documents this, and TP15 tests it. The hook always passes the previous price date, so this does not reach a report.

### F8 (information): bundle headroom

`npm run size` reports 396.1 kB raw against a budget of 400 kB. That leaves 3.9 kB for V14, so the real React panel must be lazy, like `ResidualAlphaBody`.

### F9 (information): methodology text

The definitions exist only as proposals P1 to P5 in the hand-off; `docs/methodology.md` is not edited, as the contract (SC6) requires. Ticket V13 of dashboard-v2 says "a methodology section". The owner folds P1 to P5 in. I recommend adding to P1 the tolerance from F1, and the sentence of section 5, Q2 on why M12 subtracts nothing.

---

## 2. What I verified and how

### 2.1 Method

1. I read the hand-off, the contract note, methodology M0, M1.3, M2 and M12, and DV2.5, DV4.2 and DV4.7 of dashboard-v2. I did not read `analytics/performance.py` at this stage.
2. I wrote `myperf.py`:
   - The statistics use plain Python loops for the product, the mean and the `ddof = 1` variance. The Sharpe ratio is undefined when either daily sd is below 1e-8. The standard error is `sqrt(252) sqrt((1 + SR_d^2 / 2) / n)`, and the interval uses the z value `1.959963984540054`.
   - An episode loop follows the definition. The peak moves forward on ties, so the peak is the last day at the high. The trough is updated only on a strictly lower value, so it is the first day at the low. The recovery is the first point at or above the peak. Episodes are sorted by depth, and the sort is stable.
   - The M2 sample is built from scratch. For each ticker row, I count the French dates in `(d_{t-1}, d_t]`; I exclude the row on `no_factor_row`, on two or more French dates, on a NaN or non-positive price, or when the date is after the last factor date. The path origin is the previous price date.
3. I ran it on SPY and ZM and compared with the hand-off table.
4. Only then did I read the code, and I ran both implementations side by side (`compare.py`). For the real data I used `assemble_report` on the cached files, the same path a request takes.

### 2.2 Real data (my code against the builder's claims and against the pipeline section)

| | SPY, 1 Feb 1993 to 30 Sep 2026 | SPY from 18 Nov 2021 | ZM, 22 Apr 2019 to 30 Sep 2026 |
|---|---|---|---|
| Days (mine, section, `data.n_obs`) | 8,474, 8,474, 8,474 | 1,220, 1,220, 1,220 | 1,872, 1,872, 1,872 |
| CAGR | 0.10825777308204199 (identical) | 0.12144363876723285 (identical) | 0.052654040308901084 (identical) |
| Total return | 30.705528968052352 (identical) | 0.7417510306637733 | 0.46403220392042344 |
| Mean x 252 | 0.1199845858228406 (section `...4072`) | 0.12961002278795636 | 0.19470422038352414 (section `...2458`) |
| Volatility | 0.18529253542619256 (section `...9217`) | 0.17328426146622314 | 0.5402723159866715 |
| Sharpe | 0.5150249013612037 (section `...2168`) | 0.5238838666715336 | 0.3075607287213992 |
| SE iid, interval | 0.1724925303833731 (identical), 0.177 to 0.853 | 0.4546095669055286, -0.367 to 1.415 | 0.3669341221534113, -0.412 to 1.027 |
| Worst fall | -0.5518944001105988, 2007-10-09, 2009-03-09, 2012-08-16, 355 and 869 days | -0.24496392325498595, 2022-01-03, 2022-10-12, 2023-12-13, 195 and 294 days | -0.9026639035070247, 2020-10-19, 2024-08-12, not recovered, 958 days |
| Second | -47.5158%, 2000-03-24, 2002-10-09, 2006-10-26 | -18.7552%, 2025-02-19, 2025-04-08, 2025-06-26 | -39.6711%, 2019-06-12, 2019-10-22, 2020-02-19 |
| Third | -33.7173%, 2020-02-19, 2020-03-23, 2020-08-10 | -8.8850%, 2026-01-27, 2026-03-30, 2026-04-14 | -28.7102%, 2020-03-23, 2020-04-07, 2020-04-23 |

- **Agreement:** every number the hand-off states matches to its last printed digit. Every date and day count is identical. The only differences are in the 14th to 16th significant digit of means and standard deviations: a summation-order effect of my loop against numpy's pairwise sum. That explains every difference.
- **Range chips:** the 5-year range (`start=2021-11-18`) recomputes every number on 1,220 days, so the claim "moves with the range chips" holds. TP39 tests the same on synthetic data.
- **Window equals the regression sample:** the section has the same `n` as `data.n_obs`, and the section's `sample` equals `regression.sample` (TP30). My from-scratch M2 sample has the same rows.
- **Total return series:**
  - The section uses `AnalysisSample.ret`, which is `PriceHistory.total_returns` (adjusted close, M1.3) restricted to S. Excess plus RF is not re-added; TP31 checks that `xret + rf == ret` to 1e-15.
  - The Sharpe ratio uses `ret - rf`, computed in `performance.py:193`, identical to `xret`.
  - The path origin is the previous price row (`section_hooks/performance.py:105-110`). For ZM it is 18 Apr 2019, the IPO close, so the total return equals the price panel's first-to-end change (F6).

### 2.3 Synthetic cases (module against my code, `compare.py`)

| Case | Known answer | Result |
|---|---|---|
| Constant daily return 0.0004, n 300, RF 0.0001 | CAGR `1.0004^252 - 1`; sd below floor, so Sharpe null; no episode | equal (CAGR rel. diff 2e-14); Sharpe, SE, interval null; `episodes = ()` |
| Alternating +1% / -1%, n 60, RF 0 | Sharpe 0; vol `sqrt(252) 0.01 sqrt(60/59)`; SE `sqrt(252/60)`; total `0.9999^30 - 1` | all equal |
| Crash and full recovery to the same price (float-friendly case) | recovered | recovered, same dates as mine |
| -30% crash after 30 days at +1%, then 8 days at +5% | depth -0.30, recovered after 8 days | equal |
| Same with 7 days at +5% | not recovered | equal |
| Path ending at its high | every episode closed | equal |
| Monotonic rise | max drawdown 0.0, no dates | equal |
| Constant prices, RF 0.0001 | CAGR 0, vol 0, Sharpe null, no episode | equal |
| Fall on day one | peak = origin date | equal (2019-12-31) |
| Flat top and flat bottom | peak = last day at the high, trough = first day at the low | equal |
| A -100% day | CAGR -1, depth -1, open | equal |
| NaN, +inf in `ret`; NaN in `rf`; a return below -100%; 59 rows | `ValueError` or `InsufficientObservations` | raised; through the hook, `failed` or `insufficient_data` (TP34, TP35) |
| 300 random series (half rounded to 0.001, which gives many ties; half t(3) tails), n 60 to 1,500, varying RF | — | 0 mismatches on CAGR, vol, Sharpe, SE, the three episodes and their dates |

### 2.4 Code reading

| Item | Finding |
|---|---|
| Peak date | Last day at the running high: `value >= peak_value` moves the peak forward while not under water (`performance.py:141-145`). Same convention as `residual.py:185`. |
| Trough date | First day at the low: strict `<` (`:146`). Same as `argmin` in `residual.py`. |
| Recovery | First point with `W >= peak` (`:141`), exact comparison (F1). Same rule as `residual.py:186`. |
| Day counts | Positions on the path: peak to trough `t - p`, trough to recovery `r - t`. SPY: 355 and 869. |
| Top 3 | Episodes are disjoint by construction (each starts at a running peak after the previous one closed); `sorted` is stable, so a tie keeps the earlier episode. TP03 checks that they do not overlap. |
| Annualisation | `A` is imported from `regression.py` (252). CAGR `final ** (A / n) - 1`; vol `sqrt(A) sd`; SE `sqrt(A) sqrt((1 + SR_d^2 / 2) / n)`. These are Lo (2002, eq. for iid returns) for the daily ratio, scaled by `sqrt(q)` with `q = 252`. `1 + SR^2 / 2` is the iid normal asymptotic variance; the 1/2 is present. |
| ddof | 1 for both standard deviations (`:197-198`). |
| Sharpe floor | `None` when `sd(r) < 1e-8` or `sd(x) < 1e-8`. `SD_FLOOR` equals `sample.MIN_RETURN_SD` (TP24), the documented M2 step 7 floor with its reasoning (a one-cent move on a 1,000 price is 1e-5). In the pipeline `sd(r) < 1e-8` is already refused by M2, so the floor acts only for other callers and for `r - RF` being constant. The floor is principled and documented (module docstring, hand-off P4). |
| `ci_includes_zero` | `lo <= 0 <= hi`, null when the ratio is null (`section_hooks/performance.py:76`). |
| Non-finite guard | Inputs are checked; outputs are checked for CAGR, total, mean, vol and mean excess. The Sharpe fields are finite whenever they are not null (sd at least 1e-8). |

### 2.5 Sharpe interval: iid against robust versions (`se_compare.py`, for builder question 6)

| | SR | SE iid (section) | SE with skew and kurtosis (Mertens 2002) | SE HAC (M0.5 lag rule, delta method on mean and variance) | Hedge changes? |
|---|---|---|---|---|---|
| SPY full | 0.515 | 0.1725 | 0.1728 | 0.1546 (L 10; daily lag-1 autocorrelation -0.08) | no |
| ZM | 0.308 | 0.3669 | 0.3633 | 0.3370 (L 7) | no |

On these two series the iid interval is about 10% wider than the HAC one, so it is the cautious one, and the non-normality correction is below 1%.

---

## 3. Contract, robustness and wording

| Check | Result |
|---|---|
| Optional field | `FactorReport.performance: PerformanceSection \| None = None` |
| Statuses | `Status` literal of `base.py` (`ok`, `insufficient_data`, `not_applicable`, `failed`); the hook emits `ok`, `insufficient_data`, `failed` |
| Parts only when ok | model validator (`sections/performance.py:109-117`), TP28 |
| Failure never blocks | everything inside `try` in `build_performance`, including `_origin`; TP35 and TP40 (a `RuntimeError` gives `failed`); the core report is unchanged by the hook (TP33) |
| `SCHEMA_VERSION` | `"4"`, supported `("3", "4")` |
| Old files | the dev `mock_report.json` (no `performance` key) loads with `performance = None`; the regenerated mock differs from dev only by `"performance": null`; `mock_report_v3.json` loads (TP27) |
| React | placeholder only (`PerformancePanel.tsx`: null when the field is null, the frame with the reason when not ok); the same `=== null` pattern as the other five section stubs |
| Static position 450 | between Price (400) and Exposures (500). Rendered SPY and ZM pages: `price, performance, exposures, returns, risk, residual, rolling, kalman, data, detail`. Matches DV1 of dashboard-v2. Sensible: the four numbers read off the price path. |
| Footnote | "Past performance does not predict future performance." present on both pages |
| Forecast words | the panel text on SPY and ZM contains none of "will", "expect", "likely", "should", "significant", "forecast"; "predict" appears only in the footnote |
| Sharpe hedge | ZM (interval -0.41 to 1.03): "the interval includes zero"; SPY: "does not include zero"; null ratio: "n/a" and "Not defined: the daily returns do not vary". Present, but weaker than DV4.7 (F4) |
| Interval sentence | "it is approximate and assumes independent daily returns" |
| Plain English | good, apart from F3 |
| No attribution text | none in the branch diff or its commit messages |

---

## 4. Mutation results

Method: `mutate.py` applies one textual change, runs `test_performance.py`, `test_section_performance.py` and `test_panel_performance.py` (default markers), records the failing tests and restores the file with `git checkout`. `git status` was clean after every run. TP10 counts once (five parametrised cases).

| # | Mutant (file) | Builder tests that fail | After `ffd3a42` |
|---|---|---|---|
| M1 | volatility sd with `ddof = 0` (`performance.py`) | TP05, TP06, TP22, TP30 | same |
| M2 | Sharpe sd with `ddof = 0` | TP06, TP22, TP30 | same |
| M3 | `A = 365` | TP05, TP06, TP07, TP09, TP10, TP22, TP30 | same |
| M4 | CAGR = arithmetic mean x 252 | TP05, TP06, TP09, TP10, TP19, TP22, TP30 | same |
| M5 | RF not subtracted (`x = r`) | TP06, TP22, TP30 | same |
| M6 | recovery = first day strictly above the peak | TP04 | same |
| M7 | peak = first day at the running high | **none** | TP52 |
| M8 | trough = last day on a tie | **none** | TP52 |
| M9 | overlap allowed (every new low emits an extra episode with the same peak) | TP03 | same |
| M10 | SE without the 1/2 factor | TP06 | same |
| M11 | SE not annualised | TP05, TP06 | same |
| M12 | SE with `n - 1` | TP05, TP06 | same |
| M13 | z = 1.645 | TP06 | same |
| M14 | Sharpe floor removed (`sd_x > 0`) | TP08, TP36 | same |
| M15 | path compounded from excess returns | TP06, TP08, TP09, TP22, TP30, TP36 | same |
| M16 | CAGR exponent `A / (n - 1)` | TP05, TP06, TP09, TP10, TP22, TP30 | same |
| M17 | top episodes shallowest first | TP02, TP21, TP30, TP38 | same |
| M18 | hook ignores the origin (`section_hooks/performance.py`) | TP32 | same |
| M19 | Sharpe divides by `sd(r)` instead of `sd(x)` | TP22, TP30 | same |
| M20 | `ci_includes_zero` strict (`lo < 0 < hi`) (hook) | **none** | TP54 |
| M21 | origin = first analysed row instead of the previous price row (hook) | TP32 | same |

18 of 21 mutants were caught by the builder's tests; all 21 are caught after the added commit. My first version of M7 also created zero-depth episodes and was caught for that reason (TP08, TP12). The corrected M7 above changes only the peak date, and it survived the builder's tests (I reran it against the test files of `cba2599`).

**Tests added (commit `ffd3a42`, test code only):**

| Test | File | What it checks | Kills |
|---|---|---|---|
| `test_tp52_peak_is_the_last_day_at_the_high_and_trough_the_first_day_at_the_low` | `test_performance.py` | flat top on points 1 to 3, flat bottom on 4 to 6: peak point 3, trough point 4, recovery point 7, days 1 and 3 | M7, M8 |
| `test_tp53_a_price_back_exactly_at_its_old_high_counts_as_recovered` | `test_performance.py` | the F1 case; `xfail(strict=True)`, so it fails the suite once F1 is fixed and the marker must then go | records F1 |
| `test_tp54_an_interval_that_ends_exactly_at_zero_includes_zero` | `test_section_performance.py` | intervals `(0, 0.8)` and `(-0.8, 0)` give `ci_includes_zero = True` | M20 |

The tests are not added to `docs/registry/tests.jsonl`. They are software tests, not new claims; the owner can register them under H-1001 if wanted.

---

## 5. Recommendations on the builder's open questions

- **Q1 (version):** keep `"4"`. The field is additive, and SC5 and DV2.1 of dashboard-v2 say feature branches do not bump.
- **Q2 (RF subtraction against M12):** keep RF subtraction, because there is no conflict. Both are the same definition, mean excess return over its sd:
  - M0.4 already says "for factors no RF is subtracted (they are already excess or zero-cost returns)".
  - A stock's total return is not an excess return, so subtracting RF is the M0.4 rule applied to a stock.
  - Write it once in P1 so nobody "harmonises" the two later.
  - The static wording should say "the factor file's risk-free rate" (F4).
- **Q3 (window default):** keep one window, the range-chip window.
  - Every other number on the page uses S. A grid of 1, 3, 5 years and full would put a second set of samples next to the regression and invite comparisons across windows that the page does not support.
  - SPY's 33.6-year window is what the reader asked for. The range chips already give the 3- and 5-year view, and every number moves with them (verified, section 2.2).
- **Q4 (peak date at the start):** keep the performance convention, the price date before the first return. It is a real date with a real price, and on ZM it makes the total return equal the price panel's change.
  - The other rules (last day at the high, first day at the low, first day at or above the peak) are identical in both modules (section 2.4).
  - The residual path has no price on the day before its span, so `None` there is honest.
  - Do not change either now. If the owner wants one rule, the residual section could label its start "start of the span" in text.
- **Q5 (excluded rows):** keep the rule (S only), and add the one-line note of F6 when `n_excluded > 0`.
- **Q6 (iid against HAC):** keep iid for this release, labelled approximate as it is now.
  - On SPY and ZM the HAC standard error (M0.5 lag rule) is about 10% and 8% smaller, and the non-normality correction is below 1%. The hedge changes for neither (section 2.5), and the iid interval is the cautious one here.
  - A HAC interval would need a methodology addition (a delta method on two moments) and a second field. Add it later as `sharpe_se_hac` beside the iid one, never as a silent replacement.
- **Q7 (panel redesign):** fine as a placeholder. The F2 decision decides what V14 can draw.

---

## 6. Gates (run in this worktree, at `ffd3a42`)

| Gate | Result |
|---|---|
| `uv run pytest -q` | 903 passed, 227 deselected, 1 xfailed (TP53), 1 warning (StarletteDeprecationWarning from fastapi), 225 s. The builder's tests are all among the 903; the added commit contributes 2 passes and the xfail |
| `uv run ruff check backend` | All checks passed |
| `uv run ruff format --check backend` | 110 files already formatted |
| `uv run pyright` | 0 errors, 0 warnings, 0 informations |
| `npm ci` | 0 vulnerabilities |
| `npm run typecheck`, `npm run lint` | clean |
| `npm test` | 491 passed in 34 files |
| `npm run build` | built |
| `npm run size` | initial JS 396.1 kB raw, 121.3 kB gzip; budget 400 / 125: within budget (F8) |
| `npm run e2e` | 1 passed (port 8813); no server left listening afterwards |

---

## 7. Conditions before merge

1. **F1:** use a relative tolerance on the regained-peak comparison (and the peak update), then remove the `xfail` marker from TP53 and make it pass.
2. **F3:** the window sentence either drops the arithmetic "times 252" figure or explains in plain words why it is higher than the compound figure. Fix the "two other ways to state the same history" sentence in the fold.
3. **F2:** the owner records the choice for the dashboard-v2 panel: (a) add `drawdown.series` and five episodes (additive), or (b) V14 drops the chart and keeps three falls.

F4 (align the static Sharpe and fall wording with DV4.7), F6 (excluded-rows note) and F9 (methodology P1 to P5 with the F1 tolerance and the Q2 sentence) can follow after the merge. F5 is closed by `ffd3a42`.

Commits on `validate/performance`:
- `ffd3a42` adds TP52, TP53 (strict xfail) and TP54. It holds test code only.
- The next commit adds this review.

No feature code was changed, and nothing was pushed.
