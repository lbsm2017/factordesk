# factordesk dataset cards (Kenneth R. French Data Library, daily files)

Status: v1, written 2026-11-18. Snapshot: every file below was downloaded on 2026-11-18 between 10:44:50 and 10:45:13 UTC; every library page was fetched on 2026-11-18 between 10:42 and 10:50 UTC.
Companions: `docs/methodology-datasets.md` (design, sections D1-D16), `docs/test-oracle-datasets.md` (tests TD01-TD51), `docs/research-protocol.md`.
Binding conventions: `docs/methodology.md` M0-M3. This file only records facts about the data; it decides nothing.

## 0. How to read this file

Every field carries one tag:

- **[V]** VERIFIED. The evidence is a quoted library text (code `P1`-`P7`, section 1), a downloaded file (its SHA-256 is in the card), or a computation run on those files (code `C1`-`C10`, section 1).
- **[U]** UNVERIFIED. Not found in a primary source, or inferred. The text says what would verify it.

Quotes are copied from the pages or files exactly (only line breaks removed). Dashes that the pages encode in Windows-1252 are written as `-`.

Units: the files publish **percent per day with two decimals** [V, C1]. Ranges below are in those file units.

---

## 1. Evidence register

### 1.1 Library pages (HTTP GET, 2026-11-18)

| Code | URL | HTTP Last-Modified |
| --- | --- | --- |
| P1 | <https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html> | Tue, 27 Oct 2026 15:15:55 GMT |
| P2 | <https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/Data_Library/f-f_5developed.html> | Mon, 26 Oct 2026 20:53:03 GMT |
| P3 | <https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/Data_Library/f-f_developed_daily_mom.html> | Mon, 26 Oct 2026 20:53:04 GMT |
| P4 | <https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/Data_Library/f-f_developed_mom.html> (monthly momentum; used only for comparison) | Mon, 26 Oct 2026 20:53:04 GMT |
| P5 | <https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/Data_Library/details_main.html> | Sun, 16 Jun 2013 22:56:27 GMT |
| P6 | <https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/Data_Library/f-f_5_factors_2x3.html> | Tue, 27 Oct 2026 15:16:45 GMT |
| P7 | <https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/Data_Library/det_mom_factor_daily.html> | Tue, 27 Oct 2026 15:16:42 GMT |

P1 links every daily file in this document to its description page: regional 5-factor daily files to P2, regional daily momentum files to P3, the US 5-factor daily file to P6, and the US daily momentum file to P7 [V, P1 anchors `Details`].

### 1.2 Computations

All files were parsed in memory (no extraction to disk). Scripts were run with `uv run --no-project python -I` from a scratch directory. The scratch copies of the scripts are not durable. Each computation is defined precisely enough here and in `docs/methodology-datasets.md` D12 to be re-implemented, and the tests in `docs/test-oracle-datasets.md` turn each one into an invariant.

| Code | What was computed |
| --- | --- |
| C1 | Zip structure, preamble lines, header tokens, first/last 3 rows, row count, decimal places, sentinel count, min/max per column |
| C2 | Calendars: date sets per file, missing weekdays, dates in one file and not another, rows with all five factors exactly 0 |
| C3 | RF: equality across files, regional vs US daily RF, distinct values |
| C4 | US (CRSP) vs North America (Bloomberg): daily correlation, tracking error, mean per factor |
| C5 | Developed vs its four regions: least-squares fit with static and calendar-year weights |
| C6 | Synchronicity: lead/lag correlations, Dimson and weekly betas of the regional market factor on the North America market factor |
| C7 | Daily file vs monthly file of the same region: compounded daily returns minus monthly values |
| C8 | RF quantisation: compounded daily RF per calendar year minus compounded monthly RF |
| C9 | Yahoo FX daily bars (`EURUSD=X`, `GBPUSD=X`, `CHFUSD=X`, `JPYUSD=X`, requested 2004-01-01 to 2025-10-01 from the chart API on 2026-11-18): close vs open convention, outliers, correlation and VIF against regional factors (bars dated in Europe/London) |
| C10 | Minimum detectable effects for alpha and betas (normal approximation, iid errors) |

---

## 2. The three open questions from the plan (`docs/PLAN.md`, "Not yet verified")

**Q1. Currency of returns. Answer: US dollars for every regional file [V].**
P2 (5-factor) and P3 (daily momentum) both state: "All returns are in U.S. dollars, include dividends and capital gains, and are not continuously compounded."
The US files (P6, P7) do not state a currency. They are built from CRSP data for US-listed stocks, so USD is the natural reading [U, inferred: no page says "dollars" for the US files].
Consequence: a European stock must be converted to USD before it is regressed on these factors (`docs/methodology-datasets.md` D9).

**Q2. Is the UK inside Europe? Answer: yes [V].**
P2 and P3 carry the same country-membership table (C2 extracted the check marks; the two tables are identical). "Great Britain" is checked under Europe. The full table is in section 3.

**Q3. Which risk-free rate does each file carry? Answer: the US one-month T-bill for every 5-factor file; the momentum files carry no RF [V].**

- Regional 5-factor files, P2: "The market factor is the return on a region's value-weight market portfolio minus the U.S. one month T-bill rate. The daily T-bill return is the simple daily rate that, over the number of trading days compounds to 1-month T-bill rate."
- US 5-factor file, preamble lines 2-3: "The Tbill return is the simple daily rate that, over the number of trading days compounds to 1-month TBill rate. The 1-month TBill rate data until 202405 are from Ibbotson Associates. Starting from 202406, the 1-month TBill rate is from ICE BofA US 1-Month Treasury Bill Index." P6 says the same in prose.
- The six regional 5-factor files carry an identical RF column (max absolute difference 0) [V, C3]. Regional RF equals the US-file RF on 8,782 of 9,128 common dates and differs by exactly 0.01 (one published digit) on the other 346 [V, C3]. The difference comes from the day count: the regional calendar has more days per month (section 4.3), so the "simple daily rate" is smaller and rounds differently [U, explanation consistent with P2's text; not stated by the library].
- The regional page does not name the T-bill source (Ibbotson / ICE) [U]. Monthly RF in `Europe_5_Factors_CSV.zip` equals monthly RF in `F-F_Research_Data_5_Factors_2x3_CSV.zip` in 433 of 435 months (199007-202609); the two exceptions differ by 0.01 (199504: 0.44 vs 0.45; 202507: 0.34 vs 0.35) [V, C3].
- Momentum files have a single factor column and no RF [V, C1].

---

## 3. Country membership (all regional 5-factor and momentum files)

Source: the table in P2 and P3 (identical) [V]. X = included.

| Country (library spelling) | Developed | Developed ex US | Europe | Japan | Asia Pacific ex Japan | North America |
| --- | --- | --- | --- | --- | --- | --- |
| Australia | X | X | | | X | |
| Austria | X | X | X | | | |
| Belgium | X | X | X | | | |
| Canada | X | X | | | | X |
| Switzerland | X | X | X | | | |
| Germany | X | X | X | | | |
| Denmark | X | X | X | | | |
| Spain | X | X | X | | | |
| Finland | X | X | X | | | |
| France | X | X | X | | | |
| Great Britain | X | X | X | | | |
| Greece | X | X | X | | | |
| Hong Kong | X | X | | | X | |
| Ireland | X | X | X | | | |
| Italy | X | X | X | | | |
| Japan | X | X | | X | | |
| Netherlands | X | X | X | | | |
| Norway | X | X | X | | | |
| New Zealand | X | X | | | X | |
| Portugal | X | X | X | | | |
| Sweden | X | X | X | | | |
| Singapore | X | X | | | X | |
| United States | X | | | | | X |

Facts that follow from the table [V]:

- 23 countries in Developed. Europe has 16, Asia Pacific ex Japan 4, North America 2 (US, Canada), Japan 1. The four regions partition Developed.
- Developed ex US = Developed minus the US. It contains **Canada**, so it is not the union of Europe, Japan and Asia Pacific ex Japan.
- Not in any regional file: Luxembourg, Iceland, Poland, Israel, Korea, Taiwan, China, India and every other market not listed. The table gives membership only, not dates of entry. Whether Greece or Portugal (for example) were in the sample since 1990 is [U].

---

## 4. Shared facts

### 4.1 All six regional 5-factor daily files (Europe, Developed, Developed ex US, Japan, North America, Asia Pacific ex Japan)

| Field | Value | Tag |
| --- | --- | --- |
| Description page | P2 | V (P1 link) |
| Currency | USD (section 2, Q1) | V |
| Construction | P2: "The Fama/French 5 factors (2x3) are constructed using the 6 value-weight portfolios formed on size and book-to-market, the 6 value-weight portfolios formed on size and operating profitability, and the 6 value-weight portfolios formed on size and investment." | V |
| Sort date and size breakpoint | P2: "we sort stocks in a region into two market cap and three respective book-to-market equity (B/M), operating profitability (OP), and investment (INV) groups at the end of each June. Big stocks are those in the top 90% of June market cap for the region, and small stocks are those in the bottom 10%." | V |
| Style breakpoints | P2: "The B/M, OP, and INV breakpoints for a region are the 30th and 70th percentiles of respective ratios for the big stocks of the region." | V |
| Factor definitions | P2 gives SMB = 1/3 (SMB(B/M) + SMB(OP) + SMB(INV)), HML = 1/2 (Small Value + Big Value) - 1/2 (Small Growth + Big Growth), RMW and CMA analogously | V |
| Weighting and rebalancing | Value-weight portfolios, sorted at the end of each June (annual) | V (P2) |
| Stock eligibility | P2: "SMB, HML, RMW, and CMA for July of year t to June of t+1 include all stocks for which we have market equity data for December of t-1 and June of t, (positive) book equity data for t-1 (for SMB, HML, and RMW), non-missing revenues and at least one of the following: cost of goods sold, selling, general and administrative expenses, or interest expense for t-1 (for SMB and RMW), and total assets data for t-2 and t-1 (for SMB and CMA)." | V |
| How Developed / Developed ex US breakpoints are set (regional or pooled) | Not stated on P2 | U (P3 states it for momentum only; see 4.2) |
| Source database | File preamble line 1: "This file was created using the 202609 Bloomberg database." | V (C1) |
| History of the source (any non-Bloomberg period) | Not stated for these factors. P1's sentence "The raw data are from Morgan Stanley Capital International for 1975 to 2006 and from Bloomberg for 2007 to present" belongs to the **international country and index portfolios** section of P1, not to these factor files. Do not cite it for them. | U |
| Paper | P5: "The returns in this section are updated versions of those used in Eugene F. Fama and Kenneth R. French (2012) "Size, Value, and Momentum in International Stock Returns", Journal of Fincancial Economics ." (sic) | V |
| Date range stated | P2: "Daily Returns: July 1, 1990 - September 30, 2026" | V |
| Date range observed | 1990-07-02 to 2026-09-30, 9,458 rows in each file (1990-07-01 is a Sunday) | V (C1) |
| Calendar | Every weekday (Monday-Friday) from 1990-07-02 to 2026-09-30: 9,458 weekdays, 9,458 rows, no weekday missing, no weekend row. The six files have identical date sets. | V (C2) |
| Holiday rows | Rows exist on 25 December and 1 January of every year and on all US holidays (330 dates not in the US file). They are not filled with zeros: Europe's mean absolute Mkt-RF is 0.098% on 25 December and 0.071% on 1 January vs 0.773% on all rows; North America's is 0.026% on US-holiday rows vs 0.751% on US trading rows. Rows with all five factors exactly 0: Europe 1, Developed 1, Developed ex US 1, Japan 7, North America 15, Asia Pacific ex Japan 1. What moves on such days (currency moves, stale or partial markets) is not stated. | V (C2), mechanism U |
| Header line | `,Mkt-RF,SMB,HML,RMW,CMA,RF` (7 tokens, first empty) | V (C1) |
| Preamble | 6 lines: the "created using" line, blank, "Missing data are indicated by -99.99.", 3 blank lines. Header is line index 6. | V (C1) |
| Row layout | Date padded with spaces before the comma, values padded before the comma, for example `19900702    ,0.99    ,0.00   ,-0.56    ,0.43   ,-0.25    ,0.03`. 7 fields per row. | V (C1) |
| Footer | None. The file ends after the last data row (no copyright line). | V (C1) |
| Encoding | Plain ASCII: no byte 0xA9, decodes as UTF-8, no BOM, CRLF line ends (9,465 CRLF, 9,465 LF) | V (C1) |
| Zip | One member, `<Region>_5_Factors_Daily.csv`, 605,447 bytes in every regional file | V (C1) |
| Missing-value convention | Preamble: "Missing data are indicated by -99.99." | V |
| Sentinels observed | 0 in every file | V (C1) |
| Decimal places | Exactly 2 in every value | V (C1) |
| Risk-free rate | US one-month T-bill, identical across the six files (section 2, Q3) | V |
| RF values observed | 0.00, 0.01, 0.02, 0.03 only; 36.6% of rows are 0.00 | V (C3) |
| Creation stamp | `202609` | V (C1) |
| Update cadence | P1 for US research returns: "We reconstruct the full history of returns each month when we update the portfolios." No cadence is stated for the regional files. Observed: data through 2026-09-30, HTTP Last-Modified 2026-10-26, stamp 202609 (one release seen). | Monthly: U (inferred) |

### 4.2 All six regional daily momentum files

| Field | Value | Tag |
| --- | --- | --- |
| Description page | P3 | V (P1 link) |
| Currency | USD. P3: "All returns are in U.S. dollars, include dividends and capital gains, and are not continuously compounded." | V |
| Construction | P3: "The 2x3 sorts on size and lagged momentum to construct WML are formed daily. For portfolios formed at the end of day t-1, the lagged momentum return is a stock's cumulative return for day t-250 to day t-20. The momentum breakpoints for a region are the 30th and 70th percentiles of the lagged momentum returns of the big stocks of the region." | V |
| Developed breakpoints | P3: "The developed portfolios use developed size breaks, but we use the momentum breakpoints for the four regions to allocate the stocks of these regions to the developed portfolios." | V |
| Factor | P3: "WML is the equal-weight average of the returns for the two winner portfolios for a region minus the average of the returns for the two loser portfolios", WML = 1/2 (Small High + Big High) - 1/2 (Small Low + Big Low). Portfolios are value-weight. | V |
| Eligibility | P3: "To be included in a portfolio for day t (formed at the end of the day t-1), a stock must have a price for the end of day t-251 and a good return for t-21." Note the page says "t-20" for the end of the formation window and "t-21" for the required good return. | V (text), meaning of the difference U |
| Source database | Preamble: "This file was created using the 202609 Bloomberg database." | V (C1) |
| Date range stated | P3: "Daily Returns: December 1, 1990 - September 30, 2026" | V |
| Date range observed | **1990-11-01** to 2026-09-30, 9,370 rows. The file starts one month earlier than P3 says. | V (C1) |
| Calendar | Identical across the six files, and equal to the regional 5-factor calendar from 1990-11-01 | V (C2) |
| Header | `,WML` (not `Mom`) | V (C1) |
| Preamble, layout, footer, encoding | As 4.1: same 6-line preamble with "-99.99", padded rows such as `19901101    ,0.29`, no footer, ASCII, CRLF | V (C1) |
| Zip member | `<Region>_MOM_Factor_Daily.csv` (upper-case `MOM`, even when the zip name says `Mom`); 178,143 bytes each | V (C1) |
| RF | None in the file | V (C1) |
| Sentinels observed | 0 | V (C1) |
| Creation stamp | `202609` | V (C1) |

---

## 5. Dataset cards

Common to every card: the base URL is `https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/` [V, P1 `href="ftp/..."`]. The server answered HEAD requests for case variants of the names (for example `Asia_Pacific_ex_Japan_Mom_Factor_Daily_CSV.zip`, `Europe_5_Factors_daily_CSV.zip`) with HTTP 200 and the same Last-Modified, and a non-existent name with HTTP 404 [V]. The registry must still use the exact spelling of the P1 link.

### 5.1 US 5 factors, daily (`us_ff5_daily`)

| Field | Value | Tag |
| --- | --- | --- |
| File URL | `.../ftp/F-F_Research_Data_5_Factors_2x3_daily_CSV.zip` | V (P1) |
| Description page | P6 | V |
| Universe | P6: Rm-Rf is the "value-weight return of all CRSP firms incorporated in the US and listed on the NYSE, AMEX, or NASDAQ that have a CRSP share code of 10 or 11 at the beginning of month t, good shares and price data at the beginning of t, and good return data for t minus the one-month Treasury bill rate." Style factors: "all NYSE, AMEX, and NASDAQ stocks for which we have ..." (same eligibility text as 4.1). | V |
| Breakpoints | P1: "the breakpoints use only NYSE firms" | V |
| Construction | 2x3 sorts as in 4.1, 6 value-weight portfolios per characteristic (P6) | V |
| Currency | USD | U (inferred, see Q1) |
| Source database | Preamble line 1: "This file was created by using the 202609 CRSP database." P1: from the January 2025 release the US returns use CRSP's "Flat File Format 2.0 (CIZ)". | V |
| Risk-free rate | Preamble lines 2-3 (quoted in section 2, Q3): Ibbotson Associates until 202405, ICE BofA US 1-Month Treasury Bill Index from 202406 | V |
| RF values observed | 0.00 to 0.06, two decimals; 20.8% of rows are 0.00 | V (C3) |
| Date range stated | P6 shows no daily range. Its HTML contains "Daily Returns: July 1, 1963-May 31, 2014" inside an HTML comment (not displayed, stale). | V |
| First / last date | 1963-07-01 / 2026-09-30 | V (C1) |
| Rows | 15,918 | V (C1) |
| Calendar | NYSE trading days; no weekend rows. US holidays absent. | V (C2) |
| Header | `,Mkt-RF,SMB,HML,RMW,CMA,RF` | V (C1) |
| Preamble | 4 lines: stamp line, two T-bill lines, blank. Header is line index 4. | V (C1) |
| Row layout | `19630701,   -0.67,    0.00,   -0.33,   -0.01,    0.16,    0.01` (spaces after commas) | V (C1) |
| Footer | Blank line, then `Copyright 2026 Eugene F. Fama and Kenneth R. French` (plain ASCII, **no 0xA9 byte**) | V (C1) |
| Encoding | ASCII, decodes as UTF-8, CRLF | V (C1) |
| Missing-value convention | Not in the file. P1: "Missing data are indicated by -99.99 or -999." | V |
| Sentinels observed | 0 | V (C1) |
| Zip member | `F-F_Research_Data_5_Factors_2x3_daily.csv`, 1,019,175 bytes, zip timestamp 2026-10-26 13:44:22 | V (C1) |
| Creation stamp | `202609` | V |
| HTTP Last-Modified / ETag | Tue, 27 Oct 2026 15:18:47 GMT / `"61efb9762666dd1:0"` | V |
| SHA-256 | `e58577223032aa45071a46686f7068900c371b516c9eb04e28e974c34264f84f` (equals the `sha256` in the existing `data/factors/meta.json`) | V |
| Downloaded at | 2026-11-18T10:45:02Z | V |
| Update cadence | P1: "We reconstruct the full history of returns each month when we update the portfolios. (Historical returns can change, for example, if CRSP revises its database.)" | V |
| Caveats the library states (P1) | December 2012 change of the market return; January 2015 CRSP shares revision for 1925-1946; May 2015 change of daily-return rules ("stocks are dropped from a portfolio immediately after their CRSP delist date" and the 200-day missing-price rule); August 2016 deferred-tax change to BE; August 2018 operating-profitability change (minority interest in the denominator); September 2020 removal of the FASB 106 adjustment; September 2021 switch to CRSP's CRSP-Compustat links; January 2025 switch from CRSP FIZ to CIZ files ("In the new Flat File Format (CIZ), monthly returns are compounded daily returns with dividends reinvested on their ex-dates"); June 2024 T-bill source change. P1 also links a December 2023 paper (SSRN 4629613, "Production of U.S. Rm-Rf, SMB, and HML in the Fama-French Data Library") that estimates the effect of these changes on SMB and HML. Its content was not read. | V (texts), paper content U |

### 5.2 Europe 5 factors, daily (`europe_ff5_daily`)

Shared facts: 4.1. Universe: the 16 countries checked under Europe in section 3, including Great Britain, Switzerland and Norway [V].

| Field | Value | Tag |
| --- | --- | --- |
| File URL | `.../ftp/Europe_5_Factors_Daily_CSV.zip` | V (P1) |
| Description page | P2 | V |
| First / last date, rows | 1990-07-02 / 2026-09-30, 9,458 | V (C1) |
| First rows | `19900702    ,0.99    ,0.00   ,-0.56    ,0.43   ,-0.25    ,0.03` and `19900703    ,0.33   ,-0.09    ,0.00    ,0.02    ,0.28    ,0.03` | V (C1) |
| Observed ranges (percent) | Mkt-RF [-12.00, 10.72], SMB [-5.30, 3.32], HML [-4.14, 4.38], RMW [-2.18, 4.18], CMA [-2.55, 2.16], RF [0.00, 0.03] | V (C1) |
| Zip member | `Europe_5_Factors_Daily.csv`, zip timestamp 2026-10-21 10:01:48 | V |
| HTTP Last-Modified / ETag | Mon, 26 Oct 2026 20:51:47 GMT / `"11d38d18b65dd1:0"` | V |
| SHA-256 | `df7d8ed366ae86440ba44a4c7c71b1e086ffba43e081bf3bca0d69dcf787638a` | V |
| Downloaded at | 2026-11-18T10:45:11Z | V |
| Plan check | `docs/PLAN.md` said "9,458 daily rows from 1990-07-02 to 2026-09-30 ... missing values marked -99.99, built from a Bloomberg database". All four facts confirmed. | V |

### 5.3 Developed 5 factors, daily (`developed_ff5_daily`)

Shared facts: 4.1. Universe: all 23 countries of section 3.

| Field | Value | Tag |
| --- | --- | --- |
| File URL | `.../ftp/Developed_5_Factors_Daily_CSV.zip` | V |
| First / last date, rows | 1990-07-02 / 2026-09-30, 9,458 | V |
| First row | `19900702    ,0.69   ,-0.08   ,-0.33    ,0.21    ,0.00    ,0.03` | V |
| Observed ranges | Mkt-RF [-9.62, 9.20], SMB [-5.27, 2.86], HML [-3.10, 4.16], RMW [-1.66, 1.99], CMA [-2.65, 2.16], RF [0.00, 0.03] | V |
| Zip member | `Developed_5_Factors_Daily.csv`, 2026-10-21 10:01:10 | V |
| Last-Modified / ETag | Mon, 26 Oct 2026 20:51:32 GMT / `"cdf938c88b65dd1:0"` | V |
| SHA-256 | `f6c5ceea945f4c2829025fc654d6a878041eba85765c88ee05ba34640f622831` | V |
| Downloaded at | 2026-11-18T10:45:07Z | V |
| Caveat | Mixes markets that close at different times of day (section 6.3) | V (C6) |

### 5.4 Developed ex US 5 factors, daily (`developed_ex_us_ff5_daily`)

Shared facts: 4.1. Universe: 22 countries (Developed minus the United States; **includes Canada**).

| Field | Value | Tag |
| --- | --- | --- |
| File URL | `.../ftp/Developed_ex_US_5_Factors_Daily_CSV.zip` | V |
| First / last date, rows | 1990-07-02 / 2026-09-30, 9,458 | V |
| First row | `19900702    ,0.87    ,0.08   ,-0.39    ,0.07    ,0.03    ,0.03` | V |
| Observed ranges | Mkt-RF [-9.58, 7.43], SMB [-4.91, 3.21], HML [-2.82, 3.23], RMW [-1.97, 2.81], CMA [-2.05, 2.42], RF [0.00, 0.03] | V |
| Zip member | `Developed_ex_US_5_Factors_Daily.csv`, 2026-10-21 10:00:32 | V |
| Last-Modified / ETag | Mon, 26 Oct 2026 20:51:39 GMT / `"5bb3a0cc8b65dd1:0"` | V |
| SHA-256 | `c02b42f00231278768efe3c326b232159f581141f3f2f43bf48ceb952f434105` | V |
| Downloaded at | 2026-11-18T10:44:50Z | V |

### 5.5 Japan 5 factors, daily (`japan_ff5_daily`)

Shared facts: 4.1. Universe: Japan only.

| Field | Value | Tag |
| --- | --- | --- |
| File URL | `.../ftp/Japan_5_Factors_Daily_CSV.zip` | V |
| First / last date, rows | 1990-07-02 / 2026-09-30, 9,458 | V |
| First row | `19900702    ,0.85    ,0.31   ,-0.05   ,-0.07    ,0.18    ,0.03` | V |
| Observed ranges | Mkt-RF [-10.85, 13.02], SMB [-9.05, 4.63], HML [-4.88, 4.57], RMW [-3.80, 3.59], CMA [-3.49, 3.88], RF [0.00, 0.03] | V |
| Zip member | `Japan_5_Factors_Daily.csv`, 2026-10-21 10:02:26 | V |
| Last-Modified / ETag | Mon, 26 Oct 2026 20:51:54 GMT / `"20ed74d58b65dd1:0"` | V |
| SHA-256 | `429da03b83e7688a85433825412db59604a1ac6a370adbc98f6cdd2c119c77af` | V |
| Downloaded at | 2026-11-18T10:44:58Z | V |
| Caveat | Daily correlation with same-day North America Mkt-RF is 0.040, with the previous day's 0.413 (section 6.3) | V (C6) |

### 5.6 North America 5 factors, daily (`north_america_ff5_daily`)

Shared facts: 4.1. Universe: United States and Canada. Source: Bloomberg, not CRSP.

| Field | Value | Tag |
| --- | --- | --- |
| File URL | `.../ftp/North_America_5_Factors_Daily_CSV.zip` | V |
| First / last date, rows | 1990-07-02 / 2026-09-30, 9,458 | V |
| First row | `19900702    ,0.30   ,-0.36   ,-0.11    ,0.30   ,-0.02    ,0.03` | V |
| Observed ranges | Mkt-RF [-11.93, 10.63], SMB [-4.61, 5.15], HML [-6.50, 6.63], RMW [-3.26, 3.43], CMA [-6.47, 3.70], RF [0.00, 0.03] | V |
| Zip member | `North_America_5_Factors_Daily.csv`, 2026-10-21 10:03:40 | V |
| Last-Modified / ETag | Mon, 26 Oct 2026 20:52:02 GMT / `"5593e8d98b65dd1:0"` | V |
| SHA-256 | `6a3690e29b86ca0a4fa74d0f5839bdef4309050b8e7fd44f80e2ef2c64189bf5` | V |
| Downloaded at | 2026-11-18T10:45:05Z | V |
| Caveat | Not a substitute for the US file: correlations with the US file are 0.998 (Mkt-RF) but 0.91-0.97 for the style factors, and mean SMB differs by 0.63% a year (section 6.1) | V (C4) |

### 5.7 Asia Pacific ex Japan 5 factors, daily (`asia_pacific_ex_japan_ff5_daily`)

Shared facts: 4.1. Universe: Australia, Hong Kong, New Zealand, Singapore.

| Field | Value | Tag |
| --- | --- | --- |
| File URL | `.../ftp/Asia_Pacific_ex_Japan_5_Factors_Daily_CSV.zip` | V |
| First / last date, rows | 1990-07-02 / 2026-09-30, 9,458 | V |
| First row | `19900702    ,0.40    ,0.07    ,0.60   ,-0.40    ,0.33    ,0.03` | V |
| Observed ranges | Mkt-RF [-10.32, 10.00], SMB [-5.92, 4.27], HML [-3.72, 5.11], RMW [-4.70, 3.71], CMA [-4.94, 3.85], RF [0.00, 0.03] | V |
| Zip member | `Asia_Pacific_ex_Japan_5_Factors_Daily.csv`, 2026-10-21 10:03:04 | V |
| Last-Modified / ETag | Mon, 26 Oct 2026 20:51:25 GMT / `"653f5c38b65dd1:0"` | V |
| SHA-256 | `f7bdb5344e2d51de25d7fd641eb7e4d93d7f72116273a64550943a56695f95b6` | V |
| Downloaded at | 2026-11-18T10:44:55Z | V |
| Caveat | Four markets only; Hong Kong and Singapore close later than Sydney and Wellington. Exact closing hours [U]. | V / U |

### 5.8 US momentum, daily (`us_mom_daily`)

| Field | Value | Tag |
| --- | --- | --- |
| File URL | `.../ftp/F-F_Momentum_Factor_daily_CSV.zip` | V (P1) |
| Description page | P7 | V |
| Construction | P7: "We use six value-weight portfolios formed on size and prior (2-12) returns to construct Mom. The portfolios, which are formed daily, are the intersections of 2 portfolios formed on size (market equity, ME) and 3 portfolios formed on prior (2-12) return. The daily size breakpoint is the median NYSE market equity. The daily prior (2-12) return breakpoints are the 30th and 70th NYSE percentiles." Preamble: "Prior return is measured from day - 250 to - 21." | V |
| Universe | P7: "NYSE, AMEX, and NASDAQ stocks with prior return data ... a stock must have a price for the end of day t-251 and a good return for t-21. In addition, any missing returns from t-250 to t-22 must be -99.0, CRSP's code for a missing price. Each included stock also must have ME for the end of day t-1." | V |
| Currency | USD | U (inferred) |
| Source | "This file was created by using the 202609 CRSP database.  It" (two spaces, then the text continues) | V |
| Date range stated / observed | P7: "November 3, 1926 - September 30, 2026" / 1926-11-03 to 2026-09-30 | V |
| Rows | 26,237 | V |
| Calendar | Equal to the US 5-factor calendar over 1963-07-01..2026-09-30 | V (C2) |
| Header | `,Mom` | V |
| Preamble | 13 lines (description of MOM, then "Missing data are indicated by -99.99 or -999.", blank). Header at line index 13. | V |
| Row layout / footer | `19261103,   0.55`; footer `Copyright 2026 Eugene F. Fama and Kenneth R. French` | V |
| Sentinels observed | 0 | V |
| Observed range | Mom [-18.53, 7.12] | V |
| RF | None | V |
| Zip member | `F-F_Momentum_Factor_daily.csv`, 473,140 bytes, 2026-10-26 13:51:28 | V |
| Last-Modified / ETag | Tue, 27 Oct 2026 15:18:47 GMT / `"8c28d4762666dd1:0"` | V |
| SHA-256 | `e56d5bc845544e2993e77353b12c611cfce3149ef754f9b59fc67904ddadd369` | V |
| Downloaded at | 2026-11-18T10:45:03Z | V |
| Caveats | Same US caveats as 5.1. Monthly reconstitution note on P1 ("The momentum and short term reversal portfolios are reconstituted monthly") refers to the monthly research portfolios; P7 says the daily portfolios are "formed daily". | V |

### 5.9-5.14 Regional daily momentum files

Shared facts: 4.2. Universe: as the matching region in section 3.

| Key | File URL (`.../ftp/` +) | First row | Range (WML, %) | Zip member, timestamp | Last-Modified / ETag | SHA-256 | Downloaded at |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `europe_mom_daily` | `Europe_Mom_Factor_Daily_CSV.zip` | `19901101    ,0.29` | [-10.87, 6.05] | `Europe_MOM_Factor_Daily.csv`, 2026-10-21 10:01:44 | Mon, 26 Oct 2026 20:51:50 GMT / `"931cfdd28b65dd1:0"` | `24c64dfc48d9ebf86510328517b7bb67f982b5fb60d81eff5d8db377a9112e2a` | 10:44:57Z |
| `developed_mom_daily` | `Developed_Mom_Factor_Daily_CSV.zip` | `19901101    ,0.83` | [-9.41, 4.31] | `Developed_MOM_Factor_Daily.csv`, 10:01:08 | Mon, 26 Oct 2026 20:51:43 GMT / `"80eabdce8b65dd1:0"` | `ea5851bc1dbda296b40fee41d6a11703c0db93032efdcf903a5d937bddcc4954` | 10:45:13Z |
| `developed_ex_us_mom_daily` | `Developed_ex_US_Mom_Factor_Daily_CSV.zip` | `19901101    ,1.01` | [-6.19, 3.64] | `Developed_ex_US_MOM_Factor_Daily.csv`, 10:00:32 | Mon, 26 Oct 2026 20:51:43 GMT / `"df080ce8b65dd1:0"` | `23a98ba9dc4908a87cc211fce3ed85fbc17c6d44c85285099a6091f9cf43639b` | 10:45:00Z |
| `japan_mom_daily` | `Japan_Mom_Factor_Daily_CSV.zip` | `19901101    ,1.30` | [-9.40, 8.55] | `Japan_MOM_Factor_Daily.csv`, 10:02:20 | Mon, 26 Oct 2026 20:51:57 GMT / `"984d5bd78b65dd1:0"` | `776ef58fb371bad57fc44ab1a3d0f97cf6d608bba2701d53846ba25dcab9fb58` | 10:45:09Z |
| `north_america_mom_daily` | `North_America_Mom_Factor_Daily_CSV.zip` | `19901101    ,0.08` | [-12.07, 6.45] | `North_America_MOM_Factor_Daily.csv`, 10:03:30 | Mon, 26 Oct 2026 20:52:05 GMT / `"1d30abdb8b65dd1:0"` | `8f7ed1e8a3a07bc7da97b940bd1317a85e4f7a09e7fdb54e8564127657b6fcaf` | 10:44:52Z |
| `asia_pacific_ex_japan_mom_daily` | `Asia_Pacific_ex_Japan_MOM_Factor_Daily_CSV.zip` (upper-case `MOM` in the P1 link) | `19901101    ,0.72` | [-10.42, 9.28] | `Asia_Pacific_ex_Japan_MOM_Factor_Daily.csv`, 10:02:54 | Mon, 26 Oct 2026 20:51:28 GMT / `"6c50c8c58b65dd1:0"` | `4acbb06d70f52f0580b4f10949fca7dd973f049d6f51e9c567defb38ae0913b5` | 10:44:53Z |

All six: 1990-11-01 to 2026-09-30, 9,370 rows, stamp 202609, Bloomberg, 0 sentinels, header `,WML`, all timestamps 2026-10-21 for the zip member, download date 2026-11-18 [V, C1].

---

## 6. Cross-dataset facts (computed, C2-C8)

### 6.1 US (CRSP) vs North America (Bloomberg), 9,128 common dates 1990-07-02..2026-09-30 [V, C4]

| Factor | Daily corr | Tracking error (sd of difference x sqrt 252) | Mean US (x252) | Mean NA (x252) |
| --- | --- | --- | --- | --- |
| Mkt-RF | 0.9981 | 1.14% | 9.54% | 9.37% |
| SMB | 0.9699 | 2.47% | 0.52% | -0.11% |
| HML | 0.9213 | 4.44% | 2.35% | 1.76% |
| RMW | 0.9069 | 3.38% | 3.69% | 3.67% |
| CMA | 0.9143 | 3.44% | 2.07% | 3.13% |
| Mom vs WML (9,042 dates) | 0.9431 | 5.07% | - | - |

Sub-periods (daily corr, Mkt-RF / SMB / HML / RMW / CMA): 1990-2006: 0.998 / 0.976 / 0.918 / 0.939 / 0.931; 2007-2026: 0.998 / 0.968 / 0.937 / 0.878 / 0.898.

### 6.2 Developed vs its four regions [V, C5]

- Developed Mkt-RF regressed (no intercept) on North America, Europe, Japan, Asia Pacific ex Japan Mkt-RF, one regression per calendar year (37 years, 1990-2026): R² min 0.99637 (1993), median 0.99976; weights sum to 0.9879-1.0046; largest absolute daily residual 0.217%. Weights move from (NA, EU, JP, APxJ) = (0.349, 0.269, 0.355, 0.024) in 1990 to (0.693, 0.196, 0.078, 0.036) in 2026. This is what a value-weighted partition with drifting weights produces.
- The style factors are not a partition (one static regression over the full sample): R² 0.69 (SMB), 0.95 (HML), 0.88 (RMW), 0.93 (CMA). Developed WML on the regional WMLs: R² 0.972. Consistent with Developed using developed-wide size breaks (stated for momentum in P3).
- Developed ex US Mkt-RF on Europe, Japan, Asia Pacific ex Japan and North America, per calendar year: R² min 0.9933, median 0.9969 (not exact, because North America includes the US while Developed ex US includes only Canada from that region).

### 6.3 Synchronicity, regional Mkt-RF vs North America Mkt-RF on the regional calendar [V, C6]

| Region | corr(r_t, NA_t) | corr(r_t, NA_{t-1}) | corr(r_t, NA_{t+1}) | Weekly corr (calendar weeks ending Friday) | Beta on NA: daily / Dimson (lag 0 + lag 1) / weekly |
| --- | --- | --- | --- | --- | --- |
| Europe | 0.555 | 0.258 | -0.022 | 0.765 | 0.562 / 0.579 + 0.294 = 0.872 / 0.819 |
| Japan | 0.040 | 0.413 | 0.001 | 0.406 | 0.049 / 0.077 + 0.508 = 0.585 / 0.483 |
| Asia Pacific ex Japan | 0.351 | 0.432 | -0.025 | 0.654 | 0.327 / 0.351 + 0.422 = 0.772 / 0.696 |

Reading: Tokyo closes before New York opens, so the US day `t-1` drives Japan's day `t`. A same-day daily beta of a Japanese return on a factor that contains North America is biased towards zero. Developed factors contain 35-69% North America by weight (6.2).

### 6.4 Daily files reproduce the monthly files for the market factor only [V, C7]

Monthly value rebuilt from the daily file: Mkt-RF as `prod(1 + Mkt-RF + RF) - prod(1 + RF)` over the month's rows; other factors as `prod(1 + f) - 1`. Difference to the monthly file of the same release, in percentage points:

| Daily file vs monthly file | Months | Mkt-RF rms / max abs | SMB rms / max | HML rms / max | RMW rms / max | CMA rms / max | RF rms / max |
| --- | --- | --- | --- | --- | --- | --- | --- |
| US (`F-F_Research_Data_5_Factors_2x3_CSV.zip`) | 759 | 0.021 / 0.180 | 0.228 / 3.951 | 0.220 / 2.058 | 0.209 / 3.168 | 0.150 / 1.202 | 0.056 / 0.111 |
| Europe (`Europe_5_Factors_CSV.zip`) | 435 | 0.030 / 0.185 | 0.241 / 3.166 | 0.180 / 1.248 | 0.120 / 1.130 | 0.130 / 0.835 | 0.052 / 0.120 |
| Developed (`Developed_5_Factors_CSV.zip`) | 435 | 0.017 / 0.065 | 0.162 / 1.781 | 0.176 / 1.559 | 0.093 / 0.612 | 0.145 / 1.019 | 0.052 / 0.120 |

Monthly files used (downloaded 2026-11-18, stamp 202609): US SHA-256 `17d7a575e71d6764a70ddec3f8d887756c0eebf3a60f64d6ba95d2adde3fed26` (Last-Modified Tue, 27 Oct 2026 15:18:47 GMT); Europe `87c61cc3311a4e541f623a3532af4e93be033a1897cdf664e2b549348eee9bcb` (Mon, 26 Oct 2026 20:50:01 GMT); Developed `954580906c3ae6fc1870677e40dfbe5a94a6cf188be5330c896f2fc578d9f0ba` (Mon, 26 Oct 2026 20:49:43 GMT). Their preambles: US "This file was created using the 202609 CRSP database." plus the T-bill lines and "The annual TBill return is compounded from the monthly T-bill rates from January to December."; Europe and Developed: the same 6-line Bloomberg preamble as the daily files.

A long-short factor compounded over days is not the monthly long-short return (the legs are not rebalanced daily), so only Mkt-RF is an invariant.

### 6.5 Daily RF is quantised to 0.01% per day [V, C3, C8]

Every RF value has two decimals; the US file uses 7 distinct values (0.00-0.06), the regional files 4 (0.00-0.03). Compounded over a calendar year, daily RF minus compounded monthly RF ranges from -1.03 (2003) to +0.92 (2002) percentage points a year in the US file (mean -0.006, sd 0.385 over 1991-2026), and from -1.03 to +1.01 in the regional file. Examples (US file): 2019 +0.41, 2023 +0.19, 2025 +0.88. Over the full overlap the means agree (US: daily x252 = 2.553%, monthly x12 = 2.563%). Every daily RF in 2009-2015 is 0.00 in both files.
Consequence: over a short window the RF rounding error moves a stock's estimated alpha by up to about one percentage point a year (alpha absorbs minus the mean RF error). `docs/methodology-datasets.md` D11 handles this.

### 6.6 Release timing [V]

- All 12 regional files: HTTP Last-Modified between Mon, 26 Oct 2026 20:51:25 and 20:52:05 GMT (40 seconds); zip members dated 2026-10-21 10:00-10:03.
- Both US daily files: Tue, 27 Oct 2026 15:18:47 GMT; zip members dated 2026-10-26.
- Every file: stamp 202609, last date 2026-09-30.
- One release observed. "All files are always updated together" is [U] beyond this release.

---

## 7. Discrepancies found (assumed vs verified)

| # | Assumed (where) | Verified | Evidence |
| --- | --- | --- | --- |
| X1 | Returns "assumed USD" (PLAN) | Confirmed USD for regional files; US files do not state it | P2, P3 |
| X2 | UK membership unknown (PLAN) | Great Britain is in Europe, Developed and Developed ex US | P2/P3 table |
| X3 | RF unknown (PLAN) | US one-month T-bill in every 5-factor file; regional RF differs from US-file RF by 0.01 on 346 of 9,128 dates; momentum files have no RF | P2, C3 |
| X4 | Momentum file names follow `<Region>_Mom_Factor_Daily_CSV.zip` (prompt) | Asia Pacific ex Japan link is `Asia_Pacific_ex_Japan_MOM_Factor_Daily_CSV.zip`; zip members are all `..._MOM_Factor_Daily.csv`; US file is `F-F_Momentum_Factor_daily_CSV.zip` (lower-case `daily`) | P1, C1 |
| X5 | Momentum column (plan: "Carhart momentum") | Header is `WML` in regional files, `Mom` in the US file | C1 |
| X6 | Regional daily momentum starts 1 December 1990 (P3) | File starts 1990-11-01 | C1 |
| X7 | US 5-factor footer contains byte 0xA9 (`docs/methodology.md` M1.1 step 2, test T05) | This vintage's footer is plain ASCII `Copyright 2026 ...`; regional files have no footer at all. Decoding as latin-1 is still safe; the stated reason is not true for this vintage. | C1 |
| X8 | US preamble example "This file was created by CMPT_ME_BEME_OP_INV_RETS_DAILY using the 202609 CRSP database." (test T01) | Real line: "This file was created by using the 202609 CRSP database." | C1 |
| X9 | Real first US row `19630701, -0.67, 0.00, -0.34, -0.01, 0.16, 0.012` (test T03) | Real row: `19630701,   -0.67,    0.00,   -0.33,   -0.01,    0.16,    0.01` (HML -0.33, RF two decimals). T03 is a synthetic fixture and stays valid; it must not be described as the real row. | C1 |
| X10 | Regional calendars like a trading calendar | Every weekday is present, including 25 Dec and 1 Jan; 330 dates are not in the US file | C2 |
| X11 | P1 sentence on MSCI (1975-2006) and Bloomberg (2007-) could be read as applying to the regional factors | It belongs to the international country portfolios section | P1 |
| X12 | Existing parser constant `MIN_ROWS = 15_000` (`backend/factordesk/data/factors.py`) | Regional files have 9,458 / 9,370 rows; a per-dataset minimum is needed | C1 |
| X13 | US 5-factor page shows the daily date range | It shows none; the stale range "July 1, 1963-May 31, 2014" sits inside an HTML comment | P6 |

## 8. Still unverified

- U1. Currency of the US files (USD is the natural reading; no page states it).
- U2. Source of the regional T-bill series (monthly values equal the US file's in 433 of 435 months).
- U3. How Developed and Developed ex US 5-factor breakpoints are formed (P2 is silent; P3 answers it for momentum only).
- U4. Whether the regional factors used a non-Bloomberg source for early years.
- U5. What moves the regional factors on days when all of a region's markets are closed (currency moves are the likely cause).
- U6. Update cadence of the regional files, and whether US and regional files always change in the same release.
- U7. FX conversion time the library uses to translate local returns into USD.
- U8. Dates at which each country entered each regional sample.
