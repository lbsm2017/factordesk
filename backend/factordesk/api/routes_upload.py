"""Track-record upload: ``POST /api/report/upload`` (next-stage spec E0).

The file lives in memory for the length of the request: it is not written to the data folder or
to a temporary file by this code, and the report is not stored in any ``ReportService`` cache.
The size cap is enforced by ``UploadSizeLimit`` before the body is read. Every refusal of the
file is HTTP 422 with an ``ApiError``, except a request with no file: that is 400.
"""

from __future__ import annotations

import contextlib
import logging
import time
from datetime import UTC, datetime
from typing import Annotated

import pandas as pd
from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from factordesk import progress
from factordesk.analytics.currency import convert_series
from factordesk.analytics.sample import DegenerateInputError, InsufficientHistoryError
from factordesk.analytics.subject import subject_from_monthly_returns
from factordesk.api.currency_ctx import CurrencyContext
from factordesk.api.errors import UPLOAD_PATHS, UPLOAD_REPORT_PATH, ApiException, to_api_exception
from factordesk.api.runtime import Runtime, get_runtime
from factordesk.data.factors import FactorError
from factordesk.data.french import load_ff5_monthly, load_ff6
from factordesk.data.upload import (
    MAX_UPLOAD_BYTES,
    UploadError,
    clean_name,
    parse_gross_net,
    parse_monthly_csv,
)
from factordesk.report.schema import ApiError, FactorModel, FactorReport, ReferenceCurrency

logger = logging.getLogger(__name__)

UPLOAD_PATH = UPLOAD_REPORT_PATH
router = APIRouter(prefix="/api/report")

_ERRORS: dict[int | str, dict[str, object]] = {
    400: {"model": ApiError, "description": "The request has no file."},
    413: {"model": ApiError, "description": "The file is larger than 1 MB."},
    422: {
        "model": ApiError,
        "description": "The file or a form field cannot be used, or the record is too short.",
    },
    500: {"model": ApiError, "description": "The report could not be computed."},
    502: {"model": ApiError, "description": "The downloaded factor file failed validation."},
    503: {"model": ApiError, "description": "A data source could not be reached or refused."},
}


def _too_large() -> ApiException:
    return ApiException(
        "upload_too_large",
        "The file is larger than 1 MB.",
        "A monthly track record is a few kilobytes. Send only the date and return columns.",
    )


class _BodyTooLarge(Exception):
    """Internal: the body being read passed the cap."""


class UploadSizeLimit:
    """Refuses an upload larger than ``MAX_UPLOAD_BYTES`` with HTTP 413.

    The ``Content-Length`` header is checked before the body is read; a request that has none
    (chunked) is cut off as soon as the bytes received pass the cap.
    """

    def __init__(self, app: ASGIApp, limit: int = MAX_UPLOAD_BYTES) -> None:
        self.app = app
        self.limit = limit

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        is_upload = scope["type"] == "http" and scope["method"] == "POST"
        if not is_upload or scope["path"] not in UPLOAD_PATHS:
            await self.app(scope, receive, send)
            return
        declared = dict(scope["headers"]).get(b"content-length")
        if declared is not None and declared.strip().isdigit() and int(declared) > self.limit:
            await self._refuse(scope, receive, send)
            return
        seen = 0
        answered = False

        async def counted() -> Message:
            nonlocal seen, answered
            message = await receive()
            if message["type"] == "http.request":
                seen += len(message.get("body", b""))
                if seen > self.limit and not answered:
                    # Answer now: FastAPI turns any error raised while it reads the body into
                    # a 400, so the refusal cannot wait for the exception to come back out.
                    answered = True
                    await self._refuse(scope, receive, send)
                    raise _BodyTooLarge
            return message

        async def tracked(message: Message) -> None:
            if not answered:
                await send(message)

        with contextlib.suppress(_BodyTooLarge):
            await self.app(scope, counted, tracked)

    @staticmethod
    async def _refuse(scope: Scope, receive: Receive, send: Send) -> None:
        error = _too_large()
        content = error.body().model_dump(mode="json")
        await JSONResponse(status_code=error.status, content=content)(scope, receive, send)


def _downloaded_at(frame: pd.DataFrame) -> datetime | None:
    """The factor file's download time: ``attrs["downloaded_at"]`` is an ISO string."""
    raw: object = frame.attrs.get("downloaded_at")
    if not isinstance(raw, str):
        return None
    try:
        stamp = datetime.fromisoformat(raw)
    except ValueError:
        return None
    return stamp.replace(tzinfo=UTC) if stamp.utcoffset() is None else stamp.astimezone(UTC)


def monthly_frame(model: FactorModel, runtime: Runtime, now: datetime) -> pd.DataFrame:
    """The monthly factor frame of an upload: FF6 (``load_ff6``) for both models.

    FF5 falls back to the FF5 file without the alpha strip when momentum cannot be loaded; FF6
    raises the loader's error.
    """
    data_dir = runtime.deps.data_dir
    try:
        return load_ff6("monthly", data_dir=data_dir, now=now)
    except (FactorError, OSError):
        if model == "ff6":
            raise
        logger.warning("Monthly momentum factor unavailable; FF5 report without the alpha strip")
        return load_ff5_monthly(data_dir=data_dir, now=now)


def build_upload_report(
    raw: bytes,
    name: str | None,
    gross_net: str | None,
    runtime: Runtime,
    model: FactorModel = "ff5",
    record_currency: ReferenceCurrency = "USD",
    ccy: ReferenceCurrency = "USD",
) -> FactorReport:
    """Parse, validate and analyse an uploaded monthly record (blocking; run in a worker).

    The record is in ``record_currency`` and the report in ``ccy`` (month-end exchange rates).

    Logs the row count, the frequency, the seconds and, on a refusal, its reason category. It
    never logs the file's contents, its name or the display name.
    """
    started = time.perf_counter()
    rows = 0
    try:
        report, rows = _build_upload_report(
            raw, name, gross_net, runtime, model, record_currency, ccy
        )
    except Exception as exc:
        category = to_api_exception(exc).code
        logger.info("Upload refused: reason %s (%.1f s)", category, time.perf_counter() - started)
        raise
    logger.info(
        "Upload report built: %d rows, monthly, model %s, %.1f s",
        rows,
        model,
        time.perf_counter() - started,
    )
    return report


def _to_reference(returns: pd.Series, record: str, ctx: CurrencyContext) -> pd.Series:
    """The record's monthly returns in the reference currency, with month-end exchange rates.

    Months with no exchange rate (before 1999, or after the last one) are cut at the ends and
    noted; the months stay consecutive. Nothing is filled.
    """
    if record == ctx.ref:
        return returns
    stamps = pd.DatetimeIndex(returns.index)  # calendar month-ends, set by the subject
    calendar = pd.DatetimeIndex([stamps[0] - pd.offsets.MonthEnd(1), *stamps], name="date")
    done = convert_series(returns, record, ctx.ref, lambda: ctx.returns(record, calendar))
    ctx.note(done.notice)
    ok = done.returns.notna().to_numpy()
    if not ok.any():
        return done.returns
    return done.returns.iloc[int(ok.argmax()) : len(ok) - int(ok[::-1].argmax())]


def _build_upload_report(
    raw: bytes,
    name: str | None,
    gross_net: str | None,
    runtime: Runtime,
    model: FactorModel,
    record_currency: ReferenceCurrency,
    ccy: ReferenceCurrency,
) -> tuple[FactorReport, int]:
    from factordesk.pipeline import assemble_subject_report
    from factordesk.section_hooks.context import ReferenceInput, SectionInputs

    label = clean_name(name)
    try:
        flag = parse_gross_net(gross_net)
        returns = parse_monthly_csv(raw)
        ctx = CurrencyContext(ccy, runtime.deps.currency)
        if "EUR" in (record_currency, ccy):
            progress.step("fx")
        meta = {} if flag is None else {"gross_net": flag}
        subject = subject_from_monthly_returns(returns, label=label, currency=ccy, meta=meta)
        if record_currency != ccy:  # the checks above ran on the record as sent
            subject = subject_from_monthly_returns(
                _to_reference(subject.returns, record_currency, ctx),
                label=label,
                currency=ccy,
                meta=meta,
            )
    except (UploadError, ValueError) as exc:
        raise ApiException(
            "invalid_upload",
            f"The file cannot be used: {str(exc).rstrip('.')}.",
            "Send a CSV with a date and a return column: one decimal return per calendar "
            "month, no gaps (for example 2021-01-31,0.012).",
        ) from exc
    now = runtime.deps.now().astimezone(UTC)
    progress.step("factors")
    frame = monthly_frame(model, runtime, now)
    load_macro = runtime.deps.load_macro
    load_energy = runtime.deps.load_energy
    reference = None
    if ccy == "EUR":
        usd_rf = frame["RF"]  # the dollar risk-free rate, before the frame is converted
        frame = ctx.factors(frame)
        reference = ReferenceInput(lambda dates: ctx.returns("USD", dates), usd_rf)
    inputs = (
        None
        if load_macro is None and load_energy is None
        else SectionInputs(
            macro=None if load_macro is None else load_macro(),
            energy=None if load_energy is None else load_energy(),
            reference=reference,
        )
    )
    try:
        report = assemble_subject_report(
            subject,
            frame,
            model,
            now=now,
            factors_downloaded_at=_downloaded_at(frame),
            section_inputs=inputs,
            reference_currency=ccy,
            currency=ctx.info() if ccy == "EUR" else None,
        )
        return report, len(returns)
    except InsufficientHistoryError as exc:
        raise to_api_exception(exc, label) from exc
    except DegenerateInputError as exc:
        raise ApiException(
            "degenerate_input",
            f"Cannot analyse {label}: {exc.reason.rstrip('.')}.",
            "Check that the returns are not all equal.",
        ) from exc


@router.post("/upload", responses=_ERRORS)
async def upload_report(
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
) -> FactorReport:
    """The factor report of an uploaded monthly track record (kept in memory, never stored)."""
    runtime = get_runtime(request)
    raw = await file.read(MAX_UPLOAD_BYTES + 1)
    await file.close()
    if len(raw) > MAX_UPLOAD_BYTES:
        raise _too_large()
    return await runtime.run(
        build_upload_report, raw, name, gross_net, runtime, model, record_currency, ccy
    )
