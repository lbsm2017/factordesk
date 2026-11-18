"""Standard data-generating processes of ``docs/test-oracle.md`` section 0.4.

Builders return the same typed inputs as the real providers: a ``PriceHistory`` (canonical
price frame) and a factor frame shaped like ``data.factors.load_ff5_daily()`` (French column
names, decimals).
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from datetime import UTC, datetime

import numpy as np
import pandas as pd
from numpy.typing import NDArray

from factordesk.data.prices import PriceHistory

FloatArray = NDArray[np.float64]

FRENCH = ["Mkt-RF", "SMB", "HML", "RMW", "CMA", "RF"]
SEED_BASE = 20261118
FETCHED_AT = datetime(2026, 11, 18, 12, 0, tzinfo=UTC)

MU = np.array([0.0003, 0.0001, 0.0001, 0.0001, 0.0001])
SD = np.array([0.010, 0.006, 0.006, 0.004, 0.004])
_CORR = np.eye(5)
for (_i, _j), _c in {(0, 1): 0.2, (0, 2): -0.2, (2, 4): 0.6, (1, 3): -0.3, (2, 3): 0.2}.items():
    _CORR[_i, _j] = _CORR[_j, _i] = _c
SIGMA_F: FloatArray = np.outer(SD, SD) * _CORR
BETA = np.array([1.10, 0.30, -0.40, 0.25, 0.15])
ALPHA = 0.0002
SIGMA_E = 0.012


def rng_for(test_number: int, seed: int | None = None) -> np.random.Generator:
    """Seed policy 0.2: test k uses ``default_rng(20261118 + k)``; sweeps pass ``seed``."""
    return np.random.default_rng(SEED_BASE + test_number if seed is None else seed)


def default_rf(n: int) -> FloatArray:
    """``RF_t = 0.0001 (1 + 0.5 sin(2 pi t / 1260))`` for ``t = 1..n``."""
    t = np.arange(1, n + 1, dtype=np.float64)
    return 0.0001 * (1.0 + 0.5 * np.sin(2.0 * np.pi * t / 1260.0))


@dataclass(frozen=True)
class Synthetic:
    """One draw of a DGP. ``ret`` are the generating returns; prices are built from them."""

    history: PriceHistory
    factors: pd.DataFrame
    f: FloatArray
    rf: FloatArray
    ret: FloatArray
    e: FloatArray
    beta: FloatArray
    alpha: float
    sigma_e: float
    dates: pd.DatetimeIndex


def price_history(
    ret: FloatArray,
    dates: pd.DatetimeIndex,
    first_date: str | pd.Timestamp = "2009-12-31",
    ticker: str = "SYN",
) -> PriceHistory:
    """``Close = Adj Close = 100 cumprod(1 + r)`` with a leading price of 100 on ``first_date``."""
    prices = 100.0 * np.concatenate([[1.0], np.cumprod(1.0 + ret)])
    index = pd.DatetimeIndex([pd.Timestamp(first_date), *dates], name="date")
    frame = pd.DataFrame(
        {
            "close": prices,
            "adj_close": prices,
            "dividends": np.zeros(len(prices)),
            "splits": np.zeros(len(prices)),
        },
        index=index,
    )
    return PriceHistory(ticker, frame, FETCHED_AT, "synthetic")


def factor_frame(f: FloatArray, rf: FloatArray, dates: pd.DatetimeIndex) -> pd.DataFrame:
    """French-shaped frame: columns Mkt-RF..CMA, RF (decimals), ``date`` index."""
    data = np.column_stack([f, rf])
    return pd.DataFrame(data, index=pd.DatetimeIndex(dates, name="date"), columns=FRENCH)


def dgp_a(
    rng: np.random.Generator,
    n: int = 2520,
    *,
    beta: FloatArray | None = None,
    alpha: float = ALPHA,
    sigma_e: float = SIGMA_E,
    rf: FloatArray | None = None,
    f: FloatArray | None = None,
) -> Synthetic:
    """DGP-A (static five-factor). ``beta`` may be ``(5,)`` or per-row ``(n, 5)``."""
    dates = pd.bdate_range("2010-01-04", periods=n, name="date")
    fac = rng.multivariate_normal(MU, SIGMA_F, size=n) if f is None else np.asarray(f)
    rfv = default_rf(n) if rf is None else np.asarray(rf, dtype=np.float64)
    b = BETA if beta is None else np.asarray(beta, dtype=np.float64)
    e = rng.normal(0.0, sigma_e, size=n)
    systematic = fac @ b if b.ndim == 1 else np.einsum("ij,ij->i", fac, b)
    ret = rfv + alpha + systematic + e
    return Synthetic(
        history=price_history(ret, dates),
        factors=factor_frame(fac, rfv, dates),
        f=fac,
        rf=rfv,
        ret=ret,
        e=e,
        beta=b,
        alpha=alpha,
        sigma_e=sigma_e,
        dates=dates,
    )


def dgp_b(rng: np.random.Generator, n: int = 1000) -> Synthetic:
    """DGP-B: AR(1) factors and errors with coefficient 0.5, same marginal covariances."""
    dates = pd.bdate_range("2010-01-04", periods=n, name="date")
    chol = np.linalg.cholesky(SIGMA_F)
    nu = rng.standard_normal((n, 5)) @ chol.T
    eps = rng.standard_normal(n)
    z = np.empty((n, 5))
    e = np.empty(n)
    z[0] = nu[0]
    e[0] = SIGMA_E * eps[0]
    k = np.sqrt(0.75)
    for t in range(1, n):
        z[t] = 0.5 * z[t - 1] + k * nu[t]
        e[t] = 0.5 * e[t - 1] + k * SIGMA_E * eps[t]
    fac = MU + z
    rfv = default_rf(n)
    ret = rfv + ALPHA + fac @ BETA + e
    return Synthetic(
        history=price_history(ret, dates),
        factors=factor_frame(fac, rfv, dates),
        f=fac,
        rf=rfv,
        ret=ret,
        e=e,
        beta=BETA,
        alpha=ALPHA,
        sigma_e=SIGMA_E,
        dates=dates,
    )


def dgp_n(
    rng: np.random.Generator, n: int = 2520, *, sigma_w: float = 0.006, sigma_u: float = 0.006
) -> Synthetic:
    """DGP-N: DGP-A plus a transient price error ``u_t - u_{t-1}`` that reverses the next day.

    Population lag-1 autocorrelation of the residual ``w + u_t - u_{t-1}`` is
    ``-sigma_u^2 / (2 sigma_u^2 + sigma_w^2)`` (-1/3 with the defaults).
    """
    dates = pd.bdate_range("2010-01-04", periods=n, name="date")
    fac = rng.multivariate_normal(MU, SIGMA_F, size=n)
    rfv = default_rf(n)
    w = rng.normal(0.0, sigma_w, size=n)
    u = rng.normal(0.0, sigma_u, size=n)
    e = w + u - np.concatenate([[0.0], u[:-1]])
    ret = rfv + ALPHA + fac @ BETA + e
    return Synthetic(
        history=price_history(ret, dates),
        factors=factor_frame(fac, rfv, dates),
        f=fac,
        rf=rfv,
        ret=ret,
        e=e,
        beta=BETA,
        alpha=ALPHA,
        sigma_e=float(np.sqrt(sigma_w**2 + 2 * sigma_u**2)),
        dates=dates,
    )


def dgp_g(rng: np.random.Generator, n: int = 2520) -> Synthetic:
    """DGP-G: GARCH(1,1) residuals with Student-t(5) shocks; no autocorrelation."""
    dates = pd.bdate_range("2010-01-04", periods=n, name="date")
    fac = rng.multivariate_normal(MU, SIGMA_F, size=n)
    rfv = default_rf(n)
    omega, a, b = 1e-6, 0.10, 0.85
    z = rng.standard_t(5, size=n) / np.sqrt(5.0 / 3.0)  # unit variance
    e = np.empty(n)
    var = omega / (1.0 - a - b)
    prev = 0.0
    for t in range(n):
        var = omega + a * prev**2 + b * var if t else var
        e[t] = np.sqrt(var) * z[t]
        prev = e[t]
    ret = rfv + ALPHA + fac @ BETA + e
    return Synthetic(
        history=price_history(ret, dates),
        factors=factor_frame(fac, rfv, dates),
        f=fac,
        rf=rfv,
        ret=ret,
        e=e,
        beta=BETA,
        alpha=ALPHA,
        sigma_e=float(np.sqrt(omega / (1.0 - a - b))),
        dates=dates,
    )


def theoretical_se(n: int, sigma_e: float = SIGMA_E) -> FloatArray:
    """``SE(theta) = sigma_e sqrt(diag(E[x x']^-1) / n)`` for DGP-A (alpha first)."""
    second = np.empty((6, 6))
    second[0, 0] = 1.0
    second[0, 1:] = second[1:, 0] = MU
    second[1:, 1:] = SIGMA_F + np.outer(MU, MU)
    return sigma_e * np.sqrt(np.diag(np.linalg.inv(second)) / n)


class StaticProvider:
    """Offline ``PriceProvider`` serving one fixed history (relabelled to the asked ticker)."""

    def __init__(self, history: PriceHistory) -> None:
        self.history = history
        self.calls: list[str] = []

    def fetch(self, ticker: str) -> PriceHistory:
        self.calls.append(ticker)
        return dataclasses.replace(self.history, ticker=ticker)
