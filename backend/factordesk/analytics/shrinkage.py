"""Shrunk (Bayesian) betas: posterior, credible intervals, prior weight and power (SB1-SB5).

The posterior is built on the large-sample distribution of the OLS estimator, not on a likelihood
of the data: ``b | beta ~ N(beta, V)`` with ``V`` the HAC covariance block of M0.5 (SB1.1). With a
normal prior ``beta ~ N(m0, diag(tau^2))`` it is

``V_post = (V^-1 + T0^-1)^-1``, ``b_post = V_post (V^-1 b + T0^-1 m0)``, ``S_w = V_post T0^-1``

(SB3). This module adds no hypothesis test, no p-value and no Benjamini-Hochberg family (SD5).
Shrunk betas never replace the OLS betas anywhere (SD3): nothing outside the shrunk-betas section
may import this module (test TSB18).

Pure: no I/O, no clock, no randomness. Inputs are not mutated. The prior itself (``m0``, ``tau``)
comes from ``analytics/shrinkage_prior.py``.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from statistics import NormalDist

import numpy as np
from numpy.typing import NDArray

from factordesk.analytics.regression import Z_975, A, OLSHACFit, hac_lags, ols_hac

FloatArray = NDArray[np.float64]

COND_LIMIT = 1e12
"""``cond(V)`` above this is reported as ``singular_covariance`` (SB3; M3 rank guard, F3)."""
POWER_ALPHA = 0.01
"""Level of the MDE statement: the Benjamini-Hochberg worst case for 5 betas, 0.05 / 5 (SB5)."""
POWER_LEVEL = 0.80
K80: float = NormalDist().inv_cdf(1.0 - POWER_ALPHA / 2.0) + NormalDist().inv_cdf(POWER_LEVEL)
"""``z(1 - a/2) + z(0.80)`` with ``a = 0.01``: 3.41745 (SB0.2)."""
DELTA = 0.05
"""Smallest style beta the "years to detect" sentence asks about; fixed (SB10.4 Q3)."""
MAX_YEARS_SHOWN = 50.0
"""Beyond this many extra years the sentence says "not detectable" (SB5)."""
PULL_DISPLAY_THRESHOLD = 0.05
"""A shrunk marker is drawn only for a factor pulled at least this much (SB6 rule 2)."""
MARKET_INDEX = 0
"""Position of Mkt-RF: the report tests ``beta = 0`` there, so no "years" sentence (SB5)."""

_ARTICLE = {"SMB": "an", "HML": "an", "RMW": "an"}


class SingularCovarianceError(ValueError):
    """``V`` is not a usable covariance: not finite, not positive definite, or ``cond > 1e12``."""


@dataclass(frozen=True)
class Posterior:
    """Posterior of the five betas under the stated prior (SB3). Index order is the factor order."""

    b_ols: FloatArray
    se_hac: FloatArray
    centre: FloatArray
    tau: FloatArray
    b_post: FloatArray
    v_post: FloatArray
    weight: FloatArray
    """``S_w = V_post T0^-1`` (5 x 5)."""
    pull: FloatArray
    """``S_w[j, j]``, unclipped."""
    sd_post: FloatArray
    cred_low: FloatArray
    cred_high: FloatArray
    moved_away: tuple[bool, ...]
    """True where the shrunk beta moved away from its own prior centre (L-CORR-MOVE, SB6)."""


def _as_vector(value: object, name: str) -> FloatArray:
    out = np.asarray(value, dtype=np.float64)
    if out.ndim != 1:
        raise ValueError(f"{name} must be a vector")
    return out


def check_covariance(cov: FloatArray) -> None:
    """Raise ``SingularCovarianceError`` unless ``cov`` is finite, symmetric positive definite and
    well conditioned (``cond <= 1e12``, SB3)."""
    if not bool(np.isfinite(cov).all()):
        raise SingularCovarianceError("the covariance matrix of the betas is not finite")
    sym = 0.5 * (cov + cov.T)
    eig = np.linalg.eigvalsh(sym)
    if not float(eig[0]) > 0.0 or float(eig[-1]) / float(eig[0]) > COND_LIMIT:
        raise SingularCovarianceError(
            "the covariance matrix of the betas is singular or ill-conditioned "
            f"(condition number above {COND_LIMIT:.0e})"
        )


def posterior(b: FloatArray, cov: FloatArray, centre: FloatArray, tau: FloatArray) -> Posterior:
    """Normal-normal posterior of ``beta`` given the estimate ``b`` with covariance ``cov`` (SB3).

    ``centre`` is ``m0``, ``tau`` the prior standard deviations (``T0 = diag(tau^2)``). Solved with
    ``numpy.linalg.solve``; raises ``SingularCovarianceError`` when ``cond(cov) > 1e12``.
    """
    bv = _as_vector(b, "b")
    m0 = _as_vector(centre, "centre")
    tv = _as_vector(tau, "tau")
    k = bv.shape[0]
    v = np.asarray(cov, dtype=np.float64)
    if v.shape != (k, k) or m0.shape != (k,) or tv.shape != (k,):
        raise ValueError("b, cov, centre and tau must have matching dimensions")
    if not bool((tv > 0.0).all() and np.isfinite(tv).all()):
        raise ValueError("tau must be positive and finite")
    check_covariance(v)
    v = 0.5 * (v + v.T)

    eye = np.eye(k)
    prior_precision = 1.0 / tv**2
    precision = np.linalg.solve(v, eye)  # V^-1
    v_post = np.linalg.solve(precision + np.diag(prior_precision), eye)
    v_post = 0.5 * (v_post + v_post.T)
    weight = v_post @ np.diag(prior_precision)  # S_w
    b_post = v_post @ (precision @ bv + prior_precision * m0)
    sd_post = np.sqrt(np.diag(v_post))
    shift = b_post - bv
    toward = m0 - bv
    return Posterior(
        b_ols=bv,
        se_hac=np.sqrt(np.diag(v)),
        centre=m0,
        tau=tv,
        b_post=b_post,
        v_post=v_post,
        weight=weight,
        pull=np.diag(weight).copy(),
        sd_post=sd_post,
        cred_low=b_post - Z_975 * sd_post,
        cred_high=b_post + Z_975 * sd_post,
        moved_away=tuple(bool(s * t < 0.0) for s, t in zip(shift, toward, strict=True)),
    )


def window_fit(xret: FloatArray, factors: FloatArray, window: int) -> OLSHACFit:
    """OLS with HAC ``L(window)`` on the last ``window`` rows: the latest window (M4, SB0.1).

    The same fit as the last stamp of the rolling series, here with its full covariance matrix.
    """
    if window <= 0 or window > len(xret):
        raise ValueError("window must be between 1 and the number of rows")
    return ols_hac(xret[-window:], factors[-window:], lags=hac_lags(window))


def display_pull(pull: float) -> float:
    """The pull as shown to a reader: clipped to ``[0, 1]`` (the payload keeps the raw value)."""
    return min(1.0, max(0.0, pull))


def any_visible_pull(pull: Sequence[float]) -> bool:
    """True when a factor is pulled by ``PULL_DISPLAY_THRESHOLD`` or more (SB6 rule 2)."""
    return any(display_pull(p) >= PULL_DISPLAY_THRESHOLD for p in pull)


# ----------------------------------------------------------------------------------- power (SB5)
@dataclass(frozen=True)
class Power:
    """Minimum detectable effect and data needed for one factor (SB5)."""

    factor: str
    mde80: float
    n_required: float
    """Rows needed to detect ``delta`` at the same power (``n (k80 se / delta)^2``)."""
    extra_years: float | None
    """Extra years of similar data needed; ``None`` for the market factor (no sentence)."""
    text: str


def mde(se: float, k: float = K80) -> float:
    """``MDE = k80 * se`` (SB5)."""
    return k * se


def rows_required(se: float, n: int, delta: float = DELTA, k: float = K80) -> float:
    """``n_req = n (k se / delta)^2``: the standard error shrinks like ``1 / sqrt(n)`` (SB5)."""
    return n * (k * se / delta) ** 2


def extra_years(se: float, n: int, delta: float = DELTA, k: float = K80) -> float:
    """``max(0, n_req - n) / 252`` additional years of similar data to detect ``delta`` (SB5)."""
    return max(0.0, rows_required(se, n, delta, k) - n) / A


def power_text(factor: str, n: int, mde80: float, extra: float | None, delta: float = DELTA) -> str:
    """The MDE sentence plus, for a style factor, the "years to detect" sentence (SB5 templates)."""
    article = _ARTICLE.get(factor, "a")
    years = n / A
    text = (
        f"With {years:.1f} years of data, {article} {factor} beta of {mde80:.2f} or larger would "
        "be detected with 80% power (after correcting for testing 5 betas)."
    )
    if extra is None:
        return text
    if extra == 0.0:
        return f"{text} A {factor} beta of {delta:.2f} is already detectable."
    if extra <= MAX_YEARS_SHOWN:
        return (
            f"{text} Detecting {article} {factor} beta of {delta:.2f} would take about "
            f"{extra:.1f} more years of similar data."
        )
    return (
        f"{text} {article.capitalize()} {factor} beta of {delta:.2f} is not detectable for this "
        f"stock with daily data (it would take more than {MAX_YEARS_SHOWN:.0f} years)."
    )


def power_statements(
    se: Sequence[float], n: int, names: Sequence[str], delta: float = DELTA
) -> tuple[Power, ...]:
    """One ``Power`` per factor from the HAC standard errors of the regression on ``n`` rows."""
    if len(se) != len(names):
        raise ValueError("one standard error per factor name is required")
    out: list[Power] = []
    for j, (s, name) in enumerate(zip(se, names, strict=True)):
        if not (math.isfinite(s) and s > 0.0):
            raise ValueError("standard errors must be positive and finite")
        m = mde(s)
        n_req = rows_required(s, n, delta)
        extra = None if j == MARKET_INDEX else extra_years(s, n, delta)
        out.append(Power(name, m, n_req, extra, power_text(name, n, m, extra, delta)))
    return tuple(out)
