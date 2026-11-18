# Hand-off: four statistical features in parallel

Status: dispatch briefs, written 2026-11-18, for the four features that build on the schema v3
contract: fragility score, lead-lag betas, Kalman betas, shrunk betas. (Residual alpha analysis is
the fifth contract section; it is already specified and is not dispatched here.)
Contract: `docs/specs/schema-v3-contract.md` (section ids SC0-SC9). Protocol:
`docs/research-protocol.md`. Standards: `CODING_STANDARDS.md`.

Each brief below is self-contained: paste it into the task of one engineer or agent. The four can
start at the same time; they share no file except the generated and append-only files of contract
SC7, which have their own merge rules.

---

## Common rules (every brief includes these by reference)

1. **Branch.** Start from `dev` once `feat/schema-v3-contract` has merged into it; until then,
   branch from `feat/schema-v3-contract` itself and rebase onto `dev` after it merges. Branch
   names: `feat/fragility-score`, `feat/lead-lag-betas`, `feat/kalman-betas`,
   `feat/shrunk-betas`. Work through a pull request to `dev`; the owner reviews and merges. Commit messages are plain
   sentences with no attribution lines.
2. **Files.** Edit only the files your brief lists under "May touch", plus new files under your own
   feature's name. If you need a change in any other file, stop and ask: it goes through its own
   small pull request to `dev` first (contract SC7). In particular never edit `report/schema.py`,
   `report/base.py`, `report/render_html.py`, `report/report.css`, `report/panel_registry.py`,
   `report/panels/__init__.py`, `pipeline.py`, `section_hooks/context.py`,
   `section_hooks/__init__.py`, `tests/fixtures/mock_report*.json`, `tests/test_report.py`,
   `ReportView.tsx`, `panelRegistry.ts`, `Panel.tsx`, `src/api/types.ts`, `src/styles/*`,
   `docs/methodology.md`, `docs/ROADMAP.md`, `README.md`, `CONTRIBUTING.md`, `CODING_STANDARDS.md`,
   or another feature's files.
3. **Order of work.** (a) registry lines and the oracle tests from the spec, written before the
   code (protocol items 1-2, Definition of Done); (b) analytics module, pure and typed
   (`CODING_STANDARDS.md` section 4), until the oracle tests pass; (c) section model in your
   `report/sections/<feature>.py`; (d) pipeline hook in your `section_hooks/<feature>.py`;
   (e) static panel in your `report/panels/<feature>.py`; (f) React panel in your
   `frontend/src/components/report/sections/<Name>Panel.tsx`; (g) section fixture and section
   tests; (h) regenerate the OpenAPI document and types; (i) independent validation; (j) pull
   request.
4. **Section model.** Keep the class name and the `<NAME>_SECTION` spec object of the placeholder.
   Add the fields of your spec (with the normalisations of contract SC6 item 12: display factor
   names, `_annual`, `adj_r2`). Put nested models in the same file. Put full nested statistics
   (status, reason, sample, labels, caption) into `statistic_models`, your own footnote keys and
   texts into `label_text`, and type your `labels` field with your own `Literal` of keys. A
   not-ok section carries no float outside nested objects with their own status (SC1 item 3).
5. **Hook.** Your hook reads only `SectionContext` (`ctx.sample`, `ctx.regression`, `ctx.core`,
   `ctx.factor_frame`, ...). It never changes a core section, never reads another feature's
   section, never raises for data reasons (return `status = "failed"` and a reason), and returns
   the section on every report once the feature is built. Headline numbers and tags never change
   (prove it with a bitwise comparison test, as your spec asks).
6. **Panels.** Static: keep `render_<x>_panel(report) -> str | None`, the `register_panel` call
   (name and position unchanged) and the element id; use the public helpers of `render_html.py`
   (`panel_head`, `panel_section`, `empty_state`, `footnote`, `fmt_num`, `fmt_signed`, `fmt_pct`,
   `fmt_tstat`, `fmt_pval`, `date_long`, `label_texts`, `esc`); put panel CSS in the `css=` argument.
   React: keep the component name and file; use `Panel`, `EmptyState` and the formatters of
   `src/format/`; read nested types as `components["schemas"]["..."]` from `../../../api/types.gen`;
   CSS in `sections/<Name>Panel.css`, colours only through existing tokens. Every chart is also a
   table (design rule); no `dangerouslySetInnerHTML`. A null field renders nothing.
7. **Fixture.** Replace your file in `backend/factordesk/tests/fixtures/sections/` with a synthetic
   section of the real shape (built by a function in your section test, written with
   `model_dump_json()`), marked synthetic in its reasons or captions where text appears. The
   backend helper `report_with_section` and the frontend helper `withSection` pick it up.
8. **Generated files.** After any change to your section model, from the repository root:
   `uv run python -m factordesk.api.openapi_dump frontend/src/api/openapi.json` and
   `npm --prefix frontend run gen:types`. On a merge conflict in either file, rerun both commands;
   never merge them by hand (SC8).
9. **Append-only files.** Append your spec's registry lines (its "Registry entries" section) to
   `docs/registry/tests.jsonl` in your first commit, as protocol Appendix A JSON lines; keep the
   spec's `test_id`s unless they collide with lines already there. On a merge conflict at the end
   of the file, keep both sides. Same for `wiki/index.md` and `wiki/log.md` (one line each for
   your decision page `wiki/decision-<feature>.md`).
10. **Methodology text.** Do not edit `docs/methodology.md` (four branches would conflict). Your
    spec stands in as the methodology section; its "proposed additions" list stays for the owner
    (contract SC6 item 11, pending the owner's agreement).
11. **Gates, before every push.** From the repository root: `uv run pytest -q`,
    `uv run ruff check backend`, `uv run pyright`; from `frontend/`: `npm run typecheck`,
    `npm run lint`, `npm test`, `npm run build`, `npm run size`, `npm run e2e`. Slow tests
    (`-m slow`) before the pull request; live tests (`-m live`) once, non-blocking, results in the
    validation note.
12. **Independent validation (protocol section 7-9 and the wiki decision "check our own numbers
    independently").** Someone who did not write the code (a separate reviewer or agent, given the
    spec and the branch, not the author's notes) does all of:
    - recomputes the section's headline numbers from raw inputs with separate code (scripts outside
      the repository) and compares them with the JSON the branch produces, on the synthetic DGPs
      of the spec and on SPY (and the spec's second live ticker) from the local cache;
    - runs the spec's look-ahead perturbation and truncation tests independently;
    - injects at least 8 mutants into the analytics module (constants of the spec, boundaries,
      off-by-one in windows, a removed lag, a wrong family size) and records which the test suite
      catches;
    - ticks protocol sections 1-8, line by line, or answers "n/a, because ...";
    - writes `docs/validation/<feature>-validation.md` with a verdict (ship, ship with changes,
      do not ship), findings ranked by severity, and the registry `test_id`s of every run it made
      (appended to `docs/registry/tests.jsonl`).
    The author fixes findings or records them as deviations before the pull request is opened.

---

## Brief 1: fragility score

**Goal.** Show, for alpha and each reliable beta, the smallest number of trading days found whose
removal flips its significance tag, a leave-one-year-out table and the ten most influential days,
without ever removing a day from any reported estimate.

**Spec.** `docs/specs/fragility-score.md` (FR0-FR13; schema FR9.2; tests TFR01-TFR22 in FR12;
registry entries FR13). Contract SC2.1.

**Owner decisions in force.** The warning threshold (`k <= 5`) is postponed: do not implement the
fragility warning. Leave `fragile_warning` and `explanation` out of `FlipCount` (they are added
when the owner decides); the score itself, `k_ref` and the sentences of FR6.1 and FR6.3 ship. Open
questions FR11.3 items 2 and 3 are not decided: keep the sentence in the panel (no KPI change,
the current spec), and compute the beta searches eagerly (FR8 estimates about 11 s in the worst
case at 8,000 rows); if a measured report takes clearly longer, report the time in the pull request
and ask the owner before merging.

**May touch.** `backend/factordesk/analytics/fragility.py` (new),
`backend/factordesk/report/sections/fragility.py`, `backend/factordesk/section_hooks/fragility.py`,
`backend/factordesk/report/panels/fragility.py`, `backend/factordesk/tests/test_fragility.py`
(new), `backend/factordesk/tests/test_section_fragility.py` (new),
`backend/factordesk/tests/fixtures/sections/fragility.json`,
`frontend/src/components/report/sections/FragilityPanel.tsx` (and new `.css`, `.test.tsx`),
`docs/specs/fragility-score.md` (corrections only), new `docs/validation/fragility-validation.md`,
new `wiki/decision-fragility-score.md`; append-only and generated files per common rules 8-9.

**Must not touch.** Everything in common rule 2, and the other three features' files. No API
parameter, CLI option or config key that excludes dates (FR7, TFR17).

**Contract hooks.** `FragilitySection` with the FR9.2 fields (`algorithm_version`, `k_max`,
`alpha: FlipCount`, `betas: list[FlipCount]`, `leave_one_year_out: LoyoTable`,
`influence: InfluenceLists`, `labels`), nested `FlipCount` (own status `Literal` including
`not_flipped_within_cap`), `RemovedDay`, `LoyoTable`, `LoyoRow` (`alpha_annual`, `se_annual`),
`InfluenceLists`, `InfluentialDay`; label `L-FRAGILITY` with the FR6.4 text in
`FRAGILITY_SECTION.label_text`. Hook `build_fragility(ctx)`: `ctx.sample`, `ctx.daily` (the flip
count is on the daily test, FR1), `ctx.gate` (for `gate_upper_bound_note`), `ctx.core.regression`
(tags `tag_full`), `ctx.audit` (`InfluentialDay.audit_findings`). Panel `render_fragility_panel`,
position 530, id `fragility`; React `FragilityPanel`.

**Tests.** TFR01-TFR22 in `test_fragility.py` (seeds `20261118 + 500 + k`; `slow` and `live`
markers as FR12 says). In `test_section_fragility.py`: the section validates and round-trips;
statuses of FR9.1 (`not_applicable` for a noise tag, `insufficient_data` LOYO under 3 years,
`failed` on a design-guard failure); every M3-M10 number of a DGP-A report is bitwise identical
with and without the hook (FRD9); the static panel draws the table and the influential-days list
and no "alpha without these days" number (FR7); the fixture. In `FragilityPanel.test.tsx`: null
renders nothing, the empty state, the flip-count sentence and the LOYO table.

**Validation focus.** Brute-force minimum versus greedy count on small samples (FR2.3); exact
leave-one-out refits versus the influence approximation; LOYO refits with statsmodels; SPY numbers
of FR10.

---

## Brief 2: lead-lag (Dimson / Scholes-Williams) betas

**Goal.** Add each factor's previous-day and next-day return to the regression, sum the three
coefficients per factor (Dimson), test the timing adjustment (family F11) on every report, and show
the lead-lag betas beside the daily betas when the quality gate fires or F11 rejects, with a
Scholes-Williams cross-check. The headline betas and tags never change.

**Spec.** `docs/specs/lead-lag-betas.md` (LL0-LL12; schema LL6.6; status LL6.4; tests
TLL01-TLL20 in LL11; registry entries LL12). Contract SC2.2.

**Owner decisions in force.** The Scholes-Williams cross-check is approved (LL4 ships, as the
exception to `CODING_STANDARDS.md` section 4 that LL4 describes). A lead-lag beta never replaces
the headline beta. The gate caveat must not blame late vendor closes (LL9.2 rule 3 wording). Not
decided: trigger (C) for other time zones (not built).

**May touch.** `backend/factordesk/analytics/lead_lag.py` (new),
`backend/factordesk/report/sections/lead_lag.py`, `backend/factordesk/section_hooks/lead_lag.py`,
`backend/factordesk/report/panels/lead_lag.py`, `backend/factordesk/tests/test_lead_lag.py` (new),
`backend/factordesk/tests/test_section_lead_lag.py` (new),
`backend/factordesk/tests/fixtures/sections/lead_lag.json`,
`backend/factordesk/tests/test_lookahead.py` (only to add the T104 allowlist entry for
`lead_lag.factor_at_offset`, and only if a forward lookup there trips the scan; LL5.3 is a proposal,
so say so in the pull request), `frontend/src/components/report/sections/LeadLagPanel.tsx` (and new
`.css`, `.test.tsx`), `docs/specs/lead-lag-betas.md` (corrections only), new
`docs/validation/lead-lag-validation.md`, new `wiki/decision-lead-lag-betas.md`; append-only and
generated files per common rules 8-9.

**Must not touch.** Everything in common rule 2, and the other three features' files. No per-date
lead-lag series (LLD7); no lead-lag beta used as an ex-ante exposure (LL5.2).

**Contract hooks.** `LeadLagSection` with the LL6.6 fields (`trigger`, `gate_ref`, `hac_lags`,
`n_params`, `timing_test`, `betas`, `alpha`, `r2`, `adj_r2`, `resid_rho1`, `resid_rho1_z`,
`resid_vr5`, `resid_rho1_daily`, `resid_vr5_daily`, `joint_wald`, `sw_crosscheck`, `sentences`,
`labels`); nested `LeadLagTrigger`, `TimingTest` (own status; filled whenever `n_LL >= 500`, even
when the section is `not_applicable`, SC6 item 6), `LeadLagBeta` (with `daily_beta`, `daily_tag`
copied from `ctx.core.regression`), `LeadLagAlpha` (`alpha_annual`, `se_annual`, `ci95_annual`,
`edge_term_annual`), `JointWald`, `SWCrossCheck`; label `L-LEADLAG`. The section's `SampleInfo`
lists the removed last row with reason `lead_after_sample_end` (already in `ExclusionReason`).
Hook `build_lead_lag(ctx)`: `ctx.sample`, `ctx.factor_frame` (French calendar neighbours,
LL2.2), `ctx.core.quality_gate.fired` (trigger A, read, never re-implemented),
`ctx.core.regression`. Panel `render_lead_lag_panel`, position 510, id `lead-lag`; React
`LeadLagPanel`.

**Tests.** TLL01-TLL20 in `test_lead_lag.py` (seeds `20261118 + 400 + k`). In
`test_section_lead_lag.py`: section validates and round-trips; the trigger table of LL6.1/LL6.4;
`not_applicable` section with a filled F11; headline invariance (TLL15) through the hook; the
static panel's third-column table and the LL9.2 sentence; the fixture. In `LeadLagPanel.test.tsx`:
null renders nothing, not-applicable state with the F11 line, the table.

**Validation focus.** The 16-regressor fit and the F10/F11 families against statsmodels
`OLS(...).fit(cov_type="HAC", ...)` and `multipletests`; the French-calendar neighbour rule with an
excluded stock row (TLL01); the sample-end rule under a perturbed French tail (TLL02); SPY numbers
of LL8.

---

## Brief 3: Kalman-filter betas

**Goal.** Add a daily series of time-varying betas estimated by a Kalman filter (random-walk betas,
constant alpha, one hyperparameter re-estimated every 252 rows from past data only), with a
model-based band, as an extra series beside the rolling betas. Nothing downstream uses it.

**Spec.** `docs/specs/kalman-betas.md` (KB0-KB12; outputs, status and schema KB8.3; tests
TKB01-TKB24 in KB11; registry entries KB12). Contract SC2.3.

**Owner decisions in force.** None recorded yet on KB10.4. Build the spec's defaults: re-estimation
every 252 rows (Q1 option b), scalar `Q` (Q2), random walk (Q3), **no** retrospective smoothed view
in v1 (Q4, the spec's recommendation: leave `KalmanRetrospective` out). Runtime (Q5): aim for the
10 s target of KB10.2; if a 33-year ticker still takes more than 15 s, report the measured time in
the pull request and ask before merging.

**May touch.** `backend/factordesk/analytics/kalman.py` (new),
`backend/factordesk/report/sections/kalman.py`, `backend/factordesk/section_hooks/kalman.py`,
`backend/factordesk/report/panels/kalman.py`, `backend/factordesk/tests/test_kalman.py` (new),
`backend/factordesk/tests/test_section_kalman.py` (new),
`backend/factordesk/tests/fixtures/sections/kalman.json`,
`frontend/src/components/report/sections/KalmanPanel.tsx` (and new `.css`, `.test.tsx`),
`docs/specs/kalman-betas.md` (corrections only), new `docs/validation/kalman-validation.md`, new
`wiki/decision-kalman-betas.md`; append-only and generated files per common rules 8-9.

**Must not touch.** Everything in common rule 2, and the other three features' files, including
`test_lookahead.py` (put the TKB18 static scan in `test_kalman.py`) and `RollingPanel.tsx` (the
Kalman line goes on the rolling chart only in the later integration change, contract SC6 item 8).
`analytics/attribution.py` must not import `kalman` (TKB23).

**Contract hooks.** `KalmanBetaSeries` with the KB8.3 fields (`model`, `error_model`,
`burn_in_rows`, `training_rows`, `reestimate_every`, `dates`, `alpha`, `betas`, `band_low`,
`band_high`, `ex_ante_betas`, `vintage_index`, `vintages`, `latest`, `labels`, `warnings`);
nested `KalmanVintage` and the `latest` entry model; labels `L-KF`, `L-KBAND` (and `L-KTAIL` when
gate G1 fires) in `KALMAN_SECTION.label_text`. Warm-up values are `null`, never NaN. Keep the
payload small: one shared `dates` axis (KB10.2); if you round the series, do it as D31 does for
the rolling betas and say so in the spec. Hook `build_kalman_betas(ctx)`: `ctx.sample`, `ctx.primary_window` and
`ctx.rolling` (for the comparison sentence only). Panel `render_kalman_panel`, position 810, id
`kalman` (one row per factor, latest value, band, equivalent window; a table beside any chart);
React `KalmanPanel` (ECharts through `useEChart`, lazy chunk, as `RollingPanel` does).

**Tests.** TKB01-TKB24 in `test_kalman.py` (seeds `20261118 + 600 + NN`; statsmodels `MLEModel`
and `RecursiveLS` only in tests). In `test_section_kalman.py`: section validates and round-trips;
statuses of KB8.3 (`n = 503`, `n = 504` one stamp, singular burn-in); JSON has no NaN; every M3-M10
number bitwise identical with and without the hook (TKB23); the static panel; the fixture. In
`KalmanPanel.test.tsx`: null renders nothing, the empty state, the latest-value table. Check
`npm run size` stays within budget (the chart must stay in the lazy chunk).

**Validation focus.** Filter against statsmodels `MLEModel` (TKB02) and expanding OLS at
`lambda = 0` (TKB01); the look-ahead perturbation at a vintage boundary (TKB15); the SPY and MSTR
numbers of KB9 from the cache; run time.

---

## Brief 4: shrunk (Bayesian) betas

**Goal.** Add a second set of betas pulled toward a stated prior (market portfolio centre, spread
from Ken French portfolio cross-sections), for the full sample and the latest window, plus a power
statement per style factor. OLS stays primary everywhere; no test, tag or family on shrunk betas.

**Spec.** `docs/specs/shrunk-betas.md` (SB0-SB12; schema SB7.2; status SB7.1; tests TSB01-TSB20 in
SB11; registry entries SB12). Contract SC2.4.

**Owner decisions in force.** None recorded yet on SB10.4. Build the spec's recommendation for Q1
(option a: ship with the caveat) and keep `delta = 0.05` fixed (Q3). Q2 (four extra portfolio
files, about 13 MB zipped per vintage) needs the owner's yes before the pull request merges; build
it so that missing files give `failed / prior_unavailable` and the rest of the report is unaffected.

**May touch.** `backend/factordesk/analytics/shrinkage.py` (new),
`backend/factordesk/analytics/shrinkage_prior.py` (new), `backend/factordesk/data/portfolios.py`
(new; pure parser plus a cached download with an injected clock, HTTP client and data directory,
like `data/factors.py`), `backend/factordesk/report/sections/shrunk.py`,
`backend/factordesk/section_hooks/shrunk.py` (both `build_shrunk_betas` and
`load_shrinkage_inputs`), `backend/factordesk/report/panels/shrunk.py`,
`backend/factordesk/api/deps.py` and `backend/factordesk/api/service.py` (only to load the
portfolio frames and pass `SectionInputs` to `assemble_report`; give any new `AppDeps` field a
default so `tests/fixtures/fake_app.py` and the API tests need no change),
`backend/factordesk/tests/test_shrinkage.py`,
`test_shrinkage_prior.py`, `test_section_shrunk.py`, `test_portfolios.py` (all new),
`backend/factordesk/tests/fixtures/sections/shrunk.json`,
`frontend/src/components/report/sections/ShrunkBetasPanel.tsx` (and new `.css`, `.test.tsx`),
`docs/specs/shrunk-betas.md` (corrections only), new `docs/validation/shrunk-validation.md`, new
`wiki/decision-shrunk-betas.md`; append-only and generated files per common rules 8-9.

**Must not touch.** Everything in common rule 2, and the other three features' files, including
`ExposuresPanel.tsx` and `_exposures_panel` (the marker on the exposures row comes in the later
integration change, contract SC6 item 8). `analytics/attribution.py` must not import `shrinkage`
(TSB18). No real portfolio data in the repository (synthetic fixtures only).

**Contract hooks.** The field `shrunk_betas` is a list: `ShrunkBetas` for `scope = "full_sample"`
then `"latest_window"`. `ShrunkBetas` with the SB7.2 fields (`scope`, `window`, `hac_lags`,
`prior`, `betas`, `power`, `labels`); nested `ShrinkagePrior`, `DatasetStamp`, `ShrunkBeta`
(`factor` holds display names `Mkt-RF` ..., not `mkt_rf`, SC6 item 12), `PowerStatement`; labels
`L-SHRINK`, `L-SHRINK-PRIOR`, `L-CRED`, `L-CORR-MOVE`, `L-MDE` in `SHRUNK_SECTION.label_text`.
Hook `build_shrunk_betas(ctx)`: `ctx.regression` (OLS betas and the HAC block, TSB06),
`ctx.rolling[ctx.primary_window]` (latest window), `ctx.factor_frame` (2,520 French rows ending at
`T_end`), `ctx.inputs.shrinkage_portfolios`. `load_shrinkage_inputs(now, offline=True)` returns
`None` (tests and injected factors never download). Panel `render_shrunk_panel`, position 520, id
`shrunk` (hollow marker plus credible interval per factor, the "no visible pull" line of SB6 rule 2,
the power sentences); React `ShrunkBetasPanel`.

**Tests.** TSB01-TSB20 in `test_shrinkage.py` and `test_shrinkage_prior.py` (seeds
`20261118 + 700 + NN`); the parser cases of TSB09 and TSB11 in `test_portfolios.py` with small
synthetic files. In `test_section_shrunk.py`: both scopes validate and round-trip; statuses of
SB7.1 (inherited, `prior_unavailable`, `prior_vintage_mismatch`, `singular_covariance`,
`prior_cross_section_too_small`); OLS numbers and tags bitwise identical with and without the hook
(TSB18); the static panel; the fixture. In `ShrunkBetasPanel.test.tsx`: null renders nothing, both
scopes, the "no visible pull" line.

**Validation focus.** Posterior identities (TSB01-TSB05) recomputed by hand; the prior's
method-of-moments `tau` recomputed from the raw portfolio files with a separate parser; the SPY and
RDDT numbers of SB8; the look-ahead perturbation of the prior (TSB16).

---

## After the four merge

- The last merger regenerates the OpenAPI document and types on `dev` and runs every gate
  (contract SC8 item 3).
- One integration change (roadmap "Report redesign integration") folds the in-panel pieces of
  contract SC6 item 8 into the core panels (fragility sentence under the alpha tile, lead-lag
  column, shrunk marker, Kalman line).
- The owner folds the specs' proposed methodology sections, status value
  (`not_flipped_within_cap`) and label keys into `docs/methodology.md` (SC6 items 7, 10, 11).
