"""Adversarial designs near the thresholds of the fast rolling path.

``rolling_ols_hac`` solves windows with a clearly healthy design from cumulative-sum Gram
matrices and sends every other window through the per-window QR path (``_FAST_MIN_*`` in
``analytics/rolling.py``). The equivalence tests use friendly data; these cases sit next to the
limits: factor pairs at correlation 0.99, 0.999 and 0.9999, factor means large against their
spread, one huge outlier, and factors of tiny or huge scale. Each case is held to

- the previous per-window QR implementation (``reference.rolling_ols_hac_previous``) on every
  window, and
- the statsmodels HAC fit (``reference.hac_fit``, methodology M0.5) on spot windows,

and its routing is observed: the number of windows that reach the QR path is read by wrapping
``_exact_windows`` (a recording wrapper that calls the original, so the behaviour is unchanged).
A case that must fall back is asserted to fall back for every window; a case that must stay
fast is asserted to leave (almost) none to QR. If a guard threshold were loosened, the fast path
would take the first kind of case and its error would exceed the bounds below.

Errors are scaled so that badly scaled factors are judged fairly: a beta error is divided by the
reference standard error of that coefficient ("standard errors of drift"), a standard-error
error is relative. Bounds are about ten times the largest error measured on the committed
seeds (numpy 2.5.5, statsmodels 0.15.0, Windows); each test states its measurement.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pytest
from numpy.typing import NDArray

from factordesk.analytics import rolling
from factordesk.analytics.regression import hac_lags
from factordesk.tests.fixtures.dgp import BETA, MU, SD, SIGMA_F, rng_for
from factordesk.tests.fixtures.reference import hac_fit, rolling_ols_hac_previous

FloatArray = NDArray[np.float64]
N = 1500
WINDOWS = (126, 252)


@dataclass(frozen=True)
class Design:
    y: FloatArray
    f: FloatArray


@dataclass(frozen=True)
class Outcome:
    n_stamps: int
    n_qr: int
    """Windows that reached the per-window QR path."""
    beta_vs_qr: float
    """Largest beta error against the previous QR implementation, in reference standard errors."""
    se_vs_qr: float
    """Largest relative standard-error error against the QR implementation."""
    beta_vs_sm: float
    se_vs_sm: float


def _base(seed: int) -> tuple[FloatArray, FloatArray]:
    """Five DGP-A factors and idiosyncratic noise, before ``y`` is built."""
    rng = rng_for(0, seed)
    f = rng.multivariate_normal(MU, SIGMA_F, size=N)
    return f, rng.normal(0.0, 0.012, size=N)


def _design(f: FloatArray, e: FloatArray, beta: FloatArray = BETA) -> Design:
    return Design(y=f @ beta + 0.0002 + e, f=f)


def _correlated(rho: float, seed: int) -> Design:
    """HML (column 2) and CMA (column 4) at population correlation ``rho``."""
    f, e = _base(seed)
    z = np.random.default_rng(seed + 1000).standard_normal(N)
    s = (f[:, 2] - f[:, 2].mean()) / f[:, 2].std()
    f[:, 4] = MU[4] + SD[4] * (rho * s + np.sqrt(1.0 - rho**2) * z)
    return _design(f, e)


def _large_means(n_sd: float, seed: int) -> Design:
    """Every factor's mean is ``n_sd`` of its own standard deviations (French data: 0.03)."""
    f, e = _base(seed)
    f = (f - f.mean(axis=0)) + n_sd * f.std(axis=0)
    return _design(f, e)


def _outlier(where: str, seed: int) -> Design:
    """One huge row: a +1,000% return (``y``) or a +500-standard-deviation market day."""
    f, e = _base(seed)
    d = _design(f, e)
    y, f = d.y.copy(), d.f.copy()
    if where == "y":
        y[400] += 10.0
    else:
        f[400, 0] += 5.0
    return Design(y=y, f=f)


def _scaled(scales: tuple[float, ...], seed: int) -> Design:
    """Factor columns multiplied by ``scales``; ``y`` is built from the unscaled factors."""
    f, e = _base(seed)
    d = _design(f, e)
    return Design(y=d.y, f=d.f * np.asarray(scales))


def _measure(
    design: Design, window: int, monkeypatch: pytest.MonkeyPatch, n_spot: int = 7
) -> Outcome:
    """Run the fast implementation with routing observed and compare with both oracles."""
    routed = {"qr": 0}
    original = rolling._exact_windows  # pyright: ignore[reportPrivateUsage]

    def recording(
        x_win: FloatArray, y_win: FloatArray, w: int, lags: int
    ) -> tuple[NDArray[np.bool_], FloatArray, FloatArray, FloatArray]:
        routed["qr"] += int(x_win.shape[0])
        return original(x_win, y_win, w, lags)

    monkeypatch.setattr(rolling, "_exact_windows", recording)
    params, bse, _ = rolling.rolling_ols_hac(design.y, design.f, window)
    monkeypatch.undo()
    prev_params, prev_bse, _ = rolling_ols_hac_previous(design.y, design.f, window)

    assert np.array_equal(np.isnan(params), np.isnan(prev_params)), "NaN positions differ"
    keep = ~np.isnan(prev_params[:, 0])
    n_stamps = int(keep.sum())
    beta_vs_qr = float(np.max(np.abs(params[keep] - prev_params[keep]) / prev_bse[keep]))
    se_vs_qr = float(np.max(np.abs(bse[keep] - prev_bse[keep]) / prev_bse[keep]))

    beta_vs_sm = se_vs_sm = 0.0
    rows = np.unique(np.linspace(window - 1, N - 1, n_spot).astype(int))
    for t in rows:
        ref = hac_fit(
            design.y[t - window + 1 : t + 1], design.f[t - window + 1 : t + 1], hac_lags(window)
        )
        ref_se = np.sqrt(np.diag(ref.cov))
        beta_vs_sm = max(beta_vs_sm, float(np.max(np.abs(params[t] - ref.params) / ref_se)))
        se_vs_sm = max(se_vs_sm, float(np.max(np.abs(bse[t] - ref_se) / ref_se)))
    return Outcome(n_stamps, routed["qr"], beta_vs_qr, se_vs_qr, beta_vs_sm, se_vs_sm)


def _check(
    out: Outcome, *, beta: float, se: float, sm_beta: float, sm_se: float, label: str
) -> None:
    assert out.beta_vs_qr <= beta, f"{label}: beta drift {out.beta_vs_qr:.2e} SE vs QR"
    assert out.se_vs_qr <= se, f"{label}: se drift {out.se_vs_qr:.2e} vs QR"
    assert out.beta_vs_sm <= sm_beta, f"{label}: beta drift {out.beta_vs_sm:.2e} SE vs statsmodels"
    assert out.se_vs_sm <= sm_se, f"{label}: se drift {out.se_vs_sm:.2e} vs statsmodels"


@pytest.mark.parametrize("window", WINDOWS)
@pytest.mark.parametrize("rho", [0.999, 0.9999])
def test_highly_correlated_pair_falls_back_to_qr(
    rho: float, window: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Correlation 0.999 and 0.9999: the unexplained share is 2e-3 and 2e-4, far below 1e-2.

    Every window must go to QR (the share limit 1e-2 corresponds to correlation about 0.995),
    where the result is the previous implementation's (the same code path). Measured, in
    reference standard errors: beta 0 against QR and at most 4.4e-12 against statsmodels; se at
    most 9.9e-12 relative against QR and 5.4e-12 against statsmodels. Bounds: 1e-10.
    """
    out = _measure(_correlated(rho, seed=31), window, monkeypatch)
    assert out.n_qr == out.n_stamps
    _check(out, beta=1e-10, se=1e-10, sm_beta=1e-10, sm_se=1e-10, label=f"rho {rho}")


@pytest.mark.parametrize("window", WINDOWS)
def test_correlation_099_stays_fast_and_accurate(
    window: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Correlation 0.99 (unexplained share 2e-2, twice the limit): the fast path, accurately.

    Measured (all windows, seed 32): no window reaches QR; drift against QR at most 3.2e-12
    reference standard errors on betas and 2.2e-12 relative on standard errors; against
    statsmodels 2.1e-12 and 1.7e-12. Bounds: 1e-10. Window sampling noise could push a few
    windows under the limit on another seed, so at most 5% may reach QR.
    """
    out = _measure(_correlated(0.99, seed=32), window, monkeypatch)
    assert out.n_qr <= 0.05 * out.n_stamps, "the fast path should take (almost) every window"
    _check(out, beta=1e-10, se=1e-10, sm_beta=1e-10, sm_se=1e-10, label="rho 0.99")


@pytest.mark.parametrize("window", WINDOWS)
def test_means_large_against_spread(window: int, monkeypatch: pytest.MonkeyPatch) -> None:
    """Means of 5 and 8 standard deviations stay fast; 30 (variance 1e-3 of mean square) must not.

    Fast limit: within-window variance at least 1e-2 of the mean square, that is a mean of
    about 10 standard deviations (French data: 0.03). The earlier limit, 1e-3, admitted 30.
    Measured, in reference standard errors: at 5 sd beta drift 1.4e-11 (QR) and 7.3e-12
    (statsmodels); at 8 sd, 4.1e-11 and 2.4e-11, se 3.6e-12 and 2.8e-12 relative; at 30 sd (QR
    path) beta 0 and 4.3e-14, se 7e-12 and 2.3e-12. Bounds: 4e-10 on betas of the fast cases,
    1e-10 elsewhere.
    """
    for n_sd in (5.0, 8.0):
        fast = _measure(_large_means(n_sd, seed=33), window, monkeypatch)
        assert fast.n_qr == 0
        _check(fast, beta=4e-10, se=1e-10, sm_beta=4e-10, sm_se=1e-10, label=f"means {n_sd} sd")
    slow = _measure(_large_means(30.0, seed=33), window, monkeypatch)
    assert slow.n_qr == slow.n_stamps
    _check(slow, beta=1e-10, se=1e-10, sm_beta=1e-10, sm_se=1e-10, label="means 30 sd")


@pytest.mark.parametrize("window", WINDOWS)
@pytest.mark.parametrize("where", ["y", "factor"])
def test_one_huge_outlier(where: str, window: int, monkeypatch: pytest.MonkeyPatch) -> None:
    """One row 1,000% (y) or 500 standard deviations (market factor) at row 400.

    The outlier dominates the running sums of squares, so the windows after it that no longer
    contain it have a tiny share of the running total and must go to QR; windows containing it
    are legitimate and may stay fast. Measured: 848 to 974 of the 1,249 to 1,375 windows reach QR
    for the outlier in ``y`` (every window after row 400 + W) and 256 to 974 for the factor
    outlier; drift against QR at most 2.5e-11 reference standard errors on betas and 1.2e-12
    relative on standard errors; against statsmodels 2.3e-11 and 1.1e-12. Bounds: 3e-10 on betas,
    1e-10 on standard errors.
    """
    out = _measure(_outlier(where, seed=34), window, monkeypatch)
    assert out.n_qr > 0, "windows after the outlier must be routed to QR"
    _check(out, beta=3e-10, se=1e-10, sm_beta=3e-10, sm_se=1e-10, label=f"outlier in {where}")


@pytest.mark.parametrize("window", WINDOWS)
@pytest.mark.parametrize(
    "scales", [(1.0, 1e-6, 1.0, 1.0, 1.0), (1e3, 1.0, 1e-4, 1.0, 1e4), (1e-8,) * 5]
)
def test_tiny_and_huge_factor_scales(
    scales: tuple[float, ...], window: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Factors of tiny (1e-8) or huge (1e4) scale: each window is standardised by its own spread.

    The M3.1 constant test is relative to the largest value, so these are not constant and the
    scale-free guard keeps them on the fast path. Betas reach 1e8 times the unscaled values and
    are judged in standard errors. Measured: against QR at most 3.7e-13 standard errors on betas
    and 6.3e-14 relative on standard errors; against statsmodels at most 1.2e-9 and 2.0e-10
    (statsmodels loses digits on the 1e-6 spread itself: the QR path agrees to 1e-13). Bounds:
    1e-11 and 1e-12 against QR, 1e-8 and 2e-9 against statsmodels.
    """
    out = _measure(_scaled(scales, seed=35), window, monkeypatch)
    assert out.n_qr == 0
    _check(out, beta=1e-11, se=1e-12, sm_beta=1e-8, sm_se=2e-9, label=f"scales {scales}")
