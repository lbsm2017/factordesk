"""Static serving of the built dashboard (dashboard spec DB8.1): assets, SPA fallback, headers.

Offline: a throwaway ``dist`` folder in ``tmp_path`` and ``TestClient``; no browser, no network.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol, cast

import httpx
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from factordesk.api.deps import AppDeps
from factordesk.api.main import create_app
from factordesk.api.static import CONTENT_SECURITY_POLICY
from factordesk.report.schema import ApiError
from factordesk.tests.fixtures.dgp import StaticProvider, dgp_a, rng_for

NOW = datetime(2026, 11, 18, 15, 0, tzinfo=UTC)
INDEX = "<!doctype html><title>factordesk</title><div id=root></div>"
ASSET = "console.log('hello');"
SECRET = "do not serve"


class ApiClient(Protocol):
    """The part of the test client these tests use (its own typing depends on the httpx flavour)."""

    def get(self, url: str) -> httpx.Response: ...

    def head(self, url: str) -> httpx.Response: ...

    def post(self, url: str) -> httpx.Response: ...


def _client(deps: AppDeps) -> TestClient:
    return TestClient(create_app(deps))  # pyright: ignore[reportUnknownVariableType]


def _deps(tmp_path: Path, static_dir: Path | None) -> AppDeps:
    return AppDeps(
        price_provider=StaticProvider(dgp_a(rng_for(300), n=600).history),
        load_factors=lambda refresh, now: pd.DataFrame({"Mkt-RF": [0.0]}),
        factor_status=lambda now: None,
        now=lambda: NOW,
        data_dir=tmp_path,
        static_dir=static_dir,
    )


@pytest.fixture
def dist(tmp_path: Path) -> Path:
    root = tmp_path / "dist"
    (root / "assets").mkdir(parents=True)
    (root / "index.html").write_text(INDEX, encoding="utf-8")
    (root / "assets" / "app-abc123.js").write_text(ASSET, encoding="utf-8")
    (tmp_path / "secret.txt").write_text(SECRET, encoding="utf-8")
    return root


@pytest.fixture
def client(tmp_path: Path, dist: Path) -> Iterator[ApiClient]:
    with _client(_deps(tmp_path, dist)) as test_client:  # pyright: ignore[reportUnknownVariableType]
        yield cast(ApiClient, test_client)


def _assert_page_headers(headers: dict[str, str]) -> None:
    assert headers["content-security-policy"] == CONTENT_SECURITY_POLICY
    assert headers["x-content-type-options"] == "nosniff"
    assert headers["referrer-policy"] == "no-referrer"
    assert headers["cache-control"] == "no-cache"


def test_csp_matches_the_spec() -> None:
    assert CONTENT_SECURITY_POLICY == (
        "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; font-src 'self'; connect-src 'self'; frame-ancestors 'none'"
    )


def test_root_serves_index_with_security_headers(client: ApiClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert response.text == INDEX
    assert response.headers["content-type"].startswith("text/html")
    _assert_page_headers(dict(response.headers))


@pytest.mark.parametrize("path", ["/?t=SPY&range=3Y", "/factors", "/a/b/c", "/index.html", "/x.js"])
def test_non_api_paths_fall_back_to_index(client: ApiClient, path: str) -> None:
    response = client.get(path)
    assert response.status_code == 200
    assert response.text == INDEX
    _assert_page_headers(dict(response.headers))


def test_asset_is_served_immutable(client: ApiClient) -> None:
    response = client.get("/assets/app-abc123.js")
    assert response.status_code == 200
    assert response.text == ASSET
    assert response.headers["cache-control"] == "public, max-age=31536000, immutable"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert "javascript" in response.headers["content-type"]


def test_head_on_page_and_asset(client: ApiClient) -> None:
    assert client.head("/").status_code == 200
    assert client.head("/assets/app-abc123.js").status_code == 200


def test_missing_asset_is_404_not_index(client: ApiClient) -> None:
    response = client.get("/assets/missing.js")
    assert response.status_code == 404
    assert INDEX not in response.text


@pytest.mark.parametrize(
    "path",
    [
        "/assets/../../secret.txt",
        "/assets/..%2f..%2fsecret.txt",
        "/assets/%2e%2e/%2e%2e/secret.txt",
        "/assets/..\\..\\secret.txt",
        "/assets/",
        "/assets/%00",
    ],
)
def test_assets_cannot_escape_the_assets_folder(client: ApiClient, path: str) -> None:
    response = client.get(path)
    assert SECRET not in response.text
    assert response.status_code in (200, 404)
    if response.status_code == 200:  # the client may normalise the path and land on the page
        assert response.text == INDEX


def test_unknown_api_path_is_json_404(client: ApiClient) -> None:
    for path in ("/api/nope", "/api/nope/deeper", "/api", "/api/"):
        response = client.get(path)
        assert response.status_code == 404, path
        assert response.headers["content-type"].startswith("application/json")
        assert ApiError.model_validate(response.json()).code == "not_found"
        assert "content-security-policy" not in response.headers


def test_api_routes_win_over_the_fallback(client: ApiClient) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_api_method_mismatch_stays_json(client: ApiClient) -> None:
    response = client.post("/api/health")
    assert response.status_code == 405
    assert ApiError.model_validate(response.json()).code == "not_found"


def test_openapi_does_not_list_static_routes(tmp_path: Path, dist: Path) -> None:
    with_static = create_app(_deps(tmp_path, dist)).openapi()
    without = create_app(_deps(tmp_path, None)).openapi()
    assert with_static == without


def test_without_static_dir_nothing_is_mounted(tmp_path: Path) -> None:
    with _client(_deps(tmp_path, None)) as test_client:  # pyright: ignore[reportUnknownVariableType]
        api = cast(ApiClient, test_client)
        assert api.get("/").status_code == 404
        assert api.get("/assets/app-abc123.js").status_code == 404


def test_index_removed_after_start_is_404(tmp_path: Path, dist: Path) -> None:
    with _client(_deps(tmp_path, dist)) as test_client:  # pyright: ignore[reportUnknownVariableType]
        (dist / "index.html").unlink()
        assert cast(ApiClient, test_client).get("/").status_code == 404
