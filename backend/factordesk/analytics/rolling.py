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
_CHUNK = 256
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


def _window_r2(yc: FloatArray, resid: FloatArray, window: int) -> FloatArray:
    """``1 - SSR/TSS`` per window row; NaN where ``y`` is constant within the window."""
    centred = yc - yc.mean(axis=1, keepdims=True)
    tss = np.einsum("cw,cw->c", centred, centred)
    ssr = np.einsum("cw,cw->c", resid, resid)
    varies = tss > window * (ZERO_SD_RELATIVE * np.max(np.abs(yc), axis=1)) ** 2
    ratio = np.full(len(tss), np.nan)
    np.divide(ssr, tss, out=ratio, where=varies)
    return np.where(varies, 1.0 - ratio, np.nan)


def _exact_windows(
    x_win: FloatArray, y_win: FloatArray, window: int, lags: int
) -> tuple[NDArray[np.bool_], FloatArray, FloatArray, FloatArray]:
    """Per-window QR fit with the full M3.1 design guard: the unconditionally exact path.

    ``x_win`` is ``(c, W, k)``, ``y_win`` is ``(c, W)`` (views are fine). Returns ``(ok, theta,
    se, r2)`` where ``ok`` marks the windows that pass the guard and the other three describe
    only those windows (in order).
    """
    k = x_win.shape[2]
    constant, share = unexplained_shares(x_win)
    ok = ~(constant.any(axis=1) | (share < MIN_UNEXPLAINED_SHARE).any(axis=1))
    if not ok.any():
        return ok, np.empty((0, k)), np.empty((0, k)), np.empty(0)
    xc = np.ascontiguousarray(x_win[ok])
    yc = np.ascontiguousarray(y_win[ok])
    q, r = np.linalg.qr(xc)
    r_inv = np.linalg.solve(r, np.broadcast_to(np.eye(k), r.shape))
    theta = np.einsum("cij,cj->ci", r_inv, np.einsum("cwi,cw->ci", q, yc))
    resid = yc - np.einsum("cwi,ci->cw", xc, theta)
    meat = _hac_meat_batch(xc * resid[:, :, None], lags)
    bread = r_inv @ r_inv.transpose(0, 2, 1)
    cov = bread @ meat @ bread.transpose(0, 2, 1)
    se = np.sqrt(np.diagonal(cov, axis1=1, axis2=2))
    return ok, theta, se, _window_r2(yc, resid, window)


def _hac_meat_batch(scores: FloatArray, lags: int) -> FloatArray:
    """Newey-West meat of stacked windows, ``scores`` of shape ``(c, W, k)``.

    ``S = sum_t u_t u_t' + sum_l w_l (Gamma_l + Gamma_l')`` with ``Gamma_l = sum_t u_t u_{t-l}'``,
    written as ``Z'Z + Z'T + T'Z`` where ``T_t = sum_{l=1..L, l<=t} w_l u_{t-l}`` (the kernel-
    weighted lagged scores), so that three batched matrix products replace ``L + 1``.
    """
    c, w, k = scores.shape
    zt = scores.transpose(0, 2, 1)
    if lags == 0:
        return zt @ scores
    padded = np.zeros((c, w + lags, k))
    padded[:, lags:] = scores
    # Window t spans padded rows t..t+L-1 = scores rows t-L..t-1 (zeros before the window).
    lagged = sliding_window_view(padded, lags, axis=1)[:, :w] @ bartlett_weights(lags)[:0:-1]
    cross = zt @ lagged
    return zt @ scores + cross + cross.transpose(0, 2, 1)


_FAST_MIN_SHARE = 1e-2
"""A window is estimated on the fast path only when every factor keeps at least this share of
its variance after the constant and earlier factors (10,000 times the M3.1 limit; two factors
with correlation above about 0.995 fall back to QR)."""
_FAST_MIN_CENTRED = 1e-2
"""... only when every factor's within-window variance is at least this fraction of its
within-window mean square (a factor far from zero-mean with little spread would lose digits
in the Gram solve; the M3.1 constant test fires at 1e-24) ..."""
_FAST_MIN_WINDOW_SHARE = 1e-3
"""... and only when each window's centred sum of squares (factors) and sum of squares (``y``)
is at least this fraction of the running sum of squares up to the window end, which bounds
the digits lost to the cumulative-sum difference. Every other window takes the per-window QR
path.

Measured error of the fast path against the per-window QR path (which is itself about 1e-13
relative from exact rational arithmetic): about 1e-12 absolute on betas and standard errors on
real SPY data (about 1e-10 relative from exact at the worst SPY windows); at most 1e-11 on
adversarial designs that these thresholds admit (volatility regimes up to 1,000-fold, factor
means up to 30 standard deviations). With the earlier thresholds (1e-3 and 1e-4, and the
uncentred sum of squares) such designs reached 2e-8 on betas and 1e-9 on standard errors
(independent validation, 2026-11-18). All SPY and synthetic long-series windows still take the
fast path, so tightening cost no speed there."""


def _pivots(gram: FloatArray) -> FloatArray:
    """Squared diagonal of the Cholesky factor of stacked Gram matrices ``(c, k, k)``.

    Equals ``R_jj^2`` of the QR of the design. Non-positive pivots propagate as NaN or
    non-positive values, which the caller treats as "not certified".
    """
    c, k, _ = gram.shape
    lower = np.zeros_like(gram)
    pivots = np.empty((c, k))
    with np.errstate(all="ignore"):
        for j in range(k):
            pivot = gram[:, j, j] - np.einsum("ci,ci->c", lower[:, j, :j], lower[:, j, :j])
            pivots[:, j] = pivot
            root = np.sqrt(pivot)
            lower[:, j, j] = root
            for i in range(j + 1, k):
                dot = np.einsum("ci,ci->c", lower[:, i, :j], lower[:, j, :j])
                lower[:, i, j] = (gram[:, i, j] - dot) / root
    return pivots


def rolling_ols_hac(
    y: FloatArray, factors: FloatArray, window: int
) -> tuple[FloatArray, FloatArray, FloatArray]:
    """Batched trailing-window OLS with Newey-West HAC (lags ``L(window)``).

    Returns ``(params, bse, r2)`` with shapes ``(n, k)``, ``(n, k)``, ``(n,)``; row ``i``
    (0-based) is the window of rows ``i-W+1..i``; rows ``i < W-1`` are NaN. A window whose
    factor matrix fails the design guard of M3.1 (a factor constant within the window, or a
    linear combination of the others) gets NaN instead of an estimate; the caller reports it.
    ``r2`` is NaN for a window whose ``y`` is constant.

    Windows whose design is clearly healthy are solved from window Gram matrices (cumulative
    sums of cross-products, each window standardised by its own factor spreads, with the same
    QR-equivalent guard quantities); every other window, and every window near a guard limit,
    goes through the per-window QR path that decides the guard exactly. No quantity of a window
    uses a row after it.

    Precision: the QR path is exact to about 1e-13 relative. The fast path carries the rounding
    of the cumulative sums, so it is not bit-identical to QR: about 1e-12 absolute (about 1e-10
    relative from exact rational arithmetic, worst windows) on real factor data, and at most
    about 1e-11 on the adversarial designs the thresholds above admit (see ``_FAST_MIN_*``).
    For the same reason a window's value depends, in the last bits, on rows before the
    window: the cumulative sums start at the first row passed in, so a different first row
    moves a window's value by up to about 1e-12 (measured 7.9e-13 on SPY; the previous per-
    window implementation gave exactly 0; 1e-13 on synthetic data, up to 3e-11 on the volatility
    regime design of ``test_rolling_equivalence``). A window never depends on a later row (no
    look-ahead), and the dependence is far below the 6 significant digits the report keeps.
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
    n_stamps = n - window + 1
    # Window Gram matrices X'X and X'y from cumulative sums (row j of a cumulative array is the
    # sum of the first j rows, so a window is a difference of two rows); each cumulative sum
    # at row j holds only rows before j, so a window never sees a later row.
    zero = np.zeros((1, k * k))
    cum_gram = np.concatenate(
        [zero, np.cumsum((x[:, :, None] * x[:, None, :]).reshape(n, -1), axis=0)]
    )
    cum_xy = np.concatenate([zero[:, :k], np.cumsum(x * yv[:, None], axis=0)])
    cum_yy = np.concatenate([[0.0], np.cumsum(yv * yv)])
    diag_at: list[int] = list(range(0, k * k, k + 1))  # diagonal of a flattened Gram

    x_win = sliding_window_view(x, window, axis=0).transpose(0, 2, 1)
    y_win = sliding_window_view(yv, window)

    for c0 in range(0, n_stamps, _CHUNK):
        c1 = min(c0 + _CHUNK, n_stamps)
        end = cum_gram[c0 + window : c1 + window]
        flat = end - cum_gram[c0:c1]
        gram = flat.reshape(-1, k, k)
        sq = flat[:, diag_at][:, 1:]  # window sum of squares of each factor
        css = sq - gram[:, 0, 1:] ** 2 / window  # centred sum of squares of each factor
        yy = cum_yy[c0 + window : c1 + window] - cum_yy[c0:c1]
        with np.errstate(all="ignore"):
            sd = np.sqrt(css / window)
            d = np.concatenate([np.ones((len(sd), 1)), 1.0 / sd], axis=1)  # (c, k) column scale
            gram_s = gram * d[:, :, None] * d[:, None, :]
            pivots = _pivots(gram_s)[:, 1:]
            healthy = (
                (
                    (css > _FAST_MIN_CENTRED * sq)
                    & (pivots > _FAST_MIN_SHARE * window)  # centred sum of squares is W when scaled
                    & (css > _FAST_MIN_WINDOW_SHARE * end[:, diag_at][:, 1:])
                ).all(axis=1)
                & (yy > _FAST_MIN_WINDOW_SHARE * cum_yy[c0 + window : c1 + window])
            )
        fast = healthy
        if fast.any():
            idx = np.flatnonzero(fast)
            dc = d[idx]
            xc = np.ascontiguousarray(x_win[c0:c1][idx])
            yc = np.ascontiguousarray(y_win[c0:c1][idx])
            g_inv = np.linalg.inv(gram_s[idx])
            xy_s = (cum_xy[c0 + window : c1 + window] - cum_xy[c0:c1])[idx] * dc
            theta_s = np.einsum("cij,cj->ci", g_inv, xy_s)
            theta = theta_s * dc
            resid = yc - (xc @ theta[:, :, None])[:, :, 0]
            meat = _hac_meat_batch(xc * resid[:, :, None], lags) * dc[:, :, None] * dc[:, None, :]
            cov = g_inv @ meat @ g_inv
            rows = idx + (c0 + window - 1)
            params[rows] = theta
            bse[rows] = np.sqrt(np.diagonal(cov, axis1=1, axis2=2)) * dc
            r2[rows] = _window_r2(yc, resid, window)
        rest = np.flatnonzero(~fast)
        for s0 in range(0, len(rest), _CHUNK):
            sel = c0 + rest[s0 : s0 + _CHUNK]
            ok, theta, se, r2_sel = _exact_windows(x_win[sel], y_win[sel], window, lags)
            rows = (sel + (window - 1))[ok]
            params[rows] = theta
            bse[rows] = se
            r2[rows] = r2_sel
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
