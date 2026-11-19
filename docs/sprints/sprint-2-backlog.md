# Sprint 2 backlog (not yet planned)

Status: open backlog as of 2026-11-19. Sprint 2 planning picks from this list. Scope is frozen once the sprint starts, and new requests go to the next backlog.
Previous sprint: [Sprint 1](sprint-1.md). Spec: [next-stage spec](../specs/next-stage-track-record-and-portfolio.md).

## 1. Hygiene (small, do first)

- **Server log verbosity.** One line per step with timing:
  - report start;
  - price download (cached or not) and factor load (vintage);
  - sections built, with each section over 1 s named;
  - total time, and cache hits.
  - Uploads log only the row count and the frequency, never contents.
- **Stale-build warning.** `factordesk serve` warns when `frontend/dist` is older than the frontend source.
- **Test stability.** Set Vitest `maxWorkers` in the config. Add a coding-standards note: compare floats with a tolerance.
- **Bundle size.** Enforce the budget in CI or set a realistic budget. Today it is about 410 kB raw against a 400 kB limit.
- **Leftover review minors:**
  - Compare the French data stamps of FF5 and Mom.
  - FF6 range coverage uses the FF5 frame.
  - Upload error messages: cap the echoed cell at about 40 characters, use the CSV line number, and send 400 rather than 422 for a missing file.
  - Extra upload tests: spool-size assert, log check, YYYY-MM unit test, frontend 413 test.
  - The verdict text still lacks the lean floor.

## 2. Roadmap epics

| Epic | Scope | Depends on |
|---|---|---|
| E5 wiring | SAA tree builder screen, modelled on Venn/Risk Pro: asset class > sub-asset class > proxy ETF, with a prefilled template. Portfolio API, backtest report and per-holding table. | E5 core (done) |
| E2 | Upload hardening: XLSX, NAV input, auto-detection, daily uploads, quality flags, template download | E0 (done) |
| E3 | Track-record diagnostics: ACWI statistics, Ljung-Box, Dimson beta, Lo Sharpe, MinTRL (E9c) | E2 |
| E6 | Portfolio attribution tree: contribution and risk share rolled up by group | E5 wiring |
| E4 | Macro section: market, TERM, DEF, COMM, INFL and the Fed broad dollar index | E0 (done) |
| E7b | Per-holding CVaR | E5 wiring, E6 |
| E9b | Specification curve | E1 (done) |
| E8 | Joint tail: crash-together heatmap, co-crash histogram, t-copula | E5 wiring, E7b |

## 3. Tail risk v2

- **Cornish-Fisher overshoot on fat-tailed daily data.** Example: CVaR 10.2% against 5.0% historical, with no warning. Options: the corrected Cornish-Fisher method (Amédée-Manesme, Barthélémy & Maillard 2019), or a flag when the result is far from the historical figure.
- **"Based on N days".** Use exactly the analysed window, or state that the count includes the days after the factor data end.
- **Compact layout.** One line per cell, labels as badges, the band as a whisker. Show the reason under an "indicative" flag.
- **Horizon toggle: daily, monthly, quarterly.**
  - Use non-overlapping compounded returns at each horizon, with no square-root-of-time scaling.
  - Hide the daily option for monthly records.
  - Quarterly has few tail observations.
- **Band coverage.** The "validated" label was only checked on iid data. Check it on volatility-clustered data, or relabel it.

## 4. Factor model: lessons from MSCI Barra

Research: [research notes, section H](../research/next-stage-research.md).

Selected by the owner for the backlog:

- **Factor families view.** Group the sensitivities into Value (HML), Size (SMB), Momentum (Mom) and Quality (RMW + CMA), each with an icon and a colour.
  - Label them "factor sensitivities", not exposures.
  - Do not use the MSCI marks "FaCS" or "Factor Box".
- **Crowding-lite (US)**, labelled partial (3 of MSCI's 5 components). It replaces the planned "crowding / stretch proxy" in `docs/PLAN.md`. The components:
  - value spread from the French BE/ME portfolio files;
  - factor-volatility z-score;
  - factor-reversal z-score.
- **Low-vol family and monthly spreads.** Built from the French monthly sorts (beta, variance, residual variance, E/P, CF/P, accruals, D/P). This needs its own design round, because it mixes frequencies, adds collinear factors, and the causal-discipline rule applies.

Not selected: the active-sensitivity bars against a benchmark.

## 5. Later

- **Settings module.** It will hold the FF5/FF6 choice and other preferences. Until it exists, the FF5-only sections are reachable only with a `model=ff5` URL. The alternative is to extend those sections to six factors.
- European mode and a EUR base currency. Alternatives proxies. Weekly uploads. HTML export for the new modules.
- Strategy-gated factors for uploads: short-term reversal, TSMOM, Fung-Hsieh. VIX. q5 as an alternative model. QMJ and BAB once the AQR terms allow it.
- Regressor-overlap warning. FF5/FF6 drift check. Placebo test. Omitted-variable alpha check.
- The Labovitz GEV + Gaussian-process method, for a future large-universe feature.
- Dark-theme check in screenshots.
