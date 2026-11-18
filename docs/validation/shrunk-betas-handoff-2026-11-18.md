# Shrunk betas: hand-off to independent validation

Date: 2026-11-18. Branch `feat/shrunk-betas`, code as of commit `b1331d8` (the registry commit `3cdb31d` follows it and changes no code).
Spec: `docs/specs/shrunk-betas.md` (sections SB0 to SB12). Contract: `docs/specs/schema-v3-contract.md`. Owner decision of 2026-11-18 on the portfolio download: SB10.4 question 2.
Audience: the independent validator (next step), and the owner for the open decisions in section 6.

The validator recomputes the numbers in section 7 from the spec and the cached files **without reading the implementation**. Section 7 is written so that it can be done from this page and the spec alone.

---

## 1. What was built

| Layer | File | What it holds |
| --- | --- | --- |
| Maths | `backend/factordesk/analytics/shrinkage.py` | `posterior` (V_post, b_post, S_w, pull, credible interval, `moved_away`), `window_fit` (OLS with HAC on the last W rows), power: `mde`, `rows_required`, `extra_years`, `power_text`, `power_statements`; constants `K80`, `DELTA`, `PULL_DISPLAY_THRESHOLD`; `display_pull` and `any_visible_pull` |
| Prior | `backend/factordesk/analytics/shrinkage_prior.py` | `estimate_prior` (method of moments per cross-section, max rule, floor), `usable_columns`, `fit_portfolios`, `raw_tau_squared`, `combine_tau`, `window_dates`; returns `PriorEstimate` or `PriorFailure` (never raises for data reasons) |
| Data | `backend/factordesk/data/portfolios.py` | Parser of the four Ken French portfolio files (value-weighted block only, Latin-1, `-99.99` and `-999` become missing), cache with SHA-256 and CRSP stamp, staleness policy, `If-Modified-Since`, sequential downloads, `load_portfolio_frames`, `refresh_portfolio_frames` |
| Schema | `backend/factordesk/report/sections/shrunk.py` | `ShrunkBetas`, `ShrunkBeta`, `PowerStatement`, `ShrinkagePrior`, `DatasetStamp`, label texts; status rules (numbers are `null` unless `ok`) |
| Pipeline | `backend/factordesk/section_hooks/shrunk.py` | `build_shrunk_betas` (two scopes: `full_sample`, `latest_window`), `load_shrinkage_inputs`, `refresh_shrinkage_inputs`, `vintage_problem` |
| Wiring | `api/deps.py`, `api/runtime.py`, `api/service.py`, `cli.py` | The dashboard passes the portfolio frames to the report; `factordesk factors refresh` and `POST /api/factors/refresh` refresh the four files after the factor file |
| Static panel | `backend/factordesk/report/panels/shrunk.py` | Tables per scope, power statements, "How this is computed" |
| React panel | `frontend/src/components/report/sections/ShrunkBetasPanel.tsx` (+ `.css`) | The same content with the OLS bar and the hollow diamond |
| Types | `frontend/src/api/openapi.json`, `types.gen.ts` | Regenerated for the section |

Statuses the section can take (SB7.1), per scope: `ok`; `insufficient_data` (fewer rows than the window, or `prior_cross_section_too_small`: under 40 usable portfolios or under 2520 factor rows); `failed` with `prior_unavailable` (a portfolio file is missing), `prior_vintage_mismatch` (different CRSP stamps, or a portfolio file ending on another date than the factor file) or `singular_covariance` (condition number of V above 1e12); a status inherited from the underlying regression. When the pipeline is given no portfolio inputs (injected factors, or the loader told to stay offline) the feature did not run and the field is `null`.

OLS betas, tags, attribution, risk, dominance and drift are untouched (TSB18 checks this, including a static check that nothing outside the feature imports `shrinkage`).

## 2. Tests and ids

All run on this branch at `b1331d8`.

| Spec id | Test (file) | Marker |
| --- | --- | --- |
| TSB01 flat prior, TSB02 dogmatic, TSB03 weight identities, TSB04 scalar and diagonal hand examples, TSB05 move away (three cases), TSB06 HAC block and latest-window lag rule, TSB10 MDE and sentences | `test_shrinkage.py` | default |
| TSB12 and TSB13 prior correct, TSB14 prior too tight, TSB15 HAC against OLS covariance | `test_shrinkage.py` | `slow` |
| TSB07 method of moments, TSB08 max rule and floor, TSB09 missing portfolios, TSB16 rows after `T_end`, TSB17 truncation | `test_shrinkage_prior.py` | default |
| TSB20 live smoke (real files parse, SPY barely moves) | `test_shrinkage_prior.py` | `live` |
| TSB09 parser part, TSB11 block parsing, cache, staleness, refresh, vintage re-download, CLI and API refresh | `test_portfolios.py` | default |
| TSB18 OLS untouched, TSB19 statuses and schema, hand recomputation of the posterior in the section, loader behaviour, dashboard wiring | `test_section_shrunk.py` | default |
| Section model, fixture, status rules, version-3 files cannot hold the section | `test_section_shrunk.py` | default |
| Static panel: numbers, markers, threshold, power list, moved-away rule, wording, escaping, no colour-only mark | `test_panel_shrunk.py` | default |
| React panel: the same cases | `ShrunkBetasPanel.test.tsx` | vitest |
| Panel order and placeholder handling, pipeline leaves unbuilt sections absent | `test_panel_registry.py`, `test_schema_contract.py`, `panelRegistry.test.tsx` | default |

Notes on the spec's test list. TSB05: the spec's first draft had `b = (0.5, 0.5)`; the implementation corrected it to opposite signs (spec edited in commit `82609ef`). TSB20 is the live smoke; it ran with the network on 2026-11-18 and passed.

Gate results at this hand-off are in section 8.

Registry lines of the implementation runs (`docs/registry/tests.jsonl`, status `run`, code version `b1331d8`):

| test_id | hypothesis | What |
| --- | --- | --- |
| T-20261118-830 | H-801 | Prior estimated by the implementation from the cached files (tau and portfolio counts) |
| T-20261118-831 | H-803 | SPY full sample |
| T-20261118-832 | H-803 | SPY latest 252-row window (the report's second scope) |
| T-20261118-833 | H-803 | SPY last 504 rows (computed with the library functions, checked against statsmodels) |
| T-20261118-834 | H-801S | TSB12 and TSB13 |
| T-20261118-835 | H-801S | TSB14 |
| T-20261118-836 | H-801S | TSB15 |
| T-20261118-837 | H-803 | TSB20 (live) |

## 3. Real numbers from the live run (SPY, 2026-11-18, cached files)

Command: `uv run factordesk report SPY --json` in this worktree, from the cached files below (no network needed; the SPY price file is dated 2026-11-18).

### 3.1 The prior

Window: the 2520 French rows ending 2026-09-30, from 2016-09-21 (`window_rows` 2520). Centre `m0 = (1, 0, 0, 0, 0)`. Portfolios: 49 industry and 75 size-characteristic (25 + 25 + 25), none dropped for missing values.

| Tau | Mkt-RF | SMB | HML | RMW | CMA |
| --- | --- | --- | --- | --- | --- |
| A, 49 industries | 0.209349 | 0.407894 | 0.341372 | 0.280467 | 0.253599 |
| B, 75 size-characteristic | 0.063014 | 0.764220 | 0.328910 | 0.328693 | 0.220502 |
| Default `tau = max(A, B, 0.05)` | **0.209349** | **0.764220** | **0.341372** | **0.328693** | **0.253599** |

These equal the SB2.2 table to the printed digits (0.209, 0.764, 0.341, 0.329, 0.254). Vintage: all five files CRSP stamp `202609`, last date 2026-09-30, `Last-Modified` 2026-10-27.

### 3.2 The three regressions

n = 8474 rows, 1993-02-01 to 2026-09-30, no excluded rows. Beta order: Mkt-RF, SMB, HML, RMW, CMA. HAC lag rule `L = floor(4 (m/100)^(2/9))`: 10 for 8474 rows, 5 for 504, 4 for 252.

**Full sample** (`L = 10`)

| Factor | OLS beta | se HAC | Shrunk beta | Pull | MDE80 |
| --- | --- | --- | --- | --- | --- |
| Mkt-RF | 1.009307 | 0.006648 | 1.009238 | 0.001007 | 0.022719 |
| SMB | -0.147573 | 0.006168 | -0.147548 | 0.000065 | 0.021079 |
| HML | 0.007112 | 0.008729 | 0.007206 | 0.000653 | 0.029830 |
| RMW | 0.087762 | 0.009364 | 0.087647 | 0.000810 | 0.032002 |
| CMA | 0.060741 | 0.011204 | 0.060586 | 0.001947 | 0.038290 |

**Last 504 rows**, 2024-09-26 to 2026-09-30 (`L = 5`; not a scope of the report section, computed with the library functions and checked against statsmodels)

| Factor | OLS beta | se HAC | Shrunk beta | Pull | MDE80 |
| --- | --- | --- | --- | --- | --- |
| Mkt-RF | 1.011590 | 0.019482 | 1.011382 | 0.008572 | 0.066580 |
| SMB | -0.089326 | 0.013065 | -0.089283 | 0.000292 | 0.044648 |
| HML | 0.007472 | 0.011972 | 0.007494 | 0.001227 | 0.040915 |
| RMW | 0.028211 | 0.013991 | 0.028128 | 0.001803 | 0.047813 |
| CMA | 0.023622 | 0.012340 | 0.023502 | 0.002351 | 0.042172 |

**Last 252 rows**, 2025-09-30 to 2026-09-30 (`L = 4`; the report's `latest_window` scope)

| Factor | OLS beta | se HAC | Shrunk beta | Pull | MDE80 |
| --- | --- | --- | --- | --- | --- |
| Mkt-RF | 0.989937 | 0.006603 | 0.989928 | 0.000993 | 0.022564 |
| SMB | -0.102140 | 0.022655 | -0.102042 | 0.000875 | 0.077422 |
| HML | 0.026463 | 0.014720 | 0.026394 | 0.001852 | 0.050306 |
| RMW | 0.010865 | 0.013685 | 0.010921 | 0.001726 | 0.046768 |
| CMA | -0.006103 | 0.009454 | -0.006102 | 0.001387 | 0.032310 |

The 504-row numbers equal SB8.1 to its printed digits (OLS Mkt-RF 1.0116, se 0.0195, shrunk 1.0114, pull 0.009, MDE80 0.067). The full-sample numbers equal SB8.1 and `docs/validation/spy-slice-validation.md` section 4.

Further expected values, all from the same runs:

- Extra years to detect a beta of 0.05 (SMB, HML, RMW, CMA; Mkt-RF has no sentence): full sample 0 for all four; 504 rows 0 for all four; 252 rows SMB 1.3977, HML 0.0123, RMW 0, CMA 0.
- 95% credible intervals, full sample: Mkt-RF [0.996219, 1.022257], SMB [-0.159635, -0.135461], HML [-0.009885, 0.024298], RMW [0.069307, 0.105988], CMA [0.038655, 0.082517].
- 95% credible intervals, 252 rows: Mkt-RF [0.977001, 1.002855], SMB [-0.146354, -0.057729], HML [-0.002400, 0.055188], RMW [-0.015847, 0.037690], CMA [-0.024614, 0.012411].
- `moved_away` is true for HML (full sample, pull 0.0007), HML (504 rows, pull 0.0012), and Mkt-RF and RMW (252 rows, pulls 0.0010 and 0.0017). Every pull is below 0.05, so the panels draw no diamond, no "Moved away from typical" and no L-CORR-MOVE text (section 4.3), and say "Shrinkage moves no beta by a visible amount: this sample is long enough."

Reading: for a long, precise history like SPY shrinkage is invisible (largest pull 0.9%, Mkt-RF on 504 rows). A visible pull appears only in the synthetic two-scope fixture (`backend/factordesk/tests/fixtures/sections/shrunk.json`, a short-history stock with pulls from 9% to 80%), which the panel tests use.

## 4. Changes made in this stage

### 4.1 Gates

Everything passed except one known failure, fixed first: `panelRegistry.test.tsx` expected the placeholder text for a populated shrunk section. It now follows the shape of the kalman branch (the placeholder check runs only when the section's fixture still carries the placeholder reason; otherwise the panel must exist). `test_panel_registry.py` follows the same shape, counting placeholders from the fixture files. `test_schema_contract.py` uses the `BUILT_SECTIONS` tuple of the sibling branches; here it is empty because the shrunk hook fills the field only online, from the portfolio files, so the offline pipeline test still leaves it absent. When the three feature branches merge, the tuples combine (`("residual", "kalman_betas")`); the only expected conflict is that one line.

### 4.2 Wording made identical in the two panels

Both panels are pinned by a test on each side (`test_panel_shrunk.py`, `ShrunkBetasPanel.test.tsx`).

- Scope heading: "Full sample (559 days)" and "Latest 252-day window" (the static panel used "Full sample" with a sub-line).
- Table headings: "Factor", "OLS beta", "se", "Shrunk beta", "95% credible interval", "Pull" (the React panel used lower case); the credible interval prints as "[+0.996, +1.022]" in both (the static panel said "to").
- Visually hidden table caption: "OLS and shrunk betas with standard errors, 95% credible intervals and pull; a marker is drawn only where the pull is at least 5%".
- Marker word: "Moved away from typical".
- Legend text: "Pulled 5% or more toward typical".
- Pull note under each table: "Pull is the share of the way from the OLS beta to its typical value: 0% means no move, 100% means all the way." (added to the React panel).
- No-pull line: "Shrinkage moves no beta by a visible amount: this sample is long enough."
- Power statements: a heading "What the test behind the reliable tags could detect" and one sentence per factor, as the model wrote them (the static panel had a three-column table; it now uses the list of the React panel).
- Next-step line for a scope that is not `ok`: "Widen the date range and run the report again." for `insufficient_data`, "Run the report again; if it repeats, check the factor data in Data and audit." otherwise (the static panel used the first for every status).
- Footnote: the descriptive label alone; "How this is computed" holds the prior sentence, "Prior centre and spread per factor: Mkt-RF 1.000 and 0.209; SMB 0.000 and 0.764; ... The spread comes from 49 industry and 75 size portfolios, 2016-09-21 to 2026-09-30.", then the model labels in the order the model lists them (the static panel had a prior table, a "Prior for" line per scope, and put L-SHRINK in the footnote).
- With no scope `ok`, neither panel draws a footnote or a legend.

### 4.3 Moved-away only where the pull marker is drawn

The model's `moved_away` is true when the shrunk beta sits on the far side of the OLS beta from the prior centre (L-CORR-MOVE condition of SB6). The live run showed it true for SPY full-sample HML with a pull of 0.0007, where a "moved away" marker would look like a finding. Both panels now show the word, and the label L-CORR-MOVE in "How this is computed", only on rows whose pull is at least 0.05 (the rows that draw the diamond). The payload is unchanged: `moved_away` and the label list still follow the spec. Tests: negligible pull draws neither the word nor the label; a pull of exactly 0.05 draws both.

### 4.4 L-SHRINK says "bars", the panels are tables

The model text (SB6, `report/sections/shrunk.py`) ends "the bars show the estimates from this stock's data". The static panel has no bars, and the React panel has them only in a plot column. The spec text belongs to the owner, so the model text is unchanged. Proposed sentence for the owner to approve: replace the last clause with "the OLS betas shown are the estimates from this stock's data."

## 5. Known limits

- Scope is the full sample and the latest primary window only (SD7); no shrunk rolling series.
- The reference prior understates single-stock dispersion (SB2.4): with true spread twice the prior's, shrunk MSE is 11 to 35% worse than OLS and the 95% intervals under-cover (simulation SB8.3, TSB14). OLS stays primary (SD3).
- The prior is recomputed per report from 2520 French rows ending at the last factor date; it varies by decade (SB2.2 stability table). One prior serves both scopes, so the static panel lists one prior, not one per scope.
- The 252-row window of SPY has a HAC standard error for Mkt-RF (0.0066) equal to the full-sample one, and smaller than the 504-row one (0.0195). The three fits agree between the pipeline and an independent statsmodels fit to 1e-10, so the difference sits in the data, not in the code; the validator should confirm it (a likely cause is that the last 504 rows include a volatile stretch that the last 252 rows do not).
- First use downloads four files (about 13.4 MB zipped). Without network the section is `failed` with `prior_unavailable`; the rest of the report is unaffected.
- With injected factors or an offline loader the section is `null` and no panel is drawn. The dashboard and the CLI on the default path fill it.
- In the payload, `sample.n` of the latest-window scope is the row count of the whole sample (8474 for SPY) and `window` is the window length; the power sentence uses the window's own row count.
- `docs/methodology.md` is not edited (SB10.3 lists the proposed additions: labels M0.9, rows M0.7, schema mention M14, constants M15).
- Merge note: this branch and the two sibling branches each edit `panelRegistry.test.tsx`, `test_panel_registry.py` and `test_schema_contract.py` in the same shape; expect trivial conflicts.

## 6. Open owner decisions

1. **Prior spread for single stocks** (SB10.4 Q1): ship as specified with the caveat (current behaviour and the recommendation), inflate `tau`, or ship only the power statement until the peer prior exists.
2. **`delta = 0.05`** (SB10.4 Q3): keep fixed (current) or let the user choose.
3. **L-SHRINK wording** (section 4.4): approve the corrected clause.
4. **Where the "moved away" rule lives**: it is a display rule in both panels now (section 4.3). If the owner prefers the model to add L-CORR-MOVE to `labels` only when a drawn row moved away, the hook changes and the panel filters become redundant but harmless.
5. **Methodology additions** of SB10.3.
6. Already decided on 2026-11-18: download and keep the four portfolio files fresh (SB10.4 Q2; refresh with the factor data, same staleness policy, re-download when the factor vintage moves).

## 7. What the independent validator must recompute (without reading the implementation)

Use only `docs/specs/shrunk-betas.md`, `docs/methodology.md` (M0.5 HAC, M2 alignment) and the files below.

### 7.1 Inputs and where they are cached

All in this worktree, `C:\Users\loren\Research\factordesk-wt\feat-shrunk-betas\data\` (gitignored, never committed). Read the parquet files directly with pandas; do not call the factordesk loaders.

| File | Content | SHA-256 of the parquet file |
| --- | --- | --- |
| `data/prices/SPY_2026-11-18.parquet` | SPY bars 1993-01-29 to 2026-11-17, columns `close, adj_close, dividends, splits, capital_gains, volume` | `5223e94ffa5ba9122e6503bdf36116f7bf61979674da9def427a4b3c7d4a5b58` |
| `data/factors/ff5_daily.parquet` | French 5 factors + RF, decimals, 15918 rows 1963-07-01 to 2026-09-30 (source zip SHA-256 `e5857722...84f` in `meta.json`) | `0165744897146d1a0b328bbf961e2c29bdb117cc235eabc30d044ce3f5430b78` |
| `data/portfolios/ind49_daily.parquet` | 49 industries, value-weighted, 26338 rows from 1926-07-01 (zip SHA-256 `b9d36d57...`) | `ca60280b3f3918eedd33586686987337323885cfab7d407beaa06582e8c68ec8` |
| `data/portfolios/me_bm25_daily.parquet` | 25 ME x BE/ME (zip `820936bd...`) | `f35e3b0f3e882850d45d75253aed92c3d85da96eb03a8b98a3f395d3c2b3117c` |
| `data/portfolios/me_op25_daily.parquet` | 25 ME x OP (zip `1b588736...`) | `f942cedb2b109921cb169fc4e708c34ce371bcc5ca293f4911a3bd2905c74129` |
| `data/portfolios/me_inv25_daily.parquet` | 25 ME x INV (zip `b4a29993...`) | `5eaee869b496b044b3e080a87dc3944323897dde6f21a8dfe12999fcdb2a70b4` |

Each portfolio file has a sidecar `.json` with the zip SHA-256, `crsp_stamp` 202609 and `Last-Modified`. Returns are decimals; missing values are NaN. If the validator prefers fresh files, the same zips are on the Ken French library page (spec SB2.2 table); the expected values below hold only for the 202609 vintage.

### 7.2 Recipe

1. **SPY sample (M2).** `r_t = adj_close_t / adj_close_(t-1) - 1` on consecutive price rows (a non-positive price counts as missing). Keep a return row only if its date is a French date, exactly one French date lies in (previous price date, date], and neither the return nor the factors are missing. Excess return `y = r - RF`. Rows after 2026-09-30 are not used. Expect n = 8474, 1993-02-01 to 2026-09-30, zero excluded rows.
2. **Regression.** OLS of `y` on a constant and the five factors (Mkt-RF, SMB, HML, RMW, CMA). Covariance: Bartlett HAC, `L = floor(4 (m/100)^(2/9))` for m rows, no small-sample correction (statsmodels `cov_type="HAC", maxlags=L, use_correction=False` is the same estimator). `b` = the five factor coefficients; `V` = the 5 x 5 factor block of the covariance. Do this for all rows, the last 504 rows and the last 252 rows (each with its own L).
3. **Prior (SB2.1, SB2.2).** `m0 = (1,0,0,0,0)`. Window = the 2520 French dates ending 2026-09-30 (2016-09-21 to 2026-09-30). For each portfolio column of the four files with no missing value in the window: excess return = portfolio - RF; OLS on the five factors with intercept, HAC `L(2520) = 8`; keep `b_ij` and `V_i,jj`. Cross-section A = the 49 industries; B = the 75 columns of the three 25-portfolio files. `tau_c,j^2 = mean_i (b_ij - m0_j)^2 - mean_i V_i,jj`; take `sqrt(max(., 0))`; `tau_j = max(tau_A,j, tau_B,j, 0.05)`.
4. **Posterior (SB3).** `V_post = (V^-1 + diag(tau^-2))^-1`; `b_post = V_post (V^-1 b + diag(tau^-2) m0)`; `S_w = V_post diag(tau^-2)`; `pull_j = S_w[j, j]` (unclipped); credible interval `b_post,j +/- 1.959964 sqrt(V_post[j,j])`; `moved_away_j = sign(b_post,j - b_j) != sign(m0_j - b_j)`.
5. **Power (SB5).** `k80 = z(0.995) + z(0.80) = 3.417451`; `MDE_j = k80 se_j`; `n_req = n (k80 se_j / 0.05)^2`; extra years `= max(0, n_req - n) / 252`. Market beta gets no "years" sentence. Years in the sentence = rows / 252 (33.6 for 8474, 1.0 for 252). Check the sentence text against the templates of SB5; for example, 252 rows SMB reads "With 1.0 years of data, an SMB beta of 0.08 or larger would be detected with 80% power (after correcting for testing 5 betas). Detecting an SMB beta of 0.05 would take about 1.4 more years of similar data.", 252 rows HML ends "... would take less than 0.1 more years of similar data.", and the full sample SMB ends "An SMB beta of 0.05 is already detectable."
6. **Report JSON (optional cross-check).** `uv run factordesk report SPY --json --out <empty folder>` writes `SPY_report.json`; its `shrunk_betas` list holds the two scopes. Compare the validator's numbers to it, not the other way round.

### 7.3 Expected values and tolerances

| Quantity | Expected | Tolerance |
| --- | --- | --- |
| n, first and last date (full) | 8474, 1993-02-01, 2026-09-30 | exact |
| L for 8474, 504, 252, 2520 rows | 10, 5, 4, 8 | exact |
| `n_portfolios` | 49 industry, 75 size | exact |
| Prior window | 2016-09-21 to 2026-09-30, 2520 rows | exact |
| `tau` (A, B, default), section 3.1 | 0.209349, 0.764220, 0.341372, 0.328693, 0.253599 (default) | 1e-6 absolute |
| OLS beta and se HAC (all three windows), section 3.2 | as printed | 1e-8 absolute |
| Shrunk beta | as printed | 1e-8 absolute |
| Pull | as printed | 1e-8 absolute |
| Credible interval ends, section 3 | as printed | 1e-6 absolute |
| MDE80 | as printed | 1e-8 absolute |
| Extra years | as printed | 1e-5 absolute |
| `moved_away` flags | as listed in section 3.2 | exact |
| Identities | `b_post = (I - S_w) b + S_w m0`, `V_post V^-1 + S_w = I` | 1e-10 |
| Pull display | all 15 pulls below 0.05, so no marker, no moved-away word | exact |

Also to check without reading the code: (a) rows dated after 2026-09-30 never enter the prior (replace them with noise and the prior is unchanged); (b) the shrunk numbers do not feed attribution, risk, dominance or drift (the OLS numbers in the report JSON equal an independent OLS); (c) the L-SHRINK, L-SHRINK-PRIOR, L-CRED, L-CORR-MOVE and L-MDE texts in the report equal SB6 and SB5; (d) the two panels show the same words (section 4.2); (e) the MSE and coverage claims of SB8.3 for the prior-correct and twice-too-tight cases with a fresh seed.

## 8. Gate results at hand-off

Python: 649 passed (default selection; 209 `slow` and `live` tests deselected), plus the 4 shrunk `slow` and `live` tests run separately and passed. ruff and pyright: no findings. Frontend: typecheck and lint clean, 399 vitest tests passed (28 files), build and size budget (383.8 kB raw, 117.7 kB gzip against 400 / 125) pass, browser smoke test passed.
