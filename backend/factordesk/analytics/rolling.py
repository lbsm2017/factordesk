"""Trailing-window betas with HAC standard errors, and the average beta (methodology M4, M5).

A window of length ``W`` stamped at row ``t`` (1-based) contains exactly rows ``t-W+1..t`` of
the analysis sample, including row ``t`` (M0.3). The first stamp is row ``W``; the first
``W - 1`` rows carry NaN (warm-up). statsmodels' ``RollingOLS`` has no HAC option, so the
estimates and the Newey-West covariance of every window are computed here in batches with the
same formula as ``regression.ols_hac`` (lags ``L(W)``).

Pure: no I/O, no clock. Inputs are not mutated.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from numpy.lib.stride_tricks import sliding_window_view
from numpy.typing import NDArray

from factordesk.analytics.regression import (
    MIN_UNEXPLAINED_SHARE,
    ZERO_SD_RELATIVE,
    bartlett_weights,
    hac_lags,
    unexplained_shares,
    with_intercept,
)
from factordesk.analytics.sample import DISPLAY_NAMES, FACTOR_CODES, AnalysisSample

FloatArray = NDArray[np.float64]

WINDOWS: tuple[int, ...] = (126, 252)
"""Windows always computed and overlaid (M4)."""
PRIMARY_WINDOW = 252
"""Default ``beta_window`` W_p (M15)."""
_CHUNK = 512
"""Stamps per batch; bounds memory at about chunk x W x 6 floats per array."""


@dataclass(frozen=True)
class RollingBetas:
    """Per-stamp estimates of one window length on the analysis sample.

    All frames/series share the sample's ``date`` index; rows before the first stamp are NaN
    (``window_start`` is NaT there). Columns of ``betas`` and ``se`` are ``FACTOR_CODES``.
    """

    window: int
    lags: int
    alpha: pd.Series
    alpha_se: pd.Series
    betas: pd.DataFrame
    se: pd.DataFrame
    r2: pd.Series
    window_start: pd.Series

    @property
    def n_stamps(self) -> int:
        return int(self.betas.iloc[:, 0].notna().sum())

    @property
    def stamps(self) -> pd.DatetimeIndex:
        """Dates that carry an estimate (the warm-up rows are dropped)."""
        mask = self.betas.iloc[:, 0].notna().to_numpy()
        return pd.DatetimeIndex(self.betas.index[mask])


def rolling_ols_hac(
    y: FloatArray, factors: FloatArray, window: int
) -> tuple[FloatArray, FloatArray, FloatArray]:
    """Batched trailing-window OLS with Newey-West HAC (lags ``L(window)``).

    Returns ``(params, bse, r2)`` with shapes ``(n, k)``, ``(n, k)``, ``(n,)``; row ``i``
    (0-based) is the window of rows ``i-W+1..i``; rows ``i < W-1`` are NaN. A window whose
    factor matrix fails the design guard of M3.1 (a factor constant within the window, or a
    linear combination of the others) gets NaN instead of an estimate; the caller reports it.
    ``r2`` is NaN for a window whose ``y`` is constant.
    """
    yv = np.asarray(y, dtype=np.float64)
    x = with_intercept(factors)
    n, k = x.shape
    params = np.full((n, k), np.nan)
    bse = np.full((n, k), np.nan)
    r2 = np.full(n, np.nan)
    if window <= k:
        raise ValueError(f"window {window} must exceed the number of parameters {k}")
    if n < window:
        return params, bse, r2
    if not (np.isfinite(yv).all() and np.isfinite(x).all()):
        raise ValueError("inputs must be finite; excluded rows are removed upstream")

    lags = hac_lags(window)
    weights = bartlett_weights(lags)
    eye = np.eye(k)
    # Views of shape (n - W + 1, W, k) and (n - W + 1, W): window j holds rows j..j+W-1.
    x_win = sliding_window_view(x, window, axis=0).transpose(0, 2, 1)
    y_win = sliding_window_view(yv, window)
    n_stamps = n - window + 1
    for c0 in range(0, n_stamps, _CHUNK):
        c1 = min(c0 + _CHUNK, n_stamps)
        constant, share = unexplained_shares(x_win[c0:c1])
        ok = ~(constant.any(axis=1) | (share < MIN_UNEXPLAINED_SHARE).any(axis=1))
        if not ok.any():
            continue
        xc = np.ascontiguousarray(x_win[c0:c1][ok])
        yc = np.ascontiguousarray(y_win[c0:c1][ok])
        q, r = np.linalg.qr(xc)
        r_inv = np.linalg.solve(r, np.broadcast_to(eye, r.shape))
        theta = np.einsum("cij,cj->ci", r_inv, np.einsum("cwi,cw->ci", q, yc))
        resid = yc - np.einsum("cwi,ci->cw", xc, theta)
        scores = xc * resid[:, :, None]
        meat = np.einsum("cwi,cwj->cij", scores, scores)
        for lag in range(1, lags + 1):
            gamma = np.einsum("cwi,cwj->cij", scores[:, lag:], scores[:, :-lag])
            meat += weights[lag] * (gamma + gamma.transpose(0, 2, 1))
        bread = r_inv @ r_inv.transpose(0, 2, 1)
        cov = bread @ meat @ bread.transpose(0, 2, 1)
        rows = np.arange(c0 + window - 1, c1 + window - 1)[ok]
        params[rows] = theta
        bse[rows] = np.sqrt(np.diagonal(cov, axis1=1, axis2=2))
        centred = yc - yc.mean(axis=1, keepdims=True)
        tss = np.einsum("cw,cw->c", centred, centred)
        ssr = np.einsum("cw,cw->c", resid, resid)
        varies = tss > window * (ZERO_SD_RELATIVE * np.max(np.abs(yc), axis=1)) ** 2
        r2_chunk = np.full(len(tss), np.nan)
        np.divide(ssr, tss, out=r2_chunk, where=varies)
        r2[rows] = np.where(varies, 1.0 - r2_chunk, np.nan)
    return params, bse, r2


def rolling_betas(sample: AnalysisSample, window: int) -> RollingBetas:
    """Trailing ``window``-row betas on the analysis sample (M4)."""
    index = pd.DatetimeIndex(sample.xret.index)
    y = sample.xret.to_numpy(dtype=np.float64)
    f = sample.factors.loc[:, list(FACTOR_CODES)].to_numpy(dtype=np.float64)
    params, bse, r2 = rolling_ols_hac(y, f, window)
    start = pd.Series(pd.NaT, index=index, dtype="datetime64[ns]", name="window_start")
    if len(index) >= window:
        start.iloc[window - 1 :] = index[: len(index) - window + 1]
    cols = list(FACTOR_CODES)
    return RollingBetas(
        window=window,
        lags=hac_lags(window),
        alpha=pd.Series(params[:, 0], index=index, name="alpha"),
        alpha_se=pd.Series(bse[:, 0], index=index, name="alpha_se"),
        betas=pd.DataFrame(params[:, 1:], index=index, columns=cols),
        se=pd.DataFrame(bse[:, 1:], index=index, columns=cols),
        r2=pd.Series(r2, index=index, name="r2"),
        window_start=start,
    )


def ex_ante_betas(rolling: RollingBetas) -> pd.DataFrame:
    """``beta_tilde_t = beta_hat_{t-1}``: the estimate available before day ``t`` (M4).

    A positive positional lag of one row of the sample (never a negative shift).
    """
    return rolling.betas.shift(1)


@dataclass(frozen=True)
class AverageBetaStats:
    """Distribution of one factor's rolling betas over all stamps (M5)."""

    code: str
    name: str
    mean: float
    sd: float
    p10: float
    p90: float
    min: float
    max: float
    share_positive: float
    n_stamps: int


def average_beta(rolling: RollingBetas) -> tuple[AverageBetaStats, ...]:
    """Mean, sd (ddof=1), 10th/90th percentiles (linear), min, max and share > 0 (M5)."""
    out: list[AverageBetaStats] = []
    for code in FACTOR_CODES:
        column = rolling.betas[code].to_numpy(dtype=np.float64)
        values: FloatArray = column[~np.isnan(column)]  # warm-up rows carry no estimate
        if values.size < 2:
            raise ValueError(f"average beta needs at least 2 stamps of window {rolling.window}")
        out.append(
            AverageBetaStats(
                code=code,
                name=DISPLAY_NAMES[code],
                mean=float(np.mean(values)),
                sd=float(np.std(values, ddof=1)),
                p10=float(np.percentile(values, 10, method="linear")),
                p90=float(np.percentile(values, 90, method="linear")),
                min=float(np.min(values)),
                max=float(np.max(values)),
                share_positive=float(np.count_nonzero(values > 0)) / values.size,
                n_stamps=int(values.size),
            )
        )
    return tuple(out)
