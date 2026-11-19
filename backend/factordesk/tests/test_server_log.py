"""The server logs one INFO line per step, and never an upload's contents or names (S2-1)."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import cast

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from factordesk.tests.test_api_report import World, make_world, serve
from factordesk.tests.test_api_report import _no_network as _no_network  # pyright: ignore[reportPrivateUsage]
from factordesk.tests.test_api_upload import ApiClient as UploadClient
from factordesk.tests.test_api_upload import csv_of, post
from factordesk.tests.test_api_upload import factors as factors  # pyright: ignore[reportUnusedImport]
from factordesk.tests.test_api_upload import returns as returns  # pyright: ignore[reportUnusedImport]

_ = _no_network


def _lines(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [r.getMessage() for r in caplog.records if r.name.startswith("factordesk")]


def _has(lines: list[str], *needles: str) -> bool:
    return any(all(n in line for n in needles) for line in lines)


@pytest.fixture
def world(tmp_path: Path) -> World:
    return make_world(tmp_path)


def test_a_report_logs_every_step_with_its_timing(
    world: World, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.INFO, logger="factordesk"), serve(world.app) as client:
        assert client.get("/api/report/SPY?range=FULL").status_code == 200
    lines = _lines(caplog)
    assert _has(lines, "Report start", "SPY", "ff5", "FULL")
    assert _has(lines, "Prices SPY", "days", " s")
    assert _has(lines, "Prices SPY", "downloaded") or _has(lines, "Prices SPY", "from cache")
    assert _has(lines, "Factors:", "Fama-French", "vintage")
    assert _has(lines, "Sections built:", " s")
    assert _has(lines, "Report built", "SPY", "total", " s")


def test_a_second_request_logs_a_cache_hit_with_its_milliseconds(
    world: World, caplog: pytest.LogCaptureFixture
) -> None:
    with serve(world.app) as client:
        assert client.get("/api/report/SPY?range=FULL").status_code == 200
        caplog.clear()
        with caplog.at_level(logging.INFO, logger="factordesk"):
            assert client.get("/api/report/SPY?range=FULL").status_code == 200
    lines = _lines(caplog)
    assert _has(lines, "Report cache hit", "SPY", " ms)")
    assert not _has(lines, "Sections built")


def test_a_refusal_logs_its_reason_category(world: World, caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO, logger="factordesk"), serve(world.app) as client:
        assert client.get("/api/report/SPY?start=2030-01-01&end=2030-02-01").status_code == 400
    assert _has(_lines(caplog), "Report refused", "SPY", "reason bad_range")


def test_a_slow_section_is_named(
    world: World, caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    from factordesk.section_hooks import registry

    ticks = iter(float(i) * 2.0 for i in range(1000))
    monkeypatch.setattr(registry.time, "perf_counter", lambda: next(ticks))
    with caplog.at_level(logging.INFO, logger="factordesk"), serve(world.app) as client:
        assert client.get("/api/report/SPY?range=FULL").status_code == 200
    assert _has(_lines(caplog), "Slow section performance")


def test_an_upload_logs_rows_frequency_and_timing_but_no_content(
    world: World,
    factors: pd.DataFrame,
    returns: pd.Series,
    caplog: pytest.LogCaptureFixture,
) -> None:
    secret_name = "Zebra Secret Fund 4711"
    body = csv_of(returns)
    with caplog.at_level(logging.DEBUG), TestClient(world.app) as client:
        response = post(cast(UploadClient, client), body, name=secret_name, gross_net="net")
    assert response.status_code == 200, response.text
    lines = _lines(caplog)
    assert _has(lines, "Upload report built", f"{len(returns)} rows", "monthly", " s")
    everything = "\n".join(r.getMessage() for r in caplog.records)
    assert secret_name not in everything and "Zebra" not in everything
    assert "record.csv" not in everything
    assert "date,return" not in everything
    for value in list(returns.astype(str))[:5]:
        assert value not in everything
    for stamp in returns.index[:3]:
        assert f"{stamp:%Y-%m-%d}" not in everything


def test_a_refused_upload_logs_only_the_category(
    world: World, factors: pd.DataFrame, caplog: pytest.LogCaptureFixture
) -> None:
    bad = b"date,return\nsecret-marker-xyz,not-a-number\n"
    with caplog.at_level(logging.DEBUG), TestClient(world.app) as client:
        response = post(cast(UploadClient, client), bad, name="Hidden Name")
    assert response.status_code == 422
    everything = "\n".join(r.getMessage() for r in caplog.records)
    assert "Upload refused" in everything and "invalid_upload" in everything
    assert "secret-marker-xyz" not in everything and "Hidden Name" not in everything
    assert "record.csv" not in everything
