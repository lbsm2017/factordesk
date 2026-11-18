"""Performance section: schema, hook, pipeline, fixture (schema v3 contract SC9, sixth section).

Run ``uv run python -m factordesk.tests.test_section_performance`` to regenerate the synthetic
fixture ``fixtures/sections/performance.json`` (the OpenAPI document does not contain fixtures).
IDs TP25-TP40.
"""

from __future__ import annotations

import dataclasses
import json
import math
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest
from pydantic import ValidationError

from factordesk.analytics.performance import MIN_OBS
from factordesk.pipeline import assemble_report
from factordesk.report import FactorReport, load_report
from factordesk.report.schema import SECTIONS, SUPPORTED_SCHEMA_VERSIONS
from factordesk.report.sections.performance import (
    PERFORMANCE_SECTION,
    PerformanceSection,
)
from factordesk.section_hooks import performance as hook
from factordesk.section_hooks.context import SectionContext
from factordesk.tests.fixtures.dgp import (
    MU,
    SIGMA_F,
    default_rf,
    dgp_a,
    factor_frame,
    price_history,
    rng_for,
)
from factordesk.tests.fixtures.sections import report_with_section

FIXTURES = Path(__file__).parent / "fixtures"
MOCK = FIXTURES / "mock_report.json"
FIXTURE = FIXTURES / "sections" / "performance.json"
NOW = datetime(2026, 11, 18, 15, 0, tzinfo=UTC)


def _spy_context(n: int = 700) -> tuple[FactorReport, SectionContext]:
    """A pipeline report and the context its performance hook saw."""
    d = dgp_a(rng_for(4001), n=n)
    seen: list[SectionContext] = []
    real = hook.build_performance

    def spy(ctx: SectionContext) -> PerformanceSection | None:
        seen.append(ctx)
        return real(ctx)

    original = hook.build_performance
    hook.build_performance = spy  # the pipeline reads the attribute at call time
    try:
        report = assemble_report("SYN", d.history, d.factors, now=NOW, factors_downloaded_at=None)
    finally:
        hook.build_performance = original
    (ctx,) = seen
    return report, ctx


def _validate(payload: dict[str, Any]) -> PerformanceSection:
    """Validate through JSON, as the schema does (dates are strict in Python mode)."""
    return PerformanceSection.model_validate_json(json.dumps(payload))


def _with_sample(ctx: SectionContext, ret: pd.Series, rf: pd.Series) -> SectionContext:
    sample = dataclasses.replace(ctx.sample, ret=ret, rf=rf, xret=ret - rf)
    return dataclasses.replace(ctx, sample=sample)


# ----------------------------------------------------------------------------- the fixture
def synthetic_section() -> PerformanceSection:
    """A synthetic section of the real shape on the mock report's dates (frontend visual check).

    The data are a draw of DGP-A with a daily alpha of 0.0004 and residual sd 0.008, so the
    section shows a recovered and an open drawdown. Run this module to write the fixture file.
    """
    mock = load_report(MOCK)
    dates = pd.DatetimeIndex([pd.Timestamp(d) for d in mock.rolling[0].dates], name="date")
    n = len(dates)
    rng = np.random.default_rng(20261118 + 1000)
    f = rng.multivariate_normal(MU, SIGMA_F, size=n)
    rf = default_rf(n)
    beta = np.array([1.1, 0.2, -0.3, 0.1, 0.0])
    ret = rf + 0.0004 + f @ beta + rng.normal(0.0, 0.008, size=n)
    history = price_history(ret, dates, first_date="2024-08-07", ticker="SPY")
    report = assemble_report(
        "SPY",
        history,
        factor_frame(f, rf, dates),
        now=NOW,
        factors_downloaded_at=mock.data.factors_downloaded_at,
    )
    assert report.performance is not None
    return report.performance


def test_tp25_fixture_is_a_synthetic_section_of_the_real_shape() -> None:
    section = PerformanceSection.model_validate_json(FIXTURE.read_text(encoding="utf-8"))
    assert section.status == "ok" and section.reason is None
    assert section.periods is not None and section.periods.n_days == 559
    assert section.drawdown is not None and section.drawdown.episodes
    assert section.sharpe is not None and section.sharpe.ci_includes_zero is not None
    mock = load_report(MOCK)
    assert report_with_section(mock, "performance").performance == section


# ----------------------------------------------------------------------------- schema
def test_tp26_the_section_is_registered_first_and_is_optional() -> None:
    assert SECTIONS[0] is PERFORMANCE_SECTION
    info = FactorReport.model_fields["performance"]
    assert info.default is None and not info.is_required()
    assert PERFORMANCE_SECTION.report_field == "performance"
    assert PERFORMANCE_SECTION.statistic_models == () and not PERFORMANCE_SECTION.label_text
    assert SUPPORTED_SCHEMA_VERSIONS == ("3", "4", "5")


def test_tp27_older_files_load_without_the_field() -> None:
    payload = json.loads(MOCK.read_text(encoding="utf-8"))
    del payload["performance"]
    payload["schema_version"] = "4"
    old = FactorReport.model_validate_json(json.dumps(payload))
    assert old.performance is None and old.schema_version == "4"


def test_tp28_parts_are_present_exactly_when_ok() -> None:
    ok = PerformanceSection.model_validate_json(FIXTURE.read_text(encoding="utf-8"))
    payload = ok.model_dump(mode="json")
    for part in ("periods", "returns", "volatility_annual", "sharpe", "drawdown"):
        broken = {**payload, part: None}
        with pytest.raises(ValidationError):
            _validate(broken)
    with pytest.raises(ValidationError):
        _validate({**payload, "status": "failed", "reason": "x"})
    empty = {**payload, "periods": None, "returns": None, "volatility_annual": None}
    empty |= {"sharpe": None, "drawdown": None, "status": "failed", "reason": "No data."}
    assert _validate(empty).status == "failed"


def test_tp29_nan_and_infinity_are_rejected() -> None:
    ok = PerformanceSection.model_validate_json(FIXTURE.read_text(encoding="utf-8"))
    payload = ok.model_dump(mode="json")
    for bad in (math.nan, math.inf):
        broken = json.loads(json.dumps(payload))
        broken["volatility_annual"] = bad
        with pytest.raises(ValidationError):
            _validate(broken)


# ----------------------------------------------------------------------------- pipeline and hook
def test_tp30_pipeline_fills_the_section_from_the_analysis_sample() -> None:
    report, ctx = _spy_context()
    section = report.performance
    assert section is not None and section.status == "ok"
    s = ctx.sample
    assert section.sample == report.regression.sample == ctx.sample_info(None)
    assert section.periods is not None
    assert section.periods.n_days == s.n == report.data.n_obs
    assert (section.periods.start, section.periods.end) == (s.start, s.end)
    assert section.periods.years == pytest.approx(s.n / 252)
    # An independent plain-pandas computation on the sample's total returns.
    r: np.ndarray[Any, Any] = np.asarray(s.ret, dtype=np.float64)
    x: np.ndarray[Any, Any] = np.asarray(s.ret - s.rf, dtype=np.float64)
    assert section.returns is not None and section.sharpe is not None
    assert section.returns.cagr == pytest.approx(float(np.prod(1 + r) ** (252 / len(r)) - 1))
    assert section.returns.cumulative_return == pytest.approx(float(np.prod(1 + r) - 1))
    assert section.volatility_annual == pytest.approx(float(r.std(ddof=1)) * math.sqrt(252))
    assert section.sharpe.ratio_annual == pytest.approx(
        float(x.mean() / x.std(ddof=1)) * math.sqrt(252)
    )
    w = pd.Series(np.concatenate([[1.0], np.cumprod(1 + r)]))
    assert section.drawdown is not None
    assert section.drawdown.max_drawdown == pytest.approx(float((w / w.cummax() - 1).min()))
    json.dumps(report.model_dump(mode="json"), allow_nan=False)


def test_tp31_total_returns_are_excess_plus_risk_free() -> None:
    _, ctx = _spy_context()
    s = ctx.sample
    np.testing.assert_allclose((s.xret + s.rf).to_numpy(), s.ret.to_numpy(), atol=1e-15)


def test_tp32_the_path_starts_on_the_price_date_before_the_first_return() -> None:
    d = dgp_a(rng_for(4002), n=600)
    rng = rng_for(4002, seed=77)
    ret = rng.uniform(0.0002, 0.002, size=600)  # positive, so the first day is the trough
    ret[0] = -0.2  # the very first analysed day is a crash: the peak is the starting point
    index = pd.DatetimeIndex(d.history.frame.index)
    history = price_history(ret, index[1:], first_date=index[0])
    report = assemble_report("SYN", history, d.factors, now=NOW, factors_downloaded_at=None)
    section = report.performance
    assert section is not None and section.drawdown is not None
    first_price_date = history.frame.index[0].date()
    assert section.drawdown.peak_date == first_price_date
    assert section.drawdown.trough_date == history.frame.index[1].date()


def test_tp33_hook_leaves_the_core_report_unchanged(monkeypatch: pytest.MonkeyPatch) -> None:
    d = dgp_a(rng_for(4001), n=700)
    with_section = assemble_report("SYN", d.history, d.factors, now=NOW, factors_downloaded_at=None)
    from factordesk import pipeline

    def none_hook(ctx: SectionContext) -> PerformanceSection | None:
        return None

    monkeypatch.setattr(pipeline.performance_hook, "build_performance", none_hook)
    without = assemble_report("SYN", d.history, d.factors, now=NOW, factors_downloaded_at=None)
    assert without.performance is None
    assert with_section.model_copy(update={"performance": None}) == without


def test_tp34_a_short_sample_is_insufficient_data() -> None:
    _, ctx = _spy_context()
    for n, expected in ((MIN_OBS - 1, "insufficient_data"), (MIN_OBS, "ok")):
        s = ctx.sample
        sec = hook.build_performance(_with_sample(ctx, s.ret.iloc[:n], s.rf.iloc[:n]))
        assert sec is not None and sec.status == expected
        if expected != "ok":
            assert sec.reason is not None and str(n) in sec.reason
            assert sec.periods is None and sec.volatility_annual is None
            json.dumps(sec.model_dump(mode="json"), allow_nan=False)


def test_tp35_non_finite_returns_fail_the_section_without_blocking() -> None:
    _, ctx = _spy_context()
    s = ctx.sample
    for bad in (math.nan, math.inf):
        ret = s.ret.copy()
        ret.iloc[10] = bad
        sec = hook.build_performance(_with_sample(ctx, ret, s.rf))
        assert sec is not None and sec.status == "failed" and sec.reason
        assert sec.returns is None and sec.sharpe is None and sec.drawdown is None


def test_tp36_constant_prices_give_a_null_sharpe_ratio_not_nan() -> None:
    _, ctx = _spy_context()
    s = ctx.sample
    sec = hook.build_performance(_with_sample(ctx, s.ret * 0.0, s.rf))
    assert sec is not None and sec.status == "ok"
    assert sec.sharpe is not None and sec.sharpe.ratio_annual is None
    assert sec.sharpe.sharpe_se_iid is None and sec.sharpe.ci_includes_zero is None
    assert sec.volatility_annual == pytest.approx(0.0, abs=1e-12)
    assert sec.drawdown is not None and sec.drawdown.max_drawdown == 0.0
    json.dumps(sec.model_dump(mode="json"), allow_nan=False)


def test_tp37_a_rising_series_has_no_drawdown_dates() -> None:
    _, ctx = _spy_context()
    s = ctx.sample
    rising = pd.Series(0.001, index=s.ret.index, name="ret")
    sec = hook.build_performance(_with_sample(ctx, rising, s.rf))
    assert sec is not None and sec.drawdown is not None
    dd = sec.drawdown
    assert dd.max_drawdown == 0.0 and dd.episodes == []
    assert dd.peak_date is None and dd.trough_date is None and dd.recovery_date is None
    assert dd.days_peak_to_trough is None and dd.days_trough_to_recovery is None


def test_tp38_first_episode_is_the_maximum_drawdown() -> None:
    report, _ = _spy_context()
    dd = report.performance.drawdown if report.performance else None
    assert dd is not None and dd.episodes
    first = dd.episodes[0]
    assert (first.depth, first.peak_date, first.trough_date, first.recovery_date) == (
        dd.max_drawdown,
        dd.peak_date,
        dd.trough_date,
        dd.recovery_date,
    )
    assert (first.days_peak_to_trough, first.days_trough_to_recovery) == (
        dd.days_peak_to_trough,
        dd.days_trough_to_recovery,
    )
    assert len(dd.episodes) <= 3
    assert [e.depth for e in dd.episodes] == sorted(e.depth for e in dd.episodes)


def test_tp39_the_section_follows_the_analysed_range() -> None:
    d = dgp_a(rng_for(4003), n=900)
    full = assemble_report("SYN", d.history, d.factors, now=NOW, factors_downloaded_at=None)
    start = d.history.frame.index[300].date()
    short = assemble_report(
        "SYN", d.history, d.factors, start=start, now=NOW, factors_downloaded_at=None
    )
    assert full.performance is not None and short.performance is not None
    assert full.performance.periods is not None and short.performance.periods is not None
    assert short.performance.periods.n_days == short.data.n_obs < full.performance.periods.n_days
    assert short.performance.periods.start >= start
    assert short.performance.returns != full.performance.returns


def test_tp40_hook_returns_the_failed_state_when_the_statistics_raise(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, ctx = _spy_context()

    def boom(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("boom")

    monkeypatch.setattr(hook, "performance_stats", boom)
    sec = hook.build_performance(ctx)
    assert sec is not None and sec.status == "failed" and sec.reason == hook.FAILED


if __name__ == "__main__":
    FIXTURE.write_text(synthetic_section().model_dump_json() + "\n", encoding="utf-8")
