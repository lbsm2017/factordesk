# Glossary

Plain-English definitions of the terms used in factordesk. Each entry links to the decision page where the term matters. Examples use round numbers for illustration, not real data, unless a date is given.

## Returns and data

**Excess return.** A return minus what a risk-free investment earned over the same period. Example: a stock gains 1.00% on a day when the risk-free rate is 0.01%, so its excess return is 0.99%. See [daily returns and robust errors](decision-daily-returns-and-robust-errors.md).

**Risk-free rate.** What a very safe investment (here the US one-month Treasury bill) earns. The library publishes it as a daily figure rounded to 0.01%, which adds a little noise to alpha. Example: 0.01% a day is about 2.5% a year. See [factor data source](decision-factor-data-source-french-library.md).

**Total return and adjusted close.** Total return counts price change plus dividends. Yahoo's "adjusted close" rewrites past prices so that price changes include dividends and splits. Example: close 100 then 101 with a 1.00 dividend gives an adjusted return of 2.02%, not 1.00%. See [prices from Yahoo](decision-prices-from-yahoo-with-adjusted-close-care.md).

**The Ken French Data Library.** A public website run by Kenneth R. French that publishes the factor returns used by academics. We treat it as the source of truth for factor definitions. Example: its US daily 5-factor file begins on 1963-07-01. See [factor data source](decision-factor-data-source-french-library.md).

**Survivorship bias.** Analysing only companies that still exist makes results look better than reality, because failures are missing. Example: studying today's index members ignores the ones that went bankrupt. See [prices from Yahoo](decision-prices-from-yahoo-with-adjusted-close-care.md).

## The five factors

A **factor** is a return series that stands for a common source of risk or reward, built from many stocks. Example: "size" is the return of small companies minus big ones. See [factor data source](decision-factor-data-source-french-library.md).

**Market (Mkt-RF).** The return of all US-listed stocks minus the risk-free rate. A beta of 1.0 means the stock moves about one-for-one with the market. See [return and risk attribution](decision-return-and-risk-attribution.md).

**Size (SMB, small minus big).** Return of small companies minus big companies. A negative beta, as for SPY (about -0.15 on 2026-11-18), means the stock behaves like large companies. See [which betas count as reliable](decision-which-betas-count-as-reliable.md).

**Value (HML, high minus low).** Return of cheap stocks (high book value relative to price) minus expensive ones. Example: a positive beta leans towards value stocks. See [which betas count as reliable](decision-which-betas-count-as-reliable.md).

**Profitability (RMW, robust minus weak).** Return of firms with strong operating profits minus those with weak profits. See [return and risk attribution](decision-return-and-risk-attribution.md).

**Investment (CMA, conservative minus aggressive).** Return of firms that invest cautiously minus those that expand fast. See [return and risk attribution](decision-return-and-risk-attribution.md).

## The regression

**Beta.** How strongly a stock moves with a factor. Example: a market beta of 1.2 means a 1% market gain goes with about a 1.2% gain in the stock, other things equal. See [which betas count as reliable](decision-which-betas-count-as-reliable.md).

**Alpha.** The average return left after removing what the factors explain. Example: SPY's alpha was -0.58% a year (z -2.24, borderline significant) in the 2026-11-18 report. See [SPY timing noise](decision-spy-timing-noise-and-the-quality-gate.md) and [residual alpha analysis](decision-residual-alpha-analysis.md).

**Residual.** The part of a day's return the factors do not explain. Example: factors imply +0.80% and the stock gained +1.10%, so the residual is +0.30%. See [residual alpha analysis](decision-residual-alpha-analysis.md).

**R-squared.** The share of a stock's day-to-day variation that the factors explain, from 0 to 1. Example: 0.95 means 95% explained and 5% left to stock-specific moves. See [SPY timing noise](decision-spy-timing-noise-and-the-quality-gate.md).

**t-statistic and p-value.** The t-statistic measures how many standard errors an estimate is from zero; the p-value is the chance of seeing something that extreme if the true value were zero. Example: a t-statistic of 2 gives p of about 0.05. We use robust statistics that are close cousins of t (called z). See [which betas count as reliable](decision-which-betas-count-as-reliable.md).

**HAC (Newey-West) errors.** Standard errors that allow for returns being correlated or volatile in clusters across days. Example: the SPY alpha has z = -1.00 with plain errors and -2.24 with Newey-West errors. See [daily returns and robust errors](decision-daily-returns-and-robust-errors.md).

**Benjamini-Hochberg correction.** A method for testing several things at once while keeping the share of false positives low. Example: five betas are tested together, so the smallest p-value must beat 0.01, not 0.05. See [which betas count as reliable](decision-which-betas-count-as-reliable.md).

## Time and testing

**In-sample versus out-of-sample.** In-sample means judged on the same data used to fit the model; out-of-sample means judged on data the fit never saw. Example: betas fitted on 2015 to 2025 and graded on 2015 to 2025 are in-sample. See [residual alpha analysis](decision-residual-alpha-analysis.md).

**Point-in-time.** Each day's number uses only information available by then. In this project it also means we hold one version of the library's data. Example: a beta for 10 March uses days up to 9 March. See [no look-ahead rule](decision-no-look-ahead-rule.md).

**Look-ahead bias.** Letting future information leak into a past result, which flatters it. Example: smoothing a chart with a window centred on each day uses tomorrow's data. See [no look-ahead rule](decision-no-look-ahead-rule.md).

**Rolling window.** An estimate recomputed each day from the latest fixed number of days. Example: a 252-day window on day 300 uses days 49 to 300. See [no look-ahead rule](decision-no-look-ahead-rule.md).

## Risk and long-run links

**Euler risk contribution.** A way to split total variance among the factors and a leftover part so the shares add to 100%. Example: market 98.4%, others small, idiosyncratic 3.3% (SPY, 2026-11-18). See [return and risk attribution](decision-return-and-risk-attribution.md).

**Cointegration.** Two series that can wander but stay tied together over the long run. Example: two similar stocks whose price gap keeps returning to a typical level. See [cointegration design](decision-cointegration-design.md).

**Half-life.** The time it takes a gap to close halfway. Example: a gap that shrinks 5% a day has a half-life of about 13.5 trading days. See [cointegration design](decision-cointegration-design.md).
