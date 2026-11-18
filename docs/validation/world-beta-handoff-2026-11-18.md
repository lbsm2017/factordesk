# World beta: hand-off to independent validation

Date: 2026-11-18 (live run 2026-11-19). Branch `feat/world-beta`, from `dev` at `4ad6d2e`; code as of commit `f0aabce` (the commit that follows it changes only documents and the test registry).
Spec: none separate; the definition is section 2 of this page. Contract: `docs/specs/schema-v3-contract.md`; the sixth-section note is `docs/validation/world-beta-contract-note-2026-11-18.md`. Decision page: `wiki/decision-world-beta.md`.
Audience: the independent validator (next step), and the owner for the open questions in section 7.

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
