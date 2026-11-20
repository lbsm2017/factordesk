"""Report service: in-flight de-duplication, caches and worker threads (dashboard spec DB3).

Four layers, each a ``SingleFlight`` (a dict of running tasks plus an LRU of results):

1. factor frame: loaded on every request through ``load_factors(False, now)`` (which may run
   the 40-day auto-refresh), then identified by its vintage ``(last_date, last_download_at)``;
2. price history: key ``(ticker, today)``, matching the same-day cache of ``YFinanceProvider``;
3. report: key ``(ticker, start, end, vintage, today, model, factor set, currency)`` after
   preset resolution, so ``range=3Y`` and the same explicit dates share one entry, and FF5 and
   FF6 (or the US and Europe factor sets) never do;
4. ranges: the report key without start and end.

A request whose key is running awaits the same task through ``asyncio.shield``, so a closed
browser tab does not cancel work that others wait for. Failures are not cached; every waiter
gets the same exception. When the vintage changes, entries of other vintages are dropped.

Every report is built on the FF6 frame (``AppDeps.load_ff6``, cached per vintage and day) so it
carries the alpha strip. An FF5 report whose FF6 frame cannot be loaded falls back to the FF5
frame without the strip; an FF6 report fails with the loader's error.
A request for the Europe factor set (``factor_set="europe"``) uses ``AppDeps.load_europe_ff6`` for
its factors and its ranges, always with momentum; the US vintage still names the cache entries
(the Europe frame is re-read once a day, like the FF6 one).
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
from typing import TYPE_CHECKING, cast

import pandas as pd
from fastapi import Request

from factordesk.analytics.currency import convert_history, listing_currency
from factordesk.api import ranges
from factordesk.api.currency_ctx import CurrencyContext
from factordesk.api.errors import ApiException, to_api_exception
from factordesk.api.runtime import Runtime
from factordesk.data.factors import FactorError, FactorStatus
from factordesk.data.french import DEFAULT_FACTOR_SET, FactorSet
from factordesk.data.prices import PriceHistory, Security, security_of
from factordesk.report.render_html import render_report_html
from factordesk.report.schema import (
    CurrencyInfo,
    FactorModel,
    FactorReport,
    RangeOptions,
    RangePreset,
    ReferenceCurrency,
)

if TYPE_CHECKING:
    from factordesk.api.portfolio_models import PortfolioTree
    from factordesk.section_hooks.context import SectionInputs, WorldBenchmarkInput

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
    reference_currency: ReferenceCurrency = "USD",
    currency: CurrencyInfo | None = None,
    audit_history: PriceHistory | None = None,
    factor_set: FactorSet = DEFAULT_FACTOR_SET,
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
        reference_currency=reference_currency,
        currency=currency,
        converted=True,  # ``ReportService`` has converted the history and the factors
        audit_history=audit_history,
        factor_set=factor_set,
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
type RangesKey = tuple[str, Vintage, date, FactorSet]
type ReportKey = tuple[
    str, date | None, date | None, Vintage, date, FactorModel, FactorSet, ReferenceCurrency
]
type PortfolioKey = tuple[
    str,
    FactorModel,
    RangePreset | None,
    date | None,
    date | None,
    Vintage,
    date,
    ReferenceCurrency,
    FactorSet,
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
        self.ff6: SingleFlight[tuple[Vintage, date, FactorSet], pd.DataFrame] = SingleFlight(2)
        self.converted: SingleFlight[
            tuple[Vintage, date, ReferenceCurrency, bool, FactorSet], pd.DataFrame
        ] = SingleFlight(4)
        self.vintage: Vintage | None = None

    # ------------------------------------------------------------------ public

    async def report(
        self,
        ticker: str,
        preset: RangePreset | None = None,
        start: date | None = None,
        end: date | None = None,
        model: FactorModel = "ff5",
        ccy: ReferenceCurrency = "USD",
        factor_set: FactorSet = DEFAULT_FACTOR_SET,
    ) -> FactorReport:
        """The report for an already validated ticker; no range and no dates means FULL.

        ``model`` is the factor model, FF5 (default) or FF6 (FF5 plus momentum). ``ccy`` is the
        reference currency of every figure, USD (default) or EUR. ``factor_set`` is the regional
        Fama-French set, US (default) or Europe.
        """
        started = time.perf_counter()
        logger.info(
            "Report start: %s, model %s, %s, factors %s, range %s",
            ticker,
            model,
            ccy,
            factor_set,
            _range_text(preset, start, end),
        )
        try:
            return await self._report(ticker, preset, start, end, model, ccy, started, factor_set)
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
        ccy: ReferenceCurrency,
        started: float,
        factor_set: FactorSet = DEFAULT_FACTOR_SET,
    ) -> FactorReport:
        ranges.check_request(preset, start, end)
        now = self._now()
        loaded = await self._factors()
        base = await self._set_frame(loaded, now, factor_set)
        security = await self._security(ticker, now.date())
        listing, scale = listing_currency(ticker, security)
        history = await self._history(ticker, now.date())
        ctx = CurrencyContext(ccy, self.deps.currency)
        local = history  # the audit reads the prices as the exchange lists them
        history = await self.runtime.run(self._to_reference, ticker, history, listing, scale, ctx)
        cov = await self.runtime.run(ranges.coverage, history, base)
        first, last = ranges.resolve(preset, start, end, cov)
        key: ReportKey = (ticker, first, last, loaded.vintage, now.date(), model, factor_set, ccy)
        if key in self.reports:
            logger.info(
                "Report cache hit: %s, model %s (%.0f ms)",
                ticker,
                model,
                (time.perf_counter() - started) * 1000,
            )

        async def make() -> FactorReport:
            frame = await self._model_frame(loaded, now, model, ctx, factor_set)
            inputs = await self._section_inputs(loaded.vintage, now)
            inputs = await self._with_world_benchmark(inputs, ctx, factor_set)
            inputs = await self._with_reference(inputs, ctx, loaded, now, model)
            inputs = await self._with_us_factors(inputs, ctx, loaded, now, model, factor_set)
            inputs = await self._with_macro(inputs, ctx)
            inputs = await self._with_energy(inputs, ctx)

            def build() -> FactorReport:
                return assemble_report(
                    ticker,
                    history,
                    frame,
                    now=now,
                    factors_downloaded_at=_downloaded_at(loaded, base, factor_set),
                    start=first,
                    end=last,
                    section_inputs=inputs,
                    security=security,
                    model=model,
                    reference_currency=ccy,
                    currency=None if ccy == "USD" else ctx.info(),
                    audit_history=local,
                    factor_set=factor_set,
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
        factor vintage, the day, the reference currency and the factor set (``tree.factor_set``),
        so a new price day or factor file never serves an old result.
        Nothing about the portfolio is written to disk or logged beyond counts.
        """
        from factordesk.api import portfolio_report as pr

        started = time.perf_counter()
        ranges.check_request(preset, start, end)
        plan = pr.plan_of(tree)
        ccy = tree.reference_currency
        factor_set = tree.factor_set
        tickers = pr.tickers_for(plan, ccy)
        logger.info(
            "Portfolio report start: %d instruments, model %s, %s, factors %s, range %s",
            len(plan.rows),
            model,
            ccy,
            factor_set,
            _range_text(preset, start, end),
        )
        now = self._now()
        loaded = await self._factors()
        key: PortfolioKey = (
            plan.digest,
            model,
            preset,
            start,
            end,
            loaded.vintage,
            now.date(),
            ccy,
            factor_set,
        )
        if key in self.portfolios:
            logger.info("Portfolio report cache hit")

        async def make() -> FactorReport:
            ctx = CurrencyContext(ccy, self.deps.currency)
            listings: dict[str, tuple[str, float]] = {}
            for ticker in tickers:  # refuses a currency that cannot be converted
                security = await self._security(ticker, now.date())
                listings[ticker] = listing_currency(ticker, security)
            histories = await self.runtime.run(
                pr.fetch_histories, self.deps.price_provider, tickers
            )
            frame = await self._model_frame(loaded, now, model, ctx, factor_set)
            inputs = await self._with_world_benchmark(None, ctx, factor_set)
            inputs = await self._with_reference(inputs, ctx, loaded, now, model)
            inputs = await self._with_us_factors(inputs, ctx, loaded, now, model, factor_set)
            inputs = await self._with_macro(inputs, ctx)
            inputs = await self._with_energy(inputs, ctx)

            def build() -> FactorReport:
                converted = {
                    t: self._to_reference(t, h, *listings[t], ctx) for t, h in histories.items()
                }  # the local histories go too: a hedged line is hedged on its local return
                return pr.build_portfolio_report(
                    plan,
                    converted,
                    frame,
                    model,
                    now=now,
                    factors_downloaded_at=_downloaded_at(loaded, frame, factor_set),
                    preset=preset,
                    start=start,
                    end=end,
                    inputs=inputs,
                    ctx=ctx,
                    usd_rf=loaded.frame["RF"],
                    listings={t: code for t, (code, _) in listings.items()},
                    local_histories=histories,
                    factor_set=factor_set,
                )

            report = await self.runtime.run(build)
            logger.info("Portfolio report built in %.1f s", time.perf_counter() - started)
            return report

        try:
            return await self.portfolios.get(key, make)
        except Exception as exc:
            logger.info("Portfolio report refused: reason %s", to_api_exception(exc).code)
            raise

    async def range_options(
        self, ticker: str, factor_set: FactorSet = DEFAULT_FACTOR_SET
    ) -> RangeOptions:
        """Availability of every preset for an already validated ticker, on the dates of the
        factor set."""
        now = self._now()
        loaded = await self._factors()
        base = await self._set_frame(loaded, now, factor_set)
        await self._security(ticker, now.date())
        history = await self._history(ticker, now.date())
        key: RangesKey = (ticker, loaded.vintage, now.date(), factor_set)

        async def make() -> RangeOptions:
            return await self.runtime.run(ranges.range_options, ticker, history, base)

        return await self.ranges.get(key, make)

    async def report_html(
        self,
        ticker: str,
        preset: RangePreset | None = None,
        start: date | None = None,
        end: date | None = None,
        model: FactorModel = "ff5",
        factor_set: FactorSet = DEFAULT_FACTOR_SET,
    ) -> str:
        """The offline HTML report of the same (cached) report, from the unchanged renderer."""
        report = await self.report(ticker, preset, start, end, model, "USD", factor_set)
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
            self.converted.discard(lambda key: key[0] == current)
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
        self,
        loaded: LoadedFactors,
        now: datetime,
        model: FactorModel,
        ctx: CurrencyContext | None = None,
        factor_set: FactorSet = DEFAULT_FACTOR_SET,
    ) -> pd.DataFrame:
        """The factor frame of a report, in the reference currency of ``ctx`` (default USD).

        The USD frame is the FF6 frame, or the FF5 one when FF5 cannot have it; the EUR frame is
        that frame converted once per vintage and day (``CurrencyContext.factors``).
        """
        frame = await self._usd_model_frame(loaded, now, model, factor_set)
        if ctx is None or ctx.ref == "USD":
            return frame
        key: tuple[Vintage, date, ReferenceCurrency, bool, FactorSet] = (
            loaded.vintage,
            now.date(),
            cast(ReferenceCurrency, ctx.ref),
            "Mom" in frame.columns,
            factor_set,
        )

        async def make() -> pd.DataFrame:
            return await self.runtime.run(ctx.factors, frame)

        out = await self.converted.get(key, make)
        ctx.absorb(out)
        return out

    async def _usd_model_frame(
        self,
        loaded: LoadedFactors,
        now: datetime,
        model: FactorModel,
        factor_set: FactorSet = DEFAULT_FACTOR_SET,
    ) -> pd.DataFrame:
        """The USD frame: the FF6 frame, or the FF5 one when FF5 cannot have it.

        FF6 needs ``AppDeps.load_ff6``; without it the request is refused, and a loader error is
        raised as is. FF5 uses the FF6 frame for the alpha strip when it loads, else the FF5 frame.
        The Europe set has no FF5-only fallback: its frame is the Europe FF6 frame or an error.
        """
        if factor_set != "us":
            return await self._europe_frame(loaded, now)
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
            return await self.ff6.get((loaded.vintage, now.date(), "us"), make)
        except (FactorError, OSError):
            if model == "ff6":
                raise
            logger.warning("Momentum factor unavailable; FF5 report without the alpha strip")
            return loaded.frame

    async def _europe_frame(self, loaded: LoadedFactors, now: datetime) -> pd.DataFrame:
        """The daily Developed Europe FF6 frame (USD), once per vintage and day.

        Refused when ``AppDeps.load_europe_ff6`` is not wired; a loader error is raised as is.
        """
        loader = self.deps.load_europe_ff6
        if loader is None:
            raise ApiException(
                "network",
                "The Europe factor set is not available on this server.",
                "Use the US factor set.",
            )

        async def make() -> pd.DataFrame:
            return await self.runtime.run(loader, now)

        return await self.ff6.get((loaded.vintage, now.date(), "europe"), make)

    async def _set_frame(
        self, loaded: LoadedFactors, now: datetime, factor_set: FactorSet
    ) -> pd.DataFrame:
        """The daily USD frame whose dates set the ranges and the coverage of a request: the
        cached US five-factor frame, or the Europe FF6 frame."""
        if factor_set == "us":
            return loaded.frame
        return await self._europe_frame(loaded, now)

    async def _section_inputs(self, vintage: Vintage, now: datetime) -> SectionInputs | None:
        """The extra data of the optional sections, once per vintage and day (None: not wired)."""
        loader = self.deps.load_section_inputs
        if loader is None:
            return None

        async def make() -> SectionInputs | None:
            return await self.runtime.run(loader, now)

        return await self.inputs.get((vintage, now.date()), make)

    async def _security(self, ticker: str, today: date) -> Security | None:
        """The ticker's Yahoo metadata, or None when unavailable; refuses a currency that cannot
        be converted.

        Metadata never blocks a report: a missing or failed read gives None (not cached, so the
        next request tries again). A known currency outside ``data.fx.CURRENCIES`` raises
        ``UnsupportedCurrencyError`` before the price history is downloaded.
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
        listing_currency(ticker, security)
        return security

    async def _with_world_benchmark(
        self,
        inputs: SectionInputs | None,
        ctx: CurrencyContext,
        factor_set: FactorSet = DEFAULT_FACTOR_SET,
    ) -> SectionInputs | None:
        """``inputs`` plus the ACWI and IEUR histories, refreshed now (None: not wired).

        In the EUR view the two US-dollar histories are converted and the shrunk betas (they
        need US factor portfolios) are left out; they are also left out with the Europe factor
        set, whose report says so in its notes."""
        import dataclasses

        loader = self.deps.load_world_benchmark
        if (
            (ctx.ref != "USD" or factor_set != "us")
            and inputs is not None
            and inputs.shrinkage_portfolios is not None
        ):
            inputs = dataclasses.replace(inputs, shrinkage_portfolios=None)
            if ctx.ref != "USD":
                ctx.note("The shrunk-betas section is not available in EUR yet.")
        if loader is None:
            return inputs

        from factordesk.section_hooks.context import SectionInputs

        benchmark = await self.runtime.run(loader)
        europe_loader = self.deps.load_europe_benchmark
        europe = None if europe_loader is None else await self.runtime.run(europe_loader)
        if ctx.ref != "USD":
            benchmark = await self.runtime.run(self._benchmark_to_reference, benchmark, ctx)
            if europe is not None:
                europe = await self.runtime.run(self._benchmark_to_reference, europe, ctx)
        return dataclasses.replace(
            inputs or SectionInputs(), world_benchmark=benchmark, europe_benchmark=europe
        )

    @staticmethod
    def _benchmark_to_reference(
        bench: WorldBenchmarkInput, ctx: CurrencyContext
    ) -> WorldBenchmarkInput:
        """A US-dollar benchmark history in the reference currency (blocking)."""
        import dataclasses

        if bench.history is None:
            return bench
        history, dropped = convert_history(bench.history, lambda d: ctx.prices("USD", d))
        _note_left_out(ctx, "benchmark", bench.history, history, dropped)
        return dataclasses.replace(bench, history=history)

    @staticmethod
    def _to_reference(
        ticker: str, history: PriceHistory, listing: str, scale: float, ctx: CurrencyContext
    ) -> PriceHistory:
        """A listing's price history in the reference currency (blocking; the same object when
        no conversion is needed). Dates without an exchange rate are left out and noted."""
        if listing == ctx.ref and scale == 1.0:
            return history
        converted, dropped = convert_history(history, lambda d: ctx.prices(listing, d), scale)
        _note_left_out(ctx, ticker, history, converted, dropped)
        return converted

    async def _with_reference(
        self,
        inputs: SectionInputs | None,
        ctx: CurrencyContext,
        loaded: LoadedFactors,
        now: datetime,
        model: FactorModel,
    ) -> SectionInputs | None:
        """``inputs`` plus what the macro and energy sections need in the EUR view: the USD/EUR
        return on the subject's calendar and the US dollar risk-free rate. The USD view is
        returned as it is."""
        if ctx.ref == "USD" or (self.deps.load_macro is None and self.deps.load_energy is None):
            return inputs
        import dataclasses

        from factordesk.section_hooks.context import ReferenceInput, SectionInputs

        usd = await self._usd_model_frame(loaded, now, model)  # always the US dollar rate
        reference = ReferenceInput(lambda dates: ctx.returns("USD", dates), usd["RF"])
        return dataclasses.replace(inputs or SectionInputs(), reference=reference)

    async def _with_us_factors(
        self,
        inputs: SectionInputs | None,
        ctx: CurrencyContext,
        loaded: LoadedFactors,
        now: datetime,
        model: FactorModel,
        factor_set: FactorSet,
    ) -> SectionInputs | None:
        """``inputs`` plus the US frame, when the factor set is not the US one.

        The macro, energy and world beta sections keep their US inputs: they run on a second
        analysis sample built on the frame the US set would give for this request (converted to
        the reference currency exactly as the US report converts it). The US set is returned as
        it is."""
        if factor_set == "us":
            return inputs
        import dataclasses

        from factordesk.section_hooks.context import SectionInputs, UsFactorsInput

        frame = await self._model_frame(loaded, now, model, ctx, "us")
        us = UsFactorsInput(frame, loaded.vintage.downloaded_at)
        return dataclasses.replace(inputs or SectionInputs(), us_factors=us)

    async def _with_macro(
        self, inputs: SectionInputs | None, ctx: CurrencyContext
    ) -> SectionInputs | None:
        """``inputs`` plus the macro section's funds and dollar index (None: not wired). In the
        EUR view the section converts its legs (``_with_reference``)."""
        loader = self.deps.load_macro
        if loader is None:
            return inputs
        import dataclasses

        from factordesk.section_hooks.context import SectionInputs

        macro = await self.runtime.run(loader)
        return dataclasses.replace(inputs or SectionInputs(), macro=macro)

    async def _with_energy(
        self, inputs: SectionInputs | None, ctx: CurrencyContext
    ) -> SectionInputs | None:
        """``inputs`` plus the energy section's oil, gas and KRBN data (None: not wired). In the
        EUR view the section converts its legs (``_with_reference``)."""
        loader = self.deps.load_energy
        if loader is None:
            return inputs
        import dataclasses

        from factordesk.section_hooks.context import SectionInputs

        energy = await self.runtime.run(loader)
        return dataclasses.replace(inputs or SectionInputs(), energy=energy)

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


def _downloaded_at(
    loaded: LoadedFactors, frame: pd.DataFrame, factor_set: FactorSet
) -> datetime | None:
    """When the factor files of the set were downloaded: the US vintage's time, or for Europe
    the time its five-factor file carries (``frame.attrs["ff5"]``, set by ``join_momentum``)."""
    if factor_set == "us":
        return loaded.vintage.downloaded_at
    ff5 = cast("dict[str, object]", frame.attrs.get("ff5") or {})
    raw = ff5.get("downloaded_at")
    if not isinstance(raw, str):
        return None
    try:
        return _utc(datetime.fromisoformat(raw))
    except ValueError:
        return None


def _day(moment: pd.Timestamp) -> str:
    """``4 Jan 1999``."""
    return f"{moment.day} {moment:%b %Y}"


def _note_left_out(
    ctx: CurrencyContext, label: str, local: PriceHistory, converted: PriceHistory, dropped: int
) -> None:
    """Tell the report which dates the conversion left out: the edges (before the first and
    after the last exchange rate) and, apart from them, dates inside the series with no rate."""
    if not dropped:
        return
    unit = {"EUR": "euro", "USD": "US dollar"}.get(ctx.ref, ctx.ref)
    kept = converted.frame.index
    if len(kept) == 0:
        ctx.note(f"{label}: no date has an exchange rate.")
        return
    dates = local.frame.index.unique()
    before = int((dates < kept[0]).sum())
    after = int((dates > kept[-1]).sum())
    if before:
        ctx.note(
            f"Dates before the first {unit} exchange rate ({_day(kept[0])}) "
            f"are left out of the {unit} view ({label})."
        )
    if after:
        ctx.note(
            f"Dates after the last {unit} exchange rate ({_day(kept[-1])}) "
            f"are left out of the {unit} view ({label})."
        )
    gaps = dropped - before - after
    if gaps:
        ctx.note(
            f"{label}: {gaps} dates inside the series had no exchange rate "
            "and are left out of the analysis."
        )


def get_report_service(request: Request) -> ReportService:
    """FastAPI dependency: the ``ReportService`` of the app that received the request."""
    service: ReportService = request.app.state.report_service
    return service
