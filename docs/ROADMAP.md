# factordesk roadmap

Last updated 2026-11-18. Now / Next / Later format. A roadmap is a plan, not a promise: items move
when evidence changes. Every statistical item follows `docs/research-protocol.md` (hypothesis and
test written down first, logged, independently reviewed) before it ships.

## Status overview (2026-11-18)

- **Done:** the SPY thin slice (factor download, prices, date matching, HAC regression, rolling
  betas, return and risk attribution, offline HTML report), independently validated
  (`docs/validation/spy-slice-validation.md`, verdict "ship with changes").
- **In progress:** hardening from the validation findings (residual diagnostics, quality gate,
  bad-input handling); a data-source comparison of Yahoo, Tiingo and Alpaca.
- **Specified, not built:** report redesign (`docs/design/report-design.md`), residual alpha
  analysis (`docs/methodology-residual-analysis.md`), regional datasets
  (`docs/methodology-datasets.md`).

## Now

| Item | Why it matters | Status | Depends on |
|---|---|---|---|
| Hardening of the SPY slice | Numbers must never mislead: diagnostics, quality gate, clean errors | On Track | — |
| First commit, `prod` and `dev` branches | Everything after this goes through pull requests | Not Started | Hardening; folder rename to `factordesk` |
| Report redesign integration | The validated numbers in the approved look | Not Started | First commit; schema v3 contract |
| Residual alpha analysis | Shows how much alpha holds up with point-in-time betas | Not Started | Schema v3 contract |
| Lead-lag (Dimson / Scholes-Williams) betas | Fixes non-synchronous closes (old Yahoo SPY data, future European and Asian tickers); switched on by the quality gate | Spec in progress | Quality gate (hardening) |
| Fragility score | "This alpha rests on N days": how many days must go before significance flips; leave-one-year-out | Spec in progress | — |
| Kalman-filter betas | Time-varying betas with proper uncertainty, using past data only | Spec in progress | — |
| Shrunk betas | Pull noisy style betas toward a prior; report how much data would make an effect detectable | Spec in progress | — |
| Data-quality plan (triangulation) | A written plan for multi-source consensus returns and per-day agreement scores | Waits for the source comparison | Data-source comparison |
| Config key names | Code reads the `.env` names actually used (`ALPACA_KEY`, `ALPACA_SECRET`, `TIINGO_KEY`); Alpaca feed `sip` | Not Started | First commit |
| Total returns from Close + Dividends | factordesk computes total return itself (CRSP convention) for every source; vendor Adj Close becomes a reported cross-check (owner decision 2026-11-18) | Not Started | Schema v3 contract; methodology update |

## Next

| Item | Why it matters | Depends on |
|---|---|---|
| Placebo calibration, with a `factordesk calibrate` CLI command (multi-core) | Publishes how often each report flag is wrong on stocks with no true alpha | Now items it calibrates (gate, fragility, alerts) |
| Block-bootstrap intervals | Standard errors for risk shares and return contributions; cross-check of HAC | — |
| Specification curve | Share of reasonable specifications (windows, start dates, sources) that agree on alpha | Data triangulation |
| Data triangulation build | Consensus returns from Yahoo, Tiingo and Alpaca; flagged disagreement days | Data-quality plan |
| European mode | Regional French factors, USD conversion, currency regressor | Dataset docs; owner decisions D16 (RF source, ECB FX, regressor default, Canada) |
| Peer comparison | Where a stock's betas sit within its sector | — |
| Dashboard (FastAPI + React) | Search bar, "Factor it", range chips and custom dates, refresh; the report as an app (controls specified in `docs/design/report-design.md` section I) | Report redesign (specified; renderer port pending) |
| Alpaca adapter | Optional cross-check and fallback from 2016, returns rebuilt from raw closes and dividends (`sip` feed); check Alpaca's "user application" notice before shipping | Data-quality plan |
| One-shot install-and-run command | A single line per OS that installs uv if missing and opens a report (`uvx factordesk report SPY --open`); a short bootstrap script pinned to a release tag, readable, with a published checksum | Publish to PyPI; first tagged release |

## Later

Tiingo adapter for users with a paid licence that allows this use (the free plan forbids storing
data, validating other datasets and charting prices). Factor-mimicking hedge, model comparison (CAPM / FF3 / FF5 / FF5+momentum), portfolio mode,
screener, out-of-sample stability score, other regions after Europe, cointegration, drift alerts
and regime betas (specified in `docs/methodology.md`, not yet scheduled).

## Risks and dependencies

- **Schema conflicts between parallel branches.** Five features add report fields at once. A
  schema v3 contract (all new sections as optional sub-models, one renderer module per panel) lands
  on `dev` first so branches do not collide.
- **The folder rename blocks the first commit.** The project folder can only be renamed while no
  editor or session has it open.
- **Pull requests need a remote.** Branches can be reviewed locally until a GitHub repository
  exists.
- **Data licences.** Tiingo's free plan is "internal use only"; Yahoo is personal use. Real-data
  sample reports stay out of the public repository (owner decision 2026-11-18).

## Changes in this update (2026-11-18)

- Added to Now: lead-lag betas, fragility score, Kalman betas, shrunk betas, data-quality plan.
- Added to Next: placebo calibration CLI (multi-core), block bootstrap, specification curve.
- Moved factor-mimicking hedge and model comparison to Later (owner triage earlier the same day).
