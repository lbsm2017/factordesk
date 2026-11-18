# Decision: download several tickers in parallel, but gently

Date: 2026-11-18
Status: Decided-pending-implementation (becomes Decided when the change is merged)

## In one sentence

When we need prices for several tickers at once, we download them a few at a time on a small number of threads, with a pause between requests, slow retries and a stop switch, because Yahoo publishes no rate limit and a faster download is not worth being blocked.

## What we decided

The owner asked on 2026-11-18 that the Yahoo download be "parallelized in chunks to optimize time, careful with throttling." We read that as follows.

- One ticker is still one request for its full history. We do not split a ticker's history into date ranges: adjusted prices are rewritten at every dividend, so one ticker must come from one download (see the earlier prices decision). "Chunks" here means groups of tickers.
- A new call, `fetch_many(tickers)`, loads several tickers. The existing `fetch(ticker)` is unchanged.
- Defaults: 5 tickers per chunk, 3 chunks at a time, at least 0.5 seconds between request starts (plus a random extra of up to 0.25 seconds), up to 3 tries per ticker, and a stop after 3 rate-limit replies in a row. All five are settings (`PRICE_CHUNK_SIZE`, `PRICE_MAX_WORKERS`, `PRICE_MIN_INTERVAL_SECONDS`, `PRICE_MAX_ATTEMPTS`, `PRICE_BREAKER_THRESHOLD`) listed in `.env.example`.
- Peers and the dashboard can call `fetch_many` later. This decision changes no dashboard code.

## Why

The gain is real: tickers are independent, and most of the time is spent waiting for Yahoo to answer, so a few at once finish sooner than one after another. The risk is also real: Yahoo publishes no API, no rate limit and no statement about automated access ([docs/data-source-comparison.md](../docs/data-source-comparison.md), section 6.3). We therefore cannot say what is safe, and we do not claim a number. We chose small, conservative defaults that the owner can change, and a design that backs off when Yahoo pushes back instead of one tuned to a guessed limit.

We rejected `yf.download` for the batch, as the code already avoids it: `Ticker.history` gives a stable shape and lets us control every option per ticker. We rejected splitting history by date range because it gives no speed-up per ticker and would mix adjustment bases. We rejected unlimited parallelism because a block from Yahoo would cost the user more time than the speed-up saves.

## How it works

1. Each ticker is checked for a symbol that is safe to use, then repeats are removed. Repeats are reported, not hidden.
2. Tickers already downloaded today are read from the same-day cache. No request is made for them.
3. The rest are split into chunks and handed to a small pool of threads. Inside a chunk, tickers go one after another.
4. A shared pacer lets only one request start per interval across all threads, with a little random jitter, so the requests never arrive in a burst.
5. If Yahoo replies with a rate limit (HTTP 429, "Too Many Requests", or yfinance's rate-limit error) or a temporary network error, the ticker waits and tries again: 2 seconds, then 4, then 8, capped at 30, with up to 25% random extra. If the reply carries a Retry-After value, we wait at least that long (never more than 120 seconds). We never retry forever: three tries, then the ticker is reported as failed.
6. If three rate-limit replies arrive in a row, a circuit breaker opens. No new request starts. Tickers not yet tried are reported as skipped, with the sentence: "Yahoo is limiting requests. Wait a few minutes and try again." A reply that is not a rate limit resets the count.
7. The result lists every distinct ticker in the order it was asked for, with either its prices or a reason code and one plain sentence. It also gives counts (from cache, downloaded, failed, skipped) and the elapsed time. One bad ticker never fails the batch.
8. Two callers asking for the same ticker at the same moment cause one download; the second reads the cache the first one wrote. Cache files are written atomically.

## What it costs us

- More code to maintain: a pacer, a retry schedule, a breaker and a result type, all with tests.
- The defaults are guesses. Because Yahoo publishes no limit, 5, 3 and 0.5 seconds are cautious choices, not measured ones. We have not measured the speed-up on live Yahoo yet (2026-11-18), so we do not state one.
- A stopped batch is a partial answer. Tickers that were skipped have to be requested again later.
- Detection of a rate limit relies on the error text and status code that Yahoo and yfinance happen to give today. If yfinance changes them, a rate limit could be reported as an unexpected error until the detection is updated.
- Threads add a little risk of subtle bugs. We limit it by keeping each ticker's download in one thread and the cache writes atomic.

## What would change our mind

- A live measurement showing the speed-up is small, or that these defaults still trigger rate limits: lower the settings or go back to one at a time.
- Yahoo publishing a limit, or the owner moving to a licensed or official feed with a documented limit: tune to that limit.
- yfinance adding its own batching or pacing that does the same job.

## Sources

- Owner request, 2026-11-18: "yfinance download should be parallelized in chunks to optimize time, careful with throttling."
- [docs/data-source-comparison.md](../docs/data-source-comparison.md), section 6.3 (Yahoo: no published API or rate limit).
- [docs/data-quality-plan.md](../docs/data-quality-plan.md): adjusted-close handling, which this change does not touch.
- [CODING_STANDARDS.md](../CODING_STANDARDS.md), sections 3, 4 and 7 (no silent drops, injected clocks and clients, settings in one place).
- Code: `backend/factordesk/data/prices.py` and `backend/factordesk/data/throttle.py`.

## Related decisions

- [Prices from Yahoo, with adjusted-close care](decision-prices-from-yahoo-with-adjusted-close-care.md)
- [Dashboard server and interface](decision-dashboard-server-and-interface.md)
- [No data and no secrets in the repository](decision-no-data-and-no-secrets-in-the-repo.md)
