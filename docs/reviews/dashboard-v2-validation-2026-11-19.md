# Dashboard v2: independent validation before delivery

Date: 2026-11-19. Branch under review: `integrate/ui-v2` at `4aa0eef`, checked out as `validate/ui-v2`.
Rules used: `docs/specs/dashboard-v2.md` (DV4 verdict rules, DV11 owner decisions), `docs/design/report-design.md` rev 3, the approved look `feat/ui-v2-prototype:docs/design/prototype/report-v4a.html` and its screenshots `shot_v4a_*.png`, and the owner decisions of 2026-11-19 (v4a approved; betas in neutral ink; red and green only on signed returns, alpha, Sharpe, drawdown and return contributions; light only; presets 3Y, 5Y, 10Y, Full; no regression formula; company name; performance; world beta with ACWI and IEUR stand-ins).
Environment: Windows 11, Node 26.13.0, Python 3.13.14, Google Chrome driven headless through Playwright 1.65.1 (`channel: "chrome"`). Server: `uv run factordesk serve --port 8822`, built page from `frontend/dist` (`npm ci && npm run build`, 28 s).
Screenshots (not committed): `C:\Users\loren\Research\factordesk-wt\validate-ui-v2\docs\reviews\dashboard-v2-validation-2026-11-19-shots\`. Paths below are relative to that folder.
Already known and being fixed in parallel, so not repeated here: nav lists Lead-lag and Fragility although absent; header lacks the warnings link; "NYSEArca" instead of "NYSE Arca"; no ETF badge; panel titles differ from nav labels.

**Verdict: SHIP WITH FIXES.** Every number I recomputed is right and correctly rounded and signed, the alpha and world-beta wording follows the tags and intervals, every gate is green, and keyboard, drawer, URL state and download work. No blocker. Six major findings should be fixed before the owner reads the page: a wrong day count on the world beta panel, two different numbers both called the "US market beta", the DV4.9 outcome lines not built (the v1 questions are still under every title), causal and second-person copy in Risk sources, the panel order not matching the nav and v4a, and chart text under 14 px.

---

## 1. Findings

### Blocker

None.

### Major

**M1. World beta panel prints the five-factor sample size as the ACWI day count.**
- Where: `frontend/src/components/report/sections/WorldBetaBody.tsx:146` (`days: count(s.n_sample)`) and `:178` (legend `Quick estimate, ${count(s.n_sample)} days, one-factor`). URL `http://127.0.0.1:8822/?t=SPY&range=FULL`. Screenshot `spy_full_panel_world-beta.png`.
- Evidence: SPY Full shows "Quick estimate, 8,474 days" and ACWI "Days 8,474". The regression ran on `world_beta.sample.n` = 4,656 days (31 Mar 2008 to 30 Sep 2026; ACWI starts 28 Mar 2008); `n_sample` = 8,474 is the five-factor sample and `n_not_in_benchmark` = 3,818 days were left out. I refitted it: 4,656 rows reproduce the backend beta 0.94516 and HAC se 0.01167 exactly. The error is invisible on 3Y and 5Y, where the two counts coincide.
- Fix: use `s.sample.n` in both places; add a unit test with `n_sample != sample.n`. While there, add the DV4.9 sentence "This covers a shorter span than the five-factor model, because the fund's history starts in March 2008."

**M2. Two different numbers are both called the "US market beta".**
- Where: `frontend/src/components/report/SummaryPanel.tsx:46` (row "Beta to US market" = five-factor Mkt-RF beta) against the ACWI note and the World beta panel, which use the one-factor `world_beta.us_market.beta`. Screenshots `spy_full_1440.png`, `spy_full_panel_world-beta.png`, `zm_5y_1440.png`.
- Evidence: SPY Full: Summary "Beta to US market +1.01"; World beta panel "US market +0.97"; the ACWI reading note says "about the same as its US market beta of 0.97". ZM 5Y is worse: Summary "Beta to US market +0.88" next to "Beta to ACWI +1.33", which reads as "much higher against the world", while the like-for-like one-factor US beta is 1.32 ("about the same", intervals 1.14 to 1.51 and 1.15 to 1.49 overlap). The table invites a comparison the statistics do not support (DV4.2 rule 1).
- Fix: label the Summary row "Market beta (five-factor)" and the panel row "US market (one-factor, same days)", or show the one-factor US beta in the Summary row note next to the ACWI beta. Keep "about the same as" tied to the one-factor pair only.

**M3. DV4.9 outcome lines are not built; the v1 questions are still the takeaway line of every panel.**
- Where: `Panel.tsx:48` renders `question`; `PricePanel.tsx:10`, `ExposuresPanel.tsx:15`, `ReturnPanel.tsx:68`, `RiskPanel.tsx:32`, `RollingPanel.tsx:462`, `KalmanPanel.tsx:427`, `DataAuditPanel.tsx:98`, `RegressionDetail.tsx:250`. `text/verdict.ts` has no outcome-line functions. Screenshots `spy_full_1440.png` (Price), `spy_full_panel_exposures.png`, `spy_full_panel_risk.png`.
- Evidence: the approved v4a opens each panel with its result ("Up 30.5% over the analysed window. The last 32 trading days are charted but not analysed."; "Market beta 1.00. Clear but small tilts: size and profitability."; "Steady: the market beta stayed between 0.99 and 1.01 in most windows"). The build shows "How has the price moved over the window? Shaded days are not in the analysis.", "What is this stock exposed to, and how sure are we?", "Have the exposures been stable, or did they drift?" and so on. Only Drawdown and World beta carry a result line. The Regression detail therefore also lacks the DV4.9 gate sentence ("a term counts as significant only when the 5-day estimate agrees"), which matters on SPY Full, where the gate fired.
- Fix: implement the DV4.9 rows in `text/verdict.ts` (tests word for word, as DV9 V8 and V9 ask) and pass them as the panel's lead line; drop the questions, or keep them only as screen-reader descriptions.

**M4. Risk sources copy is causal and addresses the reader's portfolio.**
- Where: `backend/factordesk/analytics/attribution.py:229` ("{name} reduces total risk because it offsets your other exposures.") and `:225` ("moves with your other exposures"), shown by `RiskPanel.tsx`; lead sentence built at `RiskPanel.tsx:60` with codes. Screenshot `spy_full_panel_risk.png`.
- Evidence: SPY Full: "Mkt-RF drives 98.4% of the variance; stock-specific risk is 3.3%. ... RMW reduces total risk because it offsets your other exposures. CMA reduces total risk because it offsets your other exposures." DV4.2 rule 3 bans "because of"-style causation outside the arithmetic split, the report is about one security and not "your" portfolio, and DV4.2 rule 7 wants plain names ("Market exposure drives 98.4% of SPY's day-to-day risk; 3.3% is specific to SPY", DV4.9).
- Fix: use the DV4.9 Risk sources sentence; reword the negative-share note to "RMW and CMA have negative shares: they offset part of the other exposures in the variance split." with no "because" and no "your".

**M5. Panel order does not match the nav or v4a.**
- Where: `frontend/src/components/report/panelRegistry.ts:57` (`shrunk` at 520, between World beta and Return sources) and `:60` (`residual_alpha` at 710, before `rolling` at 800), against `components/shell/SectionNav.tsx:27-32` and v4a (Rolling, then Residual, Kalman, Shrunk under "Deeper checks").
- Evidence: page order on SPY Full: Summary, Price, Drawdown, Factor exposures, World beta, **Pulled toward typical**, Return sources, Risk sources, **Residual return, Exposure over time**, Kalman, Data, Regression detail. The nav lists Exposure over time before Beyond the factors and Adjusted for noise last but two, so scrolling makes `aria-current` jump from "World beta" to "Adjusted for noise" and back to "Return sources" (scroll-spy log in section 3). A "deeper check" sits among the main panels. Screenshot `spy_full_fullpage_after_scroll.png`.
- Fix: positions rolling 710, residual_alpha 800, kalman 810, shrunk 820 (or the v4a order the nav already uses); add a test that the registry order equals the `NAV_ITEMS` order.

**M6. Text under 14 px (design rev 3: "no text under 14 px anywhere, including chart").**
- Where: `frontend/src/components/report/priceModel.ts:172` and `:184` (`fontSize: 12.5`, price and drawdown axis labels and tooltip), `RollingPanel.tsx:165` (tooltip `fontSize: 12`), `sections/ShrunkBetasPanel.css:42` (`font-size: 11px` cell labels "OLS", "Shrunk", "se", "95% credible interval", "Pull" below 720 px).
- Evidence: computed-style scan of the DOM: the only text under 14 px at 1440 is SVG chart text at 12.5 px; at 390 px also the five `::before` labels at 11 px. Everything else is 14 px or more.
- Fix: 14 px in the three chart text styles and in the Shrunk cell labels.

### Minor

- **m1. Scroll-spy marks "Drawdown" while Price is at the top.** Price and Drawdown share a row, so both cross the 20% line together and the later one wins. Fix: for paired panels, prefer the left one (`SectionNav.tsx`, active-item rule).
- **m2. The "Reading" header tooltip is wrong for three rows.** `SummaryPanel.tsx:149` says "Clear evidence: the 95% interval excludes zero after correcting for testing five betas at once." That holds for the beta row only; alpha is a single 5% test, the Sharpe ratio and the ACWI beta read their own intervals. Fix: "Clear evidence: the result is distinguishable from zero at the 5% level (betas corrected for testing five at once). Could be noise: it is not."
- **m3. "no alpha" on the page.** `sections/ResidualAlphaBody.tsx:69`: "... ordinary for a stock with no alpha." DV4.2 rule 1 bans the phrase. Fix: "... ordinary when the true return beyond the exposures is zero."
- **m4. "p = <0.001".** `ResidualAlphaBody.tsx:907` with `format/numbers.ts:45` (Ljung-Box, Jarque-Bera, ARCH lines). DV4.9 copy fix asks for "p < 0.001".
- **m5. Return sources sentence.** `ReturnPanel.tsx:92`: "Alpha adds −0.58%." uses "Alpha" in a sentence (DV4.2 rule 2) and "adds" for a negative number. "Not in the sum" prints "stock return -3.96%" (hyphen, not the true minus) and the ISO date "2026-09-30" (DV4.3 wants "30 Sep 2026"). Fix: the DV4.9 Return sources sentence; format with `pct` and `dateLong`.
- **m6. Risk "How this is computed" ends "Sum check -2.2e-16."** (`RiskPanel.tsx:70`): a developer check with a hyphen minus. Fix: drop it, or "The shares add to 100% to within rounding."
- **m7. Risk legend swatches use green (SMB) and red-pink (HML)** on a panel that carries no signed return. The owner reserved red and green for signed returns, alpha, Sharpe, drawdown and return contributions. Fix: neutral or blue-family categorical swatches. Screenshot `spy_full_panel_risk.png`.
- **m8. A disabled range in the URL is analysed silently as Full.** `?t=ZM&range=10Y` loads 22 Apr 2019 to 30 Sep 2026, shows the 10Y chip selected although disabled, and keeps `range=10Y` in the URL. The reason is shown in the sidebar, so nothing is misstated. Fix: rewrite the URL to `range=FULL` and select Full. Screenshot `zm_10y_direct_1440.png`.
- **m9. The Summary band does not end with "Descriptive, in-sample, not predictive."** (DV4.2 rule 4; design rev 3 line 978). The page shows "Past data, not a forecast." at the top right, as v4a does. The owner should confirm that v4a's wording replaces the rule; if so, update DV4.2.
- **m10. Price panel lacks v4a's legend and "Adjusted close" aside** (v4a: "Adjusted close, USD", "Analysed window", "End of factor data"). Screenshot `spy_full_1440.png` against `shot_v4a_1440.png`.
- **m11. Size budget headroom is 1%.** 396.3 of 400 kB raw and 123.8 of 125 kB gzip. Any fix that adds code to the entry chunk will fail `npm run size`; put new text helpers in lazy chunks.

---

## 2. Numbers: SPY Full, recomputed

Independent code (`recompute.py` in scratch, statsmodels OLS with HAC Bartlett errors) on `data/prices/SPY_2026-11-19.parquet` (adjusted close) and `data/factors/ff5_daily.parquet`, sample 1 Feb 1993 to 30 Sep 2026, 8,474 days (equal to `n_obs`).

| Metric | Mine | API | UI | Check |
|---|---|---|---|---|
| Annualised return (CAGR, years = n/252) | 0.108258 | 0.108258 | +10.8% (green) | ok |
| Volatility (ddof 1, x sqrt 252) | 0.185293 | 0.185293 | 18.5% (ink) | ok |
| Sharpe (mean excess x 252 / vol) | 0.515039 | 0.515025 | +0.52 (green), "Clear evidence", interval +0.18 to +0.85 | ok (difference 1.4e-5, below print precision) |
| Max drawdown | −0.551894, 9 Oct 2007 to 9 Mar 2009 | same | −55.2% (red), "Recovered", back 16 Aug 2012 | ok |
| Alpha a year (252 x intercept) | −0.005765, HAC z −2.2368 (10 lags) | −0.005765, z −2.2368, p 0.0253 | −0.58% (red), "Clear evidence" | ok |
| R² | 0.967339 | 0.967339 | 96.7%, "Probably understated" | ok |
| Residual volatility (ddof 1) | 0.033488 | 0.033488 | 3.3%, "Probably overstated" | ok |
| Beta to US market (five-factor) | 1.009308, z 151.8 | same | +1.01 (ink), "Clear evidence" | ok (see M2) |
| Beta to ACWI (one-factor, 4,656 days, 9 lags) | 0.94516, se 0.01167, 0.9223 to 0.9680 | same | +0.95 (ink), "Clear evidence" | ok (see M1) |

All five betas and their HAC z match to three decimals. Signs use the true minus; betas are neutral ink (`rgb(74, 84, 112)`), and only return, Sharpe, drawdown and alpha carry green `rgb(0, 120, 98)` or red `rgb(194, 51, 69)`, as the owner decided. Exposure bars are neutral ink; return-contribution bars are green and red.

**Alpha and the quality gate.** The gate fired on SPY Full (lag-1 autocorrelation −0.40, robust z −13.1). Methodology M3.2 and M3.6: alpha is "reliable" only if the daily single 5% test and the 5-day test both reject. Daily: z −2.24, p 0.025. 5-day (1,694 blocks): alpha −0.56% a year, z −2.55, p 0.011, same sign, `alpha_tag` "reliable". So the backend's `alpha_tag` = "reliable" is right, the UI reads it and does not recompute it (`text/verdict.ts` `alphaReading`), "Clear evidence" is right, and the headline "earned 0.6% a year less than its exposures explain over this range" is the DV4.4 reliable-negative form with `pct1` rounding. The gate hedge sentence follows the headline, and R² and residual volatility read "Probably understated" and "Probably overstated" (DV4.5). HML shows how the conjunction works: daily z 0.81 (noise), 5-day z 3.49; the tag is "noise", and the headline correctly lists only size, profitability and investment tilts.

**World beta wording on real data** (overlap = the two 95% intervals overlap):

| Report | ACWI interval | US one-factor interval | Overlap | Backend | UI |
|---|---|---|---|---|---|
| SPY Full | 0.922 to 0.968 | 0.957 to 0.992 | yes | about_the_same | "About the same against the world as against the US market." |
| SPY 5Y | 0.995 to 1.059 | 0.944 to 0.985 | no | higher | "Higher against the world than against the US market." |
| SPY 3Y | 0.952 to 1.076 | 0.942 to 1.015 | yes | about_the_same | about the same |
| ZM 5Y | 1.140 to 1.513 | 1.146 to 1.492 | yes | about_the_same | about the same |
| AAPL 10Y | 1.122 to 1.283 | 1.085 to 1.222 | yes | about_the_same | about the same |
| Europe (IEUR) rows, all five | | | no | lower | "Lower against Europe ..." |

"Higher" on SPY 5Y is correct under DV4.8: the intervals do not overlap. Every overlapping case reads "about the same".

**Other readings checked.** SPY 3Y Sharpe +1.12 with interval −0.01 to +2.26 reads "Could be noise" (owner rule). ZM 5Y alpha −16.89% reads "Could be noise" (tag noise) and the headline says "shows no reliable return beyond its exposures". ZM 5Y market beta 0.875 gives "moves less than the market (about 0.88 times as much)". No "no alpha" in any generated sentence (m3 is static help text).

---

## 3. What I verified, and how

**Runs.** First screens at 1440 x 900, console errors and failed requests captured with Playwright:

| URL | Page load / network idle | API time (cold) | Console | Result |
|---|---|---|---|---|
| `/?t=SPY&range=FULL` | 1.6 s / 3.0 s | 13.9 s (first report of the server) | none | all 13 panels render (`spy_full_1440.png`, `spy_full_full.png`) |
| `/?t=ZM&range=5Y` | 0.1 s / 1.0 s | 0.8 s | none | all panels render (`zm_5y_1440.png`) |
| `/?t=AAPL&range=10Y` | 1.0 s / 1.7 s | 1.2 s | none | all panels render (`aapl_10y_1440.png`) |
| `/?t=SPY&range=3Y&stats=1` | 0.9 s / 1.7 s | 0.2 s | none | t and 95% interval columns shown (`spy_3y_stats_1440.png`) |
| `/?t=ZZZZZZ` | 1.0 s / 2.3 s | 404 | only the two expected 404 resource lines | "No prices were returned for ZZZZZZ. Check the ticker symbol." (`bad_ticker_1440.png`) |
| `/?t=ASML.AS` | 1.0 s / 1.6 s | 422 | only the two expected 422 lines | "Only tickers quoted in US dollars are supported for now. ASML.AS is quoted in EUR." plus action (`asml_1440.png`) |
| `/` | 0.9 s / 1.5 s | none | none | "Type a ticker and press Factor it, for example SPY.", range controls disabled with a reason (`landing_1440.png`) |

No panel was blank or showed the panel-failed state on any of the four reports.

**Wording scan** over the full page text with every disclosure open (SPY Full, ZM 5Y with statistics on): no em dash, no "will", "expected", "likely", "driven by", "causes", no all-caps words, no Greek letters, no regression formula. Hits: "because ... your other exposures" (M4), "no alpha" (m3), "p = <0.001" (m4). "because" also appears in method text ("left out because ACWI has no usable return"; "computed because the residual quality gate fired"), which is not a causal claim about a beta. Sentence case holds.

**Design against v4a** (`shot_v4a_1440.png` against `spy_full_1440.png`): same rail, palette, header, facts strip, summary table layout and density. No hero headline, gradient, nested card or decorative shadow; the only radii of 12 px or more are the switch track and thumb and the radio inputs. Betas neutral (v4a still showed them green; the owner overrode that). Differences are M3, M5, m10 and the known items.

**Contrast**, every text colour on its actual background, computed from the DOM: lowest 5.44:1 (green `+0.52` on white, 15 px / 600), then red values 5.45:1, link teal 5.59:1, muted ink 5.87:1 and up; rail text 7.38:1 and up. All pass WCAG AA.

**Keyboard** (1440): Tab order is skip link, ticker combobox, Factor it, range radio group (one stop, arrows move), From and To date fields, Check for newer factor data, Show statistics switch, the 13 nav links, Download report. Every stop shows a 2 px outline or, for the switch, a ring on the track (`kbd_switch_focus_sidebar.png`). Space on the switch sets `aria-checked="true"` and adds `stats=1` to the URL; after reload it stays on and the tables have five columns. Enter on a "How this is computed" summary opens it. Enter on a nav link scrolls and moves focus to the panel heading. Scroll-spy sets `aria-current="location"` on the panel at the top (with m1 and the M5 jumps).

**390 px and the drawer**: no horizontal scroll at 390, 1024, 1440 or 1920 (`scrollWidth − clientWidth` = 0, also after scrolling every panel into view at 390). The menu button opens the drawer (`aria-expanded="true"`, focus moves to the ticker field, page behind is inert), Escape closes it and focus returns to the Menu button; choosing a nav item closes it and focuses the panel heading (`spy_full_390.png`, `spy_390_drawer_open.png`, `spy_full_390_full.png`).

**Reduced motion**: with `prefers-reduced-motion: reduce` no element has a transition or animation and scrolling is instant; without it only the switch thumb (0.16 s) and nav links (0.15 s) transition.

**Robustness**: 5Y then 3Y, then Back gives `range=5Y` with 5Y checked and period 1 Oct 2021 to 30 Sep 2026; Back again gives Full (1 Feb 1993); Forward gives 5Y again. Six range clicks 60 ms apart (3Y, 5Y, 10Y, Full, 3Y, 10Y) end on 10Y in the URL, the control and the analysis period (3 Oct 2016), with no stale report (`rapid_range_final.png`). ZM: 10Y radio disabled, reason "10Y needs prices from 1 Oct 2016, but the history starts 22 Apr 2019. Full history covers all of it." (`zm_sidebar_10y_disabled.png`). Download report links to `/api/report/SPY/html?range=10Y` (same range), returns 200 `text/html`, `attachment; filename="SPY_report.html"`, 429,360 bytes, title "SPY factor profile".

---

## 4. Gates (run by me in this worktree)

| Gate | Result |
|---|---|
| `uv run pytest -q` | 1,086 passed, 227 deselected, 1 warning (Starlette httpx deprecation), 129.6 s |
| `uv run ruff check backend` | All checks passed |
| `uv run ruff format --check backend` | 119 files already formatted |
| `uv run pyright` | 0 errors, 0 warnings, 0 informations |
| `npm run typecheck` | no errors |
| `npm run lint` | no problems |
| `npm test` | 40 files, 614 tests passed |
| `npm run size` | within budget: 396.3 kB raw / 123.8 kB gzip against 400 / 125 (see m11) |
| `npm run e2e` | 1 passed (dashboard smoke on the fake backend) |
