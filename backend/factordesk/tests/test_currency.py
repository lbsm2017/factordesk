"""Currency engine: identity, round trip, hedge, NaN policy."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from factordesk.analytics.currency import convert, convert_series, hedge

DATES = pd.bdate_range("2024-01-01", periods=6, name="date")
R = pd.Series([0.01, -0.02, 0.005, 0.0, 0.03, -0.01], index=DATES, name="r")
F = pd.Series([0.002, -0.001, 0.0, 0.004, -0.003, 0.001], index=DATES)


def test_convert_formula() -> None:
    out = convert(R, F)
    assert out.iloc[0] == pytest.approx(1.01 * 1.002 - 1)
    assert out.name == "r"


def test_round_trip_is_identity() -> None:
    inverse = 1.0 / (1.0 + F) - 1.0  # return of EUR in USD when F is USD in EUR
    back = convert(convert(R, F), inverse)
    np.testing.assert_allclose(back.to_numpy(), R.to_numpy(), atol=1e-12)


def test_identity_does_not_call_fx() -> None:
    def boom() -> pd.Series:
        raise AssertionError("must not download")

    out = convert_series(R, "usd", "USD", boom)
    assert out.returns is R
    assert out.dropped == 0
    assert out.notice is None


def test_hedge_equal_cash_returns_asset() -> None:
    cash = pd.Series(0.0001, index=DATES)
    np.testing.assert_allclose(hedge(R, cash, cash).to_numpy(), R.to_numpy(), atol=1e-15)


def test_hedge_swaps_cash() -> None:
    out = hedge(R, pd.Series(0.0002, index=DATES), pd.Series(0.0005, index=DATES))
    np.testing.assert_allclose((out - R).to_numpy(), 0.0003)


def test_missing_fx_dates_are_dropped_and_counted() -> None:
    fx = F.copy()
    fx.iloc[[1, 4]] = np.nan
    out = convert_series(R, "USD", "EUR", lambda: fx)
    assert out.dropped == 2
    assert len(out.returns) == 4
    assert out.returns.notna().all()
    assert out.notice is not None and "2 dates" in out.notice


def test_missing_source_raises() -> None:
    with pytest.raises(ValueError, match="no exchange rate"):
        convert_series(R, "USD", "EUR", lambda: None)
