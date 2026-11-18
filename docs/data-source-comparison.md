# Price data sources: Yahoo, Tiingo and Alpaca compared

Status: research note, 2026-11-18. Follows `docs/research-protocol.md`.
Every claim is marked **VERIFIED** (a computation that was run, or a quoted line with its URL) or **UNVERIFIED**.
Section 1 was written and saved before any price data was downloaded. It was not edited after the results
were seen. Later corrections, if any, are added as new lines in section 1.6.

---

## 1. Pre-registration (written before any data was fetched)

Written 2026-11-18T11:12Z. At that time no Tiingo or Alpaca request had been made and no new Yahoo download had
been made for this study. The only result known in advance is the one in `docs/validation/spy-slice-validation.md`
(Yahoo SPY, full history: R2 0.967, residual lag-1 autocorrelation -0.40; `^SP500TR` and VFINX: R2 about 0.995,
autocorrelation -0.06 and -0.11).

### 1.1 Sources, tickers and samples (fixed now)

- Sources:
  - (A) Yahoo via yfinance, `Ticker.history(period="max", interval="1d", auto_adjust=False, actions=True, repair=False)`.
  - (B) Tiingo end-of-day prices (`close`, `adjClose`, `divCash`, `splitFactor`), full history.
  - (C) Alpaca historical daily bars, `feed=sip`, once with `adjustment=raw` and once with `adjustment=all`, from
    2016-01-01 (the expected start of SIP history; checked, not assumed).
- Tickers (chosen before any data was seen):
  - SPY: the series with the known problem.
  - VFINX: a 4:00 pm NAV benchmark. Tiingo only, if Tiingo covers mutual funds. Alpaca is asked once to confirm
    whether it covers it.
  - AAPL.
  - NVDA: large split history.
  - KO: steady dividends.
  - AVGO: a recent split (10-for-1, July 2024) that also pays dividends.
  - Reference only, Yahoo: `^SP500TR`, the S&P 500 total-return index, 4:00 pm close.
  - Tiingo: 6 series (2 calls each: metadata and prices). Alpaca: 5 symbols plus a single VFINX probe.
- Factor data: French US daily 5 factors
  (`F-F_Research_Data_5_Factors_2x3_daily_CSV.zip`), downloaded once and parsed in memory. The vintage
  (`Last-Modified` and SHA-256) is recorded in section 2.
- Periods:
  - P-LONG: the longest common period per ticker of Yahoo, Tiingo and French.
  - P-2016: 2016-01-04 to the French last date, common to all sources that have the ticker.
  - Sub-periods for residual statistics: "pre-2010" (dates up to 2009-12-31) and "2010 onward".
- Return definition, the same for every source: `r_t = P_t / P_{t-1} - 1` on the source's own adjusted close
  (Yahoo `Adj Close`, Tiingo `adjClose`, Alpaca `close` with `adjustment=all`). Calendar alignment follows M2:
  a row is kept only when exactly one French date lies in `(d_{t-1}, d_t]` and it equals `d_t`.
- Regression: per M3.1 and M0.5/D2. `sm.OLS(y, add_constant(F)).fit(cov_type="HAC",
  cov_kwds={"maxlags": L, "use_correction": False}, use_t=False)`, with `L = floor(4 (n/100)^(2/9))`,
  `y = r - RF`. Reported: n, R2, alpha (annualised x252) and its z, five betas, residual volatility (annualised,
  ddof 1) pre-2010 and from 2010, and residual lag-1 autocorrelation (full sample and per sub-period, from the
  residuals of the period's own fit).

### 1.2 Hypotheses and decision rules

These are data-quality comparisons. Most of them are threshold rules, not significance tests, so there are no
p-values to correct. Each hypothesis is its own family (protocol section 3). The registry lines are in 1.5.

**H1. The late-close noise is a property of Yahoo's SPY data, not of the model.**
Claim: with Tiingo's SPY adjusted close, over P-LONG, the residual lag-1 autocorrelation of the pre-2010 residuals
(from the P-LONG fit) is above -0.10, and the P-LONG R2 is at least 0.990.

- Supported: autocorrelation > -0.10 **and** R2 >= 0.990.
- Rejected: autocorrelation < -0.20 **or** R2 < 0.980.
- Anything else: inconclusive.
- Against H1, in numbers: Tiingo's pre-2010 SPY daily returns equal Yahoo's within 1 bp on 99% or more of
  days. That would mean both vendors carry the same consolidated close. The noise would then be a property of
  the SPY consolidated-close series (any vendor), not of Yahoo.

**H2. Alpaca SIP and Yahoo agree on daily returns after 2016.**
Claim: for SPY, AAPL and KO over P-2016, `|r_Alpaca(all) - r_Yahoo|` is at most 1 bp on at least 99% of common
days.

- Supported: all three tickers meet the rule.
- Rejected: any ticker fails.
- Reported for each ticker as well: days above 1, 5 and 25 bp, the max and the correlation. Where it fails, the
  report shows whether the cause is the close itself (raw close differences) or the adjustment (dividend
  method), using `adjustment=raw` with Alpaca's own dividend amounts.

**H3. Each provider's adjusted-close return on ex-dividend dates equals the independent formula.**
Claim: for every ex-dividend event of every ticker in each provider's data, the provider's adjusted return
`P_t/P_{t-1} - 1` equals `(C_t + D_t)/C_{t-1} - 1` within 1 bp, where `C` and `D` are the same provider's
unadjusted (split-adjusted only) close and dividend.

- Supported for a provider: 100% of its events are within 1 bp.
- Mostly supported: at least 95% of events are within 1 bp.
- Rejected: fewer than 95%.
- Secondary: the CRSP convention `C_t/(C_{t-1} - D_t)` with the M1.4 tolerance `tau_t = 1e-4 + 0.01/C_{t-1}`.
  The validation found that this convention is the one Yahoo uses. I expect the primary formula to fail by
  `D/C x r_t` on volatile ex-dates even when the provider's adjustment is internally correct, so the secondary
  rule decides whether the adjustment is *correct*. The primary rule only decides whether the formula as stated
  holds.

**H4. Tiingo's SPY history starts by 1993-02-01.**

- Supported: both the metadata `startDate` and the first returned price row are on or before 1993-02-01.
- Rejected otherwise.

**Descriptive (no hypothesis): closing-price definition.** For the 20 most recent trading days that every source
has (ending on or before 2026-11-13), compare each source's raw close for SPY, AAPL, NVDA, KO and AVGO with
the others. Where possible, compare with an official closing-auction price from a verifiable source (stated in
section 4.4). Report the count of exact matches and the max difference in cents.

### 1.3 What decides the recommendation (fixed now)

**Default source** (the series a report uses) must meet all of these:

1. Full history: SPY from 1993 (H4), AAPL from 1980, NVDA from 1999.
2. Dividend and split handling correct by the secondary rule of H3. No unexplained split error.
3. Its SPY regression is at least as clean as Yahoo's: pre-2010 residual autocorrelation not more negative
   than Yahoo's minus 0.02.
4. Its free-plan terms, as written on the official pages, allow a user to fetch data with their own key in an
   open-source tool that writes a local report with derived statistics and a price chart. If the terms are
   ambiguous, it can still be the default only if no other source is clearly permitted, and the report says so.
5. Its rate limits allow at least about 10 new tickers per hour.

Among sources that meet 1-5, a source that **passes H1** is preferred over Yahoo.

**Cross-check source** (a second opinion on the overlap, never the series a report uses): covers 2016 onward
with returns that agree with the default within 1 bp on at least 99% of days. Disagreements must be
explainable (adjustment method, close definition).

**Not at all**: terms that prohibit this use; or unexplained differences above 25 bp on more than 0.1% of days;
or coverage gaps (missing trading days) on more than 0.1% of the period it claims to cover.

**Data-quality gate**: whatever the result, the recommendation includes a gate on residual lag-1
autocorrelation. Its starting point is G1 of the validation (autocorrelation below -0.2 with a
heteroskedasticity-robust z below -4). The study reports the value of the gate statistic for every source and
ticker. Any change to G1's thresholds is labelled as calibrated on this sample (in-sample, few tickers).

### 1.4 Power and multiple testing

- No hypothesis here is a significance test with a p-value, so Benjamini-Hochberg does not apply. The alpha z
  values in the regression tables are descriptive single tests (M0.6), shown to compare sources, not to make a
  claim about alpha.
- Power is not applicable to threshold rules. Sampling error of the lag-1 autocorrelation is about
  `1/sqrt(n)`: with about 4,200 pre-2010 days, that is 0.015. The H1 thresholds (-0.10 vs Yahoo's -0.40) are
  20 standard errors apart, so sampling noise cannot decide H1.
- Survivorship: all six tickers exist today (M1.5). Nothing here says anything about delisted stocks, except the
  documentation facts in section 6.

### 1.5 Registry lines (to be entered in `docs/registry/tests.jsonl`)

The write scope of this study is this file only, so the lines are kept here. `code_version` is "scratchpad
scripts, see section 9", because the scripts are not in the repo.

| test_id | hypothesis_id | status at 11:12Z | hypothesis (short) | spec |
| --- | --- | --- | --- | --- |
| T-20261118-101 | H-DS1 | pre-registered | Tiingo SPY pre-2010 residual autocorrelation > -0.10 and R2 >= 0.990 | SPY, Tiingo adjClose, P-LONG, FF5 US daily, HAC L(n) |
| T-20261118-102 | H-DS2 | pre-registered | Alpaca SIP vs Yahoo, <= 1 bp on >= 99% of days | SPY, AAPL, KO; P-2016; Alpaca `adjustment=all` |
| T-20261118-103 | H-DS3 | pre-registered | Ex-dividend adjusted return = (C+D)/C_prev - 1 within 1 bp | all tickers, each provider's own data |
| T-20261118-104 | H-DS4 | pre-registered | Tiingo SPY starts on or before 1993-02-01 | Tiingo metadata and price rows |
| T-20261118-105 | descriptive | pre-registered | Regression impact table, all sources | SPY, AAPL, NVDA (plus VFINX and `^SP500TR` as references), P-LONG and P-2016 |
| T-20261118-106 | descriptive | pre-registered | Closing-price definition, 20 recent days | SPY, AAPL, NVDA, KO, AVGO |

### 1.6 Amendments after data were seen

Amendments are added below with a time stamp and a reason.

- **A1, about 2026-11-18T11:21Z, before any price data was fetched: the Tiingo arm is withdrawn, and no Tiingo API
  call was made.** Reason: Tiingo's Terms of Use (<https://www.tiingo.com/tos/>, "Last Updated Date: November
  5th, 2026", read in full, VERIFIED, quoted in section 6.1) forbid three things this arm needs on the free Starter plan:
  - persistent storage of Tiingo Data or of Derived Products (section 1.6(a)). The design needs a disk cache,
    and this document needs the derived numbers;
  - "using Tiingo end-of-day data to validate another end-of-day dataset" (section 1.6(c)). That is the purpose
    of the arm;
  - and, under section 1.7(b), use through an AI tool needs a zero-data-retention or no-training setting that I
    cannot confirm for this session.

  Consequences:
  - H1 (T-20261118-101) and H4 (T-20261118-104) get status `abandoned`. They are not run.
  - H3 is run for Yahoo and Alpaca only.
  - VFINX comes from Yahoo, as a reference series only (as in the validation).
  - The question H1 asks ("is the pre-2010 SPY noise a Yahoo property?") cannot be answered with the free
    sources available here, because Alpaca SIP starts in 2016. Section 7 says what would answer it.
- **A2, same time.** To keep a pre-2010 comparison, the regression-impact table adds the two 4:00 pm
  references the validation used, both from Yahoo: `^SP500TR` and VFINX. This is descriptive, not a test of H1.
- **A3, after the first comparison run (data seen). Added diagnostics, all labelled "not pre-registered":**
  - Alpaca returns rebuilt from raw closes plus Alpaca's own corporate actions ("Alpaca rebuilt"). Reason:
    Alpaca's `adjustment=all` prices turned out to be rounded to cents.
  - Alpaca closing-auction prints (`/v2/stocks/auctions`) for SPY and AAPL 2016-2022, and for KO in March 2020.
    Reason: to find out which close is the official one.
  - KO and AVGO regressions over P-2016.
  - SPY sub-windows 2016-2020 and 2023 onward.
  - A rank-based lag-1 autocorrelation and a 5-day variance ratio (VR5) of residuals, to study the gate.
  - None of these changes a pre-registered rule or verdict.

---

## 2. Data and method

| Item | Value |
| --- | --- |
| French factors | `F-F_Research_Data_5_Factors_2x3_daily_CSV.zip`, `Last-Modified: Tue, 27 Oct 2026 15:18:47 GMT`, SHA-256 `e58577223032aa45071a46686f7068900c371b516c9eb04e28e974c34264f84f`, 15,918 rows, last date 2026-09-30. Parsed in memory (latin-1, header check, contiguous block, /100). Same vintage as the validation. |
| Yahoo | yfinance 1.8.0, `Ticker(t).history(period="max", interval="1d", auto_adjust=False, actions=True, repair=False)`, fetched 2026-11-18T11:22Z. Dates are calendar dates in America/New_York; rows dated 2026-11-18 or later were dropped. Tickers: SPY, VFINX, AAPL, NVDA, KO, AVGO, `^SP500TR`. |
| Alpaca bars | `GET https://data.alpaca.markets/v2/stocks/bars?symbols=SPY,AAPL,NVDA,KO,AVGO&timeframe=1Day&start=2016-01-01&end=2026-11-17&adjustment={raw,all}&feed=sip&limit=10000&sort=asc`, followed by `next_page_token`. Keys go in the `APCA-API-KEY-ID` and `APCA-API-SECRET-KEY` headers. Bar timestamps (`T04:00:00Z` or `T05:00:00Z`) are New York midnight, so the date is the UTC date part (asserted for every bar). |
| Alpaca corporate actions | `GET https://data.alpaca.markets/v1/corporate-actions?symbols=...&types=cash_dividend,forward_split,reverse_split&start=2016-01-01&end=2026-11-17&limit=1000` |
| Alpaca auctions | `GET https://data.alpaca.markets/v2/stocks/auctions?symbols=...&feed=sip`, for 2026-10-01..2026-11-17 (5 symbols), 2016-01-01..2022-12-31 (SPY, AAPL) and 2020-03-02..2020-03-13 (KO). The closing auction is the condition `6` print ("Market Center Closing Trade") of the primary listing exchange: `P` NYSE Arca (SPY), `Q` (from 2021) or `T` (earlier) Nasdaq (AAPL, NVDA, AVGO), `N` NYSE (KO). |
| Alpaca calls made | 11 in total (4 bar pages, 1 VFINX probe, 1 corporate actions, 5 auction pages). The rate-limit header showed 199 remaining every time. |
| Tiingo | No call made (amendment A1). |
| Returns | `r_t = P_t/P_{t-1} - 1` on each source's own rows. For cross-source comparisons, a day is used only when both sources have the same previous date. "Alpaca rebuilt": `r_t = C_t s_t / (C_{t-1} - D_t s_t) - 1` from raw closes `C`, Alpaca dividends `D` and split ratio `s` (CRSP form). |
| Regression | M2 alignment (exactly one French date in `(d_{t-1}, d_t]`, equal to `d_t`); `y = r - RF`; `sm.OLS(y, add_constant(F)).fit(cov_type="HAC", cov_kwds={"maxlags": L, "use_correction": False}, use_t=False)` with `L = floor(4 (n/100)^(2/9))`; statsmodels 0.15.0, pandas 3.1.1, Python 3.12. Residual volatility is `sqrt(252) sd(e)` (ddof 1). Lag-1 autocorrelation is Pearson, and its robust z is `sum e_t e_{t-1} / sqrt(sum e_t^2 e_{t-1}^2)`. |

**Replication check (VERIFIED):** Yahoo SPY over P-LONG gives n 8,474, R2 0.9673, alpha -0.58%/yr (z -2.24) and
residual autocorrelation -0.404 (z -13.1). These equal `docs/validation/spy-slice-validation.md` section 4.

---

## 3. Results: data comparison (all VERIFIED by `compare.py`, `spy_close.py`, `auction_hist.py`, `adj_method.py`, `spot_dates.py`)

### 3.1 Coverage

| Series | Yahoo first date | Alpaca first date | Alpaca rows to 2026-11-17 | French trading days missing |
| --- | --- | --- | --- | --- |
| SPY | 1993-01-29 | 2016-01-04 | 2,735 | 0 in either source (2016-01-04..2026-09-30) |
| AAPL | 1980-12-12 | 2016-01-04 | 2,735 | 0 |
| NVDA | 1999-01-22 | 2016-01-04 | 2,735 | 0 |
| KO | 1962-01-02 | 2016-01-04 | 2,735 | 0 |
| AVGO | 2009-08-06 | 2016-01-04 | 2,735 | 0 |
| VFINX | 1980-01-02 | not covered: Alpaca returned `{"bars": {}}` | - | - |
| `^SP500TR` | 1988-01-04 | (index, not requested) | - | - |

Alpaca's SIP history starts exactly at the first trading day of 2016 for all five symbols. That matches its plan
table ("Historical data timeframe: Since 2016", section 6.2).

### 3.2 Daily total-return differences against Yahoo `Adj Close`, 2016-01-05 to 2026-11-17

| Ticker | n | Alpaca `all`: days > 1 / 5 / 25 bp | share <= 1 bp | max bp (date) | corr | Alpaca rebuilt: days > 1 / 5 / 25 bp | share <= 1 bp | max bp |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| SPY | 2,734 | 869 / 173 / 13 | 68.2% | 268.8 (2020-03-13) | 0.99615 | 858 / 173 / 13 | 68.6% | 268.7 |
| AAPL | 2,734 | 443 / 40 / 1 | 83.8% | 25.0 (2022-02-24) | 0.999972 | 70 / 38 / 1 | 97.4% | 25.1 |
| NVDA | 2,734 | 928 / 68 / 0 | 66.1% | 10.9 (2019-12-12) | 0.999985 | 43 / 10 / 0 | 98.4% | 11.5 |
| KO | 2,734 | 767 / 4 / 2 | 72.0% | 72.6 (2020-03-10) | 0.99983 | 6 / 4 / 2 | 99.78% | 73.3 |
| AVGO | 2,734 | 962 / 40 / 2 | 64.8% | 71.4 (2018-03-21) | 0.99995 | 24 / 4 / 2 | 99.1% | 74.9 |

From 2023-01-01 the rebuilt Alpaca returns equal Yahoo within 1 bp on 100% of days for SPY (max 0.01 bp), AAPL
(max 0.29 bp) and KO (max 0.00 bp), n = 973.

The differences have four separate causes, each VERIFIED:

1. **Alpaca `adjustment=all` prices are rounded.** They have at most 2 decimals for SPY, AAPL and KO, 3 for
   AVGO and 4 for NVDA. On non-event days the adjusted day ratio should equal the raw one. Instead it differs by
   up to 0.5 bp (SPY), 3.7 bp (AAPL), 7.8 bp (NVDA) and 8.9 bp (AVGO), and by more than 1 bp on 377 to 932 days
   per ticker. Early prices are adjusted down to cents (NVDA min 0.6137), so rounding error is large relative
   to price. This alone explains most of the gap between the `all` and "rebuilt" columns.
2. **Alpaca's SPY daily close was not the official close from 2016 to mid-2022.** Section 3.5.
3. **Alpaca's corporate actions omit two SPY dividends.** Section 3.3.
4. **Yahoo doubles two AVGO dividends.** Section 3.3.

### 3.3 Dividend and split events, 2016-01-01 to 2026-11-17

Yahoo amounts are converted to the "as paid" basis by multiplying by later Yahoo split ratios.

| Ticker | Yahoo dividends | Alpaca dividends | Same ex-date | Amount disagreements (> 0.0001) | Splits (both sources agree on date and ratio) |
| --- | --- | --- | --- | --- | --- |
| SPY | 43 | 41 | 41 | 32, max 0.0034 (Yahoo rounds to 3 decimals, e.g. 1.078 vs Alpaca 1.078442) | none |
| AAPL | 44 | 44 | 44 | 0 | 2020-08-31 4:1 |
| NVDA | 43 | 43 | 43 | 0 | 2021-07-20 4:1, 2024-06-10 10:1 |
| KO | 43 | 43 | 43 | 0 | none |
| AVGO | 43 | 43 | 43 | **2**: 2018-03-21 and 2018-06-19, Yahoo 3.50 vs Alpaca 1.75 | 2024-07-15 10:1 |

- **Yahoo AVGO error (VERIFIED).** Broadcom's 8-K for its fiscal Q3 2018 says: "On June 29, 2018, the Company paid
  a cash dividend of $1.75 per share of common stock"
  (<https://www.sec.gov/Archives/edgar/data/0001730168/000173016818000036/avgo-08052018x8kxex99.htm>). Yahoo
  stores 0.350 (split-adjusted, that is 3.50 as paid) on 2018-03-21 and 2018-06-19, between correct values of
  0.175 on 2017-12-18 and 2018-09-18. Yahoo's `Adj Close` applies the wrong amount consistently: its ex-date
  total returns are +2.99% and -0.02%, against price returns of +1.50% and -1.34%. This puts about 0.7% of
  spurious return into each day.
  - The project audit (M1.4 A6) checks `Adj Close` against Yahoo's *own* `Dividends`, so it **cannot** see this
    error.
  - Effect on the AVGO P-2016 alpha: +0.14%/yr (section 4).
  - That the March 2018 dividend was also $1.75 is UNVERIFIED from a primary page. A search summary of Broadcom's
    Q2 FY2018 release says it was; I did not open the release.
- **Alpaca missing SPY dividends (VERIFIED in the data).** Yahoo has dividends ex 2016-03-18 (1.05) and 2018-06-15
  (1.246); Alpaca's corporate actions have none. Alpaca's `adjustment=all` series shows no factor change on
  either date: +0.21 and +0.17 bp, against the 51.3 and 44.7 bp those dividends imply. Alpaca's total return for
  SPY therefore misses about 0.96% over 2016-2026, roughly -0.09%/yr.
  - SPY otherwise pays every quarter in both sources.
  - The amounts are confirmed only by Yahoo. They are UNVERIFIED against State Street's distribution history,
    which I could not retrieve.

### 3.4 H3: adjusted-close return on ex-dividend dates

| Provider (sample) | Events | Primary `(C_t+D_t)/C_{t-1}-1` within 1 bp | CRSP `C_t/(C_{t-1}-D_t)` within `tau_t` | CRSP within 1 bp | CRSP max bp |
| --- | --- | --- | --- | --- | --- |
| Yahoo, full history, 6 tickers | 796 | 690 (86.7%); max 8.5 bp (VFINX) | 796 (100%) | 796 (100%) | 0.32 (KO) |
| Yahoo, 2016 onward | 259 | 231 (89.2%) | 259 (100%) | 259 (100%) | 0.01 |
| Alpaca `all`, 2016 onward, 5 tickers | 214 | 147 (68.7%); max 7.0 bp (NVDA) | 190 (88.8%) | 162 (75.7%) | 6.2 (NVDA) |

Per ticker (primary within 1 bp):

- Yahoo full history: SPY 131/136, AAPL 86/93, NVDA 56/56, KO 208/259, AVGO 46/64, VFINX 163/188.
- Alpaca: SPY 39/41, AAPL 39/44, NVDA 24/43, KO 26/43, AVGO 19/43.

Which convention each provider uses (VERIFIED, `adj_method.py`): the dividend factor implied by
`adjustment=all / raw` was measured on each event as a 5-day median before and after, to dampen rounding. Its
median distance from the CRSP factor `1 - D/C_{t-1}` is 0.06-0.43 bp. The alternatives
`1/(1 + D/C_{t-1})` and `C_t/(C_t + D)` fit worse. So both providers use the CRSP convention. Alpaca's failures
against `tau_t` are the cent rounding of 3.2, not a wrong method.

### 3.5 Closing-price definition

Recent window, 20 days, 2026-10-19 to 2026-11-13. Compared: Yahoo `Close`, Alpaca raw bar close, and the
primary-exchange closing auction from Alpaca's SIP auctions endpoint.

| Ticker | Yahoo = auction | Alpaca bar = auction | Auction `6` = official close `M` | Yahoo = Alpaca |
| --- | --- | --- | --- | --- |
| SPY | 20/20 | 20/20 | 20/20 | 20/20 |
| AAPL | 19/20 (2026-10-23: Yahoo 347.73, auction 347.725, a sub-penny auction price rounded) | 20/20 | 20/20 | 19/20 |
| NVDA | 20/20 | 20/20 | 20/20 | 20/20 |
| KO | 20/20 | 20/20 | 20/20 | 20/20 |
| AVGO | 20/20 | 20/20 | 20/20 | 20/20 |

All 34 auction days from 2026-10-01 give the same result.

History 2016-2022 (share of days on which the close equals the primary-exchange closing auction to the cent):

| Year | SPY: Yahoo | SPY: Alpaca bar | SPY median \|Alpaca - auction\| | AAPL: Yahoo | AAPL: Alpaca bar |
| --- | --- | --- | --- | --- | --- |
| 2016 | 38.5% | 10.7% | 3.0 c | 100% | 99.2% |
| 2017 | 100% | 10.4% | 3.0 c | 99.6% | 97.6% |
| 2018 | 100% | 8.8% | 4.0 c | 100% | 96.8% |
| 2019 | 99.6% | 9.1% | 4.0 c | 100% | 99.2% |
| 2020 | 100% | 5.5% | 6.0 c | 98.8% | 93.3% |
| 2021 | 100% | 70.6% | 0.0 c | 99.6% | 98.0% |
| 2022 | 100% | 96.8% | 0.0 c | 100% | 99.2% |

- The last SPY day on which Alpaca's close differs from Yahoo's by 0.5 cents or more is 2022-07-28. There are
  none from 2023 on.
- Spot checks:
  - SPY 2020-03-12: Arca auction 248.11, Yahoo 248.11, Alpaca 255.24.
  - SPY 2020-03-13: Arca auction 269.32, Yahoo 269.32, Alpaca 270.20, which equals the Nasdaq (`T`) closing
    print that day.
  - KO 2020-03-09: NYSE auction 51.86, Yahoo 51.86, Alpaca 52.23.
  - AAPL 2022-02-24: Nasdaq auction 162.74, Yahoo 162.74, Alpaca 162.51.
- Alpaca's FAQ lists condition `6` "Market Center Closing Trade" as updating a bar's open/close for *any* market
  center. That is consistent with Alpaca's SPY close sometimes being another exchange's later closing print.
  Why the behaviour stopped during 2021-2022 is UNVERIFIED (reprocessing on Alpaca's side, or a change in
  exchange reporting).
- Timing signature (tracking difference against `^SP500TR`, 2020-2022): sd 20.7 bp/day for Alpaca SPY against
  8.0 for Yahoo SPY and 1.1 for VFINX. The lag-1 autocorrelation is about -0.6 for both SPY series.
- What this does and does not verify: the auction prints come from Alpaca's own SIP feed, not from the exchanges'
  websites. That Yahoo equals the official close is VERIFIED against the SIP closing-auction record, not
  against an exchange publication (UNVERIFIED).
- Yahoo SPY in 2016 matches the Arca auction on only 38.5% of days, and some exchange's closing print on 197 of
  252 days. Its 2016 close definition is mixed (UNVERIFIED why).

---

## 4. Regression impact (FF5, daily, HAC per M0.5/D2; VERIFIED, `regress.py`)

Columns:

- Rvol: residual volatility, %/yr, for the sub-periods pre-2010 and 2010 onward. "-" means no data.
- rho: residual lag-1 autocorrelation, full period, with robust z, then the pre-2010 and 2010-onward parts.
- VR5: 5-day variance ratio of residuals (A3, not pre-registered).
- G1: the validation's gate (rho < -0.2 and robust z < -4).

| Ticker, period | Source | n | R2 | Alpha %/yr (z) | Mkt, SMB, HML, RMW, CMA | Rvol pre-2010 / 2010+ | rho (z) / pre / post | VR5 | G1 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| SPY, 1993-02-01..2026-09-30 | Yahoo SPY | 8,474 | 0.9673 | -0.58 (-2.24) | 1.009, -0.148, 0.007, 0.088, 0.061 | 4.53 / 1.35 | -0.404 (-13.1) / -0.420 / -0.225 | 0.30 | fires |
| same dates | `^SP500TR` (ref) | 8,474 | 0.9955 | -0.53 (-2.79) | 1.012, -0.138, 0.026, 0.084, 0.053 | 1.43 / 0.99 | -0.063 (-3.0) / -0.081 / -0.023 | 0.83 | - |
| same dates | VFINX (ref) | 8,474 | 0.9948 | -0.64 (-3.35) | 1.011, -0.138, 0.026, 0.083, 0.053 | 1.55 / 1.04 | -0.114 (-3.4) / -0.131 / -0.075 | 0.81 | - |
| SPY, 2016-01-05..2026-09-30 | Yahoo SPY | 2,700 | 0.9946 | -0.20 (-0.66) | 0.985, -0.102, 0.018, 0.047, 0.034 | - / 1.30 | -0.239 (-3.5) | 0.63 | - |
| same dates | Alpaca SPY `all` | 2,700 | 0.9870 | +0.02 (+0.06) | 0.963, -0.078, 0.017, 0.039, 0.015 | - / 1.99 | -0.386 (-2.1) | 0.33 | - |
| same dates | Alpaca SPY rebuilt | 2,700 | 0.9870 | +0.02 (+0.06) | 0.963, -0.078, 0.017, 0.039, 0.015 | - / 1.99 | -0.386 (-2.1) | 0.33 | - |
| same dates | `^SP500TR` (ref) | 2,700 | 0.9971 | -0.19 (-0.67) | 0.993, -0.103, 0.022, 0.050, 0.028 | - / 0.96 | -0.035 (-0.9) | 0.93 | - |
| same dates | VFINX (ref) | 2,700 | 0.9965 | -0.33 (-1.17) | 0.993, -0.104, 0.022, 0.050, 0.029 | - / 1.05 | -0.120 (-1.2) | 0.71 | - |
| AAPL, 1980-12-15..2026-09-30 | Yahoo | 11,541 | 0.2771 | +15.83 (+2.89) | 1.163, -0.051, -0.463, 0.135, -0.519 | 43.88 / 20.63 | +0.042 (+2.8) / +0.040 / +0.063 | 1.04 | - |
| AAPL, 2016-01-05..2026-09-30 | Yahoo | 2,700 | 0.5996 | +8.84 (+1.49) | 1.231, -0.135, -0.533, 0.529, 0.411 | - / 18.28 | +0.075 (+3.0) | 1.18 | - |
| same dates | Alpaca `all` | 2,700 | 0.5991 | +8.85 (+1.49) | 1.230, -0.135, -0.533, 0.529, 0.410 | - / 18.29 | +0.075 (+3.0) | 1.18 | - |
| same dates | Alpaca rebuilt | 2,700 | 0.5992 | +8.84 (+1.49) | 1.230, -0.135, -0.533, 0.528, 0.411 | - / 18.29 | +0.075 (+3.0) | 1.18 | - |
| NVDA, 1999-01-25..2026-09-30 | Yahoo | 6,964 | 0.3579 | +38.70 (+4.22) | 1.485, 0.154, -0.729, -0.847, -0.315 | 62.84 / 33.64 | -0.005 (-0.2) / -0.003 / -0.011 | 1.00 | - |
| NVDA, 2016-01-05..2026-09-30 | Yahoo | 2,700 | 0.5220 | +39.30 (+3.83) | 1.694, -0.108, -0.878, 0.108, -0.326 | - / 33.99 | -0.043 (-1.7) | 0.90 | - |
| same dates | Alpaca `all` | 2,700 | 0.5218 | +39.30 (+3.83) | 1.694, -0.109, -0.876, 0.107, -0.327 | - / 34.00 | -0.043 (-1.7) | 0.90 | - |
| same dates | Alpaca rebuilt | 2,700 | 0.5221 | +39.29 (+3.83) | 1.695, -0.108, -0.878, 0.108, -0.326 | - / 34.00 | -0.043 (-1.7) | 0.90 | - |
| KO, P-2016 (extra) | Yahoo / Alpaca `all` / rebuilt | 2,700 | 0.3428 / 0.3407 / 0.3408 | +0.24 / +0.28 / +0.28 | Mkt 0.579 / 0.576 / 0.577 | - / 14.73 (all three) | -0.005 | 0.93 | - |
| AVGO, P-2016 (extra) | Yahoo / Alpaca `all` / rebuilt | 2,700 | 0.4558 / 0.4561 / 0.4560 | +18.81 / +18.67 / +18.67 | Mkt 1.405 (all three) | - / 29.03 | +0.040 | 0.95 | - |
| SPY 2016-2020 (extra) | Yahoo / Alpaca rebuilt / `^SP500TR` | 1,258 | 0.9958 / 0.9829 / 0.9975 | -0.62 / -0.30 / -0.76 | Mkt 0.974 / 0.934 / 0.994 | - / 1.22 / 2.40 / 0.96 | -0.192 / -0.372 / -0.082 | 0.66 / 0.32 / 0.90 | - |
| SPY 2023-01-03..2026-09-30 (extra) | Yahoo = Alpaca rebuilt / `^SP500TR` | 939 | 0.9930 / 0.9979 | -0.30 / -0.04 | Mkt 0.999 / 0.984 | - / 1.25 / 0.67 | -0.352 (-2.4) / -0.004 | 0.31 / 0.90 | - |

Reading:

- **For single stocks the source does not matter after 2016.** For AAPL and NVDA, Yahoo and Alpaca agree on R2
  to 0.0005, on every beta to 0.002 and on alpha to 0.01%/yr. Alpaca's rounding noise is invisible at 18-34%
  residual volatility. The one material difference is AVGO: Yahoo's doubled dividends add 0.14%/yr of alpha.
- **For SPY the close definition matters a lot.** Over 2016-2026, Alpaca's non-official closes have these
  effects compared with Yahoo:
  - R2 falls from 0.9946 to 0.9870;
  - residual volatility rises from 1.30% to 1.99%/yr, and in 2016-2020 from 1.22% to 2.40%;
  - the market beta falls by 0.022 (0.04 in 2016-2020). A close recorded after 4 pm moves part of the next day's
    market move into today's return, which attenuates the same-day beta;
  - alpha moves by +0.22%/yr, mostly as the mirror image of the beta change.
- **SPY keeps a negative residual autocorrelation even with official closes.** From 2023 both vendors give
  identical SPY returns, equal to the official closing auction. The residual autocorrelation is still -0.35
  and VR5 is 0.31, against -0.004 and 0.90 for the index. The remaining noise is the ETF's closing price relative
  to the 4 pm index value (premium/discount and auction noise; rank 2 in the validation). So the -0.4 SPY
  pattern is partly a property of the ETF, not only of a vendor. A gate caveat should not blame "the data
  vendor" alone.
- **G1 misses a series it should catch.** It does not fire for Alpaca SPY over P-2016 (rho -0.386, robust
  z -2.1). The heteroskedasticity-robust z is swamped by March 2020: residuals of 2-3% that reverse. VR5 0.33
  and the rank autocorrelation (-0.13, z -6.6) both flag the series. Exploratory, in-sample: the rule
  "rho < -0.2 and VR5 < 0.6" fires for Yahoo SPY over P-LONG, Alpaca SPY over P-2016 and 2016-2020, and SPY
  from 2023 (VR5 0.30-0.33). It does not fire for the references or the stocks (VR5 0.81-1.18). The one
  borderline case is Yahoo SPY over P-2016 (rho -0.239, VR5 0.63), which neither rule flags.

---

## 5. Hypothesis verdicts

| Test | Hypothesis | Status | Result | Verdict |
| --- | --- | --- | --- | --- |
| T-20261118-101 | H1, Tiingo SPY clean before 2010 | abandoned (A1) | not run | **Not tested.** No free source available here covers SPY before 2016 except Yahoo. |
| T-20261118-102 | H2, Alpaca SIP vs Yahoo <= 1 bp on >= 99% of days | run | SPY 68.2%, AAPL 83.8%, KO 72.0% (`adjustment=all`, n 2,734 each) | **Rejected.** Causes (all explained): Alpaca's cent-rounded adjusted prices; Alpaca's SPY close was not the official close until mid-2022; 2 SPY dividends missing at Alpaca. Not pre-registered: rebuilt from raw closes, KO passes (99.78%), AAPL 97.4%, SPY 68.6%. From 2023 all three agree on 100% of days. |
| T-20261118-103 | H3, ex-dividend adjusted return = `(C+D)/C_prev - 1` within 1 bp | run | Yahoo 86.7% of 796 events; Alpaca 68.7% of 214 | **Rejected for both providers on the primary formula**, as predicted in 1.2: neither provider uses that convention. Secondary rule: Yahoo matches the CRSP convention on 100% of events (max 0.32 bp). Alpaca matches it within `tau_t` on 88.8%; the misses come from cent rounding, and the method itself is CRSP (median 0.06-0.43 bp). H3 is internal consistency only. It found neither Yahoo's wrong AVGO amounts nor Alpaca's missing SPY events. |
| T-20261118-104 | H4, Tiingo SPY starts by 1993-02-01 | abandoned (A1) | not run | **Not tested.** |
| T-20261118-105 | Regression impact | run | section 4 | Descriptive. |
| T-20261118-106 | Closing-price definition | run | section 3.5 | Descriptive. All three closes equal the primary closing auction on 20/20 recent days, except one sub-penny case at Yahoo. |

No p-values are claimed, so no multiple-testing correction applies (1.4). The alpha z values in section 4 are
descriptive single tests (M0.6).

---

## 6. Terms, rate limits, authentication and delisted coverage (facts as written; not legal advice)

How each page was read:

- Tiingo Terms of Use, Alpaca's Terms and Conditions PDF, Alpaca's docs and FAQ, the Yahoo terms and the yfinance
  README were downloaded and searched as raw text (VERIFIED).
- Tiingo's pricing, end-of-day, connecting and symbology pages are rendered by script. They were read through
  a page-to-text tool, and the quotes below are the text it returned (VERIFIED with that caveat).

### 6.1 Tiingo (free "Starter" plan)

- **Licence**, <https://www.tiingo.com/about/pricing>: "Internal Use Only". "Internal use means you may only use
  the data for your own personal use and you may not display or share the data with another person or
  organization."
- **Terms**, <https://www.tiingo.com/tos/>, "Last Updated Date: November 5th, 2026":
  - §1.6(a): "If you use a Starter Plan or any free or paid trial plan … you may not write, save, archive, back
    up, or otherwise retain Tiingo Data in any persistent or durable storage." It goes on: "This prohibition
    applies to … local devices, databases, object stores, file systems, logs …". It also says: "The same limits
    apply to Derived Products".
  - §1.6(c) lists as prohibited, among others:
    - "using Tiingo end-of-day data to validate another end-of-day dataset";
    - "a single-security performance series, equity curve, or price path that is rebased or indexed to 100";
    - "tables, files, … charts … that display, deliver, or permit extraction of Tiingo Data or a substantially
      equivalent substitute".
  - §1.6(c) lists as possibly permitted, only if not a substitute and not reconstructable: "aggregate or
    statistical results of a backtest, such as … alpha, beta". It then adds: "A Starter Plan or Trial Plan does
    not permit persistent storage of Derived Products". It says exceptions are given only to "a Start-up,
    Enterprise, or Institutional account … Those plans start at $250 per month."
  - §7.3: "All data via the API is for internal consumption only." Permitted redistribution must carry "Data
    sourced by Tiingo" with a link.
  - §1.7(b) allows giving Tiingo Data to an AI model in a prompt or tool call. The model must be run by an
    "Approved Inference Provider", which requires a zero-data-retention or no-training setting that the user
    has confirmed.
- **Consequence for factordesk (my reading of the quoted text, not legal advice).** On the free plan, a tool that
  caches prices, writes a report file or draws a price chart from Tiingo data is outside these terms. Using
  Tiingo as a cross-check of Yahoo is listed as prohibited without a written exception.
- **Rate limits**, pricing page: 50 requests per hour, 1,000 per day, 500 unique symbols per month, 1 GB per
  month. End-of-day history on Starter: "30+ Years". The stated limits are **VERIFIED**.
- **Authentication**, <https://www.tiingo.com/documentation/general/connecting>: "You can pass the token
  directly in the request URL by passing the token parameter" or "pass the token in the request headers … "Token
  " + your API token to the "Authorization" header." Factordesk should use the header only.
- **Endpoints and fields**, <https://www.tiingo.com/documentation/end-of-day>:
  - endpoints `https://api.tiingo.com/tiingo/daily/<ticker>/prices` and `https://api.tiingo.com/tiingo/daily/<ticker>`;
  - `divCash`: "The dividend paid out on "date" (note that "date" will be the "exDate" for the dividend)";
  - `splitFactor`: "The factor used to adjust prices when a company splits, reverse splits, or pays a distribution";
  - `startDate`: "The earliest date we have price data available for the asset";
  - "The adjustment methodology follows the standard method set forth by" CRSP;
  - "Mutual Fund NAVs are available after 12 AM EST. The fields "open", "high", "low", "close" will contain the
    NAV value".
- **Delisted tickers**, <https://www.tiingo.com/documentation/appendix/symbology>: "Tiingo supports delisted data
  for tickers that have not yet been recycled."
- SPY's actual Tiingo start date (H4) is UNVERIFIED.

### 6.2 Alpaca (free "Basic" market-data plan)

- **Plan**, <https://docs.alpaca.markets/docs/about-market-data-api>: "Basic … Free … Securities coverage US
  Stocks & ETFs … Historical data timeframe Since 2016 … Historical data limitation* latest 15 minutes …
  Historical API calls 200 / min". Algo Trader Plus is "$99 / month" with "10,000 / min".
- **Authentication**: headers `APCA-API-KEY-ID` and `APCA-API-SECRET-KEY`.
- **Bars parameters**, <https://docs.alpaca.markets/reference/stockbars>:
  - `adjustment`: "raw : no adjustments", "split : adjust price and volume for forward and reverse stock splits",
    "dividend : adjust price for cash dividends", "spin-off : adjust price for spin-offs", "all : apply split,
    dividend, and spin-off adjustments", "Default: raw";
  - `limit`: "The limit applies to the total number of data points, not per symbol!";
  - `feed`: "sip : all US exchanges", "iex : Investors EXchange", "Defaults to sip";
  - `asof` does symbol mapping across renames ("FB was renamed to META in 2022-06-09 …").
- **FAQ**, <https://docs.alpaca.markets/us/docs/market-data-faq.md>:
  - "For historical queries, the `end` parameter must be at least 15 minutes old to query SIP data without a
    subscription";
  - "Minute and daily bars are aggregated from trades. The (SIP) timestamp of the trade is truncated … to the
    day (in New York) for daily bars";
  - condition `6` "Market Center Closing Trade" updates open/close, and `M` "Market Center Official Close" does
    not.
- **Corporate actions**, <https://docs.alpaca.markets/us/reference/corporateactions-1.md>: "Currently Alpaca has
  no guarantees on the creation time of corporate actions."
- **Terms**, <https://files.alpaca.markets/disclosures/alpaca_terms_and_conditions.pdf> (no date on the PDF):
  - "you agree to use the Services and Content solely for your own personal and non-commercial purposes";
  - "making the Services and Content available to others through your own application (a "User Application"),
    you shall provide Alpaca with 30 days advance written notice";
  - "No part of the Service or Content may be copied, reproduced, republished, uploaded, posted, publicly
    displayed … for publication or distribution or for any commercial" purpose.
- **Redistribution**, <https://alpaca.markets/support/redistribute-alpaca-api> (November 2022): "Unfortunately,
  you cannot redistribute Alpaca API data."
- **Delisted symbols and mutual funds**:
  - VFINX returned no bars (VERIFIED). Mutual funds are not in the stated coverage.
  - Delisted coverage: no official statement found (UNVERIFIED). A forum reply of 2025-12-18 without a visible
    staff badge says "we do not have an endpoint for historical assets"
    (<https://forum.alpaca.markets/t/delisted-tickers/18227>, read by a delegated web search, not re-read).
- **This study's use of Alpaca data**: the owner's research under their own key. Only aggregate statistics
  appear in this document.

### 6.3 Yahoo Finance through yfinance

- **yfinance README** (<https://raw.githubusercontent.com/ranaroussi/yfinance/main/README.md>):
  - "yfinance is **not** affiliated, endorsed, or vetted by Yahoo, Inc. It's an open-source tool that uses
    Yahoo's publicly available APIs, and is intended for research and educational purposes";
  - "Remember - the Yahoo! finance API is intended for personal use only."
- **Yahoo Terms of Service** (<https://legal.yahoo.com/us/en/yahoo/terms/otos/index.html>):
  - "you may not access or reuse the Services, or any portion thereof, for any commercial purpose";
  - you may not "access or collect data, or attempt to access or collect data, from our Services using any
    automated means … for any purpose without our express, prior permission".
- Yahoo publishes no API, no rate limit and no statement on delisted tickers (UNVERIFIED that none exists; none
  found).

---

## 7. Recommendation

**Applying the pre-registered rules (1.3).**

| Source | 1 History | 2 Adjustment | 3 SPY cleanliness | 4 Terms | 5 Rate | Outcome by the rules |
| --- | --- | --- | --- | --- | --- | --- |
| Yahoo | pass (1993 / 1980 / 1999) | pass by CRSP rule; but a verified wrong dividend amount (AVGO 2018) | baseline; cleaner than Alpaca over 2016-2026 | **fails or ambiguous**: no automated access without permission, personal use | no published limit | Default only "if no other source is clearly permitted, and the report says so". That condition holds, so Yahoo stays the default **with this disclosure**. |
| Alpaca | **fail** (2016 onward) | method is CRSP, but adjusted prices are cent-rounded and 2 SPY dividends are missing | worse than Yahoo for SPY 2016-2022 | personal, non-commercial use; 30-day notice for a "User Application"; no redistribution | 200/min | Not eligible as the default. **Cross-check** only where its returns meet the 99% rule: from 2023 for SPY, AAPL and KO; KO and AVGO (rebuilt) since 2016. Every disagreement found was explained, so it is not excluded. |
| Tiingo (free) | not measured | not measured | not measured | **fails**: no persistent storage of data or derived products; validation use and price charts prohibited | 50/hour | **Not at all** on the free plan. A paid plan still lists validation use and rebased price paths as prohibited without a written exception. |

**Recommended order:** Yahoo first, then Alpaca (rebuilt from raw closes, 2016 onward only), then a clear
failure. Tiingo has no place in the order unless the owner obtains a written licence that covers this use.

**What to build in the data layer (one sentence each, for the code owners):**

1. Each `PriceProvider` (`YahooProvider`, `AlpacaProvider`) returns the same `PriceHistory`:
   - raw or split-adjusted close, dividends as paid, split ratios, and a `close_definition` note;
   - the provider name, request parameters, `fetched_at` and the SHA-256 of the frame.
2. Total returns are computed **in factordesk**, never taken from the provider's adjusted close, with the CRSP
   form `r_t = C_t s_t / (C_{t-1} - D_t s_t) - 1`. This is exactly reproducible (removes validation F8), and it
   avoids Alpaca's cent rounding (up to 8.9 bp a day).
3. `AlpacaProvider` uses:
   - `/v2/stocks/bars` with `timeframe=1Day&adjustment=raw&feed=sip&limit=10000`, `end` at least 15 minutes old
     (use the previous session date), and `next_page_token` paging;
   - `/v1/corporate-actions` (`cash_dividend`, `forward_split`, `reverse_split`, and `spin_off` when that is
     supported);
   - the `X-RateLimit-Remaining` header to stay under 200 per minute.

   It must never use `adjustment=all`.
4. A **cross-check** runs on the 2016-onward overlap when Alpaca keys exist. It never substitutes data
   silently. It compares:
   - dividend events, as paid: date set, and amount mismatches above max(0.0005, 0.1%) become an audit `error`;
   - splits (date and ratio);
   - close levels on non-event days: a year with more than 1% of days differing by a cent or more becomes a
     `close_definition` warning.
   For a disputed close, the primary-exchange closing auction (`/v2/stocks/auctions`, condition `6`, listing
   exchange) can settle which close is official.
5. The **data-quality gate** keeps G1 from the validation and adds a variance-ratio rule. It fires when residual
   lag-1 autocorrelation is below -0.2 **and** the 5-day variance ratio of residuals is below 0.6.
   - Reason: the robust z misses fat-tailed episodes (Alpaca SPY 2016-2026: rho -0.386, z -2.1).
   - This threshold is **calibrated in-sample on 8 series**, so it must be re-calibrated on a panel before
     release.
   - The caveat text should say "closing prices are not synchronous with the 4 pm factor data (an ETF's closing
     price can differ from its index value, and some vendors' closes are late)", and should not blame the
     vendor alone. SPY with official closes still fires from 2023.
6. The README and docs should state the terms facts of section 6 next to each provider. The owner may wish to
   check Alpaca's "User Application" notice clause and Yahoo's automated-access clause with counsel.

**What would answer H1 and H4.** Either of these would do:

- a source with pre-2010 SPY closes, licensed for this use, such as a CRSP or exchange-licensed file, or a Tiingo
  plan with written permission;
- the closing-auction history before 2016, which Alpaca does not offer.

---

## 8. Limits and UNVERIFIED items

- H1 and H4 were not tested (A1). Whether Tiingo's pre-2010 SPY is clean, and when its SPY history starts, are
  both UNVERIFIED.
- The auction prices used as "official close" come from Alpaca's SIP feed. They were not checked against
  exchange publications (UNVERIFIED that the SIP record equals the exchanges' official close lists).
- Why Alpaca's SPY close moved onto the official auction during 2021-2022 is UNVERIFIED. So is why Yahoo's 2016
  SPY close matches the Arca auction on only 38.5% of days.
- SPY dividends ex 2016-03-18 and 2018-06-15 are confirmed by Yahoo only, not by State Street (UNVERIFIED
  amounts). The March 2018 AVGO amount of $1.75 is UNVERIFIED from a primary page (June 2018 is VERIFIED).
- Gate thresholds (VR5 < 0.6) are in-sample on 8 series.
- Delisted coverage for Alpaca and Yahoo is UNVERIFIED. All tickers here exist today (survivorship, M1.5).
- Ticker sample: 5 stocks and ETFs plus 2 references. Results about rounding and close definitions may differ
  for low-priced or less liquid stocks.
- Licence facts are quotations, not an interpretation of rights. Terms can change; Tiingo's changed on
  2026-11-05.
- Yahoo `Adj Close` differs slightly between downloads (validation F8). These numbers come from the 11:22Z
  download.

---

## 9. Reproducibility

Scripts and caches are in the session scratchpad, folder `scratchpad\sources\`, with subfolders `scripts`,
`yahoo`, `alpaca`, `french`, `docs` and `out`. The scratchpad is throwaway and not part of the repo. Run them
from the `sources` folder as `uv run --no-project --python 3.12 --with pandas==3.1.1 --with statsmodels==0.15.0
python -I scripts/<name>.py .` (the fetch scripts take their arguments as shown in each file). No API key
appears in any script, cache, output or this document. `check_no_secrets.py` scanned every file and found 0
matches.

| Script | Purpose |
| --- | --- |
| `fetch_french.py` | French zip, vintage metadata |
| `fetch_yahoo.py` | yfinance downloads (needs `--with yfinance==1.8.0`) |
| `fetch_alpaca.py`, `fetch_alpaca_lib.py`, `fetch_alpaca_auctions_hist.py`, `fetch_alpaca_ko2020.py` | Alpaca bars, corporate actions and auctions. Arguments: path of the `.env` file and output folder. Keys go in headers only and are redacted from errors. |
| `common.py` | Loaders, M2 alignment, HAC lag rule |
| `compare.py` | Sections 3.1-3.5 (recent window) |
| `spy_close.py`, `auction_hist.py`, `auction_peek.py`, `spot_dates.py` | Section 3.5 history and spot checks |
| `adj_method.py` | Adjustment convention and rebuilt returns (3.2-3.4) |
| `regress.py` | Section 4 |
| `html2text.py`, `pdf2text.py` | Turning terms pages into text for quoting |
| `check_no_secrets.py` | Scans every file for key values |
