"""The factor model over the API (E1): ``?model=`` on the ticker report, ``model`` on the upload.

Offline, on the fakes of ``test_api_report`` and ``test_api_upload``: the FF6 loader returns the
fake FF5 frame with a synthetic ``Mom`` column.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from factordesk.api import routes_upload
from factordesk.api.main import create_app
from factordesk.data.factors import FactorDownloadError
from factordesk.report.schema import FactorReport
from factordesk.tests.test_api_report import (
    ApiClient,
    World,
    _no_network,  # noqa: F401  # pyright: ignore[reportUnusedImport, reportPrivateUsage]
    assert_api_error,
    make_world,
    serve,
)
from factordesk.tests.test_api_upload import ApiClient as UploadClient
from factordesk.tests.test_api_upload import csv_of, post
from factordesk.tests.test_ff6_report import with_mom
from factordesk.tests.test_subject import monthly_case

FF5_ONLY = ("lead_lag", "shrunk_betas", "fragility", "residual", "kalman_betas")
SIX = ["Mkt-RF", "SMB", "HML", "RMW", "CMA", "Mom"]


class FakeFF6:
    """The FF6 loader: the fake FF5 frame plus ``Mom``; counts calls and can fail."""

    def __init__(self, world: World) -> None:
        self.world = world
        self.calls = 0
        self.error: Exception | None = None

    def load(self, now: datetime) -> pd.DataFrame:
        self.calls += 1
        if self.error is not None:
            raise self.error
        return with_mom(self.world.factors.frame, 91)


@pytest.fixture
def ff6_world(tmp_path: Path) -> tuple[World, FakeFF6]:
    world = make_world(tmp_path)
    fake = FakeFF6(world)
    deps = dataclasses.replace(world.service.deps, load_ff6=fake.load)
    app = create_app(deps)
    return dataclasses.replace(world, app=app, service=app.state.report_service), fake


@pytest.fixture
def client(ff6_world: tuple[World, FakeFF6]) -> Iterator[ApiClient]:
    with serve(ff6_world[0].app) as test_client:
        yield test_client


def _report(client: ApiClient, query: str = "") -> FactorReport:
    response = client.get(f"/api/report/SPY{query}")
    assert response.status_code == 200, response.text
    return FactorReport.model_validate_json(response.text)


# ----------------------------------------------------------------------------- ticker
def test_model_ff6_returns_six_betas_with_momentum(client: ApiClient) -> None:
    report = _report(client, "?model=ff6")
    assert report.model == "ff6"
    assert [f.name for f in report.regression.factors] == SIX
    assert next(f for f in report.regression.factors if f.name == "Mom").beta is not None


def test_ff5_only_sections_are_absent_under_ff6(client: ApiClient) -> None:
    body = client.get("/api/report/SPY?model=ff6").json()
    for field in FF5_ONLY:
        assert body[field] is None, field
    assert body["performance"] is not None


def test_default_is_ff5_with_the_alpha_strip(client: ApiClient) -> None:
    response = client.get("/api/report/SPY")
    body = response.json()
    assert "model" not in body
    assert [f["name"] for f in body["regression"]["factors"]] == SIX[:5]
    strip = body["alpha_strip"]
    assert strip["status"] == "ok" and strip["model"] == "ff5"
    assert [r["label"] for r in strip["rows"]] == ["CAPM", "FF3", "FF5", "FF6"]
    assert _report(client, "?model=ff5") == FactorReport.model_validate_json(response.text)


def test_ff6_report_carries_the_strip(client: ApiClient) -> None:
    strip = _report(client, "?model=ff6").alpha_strip
    assert strip is not None and strip.model == "ff6" and len(strip.rows) == 4


def test_unknown_model_is_a_bad_request(client: ApiClient) -> None:
    assert_api_error(client.get("/api/report/SPY?model=ff4"), 400, "bad_request")


def test_models_are_cached_apart_and_the_ff6_frame_once(
    ff6_world: tuple[World, FakeFF6], client: ApiClient
) -> None:
    world, fake = ff6_world
    _report(client)
    _report(client, "?model=ff6")
    _report(client, "?model=ff6")
    models = sorted(key[5] for key in world.service.reports.keys())  # noqa: SIM118
    assert models == ["ff5", "ff6"]
    assert fake.calls == 1


def test_ff5_falls_back_without_momentum_and_ff6_fails(
    ff6_world: tuple[World, FakeFF6], client: ApiClient
) -> None:
    _, fake = ff6_world
    fake.error = FactorDownloadError("momentum file unreachable")
    report = _report(client)
    assert report.alpha_strip is None
    assert [f.name for f in report.regression.factors] == SIX[:5]
    assert_api_error(client.get("/api/report/SPY?model=ff6"), 503, "network")


def test_ff6_is_refused_when_the_loader_is_not_wired(tmp_path: Path) -> None:
    world = make_world(tmp_path)
    with serve(world.app) as plain:
        assert_api_error(plain.get("/api/report/SPY?model=ff6"), 400, "bad_request")
        assert plain.get("/api/report/SPY").json().get("alpha_strip") is None


def test_html_download_follows_the_model(client: ApiClient) -> None:
    page = client.get("/api/report/SPY/html?model=ff6").text
    assert 'id="alpha-strip"' in page and 'id="kalman"' not in page


# ----------------------------------------------------------------------------- upload
@pytest.fixture
def upload_client(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[tuple[UploadClient, list[str]]]:
    _, frame, _ = monthly_case(72, 11, extra_factor_months=6)
    ff6 = with_mom(frame, 92, sd=0.03)
    calls: list[str] = []

    def load_ff6(frequency: str, **_kw: object) -> pd.DataFrame:
        calls.append(frequency)
        return ff6

    monkeypatch.setattr(routes_upload, "load_ff6", load_ff6)

    def load_ff5(**_kw: object) -> pd.DataFrame:
        return frame

    monkeypatch.setattr(routes_upload, "load_ff5_monthly", load_ff5)
    with TestClient(make_world(tmp_path).app) as test_client:  # pyright: ignore[reportUnknownVariableType]
        yield test_client, calls  # pyright: ignore[reportReturnType]


def test_upload_carries_the_strip_and_takes_the_model_field(
    upload_client: tuple[UploadClient, list[str]],
) -> None:
    client, calls = upload_client
    returns = monthly_case(72, 11)[0]
    ff5 = FactorReport.model_validate_json(post(client, csv_of(returns)).text)
    assert ff5.alpha_strip is not None and ff5.alpha_strip.t_reference == "student_t"
    assert ff5.model is None
    response = client.post(
        "/api/report/upload",
        files={"file": ("record.csv", csv_of(returns), "text/csv")},
        data={"model": "ff6"},
    )
    assert response.status_code == 200, response.text
    ff6 = FactorReport.model_validate_json(response.text)
    assert ff6.model == "ff6" and [f.name for f in ff6.regression.factors] == SIX
    assert ff6.alpha_strip is not None and ff6.alpha_strip.model == "ff6"
    assert calls == ["monthly", "monthly"]
    bad = client.post(
        "/api/report/upload",
        files={"file": ("record.csv", csv_of(returns), "text/csv")},
        data={"model": "ff7"},
    )
    assert bad.status_code in (400, 422), bad.text
