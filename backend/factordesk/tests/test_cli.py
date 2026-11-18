"""CLI smoke tests with injected providers (offline)."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, date, datetime
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from factordesk import cli
from factordesk.data.factors import FactorDownloadError, FactorStatus
from factordesk.data.prices import PriceDataError, PriceHistory
from factordesk.report import load_report
from factordesk.tests.fixtures.dgp import StaticProvider, dgp_a, rng_for

NOW = datetime(2026, 11, 18, 15, 0, tzinfo=UTC)


def _returning(status: FactorStatus | None) -> Callable[..., FactorStatus | None]:
    def fake(data_dir: Path | None = None, now: datetime | None = None) -> FactorStatus | None:
        return status

    return fake


class FailingProvider:
    def __init__(self, exc: Exception) -> None:
        self.exc = exc

    def fetch(self, ticker: str) -> PriceHistory:
        raise self.exc


@pytest.fixture
def synthetic() -> tuple[StaticProvider, pd.DataFrame]:
    d = dgp_a(rng_for(200), n=800)
    return StaticProvider(d.history), d.factors.iloc[:780]


@pytest.fixture(autouse=True)
def _isolated_data_dir(  # pyright: ignore[reportUnusedFunction]
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class StubSettings:
        data_dir = tmp_path / "cache"

    monkeypatch.setattr(cli, "get_settings", lambda: StubSettings())


def test_report_writes_html_and_json(
    synthetic: tuple[StaticProvider, pd.DataFrame],
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    provider, factors = synthetic
    out = tmp_path / "out"
    code = cli.main(
        ["report", "spy", "--out", str(out), "--json"],
        price_provider=provider,
        factors=factors,
        now=NOW,
    )
    assert code == cli.EXIT_OK
    html = out / "SPY_report.html"
    js = out / "SPY_report.json"
    assert html.is_file() and js.is_file()
    assert html.read_bytes().startswith(b"<!doctype html>")
    assert bytes([13, 10]) not in html.read_bytes() + js.read_bytes()
    rep = load_report(js)
    assert rep.ticker == "SPY" and rep.data.n_obs == 780
    printed = capsys.readouterr().out
    assert "SPY: n = 780" in printed and "Wrote" in printed


def test_report_without_json_and_default_out(
    synthetic: tuple[StaticProvider, pd.DataFrame],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider, factors = synthetic
    monkeypatch.chdir(tmp_path)
    opened: list[str] = []
    monkeypatch.setattr(cli.webbrowser, "open", lambda url: opened.append(url) or True)  # pyright: ignore[reportUnknownLambdaType, reportUnknownArgumentType, reportUnknownMemberType]
    code = cli.main(["report", "SPY", "--open"], price_provider=provider, factors=factors, now=NOW)
    assert code == cli.EXIT_OK
    assert (tmp_path / "SPY_report.html").is_file()
    assert not (tmp_path / "SPY_report.json").exists()
    assert len(opened) == 1 and opened[0].startswith("file:")


def test_invalid_ticker(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    code = cli.main(["report", "../x", "--out", str(tmp_path)], now=NOW)
    assert code == cli.EXIT_DATA
    err = capsys.readouterr().err
    assert err.count("\n") == 1 and "invalid ticker" in err


def test_unknown_ticker(
    synthetic: tuple[StaticProvider, pd.DataFrame],
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    _, factors = synthetic
    provider = FailingProvider(PriceDataError("No price data returned for 'ZZZZQX'"))
    code = cli.main(
        ["report", "ZZZZQX", "--out", str(tmp_path)],
        price_provider=provider,
        factors=factors,
        now=NOW,
    )
    assert code == cli.EXIT_DATA
    assert "ZZZZQX" in capsys.readouterr().err


def test_no_network(
    synthetic: tuple[StaticProvider, pd.DataFrame],
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    _, factors = synthetic
    provider = FailingProvider(ConnectionError("Could not resolve host"))
    code = cli.main(
        ["report", "SPY", "--out", str(tmp_path)], price_provider=provider, factors=factors, now=NOW
    )
    assert code == cli.EXIT_NETWORK
    assert "network" in capsys.readouterr().err


def test_too_short_history(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    d = dgp_a(rng_for(201), n=300)
    code = cli.main(
        ["report", "NEW", "--out", str(tmp_path)],
        price_provider=StaticProvider(d.history),
        factors=d.factors,
        now=NOW,
    )
    assert code == cli.EXIT_DATA
    err = capsys.readouterr().err
    assert "300" in err and "504" in err and err.count("\n") == 1


def test_refuses_cache_folder(
    synthetic: tuple[StaticProvider, pd.DataFrame], tmp_path: Path
) -> None:
    provider, factors = synthetic
    code = cli.main(
        ["report", "SPY", "--out", str(tmp_path / "cache" / "x")],
        price_provider=provider,
        factors=factors,
        now=NOW,
    )
    assert code == cli.EXIT_OUTPUT
    assert not (tmp_path / "cache").exists()


# --------------------------------------------------------------------------- T126 bad inputs
def _degenerate_case(case: str) -> tuple[PriceHistory, pd.DataFrame]:
    """Inputs for test-oracle T126 (each from DGP-A with 800 rows)."""
    rng = rng_for(126)
    d = dgp_a(rng, n=800)
    history, factors = d.history, d.factors.copy()
    frame = history.frame.copy()
    if case == "zero_factor":
        factors["CMA"] = 0.0
    elif case == "constant_factor":
        factors["CMA"] = 0.001
    elif case == "collinear":
        factors["CMA"] = factors["HML"]
    elif case == "near_collinear":
        noise = rng.standard_normal(len(factors)) * float(factors["HML"].std()) * 1e-4
        factors["CMA"] = factors["HML"] + noise
    elif case == "constant_price_rf_const":
        frame[["close", "adj_close"]] = 50.0
        factors["RF"] = 0.0001
    elif case == "constant_price_rf_varies":
        frame[["close", "adj_close"]] = 50.0
    elif case == "zero_factor_stretch":
        smb = factors["SMB"].to_numpy(copy=True)
        smb[300:430] = 0.0
        factors["SMB"] = smb
    elif case == "nan_gaps":
        adj = frame["adj_close"].to_numpy(copy=True)
        adj[100:105] = np.nan
        frame["adj_close"] = adj
        frame["close"] = adj
        hml = factors["HML"].to_numpy(copy=True)
        hml[200:203] = np.nan
        factors["HML"] = hml
    elif case == "duplicate_dates":
        frame = pd.concat([frame.iloc[:400], frame.iloc[399:400], frame.iloc[400:]])
    else:  # pragma: no cover - test bug
        raise AssertionError(case)
    return PriceHistory("SYN", frame, history.fetched_at, history.source), factors


@pytest.mark.parametrize(
    ("case", "expect_exit"),
    [
        ("zero_factor", 1),
        ("constant_factor", 1),
        ("collinear", 1),
        ("near_collinear", 1),
        ("constant_price_rf_const", 1),
        ("constant_price_rf_varies", 1),
        ("zero_factor_stretch", 0),
        ("nan_gaps", 0),
        ("duplicate_dates", 0),
    ],
)
def test_t126_degenerate_inputs_end_cleanly(
    case: str, expect_exit: int, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    history, factors = _degenerate_case(case)
    out = tmp_path / "out"
    code = cli.main(
        ["report", "SYN", "--out", str(out), "--json"],
        price_provider=StaticProvider(history),
        factors=factors,
        now=NOW,
    )
    err = capsys.readouterr().err
    assert code == expect_exit, err
    assert "Traceback" not in err
    if expect_exit:
        assert err.count("\n") == 1 and err.startswith("factordesk: error: ")
        assert not (out / "SYN_report.json").exists()
        if case in {"zero_factor", "constant_factor", "collinear", "near_collinear"}:
            assert "CMA" in err
        if case.startswith("constant_price"):
            assert "price" in err
        return
    rep = load_report(out / "SYN_report.json")
    assert rep.regression.r2 is not None and 0.0 <= rep.regression.r2 <= 1.0
    if case == "zero_factor_stretch":
        by_window = {w.window: w for w in rep.rolling}
        assert by_window[126].status == "failed" and by_window[126].reason
        assert "5 of 675" in by_window[126].reason
        assert by_window[252].status == "ok"
        assert rep.average_beta.status == "ok"
    if case == "nan_gaps":
        assert rep.data.excluded_by_reason == {"price_missing": 6, "factor_missing": 3}
    if case == "duplicate_dates":
        assert rep.data.audit_status == "errors"
        dup = [f for f in rep.data.audit_findings if f.code == "duplicate_index"]
        assert len(dup) == 1 and dup[0].severity == "error"
        assert dup[0].dates == [history.frame.index[399].date()]
        assert rep.data.n_obs == 800


def test_unexpected_numerical_error_is_one_line(
    synthetic: tuple[StaticProvider, pd.DataFrame],
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider, factors = synthetic

    def boom(*args: object, **kwargs: object) -> None:
        raise ArithmeticError("non-finite statistic nan in an 'ok' result")

    monkeypatch.setattr("factordesk.pipeline.assemble_report", boom)
    code = cli.main(
        ["report", "SPY", "--out", str(tmp_path)], price_provider=provider, factors=factors, now=NOW
    )
    err = capsys.readouterr().err
    assert code == cli.EXIT_DATA
    assert err.count("\n") == 1 and "could not compute" in err


def test_usage_errors() -> None:
    assert cli.main([]) == cli.EXIT_USAGE
    assert cli.main(["report"]) == cli.EXIT_USAGE
    assert cli.main(["factors", "bogus"]) == cli.EXIT_USAGE
    assert cli.main(["--help"]) == cli.EXIT_OK


def test_factors_status(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    status = FactorStatus(
        last_date=date(2026, 9, 30),
        first_date=date(1963, 7, 1),
        days_behind=49,
        last_download_at=datetime(2026, 11, 1, tzinfo=UTC),
        source_url="https://example.invalid/f.zip",
        stale=True,
    )
    monkeypatch.setattr(cli, "factor_status", _returning(status))
    assert cli.main(["factors", "status"], now=NOW) == cli.EXIT_OK
    out = capsys.readouterr().out
    assert "1963-07-01 to 2026-09-30" in out and "49 days" in out and "stale" in out
    monkeypatch.setattr(cli, "factor_status", _returning(None))
    assert cli.main(["factors", "status"], now=NOW) == cli.EXIT_DATA


def test_factors_refresh(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    calls: list[bool] = []

    def fake_load(refresh: bool = False, now: datetime | None = None) -> pd.DataFrame:
        calls.append(refresh)
        return pd.DataFrame()

    status = FactorStatus(date(2026, 9, 30), date(1963, 7, 1), 49, NOW, "u", True)
    monkeypatch.setattr(cli, "load_ff5_daily", fake_load)
    monkeypatch.setattr(cli, "factor_status", _returning(status))
    assert cli.main(["factors", "refresh"], now=NOW) == cli.EXIT_OK
    assert calls == [True]
    assert "refreshed" in capsys.readouterr().out

    def failing(refresh: bool = False, now: datetime | None = None) -> pd.DataFrame:
        raise FactorDownloadError("network error: offline")

    monkeypatch.setattr(cli, "load_ff5_daily", failing)
    assert cli.main(["factors", "refresh"], now=NOW) == cli.EXIT_NETWORK
    assert "network" in capsys.readouterr().err
