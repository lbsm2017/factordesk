"""Analysis sample and excess returns (methodology M2).

Aligns a return series with the French factor file on dates and returns the single sample ``S``
used by every statistic. Nothing is filled: each return row inside the requested range is either
aligned, or excluded with a date and a reason, or lies after the factor file's last date (the
uncovered tail, reported but never analysed).

``align_returns`` is the frequency-free core: a return ``r_t`` covers the interval
``(calendar[t-1], calendar[t]]`` of the subject's own observation dates, and it aligns with a
factor row only when exactly one factor date falls in that interval and that date is ``t``
itself (M2 step 2). For daily data the dates are trading days; for monthly data both the
returns and the French monthly file are stamped at calendar month-ends, so a month aligns with
the factor month of the same name. ``build_sample`` (a ticker's price history, daily) and
``build_subject_sample`` (any ``ReturnSubject``) are thin wrappers that set the length floors:
daily samples are refused below 504 rows and warned below 750 (M0.7); monthly samples are
refused below 36 months and warned below 60 (next-stage research A1, practitioner convention).

Pure: no I/O, no clock. Inputs are not mutated.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING, Literal, cast

import numpy as np
import pandas as pd
from numpy.typing import NDArray

from factordesk.data.prices import PriceHistory

if TYPE_CHECKING:
    from factordesk.analytics.subject import ReturnSubject

FACTOR_CODES: tuple[str, ...] = ("mkt_rf", "smb", "hml", "rmw", "cma")
"""Canonical factor code names and order (M0.1)."""

FRENCH_COLUMNS: dict[str, str] = {
    "Mkt-RF": "mkt_rf",
    "SMB": "smb",
    "HML": "hml",
    "RMW": "rmw",
    "CMA": "cma",
    "RF": "rf",
}
"""French file column -> code name. ``data.factors`` returns the French names."""

EXTRA_FRENCH_COLUMNS: dict[str, str] = {"Mom": "mom"}
"""Optional factor columns: carried into the sample when the factor frame has them (the FF6
frame of ``data.french.load_ff6``), in ``AnalysisSample.extra_factors``."""
EXTRA_FACTOR_CODES: tuple[str, ...] = tuple(EXTRA_FRENCH_COLUMNS.values())
"""Code names of the optional factors, canonical order (after ``FACTOR_CODES``)."""

DISPLAY_NAMES: dict[str, str] = {
    code: name for name, code in (FRENCH_COLUMNS | EXTRA_FRENCH_COLUMNS).items()
}

Frequency = Literal["daily", "monthly"]
"""Observation frequency of a return series. Weekly data is refused for now (owner decision)."""

PERIODS_PER_YEAR: dict[Frequency, int] = {"daily": 252, "monthly": 12}
"""Observations a year, the ``periods`` of every annualised statistic (M0.4)."""

MIN_OBS = 504
"""Refusal threshold for a whole daily report (M0.7)."""
WARN_OBS = 750
"""Below this many daily rows the report carries a ``short_history`` warning (M0.7)."""
MIN_OBS_MONTHLY = 36
"""Refusal threshold for a whole monthly report (research A1: three years)."""
WARN_OBS_MONTHLY = 60
"""Below this many monthly rows the report carries a ``short_history`` warning (research A1)."""
SAMPLE_FLOORS: dict[Frequency, tuple[int, int]] = {
    "daily": (MIN_OBS, WARN_OBS),
    "monthly": (MIN_OBS_MONTHLY, WARN_OBS_MONTHLY),
}
"""``(refuse below, warn below)`` by frequency."""
MIN_RETURN_SD = 1e-8
"""Total returns with a smaller sample sd mean the price does not move (M2 step 7)."""

ExclusionReason = Literal["multi_day_return", "no_factor_row", "price_missing", "factor_missing"]


class InsufficientHistoryError(ValueError):
    """Fewer aligned rows than the minimum sample: the report is refused (M0.7)."""

    def __init__(
        self, n: int, required: int, detail: str | None = None, frequency: Frequency = "daily"
    ) -> None:
        message = (
            f"insufficient_history: {n} aligned {frequency} observations, at least {required} "
            "required"
        )
        super().__init__(f"{message} ({detail})" if detail else message)
        self.code = "insufficient_history"
        self.n = n
        self.required = required
        self.detail = detail
        # Why no row lines up, when that has a single clear cause (validation F14); else None.
        self.frequency: Frequency = frequency


class DegenerateInputError(ValueError):
    """The inputs cannot support a regression (D30): the report is refused with a reason.

    Raised when the price does not move over the sample (M2 step 7), when the factor design is
    singular or nearly so (M3.1), or when the dependent variable is constant.
    """

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.code = "degenerate_input"
        self.reason = reason


@dataclass(frozen=True)
class Exclusion:
    """A return row inside the analysed range that is not in ``S``."""

    date: date
    reason: ExclusionReason


@dataclass(frozen=True)
class UncoveredTail:
    """Ticker return dates after the factor file's last date (M2 step 6)."""

    n: int
    first: date | None
    last: date | None
    compounded_return: float | None
    """``prod(1 + ret) - 1`` over the tail (raw, not excess); None if empty or a value is NaN."""


@dataclass(frozen=True)
class AnalysisSample:
    """The aligned sample ``S`` (M2) plus everything needed to report how it was built.

    ``xret``, ``ret``, ``rf`` and ``factors`` share one ``date`` index (the rows of ``S``).
    ``factors`` has exactly the columns ``FACTOR_CODES``. ``extra_factors`` holds the optional
    factors the factor frame carried (``EXTRA_FACTOR_CODES`` present in it, e.g. ``mom``) on the
    same index, or is None; ``factor_columns`` reads any of them by code. The rows of ``S`` are
    set by the five factors only: an extra factor may be NaN on some rows, and a fit that uses
    it keeps the rows of ``complete_rows`` (the five-factor sample never loses a row to it).
    """

    xret: pd.Series
    ret: pd.Series
    rf: pd.Series
    factors: pd.DataFrame
    requested_start: date
    requested_end: date
    factor_first_date: date
    factor_last_date: date
    excluded: tuple[Exclusion, ...]
    uncovered: UncoveredTail
    n_before_factors: int
    frequency: Frequency = "daily"
    warn_obs: int = WARN_OBS
    """Below this many rows the sample is short (``short_history``)."""
    extra_factors: pd.DataFrame | None = None

    @property
    def n(self) -> int:
        return len(self.xret)

    @property
    def periods(self) -> int:
        """Observations a year at the sample's frequency (252 daily, 12 monthly)."""
        return PERIODS_PER_YEAR[self.frequency]

    @property
    def start(self) -> date:
        return _as_date(self.xret.index[0])

    @property
    def end(self) -> date:
        return _as_date(self.xret.index[-1])

    @property
    def short_history(self) -> bool:
        return self.n < self.warn_obs

    @property
    def factor_codes(self) -> tuple[str, ...]:
        """Every factor code the sample carries: ``FACTOR_CODES``, then the extra ones present."""
        extra = () if self.extra_factors is None else tuple(self.extra_factors.columns)
        return (*FACTOR_CODES, *extra)

    def complete_rows(self, codes: Sequence[str]) -> NDArray[np.bool_]:
        """Rows of ``S`` where the excess return and every factor of ``codes`` have a value.

        All True for the five factors; False where an extra factor (``mom``) is missing.
        """
        y = self.xret.to_numpy(dtype=np.float64)
        f = self.factor_columns(codes).to_numpy(dtype=np.float64)
        return np.asarray(np.isfinite(y) & np.isfinite(f).all(axis=1), dtype=np.bool_)

    def factor_columns(self, codes: Sequence[str]) -> pd.DataFrame:
        """The factor columns ``codes`` (in that order) on the sample's rows.

        Raises ``ValueError`` for a code the sample does not carry (``mom`` needs the FF6 frame).
        """
        available = self.factor_codes
        missing = [c for c in codes if c not in available]
        if missing:
            hint = (
                "; momentum needs the FF6 factor frame (data.french.load_ff6)"
                if "mom" in missing
                else ""
            )
            raise ValueError(f"the sample has no factor {missing}{hint}")
        parts = [self.factors]
        if self.extra_factors is not None:
            parts.append(self.extra_factors)
        frame = pd.concat(parts, axis=1) if len(parts) > 1 else self.factors
        return frame.loc[:, list(codes)]


def _as_date(value: object) -> date:
    return pd.Timestamp(cast(str, value)).date()


def validate_date_index(index: pd.Index, what: str) -> pd.DatetimeIndex:
    """Return ``index`` as a DatetimeIndex after checking the project's index contract.

    tz-naive, normalised, unique and strictly increasing (CODING_STANDARDS section 1).
    """
    if not isinstance(index, pd.DatetimeIndex):
        raise TypeError(f"{what}: index must be a DatetimeIndex, got {type(index).__name__}")
    if index.tz is not None:
        raise ValueError(f"{what}: index must be tz-naive")
    if not bool((index == index.normalize()).all()):
        raise ValueError(f"{what}: index must be normalised to midnight")
    if not index.is_unique or not index.is_monotonic_increasing:
        raise ValueError(f"{what}: index must be unique and strictly increasing")
    return index


def all_month_ends(index: pd.DatetimeIndex) -> bool:
    """True when every date is the last calendar day of its month.

    Computed from the day numbers, not ``DatetimeIndex.is_month_end``, which follows the index's
    ``freq`` (with ``freq="BME"`` it accepts business month-ends such as 2020-02-28).
    """
    days = np.asarray(index.day, dtype=np.int64)
    lengths = np.asarray(index.days_in_month, dtype=np.int64)
    return bool((days == lengths).all())


def infer_periods(index: pd.Index) -> int | None:
    """Observations a year implied by the spacing of ``index``: 252 or 12, or None if unclear.

    The median gap between consecutive dates decides: at most 5 calendar days is daily (252), 28
    to 31 days is monthly (12, calendar or business month-ends). Fewer than two dates, or any
    other spacing (weekly, quarterly), gives None.
    """
    dates = pd.DatetimeIndex(index)
    if len(dates) < 2:
        return None
    days = dates.to_numpy().astype("datetime64[D]").astype(np.int64)  # any datetime unit
    gap = float(np.median(np.diff(days)))
    if 0.0 < gap <= 5.0:
        return PERIODS_PER_YEAR["daily"]
    if 28.0 <= gap <= 31.0:
        return PERIODS_PER_YEAR["monthly"]
    return None


def factor_frame_to_codes(factors: pd.DataFrame) -> pd.DataFrame:
    """Validate a French factor frame (decimals) and rename it to code names, canonical order.

    The optional columns of ``EXTRA_FRENCH_COLUMNS`` (``Mom``) are kept, after the others, when
    the frame has them.
    """
    validate_date_index(factors.index, "factor frame")
    missing = [c for c in FRENCH_COLUMNS if c not in factors.columns]
    if missing:
        raise ValueError(f"factor frame is missing columns {missing}")
    columns = {**FRENCH_COLUMNS}
    columns.update({k: v for k, v in EXTRA_FRENCH_COLUMNS.items() if k in factors.columns})
    out = factors.loc[:, list(columns)].astype("float64").rename(columns=columns)
    out.index.name = "date"
    return out


def _no_rows_detail(
    in_range: NDArray[np.bool_],
    price_nan: NDArray[np.bool_],
    req_start: date,
    req_end: date,
    fac_first: date,
    fac_last: date,
) -> str | None:
    """Single clear cause when no row aligns (validation F14), or None when causes are mixed."""
    if not bool(in_range.any()):
        return (
            f"no price date falls in both the requested range ({req_start} to {req_end}) "
            f"and the factor data ({fac_first} to {fac_last})"
        )
    if bool(price_nan[in_range].all()):
        return "every price in the requested range is missing"
    return None


def build_sample(
    history: PriceHistory,
    factors: pd.DataFrame,
    requested_start: date | None = None,
    requested_end: date | None = None,
    *,
    min_obs: int = MIN_OBS,
) -> AnalysisSample:
    """Align a ticker's daily total returns with the French factors (M2).

    ``factors`` is the frame from ``data.factors.load_ff5_daily`` (French column names,
    decimals). ``requested_start`` defaults to the first date with a return (the second price
    row) and ``requested_end`` to the last price date. Raises ``InsufficientHistoryError`` when
    fewer than ``min_obs`` rows align. A wrapper over ``align_returns``.
    """
    return align_returns(
        history.total_returns,
        history.frame.index,
        factors,
        requested_start,
        requested_end,
        min_obs=min_obs,
        what=f"{history.ticker} prices",
        mover=f"the price of {history.ticker}",
    )


def build_subject_sample(
    subject: ReturnSubject,
    factors: pd.DataFrame,
    requested_start: date | None = None,
    requested_end: date | None = None,
) -> AnalysisSample:
    """Align any return subject with the French factors of its frequency (M2).

    Daily subjects need the daily factor frame, monthly subjects the monthly one (stamped at
    calendar month-ends, ``data.french.load_ff5_monthly``); a mismatch raises ``ValueError``.
    The floors are ``SAMPLE_FLOORS[subject.frequency]``: fewer rows raise
    ``InsufficientHistoryError``; fewer than the warning floor set ``short_history``.
    """
    fac_index = validate_date_index(factors.index, "factor frame")
    month_ends = all_month_ends(fac_index)
    if subject.frequency == "monthly" and not month_ends:
        raise ValueError(
            "monthly returns need the monthly French factor frame (one row per month, stamped "
            "at the calendar month-end); the frame given has other dates"
        )
    if subject.frequency == "daily" and month_ends and len(fac_index) > 2:
        raise ValueError(
            "daily returns need the daily French factor frame; the frame given looks monthly"
        )
    min_obs, warn_obs = SAMPLE_FLOORS[subject.frequency]
    ticker = subject.kind == "ticker"
    return align_returns(
        subject.returns,
        subject.calendar,
        factors,
        requested_start,
        requested_end,
        min_obs=min_obs,
        warn_obs=warn_obs,
        frequency=subject.frequency,
        what=f"{subject.label} {'prices' if ticker else 'dates'}",
        mover=f"the price of {subject.label}" if ticker else f"the return of {subject.label}",
    )


def align_returns(
    returns: pd.Series,
    calendar: pd.Index,
    factors: pd.DataFrame,
    requested_start: date | None = None,
    requested_end: date | None = None,
    *,
    min_obs: int = MIN_OBS,
    warn_obs: int = WARN_OBS,
    frequency: Frequency = "daily",
    what: str = "return series",
    mover: str = "the return series",
) -> AnalysisSample:
    """Align simple total returns with the French factors (M2), for any frequency.

    ``calendar`` holds the subject's observation dates, the origin first; ``returns`` (simple,
    decimals, NaN where a level is missing) is indexed by ``calendar[1:]`` and ``returns[t]``
    covers ``(calendar[t-1], calendar[t]]``. ``factors`` is a French frame of the same frequency
    (French column names, decimals). ``requested_start`` defaults to the first return date and
    ``requested_end`` to the last. ``what`` names the dates in index errors, ``mover`` the
    series in the "does not move" refusal. Raises ``InsufficientHistoryError`` when fewer than
    ``min_obs`` rows align, ``DegenerateInputError`` when the returns do not vary.
    """
    price_index = validate_date_index(calendar, what)
    fac = factor_frame_to_codes(factors)
    if len(price_index) < 2:
        raise InsufficientHistoryError(0, min_obs, "fewer than two price dates", frequency)
    if not pd.DatetimeIndex(returns.index).equals(price_index[1:]):
        raise ValueError(f"{what}: the returns must be indexed by the calendar after its origin")

    ret = returns  # index = calendar[1:]; NaN where a level is missing
    ret_dates = pd.DatetimeIndex(ret.index)
    req_start = requested_start or _as_date(ret_dates[0])
    req_end = requested_end or _as_date(ret_dates[-1])
    if req_start > req_end:
        raise ValueError(f"requested_start {req_start} is after requested_end {req_end}")

    fac_index = pd.DatetimeIndex(fac.index)
    fac_first, fac_last = _as_date(fac_index[0]), _as_date(fac_index[-1])
    lo = pd.Timestamp(max(req_start, fac_first))
    hi = pd.Timestamp(min(req_end, fac_last))

    # Number of French dates in (date_{t-1}, date_t] for every return row (M2 step 2).
    fac_values = fac_index.to_numpy()
    prev_dates = price_index[:-1].to_numpy()
    cur_dates = price_index[1:].to_numpy()
    n_in_interval = np.searchsorted(fac_values, cur_dates, side="right") - np.searchsorted(
        fac_values, prev_dates, side="right"
    )
    on_factor_date = np.isin(cur_dates, fac_values)

    in_range = (ret_dates >= lo) & (ret_dates <= hi)
    fac_on_ret = fac.reindex(ret_dates)  # rows absent from the French file become NaN here
    # Only the five factors and RF decide the rows of S; a missing extra factor (Mom) does not.
    core = [c for c in fac.columns if c not in EXTRA_FACTOR_CODES]
    factor_nan = fac_on_ret.loc[:, core].isna().any(axis=1).to_numpy()
    price_nan = ret.isna().to_numpy()

    reasons: list[ExclusionReason | None] = []
    for i in range(len(ret_dates)):
        if not on_factor_date[i]:
            reasons.append("no_factor_row")
        elif n_in_interval[i] >= 2:
            reasons.append("multi_day_return")
        elif price_nan[i]:
            reasons.append("price_missing")
        elif factor_nan[i]:
            reasons.append("factor_missing")
        else:
            reasons.append(None)
    reason_arr = np.array(reasons, dtype=object)
    aligned = in_range & np.array([r is None for r in reasons], dtype=bool)
    excluded = tuple(
        Exclusion(_as_date(d), cast(ExclusionReason, r))
        for d, r, keep in zip(ret_dates, reason_arr, in_range, strict=True)
        if keep and r is not None
    )

    tail_mask = (ret_dates > hi) & (ret_dates <= pd.Timestamp(req_end))
    tail = ret[tail_mask]
    tail_dates = pd.DatetimeIndex(tail.index)
    tail_values: NDArray[np.float64] = np.asarray(tail, dtype=np.float64)
    compounded = (
        float(np.prod(1.0 + tail_values) - 1.0)
        if tail_values.size and bool(np.isfinite(tail_values).all())
        else None
    )
    uncovered = UncoveredTail(
        n=len(tail),
        first=_as_date(tail_dates[0]) if len(tail) else None,
        last=_as_date(tail_dates[-1]) if len(tail) else None,
        compounded_return=compounded,
    )
    n_before = int(((ret_dates < lo) & (ret_dates >= pd.Timestamp(req_start))).sum())

    s_dates = ret_dates[aligned]
    n = len(s_dates)
    if n < min_obs:
        detail = (
            _no_rows_detail(in_range, price_nan, req_start, req_end, fac_first, fac_last)
            if n == 0
            else None
        )
        raise InsufficientHistoryError(n, min_obs, detail, frequency)

    s_ret = ret[aligned].astype("float64")
    ret_sd = float(np.std(s_ret.to_numpy(dtype=np.float64), ddof=1))
    if not ret_sd >= MIN_RETURN_SD:
        raise DegenerateInputError(
            f"{mover} does not move over the sample (standard deviation "
            f"of {frequency} returns {ret_sd:.1e}, below {MIN_RETURN_SD:.0e}); a factor regression "
            "would only describe the risk-free rate"
        )
    s_fac = fac.loc[s_dates, list(FACTOR_CODES)]
    extra_codes = [c for c in EXTRA_FACTOR_CODES if c in fac.columns]
    s_extra = fac.loc[s_dates, extra_codes] if extra_codes else None
    s_rf = fac.loc[s_dates, "rf"]
    s_xret = s_ret - s_rf  # y_t = r_t - RF_t (M2 step 5)
    s_ret.name, s_rf.name, s_xret.name = "ret", "rf", "xret"
    for obj in (s_ret, s_rf, s_xret, s_fac, *(() if s_extra is None else (s_extra,))):
        obj.index.name = "date"

    return AnalysisSample(
        xret=s_xret,
        ret=s_ret,
        rf=s_rf,
        factors=s_fac,
        requested_start=req_start,
        requested_end=req_end,
        factor_first_date=fac_first,
        factor_last_date=fac_last,
        excluded=excluded,
        uncovered=uncovered,
        n_before_factors=n_before,
        frequency=frequency,
        warn_obs=warn_obs,
        extra_factors=s_extra,
    )
