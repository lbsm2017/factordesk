# Real-data smoke test of the dashboard, 2026-11-18

Scope: `factordesk serve` on port 8123 against real cached data (SPY prices fetched 2026-11-18, Fama-French 5-factor file downloaded 2026-11-18, data through 2026-09-30), driven with curl, an in-process client and Playwright (Chrome). One extra Yahoo call was made, for QQQ, through the page. No unknown-ticker request was sent to Yahoo, so the 404 `unknown_ticker` path is covered only by the fake-provider tests.

Machine note: other jobs were running on the same machine, so every time below is an upper bound.

## Checked and fine

- Response shape: `/api/report/SPY` (Full, 3Y, 5Y and custom dates), `/ranges` and `/api/health` validate against `FactorReport`, `RangeOptions` and `Health` (`model_validate_json`).
- Same numbers as the CLI: the JSON of `factordesk report SPY --json` equals `/api/report/SPY` except `generated_at`. The HTML download is byte-identical to the CLI's `SPY_report.html`. Full history in the page gives n = 8,474, alpha -0.58%, R2 0.9673, residual volatility 3.3%, the same as the static report.
- `range=FULL` and no range give identical bodies and one cache entry.
- In-flight de-duplication: three simultaneous identical requests for a new range gave one `assemble_report` call, one price fetch and one factor load per request cycle (counted in process).
- Errors are plain sentences with `code`, `message` and `action`: bad ticker (422), bad range, both range and dates, bad date, start after end, end before first return (all 400), too little history (422), unknown API path (404).
- Page: `/?t=SPY` loads KPI strip, equation, price panel, rolling panel and notice; chips 3Y, 5Y and Full history change the URL and the numbers; `win` survives chip changes and reloads; custom From and To dates update the URL; a start after the end shows an inline message and keeps the URL; browser back restores the previous range; Download report keeps the range; ticker suggestions show SPY; no foreign requests; no console errors other than the browser's own line for the expected 422; no horizontal overflow at 1440 and 390 px.

## Timings (SPY, cached prices, this loaded machine)

| Request | Time |
|---|---|
| `/api/health` | 0.01 s |
| `/api/factors/status` first call | 0.67 s |
| Full history, cold | 15.9 s (9.6 s in process) |
| 3Y cold | 0.87 s |
| 5Y cold | 1.45 s |
| Full, warm (cached) | 0.05 to 0.09 s |
| HTML download | 0.5 s |
| Custom range of about 30 years, new key | 5 to 7 s |
| Page, first KPIs, warm server | about 2 s |
| QQQ through the page, cold, with Yahoo | 23.5 s |
| `factordesk serve` until listening | about 17 s (imports) |

## Findings

### F1. Counts lost their thousands separator in two places (fixed)

What: the range line under the controls said "The first 7722 price days are also not analysed" and the Data and audit panel said "8474 trading days", while the KPI strip said "8,474".
Evidence: Playwright text of `#analysed-range` and `#data` on Full and 3Y history of SPY.
Status: fixed. A shared `count()` in `frontend/src/format/numbers.ts` is used by the range line and the Data and audit facts. Regression tests in `format.test.ts`, `controls.test.tsx` and `DataAuditPanel.test.tsx`.
Commit: 0e37aec.

### F2. Full-history report is slow to compute (open, not in scope)

What: a Full-history result takes 10 to 16 s cold, and every new long custom range takes 5 to 7 s. About two thirds is `rolling_ols_hac` (`einsum` in `backend/factordesk/analytics/rolling.py`), the rest the residual diagnostics.
Evidence: cProfile of `assemble_report` for SPY Full: `rolling_betas` 27.6 s of 40.5 s under the profiler, `acorr_*` 7.9 s.
Status: open. The page shows a loading state meanwhile, and repeat requests are served from cache. A fix touches statistics code, so it was not attempted.

### F3. SPY over Full history fires the residual-reversal gate (open, data or method question)

What: SPY Full history carries the "Prices look out of step with the factor data" warning (lag-1 residual autocorrelation -0.40, robust z -13.1, estimated noise share 81%). The same autocorrelation is present in every sub-period (1993 to 2000 -0.42, 2001 to 2008 -0.42, 2009 to 2016 -0.38, 3Y -0.35, 5Y -0.25), yet the gate fires only on long samples because the robust z is -2.2 for 3Y and -2.3 for 5Y. So the 3Y and 5Y views show no warning although rho is below the -0.2 threshold.
Evidence: `quality_gate` blocks of `/api/report/SPY`, `?range=3Y`, `?range=5Y`.
Status: open. No statistic or threshold was changed. The owner should decide whether SPY (the README ticker) should be explained in the docs, and whether a z that depends so much on sample length is the right trigger.

### F4. Price panel side readout describes the whole price history, not the zoomed window (open, design question)

What: on 3Y the chart is zoomed to about mid 2023 onward, but the side list says "First 29 Jan 1993 24.05". It matches the series and the "Show full history" button, so it may be intended.
Status: open, no change made.

### F5. Static-file 404 body is not an `ApiError` (open, left as is)

What: `/assets/missing.js` answers `{"detail":"Not Found"}`. `test_missing_asset_is_404_not_index` pins the status; no browser shows the body. Left unchanged.

### F6. Server start takes about 17 s here (open)

What: importing `factordesk.api.main` takes about 17 s on this machine (statsmodels, scipy, pandas), mostly cold disk and a busy machine. `localhost` in curl also took 2.2 s the first time on Windows (IPv6 first); the server prints and the page uses `127.0.0.1`, so users following the printed URL are not affected.
Status: open, informational.

## Gates

`uv run pytest -q` 452 passed; `ruff check backend` clean; `pyright` 0 errors; frontend `typecheck`, `lint`, `test` (317 passed), `build` and `e2e` (1 passed) green.
