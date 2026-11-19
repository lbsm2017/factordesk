"""Full-sample OLS with Newey-West HAC inference (methodology M0.5, M0.6, M3).

Every regression is OLS with an intercept. Standard errors are Newey-West (Bartlett kernel,
no small-sample correction, normal reference distribution) with the lag rule
``L(m) = floor(4 (m/100)^(2/9))`` applied to the observations of that regression. The
implementation is plain linear algebra and is cross-checked against the statsmodels reference
call ``OLS(y, X).fit(cov_type="HAC", cov_kwds={"maxlags": L, "use_correction": False},
use_t=False)`` in the tests.

Monthly subjects (owner decision) use the small-sample variant: the HAC covariance is scaled
by ``m / (m - k)`` and p-values, intervals and tags use Student-t with ``m - k`` degrees of
freedom, as statsmodels does with ``use_correction=True, use_t=True``. Daily output is unchanged.

Pure: no I/O, no clock, no randomness. Inputs are not mutated.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date
from statistics import NormalDist
from typing import Any, Literal, cast

import numpy as np
from numpy.typing import NDArray
from scipy.stats import t as student_t  # pyright: ignore[reportMissingTypeStubs]
from statsmodels.stats.multitest import (  # pyright: ignore[reportMissingTypeStubs]
    multipletests,  # pyright: ignore[reportUnknownVariableType]
)

from factordesk.analytics.sample import (
    DISPLAY_NAMES,
    FACTOR_CODES,
    AnalysisSample,
    DegenerateInputError,
)

FloatArray = NDArray[np.float64]
Tag = Literal["reliable", "noise"]

A = 252
"""Annualisation constant, trading days per year (M0.4). It is the default of every
``periods`` argument (observations per year): a daily series uses 252, a monthly one 12."""
BH_Q = 0.05
"""Benjamini-Hochberg level, fixed (M0.6)."""
ALPHA_LEVEL = 0.05
"""Nominal level of the single alpha test (M3.2)."""
Z_975: float = NormalDist().inv_cdf(0.975)
"""Two-sided 95% normal quantile (1.959964...)."""

_multipletests = cast(Callable[..., tuple[Any, Any, Any, Any]], multipletests)
_student_t = cast(Any, student_t)
_erfc = np.frompyfunc(math.erfc, 1, 1)


def two_sided_p(z: FloatArray) -> FloatArray:
    """``p = 2 (1 - Phi(|z|)) = erfc(|z| / sqrt 2)``, accurate in the far tail (M0.5)."""
    return np.asarray(_erfc(np.abs(z) / math.sqrt(2.0)), dtype=np.float64)


def two_sided_t_p(t: FloatArray, df: int) -> FloatArray:
    """Two-sided Student-t p-value ``2 (1 - F_df(|t|))``, from the survival function."""
    return np.asarray(2.0 * _student_t.sf(np.abs(t), df), dtype=np.float64)


def t_975(df: int) -> float:
    """Two-sided 95% Student-t quantile with ``df`` degrees of freedom."""
    return float(_student_t.ppf(0.975, df))


LARGE_ALPHA = 0.03
"""|alpha_ann| at or above which an insignificant alpha is explained (M3.2)."""
VIF_WARN = 5.0
VIF_STRONG = 10.0
KAPPA_WARN = 30.0
CORR_WARN = 0.6
MIN_UNEXPLAINED_SHARE = 1e-6
"""Design guard (M3.1): a factor whose variation is explained by the constant and the earlier
factors except for less than this share makes the design singular or nearly so."""
ZERO_SD_RELATIVE = 1e-12
"""A column whose sd is below this fraction of its largest absolute value is constant."""

_DEFAULT_NAMES: tuple[str, ...] = tuple(DISPLAY_NAMES[c] for c in FACTOR_CODES)


def unexplained_shares(x: FloatArray) -> tuple[NDArray[np.bool_], FloatArray]:
    """Design guard quantities for ``x = [1, f]`` (shape ``(..., m, k)``, stacked windows allowed).

    Returns ``(constant, share)`` per factor column: ``constant`` marks a column with (numerically)
    zero variance; ``share = R_jj^2 / sum_t (f_jt - mean f_j)^2`` is the part of factor ``j``'s
    centred variation not explained by the constant and the factors before it (QR, canonical
    order), i.e. ``1 - R^2`` of that sequential regression (M3.1).
    """
    xv = np.asarray(x, dtype=np.float64)
    f = xv[..., 1:]
    m = xv.shape[-2]
    centred = f - f.mean(axis=-2, keepdims=True)
    css = np.einsum("...ij,...ij->...j", centred, centred)
    largest = np.max(np.abs(f), axis=-2)
    constant = css <= m * (ZERO_SD_RELATIVE * largest) ** 2
    r = np.linalg.qr(xv, mode="r")
    diag = np.abs(np.diagonal(r, axis1=-2, axis2=-1))[..., 1:]
    share = np.where(constant, 0.0, diag**2 / np.where(constant, 1.0, css))
    return constant, np.asarray(share, dtype=np.float64)


def design_problem(factors: FloatArray, names: Sequence[str] = _DEFAULT_NAMES) -> str | None:
    """Why the design ``[1, f]`` cannot be fitted (M3.1), or None when it is fine."""
    f = np.asarray(factors, dtype=np.float64)
    constant, share = unexplained_shares(with_intercept(f))
    for j in range(f.shape[1]):
        name = names[j] if j < len(names) else f"column {j + 1}"
        if constant[j]:
            return (
                f"factor {name} has zero variance in the sample, so the factor matrix is "
                "singular; check the factor data"
            )
        if share[j] < MIN_UNEXPLAINED_SHARE:
            return (
                f"factor {name} is a linear combination of the constant and the other factors "
                f"(only {share[j]:.1e} of its variance is not explained by them; the limit is "
                f"{MIN_UNEXPLAINED_SHARE:.0e}), so the factor matrix is singular or nearly so; "
                "check the factor data"
            )
    return None


def hac_lags(m: int) -> int:
    """Newey-West lag rule ``floor(4 (m/100)^(2/9))`` for a regression on ``m`` rows (M0.5)."""
    if m <= 0:
        raise ValueError("number of observations must be positive")
    return math.floor(4.0 * (m / 100.0) ** (2.0 / 9.0))


def bartlett_weights(lags: int) -> FloatArray:
    """``w_l = 1 - l/(L+1)`` for ``l = 0..L`` (``w_0 = 1``)."""
    return 1.0 - np.arange(lags + 1, dtype=np.float64) / (lags + 1)


def with_intercept(factors: FloatArray) -> FloatArray:
    """Design matrix ``[1, f_t']`` (the constant is always the first column)."""
    f = np.asarray(factors, dtype=np.float64)
    return np.column_stack([np.ones(f.shape[0], dtype=np.float64), f])


def hac_meat(scores: FloatArray, lags: int) -> FloatArray:
    """``S_hat = sum_t u_t u_t' + sum_l w_l (Gamma_l + Gamma_l')`` with ``u_t = e_t x_t``.

    ``Gamma_l = sum_{t=l+1..m} u_t u_{t-l}'``. Sums, not means (M0.5).
    """
    w = bartlett_weights(lags)
    meat = scores.T @ scores
    for lag in range(1, lags + 1):
        gamma = scores[lag:].T @ scores[:-lag]
        meat += w[lag] * (gamma + gamma.T)
    return meat


@dataclass(frozen=True)
class OLSHACFit:
    """OLS with intercept and HAC covariance. Index 0 is the intercept, 1..K the factors."""

    params: FloatArray
    cov: FloatArray
    bse: FloatArray
    zvalues: FloatArray
    pvalues: FloatArray
    ci_low: FloatArray
    ci_high: FloatArray
    resid: FloatArray
    rsquared: float
    rsquared_adj: float
    nobs: int
    lags: int
    t_df: int | None = None
    """Student-t degrees of freedom of the small-sample variant; None for the normal reference.
    ``zvalues`` then holds t-statistics."""


def ols_hac(
    y: FloatArray,
    factors: FloatArray,
    lags: int | None = None,
    names: Sequence[str] = _DEFAULT_NAMES,
    *,
    small_sample: bool = False,
) -> OLSHACFit:
    """Fit ``y = alpha + beta' f + e`` by OLS with Newey-West HAC covariance (M0.5).

    ``lags`` defaults to ``hac_lags(len(y))``. Solved through a QR decomposition of the design
    matrix (no normal equations), so precision does not depend on the scale of the columns.
    Raises ``DegenerateInputError`` when the design is singular or nearly so, or ``y`` is
    constant (M3.1, D30); ``names`` label the factors in that message.

    ``small_sample`` (monthly subjects) scales the covariance by ``m / (m - k)`` and uses
    Student-t with ``m - k`` degrees of freedom for the p-values and the 95% intervals.
    """
    yv = np.asarray(y, dtype=np.float64)
    x = with_intercept(factors)
    m, k = x.shape
    if yv.shape != (m,):
        raise ValueError("y and factors must have the same number of rows")
    if m <= k:
        raise ValueError(f"need more observations ({m}) than parameters ({k})")
    if not (np.isfinite(yv).all() and np.isfinite(x).all()):
        raise ValueError("inputs must be finite; excluded rows are removed upstream, never filled")
    problem = design_problem(x[:, 1:], names)
    if problem is not None:
        raise DegenerateInputError(problem)
    centred_y = yv - yv.mean()
    if float(centred_y @ centred_y) <= m * (ZERO_SD_RELATIVE * float(np.max(np.abs(yv)))) ** 2:
        raise DegenerateInputError(
            "the excess return does not vary over the sample, so there is nothing to explain"
        )
    n_lags = hac_lags(m) if lags is None else lags

    q, r = np.linalg.qr(x)
    r_inv: FloatArray = np.linalg.solve(r, np.eye(k))
    params: FloatArray = r_inv @ (q.T @ yv)
    bread = r_inv @ r_inv.T  # (X'X)^-1
    resid: FloatArray = yv - x @ params
    cov: FloatArray = bread @ hac_meat(x * resid[:, None], n_lags) @ bread
    t_df = m - k if small_sample else None
    if t_df is not None:
        cov = cov * (m / t_df)
    bse: FloatArray = np.sqrt(np.diag(cov))
    z = params / bse
    pvalues = two_sided_p(z) if t_df is None else two_sided_t_p(z, t_df)
    q975 = Z_975 if t_df is None else t_975(t_df)

    ssr = float(resid @ resid)
    centred = yv - yv.mean()
    tss = float(centred @ centred)
    r2 = 1.0 - ssr / tss
    r2_adj = 1.0 - (1.0 - r2) * (m - 1) / (m - k)
    return OLSHACFit(
        params=params,
        cov=cov,
        bse=bse,
        zvalues=z,
        pvalues=pvalues,
        ci_low=params - q975 * bse,
        ci_high=params + q975 * bse,
        resid=resid,
        rsquared=r2,
        rsquared_adj=r2_adj,
        nobs=m,
        lags=n_lags,
        t_df=t_df,
    )


# ----------------------------------------------------------------------------- significance
def bh_adjust(pvalues: Sequence[float]) -> tuple[list[bool], list[float]]:
    """Benjamini-Hochberg at q = 0.05: (rejected, adjusted p) per input, input order (M0.6)."""
    p = np.asarray(pvalues, dtype=np.float64)
    if p.size == 0:
        return [], []
    reject, p_adj, _, _ = _multipletests(p, alpha=BH_Q, method="fdr_bh")
    rej = np.asarray(reject, dtype=bool)
    adj = np.asarray(p_adj, dtype=np.float64)
    return [bool(v) for v in rej], [float(v) for v in adj]


def significance_tags(pvalues: Sequence[float]) -> list[Tag]:
    """Beta tags: BH-rejected = 'reliable', otherwise 'noise' (D1, the only rule)."""
    reject, _ = bh_adjust(pvalues)
    return ["reliable" if r else "noise" for r in reject]


def alpha_tag(p: float) -> Tag:
    """Alpha is a single nominal test: reliable iff p < 0.05 (M3.2)."""
    return "reliable" if p < ALPHA_LEVEL else "noise"


def _pct(x: float) -> str:
    return f"{x * 100:+.2f}%"


def alpha_sentence(
    alpha_ann: float, p: float, sigma_e_ann: float, n: int, se_ann: float, periods: int = A
) -> str | None:
    """Explain a large but insignificant alpha (M3.2); None when it does not apply.

    ``n`` observations at ``periods`` a year span ``n / periods`` years.
    """
    if abs(alpha_ann) < LARGE_ALPHA or p < ALPHA_LEVEL:
        return None
    years = n / periods
    return (
        f"Alpha of {_pct(alpha_ann)} a year cannot be told apart from zero: residual volatility "
        f"is {sigma_e_ann * 100:.2f}% a year over {years:.1f} years, so the standard error of "
        f"annual alpha is {se_ann * 100:.2f}%."
    )


def beta_interpretation(name: str, beta: float, tag: Tag) -> str | None:
    """Plain-English reading of a beta, generated only for reliable betas (M3.2)."""
    if tag != "reliable":
        return None
    return (
        f"A 1 percentage-point move in the {name} return has gone with a {beta:+.2f} "
        "percentage-point move in the excess return, other factors held fixed."
    )


# ----------------------------------------------------------------------------- collinearity
def vif(factors: FloatArray) -> FloatArray:
    """``VIF_j = 1 / (1 - R^2_j)``, ``R^2_j`` from OLS of factor j on a constant and the rest."""
    f = np.asarray(factors, dtype=np.float64)
    out = np.empty(f.shape[1], dtype=np.float64)
    for j in range(f.shape[1]):
        target = f[:, j]
        x = with_intercept(np.delete(f, j, axis=1))
        coef, *_ = np.linalg.lstsq(x, target, rcond=None)
        resid = target - x @ coef
        centred = target - target.mean()
        r2 = 1.0 - float(resid @ resid) / float(centred @ centred)
        out[j] = 1.0 / (1.0 - r2)
    return out


def condition_number(factors: FloatArray) -> float:
    """``sqrt(lambda_max / lambda_min)`` of the factor correlation matrix (M3.4)."""
    eig = np.linalg.eigvalsh(np.corrcoef(np.asarray(factors, dtype=np.float64), rowvar=False))
    return float(math.sqrt(eig[-1] / eig[0]))


@dataclass(frozen=True)
class Collinearity:
    vif: dict[str, float]
    kappa: float
    high_corr_pairs: tuple[tuple[str, str, float], ...]
    warnings: tuple[str, ...]


def collinearity(factors: FloatArray, names: Sequence[str]) -> Collinearity:
    """VIF, condition number, high-correlation pairs and the M3.4 warning sentences."""
    v = vif(factors)
    kappa = condition_number(factors)
    corr: FloatArray = np.asarray(
        np.corrcoef(np.asarray(factors, dtype=np.float64), rowvar=False), dtype=np.float64
    )
    pairs = tuple(
        (names[i], names[j], float(corr[i, j]))
        for i in range(len(names))
        for j in range(i + 1, len(names))
        if abs(corr[i, j]) > CORR_WARN
    )
    warnings: list[str] = []
    over5 = [names[j] for j in range(len(names)) if v[j] > VIF_WARN]
    over10 = [names[j] for j in range(len(names)) if v[j] > VIF_STRONG]
    if over5:
        warnings.append(
            f"Factors {', '.join(over5)} overlap strongly (typically HML/CMA/RMW). Their "
            "individual betas are imprecise; the combined exposure is better determined."
        )
    if over10:
        warnings.append(
            f"Strong collinearity: variance inflation factor above 10 for {', '.join(over10)}."
        )
    if kappa > KAPPA_WARN:
        warnings.append(
            f"The factor correlation matrix has condition number {kappa:.1f} (above 30)."
        )
    if pairs:
        listing = ", ".join(f"{a}/{b} ({c:+.2f})" for a, b, c in pairs)
        warnings.append(f"Factor pairs with |correlation| above 0.6: {listing}.")
    return Collinearity(
        vif={names[j]: float(v[j]) for j in range(len(names))},
        kappa=kappa,
        high_corr_pairs=pairs,
        warnings=tuple(warnings),
    )


# ----------------------------------------------------------------------------- full sample
@dataclass(frozen=True)
class FullSampleRegression:
    """M3 outputs for the analysis sample. Stamped at ``end`` (in-sample, whole window)."""

    fit: OLSHACFit
    names: tuple[str, ...]
    """Display names of the factors, canonical order."""
    alpha_ann: float
    alpha_se_ann: float
    alpha_ci_ann: tuple[float, float]
    alpha_tag: Tag
    alpha_sentence: str | None
    beta_p_adj: tuple[float, ...]
    beta_tags: tuple[Tag, ...]
    interpretations: tuple[str | None, ...]
    sigma_e_ann: float
    collinearity: Collinearity
    end: date
    periods: int = A
    """Observations a year used for the annualised figures (252 daily, 12 monthly)."""

    @property
    def betas(self) -> FloatArray:
        return self.fit.params[1:]

    @property
    def alpha(self) -> float:
        return float(self.fit.params[0])


def run_regression(
    sample: AnalysisSample, periods: int = A, *, small_sample: bool = False
) -> FullSampleRegression:
    """Full-sample OLS of ``y`` on the five factors with HAC ``L(n)`` (M3.1-M3.4).

    ``periods`` is the number of observations a year (252 daily, 12 monthly). It scales the
    annualised figures only: alpha and its standard error and interval by ``periods`` (arithmetic,
    M0.4) and the residual volatility by ``sqrt(periods)``. The fit itself does not depend on it.
    ``small_sample`` (monthly subjects) selects the corrected covariance and Student-t inference
    of ``ols_hac``; the tags follow from those p-values.
    """
    if periods <= 0:
        raise ValueError("periods must be positive")
    y = sample.xret.to_numpy(dtype=np.float64)
    f = sample.factors.loc[:, list(FACTOR_CODES)].to_numpy(dtype=np.float64)
    names = tuple(DISPLAY_NAMES[c] for c in FACTOR_CODES)
    fit = ols_hac(y, f, names=names, small_sample=small_sample)

    beta_p = [float(p) for p in fit.pvalues[1:]]
    _, p_adj = bh_adjust(beta_p)
    tags = significance_tags(beta_p)
    alpha_ann = periods * float(fit.params[0])
    alpha_se_ann = periods * float(fit.bse[0])
    sigma_e_ann = math.sqrt(periods) * float(np.std(fit.resid, ddof=1))
    a_tag = alpha_tag(float(fit.pvalues[0]))
    return FullSampleRegression(
        fit=fit,
        names=names,
        alpha_ann=alpha_ann,
        alpha_se_ann=alpha_se_ann,
        alpha_ci_ann=(periods * float(fit.ci_low[0]), periods * float(fit.ci_high[0])),
        alpha_tag=a_tag,
        alpha_sentence=alpha_sentence(
            alpha_ann, float(fit.pvalues[0]), sigma_e_ann, fit.nobs, alpha_se_ann, periods
        ),
        beta_p_adj=tuple(p_adj),
        beta_tags=tuple(tags),
        interpretations=tuple(
            beta_interpretation(nm, float(b), t)
            for nm, b, t in zip(names, fit.params[1:], tags, strict=True)
        ),
        sigma_e_ann=sigma_e_ann,
        collinearity=collinearity(f, names),
        end=sample.end,
        periods=periods,
    )
