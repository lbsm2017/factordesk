# Residual return section: handoff to the independent validator (2026-11-18)

Branch `feat/residual-alpha`, code state at commit `4518e38` (plus this document, the wiki update and the registry lines). Status of the section: built, tested by its author, **not independently validated**. This document says what exists, what the author's tests show, where the author is unsure, and exactly what the validator must recompute without reading the implementation.

Specification: `docs/methodology-residual-analysis.md` (R0 to R9, owner decisions of 2026-11-18). Oracle: `docs/test-oracle-residual-analysis.md` (TR01 to TR40). Both are unchanged by this work.

## 1. What was built

| Layer | File | Main functions and statuses |
| --- | --- | --- |
| Calculation | `backend/factordesk/analytics/residual.py` | `in_sample_residual`, `point_in_time_betas`, `point_in_time_residual`, `compound_path`, `max_drawdown`, `noise_drawdown_reference`, `hac_location_test`, `summarise`, `gap_statistics`, `decide_verdict` (seven codes), `verdict_message`, `series_diagnostics` (Ljung-Box 10, Jarque-Bera, ARCH 5), `residual_analysis` |
| Stability | `backend/factordesk/analytics/residual_stability.py` | `rolling_alpha` (252 rows), `non_overlapping_alpha` (disjoint windows, Benjamini-Hochberg), `split_half_alpha`, `calendar_years` |
| Section model | `backend/factordesk/report/sections/residual_alpha.py` | `ResidualAnalysis` and nested statistics (`ResidualStats`, `ResidualChart`, `ResidualGap`, `RollingResidualAlpha`, `NonOverlappingAlpha`, `SplitHalfAlpha`, `ResidualYears`, `ResidualAlphaDiagnostics`); the four label texts `RESIDUAL_LABEL_TEXT` |
| Hook | `backend/factordesk/section_hooks/residual_alpha.py` | `build_residual_analysis`; statuses `ok`, `insufficient_data` (point-in-time part when `n < W + 252`), `failed`, `not_applicable` (exact fit); captions, five caveats, warnings (`residual_wipeout`) |
| Static panel | `backend/factordesk/report/panels/residual_alpha.py` | `render_residual_alpha_panel`, registered at position 710, element id `residual` |
| Dashboard panel | `frontend/src/components/report/sections/ResidualAlphaPanel.tsx` (lazy wrapper), `ResidualAlphaBody.tsx`, `ResidualAlphaChart.tsx`, `ResidualAlphaPanel.css` | The body loads as its own script chunk (26 kB), so the initial script stays at 377.0 kB raw and 116.0 kB gzip (budget 400 and 125) |
| Contract | `frontend/src/api/openapi.json`, `types.gen.ts` | Regenerated for the section; report format version 4 |

Stage 3 changes (this step): label texts now travel with the fixture report (`fixtures/sections/label_text.json`, helper `section_labels`, used by `report_with_section` and the frontend `withSection`), so the static panel no longer has a fallback constant; both panels share their wording; the same-days line has its own style; calendar-year sums are percent in cells and decimals in tooltips on both sides; the end-to-end test fails at once when `frontend/dist` is missing or older than `src` (`frontend/scripts/check-dist.mjs`); TR40 was written.

### Wording shared by the two panels

Headings, row names, column heads, tooltips (the R3.5 reading rules), survival texts, severity words ("Note", "Warning", "Error"), state texts, next steps and notes are the same in both panels. The file `backend/factordesk/tests/fixtures/sections/residual_alpha_wording.json` lists them; `test_wording_matches_the_react_panel` (pytest) and "the words of the static panel" (vitest) check it on each side. Survival text: `100% kept`, `more than 200% kept`, `−35% kept (the sign reversed)`, rounded to the nearest 5 points, halves away from zero. The word "survives" appears nowhere a reader sees; it stays as an internal verdict code.

Two deliberate departures from R8.2/R8.3 (the spec table lists fewer rows and puts skew and kurtosis in a drawer; it shows end-of-line annotations): both panels show skew, excess kurtosis and compound growth in the main table, the noise drawdown reference sits under the drawdown value instead of in a tooltip, and the numbers the annotations would carry are in the table under the chart (cumulative at the end, residual return a year, t-statistic). Owner choice 1 (the toggle) exists in the dashboard panel only; the static report draws all three lines, which a page without scripts cannot toggle.

## 2. Tests and ids

Register: `docs/registry/tests.jsonl`. Stage 1 registered TR01 to TR39 (T-20261118-901 to 939, hypothesis H-901). This stage added T-20261118-940 (TR40 on real SPY, with numbers), 941 to 943 (reruns of TR20, TR26, TR37 with measured rates) and 944 (panel wording tests).

| Ids | File | Notes |
| --- | --- | --- |
| TR01 to TR22, TR29 to TR37 | `backend/factordesk/tests/test_residual.py` | TR20 and TR37 have a `slow` Monte Carlo half |
| TR23 to TR28 | `backend/factordesk/tests/test_residual_stability.py` | TR26 is `slow` |
| TR38, TR39, TR11, TR16, TR33 (caption parts) | `backend/factordesk/tests/test_section_residual_alpha.py` | schema, labels, captions, caveats, short history |
| Static panel (19 tests) | `backend/factordesk/tests/test_panel_residual_alpha.py` | numbers, states, escaping, true minus, wording file, label texts, line style |
| Dashboard panel (55 tests with the lazy wrapper) | `frontend/src/components/report/sections/*.test.tsx` | same, plus accessibility and the toggle |
| Contract | `backend/factordesk/tests/test_schema_contract.py`, `frontend/src/test/sectionFixtures.test.ts` | label fixture equals the section specs |
| TR40 | `backend/factordesk/tests/test_residual_live.py` | marker `live`; reads the cached files, never downloads; skips when no cache; AAPL skipped (no cached AAPL file) |
| Browser | `frontend/e2e/smoke.spec.ts` | the residual panel loads as its own chunk and shows its headings |

Gate results at the end of this stage: `uv run pytest -q` 629 passed (210 deselected by the `live` and `slow` markers; the three slow tests and TR40 were run separately and pass); `ruff check backend` clean; `pyright` 0 errors; `npm run typecheck`, `lint` clean; `npm test` 441 passed in 29 files; `npm run build` and `size` within budget; `npm run e2e` 1 passed (ran about ten times without a failure).

### E2E flakiness

The one first-run failure a sibling agent saw could not be reproduced in about ten runs, cold and warm. The e2e serves the built page from `frontend/dist` on a port derived from the checkout path. Two causes fit the report: a stale or missing `dist` (the test then checks an older page, or the server answers 404 and the page-level waits time out after 15 s), or a port still held by another checkout before the per-checkout port change `efa0275`. The first is a property of how the test is run, not of the page, so a global setup now stops the run at once with the reason when `dist` is missing or older than `src`. The test body needed no change.

### Measured Monte Carlo rates (reran 2026-11-18; the slow tests passed, rates from the same loops)

| Test | Repetitions | Measured | Oracle bound |
| --- | --- | --- | --- |
| TR20 point-in-time rejection at 5% under zero alpha | 1000 | 0.051 | 0.026 to 0.074 |
| TR20 in-sample rejection at 5% | 1000 | 0.046 | 0.026 to 0.074 |
| TR20 `abs(alpha_annual) >= 3%` | 1000 | 0.628 | 0.564 to 0.672 |
| TR20 verdict `survives` | 1000 | 0.036 | 0.013 to 0.074 |
| TR20 verdict `reversed` or `mostly_disappears` | 1000 | 0 of 1000 | at most 5 |
| TR20 standard deviation of the annual gap | 1000 | 0.00865 | 0.0070 to 0.0105 |
| TR26 at least one reliable window under zero alpha | 1000 | **0.080** | at most 0.10 |
| TR37 ARCH rejection at 5% under t(5) errors | 400 | 0.0575 | at most 0.0881 |

TR26 note for the validator: 0.080 is about 3.5 binomial standard errors above 5% (standard error 0.0086). The test passes against its own bound of 10%, but the family-wise behaviour of the Benjamini-Hochberg step on the non-overlapping windows is not at the nominal rate in this simulation. The author did not investigate why.

## 3. Real SPY run (TR40), 2026-11-18

Inputs: `data/prices/SPY_2026-11-18.parquet` (sha256 `5223e94ffa5ba9122e6503bdf36116f7bf61979674da9def427a4b3c7d4a5b58`) and `data/factors/ff5_daily.parquet` (sha256 `0165744897146d1a0b328bbf961e2c29bdb117cc235eabc30d044ce3f5430b78`; the French zip it came from has sha256 `e58577223032aa45071a46686f7068900c371b516c9eb04e28e974c34264f84f`, last factor date 2026-09-30). Report built from 2010-01-04 (the T109 to T111 sample), beta window 252, `now` 2026-11-18 15:00 UTC. The data are not committed.

| Quantity | In-sample | Point-in-time |
| --- | --- | --- |
| Span, days | 2010-01-04 to 2026-09-30, 4,211 | 2011-01-03 to 2026-09-30, 3,959 |
| Residual return a year | −0.1228% | −0.2216% |
| 95% interval | −0.5440% to +0.2984% | −0.6283% to +0.1850% |
| Standard error a year | 0.2149% | 0.2075% |
| z (HAC) | −0.571, p 0.568 | −1.068, p 0.285 |
| HAC lags | 9 | 9 |
| Residual volatility a year | 1.2057% | 1.1665% |
| Information ratio (interval) | −0.102 (−0.451 to 0.248) | −0.190 (−0.539 to 0.159) |
| Cumulative, compounded | −2.15% | −3.53% |
| Compound growth a year | −0.130% | −0.228% |
| Hit rate | 49.28% | 49.68% |
| Largest fall | −4.95% (peak 2016-01-25, trough 2021-01-12, not recovered) | −6.24% (peak 2012-08-03, trough 2025-09-17, not recovered) |
| Noise drawdown reference | −5.99% | −5.63% |
| Skew, excess kurtosis | −0.105, 21.31 | −0.013, 28.25 |

- Regression alpha (M3) −0.12277251649375205 a year, R² 0.99500, residual volatility 1.2057% a year. In-sample residual return equals the regression alpha to full precision.
- Same days: in-sample on the point-in-time days −0.0902% a year; gap +0.1314% a year (standard error 0.1227%, z 1.071, p 0.284); share of the full-period alpha earned on those days 0.7346; survival ratio 2.4572 (shown as "more than 200% kept"). Verdict `no_reliable_alpha`, severity `info`, message "Neither residual return can be told apart from zero. Read both lines as noise."
- Rolling one-year alpha: 1.41% of 3,960 windows have a 95% band that excludes zero; HAC lags 4.
- Non-overlapping one-year windows: 0 of 16 reliable (smallest adjusted p 0.606; the 2012-09-18 to 2013-09-19 window has an unadjusted p of 0.048 and alpha −1.21% a year).
- Split halves (2,105 and 2,106 days, split after 2018-05-14): −0.1185% and −0.1393% a year; difference −0.0208% a year (z −0.050, p 0.960).
- Calendar years (in-sample sum, point-in-time sum, decimals in the section): 2020 is the largest, −3.16% and −2.83%; 2021 +2.33% and +0.998%; the 2010 point-in-time sum is absent (the first 252 days are warm-up).
- Diagnostics findings, both series: all three tests reject (p below 0.001): "Residual returns are correlated from day to day. The t-statistics allow for this.", "Residual returns have more extreme days than a normal distribution. Intervals are approximate.", "Residual volatility comes in clusters: calm and turbulent periods alternate. One volatility number averages them."
- The quality gate of M3.6 fired for this sample (`residual_reversal` is the first report warning) although R² is 0.995. The residual section does not repeat that warning.
- Full history (from 1993-02-01, 8,474 days) for information: R² 0.9673, regression alpha −0.5765% a year, point-in-time −0.7956% a year, verdict `survives` (its message reads "holds up out-of-sample" to the reader).

Identities checked in the JSON payload by the live test, tolerance 1e-10: TR01 (b) (residual return equals regression alpha), TR01 (c) and TR28 (yearly sums add to `n alpha_hat`; each yearly sum equals `n_Y alpha_hat` plus the regression residual of that year), TR13 (point-in-time residual return equals the unattributed row `U` of M6.3, recomputed from the cached inputs).

## 4. Known limits and open decisions

Open owner decisions:
1. **Decision 2 (warm-up from earlier data) is not implemented.** With a later start date the point-in-time line starts `W` rows after the chosen start, and nothing is said about earlier data. The spec asks for the first year of betas to use data before the start, with a footnote. Implementing it changes the sample metadata (`S_c`), TR13 and the calendar table.
2. **Survival ratio on a noise alpha.** When neither line differs from zero, the table still prints a survival ratio, which divides two numbers near zero (SPY: 2.457, printed "more than 200% kept"). Proposal for the methodology (not applied; `docs/methodology*.md` was not edited): print survival and "share of the full-period alpha" only when the in-sample alpha is distinguishable from zero (verdicts other than `no_reliable_alpha`), otherwise print "n/a, the in-sample alpha is not distinguishable from zero" in both panels.
3. **TR26 rate 0.080** (above): decide whether the bound of 0.10 stays.
4. **Proposals P1 to P12 of R9.2** (label table, family FR1 in M0.6, minimum samples, the geometric convention, the ARCH call, the tilt/timing note) are still unapplied.
5. **Placement.** The panel is a section of the report; whether it also moves into the Attribution sub-tab and whether the verdict reaches the headline strip are owner decisions (the owner chose: warning only in the residual panel).

Limits of the work:
- Only SPY was run on real data; AAPL (named in TR40) was not cached, so that branch skipped. No other real ticker was checked.
- The static report cannot toggle between "both lines" and "full period"; it draws three lines at once.
- Row names and the table content differ from the R8.2 table as described in section 1.
- Strings with a number inside (drag note, noise note) are filled from the first computed value; the drag note uses the point-in-time volatility in the default view and the in-sample volatility in the full-period view.
- The wording file was generated once from the static constants; the React side must match it, so a wrong word in both panels at once would pass. The validator should read the wording against R3.5, R4.8, R6 and R8.5 of the specification.

## 5. What the validator must recompute (without reading the implementation)

Allowed inputs: the specification (`docs/methodology.md` M0 to M6 and D-decisions, `docs/methodology-residual-analysis.md`), the two cached files below and the oracle. Not allowed: the files under `backend/factordesk/analytics/residual*.py`, `section_hooks/residual_alpha.py`, and the tests that import them.

Inputs and sample:
- Price file `data/prices/SPY_2026-11-18.parquet`, column `adj_close`; factor file `data/factors/ff5_daily.parquet` (columns `Mkt-RF`, `SMB`, `HML`, `RMW`, `CMA`, `RF`, decimals). Sample rule M2: daily simple return from adjusted close, `y = r − RF` on dates present in both files, start 2010-01-04 (first date on or after), end 2026-09-30. Expected `n = 4211`, last date 2026-09-30, `W = 252`, `S_c` = rows 253 to 4211 (2011-01-03 to 2026-09-30, `m_c = 3959`). If these do not match, stop and report: every number below depends on them.
- Full-sample regression (M3): OLS of `y` on the five factors with intercept, HAC with `L(n)` of M0.5, no small-sample correction. Expected `L = 9` for 4,211 and 3,959 rows and `L = 4` for 252 rows.

Recompute from the formulas, with the expected value and tolerance (relative unless stated; the report keeps full precision except per-day series, which keep six significant digits):

| Quantity (formula) | Expected | Tolerance |
| --- | --- | --- |
| `alpha_ann = 252 alpha_hat` (R1.2 item 1, M3.1) | −0.0012277251649375205 | 1e-9 relative |
| `u_t = y_t − beta_hat' f_t`; `252 mean(u)` equals `alpha_ann`; `sum(u) = n alpha_hat` (R1.1, R1.2) | −0.12277% a year | 1e-10 absolute |
| In-sample HAC standard error and z of the alpha, `p` (R3.2: the M3 alpha test) | se 0.002149, z −0.5713, p 0.5678 | 1e-6 |
| `sd(u)·sqrt(252)` = `sigma_e_ann` (R1.2 item 4) | 0.012057218053471689 | 1e-9 |
| Beta `beta_tilde_t` from the 252 rows `t−252..t−1`, `u_tilde_t = y_t − beta_tilde_t' f_t` for rows 253 to 4211 (R4.1) | — | — |
| `252 mean(u_tilde)` over `S_c` (R3.1, R4.3), equal to the unattributed row `U` of M6.3 (R4.4) | −0.002216261335845656 | 1e-9 absolute 1e-10 against `U` |
| Point-in-time HAC se, z, p (R3.2 on `u_tilde`, `L = 9`) | se 0.002075, z −1.0682, p 0.2855 | 1e-6 |
| 95% intervals: estimate ± 1.959964 × se | in-sample −0.005440 to +0.002984; point-in-time −0.006283 to +0.001850 | 1e-6 |
| Residual volatility `sqrt(252) sd(x)` (ddof 1) for `u` and `u_tilde` | 0.012057, 0.011665 | 1e-6 |
| Information ratio and its interval (R3.3) | −0.1018 (−0.4512, 0.2475); −0.1900 (−0.5386, 0.1586) | 1e-4 |
| Cumulative return `prod(1+x) − 1` and compound growth `Q^(252/m) − 1` (R2.1, M0.4) | in-sample −0.021496, −0.001300; point-in-time −0.035251, −0.002282 | 1e-6 |
| Hit rate, skew, excess kurtosis (R3.1) | 0.492757 / −0.10455 / 21.3084; 0.496843 / −0.012656 / 28.2497 | 1e-5 |
| Max drawdown of the compounded line and its dates (R3.1) | −0.049546 (2016-01-25, 2021-01-12, no recovery); −0.062446 (2012-08-03, 2025-09-17, no recovery) | 1e-6; dates exact |
| Noise drawdown reference `exp(−1.2533 σ sqrt(T)) − 1`, σ the residual volatility, T = rows/252 (R3.4) | −0.059904; −0.056303 | 1e-6 |
| Same-days in-sample annual `252 mean(u[253:])`; gap `= in-sample same days − point-in-time`; gap HAC z on `u − u_tilde` (R4.7) | −0.000902; +0.001314; z 1.0708, p 0.2842 | 1e-6 |
| Share of the full-period alpha earned on these days (R4.7) and survival ratio (R4.7) | 0.734645; 2.457209 | 1e-6 |
| Verdict (R4.8, first matching rule): neither tag reliable | `no_reliable_alpha` | exact |
| Rolling 252-row alpha series (R5.1) and the share of stamps whose band excludes zero | share 0.014141414… (56 of 3,960) | share exact; series 1e-5 |
| Non-overlapping windows counted back from the end, 252 rows each, 16 windows, Benjamini-Hochberg q = 0.05 (R5.2) | 0 of 16 reliable; first window 2025-09-30 to 2026-09-30, alpha +0.010860, adjusted p 0.6064 | 1e-6 |
| Split halves at the middle, 2,105 and 2,106 rows (R5.3) | −0.001185 and −0.001393; difference −0.000208, z −0.0501, p 0.9600 | 1e-6 |
| Calendar-year sums (R5.4), in-sample and point-in-time, with the 2011 start of the second | years 2010 to 2026; 2010: −0.006346 and none; 2020: −0.031605 and −0.028279; 2026: +0.014149 and +0.014653 (187 days) | 1e-9 absolute; day counts exact |
| Diagnostics (R6): Ljung-Box lag 10, Jarque-Bera, ARCH 5 lags on the demeaned series | all p < 0.001; statistics 287.6 / 79,674 / 1,193.0 (in-sample), 281.3 / 131,644 / 1,021.5 (point-in-time) | 1e-4 relative |

For the in-sample column the validator can take `e_hat` from its own OLS; the Ljung-Box and Jarque-Bera in-sample values must equal the M3.5 values the report already prints elsewhere.

Further checks that need no author number:
- **No look-ahead (T102/T103 style).** Change `y`, factors and prices only after day `t*`; every `u_tilde_t`, rolling alpha stamp and point-in-time chart value for `t ≤ t*` must not change. Truncate the series at `t*` and compare.
- **Excluded rows are skipped, not filled** (TR11, TR30): the report must not fill with zero or interpolate.
- **Monte Carlo** (own generator, own seed): zero-alpha DGP with market, SMB, HML, RMW, CMA loadings and homoskedastic Gaussian residuals, `n = 2520`. Expected: in-sample and point-in-time 5% rejection both in 0.026 to 0.074; share with `|alpha_ann| >= 3%` near 0.62 for 19% residual volatility; FR1 family rate under zero alpha (TR26): the author measured 0.080 against a nominal 0.05, so the validator's own number is the main open question.
- **A real alpha that should survive and one that should not** (TR19, TR22): strong stable alpha keeps a survival ratio of 0.85 to 1.15 and verdict `survives` code; hindsight-only alpha gives `mostly_disappears` or `reversed`.
- **Wording.** Compare the printed text of both panels with R3.5 (reading rules), R4.8 (verdict messages, with "holds up out-of-sample" in place of "survives"), R6 (findings), R8.4 and R8.5 (states and the five caveats). The shared wording file proves the two panels agree, not that they agree with the specification.
- **Mutation testing** (`wiki/decision-independent-validation-and-mutation-testing.md`): the validator picks its own mutants of the residual modules; suggested targets are the lag of the beta window (off by one), a missing `RF` subtraction, filling a gap row with zero, a changed HAC lag, and the sign of the gap.

Report back with: the sample check (n, dates), a table of expected against recomputed values, any mismatch above tolerance, and the validator's own TR26 rate.
