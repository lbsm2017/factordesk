"""Historical performance of the analysed stock: growth, volatility, Sharpe ratio, drawdowns.

Pure functions, no I/O. Every statistic is computed over the analysed sample ``S`` (methodology
M2): the same rows as the factor regression, so the numbers move with the date range.
Annualisation uses ``A = periods``, the number of observations a year: 252 for daily data (M0),
12 for monthly data. Every formula below holds for either frequency; "daily" reads "per period"
for a monthly series, and day counts of the drawdown are then month counts.

Inputs and definitions (owner-approved wording of 2026-11-18; they are proposals for
``docs/methodology.md`` until the owner folds them in, see the hand-off document):

* ``r_t`` is the stock's simple daily total return, ``AnalysisSample.ret`` (from adjusted close,
  M1.3). The regression's excess return is ``x_t = r_t - RF_t`` (M2 step 5), so
  ``r_t = x_t + RF_t``; this module takes ``ret`` and ``rf`` and forms ``x_t = r_t - RF_t`` the
  same way the sample does.
* Return a year: the compound annual growth rate ``CAGR = (prod(1 + r_t))^(A / n) - 1``. Also the
  cumulative total return ``prod(1 + r_t) - 1`` and the arithmetic mean ``A * mean(r_t)``.
* Volatility a year: ``sqrt(A) * sd(r_t)``, sample standard deviation (``ddof = 1``).
* Sharpe ratio: ``sqrt(A) * mean(x_t) / sd(x_t)`` (``ddof = 1``) with the risk-free rate of the
  factor file. Not defined (``None``) when the daily returns or the daily excess returns do not
  vary (``sd(r_t) < SD_FLOOR`` or ``sd(x_t) < SD_FLOOR``; a flat price against a moving RF would
  otherwise give a huge, meaningless ratio). Its standard error is
  ``sharpe_se_iid = sqrt(A) * sqrt((1 + SR_d^2 / 2) / n)`` (``SR_d`` the daily Sharpe ratio), the
  closed form of Lo (2002) for independent,
  identically distributed returns. It assumes iid returns, ignores autocorrelation, fat tails and
  volatility clustering, and is approximate. The 95% interval is ``SR +/- 1.96 * SE``.
* Drawdown: the compounded return path starts at 1.0 on ``origin`` (the price date before the
  first analysed return, or the first analysed date when none is given) and
  ``W_j = prod_{i<=j}(1 + r_i)``. The drawdown at ``j`` is ``W_j / max_{i<=j} W_i - 1``. An
  *episode* runs from a running peak until the path first regains that peak (``W >= peak``,
  within ``PEAK_TOLERANCE``); it is open when the path never regains it. Episodes never
  overlap. Its depth is the lowest drawdown inside it, its trough the date of that low (first
  date on a tie). The maximum drawdown is the deepest episode; ``episodes`` lists the five
  deepest, deepest first. ``drawdown_series`` gives the drawdown at every path point.
  A path that never falls below a previous peak has no episode: depth ``0.0`` and no dates.
  Day counts are trading days of the path (positions in the sample, the origin counting as 0).
  Rows excluded from ``S`` (M2) are not in the path.

Inputs are not mutated. Non-finite values, a return below -100% or mismatched indexes raise
``ValueError``; fewer than ``MIN_OBS`` rows raise ``InsufficientObservations``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date
from typing import cast

import numpy as np
import pandas as pd
from numpy.typing import NDArray

from factordesk.analytics.sample import infer_periods

FloatArray = NDArray[np.float64]

MIN_OBS = 60
"""Safety floor of the section (fewer daily rows give ``insufficient_data``). The pipeline's own
minimum is 504 (M0.7), so this only matters for other callers."""
SD_FLOOR = 1e-8
"""A daily sample standard deviation below this is zero for the Sharpe ratio (the same floor as
``sample.MIN_RETURN_SD``): a constant series has an sd of rounding noise, never exactly 0."""
Z95 = 1.959963984540054
"""Two-sided 95% normal quantile."""
TOP_EPISODES = 5
"""How many of the deepest, non-overlapping falls the result lists."""
PEAK_TOLERANCE = 1e-9
"""A path value within this fraction of the running peak is back at the peak (validation F1).

The path is a product of thousands of daily ratios, so a price that returns exactly to an earlier
high can land a few units in the last place below it. An exact ``>=`` would then call a recovered
fall open. 1e-9 is far above that rounding (about 1e-12 over a long history) and far below any
real price move (a one-cent move on a 100 price is 1e-4)."""


class InsufficientObservations(ValueError):
    """Fewer returns than the minimum the caller asked for (``MIN_OBS`` by default)."""

    def __init__(self, n: int, required: int = MIN_OBS, unit: str = "daily") -> None:
        super().__init__(f"{n} {unit} observations, at least {required} required")
        self.n = n
        self.required = required


@dataclass(frozen=True)
class DrawdownEpisode:
    """One peak-to-trough-to-recovery episode of the compounded return path."""

    depth: float
    """``trough value / peak value - 1``, negative."""
    peak_date: date
    trough_date: date
    recovery_date: date | None
    """First date after the trough where the path regains the peak; ``None`` when it does not."""
    days_peak_to_trough: int
    days_trough_to_recovery: int | None


@dataclass(frozen=True)
class PerformanceResult:
    n: int
    start: date
    end: date
    years: float
    """``n / periods``."""
    cagr: float
    cumulative_return: float
    mean_return_annual: float
    """``periods * mean(r_t)``: arithmetic, ignores compounding."""
    volatility_annual: float
    mean_excess_annual: float
    """``periods * mean(x_t)``."""
    sharpe_daily: float | None
    sharpe_annual: float | None
    sharpe_se_iid: float | None
    sharpe_ci95: tuple[float, float] | None
    max_drawdown: float
    """Depth of the deepest episode; ``0.0`` when there is none."""
    episodes: tuple[DrawdownEpisode, ...]
    """The deepest ``TOP_EPISODES`` episodes, deepest first (ties: earlier peak first)."""
    drawdown_dates: tuple[date, ...]
    """Date of every path point: the origin, then each analysed date (``n + 1`` entries)."""
    drawdown_values: tuple[float, ...]
    """``W_j / max_{i<=j} W_i - 1`` at each path point, 0.0 or negative (``n + 1`` entries)."""


def _as_date(value: object) -> date:
    return pd.Timestamp(cast(str, value)).date()


def _values(name: str, series: pd.Series) -> FloatArray:
    arr = np.asarray(series, dtype=np.float64)
    if not bool(np.isfinite(arr).all()):
        raise ValueError(f"{name} holds a value that is not finite")
    return arr


def compound_path(ret: FloatArray) -> FloatArray:
    """``[1, W_1, ..., W_n]``, the compounded path starting at 1.0 (length ``n + 1``)."""
    return np.concatenate([[1.0], np.cumprod(1.0 + ret)])


def drawdown_series(path: FloatArray) -> FloatArray:
    """The drawdown ``W_j / max_{i<=j} W_i - 1`` at every point of ``path`` (0.0 at a new high)."""
    return np.asarray(path / np.maximum.accumulate(path) - 1.0, dtype=np.float64)


def drawdown_episodes(path: FloatArray, dates: list[date]) -> list[DrawdownEpisode]:
    """Every underwater episode of ``path`` in time order.

    ``dates[j]`` is the date of ``path[j]``. An episode starts at the running peak before the
    path first falls below it and ends at the first point that is at or above the peak (the
    recovery); the last episode is open when the path ends below its peak.
    """
    episodes: list[DrawdownEpisode] = []
    peak_value = float(path[0])
    peak_i = 0
    trough_i = -1
    for i in range(1, len(path)):
        value = float(path[i])
        if value >= peak_value * (1.0 - PEAK_TOLERANCE):
            if trough_i >= 0:
                episodes.append(_episode(path, dates, peak_i, trough_i, i))
                trough_i = -1
            peak_value, peak_i = max(peak_value, value), i
        elif trough_i < 0 or value < float(path[trough_i]):
            trough_i = i
    if trough_i >= 0:
        episodes.append(_episode(path, dates, peak_i, trough_i, None))
    return episodes


def _episode(
    path: FloatArray, dates: list[date], peak_i: int, trough_i: int, recovery_i: int | None
) -> DrawdownEpisode:
    return DrawdownEpisode(
        depth=float(path[trough_i] / path[peak_i] - 1.0),
        peak_date=dates[peak_i],
        trough_date=dates[trough_i],
        recovery_date=None if recovery_i is None else dates[recovery_i],
        days_peak_to_trough=trough_i - peak_i,
        days_trough_to_recovery=None if recovery_i is None else recovery_i - trough_i,
    )


def top_episodes(episodes: list[DrawdownEpisode], k: int = TOP_EPISODES) -> list[DrawdownEpisode]:
    """The ``k`` deepest episodes, deepest first; a tie keeps the earlier episode first."""
    return sorted(episodes, key=lambda e: e.depth)[:k]


def performance_stats(
    ret: pd.Series,
    rf: pd.Series,
    origin: date | pd.Timestamp | None = None,
    *,
    periods: int | None = None,
    min_obs: int = MIN_OBS,
) -> PerformanceResult:
    """Growth, volatility, Sharpe ratio and drawdowns over the sample (module docstring).

    ``ret`` and ``rf`` are simple returns and risk-free rates per period (decimals) on one
    strictly increasing date index. ``origin`` dates the starting point of the return path;
    ``None`` uses the first date of ``ret``. ``periods`` is the number of observations a year
    (252 daily, 12 monthly); ``None`` uses the frequency of ``ret``'s dates
    (``sample.infer_periods``), and a given value must agree with it when the dates show one,
    else ``ValueError``. Fewer than ``min_obs`` rows raise ``InsufficientObservations``.
    """
    inferred = infer_periods(ret.index)
    if periods is None:
        if inferred is None:
            raise ValueError(
                "cannot tell the frequency of the returns from their dates; pass periods "
                "(252 daily, 12 monthly)"
            )
        periods = inferred
    if periods <= 0:
        raise ValueError("periods must be positive")
    if inferred is not None and periods != inferred:
        raise ValueError(
            f"periods={periods} does not match the dates of the returns ({inferred} a year)"
        )
    if len(ret) != len(rf) or not ret.index.equals(rf.index):
        raise ValueError("ret and rf must share one index")
    n = len(ret)
    if n < min_obs:
        raise InsufficientObservations(n, min_obs)
    r = _values("ret", ret)
    f = _values("rf", rf)
    if bool((r < -1.0).any()):
        raise ValueError("a return is below -100%")
    index = pd.DatetimeIndex(ret.index)
    if not index.is_monotonic_increasing or not index.is_unique:
        raise ValueError("the index must be strictly increasing")

    x = r - f
    path = compound_path(r)
    final = float(path[-1])
    cagr = final ** (periods / n) - 1.0
    sd_ret = float(np.std(r, ddof=1))
    sd_x = float(np.std(x, ddof=1))
    mean_x = float(np.mean(x))
    sharpe_d = sharpe_a = se = None
    ci: tuple[float, float] | None = None
    if sd_x >= SD_FLOOR and sd_ret >= SD_FLOOR:
        sharpe_d = mean_x / sd_x
        sharpe_a = math.sqrt(periods) * sharpe_d
        se = math.sqrt(periods) * math.sqrt((1.0 + 0.5 * sharpe_d * sharpe_d) / n)
        ci = (sharpe_a - Z95 * se, sharpe_a + Z95 * se)

    start_point = index[0] if origin is None else pd.Timestamp(origin)
    if start_point > index[0]:
        raise ValueError("origin is after the first date")
    dates = [_as_date(start_point), *(_as_date(d) for d in index)]
    top = top_episodes(drawdown_episodes(path, dates))
    series = drawdown_series(path)
    result = PerformanceResult(
        n=n,
        start=_as_date(index[0]),
        end=_as_date(index[-1]),
        years=n / periods,
        cagr=cagr,
        cumulative_return=final - 1.0,
        mean_return_annual=periods * float(np.mean(r)),
        volatility_annual=math.sqrt(periods) * sd_ret,
        mean_excess_annual=periods * mean_x,
        sharpe_daily=sharpe_d,
        sharpe_annual=sharpe_a,
        sharpe_se_iid=se,
        sharpe_ci95=ci,
        max_drawdown=top[0].depth if top else 0.0,
        episodes=tuple(top),
        drawdown_dates=tuple(dates),
        drawdown_values=tuple(float(v) for v in series),
    )
    numbers = [
        result.cagr,
        result.cumulative_return,
        result.mean_return_annual,
        result.volatility_annual,
        result.mean_excess_annual,
    ]
    if not all(math.isfinite(v) for v in numbers):
        raise ValueError("a performance statistic is not finite")
    return result
