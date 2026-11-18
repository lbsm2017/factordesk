# factordesk: Fama-French 5-Factor Analyzer

## Context

Greenfield project in `c:\Users\loren\Research\factors` (empty, not a git repo). The goal is a terminal-style dashboard, "factordesk", where you type a ticker and press **Factor it**. It downloads daily prices (yfinance) and the public Fama-French 5-factor daily data (Ken French Data Library), regresses the stock on the factors, and shows:

1. Daily price line chart with shaded regions where each factor was dominant.
2. EDA panels: average beta, positive/negative betas, contribution to return, contribution to risk, cointegrations.

A second button downloads or refreshes the factor data, and it also runs automatically when the local factors are stale.

**Environment findings.**
- Node 26 and npm are installed.
- **Python is not installed.** Only the Windows Store stub exists. `uv` (`C:\Users\loren\.local\bin\uv.exe`) and `winget` are present, so `uv` can provision Python 3.12 without admin rights.
- Python is required: statsmodels gives HAC regression, Engle-Granger and Johansen tests.

**Decisions made (your answers + defaults):**
- Prices come from **yfinance only for now**, with extra care on adjusted close. Alpaca is wired in as an adapter stub plus `.env` keys, but not called yet.
- Cointegration panel = ticker vs factor indices **plus** peer tickers.
- Stack: FastAPI (Python) backend, Vite + React + TypeScript frontend, Tailwind v4 + shadcn/ui, Apache ECharts for all charts.
- No Plan/Explore agents were needed. This is greenfield and the skill references were read directly.

## Architecture

```
factors/
  .env                 # placeholders only, gitignored (ALPACA_API_KEY, ALPACA_SECRET_KEY, ALPACA_DATA_FEED=iex)
  .env.example         # committed template
  pyproject.toml       # uv-managed: fastapi, uvicorn, pandas, numpy, statsmodels, scipy, yfinance,
                       #   pydantic-settings, pyarrow, httpx, alpaca-py (stub only); dev: pytest, ruff, pyright
  CODING_STANDARDS.md  PRODUCT.md  DESIGN.md  README.md
  backend/factordesk/
    config.py                    # pydantic-settings reads .env
    data/prices.py               # PriceProvider protocol, YFinanceProvider, AlpacaProvider (NotImplemented stub)
    data/factors.py              # French downloader, parser, staleness policy, atomic parquet write
    data/audit.py                # data-quality + adjusted-close verification
    analytics/regression.py      # OLS + Newey-West HAC, alpha, VIF
    analytics/rolling.py         # trailing-window betas (point-in-time, no look-ahead)
    analytics/dominance.py       # dominant-factor regions
    analytics/attribution.py     # return and risk contribution
    analytics/cointegration.py   # Engle-Granger, Johansen, half-life, split-sample OOS, BH correction
    api/main.py  report/schema.py  # typed pydantic response models are the only contract
    tests/  (fixtures/ = synthetic known-beta data + frozen real samples)
  frontend/                      # Vite React TS, Tailwind v4, shadcn/ui, ECharts, TanStack Query
  data/                          # gitignored caches (factors parquet + meta.json, price cache)
  docs/ROADMAP.md  docs/methodology.md
  wiki/                          # chief-of-staff memory (index.md + dated pages)
```

**API (typed, minimal):**
- `GET /api/health`
- `GET /api/factors/status` returns `{last_date, days_behind, last_download_at, source_url, stale}`
- `POST /api/factors/refresh`
- `POST /api/factor-it` takes `{ticker, start?, beta_window=252, include_market_in_dominance=false, peers?[]}` and returns one `FactorReport` containing everything below.

## Quant methodology (grounded in the quantitative-research references)

**Data**
- **Factors.**
  - Source: Ken French's `F-F_Research_Data_5_Factors_2x3_daily` zip. Verify the exact URL in the spike.
  - The zip is read in memory only (no extraction to disk) and validated: expected columns, values in percent converted to decimals, `-99.99`/`-999` treated as missing, monotonic dates.
  - Parquet is written atomically (tmp + rename). A failed download keeps the previous file.
  - French data lags about 1-2 months. The price chart greys out the tail with no factor coverage, and the UI shows "Factors through YYYY-MM-DD".
- **Auto-refresh rule.** Refresh when `today - last_date > 40 days` AND the last attempt is more than 12 hours old, checked on app start and on every Factor it. A `HEAD` request on Last-Modified avoids needless downloads. The manual button always forces a refresh.
- **Prices (adjusted-close care, revised after the yfinance research).**
  - One fetch per ticker with `auto_adjust=False, actions=True`, every argument passed explicitly (defaults changed in 0.2.51). This returns both `Close` and `Adj Close`.
  - Yahoo's `Close` is **already split-adjusted**. Never multiply by `Stock Splits` again. That column is used only to check for a missing split adjustment.
  - Regression returns come from `Adj Close` (total return, matching FF). The audit recomputes total return as `(Close_t + Div_t) / Close_{t-1} - 1` and compares it to `Adj Close` returns **per dividend event and per calendar year**, not only as cumulative drift, so one bad dividend cannot hide.
  - For funds, check the `Capital Gains` column so distributions are not double counted.
  - `repair=False` by default (yfinance's repair has had its own 100x bugs). The audit reports problems instead of silently fixing them.
  - Always re-download full history, because adjusted history changes at each dividend. Keep our own same-day disk cache and let yfinance own its `curl_cffi` session (it rejects caching sessions).
  - Normalise the two-level columns, convert the exchange-timezone index to plain dates, and drop today's incomplete bar.
  - Invalid or delisted ticker: detect an empty or all-NaN result and return a clear error. `download()` does not raise.
  - Also flag `|ret| > 40%`, zero prices, duplicate stamps, gaps and stale runs. Rows are never dropped or zero-filled silently.
- **Excess returns.** `r_i - RF` using simple returns, with an inner-join on dates.
- **Guards.**
  - Refuse below 504 observations. Warn below 750 (~3 years).
  - Show a regime-coverage badge (2008, 2020, 2022 covered or not).
  - Show a US-factors caveat for non-US tickers.
  - Add a survivorship note.

**Regression.** Full-sample `r-rf = a + b1(Mkt-RF) + b2 SMB + b3 HML + b4 RMW + b5 CMA + e`, with Newey-West HAC t-stats (lag = floor(4(T/100)^(2/9))). Report annualised alpha (x252) with its t-stat, R², adjusted R², n, window, and VIF/condition number on the factors (HML/CMA/RMW collinearity warning). Betas are marked significant after Benjamini-Hochberg across the 5 tests.

**EDA panels**
- **Average beta.** Mean and dispersion of trailing-252d rolling betas, shown beside the full-sample beta. Trailing only, so no look-ahead. Show a sparkline per factor.
- **Positive/negative beta.** Diverging bars with 95% HAC CIs, with significant betas solid and insignificant hatched or muted.
- **Contribution to return.**
  - Per factor: `b_i x mean(f_i) x 252`, plus alpha.
  - Alpha + sum of factor contributions = annualised mean excess return, **exactly**. This is an OLS identity and a unit test.
  - Shown as a waterfall plus a per-calendar-year table.
- **Contribution to risk.**
  - Euler decomposition: `var = b' S_f b + s²_e`, `RC_i = b_i (S_f b)_i / var`, idiosyncratic = `s²_e / var`.
  - Sums to 100%, also a unit test.
  - Shown as sorted horizontal bars.
- **Cointegration.**
  - Series: `log(price)` of the ticker vs `log(cumprod(1+f))` for each of the 5 factor indices, plus peers (default SPY, QQQ, IWM and a sector ETF if resolvable, editable).
  - Per pair: Engle-Granger p, Johansen trace as confirmation, hedge ratio, residual ADF, half-life (flag 5-60 days), and a split-sample test (hedge ratio fitted on the first 60%, ADF on the last 40% with the ratio frozen).
  - Benjamini-Hochberg across **all** tests in the table.
  - Labelled "exploratory long-run link" because cointegration with cumulative factor indices is unconventional and spurious on short or single-regime samples.

**Chart shading ("dominant factor")**
- Definition: at day t, with a trailing 252d window, the factor with the largest risk contribution `RC_i,t` is dominant. This is point-in-time and sign-agnostic.
- Because Market dominates almost everywhere, the default is **style-dominance** (SMB, HML, RMW, CMA) with a toggle to include Mkt-RF.
- A 10-day minimum-run merge stops flicker. Opacity scales with the dominance share. The warm-up period is unshaded.
- Parameters kept to 3 (beta window, min-run, include-market) to stay under the overfit guideline.
- Every panel carries a "descriptive, in-sample, not predictive" footnote.

**Test oracle (opus-designed):**
- Synthetic series with known betas must be recovered within HAC SE.
- The return and risk identities must hold to 1e-10.
- A statsmodels cross-check.
- Known cases: SPY gives Mkt beta ~1, other betas ~0, alpha insignificant. A split-heavy name (NVDA/AAPL) passes the adjusted-close audit.

## Added scope (approved 2026-11-18)

**In v1**
- **Rolling beta drift + style-drift alerts.**
  - Chart of each trailing-252d beta through time with HAC confidence bands.
  - Alert when (a) the current rolling beta sits more than 2 sd from its own rolling history, (b) a significant beta flips sign, or (c) a Wald test (HAC) rejects equality of the latest window vs the non-overlapping window one year earlier.
  - CUSUM residual test (`statsmodels.stats.diagnostic.breaks_cusumolsresid`) as a whole-sample structural-break flag.
  - Alerts are BH-corrected across the 5 factors and surfaced in the KPI strip.
- **Regime-conditional betas.**
  - Up vs down market (sign of Mkt-RF) via interaction-dummy regression, giving downside beta and a Wald test of the difference.
  - High vs low volatility: trailing-21d realised market vol against its own trailing-252d median, point-in-time.
  - Crisis windows 2008, 2020, 2022, shown only where n >= 60.
  - Small-multiple bars per factor, with "insufficient data" states.
- **Factor dashboard** (ticker-independent "Factors" view): per-factor cumulative return, drawdown, rolling-252d Sharpe, correlation matrix (full sample and trailing 1y), current trailing-1y return percentile.
- **Factor crowding / stretch proxy.** Z-score of each factor's trailing 12m and 36m return against its full-history distribution, plus drawdown-from-peak. Labelled a *return-based proxy*, not a valuation spread (that needs holdings data we do not have).

**Deferred**
- Next: peer comparison (sector distribution of betas).
- Next (owner confirmed 2026-11-18, needs a design pass): **European mode** first, then other regions. For European tickers, download the French **Europe 5-factor daily** file, convert the stock's return to USD, and add the currency return as an extra regressor with its own beta, risk share and contribution. Until then non-USD tickers get a warning only.
  - Verified on 2026-11-18: the library publishes daily 5-factor files for `Europe`, `Developed`, `Developed_ex_US`, `Japan`, `North_America` and `Asia_Pacific_ex_Japan` (pattern `ftp/<Region>_5_Factors_Daily_CSV.zip`), plus `Europe_Mom_Factor_Daily_CSV.zip` for momentum.
  - `Europe_5_Factors_Daily_CSV.zip` held 9,458 daily rows from 1990-07-02 to 2026-09-30. Same row layout as the US file, missing values marked `-99.99`, built from a Bloomberg database (the US file uses a different source).
  - Not yet verified: the currency the returns are quoted in (assumed USD, to confirm on the library's description page), the list of countries inside "Europe" (UK included?), and which risk-free rate the file carries.
  - Consequences for design: a region-aware factor loader (one cache file per region), a ticker-to-region map (exchange suffix: `.DE`, `.PA`, `.L`, `.MI`, `.AS`, `.SW`, ...), a currency map and FX fetcher (EUR, GBP, CHF, SEK, DKK, NOK), pence handling for `.L` tickers, and a shorter history (starts 1990, so the 2008 and 2020 regime windows are covered but earlier ones are not).
- Later: factor-mimicking hedge, model comparison (CAPM/FF3/FF5/+MOM), portfolio mode, screener, out-of-sample stability score.

**Navigation change.** Two top-level views: **Ticker** and **Factors**. The Ticker view gets sub-tabs: Overview (price + dominance, KPI, betas) | Exposures (drift, regimes) | Attribution (return, risk) | Cointegration.

## Lessons from GitHub analogs (researched 2026-11-18)

Sources read: pyfolio-reloaded + empyrical-reloaded, quantstats, skfolio, equity-risk-model, KrishKPs/GS_QUANT (closest analog: FastAPI + React), quant-lab-alpha, aistatcharts, factorlens, portfolio-tracker, open-climate-investing, pandas-datareader, yfinance issues.

**Adopt**
- **French file.** URL verified live: `https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Research_Data_5_Factors_2x3_daily_CSV.zip` (data through 2026-09-30, about one month lag). Write our own ~30-line parser: header = first line starting with a comma, keep rows matching `^\d{8}`, strip spaces, decode latin-1, divide by 100. Do not depend on pandas-datareader (fragile, most readers broken). On each refresh, diff old vs new values and log revisions.
- **Tilt vs timing** (pyfolio). Split return contribution into tilt (mean rolling beta x factor return) and timing (the rest). Timing shows what the stock's changing exposures added.
- **Unattributed row** (skfolio). Alpha, residual and dates without factor coverage are shown as an explicit component, never folded in.
- **Exposure x volatility x correlation view** (skfolio) as a tooltip/detail on each risk-contribution bar.
- **"Disagreement" sentence** (GS_QUANT). Call out a factor whose share of risk ranks higher than its beta.
- **Reliable vs noise tags** on betas (|HAC t| >= 2), and interpretation text only for significant coefficients (portfolio-tracker). Explain why a large alpha can be insignificant.
- **Two rolling windows overlaid** (126d and 252d, as quantstats and quant-lab-alpha do), with opacity by window length.
- **Style-drift magnitude** (factorlens): Euclidean norm of the change in the beta vector, plus its z-score, as a single drift number in the KPI strip.
- **Requested vs actual dates** shown on every result, so inner-join truncation is never silent (three analogs truncate silently).
- **Residual diagnostics** (Ljung-Box, Jarque-Bera, Durbin-Watson) in a details drawer, each with what it justifies.
- **Shareable state.** Ticker and parameters live in the URL.

**Avoid (bugs seen in the wild, each becomes a test)**
- Rolling window off by one (pyfolio returns W+1 observations). Test exact window length.
- `fillna(0)` on returns or betas (quantstats: beta collapses to zero). NaN raises or is reported.
- Compounding components separately and expecting them to sum (pyfolio, aistatcharts). We use arithmetic contributions and label them as such.
- Regressing raw returns without subtracting RF (quantstats, open-climate).
- Factor risks that do not add up (equity-risk-model). Euler only.
- Lasso or no-intercept loadings (skfolio default). Plain OLS with intercept.
- Dropping extreme rows (open-climate removes real crash days). Flag, never drop.
- Factor cache that never expires (portfolio-tracker), currency mismatch between returns and factors.

## Sprint plan (lands in docs/SPRINTS.md)

Team = agent pool under one DRI. Capacity is counted in story points, planned at ~75% load. No calendar dates: a sprint ends when its goal and Definition of Done are met.

| Sprint | Goal | Backlog (priority, points, model) |
|---|---|---|
| **S1 Trustworthy numbers** | `POST /api/factor-it` returns a validated `FactorReport` for SPY, AAPL, NVDA. | P0 E0 foundations: uv Python, git, tooling, standards, wiki, `.env` (3, haiku). P0 methodology spec + test oracle (5, opus). P0 French downloader + staleness (5, sonnet). P0 yfinance provider + adjusted-close audit (5, sonnet). P0 regression, rolling, attribution, risk (8, sonnet). P0 API + schemas (3, sonnet). P1 cointegration module (5, sonnet). P0 opus math review (3, opus). Total 37. |
| **S2 Dashboard v1** | A user can type a ticker, press Factor it and read all five original panels. | P0 PRODUCT.md, design system, comp (5, opus). P0 app shell, command bar, refresh flow, states (5, sonnet). P0 price chart with dominance shading (8, sonnet). P0 betas, return, risk panels (8, sonnet). P1 cointegration panel (5, sonnet). P0 Playwright screenshot harness (2, haiku). P0 impeccable critique + fixes (3, opus + sonnet). Total 36. |
| **S3 Factor-investing depth** | Drift alerts, regime betas and the Factors view are live and validated. | P0 drift + alerts backend (5, sonnet). P0 regime-conditional betas backend (5, sonnet). P0 Exposures tab UI (5, sonnet). P0 factor dashboard backend + view (8, sonnet). P1 crowding/stretch proxy (3, sonnet). P1 tilt/timing split + diagnostics drawer (3, sonnet). P0 opus validation of new statistics (3, opus). P0 audit, polish, release candidate (5, opus + sonnet). P2 stretch: peer comparison (5). Total 37 + 5 stretch. |

**Cut order if a sprint overruns:** S1 cointegration moves to S2. S2 cointegration panel moves to S3. S3 drops stretch, then tilt/timing, then crowding proxy.

**Risks**

| Risk | Impact | Mitigation |
|---|---|---|
| yfinance rate-limit or breakage | Factor it fails | Same-day cache, clear error state, frozen fixtures for tests, provider interface ready for Alpaca. |
| French URL or format change | No factors | Validate schema on download, keep last good file, spike verifies URL first. |
| Statistical false alarms in drift alerts | User distrust | BH correction, require two of three alert conditions for a "strong" alert, show test details. |
| Regime slices too small | Noisy betas | Minimum n = 60, wide-CI display, "insufficient data" state. |
| Design drifts to generic dashboard | Misses the brief | Opus-owned comp before UI code, impeccable critique gate at end of S2 and S3. |

**Definition of Done (every item):** tests, `ruff`, `pyright`, frontend build green; reviewed by a different agent than the author; UI items screenshot-verified in dark and light; wiki updated with any decision; methodology doc updated for any new statistic.

## UI / design direction (impeccable "Operate" mode)

Run order: `impeccable init` writes PRODUCT.md. `ui-ux-pro-max --design-system --persist` (dials: density 8, variance 3, motion 2) writes the design system to `design-system/`. `ui-taste` research and a target comp come next. Chart palette is validated with the `dataviz` skill. Then build with `ui-styling` (`shadcn init`, Tailwind v4). Finish with `impeccable critique`, `audit`, `polish`.

- **Look.** Material 3 tonal-surface logic on cool graphite, dark default with a light theme. Hairline 1px borders, no gradients, glow or glassmorphism. One restrained accent. Red/green are reserved for sign semantics and always paired with +/- glyphs. No Bloomberg orange-on-black, no emoji icons.
- **Type.** Candidate pair: IBM Plex Sans (UI) + IBM Plex Mono with tabular numerals, to be confirmed by the design-system run. Minimum body 13px at this density.
- **Factor colors.** Five colorblind-safe categorical hues (dataviz-validated), identical across the chart shading, beta bars and risk bars.

```
┌ factordesk ─ [ / search ticker...        ] [Factor it] ── ● FF5 thru 2026-09-30 · [Refresh factors] ┐
├ KPI strip: Alpha(ann) t · R² · Obs · Window · Coverage badges · warnings ─────────────────────────┤
│ Price + dominant-factor shading (dataZoom)  (≈65%)   │ Betas: full vs avg, ± CI, sign     (≈35%)  │
├──────────────────────────────────────────────────────┴──────────────────────────────────────────┤
│ Return contribution (waterfall) │ Risk contribution (bars) │ Cointegration table + spread chart │
└ status bar: source · as-of · data audit result · API latency ───────────────────────────────────┘
```

`/` focuses search, Enter = Factor it, recent-ticker chips, skeleton loaders (no layout shift), explicit empty, error and stale states, keyboard-reachable everything, `prefers-reduced-motion` respected.

## Roadmap (docs/ROADMAP.md, Now/Next/Later, outcome-framed)

| Horizon | Epic (hypothesis -> metric) | Size |
|---|---|---|
| **Now** | E0 Foundations: Python via uv, git init, tooling, CODING_STANDARDS, wiki, `.env`, design system -> agents can ship without environment friction. Metric: `uv run pytest && ruff && pyright` and `npm run build` green. | S |
| Now | E1 Data layer (factors + prices + audit) -> trustworthy inputs. Metric: audit passes on 5 reference tickers; failed download keeps old file. | M |
| Now | E2 Analytics core -> correct numbers. Metric: oracle tests green, identities to 1e-10. | M |
| Now | E3 API -> one typed `FactorReport`. Metric: warm Factor it p95 < 3 s. | S |
| Now | E4 Dashboard shell + search/Factor it/Refresh -> one-keystroke flow. | M |
| Now | E5 Price chart with dominance shading; EDA panels; cointegration panel. | L |
| Now | E6 Validation + polish -> release candidate. Metric: opus validation sign-off, impeccable audit clean, screenshots at 1440/1920/390. | M |
| Next | Alpaca adapter live: cross-check of the overlap window and fallback. Add Carhart momentum / FF6 toggle. Persistent watchlist/peers. CSV/PDF export. | M |
| Later | International factor sets, multi-ticker portfolio view, regime (HMM) overlay, rolling OOS alpha-stability test. | L |

Dependency order: E0 -> E1 -> E2 -> E3 -> (E4 || E5 data wiring) -> E6. E4 UI work can start after E0 design-system and E3 schemas are frozen.

## Chief-of-staff operating model

I act as DRI. All work goes to **background subagents with fresh context**, and I communicate through context pointers (files, wiki pages), not pasted text.

| Model | Work |
|---|---|
| **haiku** (mechanical) | Scaffold repo and folders, `.gitignore`, `.env`/`.env.example`, README stubs, lint/format config, `pyproject`/`package.json` boilerplate, copy design tokens into CSS, wiki index upkeep, running test/lint suites and reporting output. |
| **sonnet** (medium) | Price and factor providers, API endpoints, pydantic schemas, React components and ECharts wrappers, unit tests, bug fixes from reviews. |
| **opus** (strategic, quality, validation) | Methodology spec and test oracle, review of regression / Euler risk / cointegration math, dominance definition, design direction and comp, adversarial review of each epic, final validation, retros on ~1 in 5 subagent sessions (failures first), roadmap re-sequencing. |

**Wiki** in `wiki/` (`index.md` + one page per decision, dated claims, cite commit once git exists). **Pit-of-success improvements:**
- Typed `FactorReport` is the only API surface.
- `ruff` + `pyright` strict.
- `CODING_STANDARDS.md` (no look-ahead, no bare `shift(-n)`, no hardcoded keys, units always decimals).
- Synthetic-data fixtures.
- Playwright screenshot script so agents can see the rendered UI.
- Dev-server log file agents can read.
- "No workarounds" rule: convention breaks get fixed before feature work.

**Suggested schedules** (via `/schedule`, after approval): weekly wiki lint, monthly factor-freshness check (French publishes monthly), periodic dependency/yfinance-breakage smoke test (yfinance scrapes Yahoo and breaks often).

## Verification (end-to-end)

1. `uv run pytest` (oracle + identity + audit tests), `ruff`, `pyright` all green.
2. Start API and frontend. Run Factor it on **SPY** (Mkt ~1, alpha ~0), **AAPL / NVDA** (splits: adjusted-close audit clean), a **recent IPO** (clean refusal message), an **invalid ticker** (error state).
3. Delete or age the factor parquet, then confirm auto-download triggers, the refresh button works, and a simulated download failure keeps the old file.
4. Check the return identity (alpha + factors = mean excess return) and the risk-sum-to-100% identity in the live payload.
5. Playwright screenshots at 1440, 1920 and 390 wide in dark and light. Inspect them, run impeccable audit/critique, fix in one batch, re-inspect.
6. Opus validation agent signs off on the methodology versus `docs/methodology.md` before release candidate.

## Needs your approval at execution time
- `uv python install 3.12` and `uv sync` (installs Python locally, no admin).
- `git init` in the project folder.
- Wiki location `wiki/` inside the project.
- Alpaca keys go in `.env` later (not needed for v1).
