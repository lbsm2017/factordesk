"""Progress streams of the three report endpoints (Sprint 4, S4-5).

Each ``.../stream`` endpoint takes the same input as its plain endpoint and answers with
server-sent events (``text/event-stream``):

- ``event: step``: a ``ProgressStep``, sent when the run reaches a step (``factordesk.progress``);
- ``event: report``: the ``FactorReport``, exactly the body of the plain endpoint;
- ``event: error``: an ``ApiErrorEvent``, the plain endpoint's ``ApiError`` plus its HTTP status.

The stream ends after ``report`` or ``error``. A comment line (``: keep-alive``) is sent every
``KEEP_ALIVE_SECONDS`` while the run has nothing new to say. A report already in the cache is
sent at once with no step events. A request the framework refuses before the run starts (a date
that is not a date, a file over 1 MB, no file) is the plain endpoint's HTTP error, not an event.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncGenerator, AsyncIterator, Awaitable, Callable
from typing import Annotated, Any

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import StreamingResponse

from factordesk import progress
from factordesk.api.errors import ApiException, check_ticker, to_api_exception
from factordesk.api.portfolio_models import PortfolioTree
from factordesk.api.routes_report import Ccy, End, Model, Preset, Service, Start
from factordesk.api.routes_upload import _too_large  # pyright: ignore[reportPrivateUsage]
from factordesk.api.runtime import get_runtime
from factordesk.data.upload import MAX_UPLOAD_BYTES
from factordesk.report.schema import (
    ApiErrorEvent,
    FactorModel,
    FactorReport,
    ProgressStep,
    ProgressStepId,
    ReferenceCurrency,
)

logger = logging.getLogger(__name__)

KEEP_ALIVE_SECONDS = 15.0
"""Silence after which a comment line is sent, so a proxy does not close the stream."""

INTERNAL_MESSAGE = "The report could not be computed."
INTERNAL_ACTION = "Try again. If it happens again, report it with this page's address."

router = APIRouter(prefix="/api/report")


class EventStreamResponse(StreamingResponse):
    media_type = "text/event-stream"


_DOC: dict[int | str, dict[str, Any]] = {
    200: {
        "model": ProgressStep | FactorReport | ApiErrorEvent,
        "description": (
            "A stream of server-sent events. `step` (data: ProgressStep) for each step reached, "
            "then one `report` (data: FactorReport, as the plain endpoint) or one `error` "
            "(data: ApiErrorEvent). A cached report sends `report` alone."
        ),
    }
}

_Run = Callable[[], Awaitable[FactorReport]]


def _event(name: str, data: str) -> str:
    return f"event: {name}\ndata: {data}\n\n"


def _error_event(exc: BaseException, ticker: str | None) -> str:
    error = to_api_exception(exc, ticker)
    if error.code == "internal":  # the text of an unexpected error is logged, never sent
        logger.error("Unhandled %s in a report stream", type(exc).__name__, exc_info=exc)
        error = ApiException("internal", INTERNAL_MESSAGE, INTERNAL_ACTION)
    else:
        logger.info("%s in a report stream: %s", error.code, error.message)
    body = ApiErrorEvent(
        code=error.code, message=error.message, action=error.action, status=error.status
    )
    return _event("error", body.model_dump_json())


async def _events(
    plan: list[ProgressStepId], run: _Run, ticker: str | None = None
) -> AsyncGenerator[str]:
    """Run ``run`` and yield its events. The reporter lives in the run's own task, so the tasks
    and worker threads the run starts report to this stream and to no other."""
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue[ProgressStep | None] = asyncio.Queue()

    def emit(step: ProgressStep) -> None:  # called from the loop or from a worker thread
        loop.call_soon_threadsafe(queue.put_nowait, step)

    async def work() -> FactorReport:
        with progress.reporting(progress.StepReporter(plan, emit)):
            return await run()

    def finished(done: asyncio.Task[FactorReport]) -> None:
        if not done.cancelled():
            done.exception()  # mark a failure as seen, even when the client has left
        queue.put_nowait(None)

    task = asyncio.ensure_future(work())
    task.add_done_callback(finished)
    try:
        while True:
            try:
                item = await asyncio.wait_for(queue.get(), KEEP_ALIVE_SECONDS)
            except TimeoutError:
                yield ": keep-alive\n\n"
                continue
            if item is not None:
                yield _event("step", item.model_dump_json())
                continue
            try:
                report = task.result()
            except Exception as exc:
                yield _error_event(exc, ticker)
            else:
                yield _event("report", report.model_dump_json(by_alias=True))
            return
    finally:
        if not task.done():  # the client left; shared work in the service goes on regardless
            task.cancel()


def _stream(events: AsyncIterator[str]) -> EventStreamResponse:
    return EventStreamResponse(
        events, headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )


@router.get("/{ticker}/stream", response_class=EventStreamResponse, responses=_DOC)
async def stream_report(
    ticker: str,
    service: Service,
    preset: Preset = None,
    start: Start = None,
    end: End = None,
    model: Model = "ff5",
    ccy: Ccy = "USD",
) -> EventStreamResponse:
    """Progress and result of ``GET /api/report/{ticker}``, as server-sent events."""
    plan = progress.plan_of(fx=ccy == "EUR")

    async def run() -> FactorReport:
        return await service.report(check_ticker(ticker), preset, start, end, model, ccy)

    return _stream(_events(plan, run, ticker.upper()))


@router.post("/portfolio/stream", response_class=EventStreamResponse, responses=_DOC)
async def stream_portfolio_report(
    tree: PortfolioTree,
    service: Service,
    preset: Preset = None,
    start: Start = None,
    end: End = None,
    model: Model = "ff6",
) -> EventStreamResponse:
    """Progress and result of ``POST /api/report/portfolio``, as server-sent events."""
    plan = progress.plan_of(fx=tree.reference_currency == "EUR")

    async def run() -> FactorReport:
        return await service.portfolio_report(tree, preset, start, end, model)

    return _stream(_events(plan, run))


@router.post("/upload/stream", response_class=EventStreamResponse, responses=_DOC)
async def stream_upload_report(
    request: Request,
    file: Annotated[UploadFile, File(description="CSV with a date and a return column.")],
    name: Annotated[str | None, Form(description="Display name of the record.")] = None,
    gross_net: Annotated[
        str | None, Form(description="gross or net of fees; empty when unknown.")
    ] = None,
    model: Annotated[
        FactorModel, Form(description="Factor model: ff5 (default) or ff6 (FF5 plus momentum).")
    ] = "ff5",
    record_currency: Annotated[
        ReferenceCurrency, Form(description="Currency of the record itself: USD (default) or EUR.")
    ] = "USD",
    ccy: Annotated[
        ReferenceCurrency, Form(description="Reference currency of the report: USD or EUR.")
    ] = "USD",
) -> EventStreamResponse:
    """Progress and result of ``POST /api/report/upload``, as server-sent events.

    An upload has no price download, so its steps start at the factor data; ``fx`` is a step
    when the record or the report is in euros.
    """
    from factordesk.api.routes_upload import build_upload_report

    runtime = get_runtime(request)
    raw = await file.read(MAX_UPLOAD_BYTES + 1)
    await file.close()
    if len(raw) > MAX_UPLOAD_BYTES:
        raise _too_large()
    plan = progress.plan_of(prices=False, fx="EUR" in (record_currency, ccy))

    async def run() -> FactorReport:
        return await runtime.run(
            build_upload_report, raw, name, gross_net, runtime, model, record_currency, ccy
        )

    return _stream(_events(plan, run))
