"""Price data layer: yfinance provider, same-day parquet cache, total-return series.

Every rule below is a researched yfinance pitfall (see docs/PLAN.md, "Prices").
"""

from __future__ import annotations

import dataclasses
import json
import logging
import os
import random
import re
import tempfile
import threading
import time
from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import Executor, ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Final, Literal, Protocol, cast, runtime_checkable
from zoneinfo import ZoneInfo

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


SECURITY_MAX_AGE = timedelta(days=7)
"""A cached security record is refreshed when it is older than this."""

SUPPORTED_CURRENCY = "USD"
"""The only quote currency accepted until European factors exist (roadmap N1)."""


@dataclass(frozen=True)
class Security:
    """What Yahoo says a ticker is: company name, quote currency, exchange and quote type.

    Every field is optional because Yahoo omits any of them for some symbols.
    """

    name: str | None = None
    currency: str | None = None
    exchange: str | None = None
    quote_type: str | None = None


class UnsupportedCurrencyError(Exception):
    """The ticker is quoted in a currency other than US dollars (roadmap N1, methodology M1.5)."""

    def __init__(self, ticker: str, currency: str) -> None:
        self.ticker = ticker
        self.currency = currency
        super().__init__(
            f"Only tickers quoted in US dollars are supported for now. "
            f"{ticker} is quoted in {currency}."
        )


def check_currency(ticker: str, security: Security | None) -> None:
    """Raise ``UnsupportedCurrencyError`` when the currency is known and is not USD.

    An unknown currency (no metadata, or no currency in it) passes: the check refuses only on
    evidence. Pence quotes (``GBp``, ``GBX``) are not USD, so they are refused like any other.
    """
    currency = None if security is None else security.currency
    if currency is not None and currency.strip().upper() != SUPPORTED_CURRENCY:
        raise UnsupportedCurrencyError(ticker, currency.strip())


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
    full_downloaded_at: datetime | None = None
    """When the whole history was last downloaded in one piece (UTC). Incremental refreshes keep
    it; ``None`` for a cache written before the stamp existed."""

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


class SecurityProvider(Protocol):
    """Optional second capability of a price provider: the metadata of a ticker, never raising."""

    def fetch_security(self, ticker: str) -> Security | None: ...


def security_of(provider: object, ticker: str) -> Security | None:
    """The security record of ``ticker`` from ``provider``, or None.

    None when the provider has no ``fetch_security`` (a fake or an adapter without metadata) or
    when the read fails for any reason: metadata never blocks a report.
    """
    fetch = getattr(provider, "fetch_security", None)
    if not callable(fetch):
        return None
    try:
        found: object = fetch(ticker)
    except Exception:
        logger.warning("Security metadata read for %s failed", ticker, exc_info=True)
        return None
    return found if isinstance(found, Security) else None


RefreshAction = Literal["cached", "incremental", "full", "stale"]
"""What ``fetch_incremental`` did: ``cached`` no network call, ``incremental`` only the new days,
``full`` the whole history, ``stale`` the refresh failed and the older cache was served."""


@dataclass(frozen=True)
class HistoryRefresh:
    """The result of ``fetch_incremental``: the history, what was done, and a note on a failure."""

    history: PriceHistory
    action: RefreshAction
    note: str | None = None
    """Set exactly when ``action`` is ``stale``: where the data ends and why it is not newer."""


@runtime_checkable
class IncrementalPriceProvider(Protocol):
    """A provider that can bring a cached history up to date by fetching only the new days."""

    def fetch_incremental(self, ticker: str) -> HistoryRefresh: ...


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
    """Full daily history through ``_yf_history`` (``period="max"``)."""
    return _yf_history(ticker, period="max")


def _download_history_bounded(ticker: str) -> pd.DataFrame:
    """Full daily history with the short timeout of a refresh that has a cache to fall back on."""
    return _yf_history(ticker, timeout=REFRESH_FULL_TIMEOUT_SECONDS, period="max")


def _download_history_since(ticker: str, start: date) -> pd.DataFrame:
    """Daily history from ``start`` (inclusive), with the short timeout of a refresh.

    Only the incremental refresh asks for a window, and it always has a cache to fall back on.
    """
    return _yf_history(ticker, timeout=REFRESH_TIMEOUT_SECONDS, start=start.isoformat())


def _yf_history(ticker: str, *, timeout: float | None = None, **window: str) -> pd.DataFrame:
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
            **window,
            **({} if timeout is None else {"timeout": timeout}),
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


def _download_info(ticker: str) -> Mapping[str, object]:
    """Yahoo's quote summary for one ticker (one request; yfinance 1.8.0 ``Ticker.get_info``).

    ``fast_info`` is cheaper but has no company name; ``get_info`` has ``longName``,
    ``shortName``, ``currency``, ``exchange``, ``fullExchangeName`` and ``quoteType``.
    """
    import yfinance as yf  # pyright: ignore[reportMissingTypeStubs]

    info = cast(object, yf.Ticker(ticker).get_info())  # pyright: ignore[reportUnknownMemberType]
    return cast(Mapping[str, object], info) if isinstance(info, Mapping) else {}


def _clean(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    text = " ".join(value.split())
    return text or None


EXCHANGE_LABELS: Final[Mapping[str, str]] = {
    "NMS": "NASDAQ",
    "NGM": "NASDAQ",
    "NCM": "NASDAQ",
    "NasdaqGS": "NASDAQ",
    "NasdaqGM": "NASDAQ",
    "NasdaqCM": "NASDAQ",
    "NYQ": "NYSE",
    "NYSE": "NYSE",
    "ASE": "NYSE American",
    "NYSE American": "NYSE American",
    "PCX": "NYSE Arca",
    "NYSEArca": "NYSE Arca",
    "NYSE Arca": "NYSE Arca",
    "BTS": "Cboe BZX",
    "Cboe BZX": "Cboe BZX",
    "BATS": "Cboe BZX",
}
"""Yahoo exchange values (short codes and full names) to the label a reader sees (DV2.2)."""


def exchange_label(exchange: str | None) -> str | None:
    """The reader label of a Yahoo exchange value; a value not in the table is returned as given."""
    return None if exchange is None else EXCHANGE_LABELS.get(exchange, exchange)


def security_from_info(info: Mapping[str, object]) -> Security | None:
    """The ``Security`` in a Yahoo quote summary; None when it holds none of its fields.

    The name is ``longName``, else ``shortName``. The exchange is the readable
    ``fullExchangeName`` (for example ``NasdaqGS``), else the short ``exchange`` code.
    """
    found = Security(
        name=_clean(info.get("longName")) or _clean(info.get("shortName")),
        currency=_clean(info.get("currency")),
        exchange=exchange_label(
            _clean(info.get("fullExchangeName")) or _clean(info.get("exchange"))
        ),
        quote_type=_clean(info.get("quoteType")),
    )
    return found if found != Security() else None


def _security_path(cache_dir: Path, ticker: str) -> Path:
    return cache_dir / f"{ticker}_security.json"


def _read_security_file(path: Path) -> tuple[Security, datetime] | None:
    """The record and its fetch time from a cache file; None when absent or unreadable."""
    try:
        raw = cast(object, json.loads(path.read_text(encoding="utf-8")))
        if not isinstance(raw, dict):
            raise ValueError("not an object")
        fields = cast(dict[str, object], raw)
        fetched = datetime.fromisoformat(str(fields["fetched_at"]))
        if fetched.tzinfo is None:
            fetched = fetched.replace(tzinfo=UTC)
        security = Security(
            name=_clean(fields.get("name")),
            currency=_clean(fields.get("currency")),
            exchange=exchange_label(_clean(fields.get("exchange"))),
            quote_type=_clean(fields.get("quote_type")),
        )
    except FileNotFoundError:
        return None
    except (OSError, ValueError, KeyError):
        logger.warning("Unreadable security cache %s; ignoring it", path.name, exc_info=True)
        return None
    return security, fetched


def read_cached_security(cache_dir: Path, ticker: str) -> Security | None:
    """The cached security record of ``ticker`` whatever its age; no network, never raises."""
    found = _read_security_file(_security_path(cache_dir, ticker))
    return None if found is None else found[0]


def _atomic_write_text(text: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".", suffix=".tmp")
    os.close(fd)
    tmp = Path(tmp_name)
    try:
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


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
        info: Callable[[str], Mapping[str, object]] | None = None,
        download_since: Callable[[str, date], pd.DataFrame] | None = None,
        monotonic: Callable[[], float] | None = None,
        sleep: Callable[[float], None] | None = None,
        rng: JitterSource | None = None,
        executor_factory: Callable[[int], Executor] | None = None,
    ) -> None:
        self._cache_dir = cache_dir
        self._now: Callable[[], datetime] = now or (lambda: datetime.now(UTC))
        self._settings = settings
        self._download: Callable[[str], pd.DataFrame] = download or _download_history
        self._info: Callable[[str], Mapping[str, object]] = info or _download_info
        self._download_bounded: Callable[[str], pd.DataFrame] = (
            download or _download_history_bounded
        )
        self._download_since: Callable[[str, date], pd.DataFrame] = (
            download_since or _download_history_since
        )
        self._monotonic: Callable[[], float] = monotonic or time.monotonic
        self._sleep: Callable[[float], None] = sleep or time.sleep
        self._rng: JitterSource = rng or random.Random()
        self._executor_factory: Callable[[int], Executor] = executor_factory or (
            lambda workers: ThreadPoolExecutor(max_workers=workers, thread_name_prefix="prices")
        )
        self._locks_guard = threading.Lock()
        self._symbol_locks: dict[str, threading.Lock] = {}
        self._security_limiter: RateLimiter | None = None

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
            full_raw = str(frame.attrs.get("full_downloaded_at", ""))
            full_at = datetime.fromisoformat(full_raw) if full_raw else None
            frame.attrs = {}
            if not isinstance(frame.index, pd.DatetimeIndex) or "adj_close" not in frame.columns:
                raise ValueError("unexpected cache layout")
        except Exception:
            logger.warning("Unreadable price cache %s; refetching", path.name, exc_info=True)
            return None
        logger.info("Price cache hit for %s", ticker)
        return PriceHistory(ticker, frame, fetched_at, SOURCE_YFINANCE, duplicates, full_at)

    def _store(
        self,
        frame: pd.DataFrame,
        duplicates: tuple[date, ...],
        symbol: str,
        now_utc: datetime,
        path: Path,
        full_at: datetime | None,
    ) -> None:
        """Write ``frame`` as the cache of ``symbol`` for ``path``'s day; failures are logged.

        ``full_at`` is when the history was last downloaded whole (``None`` if unknown).
        """
        to_store = frame.copy()
        to_store.attrs["fetched_at"] = now_utc.isoformat()
        if full_at is not None:
            to_store.attrs["full_downloaded_at"] = full_at.isoformat()
        to_store.attrs["duplicate_dates"] = ",".join(d.isoformat() for d in duplicates)
        try:
            _atomic_write_parquet(to_store, path)
            self._cleanup_old(symbol, keep=path)
        except OSError:
            logger.warning("Could not write price cache for %s", symbol, exc_info=True)

    def _normalize_and_store(
        self, raw: pd.DataFrame, symbol: str, now_utc: datetime, path: Path
    ) -> PriceHistory:
        frame, duplicates = normalize_frame(raw, symbol, now_utc)
        self._store(frame, duplicates, symbol, now_utc, path, now_utc)
        return PriceHistory(symbol, frame, now_utc, SOURCE_YFINANCE, duplicates, now_utc)

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

    # ------------------------------------------------------------ security metadata

    def fetch_security(self, ticker: str) -> Security | None:
        """Company name, currency, exchange and quote type of ``ticker``; None when unknown.

        Cached as ``{TICKER}_security.json`` next to the price cache and refreshed after
        ``SECURITY_MAX_AGE``. The read obeys the price settings (spacing, attempts, backoff,
        breaker) and NEVER raises or blocks a report: an invalid ticker, a throttled or failed
        read, or an answer with none of the fields returns None (a stale cached record is
        returned instead when there is one).
        """
        try:
            symbol = validate_ticker(ticker)
        except PriceDataError:
            return None
        now_utc = self._now()
        path = _security_path(self.cache_dir, symbol)
        cached = _read_security_file(path)
        if cached is not None and now_utc - cached[1] < SECURITY_MAX_AGE:
            logger.info("Security cache hit for %s", symbol)
            return cached[0]
        try:
            with self._symbol_lock(symbol):
                found = self._download_security(symbol)
        except Exception:
            logger.warning("%s: security metadata read failed", symbol, exc_info=True)
            found = None
        if found is None:
            return None if cached is None else cached[0]
        record = {"fetched_at": now_utc.isoformat(), **dataclasses.asdict(found)}
        try:
            _atomic_write_text(json.dumps(record, ensure_ascii=False), path)
        except OSError:
            logger.warning("Could not write security cache for %s", symbol, exc_info=True)
        return found

    def _download_security(self, symbol: str) -> Security | None:
        """One metadata read with the price settings' retries; None on any failure."""
        settings = self._settings or _settings_from_config()
        with self._locks_guard:
            if self._security_limiter is None:
                self._security_limiter = RateLimiter(
                    settings.min_interval_seconds, self._monotonic, self._sleep, self._rng
                )
            limiter = self._security_limiter
        breaker = CircuitBreaker(settings.breaker_threshold)
        for attempt in range(1, settings.max_attempts + 1):
            limiter.wait()
            try:
                info = self._info(symbol)
            except Exception as exc:
                if is_rate_limited(exc):
                    if breaker.record_rate_limited() or attempt == settings.max_attempts:
                        logger.warning("%s: security read rate limited by Yahoo", symbol)
                        return None
                elif is_transient(exc):
                    if attempt == settings.max_attempts:
                        logger.warning("%s: security read network error, giving up", symbol)
                        return None
                else:
                    logger.warning("%s: unexpected security read error", symbol, exc_info=True)
                    return None
                self._sleep(backoff_delay(attempt, retry_after_seconds(exc), self._rng))
            else:
                return security_from_info(info)
        return None

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
        *,
        request: Callable[[], pd.DataFrame] | None = None,
        finish: Callable[[pd.DataFrame], PriceHistory] | None = None,
    ) -> TickerOutcome:
        """Download one ticker with retries. Never raises for a data or network problem.

        ``request`` and ``finish`` replace the full-history download and its normalise-and-store
        step (the incremental refresh passes its own); both keep the retry and throttle rules.
        """
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
                    raw = request() if request is not None else self._download(symbol)
                    history = (
                        finish(raw)
                        if finish is not None
                        else self._normalize_and_store(raw, symbol, now_utc, path)
                    )
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

    # ------------------------------------------------------------ incremental refresh

    def _latest_cache(self, symbol: str) -> PriceHistory | None:
        """The newest cache file of ``symbol`` (any day) if it is readable, else ``None``."""
        if not self.cache_dir.is_dir():
            return None
        pattern = re.compile(rf"^{re.escape(symbol)}_\d{{4}}-\d{{2}}-\d{{2}}\.parquet$")
        files = sorted(
            (p for p in self.cache_dir.iterdir() if pattern.fullmatch(p.name)),
            key=lambda p: p.name,
            reverse=True,
        )
        return self._read_cache(symbol, files[0]) if files else None

    def fetch_incremental(self, ticker: str) -> HistoryRefresh:
        """The history of ``ticker``, brought up to date by fetching only the days it lacks.

        * A cache file of today, or an older one whose last bar is the latest completed trading
          day, is served with no network call.
        * Otherwise only the days after the last cached date are requested, starting at the
          last cached distribution (or ``REFRESH_OVERLAP_DAYS`` calendar days before the last
          date, whichever is earlier). If the overlap does not match the cache (a dividend or
          split rebased the adjusted prices, so old and new rows would mix bases, or a
          distribution is new) the whole history is downloaded again.
        * The whole history is also downloaded again when the last whole download is older than
          ``FULL_REFRESH_DAYS`` days, which catches corrections not tied to a distribution.
        * No usable cache (none, or an unreadable file): the whole history is downloaded once,
          with the normal retry rules of ``fetch_many``.
        * With a cache, the refresh makes one attempt with a short timeout: no retries and no
          waiting for a ``Retry-After``. A failed refresh keeps the cache: the older history is
          returned with ``action`` ``stale`` and a note saying where it ends. Without any cache
          a ``PriceDataError`` says why nothing could be loaded.

        Requests follow the throttle and rate-limit rules of ``fetch_many``.
        """
        symbol = validate_ticker(ticker)
        now_utc = self._now()
        path = self._cache_path(symbol, now_utc.date())
        with self._symbol_lock(f"{symbol}#refresh"):
            today_cache = self._read_cache(symbol, path)
            if today_cache is not None:
                return HistoryRefresh(today_cache, "cached")
            prior = self._latest_cache(symbol)
            if prior is not None and _last_date(prior.frame) >= latest_completed_session(now_utc):
                return HistoryRefresh(prior, "cached")
            settings = self._settings or _settings_from_config()
            limiter = RateLimiter(
                settings.min_interval_seconds, self._monotonic, self._sleep, self._rng
            )
            breaker = CircuitBreaker(settings.breaker_threshold)
            if prior is None:
                return self._full_refresh(symbol, now_utc, settings, limiter, breaker)
            # A cache exists, so a failure is not fatal: one try, no retries, no waiting.
            once = dataclasses.replace(settings, max_attempts=1)
            if _full_download_is_due(prior, now_utc):
                logger.info("%s: last full download is old; downloading the full history", symbol)
                return self._refresh_with_fallback(symbol, prior, now_utc, once, limiter, breaker)
            return self._partial_refresh(symbol, prior, now_utc, once, limiter, breaker)

    def _full_refresh(
        self,
        symbol: str,
        now_utc: datetime,
        settings: BatchSettings,
        limiter: RateLimiter,
        breaker: CircuitBreaker,
        *,
        bounded: bool = False,
    ) -> HistoryRefresh:
        download = self._download_bounded if bounded else self._download
        outcome = self._download_one(
            symbol, now_utc, settings, limiter, breaker, request=lambda: download(symbol)
        )
        if outcome.history is None:
            assert outcome.failure is not None
            raise PriceDataError(outcome.failure.message)
        return HistoryRefresh(outcome.history, "full")

    @staticmethod
    def _stale(symbol: str, prior: PriceHistory, why: str) -> HistoryRefresh:
        last = _last_date(prior.frame)
        note = (
            f"{symbol} data ends {last}; the refresh did not complete "
            f"({why.rstrip('.')}), so the cached history was used."
        )
        logger.warning("%s: refresh failed, serving the cache that ends %s", symbol, last)
        return HistoryRefresh(prior, "stale", note)

    def _refresh_with_fallback(
        self,
        symbol: str,
        prior: PriceHistory,
        now_utc: datetime,
        settings: BatchSettings,
        limiter: RateLimiter,
        breaker: CircuitBreaker,
    ) -> HistoryRefresh:
        """A whole-history download for a symbol that has a cache: on failure the cache stands."""
        try:
            return self._full_refresh(symbol, now_utc, settings, limiter, breaker, bounded=True)
        except PriceDataError as exc:
            return self._stale(symbol, prior, str(exc))

    def _partial_refresh(
        self,
        symbol: str,
        prior: PriceHistory,
        now_utc: datetime,
        settings: BatchSettings,
        limiter: RateLimiter,
        breaker: CircuitBreaker,
    ) -> HistoryRefresh:
        start = _refresh_start(prior.frame)

        def request() -> pd.DataFrame:
            return self._download_since(symbol, start)

        def finish(raw: pd.DataFrame) -> PriceHistory:
            if raw.empty:  # no new bar: legitimate, the cache is already complete
                return PriceHistory(symbol, prior.frame.iloc[0:0], now_utc, SOURCE_YFINANCE)
            frame, duplicates = normalize_frame(raw, symbol, now_utc)
            return PriceHistory(symbol, frame, now_utc, SOURCE_YFINANCE, duplicates)

        outcome = self._download_one(
            symbol, now_utc, settings, limiter, breaker, request=request, finish=finish
        )
        if outcome.history is None:
            assert outcome.failure is not None
            return self._stale(symbol, prior, outcome.failure.message)
        fresh = outcome.history
        if not fresh.frame.empty and rebased(prior.frame, fresh.frame):
            logger.info("%s: adjusted prices were rebased; downloading the full history", symbol)
            return self._refresh_with_fallback(symbol, prior, now_utc, settings, limiter, breaker)
        merged = merge_histories(prior.frame, fresh.frame)
        duplicates = tuple(sorted(set(prior.duplicate_dates) | set(fresh.duplicate_dates)))
        full_at = prior.full_downloaded_at
        self._store(
            merged, duplicates, symbol, now_utc, self._cache_path(symbol, now_utc.date()), full_at
        )
        return HistoryRefresh(
            PriceHistory(symbol, merged, now_utc, SOURCE_YFINANCE, duplicates, full_at),
            "incremental",
        )


REFRESH_OVERLAP_DAYS = 7
"""Calendar days before the last cached date that an incremental refresh asks for again, to check
that the adjusted prices were not rebased since the cache was written."""
FULL_REFRESH_DAYS = 30
"""A cache whose last whole download is older than this many days is downloaded whole again, so a
vendor correction that is not tied to a distribution cannot stay for long."""
REFRESH_TIMEOUT_SECONDS = 15.0
"""Timeout of the window request of a refresh that has a cache to fall back on."""
REFRESH_FULL_TIMEOUT_SECONDS = 45.0
"""Timeout of a whole-history request made by a refresh that has a cache to fall back on."""
REBASE_TOLERANCE = 1e-6
"""Relative difference of ``adj_close`` or ``close`` above which an overlap row changed."""
_DISTRIBUTION_COLUMNS = ("dividends", "capital_gains")
_NEW_YORK = ZoneInfo("America/New_York")


def _last_date(frame: pd.DataFrame) -> date:
    return pd.Timestamp(str(frame.index[-1])).date()


def _full_download_is_due(prior: PriceHistory, now_utc: datetime) -> bool:
    """True when the last whole download of the cache is older than ``FULL_REFRESH_DAYS``."""
    if prior.full_downloaded_at is None:
        return True  # a cache written before the stamp existed: one whole download sets it
    return now_utc - prior.full_downloaded_at > timedelta(days=FULL_REFRESH_DAYS)


def _refresh_start(frame: pd.DataFrame) -> date:
    """First date an incremental refresh asks for.

    The earlier of ``REFRESH_OVERLAP_DAYS`` before the last cached date and the last cached
    distribution (dividend or capital gain). A distribution Yahoo records late has an ex-date
    after the last one cached, so it lies inside the window and changes the rows the window
    shares with the cache; the window is at most about one distribution period long.
    """
    last = _last_date(frame)
    start = last - timedelta(days=REFRESH_OVERLAP_DAYS)
    paid = np.zeros(len(frame), dtype=bool)
    for column in _DISTRIBUTION_COLUMNS:
        if column in frame.columns:
            paid |= np.nan_to_num(frame[column].to_numpy(dtype=np.float64)) > 0.0
    if paid.any():
        start = min(start, pd.Timestamp(str(frame.index[np.flatnonzero(paid)[-1]])).date())
    return start


def latest_completed_session(now_utc: datetime) -> date:
    """The latest weekday before today in New York: the newest bar a cache can be expected to hold.

    Today's bar is never stored (M1.3), and exchange holidays are not modelled: on a holiday the
    refresh asks once, learns there is nothing new, and today's cache file records the check.
    """
    day = now_utc.astimezone(_NEW_YORK).date() - timedelta(days=1)
    while day.weekday() >= 5:
        day -= timedelta(days=1)
    return day


def rebased(cached: pd.DataFrame, fresh: pd.DataFrame) -> bool:
    """True when the rows both frames hold differ in a price or a distribution column.

    Yahoo rewrites the whole adjusted history at every dividend and split, so rows fetched after
    one cannot be appended to rows fetched before it. The overlap is the check; with no common
    row nothing shows that the two bases agree, so that counts as rebased too.
    """
    common = cached.index.intersection(fresh.index)
    if common.empty:
        return True
    for column in ("adj_close", "close", *_DISTRIBUTION_COLUMNS):
        if column not in cached.columns or column not in fresh.columns:
            continue
        old = cached.loc[common, column].to_numpy(dtype=np.float64)
        new = fresh.loc[common, column].to_numpy(dtype=np.float64)
        same = np.isclose(old, new, rtol=REBASE_TOLERANCE, atol=0.0) | (
            np.isnan(old) & np.isnan(new)
        )
        if not bool(same.all()):
            return True
    return False


def merge_histories(cached: pd.DataFrame, fresh: pd.DataFrame) -> pd.DataFrame:
    """Cached rows before the first fresh date plus every fresh row (fresh wins on a repeat)."""
    if fresh.empty:
        return cached
    older = np.asarray(cached.index < fresh.index[0], dtype=bool)
    kept = cached.iloc[np.flatnonzero(older)]
    merged = pd.concat([kept, fresh]).sort_index(kind="stable")
    merged = merged.loc[~merged.index.duplicated(keep="last")]
    for column in _ZERO_FILLED:
        if column in merged.columns:
            merged[column] = merged[column].fillna(0.0)
    order = [c for c in _COLUMN_ORDER if c in merged.columns]
    out = merged[order].astype("float64")
    out.index.name = "date"
    return out


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
