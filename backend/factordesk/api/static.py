"""Serve the built dashboard (``frontend/dist``) from the same origin as the API (spec DB8.1).

``/assets/*`` comes from ``dist/assets`` with a one-year immutable cache (file names carry a
content hash). Any other GET outside ``/api`` answers ``index.html`` so a reloaded address such
as ``/?t=SPY`` works; that response is never cached and carries the page security headers.
``/api/*`` never falls back: an unknown API path raises a 404 that the error handlers turn into
an ``ApiError`` body. There is no CORS middleware; development goes through the Vite proxy.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from starlette.responses import Response

from factordesk.api.errors import API_PREFIX

ASSET_CACHE_CONTROL = "public, max-age=31536000, immutable"
PAGE_CACHE_CONTROL = "no-cache"

CONTENT_SECURITY_POLICY = (
    "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data:; font-src 'self'; connect-src 'self'; frame-ancestors 'none'"
)
"""Same-origin only. ``'unsafe-inline'`` is for styles alone (ECharts sets inline styles)."""

_BASE_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
}
_PAGE_HEADERS = {
    **_BASE_HEADERS,
    "Content-Security-Policy": CONTENT_SECURITY_POLICY,
    "Cache-Control": PAGE_CACHE_CONTROL,
}
_ASSET_HEADERS = {**_BASE_HEADERS, "Cache-Control": ASSET_CACHE_CONTROL}

_NOT_FOUND = "Not Found"


def _is_api_path(path: str) -> bool:
    return path == API_PREFIX or path.startswith(API_PREFIX + "/")


def _asset_file(assets_root: Path, relative: str) -> Path | None:
    """The file under ``assets_root`` named by ``relative``, or None when it is not one.

    The resolved path must stay inside ``assets_root``, so ``..``, absolute paths and drive
    letters in the request cannot reach another file.
    """
    try:
        candidate = (assets_root / relative).resolve()
        if candidate.is_relative_to(assets_root) and candidate.is_file():
            return candidate
    except (OSError, ValueError):  # a name the file system rejects, such as a NUL byte
        return None
    return None


def install_static(app: FastAPI, static_dir: Path) -> None:
    """Add the asset and page routes for ``static_dir``. Call after the API routers.

    The directory is read per request, so a rebuild shows up without a restart. The routes are
    left out of the OpenAPI document.
    """
    root = static_dir.resolve()
    assets_root = (root / "assets").resolve()
    index = root / "index.html"

    @app.api_route("/assets/{asset_path:path}", methods=["GET", "HEAD"], include_in_schema=False)
    def asset(asset_path: str) -> Response:  # pyright: ignore[reportUnusedFunction]
        found = _asset_file(assets_root, asset_path)
        if found is None:
            raise HTTPException(status_code=404, detail=_NOT_FOUND)
        return FileResponse(found, headers=_ASSET_HEADERS)

    @app.api_route("/{page_path:path}", methods=["GET", "HEAD"], include_in_schema=False)
    def page(page_path: str) -> Response:  # pyright: ignore[reportUnusedFunction]
        if _is_api_path("/" + page_path):
            raise HTTPException(status_code=404, detail=_NOT_FOUND)
        if not index.is_file():
            raise HTTPException(status_code=404, detail=_NOT_FOUND)
        return FileResponse(index, media_type="text/html", headers=_PAGE_HEADERS)
