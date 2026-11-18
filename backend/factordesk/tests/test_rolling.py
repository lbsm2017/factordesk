"""Rolling and average beta tests (test-oracle T48-T52, T94; methodology M0.3, M4, M5)."""

from __future__ import annotations

import dataclasses
import warnings

import numpy as np
import pandas as pd
import pytest
from numpy.typing import NDArray

from factordesk.analytics.rolling import (
    average_beta,
    ex_ante_betas,
    rolling_betas,
    rolling_ols_hac,
)
from factordesk.analytics.sample import FACTOR_CODES, AnalysisSample, build_sample
from factordesk.tests.fixtures.dgp import BETA, dgp_a, rng_for
from factordesk.tests.fixtures.reference import RefFit, hac_fit, rolling_params

SWEEP = [None, *[pytest.param(s, marks=pytest.mark.slow, id=f"seed{s}") for s in range(1, 51)]]


def _sample(test_number: int, seed: int | None = None, **kwargs: object) -> AnalysisSample:
    d = dgp_a(rng_for(test_number, seed), **kwargs)  # type: ignore[arg-type]
    return build_sample(d.history, d.factors)


def _ols_window(s: AnalysisSample, first: int, last: int, lags: int) -> RefFit:
    """Reference HAC fit on 0-based rows ``first..last`` inclusive."""
    y = s.xret.to_numpy()[first : last + 1]
    return hac_fit(y, s.factors.to_numpy()[first : last + 1], lags)


@pytest.mark.parametrize("window", [126, 252])
def test_t48_exact_window_length(window: int) -> None:
    s = _sample(48)
    rb = rolling_betas(s, window)
    n = s.n
    assert rb.n_stamps == n - window + 1
    assert rb.n_stamps == (2269 if window == 252 else 2395)
    betas = rb.betas.to_numpy()
    assert np.isnan(betas[: window - 1]).all()
    assert np.isfinite(betas[window - 1 :]).all()
    assert rb.stamps[0] == s.xret.index[window - 1]  # first stamp is row W (1-based)

    ref_params = rolling_params(s.xret.to_numpy(), s.factors.to_numpy(), window)
    np.testing.assert_allclose(betas[window - 1 :], ref_params[window - 1 :, 1:], rtol=1e-10)
    assert np.isnan(ref_params[: window - 1]).all()

    for t in (window - 1, 700, 1500, n - 1):
        exact = _ols_window(s, t - window + 1, t, rb.lags)
        np.testing.assert_allclose(betas[t], exact.params[1:], rtol=1e-10)
        assert rb.alpha.iloc[t] == pytest.approx(float(exact.params[0]), rel=1e-10)
        if t >= window:
            longer = _ols_window(s, t - window, t, rb.lags)
            assert np.max(np.abs(betas[t] - longer.params[1:])) > 1e-6


@pytest.mark.parametrize("window", [126, 252])
def test_t94_every_window_has_exactly_w_rows(window: int) -> None:
    s = _sample(94, n=900)
    rb = rolling_betas(s, window)
    pos = {ts: i for i, ts in enumerate(s.xret.index)}
    stamps = rb.stamps
    starts = rb.window_start.loc[stamps]
    lengths = [pos[t] - pos[pd.Timestamp(st)] + 1 for t, st in zip(stamps, starts, strict=True)]
    assert set(lengths) == {window}
    assert rb.window_start.iloc[: window - 1].isna().all()


@pytest.mark.parametrize("seed", SWEEP)
def test_t49_structural_break(seed: int | None) -> None:
    beta = np.tile(BETA, (2520, 1))
    beta[:1260, 0] = 0.5
    beta[1260:, 0] = 1.5
    s = _sample(49, seed, beta=beta)
    rb = rolling_betas(s, 252)
    at_1260 = rb.betas.iloc[1259].to_numpy()
    exact = _ols_window(s, 1008, 1259, 4)
    np.testing.assert_allclose(at_1260, exact.params[1:], rtol=1e-10)
    se_1260 = rb.se.iloc[1259]["mkt_rf"]
    assert abs(at_1260[0] - 0.5) <= 4 * se_1260
    assert abs(rb.betas.iloc[1511]["mkt_rf"] - 1.5) <= 4 * rb.se.iloc[1511]["mkt_rf"]


@pytest.mark.parametrize("window", [126, 252])
def test_t50_vectorised_rolling_hac(window: int) -> None:
    s = _sample(50)
    rb = rolling_betas(s, window)
    rng = rng_for(50)
    stamps = rng.choice(np.arange(window - 1, s.n), size=5, replace=False)
    for t in stamps:
        ref = _ols_window(s, int(t) - window + 1, int(t), 4)
        ours = np.concatenate([[rb.alpha_se.iloc[int(t)]], rb.se.iloc[int(t)].to_numpy()])
        np.testing.assert_allclose(ours, ref.bse, rtol=1e-8)


def test_t51_ex_ante_beta() -> None:
    s = _sample(51, n=800)
    rb = rolling_betas(s, 252)
    tilde = ex_ante_betas(rb)
    np.testing.assert_array_equal(tilde.to_numpy()[1:], rb.betas.to_numpy()[:-1])
    assert np.isnan(tilde.to_numpy()[:252]).all()

    t = 600
    xret = s.xret.copy()
    fac = s.factors.copy()
    xret.iloc[t] *= 10
    fac.iloc[t] *= 10
    bumped = dataclasses.replace(s, xret=xret, factors=fac)
    tilde2 = ex_ante_betas(rolling_betas(bumped, 252))
    np.testing.assert_array_equal(tilde2.iloc[t].to_numpy(), tilde.iloc[t].to_numpy())
    assert not np.array_equal(tilde2.iloc[t + 1].to_numpy(), tilde.iloc[t + 1].to_numpy())


def test_t52_average_beta_statistics() -> None:
    s = _sample(52)
    rb = rolling_betas(s, 252)
    stats = average_beta(rb)
    assert [a.code for a in stats] == list(FACTOR_CODES)
    for a in stats:
        v: NDArray[np.float64] = np.asarray(rb.betas[a.code], dtype=np.float64)[251:]
        assert a.n_stamps == s.n - 252 + 1 == len(v)
        expected: dict[str, float] = {
            "mean": float(np.mean(v)),
            "sd": float(np.std(v, ddof=1)),
            "p10": float(np.percentile(v, 10)),
            "p90": float(np.percentile(v, 90)),
            "min": float(np.min(v)),
            "max": float(np.max(v)),
            "share_positive": np.count_nonzero(v > 0) / v.size,
        }
        for key, value in expected.items():
            assert getattr(a, key) == pytest.approx(value, rel=1e-12, abs=1e-15)


def test_rolling_short_sample_is_all_warmup() -> None:
    s = _sample(52, n=600)
    rb = rolling_betas(
        dataclasses.replace(s, xret=s.xret.iloc[:100], factors=s.factors.iloc[:100]), 126
    )
    assert rb.n_stamps == 0
    assert rb.betas.isna().all().all()


def test_t126_singular_windows_get_no_estimate_and_no_warning() -> None:
    """A factor that is zero for 130 rows makes exactly the 126-row windows inside it singular."""
    d = dgp_a(rng_for(126), n=800)
    f = d.f.copy()
    f[300:430, 1] = 0.0
    y = d.ret - d.rf
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        params, bse, _ = rolling_ols_hac(y, f, 126)
    bad = np.flatnonzero(np.isnan(params[125:, 0])) + 125
    assert bad.tolist() == [425, 426, 427, 428, 429]
    assert np.isnan(bse[bad]).all() and np.isfinite(params[430:]).all()
    # Windows next to the stretch are estimated exactly as the reference call.
    ref = hac_fit(y[305:431], f[305:431], 4)
    np.testing.assert_allclose(params[430], ref.params, rtol=1e-9)


def test_rolling_constant_y_window_has_nan_r2_without_warning() -> None:
    d = dgp_a(rng_for(126), n=400)
    y = d.ret - d.rf
    y[100:240] = 0.0001
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        _, _, r2 = rolling_ols_hac(y, d.f, 126)
    assert np.isnan(r2[239]) and np.isfinite(r2[260])
