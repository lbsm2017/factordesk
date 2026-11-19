"""The ``periods`` argument (observations a year) of the annualised statistics (E0-T2).

The default is 252, so daily results are unchanged. ``periods = 12`` (monthly data) must scale
every annualised figure by the textbook rule: arithmetic means and alpha by ``periods``,
volatilities by ``sqrt(periods)``, the compound growth rate by the exponent ``periods / n``.
Nothing that is not annualised (betas, standard errors of the betas, R²) may move.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from factordesk.analytics.attribution import return_contribution_for, risk_contribution_for
from factordesk.analytics.performance import InsufficientObservations, performance_stats
from factordesk.analytics.regression import A, alpha_sentence, run_regression
from factordesk.analytics.sample import AnalysisSample, build_sample
from factordesk.tests.fixtures.dgp import dgp_a, rng_for


def _sample() -> AnalysisSample:
    case = dgp_a(rng_for(9101), n=600)
    return build_sample(case.history, case.factors)


def test_regression_periods_scale_only_annualised_figures() -> None:
    sample = _sample()
    daily = run_regression(sample)
    monthly = run_regression(sample, periods=12)
    assert daily.periods == A == 252
    assert monthly.periods == 12
    np.testing.assert_array_equal(daily.fit.params, monthly.fit.params)
    np.testing.assert_array_equal(daily.fit.bse, monthly.fit.bse)
    assert daily.fit.rsquared == monthly.fit.rsquared
    a = float(daily.fit.params[0])
    assert monthly.alpha_ann == pytest.approx(12 * a, rel=1e-15)
    assert monthly.alpha_se_ann == pytest.approx(12 * float(daily.fit.bse[0]), rel=1e-15)
    assert monthly.alpha_ci_ann[0] == pytest.approx(12 * float(daily.fit.ci_low[0]), rel=1e-15)
    assert monthly.alpha_ci_ann[1] == pytest.approx(12 * float(daily.fit.ci_high[0]), rel=1e-15)
    sd_e = float(np.std(daily.fit.resid, ddof=1))
    assert monthly.sigma_e_ann == pytest.approx(math.sqrt(12) * sd_e, rel=1e-15)
    assert daily.sigma_e_ann == pytest.approx(math.sqrt(252) * sd_e, rel=1e-15)


def test_regression_rejects_non_positive_periods() -> None:
    with pytest.raises(ValueError, match="periods"):
        run_regression(_sample(), periods=0)


def test_alpha_sentence_counts_years_with_periods() -> None:
    text = alpha_sentence(0.05, 0.4, 0.2, 48, 0.06, periods=12)
    assert text is not None and "over 4.0 years" in text
    text = alpha_sentence(0.05, 0.4, 0.2, 504, 0.06)
    assert text is not None and "over 2.0 years" in text


def test_attribution_periods() -> None:
    sample = _sample()
    reg = run_regression(sample, periods=12)
    ra = return_contribution_for(sample, reg)
    f = sample.factors.to_numpy(dtype=np.float64)
    expected = 12 * reg.betas * f.mean(axis=0)
    np.testing.assert_allclose(list(ra.contributions.values()), expected, rtol=1e-14)
    assert ra.alpha_ann == pytest.approx(12 * reg.alpha, rel=1e-15)
    assert ra.total_ann == pytest.approx(12 * float(sample.xret.mean()), rel=1e-14)
    assert abs(ra.identity_residual) < 1e-14
    rk = risk_contribution_for(sample, reg)
    assert rk.periods == 12
    assert rk.vol_ann == pytest.approx(math.sqrt(12 * float(sample.xret.var(ddof=1))), rel=1e-12)
    np.testing.assert_allclose(rk.sigma_ann, math.sqrt(12) * f.std(axis=0, ddof=1), rtol=1e-12)
    assert abs(rk.sums_to_one_residual) < 1e-12


def test_performance_periods_twelve_hand_computed() -> None:
    """Thirty-six months of +1% then -0.5% alternating; RF 0.2% a month."""
    dates = pd.date_range("2020-01-31", periods=36, freq="ME")
    r = np.tile([0.01, -0.005], 18)
    ret = pd.Series(r, index=dates)
    rf = pd.Series(0.002, index=dates)
    res = performance_stats(ret, rf, periods=12, min_obs=36)
    growth = float(np.prod(1.0 + r))
    assert res.years == 3.0
    assert res.cagr == pytest.approx(growth ** (12 / 36) - 1.0, rel=1e-14)
    assert res.cumulative_return == pytest.approx(growth - 1.0, rel=1e-14)
    assert res.mean_return_annual == pytest.approx(12 * 0.0025, rel=1e-14)
    sd = float(np.std(r, ddof=1))
    assert res.volatility_annual == pytest.approx(math.sqrt(12) * sd, rel=1e-14)
    x = r - 0.002
    sr = float(np.mean(x) / np.std(x, ddof=1))
    assert res.sharpe_daily == pytest.approx(sr, rel=1e-14)
    assert res.sharpe_annual == pytest.approx(math.sqrt(12) * sr, rel=1e-14)
    se = math.sqrt(12) * math.sqrt((1 + sr * sr / 2) / 36)
    assert res.sharpe_se_iid == pytest.approx(se, rel=1e-14)
    assert res.mean_excess_annual == pytest.approx(12 * float(np.mean(x)), rel=1e-14)


def test_performance_min_obs_is_the_callers() -> None:
    dates = pd.date_range("2020-01-31", periods=30, freq="ME")
    ret = pd.Series(np.tile([0.01, -0.005], 15), index=dates)
    with pytest.raises(InsufficientObservations) as info:
        performance_stats(ret, pd.Series(0.0, index=dates), periods=12, min_obs=36)
    assert info.value.n == 30 and info.value.required == 36
