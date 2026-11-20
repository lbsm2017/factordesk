# Dollar term in the EUR view: lag or lead (S4-7)

Date: 2026-11-20. Sprint 4, item S4-7. Measure only: no app code changed.
Reproduce: `uv run python scripts/dollar_lag_lead_spike.py` (downloads FRED, ECB and Yahoo data into `data/`, then prints every table below).

## Conclusion

1. **Recommendation: in the EUR view, replace the one-day lag term with a one-day lead term (daily subjects only).** Report the summed beta (same day plus next day), as the lag does today. Keep the USD view as it is for now (point 5).
2. **The lag term does nothing in the EUR view.** For the five subjects (SPY, VGK, EFA, IEF, 60/40) the lag has |t| at most 1.8 and adds at most 0.3 basis points (bp) of adjusted R2. The joint test of the lag term has p between 0.07 and 0.58.
3. **The lead term does a lot for three of the five subjects.** In the EUR view the lead has t = -15.2 for VGK, -13.6 for EFA and -8.2 for IEF. The adjusted R2 rises by 184, 115 and 105 bp. For SPY and 60/40 it adds 0.1 bp (t = -1.2 and -1.7): no harm, no gain. Lag plus lead is no better than lead alone (VGK 184.1 bp against 184.0 bp).
4. **Close-time mismatch explains the lead for US-listed funds.** The ECB rate is fixed at about 14:10 CET and a US fund closes at 22:00 CET, so 7 h 50 min of the fund's day fall after the fixing. That part is in the next day's dollar return. Three checks agree: no effect at day t-1 or t+2 (all |t| below 1.4 for the three funds); the lead of VGK and EFA is about three times smaller when the same regression uses the noon New York rate (4 h before the close); and the Fed index (also a noon fixing) gives a lead between the two. One check does not agree: the Xetra control (EXSA.DE) has a positive lead (see Caveats).
5. **The USD view has the same lead.** With the Fed index (noon fixing), VGK, EFA and IEF have a lead at t = -5.8, -5.1 and -4.9 (+26, +18 and +97 bp). That is larger than the lag the app uses (t = +2.8, +2.3 and -0.2; +6, +4 and -2 bp). Changing the USD view would change the golden report, so it is not part of this recommendation. It is a separate, owner-level decision.

## What the model is

The macro regression of `analytics/macro.py`, built by `macro.build_design` itself: market, TERM, DEF, COMM, INFL and the dollar leg, daily, 2007-01 to 2026-09 (the French factor file ends 2026-09-30). The legs, the alignment rule (a daily return counts only when its previous date is the calendar's previous date) and the EUR conversion are the app's. Inference is `regression.ols_hac` (Newey-West).

- **USD view.** The dollar leg is the Fed broad index (FRED `DTWEXBGS`, noon New York fixing).
- **EUR view.** The dollar leg is `f`, the return of the US dollar in euros from ECB reference rates (about 14:10 CET). The subject is `(1 + R)(1 + f) - 1 - c` with `c` the euro cash return, and the market factor is converted by `convert_factors`.
- **EUR-noon view (test only).** The EUR view with FRED H.10 `DEXUSEU` (noon New York, the app's fallback source) instead of the ECB rate. Used in section 4 only.
- **Subjects.** SPY, VGK, EFA, IEF and 60/40 (IVV 60% and IEF 40%, `run_backtest`, monthly rebalance, no cost; in the EUR view converted as one unhedged line). IEF is its own TERM leg and sits inside DEF, so for IEF those two columns are removed. Control: EXSA.DE (STOXX Europe 600 on Xetra, a euro listing, closes 17:30 CET), euro views only.
- **Specifications.** The same-day dollar term is in every one. `none` is the same-day term alone; `lag` adds the previous day; `lead` adds the next day; `lag+lead` adds both; `no dollar` removes the dollar leg (a baseline only). Each subject and view uses one common sample, so the adjusted R2 values compare.
- **Reading the tables.** Cell = coefficient (Newey-West t); `*` marks |t| > 2. `sum` is every dollar term added (the beta the app reports). `p(added)` is the joint test that the added terms are zero. `dR2` is the change of adjusted R2 against `none`, in bp.
- **Samples.** USD: 2007-01-18 to 2026-09-29, n = 4,199 (the Fed index has 214 missing days, each removing that day and the next). EUR: 2007-01-12 to 2026-09-29, n = 4,959. EXSA.DE: 2008-01-04 to 2026-09-30, n = 4,439.

## 1. Lag, lead, both or neither

**EUR view** (the recommendation is about this view)

| subject | spec | n | same | lag | lead | sum | p(added) | adjR2 | dR2 bp |
|---|---|---|---|---|---|---|---|---|---|
| SPY | none | 4959 | +0.022 (+2.2)* |  |  | +0.022 (+2.2)* |  | 0.9843 | +0.0 |
| SPY | lag | 4959 | +0.022 (+2.2)* | +0.013 (+1.8) |  | +0.035 (+4.4)* | 0.067 | 0.9843 | +0.3 |
| SPY | lead | 4959 | +0.022 (+2.3)* |  | -0.007 (-1.2) | +0.015 (+1.6) | 0.216 | 0.9843 | +0.1 |
| SPY | lag+lead | 4959 | +0.022 (+2.3)* | +0.013 (+1.8) | -0.007 (-1.2) | +0.028 (+3.6)* | 0.087 | 0.9843 | +0.3 |
| SPY | no dollar | 4959 |  |  |  |  |  | 0.9842 | -0.7 |
| VGK | none | 4959 | -0.404 (-11.0)* |  |  | -0.404 (-11.0)* |  | 0.7546 | +0.0 |
| VGK | lag | 4959 | -0.404 (-11.0)* | +0.022 (+1.1) |  | -0.382 (-9.7)* | 0.258 | 0.7546 | +0.2 |
| VGK | lead | 4959 | -0.371 (-10.5)* |  | -0.359 (-15.2)* | -0.730 (-18.3)* | 0.000 | 0.7730 | +184.0 |
| VGK | lag+lead | 4959 | -0.371 (-10.6)* | +0.020 (+1.1) | -0.359 (-15.2)* | -0.711 (-16.8)* | 0.000 | 0.7730 | +184.1 |
| VGK | no dollar | 4959 |  |  |  |  |  | 0.7356 | -189.7 |
| EFA | none | 4959 | -0.259 (-7.5)* |  |  | -0.259 (-7.5)* |  | 0.7969 | +0.0 |
| EFA | lag | 4959 | -0.259 (-7.5)* | +0.014 (+0.7) |  | -0.245 (-7.2)* | 0.454 | 0.7969 | -0.1 |
| EFA | lead | 4959 | -0.234 (-7.0)* |  | -0.266 (-13.6)* | -0.500 (-14.0)* | 0.000 | 0.8084 | +114.9 |
| EFA | lag+lead | 4959 | -0.234 (-7.0)* | +0.012 (+0.7) | -0.265 (-13.6)* | -0.488 (-13.6)* | 0.000 | 0.8084 | +114.7 |
| EFA | no dollar | 4959 |  |  |  |  |  | 0.7880 | -88.8 |
| IEF | none | 4959 | +1.159 (+84.7)* |  |  | +1.159 (+84.7)* |  | 0.7015 | +0.0 |
| IEF | lag | 4959 | +1.159 (+84.8)* | -0.008 (-0.6) |  | +1.151 (+58.9)* | 0.550 | 0.7015 | -0.3 |
| IEF | lead | 4959 | +1.164 (+85.7)* |  | -0.135 (-8.2)* | +1.029 (+46.1)* | 0.000 | 0.7121 | +105.3 |
| IEF | lag+lead | 4959 | +1.164 (+85.7)* | -0.008 (-0.6) | -0.135 (-8.2)* | +1.021 (+39.8)* | 0.000 | 0.7121 | +105.2 |
| IEF | no dollar | 4959 |  |  |  |  |  | 0.0143 | -6872.2 |
| 60/40 | none | 4959 | +0.427 (+106.9)* |  |  | +0.427 (+106.9)* |  | 0.9908 | +0.0 |
| 60/40 | lag | 4959 | +0.427 (+106.8)* | +0.002 (+0.6) |  | +0.429 (+92.8)* | 0.582 | 0.9908 | -0.0 |
| 60/40 | lead | 4959 | +0.428 (+105.5)* |  | -0.005 (-1.7) | +0.423 (+100.8)* | 0.096 | 0.9908 | +0.1 |
| 60/40 | lag+lead | 4959 | +0.428 (+105.4)* | +0.002 (+0.5) | -0.005 (-1.7) | +0.424 (+81.5)* | 0.155 | 0.9908 | +0.1 |
| 60/40 | no dollar | 4959 |  |  |  |  |  | 0.9280 | -628.9 |
| EXSA.DE | none | 4439 | -0.602 (-12.9)* |  |  | -0.602 (-12.9)* |  | 0.3924 | +0.0 |
| EXSA.DE | lag | 4439 | -0.601 (-12.9)* | -0.033 (-1.2) |  | -0.635 (-11.6)* | 0.229 | 0.3925 | +1.2 |
| EXSA.DE | lead | 4439 | -0.617 (-12.9)* |  | +0.153 (+3.9)* | -0.464 (-9.2)* | 0.000 | 0.3973 | +49.5 |
| EXSA.DE | lag+lead | 4439 | -0.617 (-12.9)* | -0.032 (-1.2) | +0.153 (+3.9)* | -0.496 (-8.4)* | 0.000 | 0.3974 | +50.5 |
| EXSA.DE | no dollar | 4439 |  |  |  |  |  | 0.3289 | -634.6 |

**USD view** (for comparison)

| subject | spec | n | same | lag | lead | sum | p(added) | adjR2 | dR2 bp |
|---|---|---|---|---|---|---|---|---|---|
| SPY | none | 4199 | -0.008 (-0.5) |  |  | -0.008 (-0.5) |  | 0.9820 | +0.0 |
| SPY | lag | 4199 | -0.009 (-0.5) | +0.019 (+1.0) |  | +0.011 (+0.4) | 0.304 | 0.9820 | +0.2 |
| SPY | lead | 4199 | -0.008 (-0.5) |  | -0.003 (-0.3) | -0.011 (-0.6) | 0.758 | 0.9820 | -0.0 |
| SPY | lag+lead | 4199 | -0.009 (-0.5) | +0.019 (+1.0) | -0.003 (-0.3) | +0.007 (+0.3) | 0.588 | 0.9820 | +0.2 |
| SPY | no dollar | 4199 |  |  |  |  |  | 0.9820 | +0.0 |
| VGK | none | 4199 | -1.081 (-17.2)* |  |  | -1.081 (-17.2)* |  | 0.8065 | +0.0 |
| VGK | lag | 4199 | -1.085 (-17.3)* | +0.113 (+2.8)* |  | -0.972 (-13.1)* | 0.005 | 0.8071 | +6.3 |
| VGK | lead | 4199 | -1.102 (-17.8)* |  | -0.231 (-5.8)* | -1.333 (-17.5)* | 0.000 | 0.8090 | +25.6 |
| VGK | lag+lead | 4199 | -1.107 (-17.9)* | +0.114 (+2.9)* | -0.231 (-5.9)* | -1.224 (-14.6)* | 0.000 | 0.8097 | +32.0 |
| VGK | no dollar | 4199 |  |  |  |  |  | 0.7559 | -506.1 |
| EFA | none | 4199 | -0.833 (-14.6)* |  |  | -0.833 (-14.6)* |  | 0.8301 | +0.0 |
| EFA | lag | 4199 | -0.836 (-14.8)* | +0.084 (+2.3)* |  | -0.752 (-10.1)* | 0.021 | 0.8305 | +3.9 |
| EFA | lead | 4199 | -0.850 (-15.2)* |  | -0.179 (-5.1)* | -1.028 (-16.4)* | 0.000 | 0.8319 | +17.8 |
| EFA | lag+lead | 4199 | -0.853 (-15.5)* | +0.085 (+2.3)* | -0.179 (-5.2)* | -0.947 (-12.4)* | 0.000 | 0.8323 | +21.8 |
| EFA | no dollar | 4199 |  |  |  |  |  | 0.7950 | -351.0 |
| IEF | none | 4199 | -0.146 (-4.2)* |  |  | -0.146 (-4.2)* |  | 0.1886 | +0.0 |
| IEF | lag | 4199 | -0.146 (-4.2)* | -0.005 (-0.2) |  | -0.151 (-3.7)* | 0.825 | 0.1884 | -1.8 |
| IEF | lead | 4199 | -0.156 (-4.6)* |  | -0.129 (-4.9)* | -0.286 (-6.4)* | 0.000 | 0.1983 | +97.0 |
| IEF | lag+lead | 4199 | -0.156 (-4.6)* | -0.004 (-0.2) | -0.129 (-4.9)* | -0.290 (-5.9)* | 0.000 | 0.1981 | +95.2 |
| IEF | no dollar | 4199 |  |  |  |  |  | 0.1776 | -110.2 |
| 60/40 | none | 4199 | -0.009 (-1.3) |  |  | -0.009 (-1.3) |  | 0.9863 | +0.0 |
| 60/40 | lag | 4199 | -0.009 (-1.3) | -0.005 (-0.9) |  | -0.014 (-1.6) | 0.370 | 0.9863 | +0.0 |
| 60/40 | lead | 4199 | -0.009 (-1.2) |  | +0.007 (+1.3) | -0.001 (-0.1) | 0.192 | 0.9863 | +0.1 |
| 60/40 | lag+lead | 4199 | -0.008 (-1.2) | -0.005 (-0.9) | +0.007 (+1.3) | -0.006 (-0.6) | 0.364 | 0.9863 | +0.1 |
| 60/40 | no dollar | 4199 |  |  |  |  |  | 0.9862 | -0.1 |

## 2. Where the dollar effect sits in time

One regression per subject with the dollar return of days t+2 and t+1 (leads), t, t-1 and t-2 (lags) next to the other macro factors. Cell = coefficient (Newey-West t). `lead share` = lead / (lead + same day), shown when the same-day beta is above 0.05 in size.

**EUR view**

| subject | n | t+2 | t+1 | same | t-1 | t-2 | lead share |
|---|---|---|---|---|---|---|---|
| SPY | 4958 | +0.003 (+0.6) | -0.007 (-1.2) | +0.022 (+2.2)* | +0.013 (+1.8) | -0.012 (-2.1)* | n/a |
| VGK | 4958 | +0.017 (+0.7) | -0.359 (-15.3)* | -0.371 (-10.6)* | +0.020 (+1.1) | +0.027 (+1.3) | 49% |
| EFA | 4958 | +0.019 (+1.0) | -0.266 (-13.6)* | -0.234 (-7.0)* | +0.012 (+0.7) | +0.015 (+0.9) | 53% |
| IEF | 4958 | -0.000 (-0.0) | -0.135 (-8.2)* | +1.164 (+85.7)* | -0.008 (-0.6) | +0.001 (+0.1) | -13% |
| 60/40 | 4958 | +0.000 (+0.2) | -0.005 (-1.6) | +0.428 (+105.0)* | +0.002 (+0.5) | -0.008 (-3.2)* | -1% |
| EXSA.DE | 4438 | +0.028 (+0.8) | +0.153 (+3.9)* | -0.616 (-13.0)* | -0.032 (-1.2) | +0.060 (+2.4)* | -33% |

**USD view**

| subject | n | t+2 | t+1 | same | t-1 | t-2 | lead share |
|---|---|---|---|---|---|---|---|
| SPY | 3766 | +0.013 (+0.8) | -0.002 (-0.1) | -0.005 (-0.3) | +0.021 (+1.0) | -0.009 (-0.5) | n/a |
| VGK | 3766 | -0.046 (-1.3) | -0.234 (-5.7)* | -1.078 (-16.5)* | +0.136 (+3.3)* | +0.022 (+0.5) | 18% |
| EFA | 3766 | -0.034 (-1.0) | -0.189 (-5.1)* | -0.818 (-14.3)* | +0.101 (+2.7)* | +0.015 (+0.4) | 19% |
| IEF | 3766 | +0.012 (+0.6) | -0.136 (-4.9)* | -0.152 (-4.3)* | -0.011 (-0.5) | -0.010 (-0.4) | 47% |
| 60/40 | 3766 | -0.003 (-0.5) | +0.009 (+1.5) | -0.006 (-0.7) | -0.002 (-0.4) | -0.006 (-1.1) | n/a |

In the EUR view the effect sits on day t and day t+1 only. For VGK and EFA the two coefficients are about equal. Days t-1, t-2 and t+2 are near zero.

## 3. Close times

| event | time |
|---|---|
| US fund close | 16:00 New York = 22:00 CET |
| Xetra close (EXSA.DE) | 17:30 CET |
| Fed broad dollar index, FRED `DTWEXBGS` (H.10 noon rates) | noon New York = 18:00 CET |
| ECB euro reference rate (the app's EUR source) | about 14:10 CET |

A day-t return measured close to close covers (close t-1, close t). The dollar return of day t covers (fixing t-1, fixing t). The part of the fund's day after the day-t fixing is the dollar move of the next fixing window. So a fixing earlier than the close puts the missing overlap in the dollar return of day t+1: a lead. A lag would be right only if the fixing came after the close of the same day, which is never the case here. For a US close, the gap after the fixing is 7 h 50 min for the ECB rate (about a third of a day) and 4 h for a noon New York rate (about a sixth). Against a Xetra close the gap after the ECB fixing is 3 h 20 min.

## 4. Does the lead follow the fixing time?

Same subjects, three dollar legs. Cell = lead coefficient (t) in the `lead` model; after the semicolon, its share of lead plus same-day coefficient.

| subject | USD: Fed index, noon NY | EUR: ECB, 14:10 CET | EUR: H.10, noon NY |
|---|---|---|---|
| SPY | -0.003 (-0.3) | -0.007 (-1.2) | -0.005 (-0.9) |
| VGK | -0.231 (-5.8)*; 17% | -0.359 (-15.2)*; 49% | -0.113 (-5.8)*; 15% |
| EFA | -0.179 (-5.1)*; 17% | -0.266 (-13.6)*; 53% | -0.090 (-5.1)*; 18% |
| IEF | -0.129 (-4.9)*; 45% | -0.135 (-8.2)*; -13% | -0.060 (-4.0)*; -6% |
| 60/40 | +0.007 (+1.3) | -0.005 (-1.7); -1% | +0.001 (+0.3); 0% |
| EXSA.DE |  | +0.153 (+3.9)*; -33% | +0.154 (+4.5)*; -34% |

The prediction is that the lead shrinks when the fixing moves closer to the close. For VGK and EFA it does: the coefficient falls from -0.36 and -0.27 (ECB) to -0.11 and -0.09 (noon New York), a factor of about 3 where the hours predict about 2. The Fed index, another noon fixing, sits in between (-0.23 and -0.18). IEF behaves the same way (-0.135 to -0.060). SPY and 60/40 have no lead with any source.

## Caveats

- **Control subject.** EXSA.DE has a positive lead (t = +3.9 and +4.5) that does not change with the fixing time. The close-time reading predicts a small negative lead for the ECB rate and about zero for the noon rate. The model uses the US market factor, whose close is 4 h 30 min after Xetra's, so the control is confounded. The Europe factor set (S4-2, S4-3) removes that problem; repeat the control then.
- **VGK and EFA are US listings of European stocks.** Part of the "dollar" effect is the same time gap applied to the European stocks' own euro moves. The lead is a statistical fix for the time gap, not a claim that the funds hold a dollar exposure. The summed beta for VGK in the EUR view goes from -0.40 (same day) to -0.73 (with the lead), so the wording matters.
- **Last day.** A lead term needs the next day's dollar return. The newest row of a sample drops out. The effect is one row.
- **Summer time.** New York and Europe change summer time on different weeks. For about 3 weeks a year the gap is an hour smaller. Not modelled.
- **Scope.** Five subjects and one control, daily data, one period. Monthly regressions have no lag today and need no lead.

## Recommendation for the build (small follow-up)

1. EUR view, daily subjects: in `macro.build_design`, replace the previous-date lag with the next-date lead. Keep the summed beta and its standard error from the full covariance (`summed_beta` already does it). The monthly view stays without a term.
2. Label the row "US dollar against the euro (same day and next day)" and add one sentence to the section note: the ECB rate is fixed before the US close, so the next day's move belongs to today's return.
3. Leave the USD view and the golden report unchanged. Open one owner decision: use the lead in the USD view too (VGK, EFA and IEF gain more from a lead than from the lag). That change moves the golden macro section, so it needs the owner's approval and a new snapshot.
4. Update `wiki/decision-factor-models-and-macro.md` (the EUR dollar-leg paragraph says the lag term stays) and `wiki/decision-reference-currency.md` when the build lands.

## 5. Freshness

Today: 2026-11-20.

| series | last observation | calendar days old |
|---|---|---|
| French daily FF5 | 2026-09-30 | 51 |
| FRED DTWEXBGS | 2026-11-13 | 7 |
| Yahoo IEF | 2026-11-19 | 1 |
| Yahoo LQD | 2026-11-19 | 1 |
| Yahoo DBC | 2026-11-19 | 1 |
| Yahoo TIP | 2026-11-19 | 1 |
| Yahoo IEI | 2026-11-19 | 1 |
| Yahoo SPY | 2026-11-19 | 1 |
| Yahoo VGK | 2026-11-19 | 1 |
| Yahoo EFA | 2026-11-19 | 1 |
| Yahoo IVV | 2026-11-19 | 1 |
| Yahoo EXSA.DE | 2026-11-18 | 2 |
