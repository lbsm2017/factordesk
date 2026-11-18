# factordesk wiki

Last updated 2026-11-18. This is the project's knowledge base. Its main purpose is to record each decision in plain English: what we decided, why, how it works, and what we gave up. Pages date their claims, and facts that depend on `docs/` link to the source document instead of copying it.

## Start here

- [Glossary](glossary.md): plain-English definitions of every term used in the wiki, from alpha to the five factors.
- [README](../README.md): what factordesk is and how to run it.
- [Methodology specification](../docs/methodology.md): the exact statistical rules the decisions below summarise.
- [Plan](../docs/PLAN.md): the approved architecture and sprint plan (2026-11-18).

## Decisions

Status in brackets: Decided, Proposed, or Decided-pending-implementation.

### Data

- [Factor data source: the Ken French Data Library](decision-factor-data-source-french-library.md) [Decided]: one public library is the single source of truth for factors.
- [Prices from Yahoo, with adjusted-close care](decision-prices-from-yahoo-with-adjusted-close-care.md) [Decided]: raw bars, total return from adjusted close, independent recomputation, same-day cache.
- [European mode, regional factors and currency](decision-european-mode-and-currency.md) [Proposed]: regional factor files, US dollar conversion and an optional currency regressor.

### Statistics

- [Daily returns with robust errors](decision-daily-returns-and-robust-errors.md) [Decided]: daily data and Newey-West errors instead of monthly data and plain errors.
- [Which betas count as reliable](decision-which-betas-count-as-reliable.md) [Decided]: Benjamini-Hochberg across five betas instead of a simple |t| over 2.
- [No look-ahead rule](decision-no-look-ahead-rule.md) [Decided]: every dated result uses only data up to that date.
- [Return and risk attribution](decision-return-and-risk-attribution.md) [Decided]: pieces that add up exactly to the total and to 100%.
- [SPY timing noise and the quality gate](decision-spy-timing-noise-and-the-quality-gate.md) [Decided-pending-implementation]: why SPY's R-squared was 0.967 and the pre-set gate that flags it.
- [Residual alpha analysis](decision-residual-alpha-analysis.md) [Decided-pending-implementation]: an in-sample and a point-in-time line, with the owner's four choices.
- [Cointegration design](decision-cointegration-design.md) [Decided-pending-implementation]: an exploratory long-run link test that must hold on unseen data.
- [Drift alerts and regime betas](decision-drift-alerts-and-regime-betas.md) [Decided-pending-implementation]: alerts when two of three conditions agree, and betas by market regime.

### Product and design

- [Report design: colour is evidence](decision-report-design-colour-is-evidence.md) [Decided]: colour only encodes data, every chart is also a table, and the equation is the one bold element.
- [Report density, width cap and range controls](decision-report-density-and-range-controls.md) [Decided-pending-implementation]: a narrow, less dense report; range and ticker pickers belong to the dashboard.
- [Dashboard server and interface](decision-dashboard-server-and-interface.md) [Decided-pending-implementation]: FastAPI server plus one scrolling React page with ticker search and range chips; plain CSS tokens; static report stays as export.

### Engineering and process

- [Thin slice on SPY first](decision-thin-slice-on-spy-first.md) [Decided]: one end-to-end path, checked hard, before the dashboard.
- [Application stack and the offline report](decision-application-stack.md) [Decided-pending-implementation]: FastAPI, React and ECharts for the dashboard; a self-contained HTML report first.
- [Python and uv for every platform](decision-python-and-uv-for-every-platform.md) [Decided]: uv is the only prerequisite on Windows, macOS and Linux.
- [No data and no secrets in the repository](decision-no-data-and-no-secrets-in-the-repo.md) [Decided]: data downloaded at run time, keys only in `.env`.
- [Branches and pull requests](decision-branches-and-pull-requests.md) [Decided]: `prod`, `dev`, feature and fix branches, maintainer merges.
- [Independent validation and mutation testing](decision-independent-validation-and-mutation-testing.md) [Decided]: a second recomputation plus deliberately injected bugs.

### Open source

- [Open source under the MIT license](decision-open-source-mit-license.md) [Decided]: a short permissive license.
- [Project name: factordesk](decision-project-name-factordesk.md) [Decided]: the name, and the rule not to imply endorsement by data providers.

## Concepts (glossary)

- [Glossary](glossary.md): excess return, factor, beta, alpha, t-statistic and p-value, HAC errors, R-squared, Benjamini-Hochberg, in-sample versus out-of-sample, point-in-time, look-ahead bias, rolling window, Euler risk contribution, residual, cointegration, half-life, survivorship bias, total return and adjusted close, risk-free rate, the Ken French Data Library, and the five factors.

## Research notes

- [README research, 2026-11-18](readme-research-2026-11-18.md): a survey of how popular finance repositories write their READMEs, and the outline chosen for ours.
- [Prior art review, 2026-11-18](prior-art-review-2026-11-18.md): what we learned from other open-source factor and portfolio tools, and the bugs we avoid.
- [Independent validation of the SPY slice](../docs/validation/spy-slice-validation.md): the full review behind several decision pages.
- [Dataset cards](../docs/datasets.md): verified facts about each Ken French file.

## Change log

- [Change log](log.md): dated changes to this knowledge base, newest first.
- [Earlier decisions log, 2026-11-18](decisions-2026-11-18.md): the first flat list of decisions, kept for history.
