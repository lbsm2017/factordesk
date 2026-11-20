"""EUR and CHF overnight rates and cash returns.

Public functions and constants (soft fail: a source that is down gives ``rate=None`` and a
notice, never an exception; every download stops after the 8 s timeout, twice at most):

- ``load_eur_overnight()``: the EUR overnight rate as a decimal ANNUAL rate (0.0292 means 2.92%),
  one value per TARGET business day. Date convention: the value dated D is the rate for the night
  that starts on D (it applies from D to the next rate date). EONIA (ECB series
  ``EON.D.EONIA_TO.RATE``, as published, no spread) for dates before 2019-10-01, then the euro
  short-term rate (euro STR, ECB series ``EST.B.EU000A2X2A25.WT``) from 2019-10-01. If the ECB
  is down, FRED ``ECBESTRVOLWGTTRMDMNRT`` replaces euro STR, and EONIA still comes from any
  cached ECB copy (no download); with no cached EONIA the series starts on 2019-10-01.
- ``load_chf_overnight()``: the CHF overnight rate (decimal annual rate, one value per Swiss
  business day, dated like the EUR one): SARON, the fixing at the close of the trading day, from
  the SNB data portal. One series: cube ``zirepo``, item ``H0`` ("Overnight (SARON), close of
  trading": daily from 1999-06-21, six decimals, published with a lag of about a month), then
  cube ``snbgwdzid``, item ``SARON`` (daily, fresh, rounded to two decimals of a percent) for the
  days after the last ``zirepo`` day. The portal has no daily TOIS series. The values are used as
  published. If the fresh cube is down (and has no cached copy), ``rate`` is ``None`` and the
  caller falls back to FXF. If only ``zirepo`` is missing, the rate starts on 2009-08-24, the
  first fixing of the fresh cube, and the notice says so. CHF cash uses the same ACT/360 index as
  EUR cash (``cash_levels``, ``cash_returns``).
- ``cash_levels(rate, dates)``: the compounded cash index (1.0 at the first rate date) on
  ``dates``. ACT/360: between two rate dates the index grows by
  ``1 + rate * calendar days / 360``.
- ``cash_returns(rate, dates)``: ``levels[t] / levels[t-1] - 1``, indexed by ``dates[1:]``. A gap
  (weekend, holiday) is compounded day by day with the rate of each business day inside it.
  NaN before the first rate date and more than ``MAX_CARRY_DAYS`` after the last one.
- ``ECB_CREDIT``, ``ECB_ESTR_CREDIT``, ``FRED_CREDIT``, ``FRED_EONIA_CREDIT``,
  ``snb_credit(start)``: footer lines (the one that matches the sources actually used is in
  ``RateResult.credit``).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from factordesk.data.ecb import EcbError, load_ecb_series
from factordesk.data.fred import FredError, load_fred_series
from factordesk.data.snb import SnbError, load_snb_series

ESTR = ("EST", "B.EU000A2X2A25.WT")
EONIA = ("EON", "D.EONIA_TO.RATE")
FRED_ESTR_SERIES = "ECBESTRVOLWGTTRMDMNRT"
SPLICE_DATE = pd.Timestamp("2019-10-01")
"""First date on euro STR; earlier dates use EONIA."""
SARON = ("snbgwdzid", "SARON")
SARON_HISTORY = ("zirepo", "H0")
SARON_START = pd.Timestamp("2009-08-24")
"""First fixing of the fresh cube; the rate starts here when ``zirepo`` is missing."""
MAX_CARRY_DAYS = 5
"""The last rate is carried past its date for at most this many calendar days."""
ECB_ESTR_CREDIT = "Euro short-term rate: European Central Bank, ECB Data Portal."
ECB_CREDIT = "Euro short-term rate and EONIA: European Central Bank, ECB Data Portal."
FRED_CREDIT = (
    "Euro short-term rate: European Central Bank, via FRED, Federal Reserve Bank of St. Louis."
)
FRED_EONIA_CREDIT = FRED_CREDIT + " EONIA: European Central Bank, ECB Data Portal (cached copy)."


def snb_credit(start: pd.Timestamp) -> str:
    """The footer line for CHF cash: SARON, with the first date of the series used."""
    return (
        "Swiss franc overnight rate (SARON): Swiss National Bank data portal, "
        f"from {start:%Y-%m-%d}."
    )


@dataclass(frozen=True)
class RateResult:
    """The overnight rate (None when no source works), a notice, and the credit actually used."""

    rate: pd.Series | None
    notice: str | None = None
    credit: str | None = None


def load_eur_overnight(
    *,
    data_dir: Path | None = None,
    now: datetime | None = None,
    fetch_ecb: Callable[[str, str], str] | None = None,
    fetch_fred: Callable[[str], str] | None = None,
) -> RateResult:
    """EONIA spliced with euro STR; see the module docstring. ``fetch_*`` replace the downloads
    (tests)."""
    notes: list[str] = []
    try:
        estr, note = load_ecb_series(*ESTR, scale=0.01, data_dir=data_dir, now=now, fetch=fetch_ecb)
    except EcbError as exc:
        return _from_fred(str(exc), data_dir, now, fetch_fred)
    if note:
        notes.append(note)
    estr = estr[estr.index >= SPLICE_DATE]
    try:
        eonia, note = load_ecb_series(
            *EONIA, scale=0.01, data_dir=data_dir, now=now, fetch=fetch_ecb
        )
    except EcbError as exc:
        notes.append(f"EONIA is unavailable ({exc}); the EUR cash rate starts on 2019-10-01.")
        return RateResult(estr.rename("eur_rate"), " ".join(notes), ECB_ESTR_CREDIT)
    if note:
        notes.append(note)
    rate = pd.concat([eonia[eonia.index < SPLICE_DATE], estr]).rename("eur_rate")
    return RateResult(rate, " ".join(notes) or None, ECB_CREDIT)


def load_chf_overnight(
    *,
    data_dir: Path | None = None,
    now: datetime | None = None,
    fetch_snb: Callable[[str, str], str] | None = None,
) -> RateResult:
    """SARON from the SNB data portal; see the module docstring. ``fetch_snb`` replaces the
    downloads (tests)."""
    notes: list[str] = []
    try:
        fresh, note = load_snb_series(
            *SARON, scale=0.01, data_dir=data_dir, now=now, fetch=fetch_snb
        )
    except SnbError as exc:
        return RateResult(None, f"SARON is unavailable (Swiss National Bank: {exc}).")
    if note:
        notes.append(note)
    fresh = fresh[fresh.index >= SARON_START]
    try:
        history, note = load_snb_series(
            *SARON_HISTORY, scale=0.01, data_dir=data_dir, now=now, fetch=fetch_snb
        )
    except SnbError as exc:
        notes.append(
            f"The SARON history before 2009-08-24 is unavailable ({exc}); "
            "the CHF cash rate starts on 2009-08-24."
        )
        rate = fresh.rename("chf_rate")
        return RateResult(rate, " ".join(notes), snb_credit(rate.index[0]))
    if note:
        notes.append(note)
    rate = pd.concat([history, fresh[fresh.index > history.index[-1]]]).rename("chf_rate")
    return RateResult(rate, " ".join(notes) or None, snb_credit(rate.index[0]))


def _from_fred(
    ecb_reason: str,
    data_dir: Path | None,
    now: datetime | None,
    fetch_fred: Callable[[str], str] | None,
) -> RateResult:
    """Euro STR from FRED (ECB down); EONIA before the splice only from a cached ECB copy."""
    try:
        fred = load_fred_series(FRED_ESTR_SERIES, data_dir=data_dir, now=now, fetch=fetch_fred)
    except FredError as exc:
        return RateResult(
            None, f"The EUR cash rate is unavailable (ECB: {ecb_reason}; FRED: {exc})."
        )
    estr = (fred.values.dropna() / 100.0).rename("eur_rate")  # noqa: PD011
    estr = estr[estr.index >= SPLICE_DATE]
    notice = (
        f"The ECB could not be reached ({ecb_reason}); the euro short-term rate comes from FRED."
    )
    if fred.note:
        notice += " " + fred.note
    try:
        eonia, _ = load_ecb_series(*EONIA, scale=0.01, data_dir=data_dir, now=now, cache_only=True)
    except EcbError:
        notice += " The EUR cash rate starts on 2019-10-01."
        return RateResult(estr, notice, FRED_CREDIT)
    notice += " EONIA before 2019-10-01 comes from a cached ECB copy."
    rate = pd.concat([eonia[eonia.index < SPLICE_DATE], estr]).rename("eur_rate")
    return RateResult(rate, notice, FRED_EONIA_CREDIT)


def cash_levels(rate: pd.Series, dates: pd.DatetimeIndex) -> pd.Series:
    """The compounded ACT/360 cash index on ``dates``; see the module docstring."""
    r = rate.dropna()
    if r.empty:
        return pd.Series(np.nan, index=dates, name="cash")
    rate_days = r.index.to_numpy().astype("datetime64[D]")
    rates = r.to_numpy(dtype="float64")
    # Index level at each rate date: each rate runs until the next rate date.
    step = 1.0 + rates[:-1] * np.diff(rate_days).astype(float) / 360.0
    base = np.concatenate([[1.0], np.cumprod(step)])
    pos = np.asarray(r.index.searchsorted(dates, side="right")) - 1
    safe = np.maximum(pos, 0)
    since = (dates.to_numpy().astype("datetime64[D]") - rate_days[safe]).astype(float)
    level = base[safe] * (1.0 + rates[safe] * since / 360.0)
    too_late = (pos == len(r) - 1) & (since > MAX_CARRY_DAYS)
    level[(pos < 0) | too_late] = np.nan
    return pd.Series(level, index=dates, name="cash")


def cash_returns(rate: pd.Series, dates: pd.DatetimeIndex) -> pd.Series:
    """Cash return over each interval of ``dates``, indexed by ``dates[1:]``."""
    level = cash_levels(rate, dates)
    return (level / level.shift(1) - 1.0).iloc[1:].rename("cash")
