"""FF6 regression and the alpha strip (E1): ``analytics/models.py``, ``model_comparison.py``.

Synthetic data with known coefficients (a momentum beta included), built into a sample by the
real ``align_returns`` from a French-shaped frame that carries ``Mom``. Every fit is checked
against the statsmodels HAC reference call (methodology M0.5).
"""

from __future__ import annotations

import dataclasses
import math

import numpy as np
import pandas as pd
import pytest
from numpy.typing import NDArray

from factordesk.analytics.attribution import return_contribution_for, risk_contribution_for
from factordesk.analytics.model_comparison import ModelComparison, compare_models
from factordesk.analytics.models import MODEL_ORDER, MODELS, model_codes
from factordesk.analytics.regression import hac_lags, ols_hac, run_regression
from factordesk.analytics.sample import (
    FACTOR_CODES,
    SAMPLE_FLOORS,
    AnalysisSample,
    Frequency,
    align_returns,
)
from factordesk.tests.fixtures import reference

FloatArray = NDArray[np.float64]

FF6_CODES = (*FACTOR_CODES, "mom")
FRENCH_FF6 = ("Mkt-RF", "SMB", "HML", "RMW", "CMA", "Mom")
# Daily factor means and volatilities, roughly the size of the real series.
MEAN_D = np.array([0.0003, 0.0001, 0.0001, 0.0001, 0.0001, 0.0004])
SD_D = np.array([0.010, 0.005, 0.005, 0.004, 0.004, 0.007])
CORR = np.array(
    [
        [1.0, 0.2, -0.1, -0.2, -0.2, -0.1],
        [0.2, 1.0, 0.0, -0.3, 0.0, 0.0],
        [-0.1, 0.0, 1.0, 0.2, 0.5, -0.3],
        [-0.2, -0.3, 0.2, 1.0, 0.1, 0.1],
        [-0.2, 0.0, 0.5, 0.1, 1.0, 0.0],
        [-0.1, 0.0, -0.3, 0.1, 0.0, 1.0],
    ]
)
BETA = np.array([1.1, 0.3, -0.25, 0.2, 0.15, 0.45])
"""True loadings on Mkt-RF, SMB, HML, RMW, CMA and Mom."""
RF_D = 0.0001
ALPHA_D = 0.0002
SIGMA_E_D = 0.006
MONTH_DAYS = 21


def _ff6_case(
    n: int,
    seed: int,
    frequency: Frequency = "daily",
    alpha: float | None = None,
    sigma_e: float = SIGMA_E_D,
) -> tuple[pd.Series, pd.DatetimeIndex, pd.DataFrame]:
    """Returns, the subject's calendar (origin first) and an FF6 French frame.

    Monthly data scale the daily moments by 21 trading days. ``alpha`` overrides the true
    intercept per period, ``sigma_e`` the daily residual volatility.
    """
    rng = np.random.default_rng(seed)
    scale = 1 if frequency == "daily" else MONTH_DAYS
    mean, sd = MEAN_D * scale, SD_D * math.sqrt(scale)
    cov = np.outer(sd, sd) * CORR
    f = rng.multivariate_normal(mean, cov, size=n)
    e = rng.normal(0.0, sigma_e * math.sqrt(scale), size=n)
    a = ALPHA_D * scale if alpha is None else alpha
    rf = RF_D * scale
    y = a + f @ BETA + e
    if frequency == "daily":
        calendar = pd.bdate_range("1990-01-01", periods=n + 1, name="date")
    else:
        calendar = pd.date_range("1960-12-31", periods=n + 1, freq="ME", name="date")
    dates = calendar[1:]
    frame = pd.DataFrame(f, index=dates, columns=list(FRENCH_FF6))
    frame["RF"] = rf
    frame = frame.loc[:, ["Mkt-RF", "SMB", "HML", "RMW", "CMA", "RF", "Mom"]]
    returns = pd.Series(y + rf, index=dates, name="ret")
    return returns, pd.DatetimeIndex(calendar), frame


def _sample(n: int, seed: int, frequency: Frequency = "daily", **kw: float) -> AnalysisSample:
    returns, calendar, frame = _ff6_case(n, seed, frequency, **kw)
    lo, warn = SAMPLE_FLOORS[frequency]
    return align_returns(returns, calendar, frame, min_obs=lo, warn_obs=warn, frequency=frequency)


def _xy(sample: AnalysisSample, codes: tuple[str, ...]) -> tuple[FloatArray, FloatArray]:
    y = sample.xret.to_numpy(dtype=np.float64)
    return y, sample.factor_columns(codes).to_numpy(dtype=np.float64)


# ----------------------------------------------------------------------------- models
def test_model_factor_sets() -> None:
    assert MODELS["capm"] == ("mkt_rf",)
    assert MODELS["ff3"] == ("mkt_rf", "smb", "hml")
    assert MODELS["ff5"] == FACTOR_CODES == ("mkt_rf", "smb", "hml", "rmw", "cma")
    assert MODELS["ff6"] == FF6_CODES
    assert MODEL_ORDER == ("capm", "ff3", "ff5", "ff6")
    with pytest.raises(ValueError, match="unknown factor model"):
        model_codes("ff7")


def test_the_sample_carries_mom_apart_from_the_five_factors() -> None:
    s = _sample(600, 1)
    assert list(s.factors.columns) == list(FACTOR_CODES)  # unchanged for every FF5 consumer
    assert s.extra_factors is not None and list(s.extra_factors.columns) == ["mom"]
    assert s.factor_codes == FF6_CODES
    assert s.extra_factors.index.equals(s.factors.index)
    no_mom = dataclasses.replace(s, extra_factors=None)
    with pytest.raises(ValueError, match="momentum needs the FF6 factor frame"):
        no_mom.factor_columns(FF6_CODES)


def test_a_missing_mom_value_excludes_the_row_from_the_sample() -> None:
    returns, calendar, frame = _ff6_case(600, 2)
    frame.loc[frame.index[10], "Mom"] = np.nan
    s = align_returns(returns, calendar, frame)
    assert s.n == 599
    assert [(e.date, e.reason) for e in s.excluded] == [(frame.index[10].date(), "factor_missing")]


# ----------------------------------------------------------------------------- FF6 fit
def test_ff6_ols_hac_equals_statsmodels_hac() -> None:
    s = _sample(1500, 3)
    y, f = _xy(s, FF6_CODES)
    lags = hac_lags(len(y))
    ours = ols_hac(y, f)
    ref = reference.hac_fit(y, f, lags=lags)
    np.testing.assert_allclose(ours.params, ref.params, rtol=1e-10, atol=1e-14)
    np.testing.assert_allclose(ours.bse, ref.bse, rtol=1e-10)
    np.testing.assert_allclose(ours.cov, ref.cov, rtol=1e-9, atol=1e-18)
    np.testing.assert_allclose(ours.pvalues, ref.pvalues, rtol=1e-8, atol=1e-300)
    assert ours.rsquared == pytest.approx(ref.rsquared, rel=1e-12)
    assert ours.rsquared_adj == pytest.approx(ref.rsquared_adj, rel=1e-12)
    reg = run_regression(s, codes=MODELS["ff6"])
    np.testing.assert_array_equal(reg.fit.params, ours.params)
    assert reg.names == ("Mkt-RF", "SMB", "HML", "RMW", "CMA", "Mom")
    assert reg.codes == FF6_CODES
    assert len(reg.beta_tags) == 6 and set(reg.collinearity.vif) == set(reg.names)


@pytest.mark.parametrize(("frequency", "n"), [("daily", 5000), ("monthly", 720)])
def test_known_betas_including_mom_are_recovered(frequency: Frequency, n: int) -> None:
    s = _sample(n, 20261119, frequency)
    reg = run_regression(s, codes=MODELS["ff6"])
    truth = np.concatenate([[ALPHA_D * (1 if frequency == "daily" else MONTH_DAYS)], BETA])
    z = (reg.fit.params - truth) / reg.fit.bse
    assert bool(np.all(np.abs(z) < 3.5)), z
    assert abs(float(reg.betas[5]) - BETA[5]) < 0.05  # the momentum loading itself
    assert reg.beta_tags[5] == "reliable"
    ref = reference.hac_fit(*_xy(s, FF6_CODES), lags=reg.fit.lags)
    np.testing.assert_allclose(reg.fit.params, ref.params, rtol=1e-10, atol=1e-14)
    np.testing.assert_allclose(reg.fit.bse, ref.bse, rtol=1e-10)


def test_one_and_three_factor_regressions_and_their_attribution() -> None:
    s = _sample(1500, 4)
    for model in ("capm", "ff3"):
        codes = MODELS[model]
        reg = run_regression(s, codes=codes)
        ref = reference.hac_fit(*_xy(s, codes), lags=reg.fit.lags)
        np.testing.assert_allclose(reg.fit.params, ref.params, rtol=1e-10, atol=1e-14)
        np.testing.assert_allclose(reg.fit.bse, ref.bse, rtol=1e-10)
        ra = return_contribution_for(s, reg)
        assert list(ra.contributions) == list(reg.names)
        assert abs(ra.identity_residual) < 1e-14
        rk = risk_contribution_for(s, reg)
        assert abs(rk.sums_to_one_residual) < 1e-12
    assert run_regression(s, codes=MODELS["capm"]).collinearity.kappa == 1.0
    with pytest.raises(ValueError, match="unknown factor codes"):
        run_regression(s, codes=("mkt_rf", "umd"))
    with pytest.raises(ValueError, match="repeat"):
        run_regression(s, codes=("mkt_rf", "mkt_rf"))


# ----------------------------------------------------------------------------- alpha strip
def _check_strip(s: AnalysisSample, strip: ModelComparison) -> None:
    """Every row equals the statsmodels HAC fit of its model on the strip's rows."""
    y_all = s.xret.to_numpy(dtype=np.float64)
    f_all = s.factor_columns(FF6_CODES).to_numpy(dtype=np.float64)
    keep = np.isfinite(y_all) & np.isfinite(f_all).all(axis=1)
    assert strip.nobs == int(keep.sum()) and strip.lags == hac_lags(strip.nobs)
    for row in strip.models:
        f = s.factor_columns(row.codes).to_numpy(dtype=np.float64)[keep]
        ref = reference.hac_fit(y_all[keep], f, lags=strip.lags)
        assert row.alpha == pytest.approx(float(ref.params[0]), rel=1e-10, abs=1e-15)
        assert row.alpha_ann == pytest.approx(strip.periods * float(ref.params[0]), rel=1e-10)
        assert row.alpha_se_ann == pytest.approx(strip.periods * float(ref.bse[0]), rel=1e-10)
        t = float(ref.params[0] / ref.bse[0])
        assert row.alpha_t == pytest.approx(t, rel=1e-9)
        assert row.alpha_p == pytest.approx(float(ref.pvalues[0]), rel=1e-8)
        assert row.rsquared == pytest.approx(ref.rsquared, rel=1e-12)
        assert row.rsquared_adj == pytest.approx(ref.rsquared_adj, rel=1e-12)
        assert row.nobs == strip.nobs


@pytest.mark.parametrize(
    ("frequency", "n", "periods"), [("daily", 2000, 252), ("monthly", 240, 12)]
)
def test_alpha_strip_daily_and_monthly(frequency: Frequency, n: int, periods: int) -> None:
    s = _sample(n, 7, frequency)
    strip = compare_models(s)
    assert strip.periods == s.periods == periods
    assert [r.model for r in strip.models] == list(MODEL_ORDER)
    assert [r.label for r in strip.models] == ["CAPM", "FF3", "FF5", "FF6"]
    assert strip.n_dropped == 0 and strip.nobs == s.n
    assert (strip.start, strip.end) == (s.start, s.end)
    _check_strip(s, strip)
    # The FF5 row is the full-sample regression on the same rows.
    ff5 = run_regression(s)
    assert strip.by_model("ff5").alpha_ann == ff5.alpha_ann
    assert strip.by_model("ff5").rsquared == ff5.fit.rsquared
    assert strip.by_model("ff6").alpha_ann == run_regression(s, codes=MODELS["ff6"]).alpha_ann
    other = 12 if periods == 252 else 252
    with pytest.raises(ValueError, match="does not match"):
        compare_models(s, periods=other)


def test_all_models_use_identical_rows() -> None:
    """Rows where only Mom is missing are dropped for every model, not only for FF6."""
    s = _sample(1200, 11)
    assert s.extra_factors is not None
    holes = s.extra_factors.copy()
    holes.iloc[[5, 50, 500, 900], 0] = np.nan
    gappy = dataclasses.replace(s, extra_factors=holes)
    strip = compare_models(gappy)
    assert strip.n_dropped == 4 and strip.nobs == 1196
    assert {r.nobs for r in strip.models} == {1196}
    _check_strip(gappy, strip)
    # The CAPM row is not the CAPM fit on all 1200 rows: the rows are shared.
    capm_all = run_regression(s, codes=MODELS["capm"])
    assert capm_all.fit.nobs == 1200
    assert strip.by_model("capm").alpha != capm_all.alpha


def test_alpha_vanishes_once_momentum_is_added() -> None:
    """True alpha 0 and a 0.45 Mom loading: FF5 shows a large alpha, FF6 does not.

    The gap is exact OLS algebra (omitted variable): ``alpha_FF5 = alpha_FF6 + b_Mom x d``, with
    ``b_Mom`` the FF6 momentum loading and ``d`` the intercept of Mom regressed on the five
    factors. True ``d`` here is about 0.00044 a day (Mom's mean plus its negative HML link).
    """
    s = _sample(10_000, 23, alpha=0.0, sigma_e=0.002)
    strip = compare_models(s)
    ff5, ff6 = strip.by_model("ff5"), strip.by_model("ff6")
    assert ff5.alpha_t > 4.0 and ff5.alpha_tag == "reliable"
    assert abs(ff6.alpha_t) < 3.0
    assert abs(ff6.alpha_ann) < 0.25 * ff5.alpha_ann
    y, f6 = _xy(s, FF6_CODES)
    b_mom = float(ols_hac(y, f6).params[6])
    d = float(ols_hac(f6[:, 5], f6[:, :5]).params[0])
    assert ff5.alpha == pytest.approx(ff6.alpha + b_mom * d, rel=1e-9)
    assert ff5.rsquared < ff6.rsquared


def test_strip_needs_mom_for_ff6_and_validates_models() -> None:
    s = _sample(600, 31)
    no_mom = dataclasses.replace(s, extra_factors=None)
    with pytest.raises(ValueError, match="momentum needs the FF6 factor frame"):
        compare_models(no_mom)
    strip = compare_models(no_mom, models=("capm", "ff3", "ff5"))
    assert [r.model for r in strip.models] == ["capm", "ff3", "ff5"]
    with pytest.raises(ValueError, match="unknown factor model"):
        compare_models(s, models=("capm", "apt"))
    with pytest.raises(ValueError, match="twice"):
        compare_models(s, models=("ff5", "ff5"))


def test_strip_keeps_the_requested_order_and_marks_no_best_model() -> None:
    s = _sample(800, 37)
    strip = compare_models(s, models=("ff6", "capm", "ff5", "ff3"))
    assert [r.model for r in strip.models] == ["ff6", "capm", "ff5", "ff3"]
    fields = {f.name for f in dataclasses.fields(strip)} | {
        f.name for f in dataclasses.fields(strip.models[0])
    }
    assert not {"best", "rank", "best_model", "winner"} & fields
