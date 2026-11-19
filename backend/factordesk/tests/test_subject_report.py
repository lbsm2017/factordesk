"""Reports on return subjects: ``assemble_subject_report`` and the hook registry (E0-T2).

* Monthly subjects: daily-only sections are hidden (``None``), rolling windows, average beta,
  quality gate and 5-day estimate are ``not_applicable`` with a reason, annualisation uses 12,
  the 36/60 floors refuse and warn, the level audit replaces the price audit.
* A daily subject that is not a ticker (same returns as a ticker) gets the same statistics and
  every section: no hook depends on the price frame any more.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime

import numpy as np
import pandas as pd
import pytest

from factordesk.analytics.sample import InsufficientHistoryError
from factordesk.analytics.subject import (
    ReturnSubject,
    subject_from_history,
    subject_from_monthly_returns,
)
from factordesk.data import french
from factordesk.data.audit import AuditFinding, audit_levels
from factordesk.data.prices import Security, UnsupportedCurrencyError
from factordesk.pipeline import (
    NOT_DAILY_GATE,
    NOTE_MONTHLY,
    NOTE_SURVIVORSHIP,
    assemble_report,
    assemble_subject_report,
    unique_dates,
)
from factordesk.report.schema import LABEL_TEXT, SECTIONS, FactorReport, report_label_text
from factordesk.section_hooks.context import SectionInputs, WorldBenchmarkInput
from factordesk.section_hooks.registry import HOOKS, HookSpec, run_hooks
from factordesk.tests.test_subject import monthly_case
from factordesk.tests.test_world_beta import make_case

NOW = datetime(2026, 11, 19, 12, 0, tzinfo=UTC)
DAILY_ONLY = ("lead_lag", "shrunk_betas", "fragility", "world_beta", "residual", "kalman_betas")


def monthly_report(n: int = 72, seed: int = 11, **kwargs: object) -> FactorReport:
    returns, factors, _ = monthly_case(n, seed)
    subject = subject_from_monthly_returns(returns, label="Example Fund")
    return assemble_subject_report(
        subject,
        factors,
        now=NOW,
        factors_downloaded_at=None,
        **kwargs,  # pyright: ignore[reportArgumentType]
    )


def _world_inputs() -> SectionInputs:
    case = make_case(3001, n=720)
    return SectionInputs(world_benchmark=WorldBenchmarkInput(history=case.bench))


# ----------------------------------------------------------------------------- registry
def test_registry_covers_every_optional_section_once() -> None:
    fields = [spec.field for spec in HOOKS]
    assert len(fields) == len(set(fields))
    assert set(fields) == {spec.report_field for spec in SECTIONS}


@pytest.mark.parametrize("field", DAILY_ONLY)
def test_daily_only_hooks_decline_monthly(field: str) -> None:
    spec = next(s for s in HOOKS if s.field == field)
    assert spec.applies("ticker", "daily", "ff5")
    assert spec.applies("upload", "daily", "ff5")
    assert not spec.applies("upload", "monthly", "ff5")
    assert not spec.applies("ticker", "monthly", "ff5")


def test_performance_runs_everywhere_and_model_gates() -> None:
    perf = next(s for s in HOOKS if s.field == "performance")
    for kind in ("ticker", "upload", "portfolio"):
        for freq in ("daily", "monthly"):
            assert perf.applies(kind, freq, "ff5") and perf.applies(kind, freq, "ff6")  # pyright: ignore[reportArgumentType]
    kalman = next(s for s in HOOKS if s.field == "kalman_betas")
    assert not kalman.applies("ticker", "daily", "ff6")


def test_run_hooks_calls_only_applicable_hooks() -> None:
    calls: list[str] = []
    case = make_case(3002, n=600)
    report = assemble_report("STK", case.stock, case.factors, now=NOW, factors_downloaded_at=None)
    assert report.performance is not None

    def hook(name: str):  # noqa: ANN202 - a tiny closure factory
        def build(_ctx: object) -> str:
            calls.append(name)
            return name

        return build

    hooks = (
        HookSpec("a", hook("a"), frozenset({"upload"}), frozenset({"monthly"}), frozenset({"ff5"})),
        HookSpec("b", hook("b"), frozenset({"upload"}), frozenset({"daily"}), frozenset({"ff5"})),
    )

    class Ctx:
        subject = subject_from_monthly_returns(monthly_case(3, 1)[0], label="F")
        model = "ff5"

    out = run_hooks(Ctx(), hooks)  # pyright: ignore[reportArgumentType]
    assert out == {"a": "a", "b": None} and calls == ["a"]


# ----------------------------------------------------------------------------- monthly report
def test_monthly_report_hides_the_daily_only_sections() -> None:
    report = monthly_report(section_inputs=_world_inputs())
    for field in DAILY_ONLY:
        assert getattr(report, field) is None, field
    assert report.performance is not None and report.performance.status == "ok"
    present = {"performance": report.performance}
    assert report.label_text == report_label_text(present)
    assert set(LABEL_TEXT) <= set(report.label_text)


def test_monthly_report_marks_daily_core_sections_not_applicable() -> None:
    report = monthly_report()
    assert [w.window for w in report.rolling] == [126, 252]
    for window in report.rolling:
        assert window.status == "not_applicable"
        assert window.reason is not None and "daily returns only" in window.reason
        assert window.dates == [] and window.betas == {}
    assert report.average_beta.status == "not_applicable"
    assert report.average_beta.reason is not None
    assert report.quality_gate.status == "not_applicable"
    assert report.quality_gate.reason == NOT_DAILY_GATE
    assert report.five_day_regression.status == "not_applicable"
    assert report.five_day_regression.reason is not None
    assert "gate does not apply to monthly" in report.five_day_regression.reason
    diag = report.residual_diagnostics
    assert diag.status == "ok" and "quality gate" not in diag.caption
    assert not any(w.code == "residual_reversal" for w in report.warnings)


def test_monthly_report_annualises_with_twelve() -> None:
    n = 72
    returns, factors, _ = monthly_case(n, 11)
    report = monthly_report(n, 11)
    reg = report.regression
    assert reg.status == "ok" and reg.sample.n == n and report.data.n_obs == n
    assert reg.hac_lags == math.floor(4 * (n / 100) ** (2 / 9))
    assert reg.alpha_ci_low_annual is not None and reg.alpha_ci_high_annual is not None
    assert reg.alpha_annual is not None
    # The interval is symmetric around alpha: (low + high) / 2 = 12 x intercept = alpha_annual.
    mid = (reg.alpha_ci_low_annual + reg.alpha_ci_high_annual) / 2
    assert mid == pytest.approx(reg.alpha_annual, rel=1e-12)
    assert "(x12)" in report.return_contribution.caption
    total = report.return_contribution.total_annualised_mean_excess_return
    xret = returns.to_numpy() - factors["RF"].to_numpy()[:n]
    assert total == pytest.approx(12 * float(xret.mean()), rel=1e-12)
    vol = report.risk_contribution.total_vol_annual
    assert vol == pytest.approx(math.sqrt(12 * float(xret.var(ddof=1))), rel=1e-12)
    perf = report.performance
    assert perf is not None and perf.periods is not None and perf.returns is not None
    assert perf.periods.n_days == n and perf.periods.years == pytest.approx(6.0)
    growth = float((1.0 + returns.to_numpy()).prod())
    assert perf.returns.cagr == pytest.approx(growth ** (12 / n) - 1.0, rel=1e-12)


def test_monthly_report_provenance_levels_and_notes() -> None:
    report = monthly_report(48, 12)
    assert report.ticker == "Example Fund"
    assert report.data.factors_source_url == french.DATASETS["ff5_monthly"].url
    assert report.data.price_source == "upload (monthly returns)"
    assert report.data.security is None
    series = report.price_series
    assert series.dates[0] == pd.Timestamp("1989-12-31").date()
    assert series.adj_close[0] == 100.0 and len(series.dates) == 49
    assert NOTE_MONTHLY in report.notes and NOTE_SURVIVORSHIP not in report.notes
    short = [w for w in report.warnings if w.code == "short_history"]
    assert (
        len(short) == 1 and "48 monthly observations (fewer than 60, 5 years)" in short[0].message
    )
    memo = report.return_contribution.memo
    assert memo[0].startswith("Not covered by factor data: none")


def test_monthly_report_without_short_history_warning_at_60() -> None:
    report = monthly_report(60, 13)
    assert not any(w.code == "short_history" for w in report.warnings)


def test_monthly_report_below_36_months_is_refused() -> None:
    with pytest.raises(InsufficientHistoryError) as info:
        monthly_report(35, 14)
    assert info.value.required == 36 and info.value.frequency == "monthly"


def test_uncovered_months_are_named_in_months() -> None:
    returns, factors, _ = monthly_case(70, 15)
    subject = subject_from_monthly_returns(returns, label="Example Fund")
    report = assemble_subject_report(
        subject, factors.iloc[:-3], now=NOW, factors_downloaded_at=None
    )
    assert report.data.uncovered.n == 3
    assert "3 months after" in report.return_contribution.memo[0]
    assert "track record return" in report.return_contribution.memo[0]
    lag = [w for w in report.warnings if w.code == "factor_data_lag"]
    assert lag and "3 later months are not analysed" in lag[0].message


def test_non_usd_subject_and_unknown_model_are_refused() -> None:
    returns, factors, _ = monthly_case(40, 16)
    eur = subject_from_monthly_returns(returns, label="Euro Fund", currency="EUR")
    with pytest.raises(UnsupportedCurrencyError):
        assemble_subject_report(eur, factors, now=NOW, factors_downloaded_at=None)
    usd = subject_from_monthly_returns(returns, label="Fund")
    with pytest.raises(ValueError, match="ff6"):
        assemble_subject_report(usd, factors, "ff6", now=NOW, factors_downloaded_at=None)


def test_subject_findings_join_the_audit() -> None:
    returns, factors, _ = monthly_case(40, 17)
    finding = AuditFinding("nav_reconstructed", "warn", "Returns were derived from NAVs.", ())
    subject = subject_from_monthly_returns(returns, label="Fund", findings=(finding,))
    report = assemble_subject_report(subject, factors, now=NOW, factors_downloaded_at=None)
    codes = [f.code for f in report.data.audit_findings]
    assert codes[-1] == "nav_reconstructed" and report.data.audit_status == "warnings"


# ----------------------------------------------------------------------------- level audit
def test_level_audit_monthly() -> None:
    idx = pd.date_range("2020-01-31", periods=10, freq="ME")
    values = [100.0, 100.0, 100.0, 100.0, 100.0, 150.0, 151.0, float("nan"), 152.0, 153.0]
    report = audit_levels(pd.Series(values, index=idx), "monthly")
    codes = {f.code: f for f in report.findings}
    assert codes["stale_run"].severity == "warn"
    assert codes["large_return"].dates == (idx[5].date(),)
    assert "months with |return| > 40%" in codes["large_return"].message
    assert codes["nan_price"].severity == "error" and not report.ok
    assert "gap_run" not in codes and "gaps_fraction" not in codes  # no business-day rule
    gap = audit_levels(pd.Series([1.0, 1.1, 1.2], index=idx[[0, 1, 4]]), "monthly")
    assert [f.code for f in gap.findings] == ["gap_run"]
    clean = audit_levels(pd.Series(np.linspace(100, 120, 10), index=idx), "monthly")
    assert clean.findings == () and clean.ok


# ----------------------------------------------------------------------------- daily non-ticker
def test_daily_upload_subject_matches_the_ticker_statistics() -> None:
    """Same daily returns as a ticker, as an upload: identical statistics, all sections run."""
    case = make_case(3001, n=720)
    security = Security(name="Example Corp", currency="USD", exchange="NASDAQ")
    ticker = assemble_report(
        "STK",
        case.stock,
        case.factors,
        now=NOW,
        factors_downloaded_at=None,
        section_inputs=_world_inputs(),
        security=security,
    )
    ticker_subject = subject_from_history(unique_dates(case.stock), label="STK")
    upload = ReturnSubject(
        kind="upload",
        label="STK",
        frequency="daily",
        returns=ticker_subject.returns,
        calendar=ticker_subject.calendar,
        levels=ticker_subject.levels,
        source="upload",
        currency="USD",
    )
    report = assemble_subject_report(
        upload,
        case.factors,
        now=NOW,
        factors_downloaded_at=None,
        section_inputs=_world_inputs(),
    )
    for field in (
        "regression",
        "rolling",
        "average_beta",
        "return_contribution",
        "risk_contribution",
        "residual_diagnostics",
        "quality_gate",
        "five_day_regression",
        "performance",
        "world_beta",
        "residual",
        "kalman_betas",
        "price_series",
    ):
        if field == "return_contribution":
            a = ticker.return_contribution.model_copy(update={"memo": []})
            b = report.return_contribution.model_copy(update={"memo": []})
            assert a == b
            continue
        assert getattr(report, field) == getattr(ticker, field), field
    assert report.world_beta is not None and report.kalman_betas is not None
    assert report.data.price_source == "upload (daily returns)"
