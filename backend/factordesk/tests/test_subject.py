"""The return-subject seam and the monthly regression path (E0-T2).

* A ticker subject gives exactly the sample ``build_sample`` gives (the seam changes nothing).
* Monthly subjects: month-end stamps, consecutive months, the 36/60 floors, the factor-frame
  frequency check, the uncovered tail.
* Known-beta recovery on a monthly DGP with ``ols_hac`` (cross-checked against the statsmodels
  HAC reference call), annualised with ``periods = 12``.
"""

from __future__ import annotations

import math
from types import MappingProxyType

import numpy as np
import pandas as pd
import pytest
from numpy.typing import NDArray

from factordesk.analytics.regression import hac_lags, ols_hac, run_regression
from factordesk.analytics.sample import (
    FACTOR_CODES,
    MIN_OBS_MONTHLY,
    WARN_OBS_MONTHLY,
    AnalysisSample,
    DegenerateInputError,
    InsufficientHistoryError,
    align_returns,
    all_month_ends,
    build_sample,
    build_subject_sample,
)
from factordesk.analytics.subject import (
    ReturnSubject,
    subject_from_history,
    subject_from_monthly_returns,
)
from factordesk.tests.fixtures import reference
from factordesk.tests.fixtures.dgp import BETA, FRENCH, dgp_a, rng_for  # pyright: ignore[reportPrivateUsage]

FloatArray = NDArray[np.float64]

# Monthly DGP: plausible monthly factor moments (US 1963-2025 order of magnitude).
MU_M = np.array([0.006, 0.002, 0.003, 0.003, 0.002])
SD_M = np.array([0.045, 0.030, 0.030, 0.020, 0.020])
CORR_M = np.eye(5)
for (_i, _j), _c in {(0, 1): 0.2, (0, 2): -0.2, (2, 4): 0.6, (1, 3): -0.3, (2, 3): 0.2}.items():
    CORR_M[_i, _j] = CORR_M[_j, _i] = _c  # the correlations of the daily DGP (dgp.py)
SIGMA_M: FloatArray = np.outer(SD_M, SD_M) * CORR_M
ALPHA_M = 0.002
SIGMA_E_M = 0.02
RF_M = 0.003


def monthly_case(
    n: int, seed: int, *, start: str = "1990-01-31", extra_factor_months: int = 0
) -> tuple[pd.Series, pd.DataFrame, FloatArray]:
    """``n`` monthly returns ``r = RF + alpha + f' beta + e`` and the French-shaped factor frame.

    Returns (returns stamped at month-ends, factor frame, factor draws). The factor frame may
    run ``extra_factor_months`` beyond the returns.
    """
    rng = np.random.default_rng(seed)
    m = n + extra_factor_months
    dates = pd.date_range(start, periods=m, freq="ME", name="date")
    f = rng.multivariate_normal(MU_M, SIGMA_M, size=m)
    e = rng.normal(0.0, SIGMA_E_M, size=m)
    rf = np.full(m, RF_M)
    r = rf + ALPHA_M + f @ BETA + e
    factors = pd.DataFrame(np.column_stack([f, rf]), index=dates, columns=FRENCH)
    return pd.Series(r[:n], index=dates[:n]), factors, f


def _assert_same_sample(a: AnalysisSample, b: AnalysisSample) -> None:
    for name in ("xret", "ret", "rf"):
        pd.testing.assert_series_equal(getattr(a, name), getattr(b, name), check_exact=True)
    pd.testing.assert_frame_equal(a.factors, b.factors, check_exact=True)
    for name in (
        "requested_start",
        "requested_end",
        "factor_first_date",
        "factor_last_date",
        "excluded",
        "uncovered",
        "n_before_factors",
        "frequency",
        "warn_obs",
    ):
        assert getattr(a, name) == getattr(b, name), name


# ----------------------------------------------------------------------------- ticker seam
def test_ticker_subject_gives_the_build_sample_sample() -> None:
    d = dgp_a(rng_for(9201), n=800)
    frame = d.history.frame.drop(index=d.history.frame.index[[40, 41]])  # a multi-day return
    history = type(d.history)(d.history.ticker, frame, d.history.fetched_at, "synthetic")
    factors = d.factors.drop(index=d.factors.index[100])  # a day without a factor row
    subject = subject_from_history(history)
    assert subject.kind == "ticker" and subject.frequency == "daily" and subject.periods == 252
    assert subject.history is history and subject.label == "SYN"
    start, end = pd.Timestamp("2010-02-01").date(), pd.Timestamp("2012-12-31").date()
    for window in ((None, None), (start, end)):
        old = build_sample(history, factors, *window)
        new = build_subject_sample(subject, factors, *window)
        _assert_same_sample(old, new)
        assert {e.reason for e in new.excluded} >= {"multi_day_return", "no_factor_row"}


def test_ticker_subject_keeps_the_index_errors() -> None:
    d = dgp_a(rng_for(9202), n=600)
    frame = d.history.frame.iloc[::-1]
    history = type(d.history)("SYN", frame, d.history.fetched_at, "synthetic")
    with pytest.raises(ValueError, match="SYN prices: index must be unique and strictly"):
        subject_from_history(history)


def test_align_returns_checks_the_return_index() -> None:
    returns, factors, _ = monthly_case(40, 1)
    calendar = pd.DatetimeIndex([returns.index[0] - pd.offsets.MonthEnd(1), *returns.index])
    with pytest.raises(ValueError, match="indexed by the calendar"):
        align_returns(returns.iloc[1:], calendar, factors, min_obs=36, frequency="monthly")


# ----------------------------------------------------------------------------- monthly subject
def test_monthly_subject_stamps_month_ends_and_builds_levels() -> None:
    dates = pd.DatetimeIndex(["2020-01-31", "2020-02-28", "2020-03-31"])  # 28 Feb: a Friday
    subject = subject_from_monthly_returns(
        pd.Series([0.10, -0.05, 0.02], index=dates), label="Fund A", meta={"gross_net": "net"}
    )
    assert subject.kind == "upload" and subject.frequency == "monthly" and subject.periods == 12
    assert list(subject.calendar) == list(
        pd.DatetimeIndex(["2019-12-31", "2020-01-31", "2020-02-29", "2020-03-31"])
    )
    assert list(subject.returns.index) == list(subject.calendar[1:])
    np.testing.assert_allclose(subject.levels.to_numpy(), [100.0, 110.0, 104.5, 106.59], rtol=1e-15)
    assert subject.currency == "USD" and subject.history is None
    assert isinstance(subject.meta, MappingProxyType) and subject.meta["gross_net"] == "net"


@pytest.mark.parametrize(
    ("dates", "values", "message"),
    [
        (["2020-02-29", "2020-01-31"], [0.01, 0.01], "increasing"),
        (["2020-01-15", "2020-01-31"], [0.01, 0.01], "more than one return in 2020-01"),
        (["2020-01-31", "2020-03-31"], [0.01, 0.01], "no return for 2020-02"),
        (["2020-01-31", "2020-02-29"], [0.01, float("nan")], "2020-02 is not a number"),
        (["2020-01-31", "2020-02-29"], [-1.0, 0.01], "2020-01 is not a number above -100%"),
    ],
)
def test_monthly_subject_refuses_bad_series(
    dates: list[str], values: list[float], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        subject_from_monthly_returns(
            pd.Series(values, index=pd.DatetimeIndex(dates)), label="Fund A"
        )


def test_subject_invariants() -> None:
    returns, _, _ = monthly_case(3, 2)
    good = subject_from_monthly_returns(returns, label="Fund")
    with pytest.raises(ValueError, match="month-ends"):
        ReturnSubject(
            kind="upload",
            label="Fund",
            frequency="monthly",
            returns=pd.Series([0.01], index=pd.DatetimeIndex(["2020-01-30"])),
            calendar=pd.DatetimeIndex(["2019-12-31", "2020-01-30"]),
            levels=pd.Series([1.0, 1.01], index=pd.DatetimeIndex(["2019-12-31", "2020-01-30"])),
            source="upload",
        )
    d = dgp_a(rng_for(9203), n=10)
    with pytest.raises(ValueError, match="price history"):
        ReturnSubject(
            kind="upload",
            label="Fund",
            frequency="monthly",
            returns=good.returns,
            calendar=good.calendar,
            levels=good.levels,
            source="upload",
            history=d.history,
        )
    with pytest.raises(ValueError, match="frequency"):
        ReturnSubject(
            kind="upload",
            label="Fund",
            frequency="weekly",  # pyright: ignore[reportArgumentType]
            returns=good.returns,
            calendar=good.calendar,
            levels=good.levels,
            source="upload",
        )


# ----------------------------------------------------------------------------- monthly sample
@pytest.mark.parametrize(
    ("n", "refused", "short"),
    [(35, True, True), (36, False, True), (59, False, True), (60, False, False)],
)
def test_monthly_floors(n: int, refused: bool, short: bool) -> None:
    returns, factors, _ = monthly_case(n, 3)
    subject = subject_from_monthly_returns(returns, label="Fund")
    if refused:
        with pytest.raises(InsufficientHistoryError) as info:
            build_subject_sample(subject, factors)
        assert info.value.n == n and info.value.required == MIN_OBS_MONTHLY == 36
        assert info.value.frequency == "monthly"
        assert "35 aligned monthly observations, at least 36 required" in str(info.value)
        return
    sample = build_subject_sample(subject, factors)
    assert sample.n == n and sample.frequency == "monthly" and sample.periods == 12
    assert sample.warn_obs == WARN_OBS_MONTHLY == 60
    assert sample.short_history is short


def test_monthly_alignment_by_month() -> None:
    """Returns stamped on business month-ends align with the French month of the same name."""
    returns, factors, f = monthly_case(48, 4, extra_factor_months=0)
    business_end = pd.date_range("1990-01-31", periods=48, freq="BME")  # 1990-03-30, ...
    assert not all_month_ends(business_end)
    shifted = pd.Series(returns.to_numpy(), index=business_end)
    sample = build_subject_sample(subject_from_monthly_returns(shifted, label="Fund"), factors)
    assert sample.n == 48 and sample.excluded == ()
    np.testing.assert_array_equal(sample.factors.to_numpy(), f[:, :5])
    np.testing.assert_array_equal(sample.xret.to_numpy(), returns.to_numpy() - RF_M)


def test_monthly_uncovered_tail_and_months_before_the_factors() -> None:
    returns, factors, _ = monthly_case(60, 5)
    later = factors.iloc[6:-4]  # factor file starts 6 months late and ends 4 months early
    sample = build_subject_sample(subject_from_monthly_returns(returns, label="Fund"), later)
    assert sample.n == 50
    assert sample.n_before_factors == 6
    assert sample.uncovered.n == 4
    tail = returns.to_numpy()[-4:]
    assert sample.uncovered.compounded_return == pytest.approx(float((1.0 + tail).prod()) - 1.0)


def test_factor_frame_frequency_must_match_the_subject() -> None:
    returns, factors, _ = monthly_case(40, 6)
    monthly = subject_from_monthly_returns(returns, label="Fund")
    daily = dgp_a(rng_for(9204), n=600)
    with pytest.raises(ValueError, match="monthly French factor frame"):
        build_subject_sample(monthly, daily.factors)
    with pytest.raises(ValueError, match="daily French factor frame"):
        build_subject_sample(subject_from_history(daily.history), factors)


def test_flat_monthly_returns_are_degenerate() -> None:
    _, factors, _ = monthly_case(40, 7)
    flat = pd.Series(0.004, index=factors.index)
    with pytest.raises(DegenerateInputError, match="the return of Fund does not move"):
        build_subject_sample(subject_from_monthly_returns(flat, label="Fund"), factors)


# ----------------------------------------------------------------------------- known betas
def test_monthly_known_beta_recovery_with_ols_hac() -> None:
    """600 months of a static five-factor DGP: every coefficient within 3.5 HAC SEs of the truth.

    The fit matches the statsmodels HAC reference call (M0.5) to 1e-10, the lag rule gives
    ``floor(4 (600/100)^(2/9)) = 5``, and the annualised alpha is ``12 x`` the monthly intercept.
    """
    returns, factors, f = monthly_case(600, 20261119)
    sample = build_subject_sample(subject_from_monthly_returns(returns, label="Fund"), factors)
    reg = run_regression(sample, periods=sample.periods)
    fit = reg.fit
    truth = np.concatenate([[ALPHA_M], BETA])
    assert fit.lags == hac_lags(600) == 5
    z = (fit.params - truth) / fit.bse
    assert bool(np.all(np.abs(z) < 3.5)), z

    y = returns.to_numpy() - RF_M
    ref = reference.hac_fit(y, f, lags=5)
    np.testing.assert_allclose(fit.params, ref.params, rtol=1e-10, atol=1e-14)
    np.testing.assert_allclose(fit.bse, ref.bse, rtol=1e-10)
    direct = ols_hac(y, f)
    np.testing.assert_array_equal(direct.params, fit.params)

    assert reg.periods == 12
    assert reg.alpha_ann == pytest.approx(12 * float(fit.params[0]), rel=1e-15)
    assert reg.sigma_e_ann == pytest.approx(
        math.sqrt(12) * float(np.std(fit.resid, ddof=1)), rel=1e-15
    )
    assert abs(reg.sigma_e_ann - math.sqrt(12) * SIGMA_E_M) < 0.1 * math.sqrt(12) * SIGMA_E_M
    assert list(sample.factors.columns) == list(FACTOR_CODES)


def test_monthly_regression_at_the_36_month_floor() -> None:
    """The shortest accepted record still fits; HAC uses 3 lags (research A3)."""
    returns, factors, _ = monthly_case(36, 8)
    sample = build_subject_sample(subject_from_monthly_returns(returns, label="Fund"), factors)
    reg = run_regression(sample, periods=12)
    assert reg.fit.nobs == 36 and reg.fit.lags == 3
    assert np.isfinite(reg.fit.bse).all()
