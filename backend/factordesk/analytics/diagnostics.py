"""Residual diagnostics, the residual quality gate and the 5-day estimate (methodology M3.5-M3.6).

Diagnostics describe the full-sample OLS residuals; they never select the covariance estimator
(HAC is prespecified, M0.5) and never drive tags, except through the quality gate: when the
lag-1 residual autocorrelation shows that part of each day's residual reverses the next day
(non-synchronous closes), the report adds a caveat and a 5-day estimate, and a coefficient is
tagged reliable only if the daily and the 5-day tests both reject.

Pure: no I/O, no clock, no randomness. Inputs are not mutated. Every statsmodels call that
offers ``result_object=True`` uses it, so nothing emits a ``FutureWarning``.
"""

from __future__ import annotations

import dataclasses
import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any, cast

import numpy as np
import pandas as pd
from numpy.typing import NDArray
from scipy.stats import chi2  # pyright: ignore[reportMissingTypeStubs]
from statsmodels.stats.diagnostic import (  # pyright: ignore[reportMissingTypeStubs]
    acorr_ljungbox,  # pyright: ignore[reportUnknownVariableType]
    het_arch,  # pyright: ignore[reportUnknownVariableType]
)
from statsmodels.stats.stattools import (  # pyright: ignore[reportMissingTypeStubs]
    durbin_watson,  # pyright: ignore[reportUnknownVariableType]
    jarque_bera,  # pyright: ignore[reportUnknownVariableType]
)

from factordesk.analytics.regression import (
    ALPHA_LEVEL,
    A,
    FullSampleRegression,
    OLSHACFit,
    Tag,
    alpha_tag,
    beta_interpretation,
    bh_adjust,
    ols_hac,
    significance_tags,
    two_sided_p,
)
from factordesk.analytics.sample import DISPLAY_NAMES, FACTOR_CODES, AnalysisSample

FloatArray = NDArray[np.float64]

LB_LAGS = 10
"""Ljung-Box: one test at lag 10 (M3.5)."""
BG_LAGS = 10
"""Robust Breusch-Godfrey: 10 lagged residuals in the auxiliary regression (M3.5)."""
ARCH_LAGS = 5
"""ARCH-LM: 5 lags (M3.5)."""
RHO_GATE = -0.2
"""Quality gate: lag-1 residual autocorrelation strictly below this (M3.6)."""
Z_GATE = -4.0
"""Quality gate: robust z of the lag-1 autocorrelation strictly below this (M3.6)."""
HORIZON = 5
"""Block length of the multi-day estimate, trading days (M3.6)."""
MIN_BLOCKS = 100
"""Minimum number of non-overlapping blocks for the multi-day estimate (M0.7, M3.6)."""
EXACT_FIT = 1e-12
"""When ``1 - R^2`` is below this the residuals are rounding noise: no diagnostics (M3.5)."""


def exact_fit(rsquared: float) -> bool:
    """True when the regression fits to rounding, so residual diagnostics mean nothing."""
    return 1.0 - rsquared < EXACT_FIT


NOTE = (
    "Standard errors are Newey-West HAC for every regression whatever these tests show; the "
    "tests are informational."
)

_ljungbox = cast(Callable[..., Any], acorr_ljungbox)
_het_arch = cast(Callable[..., Any], het_arch)
_jarque_bera = cast(Callable[..., Any], jarque_bera)
_durbin_watson = cast(Callable[..., Any], durbin_watson)
_chi2_sf = cast(Callable[..., Any], chi2.sf)  # pyright: ignore[reportUnknownMemberType]


def _p_text(p: float) -> str:
    """p-value as the report prints it."""
    return "<0.001" if p < 0.001 else f"{p:.3f}"


# ----------------------------------------------------------------------------- statistics
@dataclass(frozen=True)
class Lag1:
    """Lag-1 autocorrelation of the residuals with its heteroskedasticity-robust z (M3.5)."""

    rho: float
    se: float
    z: float
    p: float


@dataclass(frozen=True)
class ChiSquareTest:
    statistic: float
    df: int
    p: float


def lag1_autocorrelation(resid: FloatArray) -> Lag1:
    """Lag-1 autocorrelation ``rho_1 = sum e_t e_{t-1} / sum e_t^2`` and its robust z (M3.5).

    Robust se ``sqrt(sum e_t^2 e_{t-1}^2) / sum e_t^2``: valid under no autocorrelation with
    changing variance.
    """
    e = np.asarray(resid, dtype=np.float64)
    denom = float(e @ e)
    rho = float(e[1:] @ e[:-1]) / denom
    se = math.sqrt(float(np.sum((e[1:] * e[:-1]) ** 2))) / denom
    z = rho / se
    return Lag1(rho=rho, se=se, z=z, p=float(two_sided_p(np.array([z]))[0]))


def robust_breusch_godfrey(
    resid: FloatArray, factors: FloatArray, lags: int = BG_LAGS
) -> ChiSquareTest:
    """HC0-robust Breusch-Godfrey test of no autocorrelation up to ``lags`` (M3.5).

    Auxiliary OLS on rows ``t = lags+1..n``: ``e_t`` on a constant, ``f_t`` and
    ``e_{t-1}..e_{t-lags}``; Wald statistic of the lag coefficients with HC0 covariance,
    chi-square with ``lags`` degrees of freedom.
    """
    e = np.asarray(resid, dtype=np.float64)
    f = np.asarray(factors, dtype=np.float64)
    n = len(e)
    lagged = [e[lags - lag : n - lag] for lag in range(1, lags + 1)]
    z = np.column_stack([np.ones(n - lags), f[lags:], *lagged])
    dep = e[lags:]
    q, r = np.linalg.qr(z)
    coef = np.linalg.solve(r, q.T @ dep)
    u = dep - z @ coef
    r_inv = np.linalg.solve(r, np.eye(z.shape[1]))
    bread = r_inv @ r_inv.T
    scores = z * u[:, None]
    cov = bread @ (scores.T @ scores) @ bread
    g = coef[-lags:]
    stat = float(g @ np.linalg.solve(cov[-lags:, -lags:], g))
    return ChiSquareTest(statistic=stat, df=lags, p=float(_chi2_sf(stat, lags)))


@dataclass(frozen=True)
class DiagnosticsResult:
    """M3.5 diagnostics of one residual series, with one plain-language reading per row."""

    lag1: Lag1
    ljung_box: ChiSquareTest
    robust_bg: ChiSquareTest
    arch_lm: ChiSquareTest
    jarque_bera: ChiSquareTest
    skew: float
    kurtosis: float
    durbin_watson: float
    readings: dict[str, str]
    note: str


def _readings(
    lag: Lag1,
    lb: ChiSquareTest,
    bg: ChiSquareTest,
    arch: ChiSquareTest,
    jb: ChiSquareTest,
    skew: float,
    kurt: float,
    dw: float,
) -> dict[str, str]:
    lag_text = f"Lag-1 autocorrelation of the residuals is {lag.rho:+.2f} (robust z {lag.z:+.1f}). "
    if lag.p < ALPHA_LEVEL and lag.rho < 0:
        lag_text += "Part of each day's unexplained return reverses the next day."
    elif lag.p < ALPHA_LEVEL:
        lag_text += "Unexplained returns tend to persist into the next day."
    else:
        lag_text += "No clear day-to-day pattern."
    fat = jb.p < ALPHA_LEVEL
    return {
        "lag1_autocorrelation": lag_text,
        "ljung_box": (
            f"Ljung-Box ({lb.df} lags) {'rejects' if lb.p < ALPHA_LEVEL else 'does not reject'} "
            f"no autocorrelation (p {_p_text(lb.p)}). It assumes constant variance, so it "
            "rejects too often on daily returns; read the robust test below."
        ),
        "robust_breusch_godfrey": (
            f"Autocorrelation test robust to changing volatility ({bg.df} lags): "
            f"{'autocorrelation present' if bg.p < ALPHA_LEVEL else 'no autocorrelation detected'}"
            f" (p {_p_text(bg.p)})."
        ),
        "arch_lm": (
            f"Volatility clustering (ARCH-LM, {arch.df} lags): "
            f"{'present' if arch.p < ALPHA_LEVEL else 'not detected'} (p {_p_text(arch.p)})."
        ),
        "jarque_bera": (
            "Residual tails: "
            f"{'fatter than normal or skewed' if fat else 'consistent with a normal distribution'}"
            f" (Jarque-Bera p {_p_text(jb.p)}, skew {skew:+.2f}, excess kurtosis {kurt - 3:.1f})"
            + ("; normal-based intervals are approximate." if fat else ".")
        ),
        "durbin_watson": (
            f"Durbin-Watson {dw:.2f}: near 2 means little first-order autocorrelation; above 2 "
            "points to negative, below 2 to positive autocorrelation."
        ),
    }


def residual_diagnostics(resid: FloatArray, factors: FloatArray) -> DiagnosticsResult:
    """All M3.5 diagnostics of the full-sample residuals ``resid`` (regressors ``factors``)."""
    e = np.asarray(resid, dtype=np.float64)
    lag = lag1_autocorrelation(e)
    lb_frame: Any = _ljungbox(e, lags=[LB_LAGS], model_df=0)
    lb = ChiSquareTest(
        statistic=float(lb_frame["lb_stat"].iloc[0]),
        df=LB_LAGS,
        p=float(lb_frame["lb_pvalue"].iloc[0]),
    )
    bg = robust_breusch_godfrey(e, factors, BG_LAGS)
    arch_res: Any = _het_arch(e, nlags=ARCH_LAGS, result_object=True)
    arch = ChiSquareTest(statistic=float(arch_res.lm), df=ARCH_LAGS, p=float(arch_res.lmpval))
    jb_res: Any = _jarque_bera(e)
    jb = ChiSquareTest(statistic=float(jb_res[0]), df=2, p=float(jb_res[1]))
    skew, kurt = float(jb_res[2]), float(jb_res[3])
    dw = float(_durbin_watson(e))
    return DiagnosticsResult(
        lag1=lag,
        ljung_box=lb,
        robust_bg=bg,
        arch_lm=arch,
        jarque_bera=jb,
        skew=skew,
        kurtosis=kurt,
        durbin_watson=dw,
        readings=_readings(lag, lb, bg, arch, jb, skew, kurt, dw),
        note=NOTE,
    )


# ----------------------------------------------------------------------------- quality gate
def gate_fires(rho: float, z: float) -> bool:
    """The M3.6 rule: ``rho_1 < -0.2`` and robust ``z < -4`` (both strict)."""
    return rho < RHO_GATE and z < Z_GATE


def noise_share(rho: float) -> float:
    """Share of residual variance that is a reversing price error, ``min(1, -2 rho)`` (M3.6)."""
    return min(1.0, max(0.0, -2.0 * rho))


@dataclass(frozen=True)
class GateResult:
    rho: float
    z: float
    fired: bool
    noise_share: float
    message: str | None


def quality_gate(lag: Lag1) -> GateResult:
    """Apply the residual quality gate to the lag-1 autocorrelation (M3.6)."""
    fired = gate_fires(lag.rho, lag.z)
    share = noise_share(lag.rho)
    message = (
        "Daily price changes partly reverse the next day: the lag-1 autocorrelation of the "
        f"regression residuals is {lag.rho:+.2f} (robust z {lag.z:+.1f}). The closing prices "
        "are probably not synchronous with the factor data (for example a close recorded after "
        "the 4:00 pm index close). Under a simple model of a price error that reverses the next "
        f"day, about {share:.0%} of the residual variance is such noise, so R², residual "
        "volatility and the idiosyncratic share overstate stock-specific risk. Alpha and betas "
        "are also estimated from 5-day returns; a coefficient is tagged reliable only if the "
        "daily and the 5-day tests both reject."
        if fired
        else None
    )
    return GateResult(rho=lag.rho, z=lag.z, fired=fired, noise_share=share, message=message)


# ----------------------------------------------------------------------------- 5-day estimate
def block_sums(
    y: FloatArray, factors: FloatArray, horizon: int = HORIZON
) -> tuple[FloatArray, FloatArray, int]:
    """Sums over non-overlapping blocks of ``horizon`` rows anchored at the first row (M3.6).

    Returns ``(Y_b, F_b, n_unused)``; the last ``n_unused = n mod horizon`` rows are not used.
    """
    yv = np.asarray(y, dtype=np.float64)
    f = np.asarray(factors, dtype=np.float64)
    m = len(yv) // horizon
    used = m * horizon
    yb = yv[:used].reshape(m, horizon).sum(axis=1)
    fb = f[:used].reshape(m, horizon, f.shape[1]).sum(axis=1)
    return yb, fb, len(yv) - used


@dataclass(frozen=True)
class MultiDayFit:
    """OLS with HAC on non-overlapping ``horizon``-day sums (M3.6). Annualised with A/horizon."""

    horizon: int
    n_blocks: int
    n_unused: int
    first_date: date
    last_date: date
    fit: OLSHACFit
    alpha_ann: float
    alpha_se_ann: float
    alpha_ci_ann: tuple[float, float]
    alpha_tag: Tag
    beta_p_adj: tuple[float, ...]
    beta_tags: tuple[Tag, ...]
    sigma_e_ann: float


def multi_day_regression(sample: AnalysisSample, horizon: int = HORIZON) -> MultiDayFit | None:
    """The 5-day estimate of M3.6, or None when fewer than ``MIN_BLOCKS`` blocks exist."""
    y = sample.xret.to_numpy(dtype=np.float64)
    f = sample.factors.loc[:, list(FACTOR_CODES)].to_numpy(dtype=np.float64)
    if len(y) // horizon < MIN_BLOCKS:
        return None
    yb, fb, unused = block_sums(y, f, horizon)
    names = tuple(DISPLAY_NAMES[c] for c in FACTOR_CODES)
    fit = ols_hac(yb, fb, names=names)
    scale = A / horizon
    beta_p = [float(p) for p in fit.pvalues[1:]]
    _, p_adj = bh_adjust(beta_p)
    index = pd.DatetimeIndex(sample.xret.index)
    return MultiDayFit(
        horizon=horizon,
        n_blocks=len(yb),
        n_unused=unused,
        first_date=pd.Timestamp(index[0]).date(),
        last_date=pd.Timestamp(index[len(yb) * horizon - 1]).date(),
        fit=fit,
        alpha_ann=scale * float(fit.params[0]),
        alpha_se_ann=scale * float(fit.bse[0]),
        alpha_ci_ann=(scale * float(fit.ci_low[0]), scale * float(fit.ci_high[0])),
        alpha_tag=alpha_tag(float(fit.pvalues[0])),
        beta_p_adj=tuple(p_adj),
        beta_tags=tuple(significance_tags(beta_p)),
        sigma_e_ann=math.sqrt(scale) * float(np.std(fit.resid, ddof=1)),
    )


# ----------------------------------------------------------------------------- tags
def combine_tags(daily: Sequence[Tag], multi: Sequence[Tag]) -> list[Tag]:
    """Reliable only when both the daily and the multi-day rule reject (M3.6)."""
    return [
        "reliable" if d == "reliable" and m == "reliable" else "noise"
        for d, m in zip(daily, multi, strict=True)
    ]


def apply_gate(reg: FullSampleRegression, multi: MultiDayFit) -> FullSampleRegression:
    """Daily regression with the M3.6 conjunction tags; every daily number is unchanged."""
    alpha = combine_tags([alpha_tag(float(reg.fit.pvalues[0]))], [multi.alpha_tag])[0]
    tags = tuple(combine_tags(list(reg.beta_tags), list(multi.beta_tags)))
    return dataclasses.replace(
        reg,
        alpha_tag=alpha,
        beta_tags=tags,
        interpretations=tuple(
            beta_interpretation(name, float(b), t)
            for name, b, t in zip(reg.names, reg.fit.params[1:], tags, strict=True)
        ),
    )
