# Energy factor spike (S3-6)

Date: 2026-11-20. Sprint 3, item S3-6. Measure only: no app code changed.
Reproduce: `uv run python scripts/energy_factor_spike.py` (downloads FRED, Yahoo and Ken French data into `data/`, then prints every table below).

## Conclusion

1. **Lag terms: no.** 20 one-day lag terms were tested (4 subjects; OIL, GAS and CO2 where in the model). Two pass |t| > 2, both on GAS (t = 2.02 and 2.37). That is about what chance gives, and no OIL or CO2 lag passes. Keep one same-day beta per leg.
2. **Gas spike handling: yes.** The 5 largest |GAS| days hold 31% (2007+) and 41% (2020-08+) of the sum of squared GAS returns (excess kurtosis 115). Without them the only borderline daily GAS betas (SPY and 60/40, t = 1.9 and 2.0) fall to t = 1.5 and 1.3. Show the GAS beta with and without the 5 largest days, or winsorise. Monthly data goes the other way (XLE t 1.6 to 2.4 without the top 5 months), so the rule must be symmetric and not tuned to one frequency.
3. **VIF risk: low.** Model L (MKT, OIL, GAS) has VIF at most 1.14 and model C (adds CO2) at most 1.17. Risk appears only if COMM is added: OIL VIF goes to 1.6 (daily, 2007+) and 2.7 to 3.1 (2020-08+), with OIL and COMM correlated at +0.60 to +0.80. Still below 5, but keep COMM out of the Energy model.
4. **Surprises.** (a) Ken French data ends 2026-09-30, 51 days old. Every common sample stops there, although prices run to 2026-11-18. (b) GAS carries almost no signal for these subjects: daily betas are about 0.001 with t at or below 2.0, and monthly XLE is the best case at t = 1.6. (c) CO2 matters only for XLE (daily t = +3.6, monthly t = +1.2). (d) The clear effects are OIL on XLE (+0.21 to +0.38, t about 5 or more) and a negative OIL beta for 60/40 (t = -2.3 to -6.3, bonds fall when oil rises).
5. **Data health.** No non-positive prices in Brent or Henry Hub. FRED is fresh (last value 2026-11-17, 3 days old). Under the no-fill rule, Brent and Henry Hub lose 261 and 297 of 4,967 daily rows (2007+). Henry Hub has 73 missing days in 2007, so the daily GAS leg effectively starts on 2007-01-24.

## Setup

- OIL: log return of Brent spot (FRED `DCOILBRENTEU`). GAS: log return of Henry Hub spot (FRED `DHHNGSP`). Non-positive prices dropped: 0 and 0.
- CO2: KRBN total return minus French RF. COMM: DBC minus RF. MKT: French Mkt-RF. Returns are simple unless stated.
- Subjects are excess returns over RF: SPY, XLE, XLU, and 60/40 (IVV 60% / IEF 40%, `run_backtest`, monthly rebalance, no cost, from the same daily returns; the monthly 60/40 compounds the daily result).
- Alignment is the app's rule (`analytics/macro.py`): a daily leg return counts only when its previous level date equals the calendar's previous date. A missing FRED day removes that day and the next one. Nothing is filled. Monthly legs compound to month-end.
- Inference: `regression.ols_hac` (Newey-West; monthly uses the small-sample scaling and Student-t). VIF: `regression.vif`.
- Samples. Model L: 2007-01 to 2026-09-30, daily n = 4,603 (first row 2007-01-24), monthly n = 237. Model C and the carbon window: 2020-08 to 2026-09-30, daily n = 1,432, monthly n = 74.

## 1. Correlations (carbon window, 2020-08 to 2026-09)

Daily (n = 1,432):

| | MKT | OIL | GAS | CO2 | COMM |
|---|---|---|---|---|---|
| MKT | 1.00 | +0.05 | +0.02 | +0.23 | +0.20 |
| OIL | +0.05 | 1.00 | +0.05 | +0.06 | +0.79 |
| GAS | +0.02 | +0.05 | 1.00 | +0.01 | +0.07 |
| CO2 | +0.23 | +0.06 | +0.01 | 1.00 | +0.10 |
| COMM | +0.20 | +0.79 | +0.07 | +0.10 | 1.00 |

Monthly (n = 74):

| | MKT | OIL | GAS | CO2 | COMM |
|---|---|---|---|---|---|
| MKT | 1.00 | -0.01 | +0.11 | +0.37 | +0.19 |
| OIL | -0.01 | 1.00 | +0.04 | +0.10 | +0.80 |
| GAS | +0.11 | +0.04 | 1.00 | +0.04 | +0.16 |
| CO2 | +0.37 | +0.10 | +0.04 | 1.00 | +0.25 |
| COMM | +0.19 | +0.80 | +0.16 | +0.25 | 1.00 |

Full window without CO2 (2007+): OIL/COMM +0.60 daily and +0.73 monthly; OIL/MKT +0.20 daily and +0.34 monthly; GAS is below 0.2 with everything. The script prints these two matrices as well.

## 2. VIF

| model | freq | n | MKT | OIL | GAS | CO2 | COMM |
|---|---|---|---|---|---|---|---|
| L (2007+) | daily | 4603 | 1.04 | 1.04 | 1.00 | | |
| C (2020-08+) | daily | 1432 | 1.06 | 1.01 | 1.00 | 1.06 | |
| L + COMM (2007+) | daily | 4603 | 1.19 | 1.58 | 1.00 | | 1.80 |
| L + COMM (2020-08+) | daily | 1432 | 1.08 | 2.71 | 1.00 | | 2.82 |
| L (2007+) | monthly | 237 | 1.14 | 1.13 | 1.01 | | |
| C (2020-08+) | monthly | 74 | 1.17 | 1.01 | 1.01 | 1.17 | |
| L + COMM (2007+) | monthly | 237 | 1.25 | 2.19 | 1.05 | | 2.47 |
| L + COMM (2020-08+) | monthly | 74 | 1.12 | 3.06 | 1.05 | | 3.24 |

The script also prints L on the carbon window and C + COMM (OIL VIF 2.71 daily, 3.08 monthly).

## 3. Betas, Newey-West t in brackets

Beta is the excess return per 1.00 of the leg return. L = MKT, OIL, GAS. C = L + CO2.

Daily:

| subject | model | n | MKT | OIL | GAS | CO2 |
|---|---|---|---|---|---|---|
| SPY | L 2007+ | 4603 | +0.973 (106.1) | +0.002 (1.8) | +0.001 (1.9) | |
| SPY | C 2020-08+ | 1432 | +0.960 (90.6) | -0.000 (-0.3) | +0.000 (0.6) | +0.002 (0.7) |
| XLE | L 2007+ | 4603 | +0.990 (25.7) | +0.208 (5.5) | +0.002 (0.8) | |
| XLE | C 2020-08+ | 1432 | +0.555 (11.8) | +0.346 (14.3) | -0.001 (-0.4) | +0.078 (3.6) |
| XLU | L 2007+ | 4603 | +0.598 (15.0) | -0.010 (-1.5) | +0.003 (1.3) | |
| XLU | C 2020-08+ | 1432 | +0.419 (13.2) | -0.020 (-1.7) | +0.002 (0.8) | -0.007 (-0.3) |
| 60/40 | L 2007+ | 4603 | +0.531 (105.3) | -0.006 (-3.0) | +0.001 (2.0) | |
| 60/40 | C 2020-08+ | 1432 | +0.585 (71.2) | -0.013 (-6.2) | +0.001 (1.4) | -0.003 (-0.7) |

Monthly:

| subject | model | n | MKT | OIL | GAS | CO2 |
|---|---|---|---|---|---|---|
| SPY | L 2007+ | 237 | +0.968 (162.9) | -0.003 (-1.6) | +0.001 (0.5) | |
| SPY | C 2020-08+ | 74 | +0.965 (76.6) | -0.001 (-0.2) | +0.001 (0.7) | +0.001 (0.1) |
| XLE | L 2007+ | 237 | +0.766 (7.4) | +0.244 (5.7) | +0.040 (1.6) | |
| XLE | C 2020-08+ | 74 | +0.538 (3.3) | +0.369 (5.1) | +0.029 (0.9) | +0.146 (1.2) |
| XLU | L 2007+ | 237 | +0.442 (8.4) | -0.014 (-0.6) | +0.018 (0.9) | |
| XLU | C 2020-08+ | 74 | +0.484 (5.2) | -0.051 (-1.1) | -0.004 (-0.2) | -0.057 (-0.6) |
| 60/40 | L 2007+ | 237 | +0.587 (33.4) | -0.020 (-5.1) | -0.000 (-0.1) | |
| 60/40 | C 2020-08+ | 74 | +0.672 (27.4) | -0.015 (-2.3) | -0.001 (-0.1) | -0.011 (-0.7) |

The script also prints model L on the 2020-08+ window, so L and C compare on equal rows. Adding CO2 changes no OIL or GAS beta by more than its noise.

## 4. Lag test (daily)

Lag-1 terms of OIL, GAS and CO2 added. Cell = summed beta / t of the lag term alone. `*` = |t| > 2.

| subject | model | n | OIL | GAS | CO2 |
|---|---|---|---|---|---|
| SPY | L + lags 2007+ | 4379 | +0.001 / -0.8 | +0.001 / +2.0* | |
| SPY | C + lags 2020-08+ | 1351 | -0.002 / -1.5 | +0.001 / +1.7 | +0.002 / +0.4 |
| XLE | L + lags 2007+ | 4379 | +0.201 / -0.1 | -0.001 / -0.6 | |
| XLE | C + lags 2020-08+ | 1351 | +0.347 / +0.3 | -0.006 / -0.8 | +0.063 / -0.6 |
| XLU | L + lags 2007+ | 4379 | -0.007 / +0.3 | +0.005 / +1.7 | |
| XLU | C + lags 2020-08+ | 1351 | -0.002 / +1.6 | +0.005 / +1.5 | +0.004 / +0.4 |
| 60/40 | L + lags 2007+ | 4379 | -0.003 / +1.2 | +0.001 / +1.7 | |
| 60/40 | C + lags 2020-08+ | 1351 | -0.013 / -0.4 | +0.001 / +2.4* | +0.002 / +1.4 |

The GAS lag t is positive in 6 of 8 rows (SPY, XLU and 60/40, between +1.5 and +2.4). That is a weak hint, not a pass. Summed betas stay close to the same-day betas of section 3.

## 5. Gas spike influence

GAS beta (t) with all rows and without the 5 rows of largest |GAS|.

Daily, L 2007+ (n = 4,603). Largest |GAS| days: 2024-01-12 (+1.433), 2026-01-23 (+1.294), 2021-02-18 (-1.025), 2025-01-17 (+0.830), 2021-02-17 (+0.746). They hold 31% of the sum of squared GAS returns. Excess kurtosis 115.

| subject | all rows | without top 5 |
|---|---|---|
| SPY | +0.001 (1.9) | +0.001 (1.5) |
| XLE | +0.002 (0.8) | +0.001 (0.2) |
| XLU | +0.003 (1.3) | +0.004 (1.6) |
| 60/40 | +0.001 (2.0) | +0.001 (1.3) |

Daily, C 2020-08+ (n = 1,432). The same 5 days are the largest, and hold 41%. Excess kurtosis 63.

| subject | all rows | without top 5 |
|---|---|---|
| SPY | +0.000 (0.6) | -0.000 (-0.1) |
| XLE | -0.001 (-0.4) | -0.006 (-1.1) |
| XLU | +0.002 (0.8) | +0.004 (0.9) |
| 60/40 | +0.001 (1.4) | +0.000 (0.5) |

Monthly, L 2007+ (n = 237). Largest |GAS| months: 2026-02 (-0.876), 2022-12 (-0.687), 2024-11 (+0.622), 2020-10 (+0.602), 2026-01 (+0.585). They hold 32%. Excess kurtosis 3.8.

| subject | all rows | without top 5 |
|---|---|---|
| SPY | +0.001 (0.5) | +0.002 (1.2) |
| XLE | +0.040 (1.6) | +0.066 (2.4) |
| XLU | +0.018 (0.9) | +0.038 (2.1) |
| 60/40 | -0.000 (-0.1) | +0.002 (0.4) |

The 5 rows are removed from the regression and the Newey-West lag chain is not re-spaced. The effect of that on the t-statistics is small next to the shifts above.

## 6. Freshness (today 2026-11-20)

| series | last observation | days old |
|---|---|---|
| FRED DCOILBRENTEU | 2026-11-17 | 3 |
| FRED DHHNGSP | 2026-11-17 | 3 |
| Yahoo KRBN, DBC, SPY, XLE, XLU, IVV, IEF | 2026-11-18 | 2 |
| French daily and monthly FF5 | 2026-09-30 | 51 |

## Limits

- Daily Henry Hub spot is a thin, spiky series (weekend packages, cold snaps). Its HAC t-statistics are unreliable at kurtosis 115. Treat daily GAS betas as descriptive.
- The carbon model has 74 months and about 1,430 days, and KRBN holds mainly EU allowances. The "short sample, mainly EU carbon" label stays correct.
- 20 lag terms over 4 subjects is a small test. It rules out a large lag effect, not a small one.
