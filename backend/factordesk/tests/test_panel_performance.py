"""Static Performance panel: numbers, states, wording, position (contract SC3.3). IDs TP41-TP50."""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

import pytest

from factordesk.report import FactorReport, load_report, render_report_html
from factordesk.report.panel_registry import registered_panels
from factordesk.report.panels import performance as panel
from factordesk.report.sections.performance import (
    DrawdownEpisodeInfo,
    PerformanceDrawdown,
    PerformanceSection,
    PerformanceSharpe,
)
from factordesk.tests.fixtures.sections import report_with_section

MOCK = Path(__file__).parent / "fixtures" / "mock_report.json"


def _report() -> FactorReport:
    return report_with_section(load_report(MOCK), "performance")


def _with(report: FactorReport, **update: object) -> FactorReport:
    assert report.performance is not None
    return report.model_copy(update={"performance": report.performance.model_copy(update=update)})


def _html(report: FactorReport) -> str:
    out = panel.render_performance_panel(report)
    assert out is not None
    return out


def _text(html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))


def test_tp41_absent_section_draws_nothing() -> None:
    report = load_report(MOCK)
    assert panel.render_performance_panel(report) is None
    page = render_report_html(report)
    assert 'id="performance"' not in page and "#performance" not in page


def test_tp42_panel_sits_right_after_price() -> None:
    assert [(p.name, p.position) for p in registered_panels() if p.name == "performance"] == [
        ("performance", 450)
    ]
    page = render_report_html(_report())
    ids = re.findall(r'<section class="panel[^"]*" id="([^"]+)"', page)
    assert ids.index("performance") == ids.index("price") + 1
    assert "#performance .kpis dl" in page  # the panel's stylesheet is inlined when it draws


def test_tp43_four_cell_strip_with_plain_lines() -> None:
    report = _report()
    html = _html(report)
    sec = report.performance
    assert sec is not None and sec.returns is not None and sec.drawdown is not None
    assert sec.sharpe is not None
    labels = re.findall(r"<dt>([^<]+)</dt>", html)
    assert labels == ["Return a year", "Volatility a year", "Sharpe ratio", "Worst fall"]
    assert len(re.findall(r'<div class="kpi ', html)) == 4
    text = _text(html)
    assert "Compound growth over the window" in text
    assert "Typical size of daily swings, scaled to a year" in text
    assert "Return above the risk-free rate per unit of risk; the interval includes zero" in text
    # The values come from the section, true minus sign for negatives.
    assert panel.fmt_pct(sec.returns.cagr, 1) in text
    assert panel.fmt_pct(sec.drawdown.max_drawdown, 1) in text
    assert "−7.2%" in text and "22.9%" in text and "−0.36" in text and "−41.0%" in text
    assert "Peak 2 Jan 2025, trough 12 Mar 2026, not recovered" in text


def test_tp44_sharpe_line_says_whether_the_interval_includes_zero() -> None:
    report = _report()
    assert report.performance is not None and report.performance.sharpe is not None
    sharpe = report.performance.sharpe.model_copy(
        update={"ratio_annual": 1.2, "ci95_low": 0.3, "ci95_high": 2.1, "ci_includes_zero": False}
    )
    text = _text(_html(_with(report, sharpe=sharpe)))
    assert "the interval does not include zero" in text and "1.20" in text
    assert "includes zero" not in text.replace("does not include zero", "")
    assert "from 0.30 to 2.10" in text
    assert "assumes independent daily returns" in text


def test_tp45_an_undefined_sharpe_ratio_shows_n_a_and_no_interval() -> None:
    report = _report()
    assert report.performance is not None and report.performance.sharpe is not None
    sharpe = PerformanceSharpe(
        ratio_annual=None,
        ratio_daily=None,
        mean_excess_annual=-0.01,
        sharpe_se_iid=None,
        ci95_low=None,
        ci95_high=None,
        ci_includes_zero=None,
    )
    text = _text(_html(_with(report, sharpe=sharpe)))
    assert "n/a" in text and "Not defined: the daily returns do not vary" in text
    assert "interval of the Sharpe ratio runs" not in text and "nan" not in text.lower()


def test_tp46_recovered_and_no_fall_states() -> None:
    report = _report()
    dd = PerformanceDrawdown(
        max_drawdown=-0.2,
        peak_date=date(2025, 1, 2),
        trough_date=date(2025, 3, 3),
        recovery_date=date(2025, 6, 2),
        days_peak_to_trough=40,
        days_trough_to_recovery=65,
        episodes=[
            DrawdownEpisodeInfo(
                depth=-0.2,
                peak_date=date(2025, 1, 2),
                trough_date=date(2025, 3, 3),
                recovery_date=date(2025, 6, 2),
                days_peak_to_trough=40,
                days_trough_to_recovery=65,
            )
        ],
    )
    text = _text(_html(_with(report, drawdown=dd)))
    assert "Peak 2 Jan 2025, trough 3 Mar 2025, recovered 2 Jun 2025" in text
    assert "−20.0%" in text
    none = PerformanceDrawdown(
        max_drawdown=0.0,
        peak_date=None,
        trough_date=None,
        recovery_date=None,
        days_peak_to_trough=None,
        days_trough_to_recovery=None,
        episodes=[],
    )
    html = _html(_with(report, drawdown=none))
    assert "No fall from an earlier high" in html and "Largest falls" not in html
    assert "<table" not in html


def test_tp47_drawdown_table_lists_the_episodes_deepest_first() -> None:
    html = _html(_report())
    rows = re.findall(r"<tbody>(.*?)</tbody>", html, flags=re.S)[0]
    parts = re.findall(r"<tr>(.*?)</tr>", rows, flags=re.S)
    assert len(parts) == 3
    first = _text(parts[0])
    assert "−41.0%" in first and "not recovered" in first and "310" in first and "n/a" in first
    second = _text(parts[1])
    assert "−10.1%" in second and "24 Dec 2024" in second and "15" in second and "7" in second
    assert 'scope="row"' in parts[0] and "<caption" in html


def test_tp48_text_states_no_future_and_has_the_footnote_and_fold() -> None:
    html = _html(_report())
    assert panel.FOOTNOTE == "Past performance does not predict future performance."
    assert html.count(panel.FOOTNOTE) == 1
    assert '<details class="how"><summary>How this is computed</summary>' in html
    text = _text(html).lower()
    for word in ("will ", "expect", "forecast", "predict future returns", "should", "likely"):
        assert word not in text.replace("does not predict future performance", "")
    for claim in ("significant", "reliable", "skill"):
        assert claim not in text


def test_tp49_not_ok_sections_show_their_reason_and_no_numbers() -> None:
    report = _report()
    for status, reason in (
        ("insufficient_data", "Insufficient data: performance needs at least 60 observations."),
        ("failed", "Performance could not be computed."),
    ):
        broken = report.model_copy(
            update={
                "performance": PerformanceSection(
                    status=status,  # type: ignore[arg-type]
                    reason=reason,
                    sample=report.regression.sample,
                    periods=None,
                    returns=None,
                    volatility_annual=None,
                    sharpe=None,
                    drawdown=None,
                )
            }
        )
        html = _html(broken)
        assert reason in html and 'class="empty"' in html
        assert "<dt>" not in html and "%" not in _text(html)
        assert panel.FOOTNOTE not in html


def test_tp50_the_page_keeps_the_header_and_other_panels_intact() -> None:
    base = render_report_html(load_report(MOCK))
    page = render_report_html(_report())
    stripped = re.sub(
        r'<section class="panel" id="performance".*?</section>\n', "", page, flags=re.S
    ).replace(panel.CSS, "")
    # Only the performance panel and its stylesheet are added; the rest is byte for byte as before.
    assert stripped == base


@pytest.mark.parametrize("width_class", ["kpis"])
def test_tp51_uses_existing_classes_only(width_class: str) -> None:
    html = _html(_report())
    classes = set(re.findall(r'class="([^"]+)"', html))
    flat = {c for entry in classes for c in entry.split()}
    allowed = {
        "panel", "panel-head", "q", width_class, "kpi", "v", "n", "ns", "perf-line", "reg-title",
        "perf-table-title", "scroll-x", "reg", "num", "vh", "foot", "how",
    }  # fmt: skip
    assert flat <= allowed, flat - allowed
