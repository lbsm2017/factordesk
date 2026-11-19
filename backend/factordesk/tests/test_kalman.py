"""Kalman-filter beta tests (kalman-betas spec KB11, TKB01-TKB22; seeds 20261118 + 600 + NN).

The independent references live here and nowhere else: a naive matrix Kalman recursion written
for the test (true-unit ``R``, textbook formulas), and statsmodels ``MLEModel`` and
``RecursiveLS`` (spec KB8.2). The simulation tests (marker ``slow``) use 100 replications by
default instead of the spec's 200 to bound the run time; set ``FACTORDESK_KB_REPS=200`` to run
them as the spec writes them. Every threshold is the spec's.
"""

from __future__ import annotations

import ast
import math
import os
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

import numpy as np
import pytest
import statsmodels.api as sm  # pyright: ignore[reportMissingTypeStubs]
from numpy.lib.stride_tricks import sliding_window_view
from numpy.typing import NDArray
from statsmodels.tsa.statespace.mlemodel import MLEModel  # pyright: ignore[reportMissingTypeStubs]

from factordesk.analytics import kalman as kf
from factordesk.analytics.kalman import (
    LAMBDA_GRID,
    FilterPath,
    KalmanResult,
    filter_path,
    kalman_betas,
    refine_lambda,
    t_weight,
    vintage_rows,
)
from factordesk.analytics.regression import Z_975
from factordesk.tests.fixtures.dgp import MU, SD, SIGMA_F, dgp_a, rng_for

FloatArray = NDArray[np.float64]
B = kf.BURN_IN_ROWS
KB_REPS = int(os.environ.get("FACTORDESK_KB_REPS", "100"))
"""Replications of the slow simulation tests (the spec writes 200)."""
_sm: Any = sm
_MLEModel: Any = MLEModel


# ------------------------------------------------------------------------------------ helpers
def _xy(test_number: int, n: int, *, seed: int | None = None) -> tuple[FloatArray, FloatArray]:
    """DGP-A excess returns and factors."""
    d = dgp_a(rng_for(test_number, seed), n=n)
    return d.ret - d.rf, d.f


def _scale_m(f: FloatArray, rows: int) -> FloatArray:
    return np.linalg.inv(np.cov(f[:rows], rowvar=False, ddof=1))


@dataclass(frozen=True)
class RefRun:
    """Textbook Kalman recursion (reference)."""

    states: FloatArray
    cov: FloatArray
    innov: FloatArray
    var: FloatArray


def reference_filter(
    y: FloatArray, f: FloatArray, lam: float, r: float, m_inv: FloatArray, burn_in: int = B
) -> RefRun:
    """Naive matrix filter in true units: ``R = r``, ``Q = blockdiag(0, lam r M)``."""
    n = len(y)
    x = np.column_stack([np.ones(n), f])
    gram = x[:burn_in].T @ x[:burn_in]
    a = np.linalg.solve(gram, x[:burn_in].T @ y[:burn_in])
    p = r * np.linalg.inv(gram)
    q = np.zeros((6, 6))
    q[1:, 1:] = lam * r * m_inv
    states = np.full((n, 6), np.nan)
    cov = np.full((n, 6, 6), np.nan)
    innov = np.full(n, np.nan)
    var = np.full(n, np.nan)
    states[burn_in - 1], cov[burn_in - 1] = a, p
    for t in range(burn_in, n):
        p = p + q
        xt = x[t]
        v = y[t] - xt @ a
        ft = xt @ p @ xt + r
        gain = p @ xt / ft
        a = a + gain * v
        p = p - np.outer(gain, xt @ p)
        states[t], cov[t], innov[t], var[t] = a, p, v, ft
    return RefRun(states, cov, innov, var)


def reference_vintage_loglik(
    y: FloatArray, f: FloatArray, lam: float, m_inv: FloatArray, rows: int
) -> float:
    """Concentrated log-likelihood of one (vintage, lam) by the naive recursion (R = 1)."""
    run = reference_filter(y[:rows], f[:rows], lam, 1.0, m_inv)
    v, ft = run.innov[B:], run.var[B:]
    n_rows = rows - B
    r_hat = float(np.mean(v**2 / ft))
    return -0.5 * n_rows * (math.log(2 * math.pi) + math.log(r_hat) + 1.0) - 0.5 * float(
        np.sum(np.log(ft))
    )


def sm_filter(
    y: FloatArray, f: FloatArray, lam: float, r_hat: float, m_inv: FloatArray
) -> tuple[FloatArray, FloatArray, float]:
    """statsmodels ``MLEModel`` with exact diffuse start (KB11, TKB02)."""
    n = len(y)
    design = np.column_stack([np.ones(n), f])
    state_cov = np.zeros((6, 6, n))
    for t in range(B - 1, n):
        state_cov[1:, 1:, t] = lam * r_hat * m_inv

    class Model(_MLEModel):  # pyright: ignore[reportUntypedBaseClass]
        def __init__(self) -> None:
            super().__init__(  # pyright: ignore[reportUnknownMemberType]
                y, k_states=6, initialization="diffuse"
            )
            self["design"] = design.T[None]
            self["transition"] = np.eye(6)
            self["selection"] = np.eye(6)
            self["obs_cov"] = np.array([[r_hat]])
            self["state_cov"] = state_cov

    res: Any = Model().filter([])
    states = np.asarray(res.filtered_state, dtype=np.float64).T
    cov = np.asarray(res.filtered_state_cov, dtype=np.float64).transpose(2, 0, 1)
    return states, cov, float(np.sum(np.asarray(res.llf_obs)[B:]))


def rolling_ols(y: FloatArray, f: FloatArray, window: int) -> FloatArray:
    """Betas of the trailing ``window`` rows, stamped at the last row; NaN before it."""
    x = np.column_stack([np.ones(len(y)), f])
    xw = sliding_window_view(x, window, axis=0).transpose(0, 2, 1)
    yw = sliding_window_view(y, window)
    gram: FloatArray = np.einsum("cwi,cwj->cij", xw, xw)
    cross: FloatArray = np.einsum("cwi,cw->ci", xw, yw)
    theta = np.asarray(np.linalg.solve(gram, cross[:, :, None]), dtype=np.float64)[:, :, 0]
    out = np.full((len(y), 5), np.nan)
    out[window - 1 :] = theta[:, 1:]
    return out


def expanding_ols(y: FloatArray, f: FloatArray) -> FloatArray:
    x = np.column_stack([np.ones(len(y)), f])
    gram = np.cumsum(np.einsum("ti,tj->tij", x, x), axis=0)
    cross = np.cumsum(x * y[:, None], axis=0)
    out = np.full((len(y), 5), np.nan)
    for t in range(B, len(y)):
        out[t] = np.linalg.solve(gram[t], cross[t])[1:]
    return out


# ============================================================ identities and references
def test_tkb01_lambda_zero_is_expanding_ols() -> None:
    y, f = _xy(601, 800)
    path = filter_path(y, f, 0.0)
    x = np.column_stack([np.ones(len(y)), f])
    worst = 0.0
    for t in range(B - 1, len(y), 7):
        ols = np.linalg.lstsq(x[: t + 1], y[: t + 1], rcond=None)[0]
        worst = max(worst, float(np.abs(path.states[t] - ols).max()))
    assert worst < 1e-10
    rls: Any = _sm.RecursiveLS(y, x).fit()
    ref = np.asarray(rls.recursive_coefficients.filtered, dtype=np.float64).T
    assert np.abs(path.states[B - 1 :] - ref[B - 1 :]).max() < 1e-10


@pytest.mark.parametrize("lam", [1e-6, 1e-4, 1e-2])
def test_tkb02_statsmodels_reference(lam: float) -> None:
    y, f = _xy(602, 1000)
    m_inv = _scale_m(f, 1000)
    path = filter_path(y, f, lam)
    ref_states, ref_cov, ref_llf = sm_filter(y, f, lam, path.r_hat, m_inv)
    assert np.abs(path.states[B - 1 :] - ref_states[B - 1 :]).max() < 1e-10
    ours = path.r_hat * path.cov_scale[B - 1 :]
    assert np.abs(ours - ref_cov[B - 1 :]).max() / np.abs(ref_cov[B - 1 :]).max() < 1e-8
    assert path.loglik == pytest.approx(ref_llf, rel=1e-8)


def test_tkb02b_naive_matrix_recursion_matches_filter_path() -> None:
    y, f = _xy(602, 900, seed=5)
    m_inv = _scale_m(f, 900)
    path = filter_path(y, f, 3e-5)
    ref = reference_filter(y, f, 3e-5, 1.0, m_inv)
    assert np.abs(path.states[B - 1 :] - ref.states[B - 1 :]).max() < 1e-11
    assert np.abs(path.cov_scale[B - 1 :] - ref.cov[B - 1 :]).max() < 1e-9
    assert np.abs(path.innovations[B:] - ref.innov[B:]).max() < 1e-12


def test_tkb03_burn_in_is_ols_on_first_21_rows() -> None:
    y, f = _xy(603, 600)
    x = np.column_stack([np.ones(600), f])
    path = filter_path(y, f, 1e-4)
    ols = np.linalg.lstsq(x[:B], y[:B], rcond=None)[0]
    assert np.abs(path.states[B - 1] - ols).max() < 1e-12
    assert np.abs(path.cov_scale[B - 1] - np.linalg.inv(x[:B].T @ x[:B])).max() < 1e-12
    assert np.isnan(path.states[: B - 1]).all()


def test_tkb04_concentration_maximises_the_full_likelihood() -> None:
    y, f = _xy(604, 700)
    path = filter_path(y, f, 2e-5)
    v, ft = path.innovations[B:], path.variances[B:]
    rows = len(v)

    def full(r: float) -> float:
        return float(
            -0.5 * rows * math.log(2 * math.pi * r)
            - 0.5 * np.sum(np.log(ft))
            - 0.5 * np.sum(v**2 / ft) / r
        )

    assert full(path.r_hat * 1.01) < full(path.r_hat)
    assert full(path.r_hat * 0.99) < full(path.r_hat)
    assert full(path.r_hat) == pytest.approx(path.loglik, rel=1e-10)


def test_tkb05_scale_form_equals_true_unit_filter() -> None:
    y, f = _xy(605, 700)
    m_inv = _scale_m(f, 700)
    path = filter_path(y, f, 4e-5)
    unit = reference_filter(y, f, 4e-5, path.r_hat, m_inv)
    assert np.abs(unit.states[B - 1 :] - path.states[B - 1 :]).max() < 1e-12
    assert np.abs(unit.cov[B - 1 :] - path.r_hat * path.cov_scale[B - 1 :]).max() < 1e-12 * 10


# ============================================================ hyperparameters and vintages
def test_tkb07_grid_and_parabolic_refinement() -> None:
    grid = LAMBDA_GRID
    assert len(grid) == 58 and grid[0] == 0.0
    assert grid[1] == pytest.approx(1e-9) and grid[-1] == pytest.approx(1e-2)
    ll = np.full(len(grid), -np.inf)
    ll[1:] = -((np.log10(grid[1:]) + 4.3) ** 2)
    lam, bound = refine_lambda(grid, ll)
    assert abs(math.log10(lam) + 4.3) < 1e-9 and bound == "none"
    decreasing = -np.arange(len(grid), dtype=np.float64)
    assert refine_lambda(grid, decreasing) == (0.0, "zero")
    rising = np.arange(len(grid), dtype=np.float64)
    assert refine_lambda(grid, rising) == (float(grid[-1]), "upper")


def test_tkb08_vintage_schedule() -> None:
    y, f = _xy(608, 2520)
    assert vintage_rows(2520) == tuple(range(504, 2521, 252)) and len(vintage_rows(2520)) == 9
    res = kalman_betas(y, f)
    assert [v.rows for v in res.vintages] == list(range(504, 2521, 252))
    assert (res.vintage_index[:503] == -1).all() and np.isnan(res.betas[:503]).all()
    assert (res.vintage_index[503:755] == 0).all()
    assert res.vintage_index[755] == 1 and res.vintage_index[-1] == 8
    assert [v.valid_from for v in res.vintages][:2] == [504, 756]
    assert [v.valid_to for v in res.vintages][:2] == [755, 1007]
    for v in res.vintages:
        m = kf._drift_shape(f, v.rows)  # pyright: ignore[reportPrivateUsage]
        assert m is not None
        assert np.abs(m - _scale_m(f, v.rows)).max() < 1e-12 * np.abs(m).max()


def test_pipeline_matches_a_naive_reference_end_to_end() -> None:
    """Grid, parabolic step, vintage re-runs, bands and ex-ante betas, by the naive recursion."""
    y, f = _xy(609, 800)
    res = kalman_betas(y, f)
    assert [v.rows for v in res.vintages] == [504, 756]
    for v in res.vintages:
        m_inv = _scale_m(f, v.rows)
        loglik = np.array(
            [reference_vintage_loglik(y, f, float(g), m_inv, v.rows) for g in LAMBDA_GRID]
        )
        lam, bound = refine_lambda(LAMBDA_GRID, loglik)
        assert v.lam == pytest.approx(lam, rel=1e-8, abs=0.0)
        assert v.lam_at_bound == bound
        run = reference_filter(y, f, lam, 1.0, m_inv)
        r_hat = float(np.mean(run.innov[B : v.rows] ** 2 / run.var[B : v.rows]))
        assert v.resid_var == pytest.approx(r_hat, rel=1e-8)
        lo, hi = v.valid_from - 1, v.valid_to
        assert np.abs(res.betas[lo:hi] - run.states[lo:hi, 1:]).max() < 1e-8
        assert np.abs(res.alpha[lo:hi] - run.states[lo:hi, 0]).max() < 1e-8
        sd = np.sqrt(r_hat * np.diagonal(run.cov[lo:hi], axis1=1, axis2=2)[:, 1:])
        assert np.abs(res.band_high[lo:hi] - (run.states[lo:hi, 1:] + Z_975 * sd)).max() < 1e-8
        assert np.abs(res.band_low[lo:hi] - (run.states[lo:hi, 1:] - Z_975 * sd)).max() < 1e-8
        assert v.w_eq == (None if lam == 0 else pytest.approx(2 / math.sqrt(lam)))
    # ex-ante: the prediction for stamp t is the filtered state of t-1 (same vintage as t-1)
    assert np.isnan(res.ex_ante[503]).all()
    assert np.abs(res.ex_ante[504:] - res.betas[503:-1]).max() == 0.0
    assert np.abs(res.latest_sd - (res.band_high[-1] - res.betas[-1]) / Z_975).max() < 1e-12


def test_batched_filter_equals_single_filter() -> None:
    """The batched output pass and the single-path filter agree (guards the batch layout)."""
    y, f = _xy(610, 1300)
    res = kalman_betas(y, f)
    v = res.vintages[-1]
    path = filter_path(y, f, v.lam, drift_shape=_scale_m(f, v.rows))
    lo = v.valid_from - 1
    assert np.abs(res.betas[lo:] - path.states[lo:, 1:]).max() < 1e-10


@pytest.mark.slow
@pytest.mark.parametrize("lam", [1e-3, 1e-4])
def test_tkb09_equivalent_window(lam: float) -> None:
    rng = rng_for(609 + 40, 20261118 + 609 + int(-math.log10(lam)))
    window = round(2 / math.sqrt(lam))
    m_inv = np.diag(1 / SD**2)
    kf_sq = roll_sq = 0.0
    reps = KB_REPS
    truth = np.array([1.10, 0.30, -0.40, 0.25, 0.15])
    for _ in range(reps):
        f = rng.normal(MU, SD, size=(3000, 5))
        y = 0.0002 + f @ truth + rng.normal(0, 0.012, 3000)
        est = filter_path(y, f, lam, drift_shape=m_inv).states[:, 1:]
        roll = rolling_ols(y, f, window)
        kf_sq += float(np.mean((est[504:] - truth) ** 2))
        roll_sq += float(np.mean((roll[504:] - truth) ** 2))
    ratio = math.sqrt(kf_sq / reps) / math.sqrt(roll_sq / reps)
    assert 0.90 <= ratio <= 1.05


# ============================================================ simulations (DGP-KB)
KB_ALPHA, KB_SIGMA_E, KB_N = 0.0002, 0.012, 2520
KB_BETA = np.array([1.10, 0.30, -0.40, 0.25, 0.15])


@dataclass(frozen=True)
class SimRep:
    result: KalmanResult
    truth: FloatArray
    y: FloatArray
    f: FloatArray


@cache
def _simulate(case: str, number: int) -> tuple[SimRep, ...]:
    """DGP-KB (KB7.1): RW betas with lambda 1e-4, STEP at row 1261, or CONST; Gaussian errors."""
    rng = np.random.default_rng(20261118 + 600 + number)
    m_inv = np.linalg.inv(SIGMA_F)
    reps: list[SimRep] = []
    for _ in range(KB_REPS):
        f = rng.multivariate_normal(MU, SIGMA_F, size=KB_N)
        truth = np.tile(KB_BETA, (KB_N, 1))
        if case == "rw":
            steps = rng.multivariate_normal(np.zeros(5), 1e-4 * KB_SIGMA_E**2 * m_inv, size=KB_N)
            truth = KB_BETA + np.cumsum(steps, axis=0)
        elif case == "step":
            truth[1260:, 0] = 1.60
            truth[1260:, 2] = 0.20
        y = KB_ALPHA + np.einsum("ti,ti->t", f, truth) + rng.normal(0, KB_SIGMA_E, KB_N)
        reps.append(SimRep(kalman_betas(y, f), truth, y, f))
    return tuple(reps)


def _rmse(estimates: list[FloatArray], truths: list[FloatArray]) -> float:
    sq = [np.mean((e[503:] - t[503:]) ** 2) for e, t in zip(estimates, truths, strict=True)]
    return float(np.sqrt(np.mean(sq)))


@pytest.mark.slow
def test_tkb10_ml_recovery() -> None:
    ratios = [r.result.vintages[-1].lam / 1e-4 for r in _simulate("rw", 10)]
    assert 0.85 <= float(np.median(ratios)) <= 1.18


@pytest.mark.slow
def test_tkb11_false_drift() -> None:
    reps = _simulate("const", 11)
    zero = np.mean([r.result.vintages[-1].lam == 0.0 for r in reps])
    assert zero >= 0.45
    sd_kf = np.mean([np.nanstd(r.result.betas[503:, 0]) for r in reps])
    sd_roll = np.mean([np.nanstd(rolling_ols(r.y, r.f, 252)[503:, 0]) for r in reps])
    assert sd_kf <= 0.5 * sd_roll
    truths = [r.truth[:, :5] for r in reps]
    kf_rmse = _rmse([r.result.betas for r in reps], truths)
    exp_rmse = _rmse([expanding_ols(r.y, r.f) for r in reps], truths)
    assert kf_rmse <= 1.25 * exp_rmse


@pytest.mark.slow
def test_tkb19_beats_rolling_on_drifting_betas() -> None:
    reps = _simulate("rw", 10)
    truths = [r.truth for r in reps]
    kf_rmse = _rmse([r.result.betas for r in reps], truths)
    r252 = _rmse([rolling_ols(r.y, r.f, 252) for r in reps], truths)
    r126 = _rmse([rolling_ols(r.y, r.f, 126) for r in reps], truths)
    assert kf_rmse < 0.97 * r252
    assert kf_rmse < 0.97 * r126


@pytest.mark.slow
def test_tkb20_band_coverage_correct_model() -> None:
    reps = _simulate("rw", 10)
    for k in range(5):
        hit = np.mean(
            [
                np.mean(
                    (r.truth[503:, k] >= r.result.band_low[503:, k])
                    & (r.truth[503:, k] <= r.result.band_high[503:, k])
                )
                for r in reps
            ]
        )
        assert 0.90 <= float(hit) <= 0.96, (k, hit)


@pytest.mark.slow
def test_tkb21_slow_step_response_is_documented() -> None:
    reps = _simulate("step", 21)
    midpoint = 1.35

    def first_cross(est: FloatArray) -> float:
        after = est[1260:, 0]
        hit = np.nonzero(after > midpoint)[0]
        return float(hit[0]) if len(hit) else float(len(after))

    lag_kf = float(np.median([first_cross(r.result.betas) for r in reps]))
    lag_roll = float(np.median([first_cross(rolling_ols(r.y, r.f, 252)) for r in reps]))
    assert lag_kf >= lag_roll


# ============================================================ robust variant
def test_tkb12_t_weights() -> None:
    assert t_weight(np.array([0.5]), 5.0)[0] == 1.0
    assert t_weight(np.array([16.0]), 5.0)[0] == pytest.approx(21 / 6)
    y, f = _xy(612, 2000)
    base = filter_path(y, f, 1e-4)
    near_gauss = filter_path(y, f, 1e-4, nu=1e12, r_hat=base.r_hat)
    assert np.abs(near_gauss.states - base.states)[B - 1 :].max() < 1e-10
    spiked = y.copy()
    spiked[1499] += 20 * 0.012
    gauss = filter_path(spiked, f, 1e-4)
    robust = filter_path(spiked, f, 1e-4, nu=5.0, r_hat=gauss.r_hat)
    move_g = abs(gauss.states[1499, 1] - gauss.states[1498, 1])
    move_t = abs(robust.states[1499, 1] - robust.states[1498, 1])
    assert move_g > 3 * move_t


def test_student_t_variant_runs_and_differs_from_gaussian() -> None:
    y, f = _xy(612, 800, seed=77)
    y = y.copy()
    y[700] += 0.3
    gauss = kalman_betas(y, f)
    robust = kalman_betas(y, f, error_model="student_t5")
    assert robust.error_model == "student_t5" and robust.status == "ok"
    assert [v.lam for v in robust.vintages] == [v.lam for v in gauss.vintages]
    assert np.abs(robust.betas[700:] - gauss.betas[700:]).max() > 1e-4
    move_g = np.abs(gauss.betas[700] - gauss.betas[699]).max()
    move_t = np.abs(robust.betas[700] - robust.betas[699]).max()
    assert move_t < move_g  # the outlier row (0-based row 700) is down-weighted


# ============================================================ look-ahead
def _perturbed(
    y: FloatArray, f: FloatArray, last_kept: int, seed: int
) -> tuple[FloatArray, FloatArray]:
    """Every row after ``last_kept`` (1-based) replaced by a different draw."""
    rng = np.random.default_rng(seed)
    y2, f2 = y.copy(), f.copy()
    k = len(y) - last_kept
    f2[last_kept:] = rng.multivariate_normal(MU, 4 * SIGMA_F, size=k)
    y2[last_kept:] = rng.normal(0.01, 0.05, size=k)
    return y2, f2


def _same_up_to(a: KalmanResult, b: KalmanResult, stamp: int, tol: float) -> None:
    for name in ("alpha", "betas", "band_low", "band_high", "ex_ante"):
        x, z = getattr(a, name)[:stamp], getattr(b, name)[:stamp]
        assert np.array_equal(np.isnan(x), np.isnan(z)), name
        assert np.nan_to_num(np.abs(x - z)).max() <= tol, name
    assert np.array_equal(a.vintage_index[:stamp], b.vintage_index[:stamp])


def test_tkb13_filtered_and_predicted_are_causal() -> None:
    y, f = _xy(613, 2520)
    star = 1800
    y2, f2 = _perturbed(y, f, star, 13)
    base, other = kalman_betas(y, f), kalman_betas(y2, f2)
    _same_up_to(base, other, star, 1e-12)
    done = [v for v in base.vintages if v.rows <= star]
    assert len(done) == 6
    for v0, v1 in zip(done, other.vintages, strict=False):
        assert abs(v0.lam - v1.lam) <= 1e-12 * max(v0.lam, 1e-300) + 1e-300
        assert abs(v0.resid_var - v1.resid_var) <= 1e-12 * v0.resid_var
    assert np.abs(base.betas[star:] - other.betas[star:]).max() > 1e-3


def test_tkb14_truncation() -> None:
    y, f = _xy(614, 2520)
    star = 1800
    full, cut = kalman_betas(y, f), kalman_betas(y[:star], f[:star])
    _same_up_to(full, cut, star, 1e-12)


def test_tkb15_vintage_boundary() -> None:
    y, f = _xy(615, 1600)
    boundary = 504 + 252 * 2  # m_2 = 1008
    y2, f2 = _perturbed(y, f, boundary - 1, 15)
    base, other = kalman_betas(y, f), kalman_betas(y2, f2)
    _same_up_to(base, other, boundary - 1, 1e-12)
    assert np.abs(base.betas[boundary - 1] - other.betas[boundary - 1]).max() > 1e-4


def test_tkb16_ex_ante_lag() -> None:
    y, f = _xy(616, 1500)
    t = 1200  # 1-based stamp, inside a vintage (m = 1008 .. 1259)
    y2, f2 = y.copy(), f.copy()
    y2[t - 1] *= 10
    f2[t - 1] *= 10
    base, other = kalman_betas(y, f), kalman_betas(y2, f2)
    assert np.abs(base.ex_ante[t - 1] - other.ex_ante[t - 1]).max() == 0.0
    assert np.abs(base.betas[t - 1] - other.betas[t - 1]).max() > 1e-4


def _smoothed(y: FloatArray, f: FloatArray, lam: float, m_inv: FloatArray) -> FloatArray:
    """Rauch-Tung-Striebel smoothed betas at a fixed lam and M (oracle only, not in the package)."""
    path = filter_path(y, f, lam, drift_shape=m_inv)
    q = np.zeros((6, 6))
    q[1:, 1:] = lam * m_inv
    smooth = path.states.copy()
    for t in range(len(y) - 2, B - 2, -1):
        pred = path.cov_scale[t] + q
        gain = path.cov_scale[t] @ np.linalg.inv(pred)
        smooth[t] = path.states[t] + gain @ (smooth[t + 1] - path.states[t])
    return smooth[:, 1:]


def test_tkb17_a_smoother_fails_the_lookahead_test_on_purpose() -> None:
    y, f = _xy(617, 900)
    star = 700
    y2, f2 = _perturbed(y, f, star, 17)
    m_inv = np.linalg.inv(SIGMA_F)
    smoothed = _smoothed(y, f, 1e-4, m_inv)[star - 2]
    smoothed2 = _smoothed(y2, f2, 1e-4, m_inv)[star - 2]
    assert np.abs(smoothed - smoothed2).max() > 1e-6
    before = filter_path(y, f, 1e-4, drift_shape=m_inv).states[: star - 1]
    after = filter_path(y2, f2, 1e-4, drift_shape=m_inv).states[: star - 1]
    assert np.abs(before - after)[B - 1 :].max() < 1e-12  # the filter alone passes the same check


def test_tkb18_static_scan_no_smoother_and_no_forward_index() -> None:
    source = Path(kf.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    names |= {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    names |= {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    assert not [n for n in names if "smooth" in n.lower()]
    assert "reversed" not in names
    loops = {"_grid_pass", "_output_pass", "_single_path"}
    for fn in ast.walk(tree):
        if not (isinstance(fn, ast.FunctionDef) and fn.name in loops):
            continue
        for node in ast.walk(fn):
            if isinstance(node, ast.Subscript) and isinstance(node.slice, ast.BinOp):
                # an index such as x[i + 1] or y[i - 1] inside the forward loop is forbidden
                assert not (isinstance(node.slice.left, ast.Name) and node.slice.left.id == "i"), (
                    ast.unparse(node)
                )


# ============================================================ status and schema
def test_tkb22_status_and_nulls() -> None:
    y, f = _xy(622, 600)
    short = kalman_betas(y[:503], f[:503])
    assert short.status == "insufficient_data" and short.reason == "kalman_needs_504_rows"
    assert short.vintages == () and not np.isfinite(short.betas).any()
    one = kalman_betas(y[:504], f[:504])
    assert one.status == "ok" and len(one.vintages) == 1
    assert int(np.isfinite(one.betas[:, 0]).sum()) == 1 and np.isfinite(one.betas[503]).all()
    assert (one.vintage_index[:503] == -1).all() and one.vintage_index[503] == 0
    assert np.isnan(one.ex_ante).all()
    flat = f.copy()
    flat[:B, 2] = 0.01  # a constant factor over rows 1..21 duplicates the intercept
    broken = kalman_betas(y, flat)
    assert broken.status == "failed" and broken.reason == "singular_burn_in"
    assert not np.isfinite(broken.betas).any() and broken.vintages == ()


def test_lambda_at_upper_bound_warns() -> None:
    """Betas that move 10% of a factor's standard error a day make the likelihood prefer 1e-2."""
    rng = np.random.default_rng(20261118 + 699)
    n = 800
    f = rng.multivariate_normal(MU, SIGMA_F, size=n)
    steps = rng.multivariate_normal(
        np.zeros(5), 0.1 * KB_SIGMA_E**2 * np.linalg.inv(SIGMA_F), size=n
    )
    y = np.einsum("ti,ti->t", f, KB_BETA + np.cumsum(steps, axis=0)) + rng.normal(0, 0.012, n)
    res = kalman_betas(y, f)
    assert res.status == "ok"
    assert res.warnings == ("kalman_lambda_at_upper_bound",)
    assert all(v.lam_at_bound == "upper" and v.lam == pytest.approx(1e-2) for v in res.vintages)


def test_inputs_are_validated_and_not_mutated() -> None:
    y, f = _xy(623, 520)
    y0, f0 = y.copy(), f.copy()
    kalman_betas(y, f)
    assert np.array_equal(y, y0) and np.array_equal(f, f0)
    with pytest.raises(ValueError):
        kalman_betas(y[:-1], f)
    bad = f.copy()
    bad[3, 1] = np.nan
    with pytest.raises(ValueError):
        kalman_betas(y, bad)


def test_filter_path_is_a_named_result() -> None:
    y, f = _xy(624, 200)
    path = filter_path(y, f, 1e-5)
    assert isinstance(path, FilterPath) and path.states.shape == (200, 6)
    with pytest.raises(ValueError):
        filter_path(y, np.column_stack([f[:, :2], np.zeros(200), f[:, 3:]]), 1e-5, burn_in=21)


# ============================================ validation: drifting betas in the default suite
def _drifting(n: int, seed: int) -> tuple[FloatArray, FloatArray]:
    """DGP-KB RW (lambda_true 1e-4): the betas drift, so the estimated lambda is positive."""
    rng = np.random.default_rng(seed)
    f = rng.multivariate_normal(MU, SIGMA_F, size=n)
    steps = rng.multivariate_normal(
        np.zeros(5), 1e-4 * KB_SIGMA_E**2 * np.linalg.inv(SIGMA_F), size=n
    )
    y = KB_ALPHA + np.einsum("ti,ti->t", f, KB_BETA + np.cumsum(steps, axis=0))
    return y + rng.normal(0, KB_SIGMA_E, n), f


def test_pipeline_matches_a_naive_reference_with_drifting_betas() -> None:
    """The end-to-end reference check above, on data where every vintage has lambda > 0.

    On DGP-A (constant betas) the grid picks lambda = 0 or nearly 0, so a wrong state-noise
    term in the batched passes (dropped, rescaled, or different between the grid and the
    output pass) goes unnoticed by the default suite. Here it cannot.
    """
    y, f = _drifting(1100, 20261118 + 690)
    res = kalman_betas(y, f)
    assert [v.rows for v in res.vintages] == [504, 756, 1008]
    for v in res.vintages:
        assert v.lam > 1e-6, v.lam
        m_inv = _scale_m(f, v.rows)
        loglik = np.array(
            [reference_vintage_loglik(y, f, float(g), m_inv, v.rows) for g in LAMBDA_GRID]
        )
        lam, bound = refine_lambda(LAMBDA_GRID, loglik)
        assert v.lam == pytest.approx(lam, rel=1e-8, abs=0.0)
        assert v.lam_at_bound == bound
        run = reference_filter(y, f, lam, 1.0, m_inv)
        r_hat = float(np.mean(run.innov[B : v.rows] ** 2 / run.var[B : v.rows]))
        assert v.resid_var == pytest.approx(r_hat, rel=1e-8)
        lo, hi = v.valid_from - 1, v.valid_to
        assert np.abs(res.betas[lo:hi] - run.states[lo:hi, 1:]).max() < 1e-8
        sd = np.sqrt(r_hat * np.diagonal(run.cov[lo:hi], axis1=1, axis2=2)[:, 1:])
        assert np.abs(res.band_low[lo:hi] - (run.states[lo:hi, 1:] - Z_975 * sd)).max() < 1e-8
        assert np.abs(res.band_high[lo:hi] - (run.states[lo:hi, 1:] + Z_975 * sd)).max() < 1e-8


def test_tkb13_causal_with_drifting_betas() -> None:
    """TKB13 on drifting betas (lambda > 0 in every finished vintage)."""
    y, f = _drifting(1600, 20261118 + 691)
    star = 1100
    y2, f2 = _perturbed(y, f, star, 691)
    base, other = kalman_betas(y, f), kalman_betas(y2, f2)
    done = [v for v in base.vintages if v.rows <= star]
    assert len(done) == 3 and all(v.lam > 1e-6 for v in done)
    _same_up_to(base, other, star, 1e-12)
    for v0, v1 in zip(done, other.vintages, strict=False):
        assert v0.lam == pytest.approx(v1.lam, rel=1e-12)
        assert v0.resid_var == pytest.approx(v1.resid_var, rel=1e-12)
    assert np.abs(base.betas[star:] - other.betas[star:]).max() > 1e-3


# ============================== drift term of the batched passes against independent references
def test_batched_passes_match_statsmodels_at_positive_lambda() -> None:
    """Output pass: states and bands equal statsmodels' filter, in every vintage, at lambda > 0.

    statsmodels is independent of this package's recursion. A missing, rescaled or doubled
    state-noise term in ``_output_pass`` moves the betas and the bands away from it (the live
    SPY tests caught these changes; this one needs no cached data).
    """
    y, f = _drifting(1100, 20261118 + 692)
    res = kalman_betas(y, f)
    assert len(res.vintages) == 3
    for v in res.vintages:
        assert v.lam > 1e-6, v.lam
        lo, hi = v.valid_from - 1, v.valid_to
        states, cov, _ = sm_filter(y[:hi], f[:hi], v.lam, v.resid_var, _scale_m(f, v.rows))
        assert np.abs(res.betas[lo:hi] - states[lo:hi, 1:]).max() < 1e-9
        sd = np.sqrt(np.diagonal(cov[lo:hi], axis1=1, axis2=2)[:, 1:])
        assert np.abs(res.band_low[lo:hi] - (states[lo:hi, 1:] - Z_975 * sd)).max() < 1e-9
        assert np.abs(res.band_high[lo:hi] - (states[lo:hi, 1:] + Z_975 * sd)).max() < 1e-9


def test_grid_pass_picks_the_maximiser_of_the_single_path_likelihood() -> None:
    """Grid pass: each vintage's lambda is the refined maximiser of ``filter_path`` likelihoods.

    ``filter_path`` is tied to statsmodels by TKB02. If ``_grid_pass`` used a different
    state-noise term from the output pass (for example ``Q`` doubled), the grid would pick a
    lambda that is off by that factor, and this comparison fails.
    """
    y, f = _drifting(800, 20261118 + 693)
    res = kalman_betas(y, f)
    assert [v.rows for v in res.vintages] == [504, 756]
    for v in res.vintages:
        assert v.lam > 1e-6, v.lam
        m_inv = _scale_m(f, v.rows)
        loglik = np.array(
            [
                filter_path(y[: v.rows], f[: v.rows], float(g), drift_shape=m_inv).loglik
                for g in LAMBDA_GRID
            ]
        )
        lam, bound = refine_lambda(LAMBDA_GRID, loglik)
        assert v.lam == pytest.approx(lam, rel=1e-8, abs=0.0)
        assert v.lam_at_bound == bound
        path = filter_path(y[: v.rows], f[: v.rows], lam, drift_shape=m_inv)
        assert v.resid_var == pytest.approx(path.r_hat, rel=1e-8)
