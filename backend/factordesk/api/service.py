"""Report service: in-flight de-duplication, caches and worker threads (dashboard spec DB3).

Four layers, each a ``SingleFlight`` (a dict of running tasks plus an LRU of results):

1. factor frame: loaded on every request through ``load_factors(False, now)`` (which may run
   the 40-day auto-refresh), then identified by its vintage ``(last_date, last_download_at)``;
2. price history: key ``(ticker, today)``, matching the same-day cache of ``YFinanceProvider``;
3. report: key ``(ticker, start, end, vintage, today)`` after preset resolution, so ``range=3Y``
   and the same explicit dates share one entry;
4. ranges: the report key without start and end.

A request whose key is running awaits the same task through ``asyncio.shield``, so a closed
browser tab does not cancel work that others wait for. Failures are not cached; every waiter
gets the same exception. When the vintage changes, entries of other vintages are dropped.
Shared state is touched only on the event-loop thread; worker functions take inputs and return
values, so no locks are needed.
"""

from __future__ import annotations

import asyncio
import logging
from collections import OrderedDict
from collections.abc import Awaitable, Callable, Hashable
from dataclasses import dataclass
from datetime import UTC, date, datetime

import pandas as pd
from fastapi import Request

from factordesk.api import ranges
from factordesk.api.runtime import Runtime
from factordesk.data.prices import PriceHistory
from factordesk.report.render_html import render_report_html
from factordesk.report.schema import FactorReport, RangeOptions, RangePreset

logger = logging.getLogger(__name__)


def assemble_report(
    ticker: str,
    history: PriceHistory,
    factor_frame: pd.DataFrame,
    *,
    now: datetime,
    factors_downloaded_at: datetime | None,
    start: date | None = None,
    end: date | None = None,
) -> FactorReport:
    """``factordesk.pipeline.assemble_report``, imported on first use.

    The pipeline pulls in statsmodels and scipy, which take seconds to load; importing it at
    module level would delay the start of the server.
    """
    from factordesk.pipeline import assemble_report as assemble

    return assemble(
        ticker,
        history,
        factor_frame,
        now=now,
        factors_downloaded_at=factors_downloaded_at,
        start=start,
        end=end,
    )


PRICE_CACHE_SIZE = 16
"""Price histories kept in memory (DB3 layer 2)."""


class SingleFlight[K: Hashable, V]:
    """Results by key (an LRU of ``max_size``; 0 keeps none) plus the tasks still running.

    ``started`` counts tasks created, ``hits`` answers served from the LRU and ``waiting`` the
    callers awaiting a running task right now. Touch only from the event-loop thread.
    """

    def __init__(self, max_size: int) -> None:
        if max_size < 0:
            raise ValueError("max_size must not be negative")
        self.max_size = max_size
        self.started = 0
        self.hits = 0
        self.waiting = 0
        self._done: OrderedDict[K, V] = OrderedDict()
        self._running: dict[K, asyncio.Task[V]] = {}

    def __len__(self) -> int:
        return len(self._done)

    def keys(self) -> list[K]:
        """Cached keys, least recently used first."""
        return list(self._done)

    async def get(self, key: K, make: Callable[[], Awaitable[V]]) -> V:
        """The cached value, the running task's value, or the value of a new task."""
        if key in self._done:
            self._done.move_to_end(key)
            self.hits += 1
            return self._done[key]
        task = self._running.get(key)
        if task is None:
            task = asyncio.ensure_future(self._run(key, make))
            task.add_done_callback(_retrieve)
            self._running[key] = task
            self.started += 1
        self.waiting += 1
        try:
            return await asyncio.shield(task)
        finally:
            self.waiting -= 1

    def discard(self, keep: Callable[[K], bool]) -> None:
        """Drop every cached entry whose key ``keep`` rejects."""
        for key in [k for k in self._done if not keep(k)]:
            del self._done[key]

    async def _run(self, key: K, make: Callable[[], Awaitable[V]]) -> V:
        try:
            value = await make()
            if self.max_size:
                self._done[key] = value
                self._done.move_to_end(key)
                while len(self._done) > self.max_size:
                    self._done.popitem(last=False)
            return value
        finally:
            self._running.pop(key, None)


def _retrieve(task: asyncio.Task[object]) -> None:
    """Mark a failure as seen even when every waiter has gone (the waiters re-raise it)."""
    if not task.cancelled() and task.exception() is not None:
        logger.debug("Report task failed: %r", task.exception())


@dataclass(frozen=True)
class Vintage:
    """Which factor file a result was computed from."""

    last_date: date
    downloaded_at: datetime | None


@dataclass(frozen=True)
class LoadedFactors:
    vintage: Vintage
    frame: pd.DataFrame


type PriceKey = tuple[str, date]
type RangesKey = tuple[str, Vintage, date]
type ReportKey = tuple[str, date | None, date | None, Vintage, date]


def _utc(ts: datetime | None) -> datetime | None:
    """A stored download time as aware UTC (naive values are taken as UTC)."""
    if ts is None:
        return None
    return ts.replace(tzinfo=UTC) if ts.utcoffset() is None else ts.astimezone(UTC)


class ReportService:
    """Builds reports, range options and HTML downloads from the injected collaborators."""

    def __init__(self, runtime: Runtime) -> None:
        self.runtime = runtime
        self.deps = runtime.deps
        self.factors: SingleFlight[str, LoadedFactors] = SingleFlight(0)
        self.prices: SingleFlight[PriceKey, PriceHistory] = SingleFlight(PRICE_CACHE_SIZE)
        self.ranges: SingleFlight[RangesKey, RangeOptions] = SingleFlight(
            self.deps.report_cache_size
        )
        self.reports: SingleFlight[ReportKey, FactorReport] = SingleFlight(
            self.deps.report_cache_size
        )
        self.vintage: Vintage | None = None

    # ------------------------------------------------------------------ public

    async def report(
        self,
        ticker: str,
        preset: RangePreset | None = None,
        start: date | None = None,
        end: date | None = None,
    ) -> FactorReport:
        """The report for an already validated ticker; no range and no dates means FULL."""
        ranges.check_request(preset, start, end)
        now = self._now()
        loaded = await self._factors()
        history = await self._history(ticker, now.date())
        cov = await self.runtime.run(ranges.coverage, history, loaded.frame)
        first, last = ranges.resolve(preset, start, end, cov)
        key: ReportKey = (ticker, first, last, loaded.vintage, now.date())

        async def make() -> FactorReport:
            def build() -> FactorReport:
                return assemble_report(
                    ticker,
                    history,
                    loaded.frame,
                    now=now,
                    factors_downloaded_at=loaded.vintage.downloaded_at,
                    start=first,
                    end=last,
                )

            return await self.runtime.run(build)

        return await self.reports.get(key, make)

    async def range_options(self, ticker: str) -> RangeOptions:
        """Availability of every preset for an already validated ticker."""
        now = self._now()
        loaded = await self._factors()
        history = await self._history(ticker, now.date())
        key: RangesKey = (ticker, loaded.vintage, now.date())

        async def make() -> RangeOptions:
            return await self.runtime.run(ranges.range_options, ticker, history, loaded.frame)

        return await self.ranges.get(key, make)

    async def report_html(
        self,
        ticker: str,
        preset: RangePreset | None = None,
        start: date | None = None,
        end: date | None = None,
    ) -> str:
        """The offline HTML report of the same (cached) report, from the unchanged renderer."""
        report = await self.report(ticker, preset, start, end)
        return await self.runtime.run(render_report_html, report)

    # ------------------------------------------------------------------ layers

    def _now(self) -> datetime:
        now = self.deps.now()
        if now.utcoffset() is None:
            raise ValueError("the injected clock must return a timezone-aware time")
        return now.astimezone(UTC)

    async def _factors(self) -> LoadedFactors:
        loaded = await self.factors.get("factors", self._load_factors)
        if loaded.vintage != self.vintage:
            self.vintage = loaded.vintage
            current = loaded.vintage
            self.reports.discard(lambda key: key[3] == current)
            self.ranges.discard(lambda key: key[1] == current)
        return loaded

    async def _load_factors(self) -> LoadedFactors:
        now = self._now()
        frame = await self.runtime.run(self.deps.load_factors, False, now)
        status = await self.runtime.run(self.deps.factor_status, now)
        if status is None:  # the loader always caches what it returns; be safe anyway
            last = pd.Timestamp(str(frame.index[-1])).date()
            return LoadedFactors(Vintage(last, None), frame)
        return LoadedFactors(Vintage(status.last_date, _utc(status.last_download_at)), frame)

    async def _history(self, ticker: str, today: date) -> PriceHistory:
        async def make() -> PriceHistory:
            return await self.runtime.run(self.deps.price_provider.fetch, ticker)

        return await self.prices.get((ticker, today), make)


def get_report_service(request: Request) -> ReportService:
    """FastAPI dependency: the ``ReportService`` of the app that received the request."""
    service: ReportService = request.app.state.report_service
    return service
