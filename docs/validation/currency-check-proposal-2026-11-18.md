# Currency check: proposed decision entry (roadmap N1)

Status: PROPOSAL, written 2026-11-18, for the owner to fold into `docs/methodology.md`.
Nothing in `docs/methodology*` was edited. This note stands in for the entry that M1.5 lacks (see
`docs/validation/spy-hardening-closure-2026-11-18.md`, row F13 and deferral D-4).

## What changes against M1.5

M1.5 says: for `currency != "USD"` raise the warning `currency_mismatch` and "v1 still computes".
On 2026-11-18 the owner decided otherwise: refuse a non-USD ticker until European factors exist.
The code now does that. Proposed text for M1.5, first bullet:

> A ticker whose Yahoo currency is known and is not USD is refused with
> `unsupported_currency` ("Only tickers quoted in US dollars are supported for now. {ticker} is
> quoted in {currency}."). No price history is downloaded and no report is built. A ticker whose
> currency is unknown is analysed; the caveat below says so.

The second bullet (non-US listing caveat) and the survivorship bullet stay as they are.

## The rule, as implemented

| Case | Result |
|---|---|
| Currency known and `USD` (any letter case, spaces ignored) | Analysed. |
| Currency known and anything else: `EUR`, `GBP`, `JPY`, and the pence quotes `GBp` and `GBX` | Refused. Pence are not US dollars, so they take the same path as every other currency. |
| Currency unknown (Yahoo gave none, the read failed, or Yahoo limited the request) | Analysed, not refused. The check refuses only on evidence. The report carries `data.security = null` (or a security with `currency = null`). |

The currency comes from one Yahoo metadata read per ticker (`Ticker.get_info()`, fields `longName`,
`shortName`, `currency`, `exchange` or `fullExchangeName`, `quoteType`). It is cached for 7 days
next to the price cache (`{TICKER}_security.json`), obeys the same spacing, retries, backoff and
circuit breaker as the price download, and never blocks a report.

Where it is enforced:

- `build_report` (CLI): before the price history is downloaded. Exit code 1 (data error) and one
  line on standard error with the message above.
- The API: `GET /api/report/{ticker}`, `/html` and `/ranges` answer HTTP 422 with the error code
  `unsupported_currency`, the same `ApiError` envelope as the other typed errors.
- `assemble_report` checks too, so any caller that passes a security record gets the same rule.

## Why unknown is accepted

A failed or throttled metadata read must not stop a report that worked yesterday: the read is
cosmetic for most tickers (the company name). Refusing on a missing answer would turn a Yahoo
rate limit into a refusal of valid US tickers. The cost is that a non-USD ticker can slip through
while Yahoo is limiting requests. The US-factors caveat in every report still says that betas of a
non-US or non-USD series mix factor exposure with currency and local-market effects.

## Open points for the owner

1. **A warning for the unknown case.** This change adds none (the report builds and the header
   simply shows no currency). If wanted, a `currency_unknown` report warning is a few lines in
   `pipeline._warnings`, but it would appear on every offline test report and on every report
   built while Yahoo is limiting requests.
2. **Exchange versus currency.** M1.5's second bullet also mentions a non-US exchange. A USD-quoted
   foreign listing (an ADR, or a US-dollar share class listed abroad) passes this check and keeps
   only the caveat. Decide whether those should also be refused.
3. **Lifting the rule.** When European factors exist (roadmap item 15), the refusal is replaced by
   a choice of factor set per currency; `check_currency` in `data/prices.py` is the one place to
   change.
4. **Methodology and decision record.** Fold the proposed M1.5 text into `docs/methodology.md`,
   add the decision to the register, and update ticket N1 and the README line on non-US tickers
   (the factcheck in `docs/reviews/readme-factcheck-2026-11-18.md`, row M12).
