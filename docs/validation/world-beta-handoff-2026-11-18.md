# World beta: hand-off to independent validation

Date: 2026-11-18 (live run 2026-11-19). Branch `feat/world-beta`, from `dev` at `4ad6d2e`; code as of commit `f0aabce` (the commit that follows it changes only documents and the test registry).
Spec: none separate; the definition is section 2 of this page. Contract: `docs/specs/schema-v3-contract.md`; the sixth-section note is `docs/validation/world-beta-contract-note-2026-11-18.md`. Decision page: `wiki/decision-world-beta.md`.
Audience: the independent validator (next step), and the owner for the open questions in section 7.

**After validation (2026-11-19).** The independent validation (`docs/reviews/world-beta-validation-2026-11-19.md`, verdict merge with conditions) was answered on this branch the same day: section 9 below lists every rename, the proposals for the dashboard spec, and what changed. Where this page's earlier sections name a field, a value, a reason text or a position that section 9 renames, section 9 is current.

The validator recomputes the numbers in section 6 from the definitions in section 2 and the cached prices **without reading the implementation**.

**What the owner asked for, and what was used.** The owner asked for a quick beta against the MSCI All Country World index (or ACWI). The MSCI index has no free daily data source, so the proxy is the **iShares MSCI ACWI ETF** (Yahoo ticker `ACWI`, history from March 2008, US dollars, priced on a US exchange at the same close as US stocks). The panel, the schema and every caveat say so plainly: the number is a beta against an ETF used as a stand-in for the index.

---

## 1. What was built

| Layer | File | What it holds |
| --- | --- | --- |
| Maths | `backend/factordesk/analytics/world_beta.py` | `single_factor_beta` (calls the existing `ols_hac`; no second HAC), `align_overlap` (the common days, with the same-interval rule), `compare_betas` and the three comparison sentences |
| Prices | `backend/factordesk/data/prices.py` | `YFinanceProvider.fetch_incremental` (incremental cache refresh), `HistoryRefresh`, `IncrementalPriceProvider`, `rebased`, `merge_histories`, `latest_completed_session`. Existing methods are unchanged in behaviour |
| Schema | `backend/factordesk/report/sections/world_beta.py` | `WorldBetaSection`, `BetaFit`, the two label texts; status rules |
| Pipeline | `backend/factordesk/section_hooks/world_beta.py` | `load_world_benchmark` (fetch through the report's provider, never raises), `build_world_beta` |
| Wiring | `section_hooks/context.py`, `section_hooks/__init__.py`, `pipeline.py`, `api/deps.py`, `api/service.py` | `WorldBenchmarkInput`, `SectionInputs.world_benchmark`; `build_report` passes its provider; the dashboard refreshes ACWI on each report build |
| Static panel | `backend/factordesk/report/panels/world_beta.py` | "World beta (quick estimate)", position 540, element id `world-beta`; existing classes only (one rule, `table.reg.wb{min-width:0}`) |
| React | `frontend/src/components/report/sections/WorldBetaPanel.tsx`, `panelRegistry.ts`, `api/types.ts`, test helpers | A placeholder frame only; the real panel is built later by someone else |
| Generated | `frontend/src/api/openapi.json`, `types.gen.ts`, `tests/fixtures/mock_report.json` | Regenerated with the repository commands; the mock fixture gains `"world_beta": null` |

`SCHEMA_VERSION` stays `"4"` (contract SC5: an additive optional field does not bump it).

**Offline behaviour.** When `build_report` receives injected factors (the offline path used by the tests and the offline CLI) nothing is fetched and `world_beta` is `None`, as for the shrunk betas. With real factors, ACWI is fetched through the same provider object as the stock. A fetch that fails never stops the report.

**Statuses.** `ok`; `insufficient_data` (fewer than 252 common days); `failed` with a reason when: the ACWI price audit finds errors; ACWI cannot be fetched and no cache exists (reason "ACWI price data could not be fetched", the cause in `acwi_note`); the benchmark's excess return does not vary (standard deviation below 1e-8, the M2 step 7 limit); any other error. The shared `Status` is not extended: the owner's first brief said `unavailable`, and the contract review of 2026-11-19 replaced it with `failed` (M0.7 values only). When the refresh fails but a cache exists the section is `ok`, built from the cache, with `acwi_note` "ACWI data ends <date>; the refresh did not complete (...), so the cached history was used." The field is `None` only when the feature did not run (offline).

## 2. Definitions (the validator recomputes these)

Notation: `S` is the analysis sample of M2 (dates after the usual exclusions, in the requested range). `P_t` is ACWI's `adj_close`. `RF_t` is the daily risk-free rate of the French file.

- WB1.1 Benchmark return: `b_t = P_t / P_{s(t)} - 1`, where `s(t)` is the row before `t` in the ACWI history (a missing or non-positive price makes `b_t` missing, as `PriceHistory.total_returns`).
- WB1.2 Same interval: `b_t` is used on a date `t` of `S` only if the ACWI row before `t` has the same date as the stock's row before `t`. Otherwise the day is dropped (it would set a two-day ACWI return against a one-day stock return). A date absent from ACWI therefore drops that day and the next.
- WB1.3 Excess benchmark return: `x_t = b_t - RF_t`. Stock excess return `y_t = r_t - RF_t` (M2 step 5, the sample's own `xret`).
- WB1.4 Overlap `O`: the dates of `S` with a usable `b_t` (WB1.1 and WB1.2). `n = |O|`. If `n < 252` the status is `insufficient_data`.
- WB1.5 Quick beta: OLS of `y_t` on `x_t` with an intercept over `O`. Standard error: Newey-West, Bartlett kernel, no small-sample correction, `L = floor(4 (n/100)^(2/9))` (M0.5; the same function as every other regression). Interval: `beta +/- 1.959964 se`. Also R squared, the correlation of `y` and `x`, `alpha_annual = 252 * intercept` and its HAC z.
- WB1.6 US market beta on the same days: the same regression with `Mkt-RF_t` (from the FF5 file) in place of `x_t`, same dates, same `L`.
- WB1.7 Comparison: the two 95% intervals share a point: "About the same". Otherwise, if the world beta is the larger: "Higher against the world"; if smaller: "Lower against the world". Nothing else is claimed.
- WB1.8 Guards: `x` with standard deviation below `1e-8` (M2 step 7 limit) or `y` constant: refused (`failed`, never NaN). Non-finite input: refused. An exact fit (`y = x`) has a zero standard error; the alpha t is then `null`.
- WB1.9 Audit: the full ACWI history goes through the same audit as the stock (`audit_prices`). Any `error` finding makes the section `failed`; `warn` findings are carried in `audit_warnings`.

## 3. Tests and ids

All run on this branch at `f0aabce`. Registry lines: `docs/registry/tests.jsonl`, `T-20261118-950` to `T-20261118-955`, status `run`.

| Ids | What | File | Count |
| --- | --- | --- | --- |
| TWB01 | Known beta 1.3 recovered inside its interval | `test_world_beta.py` | 19 in the file |
| TWB02 | Stock equal to the benchmark: beta 1, R2 1, no NaN | | |
| TWB03 | Independent stock: beta near 0 (within 3 se), R2 below 0.01 | | |
| TWB04 | Adding the same constant to both leaves beta, se and R2 unchanged; alpha moves by `c (1 - beta)` | | |
| TWB05 | Beta, intercept, correlation and R2 equal `np.polyfit` and the by-hand formulas to 1e-12 | | |
| TWB06 | HAC se equals the existing `ols_hac` exactly and statsmodels' HAC (`maxlags=L`, `use_correction=False`) to 1e-10 | | |
| TWB07, TWB08 | Constant benchmark refused; NaN and mismatched lengths refused | | |
| TWB09 to TWB13 | Overlap: full, stock history starting before ACWI, exactly 252 and 251 days, a missing ACWI day (drops that day and the next), a NaN ACWI price (drops its two returns) | | |
| TWB14 to TWB17 | Comparison wording: overlapping, touching, disjoint higher and lower; symmetry | | |
| TWB18 | Alpha and its t | | |
| TWB20 to TWB31 | Section: both fits on the same days; JSON round trip; labels join the report only when present; caveat sentences; 252 ok and 251 `insufficient_data`; no numbers when not ok; constant benchmark `failed`; audit errors `failed`; audit warnings carried; NaN price; fetch failure with no cache `failed` and the report builds; stale cache `ok` with the note | `test_section_world_beta.py` | 31 in the file |
| TWB32 to TWB35 | Loader: one ACWI request; never raises (no data, connection error, rate limit, other); incremental provider used; real `YFinanceProvider` cold failure and warm failure | | |
| TWB36 to TWB39 | Wiring: `load_section_inputs` through the given provider (and offline fetches nothing); `build_report` fetches ACWI once through the pipeline provider; injected factors keep the CLI offline; the dashboard refreshes on every report build | | |
| TWB40, TWB41 | Schema: `None` by default and in old files; status rules | | |
| TWB42 to TWB46 | Static panel: absent renders nothing; two rows, sentence, folded method, footnotes and the ACWI last date; position; stale note and failed reason; comparison sentences through the real hook | | |
| Cache | Cold cache (one full download); warm cache with new days (only the new days requested, merged series equals a full fetch); up to date (no call, same day and a weekend); failed refresh with a cache (stale, note starts "ACWI data ends"); failed download with no cache; rate limit in plain words; corrupt cache (downloaded again); rebased prices (full download); no new bar (holiday) | `test_prices_incremental.py` | 14 |
| Contract | Six optional fields in panel order, mock fixture version 4 with `world_beta` null, fixtures validate, labels equal the section spec, panel order and position | `test_schema_contract.py`, `test_panel_registry.py`, `test_sections_together.py`, `test_report.py` | existing, updated |
| React | Panel order and placeholder handling | `panelRegistry.test.tsx` | existing, updated |

The oracle for TWB01 to TWB06 is closed-form (OLS by the covariance formula, `np.polyfit`) and the statsmodels HAC call; no number was copied from the implementation.

## 4. Decisions made while building

- **Position 540**, after fragility (530) and before Return contribution (600): the panel reads the market beta of Exposures against a second market, so it goes with the three panels that qualify the Exposures betas, after them because it is a quick secondary view.
- **Incremental ACWI cache (owner instruction of 2026-11-18).** ACWI lives in the normal price cache (`prices/ACWI_<date>.parquet`, one file, older ones removed). On each report build: today's file or a file whose last bar is the latest completed New York weekday means no network call. Otherwise only the days after the last cached date are requested, from seven calendar days before it. **Yahoo rewrites the whole adjusted history at every dividend**, so appending would silently mix two bases (the existing code comment says this). The seven-day overlap is compared with the cache (`adj_close` and `close`, relative tolerance 1e-6); any difference means a full download. This check is an addition to the owner's instruction. Exchange holidays are not modelled: on a holiday one request finds nothing new and writes today's file, so there is no second request that day.
- **Failed refresh with a cache** keeps the cache and says "ACWI data ends <date>"; the same-day marker is not written, so the next report build tries again.
- **Retry and throttle** are the settings of `fetch_many` (`PRICE_*` variables); the refresh uses the same rate limiter, retries with back-off and circuit breaker, through the same `_download_one` path.
- **The ACWI audit covers the whole history**, like the stock's. An error finding anywhere in 2008 to today fails the section, even if it lies outside the overlap. No error appeared in the live run (section 5); a tighter rule (errors inside the overlap only) is an open question.
- **SampleInfo of the section** is the analysis sample's, with `n`, `start` and `end` replaced by those of the overlap. The count of sample days with no usable ACWI return is `n_not_in_benchmark`.
- **The caveat sentence says "many non-US stocks", not "mostly".** The owner's brief wrote "mostly non-US stocks". The MSCI ACWI index is, as far as we know, majority US by weight (we have not verified the current figure and do not state one), so "mostly" would be an unverified claim in a panel. The sentence says ACWI includes many non-US stocks (their share varies over time) whose markets close earlier than the US. Owner: please confirm or restore your wording.
- **No Dimson correction** and no global factor model (wiki decision page).

## 5. Live numbers (real Yahoo prices, real factor file to 2026-09-30)

Run 2026-11-19 in a scratch data directory (nothing committed). ACWI: 4,691 rows, 2008-03-28 to 2026-11-17, no audit error, no audit warning. First download was the full history; a second ticker in the same run read the cache.

| Ticker | Days (from to) | HAC lags | World beta | se | 95% interval | R2 | Corr | Alpha a year (HAC t) | US market beta, same days (se, R2) | Reading |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| SPY | 4,656 (2008-03-31 to 2026-09-30) | 9 | 0.9452 | 0.0117 | [0.922, 0.968] | 0.930 | 0.964 | +3.62% (3.59) | 0.9745 (0.0092, 0.984) | about the same |
| ZM | 1,872 (2019-04-22 to 2026-09-30) | 7 | 0.7610 | 0.2053 | [0.359, 1.163] | 0.068 | 0.261 | +8.29% (0.46) | 0.7756 (0.2022, 0.083) | about the same |
| EFA | 4,656 (2008-03-31 to 2026-09-30) | 9 | 1.0278 | 0.0144 | [1.000, 1.056] | 0.906 | 0.952 | -3.01% (-2.31) | 0.9536 (0.0246, 0.776) | about the same (touching near 1.00) |

SPY's sample has 8,474 days, of which 3,818 precede ACWI's first return. ZM's 1,872 days all have an ACWI return.

**Cross-check.** A scratch script (not committed) recomputed every beta and R2 with plain pandas and numpy from the provider's cached prices and the factor file (inner join on dates, `pct_change`, `cov / var`): all differences are at most 2.7e-15.

**Sanity against the brief's expectation.** The brief expected SPY's beta against ACWI near 1.0 to 1.1 with R2 about 0.9. R2 is 0.93, but the beta is 0.945, **below** that range. The independent check agrees with the number, so it is not a bug. The reason is arithmetic: beta equals the correlation times the ratio of the volatilities, and SPY's daily volatility over these days is slightly below ACWI's (the correlation is 0.964, so the ratio is about 0.98). A beta of SPY against a broader, more volatile index is below one over this window. The US market beta on the same days is 0.975, not 1.0; a likely reason (not tested here) is that the market factor includes small caps while SPY is large-cap (the five-factor regression of the shrunk-betas hand-off gives SPY an SMB beta of -0.15). Not checked: the same regression with one-day leads and lags, which would show the asynchronous-trading effect directly.

## 6. What the validator recomputes

For SPY, ZM and EFA, from the cached prices of the ticker and of ACWI and the French file:

1. The list of dates: ticker return dates in the analysis sample and in ACWI's history, after WB1.2. Expected `n` is in section 5 (compare also the count of dropped days, SPY 3,818 before ACWI started).
2. The excess returns of WB1.3 and the two OLS regressions of WB1.5 and WB1.6. Expected betas, R2 and correlations are in section 5 to the printed digits.
3. The HAC standard error with the lag rule of WB1.5 (9 for 4,656 days; 7 for 1,872), the interval and the alpha t. Expected SPY world se 0.0117; US 0.0092.
4. The reading of WB1.7 for each row.
5. Hand-built checks: (a) a stock series equal to ACWI's excess return gives beta 1, R2 1; (b) shifting both series by the same constant leaves the beta unchanged.
6. The cache: delete `ACWI_*.parquet`, run one report (one full download), run a second report the same day (no request), then edit the cached file to remove the last five rows and run again on a later day (a request from seven days before the last date; the merged frame equals a fresh full download).

## 7. Open questions for the owner

1. **Caveat wording.** "Mostly non-US" (the brief) or "many non-US stocks" (used), see section 4.
2. **Audit scope.** Fail the section for an ACWI audit error anywhere in its history (as built, same as the stock), or only inside the overlap? One error in 2008 would fail every report.
3. **Methodology text.** The branch did not edit `docs/methodology.md`. Proposed new section M-WB (to be folded in by the owner): "Quick world beta: definitions WB1.1 to WB1.9 of the hand-off, the proxy statement, the same-interval rule, and the note that the M0.5 lag rule applies to the overlap." Also M1.3 could say that a cached history is refreshed incrementally with an overlap check.
4. **Contract amendments.** Section 3 of the contract note proposes the text.
5. **Alpha.** Shown only in the folded text; confirm that is the right prominence for "secondary".
6. **Holiday handling.** Holidays are not modelled; a holiday costs one request and one same-day file. A trading calendar would remove it; not worth a dependency unless the owner prefers.
7. **Another kind of vendor rewrite.** The overlap check catches dividends and splits (any change in the overlap rows). A rewrite that changes only rows older than seven days is not caught; Yahoo does that for capital-gain adjustments and corrections. Option: a full download once a week or a larger overlap.
8. **React panel.** Placeholder only; it renders the frame, not the table.
9. **Equivalent ETF.** If the owner prefers another proxy (for example a different global fund), the ticker is one constant (`BENCHMARK_TICKER`) and the section field `benchmark` is typed `"ACWI"`, so the type would change too.

## 8. Gates at this hand-off

From the worktree, 2026-11-19:

| Gate | Result |
| --- | --- |
| `uv run pytest -q` | 910 passed, 227 deselected (live and slow markers) |
| `uv run ruff check backend` | All checks passed |
| `uv run ruff format --check backend` | 110 files already formatted |
| `uv run pyright` | 0 errors, 0 warnings |
| `frontend`: `npm run typecheck`, `npm run lint` | no errors |
| `frontend`: `npm test` | 34 files, 491 tests passed |
| `frontend`: `npm run build`, `npm run size` | built; 396.1 kB raw, 121.3 kB gzip (budget 400 / 125) |
| `frontend`: `npm run e2e` | 1 passed (dashboard smoke on the fake backend) |
| Generated files | `openapi.json` and `types.gen.ts` regenerate with no diff |

Not run: the `live` and `slow` markers (the live Yahoo run of section 5 was done by script, not by a marked test).

---

## 9. After validation (2026-11-19)

Review: `docs/reviews/world-beta-validation-2026-11-19.md` (commit `bbc766b`), merged with `--no-ff` so that it stays in the history. SCHEMA_VERSION stays `"4"`. The numbers were not in question; the conditions were about the interface (F1), the failure path (F2) and one documented value (F4). The recommended items for the cache (F3) and the audit scope (question b) were done too.

### 9.1 F1: aligned with dashboard spec DV2.6 and DV4.8

Every rename, in one table. Nothing else in the section changed name.

| Before | After | Where |
| --- | --- | --- |
| `benchmark` (section field) | `proxy` | `WorldBetaSection` |
| `se_hac` (in `world` and `us_market`) | `se` | `BetaFit` |
| `ci95_low` | `ci_low` | `BetaFit` |
| `ci95_high` | `ci_high` | `BetaFit` |
| comparison `higher_against_the_world` | `higher` | `comparison` |
| comparison `lower_against_the_world` | `lower` | `comparison` |
| failed reason "ACWI price data could not be fetched" | "The world fund's prices could not be fetched." (with the full stop) | `UNAVAILABLE_REASON` |
| static panel position 540 (after fragility, before returns) | 350 (after the headline strip, `kpis`, before the price chart), in the static and the React registry | `report/panels/world_beta.py`, `panelRegistry.ts` |

`about_the_same` is unchanged. The comparison sentences (`comparison_text`) are unchanged. The Python dataclass `BetaEstimate.se_hac` in `analytics/world_beta.py` keeps its name (it is internal and is not in the schema). Regenerated: `tests/fixtures/sections/world_beta.json`, `frontend/src/api/openapi.json`, `frontend/src/api/types.gen.ts` (`mock_report.json` holds `world_beta: null` and did not change).

**Proposals for DV2.6 and DV4.8 (the validated behaviour is kept; the owner decides).** These are differences of substance, not of naming, so the section was not bent to the spec.

1. **Nested fits instead of flat fields.** DV2.6 has flat `beta, se, ci_low, ci_high, us_beta, us_se, us_ci_low, us_ci_high` and top-level `n, start, end`. The section has two objects, `world` and `us_market`, of the same type (`beta, se, ci_low, ci_high, r2, correlation, alpha_annual, alpha_t`), and `sample.n, sample.start, sample.end` (the shape every section already uses). It carries R squared and correlation for the US fit too, which the comparison needs to be read fairly, and one type is one component for V16. Proposal: amend DV2.6 to read `world.beta`, `world.se`, `world.ci_low`, `world.ci_high`, `world.r2`, `us_market.beta`, `us_market.se`, `us_market.ci_low`, `us_market.ci_high`, `sample.n`, `sample.start`, `sample.end`.
2. **Fields the spec does not list**: `hac_lags`, `n_sample`, `n_not_in_benchmark`, `acwi_first_date`, `acwi_last_date`, `acwi_note`, `audit_warnings`, `comparison_text`, `labels`. DV2.6 says the stale note goes "in the section note"; it is `acwi_note` (and `acwi_last_date` gives the date for DV4.8's ". ACWI data ends {date}"). Proposal: add them to the DV2.6 table.
3. **Why a section failed.** DV4.8 gives one fixed sentence for `failed` ("The world fund's prices could not be fetched; ..."). The section also fails when the ACWI audit finds errors inside the overlap or the benchmark does not vary, and then that sentence would misstate the cause. Rule for V16: show `reason` as given whenever `acwi_first_date` is not null (the prices came but cannot be used); the fixed fetch sentence only when `acwi_first_date` is null. The static panel already does this: "Run the report again later" only for a fetch failure, "The rest of the report is not affected." otherwise (F5).
4. **ACWI audit errors.** DV4.8 shows "Unconfirmed: the price audit found errors." for the stock, as M1.4 says (the analysis goes on). For ACWI, an error dated inside the overlap makes the section `failed` (the only regressor would be wrong); an error outside it is a note in `audit_warnings`. Proposal: say so in DV4.8, or choose the "Unconfirmed" reading for ACWI too.

### 9.2 F2: a failing refresh with a cache costs no waiting

When a cached ACWI history exists, the refresh makes one attempt: the retry count is set to one for that call, so there is no back-off, no rate-limit pause and no `Retry-After` wait. The window request has a timeout of 15 seconds and a whole-history request made on a cache refresh one of 45 seconds (`REFRESH_TIMEOUT_SECONDS`, `REFRESH_FULL_TIMEOUT_SECONDS` in `data/prices.py`). On failure the cache is served with the "ACWI data ends <date>" note, as before. A cold cache (no file) keeps the normal retry policy of `fetch_many`. Tests (`test_prices_incremental.py`, fake clock that moves only when the code sleeps): connection error, timeout and a rate limit with `Retry-After: 90` each return `stale` with no sleep and one request; a failed forced full download is one attempt too; a cold cache still retries and sleeps; the real download functions pass the timeout to yfinance only on the refresh path.

### 9.3 F3: late-posted dividends and a monthly full download (validator recommendation c)

- The incremental request starts at the earlier of seven days before the last cached date and the last cached dividend or capital-gain date. A distribution that Yahoo records late has an ex-date after the last cached one, so it lies inside the window and changes the rows the window shares with the cache.
- The overlap check now also compares the `dividends` and `capital_gains` columns (a new distribution in the overlap counts as a rewrite), in addition to `adj_close` and `close`. Any rewrite means a whole-history download.
- The cache records when the history was last downloaded whole (`full_downloaded_at` in the parquet attributes, next to `fetched_at`). Incremental refreshes keep it. When a refresh is needed and the stamp is older than 30 days (`FULL_REFRESH_DAYS`), the whole history is downloaded. A cache without the stamp (written before it existed) gets one whole download, which sets it. An up-to-date cache still makes no call, whatever its age.
- Tests: a dividend posted weeks late (outside the old seven days, inside the new window) is picked up by a whole download and the adjusted prices equal Yahoo's; with no late dividend the refresh stays incremental and starts at the last dividend date; the old window cannot see the rewrite; a changed distribution column counts as rebased; the start date rule; the stamp is stored and kept; exactly 30 days is still incremental and 31 forces a whole download that restarts the clock; an unstamped cache is downloaded whole once.

### 9.4 F4: an exact fit has no alpha t

`single_factor_beta` returns `alpha_t = None` when the residual sum of squares is at most `1e-20` times the total sum of squares (`EXACT_FIT_RELATIVE_SSR`), as the hand-off (WB1.8), the dataclass and the schema description say. Tests: `y = x`, `y = 2x`, `y = x + 0.001` and `y = 0.5x - 0.0003` all give `None`; TWB02 asserts `None`; a fit with a residual of one part in 1e6 of the signal keeps its t.

### 9.5 Question (b): ACWI audit errors inside and outside the overlap

Only an error dated from the ACWI row before the first overlap date to the last overlap date fails the section, with the reason "The ACWI price history has errors on days this section uses (<codes>), so its returns cannot be trusted and the world beta is not computed. The section is left out until the history is corrected." An error outside that window is carried in `audit_warnings` as one sentence ("... on dates outside the days used here (<first> to <last>), so they do not affect this beta."). An error with no date counts as inside (it cannot be placed). A calendar-year drift is dated at the last row of its year and counts as inside when that year meets the window. Tests: before the overlap, after the overlap, the edge row (inside) and two rows before it (outside), and the panel's own next step.

### 9.6 Question (a): the caveat wording

Kept as "many non-US stocks". The validator cites the MSCI ACWI Index factsheet of 30 October 2026 (msci.com): United States 64.63%, Japan 5.08%, Taiwan 3.23%, United Kingdom 3.12%, Canada 3.06%, other 20.88%. By weight the index is about two thirds US, so "mostly non-US" would be false today. We did not open the factsheet ourselves; the figure is the validator's. The panel states no percentage, because it goes stale.

### 9.7 Not done (validator items outside the conditions)

F6 (the timing caveat overstates the effect for the ETF: proposed wording is the owner's call), F7 (the React placeholder shows an empty frame for an `ok` section until V16) and F8 (the stale note repeats "ACWI data ends" in two date formats on the static panel) are unchanged. The F5 wording and next step are done (9.1 item 3, 9.5).

### 9.8 Gates after validation (2026-11-19)

| Gate | Result |
| --- | --- |
| `uv run pytest -q` | 932 passed, 227 deselected (`test_world_beta.py` 24, `test_section_world_beta.py` 35, `test_prices_incremental.py` 27 tests) |
| `uv run ruff check backend` | All checks passed |
| `uv run ruff format --check backend` | 110 files already formatted |
| `uv run pyright` | 0 errors, 0 warnings |
| `frontend`: `npm run typecheck`, `npm run lint` | no errors |
| `frontend`: `npm test` | 34 files, 491 tests passed |
| `frontend`: `npm run build`, `npm run size` | built; 396.1 kB raw, 121.3 kB gzip (budget 400 / 125) |
| `frontend`: `npm run e2e` | 1 passed |
| Generated files | `openapi.json` and `types.gen.ts` regenerate with no further diff |

No test needed a rerun. The `live` and `slow` markers were not run.

## 10. Europe benchmark (2026-11-19)

Owner decision of 2026-11-19: the world beta section gets a Europe row. The stand-in is IEUR (iShares Core MSCI Europe ETF, US dollars, US-listed, history from June 2014) for the MSCI Europe index, in the same way as ACWI stands in for MSCI ACWI. SCHEMA_VERSION stays `"4"`; the change is additive.

### 10.1 What changed

- One computation per proxy. `analytics.world_beta.PROXIES` lists `("world", "ACWI", "MSCI ACWI")` and `("europe", "IEUR", "MSCI Europe")`; the hook runs the same estimator, audit and overlap rules for each. `load_world_benchmark(provider, ticker)` takes the ticker and uses the same incremental refresh and cache as ACWI (one attempt when cached, last-dividend start, whole download after 30 days, statuses `ok`, `insufficient_data`, `failed`). `SectionInputs.europe_benchmark` carries the IEUR history; `AppDeps.load_europe_benchmark` does the same for the API.
- The ACWI fields of `WorldBetaSection` are unchanged and still decide the status of the section. A new optional field `europe` holds a `ProxyBeta`: the same content as the ACWI fields (status, reason, days, dates, note, audit warnings, the fit, the US market fit on the same days, the comparison and its text), with its own status and reason, plus `label` ("MSCI Europe") and `proxy` ("IEUR"). It is `null` when it was not computed.
- One proxy failing never changes the other. If IEUR cannot be fetched, has under 252 common days, or has audit errors on the days used, the ACWI section is as before and `europe.status` says why. If ACWI fails alone, the section is `failed` and `europe` can still be `ok`.
- A fund that started after the analysis starts is fine: the Europe days are the days IEUR and the sample share (about 3,090 for SPY, from 13 June 2014). Its US-market fit is therefore on its own days and can differ from the ACWI one.

### 10.2 TypeScript paths

`report.world_beta.europe` is `ProxyBeta | null` with: `status`, `reason`, `label`, `proxy`, `n_days`, `start`, `end`, `hac_lags`, `n_not_in_benchmark`, `first_date`, `last_date`, `note`, `audit_warnings`, `benchmark` (a `BetaFit`: `beta`, `se`, `ci_low`, `ci_high`, `r2`, `correlation`, `alpha_annual`, `alpha_t`), `us_market` (a `BetaFit`), `comparison` and `comparison_text`. The Europe comparison text reads "against Europe" where the ACWI one reads "against the world".

### 10.3 Static panel

The panel table has three rows when both fits cover the same days: Against the world (ACWI), Europe (sub-label "IEUR, MSCI Europe stand-in"), and Against the US market, same days. When the Europe days differ from the ACWI days a fourth row, "Against the US market, same days as Europe", gives the other US fit. A sentence under the ACWI reading gives the Europe comparison, or says why there is no Europe row. The footnote names both stand-ins and says that IEUR history starts in June 2014. The panel also moved from position 350 to 505 (after Factor exposures); the React page uses the same position.

### 10.4 Static header line

The company line is now a sentence: "State Street SPDR S&P 500 ETF Trust. Listed on NYSE Arca, priced in US dollars." USD is written "US dollars"; other currency codes and exchange names are shown as given, except `NYSEArca`, which is written "NYSE Arca".

### 10.5 Live numbers (real Yahoo prices, factor file to 2026-09-30)

Europe beta against IEUR, excess of RF, Newey-West intervals. The plain numpy slope, computed from the same cached histories, agreed to three decimals in every row.

| Ticker | Europe beta | 95% interval | R squared | Days | US market beta, same days | Comparison |
| --- | --- | --- | --- | --- | --- | --- |
| SPY | 0.764 | [0.697, 0.831] | 0.652 | 3,093 (2014-06-13 to 2026-09-30) | 0.964 | lower |
| ZM | 0.458 | [0.177, 0.738] | 0.028 | 1,872 (2019-04-22 to 2026-09-30) | 0.776 | about the same |
| EFA | 0.908 | [0.893, 0.924] | 0.952 | 3,093 (2014-06-13 to 2026-09-30) | 0.804 | higher |

The ACWI betas on the same runs were SPY 0.945, ZM 0.761 and EFA 1.028 (4,656, 1,872 and 4,656 days). IEUR holds European stocks that close before the US, so the same-day timing caveat of the ACWI row applies, more strongly.

### 10.6 Tests

`test_europe_beta.py` (TEB01 to TEB20): the proxy list drives both blocks, the Europe block equals the ACWI path fed with the IEUR history, plain numpy cross-check, ACWI fields unchanged by the block, Europe failing alone (fetch failure, 251 common days, audit error), ACWI failing alone, the loader and cache for IEUR through the ACWI helpers, schema rules, old files without `europe`, and the panel (three rows, four rows, no Europe, failed Europe, ACWI failed alone). `test_section_world_beta.py` and the registry tests were updated for the two extra fetches, the three rows and the new position.
