import logging
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest

from factordesk.data import prices
from factordesk.data.audit import audit_prices
from factordesk.data.prices import (
    AlpacaProvider,
    PriceDataError,
    PriceHistory,
    YFinanceProvider,
    collapse_duplicate_dates,
    validate_ticker,
)

logger = logging.getLogger(__name__)

NOW = datetime(2026, 3, 10, 21, 0, tzinfo=UTC)  # 17:00 New York on Tuesday 2026-03-10
TZ = "America/New_York"


def raw_yahoo_frame(
    start: str = "2026-03-02", periods: int = 7, *, with_extras: bool = True
) -> pd.DataFrame:
    """A frame shaped like Ticker.history(): tz-aware index named Date, Title-case columns."""
    idx = pd.date_range(start, periods=periods, freq="B", tz=TZ, name="Date")
    close = 100.0 + np.arange(periods, dtype="float64")
    data: dict[str, Any] = {
        "Open": close - 1,
        "High": close + 1,
        "Low": close - 2,
        "Close": close,
        "Adj Close": close * 0.98,
        "Volume": np.full(periods, 1_000, dtype="int64"),
        "Dividends": np.zeros(periods),
        "Stock Splits": np.zeros(periods),
    }
    if with_extras:
        data["Capital Gains"] = np.zeros(periods)
        data["Repaired?"] = np.zeros(periods)
    return pd.DataFrame(data, index=idx)


class FakeTicker:
    frame: pd.DataFrame = pd.DataFrame()
    calls: list[dict[str, Any]] = []
    raises: Exception | None = None

    def __init__(self, ticker: str, *args: Any, **kwargs: Any) -> None:
        if FakeTicker.raises is not None:
            raise FakeTicker.raises
        self.ticker = ticker
        FakeTicker.calls.append({"ticker": ticker, "ctor_kwargs": kwargs})

    def history(self, *args: Any, **kwargs: Any) -> pd.DataFrame:
        FakeTicker.calls[-1]["history_args"] = args
        FakeTicker.calls[-1]["history_kwargs"] = kwargs
        return FakeTicker.frame.copy()


@pytest.fixture
def fake_yf(monkeypatch: pytest.MonkeyPatch) -> type[FakeTicker]:
    FakeTicker.frame = raw_yahoo_frame()
    FakeTicker.calls = []
    FakeTicker.raises = None
    monkeypatch.setattr("yfinance.Ticker", FakeTicker)
    return FakeTicker


def provider(tmp_path: Path, now: datetime = NOW) -> YFinanceProvider:
    return YFinanceProvider(cache_dir=tmp_path / "prices", now=lambda: now)


# ---------------------------------------------------------------- fetch normalization


def test_yfinance_called_with_every_argument_explicit(
    fake_yf: type[FakeTicker], tmp_path: Path
) -> None:
    provider(tmp_path).fetch("spy")
    call = fake_yf.calls[0]
    assert call["ticker"] == "SPY"
    assert call["ctor_kwargs"] == {}  # no session passed: yfinance owns its curl_cffi session
    assert call["history_args"] == ()
    assert call["history_kwargs"] == {
        "period": "max",
        "interval": "1d",
        "auto_adjust": False,
        "actions": True,
        "repair": False,
    }


def test_fetch_normalizes_frame(fake_yf: type[FakeTicker], tmp_path: Path) -> None:
    raw = raw_yahoo_frame()
    raw.loc[raw.index[2], "Dividends"] = np.nan  # NaN in an action column means "none"
    fake_yf.frame = raw
    history = provider(tmp_path).fetch("SPY")
    frame = history.frame

    assert history.source == "yfinance"
    assert history.ticker == "SPY"
    assert history.fetched_at == NOW
    assert isinstance(frame.index, pd.DatetimeIndex)
    assert frame.index.name == "date"
    assert frame.index.tz is None
    assert (frame.index == frame.index.normalize()).all()
    assert frame.index.is_monotonic_increasing and frame.index.is_unique
    assert list(frame.columns) == [
        "close",
        "adj_close",
        "dividends",
        "splits",
        "capital_gains",
        "volume",
    ]
    assert all(dtype == np.dtype("float64") for dtype in frame.dtypes)
    # Exchange-local dates survive (no shift to the previous day via UTC).
    assert pd.Timestamp(frame.index[0]).date() == date(2026, 3, 2)
    assert frame["dividends"].notna().all()
    # Close is already split adjusted: it must pass through untouched.
    np.testing.assert_allclose(frame["close"], raw["Close"].to_numpy()[:-1])
    np.testing.assert_allclose(frame["adj_close"], raw["Adj Close"].to_numpy()[:-1])


def test_fetch_without_optional_columns(fake_yf: type[FakeTicker], tmp_path: Path) -> None:
    raw = raw_yahoo_frame(with_extras=False).drop(columns=["Dividends", "Stock Splits"])
    fake_yf.frame = raw
    frame = provider(tmp_path).fetch("SPY").frame
    assert (frame["dividends"] == 0.0).all()
    assert (frame["splits"] == 0.0).all()
    assert "capital_gains" not in frame.columns


def test_split_column_is_never_applied(fake_yf: type[FakeTicker], tmp_path: Path) -> None:
    raw = raw_yahoo_frame()
    raw.loc[raw.index[3], "Stock Splits"] = 4.0
    fake_yf.frame = raw
    frame = provider(tmp_path).fetch("SPY").frame
    np.testing.assert_allclose(frame["close"], raw["Close"].to_numpy()[:-1])
    assert frame["splits"].iloc[3] == 4.0


def test_todays_partial_bar_is_dropped(fake_yf: type[FakeTicker], tmp_path: Path) -> None:
    # Raw runs Mon 03-02 .. Tue 03-10; NOW is 03-10 in New York, so the last bar is partial.
    history = provider(tmp_path).fetch("SPY")
    assert pd.Timestamp(history.frame.index[-1]).date() == date(2026, 3, 9)
    assert len(history.frame) == 6


def test_today_is_judged_in_exchange_timezone(fake_yf: type[FakeTicker], tmp_path: Path) -> None:
    # 01:00 UTC on 03-11 is still 03-10 in New York: the 03-10 bar is still "today".
    late_utc = datetime(2026, 3, 11, 1, 0, tzinfo=UTC)
    history = provider(tmp_path, late_utc).fetch("SPY")
    assert pd.Timestamp(history.frame.index[-1]).date() == date(2026, 3, 9)


def test_completed_bars_are_kept(fake_yf: type[FakeTicker], tmp_path: Path) -> None:
    next_day = datetime(2026, 3, 11, 15, 0, tzinfo=UTC)  # 03-10 bar is now yesterday's
    history = provider(tmp_path, next_day).fetch("SPY")
    assert pd.Timestamp(history.frame.index[-1]).date() == date(2026, 3, 10)
    assert len(history.frame) == 7


def test_t117_duplicate_dates_are_recorded_not_dropped_silently(
    fake_yf: type[FakeTicker], tmp_path: Path
) -> None:
    raw = raw_yahoo_frame()
    repeat = raw.iloc[[-2]].assign(Close=999.0)  # 2026-03-09 delivered twice
    fake_yf.frame = pd.concat([raw, repeat]).sort_index(kind="stable")
    history = provider(tmp_path).fetch("SPY")
    frame = history.frame
    assert frame.index.is_unique and len(frame) == 6
    assert 999.0 not in frame["close"].to_numpy()  # the first bar is kept (D29)
    assert history.duplicate_dates == (date(2026, 3, 9),)
    report = audit_prices(frame, duplicate_dates=history.duplicate_dates)
    dup = next(f for f in report.findings if f.code == "duplicate_index")
    assert dup.severity == "error" and dup.dates == (date(2026, 3, 9),)
    # The record survives the same-day cache.
    cached = provider(tmp_path, NOW + timedelta(hours=1)).fetch("SPY")
    assert len(fake_yf.calls) == 1
    assert cached.duplicate_dates == (date(2026, 3, 9),)


def test_unique_history_has_no_duplicate_record(fake_yf: type[FakeTicker], tmp_path: Path) -> None:
    history = provider(tmp_path).fetch("SPY")
    assert history.duplicate_dates == ()
    assert provider(tmp_path, NOW + timedelta(hours=1)).fetch("SPY").duplicate_dates == ()


def test_collapse_duplicate_dates_keeps_first_and_lists_dates() -> None:
    idx = pd.DatetimeIndex(
        ["2026-03-02", "2026-03-03", "2026-03-03", "2026-03-04", "2026-03-04", "2026-03-04"],
        name="date",
    )
    frame = pd.DataFrame({"close": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]}, index=idx)
    out, dups = collapse_duplicate_dates(frame)
    assert out["close"].tolist() == [1.0, 2.0, 4.0]
    assert dups == (date(2026, 3, 3), date(2026, 3, 4))
    assert len(frame) == 6  # input not mutated


def test_t118_bars_on_or_after_today_are_dropped(fake_yf: type[FakeTicker], tmp_path: Path) -> None:
    raw = raw_yahoo_frame(periods=8)  # Mon 03-02 .. Wed 03-11; NOW is Tue 03-10 in New York
    fake_yf.frame = raw
    history = provider(tmp_path).fetch("SPY")
    assert pd.Timestamp(history.frame.index[-1]).date() == date(2026, 3, 9)
    assert len(history.frame) == 6


def test_empty_frame_raises(fake_yf: type[FakeTicker], tmp_path: Path) -> None:
    # yfinance logs "possibly delisted" and returns an empty frame instead of raising.
    fake_yf.frame = pd.DataFrame(columns=["Open", "High", "Low", "Close", "Adj Close", "Volume"])
    with pytest.raises(PriceDataError, match="No price data"):
        provider(tmp_path).fetch("NOPE")
    assert not (tmp_path / "prices").exists()


def test_all_nan_frame_raises(fake_yf: type[FakeTicker], tmp_path: Path) -> None:
    raw = raw_yahoo_frame()
    raw[["Close", "Adj Close"]] = np.nan
    fake_yf.frame = raw
    with pytest.raises(PriceDataError, match="all-NaN"):
        provider(tmp_path).fetch("NOPE")


def test_only_todays_bar_raises(fake_yf: type[FakeTicker], tmp_path: Path) -> None:
    fake_yf.frame = raw_yahoo_frame(start="2026-03-10", periods=1)
    with pytest.raises(PriceDataError):
        provider(tmp_path).fetch("NEWIPO")


def test_missing_adj_close_raises(fake_yf: type[FakeTicker], tmp_path: Path) -> None:
    fake_yf.frame = raw_yahoo_frame().drop(columns=["Adj Close"])
    with pytest.raises(PriceDataError, match="Adj Close"):
        provider(tmp_path).fetch("SPY")


def test_yfinance_value_error_becomes_price_data_error(
    fake_yf: type[FakeTicker], tmp_path: Path
) -> None:
    fake_yf.raises = ValueError("Invalid ISIN number: ZZZZNOTREAL9")
    with pytest.raises(PriceDataError, match="rejected"):
        provider(tmp_path).fetch("ZZZZNOTREAL9")


# ---------------------------------------------------------------- ticker validation


@pytest.mark.parametrize(
    "bad",
    [
        "../x",
        "..\\x",
        "a/b",
        "/etc/passwd",
        "C:\\x",
        "",
        " ",
        "SPY ",
        "SP Y",
        "AAAAAAAAAAAAA",  # 13 characters
        ".hidden",
        "..",
        "A\x00B",
        "SPY;rm",
        "é",
    ],
)
def test_bad_tickers_are_rejected_before_any_io(
    bad: str, fake_yf: type[FakeTicker], tmp_path: Path
) -> None:
    with pytest.raises(PriceDataError, match="Invalid ticker"):
        validate_ticker(bad)
    with pytest.raises(PriceDataError, match="Invalid ticker"):
        provider(tmp_path).fetch(bad)
    assert fake_yf.calls == []
    assert not (tmp_path / "prices").exists()


@pytest.mark.parametrize("good", ["SPY", "brk-b", "BRK.B", "^GSPC", "EURUSD=X", "A"])
def test_good_tickers_are_accepted(good: str) -> None:
    assert validate_ticker(good) == good.upper()


# ---------------------------------------------------------------- cache


def test_cache_miss_then_hit(fake_yf: type[FakeTicker], tmp_path: Path) -> None:
    p = provider(tmp_path)
    first = p.fetch("SPY")
    path = tmp_path / "prices" / "SPY_2026-03-10.parquet"
    assert path.is_file()
    assert len(fake_yf.calls) == 1

    later = NOW + timedelta(hours=2)
    second = provider(tmp_path, later).fetch("SPY")
    assert len(fake_yf.calls) == 1  # served from disk
    pd.testing.assert_frame_equal(second.frame, first.frame, check_freq=False)
    assert second.fetched_at == first.fetched_at == NOW
    assert second.source == "yfinance"
    assert second.frame.attrs == {}
    assert list(path.parent.glob("*.tmp")) == []


def test_new_day_refetches_full_history_and_cleans_old_files(
    fake_yf: type[FakeTicker], tmp_path: Path
) -> None:
    cache = tmp_path / "prices"
    provider(tmp_path).fetch("SPY")
    provider(tmp_path).fetch("QQQ")
    other = cache / "SPYX_2026-03-09.parquet"  # different ticker sharing a prefix
    other.write_bytes(b"keep")
    assert (cache / "SPY_2026-03-10.parquet").is_file()

    tomorrow = NOW + timedelta(days=1)
    provider(tmp_path, tomorrow).fetch("SPY")
    assert len(fake_yf.calls) == 3
    assert (cache / "SPY_2026-03-11.parquet").is_file()
    assert not (cache / "SPY_2026-03-10.parquet").exists()
    assert (cache / "QQQ_2026-03-10.parquet").is_file()  # other tickers untouched
    assert other.read_bytes() == b"keep"


def test_corrupt_cache_file_is_refetched(fake_yf: type[FakeTicker], tmp_path: Path) -> None:
    cache = tmp_path / "prices"
    cache.mkdir()
    (cache / "SPY_2026-03-10.parquet").write_bytes(b"not parquet")
    history = provider(tmp_path).fetch("SPY")
    assert len(fake_yf.calls) == 1
    assert len(history.frame) == 6
    # The bad file was replaced by a readable one.
    assert len(pd.read_parquet(cache / "SPY_2026-03-10.parquet")) == 6


def test_failed_fetch_leaves_old_cache_alone(fake_yf: type[FakeTicker], tmp_path: Path) -> None:
    cache = tmp_path / "prices"
    provider(tmp_path).fetch("SPY")
    fake_yf.frame = pd.DataFrame()
    with pytest.raises(PriceDataError):
        provider(tmp_path, NOW + timedelta(days=1)).fetch("SPY")
    assert (cache / "SPY_2026-03-10.parquet").is_file()


def test_default_cache_dir_comes_from_settings(
    fake_yf: type[FakeTicker], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class StubSettings:
        data_dir = tmp_path / "datadir"

    monkeypatch.setattr(prices, "get_settings", lambda: StubSettings())
    YFinanceProvider(now=lambda: NOW).fetch("SPY")
    assert (tmp_path / "datadir" / "prices" / "SPY_2026-03-10.parquet").is_file()


def test_alpaca_is_a_stub() -> None:
    with pytest.raises(NotImplementedError, match="Alpaca is not used in v1"):
        AlpacaProvider().fetch("SPY")


# ---------------------------------------------------------------- total_returns


def history_from(adj: list[float], ticker: str = "XYZ") -> PriceHistory:
    idx = pd.bdate_range("2024-01-01", periods=len(adj), name="date")
    frame = pd.DataFrame(
        {
            "close": adj,
            "adj_close": adj,
            "dividends": 0.0,
            "splits": 0.0,
        },
        index=idx,
    )
    return PriceHistory(ticker, frame, NOW, "yfinance")


def test_total_returns_values_and_shape() -> None:
    h = history_from([100.0, 110.0, 99.0, 99.0])
    r = h.total_returns
    assert r.name == "XYZ"
    assert len(r) == 3  # first row dropped
    assert r.index[0] == h.frame.index[1]
    np.testing.assert_allclose(r.to_numpy(), [0.10, -0.10, 0.0])


def test_total_returns_uses_adj_close_not_close() -> None:
    h = history_from([100.0, 110.0])
    frame = h.frame.copy()
    frame["close"] = [100.0, 150.0]
    r = PriceHistory("XYZ", frame, NOW, "yfinance").total_returns
    np.testing.assert_allclose(r.to_numpy(), [0.10])


def test_total_returns_never_zero_fills_nan() -> None:
    h = history_from([100.0, np.nan, 120.0, 132.0])
    r = h.total_returns
    assert len(r) == 3
    assert r.isna().sum() == 2  # the NaN day and the day after it; not filled with 0
    assert not (r == 0.0).any()
    np.testing.assert_allclose(r.iloc[2], 0.10)


def test_price_history_is_frozen() -> None:
    h = history_from([1.0, 2.0])
    with pytest.raises(AttributeError):
        h.ticker = "OTHER"  # type: ignore[misc]


# ---------------------------------------------------------------- live


@pytest.mark.live
def test_live_spy_history(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO)
    history = YFinanceProvider(cache_dir=tmp_path / "prices").fetch("SPY")
    frame = history.frame
    first = pd.Timestamp(frame.index[0]).date()
    last = pd.Timestamp(frame.index[-1]).date()
    report = audit_prices(frame)

    logger.info("SPY rows=%d first=%s last=%s ok=%s", len(frame), first, last, report.ok)
    for f in report.findings:
        logger.info("AUDIT [%s] %s: %s (%d dates)", f.severity, f.code, f.message, len(f.dates))

    assert len(frame) >= 7000
    assert first <= date(1993, 2, 1)
    assert (frame["close"] > 0).all()
    assert frame.index.is_unique and frame.index.is_monotonic_increasing
    assert history.total_returns.notna().sum() > 7000
