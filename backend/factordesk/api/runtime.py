"""Per-app runtime: worker threads and the single-flight factor refresh (dashboard spec DB3).

Blocking work (disk, network, regressions) runs through ``anyio.to_thread`` behind one shared
``CapacityLimiter`` so the event loop never blocks. Shared state here is touched only on the
event-loop thread; worker functions take inputs and return values.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable

import anyio
import anyio.to_thread
from fastapi import Request

from factordesk.api.deps import AppDeps
from factordesk.data.factors import SOURCE_URL, FactorStatus
from factordesk.report.schema import FactorDataStatus

logger = logging.getLogger(__name__)


def factor_data_status(status: FactorStatus | None) -> FactorDataStatus:
    """The API form of a ``FactorStatus``; ``available`` is False when nothing is cached."""
    if status is None:
        return FactorDataStatus(
            available=False,
            first_date=None,
            last_date=None,
            days_behind=None,
            last_download_at=None,
            stale=None,
            source_url=SOURCE_URL,
        )
    return FactorDataStatus(
        available=True,
        first_date=status.first_date,
        last_date=status.last_date,
        days_behind=status.days_behind,
        last_download_at=status.last_download_at,
        stale=status.stale,
        source_url=status.source_url,
    )


class Runtime:
    """Holds the injected deps, the worker limiter and the running refresh, if any."""

    def __init__(self, deps: AppDeps) -> None:
        self.deps = deps
        self.refresh_joiners = 0
        """Callers waiting on the refresh that is running now (0 when none is)."""
        self._limiter: anyio.CapacityLimiter | None = None
        self._limiter_loop: asyncio.AbstractEventLoop | None = None
        self._refresh: asyncio.Task[FactorDataStatus] | None = None

    def limiter(self) -> anyio.CapacityLimiter:
        """The shared worker limiter, created on first use inside the running loop."""
        loop = asyncio.get_running_loop()
        if self._limiter is None or self._limiter_loop is not loop:
            self._limiter = anyio.CapacityLimiter(self.deps.max_workers)
            self._limiter_loop = loop
        return self._limiter

    async def run[T, *Ts](self, fn: Callable[[*Ts], T], *args: *Ts) -> T:
        """Run a blocking function in a worker thread."""
        return await anyio.to_thread.run_sync(fn, *args, limiter=self.limiter())

    async def factor_status(self) -> FactorDataStatus:
        status = await self.run(self.deps.factor_status, self.deps.now())
        return factor_data_status(status)

    async def refresh_factors(self) -> FactorDataStatus:
        """Force a factor download; a call made while one runs joins it (single flight).

        A failed download raises to every waiter and leaves the cache as it was, because
        ``load_ff5_daily`` replaces the cache only after the new file validates.
        """
        task = self._refresh
        if task is None:
            task = asyncio.ensure_future(self._download())
            self._refresh = task
            task.add_done_callback(self._finished)
        self.refresh_joiners += 1
        try:
            # shield: a closed browser tab must not cancel a download that others wait for
            return await asyncio.shield(task)
        finally:
            self.refresh_joiners -= 1

    async def _download(self) -> FactorDataStatus:
        await self.run(self.deps.load_factors, True, self.deps.now())
        return await self.factor_status()

    def _finished(self, task: asyncio.Task[FactorDataStatus]) -> None:
        if self._refresh is task:
            self._refresh = None
        if not task.cancelled() and task.exception() is not None:
            logger.info("Factor refresh failed: %r", task.exception())


def get_runtime(request: Request) -> Runtime:
    """FastAPI dependency: the ``Runtime`` of the app that received the request."""
    runtime: Runtime = request.app.state.runtime
    return runtime
