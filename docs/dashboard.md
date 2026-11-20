# The dashboard: runbook

Written 2026-11-18. Statements about code are dated: "As of commit f36255e" means the code in that
commit. Check the code if you are on a later commit.

The design source of truth is `docs/design/report-design.md` (look and wording) and
`docs/specs/dashboard.md` (behaviour, API, tickets). This page is a how-to. It does not replace
them.

## What it is

The dashboard is a local web page. You type a ticker, pick a date range and read the same factor
report as the offline HTML file. It runs on your machine. Nothing is hosted and there is no login.

Two parts make it work:

- A FastAPI server (`backend/factordesk/api/`) that fetches prices and factors, runs the
  regression and answers with the report as JSON.
- A React page (`frontend/`) that shows the report and holds the controls.

As of commit f36255e, the server and the page are built and tested against a fake backend. They
have not been run against live Yahoo data (see "Not verified yet" at the end).

## Start it

You need `uv`, and for the page you need Node 26 or newer and npm 12 or newer (these are the
`engines` in `frontend/package.json`).

### Production build, one port

Run these from the repository root:

```text
npm --prefix frontend ci
npm --prefix frontend run build
uv run factordesk serve --open
```

The server prints the address (by default `http://127.0.0.1:8000/`) and `--open` opens it in your
browser. The API and the page share that one port. Build once; run `serve` as often as you like.

Options, as of commit f36255e (`backend/factordesk/cli.py`):

| Option | Meaning |
|---|---|
| `--host HOST` | Address to listen on. Default `127.0.0.1`. |
| `--port PORT` | Port, 1 to 65535. Default `8000`. |
| `--static DIR` | Folder with the built page. Default: `frontend/dist` in a checkout, otherwise the copy shipped inside the package (`factordesk/web`). |
| `--dev` | API only, restarts when Python code changes. The page comes from Vite. |
| `--open` | Open the dashboard in a browser once the server accepts connections. |

If you pass a host that is not a loopback address, the server prints a warning: the dashboard has
no login, so anyone who can reach that address can use it. Keep the default unless you know why
you are changing it.

### Install without cloning (after the first release)

This section depends on factordesk being published on PyPI and on a tagged release that carries
the bootstrap scripts. As of commit ce931c7 neither exists, so the commands below do not work
yet. The wheel is built and tested locally (see `docs/release-checklist.md`). Replace `0.1.0`
with the release you want; there is no "latest" form on purpose, so a run is repeatable.

The wheel contains the built page and the report fonts, so a clean machine needs only uv, not Node
and not a checkout.

If you already have uv:

```text
uvx --from factordesk==0.1.0 factordesk serve --open
```

If you do not have uv, download the script from the release, check it, then run it. Do not pipe
a download into a shell. The release page lists a SHA-256 for each script in `SHA256SUMS`.

macOS and Linux:

```text
curl -fsSLO https://github.com/lbsm2017/factordesk/releases/download/v0.1.0/install.sh
curl -fsSLO https://github.com/lbsm2017/factordesk/releases/download/v0.1.0/SHA256SUMS
grep ' install.sh$' SHA256SUMS      # the published hash; compare it with the next line
sha256sum install.sh                # on macOS: shasum -a 256 install.sh
sh install.sh --version 0.1.0 --expect-sha256 <the hash from SHA256SUMS>
```

Windows PowerShell:

```text
Invoke-WebRequest https://github.com/lbsm2017/factordesk/releases/download/v0.1.0/install.ps1 -OutFile install.ps1
Get-FileHash install.ps1 -Algorithm SHA256     # compare with install.ps1 in the release SHA256SUMS
powershell -ExecutionPolicy Bypass -File .\install.ps1 -Version 0.1.0 -ExpectSha256 <the hash>
```

Both scripts print what they will do before they do it. Add `--dry-run` (`-DryRun` on Windows)
to see the plan and change nothing. They install uv only if it is missing, using uv's own
installer (<https://docs.astral.sh/uv/getting-started/installation/>) at a pinned uv version,
saved to a file first. The `--expect-sha256` check catches a damaged or swapped copy of the
script. It does not help if both the script and the hash came from a compromised page, so read
the script (about 140 lines) if that matters to you.

The cache folder `data/` is created in the folder you run the command from (the default of
`DATA_DIR`). Run it from a folder you are happy to keep cached files in, or set `DATA_DIR`.

### Development, two servers

```text
npm --prefix frontend ci
npm --prefix frontend run dev
```

This starts the API on port 8000 (`uv run factordesk serve --dev`, with reload) and Vite on port
5173 together. Open `http://localhost:5173`. Vite sends `/api` requests to port 8000, so there is
no cross-origin setup. Edits to React files reload the page; edits to Python files restart the
API.

In development only, `/?demo=1` shows the mock report without the API. The demo is not in the
production build.

## How data is fetched and cached

As of commit f36255e:

- **Factors.** The five Fama-French factors come from the Ken French Data Library. The server
  loads the cached file on each request. If none exists, it downloads one. If the cache is more
  than 40 days behind today and the last attempt was over 12 hours ago, it tries a refresh before
  answering that request; a failed automatic refresh keeps the old file.
- **Prices.** Prices come from Yahoo through `yfinance`, one request per ticker for its full
  history. Each ticker is cached on disk for the day as `data/prices/{TICKER}_{YYYY-MM-DD}.parquet`.
  A second request for the same ticker on the same day reads the file.
- **Reports.** Finished reports are also kept in memory, keyed by ticker, dates and the factor
  file's version. `range=3Y` and the same dates typed by hand share one entry. Two browser tabs
  asking for the same report cause one computation.
- **Where files go.** The data folder is `data/` in the folder you start the server from, or the
  value of `DATA_DIR` in `.env`. The folder is gitignored. The server logs the full path at start.
- **Memory caches** reset when you stop the server. Disk caches do not.

Price download settings live in `.env` (see `.env.example`). They apply to the batch download
(`fetch_many`), which the dashboard does not call yet:

| Setting | Default | Meaning |
|---|---|---|
| `PRICE_CHUNK_SIZE` | 5 | Tickers per chunk. |
| `PRICE_MAX_WORKERS` | 3 | Chunks downloaded at once. |
| `PRICE_MIN_INTERVAL_SECONDS` | 0.5 | Minimum time between request starts. |
| `PRICE_MAX_ATTEMPTS` | 3 | Tries per ticker. |
| `PRICE_BREAKER_THRESHOLD` | 3 | Rate-limit replies in a row before the batch stops. |

Yahoo publishes no rate limit. Raising workers or lowering the interval risks being limited. See
`wiki/decision-parallel-throttled-price-downloads.md`.

## What the controls do

All controls sit in one strip above the report.

- **Ticker search.** Type a ticker and press Enter. Suggestions come from tickers already fetched
  on this machine and from your recent tickers. There is no online lookup. Press `/` outside a
  text field to jump to the search box.
- **Range chips.** `3Y`, `5Y` and `Full history`. A chip that cannot work for this ticker is
  disabled, with the reason (a regression needs at least 504 aligned trading days). The page
  opens on Full history.
- **Custom dates.** From and To fields. A complete, valid pair is applied at once. A start after
  the end, or a date after the factor data, shows a sentence and is not sent.
- **Analysed range.** States the dates the numbers cover. Dates after the factor data ends are
  reported as not analysed, as in the offline report.
- **Factor data line.** Says where the factor data ends. "Check for newer factor data" forces a
  download. If it fails, the cached file is kept.
- **Rolling window.** In the exposure-over-time panel, choose 126 or 252 days. Arrow keys move
  between the two.
- **Download report.** A link in the report header. It saves the offline HTML report for the same
  ticker and range.

How presets become dates (`backend/factordesk/api/ranges.py`, as of commit f36255e): the anchor is
the earlier of the last factor date and the last price date. `3Y` starts three calendar years
before the anchor plus one day. `Full history` has no start. Every preset leaves the end open.

## The URL is the state

The address holds what you are looking at, so you can bookmark it or share it:

```text
/?t=SPY&range=3Y
/?t=SPY&start=2023-01-01&end=2026-09-30
/?t=SPY&range=5Y&win=126
```

| Parameter | Values |
|---|---|
| `t` | A ticker: 1 to 12 letters, digits or `. ^ = -`. Case does not matter. |
| `range` | `3Y`, `5Y` or `FULL`. No `range` means Full history. |
| `start`, `end` | ISO dates, `YYYY-MM-DD`. They win over `range`. |
| `win` | `126` or `252`: the rolling window. |

Invalid values are dropped, not shown as errors. Reloading the page restores the same view. The
server answers any address outside `/api` with the page, so a reload on `/?t=SPY` works.

## The offline report is the export

The offline HTML report stays. It is a single file that works without the server, and it is the
way to keep a result. Two ways to get it:

- Click "Download report" in the dashboard. The server calls
  `GET /api/report/{ticker}/html` with the same range.
- Run `uv run factordesk report SPY --open` with no server.

Both use the same Python renderer. Real-data reports stay on your machine; the repository holds
only the synthetic sample `docs/samples/mock_report.html`.

## The API

As of commit f36255e, all routes are under `/api` (`backend/factordesk/api/`):

| Route | Purpose |
|---|---|
| `GET /api/health` | Liveness, version and schema version. Reads no disk and no network. |
| `GET /api/factors/status` | Coverage and age of the cached factor file. |
| `POST /api/factors/refresh` | Force a factor download. Calls made together join one download. |
| `GET /api/tickers?q=&limit=` | Already-fetched tickers by prefix, newest first. No network call. |
| `GET /api/report/{ticker}/ranges` | Which presets are available, with the reason when one is not. |
| `GET /api/report/{ticker}?range=` or `?start=&end=` | The report. Neither means Full history. |
| `GET /api/report/{ticker}/html` | The offline HTML report as a download. |

Every error body has a `code`, a `message` and an `action`, in plain sentences. An unknown `/api`
path returns 404 in the same shape. The OpenAPI document is committed at
`frontend/src/api/openapi.json`; CI fails if the generated types differ from the backend models.

## Troubleshooting

Each problem below ends in one line on stderr or one message on the page.

**"port 8000 on 127.0.0.1 is already in use".** Another program, or another copy of `serve`, has
the port. Stop it, or choose another: `uv run factordesk serve --port 8001`. In development,
Vite needs port 5173 and the API needs 8000; both must be free.

**"the dashboard is not built; run 'npm --prefix frontend run build' first, or use --dev (API
only)".** `frontend/dist/index.html` is missing. Build the page, or use `npm --prefix frontend
run dev`. If you passed `--static DIR`, the message names that folder instead.

**"Yahoo Finance refused the request. Wait a minute, then try again."** Yahoo is limiting
requests from your connection. Wait a minute and try the ticker again. Do not retry in a loop.
Reports for tickers already fetched today still load from the cache.

**"No prices were returned for X."** The ticker is unknown to Yahoo, or delisted. Check the
symbol (for example `BRK-B`, not `BRK.B`).

**"X has N trading days in this range that line up with the factor data; at least 504 ... are
needed."** The ticker is too new or the range too short. Choose Full history.

**"factordesk could not reach the data source."** Check your network connection. If the factor
download failed, the old file is kept.

**Factor data looks old.** The page says where the factor data ends. The library publishes with a
delay, so the last factor date is always behind today. The server refreshes by itself once the
cache is more than 40 days behind. To force it now, use "Check for newer factor data" or run
`uv run factordesk factors refresh`. `uv run factordesk factors status` prints the age.

**"The downloaded factor file failed validation; the previous copy was kept."** The download was
not in the expected shape. Nothing was replaced. Try again later.

**Stale numbers after a code change.** Memory caches reset when the server restarts. The price
cache is per day; delete the file in `data/prices/` to force a new download.

## Run the tests on a laptop

Python, from the repository root:

```text
uv sync
uv run ruff check
uv run pyright
uv run pytest -q
```

No test calls Yahoo or the French library by default. Live tests are deselected.

Frontend, with `npm --prefix frontend ci` run once:

```text
npm --prefix frontend run typecheck
npm --prefix frontend run lint
npm --prefix frontend run test
npm --prefix frontend run build
```

Browser smoke test (end to end):

```text
npm --prefix frontend run build
npm --prefix frontend run e2e
```

On a laptop, the test uses the Google Chrome you have installed. In CI it uses Playwright's
Chromium (`npm --prefix frontend run e2e:install` installs it). The test starts the fake backend
itself on port 8765 (`backend/factordesk/tests/fixtures/fake_app.py`): the real application with a
fake price provider, a synthetic history, a fixed clock and an empty temporary data folder. It
makes no network call, and the test fails if the page asks for any host other than 127.0.0.1.
Screenshots from a run go to `frontend/shots/` (gitignored).

If you change a backend model, regenerate the API types:

```text
uv run python -m factordesk.api.openapi_dump frontend/src/api/openapi.json
npm --prefix frontend run gen:types
```

### CI

As of commit f36255e, `.github/workflows/ci.yml` runs on pull requests to `dev` and `prod`:

- `python`: ruff, pyright and pytest on Ubuntu and Windows.
- `frontend`: typecheck, lint, test, build, and a check that the generated API types match.
- `e2e`: the browser smoke test, after the other two pass.

On 2026-11-20 the owner removed the nightly workflow: GitHub runs tests for pull requests only. The
tests that the pytest defaults skip now run by hand before each release:

- `slow`: `uv run pytest -m slow` (Monte Carlo and seed sweeps). A failure blocks the release.
- `live`: `uv run pytest -m live` (3 tests that call Yahoo and the Ken French library). A failure
  is reported in the release PR.

See [the decision](../wiki/decision-nightly-slow-tests.md).

## Not verified yet

As of commit f36255e:

- The dashboard has not been run against real Yahoo data. The tests use the fake backend.
- The design and accessibility review (ticket T11 in `docs/specs/dashboard.md`) has not been
  done.
- The peer comparison does not exist yet. It is meant to use the batch price download.
