# factordesk

factordesk is a terminal-style dashboard for Fama-French 5-factor analysis of a single stock.
Type a ticker and press **Factor it**: the backend downloads daily prices (yfinance) and the
public Ken French 5-factor daily data, regresses the stock on the factors, and returns a typed
report with factor-dominance shading, beta, return and risk attribution, and cointegration
panels. Design and methodology live in `docs/PLAN.md`.

Factor data comes from the
[Kenneth R. French Data Library](https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html),
which is the source of truth for every factor definition. Prices come from Yahoo Finance through
yfinance. Neither dataset is stored in this repository; both are downloaded when you run it. See
[docs/references.md](docs/references.md) for sources, papers and terms.

Status: backend foundations only. The frontend and analytics are not built yet.
Alpaca is not used in v1 (yfinance only); the `.env` keys are placeholders for a later adapter.

## Setup

factordesk runs on Windows, macOS and Linux. The only prerequisite is
[uv](https://docs.astral.sh/uv/), which also installs the right Python (3.12) for you. You do not
need a system Python, conda or make.

**1. Install uv** (once)

| System | Command |
|---|---|
| macOS, Linux | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| Windows (PowerShell) | `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 \| iex"` |
| Any (package managers) | `brew install uv` or `winget install --id=astral-sh.uv` |

**2. Get the code and its dependencies**

```bash
git clone <repo-url>
cd factordesk
uv sync
```

`uv sync` creates a local `.venv`, installs the pinned dependencies from `uv.lock`, and downloads
Python 3.12 if it is missing. The same command works on every system.

Copy `.env.example` to `.env` if you need to override settings. `.env` is gitignored.

## Tests and checks

```bash
uv run pytest
uv run ruff check .
uv run pyright
```

Tests that use the network are marked `live` and are skipped by default. Run them with
`uv run pytest -m live`.

## Run the API (once it exists)

```bash
uv run uvicorn factordesk.api.main:app --reload
```
