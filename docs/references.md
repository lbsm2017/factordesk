# References

Sources factordesk relies on, and how much weight each carries. URLs were checked on 2026-11-18.

## Source of truth for factor data

**Kenneth R. French Data Library**
<https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html>

Every factor return used by factordesk comes from this library, and its definitions win any
disagreement with another source. Specifically:

- Data file (daily, US, 5 factors plus RF):
  `https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Research_Data_5_Factors_2x3_daily_CSV.zip`
- Factor construction notes (breakpoints, sorts, weighting):
  <https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/Data_Library/f-f_5_factors_2x3.html>

The library is updated about once a month, so the newest factor day trails today's date by
roughly one to two months. factordesk shows this lag in every report. Factor data is downloaded at
run time and is never stored in this repository. Follow the library's own terms of use and credit
Kenneth R. French and Eugene F. Fama when you publish results.

## Academic papers

- Fama, E. F., and French, K. R. (2015). A five-factor asset pricing model. *Journal of Financial
  Economics*, 116(1), 1-22. The model factordesk implements.
- Fama, E. F., and French, K. R. (1993). Common risk factors in the returns on stocks and bonds.
  *Journal of Financial Economics*, 33(1), 3-56. The three-factor model.
- Carhart, M. M. (1997). On persistence in mutual fund performance. *Journal of Finance*, 52(1),
  57-82. Adds momentum, which FF5 does not include.
- Newey, W. K., and West, K. D. (1987). A simple, positive semi-definite, heteroskedasticity and
  autocorrelation consistent covariance matrix. *Econometrica*, 55(3), 703-708. The HAC standard
  errors used for every beta and alpha.
- Benjamini, Y., and Hochberg, Y. (1995). Controlling the false discovery rate. *Journal of the
  Royal Statistical Society B*, 57(1), 289-300. The multiple-testing correction.

## Secondary explainers (orientation only, not authoritative)

**Quantt, "Fama-French model explained"**
<https://www.quantt.co.uk/resources/fama-french-model-explained>

A readable overview of the factors, the regression and the main criticisms. We use it for
plain-language wording and for the list of caveats below. We do not use its numbers as
benchmarks: its premium figures (for example "5-7% per year" for the market) and its R-squared
ranges ("90-95% for portfolios, 30-60% for single stocks") carry no sample period or source.
Where it differs from the library or the papers, the library and papers win.

Points from that page that factordesk handles on purpose:

| Point | What factordesk does |
|---|---|
| Default OLS errors understate uncertainty when returns are autocorrelated or heteroskedastic | Newey-West HAC errors everywhere (`docs/methodology.md`, M0.5) |
| About 120 monthly observations for one stock is a small sample | Daily data, a minimum-sample rule, and explicit "insufficient data" states |
| Annualising by multiplying the intercept (x12 monthly, x252 daily) is arithmetic | The convention is stated in every label (`docs/methodology.md`, M0.4) |
| Loadings drift over time, so a single full-sample beta can mislead | Rolling betas, drift alerts and regime splits |
| Many published "factors" fail out-of-sample (the factor zoo) | In-sample results are labelled as such; the residual analysis adds a point-in-time check |
| FF5 omits momentum, and value's premium has weakened in some periods | Momentum is a planned optional factor; the report never claims a factor "should" pay |
| "Negative beta means defensive" is too loose | The report states the sign and the significance, and does not interpret defensiveness |

## Related tools we studied

See `wiki/` for the dated notes on pyfolio, quantstats, skfolio and the other projects reviewed
while designing factordesk.
