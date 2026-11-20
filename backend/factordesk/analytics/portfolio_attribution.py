"""Return contribution and risk share per leaf of a backtested portfolio, and group roll-ups.

Pure functions, no I/O (research notes B4 and B5). Input is a
:class:`~factordesk.analytics.backtest.BacktestResult`.

Rows
    One row per leaf (``CASH_ID`` included) and one ``COST_ID`` row for trading cost.

Daily contribution
    ``c_{i,t} = w_{i,t-1} * r_{i,t}`` with the applied (start-of-day) weights. The cost row is
    ``c_{cost,t} = r_t - g_t = -k_t * (1 + g_t)`` (net minus gross return), 0.0 off rebalance
    days. The rows of one day sum to the net portfolio return ``r_t``.

Linked contribution (Frongello 2002)
    ``C_i = sum_t c_{i,t} * (1 + R_{t-1})`` where ``R_{t-1} = prod_{s<t}(1 + r_s) - 1`` is the
    portfolio's cumulative net return up to the previous day (``R_0 = 0``). Because
    ``r_t * (1 + R_{t-1}) = (1 + R_t) - (1 + R_{t-1})`` the sum telescopes, so
    ``sum_i C_i = prod_t (1 + r_t) - 1`` exactly (up to rounding). Summing daily contributions
    without the factor would not compound and is not offered.

Risk share (ex post)
    ``s_i = Cov(c_{i,t}, r_t) / Var(r_t)``, sample moments over the window. Covariance is linear
    and ``sum_i c_{i,t} = r_t``, so ``sum_i s_i = 1``. Cash and cost are rows of their own. It
    uses the realised drifted weights and needs no covariance-matrix estimate. A share can be
    negative (a hedge). It is ``None`` with a reason when there are fewer than ``MIN_RISK_OBS``
    days or the portfolio return does not vary.

Roll-up
    :func:`roll_up` sums any per-row value over groups. Each row maps to a path such as
    ``("Equities", "USA")``; the row then counts in ``()`` (the whole portfolio),
    ``("Equities",)`` and ``("Equities", "USA")``. Every row needs a path, so nothing is dropped
    silently.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

import numpy as np
import pandas as pd

from factordesk.analytics.backtest import BacktestResult

COST_ID = "cost"
"""Row id of the trading-cost line."""
MIN_RISK_OBS = 2
"""Fewest daily returns for a sample variance."""
VAR_FLOOR = 1e-16
"""A daily variance below this (a daily sd below 1e-8, as ``performance.SD_FLOOR``) is zero."""

GroupPath = tuple[str, ...]


@dataclass(frozen=True)
class PortfolioAttribution:
    """Output of :func:`attribute`."""

    row_ids: tuple[str, ...]
    """The backtest's leaves (cash last among them), then ``COST_ID``."""
    daily_contribution: pd.DataFrame
    """``c_{i,t}``, one column per row; each row of the frame sums to ``r_t``."""
    contribution: Mapping[str, float]
    """Frongello-linked contribution ``C_i`` of every row."""
    total_return: float
    """``prod_t (1 + r_t) - 1``, the net compounded return over the window."""
    risk_share: Mapping[str, float] | None
    """``Cov(c_i, r) / Var(r)`` of every row; ``None`` when not defined (``risk_share_reason``)."""
    risk_share_reason: str | None


@dataclass(frozen=True)
class RollUp:
    """Output of :func:`roll_up`."""

    totals: Mapping[GroupPath, float]
    """Sum over the rows of each group; ``()`` is the whole portfolio."""
    members: Mapping[GroupPath, tuple[str, ...]]
    """Row ids counted in each group, in input order."""


def attribute(result: BacktestResult, *, days: pd.Index[Any] | None = None) -> PortfolioAttribution:
    """Linked return contribution and ex-post risk share of every leaf, cash and cost.

    ``days`` are the exact days that count, for a report whose analysed window is shorter than the
    backtest or leaves out days of it (the analysis sample). Linking restarts at the first of them
    (``R_0 = 0``) and the weights that earn each day stay the backtest's own, so the first day uses
    the weights as drifted until then. Without ``days`` every day of the backtest counts. Raises
    ``ValueError`` when no day is left.
    """
    kept = result.ret.index if days is None else days
    ret = result.ret.loc[kept]
    if len(ret) == 0:
        raise ValueError("no day of the backtest falls inside the window")
    index = ret.index
    applied = result.applied_weights.loc[kept]
    leaf_ret = result.leaf_ret.loc[kept]
    gross = result.gross_ret.loc[kept]
    leaf_part = applied.to_numpy() * leaf_ret.to_numpy()
    cost_part = ret.to_numpy() - gross.to_numpy()
    daily = np.column_stack([leaf_part, cost_part])
    row_ids = (*result.leaf_ids, COST_ID)

    net = ret.to_numpy(dtype=np.float64)
    growth = np.cumprod(1.0 + net)
    prior_growth = np.concatenate([[1.0], growth[:-1]])
    linked = (daily * prior_growth[:, None]).sum(axis=0)
    total = float(growth[-1] - 1.0)

    share: Mapping[str, float] | None = None
    reason: str | None = None
    n = len(net)
    if n < MIN_RISK_OBS:
        reason = f"Risk shares are not shown: {n} daily return, at least {MIN_RISK_OBS} are needed."
    else:
        var = float(np.var(net, ddof=1))
        if var < VAR_FLOOR:
            reason = "Risk shares are not shown: the portfolio return does not vary."
        else:
            centred = net - net.mean()
            cov = ((daily - daily.mean(axis=0)) * centred[:, None]).sum(axis=0) / (n - 1)
            share = MappingProxyType(
                {row: float(v) for row, v in zip(row_ids, cov / var, strict=True)}
            )

    return PortfolioAttribution(
        row_ids=row_ids,
        daily_contribution=pd.DataFrame(daily, index=index, columns=pd.Index(row_ids)),
        contribution=MappingProxyType(
            {row: float(v) for row, v in zip(row_ids, linked, strict=True)}
        ),
        total_return=total,
        risk_share=share,
        risk_share_reason=reason,
    )


def roll_up(values: Mapping[str, float], paths: Mapping[str, GroupPath]) -> RollUp:
    """Sum ``values`` over every group prefix of ``paths`` (module docstring).

    ``values`` and ``paths`` must have the same row ids. A path is a tuple of non-empty group
    names; the empty path ``()`` puts a row directly under the whole portfolio. Sums use
    ``math.fsum``.
    """
    unknown = sorted(set(paths) - set(values))
    missing = sorted(set(values) - set(paths))
    if unknown or missing:
        raise ValueError(
            f"paths do not match the rows: no value for {unknown}, no path for {missing}"
        )
    parts: dict[GroupPath, list[float]] = {}
    members: dict[GroupPath, list[str]] = {}
    for row, value in values.items():
        path = tuple(paths[row])
        if any(not name for name in path):
            raise ValueError(f"path of {row!r} must hold non-empty group names, got {path}")
        v = float(value)
        if not math.isfinite(v):
            raise ValueError(f"value of {row!r} is not finite")
        for depth in range(len(path) + 1):
            group = path[:depth]
            parts.setdefault(group, []).append(v)
            members.setdefault(group, []).append(row)
    if not parts:
        parts[()] = []
        members[()] = []
    return RollUp(
        totals=MappingProxyType({g: math.fsum(vs) for g, vs in parts.items()}),
        members=MappingProxyType({g: tuple(rs) for g, rs in members.items()}),
    )
