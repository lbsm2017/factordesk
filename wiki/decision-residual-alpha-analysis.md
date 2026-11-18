# Decision: residual (alpha) analysis with an in-sample and a point-in-time line

Date: 2026-11-18
Status: Decided-pending-implementation

## In one sentence

We will show what a stock returned beyond its factor exposures as two lines side by side, one using betas fitted with hindsight and one using only earlier data, and say plainly that the second rules out hindsight in the betas but not luck.

## What we decided

- A "Residual return" panel shows a table, a chart of two cumulative lines, a verdict sentence, a stability section and diagnostics. No forecasts and no benchmark comparison (owner decisions).
- Owner's four choices, recorded 2026-11-18:
  1. The chart opens on both lines from the same starting point; a toggle shows the full-period in-sample line.
  2. If the user picks a later start date, the first year of point-in-time betas may use earlier data, with a footnote saying so.
  3. The "mostly disappears" warning appears only in the residual panel, not in the headline strip.
  4. User-facing text says "holds up out-of-sample" instead of "survives".

"Holds up out-of-sample" refers to point-in-time betas (no hindsight in the betas), not to a true holdout sample, and the panel caveat says so.

## Why

A static-beta residual line always drifts by the regression alpha, because the betas were fitted on those same days, so a line ending above zero proves little. We rejected showing only the in-sample line because it looks like skill by construction. We rejected calling the point-in-time line a validation because it shares the same days and shocks; in 1,000 simulated zero-alpha stocks, 5.0% looked reliable in-sample and 3.2% also held up point-in-time. We rejected tunable verdict thresholds because they invite tuning until the verdict says what one hoped.

## How it works

- In-sample residual: excess return minus factor effects using full-period betas. Its average equals alpha exactly.
- Point-in-time residual: each day uses betas from the previous 252 days (the existing beta window; no new setting). Rows before that are warm-up.
- Both lines start at zero on the same date and cover the same days. A verdict rule compares them (for example, "mostly disappears" if less than half of the in-sample alpha is kept).
- Example of noise: with 19% residual volatility over 10 years, alpha has a standard error of about 6% a year, so about 62% of zero-alpha stocks show an alpha above 3% in size.

## What it costs us

- The owner's wording "holds up out-of-sample" can still be over-read as a real holdout, which is why the caveat is required. The specification body still uses "survives" and "holds up with point-in-time betas"; strings must be updated.
- Using earlier data for the first year loosens the link between the panel and the selected period.
- Compounded lines describe a paper strategy that ignores trading, financing and borrowing costs.
- Not implemented as of 2026-11-18; schema and label changes are still to be made.

## What would change our mind

A real holdout design (such as walk-forward scoring), which the specification defers; evidence that readers take the chart as proof of skill; or a verdict that rarely fires.

## Sources

- [docs/methodology-residual-analysis.md](../docs/methodology-residual-analysis.md), sections R0 to R5, R9 and "Owner decisions (2026-11-18)".
- [docs/test-oracle-residual-analysis.md](../docs/test-oracle-residual-analysis.md), TR19 to TR22.
- [docs/methodology.md](../docs/methodology.md), M6.3.

## Related decisions

- [No look-ahead rule](decision-no-look-ahead-rule.md)
- [Which betas count as reliable](decision-which-betas-count-as-reliable.md)
- [Return and risk attribution](decision-return-and-risk-attribution.md)
