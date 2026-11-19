# Research notes: track records, portfolio backtests, momentum and macro factors

Date: 2026-11-19
Status: Research input for [the next-stage spec](../specs/next-stage-track-record-and-portfolio.md)

This page summarises three desk-research tracks run on 2026-11-19. Each finding gives the recommendation adopted for factordesk and its sources. Items marked **[unverified]** come from memory or from secondary sources only; they must be checked against the primary text before they are cited in methodology docs or used as test oracles.

---

## A. Evaluating an uploaded track record

### A1. Minimum length and Sharpe-ratio uncertainty

- **Adopted:** monthly uploads need at least 36 months and get a warning under 60. Daily uploads keep the existing 504-observation floor.
- 36 and 60 months are practitioner convention. No paper sets them as a rule. Morningstar's returns-based style analysis asks for 20 to 36 months.
- **Lo (2002), autocorrelation-adjusted annualisation of the Sharpe ratio:**
  - The annualised Sharpe ratio is the per-period Sharpe ratio times η(q).
  - η(q) = q / sqrt(q + 2 Σ_{k=1}^{q−1} (q−k) ρ_k), with q = 12 for monthly data.
  - With all ρ_k = 0 it reduces to √q.
  - Lo reports that ignoring serial correlation can overstate annualised Sharpe ratios by more than 65%.
  - The IID standard error of the Sharpe ratio, sqrt((1 + SR²/2)/T), is **[unverified]**.
- **Minimum Track Record Length (MinTRL; Bailey & López de Prado 2012):**
  - n* = 1 + [1 − γ3·SR + ((γ4 − 1)/4)·SR²]·(z_α/(SR − SR*))².
  - The kurtosis convention (raw or excess) is **[unverified]**.
  - It is an optional later addition. The Deflated Sharpe Ratio is for multiple-testing settings and is not needed for a single record.

Sources:
- Lo, A. (2002). The Statistics of Sharpe Ratios. *Financial Analysts Journal* 58(4), 36-52. https://rpc.cfainstitute.org/research/financial-analysts-journal/2002/the-statistics-of-sharpe-ratios
- Bailey, D. & López de Prado, M. (2012). The Sharpe Ratio Efficient Frontier. *Journal of Risk* 15(2). https://www.risk.net/journal-risk/2223785/sharpe-ratio-efficient-frontier
- Bailey, D. & López de Prado, M. (2014). The Deflated Sharpe Ratio. *Journal of Portfolio Management* 40(5). https://papers.ssrn.com/abstract=2460551
- PerformanceAnalytics `MinTrackRecord` (implementation reference). https://rdrr.io/cran/PerformanceAnalytics/man/MinTrackRecord.html
- Morningstar style-analysis fact sheet. https://advisor.morningstar.com/Principia/pdf/StyleAnalysis_FactSheet.pdf

### A2. Smoothed returns (illiquidity)

- **Adopted:** two checks, and no automatic "unsmoothing".
  1. **Autocorrelation flag:**
     - ρ1 to ρ3 (ρ1 to ρ6 when T ≥ 60) plus a Ljung-Box Q with lags = min(6, T/5), tested at 5%.
     - The flag fires when ρ1 is outside ±1.96/√T or Ljung-Box rejects.
  2. **Dimson summed-lag market beta:**
     - Contemporaneous market return plus 2 lags (monthly) or 5 lags (daily).
     - The report shows the summed beta next to the plain beta.
     - It also shows a Wald test that the lag coefficients are jointly zero.
     - Standard errors are Newey-West.
- Getmansky, Lo & Makarov model reported returns as a moving average of true returns (MA(2) form **[unverified]**). Smoothing biases volatility, beta and correlation down and inflates the Sharpe ratio. Their Ljung-Box lag choice and thresholds were not retrieved.
- Asness, Krail & Liew found much higher market betas for hedge-fund indices once lagged betas were summed, and little remaining alpha. Their result is for aggregate indices, not single funds. The lag count they used is **[unverified]**.

Sources:
- Getmansky, M., Lo, A. & Makarov, I. (2004). An Econometric Model of Serial Correlation and Illiquidity in Hedge Fund Returns. *Journal of Financial Economics* 74(3), 529-609. https://nber.org/papers/w9571
- Asness, C., Krail, R. & Liew, J. (2001). Do Hedge Funds Hedge? *Journal of Portfolio Management* 28(1). https://www.aqr.com/insights/research/journal-article/do-hedge-funds-hedge
- Dimson, E. (1979). Risk Measurement When Shares Are Subject to Infrequent Trading. *Journal of Financial Economics* 7. **[URL not retrieved]**

### A3. Testing alpha

- **Newey-West lag:** the existing rule floor(4·(T/100)^(2/9)) also works for monthly data. It gives 3 lags at T = 36 to 60 and 4 at T = 120. The report states that HAC t-statistics are asymptotic, so they are approximate for 36 to 60 months.
- **Alpha strip:**
  - Shows alpha, t-statistic, R² and adjusted R² for CAPM, FF3, FF5 and FF6, all on the same rows.
  - No model is highlighted as "best".
  - Alpha shrinking as factors are added is the diagnostic.
- **FF6:**
  - FF6 is FF5 plus the Ken French momentum factor.
  - Fama & French (2018) rank the six-factor model first in their comparison.
  - Carhart (1997) introduced momentum as a fourth factor.
- **Significance:** |t| ≥ 2 is a weak bar. Harvey, Liu & Zhu argue for about 3 when selecting among many candidates. This is shown as context, not enforced.
- **Bootstrap:** Kosowski et al. (2006) and Fama & French (2010) bootstrap alphas across many funds (cross-sectional). Neither validates a single-fund bootstrap p-value. Not adopted for v1.

Sources:
- Newey, W. & West, K. (1994). Automatic Lag Selection in Covariance Matrix Estimation. *Review of Economic Studies* 61(4). https://ideas.repec.org/a/oup/restud/v61y1994i4p631-653..html
- Fama, E. & French, K. (2018). Choosing Factors. *Journal of Financial Economics* 128(2), 234-252. https://www.nber.org/papers/w24709.pdf
- Carhart, M. (1997). On Persistence in Mutual Fund Performance. *Journal of Finance* 52(1), 57-82. doi:10.1111/j.1540-6261.1997.tb03808.x
- Kosowski, R., Timmermann, A., Wermers, R. & White, H. (2006). *Journal of Finance* 61(6), 2551-2595. https://econpapers.repec.org/RePEc:bla:jfinan:v:61:y:2006:i:6:p:2551-2595
- Fama, E. & French, K. (2010). Luck versus Skill in the Cross-Section of Mutual Fund Returns. *Journal of Finance* 65(5), 1915-1947. https://econpapers.repec.org/RePEc:bla:jfinan:v:65:y:2010:i:5:p:1915-1947
- Harvey, C., Liu, Y. & Zhu, H. (2016). ...and the Cross-Section of Expected Returns. *Review of Financial Studies* 29(1).

### A4. Hedge-fund factor models and style analysis

- **Fung-Hsieh 7-factor model:**
  - It explains up to 80% of the monthly variation of diversified hedge-fund portfolios.
  - Its trend-following factors catch option-like "alpha" that equity factors miss.
  - Not in v1. A candidate for a later "alternatives" model.
  - The factor files are published on David Hsieh's Duke site, with a long lag **[unverified URL]**.
- **Sharpe (1992) returns-based style analysis:**
  - A constrained regression (weights ≥ 0, summing to 1) on asset-class indices.
  - Its weights are not factor betas, and its intercept is not comparable to alpha.
  - Not in v1. factordesk stays with unconstrained OLS.

Sources:
- Fung, W. & Hsieh, D. (2004). Hedge Fund Benchmarks: A Risk-Based Approach. *Financial Analysts Journal* 60(5), 65-80. https://rpc.cfainstitute.org/research/financial-analysts-journal/2004/hedge-fund-benchmarks-a-risk-based-approach
- Sharpe, W. (1992). Asset Allocation: Management Style and Performance Measurement. *Journal of Portfolio Management*, Winter, 7-19. https://web.stanford.edu/~wfsharpe/art/sa/sa.htm

### A5. Upload data quality and fees

- **Fee basis:** the gross/net flag is required and shown on every output. Net alpha is what the investor received; gross alpha is skill before fees. A record never mixes the two.
- **Converting NAV to returns:** r_t = NAV_t / NAV_{t−1} − 1. This is only valid for a total-return or distribution-adjusted NAV per unit.
  - The first row only provides the base value.
  - A gap makes the next change a multi-period return, so gaps are refused.
- **Checks:**
  - duplicate dates or dates out of order (refused);
  - calendar gaps (refused);
  - values that look like percent instead of decimal (auto-detected);
  - outliers (|r| > 5 standard deviations, or a monthly return outside about −50% to +100%; thresholds are our choice);
  - share of exactly-zero or repeated returns (stale or smoothed data);
  - large moves followed by an exact reversal.
- **Self-reported records may be backfilled.** Database studies estimate backfill bias at roughly 0.4% to 1.4% a year (secondary sources). These figures are not applied, but the report says the bias exists.
- **GIPS** requires time-weighted returns and monthly valuation. A model fee is deducted monthly in its examples.

Sources:
- GIPS Standards (September 2024 document). https://www.gipsstandards.org/wp-content/uploads/2024/09/september2024.pdf
- Fung, W. & Hsieh, D. (2000). *Journal of Financial and Quantitative Analysis* 35(3), 291-307 (backfill and survivorship estimates) **[unverified]**.

### A6. Benchmark-relative statistics (default benchmark: ACWI)

- **Tracking error:** the standard deviation of the fund return minus the benchmark return, annualised by √12 (monthly) or √252 (daily).
- **Information ratio:** annualised mean active return divided by tracking error. It uses arithmetic annualisation, and the report states that convention.
- **Up/down capture (Morningstar convention):**
  - The compound fund return over the months when the benchmark rose (or fell), divided by the compound benchmark return over the same months.
  - Uses monthly data only.
  - Needs at least 12 up months and 12 down months.
- **Overlap only:** all benchmark statistics use only the period the two series share. The ACWI ETF starts in March 2008.

Sources:
- Morningstar, "What are upside and downside capture ratios?" https://global.morningstar.com/en-ca/personal-finance/what-are-upside-and-downside-capture-ratios

---

## B. Backtesting a fixed-weight portfolio

### B1. Daily mechanics

- **Portfolio return:** r_p,t = Σ_i w_i,t−1 · r_i,t. Cash is a holding that earns the French daily risk-free rate (which is published in percent, so divide by 100).
- **Drift:** w_i,t = w_i,t−1 (1 + r_i,t) / (1 + r_p,t). Weights are renormalised so they sum to 1 at every step.
- **Rebalance:**
  - Weights are reset to target at the close of the last trading day of each month in the common calendar.
  - The reset affects returns from the next day, so there is no look-ahead.
  - The last, partial month does not rebalance.
- **Turnover and cost:**
  - One-way turnover = ½ Σ |w_target − w_drifted|.
  - Cost = turnover × bps, charged on rebalance days only and reported on its own line.
  - Whether the initial purchase is charged must be stated.
- **Timing luck:** practitioner studies show that rebalance-day choice can matter for concentrated portfolios. The convention is stated in the report.

Sources:
- Boyd, S. et al. (2017). Multi-Period Trading via Convex Optimization. https://arxiv.org/pdf/1705.00109
- Ken French Data Library (RF definition). https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html

### B2. Total-return data from Yahoo

- **Adjusted Close:** use it with `auto_adjust=False`, which the project already does. Take one fresh download per run. Never splice cached and fresh Adjusted Close, because history is back-adjusted every time a new dividend arrives.
- **Known Yahoo errors** (listed in the yfinance price-repair docs):
  - unadjusted dividends;
  - wrong or duplicate dividends;
  - unadjusted splits;
  - capital gains counted twice for funds.
- **Mutual funds:** capital-gain distributions may not be reflected reliably **[unverified]**.
- **Cross-checks:**
  - Reuse audit A6 (CRSP-style distribution check) with a 1% discrepancy threshold.
  - Reuse audit A4, which already flags |r| > 40% per day.
- **Reproducibility:** record the yfinance version and the download time.

Sources:
- yfinance, Price Repair. https://ranaroussi.github.io/yfinance/advanced/price_repair.html
- Vanguard, Mutual funds and ETFs: understanding capital gains. https://corporate.vanguard.com/content/corporatesite/us/en/corp/articles/mutual-funds-and-etfs-understanding-capital-gains.html

### B3. Survivorship bias

- **Adopted:** a fixed warning on every portfolio report. The magnitude is not estimated, because the user has already picked surviving tickers.
- **Suggested wording:** "Holdings are currently listed securities. Past delisted, merged or liquidated peers are excluded, which tends to overstate historical returns, more so for small caps, long histories and concentrated portfolios."

Sources:
- Brown, S., Goetzmann, W., Ibbotson, R. & Ross, S. (1992). Survivorship Bias in Performance Studies. *Review of Financial Studies* 5(4), 553-580. https://ideas.repec.org/a/oup/rfinst/v5y1992i4p553-80.html
- Elton, E., Gruber, M. & Blake, C. (1996). Survivorship Bias and Mutual Fund Performance. *Review of Financial Studies* 9(4), 1097-1120. https://ideas.repec.org/a/oup/rfinst/v9y1996i4p1097-1120.html
- Shumway, T. (1997). The Delisting Bias in CRSP Data. *Journal of Finance* 52(1), 327-340. https://ideas.repec.org/a/bla/jfinan/v52y1997i1p327-40.html

### B4. Return contribution per holding over many days

- **Adopted:** recursive (Frongello-style) linking.
  - Daily contribution: c_i,t = w_i,t−1 · r_i,t.
  - Period contribution: C_i = Σ_t c_i,t · (1 + R_{t−1}), where R_{t−1} is the portfolio's cumulative return up to the previous day.
  - Then Σ_i C_i = Π_t (1 + r_p,t) − 1 exactly.
  - Cash and the cost line are rows of their own.
  - A unit test asserts the sum.
- **Rejected alternatives:**
  - Summing daily contributions does not compound.
  - Initial-weight buy-and-hold contributions ignore rebalancing.
  - Cariño or Menchero coefficients add complexity for no gain when there is no benchmark.

Sources:
- Frongello, A. (2002). Linking Single Period Attribution Results. *Journal of Performance Measurement* 6(3).
- Cariño, D. (1999). Combining Attribution Effects Over Time. *Journal of Performance Measurement*, Spring.
- Menchero, J. (2004). Multiperiod Arithmetic Attribution. *Financial Analysts Journal* 60(4), 76-91. https://ideas.repec.org/a/taf/ufajxx/v60y2004i4p76-91.html

### B5. Risk contribution per holding

- **Adopted:** ex-post share of realised variance, share_i = Cov(c_i,t, r_p,t) / Var(r_p,t).
  - It sums to 100% and includes cash.
  - It uses the actual drifted weights.
  - It needs no covariance-matrix estimate.
- **Later option:** the forward-looking Euler version RC_i = w_i (Σw)_i / σ_p with Ledoit-Wolf shrinkage. It needs a choice of weight vector and is not in v1.

Sources:
- Bruder, B. & Roncalli, T. (2012). Managing Risk Exposures Using the Risk Budgeting Approach. MPRA 37246. https://mpra.ub.uni-muenchen.de/37246/1/MPRA_paper_37246.pdf
- Maillard, S., Roncalli, T. & Teïletche, J. (2010). The Properties of Equally Weighted Risk Contribution Portfolios. *Journal of Portfolio Management* 36(4).
- Ledoit, O. & Wolf, M. (2004). Honey, I Shrunk the Sample Covariance Matrix. *Journal of Portfolio Management*. https://econ-papers.upf.edu/papers/691.pdf

### B6. Holdings with different histories

- **Adopted:** the backtest runs only on dates where every holding has prices. It starts at the first such date and ends at the last. The report names the holdings that set the start and the end.
- **Rejected:**
  - Backfilling with proxies, which invents history.
  - Re-spreading weights while some holdings are missing, which mixes different portfolios in one regression.
- **Warning:** a short window is flagged, because short windows give wide error bands on factor betas.

### B7. Rebalancing frequency (context only)

- No "rebalancing premium" is claimed. The literature finds that its sign is theoretically ambiguous and that no frequency is optimal.

Sources:
- Bouchey, P., Nemtchinov, V., Paulsen, A. & Stein, D. (2012). Volatility Harvesting. *Journal of Wealth Management* 15(2), 26-35.
- Hallerbach, W. (2014). Disentangling Rebalancing Return. Summary: https://www.robeco.com/files/docm/docu-is-rebalancing-the-source-of-factor-premiums-february-2015.pdf
- Zilbering, Y., Jaconetti, C. & Kinniry, F. (2015). Best Practices for Portfolio Rebalancing. Vanguard.

---

## C. Momentum, macro factors and prior art

### C1. Momentum (FF6)

- **Files:**
  - daily: `ftp/F-F_Momentum_Factor_daily_CSV.zip`, from 1926-11-03;
  - monthly: `ftp/F-F_Momentum_Factor_CSV.zip`, from January 1927.
- **Construction:**
  - Six value-weight portfolios formed on size and prior (2-12) return.
  - Size is split at the NYSE median; prior return is split at the NYSE 30th and 70th percentiles.
  - Mom = ½(Small High + Big High) − ½(Small Low + Big Low).
- **Use:** Mom is a long-short spread, so RF is never subtracted from it. Parse the column header defensively. The library calls it "Mom", not "UMD".

Sources:
- Ken French, Momentum Factor (daily). https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/Data_Library/det_mom_factor_daily.html
- Fama & French (2018); Carhart (1997), as in A3.

### C2. Rates and credit factors

- **Adopted:**
  - TERM = IEF total return − RF.
  - DEF = LQD total return − IEF total return.
  - Both start on 2002-07-30, the first Yahoo trade date for each.
- **DEF is not duration-matched:**
  - LQD's effective duration (about 7.6 years) is longer than IEF's (about 7.0 years), so DEF keeps some rate exposure. It is labelled "credit minus rates, not duration-matched".
  - A duration-adjusted variant, LQD − (D_LQD/D_IEF)·IEF, is a later option.
- These factors follow the definitions of TERM and DEF in Fama & French (1993) **[definitions from memory, verify against the text]**.

Sources:
- Fama, E. & French, K. (1993). Common Risk Factors in the Returns on Stocks and Bonds. *Journal of Financial Economics* 33(1), 3-56.
- iShares LQD and IEF product pages (effective duration).
- MSCI, "Did corporate credit factors offer a risk-return edge?" https://www.msci.com/research-and-insights/blog-post/did-corporate-credit-factors-offer-a-risk-return-edge

### C3. EUR/USD factor

- **Adopted:** the simple daily spot return of FRED DEXUSEU (USD per EUR). In the file, "." means missing. The yfinance `EURUSD=X` series is the fallback; its history starts only on 2003-12-01.
  - This is spot only, without the interest-rate carry, and it is labelled "euro exposure".
- **Timing:** DEXUSEU is a noon New York rate, while equities close at 4 pm. Same-day daily regressions therefore show false lead/lag effects.
  - The daily macro regression adds FX_{t−1} and reports the summed FX beta, with SE = sqrt(v00 + v11 + 2·v01).
  - Monthly regressions compound each leg to month-end.
- **Later alternative:** a multi-currency dollar factor, as in Lustig, Roussanov & Verdelhan (2011).

Sources:
- FRED, DEXUSEU. https://fred.stlouisfed.org/series/DEXUSEU
- Federal Reserve H.10 release notes. https://www.federalreserve.gov/releases/h10/about.htm
- Lustig, H., Roussanov, N. & Verdelhan, A. (2011). Common Risk Factors in Currency Markets. *Review of Financial Studies* 24(11), 3731-3777. https://papers.ssrn.com/abstract=1159046

### C4. Regression design for the macro section

- **Adopted:**
  - A separate regression with raw betas, Newey-West errors, and correlations plus VIF (reusing the existing collinearity code).
  - No orthogonalisation in v1.
  - Venn residualises factors in documented tiers. That is a later option, and if adopted the order must be stated.

### C5. Prior art

| | Venn (Two Sigma) | Portfolio Visualizer | Morningstar / MSCI Barra |
|---|---|---|---|
| Inputs | Uploaded return streams, portfolios | Tickers, portfolios of up to 10 assets | Fund returns or holdings |
| Factor sets | 18 macro and style factors, residualised in tiers | CAPM to FF5, Carhart, q-factor, QMJ, BAB, Term and Credit, custom | Style indices or Fama-French (Morningstar); proprietary (Barra) |
| Frequency | Detected on upload | Mostly monthly; the tool page and FAQ disagree on daily support | Monthly, 20 to 36 months minimum |
| Uncertainty | Share of return explained, residual | Newey-West available | Accuracy caveats stated |
| Worth copying | Upload wizard that detects price vs return, percent vs decimal, frequency; stated residualisation order | Rolling windows; custom factors | Explicit minimum history |
| Worth avoiding | Hidden ordering effects | 10-asset cap; ambiguous frequency claims | — |

Morningstar's own research found holdings-based style analysis more stable than returns-based. factordesk stays returns-based by choice and says so.

Sources:
- Two Sigma, Introducing the Two Sigma Factor Lens. https://www.twosigma.com/articles/introducing-the-two-sigma-factor-lens/
- Venn help: Uploading returns. https://help.venn.twosigma.com/en/articles/4277742-uploading-returns
- Portfolio Visualizer, Factor Analysis and FAQ. https://www.portfoliovisualizer.com/factor-analysis, https://www.portfoliovisualizer.com/faq

---

## Open verification items

1. The Lo (2002) SE formula and the MinTRL kurtosis convention: check against the primary text.
2. The Fama & French (1993) TERM/DEF wording.
3. Ken French momentum file header spacing.
4. ETF inception and history for the default proxy table, and a Bonds Europe proxy (see the spec).
5. The current status of capital-gains handling for mutual funds on Yahoo.
