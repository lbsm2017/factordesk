"""Report, range options and HTML download for one ticker (dashboard spec DB2.1).

The ticker is checked with ``validate_ticker`` before any provider, cache or file is touched;
the upper-cased result is used everywhere after that. ``range`` and dates are exclusive;
neither means Full history.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import HTMLResponse

from factordesk.api.errors import check_ticker
from factordesk.api.service import ReportService, get_report_service
from factordesk.data.french import FactorSet
from factordesk.report.schema import (
    ApiError,
    FactorModel,
    FactorReport,
    RangeOptions,
    RangePreset,
    ReferenceCurrency,
)

router = APIRouter(prefix="/api/report")

_ERRORS: dict[int | str, dict[str, object]] = {
    400: {"model": ApiError, "description": "The range or the dates are not valid."},
    404: {"model": ApiError, "description": "No prices were returned for the ticker."},
    422: {
        "model": ApiError,
        "description": "Invalid ticker, too little history, or inputs that cannot be analysed.",
    },
    500: {"model": ApiError, "description": "The report could not be computed."},
    502: {"model": ApiError, "description": "The downloaded factor file failed validation."},
    503: {"model": ApiError, "description": "A data source could not be reached or refused."},
}

Service = Annotated[ReportService, Depends(get_report_service)]
Preset = Annotated[
    RangePreset | None,
    Query(alias="range", description="Range preset; not together with start or end."),
]
Start = Annotated[date | None, Query(description="First requested date, YYYY-MM-DD.")]
End = Annotated[date | None, Query(description="Last requested date, YYYY-MM-DD.")]
Model = Annotated[
    FactorModel,
    Query(description="Factor model: ff5 (default) or ff6 (FF5 plus momentum)."),
]


Ccy = Annotated[
    ReferenceCurrency,
    Query(description="Reference currency of every figure: USD (default) or EUR."),
]
Factors = Annotated[
    FactorSet,
    Query(
        description="Regional Fama-French factor set: us (default) or europe (Developed Europe, "
        "published in US dollars)."
    ),
]


@router.get("/{ticker}/ranges", responses=_ERRORS)
async def get_ranges(
    ticker: str, service: Service, ccy: Ccy = "USD", factor_set: Factors = "us"
) -> RangeOptions:
    """Availability of every range preset for this ticker, with the reason when one is short.

    ``ccy=EUR`` counts the days of the EUR report: a rate series that starts after the prices
    leaves fewer days. 503 when the exchange rates cannot be reached (USD does not need them).
    The presets follow the dates of the chosen factor set (the Europe files start in 1990).
    """
    return await service.range_options(check_ticker(ticker), ccy, factor_set)


@router.get("/{ticker}", responses=_ERRORS)
async def get_report(
    ticker: str,
    service: Service,
    preset: Preset = None,
    start: Start = None,
    end: End = None,
    model: Model = "ff5",
    ccy: Ccy = "USD",
    factor_set: Factors = "us",
) -> FactorReport:
    """The factor report for a range preset or custom dates (neither: Full history).

    ``ccy=EUR`` shows it in euros: returns converted with the exchange rate, cash at the euro
    rate, factors converted. The report then carries a ``currency`` block. 503 when the
    exchange rates or the euro rate cannot be reached (the USD view does not need them).
    ``factor_set=europe`` uses the Developed Europe factors in place of the US ones; the report
    then carries a ``factor_set`` field.
    """
    return await service.report(check_ticker(ticker), preset, start, end, model, ccy, factor_set)


@router.get(
    "/{ticker}/html",
    response_class=HTMLResponse,
    responses={**_ERRORS, 200: {"content": {"text/html": {}}, "description": "The report."}},
)
async def get_report_html(
    ticker: str,
    service: Service,
    preset: Preset = None,
    start: Start = None,
    end: End = None,
    model: Model = "ff5",
    factor_set: Factors = "us",
) -> HTMLResponse:
    """The offline HTML report for the same ticker and range, as a file download."""
    symbol = check_ticker(ticker)
    page = await service.report_html(symbol, preset, start, end, model, factor_set)
    return HTMLResponse(
        content=page,
        headers={"Content-Disposition": f'attachment; filename="{symbol}_report.html"'},
    )
