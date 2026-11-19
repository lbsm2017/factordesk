# factordesk frontend

Vite, React, TypeScript (strict), TanStack Query, ECharts (price and exposure over time only) and downshift. Plain CSS tokens; no CSS framework. Spec: `docs/specs/dashboard.md`. Design: `docs/design/report-design.md`.

```text
npm ci
npm run dev        # API on 8000 (uvicorn reload) and Vite on 5173; open http://localhost:5173
npm run typecheck && npm run lint && npm test && npm run build
npm run size       # after build: fails if the initial JS is over budget (scripts/size.mjs)
npm run gen:types  # after: uv run python -m factordesk.api.openapi_dump frontend/src/api/openapi.json (repo root)
```

In development, `/?demo=1` renders the mock report so panels can be seen without the API. The demo is not in the production build.

ECharts loads in its own lazy chunk (`echarts`), so it is not in the initial JS; React and TanStack Query have their own vendor chunks. `npm run size` counts the entry script plus preloaded chunks against a budget of 405 kB raw and 125 kB gzip (measured: 401 and 123.5). Raise the budget in `scripts/size.mjs` only on purpose.

## Component map

- `src/App.tsx`: query client, URL state (`src/state/`), data flow (`src/api/queries.ts`), page composition.
- `src/components/controls/`: the controls strip (ticker search, range chips, custom dates, analysed range, factor data line).
- `src/components/report/`: one file per panel. `ReportView.tsx` draws them in the order of `panelRegistry.ts` (name and position per panel, schema v3 contract `docs/specs/schema-v3-contract.md` SC4): Header, Notice, Equation, KpiStrip, PricePanel, ExposuresPanel, then the optional LeadLagPanel, ShrunkBetasPanel and FragilityPanel, ReturnPanel, RiskPanel, the optional ResidualAlphaPanel, RollingPanel, the optional KalmanPanel, DataAuditPanel, RegressionDetail, Colophon. The optional panels live in `sections/` and render nothing while their report field is null. `Panel.tsx` is the shared frame (title, question, reading, body, footnote, "How this is computed"); pass `empty={{ reason, action }}` when a statistic's `status` is not `ok`.
- `src/components/charts/`: `BarCell`, `Hatch`, `useEChart` (lazy ECharts, SVG renderer), `chartTokens` (colours from CSS variables).
- `src/report/derive.ts`: values the renderer derives (rolling statistics for the non-primary window).
- `src/format/` and `src/text/plain.ts`: number and date rules, plain-language text.
- `src/styles/`: `tokens.css` (the only place for colour literals; a test enforces it), `report.css` (ported from the report stylesheet), `controls.css`.
- `src/test/`: `fixture.ts` (`mockReport`, `cloneReport()`) and `mockApi.ts` (msw server for tests that use `fetch`).

`src/api/openapi.json` and `types.gen.ts` are generated; rerun both commands above after any backend model change.
