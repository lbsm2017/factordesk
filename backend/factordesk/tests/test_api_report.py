"""Report endpoints: report, ranges and HTML download, range rules and caching (DB2, DB3).

Offline: ``AppDeps`` is built from fakes (``StaticProvider`` over ``dgp_a`` prices, a factor
frame cut 30 rows before the price end), the clock is fixed, ``tmp_path`` is the data dir, and
an autouse fixture makes any socket connection other than loopback fail.
"""

from __future__ import annotations

import asyncio
import json
import socket
import threading
import time
from collections.abc import Callable, Generator, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Protocol, cast

import httpx
import numpy as np
import pandas as pd
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from factordesk.analytics.sample import MIN_OBS
from factordesk.api import service as service_module
from factordesk.api.deps import AppDeps
from factordesk.api.errors import ApiException
from factordesk.api.main import create_app
from factordesk.api.openapi_dump import openapi_text
from factordesk.api.ranges import (
    Coverage,
    check_request,
    long_date,
    preset_label,
    preset_start,
    range_options,
    resolve,
    years_back,
)
from factordesk.api.service import ReportService, SingleFlight
from factordesk.data import factors as factors_module
from factordesk.data.factors import FactorDataError, FactorDownloadError, FactorStatus
from factordesk.data.prices import PriceDataError, PriceHistory
from factordesk.pipeline import assemble_report
from factordesk.report.render_html import render_report_html
from factordesk.report.schema import RANGE_PRESETS, ApiError, FactorReport, RangeOptions
from factordesk.tests.fixtures.dgp import StaticProvider, dgp_a, price_history, rng_for

NOW = datetime(2026, 11, 18, 15, 0, tzinfo=UTC)
DOWNLOADED = datetime(2026, 10, 2, 8, 30, tzinfo=UTC)
N_PRICES = 1400
CUT = 30
OWNER_PRESETS = ("3Y", "5Y", "10Y", "FULL")
SHORT_SPAN = ("3Y", "5Y", "FULL")
"""The presets that cover the synthetic history of about five and a half years."""


class ApiClient(Protocol):
    def get(self, url: str) -> httpx.Response: ...


@contextmanager
def serve(app: FastAPI, *, raise_server_exceptions: bool = True) -> Generator[ApiClient]:
    with TestClient(app, raise_server_exceptions=raise_server_exceptions) as test_client:  # pyright: ignore[reportUnknownVariableType]
        yield cast(ApiClient, test_client)


@pytest.fixture(autouse=True)
def _no_network(monkeypatch: pytest.MonkeyPatch) -> None:  # pyright: ignore[reportUnusedFunction]
    real_connect = socket.socket.connect

    def refuse(self: socket.socket, address: Any) -> None:
        # Loopback stays open: the Windows event loop and the test client build socket pairs.
        if isinstance(address, tuple) and cast(tuple[object, ...], address)[0] in (
            "127.0.0.1",
            "::1",
        ):
            real_connect(self, cast(tuple[object, ...], address))
            return
        raise AssertionError(f"network access attempted: {address!r}")

    monkeypatch.setattr(socket.socket, "connect", refuse)


# --------------------------------------------------------------------------- fakes


def _day(value: object) -> date:
    return pd.Timestamp(str(value)).date()


class FakeFactors:
    """Fake factor store whose status always describes the frame it serves."""

    def __init__(self, frame: pd.DataFrame, downloaded: datetime | None = DOWNLOADED) -> None:
        self.loads: list[bool] = []
        self.error: Exception | None = None
        self.frame = frame
        self.status = self._status(frame, downloaded)

    @staticmethod
    def _status(frame: pd.DataFrame, downloaded: datetime | None) -> FactorStatus:
        last = _day(frame.index[-1])
        behind = (NOW.date() - last).days
        return FactorStatus(
            last_date=last,
            first_date=_day(frame.index[0]),
            days_behind=behind,
            last_download_at=downloaded,
            source_url=factors_module.SOURCE_URL,
            stale=behind > factors_module.STALE_AFTER_DAYS,
        )

    def publish(self, frame: pd.DataFrame, downloaded: datetime) -> None:
        """A new vintage arrives (as after a refresh)."""
        self.frame = frame
        self.status = self._status(frame, downloaded)

    def load(self, refresh: bool, now: datetime) -> pd.DataFrame:
        self.loads.append(refresh)
        if self.error is not None:
            raise self.error
        return self.frame

    def read_status(self, now: datetime) -> FactorStatus | None:
        return self.status


class GatedProvider(StaticProvider):
    """``StaticProvider`` that can wait on an event, fail, and records its worker threads."""

    def __init__(self, history: PriceHistory) -> None:
        super().__init__(history)
        self.started = threading.Event()
        self.release = threading.Event()
        self.release.set()
        self.error: Exception | None = None
        self.threads: list[str] = []

    def fetch(self, ticker: str) -> PriceHistory:
        self.threads.append(threading.current_thread().name)
        result = super().fetch(ticker)
        self.started.set()
        assert self.release.wait(timeout=20), "test never released the fake provider"
        if self.error is not None:
            raise self.error
        return result


@dataclass
class World:
    app: FastAPI
    service: ReportService
    factors: FakeFactors
    provider: GatedProvider
    history: PriceHistory
    full_factors: pd.DataFrame


def make_world(
    tmp_path: Path,
    *,
    n: int = N_PRICES,
    cut: int = CUT,
    history: PriceHistory | None = None,
    test_number: int = 400,
) -> World:
    d = dgp_a(rng_for(test_number), n=n)
    hist = history if history is not None else d.history
    fake = FakeFactors(d.factors.iloc[: n - cut])
    provider = GatedProvider(hist)
    deps = AppDeps(
        price_provider=provider,
        load_factors=fake.load,
        factor_status=fake.read_status,
        now=lambda: NOW,
        data_dir=tmp_path,
        static_dir=None,
    )
    app = create_app(deps)
    return World(app, app.state.report_service, fake, provider, hist, d.factors)


@pytest.fixture
def world(tmp_path: Path) -> World:
    return make_world(tmp_path)


@pytest.fixture
def client(world: World) -> Iterator[ApiClient]:
    with serve(world.app) as test_client:
        yield test_client


def no_nan(text: str) -> Any:
    """Parse JSON, failing on NaN or infinity."""

    def refuse(token: str) -> object:
        raise AssertionError(f"non-finite number {token} in a response body")

    return json.loads(text, parse_constant=refuse)


def assert_api_error(response: httpx.Response, status: int, code: str) -> ApiError:
    assert response.status_code == status, response.text
    error = ApiError.model_validate(no_nan(response.text))
    assert error.code == code
    for text in (error.message, error.action):
        assert text.endswith((".", ")"))
        assert "Traceback" not in text and "Error(" not in text
    return error


def report_of(response: httpx.Response) -> FactorReport:
    assert response.status_code == 200, response.text
    no_nan(response.text)
    return FactorReport.model_validate_json(response.text)


def ranges_of(response: httpx.Response) -> RangeOptions:
    assert response.status_code == 200, response.text
    no_nan(response.text)
    return RangeOptions.model_validate_json(response.text)


def first_return(history: PriceHistory) -> date:
    return _day(history.frame.index[1])


def last_price(history: PriceHistory) -> date:
    return _day(history.frame.index[-1])


# ------------------------------------------------------------------ range rules (pure)


def test_preset_starts_follow_the_anchor() -> None:
    anchor = date(2026, 9, 30)
    assert preset_start("3Y", anchor) == date(2023, 10, 1)
    assert preset_start("5Y", anchor) == date(2021, 10, 1)
    assert preset_start("10Y", anchor) == date(2016, 10, 1)
    assert preset_start("FULL", anchor) is None
    assert [preset_label(p) for p in OWNER_PRESETS] == ["3Y", "5Y", "10Y", "Full history"]


def test_29_february_maps_to_28_february() -> None:
    assert years_back(date(2028, 2, 29), 1) == date(2027, 2, 28)
    assert years_back(date(2028, 2, 29), 4) == date(2024, 2, 28)
    assert years_back(date(2027, 2, 28), 3) == date(2024, 2, 28)
    assert preset_start("3Y", date(2028, 2, 29)) == date(2025, 3, 1)
    assert preset_start("5Y", date(2028, 2, 29)) == date(2023, 3, 1)
    assert preset_start("10Y", date(2028, 2, 29)) == date(2018, 3, 1)


def test_anchor_is_the_earlier_of_factor_and_price_ends() -> None:
    assert Coverage(date(2010, 1, 5), date(2026, 11, 17), date(2026, 9, 30)).anchor == date(
        2026, 9, 30
    )
    assert Coverage(date(2010, 1, 5), date(2020, 3, 31), date(2026, 9, 30)).anchor == date(
        2020, 3, 31
    )


COV = Coverage(date(2010, 1, 5), date(2026, 11, 17), date(2026, 9, 30))


def test_resolve_presets_have_an_open_end_and_dates_pass_as_given() -> None:
    assert resolve("3Y", None, None, COV) == (date(2023, 10, 1), None)
    assert resolve("FULL", None, None, COV) == (None, None)
    assert resolve(None, None, None, COV) == (None, None)
    # an end after the factor data is allowed and passed on unchanged
    assert resolve(None, date(2020, 1, 2), date(2026, 11, 10), COV) == (
        date(2020, 1, 2),
        date(2026, 11, 10),
    )
    # the edges of the history are the same as no date
    assert resolve(None, COV.first_return_date, COV.last_price_date, COV) == (None, None)


@pytest.mark.parametrize(
    ("preset", "start", "end", "message"),
    [
        ("3Y", date(2020, 1, 2), None, "Both a range and dates were given."),
        ("FULL", None, date(2020, 1, 2), "Both a range and dates were given."),
        (
            None,
            date(2026, 5, 1),
            date(2026, 1, 1),
            "The start date 1 May 2026 is after the end date 1 Jan 2026.",
        ),
        (
            None,
            date(2026, 11, 18),
            None,
            "The start date 18 Nov 2026 is after the last price date 17 Nov 2026.",
        ),
        (
            None,
            None,
            date(2009, 12, 31),
            "The end date 31 Dec 2009 is before the first return date 5 Jan 2010.",
        ),
    ],
)
def test_resolve_refuses_bad_ranges(
    preset: Any, start: date | None, end: date | None, message: str
) -> None:
    with pytest.raises(ApiException) as caught:
        resolve(preset, start, end, COV)
    assert caught.value.code == "bad_range" and caught.value.status == 400
    assert caught.value.message == message


def test_check_request_needs_no_data() -> None:
    check_request(None, date(2020, 1, 1), date(2020, 1, 1))
    with pytest.raises(ApiException):
        check_request("3Y", None, date(2020, 1, 1))
    assert long_date(date(2024, 8, 8)) == "8 Aug 2024"


def test_range_options_reason_names_the_minimum_and_the_count() -> None:
    d = dgp_a(rng_for(401), n=N_PRICES)
    options = range_options("SYN", d.history, d.factors.iloc[: N_PRICES - CUT], min_obs=800)
    by_preset = {o.preset: o for o in options.options}
    assert tuple(by_preset) == RANGE_PRESETS
    three = by_preset["3Y"]
    assert not three.available and three.n_obs < 800
    assert three.reason == f"3Y has {three.n_obs} trading days; a regression needs at least 800."
    assert by_preset["5Y"].available and by_preset["5Y"].reason is None
    assert by_preset["FULL"].available and by_preset["FULL"].n_obs == N_PRICES - CUT
    assert options.min_obs == 800
    ten = by_preset["10Y"]
    assert ten.start is not None and not ten.available
    assert ten.n_obs == by_preset["FULL"].n_obs
    assert ten.reason == (
        f"10Y needs prices from {long_date(ten.start)}, but the history starts "
        f"{long_date(options.first_return_date)}. Full history covers all of it."
    )


def test_ten_years_of_history_make_10y_available_with_its_own_start() -> None:
    n = 2700
    d = dgp_a(rng_for(404), n=n)
    options = range_options("SYN", d.history, d.factors.iloc[: n - CUT])
    by_preset = {o.preset: o for o in options.options}
    ten = by_preset["10Y"]
    assert ten.available and ten.reason is None
    anchor = options.factors_last_date
    assert ten.start == preset_start("10Y", anchor)
    assert ten.start is not None and ten.start > options.first_return_date
    assert by_preset["5Y"].n_obs < ten.n_obs < by_preset["FULL"].n_obs


# ------------------------------------------------------------------------- report


def test_report_defaults_to_full_history(world: World, client: ApiClient) -> None:
    rep = report_of(client.get("/api/report/syn"))
    assert rep.ticker == "SYN" and rep.generated_at == NOW
    assert world.provider.calls == ["SYN"]
    assert world.factors.loads == [False]
    assert rep.data.requested_start == first_return(world.history)
    assert rep.data.requested_end == last_price(world.history)
    assert rep.data.n_obs == N_PRICES - CUT
    assert rep.data.uncovered.n == CUT
    assert rep.data.factors_downloaded_at == DOWNLOADED
    assert rep.regression.sample.factor_vintage.downloaded_at == DOWNLOADED
    # FULL is the same request, so the same cache entry
    assert report_of(client.get("/api/report/SYN?range=FULL")) == rep
    assert world.service.reports.started == 1


def test_report_preset_and_the_same_dates_share_a_cache_entry(
    world: World, client: ApiClient
) -> None:
    options = ranges_of(client.get("/api/report/SYN/ranges"))
    three = next(o for o in options.options if o.preset == "3Y")
    assert three.start is not None and three.available
    rep = report_of(client.get("/api/report/SYN?range=3Y"))
    assert rep.data.requested_start == three.start
    assert rep.data.requested_end == last_price(world.history)
    assert rep.data.n_obs == three.n_obs
    assert rep.regression.sample.requested_start == three.start
    same = report_of(client.get(f"/api/report/SYN?start={three.start}"))
    with_end = report_of(
        client.get(f"/api/report/SYN?start={three.start}&end={last_price(world.history)}")
    )
    assert same == rep == with_end
    assert world.service.reports.started == 1
    assert world.service.reports.hits == 2


def test_custom_dates_reach_the_sample(world: World, client: ApiClient) -> None:
    start, end = date(2011, 3, 1), date(2014, 6, 30)
    rep = report_of(client.get(f"/api/report/SYN?start={start}&end={end}"))
    for info in (rep.regression.sample, rep.risk_contribution.sample):
        assert (info.requested_start, info.requested_end) == (start, end)
    assert (rep.data.requested_start, rep.data.requested_end) == (start, end)
    assert rep.data.actual_start is not None and rep.data.actual_start >= start
    assert rep.data.actual_end is not None and rep.data.actual_end <= end
    assert rep.data.uncovered.n == 0


def test_an_end_after_the_factor_data_is_reported_not_clipped(
    world: World, client: ApiClient
) -> None:
    end = _day(world.history.frame.index[-5])
    rep = report_of(client.get(f"/api/report/SYN?start=2012-01-03&end={end}"))
    assert rep.data.requested_end == end
    assert rep.data.actual_end == rep.data.factors_last_date
    assert rep.data.uncovered.n == CUT - 4


def test_report_and_ranges_agree_on_row_counts(world: World, client: ApiClient) -> None:
    options = ranges_of(client.get("/api/report/SYN/ranges"))
    assert options.ticker == "SYN"
    assert options.first_return_date == first_return(world.history)
    assert options.last_price_date == last_price(world.history)
    assert options.factors_last_date == world.factors.status.last_date
    assert options.min_obs == MIN_OBS
    assert tuple(o.preset for o in options.options) == RANGE_PRESETS
    for option in options.options:
        if option.preset not in SHORT_SPAN:
            continue
        assert option.available == (option.n_obs >= MIN_OBS)
        if not option.available:
            assert option.reason == (
                f"{preset_label(option.preset)} has {option.n_obs} trading days; "
                f"a regression needs at least {MIN_OBS}."
            )
    ten = next(o for o in options.options if o.preset == "10Y")
    assert not ten.available and ten.reason is not None
    assert ten.reason.endswith("Full history covers all of it.")
    for preset in SHORT_SPAN:
        option = next(o for o in options.options if o.preset == preset)
        assert option.available, option
        rep = report_of(client.get(f"/api/report/SYN?range={preset}"))
        assert rep.data.n_obs == option.n_obs
    assert world.provider.calls == ["SYN"]
    assert world.service.ranges.started == 1


def test_short_history_makes_every_preset_unavailable_with_a_visible_reason(
    tmp_path: Path,
) -> None:
    w = make_world(tmp_path, n=400, test_number=402)
    with serve(w.app) as client:
        options = ranges_of(client.get("/api/report/SYN/ranges"))
        n = 400 - CUT
        for option in options.options:
            assert not option.available
            assert option.reason == (
                f"{preset_label(option.preset)} has {option.n_obs} trading days; "
                f"a regression needs at least {MIN_OBS}."
            )
        assert {o.n_obs for o in options.options if o.preset in OWNER_PRESETS} == {n}
        error = assert_api_error(client.get("/api/report/SYN"), 422, "insufficient_history")
        assert error.message == (
            f"SYN has {n} trading days in this range that line up with the factor data; "
            f"at least {MIN_OBS} (about two years) are needed."
        )
        assert error.action == "Choose a longer range or Full history."
        assert_api_error(client.get("/api/report/SYN/html?range=3Y"), 422, "insufficient_history")


def test_a_price_that_does_not_move_is_refused_with_its_reason(tmp_path: Path) -> None:
    dates = pd.bdate_range("2010-01-04", periods=900, name="date")
    flat = price_history(np.zeros(900), dates)
    w = make_world(tmp_path, n=900, history=flat, test_number=403)
    with serve(w.app) as client:
        options = ranges_of(client.get("/api/report/SYN/ranges"))
        for option in options.options:
            assert not option.available
            assert option.reason is not None
            if option.n_obs >= MIN_OBS:
                assert "does not move" in option.reason
                assert f"at least {MIN_OBS}" in option.reason
                assert f"has {option.n_obs} trading days" in option.reason
        error = assert_api_error(client.get("/api/report/SYN"), 422, "degenerate_input")
        assert error.message.startswith("Cannot analyse SYN: the price of SYN does not move")


# ------------------------------------------------------------------------- html


def test_html_download_is_the_renderer_output_of_the_same_report(
    world: World, client: ApiClient
) -> None:
    json_response = client.get("/api/report/SYN?range=5Y")
    rep = report_of(json_response)
    response = client.get("/api/report/syn/html?range=5Y")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert response.headers["content-disposition"] == 'attachment; filename="SYN_report.html"'
    assert response.content == render_report_html(rep).encode("utf-8")
    assert world.service.reports.started == 1


def test_html_errors_are_api_errors(world: World, client: ApiClient) -> None:
    assert_api_error(client.get("/api/report/BRK%20B/html"), 422, "invalid_ticker")
    assert_api_error(client.get("/api/report/SYN/html?range=3Y&end=2014-01-02"), 400, "bad_range")
    assert world.provider.calls == []


# ---------------------------------------------------------------------- error model


@pytest.mark.parametrize("suffix", ["", "/ranges", "/html"])
@pytest.mark.parametrize("raw", ["BRK%20B", "TOOLONGTICKER1", "%2Eetc", "SP%3BY"])
def test_invalid_ticker_never_reaches_a_provider(
    world: World, client: ApiClient, raw: str, suffix: str
) -> None:
    error = assert_api_error(client.get(f"/api/report/{raw}{suffix}"), 422, "invalid_ticker")
    assert error.action == "Use 1 to 12 letters, digits or . ^ = - (for example SPY or BRK-B)."
    assert world.provider.calls == [] and world.factors.loads == []


def test_invalid_ticker_names_the_symbol(client: ApiClient) -> None:
    error = assert_api_error(client.get("/api/report/BRK%20B"), 422, "invalid_ticker")
    assert error.message == "BRK B is not a valid ticker."


@pytest.mark.parametrize(
    ("query", "message"),
    [
        ("range=3Y&start=2014-01-02", "Both a range and dates were given."),
        ("range=FULL&end=2014-01-02", "Both a range and dates were given."),
        (
            "start=2026-05-01&end=2026-01-01",
            "The start date 1 May 2026 is after the end date 1 Jan 2026.",
        ),
        ("start=yesterday", "The start date is not a valid date."),
        ("end=2026-02-30", "The end date is not a valid date."),
        ("range=2Y", None),
        ("range=1Y", None),
        ("range=YTD", None),
    ],
)
def test_bad_ranges_are_refused_before_any_data_is_read(
    world: World, client: ApiClient, query: str, message: str | None
) -> None:
    error = assert_api_error(client.get(f"/api/report/SYN?{query}"), 400, "bad_range")
    if message is not None:
        assert error.message == message
    assert world.provider.calls == [] and world.factors.loads == []


def test_dates_outside_the_price_history_are_bad_ranges(world: World, client: ApiClient) -> None:
    after = assert_api_error(client.get("/api/report/SYN?start=2026-01-02"), 400, "bad_range")
    assert after.message == (
        f"The start date 2 Jan 2026 is after the last price date "
        f"{long_date(last_price(world.history))}."
    )
    assert after.action == "Choose an earlier start date."
    before = assert_api_error(client.get("/api/report/SYN?end=2009-06-30"), 400, "bad_range")
    assert before.action == "Choose a later end date."


def yahoo_refusal() -> Exception:
    from yfinance.exceptions import YFRateLimitError  # pyright: ignore[reportMissingTypeStubs]

    return YFRateLimitError()


@pytest.mark.parametrize("suffix", ["", "/ranges", "/html"])
@pytest.mark.parametrize(
    ("make", "status", "code"),
    [
        (lambda: PriceDataError("no data"), 404, "unknown_ticker"),
        (lambda: httpx.ConnectError("refused"), 503, "network"),
        (lambda: OSError("disk"), 503, "network"),
        (yahoo_refusal, 503, "upstream_refused"),
    ],
)
def test_provider_failures_become_api_errors(
    tmp_path: Path, suffix: str, make: Callable[[], Exception], status: int, code: str
) -> None:
    w = make_world(tmp_path)
    w.provider.error = make()
    with serve(w.app) as client:
        error = assert_api_error(client.get(f"/api/report/xyz{suffix}"), status, code)
    if code == "unknown_ticker":
        assert error.message == "No prices were returned for XYZ."
        assert error.action == "Check the ticker symbol."


@pytest.mark.parametrize(
    ("make", "status", "code"),
    [
        (lambda: FactorDataError("bad header"), 502, "factor_data_invalid"),
        (lambda: FactorDownloadError("HTTP 503"), 503, "network"),
    ],
)
def test_factor_failures_become_api_errors(
    tmp_path: Path, make: Callable[[], Exception], status: int, code: str
) -> None:
    w = make_world(tmp_path)
    w.factors.error = make()
    with serve(w.app) as client:
        assert_api_error(client.get("/api/report/SYN"), status, code)
        assert_api_error(client.get("/api/report/SYN/ranges"), status, code)
    assert w.provider.calls == []


def test_an_unexpected_failure_is_internal_and_hides_the_traceback(
    world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(*args: object, **kwargs: object) -> FactorReport:
        raise ArithmeticError("non-finite statistic nan in an 'ok' result")

    monkeypatch.setattr(service_module, "assemble_report", broken)
    with serve(world.app, raise_server_exceptions=False) as client:
        response = client.get("/api/report/SYN")
    error = assert_api_error(response, 500, "internal")
    assert error.message == (
        "The report for SYN could not be computed: non-finite statistic nan in an 'ok' result."
    )
    assert "ArithmeticError" not in response.text


def test_unknown_report_path_is_an_api_404(client: ApiClient) -> None:
    error = assert_api_error(client.get("/api/report/SYN/pdf"), 404, "not_found")
    assert error.message == "There is no API endpoint at /api/report/SYN/pdf."


# ------------------------------------------------------------- caching and threads


def test_a_second_request_is_a_cache_hit(world: World, client: ApiClient) -> None:
    first = client.get("/api/report/SYN")
    second = client.get("/api/report/SYN")
    assert first.content == second.content
    assert world.provider.calls == ["SYN"]
    assert world.service.reports.started == 1 and world.service.reports.hits == 1
    assert world.factors.loads == [False, False]  # the auto-refresh check runs every time


def test_concurrent_requests_share_one_fetch_and_one_build(
    world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    builds: list[str] = []

    def counting(*args: Any, **kwargs: Any) -> FactorReport:
        builds.append(threading.current_thread().name)
        return assemble_report(*args, **kwargs)

    monkeypatch.setattr(service_module, "assemble_report", counting)
    world.provider.release.clear()
    results: list[httpx.Response] = []

    with serve(world.app) as client:

        def call() -> None:
            results.append(client.get("/api/report/SYN?range=3Y"))

        threads = [threading.Thread(target=call) for _ in range(2)]
        threads[0].start()
        assert world.provider.started.wait(timeout=20)
        threads[1].start()
        deadline = time.monotonic() + 20
        while world.service.prices.waiting < 2 and time.monotonic() < deadline:
            time.sleep(0.01)
        assert world.service.prices.waiting == 2
        world.provider.release.set()
        for thread in threads:
            thread.join(timeout=60)

    assert [r.status_code for r in results] == [200, 200]
    assert results[0].content == results[1].content
    assert world.provider.calls == ["SYN"]
    assert len(builds) == 1 and world.service.reports.started == 1
    # blocking work runs in worker threads, never on the event loop
    assert builds[0].startswith("AnyIO worker thread")
    assert world.provider.threads[0].startswith("AnyIO worker thread")


def test_a_failure_reaches_every_waiter_and_is_not_cached(world: World) -> None:
    world.provider.release.clear()
    world.provider.error = PriceDataError("no data")
    results: list[httpx.Response] = []
    with serve(world.app) as client:

        def call() -> None:
            results.append(client.get("/api/report/XYZ"))

        threads = [threading.Thread(target=call) for _ in range(2)]
        threads[0].start()
        assert world.provider.started.wait(timeout=20)
        threads[1].start()
        deadline = time.monotonic() + 20
        while world.service.prices.waiting < 2 and time.monotonic() < deadline:
            time.sleep(0.01)
        world.provider.release.set()
        for thread in threads:
            thread.join(timeout=30)
        assert [r.status_code for r in results] == [404, 404]
        assert results[0].json() == results[1].json()
        assert world.provider.calls == ["XYZ"]
        world.provider.error = None
        assert client.get("/api/report/XYZ").status_code == 200
    assert world.provider.calls == ["XYZ", "XYZ"]


def test_a_new_vintage_rebuilds_and_drops_old_entries(world: World, client: ApiClient) -> None:
    old = report_of(client.get("/api/report/SYN"))
    ranges_of(client.get("/api/report/SYN/ranges"))
    world.factors.publish(
        world.full_factors.iloc[: N_PRICES - 10], datetime(2026, 11, 1, tzinfo=UTC)
    )
    new = report_of(client.get("/api/report/SYN"))
    assert world.service.reports.started == 2
    assert new.data.factors_last_date > old.data.factors_last_date
    assert new.data.n_obs == N_PRICES - 10
    assert new.data.factors_downloaded_at == datetime(2026, 11, 1, tzinfo=UTC)
    # only entries of the current vintage stay in memory
    assert len(world.service.reports) == 1 and len(world.service.ranges) == 0
    assert world.service.reports.keys()[0][3].last_date == new.data.factors_last_date
    # prices are keyed by ticker and day, so they were not fetched again
    assert world.provider.calls == ["SYN"]


# --------------------------------------------------------------------- single flight


def test_single_flight_survives_a_cancelled_waiter_and_keeps_an_lru() -> None:
    async def scenario() -> None:
        flight: SingleFlight[str, int] = SingleFlight(2)
        gate = asyncio.Event()
        calls: list[str] = []

        def maker(key: str, value: int) -> Callable[[], Any]:
            async def make() -> int:
                calls.append(key)
                await gate.wait()
                return value

            return make

        waiter = asyncio.ensure_future(flight.get("a", maker("a", 1)))
        await asyncio.sleep(0)
        waiter.cancel()
        with pytest.raises(asyncio.CancelledError):
            await waiter
        gate.set()
        # joins the shielded task, which went on after its only waiter was cancelled
        assert await flight.get("a", maker("a", 99)) == 1
        assert calls == ["a"] and flight.keys() == ["a"]
        await flight.get("b", maker("b", 2))
        await flight.get("a", maker("a", 99))  # hit: "a" becomes most recent
        await flight.get("c", maker("c", 3))  # evicts "b"
        assert flight.keys() == ["a", "c"] and flight.hits == 1 and flight.started == 3

        async def fail() -> int:
            raise ValueError("boom")

        with pytest.raises(ValueError, match="boom"):
            await flight.get("d", fail)
        assert flight.keys() == ["a", "c"]

        nothing: SingleFlight[str, int] = SingleFlight(0)
        await nothing.get("x", maker("x", 5))
        assert len(nothing) == 0
        with pytest.raises(ValueError, match="max_size"):
            SingleFlight[str, int](-1)

    asyncio.run(scenario())


# ------------------------------------------------------------------------- openapi


def test_openapi_lists_the_report_endpoints() -> None:
    document = json.loads(openapi_text())
    paths = document["paths"]
    assert {
        "/api/report/{ticker}",
        "/api/report/{ticker}/ranges",
        "/api/report/{ticker}/html",
    } <= set(paths)
    params = {p["name"] for p in paths["/api/report/{ticker}"]["get"]["parameters"]}
    assert params == {"ticker", "range", "start", "end", "model", "ccy", "factor_set"}
    assert "text/html" in paths["/api/report/{ticker}/html"]["get"]["responses"]["200"]["content"]
