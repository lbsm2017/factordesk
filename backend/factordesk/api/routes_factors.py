"""Health, factor data status and refresh, and ticker suggestions (dashboard spec DB2.1)."""

from __future__ import annotations

import re
from datetime import date
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from factordesk.api.runtime import Runtime, get_runtime
from factordesk.data.prices import PriceDataError, validate_ticker
from factordesk.report.schema import (
    SCHEMA_VERSION,
    ApiError,
    FactorDataStatus,
    Health,
    TickerSuggestion,
    TickerSuggestions,
)

router = APIRouter(prefix="/api")

_ERRORS: dict[int | str, dict[str, object]] = {
    503: {"model": ApiError, "description": "The data source could not be reached."},
    502: {"model": ApiError, "description": "The downloaded factor file failed validation."},
}

_PRICE_CACHE_NAME = re.compile(r"^(?P<ticker>.+)_(?P<day>\d{4}-\d{2}-\d{2})\.parquet$")


def _package_version() -> str:
    try:
        return version("factordesk")
    except PackageNotFoundError:  # running from a source tree that was never installed
        return "0+unknown"


@router.get("/health")
async def get_health() -> Health:
    """Liveness. Reads no disk and no network."""
    return Health(status="ok", version=_package_version(), schema_version=SCHEMA_VERSION)


@router.get("/factors/status")
async def get_factor_status(
    runtime: Annotated[Runtime, Depends(get_runtime)],
) -> FactorDataStatus:
    """Coverage and age of the cached factor file; ``available`` is false when none."""
    return await runtime.factor_status()


@router.post("/factors/refresh", responses=_ERRORS)
async def refresh_factors(
    runtime: Annotated[Runtime, Depends(get_runtime)],
) -> FactorDataStatus:
    """Force a factor download. Calls made while one runs join it; a failure keeps the cache."""
    return await runtime.refresh_factors()


def cached_tickers(price_dir: Path) -> dict[str, date]:
    """Tickers with a price cache file, each with its most recent fetch date.

    Files are named ``{TICKER}_{YYYY-MM-DD}.parquet``; anything else, and any name whose
    ticker part fails ``validate_ticker``, is ignored.
    """
    found: dict[str, date] = {}
    try:
        entries = list(price_dir.iterdir())
    except OSError:  # no cache directory yet: nothing was fetched
        return found
    for path in entries:
        match = _PRICE_CACHE_NAME.fullmatch(path.name)
        if match is None or not path.is_file():
            continue
        try:
            ticker = validate_ticker(match["ticker"])
            day = date.fromisoformat(match["day"])
        except (PriceDataError, ValueError):
            continue
        if ticker not in found or day > found[ticker]:
            found[ticker] = day
    return found


def suggest(price_dir: Path, q: str, limit: int) -> TickerSuggestions:
    prefix = q.upper()
    matches = [(t, d) for t, d in cached_tickers(price_dir).items() if t.startswith(prefix)]
    matches.sort(key=lambda item: (-item[1].toordinal(), item[0]))
    return TickerSuggestions(
        items=[TickerSuggestion(ticker=t, last_fetched=d) for t, d in matches[:limit]]
    )


@router.get("/tickers")
async def get_tickers(
    runtime: Annotated[Runtime, Depends(get_runtime)],
    q: Annotated[str, Query(max_length=12)] = "",
    limit: Annotated[int, Query(ge=1, le=20)] = 8,
) -> TickerSuggestions:
    """Tickers already fetched (prefix match, newest first). Makes no network call."""
    return await runtime.run(suggest, runtime.deps.data_dir / "prices", q, limit)
