# Decision: residual (alpha) analysis with an in-sample and a point-in-time line

Date: 2026-11-18
Status: Implemented on branch `feat/residual-alpha`; not yet independently validated; not merged

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

- The owner's wording "holds up out-of-sample" can still be over-read as a real holdout, which is why the caveat is required. The specification body still uses "survives"; the code keeps "survives" only as an internal verdict name and the user-facing strings say "holds up out-of-sample".
- Using earlier data for the first year loosens the link between the panel and the selected period.
- Compounded lines describe a paper strategy that ignores trading, financing and borrowing costs.
- Built on branch `feat/residual-alpha` on 2026-11-18, not yet validated by an independent check (see "As of commit 4518e38" below).

## As of commit 4518e38 (2026-11-18): built, not yet validated

What is built:
- The calculation (`analytics/residual.py`, `analytics/residual_stability.py`), the report section and its hook, the static HTML panel and the dashboard panel. Both panels print the same headings, row names, survival wording ("100% kept", "more than 200% kept"), notes and caveats, and a test on each side reads one shared wording file.
- 40 oracle tests (TR01 to TR40) plus panel tests. The slow simulation tests were rerun on 2026-11-18 and pass; the measured rates are in `docs/validation/residual-alpha-handoff-2026-11-18.md`.
- The live smoke test (TR40) ran once on the cached SPY series from 2010-01-04. SPY showed no residual return distinguishable from zero in either line (in-sample -0.12% a year, point-in-time -0.22% a year), which is the expected answer for an index fund.

What is not done or not validated:
- Not validated: an independent recomputation without reading the implementation is the next step. Until it is done, treat the numbers as the author's own.
- Owner choice 2 (use data from before a later start date to warm up the first year) is not implemented. A later start date gives fewer point-in-time days, with no footnote about earlier data.
- When neither line differs from zero, the table still shows a survival ratio (for SPY "more than 200% kept"). That figure is a ratio of two numbers near zero and means nothing; a fix is proposed in the handoff.
- Both panels are built and tested on synthetic data plus the one cached SPY series. Nothing else was checked on real tickers, and no AAPL data was cached for the smoke test.

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

## After validation (2026-11-18)

An independent validation recomputed the numbers and found the statistics right. It found five things to fix, now fixed on `feat/residual-alpha` (details in `docs/validation/residual-alpha-handoff-2026-11-18.md`, section 6):

- The verdict now reads the same quality-gated alpha tag as the chip in the table, so a "noise" chip can no longer sit under a verdict that says the alpha is distinguishable from zero.
- If a factor is constant in one half of the period, only the split-half part says it could not be fitted. The rest of the section still builds.
- If the residual panel fails to load or crashes, it shows "This section could not be shown." in its own frame. The rest of the dashboard stays on screen.
- The row "Survival of the alpha ..." is now "Kept with point-in-time betas". When the verdict says the alpha cannot be told apart from zero, the share and kept rows print "n/a, the in-sample alpha is not distinguishable from zero".
- The verdict message and both tables round to the nearest 5 points the same way, halves away from zero.

Superseded: the two bullets above under "What is not done or not validated" that say the section is not validated and that the table still shows a survival ratio for noise. The section has been independently validated (merge with conditions); the survival-ratio problem is fixed and the one open condition is the deferral below. The first bullet under "What it costs us" about "Built ... not yet validated" is also out of date. The older text is kept as it was written.

Still open: owner choice 2 (use earlier data before a later start date) is deferred, 2026-11-18, until the owner confirms it. The validator accepted a merge only with the owner's agreement to that deferral. The owner accepted the edits to shared contract files earlier. The methodology still says "survives", "Survival" and the old verdict rule; the changes above are proposals for it and are not written into `docs/methodology*.md`.
