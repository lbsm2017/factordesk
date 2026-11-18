# Decision: a historical performance block in every report

Date: 2026-11-18
Status: Built and independently validated (2026-11-19); the validator's conditions are met (branch `feat/performance`)

## In one sentence

Every report shows how the stock itself performed over the analysed window: its yearly growth, how much it swings, its Sharpe ratio and its worst fall, next to the factor numbers.

## What we decided

The owner asked (2026-11-18, looking at the headline strip) for the stock's own annualised return, volatility, Sharpe ratio and maximum drawdown. They sit in a new section called Performance, drawn right after the Price panel.

- All four numbers are computed over the analysed sample, the same trading days as the regression. When the date range chips change, the performance numbers change with them.
- **Return a year** is the compound annual growth rate: the growth of one dollar over the window, scaled to a year. The report also gives the total return over the window. The data also holds the simple average of daily returns times 252, because people quote it, but the panel does not show it as a result (see the entry of 2026-11-19).
- **Volatility a year** is the standard deviation of daily returns times the square root of 252.
- **Sharpe ratio** is the average daily return above the risk-free rate (the rate in the Ken French file) divided by its standard deviation, times the square root of 252. It comes with an approximate 95% interval. The panel says only whether the interval includes zero. It never says a Sharpe ratio is "significant".
- **Worst fall** is the largest drop of the compounded return path from a running high, with the peak date, the trough date, the recovery date (or "not recovered") and the days between. A small table lists the five deepest, separate falls (three until 2026-11-19, see the dated entry below).
- The panel says nothing about the future and carries one footnote: "Past performance does not predict future performance."
- If the section cannot be computed (fewer than 60 daily observations, which the 504-row minimum of the report already prevents, or a bad value in the returns) it shows its reason and the report still builds.

## Why

- The factor numbers describe how the stock moves with the market. A reader also asks the plain question "what did this stock do?", and answering it next to the factor numbers avoids a second tool.
- A flat price against a moving risk-free rate would give a huge, meaningless Sharpe ratio, so the ratio is left undefined when the stock's returns do not vary.
- The standard error of the Sharpe ratio uses a textbook closed form (Lo 2002) that assumes independent, identically distributed daily returns. Real returns are not, so the interval is approximate. The field is named `sharpe_se_iid` so nobody mistakes it for a robust standard error.
- The position (after Price, before Exposures) follows the flow of the page: the price panel draws the path of the stock, these four numbers read straight off that path, and the factor panels then explain where the return came from.

## What it costs

- It is a sixth optional section, and the schema contract listed five. The branch edited a few shared files to add one more entry to each list; `docs/validation/performance-contract-note-2026-11-18.md` lists them for the owner to accept. The report format version stays 4: the field is additive, and the contract says feature branches do not bump it.
- The Sharpe ratio here subtracts the risk-free rate, while the rolling Sharpe of the planned factor dashboard (`docs/methodology.md` M12, which describes factor series, not a stock) does not. If both ship, the owner may want one definition.
- A stock with a long history shows a very long window by default (SPY: 8,474 days from 1993). The numbers describe that window and nothing else.

## What we have measured

As of 2026-11-18, on cached SPY and downloaded ZM prices with the cached French factor file (full history, requested end 18 Nov 2026, last factor date 30 Sep 2026). Each number matched an independent plain-pandas calculation to the last digit:

| | SPY, 1 Feb 1993 to 30 Sep 2026 (8,474 days) | ZM, 22 Apr 2019 to 30 Sep 2026 (1,872 days) |
|---|---|---|
| Return a year (compound) | 10.83% | 5.27% |
| Volatility a year | 18.53% | 54.03% |
| Sharpe ratio (95% interval) | 0.52 (0.18 to 0.85) | 0.31 (-0.41 to 1.03) |
| Worst fall | -55.19%, peak 9 Oct 2007, trough 9 Mar 2009, recovered 16 Aug 2012 | -90.27%, peak 19 Oct 2020, trough 12 Aug 2024, not recovered |

## What we have not verified

The React panel is not built; only a placeholder is registered. The methodology text for these definitions is a proposal in the hand-off, not yet in `docs/methodology.md`.

## After validation (2026-11-19)

An independent validator recomputed every number from the hand-off definitions, with its own code, on SPY (full history and five years) and ZM. All of them matched to the last printed digit (review: `docs/reviews/performance-validation-2026-11-19.md`). Four things changed after the review:

- **A price back at its old high now counts as recovered.** The path is a product of thousands of daily ratios, so a price that returned exactly to an earlier high could land a hair below it and the fall was shown as "not recovered". The test now allows a relative difference of one part in a billion, far below any real price move.
- **The panel carries what the dashboard design asks for.** The section now holds a daily drawdown series (the fall from the running peak on every day, rounded to 4 decimals) and lists the five deepest falls instead of three. On SPY from 1993 the series has 8,475 points and adds about 174 kB (35 kB compressed) to a report of about 4.8 MB.
- **The sentence under the numbers no longer quotes the arithmetic average times 252.** For ZM it read +19.5% next to a compound return of +5.3% with no explanation, and a reader could take it for the yearly return. The figure stays in the data. The "How this is computed" fold says that it is higher than the compound figure when returns swing widely, because large swings cut compound growth, and that it is not what an investor earned.
- **The Sharpe and worst-fall notes use the wording of the dashboard spec.** "Return above the factor file's risk-free rate, per unit of volatility", then "Cannot be told apart from zero.", "Above zero at the 5% level." or "Below zero at the 5% level."; the fall note reads "From {peak} to {trough}; back at the peak by {date}" or "not recovered by {end date}".

Still open: the methodology text (proposals P1 to P5 in the hand-off, now with the recovery tolerance), the note on excluded days (review F6), and the React panel.
