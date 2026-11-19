# Decision: monthly track-record uploads

Date: 2026-11-19
Status: Decided

## In one sentence

A user can upload a monthly or daily return record for a fund or manager, we check and analyse it in memory, and monthly records need at least 36 months, with a warning under 60.

## What we decided

- Users upload a CSV or XLSX file that follows our template. It has a date column, a return or NAV column, and header fields for currency, gross or net, and name.
- Frequency is daily or monthly. Weekly uploads are refused for now.
- Monthly records need at least 36 months. We warn below 60 months. Daily records keep the existing floor of 504 observations.
- Each report compares the record with ACWI by default. It shows tracking error, information ratio and up and down capture, on the overlapping period only.
- Each report runs three smoothing checks. They are described below.
- Uploads are processed in memory only and are never written to disk.
- The first release accepts CSV with a date and a decimal return, assumes USD, and caps files at 1 MB. XLSX, NAV input, format detection, daily uploads and the template download come in the upload hardening release.

## Why

- Track-record statistics answer one question: is the return alpha, or cheap beta?
- The first upload path is monthly, because the walking skeleton proves that path first.
- The 36 and 60 month limits are practitioner convention. No paper sets them as a rule. Morningstar's style analysis asks for 20 to 36 months. We use the higher figure.
- Uploads stay in memory, so the repository and the data folder never hold a manager's returns.

## Amendment to the daily-data decision

[Daily returns with robust errors](decision-daily-returns-and-robust-errors.md) is amended, not replaced. Stock tickers still use daily data with Newey-West errors. Uploads add monthly records, using the same robust-error approach with a lag rule suited to monthly data.

## How it works

- Refused on upload: duplicate dates, dates out of order, calendar gaps, and weekly data.
- Flagged on upload: outliers (|r| more than 5 standard deviations, or a monthly return outside about -50% to +100%), a large move followed by an exact reversal, and a high share of zero or repeated returns. Thresholds are our choice.
- NAV input, when added, converts with r_t = NAV_t / NAV_(t-1) - 1. It is valid only for total-return or distribution-adjusted NAV per unit. A gap in NAV is refused.
- Gross or net is required and shown on every output. We never mix the two in one record.
- Smoothing check 1: autocorrelation at lags 1 to 3 (lags 1 to 6 when T is 60 or more), plus a Ljung-Box test with lags min(6, T/5) at 5%. The flag fires when rho-1 is outside plus or minus 1.96 / sqrt(T), or when Ljung-Box rejects.
- Smoothing check 2: a Dimson beta using the market return and two monthly lags. The report shows the summed beta next to the plain beta, with a Wald test that the lag terms are zero. Standard errors are Newey-West.
- Smoothing check 3: Lo's adjusted Sharpe ratio, with q = 12 for monthly data. Lo reports that ignoring serial correlation can overstate the annualised Sharpe ratio by more than 65%.
- Benchmark: tracking error is the standard deviation of active return, annualised with the square root of 12. Information ratio is mean active return over tracking error, using arithmetic annualisation. Up and down capture needs at least 12 up months and 12 down months.
- Self-reported records can be backfilled. Secondary sources put the bias at roughly 0.4% to 1.4% a year. We do not correct for it, but the report says the bias exists.

## What it costs us

- The first release takes CSV only, so other formats wait for the hardening release.
- Nothing is saved. A user who comes back must upload again.
- A record of 36 to 60 months gives wide error bands, and its HAC t-statistics are approximate.
- The smoothing checks flag problems. They do not correct returns. Unsmoothing is not automatic.
- ACWI's ETF starts in March 2008, so a long record is compared only over the later overlap.

## What would change our mind

- If users need saved records, the in-memory rule needs a new decision from the owner.
- If 36 months proves too strict for real records, we would revisit it. No paper sets the figure, so user evidence is the test.
- Weekly uploads are a deferred item and will be revisited later.
- If the statistics fail to match the hand-worked or statsmodels values in the spec, the release waits until they do.

## Update, 2026-11-19: small-sample correction for monthly regressions

- On 2026-11-19 the owner decided that monthly regressions use a small-sample correction.
- The robust (HAC) covariance is scaled by n/(n−k).
- p-values, intervals and "reliable" tags use Student-t with n−k degrees of freedom instead of the normal distribution.
- Why: with 36-60 months and six regressors, the large-sample method made standard errors about 9% too small. It also used 1.96 where about 2.04 is right.
- Daily regressions are unchanged. They have at least 504 rows, so the difference is negligible, and ticker reports stay identical.
- The change is built in the E0 upload skeleton.

## Sources

- [Next-stage spec](../docs/specs/next-stage-track-record-and-portfolio.md): owner decisions on the track record, and epics E0 and E2.
- [Next-stage research](../docs/research/next-stage-research.md): sections A1, A2, A3, A5 and A6.

## Related decisions

- [Daily returns with robust errors](decision-daily-returns-and-robust-errors.md), amended by this page
- [Factor models and macro](decision-factor-models-and-macro.md)
- [Which betas count as reliable](decision-which-betas-count-as-reliable.md)
- [Portfolio backtest rules](decision-portfolio-backtest-rules.md)
