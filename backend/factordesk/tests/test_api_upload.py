"""``POST /api/report/upload``: happy path, every refusal, the 1 MB cap and privacy (E0-T3).

Offline: the monthly factor loader is replaced by a synthetic French-shaped frame, the clock is
fixed and ``tmp_path`` is the data folder.
"""

from __future__ import annotations

import codecs
import socket
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol, cast

import httpx
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from factordesk.api import routes_upload
from factordesk.data.upload import MAX_UPLOAD_BYTES
from factordesk.report.schema import ApiError, FactorReport
from factordesk.tests.test_api_report import NOW, World, make_world
from factordesk.tests.test_subject import monthly_case

DOWNLOADED = datetime(2026, 10, 2, 8, 30, tzinfo=UTC)


class ApiClient(Protocol):
    def post(self, url: str, **kwargs: Any) -> httpx.Response: ...

    def get(self, url: str) -> httpx.Response: ...


@pytest.fixture(autouse=True)
def _no_network(monkeypatch: pytest.MonkeyPatch) -> None:  # pyright: ignore[reportUnusedFunction]
    real_connect = socket.socket.connect

    def refuse(self: socket.socket, address: Any) -> None:
        if isinstance(address, tuple) and cast(tuple[object, ...], address)[0] in (
            "127.0.0.1",
            "::1",
        ):
            real_connect(self, cast(tuple[object, ...], address))
            return
        raise AssertionError(f"network access attempted: {address!r}")

    monkeypatch.setattr(socket.socket, "connect", refuse)


def csv_of(returns: pd.Series, header: str = "date,return") -> bytes:
    lines = [header] + [f"{d:%Y-%m-%d},{v!r}" for d, v in returns.items()]
    return ("\n".join(lines) + "\n").encode()


@pytest.fixture
def factors(monkeypatch: pytest.MonkeyPatch) -> pd.DataFrame:
    _, frame, _ = monthly_case(72, 11, extra_factor_months=6)
    frame.attrs = {"downloaded_at": DOWNLOADED.isoformat()}

    def load(**_kw: object) -> pd.DataFrame:
        return frame

    monkeypatch.setattr(routes_upload, "load_ff5_monthly", load)
    return frame


@pytest.fixture
def returns() -> pd.Series:
    return monthly_case(72, 11)[0]


@pytest.fixture
def world(tmp_path: Path) -> World:
    return make_world(tmp_path)


@pytest.fixture
def client(world: World, factors: pd.DataFrame) -> Iterator[ApiClient]:
    with TestClient(world.app) as test_client:  # pyright: ignore[reportUnknownVariableType]
        yield cast(ApiClient, test_client)


def post(
    client: ApiClient,
    body: bytes,
    *,
    name: str | None = None,
    gross_net: str | None = None,
) -> httpx.Response:
    data: dict[str, str] = {}
    if name is not None:
        data["name"] = name
    if gross_net is not None:
        data["gross_net"] = gross_net
    return client.post(
        "/api/report/upload",
        files={"file": ("record.csv", body, "text/csv")},
        data=data,
    )


def refused(response: httpx.Response, status: int, code: str) -> ApiError:
    assert response.status_code == status, response.text
    error = ApiError.model_validate(response.json())
    assert error.code == code
    assert error.message and error.action
    assert "Traceback" not in response.text
    return error


# ------------------------------------------------------------------------- happy path
def test_upload_gives_a_monthly_report(client: ApiClient, returns: pd.Series) -> None:
    response = post(client, csv_of(returns), name="Example Fund", gross_net="net")
    assert response.status_code == 200, response.text
    report = FactorReport.model_validate_json(response.text)
    assert report.ticker == "Example Fund"
    assert report.subject is not None
    assert report.subject.kind == "upload"
    assert report.subject.frequency == "monthly"
    assert report.subject.periods == 12
    assert report.subject.gross_net == "net"
    assert report.subject.currency == "USD"
    assert report.regression is not None
    assert report.regression.sample.n == 72
    assert all(w.status == "not_applicable" for w in report.rolling)
    assert report.average_beta.status == "not_applicable"
    assert report.world_beta is None and report.kalman_betas is None
    assert report.data.factors_downloaded_at == DOWNLOADED


def test_upload_name_and_gross_net_are_optional(client: ApiClient, returns: pd.Series) -> None:
    report = FactorReport.model_validate_json(post(client, csv_of(returns)).text)
    assert report.ticker == "Uploaded track record"
    assert report.subject is not None and report.subject.gross_net is None


def test_upload_accepts_year_month_dates_semicolons_and_a_bom(
    client: ApiClient, returns: pd.Series
) -> None:
    lines = ["date;return"] + [f"{d:%Y-%m};{v!r}" for d, v in returns.items()]
    body = codecs.BOM_UTF8 + "\n".join(lines).encode("utf-8")
    assert post(client, body).status_code == 200


def test_upload_route_is_registered_before_the_ticker_route(world: World) -> None:
    paths = list(world.app.openapi()["paths"])
    assert paths.index("/api/report/upload") < paths.index("/api/report/{ticker}")


# --------------------------------------------------------------------------- refusals
def months(error: ApiError) -> bool:
    return "months" in error.message and "trading days" not in error.message


def test_refuses_fewer_than_36_months_in_months(client: ApiClient, returns: pd.Series) -> None:
    error = refused(post(client, csv_of(returns.iloc[:30])), 422, "insufficient_history")
    assert months(error)
    assert "36" in error.message and "30" in error.message


def test_refuses_a_gap(client: ApiClient, returns: pd.Series) -> None:
    error = refused(post(client, csv_of(returns.drop(returns.index[20]))), 422, "invalid_upload")
    assert "consecutive" in error.message and str(returns.index[20].year) in error.message


def test_refuses_a_repeated_month(client: ApiClient, returns: pd.Series) -> None:
    body = csv_of(returns) + f"{returns.index[-1]:%Y-%m-%d},0.01\n".encode()
    error = refused(post(client, body), 422, "invalid_upload")
    assert "more than one return" in error.message


def test_refuses_a_missing_return(client: ApiClient, returns: pd.Series) -> None:
    lines = csv_of(returns).decode().splitlines()
    lines[5] = lines[5].split(",")[0] + ","
    refused(post(client, ("\n".join(lines) + "\n").encode()), 422, "invalid_upload")


@pytest.mark.parametrize("token", ["nan", "inf", "-inf", "abc", "1.2%"])
def test_refuses_a_return_that_is_not_a_decimal(
    client: ApiClient, returns: pd.Series, token: str
) -> None:
    lines = csv_of(returns).decode().splitlines()
    lines[5] = lines[5].split(",")[0] + "," + token
    error = refused(post(client, ("\n".join(lines) + "\n").encode()), 422, "invalid_upload")
    assert "line 6" in error.message


@pytest.mark.parametrize("value", ["-1.0", "-1.5"])
def test_refuses_a_return_at_or_below_minus_100_percent(
    client: ApiClient, returns: pd.Series, value: str
) -> None:
    lines = csv_of(returns).decode().splitlines()
    lines[5] = lines[5].split(",")[0] + "," + value
    error = refused(post(client, ("\n".join(lines) + "\n").encode()), 422, "invalid_upload")
    assert "-100%" in error.message


def test_refuses_a_mid_month_date(client: ApiClient, returns: pd.Series) -> None:
    lines = csv_of(returns).decode().splitlines()
    day = returns.index[4]
    lines[5] = f"{day:%Y-%m}-15," + lines[5].split(",")[1]
    lines[9] = f"{returns.index[8]:%Y-%m}-10," + lines[9].split(",")[1]
    error = refused(post(client, ("\n".join(lines) + "\n").encode()), 422, "invalid_upload")
    assert f"{day:%Y-%m}-15 is not in the last 7 days of its month" in error.message
    assert f"{day:%Y-%m-%d}" in error.message  # the month-end to use instead
    assert f"{returns.index[8]:%Y-%m}-10" not in error.message


@pytest.mark.parametrize(
    "body",
    [
        b"",
        b"date,return\n",
        b"when,what\n2020-01-31,0.01\n",
        b"date,return,extra\n2020-01-31,0.01,1\n",
        b"date,return\nnot-a-date,0.01\n",
        b"date,return\n2020-01-31,0.01,5\n",
        b"\xff\xfe\x00\x01",
    ],
    ids=["empty", "header_only", "wrong_header", "extra_column", "bad_date", "wide_row", "binary"],
)
def test_refuses_a_malformed_file(client: ApiClient, body: bytes) -> None:
    refused(post(client, body), 422, "invalid_upload")


def test_refuses_a_bad_gross_net(client: ApiClient, returns: pd.Series) -> None:
    error = refused(post(client, csv_of(returns), gross_net="maybe"), 422, "invalid_upload")
    assert "gross" in error.message


def test_refuses_a_request_without_a_file(client: ApiClient) -> None:
    assert client.post("/api/report/upload", data={"name": "x"}).status_code == 400


# ----------------------------------------------------------------------------- size cap
def test_refuses_more_than_1_mb_by_content_length(
    client: ApiClient, returns: pd.Series, monkeypatch: pytest.MonkeyPatch
) -> None:
    read: list[int] = []
    real = routes_upload.UploadFile.read

    async def spy(self: Any, size: int = -1) -> bytes:
        read.append(size)
        return await real(self, size)

    monkeypatch.setattr(routes_upload.UploadFile, "read", spy)
    big = csv_of(returns) + b"#" * MAX_UPLOAD_BYTES
    error = refused(post(client, big), 413, "upload_too_large")
    assert "1 MB" in error.message
    assert read == []  # refused before the handler read anything


def test_cap_applies_without_a_content_length(client: ApiClient, returns: pd.Series) -> None:
    def chunks() -> Iterator[bytes]:
        yield b'--b\r\nContent-Disposition: form-data; name="file"; filename="r.csv"\r\n\r\n'
        for _ in range(3):
            yield b"#" * MAX_UPLOAD_BYTES
        yield b"\r\n--b--\r\n"

    response = client.post(
        "/api/report/upload",
        content=chunks(),
        headers={"content-type": "multipart/form-data; boundary=b"},
    )
    refused(response, 413, "upload_too_large")


def test_a_file_just_under_the_cap_is_read(client: ApiClient, returns: pd.Series) -> None:
    padded = csv_of(returns) + b"\n" * (MAX_UPLOAD_BYTES - 4096 - len(csv_of(returns)))
    assert post(client, padded).status_code == 200


# --------------------------------------------------------------------------- privacy
def listing(root: Path) -> list[tuple[str, int, int]]:
    return sorted(
        (str(p.relative_to(root)), p.stat().st_size, p.stat().st_mtime_ns) for p in root.rglob("*")
    )


def cache_state(world: World) -> list[tuple[str, int, int, int, list[Any]]]:
    s = world.service
    layers = (s.factors, s.prices, s.ranges, s.reports, s.securities, s.inputs)
    return [(type(x).__name__, len(x), x.started, x.hits, x.keys()) for x in layers]


def test_upload_leaves_the_data_folder_and_the_report_caches_untouched(
    client: ApiClient, world: World, returns: pd.Series, tmp_path: Path
) -> None:
    (tmp_path / "factors").mkdir()
    (tmp_path / "factors" / "kept.txt").write_text("existing")
    before_files, before_caches = listing(tmp_path), cache_state(world)
    assert post(client, csv_of(returns), name="Secret Fund").status_code == 200
    assert post(client, csv_of(returns.iloc[:10])).status_code == 422
    assert listing(tmp_path) == before_files
    assert cache_state(world) == before_caches
    assert world.provider.threads == []  # no price lookup either
    assert NOW  # the clock is fixed, so nothing here depends on the day


def test_the_committed_monthly_report_fixture_matches_the_schema() -> None:
    path = Path(__file__).parent / "fixtures" / "monthly_report.json"
    report = FactorReport.model_validate_json(path.read_text(encoding="utf-8"))
    assert report.subject is not None and report.subject.frequency == "monthly"
    assert report.subject.gross_net == "net"
