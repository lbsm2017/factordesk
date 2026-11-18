"""Data-generating processes of ``docs/test-oracle-residual-analysis.md`` section 0.2.

All of them reuse DGP-A of ``docs/test-oracle.md`` 0.4 (``fixtures/dgp.py``) and override only what
the oracle lists. Seeds: test ``TRk`` uses ``default_rng(20261118 + 500 + k)``; replication ``r`` of
a Monte Carlo test uses ``default_rng([20261118 + 500 + k, r])`` (oracle 0.1).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
import statsmodels.api as sm  # pyright: ignore[reportMissingTypeStubs]
from numpy.typing import NDArray

from factordesk.analytics.regression import FullSampleRegression, run_regression
from factordesk.analytics.residual import ResidualResult, residual_analysis
from factordesk.analytics.rolling import RollingBetas, rolling_betas
from factordesk.analytics.sample import AnalysisSample, build_sample
from factordesk.tests.fixtures.dgp import (
    BETA,
    MU,
    SEED_BASE,
    SIGMA_E,
    SIGMA_F,
    Synthetic,
    default_rf,
    factor_frame,
    price_history,
)

FloatArray = NDArray[np.float64]
_sm: Any = sm


def rng_tr(k: int, replication: int | None = None) -> np.random.Generator:
    """Seed policy of the residual oracle (0.1)."""
    if replication is None:
        return np.random.default_rng(SEED_BASE + 500 + k)
    return np.random.default_rng([SEED_BASE + 500 + k, replication])


def dgp_residual(
    rng: np.random.Generator,
    n: int = 2520,
    *,
    alpha: float | FloatArray = 0.0002,
    sigma_e: float = SIGMA_E,
    beta: FloatArray | None = None,
    f: FloatArray | None = None,
    rf: FloatArray | None = None,
    e: FloatArray | None = None,
    first_price_date: str = "2009-12-31",
) -> Synthetic:
    """DGP-A with an optional per-row alpha, per-row betas, given factors, RF or errors."""
    dates = pd.bdate_range("2010-01-04", periods=n, name="date")
    fac = rng.multivariate_normal(MU, SIGMA_F, size=n) if f is None else np.asarray(f)
    rfv = default_rf(n) if rf is None else np.asarray(rf, dtype=np.float64)
    b = BETA if beta is None else np.asarray(beta, dtype=np.float64)
    err = rng.normal(0.0, sigma_e, size=n) if e is None else np.asarray(e, dtype=np.float64)
    systematic = fac @ b if b.ndim == 1 else np.einsum("ij,ij->i", fac, b)
    a = np.asarray(alpha, dtype=np.float64)
    ret = rfv + a + systematic + err
    return Synthetic(
        history=price_history(ret, dates, first_date=first_price_date),
        factors=factor_frame(fac, rfv, dates),
        f=fac,
        rf=rfv,
        ret=ret,
        e=err,
        beta=b,
        alpha=float(np.mean(a)),
        sigma_e=sigma_e,
        dates=dates,
    )


def dgp_r0(rng: np.random.Generator, n: int = 2520) -> Synthetic:
    """DGP-R0: zero true alpha."""
    return dgp_residual(rng, n, alpha=0.0, sigma_e=0.012)


def dgp_rplus(rng: np.random.Generator, n: int = 2520) -> Synthetic:
    """DGP-R+: strong, stable alpha (0.0012 a day = 30.24% a year), residual sd 0.008."""
    return dgp_residual(rng, n, alpha=0.0012, sigma_e=0.008)


def dgp_rb(rng: np.random.Generator, n: int = 2520) -> Synthetic:
    """DGP-RB: market beta 0.5 on rows 1-1260 and 1.5 on rows 1261-2520, alpha 0."""
    beta = np.tile(BETA, (n, 1))
    beta[:1260, 0] = 0.5
    beta[1260:, 0] = 1.5
    return dgp_residual(rng, n, alpha=0.0, sigma_e=0.008, beta=beta)


def dgp_rt(rng: np.random.Generator, n: int = 2520) -> Synthetic:
    """DGP-RT: alpha that is a moving exposure (market beta 0 then 2, market drift -/+ 0.0015)."""
    fac = rng.multivariate_normal(MU, SIGMA_F, size=n)
    fac[:1260, 0] += -0.0015 - fac[:1260, 0].mean()
    fac[1260:, 0] += 0.0015 - fac[1260:, 0].mean()
    beta = np.tile(BETA, (n, 1))
    beta[:1260, 0] = 0.0
    beta[1260:, 0] = 2.0
    return dgp_residual(rng, n, alpha=0.0, sigma_e=0.005, beta=beta, f=fac)


@dataclass(frozen=True)
class Analysis:
    """One DGP run through the analytics of the residual feature."""

    sample: AnalysisSample
    reg: FullSampleRegression
    rolling: RollingBetas
    result: ResidualResult


def analyse(d: Synthetic, window: int = 252) -> Analysis:
    """Sample, full-sample regression, M4 betas for ``window`` and the residual analysis."""
    sample = build_sample(d.history, d.factors)
    return analyse_sample(sample, window)


def analyse_sample(sample: AnalysisSample, window: int = 252) -> Analysis:
    reg = run_regression(sample)
    rb = rolling_betas(sample, window)
    return Analysis(sample, reg, rb, residual_analysis(sample, reg, rb, exact_fit=False))


def ols_reference(y: FloatArray, design: FloatArray, lags: int) -> Any:
    """``sm.OLS(y, design).fit(HAC, maxlags=lags, use_correction=False, use_t=False)`` (M0.5)."""
    return _sm.OLS(y, design).fit(
        cov_type="HAC", cov_kwds={"maxlags": lags, "use_correction": False}, use_t=False
    )


def location_reference(x: FloatArray, lags: int) -> tuple[float, float, float]:
    """``(mean, se, p)`` of the constant-only HAC fit of R3.2 (daily units)."""
    res = ols_reference(np.asarray(x, dtype=np.float64), np.ones(len(x)), lags)
    return float(res.params[0]), float(res.bse[0]), float(res.pvalues[0])


def with_constant(f: FloatArray) -> FloatArray:
    return np.column_stack([np.ones(len(f)), f])
