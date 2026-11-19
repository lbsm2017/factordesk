"""Quick world beta: a single-factor regression on a world benchmark (docs/validation handoff WB1).

The benchmark is the iShares MSCI ACWI ETF (Yahoo ticker ``ACWI``), a stand-in for the MSCI ACWI
index, which has no free daily data. Definitions:

* benchmark return ``b_t = P_t / P_{t-1} - 1`` from ``adj_close`` (``PriceHistory.total_returns``
  rules: a missing or non-positive price is a missing return, never zero);
* excess benchmark return ``x_t = b_t - RF_t`` with the French ``RF``;
* quick beta: OLS of the stock's excess return ``y_t`` on ``x_t`` with an intercept, on the dates
  the analysis sample ``S`` (M2) and the benchmark have in common, with the Newey-West standard
  error of M0.5 (the existing ``ols_hac``, one factor);
* the same dates against the US market factor ``Mkt-RF``, so the two betas compare like for like.

Pure: no I/O, no clock. Inputs are not mutated.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd
from numpy.typing import NDArray

from factordesk.analytics.regression import A, ols_hac
from factordesk.analytics.sample import MIN_RETURN_SD, AnalysisSample, DegenerateInputError
from factordesk.data.prices import PriceHistory

FloatArray = NDArray[np.float64]

BENCHMARK_TICKER = "ACWI"
"""Yahoo ticker of the proxy: iShares MSCI ACWI ETF, USD, US exchange, history from 2008-03."""
MIN_OVERLAP = 252
"""Fewest common days with a result (one trading year); fewer is ``insufficient_data``."""
EXACT_FIT_RELATIVE_SSR = 1e-20
"""Residual sum of squares, as a share of the total sum of squares, at or below which the fit is
exact: the residual is rounding noise, so a t value built on it would be the ratio of two
rounding errors."""

Comparison = Literal["about_the_same", "higher", "lower"]


@dataclass(frozen=True)
class BetaEstimate:
    """One single-factor regression ``y = alpha + beta x + e`` with Newey-West inference."""

    beta: float
    se_hac: float
    ci_low: float
    ci_high: float
    r2: float
    correlation: float
    alpha_annual: float
    alpha_t: float | None
    """HAC t of alpha; ``None`` on an exact fit (residuals are rounding noise, see
    ``EXACT_FIT_RELATIVE_SSR``) or when its standard error is zero."""
    nobs: int
    lags: int


def single_factor_beta(y: FloatArray, x: FloatArray) -> BetaEstimate:
    """OLS of ``y`` on ``x`` with an intercept; HAC lags ``hac_lags(len(y))`` (M0.5).

    Raises ``ValueError`` for non-finite input and ``DegenerateInputError`` when ``x`` or ``y``
    does not vary (``x`` below the ``MIN_RETURN_SD`` of M2 step 7, so noise around zero is refused
    too). Reuses ``ols_hac``; there is no second HAC implementation.
    """
    yv = np.asarray(y, dtype=np.float64)
    xv = np.asarray(x, dtype=np.float64)
    if yv.ndim != 1 or xv.shape != yv.shape:
        raise ValueError("y and x must be one-dimensional and of equal length")
    if float(np.std(xv, ddof=1)) < MIN_RETURN_SD:
        raise DegenerateInputError(
            f"the daily excess return of {BENCHMARK_TICKER} does not vary over the sample "
            f"(standard deviation below {MIN_RETURN_SD:.0e}), so there is no beta to estimate"
        )
    with np.errstate(divide="ignore", invalid="ignore"):  # an exact fit has a zero standard error
        fit = ols_hac(yv, xv[:, None], names=(BENCHMARK_TICKER,))
    beta, se = float(fit.params[1]), float(fit.bse[1])
    alpha_se = float(fit.bse[0])
    resid = yv - float(fit.params[0]) - beta * xv
    ssr = float(resid @ resid)
    tss = float(np.sum((yv - yv.mean()) ** 2))
    exact_fit = ssr <= EXACT_FIT_RELATIVE_SSR * tss
    corr = float(np.corrcoef(yv, xv)[0, 1])
    values = (beta, se, float(fit.ci_low[1]), float(fit.ci_high[1]), fit.rsquared, corr)
    if not all(math.isfinite(v) for v in values):
        raise ValueError("the regression produced a non-finite value")
    return BetaEstimate(
        beta=beta,
        se_hac=se,
        ci_low=float(fit.ci_low[1]),
        ci_high=float(fit.ci_high[1]),
        r2=min(max(fit.rsquared, 0.0), 1.0),
        correlation=max(-1.0, min(1.0, corr)),
        alpha_annual=A * float(fit.params[0]),
        alpha_t=None if exact_fit or not alpha_se > 0.0 else float(fit.params[0]) / alpha_se,
        nobs=fit.nobs,
        lags=fit.lags,
    )


@dataclass(frozen=True)
class Overlap:
    """The days the analysis sample and the benchmark share, with the three aligned series."""

    dates: pd.DatetimeIndex
    stock_xret: FloatArray
    bench_xret: FloatArray
    mkt_rf: FloatArray
    n_sample: int
    """Rows of the analysis sample ``S``."""
    n_without_benchmark: int
    """Rows of ``S`` with no usable benchmark return (date absent, price missing, or a gap that
    makes the benchmark return span a different interval than the stock's)."""

    @property
    def n(self) -> int:
        return len(self.dates)


def _previous_dates(index: pd.DatetimeIndex) -> pd.Series:
    """For every date but the first, the date of the row before it."""
    return pd.Series(index[:-1], index=index[1:])


def align_overlap(
    sample: AnalysisSample, stock_prices: pd.DatetimeIndex, benchmark: PriceHistory
) -> Overlap:
    """Common days of ``S`` and the benchmark's returns (the dates of the analysis sample).

    A benchmark return on date ``t`` is kept only when the benchmark's previous price date is the
    stock's previous price date: the two returns then span the same interval. A benchmark date
    missing from its history would otherwise turn its next return into a two-day return set
    against the stock's one-day return.
    """
    s_dates = pd.DatetimeIndex(sample.xret.index)
    bench_ret = benchmark.total_returns.reindex(s_dates)
    bench_index = pd.DatetimeIndex(benchmark.frame.index)
    same_interval = (
        _previous_dates(bench_index).reindex(s_dates)
        == _previous_dates(stock_prices).reindex(s_dates)
    ).to_numpy(dtype=bool)
    usable = same_interval & np.isfinite(bench_ret.to_numpy(dtype=np.float64))
    dates = pd.DatetimeIndex(s_dates[np.flatnonzero(usable)])
    rf = sample.rf.loc[dates].to_numpy(dtype=np.float64)
    return Overlap(
        dates=dates,
        stock_xret=sample.xret.loc[dates].to_numpy(dtype=np.float64),
        bench_xret=bench_ret.loc[dates].to_numpy(dtype=np.float64) - rf,
        mkt_rf=sample.factors.loc[dates, "mkt_rf"].to_numpy(dtype=np.float64),
        n_sample=sample.n,
        n_without_benchmark=sample.n - len(dates),
    )


def intervals_overlap(a: BetaEstimate, b: BetaEstimate) -> bool:
    """True when the two 95% intervals share at least one point."""
    return max(a.ci_low, b.ci_low) <= min(a.ci_high, b.ci_high)


WORDS: dict[Comparison, str] = {
    "about_the_same": (
        "About the same: the 95% intervals of the two betas overlap, so these days do not show "
        "a difference between the US market beta and the world beta."
    ),
    "higher": (
        "Higher against the world: the beta against the world is above the beta against the US "
        "market, and the two 95% intervals do not overlap."
    ),
    "lower": (
        "Lower against the world: the beta against the world is below the beta against the US "
        "market, and the two 95% intervals do not overlap."
    ),
}
"""The plain reading of the comparison; nothing is claimed beyond the intervals."""


def compare_betas(world: BetaEstimate, us: BetaEstimate) -> tuple[Comparison, str]:
    """``about_the_same`` when the intervals overlap; otherwise which beta is higher."""
    if intervals_overlap(world, us):
        key: Comparison = "about_the_same"
    elif world.beta > us.beta:
        key = "higher"
    else:
        key = "lower"
    return key, WORDS[key]


__all__ = [
    "BENCHMARK_TICKER",
    "MIN_OVERLAP",
    "WORDS",
    "BetaEstimate",
    "Comparison",
    "Overlap",
    "align_overlap",
    "compare_betas",
    "intervals_overlap",
    "single_factor_beta",
]
