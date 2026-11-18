# factordesk roadmap

Last updated 2026-11-18 (update 2). Now / Next / Later format. A roadmap is a plan, not a promise: items move
when evidence changes. Every statistical item follows `docs/research-protocol.md` (hypothesis and
test written down first, logged, independently reviewed) before it ships.

## Status overview (2026-11-18)

- **Done:** the SPY thin slice (factor download, prices, date matching, HAC regression, rolling
  betas, return and risk attribution, offline HTML report), independently validated
  (`docs/validation/spy-slice-validation.md`, verdict "ship with changes").
- **Done 2026-11-18:** the rolling-regression speed-up conditions (rank 2), the SPY hardening
  (rank 3) and the schema contract (rank 4). Evidence is in the "Done 2026-11-18" list below.
- **In review:** the dashboard (local FastAPI server and React page, one-command start,
  fake-backend browser test and CI). PR #1 is open and CI is green on four jobs (run 44350980579).
  It waits for the owner to review and merge. Not yet run against live Yahoo data beyond one ticker.
- **Built, not released:** the one-shot install and run command (rank 7), in PR #1. The release
  is the owner's step, following `docs/release-checklist.md`.
- **In progress:** follow-ups to the first GitHub CI run (rank 5); residual alpha, shrunk betas and
  Kalman betas (ranks 8, 12 and 14), at the analytics step; a data-source comparison of Yahoo,
  Tiingo and Alpaca (blocks rank 11).
- **Specified, not built:** report redesign (`docs/design/report-design.md`), regional datasets
  (`docs/methodology-datasets.md`).
- **Owner ranking (2026-11-18, re-scored in update 2):** 16 epics are ranked in the priority ranking
  below. Item 1 is Now, items 2 to 4 are Done, items 5, 8, 12 and 14 are Next, items 6, 9, 10,
  11 and 15 are Later, and items 7, 13 and 16 are Very later. Fragility score and lead-lag betas have
  specs ready. One new proposal (a nightly workflow) is listed under the table and is not ranked.

## Priority ranking (owner, 2026-11-18)

Sorted by RICE, highest first. Owner decision and progress are the owner's words where the owner
gave them.

| Rank | Epic | Reach (1-10) | Impact (0.25-3) | Confidence | Effort (agent sessions, about 30 min each) | RICE | MoSCoW | Owner decision | Progress | Depends on |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | Ship the dashboard: push, PR, merge to dev | 10 | 3 | 1.0 | 1 | 30 | Must | ok | In review: PR #1 open, CI green on 4 jobs (run 44350980579), waiting for the owner to review and merge | CI green (done) |
| 2 | Rolling regression speed-up conditions | - | - | - | - | - | Must | ok | Done: 3 conditions met, merged in PR #1; independent validation accepted | none |
| 3 | SPY hardening: diagnostics, quality gate, bad input | - | - | - | - | - | Must | deliver and close | Done: 29 findings, 20 fixed before, 4 fixed now, 5 deferred (closure doc); F13 non-USD warn-or-refuse and gate thresholds (G2) need owner decisions | none |
| 4 | Schema contract (ships as schema version 4) | - | - | - | - | - | Must | deliver and close | Done: five optional sections, panel registries on both renderers, four briefs; in PR #1 | none |
| 5 | First GitHub CI run | - | - | - | - | - | Should | next | Done: run 1 failed on one float comparison in a fixture, fixed; run 2 green (3 min 30 s). Open: Playwright cache hit path needs a third run; nightly slow tests need an owner decision | PR #1 |
| 6 | Fragility score | 6 | 2 | 0.8 | 5 | 1.9 | Should | later | Not started; spec ready; the hardening deferral D-1 (influence diagnostic) folds in here | Schema contract (done): unblocked |
| 7 | One-shot install and run | 8 | 1 | 0.7 | 5 | 1.1 | Should | very later (was next) | Built, in PR #1; not released: the owner runs `docs/release-checklist.md`; installer URL and a real install on a machine without uv unverified | PyPI release (owner) |
| 8 | Residual alpha analysis | 6 | 2 | 0.8 | 8 | 1.2 | Should | next | In progress: analytics step (agent resumed after a network error); then pipeline, static panel, React panel, independent validation | Schema contract (done) |
| 9 | Lead-lag betas | 4 | 2 | 0.7 | 8 | 0.7 | Could | later | Not started; spec ready | Schema contract (done); hardening gate (done); gate threshold calibration (owner) |
| 10 | Dead-code cleanup | 2 | 0.25 | 1.0 | 1 | 0.5 | Could | later | Not started | none |
| 11 | Data triangulation | 7 | 2 | 0.5 | 20 | 0.35 | Could | later | Not started | Data-source comparison (in progress) |
| 12 | Shrunk betas | 3 | 1 | 0.6 | 5 | 0.4 | Could | next | In progress: analytics step; then pipeline, panels, validation | Schema contract (done) |
| 13 | Peers using the batch price fetch | 4 | 1 | 0.6 | 8 | 0.3 | Could | very later | Not started; the batch fetch exists but nothing calls it | Cointegration (not built) |
| 14 | Kalman betas | 4 | 1 | 0.6 | 8 | 0.3 | Could | next, before later items | In progress: analytics step; runtime budget a couple of seconds | Schema contract (done) |
| 15 | European mode | 3 | 2 | 0.5 | 20 | 0.15 | Won't (this round) | later | Not started; D16 covers RF source, ECB FX, regressor default, Canada | Owner decisions D16 and F13 |
| 16 | Alpaca adapter | 2 | 1 | 0.5 | 8 | 0.13 | Won't (this round) | very later | Not started | none |

The RICE values are the chief of staff's estimates, not measured results. RICE is Reach x Impact x
Confidence / Effort. Effort counts agent sessions of about 30 minutes each. The values were re-scored
on 2026-11-18 because the schema contract landed: confidence was raised on ranks 6, 8, 9, 12 and 14.
Ranks 2 to 5 show a dash because they are done.

New, not ranked: a nightly workflow for the 202 slow tests
(about 1.5 min on ubuntu), plus an allowed-to-fail job for the 3 live tests. Reach 5, impact 1,
confidence 0.8, effort 1, RICE 4.0, MoSCoW Could. Status: approved by the owner on 2026-11-18;
workflow written in a pull request stacked on PR #1, not yet run on GitHub.

## Now

Item 1 of the priority ranking.

| Item | Why it matters | Status | Depends on |
|---|---|---|---|
| Dashboard (FastAPI + React) (rank 1) | Search bar, range chips (3Y, 5Y, Full history) and custom dates, factor refresh; the report as an app. Runbook: `docs/dashboard.md`; spec: `docs/specs/dashboard.md` | In review: PR #1 open, CI green on 4 jobs (run 44350980579), waiting for the owner to review and merge. Tickets T1 to T10 done as of commit f36255e on `feat/report-ui-feedback`. Left: a smoke test on live Yahoo data, fixes from the T11 design and accessibility review, peer comparison using the batch price fetch | Owner review and merge of PR #1 into `dev` |

## Done 2026-11-18

| Item | What it delivered | Evidence |
|---|---|---|
| Rolling regression speed-up conditions (rank 2) | All three conditions met; merged in PR #1; independent validation accepted | `docs/reviews/rolling-speedup-validation-2026-11-18.md` |
| Hardening of the SPY slice (rank 3) | 29 findings: 20 fixed before, 4 fixed now, 5 deferred with reasons. Owner decisions still open: F13 non-USD tickers (warn or refuse) and gate thresholds (G2) | `docs/validation/spy-hardening-closure-2026-11-18.md` |
| Schema contract (rank 4, ships as schema version 4) | Five optional sections, panel registries on both renderers, four briefs; in PR #1. The contract keeps its v3 name | `wiki/decision-schema-v3-contract.md`, `docs/specs/schema-v3-contract.md` |

## Next

Items 5, 8, 12 and 14 of the priority ranking, in owner order.

| Item | Why it matters | Status | Depends on |
|---|---|---|---|
| First GitHub CI run (rank 5) | Runs the checks on GitHub for every pull request | Done: run 1 failed on one float comparison in a fixture, fixed; run 2 green (3 min 30 s). Open: Playwright cache hit path needs a third run; nightly slow tests need an owner decision | PR #1 |
| Residual alpha analysis (rank 8) | Shows how much alpha holds up with point-in-time betas | In progress: analytics step (agent resumed after a network error); then pipeline, static panel, React panel, independent validation | Schema contract (done) |
| Shrunk betas (rank 12) | Pull noisy style betas toward a prior; report how much data would make an effect detectable | In progress: analytics step; then pipeline, panels, validation | Schema contract (done) |
| Kalman-filter betas (rank 14) | Time-varying betas with proper uncertainty, using past data only | In progress: analytics step; runtime budget a couple of seconds; goes before the Later items | Schema contract (done) |

## Later

Items 6, 9, 10, 11 and 15 of the priority ranking, in owner order.

| Item | Why it matters | Status | Depends on |
|---|---|---|---|
| Fragility score (rank 6) | "This alpha rests on N days": how many days must go before significance flips; leave-one-year-out | Not started; spec ready; the hardening deferral D-1 (influence diagnostic) folds in here | Schema contract (done): unblocked |
| Lead-lag (Dimson / Scholes-Williams) betas (rank 9) | Fixes non-synchronous closes (old Yahoo SPY data, future European and Asian tickers); switched on by the quality gate | Not started; spec ready | Schema contract (done); hardening gate (done); gate threshold calibration (owner) |
| Dead-code cleanup (rank 10) | Removes unused code | Not started | — |
| Data-quality plan (triangulation) (rank 11) | A written plan for multi-source consensus returns and per-day agreement scores | Not started | Data-source comparison (in progress) |
| European mode (rank 15) | Regional French factors, USD conversion, currency regressor | Not started; D16 covers RF source, ECB FX, regressor default, Canada | Owner decisions D16 and F13 |

## Very later

Items 7, 13 and 16 of the priority ranking.

| Item | Why it matters | Status | Depends on |
|---|---|---|---|
| One-shot install-and-run command (rank 7) | A single line per OS that installs uv if missing and opens a report (`uvx factordesk report SPY --open`); a short bootstrap script pinned to a release tag, readable, with a published checksum | Built, in PR #1; not released (no publishing) | PyPI release (owner); first tagged release |
| Peer comparison (rank 13) | Where a stock's betas sit within its sector | Not started; the batch fetch exists but nothing calls it | Cointegration (not built) |
| Alpaca adapter (rank 16) | Optional cross-check and fallback from 2016, returns rebuilt from raw closes and dividends (`sip` feed); check Alpaca's "user application" notice before shipping | Not started | — |

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

## Risks and blockers (2026-11-18)

- **Feature agents resumed, no commits yet.** The three feature agents (residual alpha, shrunk
  betas, Kalman betas) hit a network error and were resumed. None has commits yet.
- **PR #1 awaits the owner.** The dashboard, the one-shot install and the schema contract all sit
  in PR #1 until the owner reviews and merges it.
- **Release not executed.** The one-shot install is built but not released. The release is the
  owner's step in `docs/release-checklist.md`.
- **Schema version is 4, not 3.** The contract keeps its v3 name in file names and wiki pages, but
  the shipped schema is version 4.
- **Live Yahoo throttling untested beyond one ticker.** A real run on one ticker is the only live
  evidence. Throttling under a full batch is not tested.
- **Owner decisions open.** F13 (non-USD tickers: warn or refuse) and G2 (gate thresholds) need
  owner decisions before the affected items can close.
- **Shared methodology file.** Four feature branches may all want to edit `docs/methodology.md`.
  They add proposals only. Folding those proposals into the methodology is the owner's call.

## Changes in update 1 (2026-11-18)

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

## Changes in this update (update 2)

What moved, and why:

- Owner moved rank 7 (one-shot install and run) from Next to very later on 2026-11-18. The work is built and stays in PR #1; only the release is deferred.
- New information: PR #1 is open with CI green on four jobs (run 44350980579). The schema contract
  landed (as schema version 4), the SPY hardening closed, the rolling speed-up conditions were met,
  and the three feature agents started.
- Rank 1 moved from "waiting to push and PR" to "in review". Rank 2, 3 and 4 moved to the Done list.
  Rank 5 stays in Next with its open follow-ups. Rank 7 is built in PR #1 but not released.
- Ranks 8, 12 and 14 moved from "starts after schema v3" to in progress at the analytics step.
- Ranks 6 and 9 are unblocked by the schema contract. Rank 9 also needs gate threshold calibration
  from the owner. Rank 11 depends on the data-source comparison, which is in progress.
- Re-scored confidence (the schema contract landed): rank 6 from 0.7 to 0.8, rank 8 from 0.7 to 0.8,
  rank 9 from 0.6 to 0.7, rank 12 from 0.5 to 0.6, rank 14 from 0.5 to 0.6. RICE values recalculated:
  rank 6 from 1.7 to 1.9, rank 8 from 1.1 to 1.2, rank 9 from 0.6 to 0.7, rank 12 from 0.3 to 0.4,
  rank 14 from 0.25 to 0.3. Ranks 2 to 5 show a dash now that they are done (their earlier values
  were 9, 4.8, 4.3 and 4.0).
- The Now, Next, Later and Very later tables and the status overview follow the owner order.

What was added:

- Progress and Depends on columns in the priority ranking.
- A "Done 2026-11-18" list with evidence pointers.
- The nightly workflow proposal for the slow and live tests (RICE 4.0, not ranked, needs an owner
  decision, depends on PR #1).
- A "Risks and blockers (2026-11-18)" section.

What was removed: nothing. Done items moved to the Done list and kept their evidence. The
update 1 section keeps its content and is retitled "Changes in update 1 (2026-11-18)" so it does not
clash with this section.
