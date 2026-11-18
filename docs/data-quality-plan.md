# Data-quality plan: two-source triangulation

Status: plan, 2026-11-18. No code. It follows `docs/research-protocol.md` (binding for every new statistic and
threshold) and builds on `docs/data-source-comparison.md` (cited as "study §n") and
`docs/validation/spy-slice-validation.md` (cited as "validation Fn").
Every claim is marked **VERIFIED** (a computation that was run, or a quoted line with its source) or
**UNVERIFIED**.

New computations for this plan use only the study's cached files (no API was called; Tiingo was not touched).
Scripts and outputs: session scratchpad, folder `scratchpad\dqplan\` next to the study's `scratchpad\sources\`
(`dq_bands.py`, `dq_sens.py`, `dq_divs.py`, `gate_sim.py`, each with a `.txt` output). They are throwaway and
not part of the repo. Run as in study §9. They are registry lines T-20261118-201 to -204 (section 8).

---

## 0. The design in three sentences

1. **The headline series is always one source, rebuilt by factordesk from raw closes and dividends.** A second
   source never changes the headline. It produces a per-day agreement status, flags and two sensitivity reruns.
   There is no averaging. With two sources, an average of a correct and a wrong close is still wrong, and it
   hides which vendor was wrong.
2. **There is one tolerance band, and it is the existing audit tolerance** `tau_t = 1e-4 + 0.01 / C_{t-1}` (M1.4),
   plus a two-day rule for disputed close levels. No new threshold is fitted.
3. **The residual quality gate stays G1 (D22) until a registered, out-of-sample evaluation says otherwise.** The
   variance-ratio proposal is a candidate under H-DQ1. It is not used in reports in the meantime.

---

## 1. Goals, non-goals and the licensing boundary

**Goals:** detect and disclose the price, dividend and split defects actually observed; measure how much each
moves alpha, the betas and R2; make every report traceable to source, download time and vendor revisions; stay
inside each vendor's terms.

**Non-goals:** silent repair (rows are never dropped, substituted or filled in the headline, CODING_STANDARDS
§3); averaging vendors; a second source before 2016 (Alpaca SIP starts 2016-01-04, VERIFIED, study §3.1); paid
data; Tiingo on the free plan; legal opinions; vendor data in the repository.

**What each source's terms allow (quotes from study §6, VERIFIED as quoted there; this is not legal advice).**

| Source | What the terms say | Consequence for an open-source tool run locally with the user's own key |
| --- | --- | --- |
| Yahoo via yfinance | yfinance README: "the Yahoo! finance API is intended for personal use only". Yahoo ToS: no access "using any automated means … without our express, prior permission"; no "commercial purpose". | Default source, **with disclosure**. Study §7 kept it as default only because "no other source is clearly permitted, and the report says so". Personal, local use only. |
| Alpaca (free Basic) | "solely for your own personal and non-commercial purposes". "making the Services and Content available to others through your own application (a "User Application"), you shall provide Alpaca with 30 days advance written notice". "you cannot redistribute Alpaca API data". | Optional second source, **opt-in, off by default** (README today: "Alpaca is not used in v1"). Reports that contain Alpaca-derived numbers are personal and must not be published. Whether distributing factordesk counts as a "User Application" is an **owner decision** (section 9). |
| Tiingo (free Starter) | §1.6(a): no "persistent or durable storage" of Tiingo Data, and "The same limits apply to Derived Products". §1.6(c) prohibits "using Tiingo end-of-day data to validate another end-of-day dataset". | **Excluded.** Triangulation is exactly the prohibited use. The ROADMAP rows "Consensus returns from Yahoo, Tiingo and Alpaca" and "Alpaca and Tiingo adapters" should drop Tiingo (owner edit; this plan does not touch ROADMAP). |

**No data in the repo.** `.gitignore` already excludes `/data/`, `*.parquet` and `/docs/samples/spy_report.*`
(VERIFIED, read 2026-11-18). Test fixtures for this plan are **synthetic**: they copy the *shape* of an observed
defect (a dividend stored at twice the paid amount), never vendor rows. Facts quoted from public filings (an SEC
8-K dividend amount) are not vendor data and may appear in docs with their URL.

**Disclosure required in the README** (a "Data sources and terms" section, written by the owner). It must contain:

1. For each provider: a one-line quote of its terms and a link (the rows above). Also the yfinance line "not
   affiliated, endorsed, or vetted by Yahoo, Inc."
2. That the user fetches data with their own access, is responsible for following the vendor's terms, and that
   factordesk caches data only on the user's machine.
3. That reports built from vendor data are for personal use and are not to be redistributed. This applies
   especially to reports that contain Alpaca data.
4. That Tiingo is not supported on the free plan, and why.
5. That the repository holds no price data, and that the bundled sample report is synthetic.

Every report footer repeats item 3 and names the sources used. Whether local caching of Alpaca data is within
its terms is UNVERIFIED; the terms quoted above do not address it.

**Config fix (VERIFIED).** `backend/factordesk/config.py` line 12 sets `alpaca_data_feed: str = "iex"`. The study
used `feed=sip` ("sip : all US exchanges"; "iex : Investors EXchange"). An IEX-only daily bar closes on the last
IEX trade, not on the consolidated official close. That consequence is inferred from the documentation
(UNVERIFIED by data). The default must become `sip`, and the provider must refuse `iex` for daily total returns.

---

## 2. Defect taxonomy

The default action for every defect: **flag, report, measure the sensitivity, never silently fix.** "Rule" names
the detector. Test ids refer to the oracle (TQ) or to existing tests (T, TD).

| ID | Defect | Evidence | Detection | Report | Analysis action | Test |
| --- | --- | --- | --- | --- | --- | --- |
| DQ1 | Late or non-official close | VERIFIED: Alpaca SPY matched the Arca auction on 5.5-10.7% of days in 2016-2020 (study §3.5). Yahoo SPY before about 2009 carries post-4 pm moves (validation §3.3). | Two sources: a close-level dispute (≥ 1 cent, as traded) flags day t and day t+1 (section 4.2). One source: the gate (section 5). Optional tie-break: the primary-exchange closing auction (section 3.3). | `close_level` disagreement days, by year; gate caveat | Headline unchanged; S-EX and S-SUB reruns (4.4) | TQ15, TQ16, TQ13 |
| DQ2 | Adjusted prices rounded to cents | VERIFIED: Alpaca `adjustment=all` has at most 2 decimals; non-event errors up to 8.9 bp a day (study §3.2) | Prevention: adjusted prices are never ingested; total returns are rebuilt (TQ03) | none needed | - | TQ01, TQ03 |
| DQ3 | Missing dividend | VERIFIED: Alpaca has no SPY dividends ex 2016-03-18 and 2018-06-15; effect 51.3 and 44.7 bp on the ex-date (dq_divs) | Event reconciliation (section 3) | Corporate-action table, `missing_in_<source>` | Material event: the day is flagged; S-SUB | TQ10 |
| DQ4 | Wrong (doubled) dividend amount | VERIFIED: Yahoo AVGO 2018-03-21 and 2018-06-19 store 3.50 against 1.75 paid. The June amount is confirmed by Broadcom's 8-K (study §3.3). Effect 72.2 and 66.2 bp; +0.14%/yr of alpha. Yahoo's own audit (M1.4 A6) cannot see it. | Event reconciliation | `amount_mismatch`, material | As DQ3; primary-source confirmation (3.3) | TQ10, TQ11 |
| DQ5 | Dividend rounding | VERIFIED: Yahoo SPY amounts have 3 decimals; 1 of 43 events differs by more than max(0.0005, 0.1%): 2021-12-17, 1.633 vs 1.636431, effect 0.07 bp (dq_divs) | Event reconciliation, materiality test | Shown as `immaterial` | none | TQ11 |
| DQ6 | Split error (wrong date or ratio, or not applied) | No real case: both sources agree on all 4 splits 2016-2026 (VERIFIED, study §3.3). Synthetic: an unapplied 4:1 split gives R2 0.134 (validation F4). | A5/A5b (M1.4); cross-source date and ratio check; check against the as-traded price jump (3.2) | `split_mismatch` | Flag; S-SUB | T22-T30, TQ12 |
| DQ7 | Pence and currency units | VERIFIED: VOD.L quotes in `GBp` (methodology-datasets D7.2). Dividend units for GBp tickers are UNVERIFIED (D9.2). | `currency_unit_switch`, `dividend_unit_mismatch` (D9.2) | audit finding | Flag only | TD28 |
| DQ8 | Stale prints | No real case observed. The rule exists (M1.4 A3). | A3 run of identical closes; across sources, one stale and the other moving shows up as a return disagreement | audit finding + disagreement days | Flag | T29 |
| DQ9 | Holiday rows and calendar gaps | VERIFIED: regional factor files have a row on every weekday, including 25 Dec (datasets.md, C2). Yahoo FX has a 1 January row. Both sources have 0 missing US trading days 2016-2026 (study §3.1). | M2 / D10 alignment (`multi_day_return`, `no_factor_row`); date-set comparison between sources | `calendar` disagreement | Excluded by M2 (already reported) | T31, TQ15 |
| DQ10 | FX bad prints | VERIFIED: EURUSD +17.31% then -13.35% (2008-12-08/09) (D9.3) | `fx_spike` (D9.3) | audit error | Flag only | TD31 |
| DQ11 | Vendor revisions between downloads | VERIFIED: Yahoo `Adj Close` differs between two same-day downloads by up to 1.8e-4 on 7,108 rows, while `Close` and `Dividends` were identical (validation F8). Alpaca: "no guarantees on the creation time of corporate actions" (study §6.2). | Price-vintage diff (section 6) | revision banner | none; reproduce from the archived vintage | TQ26, TQ28 |
| DQ12 | One-day timing (non-synchronous close) | VERIFIED: Alpaca's late SPY closes cut the same-day market beta by 0.022 and raise residual volatility from 1.30 to 1.99%/yr (study §4). Japan's same-day correlation with North America is 0.040, against 0.413 with the previous US day (datasets.md 6.3). | Gate (section 5); cross-source DQ1 | gate caveat | 5-day estimate (M3.6); lead-lag betas (ROADMAP, Now) | M3.6 tests, TQ30 |

What closes the gap in DQ4: the existing audit compares a vendor's adjusted close with the *same* vendor's
dividend, so a wrong amount that is applied consistently passes. Only a second record of the event (section 3)
can catch it.

---

## 3. Corporate-action reconciliation (`data/corporate_actions.py`)

### 3.1 Normalised event record

`CorporateAction(ticker, ex_date, kind ∈ {cash_dividend, forward_split, reverse_split, spin_off}, amount_as_paid,
ratio, special, foreign, source, source_record_id, fetched_at)`.

- **Yahoo** dividends are split-adjusted. The as-paid amount is the Yahoo amount times the product of all
  *later* Yahoo split ratios (study §3.3).
- **Alpaca** `rate` is already as paid. The Alpaca record carries `cusip, ex_date, foreign, id, payable_date,
  process_date, rate, record_date, special, symbol` (VERIFIED, cached response). `special` and `foreign` are
  kept and shown.

### 3.2 Matching and classification (pure function of two event lists)

1. Match on `(kind, ex_date)`.
2. An unmatched event whose counterpart lies within 3 trading days is `date_mismatch`. Otherwise it is
   `missing_in_<source>`.
3. Amounts of matched dividends:
   - **record mismatch** when `|ΔD| > max(0.0005, 0.001 * max(D))` (the study's §7 item 4 rule);
   - **material** when `|ΔD| / C_{t-1} > tau_t`, with `C_{t-1}` the as-traded previous close. Material means
     the disagreement moves the ex-date return by more than the band of section 4.
4. Missing events and date mismatches are always material.
5. The study proposed calling every record mismatch an audit `error`. Applied to the cached data, that rule
   would turn SPY 2021-12-17 (effect 0.07 bp) into an error. The materiality rule finds exactly the 4 known
   defects (DQ3, DQ4) and nothing else across 216 events of 5 tickers (VERIFIED, dq_divs).
6. **Splits.** Date and ratio are compared across sources. Independent evidence comes from the price itself:
   Alpaca raw closes are as traded, so the ex-date close ratio must be near `1/ratio` (A5b's
   `|ln rho_t - ln(1/k)| < 0.03`). A split whose price jump contradicts a source's ratio is `split_mismatch`,
   and the finding names the ratio the price implies.

### 3.3 Escalation: which source is trusted when

| Situation | Automatic evidence (licensed, already reachable) | Outcome |
| --- | --- | --- |
| Agree, or immaterial mismatch | - | Nothing to resolve |
| Close-level dispute (DQ1), 2016 onward, Alpaca enabled | Primary-exchange closing auction from Alpaca `/v2/stocks/auctions` (condition `6`, listing exchange; study §3.5). Called only for disputed days, capped per report (rate limit 200/min). | The source equal to the auction to the cent is marked `official`. If the default source is the official one, the flag stays, with the resolution shown. If it is not, the report says so prominently. The headline is still not switched (see the last row). |
| Split date or ratio | As-traded close jump (3.2 item 6) | The ratio consistent with the price is marked `price-consistent` |
| Dividend missing or amount differs | **None.** Both vendors' adjusted series encode their own dividend records, so neither is independent evidence. | `unresolved`. The report shows both values, the effect in bp, the S-SUB rerun, and where to confirm: the issuer's filing on SEC EDGAR (8-K exhibit 99 or 10-Q "dividends declared per share"), or the fund sponsor's distribution history for an ETF. |
| A user records a primary-source confirmation | A local, user-maintained file under `data/` with ticker, ex-date, amount, URL and quoted text (never shipped, never in the repo) | The event is shown as `confirmed by primary source (user-recorded)`. The headline uses the confirmed amount **only if** the user has set `use_confirmed_actions=true`. The report then says so, and the vendor-value result is kept as a sensitivity row. Otherwise the headline is unchanged. |

**Default trust.** Without a resolution, the default source (Yahoo) stays in the headline and the day is
flagged. The study's evidence does not support preferring either vendor's dividend records: each had 2 material
errors in 5 tickers (VERIFIED).

A shipped, cited errata list would be a hard-coded data patch (CODING_STANDARDS §8). It is not built; see owner
decision 3.

### 3.4 How it appears in the report

There is a **corporate-action table** (one row per event with any status other than `agree`): date, kind,
Yahoo value, Alpaca value, status, effect on the ex-date return (bp), and confirmation link or "unresolved". A
summary line counts the events in each status. Each material event adds its day to the disagreement days of
section 4. An unresolved material event raises the report warning `corporate_action_mismatch`.

---

## 4. Agreement status and the per-day score (`data/consensus.py`)

### 4.1 Return definition (all sources)

`r^s_t = C_t s_t / (C_{t-1} - D_t s_t) - 1` (CRSP form), computed by factordesk from the source's as-traded
close `C`, dividend as paid `D` and split ratio `s`. Adjusted prices are never used (DQ2).

- For Yahoo, this equals `Adj Close` returns within 0.017 bp on SPY, AAPL, NVDA, AVGO and VFINX, and within
  0.32 bp on KO, over full histories (VERIFIED, dq_bands A).
- Switching the headline from `Adj Close` to this rebuild removes the irreproducibility of validation F8. It
  needs a D-entry amending M1.3 and M1.4 (owner decision 2).

### 4.2 Per-day status and score

Let `P` be the default source (Yahoo) and `A` the second source (Alpaca, when enabled). For each date `t` that
`P` has:

- `d_t = r^A_t - r^P_t`. The band is `tau_t = 1e-4 + 0.01 / C^{as-traded}_{t-1}` (M1.4).
- **Score** `q_t = |d_t| / tau_t`: the disagreement in units of the band. It is `null` when there is no second
  value.
- **Close-level dispute on t**: `|C^A_t - C^P_t k_t| >= 0.01`, where `k_t` is the product of later splits that
  converts `P`'s close to the as-traded price. A wrong level on `t` contaminates both `r_t` and `r_{t+1}` (it
  reverses), so **both days** are flagged.
- **Status**:
  - `agree`: `q_t <= 1` and no close-level dispute on `t` or `t-1`.
  - `disagree`, with a class in {`close_level`, `dividend`, `split`, `calendar`, `other`}.
  - `single_source`, with a reason: `no_second_source_history` (before 2016-01-04), `second_source_disabled`,
    or `missing_in_second_source`.

**Why this band (VERIFIED, dq_bands).** From 2023-01-03 to 2026-11-17 both vendors carry the official close, and
the band flags **0 of 4,865 ticker-days** (5 tickers x 973 days; max `|d|` 0.37 bp). Over 2016-2022 it flags
SPY 773 days (43.9%), AAPL 62 (3.5%), NVDA 36 (2.0%), KO 4 (0.2%) and AVGO 20 (1.1%), and **every** flagged day
has a class (close level or dividend); none is `other`. Unflagged days have `|d|` p99.9 at most 0.42 bp. By
design, two half-cent roundings move a return by at most `0.005 (2 + r_t) / C_{t-1}`, which `tau_t` covers
whenever `r_t <= 0.02 C_{t-1}` (any price above $20 with moves up to 40%). A sub-penny auction print stays below
the 1-cent level rule (AAPL 2026-10-23: Yahoo 347.73, auction 347.725; VERIFIED, study §3.5).

### 4.3 What the analysis does with disagreement days

- **Headline:** every day is included, exactly as the default source has it. The headline series is bitwise
  equal to `r^P` (TQ14).
- **S-EX (requested exclusion rerun):** refit without the flagged days. Report the change in alpha (%/yr, next to
  its HAC SE), in each beta and in R2.
  - S-EX has status `not_applicable` when flagged days are more than 5% of the overlap. Reason: "the sources
    disagree on the closing-price definition in this period; excluding them would analyse a different sample".
    SPY 2016-2022 is that case (41.3% of P-2016 days).
  - The 5% is a display constant, not a statistic.
- **Placebo band for S-EX (not requested, needed to read S-EX).** Disagreement days cluster on volatile days, so
  removing them shifts alpha even when the data are fine. The fix: exclude the same number of days at random,
  matched on `|Mkt-RF|` deciles; 200 draws, seed `20261118`; report the 5th and 95th percentiles of the alpha
  change.
  - Evidence (VERIFIED, dq_sens, P-2016): for AAPL, NVDA and AVGO, the S-EX alpha change (+0.84, +0.94, +0.96
    %/yr) is smaller than the placebo change in 21-51% of draws. So the raw S-EX number alone would mislead.
  - KO (+0.52, 5 days) lies outside its placebo band (3% of draws).
- **S-SUB (substitution rerun):** replace `r^P_t` by `r^A_t` on flagged days only, so the sample is unchanged
  and only the data differ. This isolates the data effect. VERIFIED, dq_sens:

  | Ticker | Alpha change (%/yr) | Largest beta change | Cause |
  | --- | --- | --- | --- |
  | AAPL | +0.004 | 0.001 | - |
  | NVDA | -0.003 | 0.001 | - |
  | KO | +0.037 | 0.003 | - |
  | AVGO | -0.138 | - | Yahoo's doubled dividends |
  | SPY | +0.225 | 0.024 (market beta -0.0225) | Alpaca's late closes |

  S-SUB shows the range across sources. It does not decide which source is right; section 3.3 does.
- **Tags.** No new test. If the alpha tag (M3.2) differs between the headline and S-SUB, the warning
  `source_sensitive_alpha` says so: "Alpha's significance depends on which vendor's data are used on {k} days."

### 4.4 Data-confidence summary (report panel)

One row per period: before 2016-01-04, and 2016-01-04 to the end.

- Columns: days in the sample; `single_source` / `agree` / `disagree` counts, with the disagree days split by
  class; material corporate-action events (resolved, unresolved); S-EX, its placebo band and S-SUB deltas; and a
  plain label.
- **Label rule:**
  - "Two sources agree": the overlap exists, at least 99% of its days are `agree`, and there is no unresolved
    material event. The 99% reuses the study's pre-registered cross-check criterion (§1.3).
  - "Two sources, with disagreements": otherwise.
  - "Single source": no overlap.
- There is no composite score. A single number would hide which defect drives it.

---

## 5. The quality gate: G1 against the variance-ratio proposal

**Binding now:** M3.6 / D22. G1 fires iff `rho_1 < -0.2` **and** robust `z_rho < -4`.

**Proposal (study §7 item 5):** add "`rho_1 < -0.2` and `VR5 < 0.6`". This plan reads it as the union
`C1 = G1 ∨ (rho_1 < -0.2 ∧ VR5 < 0.6)`, which is what "keeps G1 and adds" means.

**What the proposal is, analytically.** Under the M3.6 noise model (`e_t = w_t + u_t - u_{t-1}`), `VR(q) = 1 +
2 sum_j (1 - j/q) rho_j`, so `VR5 = 1 + 1.6 rho_1`. That gives `VR5 < 0.6 ⇔ rho_1 < -0.25`. The observed
pairs fit this closely (VERIFIED, study §4):

| Series | rho_1 | Predicted VR5 | Observed VR5 |
| --- | --- | --- | --- |
| Alpaca SPY | -0.386 | 0.38 | 0.33 |
| Yahoo SPY, P-2016 | -0.239 | 0.62 | 0.63 |

So VR5 is not new information about the noise. It is a second estimate of the same quantity. What it changes is
the **guard against sampling noise**: G1 uses the robust z, which March 2020 swamped (Alpaca SPY: z -2.1).

**Design check on synthetic data (VERIFIED, gate_sim, 1,000 replications per cell, seed 20261118; GARCH(1,1)-t5
residuals with MA noise of share s).**

- **No false alarms.** Under the null, G1, `V = (rho_1 < -0.2 ∧ VR5 < 0.6)` and `R = (rho_1 < -0.2 ∧ rank-z <
  -4)` fired in 0 of 1,000 runs at every n in {504, 1260, 2520, 8474}.
- **V alone is weaker than G1.** At s = 0.4 and n = 2520, V detects 17-28% against G1's 62-73%.
- **R (rank-z, `sqrt(n)` times the lag-1 Spearman autocorrelation) is the most sensitive.** At s = 0.4,
  volatility-scaled noise and n = 504, it detects 67% against G1's 49%.
- **Short samples.** Under the null at n = 504, the 1st percentile of VR5 is 0.63, close to 0.6. VR5 must never
  gate on its own in short samples.
- These are design calculations on synthetic data, not a calibration.

**Interim rule.** G1, unchanged (M15 constants untouched). VR5 and rank-z are **not shown in reports** until
H-DQ1 is decided. A new reported statistic needs a methodology section first (protocol §9). Showing candidate
flags next to the binding one would also invite choosing whichever looks better (M3.6). One wording change, to
be proposed as a separate D-entry: per study §4, the caveat should name both causes, "a close recorded after the
4:00 pm index close, or an ETF's closing price differing from its index value". SPY with official closes still
has `rho_1 = -0.35` from 2023.

**How H-DQ1 is tested (pre-registered in section 8; thresholds fixed now, nothing tuned).**

- **Candidates:** C1 = G1 ∨ V (the proposal) and C2 = G1 ∨ R. Both contain G1, so each can only add detections
  and false alarms; the test is that trade-off.
- **(a) Placebo grid** (`factordesk calibrate`, ROADMAP Next): full pipeline on real French factor rows (vintage
  stamped), `y = beta' f + e`, `e` GARCH(1,1)-t5 plus MA noise with s ∈ {0, 0.2, 0.3, 0.4, 0.6}, constant or
  volatility-scaled; n ∈ {504, 1260, 2520, 8474}; 2,000 replications per cell, seeds `20261118 + cell`.
- **(b) Real negatives:** 300 US common stocks drawn with `numpy.random.default_rng(20261118)` from a universe
  snapshot whose SHA-256 is in the registry line **before** any price is fetched (universe source: owner
  decision 5). Confirmation window 2016-01-04 to the vintage's last date (protocol §4). Fixed now: tickers whose
  Yahoo/Alpaca close-level disagreement exceeds 1% of days from 2023 leave the negative set; the study's tickers
  are excluded (in-sample).
- **(c) Real positives (descriptive):** ETFs with a 4 pm reference index on Yahoo, listed in the registry line
  after a coverage pre-check on dates only, labelled positive when the tracking difference against the reference
  has lag-1 autocorrelation below -0.3 with robust z below -4 (a label that does not use the factor residual).
  Whether enough pairs exist is UNVERIFIED.
- **Decision rule.** Ck is adopted iff all of the following hold:
  1. its *extra* false-alarm rate over G1 is at most 0.5 percentage points in every null placebo cell (binomial
     SE at 2,000 replications: 0.16 pp);
  2. its extra false-alarm rate on the real negatives is at most 1 pp (SE at 300 tickers about 0.6 pp at a 1%
     rate);
  3. its extra detection at s ∈ {0.4, 0.6}, n ≥ 1260, volatility-scaled, is at least 5 pp.

  Failing any of 1-3 counts against the candidate. If both pass, the lower real-negative false-alarm rate wins
  (tie: C1); if neither passes, G1 stays. Adoption is a D-entry plus an M15 change. (c) has few positives, so it
  is reported, not decided on. Criteria 1-3 are threshold rules, not p-values; family H-DQ1 has m = its registry
  lines, and BH applies only if a p-value claim is made.

---

## 6. Licences, provenance and vintage for prices

This extends D5 (`docs/methodology-datasets.md`) from factor files to prices. D5.1 already requires "FX and price
inputs record the provider, ticker, download time and a SHA-256 of the serialised frame used".

- **Per source, in every report** (`DataInfo.sources`): provider and version (yfinance version, Alpaca API
  path); request parameters without secrets (`adjustment=raw`, `feed=sip`, start, end); `fetched_at` (UTC);
  SHA-256 of the normalised raw frame (as-traded close, dividends, splits) and of the corporate-action list;
  first and last date; the terms label.
- **Price vintage archive (local, gitignored):** `data/prices/<source>/<ticker>/vintages/<fetched_at>_<sha[:12]>.parquet`
  plus `revisions.jsonl`. Each fetch is compared with the previous vintage on common dates: `close_revised`
  (`|Δ| >= 0.005`), `dividend_added/removed/changed` (materiality per 3.2), `split_changed`, `history_rewritten`
  (a date removed or the first date changed), `appended_rows`. `adj_close` is not compared because it is not
  used (4.1), which removes F8's noise.
- **Report banner** "vendor revised {n} values since the last report for this ticker" (D5.3 applied to prices).
  `reproduce(report)` loads the archived price and factor vintages by SHA-256 and must give bitwise-equal
  numbers (TD34 extended, TQ28).
- **By source:** archiving is exactly what Tiingo's terms forbid; for Alpaca it is UNVERIFIED (section 1). Users
  can turn archiving off; `reproduce` then returns `vintage_not_available`.
- **Mixed fetch times:** sources fetched more than 24 hours apart give `mixed_fetch_time` (info), since a late
  corporate action (Alpaca gives no timing guarantee) can explain a mismatch.

---

## 7. Phased build plan (the ROADMAP Next item)

Modules, all under `backend/factordesk/`:

| Module | Content |
| --- | --- |
| `data/sources/base.py` | `PriceProvider` v2 protocol, `RawPriceHistory` |
| `data/sources/yahoo.py` | Yahoo provider |
| `data/sources/alpaca.py` | Alpaca provider: raw closes, corporate actions, auctions |
| `data/total_return.py` | Pure CRSP rebuild |
| `data/corporate_actions.py` | Section 3 |
| `data/consensus.py` | Section 4.2 |
| `data/price_vintage.py` | Section 6 |
| `analytics/source_sensitivity.py` | S-EX, placebo, S-SUB |
| `report/panels/data_quality.py` | Renderer for the data-quality panel |

**Dependencies on the schema v3 contract.** All new report content goes in optional sub-models (ROADMAP risk
1), so none of these phases blocks other branches. They must be in the contract before Phase 4:

- `FactorReport.data_quality: DataQuality | None` (statuses, class counts, corporate-action rows, S-EX, placebo
  band, S-SUB, label);
- `DataInfo.sources: list[SourceProvenance]` (optional, default empty);
- warning codes `source_disagreement`, `corporate_action_mismatch`, `source_sensitive_alpha`,
  `single_source_period`, `vendor_revision`.

| Phase | Scope | Acceptance (all oracle tests listed green, plus ruff, pyright strict and T102-T104) | Depends on |
| --- | --- | --- | --- |
| 0 | Config: feed `sip`, key names (ROADMAP Now); D-entry for the rebuilt headline (owner decision 2) | TQ08 | First commit |
| 1 | `total_return.py`; `RawPriceHistory` (as-traded close, dividends as paid, splits, provenance); Yahoo provider emits it; the headline switches to the rebuild | TQ01, TQ02, TQ27; the SPY live smoke gives the same report numbers within 1e-6 | Phase 0 |
| 2 | Alpaca provider (raw bars, paging, rate limit, `end` at least 15 minutes old, corporate actions, auctions for disputed days only); opt-in | TQ03-TQ08 | Phase 1; owner decision 1 |
| 3 | `corporate_actions.py` | TQ09-TQ13 | Phase 2 |
| 4 | `consensus.py`, the sensitivity reruns, the schema sub-models and the panel | TQ14-TQ25 | Phase 3; schema v3 contract |
| 5 | `price_vintage.py`, `reproduce` for prices | TQ26-TQ28 | Phase 1 |
| 6 | H-DQ1 to H-DQ5 runs (section 8) through `factordesk calibrate` | registry lines with results; TQ29-TQ30 | Placebo calibration CLI (ROADMAP Next) |

---

## 8. Registry entries (to append to `docs/registry/tests.jsonl` when the build branch opens)

- Format: protocol Appendix A.
- `code_version`: the scratchpad scripts for 201-204; the commit of the run otherwise.
- Datasets: `us_ff5_daily`, stamp 202609, SHA-256 `e58577223032…` (datasets.md 5.1); prices as in study §2.
- Every hypothesis is its own family.

| test_id | hypothesis_id | status | hypothesis / content | spec, split, decision rule |
| --- | --- | --- | --- | --- |
| T-20261118-201 | descriptive | run | Band behaviour and flag classes (dq_bands) | SPY, AAPL, NVDA, KO, AVGO; 2016-01-05..2026-11-17; `in_sample_only`. Result: section 4.2. |
| T-20261118-202 | descriptive | run | S-EX, placebo band and S-SUB on P-2016 (dq_sens) | Same tickers; 2016-01-05..2026-09-30; seed 20261118; `in_sample_only`. Result: 4.3. |
| T-20261118-203 | descriptive | run | Dividend record and materiality comparison (dq_divs) | Same; 216 events; `in_sample_only`. Result: 3.2. |
| T-20261118-204 | descriptive | run | Synthetic gate firing rates (gate_sim) | Synthetic; seed 20261118; 1,000 replications. Result: section 5. |
| T-20261118-211 | H-DQ1 | pre-registered | C1 or C2 adds detection without materially adding false alarms over G1 | Section 5. Confirmation 2016-01-04..vintage end; seed 20261118; family H-DQ1 (m = 2, one line per candidate). |
| T-20261118-212 | H-DQ1 | pre-registered | (as 211, candidate C2) | as 211 |
| T-20261118-213 | H-DQ2 | pre-registered | When both sources carry official closes, the band does not raise unexplained flags | 2023-01-03..last date; 100 tickers drawn as in section 5 (b), excluding the study's tickers. Supported: unclassified (`other`) flags on at most 0.1% of days for every ticker, and total flags at most 1% for at least 95% of tickers. Against: any ticker above 0.1% `other`. |
| T-20261118-214 | H-DQ3 | pre-registered | Yahoo and Alpaca dividend records agree (or differ immaterially) on at least 99% of events | The same 100 tickers, 2016-01-04 onward. Against: fewer than 99%. Also report each material event's resolution status. |
| T-20261118-215 | H-DQ4 | pre-registered | For liquid US single stocks, the source barely matters: S-SUB `abs(Δalpha) <= 0.10%/yr` and `max abs(Δbeta) <= 0.01` for at least 95% of tickers | Same tickers and period. Against: fewer than 95%. Basis: 3 of 4 stocks within 0.04%/yr (4.3). AVGO's 0.138 shows why it can fail. |
| T-20261118-216 | H-DQ5 | pre-registered | Yahoo `Close` and `Dividends` are identical between two downloads at least 7 days apart on at least 99.9% of rows per ticker | The same 100 tickers, full history, two fetches. Against: any ticker below 99.9%. Basis: one same-day pair (validation F8). |

Power: H-DQ2 to H-DQ5 are threshold rules. With 100 tickers, a 95% share has a binomial SE of 2.2 pp, so the
95% rules need a true rate of about 99% to pass reliably. This is stated so that a failure is not over-read.

---

## 9. Decisions the owner must make

1. **Alpaca "User Application" clause.** Does shipping an Alpaca adapter need the 30-day written notice? Until
   decided, the adapter stays opt-in and off by default (counsel advised, study §7 item 6).
2. **Headline returns rebuilt from `Close` + `Dividends`** instead of `Adj Close`: a D-entry amending M1.3 and
   M1.4 (A6-A8 keep auditing `Adj Close`). Evidence: they agree within 0.32 bp at most, and the rebuild removes
   F8.
3. **Cited errata list.** Ship a curated, primary-source-cited list of known vendor errors (for example AVGO
   2018), or keep confirmations user-local only (this plan's default).
4. **Tiingo** leaves the ROADMAP rows, unless a written licence is obtained.
5. **Universe source for the H-DQ panels** (an Alpaca asset list fetched with the owner's key, or an
   owner-supplied list). Whether the Alpaca asset list is available with a market-data key is UNVERIFIED.

---

## Test oracle (TQ)

Conventions of `docs/test-oracle.md` §0 apply. Seeds: `20261118 + 900 + k` for TQk. Fixtures are synthetic
(section 1). Markers: none = blocking; `slow`; `live` (non-blocking).

| ID | Module | Setup | Assertion | Tolerance |
| --- | --- | --- | --- | --- |
| TQ01 | `total_return` | Closes, dividends and a 4:1 split, chosen by hand | `r_t = C_t s_t/(C_{t-1} - D_t s_t) - 1` on every row; split day without dividend gives `4 C_t/C_{t-1} - 1`; NaN or non-positive close makes rows t and t+1 NaN, never 0 | 1e-15 |
| TQ02 | `total_return` vs `Adj Close` | Synthetic `Adj Close` built with backward CRSP factors; `live`: SPY, KO | Rebuild equals adjusted returns | 1e-12 synthetic; live 0.5 bp (observed 0.32) |
| TQ03 | `sources/alpaca` | Mocked HTTP | Every bars request has `adjustment=raw&feed=sip&timeframe=1Day`; a call with `all` or `iex` raises; static scan finds no `adjustment=all` in `data/` | exact |
| TQ04 | `sources/alpaca` | 3 pages with `next_page_token`, 2 symbols split across pages | All bars collected once each, in order | exact |
| TQ05 | `sources/alpaca` | Timestamps `T04:00:00Z`, `T05:00:00Z`, `T13:30:00Z` | First two map to the UTC date; the third raises `PriceDataError` | exact |
| TQ06 | `sources/alpaca` | Injected clock at 09:00 New York | `end` equals the previous session date (at least 15 minutes old) | exact |
| TQ07 | `sources/alpaca` | `X-RateLimit-Remaining: 0` header; injected sleeper | No request is sent before the reset; total requests per minute at most 200 | exact |
| TQ08 | config / providers | Keys in env; a failing request | Keys only in headers; error text and logs (caplog) contain no key; `.env.example` placeholders only | exact |
| TQ09 | `corporate_actions` | Yahoo dividend 0.35 before a later 10:1 split | Normalised as paid 3.50 | 1e-12 |
| TQ10 | `corporate_actions` | Pairs: identical; 1.078 vs 1.078442; missing in A (SPY-shaped); 3.50 vs 1.75 (AVGO-shaped); ex-date shifted by 1 day | Classes `agree`, `immaterial`, `missing_in_A` (material), `amount_mismatch` (material), `date_mismatch` | exact |
| TQ11 | `corporate_actions` | `abs(ΔD)/C_{t-1}` equal to `tau_t`, then `tau_t + 1e-9` | Not material, then material (boundary) | exact |
| TQ12 | `corporate_actions` | Raw close drops to 1/4 on the ex-date; source A says 4:1, source B says 2:1 | B's event is `split_mismatch`, implied ratio 4 | exact |
| TQ13 | `corporate_actions` | Disputed close; mocked auction equal to source A; then no auction data | `official = A`; then `unresolved`; the headline series is bitwise unchanged in both | exact |
| TQ14 | `consensus` | Property test (hypothesis library, fixed seed): random disagreement patterns injected into A | The headline return series equals `r^P` bitwise; differences appear only in `DataQuality` | exact |
| TQ15 | `consensus` | `abs(d) = tau_t`; `tau_t + 1e-12`; A missing a date; dates before A's first date | `agree`; `disagree`; `single_source/missing_in_second_source`; `single_source/no_second_source_history`; date-set mismatch has class `calendar` | exact |
| TQ16 | `consensus` | A level error of +5 cents on day t only (it reverts); and on the last day | Flags t and t+1 (class `close_level`); last day flags only t | exact |
| TQ17 | `consensus` | Any input | `q_t = abs(d_t)/tau_t`; `null` when single source; no NaN or inf serialised | 1e-15 |
| TQ18 | `consensus` | Two sources from the same true closes, each rounded to the cent independently, prices in [5, 1000], `abs(r) <= 10%` | 0 disagreement days (follows from the bound in 4.2) | exact |
| TQ19 | `consensus` (`live`) | SPY, AAPL, KO, 2023-01-03..2023-12-29, Yahoo and Alpaca | 0 disagreement days (observed 0 of 973 per ticker from 2023) | exact |
| TQ20 | `source_sensitivity` | DGP-A; 20 reverting level errors in P, A clean | S-EX betas recover the truth within 4 SE; reported deltas equal refit differences | 4 SE; 1e-12 |
| TQ21 | `source_sensitivity` | As TQ20 | S-SUB equals the OLS fit on P with A's values on the flagged days | 1e-12 |
| TQ22 | `source_sensitivity` | As TQ20, seed fixed | Placebo draws match the flagged days' `abs(Mkt-RF)` decile counts exactly; quantiles reproduce bitwise on rerun | exact |
| TQ23 | `source_sensitivity` | Flagged share 5.0% and 5.01% | Applicable, then `not_applicable` with the reason text | exact |
| TQ24 | `report/schema` | Reports with and without a second source | Both validate; `data_quality` None or populated; the M0.7 status rules hold | exact |
| TQ25 | `report/panels/data_quality` | Synthetic counts | single + agree + disagree = n per period; the label rule of 4.4 at the 99% boundary | exact |
| TQ26 | `price_vintage` | Two vintages: one close +1 cent; a dividend added; only `adj_close` changed | `close_revised` 1, `dividend_added` 1, no record for `adj_close`; banner text | exact |
| TQ27 | `sources/base` | The same frame serialised twice | SHA-256 equal; request parameters recorded with no secret fields | exact |
| TQ28 | `price_vintage` | Report on vintage 1, then vintage 2 becomes current | `reproduce` gives bitwise-equal numbers; missing archive gives `vintage_not_available` | exact |
| TQ29 | diagnostics (calibration only) | MA(1) DGP with `rho_1 = -0.3`, n = 8474, 500 replications (`slow`) | Mean VR5 = `1 + 1.6 rho_1` = 0.52; rank-z computed as `sqrt(n)` times the Spearman lag-1 | 4 SE |
| TQ30 | `analytics/diagnostics` | Residuals built to give `rho_1 = -0.386`, `z_rho = -2.1` | G1 does not fire; tags unchanged; no VR5 or rank-z field in the report (interim rule) | exact |

## Owner decisions (2026-11-18)

1. **Headline returns:** factordesk computes total returns itself from raw Close plus Dividends
   (CRSP convention) for every source. The vendor's Adj Close becomes a cross-check, reported when it
   disagrees. This requires a methodology update and lands with the schema v3 contract.
2. **Tiingo:** kept as a Later option for users with a paid licence that allows this use. Nothing is
   built for the free plan.
3. **Known vendor errors list:** not shipped. Known errors are documented in the wiki only; the audit
   relies on automatic checks.
4. **Test panel:** 32 tickers, stratified: SPY, the 11 sector ETFs, and 20 stocks spread across size,
   sector and dividend habits, including the known problem cases (AVGO, NVDA, KO). The list is
   frozen in a file before any result is seen.
5. **Alpaca feed:** `sip` for history (the config default `iex` is corrected in the contract branch).
   Alpaca's "user application" notice is checked before the adapter ships.
