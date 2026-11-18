# factordesk frontend

Vite, React, TypeScript (strict), TanStack Query, ECharts (price and exposure over time only) and downshift. Plain CSS tokens; no CSS framework. Spec: `docs/specs/dashboard.md`. Design: `docs/design/report-design.md`.

```text
npm ci
npm run dev        # API on 8000 (uvicorn reload) and Vite on 5173; open http://localhost:5173
npm run typecheck && npm run lint && npm test && npm run build
npm run gen:types  # after: uv run python -m factordesk.api.openapi_dump frontend/src/api/openapi.json (repo root)
```

In development, `/?demo=1` renders the mock report so panels can be seen without the API. The demo is not in the production build.

## Contract for the panel and control tickets (T4 to T8)

Fill in your own files only. Do not change a stub's props or `ReportView.tsx` (it places the panels). Every stub renders a titled, empty `Panel` (`components/report/Panel.tsx`; props `id`, `title`, `question`, `legend`, `reading`, `footnote`, `how`, `empty`). Pass `empty={{ reason, action }}` when a statistic's `status` is not `ok`. Types come from `src/api/types.ts`; numbers and dates from `src/format`; plain text from `src/text/plain.ts`. No colour literal outside `src/styles/tokens.css` (a test enforces it).

All panels take `ReportPanelProps = { report: FactorReport }` (`components/report/types.ts`), except where noted.

| Ticket | File in `src/components/report/` | Props | Panel `id` |
|---|---|---|---|
| T5 | `Header.tsx` | `{ report, downloadHref: string }` | `header` |
| T5 | `Notice.tsx` | panel props | `notice` |
| T5 | `Equation.tsx` | panel props | `equation` |
| T5 | `KpiStrip.tsx` | panel props | `kpis` |
| T5 | `GateCallout.tsx` | panel props | `gate` |
| T5 | `Colophon.tsx` | panel props | `colophon` |
| T6 | `PricePanel.tsx` | panel props | `price` |
| T6 | `ExposuresPanel.tsx` | panel props | `exposures` |
| T7 | `ReturnPanel.tsx` | panel props | `returns` |
| T7 | `RiskPanel.tsx` | panel props | `risk` |
| T7 | `RollingPanel.tsx` | `{ report, win: 126 \| 252, onWinChange(win) }` | `rolling` |
| T8 | `DataAuditPanel.tsx` | panel props | `data` |
| T8 | `RegressionDetail.tsx` | panel props | `regression-detail` |

`ReportView.tsx` (`{ report, downloadHref, win: 126 | 252 | null, onWinChange, busy? }`) renders them in this order: Header, Notice, Equation, KpiStrip, GateCallout, PricePanel, ExposuresPanel, ReturnPanel, RiskPanel, RollingPanel, DataAuditPanel, RegressionDetail, Colophon. It passes `win ?? report.average_beta.window` to `RollingPanel`. Notice, GateCallout and others render nothing when they have nothing to say (T5 decides; update the order test in `stubs.test.tsx`).

T4 owns `src/state/url.ts` (types and the `UrlState` shape are fixed here; `parseUrl` and `toSearch` are stubs), `src/api/queries.ts`, `src/App.tsx` and these files in `src/components/controls/`:

| File | Props |
|---|---|
| `ControlsStrip.tsx` | `{ state: UrlState, recent: string[], suggestions: TickerSuggestion[], ranges: RangeOptions \| undefined, factorStatus: FactorDataStatus \| undefined, report: FactorReport \| undefined, busy, refreshing, refreshMessage: string \| null, onQueryChange(q), onCommit(patch: Partial<UrlState>), onRefreshFactors() }` |
| `TickerSearch.tsx` | `{ value, recent, suggestions, error: string \| null, onQueryChange(q), onSubmit(text) }` |
| `RangeChips.tsx` | `{ options: RangeOption[] \| undefined, selected: Preset \| null, onSelect(preset) }` |
| `CustomRange.tsx` | `{ start: string, end: string, max: string \| null, onCommit(start, end) }` |
| `AnalysedRange.tsx` | `{ report: FactorReport \| undefined }` |
| `FactorDataLine.tsx` | `{ status: FactorDataStatus \| undefined, refreshing, message: string \| null, onRefresh() }` |

Shared pieces (done in T3): `components/charts/BarCell.tsx` (bar-table plot cell), `Hatch.tsx` (the one `#hatch` pattern, rendered by `ReportView`), `useEChart.ts` (lazy ECharts, SVG renderer, `group` for `echarts.connect`), `chartTokens.ts` (colours from CSS variables), `src/api/client.ts` (`apiRequest`, `ApiRequestError`), `src/test/fixture.ts` (`mockReport`, `cloneReport()`).

`src/api/openapi.json` and `types.gen.ts` are generated; rerun both commands above after any backend model change.
