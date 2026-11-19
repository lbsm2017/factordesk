# World beta section: independent validation

Date: 2026-11-19. Branch under review: `feat/world-beta` at `74f9115`, checked out as `validate/world-beta`.
Inputs: the factor file `data/factors/ff5_daily.parquet` of the main checkout (read only, last date 2026-09-30). Prices: my own `yfinance` download of ACWI, SPY, ZM and EFA (`Ticker.history(period="max", auto_adjust=False, actions=True, repair=False)`, 2026-11-19), and separately the module's own cache, filled by `build_report` in a scratch data directory. Nothing from the scratch directories is committed.
Environment: Python 3.13.14, numpy 2.5.5, pandas 3.1.1, statsmodels 0.15.0, yfinance 1.8.0, Node 26.13.0, Playwright 1.65.1, Windows 11.
Scratch scripts (outside git): `own_ols.py` (my OLS and Newey-West, written before I opened the module), `own_ols_detail.py`, `real_own.py` (raw download, own alignment, own fits, lead and lag regressions), `real_module.py` (the real pipeline), `async_check.py`, `cache_live.py` (the cache against live Yahoo), `mutate.py`.

**Verdict: MERGE WITH CONDITIONS.** The numbers are right. My own implementation, written from the hand-off definitions before I read the code, reproduces the module to about 1e-15 on six synthetic designs and every printed number of the hand-off for SPY, ZM and EFA on an independent download. The alignment is an inner join with the same-interval rule, no fill and no look-ahead; both legs subtract the same RF; the sample is the M2 sample. The incremental cache works as described against live Yahoo (cold, same day, warm with five missing days equal to a full download to 0.0). Every one of my 17 mutants is caught by the existing tests. The conditions are about the interface and the behaviour under failure, not the statistics: the section's field names and comparison values do not match the DV2.6 spec the React ticket V16 will be written against (F1), and a failed ACWI refresh adds several seconds (up to minutes under a long `Retry-After`) to every report build while a cache sits on disk (F2). Two smaller items: an exact fit reports a noise alpha t instead of `null` (F4), and the cache misses a dividend that Yahoo posts more than seven days late (F3, demonstrated; small effect, owner decision).

---

## 1. Findings, ranked by severity

### F1 (medium): the section's shape and texts differ from DV2.6, which the React ticket V16 builds on

- **Where:** `backend/factordesk/report/sections/world_beta.py:33` (`ComparisonKey`), `:75` (`benchmark`), `:92-93` (`world`, `us_market` objects); `backend/factordesk/section_hooks/world_beta.py:47` (`UNAVAILABLE_REASON`); position `540` in `report/panels/world_beta.py:130` and `frontend/src/components/report/panelRegistry.ts`.
- **What differs:** DV2.6 (`git show feat/ui-v2-spec:docs/specs/dashboard-v2.md`) proposes `proxy`, flat `beta`, `se`, `ci_low`, `ci_high`, `us_beta`, `us_se`, `us_ci_low`, `us_ci_high`, and `comparison` in `about_the_same | higher | lower`. The branch has `benchmark`, nested `world` and `us_market` with `se_hac`, `ci95_low`, `ci95_high`, and `higher_against_the_world | lower_against_the_world`. DV2.6 gives the failed reason "The world fund's prices could not be fetched."; the branch writes "ACWI price data could not be fetched" (no full stop). DV1 puts the panel at 350; the branch registers 540. DV4.8 keys its copy on `higher` and `lower`.
- **Why it matters:** V16 must reproduce DV4.8 word for word from `comparison`; written to the spec, it will not compile against `types.gen.ts`, or will fall through on the two non-overlap values. The DV2.6 table says "proposed", so the branch was free to choose, but the two documents now disagree.
- **Fix:** one owner decision before V16 starts. Either amend DV2.6 and DV4.8 to the built names (the nested shape is reasonable: it mirrors `BetaFit` twice and carries R2, correlation and alpha too), or rename in the section. Align the reason text in either direction, and settle 350 against 540 when the two registries are merged (DV1 already notes that they differ until epic 18).

### F2 (medium): a failing ACWI refresh delays every report build, by seconds or minutes

- **Where:** `backend/factordesk/data/prices.py:702-707` (`_partial_refresh` goes through `_download_one` with the full retry schedule); `backend/factordesk/api/service.py:207` awaits it before the report is built.
- **Evidence:** `cache_live.py` step 4, a cache from 2026-11-10 and a download function that raises `ConnectionError`: the call returns `stale` with the right note after sleeps of 2.12, 0.56, 4.91 and 1.09 seconds (back-off and the rate limiter), about 8.7 seconds. With a rate limit, `backoff_delay` honours `Retry-After` up to `RETRY_AFTER_CAP_SECONDS = 120` (`data/throttle.py:25`), so two waits can add up to about four minutes. Because the same-day file is not written on failure (by design, so the next build tries again), every build pays it again while Yahoo is down. The stock's own `fetch` (`prices.py:451`) does a single attempt, so the secondary section costs more than the primary data.
- **Also:** the dashboard caches whole reports per (ticker, range, vintage, day) (`service.py:223`), so a report built with a stale or failed world beta is served for the rest of the day for that ticker and range. "Refreshed on every ticker load" is in practice "on every report-cache miss". Not a defect; worth one line in the decision page.
- **Fix:** when a cache exists, make one attempt and no back-off (the stale path is the fallback anyway), or remember a failed attempt for a few minutes in the provider. Keep the full retry schedule for the cold case. Add a test that counts sleeps on the stale path.

### F3 (low to medium): a dividend posted more than seven days late is missed, and the cache keeps the old basis until the next one

- **Where:** `backend/factordesk/data/prices.py:683` (`start = last - timedelta(days=REFRESH_OVERLAP_DAYS)`), `:747` (`rebased`), `:768` (`merge_histories`).
- **What I checked:** a normal dividend is caught. Yahoo multiplies every adjusted close before the ex-date by the same factor, so if the ex-date is after the cached last date the seven overlap rows change and the whole history is downloaded again (test `test_rebased_prices_trigger_a_full_download`; my mutant M8 is caught). Capital-gain distributions adjust the same way and are caught the same way. What is missed is a rewrite that leaves the last seven days unchanged: a dividend that Yahoo records after its ex-date has dropped out of the overlap, a corrected old bar, a split fixed late.
- **Evidence:** `cache_live.py` step 5. A cache whose rows older than 30 rows from the end lack a 0.7% adjustment (as if a dividend had been posted late) is refreshed `incremental`, and 4,661 of 4,691 rows of the merged history stay on the old basis. The audit cannot see it, because the cached `dividends` column is consistent with the cached prices.
- **Size of the effect:** one day's ACWI return is wrong by the dividend yield (about 0.7% to 1% for ACWI). Changing one day of SPY's 4,656 by 0.8% moves its world beta by at most 0.0008 (every 25th day tried), against a standard error of 0.0117. It heals itself at the next dividend, which rebases the overlap: ACWI distributes twice a year, so the window is at most about six months.
- **Fix (recommended):** start the incremental request at `min(last - 7 days, last cached date with a dividend or capital gain)` and compare the `dividends` and `capital_gains` columns in the overlap as well. Any dividend newer than the last cached one then lies inside the overlap and rebases it; the request is still one call with at most about six months of rows. Add a full download when the cache's last full download is older than 30 days (stamp it in the parquet attrs next to `fetched_at`); that catches corrections that are not tied to a distribution, at the cost of about one extra request a month. A checksum of the full adjusted series needs the full series, so it is the same cost as a full download and adds nothing. Note that an incremental request and a full one are each a single HTTP call; the incremental path saves payload, not requests.

### F4 (low): an exact fit returns a noise alpha t, not `null`

- **Where:** `backend/factordesk/analytics/world_beta.py:90` (`alpha_se > 0.0`); the test `test_world_beta.py:103` accepts any finite value.
- **Evidence:** `own_ols_detail.py`. `y = x` gives `se_hac = 4.7e-17` and `alpha_t = -3.03`; `y = 2x` the same `-3.03`; `y = x + 0.001` gives `alpha_t = 2.1e15`. My own code gives `-4.17` for `y = x`: the value is the ratio of two rounding errors. The hand-off (WB1.8), the dataclass docstring (`:53`) and the schema description (`sections/world_beta.py:63`) say it is `null`. A `-3.03` would print as "HAC t -3.0" in the folded text.
- **Likelihood:** nil on real prices (an exact fit needs the stock to be ACWI with RF removed identically). It is a documentation-against-behaviour mismatch.
- **Fix:** return `None` when the residual sum of squares is below a relative tolerance of the total sum of squares (for example `ssr <= 1e-20 * tss`), and assert `alpha_t is None` in TWB02. Or change the three texts to say what happens.

### F5 (low): an ACWI audit error anywhere fails the section, with a "try again later" next step

- **Where:** `backend/factordesk/section_hooks/world_beta.py:149-159`; `report/panels/world_beta.py:33,119`.
- **What is wrong:** M1.4 says an audit with errors does not block the analysis (the stock gets a banner). Here an error in any ACWI row from 2008 fails the section, even for a stock whose overlap starts in 2024. The static panel then shows "Run the report again later", which cannot help, and DV4.8's tile copy for `failed` ("The world fund's prices could not be fetched") would misstate the cause.
- **Fix:** see question (b) in section 3. Whatever is chosen, give the audit failure its own next step ("The ACWI price history has errors; this section is left out until it is corrected.") and tell V16 to show `reason` rather than the fixed fetch sentence for a non-fetch failure.

### F6 (low): the timing caveat overstates the effect for the ETF

- **Where:** `backend/factordesk/report/sections/world_beta.py:41-46` (`L-WORLD-ASYNC`).
- **Evidence:** `real_own.py` and `async_check.py`. Regressions with one-day lead and lag of the regressor: SPY on ACWI, lag -0.005, same day 0.945, lead -0.006; EFA on ACWI, lag -0.028, lead 0.009; ACWI on Mkt-RF, lag 0.010, lead 0.005. The ETF's price is set at the US close, so news after the European and Asian closes is already in it (through futures, ADRs and currencies); the stale-close problem belongs to the index and to the fund's NAV, not to the ETF's market price. ZM shows leads and lags of 0.14 to 0.20 against both ACWI and Mkt-RF alike, a property of the stock, not of the benchmark.
- **Fix (wording, owner's call):** "ACWI includes many non-US stocks whose markets close earlier than the US. The fund's price is set at the US close, so this matters less than for the index itself; it is not corrected here."

### F7 (low): the React placeholder shows an empty titled frame for an ok section

- **Where:** `frontend/src/components/report/sections/WorldBetaPanel.tsx:14-21`.
- **What is wrong:** with `status == "ok"` the dashboard shows the title and question and nothing else. The hand-off says so (placeholder), but between this merge and V16 a user sees an empty panel on every report with real factors.
- **Fix:** render `comparison_text` as the panel body until V16, or return `null` for an ok section until then.

### F8 (low): the stale note repeats "ACWI data ends" with two date formats

- **Where:** `backend/factordesk/report/panels/world_beta.py:104-107`.
- **What is wrong:** on a stale cache the footnote reads "ACWI data ends 10 November 2026. ACWI data ends 2026-11-10; the refresh did not complete (...)".
- **Fix:** print the plain sentence only when `acwi_note` is empty.

### F9 (information): numbers and texts checked and correct

- The interval uses the exact normal quantile (`Z_975`), not the rounded 1.959964 of M0.5; the difference is 3e-10 on a beta, as in every other regression of the project.
- The comparison texts claim nothing beyond the intervals and never forecast; a grep for "will", "expect", "likely", "predict", "forecast" and "significan" in the five feature files finds only "Descriptive, in-sample, not predictive."
- Test counts in the hand-off are right: 19, 31 and 14 collected.

---

## 2. What I verified and how

### 2.1 My implementation against the module (synthetic)

`own_ols.py`: OLS with intercept through `inv(X'X)`, Newey-West with Bartlett weights `1 - l/(L+1)`, sums not means, no small-sample correction, `L = floor(4 (n/100)^(2/9))`. Lag rule values: 126 and 252 give 4, 504 gives 5, 750 and 1000 give 6, 1872 gives 7, 2520 gives 8, 4656 and 5000 give 9 (the M0.5 reference values).

| Case (n 2,000 unless stated) | Beta | HAC se | OLS se | HAC / OLS | R2 | Largest difference to the module |
| --- | --- | --- | --- | --- | --- | --- |
| stock = 1.3 x + noise | 1.3381 | 0.02176 | 0.02276 | 0.96 | 0.634 | 4e-16 (beta), 3e-10 on the interval ends (quantile) |
| identical series | 1.0000 | 5e-17 | 0 | | 1.000 | alpha t: F4 |
| independent series | -0.0636 | 0.04529 | 0.04372 | 1.04 | 0.001 | 4e-17 |
| AR(1) 0.7 regressor and AR(1) 0.7 errors | 0.7873 | 0.03481 | 0.02250 | 1.55 | 0.380 | 5e-16; statsmodels HAC 0.03481103645576269 |
| heteroskedastic errors scaled by abs(x) | 0.8894 | 0.07839 | 0.04542 | 1.73 | 0.161 | 2e-16 |
| n 252, beta 1.1 | 1.1429 | 0.06973 | 0.06572 | 1.06 | 0.547 | 2e-17, L = 4 |

R2, correlation, annual alpha and its t agree to the same precision. The module calls the project's `ols_hac` with one factor column (`world_beta.py:75`). That is correct for a one-factor design: `with_intercept` adds the constant, the design guard reduces to "the factor varies", the lag rule is applied to the number of rows of this regression (the overlap, not the analysis sample), and the US-market fit reuses the same rows and the same `L`.

### 2.2 Real data, independent download and own alignment

`real_own.py` builds the sample from the raw `Adj Close` (returns by `shift(1)` on each ticker's own rows, a French date in `(previous date, date]` exactly once, finite values, dates up to 2026-09-30), applies the same-interval rule by comparing the previous ACWI date with the previous stock date, inner-joins, subtracts the same `RF` from both legs, and fits with `own_ols.py`. `real_module.py` runs `build_report` through the real provider into a scratch data directory.

| Ticker | S | n (overlap) | From, to | L | World beta | se | 95% interval | R2 | Corr | Alpha a year (t) | US beta (se, R2) | Reading |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| SPY, mine | 8,474 | 4,656 | 2008-03-31, 2026-09-30 | 9 | 0.9452 | 0.0117 | [0.922, 0.968] | 0.930 | 0.964 | +3.62% (3.59) | 0.9745 (0.0092, 0.984) | intervals overlap |
| SPY, module | 8,474 | 4,656 | same | 9 | 0.94516 | 0.01167 | [0.9223, 0.9680] | 0.9301 | 0.9644 | +3.62% (3.59) | 0.97452 (0.00916, 0.9838) | about_the_same |
| ZM, mine | 1,872 | 1,872 | 2019-04-22, 2026-09-30 | 7 | 0.7610 | 0.2053 | [0.359, 1.163] | 0.068 | 0.261 | +8.29% (0.46) | 0.7756 (0.2022, 0.083) | overlap |
| ZM, module | | 1,872 | same | 7 | 0.76095 | 0.20530 | [0.3586, 1.1633] | 0.0682 | 0.2611 | +8.29% (0.46) | 0.77564 (0.20224, 0.0835) | about_the_same |
| EFA, mine | 6,309 | 4,656 | 2008-03-31, 2026-09-30 | 9 | 1.0278 | 0.0144 | [1.000, 1.056] | 0.906 | 0.952 | -3.01% (-2.31) | 0.9536 (0.0246, 0.776) | overlap |
| EFA, module | 6,309 | 4,656 | same | 9 | 1.02780 | 0.01441 | [0.99956, 1.05604] | 0.9061 | 0.9519 | -3.01% (-2.31) | 0.95362 (0.02461, 0.7761) | about_the_same |

Every number of the hand-off's section 5 is reproduced to the printed digits. SPY drops 3,818 sample days before ACWI's first return (module `n_not_in_benchmark` 3,818); no SPY or EFA date after 2008-03-28 is missing from ACWI or the reverse, so the same-interval rule removes nothing on these tickers. EFA's two intervals overlap by 0.0023 (world lower end 0.99956, US upper end 1.00185), so "about the same" is right but close. For SPY the HAC standard error is three times the OLS one (0.0117 against 0.0038): the residual of SPY on ACWI is strongly heteroskedastic (crises), which is what HAC is for.

### 2.3 Is SPY's world beta below 1 plausible?

Yes. Beta is correlation times the volatility ratio: 0.964 x (0.01240 / 0.01265 = 0.980) = 0.945. Over 2008 to 2026 ACWI's daily excess return was slightly more volatile than SPY's; the non-US part (and its currencies) adds variance that SPY does not share. By calendar year the beta is below 1 from 2009 to 2017 (0.82 to 0.95, the euro and emerging-market years) and about 1.0 to 1.1 from 2018 to 2025, so the full-sample 0.945 is an average over regimes, not an artefact. The reverse regression (ACWI on SPY) is 0.984.

Asynchronous closes play almost no role for the ETF: the lead and lag coefficients of SPY on ACWI are -0.006 and -0.005, and the sum of the three (0.933) is below the same-day value, not above it. That is what one expects from a fund priced at the US close (F6). The hand-off's other remark, that the US-market beta of 0.975 is below 1 because Mkt-RF includes small caps, is consistent with SPY's negative SMB loading but I did not test it further.

### 2.4 Code reading

- **Alignment** (`analytics/world_beta.py:120-147`): dates are those of `S`; the ACWI return is `total_returns.reindex(S)`, so a missing date is NaN, never filled. A date is kept only if ACWI's previous row date equals the stock's previous row date and the return is finite. ACWI's first date has no previous date, so it drops. No row after `t` is read for `t`: no look-ahead.
- **RF:** `bench_xret = b - sample.rf` and `stock_xret = sample.xret` (which is `r - RF` by M2 step 5): the same RF series on the same dates. `mkt_rf` is taken as published.
- **Exclusions:** everything starts from the analysis sample `S`, so M2's exclusions (multi-day returns, missing factor rows, missing prices, range) apply unchanged. `n_not_in_benchmark = n_sample - n`.
- **Comparison** (`:150-180`): touching intervals count as overlapping (`<=`); otherwise the larger point estimate names the direction. With overlapping intervals the text is always "About the same", whatever the point estimates.
- **Statuses** (`section_hooks/world_beta.py`): no history gives `failed` with the reason and the cause in `acwi_note`; audit errors `failed`; under 252 days `insufficient_data` with `n`, `start`, `end`; a constant benchmark `DegenerateInputError` caught as `failed`; any other exception caught. The schema validator forbids numbers on a non-ok section. The report builds in every case (TWB30, my mutants M9 and M10).
- **Wiring:** offline (`factors` injected) fetches nothing; `build_report` passes its own provider; the API loads the benchmark per report build outside the per-day section-input cache.

### 2.5 The incremental cache against live Yahoo (`cache_live.py`)

| Step | Result |
| --- | --- |
| Cold (no file) | one `period=max` request, `full`, 4,691 rows |
| Same day again | `cached`, no request |
| Cache dated 2026-11-10 missing its last five rows | one request `start=2026-11-03`, `incremental`, merged frame equal to the full download in every column (largest difference 0.0); live Yahoo returns the overlap rows identically, so the 1e-6 tolerance does not trigger needless full downloads |
| Same cache, network failing | `stale`, note "ACWI data ends 2026-11-10; the refresh did not complete (Could not reach Yahoo for ACWI after 3 tries. ...), so the cached history was used.", no new file written; about 8.7 seconds of sleeps (F2) |
| Late-posted dividend more than 7 days back | `incremental`, 4,661 rows left on the old basis (F3) |

From the unit tests and code: up to date on a weekday or weekend means no call (`latest_completed_session` steps back over Saturday and Sunday in New York time); a corrupt newest file means a full download; no common row counts as rebased. Throttling: the refresh goes through `_download_one`, so retries, back-off, the rate-limit message and the circuit breaker are the batch path's. The rate limiter is created per call, so it does not space the ACWI request against the stock's single request; with two requests per report build that is harmless. Concurrent builds are serialised by the `ACWI#refresh` lock, and the second one reads the file the first wrote.

---

## 3. The builder's open questions

**(a) "Many non-US stocks" or "mostly non-US".** Keep "many". The MSCI ACWI Index factsheet dated 30 October 2026 (msci.com, document `a71b65b5-d0ea-4b5c-a709-24b1213bc3c5`, "Country weights") gives United States 64.63%, Japan 5.08%, Taiwan 3.23%, United Kingdom 3.12%, Canada 3.06%, other 20.88%. By weight the index is about two thirds US, so "mostly non-US" would be false today. The US share was lower in 2008 (I have no cited figure; unverified), which is why "their share varies over time" is a fair addition. I would not put a percentage in the panel, because it goes stale.

**(b) Should an ACWI audit error outside the overlap fail the section?** No. Recommended rule: audit errors dated inside the overlap (from the ACWI row before the first overlap date to the last overlap date) fail the section with an audit-specific reason and next step (F5); errors outside it are carried in `audit_warnings` with one sentence saying they lie outside the days used. The current rule lets one bad 2008 row remove the section from every report, including stocks whose overlap is recent. Failing (rather than M1.4's "banner and carry on") inside the overlap is defensible for a secondary view whose only regressor would be wrong; the owner may prefer DV4.8's "Unconfirmed" note instead, for consistency with the stock.

**(c) The incremental cache missing older-row rewrites.** The risk is real but small (F3): a dividend recorded late, or a corrected old bar, leaves part of the history on the old basis, silently, until the next distribution; the effect on a beta is under a tenth of its standard error. Recommended fix: overlap from the last cached distribution date (not only seven days), compare the dividend and capital-gain columns too, and a full download when the last full one is older than 30 days. Not a merge blocker if recorded as a follow-up.

The other questions (methodology text M-WB, contract amendments, alpha prominence, holidays, another proxy) are owner decisions with no validation finding against them. The holiday behaviour is as described: one request and one same-day file on a holiday.

---

## 4. Tests: what is covered

The hand-off's claims TWB01 to TWB46 and the 14 cache tests exist and pass. Covered with an oracle that does not come from the module: OLS against closed forms and `np.polyfit` (TWB05), HAC against statsmodels with `maxlags=L` and `use_correction=False` (TWB06), the overlap counts on hand-built date sets (TWB09 to TWB13), the comparison on hand-built intervals (TWB14 to TWB17), the threshold at 252 and 251 (TWB24), the cache with injected download functions (no network). Not covered: the exact-fit alpha t (TWB02 accepts any finite value, F4), the number of sleeps on the stale path (F2), an older-row rewrite (F3).

## 5. Mutation results

`mutate.py` applies one change at a time to the feature code, runs `test_world_beta.py`, `test_section_world_beta.py`, `test_prices_incremental.py`, `test_schema_contract.py` and `test_prices.py` (129 tests), and restores the file. All 17 mutants are killed.

| Mutant | Killed by |
| --- | --- |
| M1 no intercept (slope through the origin) | TWB04, TWB05 |
| M2 RF not subtracted on the benchmark | TWB09, TWB10, TWB12, TWB26 |
| M3a classical OLS standard error instead of HAC | TWB06 |
| M3b HAC with zero lags (White) | TWB01, TWB06, TWB18, TWB20 |
| M4 left join on the stock's dates with forward-filled ACWI prices | TWB13 |
| M4b same-interval rule removed, inner join kept | TWB12 |
| M5a touching intervals counted as not overlapping | TWB15 |
| M5b "about the same" only when the US beta lies inside the world interval | TWB15 |
| M5c higher and lower swapped | TWB16, TWB20, TWB46 |
| M6 cache never refreshed once a file exists | 5 cache tests (warm, failed refresh, rebased, no new bar) and TWB35 |
| M7a threshold `<=` 252 | TWB24[252-ok] |
| M7b threshold 251 | TWB24[251-insufficient_data] |
| M8 rebase check disabled | `test_rebased_prices_trigger_a_full_download`, `test_rebased_needs_a_common_row` |
| M9 ACWI audit errors ignored | TWB27 |
| M10 failed refresh with a cache treated as no cache | `test_failed_refresh_with_a_cache_...`, TWB35 |
| M11 alpha t always `None` | TWB06, TWB18 |
| M12 RF of the previous day used on both legs | TWB09, TWB10, TWB12, TWB26 |

M3a is caught by one test only (TWB06); it is the right test (statsmodels HAC reference). I added no tests.

## 6. Gates (run in this worktree, 2026-11-19)

| Gate | Result |
| --- | --- |
| `uv run pytest -q` | 910 passed, 227 deselected (live and slow markers), 1 warning (Starlette test client deprecation) |
| `uv run ruff check backend` | All checks passed |
| `uv run ruff format --check backend` | 110 files already formatted |
| `uv run pyright` | 0 errors, 0 warnings, 0 informations |
| `npm run typecheck` | no errors |
| `npm run lint` | no errors |
| `npm test` | 34 files, 491 tests passed (a first run made while the mutation harness loaded the machine had 1 failure; the clean rerun passed, so I count it as a timing flake, not a finding) |
| `npm run build` | built |
| `npm run size` | initial JS 396.1 kB raw, 121.3 kB gzip (budget 400 / 125) |
| `npm run e2e` | 1 passed (dashboard smoke on the fake backend) |
| `openapi_dump` and `npm run gen:types` | no diff |

## 7. Conditions before merge

1. **F1:** the owner decides the field names, comparison values, failed reason and panel position, and either DV2.6 and DV4.8 are amended or the section is renamed, before V16 starts.
2. **F2:** bound the stale path: one attempt without back-off when a cache exists (or a short remembered failure), with a test that counts the sleeps.
3. **F4:** make the exact-fit alpha t `None` as documented (and assert it in TWB02), or correct the three texts.

Recommended, not blocking: F3 (overlap from the last cached distribution and a monthly full download), F5 with the answer to question (b), F6 wording, F7 placeholder body, F8 duplicate note. The owner's answers to questions (a), (b) and (c) are in section 3.
