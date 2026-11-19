"""Portfolio backtest: hand-worked oracle, timing, cash, cost and common-window rules.

The 2-leaf, 2-month example is worked by hand in the comments with exact fractions. IDs TB01-TB16.
"""

from __future__ import annotations

import math
from datetime import date

import numpy as np
import pandas as pd
import pytest

from factordesk.analytics.backtest import (
    CASH_ID,
    SURVIVORSHIP_NOTE,
    BacktestResult,
    rebalance_mask,
    run_backtest,
)

TOL = 1e-15


def _frame(rows: dict[str, list[float]], dates: list[str]) -> pd.DataFrame:
    return pd.DataFrame(rows, index=pd.DatetimeIndex(dates, name="date"), dtype="float64")


def _rf(index: pd.DatetimeIndex, value: float = 0.0) -> pd.Series:
    return pd.Series(value, index=index, name="rf", dtype="float64")


def _random(n: int, k: int, seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2021-01-04", periods=n, name="date")
    data = rng.normal(0.0004, 0.012, size=(n, k))
    return pd.DataFrame(data, index=idx, columns=[f"L{i}" for i in range(k)])


# Hand-worked example: A 60%, B 40%, no cash, rf 0.
#   2025-01-30  rA 0.10  rB 0.00   values A 0.66 B 0.40 -> g1 = 0.06, w = (0.66, 0.40) / 1.06
#   2025-01-31  rA 0.00  rB 0.05   values A 0.66 B 0.42 -> g2 = 1.08/1.06 - 1
#               drifted w = (0.66, 0.42) / 1.08 = (11/18, 7/18); last day of January: rebalance
#               turnover = 1/2 (|0.6 - 11/18| + |0.4 - 7/18|) = 1/90
#   2025-02-03  rA 0.10  rB -0.05  start (0.6, 0.4) -> g3 = 0.06 - 0.02 = 0.04
#               drifted w = (0.66, 0.38) / 1.04
#   2025-02-04  rA -0.10 rB 0.05   values A 0.594 B 0.399 -> g4 = 0.993/1.04 - 1
#               February is the last, partial month: no rebalance.
#   Without cost the value ends at 1.08 * 0.993, a total return of 0.07244.
HAND_DATES = ["2025-01-30", "2025-01-31", "2025-02-03", "2025-02-04"]
HAND = {"A": [0.10, 0.00, 0.10, -0.10], "B": [0.00, 0.05, -0.05, 0.05]}
HAND_W = {"A": 0.6, "B": 0.4}


def _hand(cost_bps: float = 0.0) -> BacktestResult:
    frame = _frame(HAND, HAND_DATES)
    return run_backtest(frame, HAND_W, _rf(pd.DatetimeIndex(frame.index)), cost_bps=cost_bps)


def test_tb01_hand_worked_two_leaves_two_months() -> None:
    res = _hand()
    expected_gross = [0.06, 1.08 / 1.06 - 1.0, 0.04, 0.993 / 1.04 - 1.0]
    assert np.allclose(res.gross_ret.to_numpy(), expected_gross, atol=TOL, rtol=0)
    assert np.allclose(res.ret.to_numpy(), expected_gross, atol=TOL, rtol=0)
    assert res.rebalance_dates == (date(2025, 1, 31),)
    drift = res.drifted_weights
    assert drift.loc["2025-01-30", "A"] == pytest.approx(0.66 / 1.06, abs=TOL)
    assert drift.loc["2025-01-31", "A"] == pytest.approx(11 / 18, abs=TOL)
    assert drift.loc["2025-01-31", "B"] == pytest.approx(7 / 18, abs=TOL)
    assert drift.loc["2025-02-03", "A"] == pytest.approx(0.66 / 1.04, abs=TOL)
    assert drift.loc["2025-02-04", "A"] == pytest.approx(0.594 / 0.993, abs=TOL)
    assert res.turnover.to_numpy() == pytest.approx(np.array([0.0, 1 / 90, 0.0, 0.0]), abs=TOL)
    total = float(np.cumprod(1.0 + res.ret.to_numpy(dtype=np.float64))[-1]) - 1.0
    assert total == pytest.approx(1.08 * 0.993 - 1.0, abs=1e-14)
    assert res.drifted_weights.sum(axis=1).to_numpy() == pytest.approx(np.ones(4), abs=TOL)
    assert res.leaf_ids == ("A", "B", CASH_ID)
    assert res.target_weights[CASH_ID] == 0.0


def test_tb02_hand_worked_with_cost() -> None:
    # 10 bps on turnover 1/90 at the 2025-01-31 close: k = 1/90 * 0.001.
    res = _hand(cost_bps=10.0)
    k = (1 / 90) * 0.001
    assert res.cost.to_numpy() == pytest.approx(np.array([0.0, k, 0.0, 0.0]), abs=TOL)
    assert res.ret.iloc[1] == pytest.approx((1.08 / 1.06) * (1.0 - k) - 1.0, abs=TOL)
    # Other days are untouched: the cost changes the value, not the next day's return.
    for i in (0, 2, 3):
        assert res.ret.iloc[i] == res.gross_ret.iloc[i]
    total = float(np.cumprod(1.0 + res.ret.to_numpy(dtype=np.float64))[-1]) - 1.0
    assert total == pytest.approx(1.08 * (1.0 - k) * 0.993 - 1.0, abs=1e-14)


def test_tb03_rebalance_applies_from_next_day() -> None:
    res = _hand()
    applied = res.applied_weights
    # The rebalance day itself still earns on the drifted weights of the previous close.
    assert applied.loc["2025-01-31", "A"] == pytest.approx(0.66 / 1.06, abs=TOL)
    # The day after the rebalance earns on the target.
    assert applied.loc["2025-02-03", "A"] == pytest.approx(0.6, abs=TOL)
    assert applied.loc["2025-02-03", "B"] == pytest.approx(0.4, abs=TOL)
    # Buy and hold (no rebalance) agrees up to and including the rebalance day.
    held = np.array([0.6, 0.4]) * np.cumprod(1.0 + _frame(HAND, HAND_DATES).to_numpy(), axis=0)
    bh_value = held.sum(axis=1)
    bh_ret = bh_value / np.concatenate([[1.0], bh_value[:-1]]) - 1.0
    assert res.ret.to_numpy()[:2] == pytest.approx(bh_ret[:2], abs=TOL)
    assert res.ret.iloc[2] != pytest.approx(bh_ret[2], abs=1e-6)


def test_tb04_no_look_ahead_under_future_perturbation() -> None:
    base = _random(130, 3, seed=7)
    weights = {"L0": 0.5, "L1": 0.3, "L2": 0.1}
    rf = _rf(pd.DatetimeIndex(base.index), 0.0001)
    res = run_backtest(base, weights, rf, cost_bps=15.0)
    cut = 70
    shocked = base.copy()
    shocked.iloc[cut:] = shocked.iloc[cut:] * -3.0 + 0.02
    res2 = run_backtest(shocked, weights, rf, cost_bps=15.0)
    assert np.array_equal(res.ret.to_numpy()[:cut], res2.ret.to_numpy()[:cut])
    assert np.array_equal(
        res.applied_weights.to_numpy()[: cut + 1], res2.applied_weights.to_numpy()[: cut + 1]
    )
    assert np.array_equal(res.cost.to_numpy()[:cut], res2.cost.to_numpy()[:cut])


def test_tb05_single_leaf_at_full_weight_equals_its_returns() -> None:
    base = _random(300, 1, seed=3)
    rf = _rf(pd.DatetimeIndex(base.index), 0.0002)
    res = run_backtest(base, {"L0": 1.0}, rf, cost_bps=50.0)
    assert np.array_equal(res.ret.to_numpy(), base["L0"].to_numpy())
    assert res.turnover.sum() == 0.0
    assert res.cost.sum() == 0.0
    assert (res.applied_weights[CASH_ID] == 0.0).all()


def test_tb06_unallocated_weight_earns_risk_free() -> None:
    idx = pd.bdate_range("2024-03-01", periods=60, name="date")
    rf_values = np.linspace(0.0001, 0.0002, 60)
    rf = pd.Series(rf_values, index=idx)
    zero = pd.DataFrame({"A": 0.0}, index=idx)
    res = run_backtest(zero, {"A": 0.3}, rf)
    assert res.target_weights[CASH_ID] == pytest.approx(0.7, abs=TOL)
    assert res.applied_weights[CASH_ID].iloc[0] == pytest.approx(0.7, abs=TOL)
    # A earns nothing, so every day is cash weight times rf.
    expected = res.applied_weights[CASH_ID].to_numpy() * rf_values
    assert res.ret.to_numpy() == pytest.approx(expected, abs=TOL)
    assert res.ret.iloc[0] == pytest.approx(0.7 * rf_values[0], abs=TOL)
    # A leaf that itself earns rf makes the whole portfolio earn rf, whatever the split.
    same = pd.DataFrame({"A": rf_values}, index=idx)
    res2 = run_backtest(same, {"A": 0.45}, rf)
    assert res2.ret.to_numpy() == pytest.approx(rf_values, abs=TOL)


def test_tb07_common_window_names_limiting_leaves() -> None:
    idx = pd.bdate_range("2024-01-02", periods=10, name="date")
    nan = float("nan")
    data = {
        "A": [0.01] * 10,
        "B": [nan, nan] + [0.01] * 8,
        "C": [0.01] * 8 + [nan, nan],
        "D": [nan, nan] + [0.01] * 6 + [nan, nan],
        "E": [nan] + [0.01] * 9,
    }
    frame = pd.DataFrame(data, index=idx)
    res = run_backtest(frame, dict.fromkeys(data, 0.2), _rf(idx))
    assert res.start == idx[2].date()
    assert res.end == idx[7].date()
    assert res.start_leaves == ("B", "D")
    assert res.end_leaves == ("C", "D")
    assert res.n == 6


def test_tb08_risk_free_limits_the_window_only_when_cash_is_held() -> None:
    idx = pd.bdate_range("2024-01-02", periods=10, name="date")
    frame = pd.DataFrame({"A": [0.01] * 10}, index=idx)
    rf = _rf(pd.DatetimeIndex(idx[:7]), 0.0001)
    res = run_backtest(frame, {"A": 0.8}, rf)
    assert res.end == idx[6].date()
    assert res.end_leaves == (CASH_ID,)
    assert res.start_leaves == ("A", CASH_ID)
    # Fully invested: cash has no weight, so the short rf does not limit the window.
    full = run_backtest(frame, {"A": 1.0}, rf)
    assert full.end == idx[-1].date()
    assert full.start_leaves == ("A",)
    assert full.end_leaves == ("A",)


def test_tb08b_fully_invested_ignores_short_risk_free() -> None:
    base = _random(300, 2, seed=12)
    idx = pd.DatetimeIndex(base.index)
    rf = _rf(pd.DatetimeIndex(idx[:-40]), 0.0001)
    res = run_backtest(base, {"L0": 0.7, "L1": 0.3}, rf, cost_bps=10.0)
    assert res.n == 300
    assert res.start == idx[0].date()
    assert res.end == idx[-1].date()
    assert res.end_leaves == ("L0", "L1")
    assert (res.leaf_ret[CASH_ID] == 0.0).all()
    assert (res.applied_weights[CASH_ID] == 0.0).all()


def test_tb08c_rounding_below_tolerance_gives_exactly_zero_cash() -> None:
    base = _random(80, 3, seed=13)
    idx = pd.DatetimeIndex(base.index)
    short_rf = _rf(pd.DatetimeIndex(idx[:-20]), 0.0001)
    for weights in (
        {"L0": 0.1, "L1": 0.2, "L2": 0.7 - 5e-10},
        {"L0": 1 / 3, "L1": 1 / 3, "L2": 1 / 3},
        {"L0": 0.5, "L1": 0.3, "L2": 0.2 + 5e-10},
    ):
        res = run_backtest(base, weights, short_rf)
        assert res.target_weights[CASH_ID] == 0.0
        assert math.fsum(res.target_weights.values()) == pytest.approx(1.0, abs=1e-15)
        assert res.n == 80  # cash at exactly 0 does not let the short rf cut the window
    # Just above the tolerance, the remainder is a real cash holding.
    res = run_backtest(base, {"L0": 0.5, "L1": 0.3, "L2": 0.2 - 2e-9}, short_rf)
    assert res.target_weights[CASH_ID] == pytest.approx(2e-9, rel=1e-6)
    assert res.end_leaves == (CASH_ID,)


def test_tb09_gap_inside_window_is_an_error() -> None:
    idx = pd.bdate_range("2024-01-02", periods=6, name="date")
    frame = pd.DataFrame({"A": [0.01] * 6, "B": [0.0, 0.0, float("nan"), 0.0, 0.0, 0.0]}, index=idx)
    with pytest.raises(ValueError, match="'B' has no return on 2024-01-04"):
        run_backtest(frame, {"A": 0.5, "B": 0.5}, _rf(idx))


def test_tb10_cost_equals_bps_times_turnover() -> None:
    base = _random(400, 4, seed=11)
    weights = {"L0": 0.4, "L1": 0.3, "L2": 0.2, "L3": 0.05}
    rf = _rf(pd.DatetimeIndex(base.index), 0.00015)
    res = run_backtest(base, weights, rf, cost_bps=25.0)
    on = res.turnover.index.isin(pd.DatetimeIndex(res.rebalance_dates))
    assert np.array_equal(res.cost.to_numpy(), res.turnover.to_numpy() * 25.0 / 10_000.0)
    assert (res.turnover[on] > 0).all()
    assert (res.turnover[~on] == 0.0).all()
    target = np.array([res.target_weights[c] for c in res.leaf_ids])
    drift = res.drifted_weights.to_numpy()[on]
    assert res.turnover[on].to_numpy() == pytest.approx(
        0.5 * np.abs(drift - target).sum(axis=1), abs=TOL
    )
    gross, net, k = res.gross_ret.to_numpy(), res.ret.to_numpy(), res.cost.to_numpy()
    assert net == pytest.approx((1.0 + gross) * (1.0 - k) - 1.0, abs=TOL)
    # Every reset restores the target on the next day's weights.
    nxt = np.flatnonzero(on) + 1
    assert res.applied_weights.to_numpy()[nxt] == pytest.approx(
        np.tile(target, (len(nxt), 1)), abs=TOL
    )


def test_tb11_initial_purchase_is_free() -> None:
    base = _random(5, 2, seed=1)
    res = run_backtest(base, {"L0": 0.5, "L1": 0.5}, _rf(pd.DatetimeIndex(base.index)), 100.0)
    assert res.cost.iloc[0] == 0.0
    assert res.cost.sum() == 0.0  # 5 days in January 2021: one partial month, no rebalance


def test_tb12_rebalance_mask_month_ends_except_last_month() -> None:
    idx = pd.DatetimeIndex(
        ["2024-01-30", "2024-01-31", "2024-02-28", "2024-02-29", "2024-03-01", "2024-03-29"],
        name="date",
    )
    assert rebalance_mask(idx).tolist() == [False, True, False, True, False, False]
    assert rebalance_mask(idx[:1]).tolist() == [False]
    # The last common day of the month is used even when it is not the calendar month end.
    gap = pd.DatetimeIndex(["2024-04-25", "2024-04-26", "2024-05-01"], name="date")
    assert rebalance_mask(gap).tolist() == [False, True, False]


def test_tb13_weight_validation() -> None:
    base = _random(5, 2, seed=2)
    rf = _rf(pd.DatetimeIndex(base.index))
    with pytest.raises(ValueError, match="sum to"):
        run_backtest(base, {"L0": 0.7, "L1": 0.4}, rf)
    with pytest.raises(ValueError, match=">= 0"):
        run_backtest(base, {"L0": -0.1, "L1": 0.4}, rf)
    with pytest.raises(ValueError, match="missing"):
        run_backtest(base, {"L0": 0.5}, rf)
    with pytest.raises(ValueError, match="unknown"):
        run_backtest(base, {"L0": 0.5, "L1": 0.2, "X": 0.1}, rf)
    with pytest.raises(ValueError, match="cost_bps"):
        run_backtest(base, {"L0": 0.5, "L1": 0.5}, rf, cost_bps=-1.0)
    with pytest.raises(ValueError, match="reserved"):
        run_backtest(base.rename(columns={"L0": CASH_ID}), {CASH_ID: 0.5, "L1": 0.5}, rf)


def test_tb14_bad_returns_and_no_overlap() -> None:
    idx = pd.bdate_range("2024-01-02", periods=4, name="date")
    with pytest.raises(ValueError, match="-100%"):
        run_backtest(pd.DataFrame({"A": [0.0, -1.0, 0.0, 0.0]}, index=idx), {"A": 1.0}, _rf(idx))
    nan = float("nan")
    frame = pd.DataFrame({"A": [0.0, 0.0, nan, nan], "B": [nan, nan, 0.0, 0.0]}, index=idx)
    with pytest.raises(ValueError, match="no common date"):
        run_backtest(frame, {"A": 0.5, "B": 0.5}, _rf(idx))


def test_tb15_inputs_not_mutated_and_note_present() -> None:
    base = _random(60, 2, seed=5)
    rf = _rf(pd.DatetimeIndex(base.index), 0.0001)
    before, rf_before = base.copy(), rf.copy()
    res = run_backtest(base, {"L0": 0.6, "L1": 0.3}, rf, cost_bps=5.0)
    pd.testing.assert_frame_equal(base, before)
    pd.testing.assert_series_equal(rf, rf_before)
    assert res.survivorship_note == SURVIVORSHIP_NOTE
    assert "overstate" in res.survivorship_note


def test_tb16_drift_matches_independent_value_loop() -> None:
    base = _random(250, 3, seed=9)
    weights = {"L0": 0.5, "L1": 0.25, "L2": 0.15}
    rf_values = np.full(250, 0.0001)
    rf = pd.Series(rf_values, index=base.index)
    res = run_backtest(base, weights, rf, cost_bps=20.0)
    # Plain loop over holding values (dollars), not weights.
    rets = np.column_stack([base.to_numpy(), rf_values])
    target = np.array([0.5, 0.25, 0.15, 0.10])
    month = pd.DatetimeIndex(base.index).to_period("M")
    values = target.copy()
    out: list[float] = []
    for t in range(250):
        start = values.sum()
        values = values * (1.0 + rets[t])
        end = values.sum()
        if t < 249 and month[t] != month[t + 1]:
            w = values / end
            k = 0.5 * np.abs(target - w).sum() * 20.0 / 10_000.0
            end = end * (1.0 - k)
            values = target * end
        out.append(float(end / start - 1.0))
    assert res.ret.to_numpy() == pytest.approx(np.array(out), abs=1e-14)
