# Install and use factordesk

Last updated 2026-11-28. How to install factordesk on Windows, macOS or Linux, and every command, option and API route it offers. The short version is in the [README](../README.md#quick-start).

## Installation

factordesk runs on Windows, macOS and Linux. The only prerequisite for the command line is
[uv](https://docs.astral.sh/uv/), which also installs a suitable Python (3.12 or newer). You do not
need a system Python, conda or make. The dashboard also needs Node 26 or newer and npm 12 or newer
to build the page once ([decision](decision-python-and-uv-for-every-platform.md)).

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

`uv sync` creates a local `.venv`, installs the exact versions pinned in `uv.lock`, and downloads
Python 3.12 or newer if none is installed. Run it again after each `git pull`.

### 3. Check that it works

```bash
uv run factordesk --help
```

You should see the `report`, `factors` and `serve` commands. `uv run` runs a command inside the
project environment, so you never need to activate `.venv` yourself. Copy `.env.example` to `.env`
only if you need to override settings; `.env` is gitignored.

## Shortcuts

Run all commands from the `factordesk` folder. Common commands have short names. They run through
uv, so they work the same on Windows, macOS and Linux; `uv run poe` with no task lists them all. If
you have make, the same shortcuts work as `make <task>`.

| uv (every system) | make | What it does |
| --- | --- | --- |
| `uv run poe setup` | `make setup` | Install the page's dependencies and build the page (run `uv sync` first; `make setup` does it for you) |
| `uv run poe serve` | `make serve` | Start the dashboard on port 8000 and open it |
| `uv run poe serve --port 8080` | `make serve PORT=8080` | Start it on another port |
| `uv run poe stop` | `make stop` | Stop the dashboard on port 8000 (`--port` or `PORT=` for another port) |
| `uv run poe report SPY` | `make report T=SPY` | Write an offline report and open it |
| `uv run poe factors` | `make factors` | Show the cached factor file's range and age |
| `uv run poe refresh-factors` | `make refresh-factors` | Download the latest US factor file and the files behind the shrunk-beta prior |
| `uv run poe build` | `make build` | Rebuild the page after frontend changes |
| `uv run poe dev` | `make dev` | API with reload, for frontend work (run `npm --prefix frontend run dev` beside it) |
| `uv run poe test` | `make test` | Python and frontend unit tests |
| `uv run poe check` | `make check` | Lint, format and type checks, as CI runs them |
| `uv run poe e2e` | `make e2e` | Browser tests (Playwright) against a fake backend |
| `uv run poe ci` | `make ci` | Every CI gate: checks, tests, build, bundle size, browser tests |

`stop` only stops a factordesk server: it first checks that the port answers like factordesk, so it
never stops another program on that port.

## The dashboard

```bash
npm --prefix frontend ci            # once
npm --prefix frontend run build     # once, and again after pulling frontend changes
uv run factordesk serve --open
```

| Option | What it does |
| --- | --- |
| `--port PORT` | Port to listen on (default 8000). |
| `--host HOST` | Address to listen on (default `127.0.0.1`). Keep it local: the dashboard has no login, and a non-loopback address prints a warning. |
| `--open` | Open the dashboard in a browser once the server is ready. |
| `--dev` | API only, restarting on code changes; the page comes from the Vite dev server. |
| `--static DIR` | Serve the built page from another folder. |

`serve` warns when the built page is older than its source, so you know to run the build again. The
runbook, with the development setup, caching rules and troubleshooting, is
[docs/dashboard.md](../docs/dashboard.md). What each panel shows is in the
[dashboard tour](guide-dashboard.md).

## An offline report

```bash
uv run factordesk report SPY --open
```

This writes `SPY_report.html` to the current folder and opens it. The terminal prints a one-line
summary:

```text
SPY: n = 8474, 1993-02-01 to 2026-09-30 (factors through 2026-09-30); R2 = 0.9673
Wrote .../SPY_report.html
```

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

The command-line report covers a ticker quoted in US dollars, with the US five-factor model. The
euro view, the Europe factors, track records and portfolios are in the dashboard and the API.
Tickers use Yahoo Finance symbols, so a class B share is `BRK-B`, not `BRK.B`. A ticker needs about
two years of daily history that overlaps the factor data. An example report with made-up numbers is
in [docs/samples/mock_report.html](../docs/samples/mock_report.html). The offline report keeps the
earlier report design for now; giving it the dashboard's look is on the roadmap.

## Factor data

```bash
uv run factordesk factors status    # date range, age and source of the cached US file
uv run factordesk factors refresh   # download the latest US file now
```

The Europe and momentum files are downloaded the first time they are needed and cached in `data/`.
Prices are cached in `data/` for the day. Delete `data/` at any time to start clean; it is rebuilt
on the next run. Where each file comes from, and its terms, is in
[Data sources and their terms](guide-data-sources.md).

## The API

The dashboard talks to a small JSON API on the same port. All routes are under `/api`.

| Route | What it returns |
| --- | --- |
| `GET /api/health` | Liveness, version and schema version. |
| `GET /api/factors/status` | Coverage and age of the cached factor file. |
| `POST /api/factors/refresh` | Force a factor download. |
| `GET /api/tickers?q=&limit=` | Tickers already fetched, by prefix, with names. |
| `GET /api/report/{ticker}/ranges` | Which presets are available, with the reason when one is not. |
| `GET /api/report/{ticker}?range=` or `?start=&end=` | The full report as JSON. |
| `GET /api/report/{ticker}/stream` | The same report with progress steps, as server-sent events. |
| `GET /api/report/{ticker}/html` | The offline HTML report as a download (USD). |
| `POST /api/report/upload` | A track-record report from a CSV file (multipart: `file`, `name`, `gross_net`, `record_currency`). |
| `POST /api/report/portfolio` | A portfolio backtest and report from a portfolio tree (JSON). |
| `GET /api/portfolio/library` | The asset-class library with its proxy ETFs. |

The report routes also take `model=ff5|ff6`, `ccy=USD|EUR` and `factor_set=us|europe`. The API
defaults to `ff5` for tickers and uploads and to `ff6` for portfolios; the dashboard always sends
its choice. The upload and portfolio routes each have a `/stream` variant with progress steps. The
schema is in `frontend/src/api/openapi.json`. An unknown ticker returns 404 with a plain message; a
ticker quoted in an unsupported currency returns 422 `unsupported_currency`; an upload over 1 MB
returns 413.

## If something goes wrong

Every command-line failure ends with one line containing `error:` that says what to do, and the
exit code tells scripts what kind of problem it was:

| Exit code | Meaning |
| --- | --- |
| 0 | Success |
| 1 | Data problem: unknown ticker, too little history, a currency the command line does not support, or a factor file that failed validation |
| 2 | Wrong command or option (run `uv run factordesk --help`), or `serve` cannot start (page not built, port in use) |
| 3 | Network problem, or Yahoo Finance refused the request (try again later) |
| 4 | The output folder cannot be written (or is inside `data/`, which is not allowed) |
