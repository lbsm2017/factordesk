"""One error model for the local API (dashboard spec DB2.3).

Every error body is an ``ApiError``: ``message`` says what went wrong and ``action`` says what
to do, both plain sentences with no stack trace and no exception class name. Domain exceptions
are translated here, in one place, so a route only has to let them propagate.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from typing import Any, cast

import httpx
from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exception_handlers import http_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from starlette.exceptions import HTTPException as StarletteHTTPException

from factordesk.analytics.sample import DegenerateInputError, InsufficientHistoryError
from factordesk.data.factors import FactorDataError, FactorDownloadError
from factordesk.data.prices import PriceDataError, validate_ticker
from factordesk.report.schema import ApiError, ErrorCode

logger = logging.getLogger(__name__)

API_PREFIX = "/api"

_STATUS: dict[ErrorCode, int] = {
    "invalid_ticker": 422,
    "unknown_ticker": 404,
    "bad_range": 400,
    "insufficient_history": 422,
    "degenerate_input": 422,
    "factor_data_invalid": 502,
    "network": 503,
    "upstream_refused": 503,
    "not_found": 404,
    "internal": 500,
    "bad_request": 400,
}

_MAX_ECHO = 120
"""Longest request text echoed back in a message."""


class ApiException(Exception):
    """An error that is already in API form; handlers answer it with an ``ApiError`` body."""

    def __init__(self, code: ErrorCode, message: str, action: str, status: int | None = None):
        super().__init__(message)
        self.code: ErrorCode = code
        self.message = message
        self.action = action
        self.status = _STATUS[code] if status is None else status

    def body(self) -> ApiError:
        return ApiError(code=self.code, message=self.message, action=self.action)


def one_line(text: str, limit: int = _MAX_ECHO) -> str:
    """First non-empty line of ``text``, trimmed, without a trailing full stop, capped."""
    for line in text.splitlines():
        stripped = line.strip().rstrip(".")
        if stripped:
            return stripped if len(stripped) <= limit else stripped[: limit - 1] + "…"
    return "no detail was given"


def check_ticker(raw: str) -> str:
    """Return the upper-cased ticker, or raise ``invalid_ticker`` before anything else runs."""
    try:
        return validate_ticker(raw)
    except PriceDataError as exc:
        raise ApiException(
            "invalid_ticker",
            f"{one_line(raw)} is not a valid ticker.",
            "Use 1 to 12 letters, digits or . ^ = - (for example SPY or BRK-B).",
        ) from exc


def _ticker_of(request: Request) -> str | None:
    raw: object = request.path_params.get("ticker")
    if not isinstance(raw, str):
        return None
    try:
        return validate_ticker(raw)
    except PriceDataError:
        return None


def to_api_exception(exc: BaseException, ticker: str | None = None) -> ApiException:
    """Translate a domain exception into its ``ApiException`` (DB2.3 table).

    ``ticker`` names the symbol in messages that mention one. Exceptions with no row in the
    table become ``internal``.
    """
    if isinstance(exc, ApiException):
        return exc
    who = ticker or "this ticker"
    if isinstance(exc, InsufficientHistoryError):
        return ApiException(
            "insufficient_history",
            f"{who} has {exc.n} trading days in this range that line up with the factor "
            f"data; at least {exc.required} (about two years) are needed.",
            "Choose a longer range or Full history.",
        )
    if isinstance(exc, DegenerateInputError):
        return ApiException(
            "degenerate_input",
            f"Cannot analyse {who}: {one_line(exc.reason)}.",
            "Choose another ticker or range.",
        )
    if isinstance(exc, PriceDataError):
        return ApiException(
            "unknown_ticker",
            f"No prices were returned for {who}.",
            "Check the ticker symbol.",
        )
    if isinstance(exc, FactorDataError):
        return ApiException(
            "factor_data_invalid",
            "The downloaded factor file failed validation; the previous copy was kept.",
            "Try again later.",
        )
    if isinstance(exc, FactorDownloadError | httpx.HTTPError | OSError):
        return ApiException(
            "network",
            "factordesk could not reach the data source.",
            "Check your network connection, then try again.",
        )
    if _is_yahoo_refusal(exc):
        return ApiException(
            "upstream_refused",
            "Yahoo Finance refused the request.",
            "Wait a minute, then try again.",
        )
    return ApiException(
        "internal",
        f"The report for {who} could not be computed: {one_line(str(exc))}.",
        "Try another range. If it happens again, report it with this page's address.",
    )


def _is_yahoo_refusal(exc: BaseException) -> bool:
    from yfinance.exceptions import YFException  # pyright: ignore[reportMissingTypeStubs]

    return isinstance(exc, YFException)


def _respond(error: ApiException) -> JSONResponse:
    return JSONResponse(status_code=error.status, content=error.body().model_dump(mode="json"))


async def _api_exception_handler(request: Request, exc: Exception) -> Response:
    assert isinstance(exc, ApiException)
    return _respond(exc)


async def _domain_exception_handler(request: Request, exc: Exception) -> Response:
    translated = to_api_exception(exc, _ticker_of(request))
    if translated.code == "internal":
        logger.error("Unhandled %s on %s", type(exc).__name__, request.url.path, exc_info=exc)
    else:
        logger.info("%s on %s: %s", translated.code, request.url.path, translated.message)
    return _respond(translated)


def _locations(errors: Sequence[object]) -> list[tuple[str, ...]]:
    """The parameter path of every validation error, without the leading source word."""
    out: list[tuple[str, ...]] = []
    for item in errors:
        if not isinstance(item, dict):
            continue
        loc = cast(dict[str, object], item).get("loc", ())
        if isinstance(loc, list | tuple):
            parts = cast(Sequence[object], loc)
            out.append(tuple(str(part) for part in parts[1:]))
    return out


def validation_error(errors: Sequence[object], ticker: str | None) -> ApiException:
    """Turn FastAPI's validation errors into one ``ApiException`` (never the default body)."""
    names = [loc[0] for loc in _locations(errors) if loc]
    if "ticker" in names:
        shown = ticker or "that ticker"
        return ApiException(
            "invalid_ticker",
            f"{shown} is not a valid ticker.",
            "Use 1 to 12 letters, digits or . ^ = - (for example SPY or BRK-B).",
        )
    for name in ("start", "end"):
        if name in names:
            return ApiException(
                "bad_range",
                f"The {name} date is not a valid date.",
                "Write dates as YYYY-MM-DD, for example 2026-01-31.",
            )
    if "range" in names:
        return ApiException(
            "bad_range",
            "The range is not one of 3Y, 5Y or FULL.",
            "Choose one of the listed ranges, or pass start and end dates.",
        )
    shown_names = ", ".join(sorted(set(names))) or "the request"
    return ApiException(
        "bad_request",
        f"The value for {shown_names} is not valid.",
        "Check the query parameters against the API description at /docs.",
    )


async def _validation_handler(request: Request, exc: Exception) -> Response:
    assert isinstance(exc, RequestValidationError)
    errors = jsonable_encoder(exc.errors(), exclude={"input", "ctx", "url"})
    return _respond(validation_error(errors, _ticker_of(request)))


async def _http_exception_handler(request: Request, exc: Exception) -> Response:
    assert isinstance(exc, StarletteHTTPException)
    path = request.url.path
    if path != API_PREFIX and not path.startswith(API_PREFIX + "/"):
        return await http_exception_handler(request, exc)
    shown = one_line(path)
    if exc.status_code == 404:
        return _respond(
            ApiException(
                "not_found",
                f"There is no API endpoint at {shown}.",
                "Check the address.",
            )
        )
    if exc.status_code == 405:
        return _respond(
            ApiException(
                "not_found",
                f"{shown} does not accept {request.method} requests.",
                "Check the address and the request method.",
                status=405,
            )
        )
    return _respond(
        ApiException(
            "bad_request",
            "The request could not be handled.",
            "Check the request against the API description at /docs.",
            status=exc.status_code,
        )
    )


_DOMAIN_EXCEPTIONS: tuple[type[Exception], ...] = (
    InsufficientHistoryError,
    DegenerateInputError,
    PriceDataError,
    FactorDataError,
    FactorDownloadError,
    httpx.HTTPError,
    OSError,
    ValueError,
    ArithmeticError,
)


def install_error_handlers(app: FastAPI) -> None:
    """Register the handlers that make every error body an ``ApiError``."""
    from yfinance.exceptions import YFException  # pyright: ignore[reportMissingTypeStubs]

    handler: Callable[[Request, Exception], Any] = _domain_exception_handler
    app.add_exception_handler(ApiException, _api_exception_handler)
    app.add_exception_handler(RequestValidationError, _validation_handler)
    app.add_exception_handler(StarletteHTTPException, _http_exception_handler)
    for cls in (*_DOMAIN_EXCEPTIONS, YFException):
        app.add_exception_handler(cls, handler)
