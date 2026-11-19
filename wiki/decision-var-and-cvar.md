# Decision: VaR and CVaR for single names, track records and portfolios

Date: 2026-11-19
Status: Decided, not yet built

## In one sentence

Every report shows how much could be lost on a bad day or month, using three methods side by side at Basel-style levels, with an honest band showing how uncertain each figure is.

## What we decided

- **Methods:** historical, Gaussian (normal) and Cornish-Fisher (normal adjusted for skewness and fat tails), side by side.
- **Levels:** 99% VaR and 97.5% CVaR (expected shortfall) are the headline everywhere. Monthly series also get a 95% row.
- **Horizon:** results stay at the series' own frequency (1-day for daily data, 1-month for monthly). No square-root-of-time scaling.
- **Uncertainty:** each figure shows a 90% bootstrap band and how many bad days or months it rests on. A historical figure with fewer than about three expected tail observations shows "n/a" and the reason.
- **Portfolios:** each holding's share of CVaR, rolled up through the SAA tree.
- **Deferred:** backtests (Kupiec, Christoffersen), GARCH and extreme-value methods, Student-t.

## Why

- The owner wanted Basel-style levels so that all modes are comparable.
- A 36-month record has less than one month beyond the 99% level, so a historical 99% figure would be noise. The 95% row gives monthly records at least one historical figure.
- Peer tools show methods side by side, and the gap between the methods is itself a warning sign of fat tails.
- CVaR contributions add up exactly across holdings. VaR contributions do not.
- Testing VaR on the history it was fitted on proves nothing, and monthly records are too short for a real test.

## How it works

- Losses are positive percentages of value, computed from simple returns.
- Cornish-Fisher shows "n/a" outside the range where its formula is valid (Maillard 2012). Its CVaR is never shown below its VaR.
- The bootstrap resamples blocks of days for daily data, because volatility clusters, and single months for monthly data.
- A holding's CVaR share is its average contribution on the portfolio's worst days. Below about 20 such days it switches to a normal-distribution estimate, and says so.

## What it costs us

- Monthly records will often show "n/a" at 99%, which may surprise users. The reason is always printed.
- The bands make the results look less certain than peer tools do. That is deliberate.
- There is no backtest in version 1.

## What would change our mind

- If users need forward-looking risk, conditional methods (GARCH, EVT) come back for long daily series.
- If the Cornish-Fisher guard hides too many figures, the corrected expansion (Amédée-Manesme et al. 2019) is the next step.

## Sources

- [Next-stage spec, E7](../docs/specs/next-stage-track-record-and-portfolio.md)
- [Research notes, section D](../docs/research/next-stage-research.md)
