# Spec: next stage — track-record upload, SAA portfolio backtest, FF6 and macro factors

Date: 2026-11-19
Status: Approved by the owner on 2026-11-19
Research: [next-stage research notes](../research/next-stage-research.md)

## Context
factordesk answers one question today: how much of a US ticker's return is Fama-French factor exposure (daily data, FF5). The owner wants the same answer for two new inputs:
- **An uploaded manager or fund track record:** is the return alpha, or cheap beta?
- **A model portfolio:** built in a tree that mirrors the Venn/Risk Pro SAA editor, backtested with fixed weights and monthly rebalancing.

Every mode also gets momentum (FF6), a strip comparing alpha across models, and macro sensitivities (rates, credit, EUR/USD).

The new screens must blend in exactly with the current fintech v2 UI.

**Delivery model:**
- Agile, continuous delivery.
- A thin vertical slice first, then increments that each work end to end.
- Epics prioritised with RICE and MoSCoW.

Three research tracks are done:
- track-record statistics;
- backtest mechanics;
- factor proxies and prior art (Venn, Portfolio Visualizer, Morningstar/MSCI).

The owner's decisions from three question rounds are listed below.

## Owner decisions (2026-11-19)
**Scope and data**
- **Engine:** one engine. Every report runs on a "return subject" (ticker, upload or portfolio; daily or monthly). Sections declare which subjects they support and hide otherwise.
- **Interface:** dashboard only. A navy-sidebar mode switch: Ticker / Track record / Portfolio.
- **Currency:** USD only in v1. Portfolios use US-listed proxy ETFs; cash earns the French risk-free rate. EUR base currency and UCITS ETFs come later, with European mode.

**Factors (all modes)**
- **Models:** FF5/FF6 toggle (FF6 = FF5 + Mom). An alpha strip (CAPM / FF3 / FF5 / FF6) on the same sample, with no "best model" highlight.
- **Macro section** (separate regression; raw betas plus VIF):
  - mkt_rf
  - TERM = IEF − RF
  - DEF = LQD − IEF, labelled "not duration-matched"
  - EUR/USD from FRED DEXUSEU, falling back to yfinance; daily data adds a 1-day FX lag and reports the summed beta
  - data starts 2002-07-30

**Track record**
- **Input:** CSV or XLSX template with date plus return or NAV, and header fields for currency, gross/net and name. Format is auto-detected.
- **Frequency:** daily or monthly. Weekly is refused for now.
- **Minimum length:** monthly needs at least 36 months and warns below 60. Daily needs at least 504 observations.
- **Privacy:** processed in memory only, never written to disk.
- **Benchmark:** ACWI by default. Reports tracking error, information ratio and up/down capture, on the overlapping period only.
- **Smoothing checks:** Ljung-Box with ρ1–ρ3; a Dimson summed-lag beta with a Wald test; Lo's adjusted Sharpe.

**Portfolio**
- **Tree:** fixed depth, asset class > sub-asset class > ETF, starting from a prefilled template that users can edit. 1–50 holdings.
- **Rebalancing:** back to target at month-end; weights drift between rebalances. An optional cost in bps.
- **Dates:** a common start and end date, naming the holding that limits each.
- **Survivorship:** a warning on every backtest.
- **Analysis:** returns-based only. Each node of the tree shows target weight, drifted weight, Frongello-linked return contribution and risk share.
- **Storage:** CSV import/export plus the browser's localStorage.

**Deferred:**
- HTML export for the new modules
- weekly uploads
- Alternatives proxies
- holdings-based betas
- European mode
- Fung-Hsieh factors
- VaR backtests and conditional (GARCH/EVT) VaR
- EVT return levels, vine copulas and joint tail for uploads
- Labovitz GEV + Gaussian-process method (possible future large-universe feature)

## Epics, RICE and MoSCoW
RICE scale:
- **Reach:** 1–10, the share of target use cases that touch the epic.
- **Impact:** 0.5–3.
- **Confidence:** 0–1.
- **Effort:** build-days.

Score = R × I × C / E.

| # | Epic (hypothesis) | R | I | C | E | RICE | MoSCoW |
|---|---|---|---|---|---|---|---|
| E0 | **Walking skeleton**: a monthly CSV upload gives an FF5 alpha/beta report in the dashboard. It proves the seam, the monthly path, the API and the mode switch. | 8 | 3 | 0.8 | 3 | 6.4 | Must |
| E1 | **FF6 + alpha strip** in all modes. "Alpha vanishes once momentum is added" is the key due-diligence signal. | 10 | 2 | 0.9 | 2 | 9.0 | Must |
| E2 | **Upload hardening**: XLSX, NAV, auto-detection, daily uploads, data-quality refusals and flags, template download. | 8 | 2 | 0.8 | 3 | 4.3 | Must |
| E5 | **Portfolio slice**: tree builder (template) → backtest → factor report. | 7 | 3 | 0.7 | 5 | 2.9 | Must |
| E3 | **Track-record diagnostics**: ACWI statistics, smoothing checks, Lo Sharpe. | 6 | 2 | 0.8 | 3 | 3.2 | Should |
| E6 | **Portfolio attribution tree**: contribution and risk share rolled up per group, plus cost line and data checks. | 7 | 2 | 0.8 | 3 | 3.7 | Should |
| E4 | **Macro sensitivities**: TERM/DEF/EUR-USD in all modes. | 7 | 1 | 0.6 | 3 | 1.4 | Should |
| E7 | **VaR and CVaR** (added 2026-11-19) for single names, track records and portfolios: historical, Gaussian and Cornish-Fisher side by side with bootstrap bands; per-holding CVaR for portfolios. | 10 | 2 | 0.8 | 3 | 5.3 | Should |
| E8 | **Joint tail** (added 2026-11-19), portfolios only: 'crash together' heatmap, co-crash histogram, one t-copula, worst-days table. | 4 | 2 | 0.6 | 4 | 1.2 | Could |
| — | Deferred list above | | | | | | Won't (now) |

E0 is pulled to the top despite its lower RICE score, because it is the enabling thin slice: E2, E3 and E5 all depend on its seam. E5 gets a strategic boost because it is the "heavy" headline feature.

## Roadmap: releases that each work end to end
Each release ends the same way:
1. Features merge to `dev`.
2. The owner validates them on localhost, with screenshots against the current UI.
3. A `dev` → `prod` pull request goes up.

```
NOW   R1  E0 skeleton  ──►  E1 FF6 + alpha strip      (ticker + upload modes)
NEXT  R2  E2 upload hardening ║ E5 portfolio slice ║ E7a VaR/CVaR (ticker + upload)
      R3  E3 diagnostics     ║ E6 attribution tree ║ E7b per-holding CVaR
LATER R4  E4 macro sensitivities (all modes) ║ E8 joint tail (portfolios)
      R5+ European mode / EUR base, Alternatives proxies, weekly, HTML export
```

**E0 skeleton, done when:**
- A golden ticker-report snapshot test exists before any refactor.
- The `ReturnSubject` + `align_returns` seam is in place, with ticker mode byte-identical.
- The French FF5 monthly loader runs, with `periods = 12`.
- `POST /api/report/upload` accepts CSV with date and decimal return, assumes USD, works in memory only, and caps files at 1 MB.
- The sidebar mode switch and a drop zone render the existing report layout, with daily-only sections hidden.

**Dependencies:**
- E0 comes before E2, E3 and E5.
- E1 can start once E0's regression and `periods` change merges.
- E5 comes before E6.
- E4 is independent after E0.
- E7a needs only E0. E7b (per-holding CVaR) needs E5.
- E8 needs E5 and reuses E7b's tail-day machinery.
- The lanes run in parallel only on disjoint file sets:
  - **E2:** `data/upload.py` and the upload UI.
  - **E5:** `analytics/backtest.py` and the portfolio UI.

## Technical design
- **Return subject.** `analytics/subject.py` defines `ReturnSubject`. `build_sample` (sample.py:182) becomes a wrapper over `align_returns`, and `assemble_report` (pipeline.py:748) becomes a wrapper over `assemble_subject_report`. `SectionContext` gains `subject` and `model`. performance.py:120 and world_beta.py:217 switch to `ctx.subject.calendar`.
- **Hook registry.** `section_hooks/registry.py` holds `HookSpec(sources, frequencies, models)`. The Kalman, shrunk, fragility, lead-lag and residual sections are daily and FF5 only. World beta is daily only.
- **Regression.** `run_regression(codes, periods)` keeps its current defaults. The hard-coded `A = 252` in regression.py:38, attribution.py and performance.py becomes a parameter. `ols_hac` is reused unchanged.
- **French data.** A generic loader in `data/french.py` covers FF5 and Mom, daily and monthly. It follows the `parse_portfolio_csv` pattern because the current `parse_french_csv` (factors.py:113) only reads FF5 daily. FRED data goes in `data/fred.py`.
- **Schema.** An optional `subject` block is added, "5" is added to SUPPORTED, and the frontend types are regenerated. `ReportKey` (service.py:167) becomes a dataclass including model and frequency. Uploads bypass every cache; portfolios are cached in memory, keyed by the SHA-256 of the tree.
- **Reuse.**
  - audit A4 (flags returns over 40%) and A6 (`distribution_checks`, with a 1% threshold) for portfolio data checks;
  - `fetch_many` (prices.py:740) and `throttle.py` for portfolio prices;
  - `collinearity()` for macro VIF;
  - the `RangeChips` markup for `ModelToggle`.
- **New dependencies:** `python-multipart` and `openpyxl`.
- **Portfolio tree JSON:** `{version, name, cost_bps, root: group > asset_class > sub_asset_class > holding|cash}`. Weights live only on leaves; groups are computed.

**My calls (flag if wrong):**
- Unallocated weight goes to the Cash row on Run, with a notice.
- The same ETF is allowed in two sleeves.
- FF6 gets a new sixth hue token.
- UI review happens on localhost screenshots at each release demo, instead of separate mockups (cheaper).

## E7: VaR and CVaR (decided 2026-11-19)

Research: [research notes, section D](../research/next-stage-research.md).

- **Methods:** historical, Gaussian and Cornish-Fisher (modified) are shown side by side, because the gap between them is a fat-tail signal.
  - Cornish-Fisher shows "n/a" outside the expansion's valid domain (Maillard 2012). Take the exact bound from the paper before coding it.
  - The Cornish-Fisher CVaR is floored at its VaR.
- **Levels:**
  - The headline in every mode is Basel-style 99% VaR and 97.5% CVaR.
  - Monthly series also get a 95% VaR/CVaR row.
  - Results stay at the series' own frequency (1-day or 1-month), with no square-root-of-time scaling.
  - Losses are positive percentages of value, computed from simple returns.
- **Uncertainty:**
  - Each figure shows a bootstrap 90% band and the number of tail observations behind it.
  - Daily series use a stationary block bootstrap (Politis-Romano 1994); monthly series use an iid bootstrap.
  - A historical figure with fewer than about 3 expected tail observations shows "n/a" and the reason, e.g. "0.6 expected tail months".
- **Portfolios (E7b):** historical per-holding CVaR is the mean of w_i·r_i over the portfolio's tail days.
  - It sums exactly to the portfolio CVaR and rolls up through the SAA tree.
  - Below about 20 tail observations it falls back to Gaussian per-holding CVaR from the covariance matrix, and the report says so.
- **Deferred:** Student-t, GARCH/filtered historical, EVT, rolling out-of-sample backtests (Kupiec, Christoffersen, Acerbi-Székely), kernel per-holding VaR, modified per-holding CVaR, and the corrected Cornish-Fisher expansion.
- **Verification:**
  - Gaussian VaR equals mean − z·σ.
  - Cornish-Fisher reduces to Gaussian when skewness and excess kurtosis are 0.
  - Historical VaR and CVaR match hand-computed order statistics.
  - Per-holding CVaR sums to the portfolio CVaR within 1e-12.
  - On simulated normal data, bootstrap-band coverage is about nominal.

## E8: Joint tail behaviour of portfolios (decided 2026-11-19)

Research: [research notes, section E](../research/next-stage-research.md) and the [Labovitz (2009) summary](../research/labovitz-2009-summary.md). This applies to portfolios only.

- **"Crash together" heatmap.** For each pair of holdings, χ(5%) = P(B in its worst 5% | A in its worst 5%), on daily data and ordered by the SAA tree. Each cell is shown against the Gaussian-copula expectation at the same rank correlations.
- **Co-crash histogram.** On the portfolio's worst 5% of days, how many holdings were also in their own worst 5%, with an independence baseline.
- **One Student-t copula.**
  - Correlation from Kendall's τ, ρ = sin(πτ/2).
  - Profile likelihood for ν on rank pseudo-observations, using scipy only.
  - ν is shown as "joint crash odds versus normal".
- **Worst-days table.** Each holding's mean return on the portfolio's worst 5% of days and on the benchmark's worst 5% of days.
  - This reuses the E7b tail-day machinery.
  - Down-market correlation carries the Forbes-Rigobon caveat.
- **Data and display rules.**
  - Daily data is primary; weekly is a robustness toggle.
  - Stationary block-bootstrap 90% bands. Cells whose band includes the Gaussian value are greyed out.
  - Needs at least about 1,000 common daily observations; below that, the section shows counts only.
- **Not in this epic:**
  - EVT (GPD/GEV return levels)
  - vine, grouped-t, Clayton and Gumbel copulas
  - max-stable models
  - CoVaR
  - λ_L reported as a number
  - joint tail for uploaded track records
  - The Labovitz GEV + Gaussian-process method is parked for a possible future large-universe (stock screener) feature.
- **Verification.**
  - χ on simulated Gaussian data matches the Gaussian-copula expectation.
  - The t-copula fit recovers ν and ρ on simulated t data.
  - The co-crash histogram matches hand counts.
  - Bootstrap coverage is checked on simulated data.

## Draft default proxy template (to be validated in E5)

US-listed proxies with long histories. Each sub-asset class starts at 0%, and users can add, rename, delete or swap rows.

| Asset class | Sub-asset class: proxy ETF |
|---|---|
| Cash | USD T-bill (French RF) |
| Bonds | Global: BWX · Europe: IGOV (mixed proxy) · USA: AGG · USA Treasury: IEF · USA Corporate: LQD · High Yield: HYG · Emerging: EMB |
| Equities | Europe: IEV / EZU · USA: IVV · APAC: EPP + EWJ · Emerging: EEM · Thematic: QQQ · Global: ACWI |
| Commodities | Gold: GLD · Diversified: DBC |
| Alternatives | hidden in v1 (proxies to be researched) |

Bonds Europe uses IGOV (a mixed proxy with about 41% in euro-area government bonds; no pure US-listed option exists). The common start date is set by the latest-starting holding: IGOV (2009-01-30), ACWI (2008-03-28), EMB (2007-12-19) or BWX (2007-10-11). The UI names it. Dates are in the [research notes, V2](../research/next-stage-research.md).

## Verification
- **Every PR:**
  - the golden ticker snapshot is unchanged;
  - pytest, frontend type-check and lint pass;
  - CI passes.
- **Statistics:**
  - `ols_hac` matches statsmodels HAC;
  - Mom matches the published rows;
  - compounded daily Mkt+RF matches monthly within 5 bp;
  - SPY monthly β matches daily β within 0.1;
  - SPY uploaded as a NAV reproduces the ticker-mode betas;
  - capture, Lo η and Ljung-Box match hand-worked or statsmodels values;
  - Frongello contributions sum to Π(1 + r_p) − 1 within 1e-12;
  - risk shares sum to 1;
  - a single-holding portfolio at 100% equals the ticker;
  - group totals equal the sum of their leaves.
- **Privacy:** after an upload, the `data_dir` file listing and the reports cache are unchanged.
- **Release demo:** run the localhost dev server; SPY with FF5/FF6; a monthly upload; a 60/40 template portfolio; screenshots for style parity.
