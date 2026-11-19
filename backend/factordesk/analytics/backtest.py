"""Backtest of a fixed-target-weight portfolio with drift and month-end rebalancing.

Pure functions, no I/O (research notes B1, B3 and B6). Every return is a simple daily total
return in decimals.

Leaves and cash
    Each input column is one leaf (a holding). Target weights are ``>= 0`` and sum to at most 1.
    The weight that is not allocated, ``1 - sum(target)``, goes to the cash leaf ``CASH_ID``, which
    earns the daily risk-free rate ``rf`` (decimal, so the French percent file is divided by 100
    before it reaches this module). The cash leaf is always present, with a target of 0 when the
    targets sum to 1. Weights below always include cash and sum to 1.

Common window (B6)
    The backtest runs only on dates where every leaf has a return: from the latest first date to
    the earliest last date. ``start_leaves`` and ``end_leaves`` name the leaves that set those two
    dates (several on a tie). Cash takes part (as ``rf``) only when its target weight is above 0;
    with a zero cash target ``rf`` is not used, does not limit the window, and the cash column
    holds 0.0 (a zero weight never earns anything and drift keeps it at zero). A missing value
    inside the window is an error, never a dropped or filled row. History is never backfilled
    with proxies.

Daily mechanics (B1)
    ``w_{t-1}`` are the weights at the close of day ``t - 1`` after any rebalance
    (``applied_weights``). The gross portfolio return is
    ``g_t = sum_i w_{i,t-1} * r_{i,t}`` and the weights drift to
    ``w_{i,t} = w_{i,t-1} * (1 + r_{i,t}) / (1 + g_t)``, renormalised to sum to 1
    (``drifted_weights``, the close of day ``t`` before any rebalance).

Rebalancing
    At the close of the last common trading day of each calendar month the weights are reset to
    target. The reset applies to the next day's return, so no return uses a weight chosen with
    that day's information. The month that holds the last date of the window never rebalances
    (it is partial, and a trade on the final close could not affect any return).

Turnover and cost
    One-way turnover on a rebalance day is ``tau_t = 1/2 * sum_i |w_target_i - w_{i,t}|`` over
    all legs, cash included; it is reported as is. The cost is charged on the traded securities
    only: ``k_t = sum_{i != cash} |w_target_i - w_{i,t}| * cost_bps / 10_000``. Every buy and
    every sell of a holding pays ``cost_bps``; the cash leg pays nothing, because cash is where
    the trades settle, not a trade. So a rebalance between two holdings costs
    ``2 * tau_t * cost_bps / 10_000`` and one between a holding and cash costs
    ``tau_t * cost_bps / 10_000``. ``k_t`` is a fraction of the portfolio's value at that close,
    charged on rebalance days only. The net return of that day is
    ``r_t = (1 + g_t) * (1 - k_t) - 1``, so the cost's effect on the day's return is
    ``r_t - g_t = -k_t * (1 + g_t)``. **The initial purchase is free**: the portfolio starts at
    target weights at the close before the first common date, with no cost charged.

Survivorship (B3)
    Every result carries ``SURVIVORSHIP_NOTE``.

Inputs are not mutated. Non-finite values, a return at or below -100%, a bad date index, unknown
or negative weights, or a window with no common date raise ``ValueError`` (``TypeError`` for a
non-datetime index).
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from types import MappingProxyType
from typing import cast

import numpy as np
import pandas as pd
from numpy.typing import NDArray

from factordesk.analytics.sample import validate_date_index

FloatArray = NDArray[np.float64]

CASH_ID = "cash"
"""Leaf id of the cash holding that earns the risk-free rate."""
BPS = 10_000.0
"""Basis points in one unit."""
WEIGHT_TOLERANCE = 1e-9
"""Target weights may sum to at most ``1 + WEIGHT_TOLERANCE`` (rounding in user input). When
``1 - sum(target) <= WEIGHT_TOLERANCE`` the cash weight is exactly 0 and the leaf targets are
scaled to sum to 1."""
SURVIVORSHIP_NOTE = (
    "Holdings are currently listed securities. Past delisted, merged or liquidated peers are "
    "excluded, which tends to overstate historical returns, more so for small caps, long "
    "histories and concentrated portfolios."
)
"""Fixed warning carried by every backtest (research notes B3)."""


@dataclass(frozen=True)
class BacktestResult:
    """Output of :func:`run_backtest`. Every frame and series is indexed by the common dates."""

    leaf_ids: tuple[str, ...]
    """Input leaves in input order, then ``CASH_ID``."""
    target_weights: Mapping[str, float]
    """Target weight of every leaf, cash included; sums to 1."""
    cost_bps: float
    leaf_ret: pd.DataFrame
    """Daily simple return of every leaf over the window; the cash column is ``rf``, or 0.0 when
    the cash target is 0."""
    gross_ret: pd.Series
    """``g_t``: portfolio return before cost."""
    ret: pd.Series
    """``r_t``: portfolio return after cost (equal to ``gross_ret`` off rebalance days)."""
    applied_weights: pd.DataFrame
    """``w_{t-1}``: the weights that earn day ``t``'s return (after the previous close's
    rebalance). The first row is the target."""
    drifted_weights: pd.DataFrame
    """``w_t``: weights at the close of day ``t`` after drift, before any rebalance."""
    rebalance_dates: tuple[date, ...]
    """Closes at which the weights were reset to target."""
    turnover: pd.Series
    """One-way turnover ``tau_t`` over all legs, cash included; 0.0 on days without a
    rebalance."""
    cost: pd.Series
    """``k_t = sum_{i != cash} |w_target_i - w_{i,t}| * cost_bps / 10_000``, a fraction of the
    value at that close; 0.0 off rebalance days."""
    start: date
    end: date
    start_leaves: tuple[str, ...]
    """Leaves whose first return is ``start`` (they limit the window's start)."""
    end_leaves: tuple[str, ...]
    """Leaves whose last return is ``end`` (they limit the window's end)."""
    survivorship_note: str

    @property
    def n(self) -> int:
        return len(self.ret)


def _as_date(value: object) -> date:
    return pd.Timestamp(cast(str, value)).date()


def _targets(target_weights: Mapping[str, float], leaf_ids: list[str]) -> dict[str, float]:
    unknown = sorted(set(target_weights) - set(leaf_ids))
    missing = [leaf for leaf in leaf_ids if leaf not in target_weights]
    if unknown or missing:
        raise ValueError(
            f"target weights do not match the leaves: unknown {unknown}, missing {missing}"
        )
    out: dict[str, float] = {}
    for leaf in leaf_ids:
        w = float(target_weights[leaf])
        if not math.isfinite(w) or w < 0.0:
            raise ValueError(f"target weight of {leaf!r} must be finite and >= 0, got {w}")
        out[leaf] = w
    total = math.fsum(out.values())
    if total > 1.0 + WEIGHT_TOLERANCE:
        raise ValueError(f"target weights sum to {total}, more than 1")
    cash = 1.0 - total
    if cash <= WEIGHT_TOLERANCE:
        # Fully invested up to rounding: cash is exactly 0 and the leaves are scaled to sum to 1.
        out = {leaf: w / total for leaf, w in out.items()}
        out[CASH_ID] = 0.0
        return out
    out[CASH_ID] = cash
    return out


def _window(frame: pd.DataFrame) -> tuple[pd.DataFrame, tuple[str, ...], tuple[str, ...]]:
    """Rows from the latest first-valid date to the earliest last-valid date, and the leaves
    that set each bound."""
    firsts: dict[str, pd.Timestamp] = {}
    lasts: dict[str, pd.Timestamp] = {}
    index = pd.DatetimeIndex(frame.index)
    for leaf in frame.columns:
        valid = np.flatnonzero(frame[leaf].notna().to_numpy())
        if len(valid) == 0:
            raise ValueError(f"leaf {leaf!r} has no return")
        firsts[str(leaf)] = index[int(valid[0])]
        lasts[str(leaf)] = index[int(valid[-1])]
    start = max(firsts.values())
    end = min(lasts.values())
    if start > end:
        raise ValueError(
            f"the leaves share no common date (latest start {start.date()}, "
            f"earliest end {end.date()})"
        )
    window = frame.loc[start:end]
    holes = window.isna()
    if bool(holes.to_numpy().any()):
        leaf = str(holes.any().idxmax())
        first_hole = _as_date(holes[leaf].idxmax())
        raise ValueError(f"leaf {leaf!r} has no return on {first_hole}, inside the common window")
    start_leaves = tuple(leaf for leaf, d in firsts.items() if d == start)
    end_leaves = tuple(leaf for leaf, d in lasts.items() if d == end)
    return window, start_leaves, end_leaves


def rebalance_mask(index: pd.DatetimeIndex) -> NDArray[np.bool_]:
    """True at the last date of each calendar month in ``index``, except the month of the last
    date (partial month, no rebalance)."""
    period = index.to_period("M")
    month = np.asarray(period.asi8, dtype=np.int64)
    mask = np.zeros(len(index), dtype=bool)
    if len(index) > 1:
        mask[:-1] = month[1:] != month[:-1]
    return mask


def run_backtest(
    leaf_ret: pd.DataFrame,
    target_weights: Mapping[str, float],
    rf: pd.Series,
    cost_bps: float = 0.0,
) -> BacktestResult:
    """Backtest ``target_weights`` over the common window of ``leaf_ret`` (module docstring).

    ``leaf_ret`` holds one column of daily simple total returns per leaf id; leading and trailing
    NaN mark dates before a leaf's history starts or after it ends. ``rf`` is the daily
    risk-free rate in decimals; when cash has a target weight above 0 it is the return of the cash
    leaf and limits the window like any other leaf, otherwise it is not used. ``cost_bps`` is
    charged on the traded value of the securities at each rebalance (the cash leg is free); the
    initial purchase is free.
    """
    validate_date_index(leaf_ret.index, "leaf returns")
    validate_date_index(rf.index, "risk-free rate")
    leaf_ids = [str(c) for c in leaf_ret.columns]
    if not leaf_ids:
        raise ValueError("at least one leaf is required")
    if len(set(leaf_ids)) != len(leaf_ids):
        raise ValueError("leaf ids must be unique")
    if CASH_ID in leaf_ids:
        raise ValueError(f"{CASH_ID!r} is reserved for the cash leaf")
    if not math.isfinite(cost_bps) or cost_bps < 0.0:
        raise ValueError(f"cost_bps must be finite and >= 0, got {cost_bps}")
    targets = _targets(target_weights, leaf_ids)
    ids = (*leaf_ids, CASH_ID)

    frame = leaf_ret.astype("float64").copy()
    frame.columns = pd.Index(leaf_ids)
    cash_held = targets[CASH_ID] > 0.0
    if cash_held:
        frame[CASH_ID] = rf.astype("float64").reindex(frame.index)
    window, start_leaves, end_leaves = _window(frame)
    if not cash_held:
        window = window.copy()
        window[CASH_ID] = 0.0
    values = window.to_numpy(dtype=np.float64)
    if not bool(np.isfinite(values).all()):
        raise ValueError("a return in the common window is not finite")
    if bool((values <= -1.0).any()):
        raise ValueError("a daily return is at or below -100%")

    index = pd.DatetimeIndex(window.index, name="date")
    n, m = values.shape
    target = np.array([targets[leaf] for leaf in ids], dtype=np.float64)
    rebalance = rebalance_mask(index)

    applied = np.empty((n, m), dtype=np.float64)
    drifted = np.empty((n, m), dtype=np.float64)
    gross = np.empty(n, dtype=np.float64)
    net = np.empty(n, dtype=np.float64)
    turnover = np.zeros(n, dtype=np.float64)
    cost = np.zeros(n, dtype=np.float64)
    w = target.copy()
    for t in range(n):
        applied[t] = w
        g = float(w @ values[t])
        grown = w * (1.0 + values[t])
        w_drift = grown / grown.sum()
        drifted[t] = w_drift
        gross[t] = g
        if rebalance[t]:
            turnover[t] = 0.5 * float(np.abs(target - w_drift).sum())
            traded = float(np.abs(target[:-1] - w_drift[:-1]).sum())  # cash is the last leg
            cost[t] = traded * cost_bps / BPS
            w = target.copy()
        else:
            w = w_drift
        net[t] = (1.0 + g) * (1.0 - cost[t]) - 1.0 if cost[t] != 0.0 else g

    columns = pd.Index(ids)
    return BacktestResult(
        leaf_ids=ids,
        target_weights=MappingProxyType(dict(zip(ids, (float(x) for x in target), strict=True))),
        cost_bps=float(cost_bps),
        leaf_ret=pd.DataFrame(values, index=index, columns=columns),
        gross_ret=pd.Series(gross, index=index, name="gross_ret"),
        ret=pd.Series(net, index=index, name="ret"),
        applied_weights=pd.DataFrame(applied, index=index, columns=columns),
        drifted_weights=pd.DataFrame(drifted, index=index, columns=columns),
        rebalance_dates=tuple(_as_date(d) for d in index[rebalance]),
        turnover=pd.Series(turnover, index=index, name="turnover"),
        cost=pd.Series(cost, index=index, name="cost"),
        start=_as_date(index[0]),
        end=_as_date(index[-1]),
        start_leaves=start_leaves,
        end_leaves=end_leaves,
        survivorship_note=SURVIVORSHIP_NOTE,
    )
