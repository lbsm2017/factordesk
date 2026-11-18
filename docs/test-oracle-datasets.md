# factordesk test oracle: datasets, regions, FX and vintages

Status: v1, written 2026-11-18. Companion to `docs/methodology-datasets.md` (sections D1-D16, checks K1-K10) and `docs/datasets.md` (facts, evidence codes P1-P7 and C1-C10). Conventions of `docs/test-oracle.md` section 0 apply unchanged (markers, seed policy `20261118 + k` with `k` the TD number, tolerance policy).
Each test states its **target module** (proposed new modules below), the **setup**, the **assertion** and the **tolerance with its derivation**. A test that cannot be implemented as written is a spec bug: raise it, do not loosen it silently.

Proposed modules (all under `backend/factordesk/`):

| Module | Content |
| --- | --- |
| `data/factor_registry.py` | `DatasetSpec`, `REGISTRY`, `REGISTRY_VERSION`, region keys (D2) |
| `data/factor_parser.py` | `parse_factor_zip(raw, spec)` (D3) |
| `data/factor_cache.py` | cache layout, `meta.json`, raw-zip archive, atomic writes, refresh (D4, D6) |
| `data/vintage.py` | vintage records, revision diff, `reproduce` (D5) |
| `data/regions.py` | suffix table, `assign_region(symbol, metadata, override)` (D7) |
| `data/fx.py` | FX fetch (ECB, Yahoo), dating, USD conversion, FX audit (D9) |
| `data/rf.py` | monthly-derived daily RF (D11) |
| `data/consistency.py` | checks K1-K10 (D12) |

Fixture rule: fixtures are a few real lines copied from the 202609 files (`docs/datasets.md`, C1), zipped in memory by the test. Whole files are never committed (`docs/references.md`: factor data is not stored in the repository); tests that need whole files are marked `live` and download into a temporary cache.

Fixture texts (line ends CRLF unless a test says otherwise; blank lines are part of the text):

**FX-US5** (`us_ff5_daily`, member `F-F_Research_Data_5_Factors_2x3_daily.csv`)

```text
This file was created by using the 202609 CRSP database.
The Tbill return is the simple daily rate that, over the number of trading days
compounds to 1-month TBill rate. The 1-month TBill rate data until 202405 are from Ibbotson Associates. Starting from 202406, the 1-month TBill rate is from ICE BofA US 1-Month Treasury Bill Index.

,Mkt-RF,SMB,HML,RMW,CMA,RF
19630701,   -0.67,    0.00,   -0.33,   -0.01,    0.16,    0.01
19630702,    0.79,   -0.26,    0.26,   -0.07,   -0.20,    0.01
19630703,    0.63,   -0.17,   -0.10,    0.18,   -0.34,    0.01

Copyright 2026 Eugene F. Fama and Kenneth R. French
```

**FX-EU5** (`europe_ff5_daily`, member `Europe_5_Factors_Daily.csv`)

```text
This file was created using the 202609 Bloomberg database.

Missing data are indicated by -99.99.



,Mkt-RF,SMB,HML,RMW,CMA,RF
19900702    ,0.99    ,0.00   ,-0.56    ,0.43   ,-0.25    ,0.03
19900703    ,0.33   ,-0.09    ,0.00    ,0.02    ,0.28    ,0.03
19900704    ,0.24    ,0.03   ,-0.19   ,-0.09    ,0.23    ,0.03
```

**FX-EUM** (`europe_mom_daily`, member `Europe_MOM_Factor_Daily.csv`): the same 6 preamble lines as FX-EU5, then

```text
,WML
19901101    ,0.29
19901102    ,0.24
19901105    ,0.39
```

**FX-USM** (`us_mom_daily`, member `F-F_Momentum_Factor_daily.csv`)

```text
This file was created by using the 202609 CRSP database.  It
contains a momentum factor, constructed from six value-weight portfolios formed
using independent sorts on size and prior return of NYSE, AMEX, and NASDAQ stocks.
MOM is the average of the returns on two (big and small) high prior return portfolios
minus the average of the returns on two low prior return portfolios.  The portfolios
are constructed daily.  Big means a firm is above the median market cap on the NYSE
at the end of the previous day; small firms are below the median NYSE market cap.
Prior return is measured from day - 250 to - 21.  Firms in the low prior return
portfolio are below the 30th NYSE percentile.  Those in the high portfolio are above
the 70th NYSE percentile.

Missing data are indicated by -99.99 or -999.

,Mom
19261103,   0.55
19261104,  -0.51
19261105,   1.17

Copyright 2026 Eugene F. Fama and Kenneth R. French
```

For the tests below, a fixture's spec is the registry entry of its dataset with `min_rows = 1` and `first_date` set to the fixture's first date (the real values are tested in TD17 and the `live` tests).

---

## 1. Registry (`data/factor_registry.py`, D2)

- **TD01 Completeness.** `REGISTRY` has exactly 14 entries; keys are the 14 of D2.2, unique; each key equals `f"{region}_{family}_daily"`; regions are the 7 region keys; families `{ff5, mom}`; every region has one of each. Exact.
- **TD02 Exact file names and URLs.** For each entry, `url == BASE + file_name` with `BASE = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/"`, and `file_name` equals the D2.2 table, character for character. In particular: `Asia_Pacific_ex_Japan_MOM_Factor_Daily_CSV.zip` (upper-case `MOM`), `F-F_Momentum_Factor_daily_CSV.zip` (lower-case `daily`), `F-F_Research_Data_5_Factors_2x3_daily_CSV.zip`. Description URLs: P6 for `us_ff5_daily`, P7 for `us_mom_daily`, P2 for regional ff5, P3 for regional mom. Exact.
- **TD03 Registry vs library page (`live`).** Download P1; for every entry, the string `href="ftp/{file_name}"` occurs in the page exactly (case-sensitive), and its `Details` link is the entry's description URL. Any registry name not on the page, or a daily 5-factor or momentum link for one of the 7 regions on the page that is not in the registry, fails with the list. (Detects renames at the source.)

## 2. Parser layouts (`data/factor_parser.py`, D3)

- **TD04 US 5-factor layout.** Parse FX-US5. Columns `mkt_rf, smb, hml, rmw, cma, rf`; 3 rows; dates 1963-07-01..03; row 1 `= (-0.0067, 0.0, -0.0033, -0.0001, 0.0016, 0.0001)`; `ParseInfo.stamp == "202609"`, `source == "CRSP"`, footer `"copyright"`, no warnings. Values within `1e-15` (one division by 100 in float64).
- **TD05 Regional 5-factor layout (padded dates, no footer).** Parse FX-EU5. 3 rows, dates 1990-07-02..04 (04 July is present: regional calendar), row 1 `= (0.0099, 0.0, -0.0056, 0.0043, -0.0025, 0.0003)`; stamp `202609`, source `Bloomberg`, footer `"none"`, no warnings. `1e-15`.
- **TD06 Regional momentum layout.** Parse FX-EUM. One column named `mom` (not `WML`); values `(0.0029, 0.0024, 0.0039)`; dates 1990-11-01, 1990-11-02, 1990-11-05. `1e-15`.
- **TD07 US momentum layout.** Parse FX-USM (13-line preamble, stamp line continues after "database."). One column `mom`, values `(0.0055, -0.0051, 0.0117)`, stamp `202609`, source `CRSP`. `1e-15`.
- **TD08 Wrong family or region for the spec.** (a) FX-EU5 bytes with the `europe_mom_daily` spec, (b) FX-EUM with `europe_ff5_daily`, (c) FX-USM with `europe_mom_daily` (header `Mom` vs expected `WML`), (d) FX-EU5 with `us_ff5_daily` (source `Bloomberg` vs `CRSP`). Each raises `SchemaError`; (a)-(c) name the tokens found, (d) names both sources. Exact.
- **TD09 Stamp line.** Accept: "This file was created by using the 202609 CRSP database.", "This file was created using the 202609 Bloomberg database.", the FX-USM line with trailing "  It". Reject with `SchemaError("stamp_not_found")`: the stamp line removed; "created using the 2026-09 Bloomberg database."; month `202613`. Exact.
- **TD10 Member name not matched.** FX-EUM zipped under the member name `Europe_MOM_Factor_Daily.csv` inside an archive named `Europe_Mom_Factor_Daily_CSV.zip`, and again under `europe_mom_factor_daily.CSV`: both parse; `ParseInfo.member` records the name as found. A zip with no `.csv` member or two of them: `SchemaError` (as T09).
- **TD11 Footer variants.** FX-US5 without the copyright line, and FX-EU5 with a copyright line appended: both parse to the same frames; each records warning `footer_differs`. An 8-digit row after a footer: `SchemaError("unexpected second data block")` (as T06).
- **TD12 Encoding.** The four fixtures contain only ASCII and decode identically as UTF-8 and latin-1 (assert both decodings equal). FX-US5 with the footer `b"\xa9 2026 Eugene F. Fama and Kenneth R. French"`: parses (latin-1), same frame. Line ends: CRLF and LF versions give `DataFrame.equals` frames.

## 3. Sentinels, units and ranges (`data/factor_parser.py`, D3)

- **TD13 Sentinels per dataset.** In FX-EU5 replace row 2 HML by `-99.99` and row 3 RMW by `-999.00`; in FX-US5 replace row 2 SMB by `-999`. All three cells become NaN and are listed as `(date, column)`. Warnings: FX-EU5 gets exactly one `undeclared_sentinel` (for `-999.00`; the preamble declares only -99.99); FX-US5 gets none (US spec declares both). The real value `-17.44` and the value `-9.99` are kept (`-0.1744`, `-0.0999`). Exact.
- **TD14 Bounds.** A factor of `50.01` (0.5001), an RF of `0.21` (0.0021) and an RF of `-0.02` (-0.0002) each raise `SchemaError` naming date and column. A factor of `50.00` and an RF of `0.20` pass (bounds inclusive). Exact.
- **TD15 Calendar checks.** (a) A row dated 19900707 (Saturday) in FX-EU5: `SchemaError("weekend_row")`. (b) FX-EU5 with the 19900703 row removed (all-weekday calendar): accepted, warning `calendar_gap` listing `1990-07-03`. (c) The same removal in FX-US5 (exchange calendar): accepted, no warning. Exact.
- **TD16 Precision.** A value `0.123` in FX-EU5: accepted with warning `precision_changed` and `max_decimals == 3`. The four unmodified fixtures: `max_decimals == 2`. Exact.
- **TD17 Real-file expectations (`live`).** For each of the 14 datasets, download and parse with the real spec. Assert: stamp is 6 digits; source as D2.2; `n_rows >= min_rows`; first date equals D2.2 (else the test fails with `history_start_changed`, which is a real-world change to investigate); no `undeclared_sentinel`; `max_decimals == 2`; for regional files no `calendar_gap`. Observed on 2026-11-18 (vintage 202609): rows 15,918 / 9,458 (x6) / 26,237 / 9,370 (x6), 0 sentinels everywhere.

## 4. Region assignment (`data/regions.py`, D7)

- **TD18 Supported suffixes.** Parametrised over D7.2: `assign_region("X" + suffix, metadata={"currency": default}, override=None)` returns the table's region and the suffix's country. Includes `VOD.L -> europe`, `NESN.SW -> europe`, `NOVO-B.CO -> europe`, `EQNR.OL -> europe`, `VOLV-B.ST -> europe`, `SAP.DE -> europe`, `7203.T -> japan`, `BHP.AX -> asia_pacific_ex_japan`, `0005.HK -> asia_pacific_ex_japan`, `SHOP.TO -> north_america`, `XYZ.NX -> europe` with country `None`. Exact.
- **TD19 No suffix.** `AAPL` and `SPY` -> `us`. A symbol with a dot inside the root but a US class suffix pattern, `BRK-B` (Yahoo uses `-`), -> `us`. Exact.
- **TD20 Refused venues.** `SAP.F`, `VOD.IL`, `XYZ.XD`, `XYZ.XC`, `XYZ.AQ`, `XYZ.TI`, `XYZ.XA`, `XYZ.NE`, `XYZ.CN`, and the German regional suffixes `.BE .BM .DU .HM .HA .MU .SG` -> refusal `secondary_venue`. `PKO.WA`, `TEVA.TA`, `005930.KS`, `RELIANCE.NS`, `600519.SS`, `2330.TW`, `MAREL.IC` -> `market_not_in_library_regions`. `EURUSD=X`, `XYZ.CME`, `XYZ.NYB` -> `not_an_equity`. Each refusal carries the suffix and a human-readable reason. Exact.
- **TD21 Unknown suffix.** `XYZ.QQ` and `XYZ.` (trailing dot) -> refusal `unknown_exchange_suffix` with the suffix echoed. No region is returned (no default). Exact.
- **TD22 Currency from metadata.** `VOD.L` with `currency = "GBp"` -> FX currency `GBP`, `pence = True`, no warning. `XYZ.L` with `currency = "USD"` -> FX currency `USD` (no FX series requested), warning `currency_differs_from_market_default`. `SAP.DE` with `currency = "EUR"` -> no warning. Metadata without `currency` -> refusal `currency_unknown`. Exact.
- **TD23 User override.** `SAP.DE` with `override = "developed_ff5_daily"` -> that dataset, caveat `user_selected_factors`. `SAP.F` with an override -> accepted (rule 1 precedes rule 4), caveat `user_selected_factors`, and `secondary_venue` shown as a warning. Unknown dataset key in override -> error `unknown_dataset`. Exact.

## 5. FX conversion (`data/fx.py`, D9)

- **TD24 Identity.** For `r_loc = 0.0123`, `r_fx = -0.0045`: `r_usd = (1.0123)(0.9955) - 1 = 0.00774465` within `1e-15`. Vectorised over DGP-A returns (`docs/test-oracle.md` 0.4) and a random `r_fx ~ N(0, 0.007^2)` (seed rule): `(1 + r_usd) == (1 + r_loc)(1 + r_fx)` within `1e-15` relative; `r_fx = 0` gives `r_usd == r_loc` bitwise.
- **TD25 Same interval as the stock.** Stock rows on Mon 2025-04-14, Thu 2025-04-17, Tue 2025-04-22 (Easter holidays missing); FX rows every weekday with `x` = 1.00, 1.01, 1.02, 1.03, 1.04, 1.05, 1.06 for 14, 15, 16, 17, 18, 21, 22 April. Assert `r_fx` on 04-17 `= 1.03/1.00 - 1` and on 04-22 `= 1.06/1.03 - 1` (not the FX series' own one-day returns). `1e-15`.
- **TD26 Quotation direction.** A series quoted as JPY per USD `q` (Yahoo `JPY=X`) and the same rates as USD per JPY `x = 1/q`: the USD return of a JPY stock is identical (`1e-14` relative) whichever input the converter receives, given the series' declared direction. A series without a declared direction raises.
- **TD27 Pence.** Prices `[1000, 1010, 999]` GBp and `[10.00, 10.10, 9.99]` GBP give identical `r_loc` (`1e-15`); the FX lookup for `GBp` requests `GBP`.
- **TD28 Unit errors (`data/audit.py`).** (a) A `.L` series where `Close` jumps from `250.0` to `2.52` on a non-split day: error `currency_unit_switch` on that date (ratio 0.01008, within 3% of 0.01). A genuine -60% day (`250 -> 100`) is not flagged by this rule (A4 still warns). (b) Three dividend events where `Adj Close` was built with `D = 5.0` pence but `Dividends` says `0.05`: one warning `dividend_unit_mismatch`, no per-event A6 errors. Exact.
- **TD29 Missing FX.** FX missing on one stock date `t`. Per D9.1, `r_fx` needs `x` on the stock's previous row and current row, so row `t` and row `t+1` are both excluded with reason `fx_missing` and listed in `SampleInfo`. Assert exactly 2 exclusions, no filled value, and no `r_fx` equal to 0 created by the gap. Exact.
- **TD30 FX dating in Europe/London.** Bar timestamps `2016-06-23 23:00 UTC` and `2015-01-15 00:00 UTC` (real Yahoo GBPUSD and CHFUSD bars) map to dates `2016-06-24` and `2015-01-15`. Converting to UTC dates first would give `2016-06-23`; assert the module does not. Exact.
- **TD31 FX audit.** (a) Rates `1.2717, 1.4918, 1.29261` (three consecutive real EURUSD=X closes as served on 2026-11-18; the second and third are dated 2008-12-08 and 2008-12-09; returns +17.31%, -13.35%): `fx_spike` error on the middle date. A one-way move of +4% followed by +0.1% is not flagged. (b) Two FX rows 7 calendar days apart: `fx_gap` warning. (c) `fx_close_convention`: a synthetic year where `Close == Open` on every bar reports share 1.0; a year where `Close` equals the next bar's `Open` reports share near 0 (exact counts on the fixture). Findings never change the series (input frame equals output frame bitwise).
- **TD32 Currency regressor collinearity and degenerate cases (`analytics/regression.py` with D9.4).** (a) Seeded DGP: five factors as DGP-A plus `r_fx = 0.007 * (0.23 * z_mkt + sqrt(1 - 0.23^2) * u)`, with `z_mkt` the standardised `mkt_rf` and `u ~ N(0, 1)`, so `corr(r_fx, mkt_rf)` is about 0.23 (the observed EUR value) and `sd(r_fx)` about 0.7% (observed 0.703%): reported VIF of `r_fx` within 0.05 of `1 / (1 - R^2_fx)` computed with `variance_inflation_factor` on an exog with constant (M3.4 cross-check), and below 5 (no warning). (b) `r_fx = 0.9 * mkt_rf + small noise`: VIF > 5 gives the M3.4 warning naming `fx`. (c) USD stock (`r_fx == 0` everywhere): Model B status `not_applicable`, reason "stock quoted in USD", and no singular-matrix exception.

## 6. Vintage, cache and staleness (`data/factor_cache.py`, `data/vintage.py`, D4-D6)

- **TD33 `meta.json` round trip.** Parse FX-EU5 zipped bytes with injected clock `2026-11-18T10:45:11Z`, headers `Last-Modified: Mon, 26 Oct 2026 20:51:47 GMT`, `ETag: "11d38d18b65dd1:0"`. After writing, `meta.json` contains every D4.1 field; `sha256` equals `hashlib.sha256(bytes).hexdigest()`; `file_stamp == "202609"`; reading it back gives an equal `VintageRecord`. Exact.
- **TD34 Archive and reproduce.** Write two vintages of one dataset (FX-EU5, and FX-EU5 with row 3 HML changed); `vintages/` holds two zips named `202609_<sha[:12]>.zip`. A report computed on vintage 1 records its SHA-256; after vintage 2 becomes current, `reproduce(report)` loads vintage 1 by SHA-256 and returns numbers bitwise equal to the original report. A missing archived zip gives error `vintage_not_available`.
- **TD35 Revision detection.** Old and new frames equal except: one cell changed by `0.0001` (one published digit), one by `0.00004`, plus 2 rows appended. `revised_cells` counts 1 (threshold `5e-5`, D5.3), max change `0.0001`, `appended_rows == 2`, one line in `revisions.jsonl` with both stamps and SHA-256s. Exact.
- **TD36 History rewritten.** New vintage lacks a date present in the old one, or starts later: warning `history_rewritten` with the dates. Exact.
- **TD37 Mixed vintage.** A report using `europe_ff5_daily` (stamp 202609) and `europe_mom_daily` (stamp 202608): warning `mixed_vintage` naming both. Same stamp but `last_date` 2026-09-30 vs 2026-08-31: error `stamp_date_mismatch`. Exact.
- **TD38 Staleness per dataset.** Injected clock 2026-11-18. `europe_ff5_daily` last date 2026-09-30 (49 days, stale), `us_ff5_daily` last date 2026-10-30 (19 days, fresh): automatic refresh sends HEAD only for the European file; a HEAD answer for the US file is never used to decide the European one. Other rows of T14's decision table hold per dataset. Exact.

## 7. Risk-free rate (`data/rf.py`, D11)

- **TD39 Monthly-derived daily RF.** Month with `RF_m = 0.0035` and `N_m = 23` rows: every daily value equals `(1.0035)^(1/23) - 1` (`1e-15`), and `prod(1 + rf_t) - 1 == 0.0035` within `1e-15`. The month's row count comes from the daily dataset's own calendar (a regional month has more rows than the US month when it contains a US holiday). Stamps of daily and monthly files differ: error `mixed_vintage`. Live variant (`live`): over all months of `us_ff5_daily` and `europe_ff5_daily`, the derived daily RF rounded to 2 decimals (in percent) equals the published daily RF on at least 90% of rows [observed share to be recorded when first run; U], and the yearly compounded difference to the published daily RF lies within `[-1.1, +1.1]` points (C8 observed -1.03 to +1.01).

## 8. Cross-dataset consistency and replication (`data/consistency.py`, D12; `live`)

All on the current vintage of the datasets named. Observed values (vintage 202609) and the thresholds are those of D12.

- **TD40 Calendars and RF (K1, K2, K3, K5, K10).** Six regional ff5 date sets identical; six regional mom date sets identical and equal to the ff5 dates from 1990-11-01; RF columns of the six regional ff5 files identical (max diff 0); 0 US dates (from 1990-07-02) absent from the regional calendar; 0 missing weekdays in the regional calendar. Exact.
- **TD41 Regional vs US RF (K4).** On common dates every `|RF_reg - RF_us| <= 1e-4 + 1e-12` (decimal) and the share of dates that differ `<= 0.10` (observed 346/9,128 = 0.038).
- **TD42 Developed partition (K6).** Per calendar year, no-intercept OLS of Developed Mkt-RF on North America, Europe, Japan, Asia Pacific ex Japan Mkt-RF: `R^2 >= 0.99` (observed min 0.99637) and weights sum in `[0.97, 1.03]` (observed 0.9879-1.0046). Also a negative control in the same test: replacing Japan by the Japan **SMB** column drops the minimum yearly `R^2` below 0.99 (proves the check can fail).
- **TD43 US vs North America (K7).** Daily correlations on common dates: Mkt-RF `>= 0.995` (0.9981), SMB `>= 0.95` (0.9699), HML `>= 0.89` (0.9213), RMW `>= 0.88` (0.9069), CMA `>= 0.89` (0.9143); US Mom vs NA WML `>= 0.92` (0.9431). Negative control: shifting the NA file by one row drops the Mkt-RF correlation below 0.5.
- **TD44 Daily rebuilds monthly Mkt-RF (K8, replication target RT3).** For `us`, `europe`, `developed` (monthly files of the same stamp): per month `prod(1 + mkt_rf + rf) - prod(1 + rf)` minus the monthly Mkt-RF, in percentage points: rms `<= 0.05` and max `<= 0.25` (observed rms 0.021 / 0.030 / 0.017, max 0.180 / 0.185 / 0.065). Also assert that the same rebuild for HML exceeds rms 0.1 in at least one region (observed 0.18-0.22), documenting why only Mkt-RF is an invariant.
- **TD45 Library front table (replication target RT1).** Parse P1's "Fama/French 5 Research Factors (2x3)" table: the first column (latest month) equals the latest row of `F-F_Research_Data_5_Factors_2x3_CSV.zip` for all five factors, exactly (two-decimal strings). Observed for September 2026: -1.07, -4.60, -1.55, -3.22, 1.08 = row 202609. The 12-month column for HML, RMW, CMA equals the leg-difference formula of `docs/research-protocol.md` Appendix C (RT2) applied to the page's own portfolio table within 0.01.
- **TD46 Asynchrony stays detectable.** Japan Mkt-RF vs North America Mkt-RF: same-day correlation `< 0.15` and previous-day correlation `> 0.30` (observed 0.040 and 0.413). If this fails, the D14 handling must be re-examined (it is a fact test, not a code test).

## 9. Calendar alignment with regional files (`analytics/sample.py`, M2 + D10)

- **TD47 Holidays become multi-day returns.** Factor calendar: all weekdays 2025-04-14..2025-04-25 (regional). Stock calendar (London): missing 2025-04-18 (Good Friday) and 2025-04-21 (Easter Monday). Assert: the stock row of 2025-04-22 is excluded with reason `multi_day_return` (its interval contains 04-18, 04-21, 04-22); no row has reason `no_factor_row`; all other rows aligned; the factor rows of 04-18 and 04-21 enter no statistic. With an FX series missing 2025-04-18 and 2025-04-21 as well, the same row is excluded once, with both reasons listed. Exact.

## 10. Failure modes (`data/factor_cache.py`, `data/factor_parser.py`)

- **TD48 HTTP errors.** Mocked responses: 404 (the real server's answer for a non-existent name, observed 2026-11-18), 500, connection timeout, and 200 with `Content-Type: text/html` and an HTML body. Each: previous `factors.parquet`, `meta.json` and `vintages/` unchanged (SHA-256 of each file before and after); `last_attempt_at` updated and `last_attempt_ok = false` with `last_attempt_error` naming the status or `not_a_zip`. No partial temp file remains.
- **TD49 Truncated zip.** The FX-EU5 zip cut to 50% and to its first 100 bytes: typed `SchemaError("bad_zip")` (no `zipfile.BadZipFile` or `zlib.error` leaks), cache unchanged.
- **TD50 Schema changes.** Each variant of FX-EU5 raises `SchemaError` with a message naming what was found: (a) extra column `,Mkt-RF,SMB,HML,RMW,CMA,RF,WML`; (b) renamed `,Mkt-RF,SMB,HML,RMW,CMA,Rf`; (c) reordered `,Mkt-RF,SMB,HML,CMA,RMW,RF`; (d) dates written `1990-07-02` (no data row matches: zero rows); (e) monthly file given to a daily spec (6-digit dates: zero 8-digit rows); (f) semicolon separators. Exact.
- **TD51 Size limit.** A zip whose member declares or decompresses to more than 20 MB: `SchemaError("too_large")` before the whole member is read (stream with a byte budget). The real largest member is 1,019,175 bytes (US 5-factor, C1), so the limit has a margin of about 20x.

---

## Appendix. Mapping to D-sections

| D-section | Tests |
| --- | --- |
| D2 registry | TD01-TD03 |
| D3 parser | TD04-TD17, TD49-TD51 |
| D4-D6 cache, vintage, staleness | TD33-TD38, TD48 |
| D7 regions | TD18-TD23 |
| D9 FX | TD24-TD32 |
| D10 calendar | TD47 |
| D11 RF | TD39 |
| D12 consistency | TD40-TD46 |
