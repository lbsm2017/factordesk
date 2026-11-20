"""The EUR view of every subject (S3-4), offline: exchange rates and the euro rate are fakes.

Covers: the USD view never touches the sources and has no ``currency`` block; the EUR ticker,
portfolio and upload reports; a hedged line, euro cash for the unallocated weight, pence, the
cache key and the soft failure when a source is down.
"""

from __future__ import annotations

import dataclasses
import json
import socket
from collections.abc import Iterator
from typing import Any, cast

import httpx
import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from factordesk.analytics.currency import hedge
from factordesk.api import portfolio_report as pr
from factordesk.api.currency_ctx import CurrencyContext, CurrencySources
from factordesk.api.portfolio_models import PortfolioTree, load_library
from factordesk.data import rates
from factordesk.data.fx import SOURCE_ECB, FxResult
from factordesk.data.prices import PriceHistory, Security
from factordesk.tests import test_api_portfolio as portfolio_tests
from factordesk.tests import test_api_report as report_tests
from factordesk.tests.test_api_portfolio import (
    ApiClient,
    World,
    holding,
    make_world,
    tree,
)
from factordesk.tests.test_security import MetadataProvider

RATE = 0.03
SECURITIES: dict[str, Security] = {}


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


# --------------------------------------------------------------------------- fake sources
def eur_price(ccy: str, dates: pd.DatetimeIndex) -> pd.Series:
    """Price of one ``ccy`` in euros: USD moves slowly, GBP a little faster, EUR is 1."""
    days = np.asarray(dates.to_numpy().astype("datetime64[D]").astype(np.int64), dtype=float)
    level = {
        "EUR": np.ones(len(days)),
        "USD": 0.9 + 0.05 * np.sin(days / 50.0),
        "GBP": 1.15 + 0.05 * np.cos(days / 70.0),
    }[ccy]
    return pd.Series(level, index=dates)


def fake_prices(ccy: str, ref: str, dates: pd.DatetimeIndex) -> FxResult:
    price = (eur_price(ccy, dates) / eur_price(ref, dates)).rename("fx")
    return FxResult(price, None, SOURCE_ECB)


def fake_returns(ccy: str, ref: str, dates: pd.DatetimeIndex) -> FxResult:
    price = fake_prices(ccy, ref, dates).series
    assert price is not None
    return FxResult((price / price.shift(1) - 1.0).iloc[1:].rename("fx"), None, SOURCE_ECB)


def fake_rate() -> rates.RateResult:
    days = pd.bdate_range("1980-01-01", "2035-01-01")
    return rates.RateResult(pd.Series(RATE, index=days, name="eur_rate"), None, rates.ECB_CREDIT)


FAKE = CurrencySources(fake_prices, fake_returns, fake_rate)


def _unreachable(*_args: object) -> Any:
    raise AssertionError("the USD view must not use exchange rates")


FORBIDDEN = CurrencySources(_unreachable, _unreachable, _unreachable)


def down_returns(ccy: str, ref: str, dates: pd.DatetimeIndex) -> FxResult:
    return FxResult(None, f"The {ccy}/{ref} exchange rate is unavailable (simulated).")


def with_sources(world: World, sources: CurrencySources) -> None:
    deps = world.app.state.report_service.deps
    object.__setattr__(deps, "currency", sources)


@pytest.fixture
def world(tmp_path: Any) -> World:
    w = make_world(tmp_path)
    with_sources(w, FORBIDDEN)
    return w


@pytest.fixture
def client(world: World) -> Iterator[ApiClient]:
    with TestClient(world.app) as test_client:  # pyright: ignore[reportUnknownVariableType]
        yield cast(ApiClient, test_client)


def get(client: ApiClient, path: str) -> httpx.Response:
    return cast(Any, client).get(path)


def post_tree(client: ApiClient, body: dict[str, Any]) -> httpx.Response:
    return client.post("/api/report/portfolio", json=body)


# --------------------------------------------------------------------------- ticker view
def ticker_world(tmp_path: Any) -> report_tests.World:
    w = report_tests.make_world(tmp_path)
    with_sources(cast(Any, w), FORBIDDEN)
    return w


def test_usd_ticker_view_is_the_default_and_never_uses_exchange_rates(tmp_path: Any) -> None:
    w = ticker_world(tmp_path)
    with report_tests.serve(w.app) as c:
        default = c.get("/api/report/SYN?model=ff5")
        explicit = c.get("/api/report/SYN?model=ff5&ccy=USD")
    assert default.status_code == 200, default.text
    assert default.text == explicit.text
    assert "currency" not in default.json()


def test_eur_ticker_report_runs_and_carries_the_currency_block(tmp_path: Any) -> None:
    w = ticker_world(tmp_path)
    with_sources(cast(Any, w), FAKE)
    with report_tests.serve(w.app) as c:
        usd = c.get("/api/report/SYN").json()
        eur_response = c.get("/api/report/SYN?ccy=EUR")
    assert eur_response.status_code == 200, eur_response.text
    eur = eur_response.json()
    assert eur["currency"]["reference"] == "EUR"
    assert eur["currency"]["fx_source"] and eur["currency"]["rate_source"]
    assert any("macro" in n.lower() for n in eur["currency"]["notes"])
    assert "macro" not in eur
    assert any("energy" in n.lower() for n in eur["currency"]["notes"])
    assert "energy" not in eur
    assert eur["regression"] != usd["regression"]
    # The price chart is in euros: USD price times the euro price of a dollar.
    first = pd.Timestamp(eur["price_series"]["dates"][0])
    usd_price = dict(
        zip(usd["price_series"]["dates"], usd["price_series"]["adj_close"], strict=True)
    )
    expected = usd_price[first.strftime("%Y-%m-%d")] * float(
        eur_price("USD", pd.DatetimeIndex([first])).iloc[0]
    )
    assert eur["price_series"]["adj_close"][0] == pytest.approx(expected)


def test_report_cache_key_differs_by_currency(tmp_path: Any) -> None:
    w = ticker_world(tmp_path)
    with_sources(cast(Any, w), FAKE)
    with report_tests.serve(w.app) as c:
        assert c.get("/api/report/SYN").status_code == 200
        assert c.get("/api/report/SYN?ccy=EUR").status_code == 200
    keys = w.service.reports.keys()
    assert len(keys) == 2
    assert {k[-1] for k in keys} == {"USD", "EUR"}
    assert {k[:-1] for k in keys[:1]} == {k[:-1] for k in keys[1:]}


def test_eur_view_fails_soft_with_a_503_and_the_usd_view_does_not_care(tmp_path: Any) -> None:
    w = ticker_world(tmp_path)
    with_sources(cast(Any, w), dataclasses.replace(FAKE, fx_prices=down_returns))
    with report_tests.serve(w.app) as c:
        usd = c.get("/api/report/SYN")
        eur = c.get("/api/report/SYN?ccy=EUR")
    assert usd.status_code == 200
    assert eur.status_code == 503
    assert eur.json()["code"] == "network" and "USD" in eur.json()["action"]


def test_pence_listing_is_divided_by_one_hundred_and_converted(tmp_path: Any) -> None:
    w = ticker_world(tmp_path)
    with_sources(cast(Any, w), FAKE)
    pence = w.history
    provider = MetadataProvider(pence, Security(name="UK plc", currency="GBp"))
    object.__setattr__(w.service.deps, "price_provider", provider)
    with report_tests.serve(w.app) as c:
        body = c.get("/api/report/SYN").json()
    first = pd.Timestamp(body["price_series"]["dates"][0])
    gbp_in_usd = fake_prices("GBP", "USD", pd.DatetimeIndex([first])).series
    assert gbp_in_usd is not None
    expected = (
        float(cast(float, pence.frame.loc[first, "adj_close"])) * 0.01 * float(gbp_in_usd.iloc[0])
    )
    assert body["price_series"]["adj_close"][0] == pytest.approx(expected)


# --------------------------------------------------------------------------- portfolio view
def eur_tree(instruments: list[dict[str, Any]], library_id: str = "eq_na_large") -> dict[str, Any]:
    body = tree(instruments)
    body["reference_currency"] = "EUR"
    for ac in body["root"]["children"]:
        for sub in ac["children"]:
            sub["library_id"] = library_id
    return body


def test_usd_portfolio_has_no_currency_block_and_no_unallocated_currency(
    world: World, client: ApiClient
) -> None:
    body = post_tree(client, tree([holding(0, "AAA", 0.6)])).json()
    assert "currency" not in body
    assert "unallocated_currency" not in body["portfolio_backtest"]
    explicit = tree([holding(0, "AAA", 0.6)])
    assert "reference_currency" not in PortfolioTree.model_validate(explicit).model_dump(
        mode="json"
    )


def test_eur_portfolio_holds_the_unallocated_weight_as_euro_cash(
    world: World, client: ApiClient
) -> None:
    with_sources(world, FAKE)
    response = post_tree(client, eur_tree([holding(0, "AAA", 0.6)]))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["currency"]["reference"] == "EUR"
    assert body["portfolio_backtest"]["unallocated_weight"] == pytest.approx(0.4)
    assert body["portfolio_backtest"]["unallocated_currency"] == "EUR"
    assert "macro" not in body


def test_eur_portfolio_hedges_flagged_lines_and_says_so(world: World, client: ApiClient) -> None:
    with_sources(world, FAKE)
    hedged = post_tree(client, eur_tree([holding(0, "AAA", 0.5)], "fi_na_gov")).json()
    assert any("Hedged to EUR: AAA" in n for n in hedged["currency"]["notes"])
    open_ = post_tree(client, eur_tree([holding(0, "AAA", 0.5)], "fi_global")).json()
    assert any("Not hedged, several currencies" in n for n in open_["currency"]["notes"])


def test_library_flags_the_hedge_table() -> None:
    lines = {line.id: line for line in load_library().lines}
    for line_id in ("fi_na_gov", "fi_na_ig", "fi_na_hy", "fi_em", "fi_infl_linked", "fi_tips"):
        assert lines[line_id].hedge_eur and not lines[line_id].multi_currency
    for line_id in ("fi_eur_gov", "fi_eur_ig", "fi_eur_hy", "fi_global", "fi_global_hy"):
        assert lines[line_id].multi_currency and not lines[line_id].hedge_eur
    assert not any(
        line.hedge_eur or line.multi_currency
        for line in lines.values()
        if line.id.startswith(("eq_", "alt_", "com_", "cash_"))
    )


def _plan_and_histories(library_id: str) -> tuple[pr.PortfolioPlan, dict[str, PriceHistory]]:
    plan = pr.plan_of(PortfolioTree.model_validate(eur_tree([holding(0, "AAA", 0.5)], library_id)))
    dates = pd.bdate_range("2012-01-02", periods=60)
    history = portfolio_tests._history("AAA", 1, dates)  # pyright: ignore[reportPrivateUsage]
    return plan, {"AAA": history}


def test_hedged_line_is_local_excess_plus_euro_cash() -> None:
    plan, histories = _plan_and_histories("fi_na_gov")
    ctx = CurrencyContext("EUR", FAKE)
    rf = pd.Series(0.0001, index=histories["AAA"].frame.index)
    common = pr._common_returns(plan, histories, rf, ctx, {"AAA": "USD"})  # pyright: ignore[reportPrivateUsage]
    key = plan.holdings[0].key
    assert key is not None
    local = histories["AAA"].total_returns
    cash = ctx.cash(common.calendar)
    expected = hedge(local, pd.Series(0.0001, index=local.index), cash)
    np.testing.assert_allclose(common.leaf_ret[key].to_numpy(), expected.to_numpy(), atol=1e-12)
    # Unhedged line: the history is left as it is (the service converts it beforehand).
    plain, histories = _plan_and_histories("eq_na_large")
    flat = pr._common_returns(plain, histories, rf, ctx, {"AAA": "USD"})  # pyright: ignore[reportPrivateUsage]
    np.testing.assert_allclose(flat.leaf_ret[key].to_numpy(), local.to_numpy(), atol=1e-12)


def test_eur_cash_line_becomes_the_euro_cash_index() -> None:
    plan = pr.plan_of(PortfolioTree.model_validate(_two_line_tree()))
    assert pr.tickers_for(plan, "EUR") == ("AAA",)
    assert pr.tickers_for(plan, "USD") == ("AAA", "FXE")


def _two_line_tree() -> dict[str, Any]:
    body = eur_tree([holding(0, "AAA", 0.5), holding(1, "FXE", 0.3)])
    body["root"]["children"][0]["children"][1]["library_id"] = "cash_eur"
    return body


# --------------------------------------------------------------------------- monthly view
def test_monthly_euro_cash_compounds_the_days_of_the_month() -> None:
    month_ends = pd.date_range("2024-01-31", periods=4, freq="ME")
    monthly = rates.cash_returns(fake_rate().rate, month_ends)  # type: ignore[arg-type]
    days = pd.bdate_range("2024-01-31", "2024-04-30")
    daily = rates.cash_returns(fake_rate().rate, pd.DatetimeIndex(days))  # type: ignore[arg-type]
    first_month = daily[(daily.index > "2024-01-31") & (daily.index <= "2024-02-29")]
    assert monthly.iloc[0] == pytest.approx(float((1.0 + first_month).prod() - 1.0), abs=1e-12)


def test_upload_converts_the_record_to_the_reference_currency(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    from factordesk.api import routes_upload
    from factordesk.tests.test_api_upload import csv_of
    from factordesk.tests.test_subject import monthly_case

    returns, frame, _ = monthly_case(72, 11)
    frame.attrs = {}

    def load(*_args: object, **_kw: object) -> pd.DataFrame:
        return frame

    monkeypatch.setattr(routes_upload, "load_ff6", load)
    monkeypatch.setattr(routes_upload, "load_ff5_monthly", load)
    w = make_world(tmp_path)
    with_sources(w, FAKE)
    with report_tests.serve(w.app) as c:
        post = cast(Any, c).post

        def upload(**fields: str) -> httpx.Response:
            return post(
                "/api/report/upload",
                files={"file": ("r.csv", csv_of(returns), "text/csv")},
                data={"name": "Fund", **fields},
            )

        usd = upload()
        eur = upload(ccy="EUR", record_currency="EUR")
        mixed = upload(ccy="EUR", record_currency="USD")
    assert usd.status_code == 200 and "currency" not in usd.json()
    assert eur.status_code == 200, eur.text
    assert eur.json()["currency"]["reference"] == "EUR"
    assert mixed.status_code == 200, mixed.text
    assert mixed.json()["regression"] != eur.json()["regression"]
    assert json.loads(eur.text)["subject"]["currency"] == "EUR"


def test_eur_portfolio_has_holdings_that_match_performance_and_tail_horizons(
    world: World, client: ApiClient
) -> None:
    with_sources(world, FAKE)
    body = eur_tree([holding(0, "AAA", 0.5), holding(1, "BBB", 0.2)], "fi_na_gov")
    # 20% USD cash instrument, 10% unallocated (held as euro cash).
    cash = {"id": "c0", "kind": "cash", "ticker": None, "label": "USD cash", "weight": 0.2}
    body["root"]["children"][0]["children"].append(
        {
            "id": "sc",
            "kind": "group",
            "label": "USD Cash",
            "library_id": "cash_usd",
            "children": [cash],
        }
    )
    response = post_tree(client, body)
    assert response.status_code == 200, response.text
    report = response.json()
    holdings = report["holdings"]
    assert holdings["status"] == "ok"
    performance = report["performance"]["returns"]["cumulative_return"]
    assert holdings["total_return"] == pytest.approx(performance, abs=1e-9)
    cash_rows = {r["id"]: r["label"] for r in holdings["rows"] if r["kind"] == "cash"}
    assert cash_rows["cash"] == "EUR cash" and cash_rows["usd_cash"].startswith("USD cash")
    if report["tail_risk"]["by_horizon"] is not None:
        assert report["tail_risk"]["status"] == "ok"
    assert report["portfolio_backtest"]["unallocated_weight"] == pytest.approx(0.1)
