# factordesk specification: dashboard (local server and web page)

Status: implementation specification, written 2026-11-18. Not yet implemented. The owner approved building it on 2026-11-18 ("a server and a dynamic page with ticker searchbar and proper full interface").
Audience: engineers building `backend/factordesk/api/` and `frontend/`; reviewers checking the work against it.
Companions: `docs/PLAN.md` (stack, API list), `docs/design/report-design.md` rev 2 (tokens A, type B, layout C, panels D, accessibility F, gaps H, controls I), the prototype in `docs/design/prototype/` (`report.html`, `report-controls.html`, `report.css`, `build_prototype.py`, `shot_*.png`), `CODING_STANDARDS.md`, `SECURITY.md`, and the wiki pages `decision-application-stack.md`, `decision-report-density-and-range-controls.md` and `decision-report-design-colour-is-evidence.md`.
Section ids: DB0-DB10. Tickets: T1-T11 (DB9). Open questions: DB10.

---

## DB0. Scope

**In.** A local FastAPI server and a single-page React app. The user types a ticker, presses "Factor it", picks a range (YTD, 1Y, 3Y, 5Y, Full history or custom dates) and reads the full report: header, notice, equation, KPI strip, price, factor exposures, return, risk, exposure over time, data and audit, regression detail. A "Download report" button returns the existing offline HTML report for the same ticker and range.

**Out.** The Factors view, cointegration, dominance shading, drift alerts and regime betas (no schema fields yet); login; hosting; packaging the built page inside the Python wheel (belongs to the one-shot install item in `docs/ROADMAP.md`); any change to `backend/factordesk/report/render_html.py`.

**Deviations from `docs/PLAN.md`, stated plainly.**

| PLAN.md says | This spec does | Why |
|---|---|---|
| `POST /api/factor-it` with `{ticker, start?, beta_window, include_market_in_dominance, peers}` | `GET /api/report/{ticker}?range=` or `?start=&end=` | The request is a read. A GET maps one-to-one onto the page URL, can be replayed with curl and needs no body. Window, dominance and peer options have no backend yet. |
| Tailwind v4 + shadcn/ui | Plain CSS ported from `docs/design/prototype/report.css`, tokens from design section A | The approved design is already written as CSS with its own tokens, radius rule and "no card kit" rule (design G). Tailwind would duplicate the tokens, and shadcn's defaults (cards, shadows, accent) contradict the design. |
| Apache ECharts for every chart | ECharts for price and exposure over time only; every bar panel is React-rendered SVG inside a real `<table>` | "The chart is a table" (design principle 2). Zoom and hover only earn their weight on the two long time series. |
| Two top-level views and sub-tabs | One scrolling page in the report's order | The report layout is the approved design; tabs would hide panels. See DB10 question 5. |
| IBM Plex, red/green, an accent colour, a dark terminal look | Instrument Sans + STIX Two, blue/copper sign pair, no accent | Superseded by `wiki/decision-report-design-colour-is-evidence.md`. |

---

## DB1. Architecture

```text
browser (React, TanStack Query)                    uvicorn, 127.0.0.1:8000
  /?t=SPY&range=3Y ── GET /api/... (JSON) ───────►  backend/factordesk/api/main.py   create_app(deps)
                                                      api/routes_factors.py   health, factor status and refresh
                                                      api/routes_report.py    report, ranges, html, ticker suggest
                                                      api/service.py          memo, in-flight de-dup, worker threads
                                                      api/ranges.py           preset -> dates (pure)
                                                      api/errors.py           exception -> ApiError
                                                      api/static.py           serves frontend/dist (prod only)
                                                    pipeline.assemble_report -> FactorReport (report/schema.py)
                                                    data_dir/ (factor and price caches, shared with the CLI)
```

- **Contract.** The frontend sees only pydantic models in `backend/factordesk/report/schema.py` (CODING_STANDARDS section 6). `FactorReport` is unchanged and `SCHEMA_VERSION` stays `"3"`. The envelope models of DB2.2 go into the same file, in a new section "API envelope (not part of FactorReport)".
- **Range in the pipeline.** On 2026-11-18, `build_report` and `assemble_report` in `backend/factordesk/pipeline.py` take no dates, while `build_sample` in `backend/factordesk/analytics/sample.py` already accepts `requested_start` and `requested_end`. T2 adds keyword-only `start: date | None = None, end: date | None = None` to both pipeline functions and passes them through. The defaults keep today's behaviour, so CLI output does not change.
- **Injection.** `api/deps.py` defines a frozen dataclass `AppDeps`: `price_provider: PriceProvider`, `load_factors: Callable[[bool, datetime], pd.DataFrame]` (refresh flag, now), `factor_status: Callable[[datetime], FactorStatus | None]`, `now: Callable[[], datetime]`, `data_dir: Path`, `static_dir: Path | None`, `max_workers: int = 2`, `report_cache_size: int = 32`. `default_deps(static_dir)` wires `YFinanceProvider(now=...)`, `load_ff5_daily(data_dir=...)` and `factor_status(data_dir=...)` from `backend/factordesk/data/`, the UTC clock and `get_settings().data_dir` (made absolute and logged once at start). Tests pass fakes. Importing the module reads no disk and no network.
- **Fetching.** The API does not call `build_report`, because that function records no download time when factors are passed in. The service loads factors and prices through `AppDeps`, reads the vintage from `factor_status`, and calls the pure `assemble_report(symbol, history, frame, now=..., factors_downloaded_at=..., start=..., end=...)`.

---

## DB2. API

### DB2.1 Endpoints

All paths start with `/api`. All responses are JSON except the HTML download. Every error body is an `ApiError` (DB2.3).

| Method and path | Query | Response model | Notes |
|---|---|---|---|
| `GET /api/health` | – | `Health` | No disk or network access. |
| `GET /api/factors/status` | – | `FactorDataStatus` | 200 with `available: false` when nothing is cached. |
| `POST /api/factors/refresh` | – | `FactorDataStatus` | Forced download (`load_factors(True, now)`). One refresh at a time; a second call joins the running one. A failed download keeps the previous cache (existing behaviour of `load_ff5_daily`). |
| `GET /api/tickers` | `q` (0-12 chars), `limit` (1-20, default 8) | `TickerSuggestions` | Tickers with a price cache file in `data_dir/prices/` (name `{TICKER}_{YYYY-MM-DD}.parquet`, ticker part checked with `validate_ticker`), prefix match, most recently fetched first. No network. |
| `GET /api/report/{ticker}/ranges` | – | `RangeOptions` | Availability of each preset for this ticker (DB2.4). |
| `GET /api/report/{ticker}` | either `range`, or `start` and/or `end` (ISO dates) | `FactorReport` | `range` together with dates is a `bad_range` error. Neither means `FULL`. |
| `GET /api/report/{ticker}/html` | as above | `text/html` | `render_report_html(report)` from `report/render_html.py`, unchanged, with `Content-Disposition: attachment; filename="{TICKER}_report.html"` (the CLI's file name). Uses the same cached report. |

`ticker` is checked with `validate_ticker` (`backend/factordesk/data/prices.py`) before any provider, cache or file is touched. The upper-cased result is used everywhere after that.

### DB2.2 New models (in `report/schema.py`, all subclasses of `_Frozen`)

- `Health`: `status: Literal["ok"]`, `version: str` (from `importlib.metadata.version("factordesk")`), `schema_version: str`.
- `FactorDataStatus`: `available: bool`, `first_date: date | None`, `last_date: date | None`, `days_behind: int | None`, `last_download_at: datetime | None`, `stale: bool | None`, `source_url: str`. Built from the `FactorStatus` dataclass in `backend/factordesk/data/factors.py`.
- `TickerSuggestion`: `ticker: str`, `last_fetched: date`. `TickerSuggestions`: `items: list[TickerSuggestion]`.
- `RangePreset = Literal["YTD", "1Y", "3Y", "5Y", "FULL"]`. `RangeOption`: `preset`, `start: date | None`, `n_obs: int`, `available: bool`, `reason: str | None` (None exactly when available). `RangeOptions`: `ticker`, `first_return_date`, `last_price_date`, `factors_last_date`, `min_obs: int`, `options: list[RangeOption]` (always five, in preset order).
- `ErrorCode` (a `Literal` of the codes in DB2.3) and `ApiError`: `code: ErrorCode`, `message: str`, `action: str`.

### DB2.3 Error model

One rule: `message` says what went wrong and `action` says what to do. Both are plain sentences, with no stack trace and no exception class name. Wording follows the CLI's one-line errors in `backend/factordesk/cli.py`. FastAPI's default validation body is replaced by an `ApiError` handler.

| Cause | `code` | HTTP | Example `message` / `action` |
|---|---|---|---|
| `validate_ticker` fails | `invalid_ticker` | 422 | "BRK B is not a valid ticker." / "Use 1 to 12 letters, digits or . ^ = - (for example SPY or BRK-B)." |
| `PriceDataError` after validation | `unknown_ticker` | 404 | "No prices were returned for XYZ." / "Check the ticker symbol." |
| Start after end, bad date, `range` plus dates | `bad_range` | 400 | "The start date 1 May 2026 is after the end date 1 Jan 2026." / "Choose a start date before the end date." |
| `InsufficientHistoryError` (`n`, `required`) | `insufficient_history` | 422 | "SPY has 251 trading days in this range that line up with the factor data; at least 504 (about two years) are needed." / "Choose a longer range or Full history." |
| `DegenerateInputError` (`reason`) | `degenerate_input` | 422 | "Cannot analyse XYZ: {reason}." / "Choose another ticker or range." |
| `FactorDataError` | `factor_data_invalid` | 502 | "The downloaded factor file failed validation; the previous copy was kept." / "Try again later." |
| `FactorDownloadError`, `httpx.HTTPError`, `OSError` | `network` | 503 | "factordesk could not reach the data source." / "Check your network connection, then try again." |
| yfinance `YFException` | `upstream_refused` | 503 | "Yahoo Finance refused the request." / "Wait a minute, then try again." |
| Unknown `/api/...` path | `not_found` | 404 | "There is no API endpoint at /api/x." / "Check the address." |
| `ValueError` or `ArithmeticError` not caught above | `internal` | 500 | "The report for SPY could not be computed: {one line}." / "Try another range. If it happens again, report it with this page's address." The traceback goes to the log only. |

### DB2.4 Range rules (`api/ranges.py`, pure, unit-tested)

- `anchor = min(factors_last_date, last_price_date)`. YTD starts on 1 January of `anchor.year`. `NY` starts at `anchor` minus N calendar years plus one day (29 February maps to 28 February). FULL has no start.
- Every preset sends `end = None`, so the requested range runs to the last price date and the pipeline reports the days after the factor data as not analysed, exactly like the static report.
- Custom dates are passed as given. An end after the factor data is allowed; `SampleInfo` and `DataInfo` report requested and actual dates, so nothing is clipped silently.
- `n_obs` per preset comes from `build_sample(history, factors, start, None, min_obs=0)`. `available` means `n_obs >= MIN_OBS` (504 in `analytics/sample.py`). A `DegenerateInputError` makes the preset unavailable with its reason. Every reason names the minimum and what the range has: "1Y has 251 trading days; a regression needs at least 504."
- On 2026-11-18, with `MIN_OBS = 504`, YTD and 1Y are never available. See DB10 question 1.

---

## DB3. Caching, concurrency, data

- **Worker threads.** A regression takes seconds. Every provider call, factor load, `build_sample` and `assemble_report` runs through `anyio.to_thread.run_sync` with one shared `CapacityLimiter(max_workers)`. The event loop never blocks.
- **In-flight de-duplication.** `api/service.py` keeps, per layer, a dict from key to `asyncio.Task`. A request whose key is already running awaits the same task through `asyncio.shield`, so a closed browser tab does not cancel a build that others wait for. Failures are not cached; every waiter gets the same `ApiError`.
- **Layers and keys.**
  1. Factor frame: key = vintage `(last_date, last_download_at)`. A report request first loads factors (which may trigger the existing 40-day auto-refresh), then reads the vintage.
  2. Price history: key = `(ticker, now().date())`, matching the same-day cache of `YFinanceProvider`. LRU of 16.
  3. Report: key = `(ticker, start, end, vintage, now().date())` after preset resolution, so `range=3Y` and the same explicit dates share one entry. LRU of `report_cache_size`.
  4. Ranges: the report key without start and end.
- **Refresh.** `POST /api/factors/refresh` is single-flight. A new vintage changes every key, so stale entries are never served; the service then drops entries of the old vintage to free memory.
- **Shared state** (dicts and LRUs) is touched only on the event-loop thread. Worker functions take inputs and return values, so no locks are needed.
- **Data location.** The server uses the CLI's caches under `data_dir` (`data_dir/factors/`, `data_dir/prices/`) and writes nothing else there. Its only other file is its log, `logs/server.log` (gitignored by `/logs/`).
- **No network in tests.** API tests use `AppDeps` with `StaticProvider` and `dgp_a` from `backend/factordesk/tests/fixtures/dgp.py`, a fixed clock and `tmp_path` as `data_dir`. An autouse fixture in the API test files makes `socket.socket.connect` raise.

---

## DB4. Frontend stack and layout

- **Stack.** Vite, React, TypeScript (strict), TanStack Query, `echarts` (tree-shaken from `echarts/core` with the SVG renderer), and `downshift` (`useCombobox`, for an accessible ticker search). No router library, no CSS framework, no component kit. `frontend/package-lock.json` pins exact versions. Node 26 and npm 12 are installed locally on 2026-11-18.
- **Types.** `uv run python -m factordesk.api.openapi_dump frontend/src/api/openapi.json` writes the OpenAPI document; `npm run gen:types` runs `openapi-typescript` into `frontend/src/api/types.gen.ts`. Both files are committed and checked for staleness (DB8.3).
- **Styles.** `src/styles/tokens.css` holds the design section A tokens for light, dark (`prefers-color-scheme`) and `html[data-theme]` overrides. `src/styles/report.css` is ported from the prototype stylesheet with its class names kept, so the port is mechanical. No hex colour appears outside `tokens.css` (checked by a test). Fonts: the four WOFF2 files and two OFL licence texts are copied from `docs/design/prototype/fonts/` to `src/assets/fonts/` and loaded with `@font-face` and `font-display: swap`. No external font, script or style host.
- **Plain text.** `src/text/plain.ts` ports `PLAIN` (plain factor names), `WARN_PLAIN`, `TILT` and the reading template of `exposure_reading` from `docs/design/prototype/build_prototype.py` (design gaps H.2, H.3 and H.9). Unknown warning codes fall back to `message`.
- **Formatting.** `src/format/` ports the number rules: true minus U+2212, `+` on signed values, zero unsigned, tabular figures, percent from decimals, and dates as "8 Aug 2024" from a fixed month table (no locale variance).

```text
frontend/
  index.html  vite.config.ts  tsconfig.json  eslint.config.js  vitest.config.ts  playwright.config.ts
  src/main.tsx  src/App.tsx                 QueryClientProvider, URL state, page composition
  src/api/        client.ts  queries.ts  openapi.json  types.gen.ts
  src/state/      url.ts  recent.ts
  src/format/     numbers.ts  dates.ts
  src/text/       plain.ts
  src/styles/     tokens.css  report.css
  src/assets/fonts/
  src/components/controls/  ControlsStrip  TickerSearch  RangeChips  CustomRange  AnalysedRange  FactorDataLine
  src/components/report/    ReportView  Panel  EmptyState  HowComputed  Header  Notice  Equation  KpiStrip
                            PricePanel  ExposuresPanel  ReturnPanel  RiskPanel  RollingPanel  DataAuditPanel
                            RegressionDetail  GateCallout  Colophon
  src/components/charts/    BarCell  Hatch  useEChart  chartTokens
  src/report/derive.ts      renderer-derivable values (design H.13), 126-day averages
  e2e/  smoke.spec.ts  shots.spec.ts
```

---

## DB5. Panels: how each one renders

Every panel uses `Panel`: h2 title, question, optional legend or control, reading line, body, and one footnote with a `<details class="how">` "How this is computed". Any statistic with `status != "ok"` renders `EmptyState` (a `--sunk` box, `reason` in ink, one next step in `--ink-2`, no footnote), as design section D says. `dangerouslySetInnerHTML` is banned by a lint rule.

| Panel (design D) | Rendering | Data | Rules |
|---|---|---|---|
| 1 Header, notice | HTML | `ticker`, `data`, `warnings` | Ticker at 44.8/640; chips "Factor data ends 30 Sep 2026 (49 days ago)" and "N warnings" (links to the notice); a secondary "Download report" link (DB6.5). The range line moves into the controls strip (design I). Notice: 3 px ink rule, triangle glyph, hidden "Warning:", two-line plain summary, "Details" disclosure with the raw messages and the 5-day estimate line. |
| 2 Equation | HTML, STIX Two | `regression` | Port the `equation()` markup: terms link to `#beta-{name}` and `#ret-alpha`; faded terms say "not significant"; a full `aria-label`; wrapped lines hang under the first term. Omitted when empty. The one bold element. |
| 3 KPI strip | HTML | `regression`, `data` | Five cells: alpha a year, R², residual volatility, observations, analysed range. Two columns under 720 px; the last cell spans both. |
| 4 Price | ECharts | `price_series`, `data` | 1.5 px ink line. `--grid` bands before `actual_start` and after `factor_coverage_end`, with dashed `--ink-3` cut lines labelled "Not analysed: before 8 Aug 2024" and "Not analysed: factor data ends 30 Sep 2026". True time axis; a band is never widened. Initial zoom: from 10% of the analysed span before `actual_start` to the last price. Inside zoom (wheel, pinch) plus a "Show full history" / "Show analysed range" button as the keyboard path. Tooltip: date and price. Right-hand table: First, End of factor data, Latest, After factor data. |
| 5 Factor exposures | SVG in table | `regression.factors`, `average_beta` | `BarCell` with percentage coordinates. Bar at 36% of row height in the sign colour; faded fill plus outline when not significant; 1.5 px whisker with 3 px caps, caps dropped under 1.2% of plot width; 7 px ink diamond for the average 252-day beta on the row centre line. Columns Beta, t, Significant, Avg 252d. A native `<title>` per row. |
| 6 Return | SVG in table | `return_contribution` | Five factors, Alpha, Residual (hatched), Total (2 px rule with a cap). Memo list "Not in the sum". |
| 7 Risk | SVG in table | `risk_contribution` | Rows in `order`, factor hues, idiosyncratic hatched. Share, Beta, Factor vol and Corr as visible text; a second line under 720 px. |
| 8 Exposure over time | ECharts, five instances | `rolling`, `average_beta` | One 56 px chart per table row, joined with `echarts.connect` so zoom and the hover line move together. 1.75 px line in the factor hue over a 16% band; common vertical span, own centre. Window radios 126 / 252, default `average_beta.window`. Columns Latest, Average, Middle 80%. For the non-primary window, `derive.ts` computes mean, p10 and p90 with the prototype's linear `_quantile`; for the primary window its result must match `average_beta` within 1e-5. |
| 9 Data and audit | HTML | `data`, `notes`, `label_text` | Coverage `dl`; findings with glyph and severity word; caveats; the factor source URL as plain text. |
| Regression detail, 5-day, diagnostics, gate | HTML tables | `regression`, `five_day_regression`, `residual_diagnostics`, `quality_gate` | The detail table scrolls inside a labelled, focusable `role="region"`; nothing else scrolls sideways. |
| Colophon | HTML | `schema_version`, `generated_at` | "factordesk report, schema v3. Descriptive statistics on past data; nothing here is a forecast or advice." |

**ECharts rules.** `animation: false`. Colours come from CSS custom properties, read by `chartTokens.ts` at mount and on a `prefers-color-scheme` change. The chart container is `aria-hidden` because the table beside it carries the numbers. Tooltip formatters escape every string. `useEChart` disposes the instance on unmount and resizes with its container. ECharts loads in a lazy chunk, so the page frame and the tables paint first.

---

## DB6. Controls, URL state, data flow, states

### DB6.1 URL as state

- Shape: `/?t=SPY&range=3Y` or `/?t=SPY&start=2023-01-01&end=2026-09-30`, plus an optional `win=126`. `range` is one of `YTD 1Y 3Y 5Y FULL`, parsed without regard to case and written in upper case.
- `src/state/url.ts` exports `parseUrl(search)` and `toSearch(state)`. Invalid values are dropped, and the cleaned URL replaces the current entry (`history.replaceState`). When both forms appear, `start`/`end` win.
- A committed change (submit, chip, complete date, window) pushes a history entry. Back and Forward restore the state through `popstate`. Typing does not change the URL.
- A URL with `t` and no range means `FULL` (DB10 question 2). Every state can be linked to and survives a reload.

### DB6.2 Data flow (TanStack Query)

| Query key | Endpoint | Options |
|---|---|---|
| `["factors", "status"]` | `/api/factors/status` | `staleTime` 60 s |
| `["tickers", q]` | `/api/tickers` | 150 ms debounce on `q`, `staleTime` 60 s |
| `["ranges", t]` | `/api/report/{t}/ranges` | `staleTime` 5 min |
| `["report", t, rangeOrDates]` | `/api/report/{t}` | `staleTime: Infinity`, `placeholderData: keepPreviousData`, `retry: false` |

Ranges and report are requested in parallel. The refresh mutation invalidates `factors`, `ranges` and `report` on success. `client.ts` turns any non-2xx response into an `ApiRequestError` that holds the `ApiError`. A fetch with no response becomes `code: "network"`: "The factordesk server did not answer." / "Check that 'factordesk serve' is running, then try again."

### DB6.3 Controls strip (design I)

- One framed strip above the header holds the ticker search and "Factor it", the range chips, From and To, the analysed-range label, the reason line for disabled chips, and `FactorDataLine`: "Factor data ends 30 Sep 2026, so later dates cannot be chosen." plus a quiet "Check for newer factor data" button that calls the refresh endpoint and announces the result.
- **Ticker search.** 148 px, upper case, a `downshift` combobox. With an empty field it lists up to 8 recent tickers; with text it lists server suggestions. Enter submits the field's text; choosing a suggestion submits it. A client check with the server's ticker pattern shows an inline sentence and sends nothing when the text is invalid. Recent tickers live in `localStorage` key `factordesk.recent` (8, newest first), written only after a successful report, with every access wrapped in try/catch.
- **Chips.** Native radios in a `fieldset` with the hidden legend "Date range". Availability comes from `RangeOptions`. An unavailable chip is `disabled`, styled `--sunk` with `--ink-3` text, and its `reason` is visible text under the strip, never only a tooltip.
- **Custom dates.** Two `type="date"` fields with `max` set to the last factor date. Choosing a chip fills them with the analysed dates. A complete, valid date commits on change and clears the chip. From after To shows a sentence and sends nothing.
- **Analysed-range label.** Always visible, `aria-live="polite"`, with the static report's range-line wording ("Analysed 8 Aug 2024 to 30 Sep 2026, 559 trading days. The last 32 price days are charted but not analysed.").

### DB6.4 States

- **Landing** (no `t`): the strip with focus in the search field, the factor-data line, recent tickers, and one sentence: "Type a ticker and press Factor it, for example SPY." No report frame.
- **First load:** the full page frame at final heights: header with the ticker from the URL, KPI cells and equation as `--grid` placeholders, and panel frames with `--sunk` bodies. No spinner and no layout shift.
- **New request with a report on screen:** the previous page stays with `aria-busy="true"` on the report region, and the KPI values, equation and ticker show the `--grid` placeholder (the prototype rule `[aria-busy="true"] .kpi .v`). The strip stays usable.
- **Request error:** the notice style (square glyph, `message`, then `action`) replaces the report region. A stale report is never shown under an error.
- **Statistic not ok:** that panel shows its `EmptyState`; the other panels render normally.

### DB6.5 Download report

`<a class="btn-secondary" href="/api/report/{t}/html?{same range}" download>Download report</a>` sits in the header. It returns the offline HTML report from the unchanged renderer, so the file opens by double-click with no server.

---

## DB7. Accessibility, keyboard, mobile, theme

- **Keyboard.** `/` focuses the search unless focus is already in a text field. Enter submits. Escape closes the suggestion list. Arrow keys move within the suggestions and within the chip and window radio groups. Tab order follows reading order. Every control works without a mouse, including the price zoom toggle.
- **Focus.** A 2 px Graphite `:focus-visible` ring with a 2 px offset (design F). An equation link scrolls to and focuses its row, which gets the `--sunk` wash and the 2 px ink rule.
- **Semantics.** Bar tables keep hidden captions, `scope` and explicit roles (port `add_roles()` from the prototype). SVG and chart containers are `aria-hidden`. The report region carries `aria-busy` while loading. Status uses a glyph plus a word, never colour alone.
- **390 px.** No horizontal page scroll (`document.documentElement.scrollWidth === 390`). The search row is full width, chips fill one row, and every target is at least 44 px tall. The KPI strip has two columns, risk details move to a second line, and only the regression table scrolls sideways.
- **Width.** The content column is at most 1216 px and centred, including at 1920 px.
- **Theme.** Follows `prefers-color-scheme`; `html[data-theme]` overrides it both ways. No theme switch in v1.
- **Motion.** None. A `prefers-reduced-motion` block neutralises any transition added later.
- **Print.** Controls are hidden. The supported print path is "Download report", which prints on A4 as designed.

---

## DB8. Serving, tests, CI

### DB8.1 Commands

| Purpose | Command | What it does |
|---|---|---|
| Develop | `npm --prefix frontend run dev` | `concurrently` runs `uv run factordesk serve --dev` (API only, uvicorn reload, port 8000) and Vite on 5173 with a proxy from `/api` to `http://127.0.0.1:8000`. Open `http://localhost:5173`. |
| Build the page | `npm --prefix frontend run build` | `tsc --noEmit`, then `vite build` into `frontend/dist/` (gitignored by `dist/`). |
| Run | `uv run factordesk serve [--open]` | API and built page on `http://127.0.0.1:8000`. |

`factordesk serve` is a new subcommand in `backend/factordesk/cli.py` with `--host` (default `127.0.0.1`), `--port` (default 8000), `--dev`, `--static DIR` (default `frontend/dist`, found from the package location as `Path(__file__).resolve().parents[2] / "frontend" / "dist"`) and `--open`. Without `--dev` it runs `uvicorn.run(create_app(default_deps(static_dir)))`. With `--dev` it runs the import string `factordesk.api.main:create_dev_app` with `factory=True, reload=True` (API only). Errors are one line with the existing exit codes: a missing build prints "the dashboard is not built; run 'npm --prefix frontend run build' first, or use --dev" and exits 2, and a busy port exits 2. A host other than loopback prints a warning that the dashboard has no login. The `report` and `factors` commands and their output stay unchanged.

**Static serving (`api/static.py`).** `/assets/*` comes from `dist/assets` with `Cache-Control: public, max-age=31536000, immutable`. Any other GET outside `/api` returns `index.html` with `Cache-Control: no-cache`. `/api/*` never falls back. Page responses carry `Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self'; frame-ancestors 'none'`, `X-Content-Type-Options: nosniff` and `Referrer-Policy: no-referrer`. There is no CORS middleware: development goes through the Vite proxy and production is same-origin.

### DB8.2 Tests

- **pytest, no network.** `backend/factordesk/tests/test_api_basic.py` and `test_api_report.py` use FastAPI's `TestClient` with fake `AppDeps`. They cover every row of DB2.1 and DB2.3; the range rules of DB2.4, including 29 February; that an invalid ticker never reaches the provider (`StaticProvider.calls` stays empty); in-flight de-dup (two concurrent requests for one key give one provider call and one build, with a provider that waits on a `threading.Event`); a cache hit; a rebuild after a new vintage; that `range=3Y` and the same explicit dates share a cache entry; that the HTML body equals `render_report_html` of the JSON report byte for byte; the static fallback and the `/api` 404; no NaN in any body; and `test_openapi_is_current`, which compares `app.openapi()` with `frontend/src/api/openapi.json`. Pipeline: `start`/`end` reach `SampleInfo.requested_start`/`requested_end`, and the defaults give an unchanged report.
- **Vitest and Testing Library** (jsdom; MSW with `onUnhandledRequest: "error"`). The fixture is `backend/factordesk/tests/fixtures/mock_report.json` through a Vite alias, plus mutated copies for empty states. Cases: format rules; URL round-trip and cleaning; the combobox (recent list, suggestions, Enter, Escape, `/`); disabled chips with a visible reason; From/To clearing the chip; each panel's table numbers and empty state; `derive.ts` against `average_beta` within 1e-5; the tokens test (no hex colour outside `tokens.css`).
- **Playwright smoke** (one file, `e2e/smoke.spec.ts`). `webServer` starts `uv run uvicorn factordesk.tests.fixtures.fake_app:create --factory --port 8765`. The new fixture `fake_app.py` builds `create_app` with `dgp_a` prices, a factor frame cut 30 rows before the price end, a fixed clock, an unknown ticker `XYZ` and `frontend/dist`. Requests to any host other than 127.0.0.1 are aborted and fail the test. Steps: open `/`, type SYN, press Enter, wait for the KPI strip; choose 3Y and check the URL, the label, and that 1Y is disabled with a reason; open `/?t=XYZ` and see the error notice; check the Download link `href`; at 390 px check `scrollWidth`.
- **Visual check** (local, before review). `e2e/shots.spec.ts` (run with `npx playwright test --grep @shots`, Playwright `channel: "chrome"`, which uses `C:\Program Files\Google\Chrome\Application\chrome.exe`) saves 1440 and 390 in light and dark, and 1920 in light, to `frontend/shots/` (gitignored). A quick light shot without Playwright: `"C:\Program Files\Google\Chrome\Application\chrome.exe" --headless=new --hide-scrollbars --window-size=1440,4200 --virtual-time-budget=15000 --screenshot=frontend/shots/quick.png "http://127.0.0.1:8765/?t=SYN"`. Compare with `docs/design/prototype/shot_*.png`: a 1216 px column, Instrument Sans everywhere except the STIX equation, colour only on marks, five KPI cells, the notice with Details, no sideways scroll at 390. Screenshots use synthetic data only (real-data images stay out of the repository).

### DB8.3 Gates and CI

- Backend: `uv run ruff check`, `uv run pyright`, `uv run pytest`.
- Frontend: `npm run typecheck` (`tsc --noEmit`), `npm run lint` (ESLint with `typescript-eslint`, `react-hooks`, `jsx-a11y` and `react/no-danger`), `npm test` (`vitest run`), `npm run build`, and `npm run gen:types` followed by `git diff --exit-code frontend/src/api`.
- CI: on 2026-11-18 there is no `.github/workflows/ci.yml`. T10 creates it (or extends it, if the pending CI item lands first) with three jobs on pull requests to `dev` and `prod`: `python` (ubuntu and windows: ruff, pyright, pytest), `frontend` (ubuntu, Node 26: `npm ci`, typecheck, lint, test, build, types check) and `e2e` (needs both; ubuntu; `npx playwright install --with-deps chromium`; smoke only). Live, slow and screenshot tests do not run in CI.

---

## DB9. Tickets

Work lands on `feat/dashboard-*` branches from `dev`, one pull request per ticket. Size hint: haiku = mechanical, sonnet = standard, opus = hard. Paths under `api/`, `report/` and `tests/` are inside `backend/factordesk/`.

| Id | Scope (files) | Acceptance criteria | Depends on | Size |
|---|---|---|---|---|
| T1 API skeleton | `api/main.py` (`create_app`, `create_dev_app`), `api/deps.py`, `api/errors.py`, `api/routes_factors.py`, `api/openapi_dump.py`, the DB2.2 models in `report/schema.py`, `tests/test_api_basic.py`, `frontend/src/api/openapi.json` (generated) | Health, factor status, factor refresh (single-flight; a failure keeps the cache), ticker suggest; `ApiError` handlers for every DB2.3 row that applies; unknown `/api` path gives 404; every DB2.2 model exists, so T2 never edits `schema.py`; pytest, ruff and pyright green | – | sonnet |
| T2 Report endpoints | `pipeline.py` (`start`/`end`), `api/ranges.py`, `api/service.py`, `api/routes_report.py`, `tests/test_api_report.py`, `tests/test_pipeline.py` | DB2.1 report, ranges and html rows; DB2.4; DB3 de-dup, caches and worker threads; CLI output unchanged (existing `test_cli.py` green); every DB8.2 backend case for these endpoints | T1 | opus |
| T3 Frontend scaffold | `frontend/` tooling files, `src/main.tsx`, `src/App.tsx` shell, `src/styles/*`, `src/assets/fonts/*`, `src/format/*`, `src/text/plain.ts`, `src/api/client.ts`, `src/api/types.gen.ts`, `components/report/{ReportView,Panel,EmptyState,HowComputed}`, `components/charts/*`, and a stub file with agreed props for every panel and control (`{ report: FactorReport }` for panels) | `npm run dev`, typecheck, lint, test and build pass; tokens match design A in both themes; fonts load from the bundle; 1216 px column; format tests and the tokens test pass; every stub renders a titled empty `Panel` | – (its last step, `types.gen.ts`, needs T1's `openapi.json`) | sonnet |
| T4 Controls and URL state | `src/state/*`, `src/api/queries.ts`, `components/controls/*`, controls wiring in `App.tsx` | DB6.1 to DB6.4 in full; `/` shortcut; recent tickers; refresh button; landing, loading and error states; the Vitest cases of DB8.2 for these files | T3 | sonnet |
| T5 Header to KPI | `Header`, `Notice`, `Equation`, `KpiStrip`, `GateCallout`, `Colophon` | DB5 rows 1 to 3; equation links focus their rows; the equation wraps at 390 px with brackets kept; the Download link of DB6.5; empty states | T3 | sonnet |
| T6 Price and exposures | `PricePanel`, `ExposuresPanel`, hardening of `charts/useEChart.ts` | DB5 rows 4 and 5; cut labels and bands as specified; zoom toggle works by keyboard; cap and diamond sizes as specified; the tables carry every number | T3 | sonnet |
| T7 Return, risk, rolling | `ReturnPanel`, `RiskPanel`, `RollingPanel`, `src/report/derive.ts` | DB5 rows 6 to 8; connected rolling charts; window radios with `win` in the URL through the `url.ts` interface agreed in T3's stubs; the derive test within 1e-5 | T3 | sonnet |
| T8 Data, audit, detail | `DataAuditPanel`, `RegressionDetail` (with the 5-day and diagnostics tables) | DB5 row 9 and the regression detail row; focusable scroll region; "No findings. Prices passed every check." when empty | T3 | sonnet |
| T9 Serve and static | `cli.py` (`serve`), `api/static.py`, the mount in `api/main.py`, additions to `tests/test_cli.py`, the `dev` script in `frontend/package.json` | DB8.1 in full; security headers; a missing build and a busy port end with one line; `uv run factordesk serve --open` shows the built page | T2, T3 | sonnet |
| T10 E2E and CI | `tests/fixtures/fake_app.py`, `frontend/e2e/*`, `frontend/playwright.config.ts`, `.github/workflows/ci.yml`, `.gitignore` (`frontend/shots/`) | The smoke test passes locally and in CI; the DB8.3 jobs are green on the pull request | T4 to T9 | sonnet |
| T11 Design and accessibility review | Read-only review of the running page; findings filed as fix tickets | Shots at 1440, 1920 and 390, light and dark, compared with the prototype; a keyboard-only pass; an axe scan with no violations; findings dated in the pull request | T10 | opus |

**Parallel groups (disjoint file sets).**
- Wave A: T1 (backend `api/`) and T3 (`frontend/`) run in parallel.
- Wave B: once T1 and T3 are merged, T2 (backend) and T4, T5, T6, T7 and T8 (each with its own component files) run in parallel. `App.tsx` belongs to T4. `ReportView.tsx` from T3 places the panels, so panel tickets never touch it.
- Wave C: T9 after T2 and T3; then T10; then T11.

---

## DB10. Open questions for the owner (answered 2026-11-18, see Owner decisions)

1. **Short ranges.** The pipeline refuses fewer than 504 aligned days (`MIN_OBS` in `analytics/sample.py`), so YTD and 1Y can never run. Recommended default: keep 504 and show both chips disabled with the reason. A lower minimum would be a methodology change through `docs/research-protocol.md`.
2. **Default range** when the URL has only a ticker. Recommended default: Full history, so the page matches the CLI report and "Download report" gives the same file.
3. **Online ticker search** (names and exchanges from Yahoo). Recommended default: no. Suggestions come from tickers already fetched plus recent tickers, so the server makes no extra calls to Yahoo.
4. **Stack deviations** in DB0 (no Tailwind or shadcn/ui; ECharts only for price and exposure over time). Recommended default: approve, and record it on the application-stack wiki page.
5. **Navigation.** PLAN.md has Ticker and Factors views with sub-tabs. Recommended default: one scrolling page now; add the Factors view when its backend exists.

## Owner decisions

On 2026-11-18 the owner answered DB10 as follows. These override any earlier text in this file.

1. **Short ranges: drop the YTD and 1Y chips.** Presets are 3Y, 5Y and Full history only. `RangeOptions` has three presets; no chip is disabled for being too short, but a preset still becomes unavailable when the ticker has fewer than `MIN_OBS` aligned days (for example 5Y on a young stock), with the visible reason. `MIN_OBS` stays 504.
2. **Default range: Full history.**
3. **No online ticker search.** Suggestions come from fetched and recent tickers.
4. **Stack deviations approved:** plain CSS tokens, no Tailwind or shadcn/ui; ECharts only for price and exposure over time. Record on the application-stack wiki page.
5. **One scrolling page, no tabs.**

Branching: agents commit on the current feature branch (`feat/report-ui-feedback`); one pull request for the owner to review, not one per ticket.
