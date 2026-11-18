"""Residual section tests: schema, hook, labels and copy (TR38, TR39; contract SC9).

Run ``uv run python -m factordesk.tests.test_section_residual_alpha`` to regenerate the synthetic
fixture ``fixtures/sections/residual_alpha.json`` (then regenerate nothing else: the OpenAPI
document does not contain fixtures).
"""

from __future__ import annotations

import dataclasses
import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest
from pydantic import ValidationError

from factordesk.analytics.residual import residual_analysis
from factordesk.analytics.rolling import rolling_betas
from factordesk.pipeline import assemble_report
from factordesk.report import FactorReport, load_report
from factordesk.report.base import ReportWarning
from factordesk.report.schema import LABEL_TEXT, STATISTIC_MODELS, report_label_text
from factordesk.report.sections.residual_alpha import (
    QUESTION,
    RESIDUAL_ALPHA_SECTION,
    RESIDUAL_LABEL_TEXT,
    ResidualAnalysis,
    ResidualChart,
    ResidualGap,
    ResidualStats,
)
from factordesk.section_hooks import residual_alpha as hook
from factordesk.section_hooks.context import SectionContext
from factordesk.tests.fixtures.dgp import (
    BETA,
    MU,
    SIGMA_F,
    default_rf,
    dgp_a,
    factor_frame,
    price_history,
)
from factordesk.tests.fixtures.dgp_residual import dgp_residual, rng_tr
from factordesk.tests.fixtures.sections import report_with_section

FIXTURES = Path(__file__).parent / "fixtures"
MOCK = FIXTURES / "mock_report.json"
FIXTURE = FIXTURES / "sections" / "residual_alpha.json"
NOW = datetime(2026, 11, 18, 15, 0, tzinfo=UTC)
SYNTHETIC = "Synthetic data for tests and layout checks; not a real ticker."


def _report(n: int = 2520, **kwargs: Any) -> FactorReport:
    d = dgp_a(rng_tr(38), n=n)
    return assemble_report(
        "SYN", d.history, d.factors, now=NOW, factors_downloaded_at=None, **kwargs
    )


def _section(report: FactorReport) -> ResidualAnalysis:
    assert report.residual is not None
    return report.residual


# ----------------------------------------------------------------------------- the fixture
def synthetic_section() -> ResidualAnalysis:
    """A synthetic section of the real shape on the mock report's dates (frontend visual check).

    The data are a draw of DGP-A with a daily alpha of 0.0009 and residual sd 0.007; the section
    is marked synthetic through a warning. Run this module to write the fixture file.
    """
    mock = load_report(MOCK)
    dates = pd.DatetimeIndex([pd.Timestamp(d) for d in mock.rolling[0].dates], name="date")
    n = len(dates)
    rng = np.random.default_rng(20261118 + 700)
    f = rng.multivariate_normal(MU, SIGMA_F, size=n)
    rf = default_rf(n)
    ret = rf + 0.0009 + f @ BETA + rng.normal(0.0, 0.007, size=n)
    history = price_history(ret, dates, first_date="2024-08-07", ticker="SPY")
    report = assemble_report(
        "SPY",
        history,
        factor_frame(f, rf, dates),
        now=NOW,
        factors_downloaded_at=mock.data.factors_downloaded_at,
    )
    section = _section(report)
    note = ReportWarning(code="synthetic_fixture", message=SYNTHETIC)
    return section.model_copy(update={"warnings": [*section.warnings, note]})


def test_fixture_is_a_synthetic_section_of_the_real_shape() -> None:
    section = ResidualAnalysis.model_validate_json(FIXTURE.read_text(encoding="utf-8"))
    assert section.status == "ok" and section.question == QUESTION
    assert any(w.code == "synthetic_fixture" for w in section.warnings)
    assert section.point_in_time.status == "ok" and section.gap.verdict is not None
    n = len(section.chart.dates)
    assert n == 559 and section.chart.comparison_start is not None
    assert len(section.rolling_alpha.alpha_annual) == n
    assert section.calendar_years.years and section.non_overlapping.windows
    mock = load_report(MOCK)
    assert report_with_section(mock, "residual").residual == section


# ----------------------------------------------------------------------------- TR38 schema
def test_tr38_short_report_serialises_and_not_ok_statistics_hold_no_numbers() -> None:
    report = _report(n=600, primary_window=504)
    section = _section(report)
    json.dumps(report.model_dump(mode="json"), allow_nan=False)
    pit, gap = section.point_in_time, section.gap
    assert pit.status == "insufficient_data" and pit.reason is not None
    assert pit.residual_return_annual is None and pit.z is None and pit.hac_lags is None
    assert gap.status == "insufficient_data" and gap.verdict is None
    assert gap.survival_ratio is None and gap.message is None
    assert section.chart.point_in_time_status == "insufficient_data"
    assert section.chart.comparison_start is None
    assert all(v is None for v in section.chart.point_in_time_compare)
    assert section.diagnostics[1].status == "insufficient_data"
    assert section.diagnostics[1].findings == []
    assert section.in_sample.status == "ok" and section.status == "ok"
    assert all(y.point_in_time_sum is None for y in section.calendar_years.years)
    assert report.schema_version == "5"  # the contract's number (SC5), not "3" as R7.8 said


def test_tr38_statistic_models_are_registered() -> None:
    names = {m.__name__ for m in RESIDUAL_ALPHA_SECTION.statistic_models}
    assert names == {
        "ResidualStats",
        "ResidualChart",
        "ResidualGap",
        "RollingResidualAlpha",
        "NonOverlappingAlpha",
        "SplitHalfAlpha",
        "ResidualYears",
        "ResidualAlphaDiagnostics",
    }
    for model in RESIDUAL_ALPHA_SECTION.statistic_models:
        assert model in STATISTIC_MODELS
        assert {"status", "reason", "sample", "labels", "caption"} <= set(model.model_fields)


def _payload(model: type[Any], section: ResidualAnalysis, field: str) -> dict[str, Any]:
    assert isinstance(getattr(section, field), model)
    return json.loads(getattr(section, field).model_dump_json())


@pytest.fixture(scope="module")
def full_report() -> FactorReport:
    return _report()


def test_tr38_construction_fails_for_inconsistent_values(full_report: FactorReport) -> None:
    section = _section(full_report)
    chart = _payload(ResidualChart, section, "chart")

    def bad(model: type[Any], payload: dict[str, Any], **changes: Any) -> None:
        with pytest.raises(ValidationError):
            model.model_validate({**payload, **changes})

    bad(ResidualChart, chart, in_sample_full=chart["in_sample_full"][:-1])
    bad(ResidualChart, chart, point_in_time_reason="why")
    non_ok = {**chart, "point_in_time_status": "insufficient_data", "point_in_time_reason": "x"}
    bad(ResidualChart, non_ok)  # comparison lines still hold values
    shifted = list(chart["in_sample_compare"])
    anchor = shifted.index(0.0)
    shifted[anchor] = 0.5
    bad(ResidualChart, chart, in_sample_compare=shifted)
    early = list(chart["point_in_time_compare"])
    early[0] = 0.0
    bad(ResidualChart, chart, point_in_time_compare=early)

    stats = _payload(ResidualStats, section, "in_sample")
    bad(ResidualStats, stats, residual_return_annual=float("nan"))
    bad(ResidualStats, stats, beta_window=252)
    bad(ResidualStats, _payload(ResidualStats, section, "point_in_time"), beta_window=None)

    gap = _payload(ResidualGap, section, "gap")
    off = {**gap, "status": "insufficient_data", "reason": "x"}
    bad(ResidualGap, off)  # numbers and verdict stay
    bad(ResidualGap, {**gap, "verdict": None})


def test_tr38_sample_info_and_round_trip(full_report: FactorReport) -> None:
    section = _section(full_report)
    assert FactorReport.model_validate_json(full_report.model_dump_json()) == full_report
    assert section.in_sample.residual_return_annual == full_report.regression.alpha_annual
    assert section.in_sample.z == full_report.regression.alpha_z
    for obj in (section.in_sample, section.chart, section.split_half, section.calendar_years):
        assert obj.sample.n == 2520 and obj.sample.window is None
    for obj in (section.point_in_time, section.gap):
        assert obj.sample.n == 2268 and obj.sample.start == date(2010, 12, 22)
        assert obj.sample.window == 252
    assert section.rolling_alpha.sample.window == 252
    assert section.non_overlapping.sample.window == 252 and section.non_overlapping.sample.n == 2520
    assert section.sample == full_report.regression.sample
    assert section.beta_window == 252


def test_hook_leaves_the_core_report_bitwise_unchanged(monkeypatch: pytest.MonkeyPatch) -> None:
    with_section = _report(n=900)

    def none_hook(ctx: SectionContext) -> ResidualAnalysis | None:
        return None

    monkeypatch.setattr(hook, "build_residual_analysis", none_hook)
    without = _report(n=900)
    assert without.residual is None and with_section.residual is not None
    assert with_section.model_copy(update={"residual": None, "label_text": without.label_text}) == (
        without
    )
    assert with_section.regression.model_dump_json() == without.regression.model_dump_json()


# ----------------------------------------------------------------------------- TR39 labels, copy
def test_tr39_labels_captions_and_caveats(full_report: FactorReport) -> None:
    s = _section(full_report)
    assert set(s.in_sample.labels) == {"L-DESC", "L-INSAMPLE", "L-VINTAGE"}
    assert set(s.point_in_time.labels) == {"L-DESC-PIT", "L-PIT", "L-VINTAGE"}
    assert set(s.chart.labels) == {"L-INSAMPLE", "L-PIT", "L-HEDGE", "L-VINTAGE"}
    assert set(s.gap.labels) == {"L-INSAMPLE", "L-PIT", "L-VINTAGE"}
    assert set(s.rolling_alpha.labels) == {"L-DESC", "L-BAND", "L-OVERLAP"}
    assert RESIDUAL_LABEL_TEXT == {
        "L-INSAMPLE": "In-sample: betas are fitted on this same period.",
        "L-PIT": "Point-in-time: each day uses betas estimated only from earlier days.",
        "L-DESC-PIT": "Descriptive and point-in-time, not predictive.",
        "L-HEDGE": (
            "Compounded daily: a paper long-short hedge, rebalanced daily, before trading "
            "costs, financing and borrowing fees."
        ),
    }
    for key, text in RESIDUAL_LABEL_TEXT.items():
        assert full_report.label_text[key] == text
    for key in s.chart.labels + s.point_in_time.labels:
        assert key in full_report.label_text
    assert s.question == (
        "What did this stock return beyond its factor exposures, and does it hold up without "
        "hindsight?"
    )
    assert s.caveats == hook.caveats(252) and len(s.caveats) == 5
    assert "previous 252 trading days only" in s.caveats[2]
    assert s.in_sample.caption == (
        "Residual return = excess return minus factor exposures, alpha included. In-sample: "
        "betas fitted on 2010-01-04 to 2019-08-30, so the residual return equals the regression "
        "alpha exactly."
    )
    assert s.point_in_time.caption == (
        "Residual return with each day's betas estimated from the previous 252 trading days "
        "only. Covers 2010-12-22 to 2019-08-30; the first 252 days are warm-up."
    )
    assert s.chart.caption == (
        "Cumulative residual return, compounded daily. Both lines start at zero on 2010-12-21 "
        "and cover the same days. In-sample uses betas fitted on the whole period; "
        "point-in-time uses betas from the previous 252 days."
    )
    assert s.gap.caption == (
        "Same days (2010-12-22 to 2019-08-30) for both series. Out-of-sample here refers to the "
        "betas; both series share the same days and stock-specific news."
    )
    assert s.rolling_alpha.caption == (
        "Each point uses the previous 252 trading days, ending on that date; alpha and betas "
        "are both refitted in each window."
    )
    assert s.non_overlapping.caption == (
        "Separate one-year windows counted back from 2019-08-30. Corrected for testing 10 "
        "windows (Benjamini-Hochberg)."
    )
    assert s.split_half.caption == (
        "One split, fixed in advance at the middle of the period. Betas are refitted in each half."
    )
    assert s.calendar_years.caption == (
        "Sum of daily residual returns within the year (not compounded). In-sample column: "
        "betas from the whole period. Point-in-time column: betas from the previous 252 days."
    )
    for d in s.diagnostics:
        assert d.caption == (
            "Informational checks at the 5% level, not corrected for multiple testing."
        )


def test_label_text_only_when_the_section_is_present(full_report: FactorReport) -> None:
    absent = report_label_text({"residual": None})
    assert not set(RESIDUAL_LABEL_TEXT) & set(absent)
    assert absent == LABEL_TEXT
    assert {**LABEL_TEXT, **RESIDUAL_LABEL_TEXT}.items() <= full_report.label_text.items()


def test_tr33_hedge_label_and_not_compounded_caption(full_report: FactorReport) -> None:
    s = _section(full_report)
    assert "L-HEDGE" in s.chart.labels
    assert "not compounded" in s.calendar_years.caption


# ----------------------------------------------------------------------------- statuses and edge
def test_tr11_caption_names_the_skipped_days() -> None:
    d = dgp_a(rng_tr(11))
    frame = d.history.frame.drop(d.history.frame.index[[600, 1400, 2100]])
    hist = dataclasses.replace(d.history, frame=frame)
    rep = assemble_report("SYN", hist, d.factors, now=NOW, factors_downloaded_at=None)
    s = _section(rep)
    assert s.chart.n_excluded_in_span == 3
    assert "Skips 3 excluded days" in s.chart.caption
    assert s.point_in_time.sample.n_excluded == len(s.point_in_time.sample.excluded)


def test_tr16_section_sample_info_on_short_history() -> None:
    s = _section(_report(n=504))
    assert s.point_in_time.status == "ok" and s.point_in_time.hac_lags == 4
    assert s.point_in_time.sample.window == 252 and s.point_in_time.sample.n == 252


def test_beta_window_follows_the_report_window() -> None:
    rep = _report(n=1100, primary_window=126)
    s = _section(rep)
    assert s.beta_window == 126 and s.point_in_time.beta_window == 126
    assert s.point_in_time.sample.n == 1100 - 126
    assert s.rolling_alpha.window == 252  # fixed (RD9)


def test_exact_fit_is_not_applicable() -> None:
    d = dgp_residual(rng_tr(40), 700, e=np.zeros(700))
    rep = assemble_report("SYN", d.history, d.factors, now=NOW, factors_downloaded_at=None)
    s = _section(rep)
    assert s.status == "not_applicable" and s.reason == hook.EXACT_FIT_REASON
    assert s.in_sample.status == "not_applicable" and s.in_sample.z is None
    assert s.gap.verdict is None and s.chart.dates == []
    json.dumps(rep.model_dump(mode="json"), allow_nan=False)


def test_failed_regression_gives_the_failed_state() -> None:
    seen: list[SectionContext] = []
    original = hook.build_residual_analysis

    def spy(ctx: SectionContext) -> ResidualAnalysis | None:
        seen.append(ctx)
        return original(ctx)

    mp = pytest.MonkeyPatch()
    mp.setattr(hook, "build_residual_analysis", spy)
    try:
        _report(n=600)
    finally:
        mp.undo()
    (ctx,) = seen
    failed = hook.failed_section(ctx, 252)
    assert failed.status == "failed" and failed.reason == hook.REGRESSION_FAILED
    assert failed.in_sample.status == "failed" and failed.in_sample.residual_return_annual is None
    assert failed.in_sample.reason == "Full-sample regression unavailable"
    assert (
        FactorReport.model_validate_json(
            report_with_section(load_report(MOCK), "residual").model_dump_json()
        ).residual
        is not None
    )
    assert ResidualAnalysis.model_validate_json(failed.model_dump_json()) == failed


def test_wipe_out_becomes_a_warning() -> None:
    seen: list[SectionContext] = []
    original = hook.build_residual_analysis

    def spy(ctx: SectionContext) -> ResidualAnalysis | None:
        seen.append(ctx)
        return original(ctx)

    mp = pytest.MonkeyPatch()
    mp.setattr(hook, "build_residual_analysis", spy)
    try:
        _report(n=700)
    finally:
        mp.undo()
    (ctx,) = seen
    result = residual_analysis(ctx.sample, ctx.regression, ctx.rolling[252], exact_fit=False)
    when = result.dates[400]
    forced = dataclasses.replace(result, wipeouts=(when, when))
    section = hook.build_section(forced, rolling_betas(ctx.sample, 252), ctx)
    assert [w.code for w in section.warnings] == ["residual_wipeout"]
    assert section.warnings[0].message == (
        f"The hedged position lost all its capital on {when}; later days are not compounded."
    )


if __name__ == "__main__":
    FIXTURE.write_text(synthetic_section().model_dump_json() + "\n", encoding="utf-8")


def test_a_constant_factor_in_one_half_only_fails_the_split_half() -> None:
    """F2: a hook must not raise for data reasons (SC3.2).

    The CMA factor is zero on rows 1 to 700 of 1300, so the pooled split-half design is singular.
    The split-half part says so; the rest of the section still builds.
    """
    rng = rng_tr(38)
    f = rng.multivariate_normal(MU, SIGMA_F, size=1300)
    f[:700, 4] = 0.0
    d = dgp_a(rng, n=1300, f=f)
    report = assemble_report("SYN", d.history, d.factors, now=NOW, factors_downloaded_at=None)
    s = _section(report)
    assert s.status == "ok"
    assert s.split_half.status == "failed"
    assert s.split_half.reason == (
        "The split-half regression could not be fitted (singular factor design in one half)."
    )
    assert s.split_half.alpha_first_annual is None and s.split_half.difference_p is None
    assert s.in_sample.status == "ok"
    # the point-in-time betas need every window fitted; that part degrades with its own reason
    assert s.point_in_time.status in {"ok", "failed", "insufficient_data"}
    assert s.gap.status == s.point_in_time.status
    assert s.calendar_years.status == "ok"
