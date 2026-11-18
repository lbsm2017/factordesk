# Decision: build the dashboard server and interface now

Date: 2026-11-18
Status: Decided-pending-implementation

## In one sentence

factordesk gets a FastAPI server and a single scrolling web page with a ticker search bar, date range controls and the full report, built with plain CSS in the report's own design language, while the offline HTML report stays as the export.

## What we decided

- On 2026-11-18 the owner approved building the server and a dynamic page with a ticker search bar and the full interface. This replaces the earlier "design only" scope in [report density, width cap and range controls](decision-report-density-and-range-controls.md).
- Backend: FastAPI endpoints for health, factor-data status and refresh, ticker suggestions, and a report for a ticker and a date range. The spec is [docs/specs/dashboard.md](../docs/specs/dashboard.md).
- Frontend: Vite, React and TypeScript with the report's own CSS tokens. We dropped Tailwind and shadcn/ui from the earlier plan. ECharts is used only for the price and exposure-over-time charts; other panels are plain SVG tables as in the report.
- Range chips are 3Y, 5Y and Full history. The owner dropped YTD and 1Y because the pipeline needs at least 504 aligned trading days. The page opens on Full history.
- Ticker suggestions come from tickers already fetched and recent tickers. There is no online lookup.
- One scrolling page, no tabs.
- The static HTML report is unchanged as the export path, and a "Download report" button calls it.

## Why

A range picker and ticker selector must rerun the regression, which a static file cannot do. The owner chose the server over embedded presets or a local-only mode. The owner approved dropping Tailwind and shadcn/ui because the approved report design has its own look, with no card kit and no accent colour, and generic components would need heavy overriding. The owner dropped YTD and 1Y rather than lower the 504-day minimum, which would change the statistics rules (a methodology decision).

## How it works

- The server runs a regression in a worker thread, shares one in-flight run per request, and caches by ticker, dates and factor-data vintage.
- The URL holds the state (for example `/?t=SPY&range=3Y`), so a view can be shared.
- Work is split into tickets T1 to T11 in the spec. T1 (API skeleton) and the static-report port to design revision 2 were done on 2026-11-18 on branch `feat/report-ui-feedback`.

## What it costs us

- Two renderers to keep in line: the Python static report and the React page. The design document and shared tests are the guard.
- A server is a new thing to run. The offline report keeps working for people who do not want one.
- The earlier stack decision ([application stack](decision-application-stack.md)) named Tailwind and shadcn/ui; this decision supersedes that part.
- Not verified as of 2026-11-18: the page has not been built or tested yet.

## What would change our mind

If keeping two renderers in line proves costly, we would render the report from the server and make the page a thin shell around that HTML.

## Sources

- [docs/specs/dashboard.md](../docs/specs/dashboard.md), including the "Owner decisions" section.
- [docs/PLAN.md](../docs/PLAN.md), stack and API list.
- The owner's messages of 2026-11-18 and their answers to the three spec questions.

## Related decisions

- [Application stack and the offline report](decision-application-stack.md)
- [Report density, width cap and range controls](decision-report-density-and-range-controls.md)
- [Report design: colour is evidence](decision-report-design-colour-is-evidence.md)
