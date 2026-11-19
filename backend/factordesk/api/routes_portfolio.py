"""Portfolio routes: the Asset Class Library the composer is built from."""

from __future__ import annotations

from fastapi import APIRouter

from factordesk.api.portfolio_models import AssetClassLibrary, load_library

router = APIRouter(prefix="/api/portfolio")


@router.get("/library")
async def get_library() -> AssetClassLibrary:
    """The 44 lines of the Asset Class Library, in the owner's order, with their proxies."""
    return load_library()
