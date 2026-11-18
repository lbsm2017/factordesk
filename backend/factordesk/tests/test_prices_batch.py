"""Multi-ticker download: cache, chunks, workers, spacing, backoff, circuit breaker, order.

No network and no real sleeping: the download function, clock, sleep, jitter and executor are
all injected (CODING_STANDARDS.md, section 4).
"""

import threading
from collections.abc import Callable
from concurrent.futures import Executor, Future, ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import pandas as pd
import pytest
from pydantic import ValidationError

from factordesk.config import Settings
from factordesk.data import prices
from factordesk.data.prices import (
    BatchResult,
    PriceFailure,
    PriceHistory,
    TickerOutcome,
    YFinanceProvider,
)
from factordesk.data.throttle import (
    RATE_LIMIT_MESSAGE,
    BatchSettings,
    CircuitBreaker,
    RateLimiter,
    backoff_delay,
    is_rate_limited,
    is_transient,
    retry_after_seconds,
)
from factordesk.tests.test_prices import raw_yahoo_frame

NOW = datetime(2026, 3, 10, 21, 0, tzinfo=UTC)


# ---------------------------------------------------------------- test doubles


class FakeClock:
    """A monotonic clock that only moves when something sleeps."""

    def __init__(self) -> None:
        self.t = 0.0
        self.sleeps: list[float] = []
        self._lock = threading.Lock()

    def monotonic(self) -> float:
        with self._lock:
            return self.t

    def sleep(self, seconds: float) -> None:
        with self._lock:
            self.sleeps.append(seconds)
            self.t += seconds


class ZeroJitter:
    def uniform(self, a: float, b: float) -> float:
        return a


class MaxJitter:
    def uniform(self, a: float, b: float) -> float:
        return b


class InlineExecutor(Executor):
    """Runs every task in the calling thread and remembers what it was given."""

    def __init__(self, workers: int) -> None:
        self.workers = workers
        self.chunks: list[list[str]] = []

    def submit[**P, T](self, fn: Callable[P, T], /, *args: P.args, **kwargs: P.kwargs) -> Future[T]:
        self.chunks.append(list(cast(list[str], args[0])))
        future: Future[T] = Future()
        try:
            future.set_result(fn(*args, **kwargs))
        except BaseException as exc:  # noqa: BLE001 - mirrors a real executor
            future.set_exception(exc)
        return future


class YFRateLimitError(Exception):
    """Same class name as yfinance's exception; the code must not import the real one."""

    def __init__(self) -> None:
        super().__init__("Too Many Requests. Rate limited. Try after a while.")


class _Headers(dict[str, str]):
    pass


class HttpError(Exception):
    def __init__(self, status: int, retry_after: str | None = None) -> None:
        super().__init__(f"HTTP {status}")
        self.response = type(
            "Resp",
            (),
            {
                "status_code": status,
                "headers": _Headers({"Retry-After": retry_after} if retry_after else {}),
            },
        )()


class ScriptedDownload:
    """Fake download(ticker): replays a per-ticker script of frames and exceptions."""

    def __init__(self, clock: FakeClock, script: dict[str, list[Any]] | None = None) -> None:
        self.clock = clock
        self.script = script or {}
        self.calls: list[tuple[str, float]] = []  # (ticker, fake time of the request)
        self._lock = threading.Lock()

    def __call__(self, ticker: str) -> pd.DataFrame:
        with self._lock:
            self.calls.append((ticker, self.clock.monotonic()))
            queue = self.script.get(ticker)
            step: Any = queue.pop(0) if queue else raw_yahoo_frame()
        if isinstance(step, BaseException):
            raise step
        return step

    @property
    def tickers(self) -> list[str]:
        return [t for t, _ in self.calls]

    @property
    def times(self) -> list[float]:
        return [at for _, at in self.calls]


def settings(
    *,
    chunk_size: int = 5,
    max_workers: int = 3,
    min_interval_seconds: float = 0.5,
    max_attempts: int = 3,
    breaker_threshold: int = 3,
) -> BatchSettings:
    return BatchSettings(
        chunk_size=chunk_size,
        max_workers=max_workers,
        min_interval_seconds=min_interval_seconds,
        max_attempts=max_attempts,
        breaker_threshold=breaker_threshold,
    )


class Rig:
    """A provider wired to fakes, plus the fakes."""

    def __init__(
        self,
        tmp_path: Path,
        script: dict[str, list[Any]] | None = None,
        batch: BatchSettings | None = None,
        jitter: ZeroJitter | MaxJitter | None = None,
    ) -> None:
        self.clock = FakeClock()
        self.download = ScriptedDownload(self.clock, script)
        self.executors: list[InlineExecutor] = []
        self.provider = YFinanceProvider(
            cache_dir=tmp_path / "prices",
            now=lambda: NOW,
            settings=batch or settings(),
            download=self.download,
            monotonic=self.clock.monotonic,
            sleep=self.clock.sleep,
            rng=jitter or ZeroJitter(),
            executor_factory=self._factory,
        )

    def _factory(self, workers: int) -> InlineExecutor:
        executor = InlineExecutor(workers)
        self.executors.append(executor)
        return executor


def tickers_of(result: BatchResult) -> list[str]:
    return [o.ticker for o in result.outcomes]


# ---------------------------------------------------------------- cache


def test_cache_hits_make_zero_requests(tmp_path: Path) -> None:
    rig = Rig(tmp_path)
    first = rig.provider.fetch_many(["SPY", "QQQ", "IWM"])
    assert first.downloaded == 3 and first.cache_hits == 0
    assert len(rig.download.calls) == 3

    sleeps_before = len(rig.clock.sleeps)
    second = rig.provider.fetch_many(["SPY", "QQQ", "IWM"])
    assert len(rig.download.calls) == 3  # not one more request
    assert second.cache_hits == 3 and second.downloaded == 0
    assert len(rig.executors) == 1  # no second pool was even started
    assert len(rig.clock.sleeps) == sleeps_before  # and no waiting
    pd.testing.assert_frame_equal(
        second.histories["SPY"].frame, first.histories["SPY"].frame, check_freq=False
    )


def test_only_cache_misses_are_downloaded(tmp_path: Path) -> None:
    rig = Rig(tmp_path)
    rig.provider.fetch_many(["SPY"])
    result = rig.provider.fetch_many(["SPY", "QQQ"])
    assert rig.download.tickers == ["SPY", "QQQ"]
    assert (result.cache_hits, result.downloaded) == (1, 1)
    assert [o.from_cache for o in result.outcomes] == [True, False]


def test_failed_ticker_is_not_cached_and_is_retried_next_batch(tmp_path: Path) -> None:
    rig = Rig(tmp_path, {"BAD": [pd.DataFrame()]})
    first = rig.provider.fetch_many(["SPY", "BAD"])
    assert first.failed == 1
    second = rig.provider.fetch_many(["SPY", "BAD"])
    assert rig.download.tickers == ["SPY", "BAD", "BAD"]
    assert second.cache_hits == 1 and second.downloaded == 1 and second.failed == 0


# ---------------------------------------------------------------- chunks and workers


def test_chunks_group_tickers_in_order(tmp_path: Path) -> None:
    names = [f"T{i:02d}" for i in range(12)]
    rig = Rig(tmp_path, batch=settings(chunk_size=5, max_workers=3))
    rig.provider.fetch_many(names)
    (executor,) = rig.executors
    assert [len(c) for c in executor.chunks] == [5, 5, 2]
    assert [t for c in executor.chunks for t in c] == names
    assert executor.workers == 3


def test_worker_count_is_capped_and_never_exceeds_chunk_count(tmp_path: Path) -> None:
    many = [f"T{i:02d}" for i in range(20)]
    rig = Rig(tmp_path, batch=settings(chunk_size=2, max_workers=3))
    rig.provider.fetch_many(many)
    assert rig.executors[0].workers == 3  # 10 chunks, cap 3

    rig2 = Rig(tmp_path / "b", batch=settings(chunk_size=5, max_workers=3))
    rig2.provider.fetch_many(["AAA", "BBB"])
    assert rig2.executors[0].workers == 1  # one chunk needs one worker


def test_real_thread_pool_never_runs_more_than_the_cap_at_once(tmp_path: Path) -> None:
    cap = 2
    barrier = threading.Barrier(cap)  # only passes if two requests really overlap
    lock = threading.Lock()
    state = {"active": 0, "peak": 0}
    requested: list[int] = []

    def download(ticker: str) -> pd.DataFrame:
        with lock:
            state["active"] += 1
            state["peak"] = max(state["peak"], state["active"])
        try:
            barrier.wait(timeout=10)
            return raw_yahoo_frame()
        finally:
            with lock:
                state["active"] -= 1

    def factory(workers: int) -> Executor:
        requested.append(workers)
        return ThreadPoolExecutor(max_workers=workers)

    clock = FakeClock()
    provider = YFinanceProvider(
        cache_dir=tmp_path / "prices",
        now=lambda: NOW,
        settings=settings(chunk_size=1, max_workers=cap, min_interval_seconds=0.0),
        download=download,
        monotonic=clock.monotonic,
        sleep=clock.sleep,
        rng=ZeroJitter(),
        executor_factory=factory,
    )
    result = provider.fetch_many(["AAA", "BBB", "CCC", "DDD"])
    assert requested == [cap]
    assert result.downloaded == 4 and result.failed == 0
    assert state["peak"] == cap
    assert tickers_of(result) == ["AAA", "BBB", "CCC", "DDD"]


def test_default_executor_runs_and_keeps_input_order(tmp_path: Path) -> None:
    clock = FakeClock()
    provider = YFinanceProvider(
        cache_dir=tmp_path / "prices",
        now=lambda: NOW,
        settings=settings(chunk_size=1, max_workers=3, min_interval_seconds=0.0),
        download=ScriptedDownload(clock),
        monotonic=clock.monotonic,
        sleep=clock.sleep,
        rng=ZeroJitter(),
    )
    names = [f"T{i:02d}" for i in range(9)]
    result = provider.fetch_many(names)
    assert tickers_of(result) == names
    assert result.downloaded == 9


# ---------------------------------------------------------------- spacing


def test_request_starts_are_spaced_by_the_minimum_interval(tmp_path: Path) -> None:
    rig = Rig(tmp_path, batch=settings(min_interval_seconds=0.5))
    result = rig.provider.fetch_many(["AAA", "BBB", "CCC", "DDD"])
    assert rig.download.times == [0.0, 0.5, 1.0, 1.5]
    assert result.elapsed_seconds == pytest.approx(1.5)


def test_jitter_only_adds_to_the_spacing(tmp_path: Path) -> None:
    rig = Rig(tmp_path, batch=settings(min_interval_seconds=0.5), jitter=MaxJitter())
    rig.provider.fetch_many(["AAA", "BBB", "CCC"])
    gaps = [b - a for a, b in zip(rig.download.times, rig.download.times[1:], strict=False)]
    assert gaps == [pytest.approx(0.75), pytest.approx(0.75)]  # 0.5 + up to 0.25 of jitter


def test_rate_limiter_spaces_calls_and_does_not_wait_when_idle() -> None:
    clock = FakeClock()
    limiter = RateLimiter(1.0, clock.monotonic, clock.sleep, ZeroJitter())
    limiter.wait()  # first call goes straight through
    assert clock.sleeps == []
    limiter.wait()
    assert clock.sleeps == [1.0]
    clock.t += 10.0  # a long idle gap: the next call is not delayed
    limiter.wait()
    assert clock.sleeps == [1.0]


def test_rate_limiter_reserves_distinct_slots_across_threads() -> None:
    gate = threading.Lock()
    slots: list[float] = []

    def monotonic() -> float:
        return 0.0  # time never moves, so every caller must be given its own later slot

    def sleep(seconds: float) -> None:
        with gate:
            slots.append(seconds)

    limiter = RateLimiter(0.5, monotonic, sleep, ZeroJitter())
    threads = [threading.Thread(target=limiter.wait) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(slots) == [0.5, 1.0, 1.5, 2.0]  # four waits behind the first


# ---------------------------------------------------------------- backoff and retry


def test_backoff_schedule_doubles_then_succeeds(tmp_path: Path) -> None:
    script: dict[str, list[Any]] = {"SPY": [YFRateLimitError(), YFRateLimitError()]}
    rig = Rig(tmp_path, script, settings(max_attempts=3, breaker_threshold=10))
    result = rig.provider.fetch_many(["SPY"])
    assert rig.clock.sleeps == [2.0, 4.0]  # 2 s, then 4 s; none after success
    assert len(rig.download.calls) == 3
    assert result.downloaded == 1 and result.failed == 0


def test_backoff_delay_values() -> None:
    assert backoff_delay(1, None, ZeroJitter()) == 2.0
    assert backoff_delay(2, None, ZeroJitter()) == 4.0
    assert backoff_delay(3, None, ZeroJitter()) == 8.0
    assert backoff_delay(10, None, ZeroJitter()) == 30.0  # capped
    assert backoff_delay(1, None, MaxJitter()) == pytest.approx(2.5)  # +25 % jitter at most


def test_retry_after_longer_than_backoff_is_honoured(tmp_path: Path) -> None:
    script: dict[str, list[Any]] = {"SPY": [HttpError(429, "10")]}
    rig = Rig(tmp_path, script, settings(breaker_threshold=10))
    result = rig.provider.fetch_many(["SPY"])
    assert rig.clock.sleeps == [10.0]
    assert result.downloaded == 1


def test_retry_after_never_shortens_the_backoff_and_is_capped() -> None:
    assert backoff_delay(2, 1.0, ZeroJitter()) == 4.0
    assert backoff_delay(1, 9999.0, ZeroJitter()) == 120.0


def test_retry_after_parsing() -> None:
    assert retry_after_seconds(HttpError(429, "7")) == 7.0
    assert retry_after_seconds(HttpError(429, "Wed, 21 Oct 2026 07:28:00 GMT")) is None
    assert retry_after_seconds(HttpError(429)) is None
    assert retry_after_seconds(ValueError("x")) is None
    exc = YFRateLimitError()
    exc.retry_after = 3  # type: ignore[attr-defined]
    assert retry_after_seconds(exc) == 3.0


def test_attempts_run_out_and_the_ticker_is_reported(tmp_path: Path) -> None:
    script: dict[str, list[Any]] = {"SPY": [YFRateLimitError() for _ in range(5)]}
    rig = Rig(tmp_path, script, settings(max_attempts=3, breaker_threshold=10))
    result = rig.provider.fetch_many(["SPY"])
    assert len(rig.download.calls) == 3  # never retries forever
    assert rig.clock.sleeps == [2.0, 4.0]  # no pointless wait after the last try
    (failure,) = result.failures
    assert failure.reason == "rate_limited"
    assert failure.message == "Yahoo is limiting requests. Wait a few minutes and try again."


def test_transient_errors_retry_then_report_network(tmp_path: Path) -> None:
    script: dict[str, list[Any]] = {"SPY": [TimeoutError("slow"), ConnectionError("down")]}
    rig = Rig(tmp_path, script, settings(max_attempts=3))
    ok = rig.provider.fetch_many(["SPY"])
    assert ok.downloaded == 1 and len(rig.download.calls) == 3

    script2: dict[str, list[Any]] = {"QQQ": [TimeoutError("x") for _ in range(3)]}
    rig2 = Rig(tmp_path / "b", script2, settings(max_attempts=3))
    bad = rig2.provider.fetch_many(["QQQ"])
    assert bad.failures[0].reason == "network"
    assert "QQQ" in bad.failures[0].message
    assert not bad.rate_limited


def test_no_data_is_not_retried(tmp_path: Path) -> None:
    rig = Rig(tmp_path, {"NOPE": [pd.DataFrame()]})
    result = rig.provider.fetch_many(["NOPE"])
    assert len(rig.download.calls) == 1
    assert result.failures[0].reason == "no_data"
    assert "No price data" in result.failures[0].message


def test_unexpected_error_is_reported_not_raised(tmp_path: Path) -> None:
    rig = Rig(tmp_path, {"AAA": [RuntimeError("boom")]})
    result = rig.provider.fetch_many(["AAA", "BBB"])
    assert result.failures[0].reason == "unexpected"
    assert "RuntimeError" in result.failures[0].message
    assert "BBB" in result.histories


# ---------------------------------------------------------------- circuit breaker


def test_breaker_stops_requests_and_skips_the_rest(tmp_path: Path) -> None:
    names = [f"T{i}" for i in range(7)]
    script: dict[str, list[Any]] = {n: [YFRateLimitError() for _ in range(5)] for n in names}
    rig = Rig(tmp_path, script, settings(chunk_size=5, max_attempts=3, breaker_threshold=3))
    result = rig.provider.fetch_many(names)

    assert len(rig.download.calls) == 3  # three rate limits in a row, then silence
    assert set(rig.download.tickers) == {"T0"}  # the third try of T0 tripped it
    assert [f.reason for f in result.failures] == ["rate_limited"] + ["skipped_rate_limited"] * 6
    assert (result.failed, result.skipped) == (1, 6)
    assert result.rate_limited
    assert result.message == "Yahoo is limiting requests. Wait a few minutes and try again."
    assert tickers_of(result) == names  # skipped tickers are listed, not dropped
    assert result.histories == {}


def test_breaker_is_per_batch_so_the_next_batch_tries_again(tmp_path: Path) -> None:
    script: dict[str, list[Any]] = {"SPY": [YFRateLimitError() for _ in range(3)]}
    rig = Rig(tmp_path, script, settings(breaker_threshold=3))
    first = rig.provider.fetch_many(["SPY", "QQQ"])
    assert first.skipped == 1
    second = rig.provider.fetch_many(["SPY", "QQQ"])
    assert second.downloaded == 2 and not second.rate_limited and second.message is None


def test_success_resets_the_breaker_streak(tmp_path: Path) -> None:
    script: dict[str, list[Any]] = {
        "AAA": [YFRateLimitError()],
        "BBB": [YFRateLimitError()],
        "CCC": [YFRateLimitError()],
    }
    rig = Rig(tmp_path, script, settings(max_attempts=3, breaker_threshold=2))
    result = rig.provider.fetch_many(["AAA", "BBB", "CCC"])
    assert result.downloaded == 3 and not result.rate_limited  # never two in a row


def test_a_clean_no_data_answer_also_resets_the_streak(tmp_path: Path) -> None:
    breaker = CircuitBreaker(2)
    assert breaker.record_rate_limited() is False
    breaker.record_answered()
    assert breaker.record_rate_limited() is False
    assert breaker.tripped is False
    assert breaker.record_rate_limited() is True
    assert breaker.tripped is True
    breaker.record_answered()
    assert breaker.tripped is True  # once tripped it stays tripped for the batch


# ---------------------------------------------------------------- failure, order, duplicates


def test_partial_failure_keeps_the_good_tickers(tmp_path: Path) -> None:
    script: dict[str, list[Any]] = {"BAD": [pd.DataFrame()]}
    rig = Rig(tmp_path, script)
    result = rig.provider.fetch_many(["GOOD1", "BAD", "not a ticker", "GOOD2"])
    assert set(result.histories) == {"GOOD1", "GOOD2"}
    reasons = {f.ticker: f.reason for f in result.failures}
    assert reasons == {"BAD": "no_data", "not a ticker": "invalid_ticker"}
    assert (result.downloaded, result.failed, result.skipped, result.cache_hits) == (2, 2, 0, 0)
    assert rig.download.tickers == ["GOOD1", "BAD", "GOOD2"]  # invalid symbol never requested
    assert result.message is None


def test_duplicate_tickers_download_once_and_are_reported(tmp_path: Path) -> None:
    rig = Rig(tmp_path)
    result = rig.provider.fetch_many(["spy", "SPY", "QQQ", "Spy", "bad one", "bad one"])
    assert rig.download.tickers == ["SPY", "QQQ"]
    assert tickers_of(result) == ["SPY", "QQQ", "bad one"]
    assert result.duplicates == ("SPY", "SPY", "bad one")


def test_results_keep_input_order_across_hits_misses_and_failures(tmp_path: Path) -> None:
    rig = Rig(tmp_path, {"MMM": [pd.DataFrame()]}, settings(chunk_size=1, max_workers=3))
    rig.provider.fetch_many(["AAA"])  # AAA is now cached
    names = ["ZZZ", "bad one", "AAA", "MMM", "BBB"]
    result = rig.provider.fetch_many(names)
    assert tickers_of(result) == names
    assert list(result.histories) == ["ZZZ", "AAA", "BBB"]


def test_empty_request_returns_an_empty_result(tmp_path: Path) -> None:
    rig = Rig(tmp_path)
    result = rig.provider.fetch_many([])
    assert result.outcomes == () and result.elapsed_seconds == 0.0
    assert rig.download.calls == [] and rig.executors == []


def test_same_ticker_requested_at_once_by_two_callers_downloads_once(tmp_path: Path) -> None:
    entered = threading.Event()
    release = threading.Event()
    second_caller_started = threading.Event()
    now_calls: list[int] = []
    downloads: list[str] = []

    def download(ticker: str) -> pd.DataFrame:
        downloads.append(ticker)
        entered.set()
        assert release.wait(timeout=10)
        return raw_yahoo_frame()

    def now() -> datetime:
        now_calls.append(1)
        if len(now_calls) >= 2:
            second_caller_started.set()
        return NOW

    clock = FakeClock()
    provider = YFinanceProvider(
        cache_dir=tmp_path / "prices",
        now=now,
        settings=settings(min_interval_seconds=0.0),
        download=download,
        monotonic=clock.monotonic,
        sleep=clock.sleep,
        rng=ZeroJitter(),
    )
    results: list[BatchResult] = []

    def run() -> None:
        results.append(provider.fetch_many(["SPY"]))

    first = threading.Thread(target=run)
    first.start()
    assert entered.wait(timeout=10)
    second = threading.Thread(target=run)
    second.start()
    assert second_caller_started.wait(timeout=10)
    release.set()
    first.join(timeout=10)
    second.join(timeout=10)

    assert downloads == ["SPY"]
    assert len(results) == 2 and all("SPY" in r.histories for r in results)
    assert sorted(r.cache_hits for r in results) == [0, 1]


# ---------------------------------------------------------------- same data as fetch()


class _FakeTicker:
    calls: list[tuple[str, dict[str, Any]]] = []

    def __init__(self, ticker: str, *args: Any, **kwargs: Any) -> None:
        self.ticker = ticker
        assert not args and not kwargs  # no session passed: yfinance owns its curl_cffi session

    def history(self, *args: Any, **kwargs: Any) -> pd.DataFrame:
        _FakeTicker.calls.append((self.ticker, kwargs))
        return raw_yahoo_frame()


def test_batch_uses_the_same_explicit_request_and_data_as_fetch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _FakeTicker.calls = []
    monkeypatch.setattr("yfinance.Ticker", _FakeTicker)
    clock = FakeClock()
    batch = YFinanceProvider(
        cache_dir=tmp_path / "batch",
        now=lambda: NOW,
        settings=settings(),
        monotonic=clock.monotonic,
        sleep=clock.sleep,
        rng=ZeroJitter(),
        executor_factory=InlineExecutor,
    )
    single = YFinanceProvider(cache_dir=tmp_path / "single", now=lambda: NOW)

    got = batch.fetch_many(["spy"]).histories["SPY"]
    want = single.fetch("SPY")

    assert len(_FakeTicker.calls) == 2  # one full-history request each, no date-range splitting
    for _, kwargs in _FakeTicker.calls:
        assert kwargs == {
            "period": "max",
            "interval": "1d",
            "auto_adjust": False,
            "actions": True,
            "repair": False,
        }
    pd.testing.assert_frame_equal(got.frame, want.frame, check_freq=False)
    assert (got.source, got.fetched_at, got.duplicate_dates) == (
        want.source,
        want.fetched_at,
        want.duplicate_dates,
    )


# ---------------------------------------------------------------- settings


def test_defaults_are_gentle(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "PRICE_CHUNK_SIZE",
        "PRICE_MAX_WORKERS",
        "PRICE_MIN_INTERVAL_SECONDS",
        "PRICE_MAX_ATTEMPTS",
        "PRICE_BREAKER_THRESHOLD",
    ):
        monkeypatch.delenv(name, raising=False)
    cfg = Settings(_env_file=None)  # pyright: ignore[reportCallIssue]
    assert cfg.price_chunk_size == 5
    assert cfg.price_max_workers == 3
    assert cfg.price_min_interval_seconds == 0.5
    assert cfg.price_max_attempts == 3
    assert cfg.price_breaker_threshold == 3


def test_environment_variables_override_the_knobs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PRICE_CHUNK_SIZE", "7")
    monkeypatch.setenv("PRICE_MAX_WORKERS", "2")
    monkeypatch.setenv("PRICE_MIN_INTERVAL_SECONDS", "1.5")
    cfg = Settings(_env_file=None)  # pyright: ignore[reportCallIssue]
    assert (cfg.price_chunk_size, cfg.price_max_workers) == (7, 2)
    assert cfg.price_min_interval_seconds == 1.5


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("PRICE_CHUNK_SIZE", "0"),
        ("PRICE_MAX_WORKERS", "0"),
        ("PRICE_MAX_WORKERS", "99"),
        ("PRICE_MAX_ATTEMPTS", "0"),
        ("PRICE_BREAKER_THRESHOLD", "0"),
        ("PRICE_MIN_INTERVAL_SECONDS", "-1"),
    ],
)
def test_out_of_range_knobs_are_rejected(
    name: str, value: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(name, value)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)  # pyright: ignore[reportCallIssue]


def test_provider_reads_the_knobs_from_config_when_none_injected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class StubSettings:
        price_chunk_size = 2
        price_max_workers = 1
        price_min_interval_seconds = 0.0
        price_max_attempts = 1
        price_breaker_threshold = 1

    monkeypatch.setattr(prices, "get_settings", lambda: StubSettings())
    clock = FakeClock()
    executors: list[InlineExecutor] = []

    def factory(workers: int) -> InlineExecutor:
        executors.append(InlineExecutor(workers))
        return executors[-1]

    provider = YFinanceProvider(
        cache_dir=tmp_path / "prices",
        now=lambda: NOW,
        download=ScriptedDownload(clock),
        monotonic=clock.monotonic,
        sleep=clock.sleep,
        rng=ZeroJitter(),
        executor_factory=factory,
    )
    provider.fetch_many(["AAA", "BBB", "CCC"])
    assert [len(c) for c in executors[0].chunks] == [2, 1]


def test_batch_settings_validate() -> None:
    with pytest.raises(ValueError, match="at least 1"):
        settings(chunk_size=0)
    with pytest.raises(ValueError, match="at least 1"):
        settings(breaker_threshold=0)
    with pytest.raises(ValueError, match="negative"):
        settings(min_interval_seconds=-0.1)


# ---------------------------------------------------------------- classification and types


def test_rate_limit_detection_is_generic() -> None:
    assert is_rate_limited(YFRateLimitError())
    assert is_rate_limited(HttpError(429))
    assert is_rate_limited(RuntimeError("Too Many Requests. Rate limited."))
    assert not is_rate_limited(HttpError(500))
    assert not is_rate_limited(ValueError("Invalid ISIN number"))
    assert not is_rate_limited(KeyError("x"))


def test_transient_detection() -> None:
    assert is_transient(TimeoutError())
    assert is_transient(ConnectionResetError())
    assert is_transient(HttpError(503))
    assert not is_transient(HttpError(404))
    assert not is_transient(ValueError("x"))


def test_outcome_holds_exactly_one_of_history_or_failure() -> None:
    frame = pd.DataFrame({"adj_close": [1.0]})
    history = PriceHistory("SPY", frame, NOW, "yfinance")
    failure = PriceFailure("SPY", "no_data", "x")
    with pytest.raises(ValueError, match="exactly one"):
        TickerOutcome("SPY")
    with pytest.raises(ValueError, match="exactly one"):
        TickerOutcome("SPY", history=history, failure=failure)
    assert TickerOutcome("SPY", history=history).failure is None


def test_batch_result_is_frozen() -> None:
    result = BatchResult(outcomes=(), duplicates=(), elapsed_seconds=0.0)
    with pytest.raises(AttributeError):
        result.elapsed_seconds = 1.0  # type: ignore[misc]


def test_message_constant_is_the_plain_sentence() -> None:
    assert RATE_LIMIT_MESSAGE == "Yahoo is limiting requests. Wait a few minutes and try again."
