"""The fast rolling estimator equals the previous per-window QR implementation (same numbers).

``rolling_ols_hac`` solves clearly healthy windows from window Gram matrices and sends every
other window through the per-window QR path. These tests hold it to the previous
implementation (``reference.rolling_ols_hac_previous``) on several seeds, on fat-tailed
volatility-clustered data, on persistent factors, on short windows and on designs that trip the
M3.1 guard, and to statsmodels' HAC fit on spot windows. NaN positions must be identical and
no window may use a later row.
"""

from __future__ import annotations

import numpy as np
import pytest
from numpy.typing import NDArray

from factordesk.analytics.regression import Z_975, hac_lags
from factordesk.analytics.rolling import rolling_ols_hac
from factordesk.tests.fixtures.dgp import dgp_a, dgp_b, dgp_g, rng_for
from factordesk.tests.fixtures.reference import hac_fit, rolling_ols_hac_previous

FloatArray = NDArray[np.float64]
TOL = 1e-9


def _assert_same(y: FloatArray, f: FloatArray, window: int, tol: float = TOL) -> None:
    new = rolling_ols_hac(y, f, window)
    old = rolling_ols_hac_previous(y, f, window)
    for name, a, b in zip(("params", "bse", "r2"), new, old, strict=True):
        assert np.array_equal(np.isnan(a), np.isnan(b)), f"{name}: NaN positions differ"
        keep = ~np.isnan(b)
        if keep.any():
            assert np.max(np.abs(a[keep] - b[keep])) <= tol, f"{name} differs by more than {tol}"
    # Band edges (beta +- z * se) as drawn in the report.
    for sign in (-1.0, 1.0):
        edge_new = new[0][:, 1:] + sign * Z_975 * new[1][:, 1:]
        edge_old = old[0][:, 1:] + sign * Z_975 * old[1][:, 1:]
        keep = ~np.isnan(edge_old)
        assert np.max(np.abs(edge_new[keep] - edge_old[keep])) <= tol


@pytest.mark.parametrize("window", [126, 252])
@pytest.mark.parametrize("seed", [1, 2, 3, 4, 5])
def test_equivalence_static_factor_model(seed: int, window: int) -> None:
    d = dgp_a(rng_for(0, seed), n=1400)
    _assert_same(d.ret - d.rf, d.f, window)


@pytest.mark.parametrize("window", [126, 252])
def test_equivalence_fat_tails_and_volatility_clustering(window: int) -> None:
    d = dgp_g(rng_for(0, 11), n=1400)
    _assert_same(d.ret - d.rf, d.f, window)


@pytest.mark.parametrize("window", [126, 252])
def test_equivalence_persistent_factors_and_errors(window: int) -> None:
    d = dgp_b(rng_for(0, 12), n=1400)
    _assert_same(d.ret - d.rf, d.f, window)


def test_equivalence_long_series_with_drifting_scale() -> None:
    """Market-like: 8,500 rows, volatility regimes, a quiet factor stretch, big outliers."""
    rng = rng_for(0, 13)
    d = dgp_a(rng, n=8500)
    scale = np.where((np.arange(8500) // 700) % 2 == 0, 1.0, 3.0)[:, None]
    f = d.f * scale
    f[2000:2300, 3] *= 1e-3  # near-constant but not constant: stays on the exact path
    y = d.ret - d.rf + 0.05 * (rng.random(8500) < 0.002) * rng.standard_normal(8500)
    for window in (126, 252):
        _assert_same(y, f, window)


@pytest.mark.parametrize("window", [10, 22, 63])
def test_equivalence_short_windows(window: int) -> None:
    d = dgp_a(rng_for(0, 14), n=900)
    _assert_same(d.ret - d.rf, d.f, window)


def test_equivalence_guard_windows_are_identical() -> None:
    """Constant, collinear, near-collinear and constant-y stretches: same NaN map, same values."""
    d = dgp_a(rng_for(0, 15), n=1200)
    f = d.f.copy()
    y = d.ret - d.rf
    f[200:340, 1] = 0.0  # constant factor
    f[500:700, 4] = 2.0 * f[500:700, 2] - 0.5 * f[500:700, 0]  # exact collinearity
    f[800:1000, 4] = f[800:1000, 2] + 3e-4 * f[800:1000, 4]  # near, but beyond the limit
    f[900:1100, 3] = f[900:1100, 1] + 2e-5 * f[900:1100, 3]  # near, inside the limit
    y[1100:1200] = 0.0003  # constant y
    # Near-collinear windows amplify rounding by their condition number (about 1e6 here), in
    # both implementations; at window 1000 the new one is the closer to statsmodels.
    for window in (126, 252):
        _assert_same(y, f, window, tol=1e-8)


def test_equivalence_with_statsmodels_hac_on_spot_windows() -> None:
    d = dgp_a(rng_for(0, 16), n=1000)
    y = d.ret - d.rf
    params, bse, _ = rolling_ols_hac(y, d.f, 252)
    for t in (251, 400, 999):
        ref = hac_fit(y[t - 251 : t + 1], d.f[t - 251 : t + 1], hac_lags(252))
        assert np.max(np.abs(params[t] - ref.params)) <= TOL
        assert np.max(np.abs(bse[t] - np.sqrt(np.diag(ref.cov)))) <= TOL


def test_no_look_ahead_in_fast_path() -> None:
    """Changing any row after ``t`` leaves every estimate up to ``t`` bit-for-bit unchanged."""
    d = dgp_a(rng_for(0, 17), n=900)
    y = d.ret - d.rf
    base = rolling_ols_hac(y, d.f, 126)
    t = 500
    y2, f2 = y.copy(), d.f.copy()
    y2[t + 1 :] += 0.05
    f2[t + 1 :] *= 7.0
    other = rolling_ols_hac(y2, f2, 126)
    for a, b in zip(base, other, strict=True):
        np.testing.assert_array_equal(a[: t + 1], b[: t + 1])
