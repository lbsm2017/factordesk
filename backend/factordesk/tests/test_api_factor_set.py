"""The factor-set choice over the API (S4-3): ``factor_set`` on the ticker report, the ranges, the
portfolio body and the upload form.

Offline. The Europe frame is the US test frame with the market factor doubled and ``Mom`` replaced,
so a Europe report shows half the US market beta and every other number follows from the frame it
is given. The US report must not change at all: no ``factor_set`` field, the same JSON as before.
"""

from __future__ import annotations

import dataclasses
import json
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import httpx
import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from factordesk.api import routes_upload
from factordesk.api.main import create_app
from factordesk.data.factors import FactorDownloadError
from factordesk.data.french import DATASETS
from factordesk.report.schema import FactorReport
from factordesk.tests import test_api_portfolio as portfolio_tests
from factordesk.tests import test_api_upload as upload_tests
from factordesk.tests.test_api_report import (
    ApiClient,
    World,
    _no_network,  # noqa: F401  # pyright: ignore[reportUnusedImport, reportPrivateUsage]
    assert_api_error,
    make_world,
    serve,
)
from factordesk.tests.test_currency_view import FAKE, with_sources
from factordesk.tests.test_ff6_report import with_mom
from factordesk.tests.test_subject import monthly_case

EU_DOWNLOADED = datetime(2026, 11, 2, 9, 0, tzinfo=UTC)
FACTORS = ["Mkt-RF", "SMB", "HML", "RMW", "CMA"]


def europe_of(us: pd.DataFrame, *, seed: int = 191, mom: bool = True) -> pd.DataFrame:
    """A stand-in for the Europe frame: the market factor doubled, a new ``Mom``, the vintage."""
    out = with_mom(us.drop(columns=["Mom"], errors="ignore"), seed) if mom else us.copy()
    out["Mkt-RF"] = out["Mkt-RF"] * 2.0
    out.attrs = {
        "factor_set": "europe",
        "ff5": {"downloaded_at": EU_DOWNLOADED.isoformat()},
        "mom": {"downloaded_at": EU_DOWNLOADED.isoformat()},
    }
    return out


class FakeEurope:
    def __init__(self, world: World) -> None:
        self.world = world
        self.calls = 0
        self.error: Exception | None = None
        self.frame = europe_of(world.factors.frame)

    def load(self, now: datetime) -> pd.DataFrame:
        self.calls += 1
        if self.error is not None:
            raise self.error
        return self.frame


@pytest.fixture
def eu_world(tmp_path: Path) -> tuple[World, FakeEurope]:
    world = make_world(tmp_path)
    fake = FakeEurope(world)
    us = with_mom(world.factors.frame, 91)

    def load_us(now: datetime) -> pd.DataFrame:
        return us

    deps = dataclasses.replace(world.service.deps, load_ff6=load_us, load_europe_ff6=fake.load)
    app = create_app(deps)
    return dataclasses.replace(world, app=app, service=app.state.report_service), fake


@pytest.fixture
def client(eu_world: tuple[World, FakeEurope]) -> Iterator[ApiClient]:
    with serve(eu_world[0].app) as test_client:
        yield test_client


def _report(client: ApiClient, query: str = "") -> FactorReport:
    response = client.get(f"/api/report/SPY{query}")
    assert response.status_code == 200, response.text
    return FactorReport.model_validate_json(response.text)


def _beta(report: FactorReport, name: str) -> float:
    beta = next(f for f in report.regression.factors if f.name == name).beta
    assert beta is not None
    return beta


# ----------------------------------------------------------------------------- US unchanged
def test_us_is_the_default_and_the_report_has_no_factor_set(client: ApiClient) -> None:
    default = client.get("/api/report/SPY")
    explicit = client.get("/api/report/SPY?factor_set=us")
    assert default.status_code == 200
    assert default.text == explicit.text
    body = default.json()
    assert "factor_set" not in body
    assert body["schema_version"] == "4"
    assert body["data"]["factors_source_url"] == DATASETS["ff5_monthly"].url.replace(
        DATASETS["ff5_monthly"].filename, "F-F_Research_Data_5_Factors_2x3_daily_CSV.zip"
    )
    assert not any("Europe" in note for note in body["notes"])


# ----------------------------------------------------------------------------- Europe
def test_europe_report_is_built_on_the_europe_factors(
    eu_world: tuple[World, FakeEurope], client: ApiClient
) -> None:
    _, fake = eu_world
    us = _report(client)
    eu = _report(client, "?factor_set=europe")
    assert eu.factor_set == "europe" and us.factor_set is None
    assert eu.schema_version == "4"
    assert _beta(eu, "Mkt-RF") == pytest.approx(_beta(us, "Mkt-RF") / 2.0, rel=1e-6)
    assert _beta(eu, "SMB") == pytest.approx(_beta(us, "SMB"), rel=1e-6)
    assert eu.data.factors_source_url == DATASETS["europe5_daily"].url
    assert eu.data.factors_downloaded_at == EU_DOWNLOADED
    assert any("Developed Europe" in note for note in eu.notes)
    assert any("Developed Europe" not in note and "US Fama-French" in note for note in us.notes)
    assert not any("US Fama-French" in note for note in eu.notes)
    assert eu.shrunk_betas is None
    assert fake.calls == 1


def test_europe_report_has_the_alpha_strip_and_rolling_betas(client: ApiClient) -> None:
    eu = _report(client, "?factor_set=europe")
    assert eu.alpha_strip is not None and eu.alpha_strip.status == "ok"
    assert [r.label for r in eu.alpha_strip.rows] == ["CAPM", "FF3", "FF5", "FF6"]
    assert [f.name for f in eu.regression.factors] == FACTORS
    assert eu.rolling and all(w.status == "ok" for w in eu.rolling)


def test_europe_ff6_report_has_momentum(client: ApiClient) -> None:
    eu = _report(client, "?factor_set=europe&model=ff6")
    assert eu.model == "ff6" and eu.factor_set == "europe"
    assert [f.name for f in eu.regression.factors][-1] == "Mom"


def test_the_set_is_cached_apart_and_the_europe_frame_once(
    eu_world: tuple[World, FakeEurope], client: ApiClient
) -> None:
    world, fake = eu_world
    _report(client)
    _report(client, "?factor_set=europe")
    _report(client, "?factor_set=europe")
    _report(client, "?factor_set=europe&model=ff6")
    keys = list(world.service.reports.keys())  # noqa: SIM118
    assert sorted({(k[5], k[6]) for k in keys}) == [
        ("ff5", "europe"),
        ("ff5", "us"),
        ("ff6", "europe"),
    ]
    assert world.service.reports.started == 3
    assert world.service.reports.hits == 1
    assert fake.calls == 1


def test_unknown_set_is_a_bad_request(client: ApiClient) -> None:
    assert_api_error(client.get("/api/report/SPY?factor_set=asia"), 400, "bad_request")


def test_europe_is_refused_when_the_loader_is_not_wired(tmp_path: Path) -> None:
    world = make_world(tmp_path)
    with serve(world.app) as plain:
        assert_api_error(plain.get("/api/report/SPY?factor_set=europe"), 503, "network")
        assert plain.get("/api/report/SPY").status_code == 200


def test_a_europe_loader_error_fails_the_europe_report_only(
    eu_world: tuple[World, FakeEurope], client: ApiClient
) -> None:
    _, fake = eu_world
    fake.error = FactorDownloadError("europe files unreachable")
    assert_api_error(client.get("/api/report/SPY?factor_set=europe"), 503, "network")
    assert client.get("/api/report/SPY").status_code == 200


def test_the_html_export_takes_the_set(client: ApiClient) -> None:
    response = client.get("/api/report/SPY/html?factor_set=europe")
    assert response.status_code == 200
    assert "Europe_5_Factors_Daily_CSV.zip" in response.text


def test_ranges_follow_the_dates_of_the_set(
    eu_world: tuple[World, FakeEurope], client: ApiClient
) -> None:
    _, fake = eu_world
    fake.frame = fake.frame.iloc[:-200].copy()  # the Europe files end 200 days earlier
    fake.frame.attrs = {"factor_set": "europe"}
    us = client.get("/api/report/SPY/ranges")
    eu = client.get("/api/report/SPY/ranges?factor_set=europe")
    assert us.status_code == 200 and eu.status_code == 200
    assert eu.json()["factors_last_date"] != us.json()["factors_last_date"]
    assert us.json() == client.get("/api/report/SPY/ranges?factor_set=us").json()


# ----------------------------------------------------------------------------- EUR + Europe
def test_eur_with_europe_runs_and_is_cached_apart(
    eu_world: tuple[World, FakeEurope], client: ApiClient
) -> None:
    world, _ = eu_world
    with_sources(cast(Any, world), FAKE)
    usd = _report(client, "?factor_set=europe")
    eur = _report(client, "?factor_set=europe&ccy=EUR")
    us_eur = _report(client, "?ccy=EUR")
    assert eur.factor_set == "europe" and us_eur.factor_set is None
    assert eur.currency is not None and eur.currency.reference == "EUR"
    assert _beta(eur, "Mkt-RF") != _beta(usd, "Mkt-RF")
    assert _beta(eur, "Mkt-RF") != _beta(us_eur, "Mkt-RF")
    keys = list(world.service.reports.keys())  # noqa: SIM118
    assert {(k[6], k[7]) for k in keys} == {("europe", "USD"), ("europe", "EUR"), ("us", "EUR")}


# ----------------------------------------------------------------------------- portfolio
@pytest.fixture
def pf_world(tmp_path: Path) -> tuple[portfolio_tests.World, FakeEurope]:
    w = portfolio_tests.make_world(tmp_path)
    europe = europe_of(w.factors)
    deps = w.app.state.report_service.deps

    def load_europe(now: datetime) -> pd.DataFrame:
        return europe

    object.__setattr__(deps, "load_europe_ff6", load_europe)
    fake = cast(FakeEurope, type("F", (), {"frame": europe})())
    return w, fake


def test_portfolio_body_takes_the_factor_set(
    pf_world: tuple[portfolio_tests.World, FakeEurope],
) -> None:
    w, _ = pf_world
    body = portfolio_tests.tree(
        [portfolio_tests.holding(0, "AAA", 0.6), portfolio_tests.holding(1, "BBB", 0.4)]
    )
    with TestClient(w.app) as c:
        client = cast(portfolio_tests.ApiClient, c)
        us = portfolio_tests.report_of(portfolio_tests.post(client, body))
        eu = portfolio_tests.report_of(
            portfolio_tests.post(client, {**body, "factor_set": "europe"})
        )
        again = portfolio_tests.post(client, {**body, "factor_set": "us"})
    assert us.factor_set is None and eu.factor_set == "europe"
    # the quality gate may compound the factors over five days, so the ratio is not exact
    assert _beta(eu, "Mkt-RF") == pytest.approx(_beta(us, "Mkt-RF") / 2.0, rel=0.1)
    assert eu.data.factors_source_url == DATASETS["europe5_daily"].url
    assert portfolio_tests.report_of(again).model_dump_json() == us.model_dump_json()
    service = w.app.state.report_service
    assert {k[8] for k in service.portfolios.keys()} == {"us", "europe"}  # noqa: SIM118


def test_portfolio_tree_leaves_out_the_us_set() -> None:
    from factordesk.api.portfolio_models import PortfolioTree

    body = portfolio_tests.tree([portfolio_tests.holding(0, "AAA", 1.0)])
    us = PortfolioTree.model_validate(body)
    eu = PortfolioTree.model_validate({**body, "factor_set": "europe"})
    assert "factor_set" not in json.loads(us.model_dump_json(exclude_unset=False))
    assert json.loads(eu.model_dump_json())["factor_set"] == "europe"
    with pytest.raises(ValueError, match="factor_set"):
        PortfolioTree.model_validate({**body, "factor_set": "asia"})


def test_portfolio_europe_without_a_loader_is_refused(tmp_path: Path) -> None:
    w = portfolio_tests.make_world(tmp_path)
    body = portfolio_tests.tree([portfolio_tests.holding(0, "AAA", 1.0)])
    with TestClient(w.app) as c:
        response = portfolio_tests.post(
            cast(portfolio_tests.ApiClient, c), {**body, "factor_set": "europe"}
        )
    portfolio_tests.refused(response, 503, "network")


# ----------------------------------------------------------------------------- upload
def test_upload_form_takes_the_factor_set(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    returns, us_frame, _ = monthly_case(72, 11, extra_factor_months=6)
    us_frame.attrs = {}
    seen: list[str] = []

    def load_ff6(frequency: str, **kw: object) -> pd.DataFrame:
        assert frequency == "monthly"
        seen.append(str(kw["factor_set"]))
        out = us_frame.copy()
        out["Mom"] = np.random.default_rng(93).normal(0.006, 0.03, size=len(us_frame))
        if kw["factor_set"] == "europe":
            out["Mkt-RF"] = out["Mkt-RF"] * 2.0
        out.attrs = {}
        return out

    monkeypatch.setattr(routes_upload, "load_ff6", load_ff6)
    world = upload_tests.make_world(tmp_path)
    with TestClient(world.app) as c:
        client = cast(upload_tests.ApiClient, c)
        body = upload_tests.csv_of(returns)

        def send(extra: dict[str, str]) -> httpx.Response:
            return client.post(
                "/api/report/upload",
                files={"file": ("record.csv", body, "text/csv")},
                data={"name": "Fund", **extra},
            )

        us = send({})
        eu = send({"factor_set": "europe"})
        bad = send({"factor_set": "asia"})
    assert us.status_code == 200 and eu.status_code == 200, (us.text, eu.text)
    us_report = FactorReport.model_validate_json(us.text)
    eu_report = FactorReport.model_validate_json(eu.text)
    assert us_report.factor_set is None and "factor_set" not in us.json()
    assert eu_report.factor_set == "europe"
    assert eu_report.data.factors_source_url == DATASETS["europe5_monthly"].url
    assert _beta(eu_report, "Mkt-RF") == pytest.approx(_beta(us_report, "Mkt-RF") / 2.0, rel=1e-6)
    assert seen == ["us", "europe", "us"]  # the Europe upload also loads the US frame
    assert bad.status_code in (400, 422)


# ----------------------------------------------------------------------------- US inputs kept
def _section_loaders(world: World) -> None:
    """Wire the macro, energy and world beta data (fakes) into the world's app."""
    from factordesk.section_hooks.context import WorldBenchmarkInput
    from factordesk.tests.fixtures.dgp import price_history
    from factordesk.tests.test_currency_view import _usd_loaders  # pyright: ignore[reportPrivateUsage]

    dates = pd.DatetimeIndex(world.history.frame.index[1:])
    macro, energy = _usd_loaders(dates)
    bench = price_history(
        np.random.default_rng(5).normal(0.0004, 0.009, size=len(dates)), dates, ticker="ACWI"
    )
    deps = world.service.deps
    object.__setattr__(deps, "load_macro", macro)
    object.__setattr__(deps, "load_energy", energy)
    object.__setattr__(deps, "load_world_benchmark", lambda: WorldBenchmarkInput(history=bench))


@pytest.mark.parametrize("ccy", ["USD", "EUR"])
def test_macro_energy_and_world_beta_do_not_depend_on_the_factor_set(
    eu_world: tuple[World, FakeEurope], client: ApiClient, ccy: str
) -> None:
    world, fake = eu_world
    with_sources(cast(Any, world), FAKE)
    _section_loaders(world)
    # A different calendar and a different market factor: only the US inputs may reach the three
    # sections.
    frame = fake.frame
    fake.frame = frame.drop(frame.index[::9])
    fake.frame.attrs = dict(frame.attrs)
    for query in ("", "&model=ff6"):
        us = client.get(f"/api/report/SPY?ccy={ccy}{query}").json()
        eu = client.get(f"/api/report/SPY?ccy={ccy}&factor_set=europe{query}").json()
        assert eu["factor_set"] == "europe"
        assert eu["data"]["n_obs"] != us["data"]["n_obs"]  # the Europe sample is not the US one
        for section in ("macro", "energy", "world_beta"):
            assert us[section] is not None and us[section]["status"] == "ok", section
            assert eu[section] == us[section], (section, ccy, query)
        assert eu["regression"] != us["regression"]


def test_the_world_beta_note_about_the_market_factor_is_gone(
    eu_world: tuple[World, FakeEurope], client: ApiClient
) -> None:
    world, _ = eu_world
    _section_loaders(world)
    eu = client.get("/api/report/SPY?factor_set=europe").json()
    assert not any("labelled US market" in note for note in eu["notes"])


# ----------------------------------------------------------------------------- failures
def test_a_europe_file_that_fails_validation_gives_502(
    eu_world: tuple[World, FakeEurope], client: ApiClient
) -> None:
    from factordesk.data.factors import FactorDataError

    _, fake = eu_world
    fake.error = FactorDataError("europe5_daily: unexpected columns")
    assert_api_error(client.get("/api/report/SPY?factor_set=europe"), 502, "factor_data_invalid")
    assert client.get("/api/report/SPY").status_code == 200


def test_a_europe_failure_on_ranges_gives_503(
    eu_world: tuple[World, FakeEurope], client: ApiClient
) -> None:
    _, fake = eu_world
    fake.error = FactorDownloadError("europe files unreachable")
    assert_api_error(client.get("/api/report/SPY/ranges?factor_set=europe"), 503, "network")
    assert client.get("/api/report/SPY/ranges").status_code == 200


def test_upload_falls_back_to_the_europe_five_factors_without_momentum(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    returns, us_frame, _ = monthly_case(72, 11, extra_factor_months=6)
    us_frame.attrs = {}
    five_calls: list[str] = []

    def load_ff6(frequency: str, **kw: object) -> pd.DataFrame:
        if kw["factor_set"] == "europe":
            raise FactorDownloadError("europe momentum file unreachable")
        out = us_frame.copy()
        out["Mom"] = np.random.default_rng(93).normal(0.006, 0.03, size=len(us_frame))
        return out

    def load_ff5(**kw: object) -> pd.DataFrame:
        five_calls.append(str(kw["factor_set"]))
        out = us_frame.copy()
        out["Mkt-RF"] = out["Mkt-RF"] * 2.0
        return out

    monkeypatch.setattr(routes_upload, "load_ff6", load_ff6)
    monkeypatch.setattr(routes_upload, "load_ff5_monthly", load_ff5)
    world = upload_tests.make_world(tmp_path)
    with TestClient(world.app) as c:
        client = cast(upload_tests.ApiClient, c)
        response = client.post(
            "/api/report/upload",
            files={"file": ("record.csv", upload_tests.csv_of(returns), "text/csv")},
            data={"name": "Fund", "factor_set": "europe"},
        )
    assert response.status_code == 200, response.text
    report = FactorReport.model_validate_json(response.text)
    assert report.factor_set == "europe"
    assert report.alpha_strip is None  # no momentum: no strip
    assert five_calls == ["europe"]


@pytest.mark.parametrize("ccy", ["USD", "EUR"])
def test_monthly_macro_and_energy_do_not_depend_on_the_factor_set(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, ccy: str
) -> None:
    from factordesk.tests.test_currency_view import _usd_loaders  # pyright: ignore[reportPrivateUsage]

    returns, us_frame, _ = monthly_case(72, 11, start="2015-01-31", extra_factor_months=6)
    us_frame.attrs = {}

    def load_ff6(frequency: str, **kw: object) -> pd.DataFrame:
        out = us_frame.copy()
        out["Mom"] = np.random.default_rng(93).normal(0.006, 0.03, size=len(us_frame))
        if kw["factor_set"] == "europe":
            out["Mkt-RF"] = out["Mkt-RF"] * 2.0
            out = out.drop(out.index[[5, 6, 30]])  # other months, so another sample
        out.attrs = {}
        return out

    monkeypatch.setattr(routes_upload, "load_ff6", load_ff6)
    world = upload_tests.make_world(tmp_path)
    with_sources(cast(Any, world), FAKE)
    macro, energy = _usd_loaders(pd.date_range("2010-01-01", "2023-06-30", freq="D"))
    deps = world.service.deps
    object.__setattr__(deps, "load_macro", macro)
    object.__setattr__(deps, "load_energy", energy)
    with TestClient(world.app) as c:
        client = cast(upload_tests.ApiClient, c)

        def send(extra: dict[str, str]) -> dict[str, Any]:
            response = client.post(
                "/api/report/upload",
                files={"file": ("record.csv", upload_tests.csv_of(returns), "text/csv")},
                data={"name": "Fund", "ccy": ccy, "record_currency": ccy, **extra},
            )
            assert response.status_code == 200, response.text
            return cast(dict[str, Any], response.json())

        us = send({})
        eu = send({"factor_set": "europe"})
    assert eu["data"]["n_obs"] < us["data"]["n_obs"]
    for section in ("macro", "energy"):
        assert us[section] is not None and us[section]["status"] == "ok", section
        assert eu[section] == us[section], (section, ccy)
