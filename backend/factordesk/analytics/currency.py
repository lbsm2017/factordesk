"""Currency maths on return series: pure functions, no I/O (decision-reference-currency).

- ``convert(returns, fx_returns)``: a return in the asset's currency, measured in the reference
  currency: ``(1 + R)(1 + f) - 1``, where ``f`` is the return of one unit of the asset's currency
  in the reference currency over the same interval.
- ``hedge(returns, rf_local, cash_ref)``: a hedged return, ``R - rf_local + cash_ref`` (the
  asset's return above its own cash, plus cash of the reference currency).
- ``convert_series(...)``: ``convert`` plus the NaN policy. A date with no FX return keeps its
  row with a NaN return (the analysis sample then excludes it as ``price_missing``) and is
  counted in the notice; a return is never filled and the calendar is never rebuilt. Equal
  currencies pass the series through untouched (no download, no copy of the values).

- ``convert_factors(frame, fx, cash)``: a French factor frame in the reference currency (market
  ``(1 + MktRF + RF)(1 + f) - 1 - c``, each long-short factor ``X (1 + f)``, ``RF = c``).
- ``convert_history(history, price, scale)``: a price history in the reference currency (each
  price times the exchange-rate price of its date, so its total returns are ``convert`` of the
  local ones). Dates without an exchange rate before the first or after the last one are cut;
  those inside keep their row with NaN prices (so the sample excludes them). All are counted.
- ``EuroLegs`` and the three leg helpers: the EUR view of the macro and energy sections. A traded
  spread of two USD returns is ``X (1 + f)`` (``spread_in_reference``); a traded return above
  cash is ``(1 + R)(1 + f) - 1 - c`` (``excess_in_reference``); the dollar leg is ``f`` itself.
  Shock series (Brent, Henry Hub) are not converted.
- ``listing_currency(ticker, security)``: the ISO code of a listing and the price scale (GBp and
  GBX are pence: 0.01 pounds); anything outside ``fx.CURRENCIES`` is refused.

All series are decimals indexed by the interval end date.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from factordesk.data.fx import CURRENCIES
from factordesk.data.prices import (
    PriceHistory,
    Security,
    UnsupportedCurrencyError,
    collapse_duplicate_dates,
)


@dataclass(frozen=True)
class Converted:
    """A converted series, the number of dates left NaN for lack of an FX return, and a notice."""

    returns: pd.Series
    missing: int = 0
    notice: str | None = None


def convert(returns: pd.Series, fx_returns: pd.Series) -> pd.Series:
    """``(1 + R)(1 + f) - 1`` on the dates of ``returns``; NaN where ``f`` is missing."""
    f = fx_returns.reindex(returns.index)
    out = (1.0 + returns) * (1.0 + f) - 1.0
    out.name = returns.name
    return out


def hedge(returns: pd.Series, rf_local: pd.Series, cash_ref: pd.Series) -> pd.Series:
    """``R - rf_local + cash_ref`` on the dates of ``returns``; NaN where a cash is missing."""
    local = rf_local.reindex(returns.index)
    ref = cash_ref.reindex(returns.index)
    out = returns - local + ref
    out.name = returns.name
    return out


def convert_series(
    returns: pd.Series,
    from_ccy: str,
    to_ccy: str,
    fx_returns: Callable[[], pd.Series | None],
) -> Converted:
    """Convert ``returns`` from ``from_ccy`` to ``to_ccy``; a date with no FX return stays NaN.

    ``fx_returns`` is called only when the currencies differ. It returns the FX series or None
    (source down): ``ValueError`` is raised then, so the caller can answer 503 for the view.
    """
    if from_ccy.upper() == to_ccy.upper():
        return Converted(returns)
    fx = fx_returns()
    if fx is None:
        raise ValueError(f"no exchange rate from {from_ccy} to {to_ccy}")
    out = convert(returns, fx)
    n = int((out.isna() & returns.notna()).sum())
    if n == 0:
        return Converted(out)
    notice = f"{n} dates had no {from_ccy}/{to_ccy} exchange rate and are left out."
    return Converted(out, n, notice)


@dataclass(frozen=True)
class EuroLegs:
    """What the macro and energy sections need to run in the reference currency (EUR).

    ``fx`` is the return of one US dollar in euros over each interval of the subject's calendar,
    indexed by ``calendar[1:]``. ``usd_rf`` is the French (US dollar) risk-free return on the
    factor frame's dates: the euro frame's ``RF`` is the euro cash return, so the dollar one is
    kept here for the USD spreads (``IEF - RF``). The sample's own ``rf`` is the euro cash return.
    """

    fx: pd.Series
    usd_rf: pd.Series


def spread_in_reference(spread: pd.Series | np.ndarray, fx: pd.Series | np.ndarray) -> Any:
    """A spread of two USD returns in euros: ``X (1 + f)``."""
    return spread * (1.0 + fx)


def excess_in_reference(
    returns: pd.Series | np.ndarray, fx: pd.Series | np.ndarray, cash: pd.Series | np.ndarray
) -> Any:
    """A USD return above euro cash: ``(1 + R)(1 + f) - 1 - c``."""
    return (1.0 + returns) * (1.0 + fx) - 1.0 - cash


MARKET = "Mkt-RF"
RISK_FREE = "RF"
PRICE_COLUMNS = ("close", "adj_close", "dividends", "capital_gains")
"""History columns that are amounts of money (volume and splits are not)."""
PENCE = ("GBp", "GBX")
EXCHANGE_SUFFIXES = frozenset(
    [
        "DE",
        "F",
        "L",
        "PA",
        "MI",
        "AS",
        "SW",
        "T",
        "HK",
        "TO",
        "V",
        "AX",
        "MC",
        "ST",
        "OL",
        "CO",
        "HE",
        "BR",
        "LS",
        "VI",
        "IR",
        "SI",
        "KS",
        "NS",
        "BO",
        "SS",
        "SZ",
        "TW",
        "JO",
        "SA",
        "MX",
        "NZ",
        "TA",
        "BE",
        "HM",
        "MU",
        "SG",
        "DU",
    ]
)
"""Yahoo exchange suffixes (``SAP.DE``). A US class share such as ``BRK.B`` has none of these."""


def convert_factors(frame: pd.DataFrame, fx: pd.Series, cash: pd.Series) -> pd.DataFrame:
    """The French frame (decimals, USD) in the reference currency.

    ``fx`` is the return of the US dollar in the reference currency and ``cash`` the reference
    currency's cash return, both over the same intervals as the frame's rows. Rows where either
    is missing are dropped (before the euro series start, after the cash rate ends); nothing is
    filled. Every column but ``Mkt-RF`` and ``RF`` is a long-short factor (SMB, HML, RMW, CMA,
    Mom); a missing value in one stays missing.
    """
    f = fx.reindex(frame.index)
    c = cash.reindex(frame.index)
    out = frame.copy()
    for col in frame.columns:
        if col not in (MARKET, RISK_FREE):
            out[col] = frame[col] * (1.0 + f)
    out[MARKET] = (1.0 + frame[MARKET] + frame[RISK_FREE]) * (1.0 + f) - 1.0 - c
    out[RISK_FREE] = c
    out = out[f.notna() & c.notna()]
    out.attrs = dict(frame.attrs)
    return out


def listing_currency(ticker: str, security: Security | None) -> tuple[str, float]:
    """``(ISO code, price scale)`` of a listing; ``("USD", 1.0)`` when Yahoo gives none.

    Pence quotes (``GBp``, ``GBX``) are pounds at a scale of 0.01. A currency outside
    ``fx.CURRENCIES`` raises ``UnsupportedCurrencyError``, and so does a ticker with an exchange
    suffix (``SAP.DE``) and no currency: it is never taken for USD.
    """
    raw = None if security is None or security.currency is None else security.currency.strip()
    if not raw:
        if ticker.rsplit(".", 1)[-1].upper() in EXCHANGE_SUFFIXES and "." in ticker:
            raise UnsupportedCurrencyError(
                ticker,
                "an unknown currency",
                detail=(
                    f"{ticker} is listed outside the US and Yahoo gave no quote currency, so "
                    "factordesk cannot tell what to convert it from."
                ),
            )
        return "USD", 1.0
    if raw in PENCE:
        return "GBP", 0.01
    if raw.upper() not in CURRENCIES:
        raise UnsupportedCurrencyError(ticker, raw, convertible=True)
    return raw.upper(), 1.0


def convert_history(
    history: PriceHistory,
    price_of: Callable[[pd.DatetimeIndex], pd.Series],
    scale: float = 1.0,
) -> tuple[PriceHistory, int]:
    """``history`` with its money columns times ``scale * price`` (``price_of(dates)``: the
    exchange-rate price of one local unit in the reference currency on ``dates``).

    Repeated dates are collapsed first (first bar kept, as the pipeline does). Rows before the
    first and after the last exchange rate are cut (no price to convert, no hole in the middle);
    a row with no rate in between keeps its place with NaN prices, so its returns are NaN and the
    analysis sample excludes it. The count of rows cut or blanked is returned beside the history.
    """
    frame, repeated = collapse_duplicate_dates(history.frame)
    duplicates = tuple(sorted(set(history.duplicate_dates) | set(repeated)))
    factor = price_of(pd.DatetimeIndex(frame.index)).reindex(frame.index) * scale
    have = factor.notna().to_numpy()
    inside = np.zeros(len(have), dtype=bool)
    if have.any():
        inside[int(have.argmax()) : len(have) - int(have[::-1].argmax())] = True
    frame = frame.loc[inside].copy()
    for col in PRICE_COLUMNS:
        if col in frame.columns:
            frame[col] = frame[col].astype("float64") * factor[inside]
    return dataclasses.replace(history, frame=frame, duplicate_dates=duplicates), int((~have).sum())
