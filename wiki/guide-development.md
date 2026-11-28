# Developing factordesk

Last updated 2026-11-28. The code layout, the test and quality commands, and what is built and what is next. The rules for pull requests are in [CONTRIBUTING.md](../CONTRIBUTING.md).

## Project layout

```text
backend/factordesk/
  analytics/      regression, rolling, attribution, Kalman, shrinkage, residual, performance,
                  world beta, macro, energy, tail risk, currency, backtest, portfolio attribution
  data/           prices (Yahoo), factors (Ken French), FRED, ECB, SNB, exchange and cash rates,
                  uploads, the asset-class library, caching, the price audit
  report/         the typed report schema and the offline HTML renderer
  section_hooks/  which report sections run for which model and mode
  api/            FastAPI routes, progress streams, range presets, error mapping, the static page
  pipeline.py     from ticker to report
  cli.py          the factordesk command
frontend/         React and TypeScript dashboard (Vite)
docs/             methodology, specs, design, reviews, validation, sprints, roadmap
wiki/             user guides and every decision in plain English
```

## Tests and quality checks

```bash
uv run pytest                 # fast tests; network and Monte Carlo tests are opt-in
uv run pytest -m live         # tests that use the network
uv run pytest -m slow         # Monte Carlo and seed-sweep tests
uv run ruff check backend
uv run ruff format --check backend
uv run pyright
```

Frontend, after `npm --prefix frontend ci`:

```bash
npm --prefix frontend run typecheck
npm --prefix frontend run lint
npm --prefix frontend test
npm --prefix frontend run build
npm --prefix frontend run size     # bundle budget: 540 kB raw, 166 kB gzip
npm --prefix frontend run e2e      # Playwright, against a fake backend
```

The same checks have short names (`uv run poe test`, `uv run poe check`, `uv run poe ci`), listed in
[Install and use factordesk](guide-install-and-use.md#shortcuts).

GitHub CI runs the Python checks on Ubuntu and Windows, the frontend checks and the end-to-end
tests on every pull request, and only there. The slow and live tests run by hand before each
release: `uv run pytest -m slow` and `uv run pytest -m live`.

## Status and roadmap

As of 2026-11-21, version 1.0.0, the first public release:

| Built and independently validated | Specified, not built |
| --- | --- |
| Five- and six-factor regression with HAC errors and BH correction | Fragility score ("this alpha rests on N days") |
| Alpha across CAPM, FF3, FF5 and FF6 | Lead-lag (Dimson, Scholes-Williams) betas |
| Return and risk attribution | European natural gas (TTF) in the energy panel |
| Rolling, Kalman and shrunk betas | Factor regions beyond the US and developed Europe |
| Price audit and quality gate | Offline report in the dashboard's design, in EUR |
| Residual alpha, in-sample and point-in-time | Currency, factor set and model options on the command line |
| Historical performance, drawdowns and tail risk | Peer comparison |
| World beta, macro sensitivities, energy and carbon | One-line install from a published release |
| Track-record upload | |
| Portfolio composer and backtest | |
| USD or EUR view, 11 listing currencies | |
| US or Developed Europe factors | |
| Dashboard with progress steps and a dark theme | |

What shipped in each sprint is in [docs/sprints/](../docs/sprints). Priorities, effort and owner
decisions are in [docs/ROADMAP.md](../docs/ROADMAP.md).
