# factordesk overview: method, status, rigour and limitations

Written 2026-11-18. This page holds the detail behind the summaries in the [README](../README.md).
Statements about status are dated and come from [ROADMAP.md](ROADMAP.md) and git; the binding
statistical rules are in [methodology.md](methodology.md), and every number below is quoted from
there or from the documents linked next to it.

## What the report shows

The report has these panels, in this order. Look and wording are in
[design/report-design.md](design/report-design.md).

- **Header and data-quality notice:** the dates used and every caveat that applies (short history,
  price-audit errors, a fired quality gate).
- **Equation and headline numbers:** the fitted model, then alpha, R-squared, residual volatility,
  the number of days and the analysed range.
- **Price:** the daily price line, including the last weeks the factor data does not yet cover.
- **Factor exposures:** each beta with a 95% interval, tagged *reliable* or *noise* after
  correcting for testing five betas at once.
- **Where the return came from:** factor contributions, alpha and residual, adding up to the total.
- **Where the risk comes from:** factor shares of variance and an idiosyncratic share, adding up to 100%.
- **Exposure over time:** rolling betas over 126 and 252 trading days.
- **Data and audit:** what was downloaded and left out, audit findings, caveats, the full regression
  table, then a panel of residual diagnostics.

A synthetic example of an earlier layout (made-up numbers, not real data) is
[samples/mock_report.html](samples/mock_report.html).

## Method in detail

For ticker `i` on day `t`, the model is
`r_i,t - RF_t = alpha + b_mkt (Mkt-RF)_t + b_smb SMB_t + b_hml HML_t + b_rmw RMW_t + b_cma CMA_t + e_t`
(Fama and French 2015), fitted by OLS with an intercept on daily excess returns over the days where
prices and factors overlap ([M3.1](methodology.md#m31-model-and-estimates)). Why daily data and
robust errors: [decision](../wiki/decision-daily-returns-and-robust-errors.md).

- **Inference.** Newey-West HAC standard errors (Bartlett kernel, lag `floor(4 (m/100)^(2/9))` for
  `m` observations), normal p-values
  ([M0.5](methodology.md#m05-inference-ols-with-newey-west-hac)).
- **Multiple testing.** The five betas form one family corrected with Benjamini-Hochberg at 5%.
  Alpha is a single test at 5%, not corrected
  ([M0.6](methodology.md#m06-multiple-testing-benjamini-hochberg),
  [decision](../wiki/decision-which-betas-count-as-reliable.md)).
- **Rolling betas.** Each point uses only the previous 126 or 252 trading days ending on that date
  ([M4](methodology.md#m4-rolling-betas-analyticsrollingpy)).
- **Attribution.** Return contributions are annualised arithmetic means, so contributions, alpha and
  residual sum to the total. Risk contributions are Euler shares of variance, which sum to 100%
  and whose idiosyncratic share is `1 - R-squared`
  ([M6](methodology.md#m6-return-contribution-analyticsattributionpy),
  [decision](../wiki/decision-return-and-risk-attribution.md)).
- **Data-quality gate.** A price audit runs on every ticker. A residual gate fires when the lag-1
  residual autocorrelation is below -0.2 with a robust z below -4, the signature of closing prices
  not synchronous with the factor data. When it fires, the report adds a 5-day-block estimate and
  tags a coefficient *reliable* only if the daily and the 5-day tests both reject
  ([M3.6](methodology.md#m36-residual-quality-gate-non-synchronous-prices-analyticsdiagnosticspy),
  [decision](../wiki/decision-spy-timing-noise-and-the-quality-gate.md)). The thresholds are a
  documented heuristic checked on five S&P 500 products only.

## Method status

As of 2026-11-18, from [ROADMAP.md](ROADMAP.md) and git. "Not merged" means the report has an empty
slot for the section (schema version 4) and no analytics behind it in the code that includes this
page. The dashboard pull request (PR #1) is open and not merged into `dev`.

| Section | Status | Where it stands |
| --- | --- | --- |
| Regression, rolling betas, return and risk attribution, residual diagnostics, quality gate | Built; independently validated on SPY, then hardened | [SPY slice validation](validation/spy-slice-validation.md), [hardening closure](validation/spy-hardening-closure-2026-11-18.md) |
| Dashboard | Built; in review in PR #1, not merged | Tested against a fake backend; smoke-tested on real data for SPY, plus one QQQ request ([review](reviews/real-data-smoke-2026-11-18.md)) |
| Residual alpha analysis | Specified. Not merged | [Specification](methodology-residual-analysis.md); analytics and panels in progress on unmerged feature branches |
| Shrunk betas, Kalman betas | Specified. Not merged | Specifications: [shrunk](specs/shrunk-betas.md), [Kalman](specs/kalman-betas.md); in progress on unmerged feature branches |
| Fragility score, lead-lag betas | Specified. Not merged | Specifications: [fragility](specs/fragility-score.md), [lead-lag](specs/lead-lag-betas.md); no branch yet |
| Dominant-factor shading, drift alerts, regime betas, cointegration | Specified, not built | [Methodology](methodology.md) M8 to M11; drift alerts, regime betas and cointegration are listed as not scheduled; shading is not on the roadmap |
| Regional (European) factors | Specified, not built | [Datasets methodology](methodology-datasets.md) |

## Scientific rigour in practice

The rules are in the [research protocol](research-protocol.md). What each one means, and what the
repository shows today:

- **Hypothesis before results (the rule).** The protocol requires the claim, the null, the exact test
  and the result that would count against it to be written down and entered in the append-only
  [test registry](registry/tests.jsonl) before the first run; every run, including abandoned ones, is
  a registry line. The registry (20 lines on 2026-11-18) records that the quality-gate threshold was
  written after 13 inspection runs, so it is a documented heuristic, not a pre-registered test. The
  protocol applies from now on.
- **Every number carries its sample.** Sample size, first and last date, requested dates, excluded
  rows, factor vintage and status ([CODING_STANDARDS.md](../CODING_STANDARDS.md), section 5); every
  panel is labelled in-sample. A statistic that cannot be computed says so and shows no number.
- **No look-ahead.** A result dated `t` uses only rows dated `t` or earlier. A beta used to explain
  day `t` is the one estimated up to day `t-1`. Static scans and perturbation tests enforce it
  ([M0.2](methodology.md#m02-date-stamping-and-the-no-look-ahead-rule),
  [decision](../wiki/decision-no-look-ahead-rule.md)).
- **Correction and power.** Betas are called significant only after Benjamini-Hochberg correction;
  alpha is a single, uncorrected test at 5%. Appendix B of the protocol gives the minimum
  detectable effect: a single stock's alpha is rarely detectable (about 18% a year at 20% residual
  volatility over 10 years).
- **Independent validation and mutation testing.** A reviewer who did not write the code rebuilt
  the SPY report from raw downloads with separate code; headline numbers matched to about 1e-7.
  The review also injected 17 deliberate bugs: 12 were caught by the tests and 5 survived; the
  tests were then tightened at those boundaries
  ([decision](../wiki/decision-independent-validation-and-mutation-testing.md)).
- **Test oracle.** The tests are specified in a written oracle, with tolerances derived from
  standard errors: [test-oracle.md](test-oracle.md), plus oracles for the
  [datasets](test-oracle-datasets.md) and the [residual analysis](test-oracle-residual-analysis.md).
- **Reproducibility.** Python dependencies are pinned in `uv.lock` and frontend ones in
  `frontend/package-lock.json`; CI installs with `uv sync --locked`. Simulated data uses fixed seeds
  (policy: test `k` uses `numpy.random.default_rng(20261118 + k)`; seed sweeps use seeds 1 to 50),
  never the global generator. Rerun the checks with the commands under
  [Tests and quality checks](../wiki/guide-development.md#tests-and-quality-checks).
- **No citation without verification.** Every source in the bibliography was looked up and checked
  by a script or by hand; what could not be checked is listed as unverified, and claims in the
  repository that have no source are listed in
  [references.md](references.md#claims-in-the-repo-without-a-source)
  ([decision](../wiki/decision-citations-and-verification.md)).

## Limitations

- **Descriptive and in-sample.** Full-sample betas are estimated over the whole window and describe
  that window. They are not forecasts, and no out-of-sample test is built yet.
- **Factor lag.** The French library publishes with a lag of a month or more, so the last weeks of
  prices are charted but left out of the regression.
- **SPY timing noise.** SPY's closing prices from Yahoo before about 2009 carry a transient timing
  error (whether other vendors share it is untested). It lowers SPY's full-sample R-squared to
  0.967; from 2010 it is 0.995. The gate flags it; it does not remove it
  ([validation](validation/spy-slice-validation.md), section 3).
- **US factors only.** The factors are US factors in USD. A non-US ticker still gets a report, with a
  general caveat but no currency check; whether to warn or refuse is an open owner decision (F13 in
  the [hardening closure](validation/spy-hardening-closure-2026-11-18.md)).
- **Survivorship.** The sample is tickers that exist today.
- **Yahoo prices are for personal use**, come from an unofficial route, and the adjusted close can
  differ between two downloads (up to 1.8e-4 seen); the report stores no hash of the price input
  ([decision](../wiki/decision-prices-from-yahoo-with-adjusted-close-care.md)).
- **Thresholds are heuristics.** The gate's false-alarm rate on single stocks is unknown until a
  panel calibration has been run.
- **Some claims have no source.** They are listed with file and line in
  [references.md](references.md#claims-in-the-repo-without-a-source).

## Key references

Full entries, verification notes and the claims that have no source are in
[references.md](references.md) (BibTeX: [references.bib](references.bib)). Verification means the
work exists with these details, not that each paper's text was checked against how the repository
uses it.

1. Fama and French (2015), A five-factor asset pricing model, *J. Financial Economics* 116(1),
   1-22, [doi](https://doi.org/10.1016/j.jfineco.2014.10.010). The model implemented.
2. Fama and French (1993), Common risk factors in the returns on stocks and bonds, *J. Financial
   Economics* 33(1), 3-56, [doi](https://doi.org/10.1016/0304-405X(93)90023-5). The model FF5 extends.
3. French, Kenneth R. French Data Library, Tuck School of Business, Dartmouth College,
   [library page](https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html).
   Source of every factor return.
4. Newey and West (1987), A simple, positive semi-definite, heteroskedasticity and autocorrelation
   consistent covariance matrix, *Econometrica* 55(3), 703-708,
   [doi](https://doi.org/10.2307/1913610). The HAC standard errors.
5. Benjamini and Hochberg (1995), Controlling the false discovery rate: a practical and powerful
   approach to multiple testing, *J. Royal Statistical Society B* 57(1), 289-300,
   [doi](https://doi.org/10.1111/j.2517-6161.1995.tb02031.x). The correction across the five betas.
6. Dimson (1979), Risk measurement when shares are subject to infrequent trading, *J. Financial
   Economics* 7(2), 197-226, [doi](https://doi.org/10.1016/0304-405X(79)90013-8). Lead-lag betas
   (specified, not merged).
7. Scholes and Williams (1977), Estimating betas from nonsynchronous data, *J. Financial Economics*
   5(3), 309-327, [doi](https://doi.org/10.1016/0304-405X(77)90041-1). Lead-lag cross-check
   (specified, not merged).
8. Kalman (1960), A new approach to linear filtering and prediction problems, *J. Basic
   Engineering* 82(1), 35-45, [doi](https://doi.org/10.1115/1.3662552). Kalman betas (specified,
   not merged).
9. Vasicek (1973), A note on using cross-sectional information in Bayesian estimation of security
   betas, *J. Finance* 28(5), 1233-1239, [doi](https://doi.org/10.2307/2978759). Shrunk betas
   (specified, not merged).
10. Engle and Granger (1987), Co-integration and error correction: representation, estimation, and
    testing, *Econometrica* 55(2), 251-276, [doi](https://doi.org/10.2307/1913236).
    Cointegration (specified, not built).
