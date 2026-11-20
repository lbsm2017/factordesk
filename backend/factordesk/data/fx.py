"""Daily FX returns of any major currency in a reference currency (USD or EUR).

Public names (soft fail: a source that is down gives ``series=None`` and a notice, never an
exception and never a wait longer than the 8 s download timeout, twice at most):

- ``fx_returns(ccy, ref, dates)``: the return of holding one unit of ``ccy`` measured in ``ref``,
  as a decimal per interval, indexed by ``dates[1:]``: ``S(t)/S(t-1) - 1``, where ``S`` is the
  price of one unit of ``ccy`` in ``ref`` on the last fixing on or before each date. Days without
  a fixing (TARGET holidays for the ECB, US holidays for FRED) carry the previous fixing forward,
  for at most 7 days. NaN where no fixing exists yet or the last one is older than that.
  Equal currencies give zero. Returns an ``FxResult``.
- ``FxResult``: ``series`` (or None), ``notice`` (or None) and ``source`` (``SOURCE_ECB`` or
  ``SOURCE_FRED``, None when no source worked) for the report footer; ``credit(source)`` gives
  the footer line.
- ``CURRENCIES``: the supported codes. ``FRED_QUOTES``: quote direction of each FRED H.10 series.

Primary source: ECB euro foreign exchange reference rates (``EXR.D.<CCY>.EUR.SP00.A``, units of
CCY per 1 EUR, fixed about 14:15 CET, daily from 1999-01-04). Fallback: FRED H.10 (noon New York,
crossed through USD). Both legs of a pair always come from the same source. A cross rate is a
ratio of two legs, so ``X in R = leg(X) / leg(R)``; the two fixings differ in time of day, so
daily figures differ slightly between sources.

Pence (GBX) are not handled here: the subject layer divides the price by 100 first.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pandas as pd

from factordesk.data.ecb import EcbError, load_ecb_series
from factordesk.data.fred import FredError, load_fred_series

SOURCE_ECB = "ECB euro reference rates"
SOURCE_FRED = "FRED H.10"
_CREDITS = {
    SOURCE_ECB: "Exchange rates: European Central Bank, euro foreign exchange reference rates.",
    SOURCE_FRED: (
        "Exchange rates: Board of Governors of the Federal Reserve System (H.10), via FRED, "
        "Federal Reserve Bank of St. Louis."
    ),
}

# One table for the quote direction of every FRED H.10 series used here (each verified live).
#   "usd_per_unit": the series is USD for one unit of the currency (used as is).
#   "units_per_usd": the series is units of the currency for one USD (inverted).
FRED_QUOTES: dict[str, tuple[str, str]] = {
    "EUR": ("DEXUSEU", "usd_per_unit"),
    "GBP": ("DEXUSUK", "usd_per_unit"),
    "AUD": ("DEXUSAL", "usd_per_unit"),
    "CHF": ("DEXSZUS", "units_per_usd"),
    "JPY": ("DEXJPUS", "units_per_usd"),
    "CAD": ("DEXCAUS", "units_per_usd"),
    "HKD": ("DEXHKUS", "units_per_usd"),
    "SEK": ("DEXSDUS", "units_per_usd"),
    "NOK": ("DEXNOUS", "units_per_usd"),
    "DKK": ("DEXDNUS", "units_per_usd"),
}
CURRENCIES = ("USD", *FRED_QUOTES)
_ALWAYS_ONE = pd.Series([1.0], index=pd.DatetimeIndex(["1970-01-01"], name="date"))


@dataclass(frozen=True)
class FxResult:
    """FX returns (None when no source works), a notice for the report, and the source used."""

    series: pd.Series | None
    notice: str | None = None
    source: str | None = None


def credit(source: str | None) -> str | None:
    """The report-footer line for a source name from ``FxResult.source``."""
    return _CREDITS.get(source) if source else None


def _ecb_leg(
    ccy: str, data_dir: Path | None, now: datetime | None, fetch: Callable[[str, str], str] | None
) -> tuple[pd.Series, str | None]:
    """EUR per one unit of ``ccy`` (the ECB quotes CCY per EUR, so it is inverted)."""
    if ccy == "EUR":
        return _ALWAYS_ONE, None
    key = f"D.{ccy}.EUR.SP00.A"
    per_eur, note = load_ecb_series("EXR", key, data_dir=data_dir, now=now, fetch=fetch)
    return 1.0 / per_eur, note


def _fred_leg(
    ccy: str, data_dir: Path | None, now: datetime | None, fetch: Callable[[str], str] | None
) -> tuple[pd.Series, str | None]:
    """USD per one unit of ``ccy`` from the FRED H.10 series (holidays are NaN)."""
    if ccy == "USD":
        return _ALWAYS_ONE, None
    series_id, direction = FRED_QUOTES[ccy]
    loaded = load_fred_series(series_id, data_dir=data_dir, now=now, fetch=fetch)
    values = loaded.values.astype("float64")  # noqa: PD011 (a field of FredSeries)
    return (1.0 / values if direction == "units_per_usd" else values), loaded.note


MAX_CARRY = pd.Timedelta(days=7)
"""A fixing is carried forward at most this long (covers holidays); later dates are NaN, so a
stale cache gives NaN returns, never silent zeros."""


def _price_on(leg: pd.Series, dates: pd.DatetimeIndex) -> pd.Series:
    """The last fixing on or before each date, at most ``MAX_CARRY`` old (NaN fixings are
    skipped, so holidays carry)."""
    if leg is _ALWAYS_ONE:
        return pd.Series(1.0, index=dates)
    return leg.dropna().reindex(dates, method="ffill", tolerance=MAX_CARRY)


def fx_returns(
    ccy: str,
    ref: str,
    dates: pd.DatetimeIndex,
    *,
    data_dir: Path | None = None,
    now: datetime | None = None,
    fetch_ecb: Callable[[str, str], str] | None = None,
    fetch_fred: Callable[[str], str] | None = None,
) -> FxResult:
    """Return of one unit of ``ccy`` in ``ref`` over each interval of ``dates``. See the module
    docstring. ``fetch_*`` replace the downloads (tests)."""
    ccy, ref = ccy.upper(), ref.upper()
    for code in (ccy, ref):
        if code not in CURRENCIES:
            return FxResult(None, f"No exchange-rate source for {code}.")
    if ccy == ref:
        return FxResult(pd.Series(0.0, index=dates[1:], name="fx"))
    notes: list[str] = []
    try:
        num, n1 = _ecb_leg(ccy, data_dir, now, fetch_ecb)
        den, n2 = _ecb_leg(ref, data_dir, now, fetch_ecb)
        source = SOURCE_ECB
        notes += [n for n in (n1, n2) if n]
    except EcbError as exc:
        try:
            num, n1 = _fred_leg(ccy, data_dir, now, fetch_fred)
            den, n2 = _fred_leg(ref, data_dir, now, fetch_fred)
        except FredError as exc2:
            msg = f"The {ccy}/{ref} exchange rate is unavailable (ECB: {exc}; FRED: {exc2})."
            return FxResult(None, msg)
        source = SOURCE_FRED
        notes.append(
            f"The ECB exchange rates could not be reached ({exc}); used {SOURCE_FRED} instead "
            "(noon New York fixing)."
        )
        notes += [n for n in (n1, n2) if n]
    price = _price_on(num, dates) / _price_on(den, dates)
    returns = (price / price.shift(1) - 1.0).iloc[1:].rename("fx")
    return FxResult(returns, " ".join(notes) or None, source)
