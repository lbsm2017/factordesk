# factordesk roadmap

Last updated 2026-11-18 (update 3). Now / Next / Later format. A roadmap is a plan, not a promise: items move
when evidence changes. Every statistical item follows `docs/research-protocol.md` (hypothesis and
test written down first, logged, independently reviewed) before it ships.

## Status overview (2026-11-18)

- **Done:** the SPY thin slice (factor download, prices, date matching, HAC regression, rolling
  betas, return and risk attribution, offline HTML report), independently validated
  (`docs/validation/spy-slice-validation.md`, verdict "ship with changes").
- **Merged into `dev` on 2026-11-18, not on `prod`:** PR #1 (dashboard, rolling speed-up, SPY
  hardening, schema contract, README and bibliography, CI, one-shot install code); PR #2 (shrunk
  betas, Kalman betas and residual alpha, each independently validated); PR #3 (the nightly workflow
  for the slow and live tests). Ranks 1 to 4, 8, 12 and 14 are Done on `dev`.
- **Release to `prod` has not happened.** It is the owner's step. The one-shot install code is in
  `dev` and its release stays very later (rank 7), following `docs/release-checklist.md`.
- **Merged, not yet run:** the nightly workflow (PR #3). It has not run on GitHub. Run it once by
  hand with `workflow_dispatch` before relying on it.
- **In progress:** the data-source comparison of Yahoo, Tiingo and Alpaca (blocks rank 11).
- **Specified, not built:** report redesign (`docs/design/report-design.md`), regional datasets
  (`docs/methodology-datasets.md`), fragility score, lead-lag betas.
- **Owner ranking (2026-11-18, re-scored in update 2):** 16 epics are ranked in the priority ranking
  below. Items 1 to 4, 8, 12 and 14 are Done (on `dev`). Item 5 is Next. Items 6, 9, 10, 11 and 15
  are Later, and items 7, 13 and 16 are Very later. Three new tickets are listed under the table
  and are not ranked yet; the owner places them.

## Priority ranking (owner, 2026-11-18)

Ranks keep the owner order of 2026-11-18. Done rows show a dash for RICE; their earlier values are in
"Changes in update 3". Owner decision and progress are the owner's words where the owner gave them.

| Rank | Epic | Reach (1-10) | Impact (0.25-3) | Confidence | Effort (agent sessions, about 30 min each) | RICE | MoSCoW | Owner decision | Progress | Depends on |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | Ship the dashboard: push, PR, merge to dev | - | - | - | - | - | Must | ok | Done: PR #1 merged into dev on 2026-11-18; not on prod | CI green (done) |
| 2 | Rolling regression speed-up conditions | - | - | - | - | - | Must | ok | Done: 3 conditions met, merged in PR #1; independent validation accepted | none |
| 3 | SPY hardening: diagnostics, quality gate, bad input | - | - | - | - | - | Must | deliver and close | Done: 29 findings, 20 fixed before, 4 fixed now, 5 deferred (closure doc). F13 non-USD: owner decided to refuse (new ticket N1); G2 and gate thresholds wait for the placebo calibration | none |
| 4 | Schema contract (ships as schema version 4) | - | - | - | - | - | Must | deliver and close | Done: five optional sections, panel registries on both renderers, four briefs; merged in PR #1 | none |
| 5 | First GitHub CI run | - | - | - | - | - | Should | next | Done: run 1 failed on one float comparison in a fixture, fixed; run 2 green (3 min 30 s). Open: Playwright cache hit path needs a third run; the nightly workflow (PR #3) is merged but has not run | PR #1 (done) |
| 6 | Fragility score | 6 | 2 | 0.8 | 5 | 1.9 | Should | later | Not started; spec ready; the hardening deferral D-1 (influence diagnostic) folds in here | Schema contract (done): unblocked |
| 7 | One-shot install and run | 8 | 1 | 0.7 | 5 | 1.1 | Should | very later (was next) | Code merged into dev with PR #1; not released: the owner runs `docs/release-checklist.md`; installer URL and a real install on a machine without uv unverified | PyPI release (owner) |
| 8 | Residual alpha analysis | - | - | - | - | - | Should | next | Done: merged into dev in PR #2 on 2026-11-18; independently validated (merge with conditions, conditions met); not on prod. Owner decision 2 (earlier data for a later start date) deferred | Schema contract (done) |
| 9 | Lead-lag betas | 4 | 2 | 0.7 | 8 | 0.7 | Could | later | Not started; spec ready | Schema contract (done); hardening gate (done); gate threshold calibration (owner) |
| 10 | Dead-code cleanup | 2 | 0.25 | 1.0 | 1 | 0.5 | Could | later | Not started | none |
| 11 | Data triangulation | 7 | 2 | 0.5 | 20 | 0.35 | Could | later | Not started | Data-source comparison (in progress) |
| 12 | Shrunk betas | - | - | - | - | - | Could | next | Done: merged into dev in PR #2 on 2026-11-18; independently validated (conditions C1 to C3 met); not on prod | Schema contract (done) |
| 13 | Peers using the batch price fetch | 4 | 1 | 0.6 | 8 | 0.3 | Could | very later | Not started; the batch fetch exists but nothing calls it | Cointegration (not built) |
| 14 | Kalman betas | - | - | - | - | - | Could | next, before later items | Done: merged into dev in PR #2 on 2026-11-18; independently validated (conditions met); slow tests ran at 200 replications on 2026-11-18; not on prod | Schema contract (done) |
| 15 | European mode | 3 | 2 | 0.5 | 20 | 0.15 | Won't (this round) | later | Not started; D16 covers RF source, ECB FX, regressor default, Canada | Owner decisions D16 and F13 (F13 decided on 2026-11-18: refuse non-USD until European factors exist) |
| 16 | Alpaca adapter | 2 | 1 | 0.5 | 8 | 0.13 | Won't (this round) | very later | Not started | none |

The RICE values are the chief of staff's estimates, not measured results. RICE is Reach x Impact x
Confidence / Effort. Effort counts agent sessions of about 30 minutes each. Values for ranks 6, 7, 9,
10, 11, 13, 15 and 16 are unchanged since update 2.

New tickets, not ranked (added 2026-11-18, update 3). RICE uses the same method; each number is a
rough estimate and is shown to one decimal only because the formula gives it, not because it is
precise.

| Id | Ticket | Reach | Impact | Confidence | Effort | RICE | MoSCoW | Source |
|---|---|---|---|---|---|---|---|---|
| N1 | Currency check (F13): read the currency from Yahoo metadata and refuse a non-USD ticker with a clear message until European factors exist (owner decision, 2026-11-18). Then add the decision entry (D-entry) that M1.5 lacks | 4 | 1 | 0.8 | 1 | 3.2 | Should | `docs/validation/spy-hardening-closure-2026-11-18.md`, row F13 and deferral D-4; `docs/methodology.md` M1.5 |
| N2 | Real-browser pass over the three new panels (shrunk, Kalman, residual), plus screen readers, Firefox, Safari and print for the React page. Needs the owner's devices for screen readers | 6 | 1 | 0.7 | 3 | 1.4 | Should | "What I could not check" in `docs/reviews/shrunk-betas-validation-2026-11-18.md`; "Not verified yet" in `docs/dashboard.md` |
| N3 | Align the screen-reader strings of the Kalman panels (static and React) and move them into `kalman_text.json` | 2 | 0.25 | 0.8 | 1 | 0.4 | Could | F7 in `docs/reviews/kalman-betas-validation-2026-11-18.md` |

The nightly workflow (RICE 4.0 in update 2) is merged (PR #3). What is left is one manual run (see
Risks and blockers); it has no RICE of its own.

## Now

Nothing is in Now on 2026-11-18. Item 1 moved to Done when PR #1 merged. The owner's next steps are
the manual run of the nightly workflow and the release to `prod`.

## Done 2026-11-18

All rows below are merged into `dev` and are not on `prod`.

| Item | What it delivered | Evidence |
|---|---|---|
| Dashboard (rank 1) | Local FastAPI server and React page, search bar, range chips and custom dates, factor refresh; PR #1 merged. Not run against live Yahoo data beyond one ticker | `docs/dashboard.md`, `docs/specs/dashboard.md`, `docs/reviews/dashboard-review-2026-11-18.md` |
| Rolling regression speed-up conditions (rank 2) | All three conditions met; merged in PR #1; independent validation accepted | `docs/reviews/rolling-speedup-validation-2026-11-18.md` |
| Hardening of the SPY slice (rank 3) | 29 findings: 20 fixed before, 4 fixed now, 5 deferred with reasons (F8, F13, G2, the gate calibration, T54 to T56) | `docs/validation/spy-hardening-closure-2026-11-18.md` |
| Schema contract (rank 4, ships as schema version 4) | Five optional sections, panel registries on both renderers, four briefs. The contract keeps its v3 name | `wiki/decision-schema-v3-contract.md`, `docs/specs/schema-v3-contract.md` |
| First GitHub CI run (rank 5, part) | Run 1 failed on one float comparison, fixed; run 2 green | `docs/reviews/ci-first-run-2026-11-18.md` |
| Residual alpha analysis (rank 8) | Residual return section with point-in-time betas; validator found one high and three medium findings, all fixed; owner decision 2 deferred | `docs/validation/residual-alpha-handoff-2026-11-18.md`, `docs/reviews/residual-alpha-validation-2026-11-18.md` |
| Shrunk betas (rank 12) | Betas pulled toward a prior, with a detectable-effect statement; three wording and path conditions met, no number changed | `docs/validation/shrunk-betas-handoff-2026-11-18.md`, `docs/reviews/shrunk-betas-validation-2026-11-18.md` |
| Kalman betas (rank 14) | Time-varying betas with bands, past data only; four conditions met, `ex_ante_betas` dropped from the payload; slow tests passed at 200 replications (648.8 s on a loaded machine) | `docs/validation/kalman-betas-handoff-2026-11-18.md`, `docs/reviews/kalman-betas-validation-2026-11-18.md` |
| Nightly workflow for the slow and live tests | Merged in PR #3. Not yet run on GitHub. The `slow` job sets `FACTORDESK_KB_REPS=200` from the follow-up change | `.github/workflows/nightly.yml`, `wiki/decision-nightly-slow-tests.md` |

## Next

Item 5 of the priority ranking and the three new tickets, in this proposed order until the owner
ranks them.

| Item | Why it matters | Status | Depends on |
|---|---|---|---|
| First GitHub CI run (rank 5) | Runs the checks on GitHub for every pull request | Done except: the Playwright cache hit path needs a third run, and the nightly workflow needs one manual run (`workflow_dispatch`) | PR #1 (done), PR #3 (done) |
| N1 Currency check, refuse non-USD (new, Should, RICE 3.2) | Stops a silent wrong result for a ticker quoted in another currency | Not started; owner decided to refuse on 2026-11-18 | Owner ranking |
| N2 Real-browser and accessibility pass (new, Should, RICE 1.4) | The three new panels and the React page have only been tested by code and by a fake backend | Not started | Owner devices for screen readers |
| N3 Kalman screen-reader strings (new, Could, RICE 0.4) | Both panels should say the same thing to a screen reader | Not started | none |

## Later

Items 6, 9, 10, 11 and 15 of the priority ranking, in owner order.

| Item | Why it matters | Status | Depends on |
|---|---|---|---|
| Fragility score (rank 6) | "This alpha rests on N days": how many days must go before significance flips; leave-one-year-out | Not started; spec ready; the hardening deferral D-1 (influence diagnostic) folds in here | Schema contract (done): unblocked |
| Lead-lag (Dimson / Scholes-Williams) betas (rank 9) | Fixes non-synchronous closes (old Yahoo SPY data, future European and Asian tickers); switched on by the quality gate | Not started; spec ready | Schema contract (done); hardening gate (done); gate threshold calibration (owner) |
| Dead-code cleanup (rank 10) | Removes unused code | Not started | none |
| Data-quality plan (triangulation) (rank 11) | A written plan for multi-source consensus returns and per-day agreement scores | Not started | Data-source comparison (in progress) |
| European mode (rank 15) | Regional French factors, USD conversion, currency regressor | Not started; D16 covers RF source, ECB FX, regressor default, Canada | Owner decision D16; F13 decided (refuse non-USD until this exists) |

## Very later

Items 7, 13 and 16 of the priority ranking.

| Item | Why it matters | Status | Depends on |
|---|---|---|---|
| One-shot install-and-run command (rank 7) | A single line per OS that installs uv if missing and opens a report (`uvx factordesk report SPY --open`); a short bootstrap script pinned to a release tag, readable, with a published checksum | Code merged into dev with PR #1; not released (no publishing) | PyPI release (owner); first tagged release |
| Peer comparison (rank 13) | Where a stock's betas sit within its sector | Not started; the batch fetch exists but nothing calls it | Cointegration (not built) |
| Alpaca adapter (rank 16) | Optional cross-check and fallback from 2016, returns rebuilt from raw closes and dividends (`sip` feed); check Alpaca's "user application" notice before shipping | Not started | none |

## Not in the owner ranking

Items below had earlier rows but do not appear in the 2026-11-18 owner ranking. They are kept
unchanged until the owner ranks them.

| Item | Why it matters | Status | Depends on |
|---|---|---|---|
| First commit, `prod` and `dev` branches | Everything after this goes through pull requests | Not Started | Hardening; folder rename to `factordesk` |
| Report redesign integration | The validated numbers in the approved look | Not Started | First commit; schema v3 contract |
| Config key names | Code reads the `.env` names actually used (`ALPACA_KEY`, `ALPACA_SECRET`, `TIINGO_KEY`); Alpaca feed `sip` | Not Started | First commit |
| Total returns from Close + Dividends | factordesk computes total return itself (CRSP convention) for every source; vendor Adj Close becomes a reported cross-check (owner decision 2026-11-18) | Not Started | Schema v3 contract; methodology update |
| Placebo calibration, with a `factordesk calibrate` CLI command (multi-core) | Publishes how often each report flag is wrong on stocks with no true alpha. The G2 variance-stability gate and the G1 threshold calibration wait for it (2026-11-18) | Not ranked | Now items it calibrates (gate, fragility, alerts) |
| Block-bootstrap intervals | Standard errors for risk shares and return contributions; cross-check of HAC | Not ranked | none |
| Specification curve | Share of reasonable specifications (windows, start dates, sources) that agree on alpha | Not ranked | Data triangulation |
| Data triangulation build | Consensus returns from Yahoo, Tiingo and Alpaca; flagged disagreement days | Not ranked | Data-quality plan |

Tiingo adapter for users with a paid licence that allows this use (the free plan forbids storing
data, validating other datasets and charting prices). Factor-mimicking hedge, model comparison (CAPM / FF3 / FF5 / FF5+momentum), portfolio mode,
screener, out-of-sample stability score, other regions after Europe, cointegration, drift alerts
and regime betas (specified in `docs/methodology.md`, not yet scheduled).

## Risks and dependencies

- **The folder rename blocks the first commit.** The project folder can only be renamed while no
  editor or session has it open.
- **Data licences.** Tiingo's free plan is "internal use only"; Yahoo is personal use. Real-data
  sample reports stay out of the public repository (owner decision 2026-11-18).
- **Schema conflicts between parallel branches.** The five-section contract is merged, so this risk
  applies only to future sections.

## Risks and blockers (2026-11-18)

State after PRs #1, #2 and #3 merged into `dev`.

- **Release to `prod` has not happened.** It is the owner's step (`docs/release-checklist.md`). The
  one-shot install release stays very later (rank 7).
- **The nightly workflow has not run on GitHub.** Run it once by hand with `workflow_dispatch`. The
  `slow` job sets `FACTORDESK_KB_REPS=200` in a follow-up change; the Kalman tests alone took about
  11 minutes on a developer machine, so the slow job is about 13 minutes there. On a shared runner it
  may be slower; the 45-minute limit stays. Not measured on GitHub (`wiki/decision-nightly-slow-tests.md`).
- **Schema version is 4, not 3.** The contract keeps its v3 name in file names and wiki pages, but
  the shipped schema is version 4.
- **Live Yahoo throttling untested beyond one ticker.** A real run on one ticker is the only live
  evidence. Throttling under a full batch is not tested.
- **Shared methodology file.** The feature branches add methodology proposals only. Folding them into
  `docs/methodology.md` is the owner's call (pending: shrunk SB10.3, Kalman KB10.3, residual R4.7, R4.8,
  R5.3 and R8, and the Kalman drift-rate definition).

Open items, with the owner's decision where there is one (as of 2026-11-18):

1. **Non-USD tickers (F13).** Decided: refuse until European factors exist. Ticket N1 above.
   Source: `docs/validation/spy-hardening-closure-2026-11-18.md`, D-4.
2. **G2 variance-stability gate and G1 threshold calibration.** Wait for the placebo calibration
   (`factordesk calibrate`, in the "Not in the owner ranking" table). Source: the same closure
   document, D-5.
3. **Residual alpha owner decision 2** (earlier data for a later start date). Deferred as a
   follow-up; nothing printed is wrong while it is not built. Source: F7 in
   `docs/reviews/residual-alpha-validation-2026-11-18.md`.
4. **Kalman spec edits (the spec owner's).** Five unfilled template markers (`{{MA_COV}}`,
   `{{T5_RESULT}}`, `{{MA_COV2}}`, `{{SIM_TABLE}}`, `{{KD7}}`), a stale header and KB8.1 runtime, and
   the proposal to remove the window clause from the L-KF label (KB8.3). Source:
   `docs/validation/kalman-betas-handoff-2026-11-18.md`, "After validation".
5. **Kalman panel screen-reader strings.** Ticket N3. Source: F7 in
   `docs/reviews/kalman-betas-validation-2026-11-18.md`.
6. **Unsourced claims in `docs/references.md`.** The owner's count is nine. The section "Claims in the
   repo without a source" lists seven on this branch (C1 to C7); I could not find the other two.
   Needs the owner's count checked.
7. **Not verified anywhere:** a real-browser pass over the three new panels, screen readers,
   Firefox, Safari and print for the React page. Ticket N2. Source: "What I could not check" in the
   shrunk validation and "Not verified yet" in `docs/dashboard.md`.
8. **Validator findings not marked fixed in their handoffs** (one line each):
   - Shrunk finding 4: the vintage check uses the CRSP stamp only when the factor frame has one, and the loader records none; the last-date check covers the realistic cases (`docs/reviews/shrunk-betas-validation-2026-11-18.md`, section 6).
   - Shrunk finding 5: `latest_window.sample` describes the whole sample (8,474 rows for SPY), not the 252-row window (same section; handoff section 5).
   - Shrunk handoff section 6, open owner decisions: prior spread for single stocks, `delta = 0.05` fixed or user-chosen, the L-SHRINK "bars" wording, where the moved-away rule lives, and the SB10.3 methodology additions; the proposed SB6 and SB5 spec edits are not applied.
   - Residual F8: TR15 (c) checks only the last date of a truncated run, and the TR12 off-by-one guard compares two computations on the data (`docs/reviews/residual-alpha-validation-2026-11-18.md`).
   - Residual methodology proposals R4.8, R4.7 with R8, and R5.3 are not applied; the code already behaves as proposed.
   - Kalman F8, KB7.3: the spec puts MSTR's crossing at the 2021-06-23 re-estimation; the crossing is on 2021-06-29 (`docs/reviews/kalman-betas-validation-2026-11-18.md`).
   - Kalman handoff section 9: spec questions KB10.4 Q1 to Q5, the Student-t variant in the hook, the vintage table length on long histories, and the format check in `CONTRIBUTING.md` and the release checklist.
   - Kalman F1, report-level notice: a guard in `pipeline.py` that adds a notice when a section fails is a proposal for the owner (contract file, SC3.2).
   - Kalman, the MSTR half of TKB24 is not a test until an MSTR cache is part of the live data.

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

## Changes in update 2 (2026-11-18)

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

What was added: Progress and Depends on columns in the priority ranking; a "Done 2026-11-18" list
with evidence pointers; the nightly workflow proposal (RICE 4.0); a "Risks and blockers (2026-11-18)"
section.

## Changes in this update (update 3, 2026-11-18)

What moved, and why:

- PR #1 (dashboard, rolling speed-up, SPY hardening, schema contract, README and bibliography, CI,
  one-shot install code) merged into `dev`. Rank 1 moved from "in review" to Done. Its earlier RICE
  was 30.
- PR #2 merged into `dev`: rank 8 (residual alpha), rank 12 (shrunk betas) and rank 14 (Kalman
  betas), each independently validated. All three moved from Next to Done, and none is on `prod`.
  Their earlier RICE values were 1.2, 0.4 and 0.3.
- PR #3 merged into `dev`: the nightly workflow. It has not run on GitHub; the first manual run is
  open. It left the "new, not ranked" note and is a Done row.
- Rank 7 stays very later: the code is in `dev`, the release is the owner's step and has not happened.
- Ranks 6, 9, 10, 11, 13, 15 and 16 are unchanged. Rank 15 now notes that F13 is decided.
- The old Now section is empty, and Next holds rank 5 and the three new tickets.

What was added:

- Tickets N1 (currency check), N2 (real-browser and accessibility pass) and N3 (Kalman
  screen-reader strings), with RICE 3.2, 1.4 and 0.4. Method as in the table: Reach x Impact x
  Confidence / Effort, effort in agent sessions of about 30 minutes. N1 is Reach 4, Impact 1,
  Confidence 0.8, Effort 1. N2 is Reach 6, Impact 1, Confidence 0.7, Effort 3. N3 is Reach 2,
  Impact 0.25, Confidence 0.8, Effort 1. These inputs are estimates, not measurements.
- The open-items list in Risks and blockers (eight items, with source pointers).

What was removed: the notes that the three feature agents had no commits and that PR #1 awaited the
owner, the stale schema-conflict risk (the contract is merged) and the "pull requests need a remote" risk (the repository exists). Nothing else was removed.
