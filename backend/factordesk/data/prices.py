"""Price data layer: yfinance provider, same-day parquet cache, total-return series.

Every rule below is a researched yfinance pitfall (see docs/PLAN.md, "Prices").
"""

from __future__ import annotations

import logging
import os
import random
import re
import tempfile
import threading
import time
from collections.abc import Callable, Sequence
from concurrent.futures import Executor, ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Literal, Protocol

import numpy as np
import pandas as pd

from factordesk.config import get_settings
from factordesk.data.throttle import (
    RATE_LIMIT_MESSAGE,
    BatchSettings,
    CircuitBreaker,
    JitterSource,
    RateLimiter,
    backoff_delay,
    is_rate_limited,
    is_transient,
    retry_after_seconds,
)

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


FailureReason = Literal[
    "invalid_ticker",  # not a safe symbol; no request was made
    "no_data",  # Yahoo answered but the history is missing, empty or unusable
    "rate_limited",  # Yahoo kept limiting this ticker until the attempts ran out
    "skipped_rate_limited",  # never requested: the batch stopped after repeated rate limits
    "network",  # timeouts or connection errors until the attempts ran out
    "unexpected",  # anything else; logged with its traceback
]


@dataclass(frozen=True)
class PriceFailure:
    """Why one ticker has no history: a reason code and one plain sentence."""

    ticker: str
    reason: FailureReason
    message: str


@dataclass(frozen=True)
class TickerOutcome:
    """The result for one ticker: exactly one of ``history`` or ``failure``."""

    ticker: str
    history: PriceHistory | None = None
    failure: PriceFailure | None = None
    from_cache: bool = False

    def __post_init__(self) -> None:
        if (self.history is None) == (self.failure is None):
            raise ValueError("a TickerOutcome holds exactly one of history or failure")


@dataclass(frozen=True)
class BatchResult:
    """Everything a multi-ticker download produced, in the order the tickers were asked for.

    ``outcomes`` has one entry per distinct ticker (first occurrence order, including invalid
    ones). Repeated tickers are not downloaded twice; they are listed in ``duplicates`` so
    nothing disappears silently.
    """

    outcomes: tuple[TickerOutcome, ...]
    duplicates: tuple[str, ...]
    elapsed_seconds: float

    @property
    def histories(self) -> dict[str, PriceHistory]:
        return {o.ticker: o.history for o in self.outcomes if o.history is not None}

    @property
    def failures(self) -> tuple[PriceFailure, ...]:
        return tuple(o.failure for o in self.outcomes if o.failure is not None)

    @property
    def cache_hits(self) -> int:
        return sum(1 for o in self.outcomes if o.history is not None and o.from_cache)

    @property
    def downloaded(self) -> int:
        return sum(1 for o in self.outcomes if o.history is not None and not o.from_cache)

    @property
    def skipped(self) -> int:
        return sum(1 for f in self.failures if f.reason == "skipped_rate_limited")

    @property
    def failed(self) -> int:
        return len(self.failures) - self.skipped

    @property
    def rate_limited(self) -> bool:
        return any(f.reason in ("rate_limited", "skipped_rate_limited") for f in self.failures)

    @property
    def message(self) -> str | None:
        """A plain-words note for the user when Yahoo limited the batch, else None."""
        return RATE_LIMIT_MESSAGE if self.rate_limited else None


class BatchPriceProvider(Protocol):
    def fetch_many(self, tickers: Sequence[str]) -> BatchResult: ...


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
    """Fetches full daily history from Yahoo Finance with a same-day parquet cache.

    ``fetch`` loads one ticker. ``fetch_many`` loads several in small chunks on a few threads
    with spaced requests, retries and a circuit breaker (see data/throttle.py).
    """

    def __init__(
        self,
        cache_dir: Path | None = None,
        now: Callable[[], datetime] | None = None,
        *,
        settings: BatchSettings | None = None,
        download: Callable[[str], pd.DataFrame] | None = None,
        monotonic: Callable[[], float] | None = None,
        sleep: Callable[[float], None] | None = None,
        rng: JitterSource | None = None,
        executor_factory: Callable[[int], Executor] | None = None,
    ) -> None:
        self._cache_dir = cache_dir
        self._now: Callable[[], datetime] = now or (lambda: datetime.now(UTC))
        self._settings = settings
        self._download: Callable[[str], pd.DataFrame] = download or _download_history
        self._monotonic: Callable[[], float] = monotonic or time.monotonic
        self._sleep: Callable[[float], None] = sleep or time.sleep
        self._rng: JitterSource = rng or random.Random()
        self._executor_factory: Callable[[int], Executor] = executor_factory or (
            lambda workers: ThreadPoolExecutor(max_workers=workers, thread_name_prefix="prices")
        )
        self._locks_guard = threading.Lock()
        self._symbol_locks: dict[str, threading.Lock] = {}

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

    def _normalize_and_store(
        self, raw: pd.DataFrame, symbol: str, now_utc: datetime, path: Path
    ) -> PriceHistory:
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

    def fetch(self, ticker: str) -> PriceHistory:
        symbol = validate_ticker(ticker)
        now_utc = self._now()
        path = self._cache_path(symbol, now_utc.date())
        cached = self._read_cache(symbol, path)
        if cached is not None:
            return cached

        # Always the full history: adjusted history is rewritten at every dividend, so
        # appending increments to an older download would mix adjustment bases.
        raw = self._download(symbol)
        return self._normalize_and_store(raw, symbol, now_utc, path)

    # ------------------------------------------------------------ batch download

    def _symbol_lock(self, symbol: str) -> threading.Lock:
        with self._locks_guard:
            return self._symbol_locks.setdefault(symbol, threading.Lock())

    def fetch_many(self, tickers: Sequence[str]) -> BatchResult:
        """Load several tickers: cache first, then chunked, spaced, retried downloads.

        Every distinct ticker gets an outcome, in first-seen order. One bad ticker never fails
        the batch; a rate limit that persists stops new requests and reports the rest as
        skipped. Each ticker is still one full-history request (adjustment base unchanged).
        """
        started = self._monotonic()
        settings = self._settings or _settings_from_config()

        outcomes: dict[str, TickerOutcome] = {}
        order: list[str] = []
        duplicates: list[str] = []
        valid: set[str] = set()
        for raw_ticker in tickers:
            try:
                key = validate_ticker(raw_ticker)
                valid.add(key)
            except PriceDataError as exc:
                key = str(raw_ticker)
                if key not in outcomes:
                    outcomes[key] = _failed(key, "invalid_ticker", str(exc))
            if key in order:
                duplicates.append(key)
            else:
                order.append(key)

        now_utc = self._now()
        misses: list[str] = []
        for symbol in order:
            if symbol not in valid:
                continue
            cached = self._read_cache(symbol, self._cache_path(symbol, now_utc.date()))
            if cached is not None:
                outcomes[symbol] = TickerOutcome(symbol, history=cached, from_cache=True)
            else:
                misses.append(symbol)

        if misses:
            limiter = RateLimiter(
                settings.min_interval_seconds, self._monotonic, self._sleep, self._rng
            )
            breaker = CircuitBreaker(settings.breaker_threshold)
            size = settings.chunk_size
            chunks = [misses[i : i + size] for i in range(0, len(misses), size)]
            workers = min(settings.max_workers, len(chunks))

            def run_chunk(chunk: list[str]) -> list[TickerOutcome]:
                return [
                    self._download_one(symbol, now_utc, settings, limiter, breaker)
                    for symbol in chunk
                ]

            with self._executor_factory(workers) as pool:
                for chunk_outcomes in pool.map(run_chunk, chunks):
                    for outcome in chunk_outcomes:
                        outcomes[outcome.ticker] = outcome

        result = BatchResult(
            outcomes=tuple(outcomes[key] for key in order),
            duplicates=tuple(duplicates),
            elapsed_seconds=self._monotonic() - started,
        )
        logger.info(
            "Price batch: %d from cache, %d downloaded, %d failed, %d skipped in %.2fs",
            result.cache_hits,
            result.downloaded,
            result.failed,
            result.skipped,
            result.elapsed_seconds,
        )
        return result

    def _download_one(
        self,
        symbol: str,
        now_utc: datetime,
        settings: BatchSettings,
        limiter: RateLimiter,
        breaker: CircuitBreaker,
    ) -> TickerOutcome:
        """Download one ticker with retries. Never raises for a data or network problem."""
        path = self._cache_path(symbol, now_utc.date())
        with self._symbol_lock(symbol):  # the same ticker twice at once downloads once
            cached = self._read_cache(symbol, path)
            if cached is not None:
                return TickerOutcome(symbol, history=cached, from_cache=True)

            for attempt in range(1, settings.max_attempts + 1):
                if breaker.tripped:
                    return _failed(symbol, "skipped_rate_limited", RATE_LIMIT_MESSAGE)
                limiter.wait()
                try:
                    raw = self._download(symbol)
                    history = self._normalize_and_store(raw, symbol, now_utc, path)
                except PriceDataError as exc:
                    breaker.record_answered()  # Yahoo replied; the problem is this ticker
                    return _failed(symbol, "no_data", str(exc))
                except Exception as exc:
                    # Sorted into a typed failure below; nothing is swallowed.
                    if is_rate_limited(exc):
                        tripped = breaker.record_rate_limited()
                        if tripped or attempt == settings.max_attempts:
                            logger.warning("%s: rate limited by Yahoo (try %d)", symbol, attempt)
                            return _failed(symbol, "rate_limited", RATE_LIMIT_MESSAGE)
                    elif is_transient(exc):
                        if attempt == settings.max_attempts:
                            logger.warning("%s: network error, giving up", symbol, exc_info=True)
                            return _failed(
                                symbol,
                                "network",
                                f"Could not reach Yahoo for {symbol} after {attempt} tries. "
                                "Check the connection and try again.",
                            )
                    else:
                        logger.warning("%s: unexpected download error", symbol, exc_info=True)
                        return _failed(
                            symbol,
                            "unexpected",
                            f"Downloading {symbol} failed unexpectedly ({type(exc).__name__}).",
                        )
                    self._sleep(backoff_delay(attempt, retry_after_seconds(exc), self._rng))
                else:
                    breaker.record_answered()
                    return TickerOutcome(symbol, history=history)
            # The last attempt always returns above; kept so a later change to the loop cannot
            # fall through silently.
            return _failed(symbol, "unexpected", f"Downloading {symbol} did not finish.")


def _failed(ticker: str, reason: FailureReason, message: str) -> TickerOutcome:
    return TickerOutcome(ticker, failure=PriceFailure(ticker, reason, message))


def _settings_from_config() -> BatchSettings:
    cfg = get_settings()
    return BatchSettings(
        chunk_size=cfg.price_chunk_size,
        max_workers=cfg.price_max_workers,
        min_interval_seconds=cfg.price_min_interval_seconds,
        max_attempts=cfg.price_max_attempts,
        breaker_threshold=cfg.price_breaker_threshold,
    )


class AlpacaProvider:
    """Adapter stub. Alpaca keys exist in config but the provider is not used in v1."""

    def fetch(self, ticker: str) -> PriceHistory:
        raise NotImplementedError("Alpaca is not used in v1")
