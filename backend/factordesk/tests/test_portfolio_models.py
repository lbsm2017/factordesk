"""Portfolio tree models, the Asset Class Library and its route (offline)."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from factordesk.api.main import create_app
from factordesk.api.portfolio_models import (
    LIBRARY_PATH,
    MAX_INSTRUMENTS,
    AssetClassLibrary,
    PortfolioTree,
    load_library,
)
from factordesk.tests.test_api_basic import _no_network as _no_network  # pyright: ignore[reportPrivateUsage]
from factordesk.tests.test_api_basic import make_deps, serve


def inst(
    id: str, weight: float, ticker: str | None = "SPY", kind: str = "holding"
) -> dict[str, Any]:
    return {"id": id, "kind": kind, "ticker": ticker, "label": id, "weight": weight}


def tree_of(instruments: list[dict[str, Any]], *, cost_bps: float = 5.0) -> dict[str, Any]:
    return {
        "version": 1,
        "name": "Test",
        "cost_bps": cost_bps,
        "root": {
            "id": "root",
            "kind": "group",
            "label": "Test",
            "children": [
                {
                    "id": "ac",
                    "kind": "group",
                    "label": "Equities",
                    "children": [
                        {
                            "id": "sub",
                            "kind": "group",
                            "label": "Equity Global",
                            "library_id": "eq_global",
                            "children": instruments,
                        }
                    ],
                }
            ],
        },
    }


def test_valid_tree_round_trips() -> None:
    raw = tree_of([inst("a", 0.6), inst("b", 0.4, "AGG")])
    tree = PortfolioTree.model_validate(raw)
    assert tree.total_weight == pytest.approx(1.0)
    assert tree.remainder == 0.0
    assert tree.notices() == []
    assert json.loads(tree.model_dump_json()) == raw


def test_remainder_goes_to_usd_cash_with_a_notice() -> None:
    tree = PortfolioTree.model_validate(tree_of([inst("a", 0.6)]))
    assert tree.remainder == pytest.approx(0.4)
    assert tree.notices() == ["40.00% is not allocated; it is held in USD cash."]


def test_empty_tree_is_valid_and_all_cash() -> None:
    tree = PortfolioTree.model_validate(tree_of([]))
    assert tree.remainder == pytest.approx(1.0)


def test_total_within_tolerance_is_valid() -> None:
    tree = PortfolioTree.model_validate(tree_of([inst("a", 0.3), inst("b", 0.3), inst("c", 0.4)]))
    assert tree.remainder == 0.0


@pytest.mark.parametrize(
    ("instruments", "fragment"),
    [
        ([inst("a", -0.1)], "greater than or equal to 0"),
        ([inst("a", 0.7), inst("b", 0.4)], "more than 100%"),
        ([inst("a", 1.5)], "less than or equal to 1"),
        ([inst("a", 0.1, ticker=None)], "no proxy yet"),
        ([inst("a", 0.1, ticker="SPY", kind="cash")], "cannot have a ticker"),
        ([inst("a", 0.1, ticker="bad ticker!")], "invalid ticker"),
        ([inst("a", 0.1), inst("a", 0.1)], "used twice"),
        ([inst("a", float("nan"))], "finite"),
    ],
)
def test_invalid_trees_are_refused(instruments: list[dict[str, Any]], fragment: str) -> None:
    with pytest.raises(ValidationError) as err:
        PortfolioTree.model_validate(tree_of(instruments))
    assert fragment in str(err.value)


def test_no_proxy_row_with_zero_weight_and_cash_without_ticker_are_valid() -> None:
    tree = PortfolioTree.model_validate(
        tree_of([inst("a", 0.0, ticker=None), inst("c", 0.5, ticker=None, kind="cash")])
    )
    assert tree.total_weight == 0.5


def test_same_ticker_in_two_lines_is_allowed() -> None:
    raw = tree_of([inst("a", 0.3, "SPY")])
    second = copy.deepcopy(raw["root"]["children"][0]["children"][0])
    second.update(id="sub2", library_id="eq_na_large")
    second["children"] = [inst("b", 0.3, "SPY")]
    raw["root"]["children"][0]["children"].append(second)
    assert PortfolioTree.model_validate(raw).total_weight == pytest.approx(0.6)


def test_at_most_50_instruments() -> None:
    ok = tree_of([inst(f"i{n}", 0.0) for n in range(MAX_INSTRUMENTS)])
    PortfolioTree.model_validate(ok)
    too_many = tree_of([inst(f"i{n}", 0.0) for n in range(MAX_INSTRUMENTS + 1)])
    with pytest.raises(ValidationError, match="at most 50"):
        PortfolioTree.model_validate(too_many)


@pytest.mark.parametrize("cost", [-1.0, 1000.5])
def test_cost_bps_bounds(cost: float) -> None:
    with pytest.raises(ValidationError):
        PortfolioTree.model_validate(tree_of([], cost_bps=cost))


def test_unknown_keys_and_wrong_version_are_refused() -> None:
    raw = tree_of([inst("a", 0.5)])
    with pytest.raises(ValidationError):
        PortfolioTree.model_validate({**raw, "extra": 1})
    with pytest.raises(ValidationError):
        PortfolioTree.model_validate({**raw, "version": 2})


# ------------------------------------------------------------------------------------ library

EXPECTED_ORDER = [
    ("Cash", ["EUR Cash", "USD Cash", "CHF Cash"]),
    (
        "Fixed Income",
        [
            "European Government Bonds",
            "European Corporate Investment Grade Bonds",
            "European High Yield Bonds",
            "N. American Government Bonds",
            "N. American Corporate Investment Grade Bonds",
            "N. American High Yield Bonds",
            "Global Bonds",
            "Global High Yield Bonds",
            "Emerging Market Bonds",
            "Inflation Linked Bonds",
            "Inflation Linked Bonds (TIPS)",
        ],
    ),
    (
        "Equities",
        [
            "Equity Europe - Large Cap",
            "Equity Europe - Sm/Mid Cap",
            "Equity Switzerland",
            "Equity UK",
            "Equity N. America - Large Cap",
            "Equity N. America - Sm/Mid Cap",
            "Equity USA - Small Cap",
            "Equity Japan and Pacific",
            "Equity Emerging Markets",
            "Equity China",
            "Equity Global",
            "Equity Thematic",
        ],
    ),
    (
        "Alternatives",
        [
            "Private Equity",
            "Venture Capital",
            "Secondaries",
            "Direct Investments",
            "Private Credit",
            "Hedge Funds",
            "Real Estate",
            "Real Estate Funds",
            "Real Assets / Infrastructure",
            "Crypto/Digital Assets",
        ],
    ),
    ("Real Estate", ["Direct Real Estate", "Real Estate Funds"]),
    (
        "Commodities",
        [
            "Gold",
            "Silver",
            "Copper",
            "Global Commodities",
            "Global commodities (ex- precious metal)",
        ],
    ),
    ("Other assets", ["Own Company Stake"]),
]


def test_library_has_44_lines_in_the_given_order() -> None:
    lines = load_library().lines
    assert len(lines) == 44
    expected = [(ac, sub) for ac, subs in EXPECTED_ORDER for sub in subs]
    assert [(line.asset_class, line.sub_asset_class) for line in lines] == expected


def test_library_proxy_rules() -> None:
    by_id = {line.id: line for line in load_library().lines}
    assert by_id["cash_usd"].proxy == "RF" and by_id["cash_usd"].proxy_kind == "risk_free"
    no_proxy = {line.id for line in by_id.values() if line.proxy is None}
    assert no_proxy == {
        "alt_vc",
        "alt_secondaries",
        "alt_direct",
        "alt_real_estate_funds",
        "re_direct",
        "re_funds",
        "com_global_ex_precious",
        "other_own_company",
    }
    listed = {line.id for line in by_id.values() if line.proxy_kind == "listed_proxy"}
    assert listed == {
        "alt_pe",
        "alt_private_credit",
        "alt_hedge",
        "alt_real_estate",
        "alt_real_assets",
        "alt_crypto",
    }
    assert all(
        by_id[i].note == "listed proxy: smoother private returns not captured" for i in listed
    )
    assert all(line.currency == "USD" for line in by_id.values() if line.proxy is not None)


def test_library_file_is_what_the_models_accept() -> None:
    text = LIBRARY_PATH.read_text(encoding="utf-8")
    assert AssetClassLibrary.model_validate_json(text) == load_library()


def test_library_rejects_a_proxy_kind_that_contradicts_the_proxy() -> None:
    raw = json.loads(LIBRARY_PATH.read_text(encoding="utf-8"))
    raw["lines"][0]["proxy"] = None
    with pytest.raises(ValidationError, match="proxy is null exactly when"):
        AssetClassLibrary.model_validate_json(json.dumps(raw))


def test_library_route_returns_the_library(tmp_path: Path) -> None:
    deps, _fake, _provider = make_deps(tmp_path)
    with serve(create_app(deps)) as client:
        response = client.get("/api/portfolio/library")
    assert response.status_code == 200
    body = response.json()
    assert body["version"] == 1
    assert len(body["lines"]) == 44
    assert body["lines"][0]["id"] == "cash_eur"
    assert body == json.loads(load_library().model_dump_json())
