"""Analysis sample and excess returns (methodology M2).

Aligns a ticker's daily total returns with the French factor file on dates and returns the
single sample ``S`` used by every statistic. Nothing is filled: each return row inside the
requested range is either aligned, or excluded with a date and a reason, or lies after the
factor file's last date (the uncovered tail, reported but never analysed).

Pure: no I/O, no clock. Inputs are not mutated.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Literal, cast

import numpy as np
import pandas as pd
from numpy.typing import NDArray

from factordesk.data.prices import PriceHistory

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

DISPLAY_NAMES: dict[str, str] = {code: name for name, code in FRENCH_COLUMNS.items()}

MIN_OBS = 504
"""Refusal threshold for a whole report (M0.7)."""
WARN_OBS = 750
"""Below this many rows the report carries a ``short_history`` warning (M0.7)."""
MIN_RETURN_SD = 1e-8
"""Daily total returns with a smaller sample sd mean the price does not move (M2 step 7)."""

ExclusionReason = Literal["multi_day_return", "no_factor_row", "price_missing", "factor_missing"]


class InsufficientHistoryError(ValueError):
    """Fewer aligned rows than the minimum sample: the report is refused (M0.7)."""

    def __init__(self, n: int, required: int) -> None:
        super().__init__(
            f"insufficient_history: {n} aligned daily observations, at least {required} required"
        )
        self.code = "insufficient_history"
        self.n = n
        self.required = required


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
    ``factors`` has exactly the columns ``FACTOR_CODES``.
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

    @property
    def n(self) -> int:
        return len(self.xret)

    @property
    def start(self) -> date:
        return _as_date(self.xret.index[0])

    @property
    def end(self) -> date:
        return _as_date(self.xret.index[-1])

    @property
    def short_history(self) -> bool:
        return self.n < WARN_OBS


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


def factor_frame_to_codes(factors: pd.DataFrame) -> pd.DataFrame:
    """Validate a French factor frame (decimals) and rename it to code names, canonical order."""
    validate_date_index(factors.index, "factor frame")
    missing = [c for c in FRENCH_COLUMNS if c not in factors.columns]
    if missing:
        raise ValueError(f"factor frame is missing columns {missing}")
    out = factors.loc[:, list(FRENCH_COLUMNS)].astype("float64").rename(columns=FRENCH_COLUMNS)
    out.index.name = "date"
    return out


def build_sample(
    history: PriceHistory,
    factors: pd.DataFrame,
    requested_start: date | None = None,
    requested_end: date | None = None,
    *,
    min_obs: int = MIN_OBS,
) -> AnalysisSample:
    """Align a ticker's total returns with the French factors (M2).

    ``factors`` is the frame from ``data.factors.load_ff5_daily`` (French column names,
    decimals). ``requested_start`` defaults to the first date with a return (the second price
    row) and ``requested_end`` to the last price date. Raises ``InsufficientHistoryError`` when
    fewer than ``min_obs`` rows align.
    """
    price_index = validate_date_index(history.frame.index, f"{history.ticker} prices")
    fac = factor_frame_to_codes(factors)
    if len(price_index) < 2:
        raise InsufficientHistoryError(0, min_obs)

    ret = history.total_returns  # index = price dates[1:]; NaN where a price is missing
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
    factor_nan = fac_on_ret.isna().any(axis=1).to_numpy()
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
        raise InsufficientHistoryError(n, min_obs)

    s_ret = ret[aligned].astype("float64")
    ret_sd = float(np.std(s_ret.to_numpy(dtype=np.float64), ddof=1))
    if not ret_sd >= MIN_RETURN_SD:
        raise DegenerateInputError(
            f"the price of {history.ticker} does not move over the sample (standard deviation "
            f"of daily returns {ret_sd:.1e}, below {MIN_RETURN_SD:.0e}); a factor regression "
            "would only describe the risk-free rate"
        )
    s_fac = fac.loc[s_dates, list(FACTOR_CODES)]
    s_rf = fac.loc[s_dates, "rf"]
    s_xret = s_ret - s_rf  # y_t = r_t - RF_t (M2 step 5)
    s_ret.name, s_rf.name, s_xret.name = "ret", "rf", "xret"
    for obj in (s_ret, s_rf, s_xret, s_fac):
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
    )
