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
  - The IID standard error of the Sharpe ratio is SE(SR) = sqrt((1 + SR²/2)/T) (Lo 2002, Eqs. 8-9, p. 39; verified, see V1).
- **Minimum Track Record Length (MinTRL; Bailey & López de Prado 2012):**
  - n* = 1 + [1 − γ3·SR + ((γ4 − 1)/4)·SR²]·(z_α/(SR − SR*))².
  - γ4 is raw kurtosis (3 for a Normal), and SR, SR* are per-observation, not annualised. MinTRL is a number of observations (verified, see V1).
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

## D. VaR and CVaR (expected shortfall)

Researched on 2026-11-19. Venues marked **[from memory]** were not re-checked.

### D1. Methods

| Method | Assumptions | Small samples | Adopted |
|---|---|---|---|
| Historical simulation | Stationary; no distribution | Works on daily data. With 36 months, 95% VaR is about the 2nd-worst month and 99% VaR cannot be estimated | Yes |
| Gaussian | Normal returns | Stable at 36 observations, but understates fat or left-skewed tails | Yes |
| Cornish-Fisher (modified) | Close to normal; adds skewness and kurtosis | Usable at 36-120 months, but sample skewness and kurtosis are noisy | Yes, with a validity guard |
| Student-t | Symmetric fat tails | Degrees of freedom poorly identified below about 250 observations | Deferred |
| Filtered historical / GARCH | Volatility clustering | Needs 500-1000+ daily observations; gives a conditional forecast, not a description | Deferred |
| EVT / GPD | Tail above a threshold follows a generalised Pareto | Needs 1000+ daily observations; the threshold choice is subjective | Deferred |

- **Cornish-Fisher:**
  - Zangari (1996), RiskMetrics Monitor Q1 **[from memory]**.
  - Favre & Galeano (2002), *Journal of Alternative Investments* 5(2) **[from memory]**.
  - **Validity domain:** Maillard (2012), "A User's Guide to the Cornish Fisher Expansion", SSRN 1997178.
    - The quantile stops being monotone outside a domain.
    - The expansion's parameters are not the true skewness and kurtosis.
    - Failures are worst at 99%.
    - Take the exact inequality from the paper.
  - **Corrected expansion:** Amédée-Manesme, Barthélémy & Maillard (2019), *Annals of Operations Research* 281, doi:10.1007/s10479-018-2792-4.
- **Modified expected shortfall:** Boudt, Peterson & Croux (2008), *Journal of Risk* 11(2), 79-103. Modified ES can come out below modified VaR, which is why it is floored.
- **Filtered historical simulation:**
  - Hull & White (1998), *Journal of Risk* 1(1) **[from memory]**.
  - Barone-Adesi, Giannopoulos & Vosper (1999), *Journal of Futures Markets* 19(5) **[from memory]**.
- **EVT:** McNeil & Frey (2000), *Journal of Empirical Finance* 7(3-4) **[from memory]**.
- **Estimation noise:** Danielsson & Zhou, "Why risk is so hard to measure" (https://riskresearch.org/papers/DanielssonZhou2017). At small samples, risk forecasts are close to noise, and expected shortfall is noisier than VaR.
- **Sample size:** Yamai & Yoshiba (2002, *Monetary and Economic Studies* 20(1); 2005, *Journal of Banking & Finance* 29). Expected shortfall needs larger samples than VaR to reach the same accuracy, but it does not ignore the tail beyond the quantile.

### D2. Levels and horizons

- **Basel FRTB** (BCBS d352, 2016; d457, 2019) moved from 99% VaR to 97.5% expected shortfall. Under normality the two nearly coincide: 2.326σ versus 2.338σ.
- **Expected tail observations:**

  | Sample | at 99% | at 97.5% |
  |---|---|---|
  | 36 months | 0.4 | 0.9 |
  | 120 months | 1.2 | 3 |
  | 500 days | 5 | 12.5 |

  This is why monthly series also get a 95% row.
- **Square-root-of-time scaling** is valid only for iid, zero-mean returns, so results stay at the series' own frequency.
  - Diebold, Hickman, Inoue & Schuermann (1997), Wharton FIC WP 97-34.
  - Danielsson & Zigrand (2006), *Journal of Banking & Finance* 30(10), 2701-2713.

### D3. Coherence and elicitability

- VaR can fail subadditivity: Artzner, Delbaen, Eber & Heath (1999), *Mathematical Finance* 9(3).
- Expected shortfall is coherent: Acerbi & Tasche (2002), *Journal of Banking & Finance* 26(7).
- Expected shortfall is not elicitable on its own: Gneiting (2011), *JASA* 106(494).
- VaR and expected shortfall are jointly elicitable: Fissler & Ziegel (2016), *Annals of Statistics* 44(4).
- Only expected shortfall gives per-holding contributions that add up cleanly.

### D4. Backtesting (deferred)

- **Tests:** Kupiec (1995), *Journal of Derivatives* 3(2); Christoffersen (1998), *International Economic Review* 39(4); Acerbi & Székely (2014), *Risk*, December.
- **In-sample tests are meaningless:** historical VaR hits its nominal coverage by construction on the sample it was fitted to.
- **A rolling test needs:** a 250-500 day estimation window plus 250-1000 test days. That is impossible on 36-120 monthly observations.

### D5. Per-holding contributions

- **Euler allocation:**
  - Tasche (1999, 2000; arXiv math/0104190).
  - Gourieroux, Laurent & Scaillet (2000), *Journal of Empirical Finance* 7.
  - Hallerbach (2003), *Journal of Risk* 5(2).
  - Scaillet (2004), *Mathematical Finance* 14(1).
- **Per-holding VaR (deferred):** in historical simulation it conditions on a single day, so it is very noisy and needs kernel smoothing.
- **Per-holding CVaR (adopted):** the mean of w_i·r_i over the portfolio's tail days.
  - It sums exactly to the portfolio CVaR.
  - Below about 20 tail days it is anecdotal, so the tool falls back to Gaussian per-holding CVaR.

### D6. Uncertainty

- **Historical VaR:** order-statistic (binomial) intervals, or the asymptotic SE √(p(1−p)/n)/f(q).
- **Expected shortfall:** bootstrap; Chen (2008), *Journal of Financial Econometrics* 6(1).
- **Daily data:** use a stationary block bootstrap (Politis & Romano 1994, *JASA*).
- **What peers show:**
  - PerformanceAnalytics: historical, Gaussian, modified and kernel methods, plus a per-holding option; no intervals.
  - Portfolio Visualizer: 95% historical and analytical VaR plus CVaR, one-month horizon; no intervals.
  - Showing bands goes beyond common practice, and it is the honest answer for short records.

## E. Joint tail behaviour of portfolios (copulas and EVT)

Researched on 2026-11-19 at the owner's request. The input was the owner's [summary of Labovitz (2009)](labovitz-2009-summary.md). Citations marked (nc) were not re-checked; check volume and pages before citing them elsewhere.

### E1. Measuring tail dependence

- **The coefficient of lower tail dependence λ_L is a limit, and it cannot be estimated reliably at our sample sizes.**
  - Nonparametric estimators cannot separate true tail dependence from strong ordinary dependence. Frahm, Junker & Schmidt (2005), "Estimating the tail-dependence coefficient: properties and pitfalls", *Insurance: Mathematics and Economics* 37, 80-100. https://ideas.repec.org/a/eee/insuma/v37y2005i1p80-100.html
  - Estimates depend on the threshold choice. Schmidt & Stadtmüller (2006), *Scandinavian Journal of Statistics* 33(2) (nc).
- **Use the finite-threshold version: χ(u) = P(B in its worst u | A in its worst u).** Coles, Heffernan & Tawn (1999), *Extremes* 2(4) (nc).
  - At u = 5% with about 4,500 daily observations, there are 225 tail days and the standard error is about 0.03. With about 900 weekly observations there are 45 tail weeks and the standard error is about 0.07. Both figures are back-of-envelope.
  - Volatility clustering makes both figures optimistic, so use a block bootstrap.
- **Many equity pairs look asymptotically independent**, so models that assume λ > 0 overstate joint crashes. Poon, Rockinger & Tawn (2004), "Extreme value dependence in financial markets", *Review of Financial Studies* 17(2), 581-610.
- **Exceedance correlation is the weakest option.** It is noisy, and conditioning on large moves changes the correlation even under a constant-correlation normal.
  - Longin & Solnik (2001), "Extreme correlation of international equity markets", *Journal of Finance* 56(2), 649-676.
  - Ang & Chen (2002), *Journal of Financial Economics* 63(3) (nc).
- **Co-exceedance counts are the most robust and the easiest to explain.** Bae, Karolyi & Stulz (2003), *Review of Financial Studies* 16(3) (nc).

### E2. Copulas

- **Gaussian copula:** no tail dependence. It serves as the baseline: "no extra crash clustering beyond correlation".
- **Student-t copula:** adds one parameter ν to the correlation matrix, which sets symmetric tail dependence. Demarta & McNeil (2005), *International Statistical Review* 73(1) (nc).
  - Fitting: ρ = sin(πτ/2) from Kendall's τ, then a one-dimensional profile likelihood for ν, on rank pseudo-observations. Genest, Ghoudi & Rivest (1995), *Biometrika* 82(3) (nc).
  - It needs only scipy and is stable with 500 or more observations for up to 50 holdings.
- **Grouped-t copula:** one ν per asset class, which maps onto the SAA tree. Daul, De Giorgi, Lindskog & McNeil (2003), *RISK* 16(11) (nc). It is the first upgrade to try if a single ν fits poorly.
- **Clayton and Gumbel copulas:** asymmetric, but only bivariate in practice.
- **Vine copulas:** flexible, but 50 holdings need 1,225 pair-copulas, which is opaque and noisy to select. The Python library is pyvinecopulib.
  - Aas, Czado, Frigessi & Bakken (2009), *Insurance: Mathematics and Economics* 44(2) (nc).
  - Brechmann, Czado & Aas (2012), *Canadian Journal of Statistics* 40(1) (nc).
- **Critiques:** correlation does not pin down joint tails, copulas are static, and family choice is arbitrary. This supports Labovitz's complaint, but not his remedy.
  - Embrechts, McNeil & Straumann (2002), "Correlation and dependence in risk management: properties and pitfalls" (nc).
  - Mikosch (2006), "Copulas: tales and facts", *Extremes* 9(1) (nc).

### E3. Extreme-value routes

- **A tail model fitted to the portfolio's own returns already contains the dependence between holdings** for the current weights.
  - Peaks-over-threshold (GPD) on daily losses gives about 225 exceedances.
  - Weekly GEV blocks of 5 days are too small for the asymptotics. Monthly blocks give about 215 minima since 2008.
  - Return levels should stop at about the sample length.
  - Sources: McNeil & Frey (2000) (nc); Coles (2001), *An Introduction to Statistical Modeling of Extreme Values* (nc); Hosking, Wallis & Wood (1985), *Technometrics* 27(3) (nc).
- **Multivariate max-stable models and extremal coefficients** impose asymptotic dependence and treat componentwise maxima as if they were simultaneous. Schlather & Tawn (2003), *Biometrika* 90(1) (nc). Not suited here.
- **Spatial return-level models:** the published form of the latent-Gaussian-process idea is Cooley, Nychka & Naveau (2007), *JASA* 102(479) (nc). The thesis's "Smith et al. (2006)" could not be identified.

### E4. Labovitz (2009) at our scale

- The Gaussian process is a cross-sectional regression of return levels on exchange, sector and market cap, estimated from about 3,000 stocks.
- A 10-50 ETF portfolio has no such cross-section, and the selected model's variance matrices are diagonal, so it delivers no joint structure.
- No journal version, replication or refutation was found. The search was not exhaustive.

### E5. Stress complements

- **Down-market correlation** rises mechanically with volatility, so it needs a caveat. Forbes & Rigobon (2002), "No contagion, only interdependence", *Journal of Finance* 57(5), 2223-2261.
- **A holding's mean return on the portfolio's worst days** is the Marginal Expected Shortfall (MES) idea, applied per holding. Weight-scaled, it equals the planned per-holding CVaR. Acharya, Pedersen, Philippon & Richardson (2017), *Review of Financial Studies* 30(1) (nc).
- **Downside beta:** Ang, Chen & Xing (2006), *Review of Financial Studies* 19(4) (nc).
- **CoVaR** conditions the wrong way for a holdings view. Adrian & Brunnermeier (2016), *American Economic Review* 106(7) (nc). Deferred.

## F. Causal Factor Investing: what applies to factordesk

Researched on 2026-11-19. Primary input: the owner's [study guide](causal_factor_investing_agent_kb.md) of López de Prado (2023), *Causal Factor Investing*, Cambridge Elements, DOI 10.1017/9781009397315 (open access; SSRN 4205613). The guide was checked against the book text. It agreed on every point checked: adjusted R² of 0.784 vs 0.144, F of 9,069 vs 840.8, and the out-of-sample passage in §6.5. Two flags on the guide:

- "Factor mirage" is not in the 2023 book. It comes from the 2025 companion work with Zoonekynd.
- Rule R7 points to Part 4.8 for the hierarchy of evidence, but that hierarchy is in Part 4.6.

### F1. Claims that bear on an attribution tool

- **Factor models are undeclared causal models.** Choosing a specification by fit is a causal error, and the misspecified model can have the higher adjusted R² [B §6.1, §6.4.2.3, §7.3].
- **Type-A errors (noise)** are fixed by multiple-testing corrections such as Benjamini-Hochberg and the deflated Sharpe ratio.
- **Type-B errors (misspecification)** are not fixed by those corrections, and they grow more "significant" with more data [B §6.4].
  - An omitted confounder biases beta, and a shifting covariance can flip its sign. That looks like a time-varying premium [B §6.4.2.1].
  - Controlling for a collider or a mediator biases beta as much as omitting a confounder [B §6.4.2.2].
- **Out-of-sample tests help against type-A errors, not type-B** [B §6.5].

### F2. What does not apply

- **Causal discovery, do-calculus, natural experiments and mechanism analysis** support claims that a factor earns a premium. factordesk makes no such claim; it describes exposures.
- **The deflated Sharpe ratio** corrects a strategy search, and factordesk runs none.

### F3. Decisions (owner, 2026-11-19)

**Adopted**

- **Wording and model notes.**
  - The alpha strip carries a caption: higher R² does not make a model more correct, and alpha is conditional on the model.
  - Use associational language ("co-moved with", never "driven by" or "earned from").
  - Each regression gets a fixed "model note" saying what it assumes and what it omits.
  - The out-of-sample caveat says it "rules out hindsight in the betas, not luck and not a missing factor".
  - Benjamini-Hochberg "reliable" tags must not read as "correctly attributed".
- **Specification curve.** Alpha across model × window × start date, showing the share of specifications where alpha keeps its sign and its reliability tag. No specification is highlighted as best.
- **Minimum Track Record Length** (Bailey & López de Prado 2012; formula verified in V1), in the track-record diagnostics: "this Sharpe ratio needs N months to differ from zero; you have M".

**Declined for now**

- the regressor-overlap warning (subject or holding is a building block of a factor, e.g. IEF/LQD in TERM/DEF)
- the drift alert under both FF5 and FF6
- the analysis-choices card
- the per-report placebo test
- the omitted-variable "what it would take" alpha check

**Follow-up research:** other candidate factors, to be justified by a plausible causal role rather than by fit.

Sources:

- Book: https://www.cambridge.org/core/elements/causal-factor-investing/9AFE270D7099B787B8FD4F4CBADE0C6E
- López de Prado & Zoonekynd (2024), "Why Has Factor Investing Failed?: The Role of Specification Errors", ADIA Lab Research Paper Series No. 7. https://www.adialab.ae/research-series/why-has-factor-investing-failed-the-role-of-specification-errors
- Cinelli & Hazlett (2020), "Making sense of sensitivity", *JRSS B* 82(1), 39-67.

## G. Candidate factors beyond FF6

Researched on 2026-11-19. Each candidate was tested against the causal-discipline rule from section F: add a factor only if it is a plausible cause of the subject's return (the subject holds or trades it), not because it raises fit. Start dates marked [unverified] come from memory.

### G1. Verdicts

| Candidate | Source and terms | Verdict (owner, 2026-11-19) |
|---|---|---|
| Commodities, DBC − RF | ETF via the existing price feed; from 2006-02 | **Adopted** in the macro section. Multi-asset portfolios hold this asset class, and it is nearly orthogonal to FF6. |
| Inflation, TIP − IEI | ETFs; TIP from 2003-12 [unverified], IEI from about 2007-01 [unverified]. FRED T10YIE is a level, not a return. | **Adopted** in the macro section. The book names inflation as an ignored confounder. IEI is duration-matched, unlike IEF. |
| High-yield credit, HYG − LQD | ETFs; HYG from 2007-04 | Not adopted. It is collinear with the market factor and with DEF. |
| Broad USD, FRED DTWEXBGS | Public domain, citation requested | Not adopted. It is the same cause as EUR/USD and must never be entered alongside it. |
| BAB, QMJ (AQR) | AQR terms forbid reproduction or distribution without written consent | Skipped for now; revisit if consent is obtained. They have the strongest confounding case for stocks and equity managers. QMJ would replace RMW, not be added to it. |
| q-factor model (q5) | global-q.org daily CSVs; no stated terms; the URL changes every year | Deferred. It is a rival measurement of the same causes as RMW and CMA, so it would be an alternative model and never stacked on FF5. |
| Short-term reversal, TSMOM, Fung-Hsieh PTFS, ΔVIX | Ken French (ST_Rev); AQR terms (TSMOM); academic-use-only terms (PTFS) | Deferred. These only make sense for managers who trade these strategies, so they would be unlocked by a declared strategy type on uploads. |
| Regional FF5 + Mom (Ken French) | Daily, in USD | The factor set for the future European mode. |
| Long-term reversal, HML Devil, Stambaugh-Yuan M4 | — | Skipped. They fit better but have no distinct mechanism, and M4 data ends in 2016. |

### G2. Sources

- Ken French Data Library. https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html
- AQR Terms of Use. https://www.aqr.com/Terms-of-Use
- AQR datasets. https://www.aqr.com/Insights/Datasets
- Hou, Xue & Zhang (2015), "Digesting anomalies: an investment approach", *Review of Financial Studies* 28(3); q5 factors at https://global-q.org/factors.html
- Frazzini & Pedersen (2014), "Betting against beta", *Journal of Financial Economics* 111(1).
- Asness, Frazzini & Pedersen (2019), "Quality minus junk", *Review of Accounting Studies* 24(1).
- FRED DTWEXBGS. https://fred.stlouisfed.org/series/DTWEXBGS

## Verification results (2026-11-19)

### V1. Sharpe-ratio formulas, checked against the primary texts

- Lo (2002), p. 39, Eqs. 8-9: V_IID = 1 + SR²/2 and SE(SR) = sqrt((1 + SR²/2)/T). Verified.
- Lo (2002), p. 40, Eq. 20: η(q) = q / sqrt(q + 2 Σ_{k=1}^{q−1} (q−k) ρ_k), where ρ_k is the k-th autocorrelation. With all ρ_k = 0 it reduces to Eq. 17, √q. Verified.
- Bailey & López de Prado (2012), Eq. 13. Verified through the authors' own appendix code, because the typeset equation did not extract cleanly:
  - MinTRL = 1 + [1 − γ3·SR + ((γ4 − 1)/4)·SR²]·(Z_α/(SR − SR*))².
  - γ4 is raw kurtosis. With γ3 = 0 and γ4 = 3 the bracket becomes 1 + SR²/2, which matches Lo's Eq. 8.
  - The leading "1 +" comes from a degrees-of-freedom correction, and some secondary sources omit it.
  - Preprint: https://www.davidhbailey.com/dhbpapers/sharpe-frontier.pdf

### V2. Proxy ETF histories

Inception dates come from issuer pages; first-trade dates come from Yahoo's chart API (`firstTradeDate`). EPP and QQQ inception dates are from memory, because their issuer pages did not load.

| Ticker | Inception | Yahoo first day |
|---|---|---|
| EWJ | 1996-03-12 | 1996-03-18 |
| QQQ | 1999-03-10 | 1999-03-10 |
| IVV | 2000-05-15 | 2000-05-19 |
| IEV | 2000-07-25 | 2000-07-28 |
| EZU | 2000-07-25 | 2000-07-31 |
| EPP | 2001-10-25 | 2001-10-26 |
| IEF | 2002-07-22 | 2002-07-30 |
| LQD | 2002-07-22 | 2002-07-30 |
| EEM | 2003-04-07 | 2003-04-14 |
| AGG | 2003-09-22 | 2003-09-29 |
| GLD | 2004-11-18 | 2004-11-18 |
| DBC | 2006-02-03 | 2006-02-06 |
| HYG | 2007-04-04 | 2007-04-11 |
| BWX | 2007-10-02 | 2007-10-11 |
| EMB | 2007-12-17 | 2007-12-19 |
| ACWI | 2008-03-26 | 2008-03-28 |
| IGOV | 2009-01-21 | 2009-01-30 |

Bonds Europe proxy:

- No live US-listed ETF holds only euro-area government bonds. The WisdomTree Euro Debt Fund (EU) closed in February 2015.
- **Recommended: IGOV** (unhedged international treasuries, FTSE WGBI Developed Markets Capped Select).
  - About 41% of it is in euro members within its top 12 countries: France, Italy, Germany, Spain, Austria, Belgium and the Netherlands (issuer page, 2026-11-17).
  - The rest includes Japan, the UK, Korea, Canada and Australia.
  - It keeps EUR exposure, but it is a mixed proxy, and the UI should label it that way.
- BWX starts about 15 months earlier. Its country weights were not published on its issuer page.
- BNDX starts in 2013 and holds corporate bonds as well, so it is not suitable.

The holdings that set the common start date are IGOV (2009-01-30), ACWI (2008-03-28), EMB (2007-12-19) and BWX (2007-10-11).

Sources: https://traders.studentorg.berkeley.edu/papers/The-Statistics-of-Sharpe-Ratios.pdf (DOI 10.2469/faj.v58.n4.2453); issuer pages for each ETF (iShares, State Street, Invesco); https://www.etftrends.com/2015/01/euro-debt-etf-to-close/2/

## Open verification items

1. The Fama & French (1993) TERM/DEF wording.
2. Ken French momentum file header spacing.
3. The current status of capital-gains handling for mutual funds on Yahoo.
