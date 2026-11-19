# Executive summary: Labovitz (2009)

**Using Return Level in a Statistical Model for the Joint Distribution of the Extreme Values of Equities**
Mark L. Labovitz, PhD thesis, Mathematical and Statistical Sciences, University of Colorado Denver (advisor: Stephan R. Sain), 2009. 308 PDF pages.

> Status: first-pass summary, supplied by the owner on 2026-11-19. It was built from the abstract, Chapters 2–7 and the data chapter. Chapter 1 (literature) and Appendix B (covariate-model detail) were only skimmed. Section references (§) are to the thesis. Input to [research notes, section E](next-stage-research.md).

---

## 1. Problem and thesis in one paragraph

Investors care about the **downside tail** of returns, and about the **joint** tail behaviour of a portfolio rather than of single stocks. Copulas are the usual tool for joining univariate extreme-value models. Labovitz argues they are non-unique, poorly understood beyond two dimensions, and hard to explain to non-technical managers (§1.13.1).

His alternative has three steps:

1. Fit a **time-varying Generalized Extreme Value (GEV) distribution** to each stock.
2. Convert each fit into a **return level**: the loss exceeded on average once every N weeks.
3. Model the *cross-section of return levels* as a **Gaussian process** driven by market cap, exchange and sector.

The method is adapted from Smith et al. (2006), who modelled extreme precipitation across the US. The uncertainty in the return levels (the "nugget" variance) is then fed into mean-variance optimisation as an extra risk term.

## 2. The four hypotheses and what the thesis shows for each

| # | Hypothesis | Result claimed | Where |
|---|---|---|---|
| 1 | GEV distributions describe downside returns | Weekly block minima fit a GEV adequately; block-size scaling (from weeks to longer blocks) behaves as theory predicts | §4.1, §4.4 |
| 2 | GEV parameters are time-varying functions of financial indicators | 95% of per-stock time-varying models significantly beat the static GEV; models average about 7 covariates | §4.8 |
| 3 | Joint extreme behaviour can be modelled through return levels instead of a copula | Return levels fit a Gaussian process with 158 parameters on 20,678 stock-years; residual diagnostics acceptable; holdout test passed | Ch. 5, §6.4 |
| 4 | Functions of return levels improve portfolio construction | Adding long-horizon nugget covariances to MVO raised backtested returns by roughly 100% to about 400% over 2001–2007 | §6.5, §6.6 |

## 3. Method pipeline

1. **Data.**
   - Daily data, January 2000 to August 2007.
   - 76,424 common stocks on 95 exchanges, filtered down to **12,185**. The filters were completeness, length, dead equities and a new liquidity test.
   - A stratified random sample of **3,000** stocks for training and **100** for testing (98 usable).
   - 139 candidate economic and market covariates, reduced to **44** with a patent-pending factor-analytic "high-grading" method (§3.7.1).
2. **Extreme series.**
   - Weekly block *minima* of daily returns, sign-flipped so that maxima theory applies.
   - Weeks were chosen over months or peaks-over-threshold because they give more observations and converged faster.
3. **Time-varying GEV.**
   - μ, σ and ξ are each linear in the covariates.
   - Each of the 44 covariates was expanded into 6 versions (minimum or maximum within the block × 0, 1 or 2-week lead). Together with trend and constant this gives **266 candidates**.
   - Model selection is per stock: forward/backward stepwise under BIC, with a likelihood-ratio stopping rule.
   - Optimisation used Nelder-Mead, then BFGS. The fitting took about 90 processors for 10 days (§4.7).
4. **Return levels and nugget variance.** Time-varying return levels are solved by bisection (Smith et al. 2006). Their variance comes from the delta method using the inverse Hessian (§5.3–5.4).
5. **Gaussian process on log return levels.**
   - Mean: fixed effects for exchange (69 levels), sector (20), market-cap class, year, continuous cap and cap × year, for 103 parameters.
   - Variance: a year × cap-class term (35 parameters) plus the nugget multiplied by a sector factor (20 parameters) (§5.9).
6. **Portfolios.**
   - Nugget covariances at 7 return levels (about 1, 2, 4, 26, 52, 156 and 313 weeks) are *added* to the ordinary covariance.
   - The result feeds long-only MVO on about 200 high-graded candidates per year.
   - Each frontier has about 600 portfolios (518 to 589 after cleaning).
   - The tangency (Sharpe) portfolio, with a 0% risk-free rate, is compared across 8 risk models (§6.5).

## 4. Key findings

**Tail dynamics (Ch. 4)**

- Trigonometric and seasonal covariates add nothing once constant and trend are included.
- Financial covariates are as important as the constant or the trend.
  - Lagged covariates make up 53.4% of selected terms; coincident ones make up 46.6%.
  - The block *minimum* of a covariate is selected more often than the block maximum (62.1% vs 37.9%).
- The author reads the GEV parameters as driven mainly by leading global equity indices, then by long-term sovereign and investment-grade corporate rates (§7.3).
- Model complexity rises with market cap.
- The Pacific Rim and Western Europe need more complex models than Africa, Eastern Europe, the Middle East and South America.

**Cross-sectional model (Ch. 5–6)**

- A three-factor fixed-effects model (exchange, sector, market value) gives an annual R² of 0.83 to 0.90 on log return levels. Heteroscedasticity forced the richer final model.
- On the 98-stock holdout (686 stock-years), the training coefficients predicted the log 52-week return level well, with Scheffé prediction intervals.
- The training and test residual distributions were statistically indistinguishable (§6.4).

**Portfolios (Ch. 6)**

- Risk models using nuggets at **26 weeks or longer beat conventional MVO**.
- Shorter horizons (4 weeks or less) did **not**. The author attributes this to short-horizon nuggets adding no information beyond the ordinary covariance.
- Invest-and-hold:
  - Every structure at 26 weeks or longer matched or beat the base.
  - The 156-week structure is the visual outlier in Fig. 6.6: roughly 17x, against 5–6x for the base, read off the chart.
- Annual rebalance (Fig. 6.8), with no transaction costs:
  - Best structure each year: **$34.70 per $1**.
  - Base: **$12.40**.
  - Worst structure each year: just under **$9**.
- The winning horizon changes by year (Table 6.3: 156, 313, 26, 156, *base*, 156 weeks for 2002–2007).
- Using last year's VIX returns to pick the structure gave the best or second-best choice in about half the years (§6.6).

## 5. Claimed contributions (§7.4)

- Data on a global scale.
- Return levels as the device for joint tail dependence.
- A full time-varying EVT application in finance.
- A liquidity filter, now used at Thomson Reuters.
- The patent-pending dimension-reduction method.
- A new factor model for joint tail behaviour.
- An MVO variant using the nugget covariance.
- A signal idea for choosing among covariance structures.

## 6. Critical assessment

These are the summary author's own observations, not the thesis author's. Items marked (verify) need a closer check against the text.

1. **The "joint distribution" is not really joint.**
   - In the selected model, both variance matrices H and Σ′ are **diagonal** and uncorrelated with each other (§5.9).
   - Dependence between stocks enters only through shared fixed effects in the mean.
   - The portfolio step then borrows ordinary return correlations to fill the off-diagonals (§6.5).
   - So the thesis does not show that return levels replace a copula, and it has no head-to-head test against one.
2. **The headline outperformance rests on one 7-year path.**
   - One market regime (2001–2007, ending before the 2008 crisis) and one start date.
   - No confidence intervals, no transaction costs, long-only, and a 0% risk-free rate.
   - The winning horizon is unstable across years, and in 2006 the base model won.
3. **The "best strategy" figures use hindsight.**
   - The $34.70 vs $12.40 comparison picks the best covariance structure each year after the fact.
   - The only attempt at a usable signal (lagged VIX) worked about half the time.
   - A realistic implementation would land somewhere between the base and the best.
4. **The abstract's ">300%" is not stated consistently.**
   - The abstract says ">300%". §6.1 says "between 100 percent and nearly 400 percent". Fig. 6.8 gives about 2.8x terminal wealth for best vs base (+180%).
   - The text has no table of the invest-and-hold numbers. The >300% appears to be the single best structure (156 weeks) read from Fig. 6.6.
   - It is not a typical result across horizons.
5. **Survivorship bias risk.**
   - The sample was filtered for completeness and **dead equities** (§7.2).
   - Removing delisted stocks flatters any 2000–2007 backtest, and tail-risk estimates most of all.
   - (verify) How this was handled in the test set and in the portfolio candidate pool.
6. **Long-horizon nuggets are extrapolations.**
   - A 156- or 313-week return level is estimated from about 400 weeks of data per stock, so the nugget there is mostly model uncertainty.
   - That it improves MVO is an empirical finding with only an after-the-fact explanation.
7. **Selection inference.** The thesis uses stepwise selection over 266 candidates per parameter, then reports that 95% of models "significantly" beat the static GEV. This overstates the evidence, because a likelihood-ratio test after selection is optimistic. Using BIC as a co-stopping rule helps.
8. **Weekly blocks of 5 daily observations** are small for GEV asymptotics. The author checked this by simulation and block-size scaling (§4.4), but it is worth revisiting.
9. **Stochastic covariates are treated as fixed.** The Smith et al. return-level formulas assume deterministic covariates. The thesis acknowledges this in footnotes in Ch. 4–5 and argues that re-estimating at each rebalance makes it tolerable.
10. **Validation scope.**
    - The holdout tests the *mean* model and the residual distribution. It does not test tail dependence or joint exceedances, which is what the title promises.
    - The high R² is plausibly dominated by the 69 exchange indicators. This is an interpretation and was not tested.
11. **Unfinished goals.**
    - The "financial weather" propagation model (original goal 4, §2.2) was not delivered.
    - The spatial and temporal covariance extension gave null or confusing results (§7.5).
12. **Small inconsistencies.**
    - The abstract says 3,000 stocks were "randomly selected". The body describes a stratified sample from the 12,185 liquid names, with 2,954 in the final model.
    - The test set is given as both 100 and 98.
    - Table 4.9 counts stopping at up to 12 or more coefficients, against a stated cap of 11 steps.

## Reference parameters

| Item | Value |
|---|---|
| Period | January 2000 to August 2007; model years 2001–2007 |
| Universe → liquid → training / test | 76,424 → 12,185 → 3,000 / 100 (98 usable) |
| Final GP sample | 20,678 stock-years (2,954 stocks × 7 years) |
| Covariates | 139 → 44 → 266 candidates per GEV parameter |
| Return levels (weeks) | 1.0526, 2, 4, 26.071, 52.142, 156.42, 312.85 |
| Exceedance probabilities | 0.95, 0.50, 0.25, 0.0383, 0.0192, 0.0064, 0.0032 |
| GP parameters | 103 (mean) + 55 (variance: 35 + 20) = 158 |
| Compute | about 90 processors, about 10 days |
| Portfolio candidates | about 3,000 reduced to about 200 per year |
