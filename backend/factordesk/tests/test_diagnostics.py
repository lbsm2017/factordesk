"""Residual diagnostics, quality gate and 5-day estimate (test-oracle T47, T120-T125; M3.5-M3.6)."""

from __future__ import annotations

import dataclasses
import math
import warnings
from datetime import UTC, datetime

import numpy as np
import pytest

from factordesk.analytics.diagnostics import (
    MIN_BLOCKS,
    apply_gate,
    block_sums,
    combine_tags,
    gate_fires,
    lag1_autocorrelation,
    multi_day_regression,
    noise_share,
    quality_gate,
    residual_diagnostics,
    robust_breusch_godfrey,
)
from factordesk.analytics.regression import hac_lags, run_regression
from factordesk.analytics.sample import FACTOR_CODES, AnalysisSample, build_sample
from factordesk.pipeline import build_report
from factordesk.report import render_report_html
from factordesk.tests.fixtures.dgp import (
    BETA,
    StaticProvider,
    Synthetic,
    dgp_a,
    dgp_g,
    dgp_n,
    rng_for,
)
from factordesk.tests.fixtures.reference import hac_fit, residual_reference


def _sample(d: Synthetic, min_obs: int = 504) -> AnalysisSample:
    return build_sample(d.history, d.factors, min_obs=min_obs)


def _resid_and_factors(d: Synthetic) -> tuple[np.ndarray, np.ndarray]:
    s = _sample(d)
    reg = run_regression(s)
    return reg.fit.resid, s.factors.loc[:, list(FACTOR_CODES)].to_numpy()


# ----------------------------------------------------------------------------- T47
def test_t47_diagnostics_equal_statsmodels_and_emit_no_warning() -> None:
    e, f = _resid_and_factors(dgp_a(rng_for(47)))
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        diag = residual_diagnostics(e, f)
    ref = residual_reference(e, f)

    def rel(a: float, b: float, tol: float = 1e-12) -> None:
        assert a == pytest.approx(b, rel=tol, abs=0.0), (a, b)

    rel(diag.lag1.rho, ref.acf1)
    num = float(np.sum((e[1:] * e[:-1]) ** 2))
    rel(diag.lag1.se, math.sqrt(num) / float(e @ e))
    rel(diag.lag1.z, diag.lag1.rho / diag.lag1.se)
    rel(diag.ljung_box.statistic, ref.ljung_box_stat)
    rel(diag.ljung_box.p, ref.ljung_box_p)
    assert diag.ljung_box.df == 10
    rel(diag.arch_lm.statistic, ref.arch_lm)
    rel(diag.arch_lm.p, ref.arch_lm_p)
    assert diag.arch_lm.df == 5
    rel(diag.jarque_bera.statistic, ref.jb_stat)
    rel(diag.jarque_bera.p, ref.jb_p)
    rel(diag.skew, ref.jb_skew)
    rel(diag.kurtosis, ref.jb_kurtosis)
    rel(diag.durbin_watson, ref.durbin_watson)
    rel(diag.robust_bg.statistic, ref.robust_bg_stat, 1e-10)
    rel(diag.robust_bg.p, ref.robust_bg_p, 1e-10)
    assert diag.robust_bg.df == 10
    assert set(diag.readings) == {
        "lag1_autocorrelation",
        "ljung_box",
        "robust_breusch_godfrey",
        "arch_lm",
        "jarque_bera",
        "durbin_watson",
    }
    assert all(diag.readings.values())
    assert "HAC" in diag.note


def test_t47_robust_bg_standalone_matches_reference() -> None:
    e, f = _resid_and_factors(dgp_n(rng_for(47)))
    stat = robust_breusch_godfrey(e, f, lags=10)
    ref = residual_reference(e, f)
    assert stat.statistic == pytest.approx(ref.robust_bg_stat, rel=1e-10)
    assert stat.p == pytest.approx(ref.robust_bg_p, rel=1e-10, abs=1e-300)


def test_lag1_readings_follow_sign_and_significance() -> None:
    noisy, f = _resid_and_factors(dgp_n(rng_for(47)))
    reading = residual_diagnostics(noisy, f).readings["lag1_autocorrelation"]
    assert "reverses the next day" in reading
    clean, f2 = _resid_and_factors(dgp_a(rng_for(47)))
    lag = lag1_autocorrelation(clean)
    reading2 = residual_diagnostics(clean, f2).readings["lag1_autocorrelation"]
    if lag.p >= 0.05:
        assert "No clear day-to-day pattern" in reading2


# ----------------------------------------------------------------------------- T120 (slow)
@pytest.mark.slow
def test_t120_robust_bg_size_under_garch() -> None:
    rng = rng_for(120)
    reps = 300
    bg_rej = 0
    arch_rej = 0
    for _ in range(reps):
        e, f = _resid_and_factors(dgp_g(rng))
        diag = residual_diagnostics(e, f)
        bg_rej += diag.robust_bg.p < 0.05
        arch_rej += diag.arch_lm.p < 0.05
    rate = bg_rej / reps
    assert 0.006 <= rate <= 0.094, rate
    assert arch_rej / reps >= 0.90, arch_rej / reps


# ----------------------------------------------------------------------------- T121
def test_t121_gate_rule_boundaries() -> None:
    assert gate_fires(-0.21, -5.0)
    assert not gate_fires(-0.20, -50.0)  # strict on rho
    assert not gate_fires(-0.5, -4.0)  # strict on z
    assert not gate_fires(-0.5, -3.9)
    assert not gate_fires(-0.19, -10.0)
    assert noise_share(-0.4) == pytest.approx(0.8, abs=1e-15)
    assert noise_share(-0.6) == 1.0
    assert noise_share(0.1) == 0.0


# ----------------------------------------------------------------------------- T122
def test_t122_gate_on_known_noise() -> None:
    d = dgp_n(rng_for(122))
    s = _sample(d)
    reg = run_regression(s)
    f = s.factors.loc[:, list(FACTOR_CODES)].to_numpy()
    diag = residual_diagnostics(reg.fit.resid, f)
    assert abs(diag.lag1.rho - (-1.0 / 3.0)) <= 4 * diag.lag1.se
    gate = quality_gate(diag.lag1)
    assert gate.fired
    five = multi_day_regression(s)
    assert five is not None
    err = np.abs(five.fit.params[1:] - BETA)
    assert (err <= 4 * five.fit.bse[1:]).all(), err / five.fit.bse[1:]


def test_t122_gate_quiet_without_noise() -> None:
    d = dgp_a(rng_for(122))
    e, f = _resid_and_factors(d)
    gate = quality_gate(residual_diagnostics(e, f).lag1)
    assert not gate.fired
    assert gate.message is None


# ----------------------------------------------------------------------------- T123
def test_t123_block_construction_and_reference() -> None:
    d = dgp_a(rng_for(123), n=2523)
    s = _sample(d)
    y = s.xret.to_numpy()
    f = s.factors.loc[:, list(FACTOR_CODES)].to_numpy()
    yb, fb, unused = block_sums(y, f, 5)
    assert len(yb) == 504 and unused == 3
    for b in (0, 1, 250, 503):
        assert yb[b] == pytest.approx(float(y[5 * b : 5 * b + 5].sum()), abs=1e-15)
        np.testing.assert_allclose(fb[b], f[5 * b : 5 * b + 5].sum(axis=0), atol=1e-15, rtol=0)
    five = multi_day_regression(s)
    assert five is not None
    assert five.n_blocks == 504 and five.n_unused == 3 and five.fit.lags == hac_lags(504) == 5
    ref = hac_fit(yb, fb, 5)
    np.testing.assert_allclose(five.fit.params, ref.params, rtol=1e-10)
    np.testing.assert_allclose(five.fit.bse, ref.bse, rtol=1e-10)
    np.testing.assert_allclose(five.fit.pvalues, ref.pvalues, rtol=1e-10)
    assert five.alpha_ann == pytest.approx(252 / 5 * float(five.fit.params[0]), rel=1e-15)
    assert five.alpha_se_ann == pytest.approx(252 / 5 * float(five.fit.bse[0]), rel=1e-15)
    assert five.first_date == s.start
    assert five.last_date == s.xret.index[5 * 504 - 1].date()


def test_t123_minimum_blocks_and_anchoring() -> None:
    d = dgp_a(rng_for(123), n=499)
    s = _sample(d, min_obs=1)
    assert s.n // 5 < MIN_BLOCKS
    assert multi_day_regression(s) is None
    long = dgp_a(rng_for(123), n=1005)
    y = long.ret - long.rf
    yb_short, _, _ = block_sums(y[:1000], long.f[:1000], 5)
    yb_long, _, _ = block_sums(y, long.f, 5)
    np.testing.assert_array_equal(yb_long[:200], yb_short)


# ----------------------------------------------------------------------------- T124
def test_t124_tag_conjunction() -> None:
    assert combine_tags(["reliable"], ["noise"]) == ["noise"]
    assert combine_tags(["reliable"], ["reliable"]) == ["reliable"]
    assert combine_tags(["noise"], ["reliable"]) == ["noise"]
    r, n = "reliable", "noise"
    assert combine_tags([r, r, n, r, n], [r, n, r, r, n]) == [r, n, n, r, n]


def test_t124_apply_gate_combines_alpha_and_betas() -> None:
    d = dgp_n(rng_for(124))
    s = _sample(d)
    reg = run_regression(s)
    five = multi_day_regression(s)
    assert five is not None
    combined = apply_gate(reg, five)
    expected_alpha = (
        "reliable"
        if float(reg.fit.pvalues[0]) < 0.05 and float(five.fit.pvalues[0]) < 0.05
        else "noise"
    )
    assert combined.alpha_tag == expected_alpha
    assert list(combined.beta_tags) == combine_tags(list(reg.beta_tags), list(five.beta_tags))
    for tag, text in zip(combined.beta_tags, combined.interpretations, strict=True):
        assert (text is not None) == (tag == "reliable")
    # Daily numbers are untouched (D21): only tags and readings change.
    assert combined.fit is reg.fit and combined.alpha_ann == reg.alpha_ann


def test_t124_pure_alpha_cases() -> None:
    d = dgp_a(rng_for(124))
    s = _sample(d)
    reg = run_regression(s)
    five = multi_day_regression(s)
    assert five is not None

    def with_p(daily: float, multi: float) -> str:
        fit_d = dataclasses.replace(reg.fit, pvalues=np.r_[daily, reg.fit.pvalues[1:]])
        fit_m = dataclasses.replace(five.fit, pvalues=np.r_[multi, five.fit.pvalues[1:]])
        r = dataclasses.replace(reg, fit=fit_d, alpha_tag="reliable" if daily < 0.05 else "noise")
        m = dataclasses.replace(five, fit=fit_m, alpha_tag="reliable" if multi < 0.05 else "noise")
        return apply_gate(r, m).alpha_tag

    assert with_p(0.01, 0.20) == "noise"
    assert with_p(0.01, 0.04) == "reliable"
    assert with_p(0.06, 0.001) == "noise"


# ----------------------------------------------------------------------------- T125
NOW = datetime(2026, 11, 18, 15, 0, tzinfo=UTC)


def test_t125_gate_in_the_report() -> None:
    d = dgp_n(rng_for(125))
    rep = build_report("syn", StaticProvider(d.history), factors=d.factors, now=NOW)
    assert rep.warnings[0].code == "residual_reversal"
    msg = rep.warnings[0].message
    rd = rep.residual_diagnostics
    assert rd.status == "ok" and rd.lag1_autocorrelation is not None and rd.lag1_z is not None
    assert f"{rd.lag1_autocorrelation:+.2f}" in msg and f"{rd.lag1_z:+.1f}" in msg
    assert rep.quality_gate.fired is True and rep.quality_gate.noise_share is not None
    assert f"{rep.quality_gate.noise_share:.0%}" in msg
    five = rep.five_day_regression
    assert five.status == "ok" and five.alpha_p is not None and five.n_blocks == 504
    assert rep.regression.alpha_p is not None
    both = rep.regression.alpha_p < 0.05 and five.alpha_p < 0.05
    assert rep.regression.alpha_tag == ("reliable" if both else "noise")
    page = render_report_html(rep)
    assert "Daily price changes partly reverse the next day" in page
    assert "5-day estimate" in page and "Residual diagnostics" in page


def test_t125_no_gate_without_noise() -> None:
    d = dgp_a(rng_for(125))
    rep = build_report("syn", StaticProvider(d.history), factors=d.factors, now=NOW)
    assert "residual_reversal" not in {w.code for w in rep.warnings}
    assert rep.quality_gate.fired is False
    assert rep.five_day_regression.status == "not_applicable"
    assert rep.five_day_regression.reason
    page = render_report_html(rep)
    assert "Daily price changes partly reverse" not in page
    assert "Residual diagnostics" in page


def test_t126_exact_fit_has_no_diagnostics_and_no_warning() -> None:
    """A stock that is an exact combination of the factors leaves only rounding noise (M3.5)."""
    d = dgp_a(rng_for(126), alpha=0.0, sigma_e=0.0)
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        rep = build_report("syn", StaticProvider(d.history), factors=d.factors, now=NOW)
    assert rep.regression.r2 is not None and rep.regression.r2 > 1 - 1e-12
    for section in (rep.residual_diagnostics, rep.quality_gate, rep.five_day_regression):
        assert section.status == "not_applicable" and section.reason
    assert "exactly" in (rep.residual_diagnostics.reason or "")
    assert rep.quality_gate.fired is None
    assert "residual_reversal" not in {w.code for w in rep.warnings}
    assert "Residual diagnostics" in render_report_html(rep)
