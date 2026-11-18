"""Price data layer: yfinance provider, same-day parquet cache, total-return series.

Every rule below is a researched yfinance pitfall (see docs/PLAN.md, "Prices").
"""

from __future__ import annotations

import logging
import os
import re
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Protocol

import numpy as np
import pandas as pd

from factordesk.config import get_settings

logger = logging.getLogger(__name__)

SOURCE_YFINANCE = "yfinance"

# Strict symbol check. The ticker ends up in a filename and a request, so path separators,
# whitespace and anything else exotic must never get through.
_TICKER_RE = re.compile(r"^[A-Za-z0-9.^=-]{1,12}$")

# yfinance column -> our column. "Capital Gains" is only present for some funds.
_COLUMN_MAP: dict[str, str] = {
    "Close": "close",
    "Adj Close": "adj_close",
    "Dividends": "dividends",
    "Stock Splits": "splits",
    "Capital Gains": "capital_gains",
    "Volume": "volume",
}
_COLUMN_ORDER = ("close", "adj_close", "dividends", "splits", "capital_gains", "volume")
_ZERO_FILLED = ("dividends", "splits", "capital_gains")


class PriceDataError(Exception):
    """Raised for an invalid ticker, no data, or an all-NaN price history."""


@dataclass(frozen=True)
class PriceHistory:
    """Daily price history for one ticker.

    ``frame`` has a tz-naive, normalized, increasing, unique ``date`` index and float columns
    ``close``, ``adj_close``, ``dividends``, ``splits`` (0.0 when none). ``capital_gains`` and
    ``volume`` are present when the source provides them. ``duplicate_dates`` lists every date
    the source delivered more than once; the first bar of each was kept and the audit reports
    them as an error (methodology M1.3, D29).
    """

    ticker: str
    frame: pd.DataFrame
    fetched_at: datetime  # UTC
    source: str
    duplicate_dates: tuple[date, ...] = ()

    @property
    def total_returns(self) -> pd.Series:
        """Simple daily total return from ``adj_close``, named after the ticker.

        The first row (no prior price) is dropped. Missing prices stay NaN: they are never
        filled with 0, which would fabricate a flat day. A zero or negative price is treated as
        missing (methodology M1.3), so it cannot produce a finite but meaningless return.
        """
        adj = self.frame["adj_close"].astype("float64")
        adj = adj.where(adj > 0)  # NaN stays NaN; non-positive becomes NaN (M1.3)
        # Explicit ratio instead of pct_change(): no implicit forward-fill of NaN prices.
        returns = (adj / adj.shift(1) - 1.0).iloc[1:]
        returns.name = self.ticker
        return returns


class PriceProvider(Protocol):
    def fetch(self, ticker: str) -> PriceHistory: ...


def validate_ticker(ticker: str) -> str:
    """Return the upper-cased ticker or raise PriceDataError if it is not a safe symbol."""
    if not isinstance(ticker, str) or not _TICKER_RE.fullmatch(ticker):  # pyright: ignore[reportUnnecessaryIsInstance]
        raise PriceDataError(f"Invalid ticker symbol: {ticker!r}")
    if ticker.startswith("."):
        raise PriceDataError(f"Invalid ticker symbol: {ticker!r}")
    return ticker.upper()


def _download_history(ticker: str) -> pd.DataFrame:
    """Thin typed wrapper over yfinance (whose surface is untyped).

    Ticker.history() returns single-level columns reliably (yf.download needs
    multi_level_index=False and has changed shape between releases). Every argument is explicit
    because yfinance flipped defaults in 0.2.51 (auto_adjust now True by default):
      * auto_adjust=False: keep both Close and Adj Close.
      * actions=True: include Dividends / Stock Splits (/ Capital Gains) for the audit.
      * repair=False: yfinance's repair has produced 100x errors of its own; the audit reports
        problems instead of silently "fixing" them.
    No requests_cache session is passed: yfinance uses curl_cffi and rejects such sessions.
    """
    # yfinance ships no type stubs; imported lazily to keep module import cheap and tests offline.
    import yfinance as yf  # pyright: ignore[reportMissingTypeStubs]

    try:
        ticker_obj = yf.Ticker(ticker)  # pyright: ignore[reportUnknownMemberType]
        raw = ticker_obj.history(  # pyright: ignore[reportUnknownMemberType]
            period="max",
            interval="1d",
            auto_adjust=False,
            actions=True,
            repair=False,
        )
    except ValueError as exc:  # e.g. 12-char symbols are parsed as ISINs and rejected
        raise PriceDataError(f"yfinance rejected ticker {ticker!r}: {exc}") from exc
    return pd.DataFrame(raw)  # pyright: ignore[reportUnknownArgumentType]


def collapse_duplicate_dates(frame: pd.DataFrame) -> tuple[pd.DataFrame, tuple[date, ...]]:
    """Keep the first bar of every repeated date; return the frame and the repeated dates.

    The input is not mutated. The dates are reported by the audit (A1 ``duplicate_index``),
    never dropped silently (methodology M1.3, D29).
    """
    if frame.index.is_unique:
        return frame, ()
    repeated = frame.index[frame.index.duplicated(keep="first")]
    dates = tuple(sorted({pd.Timestamp(ts).date() for ts in repeated}))
    return frame.loc[~frame.index.duplicated(keep="first")].copy(), dates


def normalize_frame(
    raw: pd.DataFrame, ticker: str, now_utc: datetime
) -> tuple[pd.DataFrame, tuple[date, ...]]:
    """Turn a raw yfinance frame into the canonical frame (see PriceHistory).

    Returns the frame and the dates that the source delivered more than once (first bar kept).
    """
    # yfinance logs (does not raise) for unknown/delisted symbols and returns an empty frame.
    if raw.empty:
        raise PriceDataError(f"No price data returned for {ticker!r} (invalid or delisted?)")
    if not isinstance(raw.index, pd.DatetimeIndex):
        raise PriceDataError(f"Unexpected index type for {ticker!r}: {type(raw.index).__name__}")
    for needed in ("Close", "Adj Close"):
        if needed not in raw.columns:
            raise PriceDataError(f"Price data for {ticker!r} is missing the {needed!r} column")

    index = raw.index
    # "Today" in the exchange timezone, taken before the tz is dropped.
    if index.tz is not None:
        today = pd.Timestamp(now_utc).tz_convert(index.tz).date()
        # tz_localize(None) keeps the exchange wall-clock date (midnight local); converting to
        # UTC first would shift US dates back by one day.
        index = index.tz_localize(None)
    else:
        today = now_utc.date()
    index = index.normalize()

    columns = {src: dst for src, dst in _COLUMN_MAP.items() if src in raw.columns}
    frame = pd.DataFrame(raw[list(columns)].to_numpy(dtype="float64"), index=index)
    frame.columns = pd.Index([columns[c] for c in columns])
    frame.index.name = "date"
    for col in ("dividends", "splits"):
        if col not in frame.columns:
            frame[col] = 0.0
    for col in _ZERO_FILLED:
        if col in frame.columns:
            # NaN in an actions column means "no action that day", not missing data.
            frame[col] = frame[col].fillna(0.0)

    if not frame.index.is_monotonic_increasing:
        frame = frame.sort_index(kind="stable")  # stable: repeated dates keep vendor order

    # Today's bar is incomplete while the session is open, and a bar dated after today can only
    # come from clock skew or a vendor error: drop every row dated today or later (M1.3, D27).
    late = np.asarray(pd.DatetimeIndex(frame.index) >= pd.Timestamp(today), dtype=bool)
    if late.any():
        logger.info("%s: dropping %d bar(s) dated %s or later", ticker, int(late.sum()), today)
        frame = frame.loc[~late]

    # Yahoo occasionally repeats a bar. Keep the first and record the date for the audit (D29).
    frame, duplicates = collapse_duplicate_dates(frame)
    if duplicates:
        logger.warning(
            "%s: %d date(s) delivered more than once; first bar kept, reported by the audit",
            ticker,
            len(duplicates),
        )

    if frame.empty or frame["close"].isna().all() or frame["adj_close"].isna().all():
        raise PriceDataError(f"Price data for {ticker!r} is empty or all-NaN")

    # NOTE: Yahoo's Close is ALREADY split-adjusted. Never multiply by `splits`; that column
    # is only used by the audit to detect a missing split adjustment.
    order = [c for c in _COLUMN_ORDER if c in frame.columns]
    return frame[order].astype("float64"), duplicates


def _atomic_write_parquet(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".", suffix=".tmp")
    os.close(fd)
    tmp = Path(tmp_name)
    try:
        frame.to_parquet(tmp)
        os.replace(tmp, path)  # atomic on the same filesystem
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


class YFinanceProvider:
    """Fetches full daily history from Yahoo Finance with a same-day parquet cache."""

    def __init__(
        self,
        cache_dir: Path | None = None,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._cache_dir = cache_dir
        self._now: Callable[[], datetime] = now or (lambda: datetime.now(UTC))

    @property
    def cache_dir(self) -> Path:
        return (
            self._cache_dir
            if self._cache_dir is not None
            else (Path(get_settings().data_dir) / "prices")
        )

    def _cache_path(self, ticker: str, day: date) -> Path:
        return self.cache_dir / f"{ticker}_{day.isoformat()}.parquet"

    def _cleanup_old(self, ticker: str, keep: Path) -> None:
        pattern = re.compile(rf"^{re.escape(ticker)}_\d{{4}}-\d{{2}}-\d{{2}}\.parquet$")
        if not self.cache_dir.is_dir():
            return
        for path in self.cache_dir.iterdir():
            if path != keep and pattern.fullmatch(path.name):
                logger.info("Removing stale price cache %s", path.name)
                path.unlink(missing_ok=True)

    def _read_cache(self, ticker: str, path: Path) -> PriceHistory | None:
        if not path.is_file():
            return None
        try:
            frame = pd.read_parquet(path)
            fetched_raw = str(frame.attrs.get("fetched_at", ""))
            fetched_at = (
                datetime.fromisoformat(fetched_raw)
                if fetched_raw
                else datetime.fromtimestamp(path.stat().st_mtime, UTC)
            )
            dup_raw = str(frame.attrs.get("duplicate_dates", ""))
            duplicates = tuple(date.fromisoformat(d) for d in dup_raw.split(",") if d)
            frame.attrs = {}
            if not isinstance(frame.index, pd.DatetimeIndex) or "adj_close" not in frame.columns:
                raise ValueError("unexpected cache layout")
        except Exception:
            logger.warning("Unreadable price cache %s; refetching", path.name, exc_info=True)
            return None
        logger.info("Price cache hit for %s", ticker)
        return PriceHistory(ticker, frame, fetched_at, SOURCE_YFINANCE, duplicates)

    def fetch(self, ticker: str) -> PriceHistory:
        symbol = validate_ticker(ticker)
        now_utc = self._now()
        path = self._cache_path(symbol, now_utc.date())
        cached = self._read_cache(symbol, path)
        if cached is not None:
            return cached

        # Always the full history: adjusted history is rewritten at every dividend, so
        # appending increments to an older download would mix adjustment bases.
        raw = _download_history(symbol)
        frame, duplicates = normalize_frame(raw, symbol, now_utc)

        to_store = frame.copy()
        to_store.attrs["fetched_at"] = now_utc.isoformat()
        to_store.attrs["duplicate_dates"] = ",".join(d.isoformat() for d in duplicates)
        try:
            _atomic_write_parquet(to_store, path)
            self._cleanup_old(symbol, keep=path)
        except OSError:
            logger.warning("Could not write price cache for %s", symbol, exc_info=True)
        return PriceHistory(symbol, frame, now_utc, SOURCE_YFINANCE, duplicates)


class AlpacaProvider:
    """Adapter stub. Alpaca keys exist in config but the provider is not used in v1."""

    def fetch(self, ticker: str) -> PriceHistory:
        raise NotImplementedError("Alpaca is not used in v1")
