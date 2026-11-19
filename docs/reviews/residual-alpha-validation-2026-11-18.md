# Residual return section: independent validation

Date: 2026-11-18. Branch under review: `feat/residual-alpha` at `d058a1d`, checked out as `validate/residual-alpha`.
Inputs: the cached files `data/prices/SPY_2026-11-18.parquet` and `data/factors/ff5_daily.parquet` of the main checkout, read only. Their SHA-256 values equal the hand-off (`5223e94f...` and `01657448...`). No network was used.
Environment: Python 3.13.14, numpy 2.5.5, scipy 1.18.1, statsmodels 0.15.0, pandas 3.1.1, Node 26.13.0, Windows 11.
Scratch scripts (outside git): `ref_impl.py` (my own implementation), `spy_check.py`, `spy_module.py`, `synth_compare.py`, `monte_carlo.py`, `mutate.py`, `robustness.py`, `gate_conflict.py`, `rounding.py`.

**Verdict: MERGE WITH CONDITIONS.** The statistics are right. My own implementation, written from the specification before I opened the code, reproduces every number of the section on real SPY data and on eight synthetic data sets to between 1e-16 and 1e-8 relative (the largest differences come from the rounded 1.959964 in the spec against the exact normal quantile in the code). The point-in-time betas use only rows strictly before each day. Lags, annualisation, Benjamini-Hochberg and the verdict table are correct. The existing tests catch 20 of my 22 mutants; I added two tests (separate commit) that catch the other two. The conditions concern what the reader is told: the verdict can contradict the alpha tag when the M3.6 quality gate fires (F1), one row label still says "Survival" and prints a ratio of two noise numbers (F4), and the residual code can stop a whole report on degenerate factor data (F2). Each fix is small.

---

## 1. Findings, ranked by severity

### F1 (high): the verdict ignores the residual quality gate and can contradict the alpha tag

- **Where:** `backend/factordesk/analytics/residual.py:516` passes the daily p-value `reg.fit.pvalues[0]` to `decide_verdict`; `residual.py:253` copies the gated `reg.alpha_tag` into the in-sample column.
- **What is wrong:** when the M3.6 gate fires (non-synchronous prices), M3.2 tags the alpha "reliable" only if the daily test and the 5-day test both reject. The regression KPI and the in-sample column of this panel then show "noise", but the verdict still treats the in-sample alpha as reliable because it reads the daily p-value. The panel can print "In-sample alpha holds up out-of-sample with point-in-time betas (95% kept) and is distinguishable from zero" under a table whose in-sample column shows a "noise" chip for the same alpha. A G4/G5 warning ("mostly disappears") can fire the same way for an alpha the rest of the report calls noise.
- **Evidence:** `gate_conflict.py`, a DGP-A stock with bid-ask bounce (`eta` sd 0.012), alpha 0.0006 a day, n 1260, seeds `[31337, s]`. In the first 21 reports the gate fired in all 21; in 2 of them the daily p was below 0.05 while the gated tag was "noise". Seed 0: daily p 0.0233, regression tag "noise", residual in-sample tag "noise", point-in-time p 0.0443, verdict `survives` with the message quoted above. Seed 20: verdict `survives_not_significant`.
- **Cause:** a gap in the specification. R4.8 says "M3 alpha p-value `p_is`" and does not mention M3.6. D1 says the tag rule is the only rule.
- **Suggested fix:** decide "in-sample reliable" with the gated tag (`reg.alpha_tag == "reliable"`) in G1 to G3, and keep `p_is` for display only. Write it as a methodology proposal for R4.8 ("when the quality gate fires, `p_is < 0.05` is read as the gated alpha tag"). Add a test with a gated regression (`dataclasses.replace(reg, alpha_tag="noise")` with `p < 0.05`) that expects `no_reliable_alpha` or `point_in_time_only`.

### F2 (medium): degenerate factor data in one half stops the whole report

- **Where:** `backend/factordesk/analytics/residual_stability.py:219` (`ols_hac` in `split_half_alpha`); the hook `section_hooks/residual_alpha.py:464` does not catch it.
- **What is wrong:** the contract (SC3.2) says a hook must not raise for data reasons. `ols_hac` raises `DegenerateInputError` when an interaction column `g * f` is collinear with `f`, which happens when a factor is constant over the first half. The core report survives that input (its rolling windows degrade to `failed`), but the residual hook turns it into a failed request.
- **Evidence:** `robustness.py`, n 1300, CMA set to 0 on rows 1 to 700: `assemble_report` raises `DegenerateInputError: factor second half x CMA is a linear combination ...`. Seven other edge inputs (a +900% day, a -97% day followed by triple betas, 320 days of a stale price, n 600 with W 504, W 126, an exact fit) all build a report with the panel.
- **Likelihood:** low with real French factors, but the contract is explicit.
- **Suggested fix:** catch `DegenerateInputError` in `split_half_alpha` and return `status = "failed"` with a reason ("The split-half regression could not be fitted (singular factor design in one half)."). Add the input above as a test.

### F3 (medium): a failure in the lazy panel body blanks the whole dashboard

- **Where:** `frontend/src/components/report/sections/ResidualAlphaPanel.tsx:20-24`.
- **What is wrong:** the body is loaded with `React.lazy` and wrapped only in `Suspense`. There is no error boundary in this file or anywhere in `frontend/src` (`grep` for `ErrorBoundary`, `componentDidCatch`, `getDerivedStateFromError` finds nothing). If the chunk fails to load (for example a tab opened before an upgrade asks for an old hashed file name) or the body throws while rendering, React unmounts the whole report, not only this panel. The brief asks that a section failure leave the rest of the report readable.
- **Evidence:** a temporary probe test: with the body mocked to throw while rendering, a sibling element next to the panel disappears from the page (section 4.3).
- **Suggested fix:** wrap `<Suspense>` in a small error boundary inside `ResidualAlphaPanel.tsx` whose fallback is the same `Panel` frame with an empty state ("The residual panel could not be shown. Reload the page."). Add a vitest that mocks the body import to throw and checks that a sibling element stays visible.

### F4 (medium): "Survival" is still printed, and it is printed for noise

- **Where:** `backend/factordesk/report/panels/residual_alpha.py:736` and `frontend/src/components/report/sections/ResidualAlphaBody.tsx:389`, row "Survival of the alpha with point-in-time betas".
- **What is wrong (two parts):**
  1. Owner decision 4 replaced "survives" with "holds up out-of-sample" in every user-facing string. The verdict messages follow it, and the test `test_wording_has_no_survives_and_no_old_labels` checks only the exact word "survives", so the row label "Survival of the alpha ..." passes.
  2. The ratio is printed even when neither line differs from zero. For SPY from 2010 it reads "more than 200% kept" (s = 2.457 = -0.222% / -0.090%), a ratio of two numbers whose intervals both span zero. It reads as a claim that an alpha exists and survived, which the verdict directly above the table denies ("Read both lines as noise"). The builder raised the same point (hand-off section 4, item 2).
- **Suggested fix:** rename the row (for example "Kept with point-in-time betas") and print "n/a, the in-sample alpha is not distinguishable from zero" for the share and the survival rows when the verdict is `no_reliable_alpha` or `point_in_time_only` (with F1, "in-sample alpha reliable" means the gated tag). Both are owner decisions on R8 wording; the change is in the two panels and the wording file only.

### F5 (low): the verdict message and the table can round the same ratio differently

- **Where:** `backend/factordesk/analytics/residual.py:431` (`ratio_text`, no tolerance) against `report/panels/residual_alpha.py:275` and `ResidualAlphaBody.tsx:120` (`+ 1e-9`).
- **What is wrong:** for a ratio whose decimal value is a half point but whose float is just below it, the message and the table disagree. `0.475 * a_c / a_c` gives `0.4749999999999999`: the G5 message says "keep 45% of it", the table says "50% kept". On a grid of step 1e-5 over [0, 2], three values disagree (0.575, 1.025, 1.275); for ratios computed as `share * a_c / a_c` with eight half-point shares and `a_c` from 0.0001 to 0.0399, 354 of 9,576 cases disagree.
- **Checked and correct:** 12.5% gives 15, 37.5% gives 40, -12.5% gives -15 (sign reversed), 2.5% gives 5, exactly 100% and 200% print as such, 200.00001% prints "more than 200%". Values below -200% are not capped ("−300% kept (the sign reversed)"); R4.7 caps only the top, so this is consistent with the spec, though odd to read.
- **Suggested fix:** one rounding helper. Either put the rounded text into the section (`survival_text`), or give `ratio_text` the same tolerance. Add 0.125, 0.375, 0.575, -0.125 and 0.4749999999999999 to the `survival` list of the wording file.

### F6 (low): edits outside the feature's files

SC7 lets a feature edit its own row, its registries and the generated files. This branch also edits contract files:

| File | Owner (SC7) | Change |
| --- | --- | --- |
| `backend/factordesk/tests/fixtures/sections/__init__.py` | contract | adds `section_labels`; `report_with_section` now adds label texts |
| `backend/factordesk/tests/fixtures/sections/label_text.json` | new, shared by all five features | label texts per section |
| `backend/factordesk/tests/test_schema_contract.py` | contract | `BUILT_SECTIONS`, label-text checks |
| `backend/factordesk/tests/test_panel_registry.py` | contract | placeholder count 6 to 5 |
| `frontend/src/test/sectionFixtures.ts` | contract | `withSection` adds label texts |
| `frontend/src/test/sectionFixtures.test.ts`, `frontend/src/components/report/panelRegistry.test.tsx` | not listed | follow the two changes above |
| `frontend/e2e/smoke.spec.ts`, `frontend/playwright.config.ts`, `frontend/scripts/check-dist.mjs` | not listed | residual headings in the smoke test; a global setup that refuses a stale `dist` |

Each change is small and needed for the section to show up in the fixtures and the smoke test. They still need the owner's agreement, and `label_text.json` should be added to the SC7 table (append-only, like `wiki/index.md`), because the four other features will edit it too.

No file under `docs/methodology*.md`, `docs/test-oracle-residual-analysis.md` or `docs/specs/` is changed. Methodology changes are proposals only (hand-off section 4), as required.

### F7 (low): owner decision 2 is not built

Owner decision 2: "when the user picks a later start date, the first year of point-in-time betas may use data from before that date ... The footnote must say that earlier data was used."

- Today the point-in-time line starts `W` rows after the chosen start and uses no earlier data. That is conservative and has no look-ahead, so nothing printed is wrong.
- The cost is lost data on short ranges: a 3-year range keeps about 2 years of point-in-time residuals, a 2-year range about 1 year (the minimum), and `W = 504` on a range shorter than 3 years gives `insufficient_data`.
- **It does not block the merge.** The decision says "may", and no footnote is needed while earlier data is not used.
- **Condition:** the owner confirms the deferral, and the follow-up is tracked. Building it changes `S_c`, the identity with M6.3 `U` (TR13) and the calendar table.

### F8 (low): test gaps that let mutants through or weaken an oracle

- **M11 and M19 survived** (section 5). No TR17 case has both p-values exactly 0.05, so `>` in place of `>=` in G1 passed every test. No test of the verdict copy uses a true half point, so the message could round halves toward zero unnoticed. I added both tests in a separate commit.
- **TR15 (c)** checks only `trunc.result.dates[-1] == trunc.sample.end`. The oracle asks that every full-sample output of the truncated run (in-sample statistics, gap, verdict, split half, windows) have `SampleInfo.end == date(t*)`.
- **TR12** "off-by-one guard" compares two computations on the data, not the module. The real guard is the `lstsq` comparison above it, which catches M03.
- **Gap sign (M01)** is caught by one assertion only (TR14).

### F9 (information): `ruff format --check backend` fails on four files this branch does not touch

`report/panel_registry.py`, `report/panels/fragility.py`, `report/panels/kalman.py` and `report/panels/lead_lag.py` would be reformatted. None is in this branch's diff, so the problem comes from the base branch. The gate is red whatever this feature does; fix it on `dev` separately.

---

## 2. What I verified and how

### 2.1 Method

1. Before reading any implementation file I read the hand-off, `docs/methodology-residual-analysis.md` (R0 to R9 and the owner decisions), `docs/test-oracle-residual-analysis.md`, `docs/methodology.md` M0.5 and M2, and `docs/specs/schema-v3-contract.md`.
2. I wrote `ref_impl.py` from those texts: plain numpy, no `factordesk` import. It covers the M2 sample rule, OLS with my own Bartlett Newey-West sandwich (no small-sample correction, `L(m) = floor(4 (m/100)^(2/9))`), the in-sample residual, point-in-time betas from the `W` rows `t-W .. t-1` by `lstsq` per day, the compounded path with the wipe-out rule, maximum drawdown with `Q_0 = 1`, the noise drawdown reference, the HAC location test, the rolling 252-row alpha, non-overlapping windows with my own Benjamini-Hochberg, the pooled split-half regression, the calendar sums and the seven-code verdict.
3. I compared it with the hand-off numbers (SPY), then with the report JSON (`build_report` on the cached files, start 2010-01-04), then with the module on synthetic data.
4. Only then I read the code, ran the edge inputs, the mutants and the gates.

### 2.2 SPY (2010-01-04 to 2026-09-30)

Sample: n 4,211, 0 excluded rows, `S_c` 2011-01-03 to 2026-09-30, `m_c` 3,959, `L` 9 for both. All as in the hand-off.

| Quantity | Mine | Hand-off | Report vs mine |
| --- | --- | --- | --- |
| In-sample residual return a year | -0.0012277251649372 | -0.0012277251649375 | 3e-16; equals `regression.alpha_annual` bitwise |
| `252 mean(u) - alpha_ann`, `sum(u) - n alpha_hat` | -2.2e-16, -3.7e-15 | identity | - |
| In-sample se, z, p | 0.002149, -0.5713, 0.5678 | same | below 4e-11 |
| Point-in-time residual return a year | -0.0022162613358460 | -0.0022162613358457 | 3e-16 |
| Point-in-time se, z, p | 0.0020749, -1.0682, 0.2855 | same | below 4e-11 |
| 95% intervals | -0.005440 to +0.002984; -0.006283 to +0.001850 | same | 3.3e-11 (rounded z in the spec) |
| Residual volatility | 0.0120572, 0.0116655 | same | below 4e-11 |
| Information ratio and interval | -0.1018 (-0.4512, 0.2475); -0.1900 (-0.5386, 0.1586) | same | 6.1e-9 relative (rounded z) |
| Cumulative, compound growth | -0.021496, -0.001300; -0.035251, -0.002282 | same | below 4e-11 |
| Hit rate, skew, excess kurtosis | 0.492757, -0.10455, 21.3084; 0.496843, -0.012656, 28.2497 | same | hit rate exact; 3.4e-11 relative |
| Max drawdown and dates | -0.049546 (2016-01-25, 2021-01-12, none); -0.062446 (2012-08-03, 2025-09-17, none) | same | dates exact |
| Noise drawdown reference | -0.059904, -0.056303 | same | below 4e-11 |
| `a_c`, gap, gap z, p | -0.000902, +0.001314, 1.0708, 0.2842 | same | below 4e-11 |
| Share `q`, survival `s` | 0.734645, 2.457209 | same | below 4e-11 |
| Verdict | `no_reliable_alpha` | same | same |
| Rolling alpha: stamps, band excludes zero | 3,960, 56 (0.0141414) | same | series 4.9e-6 relative (6 significant digits, by design); share exact |
| Non-overlapping windows | 16, 0 reliable; latest 2025-09-30 to 2026-09-30, +0.010860, adjusted p 0.6064; smallest raw p 0.0477 (2012-09-18 to 2013-09-19, -1.21%) | same | dates exact, below 4e-11 |
| Split halves | 2,105 / 2,106 rows, split after 2018-05-14; -0.001185, -0.001393; difference -0.000208, z -0.0501, p 0.9600 | same | 5.5e-11 |
| Calendar sums (2010, 2020, 2026) | -0.006346; -0.031605 / -0.028279; +0.014149 / +0.014653 (187 days) | same | below 4e-11, counts exact |
| Ljung-Box, Jarque-Bera, ARCH (in-sample; point-in-time) | 287.6, 79,674, 1,193.0; 281.3, 131,644, 1,021.5; all p < 0.001 | same | findings strings equal; statistics compared with the hand-off only |
| Point-in-time chart | anchor 0.0 at 2010-12-31 (row 252), 251 nulls before | - | 5e-8 absolute (6 significant digits) |

115 comparisons in total. The largest differences are 6.1e-9 relative (the IR interval, from the rounded z) and 5.5e-11 (the second-half interval); everything else is below 4e-11. None is outside the hand-off tolerances.

### 2.3 Synthetic data with known truth (module against my code)

| Case | n, W | Truth | Module verdict | Worst relative difference |
| --- | --- | --- | --- | --- |
| Zero alpha, normal errors | 2520, 252 | alpha 0 | `no_reliable_alpha` | 3.6e-9 |
| Alpha 0.0008 a day, normal | 2520, 252 | 20.2% a year | `survives` (in-sample 23.4%, z 4.88; point-in-time 23.5%, z 4.58; s 1.04) | 2.8e-9 |
| Alpha 0.0004, Student t(3) errors | 2520, 252 | 10.1% a year | `no_reliable_alpha` (z 1.91) | 3.8e-9 |
| Zero alpha, Student t(2.5) errors | 2520, 252 | 0 | `no_reliable_alpha` | 9.9e-9 |
| Random-walk market beta, alpha 0.0003 | 2520, 252 | 7.6% a year | `no_reliable_alpha` | 3.5e-9 |
| W 126 | 1500, 126 | - | `no_reliable_alpha` | 2.6e-9 |
| W 504 | 1500, 504 | - | `point_in_time_only` | 2.8e-9 |
| n 2600 (80 unused head rows) | 2600, 252 | 0 | `no_reliable_alpha` | 2.9e-9 |

Compared per case: `u_tilde` row by row, both summaries (mean, se, z, volatility, cumulative, drawdown and its dates, noise reference, skew, kurtosis, HAC lags), gap, `s`, verdict, the rolling alpha and its band, every window's adjusted p and dates, the split half, the calendar sums. All differences come from the rounded z constant or float order.

### 2.4 Code reading: look-ahead, lags, annualisation

- **Point-in-time betas use only rows before `t`.** `point_in_time_betas` returns `rolling.ex_ante_betas`, which is `rolling.betas.shift(1)`, and the M4 window stamped `t-1` holds rows `t-W .. t-1`. My `lstsq` betas on exactly those rows match `u_tilde` to 1e-12 on SPY and on all synthetic cases. Warm-up rows are NaN, never 0. The truncation and perturbation tests (TR15) pass, and mutant M03 (no shift) fails 7 tests.
- **No look-ahead in the comparison lines.** The anchor is positional (row `W`), and the lines compound only `x[W:]`.
- **HAC.** The location test uses `L(m)` of its own series (9 for SPY, 8 for 2,268 rows, 4 for 252), the Bartlett weights, no small-sample correction, and `se = sqrt(meat) / m`, which is the constant-only sandwich. The in-sample inference is copied from M3, as RD2 requires; nothing is re-tested on `u`.
- **Small samples.** `n - W < 252` gives `insufficient_data` with the R3.6 reason; a constant series gives `not_applicable`; an exact fit gives `not_applicable` for the whole section. Fewer than two one-year windows or a half shorter than 252 rows give `insufficient_data` (unreachable while the report needs 504 rows).
- **Annualisation.** Mean and se times 252; volatility times `sqrt(252)`; IR = annual mean / annual volatility; compound growth `Q^(252/m) - 1`; noise reference `sqrt(m/252)` years. All as R3.1.
- **Benjamini-Hochberg.** `statsmodels.multipletests(..., "fdr_bh")` at q 0.05 over the `J` window p-values, windows tiled from the end; my own BH gives the same adjusted p-values and rejections.
- **Verdict.** First matching rule, thresholds fixed, `q` and `s` `None` on a zero denominator; the 12 dyadic cases of TR17 give the expected codes. The only problem is the input `p_is` (F1).
- **Diagnostics.** In-sample on `e_hat` (equal to the M3.5 values), point-in-time on the demeaned series, `het_arch` with `result_object=True`.

### 2.5 Monte Carlo (own generator, own seeds `[777000, r]`, own code)

DGP-R0 moments (DGP-A factors and betas, Gaussian errors sd 0.012, alpha 0, n 2,520, W 252), 1,000 replications.

| Rate | Mine | Builder | Oracle bound |
| --- | --- | --- | --- |
| Point-in-time rejection at 5% | 0.054 | 0.051 | 0.026 to 0.074 |
| In-sample rejection at 5% | 0.063 | 0.046 | 0.026 to 0.074 |
| `abs(alpha_annual) >= 3%` | 0.639 | 0.628 | 0.564 to 0.672 |
| Verdict `survives` | 0.039 | 0.036 | 0.013 to 0.074 |
| `reversed` or `mostly_disappears` | 0 of 1000 | 0 | at most 5 |
| sd of the annual gap | 0.00867 | 0.00865 | 0.0070 to 0.0105 |
| TR26: at least one reliable window (first 1,000) | 0.066 | 0.080 | at most 0.10 |
| TR26 over 5,000 replications | 0.0718 (se 0.0037) | - | at most 0.10 |
| Per-window size of the 252-row HAC test at 5% | 0.0588 | - | 0.058 (R5.2 calibration) |

## 3. Builder flags

### 3.1 TR26 rate 0.080: acceptable

- The right reference is not the nominal 5%. R5.2 and TR26 already say the family rate is about 7% because each 252-row HAC test over-rejects (size 5.8% at 5%) and BH is exact only for exact tests. The oracle's calibration is 0.072.
- My rate over 5,000 replications is 0.0718 (standard error 0.0037), with a per-window size of 5.88%, matching both calibration numbers.
- The builder's 0.080 from 1,000 replications is one binomial standard error (0.0082) above 0.072, which is ordinary Monte Carlo noise. Comparing it with 5% (3.5 standard errors) used the wrong baseline.
- Keep the bound at 0.10. Nothing to investigate in the code.

### 3.2 Owner decision 2 not built: does not block the merge

See F7. The current behaviour is conservative (no earlier data, no look-ahead), so nothing shown is wrong; the owner should confirm the deferral, and the follow-up should be tracked.

## 4. Wording, contract, runtime

### 4.1 Wording

- **Same strings in both panels.** Both panels read `residual_alpha_wording.json` in their tests, and both print the verdict message from the section. The rounding helpers are duplicated in Python and TypeScript with the same tolerance; the message uses a third helper (F5).
- **Against the specification:**
  - The reading rules match R3.5.
  - The cumulative and compound-growth rule is split into two tooltips, and the noise reference moved under the drawdown value.
  - The verdict messages match R4.8 with "holds up out-of-sample" (owner decision 4).
  - The findings match R6, the five caveats match R8.5, the captions match R7.9, and the state texts match R8.4.
  - G1 says "cannot be told apart from zero" and "read both lines as noise". No text says an alpha "is zero".
  - The in-sample "same days" row of the chart table shows "n/a" for its t-statistic instead of borrowing the full-period t. This is better than the R8.3 annotation.
- **Over-claiming:** F1 (a gated "noise" alpha read as reliable) and F4 (survival printed for noise).
- **Survival rounding:**
  - Nearest 5 points, halves away from zero: 12.5 gives 15, 37.5 gives 40, -12.5 gives "−15% kept (the sign reversed)".
  - Exactly 100 and 200 print as such; above 200 prints "more than 200% kept". Small negatives print "0% kept".
  - The only defect is F5.
- **Style:** sentence case, no `text-transform`, no `letter-spacing`, no monospace in the panel CSS or markup (grep, plus `test_no_monospace_and_no_all_caps_eyebrow`), true minus signs in the panels.
- **The two documented departures are acceptable.**
  - Skew, excess kurtosis and compound growth sit in the main table, and the noise reference sits under the drawdown, not in a drawer or a tooltip. A static page has no hover, and the tooltip-only placement of R8.2 would hide the reading aid there.
  - A table under the chart replaces the end-of-line annotations. It carries the same numbers, and it does not attach the full-period t to the same-days return.
  - The static report draws all three lines because it cannot toggle; the dashboard opens on the two comparison lines (owner decision 1).
  - The spec text should be updated to match (a proposal, not an edit).

### 4.2 Contract

- **Optional section.** `residual` defaults to `None`; an absent section draws nothing in both renderers (`test_absent_section_draws_nothing`, the vitest "renders nothing while the section is null").
- **Statuses, each tested:**
  - `ok`;
  - `insufficient_data` for the point-in-time part when `n < W + 252` (TR16, the panel test, and my run with n 600 and W 504);
  - `failed` when the regression is not ok (`test_failed_regression_gives_the_failed_state`);
  - `not_applicable` on an exact fit (`test_exact_fit_is_not_applicable`, and my run).
- **Hook failure.** A raise inside any hook still fails the whole `assemble_report` (my probe: `RuntimeError` propagates). The contract only requires that hooks never raise for data reasons, and the pipeline (contract-owned) has no isolation. So "section absent plus a notice" is not implemented anywhere today. That is a contract decision, not this feature's; F2 is the one data reason I found that breaks the rule.
- **Old files.** `test_version_3_file_still_loads` and `test_version_3_file_cannot_carry_a_section` pass. The report format stays "4", as SC5 requires.
- **Ownership:** see F6.

### 4.3 Frontend failure probe

I ran a temporary vitest (deleted afterwards, not committed) that renders `<div><p>sibling panel</p><ResidualAlphaPanel/></div>` with the body module mocked to throw while rendering. After 800 ms the sibling paragraph was gone: React unmounted the whole tree and vitest reported the unhandled error "body failed to render". A mocked chunk-load failure (the mock factory itself throwing) did not reproduce in jsdom, so that path rests on code reading. In both cases the cure is the same error boundary (F3).

### 4.4 Runtime and size (SPY, 4,211 days)

- First run: whole report 1.77 s, residual hook 0.22 s. Median of three later runs: report 1.27 s, hook 0.08 s. The hook reuses the M4 fits for W 252; these runs shared the machine with the slow tests, so treat them as upper bounds.
- The report JSON grows to 1,735 kB, of which the residual section is 401 kB (23%); gzip 514 kB and 117 kB.
- The section repeats the 4,211 dates in `chart.dates` and in `rolling_alpha.dates`: about 55 kB per list, 110 kB of the 401. Sharing one date list would save one copy, but it is a schema change, not needed now.
- Full SPY history (from 1993-02-01, 8,474 days):
  - Timing: report 1.81 s, hook 0.23 s (medians of three).
  - Size: report JSON 3,163 kB, of which the section is 777 kB (25%).
  - Result: verdict `survives`, in-sample -0.58% a year (p 0.025), point-in-time -0.80% a year (p 0.0024), as in the hand-off. The quality gate fired here too, but the 5-day test also rejects, so the alpha tag is "reliable" and F1 does not change this verdict.
- Cost is acceptable for a page that already carries 1.3 to 2.4 MB of other series. The section is about a quarter of the payload, so watch the total if the four other optional sections add as much.

## 5. Mutation results

Method: `mutate.py` applies one textual change to a residual module, runs the four residual test files (`test_residual.py`, `test_residual_stability.py`, `test_section_residual_alpha.py`, `test_panel_residual_alpha.py`, default markers, so no `slow` or `live`), records the failing tests and restores the file. `git status` was clean after the run.

| # | Mutant (file) | Tests that fail |
| --- | --- | --- |
| M01 | Gap sign flipped, `a_pit - a_c` (`residual.py`) | TR14 |
| M02 | Residual sign, `y + F beta` (`residual.py`) | 11: TR01, TR02, TR04, TR08, TR19, TR20, TR21, TR28, TR31, TR33, TR34 |
| M03 | Point-in-time betas include day `t` (no `shift(1)`) (`residual.py`) | 7: TR12 (W 126, 252, 504), TR15a, TR15b, TR19, TR32 |
| M04 | HAC lag `L(m) + 1` in the location test (`residual.py`) | TR14, TR16, TR16 (section) |
| M05 | HAC lag fixed at 4 in the location test (`residual.py`) | TR14 |
| M06 | Benjamini-Hochberg skipped: raw `p < 0.05`, adjusted p = raw p (`residual_stability.py`) | TR24 |
| M07 | Standard error annualised with `sqrt(252)` (`residual.py`) | TR14, TR19 |
| M08 | Volatility annualised with 252 (`residual.py`) | TR02, TR04, TR07, TR08, TR19 |
| M09 | Compound growth exponent `m / 252` (`residual.py`) | TR05, TR07 |
| M10 | Survival threshold 0.4 instead of 0.5 (`residual.py`) | TR17 case 8 |
| M11 | G1 with `>` instead of `>=` (`residual.py`) | **none** (killed by the added test, below) |
| M12 | Warm-up share threshold 0.25 instead of 0.5 (`residual.py`) | TR17 case 4 |
| M13 | Warm-up rows filled with 0 instead of NaN (`residual.py`) | TR12 (three windows), TR28 |
| M14 | Point-in-time diagnostics not demeaned (`residual.py`) | TR36 |
| M15 | Split-half dummy read from the wrong column (`residual_stability.py`) | TR27 |
| M16 | One-year windows end one row early (`residual_stability.py`) | TR24, TR25, TR39 |
| M17 | Noise drawdown without `sqrt(pi/2)` (`residual.py`) | TR08 |
| M18 | Calendar point-in-time noise uses the in-sample sd (`residual_stability.py`) | TR28 |
| M19 | Verdict copy rounds halves toward zero (`residual.py`) | **none** (killed by the added test, below) |
| M20 | Static panel rounds halves toward zero (`panels/residual_alpha.py`) | wording test |
| M21 | Drawdown ignores the starting value `Q_0 = 1` (`residual.py`) | TR05 |
| M22 | Hit rate counts zero days (`residual.py`) | TR05 |

All six mutant types the brief asks for are caught:

| Requested type | Mutants |
| --- | --- |
| Wrong sign | M01, M02 |
| Point-in-time betas up to `t` inclusive | M03 |
| Wrong HAC lag | M04, M05 |
| Skipped BH correction | M06 |
| Wrong annualisation | M07, M08, M09 |
| Wrong verdict threshold | M10, M12; M11 only after the added test |

20 of 22 mutants were caught by the existing tests.

**Tests added (separate commit `c84ab31`, `backend/factordesk/tests/test_residual.py`, test code only):**

| Test | What it checks | Kills |
| --- | --- | --- |
| `test_tr17_both_p_values_exactly_at_the_level` | `p_is = p_pit = 0.05` gives `no_reliable_alpha` | M11 |
| `test_tr18_message_rounds_half_points_away_from_zero` | dyadic ratios 0.125, 0.375 and 1.125 print 15%, 40% and 115% in the verdict copy | M19 |

I reran M11 and M19 against the new tests: each now fails exactly the added test.

## 6. Gates (run in this worktree)

| Gate | Result |
| --- | --- |
| `uv run pytest -q` | at `d058a1d`: 629 passed, 210 deselected (`live`, `slow`), 1 warning, 185 s; with the two added tests (`c84ab31`): 631 passed, 210 deselected, 196 s |
| `uv run pytest -q -m "slow or live"` on the three residual test files, `DATA_DIR` set to the cached data | 4 passed (TR20 Monte Carlo, TR26, TR37 slow, TR40 SPY), 1 skipped (TR40 AAPL: no cached file), 801 s |
| `uv run ruff check backend` | clean |
| `uv run ruff format --check backend` | 4 files would be reformatted, none touched by this branch (F9) |
| `uv run pyright` | 0 errors, 0 warnings |
| `npm ci` | 0 vulnerabilities |
| `npm run typecheck`, `npm run lint` | clean |
| `npm test` | 441 passed in 29 files |
| `npm run build` | built; `ResidualAlphaBody` is its own chunk (26.40 kB, gzip 7.57 kB) |
| `npm run size` | initial JS 377.0 kB raw, 116.0 kB gzip, budget 400 / 125: within budget |
| `npm run e2e` | 1 passed (port 8853, derived from this checkout); no server left running |

The lazy body is needed for the budget: loaded eagerly it would add 26.4 kB and bring the initial script to about 403 kB, over 400.

## 7. Conditions before merge

1. **F1:** in-sample reliability for the verdict comes from the gated alpha tag, with a test; the R4.8 change is written as a methodology proposal for the owner.
2. **F4:** the owner chooses the survival wording; at least the row label loses "Survival", and the share and survival rows show "n/a" when no in-sample alpha is reliable.
3. **F2:** `split_half_alpha` returns `failed` instead of raising on a degenerate half, with a test.
4. **F3:** an error boundary around the lazy body, with a test.
5. **F6 and F7:** the owner agrees to the contract-file edits (and adds `label_text.json` to SC7) and confirms that decision 2 is deferred.

F5, F8 and F9 can follow after the merge.

Commits on `validate/residual-alpha`: `c84ab31` adds the two tests of section 5 (test code only); the next commit adds this review. No feature code was changed. Nothing was pushed.
