"""Currency engine: identity, round trip, hedge, NaN policy."""

from __future__ import annotations

from datetime import UTC, datetime

import numpy as np
import pandas as pd
import pytest

from factordesk.analytics.currency import (
    convert,
    convert_factors,
    convert_history,
    convert_series,
    hedge,
    listing_currency,
)
from factordesk.data.prices import PriceHistory, Security, UnsupportedCurrencyError

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
    assert out.missing == 0
    assert out.notice is None


def test_hedge_equal_cash_returns_asset() -> None:
    cash = pd.Series(0.0001, index=DATES)
    np.testing.assert_allclose(hedge(R, cash, cash).to_numpy(), R.to_numpy(), atol=1e-15)


def test_hedge_swaps_cash() -> None:
    out = hedge(R, pd.Series(0.0002, index=DATES), pd.Series(0.0005, index=DATES))
    np.testing.assert_allclose((out - R).to_numpy(), 0.0003)


def test_missing_fx_dates_stay_nan_and_are_counted() -> None:
    fx = F.copy()
    fx.iloc[[1, 4]] = np.nan
    out = convert_series(R, "USD", "EUR", lambda: fx)
    assert out.missing == 2
    assert out.returns.index.equals(R.index)  # the calendar is not rebuilt
    assert out.returns.isna().sum() == 2
    assert out.notice is not None and "2 dates" in out.notice


def test_missing_source_raises() -> None:
    with pytest.raises(ValueError, match="no exchange rate"):
        convert_series(R, "USD", "EUR", lambda: None)


# ------------------------------------------------------------------------------ factors in EUR
def _french() -> pd.DataFrame:
    rng = np.random.default_rng(3)
    idx = pd.bdate_range("2023-01-02", periods=8, name="date")
    frame = pd.DataFrame(
        rng.normal(0, 0.01, (8, 7)),
        index=idx,
        columns=["Mkt-RF", "SMB", "HML", "RMW", "CMA", "RF", "Mom"],
    )
    frame["RF"] = 0.0002
    frame.attrs["downloaded_at"] = "2023-01-01"
    return frame


def test_long_short_factor_is_usd_times_one_plus_f() -> None:
    frame = _french()
    fx = pd.Series(np.linspace(-0.004, 0.004, 8), index=frame.index)
    out = convert_factors(frame, fx, pd.Series(0.0001, index=frame.index))
    for col in ("SMB", "HML", "RMW", "CMA", "Mom"):
        np.testing.assert_allclose(out[col], frame[col] * (1 + fx))
    assert out.attrs == frame.attrs


def test_market_identity_and_rf_is_euro_cash() -> None:
    frame = _french()
    fx = pd.Series(np.linspace(-0.004, 0.004, 8), index=frame.index)
    cash = pd.Series(0.0001, index=frame.index)
    out = convert_factors(frame, fx, cash)
    total_usd = frame["Mkt-RF"] + frame["RF"]
    # The market total return in EUR, minus EUR cash, is the converted excess return.
    np.testing.assert_allclose(out["Mkt-RF"] + out["RF"], (1 + total_usd) * (1 + fx) - 1)
    assert (out["RF"] == cash).all()


def test_factor_rows_without_fx_or_cash_are_dropped() -> None:
    frame = _french()
    fx = pd.Series(0.001, index=frame.index)
    fx.iloc[0] = np.nan
    cash = pd.Series(0.0001, index=frame.index)
    cash.iloc[-1] = np.nan
    out = convert_factors(frame, fx, cash)
    assert list(out.index) == list(frame.index[1:-1])


def test_converted_history_returns_match_convert() -> None:
    idx = pd.bdate_range("2023-01-02", periods=6, name="date")
    frame = pd.DataFrame(
        {
            "close": [10, 10.5, 10.2, 10.8, 11, 10.9],
            "adj_close": [10, 10.5, 10.2, 10.8, 11, 10.9],
            "dividends": 0.0,
            "splits": 0.0,
            "volume": 100.0,
        },
        index=idx,
    ).astype("float64")
    history = PriceHistory("AAA", frame, datetime(2023, 2, 1, tzinfo=UTC), "test")
    price = pd.Series([0.92, 0.93, 0.91, 0.9, 0.94, 0.95], index=idx)
    out, dropped = convert_history(history, lambda d: price.reindex(d))
    assert dropped == 0
    fx_ret = (price / price.shift(1) - 1).iloc[1:]
    np.testing.assert_allclose(
        out.total_returns, convert(history.total_returns, fx_ret), atol=1e-12
    )
    assert (out.frame["volume"] == 100.0).all()
    price.iloc[0] = np.nan
    short, dropped = convert_history(history, lambda d: price.reindex(d))
    assert dropped == 1 and len(short.frame) == 5  # a leading row without a rate is cut
    price.iloc[0], price.iloc[3] = 0.92, np.nan
    hole, counted = convert_history(history, lambda d: price.reindex(d))
    assert counted == 1 and len(hole.frame) == 6  # an inner row stays, with NaN prices
    assert np.isnan(hole.frame["adj_close"].iloc[3])
    assert hole.total_returns.isna().sum() == 2  # the sample excludes both returns


def test_pence_are_divided_by_one_hundred() -> None:
    assert listing_currency("X.L", Security(currency="GBp")) == ("GBP", 0.01)
    assert listing_currency("X.L", Security(currency="GBX")) == ("GBP", 0.01)
    assert listing_currency("X.L", Security(currency="GBP")) == ("GBP", 1.0)
    assert listing_currency("X", None) == ("USD", 1.0)
    with pytest.raises(UnsupportedCurrencyError):
        listing_currency("X.JO", Security(currency="ZAR"))
    for security in (None, Security(name="No currency")):
        with pytest.raises(UnsupportedCurrencyError, match="no quote currency"):
            listing_currency("SAP.DE", security)
    assert listing_currency("BRK.B", None) == ("USD", 1.0)  # a US class share
    idx = pd.bdate_range("2023-01-02", periods=3, name="date")
    frame = pd.DataFrame({"close": 250.0, "adj_close": 250.0, "dividends": 0.0}, index=idx)
    history = PriceHistory("X.L", frame, datetime(2023, 2, 1, tzinfo=UTC), "test")
    out, _ = convert_history(history, lambda d: pd.Series(1.2, index=d), 0.01)
    assert out.frame["adj_close"].iloc[0] == pytest.approx(3.0)
