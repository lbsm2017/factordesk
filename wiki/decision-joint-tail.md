# Decision: joint tail behaviour of portfolios

Date: 2026-11-19
Status: Decided, not yet built

## In one sentence

Portfolio reports get a "crash together" section that shows how often holdings have their worst days at the same time. It uses plain counts plus one Student-t copula, with no extreme-value model in version 1.

## What we decided

- **"Crash together" heatmap:**
  - Each cell answers: when holding A is in its worst 5% of days, how often is holding B too?
  - Each cell is compared with what a normal (Gaussian) model would expect from correlation alone.
  - Rows and columns follow the SAA tree.
- **Co-crash histogram:** on the portfolio's worst 5% of days, how many holdings were also in their own worst 5%. An independence baseline is shown next to it.
- **One Student-t copula:**
  - Its single extra parameter is shown as "joint crash odds versus normal".
  - It is fitted from rank correlations with scipy, so there is no new dependency.
- **Worst-days table:** each holding's average return on the portfolio's worst 5% of days and on the benchmark's worst 5% of days.
- **Data rules:**
  - Daily data, with weekly as a robustness check.
  - Block-bootstrap 90% bands.
  - Cells whose band includes the normal value are greyed out.
  - Needs about 1,000 common days. Below that, the section shows counts only.
- **Not in version 1:**
  - Extreme-value models (GPD, GEV), both here and in the VaR section.
  - Vine copulas.
  - CoVaR.
  - The joint-tail section for uploaded track records.
  - The tail-dependence limit λ as a reported number.
- **Labovitz (2009):** his GEV return-level and Gaussian-process method is parked for a possible future feature on large stock universes, such as a screener.

## Why

- The owner asked how holdings behave together in the tail, not one by one.
- The textbook tail-dependence limit cannot be estimated reliably at about 4,500 days. Many equity pairs show no such dependence in the limit, so models that assume it overstate joint crashes.
- A conditional frequency at 5% can be measured, and a manager can read it directly.
- Copulas are hard to explain beyond two assets, as Labovitz argues. One t copula with one parameter is the exception that stays explainable.
- Labovitz's Gaussian process needs a cross-section of thousands of stocks. A 10-50 ETF portfolio has none, and his selected model is not truly joint.
- The owner chose to keep extreme-value models out of version 1.

## How it works

- Tail days are defined at the 5% level on the common daily calendar of the portfolio's holdings.
- The normal baseline uses a Gaussian copula with the same rank correlations.
- The t copula's correlation comes from Kendall's tau. Its parameter comes from a one-dimensional likelihood search.

## What it costs us

- No "1-in-10-year loss" figure in version 1.
- One t parameter cannot tell asset classes apart. A grouped-t copula (one parameter per asset class) is the first upgrade.
- Short portfolios (under about 1,000 common days) get counts only.

## What would change our mind

- If users ask for loss levels such as "1-in-10-year", peaks-over-threshold on the portfolio's own returns is the researched next step.
- If a single t parameter fits poorly, move to a grouped-t copula.

## Sources

- [Research notes, section E](../docs/research/next-stage-research.md)
- [Labovitz (2009) summary](../docs/research/labovitz-2009-summary.md)
- [Next-stage spec, E8](../docs/specs/next-stage-track-record-and-portfolio.md)
