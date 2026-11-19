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
from typing import Annotated, Final, Literal

from pydantic import Field, model_validator

from factordesk.analytics.backtest import WEIGHT_TOLERANCE
from factordesk.report.base import FrozenModel

TREE_VERSION: Final = 1
MAX_INSTRUMENTS: Final = 50
MAX_COST_BPS: Final = 1000.0
USD_CASH_LIBRARY_ID: Final = "cash_usd"
"""Library id of the USD cash line: the unallocated remainder goes there."""

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
            raise ValueError(
                f"instrument {self.id!r} has no proxy yet, so it cannot take a weight"
            )
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
