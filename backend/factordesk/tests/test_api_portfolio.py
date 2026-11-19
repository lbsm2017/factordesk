"""``POST /api/report/portfolio``: the backtest, the report, every refusal and the cache (S2-3).

Offline: a fake provider serves synthetic histories by ticker (through ``fetch_many`` like the real
one), the factor frame is ``dgp_a``'s, the clock is fixed and ``tmp_path`` is the data folder.
"""

from __future__ import annotations

import dataclasses
import socket
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol, cast

import httpx
import numpy as np
import pandas as pd
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from factordesk.api.deps import AppDeps
from factordesk.api.main import create_app
from factordesk.api.portfolio_models import PortfolioTree
from factordesk.api.portfolio_report import (
    _common_returns,  # pyright: ignore[reportPrivateUsage]
    backtest_portfolio,
    canonical_digest,
    plan_of,
)
from factordesk.data.factors import FactorStatus
from factordesk.data.prices import (
    BatchResult,
    PriceDataError,
    PriceFailure,
    PriceHistory,
    Security,
    TickerOutcome,
)
from factordesk.report.schema import ApiError, FactorReport
from factordesk.section_hooks.context import DollarInput, MacroInput, WorldBenchmarkInput
from factordesk.section_hooks.registry import HOOKS
from factordesk.tests.fixtures.dgp import dgp_a, price_history, rng_for

NOW = datetime(2026, 11, 18, 15, 0, tzinfo=UTC)
DOWNLOADED = datetime(2026, 10, 2, 8, 30, tzinfo=UTC)
N = 1400
CUT = 30
GAP_ROW = 500


class ApiClient(Protocol):
    def post(self, url: str, **kwargs: Any) -> httpx.Response: ...


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


# --------------------------------------------------------------------------- fakes
def _history(ticker: str, seed: int, dates: pd.DatetimeIndex) -> PriceHistory:
    """Prices of ``ticker``: random daily returns on ``dates`` (the first date is its base)."""
    rng = np.random.default_rng(20261118 + seed)
    ret = rng.normal(0.0004, 0.01, size=len(dates) - 1)
    return price_history(ret, dates[1:], first_date=dates[0], ticker=ticker)


class FakeBatchProvider:
    """Serves ``histories`` through ``fetch_many`` and ``fetch_security``; counts the calls."""

    def __init__(self, histories: dict[str, PriceHistory]) -> None:
        self.histories = histories
        self.securities: dict[str, Security] = {}
        self.many_calls: list[tuple[str, ...]] = []

    def fetch(self, ticker: str) -> PriceHistory:  # pragma: no cover - the route uses fetch_many
        raise AssertionError("the portfolio route fetches in batch")

    def fetch_many(self, tickers: Sequence[str]) -> BatchResult:
        self.many_calls.append(tuple(tickers))
        outcomes: list[TickerOutcome] = []
        for ticker in tickers:
            found = self.histories.get(ticker)
            if found is None:
                outcomes.append(
                    TickerOutcome(
                        ticker, failure=PriceFailure(ticker, "no_data", f"No data for {ticker}.")
                    )
                )
            else:
                outcomes.append(TickerOutcome(ticker, history=found))
        return BatchResult(tuple(outcomes), (), 0.0)

    def fetch_security(self, ticker: str) -> Security | None:
        return self.securities.get(ticker, Security(name=ticker, currency="USD"))


@dataclass
class World:
    app: FastAPI
    provider: FakeBatchProvider
    factors: pd.DataFrame
    dates: pd.DatetimeIndex
    data_dir: Path
    extra: dict[str, Any] = field(default_factory=lambda: {})


def make_world(tmp_path: Path, load_macro: Callable[[], MacroInput] | None = None) -> World:
    d = dgp_a(rng_for(701), n=N)
    dates = pd.DatetimeIndex(d.factors.index)
    full = dates.insert(0, pd.Timestamp("2009-12-31"))
    cut = N - CUT
    factors = d.factors.iloc[:cut].copy()
    factors["Mom"] = np.random.default_rng(702).normal(0.0, 0.007, size=len(factors))
    factors.attrs = {}
    histories = {
        "AAA": _history("AAA", 1, full),
        "BBB": _history("BBB", 2, full),
        # starts 300 trading days later
        "LATE": _history("LATE", 3, full[300:]),
        # ends 700 trading days early
        "EARLY": _history("EARLY", 4, full[:700]),
        # starts after EARLY ends
        "AFTER": _history("AFTER", 5, full[900:]),
    }
    aaa = histories["AAA"]
    # the same prices as AAA with one day missing inside the window
    histories["GAP"] = dataclasses.replace(
        aaa, ticker="GAP", frame=aaa.frame.drop(aaa.frame.index[GAP_ROW])
    )
    provider = FakeBatchProvider(histories)
    status = FactorStatus(
        last_date=factors.index[-1].date(),
        first_date=factors.index[0].date(),
        days_behind=(NOW.date() - factors.index[-1].date()).days,
        last_download_at=DOWNLOADED,
        source_url="https://example.invalid/factors",
        stale=False,
    )
    deps = AppDeps(
        price_provider=provider,
        load_factors=lambda refresh, at: factors,
        factor_status=lambda at: status,
        now=lambda: NOW,
        data_dir=tmp_path,
        static_dir=None,
        load_ff6=lambda at: factors,
        load_macro=load_macro,
    )
    return World(create_app(deps), provider, factors, dates, tmp_path)


@pytest.fixture
def world(tmp_path: Path) -> World:
    return make_world(tmp_path)


@pytest.fixture
def client(world: World) -> Iterator[ApiClient]:
    with TestClient(world.app) as test_client:  # pyright: ignore[reportUnknownVariableType]
        yield cast(ApiClient, test_client)


# --------------------------------------------------------------------------- trees
def holding(i: int, ticker: str | None, weight: float, label: str | None = None) -> dict[str, Any]:
    return {
        "id": f"h{i}",
        "kind": "holding",
        "ticker": ticker,
        "label": label or (ticker or "No proxy"),
        "weight": weight,
    }


def tree(
    instruments: Sequence[dict[str, Any]], *, name: str = "My portfolio", cost_bps: float = 0.0
) -> dict[str, Any]:
    """A valid tree: every instrument in its own sub-asset class group under one asset class."""
    subs = [
        {
            "id": f"s{i}",
            "kind": "group",
            "label": f"Line {i}",
            "library_id": "eq_na_large",
            "children": [item],
        }
        for i, item in enumerate(instruments)
    ]
    return {
        "version": 1,
        "name": name,
        "cost_bps": cost_bps,
        "root": {
            "id": "root",
            "kind": "group",
            "label": "Portfolio",
            "children": [
                {"id": "ac0", "kind": "group", "label": "Equities", "children": subs},
            ],
        },
    }


def post(client: ApiClient, body: dict[str, Any], query: str = "") -> httpx.Response:
    return client.post(f"/api/report/portfolio{query}", json=body)


def report_of(response: httpx.Response) -> FactorReport:
    assert response.status_code == 200, response.text
    return FactorReport.model_validate_json(response.text)


def refused(response: httpx.Response, status: int, code: str) -> ApiError:
    assert response.status_code == status, response.text
    error = ApiError.model_validate(response.json())
    assert error.code == code
    assert error.message.endswith(".") and error.action.endswith(".")
    assert "Traceback" not in response.text
    return error


def plan_for(world: World, instruments: Sequence[dict[str, Any]]) -> Any:
    return plan_of(PortfolioTree.model_validate(tree(instruments)))


def rf_of(world: World) -> pd.Series:
    return world.factors["RF"]


def total_returns(world: World, ticker: str) -> pd.Series:
    return world.provider.histories[ticker].total_returns


# --------------------------------------------------------------------------- the backtest
def test_a_single_holding_at_100_percent_equals_the_ticker(world: World) -> None:
    plan = plan_for(world, [holding(0, "AAA", 1.0)])
    subject, summary = backtest_portfolio(plan, world.provider.histories, rf_of(world))
    expected = total_returns(world, "AAA")
    got = subject.returns
    assert len(got) == len(expected)
    np.testing.assert_allclose(got.to_numpy(), expected.to_numpy(), rtol=0, atol=1e-12)
    assert subject.kind == "portfolio" and subject.frequency == "daily"
    assert subject.label == "My portfolio"
    assert subject.source == "backtest of 1 instrument (Yahoo adjusted close)"
    assert summary.unallocated_weight == 0.0
    assert summary.window_start == expected.index[0].date()


def test_sixty_forty_first_day_return(world: World) -> None:
    plan = plan_for(world, [holding(0, "AAA", 0.6), holding(1, "BBB", 0.4)])
    subject, summary = backtest_portfolio(plan, world.provider.histories, rf_of(world))
    a, b = total_returns(world, "AAA"), total_returns(world, "BBB")
    first = subject.returns.index[0]
    assert subject.returns.iloc[0] == pytest.approx(0.6 * a[first] + 0.4 * b[first], abs=1e-12)
    assert summary.n_instruments == 2
    assert [w[2] for w in summary.weights] == [0.6, 0.4]


def test_unallocated_weight_goes_to_usd_cash(world: World) -> None:
    plan = plan_for(world, [holding(0, "AAA", 0.5)])
    subject, summary = backtest_portfolio(plan, world.provider.histories, rf_of(world))
    first = subject.returns.index[0]
    a = total_returns(world, "AAA")[first]
    rf = rf_of(world)[first]
    assert subject.returns.iloc[0] == pytest.approx(0.5 * a + 0.5 * rf, abs=1e-12)
    assert summary.unallocated_weight == pytest.approx(0.5)
    # cash earns the French RF, which ends with the factor file: it sets the window end
    assert summary.end_limited_by == ("USD cash (risk-free rate)",)
    assert summary.window_end == world.factors.index[-1].date()


def test_a_zero_weight_leaf_does_not_limit_the_window(world: World) -> None:
    plan = plan_for(
        world, [holding(0, "AAA", 1.0), holding(1, "LATE", 0.0), holding(2, "EARLY", 0.0)]
    )
    assert plan.tickers == ("AAA",)
    subject, summary = backtest_portfolio(plan, world.provider.histories, rf_of(world))
    assert summary.window_start == total_returns(world, "AAA").index[0].date()
    assert summary.window_end == total_returns(world, "AAA").index[-1].date()
    assert len(subject.returns) == len(total_returns(world, "AAA"))
    # the same leaf with a weight above 0 does limit it, and the section names it
    plan = plan_for(world, [holding(0, "AAA", 0.5), holding(1, "LATE", 0.5)])
    _, limited = backtest_portfolio(plan, world.provider.histories, rf_of(world))
    assert limited.start_limited_by == ("LATE (LATE)",)
    assert limited.window_start == total_returns(world, "LATE").index[0].date()


def test_the_same_ticker_on_two_lines_is_fetched_once_with_two_leaves(world: World) -> None:
    plan = plan_for(world, [holding(0, "AAA", 0.3), holding(1, "aaa", 0.2), holding(2, "BBB", 0.5)])
    assert plan.tickers == ("AAA", "BBB")
    subject, summary = backtest_portfolio(plan, world.provider.histories, rf_of(world))
    a, b = total_returns(world, "AAA"), total_returns(world, "BBB")
    first = subject.returns.index[0]
    assert subject.returns.iloc[0] == pytest.approx(0.5 * a[first] + 0.5 * b[first], abs=1e-12)
    assert summary.n_instruments == 3


def test_cost_and_rebalances_are_summarised(world: World) -> None:
    plan = plan_of(
        PortfolioTree.model_validate(
            tree([holding(0, "AAA", 0.6), holding(1, "BBB", 0.4)], cost_bps=10.0)
        )
    )
    _, summary = backtest_portfolio(plan, world.provider.histories, rf_of(world))
    assert summary.n_rebalances > 40
    assert summary.total_cost > 0.0 and summary.average_turnover > 0.0
    assert summary.cost_bps == 10.0


# --------------------------------------------------------------------------- the route
def test_the_route_gives_a_portfolio_report(world: World, client: ApiClient) -> None:
    body = tree([holding(0, "AAA", 0.6), holding(1, "BBB", 0.3)], name="Balanced", cost_bps=5.0)
    report = report_of(post(client, body))
    assert report.ticker == "Balanced"
    assert report.model == "ff6"  # the dashboard default
    assert report.subject is not None
    assert report.subject.kind == "portfolio"
    assert report.subject.frequency == "daily" and report.subject.periods == 252
    assert report.subject.source == "backtest of 2 instruments (Yahoo adjusted close)"
    assert report.subject.currency == "USD"
    assert report.regression is not None
    section = report.portfolio_backtest
    assert section is not None and section.status == "ok"
    assert section.n_instruments == 2
    assert section.unallocated_weight == pytest.approx(0.1)
    assert section.window_start == total_returns(world, "AAA").index[0].date()
    assert section.survivorship_note.startswith("Holdings are currently listed securities")
    assert [(w.ticker, w.weight) for w in section.weights] == [("AAA", 0.6), ("BBB", 0.3)]
    assert report.world_beta is None  # no benchmark is wired in this world
    assert report.performance is not None and report.tail_risk is not None
    assert report.alpha_strip is not None
    # one batch download, once
    assert world.provider.many_calls == [("AAA", "BBB")]


def test_a_portfolio_report_has_the_macro_section_when_macro_inputs_are_given(
    tmp_path: Path,
) -> None:
    rng = np.random.default_rng(703)
    dates = pd.bdate_range("2010-01-04", periods=N, name="date")
    funds = {
        t: WorldBenchmarkInput(
            history=price_history(rng.normal(0.0002, 0.003, size=N), dates, ticker=t)
        )
        for t in ("IEF", "LQD", "DBC", "TIP", "IEI")
    }
    levels = pd.Series(
        100.0 * np.concatenate([[1.0], np.cumprod(1.0 + rng.normal(0.0, 0.002, size=N))]),
        index=pd.DatetimeIndex([pd.Timestamp("2009-12-31"), *dates], name="date"),
    )
    macro = MacroInput(funds=funds, dollar=DollarInput(levels=levels))
    world = make_world(tmp_path, load_macro=lambda: macro)
    with TestClient(world.app) as test_client:  # pyright: ignore[reportUnknownVariableType]
        body = tree([holding(0, "AAA", 0.6), holding(1, "BBB", 0.3)], name="Balanced")
        report = report_of(post(cast(ApiClient, test_client), body))
    section = report.macro
    assert section is not None and section.status == "ok" and section.usd_included
    assert [r.label for r in section.rows][0] == "Market" and len(section.rows) == 6
    assert section.model_note.endswith("Not the headline alpha.")


def test_a_portfolio_report_has_no_macro_section_without_macro_inputs(
    client: ApiClient,
) -> None:
    body = tree([holding(0, "AAA", 0.6)], name="One")
    assert report_of(post(client, body)).macro is None


def test_ff5_and_a_range_are_accepted(client: ApiClient) -> None:
    body = tree([holding(0, "AAA", 0.5), holding(1, "BBB", 0.5)])
    ff5 = report_of(post(client, body, "?model=ff5"))
    assert ff5.model is None
    three = report_of(post(client, body, "?model=ff6&range=3Y"))
    assert three.regression is not None
    assert three.data.actual_start > report_of(post(client, body)).data.actual_start
    refused(post(client, body, "?range=3Y&start=2015-01-02"), 400, "bad_range")


def test_hooks_for_a_portfolio_subject() -> None:
    by_field = {spec.field: spec for spec in HOOKS}
    for field_name in ("performance", "tail_risk", "alpha_strip", "world_beta"):
        assert by_field[field_name].applies("portfolio", "daily", "ff6")
    for field_name in ("lead_lag", "fragility", "residual", "kalman_betas"):
        assert by_field[field_name].applies("portfolio", "daily", "ff5")
        assert not by_field[field_name].applies("portfolio", "daily", "ff6")
    assert not by_field["shrunk_betas"].applies("portfolio", "daily", "ff5")
    assert by_field["shrunk_betas"].applies("ticker", "daily", "ff5")
    backtest = by_field["portfolio_backtest"]
    assert backtest.applies("portfolio", "daily", "ff6")
    assert not backtest.applies("ticker", "daily", "ff6")
    assert not backtest.applies("upload", "monthly", "ff6")


def test_the_section_is_never_required_and_a_ticker_report_leaves_it_out() -> None:
    assert "portfolio_backtest" not in FactorReport.model_json_schema()["required"]
    mock = Path(__file__).parent / "fixtures" / "mock_report.json"
    report = FactorReport.model_validate_json(mock.read_text(encoding="utf-8"))
    assert report.portfolio_backtest is None
    assert "portfolio_backtest" not in report.model_dump_json()


# --------------------------------------------------------------------------- refusals
def test_an_unknown_ticker_is_422(client: ApiClient) -> None:
    error = refused(
        post(client, tree([holding(0, "AAA", 0.5), holding(1, "NOPE", 0.5)])), 422, "unknown_ticker"
    )
    assert "NOPE" in error.message and "AAA" not in error.message


def test_a_ticker_with_no_data_from_a_provider_without_batch_is_422(tmp_path: Path) -> None:
    world = make_world(tmp_path)

    class SingleProvider:
        def fetch(self, ticker: str) -> PriceHistory:
            if ticker == "NOPE":
                raise PriceDataError("no data")
            return world.provider.histories[ticker]

    deps = world.app.state.runtime.deps
    app = create_app(
        AppDeps(
            price_provider=SingleProvider(),
            load_factors=deps.load_factors,
            factor_status=deps.factor_status,
            now=deps.now,
            data_dir=deps.data_dir,
            static_dir=None,
            load_ff6=deps.load_ff6,
        )
    )
    with TestClient(app) as test_client:  # pyright: ignore[reportUnknownVariableType]
        api = cast(ApiClient, test_client)
        refused(post(api, tree([holding(0, "NOPE", 1.0)])), 422, "unknown_ticker")
        assert report_of(post(api, tree([holding(0, "AAA", 1.0)]))).portfolio_backtest is not None


def test_a_non_usd_ticker_is_422(world: World, client: ApiClient) -> None:
    world.provider.securities["BBB"] = Security(name="Euro fund", currency="EUR")
    error = refused(
        post(client, tree([holding(0, "AAA", 0.5), holding(1, "BBB", 0.5)])),
        422,
        "unsupported_currency",
    )
    assert "BBB" in error.message and "EUR" in error.message
    assert world.provider.many_calls == []  # refused before any price download


def test_no_common_window_is_422_and_names_the_instruments(client: ApiClient) -> None:
    error = refused(
        post(client, tree([holding(0, "EARLY", 0.5), holding(1, "AFTER", 0.5)])),
        422,
        "invalid_portfolio",
    )
    assert "share no trading period" in error.message
    assert "AFTER (AFTER) starts on" in error.message and "EARLY (EARLY) ends on" in error.message


def test_a_total_over_100_percent_is_422(client: ApiClient) -> None:
    error = refused(
        post(client, tree([holding(0, "AAA", 0.7), holding(1, "BBB", 0.5)])),
        422,
        "invalid_portfolio",
    )
    assert "120.00%" in error.message and "more than 100%" in error.message


def test_more_than_50_instruments_is_422(client: ApiClient) -> None:
    items = [holding(i, "AAA", 0.0) for i in range(51)]
    error = refused(post(client, tree(items)), 422, "invalid_portfolio")
    assert "at most 50 instruments" in error.message


def test_weight_on_a_line_with_no_proxy_is_422(client: ApiClient) -> None:
    error = refused(
        post(client, tree([holding(0, "AAA", 0.5), holding(1, None, 0.2, "Venture Capital")])),
        422,
        "invalid_portfolio",
    )
    assert "no proxy yet" in error.message


def test_an_unknown_library_line_and_an_empty_portfolio_are_422(client: ApiClient) -> None:
    body = tree([holding(0, "AAA", 1.0)])
    body["root"]["children"][0]["children"][0]["library_id"] = "no_such_line"
    assert (
        "not in the Asset Class Library"
        in refused(post(client, body), 422, "invalid_portfolio").message
    )
    cash = {"id": "c0", "kind": "cash", "ticker": None, "label": "USD Cash", "weight": 1.0}
    assert (
        "no instrument with a ticker"
        in refused(post(client, tree([cash])), 422, "invalid_portfolio").message
    )
    zero = refused(post(client, tree([holding(0, "AAA", 0.0)])), 422, "invalid_portfolio")
    assert "no instrument with a ticker" in zero.message


def test_a_malformed_tree_is_422_with_its_place(client: ApiClient) -> None:
    body = tree([holding(0, "AAA", 0.5)])
    body["root"]["children"][0]["children"][0]["children"][0]["weight"] = 1.5
    error = refused(post(client, body), 422, "invalid_portfolio")
    assert "weight" in error.message
    assert refused(client.post("/api/report/portfolio", content=b"{"), 422, "invalid_portfolio")


# --------------------------------------------------------------------------- the cache
def test_the_same_tree_is_served_from_memory(world: World, client: ApiClient) -> None:
    body = tree([holding(0, "AAA", 0.5), holding(1, "BBB", 0.5)])
    first = post(client, body)
    second = post(client, body)
    assert first.status_code == second.status_code == 200
    assert first.text == second.text
    assert len(world.provider.many_calls) == 1
    service = world.app.state.report_service
    assert len(service.portfolios) == 1
    # another weight is another tree, another model is another entry
    post(client, tree([holding(0, "AAA", 0.4), holding(1, "BBB", 0.6)]))
    post(client, body, "?model=ff5")
    assert len(world.provider.many_calls) == 3
    assert len(service.portfolios) == 3


def test_the_cache_key_is_the_sha256_of_the_canonical_tree(world: World, client: ApiClient) -> None:
    body = tree([holding(0, "AAA", 1.0)])
    post(client, body)
    digest = canonical_digest(PortfolioTree.model_validate(body))
    assert len(digest) == 64
    keys = world.app.state.report_service.portfolios.keys()
    assert [k[0] for k in keys] == [digest]
    # key order and spacing of the request do not matter
    reordered = {k: body[k] for k in reversed(list(body))}
    assert canonical_digest(PortfolioTree.model_validate(reordered)) == digest


def test_nothing_is_written_to_disk(world: World, client: ApiClient) -> None:
    before = sorted(p.relative_to(world.data_dir) for p in world.data_dir.rglob("*"))
    body = tree([holding(0, "AAA", 0.5), holding(1, "BBB", 0.5)], name="Secret plan")
    assert post(client, body).status_code == 200
    assert post(client, body).status_code == 200
    after = sorted(p.relative_to(world.data_dir) for p in world.data_dir.rglob("*"))
    assert after == before
    assert before == []


def test_a_refusal_is_not_cached(world: World, client: ApiClient) -> None:
    body = tree([holding(0, "NOPE", 1.0)])
    refused(post(client, body), 422, "unknown_ticker")
    world.provider.histories["NOPE"] = _history("NOPE", 9, world.dates)
    assert post(client, body).status_code == 200


def test_a_ticker_starting_with_a_dot_is_422(client: ApiClient) -> None:
    error = refused(post(client, tree([holding(0, ".AAA", 1.0)])), 422, "invalid_portfolio")
    assert "'.AAA' is not a valid ticker" in error.message


# --------------------------------------------------------------------------- a day missing
def test_a_missing_day_is_compounded_into_the_next_common_day(world: World) -> None:
    aaa = world.provider.histories["AAA"].frame["adj_close"]
    gap_day, before, after = aaa.index[GAP_ROW], aaa.index[GAP_ROW - 1], aaa.index[GAP_ROW + 1]
    plan = plan_for(world, [holding(0, "GAP", 0.5), holding(1, "AAA", 0.5)])
    common = _common_returns(plan, world.provider.histories, rf_of(world))
    assert gap_day not in common.leaf_ret.index and gap_day not in common.calendar
    assert common.n_dropped == 1
    expected = aaa[after] / aaa[before] - 1.0
    for key in ("i:h0", "i:h1"):  # the gap leaf and the leaf that has the day
        got = common.leaf_ret[key].to_numpy()[common.leaf_ret.index.get_loc(after)]
        assert got == pytest.approx(expected, abs=1e-12)
    # not the sum of the two daily returns
    two_days = (aaa[gap_day] / aaa[before] - 1.0) + (aaa[after] / aaa[gap_day] - 1.0)
    assert abs(expected - two_days) > 1e-9


def test_a_single_leaf_with_a_gap_has_one_return_fewer_and_no_refusal(world: World) -> None:
    aaa = world.provider.histories["AAA"].frame["adj_close"]
    plan = plan_for(world, [holding(0, "GAP", 1.0)])
    subject, summary = backtest_portfolio(plan, world.provider.histories, rf_of(world))
    full = total_returns(world, "AAA")
    assert len(subject.returns) == len(full) - 1
    after = aaa.index[GAP_ROW + 1]
    assert subject.returns[after] == pytest.approx(
        aaa[after] / aaa.iloc[GAP_ROW - 1] - 1.0, abs=1e-12
    )
    assert summary.n_dates_dropped == 0  # a lone instrument has no common-calendar loss


def test_rf_is_compounded_across_the_gap(world: World) -> None:
    aaa = world.provider.histories["AAA"].frame["adj_close"]
    gap_day, after = aaa.index[GAP_ROW], aaa.index[GAP_ROW + 1]
    plan = plan_for(world, [holding(0, "GAP", 0.5), holding(1, "AAA", 0.4)])
    rf = rf_of(world)
    common = _common_returns(plan, world.provider.histories, rf)
    assert common.rf[after] == pytest.approx((1 + rf[gap_day]) * (1 + rf[after]) - 1.0, abs=1e-15)
    plain = aaa.index[GAP_ROW + 5]
    assert common.rf[plain] == pytest.approx(rf[plain], abs=1e-15)


def test_the_route_reports_skipped_days_as_a_data_note(client: ApiClient) -> None:
    body = tree([holding(0, "GAP", 0.5), holding(1, "AAA", 0.4)])
    section = report_of(post(client, body)).portfolio_backtest
    assert section is not None
    assert section.n_dates_dropped == 1
    assert section.data_note is not None and "1 trading day" in section.data_note
    clean = report_of(post(client, tree([holding(0, "AAA", 0.5)]))).portfolio_backtest
    assert clean is not None and clean.n_dates_dropped == 0 and clean.data_note is None


# --------------------------------------------------------------------------- explicit cash
def test_an_explicit_cash_line_and_the_remainder_add_up_to_one(client: ApiClient) -> None:
    cash = {"id": "c0", "kind": "cash", "ticker": None, "label": "USD Cash", "weight": 0.15}
    body = tree([holding(0, "AAA", 0.5), holding(1, "BBB", 0.2), cash])
    section = report_of(post(client, body)).portfolio_backtest
    assert section is not None
    assert section.n_instruments == 3
    assert [(w.label, w.ticker, w.weight) for w in section.weights] == [
        ("AAA", "AAA", 0.5),
        ("BBB", "BBB", 0.2),
        ("USD Cash", None, 0.15),
    ]
    assert section.unallocated_weight == pytest.approx(0.15)
    assert sum(w.weight for w in section.weights) + section.unallocated_weight == pytest.approx(1.0)
    assert section.end_limited_by == ["USD cash (risk-free rate)"]


# --------------------------------------------------------------------------- wording
def test_the_wording_fits_a_portfolio(client: ApiClient) -> None:
    from factordesk.section_hooks.residual_alpha import caveats

    assert caveats(252)[0].startswith("You see the stock's return")
    assert caveats(252, "portfolio")[0].startswith("You see the return after removing")
    report = report_of(
        post(client, tree([holding(0, "AAA", 0.5), holding(1, "BBB", 0.5)]), "?model=ff5")
    )
    assert report.residual is not None and report.kalman_betas is not None
    assert not any("stock" in line for line in report.residual.caveats)
    assert "this series" in report.label_text["L-KTAIL"]
    assert "ticker" not in report.label_text["L-KTAIL"]
