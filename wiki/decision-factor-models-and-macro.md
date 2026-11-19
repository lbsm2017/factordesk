# Decision: factor models (FF5 and FF6) and a separate macro section

Date: 2026-11-19
Status: Decided

## In one sentence

Every report can switch between the five-factor and six-factor (with momentum) models, shows alpha under four models side by side, and shows rates, credit and currency sensitivities in a separate section.

## What we decided

- A model toggle switches between FF5 and FF6. FF6 is FF5 plus the momentum factor, Mom.
- An alpha strip shows CAPM, FF3, FF5 and FF6 on the same sample. Each row shows alpha, t-statistic, R-squared and adjusted R-squared.
- The strip never marks one model as "best".
- A separate macro section runs its own regression with four factors: mkt_rf, TERM, DEF and EUR/USD.
- The toggle and the strip apply in every mode: ticker, track record and portfolio.

## Why

- Momentum is a key due-diligence test. "Alpha vanishes once momentum is added" is the signal we want the report to show, so FF6 must work in every mode.
- Alpha under four models on the same rows lets a reader see whether alpha shrinks as factors are added. That shrinking is the diagnostic.
- We do not pick a winner on screen. Fama and French (2018) rank the six-factor model first in their comparison. We treat that as context only.
- The macro section is a separate regression. It reports raw betas, Newey-West errors, correlations and VIF, which show how much the macro factors overlap.

## The macro factors

- TERM = IEF total return minus the risk-free rate.
- DEF = LQD total return minus IEF total return. It is labelled "credit minus rates, not duration-matched".
- EUR/USD comes from the FRED series DEXUSEU. The yfinance series EURUSD=X is the fallback. It is spot only, with no interest-rate carry, and is labelled "euro exposure".
- Data starts on 2002-07-30, the first Yahoo trade date for both IEF and LQD.
- Daily regressions add a one-day FX lag and report the summed EUR/USD beta. Monthly regressions compound each leg to month-end.

## How it works

- Mom is a long-short spread, so the risk-free rate is never subtracted from it. The library calls it "Mom", not "UMD".
- Alpha t-statistics use Newey-West errors with lag floor(4 × (T/100)^(2/9)). That gives 3 lags at 36 to 60 months and 4 lags at 120 months.
- HAC t-statistics are asymptotic. The report says they are approximate at 36 to 60 months.
- A t-statistic of 2 is a weak bar. Harvey, Liu and Zhu argue for about 3 when many candidates are tested. We show this as context and do not enforce it.

## What it costs us

- Four models on one strip means more numbers to read.
- DEF keeps some rate exposure. LQD's duration (about 7.6 years) is longer than IEF's (about 7.0 years). The label warns the reader, but DEF is not a pure credit factor.
- EUR/USD is spot only. It leaves out the interest-rate gap between the two currencies.
- The macro section starts in July 2002, so it cannot cover earlier years.
- The TERM and DEF wording in our research notes comes from memory. It must be checked against Fama and French (1993) before it is cited.

## What would change our mind

- If readers take DEF as pure credit, we would add the duration-matched version, LQD minus (D_LQD / D_IEF) × IEF. This is a later option.
- If the spot EUR/USD factor gives misleading results, a multi-currency dollar factor is the later alternative (Lustig, Roussanov and Verdelhan, 2011).
- If the macro factors overlap too much (high VIF), we would consider residualising them in a stated order. Orthogonalisation is not in version 1.

## Update, 2026-11-19: two more macro factors

- **What changed:** the owner added commodities (DBC − RF) and inflation (TIP − IEI) to the macro section, after research on candidate factors ([research notes, section G](../docs/research/next-stage-research.md)).
- **Why these two:** each one passed the causal-discipline test (multi-asset portfolios hold these asset classes), not a fit test.
- **Effect on the start date:** the macro section now starts at about 2007-01 instead of 2002-07-30. IEI starts last.
- **Still not adopted:**
  - High-yield credit, which is collinear with the market factor and with DEF.
  - A broad dollar index, which measures the same cause as EUR/USD.
  - AQR's BAB and QMJ, because of their licence terms.
  - q-factors, which are deferred.
  - Strategy-specific factors, which are deferred.

## Sources

- [Next-stage spec](../docs/specs/next-stage-track-record-and-portfolio.md): owner decisions on factors and the macro section, and epics E1 and E4.
- [Next-stage research](../docs/research/next-stage-research.md): sections A3, C1, C2, C3 and C4.

## Related decisions

- [Daily returns with robust errors](decision-daily-returns-and-robust-errors.md)
- [Which betas count as reliable](decision-which-betas-count-as-reliable.md)
- [Factor data source: the Ken French Data Library](decision-factor-data-source-french-library.md)
- [European mode, regional factors and currency](decision-european-mode-and-currency.md)
