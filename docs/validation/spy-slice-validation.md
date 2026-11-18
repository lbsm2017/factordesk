# SPY slice: independent validation

Date: 2026-11-18. Reviewer: independent quantitative review (did not write the code).
Scope: `backend/factordesk/analytics/{sample,regression,rolling,attribution}.py`, `pipeline.py`, `cli.py`,
`data/{factors,prices,audit}.py`, `report/{schema,render_html}.py`, the tests, and
`docs/samples/spy_report.{json,html}`. Binding specs: `docs/methodology.md` (M*), `docs/test-oracle.md` (T*),
`CODING_STANDARDS.md`, `docs/references.md`.

Every claim is marked **VERIFIED** (a computation I ran, or a quoted line) or **UNVERIFIED**.
Scripts and their outputs are in the session scratchpad
(`...\scratchpad\validation\scripts\*.py`, `...\scratchpad\validation\out\*.txt`); they are throwaway and not part
of the repo. No file under `backend/`, `pyproject.toml`, `uv.lock` or any existing doc was changed.

---

## 1. Verdict: ship with changes

The arithmetic is right. I rebuilt the SPY report from raw inputs that I downloaded myself (French zip, Yahoo
bars) with my own parser, my own alignment and plain statsmodels. Every headline number matches the JSON to
about 1e-7 (section 4). The return and risk identities hold to 1e-16. The HTML shows exactly the JSON values,
and it regenerates byte for byte from the JSON. Lint, types and all three test sets pass.

The SPY anomaly is real, and the author's explanation ("timing noise in early closing prices") points in the
right direction but is not proved. My root-cause analysis (section 3) finds the following.
Yahoo's SPY close before about 2009 carries a transient error that reverses the next day. That error is mostly
market movement after the 4:00 pm index close. It also appears in IVV, and it does not appear in the S&P 500
total-return index or in VFINX (a mutual fund priced at the 4:00 pm NAV). It explains the low R2, the -0.40
residual autocorrelation and the 4-5%/yr pre-2010 residual volatility. It does **not** create the negative
alpha: the S&P 500 total-return index has nearly the same FF5 alpha over the same dates (-0.53%/yr, z -2.79).

Conditions for shipping (each is detailed in section 2):

1. **Data-quality gate and residual diagnostics (F1, F2).** Implement M3.5 (Ljung-Box, Jarque-Bera,
   Durbin-Watson). Add a pre-specified gate on residual autocorrelation and residual-variance stability that
   adds a caveat and a 5-day robustness estimate to the report. Without it, a reader sees "audit: clean",
   "R2 0.9673" and "alpha reliable" with no hint that about 80% of the residual variance is transient
   price noise. If `e_t = u_t - u_{t-1} + w_t`, lag-1 autocorrelation -0.40 implies a noise share of
   `2 x 0.40 = 0.81`. The index residual (1.23%/yr vs SPY 3.35%/yr) gives `1 - (1.23/3.35)^2 = 0.87`.
2. **No crashes and no nonsense marked "ok" (F3, F4).** The degenerate inputs in section 5 currently escape
   as tracebacks (`LinAlgError`, `ValueError`, `ArithmeticError`). A constant-price ticker ships R2 = -1154.9
   with status `ok`.
3. **Silent duplicate-date drop (F5).** It must become a reported finding.
4. **Audit and parser follow the spec, or the spec documents the deviation (F6, F7).** Today they implement
   the plan's formula and thresholds, not M1.4 and M1.1, and the deviation is undocumented.
5. **Close the test gaps in section 6** (surviving mutants, missing T47, T22-T30, T54-T56).

Nothing found here would change a published SPY number by more than about 1e-7. The changes concern what a
close reader is told, and robustness on inputs that are not SPY.

---

## 2. Findings ranked by severity

### Critical

None. No look-ahead, unit error, window error or identity error was found in the slice.

| Check | How it was verified | Result |
| --- | --- | --- |
| Rolling windows | All 8,349 (126-day) and 8,223 (252-day) stamps compared with `RollingOLS` | Window lengths and stamp counts exact |
| Ex-ante beta | `rolling.py:142` read | Uses `shift(1)` |
| Rolling HAC | 25 random stamps per window compared with the statsmodels reference call | Agrees to 1e-14 on identical inputs (last 126-day stamp) |
| Full-sample statistics | Compared with statsmodels | Agree |
| Return identity | Independent recomputation | Holds to 1e-17 |
| Euler shares | Independent recomputation | Sum to 1 within 2e-16; `V = var(y)` within 2e-18 |
| BH correction | Compared with `multipletests` | Agrees |

### Major

**F1. The report cannot detect, and does not disclose, the SPY data problem. M3.5 is not implemented.**

- Evidence (VERIFIED):
  - The SPY residuals have lag-1 autocorrelation -0.404 (robust z -13.1) and a 5-day variance ratio of 0.30.
  - Pre-mid-2009 residual volatility is 4.58%/yr; after 2009-07-21 it is 1.35%/yr (single-break likelihood test).
  - The report shows "Data audit: Clean", "R² 0.9673", "Idiosyncratic 3.27% of variance" and
    "Alpha -0.58% … reliable", with no diagnostic. The schema has no Ljung-Box, Jarque-Bera or Durbin-Watson
    field, and there is no test T47.
  - The only place the problem is acknowledged is a docstring in `tests/test_pipeline.py:179-183`. That test
    also loosens the full-history R2 bound to 0.95 (`test_pipeline.py:206`). The oracle forbids loosening a
    bound silently ("raise it, do not loosen it silently").
- Location: `report/schema.py` (`Regression` has no diagnostics), `pipeline.py:145-193`, `pipeline.py:341-391`
  (`_warnings`).
- Fix:
  - Implement M3.5 and T47.
  - Add the gate in section 3.6 to `_warnings`, with its thresholds written into methodology M3.5 before
    calibration on a panel.
  - When the gate fires, add a caveat and a 5-day non-overlapping robustness row for alpha and the betas.
  - Write the test-file explanation into the methodology or the report, not a docstring.

**F2. "reliable" on the KPI alpha tile over-claims for this sample.**

- Evidence (VERIFIED, section 3.5):
  - The SPY alpha z is -2.24 daily, -2.77 on 2-day sums, -2.55 on 5-day sums and -2.14 on 10-day sums.
  - The point estimate ranges from -0.42% to -0.65%/yr across frequencies.
  - Before vs after 2010 it is -0.87% (z -1.85) vs -0.12% (z -0.57); neither subsample is significant on its
    own.
  - The index has the same sign and size, so the alpha mostly describes the S&P 500 relative to FF5 factors
    built from CRSP data, not SPY's management.
- The M3.2 rule is followed literally (p 0.025 < 0.05). However, the word "reliable" in the KPI strip
  (`render_html.py`, `_kpis`), shown without the in-sample caveat next to it, reads as a stronger claim than a
  borderline single test on a sample with a known data-quality problem. The tag is rendered at
  `render_html.py:881` and `:895`.
- Fix:
  - Keep the number. Show "significant at 5% (single test, in-sample)" instead of "reliable" for alpha.
  - When the gate (section 3.6) fires, add the caveat and the 5-day estimate.

**F3. Degenerate inputs crash the CLI with a traceback, or ship nonsense as `ok`.** Evidence in section 5
(VERIFIED).

- A zero-variance factor column raises an uncaught `LinAlgError: Singular matrix`.
- A constant non-zero factor column passes the full-sample fit with alpha_ann about -2.6e13, a CMA beta of
  1e14, z NaN and VIF 0.11 (below 1, which is impossible). It then crashes in the rolling stage with an
  uncaught `ArithmeticError`.
- A constant price with constant RF gives `R2 = -1154.88`, written to JSON and HTML with status `ok`.
- Location:
  - `analytics/regression.py:125-126` and `:213-218`: no rank or conditioning check before `solve`/`lstsq`.
  - `regression.py:138`: no `tss == 0` guard.
  - `cli.py:143-162`: catches only `InsufficientHistoryError`, `PriceDataError`, `FactorDataError`, network
    errors and `YFException`.
- Fix:
  - Check the design matrix rank (for example `np.linalg.matrix_rank(x)` or the smallest singular value of R
    relative to the largest) and the variance of `y`. Return `not_applicable` or `failed` with a reason.
  - Map any remaining `ValueError`, `ArithmeticError` or `LinAlgError` in `cli._cmd_report` to exit 1 with a
    one-line message.
  - Add oracle tests for the cases in section 5.

**F4. A recorded but unadjusted split, or a +900% bad tick, gives a full report dominated by one row.**

- Evidence (VERIFIED): with a 4:1 split recorded but not applied, the audit flags an error, but the report
  still shows R2 0.134 and alpha -13.6%/yr. A one-day x10 price glitch that reverts gives beta 1.97 and alpha
  +137.6%/yr with only an audit *warning*.
- This follows the spec (M1.4: "an audit with errors does not block the analysis"). However, the only signal
  is a banner. The headline tiles show the numbers as if they were usable.
- Fix:
  - When audit status is `errors`, grey out the KPI tiles and replace the alpha tag with "not interpretable
    (audit errors)".
  - Add an influence diagnostic: the share of SSR from the single largest row, or the change in alpha when the
    single most influential row is dropped. Report it next to the alpha. It must never be used to drop rows.

**F5. Duplicate dates are silently dropped at ingestion (keep last), so the audit never sees them.**

- Evidence (VERIFIED): a raw Yahoo frame with a repeated date is cut from 1502 to 1501 rows. The report then
  says audit "clean" and 0 exclusions. The A1 duplicate check in `audit.py:371-377` cannot fire, because
  `normalize_frame` already removed the duplicate. The only trace is a `logger.warning`.
- The same input injected through a provider raises an uncaught `ValueError`.
- Location: `data/prices.py:154-156`; `analytics/sample.py:129-130`; `cli.py:143-162`.
- Violates CODING_STANDARDS section 3 ("no silent row dropping") and M1.4 A1.
- Fix: keep the first bar or refuse, but always record a finding `duplicate_index` (error) with the dates, and
  carry it into `DataInfo.audit_findings`.

**F6. The audit implements the plan's formula, not M1.4.**

- Evidence (VERIFIED, `data/audit.py:22-43, 83-106, 127-192`):
  - It compares Adj Close returns with `(C_t + D_t)/C_{t-1} - 1` at a fixed 5 bp tolerance and severity
    `warn`. M1.4 A6 requires the CRSP convention `C_t/(C_{t-1} - D_t)` with `tau_t = 1e-4 + 0.01/C_{t-1}` and
    severity `error`. D9 explains why the plan's formula is wrong.
  - Missing or different checks: A5b (unrecorded split), A7 (non-event days per `tau_t`), A8 (calendar-year
    drift rule), A2 (gap rule in calendar days).
  - Consequence for SPY: the report says "max |diff| on a dividend date 2.52 bps". With the CRSP convention
    the true maximum discrepancy is **0.009 bp**, and all 136 events pass (section 3.4g). The reported figure
    is an artefact of the formula.
  - An unrecorded 4:1 split yields only a generic `large_return` warning (section 5).
- Fix: implement M1.4 as written and port T22-T30, or record the deviation as a new D-entry in M16.

**F7. The French parser is looser than M1.1.**

- Evidence (VERIFIED, `data/factors.py`):
  - The header is checked as a set, so reordered columns are accepted (`:124`).
  - Unsorted dates are sorted with a warning instead of raising (`:162-164`).
  - Bounds only *warn* above |1.0| (`:173-178`), instead of raising above |0.5| or for RF outside
    [-0.0001, 0.002].
  - There is no "second data block" check (a second block would be concatenated).
  - Empty cells silently become NaN outside the sentinel list (`:150`).
  - The revision tolerance is 1e-12 instead of 5e-5 (`:45`). Rounding-only changes would be logged as
    revisions.
  - `parse_french_csv` reads the wall clock (`:170`), so it is not the pure function M1.1 asks for.
  - `meta.json` lacks `last_attempt_at`, `last_attempt_ok` and `http_last_modified` (M1.1 item 11).
- None of these affected the SPY numbers: my independent parser gives a frame identical to the cache, max abs
  difference 0.0 over 15,918 rows (VERIFIED).
- Fix: implement M1.1 items 3-10 and tests T02, T06, T07, T10, T11.

### Minor

- **F8. Yahoo Adj Close is not reproducible across downloads.**
  - Two same-day downloads differ by up to 1.8e-4 in Adj Close and 1.9e-6 in daily returns (Close and
    Dividends identical) on 7,108 of 8,509 rows (VERIFIED). This moves betas by about 1e-7.
  - Fix: record the sha256 of the price frame in `DataInfo` so a report can be tied to its input. Consider
    deriving total returns from Close + Dividends with the CRSP formula, which is exactly reproducible.
- **F9. "Today's bar" is dropped only when it equals today (`data/prices.py:161`).** M1.3 says drop any date
  on or after today. A bar dated tomorrow in exchange time, from clock skew or a vendor bug, would survive.
- **F10. No requested-date control.** `build_sample` accepts `requested_start/end`, but `pipeline.py:414` and
  the CLI never pass them. The "cleaner sample" analysis in section 3 cannot be produced from the product.
  Fix: add `--start/--end`, and keep "requested vs actual" in the report.
- **F11. The HTML thins rolling series by stride (`render_html.py:278-287, 808, 825`).** About 17-row strides
  can hide extremes, such as one-day spikes of the 126-day beta. Use min-max-preserving decimation per pixel
  column.
- **F12. JSON is 6.40 MB** (`schema.py:413`, `indent=2`; the rolling block is 4.04 MB). Measured reductions
  (VERIFIED):

  | Step | Size |
  | --- | --- |
  | Compact separators | 4.11 MB |
  | Plus one shared date axis instead of per-window `dates` and `window_start` (`window_start[i] = dates[i-W+1]` is derivable) | 3.78 MB |
  | Plus rolling series at 6 significant digits | 1.96 MB |
  | Plus no warm-up nulls | 1.94 MB |

  Six significant digits on a beta is about 1e-6 relative. That is far below the standard error (about 0.01)
  and comparable to the Yahoo Adj Close revision noise in F8, so nothing a reader can see or test is lost.
  The HTML uses at most 500 points per series and the last value; the full series stays available to API
  consumers. Gzip on the wire would cut it further (not measured).
- **F13. M1.5 currency check not implemented.** It is disclosed in the US-factors note ("this version does not
  check the ticker's currency"). That is acceptable for SPY, but it is a spec deviation without a D-entry.
- **F14. The "Before factor data" count and `n_excluded` are correct**, but the `all-NaN` and "no overlap"
  cases both report "0 daily returns line up with the factor data". A clearer reason (all prices missing vs
  no date overlap) would help.
- **F15. Beta reading text** ("A 1-point move in Mkt-RF …"): "point" is ambiguous. Use "a 1 percentage-point
  move in the Mkt-RF return".
- **F16. A5 split check uses a ratio tolerance** (`SPLIT_RATIO_TOL = 0.10`), not the log rule in M1.4.

---

## 3. The anomaly: root cause

Facts in the author's summary that I reproduced (VERIFIED):

| Quantity | Value |
| --- | --- |
| R2 | 0.9673 |
| Alpha | -0.58%/yr (z -2.24) |
| Residual lag-1 autocorrelation | -0.404 |
| Residual volatility, pre-2010 | 2.3-8.4%/yr by year |
| Residual volatility, post-2010 | 0.9-2.6%/yr by year |
| From 2010-01-04 | R2 0.9950, alpha -0.12%/yr (z -0.57) |

Script outputs: `out/anomaly1.txt` to `anomaly5.txt`, `gate.txt`.

### 3.1 Where and when (VERIFIED)

FF5 residuals of SPY (Adj Close), full-sample fit, by year (selected rows):

| Year | Residual vol %/yr | Lag-1 autocorrelation | Within-year R2 |
| --- | --- | --- | --- |
| 1996 | 3.70 | -0.43 | 0.932 |
| 2000 | 8.37 | -0.34 | 0.884 |
| 2004 | 2.73 | -0.53 | 0.942 |
| 2008 | 7.24 | -0.36 | 0.971 |
| 2009 | 2.58 | -0.48 | 0.991 |
| 2010 | 1.25 | -0.31 | 0.996 |
| 2015 | 0.99 | -0.26 | 0.997 |
| 2022 | 1.42 | +0.08 | 0.997 |

A single variance break (Gaussian likelihood) is placed at **2009-07-21**: 4.58%/yr before, 1.35%/yr after.
Relative to index variance, the transient-noise share (defined in 3.2) is 1-4% of daily index variance per
quarter through 2008Q3. It falls to 0.1-0.6% from 2009Q1, with one more spike in 2009Q3 (July 2009: 4.1%), and
stays near 0.1-0.3% from 2009Q4. In IVV the drop comes earlier (about 2008Q2). The break is therefore late 2008
to 2009, not a calendar-year boundary.

### 3.2 The noise is a transient price error: it reverses the next day (VERIFIED)

Let the tracking difference be `d_t = r_SPY,t - r_SP500TR,t`, using Yahoo `^SP500TR` (the S&P 500 total-return
index, 4:00 pm close). For SPY, `d_t` has lag-1 autocorrelation of -0.4 to -0.58 in every year 1993-2026. That
is the signature of `d_t = u_t - u_{t-1}` with a transient error `u`.

Daily standard deviation of `d_t`:

| Fund | 1993-2009 (bp/day) | 2010-2026 (bp/day) |
| --- | --- | --- |
| SPY | 14-53 | 3-13 |
| IVV (from 2000) | about the same as SPY, year by year (for example 2003: 20.5 vs 20.1) | about the same as SPY |
| VFINX (4 pm NAV) | 0.4-2.4 in most years | 0.4-2.4 in most years |

### 3.3 Timing, not random price noise (VERIFIED)

Suppose the ETF close is recorded *after* the 4:00 pm index close. Then `u_t` is the market move between 4:00 pm
and the ETF's recorded close. That move belongs to the *next* day's index return, so
`cov(d_t, TR_{t+1}) = var(u) = -cov(d_t, d_{t-1})`. Pure bid-ask or random price errors would give
`cov(d_t, TR_{t+1}) = 0`.

Ratio `cov(d_t, TR_{t+1}) / var(u)`, with block-bootstrap 95% intervals (20-day blocks, 400 draws):

| Series, period | Ratio | 95% interval | Reading |
| --- | --- | --- | --- |
| SPY 1993..2009-06 | **0.77** | [0.42, 1.12] | Most of the noise is post-4 pm market movement |
| IVV 2000..2009-06 | **1.06** | [0.27, 2.03] | Same |
| SPY 2009-07..2026 | 3.94 | [0.94, 7.43] | Noise is about 15x smaller; ratio imprecise |
| VFINX, both periods | about 1 | wide intervals | Noise is negligible (var(u) 5-7 bp²) |

Other evidence for timing:

- **Regressions on factor leads.** On the French factors, SPY_t loads on the *next* day's Mkt-RF with
  coefficient +0.015 (z 2.8) in 1993-2009, and +0.004 (z 1.3) in 2010-2026. The same-day coefficient is about
  1 every year, so no block of dates is shifted. On `^SP500TR`, the lead coefficient is +0.019 (z 3.7) before
  mid-2009. The model predicts a lead coefficient of `var(u)/var(TR)`, about 0.022.
- **Adding market terms does not change the residual autocorrelation.** With Mkt-RF at t-1 and t+1 added, it
  stays at -0.419 (vs -0.418). This is expected: the post-close piece is only about 2% of the next day's
  variance, so a lead regressor cannot absorb it.
- **Aggregation.** Over non-overlapping k-day sums the transient error telescopes. SPY's R2 in 1993..2009-06
  rises from 0.948 (k = 1) to 0.969, 0.982 and 0.986 (k = 2, 5, 10). The index stays flat at 0.995. Over
  2009-07..2026, SPY rises only from 0.9945 to 0.997.
- **Noise scales with volatility.** `corr(|e_t|, |Mkt_t|)` is 0.32 before the break and 0.25 after. Days with
  |Mkt| above 2.5x trailing volatility carry 4.1x the average squared residual. The top 15 residual days
  before 2009 are mostly high-volatility days (6 in 2008 Q3-Q4, 6 in 2000-2001). In 12 of the 15, the next
  day's residual has the opposite sign.

### 3.4 Causes tested and rejected (VERIFIED)

- **(b) Specific dates.** Squared residual share relative to day share: ex-dividend days ratio 0.92, quarter
  ends 1.26, triple-witching Fridays 0.90. These are about the same before and after the break, so they cannot
  explain it. Month ends show 1.35 before and 1.24 after: mild, but the same in both periods.
- **(c) Other series.** Over the identical 8,474 dates, FF5 fits of `^SP500TR` and VFINX give R2 0.9955 and
  0.9948, residual autocorrelation -0.06 and -0.11, and residual volatility 0.6-1.7%/yr pre-2009. The French
  factors and the S&P-vs-CRSP universe difference therefore explain at most about 0.5% of variance, not 3.3%.
  IVV reproduces SPY's problem, so it is not SPY-specific (no SPY dividend or split bug). VOO, from 2010,
  looks like post-2009 SPY.
- **(e) Calendar alignment.** SPY and French dates match exactly from 1993 (no date in one and not the other).
  The same-day market coefficient is 0.95-1.10 every year, and `corr(TR_t, Mkt_t)` is 0.966-0.998 every year.
  No shifted block.
- **(f) French file.** The fresh download is identical to the repo cache (max abs difference 0.0). Exact zeros
  and repeats in Mkt-RF are 1-11 per 5-year block, with no clustering.
  - Separate effect: Mkt-RF has positive lag-1 autocorrelation in 1993-1996 (0.08-0.18), which is CRSP
    small-cap non-synchronous trading. This makes the *daily* market beta of large-cap series depend on
    frequency (index beta 1.012 daily vs 1.000 on 10-day sums). It moves alpha by about 0.1-0.2%/yr. It is not
    the anomaly, but it matters for alpha (3.5).
- **(g) Dividend scaling.** All 136 SPY events match Yahoo's CRSP convention to at most 0.009 bp, against a
  tolerance of 1.7-2.3 bp. There are 0 A7 violations on non-event days (max 0.014 bp). The mean residual on
  ex-dates is -3.3 bp and +5.3 bp the day after (sd 20 bp). That is small: about 8 bp/yr net, far below the
  anomaly.
- **Yahoo Adj Close precision (F8).** At most 1.9e-6 per day. Negligible.

### 3.5 Does the anomaly bias the headline alpha? Mostly no (VERIFIED)

Daily FF5 alpha with HAC per M0.5:

| Series | 1993-2026 | 1993-2009 | 2010-2026 |
| --- | --- | --- | --- |
| SPY | -0.58% (z -2.24) | -0.87% (z -1.85) | -0.12% (z -0.57) |
| ^SP500TR (index) | -0.53% (z -2.79) | -0.99% (z -3.23) | -0.12% (z -0.58) |
| VFINX | -0.64% (z -3.35) | -1.06% (z -3.44) | -0.26% (z -1.30) |
| IVV (from 2000-05-22) | -0.55% (z -2.32) | -1.43% (z -2.40) | -0.17% (z -0.78) |

What this table shows:

- The negative alpha belongs to the S&P 500 index against FF5 factors built from CRSP data, concentrated
  before 2010. The timing noise telescopes, so it cannot move a sample mean by more than
  `(u_T - u_1)/T` (negligible over 33 years). It *lowers* SPY's z (HAC SE 0.258%/yr vs about 0.19%/yr for the
  index) rather than creating the alpha.
- HAC does the right thing here. The non-robust alpha z is -1.00 vs the HAC z of -2.24. The MA(1) noise has
  zero long-run variance, and the Bartlett weights remove most of it (`w_1 = 0.909` at L = 10).
- The small-sample correction is immaterial: `use_correction=True` gives z -2.236.
- Frequency sensitivity: SPY alpha is -0.65 / -0.56 / -0.42%/yr on 2- / 5- / 10-day sums. The index gives
  -0.45 / -0.36 / -0.32. Most of this comes from the frequency-dependent market beta in 3.4f.

### 3.6 Ranked candidate causes and recommendation

| Rank | Cause | Evidence for | Evidence against | Confidence |
| --- | --- | --- | --- | --- |
| 1 | **Non-synchronous ETF close.** Before about 2009 the Yahoo SPY/IVV close contains market movement after the 4:00 pm index close, which reverses in the next day's relative return. | Lead covariance ratio 0.77 [0.42, 1.12]; IVV identical; index and 4 pm-NAV fund clean; aggregation restores R2; noise scales with volatility | Exact institutional mechanism and date not confirmed | **High (about 85%)** that this is the main source of the excess residual variance and the -0.4 autocorrelation |
| 2 | ETF premium/discount and closing-auction noise (all years, small) | Post-2009 SPY, IVV and VOO keep `d_t` sd 3-13 bp with autocorrelation about -0.5; residual autocorrelation -0.2 to -0.3 | Too small to explain pre-2009 | High that it explains the *post*-2009 negative autocorrelation |
| 3 | Bid-ask bounce or fractional ticks (pre-2001) | Could account for the part of var(u) not explained by the lead (ratio CI lower end 0.42) | Noise persists at the same level 2001-2008, after decimalisation | Low-moderate as a minor contributor |
| 4 | Dividend mis-scaling in Adj Close | - | 136/136 events exact | Rejected |
| 5 | Date misalignment | - | Calendars identical; same-day beta about 1 every year | Rejected |
| 6 | Stale or revised French values | - | Index and VFINX fit at 0.995; no stale clusters | Rejected (for the anomaly) |

Exact institutional mechanism (**UNVERIFIED**): a 2007 practitioner post describes SPY as having "an informal
4:00 closing price … then a formal closing rotation at 4:15" (dailyspeculations.com, 2007-04-30). A
mechanism like this, with the 4:15 pm closing print used as Yahoo's historical close, would produce exactly
this signature. I could not confirm the date on which this ended for SPY or IVV, or Yahoo's choice of print. A
2010 news item describes an NYSE Arca closing auction for SPY at 4:15 pm (investmentnews.com), which does not
fit a 2009 break. Treat the mechanism as a hypothesis. The statistical conclusion (post-4 pm information in
the close, transient, common to AMEX-era ETFs) does not depend on it.

**Should the headline SPY alpha be shown?** Show it, **with a caveat**. Do not silently compute it on a
"cleaner sample" chosen after seeing the result: picking 2010 because the residuals look better is a
forking-paths choice, and the 2010-2026 alpha is a different estimand (a different market regime, as the index
itself shows).

Make it principled with a gate that is pre-specified, written into methodology M3.5 before use, and applied to
every ticker:

- **G1, non-synchronous prices.** Fires when residual lag-1 autocorrelation is below -0.2 with a
  heteroskedasticity-robust z below -4. Effects:
  - Caveat: "Daily price changes partly reverse the next day (lag-1 autocorrelation {rho}). Closes are not
    synchronous with the factor data, so R², residual volatility and the idiosyncratic share overstate
    stock-specific risk. Betas and alpha are also shown from 5-day returns."
  - A pre-specified robustness row: the same regression on non-overlapping 5-day sums, with HAC per M0.5.
  - The alpha tag says "significant" only if the daily and 5-day estimates both reject at 5%.
  - Observed values: SPY full sample -0.40 (z -13.1) fires. `^SP500TR` -0.06 does not. VFINX -0.11 does not.
    SPY from 2009-07 -0.28 (z -4.5) fires, which is appropriate: ETF closing-auction noise is still about
    half of SPY's small residual variance there.
- **G2, residual variance stability.** Fires when, after normalising by market variance, the largest and
  smallest calendar-year residual variances differ by more than 10x and a single-break likelihood-ratio test
  has p < 0.01. Effect: report the detected break date and the alpha on each side, as information. The
  headline stays the full-sample number.
- Both thresholds must be calibrated on a panel of tickers (ETFs, large and small stocks, ADRs) before release
  so that their false-alarm rates are known. **UNVERIFIED**: I calibrated them only on the five S&P 500
  products above.

---

## 4. Independent recomputation (VERIFIED)

### Inputs and method

- French US daily 5-factor zip downloaded 2026-11-18, `Last-Modified: Tue, 27 Oct 2026 15:18:47 GMT`. Parsed
  in memory by my own parser (latin-1, header check, contiguous block, /100).
- SPY from yfinance 1.8.0, `Ticker.history(period="max", interval="1d", auto_adjust=False, actions=True,
  repair=False)`. Dates taken in America/New_York; bars dated 2026-11-18 or later dropped.
- Return `r_t = AdjClose_t / AdjClose_{t-1} - 1`. Kept rows are those whose interval `(d_{t-1}, d_t]` holds
  exactly one French date, equal to `d_t`. Excess return `r_t - RF_t`.
- Regression: `sm.OLS(y, sm.add_constant(F, has_constant="add")).fit(cov_type="HAC",
  cov_kwds={"maxlags": 10, "use_correction": False}, use_t=False)` (statsmodels 0.15.0).
- Rolling: `RollingOLS(window=W)` for all stamps, plus the HAC reference call with `maxlags=4` on the last
  stamp and 25 random stamps.

### Comparison with `docs/samples/spy_report.json`

| Quantity | Independent | Report JSON | Abs diff |
| --- | --- | --- | --- |
| n | 8474 | 8474 | 0 |
| start / end | 1993-02-01 / 2026-09-30 | 1993-02-01 / 2026-09-30 | - |
| HAC lags | 10 | 10 | 0 |
| alpha_ann | -0.0057648871 | -0.0057648908 | 3.7e-09 |
| alpha se_ann | 0.0025773514 | 0.0025773505 | 8.8e-10 |
| alpha z / p | -2.236749 / 0.025303 | -2.236751 / 0.025303 | 2.2e-06 / 1.4e-07 |
| beta Mkt-RF (z) | 1.00930706 (151.819) | 1.00930696 (151.820) | 1.0e-07 (1.0e-03) |
| beta SMB (z) | -0.14757277 (-23.9252) | -0.14757276 (-23.9253) | 1.6e-08 (1.5e-04) |
| beta HML (z) | 0.00711211 (0.81478) | 0.00711167 (0.81473) | 4.5e-07 (4.3e-05) |
| beta RMW (z) | 0.08776226 (9.37188) | 0.08776210 (9.37192) | 1.6e-07 (3.4e-05) |
| beta CMA (z) | 0.06074118 (5.42117) | 0.06074140 (5.42123) | 2.2e-07 (5.2e-05) |
| HAC se, all betas | - | - | at most 8.7e-08 |
| R2 / adj R2 | 0.96733827 / 0.96731899 | 0.96733855 / 0.96731927 | 2.8e-07 |
| sigma_e_ann | 0.03348802 | 0.03348787 | 1.5e-07 |
| contribution Mkt-RF | 0.0973619948 | 0.0973619848 | 9.9e-09 |
| contribution SMB | -0.0006310695 | -0.0006310695 | 6.7e-11 |
| contribution HML | 0.0001525128 | 0.0001525032 | 9.6e-09 |
| contribution RMW | 0.0029807396 | 0.0029807341 | 5.5e-09 |
| contribution CMA | 0.0013336079 | 0.0013336128 | 4.9e-09 |
| total (252 x mean y) | 0.0954328985 | 0.0954328747 | 2.4e-08 |
| risk share Mkt-RF | 0.98398939 | 0.98398967 | 2.8e-07 |
| risk share SMB / HML | 0.00083985 / -0.00021073 | 0.00083986 / -0.00021071 | 1.9e-09 / 1.2e-08 |
| risk share RMW / CMA | -0.01076715 / -0.00651309 | -0.01076714 / -0.00651312 | 1.2e-08 / 2.8e-08 |
| idiosyncratic share | 0.03266173 | 0.03266145 | 2.8e-07 |
| total vol ann | 0.18529764 | 0.18529759 | 4.5e-08 |
| `V` vs `var(y)` (identity) | 1.3625085e-4 | 1.3625085e-4 | 1.8e-18 |
| last 126-day betas (all 5) and HAC se | - | - | at most 1.4e-14 |
| last 252-day betas (Mkt, SMB, HML, RMW, CMA) | 0.989938, -0.102140, 0.026464, 0.010865, -0.006104 | 0.989937, -0.102140, 0.026463, 0.010865, -0.006103 | at most 8.4e-07 |
| all rolling stamps, beta vs `RollingOLS` | 8,349 / 8,223 stamps, same NaN pattern | - | at most 7.4e-05 (126), 4.2e-05 (252) |
| rolling HAC se, 25 random stamps per window | - | - | at most 2.7e-04 relative |

### Why the differences are not exactly zero (VERIFIED)

My Yahoo download and the repo's cached download from the same morning have identical `Close` and `Dividends`.
`Adj Close`, however, differs on 7,108 rows (up to 1.8e-4 price units, 1.9e-6 in daily returns), on dates up to
2026-03-18 (F8). The last 126 rows are identical, and there the agreement is 1e-14 to 1e-16. The code is
therefore exact, and the residual differences come from the price vendor.

---

## 5. Edge cases (VERIFIED)

Run through `factordesk.cli.main([...], price_provider=…, factors=…, now=…)` with synthetic data (1,500 business
days, injected providers; scratchpad `scripts/edge.py`).

| Case | Outcome | Assessment |
| --- | --- | --- |
| 300 rows (below 504) | exit 1: "TEST has 300 daily returns that line up with the factor data; at least 504 (about two years) are required" | Clear, correct |
| Split 4:1 recorded, Close and Adj not adjusted | exit 0; audit `errors` (`suspected_missing_split_adjustment`); report R2 0.134, alpha -13.6%/yr | Flagged, but headline tiles still shown (F4) |
| Same split, not recorded | exit 0; only `large_return` warning; R2 0.122 | Misleading: no A5b check (F6) |
| Constant price, constant RF | exit 0; **R2 = -1154.88**, status ok | Wrong (F3) |
| Constant price, varying RF | exit 0; R2 0.004, beta 0 | Correct arithmetic, no warning that the series is flat (stale run reported only as `info`) |
| 5 NaN prices mid-series | exit 0; 6 rows excluded `price_missing`, audit `errors` (`nan_price`) | Correct |
| Zero-variance factor column | **Uncaught `LinAlgError: Singular matrix`** | Crash (F3) |
| Constant non-zero factor column | **Uncaught `ArithmeticError`**; the full-sample fit before it has alpha -2.6e13, VIF 0.11 | Crash, and garbage upstream (F3) |
| Duplicate date via injected provider | **Uncaught `ValueError`** ("index must be unique") | Crash (F5) |
| Duplicate date via `normalize_frame` | 1502 rows become 1501, last bar kept, audit clean, 0 exclusions | Silent drop (F5) |
| Prices 40 days past factor file | exit 0; tail reported as memo; n unchanged | Correct |
| All-NaN, injected | exit 1: "has 0 daily returns that line up…" | Correct exit, imprecise reason (F14) |
| All-NaN via `normalize_frame` | `PriceDataError: … empty or all-NaN` | Clear |
| x10 one-day glitch (reverting) | exit 0; warning only; beta 1.97, alpha +137.6%/yr | Per spec, but misleading headline (F4) |
| x10 permanent jump | exit 0; warning only; alpha +159.8%/yr | Same |
| Zero price on one day | exit 0; 2 rows `price_missing`; audit `errors` | Correct |
| `--out` with spaces and non-ASCII (`dir with spaces\résumé ü 数据`) | exit 0; HTML and JSON written | Correct |
| NaN factor cells | exit 0; 3 rows `factor_missing` | Correct |
| No date overlap with factors | exit 1, "0 daily returns line up" | Correct exit, imprecise reason |
| Perfect fit (stock = market) | exit 0; R2 1.0000, alpha 0 | Correct |

---

## 6. Test-suite quality

### Baseline (VERIFIED)

| Command | Result |
| --- | --- |
| `uv run ruff check .` | All checks passed |
| `uv run pyright` | 0 errors, 0 warnings |
| `uv run pytest -q` | 187 passed, 204 deselected (72.8 s) |
| `uv run pytest -q -m slow` | 201 passed, 190 deselected (163 s) |
| `uv run pytest -q -m live` | 3 passed (network) |

### Mutation results (VERIFIED)

Each mutant is applied to a copy of `backend/` in the scratchpad and run with the default suite
(`pytest -x`, `PYTHONPATH` set to the copy; the import was checked to resolve to the copy). Survivors are re-run
with `-m slow`.

| # | Mutation (file) | Result | First failing test |
| --- | --- | --- | --- |
| M1 | HAC lag rule `+1` (`regression.py:63`) | caught | `test_build_report_end_to_end`; targeted run also fails T38, T39, T50 |
| M2 | Ex-ante beta without the `shift(1)` lag (`rolling.py:142`) | caught | T51 |
| M3 | RF not subtracted (`sample.py:236`) | caught | T97 |
| M4 | Annualisation 365 instead of 252 (`regression.py:33`) | caught | T53 |
| M5 | Off-by-one window, W+1 rows (`rolling.py:120`) | caught | `test_report_writes_html_and_json`; targeted run fails T48 (both W), T49, T50, T52 |
| M6 | Idiosyncratic variance SSR/(n-6) instead of SSR/(n-1) (`attribution.py:149`) | caught | T58 |
| M7 | HAC small-sample correction `m/(m-k)` added (`regression.py:130`) | caught | T38 |
| M8 | BH replaced by Bonferroni (`regression.py:162`) | caught | T43 |
| M9 | Multi-day returns not excluded (`sample.py:195`) | caught | T31 |
| M10 | Bartlett weights `l/(L+2)` (`regression.py:68`) | caught | T38 |
| S1 | Risk disagreement sentence gap `>= 3` instead of `>= 2` (`attribution.py:219`) | **survived** | T62 tests gaps 1 and 3 only, never the boundary 2 |
| S2 | Audit dividend tolerance x10, 5 bp to 50 bp (`audit.py:25`) | **survived** | Audit tests set inputs relative to `audit.DIV_EVENT_TOL` (`test_audit.py:91-99`), so a wrong constant cannot fail them. T24's 0.50-vs-0.05 dividend (about 45 bp) would also pass under the mutant. |
| S3 | Condition number without `sqrt` (`regression.py:225`) | **survived** | T45 checks kappa only for orthogonal factors, where `kappa = kappa^2 = 1` |
| S4 | Large-insignificant-alpha sentence uses `<=` (`regression.py:187`) | **survived** | T44 has no case at `abs(alpha) = 0.03` or `p = 0.05` |
| S5 | Duplicate dates keep first instead of last (`prices.py:156`) | caught | `test_duplicate_dates_are_collapsed`, a test that *asserts* the silent drop of F5 |
| S6 | High-correlation pair threshold 0.6 to 0.7 (`regression.py:247`) | **survived** | T46 only checks a pair at about 0.95 correlation; no case between 0.6 and 0.7 |
| S7 | Today's bar never dropped (`prices.py:161`) | caught | `test_fetch_normalizes_frame` |

Totals: 12 of 17 mutants caught, 5 survived (S1, S2, S3, S4, S6).

The five requested mutation classes (HAC lags, the point-in-time lag, RF subtraction, annualisation, window
off-by-one) are all caught, and each by a targeted oracle test. The surviving mutants share one pattern:
thresholds and boundaries are tested only far from the boundary, or relative to the constant under test.
Fix: add boundary cases (T44 at exactly 0.03 and 0.05; T62 with a gap of exactly 2; kappa on a known 2x2
correlation, where `kappa = sqrt((1+r)/(1-r))`), and pin audit tolerances to literal numbers taken from M1.4.

### Oracle tests with no implementation in the suite

- T47: residual diagnostics, which do not exist in the code.
- T22-T30: audit tests per M1.4.
- T01-T13: partly covered by `test_factors.py`, which has no T-ids, but T02 column order, T06, T07 ordering,
  T10 and T11 cannot pass against the current parser (F7).
- T54-T56 (per-year attribution, tilt/timing) and T63+: modules outside this slice; M6.2 and M6.3 are not
  implemented.

---

## 7. What remains UNVERIFIED

- The institutional mechanism and exact date of the 2008-2009 break: the 4:15 pm closing rotation, any listing
  transfer of SPY or IVV, or Yahoo's choice of closing print. Section 3 establishes the statistical signature,
  not the market-structure history.
- The calibration of the proposed gate thresholds outside the five S&P 500 products examined.
- Whether `^SP500TR` on Yahoo is itself free of revisions. I used it only as a 4:00 pm reference, and VFINX
  independently corroborates it.
- Browser rendering of the HTML (dark/light, phone width). I checked text and numbers, not visuals. The PNG
  screenshots in `docs/samples/` were not reviewed.
- The API layer (`api/`, T108): out of scope and empty.
- Gzip size of the reduced JSON.
- `backend/factordesk/report/render_html.py` and `docs/samples/spy_report.html` were last modified at
  2026-11-18 11:41, around the start of this review and not by it. All HTML checks and line numbers here refer
  to that version; the HTML regenerated byte for byte from the JSON at the time of checking.
