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

from factordesk.analytics.currency import EuroLegs, convert_factors, hedge
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


def test_api_hedged_leaf_is_the_local_return_minus_rf_plus_euro_cash(
    world: World, client: ApiClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The service converts every history, but a hedged line is hedged on its local return."""
    with_sources(world, FAKE)
    seen: dict[str, Any] = {}
    real = pr._common_returns  # pyright: ignore[reportPrivateUsage]

    def spy(*args: Any, **kwargs: Any) -> Any:
        out = real(*args, **kwargs)
        seen["common"] = out
        return out

    monkeypatch.setattr(pr, "_common_returns", spy)
    # AAA sits under a hedged line and, as BBB's twin, under an unhedged one.
    body = eur_tree([holding(0, "AAA", 0.3), holding(1, "AAA", 0.3)])
    body["root"]["children"][0]["children"][0]["library_id"] = "fi_na_gov"
    response = post_tree(client, body)
    assert response.status_code == 200, response.text
    common = seen["common"]
    hedged_key, plain_key = list(common.leaf_ret.columns)[:2]
    local = world.provider.histories["AAA"].total_returns
    calendar = common.calendar
    ctx = CurrencyContext("EUR", FAKE)
    rf = pr._compounded_rf(world.factors["RF"], calendar)  # pyright: ignore[reportPrivateUsage]
    cash = ctx.cash(calendar)
    local_on_calendar = (
        world.provider.histories["AAA"].frame["adj_close"].loc[calendar].pct_change().iloc[1:]
    )
    expected = local_on_calendar - rf + cash
    got = common.leaf_ret[hedged_key]
    ok = got.notna()
    assert ok.sum() > 100
    np.testing.assert_allclose(got[ok].to_numpy(), expected[ok].to_numpy(), atol=1e-12)
    assert local.notna().all()
    # The unhedged twin is the converted return, which differs from the local one.
    assert not np.allclose(common.leaf_ret[plain_key].to_numpy(), local_on_calendar.to_numpy())
    assert (
        "US risk-free rate (factor file)" in response.json()["portfolio_backtest"]["end_limited_by"]
    )


# ----------------------------------------------------------- macro and energy in the EUR view
def _fx_f(calendar: pd.DatetimeIndex) -> pd.Series:
    """A made-up return of the dollar in euros over each interval of ``calendar``."""
    values = 0.002 * np.sin(np.arange(1, len(calendar)) / 7.0)
    return pd.Series(values, index=calendar[1:], name="fx")


def _eur_frame(factors: pd.DataFrame, calendar: pd.DatetimeIndex, cash: float) -> pd.DataFrame:
    c = pd.Series(cash, index=calendar[1:])
    return convert_factors(factors, _fx_f(calendar), c)


def test_eur_macro_legs_are_the_usd_legs_converted_with_the_dollar_return() -> None:
    from factordesk.analytics.macro import build_design
    from factordesk.analytics.sample import build_sample
    from factordesk.tests.test_macro import levels_of, make_macro_case

    case = make_macro_case(9101, n=800)
    calendar = pd.DatetimeIndex(case.stock.frame.index)
    f = _fx_f(calendar)
    c = 0.0001
    frame = _eur_frame(case.factors, calendar, c)
    sample = build_sample(case.stock, frame)
    legs = EuroLegs(f, case.factors["RF"])
    design = build_design(sample, calendar, levels_of(case), None, legs)
    usd = build_design(
        build_sample(case.stock, case.factors), calendar, levels_of(case), case.dollar
    )
    term, dspread, comm, infl, _ = case.z.T
    skip = 800 - design.n  # the first day has no lagged dollar return
    assert skip == 1
    fx = f.to_numpy()[skip:]
    cols = dict(zip(design.codes, design.x.T, strict=True))
    usd_cols = dict(zip(usd.codes, usd.x.T, strict=True))
    # a spread leg is the USD spread times (1 + f); TERM uses the dollar risk-free rate
    for code in ("term", "def", "infl"):
        np.testing.assert_allclose(cols[code], usd_cols[code] * (1.0 + fx), atol=1e-12)
    np.testing.assert_allclose(cols["term"], term[skip:] * (1.0 + fx), atol=1e-12)
    np.testing.assert_allclose(cols["def"], dspread[skip:] * (1.0 + fx), atol=1e-12)
    np.testing.assert_allclose(cols["infl"], infl[skip:] * (1.0 + fx), atol=1e-12)
    # COMM is DBC converted, minus the euro cash return c (not the dollar rate)
    dbc = case.rf[skip:] + comm[skip:]
    np.testing.assert_allclose(cols["comm"], (1.0 + dbc) * (1.0 + fx) - 1.0 - c, atol=1e-12)
    # the dollar leg is f itself, with the previous day's f as the lag term
    np.testing.assert_allclose(cols["usd"], fx, atol=1e-15)
    assert design.usd_lag is not None
    np.testing.assert_allclose(design.usd_lag, f.to_numpy()[skip - 1 : -1], atol=1e-15)
    # the market leg is the euro market factor of the frame
    np.testing.assert_allclose(cols["mkt_rf"], frame["Mkt-RF"].to_numpy()[skip:], atol=1e-15)


def test_eur_macro_ignores_the_fed_dollar_index() -> None:
    from factordesk.analytics.macro import run_macro
    from factordesk.analytics.sample import build_sample
    from factordesk.tests.test_macro import levels_of, make_macro_case

    case = make_macro_case(9102, n=600)
    calendar = pd.DatetimeIndex(case.stock.frame.index)
    sample = build_sample(case.stock, _eur_frame(case.factors, calendar, 0.0001))
    legs = EuroLegs(_fx_f(calendar), case.factors["RF"])
    _, with_index = run_macro(sample, calendar, levels_of(case), case.dollar, legs)
    _, without = run_macro(sample, calendar, levels_of(case), None, legs)
    assert [r.beta for r in with_index.rows] == [r.beta for r in without.rows]
    assert [r.code for r in without.rows][-1] == "usd"
    usd = without.rows[-1]
    assert usd.beta_same_day is not None and usd.beta_lag is not None


def test_eur_energy_carbon_leg_uses_the_euro_cash_return_and_shocks_stay_in_dollars() -> None:
    from factordesk.analytics.energy import build_columns
    from factordesk.analytics.sample import build_sample
    from factordesk.tests.test_energy import make_energy_case

    case = make_energy_case(9103, n=700)
    calendar = pd.DatetimeIndex(case.stock.frame.index)
    f = _fx_f(calendar)
    c = 0.0001
    sample = build_sample(case.stock, _eur_frame(case.factors, calendar, c))
    krbn = case.krbn.frame["adj_close"]
    usd_cols = build_columns(
        build_sample(case.stock, case.factors), calendar, case.oil_levels, case.gas_levels, krbn
    )
    eur_cols = build_columns(sample, calendar, case.oil_levels, case.gas_levels, krbn, f)
    fx = f.to_numpy()
    krbn_ret = case.rf + case.co2  # KRBN's simple return, as the case builds it
    np.testing.assert_allclose(eur_cols.co2, (1.0 + krbn_ret) * (1.0 + fx) - 1.0 - c, atol=1e-12)
    # Brent and Henry Hub are not converted
    np.testing.assert_array_equal(eur_cols.oil, usd_cols.oil)
    np.testing.assert_array_equal(eur_cols.gas, usd_cols.gas)


def _usd_loaders(dates: pd.DatetimeIndex) -> tuple[Any, Any]:
    from factordesk.section_hooks.context import (
        DollarInput,
        EnergyInput,
        MacroInput,
        SeriesInput,
        WorldBenchmarkInput,
    )
    from factordesk.tests.fixtures.dgp import price_history

    rng = np.random.default_rng(9104)
    n = len(dates)

    def fund(ticker: str, drift: float) -> WorldBenchmarkInput:
        return WorldBenchmarkInput(
            history=price_history(rng.normal(drift, 0.003, size=n), dates, ticker=ticker)
        )

    def levels(start: float, sd: float) -> pd.Series:
        index = pd.DatetimeIndex([pd.Timestamp("2009-12-31"), *dates], name="date")
        values = start * np.exp(np.concatenate([[0.0], np.cumsum(rng.normal(0.0, sd, size=n))]))
        return pd.Series(values, index=index)

    macro = MacroInput(
        funds={t: fund(t, 0.0002) for t in ("IEF", "LQD", "DBC", "TIP", "IEI")},
        dollar=DollarInput(levels=levels(100.0, 0.002)),
    )
    energy = EnergyInput(
        oil=SeriesInput(levels=levels(60.0, 0.015)),
        gas=SeriesInput(levels=levels(3.0, 0.02)),
        carbon=fund("KRBN", 0.0003),
    )
    return (lambda: macro), (lambda: energy)


def test_eur_ticker_report_has_macro_and_energy_and_the_usd_view_keeps_its_wording(
    tmp_path: Any,
) -> None:
    w = ticker_world(tmp_path)
    with_sources(cast(Any, w), FAKE)
    macro, energy = _usd_loaders(pd.DatetimeIndex(w.history.frame.index[1:]))
    deps = cast(Any, w).service.deps
    object.__setattr__(deps, "load_macro", macro)
    object.__setattr__(deps, "load_energy", energy)
    with report_tests.serve(w.app) as c:
        usd = c.get("/api/report/SYN").json()
        eur_response = c.get("/api/report/SYN?ccy=EUR")
    assert eur_response.status_code == 200, eur_response.text
    eur = eur_response.json()
    assert eur["macro"]["status"] == "ok" and eur["energy"]["status"] == "ok"
    assert eur["energy"]["carbon_model"] is not None
    notes = " ".join(eur["currency"]["notes"]).lower()
    assert "macro" not in notes and "energy" not in notes
    # the dollar leg is the dollar against the euro, in the EUR view only
    assert [r["label"] for r in eur["macro"]["rows"]][-1] == "US dollar against the euro"
    assert [r["label"] for r in usd["macro"]["rows"]][-1] == "US dollar"
    assert "in euros" in eur["macro"]["model_note"]
    assert "in euros" not in usd["macro"]["model_note"]
    assert eur["macro"]["usd_included"] and eur["macro"]["usd_lag_note"]
    assert eur["macro"]["rows"][-1]["beta_lag"] is not None
    assert any(leg["ticker"] == "USD/EUR" for leg in eur["macro"]["legs"])
    assert "in euros" in eur["energy"]["model_note"]
    assert eur["macro"]["rows"] != usd["macro"]["rows"]
    # oil and gas stay US-dollar log changes
    oil_leg = next(leg for leg in eur["energy"]["legs"] if leg["code"] == "oil")
    assert "US dollars" in oil_leg["role"]


def test_eur_monthly_subject_has_macro_with_the_dollar_leg_and_no_lag_term() -> None:
    from factordesk.analytics.macro import LEG_TICKERS
    from factordesk.analytics.subject import subject_from_monthly_returns
    from factordesk.pipeline import assemble_subject_report
    from factordesk.section_hooks.context import (
        DollarInput,
        MacroInput,
        ReferenceInput,
        SectionInputs,
        WorldBenchmarkInput,
    )
    from factordesk.tests.test_macro import NOW, _history  # pyright: ignore[reportPrivateUsage]
    from factordesk.tests.test_subject import monthly_case

    returns, factors, _ = monthly_case(120, 33, start="2005-01-31")
    month_ends = pd.DatetimeIndex(returns.index)
    calendar = pd.DatetimeIndex([month_ends[0] - pd.offsets.MonthEnd(1), *month_ends])
    days = pd.bdate_range("2004-12-01", month_ends[-1])
    rng = np.random.default_rng(34)

    def walk(sd: float) -> pd.Series:
        steps = rng.normal(0.0002, sd, len(days) - 1)
        return pd.Series(100.0 * np.concatenate([[1.0], np.cumprod(1.0 + steps)]), index=days)

    funds = {t: WorldBenchmarkInput(history=_history(t, walk(0.003))) for t in LEG_TICKERS}
    macro = MacroInput(funds=funds, dollar=DollarInput(levels=walk(0.002)))
    usd_rf = factors["RF"]
    frame = convert_factors(factors, _fx_f(calendar), pd.Series(0.0001, index=month_ends))
    inputs = SectionInputs(
        macro=macro,
        reference=ReferenceInput(lambda dates: _fx_f(dates), usd_rf),
    )
    subject = subject_from_monthly_returns(returns, label="Fund")
    report = assemble_subject_report(
        subject, frame, now=NOW, factors_downloaded_at=None, section_inputs=inputs
    )
    section = report.macro
    assert section is not None and section.status == "ok" and section.frequency == "monthly"
    assert section.rows[-1].label == "US dollar against the euro"
    assert section.usd_lag_note is None and section.rows[-1].beta_lag is None
    assert "in euros" in section.model_note
