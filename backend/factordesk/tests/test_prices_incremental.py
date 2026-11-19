"""Incremental refresh of a cached price history (``YFinanceProvider.fetch_incremental``).

All offline: the downloads are fakes that serve slices of one synthetic Yahoo history and count
their calls.
"""

from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from factordesk.data import prices as prices_module
from factordesk.data.prices import (
    FULL_REFRESH_DAYS,
    REFRESH_OVERLAP_DAYS,
    REFRESH_TIMEOUT_SECONDS,
    IncrementalPriceProvider,
    PriceDataError,
    YFinanceProvider,
    _refresh_start,  # pyright: ignore[reportPrivateUsage]
    latest_completed_session,
    merge_histories,
    rebased,
)
from factordesk.data.throttle import BatchSettings

TZ = "America/New_York"
SETTINGS = BatchSettings(
    chunk_size=1, max_workers=1, min_interval_seconds=0.0, max_attempts=2, breaker_threshold=3
)
TUESDAY = datetime(2026, 3, 10, 21, 0, tzinfo=UTC)  # 17:00 in New York
THURSDAY = datetime(2026, 3, 12, 21, 0, tzinfo=UTC)
SATURDAY = datetime(2026, 3, 14, 15, 0, tzinfo=UTC)
SUNDAY = datetime(2026, 3, 15, 15, 0, tzinfo=UTC)


def yahoo_frame(
    start: str,
    end: str,
    *,
    adj_scale: float = 0.98,
    dividends: dict[str, float] | None = None,
) -> pd.DataFrame:
    """Rows of one synthetic history between two dates, shaped like ``Ticker.history()``.

    ``dividends`` maps an ex-date to an amount; like Yahoo, every adjusted close before an ex-date
    is multiplied by ``1 - amount / previous close``, so a late dividend rewrites old rows.
    """
    idx = pd.date_range("2026-01-05", "2026-06-30", freq="B", tz=TZ, name="Date")
    close = 100.0 + np.cumsum(np.sin(np.arange(len(idx)) / 3.0))
    paid = np.zeros(len(idx))
    adj = np.full(len(idx), adj_scale)
    for day, amount in (dividends or {}).items():
        pos = int(idx.get_loc(pd.Timestamp(day, tz=TZ)))  # pyright: ignore[reportArgumentType]
        paid[pos] = amount
        adj[:pos] *= 1.0 - amount / close[pos - 1]
    full = pd.DataFrame(
        {
            "Open": close,
            "High": close + 1,
            "Low": close - 1,
            "Close": close,
            "Adj Close": close * adj,
            "Volume": np.full(len(idx), 1_000.0),
            "Dividends": paid,
            "Stock Splits": np.zeros(len(idx)),
        },
        index=idx,
    )
    keep = (idx >= pd.Timestamp(start, tz=TZ)) & (idx <= pd.Timestamp(end, tz=TZ))
    return full.loc[keep]


class Feed:
    """Fake Yahoo: serves the history up to ``today`` (today's partial bar included)."""

    def __init__(self, today: date, *, adj_scale: float = 0.98) -> None:
        self.today = today
        self.adj_scale = adj_scale
        self.dividends: dict[str, float] = {}
        self.full_calls = 0
        self.since_calls: list[date] = []
        self.fail: Exception | None = None

    def full(self, ticker: str) -> pd.DataFrame:
        self.full_calls += 1
        if self.fail is not None:
            raise self.fail
        return yahoo_frame(
            "2026-01-05", self.today.isoformat(), adj_scale=self.adj_scale, dividends=self.dividends
        )

    def since(self, ticker: str, start: date) -> pd.DataFrame:
        self.since_calls.append(start)
        if self.fail is not None:
            raise self.fail
        return yahoo_frame(
            start.isoformat(),
            self.today.isoformat(),
            adj_scale=self.adj_scale,
            dividends=self.dividends,
        )


class Clock:
    """A fake clock that only moves when the code under test sleeps."""

    def __init__(self) -> None:
        self.now = 1000.0
        self.sleeps: list[float] = []

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


def make(tmp_path: Path, feed: Feed, now: datetime, clock: Clock | None = None) -> YFinanceProvider:
    feed.today = now.astimezone(UTC).date()
    clock = clock or Clock()
    return YFinanceProvider(
        cache_dir=tmp_path / "prices",
        now=lambda: now,
        settings=SETTINGS,
        download=feed.full,
        download_since=feed.since,
        monotonic=clock.monotonic,
        sleep=clock.sleep,
    )


def test_provider_satisfies_the_incremental_protocol(tmp_path: Path) -> None:
    assert isinstance(make(tmp_path, Feed(date(2026, 3, 10)), TUESDAY), IncrementalPriceProvider)


def test_cold_cache_downloads_the_full_history_once(tmp_path: Path) -> None:
    feed = Feed(date(2026, 3, 10))
    result = make(tmp_path, feed, TUESDAY).fetch_incremental("ACWI")
    assert result.action == "full" and result.note is None
    assert (feed.full_calls, feed.since_calls) == (1, [])
    assert result.history.frame.index[0] == pd.Timestamp("2026-01-05")
    assert result.history.frame.index[-1] == pd.Timestamp("2026-03-09")  # today's bar is dropped
    assert (tmp_path / "prices" / "ACWI_2026-03-10.parquet").is_file()


def test_warm_cache_with_new_days_fetches_only_the_new_days_and_equals_a_full_fetch(
    tmp_path: Path,
) -> None:
    feed = Feed(date(2026, 3, 10))
    make(tmp_path, feed, TUESDAY).fetch_incremental("ACWI")
    later = make(tmp_path, feed, THURSDAY).fetch_incremental("ACWI")
    assert later.action == "incremental"
    assert feed.full_calls == 1  # no second full download
    assert feed.since_calls == [date(2026, 3, 9) - timedelta(days=7)]
    reference = YFinanceProvider(
        cache_dir=tmp_path / "reference",
        now=lambda: THURSDAY,
        settings=SETTINGS,
        download=feed.full,
        sleep=lambda _s: None,
    ).fetch("ACWI")
    pd.testing.assert_frame_equal(later.history.frame, reference.frame, check_freq=False)
    assert later.history.frame.index.is_unique
    assert later.history.frame.index[-1] == pd.Timestamp("2026-03-11")
    cache = tmp_path / "prices"
    assert (cache / "ACWI_2026-03-12.parquet").is_file()
    assert not (cache / "ACWI_2026-03-10.parquet").exists()  # the old file was replaced


def test_warm_cache_that_is_up_to_date_makes_no_network_call(tmp_path: Path) -> None:
    feed = Feed(date(2026, 3, 10))
    make(tmp_path, feed, TUESDAY).fetch_incremental("ACWI")
    again = make(tmp_path, feed, TUESDAY + timedelta(hours=1)).fetch_incremental("ACWI")
    assert again.action == "cached"
    assert (feed.full_calls, feed.since_calls) == (1, [])


def test_cache_holding_the_latest_completed_day_is_not_refreshed_on_another_day(
    tmp_path: Path,
) -> None:
    feed = Feed(date(2026, 3, 14))
    first = make(tmp_path, feed, SATURDAY).fetch_incremental("ACWI")
    assert first.history.frame.index[-1] == pd.Timestamp("2026-03-13")  # Friday
    second = make(tmp_path, feed, SUNDAY).fetch_incremental("ACWI")
    assert second.action == "cached"
    assert (feed.full_calls, feed.since_calls) == (1, [])


def test_failed_refresh_with_a_cache_serves_the_cache_and_says_where_it_ends(
    tmp_path: Path,
) -> None:
    feed = Feed(date(2026, 3, 10))
    first = make(tmp_path, feed, TUESDAY).fetch_incremental("ACWI")
    feed.fail = ConnectionError("offline")
    result = make(tmp_path, feed, THURSDAY).fetch_incremental("ACWI")
    assert result.action == "stale"
    assert result.note is not None and result.note.startswith("ACWI data ends 2026-03-09")
    pd.testing.assert_frame_equal(result.history.frame, first.history.frame, check_freq=False)
    assert len(feed.since_calls) == 1  # one attempt: a cache is there to fall back on
    assert (tmp_path / "prices" / "ACWI_2026-03-10.parquet").is_file()  # cache kept


class RateLimited(RuntimeError):
    """Yahoo's 429 with a long Retry-After."""

    retry_after = 90.0


@pytest.mark.parametrize(
    "failure",
    [ConnectionError("offline"), TimeoutError("slow"), RateLimited("Too Many Requests")],
    ids=["connection", "timeout", "rate-limit-with-retry-after"],
)
def test_failed_refresh_with_a_cache_returns_at_once_without_sleeping(
    tmp_path: Path, failure: Exception
) -> None:
    """With a cache the refresh is one attempt: no back-off, no rate-limit pause, no Retry-After.

    The clock is fake and moves only when the code sleeps, so ``clock.now`` is the time the call
    would have waited. The cold-cache path keeps the retry schedule (next test).
    """
    feed = Feed(date(2026, 3, 10))
    make(tmp_path, feed, TUESDAY).fetch_incremental("ACWI")
    feed.fail = failure
    clock = Clock()
    started = clock.now
    result = make(tmp_path, feed, THURSDAY, clock).fetch_incremental("ACWI")
    assert result.action == "stale" and result.note is not None
    assert len(feed.since_calls) == 1 and feed.full_calls == 1
    assert clock.sleeps == []
    assert clock.now - started < 1.0  # the bound; in fact no time passes


def test_failed_forced_full_download_with_a_cache_is_one_attempt_too(tmp_path: Path) -> None:
    feed = Feed(date(2026, 3, 10))
    make(tmp_path, feed, TUESDAY).fetch_incremental("ACWI")
    feed.fail = RateLimited("Too Many Requests")
    clock = Clock()
    result = make(tmp_path, feed, TUESDAY + timedelta(days=40), clock).fetch_incremental("ACWI")
    assert result.action == "stale"
    assert feed.full_calls == 2 and feed.since_calls == []  # the forced full, tried once
    assert clock.sleeps == []


def test_failed_download_without_a_cache_raises(tmp_path: Path) -> None:
    feed = Feed(date(2026, 3, 10))
    feed.fail = ConnectionError("offline")
    clock = Clock()
    with pytest.raises(PriceDataError, match="Could not reach Yahoo"):
        make(tmp_path, feed, TUESDAY, clock).fetch_incremental("ACWI")
    assert feed.full_calls == SETTINGS.max_attempts  # a cold cache keeps the retry policy
    assert len(clock.sleeps) == SETTINGS.max_attempts - 1 and all(s > 0 for s in clock.sleeps)


def test_refresh_requests_carry_a_short_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[dict[str, object]] = []

    def fake(ticker: str, **kwargs: object) -> pd.DataFrame:
        seen.append(kwargs)
        return pd.DataFrame()

    monkeypatch.setattr(prices_module, "_yf_history", fake)
    prices_module._download_history_since("ACWI", date(2026, 3, 2))  # pyright: ignore[reportPrivateUsage]
    prices_module._download_history("ACWI")  # pyright: ignore[reportPrivateUsage]
    assert seen[0] == {"timeout": REFRESH_TIMEOUT_SECONDS, "start": "2026-03-02"}
    assert seen[1] == {"period": "max"}  # the cold download keeps yfinance's own timeout


def test_rate_limit_is_reported_in_plain_words(tmp_path: Path) -> None:
    feed = Feed(date(2026, 3, 10))
    feed.fail = RuntimeError("Too Many Requests")
    with pytest.raises(PriceDataError, match="limiting requests"):
        make(tmp_path, feed, TUESDAY).fetch_incremental("ACWI")


def test_corrupt_cache_is_downloaded_again(tmp_path: Path) -> None:
    cache = tmp_path / "prices"
    cache.mkdir()
    (cache / "ACWI_2026-03-10.parquet").write_bytes(b"not parquet")
    feed = Feed(date(2026, 3, 10))
    result = make(tmp_path, feed, TUESDAY).fetch_incremental("ACWI")
    assert result.action == "full"
    assert (feed.full_calls, feed.since_calls) == (1, [])
    assert len(pd.read_parquet(cache / "ACWI_2026-03-10.parquet")) == len(result.history.frame)


def test_rebased_prices_trigger_a_full_download(tmp_path: Path) -> None:
    feed = Feed(date(2026, 3, 10))
    make(tmp_path, feed, TUESDAY).fetch_incremental("ACWI")
    feed.adj_scale = 0.97  # a dividend rewrote the whole adjusted history
    result = make(tmp_path, feed, THURSDAY).fetch_incremental("ACWI")
    assert result.action == "full"
    assert feed.full_calls == 2 and len(feed.since_calls) == 1
    expected = yahoo_frame("2026-01-05", "2026-03-11", adj_scale=0.97)["Adj Close"]
    np.testing.assert_allclose(result.history.frame["adj_close"].to_numpy(), expected.to_numpy())


def test_no_new_bar_keeps_the_cache_and_records_the_check(tmp_path: Path) -> None:
    feed = Feed(date(2026, 3, 10))
    make(tmp_path, feed, TUESDAY).fetch_incremental("ACWI")
    # A holiday on Wednesday 11 March: Yahoo has nothing after the 9th.
    holiday = datetime(2026, 3, 11, 21, 0, tzinfo=UTC)
    feed.since = lambda ticker, start: yahoo_frame(  # type: ignore[method-assign]
        start.isoformat(), "2026-03-09"
    )
    result = make(tmp_path, feed, holiday).fetch_incremental("ACWI")
    assert result.action == "incremental"
    assert result.history.frame.index[-1] == pd.Timestamp("2026-03-09")
    again = make(tmp_path, feed, holiday + timedelta(hours=1)).fetch_incremental("ACWI")
    assert again.action == "cached"


def test_latest_completed_session_skips_weekends() -> None:
    assert latest_completed_session(TUESDAY) == date(2026, 3, 9)
    assert latest_completed_session(SATURDAY) == date(2026, 3, 13)
    assert latest_completed_session(SUNDAY) == date(2026, 3, 13)
    monday = datetime(2026, 3, 9, 14, 0, tzinfo=UTC)
    assert latest_completed_session(monday) == date(2026, 3, 6)


def test_merge_keeps_fresh_rows_on_a_repeated_date() -> None:
    idx = pd.to_datetime(["2026-03-02", "2026-03-03", "2026-03-04"])
    old = pd.DataFrame({"close": [1.0, 2.0, 3.0], "adj_close": [1.0, 2.0, 3.0]}, index=idx)
    new_idx = pd.to_datetime(["2026-03-03", "2026-03-05"])
    new = pd.DataFrame({"close": [2.5, 4.0], "adj_close": [2.5, 4.0]}, index=new_idx)
    merged = merge_histories(old, new)
    assert merged["close"].tolist() == [1.0, 2.5, 4.0]
    assert merged.index.is_unique


def test_rebased_needs_a_common_row() -> None:
    old = pd.DataFrame({"close": [1.0], "adj_close": [1.0]}, index=pd.to_datetime(["2026-03-02"]))
    new = pd.DataFrame({"close": [1.0], "adj_close": [1.0]}, index=pd.to_datetime(["2026-03-09"]))
    assert rebased(old, new)
    assert not rebased(old, old)


# ------------------------------------------------------------------ F3: late rewrites


def _with_dividend(tmp_path: Path) -> Feed:
    feed = Feed(date(2026, 3, 10))
    feed.dividends = {"2026-01-20": 0.5}
    make(tmp_path, feed, TUESDAY).fetch_incremental("ACWI")
    return feed


def test_refresh_starts_at_the_last_cached_dividend(tmp_path: Path) -> None:
    feed = _with_dividend(tmp_path)
    result = make(tmp_path, feed, THURSDAY).fetch_incremental("ACWI")
    assert result.action == "incremental"  # nothing was rewritten: no needless full download
    assert feed.since_calls == [date(2026, 1, 20)]
    assert feed.full_calls == 1


def test_a_late_dividend_inside_the_window_is_picked_up(tmp_path: Path) -> None:
    """A dividend Yahoo posts weeks after its ex-date leaves the last seven days unchanged; the
    window from the last cached dividend still sees the rewrite, so the history is re-downloaded."""
    feed = _with_dividend(tmp_path)
    feed.dividends["2026-02-10"] = 0.4  # ex-date more than seven days before the last cached day
    result = make(tmp_path, feed, THURSDAY).fetch_incremental("ACWI")
    assert result.action == "full" and feed.full_calls == 2
    assert feed.since_calls == [date(2026, 1, 20)]
    frame = result.history.frame
    assert frame.loc[pd.Timestamp("2026-02-10"), "dividends"] == pytest.approx(0.4)
    expected = yahoo_frame("2026-01-05", "2026-03-11", dividends=feed.dividends)["Adj Close"]
    np.testing.assert_allclose(frame["adj_close"].to_numpy(), expected.to_numpy())


def test_a_seven_day_window_alone_would_have_missed_that_dividend(tmp_path: Path) -> None:
    feed = Feed(date(2026, 3, 10))
    make(tmp_path, feed, TUESDAY).fetch_incremental("ACWI")  # no dividend in the cache
    window = _refresh_start(pd.read_parquet(next((tmp_path / "prices").glob("ACWI_*.parquet"))))
    assert window == date(2026, 3, 9) - timedelta(days=REFRESH_OVERLAP_DAYS)
    feed.dividends["2026-02-10"] = 0.4
    late = feed.since("ACWI", window)
    cached = pd.read_parquet(next((tmp_path / "prices").glob("ACWI_*.parquet")))
    fresh = late.rename(columns={"Close": "close", "Adj Close": "adj_close"})
    fresh = fresh.assign(dividends=fresh["Dividends"])
    fresh.index = pd.DatetimeIndex(fresh.index).tz_localize(None).normalize()
    assert not rebased(cached, fresh)  # the old window cannot see it


def test_a_changed_distribution_column_counts_as_rebased() -> None:
    idx = pd.to_datetime(["2026-03-02", "2026-03-03"])
    old = pd.DataFrame(
        {"close": [1.0, 2.0], "adj_close": [1.0, 2.0], "dividends": [0.0, 0.0]}, index=idx
    )
    same_prices = old.assign(dividends=[0.0, 0.1])
    assert rebased(old, same_prices)
    assert not rebased(old, old.copy())
    gains = old.assign(capital_gains=[0.0, 0.0])
    assert rebased(gains, gains.assign(capital_gains=[0.2, 0.0]))


def test_refresh_start_is_the_earlier_of_the_overlap_and_the_last_distribution() -> None:
    idx = pd.bdate_range("2026-01-05", "2026-03-09")
    base = pd.DataFrame({"close": 1.0, "adj_close": 1.0, "dividends": 0.0}, index=idx)
    overlap = date(2026, 3, 9) - timedelta(days=REFRESH_OVERLAP_DAYS)
    assert _refresh_start(base) == overlap  # no distribution cached
    old = base.copy()
    old.loc["2026-01-20", "dividends"] = 0.5
    assert _refresh_start(old) == date(2026, 1, 20)
    recent = base.copy()
    recent.loc["2026-03-06", "dividends"] = 0.5  # inside the seven days: the overlap wins
    assert _refresh_start(recent) == overlap
    gain = base.assign(capital_gains=0.0)
    gain.loc["2026-02-02", "capital_gains"] = 1.0
    assert _refresh_start(gain) == date(2026, 2, 2)


def _stamp(tmp_path: Path) -> str:
    cached = pd.read_parquet(next((tmp_path / "prices").glob("ACWI_*.parquet")))
    return str(cached.attrs.get("full_downloaded_at"))


def test_the_full_download_date_is_stored_and_kept_by_incremental_refreshes(
    tmp_path: Path,
) -> None:
    feed = Feed(date(2026, 3, 10))
    first = make(tmp_path, feed, TUESDAY).fetch_incremental("ACWI")
    assert first.history.full_downloaded_at == TUESDAY
    assert _stamp(tmp_path) == TUESDAY.isoformat()
    later = make(tmp_path, feed, THURSDAY).fetch_incremental("ACWI")
    assert later.action == "incremental"
    assert later.history.full_downloaded_at == TUESDAY  # not reset by an incremental refresh
    assert _stamp(tmp_path) == TUESDAY.isoformat()


def test_a_full_download_is_forced_when_the_last_one_is_older_than_30_days(
    tmp_path: Path,
) -> None:
    feed = Feed(date(2026, 3, 10))
    make(tmp_path, feed, TUESDAY).fetch_incremental("ACWI")
    on_the_limit = TUESDAY + timedelta(days=FULL_REFRESH_DAYS)  # 30 days: still incremental
    result = make(tmp_path, feed, on_the_limit).fetch_incremental("ACWI")
    assert result.action == "incremental" and feed.full_calls == 1
    past_it = TUESDAY + timedelta(days=FULL_REFRESH_DAYS + 1)  # measured from the full download
    forced = make(tmp_path, feed, past_it).fetch_incremental("ACWI")
    assert forced.action == "full" and feed.full_calls == 2
    assert forced.history.full_downloaded_at == past_it
    assert _stamp(tmp_path) == past_it.isoformat()
    after = make(tmp_path, feed, past_it + timedelta(days=1)).fetch_incremental("ACWI")
    assert after.action == "incremental" and feed.full_calls == 2  # the clock restarted


def test_a_cache_without_the_full_download_date_is_downloaded_whole_once(tmp_path: Path) -> None:
    feed = Feed(date(2026, 3, 10))
    make(tmp_path, feed, TUESDAY).fetch_incremental("ACWI")
    path = next((tmp_path / "prices").glob("ACWI_*.parquet"))
    frame = pd.read_parquet(path)
    frame.attrs.pop("full_downloaded_at")
    frame.to_parquet(path)
    result = make(tmp_path, feed, THURSDAY).fetch_incremental("ACWI")
    assert result.action == "full" and feed.full_calls == 2
    assert result.history.full_downloaded_at == THURSDAY
