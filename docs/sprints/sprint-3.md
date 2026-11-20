# Sprint 3: USD/EUR reference currency, energy factors, carry-over

Dates: 2026-11-21 (one day)
Status: approved by the owner on 2026-11-20. Scope is frozen. New requests go to the next backlog.
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
| P0 | **S3-1 Rates and FX data.**<br>• EUR/USD from FRED `DEXUSEU` (from 1999), using the existing `data/fred.py`.<br>• The EUR overnight rate: €STR from the ECB Data Portal, with EONIA before Oct 2019.<br>• A compounded EUR cash index.<br>• Daily cache and a source credit. If a source is down, the report shows a notice and does not wait or fail. | 3 | Sonnet; Opus review | — |
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
2. **FX source.** FRED `DEXUSEU` (noon New York rate). It reuses the FRED client. Missing days carry the previous rate forward. The EUR view starts in 1999-01.
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

