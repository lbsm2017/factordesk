"""Return contribution and Euler risk contribution (methodology M6.1, M6.4, M7).

Both use the full-sample OLS fit (M3) on the analysis sample ``S``:

* Return (M6.1): because OLS with an intercept has residuals summing to zero,
  ``mean(y) = alpha + sum_i beta_i mean(f_i)`` exactly. Every row is ``x periods`` (arithmetic,
  never compounded; ``periods`` = 252 for daily data, 12 for monthly); the residual row is
  reported, not zeroed.
* Risk (M7): ``V = beta' Sigma_f beta + sigma2_e`` with ``Sigma_f`` (ddof = 1) and
  ``sigma2_e = SSR / (n - 1)`` (D5), so ``V`` equals the sample variance of ``y`` exactly and
  the Euler shares plus the idiosyncratic share sum to one.

Pure: no I/O, no clock. Inputs are not mutated.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from factordesk.analytics.regression import A, FullSampleRegression, Tag
from factordesk.analytics.sample import FACTOR_CODES, AnalysisSample, Exclusion, UncoveredTail

FloatArray = NDArray[np.float64]

IDIOSYNCRATIC = "Idiosyncratic"
EXCLUSION_REASON_TEXT: dict[str, str] = {
    "multi_day_return": "return spans several factor days",
    "no_factor_row": "date not in the factor file",
    "price_missing": "price missing",
    "factor_missing": "factor value missing",
}


# ----------------------------------------------------------------------------- return (M6.1)
@dataclass(frozen=True)
class ReturnAttribution:
    """Annualised arithmetic contributions; ``identity_residual`` is float error only."""

    contributions: dict[str, float]
    """Display name -> periods x beta_i x mean(f_i)."""
    alpha_ann: float
    residual_ann: float
    total_ann: float
    identity_residual: float


def return_contribution(
    xret: FloatArray,
    factors: FloatArray,
    alpha: float,
    betas: FloatArray,
    resid: FloatArray,
    names: Sequence[str],
    periods: int = A,
) -> ReturnAttribution:
    """Static full-sample return contribution (M6.1). Arrays are the rows of ``S``.

    ``periods`` is the number of rows a year (252 daily, 12 monthly).
    """
    f = np.asarray(factors, dtype=np.float64)
    b = np.asarray(betas, dtype=np.float64)
    contrib = periods * b * f.mean(axis=0)
    alpha_ann = periods * alpha
    residual = periods * float(np.mean(resid))
    total = periods * float(np.mean(xret))
    identity = total - (float(contrib.sum()) + alpha_ann + residual)
    return ReturnAttribution(
        contributions={n: float(c) for n, c in zip(names, contrib, strict=True)},
        alpha_ann=alpha_ann,
        residual_ann=residual,
        total_ann=total,
        identity_residual=identity,
    )


def return_contribution_for(sample: AnalysisSample, reg: FullSampleRegression) -> ReturnAttribution:
    """``return_contribution`` on the analysis sample and its full-sample regression.

    Annualised with the regression's own ``periods``.
    """
    return return_contribution(
        sample.xret.to_numpy(dtype=np.float64),
        sample.factors.loc[:, list(FACTOR_CODES)].to_numpy(dtype=np.float64),
        reg.alpha,
        reg.betas,
        reg.fit.resid,
        reg.names,
        reg.periods,
    )


def memo_rows(
    uncovered: UncoveredTail,
    excluded: Sequence[Exclusion],
    factor_last_date: object,
    *,
    unit: str = "trading days",
    subject: str = "stock",
) -> list[str]:
    """Memo rows below the identity (M6.4, D8). They are not part of any sum.

    ``unit`` names the observations ("trading days", "months"); ``subject`` what earned the
    return ("stock", "track record").
    """
    rows: list[str] = []
    if uncovered.n:
        ret = (
            f"{uncovered.compounded_return * 100:+.2f}%"
            if uncovered.compounded_return is not None
            else "not available (a price is missing)"
        )
        rows.append(
            f"Not covered by factor data: {uncovered.n} {unit} after {factor_last_date}; "
            f"{subject} return {ret} (compounded, raw, not excess). Not attributed."
        )
    else:
        rows.append("Not covered by factor data: none (every analysed date has factor data).")
    counts: dict[str, int] = {}
    for ex in excluded:
        counts[ex.reason] = counts.get(ex.reason, 0) + 1
    detail = "; ".join(
        f"{EXCLUSION_REASON_TEXT[r]}: {counts[r]}" for r in EXCLUSION_REASON_TEXT if r in counts
    )
    rows.append(f"Excluded rows: {len(excluded)}" + (f" ({detail})." if detail else "."))
    return rows


# ----------------------------------------------------------------------------- risk (M7)
@dataclass(frozen=True)
class RiskAttribution:
    """Euler shares of variance. ``shares[i]`` may be negative."""

    names: tuple[str, ...]
    shares: FloatArray
    idio_share: float
    variance: float
    """``V`` (per period of the data); equals ``var(y, ddof=1)``."""
    sums_to_one_residual: float
    sigma: FloatArray
    """Per-period factor standard deviations ``sqrt(Sigma_f[i, i])``."""
    sigma_sys: float
    rho_sys: tuple[float | None, ...]
    betas: FloatArray
    periods: int = A
    """Rows a year (252 daily, 12 monthly), for the annualised volatilities."""

    @property
    def vol_ann(self) -> float:
        """``sqrt(periods x V)``."""
        return math.sqrt(self.periods * self.variance)

    @property
    def sigma_ann(self) -> FloatArray:
        """Annualised factor volatilities ``sqrt(periods) x sigma``."""
        return np.asarray(math.sqrt(self.periods) * self.sigma, dtype=np.float64)


def risk_contribution(
    factors: FloatArray,
    betas: FloatArray,
    resid: FloatArray,
    names: Sequence[str],
    periods: int = A,
) -> RiskAttribution:
    """Euler risk decomposition with the D5 variance convention (M7).

    ``Sigma_f`` is the sample covariance of the factor rows (ddof = 1) and
    ``sigma2_e = SSR / (n - 1)``, so ``V`` equals ``var(y, ddof=1)`` exactly for an OLS fit.
    """
    f = np.asarray(factors, dtype=np.float64)
    e = np.asarray(resid, dtype=np.float64)
    n = f.shape[0]
    sigma_f = np.cov(f, rowvar=False, ddof=1)
    return euler_risk(sigma_f, betas, float(e @ e) / (n - 1), names, periods)


def euler_risk(
    sigma_f: FloatArray,
    betas: FloatArray,
    sigma2_e: float,
    names: Sequence[str],
    periods: int = A,
) -> RiskAttribution:
    """Euler shares ``RC_i = beta_i (Sigma_f beta)_i / V``, ``RC_idio = sigma2_e / V`` (M7)."""
    b = np.asarray(betas, dtype=np.float64)
    sigma_f = np.asarray(sigma_f, dtype=np.float64)
    sb = sigma_f @ b
    systematic = float(b @ sb)
    v = systematic + sigma2_e
    shares = b * sb / v
    idio = sigma2_e / v
    sigma = np.sqrt(np.diag(sigma_f))
    sigma_sys = math.sqrt(systematic) if systematic > 0 else 0.0
    rho: tuple[float | None, ...] = tuple(
        float(sb[i] / (sigma[i] * sigma_sys)) if sigma_sys > 0 and sigma[i] > 0 else None
        for i in range(len(b))
    )
    return RiskAttribution(
        names=tuple(names),
        shares=shares,
        idio_share=idio,
        variance=v,
        sums_to_one_residual=1.0 - (float(shares.sum()) + idio),
        sigma=sigma,
        sigma_sys=sigma_sys,
        rho_sys=rho,
        betas=b,
        periods=periods,
    )


def risk_contribution_for(sample: AnalysisSample, reg: FullSampleRegression) -> RiskAttribution:
    """``risk_contribution`` on the analysis sample and its full-sample regression.

    Annualised with the regression's own ``periods``.
    """
    return risk_contribution(
        sample.factors.loc[:, list(FACTOR_CODES)].to_numpy(dtype=np.float64),
        reg.betas,
        reg.fit.resid,
        reg.names,
        reg.periods,
    )


def risk_order(names: Sequence[str], shares: Sequence[float]) -> list[str]:
    """Bar order: factors by share descending (ties: canonical order), idiosyncratic last."""
    ranked = sorted(range(len(names)), key=lambda i: (-shares[i], i))
    return [names[i] for i in ranked] + [IDIOSYNCRATIC]


def _ranks_desc(values: Sequence[float]) -> list[int]:
    """1-based ranks, 1 = largest; ties broken by input (canonical) order."""
    order = sorted(range(len(values)), key=lambda i: (-values[i], i))
    ranks = [0] * len(values)
    for rank, i in enumerate(order, start=1):
        ranks[i] = rank
    return ranks


def risk_sentences(
    names: Sequence[str], betas: Sequence[float], shares: Sequence[float], tags: Sequence[Tag]
) -> list[str]:
    """Disagreement and offset sentences, computed among reliable betas only (M7)."""
    idx = [i for i, t in enumerate(tags) if t == "reliable"]
    out: list[str] = []
    if idx:
        rank_beta = _ranks_desc([abs(betas[i]) for i in idx])
        rank_rc = _ranks_desc([shares[i] for i in idx])
        best: tuple[int, int] | None = None  # (gap, position in idx)
        for pos in range(len(idx)):
            gap = rank_beta[pos] - rank_rc[pos]
            if gap >= 2 and (best is None or gap > best[0]):
                best = (gap, pos)
        if best is not None:
            pos = best[1]
            out.append(
                f"{names[idx[pos]]} ranks #{rank_rc[pos]} by risk but only #{rank_beta[pos]} by "
                "beta size: the factor is volatile or moves with the other exposures."
            )
    for i in idx:
        if shares[i] < 0:
            out.append(
                f"{names[i]} has a negative share: it offsets part of the other exposures "
                "in the variance split."
            )
    return out
