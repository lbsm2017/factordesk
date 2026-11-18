# factordesk research protocol

Status: v1, written 2026-11-18. Applies to every new statistic, test, dataset use or parameter before it ships, and to every claim we write about results (docs, release notes, UI text).
Companions: `docs/methodology.md` (binding conventions, M0.6 families), `docs/methodology-datasets.md` (D-sections), `docs/datasets.md` (data facts), `docs/test-oracle.md` and `docs/test-oracle-datasets.md`.
A reviewer applies sections 1-9 as a checklist: every box must be ticked or answered "n/a, because ...". Appendices A-D hold formats and numbers.

---

## Checklist

### 1. Hypothesis, written before any result is seen

- [ ] One sentence: what is claimed, about which population (one ticker's report, all tickers, a factor), over which sample.
- [ ] The null hypothesis and the exact test: estimator, regressors, intercept, HAC lag rule (M0.5), test statistic, sidedness, reference distribution.
- [ ] The decision rule and its family (item 3).
- [ ] The primary specification: dataset key(s) and vintage stamp (D2, D5), window, sample dates, FX source (D9.3), RF rule (D11).
- [ ] The result that would count **against** the hypothesis, in numbers.
- [ ] Entered in the test registry (Appendix A) with status `pre-registered` **before** the first run. Commit the registry line in the same change as the spec.

### 2. Test registry

- [ ] Every run of every specification is a registry line, including variants that were abandoned, failed, or "just looked at" (a chart inspected to choose a parameter is a test).
- [ ] Parameter values tried are each a line (a grid of 9 windows is 9 lines).
- [ ] The line holds the result (statistic, p-value, n, dates) even when the result is uninteresting.
- [ ] Lines are never edited or deleted; corrections are new lines with `supersedes`.

### 3. Multiple-testing correction

- [ ] The family is named. Per-ticker report statistics use the families of M0.6 (F1-F8, plus amendments in D16). Research claims across tickers, datasets or specifications form a family per hypothesis id: **all** registry lines with that `hypothesis_id`, whatever their status.
- [ ] Rule: Benjamini-Hochberg, `q = 0.05` (M0.6), with `m` = the number of registry lines in the family, not the number reported.
- [ ] A claim is "significant" only after correction. Unadjusted p-values may be shown only next to the adjusted ones.
- [ ] Single pre-registered confirmatory tests (one line, `m = 1`) are allowed and say so.

### 4. Sample split and out-of-sample policy

- [ ] Time split fixed before running: estimation on data dated `<= 2015-12-31`, confirmation on `2016-01-01` to the vintage's last date, unless the registry line states another split and why. Confirmation data are not looked at (no charts, no summary statistics) before the estimation result is registered.
- [ ] Cross-sectional claims: tickers are listed in the registry line before any data are fetched; if a holdout set is used it is drawn with a seeded `numpy.random.Generator` (seed in the line).
- [ ] Per-ticker descriptive panels are in-sample by nature and carry L-DESC; they are not "validated" by this protocol, only specified by it.
- [ ] Anything chosen on the confirmation data (a threshold, a window, a region) turns the confirmation sample into an estimation sample; record it and get a new holdout.

### 5. Robustness grid (defined before running)

- [ ] Grid axes, each value listed in the registry line: windows `{126, 252, 504}`; factor dataset (primary + the D8.2 alternative); factor set (FF5; FF5 + MOM once D15 ships); sub-periods (1990-2006 and 2007 onward for regional data, plus the M10.3 windows when covered); frequency (daily; weekly for any dataset with markets in other time zones, D14); FX source (ECB vs Yahoo, D9.3); RF rule (daily file vs monthly-derived, D11).
- [ ] **Robust** means all of: (a) the primary specification is significant after correction; (b) the estimate has the same sign in every grid cell with status `ok`; (c) in at least 75% of `ok` cells the estimate lies inside the primary specification's 95% interval; (d) no single axis value flips the conclusion on its own. Anything else is reported as "not robust", with the failing cells listed.
- [ ] Grid cells are tests: they are registry lines and count in `m` when a claim is made about them.

### 6. Power

- [ ] Before running: the minimum detectable effect (MDE) at 80% power for the sample `n`, the factor volatilities of the dataset used and a stated residual volatility (Appendix B gives the formula and a table).
- [ ] A non-significant result is reported as "cannot be told apart from zero; effects smaller than {MDE} would usually be missed", never as "no effect".
- [ ] If the MDE exceeds the effect the hypothesis is about, the test is not run as a confirmation (it may still be shown descriptively).

### 7. Replication before trust

- [ ] The pipeline reproduces the replication targets of Appendix C (RT1-RT3 automated, `docs/test-oracle-datasets.md` TD44-TD45) on the vintage in use.
- [ ] A new dataset or parser change ships only after its own target passes.
- [ ] Published-paper targets (RT4-RT5) are compared, with the expected vintage gap stated, before a claim cites those papers' numbers.

### 8. Data-snooping and look-ahead audit

- [ ] Static scan T104 passes (no negative shifts, centred windows, back-fills, interpolation, fills).
- [ ] Perturbation tests T102-T103 extended to the new statistic (rows after `t*` changed, outputs stamped `<= t*` unchanged).
- [ ] FX: rates are dated in the quote's own time zone (D9.3); no FX value dated after the stock's row is used; audit-only rules that look one row ahead (`fx_spike`) never feed a statistic.
- [ ] Vintage: every number uses one recorded vintage per dataset (D5); the registry line holds its stamp and SHA-256. A result that changes only because the vintage changed is reported as a revision, not a finding.
- [ ] Selection: tickers, windows, regions and thresholds were not chosen after seeing results; if they were, the registry shows it and item 3's `m` includes the discarded options.
- [ ] Survivorship and listing: the sample is "tickers that exist today" (M1.5), stated in the claim.

### 9. Reporting standard and definition of done

Every reported number carries: `n`; first and last date actually used; in-sample or out-of-sample flag; dataset key, stamp and SHA-256 (D5.1); FX source and RF rule when relevant; the registry `test_id`; the family and `m` when it is a test.

Done means all of:

- [ ] Section in `docs/methodology.md` or `docs/methodology-datasets.md` (formula, sample, family, label).
- [ ] Schema in `report/schema.py` with `status`, `reason`, `SampleInfo` (M14).
- [ ] Oracle tests (identity, recovery on a DGP, look-ahead, failure modes) written before the code and green.
- [ ] Registry lines for every run, with the final status.
- [ ] Power statement and robustness verdict attached to any claim.
- [ ] Reviewer has ticked sections 1-8.

---

## Appendix A. Test registry format

File: `docs/registry/tests.jsonl` (JSON Lines, UTF-8, append-only, one object per line, committed with the change that runs the test). One file for the project; `hypothesis_id` groups lines into families.

| Field | Type | Meaning |
| --- | --- | --- |
| `test_id` | str | `T-YYYYMMDD-NNN`, unique |
| `hypothesis_id` | str | `H-NNN`; defines the correction family for research claims |
| `created_at` | ISO 8601 UTC | when the line was written |
| `status` | enum | `pre-registered`, `run`, `abandoned`, `failed`, `superseded` |
| `supersedes` | str or null | `test_id` this line corrects |
| `hypothesis` | str | one sentence (item 1) |
| `test` | str | estimator, statistic, HAC lag, sidedness |
| `spec` | object | `datasets` [{`key`, `stamp`, `sha256`}], `tickers`, `window`, `start`, `end`, `fx_source`, `rf_rule`, `frequency`, other parameters |
| `split` | object | `role` (`estimation`, `confirmation`, `in_sample_only`), `cutoff`, `seed` |
| `family` | str | M0.6 id (`F1`...) or `hypothesis_id` |
| `mde` | object | `alpha_ann`, `betas`, assumptions (Appendix B) |
| `result` | object or null | `estimate`, `se`, `stat`, `p`, `p_adj`, `n`, `first_date`, `last_date`, `m_family` |
| `code_version` | str | git commit of the run |
| `notes` | str | why abandoned, what was looked at |

Example line (wrapped here for reading; one line in the file):

```text
{"test_id":"T-20261118-001","hypothesis_id":"H-001","created_at":"2026-11-18T12:00:00Z",
 "status":"pre-registered","supersedes":null,
 "hypothesis":"For .L, .DE, .PA listings, Europe FF5 explains more daily variance than Developed FF5",
 "test":"paired difference of adjusted R2 across tickers, one-sided, Wilcoxon signed-rank",
 "spec":{"datasets":[{"key":"europe_ff5_daily","stamp":"202609","sha256":"df7d8ed3..."}],"window":"full","fx_source":"ecb","rf_rule":"daily_file","frequency":"daily"},
 "split":{"role":"estimation","cutoff":"2015-12-31","seed":20261118},
 "family":"H-001","mde":null,"result":null,"code_version":"<commit>","notes":""}
```

## Appendix B. Power and minimum detectable effects

Formulas (two-sided level `a`, power 80%, normal approximation): `k = z(1 - a/2) + z(0.80)`.

- Alpha: `MDE(alpha_ann) = k * sigma_e_ann / sqrt(n / 252)`.
- Beta of factor `i`: `MDE(beta_i) = k * sigma_e_daily / (sd(f_i) * sqrt(n)) * sqrt(VIF_i)`.
- Both assume serially uncorrelated residuals. With autocorrelation the HAC standard error is larger (test-oracle DGP-B: about 1.29x), so these are lower bounds.
- `a = 0.05` for a single test; for a BH family of 5 the worst-case threshold is `0.05/5 = 0.01` (Bonferroni bound), used here for betas.

Computed (C10, `docs/datasets.md`) with factor sds and VIFs of the **last 2,520 rows** (about 10 years to 2026-09-30) of each file. Europe daily sd: Mkt-RF 1.035%, SMB 0.369%, HML 0.562%, RMW 0.301%, CMA 0.341%; VIF 1.36, 1.18, 2.75, 1.61, 2.40. US: 1.168, 0.703, 0.924, 0.589, 0.513%; VIF 1.15, 1.33, 1.82, 1.34, 1.56.

| Residual vol (annual) | n (years) | MDE alpha_ann (single 5%) | MDE betas, Europe FF5 (Mkt, SMB, HML, RMW, CMA), a = 0.01 | MDE betas, US FF5, a = 0.01 |
| --- | --- | --- | --- | --- |
| 20% | 504 (2) | 39.6% | 0.22, 0.56, 0.57, 0.81, 0.87 | 0.18, 0.31, 0.28, 0.38, 0.47 |
| 20% | 1,260 (5) | 25.1% | 0.14, 0.36, 0.36, 0.51, 0.55 | 0.11, 0.20, 0.18, 0.24, 0.29 |
| 20% | 2,520 (10) | 17.7% | 0.10, 0.25, 0.25, 0.36, 0.39 | 0.08, 0.14, 0.13, 0.17, 0.21 |
| 30% | 2,520 (10) | 26.6% | 0.14, 0.38, 0.38, 0.54, 0.58 | 0.12, 0.21, 0.19, 0.25, 0.31 |
| 40% | 2,520 (10) | 35.4% | 0.19, 0.50, 0.51, 0.72, 0.78 | 0.16, 0.28, 0.25, 0.34, 0.42 |

Reading: a single stock's alpha is almost never detectable (10 years at 20% residual vol needs about 18% a year). European style betas are about twice as hard to detect as US ones, because the European style factors are less volatile. Weekly data (D14) multiply every MDE by about `sqrt(5) = 2.2`.

## Appendix C. Replication targets

| ID | Target | Source | Status |
| --- | --- | --- | --- |
| RT1 | US monthly FF5 for September 2026: Mkt-RF -1.07, SMB -4.60, HML -1.55, RMW -3.22, CMA 1.08 (percent) | P1 front table "Fama/French 5 Research Factors (2x3)", column "September 2026" | V: equals row 202609 of `F-F_Research_Data_5_Factors_2x3_CSV.zip` exactly (C7). Automated as TD45. |
| RT2 | P1 front table, "Last 12 Months": Rm-Rf 10.91, SMB 1.54, HML 12.15, RMW -16.99, CMA 4.34 | P1 | V, with a trap: the page's multi-month long-short numbers are **differences of compounded leg returns**, not compounded factor returns. From the page's own 12-month portfolio returns: HML = (18.50 + 32.97)/2 - (16.78 + 10.39)/2 = 12.15; RMW = (11.32 + 13.29)/2 - (31.39 + 27.21)/2 = -16.99; CMA = (20.78 + 26.33)/2 - (25.38 + 13.05)/2 = 4.34; SMB = mean of SMB(B/M) -1.92, SMB(OP) 1.21, SMB(INV) 5.34 = 1.54. Compounding the monthly factors instead gives HML 9.73 and RMW -15.70; compounding the daily factors gives 9.49 and -15.25. Rm-Rf: compounded (Mkt-RF + RF) minus compounded RF = 10.89 from the monthly file, 10.90 from the daily file, vs 10.91 on the page (rounding). Any comparison with these page figures must use the leg method or Mkt-RF only. |
| RT3 | Daily file rebuilds monthly Mkt-RF: rms 0.021 / 0.030 / 0.017 points, max 0.180 / 0.185 / 0.065 (US / Europe / Developed) | Monthly files of the same release | V (C7). Automated as TD44 / D12 K8. |
| RT4 | Fama and French (2017), summary statistics of regional factor returns (average monthly returns and t-statistics) | JFE 123(3), 441-463 | U: tables not accessible (paywall; SSRN 403). The sample period of those tables is also unverified. Current-vintage values for July 1990 - December 2015 (306 months), monthly files, mean % (t): Europe Mkt-RF 0.47 (1.64), SMB 0.04 (0.35), HML 0.32 (2.31), RMW 0.42 (4.55), CMA 0.19 (1.80); Developed 0.43 (1.71), 0.10 (0.86), 0.32 (2.39), 0.36 (4.27), 0.26 (2.34) [V, C7]. The owner must supply the paper's table to close this. Expect differences (library revisions since 2016). |
| RT5 | Fama and French (2012), regional factor statistics | JFE 105(3), 457-472 | U, same reason. Current-vintage November 1990 - March 2011 (245 months): Europe 0.54 (1.72), 0.03 (0.17), 0.53 (3.38), 0.38 (3.67), 0.24 (1.93); Developed 0.44 (1.57), 0.19 (1.39), 0.47 (2.90), 0.35 (3.54), 0.29 (2.19) [V, C7; the period is chosen to match the paper's stated sample only if the owner confirms it, U]. |
| RT6 | Existing US smoke tests T109-T111 (SPY, AAPL, NVDA) | `docs/test-oracle.md` | Unchanged; regional equivalents need tickers chosen and registered before running (Appendix A). |

## Appendix D. Families added by the dataset work

| Family | Tests | m | Where |
| --- | --- | --- | --- |
| F1 (amended, proposed) | Full-sample betas incl. currency beta (D9.4) or momentum (D15) | 6 | M3, D16 |
| H-xxx | Any research comparison of datasets (regional vs Developed, ECB vs Yahoo FX, daily vs monthly-derived RF) | all registry lines with that id | this protocol |

The consistency checks K1-K10 (D12) and the audits are not hypothesis tests and are never corrected.
