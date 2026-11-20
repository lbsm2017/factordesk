# Sprint 4 validation on real data: the Europe factor set

Date: 2026-11-20. Branch `docs/sprint-4-validation`, on `feat/factor-set-engine` (a65f080, under
review, not merged). Script: `scripts/validate_sprint4.py`. It builds every report in-process
through `ReportService` over `default_deps` (real Yahoo, Kenneth French, ECB and FRED data, no
server) and changes no app code. Last price date 2026-11-19. Baseline for check 3: `origin/dev`
at 8d70ed5, exported with `git archive origin/dev backend` and run with the same Python and the
same data cache.

Run it from the repository root:

```
uv run python scripts/validate_sprint4.py --baseline <export of origin/dev> --out numbers.json
```

## Data vintage

All files were downloaded on 2026-11-20 (the run date). Every file ends 2026-09-30.

| File set | Source file | Last-Modified | Stamp | Rows |
|---|---|---|---|---|
| US daily | five factors (own loader, no stamp) and `mom_daily` | Mom: 27 Oct 2026 | Mom: 202609 CRSP | 15,918 from 1963-07-01 |
| US monthly | `ff5_monthly`, `mom_monthly` | 27 Oct 2026 | 202609 CRSP | 759 from 1963-07 |
| Europe daily | `Europe_5_Factors_Daily`, `Europe_Mom_Factor_Daily` | 26 Oct 2026 20:51 GMT | 202609 Bloomberg | 9,458 from 1990-07-02 |
| Europe monthly | `Europe_5_Factors`, `Europe_Mom_Factor` | 26 Oct 2026 20:50 GMT | 202609 Bloomberg | 435 from 1990-07 |

SHA-256 of each file is in the script output (`vintages`). The Europe and US files carry the same
release month (202609).

## Summary

| # | Check | Result |
|---|---|---|
| 1 | VGK and EXSA.DE in EUR: Europe set R2 above US set R2 | FAIL for VGK (daily), PASS for EXSA.DE |
| 2 | SPY in USD: US set R2 above Europe set R2 | PASS |
| 3 | SPY in USD, US set, identical to dev | PASS |
| 4 | EUR market factor against the hand-built formula, 5 dates | PASS (largest difference 0.0) |
| 5 | VGK monthly in EUR: same ordering | PASS |
| 6 | Balanced SAA with the Europe set, USD and EUR | PASS |
| 7 | World beta, macro and energy the same with both sets (SPY) | PASS after the fix in #43 (commit 9474d2e): identical, largest difference 0.0 |

## 1. VGK and EXSA.DE in EUR, both sets (daily)

R2 of the full-sample regression, adjusted R2 in brackets. Same window in both sets.

| Subject | Model | US set | Europe set | Europe minus US | Result |
|---|---|---|---|---|---|
| VGK (2005-03-11 to 2026-09-30) | FF5 | 0.7301 (0.7299) | 0.7024 (0.7021) | -0.0277 | FAIL |
| VGK | FF6 | 0.7304 (0.7301) | 0.7026 (0.7022) | -0.0278 | FAIL |
| EXSA.DE (2008-01-03 to 2026-09-30) | FF5 | 0.2906 (0.2898) | 0.8051 (0.8049) | +0.5145 | PASS |
| EXSA.DE | FF6 | 0.2940 (0.2930) | 0.8063 (0.8060) | +0.5123 | PASS |

Interpretation: EXSA.DE (STOXX Europe 600 on Xetra) behaves as planned: the Europe set lifts R2
from 0.29 to 0.81. VGK does not, at daily frequency. VGK is listed in New York and closes after
the European markets, so its daily return holds US afternoon news that the Europe factors only
show the next morning. This is the same close-time effect that Sprint 3 found for SXR8.
Diagnostic (information only, same 5,423 days for all three fits, FF5 columns): US factors
0.7302, Europe factors same day 0.6934, Europe factors same day plus next day 0.7115. The
next-day term closes about half of the gap and does not reverse it. The sample also differs:
the Europe set uses 5,224 days against 5,423, because VGK trades on about 200 days when the
Europe file has no row. The expectation in the sprint plan ("the Europe set must give the higher
R2 for VGK") holds at monthly frequency (check 5) and for a European-listed fund, not for a
US-listed one at daily frequency. This is a data and timing effect, not a product bug.

## 2. SPY in USD, both sets

| Model | US set | Europe set | Result |
|---|---|---|---|
| FF5 | 0.9673 (8,474 days) | 0.3219 (8,170 days) | PASS |
| FF6 | 0.9674 | 0.3228 | PASS |

Interpretation: the US set explains SPY almost fully, the Europe set about a third. The Europe
set also cuts 304 days (SPY trades on days the Europe file does not cover).

## 3. SPY in USD with the US set against dev

Whole report as JSON, FF5 and FF6, everything compared with `==` except `generated_at`.

| Figure | FF5 | FF6 | Result |
|---|---|---|---|
| R2 | 0.9673384948850845 (identical) | 0.9674305340624177 (identical) | PASS |
| Alpha, annual | -0.5765% (identical) | -0.4901% (identical) | PASS |
| Every other figure and string | identical, largest numeric difference 0.0 | the same | PASS |

Interpretation: with the US set the engine change leaves the report bit-identical to dev. The
script checks that the baseline process imported the export, not the branch.

## 4. EUR market factor against the hand-built formula

Europe daily file, converted to EUR by the app (`svc._model_frame`, FF6) against
`(1 + MktRF + RF)(1 + f) - 1 - c_eur`, built by hand from the raw Europe file, the ECB USD/EUR
fixings (EUR per USD, last fixing on or before the date) and the euro cash index (EONIA spliced
with euro STR, ACT/360, compounded; the script re-reads it from the raw rate series). `f` is
the return of the dollar over the interval from the previous row of the Europe file.

| Date | Previous row | Market factor by hand | In the app | Difference |
|---|---|---|---|---|
| 2000-05-24 | 2000-05-23 | -0.010969 | -0.010969 | 0.0 |
| 2007-05-02 | 2007-05-01 | 0.005549 | 0.005549 | 0.0 |
| 2014-04-08 | 2014-04-07 | -0.003908 | -0.003908 | 0.0 |
| 2021-03-15 | 2021-03-12 | 0.000337 | 0.000337 | 0.0 |
| 2026-09-30 | 2026-09-29 | -0.005968 | -0.005968 | 0.0 |

The `RF` column equals `c_eur` and SMB equals `SMB x (1 + f)` on the same dates, difference 0.0.
7,237 of the 9,458 Europe rows survive the conversion (the euro series starts in 1999).

Note on the first run: a version of the hand-built cash return that used simple interest between
two dates gave a 1.2e-8 difference on 2007-05-02 (1 May is a day with no euro rate fixing, so the
interval starts inside a fixing period). That was the check, not the app: the app reads a
compounded index, and the check now reads the same index.

## 5. VGK monthly in EUR (an uploaded record)

Month-end VGK prices in EUR (259 months, 2005-04 to 2026-09), sent through the upload path with
`record_currency=EUR`, `ccy=EUR`. 258 regression months.

| Model | US set | Europe set | Result |
|---|---|---|---|
| FF5 | 0.6067 | 0.9776 | PASS |
| FF6 | 0.6262 | 0.9778 | PASS |

Interpretation: at monthly frequency the close-time gap is gone (see check 1) and the Europe set
lifts R2 from 0.61 to 0.98.

## 6. Balanced SAA preset with the Europe set

Preset `saa` of `frontend/src/portfolio/presets.ts` (13 lines), FF6, window 2007-04-12 to
2026-09-30 (4,719 days).

| Measure | Expected | USD | EUR | Result |
|---|---|---|---|---|
| Report names the Europe set | europe | europe | europe | PASS |
| Rows (groups) | | 30 (16) | 31 (16) | |
| Largest group-minus-leaves difference | 0 | 0.0 | 0.0 | PASS |
| Holdings `total_return` against Performance cumulative return | equal | 300.51% = 300.51% | 254.81% = 254.81% | PASS |
| Top-level contributions minus total return | 0 | 1e-14 | 5e-15 | PASS |
| Sum of risk shares at depth 0 | 1 | 1.000000 | 1.000000 | PASS |
| R2 of the portfolio on the Europe factors (information) | | 0.520 | 0.506 | |

Interpretation: the table is arithmetically consistent in both currencies with the Europe set.
The window is 4,719 days, shorter than the 4,899 days of the US set in Sprint 3, for the same
calendar reason as in check 2.

## 7. World beta, macro and energy with both sets (SPY, USD)

Design decision 4 says these sections keep their current inputs, so they must be identical with
both sets.

| Section | FF5 | FF6 |
|---|---|---|
| World beta | differs (43 paths) | differs (43 paths) |
| Macro | differs (78 paths) | differs (78 paths) |
| Energy | differs (65 paths) | differs (65 paths) |

Result: FAIL on a65f080. The sections are rebuilt on the Europe analysis sample: the sample has
304 fewer days (the dates SPY trades and the Europe file lacks), and the world beta section also
reads the Europe market factor in its US-market row (`NOTE_EUROPE_WORLD_BETA`,
`backend/factordesk/pipeline.py`). The coordinator has a fix pending for the market factor.
Compare the sample size too: even with the right market factor, any section that is fitted on
the dates the factor frame covers will differ if the frame is the Europe one. The run should be
repeated on the fixed branch.

## Findings

1. The Europe set lifts R2 for a European-listed fund in EUR (EXSA.DE 0.29 to 0.81) and for VGK
   monthly (0.61 to 0.98). For VGK at daily frequency it lowers R2 (0.730 to 0.702) because VGK
   closes after Europe. The plan's check 1 should name an exchange-listed European ETF, or say
   "VGK monthly".
2. The Europe set drops the days that the Europe file lacks: 304 days for SPY, about 200 for
   VGK. A US-listed subject is analysed on fewer days, and that alone changes the macro, energy
   and world-beta sections.
3. The US set in USD is bit-identical to dev for SPY.
4. The EUR market factor is built correctly from the raw Europe file, the ECB dollar rate and the
   euro cash index.
5. Check 7 fails on this commit (macro, energy and world beta use the Europe frame).

## Rerun after the fix (2026-11-20)

The coordinator reran the script after merging `feat/factor-set-engine` at 9474d2e, with `--baseline` set to a checkout of dev at 5eb6c3d. Results:

- Checks 2 to 7 pass.
- Check 7 now passes. With Europe selected, world beta, macro and energy run on their own US-aligned sample with the US market factor. Their output is identical to the US set: zero differing fields, largest difference 0.0.
- Check 1 still fails for VGK on daily data. This is the close-time effect explained above, not a product bug. VGK on monthly data (check 5) and EXSA.DE on daily data both show the Europe set fitting far better. Guidance: for a European fund listed in the US, read the Europe set on monthly data.
