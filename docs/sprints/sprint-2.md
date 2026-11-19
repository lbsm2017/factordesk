# Sprint 2: portfolio composer

Dates: 2026-11-20 (one day)
Status: closed. Release `v0.3.0` (pending the owner's merge of the release PR).
Previous: [Sprint 1](sprint-1.md). Backlog: [Sprint 2 backlog](sprint-2-backlog.md).

## Goal

A user can build a strategic asset allocation (SAA) portfolio in the dashboard, backtest it with monthly rebalancing, and read its factor report. The tree is modelled on the Venn/Risk Pro SAA tree.

## What shipped

| Item | What |
|---|---|
| S2-1 Hygiene | Timed log lines for each server step (uploads log only row count and frequency). A warning at `serve` start when the dashboard page is older than its source. Vitest limited to 3 workers locally. A tests note in CONTRIBUTING. |
| S2-2 Tree model and Asset Class Library | The portfolio tree JSON, defined in pydantic and TypeScript. The owner's 44-line Asset Class Library, with a checked proxy per line. `GET /api/portfolio/library`. |
| S2-3 Portfolio API | `POST /api/report/portfolio`. It flattens the tree, backtests it with monthly rebalancing and cost, and runs the factor report on the portfolio series. Results are cached in memory only. 422 refusals. A one-day data gap is compounded instead of refused. |
| S2-4 Composer | Portfolio mode. Split view with the allocation tree and a live check panel. Library picker. Swappable and multiple instruments per line. Typed weights with share bars. Normalise and remainder-to-cash actions. Several named portfolios with undo on delete. Presets: Blank, 60/40, Balanced SAA, Growth. Asset-class colours. The composer collapses after Run. |
| S2-5 Portfolio report | A Backtest card showing the window, the holdings that limit it, rebalances, cost, unallocated weight and the survivorship note. Sections that do not fit a portfolio are hidden. |
| E4 Macro sensitivities (added mid-sprint by the owner) | A separate regression on market, rates (IEF−RF), credit (LQD−IEF), commodities (DBC−RF), inflation (TIP−IEI) and the US dollar (Fed broad index, FRED). Daily data uses a one-day lag on the dollar. The section is available for every subject. |
| Library proxy update | Crypto BTC-USD, ex-precious commodities DBC, private credit BKLN, generic inflation-linked TIP. Unhedged labels on non-USD bonds. |
| Docs | [Reference-currency method notes](../research/reference-currency-and-benchmarks.md). |

## Owner decisions

- **Library and proxies.**
  - USD cash uses the French risk-free rate. EUR and CHF cash use FXE and FXF.
  - Alternatives get a listed proxy only where one honestly fits; the other lines show "no proxy yet".
  - Instruments at 0% weight never shorten the backtest window.
- **Composer.** The design was approved as a mockup first, then as a build.
- **Bonds.** Non-USD bonds stay unhedged in version 1. Hedging comes with the USD/EUR reference-currency epic.
- **Owner research files.** The benchmark-mapping research files stay local, because they name the owner's firm. A summary without firm names is in the repository.
- **Agent limits.** The parallel-agent limit was raised to 6. Default subagent model: Sonnet. Opus does only the statistics reviews and coordination.

## Validation (localhost demo, real data, 2026-11-20)

| Portfolio | Result |
|---|---|
| 60/40 (IVV/IEF) | Market beta +0.56, R² 93%, alpha −0.6% (could be noise). Backtest from Jul 2002, 292 monthly rebalances. |
| Balanced SAA (13 lines) | Market beta +0.61, R² 90.6%, alpha −1.2%/yr. Backtest from Apr 2007, limited by HYG. Macro: rates +0.31, credit +0.19, US dollar −0.27. |
| SPY macro panel | Market +0.96; rates, credit, commodities, inflation and dollar all close to 0. |

Every merge had green CI. The portfolio API and the macro section had an independent correctness review; their findings were fixed before merge. The golden ticker report was unchanged throughout.

## Retro

**Went well**

- The mockup-first checkpoint meant the build matched what the owner wanted the first time.
- The parallel lanes (model, API, composer, macro, hygiene) merged with few conflicts.
- The reviews caught real issues:
  - a one-day data gap refused a whole portfolio;
  - a fund was wrongly named as limiting the macro window;
  - every report waited 40 s while FRED was down.

**Problems and fixes**

| Problem | Fix |
|---|---|
| Dev CI went red twice after direct merges: a Vitest config type error, and a test that pinned a ticker | Before every direct merge, run the typecheck, the linter and the full frontend unit tests, not only the backend tests. Tests derive expected values from data instead of fixing literals. |
| Mid-sprint scope additions (macro section, library proxies) took the load to about 95% | The holdings table and CSV import/export moved to the backlog, as the cut order planned. |
| A left-over local server on port 8765 kept failing one test | Stop demo servers within the same command. Free the port. |
| Tail risk used the full history while the analysis used the selected range | Fixed before release: tail risk now uses the analysed window. |
