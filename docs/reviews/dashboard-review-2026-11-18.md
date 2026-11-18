# Dashboard design and accessibility review (T11)

Date: 2026-11-18
Branch: `feat/report-ui-feedback` at `afefd9a`
Scope: the React page in `frontend/`, checked against `docs/specs/dashboard.md` (DB4 to DB7, Owner decisions), `docs/design/report-design.md` rev 2 (A to F, I), the prototype (`report.html`, `report-controls.html`, `shot_*.png`) and the wiki pages `decision-report-density-and-range-controls.md` and `decision-report-design-colour-is-evidence.md`.
Result in one line: the page is close to the approved design and every owner-feedback item holds except custom dates; five major findings, no blockers.

## How this was checked

- **Server.** Vite dev server for `frontend/` with an in-process mock API (no network). Data: `backend/factordesk/tests/fixtures/mock_report.json`, with the ranges and status of `frontend/src/test/mockApi.ts`. Test tickers: `SPY` (full report), `EMPTY` (every statistic `insufficient_data`, as `build_prototype.py --empty`), `XYZ` (404 `unknown_ticker`), `SHORT` (422 `insufficient_history`), `SLOW` (never answers). The harness lived outside the repository. The page ran in development mode (React StrictMode), not from `factordesk serve`.
- **Screenshots.** Headless Chrome driven over the DevTools protocol. Width came from device-metrics emulation, so 390 px needed no iframe. Dark mode came from emulated `prefers-color-scheme`; `html[data-theme]` was checked separately. Files are in `frontend/shots/t11/` (gitignored).
- **Keyboard.** Real key events (Tab, `/`, arrows, Enter, Space, Escape) with focus emulation on, plus reading the code.
- **axe-core 4.14.1.** The copy already in `frontend/node_modules` (a dependency of `eslint-plugin-jsx-a11y`), injected into the page; nothing was added to the repository. Tags: wcag2a, wcag2aa, wcag21a, wcag21aa, wcag22aa, best-practice.
- **Measurements.** Layout boxes, mark geometry and panel offsets read from the DOM. WCAG contrast computed from the hex values in `tokens.css`.
- **Bundle.** Production build into a temporary folder (`vite build --outDir`).
- **Gates.** `tsc --noEmit` passed. ESLint passed. Vitest passed (314 tests, 18 files) when run from PowerShell; see C5.

**Screenshots** (all under `frontend/shots/t11/`):

- Full report: `report_1440_light.png`, `report_1440_dark.png`, `report_1920_light.png`, `report_390_light.png`, `report_390_dark.png`.
- States: `state_landing_1440.png`, `state_combobox_landing_1440_top.png`, `state_loading_1440.png`, `state_busy_1440_top.png` (new request, with the notice open), `state_notice_open_1440_top.png`, `state_error_1440.png`, `state_error_insufficient_1440.png`, `state_empty_1440.png`, `state_empty_390_dark.png`.
- Crops: `crop_1440_controls.png` (shows the disabled 5Y chip), `state_390_controls_top.png`, `crop_1440_price.png`, `crop_1440_exposures_table.png`, `crop_1440_rolling.png`, `crop_390_exposures.png`, `crop_390_price.png`, `crop_390_rolling.png`, `crop_390_equation.png`.

## Owner-feedback checks

| Item | Result | Evidence |
|---|---|---|
| Not too wide: 1216 px column | **Pass** | `.report` is 1216 px wide and centred at 1440 (x 112) and at 1920 (x 352); the content is 1152 px. At 390 px, `scrollWidth` is 390. |
| Less dense header | **Pass** | The header is one line: ticker, subtitle, two chips and Download report (`crop_1440_controls.png`, `report_1440_light.png`). The range line moved into the strip, as design I says. See DF1 for the extra callout below the header. |
| Less dense KPI strip | **Pass** | Five cells. Each has a label, a value and one 12.5 px line. Two columns at 390, and the last cell spans both. |
| Price label "Not analysed: factor data ends ..." | **Pass** | The label reads exactly "Not analysed: factor data ends 30 Sep 2026", with a dashed cut and a `--grid` band of true width (`crop_1440_price.png`). The left-hand label ("before ...") is not drawn: the fixture has no unanalysed days before the start, because the first price day is the base price. It is checked by unit tests only. |
| Smaller beta markers | **Pass** | Measured at 1440: caps are 3.08 px tall at a 44 px row. Caps are dropped on Mkt-RF, whose interval is under 1.2% of the plot. The diamond is 7.2 × 7.2 px, and its centre equals the bar's centre line (for example 1551.09 and 1551.09). |
| Five-row rolling panel with three number columns | **Pass** | Five rows, each 56 px. Columns: Latest, Average, Middle 80%. The 126/252 radios write `win` to the URL. |
| Ticker search | **Pass**, one minor gap | It is a downshift combobox (`role=combobox`, `aria-activedescendant`). An empty field lists recent tickers; typed text lists suggestions. Arrows move, Escape closes and keeps the text, and Enter submits. `/` focuses and selects the field from the page body. See A5. |
| Range controls: 3Y, 5Y, Full history | **Pass** | Native radios in a fieldset. Arrow keys skip the disabled 5Y and commit `range=` to the URL. |
| Range controls: custom dates | **Fail** | Typing a year commits partial years as real requests (S1). |
| Range controls: visible reasons | **Pass** | "5Y has 400 trading days; a regression needs at least 504." is visible under the strip and linked with `aria-describedby` (`crop_1440_controls.png`). |

## Design fidelity

| Id | Severity | Where | What I saw | Why it matters | Suggested fix |
|---|---|---|---|---|---|
| DF1 | major | `GateCallout.tsx`, between the KPI strip and Price | A framed "Residual quality gate" block sits above the first chart (`report_1440_light.png`). The design, the prototype and `render_html.py` have no such block, and its sentence repeats the notice ("R² and residual volatility are probably understated"). The Price panel starts at y 859 at 1440 and is below the fold of a 900 px window. In the prototype controls mock it starts at about 750. | The owner asked for less above the first chart. This adds a second warning box for one finding. | Move the measured numbers into the notice's Details (which already holds the 5-day line) and drop the callout. |
| DF2 | minor | Price chart (`priceModel.ts`) | Six y ticks, 450 to 700 (`crop_1440_price.png`). | Design D4 says 3 to 4 y ticks. | Set `splitNumber: 3` or a min interval on the y axis. |
| DF3 | minor | `RegressionDetail.tsx`, `.reg` | The regression, 5-day and diagnostics tables each stretch to 1104 px, with wide gaps between columns (`report_1440_light.png`, bottom). There are three sideways-scroll regions. | Design C Rev 2 says no stretched columns. DB5 says only the regression table scrolls. The prototype also stretches the first table, so part of this is inherited. | Size `.reg` to its content (`width: auto`) and keep one scroll region. |
| DF4 | minor | Data and audit; the From and To fields | "Factor file downloaded" shows `2026-11-01 00:00 UTC`, ported from `render_html.py`. The date fields show the browser locale (`08.08.2024`). | Design B says dates in prose read like "8 Aug 2024". The field format belongs to the browser and is acceptable. | Format the download time with `dateLong` plus the time. |
| DF5 | minor | `ExposuresPanel.tsx` (How this is computed); `Notice.tsx` (5-day line) | The text says "Reliable means ...; noise means it is not". The 5-day line prints the raw tag: "..., noise; R² 0.9991" (`state_busy_1440_top.png`). Both are inherited from `render_html.py`. | Design G keeps "reliable" and "noise" out of the reader's text. | Map the tags to "significant" and "not significant". |
| DF6 | minor | `KpiStrip.tsx` empty state | "Widen the date range to at least 60 trading days" (`state_empty_1440.png`). The API refuses fewer than 504 days. Inherited from the static renderer. | The action names a threshold the server does not use. | Use `ranges.min_obs` or drop the number. |
| DF7 | minor | KPI empty state after the notice | When the equation is omitted, the KPI empty box touches the notice: notice bottom 397.75 px, KPI top 397.75 px (`state_empty_1440.png`). | It reads as one box. | Add a top margin to `.kpis` when it follows `.notice`. |
| DF8 | minor | Rolling panel at 390 | Only one x label ("Jan 2026") stays, because minor ticks are hidden (`crop_390_rolling.png`). | The time span cannot be read on a phone. | Always keep the first and last labels. |

## Accessibility

**axe results.** No violations on the report at 1440 in light or dark, on the landing page, or in the empty state. There are 2 violations at 390 (light and dark). There is 1 violation each in the error and loading states. The incomplete results (color-contrast on layered backgrounds, `aria-required-children`, `aria-valid-attr-value` on the combobox) were reviewed by hand; the `aria-controls` target exists.

**Keyboard.** Tab order follows the reading order: search, Factor it, the range radio, From, To, Check for newer factor data, the warnings chip, Download report, Details, the seven equation terms, Regression detail link, the panel disclosures, the window radio, the three scroll regions. Every stop showed a 2 px Graphite ring, except the calendar button inside each date field, whose shadow-DOM focus my probe could not read (not verified). Enter and Space toggle Details. Enter on an equation term focuses `#beta-SMB` with the `--sunk` wash and the 2 px ink rule. The window radios move with the arrow keys and write `win=126`.

**Contrast** of the token pairs the controls add, computed (WCAG, light / dark):

| Pair | Light | Dark |
|---|---|---|
| Disabled chip text, ink-3 on sunk | 5.06 | 5.61 |
| Selected chip and Factor it, surface on ink | 16.46 | 14.71 |
| Reason line and suggestion note, ink-3 on surface | 5.44 | 6.12 |
| Highlighted suggestion note, ink-3 on sunk | 5.06 | 5.61 |
| Landing text, ink-2 on page | 6.88 | 9.57 |
| Focus ring against page / surface | 14.39 / 16.46 | 15.85 / 14.71 |
| Input and chip border against surface (non-text) | **1.42** | **1.43** |
| Busy ticker placeholder, grid on page (non-text) | 1.07 | 1.28 |

| Id | Severity | Where | What I saw | Why it matters | Suggested fix |
|---|---|---|---|---|---|
| A1 | major | `RollingPanel.tsx` tfoot | axe `aria-required-children` (critical) at 390 px: `.cols-3 > tfoot > .axis-row[role=row]`. Only its `aria-hidden` axis cell remains, because the other cells are `display: none` under 720 px. | The T11 acceptance in DB9 is "an axe scan with no violations". | Put `aria-hidden="true"` on the `tr`, as `ExposuresPanel` does. |
| A2 | minor | Exposures and Return headers at 390 | axe `empty-table-header`: "Significant" is hidden by CSS (`.long`), and "Sig." is `aria-hidden` (`.short`). | Screen-reader users on a phone lose the column name. | Drop `aria-hidden` from `.short`, or keep the long text visually hidden. |
| A3 | major | `report.css` `.controls input`, `.chip-opt span` | Text-field, date-field and chip boundaries are `--border`: 1.42:1 (light) and 1.43:1 (dark) against the surface. | WCAG 1.4.11 needs 3:1 for the boundary that identifies an input. The search field is the page's main control. | Use `--axis` (3.04 / 3.53) for control borders. |
| A4 | minor | `ReportStates.tsx` (error, loading) | axe `page-has-heading-one`: the error state has no h1, and the loading h1 is inside `aria-hidden`. | Heading navigation finds nothing on these states. | Render the ticker h1 above the error notice, and keep the loading h1 outside `aria-hidden`. |
| A5 | minor | `TickerSearch.tsx` `isTextTarget` | With focus on a range or window radio, `/` does nothing, because every `INPUT` counts as a text field. | DB7 says `/` works "unless focus is already in a text field". | Treat only text-like input types (and textarea, select, contenteditable) as text targets. |
| A6 | minor | Rolling "Middle 80%" cell | Spread, lowest, highest and the share of windows above zero are only in a `title`. | `title` is not reachable by keyboard or touch, and screen readers often skip it. Design D8 asks for the `title`, so this is a design gap. | Repeat the sentence in the panel's "How this is computed", or as hidden row text. |

## States

| Id | Severity | Where | What I saw | Why it matters | Suggested fix |
|---|---|---|---|---|---|
| S1 | major | `CustomRange.tsx` (commits on change) | In From, I moved to the year and typed 2, 0, 2, 3. Chrome emitted `0002-08-08`, `0020-08-08`, `0202-08-08` and `2023-08-08`. `parseIsoDate` accepts year 202, so the page pushed `?start=0202-08-08&end=2026-09-30` and requested `GET /api/report/SPY?start=0202-08-08&end=2026-09-30`, then the 2023 request. There are two history entries. | Every keyboard user who types a date sends wrong requests, and Back walks through bogus states. Each request can start a multi-second regression on the server. | Commit on blur or Enter, and reject years before the first return date (or before 1900). |
| S2 | major | `LoadingFrame` in `ReportStates.tsx` | The frame is not at final heights. Panel tops while loading compared with loaded, at 1440: Price 519 → 859, Factor exposures 974 → 1286, Exposure over time 2160 → 3257, Regression detail 2951 → 4438. There is no chips row, notice or real-height equation (`state_loading_1440.png` against `report_1440_light.png`). | DB6.4 says "no layout shift". Shifts of up to 1487 px move anything the reader has scrolled to. | Size the skeletons from the real panel heights. Reserve the header row, the notice and the equation (about 130 px). |
| S3 | minor | Busy state (`report.css`) | During a new request, the ticker and the KPI values become placeholders. The equation, the KPI notes, the notice and the analysed-range label still show the old report (`state_busy_1440_top.png`). | DB6.4 lists the equation among the placeholders. Old numbers next to new placeholders can be misread. | Add `.model .m` and `.kpi .n` to the `[aria-busy="true"]` placeholder rule. |
| S4 | minor | Busy ticker placeholder | `--grid` on `--page` is 1.07:1 in light, so the placeholder is nearly invisible (`state_busy_1440_top.png`). | The busy cue is weak. | Use `--border` for placeholders that sit on the page background. |
| S5 | minor | Landing (`ControlsStrip`) | With no ticker, the chips show Full history as selected and the date fields are enabled. Clicking 3Y writes `?range=3Y` and the page stays on landing (`state_landing_1440.png`). | The controls have no effect and look active. | Disable the range and date controls until a ticker is chosen. |
| S6 | pass | Error and empty states | `XYZ` and `SHORT` show the square glyph, `message`, then `action`, and no stale report. `EMPTY` shows every panel's empty state; the other panels render. | – | – |

## Performance

| Id | Severity | Where | What I saw | Why it matters | Suggested fix |
|---|---|---|---|---|---|
| P1 | minor | Build output | The ECharts lazy chunk is 545 KB raw (182 KB gzip). The main chunk is 372 KB raw (113 KB gzip) and the CSS 26 KB. Total JS is about 917 KB raw, 295 KB gzip, against 233 KB for the whole static report. Vite warns about a chunk over 500 KB. ECharts is not in `index.html`, so the lazy load works, and the demo fixture is not in the bundle. | The page is local, so transfer cost is small. Parse time on slow machines was not measured. Five rolling instances add runtime work, also not measured. | Record a size budget and set `chunkSizeWarningLimit`. Consider SVG for the five rolling rows, as the prototype does. |

## Code smells

| Id | Severity | Where | What I saw | Suggested fix |
|---|---|---|---|---|
| C1 | minor | `RollingPanel.tsx`, `priceModel.ts`, `AnalysedRange.tsx`, `DataAuditPanel.tsx`, `leadHelpers.ts` | `escapeHtml` and `isoOf` exist in two files, and `plural` in three. | Move them into `src/format/`. |
| C2 | minor | `chartTokens.ts` | Tokens are read again only when `prefers-color-scheme` changes. With a dark OS, setting `data-theme="light"` after mount left the price chart strokes at `#212a34`, the dark grid colour, on a light page. | Also observe the `data-theme` attribute (MutationObserver). It matters only once a theme switch exists. |
| C3 | minor | `report.css` print block | `#rolling .win { display: block }` is meant to print both windows, but React renders only the selected window. | Remove the rule, or render both windows for print. The supported print path is Download report (DB7). |
| C4 | minor | T10 deliverables | There is no `frontend/e2e/`, no `playwright.config.ts`, and no e2e job in `.github/workflows/ci.yml`; `fake_app.py` exists. DB9 makes T11 depend on T10. | Finish T10 so this review's checks (390 `scrollWidth`, axe) run in CI. |
| C5 | minor | Developer setup | `npm test` from Git Bash (`/c/...` working directory) fails all 18 files with "Vitest failed to find the current suite" in `src/test/setup.ts`. The same command from PowerShell passes 314 tests. The cause is not confirmed; I suspect drive-letter casing loads two copies of Vitest. | Note the PowerShell requirement in `CONTRIBUTING.md`, or normalise the root in `vitest.config.ts`. |
| C6 | minor | `ReportStates.tsx` | The loading frame's label "Alpha a year" differs from the report's "Alpha, a year". | Share the labels with `KpiStrip`. |

## Not checked

- Screen readers, Firefox, Safari, forced-colours mode and real long-history data.
- The built page served by `factordesk serve`, including the CSP headers. I ran the Vite dev server.
- The price "Show full history" toggle. The fixture has no history before the analysed range, so the button is not rendered.
- Rolling zoom with Ctrl and the wheel, the "Show full range" reset, and the drag-to-pan behaviour.
- The refresh button's announcement, the Back and Forward buttons, and print.
- Runtime cost of ECharts: parse time and the five connected instances.
- The focus ring on the calendar button inside each date field.

## Tickets, ordered by severity

1. **S1 (major).** Custom dates commit partial years: commit on blur or Enter, and validate the year range.
2. **S2 (major).** Loading frame at final heights: reserve the header, notice and equation, and match the panel heights.
3. **A1 (major).** `aria-hidden` on the rolling tfoot row, so axe has zero violations at 390.
4. **A3 (major).** Control borders at 3:1: use `--axis` for inputs and chips.
5. **DF1 (major).** Fold the gate callout into the notice Details, so nothing extra sits above the first chart.
6. **S3 (minor).** Busy placeholders for the equation and the KPI notes.
7. **A4 (minor).** An h1 in the error and loading states.
8. **A2 (minor).** Accessible "Significant" headers at 390.
9. **A5 (minor).** `/` works when a radio has focus.
10. **DF3 (minor).** Regression-detail tables sized to their content; one scroll region.
11. **DF7 (minor).** Gap between the notice and the KPI empty state.
12. **S5 (minor).** Disable the range controls on the landing page.
13. **DF5 and DF6 (minor).** Wording: no "reliable" or "noise", no "60 trading days". These also touch `render_html.py`, which DB0 keeps out of scope.
14. **DF2, DF4, DF8 (minor).** Price y ticks, date format in Data and audit, rolling x labels at 390.
15. **S4 and A6 (minor).** Stronger busy placeholder on the page background; Middle 80% detail as text.
16. **P1 (minor).** Bundle budget and the ECharts weight decision.
17. **C4 (minor).** Finish T10: e2e smoke test and CI job.
18. **C1, C2, C3, C5, C6 (minor).** Shared helpers, data-theme observer, dead print rule, test-shell note, label consistency.

Counts: 0 blockers, 5 major, 21 minor.

### Fixed 2026-11-18 (branch fix/dashboard-controls-input)

- **S1:** custom dates commit only on blur or Enter; a year before 1970, a date after the last factor date, From after To and an incomplete date show a sentence and send nothing; unchanged values do nothing. The smoke test types a year and checks no request or history entry until Enter.
- **A3:** control borders use `--axis` (at least 3:1 in light and dark); a style test checks the ratio and the rules.
- **A5:** `/` focuses the search from a radio; text-like inputs, textareas and selects still keep it.
- **S5:** on the landing page the chips and date fields are disabled, none is selected, and a visible sentence says to choose a ticker first.
## Fixes

Fixed 2026-11-18 on `fix/dashboard-panels-a11y`:

- **A1.** The rolling tfoot row carries `aria-hidden`; axe reports no violations at 390 px (light and dark) and at 1440 px.
- **A2.** The "Significant" header keeps its full word in the accessibility tree under 720 px; "Sig." stays the visible text.
- **A6.** The Middle 80% detail is repeated as screen-reader text in the cell, beside the `title`.
- **DF1.** The gate callout is gone; its numbers are a paragraph under the notice Details, before the 5-day line.
- **DF2.** The price y axis asks for two intervals (three or four labels).
- **DF3.** The regression tables are sized to their content. Only the main table keeps the scroll region; the 5-day and diagnostics tables become one block per row on a phone.
- **DF4.** "Factor file downloaded" reads like "1 Nov 2026, 00:00 UTC".
- **DF5 (React page only).** The 5-day line says "significant" or "not significant"; the exposures method note no longer says "reliable" or "noise". `render_html.py` still does (lines 593 and 843).
- **DF8.** The first and last x labels stay on the rolling charts under 720 px, plus the major ones that fit.
- **DF6** is in `KpiStrip.tsx` and was not touched here.
