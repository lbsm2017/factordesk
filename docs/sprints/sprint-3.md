# Sprint 3: USD/EUR reference currency, energy factors, carry-over

Dates: planned 2026-11-21; run on the night of 2026-11-20 to 05:00 on 2026-11-21 at the owner's request
Status: closed. Release `v0.4.0` (pending the owner's merge of the release PR). Approved by the owner on 2026-11-20.
Previous: [Sprint 2](sprint-2.md). Backlog: [Sprint 2 backlog](sprint-2-backlog.md). Method notes: [reference currency](../research/reference-currency-and-benchmarks.md).
Release target: `v0.4.0`.
## Context

Sprint 2 shipped v0.3.0: the portfolio composer and the macro section. The owner set Sprint 3 as follows (2026-11-20):

- **Headline: USD and EUR reference currency, platform-wide.** The owner picked this over "portfolio depth" as the goal. The method notes are ready in `docs/research/reference-currency-and-benchmarks.md`.
- **Energy factors:** Brent oil, Henry Hub natural gas, CO2 carbon credits (KRBN). European gas (TTF) comes later, with the EUR work.
- **Carry-over items planned for Sprint 3:**
  - holdings table;
  - tail-risk fixes;
  - CSV import/export;
  - tail risk v2;
  - hygiene.

  Settings, per-holding CVaR, the factor families view and FF6 for the FF5-only sections move to the backlog.

## Recap: what changes for the user

1. A **USD | EUR switch** works for every report: ticker, uploaded track record and portfolio. In EUR:
   - returns and factors are in EUR;
   - cash earns the EUR rate;
   - USD bonds are hedged to EUR.
2. A new **Energy & carbon** section shows the subject's sensitivity to oil, gas and carbon prices, controlled for the market.
3. Portfolio users see a **holdings table**: each holding's contribution to return and its share of risk, rolled up through the tree.
4. **Tail risk is fixed:**
   - consistent n/a values;
   - a Cornish-Fisher "indicative" warning;
   - the correct day count.
   - Stretch: a compact layout and a daily/monthly/quarterly horizon switch.

## Sprint plan: Sprint 3

**Dates:** 2026-11-21, one day. **Team:** at most 6 agent slots, a coordinator on Opus, and the owner, who approves the checkpoint and the demo.

**Sprint goal:** a user can switch any report between USD and EUR, with correct cash, hedged bonds and factors in EUR, and can see a portfolio's exposure to oil, gas and carbon.

### Capacity
| Resource | Available | Allocation | Notes |
|---|---|---|---|
| Agent slots | 6 × about 6 h | about 36 pts (1 pt ≈ 1 agent-hour) | Sonnet implements. Opus reviews the statistics and currency maths only. |
| Owner | 2 touchpoints | — | One checkpoint and the demo sign-off |
| **Committed (P0 + P1)** | | **29 pts, about 81%** | Above the 70–80% guide. The cut order below protects the goal. |
| Stretch (P2) | | 9 pts | |

### Sprint backlog
| Pri | Item | Pts | Model | Depends on |
|---|---|---|---|---|
| P0 | **S3-0 Checkpoint pack.** <br>• A currency formula sheet.<br>• A hedge table per library line.<br>• Mockups of the USD/EUR switch, the holdings table and the compact tail panel.<br>**The owner approves all of this before any build.** | 2 | coordinator + Sonnet | — |
| P0 | **S3-1 Rates and FX data.**<br>• EUR/USD from FRED `DEXUSEU` (from 1999), using the existing `data/fred.py`. *(Superseded on 2026-11-20 by the owner: ECB euro reference rates first, FRED H.10 as fallback, for 10 currencies.)*<br>• The EUR overnight rate: €STR from the ECB Data Portal, with EONIA before Oct 2019.<br>• A compounded EUR cash index.<br>• Daily cache and a source credit. If a source is down, the report shows a notice and does not wait or fail. | 3 | Sonnet; Opus review | — |
| P0 | **S3-2 Currency engine.**<br>• `fx_convert`.<br>• A synthetic hedge: `R_local + (r_ref − r_local)·days/360`, using the previous day's rates.<br>• When the reference currency is USD, the engine changes nothing. | 3 | Sonnet; Opus review | S3-1 |
| P0 | **S3-3 Factors in EUR.**<br>• Market: `(1+Mkt_usd)(1+f) − 1 − RF_eur`.<br>• Long-short factors: `(r_L − r_S)(1+f)`.<br>• RF becomes the EUR rate.<br>• This covers CAPM, FF3, FF5 and FF6, daily and monthly. | 2 | Sonnet; Opus review | S3-2 |
| P0 | **S3-4 Subjects in EUR.**<br>• Tickers: USD-listed and EUR-listed tickers (Yahoo currency EUR) are accepted in both views. Other currencies are still refused.<br>• Portfolios: each sleeve is converted. Cash lines use the EUR rate. USD bond lines are hedged as the S3-0 table says.<br>• Uploads: the user declares the record's currency (USD or EUR) and it is converted.<br>• Cache keys include the currency. | 4 | Sonnet; Opus review | S3-2 |
| P0 | **S3-5 Currency UI.**<br>• A USD/EUR switch in the sidebar, plus a `ccy=EUR` URL parameter.<br>• Every figure shows its currency.<br>• A "hedged to EUR" badge in the composer.<br>• Macro and Energy are hidden in the EUR view until S3-9 lands. | 3 | Sonnet | S3-0 |
| P0 | **S3-6 Energy spike.**<br>• Download Brent (FRED `DCOILBRENTEU`), Henry Hub (`DHHNGSP`) and KRBN.<br>• Measure correlations and VIFs, and test whether one-day lag terms matter.<br>• Measure how much the top 5 gas-spike days drive the gas beta.<br>• Run on SPY, XLE, XLU and the 60/40 portfolio. The numbers go to the owner. | 1 | Sonnet | — |
| P0 | **S3-7 Tail-risk fixes.**<br>• Cornish-Fisher: when VaR is n/a, CVaR is n/a too.<br>• An "indicative" flag when Cornish-Fisher is far from the historical figure.<br>• "Based on N days" counts the analysed window exactly. | 2 | Sonnet; Opus review | — |
| P1 | **S3-8 Energy & carbon section.** A new section and panel after Macro, available for every subject.<br>• Long model: market, OIL, GAS.<br>• Carbon model: market, OIL, GAS, CO2, from Aug 2020, labelled "short sample, mainly EU carbon". It is hidden when there are fewer than 2 years of data.<br>• VIFs, and the leg that limits the window.<br>• Also fix the macro correlation matrix, which is computed twice. | 4 | Sonnet; Opus review | S3-6 |
| P1 | **S3-9 Macro and energy in EUR.**<br>• Traded legs are converted.<br>• The dollar leg becomes the USD/EUR return.<br>• Oil and gas price legs stay as USD log changes.<br>• KRBN is converted to EUR, minus the EUR rate. | 2 | Sonnet; Opus review | S3-3, S3-8 |
| P1 | **S3-10 Holdings table (E6-lite).** Target weight, end weight, return contribution (Frongello) and risk share, built with `attribute` and `roll_up`. Group rows sum their leaves. | 3 | Sonnet; Opus review | S3-0 |
| P2 | **S3-11 Portfolio CSV import and export.** A lossless round trip. Bad rows are reported by CSV line number. | 2 | Sonnet | — |
| P2 | **S3-12 Tail risk v2.** The compact layout and a daily/monthly/quarterly horizon switch, using non-overlapping compounded returns with no square-root-of-time scaling. | 4 | Sonnet | S3-0, S3-7 |
| P2 | **S3-13 Hygiene.**<br>• A bundle budget enforced in CI.<br>• Upload messages: echoed cells capped at about 40 characters, CSV line numbers, and 400 for a missing file.<br>• The FF5 and Mom data stamps are compared.<br>• The verdict text gets the lean floor. | 3 | Haiku/Sonnet | — |

**Planned capacity:** 36 pts. **Sprint load:** 29 pts committed (81%), plus 9 pts stretch.

**Cut order:**
1. S3-13.
2. S3-12.
3. S3-11.
4. S3-10.
5. S3-9: Macro and Energy stay hidden in EUR.

The currency core (S3-1 to S3-5) is never cut.

**Moved to the backlog:**
- Settings module.
- Per-holding CVaR (E7b).
- Factor families view.
- FF6 for the FF5-only sections.
- CHF cash on SARON and GBP/JPY listings, including GBX/100.
- The Europe factor set (French Developed Europe).
- TTF gas.
- E2, E3, E8 and E9b.

### Design decisions (approved)

1. **The USD view is unchanged.**
   - The golden ticker test stays the same.
   - The `reference_currency` field appears only when the currency is not USD, so the schema stays "4".
2. **FX source.** FRED `DEXUSEU` (noon New York rate). It reuses the FRED client. Missing days carry the previous rate forward. The EUR view starts in 1999-01. *(Superseded on 2026-11-20: ECB euro reference rates first, FRED H.10 as fallback; a fixing carries at most 7 days.)*
3. **EUR rate.** €STR from Oct 2019. Before that, EONIA as it was published: the real overnight rate of the time, with no adjustment. Accrual uses ACT/360.
4. **Hedging in the EUR view.**
   - Bond lines with only USD underlying (US Treasuries, US investment grade, US high yield, TIPS, EMB) are hedged to EUR.
   - Multi-currency bond funds (IGOV, BNDW, PICB, IHY) stay unhedged and labelled.
   - Equities, alternatives and commodities stay unhedged.
   - The owner approves the line-by-line table at S3-0.
5. **Macro and energy.** Shock series (Brent, Henry Hub, the dollar index) are not converted. Traded legs are converted. For a EUR investor, the dollar leg is the USD/EUR return.
6. **Carbon proxy.** KRBN (owner choice), on its own shorter-window model.

### Lanes (at most 6 at once)
| Lane | Sequence |
|---|---|
| A data | S3-1 → S3-6 → S3-8 |
| B engine | S3-2 → S3-3 → S3-9 |
| C subjects | S3-10 backend (while S3-2 is in progress) → S3-4 |
| D frontend | S3-0 mockups → S3-5 → S3-10 UI → S3-11 |
| E tail risk and hygiene | S3-7 → S3-12 → S3-13 |
| F review (Opus) | S3-1, S3-2, S3-3, S3-4, S3-7, S3-8, S3-9, S3-10 |

Each lane works in a manual worktree, `../factordesk-wt/<lane>`, and merges directly into dev. Schema and generated types: rebase before each merge and regenerate the types. Never hand-merge them.

### Risks
| Risk | Impact | Mitigation |
|---|---|---|
| The ECB Data Portal API is down or changes format | No EUR rate | Fall back to FRED's €STR series after 2019. Soft fail with a notice, as with FRED today. |
| The currency change touches every subject | Silent errors in USD reports | Identity test with USD as reference, the golden ticker test, and Opus review of S3-2 to S3-4 |
| FX at noon New York against market-close prices | Noisy daily EUR returns | Monthly figures are not affected. A note on the daily figures. Validated against a EUR-listed fund. |
| KRBN has only 6 years, in one market regime | Unstable carbon beta | Its own model with a short-sample label and a 2-year minimum |
| Henry Hub spikes (2003, 2021) | Gas beta driven by a few days | The spike measures this; the label names it if it matters |
| 81% load and mid-sprint additions | Overrun | Scope frozen at approval. The cut order applies. |

### Definition of done
- [ ] All 4 CI checks exist and pass explicitly.
- [ ] Before each direct merge: backend tests, plus the frontend typecheck, lint and full unit tests.
- [ ] Opus review of every row marked for it, with findings fixed.
- [ ] The golden ticker test is unchanged. Floats are compared with a tolerance. Expected values come from data, not literals.
- [ ] Tests:
  - USD view = identity;
  - USD→EUR→USD round trip;
  - hedge with zero rate gap = local return;
  - the EUR long-short factor equals the USD one × (1+f);
  - group totals equal the sum of their leaves;
  - risk shares sum to 100%;
  - VIF reported for the energy legs.
- [ ] Wiki:
  - new pages "reference-currency" and "energy-and-carbon-factors";
  - an update to factor-models-and-macro.
- [ ] `docs/sprints/sprint-3.md` holds the plan, the result and the retro. The owner signs off on the demo screenshots. Then the dev→prod PR, which the owner merges, and the `v0.4.0` tag.
- [ ] Every brief ends with the footer: foreground tests only, stop your servers, one report.

### Key dates
| When | Event |
|---|---|
| 2026-11-21 start | S3-0 pack, S3-1, S3-6, S3-7 and S3-10 backend start |
| About 2 h in | **Owner checkpoint:** formula sheet, hedge table, mockups, plus the energy spike numbers for information |
| Midday | Check-in: EUR ticker report works end to end |
| End of day | Demo, release PR, `v0.4.0` |
| After | Retro in `docs/sprints/sprint-3.md` |

## Reused code
- `backend/factordesk/data/fred.py`: FRED client, with the day-long memory of failures and the 8 s timeout.
- `data/french.py` (`FrenchDataset`, `join_momentum`) and `analytics/sample.py` (`align_returns`, `build_subject_sample`).
- `analytics/subject.py` (`ReturnSubject`) and `pipeline.assemble_subject_report`.
- `api/portfolio_report.py`: its data layer compounds RF across gaps, and that compounding is reused for EUR cash.
- `analytics/backtest.py`, `analytics/portfolio_attribution.py` (`attribute`, `roll_up`).
- The macro analytics module and its section hook: the pattern for the energy section (HookSpec, limiting leg, VIF).
- `data/asset_class_library.json`: add a `hedge_eur` flag per line.
- Frontend: the mode switch markup in the sidebar, the composer, MacroPanel and TailRiskPanel.

## Verification
- **Backend:** pytest with the new currency, energy and holdings tests.
- **Frontend:** typecheck, lint, Vitest, and e2e, including a new e2e that switches to EUR on the fake backend.
- **Localhost demo on real data:**
  - SPY in EUR against SXR8.DE (an S&P 500 UCITS fund listed in EUR): monthly correlation above 0.99, and an annual return gap below about 0.5%.
  - 60/40 in EUR with IEF hedged, against the same portfolio in USD: the gap should track the EUR−USD rate differential.
  - The EUR cash index for 2023: about 3.3%.
  - Energy panel: XLE with a clearly positive oil beta, XLU with gas and carbon sensitivity, SPY with betas close to 0.
  - The Balanced SAA holdings table: group totals tie out.
- The owner gets the screenshots before the release PR.

## What shipped

| Item | What |
|---|---|
| S3-0 Checkpoint pack | Mockups of the currency switch, holdings table and compact tail panel ([docs/design/sprint-3](../design/sprint-3/)). The coordinator approved them and the hedge table, because the owner asked the sprint to run without waiting. |
| S3-1 Rates and FX | ECB euro reference rates for 10 currencies from 1999, with FRED H.10 as fallback. The EUR overnight rate is €STR from October 2019 and EONIA before that, with a compounded ACT/360 cash index. An outage is remembered for the whole host for the day, and a fixing carries at most 7 days. |
| S3-2 to S3-4 Currency engine | Every subject (ticker, upload, portfolio) can be shown in EUR. Each asset is converted daily before weighting. USD-only bond lines are hedged as R − RF + c_eur on the local return, the EUR cash line earns the euro rate, and unallocated weight is held as EUR cash. Factors are converted to EUR. Listings in the major currencies are accepted, with GBp divided by 100. The price audit runs on the prices as listed. The USD view is byte-identical. |
| S3-5 Currency UI | USD / EUR switch (URL `ccy=EUR` and remembered), a "Figures in EUR" pill, currency codes on key figures, hedge badges in the composer, the record currency on uploads, and source credits. |
| S3-6 and S3-8 Energy & carbon | A spike ([note](../research/energy-factor-spike.md)), then a new section with market + Brent + Henry Hub, and a carbon model (KRBN, from Aug 2020, 2-year minimum). It shows VIF, a gas robustness fit without the 5 largest gas moves, and soft fail. The macro correlation is computed once. |
| S3-7 Tail-risk fixes | Cornish-Fisher CVaR is n/a when its VaR is n/a. A "far from historical" flag scales with volatility. "Based on N" counts the analysed sample. |
| S3-9 Macro and energy in EUR | Traded legs are converted. The dollar leg is the USD/EUR return. Oil and gas stay as USD log changes. |
| S3-10 Holdings table | Target, end, return contribution and risk share, rolled up through the tree on exactly the analysed days. It is a plain accessible table. |
| S3-11 Portfolio CSV | Export and import with a lossless round trip, line-numbered errors, and no silent overwrite. |
| S3-12 Tail risk v2 | Compact layout and a daily / monthly / quarterly switch on whole calendar periods, with no square-root-of-time scaling. |
| S3-13 Hygiene | A bundle budget enforced in CI (503 kB of a 540 kB budget). Upload messages capped and line-numbered, and a missing file returns 400. A notice when the FF5 and Mom stamps differ. The lean floor in the verdict. |
| Owner request | The Backtest card drops "Ends when", and rows that would say only "None". |

## Owner decisions during the sprint (2026-11-20)

- The reference currency became the headline instead of portfolio depth. The carbon proxy is KRBN. TTF gas comes later.
- Portfolio performance is in the chosen currency, with each asset converted daily at its own rate, for all major listing currencies.
- FX comes from the ECB first.
- The sprint runs in auto mode to 05:00. The coordinator approves the checkpoint.
- The Backtest card filler rows were removed.

## Validation (real data, 2026-11-20)

All 7 checks pass ([note](../research/sprint-3-validation.md), [script](../../scripts/validate_sprint3.py)):

- SPY in EUR against SXR8.DE: quarterly correlation 0.990 and a return gap of +0.30%/yr. Monthly is 0.972, because of close-time differences.
- Hedged IEF in EUR tracks IEF + (c_eur − RF) to 0 bp. EUR cash in 2023 is 3.28%.
- XLE's oil sensitivity is +0.21 (t 5.7). XLU shows no gas or carbon sensitivity at daily frequency.
- Balanced SAA holdings tie out in USD and EUR.
- The SPY USD regression is identical to v0.3.0.
- Tail risk computes on every horizon.

Localhost demo screenshots were reviewed. The demo found a false price-audit error in the EUR view, garbled credits, small-beta axes and repeated tickers. All of them were fixed before release.

## Retro

**Went well**

- Seven independent Opus reviews caught real defects before merge:
  - a stale cache gave silent 0% FX returns;
  - the "far from historical" flag misfired on low-volatility subjects;
  - the holdings window counted excluded days;
  - the treegrid had no keyboard model;
  - the hedge was applied to returns already converted to EUR.
- Real-data validation confirmed the hedge bug independently and measured the fix.
- The mockup-first checkpoint again gave builds that matched the design.

**Problems and fixes**

| Problem | Fix |
|---|---|
| Five lanes running full suites overloaded the PC (runs of 10–40 min) | Lanes run targeted tests plus the style and token tests (`src/test`). The full suites run in CI after merge. |
| Each push to dev cancelled the running CI, so no run completed for a while | Batch merges near the end, and confirm one green run before the release. |
| CI caught a format slip and a 13 px font that targeted tests missed | Briefs include `ruff format --check backend` and `vitest run src/test`. |
| A known review nit (audit on converted prices) turned out to be a release blocker on real data | Run the real-data demo before deciding to defer a review finding. |
| Agents linked worktrees to the main checkout's packages | Remove links before deleting a worktree. Briefs ask for `npm ci` and `uv sync` in the worktree. |

**Backlog from this sprint**

- The ranges endpoint ignores `ccy`.
- The dollar-lag term in EUR (owner question: a lead term?).
- CHF cash on SARON.
- TTF gas.
- The Europe factor set.
- Dark theme (no dark styles exist yet).
- The "What EUR changes" side panel from the mockup.
- Settings module, per-holding CVaR, factor families and FF6 for the FF5-only sections, carried from the plan.
