"""Analysis sample tests (test-oracle T31-T36, T95, T100; methodology M2, M1.3)."""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import pytest
from numpy.typing import NDArray

from factordesk.analytics.regression import ols_hac
from factordesk.analytics.rolling import rolling_betas
from factordesk.analytics.sample import (
    FACTOR_CODES,
    InsufficientHistoryError,
    build_sample,
)
from factordesk.data.audit import audit_prices
from factordesk.data.prices import PriceHistory
from factordesk.tests.fixtures.dgp import (
    FETCHED_AT,
    Synthetic,
    dgp_a,
    price_history,
    rng_for,
)


def _drop_price_row(d: Synthetic, pos: int) -> PriceHistory:
    """Remove price row ``pos`` (0 = the leading 2009-12-31 row)."""
    frame = d.history.frame.drop(index=d.history.frame.index[pos])
    return PriceHistory(d.history.ticker, frame, FETCHED_AT, "synthetic")


def test_t31_multi_day_return_is_excluded() -> None:
    d = dgp_a(rng_for(31), n=700)
    missing = d.history.frame.index[101]  # a date the French file has
    s = build_sample(_drop_price_row(d, 101), d.factors)
    nxt = pd.Timestamp(d.history.frame.index[102])
    after = pd.Timestamp(d.history.frame.index[103])
    assert [(e.date, e.reason) for e in s.excluded] == [(nxt.date(), "multi_day_return")]
    assert missing not in s.xret.index and nxt not in s.xret.index
    assert after in s.xret.index
    # The aligned row after it uses one day of prices and one factor day.
    p = d.history.frame["adj_close"]
    assert s.ret.loc[after] == p.loc[after] / p.loc[nxt] - 1.0
    assert s.n == 700 - 2


def test_t32_day_without_factor_row_is_excluded() -> None:
    d = dgp_a(rng_for(32), n=700)
    gone = d.factors.index[200]
    s = build_sample(d.history, d.factors.drop(index=gone))
    following = d.factors.index[201]
    assert [(e.date, e.reason) for e in s.excluded] == [
        (pd.Timestamp(gone).date(), "no_factor_row")
    ]
    assert following in s.xret.index  # its interval (gone, following] has one French date
    assert s.n == 699


def test_t33_uncovered_tail() -> None:
    d = dgp_a(rng_for(33), n=630)
    factors = d.factors.iloc[:600]
    last = pd.Timestamp(factors.index[-1]).date()
    s = build_sample(d.history, factors)
    assert s.end == last == s.factor_last_date
    assert s.uncovered.n == 30
    tail = d.history.total_returns.iloc[600:]
    assert s.uncovered.first == pd.Timestamp(tail.index[0]).date()
    assert s.uncovered.last == pd.Timestamp(tail.index[-1]).date()
    tail_v: NDArray[np.float64] = np.asarray(tail, dtype=np.float64)
    expected = float(np.prod(tail_v + 1.0) - 1.0)
    assert s.uncovered.compounded_return is not None
    assert abs(s.uncovered.compounded_return - expected) <= 1e-12
    # No statistic uses the tail: deleting it leaves the sample identical.
    trimmed = PriceHistory("SYN", d.history.frame.iloc[:601], FETCHED_AT, "synthetic")
    s2 = build_sample(trimmed, factors)
    assert s2.n == s.n and s2.uncovered.n == 0
    pd.testing.assert_series_equal(s2.xret, s.xret)


def test_t34_requested_vs_actual_dates() -> None:
    d = dgp_a(rng_for(34), n=700)
    s = build_sample(d.history, d.factors, date(2010, 1, 1), date(2030, 1, 1))
    assert s.requested_start == date(2010, 1, 1)
    assert s.requested_end == date(2030, 1, 1)
    assert s.start == date(2010, 1, 4)
    assert s.end == s.factor_last_date
    p = d.history.frame["adj_close"]
    assert s.ret.iloc[0] == p.loc["2010-01-04"] / p.loc["2009-12-31"] - 1.0
    # A requested start inside the data uses the previous price row (earlier data only).
    s_mid = build_sample(d.history, d.factors, date(2010, 3, 1))
    assert s_mid.start == date(2010, 3, 1)
    assert s_mid.ret.iloc[0] == p.loc["2010-03-01"] / p.loc["2010-02-26"] - 1.0


@pytest.mark.parametrize(
    ("n", "ok", "short"), [(503, False, True), (504, True, True), (750, True, False)]
)
def test_t35_guards(n: int, ok: bool, short: bool) -> None:
    d = dgp_a(rng_for(35), n=n)
    if not ok:
        with pytest.raises(InsufficientHistoryError) as info:
            build_sample(d.history, d.factors)
        assert (info.value.n, info.value.required, info.value.code) == (
            503,
            504,
            "insufficient_history",
        )
        return
    s = build_sample(d.history, d.factors)
    assert s.n == n
    assert s.short_history is short


def test_t36_excess_return_is_bitwise_r_minus_rf() -> None:
    d = dgp_a(rng_for(36))
    s = build_sample(d.history, d.factors)
    assert np.array_equal(s.xret.to_numpy(), s.ret.to_numpy() - s.rf.to_numpy())
    np.testing.assert_array_equal(s.rf.to_numpy(), d.rf)
    assert list(s.factors.columns) == list(FACTOR_CODES)


def test_t95_no_fillna_zero() -> None:
    """NaN in 3 prices, 2 factor cells and 1 RF cell: rows excluded, nothing filled."""
    d = dgp_a(rng_for(95))
    clean = build_sample(d.history, d.factors)
    frame = d.history.frame.copy()
    price_rows = [300, 900, 1500]
    for pos in price_rows:
        frame.loc[frame.index[pos], "adj_close"] = np.nan
    factors = d.factors.copy()
    for pos, col in ((400, "HML"), (1100, "Mkt-RF"), (2000, "RF")):
        factors.loc[factors.index[pos], col] = np.nan
    s = build_sample(PriceHistory("SYN", frame, FETCHED_AT, "synthetic"), factors)

    # A NaN price at price row p kills returns p and p+1 (return rows p-1 and p).
    price_missing = {pd.Timestamp(frame.index[p + k]).date() for p in price_rows for k in (0, 1)}
    factor_missing = {pd.Timestamp(factors.index[i]).date() for i in (400, 1100, 2000)}
    got = {(e.date, e.reason) for e in s.excluded}
    assert got == {(x, "price_missing") for x in price_missing} | {
        (x, "factor_missing") for x in factor_missing
    }
    assert s.n == clean.n - 9
    assert int((s.ret == 0.0).sum()) == int((clean.ret == 0.0).sum()) == 0
    rb = rolling_betas(s, 252)
    assert int((rb.betas == 0.0).to_numpy().sum()) == 0

    # Full-sample betas equal OLS on the clean data with the excluded rows removed.
    keep = clean.xret.index.isin(s.xret.index)
    ref = ols_hac(clean.xret.to_numpy()[keep], clean.factors.to_numpy()[keep])
    ours = ols_hac(s.xret.to_numpy(), s.factors.to_numpy())
    np.testing.assert_allclose(ours.params, ref.params, rtol=1e-10, atol=0)


def test_non_positive_price_gives_missing_returns() -> None:
    """M1.3: a zero price makes the return of that row and of the next row NaN."""
    idx = pd.bdate_range("2024-01-01", periods=5, name="date")
    frame = pd.DataFrame(
        {
            "close": [100.0, 101.0, 0.0, 103.0, 104.0],
            "adj_close": [100.0, 101.0, 0.0, 103.0, 104.0],
            "dividends": 0.0,
            "splits": 0.0,
        },
        index=idx,
    )
    r = PriceHistory("X", frame, FETCHED_AT, "synthetic").total_returns
    assert r.isna().tolist() == [False, True, True, False]
    assert r.iloc[3] == 104.0 / 103.0 - 1.0


def test_t100_extreme_rows_kept_and_flagged() -> None:
    d = dgp_a(rng_for(100), n=800)
    ret = d.ret.copy()
    ret[300] = -0.45
    ret[500] = 0.60
    hist = price_history(ret, d.dates)
    s = build_sample(hist, d.factors)
    assert s.n == 800
    assert abs(s.ret.iloc[300] + 0.45) < 1e-12 and abs(s.ret.iloc[500] - 0.60) < 1e-12
    audit = audit_prices(hist.frame)
    large = next(f for f in audit.findings if f.code == "large_return")
    assert {pd.Timestamp(d.dates[300]).date(), pd.Timestamp(d.dates[500]).date()} <= set(
        large.dates
    )


def test_rejects_bad_factor_index() -> None:
    d = dgp_a(rng_for(36), n=600)
    bad = d.factors.copy()
    bad.index = pd.DatetimeIndex(bad.index).tz_localize("UTC")
    with pytest.raises(ValueError, match="tz-naive"):
        build_sample(d.history, bad)
