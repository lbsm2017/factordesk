"""Shrunk-betas posterior, power and simulations (spec SB11: TSB01-TSB06, TSB10, TSB12-TSB15).

Seeds: test ``TSBNN`` uses ``default_rng(20261118 + 700 + NN)`` (spec SB11 conventions).
"""

from __future__ import annotations

import math

import numpy as np
import pytest
from numpy.typing import NDArray

from factordesk.analytics.regression import Z_975, hac_lags, ols_hac
from factordesk.analytics.sample import build_sample
from factordesk.analytics.shrinkage import (
    COND_LIMIT,
    K80,
    MOVE_TOLERANCE,
    SingularCovarianceError,
    any_visible_pull,
    display_pull,
    extra_years,
    mde,
    posterior,
    power_statements,
    power_text,
    rows_required,
    window_fit,
)
from factordesk.tests.fixtures.dgp import MU, SIGMA_F, dgp_a, rng_for
from factordesk.tests.fixtures.reference import hac_fit

FloatArray = NDArray[np.float64]

TAU_DEFAULT = np.array([0.209, 0.764, 0.341, 0.329, 0.254])
"""The default prior spread of spec SB2.2 (current values), used by the simulations."""
M0 = np.array([1.0, 0.0, 0.0, 0.0, 0.0])
NAMES = ("Mkt-RF", "SMB", "HML", "RMW", "CMA")


def _seed(nn: int) -> np.random.Generator:
    return rng_for(700 + nn)


def _random_spd(rng: np.random.Generator, k: int = 5) -> FloatArray:
    """SPD matrix with eigenvalues in ``[1e-4, 1e-1]`` (spec TSB01)."""
    q, _ = np.linalg.qr(rng.standard_normal((k, k)))
    eig = np.exp(rng.uniform(math.log(1e-4), math.log(1e-1), size=k))
    eig[0], eig[-1] = 1e-4, 1e-1
    return (q * eig) @ q.T


# ------------------------------------------------------------------------------------ identities
def test_tsb01_flat_prior_limit() -> None:
    rng = _seed(1)
    v = _random_spd(rng)
    b = rng.normal(size=5)
    post = posterior(b, v, M0, np.full(5, 1e8))
    assert np.abs(post.b_post - b).max() <= 1e-10
    assert np.abs(post.v_post - v).max() / np.abs(v).max() <= 1e-10
    se = np.sqrt(np.diag(v))
    assert np.abs(post.cred_low - (b - Z_975 * se)).max() <= 1e-10
    assert np.abs(post.cred_high - (b + Z_975 * se)).max() <= 1e-10
    assert not any(post.moved_away)


def test_tsb01_flat_prior_equals_the_hac_ci95_of_the_regression() -> None:
    d = dgp_a(_seed(1))
    s = build_sample(d.history, d.factors)
    fit = ols_hac(s.xret.to_numpy(), s.factors.to_numpy())
    post = posterior(fit.params[1:], fit.cov[1:, 1:], M0, np.full(5, 1e8))
    assert np.abs(post.cred_low - fit.ci_low[1:]).max() <= 1e-10
    assert np.abs(post.cred_high - fit.ci_high[1:]).max() <= 1e-10


def test_tsb02_dogmatic_limit() -> None:
    rng = _seed(2)
    v = _random_spd(rng)
    b = rng.normal(size=5)
    post = posterior(b, v, M0, np.full(5, 1e-8))
    assert np.abs(post.b_post - M0).max() <= 1e-6
    assert np.abs(post.v_post).max() <= 1e-15
    assert (post.pull > 0.999999).all()


def test_tsb03_weight_identities() -> None:
    rng = _seed(3)
    for _ in range(20):
        v = _random_spd(rng)
        b = rng.normal(size=5)
        centre = rng.normal(size=5)
        tau = rng.uniform(0.05, 1.5, size=5)
        post = posterior(b, v, centre, tau)
        eye = np.eye(5)
        assert np.abs(post.b_post - ((eye - post.weight) @ b + post.weight @ centre)).max() <= 1e-12
        assert np.abs(post.v_post @ np.linalg.inv(v) + post.weight - eye).max() <= 1e-12


def test_tsb04_scalar_hand_example() -> None:
    post = posterior(np.array([0.6]), np.array([[0.04]]), np.array([0.0]), np.array([0.2]))
    assert abs(post.pull[0] - 0.5) <= 1e-15
    assert abs(post.b_post[0] - 0.3) <= 1e-15
    assert abs(post.v_post[0, 0] - 0.02) <= 1e-15


def test_tsb04_diagonal_version_matches_the_scalar_formula() -> None:
    rng = _seed(4)
    var = rng.uniform(0.005, 0.1, size=5)
    tau = rng.uniform(0.05, 0.9, size=5)
    b = rng.normal(size=5)
    post = posterior(b, np.diag(var), M0, tau)
    expected = (tau**2 * b + var * M0) / (tau**2 + var)
    assert np.abs(post.b_post - expected).max() <= 1e-12
    assert np.abs(post.pull - var / (var + tau**2)).max() <= 1e-12


def test_tsb05_correlated_estimates_can_move_away_from_the_prior_centre() -> None:
    # Spec SB11 as first written used b = (0.5, 0.5); with a positive covariance that pulls the
    # first coefficient toward 0 too (see the next test). The corrected oracle uses opposite signs.
    v = np.array([[0.04, 0.036], [0.036, 0.04]])
    post = posterior(np.array([0.5, -0.5]), v, np.array([0.0, 0.0]), np.array([10.0, 0.1]))
    assert post.b_post[0] > 0.5
    assert post.moved_away == (True, False)
    # Hand check (tau_1 large): the second coefficient has pull 0.04 / (0.04 + 0.01) = 0.8, so it
    # goes to 0.2 (-0.5) = -0.1, and the first follows through the covariance:
    # 0.5 + (V12 / V22)(-0.1 - (-0.5)) = 0.5 + 0.9 * 0.4 = 0.86.
    assert abs(post.b_post[0] - 0.86) <= 0.005
    assert abs(post.b_post[1] + 0.1) <= 0.005


def test_tsb05_same_signs_move_toward_the_centre() -> None:
    v = np.array([[0.04, 0.036], [0.036, 0.04]])
    post = posterior(np.array([0.5, 0.5]), v, np.array([0.0, 0.0]), np.array([10.0, 0.1]))
    assert post.b_post[0] < 0.5
    assert post.moved_away == (False, False)


def test_tsb05_no_move_away_when_the_shift_is_zero_or_toward_the_centre() -> None:
    v = np.diag([0.04, 0.04])
    post = posterior(np.array([0.5, 0.0]), v, np.array([0.0, 0.0]), np.array([0.2, 0.2]))
    assert post.moved_away == (False, False)  # first moves toward 0; second b == m0, no move


def test_moved_away_ignores_rounding_noise_in_the_flat_prior_limit() -> None:
    # Reordering the coefficients changes only the order of the floating point operations. The
    # true shift is zero, so no ordering may flag a move (this failed on Linux before the
    # tolerance: the noise is about 1e-14 and its sign depends on the ordering).
    rng = _seed(1)
    v = _random_spd(rng)
    b = rng.normal(size=5)
    tau = np.full(5, 1e8)
    for order in (np.arange(5), np.arange(5)[::-1], np.array([2, 0, 4, 1, 3])):
        post = posterior(b[order], v[np.ix_(order, order)], M0[order], tau)
        assert np.abs(post.b_post - b[order]).max() > 0.0  # there is noise to ignore
        assert not any(post.moved_away)


def test_moved_away_tolerance_has_two_sides() -> None:
    # TSB05 input: the first coefficient is pushed away from 0 through the covariance by the
    # pull on the second, so its shift is 0.9 * 0.5 * pull_2 and its scale is 0.5. The spread of
    # the second coefficient sets the pull (about V_22 / tau^2 when tau is large).
    v = np.array([[0.04, 0.036], [0.036, 0.04]])
    b = np.array([0.5, -0.5])
    m0 = np.array([0.0, 0.0])

    def first(tau_2: float) -> tuple[float, bool]:
        post = posterior(b, v, m0, np.array([1e8, tau_2]))
        return abs(post.b_post[0] - b[0]) / 0.5, post.moved_away[0]

    just_inside, flag_inside = first(1.9e4)  # relative shift about 1e-10
    just_outside, flag_outside = first(1.9e3)  # relative shift about 1e-8
    clear, flag_clear = first(0.1)  # relative shift about 0.7
    assert 0.0 < just_inside < MOVE_TOLERANCE and not flag_inside
    assert just_outside > MOVE_TOLERANCE and flag_outside
    assert clear > 0.1 and flag_clear


def test_tsb06_hac_block_is_the_reference_block_with_the_rule_of_the_regression() -> None:
    d = dgp_a(_seed(6))
    s = build_sample(d.history, d.factors)
    y, f = s.xret.to_numpy(), s.factors.to_numpy()
    n = len(y)
    fit = ols_hac(y, f)
    ref = hac_fit(y, f, hac_lags(n))
    block = ref.cov[1:, 1:]
    post = posterior(fit.params[1:], fit.cov[1:, 1:], M0, TAU_DEFAULT)
    assert np.abs(post.v_post - posterior(ref.params[1:], block, M0, TAU_DEFAULT).v_post).max() <= (
        1e-10 * np.abs(post.v_post).max()
    )
    assert np.abs(fit.cov[1:, 1:] - block).max() <= 1e-10 * np.abs(block).max()
    assert np.allclose(post.se_hac, np.sqrt(np.diag(block)), rtol=1e-10, atol=0.0)


def test_tsb06_latest_window_uses_the_rule_of_the_window() -> None:
    d = dgp_a(_seed(6))
    s = build_sample(d.history, d.factors)
    y, f = s.xret.to_numpy(), s.factors.to_numpy()
    w = 252
    fit = window_fit(y, f, w)
    ref = hac_fit(y[-w:], f[-w:], hac_lags(w))
    assert fit.lags == hac_lags(w) == 4
    assert np.abs(fit.cov[1:, 1:] - ref.cov[1:, 1:]).max() <= 1e-10 * np.abs(ref.cov[1:, 1:]).max()
    assert np.abs(fit.params - ref.params).max() <= 1e-12
    with pytest.raises(ValueError):
        window_fit(y, f, len(y) + 1)


def test_singular_covariance_is_refused() -> None:
    v = np.diag([1.0, 1.0, 1.0, 1.0, 1.0])
    v[0, 0] = 1.0 / (COND_LIMIT * 10)
    with pytest.raises(SingularCovarianceError):
        posterior(np.zeros(5), v, M0, TAU_DEFAULT)
    with pytest.raises(SingularCovarianceError):
        posterior(np.zeros(5), np.full((5, 5), np.nan), M0, TAU_DEFAULT)
    with pytest.raises(SingularCovarianceError):
        posterior(np.zeros(5), np.zeros((5, 5)), M0, TAU_DEFAULT)
    ok = np.diag([1.0, 1.0, 1.0, 1.0, 1.0])
    ok[0, 0] = 1.0 / (COND_LIMIT / 10)
    posterior(np.zeros(5), ok, M0, TAU_DEFAULT)  # just inside the limit


def test_posterior_rejects_bad_shapes_and_tau() -> None:
    with pytest.raises(ValueError):
        posterior(np.zeros(5), np.eye(4), M0, TAU_DEFAULT)
    with pytest.raises(ValueError):
        posterior(np.zeros(5), np.eye(5), M0, np.zeros(5))


def test_display_pull_is_clipped_and_the_threshold_is_inclusive() -> None:
    assert display_pull(-0.01) == 0.0
    assert display_pull(1.02) == 1.0
    assert any_visible_pull([0.0, 0.05]) is True
    assert any_visible_pull([0.0, 0.0499]) is False
    assert any_visible_pull([-0.2, 1.1]) is True


# ------------------------------------------------------------------------------------------ power
def test_tsb10_mde_and_years_hand_example() -> None:
    from statistics import NormalDist

    nd = NormalDist()
    assert abs(K80 - (nd.inv_cdf(0.995) + nd.inv_cdf(0.8))) <= 1e-12
    assert abs(K80 - 3.41745) <= 1e-5
    assert abs(mde(0.02) - 0.0683490) <= 1e-6
    assert abs(rows_required(0.02, 504) - 941.792) <= 1e-3
    assert abs(extra_years(0.02, 504) - 1.7373) <= 1e-4


def test_tsb10_sentences() -> None:
    power = power_statements([0.01, 0.02, 0.001, 0.9, 0.02], 504, NAMES)
    market, smb, hml, rmw, cma = power
    assert market.extra_years is None
    assert "would take" not in market.text and "detectable" not in market.text
    assert "0.03" in market.text and "2.0 years" in market.text
    assert smb.extra_years is not None and abs(smb.extra_years - 1.7373) <= 1e-4
    assert "about 1.7 more years" in smb.text
    assert "already detectable" in power_statements([0.001] * 5, 2520, NAMES)[2].text
    assert hml.extra_years == 0.0
    worst = power_statements([0.9] * 5, 633, NAMES)[3]
    assert "not detectable" in worst.text and "more than 50 years" in worst.text
    assert rmw.text.startswith("With 2.0 years of data")
    assert cma.extra_years is not None


def test_power_statement_grammar_and_boundaries() -> None:
    assert "an SMB beta" in power_text("SMB", 504, 0.1, 1.0)
    assert "a CMA beta" in power_text("CMA", 504, 0.1, 1.0)
    assert "a Mkt-RF beta" in power_text("Mkt-RF", 504, 0.1, None)
    assert "An SMB beta of 0.05 is already detectable" in power_text("SMB", 504, 0.1, 0.0)
    assert "less than 0.1 more years" in power_text("HML", 504, 0.1, 0.0123)
    assert "about 0.1 more years" in power_text("HML", 504, 0.1, 0.05)
    # 50 years is still "about"; just above is "not detectable".
    assert "about 50.0 more years" in power_text("HML", 504, 0.1, 50.0)
    assert "not detectable" in power_text("HML", 504, 0.1, 50.01)
    with pytest.raises(ValueError):
        power_statements([0.0, 0.1, 0.1, 0.1, 0.1], 504, NAMES)
    with pytest.raises(ValueError):
        power_statements([0.1, 0.1], 504, NAMES)


# ------------------------------------------------------------------------------- simulations
def _simulate(
    rng: np.random.Generator,
    n: int,
    runs: int,
    *,
    spread: float = 1.0,
    serial: bool = False,
) -> tuple[FloatArray, FloatArray, FloatArray, FloatArray, FloatArray]:
    """DGP-SB of spec SB8.3: ``runs`` stocks on one factor draw, true betas ~ N(m0, (c tau)^2).

    Returns squared errors of OLS and shrunk betas, and 95% interval hits for the credible
    interval with the HAC covariance and with the OLS covariance, each ``(runs, 5)``.
    """
    sigma_e = 0.30 / math.sqrt(252.0)
    if serial:
        chol = np.linalg.cholesky(SIGMA_F)
        nu = rng.standard_normal((n, 5)) @ chol.T
        z = np.empty((n, 5))
        z[0] = nu[0]
        for t in range(1, n):
            z[t] = 0.5 * z[t - 1] + math.sqrt(0.75) * nu[t]
        f = MU + z
        eps = rng.standard_normal((n, runs))
        e = np.empty((n, runs))
        e[0] = sigma_e * eps[0]
        for t in range(1, n):
            e[t] = 0.5 * e[t - 1] + math.sqrt(0.75) * sigma_e * eps[t]
    else:
        f = rng.multivariate_normal(MU, SIGMA_F, size=n)
        e = rng.normal(0.0, sigma_e, size=(n, runs))
    true = M0 + spread * TAU_DEFAULT * rng.standard_normal((runs, 5))
    y = 0.0002 + f @ true.T + e
    x = np.column_stack([np.ones(n), f])
    xtx_inv = np.linalg.inv(x.T @ x)
    err_ols = np.empty((runs, 5))
    err_shr = np.empty((runs, 5))
    hit_hac = np.empty((runs, 5), dtype=bool)
    hit_ols = np.empty((runs, 5), dtype=bool)
    for r in range(runs):
        fit = ols_hac(y[:, r], f)
        b = fit.params[1:]
        post = posterior(b, fit.cov[1:, 1:], M0, TAU_DEFAULT)
        err_ols[r] = (b - true[r]) ** 2
        err_shr[r] = (post.b_post - true[r]) ** 2
        hit_hac[r] = (post.cred_low <= true[r]) & (true[r] <= post.cred_high)
        v_ols = (fit.resid @ fit.resid) / (n - 6) * xtx_inv[1:, 1:]
        post_ols = posterior(b, v_ols, M0, TAU_DEFAULT)
        hit_ols[r] = (post_ols.cred_low <= true[r]) & (true[r] <= post_ols.cred_high)
    return err_ols, err_shr, hit_hac.astype(float), hit_ols.astype(float), true


@pytest.mark.slow
def test_tsb12_and_tsb13_prior_correct() -> None:
    err_ols, err_shr, hit, _, _ = _simulate(_seed(12), 504, 4000)
    ratio = err_shr.mean(axis=0).sum() / err_ols.mean(axis=0).sum()
    assert ratio < 0.8, ratio  # TSB12: observed 0.61 in the spec
    cover = hit.mean(axis=0)
    assert ((cover >= 0.925) & (cover <= 0.965)).all(), cover  # TSB13


@pytest.mark.slow
def test_tsb14_prior_too_tight_is_harmful() -> None:
    err_ols, err_shr, _, _, _ = _simulate(_seed(14), 504, 4000, spread=2.0)
    assert err_shr.mean(axis=0).sum() > err_ols.mean(axis=0).sum()


@pytest.mark.slow
def test_tsb15_hac_covariance_beats_ols_covariance_under_serial_correlation() -> None:
    _, _, hit_hac, hit_ols, _ = _simulate(_seed(15), 504, 2000, serial=True)
    cover_hac = float(hit_hac.mean())
    cover_ols = float(hit_ols.mean())
    assert cover_hac - cover_ols >= 0.02, (cover_hac, cover_ols)
    assert cover_hac >= 0.90, cover_hac
