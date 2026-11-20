# Sprint 3 validation on real data

Date: 2026-11-20. Branch `docs/s3-validation` (dev plus the currency engine plus hygiene).
Script: `scripts/validate_sprint3.py`. It builds every report in-process through `ReportService`
over `default_deps` (real Yahoo, Kenneth French, ECB and FRED data, no server) and changes no app
code. Last price date 2026-11-18; the French factor file ends 2026-09-30.

Run it from the repository root:

```
uv run python scripts/validate_sprint3.py --baseline <checkout of 688db25> --out numbers.json
```

## Summary

| # | Check | Result |
|---|---|---|
| 1 | SPY in EUR against SXR8.DE | FAIL on monthly correlation (0.972), PASS on return gap (+0.30%/yr) |
| 2 | 60/40 with IEF hedged in EUR | FAIL: the hedged IEF leg still carries the USD/EUR move |
| 3 | EUR cash index 2023 | PASS |
| 4 | Energy panel, USD view | PASS |
| 5 | Balanced SAA, USD and EUR | PASS |
| 6 | USD SPY report unchanged | PASS for every regression figure; one tail-risk figure differs |
| 7 | Tail risk by horizon, SPY | PASS |

## 1. SPY in EUR against SXR8.DE (EUR listing)

Both series are adjusted close (total return; SXR8 accumulates). SPY goes through the app's EUR
conversion (`ccy=EUR`); SXR8.DE is quoted in EUR and is not converted.

| Measure | Expected | Measured (2010-11-02 to 2026-11-18, 192 months) | Result |
|---|---|---|---|
| Monthly correlation | above 0.99 | 0.972 | FAIL |
| Annual return, SPY in EUR | | 15.68% | |
| Annual return, SXR8.DE | | 15.38% | |
| Return gap (SPY in EUR minus SXR8) | below about 0.5%/yr | +0.30%/yr | PASS |
| Tracking error of monthly returns | | 3.2%/yr | |

Diagnostics, same window: daily correlation 0.540; quarterly correlation 0.990; annual
correlation 0.9996; the R2 of daily SXR8 on SPY in EUR rises from 0.29 (same day) to 0.42 (same
day and previous day).

Data defect handled: the Yahoo history of SXR8.DE before 2010-11-01 is stale (84 zero-return days
in about 110) and ends in a one-day price reset of -24.6% on 2010-11-01. Including it gives a
monthly correlation of 0.849 and a gap of +1.59%/yr, which is the data and not the app. The
check starts on 2010-11-02 (`--sxr8-start`).

Interpretation: the level of the conversion is right (the gap of +0.30%/yr is about the 15%
withholding tax an Irish fund pays on US dividends plus the fee difference). The monthly
correlation misses 0.99 because the two prices are not struck at the same moment: SXR8 closes on
Xetra at 17:30 Frankfurt, SPY at the New York close, and the ECB rate is fixed at 14:10, so a
month-end can differ by about one day of US move. The noise is gone at quarterly horizon (0.990).
The wiki sentence "monthly figures are not affected" by the timing is too strong: the gap shows at
a month-end. Either state the check as quarterly, or accept 0.97 monthly.

## 2. 60/40 (IVV 60, IEF 40, monthly rebalance) in EUR, IEF hedged

Annualised returns are the Performance section's CAGR over the same analysed window
(2002-07-30 to 2026-09-30, 24.13 years). Trees are the composer presets built from the library.

| Portfolio | USD | EUR | EUR minus USD |
|---|---|---|---|
| 60/40 | 8.40% | 7.56% | -0.85%/yr |
| IEF alone (100%) | 3.37% | 2.26% (hedged) | -1.11%/yr |

Hedge check on the 100% IEF portfolio, on 6081 days with the same interval in both backtests:

| Measure | Expected | Measured | Result |
|---|---|---|---|
| Hedged leg minus IEF in USD, annualised mean | equals mean of (c_eur minus RF) | -0.67%/yr, against -0.48%/yr | FAIL |
| Daily correlation of the two gaps | near 1 | 0.025 | FAIL |
| Largest daily difference, engine against the formula `R_usd - RF + c_eur` | below 1e-6 | 0.0483 | FAIL |
| Largest daily difference, engine against the unhedged EUR return of IEF | | 0.0004 (equal to the RF minus c_eur shift) | |

Interpretation: the hedged EUR series is the unhedged EUR return of IEF with RF taken out and
c_eur put in, so the USD/EUR move stays in. In `api/portfolio_report.py`, `_common_returns`
applies `hedge()` to the returns of the prices that `ReportService` has already converted to EUR;
`hedge()` expects the dollar return. The effect is visible in the table: hedged IEF should earn
about its USD return plus the cash gap, 3.37% - 0.48% = 2.9%/yr, and it earns 2.26%. The hedge
needs the USD return of the leg (unconverted history) before it is swapped for cash. The same flaw
affects every line with `hedge_eur` in a portfolio, including the Balanced SAA bond lines.

## 3. EUR cash index, 2023

| Measure | Expected | Measured | Result |
|---|---|---|---|
| Compounded return of the euro cash index, 2022-12-30 to 2023-12-29 | about 3.3% | 3.28% (mean overnight rate 3.21%) | PASS |

Interpretation: EONIA spliced with euro STR from the ECB, accrued ACT/360 and compounded.

## 4. Energy panel, USD view (FF6, daily, long model: market, oil, gas)

| Subject | Oil beta (t) | Gas beta (t) | Carbon beta (t), from 2020-08 | Expected | Result |
|---|---|---|---|---|---|
| XLE | +0.211 (5.7) | +0.004 (1.2) | +0.078 (3.6) | clearly positive oil | PASS |
| SPY | +0.002 (1.8) | +0.001 (2.6) | +0.002 (0.7) | all close to 0 (under 0.05) | PASS |
| XLU | -0.009 (-1.4) | +0.004 (1.7) | -0.007 (-0.3) | report only | |

Interpretation: XLE is the only subject with a clear oil sensitivity, and its carbon beta is
positive and significant. XLU shows no reliable gas or carbon sensitivity at daily frequency
(none has t above 2), so the "XLU with gas and carbon sensitivity" expectation of the sprint note
is not met by the data; the gas leg is fat-tailed and the daily regression is weak. SPY's gas beta
is statistically nonzero (t 2.6) but 0.001 in size.

## 5. Balanced SAA preset, USD and EUR

Preset `saa` of `frontend/src/portfolio/presets.ts`, 13 lines, window 2007-04-12 to 2026-09-30
(4899 days) in both views.

| Measure | Expected | USD | EUR | Result |
|---|---|---|---|---|
| Rows (groups) | | 30 (16) | 31 (16) | |
| Largest group-minus-leaves difference (weights, contribution, risk share) | 0 | 0.0 | 0.0 | PASS |
| Holdings `total_return` against Performance cumulative return | equal | 287.83% = 287.83% | 342.96% = 342.96% | PASS |
| Top-level contributions minus total return | 0 | -8e-15 | 1e-14 | PASS |
| Sum of risk shares at depth 0 (with cash and cost) | 1 | 1.000000 | 1.000000 | PASS |

Interpretation: the table is arithmetically consistent in both currencies. The EUR view has one
more row than the USD view. This does not test whether the
hedged bond lines are right; see check 2.

## 6. USD ticker report unchanged against 688db25

Compared with a checkout of 688db25 (the dev commit before the sprint), same data cache and same
day, SPY, FF5 and FF6.

| Figure | FF5 | FF6 | Result |
|---|---|---|---|
| Alpha, annual | -0.5765% (identical) | -0.4901% (identical) | PASS |
| R2 | 0.96734 (identical) | 0.96743 (identical) | PASS |
| Betas and standard errors | identical to 1e-9 | identical to 1e-9 | PASS |
| Sections that differ | energy, tail_risk, generated_at | the same | expected |

Interpretation: the factor model is untouched. The differences are the new energy section, the
new tail-risk `by_horizon`, and one daily tail figure: the Cornish-Fisher CVaR 97.5% was an
indicative 8.71% at 688db25 and is now "n/a" with the reason "VaR is outside the valid range of
the expansion". That comes from the tail-risk rebuild on dev, not from the currency work.

## 7. Tail risk by horizon, SPY (FF6, 33.6 years)

| Horizon | Status | Periods | Expected | Result |
|---|---|---|---|---|
| Daily | ok | 8474 | present, ok | PASS |
| Monthly | ok | 403 | about 12 x 33.6 = 403 | PASS |
| Quarterly | ok | 134 | about 4 x 33.6 = 135 | PASS |

Interpretation: all three horizons exist. At quarterly horizon the historical VaR 99% is n/a
(1.3 expected tail observations); the CVaR and the 95% figures are present.

## Findings to act on

1. Hedged bond lines in the EUR view keep the currency move (check 2). This affects the headline
   of the EUR portfolio view, so it needs a fix and a test with a known answer before release.
2. The monthly correlation of 0.99 cannot be met against SXR8.DE because of the closing times
   (check 1). The wiki sentence on timing noise should say that month-ends carry about one day of
   noise.
3. The Yahoo history of SXR8.DE is bad before 2010-11-01; any later comparison against it must
   start after that date.
