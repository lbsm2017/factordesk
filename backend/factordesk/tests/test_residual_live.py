"""TR40: live smoke test of the residual section on real SPY (test-oracle-residual-analysis.md).

Run with ``-m live``. It reads the cached price series and the cached factor file under the data
directory and refuses to download: the price download hook raises, the factor file is loaded with
``now`` set to its own download time so it is never judged stale. A ticker without a cached price
file is skipped. Bounds are loose on purpose: they catch broken pipelines (RF, alignment, lag,
units), not estimates. ``-s`` prints the measured numbers.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, get_args

import numpy as np
import pandas as pd
import pytest

from factordesk.analytics.regression import A
from factordesk.analytics.residual import (
    FINDING_ARCH,
    FINDING_JB,
    FINDING_LB,
    point_in_time_betas,
)
from factordesk.analytics.sample import FACTOR_CODES, build_sample
from factordesk.config import get_settings
from factordesk.data.factors import load_ff5_daily
from factordesk.data.prices import YFinanceProvider
from factordesk.pipeline import build_report, unique_dates
from factordesk.report.schema import FactorReport
from factordesk.report.sections.residual_alpha import GapVerdict
from factordesk.tests.fixtures.dgp_residual import analyse_sample

pytestmark = pytest.mark.live

START = date(2010, 1, 4)
"""The sample of T109-T111 (the same sample as the SPY smoke test)."""


def _no_download(symbol: str) -> pd.DataFrame:
    raise AssertionError(f"TR40 must not download prices ({symbol})")


def _cached_day(data: Path, ticker: str) -> date | None:
    days = sorted(
        p.stem.removeprefix(f"{ticker}_") for p in (data / "prices").glob(f"{ticker}_*.parquet")
    )
    return date.fromisoformat(days[-1]) if days else None


def _factor_time(data: Path) -> datetime:
    meta = json.loads((data / "factors" / "meta.json").read_text(encoding="utf-8"))
    return datetime.fromisoformat(meta["last_download_at"]).astimezone(UTC)


def _report(ticker: str) -> tuple[FactorReport, Any, Any]:
    data = Path(get_settings().data_dir)
    day = _cached_day(data, ticker)
    if day is None or not (data / "factors" / "meta.json").is_file():
        pytest.skip(f"no cached {ticker} price file or factor file under {data}")
    now = datetime(day.year, day.month, day.day, 15, 0, tzinfo=UTC)
    factors = load_ff5_daily(data_dir=data, now=_factor_time(data))
    provider = YFinanceProvider(cache_dir=data / "prices", now=lambda: now, download=_no_download)
    report = build_report(ticker, provider, factors=factors, now=now, start=START)
    return report, provider.fetch(ticker), factors


def numbers(report: FactorReport) -> dict[str, Any]:
    """The measured values worth reporting."""
    s = report.residual
    assert s is not None
    return {
        "in_sample": {
            "span": [
                str(s.in_sample.sample.start),
                str(s.in_sample.sample.end),
                s.in_sample.sample.n,
            ],
            "return_annual": s.in_sample.residual_return_annual,
            "ci": [
                s.in_sample.residual_return_ci_low_annual,
                s.in_sample.residual_return_ci_high_annual,
            ],
            "z": s.in_sample.z,
            "vol_annual": s.in_sample.residual_vol_annual,
            "hac_lags": s.in_sample.hac_lags,
        },
        "point_in_time": {
            "span": [
                str(s.point_in_time.sample.start),
                str(s.point_in_time.sample.end),
                s.point_in_time.sample.n,
            ],
            "return_annual": s.point_in_time.residual_return_annual,
            "ci": [
                s.point_in_time.residual_return_ci_low_annual,
                s.point_in_time.residual_return_ci_high_annual,
            ],
            "z": s.point_in_time.z,
            "vol_annual": s.point_in_time.residual_vol_annual,
        },
        "gap": {
            "in_sample_same_days_annual": s.gap.in_sample_same_days_annual,
            "gap_annual": s.gap.gap_annual,
            "gap_z": s.gap.gap_z,
            "survival_ratio": s.gap.survival_ratio,
            "comparison_share_of_alpha": s.gap.comparison_share_of_alpha,
            "verdict": s.gap.verdict,
            "message": s.gap.message,
        },
        "rolling_share_excluding_zero": s.rolling_alpha.share_excluding_zero,
        "non_overlapping": [s.non_overlapping.n_reliable, s.non_overlapping.family_size],
        "split_half": {
            "first": s.split_half.alpha_first_annual,
            "second": s.split_half.alpha_second_annual,
            "difference": s.split_half.difference_annual,
            "difference_p": s.split_half.difference_p,
        },
        "diagnostics": [d.findings for d in s.diagnostics],
        "warnings": [w.code for w in s.warnings],
        "regression_alpha_annual": report.regression.alpha_annual,
        "regression_r2": report.regression.r2,
    }


def _check_identities(report: FactorReport, history: Any, factors: pd.DataFrame) -> None:
    """TR01 (b)-(c), TR13 and TR28 on the JSON payload, recomputed from the cached inputs."""
    payload = json.loads(report.model_dump_json())
    s = payload["residual"]
    assert s["status"] == "ok"
    alpha_ann = payload["regression"]["alpha_annual"]
    ins, pit = s["in_sample"], s["point_in_time"]

    # TR01 (b): the in-sample residual return is the regression alpha.
    assert abs(ins["residual_return_annual"] - alpha_ann) <= 1e-10
    # TR01 (c), TR28: the yearly sums add to n alpha_hat.
    n = ins["sample"]["n"]
    years = s["calendar_years"]["years"]
    assert abs(sum(y["in_sample_sum"] for y in years) - n * alpha_ann / A) <= 1e-10

    sample = build_sample(unique_dates(history), factors, START)
    a = analyse_sample(sample, s["beta_window"])
    y = a.sample.xret.to_numpy(dtype=np.float64)
    f = a.sample.factors.loc[:, list(FACTOR_CODES)].to_numpy(dtype=np.float64)
    w = a.rolling.window

    # TR13: the point-in-time residual return is the unattributed row of the tilt/timing split.
    bt = point_in_time_betas(a.rolling)[w:]
    dyn = A * (bt * f[w:]).mean(axis=0)
    unattributed = A * float(y[w:].mean()) - float(dyn.sum())
    assert abs(pit["residual_return_annual"] - unattributed) <= 1e-10

    # TR28: each in-sample yearly sum is alpha plus the regression residual of that year.
    e_hat = np.asarray(a.reg.fit.resid, dtype=np.float64)
    by_year = np.array([d.year for d in sample.xret.index])
    for row in years:
        m62 = row["n"] * a.reg.alpha + float(e_hat[by_year == row["year"]].sum())
        assert abs(row["in_sample_sum"] - m62) <= 1e-10, row["year"]


def _check_wording(report: FactorReport) -> None:
    s = report.residual
    assert s is not None
    assert s.gap.verdict in get_args(GapVerdict)
    allowed = {*FINDING_LB, *FINDING_JB, *FINDING_ARCH}
    for d in s.diagnostics:
        assert d.status == "ok"
        assert set(d.findings) <= allowed
        assert len(d.findings) == 3
    assert not re.search(r"survives", s.gap.message or "")
    json.dumps(report.model_dump(mode="json"), allow_nan=False)


def test_tr40_live_spy(capsys: pytest.CaptureFixture[str]) -> None:
    report, history, factors = _report("SPY")
    s = report.residual
    assert s is not None and s.status == "ok"
    assert report.regression.r2 is not None and report.regression.r2 >= 0.97
    assert s.in_sample.residual_vol_annual is not None and s.in_sample.residual_vol_annual <= 0.06
    assert s.point_in_time.status == "ok"
    assert s.point_in_time.residual_return_annual is not None
    assert abs(s.point_in_time.residual_return_annual) <= 0.03
    assert not s.in_sample.wiped_out and not s.point_in_time.wiped_out
    _check_identities(report, history, factors)
    _check_wording(report)
    with capsys.disabled():
        print("\nTR40 SPY " + json.dumps(numbers(report), indent=2, default=str))


def test_tr40_live_aapl() -> None:
    report, history, factors = _report("AAPL")
    s = report.residual
    assert s is not None and s.status == "ok"
    assert s.point_in_time.status == "ok"
    assert not s.in_sample.wiped_out and not s.point_in_time.wiped_out
    _check_identities(report, history, factors)
    _check_wording(report)
