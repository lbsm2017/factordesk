"""Adjusted-close audit tests (test-oracle T22-T30, T119; methodology M1.4, D9, D24-D26, D29)."""

from __future__ import annotations

import math
from collections.abc import Sequence
from datetime import date

import numpy as np
import pandas as pd
import pytest

from factordesk.analytics.sample import build_sample
from factordesk.data.audit import AuditReport, audit_prices
from factordesk.data.prices import PriceHistory
from factordesk.tests.fixtures.dgp import FETCHED_AT, factor_frame, rng_for

N = 756  # 3 years of business days
EVENTS = tuple(range(40, N, 63))  # quarterly ex-dates (positions)


def crsp_frame(
    test_number: int,
    *,
    n: int = N,
    start: float = 100.0,
    events: Sequence[int] = EVENTS,
    dist: dict[int, float] | None = None,
    recorded_div: dict[int, float] | None = None,
    recorded_cg: dict[int, float] | None = None,
    late: Sequence[int] = (),
    with_cg_column: bool = False,
) -> pd.DataFrame:
    """CRSP-method fixture of test-oracle section 4.

    Unrounded close path (daily sd 0.015); distribution ``Dist`` at each event (default
    ``0.005 * c_{t-1}``); ``Adj Close_t = Close_t * prod_{tau > t} (1 - Dist_tau / c_{tau-1})``;
    ``Close`` rounded to cents and ``Adj Close`` to 6 decimals. ``recorded_*`` override what
    the ``dividends`` / ``capital_gains`` columns say; ``late`` applies those events'
    adjustment one row late in ``Adj Close``.
    """
    rng = rng_for(test_number)
    idx = pd.bdate_range("2020-01-02", periods=n, name="date")
    c = start * np.cumprod(1.0 + rng.normal(0.0002, 0.015, n))
    amounts = {t: (dist or {}).get(t, 0.005 * c[t - 1]) for t in events}
    factor = np.ones(n)
    for t, amount in amounts.items():
        at = t + 1 if t in late else t
        factor[:at] *= 1.0 - amount / c[t - 1]
    div = np.zeros(n)
    cg = np.zeros(n)
    for t, amount in amounts.items():
        div[t] = (recorded_div or {}).get(t, amount)
        cg[t] = (recorded_cg or {}).get(t, 0.0)
    frame = pd.DataFrame(
        {
            "close": np.round(c, 2),
            "adj_close": np.round(c * factor, 6),
            "dividends": div,
            "splits": np.zeros(n),
        },
        index=idx,
    )
    if with_cg_column or recorded_cg:
        frame["capital_gains"] = cg
    return frame


def codes(report: AuditReport, severity: str | None = None) -> set[str]:
    return {f.code for f in report.findings if severity is None or f.severity == severity}


def finding(report: AuditReport, code: str):  # noqa: ANN201 - test helper
    return next(f for f in report.findings if f.code == code)


def serious(report: AuditReport) -> list[str]:
    return [f.code for f in report.findings if f.severity in ("warn", "error")]


def ts(frame: pd.DataFrame, pos: int) -> date:
    return pd.Timestamp(frame.index[pos]).date()


def set_col(frame: pd.DataFrame, col: str, pos: slice | int, value: float) -> None:
    values = frame[col].to_numpy(dtype="float64", copy=True)
    values[pos] = value
    frame[col] = values


def scale_from(frame: pd.DataFrame, cols: Sequence[str], start: int, k: float) -> None:
    for col in cols:
        values = frame[col].to_numpy(dtype="float64", copy=True)
        values[start:] *= k
        frame[col] = values


# ----------------------------------------------------------------------------- T22
def test_t22_clean_series_with_recorded_split() -> None:
    frame = crsp_frame(22)
    set_col(frame, "splits", 400, 4.0)  # 4:1 recorded, Close already adjusted
    report = audit_prices(frame)
    assert report.ok and serious(report) == []
    assert "distribution_summary" in codes(report, "info")
    # D9: the plan's (C_t + D_t) / C_{t-1} is not what Adj Close encodes ...
    c, p, d = frame["close"], frame["adj_close"], frame["dividends"]
    plan = (c + d) / c.shift(1)
    g = p / p.shift(1)
    tau = 1e-4 + 0.01 / c.shift(1)
    events = (d > 0).to_numpy()
    gap = np.abs(np.log(g.to_numpy()) - np.log(plan.to_numpy()))[events]
    assert bool((gap > tau.to_numpy()[events] / 10).any())
    # ... and the audit does not report it.
    assert not any("+ D_t" in f.message or "plan" in f.message for f in report.findings)


def test_t22_summary_reports_the_crsp_discrepancy() -> None:
    report = audit_prices(crsp_frame(22))
    msg = finding(report, "distribution_summary").message
    assert f"{len(EVENTS)} distribution events" in msg
    assert "largest discrepancy" in msg and "bp" in msg


# ----------------------------------------------------------------------------- T23
def test_t23_missing_split_adjustment() -> None:
    frame = crsp_frame(23)
    pos = 400
    values_c = frame["close"].to_numpy(copy=True)
    values_p = frame["adj_close"].to_numpy(copy=True)
    values_c[:pos] *= 4.0  # history before the split left unadjusted
    values_p[:pos] *= 4.0
    frame["close"], frame["adj_close"] = values_c, values_p
    set_col(frame, "splits", pos, 4.0)
    report = audit_prices(frame)
    assert not report.ok
    assert finding(report, "suspected_missing_split_adjustment").dates == (ts(frame, pos),)
    assert ts(frame, pos) in finding(report, "large_return").dates
    assert "possible_unrecorded_split" not in codes(report)


def test_properly_adjusted_reverse_split_is_fine() -> None:
    frame = crsp_frame(23)
    set_col(frame, "splits", 300, 0.1)
    assert audit_prices(frame).ok


def test_missing_reverse_split_adjustment() -> None:
    frame = crsp_frame(23)
    values_c = frame["close"].to_numpy(copy=True)
    values_p = frame["adj_close"].to_numpy(copy=True)
    values_c[:300] *= 0.1
    values_p[:300] *= 0.1
    frame["close"], frame["adj_close"] = values_c, values_p
    set_col(frame, "splits", 300, 0.1)
    assert "suspected_missing_split_adjustment" in codes(audit_prices(frame), "error")


# ----------------------------------------------------------------------------- T24
def test_t24_wrong_dividend() -> None:
    pos = EVENTS[4]
    frame = crsp_frame(24, dist={pos: 0.50}, recorded_div={pos: 0.05})
    report = audit_prices(frame)
    mismatch = finding(report, "distribution_mismatch")
    assert mismatch.severity == "error" and mismatch.dates == (ts(frame, pos),)
    implied = float(mismatch.message.split("implied by Adj Close ")[1].split()[0])
    assert implied == pytest.approx(0.50, abs=0.011)  # Close rounded to cents
    drift = finding(report, "calendar_year_drift")
    assert drift.severity == "error"
    year = ts(frame, pos).year
    last_of_year = max(d for d in pd.DatetimeIndex(frame.index).date if d.year == year)
    assert drift.dates == (last_of_year,)  # one finding, dated at the end of that year only
    assert codes(report, "error") == {"distribution_mismatch", "calendar_year_drift"}


# ----------------------------------------------------------------------------- T25
def _fund(test_number: int, dist: float, div: float, cg: float, events: Sequence[int]):  # noqa: ANN202
    return crsp_frame(
        test_number,
        start=50.0,
        events=events,
        dist=dict.fromkeys(events, dist),
        recorded_div=dict.fromkeys(events, div),
        recorded_cg=dict.fromkeys(events, cg),
    )


def test_t25a_div_plus_capital_gains() -> None:
    report = audit_prices(_fund(25, 2.30, 0.30, 2.00, [200]))
    assert report.ok and serious(report) == []
    assert "div+cg" in finding(report, "distribution_summary").message


def test_t25b_dividends_already_include_gains() -> None:
    report = audit_prices(_fund(25, 2.30, 2.30, 2.00, [200]))
    assert report.ok and serious(report) == []
    msg = finding(report, "distribution_summary").message
    assert "div 1" in msg and "div+cg 0" in msg


def test_t25c_inconsistent_treatment_warns() -> None:
    frame = crsp_frame(
        25,
        start=50.0,
        events=[200, 450],
        dist={200: 2.30, 450: 2.30},
        recorded_div={200: 0.30, 450: 2.30},
        recorded_cg={200: 2.00, 450: 2.00},
    )
    report = audit_prices(frame)
    assert report.ok
    assert finding(report, "inconsistent_capital_gains_treatment").severity == "warn"


def test_t25d_no_convention_matches() -> None:
    report = audit_prices(_fund(25, 6.30, 2.30, 2.00, [200]))
    mismatch = finding(report, "distribution_mismatch")
    implied = float(mismatch.message.split("implied by Adj Close ")[1].split()[0])
    assert implied == pytest.approx(6.30, abs=0.011)  # Close rounded to cents


# ----------------------------------------------------------------------------- T26
def test_t26_rounding_at_low_prices_is_clean() -> None:
    report = audit_prices(crsp_frame(26, start=5.0))
    assert report.ok and serious(report) == [], [f.message for f in report.findings]


# ----------------------------------------------------------------------------- T27
def test_t27_extreme_real_move_is_flagged_and_kept() -> None:
    frame = crsp_frame(27, events=())
    pos = 300
    scale_from(frame, ["close", "adj_close"], pos, 0.55)
    report = audit_prices(frame)
    assert finding(report, "large_return").dates == (ts(frame, pos),)
    assert report.ok
    dates = pd.DatetimeIndex(frame.index[1:])
    rng = rng_for(27)
    f = rng.normal(0.0, 0.01, (len(dates), 5))
    factors = factor_frame(f, np.full(len(dates), 0.0001), dates)
    sample = build_sample(PriceHistory("X", frame, FETCHED_AT, "synthetic"), factors)
    assert pd.Timestamp(frame.index[pos]) in sample.xret.index
    assert sample.n == len(dates) and not sample.excluded


# ----------------------------------------------------------------------------- T28
def test_t28_unrecorded_split_warns() -> None:
    frame = crsp_frame(28, events=())
    c = frame["close"].to_numpy()
    scale_from(frame, ["close", "adj_close"], 500, 0.5 * c[499] / c[500])  # close ratio 0.5
    report = audit_prices(frame)
    f = finding(report, "possible_unrecorded_split")
    assert f.severity == "warn" and f.dates == (ts(frame, 500),)


# ----------------------------------------------------------------------------- T29
def test_t29_gap_rules() -> None:
    frame = crsp_frame(29, events=())
    long_gap = frame.drop(frame.index[200:208])  # 8 missing business days
    f = finding(audit_prices(long_gap), "gap_run")
    assert f.severity == "warn" and f.dates == (ts(frame, 200),)
    assert "gap_run" not in codes(audit_prices(frame.drop(frame.index[200:207])))
    closure = frame.drop(frame.index[200:204])  # 4 business days, 7 calendar days as in 2001
    assert {"gap_run", "gaps_fraction"}.isdisjoint(codes(audit_prices(closure)))
    sparse = frame.drop(frame.index[::6])
    assert "gaps_fraction" in codes(audit_prices(sparse), "warn")


def _flat_run(frame: pd.DataFrame, start: int, length: int, value: float) -> None:
    """Identical closes over a run, with Adj Close moved in proportion (no A7 finding)."""
    c = frame["close"].to_numpy(copy=True)
    p = frame["adj_close"].to_numpy(copy=True)
    sl = slice(start, start + length)
    p[sl] = p[sl] * value / c[sl]
    c[sl] = value
    frame["close"], frame["adj_close"] = c, p


def test_t29_stale_run_severity() -> None:
    frame = crsp_frame(29, events=())
    _flat_run(frame, 100, 5, 55.0)
    report = audit_prices(frame)
    stale = finding(report, "stale_run")
    assert stale.severity == "info" and stale.dates == (ts(frame, 100),)
    assert "adjustment_on_non_event_day" not in codes(report)
    with_volume = frame.copy()
    with_volume["volume"] = 1_000.0
    assert finding(audit_prices(with_volume), "stale_run").severity == "warn"
    short = crsp_frame(29, events=())
    _flat_run(short, 100, 4, 55.0)
    assert "stale_run" not in codes(audit_prices(short))


def test_t29_duplicates_and_order() -> None:
    frame = crsp_frame(29)
    dup = pd.concat([frame, frame.iloc[[50]]]).sort_index(kind="stable")
    report = audit_prices(dup)
    assert not report.ok
    assert finding(report, "duplicate_index").dates == (ts(frame, 50),)
    assert "non_increasing_index" in codes(audit_prices(frame.iloc[::-1]), "error")


def test_duplicates_recorded_at_ingestion_are_reported() -> None:
    frame = crsp_frame(29)
    report = audit_prices(frame, duplicate_dates=[ts(frame, 10), ts(frame, 20)])
    f = finding(report, "duplicate_index")
    assert f.severity == "error" and f.dates == (ts(frame, 10), ts(frame, 20))
    assert "first bar" in f.message


# ----------------------------------------------------------------------------- T30
def test_t30_adjustment_on_the_wrong_day() -> None:
    pos = EVENTS[3]
    frame = crsp_frame(30, late=[pos])
    report = audit_prices(frame)
    assert finding(report, "distribution_mismatch").dates == (ts(frame, pos),)
    assert finding(report, "adjustment_on_non_event_day").dates == (ts(frame, pos + 1),)
    assert finding(report, "adjustment_on_non_event_day").severity == "warn"


# ----------------------------------------------------------------------------- T119
def _tiny(closes: Sequence[float], start: str = "2021-03-01") -> pd.DataFrame:
    idx = pd.bdate_range(start, periods=len(closes), name="date")
    c = np.asarray(closes, dtype="float64")
    return pd.DataFrame(
        {"close": c, "adj_close": c.copy(), "dividends": 0.0, "splits": 0.0}, index=idx
    )


def _event_frame(delta: float) -> pd.DataFrame:
    """C_1 = 100, dividend 1.00 on row 2 with C_2 = 99: expected ratio 99 / 99 = 1."""
    frame = _tiny([100.0, 100.0, 99.0, 99.5, 100.0, 100.5])
    p = frame["close"].to_numpy(copy=True)
    p[:2] = p[:2] * math.exp(-delta) * (99.0 / 100.0)  # g_2 = exp(delta), g_1 = rho_1
    frame["adj_close"] = p
    set_col(frame, "dividends", 2, 1.0)
    return frame


def test_t119_a6_tolerance_literal() -> None:
    assert "distribution_mismatch" not in codes(audit_prices(_event_frame(1.5e-4)))
    assert "distribution_mismatch" in codes(audit_prices(_event_frame(2.5e-4)), "error")


def _non_event_frame(delta: float) -> pd.DataFrame:
    frame = _tiny([100.0, 100.0, 100.5, 100.0, 100.5, 100.0])
    p = frame["close"].to_numpy(copy=True)
    p[0] = p[0] * math.exp(-delta)  # g_1 = exp(delta) * rho_1, C_0 = 100
    frame["adj_close"] = p
    return frame


def test_t119_a7_tolerance_literal() -> None:
    assert "adjustment_on_non_event_day" not in codes(audit_prices(_non_event_frame(1.5e-4)))
    report = audit_prices(_non_event_frame(2.5e-4))
    assert finding(report, "adjustment_on_non_event_day").severity == "warn"


def _drift_frame(days: int) -> pd.DataFrame:
    """No events, min C = 100: tau_Y = 1e-3 + 0.01/100 = 1.1e-3; 1.1e-4 log drift per day."""
    closes = [100.0 if i % 2 == 0 else 100.5 for i in range(30)]
    frame = _tiny(closes, start="2021-02-01")
    steps = np.ones(30)
    steps[1 : days + 1] = math.exp(1.1e-4)
    frame["adj_close"] = frame["close"].to_numpy() * np.cumprod(steps)
    return frame


def test_t119_a8_tolerance_literal() -> None:
    ok = audit_prices(_drift_frame(8))  # 8.8e-4 = 0.8 tau_Y
    assert "calendar_year_drift" not in codes(ok)
    assert "adjustment_on_non_event_day" not in codes(ok)
    bad = audit_prices(_drift_frame(12))  # 1.32e-3 = 1.2 tau_Y
    assert finding(bad, "calendar_year_drift").severity == "error"
    assert "adjustment_on_non_event_day" not in codes(bad)


def test_t119_a5b_literal() -> None:
    frame = _tiny([100.0, 101.0, 50.5, 51.0, 50.0])
    assert "possible_unrecorded_split" in codes(audit_prices(frame), "warn")
    near = _tiny([100.0, 101.0, 46.46, 47.0, 46.0])  # ratio 0.46: 0.083 from ln(1/2)
    report = audit_prices(near)
    assert "possible_unrecorded_split" not in codes(report)
    assert "large_return" in codes(report, "warn")


# ----------------------------------------------------------------------------- A1 and misc
@pytest.mark.parametrize("column", ["close", "adj_close"])
def test_nan_price_is_error(column: str) -> None:
    frame = crsp_frame(31)
    set_col(frame, column, 40, np.nan)
    report = audit_prices(frame)
    assert not report.ok
    assert finding(report, "nan_price").dates == (ts(frame, 40),)


@pytest.mark.parametrize("bad", [0.0, -3.0])
def test_non_positive_price_is_error(bad: float) -> None:
    frame = crsp_frame(31)
    set_col(frame, "close", 90, bad)
    report = audit_prices(frame)
    assert not report.ok
    assert finding(report, "non_positive_price").dates == (ts(frame, 90),)


def test_audit_does_not_mutate_input() -> None:
    frame = crsp_frame(31, with_cg_column=True)
    set_col(frame, "close", 5, np.nan)
    set_col(frame, "capital_gains", 7, 1.0)
    frame = pd.concat([frame.iloc[::-1], frame.iloc[:3]])
    before = frame.copy(deep=True)
    audit_prices(frame)
    pd.testing.assert_frame_equal(frame, before)


def test_invalid_frames() -> None:
    empty = audit_prices(pd.DataFrame())
    assert not empty.ok and empty.n_obs == 0
    report = audit_prices(crsp_frame(31).drop(columns=["adj_close"]))
    assert not report.ok and "missing_columns" in codes(report, "error")
    no_dt = pd.DataFrame({"close": [1.0, 2.0], "adj_close": [1.0, 2.0]})
    assert not audit_prices(no_dt).ok
