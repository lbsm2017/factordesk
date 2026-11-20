# Decision: USD or EUR reference currency

Date: 2026-11-20
Status: Decided-pending-implementation (Sprint 3)

## In one sentence

Every report (ticker, uploaded track record, portfolio) can be shown in US dollars or in euros: each asset's daily return is converted with its own exchange rate, cash earns the overnight rate of the chosen currency, USD-only bond lines are hedged in the euro view, and the factors are converted too.

## What we decided

- On 2026-11-20 the owner made the reference currency the headline of Sprint 3 ([sprint record](../docs/sprints/sprint-3.md)).
- On 2026-11-20 the owner set the rule that a portfolio's growth line and all its performance figures are in the chosen currency. Each single asset's daily return is converted with the appropriate exchange rate before weighting and rebalancing. Listings in the major currencies (EUR, USD, GBP, CHF, JPY, CAD, AUD, HKD, SEK, NOK, DKK) are accepted. London prices quoted in pence are divided by 100.
- On 2026-11-20 the owner chose ECB euro reference rates as the main exchange-rate source, with FRED H.10 as the fallback.
- On 2026-11-20 the coordinator set the hedge table below as the default. The owner asked for the sprint to run without waiting, so the owner can still override it.
- The US-dollar view stays exactly as before. The golden ticker report must not change, and the `reference_currency` field appears only when the currency is not USD.

## How it works

Notation:
- `f` is the return of the US dollar measured in euros over the period.
- `c_eur` is the euro cash return over the period: the overnight rate (€STR from 1 October 2019, EONIA as published before then), accrued as rate × calendar days / 360 and compounded across gaps.
- `RF` is the French one-month T-bill return for the period.

| What | Euro view |
|---|---|
| USD asset, unhedged | `(1 + R)(1 + f) − 1` |
| USD asset, hedged to EUR | `R − RF + c_eur`: the asset's return above dollar cash, plus euro cash |
| Asset in another currency | Converted through its own rate against the euro |
| Excess return of any subject | Return in euros minus `c_eur` |
| Market factor | `(1 + MktRF + RF)(1 + f) − 1 − c_eur` |
| Long-short factors (SMB, HML, RMW, CMA, Mom) | `X · (1 + f)` |
| Risk-free rate | `c_eur` |
| Macro and energy legs: spreads (TERM, DEF, INFL) | USD spread `X · (1 + f)` |
| Macro and energy legs: COMM, carbon (KRBN) | `(1 + R)(1 + f) − 1 − c_eur` |
| Macro dollar leg | `f` (the dollar measured in euros) instead of the Fed broad dollar index |
| Brent and Henry Hub changes | Not converted: log changes stay in US dollars |

The euro view starts in January 1999. Days without an ECB rate (euro-area bank holidays) carry the previous rate forward.

### Hedge table (euro view)

| Library line | Proxy | Euro view |
|---|---|---|
| EUR Cash | FXE | Replaced by the euro cash index |
| USD Cash, CHF Cash | RF, FXF | Unhedged: holding them is a currency position |
| N. American government, corporate investment grade and high yield bonds; EM bonds in USD; inflation-linked bonds | IEF, LQD, HYG, EMB, TIP | Hedged |
| European and global bond lines | IGOV, PICB, IHY, BNDW, GHYG | Unhedged, labelled "several currencies" |
| Equities, alternatives, real estate, commodities | all | Unhedged |

### Screen (mockups approved by the coordinator on 2026-11-20, [docs/design/sprint-3](../docs/design/sprint-3/))

- A USD | EUR switch sits under the mode switch in the sidebar. On phones the drawer holds it, with a small currency chip in the top bar. The URL parameter `ccy=EUR` overrides it.
- The report header shows "Figures in EUR". Only key figures carry the currency code.
- Composer rows show "hedged to EUR" on hedged lines and "not hedged: several currencies" on multi-currency bond funds.

## Why

- A euro investor's result depends on currency moves. Showing it in dollars hides them.
- Converting each asset before weighting is the only way a rebalanced portfolio's weights drift in the investor's currency.
- Hedging bonds is the usual practice for a euro investor, because unhedged dollar bonds carry mostly currency risk. Hedging equities is not usual.
- ECB rates are published every day, are based in euros and cover all the major currencies. The FRED H.10 rates are released weekly, so the latest days can be missing.

## What it costs us

- The ECB rate is fixed at 14:10 Frankfurt time, about 8 hours before the US close. Daily euro returns of US assets therefore carry some timing noise. Monthly figures are not affected.
- On 2026-11-20 the validation on real data ([results](../docs/research/sprint-3-validation.md)) found a monthly correlation of 0.972 between SPY in euros and SXR8.DE, a euro-listed S&P 500 fund. The cause is the difference in closing times: Xetra closes at 17:30 Frankfurt, New York later, and the ECB rate is fixed at 14:10, so a month-end can differ by about one day of US move. The correlation is 0.990 over quarters and 0.9996 over years, and the annual return gap is +0.30%. The earlier claim "Monthly figures are not affected" is superseded.
- The factors stay US factors, converted into euros. Regional factor files (see [European mode](decision-european-mode-and-currency.md)) remain a separate, later decision.
- CHF cash on SARON, and hedging for multi-currency bond funds, are not in scope.

## What would change our mind

- A validation gap: SPY converted to euros against SXR8.DE, a euro-listed S&P 500 fund, shows a monthly correlation below 0.99 or an annual return gap above about 0.5%.
- The owner flipping lines in the hedge table.

## Sources

- [Reference-currency method notes](../docs/research/reference-currency-and-benchmarks.md)
- [Sprint 3 record](../docs/sprints/sprint-3.md)
- Related: [European mode](decision-european-mode-and-currency.md), [USD-only v1 portfolios](decision-usd-only-v1-portfolios.md), [SAA tree and proxies](decision-saa-tree-and-proxies.md)

## Update, 2026-11-20 (Sprint 4): SARON, ranges and a dollar lead

- **Ranges honour the currency.** PR #36 (S4-1, open on 2026-11-20): the ranges endpoint takes `ccy`, and the cache key includes it. Before this change the preset day counts ignored the currency, so in the euro view they could exceed what the euro report could use when the exchange-rate series started later than the prices ([Sprint 4](../docs/sprints/sprint-4.md), "Recap" item 3).
- **CHF cash on SARON.** The cost "CHF cash on SARON is not in scope" above was true on 2026-11-20 for Sprint 3 and is superseded by PR #44 (S4-10, open on 2026-11-20). It moves the CHF Cash line from the FXF currency trust to the Swiss franc overnight rate (SARON) from the SNB data portal, in both views. The series is spliced: cube `zirepo` (item `H0`) is daily from 1999-06-21 but about a month late, and cube `snbgwdzid` (item `SARON`) is fresh but rounded to two decimals, so it fills the days after the last `zirepo` day. The index maths is the euro cash code (ACT/360, compounding across gaps). The franc return is converted unhedged. If the portal or the franc rate is down, the line keeps FXF with a notice. Hedging for multi-currency bond funds is still out of scope.
- **The dollar term needs a lead, not a lag.** On 2026-11-20 the spike in [dollar lag and lead](../docs/research/dollar-lag-lead-spike.md) (PR #41, merged at 5eb6c3d) measured the macro regression in the euro view for SPY, VGK, EFA, IEF and a 60/40 mix, 2007-01 to 2026-09. The one-day lag adds at most 0.3 bp of adjusted R-squared. The one-day lead adds 184, 115 and 105 bp for VGK, EFA and IEF (t = -15.2, -13.6, -8.2). The reading is close time: the ECB rate is fixed at about 14:10 CET and a US fund closes at 22:00 CET, so the last hours of the fund's day sit in the next day's dollar return. The lead is about three times smaller with a noon New York rate. The USD view, with the Fed index, shows a smaller lead of the same sign (VGK t = -5.8, IEF t = -4.9). The Xetra control EXSA.DE has a positive lead that this reading does not explain; the note says to repeat it after the Europe factor set.
- **Not built.** A lead is a negative shift, which [no look-ahead rule](decision-no-look-ahead-rule.md) forbids. On 2026-11-20 the note recommended a lead in the euro view only, and the decision is with the owner. Options: keep the rule and the lag; allow a lead that is labelled as using the next day's dollar move; or use a fixing nearer the US close. Until the owner decides, the euro view keeps the lag term described in [factor models and macro](decision-factor-models-and-macro.md).
