"""Historical performance statistics: hand-computed oracles, edge cases, properties.

Every oracle is worked by hand in a comment and again by a plain-python loop in the test, so the
vectorised code is checked against two independent computations. IDs TP01-TP24.
"""

from __future__ import annotations

import math
from datetime import date

import numpy as np
import pandas as pd
import pytest

from factordesk.analytics.performance import (
    MIN_OBS,
    SD_FLOOR,
    InsufficientObservations,
    compound_path,
    drawdown_episodes,
    performance_stats,
    top_episodes,
)

A = 252


def _index(n: int, start: str = "2020-01-02") -> pd.DatetimeIndex:
    return pd.bdate_range(start, periods=n, name="date")


def _series(
    values: list[float] | np.ndarray, rf: float | list[float] = 0.0
) -> tuple[pd.Series, pd.Series]:
    idx = _index(len(values))
    ret = pd.Series(np.asarray(values, dtype=float), index=idx, name="ret")
    rfs = pd.Series(rf if isinstance(rf, list) else [rf] * len(values), index=idx, name="rf")
    return ret, rfs


def _dates(n: int) -> list[date]:
    """``n`` consecutive business dates (path points)."""
    return [d.date() for d in pd.bdate_range("2019-12-31", periods=n)]


def _plain_drawdowns(
    ret: list[float],
) -> list[tuple[float, int, int, int | None]]:
    """Independent loop: (depth, peak_i, trough_i, recovery_i) of every underwater episode."""
    w = [1.0]
    for r in ret:
        w.append(w[-1] * (1.0 + r))
    out: list[tuple[float, int, int, int | None]] = []
    peak_i, trough_i = 0, None
    for i in range(1, len(w)):
        if w[i] >= w[peak_i]:
            if trough_i is not None:
                out.append((w[trough_i] / w[peak_i] - 1.0, peak_i, trough_i, i))
                trough_i = None
            peak_i = i
        elif trough_i is None or w[i] < w[trough_i]:
            trough_i = i
    if trough_i is not None:
        out.append((w[trough_i] / w[peak_i] - 1.0, peak_i, trough_i, None))
    return out


# ------------------------------------------------------------------------- TP01-TP04 drawdowns
# Hand oracle. r = [+10%, -20%, +30%, +10%, -50%, +30%] gives the path
#   1, 1.1, 0.88, 1.144, 1.2584, 0.6292, 0.81796.
# Episode 1: peak 1.1 (point 1), trough 0.88 (point 2), depth 0.88/1.1 - 1 = -0.2, the path
#   regains 1.1 at point 3 (1.144): 1 day down, 1 day back.
# Episode 2: peak 1.2584 (point 4), trough 0.6292 (point 5), depth -0.5, never regained
#   (0.81796 < 1.2584): open, 1 day down.
R6 = [0.10, -0.20, 0.30, 0.10, -0.50, 0.30]


def test_tp01_path_and_episodes_by_hand() -> None:
    path = compound_path(np.array(R6))
    assert path.tolist() == pytest.approx([1, 1.1, 0.88, 1.144, 1.2584, 0.6292, 0.81796])
    dates = _dates(len(path))
    eps = drawdown_episodes(path, dates)
    assert len(eps) == 2
    first, second = eps
    assert first.depth == pytest.approx(-0.2)
    assert (first.peak_date, first.trough_date, first.recovery_date) == (
        dates[1],
        dates[2],
        dates[3],
    )
    assert (first.days_peak_to_trough, first.days_trough_to_recovery) == (1, 1)
    assert second.depth == pytest.approx(-0.5)
    assert (second.peak_date, second.trough_date, second.recovery_date) == (
        dates[4],
        dates[5],
        None,
    )
    assert (second.days_peak_to_trough, second.days_trough_to_recovery) == (1, None)


def test_tp02_top_episodes_are_deepest_first_and_capped() -> None:
    path = compound_path(np.array(R6))
    eps = drawdown_episodes(path, _dates(len(path)))
    top = top_episodes(eps)
    assert [e.depth for e in top] == pytest.approx([-0.5, -0.2])
    many = [e for _ in range(5) for e in eps]
    assert len(top_episodes(many)) == 3
    assert top_episodes([]) == []


def test_tp03_episodes_match_a_plain_loop_and_never_overlap() -> None:
    for seed in range(30):
        rng = np.random.default_rng(1000 + seed)
        r = rng.normal(0.0003, 0.012, size=400)
        path = compound_path(r)
        eps = drawdown_episodes(path, _dates(len(path)))
        plain = _plain_drawdowns(r.tolist())
        assert len(eps) == len(plain)
        dates = _dates(len(path))
        for e, (depth, p, t, rec) in zip(eps, plain, strict=True):
            assert e.depth == pytest.approx(depth, rel=1e-12)
            assert (e.peak_date, e.trough_date) == (dates[p], dates[t])
            assert e.recovery_date == (None if rec is None else dates[rec])
            assert e.days_peak_to_trough == t - p
            assert e.days_trough_to_recovery == (None if rec is None else rec - t)
            assert -1.0 <= e.depth < 0.0
        # Non-overlapping: each episode ends (recovers) before the next one's peak or at it.
        for a, b in zip(eps, eps[1:], strict=False):
            assert a.recovery_date is not None and a.recovery_date <= b.peak_date
        # Against pandas: the deepest episode is the minimum of the running drawdown.
        w = pd.Series(path)
        pandas_min = float((w / w.cummax() - 1.0).min())
        assert min(e.depth for e in eps) == pytest.approx(pandas_min, rel=1e-12)


def test_tp04_a_flat_start_and_equal_peak_count_as_regained() -> None:
    # Path 1, 0.9, 1.0 : the path regains the peak of 1.0 exactly at point 2.
    r = [-0.10, 1 / 0.9 - 1.0]
    path = compound_path(np.array(r))
    (ep,) = drawdown_episodes(path, _dates(3))
    assert ep.depth == pytest.approx(-0.1)
    assert ep.recovery_date is not None and ep.days_trough_to_recovery == 1


# ------------------------------------------------------------------------- full-function oracles
def test_tp05_alternating_series_oracle() -> None:
    # r alternates +x, -x (x = 1%), n = 60, RF = 0.
    # mean = 0, so Sharpe = 0; sample variance = n x^2 / (n - 1), so
    # volatility = sqrt(252) x sqrt(60 / 59).
    # Every pair multiplies to (1.01)(0.99) = 0.9999, so prod = 0.9999^30 and
    # CAGR = prod^(252/60) - 1. Standard error of the Sharpe ratio: sqrt(252) sqrt(1 / 60).
    x, n = 0.01, 60
    ret, rf = _series([x if i % 2 == 0 else -x for i in range(n)])
    res = performance_stats(ret, rf)
    assert res.n == n
    assert res.volatility_annual == pytest.approx(math.sqrt(A) * x * math.sqrt(n / (n - 1)))
    assert res.sharpe_annual == pytest.approx(0.0, abs=1e-12)
    assert res.sharpe_se_iid == pytest.approx(math.sqrt(A) * math.sqrt(1 / n))
    lo, hi = res.sharpe_ci95 or (math.nan, math.nan)
    assert lo < 0.0 < hi
    prod = 1.0
    for i in range(n):
        prod *= 1 + (x if i % 2 == 0 else -x)
    assert res.cumulative_return == pytest.approx(0.9999**30 - 1.0, rel=1e-12)
    assert res.cumulative_return == pytest.approx(prod - 1.0, rel=1e-12)
    assert res.cagr == pytest.approx(prod ** (A / n) - 1.0, rel=1e-12)
    assert res.mean_return_annual == pytest.approx(0.0, abs=1e-12)
    # Drawdown: checked against the independent loop (the deepest of the 30 small episodes).
    plain = _plain_drawdowns([x if i % 2 == 0 else -x for i in range(n)])
    assert res.max_drawdown == pytest.approx(min(d for d, *_ in plain), rel=1e-12)


def test_tp06_two_by_hand_values_with_a_risk_free_rate() -> None:
    # 60 days: 30 days of +1% then 30 days of -0.5%, RF = 0.01% a day.
    # r mean = (0.01 + -0.005) / 2 = 0.0025 ; excess mean = 0.0025 - 0.0001 = 0.0024.
    # excess is two values (0.0099 and -0.0051) in equal halves: sample variance
    #   = 60 * ((0.0099 - 0.0024)^2) / 59 = 60 * 0.0075^2 / 59.
    r = [0.01] * 30 + [-0.005] * 30
    ret, rf = _series(r, rf=0.0001)
    res = performance_stats(ret, rf)
    sd = math.sqrt(60 * 0.0075**2 / 59)
    sharpe_d = 0.0024 / sd
    assert res.sharpe_daily == pytest.approx(sharpe_d, rel=1e-9)
    assert res.sharpe_annual == pytest.approx(math.sqrt(A) * sharpe_d, rel=1e-9)
    se = math.sqrt(A) * math.sqrt((1 + 0.5 * sharpe_d**2) / 60)
    assert res.sharpe_se_iid == pytest.approx(se, rel=1e-9)
    lo, hi = res.sharpe_ci95 or (math.nan, math.nan)
    assert lo == pytest.approx(math.sqrt(A) * sharpe_d - 1.959963984540054 * se, rel=1e-9)
    assert hi == pytest.approx(math.sqrt(A) * sharpe_d + 1.959963984540054 * se, rel=1e-9)
    assert res.mean_excess_annual == pytest.approx(A * 0.0024, rel=1e-9)
    assert res.mean_return_annual == pytest.approx(A * 0.0025, rel=1e-9)
    assert res.volatility_annual == pytest.approx(
        math.sqrt(A) * math.sqrt(60 * 0.0075**2 / 59), rel=1e-9
    )
    # Independent plain loop for the compounded growth.
    prod = 1.0
    for v in r:
        prod *= 1 + v
    assert res.cumulative_return == pytest.approx(prod - 1, rel=1e-12)
    assert res.cagr == pytest.approx(prod ** (A / 60) - 1, rel=1e-12)
    assert res.years == pytest.approx(60 / A)
    assert res.max_drawdown == pytest.approx(-(1 - 0.995**30), rel=1e-9)


def test_tp07_period_fields() -> None:
    ret, rf = _series([0.001, -0.001] * 40)
    res = performance_stats(ret, rf)
    assert res.n == 80 and res.years == pytest.approx(80 / 252)
    assert res.start == ret.index[0].date() and res.end == ret.index[-1].date()


# ------------------------------------------------------------------------- edge cases
def test_tp08_constant_prices_give_no_sharpe_and_no_nan() -> None:
    ret, rf = _series([0.0] * 100, rf=0.0001)  # a flat price: every return is zero
    res = performance_stats(ret, rf)
    assert res.volatility_annual == pytest.approx(0.0, abs=1e-12)
    assert res.sharpe_annual is None and res.sharpe_daily is None
    assert res.sharpe_se_iid is None and res.sharpe_ci95 is None
    assert res.cagr == 0.0 and res.cumulative_return == 0.0
    assert res.max_drawdown == 0.0 and res.episodes == ()
    assert math.isfinite(res.mean_excess_annual)


def test_tp09_constant_nonzero_return_matches_the_closed_form() -> None:
    r = 0.0004
    ret, rf = _series([r] * 100, rf=0.0001)
    res = performance_stats(ret, rf)
    assert res.cagr == pytest.approx((1 + r) ** 252 - 1, rel=1e-12)
    assert res.cumulative_return == pytest.approx((1 + r) ** 100 - 1, rel=1e-12)
    assert res.mean_return_annual == pytest.approx(252 * r)
    assert res.sharpe_annual is None  # the excess return is a constant 0.0003
    assert res.max_drawdown == 0.0


@pytest.mark.parametrize("r", [-0.0003, 0.0, 0.0002, 0.001, 0.02])
def test_tp10_cagr_of_a_constant_return_for_any_length(r: float) -> None:
    for n in (60, 61, 252, 500):
        ret, rf = _series([r] * n)
        assert performance_stats(ret, rf).cagr == pytest.approx((1 + r) ** 252 - 1, rel=1e-10)


def test_tp11_rising_series_has_no_drawdown() -> None:
    ret, rf = _series([0.001 * (1 + i / 100) for i in range(120)])
    res = performance_stats(ret, rf)
    assert res.max_drawdown == 0.0 and res.episodes == ()


def test_tp12_one_crash_and_full_recovery() -> None:
    # 30 days at +1%, one day at -30%, 8 days at +5% (1.05^8 = 1.4775 > 1/0.7 = 1.4286), then
    # 21 flat days: 60 rows. Peak = path point 30, trough = 31, recovery = 39.
    r = [0.01] * 30 + [-0.30] + [0.05] * 8 + [0.0] * 21
    assert len(r) == 60
    ret, rf = _series(r)
    origin = ret.index[0] - pd.offsets.BDay(1)
    res = performance_stats(ret, rf, origin=origin)
    (ep,) = res.episodes
    assert res.max_drawdown == pytest.approx(-0.30)
    pts = [origin, *ret.index]
    assert ep.peak_date == pts[30].date() and ep.trough_date == pts[31].date()
    assert ep.recovery_date == pts[39].date()
    assert (ep.days_peak_to_trough, ep.days_trough_to_recovery) == (1, 8)


def test_tp13_crash_without_recovery() -> None:
    r = [0.01] * 30 + [-0.30] + [0.05] * 7 + [0.0] * 22  # 1.05^7 * 0.7 = 0.985 < 1
    assert len(r) == 60
    ret, rf = _series(r)
    res = performance_stats(ret, rf)
    (ep,) = res.episodes
    assert ep.recovery_date is None and ep.days_trough_to_recovery is None
    assert ep.depth == pytest.approx(-0.30)
    assert res.max_drawdown == ep.depth


def test_tp14_series_ending_at_its_peak() -> None:
    r = [0.02, -0.05, 0.03, 0.04, 0.01, 0.02] * 10
    ret, rf = _series(r)
    res = performance_stats(ret, rf)
    path = compound_path(np.array(r))
    assert path[-1] == path.max()
    # Every episode is closed because the path ends at its highest point.
    assert all(e.recovery_date is not None for e in res.episodes)


def test_tp15_drawdown_starting_on_day_one_uses_the_origin_date() -> None:
    r = [-0.10] + [0.002] * 59
    ret, rf = _series(r)
    origin = ret.index[0] - pd.offsets.BDay(1)
    res = performance_stats(ret, rf, origin=origin)
    ep = res.episodes[0]
    assert ep.peak_date == origin.date() and ep.trough_date == ret.index[0].date()
    # Without an origin the starting point carries the first analysed date.
    plain = performance_stats(ret, rf)
    assert plain.episodes[0].peak_date == ret.index[0].date()


def test_tp16_non_finite_input_raises() -> None:
    base = [0.001, -0.001] * 40
    for bad in (math.nan, math.inf, -math.inf):
        r = list(base)
        r[10] = bad
        ret, rf = _series(r)
        with pytest.raises(ValueError, match="not finite"):
            performance_stats(ret, rf)
    ret, rf = _series(base)
    rf.iloc[5] = math.nan
    with pytest.raises(ValueError, match="not finite"):
        performance_stats(ret, rf)


def test_tp17_bad_inputs_raise() -> None:
    ret, rf = _series([0.001, -0.001] * 40)
    with pytest.raises(ValueError, match="below -100%"):
        performance_stats(ret.where(ret.index != ret.index[3], -1.5), rf)
    with pytest.raises(ValueError, match="share one index"):
        performance_stats(ret, rf.iloc[:-1])
    with pytest.raises(ValueError, match="origin"):
        performance_stats(ret, rf, origin=ret.index[0] + pd.offsets.BDay(2))


def test_tp18_exactly_at_the_safety_threshold() -> None:
    assert MIN_OBS == 60
    ret, rf = _series([0.001, -0.002, 0.003] * 20)
    assert performance_stats(ret, rf).n == 60
    ret, rf = _series([0.001, -0.002, 0.003] * 20 + [0.0])
    assert performance_stats(ret, rf).n == 61
    ret, rf = _series([0.001, -0.002, 0.003] * 19 + [0.001, -0.002])
    with pytest.raises(InsufficientObservations) as info:
        performance_stats(ret, rf)
    assert info.value.n == 59


def test_tp19_total_loss_day_is_allowed() -> None:
    r = [0.001] * 30 + [-1.0] + [0.0] * 29
    ret, rf = _series(r)
    res = performance_stats(ret, rf)
    assert res.max_drawdown == pytest.approx(-1.0)
    assert res.cagr == pytest.approx(-1.0)
    assert res.episodes[0].recovery_date is None


# ------------------------------------------------------------------------- properties
def test_tp20_sharpe_is_invariant_to_a_scale_change_of_excess_and_sd() -> None:
    rng = np.random.default_rng(7)
    r = rng.normal(0.0004, 0.01, size=300)
    rfv = np.full(300, 0.0001)
    base = performance_stats(*_series(r, rf=0.0001))
    for c in (0.1, 0.5, 3.0, 10.0):
        scaled = performance_stats(*_series(r * c, rf=list(rfv * c)))
        assert scaled.sharpe_annual == pytest.approx(base.sharpe_annual, rel=1e-9)
        assert scaled.sharpe_se_iid == pytest.approx(base.sharpe_se_iid, rel=1e-9)
        assert scaled.volatility_annual == pytest.approx(c * base.volatility_annual, rel=1e-9)


def test_tp21_drawdown_is_within_minus_one_and_zero_and_matches_pandas() -> None:
    for seed in range(40):
        rng = np.random.default_rng(500 + seed)
        r = rng.normal(0.0, rng.uniform(0.003, 0.05), size=int(rng.integers(60, 700)))
        r = np.clip(r, -0.9, 1.0)
        res = performance_stats(*_series(r))
        assert -1.0 <= res.max_drawdown <= 0.0
        w = pd.Series(compound_path(r))
        assert res.max_drawdown == pytest.approx(float((w / w.cummax() - 1.0).min()), rel=1e-12)
        if res.episodes:
            assert res.episodes[0].depth == res.max_drawdown
            depths = [e.depth for e in res.episodes]
            assert depths == sorted(depths) and len(res.episodes) <= 3


def test_tp22_volatility_and_mean_against_numpy_on_random_series() -> None:
    for seed in range(10):
        rng = np.random.default_rng(900 + seed)
        r = rng.normal(0.0005, 0.015, size=800)
        rfv = rng.uniform(0.0, 0.0002, size=800)
        res = performance_stats(*_series(r, rf=list(rfv)))
        x = r - rfv
        assert res.volatility_annual == pytest.approx(r.std(ddof=1) * math.sqrt(252), rel=1e-12)
        assert res.sharpe_annual == pytest.approx(
            x.mean() / x.std(ddof=1) * math.sqrt(252), rel=1e-12
        )
        assert res.mean_return_annual == pytest.approx(252 * r.mean(), rel=1e-12)
        assert res.cagr == pytest.approx(np.prod(1 + r) ** (252 / 800) - 1, rel=1e-11)


def test_tp23_inputs_are_not_mutated() -> None:
    ret, rf = _series([0.001, -0.002, 0.003] * 30)
    before = (ret.copy(), rf.copy())
    performance_stats(ret, rf)
    pd.testing.assert_series_equal(ret, before[0])
    pd.testing.assert_series_equal(rf, before[1])


def test_tp24_sd_floor_is_the_sample_floor() -> None:
    from factordesk.analytics.sample import MIN_RETURN_SD

    assert SD_FLOOR == MIN_RETURN_SD
