"""Shrunk betas and Kalman betas present in one report (schema v3 contract SC9)."""

from __future__ import annotations

import re
from pathlib import Path

from factordesk.report import load_report, render_report_html
from factordesk.report.schema import FactorReport
from factordesk.tests.fixtures.sections import report_with_section

MOCK = Path(__file__).parent / "fixtures" / "mock_report.json"
FIELDS = ("shrunk_betas", "kalman_betas")


def _both() -> FactorReport:
    report = load_report(MOCK)
    for field in FIELDS:
        report = report_with_section(report, field)
    return report


def test_both_sections_round_trip_through_the_schema() -> None:
    report = _both()
    assert all(getattr(report, field) is not None for field in FIELDS)
    again = FactorReport.model_validate_json(report.model_dump_json())
    assert again == report


def test_both_panels_render_once_in_registry_order() -> None:
    page = render_report_html(_both())
    ids = re.findall(r'<section class="panel[^"]*" id="([^"]+)"', page)
    assert ids.count("shrunk") == 1
    assert ids.count("kalman") == 1
    assert ids.index("exposures") < ids.index("shrunk") < ids.index("rolling")
    assert ids.index("rolling") < ids.index("kalman") < ids.index("data")


def test_each_section_renders_alone() -> None:
    for field, own, other in (
        ("shrunk_betas", "shrunk", "kalman"),
        ("kalman_betas", "kalman", "shrunk"),
    ):
        page = render_report_html(report_with_section(load_report(MOCK), field))
        assert f'id="{own}"' in page
        assert f'id="{other}"' not in page
