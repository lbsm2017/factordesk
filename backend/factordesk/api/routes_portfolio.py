"""Portfolio routes: the Asset Class Library, and the report of a portfolio tree."""

from __future__ import annotations

from fastapi import APIRouter

from factordesk.api.portfolio_models import AssetClassLibrary, PortfolioTree, load_library
from factordesk.api.routes_report import End, Model, Preset, Service, Start
from factordesk.report.schema import ApiError, FactorReport

router = APIRouter(prefix="/api/portfolio")
report_router = APIRouter(prefix="/api/report")

_ERRORS: dict[int | str, dict[str, object]] = {
    400: {"model": ApiError, "description": "The range or the dates are not valid."},
    422: {
        "model": ApiError,
        "description": "The portfolio is not valid (a total over 100%, more than 50 instruments, "
        "a weight on a line with no proxy), an instrument has no prices, is not quoted in US "
        "dollars or shares no trading period with the others, or the history is too short.",
    },
    500: {"model": ApiError, "description": "The report could not be computed."},
    502: {"model": ApiError, "description": "The downloaded factor file failed validation."},
    503: {"model": ApiError, "description": "A data source could not be reached or refused."},
}


@router.get("/library")
async def get_library() -> AssetClassLibrary:
    """The 44 lines of the Asset Class Library, in the owner's order, with their proxies."""
    return load_library()


@report_router.post("/portfolio", responses=_ERRORS)
async def portfolio_report(
    tree: PortfolioTree,
    service: Service,
    preset: Preset = None,
    start: Start = None,
    end: End = None,
    model: Model = "ff6",
) -> FactorReport:
    """The factor report of a backtested portfolio tree (kept in memory, never stored).

    The tree is flattened to its instruments with a weight above 0. Prices come from Yahoo
    (adjusted close), the weights drift and reset to target at each month-end, and the net daily
    returns go through the same factor analysis as a ticker. The unallocated weight is held in
    USD cash, which earns the risk-free rate. Only instruments with a weight above 0 limit the
    window. The model defaults to ff6; a range or dates cut the analysis sample.
    """
    return await service.portfolio_report(tree, preset, start, end, model)
