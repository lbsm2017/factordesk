"""CHF cash on SARON (S4-10): the SNB loader, the rate splice, the index, and the portfolio line.

No network: every download is replaced by a fake, and the sockets are closed.
"""

from __future__ import annotations

import dataclasses
import socket
from collections.abc import Iterator, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import httpx
import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from factordesk.analytics.currency import convert
from factordesk.api import portfolio_report as pr
from factordesk.api.currency_ctx import CurrencyContext, CurrencySources
from factordesk.api.portfolio_models import PortfolioTree
from factordesk.data import rates, snb
from factordesk.data.fx import SOURCE_ECB, FxResult
from factordesk.data.snb import SnbError, load_snb_series, parse_snb_csv
from factordesk.tests import test_api_portfolio as portfolio_tests
from factordesk.tests.test_api_portfolio import ApiClient, World, holding, make_world, tree
from factordesk.tests.test_currency_view import (
    FAKE,
    eur_price,
    fake_rate,
    with_sources,
)

NOW = datetime(2026, 11, 20, 12, 0, tzinfo=UTC)
LATER = datetime(2026, 11, 21, 12, 0, tzinfo=UTC)


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
    snb._FAILED.clear()  # pyright: ignore[reportPrivateUsage]


# ---------------------------------------------------------------------------- the SNB loader
def snb_csv(item: str, values: Mapping[str, float | None]) -> str:
    """The body of an SNB cube file: header lines, a blank line, then the rows."""
    rows = "\n".join(
        f'"{d}";"{item}";{"" if v is None else f"{chr(34)}{v}{chr(34)}"}' for d, v in values.items()
    )
    return f'﻿"CubeId";"x"\n"PublishingDate";"2026-11-16 10:00"\n\n"Date";"D0";"Value"\n{rows}\n'


def test_the_cube_file_is_read_in_percent_and_empty_days_are_dropped() -> None:
    text = snb_csv("SARON", {"2009-08-21": None, "2009-08-24": 0.02, "2009-08-25": -0.04})
    series = parse_snb_csv(text, "x", 0.01)
    assert list(series.index) == [pd.Timestamp("2009-08-24"), pd.Timestamp("2009-08-25")]
    np.testing.assert_allclose(series.to_numpy(), [0.0002, -0.0004])


@pytest.mark.parametrize("body", ["", "nothing here", snb_csv("SARON", {"2009-08-21": None})])
def test_a_file_with_no_rows_is_an_error(body: str) -> None:
    with pytest.raises(SnbError):
        parse_snb_csv(body, "x")


def test_the_url_asks_for_the_full_history_of_one_item() -> None:
    url = snb.SNB_URL.format(cube="snbgwdzid", item="SARON", start=snb.HISTORY_START)
    assert url == (
        "https://data.snb.ch/api/cube/snbgwdzid/data/csv/en?fromDate=1999-01-01&dimSel=D0(SARON)"
    )


def test_snb_cache_is_used_for_the_day_and_an_old_copy_serves_an_outage(tmp_path: Path) -> None:
    calls: list[str] = []

    def fetch(cube: str, item: str) -> str:
        calls.append(item)
        return snb_csv(item, {"2026-11-18": -0.04, "2026-11-19": -0.05})

    first, note = load_snb_series("snbgwdzid", "SARON", data_dir=tmp_path, now=NOW, fetch=fetch)
    again, _ = load_snb_series("snbgwdzid", "SARON", data_dir=tmp_path, now=NOW, fetch=fetch)
    assert note is None and calls == ["SARON"] and first.equals(again)

    def down(*_a: str) -> str:
        raise SnbError("simulated outage", host_down=True)

    old, note = load_snb_series("snbgwdzid", "SARON", data_dir=tmp_path, now=LATER, fetch=down)
    assert old.equals(first)
    assert note and "Swiss National Bank could not be reached" in note and "2026-11-20" in note
    with pytest.raises(SnbError):  # another item has no cache at all
        load_snb_series("zirepo", "H0", data_dir=tmp_path, now=LATER, fetch=down)


def test_download_retries_a_5xx_and_stops_at_a_4xx(monkeypatch: pytest.MonkeyPatch) -> None:
    status = {"code": 503, "calls": 0}

    class Client:
        def __init__(self, **_kw: object) -> None: ...
        def __enter__(self) -> Client:
            return self

        def __exit__(self, *_a: object) -> None: ...
        def get(self, _url: str) -> httpx.Response:
            status["calls"] += 1
            return httpx.Response(status["code"], text="body")

    monkeypatch.setattr(snb.httpx, "Client", Client)
    with pytest.raises(SnbError) as excinfo:
        snb.download_csv("snbgwdzid", "SARON")
    assert excinfo.value.host_down and status["calls"] == snb.ATTEMPTS
    status.update(code=404, calls=0)
    with pytest.raises(SnbError) as excinfo:
        snb.download_csv("snbgwdzid", "SARON")
    assert not excinfo.value.host_down and status["calls"] == 1


# ------------------------------------------------------------------------------ the rate splice
# zirepo H0: six decimals, ends on 2026-11-10 (it lags); snbgwdzid SARON: two decimals, fresh.
HISTORY = {
    "2009-08-20": 0.0155,
    "2009-08-21": 0.0158,
    "2009-08-24": 0.0178,
    "2009-08-25": 0.0163,
    "2026-11-10": -0.0446,
}
FRESH = {"2009-08-24": 0.02, "2009-08-25": 0.02, "2026-11-10": -0.04, "2026-11-11": -0.05}


def snb_fetch(*, fresh: bool = True, history: bool = True) -> Any:
    def fetch(cube: str, item: str) -> str:
        if cube == "snbgwdzid" and fresh:
            return snb_csv(item, {"2009-08-21": None, **FRESH})
        if cube == "zirepo" and history:
            return snb_csv(item, HISTORY)
        raise SnbError(f"{cube}: simulated outage", host_down=True)

    return fetch


def test_rate_is_one_saron_series_with_the_precise_history_then_the_fresh_days(
    tmp_path: Path,
) -> None:
    result = rates.load_chf_overnight(data_dir=tmp_path, now=NOW, fetch_snb=snb_fetch())
    assert result.rate is not None and result.notice is None
    assert result.credit == (
        "Swiss franc overnight rate (SARON): Swiss National Bank data portal, from 2009-08-20."
    )
    rate = result.rate
    # every day the history has is the history's value (six decimals), as published
    assert rate.loc["2009-08-20"] == pytest.approx(0.000155)
    assert rate.loc["2009-08-24"] == pytest.approx(0.000178)
    assert rate.loc["2026-11-10"] == pytest.approx(-0.000446)
    # after the last day of the history: the fresh cube's SARON
    assert rate.loc["2026-11-11"] == pytest.approx(-0.0005)
    assert rate.index.is_monotonic_increasing and not rate.index.has_duplicates


def test_rate_starts_at_the_first_fresh_fixing_when_the_history_is_missing(
    tmp_path: Path,
) -> None:
    result = rates.load_chf_overnight(
        data_dir=tmp_path, now=NOW, fetch_snb=snb_fetch(history=False)
    )
    assert result.rate is not None and result.rate.index[0] == pd.Timestamp("2009-08-24")
    assert result.notice and "2009-08-24" in result.notice
    assert result.credit is not None and result.credit.endswith("from 2009-08-24.")
    assert result.rate.loc["2009-08-24"] == pytest.approx(0.0002)


def test_rate_is_none_with_a_notice_when_the_fresh_cube_is_down(tmp_path: Path) -> None:
    result = rates.load_chf_overnight(data_dir=tmp_path, now=NOW, fetch_snb=snb_fetch(fresh=False))
    assert result.rate is None and result.notice and "SARON is unavailable" in result.notice


# ------------------------------------------------------------------------------- the cash index
def test_cash_index_accrues_act_360_and_compounds_each_day_of_a_holiday_gap() -> None:
    # Good Friday and Easter Monday 2025 are Swiss holidays: no SARON on 18 and 21 April.
    days = ["2025-04-16", "2025-04-17", "2025-04-22"]
    rate = pd.Series([0.0001, -0.0004, 0.0002], index=pd.DatetimeIndex(days), name="chf_rate")
    grid = pd.DatetimeIndex(["2025-04-16", "2025-04-17", "2025-04-22", "2025-04-23"])
    got = rates.cash_returns(rate, grid)
    # 16 -> 17: one day at 0.01%
    assert got.iloc[0] == pytest.approx(1.0 + 0.0001 / 360.0 - 1.0, abs=1e-15)
    # 17 -> 22: five calendar days at the 17 April rate (-0.04%), ACT/360
    assert got.iloc[1] == pytest.approx(-0.0004 * 5 / 360.0, abs=1e-15)
    # 22 -> 23: one day at the 22 April rate
    assert got.iloc[2] == pytest.approx(0.0002 / 360.0, abs=1e-15)
    # a gap on the grid compounds the rate of each business day inside it
    wide = pd.DatetimeIndex(["2025-04-16", "2025-04-23"])
    one_step = rates.cash_returns(rate, wide).iloc[0]
    expected = (1.0 + 0.0001 / 360.0) * (1.0 + -0.0004 * 5 / 360.0) * (1.0 + 0.0002 / 360.0) - 1.0
    assert one_step == pytest.approx(expected, abs=1e-15)
    assert (1.0 + got).prod() - 1.0 == pytest.approx(expected, abs=1e-15)


def test_cash_index_is_nan_before_the_first_fixing_and_after_the_carry_limit() -> None:
    rate = pd.Series([0.0001, 0.0002], index=pd.DatetimeIndex(["2025-04-16", "2025-04-17"]))
    grid = pd.DatetimeIndex(["2025-04-14", "2025-04-16", "2025-04-18", "2025-05-02"])
    got = rates.cash_returns(rate, grid)
    assert np.isnan(got.iloc[0])  # interval starts before the first rate date
    assert np.isfinite(got.iloc[1])
    assert np.isnan(got.iloc[2])  # the last rate is 15 days old


# ---------------------------------------------------------------------- the portfolio line
CHF_RATE = -0.0004


def chf_rate() -> rates.RateResult:
    days = pd.bdate_range("1999-06-21", "2035-01-01")
    series = pd.Series(CHF_RATE, index=days, name="chf_rate")
    return rates.RateResult(series, None, rates.snb_credit(series.index[0]))


def chf_down() -> rates.RateResult:
    return rates.RateResult(None, "SARON is unavailable (Swiss National Bank: simulated outage).")


def _level(ccy: str, dates: pd.DatetimeIndex) -> pd.Series:
    """Price of one unit of ``ccy`` in euros, with the franc added to the test world."""
    if ccy == "CHF":
        days = np.asarray(dates.to_numpy().astype("datetime64[D]").astype(np.int64), dtype=float)
        return pd.Series(0.65 + 0.04 * np.sin(days / 40.0), index=dates)
    return eur_price(ccy, dates)


def fx_prices(ccy: str, ref: str, dates: pd.DatetimeIndex) -> FxResult:
    return FxResult((_level(ccy, dates) / _level(ref, dates)).rename("fx"), None, SOURCE_ECB)


def fx_returns(ccy: str, ref: str, dates: pd.DatetimeIndex) -> FxResult:
    price = fx_prices(ccy, ref, dates).series
    assert price is not None
    return FxResult((price / price.shift(1) - 1.0).iloc[1:].rename("fx"), None, SOURCE_ECB)


def franc_down(ccy: str, ref: str, dates: pd.DatetimeIndex) -> FxResult:
    if ccy == "CHF":
        return FxResult(None, "The CHF exchange rate is unavailable (simulated).")
    return fx_returns(ccy, ref, dates)


SOURCES = CurrencySources(fx_prices, fx_returns, fake_rate, chf_rate)


def chf_tree(reference: str = "USD", weights: tuple[float, float] = (0.6, 0.3)) -> dict[str, Any]:
    body = tree([holding(0, "AAA", weights[0]), holding(1, "FXF", weights[1], "CHF Cash")])
    body["root"]["children"][0]["children"][1]["library_id"] = "cash_chf"
    if reference == "EUR":
        body["reference_currency"] = "EUR"
    return body


def _plan_and_histories() -> tuple[pr.PortfolioPlan, dict[str, Any]]:
    plan = pr.plan_of(PortfolioTree.model_validate(chf_tree()))
    dates = pd.bdate_range("2012-01-02", periods=80)
    histories = {
        "AAA": portfolio_tests._history("AAA", 1, dates),  # pyright: ignore[reportPrivateUsage]
        "FXF": portfolio_tests._history("FXF", 2, dates),  # pyright: ignore[reportPrivateUsage]
    }
    return plan, histories


@pytest.mark.parametrize("view", ["USD", "EUR"])
def test_chf_cash_line_is_saron_converted_to_the_reference_currency(view: str) -> None:
    plan, histories = _plan_and_histories()
    ctx = CurrencyContext(cast(Any, view), SOURCES)
    rf = pd.Series(0.0001, index=histories["AAA"].frame.index)
    listings = {"AAA": view, "FXF": "USD"}
    if view == "EUR":  # the service has converted every history to euros before this point
        histories = {k: h for k, h in histories.items()}
    common = pr._common_returns(plan, histories, rf, ctx, listings)  # pyright: ignore[reportPrivateUsage]
    key = next(r.key for r in plan.holdings if r.ticker == "FXF")
    assert key is not None
    in_francs = rates.cash_returns(chf_rate().rate, common.calendar)  # type: ignore[arg-type]
    to_ref = fx_returns("CHF", view, common.calendar).series
    assert to_ref is not None
    expected = convert(in_francs, to_ref)
    np.testing.assert_allclose(common.leaf_ret[key].to_numpy(), expected.to_numpy(), atol=1e-15)
    # the ETF is not in the backtest calendar, and the columns keep the tree order
    assert list(common.leaf_ret.columns) == [r.key for r in plan.holdings]
    assert ctx.chf_credit == rates.snb_credit(chf_rate().rate.index[0])  # type: ignore[union-attr]
    assert any("CHF Cash line earns SARON" in n for n in ctx.notes)


def test_chf_cash_with_no_sources_keeps_the_etf_and_says_nothing() -> None:
    plan, histories = _plan_and_histories()
    for sources in (None, CurrencySources(fx_prices, fx_returns, fake_rate)):
        ctx = CurrencyContext("USD", sources)
        rf = pd.Series(0.0001, index=histories["AAA"].frame.index)
        common = pr._common_returns(plan, histories, rf, ctx)  # pyright: ignore[reportPrivateUsage]
        key = next(r.key for r in plan.holdings if r.ticker == "FXF")
        assert key is not None
        etf = histories["FXF"].frame["adj_close"].loc[common.calendar].pct_change().iloc[1:]
        np.testing.assert_allclose(common.leaf_ret[key].to_numpy(), etf.to_numpy(), atol=1e-15)
        assert ctx.notes == [] and ctx.chf_credit is None


@pytest.mark.parametrize("failure", ["rate", "franc"])
def test_chf_cash_falls_back_to_fxf_with_a_notice(failure: str) -> None:
    plan, histories = _plan_and_histories()
    sources = (
        dataclasses.replace(SOURCES, chf_rate=chf_down)
        if failure == "rate"
        else dataclasses.replace(SOURCES, fx_returns=franc_down)
    )
    ctx = CurrencyContext("USD", sources)
    rf = pd.Series(0.0001, index=histories["AAA"].frame.index)
    common = pr._common_returns(plan, histories, rf, ctx)  # pyright: ignore[reportPrivateUsage]
    key = next(r.key for r in plan.holdings if r.ticker == "FXF")
    assert key is not None
    etf = histories["FXF"].frame["adj_close"].loc[common.calendar].pct_change().iloc[1:]
    np.testing.assert_allclose(common.leaf_ret[key].to_numpy(), etf.to_numpy(), atol=1e-15)
    assert any("The CHF Cash line uses FXF." in n for n in ctx.notes)
    assert ctx.chf_credit is None


def test_the_etf_is_fetched_only_when_saron_is_not_used() -> None:
    plan = pr.plan_of(PortfolioTree.model_validate(chf_tree()))
    for view in ("USD", "EUR"):
        assert pr.tickers_for(plan, view) == ("AAA", "FXF")
        assert pr.tickers_for(plan, view, True) == ("AAA",)


# --------------------------------------------------------------------------------- the report
@pytest.fixture
def world(tmp_path: Any) -> World:
    w = make_world(tmp_path)
    full = w.provider.histories["AAA"].frame.index
    w.provider.histories["FXF"] = portfolio_tests._history("FXF", 9, pd.DatetimeIndex(full))  # pyright: ignore[reportPrivateUsage]
    return w


@pytest.fixture
def client(world: World) -> Iterator[ApiClient]:
    with TestClient(world.app) as test_client:  # pyright: ignore[reportUnknownVariableType]
        yield cast(ApiClient, test_client)


def post_tree(client: ApiClient, body: dict[str, Any]) -> httpx.Response:
    return client.post("/api/report/portfolio", json=body)


def test_usd_report_names_saron_in_the_currency_block(world: World, client: ApiClient) -> None:
    with_sources(world, SOURCES)
    response = post_tree(client, chf_tree("USD"))
    assert world.provider.many_calls == [("AAA",)]  # FXF is not fetched: SARON is used
    assert response.status_code == 200, response.text
    body = response.json()
    block = body["currency"]
    assert block["reference"] == "USD"
    assert "SARON" in block["rate_source"] and "Swiss National Bank" in block["rate_source"]
    assert block["fx_source"]
    assert any("SARON" in n and "USD" in n for n in block["notes"])
    assert "unallocated_currency" not in body["portfolio_backtest"]


def test_eur_report_names_both_overnight_rates(world: World, client: ApiClient) -> None:
    with_sources(world, SOURCES)
    response = post_tree(client, chf_tree("EUR"))
    assert response.status_code == 200, response.text
    block = response.json()["currency"]
    assert block["reference"] == "EUR"
    assert "SARON" in block["rate_source"] and "European Central Bank" in block["rate_source"]
    assert any("SARON, converted to EUR" in n for n in block["notes"])


def test_the_report_differs_from_the_etf_and_survives_a_dead_source(
    world: World, client: ApiClient
) -> None:
    with_sources(world, SOURCES)
    saron = post_tree(client, chf_tree("USD")).json()
    with_sources(world, dataclasses.replace(SOURCES, chf_rate=chf_down))
    for view in ("USD", "EUR"):
        body = chf_tree(view)
        body["name"] = f"Same weights, {view} view, SARON down"  # a new name is a new cache key
        down = post_tree(client, body)
        assert down.status_code == 200, down.text
        assert world.provider.many_calls[-1] == ("AAA", "FXF")  # the fallback needs the ETF
        block = down.json()["currency"] if view == "EUR" else down.json().get("currency")
        if view == "EUR":
            assert any("The CHF Cash line uses FXF." in n for n in block["notes"])
            assert "SARON" not in (block["rate_source"] or "")
        else:
            assert block is not None and "SARON" not in (block["rate_source"] or "")
            assert any("SARON is unavailable" in n for n in block["notes"])
            assert down.json()["regression"] != saron["regression"]


def test_a_usd_portfolio_without_a_chf_line_has_no_currency_block(
    world: World, client: ApiClient
) -> None:
    with_sources(world, SOURCES)
    plain = post_tree(client, tree([holding(0, "AAA", 0.6)]))
    assert plain.status_code == 200
    assert "currency" not in plain.json()
    with_sources(world, FAKE)
    assert "currency" not in post_tree(client, chf_tree("USD")).json()
