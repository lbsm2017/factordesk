# factordesk roadmap

Last updated 2026-11-18. Now / Next / Later format. A roadmap is a plan, not a promise: items move
when evidence changes. Every statistical item follows `docs/research-protocol.md` (hypothesis and
test written down first, logged, independently reviewed) before it ships.

## Status overview (2026-11-18)

- **Done:** the SPY thin slice (factor download, prices, date matching, HAC regression, rolling
  betas, return and risk attribution, offline HTML report), independently validated
  (`docs/validation/spy-slice-validation.md`, verdict "ship with changes").
- **Built, in review:** the dashboard (local FastAPI server and React page, one-command start,
  fake-backend browser test and CI). Not yet run against live Yahoo data.
- **In progress:** a data-source comparison of Yahoo, Tiingo and Alpaca; the schema v3
  contract (owner rank 4). Built and waiting for review: the rolling-regression speed-up
  conditions (owner rank 2) and the one-shot install and run command (owner rank 7, no
  publishing). Hardening from the validation findings is done as of 2026-11-18:
  `docs/validation/spy-hardening-closure-2026-11-18.md`.
- **Specified, not built:** report redesign (`docs/design/report-design.md`), residual alpha
  analysis (`docs/methodology-residual-analysis.md`), regional datasets
  (`docs/methodology-datasets.md`).
- **Owner ranking (2026-11-18):** 16 epics are ranked in the priority ranking below. Items 1 to 4
  are Now, items 5, 7, 8, 12 and 14 are Next, items 6, 9, 10, 11 and 15 are Later, and items 13 and
  16 are Very later. Fragility score and lead-lag betas have specs ready.

## Priority ranking (owner, 2026-11-18)

Sorted by RICE, highest first. Owner decision and status are the owner's words.

| Rank | Epic | Reach (1-10) | Impact (0.25-3) | Confidence | Effort (agent sessions, about 30 min each) | RICE | MoSCoW | Owner decision | Status |
|---|---|---|---|---|---|---|---|---|---|
| 1 | Ship the dashboard: push, PR, merge to dev | 10 | 3 | 1.0 | 1 | 30 | Must | ok | Waiting for the rolling-validation conditions, then push and PR |
| 2 | Rolling regression speed-up conditions | 10 | 1 | 0.9 | 1 | 9 | Must | ok | In progress |
| 3 | SPY hardening: diagnostics, quality gate, bad input | 10 | 3 | 0.8 | 5 | 4.8 | Must | deliver and close | In progress (closure agent) |
| 4 | Schema v3 contract | 8 | 2 | 0.8 | 3 | 4.3 | Must | deliver and close | In progress |
| 5 | First GitHub CI run | 5 | 2 | 0.8 | 2 | 4.0 | Should | next | Starts with the pull request |
| 6 | Fragility score | 6 | 2 | 0.7 | 5 | 1.7 | Should | later | Spec ready |
| 7 | One-shot install and run | 8 | 1 | 0.7 | 5 | 1.1 | Should | next | In progress (no publishing) |
| 8 | Residual alpha analysis | 6 | 2 | 0.7 | 8 | 1.1 | Should | next | Starts after schema v3 |
| 9 | Lead-lag betas | 4 | 2 | 0.6 | 8 | 0.6 | Could | later | Spec ready |
| 10 | Dead-code cleanup | 2 | 0.25 | 1.0 | 1 | 0.5 | Could | later | Deferred |
| 11 | Data triangulation | 7 | 2 | 0.5 | 20 | 0.35 | Could | later | Needs the source comparison |
| 12 | Shrunk betas | 3 | 1 | 0.5 | 5 | 0.3 | Could | next | Starts after schema v3 |
| 13 | Peers using the batch price fetch | 4 | 1 | 0.6 | 8 | 0.3 | Could | very later | Deferred |
| 14 | Kalman betas | 4 | 1 | 0.5 | 8 | 0.25 | Could | next, before later items | Starts after schema v3 |
| 15 | European mode | 3 | 2 | 0.5 | 20 | 0.15 | Won't (this round) | later | Needs owner decisions |
| 16 | Alpaca adapter | 2 | 1 | 0.5 | 8 | 0.13 | Won't (this round) | very later | Deferred |

The RICE values are the chief of staff's estimates, not measured results. RICE is Reach x Impact x
Confidence / Effort. Effort counts agent sessions of about 30 minutes each.

## Now

Items 1 to 4 of the priority ranking.

| Item | Why it matters | Status | Depends on |
|---|---|---|---|
| Dashboard (FastAPI + React) (rank 1) | Search bar, range chips (3Y, 5Y, Full history) and custom dates, factor refresh; the report as an app. Runbook: `docs/dashboard.md`; spec: `docs/specs/dashboard.md` | Built, in review: tickets T1 to T10 done as of commit f36255e on `feat/report-ui-feedback`, not merged to `dev`. Left: a smoke test on live Yahoo data, fixes from the T11 design and accessibility review, peer comparison using the batch price fetch | Review; merge of `feat/report-ui-feedback` into `dev` |
| Rolling regression speed-up conditions (rank 2) | Conditions the rolling-regression speed-up must meet before it ships | Built: all three conditions met on 2026-11-18 (`docs/reviews/rolling-speedup-validation-2026-11-18.md`) | — |
| Hardening of the SPY slice (rank 3) | Numbers must never mislead: diagnostics, quality gate, clean errors | Done 2026-11-18: every critical and major validation finding fixed; minor and calibration items deferred with reasons in `docs/validation/spy-hardening-closure-2026-11-18.md` | — |
| Schema v3 contract (rank 4) | One shared report schema, so parallel branches do not collide (see Risks) | In progress | — |

## Next

Items 5, 7, 8, 12 and 14 of the priority ranking, in owner order.

| Item | Why it matters | Status | Depends on |
|---|---|---|---|
| First GitHub CI run (rank 5) | Runs the checks on GitHub for every pull request | Starts with the pull request | The first pull request |
| One-shot install-and-run command (rank 7) | A single line per OS that installs uv if missing and opens a report (`uvx factordesk report SPY --open`); a short bootstrap script pinned to a release tag, readable, with a published checksum | In progress (no publishing) | Publish to PyPI; first tagged release |
| Residual alpha analysis (rank 8) | Shows how much alpha holds up with point-in-time betas | Starts after schema v3 (earlier: Not Started) | Schema v3 contract |
| Shrunk betas (rank 12) | Pull noisy style betas toward a prior; report how much data would make an effect detectable | Starts after schema v3 (earlier: Spec in progress) | — |
| Kalman-filter betas (rank 14) | Time-varying betas with proper uncertainty, using past data only | Starts after schema v3 (earlier: Spec in progress); before the Later items | — |

## Later

Items 6, 9, 10, 11 and 15 of the priority ranking, in owner order.

| Item | Why it matters | Status | Depends on |
|---|---|---|---|
| Fragility score (rank 6) | "This alpha rests on N days": how many days must go before significance flips; leave-one-year-out | Spec ready (earlier: Spec in progress) | — |
| Lead-lag (Dimson / Scholes-Williams) betas (rank 9) | Fixes non-synchronous closes (old Yahoo SPY data, future European and Asian tickers); switched on by the quality gate | Spec ready (earlier: Spec in progress) | Quality gate (hardening) |
| Dead-code cleanup (rank 10) | Removes unused code | Deferred | — |
| Data-quality plan (triangulation) (rank 11) | A written plan for multi-source consensus returns and per-day agreement scores | Needs the source comparison | Data-source comparison |
| European mode (rank 15) | Regional French factors, USD conversion, currency regressor | Needs owner decisions | Dataset docs; owner decisions D16 (RF source, ECB FX, regressor default, Canada) |

## Very later

Items 13 and 16 of the priority ranking.

| Item | Why it matters | Status | Depends on |
|---|---|---|---|
| Peer comparison (rank 13) | Where a stock's betas sit within its sector | Deferred | — |
| Alpaca adapter (rank 16) | Optional cross-check and fallback from 2016, returns rebuilt from raw closes and dividends (`sip` feed); check Alpaca's "user application" notice before shipping | Deferred | Data-quality plan |

## Not in the owner ranking

Items below had earlier rows but do not appear in the 2026-11-18 owner ranking. They are kept
unchanged until the owner ranks them.

| Item | Why it matters | Status | Depends on |
|---|---|---|---|
| First commit, `prod` and `dev` branches | Everything after this goes through pull requests | Not Started | Hardening; folder rename to `factordesk` |
| Report redesign integration | The validated numbers in the approved look | Not Started | First commit; schema v3 contract |
| Config key names | Code reads the `.env` names actually used (`ALPACA_KEY`, `ALPACA_SECRET`, `TIINGO_KEY`); Alpaca feed `sip` | Not Started | First commit |
| Total returns from Close + Dividends | factordesk computes total return itself (CRSP convention) for every source; vendor Adj Close becomes a reported cross-check (owner decision 2026-11-18) | Not Started | Schema v3 contract; methodology update |
| Placebo calibration, with a `factordesk calibrate` CLI command (multi-core) | Publishes how often each report flag is wrong on stocks with no true alpha | Not ranked | Now items it calibrates (gate, fragility, alerts) |
| Block-bootstrap intervals | Standard errors for risk shares and return contributions; cross-check of HAC | Not ranked | — |
| Specification curve | Share of reasonable specifications (windows, start dates, sources) that agree on alpha | Not ranked | Data triangulation |
| Data triangulation build | Consensus returns from Yahoo, Tiingo and Alpaca; flagged disagreement days | Not ranked | Data-quality plan |

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
- Moved the dashboard from Next to Now: built and in review (see its row for what is left).
- Added the owner priority ranking (16 epics, RICE values as the chief of staff's estimates).
- Re-sorted Now, Next and Later to the owner order, and added a Very later section (peer comparison,
  Alpaca adapter). Added rows for ranked items with no earlier row: rolling-regression speed-up
  conditions, schema v3 contract, first GitHub CI run, dead-code cleanup.
- Moved unranked rows (first commit, report redesign, config key names, total returns, placebo
  calibration, block bootstrap, specification curve, data triangulation build) to Not in the owner
  ranking, with their text unchanged.
