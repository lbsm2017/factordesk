"""Return and risk contribution tests (test-oracle T53, T57-T62, T96, T98; M6.1, M6.4, M7)."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest
from numpy.typing import NDArray

from factordesk.analytics.attribution import (
    IDIOSYNCRATIC,
    euler_risk,
    memo_rows,
    return_contribution_for,
    risk_contribution_for,
    risk_order,
    risk_sentences,
)
from factordesk.analytics.regression import run_regression
from factordesk.analytics.sample import FACTOR_CODES, AnalysisSample, build_sample
from factordesk.data.prices import PriceHistory
from factordesk.tests.fixtures.dgp import FETCHED_AT, dgp_a, rng_for

NAMES = ("Mkt-RF", "SMB", "HML", "RMW", "CMA")


def _arr(x: object) -> NDArray[np.float64]:
    return np.asarray(x, dtype=np.float64)


def _dgp_sample(test_number: int, n: int = 2520) -> AnalysisSample:
    d = dgp_a(rng_for(test_number), n=n)
    return build_sample(d.history, d.factors)


def test_t53_static_return_identity() -> None:
    s = _dgp_sample(53)
    reg = run_regression(s)
    ra = return_contribution_for(s, reg)
    lhs = sum(ra.contributions.values()) + ra.alpha_ann + ra.residual_ann
    mean_y = float(np.mean(_arr(s.xret)))
    assert abs(lhs - 252 * mean_y) <= 1e-10
    assert abs(ra.total_ann - 252 * mean_y) <= 1e-15
    assert abs(ra.residual_ann) <= 1e-12
    assert abs(ra.identity_residual) <= 1e-10
    for i, name in enumerate(NAMES):
        expected = 252 * reg.betas[i] * float(s.factors[FACTOR_CODES[i]].mean())
        assert ra.contributions[name] == pytest.approx(expected, rel=1e-12)


def test_t57_memo_rows_outside_the_identity() -> None:
    d = dgp_a(rng_for(57), n=830)
    frame = d.history.frame
    factors = d.factors.iloc[:800].drop(index=d.factors.index[[100, 200]])  # 2 excluded rows
    s = build_sample(d.history, factors)
    assert s.uncovered.n == 30 and len(s.excluded) == 2
    reg = run_regression(s)
    ra = return_contribution_for(s, reg)
    memo = memo_rows(s.uncovered, s.excluded, s.factor_last_date)
    assert memo[0].startswith("Not covered by factor data: 30 trading days after")
    assert "(compounded, raw, not excess). Not attributed." in memo[0]
    assert memo[1] == "Excluded rows: 2 (date not in the factor file: 2)."
    # The memo value is not part of the identity: the identity closes without it.
    assert abs(ra.identity_residual) <= 1e-10
    # Deleting the tail leaves alpha unchanged.
    trimmed = PriceHistory("SYN", frame.iloc[:801], FETCHED_AT, "synthetic")
    reg2 = run_regression(build_sample(trimmed, factors))
    assert reg2.alpha == reg.alpha


def test_t58_variance_identities() -> None:
    s = _dgp_sample(58)
    reg = run_regression(s)
    rk = risk_contribution_for(s, reg)
    assert rk.variance == pytest.approx(float(np.var(s.xret.to_numpy(), ddof=1)), rel=1e-12)
    assert abs(float(rk.shares.sum()) + rk.idio_share - 1.0) <= 1e-10
    assert abs(rk.sums_to_one_residual) <= 1e-10
    assert abs((1.0 - rk.idio_share) - reg.fit.rsquared) <= 1e-10


def test_t59_exposure_volatility_correlation() -> None:
    s = _dgp_sample(59)
    reg = run_regression(s)
    rk = risk_contribution_for(s, reg)
    for i in range(5):
        rho = rk.rho_sys[i]
        assert rho is not None
        lhs = rk.shares[i] * rk.variance
        rhs = rk.betas[i] * rk.sigma[i] * rho * rk.sigma_sys
        assert lhs == pytest.approx(rhs, rel=1e-12)


def test_t60_euler_property() -> None:
    s = _dgp_sample(60)
    reg = run_regression(s)
    rk = risk_contribution_for(s, reg)
    sigma_f = np.cov(s.factors.to_numpy(), rowvar=False, ddof=1)
    e = reg.fit.resid
    s_e = math.sqrt(float(e @ e) / (len(e) - 1))

    def vol(b: np.ndarray) -> float:
        return math.sqrt(float(b @ sigma_f @ b) + s_e**2)

    b0 = reg.betas.copy()
    sigma = vol(b0)
    h = 1e-6
    for i in range(5):
        up, dn = b0.copy(), b0.copy()
        up[i] += h
        dn[i] -= h
        deriv = (vol(up) - vol(dn)) / (2 * h)
        assert b0[i] * deriv == pytest.approx(rk.shares[i] * sigma, rel=1e-6)


def _t61_inputs() -> tuple[np.ndarray, np.ndarray, float]:
    sd = np.array([0.010, 0.006, 0.005, 0.004, 0.004])
    corr = np.eye(5)
    corr[0, 1] = corr[1, 0] = 0.8
    return np.outer(sd, sd) * corr, np.array([1.0, -1.0, 0.0, 0.0, 0.0]), 0.01**2


def test_t61_negative_contribution() -> None:
    sigma_f, beta, s2e = _t61_inputs()
    rk = euler_risk(sigma_f, beta, s2e, NAMES)
    assert (sigma_f @ beta)[1] == pytest.approx(0.8 * 0.010 * 0.006 - 0.006**2, rel=1e-12)
    assert rk.shares[1] < 0
    assert abs(float(rk.shares.sum()) + rk.idio_share - 1.0) <= 1e-12
    order = risk_order(NAMES, [float(v) for v in rk.shares])
    assert order[-1] == IDIOSYNCRATIC and order[-2] == "SMB"
    shares = [float(v) for v in rk.shares]
    tagged = risk_sentences(
        NAMES, list(beta), shares, ["reliable", "reliable", "noise", "noise", "noise"]
    )
    assert (
        "SMB has a negative share: it offsets part of the other exposures in the variance split."
        in tagged
    )
    assert not any("because" in t or "your" in t for t in tagged)
    untagged = risk_sentences(
        NAMES, list(beta), shares, ["reliable", "noise", "noise", "noise", "noise"]
    )
    assert not any("negative share" in t for t in untagged)


def test_t62_disagreement_sentence() -> None:
    betas = [5.0, 4.0, 3.0, 2.0, 1.0]  # |beta| ranks 1..5

    def shares_for(ranks: tuple[int, ...]) -> list[float]:
        return [(6 - r) / 100 for r in ranks]

    tags: list[str] = ["reliable"] * 5
    assert risk_sentences(NAMES, betas, shares_for((1, 4, 2, 3, 5)), tags) == []  # type: ignore[arg-type]
    out = risk_sentences(NAMES, betas, shares_for((2, 3, 4, 1, 5)), tags)  # type: ignore[arg-type]
    assert out == [
        "RMW ranks #1 by risk but only #4 by beta size: the factor is volatile or moves with "
        "the other exposures."
    ]
    # Boundary of M7's rule rank_RC <= rank_beta - 2: a gap of exactly 2 emits the sentence.
    edge = risk_sentences(NAMES, betas, shares_for((2, 3, 1, 4, 5)), tags)  # type: ignore[arg-type]
    assert edge == [
        "HML ranks #1 by risk but only #3 by beta size: the factor is volatile or moves with "
        "the other exposures."
    ]


def test_t96_arithmetic_not_compounded() -> None:
    """Components add up arithmetically; compounding each separately does not reproduce y."""
    s = _dgp_sample(96)
    reg = run_regression(s)
    y = s.xret.to_numpy()
    f = s.factors.to_numpy()
    parts = np.column_stack([f * reg.betas, np.full(len(y), reg.alpha), reg.fit.resid])
    np.testing.assert_allclose(parts.sum(axis=1), y, atol=1e-15, rtol=0)
    year = pd.DatetimeIndex(s.xret.index).year.to_numpy() == 2011
    arithmetic = float(parts[year].sum())
    assert abs(arithmetic - float(y[year].sum())) <= 1e-10
    separately = float(np.prod(np.prod(1.0 + parts[year], axis=0)) - 1.0)
    together = float(np.prod(_arr(y[year]) + 1.0) - 1.0)
    assert abs(separately - together) > 1e-6


def test_t98_risk_adds_up_only_with_euler() -> None:
    s = _dgp_sample(98)
    reg = run_regression(s)
    rk = risk_contribution_for(s, reg)
    assert abs(float(rk.shares.sum()) + rk.idio_share - 1.0) <= 1e-10
    naive = reg.betas**2 * rk.sigma**2 / rk.variance
    assert abs(float(naive.sum()) + rk.idio_share - 1.0) > 1e-3
