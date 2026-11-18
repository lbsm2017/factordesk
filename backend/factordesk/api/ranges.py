"""Range presets to dates, preset availability and request checks (dashboard spec DB2.4).

Pure: no I/O and no clock. The anchor is the earlier of the last factor date and the last price
date. ``NY`` starts N calendar years before the anchor plus one day (29 February maps to
28 February first); FULL has no start. Every preset leaves the end open, so the requested range
runs to the last price date and the days after the factor data are reported as not analysed,
exactly like the static report.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import date, timedelta

import pandas as pd

from factordesk.analytics.sample import (
    MIN_OBS,
    DegenerateInputError,
    InsufficientHistoryError,
    build_sample,
)
from factordesk.api.errors import ApiException
from factordesk.data.prices import PriceHistory
from factordesk.report.schema import RANGE_PRESETS, RangeOption, RangeOptions, RangePreset

_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")

_COUNT_ONLY = sys.maxsize
"""A minimum no sample can meet: ``build_sample`` then reports the aligned row count through
``InsufficientHistoryError`` before any later check runs."""


def long_date(day: date) -> str:
    """``8 Aug 2024``: the report's date wording, independent of the locale."""
    return f"{day.day} {_MONTHS[day.month - 1]} {day.year}"


def preset_label(preset: RangePreset) -> str:
    """The name a person reads: ``Full history`` for FULL, the preset itself otherwise."""
    return "Full history" if preset == "FULL" else preset


def years_back(anchor: date, years: int) -> date:
    """``anchor`` minus ``years`` calendar years; 29 February becomes 28 February."""
    year = anchor.year - years
    if anchor.month == 2 and anchor.day == 29:
        return date(year, 2, 28)
    return anchor.replace(year=year)


def preset_start(preset: RangePreset, anchor: date) -> date | None:
    """First requested date of ``preset`` ending at ``anchor`` (None for FULL)."""
    if preset == "FULL":
        return None
    return years_back(anchor, int(preset.removesuffix("Y"))) + timedelta(days=1)


@dataclass(frozen=True)
class Coverage:
    """The dates a request is resolved against."""

    first_return_date: date
    last_price_date: date
    factors_last_date: date

    @property
    def anchor(self) -> date:
        return min(self.factors_last_date, self.last_price_date)


def _day(value: object) -> date:
    return pd.Timestamp(str(value)).date()


def unique_dates(history: PriceHistory) -> PriceHistory:
    """``factordesk.pipeline.unique_dates``, imported on first use.

    The pipeline pulls in statsmodels and scipy, which take seconds to load; importing it here
    would delay the start of the server. The first report request pays for it instead.
    """
    from factordesk.pipeline import unique_dates as collapse

    return collapse(history)


def coverage(history: PriceHistory, factor_frame: pd.DataFrame) -> Coverage:
    """First return date, last price date and last factor date of the inputs.

    A history with fewer than two prices has no return at all and is refused like any other
    history that is too short.
    """
    index = unique_dates(history).frame.index
    if len(index) < 2:
        raise InsufficientHistoryError(0, MIN_OBS)
    if len(factor_frame.index) == 0:
        raise ValueError("the factor frame is empty")
    return Coverage(
        first_return_date=_day(index[1]),
        last_price_date=_day(index[-1]),
        factors_last_date=_day(factor_frame.index[-1]),
    )


def check_request(preset: RangePreset | None, start: date | None, end: date | None) -> None:
    """Refuse a range given with dates, or a start after the end, before any data is fetched."""
    if preset is not None and (start is not None or end is not None):
        raise ApiException(
            "bad_range",
            "Both a range and dates were given.",
            "Choose either a range or start and end dates, not both.",
        )
    if start is not None and end is not None and start > end:
        raise ApiException(
            "bad_range",
            f"The start date {long_date(start)} is after the end date {long_date(end)}.",
            "Choose a start date before the end date.",
        )


def resolve(
    preset: RangePreset | None, start: date | None, end: date | None, cov: Coverage
) -> tuple[date | None, date | None]:
    """The (start, end) the pipeline receives; None stands for the edge of the price history.

    A preset gives its start and an open end. Custom dates are passed as given, except that a
    date equal to the edge of the history becomes None, so ``range=3Y`` and the same explicit
    dates share one cache entry and FULL equals the whole history given as dates. An end after
    the factor data is allowed: the report states the requested and the analysed dates.
    """
    check_request(preset, start, end)
    if preset is not None:
        return _open_edges(preset_start(preset, cov.anchor), None, cov)
    if start is not None and start > cov.last_price_date:
        raise ApiException(
            "bad_range",
            f"The start date {long_date(start)} is after the last price date "
            f"{long_date(cov.last_price_date)}.",
            "Choose an earlier start date.",
        )
    if end is not None and end < cov.first_return_date:
        raise ApiException(
            "bad_range",
            f"The end date {long_date(end)} is before the first return date "
            f"{long_date(cov.first_return_date)}.",
            "Choose a later end date.",
        )
    return _open_edges(start, end, cov)


def _open_edges(
    start: date | None, end: date | None, cov: Coverage
) -> tuple[date | None, date | None]:
    """A date on the edge of the history means the same as no date: write it as None."""
    return (
        None if start == cov.first_return_date else start,
        None if end == cov.last_price_date else end,
    )


def _aligned_rows(history: PriceHistory, factor_frame: pd.DataFrame, start: date | None) -> int:
    try:
        build_sample(history, factor_frame, start, None, min_obs=_COUNT_ONLY)
    except InsufficientHistoryError as exc:
        return exc.n
    raise AssertionError("no sample can reach the count-only minimum")  # pragma: no cover


def _option(
    preset: RangePreset,
    history: PriceHistory,
    factor_frame: pd.DataFrame,
    anchor: date,
    min_obs: int,
) -> RangeOption:
    start = preset_start(preset, anchor)
    label = preset_label(preset)
    try:
        n = build_sample(history, factor_frame, start, None, min_obs=min_obs).n
    except InsufficientHistoryError as exc:
        return RangeOption(
            preset=preset,
            start=start,
            n_obs=exc.n,
            available=False,
            reason=f"{label} has {exc.n} trading days; a regression needs at least {min_obs}.",
        )
    except DegenerateInputError as exc:
        n = _aligned_rows(history, factor_frame, start)
        return RangeOption(
            preset=preset,
            start=start,
            n_obs=n,
            available=False,
            reason=(
                f"{label} has {n} trading days (a regression needs at least {min_obs}) but "
                f"cannot be analysed: {exc.reason}."
            ),
        )
    return RangeOption(preset=preset, start=start, n_obs=n, available=True, reason=None)


def range_options(
    ticker: str, history: PriceHistory, factor_frame: pd.DataFrame, min_obs: int = MIN_OBS
) -> RangeOptions:
    """Availability of every preset for ``ticker``: aligned rows, and the reason when short."""
    history = unique_dates(history)
    cov = coverage(history, factor_frame)
    return RangeOptions(
        ticker=ticker,
        first_return_date=cov.first_return_date,
        last_price_date=cov.last_price_date,
        factors_last_date=cov.factors_last_date,
        min_obs=min_obs,
        options=[
            _option(preset, history, factor_frame, cov.anchor, min_obs) for preset in RANGE_PRESETS
        ],
    )
