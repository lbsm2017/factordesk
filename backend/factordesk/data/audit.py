"""Adjusted-close audit (methodology M1.4): reports data problems, never fixes or drops anything.

Operates on the canonical frame produced by ``factordesk.data.prices`` (DatetimeIndex "date";
columns close, adj_close, dividends, splits, optional capital_gains and volume). The input is
never mutated; all work happens on copies.

Notation (M1.4): ``C`` close (split-adjusted), ``P`` adjusted close, ``rho_t = C_t / C_{t-1}``,
``g_t = P_t / P_{t-1}``, rounding tolerance ``tau_t = 1e-4 + 0.01 / C_{t-1}``. Yahoo's
``Adj Close`` follows the CRSP method, so on an ex-date with distribution ``Dist`` the expected
adjusted ratio is ``C_t / (C_{t-1} - Dist)`` (D9, D24). The plan's ``(C_t + D_t) / C_{t-1}``
differs from it by about ``(D/C) r`` per event and is deliberately not reported.
"""

from __future__ import annotations

import itertools
import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from typing import Literal

import numpy as np
import pandas as pd
from numpy.typing import NDArray

Severity = Literal["info", "warn", "error"]

# --- Constants of M1.4 (fixed, M15) ---
TAU_FLOAT = 1e-4
"""Float-noise allowance per ratio in ``tau_t``."""
TAU_CENTS = 0.01
"""Two half-cent roundings of ``Close`` (in price units) in ``tau_t``."""
YEAR_TAU_FLOAT = 1e-3
"""Float allowance per calendar year in ``tau_Y`` (A8)."""
LARGE_RETURN = 0.40
"""A4: absolute daily move flagged as extreme (kept in the sample)."""
MISSING_SPLIT_LOG = 0.15
"""A5: ``abs(ln(rho_t s_t))`` below this on a split row means Close was not split-adjusted."""
UNRECORDED_SPLIT_LOG = 0.03
"""A5b: ``abs(ln rho_t - ln(1/k))`` below this on an extreme day suggests an unrecorded split."""
SPLIT_FACTORS: tuple[float, ...] = (
    2,
    3,
    4,
    5,
    8,
    10,
    15,
    20,
    1 / 2,
    1 / 3,
    1 / 4,
    1 / 5,
    1 / 8,
    1 / 10,
    1 / 15,
    1 / 20,
)
MAX_MISSING_FRACTION = 0.10
"""A2: share of business days missing between the first and last date (D25)."""
MAX_GAP_BDAYS = 7
"""A2: longest tolerated run of consecutive missing business days (9/11 closure was 4; D25)."""
STALE_RUN_LEN = 5
"""A3: identical consecutive closes that count as a stale run."""

DIV = "div"
DIV_CG = "div+cg"


@dataclass(frozen=True)
class AuditFinding:
    code: str
    severity: Severity
    message: str
    dates: tuple[date, ...]


@dataclass(frozen=True)
class AuditReport:
    findings: tuple[AuditFinding, ...]
    n_obs: int
    first_date: date
    last_date: date
    ok: bool  # True when there is no "error" finding


def _dates(index: pd.Index) -> tuple[date, ...]:
    return tuple(pd.Timestamp(ts).date() for ts in index)


def rounding_tolerance(prev_close: float | pd.Series) -> float | pd.Series:
    """``tau_t = 1e-4 + 0.01 / C_{t-1}`` (M1.4)."""
    return TAU_FLOAT + TAU_CENTS / prev_close


def _clean_copy(frame: pd.DataFrame) -> pd.DataFrame:
    """Sorted copy with the first bar of every repeated date (as ingestion keeps it, D29)."""
    work = frame.copy()
    if not work.index.is_monotonic_increasing:
        work = work.sort_index(kind="stable")
    if not work.index.is_unique:
        work = work.loc[~work.index.duplicated(keep="first")]
    return work


def _column(work: pd.DataFrame, name: str) -> pd.Series:
    """A float column, or an all-zero series when the column is absent."""
    if name in work.columns:
        return work[name].astype("float64").fillna(0.0)
    return pd.Series(0.0, index=work.index, name=name)


@dataclass(frozen=True)
class _Ratios:
    close: pd.Series
    rho: pd.Series
    g: pd.Series
    prev: pd.Series
    tau: pd.Series
    div: pd.Series
    cg: pd.Series
    splits: pd.Series
    event: pd.Series
    has_cg: bool


def _ratios(work: pd.DataFrame) -> _Ratios:
    close = work["close"].astype("float64").where(lambda s: s > 0)
    adj = work["adj_close"].astype("float64").where(lambda s: s > 0)
    prev = close.shift(1)
    div = _column(work, "dividends")
    cg = _column(work, "capital_gains")
    event = ((div > 0) | (cg > 0)) & prev.notna()
    return _Ratios(
        close=close,
        rho=close / prev,
        g=adj / adj.shift(1),
        prev=prev,
        tau=TAU_FLOAT + TAU_CENTS / prev,
        div=div,
        cg=cg,
        splits=_column(work, "splits"),
        event=event,
        has_cg="capital_gains" in work.columns,
    )


FloatArray = NDArray[np.float64]


@dataclass(frozen=True)
class _Arrays:
    """Positional numpy views of ``_Ratios`` (row ``i`` of the cleaned frame)."""

    index: pd.DatetimeIndex
    close: FloatArray
    prev: FloatArray
    rho: FloatArray
    g: FloatArray
    tau: FloatArray
    div: FloatArray
    cg: FloatArray
    splits: FloatArray
    event: NDArray[np.bool_]
    has_cg: bool


def _arrays(r: _Ratios) -> _Arrays:
    def f(s: pd.Series) -> FloatArray:
        return s.to_numpy(dtype=np.float64)

    return _Arrays(
        index=pd.DatetimeIndex(r.close.index),
        close=f(r.close),
        prev=f(r.prev),
        rho=f(r.rho),
        g=f(r.g),
        tau=f(r.tau),
        div=f(r.div),
        cg=f(r.cg),
        splits=f(r.splits),
        event=r.event.to_numpy(dtype=bool),
        has_cg=r.has_cg,
    )


@dataclass(frozen=True)
class _Event:
    pos: int
    delta_div: float
    delta_div_cg: float
    tau: float
    convention: str | None
    discrepancy: float
    expected: float
    d_implied: float


def _events(a: _Arrays) -> list[_Event]:
    """A6 per distribution event whose prices exist (positions in the cleaned frame)."""
    out: list[_Event] = []
    valid = a.event & np.isfinite(a.g) & np.isfinite(a.close)
    for pos in np.flatnonzero(valid):
        i = int(pos)
        c, prev, g = float(a.close[i]), float(a.prev[i]), float(a.g[i])
        d, cg = float(a.div[i]), float(a.cg[i])
        candidates: list[tuple[str, float, float]] = []
        for name, dist in ((DIV, d), (DIV_CG, d + cg)):
            if name == DIV_CG and (not a.has_cg or cg <= 0):
                continue
            if prev - dist > 0:
                expected = c / (prev - dist)
                candidates.append((name, math.log(g) - math.log(expected), expected))
        best = min(candidates, key=lambda x: abs(x[1])) if candidates else None
        matched = best is not None and abs(best[1]) <= float(a.tau[i])
        div_entry = next((x for x in candidates if x[0] == DIV), None)
        cg_entry = next((x for x in candidates if x[0] == DIV_CG), None)
        fallback = best if matched else div_entry
        out.append(
            _Event(
                pos=i,
                delta_div=div_entry[1] if div_entry else math.nan,
                delta_div_cg=cg_entry[1] if cg_entry else math.nan,
                tau=float(a.tau[i]),
                convention=best[0] if (best is not None and matched) else None,
                discrepancy=abs(best[1]) if best is not None else math.nan,
                expected=fallback[2] if fallback is not None else math.nan,
                d_implied=prev - c / g,
            )
        )
    return out


def distribution_checks(frame: pd.DataFrame) -> pd.DataFrame:
    """A6 per distribution event: discrepancy per convention, tolerance, matched convention.

    Columns: ``delta_div`` (``ln g - ln(C_t / (C_{t-1} - D_t))``), ``delta_div_cg`` (same with
    ``D_t + G_t``; NaN without a capital-gains column), ``tau``, ``convention`` (``"div"``,
    ``"div+cg"`` or ``None`` when neither is within ``tau``), ``discrepancy`` (smallest absolute
    delta), ``expected`` (the matched expected ratio, convention ``div`` when unmatched) and
    ``d_implied`` (``C_{t-1} - C_t / g_t``). Rows whose prices are missing are left out.
    """
    a = _arrays(_ratios(_clean_copy(frame)))
    events = _events(a)
    return pd.DataFrame(
        {
            "delta_div": [e.delta_div for e in events],
            "delta_div_cg": [e.delta_div_cg for e in events],
            "tau": [e.tau for e in events],
            "convention": [e.convention for e in events],
            "discrepancy": [e.discrepancy for e in events],
            "expected": [e.expected for e in events],
            "d_implied": [e.d_implied for e in events],
        },
        index=a.index[[e.pos for e in events]],
    )


def _day(index: pd.DatetimeIndex, pos: int) -> date:
    return pd.Timestamp(index[pos]).date()


def _check_distributions(r: _Ratios) -> list[AuditFinding]:
    """A6, A7, A8 and the informational summary (M1.4)."""
    findings: list[AuditFinding] = []
    a = _arrays(r)
    events = _events(a)

    unmatched = [e for e in events if e.convention is None]
    if unmatched:
        details = [
            f"{_day(a.index, e.pos)}: recorded "
            f"{float(a.div[e.pos]) + (float(a.cg[e.pos]) if a.has_cg else 0.0):.4f}, implied by "
            f"Adj Close {e.d_implied:.4f} per share"
            for e in unmatched[:3]
        ]
        more = f"; and {len(unmatched) - 3} more" if len(unmatched) > 3 else ""
        findings.append(
            AuditFinding(
                "distribution_mismatch",
                "error",
                f"{len(unmatched)} of {len(events)} distribution events do not match the "
                "adjustment Adj Close should carry (C_t / (C_{t-1} - D_t), CRSP method, tolerance "
                "1e-4 + 0.01 / C_{t-1}): " + "; ".join(details) + more + ".",
                tuple(_day(a.index, e.pos) for e in unmatched),
            )
        )

    with_gains = [e for e in events if a.has_cg and float(a.cg[e.pos]) > 0 and e.convention]
    if {DIV, DIV_CG} <= {e.convention for e in with_gains}:
        findings.append(
            AuditFinding(
                "inconsistent_capital_gains_treatment",
                "warn",
                "Capital-gain distributions are adjusted inconsistently: some events match "
                "dividends alone, others dividends plus capital gains (one of them may be "
                "double counted).",
                tuple(_day(a.index, e.pos) for e in with_gains),
            )
        )

    # A7: on days without a distribution or split, the adjusted ratio equals the close ratio.
    log_g = np.log(a.g)
    a7_rows = ~a.event & np.isin(a.splits, [0.0, 1.0]) & np.isfinite(a.g) & np.isfinite(a.rho)
    a7_disc = np.where(a7_rows, np.abs(log_g - np.log(a.rho)), np.nan)
    a7_bad = np.flatnonzero(a7_rows & (np.nan_to_num(a7_disc) > a.tau))
    if a7_bad.size:
        worst = int(a7_bad[np.argmax(a7_disc[a7_bad])])
        findings.append(
            AuditFinding(
                "adjustment_on_non_event_day",
                "warn",
                f"Adj Close moves differently from Close beyond the rounding tolerance on "
                f"{a7_bad.size} day(s) without a distribution or split (worst "
                f"{float(a7_disc[worst]) * 1e4:.2f} bp on {_day(a.index, worst)}): an "
                "adjustment may sit on the wrong day.",
                tuple(_day(a.index, int(i)) for i in a7_bad),
            )
        )

    # A8: calendar-year drift of ln g against the expected log ratio.
    expected = a.rho.copy()
    for e in events:
        expected[e.pos] = e.expected
    dev = log_g - np.log(expected)
    years = a.index.year.to_numpy()
    year_rows: list[tuple[int, float, float, int]] = []  # (year, Delta_Y, tau_Y, last position)
    for year in np.unique(years):
        rows = years == year
        devs = dev[rows][np.isfinite(dev[rows])]
        if devs.size == 0:
            continue
        closes = a.close[rows][np.isfinite(a.close[rows])]
        n_ev = int(a.event[rows].sum())
        tau_y = YEAR_TAU_FLOAT + (n_ev + 1) * TAU_CENTS / float(closes.min())
        year_rows.append((int(year), float(devs.sum()), tau_y, int(np.flatnonzero(rows)[-1])))
    bad_years = [y for y in year_rows if abs(y[1]) > y[2]]
    if bad_years:
        listing = ", ".join(
            f"{y}: {d * 1e4:+.1f} bp (tolerance {t * 1e4:.1f} bp)" for y, d, t, _ in bad_years
        )
        findings.append(
            AuditFinding(
                "calendar_year_drift",
                "error",
                "Adj Close drifts away from Close and the recorded distributions within a "
                f"calendar year: {listing}.",
                tuple(_day(a.index, last) for *_, last in bad_years),
            )
        )

    # Informational summary (no plan-formula figure, D9).
    a7_finite = a7_disc[np.isfinite(a7_disc)]
    a7_max = float(a7_finite.max()) if a7_finite.size else 0.0
    year_max = max((abs(d) for _, d, _, _ in year_rows), default=0.0)
    tau_min = min((t for _, _, t, _ in year_rows), default=math.nan)
    if events:
        n_div = sum(1 for e in events if e.convention == DIV)
        n_cg = sum(1 for e in events if e.convention == DIV_CG)
        taus = [e.tau for e in events]
        head = (
            f"{len(events)} distribution events checked against the CRSP adjustment "
            f"C_t / (C_{{t-1}} - D_t): largest discrepancy "
            f"{max(e.discrepancy for e in events) * 1e4:.3f} bp (tolerance "
            f"{min(taus) * 1e4:.1f}-{max(taus) * 1e4:.1f} bp); conventions matched: div "
            f"{n_div}, div+cg {n_cg}" + (f", none {len(unmatched)}" if unmatched else "") + ". "
        )
    else:
        head = "No distribution events. "
    cumulative = float(np.nansum(dev))
    findings.append(
        AuditFinding(
            "distribution_summary",
            "info",
            head
            + f"Largest discrepancy on other days {a7_max * 1e4:.3f} bp; largest calendar-year "
            f"drift {year_max * 1e4:.3f} bp (smallest yearly tolerance {tau_min * 1e4:.1f} bp); "
            f"cumulative drift {cumulative * 1e4:+.3f} bp.",
            (),
        )
    )
    return findings


def _check_index(frame: pd.DataFrame, duplicate_dates: Sequence[date]) -> list[AuditFinding]:
    """A1 index integrity on the original order, plus duplicates recorded at ingestion."""
    findings: list[AuditFinding] = []
    in_frame = _dates(frame.index[frame.index.duplicated(keep=False)].unique())
    recorded = tuple(sorted(set(duplicate_dates)))
    if in_frame or recorded:
        dates = tuple(sorted(set(in_frame) | set(recorded)))
        parts: list[str] = []
        if recorded:
            parts.append(
                f"{len(recorded)} date(s) were delivered more than once by the price source; "
                "the first bar of each was kept, so the returns around them depend on which bar "
                "is right"
            )
        if in_frame:
            parts.append(f"{len(in_frame)} date(s) appear on more than one row")
        findings.append(AuditFinding("duplicate_index", "error", "; ".join(parts) + ".", dates))
    if not frame.index.is_monotonic_increasing:
        backward = frame.index[1:][np.asarray(frame.index[1:] < frame.index[:-1])]
        findings.append(
            AuditFinding(
                "non_increasing_index", "error", "Index is not increasing", _dates(backward)
            )
        )
    return findings


def _check_prices(work: pd.DataFrame) -> list[AuditFinding]:
    """A1 sanity: NaN or non-positive prices."""
    findings: list[AuditFinding] = []
    for col in ("close", "adj_close"):
        s = work[col].astype("float64")
        nan_idx = s.index[s.isna()]
        if len(nan_idx):
            findings.append(
                AuditFinding(
                    "nan_price", "error", f"{len(nan_idx)} NaN values in {col}", _dates(nan_idx)
                )
            )
        bad_idx = s.index[s <= 0]  # NaN compares False, so only real values are caught
        if len(bad_idx):
            findings.append(
                AuditFinding(
                    "non_positive_price",
                    "error",
                    f"{len(bad_idx)} zero or negative values in {col}",
                    _dates(bad_idx),
                )
            )
    return findings


def _check_large_returns(r: _Ratios) -> list[AuditFinding]:
    """A4: ``abs(g_t - 1) > 0.40`` or ``abs(rho_t - 1) > 0.40`` (D26)."""
    flagged = ((r.g - 1.0).abs() > LARGE_RETURN) | ((r.rho - 1.0).abs() > LARGE_RETURN)
    idx = r.close.index[flagged.fillna(False).to_numpy(dtype=bool)]
    if len(idx) == 0:
        return []
    return [
        AuditFinding(
            "large_return",
            "warn",
            f"{len(idx)} days with |daily return| > {LARGE_RETURN:.0%} (kept, not dropped)",
            _dates(idx),
        )
    ]


def _check_gaps(work: pd.DataFrame) -> list[AuditFinding]:
    """A2 as decided in D25: long runs of missing business days, or many missing days."""
    if len(work) < 2:
        return []
    bdays = pd.bdate_range(work.index[0], work.index[-1])
    present = bdays.isin(work.index)
    n_missing = int((~present).sum())
    findings: list[AuditFinding] = []
    fraction = n_missing / len(bdays)
    if fraction > MAX_MISSING_FRACTION:
        findings.append(
            AuditFinding(
                "gaps_fraction",
                "warn",
                f"{fraction:.1%} of business days are missing (limit {MAX_MISSING_FRACTION:.0%})",
                (),
            )
        )
    starts: list[pd.Timestamp] = []
    lengths: list[int] = []
    pos = 0
    for is_present, group in itertools.groupby(present.tolist()):
        run = len(list(group))
        if not is_present and run > MAX_GAP_BDAYS:
            starts.append(bdays[pos])
            lengths.append(run)
        pos += run
    if starts:
        findings.append(
            AuditFinding(
                "gap_run",
                "warn",
                f"{len(starts)} gap(s) longer than {MAX_GAP_BDAYS} consecutive business days "
                f"(longest {max(lengths)})",
                _dates(pd.DatetimeIndex(starts)),
            )
        )
    return findings


def _check_stale(work: pd.DataFrame) -> list[AuditFinding]:
    """A3: 5 or more identical consecutive closes (warning with volume, info without; D26)."""
    close = work["close"].astype("float64")
    if close.empty:
        return []
    run_id = (close != close.shift(1)).cumsum()  # NaN != NaN, so NaN never extends a run
    sizes = close.groupby(run_id).transform("size")
    long_run = (sizes >= STALE_RUN_LEN) & close.notna()
    if not bool(long_run.any()):
        return []
    starts = close.index[long_run & (close != close.shift(1))]
    has_volume = "volume" in work.columns
    severity: Severity = "warn" if has_volume else "info"
    suffix = "" if has_volume else " (no volume column to confirm)"
    return [
        AuditFinding(
            "stale_run",
            severity,
            f"{len(starts)} run(s) of {STALE_RUN_LEN}+ identical consecutive closes{suffix}",
            _dates(starts),
        )
    ]


def _check_splits(r: _Ratios) -> list[AuditFinding]:
    """A5 (recorded split, Close not adjusted) and A5b (extreme move that looks like a split)."""
    findings: list[AuditFinding] = []
    log_rho = np.log(r.rho)
    recorded = r.splits.notna() & ~r.splits.isin([0.0, 1.0]) & r.rho.notna()
    a5: list[pd.Timestamp] = []
    for ts in r.splits.index[recorded]:
        lr = float(np.log(float(r.rho[ts]) * float(r.splits[ts])))
        if abs(lr) < MISSING_SPLIT_LOG and abs(lr) < abs(float(log_rho[ts])):
            a5.append(pd.Timestamp(ts))
    if a5:
        findings.append(
            AuditFinding(
                "suspected_missing_split_adjustment",
                "error",
                f"{len(a5)} split date(s) where Close moved by the share-count ratio: Close "
                "looks unadjusted, so returns across them are wrong",
                _dates(pd.DatetimeIndex(a5)),
            )
        )
    candidates = r.splits.isin([0.0, 1.0]) & ((r.g - 1.0).abs() > LARGE_RETURN) & r.rho.notna()
    a5b: list[pd.Timestamp] = []
    ratios: list[str] = []
    for ts in r.splits.index[candidates.fillna(False).to_numpy(dtype=bool)]:
        lr = float(log_rho[ts])
        k = min(SPLIT_FACTORS, key=lambda f: abs(lr - np.log(1.0 / f)))
        if abs(lr - float(np.log(1.0 / k))) < UNRECORDED_SPLIT_LOG:
            a5b.append(pd.Timestamp(ts))
            label = f"{k:g}:1" if k >= 1 else f"1:{1 / k:g}"
            ratios.append(f"{pd.Timestamp(ts).date()} ({label})")
    if a5b:
        findings.append(
            AuditFinding(
                "possible_unrecorded_split",
                "warn",
                "Close moved by a typical split ratio with no split recorded: "
                + ", ".join(ratios)
                + ". If a split happened, the history before it is not adjusted.",
                _dates(pd.DatetimeIndex(a5b)),
            )
        )
    return findings


def audit_prices(frame: pd.DataFrame, *, duplicate_dates: Sequence[date] = ()) -> AuditReport:
    """Audit a canonical price frame (M1.4). Findings only: nothing is repaired or dropped.

    ``duplicate_dates`` are dates the price source delivered more than once and that ingestion
    collapsed to their first bar (``PriceHistory.duplicate_dates``); they are reported as A1
    errors together with any duplicates still present in ``frame``.
    """
    findings: list[AuditFinding] = []
    n_obs = len(frame)

    if not isinstance(frame.index, pd.DatetimeIndex) or n_obs == 0:
        reason = "empty frame" if n_obs == 0 else "index is not a DatetimeIndex"
        findings.append(AuditFinding("invalid_frame", "error", f"Cannot audit: {reason}", ()))
        return AuditReport(tuple(findings), n_obs, date.min, date.min, False)

    missing_cols = [c for c in ("close", "adj_close") if c not in frame.columns]
    first_date = pd.Timestamp(frame.index.min()).date()
    last_date = pd.Timestamp(frame.index.max()).date()
    if missing_cols:
        findings.append(
            AuditFinding("missing_columns", "error", f"Missing columns: {missing_cols}", ())
        )
        return AuditReport(tuple(findings), n_obs, first_date, last_date, False)

    findings += _check_index(frame, duplicate_dates)  # A1 index
    work = _clean_copy(frame)
    ratios = _ratios(work)
    findings += _check_prices(work)  # A1 values
    findings += _check_gaps(work)  # A2
    findings += _check_stale(work)  # A3
    findings += _check_large_returns(ratios)  # A4
    findings += _check_splits(ratios)  # A5, A5b
    findings += _check_distributions(ratios)  # A6, A7, A8, summary

    return AuditReport(
        findings=tuple(findings),
        n_obs=n_obs,
        first_date=first_date,
        last_date=last_date,
        ok=not any(f.severity == "error" for f in findings),
    )


# --------------------------------------------------------------------------- level series
LevelFrequency = Literal["daily", "monthly"]
_LEVEL_UNIT: dict[LevelFrequency, str] = {"daily": "days", "monthly": "months"}


def audit_levels(levels: pd.Series, frequency: LevelFrequency) -> AuditReport:
    """Audit the level series of a return subject that has no price frame (an upload, a backtest).

    The series is a NAV or a growth index built from returns, so there is no Close/Adj Close
    pair, no distribution and no split to check (A5-A8 do not apply). What is checked, findings
    only, nothing repaired or dropped:

    * A1: duplicate or decreasing dates (error), missing or non-positive levels (error);
    * A2: gaps. Daily: the business-day rule of D25; monthly: a calendar month with no level
      between two that have one (warning);
    * A3: five or more identical consecutive levels, i.e. four or more returns of exactly zero
      in a row (warning: with no volume to explain it, a frozen value is a data-quality flag);
    * A4: a return of more than 40% in absolute value in one period (warning, kept).
    """
    findings: list[AuditFinding] = []
    n_obs = len(levels)
    if not isinstance(levels.index, pd.DatetimeIndex) or n_obs == 0:
        reason = "empty series" if n_obs == 0 else "index is not a DatetimeIndex"
        findings.append(AuditFinding("invalid_frame", "error", f"Cannot audit: {reason}", ()))
        return AuditReport(tuple(findings), n_obs, date.min, date.min, False)
    unit = _LEVEL_UNIT[frequency]
    frame = pd.DataFrame({"close": levels.astype("float64")})
    findings += _check_index(frame, ())
    work = _clean_copy(frame)
    value = work["close"]
    for code, mask, what in (
        ("nan_price", value.isna(), "missing"),
        ("non_positive_price", value <= 0, "zero or negative"),
    ):
        idx = value.index[mask.to_numpy(dtype=bool)]
        if len(idx):
            findings.append(
                AuditFinding(code, "error", f"{len(idx)} {what} level value(s)", _dates(idx))
            )
    if frequency == "daily":
        findings += _check_gaps(work)
    else:
        months = pd.DatetimeIndex(work.index).to_period("M").asi8
        jumps = np.flatnonzero(np.diff(months) > 1)
        if jumps.size:
            starts = pd.DatetimeIndex(work.index[jumps])
            findings.append(
                AuditFinding(
                    "gap_run",
                    "warn",
                    f"{jumps.size} gap(s) of at least one calendar month with no level",
                    _dates(starts),
                )
            )
    positive = value.where(value > 0)
    run_id = (positive != positive.shift(1)).cumsum()
    sizes = positive.groupby(run_id).transform("size")
    long_run = (sizes >= STALE_RUN_LEN) & positive.notna()
    if bool(long_run.any()):
        starts = positive.index[(long_run & (positive != positive.shift(1))).to_numpy(dtype=bool)]
        findings.append(
            AuditFinding(
                "stale_run",
                "warn",
                f"{len(starts)} run(s) of {STALE_RUN_LEN}+ identical consecutive levels "
                f"(returns of exactly zero for {STALE_RUN_LEN - 1}+ {unit} in a row)",
                _dates(starts),
            )
        )
    ratio = positive / positive.shift(1)
    large = ((ratio - 1.0).abs() > LARGE_RETURN).to_numpy(dtype=bool)
    if bool(large.any()):
        idx = positive.index[large]
        findings.append(
            AuditFinding(
                "large_return",
                "warn",
                f"{len(idx)} {unit} with |return| > {LARGE_RETURN:.0%} (kept, not dropped)",
                _dates(idx),
            )
        )
    return AuditReport(
        findings=tuple(findings),
        n_obs=n_obs,
        first_date=pd.Timestamp(work.index[0]).date(),
        last_date=pd.Timestamp(work.index[-1]).date(),
        ok=not any(f.severity == "error" for f in findings),
    )
