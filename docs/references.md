# References

Sources factordesk relies on, and how much weight each carries. URLs were checked on 2026-11-18.

The rule for this file: no citation without verification. Every work listed below was looked up
in a primary or authoritative source on 2026-11-18, and the bibliographic data (authors, year,
title, venue, volume, pages, DOI) come from that lookup, not from memory. Anything the repository
states that we could not check is listed under [Unverified citations](#unverified-citations), with
exactly what the repository says and what is missing. The same entries are in
[`references.bib`](references.bib), one key per work (for example `fama2015`), so a document can
cite by key. [How the checks were done](#how-the-checks-were-done) says how to repeat them.

## How to read this file

Sources carry different weight, and the file keeps them apart.

| Weight | What it is | What it can support |
|---|---|---|
| Primary literature | Journal articles, working papers and books, checked by DOI or stable URL | Method claims: why an estimator, test or correction is used |
| Data provider | The provider's own data files, documentation and terms of use | Definitions of the data, update timing, what use is allowed |
| Secondary documentation | Explainers, package documentation, project READMEs and search summaries | Orientation and wording only; never a number or a method claim on its own |

Verification covers bibliographic data only: that the work exists, who wrote it, where and when it
appeared. It does not mean we have read the full text or that the work says what a spec attributes
to it. Where a spec quotes a result, the quotation is cited to the spec section, and the spec's own
evidence marker (`[V]` verified, `[U]` unverified) is kept.

Summary on 2026-11-18: 63 entries in `references.bib` (58 checked by script against Crossref or
arXiv, 5 checked by hand) and 1 press release checked by hand. Of the 11 items first listed as
unverified, 4 are resolved with a source, 2 are partly resolved and 5 still have no source; see
[Unverified citations](#unverified-citations) and
[Claims in the repo without a source](#claims-in-the-repo-without-a-source).

## Data sources and licences

| Provider | Terms of use | What factordesk uses it for | Status |
|---|---|---|---|
| Kenneth R. French Data Library | No terms page found; the page carries the notice "Copyright Eugene F. Fama and Kenneth R. French" ([library page](https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html)) | Every factor return and the risk-free rate; downloaded at run time, never stored in the repository | Used |
| Yahoo Finance, through yfinance 1.8.0 | [Yahoo terms of service](https://legal.yahoo.com/us/en/yahoo/terms/otos/index.html); [yfinance README](https://raw.githubusercontent.com/ranaroussi/yfinance/main/README.md) | Daily prices (`Close`, `Adj Close`, dividends, splits) for the analysed ticker; downloaded at run time, never stored in the repository | Used |
| Tiingo | [Terms of use](https://www.tiingo.com/tos/) ("Last Updated Date: November 5th, 2026"); [pricing page](https://www.tiingo.com/about/pricing) | Candidate cross-check source, studied in `data-source-comparison.md` | Not used |
| Alpaca Markets | [Terms and conditions (PDF)](https://files.alpaca.markets/disclosures/alpaca_terms_and_conditions.pdf); [redistribution note](https://alpaca.markets/support/redistribute-alpaca-api) | Research comparison only (the owner's own key, aggregate statistics only); the planned adapter is not built | Not used in the product |
| ECB euro reference rates | [ECB page](https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/index.en.html) | Proposed currency conversion for European tickers (`methodology-datasets.md`, D9.3); not implemented | Not used |
| Yahoo help, "What is the adjusted close?" | [SLN28256](https://help.yahoo.com/kb/SLN28256.html) | Yahoo's own definition of `Adj Close` and its split and dividend multipliers; the basis of the adjusted-close audit (`methodology.md` M1.4) | Documentation only |
| Yahoo help, "Yahoo Finance Market Coverage and Data Delays" | [SLN2310](https://help.yahoo.com/kb/SLN2310.html) | Ticker suffix, exchange and country table behind the region rule (`methodology-datasets.md`, D7) | Documentation only |

What the provider texts say, as read on 2026-11-18 (quotations, not an interpretation of rights; the
project's wider comparison is in [`data-source-comparison.md`](data-source-comparison.md), section 6):

- yfinance README: "yfinance is **not** affiliated, endorsed, or vetted by Yahoo, Inc. It's an
  open-source tool that uses Yahoo's publicly available APIs, and is intended for research and
  educational purposes", and "the Yahoo! finance API is intended for personal use only". Quotations
  re-checked in the page text on 2026-11-18.
- Yahoo terms: "you may not access or reuse the Services, or any portion thereof, for any commercial
  purpose", and a ban on collecting data "using any automated means" without permission. Re-checked
  in the page text on 2026-11-18. Yahoo remains the default price source with that disclosure
  (`data-source-comparison.md`, section 7).
- Tiingo and Alpaca: the quotations in `data-source-comparison.md` section 6 were taken by the
  project's own review; we re-checked only that the cited URLs answer (HTTP 200) and that the Tiingo
  terms still carry the date above. We did not re-read the Alpaca PDF.
- Yahoo help, "What is the adjusted close?" (<https://help.yahoo.com/kb/SLN28256.html>, HTTP 200, text read
  2026-11-18): "Adjusted close is the closing price after adjustments for all applicable splits and
  dividend distributions. Data is adjusted using appropriate split and dividend multipliers,
  adhering to Center for Research in Security Prices (CRSP) standards." and "Dividend multipliers
  are calculated based on dividend as a percentage of the price, primarily to avoid negative
  historical pricing. For example: If a $0.08 cash dividend is distributed on Feb 19 (ex- date),
  and the Feb 18 closing price is $24.96, the pre-dividend data is multiplied by (1-0.08/24.96) =
  0.9968." This is the multiplier `1 - Dist_t / C_{t-1}` that `methodology.md` M1.4 A6 uses. The
  words "CRSP standards" rest on Yahoo's statement; we did not consult a CRSP document.
- yfinance 1.8.0 documentation of `Ticker.history`, read in the installed package: `auto_adjust`
  "Adjust all OHLC automatically? Default: True"; `repair` "Fixes price errors in Yahoo data: 100x,
  missing, bad dividend adjust. Default: False". factordesk calls it with `auto_adjust=False` and
  `repair=False` (`backend/factordesk/data/prices.py`). Documentation:
  <https://ranaroussi.github.io/yfinance/> (HTTP 200).

### Source of truth for factor data

**Kenneth R. French Data Library**
<https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html>

Every factor return used by factordesk comes from this library, and its definitions win any
disagreement with another source. Specifically:

- Data file (daily, US, 5 factors plus RF):
  `https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Research_Data_5_Factors_2x3_daily_CSV.zip`
  (HTTP 200 on 2026-11-18)
- Factor construction notes (breakpoints, sorts, weighting):
  <https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/Data_Library/f-f_5_factors_2x3.html>
  (HTTP 200 on 2026-11-18). That page points to Fama and French (1993) and to "Fama and French,
  2014, A Five-Factor Asset Pricing Model" for a complete description of the factor returns
  ([R1](#r1), [R2](#r2); the journal version is dated 2015).

The library is updated about once a month, so the newest factor day trails today's date by
roughly one to two months. factordesk shows this lag in every report. Factor data is downloaded at
run time and is never stored in this repository. We credit Kenneth R. French and Eugene F. Fama
when we publish results.

What the site says about use and credit, read on 2026-11-18. We searched the home page
(<https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/>), the library page
(<https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html>), the 5-factor
description page (`Data_Library/f-f_5_factors_2x3.html`), `Data_Library/details_main.html`, the
consulting and contact pages, and the daily 5-factor file inside the zip, for wording on terms of
use, licence, permission, redistribution, citation or credit. We found none. The notices that
exist are, word for word:

- Library page, bottom: "Copyright Eugene F. Fama and Kenneth R. French".
- Home page: "Kenneth R. French: Copyright Kenneth R. French".
- Data file, first line: "This file was created by using the 202609 CRSP database." Last line:
  "Copyright 2026 Eugene F. Fama and Kenneth R. French".
- 5-factor description page: "See Fama and French, 1993, "Common Risk Factors in the Returns on
  Stocks and Bonds," Journal of Financial Economics, and Fama and French, 2014, "A Five-Factor
  Asset Pricing Model" for a complete description of the factor returns." This points readers to
  the papers; it is not worded as a request to cite.
- Details page for developed-market factors: "The returns in this section are updated versions of
  those used in Eugene F. Fama and Kenneth R. French (2012) "Size, Value, and Momentum in
  International Stock Returns", Journal of Fincancial Economics ." (spelling as on the page).

So the factor data are copyrighted by Fama and French, are built from the CRSP database, and the
site states no terms of use and no citation request. Our practice follows from that: download at run
time, never store or redistribute the data, and credit Fama and French as a courtesy and an
academic norm. Earlier versions of this file, and three wiki pages, say the library "asks" users to
follow its terms and to credit its authors; that is not what the pages say. CRSP's own terms were not
checked. See [Claims in the repo without a source](#claims-in-the-repo-without-a-source), item C4.

## Academic papers

The five works the project cites most often. Full entries, with pages and DOIs, are in
[Method references](#method-references).

- Fama, E. F., and French, K. R. (2015). A five-factor asset pricing model. *Journal of Financial
  Economics*, 116(1), 1-22. The model factordesk implements. [R2](#r2)
- Fama, E. F., and French, K. R. (1993). Common risk factors in the returns on stocks and bonds.
  *Journal of Financial Economics*, 33(1), 3-56. The three-factor model. [R1](#r1)
- Carhart, M. M. (1997). On persistence in mutual fund performance. *Journal of Finance*, 52(1),
  57-82. Adds momentum, which FF5 does not include. [R3](#r3)
- Newey, W. K., and West, K. D. (1987). A simple, positive semi-definite, heteroskedasticity and
  autocorrelation consistent covariance matrix. *Econometrica*, 55(3), 703-708. The HAC standard
  errors used for every beta and alpha. [R7](#r7)
- Benjamini, Y., and Hochberg, Y. (1995). Controlling the false discovery rate. *Journal of the
  Royal Statistical Society B*, 57(1), 289-300. The multiple-testing correction. [R12](#r12)

## Method references

How to read an entry. The line under each reference gives what factordesk uses it for, where in
the repository it is used (file and section), how the repository cites it (`full` citation in the
repository, `author-year` only, `name only` for a method named with no citation), and how it was
verified on 2026-11-18. "Crossref" means the record at `https://api.crossref.org/works/<doi>`;
"RePEc" means the IDEAS/RePEc record, used where Crossref gives only a start page. The BibTeX key
is in brackets. Spec section labels (M0.5, LL1, KB6.1) are the labels used inside the files.

### Factor model

<a id="r1"></a>**R1.** Fama, E. F., and French, K. R. (1993). Common risk factors in the returns on
stocks and bonds. *Journal of Financial Economics*, 33(1), 3-56.
doi:[10.1016/0304-405X(93)90023-5](https://doi.org/10.1016/0304-405X(93)90023-5). [`fama1993`]
- Used for: the three-factor model (market, size, value) that FF5 extends; the library's factor
  description cites it. Used in: [`PLAN.md`](PLAN.md) (Regression); this file. Repo cites: full.
  Verified 2026-11-18, Crossref.

<a id="r2"></a>**R2.** Fama, E. F., and French, K. R. (2015). A five-factor asset pricing model.
*Journal of Financial Economics*, 116(1), 1-22.
doi:[10.1016/j.jfineco.2014.10.010](https://doi.org/10.1016/j.jfineco.2014.10.010). [`fama2015`]
- Used for: the model factordesk implements (Mkt-RF, SMB, HML, RMW, CMA). Used in:
  [`methodology.md`](methodology.md) M3.1; [`PLAN.md`](PLAN.md). Repo cites: full. Verified
  2026-11-18, Crossref (issued 2015) and OpenAlex (which dates it 2014, the online date). The
  library page cites it as 2014.

<a id="r3"></a>**R3.** Carhart, M. M. (1997). On persistence in mutual fund performance. *The Journal
of Finance*, 52(1), 57-82.
doi:[10.1111/j.1540-6261.1997.tb03808.x](https://doi.org/10.1111/j.1540-6261.1997.tb03808.x).
[`carhart1997`]
- Used for: the momentum factor, a planned optional addition (not in v1). Used in:
  [`methodology-datasets.md`](methodology-datasets.md) D15; [`PLAN.md`](PLAN.md) ("Next"). Repo
  cites: full. Verified 2026-11-18, Crossref.

<a id="r4"></a>**R4.** Fama, E. F., and French, K. R. (2012). Size, value, and momentum in
international stock returns. *Journal of Financial Economics*, 105(3), 457-472.
doi:[10.1016/j.jfineco.2012.05.011](https://doi.org/10.1016/j.jfineco.2012.05.011). [`fama2012`]
- Used for: choosing regional factor files for non-US tickers; target RT5 of the research protocol.
  Used in: [`methodology-datasets.md`](methodology-datasets.md) D8.1;
  [`research-protocol.md`](research-protocol.md) RT5;
  [`wiki/decision-european-mode-and-currency.md`](../wiki/decision-european-mode-and-currency.md).
  Repo cites: full. Verified 2026-11-18, Crossref. The repo's quoted abstract was not re-checked.

<a id="r5"></a>**R5.** Fama, E. F., and French, K. R. (2017). International tests of a five-factor
asset pricing model. *Journal of Financial Economics*, 123(3), 441-463.
doi:[10.1016/j.jfineco.2016.11.004](https://doi.org/10.1016/j.jfineco.2016.11.004). [`fama2017`]
- Used for: as R4; target RT4. Used in: [`methodology-datasets.md`](methodology-datasets.md) D8.1;
  [`research-protocol.md`](research-protocol.md) RT4. Repo cites: full. Verified 2026-11-18,
  Crossref. The tables are not accessible to us (item U4).

<a id="r6"></a>**R6.** Griffin, J. M. (2002). Are the Fama and French factors global or country
specific? *The Review of Financial Studies*, 15(3), 783-803.
doi:[10.1093/rfs/15.3.783](https://doi.org/10.1093/rfs/15.3.783). [`griffin2002`]
- Used for: the decision to prefer regional factors for a regional ticker. Used in:
  [`methodology-datasets.md`](methodology-datasets.md) D8.1. Repo cites: full. Verified 2026-11-18,
  Crossref.

### Regression and HAC inference

<a id="r7"></a>**R7.** Newey, W. K., and West, K. D. (1987). A simple, positive semi-definite,
heteroskedasticity and autocorrelation consistent covariance matrix. *Econometrica*, 55(3),
703-708. doi:[10.2307/1913610](https://doi.org/10.2307/1913610). [`newey1987`]
- Used for: Bartlett-kernel HAC standard errors for every beta and alpha. Used in:
  [`methodology.md`](methodology.md) M0.5, D2;
  [`wiki/decision-daily-returns-and-robust-errors.md`](../wiki/decision-daily-returns-and-robust-errors.md).
  Repo cites: full. Verified 2026-11-18, Crossref (start page 703) and RePEc (pages 703-708).

<a id="r8"></a>**R8.** Newey, W. K., and West, K. D. (1994). Automatic lag selection in covariance
matrix estimation. *The Review of Economic Studies*, 61(4), 631-653.
doi:[10.2307/2297912](https://doi.org/10.2307/2297912). [`newey1994`]
- Used for: the lag rule `L(m) = floor(4 (m/100)^(2/9))`, which `skill-review.md` (finding 20)
  attributes to this paper. Used in: [`methodology.md`](methodology.md) M0.5;
  [`skill-review.md`](skill-review.md). Repo cites: author-year. Verified 2026-11-18, Crossref,
  OpenAlex and RePEc. We did not read the paper, so the attribution of that exact rule is item U5.

<a id="r9"></a>**R9.** White, H. (1980). A heteroskedasticity-consistent covariance matrix estimator
and a direct test for heteroskedasticity. *Econometrica*, 48(4), 817-838.
doi:[10.2307/1912934](https://doi.org/10.2307/1912934). [`white1980`]
- Used for: the HC0 covariance in the robust Breusch-Godfrey autocorrelation test. Used in:
  [`methodology.md`](methodology.md) M3.5. Repo cites: name only ("HC0"). Verified 2026-11-18,
  Crossref (start page 817) and RePEc (pages 817-838).

<a id="r10"></a>**R10.** Hodrick, R. J. (1992). Dividend yields and expected stock returns:
alternative procedures for inference and measurement. *The Review of Financial Studies*, 5(3),
357-386. doi:[10.1093/rfs/5.3.351](https://doi.org/10.1093/rfs/5.3.351). [`hodrick1992`]
- Used for: the reason not to use overlapping 5-day sums with HAC (over-rejection in finite
  samples). Used in: [`methodology.md`](methodology.md) M3.6. Repo cites: author-year. Verified
  2026-11-18, Crossref and RePEc. The DOI suffix reads 351 while the page range is 357-386; both
  are as registered.

<a id="r11"></a>**R11.** Britten-Jones, M., Neuberger, A., and Nolte, I. (2011). Improved inference
in regression with overlapping observations. *Journal of Business Finance & Accounting*,
38(5-6), 657-683.
doi:[10.1111/j.1468-5957.2011.02244.x](https://doi.org/10.1111/j.1468-5957.2011.02244.x).
[`brittenjones2011`]
- Used for: as R10. Used in: [`methodology.md`](methodology.md) M3.6. Repo cites: author-year.
  Verified 2026-11-18, Crossref.

### Multiple testing

<a id="r12"></a>**R12.** Benjamini, Y., and Hochberg, Y. (1995). Controlling the false discovery rate:
a practical and powerful approach to multiple testing. *Journal of the Royal Statistical Society:
Series B (Methodological)*, 57(1), 289-300.
doi:[10.1111/j.2517-6161.1995.tb02031.x](https://doi.org/10.1111/j.2517-6161.1995.tb02031.x).
[`benjamini1995`]
- Used for: the false-discovery-rate correction applied within each family of tests. Used in:
  [`methodology.md`](methodology.md) M0.6;
  [`methodology-residual-analysis.md`](methodology-residual-analysis.md) R5.2;
  [`wiki/decision-which-betas-count-as-reliable.md`](../wiki/decision-which-betas-count-as-reliable.md).
  Repo cites: full. Verified 2026-11-18, Crossref.

### Other tests named in the research protocol

<a id="r61"></a>**R61.** Wilcoxon, F. (1945). Individual comparisons by ranking methods. *Biometrics
Bulletin*, 1(6), 80. doi:[10.2307/3001968](https://doi.org/10.2307/3001968). [`wilcoxon1945`]
- Used for: the Wilcoxon signed-rank test named in the research protocol. Used in:
  [`research-protocol.md`](research-protocol.md) (registry example). Repo cites: name only.
  Verified 2026-11-18, Crossref and OpenAlex give start page 80 and no end page; JSTOR answered with a
  client challenge, which we did not work around, so the page range is incomplete.

### Rolling and time-varying betas, Kalman filter

<a id="r13"></a>**R13.** Kalman, R. E. (1960). A new approach to linear filtering and prediction
problems. *Journal of Basic Engineering*, 82(1), 35-45.
doi:[10.1115/1.3662552](https://doi.org/10.1115/1.3662552). [`kalman1960`]
- Used for: the filter behind the Kalman betas. Used in:
  [`specs/kalman-betas.md`](specs/kalman-betas.md) KB0.1, KB1. Repo cites: name only ("Kalman
  filter"). Verified 2026-11-18, Crossref.

<a id="r14"></a>**R14.** Rauch, H. E., Tung, F., and Striebel, C. T. (1965). Maximum likelihood
estimates of linear dynamic systems. *AIAA Journal*, 3(8), 1445-1450.
doi:[10.2514/3.3166](https://doi.org/10.2514/3.3166). [`rauch1965`]
- Used for: the smoother offered only as a labelled retrospective view. Used in:
  [`specs/kalman-betas.md`](specs/kalman-betas.md) KB4.2. Repo cites: name only ("Rauch-Tung-Striebel
  smoother"). Verified 2026-11-18, Crossref.

<a id="r15"></a>**R15.** Durbin, J., and Koopman, S. J. (2012). *Time Series Analysis by State Space
Methods* (2nd ed.). Oxford University Press.
doi:[10.1093/acprof:oso/9780199641178.001.0001](https://doi.org/10.1093/acprof:oso/9780199641178.001.0001).
[`durbin2012`]
- Used for: the standard reference for the filter, the exact diffuse initialisation and the
  smoother. Used in: [`specs/kalman-betas.md`](specs/kalman-betas.md) ("Sources checked"). Repo
  cites: full, marked "not re-checked in this session". Verified 2026-11-18, Crossref (monograph
  record, 2012, Oxford University Press).

<a id="r16"></a>**R16.** Masreliez, C., and Martin, R. (1977). Robust Bayesian estimation for the
linear model and robustifying the Kalman filter. *IEEE Transactions on Automatic Control*, 22(3),
361-371. doi:[10.1109/TAC.1977.1101538](https://doi.org/10.1109/TAC.1977.1101538).
[`masreliez1977`]
- Used for: the Student-t weighted update variant, which the spec calls "in that spirit" and not
  their estimator. Used in: [`specs/kalman-betas.md`](specs/kalman-betas.md) KB6.1. Repo cites:
  author-year. Verified 2026-11-18, Crossref. The spec read only the record and abstract.

<a id="r17"></a>**R17.** Diebold, F. X., and Mariano, R. S. (1995). Comparing predictive accuracy.
*Journal of Business & Economic Statistics*, 13(3), 253-263.
doi:[10.1080/07350015.1995.10524599](https://doi.org/10.1080/07350015.1995.10524599).
[`diebold1995`]
- Used for: the test of equal squared prediction error between Kalman and rolling betas (with a HAC
  variance). Used in: [`specs/kalman-betas.md`](specs/kalman-betas.md) KB7.2. Repo cites: name only
  ("Diebold-Mariano"). Verified 2026-11-18, Crossref.

### Non-synchronous trading: Dimson and Scholes-Williams

<a id="r18"></a>**R18.** Scholes, M., and Williams, J. (1977). Estimating betas from nonsynchronous
data. *Journal of Financial Economics*, 5(3), 309-327.
doi:[10.1016/0304-405X(77)90041-1](https://doi.org/10.1016/0304-405X(77)90041-1). [`scholes1977`]
- Used for: the cross-check estimator `(b_-1 + b_0 + b_+1) / (1 + 2 rho_m)`. Used in:
  [`specs/lead-lag-betas.md`](specs/lead-lag-betas.md) LL1, LL4. Repo cites: full. Verified
  2026-11-18, Crossref. The spec could not read the paper's text (item U6).

<a id="r19"></a>**R19.** Dimson, E. (1979). Risk measurement when shares are subject to infrequent
trading. *Journal of Financial Economics*, 7(2), 197-226.
doi:[10.1016/0304-405X(79)90013-8](https://doi.org/10.1016/0304-405X(79)90013-8). [`dimson1979`]
- Used for: the primary lead-lag estimator (sum of the lag, same-day and lead coefficients, per
  factor). Used in: [`specs/lead-lag-betas.md`](specs/lead-lag-betas.md) LL1, LL2.1. Repo cites:
  full. Verified 2026-11-18, Crossref. The paper's own conclusions are `[U]` in the spec (item U3).

<a id="r20"></a>**R20.** Fowler, D. J., and Rorke, C. H. (1983). Risk measurement when shares are
subject to infrequent trading: comment. *Journal of Financial Economics*, 12(2), 279-283.
doi:[10.1016/0304-405X(83)90039-9](https://doi.org/10.1016/0304-405X(83)90039-9). [`fowler1983`]
- Used for: background to the bias of the plain Dimson sum when the market is autocorrelated. Used
  in: [`specs/lead-lag-betas.md`](specs/lead-lag-betas.md) LL1. Repo cites: full. Verified
  2026-11-18, Crossref and RePEc. Crossref registers the title without ": Comment"; RePEc gives it
  with ": Comment". The spec marks the content `[U]` (item U3).

<a id="r21"></a>**R21.** Cohen, K. J., Hawawini, G. A., Maier, S. F., Schwartz, R. A., and Whitcomb,
D. K. (1983). Friction in the trading process and the estimation of systematic risk. *Journal of
Financial Economics*, 12(2), 263-278.
doi:[10.1016/0304-405X(83)90038-7](https://doi.org/10.1016/0304-405X(83)90038-7). [`cohen1983`]
- Used for: related work only; nothing in the spec depends on it. Used in:
  [`specs/lead-lag-betas.md`](specs/lead-lag-betas.md) LL1. Repo cites: full. Verified 2026-11-18,
  Crossref.

<a id="r22"></a>**R22.** Chung, L. T. D. (2026). Simply better market betas around the globe.
*Critical Finance Review*, 15(2), 133-155.
doi:[10.1108/CFR-06-2023-2498](https://doi.org/10.1108/CFR-06-2023-2498). [`chung2026`]
- Used for: evidence that Dimson-type adjustments can hurt when forecasting betas, which is why no
  lead-lag beta may be used as an ex-ante exposure. Used in:
  [`specs/lead-lag-betas.md`](specs/lead-lag-betas.md) LL1, LL5. Repo cites: the manuscript dated
  2024-03-12 (SSRN 10.2139/ssrn.4755442), venue `[U]`. Verified 2026-11-18, Crossref: the paper is
  published in *Critical Finance Review* 15(2), 133-155 (issued 2026-06-01). The page numbers quoted
  in the spec (p. 3, 6, 17) refer to the manuscript, not to the published version.

<a id="r55"></a>**R55.** Hollstein, F., Prokopczuk, M., and Wese Simen, C. (2019). Estimating beta:
forecast adjustments and the impact of stock characteristics for a broad cross-section. *Journal of
Financial Markets*, 44, 91-118.
doi:[10.1016/j.finmar.2019.03.001](https://doi.org/10.1016/j.finmar.2019.03.001). [`hollstein2019`]
- Used for: a second-hand check of the Scholes-Williams estimator. The accepted manuscript (p. 9,
  equation 4) estimates three separate regressions on the lagged, contemporaneous and led market
  excess return and takes the sum of the three slopes divided by `1 + 2 rho`, "where rho is the first
  order autocorrelation of the market excess return". This is the form in
  [`specs/lead-lag-betas.md`](specs/lead-lag-betas.md) LL1 and LL4. Repo cites: not cited. Verified
  2026-11-18, Crossref (volume 44, pages 91-118); manuscript read at
  <https://centaur.reading.ac.uk/81659/1/Estimating%20Beta.pdf>. It is a secondary source: the 1977
  paper's text (R18) was still not read.

<a id="r62"></a>**R62.** Roll, R. (1984). A simple implicit measure of the effective bid-ask spread in
an efficient market. *The Journal of Finance*, 39(4), 1127-1139.
doi:[10.1111/j.1540-6261.1984.tb03897.x](https://doi.org/10.1111/j.1540-6261.1984.tb03897.x).
[`roll1984`]
- Used for: context for the timing-noise argument. The abstract (read through OpenAlex) says
  "trading costs induce negative serial dependence in successive observed market price changes" and
  that the effective spread can be measured from the first-order serial covariance of price changes.
  `methodology.md` M3.6 derives its own noise-share formula `s = -2 rho_1` for a transient error
  `u_t - u_{t-1}`; Roll is background to that argument, not a source for the formula or for the gate
  threshold. Repo cites: not cited. Verified 2026-11-18, Crossref.

### Shrinkage and empirical Bayes

<a id="r23"></a>**R23.** Vasicek, O. A. (1973). A note on using cross-sectional information in
Bayesian estimation of security betas. *The Journal of Finance*, 28(5), 1233-1239.
doi:[10.2307/2978759](https://doi.org/10.2307/2978759). [`vasicek1973`]
- Used for: the Vasicek-style empirical-Bayes estimate of the prior spread of betas. Used in:
  [`specs/shrunk-betas.md`](specs/shrunk-betas.md) SB2.2. Repo cites: author-year, journal, volume
  and pages (no title). Verified 2026-11-18, Crossref (start page) and RePEc (pages 1233-1239). The
  spec did not read the paper's text.

<a id="r24"></a>**R24.** Müller, U. K. (2013). Risk of Bayesian inference in misspecified models, and
the sandwich covariance matrix. *Econometrica*, 81(5), 1805-1849.
doi:[10.3982/ECTA9097](https://doi.org/10.3982/ECTA9097). [`mueller2013`]
- Used for: the justification of a normal posterior centred at the estimator with the sandwich
  (HAC) covariance. Used in: [`specs/shrunk-betas.md`](specs/shrunk-betas.md) SB1.1, SB4. Repo
  cites: full (abstract only). Verified 2026-11-18, Crossref (no author list in the record), OpenAlex
  (author Ulrich K. Müller) and RePEc (pages 1805-1849).

<a id="r53"></a>**R53.** Efron, B., and Morris, C. (1973). Stein's estimation rule and its
competitors---an empirical Bayes approach. *Journal of the American Statistical Association*,
68(341), 117-130.
doi:[10.1080/01621459.1973.10481350](https://doi.org/10.1080/01621459.1973.10481350).
[`efron1973`]

<a id="r54"></a>**R54.** Efron, B., and Morris, C. (1975). Data analysis using Stein's estimator and
its generalizations. *Journal of the American Statistical Association*, 70(350), 311-319.
doi:[10.1080/01621459.1975.10479864](https://doi.org/10.1080/01621459.1975.10479864).
[`efron1975`]
- R53 and R54: candidate sources for the phrase "Efron-Morris type" in
  [`specs/shrunk-betas.md`](specs/shrunk-betas.md) SB2.5, which names the authors with no year or
  title. We list both because the spec does not say which paper it means; we read neither text, only
  the titles. Repo cites: authors only. Verified 2026-11-18, Crossref.

### Residual alpha, summary statistics and stability

<a id="r25"></a>**R25.** Lo, A. W. (2002). The statistics of Sharpe ratios. *Financial Analysts
Journal*, 58(4), 36-52. doi:[10.2469/faj.v58.n4.2453](https://doi.org/10.2469/faj.v58.n4.2453).
[`lo2002`]
- Used for: the delta-method variance of the information ratio, and why the report's interval is
  labelled approximate. Used in: [`methodology-residual-analysis.md`](methodology-residual-analysis.md)
  R3.3. Repo cites: author-year. Verified 2026-11-18, Crossref.

<a id="r26"></a>**R26.** Magdon-Ismail, M., Atiya, A. F., Pratap, A., and Abu-Mostafa, Y. S. (2004). On
the maximum drawdown of a Brownian motion. *Journal of Applied Probability*, 41(1), 147-161.
doi:[10.1239/jap/1077134674](https://doi.org/10.1239/jap/1077134674). [`magdonismail2004`]
- Used for: the noise-drawdown reference `sqrt(pi/2) sigma sqrt(T)`. Used in:
  [`methodology-residual-analysis.md`](methodology-residual-analysis.md) R3.4. Repo cites:
  author-year (all four authors). Verified 2026-11-18, Crossref (the same article also has DOI
  10.1017/S0021900200014108).

<a id="r27"></a>**R27.** Ploberger, W., and Krämer, W. (1992). The CUSUM test with OLS residuals.
*Econometrica*, 60(2), 271-285. doi:[10.2307/2951597](https://doi.org/10.2307/2951597).
[`ploberger1992`]
- Used for: the whole-sample OLS-CUSUM check of alpha stability. Used in:
  [`methodology.md`](methodology.md) M9; [`skill-review.md`](skill-review.md) finding 2. Repo cites:
  author-year. Verified 2026-11-18, Crossref (start page) and RePEc (pages 271-285).

<a id="r28"></a>**R28.** Krämer, W., Ploberger, W., and Alt, R. (1988). Testing for structural change
in dynamic models. *Econometrica*, 56(6), 1355-1369.
doi:[10.2307/1913102](https://doi.org/10.2307/1913102). [`kramer1988`]
- Used for: the recursive CUSUM, which the review chose not to adopt. Used in:
  [`skill-review.md`](skill-review.md) finding 2. Repo cites: author-year. Verified 2026-11-18,
  Crossref (start page) and RePEc (pages 1355-1369).

### Risk and return attribution

<a id="r56"></a>**R56.** Tasche, D. (2007). Capital allocation to business units and sub-portfolios:
the Euler principle. arXiv preprint 0708.2542 (first posted 2007-08-19).
<https://arxiv.org/abs/0708.2542>. [`tasche2008`]
- Used for: the Euler allocation principle behind the risk contributions
  `RC_i = beta_hat_i (Sigma_f beta_hat)_i / V`. The abstract, read through the arXiv API, says: "Despite
  the fact that the Euler allocation principle has been adopted by many financial institutions for
  their internal capital allocation process, a comprehensive description of Euler allocation seems
  still to be missing. We try to fill this gap by presenting the theoretical background as well as
  practical aspects." Used in: [`methodology.md`](methodology.md) M7, D5; [`PLAN.md`](PLAN.md).
  Repo cites: not cited ("Euler decomposition" by name). We read the abstract only and did not check
  that M7's formula appears in the paper. The bib key says 2008 and the entry year is 2007; the arXiv
  posting date is the one verified.

<a id="r57"></a>**R57.** Litterman, R. (1996). Hot Spots and hedges. *The Journal of Portfolio
Management*, 23(5), 52-75. doi:[10.3905/jpm.1996.052](https://doi.org/10.3905/jpm.1996.052).
[`litterman1996`]

<a id="r58"></a>**R58.** Qian, E. E. (2005). On the financial interpretation of risk contribution: risk
budgets do add up. SSRN working paper. doi:[10.2139/ssrn.684221](https://doi.org/10.2139/ssrn.684221).
[`qian2005`]
- R57 and R58: candidate sources on risk contribution, found by title; we read neither abstract nor
  text, so we do not say what they show. Used in: none yet. Repo cites: not cited. Verified
  2026-11-18, Crossref (R58 is the SSRN posting; a journal version was not located).

The tilt-and-timing split (`methodology.md` M6.3) has no literature source. `PLAN.md` credits the
pyfolio project, which is software, not a paper; see
[Claims in the repo without a source](#claims-in-the-repo-without-a-source), item C5.

### Influence and fragility

<a id="r29"></a>**R29.** Cook, R. D. (1977). Detection of influential observation in linear
regression. *Technometrics*, 19(1), 15-18.
doi:[10.1080/00401706.1977.10489493](https://doi.org/10.1080/00401706.1977.10489493). [`cook1977`]
- Used for: the textbook influence measure that the spec adapts to the HAC covariance (Cook-HAC).
  Used in: [`specs/fragility-score.md`](specs/fragility-score.md) FR5.1. Repo cites: full. Verified
  2026-11-18, Crossref.

<a id="r30"></a>**R30.** Broderick, T., Giordano, R., and Meager, R. (2020). An automatic
finite-sample robustness metric: when can dropping a little data make a big difference? arXiv
preprint 2011.14999. <https://arxiv.org/abs/2011.14999>. [`broderick2020`]
- Used for: the idea of finding the smallest set of observations whose removal flips a conclusion.
  Used in: [`specs/fragility-score.md`](specs/fragility-score.md) FR2.3. Repo cites: full, abstract
  quoted. Verified 2026-11-18, arXiv API (title, authors, first posted 2020; the API returns version
  v5) and OpenAlex.

<a id="r31"></a>**R31.** Giordano, R., Meager, R., and Broderick, T. (2026). An automatic finite-sample
robustness metric: when can dropping a little data change conclusions? Part I: definitions and
experiments. *Philosophical Transactions of the Royal Society A*, 384(2321), article 20250001.
doi:[10.1098/rsta.2025.0001](https://doi.org/10.1098/rsta.2025.0001). [`giordano2026a`]

<a id="r32"></a>**R32.** Giordano, R., Meager, R., and Broderick, T. (2026). An automatic finite-sample
robustness metric: when can dropping a little data change conclusions? Part II: theory and
intuition. *Philosophical Transactions of the Royal Society A*, 384(2321), article 20240614.
doi:[10.1098/rsta.2024.0614](https://doi.org/10.1098/rsta.2024.0614). [`giordano2026b`]
- R31 and R32: the published two-part version of R30; the spec says "content of the published parts
  U". Used in: [`specs/fragility-score.md`](specs/fragility-score.md) FR2.3. Repo cites: author-year
  and both DOIs (the spec's phrase "Giordano and Meager (2020)" refers to the preprint). Verified
  2026-11-18, Crossref (volume 384, issue 2321, published online 2026-05-27). The published titles
  say "change conclusions", the preprint's "make a big difference".

<a id="r33"></a>**R33.** Sherman, J., and Morrison, W. J. (1950). Adjustment of an inverse matrix
corresponding to a change in one element of a given matrix. *The Annals of Mathematical Statistics*,
21(1), 124-127. doi:[10.1214/aoms/1177729893](https://doi.org/10.1214/aoms/1177729893).
[`sherman1950`]
- Used for: the exact leave-one-out update behind the influence calculations. Used in:
  [`specs/fragility-score.md`](specs/fragility-score.md) FR2.2, FR10.3. Repo cites: name only
  ("Sherman-Morrison"). Verified 2026-11-18, Crossref.

### Residual diagnostics

The diagnostics are informational and are never used to choose the HAC covariance
(`methodology.md` M3.5, D2). The repository names each test and, apart from R40 and R41, gives no
citation; the entries below are the original papers of the named tests, found in Crossref.

<a id="r34"></a>**R34.** Ljung, G. M., and Box, G. E. P. (1978). On a measure of lack of fit in time
series models. *Biometrika*, 65(2), 297-303.
doi:[10.1093/biomet/65.2.297](https://doi.org/10.1093/biomet/65.2.297). [`ljung1978`]
- Used for: the Ljung-Box test at lag 10. Used in: [`methodology.md`](methodology.md) M3.5;
  [`methodology-residual-analysis.md`](methodology-residual-analysis.md) R6. Repo cites: name only.
  Verified 2026-11-18, Crossref.

<a id="r35"></a>**R35.** Jarque, C. M., and Bera, A. K. (1980). Efficient tests for normality,
homoscedasticity and serial independence of regression residuals. *Economics Letters*, 6(3), 255-259.
doi:[10.1016/0165-1765(80)90024-5](https://doi.org/10.1016/0165-1765(80)90024-5). [`jarque1980`]
- Used for: the Jarque-Bera test of residual skew and kurtosis. Used in:
  [`methodology.md`](methodology.md) M3.5. Repo cites: name only. Verified 2026-11-18, Crossref.

<a id="r36"></a>**R36.** Durbin, J., and Watson, G. S. (1950). Testing for serial correlation in least
squares regression. I. *Biometrika*, 37(3-4), 409-428.
doi:[10.1093/biomet/37.3-4.409](https://doi.org/10.1093/biomet/37.3-4.409). [`durbin1950`]
- Used for: the Durbin-Watson statistic. Used in: [`methodology.md`](methodology.md) M3.5. Repo
  cites: name only. Verified 2026-11-18, Crossref. Part II is Biometrika 38(1-2), 159-178 (Crossref
  DOI 10.1093/biomet/38.1-2.159); it is not in the bibliography because the repo does not name it.

<a id="r37"></a>**R37.** Breusch, T. S. (1978). Testing for autocorrelation in dynamic linear models.
*Australian Economic Papers*, 17(31), 334-355.
doi:[10.1111/j.1467-8454.1978.tb00635.x](https://doi.org/10.1111/j.1467-8454.1978.tb00635.x).
[`breusch1978`]

<a id="r38"></a>**R38.** Godfrey, L. G. (1978). Testing against general autoregressive and moving
average error models when the regressors include lagged dependent variables. *Econometrica*,
46(6), 1293-1301. doi:[10.2307/1913829](https://doi.org/10.2307/1913829). [`godfrey1978`]
- R37 and R38: the Breusch-Godfrey test, implemented with an HC0 covariance. Used in:
  [`methodology.md`](methodology.md) M3.5. Repo cites: name only. Verified 2026-11-18, Crossref
  (Godfrey: start page) and RePEc (Godfrey: pages 1293-1301).

<a id="r39"></a>**R39.** Engle, R. F. (1982). Autoregressive conditional heteroscedasticity with
estimates of the variance of United Kingdom inflation. *Econometrica*, 50(4), 987-1007.
doi:[10.2307/1912773](https://doi.org/10.2307/1912773). [`engle1982`]
- Used for: the ARCH-LM test (5 lags) for volatility clustering. Used in:
  [`methodology.md`](methodology.md) M3.5; [`methodology-residual-analysis.md`](methodology-residual-analysis.md)
  R6, P5 ("Engle's ARCH LM test"). Repo cites: author name only. Verified 2026-11-18, Crossref
  (start page) and RePEc (pages 987-1007).

<a id="r40"></a>**R40.** Lobato, I., Nankervis, J. C., and Savin, N. E. (2001). Testing for
autocorrelation using a modified Box-Pierce Q test. *International Economic Review*, 42(1), 187-205.
doi:[10.1111/1468-2354.00106](https://doi.org/10.1111/1468-2354.00106). [`lobato2001`]
- Used for: the literature behind replacing the classical Ljung-Box reading with a test robust to
  changing volatility. Used in: [`skill-review.md`](skill-review.md) finding 1. Repo cites:
  author-year. Verified 2026-11-18, Crossref.

<a id="r41"></a>**R41.** Romano, J. P., and Thombs, L. A. (1996). Inference for autocorrelations under
weak assumptions. *Journal of the American Statistical Association*, 91(434), 590-600.
doi:[10.1080/01621459.1996.10476928](https://doi.org/10.1080/01621459.1996.10476928).
[`romano1996`]
- Used for: as R40. Used in: [`skill-review.md`](skill-review.md) finding 1. Repo cites:
  author-year. Verified 2026-11-18, Crossref.

### Cointegration and unit roots

<a id="r42"></a>**R42.** Engle, R. F., and Granger, C. W. J. (1987). Co-integration and error
correction: representation, estimation, and testing. *Econometrica*, 55(2), 251-276.
doi:[10.2307/1913236](https://doi.org/10.2307/1913236). [`engle1987`]
- Used for: the Engle-Granger two-step test for each pair, and its requirement that both series are
  I(1). Used in: [`methodology.md`](methodology.md) M11.2;
  [`wiki/decision-cointegration-design.md`](../wiki/decision-cointegration-design.md). Repo cites:
  author-year (`skill-review.md` finding 16). Verified 2026-11-18, Crossref (start page) and RePEc
  (pages 251-276).

<a id="r43"></a>**R43.** MacKinnon, J. G. (1994). Approximate asymptotic distribution functions for
unit-root and cointegration tests. *Journal of Business & Economic Statistics*, 12(2), 167-176.
doi:[10.1080/07350015.1994.10510005](https://doi.org/10.1080/07350015.1994.10510005).
[`mackinnon1994`]

<a id="r44"></a>**R44.** MacKinnon, J. G. (2010). *Critical values for cointegration tests*. Queen's
Economics Department Working Paper No. 1227, Queen's University, January 2010.
<https://www.econ.queensu.ca/sites/econ.queensu.ca/files/qed_wp_1227.pdf>. [`mackinnon2010`]
- R43 and R44: the source of the approximate p-values that `coint` returns (family F7). Used in:
  [`methodology.md`](methodology.md) M11.2, step 1; [`skill-review.md`](skill-review.md) findings
  17 and 20. Repo cites: author-year ("MacKinnon (1994, 2010)"). Verified 2026-11-18: R43 Crossref;
  R44 the PDF answers (HTTP 200, application/pdf), RePEc record "Critical Values For Cointegration
  Tests" (working paper, 2010-01) and OpenAlex. R44 has no DOI.

<a id="r45"></a>**R45.** Johansen, S. (1991). Estimation and hypothesis testing of cointegration
vectors in Gaussian vector autoregressive models. *Econometrica*, 59(6), 1551-1580.
doi:[10.2307/2938278](https://doi.org/10.2307/2938278). [`johansen1991`]
- Used for: the Johansen trace test, shown as a confirmation column outside the p-value families.
  Used in: [`methodology.md`](methodology.md) M11.2 step 4, D11. Repo cites: author-year. Verified
  2026-11-18, Crossref (start page) and RePEc (pages 1551-1580).

<a id="r46"></a>**R46.** Shin, Y. (1994). A residual-based test of the null of cointegration against
the alternative of no cointegration. *Econometric Theory*, 10(1), 91-115.
doi:[10.1017/S0266466600008240](https://doi.org/10.1017/S0266466600008240). [`shin1994`]
- Used for: the stated reason not to add a KPSS test on cointegrating residuals (finding 17, "do not
  adopt"). Used in: [`skill-review.md`](skill-review.md) finding 17. Repo cites: author-year.
  Verified 2026-11-18, Crossref.

<a id="r47"></a>**R47.** Dickey, D. A., and Fuller, W. A. (1979). Distribution of the estimators for
autoregressive time series with a unit root. *Journal of the American Statistical Association*,
74(366a), 427-431.
doi:[10.1080/01621459.1979.10482531](https://doi.org/10.1080/01621459.1979.10482531). [`dickey1979`]

<a id="r48"></a>**R48.** Said, S. E., and Dickey, D. A. (1984). Testing for unit roots in
autoregressive-moving average models of unknown order. *Biometrika*, 71(3), 599-607.
doi:[10.1093/biomet/71.3.599](https://doi.org/10.1093/biomet/71.3.599). [`said1984`]
- R47 and R48: the (augmented) Dickey-Fuller test of the out-of-sample residual. Used in:
  [`methodology.md`](methodology.md) M11.2 steps 3 and 6. Repo cites: name only ("ADF",
  `adfuller`). Verified 2026-11-18, Crossref. That R48 is the source of the augmented form as
  implemented is our choice; the repo does not say.

### Report design

<a id="r49"></a>**R49.** Machado, G. M., Oliveira, M. M., and Fernandes, L. A. F. (2009). A
physiologically-based model for simulation of color vision deficiency. *IEEE Transactions on
Visualization and Computer Graphics*, 15(6), 1291-1298.
doi:[10.1109/TVCG.2009.113](https://doi.org/10.1109/TVCG.2009.113). [`machado2009`]
- Used for: the colour-vision-deficiency simulation in the palette validation. Used in:
  [`design/report-design.md`](design/report-design.md) A (Validation). Repo cites: author-year.
  Verified 2026-11-18, Crossref (a correction, TVCG 16(2), 352, exists and is not listed).

<a id="r50"></a>**R50.** Ottosson, B. (2020). A perceptual color space for image processing (Oklab).
<https://bottosson.github.io/posts/oklab/>. [`ottosson2020`]
- Used for: the OKLab and OKLCH colour spaces named in the palette validation. Used in:
  [`design/report-design.md`](design/report-design.md) A. Repo cites: name only ("OKLab"). Verified
  2026-11-18: the page answers (HTTP 200), is titled "A perceptual color space for image
  processing" and is by Björn Ottosson. The page shows no date; the year 2020 comes from its text
  ("When introduced Oklab in 2020").

<a id="r51"></a>**R51.** World Wide Web Consortium (2024). *Web Content Accessibility Guidelines
(WCAG) 2.2*. W3C Recommendation, 12 December 2024. <https://www.w3.org/TR/WCAG22/>. [`wcag22`]
- Used for: the contrast ratio the report design measures. Used in:
  [`design/report-design.md`](design/report-design.md) F. Repo cites: name only ("WCAG ratio",
  no version). Verified 2026-11-18: the page answers (HTTP 200) and shows "W3C Recommendation 12
  December 2024". Which WCAG version the design follows is our reading, not stated in the repo.

### Event sources used in demonstrations

<a id="r52"></a>**R52.** MicroStrategy (2020-08-11). *MicroStrategy Adopts Bitcoin as Primary Treasury
Reserve Asset*. Press release, Nasdaq.
<https://www.nasdaq.com/press-release/microstrategy-adopts-bitcoin-as-primary-treasury-reserve-asset-2020-08-11>.
- Used for: the date of the exposure change used as a known-break example. Used in:
  [`specs/kalman-betas.md`](specs/kalman-betas.md) KB9.2. Repo cites: title and URL (read through a
  search summary). Verified 2026-11-18: the page answers (HTTP 200), carries the title, "purchased
  21,454 bitcoins" and a reference to the 28 July 2020 results; the 11 August 2020 date comes from
  the URL. Not in `references.bib` (not a bibliographic work).

### Planned features (not implemented)

<a id="r59"></a>**R59.** Künsch, H. R. (1989). The jackknife and the bootstrap for general stationary
observations. *The Annals of Statistics*, 17(3), 1217-1241.
doi:[10.1214/aos/1176347265](https://doi.org/10.1214/aos/1176347265). [`kunsch1989`]

<a id="r60"></a>**R60.** Politis, D. N., and Romano, J. P. (1994). The stationary bootstrap. *Journal of
the American Statistical Association*, 89(428), 1303-1313.
doi:[10.1080/01621459.1994.10476870](https://doi.org/10.1080/01621459.1994.10476870).
[`politis1994`]
- R59 and R60: candidate sources for the block-bootstrap intervals listed as "Not ranked" in
  [`ROADMAP.md`](ROADMAP.md), which names the method with no source. Found by title; texts not read.
  Nothing in the code uses them. Repo cites: not cited. Verified 2026-11-18, Crossref.

### Data quality and adjusted close

No journal article is cited for the adjusted-close audit (`methodology.md` M1.4, D9). The sources
are the provider documents in [Data sources and licences](#data-sources-and-licences) and the
project's own checks (`validation/spy-slice-validation.md` F6; `data-source-comparison.md`). The
repo's statement that Yahoo's adjustment follows the CRSP method is documented by Yahoo itself
(see the Yahoo help entry in [Data sources and licences](#data-sources-and-licences)); no CRSP
document was consulted.

## Software

Versions are from `uv.lock` (Python) and `frontend/package-lock.json` (JavaScript), the files the
project installs from. Licences were read on 2026-11-18 from PyPI's record for the exact locked
version (`https://pypi.org/pypi/<package>/<version>/json`) and from the `license` field of each
package in `package-lock.json`. A licence name is the package's own declaration, not a legal review.
Packages pulled in indirectly, and the extras of `uvicorn[standard]`, are not listed.

Python, runtime (`pyproject.toml`):

| Package | Locked version | Licence | Role in factordesk |
|---|---|---|---|
| statsmodels | 0.15.0 | BSD-3-Clause | OLS, HAC covariance, diagnostics, `coint`, Johansen, state-space tools for tests |
| pandas | 3.1.1 | BSD-3-Clause | Tables and dates |
| numpy | 2.5.5 | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 | Linear algebra, Kalman filter loop |
| scipy | 1.18.1 | BSD (PyPI classifier "BSD License"; no SPDX expression given) | Distributions and tests |
| yfinance | 1.8.0 | Apache-2.0 | Yahoo Finance price downloads |
| fastapi | 0.163.2 | MIT | Local dashboard API |
| uvicorn | 0.54.0 | BSD-3-Clause | Local server |
| pydantic-settings | 2.16.3 | MIT | Settings |
| pyarrow | 26.0.1 | Apache-2.0 | Parquet cache |
| httpx | 0.28.1 | BSD-3-Clause | HTTP downloads |

Python, development: pytest 9.2.0 (MIT), ruff 0.17.5 (MIT), pyright 1.1.414 (MIT), pandas-stubs
3.1.0.261029 (BSD-3-Clause).

JavaScript, runtime (`frontend/package.json`, exact pins):

| Package | Locked version | Licence | Role in factordesk |
|---|---|---|---|
| react, react-dom | 19.3.1 | MIT | Dashboard interface |
| echarts | 6.1.0 | Apache-2.0 | Charts |
| @tanstack/react-query | 5.108.0 | MIT | Data fetching |
| downshift | 9.5.0 | MIT | Ticker search box |

JavaScript, development: vite 8.3.8, vitest 5.1.1, @vitejs/plugin-react 6.3.0, typescript 5.9.3
(Apache-2.0), eslint 9.39.5, @eslint/js 9.39.5, typescript-eslint 8.73.0, eslint-plugin-react 7.37.5,
eslint-plugin-react-hooks 7.1.1, eslint-plugin-jsx-a11y 6.10.2, @playwright/test 1.65.1
(Apache-2.0), @testing-library/react 16.3.3, @testing-library/dom 10.4.2, jsdom 31.0.1, msw 3.0.7,
openapi-typescript 7.13.0, concurrently 10.0.7, @types/node 26.6.6, @types/react 19.3.0,
@types/react-dom 19.3.0. All MIT except where marked.

Fonts embedded in the report (licence files in `backend/factordesk/report/fonts/`): Instrument Sans
(SIL Open Font License 1.1; "Copyright 2022 The Instrument Sans Project Authors") and STIX Two Text
(SIL Open Font License 1.1; "Copyright 2001-2021 The STIX Fonts Project Authors").

factordesk itself is MIT licensed (`LICENSE`).

## Unverified citations

The 11 items first listed here on 2026-11-18, and what happened to each in the follow-up pass the
same day. "Resolved" means we found a source and verified it as described above; "partly" means one
part is sourced and one is not; "no source" means we looked and found nothing authoritative that
we could read. Items with no source are listed with file and line in
[Claims in the repo without a source](#claims-in-the-repo-without-a-source).

| Item | What the repository says | Status |
|---|---|---|
| U1 | `specs/shrunk-betas.md:133`: "Vasicek / empirical Bayes; Efron-Morris type" | Resolved: candidate sources R53, R54 (the spec does not say which paper it means). |
| U2 | `research-protocol.md:110`: a test "one-sided, Wilcoxon signed-rank" | Resolved: R61, with start page only (end page not confirmed). |
| U3 | `specs/lead-lag-betas.md:57-59`: content of Scholes-Williams, Dimson and Fowler-Rorke marked `[U]` | No source for the content of Dimson (1979) and Fowler-Rorke (1983); the Scholes-Williams estimator form is sourced under U6. |
| U4 | `research-protocol.md:144-145` RT4 and RT5: tables of Fama and French (2017, 2012) marked `U` | No source: paywall, SSRN HTTP 403. |
| U5 | `skill-review.md:77`: the lag rule `floor(4 (m/100)^(2/9))` "is the rule-of-thumb from Newey and West (1994)" | No source for the attribution (details in item C3). |
| U6 | `specs/lead-lag-betas.md:57`: the form `beta^SW = (b_-1 + b_0 + b_+1) / (1 + 2 rho_m)` | Resolved with a secondary source, R55. |
| U7 | `wiki/decision-factor-data-source-french-library.md:35` and two other wiki lines: the library asks users to follow its terms and credit its authors | No source: the site states neither (exact wording in [Source of truth for factor data](#source-of-truth-for-factor-data)). |
| U8 | `methodology.md` M1.4 A6 and D9: "the adjustment Yahoo applies (CRSP method)" | Resolved: Yahoo's own help page SLN28256 (see [Data sources and licences](#data-sources-and-licences)). |
| U9 | `methodology.md` M6.3 and M7, `PLAN.md`, `ROADMAP.md`: Euler contributions, tilt-and-timing split, block bootstrap | Partly: sources for Euler (R56 to R58) and the bootstrap (R59, R60); none for tilt and timing. |
| U10 | `data-source-comparison.md:258` and `data-quality-plan.md:83`: Yahoo's doubled AVGO dividend, confirmed by a Broadcom filing on sec.gov | No source we could read: the SEC returns HTTP 403 to scripts. |
| U11 | `methodology.md` M3.6: noise-share formula `s = -2 rho_1` and gate `rho_1 < -0.2` | Partly: Roll (R62) is background for the noise argument; the formula is the repo's own derivation and the threshold has no source. |

Also resolved in the first pass (the repo marked them unverified or incomplete):

- Chung (2024): the published version is Critical Finance Review 15(2), 133-155 ([R22](#r22)).
- Durbin and Koopman (2012): bibliographic data verified ([R15](#r15)).
- Müller (2013), Vasicek (1973) and Masreliez and Martin (1977): bibliographic data verified
  ([R24](#r24), [R23](#r23), [R16](#r16)).
- `skill-review.md` finding 20 asked for Newey and West (1994), Ploberger and Krämer (1992),
  MacKinnon (1994, 2010) and Johansen (1991): all are verified ([R8](#r8), [R27](#r27),
  [R43](#r43), [R44](#r44), [R45](#r45)).

## Claims in the repo without a source

Line numbers are for the files as they are on this branch on 2026-11-18. We did not edit these
files; they are the owner's. Each item recommends one action: add a source, soften the wording, or
remove the claim.

- **C1. Dimson (1979) and Fowler-Rorke (1983) content.** `docs/specs/lead-lag-betas.md:58-59` (and
  `:57` for Scholes-Williams, now sourced by R55). The texts were not read; "commonly cited as showing
  that the plain Dimson sum is inconsistent when the market index is autocorrelated" has no source
  we could read. Recommendation: keep the existing `[U]` marker and add a source once someone has
  read the paper.
- **C2. Regional factor tables.** `docs/research-protocol.md:144-145` (RT4, RT5) and
  `docs/methodology-datasets.md:201`. Fama and French (2017, 2012) tables are behind a paywall.
  Recommendation: keep `U`; add a source when the tables are obtained, and keep the instruction
  that no claim cites those numbers before then.
- **C3. Newey-West lag rule attributed to the 1994 paper.** `docs/skill-review.md:77` says the rule
  is "the rule-of-thumb from Newey and West (1994)"; `docs/methodology.md:65` and `docs/PLAN.md:82`
  state the rule with no attribution. The paper (R8) cannot be read here: the NBER copy
  (technical working paper 144) is a scanned image with no text layer. What we found instead: the
  statsmodels 0.15.0 docstring of `S_hac_simple` says "If None, then nlags = floor(4(T/100)^(2/9)) is
  used" and the source comment says "Reference: xtscc paper, Newey-West"; the SAS documentation lists
  the Bartlett lag-selection parameter `n = c(T/100)^(2/9)` with `c` defaulting to 12 (not 4) in
  its description of the NEWEYWEST94 bandwidth; and a read of the MathWorks `hac` documentation
  (through a fetch tool, not re-checked by script) shows `floor(4*(T/100)^(2/9))` attributed to a
  different reference, Andrews and Monahan (1992), not to Newey and West (1994). So the formula is
  widely used and its exact origin is unclear. Recommendation: soften `skill-review.md:77` to "a
  common rule of thumb, the default maximum lag of statsmodels' HAC helpers"; attribute it to
  Newey and West (1994) only after someone reads the paper.
- **C4. The library "asks" for terms and credit.** `wiki/decision-no-data-and-no-secrets-in-the-repo.md:19`,
  `wiki/decision-factor-data-source-french-library.md:35` and
  `wiki/decision-project-name-factordesk.md:14` ("as the library asks"). The site's wording is quoted
  in full above and contains no such request. Recommendation: soften to "the library states a
  copyright notice and no terms; we credit Fama and French as a courtesy".
- **C5. Tilt-and-timing split.** `docs/methodology.md:353-362` (M6.3) and `docs/PLAN.md:147`
  ("Tilt vs timing (pyfolio)"). No paper is cited; pyfolio is software. Recommendation: soften: call
  it the project's own decomposition, tested by identity, and say pyfolio inspired the idea.
- **C6. AVGO dividend confirmed by a filing.** `docs/data-source-comparison.md:258-260` and
  `docs/data-quality-plan.md:83`. The URL (SEC EDGAR 8-K exhibit) answers HTTP 403 to scripts, so we
  could not re-read it; a web-search summary described the same text ("paid a cash dividend of $1.75
  per share ... on June 29, 2018") and is not an authoritative read. Recommendation: soften
  "VERIFIED" to "read through a search summary; confirm in a browser", or re-read the filing in a
  browser and keep it.
- **C7. The residual quality gate threshold.** `docs/methodology.md:294` (`rho_1 < -0.2`) and
  `:561` (D22). Already described in `:297` as "a documented heuristic from the noise-share
  argument, not tuned on SPY"; no source exists. The noise-share formula at `:288` is the repo's own
  derivation. Recommendation: keep as written; optionally add Roll (R62) as background to `:288`.

## How the checks were done

On 2026-11-18, for each work:

1. Crossref REST API: `https://api.crossref.org/works/<doi>` for the record, or
   `https://api.crossref.org/works?query.bibliographic=<text>&rows=3` to find the DOI. Authors, year,
   title, journal, volume, issue and pages come from the record.
2. Where Crossref gives only a start page (JSTOR-hosted records), the end page and the volume and
   issue come from the RePEc record at `https://ideas.repec.org/a/<handle>.html`.
3. OpenAlex (`https://api.openalex.org/works/doi:<doi>`) as a second source for a sample of records
   (R2, R8, R24, R30, R44), and for the author list where Crossref had none.
4. arXiv API (`https://export.arxiv.org/api/query?id_list=<id>`) for the preprint.
5. For works without a DOI (R44, R50, R51) and for data pages: the page or file itself, fetched
   with an HTTP request that identifies itself as a script; the status code is recorded.
6. For software: PyPI JSON for the locked version, the `license` field in `package-lock.json`, and
   the licence files in the repository.

Pages that refused a script request (the SEC filing, HTTP 403) are not relied on. We did not use a
browser identity to get around a refusal.

Repeat the DOI checks at any time with the script, which needs only the Python standard library:

```
uv run python scripts/check_references.py
```

It reads `docs/references.bib`, asks Crossref for every DOI (and arXiv for the eprint), and prints
one line per entry: `OK`, `FAIL` (title, year or first author differs from the record, or the DOI
does not exist), `ERROR` (the network or the service failed; the entry was not checked) or `SKIP`
(no DOI or arXiv id). The exit code is 0 when every checked entry matches, 1 on a mismatch and 2
when some entries could not be checked. On the same date the script reported 58 matches, 0
mismatches, 0 not checked and 5 skipped (the library page, the MacKinnon working paper, the
Oklab post, WCAG and the Yahoo help page, all checked by hand above). Run it after editing the bib file, and cite a work
only after it passes. The rule is recorded in
[`wiki/decision-citations-and-verification.md`](../wiki/decision-citations-and-verification.md).

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
while designing factordesk. Those are software projects, not literature; the notes are in
[`wiki/prior-art-review-2026-11-18.md`](../wiki/prior-art-review-2026-11-18.md).
