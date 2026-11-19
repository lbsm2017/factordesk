"""World beta analytics (``analytics/world_beta.py``): hand-computed oracles and edge cases.

Identifiers TWB01-TWB18 (docs/registry/tests.jsonl). All data is synthetic.
"""

from __future__ import annotations

import dataclasses
import math

import numpy as np
import pandas as pd
import pytest
import statsmodels.api as sm  # pyright: ignore[reportMissingTypeStubs]

from factordesk.analytics.regression import hac_lags, ols_hac
from factordesk.analytics.sample import DegenerateInputError, build_sample
from factordesk.analytics.world_beta import (
    MIN_OVERLAP,
    WORDS,
    BetaEstimate,
    align_overlap,
    compare_betas,
    intervals_overlap,
    single_factor_beta,
)
from factordesk.data.prices import PriceHistory
from factordesk.tests.fixtures.dgp import (
    FloatArray,
    default_rf,
    dgp_a,
    price_history,
    rng_for,
)

N = 1500
BENCH_BETA = 1.3


@dataclasses.dataclass(frozen=True)
class Case:
    stock: PriceHistory
    bench: PriceHistory
    factors: pd.DataFrame
    dates: pd.DatetimeIndex
    x: FloatArray
    """Benchmark excess returns, one per date."""
    y: FloatArray
    """Stock excess returns, one per date."""
    rf: FloatArray


def make_case(
    test_number: int,
    *,
    n: int = N,
    beta: float = BENCH_BETA,
    noise: float = 0.004,
    bench_rows: int | None = None,
) -> Case:
    """Stock excess return = ``beta`` times the benchmark's plus noise (known beta).

    The benchmark history holds only the last ``bench_rows`` price rows when given.
    """
    rng = rng_for(test_number)
    base = dgp_a(rng, n=n)  # factors, dates and RF; independent of x
    x = rng.normal(0.0004, 0.009, size=n)
    y = beta * x + rng.normal(0.0, noise, size=n)
    rf = default_rf(n)
    stock = price_history(rf + y, base.dates, ticker="STK")
    if bench_rows is None:
        bench = price_history(rf + x, base.dates, ticker="ACWI")
    else:
        # bench_rows price rows: one base price and bench_rows - 1 returns
        k = bench_rows - 1
        bench = price_history(rf[-k:] + x[-k:], base.dates[-k:], base.dates[-k - 1], "ACWI")
    return Case(stock, bench, base.factors, base.dates, x, y, rf)


def overlap_of(case: Case):  # noqa: ANN201 - the Overlap type is only needed here
    sample = build_sample(case.stock, case.factors)
    return sample, align_overlap(sample, pd.DatetimeIndex(case.stock.frame.index), case.bench)


# ------------------------------------------------------------------------------ oracles
def test_twb01_known_beta_is_recovered_inside_its_interval() -> None:
    case = make_case(701)
    est = single_factor_beta(case.y, case.x)
    assert est.ci_low < BENCH_BETA < est.ci_high
    assert abs(est.beta - BENCH_BETA) < 0.05
    assert est.nobs == N and est.lags == hac_lags(N)
    assert 0.0 < est.r2 < 1.0 and est.correlation > 0.9


def test_twb02_stock_equal_to_the_benchmark_has_beta_one_and_r2_one() -> None:
    x = make_case(702).x
    est = single_factor_beta(x.copy(), x)
    assert est.beta == pytest.approx(1.0, abs=1e-12)
    assert est.r2 == pytest.approx(1.0, abs=1e-12)
    assert est.correlation == pytest.approx(1.0, abs=1e-12)
    assert est.alpha_annual == pytest.approx(0.0, abs=1e-9)
    assert est.se_hac < 1e-12
    assert est.alpha_t is None or math.isfinite(est.alpha_t)


def test_twb03_independent_stock_has_beta_near_zero() -> None:
    rng = rng_for(703)
    x = rng.normal(0.0, 0.009, size=3000)
    y = rng.normal(0.0, 0.012, size=3000)
    est = single_factor_beta(y, x)
    assert abs(est.beta) < 3.0 * est.se_hac
    assert est.r2 < 0.01 and abs(est.correlation) < 0.1


def test_twb04_beta_is_unchanged_by_adding_the_same_constant_to_both() -> None:
    case = make_case(704)
    base = single_factor_beta(case.y, case.x)
    shifted = single_factor_beta(case.y + 0.0007, case.x + 0.0007)
    assert shifted.beta == pytest.approx(base.beta, abs=1e-12)
    assert shifted.se_hac == pytest.approx(base.se_hac, abs=1e-12)
    assert shifted.r2 == pytest.approx(base.r2, abs=1e-12)
    # The intercept moves by c (1 - beta): alpha is not invariant, beta is.
    assert shifted.alpha_annual - base.alpha_annual == pytest.approx(
        252 * 0.0007 * (1 - base.beta), abs=1e-9
    )


def test_twb05_beta_agrees_with_numpy_polyfit_to_1e_12() -> None:
    case = make_case(705)
    est = single_factor_beta(case.y, case.x)
    slope, intercept = np.polyfit(case.x, case.y, 1)
    assert est.beta == pytest.approx(float(slope), abs=1e-12)
    assert est.alpha_annual == pytest.approx(252 * float(intercept), abs=1e-9)
    xc = case.x - case.x.mean()
    yc = case.y - case.y.mean()
    by_hand = float(xc @ yc / (xc @ xc))
    assert est.beta == pytest.approx(by_hand, abs=1e-12)
    corr = float(np.corrcoef(case.x, case.y)[0, 1])
    assert est.correlation == pytest.approx(corr, abs=1e-12)
    assert est.r2 == pytest.approx(corr**2, abs=1e-12)


def test_twb06_hac_se_is_the_existing_regression_code_and_the_statsmodels_reference() -> None:
    case = make_case(706, noise=0.01)
    est = single_factor_beta(case.y, case.x)
    existing = ols_hac(case.y, case.x[:, None])
    assert est.se_hac == float(existing.bse[1])  # the same code, not a second HAC
    lags = hac_lags(len(case.y))
    ref = sm.OLS(case.y, sm.add_constant(case.x)).fit(  # pyright: ignore[reportUnknownMemberType]
        cov_type="HAC", cov_kwds={"maxlags": lags, "use_correction": False}, use_t=False
    )
    assert est.se_hac == pytest.approx(float(ref.bse[1]), rel=1e-10)  # pyright: ignore[reportUnknownArgumentType]
    assert est.alpha_t == pytest.approx(
        float(ref.params[0] / ref.bse[0]),  # pyright: ignore[reportUnknownArgumentType]
        rel=1e-9,
    )
    assert est.ci_high - est.ci_low == pytest.approx(2 * 1.959963984540054 * est.se_hac, rel=1e-12)


def test_twb07_constant_benchmark_returns_are_refused_not_nan() -> None:
    y = make_case(707).y
    with pytest.raises(DegenerateInputError):
        single_factor_beta(y, np.full(len(y), 0.0003))


def test_twb08_non_finite_input_is_refused() -> None:
    case = make_case(708)
    x = case.x.copy()
    x[10] = np.nan
    with pytest.raises(ValueError, match="finite"):
        single_factor_beta(case.y, x)
    with pytest.raises(ValueError, match="same length|one-dimensional"):
        single_factor_beta(case.y[:-1], case.x)


# --------------------------------------------------------------------------- the overlap
def test_twb09_full_overlap_uses_every_row_of_the_sample() -> None:
    case = make_case(709)
    sample, overlap = overlap_of(case)
    assert overlap.n == sample.n == overlap.n_sample and overlap.n_without_benchmark == 0
    rf = sample.rf.to_numpy(dtype=np.float64)
    np.testing.assert_allclose(overlap.bench_xret, case.x[-sample.n :], atol=1e-12)
    np.testing.assert_allclose(overlap.stock_xret, case.y[-sample.n :], atol=1e-12)
    np.testing.assert_allclose(overlap.mkt_rf, sample.factors["mkt_rf"].to_numpy(), atol=0)
    np.testing.assert_allclose(rf, case.rf[-sample.n :], atol=0)


def test_twb10_stock_history_starting_before_the_benchmark_gives_the_common_dates() -> None:
    case = make_case(710, n=1500, bench_rows=801)  # 800 benchmark returns
    sample, overlap = overlap_of(case)
    assert overlap.n == 800 and overlap.n_without_benchmark == sample.n - 800
    assert overlap.dates[0] == case.dates[-800] and overlap.dates[-1] == case.dates[-1]
    np.testing.assert_allclose(overlap.bench_xret, case.x[-800:], atol=1e-12)
    np.testing.assert_allclose(overlap.stock_xret, case.y[-800:], atol=1e-12)


@pytest.mark.parametrize("returns", [MIN_OVERLAP, MIN_OVERLAP - 1])
def test_twb11_overlap_of_exactly_252_and_251_days(returns: int) -> None:
    case = make_case(711, bench_rows=returns + 1)
    _, overlap = overlap_of(case)
    assert overlap.n == returns


def test_twb12_a_missing_benchmark_day_removes_that_day_and_the_next_only() -> None:
    case = make_case(712)
    gap = 700
    frame = case.bench.frame.drop(case.bench.frame.index[gap])
    bench = dataclasses.replace(case.bench, frame=frame)
    sample = build_sample(case.stock, case.factors)
    overlap = align_overlap(sample, pd.DatetimeIndex(case.stock.frame.index), bench)
    missing = case.bench.frame.index[gap]
    nxt = case.bench.frame.index[gap + 1]
    assert overlap.n_without_benchmark == 2
    assert missing not in overlap.dates and nxt not in overlap.dates
    # Every other day keeps its one-day benchmark return.
    keep = np.array([d not in (missing, nxt) for d in case.dates[-sample.n :]])
    np.testing.assert_allclose(overlap.bench_xret, case.x[-sample.n :][keep], atol=1e-12)


def test_twb13_a_nan_benchmark_price_removes_its_two_returns() -> None:
    case = make_case(713)
    frame = case.bench.frame.copy()
    frame.iloc[900, frame.columns.get_loc("adj_close")] = np.nan  # type: ignore[call-overload]
    bench = dataclasses.replace(case.bench, frame=frame)
    sample = build_sample(case.stock, case.factors)
    overlap = align_overlap(sample, pd.DatetimeIndex(case.stock.frame.index), bench)
    assert overlap.n_without_benchmark == 2  # the return into and the return out of the NaN
    assert np.isfinite(overlap.bench_xret).all()


# ----------------------------------------------------------------------------- comparison
def _est(beta: float, half: float) -> BetaEstimate:
    return BetaEstimate(
        beta=beta,
        se_hac=half / 1.96,
        ci_low=beta - half,
        ci_high=beta + half,
        r2=0.8,
        correlation=0.9,
        alpha_annual=0.0,
        alpha_t=0.0,
        nobs=500,
        lags=5,
    )


def test_twb14_overlapping_intervals_read_about_the_same() -> None:
    key, text = compare_betas(_est(0.90, 0.10), _est(1.00, 0.05))  # [0.80, 1.00] and [0.95, 1.05]
    assert key == "about_the_same" and text == WORDS["about_the_same"]
    assert text.startswith("About the same")
    assert "overlap" in text


def test_twb15_touching_intervals_count_as_overlapping() -> None:
    a, b = _est(0.90, 0.10), _est(1.10, 0.10)  # [0.8, 1.0] and [1.0, 1.2]
    assert intervals_overlap(a, b)
    assert compare_betas(a, b)[0] == "about_the_same"


def test_twb16_disjoint_intervals_name_the_higher_beta() -> None:
    higher_key, higher = compare_betas(_est(1.30, 0.05), _est(1.00, 0.05))
    lower_key, lower = compare_betas(_est(0.70, 0.05), _est(1.00, 0.05))
    assert higher_key == "higher" and higher.startswith("Higher against")
    assert lower_key == "lower" and lower.startswith("Lower against")
    for text in (higher, lower):
        assert "do not overlap" in text
        assert "will" not in text and "predict" not in text  # no claim about the future


def test_twb17_comparison_is_symmetric_in_overlap() -> None:
    a, b = _est(0.9, 0.2), _est(1.0, 0.1)
    assert intervals_overlap(a, b) == intervals_overlap(b, a)


def test_twb18_alpha_and_t_are_secondary_but_correct() -> None:
    case = make_case(718)
    est = single_factor_beta(case.y + 0.0002, case.x)
    ols = ols_hac(case.y + 0.0002, case.x[:, None])
    assert est.alpha_annual == pytest.approx(252 * float(ols.params[0]), abs=1e-12)
    assert est.alpha_t == pytest.approx(float(ols.params[0] / ols.bse[0]), abs=1e-12)
