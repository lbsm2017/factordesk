"""Throttle-safety building blocks for multi-ticker price downloads.

Yahoo publishes no rate limit (docs/data-source-comparison.md, section 6), so nothing here
assumes a number. The rules are defensive: space requests out, back off when Yahoo pushes
back, and stop asking when it keeps pushing back. Clocks, sleep and randomness are injected so
tests need neither network nor real waiting (CODING_STANDARDS.md, section 4).
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

# Plain-English text shown when Yahoo is limiting requests.
RATE_LIMIT_MESSAGE = "Yahoo is limiting requests. Wait a few minutes and try again."

# Retry schedule: attempt n waits BACKOFF_BASE * 2**(n-1) seconds (capped), plus up to
# BACKOFF_JITTER_FRACTION of that as random jitter. A Retry-After from the server raises the
# wait (never lowers it) but is capped so one reply cannot freeze a request for long.
BACKOFF_BASE_SECONDS = 2.0
BACKOFF_CAP_SECONDS = 30.0
BACKOFF_JITTER_FRACTION = 0.25
RETRY_AFTER_CAP_SECONDS = 120.0

# Spacing jitter between request starts, as a fraction of the minimum interval.
SPACING_JITTER_FRACTION = 0.5


class JitterSource(Protocol):
    """The one method of ``random.Random`` we use, so tests can pin the jitter."""

    def uniform(self, a: float, b: float) -> float: ...


@dataclass(frozen=True)
class BatchSettings:
    """The five knobs of a batch download (environment variables PRICE_*, see config.py)."""

    chunk_size: int
    max_workers: int
    min_interval_seconds: float
    max_attempts: int
    breaker_threshold: int

    def __post_init__(self) -> None:
        if self.chunk_size < 1 or self.max_workers < 1 or self.max_attempts < 1:
            raise ValueError("chunk_size, max_workers and max_attempts must be at least 1")
        if self.breaker_threshold < 1:
            raise ValueError("breaker_threshold must be at least 1")
        if self.min_interval_seconds < 0:
            raise ValueError("min_interval_seconds must not be negative")


class RateLimiter:
    """Keeps request starts at least ``min_interval`` apart across all threads.

    Each caller reserves the next free slot under a lock and sleeps outside it, so threads
    queue up in order and no two requests start closer together than the interval. Random
    jitter (up to half the interval) is added to every slot so the pattern is not a metronome.
    """

    def __init__(
        self,
        min_interval: float,
        monotonic: Callable[[], float],
        sleep: Callable[[float], None],
        rng: JitterSource,
    ) -> None:
        self._min_interval = min_interval
        self._jitter = min_interval * SPACING_JITTER_FRACTION
        self._monotonic = monotonic
        self._sleep = sleep
        self._rng = rng
        self._lock = threading.Lock()
        self._next_slot = 0.0

    def wait(self) -> None:
        """Block until this caller's request slot arrives."""
        with self._lock:
            now = self._monotonic()
            start = max(now, self._next_slot)
            self._next_slot = start + self._min_interval + self._rng.uniform(0.0, self._jitter)
        delay = start - now
        if delay > 0:
            self._sleep(delay)


class CircuitBreaker:
    """Trips after ``threshold`` rate-limit replies in a row, then stays tripped.

    Any reply that is not a rate limit (data, or a clean "no such ticker") resets the count,
    because it shows Yahoo is answering. Once tripped, the batch starts no new requests.
    """

    def __init__(self, threshold: int) -> None:
        self._threshold = threshold
        self._consecutive = 0
        self._tripped = False
        self._lock = threading.Lock()

    @property
    def tripped(self) -> bool:
        with self._lock:
            return self._tripped

    def record_rate_limited(self) -> bool:
        """Count one rate-limit reply. Returns True when the breaker is (now) tripped."""
        with self._lock:
            self._consecutive += 1
            if self._consecutive >= self._threshold:
                self._tripped = True
            return self._tripped

    def record_answered(self) -> None:
        """Yahoo answered with something other than a rate limit: reset the streak."""
        with self._lock:
            self._consecutive = 0


# ---------------------------------------------------------------- error classification


def _status_code(exc: BaseException) -> int | None:
    """HTTP status carried by an exception, if any (requests, curl_cffi and httpx styles)."""
    for holder in (exc, getattr(exc, "response", None)):
        for attr in ("status_code", "status"):
            value = getattr(holder, attr, None)
            if isinstance(value, int):
                return value
    return None


def is_rate_limited(exc: BaseException) -> bool:
    """True for a Yahoo rate-limit reply.

    Detected without importing yfinance, whose exception class has moved between releases:
    an HTTP 429 on the exception or its response, a class name that mentions rate limiting
    (yfinance's ``YFRateLimitError``), or the "Too Many Requests" wording.
    """
    if _status_code(exc) == 429:
        return True
    if "ratelimit" in type(exc).__name__.lower():
        return True
    text = str(exc).lower()
    return "too many requests" in text or "rate limit" in text


def is_transient(exc: BaseException) -> bool:
    """True for a failure that is worth retrying but is not a rate limit."""
    if isinstance(exc, TimeoutError | ConnectionError):
        return True
    name = type(exc).__name__.lower()
    if "timeout" in name or "connection" in name:
        return True
    status = _status_code(exc)
    return status is not None and 500 <= status <= 599


def retry_after_seconds(exc: BaseException) -> float | None:
    """The server's Retry-After in seconds, when the exception carries a numeric one."""
    direct = getattr(exc, "retry_after", None)
    candidates: list[object] = [direct]
    headers = getattr(getattr(exc, "response", None), "headers", None)
    if headers is not None and hasattr(headers, "get"):
        candidates.append(headers.get("Retry-After"))
    for value in candidates:
        if value is None or isinstance(value, bool):
            continue
        try:
            seconds = float(str(value).strip())
        except ValueError:
            continue  # an HTTP-date form: ignored, the backoff schedule applies
        if seconds >= 0:
            return seconds
    return None


def backoff_delay(attempt: int, retry_after: float | None, rng: JitterSource) -> float:
    """Seconds to wait after failed attempt number ``attempt`` (1-based)."""
    base = min(BACKOFF_CAP_SECONDS, BACKOFF_BASE_SECONDS * 2.0 ** (attempt - 1))
    delay = base + rng.uniform(0.0, base * BACKOFF_JITTER_FRACTION)
    if retry_after is not None:
        delay = max(delay, min(retry_after, RETRY_AFTER_CAP_SECONDS))
    return delay
