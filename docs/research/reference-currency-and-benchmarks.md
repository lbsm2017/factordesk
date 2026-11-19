# Reference currency and benchmark proxies: method notes

Date: 2026-11-20
Status: research input for a later reference-currency epic. Version 1 stays USD only.

This note records how factordesk will support a **USD or EUR reference currency** across the whole platform: portfolios, factors and analysis. It also records how benchmark proxies for the SAA library are chosen. The source was an owner-supplied benchmark-mapping study, which is not in the repository. Every ticker and series must be verified with the app's own data code before use.

## 1. Principle: one reference currency per analysis

factordesk regresses **one** return series on factor returns, so every sleeve of a portfolio must be expressed in the analysis's reference currency. Sleeves are never mixed in their native currencies.

| Rule | USD reference | EUR reference |
|---|---|---|
| Cash | Overnight rate of the cash currency, converted to USD (EUR cash: €STR plus EUR/USD) | Same idea, converted to EUR |
| Bonds | Hedged to USD (planned). Version 1 uses unhedged US-listed funds and labels them. | Hedged to EUR |
| Single-currency equity markets (Japan, Switzerland, UK) | Local return converted to USD, or a US-listed fund | Local return converted to EUR |
| Multi-currency equity regions (EM, Pacific, Global) | USD, unhedged | EUR, unhedged |
| Alternatives, real estate, commodities | Converted to USD (mostly USD already) | Converted to EUR |

## 2. Formulas

- **Unhedged conversion:** `R_ref(t) = (1 + R_local(t)) · S(t)/S(t−1) − 1`, where `S` is the price of one unit of local currency in the reference currency. Reference FX comes from the ECB or FRED.
- **Synthetic hedge** (rolling one-month hedge, cross-currency basis ignored):
  - `R_hedged(t) = R_local(t) + (r_ref(t−1) − r_local(t−1)) · days(t)/360`;
  - the overnight rates are €STR (EUR), SOFR (USD) and SARON (CHF), on an ACT/360 basis;
  - monthly frequency is recommended.
- **Cash index:** compound the daily overnight rate into a total-return index.

## 3. Data sources an open-source tool may fetch at runtime

Never bundle any of this data. The user's machine fetches it, with credit.

| Use | Source | Terms (to confirm before use) |
|---|---|---|
| USD rates | FRED SOFR, DTB3; Ken French RF (in use) | Public FRED series; French academic citation |
| EUR rates, FX | ECB Data Portal (€STR, EXR reference rates) | Free with attribution |
| CHF rates | SNB data portal (SARON) | Free with attribution |
| Prices of listed funds | Yahoo via the existing provider (in use) | Personal or internal use |
| Commodity spot (monthly) | World Bank Pink Sheet | CC BY 4.0 |
| Property prices (quarterly) | BIS | Free with attribution |

**Not usable in an open-source tool:**
- the public MSCI index endpoint, because its terms bar extraction and products;
- ICE BofA series on FRED, which are internal use only and limited to the last 3 years;
- HFR and SG indices;
- the Cliffwater Direct Lending Index, which needs consent;
- CCi30;
- Coin Metrics data, which is CC BY-NC (non-commercial).

## 4. Lines without a daily proxy

The free sources for private equity, venture capital, private credit, hedge funds and direct real estate are quarterly appraisal series: Cambridge Associates summaries, Cliffwater, NCREIF. They lag by months and are smoothed. They cannot enter a daily backtest. A later quarterly path would need to:

- store each series raw and desmoothed (Geltner AR(1) or Getmansky-Lo-Makarov);
- never interpolate silently;
- run beside the daily listed proxies, not in place of them.

## 5. Decisions recorded (owner, 2026-11-20)

- Version 1 stays USD only. A USD or EUR reference currency comes later for the whole platform.
- Library updates for version 1:
  - Crypto: BTC-USD.
  - Global commodities ex-precious: DBC, noted as including a small precious weight.
  - Private credit: BKLN.
  - Generic inflation-linked bonds: TIP.
- European and global non-USD bonds stay **unhedged** in version 1 and are labelled. Hedging arrives with the reference-currency epic.
- The library keeps its 44 lines. Extra lines from the study (Equity Japan, Equity Pacific, EM ex China, HKD and other cash) wait for taxonomy work alongside the currency epic.

## 6. Work the reference-currency epic will need

1. A rates module: SOFR, €STR (spliced with EONIA before October 2019) and SARON, compounded into cash indices.
2. An FX module: ECB EXR and FRED DEX series.
3. Conversion and hedging for each sleeve, as in sections 1 and 2.
4. Local listings (`.DE`, `.L`, `.SW`, `.T`, `.HK`). LSE prices quoted in GBX must be divided by 100.
5. The currency check applied per reference currency, replacing today's USD-only refusal.
6. Factors in EUR. The market factor and the risk-free rate change with the reference currency. Long-short factor returns change much less, but should still be converted.
