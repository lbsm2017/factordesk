# factordesk specification: schema v3 contract (optional report sections)

Status: contract, written 2026-11-18. The code that implements it lands with this document
(`feat/schema-v3-contract`): placeholders, registries and tests, no statistic.
Audience: the engineers of the five features below, who build on separate branches at the same
time; reviewers who merge them.
Companions: `docs/ROADMAP.md` ("Risks and dependencies"), `CODING_STANDARDS.md` (sections 5 and 6),
`docs/research-protocol.md`, the five feature specifications listed in section 2, and the
hand-off briefs in `docs/specs/handoff-statistical-features.md`.
Section ids: SC0-SC9.

---

## SC0. Why this exists

Five features add report sections at the same time: fragility score, lead-lag betas, Kalman betas,
shrunk betas and residual alpha analysis. If each one edited `FactorReport`, the pipeline, the HTML
renderer and the React page, every merge would conflict and every branch would break the others.
This contract fixes, before any of them starts:

1. the name and type of each new field on `FactorReport`;
2. one new file per feature for each layer (schema, analytics, pipeline hook, static panel, React
   panel, tests), so the branches touch disjoint files;
3. the shared extension points (the section base model, the pipeline hook context, the two panel
   registries), which no feature branch edits;
4. how the schema version changes and how old report files keep loading.

## SC1. Rules

1. **Optional and additive.** Every new field on `FactorReport` is optional and defaults to `None`
   (JSON `null`). `None` means "this feature did not run for this report"; it is never used for
   "ran and failed" (that is a section with `status = "failed"` and a `reason`). No existing field is
   removed, renamed or retyped.
2. **One section model per feature, in its own file.** Each feature owns exactly one top-level
   section class in its own module under `backend/factordesk/report/sections/`. Nested helper
   models of that feature (for example `FlipCount`, `TimingTest`, `KalmanVintage`) live in the same
   file. `schema.py` imports each section module with exactly one import statement and never changes
   when a feature fills its section in.
3. **Every section carries `status`, `reason` and `sample`.** The section base class
   `SectionModel` (`backend/factordesk/report/base.py`) holds the three fields of
   `CODING_STANDARDS.md` section 5: `status` (M0.7 values: `ok`, `insufficient_data`,
   `not_applicable`, `failed`), `reason` (required exactly when `status != "ok"`) and
   `sample: SampleInfo`. A section whose status is not `ok` carries no float, except inside a
   nested object that has its own `status` field (that object is governed by its own status; see
   SC6 item 6). NaN and infinity are rejected, as everywhere in the schema.
4. **Nested statistics.** A nested model that is a full statistic in the M14 sense subclasses
   `StatisticModel` (status, reason, sample, labels, caption) and is listed in its section's
   `statistic_models`, so it joins `schema.STATISTIC_MODELS` and test T105 covers it.
5. **Labels stay with the section.** A feature's own footnote keys (for example `L-FRAGILITY`,
   `L-KF`) and their texts go into its section module's `label_text`. `schema.LabelKey` and
   `schema.LABEL_TEXT` are not edited. The pipeline adds a section's texts to the report's
   `label_text` only when that section is present (`schema.report_label_text`), so a report without
   new sections keeps exactly today's `label_text`. Section models type their `labels` field with
   their own `Literal` of keys. Section keys must not repeat a key of `LABEL_TEXT` or of another
   section (a test checks this).
6. **Field naming.** Display factor names (`FACTOR_NAMES`: `Mkt-RF`, `SMB`, `HML`, `RMW`, `CMA`)
   in every API field, as the existing schema does (`CODING_STANDARDS.md` section 1: column codes
   such as `mkt_rf` stay inside the backend). Annualised API fields end in `_annual`, adjusted R²
   is `adj_r2`, as in the existing schema. Where a spec says otherwise, SC6 lists the change.
7. **Panels are registered, not listed.** Each feature has one static panel module and one React
   component, each already registered at a fixed position (SC4). Adding or filling a panel never
   edits `render_report_html`, `ReportView.tsx` or another panel. An absent section renders
   nothing in both renderers.
8. **No feature changes a headline number.** Every spec already says so (LLD6, KD8, SD3, FRD6,
   RD2); the contract adds that no section hook may change the core sections passed to it.

## SC2. The five sections

All paths are relative to the repository root. "Placeholder" is what this contract ships: the
class exists with only `status`, `reason` and `sample`; the feature replaces the body with the
fields of its spec.

### SC2.1 Fragility score

| Item | Value |
|---|---|
| Spec | `docs/specs/fragility-score.md` (FR9.2 schema, FR9.1 status) |
| `FactorReport` field | `fragility: FragilitySection \| None = None` |
| Section module | `backend/factordesk/report/sections/fragility.py`, exports `FragilitySection` and `FRAGILITY_SECTION` |
| Section fields (FR9.2) | `status`, `reason`, `sample`, `algorithm_version`, `k_max`, `alpha: FlipCount`, `betas: list[FlipCount]` (5, canonical order), `leave_one_year_out: LoyoTable`, `influence: InfluenceLists`, `labels` (`["L-DESC", "L-FRAGILITY"]`) |
| Nested models (same file) | `FlipCount`, `RemovedDay`, `LoyoTable`, `LoyoRow`, `InfluenceLists`, `InfluentialDay`, fields exactly as FR9.2 except SC6 items 7 and 12 |
| Status values | Section: M0.7 values; `ok` when M3.1 is `ok`. `FlipCount.status`: `ok`, `not_applicable` (tag noise), `not_flipped_within_cap`, `failed` (its own `Literal`, FR9.1). `LoyoTable.status`: `ok`, `insufficient_data` (fewer than 3 years). |
| Analytics | `backend/factordesk/analytics/fragility.py` |
| Pipeline hook | `backend/factordesk/section_hooks/fragility.py`, `build_fragility(ctx: SectionContext) -> FragilitySection \| None` |
| Static panel | `backend/factordesk/report/panels/fragility.py`, `render_fragility_panel(report) -> str \| None`, name `fragility`, position 530, element id `fragility` |
| React panel | `frontend/src/components/report/sections/FragilityPanel.tsx`, component `FragilityPanel` |
| Tests | `backend/factordesk/tests/test_fragility.py` (TFR01-TFR22), `backend/factordesk/tests/test_section_fragility.py` (schema, hook, static panel), `frontend/src/components/report/sections/FragilityPanel.test.tsx` |
| Fixture | `backend/factordesk/tests/fixtures/sections/fragility.json` (one section object) |

### SC2.2 Lead-lag (Dimson / Scholes-Williams) betas

| Item | Value |
|---|---|
| Spec | `docs/specs/lead-lag-betas.md` (LL6.6 schema, LL6.4 status) |
| `FactorReport` field | `lead_lag: LeadLagSection \| None = None` |
| Section module | `backend/factordesk/report/sections/lead_lag.py`, exports `LeadLagSection` and `LEAD_LAG_SECTION` |
| Section fields (LL6.6) | `status`, `reason`, `sample`, `trigger` (`{gate, timing_test}`), `gate_ref`, `hac_lags`, `n_params`, `timing_test: TimingTest`, `betas: list[LeadLagBeta] \| None`, `alpha: LeadLagAlpha \| None`, `r2`, `adj_r2`, `resid_rho1`, `resid_rho1_z`, `resid_vr5`, `resid_rho1_daily`, `resid_vr5_daily`, `joint_wald`, `sw_crosscheck: SWCrossCheck \| None`, `sentences`, `labels` (`["L-DESC", "L-LEADLAG"]`) |
| Nested models (same file) | `LeadLagTrigger`, `TimingTest` (+ per-factor row), `LeadLagBeta` (+ coefficient `{est, se, z, p}` model), `LeadLagAlpha`, `JointWald`, `SWCrossCheck` |
| Status values | LL6.4: `not_applicable` (neither trigger), `insufficient_data` (`n_LL < 500`), `failed` (design guard), `ok`. `TimingTest.status`: same values; F11 is filled whenever `n_LL >= 500`, whatever the section status (SC6 item 6). |
| Analytics | `backend/factordesk/analytics/lead_lag.py` |
| Pipeline hook | `backend/factordesk/section_hooks/lead_lag.py`, `build_lead_lag(ctx) -> LeadLagSection \| None` |
| Static panel | `backend/factordesk/report/panels/lead_lag.py`, `render_lead_lag_panel(report)`, name `lead_lag`, position 510, element id `lead-lag` |
| React panel | `frontend/src/components/report/sections/LeadLagPanel.tsx`, component `LeadLagPanel` |
| Tests | `backend/factordesk/tests/test_lead_lag.py` (TLL01-TLL20), `backend/factordesk/tests/test_section_lead_lag.py`, `frontend/src/components/report/sections/LeadLagPanel.test.tsx` |
| Fixture | `backend/factordesk/tests/fixtures/sections/lead_lag.json` |

The exclusion reason `lead_after_sample_end` (LL2.2) is already in `ExclusionReason`, so the
section's `SampleInfo` can list the removed row.

### SC2.3 Kalman-filter betas

| Item | Value |
|---|---|
| Spec | `docs/specs/kalman-betas.md` (KB8.3 outputs, status, schema) |
| `FactorReport` field | `kalman_betas: KalmanBetaSeries \| None = None` |
| Section module | `backend/factordesk/report/sections/kalman.py`, exports `KalmanBetaSeries` and `KALMAN_SECTION` |
| Section fields (KB8.3) | `status`, `reason`, `sample`, `model`, `error_model`, `burn_in_rows`, `training_rows`, `reestimate_every`, `dates`, `alpha`, `betas`, `band_low`, `band_high`, `ex_ante_betas`, `vintage_index`, `vintages: list[KalmanVintage]`, `latest`, `labels`, `warnings`; plus `retrospective: KalmanRetrospective \| None` only if the owner ships the smoothed view (KB10.4 Q4) |
| Nested models (same file) | `KalmanVintage`, the `latest` entry model, `KalmanRetrospective` (if shipped) |
| Status values | KB8.3: `insufficient_data` (`n < 504`), `failed` (reason `singular_burn_in`), `ok` (with warning `kalman_lambda_at_upper_bound` when a vintage hits the grid edge) |
| Analytics | `backend/factordesk/analytics/kalman.py` |
| Pipeline hook | `backend/factordesk/section_hooks/kalman.py`, `build_kalman_betas(ctx) -> KalmanBetaSeries \| None` |
| Static panel | `backend/factordesk/report/panels/kalman.py`, `render_kalman_panel(report)`, name `kalman`, position 810, element id `kalman` |
| React panel | `frontend/src/components/report/sections/KalmanPanel.tsx`, component `KalmanPanel` |
| Tests | `backend/factordesk/tests/test_kalman.py` (TKB01-TKB24), `backend/factordesk/tests/test_section_kalman.py`, `frontend/src/components/report/sections/KalmanPanel.test.tsx` |
| Fixture | `backend/factordesk/tests/fixtures/sections/kalman.json` |

### SC2.4 Shrunk (Bayesian) betas

| Item | Value |
|---|---|
| Spec | `docs/specs/shrunk-betas.md` (SB7.2 schema, SB7.1 status) |
| `FactorReport` field | `shrunk_betas: list[ShrunkBetas] \| None = None` (one entry per scope, `full_sample` then `latest_window`; SC6 item 5) |
| Section module | `backend/factordesk/report/sections/shrunk.py`, exports `ShrunkBetas` and `SHRUNK_SECTION` |
| Section fields (SB7.2) | `status`, `reason`, `sample`, `scope`, `window`, `hac_lags`, `prior: ShrinkagePrior \| None`, `betas: list[ShrunkBeta]`, `power: list[PowerStatement]`, `labels` |
| Nested models (same file) | `ShrinkagePrior`, `DatasetStamp`, `ShrunkBeta`, `PowerStatement` |
| Status values | SB7.1: inherited from the underlying regression; `failed` (`prior_unavailable`, `prior_vintage_mismatch`, `singular_covariance`); `insufficient_data` (`prior_cross_section_too_small`); `ok` |
| Analytics | `backend/factordesk/analytics/shrinkage.py` and `backend/factordesk/analytics/shrinkage_prior.py`; the portfolio-file parser in `backend/factordesk/data/portfolios.py` |
| Pipeline hook | `backend/factordesk/section_hooks/shrunk.py`, `build_shrunk_betas(ctx) -> list[ShrunkBetas] \| None`, and `load_shrinkage_inputs(now, *, offline)` for the portfolio files (SC3) |
| Static panel | `backend/factordesk/report/panels/shrunk.py`, `render_shrunk_panel(report)`, name `shrunk`, position 520, element id `shrunk` |
| React panel | `frontend/src/components/report/sections/ShrunkBetasPanel.tsx`, component `ShrunkBetasPanel` |
| Tests | `backend/factordesk/tests/test_shrinkage.py` and `test_shrinkage_prior.py` (TSB01-TSB20), `backend/factordesk/tests/test_section_shrunk.py`, `frontend/src/components/report/sections/ShrunkBetasPanel.test.tsx` |
| Fixture | `backend/factordesk/tests/fixtures/sections/shrunk.json` (a list of two section objects) |

### SC2.5 Residual alpha analysis

| Item | Value |
|---|---|
| Spec | `docs/methodology-residual-analysis.md` (R7 schema, R8 panel), oracle `docs/test-oracle-residual-analysis.md` |
| `FactorReport` field | `residual: ResidualAnalysis \| None = None` |
| Section module | `backend/factordesk/report/sections/residual_alpha.py`, exports `ResidualAnalysis` and `RESIDUAL_ALPHA_SECTION` |
| Section fields (R7.8) | `status`, `reason`, `sample` (contract base, SC6 item 3), then `question`, `beta_window`, `in_sample`, `point_in_time`, `gap`, `chart`, `rolling_alpha`, `non_overlapping`, `split_half`, `calendar_years`, `diagnostics`, `caveats`, `warnings` |
| Nested models (same file) | `ResidualStats`, `ResidualChart`, `ResidualGap`, `RollingResidualAlpha`, `AlphaWindow`, `NonOverlappingAlpha`, `SplitHalfAlpha`, `ResidualYear`, `ResidualYears`, `ResidualAlphaDiagnostics` (R7.7's `ResidualDiagnostics`, renamed: SC6 item 4); type aliases `ResidualBasis`, `GapVerdict`; label keys `L-INSAMPLE`, `L-PIT`, `L-DESC-PIT`, `L-HEDGE` in the module's `label_text` |
| Statistic models | The eight `StatisticModel` subclasses of R7.8 go into `RESIDUAL_ALPHA_SECTION.statistic_models` |
| Status values | Section: `ok` when M3.1 is `ok`, `failed` with "Residual analysis is unavailable because the regression could not be computed." otherwise (R8.4). Nested statistics follow R3.6 and R7. |
| Analytics | `backend/factordesk/analytics/residual.py`, `backend/factordesk/analytics/residual_stability.py` |
| Pipeline hook | `backend/factordesk/section_hooks/residual_alpha.py`, `build_residual_analysis(ctx) -> ResidualAnalysis \| None` |
| Static panel | `backend/factordesk/report/panels/residual_alpha.py`, `render_residual_alpha_panel(report)`, name `residual_alpha`, position 710, element id `residual` |
| React panel | `frontend/src/components/report/sections/ResidualAlphaPanel.tsx`, component `ResidualAlphaPanel` |
| Tests | `backend/factordesk/tests/test_residual.py`, `backend/factordesk/tests/test_residual_stability.py` (TR01-TR40), `backend/factordesk/tests/test_section_residual_alpha.py`, `frontend/src/components/report/sections/ResidualAlphaPanel.test.tsx` |
| Fixture | `backend/factordesk/tests/fixtures/sections/residual_alpha.json` |

## SC3. Shared extension points (fixed by this contract; feature branches do not edit them)

### SC3.1 Schema

- `backend/factordesk/report/base.py`: the primitives every section needs, moved out of
  `schema.py` without change (`FrozenModel`, `StatisticModel`, `SampleInfo`, `ExcludedRow`,
  `FactorVintage`, `Status`, `Tag`, `Severity`, `ExclusionReason`, `LabelKey`, `LABEL_TEXT`,
  `FACTOR_NAMES`, `ReportWarning`), plus `SectionModel` (SC1 item 3) and `SectionSpec`.
  `schema.py` re-exports every moved name, so existing imports keep working.
- `SectionSpec` (frozen dataclass), one per section module:
  `field` (the `FactorReport` field name), `model` (the section class), `many` (true only for
  `shrunk_betas`), `statistic_models` (nested `StatisticModel` classes), `label_text` (the
  section's own footnote keys and texts).
- `schema.SECTIONS`: the five specs in panel order. `schema.STATISTIC_MODELS` = the eight core
  statistics plus every section's `statistic_models`. `schema.report_label_text(present)` returns
  `LABEL_TEXT` plus the texts of the sections whose field is not `None`.

### SC3.2 Pipeline hook

- `backend/factordesk/section_hooks/context.py`:
  - `SectionContext` (frozen dataclass), built once in `assemble_report` after every core section:
    `ticker`, `now`, `history` (prices after duplicate dates are collapsed), `factor_frame` (the
    whole French frame, for the French calendar of LL2.2), `sample` (`AnalysisSample`, M2),
    `vintage`, `audit` (`AuditReport`), `daily` (M3.1 fit before the gate), `regression` (after the
    gate, M3.6), `diagnostics`, `gate`, `five_day` (`MultiDayFit | None`), `rolling` (window ->
    `RollingBetas`, including the primary window), `primary_window`, `core` (the finished core
    sections: `regression`, `rolling`, `average_beta`, `return_contribution`, `risk_contribution`,
    `residual_diagnostics`, `quality_gate`, `five_day_regression`), `inputs` (`SectionInputs`), and
    the method `sample_info(window)` (the `SampleInfo` of the analysis sample, with `window`).
  - `SectionInputs` (frozen dataclass): data a section needs that `assemble_report` does not
    already have. One field today: `shrinkage_portfolios: Mapping[str, pd.DataFrame] | None`
    (owned by the shrunk feature).
- `backend/factordesk/section_hooks/__init__.py`: `load_section_inputs(now, *, offline)`, which
  `build_report` calls; it delegates to `section_hooks/shrunk.py`.
- `assemble_report(..., section_inputs=None)` and `build_report(..., section_inputs=None)` pass the
  inputs through. `assemble_report` calls the five hooks in panel order and sets the report's
  `label_text` with `report_label_text`. Each hook returns its section or `None`, must not raise
  for data reasons (it returns `status = "failed"` with a reason instead, CODING_STANDARDS section
  8), and must not mutate the context.
- This contract ships each hook returning `None`, so reports are unchanged apart from the five
  `null` fields and the version (SC5).

### SC3.3 Static renderer

- `backend/factordesk/report/panel_registry.py`: `PanelSpec(name, position, render, css)`,
  `register_panel(name, position, render, *, css="")` and `registered_panels()` (ordered by
  position; it imports `factordesk.report.panels` once, which registers the five feature panels).
  A render function returns HTML, or `None` when its section is absent; `None` adds nothing to the
  page. A panel's `css` (empty by default) is appended to the inline stylesheet.
- `render_report_html` iterates `registered_panels()` between `<main>` and `</main>`; the core
  panels register themselves in `render_html.py`.
- Helpers for panel modules are public in `render_html.py`: `esc`, `panel_head`, `panel_section`,
  `empty_state`, `footnote`, `fmt_num`, `fmt_signed`, `fmt_pct`, `fmt_tstat`, `fmt_pval`,
  `date_long`, `label_texts`.

### SC3.4 React

- `frontend/src/components/report/panelRegistry.ts`: `PanelHostProps` (`report`, `downloadHref`,
  `win`, `onWinChange`), `PanelEntry` (`name`, `position`, `Component`), `PANELS` and
  `orderedPanels()`. `ReportView.tsx` renders `orderedPanels()` in order. A feature component
  returns `null` when its field is `null`.
- `frontend/src/api/types.ts` already exports the five section types (`FragilitySection`,
  `LeadLagSection`, `KalmanBetaSeries`, `ShrunkBetas`, `ResidualAnalysis`). Nested types are read
  in the feature's own files as `components["schemas"]["FlipCount"]` from `../../../api/types.gen`.
- `frontend/src/test/sectionFixtures.ts`: `withSection(report, field)` attaches the feature's JSON
  fixture (`@fixtures/sections/<file>.json`) to a copy of the mock report.
- CSS: a feature's styles go in its own file next to the component
  (`sections/FragilityPanel.css`), imported by the component. Colours only through the existing
  tokens of `src/styles/tokens.css` (a test forbids colour literals elsewhere). A feature that needs
  a new token asks in its pull request; it does not edit `tokens.css` on its branch.

## SC4. Panel order

The same names and positions in both renderers (React has one extra entry, `notice`, at 150,
because the static page draws the notice inside the header). Element ids of the core panels are
as they were; the five new panels use the same id in both renderers.

| Position | Name | Element id (static / React) | Source |
|---|---|---|---|
| 100 | `header` | masthead, no id / `header` | core |
| 150 | `notice` | inside the header / `notice` | core, React only |
| 200 | `equation` | no id / `equation` | core |
| 300 | `kpis` | no id / `kpis` | core |
| 400 | `price` | `price` | core |
| 500 | `exposures` | `exposures` | core |
| 510 | `lead_lag` | `lead-lag` | lead-lag |
| 520 | `shrunk` | `shrunk` | shrunk betas |
| 530 | `fragility` | `fragility` | fragility |
| 600 | `returns` | `returns` | core |
| 700 | `risk` | `risk` | core |
| 710 | `residual_alpha` | `residual` | residual alpha |
| 800 | `rolling` | `rolling` | core |
| 810 | `kalman` | `kalman` | Kalman betas |
| 900 | `data` | `data` | core |
| 1000 | `regression_detail` | `detail` / `regression-detail` | core |
| 1100 | `colophon` | footer, no id / `colophon` | core |

Reasons: lead-lag, shrunk and fragility qualify the betas and the alpha shown in the exposures
panel, so they follow it; the residual panel belongs after return and risk contribution (R8); the
Kalman line is read against the rolling betas (KB0.1). Positions between the numbers are free for
later panels.

## SC5. Schema version

- **What "v3 contract" means.** `docs/ROADMAP.md` calls this work the schema v3 contract. The
  payload number `"3"` was already taken: `SCHEMA_VERSION = "3"` added `residual_diagnostics`,
  `quality_gate` and `five_day_regression` (M3.5, M3.6) in the first commit. So the contract ships
  as **`SCHEMA_VERSION = "4"`**: version 3 plus the five optional section fields (and the exclusion
  reason `lead_after_sample_end`). Reports written before this change say `"3"`.
- **Reading old files.** `SUPPORTED_SCHEMA_VERSIONS = ("3", "4")`. A version 3 file loads
  unchanged: the five fields are absent and become `None`, and the object keeps
  `schema_version = "3"`, so the colophon still says which version wrote it. A file with any other
  version is refused with a message that names the supported versions. No version 2 file exists:
  the repository's first commit already wrote version 3.
- **When the number changes.** Only for a change an older reader cannot absorb: a field removed,
  renamed or retyped, a new required field, or a changed meaning. Each bump adds the old number to
  `SUPPORTED_SCHEMA_VERSIONS` only if a migration in `schema.py` maps it to the new shape, with a
  test on a committed old fixture.
- **Feature branches do not bump.** Filling a section in is additive for every file in
  circulation: the hooks of this contract return `None`, so no version 4 file contains a
  placeholder body, and a version 4 file written before a feature merged has `null` there.

## SC6. Where this contract departs from the feature specifications

1. **Version number** (SC5): the residual spec says `SCHEMA_VERSION` "becomes 3" (R7.8, P7), the
   dashboard spec says it "stays 3" and quotes "schema v3" in the colophon (DB1, DB5). It is `"4"`.
2. **Optional, not always present.** LL6.6 says `lead_lag` is "always present"; R7.8 makes
   `residual` required. Both are `None` by default (SC1 item 1); once the features ship, their hooks
   fill them on every report, so in practice they are always present in new reports.
3. **Residual container status.** R7.8's `ResidualAnalysis` is a plain container. Under the
   contract it subclasses `SectionModel`, so it also has `status`, `reason` and `sample` (`S`,
   window `None`). That lets both renderers draw R8.4's "regression failed" state from one field.
4. **Name collision.** R7.7 defines a new `ResidualDiagnostics`, but `schema.ResidualDiagnostics`
   is already the M3.5 model. The residual feature's class is `ResidualAlphaDiagnostics`.
5. **Two shrunk scopes.** SB7.2 defines one model with `scope` in `full_sample` and
   `latest_window` (SD7). The field is a list, like `rolling`.
6. **Numbers under a non-ok status.** LL6.6 fills F11 (`timing_test`) even when the section is
   `not_applicable`, and FR9.1 fills numbers for `not_flipped_within_cap`. M0.7 says a statistic
   that is not `ok` carries no numbers. Rule: the check applies to each object with a `status`
   field separately; a nested object with its own `status` is checked against that status, not the
   section's.
7. **New status value.** FR9.1 proposes `not_flipped_within_cap` for M0.7 (FR11.2, owner's
   choice). It is a value of `FlipCount.status` only, declared in `sections/fragility.py`; the
   shared `Status` is not changed.
8. **Panels inside core panels.** FR6.1 puts a sentence under the alpha tile and in beta tooltips,
   LL6.2 a third column beside the daily betas, SB6 a marker on the exposures row, KB0.1 a line on
   the rolling chart. Each of those edits a core panel that all branches share. In this contract
   each feature ships its own panel (SC4); folding them into the core panels is one follow-up
   change after all four merge (the "Report redesign integration" roadmap item).
9. **Schema location.** Every spec says "`report/schema.py`"; the models go into
   `report/sections/<feature>.py` instead (SC1 item 2).
10. **Labels.** The specs add keys to M0.9 / `LabelKey` (FR6.4, LL9.1, KB8.3, SB6, R7.1). They go
    into each section's `label_text` (SC1 item 5); folding them into M0.9 is the owner's call.
11. **`methodology.md`.** `CODING_STANDARDS.md` section 6 asks for a methodology section in the
    same change as a new statistic; every spec instead leaves its proposed methodology text to the
    owner (FR11.2, LL10.3, KB10.3, SB10.3, R9.2). Four branches editing one file in parallel would
    conflict. Feature branches do not edit `docs/methodology.md`; their spec stands in for the
    section until the owner folds the proposals in. This needs the owner's agreement.
12. **Factor names and suffixes.** SB7.2 types `factor` as `mkt_rf` ... codes; FR9.2 says "factor
    code"; the API uses display names (SC1 item 6), so these fields hold `Mkt-RF` and so on. FR9.2
    (`LoyoRow.alpha_ann`, `se_ann`) and LL6.6 (`alpha_ann`, `se_ann`, `ci95_ann`, `edge_term_ann`,
    `r2_adj`) become `alpha_annual`, `se_annual`, `ci95_annual`, `edge_term_annual`, `adj_r2`,
    matching the existing schema and R7 (residual P11 notes the same split).

## SC7. File ownership

A feature branch edits only the files of its own row, plus new files under its own names
(`docs/validation/<feature>-validation.md`, `wiki/decision-<feature>.md`). The generated files
and the append-only files of the last two rows are shared under the rules given there.

| Owner | Files |
|---|---|
| fragility | `analytics/fragility.py`, `report/sections/fragility.py`, `section_hooks/fragility.py`, `report/panels/fragility.py`, `tests/test_fragility.py`, `tests/test_section_fragility.py`, `tests/fixtures/sections/fragility.json`, `frontend/src/components/report/sections/FragilityPanel.{tsx,css,test.tsx}`, `docs/specs/fragility-score.md` |
| lead-lag | `analytics/lead_lag.py`, `report/sections/lead_lag.py`, `section_hooks/lead_lag.py`, `report/panels/lead_lag.py`, `tests/test_lead_lag.py`, `tests/test_section_lead_lag.py`, `tests/fixtures/sections/lead_lag.json`, `tests/test_lookahead.py` (only the T104 allowlist of LL5.3, if the owner grants it), `frontend/.../sections/LeadLagPanel.{tsx,css,test.tsx}`, `docs/specs/lead-lag-betas.md` |
| Kalman | `analytics/kalman.py`, `report/sections/kalman.py`, `section_hooks/kalman.py`, `report/panels/kalman.py`, `tests/test_kalman.py`, `tests/test_section_kalman.py`, `tests/fixtures/sections/kalman.json`, `frontend/.../sections/KalmanPanel.{tsx,css,test.tsx}`, `docs/specs/kalman-betas.md` |
| shrunk | `analytics/shrinkage.py`, `analytics/shrinkage_prior.py`, `data/portfolios.py`, `report/sections/shrunk.py`, `section_hooks/shrunk.py`, `report/panels/shrunk.py`, `tests/test_shrinkage.py`, `tests/test_shrinkage_prior.py`, `tests/test_section_shrunk.py`, `tests/fixtures/sections/shrunk.json`, `api/deps.py` and `api/service.py` (only to pass `SectionInputs` from the dashboard), `frontend/.../sections/ShrunkBetasPanel.{tsx,css,test.tsx}`, `docs/specs/shrunk-betas.md` |
| residual alpha | `analytics/residual.py`, `analytics/residual_stability.py`, `report/sections/residual_alpha.py`, `section_hooks/residual_alpha.py`, `report/panels/residual_alpha.py`, `tests/test_residual.py`, `tests/test_residual_stability.py`, `tests/test_section_residual_alpha.py`, `tests/fixtures/sections/residual_alpha.json`, `frontend/.../sections/ResidualAlphaPanel.{tsx,css,test.tsx}`, `docs/methodology-residual-analysis.md`, `docs/test-oracle-residual-analysis.md` |
| nobody (contract) | `report/schema.py`, `report/base.py`, `report/render_html.py`, `report/report.css`, `report/panel_registry.py`, `report/panels/__init__.py`, `section_hooks/context.py`, `section_hooks/__init__.py`, `pipeline.py`, `tests/fixtures/mock_report.json`, `tests/fixtures/mock_report_v3.json`, `tests/fixtures/sections/__init__.py`, `tests/test_report.py`, `tests/test_schema_contract.py`, `tests/test_panel_registry.py`, `frontend/src/components/report/ReportView.tsx`, `panelRegistry.ts`, `Panel.tsx`, `EmptyState.tsx`, every core panel, `frontend/src/api/types.ts`, `frontend/src/test/fixture.ts`, `frontend/src/test/sectionFixtures.ts`, `frontend/src/styles/*`, `docs/methodology.md`, `docs/ROADMAP.md`, `README.md`, `CONTRIBUTING.md`, `CODING_STANDARDS.md` |
| generated (everyone regenerates, nobody hand-edits) | `frontend/src/api/openapi.json`, `frontend/src/api/types.gen.ts` (SC8) |
| append-only (everyone appends; on a conflict keep both sides) | `docs/registry/tests.jsonl`, `wiki/index.md`, `wiki/log.md` |

Backend paths in the table are under `backend/factordesk/`. If a feature finds it needs a change in
a "nobody" file, it stops and asks; the change goes through a separate pull request to `dev` that
all branches then merge.

## SC8. OpenAPI document and generated types

1. Every branch that changes its section model regenerates both files before committing, from the
   repository root:
   `uv run python -m factordesk.api.openapi_dump frontend/src/api/openapi.json`, then
   `npm --prefix frontend run gen:types`. `test_openapi_is_current` and the CI step
   `git diff --exit-code frontend/src/api` fail otherwise.
2. When merging, a conflict in either file is never resolved by hand: take either side, rerun the
   two commands, and commit the result.
3. **The last merger** (whoever merges the last of the five branches into `dev`) reruns the two
   commands on `dev` after the merge, runs every gate, and commits the regenerated files if they
   changed. Until then each intermediate `dev` state is regenerated by the merger of that branch.

## SC9. What the contract's tests prove

- `backend/factordesk/tests/test_schema_contract.py`: the five fields exist, default to `None`, are
  serialised as `null`, and have the types of SC2; `SECTIONS` matches the fields; a version 3 file
  (`fixtures/mock_report_v3.json`, a frozen copy of the mock report before this change) loads with
  the sections `None` and `schema_version = "3"`; an unknown version is refused; the mock fixture
  round-trips; every placeholder fixture under `fixtures/sections/` validates and attaches to the
  mock report; the section status rules (SC1 item 3, SC6 item 6); section label keys are unique;
  the pipeline leaves all five fields `None`.
- `backend/factordesk/tests/test_panel_registry.py`: the registry order of SC4, duplicate names or
  positions are refused, absent sections render nothing, a present placeholder renders its frame.
- `test_openapi_is_current` (existing) covers the regenerated OpenAPI document.
- The existing renderer and React tests, plus a before/after comparison on the mock fixture, show
  that the core panels render byte for byte (static) and node for node (React) as before.
- `frontend/src/components/report/panelRegistry.test.tsx`: the order of SC4 and that an absent
  section renders nothing.
