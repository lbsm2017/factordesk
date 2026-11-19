"""The return subject: what a report is about, independent of where its returns came from.

One engine serves every mode (next-stage spec, Technical design). A report runs on a
``ReturnSubject``: a ticker (daily prices from Yahoo), an uploaded track record, or a backtested
portfolio, at a daily or monthly frequency. The pipeline, the analysis sample and the section
hooks read the subject only; a section that needs more (the price frame of a ticker) checks
``history``, which only ticker subjects carry.

Representation. ``calendar`` holds the subject's observation dates with the origin first (for a
ticker: every price date; for a monthly series: the month-end before the first return, then the
month-end of every return). ``returns[t]`` is the simple total return over
``(calendar[t-1], calendar[t]]``, so ``returns`` is indexed by ``calendar[1:]``; a missing level
gives NaN, never a filled value. ``levels`` is the level series on ``calendar`` (adjusted close
for a ticker, a growth-of-100 index for a return series) and is used for the chart and the data
audit only, never for a statistic.

Pure: no I/O, no clock. Inputs are not mutated.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Literal

import numpy as np
import pandas as pd

from factordesk.analytics.sample import (
    PERIODS_PER_YEAR,
    Frequency,
    all_month_ends,
    validate_date_index,
)
from factordesk.data.audit import AuditFinding
from factordesk.data.prices import PriceHistory

SubjectKind = Literal["ticker", "upload", "portfolio"]
SUBJECT_KINDS: tuple[SubjectKind, ...] = ("ticker", "upload", "portfolio")
FREQUENCIES: tuple[Frequency, ...] = ("daily", "monthly")
LEVEL_BASE = 100.0
"""Starting value of the level index built from a return series (growth of 100)."""
MONTH_END_DAYS = 7
"""A monthly return must be dated in the last 7 calendar days of its month (month-end stamp)."""


def _empty_meta() -> Mapping[str, str]:
    return MappingProxyType({})


@dataclass(frozen=True)
class ReturnSubject:
    """A return series and what the report needs to know about it (module docstring)."""

    kind: SubjectKind
    label: str
    """Display name: the ticker symbol, the fund name of an upload, the portfolio name."""
    frequency: Frequency
    returns: pd.Series
    """Simple total returns, decimals, indexed by ``calendar[1:]``; NaN where a level is missing."""
    calendar: pd.DatetimeIndex
    """Observation dates, the origin first (tz-naive, normalised, strictly increasing)."""
    levels: pd.Series
    """Price, NAV or index level on ``calendar`` (chart and audit only)."""
    source: str
    """Where the returns come from, e.g. ``"yfinance"`` or ``"upload"``."""
    currency: str | None = None
    """ISO currency of the returns; ``None`` when unknown."""
    history: PriceHistory | None = None
    """The price history behind a ticker subject; ``None`` for every other kind."""
    meta: Mapping[str, str] = field(default_factory=_empty_meta)
    """Free-form descriptive fields of the source (e.g. ``gross_net`` of an upload)."""
    findings: tuple[AuditFinding, ...] = ()
    """Data-quality findings raised while the subject was built (they join the audit)."""

    def __post_init__(self) -> None:
        if self.kind not in SUBJECT_KINDS:
            raise ValueError(f"unknown subject kind {self.kind!r}")
        if self.frequency not in FREQUENCIES:
            raise ValueError(f"unsupported frequency {self.frequency!r} (daily or monthly)")
        if not self.label.strip():
            raise ValueError("a return subject needs a non-empty label")
        what = f"{self.label} {'prices' if self.kind == 'ticker' else 'dates'}"
        calendar = validate_date_index(self.calendar, what)
        if not pd.DatetimeIndex(self.returns.index).equals(calendar[1:]):
            raise ValueError(f"{what}: returns must be indexed by the calendar after its origin")
        if not pd.DatetimeIndex(self.levels.index).equals(calendar):
            raise ValueError(f"{what}: levels must be indexed by the calendar")
        if self.frequency == "monthly" and not all_month_ends(calendar):
            raise ValueError(f"{what}: monthly dates must be calendar month-ends")
        if self.history is not None and (self.kind != "ticker" or self.frequency != "daily"):
            raise ValueError("only a daily ticker subject carries a price history")
        object.__setattr__(self, "meta", MappingProxyType(dict(self.meta)))

    @property
    def periods(self) -> int:
        """Observations a year: 252 daily, 12 monthly (the ``periods`` of the statistics)."""
        return PERIODS_PER_YEAR[self.frequency]


def subject_from_history(
    history: PriceHistory,
    *,
    label: str | None = None,
    currency: str | None = None,
    meta: Mapping[str, str] | None = None,
) -> ReturnSubject:
    """The daily ticker subject of a price history (repeated dates already collapsed).

    Returns are ``history.total_returns`` (from adjusted close, M1.3), the calendar is every
    price date and the levels are the adjusted close, so the analysis sample is exactly the one
    ``build_sample`` builds from the same history.
    """
    name = label or history.ticker
    calendar = validate_date_index(history.frame.index, f"{name} prices")
    return ReturnSubject(
        kind="ticker",
        label=name,
        frequency="daily",
        returns=history.total_returns,
        calendar=calendar,
        levels=history.frame["adj_close"].astype("float64"),
        source=history.source,
        currency=currency,
        history=history,
        meta=meta or {},
    )


def subject_from_monthly_returns(
    returns: pd.Series,
    *,
    label: str,
    kind: SubjectKind = "upload",
    source: str = "upload",
    currency: str | None = "USD",
    meta: Mapping[str, str] | None = None,
    findings: tuple[AuditFinding, ...] = (),
) -> ReturnSubject:
    """A monthly subject from one simple return per calendar month.

    Each date must fall in the last ``MONTH_END_DAYS`` calendar days of its month and is moved
    to its calendar month-end (a fund that reports on the last business day and the French file
    then share one stamp); a mid-month date raises ``ValueError`` naming the first such date.
    The months must be consecutive, one return each, finite and above -100%; anything else
    raises ``ValueError`` naming the first offending month. The origin is the month-end before
    the first return and the levels are a growth-of-100 index. Nothing is filled or dropped.
    """
    if kind == "ticker":
        raise ValueError("a ticker subject is built from its price history")
    if returns.empty:
        raise ValueError("no returns given")
    index = returns.index
    if not isinstance(index, pd.DatetimeIndex) or index.tz is not None:
        raise ValueError("returns must have a tz-naive DatetimeIndex")
    days = index.normalize()
    month_ends = pd.DatetimeIndex(days + pd.offsets.MonthEnd(0), name="date")
    early = np.flatnonzero((month_ends - days).days >= MONTH_END_DAYS)
    if early.size:
        when = pd.Timestamp(index[int(early[0])])
        raise ValueError(
            f"the date {when:%Y-%m-%d} is not in the last {MONTH_END_DAYS} days of its month; "
            f"date each monthly return at its month-end (for example "
            f"{pd.Timestamp(month_ends[int(early[0])]):%Y-%m-%d})"
        )
    if not month_ends.is_monotonic_increasing:
        raise ValueError("return dates must be in increasing order")
    if month_ends.has_duplicates:
        dup = pd.Timestamp(month_ends[month_ends.duplicated()][0])
        raise ValueError(f"more than one return in {dup:%Y-%m}")
    months = month_ends.to_period("M").asi8
    gaps = np.flatnonzero(np.diff(months) != 1)
    if gaps.size:
        after = pd.Timestamp(month_ends[int(gaps[0])])
        missing = (after + pd.offsets.MonthEnd(1)).strftime("%Y-%m")
        raise ValueError(f"months must be consecutive: no return for {missing}")
    values = returns.to_numpy(dtype=np.float64)
    bad = np.flatnonzero(~np.isfinite(values) | (values <= -1.0))
    if bad.size:
        when = pd.Timestamp(month_ends[int(bad[0])])
        raise ValueError(
            f"the return of {when:%Y-%m} is not a number above -100% ({values[int(bad[0])]!r})"
        )
    origin = pd.Timestamp(month_ends[0]) - pd.offsets.MonthEnd(1)
    calendar = pd.DatetimeIndex([origin, *month_ends], name="date")
    clean = pd.Series(values, index=month_ends, name=label)
    levels = pd.Series(
        LEVEL_BASE * np.concatenate([[1.0], np.cumprod(1.0 + values)]), index=calendar, name=label
    )
    return ReturnSubject(
        kind=kind,
        label=label,
        frequency="monthly",
        returns=clean,
        calendar=calendar,
        levels=levels,
        source=source,
        currency=currency,
        meta=meta or {},
        findings=findings,
    )
