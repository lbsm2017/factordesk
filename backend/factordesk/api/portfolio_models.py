"""The portfolio tree: the one JSON shape shared by the backend and the dashboard.

``frontend/src/portfolio/tree.ts`` mirrors this module, rule for rule. The shape is fixed:

    {version: 1, name, cost_bps, root: {id, kind: "group", label, children: [asset class groups]}}

* Level 1, an asset class group, holds sub-asset class groups.
* Level 2, a sub-asset class group, has a ``library_id`` (a line of the Asset Class Library) and
  holds instruments.
* Level 3, an instrument, is ``{id, kind: "holding" | "cash", ticker | null, label, weight}``.

Weights exist only on instruments and are decimal fractions (0.25 means 25%). The total of a
group is computed from its instruments and is never stored.

A ``cash`` instrument is the risk-free cash leaf and has no ticker. A ``holding`` has a ticker, or
none when its library line has no proxy yet; a holding without a ticker cannot take a weight.
The currency of a ticker is not checked here: the run checks it with ``check_currency``.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Final, Literal

from pydantic import Field, model_validator

from factordesk.analytics.backtest import WEIGHT_TOLERANCE
from factordesk.data.french import FactorSet
from factordesk.report.base import FrozenModel
from factordesk.report.schema import ReferenceCurrency

TREE_VERSION: Final = 1
MAX_INSTRUMENTS: Final = 50
MAX_COST_BPS: Final = 1000.0
USD_CASH_LIBRARY_ID: Final = "cash_usd"
"""Library id of the USD cash line: the unallocated remainder goes there."""
EUR_CASH_LIBRARY_ID: Final = "cash_eur"
"""Library id of the EUR cash line: the EUR view replaces its proxy (FXE) by the euro cash index."""

_TICKER_RE = re.compile(r"^[A-Za-z0-9.^=-]{1,12}$")  # same rule as data.prices.validate_ticker

Text = Annotated[str, Field(min_length=1, max_length=80)]
NodeId = Annotated[str, Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_.:-]+$")]


class Instrument(FrozenModel):
    """A leaf: one holding (a ticker) or the cash leaf, with its target weight."""

    id: NodeId
    kind: Literal["holding", "cash"]
    ticker: str | None
    label: Text
    weight: float = Field(ge=0.0, le=1.0, description="Target weight as a decimal fraction.")

    @model_validator(mode="after")
    def _check(self) -> Instrument:
        if self.kind == "cash" and self.ticker is not None:
            raise ValueError(f"cash instrument {self.id!r} cannot have a ticker")
        if self.ticker is not None and not _TICKER_RE.fullmatch(self.ticker):
            raise ValueError(f"instrument {self.id!r} has an invalid ticker {self.ticker!r}")
        if self.kind == "holding" and self.ticker is None and self.weight > 0.0:
            raise ValueError(f"instrument {self.id!r} has no proxy yet, so it cannot take a weight")
        return self


class SubAssetClassGroup(FrozenModel):
    """Level 2: one line of the library with its instruments."""

    id: NodeId
    kind: Literal["group"]
    label: Text
    library_id: NodeId
    children: list[Instrument]


class AssetClassGroup(FrozenModel):
    """Level 1: an asset class (Cash, Fixed Income, ...) with its sub-asset class groups."""

    id: NodeId
    kind: Literal["group"]
    label: Text
    children: list[SubAssetClassGroup]


class RootGroup(FrozenModel):
    id: NodeId
    kind: Literal["group"]
    label: Text
    children: list[AssetClassGroup]


class PortfolioTree(FrozenModel):
    """A named portfolio: the tree and the cost of a rebalance."""

    version: Literal[1]
    name: Text
    cost_bps: float = Field(ge=0.0, le=MAX_COST_BPS, description="Cost per unit of turnover.")
    reference_currency: ReferenceCurrency = Field(
        default="USD",
        exclude_if=lambda value: value == "USD",
        description="Currency of the backtest and of every figure of the report; left out of the "
        "JSON when USD.",
    )
    factor_set: FactorSet = Field(
        default="us",
        exclude_if=lambda value: value == "us",
        description="Regional Fama-French factor set of the report: us (default) or europe "
        "(Developed Europe, in US dollars); left out of the JSON when us.",
    )
    root: RootGroup

    @model_validator(mode="after")
    def _check(self) -> PortfolioTree:
        seen: set[str] = set()
        nodes: list[str] = [self.root.id]
        for ac in self.root.children:
            nodes.append(ac.id)
            for sub in ac.children:
                nodes.append(sub.id)
                nodes.extend(i.id for i in sub.children)
        for node_id in nodes:
            if node_id in seen:
                raise ValueError(f"id {node_id!r} is used twice")
            seen.add(node_id)
        count = sum(1 for _ in self.instruments())
        if count > MAX_INSTRUMENTS:
            raise ValueError(f"at most {MAX_INSTRUMENTS} instruments are allowed, got {count}")
        total = self.total_weight
        if total > 1.0 + WEIGHT_TOLERANCE:
            raise ValueError(f"the weights add up to {total:.2%}, which is more than 100%")
        return self

    def instruments(self) -> Iterator[Instrument]:
        for ac in self.root.children:
            for sub in ac.children:
                yield from sub.children

    @property
    def total_weight(self) -> float:
        return sum(i.weight for i in self.instruments())

    @property
    def remainder(self) -> float:
        """The unallocated weight, 0.0 when within tolerance of 100%."""
        rest = 1.0 - self.total_weight
        return rest if rest > WEIGHT_TOLERANCE else 0.0

    def notices(self) -> list[str]:
        """Plain-words notices for a valid tree (never errors)."""
        rest = self.remainder
        if rest > 0.0:
            return [f"{rest:.2%} is not allocated; it is held in USD cash."]
        return []


# --------------------------------------------------------------------------- Asset Class Library

LIBRARY_PATH: Final = Path(__file__).resolve().parents[1] / "data" / "asset_class_library.json"
RISK_FREE_PROXY: Final = "RF"
"""Proxy value of the USD cash line: the French risk-free rate, not a ticker."""

ProxyKind = Literal["etf", "risk_free", "listed_proxy", "none"]


class LibraryLine(FrozenModel):
    """One sub-asset class of the owner's Asset Class Library and the proxy that stands for it."""

    id: NodeId
    asset_class: Text
    sub_asset_class: Text
    proxy: str | None = Field(
        description='A ticker, "RF" for the risk-free rate, or null when there is no proxy yet.'
    )
    proxy_kind: ProxyKind
    note: str = Field(min_length=1, description="The caveat a reader should see with the proxy.")
    first_date: date | None = Field(description="First daily price date of the proxy.")
    currency: str | None = Field(description="Quote currency of the proxy.")
    hedge_eur: bool = Field(
        default=False,
        description="True for a bond line with only US-dollar underlying: the EUR view hedges it "
        "to euros (its return above US cash, plus euro cash).",
    )
    multi_currency: bool = Field(
        default=False,
        description="True for a bond fund that holds several currencies: the EUR view leaves it "
        "unhedged and says so.",
    )

    @model_validator(mode="after")
    def _check(self) -> LibraryLine:
        if (self.proxy is None) != (self.proxy_kind == "none"):
            raise ValueError(f"line {self.id!r}: proxy is null exactly when proxy_kind is none")
        if (self.proxy == RISK_FREE_PROXY) != (self.proxy_kind == "risk_free"):
            raise ValueError(f"line {self.id!r}: RF goes with proxy_kind risk_free only")
        if (
            self.proxy is not None
            and self.proxy != RISK_FREE_PROXY
            and not _TICKER_RE.fullmatch(self.proxy)
        ):
            raise ValueError(f"line {self.id!r} has an invalid proxy {self.proxy!r}")
        if (self.first_date is None) != (self.proxy is None):
            raise ValueError(f"line {self.id!r}: first_date is null exactly when proxy is null")
        return self


class AssetClassLibrary(FrozenModel):
    """The library: lines in the owner's order, grouped by asset class."""

    version: Literal[1]
    lines: list[LibraryLine]

    @model_validator(mode="after")
    def _check(self) -> AssetClassLibrary:
        ids = [line.id for line in self.lines]
        if len(set(ids)) != len(ids):
            raise ValueError("library line ids must be unique")
        return self


@lru_cache(maxsize=1)
def load_library() -> AssetClassLibrary:
    """The library from ``data/asset_class_library.json`` (read once)."""
    return AssetClassLibrary.model_validate_json(LIBRARY_PATH.read_text(encoding="utf-8"))
