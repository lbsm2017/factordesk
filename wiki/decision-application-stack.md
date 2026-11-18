# Decision: the application stack, and an offline HTML report first

Date: 2026-11-18
Status: Decided-pending-implementation

## In one sentence

The analysis runs on a Python backend (FastAPI) with a React dashboard on top and Apache ECharts for charts, but the first deliverable is a self-contained offline HTML report that needs no server.

## What we decided

- Backend: FastAPI in Python. Python is required because the statsmodels library provides Newey-West errors, Engle-Granger and Johansen tests.
- Dashboard: Vite, React and TypeScript, with Tailwind and shadcn/ui, and Apache ECharts for every chart.
- First slice: a single HTML file with inline SVG charts, written by a command-line tool.
- Status: the report is Decided and built. The dashboard is pending implementation as of 2026-11-18; the API folder is empty.

## Why

The statistics are the product, and the best tested implementations of the tests we need are in Python, so the backend stays in Python. We rejected a JavaScript-only stack because it would mean re-implementing those tests. ECharts was chosen because one library covers shaded regions and zoom, which the price chart with factor shading needs, so every chart looks and behaves the same. We rejected a server-based first deliverable because a static HTML file opens by double-click, prints cleanly and needs no server or content delivery network.

## How it works

- The backend exposes typed models only; the frontend sees nothing else, so a numbers change cannot silently break a chart.
- The report embeds its fonts and draws charts as inline SVG tables, so it works offline. See the report design page.
- Example: running the command-line tool for SPY writes a `.html` and a `.json` file; opening the HTML needs no network.
- The plan has the dashboard consume the same typed report, so the first slice should not need redoing (not yet tested, as the dashboard is unbuilt).

## What it costs us

- Two languages (Python and TypeScript) mean two toolchains; the dashboard needs Node for development.
- Inline SVG is less interactive than ECharts: no zoom or hover charts in the report.
- A frontend not yet built carries risk: choices such as Tailwind and shadcn/ui are not tested against our design yet.
- The report and the dashboard may drift visually if they do not share design rules.

## What would change our mind

Finding that ECharts cannot draw the shaded-region price chart cleanly, a decision to ship only the report, or a hosted version that needs a different front-end approach.

## Sources

- [docs/PLAN.md](../docs/PLAN.md), "Context" and "Architecture".
- [Earlier decisions log](decisions-2026-11-18.md).
- [docs/design/report-design.md](../docs/design/report-design.md).
- [SECURITY.md](../SECURITY.md): the report loads no external scripts, styles or fonts.
- [pyproject.toml](../pyproject.toml): backend dependencies.

## Related decisions

- [Report design: colour is evidence](decision-report-design-colour-is-evidence.md)
- [Thin slice on SPY first](decision-thin-slice-on-spy-first.md)
- [Python and uv for every platform](decision-python-and-uv-for-every-platform.md)
