"""Tail risk section: schema, hook, pipeline, fixtures (next-stage spec E7, task S1-9).

Run ``uv run python -m factordesk.tests.test_section_tail_risk`` to regenerate the synthetic
fixtures ``fixtures/sections/tail_risk.json`` (daily) and ``tail_risk_monthly.json`` (monthly,
60 months: the historical figures at 99% and 97.5% are n/a). The frontend reads the same files.
"""

from __future__ import annotations

import json
import math
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import numpy as np
import pandas as pd
import pytest
from pydantic import ValidationError

from factordesk.analytics.subject import subject_from_monthly_returns
from factordesk.analytics.tail_risk import MIN_OBS, tail_risk
from factordesk.pipeline import assemble_report, assemble_subject_report
from factordesk.report import FactorReport, load_report
from factordesk.report.schema import SECTIONS
from factordesk.report.sections.tail_risk import TAIL_RISK_SECTION, TailRiskSection
from factordesk.section_hooks import tail_risk as hook
from factordesk.section_hooks.context import SectionContext
from factordesk.section_hooks.registry import HOOKS
from factordesk.tests.fixtures.sections import report_with_section
from factordesk.tests.test_subject import monthly_case
from factordesk.tests.test_world_beta import make_case

FIXTURES = Path(__file__).parent / "fixtures"
MOCK = FIXTURES / "mock_report.json"
FIXTURE = FIXTURES / "sections" / "tail_risk.json"
FIXTURE_MONTHLY = FIXTURES / "sections" / "tail_risk_monthly.json"
NOW = datetime(2026, 11, 19, 12, 0, tzinfo=UTC)

DAILY_KEYS = [
    ("var", 0.99),
    ("cvar", 0.975),
]
MONTHLY_KEYS = [("var", 0.99), ("cvar", 0.975), ("var", 0.95), ("cvar", 0.95)]
METHODS = ["historical", "gaussian", "cornish_fisher"]


def daily_report() -> tuple[FactorReport, SectionContext]:
    """A ticker report (720 trading days) and the context its tail risk hook saw."""
    case = make_case(3001, n=720)
    seen: list[SectionContext] = []
    real = hook.build_tail_risk

    def spy(ctx: SectionContext) -> TailRiskSection | None:
        seen.append(ctx)
        return real(ctx)

    hook.build_tail_risk = spy  # the registry reads the attribute at call time
    try:
        report = assemble_report(
            "STK", case.stock, case.factors, now=NOW, factors_downloaded_at=None
        )
    finally:
        hook.build_tail_risk = real
    (ctx,) = seen
    return report, ctx


def monthly_report(n: int = 60, seed: int = 11) -> FactorReport:
    returns, factors, _ = monthly_case(n, seed)
    subject = subject_from_monthly_returns(returns, label="Example Fund")
    return assemble_subject_report(subject, factors, now=NOW, factors_downloaded_at=None)


def _keys(section: TailRiskSection) -> list[tuple[str, float]]:
    assert section.figures is not None
    seen: list[tuple[str, float]] = []
    for f in section.figures:
        if (f.measure, f.level) not in seen:
            seen.append((f.measure, f.level))
    return seen


# ----------------------------------------------------------------------------- registry, schema
def test_the_section_is_registered_for_every_source_and_frequency() -> None:
    spec = next(s for s in HOOKS if s.field == "tail_risk")
    for kind in ("ticker", "upload", "portfolio"):
        for freq in ("daily", "monthly"):
            for model in ("ff5", "ff6"):
                assert spec.applies(kind, freq, model)  # pyright: ignore[reportArgumentType]
    assert TAIL_RISK_SECTION in SECTIONS
    info = FactorReport.model_fields["tail_risk"]
    assert info.default is None and not info.is_required()
    assert TAIL_RISK_SECTION.statistic_models == () and not TAIL_RISK_SECTION.label_text


def test_a_not_ok_section_holds_no_part_and_an_ok_one_holds_all() -> None:
    section = TailRiskSection.model_validate_json(FIXTURE.read_text(encoding="utf-8"))
    payload = json.loads(section.model_dump_json())
    for part in ("frequency", "series", "figures"):
        broken = {**payload, part: None}
        with pytest.raises(ValidationError, match="exactly when status is 'ok'"):
            TailRiskSection.model_validate_json(json.dumps(broken))
    with pytest.raises(ValidationError, match="reason must be None"):
        TailRiskSection.model_validate_json(json.dumps({**payload, "status": "failed"}))


# ----------------------------------------------------------------------------- daily hook
def test_daily_hook_output_matches_the_analytics_and_has_two_levels() -> None:
    report, ctx = daily_report()
    section = report.tail_risk
    assert section is not None and section.status == "ok" and section.reason is None
    assert section.frequency == "daily"
    assert _keys(section) == DAILY_KEYS
    expected = tail_risk(ctx.subject.returns.dropna().to_numpy(), "daily")
    assert section.series is not None
    assert section.series.n_obs == expected.n_obs == 720
    assert section.series.bootstrap == "stationary" and section.series.seed == 0
    assert section.series.mean_block_length == expected.mean_block_length
    assert section.figures is not None and len(section.figures) == 6
    for got, want in zip(section.figures, expected.figures, strict=True):
        assert (got.method, got.measure, got.level) == (want.method, want.measure, want.level)
        assert got.value == want.value and got.indicative == want.indicative
        assert got.tail_count == want.tail_count
        assert got.expected_tail_obs == want.expected_tail_obs
        assert got.band_quality == want.band_quality and got.band_reason == want.band_reason
        assert (got.band is None) == (want.band is None)
        if got.band is not None and want.band is not None:
            assert (got.band.low, got.band.high) == (want.band.low, want.band.high)
            assert got.band.resamples == want.band.resamples
    assert [f.method for f in section.figures[:3]] == METHODS
    var99 = section.figures[0]
    assert var99.value is not None and 0.0 < var99.value < 0.2
    assert var99.band is not None and var99.band.low <= var99.value <= var99.band.high
    assert var99.band_quality == "validated" and var99.tail_count is not None
    assert section.figures[3].method == "historical" and section.figures[3].measure == "cvar"
    assert section.figures[3].band_quality == "approximate"
    # The sample block is the regression sample of the report; the section changes nothing else.
    assert section.sample == report.regression.sample
    assert report.model_copy(update={"tail_risk": None}).tail_risk is None


# ----------------------------------------------------------------------------- monthly hook
def test_monthly_hook_output_has_four_levels_and_the_95_rows() -> None:
    report = monthly_report(120, 13)
    section = report.tail_risk
    assert section is not None and section.status == "ok" and section.frequency == "monthly"
    assert _keys(section) == MONTHLY_KEYS
    assert section.series is not None
    assert section.series.n_obs == 120 and section.series.bootstrap == "iid"
    assert section.series.mean_block_length is None and section.series.n_resamples == 1000
    assert section.figures is not None and len(section.figures) == 12
    by = {(f.method, f.measure, f.level): f for f in section.figures}
    for method in ("historical", "gaussian", "cornish_fisher"):
        for measure in ("var", "cvar"):
            f = by[(method, measure, 0.95)]
            assert f.expected_tail_obs == pytest.approx(6.0)
    h95 = by[("historical", "var", 0.95)]
    assert h95.value is not None and h95.reason is None and h95.tail_count is not None
    # 120 x 1% = 1.2 expected tail months: the historical 99% VaR is n/a, with its reason.
    h99 = by[("historical", "var", 0.99)]
    assert h99.value is None and h99.band is None and h99.tail_count is None
    assert h99.reason == "1.2 expected tail observations"
    assert by[("gaussian", "var", 0.99)].value is not None


def test_thirty_six_months_give_na_rows_with_their_reasons() -> None:
    report = monthly_report(36, 21)
    section = report.tail_risk
    assert section is not None and section.status == "ok" and section.figures is not None
    by = {(f.method, f.measure, f.level): f for f in section.figures}
    # n x (1 - level): 0.36 at 99%, 0.9 at 97.5%, 1.8 at 95% (the 95% rule needs 2).
    expected = {(("var", 0.99)): "0.4", ("cvar", 0.975): "0.9", ("var", 0.95): "1.8"}
    for (measure, level), text in expected.items():
        f = by[("historical", measure, level)]
        assert f.value is None and f.band is None and f.band_quality is None
        assert f.reason == f"{text} expected tail observations", (measure, level, f.reason)
        assert f.tail_count is None
    assert by[("historical", "cvar", 0.95)].value is None
    # The Gaussian figures stay, with bands and the count of observations behind them.
    for measure, level in MONTHLY_KEYS:
        g = by[("gaussian", measure, level)]
        assert g.value is not None and g.band is not None and g.reason is None
    assert section.series is not None and section.series.n_obs == 36


def test_cornish_fisher_na_and_indicative_figures_carry_a_reason() -> None:
    for seed in range(1, 30):
        section = monthly_report(48, seed).tail_risk
        assert section is not None and section.figures is not None
        for f in section.figures:
            if f.method == "cornish_fisher" and f.value is None:
                assert f.reason is not None and "valid range" in f.reason
            if f.indicative:
                assert f.value is not None and f.reason is not None
                assert "indicative" in f.reason


# ----------------------------------------------------------------------------- failure paths
def _with_returns(ctx: SectionContext, returns: pd.Series) -> SectionContext:
    """The hook reads only the subject's frequency and returns, the sample and ``sample_info``."""
    subject = SimpleNamespace(frequency=ctx.subject.frequency, returns=returns)
    return cast(
        SectionContext,
        SimpleNamespace(subject=subject, sample=ctx.sample, sample_info=ctx.sample_info),
    )


def test_short_series_is_insufficient_and_constant_series_fails() -> None:
    _, ctx = daily_report()
    returns = ctx.subject.returns
    short = hook.build_tail_risk(_with_returns(ctx, returns.iloc[: MIN_OBS - 1]))
    assert short is not None and short.status == "insufficient_data"
    assert short.reason is not None and str(MIN_OBS) in short.reason
    assert short.figures is None and short.series is None
    flat = hook.build_tail_risk(_with_returns(ctx, returns * 0.0 + 0.001))
    assert flat is not None and flat.status == "failed"
    assert flat.reason is not None and "constant" in flat.reason and flat.figures is None


def test_the_tail_risk_window_is_the_analysed_window_for_a_3y_range() -> None:
    """A report limited to the last 3 years describes those days, not the whole history."""
    case = make_case(3001, n=1500)
    last = case.dates[-1].date()
    start = (pd.Timestamp(last) - pd.DateOffset(years=3)).date()
    full = assemble_report("STK", case.stock, case.factors, now=NOW, factors_downloaded_at=None)
    cut = assemble_report(
        "STK", case.stock, case.factors, start=start, now=NOW, factors_downloaded_at=None
    )
    assert full.tail_risk is not None and full.tail_risk.series is not None
    assert cut.tail_risk is not None and cut.tail_risk.series is not None
    window_n = cut.regression.sample.n
    assert abs(window_n - 756) <= 0.05 * 756  # about 3 years of daily rows
    assert cut.tail_risk.series.n_obs == window_n
    assert cut.tail_risk.sample.start == cut.regression.sample.start
    assert cut.tail_risk.series.n_obs < full.tail_risk.series.n_obs
    assert full.tail_risk.series.n_obs == full.regression.sample.n


def test_based_on_counts_exactly_the_returns_of_the_analysed_sample(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Days inside the window that the sample excludes are not in the tail series or its count."""
    case = make_case(3001, n=720)
    factors = case.factors.drop(case.factors.index[[10, 200, 400]])  # no factor row on 3 days
    used: list[np.ndarray] = []
    real = hook.tail_risk

    def spy(returns: np.ndarray, frequency: str, **kwargs: object) -> object:
        used.append(np.asarray(returns))
        return real(returns, frequency, **kwargs)  # pyright: ignore[reportArgumentType]

    monkeypatch.setattr(hook, "tail_risk", spy)
    report = assemble_report("STK", case.stock, factors, now=NOW, factors_downloaded_at=None)
    section = report.tail_risk
    assert section is not None and section.series is not None
    sample = report.regression.sample
    assert sample.n_excluded == 3
    # Every return the window holds, before the sample drops any.
    in_window = case.stock.total_returns.loc[str(sample.start) : str(sample.end)].dropna()
    assert len(in_window) == sample.n + sample.n_excluded
    (series,) = used
    assert section.series.n_obs == len(series) == sample.n == len(in_window) - 3
    excluded = {pd.Timestamp(e.date) for e in sample.excluded}
    kept = in_window[~in_window.index.isin(excluded)]
    assert np.allclose(series, kept.to_numpy(), rtol=0.0, atol=1e-15)


def test_missing_returns_are_dropped_not_fatal() -> None:
    _, ctx = daily_report()
    holed = ctx.subject.returns.copy()
    holed.iloc[[5, 100]] = float("nan")
    section = hook.build_tail_risk(_with_returns(ctx, holed))
    assert section is not None and section.status == "ok" and section.series is not None
    assert section.series.n_obs == len(holed) - 2


def test_an_unexpected_error_marks_the_section_failed(monkeypatch: pytest.MonkeyPatch) -> None:
    _, ctx = daily_report()

    def boom(*_a: object, **_k: object) -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr(hook, "tail_risk", boom)
    section = hook.build_tail_risk(ctx)
    assert section is not None and section.status == "failed" and section.reason == hook.FAILED


# ----------------------------------------------------------------------------- fixtures
def test_fixtures_are_sections_of_the_real_shape() -> None:
    daily = TailRiskSection.model_validate_json(FIXTURE.read_text(encoding="utf-8"))
    monthly = TailRiskSection.model_validate_json(FIXTURE_MONTHLY.read_text(encoding="utf-8"))
    assert daily.status == monthly.status == "ok"
    assert daily.frequency == "daily" and monthly.frequency == "monthly"
    assert _keys(daily) == DAILY_KEYS and _keys(monthly) == MONTHLY_KEYS
    assert monthly.series is not None and monthly.series.n_obs == 60
    assert monthly.figures is not None
    assert any(f.value is None and f.reason for f in monthly.figures)
    assert math.isclose(monthly.series.band_level, 0.9)
    mock = load_report(MOCK)
    assert report_with_section(mock, "tail_risk").tail_risk == daily


# ----------------------------------------------------------------------------- fixture writer
def _write(path: Path, section: TailRiskSection | None) -> None:
    assert section is not None
    path.write_text(section.model_dump_json() + "\n", encoding="utf-8", newline="\n")


def main() -> None:
    """Write both fixtures from the pipeline on synthetic data."""
    mock = load_report(MOCK)
    daily, _ = daily_report()
    section = daily.tail_risk
    assert section is not None
    # Show the fixture on the mock report's sample block, as the other section fixtures do.
    _write(FIXTURE, section.model_copy(update={"sample": mock.regression.sample}))
    monthly = monthly_report(60, 11).tail_risk
    assert monthly is not None
    _write(FIXTURE_MONTHLY, monthly.model_copy(update={"sample": mock.regression.sample}))


if __name__ == "__main__":
    main()
