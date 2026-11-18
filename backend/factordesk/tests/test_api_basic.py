"""API skeleton tests: health, factor status and refresh, ticker suggestions, error model.

Offline: ``AppDeps`` is built from fakes, the clock is fixed, ``tmp_path`` is the data dir, and
an autouse fixture makes any socket connection fail.
"""

from __future__ import annotations

import dataclasses
import json
import socket
import threading
import time
from collections.abc import Callable, Generator, Iterator
from contextlib import contextmanager
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Protocol, cast

import httpx
import pandas as pd
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from factordesk.analytics.sample import DegenerateInputError, InsufficientHistoryError
from factordesk.api import deps as deps_module
from factordesk.api.deps import AppDeps, default_deps
from factordesk.api.errors import ApiException
from factordesk.api.main import create_app, create_dev_app
from factordesk.api.openapi_dump import main as openapi_dump_main
from factordesk.api.openapi_dump import openapi_text
from factordesk.api.runtime import Runtime
from factordesk.data import factors as factors_module
from factordesk.data.factors import (
    FactorDataError,
    FactorDownloadError,
    FactorStatus,
)
from factordesk.data.prices import PriceDataError, YFinanceProvider
from factordesk.report.schema import (
    RANGE_PRESETS,
    SCHEMA_VERSION,
    ApiError,
    RangeOption,
    RangeOptions,
)
from factordesk.tests.fixtures.dgp import StaticProvider, dgp_a, rng_for

NOW = datetime(2026, 11, 18, 15, 0, tzinfo=UTC)
FIRST = date(2010, 1, 4)
LAST = date(2026, 9, 30)
DOWNLOADED = datetime(2026, 10, 2, 8, 30, tzinfo=UTC)
OPENAPI_FILE = Path(__file__).resolve().parents[3] / "frontend" / "src" / "api" / "openapi.json"


class ApiClient(Protocol):
    """The part of the test client these tests use (its own typing depends on the httpx flavour)."""

    def get(self, url: str, *, headers: dict[str, str] | None = None) -> httpx.Response: ...

    def post(self, url: str) -> httpx.Response: ...


@contextmanager
def serve(app: FastAPI, *, raise_server_exceptions: bool = True) -> Generator[ApiClient]:
    """Run ``app`` (lifespan included) behind a test client."""
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


def make_status(last: date = LAST) -> FactorStatus:
    return FactorStatus(
        last_date=last,
        first_date=FIRST,
        days_behind=(NOW.date() - last).days,
        last_download_at=DOWNLOADED,
        source_url=factors_module.SOURCE_URL,
        stale=(NOW.date() - last).days > factors_module.STALE_AFTER_DAYS,
    )


class FakeFactors:
    """Fake factor store: a status that moves to a new vintage on every refresh."""

    def __init__(self, status: FactorStatus | None = None) -> None:
        self.status: FactorStatus | None = status
        self.frame = pd.DataFrame({"Mkt-RF": [0.0]})
        self.loads: list[bool] = []
        self.error: Exception | None = None
        self.started = threading.Event()
        self.release = threading.Event()
        self.release.set()

    def load(self, refresh: bool, now: datetime) -> pd.DataFrame:
        self.loads.append(refresh)
        self.started.set()
        assert self.release.wait(timeout=10), "test never released the fake download"
        if self.error is not None:
            raise self.error
        if refresh:
            self.status = make_status(date(2026, 10, 31))
        return self.frame

    def read_status(self, now: datetime) -> FactorStatus | None:
        return self.status


def make_deps(
    tmp_path: Path, fake: FakeFactors | None = None, provider: StaticProvider | None = None
) -> tuple[AppDeps, FakeFactors, StaticProvider]:
    fake = fake or FakeFactors(make_status())
    provider = provider or StaticProvider(dgp_a(rng_for(300), n=600).history)
    deps = AppDeps(
        price_provider=provider,
        load_factors=fake.load,
        factor_status=fake.read_status,
        now=lambda: NOW,
        data_dir=tmp_path,
        static_dir=None,
    )
    return deps, fake, provider


@pytest.fixture
def parts(tmp_path: Path) -> tuple[AppDeps, FakeFactors, StaticProvider]:
    return make_deps(tmp_path)


@pytest.fixture
def client(parts: tuple[AppDeps, FakeFactors, StaticProvider]) -> Iterator[ApiClient]:
    with serve(create_app(parts[0])) as test_client:
        yield test_client


def assert_api_error(response: httpx.Response, status: int, code: str) -> ApiError:
    assert response.status_code == status, response.text
    error = ApiError.model_validate(response.json())
    assert error.code == code
    for text in (error.message, error.action):
        assert text.endswith((".", ")"))
        assert "Traceback" not in text
        assert "Error(" not in text
    return error


# --------------------------------------------------------------------------- health


def test_health_reads_no_disk_and_no_provider(
    parts: tuple[AppDeps, FakeFactors, StaticProvider], client: ApiClient
) -> None:
    _, fake, provider = parts
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["schema_version"] == SCHEMA_VERSION
    assert isinstance(body["version"], str) and body["version"]
    assert fake.loads == [] and provider.calls == []


# ------------------------------------------------------------------- factor status


def test_factor_status_reports_coverage_and_age(client: ApiClient) -> None:
    body = client.get("/api/factors/status").json()
    assert body == {
        "available": True,
        "first_date": "2010-01-04",
        "last_date": "2026-09-30",
        "days_behind": 49,
        "last_download_at": "2026-10-02T08:30:00Z",
        "stale": True,
        "source_url": factors_module.SOURCE_URL,
    }


def test_factor_status_when_nothing_is_cached(tmp_path: Path) -> None:
    deps, _, _ = make_deps(tmp_path, FakeFactors(None))
    with serve(create_app(deps)) as client:
        response = client.get("/api/factors/status")
    assert response.status_code == 200
    body = response.json()
    assert body["available"] is False
    assert body["source_url"] == factors_module.SOURCE_URL
    assert all(body[key] is None for key in body if key not in ("available", "source_url"))


# ---------------------------------------------------------------- factor refresh


def test_refresh_forces_a_download_and_returns_the_new_vintage(
    parts: tuple[AppDeps, FakeFactors, StaticProvider], client: ApiClient
) -> None:
    _, fake, _ = parts
    response = client.post("/api/factors/refresh")
    assert response.status_code == 200
    assert response.json()["last_date"] == "2026-10-31"
    assert fake.loads == [True]
    assert client.get("/api/factors/status").json()["last_date"] == "2026-10-31"


def test_refresh_is_single_flight(tmp_path: Path) -> None:
    fake = FakeFactors(make_status())
    fake.release.clear()
    deps, _, _ = make_deps(tmp_path, fake)
    app = create_app(deps)
    runtime: Runtime = app.state.runtime
    results: list[httpx.Response] = []

    with serve(app) as client:

        def call() -> None:
            results.append(client.post("/api/factors/refresh"))

        first = threading.Thread(target=call)
        first.start()
        assert fake.started.wait(timeout=10)
        second = threading.Thread(target=call)
        second.start()
        deadline = time.monotonic() + 10
        while runtime.refresh_joiners < 2 and time.monotonic() < deadline:
            time.sleep(0.01)
        assert runtime.refresh_joiners == 2
        fake.release.set()
        first.join(timeout=10)
        second.join(timeout=10)

        assert fake.loads == [True]
        assert [r.status_code for r in results] == [200, 200]
        assert results[0].json() == results[1].json()
        # the flight is over: the next call starts a new download
        assert client.post("/api/factors/refresh").status_code == 200
        assert fake.loads == [True, True]
        assert runtime.refresh_joiners == 0


def test_failed_refresh_reaches_every_waiter_and_is_not_cached(tmp_path: Path) -> None:
    fake = FakeFactors(make_status())
    fake.error = FactorDownloadError("HTTP 503")
    deps, _, _ = make_deps(tmp_path, fake)
    with serve(create_app(deps)) as client:
        assert_api_error(client.post("/api/factors/refresh"), 503, "network")
        assert client.get("/api/factors/status").json()["last_date"] == "2026-09-30"
        fake.error = None
        assert client.post("/api/factors/refresh").status_code == 200


def test_failed_download_keeps_the_real_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """End to end through the real loader: a failing download leaves the cached file alone."""
    frame = dgp_a(rng_for(301), n=600).factors
    fdir = tmp_path / "factors"
    factors_module._write_cache(fdir, frame, b"zip", None, DOWNLOADED)  # pyright: ignore[reportPrivateUsage]

    def fail(url: str = factors_module.SOURCE_URL) -> tuple[bytes, str | None]:
        raise FactorDownloadError("HTTP 503")

    monkeypatch.setattr(factors_module, "_download", fail)

    def real_load(refresh: bool, now: datetime) -> pd.DataFrame:
        return factors_module.load_ff5_daily(refresh=refresh, data_dir=tmp_path, now=now)

    def real_status(now: datetime) -> FactorStatus | None:
        return factors_module.factor_status(data_dir=tmp_path, now=now)

    deps = dataclasses.replace(
        make_deps(tmp_path)[0], load_factors=real_load, factor_status=real_status
    )
    with serve(create_app(deps)) as client:
        before = client.get("/api/factors/status").json()
        assert before["available"] is True
        assert_api_error(client.post("/api/factors/refresh"), 503, "network")
        assert client.get("/api/factors/status").json() == before


# ------------------------------------------------------------------------- tickers


def write_price_cache(tmp_path: Path, *names: str) -> None:
    price_dir = tmp_path / "prices"
    price_dir.mkdir(parents=True, exist_ok=True)
    for name in names:
        (price_dir / name).write_bytes(b"")


def test_tickers_prefix_match_newest_first(tmp_path: Path) -> None:
    write_price_cache(
        tmp_path,
        "SPY_2026-11-18.parquet",
        "SPXL_2026-11-10.parquet",
        "SPXS_2026-11-17.parquet",
        "AAPL_2026-11-18.parquet",
        "BRK-B_2026-11-01.parquet",
    )
    deps, _, provider = make_deps(tmp_path)
    with serve(create_app(deps)) as client:
        every = client.get("/api/tickers").json()["items"]
        assert [i["ticker"] for i in every] == ["AAPL", "SPY", "SPXS", "SPXL", "BRK-B"]
        assert every[1] == {"ticker": "SPY", "last_fetched": "2026-11-18"}
        assert [i["ticker"] for i in client.get("/api/tickers?q=sp").json()["items"]] == [
            "SPY",
            "SPXS",
            "SPXL",
        ]
        assert len(client.get("/api/tickers?limit=2").json()["items"]) == 2
        assert client.get("/api/tickers?q=zz").json() == {"items": []}
    assert provider.calls == []


def test_tickers_ignore_files_that_are_not_price_caches(tmp_path: Path) -> None:
    write_price_cache(
        tmp_path,
        "SPY_2026-11-18.parquet",
        "SPY_2026-11-01.parquet",
        "notes.txt",
        "bad name_2026-11-18.parquet",
        ".hidden_2026-11-18.parquet",
        "WAYTOOLONGTICKER_2026-11-18.parquet",
        "XYZ_2026-13-45.parquet",
    )
    deps, _, _ = make_deps(tmp_path)
    with serve(create_app(deps)) as client:
        items = client.get("/api/tickers").json()["items"]
    assert items == [{"ticker": "SPY", "last_fetched": "2026-11-18"}]


def test_tickers_without_a_cache_directory_is_empty(client: ApiClient) -> None:
    assert client.get("/api/tickers").json() == {"items": []}


@pytest.mark.parametrize("query", ["q=ABCDEFGHIJKLM", "limit=0", "limit=21", "limit=x"])
def test_tickers_bad_parameters_give_bad_request(client: ApiClient, query: str) -> None:
    assert_api_error(client.get(f"/api/tickers?{query}"), 400, "bad_request")


# --------------------------------------------------------------------- error model


def raising_app(tmp_path: Path, exc: BaseException) -> FastAPI:
    deps, _, _ = make_deps(tmp_path)
    app = create_app(deps)

    @app.get("/api/_raise/{ticker}")
    async def raise_it(ticker: str) -> None:  # pyright: ignore[reportUnusedFunction]
        raise exc

    return app


def yahoo_refusal() -> Exception:
    from yfinance.exceptions import YFRateLimitError  # pyright: ignore[reportMissingTypeStubs]

    return YFRateLimitError()


ERROR_ROWS: list[tuple[Callable[[], BaseException], int, str]] = [
    (lambda: PriceDataError("no data"), 404, "unknown_ticker"),
    (lambda: InsufficientHistoryError(251, 504), 422, "insufficient_history"),
    (lambda: DegenerateInputError("the price does not move"), 422, "degenerate_input"),
    (lambda: FactorDataError("bad header"), 502, "factor_data_invalid"),
    (lambda: FactorDownloadError("HTTP 503"), 503, "network"),
    (lambda: httpx.ConnectError("refused"), 503, "network"),
    (lambda: OSError("disk"), 503, "network"),
    (yahoo_refusal, 503, "upstream_refused"),
    (lambda: ValueError("matrix is singular"), 500, "internal"),
    (lambda: ArithmeticError("overflow"), 500, "internal"),
    (lambda: ApiException("bad_range", "The range is wrong.", "Fix it."), 400, "bad_range"),
]


@pytest.mark.parametrize(("make", "status", "code"), ERROR_ROWS)
def test_domain_exceptions_become_api_errors(
    tmp_path: Path, make: Callable[[], BaseException], status: int, code: str
) -> None:
    app = raising_app(tmp_path, make())
    with serve(app, raise_server_exceptions=False) as client:
        assert_api_error(client.get("/api/_raise/spy"), status, code)


WORDING: list[tuple[BaseException, int, str, str, str]] = [
    (
        InsufficientHistoryError(251, 504),
        422,
        "insufficient_history",
        "SPY has 251 trading days in this range that line up with the factor data; "
        "at least 504 (about two years) are needed.",
        "Choose a longer range or Full history.",
    ),
    (  # validation F14: a single clear cause for zero rows is named
        InsufficientHistoryError(0, 504, "every price in the requested range is missing"),
        422,
        "insufficient_history",
        "SPY has 0 trading days in this range that line up with the factor data; "
        "at least 504 (about two years) are needed: every price in the requested range is "
        "missing.",
        "Choose a longer range or Full history.",
    ),
    (
        DegenerateInputError("the price does not move"),
        422,
        "degenerate_input",
        "Cannot analyse SPY: the price does not move.",
        "Choose another ticker or range.",
    ),
    (
        PriceDataError("x"),
        404,
        "unknown_ticker",
        "No prices were returned for SPY.",
        "Check the ticker symbol.",
    ),
    (
        FactorDataError("x"),
        502,
        "factor_data_invalid",
        "The downloaded factor file failed validation; the previous copy was kept.",
        "Try again later.",
    ),
    (
        FactorDownloadError("x"),
        503,
        "network",
        "factordesk could not reach the data source.",
        "Check your network connection, then try again.",
    ),
    (
        ValueError("matrix is singular\nsecond line"),
        500,
        "internal",
        "The report for SPY could not be computed: matrix is singular.",
        "Try another range. If it happens again, report it with this page's address.",
    ),
]


@pytest.mark.parametrize(("exc", "status", "code", "message", "action"), WORDING)
def test_error_messages_follow_the_spec_wording(
    tmp_path: Path, exc: BaseException, status: int, code: str, message: str, action: str
) -> None:
    with serve(raising_app(tmp_path, exc), raise_server_exceptions=False) as client:
        error = assert_api_error(client.get("/api/_raise/spy"), status, code)
    assert (error.message, error.action) == (message, action)


def test_internal_error_hides_the_traceback(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    app = raising_app(tmp_path, ValueError("boom"))
    with caplog.at_level("ERROR"), serve(app, raise_server_exceptions=False) as client:
        response = client.get("/api/_raise/spy")
    assert "Traceback" not in response.text and "ValueError" not in response.text
    assert any(record.exc_info for record in caplog.records)


def test_invalid_ticker_error_names_the_symbol_and_the_rule() -> None:
    from factordesk.api.errors import check_ticker

    with pytest.raises(ApiException) as caught:
        check_ticker("BRK B")
    error = caught.value.body()
    assert caught.value.status == 422 and error.code == "invalid_ticker"
    assert error.message == "BRK B is not a valid ticker."
    assert error.action == ("Use 1 to 12 letters, digits or . ^ = - (for example SPY or BRK-B).")
    assert check_ticker("brk-b") == "BRK-B"


def test_unknown_api_path_is_a_404_api_error(client: ApiClient) -> None:
    error = assert_api_error(client.get("/api/x"), 404, "not_found")
    assert error.message == "There is no API endpoint at /api/x."
    assert error.action == "Check the address."
    assert_api_error(client.get("/api"), 404, "not_found")
    assert_api_error(client.get("/api/factors/nothing"), 404, "not_found")


def test_wrong_method_is_an_api_error(client: ApiClient) -> None:
    assert_api_error(client.post("/api/health"), 405, "not_found")


def test_paths_outside_api_keep_the_default_404(client: ApiClient) -> None:
    response = client.get("/nothing")
    assert response.status_code == 404
    assert response.json() == {"detail": "Not Found"}


def test_validation_errors_use_the_api_error_body(tmp_path: Path) -> None:
    deps, _, _ = make_deps(tmp_path)
    app = create_app(deps)

    @app.get("/api/_check/{ticker}")
    async def check(ticker: str, start: date | None = None, range: str | None = None) -> None:  # pyright: ignore[reportUnusedFunction]  # noqa: A002
        return None

    with serve(app) as client:
        assert_api_error(client.get("/api/_check/SPY?start=yesterday"), 400, "bad_range")
        assert client.get("/api/_check/SPY?range=3Y").status_code == 200


# ---------------------------------------------------------------- schema and wiring


def test_range_options_models_enforce_their_invariants() -> None:
    ok = RangeOption(preset="3Y", start=date(2023, 9, 30), n_obs=700, available=True, reason=None)
    assert ok.reason is None
    with pytest.raises(ValueError, match="reason"):
        RangeOption(preset="5Y", start=None, n_obs=251, available=False, reason=None)
    with pytest.raises(ValueError, match="reason"):
        RangeOption(preset="5Y", start=None, n_obs=251, available=True, reason="no")

    def option(preset: str) -> RangeOption:
        return RangeOption.model_validate(
            {"preset": preset, "start": None, "n_obs": 1, "available": False, "reason": "short"}
        )

    base: dict[str, Any] = {
        "ticker": "SPY",
        "first_return_date": date(2010, 1, 4),
        "last_price_date": date(2026, 11, 17),
        "factors_last_date": LAST,
        "min_obs": 504,
    }
    RangeOptions(**base, options=[option(p) for p in RANGE_PRESETS])
    with pytest.raises(ValueError, match="preset order"):
        RangeOptions(**base, options=[option(p) for p in reversed(RANGE_PRESETS)])


def test_default_deps_wires_the_real_layer_without_touching_disk(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class StubSettings:
        data_dir = Path("relative-data")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(deps_module, "get_settings", lambda: StubSettings())
    deps = default_deps(None)
    assert deps.data_dir.is_absolute() and deps.data_dir == (tmp_path / "relative-data").resolve()
    assert isinstance(deps.price_provider, YFinanceProvider)
    assert deps.price_provider.cache_dir == deps.data_dir / "prices"
    assert deps.now().tzinfo is not None
    assert list(tmp_path.iterdir()) == []
    app = create_dev_app()
    with serve(app) as client:
        assert client.get("/api/health").status_code == 200
        assert client.get("/api/factors/status").json()["available"] is False
        assert client.get("/api/tickers").json() == {"items": []}
    assert list(tmp_path.iterdir()) == []


def test_deps_reject_nonsense_limits(tmp_path: Path) -> None:
    deps, _, _ = make_deps(tmp_path)
    with pytest.raises(ValueError, match="max_workers"):
        dataclasses.replace(deps, max_workers=0)
    with pytest.raises(ValueError, match="report_cache_size"):
        dataclasses.replace(deps, report_cache_size=0)


def test_no_cors_middleware(client: ApiClient) -> None:
    response = client.get("/api/health", headers={"Origin": "http://evil.example"})
    assert "access-control-allow-origin" not in response.headers


def test_openapi_dump_writes_the_document(tmp_path: Path) -> None:
    out = tmp_path / "nested" / "openapi.json"
    assert openapi_dump_main([str(out)]) == 0
    assert out.read_text(encoding="utf-8") == openapi_text()
    document = json.loads(out.read_text(encoding="utf-8"))
    assert {"/api/health", "/api/factors/status", "/api/factors/refresh", "/api/tickers"} <= set(
        document["paths"]
    )
    assert openapi_dump_main([]) == 2


@pytest.mark.skipif(
    not OPENAPI_FILE.exists(), reason="frontend/src/api/openapi.json is not generated yet"
)
def test_openapi_is_current(parts: tuple[AppDeps, FakeFactors, StaticProvider]) -> None:
    committed = json.loads(OPENAPI_FILE.read_text(encoding="utf-8"))
    assert committed == create_app(parts[0]).openapi()
