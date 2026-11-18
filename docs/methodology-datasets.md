# factordesk dataset methodology (regional factor files, FX, vintages)

Status: v1 specification, written 2026-11-18. Extends `docs/methodology.md` M1 (data inputs). Facts about the files are in `docs/datasets.md` (evidence codes P1-P7, C1-C10, discrepancies X1-X13, unverified items U1-U8). Tests are in `docs/test-oracle-datasets.md` (TD01-TD51). The standing rules for new statistics are in `docs/research-protocol.md`.

Rule of precedence: `docs/methodology.md` M0-M3 stay binding. Where this document needs a change to them, the change is listed in **D16** as a proposed amendment; until the owner accepts it, the M-section wins and the D-section describes an addition only. Every number below is either a computation from `docs/datasets.md` (code given) or marked [U].

---

## D1. Scope

- 14 datasets: the daily 5-factor file and the daily momentum file for 7 regions (US, Europe, Developed, Developed ex US, Japan, North America, Asia Pacific ex Japan). Monthly files are used only for the RF rule in D11 and for the replication checks in D12.
- Every dataset goes through one registry (D2), one parser (D3), one cache layout (D4) and one vintage record (D5).
- Out of scope for v1: emerging-market files, 3-factor files, portfolio files, country-level factors (the library publishes none for the developed regions).

## D2. Dataset registry (`data/factor_registry.py`)

### D2.1 Keys

Region keys (fixed, lower case): `us`, `europe`, `developed`, `developed_ex_us`, `japan`, `north_america`, `asia_pacific_ex_japan`.
Family keys: `ff5`, `mom`. Dataset key: `<region>_<family>_daily`, for example `europe_ff5_daily`, `us_mom_daily`.

### D2.2 Entries

The registry is an immutable tuple of frozen `DatasetSpec` records plus `REGISTRY_VERSION` (an integer, incremented on any change). URLs are built from one base constant, `https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/`, plus the exact file name of the P1 link (the server is case-insensitive, `docs/datasets.md` section 5, but the registry spelling must match P1 so a live test can compare them).

| Key | File name | Description page | Header tokens | Canonical columns | Source in preamble | First date | Min rows | Calendar |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `us_ff5_daily` | `F-F_Research_Data_5_Factors_2x3_daily_CSV.zip` | P6 | `"", Mkt-RF, SMB, HML, RMW, CMA, RF` | `mkt_rf, smb, hml, rmw, cma, rf` | CRSP | 1963-07-01 | 15,000 | exchange |
| `europe_ff5_daily` | `Europe_5_Factors_Daily_CSV.zip` | P2 | same | same | Bloomberg | 1990-07-02 | 9,000 | all weekdays |
| `developed_ff5_daily` | `Developed_5_Factors_Daily_CSV.zip` | P2 | same | same | Bloomberg | 1990-07-02 | 9,000 | all weekdays |
| `developed_ex_us_ff5_daily` | `Developed_ex_US_5_Factors_Daily_CSV.zip` | P2 | same | same | Bloomberg | 1990-07-02 | 9,000 | all weekdays |
| `japan_ff5_daily` | `Japan_5_Factors_Daily_CSV.zip` | P2 | same | same | Bloomberg | 1990-07-02 | 9,000 | all weekdays |
| `north_america_ff5_daily` | `North_America_5_Factors_Daily_CSV.zip` | P2 | same | same | Bloomberg | 1990-07-02 | 9,000 | all weekdays |
| `asia_pacific_ex_japan_ff5_daily` | `Asia_Pacific_ex_Japan_5_Factors_Daily_CSV.zip` | P2 | same | same | Bloomberg | 1990-07-02 | 9,000 | all weekdays |
| `us_mom_daily` | `F-F_Momentum_Factor_daily_CSV.zip` | P7 | `"", Mom` | `mom` | CRSP | 1926-11-03 | 26,000 | exchange |
| `europe_mom_daily` | `Europe_Mom_Factor_Daily_CSV.zip` | P3 | `"", WML` | `mom` | Bloomberg | 1990-11-01 | 9,000 | all weekdays |
| `developed_mom_daily` | `Developed_Mom_Factor_Daily_CSV.zip` | P3 | `"", WML` | `mom` | Bloomberg | 1990-11-01 | 9,000 | all weekdays |
| `developed_ex_us_mom_daily` | `Developed_ex_US_Mom_Factor_Daily_CSV.zip` | P3 | `"", WML` | `mom` | Bloomberg | 1990-11-01 | 9,000 | all weekdays |
| `japan_mom_daily` | `Japan_Mom_Factor_Daily_CSV.zip` | P3 | `"", WML` | `mom` | Bloomberg | 1990-11-01 | 9,000 | all weekdays |
| `north_america_mom_daily` | `North_America_Mom_Factor_Daily_CSV.zip` | P3 | `"", WML` | `mom` | Bloomberg | 1990-11-01 | 9,000 | all weekdays |
| `asia_pacific_ex_japan_mom_daily` | `Asia_Pacific_ex_Japan_MOM_Factor_Daily_CSV.zip` | P3 | `"", WML` | `mom` | Bloomberg | 1990-11-01 | 9,000 | all weekdays |

Further fields of every `DatasetSpec` (same for all entries unless stated):

- `monthly_file_name` (ff5 only, for D11): `F-F_Research_Data_5_Factors_2x3_CSV.zip` for `us`, `<Region>_5_Factors_CSV.zip` otherwise.
- `declared_sentinels`: `{-99.99}` for regional files (preamble), `{-99.99, -999}` for US files (P1, US momentum preamble).
- `factor_bound = 0.5` (decimal, after division by 100) for every factor column; `rf_bounds = [-0.0001, 0.002]` (M1.1 step 8); observed maxima are 0.1744 (US Mkt-RF) and 0.0006 (US RF) (C1).
- `decimals = 2` (C1).
- `footer`: `"copyright"` for US files, `"none"` for regional files. A mismatch is a warning, never an error (the footer carries no data).
- `region_countries`: the country list of `docs/datasets.md` section 3, used only for labels.
- `currency = "USD"`.

`MIN_ROWS` stops being a module constant (the existing `backend/factordesk/data/factors.py` has `MIN_ROWS = 15_000`, which would reject every regional file, X12). Minimum rows are per spec.

## D3. One parser for all layouts (`data/factor_parser.py`)

Pure function `parse_factor_zip(raw: bytes, spec: DatasetSpec) -> ParsedFactorFile` (raises `SchemaError`). It keeps M1.1 steps 1-9 and generalises them.

1. Zip checks: the bytes start with the zip magic `PK\x03\x04` (an HTML error page served with status 200 fails here); total decompressed size `<= 20 MB`; exactly one member whose name ends in `.csv`, compared case-insensitively. The member name is recorded but not matched (regional momentum members are `..._MOM_Factor_Daily.csv` inside `..._Mom_...zip`, X4).
2. Decode latin-1, universal newlines (M1.1 step 2). All real files are ASCII (X7), so latin-1 never changes a byte.
3. Stamp: the first non-blank line must match `^This file was created (?:by )?using the (\d{6}) (CRSP|Bloomberg) database\.` The pattern is not anchored at the end (the US momentum line continues: "...database.  It"). The source group must equal `spec.source`; the stamp must be a valid `YYYYMM`. No match = `SchemaError("stamp_not_found")`.
4. Header: first line whose stripped text starts with `,`; tokens (split on `,`, each stripped) must equal `spec.header_tokens` exactly. Columns are renamed to `spec.canonical_columns` (`WML` and `Mom` both become `mom`).
5. Data rows: lines after the header matching `^\s*\d{8}\s*,` (this covers the regional padding `19900702    ,0.99`). After stripping, the field count equals the token count. Dates parse strictly as `YYYYMMDD`.
6. Block end: as M1.1 step 5. Regional files have no footer; US files end with a copyright line. Either is accepted.
7. Sentinels: any value equal to `-99.99` or `-999` (any trailing zeros) becomes NaN, recorded as `(date, column)`, for every dataset. A sentinel not in `spec.declared_sentinels` adds warning `undeclared_sentinel`. Observed count is 0 in all 14 files (C1).
8. Precision: record the largest number of decimals seen; if it is not `spec.decimals`, add warning `precision_changed` (a format change at the source must be noticed, D11 depends on it).
9. Divide by 100.
10. Validation (errors): dates strictly increasing and unique; no Saturday or Sunday rows; `|factor| <= 0.5`; RF in `rf_bounds`; row count `>= spec.min_rows`.
11. Validation (warnings, the file is still accepted): first date differs from `spec.first_date` (`history_start_changed`); for `all_weekdays` calendars, any weekday between first and last date missing (`calendar_gap`, with the list); footer differs from `spec.footer`.
12. Output: frame with the canonical columns, plus `ParseInfo` (stamp, source, member name, member zip timestamp, n rows, first/last date, sentinel list, max decimals, warnings).

Per-dataset differences live in the spec only. There is no branch on the dataset key inside the parser (`CODING_STANDARDS.md` section 8).

## D4. Cache layout (`data/factor_cache.py`)

```text
data/factors/<dataset_key>/
    factors.parquet          # current vintage, canonical columns, index `date`
    meta.json                # D4.1
    revisions.jsonl          # one line per refresh that changed history (D5.3)
    vintages/<stamp>_<sha256[:12]>.zip   # raw bytes of every vintage ever accepted
```

- Writes follow M1.1 step 11 (temp file in the same directory, flush, fsync, `os.replace`). The raw zip is written before the parquet; a failed parse never touches either.
- The legacy cache `data/factors/ff5_daily.parquet` + `meta.json` (current repo) is not migrated: on first run of the registry the US dataset is downloaded into `data/factors/us_ff5_daily/`. The legacy files are left in place and ignored. (Its recorded SHA-256 equals the vintage in `docs/datasets.md` 5.1, so nothing is lost.)
- Raw zips are 30-150 KB each (C1); keeping every vintage costs about 2 MB a year for all 14 datasets plus 7 monthly files. `references.md` forbids storing factor data **in the repository**; `data/` is a local cache, and `.gitignore` contains `/data/` (checked 2026-11-18), so the archive never enters the repository.

### D4.1 `meta.json` (one per dataset)

| Field | Type | Source |
| --- | --- | --- |
| `dataset_key` | str | registry |
| `registry_version` | int | registry |
| `parser_version` | str | parser module constant |
| `source_url`, `description_url` | str | registry |
| `downloaded_at` | ISO 8601 UTC | injected clock |
| `http_last_modified`, `http_etag`, `http_content_length` | str / str / int | response headers |
| `sha256`, `bytes` | str / int | raw zip |
| `zip_member`, `zip_member_datetime` | str / str | zip directory (naive local time, recorded as written) |
| `file_stamp`, `source_database` | `YYYYMM` / str | D3 step 3 |
| `first_date`, `last_date`, `n_rows`, `n_sentinels`, `max_decimals` | | parser |
| `parse_warnings` | list[str] | parser |
| `last_attempt_at`, `last_attempt_ok`, `last_attempt_error` | | refresh logic (M1.2) |
| `monthly_sha256`, `monthly_file_stamp` | ff5 only | D11 |

## D5. Vintages and reproducibility (`data/vintage.py`)

### D5.1 What every report records

`SampleInfo.factor_vintage` (M0.8) becomes a list with one entry per dataset used: `dataset_key`, `file_stamp`, `sha256`, `http_last_modified`, `downloaded_at`, `last_date`, plus `monthly_sha256` when D11's RF rule is used. FX and price inputs record the provider, ticker, download time and a SHA-256 of the serialised frame used. With these, `reproduce(report)` loads the archived zips by SHA-256 (D4), re-parses them with the recorded `parser_version`, and must produce identical numbers (test TD34).

### D5.2 Label

L-VINTAGE (M0.9) gains the stamp: "Factor data: {dataset} release {stamp} (SHA-256 {sha[:12]}), downloaded {date}. The library revises history; numbers from another release can differ."

### D5.3 Revision detection (on every accepted refresh)

Compare the new frame with the previous vintage of the same dataset on their common dates:

- `revised_cells`: `|new - old| > 5e-5` (half of the last published digit, M1.1 step 10), per column: count, max absolute change, first and last date.
- `history_rewritten` (warning): a date present in the old vintage and absent from the new one, or a change of `first_date`.
- `appended_rows`: dates after the old `last_date`.
- One JSON line per refresh in `revisions.jsonl`: old and new stamp and SHA-256, the three items above.
- Surfacing: the report shows a banner when any dataset it uses has `revised_cells > 0` between the vintage of the last report for the same ticker (if stored) and the current one; the factor dashboard lists the latest revision summary per dataset.

## D6. Staleness and refresh, per dataset

- M1.2 applies to each dataset separately: `days_behind = today - last_date`, `stale = days_behind > 40`, 12-hour attempt rule, HEAD shortcut on `Last-Modified`.
- HEAD is sent per file. Observed release (`docs/datasets.md` 6.6): all 12 regional files changed within 40 seconds on 2026-10-26, the US files a day later, all with stamp 202609. A fresh HEAD on one file therefore says nothing about another file; one release does not prove the library always updates together (U6).
- Group coherence: all datasets used in one report (for example `europe_ff5_daily` + `europe_mom_daily`, plus a monthly file for D11) must share the same `file_stamp`; otherwise warning `mixed_vintage`, and a manual refresh of the group is offered. Different `last_date` with the same stamp is an error (`SchemaError`-class finding `stamp_date_mismatch`).
- A report that uses a regional dataset refreshes that group on demand, not all 14 datasets.

## D7. Ticker-to-region assignment (`data/regions.py`)

### D7.1 Rule

Region follows the **listing whose prices are regressed** (its currency and trading hours define the return series), not the company's domicile. Order:

1. Explicit user choice of a dataset key: used, with caveat `user_selected_factors` when it differs from rules 2-3.
2. Suffix (text after the last `.` of the yfinance symbol) found in table D7.2: its region.
3. No suffix: `us` (current behaviour, M1). A US-listed ADR stays `us`, with caveat "ADR of a non-US company: factors describe the ADR's USD return in the US market."
4. Suffix in D7.3 (known venue, not supported): refuse with the reason given there.
5. Any other suffix: refuse, error `unknown_exchange_suffix` naming the suffix.

**Decision: refuse instead of a default for 4-5.** A silent fallback to US or Developed factors would regress a non-US stock on factors from another market and another time zone. M1.5 already calls the US-factor case a mix of factor exposure, currency and local-market effects, and D14 shows a same-day daily beta of a Japanese return on North American factors is 0.049 against 0.585 with the lagged day (C6). A wrong default produces confident wrong numbers; a refusal with a reason produces none, and rule 1 lets the user override knowingly.

Currency comes from ticker metadata (`currency`), never from the suffix. The suffix table's currency column is a cross-check: a mismatch gives warning `currency_differs_from_market_default` and the metadata wins (some `.L` lines trade in USD or EUR [U: no example verified]).

### D7.2 Supported suffixes

Suffix, exchange and country are quoted from Yahoo's help page "Yahoo Finance Market Coverage and Data Delays", <https://help.yahoo.com/kb/SLN2310.html> (fetched 2026-11-18, HTTP 200) [V]. Region from `docs/datasets.md` section 3 [V]. Currency is [V] where Yahoo's chart API (`query1.finance.yahoo.com/v8/finance/chart/<symbol>`, 2026-11-18) returned that `currency` for the example symbol, otherwise [U].

| Suffix | Exchange (Yahoo wording) | Country | Region key | Default currency | Currency evidence |
| --- | --- | --- | --- | --- | --- |
| `.VI` | Vienna Stock Exchange | Austria | `europe` | EUR | U |
| `.BR` | Euronext Brussels | Belgium | `europe` | EUR | U |
| `.SW` | Swiss Exchange (SIX) | Switzerland | `europe` | CHF | V (NESN.SW: CHF) |
| `.DE` | Deutsche Boerse XETRA | Germany | `europe` | EUR | V (SAP.DE: EUR) |
| `.CO` | Nasdaq OMX Copenhagen | Denmark | `europe` | DKK | V (NOVO-B.CO: DKK) |
| `.MC` | Madrid Stock Exchange (BME) | Spain | `europe` | EUR | U |
| `.HE` | Nasdaq OMX Helsinki | Finland | `europe` | EUR | U |
| `.PA` | Euronext Paris | France | `europe` | EUR | U |
| `.L` | London Stock Exchange | United Kingdom | `europe` | GBp (pence) | V (VOD.L: `GBp`) |
| `.AT` | Athens Stock Exchange (ATHEX) | Greece | `europe` | EUR | U |
| `.IR` | Euronext Dublin | Ireland | `europe` | EUR | U |
| `.MI` | Italian Stock Exchange | Italy | `europe` | EUR | U |
| `.AS` | Euronext Amsterdam | Netherlands | `europe` | EUR | U |
| `.OL` | Oslo Stock Exchange | Norway | `europe` | NOK | V (EQNR.OL: NOK) |
| `.LS` | Euronext Lisbon | Portugal | `europe` | EUR | U |
| `.ST` | Nasdaq OMX Stockholm | Sweden | `europe` | SEK | V (VOLV-B.ST: SEK) |
| `.NX` | Euronext (country "Europe") | not identified | `europe` | EUR | U |
| `.T` | Tokyo Stock Exchange | Japan | `japan` | JPY | V (7203.T: JPY) |
| `.AX` | Australian Stock Exchange (ASX) | Australia | `asia_pacific_ex_japan` | AUD | V (BHP.AX: AUD) |
| `.HK` | Hong Kong Stock Exchange (HKEX) | Hong Kong | `asia_pacific_ex_japan` | HKD | V (0005.HK: HKD) |
| `.NZ` | New Zealand Stock Exchange (NZX) | New Zealand | `asia_pacific_ex_japan` | NZD | U |
| `.SI` | Singapore Stock Exchange (SGX) | Singapore | `asia_pacific_ex_japan` | SGD | U |
| `.TO` | Toronto Stock Exchange (TSX) | Canada | `north_america` | CAD | V (SHOP.TO: CAD) |
| `.V` | TSX Venture Exchange (TSXV) | Canada | `north_america` | CAD | U |
| (none) | US exchanges | United States | `us` | USD | (M1) |

Exchange time zones returned by the chart API [V, 2026-11-18]: Europe/London (LSE), Europe/Berlin (XETRA), Europe/Zurich (SIX), Europe/Stockholm, Europe/Copenhagen, Europe/Oslo, Asia/Tokyo, Australia/Sydney, Asia/Hong_Kong, America/Toronto.

### D7.3 Known venues that are refused

| Suffixes | Reason code | Why |
| --- | --- | --- |
| `.F .BE .BM .DU .HM .HA .MU .SG` (German regional exchanges), `.IL` (LSE second line, same Yahoo page), `.XD .XC .AQ .TI .XA .NE .CN` (Cboe Europe, Cboe UK, Aquis, EuroTLX, Cboe Australia, Cboe Canada, Canadian Securities Exchange) | `secondary_venue` | Often secondary quotes of companies listed elsewhere; prices are thin and driven by the home market. The message asks for the primary listing. |
| Every other equity suffix on SLN2310 (for example `.WA` Poland, `.TA` Israel, `.KS` Korea, `.NS` India, `.SS` China, `.TW` Taiwan, `.IC` Iceland, `.SA` Brazil) | `market_not_in_library_regions` | The country is in none of the six regional samples (`docs/datasets.md` section 3). |
| `=X`, `.CBT`, `.CME`, `.NYB`, `.CMX`, `.NYM` | `not_an_equity` | Currencies and futures. |

## D8. Regional or global factors for a given ticker

### D8.1 Literature (verified before use)

| Paper | Bibliographic check | What its abstract says (quoted) |
| --- | --- | --- |
| Griffin, J. M. (2002). Are the Fama and French factors global or country specific? *Review of Financial Studies*, 15(3), 783-803. doi:10.1093/rfs/15.3.783 | V (Crossref API: volume 15, issue 3, pages 783-803, April 2002) | "domestic factor models explain much more time-series variation in returns and generally have lower pricing errors than does the world factor model" ... "the addition of foreign factors to domestic models leads to less accurate in- and out-of-sample pricing. Practical applications of the three-factor model, such as cost-of-capital calculations and performance evaluation, are best performed on a country-specific basis." (abstract via OpenAlex) |
| Fama, E. F., and French, K. R. (2012). Size, value, and momentum in international stock returns. *Journal of Financial Economics*, 105(3), 457-472. doi:10.1016/j.jfineco.2012.05.011 | V (Crossref; IDEAS/RePEc) | "Integrated pricing across regions does not get strong support in our tests. For three regions (North America, Europe, and Japan), local models that use local explanatory returns provide passable descriptions of local average returns for portfolios formed on size and value versus growth. Even local models are less successful in tests on portfolios formed on size and momentum." (abstract, <https://ideas.repec.org/a/eee/jfinec/v105y2012i3p457-472.html>) |
| Fama, E. F., and French, K. R. (2017). International tests of a five-factor asset pricing model. *Journal of Financial Economics*, 123(3), 441-463. doi:10.1016/j.jfineco.2016.11.004 | V (Crossref; IDEAS/RePEc) | "Average stock returns for North America, Europe, and Asia Pacific increase with the book-to-market ratio (B/M) and profitability and are negatively related to investment. For Japan, the relation between average returns and B/M is strong, but average returns show little relation to profitability or investment. A five-factor model that adds profitability and investment factors to the three-factor model of Fama and French (1993) largely absorbs the patterns in average returns." (abstract, <https://ideas.repec.org/a/eee/jfinec/v123y2017i3p441-463.html>) |

What is not verified: the papers' tables and body text (paywalled; SSRN returned HTTP 403). A search-engine summary claimed FF (2017) finds a global five-factor model performs poorly; that sentence is not in the abstract and is **not relied on** [U]. All three papers are about **average returns and pricing errors of portfolios** (asset pricing tests). factordesk uses the factors for something narrower: describing one stock's time-series exposures. The papers support "local factors describe local returns better" (Griffin explicitly for time-series variation); they do not test our single-stock use.

Caveats on applying them: Griffin compares country factors with world factors; the library offers regional factors (Europe pools 16 countries), which sit between the two. FF (2012) find local models "passable", and less successful for momentum portfolios.

### D8.2 Decision

| Listing region (D7) | Default factor dataset | Robustness alternative (shown only through the protocol's robustness grid) | Never by default |
| --- | --- | --- | --- |
| `us` | `us_ff5_daily` (CRSP; M1 binding) | `north_america_ff5_daily` | Developed (asynchronous with Asia/Europe components, D14) |
| `europe` | `europe_ff5_daily` | `developed_ff5_daily`, `developed_ex_us_ff5_daily` | US factors |
| `japan` | `japan_ff5_daily` | `developed_ex_us_ff5_daily` | Developed or US factors on daily data (C6: same-day corr with NA 0.040) |
| `asia_pacific_ex_japan` | `asia_pacific_ex_japan_ff5_daily` | `developed_ex_us_ff5_daily` | Developed or US on daily data |
| `north_america` (Canada) | `north_america_ff5_daily` | `us_ff5_daily` | - |

Notes: North America is US-dominated (no weight series is published; C5 shows NA's weight in Developed of 0.35-0.69, which says nothing about Canada's share inside NA [U]). For Canadian stocks this is the closest available regional set; the report states "No Canada-only factors exist in the library." Asia Pacific ex Japan mixes four markets with different closes [U exact hours].

## D9. USD conversion and the currency regressor (`data/fx.py`, `analytics/sample.py`)

### D9.1 Return in USD

For a stock quoted in local currency `L` (from metadata, D7):

- `r_loc_t` = simple daily return from `Adj Close` in quote units (M1.3, unchanged).
- `x_t` = USD price of one unit of `L` on the stock's date `t` (D9.3). `r_fx_t = x_t / x_{t-1} - 1`, computed over **the same two dates** as `r_loc_t` (the stock's previous row and current row), never over the FX series' own previous row.
- `r_usd_t = (1 + r_loc_t)(1 + r_fx_t) - 1` (exact identity, tested to `1e-15`).
- `y_t = r_usd_t - RF_t`, with `RF_t` from the factor dataset (D11). Currency `USD`: `r_fx = 0` exactly, no FX series is fetched.
- Missing `x_t` or `x_{t-1}`: the row is excluded, reason `fx_missing`. Nothing is filled (`CODING_STANDARDS.md` section 3).

### D9.2 Pence and other sub-units

- `GBp` (verified for VOD.L, D7.2) means pence. Returns are scale-free, so `r_loc` is the same in pence or pounds. The FX series is GBP's; the unit only matters for (a) the FX lookup (`GBp` maps to `GBP`), (b) the audit (M1.4), whose tolerance `0.01 / C` assumes a price tick of 0.01 quote units [U for LSE tick sizes; the audit stays in quote units, so the formula is unchanged], (c) dividends.
- Unit consistency of `Dividends` vs `Close` for `GBp` tickers is [U] (not checked against yfinance). Rule: if every A6 dividend event of a ticker fails and `D_implied / D` is within 3% of 100 or of 0.01 for all of them, the audit emits one warning `dividend_unit_mismatch` instead of one error per event; regression returns still come from `Adj Close` (M1.4), so the regression is not affected.
- Unit switch inside the price series: a close ratio `rho_t` within 3% of 100 or of 0.01 on a non-split day is an error `currency_unit_switch` (an addition to A5b).

### D9.3 FX source and timing

Facts:

- ECB euro reference rates: "They are based on the daily concertation procedure between central banks across Europe, which normally takes place around 14:10 CET." and "The reference rates are usually updated at around 16:00 CET every working day, except on TARGET closing days." (<https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/index.en.html>, fetched 2026-11-18) [V]. The same page says "The reference rates are published for information purposes only."
- Yahoo daily FX bars (`EURUSD=X`, `GBPUSD=X`, `CHFUSD=X`, `JPYUSD=X`, 2004-01-01..2025-09-30) carry a timestamp of 00:00 Europe/London [V, chart API metadata `exchangeTimezoneName: Europe/London`]. The meaning of their `Close` **changed over time** [V, C9]: median `|Close/Open - 1|` was 37-59 bp a year in 2004-2008 with `Close` within 2 bp of the next bar's `Open` (an end-of-day quote); from August 2010 the monthly median flips, and by 2023-2025 99-100% of bars have `|Close/Open - 1| < 1 bp` (`Close` is a start-of-day quote). Two events show it: CHF on 2015-01-15 (SNB) has high 1.3648 but close 0.98142, open 0.98135; GBP on the bar of 2016-06-24 (EU referendum) has low 1.3239 but close 1.45579, open 1.45601.
- Yahoo FX contains reversing spikes, for example EURUSD 2008-12-08 +17.31% followed by -13.35% on 2008-12-09; JPYUSD 2008-12-08 -15.03% then +18.35% [V, C9].
- Converting Yahoo FX timestamps to UTC dates mislabels bars during British Summer Time (the 00:00 BST bar becomes the previous UTC day, so some bars land on Sundays) [V, C9]. Dates must be taken in Europe/London, exactly as M1.3 does for exchanges.
- The FX timing the library uses to put local returns into USD is unknown (U7).

Decision:

1. Primary FX source for currencies the ECB publishes: ECB reference rates, crossed through EUR (`USD per L = (USD per EUR) / (L per EUR)`). The fix (~14:10 CET) is about 3 h 20 min before a 17:30 CET close [U: exact closing times not verified], so roughly 86% of the FX day overlaps the equity day.
2. Fallback: Yahoo `<L>USD=X` (USD per unit of `L`; verified to return data for EUR, GBP, CHF, JPY) with its `Close`, dated in Europe/London. The report states the timing regime ("Yahoo FX close: start-of-day quote from about 2010; end-of-day before") and runs the FX audit below. A Yahoo-based conversion is labelled "approximate FX timing".
3. FX audit (`data/fx.py`, findings never modify the series, M1.4 policy): `fx_spike` error when `|r_t| > 3%`, `|r_{t+1}| > 3%`, opposite signs, and `|(1 + r_t)(1 + r_{t+1}) - 1| < 0.5%`; `fx_gap` warning for more than 5 calendar days between FX rows; `fx_close_convention` info with the yearly share of `|Close/Open - 1| < 1 bp`. The spike rule looks one row ahead, which is allowed for audits only (they describe the data vintage; they stamp no analytics).
4. ECB data access (API endpoint, history depth) is [U] and must be verified before implementation; if it fails, the fallback applies and is labelled.

Limits that remain: even a perfect FX fix cannot match the library's unknown conversion time (U7); for Japan and Asia Pacific the ECB fix is 6-8 hours after the close [U exact hours], so the same-day FX window is misaligned for those currencies whichever source is used. D14's weekly check is the mitigation.

### D9.4 Currency regressor (plan's European mode)

- Model A (default): `y_t` on the regional FF5 factors (all USD).
- Model B (optional, plan's request): Model A plus `r_fx_t` as a sixth regressor with its own beta, risk share (M7 extends to 6 factors) and contribution (M6). Interpretation label: "Currency beta: exposure of the stock's USD return to its home currency beyond what the regional factors (already in USD) carry." Note for reviewers: the regional Mkt-RF is itself a USD return, so it already contains the region's average currency move; the currency beta is not "the stock's currency exposure" in an absolute sense.
- Collinearity, measured [V, C9; Yahoo FX `<L>USD=X` closes dated in Europe/London, joined to the factor dates, 2004-01-02..2025-10-01, 5,642-5,655 rows each]: corr(`r_fx`, Europe Mkt-RF) 0.232 (EUR), 0.253 (GBP), 0.116 (CHF); corr(JPY, Japan Mkt-RF) -0.005. VIF of `r_fx` among the six regressors: 1.07, 1.10, 1.03, 1.02; condition number of the 6x6 correlation matrix 2.69-2.72. The FX return dated `t` correlates with the **previous** day's regional Mkt-RF at 0.186 (EUR), 0.302 (GBP), 0.158 (CHF), 0.192 (JPY), as expected when Yahoo's close is a start-of-day quote (D9.3); with UTC dating (wrong, D9.3) the same numbers come out different (EUR same-day 0.258), which is why the dating rule is tested (TD30). Collinearity is low for these four currencies; it is computed and reported for every ticker anyway, with M3.4's thresholds (VIF > 5 warning, > 10 strong, `kappa > 30`), and `corr(r_fx, mkt_rf)` shown.
- `r_fx` identically zero (USD stock) or with sample variance 0: Model B is `not_applicable`.
- Testing family: the currency beta joins F1, making `m = 6` for Model B (proposed amendment, D16).

## D10. Calendar alignment with regional files (extends M2)

- M2 applies unchanged: rows whose interval `(date_{t-1}, date_t]` contains two or more factor dates are excluded as `multi_day_return`; a stock date absent from the factor file is `no_factor_row`.
- Regional files contain every weekday (C2), so `no_factor_row` occurs only for weekend trading, and every exchange holiday of the stock creates one `multi_day_return` exclusion (one per run of consecutive holidays). Yahoo calendars, 2025-01-01..2025-09-30, missing weekdays [V, chart API]: VOD.L 6, SAP.DE 4, NESN.SW 8, 7203.T 14, BHP.AX 6; EURUSD=X and GBPUSD=X 1 each (1 January). Expect roughly 2-6% of rows excluded for a European or Japanese stock; the count is in `SampleInfo`.
- Decision: keep exclusion. Rejected alternative: compounding the factors over the gap. A compounded long-short factor is not the factor's multi-day return (C7: compounded daily SMB differs from monthly SMB by up to 3.2-4.0 points a month), and holiday rows carry moves the closed stock did not have.
- The US file keeps its own calendar; a US stock on `us_ff5_daily` is unaffected.

## D11. Risk-free rate

Fact (C8): daily RF is published with two decimals (0.01% per day). Compounded over a calendar year, daily RF differs from the monthly file's RF by -1.03 to +1.01 percentage points (sd about 0.4 a year), although the full-sample means agree within 0.01-0.11 points. In 2009-2015 every daily RF is 0.00. Over a short window, alpha absorbs minus the mean rounding error, so alpha can move by up to about one point a year from rounding alone.

- Binding today (M1.1): `RF_t` from the daily file.
- Proposed (D16, DD5): `RF_t = (1 + RF_m)^(1 / N_m) - 1`, with `RF_m` from the monthly file of the same region and release (same stamp, checked) and `N_m` the number of rows of the daily dataset's calendar in month `m`. This is the construction the library describes ("the simple daily rate that, over the number of trading days compounds to 1-month T-bill rate", P2), without the two-decimal rounding; remaining error is the monthly rounding (at most 0.005% a month). The monthly files cover the same months as the daily files (both end 202609, C7).
- Until accepted: the report shows alpha with the binding RF and, in the details drawer, the alpha with the monthly-derived RF and their difference (a robustness cell, not a second test).
- `Mkt-RF` in the file is used as published either way. Whether the library subtracts a rounded or unrounded RF inside Mkt-RF is [U].

## D12. Cross-dataset consistency checks (`data/consistency.py`)

Run after every accepted refresh of the datasets involved; a failure is a warning `cross_dataset_inconsistency` naming the check (never blocks; the data are still the library's). Thresholds = observed value with margin; observed values from `docs/datasets.md` section 6 (vintage 202609).

| ID | Check | Observed (202609) | Threshold |
| --- | --- | --- | --- |
| K1 | Six regional ff5 files have identical date sets | identical | exact |
| K2 | Six regional mom files identical; equal to regional ff5 dates from mom's first date | identical, from 1990-11-01 | exact |
| K3 | RF identical across the six regional ff5 files | max diff 0 | exact |
| K4 | Regional vs US-file RF on common dates | 346 of 9,128 differ, all by exactly 0.01 (file units) | every diff `<= 1e-4` (decimal); share differing `<= 10%` |
| K5 | US calendar is a subset of the regional calendar from 1990-07-02 | 0 US-only dates; 330 regional-only | 0 US-only dates |
| K6 | Developed Mkt-RF vs NA, EU, JP, APxJ Mkt-RF, one no-intercept regression per calendar year | R² min 0.99637, weights sum 0.9879-1.0046 | R² `>= 0.99` every year; sum in `[0.97, 1.03]` |
| K7 | US vs North America daily correlation | Mkt-RF 0.9981, SMB 0.9699, HML 0.9213, RMW 0.9069, CMA 0.9143; Mom vs WML 0.9431 | `>= 0.995, 0.95, 0.89, 0.88, 0.89; 0.92` |
| K8 | Daily file rebuilds the monthly Mkt-RF (`prod(1 + Mkt-RF + RF) - prod(1 + RF)` per month) | rms 0.021 / 0.030 / 0.017 points (US / Europe / Developed); max 0.180 / 0.185 / 0.065 | rms `<= 0.05`, max `<= 0.25` points, every region with a monthly file |
| K9 | Same stamp for every dataset in a report | all 202609 | exact (D6) |
| K10 | Regional weekday completeness | 0 missing of 9,458 | 0 missing (else `calendar_gap`, D3) |

K6, K7 and K8 are statistical; they detect a column swap, a unit error or a wrong file far more often than they fire on a correct release. Their thresholds must be re-derived (and the change logged in the test registry, `docs/research-protocol.md`) if a new release moves an observed value by more than half its margin.

## D13. Sample periods and regime coverage per region

| Dataset family | First date | Years to 2026-09 | Crisis windows of M10.3 covered | Notes |
| --- | --- | --- | --- | --- |
| `us_ff5_daily` | 1963-07-01 | 63.3 | GFC, COVID, 2022 | M10.2 warm-up excludes 1963-1964 rows |
| regional `ff5` | 1990-07-02 | 36.3 | GFC, COVID, 2022 | M10.2 warm-up (272 rows) excludes 1990-07-02 to about mid-1991 |
| regional `mom` | 1990-11-01 | 35.9 | same | adding momentum shifts the earliest possible sample start by 4 months |
| `us_mom_daily` | 1926-11-03 | 99.9 | same | |

Rules:

- The stock's own history still decides `S` (M2) and the 504-row minimum (M0.7).
- M10.3 crisis windows are S&P 500 dates. For non-US stocks they are kept as fixed dates (comparability) and labelled "US-dated window". Region-specific windows (for example the euro-area debt crisis) are new tests and must go through `docs/research-protocol.md` before they are added.
- M10.2 volatility regimes use the full history **of the factor dataset in use** (regional Mkt-RF for regional reports).
- M12/M13 labels that say "since 1963" use the dataset's first date. With 36 years, the stretch proxy has about 36 independent 1-year and 12 independent 3-year periods (M13 label must change accordingly).
- Regime-coverage badges (M10.3) are unchanged.

## D14. Timing and synchronicity

Facts (C6): same-day correlation of the regional Mkt-RF with North America Mkt-RF is 0.555 (Europe), 0.040 (Japan), 0.351 (Asia Pacific ex Japan); with the previous US day it is 0.258, 0.413 and 0.432. The Dimson sum (lag 0 + lag 1) of the beta on North America is 0.872, 0.585 and 0.772, close to the weekly betas (0.819, 0.483, 0.696), while the same-day betas are 0.562, 0.049 and 0.327.

Handling:

1. Default factors are those of the listing's own region (D8.2), whose markets close within a few hours of each other [U exact hours]. This removes most of the problem for Europe and Japan.
2. Developed, Developed ex US and US factors are not used on daily data for Asian listings (D8.2), and are robustness cells only for European listings.
3. Diagnostic (needs its own M-section, schema and oracle tests before it ships, per Definition of Done): for any report whose factor dataset contains markets in other time zones, show the lag-1 Dimson sum per factor and a weekly (calendar weeks ending Friday, compounded) regression next to the daily betas.
4. Limits: the Dimson regression doubles the parameters and inflates VIF; weekly data cut `n` by five (minimum detectable betas grow by about `sqrt(5) = 2.2`, see the power table in `docs/research-protocol.md`); FX timing (D9.3) is not fixed by either; within Europe, Asia Pacific ex Japan and North America, closes differ by up to a few hours [U].

## D15. Momentum

- Canonical column `mom` for both `WML` (regional) and `Mom` (US). Constructions differ: the US factor uses NYSE breakpoints (P7), the regional factors use breakpoints from the region's big stocks (P3).
- Optional sixth factor ("FF5 + MOM"); it changes F1 to `m = 6` and every identity of M6-M7 to six factors. It needs its own M-section before it ships; until then, momentum datasets are parsed, cached and checked (D2-D12) but not used in reports.

## D16. Decisions, proposed amendments and open questions

Decisions in this document:

- **DD1** One registry, one parser; per-dataset differences only in `DatasetSpec` (D2, D3).
- **DD2** Unknown or unsupported suffix is refused with a reason, never given a default (D7.1).
- **DD3** Regional factors of the listing's region are the default; Developed is a robustness cell; US factors never by default for non-US listings (D8.2).
- **DD4** ECB reference rates first, Yahoo FX as labelled fallback, FX audit always (D9.3).
- **DD5** (proposed amendment to M1.1) RF derived from the monthly file (D11).
- **DD6** Holiday rows: exclusion, no compounding of factors (D10).
- **DD7** Every vintage's raw zip kept locally (D4); `factor_vintage` becomes a per-dataset list (D5.1).

Proposed amendments to `docs/methodology.md` (need the owner):

- M0.6 F1: `m = 6` when the currency regressor (D9.4) or momentum (D15) is in the model.
- M0.8: `factor_vintage` per dataset with stamp and SHA-256 (D5.1).
- M1.1: per-dataset specs; stamp line check; "footer contains 0xA9" removed as the reason for latin-1 (X7); RF rule DD5.
- M1.5: replace "warn and compute" for non-USD tickers with D7-D9 when European mode ships (answers M16 open question 2).
- M13 label: dataset-specific start year.

Open questions for the owner:

1. Accept DD5 (monthly-derived RF)? Cost: one extra small download per region; benefit: removes up to about one point a year of alpha noise in short windows.
2. Accept ECB as the primary FX source (and its "information purposes only" wording) for a descriptive tool?
3. Should Model B (currency regressor) be on by default in European mode, or a toggle? The plan says "add the currency return as an extra regressor"; D9.4 shows low collinearity, but it changes F1 to six tests.
4. Canada: accept North America factors (US-dominated) or refuse `.TO` until a better source exists?
