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

## Update, 2026-11-19: broad dollar index replaces EUR/USD; no VIX

- **The FX factor is now the Fed broad dollar index (FRED DTWEXBGS).**
  - A USD portfolio of international funds is exposed to the dollar against all its trading partners, not just the euro.
  - The Fed index is public and covers 26 currencies. ICE's DXY is proprietary and mostly euro.
  - A positive beta means the subject gains when the dollar strengthens.
  - The 1-day lag term stays, because the index uses the same noon fixing.
  - EUR/USD moves to the future European mode and is never used alongside the dollar index.
- **VIX was assessed and skipped for now.** It is not a return and largely repeats the market factor. For most subjects it is a common shock rather than something held. See [research notes, section G3](../docs/research/next-stage-research.md).

## Sources

- [Next-stage spec](../docs/specs/next-stage-track-record-and-portfolio.md): owner decisions on factors and the macro section, and epics E1 and E4.
- [Next-stage research](../docs/research/next-stage-research.md): sections A3, C1, C2, C3 and C4.

## Related decisions

- [Daily returns with robust errors](decision-daily-returns-and-robust-errors.md)
- [Which betas count as reliable](decision-which-betas-count-as-reliable.md)
- [Factor data source: the Ken French Data Library](decision-factor-data-source-french-library.md)
- [European mode, regional factors and currency](decision-european-mode-and-currency.md)

## Update, 2026-11-20: the macro section as built

- **Six factors, one regression:** market, TERM, DEF, COMM, INFL and USD. It is separate from the headline model and its intercept is not the headline alpha.
- **First price dates of the funds (checked on Yahoo):** IEF 2002-07-30, LQD 2002-07-30, TIP 2003-12-05, DBC 2006-02-06, IEI 2007-01-11. The dollar index starts 2006-01-02. So the window starts in January 2007, set by IEI.
- **Same-interval rule:** a daily fund return counts only when the fund's previous price date is the subject's previous date. A missing price is never filled.
- **Dollar timing:** the index is a noon New York fixing, so daily data adds the previous day's return and reports the summed beta. The standard error of the sum comes from the full HAC covariance. Monthly data compounds each fund to the month-end and has no lag term.
- **If FRED is unreachable:** the section runs without the dollar and says "dollar index unavailable". An older cached copy is used first, with a note.
- **Overlap:** VIF and the correlation matrix show how much the factors share. The VIF is computed on the six factors without the lag term. A badge shows when VIF is above 5.
- **Tags:** reliable or noise by the same Benjamini-Hochberg rule as the headline betas, across the factors of this regression.

## Update, 2026-11-20: oil, gas and carbon get their own section

- **What changed:** an Energy & carbon section now follows the macro section. Its legs are the Brent oil change, the Henry Hub gas change and KRBN (carbon), with the market as a control. Details are on the [energy and carbon page](energy-and-carbon-factors.md).
- **Why a separate section:** the legs do not belong in the macro regression. Broad commodities (COMM) already sit there, and oil and COMM correlate +0.6 to +0.8, so mixing them would inflate the VIF.
- **Also fixed:** the macro correlation matrix was computed twice (and a third time for the condition number). It is now computed once. The output is the same.

## Update, 2026-11-20: the macro section in the euro view

- **What changed:** the macro section now runs in the EUR view. It no longer hides there.
- **How the legs are converted** (`f` is the return of the US dollar in euros over the same interval, `c` the euro cash return):
  - TERM, DEF and INFL are spreads of two US-dollar returns, so each becomes the USD spread times `(1 + f)`. TERM still uses the US-dollar risk-free rate inside the spread.
  - COMM becomes `(1 + DBC)(1 + f) − 1 − c`.
  - The market leg and the subject's excess return are already in euros.
- **The dollar leg:** in the euro view the Fed broad dollar index is replaced by `f`, the dollar measured in euros. The row is labelled "US dollar against the euro". Daily regressions keep the one-day lag term and the summed beta.
- **What we did not change:** the US-dollar view, including its golden report, is the same as before.
- Details: [reference currency](decision-reference-currency.md).

## Update, 2026-11-20 (Sprint 4): lead or lag spike, and the factor set

- **Spike on the dollar term.** The note [dollar lag and lead](../docs/research/dollar-lag-lead-spike.md) (PR #41, merged at 5eb6c3d) tested the dollar leg of the macro section. In the euro view a one-day lead explains much more than the one-day lag for VGK, EFA and IEF (adjusted R-squared +184, +115 and +105 bp, against at most +0.3 bp for the lag). The USD view, with the Fed index, has a smaller lead of the same sign. The note names close times as the cause. A lead is a negative shift, forbidden by [no look-ahead rule](decision-no-look-ahead-rule.md), so it was not built. The owner has not decided (options: keep the rule; allow a labelled lead; use a fixing nearer the US close). The statements above that daily regressions add a one-day lag are not superseded as of 2026-11-20.
- **Design decision 4 of Sprint 4.** On 2026-11-20 the plan fixed that the macro section, the energy section and the world beta keep the US factors, and their own US-aligned sample, for every factor set. On the first engine branch (commit a65f080) the validation found that they differed between the US and Europe sets. The fix is commit 9474d2e, after which they are identical (largest difference 0.0). Details: [Europe factor set](decision-europe-factor-set.md).
- **TTF gas.** On 2026-11-20 the data check ([TTF data check](../docs/research/ttf-data-check.md), PR #42, merged at c1575b5) found one usable free source, Yahoo `TTF=F`, daily from 2017-10-23, with a false roll step on 2019-09-30. It is not built; the note recommends a later item of about 2 points. The legs of [Energy & carbon](energy-and-carbon-factors.md) are still Brent, Henry Hub and KRBN as of 2026-11-20.
