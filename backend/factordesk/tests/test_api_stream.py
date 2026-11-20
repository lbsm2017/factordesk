"""Progress streams (S4-5): ``GET /api/report/{ticker}/stream``, ``POST .../portfolio/stream`` and
``POST .../upload/stream``.

Offline, on the fakes of the report, portfolio and currency tests. The events are parsed from the
body of the finished stream.
"""

from __future__ import annotations

import asyncio
import json
import socket
import threading
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any, cast

import httpx
import pandas as pd
import pytest

from factordesk import progress
from factordesk.api import routes_stream, routes_upload
from factordesk.api import service as service_module
from factordesk.data.prices import PriceDataError
from factordesk.report.schema import ApiErrorEvent, FactorReport, ProgressStep
from factordesk.tests import test_api_portfolio as portfolio_tests
from factordesk.tests import test_api_report as report_tests
from factordesk.tests.test_api_upload import csv_of
from factordesk.tests.test_currency_view import FAKE, eur_tree, with_sources
from factordesk.tests.test_subject import monthly_case

USD_STEPS = ["prices", "factors", "models", "sections"]
EUR_STEPS = ["prices", "fx", "factors", "models", "sections"]


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


def events_of(response: httpx.Response) -> list[tuple[str, Any]]:
    """The ``(event name, data)`` pairs of a finished stream; comment lines are skipped."""
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("text/event-stream")
    return parse_events(response.text)


def parse_events(text: str) -> list[tuple[str, Any]]:
    out: list[tuple[str, Any]] = []
    for block in text.split("\n\n"):
        lines = [line for line in block.split("\n") if line and not line.startswith(":")]
        if not lines:
            continue
        assert lines[0].startswith("event: ") and lines[1].startswith("data: "), block
        assert len(lines) == 2, block  # the data is one line
        out.append((lines[0].removeprefix("event: "), json.loads(lines[1].removeprefix("data: "))))
    return out


def names(events: list[tuple[str, Any]]) -> list[str]:
    return [name for name, _ in events]


def step_ids(events: list[tuple[str, Any]]) -> list[str]:
    return [data["step"] for name, data in events if name == "step"]


def check_steps(events: list[tuple[str, Any]], expected: list[str]) -> None:
    steps = [ProgressStep.model_validate(data) for name, data in events if name == "step"]
    assert [s.step for s in steps] == expected
    assert [s.index for s in steps] == list(range(1, len(expected) + 1))
    assert {s.total for s in steps} == {len(expected)}
    assert all(s.label for s in steps)
    assert names(events) == ["step"] * len(expected) + ["report"]


def labels(events: list[tuple[str, Any]]) -> dict[str, str]:
    return {data["step"]: data["label"] for name, data in events if name == "step"}


# --------------------------------------------------------------------------- the reporter


def test_the_default_reporter_does_nothing() -> None:
    progress.step("models")  # no reporter installed: no error and no effect


def test_the_step_reporter_sends_each_step_once_in_order_and_catches_up() -> None:
    sent: list[ProgressStep] = []
    reporter = progress.StepReporter(progress.plan_of(), sent.append)
    reporter.step("factors")  # prices was not announced: it goes first
    reporter.step("factors")
    reporter.step("prices")
    reporter.step("fx")  # not in this plan
    reporter.step("sections")
    assert [s.step for s in sent] == ["prices", "factors", "models", "sections"]
    assert [s.index for s in sent] == [1, 2, 3, 4]
    assert {s.total for s in sent} == {4}


def test_plans() -> None:
    assert progress.plan_of() == USD_STEPS
    assert progress.plan_of(fx=True) == EUR_STEPS
    assert progress.plan_of(prices=False) == ["factors", "models", "sections"]


# --------------------------------------------------------------------------- ticker


def test_usd_steps_come_in_order_then_the_report(tmp_path: Path) -> None:
    w = report_tests.make_world(tmp_path)
    with report_tests.serve(w.app) as c:
        events = events_of(cast(Any, c).get("/api/report/SYN/stream"))
    check_steps(events, USD_STEPS)
    assert labels(events) == {
        "prices": "Downloading prices",
        "factors": "Loading factor data",
        "models": "Fitting the models",
        "sections": "Building the sections",
    }
    FactorReport.model_validate_json(json.dumps(events[-1][1]))


def test_eur_steps_include_the_exchange_rates(tmp_path: Path) -> None:
    w = report_tests.make_world(tmp_path)
    with_sources(cast(Any, w), FAKE)
    with report_tests.serve(w.app) as c:
        events = events_of(cast(Any, c).get("/api/report/SYN/stream?ccy=EUR"))
    check_steps(events, EUR_STEPS)
    assert labels(events)["fx"] == "Loading exchange rates"


def test_the_report_event_equals_the_plain_endpoint(tmp_path: Path) -> None:
    w = report_tests.make_world(tmp_path)
    query = "?range=3Y&model=ff5"
    with report_tests.serve(w.app) as c:
        streamed = events_of(cast(Any, c).get(f"/api/report/SYN/stream{query}"))
        plain = cast(Any, c).get(f"/api/report/SYN{query}")
    assert plain.status_code == 200
    assert streamed[-1][0] == "report"
    assert streamed[-1][1] == plain.json()


def test_a_cached_report_sends_only_the_report(tmp_path: Path) -> None:
    w = report_tests.make_world(tmp_path)
    with report_tests.serve(w.app) as c:
        first = events_of(cast(Any, c).get("/api/report/SYN/stream"))
        again = events_of(cast(Any, c).get("/api/report/SYN/stream"))
        plain = cast(Any, c).get("/api/report/SYN")
    assert names(first) == ["step"] * 4 + ["report"]
    assert names(again) == ["report"]
    assert again[0][1] == first[-1][1] == plain.json()


def test_a_report_that_is_not_cached_still_shows_every_step_when_the_prices_are_warm(
    tmp_path: Path,
) -> None:
    w = report_tests.make_world(tmp_path)
    with report_tests.serve(w.app) as c:
        assert cast(Any, c).get("/api/report/SYN?range=5Y").status_code == 200
        events = events_of(cast(Any, c).get("/api/report/SYN/stream?range=3Y"))
    check_steps(events, USD_STEPS)


def test_an_unknown_ticker_sends_an_error_with_the_status(tmp_path: Path) -> None:
    w = report_tests.make_world(tmp_path)
    w.provider.error = PriceDataError("no data for ZZZ")
    with report_tests.serve(w.app) as c:
        streamed = events_of(cast(Any, c).get("/api/report/ZZZ/stream"))
        plain = cast(Any, c).get("/api/report/ZZZ")
    assert names(streamed)[-1] == "error"
    assert names(streamed).count("error") == 1 and "report" not in names(streamed)
    error = ApiErrorEvent.model_validate(streamed[-1][1])
    assert error.status == plain.status_code == 404
    assert error.code == "unknown_ticker"
    assert {k: v for k, v in streamed[-1][1].items() if k != "status"} == plain.json()


def test_an_invalid_ticker_sends_an_error_event(tmp_path: Path) -> None:
    w = report_tests.make_world(tmp_path)
    with report_tests.serve(w.app) as c:
        events = events_of(cast(Any, c).get("/api/report/bad%21ticker/stream"))
    assert names(events) == ["error"]
    assert events[0][1]["code"] == "invalid_ticker" and events[0][1]["status"] == 422


def test_a_bad_range_sends_an_error_event(tmp_path: Path) -> None:
    w = report_tests.make_world(tmp_path)
    with report_tests.serve(w.app) as c:
        events = events_of(cast(Any, c).get("/api/report/SYN/stream?range=3Y&start=2020-01-02"))
    assert events[-1][0] == "error"
    assert events[-1][1]["code"] == "bad_range" and events[-1][1]["status"] == 400


def test_a_request_the_framework_refuses_is_the_plain_http_error(tmp_path: Path) -> None:
    w = report_tests.make_world(tmp_path)
    with report_tests.serve(w.app) as c:
        response = cast(Any, c).get("/api/report/SYN/stream?start=not-a-date")
    assert response.status_code == 400
    assert response.json()["code"] == "bad_range"


def test_the_plain_endpoint_is_json_and_sends_no_steps(tmp_path: Path) -> None:
    w = report_tests.make_world(tmp_path)
    with report_tests.serve(w.app) as c:
        plain = cast(Any, c).get("/api/report/SYN")
    assert plain.headers["content-type"] == "application/json"
    assert plain.json()["ticker"] == "SYN"


def test_a_comment_line_keeps_a_slow_step_alive(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(routes_stream, "KEEP_ALIVE_SECONDS", 0.05)
    w = report_tests.make_world(tmp_path)
    w.provider.release.clear()
    timer = threading.Timer(0.4, w.provider.release.set)
    timer.start()
    try:
        with report_tests.serve(w.app) as c:
            response = cast(Any, c).get("/api/report/SYN/stream")
    finally:
        timer.cancel()
        w.provider.release.set()
    assert ": keep-alive\n\n" in response.text
    check_steps(events_of(response), USD_STEPS)


# --------------------------------------------------------------------------- portfolio


def test_a_portfolio_streams_its_steps_and_the_plain_report(tmp_path: Path) -> None:
    w = portfolio_tests.make_world(tmp_path)
    body = portfolio_tests.tree([portfolio_tests.holding(0, "AAA", 0.6)])
    with report_tests.serve(w.app) as c:
        post = cast(Any, c).post
        streamed = events_of(post("/api/report/portfolio/stream", json=body))
        again = events_of(post("/api/report/portfolio/stream", json=body))
        plain = post("/api/report/portfolio", json=body)
    check_steps(streamed, USD_STEPS)
    assert streamed[-1][1] == plain.json()
    assert names(again) == ["report"]


def test_an_eur_portfolio_has_the_exchange_rate_step(tmp_path: Path) -> None:
    w = portfolio_tests.make_world(tmp_path)
    with_sources(cast(Any, w), FAKE)
    body = eur_tree([portfolio_tests.holding(0, "AAA", 0.6)])
    with report_tests.serve(w.app) as c:
        events = events_of(cast(Any, c).post("/api/report/portfolio/stream", json=body))
    check_steps(events, EUR_STEPS)


def test_a_portfolio_that_is_not_valid_is_the_plain_http_error(tmp_path: Path) -> None:
    w = portfolio_tests.make_world(tmp_path)
    body = portfolio_tests.tree([portfolio_tests.holding(0, "AAA", 1.5)])
    with report_tests.serve(w.app) as c:
        post = cast(Any, c).post
        streamed = post("/api/report/portfolio/stream", json=body)
        plain = post("/api/report/portfolio", json=body)
    assert streamed.status_code == plain.status_code == 422
    assert streamed.json() == plain.json()


def test_a_portfolio_with_an_unknown_ticker_sends_an_error(tmp_path: Path) -> None:
    w = portfolio_tests.make_world(tmp_path)
    body = portfolio_tests.tree([portfolio_tests.holding(0, "NOPE", 0.5)])
    with report_tests.serve(w.app) as c:
        post = cast(Any, c).post
        events = events_of(post("/api/report/portfolio/stream", json=body))
        plain = post("/api/report/portfolio", json=body)
    assert events[-1][0] == "error"
    assert events[-1][1]["status"] == plain.status_code == 422


# --------------------------------------------------------------------------- upload


@pytest.fixture
def monthly(monkeypatch: pytest.MonkeyPatch) -> pd.Series:
    returns, frame, _ = monthly_case(72, 11)
    frame.attrs = {}

    def load(*_args: object, **_kw: object) -> pd.DataFrame:
        return frame

    monkeypatch.setattr(routes_upload, "load_ff6", load)
    monkeypatch.setattr(routes_upload, "load_ff5_monthly", load)
    return returns


def test_an_upload_streams_steps_without_prices_and_the_plain_report(
    tmp_path: Path, monthly: pd.Series
) -> None:
    w = report_tests.make_world(tmp_path)
    files = {"file": ("r.csv", csv_of(monthly), "text/csv")}
    with report_tests.serve(w.app) as c:
        post = cast(Any, c).post
        streamed = events_of(post("/api/report/upload/stream", files=files, data={"name": "F"}))
        plain = post("/api/report/upload", files=files, data={"name": "F"})
    check_steps(streamed, ["factors", "models", "sections"])
    assert streamed[-1][1] == plain.json()


def test_an_eur_upload_has_the_exchange_rate_step(tmp_path: Path, monthly: pd.Series) -> None:
    w = report_tests.make_world(tmp_path)
    with_sources(cast(Any, w), FAKE)
    files = {"file": ("r.csv", csv_of(monthly), "text/csv")}
    with report_tests.serve(w.app) as c:
        events = events_of(
            cast(Any, c).post(
                "/api/report/upload/stream",
                files=files,
                data={"ccy": "EUR", "record_currency": "EUR"},
            )
        )
    check_steps(events, ["fx", "factors", "models", "sections"])


def test_a_bad_upload_sends_an_error_and_a_missing_file_is_the_plain_error(
    tmp_path: Path, monthly: pd.Series
) -> None:
    w = report_tests.make_world(tmp_path)
    with report_tests.serve(w.app) as c:
        post = cast(Any, c).post
        bad = events_of(
            post("/api/report/upload/stream", files={"file": ("r.csv", b"nonsense", "text/csv")})
        )
        missing = post("/api/report/upload/stream", data={"name": "F"})
        big = post(
            "/api/report/upload/stream",
            files={"file": ("r.csv", b"x" * (1024 * 1024 + 10), "text/csv")},
        )
    assert bad[-1][0] == "error"
    assert bad[-1][1]["code"] == "invalid_upload" and bad[-1][1]["status"] == 422
    assert missing.status_code == 400 and missing.json()["code"] == "bad_request"
    assert big.status_code == 413


# --------------------------------------------------------------------------- robustness


async def collect(events: AsyncIterator[str]) -> list[tuple[str, Any]]:
    return parse_events("".join([chunk async for chunk in events]))


def test_the_stream_headers_stop_caching_and_proxy_buffering(tmp_path: Path) -> None:
    w = report_tests.make_world(tmp_path)
    with report_tests.serve(w.app) as c:
        response = cast(Any, c).get("/api/report/SYN/stream")
    assert response.headers["cache-control"] == "no-cache"
    assert response.headers["x-accel-buffering"] == "no"


def test_an_unexpected_error_is_an_internal_event_with_a_fixed_message(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(*_args: object, **_kw: object) -> FactorReport:
        raise RuntimeError("secret detail")

    monkeypatch.setattr(service_module, "assemble_report", broken)
    w = report_tests.make_world(tmp_path)
    with report_tests.serve(w.app) as c:
        response = cast(Any, c).get("/api/report/SYN/stream")
    events = events_of(response)
    assert names(events)[-1] == "error" and "report" not in names(events)
    error = ApiErrorEvent.model_validate(events[-1][1])
    assert error.code == "internal" and error.status == 500
    assert error.message == routes_stream.INTERNAL_MESSAGE
    assert "secret detail" not in response.text


def test_two_streams_at_once_do_not_cross_their_events(tmp_path: Path) -> None:
    w = report_tests.make_world(tmp_path)
    with_sources(cast(Any, w), FAKE)

    async def go() -> tuple[list[tuple[str, Any]], list[tuple[str, Any]]]:
        async def usd() -> FactorReport:
            return await w.service.report("SYN", ccy="USD")

        async def eur() -> FactorReport:
            return await w.service.report("SYN", ccy="EUR")

        return await asyncio.gather(
            collect(routes_stream._events(progress.plan_of(), usd, "SYN")),  # pyright: ignore[reportPrivateUsage]
            collect(routes_stream._events(progress.plan_of(fx=True), eur, "SYN")),  # pyright: ignore[reportPrivateUsage]
        )

    usd_events, eur_events = asyncio.run(go())
    assert step_ids(usd_events) == USD_STEPS and names(usd_events)[-1] == "report"
    assert step_ids(eur_events) == EUR_STEPS and names(eur_events)[-1] == "report"
    assert {d["total"] for n, d in usd_events if n == "step"} == {4}
    assert {d["total"] for n, d in eur_events if n == "step"} == {5}


def test_a_client_that_leaves_cancels_its_stream_but_the_cache_is_still_filled(
    tmp_path: Path,
) -> None:
    w = report_tests.make_world(tmp_path)
    inside, gate = threading.Event(), threading.Event()

    def slow_inputs(_now: object) -> None:
        inside.set()
        assert gate.wait(timeout=20)

    object.__setattr__(w.service.deps, "load_section_inputs", slow_inputs)
    seen: dict[str, asyncio.Task[Any]] = {}

    async def go() -> None:
        async def run() -> FactorReport:
            task = asyncio.current_task()
            assert task is not None
            seen["work"] = task
            return await w.service.report("SYN")

        events = routes_stream._events(progress.plan_of(), run, "SYN")  # pyright: ignore[reportPrivateUsage]
        await anext(events)
        while not inside.is_set():
            await asyncio.sleep(0.01)
        await events.aclose()  # what the server does when the client disconnects
        await asyncio.sleep(0.05)
        assert seen["work"].cancelled()
        assert len(w.service.reports) == 0
        gate.set()
        for _ in range(500):
            if len(w.service.reports) == 1:
                return
            await asyncio.sleep(0.02)

    try:
        asyncio.run(go())
    finally:
        gate.set()
    assert len(w.service.reports) == 1


def test_a_slow_factor_load_shows_the_factor_step_before_it_ends(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(service_module, "SLOW_FACTORS_SECONDS", 0.05)
    w = report_tests.make_world(tmp_path)
    inside, gate = threading.Event(), threading.Event()
    real_load = w.factors.load

    def slow_load(refresh: bool, now: Any) -> pd.DataFrame:
        inside.set()
        assert gate.wait(timeout=20)
        return real_load(refresh, now)

    object.__setattr__(w.service.deps, "load_factors", slow_load)

    async def go() -> tuple[list[str], list[tuple[str, Any]]]:
        async def run() -> FactorReport:
            return await w.service.report("SYN")

        events = routes_stream._events(progress.plan_of(), run, "SYN")  # pyright: ignore[reportPrivateUsage]
        early = [await anext(events), await anext(events)]
        assert inside.is_set() and not gate.is_set()  # the load is still running
        gate.set()
        rest = [chunk async for chunk in events]
        return early, parse_events("".join(early + rest))

    try:
        early, events = asyncio.run(go())
    finally:
        gate.set()
    assert [parse_events(chunk)[0][1]["step"] for chunk in early] == ["prices", "factors"]
    check_steps(events, USD_STEPS)
