# TTF gas data check (S4-11)

Date: 2026-11-20. Sprint 4, item S4-11. Research only: nothing is built and no app code changed.
Question: is there a free source of daily (or at least monthly) European TTF natural gas prices that the tool can download at run time, under terms that fit an open-source MIT tool that does not redistribute data?

## Recommendation

**Build, in a small later item (about 2 points, Sprint 5 or later; it is below the Sprint 4 cut line).** Use one source only: Yahoo `TTF=F`, read through the existing `YFinanceProvider` like KRBN and DBC. It is the only free source that gives daily data, it is current to the day before, and it adds no new download path, no new dependency and no new licence question. It starts in October 2017, so the TTF leg has about nine years, and monthly subjects get about 100 months by compounding the daily series.

Do not build a fallback from the World Bank or the IMF. They are monthly, one to three weeks late, ship as Excel files with unstable URLs, and the IMF terms forbid automated bulk download without permission.

Conditions for the build ticket:

1. **Guard the roll.** The series is a continuous front-month future, and it has at least one false step (2019-09-30: 11.94 to 16.39, +37% in one day, which is a contract change and not a market move). Use the same treatment as the Henry Hub leg: show the beta with and without the largest days, and note the 2019-09-30 row.
2. **Currency.** The price is in EUR/MWh. Brent and Henry Hub are never converted, so decide once whether the TTF log return is also left alone (the EUR view then needs no conversion) or converted in the USD view.
3. **Soft failure.** If Yahoo is down, the section says "TTF unavailable" and the other legs still run, as for the dollar index.
4. **Repeat the check before the build.** Yahoo can change or withdraw a symbol without notice.

## Sources checked

All live checks were made on 2026-11-20 with plain HTTP requests or the project's own libraries.

| Source | What it is | Frequency | History start | Update lag | Licence for an MIT tool that downloads at run time and does not redistribute | Reliability | Verdict |
|---|---|---|---|---|---|---|---|
| **Yahoo `TTF=F`** (yfinance) | NYMEX "Dutch TTF Natural Gas Calendar Month" future, continuous front month, EUR/MWh | Daily | 2017-10-23 (2,284 rows; last row 2026-11-19) | 1 day | Yahoo's terms govern the data (personal use; the yfinance README says to check them). Same position as every price the tool already reads from Yahoo. No redistribution needed | Unofficial API, no guarantee. Works today (HTTP 200, no key). 85 weekdays missing in 9 years; 20% of days have zero volume; 19 repeated closes; one false roll step (2019-09-30). Other symbols tried (`TFAF.NYM`, `TTF1!`) do not exist | **Use** |
| **World Bank Pink Sheet**, "Natural gas, Europe" | Monthly average, USD/mmbtu. TTF from April 2015; April 2010 to March 2015 import border price plus spot; older periods differ again | Monthly | 1960 (TTF only from 2015-04, about 137 months) | About 3 days (the October 2026 value came out on 2026-11-03; next release 2026-12-02) | World Bank datasets default to CC BY 4.0 (attribution, state changes). The Pink Sheet page does not say so itself, and the gas series come from Bloomberg and World Gas Intelligence, so the licence is not confirmed for this file | One Excel file. The file URL carries a hash that changes at each release, so it cannot be hard-coded. Reading it needs an Excel reader (`openpyxl` is not a project dependency). From 2017-10 its monthly changes match the Yahoo series (108 months, correlation of log changes 0.996) | Backup at most. **Do not build** |
| **FRED `PNGASEUUSDM`** (IMF "Global price of Natural gas, EU") | Monthly average, USD/mmbtu | Monthly | 1992-01 (a third party says the early years are an older German border price, not TTF; FRED does not say) | About 3 weeks (September 2026 was posted 2026-10-22) | FRED page: "Copyright 2016, International Monetary Fund. Reprinted with permission". IMF terms: free reuse with attribution, commercial reuse needs permission, and bulk automated download is prohibited without written permission | FRED CSV works without a key (HTTP 200) and the tool already uses FRED. The IMF's own file answered a scripted request with HTTP 403 | **Do not build** (terms, lag, mixed definition) |
| **EIA** | US data. Only a US LNG export price to the Netherlands was found, which is not TTF | n/a | n/a | n/a | n/a | n/a | No TTF series |
| **ECB** (Data Portal) | No TTF or gas price series found in the search. The ECB publishes exchange rates, rates and HICP. Not checked series by series | n/a | n/a | n/a | n/a | n/a | No TTF series found |
| **Eurostat** | Retail gas prices for households and non-households, twice a year (`nrg_pc_202`, `nrg_pc_203`). No wholesale or TTF dataset found | Half-yearly | 2007 | Months | Eurostat reuse policy (free, with attribution) | Stable API, but wrong series | Not suitable |
| **ACER CHEST** (EU agency) | "Gas prices in EU, US and Asia", TTF from S&P Global, EUR/MWh | Monthly | 2019-01 | Months (last value 2026-01, page updated 2026-06-09) | None stated; the source is S&P Global, which is commercial | Web download of CSV or Excel; no documented API | Not suitable |
| **EEX** TTF Neutral Gas Price | Daily final price of EEX spot trades, EUR/MWh, as CSV | Daily | Only the last 60 days | Hours | Not stated on the page; a separate licensing page applies | Direct CSV links, but no history | Not suitable (no history) |
| **Stooq** | `ttf.f` | Daily | n/a | n/a | Not read | A scripted request returns a JavaScript challenge page, not data | Not usable |
| **Paid or keyed services** (OilPriceAPI, Commodities-API, Trading Economics, S&P Global, ICE Endex, CME, Cbonds) | TTF futures or spot | Daily or finer | Varies | Real time to days | Paid, keyed, or terms that forbid automated use or redistribution | Not tested | Not suitable |

## How the Yahoo series was checked

- `yfinance` `Ticker("TTF=F").history(period="max")`: 2,284 daily rows from 2017-10-23 to 2026-11-19, currency EUR, exchange NYM. Close ranges from 3.5 to 339 EUR/MWh.
- Daily log return: standard deviation 5.0%. 43 days with a move above 15%. Most sit in clear market events (2022-02-24 +41%, 2022-02-25 -35%, 2022-03 and 2023-06 spikes). The 2019-09-30 step (11.94 to 16.39) has no matching event: the price stays near 16 for days, so it is a contract roll or a bad bar.
- 85 weekdays have no row between the first and last date (holidays and gaps). Nothing is filled, as in the other legs.
- Against the World Bank monthly TTF series, the monthly mean of `TTF=F` has a level correlation of 0.997 and the monthly log changes 0.996 over 108 overlapping months (2017-10 to 2026-09). The two sources agree, so Yahoo's continuous series is a fair TTF proxy.

## Limits of this check

- Licence readings are from the sources' own pages and the yfinance README, not legal advice. The Pink Sheet licence for the gas series was not confirmed.
- ECB and Eurostat were checked by search, not series by series. A TTF series could exist that the search did not surface, but none of the usual indexes list one.
- The Yahoo symbol is a NYMEX-listed Dutch TTF contract, not the ICE Endex TTF benchmark. The two track each other (see the World Bank comparison), but volume on the NYMEX contract is thin.
