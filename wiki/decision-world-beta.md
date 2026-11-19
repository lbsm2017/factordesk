# Decision: a quick world beta against the ACWI ETF

Date: 2026-11-18
Status: Decided-pending-implementation (built on branch `feat/world-beta`; stays here until the independent validation of `docs/validation/world-beta-handoff-2026-11-18.md` has passed)

## In one sentence

We will show, next to the US market beta, a quick beta against the world, measured against the iShares MSCI ACWI ETF (ticker `ACWI`) as a stand-in for the MSCI ACWI index, and say plainly that it is a stand-in and a quick estimate.

## What we decided

- Owner request, 2026-11-18: "add a quick beta estimate against the MSCI All Country World index (or use ACWI)". We use the ETF.
- The beta is the slope of a regression of the stock's daily excess return (return minus the US risk-free rate of the Fama-French file) on ACWI's daily excess return, with an intercept, on the days the analysed sample and ACWI share. The standard error is the report's existing Newey-West (HAC) error. We report the beta, its 95% interval, R squared, the correlation, the number of days, the dates, and (secondary) the alpha a year with its HAC t.
- Beside it, the beta of the same days against the US market factor (Mkt-RF), so the reader compares two betas on identical days. A plain sentence says "about the same" when the two 95% intervals overlap, and otherwise "higher" or "lower against the world". It says nothing more.
- ACWI prices follow the same rules as the stock's: Adj Close, the same normaliser, the same audit. If the audit finds errors in ACWI data the section is `failed` with a reason. If ACWI cannot be fetched and nothing is cached the section is `failed` with "The world fund's prices could not be fetched." and the rest of the report is built as usual. If the refresh fails but a cache exists, the section is built from the cache and says "ACWI data ends <date>".
- Owner instruction, 2026-11-18: ACWI is cached and brought up to date on every ticker load. The first load downloads the full history (it starts in March 2008). After that, each report build asks only for the days after the last cached date (with a few days of overlap to check that Yahoo did not rewrite the history), merges them, and makes no network call when the cache already holds the latest completed trading day.
- A short history gives a wide interval, and fewer than 252 shared days gives no number (`insufficient_data`).
- The section appears in the static report as "World beta (quick estimate)", after the headline strip and before the price chart (position 350, as the dashboard spec places it; first built at 540, after the panels that qualify the Exposures betas). The React panel is only a placeholder for now.

## Why

A US investor often asks how a stock moves with the world and not only with the US market. The US market beta already comes with the five-factor regression. A second beta on the same days answers the question with one more regression and no new model.

**Why the ETF and not the index.** The MSCI ACWI index has no free daily data source. MSCI publishes index levels on its own site, with licence terms we have not checked, and Yahoo does not serve them. The iShares MSCI ACWI ETF tracks that index, is quoted in US dollars on a US exchange, and has free daily history from March 2008 on Yahoo (the first row we downloaded is 2008-03-28). It is priced at the same US close as US stocks, which keeps the days aligned with the Fama-French file. The cost is that the ETF is not the index: it has fees, tracking error and creation-redemption effects that we have not measured. The panel says so.

## What was rejected

- **MSCI index data.** No free daily source; a paid or licensed feed breaks the "open source, no data in the repository" rule ([decision](decision-no-data-and-no-secrets-in-the-repo.md)).
- **A global factor model** (a Fama-French global or world-ex-US factor set, or a world market factor, in place of or next to the US factors). It is a different product: another data source, another set of definitions, and a decision about currency. The owner asked for a quick estimate. The proposed European mode already shows what that involves: regional factor files and a currency decision ([decision](decision-european-mode-and-currency.md)).
- **A Dimson (lead-lag) correction** inside this quick estimate. Much of ACWI trades in markets that close before the US, so same-day co-movement with a US stock can be understated. The lead-lag feature exists as its own section for the five factors. Adding leads and lags here would turn one number into three and invite reading a sum as the answer. We say "a quick estimate, not a full model" and leave the effect uncorrected.
- **Showing the beta without the US comparison.** One beta alone invites reading 0.9 as "less risky than the market" when the US beta on the same days may be 0.97.
- **Fetching ACWI once a day and caching the outcome.** A failed fetch in the morning would then hide the section until the next day. The refresh runs on every report build; it is free when the cache is current.

## How it works

- Benchmark return on date t: `P_t / P_{t-1} - 1` from Adj Close, where `P_{t-1}` is the previous row of the ACWI history. A return is used only when the ACWI previous date equals the stock's previous date, so both returns span the same interval. A day that ACWI lacks removes that day and the next one (the next return would span two days). The count of removed days is in the section.
- Excess benchmark return: ACWI return minus RF of the factor file on the same date.
- The incremental refresh compares the overlap rows (`adj_close` and `close`, relative tolerance 1e-6) with the cache. If they differ, a dividend or split rewrote the adjusted history, and the whole history is downloaded again instead of appending to a different base.
- Real numbers (2026-11-19, factor file to 2026-09-30, ACWI to 2026-11-17): SPY beta against ACWI 0.945 (interval 0.922 to 0.968, R squared 0.930) over 4,656 days since 2008-03-31, against the US market 0.975 on the same days: about the same. ZM 0.761 (0.359 to 1.163, R squared 0.068) over 1,872 days: wide, as a short history gives. EFA 1.028 (1.000 to 1.056, R squared 0.906) against the world and 0.954 (0.905 to 1.002, R squared 0.776) against the US market: about the same, the intervals touching at 1.00.
- SPY's beta against ACWI is a little below 1, not above. The reason is arithmetic: SPY's daily volatility over those days is slightly below ACWI's (the correlation is 0.964, and beta equals the correlation times the ratio of the two volatilities).

## What it costs us

- One more download per run in the worst case (the first run: the full ACWI history, about 4,700 rows), then a few rows per day.
- A beta against an ETF, not the index. Fund fees and tracking error are in it.
- The same-day beta of a US stock against a global fund is biased toward zero by the timing difference. We do not correct for it, and the panel says so.
- A sixth optional section needs small edits in shared files; they are listed in `docs/validation/world-beta-contract-note-2026-11-18.md` for the owner.
- Yahoo can rewrite the whole adjusted history; the overlap check handles dividends and splits but one more kind of change in the vendor's data is possible (see the handoff, open questions).

## What would change our mind

A free daily source for the MSCI ACWI index with a clear licence: then we use the index. Evidence that the ETF differs from the index by more than a few basis points of daily tracking error. Readers taking the world beta as a statement about the future or as a risk rating: then we fold it behind the Exposures panel. A validation finding in the hand-off checks.

## Sources

- [docs/validation/world-beta-handoff-2026-11-18.md](../docs/validation/world-beta-handoff-2026-11-18.md): definitions, tests, live numbers, and what the validator recomputes.
- [docs/validation/world-beta-contract-note-2026-11-18.md](../docs/validation/world-beta-contract-note-2026-11-18.md): how the sixth section fits the contract.
- [docs/specs/schema-v3-contract.md](../docs/specs/schema-v3-contract.md): where the section plugs into the report.
- [docs/methodology.md](../docs/methodology.md): M0.5 (HAC lags and the normal interval), M1 (price rules), M2 (the analysis sample).
- Yahoo Finance daily history for `ACWI`, first row 2008-03-28 (downloaded 2026-11-19).

## Related decisions

- [Daily returns with robust errors](decision-daily-returns-and-robust-errors.md)
- [Prices from Yahoo, with adjusted-close care](decision-prices-from-yahoo-with-adjusted-close-care.md)
- [No data and no secrets in the repository](decision-no-data-and-no-secrets-in-the-repo.md)
- [One contract for the five new report sections](decision-schema-v3-contract.md)
- [European mode and currency](decision-european-mode-and-currency.md)
- [Independent validation and mutation testing](decision-independent-validation-and-mutation-testing.md)

## Research notes

- [Prior art review, 2026-11-18](prior-art-review-2026-11-18.md): what we learned from other open-source factor and portfolio tools, and the bugs we avoid.
- [Dataset cards](../docs/datasets.md): verified facts about each Ken French file.

## Change log

- [Change log](log.md): dated changes to this knowledge base, newest first.

## Update 2026-11-19: after the independent validation

The validator recomputed every number from the definitions and agreed (verdict: merge with conditions). What changed, in plain words:

- **Names now follow the dashboard spec.** The proxy field is `proxy`; the fits use `se`, `ci_low`, `ci_high`; the comparison is `about_the_same`, `higher` or `lower`; the failed reason is "The world fund's prices could not be fetched."; the panel sits at position 350. The full list of renames is in section 9 of the hand-off. The nested shape (`world` and `us_market`) stays and is proposed to the owner as the amendment to the spec, because it carries R squared and correlation for both fits.
- **A failing refresh no longer slows the report.** When an ACWI cache exists, the refresh tries once, with a short timeout, and uses the cache if that fails. It does not wait through retries or a `Retry-After` header. Only a first-ever download keeps the retry policy.
- **Late dividends are caught.** The refresh starts at the last cached dividend date, the overlap check also compares the dividend columns, and the whole history is downloaded again when the last whole download is more than 30 days old. The date of the last whole download is stored in the cache file.
- **An exact fit has no alpha t.** It was a ratio of two rounding errors; it is now `null`, as documented.
- **One bad ACWI row far from the stock's days no longer removes the section.** Only audit errors dated inside the days the beta uses fail it; others become a note.
- **The wording "many non-US stocks" stays.** The validator found the MSCI ACWI factsheet of 30 October 2026 (United States 64.63% of the index), which makes "mostly non-US" false today.
- Still open for the owner: the amendment of the dashboard spec (nested shape, extra fields, how a non-fetch failure is shown), the caveat wording for the ETF's timing (F6), and the React placeholder body (F7).

## Update 2026-11-19: a Europe row

The owner asked for a Europe benchmark next to the world one. Same idea as before: there is no free daily MSCI Europe index, so the quick beta uses IEUR, the iShares Core MSCI Europe ETF (US dollars, US-listed, history from June 2014), as a stand-in.

- **Same machinery.** One list of proxies (ACWI and IEUR) drives one computation: the same regression, the same price audit, the same cache and the same refresh rules. Nothing was copied.
- **Each proxy stands alone.** The Europe result sits in its own block with its own status and reason. If IEUR fails, the world beta is shown as before; if ACWI fails, the Europe row can still show. The section status stays that of ACWI.
- **Fewer days.** IEUR starts in June 2014, so for a long analysis the Europe row covers fewer days than the world row. When the days differ, the panel shows a second US-market beta on the Europe days, so every comparison is like for like.
- **Two small changes in the same piece of work.** The static panel now sits right after Factor exposures (position 505), and the static header writes the company line as a sentence ("Listed on NYSE Arca, priced in US dollars").
- Details, field names and live numbers: section 10 of `docs/validation/world-beta-handoff-2026-11-18.md`.
