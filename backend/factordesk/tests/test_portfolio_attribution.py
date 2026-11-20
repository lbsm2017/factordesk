"""Portfolio attribution: Frongello linking, ex-post risk share, group roll-ups. IDs TA01-TA10."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from factordesk.analytics.backtest import CASH_ID, BacktestResult, run_backtest
from factordesk.analytics.portfolio_attribution import COST_ID, attribute, roll_up

TOL = 1e-12


def _backtest(n: int = 750, seed: int = 4, cost_bps: float = 25.0) -> BacktestResult:
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2019-01-02", periods=n, name="date")
    data = rng.normal(0.0004, 0.012, size=(n, 4))
    data[:, 3] = 0.6 * data[:, 0] + rng.normal(0.0, 0.004, size=n)
    frame = pd.DataFrame(data, index=idx, columns=["SPY", "EFA", "AGG", "QQQ"])
    rf = pd.Series(rng.uniform(0.0, 0.0002, size=n), index=idx)
    weights = {"SPY": 0.35, "EFA": 0.2, "AGG": 0.25, "QQQ": 0.1}
    return run_backtest(frame, weights, rf, cost_bps=cost_bps)


def _hand() -> BacktestResult:
    # The 2-leaf, 2-month example of test_backtest (A 60%, B 40%, rebalance at 2025-01-31).
    idx = pd.DatetimeIndex(["2025-01-30", "2025-01-31", "2025-02-03", "2025-02-04"], name="date")
    frame = pd.DataFrame(
        {"A": [0.10, 0.00, 0.10, -0.10], "B": [0.00, 0.05, -0.05, 0.05]}, index=idx
    )
    return run_backtest(frame, {"A": 0.6, "B": 0.4}, pd.Series(0.0, index=idx), cost_bps=10.0)


def test_ta01_linked_contributions_sum_to_compounded_return() -> None:
    res = _backtest()
    att = attribute(res)
    compounded = float(np.cumprod(1.0 + res.ret.to_numpy(dtype=np.float64))[-1]) - 1.0
    assert abs(math.fsum(att.contribution.values()) - compounded) < TOL
    assert att.total_return == pytest.approx(compounded, abs=1e-15)
    assert res.cost.sum() > 0.0
    assert att.contribution[COST_ID] < 0.0
    assert att.row_ids == ("SPY", "EFA", "AGG", "QQQ", CASH_ID, COST_ID)


def test_ta02_daily_rows_sum_to_net_return() -> None:
    res = _backtest()
    att = attribute(res)
    row_sum = att.daily_contribution.sum(axis=1).to_numpy(dtype=np.float64)
    assert row_sum == pytest.approx(res.ret.to_numpy(dtype=np.float64), abs=1e-16)


def test_ta03_risk_shares_sum_to_one() -> None:
    att = attribute(_backtest())
    assert att.risk_share is not None
    assert abs(math.fsum(att.risk_share.values()) - 1.0) < TOL
    # The equity-heavy leaves carry most of the risk; cash carries almost none.
    assert att.risk_share["SPY"] > att.risk_share["AGG"] > abs(att.risk_share[CASH_ID])


def test_ta04_risk_share_matches_plain_covariance() -> None:
    res = _backtest(n=300, seed=8)
    att = attribute(res)
    assert att.risk_share is not None
    rp = res.ret.to_numpy(dtype=np.float64)
    var = float(np.var(rp, ddof=1))
    for row in att.row_ids:
        c = att.daily_contribution[row].to_numpy(dtype=np.float64)
        cov = float(((c - c.mean()) * (rp - rp.mean())).sum()) / (len(rp) - 1)
        assert att.risk_share[row] == pytest.approx(cov / var, abs=1e-12)


def test_ta05_frongello_hand_worked() -> None:
    # Daily contributions c = w_{t-1} * r_t (rf 0, so cash adds nothing):
    #   A: 0.06, 0, (0.6)(0.10) = 0.06, (0.66/1.04)(-0.10)
    #   B: 0, (0.40/1.06)(0.05), (0.4)(-0.05) = -0.02, (0.38/1.04)(0.05)
    # cost: -k (1 + g2) on 2025-01-31 with k = (1/90 sold + 1/90 bought) * 10 bps.
    # Link factors 1 + R_{t-1}: 1, 1.06, V2, V2 * 1.04, where V2 = 1.08 (1 - k).
    res = _hand()
    att = attribute(res)
    k = (2 / 90) * 0.001
    v2 = 1.08 * (1.0 - k)
    c_a = 0.06 * 1.0 + 0.0 * 1.06 + 0.06 * v2 + (0.66 / 1.04) * -0.10 * v2 * 1.04
    c_b = 0.0 + (0.40 / 1.06) * 0.05 * 1.06 - 0.02 * v2 + (0.38 / 1.04) * 0.05 * v2 * 1.04
    c_cost = -k * (1.08 / 1.06) * 1.06
    assert att.contribution["A"] == pytest.approx(c_a, abs=1e-15)
    assert att.contribution["B"] == pytest.approx(c_b, abs=1e-15)
    assert att.contribution[COST_ID] == pytest.approx(c_cost, abs=1e-15)
    assert att.contribution[CASH_ID] == 0.0
    assert c_a + c_b + c_cost == pytest.approx(v2 * 0.993 / 1.04 * 1.04 - 1.0, abs=1e-15)
    assert att.total_return == pytest.approx(v2 * 0.993 - 1.0, abs=1e-15)


def test_ta06_single_leaf_takes_everything() -> None:
    idx = pd.bdate_range("2022-01-03", periods=200, name="date")
    rng = np.random.default_rng(1)
    frame = pd.DataFrame({"SPY": rng.normal(0.0, 0.01, 200)}, index=idx)
    res = run_backtest(frame, {"SPY": 1.0}, pd.Series(0.0001, index=idx), cost_bps=20.0)
    att = attribute(res)
    expected = float(np.cumprod(1.0 + frame["SPY"].to_numpy(dtype=np.float64))[-1]) - 1.0
    assert att.contribution["SPY"] == pytest.approx(expected, abs=TOL)
    assert att.contribution[CASH_ID] == 0.0
    assert att.contribution[COST_ID] == 0.0
    assert att.risk_share is not None
    assert att.risk_share["SPY"] == pytest.approx(1.0, abs=TOL)


def test_ta07_cash_contribution_compounds_rf() -> None:
    # A leaf with zero return and 50% cash: all growth comes from cash.
    idx = pd.bdate_range("2023-05-01", periods=90, name="date")
    rf = pd.Series(0.0002, index=idx)
    res = run_backtest(pd.DataFrame({"A": 0.0}, index=idx), {"A": 0.5}, rf)
    att = attribute(res)
    assert att.contribution["A"] == 0.0
    assert att.contribution[CASH_ID] == pytest.approx(att.total_return, abs=TOL)
    assert att.total_return > 0.0


def test_ta08_risk_share_undefined_cases() -> None:
    idx = pd.bdate_range("2023-05-01", periods=30, name="date")
    flat = run_backtest(
        pd.DataFrame({"A": 0.001}, index=idx), {"A": 1.0}, pd.Series(0.0, index=idx)
    )
    att = attribute(flat)
    assert att.risk_share is None
    assert att.risk_share_reason == "the portfolio return does not vary"
    one = run_backtest(
        pd.DataFrame({"A": [0.01]}, index=idx[:1]), {"A": 1.0}, pd.Series(0.0, index=idx[:1])
    )
    att1 = attribute(one)
    assert att1.risk_share is None
    assert att1.contribution["A"] == pytest.approx(0.01, abs=1e-16)


PATHS: dict[str, tuple[str, ...]] = {
    "SPY": ("Equities", "USA"),
    "QQQ": ("Equities", "USA"),
    "EFA": ("Equities", "Developed ex-US"),
    "AGG": ("Fixed income", "US aggregate"),
    CASH_ID: ("Cash",),
    COST_ID: (),
}


def test_ta09_group_totals_equal_sum_of_leaves() -> None:
    att = attribute(_backtest())
    rolled = roll_up(att.contribution, PATHS)
    c = att.contribution
    assert rolled.totals[("Equities", "USA")] == pytest.approx(c["SPY"] + c["QQQ"], abs=1e-15)
    assert rolled.totals[("Equities",)] == pytest.approx(c["SPY"] + c["QQQ"] + c["EFA"], abs=1e-15)
    assert rolled.totals[("Fixed income",)] == c["AGG"]
    assert rolled.totals[("Cash",)] == c[CASH_ID]
    assert abs(rolled.totals[()] - att.total_return) < TOL
    assert rolled.members[("Equities",)] == ("SPY", "EFA", "QQQ")
    assert rolled.members[()] == att.row_ids
    # Every group equals the sum of its child groups plus rows placed directly in it.
    for group, total in rolled.totals.items():
        children = [g for g in rolled.totals if len(g) == len(group) + 1 and g[:-1] == group]
        direct = [r for r in rolled.members[group] if PATHS[r] == group]
        parts = [rolled.totals[g] for g in children] + [c[r] for r in direct]
        assert total == pytest.approx(math.fsum(parts), abs=1e-15)
    assert att.risk_share is not None
    risk = roll_up(att.risk_share, PATHS)
    assert abs(risk.totals[()] - 1.0) < TOL
    weights = roll_up(
        dict(zip(att.row_ids[:-1], [0.35, 0.2, 0.25, 0.1, 0.1], strict=True)) | {COST_ID: 0.0},
        PATHS,
    )
    assert weights.totals[("Equities",)] == pytest.approx(0.65, abs=1e-15)


def test_ta10_roll_up_rejects_missing_paths() -> None:
    with pytest.raises(ValueError, match="no path for"):
        roll_up({"A": 1.0, "B": 2.0}, {"A": ("X",)})
    with pytest.raises(ValueError, match="no value for"):
        roll_up({"A": 1.0}, {"A": ("X",), "B": ("Y",)})
    with pytest.raises(ValueError, match="non-empty"):
        roll_up({"A": 1.0}, {"A": ("X", "")})


def test_ta11_a_window_relinks_from_its_first_day() -> None:
    res = _backtest()
    first, last = res.ret.index[200].date(), res.ret.index[500].date()
    att = attribute(res, start=first, end=last)
    window = slice(200, 501)
    net = res.ret.to_numpy(dtype=np.float64)[window]
    assert len(att.daily_contribution) == len(net)
    assert att.total_return == pytest.approx(float((1.0 + net).prod() - 1.0), abs=1e-15)
    assert abs(math.fsum(att.contribution.values()) - att.total_return) < TOL
    # daily rows are the backtest's own weights times that day's returns
    expected = res.applied_weights.iloc[window, 0].to_numpy() * res.leaf_ret.iloc[window, 0]
    np.testing.assert_allclose(att.daily_contribution["SPY"].to_numpy(), expected, atol=1e-16)
    assert att.risk_share is not None and abs(math.fsum(att.risk_share.values()) - 1.0) < TOL
    # no window is the whole backtest
    assert attribute(res).contribution == attribute(res, start=None, end=None).contribution
    with pytest.raises(ValueError, match="no day"):
        attribute(res, start=res.end, end=res.start)
