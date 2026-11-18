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

Status (2026-11-18): the SPY slice, the offline report and the CLI are built; the dashboard is built
and in review in PR #1, not yet merged into `dev`; the newer analytics sections are not built (see
[Method status](#method-status)). Alpaca is not used in v1 (yfinance only); the `.env` keys are
placeholders for a later adapter.

## What it does

One ticker in, one factor profile out. The report shows the price, each factor beta with a 95%
interval (tagged *reliable* or *noise* after correcting for five tests), where the return and the
risk came from, rolling betas, and a data-and-audit panel with every caveat. The panel list is in
[docs/overview.md](docs/overview.md#what-the-report-shows).

- **Dashboard.** A local web page with a ticker search, range chips (3Y, 5Y, Full history), custom
  dates and a factor refresh. It runs on your machine, with no login, and nothing is hosted.
  Runbook: [docs/dashboard.md](docs/dashboard.md).
- **Offline HTML report.** One self-contained file from `uv run factordesk report SPY --open`.
  Example with made-up numbers: [docs/samples/mock_report.html](docs/samples/mock_report.html).

## Method on one screen

For each day, the stock's excess return is regressed by OLS on the five Fama-French factors
(Mkt-RF, SMB, HML, RMW, CMA) over the days where prices and factors overlap
([Fama and French 2015](https://doi.org/10.1016/j.jfineco.2014.10.010)). Inference uses
Newey-West HAC standard errors; the five betas are corrected together with Benjamini-Hochberg at 5%;
rolling betas use only past days; return and risk attribution add up exactly; a data-quality gate
flags closing prices that are not synchronous with the factor data. Details and links to the exact
rules: [docs/overview.md](docs/overview.md#method-in-detail).

### Method status

As of 2026-11-18 (from [docs/ROADMAP.md](docs/ROADMAP.md) and git): the regression, rolling betas,
attribution, residual diagnostics and quality gate are built and were independently validated on
SPY. Residual alpha, shrunk betas, Kalman betas, fragility score and lead-lag betas are specified;
none is merged here (the report has empty slots for them), and fragility and lead-lag are not
started. Dominant-factor shading, drift alerts, regime betas, cointegration and regional factors
are specified and not built. The table is in
[docs/overview.md](docs/overview.md#method-status).

## Scientific rigour

The [research protocol](docs/research-protocol.md) is the rule: write the hypothesis and the exact
test down before results, enter every run in an append-only
[test registry](docs/registry/tests.jsonl), correct for multiple tests, report power, and never use
data from after the date a result is stamped. The registry shows that the quality-gate threshold
was written after 13 inspection runs, so it is a documented heuristic and not a pre-registered
test; the protocol applies from now on. Also in place: an independent recomputation of the SPY
report and mutation testing ([validation](docs/validation/)), a written
[test oracle](docs/test-oracle.md), pinned lockfiles and fixed seeds, and a bibliography where every
source was checked. Details: [docs/overview.md](docs/overview.md#scientific-rigour-in-practice).

**Limitations.** The results are descriptive and in-sample, not forecasts. The factor file lags by a
month or more. US factors only. SPY's early Yahoo closes carry timing noise that the gate flags but
does not remove. Yahoo prices are for personal use. The full list is in
[docs/overview.md](docs/overview.md#limitations); some claims in the repository have no source and
are listed in [docs/references.md](docs/references.md#claims-in-the-repo-without-a-source).

## Data sources and licences

| Source | Used for | Terms |
| --- | --- | --- |
| [Kenneth R. French Data Library](https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html) | Every factor return and the risk-free rate | The page carries a copyright notice by Eugene F. Fama and Kenneth R. French; no terms page was found on 2026-11-18. We credit them. |
| Yahoo Finance, through [yfinance](https://ranaroussi.github.io/yfinance/) | Daily prices, dividends and splits of the analysed ticker | Yahoo's terms forbid commercial use and collecting data by automated means without permission. The yfinance README says the Yahoo Finance API is "intended for personal use only". No source grants research use, and factordesk obtains no permission from Yahoo for you. The project is personal use only. |

The wording of both is quoted and dated in [docs/references.md](docs/references.md). Neither dataset
is committed: `data/` and `.env` are gitignored, and real-data sample reports stay local
([decision](wiki/decision-no-data-and-no-secrets-in-the-repo.md)). You are responsible for following
the providers' terms when you run factordesk.

factordesk is not affiliated with, endorsed by or vetted by Yahoo, the yfinance project, Dartmouth
College, Kenneth R. French or Eugene F. Fama ([decision](wiki/decision-project-name-factordesk.md)).

## Setup

factordesk runs on Windows, macOS and Linux. The only prerequisite is
[uv](https://docs.astral.sh/uv/), which also installs a suitable Python (3.12 or newer) for you. You do not
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
a Python 3.12 or newer if none is installed. The same command works on every system. Run it again after each
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

The page needs Node 26 or newer and npm 12 or newer, and is built once (build again after pulling frontend changes). The server listens on
`127.0.0.1:8000` by default; keep it there, because the dashboard has no login. Options and the
development setup are in [docs/dashboard.md](docs/dashboard.md).

### Keep the factor data up to date

The first report downloads the factor file from the
[Kenneth R. French Data Library](https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html)
and caches it in `data/`. The library publishes with a lag of a month or more, so the last few
weeks of prices are always shown in the chart but left out of the regression. factordesk
refreshes the file by itself once it is more than 40 days old. To check or refresh it by hand:

```bash
uv run factordesk factors status    # date range, age and source of the cached file
uv run factordesk factors refresh   # download the latest file now
```

Prices are cached in `data/` for the day, so running the same ticker again is fast. Delete
`data/` at any time to start clean; it is rebuilt on the next run.

### If something goes wrong

Every failure ends with one line containing `error:` that says what to do (usage errors print the
usage first), and the exit code tells scripts what kind of problem it was:

| Exit code | Meaning |
| --- | --- |
| 0 | Success |
| 1 | Data problem: unknown ticker, too little history, or a factor file that failed validation |
| 2 | Wrong command or option (run `uv run factordesk --help`), or `serve` cannot start (page not built, port in use) |
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
`uv run pytest -m slow`. Frontend checks, after `npm --prefix frontend ci`: `npm --prefix frontend test`.

## Documentation map

| Where | What it holds |
| --- | --- |
| [wiki/index.md](wiki/index.md) | Every decision in plain English: what, why, cost |
| [wiki/glossary.md](wiki/glossary.md) | Plain definitions of alpha, HAC, point-in-time and the rest |
| [docs/overview.md](docs/overview.md) | Method, status, rigour and limitations in detail |
| [docs/methodology.md](docs/methodology.md) | The binding statistical rules (M0 to M16) |
| [docs/research-protocol.md](docs/research-protocol.md) | Pre-registration, correction, power, robustness |
| [docs/test-oracle.md](docs/test-oracle.md) | The tests and their tolerances |
| [docs/specs/](docs/specs) | Feature specifications: dashboard, schema contract, and the sections not yet built |
| [docs/design/report-design.md](docs/design/report-design.md) | Look, wording and accessibility of the report |
| [docs/validation/](docs/validation) | Independent validation and hardening closure |
| [docs/ROADMAP.md](docs/ROADMAP.md) | What is built, in progress and planned |
| [docs/references.md](docs/references.md) | Verified bibliography, sources and terms; [BibTeX](docs/references.bib) |
| [docs/dashboard.md](docs/dashboard.md) | Dashboard runbook |
| [docs/release-checklist.md](docs/release-checklist.md) | Steps for a release |

## Key references

Verification means a work exists with these details, not that each paper's text was checked against
how the repository uses it. Full entries, with titles, are in
[docs/overview.md](docs/overview.md#key-references) and [docs/references.md](docs/references.md).

1. Fama and French (2015), *J. Financial Economics* 116(1), [doi](https://doi.org/10.1016/j.jfineco.2014.10.010): the model.
2. Fama and French (1993), *J. Financial Economics* 33(1), [doi](https://doi.org/10.1016/0304-405X(93)90023-5): the three-factor model.
3. French, [Kenneth R. French Data Library](https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html): factor data.
4. Newey and West (1987), *Econometrica* 55(3), [doi](https://doi.org/10.2307/1913610): HAC errors.
5. Benjamini and Hochberg (1995), *J. Royal Statistical Society B* 57(1), [doi](https://doi.org/10.1111/j.2517-6161.1995.tb02031.x): multiple testing.
6. Dimson (1979), *J. Financial Economics* 7(2), [doi](https://doi.org/10.1016/0304-405X(79)90013-8): lead-lag betas (specified).
7. Scholes and Williams (1977), *J. Financial Economics* 5(3), [doi](https://doi.org/10.1016/0304-405X(77)90041-1): lead-lag cross-check (specified).
8. Kalman (1960), *J. Basic Engineering* 82(1), [doi](https://doi.org/10.1115/1.3662552): Kalman betas (specified).
9. Vasicek (1973), *J. Finance* 28(5), [doi](https://doi.org/10.2307/2978759): shrunk betas (specified).
10. Engle and Granger (1987), *Econometrica* 55(2), [doi](https://doi.org/10.2307/1913236): cointegration (specified).

## How to cite, contribute, licence

[CITATION.cff](CITATION.cff) holds the citation for factordesk itself (GitHub: "Cite this
repository"); please also credit Eugene F. Fama and Kenneth R. French for the factor data.
[CONTRIBUTING.md](CONTRIBUTING.md) covers setup, rules and pull requests; [SECURITY.md](SECURITY.md)
says how to report a vulnerability privately; [LICENSE](LICENSE) is MIT
([decision](wiki/decision-open-source-mit-license.md)).

## Not financial advice

factordesk is a research and education tool. Its output describes how a stock's past returns
related to published factors. It is not investment, tax or legal advice, and it is not a
recommendation to buy or sell anything. Past exposures may not persist.
