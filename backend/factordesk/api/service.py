"""Report service: in-flight de-duplication, caches and worker threads (dashboard spec DB3).

Four layers, each a ``SingleFlight`` (a dict of running tasks plus an LRU of results):

1. factor frame: loaded on every request through ``load_factors(False, now)`` (which may run
   the 40-day auto-refresh), then identified by its vintage ``(last_date, last_download_at)``;
2. price history: key ``(ticker, today)``, matching the same-day cache of ``YFinanceProvider``;
3. report: key ``(ticker, start, end, vintage, today, model)`` after preset resolution, so
   ``range=3Y`` and the same explicit dates share one entry, and FF5 and FF6 never do;
4. ranges: the report key without start and end.

A request whose key is running awaits the same task through ``asyncio.shield``, so a closed
browser tab does not cancel work that others wait for. Failures are not cached; every waiter
gets the same exception. When the vintage changes, entries of other vintages are dropped.

Every report is built on the FF6 frame (``AppDeps.load_ff6``, cached per vintage and day) so it
carries the alpha strip. An FF5 report whose FF6 frame cannot be loaded falls back to the FF5
frame without the strip; an FF6 report fails with the loader's error.
Shared state is touched only on the event-loop thread; worker functions take inputs and return
values, so no locks are needed.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import OrderedDict
from collections.abc import Awaitable, Callable, Hashable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import TYPE_CHECKING

import pandas as pd
from fastapi import Request

from factordesk.api import ranges
from factordesk.api.errors import ApiException, to_api_exception
from factordesk.api.runtime import Runtime
from factordesk.data.factors import FactorError, FactorStatus
from factordesk.data.prices import PriceHistory, Security, check_currency, security_of
from factordesk.report.render_html import render_report_html
from factordesk.report.schema import FactorModel, FactorReport, RangeOptions, RangePreset

if TYPE_CHECKING:
    from factordesk.api.portfolio_models import PortfolioTree
    from factordesk.section_hooks.context import SectionInputs

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
    section_inputs: SectionInputs | None = None,
    security: Security | None = None,
    model: FactorModel = "ff5",
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
        section_inputs=section_inputs,
        security=security,
        model=model,
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

    def __contains__(self, key: object) -> bool:
        return key in self._done

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


class _NoSecurity(Exception):
    """Internal: the metadata read gave nothing; keeps ``SingleFlight`` from caching a None."""


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
type SecurityKey = tuple[str, date]
type RangesKey = tuple[str, Vintage, date]
type ReportKey = tuple[str, date | None, date | None, Vintage, date, FactorModel]
type PortfolioKey = tuple[
    str, FactorModel, RangePreset | None, date | None, date | None, Vintage, date
]


def _range_text(preset: RangePreset | None, start: date | None, end: date | None) -> str:
    """The requested range for the log: the preset, the dates, or FULL."""
    if preset is not None:
        return preset
    if start is None and end is None:
        return "FULL"
    return f"{start or 'first'}..{end or 'last'}"


def _log_factors(status: FactorStatus | None, now: datetime, seconds: float) -> None:
    """One INFO line: the factor dataset, whether it came from cache or a download, its vintage."""
    if status is None:
        logger.info("Factors: Fama-French 5 daily, no cache record (%.1f s)", seconds)
        return
    stamp = _utc(status.last_download_at)
    source = "downloaded" if stamp is not None and stamp >= now else "from cache"
    logger.info(
        "Factors: Fama-French 5 daily, %s, vintage %s (downloaded %s) (%.1f s)",
        source,
        status.last_date,
        "unknown" if stamp is None else stamp.date(),
        seconds,
    )


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
        self.portfolios: SingleFlight[PortfolioKey, FactorReport] = SingleFlight(
            self.deps.report_cache_size
        )
        self.securities: SingleFlight[SecurityKey, Security] = SingleFlight(PRICE_CACHE_SIZE * 4)
        self.inputs: SingleFlight[tuple[Vintage, date], SectionInputs | None] = SingleFlight(1)
        self.ff6: SingleFlight[tuple[Vintage, date], pd.DataFrame] = SingleFlight(1)
        self.vintage: Vintage | None = None

    # ------------------------------------------------------------------ public

    async def report(
        self,
        ticker: str,
        preset: RangePreset | None = None,
        start: date | None = None,
        end: date | None = None,
        model: FactorModel = "ff5",
    ) -> FactorReport:
        """The report for an already validated ticker; no range and no dates means FULL.

        ``model`` is the factor model, FF5 (default) or FF6 (FF5 plus momentum).
        """
        started = time.perf_counter()
        logger.info(
            "Report start: %s, model %s, range %s", ticker, model, _range_text(preset, start, end)
        )
        try:
            return await self._report(ticker, preset, start, end, model, started)
        except Exception as exc:
            category = to_api_exception(exc, ticker).code
            logger.info("Report refused: %s, reason %s", ticker, category)
            raise

    async def _report(
        self,
        ticker: str,
        preset: RangePreset | None,
        start: date | None,
        end: date | None,
        model: FactorModel,
        started: float,
    ) -> FactorReport:
        ranges.check_request(preset, start, end)
        now = self._now()
        loaded = await self._factors()
        security = await self._security(ticker, now.date())
        history = await self._history(ticker, now.date())
        cov = await self.runtime.run(ranges.coverage, history, loaded.frame)
        first, last = ranges.resolve(preset, start, end, cov)
        key: ReportKey = (ticker, first, last, loaded.vintage, now.date(), model)
        if key in self.reports:
            logger.info(
                "Report cache hit: %s, model %s (%.0f ms)",
                ticker,
                model,
                (time.perf_counter() - started) * 1000,
            )

        async def make() -> FactorReport:
            frame = await self._model_frame(loaded, now, model)
            inputs = await self._section_inputs(loaded.vintage, now)
            inputs = await self._with_world_benchmark(inputs)
            inputs = await self._with_macro(inputs)

            def build() -> FactorReport:
                return assemble_report(
                    ticker,
                    history,
                    frame,
                    now=now,
                    factors_downloaded_at=loaded.vintage.downloaded_at,
                    start=first,
                    end=last,
                    section_inputs=inputs,
                    security=security,
                    model=model,
                )

            built_at = time.perf_counter()
            report = await self.runtime.run(build)
            logger.info(
                "Report built: %s, model %s in %.1f s (total %.1f s)",
                ticker,
                model,
                time.perf_counter() - built_at,
                time.perf_counter() - started,
            )
            return report

        return await self.reports.get(key, make)

    async def portfolio_report(
        self,
        tree: PortfolioTree,
        preset: RangePreset | None = None,
        start: date | None = None,
        end: date | None = None,
        model: FactorModel = "ff6",
    ) -> FactorReport:
        """The report of a portfolio tree (``api.portfolio_report``): in-memory cache only.

        The key is the SHA-256 of the canonical tree JSON, the model, the range as asked, the
        factor vintage and the day, so a new price day or factor file never serves an old result.
        Nothing about the portfolio is written to disk or logged beyond counts.
        """
        from factordesk.api import portfolio_report as pr

        started = time.perf_counter()
        ranges.check_request(preset, start, end)
        plan = pr.plan_of(tree)
        logger.info(
            "Portfolio report start: %d instruments, model %s, range %s",
            len(plan.rows),
            model,
            _range_text(preset, start, end),
        )
        now = self._now()
        loaded = await self._factors()
        key: PortfolioKey = (plan.digest, model, preset, start, end, loaded.vintage, now.date())
        if key in self.portfolios:
            logger.info("Portfolio report cache hit")

        async def make() -> FactorReport:
            for ticker in plan.tickers:
                await self._security(ticker, now.date())  # refuses a currency other than USD
            histories = await self.runtime.run(
                pr.fetch_histories, self.deps.price_provider, plan.tickers
            )
            frame = await self._model_frame(loaded, now, model)
            inputs = await self._with_world_benchmark(None)

            def build() -> FactorReport:
                return pr.build_portfolio_report(
                    plan,
                    histories,
                    frame,
                    model,
                    now=now,
                    factors_downloaded_at=loaded.vintage.downloaded_at,
                    preset=preset,
                    start=start,
                    end=end,
                    inputs=inputs,
                )

            report = await self.runtime.run(build)
            logger.info("Portfolio report built in %.1f s", time.perf_counter() - started)
            return report

        try:
            return await self.portfolios.get(key, make)
        except Exception as exc:
            logger.info("Portfolio report refused: reason %s", to_api_exception(exc).code)
            raise

    async def range_options(self, ticker: str) -> RangeOptions:
        """Availability of every preset for an already validated ticker."""
        now = self._now()
        loaded = await self._factors()
        await self._security(ticker, now.date())
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
        model: FactorModel = "ff5",
    ) -> str:
        """The offline HTML report of the same (cached) report, from the unchanged renderer."""
        report = await self.report(ticker, preset, start, end, model)
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
            self.portfolios.discard(lambda key: key[5] == current)
        return loaded

    async def _load_factors(self) -> LoadedFactors:
        now = self._now()
        began = time.perf_counter()
        frame = await self.runtime.run(self.deps.load_factors, False, now)
        status = await self.runtime.run(self.deps.factor_status, now)
        _log_factors(status, now, time.perf_counter() - began)
        if status is None:  # the loader always caches what it returns; be safe anyway
            last = pd.Timestamp(str(frame.index[-1])).date()
            return LoadedFactors(Vintage(last, None), frame)
        return LoadedFactors(Vintage(status.last_date, _utc(status.last_download_at)), frame)

    async def _model_frame(
        self, loaded: LoadedFactors, now: datetime, model: FactorModel
    ) -> pd.DataFrame:
        """The factor frame of a report: the FF6 frame, or the FF5 one when FF5 cannot have it.

        FF6 needs ``AppDeps.load_ff6``; without it the request is refused, and a loader error is
        raised as is. FF5 uses the FF6 frame for the alpha strip when it loads, else the FF5 frame.
        """
        loader = self.deps.load_ff6
        if loader is None:
            if model == "ff6":
                raise ApiException(
                    "bad_request",
                    "The FF6 model is not available on this server.",
                    "Use the FF5 model.",
                )
            return loaded.frame

        async def make() -> pd.DataFrame:
            return await self.runtime.run(loader, now)

        try:
            return await self.ff6.get((loaded.vintage, now.date()), make)
        except (FactorError, OSError):
            if model == "ff6":
                raise
            logger.warning("Momentum factor unavailable; FF5 report without the alpha strip")
            return loaded.frame

    async def _section_inputs(self, vintage: Vintage, now: datetime) -> SectionInputs | None:
        """The extra data of the optional sections, once per vintage and day (None: not wired)."""
        loader = self.deps.load_section_inputs
        if loader is None:
            return None

        async def make() -> SectionInputs | None:
            return await self.runtime.run(loader, now)

        return await self.inputs.get((vintage, now.date()), make)

    async def _security(self, ticker: str, today: date) -> Security | None:
        """The ticker's Yahoo metadata, or None when unavailable; refuses a non-USD currency.

        Metadata never blocks a report: a missing or failed read gives None (not cached, so the
        next request tries again). A known currency other than USD raises
        ``UnsupportedCurrencyError`` before the price history is downloaded (roadmap N1).
        """

        async def make() -> Security:
            found = await self.runtime.run(security_of, self.deps.price_provider, ticker)
            if found is None:
                raise _NoSecurity
            return found

        try:
            security = await self.securities.get((ticker, today), make)
        except _NoSecurity:
            return None
        check_currency(ticker, security)
        return security

    async def _with_world_benchmark(self, inputs: SectionInputs | None) -> SectionInputs | None:
        """``inputs`` plus the ACWI and IEUR histories, refreshed now (None: not wired)."""
        loader = self.deps.load_world_benchmark
        if loader is None:
            return inputs
        import dataclasses

        from factordesk.section_hooks.context import SectionInputs

        benchmark = await self.runtime.run(loader)
        europe_loader = self.deps.load_europe_benchmark
        europe = None if europe_loader is None else await self.runtime.run(europe_loader)
        return dataclasses.replace(
            inputs or SectionInputs(), world_benchmark=benchmark, europe_benchmark=europe
        )

    async def _with_macro(self, inputs: SectionInputs | None) -> SectionInputs | None:
        """``inputs`` plus the macro section's funds and dollar index (None: not wired)."""
        loader = self.deps.load_macro
        if loader is None:
            return inputs
        import dataclasses

        from factordesk.section_hooks.context import SectionInputs

        macro = await self.runtime.run(loader)
        return dataclasses.replace(inputs or SectionInputs(), macro=macro)

    async def _history(self, ticker: str, today: date) -> PriceHistory:
        async def make() -> PriceHistory:
            asked = self._now()
            began = time.perf_counter()
            history = await self.runtime.run(self.deps.price_provider.fetch, ticker)
            logger.info(
                "Prices %s: %s, %d days, %.1f s",
                ticker,
                "downloaded" if history.fetched_at >= asked else "from cache",
                len(history.frame),
                time.perf_counter() - began,
            )
            return history

        return await self.prices.get((ticker, today), make)


def get_report_service(request: Request) -> ReportService:
    """FastAPI dependency: the ``ReportService`` of the app that received the request."""
    service: ReportService = request.app.state.report_service
    return service
