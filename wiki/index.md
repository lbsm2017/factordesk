# factordesk wiki

Last updated 2026-11-20. This is the project's knowledge base. Its main purpose is to record each decision in plain English: what we decided, why, how it works, and what we gave up. Pages date their claims, and facts that depend on `docs/` link to the source document instead of copying it.

## Start here

- [Glossary](glossary.md): plain-English definitions of every term used in the wiki, from alpha to the five factors.
- [README](../README.md): what factordesk is and how to run it.
- [Methodology specification](../docs/methodology.md): the exact statistical rules the decisions below summarise.
- [Plan](../docs/PLAN.md): the approved architecture and sprint plan (2026-11-18).

## Decisions

Status in brackets: Decided, Proposed, Decided-pending-implementation, or Implemented, not yet validated.

### Data

- [Factor data source: the Ken French Data Library](decision-factor-data-source-french-library.md) [Decided]: one public library is the single source of truth for factors.
- [Prices from Yahoo, with adjusted-close care](decision-prices-from-yahoo-with-adjusted-close-care.md) [Decided]: raw bars, total return from adjusted close, independent recomputation, same-day cache.
- [Parallel, throttled price downloads](decision-parallel-throttled-price-downloads.md) [Decided-pending-implementation]: a few tickers at a time, spaced requests, slow retries and a stop switch, because Yahoo publishes no rate limit.
- [European mode, regional factors and currency](decision-european-mode-and-currency.md) [Proposed]: regional factor files, US dollar conversion and an optional currency regressor.
- [USD or EUR reference currency](decision-reference-currency.md) [Decided-pending-implementation]: every report in USD or EUR; each asset converted daily at ECB rates; USD-only bond lines hedged in the euro view (2026-11-20).
- [A Europe factor set next to the US one](decision-europe-factor-set.md) [Decided; built on branches, not on dev as of 2026-11-20]: Ken French Developed Europe factors chosen by the user, default US; macro, energy and world beta keep the US factors; validation on real data (2026-11-20).

### Statistics

- [Daily returns with robust errors](decision-daily-returns-and-robust-errors.md) [Decided]: daily data and Newey-West errors instead of monthly data and plain errors.
- [Which betas count as reliable](decision-which-betas-count-as-reliable.md) [Decided]: Benjamini-Hochberg across five betas instead of a simple |t| over 2.
- [No look-ahead rule](decision-no-look-ahead-rule.md) [Decided]: every dated result uses only data up to that date.
- [Return and risk attribution](decision-return-and-risk-attribution.md) [Decided]: pieces that add up exactly to the total and to 100%.
- [SPY timing noise and the quality gate](decision-spy-timing-noise-and-the-quality-gate.md) [Decided-pending-implementation]: why SPY's R-squared was 0.967 and the pre-set gate that flags it.
- [Residual alpha analysis](decision-residual-alpha-analysis.md) [Built and validated on 2026-11-18]: an in-sample and a point-in-time line, with the owner's four choices.
- [Historical performance block](decision-performance-metrics.md) [Built, not yet validated]: the stock's own yearly growth, volatility, Sharpe ratio and worst fall over the analysed window, next to the factor numbers.
- [Cointegration design](decision-cointegration-design.md) [Decided-pending-implementation]: an exploratory long-run link test that must hold on unseen data.
- [Drift alerts and regime betas](decision-drift-alerts-and-regime-betas.md) [Decided-pending-implementation]: alerts when two of three conditions agree, and betas by market regime.
- [Shrunk betas](decision-shrunk-betas.md) [Decided-pending-implementation]: a second beta pulled toward a typical stock by how noisy it is, plus power statements; the ordinary betas stay primary.
- [Kalman-filter betas](decision-kalman-betas.md) [Decided-pending-implementation]: an extra time-varying beta line with a band, from a filter that learns its own drift rate; the rolling betas stay.
- [World beta](decision-world-beta.md) [Decided-pending-implementation]: a quick beta against the iShares MSCI ACWI ETF as a stand-in for the MSCI ACWI index, next to the US market beta on the same days; ACWI is cached and refreshed incrementally.

### Product and design

- [Report design: colour is evidence](decision-report-design-colour-is-evidence.md) [Decided]: colour only encodes data, every chart is also a table, and the equation is the one bold element.
- [Report density, width cap and range controls](decision-report-density-and-range-controls.md) [Decided-pending-implementation]: a narrow, less dense report; range and ticker pickers belong to the dashboard.
- [Dashboard server and interface](decision-dashboard-server-and-interface.md) [Decided-pending-implementation]: FastAPI server plus one scrolling React page with ticker search and range chips; plain CSS tokens; static report stays as export.
- [Dashboard v2: outcome first with a sidebar](decision-dashboard-v2.md) [Decided-pending-implementation]: navy sidebar with controls and section links, a plain verdict sentence instead of the formula, a Show statistics switch, company name, performance and a quick world beta (specified 2026-11-18, not built).
- [Factor it shows real progress](decision-factor-it-progress.md) [Decided; built on branches, not on dev as of 2026-11-20]: real progress steps over server-sent events, a placeholder page that matches the report, and a failed re-run that keeps the old report under a banner.

### Engineering and process

- [Thin slice on SPY first](decision-thin-slice-on-spy-first.md) [Decided]: one end-to-end path, checked hard, before the dashboard.
- [Application stack and the offline report](decision-application-stack.md) [Decided-pending-implementation]: FastAPI, React and ECharts for the dashboard; a self-contained HTML report first.
- [Python and uv for every platform](decision-python-and-uv-for-every-platform.md) [Decided]: uv is the only prerequisite on Windows, macOS and Linux.
- [No data and no secrets in the repository](decision-no-data-and-no-secrets-in-the-repo.md) [Decided]: data downloaded at run time, keys only in `.env`.
- [Branches and pull requests](decision-branches-and-pull-requests.md) [Decided]: `prod`, `dev`, feature and fix branches, maintainer merges.
- [Independent validation and mutation testing](decision-independent-validation-and-mutation-testing.md) [Decided]: a second recomputation plus deliberately injected bugs.
- [No citation without verification](decision-citations-and-verification.md) [Decided]: every source is looked up and checked by a script, and what we cannot check is listed as unverified.
- [Precision of the fast rolling regression](decision-rolling-fast-path-precision.md) [Decided-pending-implementation]: the fast path is about 1e-12 from the exact one on real data; its safety check is tighter and costs no speed.
- [One contract for the five new report sections](decision-schema-v3-contract.md) [Decided-pending-implementation]: optional sections, one file per feature and layer, panel registries, report format version 4.
- [Nightly run of the slow and live tests](decision-nightly-slow-tests.md) [Decided-pending-implementation]: a daily workflow for the statistical tests CI skips; the live job may fail.

### Next stage: track records and portfolios (2026-11-19)

Spec: [next-stage spec](../docs/specs/next-stage-track-record-and-portfolio.md). Status for all eight: Decided, not yet built.

- [Factor models (FF5 and FF6) and a separate macro section](decision-factor-models-and-macro.md) [Decided]: a five/six-factor switch, alpha under four models side by side, and rates, credit and euro sensitivities in their own section.
- [Energy & carbon section](energy-and-carbon-factors.md) [Decided]: sensitivities to oil, gas and carbon prices after the market, with a short-sample carbon model and a gas result without the 5 largest moves.
- [Monthly track-record uploads](decision-monthly-track-records.md) [Decided]: uploaded fund records, daily or monthly, checked and analysed in memory; monthly needs 36 months. Amends the daily-returns decision.
- [Portfolio backtest rules](decision-portfolio-backtest-rules.md) [Decided]: month-end rebalancing with drift, a cost line, cash at the risk-free rate, common start and end dates, and contribution and risk per holding.
- [SAA tree and default proxies](decision-saa-tree-and-proxies.md) [Decided]: a three-level tree (asset class, sub-asset class, ETF) prefilled with US-listed proxy ETFs; alternatives later.
- [USD only in version 1](decision-usd-only-v1-portfolios.md) [Decided]: US dollars and US-listed proxies first; a euro base and UCITS funds wait for European mode.
- [VaR and CVaR](decision-var-and-cvar.md) [Decided]: historical, Gaussian and Cornish-Fisher side by side at 99% VaR / 97.5% CVaR (plus 95% for monthly), with bootstrap bands and per-holding CVaR for portfolios.
- [Joint tail behaviour of portfolios](decision-joint-tail.md) [Decided]: a 'crash together' heatmap against a normal baseline, a co-crash histogram and one t copula; no EVT in version 1; Labovitz's method parked for large stock universes.
- [Causal-discipline guardrails](decision-causal-discipline-guardrails.md) [Decided]: model-dependence wording and notes, a specification curve and Minimum Track Record Length, after López de Prado (2023).

### Open source

- [Open source under the MIT license](decision-open-source-mit-license.md) [Decided]: a short permissive license.
- [Project name: factordesk](decision-project-name-factordesk.md) [Decided]: the name, and the rule not to imply endorsement by data providers.

## Concepts (glossary)

- [Glossary](glossary.md): excess return, factor, beta, alpha, t-statistic and p-value, HAC errors, R-squared, Benjamini-Hochberg, in-sample versus out-of-sample, point-in-time, look-ahead bias, rolling window, Euler risk contribution, residual, cointegration, half-life, survivorship bias, total return and adjusted close, risk-free rate, the Ken French Data Library, and the five factors.

## Research notes

- [README research, 2026-11-18](readme-research-2026-11-18.md): a survey of how popular finance repositories write their READMEs, and the outline chosen for ours.
- [Prior art review, 2026-11-18](prior-art-review-2026-11-18.md): what we learned from other open-source factor and portfolio tools, and the bugs we avoid.
- [Independent validation of the SPY slice](../docs/validation/spy-slice-validation.md): the full review behind several decision pages.
- [Causal Factor Investing study guide](../docs/research/causal_factor_investing_agent_kb.md): the owner's summary of López de Prado (2023), with attribution.
- [Labovitz (2009) summary](../docs/research/labovitz-2009-summary.md): owner-supplied summary and critique of a GEV return-level alternative to copulas.
- [Next-stage research, 2026-11-19](../docs/research/next-stage-research.md): track-record statistics, backtest mechanics, momentum and macro factors, and prior art (Venn, Portfolio Visualizer, Morningstar), with citations.
- [Dataset cards](../docs/datasets.md): verified facts about each Ken French file.

## Change log

- [Change log](log.md): dated changes to this knowledge base, newest first.
- [Earlier decisions log, 2026-11-18](decisions-2026-11-18.md): the first flat list of decisions, kept for history.
