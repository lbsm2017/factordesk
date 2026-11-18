"""Stability of the alpha: rolling alpha, one-year windows, split halves, calendar years (R5).

Spec: ``docs/methodology-residual-analysis.md`` R5; oracle ``docs/test-oracle-residual-analysis.md``
TR23-TR28.

* Rolling 252-row alpha (R5.1): the intercept of the M4 window, reused from ``rolling_betas``.
* Non-overlapping one-year windows (R5.2): tiled from the end of the sample, one Benjamini-
  Hochberg family (FR1, q = 0.05, ``m = J``).
* Split-half alpha (R5.3): one prespecified split in the middle, the M10 pooled estimator with
  ``g_t = 1[t > n_1]``, HAC ``L(n)``.
* Calendar-year table (R5.4): within-year sums of daily residuals, arithmetic, no tests.

Pure: no I/O, no clock, no randomness. Inputs are not mutated.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import date
from typing import Literal

import numpy as np
from numpy.typing import NDArray

from factordesk.analytics.regression import (
    Z_975,
    A,
    Tag,
    bh_adjust,
    ols_hac,
    two_sided_p,
)
from factordesk.analytics.rolling import RollingBetas
from factordesk.analytics.sample import DISPLAY_NAMES, FACTOR_CODES, AnalysisSample

FloatArray = NDArray[np.float64]
Status = Literal["ok", "insufficient_data", "not_applicable", "failed"]

WINDOW = 252
"""Rolling alpha window and one-year window length, fixed (R5.1, RD9)."""
PARTIAL_YEAR_ROWS = 200
"""A year with fewer rows is partial (M6.2)."""


# ----------------------------------------------------------------------------- rolling alpha
@dataclass(frozen=True)
class RollingAlphaSeries:
    """Trailing 252-row alpha per row of ``S``; NaN before the first stamp (R5.1)."""

    hac_lags: int
    n_stamps: int
    alpha_annual: FloatArray
    ci_low_annual: FloatArray
    ci_high_annual: FloatArray
    share_excluding_zero: float | None


def rolling_alpha(rolling: RollingBetas) -> RollingAlphaSeries:
    """``A alpha_t`` with the band ``A (alpha_t -/+ z se_t)`` from the M4 window of 252 rows."""
    if rolling.window != WINDOW:
        raise ValueError(f"rolling alpha uses the {WINDOW}-row window, got {rolling.window}")
    alpha = rolling.alpha.to_numpy(dtype=np.float64)
    se = rolling.alpha_se.to_numpy(dtype=np.float64)
    live = ~np.isnan(alpha)
    ann = A * alpha
    low = A * (alpha - Z_975 * se)
    high = A * (alpha + Z_975 * se)
    n_stamps = int(live.sum())
    excluding = int(np.count_nonzero(live & ((low > 0.0) | (high < 0.0))))
    return RollingAlphaSeries(
        hac_lags=rolling.lags,
        n_stamps=n_stamps,
        alpha_annual=np.asarray(ann, dtype=np.float64),
        ci_low_annual=np.asarray(low, dtype=np.float64),
        ci_high_annual=np.asarray(high, dtype=np.float64),
        share_excluding_zero=excluding / n_stamps if n_stamps else None,
    )


# ----------------------------------------------------------------------------- one-year windows
@dataclass(frozen=True)
class WindowAlpha:
    """Alpha of one disjoint 252-row window (the M4 stamp at its last row)."""

    start: date
    end: date
    n: int
    alpha_annual: float
    se_annual: float
    z: float
    p: float
    p_adj_bh: float
    tag: Tag


@dataclass(frozen=True)
class NonOverlappingResult:
    """Family FR1 (R5.2)."""

    status: Status
    reason: str | None
    family_size: int
    n_reliable: int
    windows: tuple[WindowAlpha, ...]
    """Most recent first."""


def non_overlapping_alpha(rolling: RollingBetas, dates: Sequence[date]) -> NonOverlappingResult:
    """``J = floor(n / 252)`` windows tiled from the end; BH across their ``J`` p-values (R5.2)."""
    if rolling.window != WINDOW:
        raise ValueError(f"windows use the {WINDOW}-row rolling fit, got {rolling.window}")
    n = len(dates)
    j_count = n // WINDOW
    if j_count < 2:
        return NonOverlappingResult(
            status="insufficient_data",
            reason=f"At least {2 * WINDOW} trading days are needed for two separate one-year "
            f"windows; this period has {n}.",
            family_size=0,
            n_reliable=0,
            windows=(),
        )
    alpha = rolling.alpha.to_numpy(dtype=np.float64)
    se = rolling.alpha_se.to_numpy(dtype=np.float64)
    ends = [n - WINDOW * j - 1 for j in range(j_count)]  # 0-based row of each window's last day
    if not bool(np.isfinite(alpha[ends]).all() and np.isfinite(se[ends]).all()):
        return NonOverlappingResult(
            status="failed",
            reason="A one-year window could not be fitted (singular factor design).",
            family_size=0,
            n_reliable=0,
            windows=(),
        )
    z = alpha[ends] / se[ends]
    p = two_sided_p(np.asarray(z, dtype=np.float64))
    reject, p_adj = bh_adjust([float(v) for v in p])
    windows = tuple(
        WindowAlpha(
            start=dates[e - WINDOW + 1],
            end=dates[e],
            n=WINDOW,
            alpha_annual=A * float(alpha[e]),
            se_annual=A * float(se[e]),
            z=float(z[k]),
            p=float(p[k]),
            p_adj_bh=p_adj[k],
            tag="reliable" if reject[k] else "noise",
        )
        for k, e in enumerate(ends)
    )
    return NonOverlappingResult(
        status="ok",
        reason=None,
        family_size=j_count,
        n_reliable=sum(reject),
        windows=windows,
    )


# ----------------------------------------------------------------------------- split halves
@dataclass(frozen=True)
class SplitHalfResult:
    """One prespecified split at the middle of ``S`` (R5.3)."""

    status: Status
    reason: str | None
    first_start: date
    first_end: date
    second_start: date
    second_end: date
    n_first: int
    n_second: int
    hac_lags: int | None = None
    alpha_first_annual: float | None = None
    alpha_first_ci_low_annual: float | None = None
    alpha_first_ci_high_annual: float | None = None
    alpha_second_annual: float | None = None
    alpha_second_ci_low_annual: float | None = None
    alpha_second_ci_high_annual: float | None = None
    difference_annual: float | None = None
    difference_se_annual: float | None = None
    difference_z: float | None = None
    difference_p: float | None = None


def split_half_alpha(sample: AnalysisSample) -> SplitHalfResult:
    """Pooled regression ``y = a + b'f + c g + d'(g f)`` with ``g_t = 1[t > n_1]`` (R5.3).

    The point estimates equal two separate regressions on the halves. HAC lags are ``L(n)`` of
    the pooled fit. Betas are refitted in each half. The test of ``c = 0`` is one prespecified
    test at the nominal 5% level.
    """
    y = sample.xret.to_numpy(dtype=np.float64)
    f = sample.factors.loc[:, list(FACTOR_CODES)].to_numpy(dtype=np.float64)
    n = len(y)
    n1 = n // 2
    idx = sample.xret.index
    dates = [d.date() for d in idx]
    base = SplitHalfResult(
        status="insufficient_data",
        reason="",
        first_start=dates[0],
        first_end=dates[n1 - 1],
        second_start=dates[n1],
        second_end=dates[-1],
        n_first=n1,
        n_second=n - n1,
    )
    if n1 < WINDOW:
        return replace(
            base,
            reason=f"Each half needs at least {WINDOW} trading days; the first half has {n1}.",
        )
    g = (np.arange(n) >= n1).astype(np.float64)
    design = np.column_stack([f, g, f * g[:, None]])
    names = tuple(DISPLAY_NAMES[c] for c in FACTOR_CODES)
    fit = ols_hac(
        y,
        design,
        names=(*names, "second-half dummy", *(f"second half x {nm}" for nm in names)),
    )
    k_gamma = 6  # index of the split-dummy coefficient (0 is the constant)
    cov = fit.cov
    a1 = float(fit.params[0])
    gamma = float(fit.params[k_gamma])
    se1 = math.sqrt(float(cov[0, 0]))
    se2 = math.sqrt(float(cov[0, 0] + cov[k_gamma, k_gamma] + 2.0 * cov[0, k_gamma]))
    se_diff = math.sqrt(float(cov[k_gamma, k_gamma]))
    z_diff = gamma / se_diff
    p_diff = float(two_sided_p(np.array([z_diff]))[0])
    a2 = a1 + gamma
    return SplitHalfResult(
        status="ok",
        reason=None,
        first_start=base.first_start,
        first_end=base.first_end,
        second_start=base.second_start,
        second_end=base.second_end,
        n_first=n1,
        n_second=n - n1,
        hac_lags=fit.lags,
        alpha_first_annual=A * a1,
        alpha_first_ci_low_annual=A * (a1 - Z_975 * se1),
        alpha_first_ci_high_annual=A * (a1 + Z_975 * se1),
        alpha_second_annual=A * a2,
        alpha_second_ci_low_annual=A * (a2 - Z_975 * se2),
        alpha_second_ci_high_annual=A * (a2 + Z_975 * se2),
        difference_annual=A * gamma,
        difference_se_annual=A * se_diff,
        difference_z=z_diff,
        difference_p=p_diff,
    )


# ----------------------------------------------------------------------------- calendar years
@dataclass(frozen=True)
class YearRow:
    """One calendar year of residual sums (R5.4)."""

    year: int
    n: int
    partial: bool
    in_sample_sum: float
    in_sample_noise_sd: float
    n_point_in_time: int
    point_in_time_partial: bool
    point_in_time_sum: float | None
    point_in_time_noise_sd: float | None


def calendar_years(
    dates: Sequence[date], u: FloatArray, u_tilde: FloatArray | None
) -> tuple[YearRow, ...]:
    """Within-year sums of ``u`` and ``u_tilde`` (arithmetic, not compounded) with noise sds (R5.4).

    ``u_tilde`` is NaN on the warm-up rows, or ``None`` when no point-in-time series exists (then
    every point-in-time column is empty).
    """
    uv = np.asarray(u, dtype=np.float64)
    sd_u = float(np.std(uv, ddof=1))
    pit_live = None if u_tilde is None else ~np.isnan(np.asarray(u_tilde, dtype=np.float64))
    sd_pit: float | None = None
    if u_tilde is not None and pit_live is not None and int(pit_live.sum()) > 1:
        sd_pit = float(np.std(np.asarray(u_tilde, dtype=np.float64)[pit_live], ddof=1))
    years = np.array([d.year for d in dates])
    rows: list[YearRow] = []
    for year in sorted({int(v) for v in years}):
        mask = years == year
        n_y = int(mask.sum())
        n_pit = 0 if pit_live is None else int(np.count_nonzero(mask & pit_live))
        pit_sum: float | None = None
        pit_noise: float | None = None
        if u_tilde is not None and pit_live is not None and n_pit > 0:
            pit_sum = float(np.asarray(u_tilde, dtype=np.float64)[mask & pit_live].sum())
            pit_noise = None if sd_pit is None else sd_pit * math.sqrt(n_pit)
        rows.append(
            YearRow(
                year=year,
                n=n_y,
                partial=n_y < PARTIAL_YEAR_ROWS,
                in_sample_sum=float(uv[mask].sum()),
                in_sample_noise_sd=sd_u * math.sqrt(n_y),
                n_point_in_time=n_pit,
                point_in_time_partial=n_pit < PARTIAL_YEAR_ROWS,
                point_in_time_sum=pit_sum,
                point_in_time_noise_sd=pit_noise,
            )
        )
    return tuple(rows)
