# Decision: portfolio backtest rules

Date: 2026-11-19
Status: Decided

## In one sentence

A model portfolio is backtested with weights reset to target at each month-end and drifting in between, with a cost line, cash earning the French risk-free rate, a common start and end date, a survivorship warning, and a returns-based breakdown of contribution and risk for each holding.

## What we decided

- The backtest starts from fixed target weights. It rebalances back to target at the close of the last trading day of each month.
- Weights drift between rebalances. They are renormalised to sum to 1 at every step.
- An optional cost in basis points is charged on rebalance days only. It shows on its own line.
- Cash is a holding. It earns the French daily risk-free rate, which is published in percent, so we divide by 100.
- Weight that is not allocated goes to the Cash row when the user runs the backtest. The report shows a notice.
- The backtest runs on a common calendar, from the first date when every holding has prices to the last such date. The report names the holdings that set each end.
- Every backtest carries a survivorship warning.
- Analysis is returns-based only. Holdings-based betas are deferred.

## Why

- Contributions must add up. We use recursive (Frongello-style) linking, so holding contributions sum exactly to the portfolio's compounded return. Summing daily contributions would not compound. Buy-and-hold from initial weights would ignore rebalancing.
- A month-end rebalance changes returns only from the next day, so there is no look-ahead.
- We do not backfill missing history with proxies, because that invents history. We also do not re-spread weights while a holding is missing, because that would mix different portfolios in one regression.
- Survivorship bias tends to overstate historical returns. We cannot estimate its size, because the user has already picked surviving tickers. So we warn every time instead of quoting a number.
- No "rebalancing premium" is claimed. The literature finds its sign ambiguous. We state the convention and stop there.

## How it works

- Portfolio return: r_p,t = sum of w_i,t-1 × r_i,t.
- Drift: w_i,t = w_i,t-1 × (1 + r_i,t) / (1 + r_p,t).
- One-way turnover = half the sum of |target - drifted|. Cost = turnover × bps, on rebalance days only.
- The last, partial month does not rebalance.
- Contribution: c_i,t = w_i,t-1 × r_i,t, and C_i = sum over t of c_i,t × (1 + R_t-1), where R is the cumulative portfolio return up to the previous day. The C_i sum to the compounded return within 1e-12. A unit test checks this.
- Risk share: share_i = Cov(c_i,t, r_p,t) / Var(r_p,t). Shares sum to 100%, include cash, and use drifted weights. No covariance matrix is estimated.
- Each node of the tree shows target weight, drifted weight, contribution and risk share. Group totals equal the sum of their leaves.
- Prices come from one fresh Yahoo download per run, with adjusted close taken from the raw bars. Cached and fresh adjusted closes are never spliced.
- Survivorship wording: "Holdings are currently listed securities. Past delisted, merged or liquidated peers are excluded, which tends to overstate historical returns, more so for small caps, long histories and concentrated portfolios."

## What it costs us

- Cost is one basis-point figure. It cannot model spreads or taxes.
- Our sources do not fix whether the first purchase is charged. The report must state which convention it uses.
- The common calendar can shorten the test for the whole portfolio. A short window is flagged, because it gives wide error bands on factor betas.
- Risk shares are ex-post. They describe what happened, not what will happen. The forward-looking version is deferred.
- Contributions use no benchmark, so there is no benchmark-relative attribution.
- Yahoo adjusted closes have known errors, such as unadjusted dividends and splits. Capital-gain handling for mutual funds is unverified.

## What would change our mind

- If users need holdings-based betas, that deferred item comes in.
- If users need forward-looking risk, we add the Euler version with Ledoit-Wolf shrinkage.
- If users want a benchmark-relative view, we add the Carino or Menchero linking.
- If the Yahoo checks find errors above the 1% threshold, we revisit the price source.

## Sources

- [Next-stage spec](../docs/specs/next-stage-track-record-and-portfolio.md): owner decisions on the portfolio, and epics E5 and E6.
- [Next-stage research](../docs/research/next-stage-research.md): sections B1 to B7.

## Related decisions

- [SAA tree and proxies](decision-saa-tree-and-proxies.md)
- [Track-record uploads](decision-monthly-track-records.md)
- [Return and risk attribution](decision-return-and-risk-attribution.md)
- [Prices from Yahoo, with adjusted-close care](decision-prices-from-yahoo-with-adjusted-close-care.md)
