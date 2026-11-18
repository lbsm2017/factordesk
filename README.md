# factordesk

factordesk is a Fama-French 5-factor analysis of a single stock, as a local dashboard and as an
offline HTML report. Type a ticker and press **Factor it**: the backend downloads daily prices
(yfinance) and the public Ken French 5-factor daily data, regresses the stock on the factors, and
returns a typed report with factor betas, return and risk attribution, and rolling betas. The
architecture plan is in [docs/PLAN.md](docs/PLAN.md); the statistical rules are in
[docs/methodology.md](docs/methodology.md).

It is for researchers and curious investors who want to see what a stock's returns have been
exposed to (market, size, value, profitability, investment) and how much of that exposure can be
told apart from noise. It describes the past. It does not forecast, rank or recommend anything.

Factor data comes from the
[Kenneth R. French Data Library](https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html),
which is the source of truth for every factor definition. Prices come from Yahoo Finance through
yfinance. Neither dataset is stored in this repository; both are downloaded when you run it. See
[docs/references.md](docs/references.md) for sources, papers and terms.

Status (2026-11-18): the SPY slice, the offline report, the CLI and the dashboard are built; the
newer analytics sections are not (see [Method status](#method-status)). Alpaca is not used in v1
(yfinance only); the `.env` keys are placeholders for a later adapter.

## What it does

One ticker in, one factor profile out. The report has these panels, in this order:

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

Two ways to read it:

- **Dashboard.** A local web page: a ticker search, range chips (3Y, 5Y, Full history), custom
  dates and a factor refresh. It runs on your machine, with no login, and nothing is hosted.
  Runbook: [docs/dashboard.md](docs/dashboard.md); behaviour: [docs/specs/dashboard.md](docs/specs/dashboard.md).
- **Offline HTML report.** One self-contained file from `uv run factordesk report SPY --open`.
  A synthetic example (made-up numbers, not real data) is
  [docs/samples/mock_report.html](docs/samples/mock_report.html). Look and wording:
  [docs/design/report-design.md](docs/design/report-design.md).

## Method on one screen

For ticker `i` on day `t`, the model is
`r_i,t - RF_t = alpha + b_mkt (Mkt-RF)_t + b_smb SMB_t + b_hml HML_t + b_rmw RMW_t + b_cma CMA_t + e_t`
(Fama and French 2015), fitted by OLS on daily excess returns over the days where prices and
factors overlap ([M3.1](docs/methodology.md)). Why daily data and robust errors:
[decision](wiki/decision-daily-returns-and-robust-errors.md).

- **Inference.** Newey-West HAC standard errors (Bartlett kernel, lag `floor(4 (m/100)^(2/9))` for
  `m` observations), normal p-values ([M0.5](docs/methodology.md)).
- **Multiple testing.** The five betas form one family corrected with Benjamini-Hochberg at 5%.
  Alpha is a single test at 5% ([M0.6](docs/methodology.md),
  [decision](wiki/decision-which-betas-count-as-reliable.md)).
- **Rolling betas.** Each point uses only the previous 126 or 252 trading days ending on that date.
- **Attribution.** Return contributions are annualised arithmetic means, so contributions, alpha and
  residual sum to the total. Risk contributions are Euler shares of variance, which sum to 100%
  and whose idiosyncratic share is `1 - R-squared`
  ([M6, M7](docs/methodology.md), [decision](wiki/decision-return-and-risk-attribution.md)).
- **Data-quality gate.** A price audit runs on every ticker. A residual gate fires when the lag-1
  residual autocorrelation is below -0.2 with a robust z below -4, the signature of closing prices
  not synchronous with the factor data. When it fires, the report adds a 5-day-block estimate and
  tags a coefficient *reliable* only if the daily and the 5-day tests both reject
  ([M3.6](docs/methodology.md), [decision](wiki/decision-spy-timing-noise-and-the-quality-gate.md)).
  The thresholds are a documented heuristic checked on five S&P 500 products only.

### Method status

As of 2026-11-18, from [docs/ROADMAP.md](docs/ROADMAP.md), for this branch. "Not in this branch"
means the report has an empty slot for the section (schema version 4) and no analytics behind it.

| Section | Status in this branch | Where it stands |
| --- | --- | --- |
| Regression, rolling betas, return and risk attribution, residual diagnostics, quality gate | Built; independently validated on SPY, then hardened | [SPY slice validation](docs/validation/spy-slice-validation.md), [hardening closure](docs/validation/spy-hardening-closure-2026-11-18.md) |
| Dashboard | Built; in review (PR #1) | Tested against a fake backend; run against live Yahoo data for one ticker only |
| Residual alpha analysis | Specified only. Not in this branch | [Specification](docs/methodology-residual-analysis.md); analytics in progress on a feature branch |
| Shrunk betas, Kalman betas | Specified only. Not in this branch | Specifications: [shrunk](docs/specs/shrunk-betas.md), [Kalman](docs/specs/kalman-betas.md); both in progress on feature branches |
| Fragility score, lead-lag betas | Specified only. Not in this branch | Specifications: [fragility](docs/specs/fragility-score.md), [lead-lag](docs/specs/lead-lag-betas.md); not started |
| Dominant-factor shading, drift alerts, regime betas, cointegration | Specified only, not built | [Methodology](docs/methodology.md) M8 to M11; not scheduled or later |
| Regional (European) factors | Specified only, not built | [Datasets methodology](docs/methodology-datasets.md) |

## Scientific rigour

The rules are written down in the [research protocol](docs/research-protocol.md). The ones that
matter most:

- **Hypothesis before results.** For any new statistic, the claim, the null, the exact test and the
  result that would count against it are written down first, and entered in the append-only
  [test registry](docs/registry/tests.jsonl) before the first run. Every run is a registry line,
  including abandoned ones.
- **Every number carries its sample.** Sample size, first and last date, in-sample flag and status
  ([CODING_STANDARDS.md](CODING_STANDARDS.md), section 5). A statistic that cannot be computed says
  so and shows no number.
- **No look-ahead.** A result dated `t` uses only rows dated `t` or earlier. A beta used to explain
  day `t` is the one estimated up to day `t-1`. Static scans and perturbation tests enforce it
  ([M0.2](docs/methodology.md), [decision](wiki/decision-no-look-ahead-rule.md)).
- **Correction and power.** Claims are called significant only after correction. Appendix B of the
  protocol gives the minimum detectable effect: a single stock's alpha is rarely detectable (about
  18% a year at 20% residual volatility over 10 years).
- **Independent validation and mutation testing.** A reviewer who did not write the code rebuilt the
  SPY report from raw downloads with separate code; headline numbers matched to about 1e-7. The
  review also injected 17 deliberate bugs: 12 were caught by the tests and 5 survived; the tests were then tightened at those
  boundaries ([decision](wiki/decision-independent-validation-and-mutation-testing.md)).
- **Test oracle.** The tests are specified in advance, with tolerances derived from standard
  errors: [docs/test-oracle.md](docs/test-oracle.md), plus oracles for the
  [datasets](docs/test-oracle-datasets.md) and the
  [residual analysis](docs/test-oracle-residual-analysis.md).
- **Reproducibility.** Python dependencies are pinned in `uv.lock` and frontend ones in
  `frontend/package-lock.json`; CI installs with `uv sync --locked`. Simulated data uses fixed seeds
  (test `k` uses `numpy.random.default_rng(20261118 + k)`), never the global generator. Rerun the
  checks with the commands under [Tests and checks](#tests-and-checks).
- **No citation without verification.** Every source in the bibliography was looked up and checked
  by a script or by hand; what could not be checked is listed as unverified
  ([decision](wiki/decision-citations-and-verification.md)).

### Limitations

- **Descriptive and in-sample.** Betas are estimated over the whole window and describe that window.
  They are not forecasts, and no out-of-sample test is built yet.
- **Factor lag.** The French library publishes with a lag of a month or more, so the last weeks of
  prices are charted but left out of the regression.
- **SPY timing noise.** Yahoo's SPY closes before about 2009 carry a transient timing error, which is
  why SPY's R-squared is 0.967 and not higher. The gate flags it; it does not remove it.
- **US factors only.** Non-US tickers are not supported. Whether to warn or refuse on non-USD
  tickers is an open owner decision (F13 in the hardening closure).
- **Survivorship.** The sample is tickers that exist today.
- **Yahoo prices are for personal use**, come from an unofficial route, and the adjusted close is not
  reproducible from the stored inputs.
- **Thresholds are heuristics.** The gate's false-alarm rate on single stocks is unknown until a
  panel calibration has been run.

## Data sources and licences

| Source | Used for | Terms |
| --- | --- | --- |
| [Kenneth R. French Data Library](https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html) | Every factor return and the risk-free rate | The page carries a copyright notice by Eugene F. Fama and Kenneth R. French; no terms page was found on 2026-11-18. We credit them. |
| Yahoo Finance, through [yfinance](https://ranaroussi.github.io/yfinance/) | Daily prices, dividends and splits of the analysed ticker | Yahoo's terms and the yfinance notice limit use to personal and research use. |

The wording of both is quoted and dated in [docs/references.md](docs/references.md). Neither dataset
is committed: `data/` and `.env` are gitignored, and real-data sample reports stay local
([decision](wiki/decision-no-data-and-no-secrets-in-the-repo.md)). You are responsible for following
the providers' terms when you run factordesk.

factordesk is not affiliated with, endorsed by or vetted by Yahoo, Dartmouth College, Kenneth R.
French or Eugene F. Fama ([decision](wiki/decision-project-name-factordesk.md)).

## Setup

factordesk runs on Windows, macOS and Linux. The only prerequisite is
[uv](https://docs.astral.sh/uv/), which also installs the right Python (3.12) for you. You do not
need a system Python, conda or make.

### 1. Install uv (once)

| System | Command |
| --- | --- |
| macOS, Linux | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| Windows (PowerShell) | `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 \| iex"` |
| Any (package managers) | `brew install uv` or `winget install --id=astral-sh.uv` |

### 2. Get the code and install dependencies

```bash
git clone https://github.com/lbsm2017/factordesk.git
cd factordesk
uv sync
```

`uv sync` is uv's install command. It is the project equivalent of `pip install -r requirements.txt`:
it creates a local `.venv`, installs the exact versions pinned in `uv.lock`, and downloads
Python 3.12 if it is missing. The same command works on every system. Run it again after each
`git pull` to pick up dependency changes.

### 3. Check that it works

```bash
uv run factordesk --help
```

You should see the `report`, `factors` and `serve` commands. `uv run` runs a command inside the
project environment, so you never need to activate `.venv` yourself.

Copy `.env.example` to `.env` if you need to override settings. `.env` is gitignored.

## How to run it

factordesk is a command-line tool and a local dashboard. You give it one ticker. It
downloads that stock's daily price history and the daily Fama-French 5 factors, regresses the
stock's excess returns on the factors, and writes a self-contained HTML report: factor betas with
confidence intervals, return and risk contribution, rolling betas, data coverage and every caveat
that applies. Run all commands from the `factordesk` folder.

### Build a report

```bash
uv run factordesk report SPY --open
```

This writes `SPY_report.html` to the current folder and opens it in your browser. The terminal
prints a one-line summary:

```text
SPY: n = 8474, 1993-02-01 to 2026-09-30 (factors through 2026-09-30); R2 = 0.9673
Wrote .../SPY_report.html
```

Options:

| Option | What it does |
| --- | --- |
| `--open` | Open the HTML report in your browser when it is ready. |
| `--out DIR` | Write the report to `DIR` instead of the current folder. |
| `--json` | Also write `SPY_report.json`, the same report as machine-readable data. |
| `--start YYYY-MM-DD` | First requested date (default: the start of the price history). |
| `--end YYYY-MM-DD` | Last requested date (default: the end of the price history). |

```bash
uv run factordesk report AAPL --out reports --json
uv run factordesk report BRK-B --open
```

Tickers use Yahoo Finance symbols, so a class B share is `BRK-B`, not `BRK.B`. A ticker needs
about two years of daily history that overlaps the factor data; shorter histories are refused.

### Start the dashboard

```bash
npm --prefix frontend ci
npm --prefix frontend run build
uv run factordesk serve --open
```

The page needs Node 26 or newer and npm 12 or newer, and is built once. The server listens on
`127.0.0.1:8000` by default; keep it there, because the dashboard has no login. Options and the
development setup are in [docs/dashboard.md](docs/dashboard.md).

### Keep the factor data up to date

The first report downloads the factor file from the
[Kenneth R. French Data Library](https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html)
and caches it in `data/`. The library publishes with a lag of about a month, so the last few
weeks of prices are always shown in the chart but left out of the regression. factordesk
refreshes the file by itself once it is more than 40 days old. To check or refresh it by hand:

```bash
uv run factordesk factors status    # date range, age and source of the cached file
uv run factordesk factors refresh   # download the latest file now
```

Prices are cached in `data/` for the day, so running the same ticker again is fast. Delete
`data/` at any time to start clean; it is rebuilt on the next run.

### If something goes wrong

Every failure prints one line starting with `factordesk: error:` that says what to do, and the
exit code tells scripts what kind of problem it was:

| Exit code | Meaning |
| --- | --- |
| 0 | Success |
| 1 | Data problem: unknown ticker, too little history, or a factor file that failed validation |
| 2 | Wrong command or option (run `uv run factordesk --help`) |
| 3 | Network problem, or Yahoo Finance refused the request (try again later) |
| 4 | The output folder cannot be written (or is inside `data/`, which is not allowed) |

## Tests and checks

```bash
uv run pytest
uv run ruff check .
uv run pyright
```

Tests that use the network are marked `live` and are skipped by default. Run them with
`uv run pytest -m live`. Monte Carlo and seed-sweep tests are marked `slow`; run them with
`uv run pytest -m slow`. Frontend checks: `npm --prefix frontend test`.

## Documentation map

| Where | What it holds |
| --- | --- |
| [wiki/index.md](wiki/index.md) | Every decision in plain English: what, why, cost |
| [wiki/glossary.md](wiki/glossary.md) | Plain definitions of alpha, HAC, point-in-time and the rest |
| [docs/methodology.md](docs/methodology.md) | The binding statistical rules (M0 to M16) |
| [docs/research-protocol.md](docs/research-protocol.md) | Pre-registration, correction, power, robustness |
| [docs/test-oracle.md](docs/test-oracle.md) | The tests, written before the code |
| [docs/specs/](docs/specs) | Specifications of the features not yet in the report |
| [docs/design/report-design.md](docs/design/report-design.md) | Look, wording and accessibility of the report |
| [docs/validation/](docs/validation) | Independent validation and hardening closure |
| [docs/ROADMAP.md](docs/ROADMAP.md) | What is built, in progress and planned |
| [docs/references.md](docs/references.md) | Verified bibliography, sources and terms; [BibTeX](docs/references.bib) |
| [docs/dashboard.md](docs/dashboard.md) | Dashboard runbook |
| [docs/release-checklist.md](docs/release-checklist.md) | Steps for a release |

## Key references

Full entries, verification notes and the 11 citations that could not be verified are in
[docs/references.md](docs/references.md) (BibTeX: [references.bib](docs/references.bib)).
Verification means the work exists with these details, not that each paper's text was checked
against how the repository uses it.

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
5. Benjamini and Hochberg (1995), Controlling the false discovery rate, *J. Royal Statistical
   Society B* 57(1), 289-300, [doi](https://doi.org/10.1111/j.2517-6161.1995.tb02031.x). The
   correction across the five betas.
6. Dimson (1979), Risk measurement when shares are subject to infrequent trading, *J. Financial
   Economics* 7(2), 197-226, [doi](https://doi.org/10.1016/0304-405X(79)90013-8). Lead-lag betas
   (specified, not built).
7. Scholes and Williams (1977), Estimating betas from nonsynchronous data, *J. Financial Economics*
   5(3), 309-327, [doi](https://doi.org/10.1016/0304-405X(77)90041-1). Lead-lag cross-check
   (specified, not built).
8. Kalman (1960), A new approach to linear filtering and prediction problems, *J. Basic
   Engineering* 82(1), 35-45, [doi](https://doi.org/10.1115/1.3662552). Kalman betas (specified,
   not in this branch).
9. Vasicek (1973), A note on using cross-sectional information in Bayesian estimation of security
   betas, *J. Finance* 28(5), 1233-1239, [doi](https://doi.org/10.2307/2978759). Shrunk betas
   (specified, not in this branch).
10. Engle and Granger (1987), Co-integration and error correction: representation, estimation, and
    testing, *Econometrica* 55(2), 251-276, [doi](https://doi.org/10.2307/1913236).
    Cointegration (specified, not built).

## How to cite

[CITATION.cff](CITATION.cff) holds the citation for factordesk itself; GitHub shows it under "Cite
this repository". The methods it implements are cited in
[docs/references.md](docs/references.md). Please also credit Eugene F. Fama and Kenneth R. French
for the factor data.

## Contributing, security and licence

- [CONTRIBUTING.md](CONTRIBUTING.md): how to set up, the code and statistics rules, branches and
  pull requests.
- [SECURITY.md](SECURITY.md): how to report a vulnerability privately.
- [LICENSE](LICENSE): MIT ([decision](wiki/decision-open-source-mit-license.md)).

## Not financial advice

factordesk is a research and education tool. Its output describes how a stock's past returns
related to published factors. It is not investment, tax or legal advice, and it is not a
recommendation to buy or sell anything. Past exposures may not persist.
