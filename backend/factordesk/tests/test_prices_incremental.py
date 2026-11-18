"""Incremental refresh of a cached price history (``YFinanceProvider.fetch_incremental``).

All offline: the downloads are fakes that serve slices of one synthetic Yahoo history and count
their calls.
"""

from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from factordesk.data.prices import (
    IncrementalPriceProvider,
    PriceDataError,
    YFinanceProvider,
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


def yahoo_frame(start: str, end: str, *, adj_scale: float = 0.98) -> pd.DataFrame:
    """Rows of one synthetic history between two dates, shaped like ``Ticker.history()``."""
    idx = pd.date_range("2026-01-05", "2026-03-20", freq="B", tz=TZ, name="Date")
    close = 100.0 + np.cumsum(np.sin(np.arange(len(idx)) / 3.0))
    full = pd.DataFrame(
        {
            "Open": close,
            "High": close + 1,
            "Low": close - 1,
            "Close": close,
            "Adj Close": close * adj_scale,
            "Volume": np.full(len(idx), 1_000.0),
            "Dividends": np.zeros(len(idx)),
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
        self.full_calls = 0
        self.since_calls: list[date] = []
        self.fail: Exception | None = None

    def full(self, ticker: str) -> pd.DataFrame:
        self.full_calls += 1
        if self.fail is not None:
            raise self.fail
        return yahoo_frame("2026-01-05", self.today.isoformat(), adj_scale=self.adj_scale)

    def since(self, ticker: str, start: date) -> pd.DataFrame:
        self.since_calls.append(start)
        if self.fail is not None:
            raise self.fail
        return yahoo_frame(start.isoformat(), self.today.isoformat(), adj_scale=self.adj_scale)


def make(tmp_path: Path, feed: Feed, now: datetime) -> YFinanceProvider:
    feed.today = now.astimezone(UTC).date()
    return YFinanceProvider(
        cache_dir=tmp_path / "prices",
        now=lambda: now,
        settings=SETTINGS,
        download=feed.full,
        download_since=feed.since,
        sleep=lambda _s: None,
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
    assert len(feed.since_calls) == SETTINGS.max_attempts  # retried like any other download
    assert (tmp_path / "prices" / "ACWI_2026-03-10.parquet").is_file()  # cache kept


def test_failed_download_without_a_cache_raises(tmp_path: Path) -> None:
    feed = Feed(date(2026, 3, 10))
    feed.fail = ConnectionError("offline")
    with pytest.raises(PriceDataError, match="Could not reach Yahoo"):
        make(tmp_path, feed, TUESDAY).fetch_incremental("ACWI")


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
