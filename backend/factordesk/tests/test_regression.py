"""Full-sample regression tests (test-oracle T37-T46, T97, T99; methodology M0.5, M0.6, M3)."""

from __future__ import annotations

import math

import numpy as np
import pytest

from factordesk.analytics.regression import (
    alpha_sentence,
    collinearity,
    condition_number,
    design_problem,
    hac_lags,
    ols_hac,
    run_regression,
    significance_tags,
    vif,
)
from factordesk.analytics.sample import DegenerateInputError, build_sample
from factordesk.tests.fixtures.dgp import (
    BETA,
    Synthetic,
    dgp_a,
    dgp_b,
    rng_for,
    theoretical_se,
)
from factordesk.tests.fixtures.reference import (
    RefFit,
    hac_fit,
    hac_fit_missing_raise,
    ols_fit,
    vif_with_constant,
)

SWEEP = [None, *[pytest.param(s, marks=pytest.mark.slow, id=f"seed{s}") for s in range(1, 51)]]


def _reference(d: Synthetic, lags: int) -> RefFit:
    s = build_sample(d.history, d.factors)
    return hac_fit(s.xret.to_numpy(), s.factors.to_numpy(), lags)


@pytest.mark.parametrize("seed", SWEEP)
def test_t37_parameter_recovery(seed: int | None) -> None:
    d = dgp_a(rng_for(37, seed))
    reg = run_regression(build_sample(d.history, d.factors))
    truth = np.concatenate([[d.alpha], d.beta])
    err = np.abs(reg.fit.params - truth)
    assert (err <= 4 * reg.fit.bse).all(), err / reg.fit.bse
    assert (err <= 4 * theoretical_se(2520)).all(), err / theoretical_se(2520)


def test_t38_statsmodels_cross_check() -> None:
    d = dgp_a(rng_for(38))
    s = build_sample(d.history, d.factors)
    ours = run_regression(s).fit
    ref = _reference(d, 8)
    assert ours.lags == hac_lags(2520) == 8

    def close(a: object, b: object) -> None:
        np.testing.assert_allclose(
            np.asarray(a, dtype=np.float64), np.asarray(b, dtype=np.float64), rtol=1e-10, atol=0
        )

    close(ours.params, ref.params)
    close(ours.bse, ref.bse)
    close(ours.pvalues, ref.pvalues)
    close(ours.ci_low, ref.conf_int[:, 0])
    close(ours.ci_high, ref.conf_int[:, 1])
    close(ours.rsquared, ref.rsquared)
    close(ours.rsquared_adj, ref.rsquared_adj)
    close(ours.cov, ref.cov)


def test_t39_lag_rule() -> None:
    expected = {100: 4, 126: 4, 252: 4, 504: 5, 750: 6, 756: 6, 1000: 6, 2520: 8, 5000: 9}
    assert {m: hac_lags(m) for m in expected} == expected


def _hac_ols_ratio(d: Synthetic) -> tuple[float, float, float, float]:
    s = build_sample(d.history, d.factors)
    fit = ols_hac(s.xret.to_numpy(), s.factors.to_numpy())
    bse_ols = ols_fit(s.xret.to_numpy(), s.factors.to_numpy()).bse
    return (
        float(fit.bse[1] / bse_ols[1]),
        float(fit.params[1]),
        float(fit.bse[1]),
        float(bse_ols[1]),
    )


def test_t41_hac_exceeds_ols_under_serial_correlation() -> None:
    ratio, *_ = _hac_ols_ratio(dgp_b(rng_for(41)))
    assert 1.10 <= ratio <= 1.40


@pytest.mark.slow
def test_t40_hac_coverage() -> None:
    rng = rng_for(40)
    reps = 1000
    hit_hac = np.zeros(2)
    hit_ols = np.zeros(2)
    for _ in range(reps):
        d = dgp_b(rng)
        s = build_sample(d.history, d.factors)
        y, f = s.xret.to_numpy(), s.factors.to_numpy()
        fit = ols_hac(y, f)
        x = np.column_stack([np.ones(len(y)), f])
        sigma2 = float(fit.resid @ fit.resid) / (len(y) - 6)
        bse_ols = np.sqrt(np.diag(sigma2 * np.linalg.inv(x.T @ x)))
        for slot, j in enumerate((1, 3)):  # beta_mkt, beta_hml
            hit_hac[slot] += abs(fit.params[j] - BETA[j - 1]) <= 1.959964 * fit.bse[j]
            hit_ols[slot] += abs(fit.params[j] - BETA[j - 1]) <= 1.959964 * bse_ols[j]
    cov_hac, cov_ols = hit_hac / reps, hit_ols / reps
    assert ((cov_hac >= 0.910) & (cov_hac <= 0.975)).all(), cov_hac
    assert (cov_hac - cov_ols >= 0.03).all(), (cov_hac, cov_ols)


def test_t42_annualisation() -> None:
    d = dgp_a(rng_for(42))
    reg = run_regression(build_sample(d.history, d.factors))
    fit = reg.fit
    rel = 1e-12
    assert reg.alpha_ann == pytest.approx(252 * fit.params[0], rel=rel)
    assert reg.alpha_se_ann == pytest.approx(252 * fit.bse[0], rel=rel)
    assert (reg.alpha_ann / reg.alpha_se_ann) == pytest.approx(fit.zvalues[0], rel=rel)
    assert fit.rsquared_adj == pytest.approx(
        1 - (1 - fit.rsquared) * (fit.nobs - 1) / (fit.nobs - 6), rel=rel
    )
    assert reg.sigma_e_ann == pytest.approx(
        math.sqrt(252) * float(np.std(fit.resid, ddof=1)), rel=rel
    )


def test_t43_significance_tags() -> None:
    assert significance_tags([1e-6, 0.03, 0.40, 0.50, 0.70]) == [
        "reliable",
        "noise",
        "noise",
        "noise",
        "noise",
    ]
    assert significance_tags([0.01, 0.02, 0.03, 0.04, 0.05]) == ["reliable"] * 5


def test_t44_large_insignificant_alpha_sentence() -> None:
    present = alpha_sentence(0.08, 0.30, 0.20, 2520, 0.0777)
    assert present is not None and "+8.00%" in present and "7.77%" in present
    assert "10.0 years" in present
    assert alpha_sentence(0.02, 0.30, 0.20, 2520, 0.0777) is None
    assert alpha_sentence(0.08, 0.01, 0.20, 2520, 0.0777) is None


def test_t44_boundaries() -> None:
    """M3.2: shown when |alpha_ann| >= 0.03 and p >= 0.05 (both boundaries inclusive)."""
    assert alpha_sentence(0.03, 0.30, 0.20, 2520, 0.0777) is not None
    assert alpha_sentence(-0.03, 0.30, 0.20, 2520, 0.0777) is not None
    assert alpha_sentence(0.08, 0.05, 0.20, 2520, 0.0777) is not None
    assert alpha_sentence(0.0299, 0.30, 0.20, 2520, 0.0777) is None


def _orthonormal_factors(test_number: int) -> np.ndarray:
    d = dgp_a(rng_for(test_number))
    q, _ = np.linalg.qr(d.f - d.f.mean(axis=0))
    return q


def _with_pair_correlation(q: np.ndarray, r: float) -> np.ndarray:
    """HML/CMA with sample correlation exactly ``r``; every other pair uncorrelated."""
    f = q.copy()
    f[:, 4] = r * q[:, 2] + math.sqrt(1.0 - r * r) * q[:, 4]
    return f


def test_t45_vif_orthogonal_factors() -> None:
    q = _orthonormal_factors(45)
    np.testing.assert_allclose(vif(q), np.ones(5), atol=1e-12, rtol=0)
    assert abs(condition_number(q) - 1.0) <= 1e-12


def test_t45_condition_number_known_correlation() -> None:
    """Eigenvalues 1.6, 0.4, 1, 1, 1 give kappa = sqrt(1.6/0.4) = 2 (kappa^2 = 4 would fail)."""
    f = _with_pair_correlation(_orthonormal_factors(45), 0.6)
    corr = np.corrcoef(f, rowvar=False)
    assert corr[2, 4] == pytest.approx(0.6, abs=1e-12)
    assert condition_number(f) == pytest.approx(2.0, abs=1e-12)


def test_t46_pair_threshold() -> None:
    names = ("Mkt-RF", "SMB", "HML", "RMW", "CMA")
    q = _orthonormal_factors(46)
    listed = collinearity(_with_pair_correlation(q, 0.65), names).high_corr_pairs
    assert [(a, b) for a, b, _ in listed] == [("HML", "CMA")]
    assert listed[0][2] == pytest.approx(0.65, abs=1e-12)
    assert collinearity(_with_pair_correlation(q, 0.55), names).high_corr_pairs == ()


# ----------------------------------------------------------------------------- design guard
@pytest.mark.parametrize(
    ("case", "needle"),
    [
        ("zero", "zero variance"),
        ("constant", "zero variance"),
        ("duplicate", "linear combination"),
        ("near_duplicate", "linear combination"),
    ],
)
def test_t126_design_guard_names_the_factor(case: str, needle: str) -> None:
    rng = rng_for(126)
    d = dgp_a(rng)
    f = d.f.copy()
    if case == "zero":
        f[:, 4] = 0.0
    elif case == "constant":
        f[:, 4] = 0.001
    elif case == "duplicate":
        f[:, 4] = f[:, 2]
    else:
        f[:, 4] = f[:, 2] + rng.standard_normal(len(f)) * f[:, 2].std() * 1e-4
    y = d.ret - d.rf
    with pytest.raises(DegenerateInputError, match=needle) as info:
        ols_hac(y, f)
    assert "CMA" in str(info.value)
    problem = design_problem(f, ("Mkt-RF", "SMB", "HML", "RMW", "CMA"))
    assert problem is not None and "CMA" in problem


def test_design_guard_passes_real_like_factors() -> None:
    d = dgp_a(rng_for(126))
    assert design_problem(d.f, ("Mkt-RF", "SMB", "HML", "RMW", "CMA")) is None


def test_constant_dependent_variable_is_refused() -> None:
    d = dgp_a(rng_for(126))
    with pytest.raises(DegenerateInputError, match="does not vary"):
        ols_hac(np.full(len(d.f), -0.0001), d.f)


def test_reference_call_with_missing_raise_is_identical() -> None:
    """M0.5: ``missing="raise"`` and an explicit Bartlett kernel change no number."""
    d = dgp_a(rng_for(38))
    s = build_sample(d.history, d.factors)
    a = hac_fit(s.xret.to_numpy(), s.factors.to_numpy(), 8)
    b = hac_fit_missing_raise(s.xret.to_numpy(), s.factors.to_numpy(), 8)
    np.testing.assert_array_equal(a.params, b.params)
    np.testing.assert_array_equal(a.bse, b.bse)
    ours = run_regression(s).fit
    np.testing.assert_allclose(ours.pvalues, b.pvalues, rtol=1e-10)


def test_t46_vif_collinear_factors() -> None:
    rng = rng_for(46)
    d = dgp_a(rng)
    f = d.f.copy()
    hml_scaled = (f[:, 2] - f[:, 2].mean()) / f[:, 2].std()
    noise = rng.standard_normal(len(f))
    f[:, 4] = 0.004 * (0.95 * hml_scaled + math.sqrt(1 - 0.9025) * noise)
    ours = vif(f)
    for j in range(5):
        aux = ols_fit(f[:, j], np.delete(f, j, axis=1))
        direct = 1.0 / (1.0 - aux.rsquared)
        assert ours[j] == pytest.approx(direct, rel=1e-10)
        assert ours[j] == pytest.approx(vif_with_constant(f, j), rel=1e-10)
    col = collinearity(f, ("Mkt-RF", "SMB", "HML", "RMW", "CMA"))
    assert any("HML" in w and "CMA" in w and "overlap strongly" in w for w in col.warnings)
    strong = [w for w in col.warnings if w.startswith("Strong collinearity")]
    assert strong and "HML" in strong[0] and "CMA" in strong[0], (col.vif, col.warnings)
    assert any(a == "HML" and b == "CMA" for a, b, _ in col.high_corr_pairs)


@pytest.mark.parametrize("seed", SWEEP)
def test_t97_rf_is_subtracted(seed: int | None) -> None:
    rf = np.full(2520, 0.0004)
    d = dgp_a(rng_for(97, seed), alpha=0.0, sigma_e=0.004, rf=rf)
    s = build_sample(d.history, d.factors)
    reg = run_regression(s)
    assert abs(reg.alpha) <= 4 * reg.fit.bse[0]
    if seed is None:
        # Oracle bound |z| < 3 (P(|Z| > 3) = 0.27%, so it is not part of the seed sweep).
        assert abs(reg.fit.zvalues[0]) < 3
        # The mistake this guards against: regressing raw returns puts RF into alpha
        # (expected z about 5, so a raw-return pipeline fails the bound above).
        raw = ols_hac(s.ret.to_numpy(), s.factors.to_numpy())
        assert raw.zvalues[0] > 3


@pytest.mark.parametrize("seed", SWEEP)
def test_t99_intercept_recovered(seed: int | None) -> None:
    d = dgp_a(rng_for(99, seed), alpha=0.001)
    reg = run_regression(build_sample(d.history, d.factors))
    truth = np.concatenate([[0.001], d.beta])
    assert (np.abs(reg.fit.params - truth) <= 4 * reg.fit.bse).all()


def test_tags_and_interpretation_only_for_reliable() -> None:
    d = dgp_a(rng_for(43), beta=np.array([1.0, 0.0, 0.0, 0.0, 0.0]))
    reg = run_regression(build_sample(d.history, d.factors))
    for tag, text in zip(reg.beta_tags, reg.interpretations, strict=True):
        assert (text is not None) == (tag == "reliable")
    assert reg.beta_tags[0] == "reliable"
