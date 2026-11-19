"""Panel registry of the static report (schema v3 contract SC3.3, SC4, SC9)."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from factordesk.report import load_report, render_report_html
from factordesk.report import render_html as render_module
from factordesk.report.panel_registry import PanelRegistry, PanelSpec, registered_panels
from factordesk.report.schema import FactorReport
from factordesk.tests.fixtures.sections import SECTION_FILES, report_with_section, section_payload

MOCK = Path(__file__).parent / "fixtures" / "mock_report.json"

ORDER = [
    ("header", 100),
    ("equation", 200),
    ("kpis", 300),
    ("price", 400),
    ("performance", 450),
    ("exposures", 500),
    ("alpha_strip", 502),
    ("world_beta", 505),
    ("lead_lag", 510),
    ("shrunk", 520),
    ("fragility", 530),
    ("returns", 600),
    ("risk", 700),
    ("residual_alpha", 710),
    ("rolling", 800),
    ("kalman", 810),
    ("data", 900),
    ("regression_detail", 1000),
    ("colophon", 1100),
]
"""Static panel order of contract SC4 (the React page adds ``notice`` at 150)."""

SECTION_PANELS = {
    "performance": ("performance", "price"),
    "lead_lag": ("lead-lag", "world-beta"),
    "shrunk_betas": ("shrunk", "lead-lag"),
    "fragility": ("fragility", "shrunk"),
    "world_beta": ("world-beta", "alpha-strip"),
    "alpha_strip": ("alpha-strip", "exposures"),
    "residual": ("residual", "risk"),
    "kalman_betas": ("kalman", "rolling"),
}
"""Element id of each optional section's panel, and the panel it follows.

The alpha strip (502) follows the exposures (500), the world beta panel (505) follows it and
lead-lag (510) follows the world beta."""


def _panel_ids(page: str) -> list[str]:
    return re.findall(r'<section class="panel[^"]*" id="([^"]+)"', page)


def _render_none(report: FactorReport) -> str | None:
    return None


def _render_other(report: FactorReport) -> str | None:
    return None


def test_registry_order_matches_the_contract() -> None:
    assert [(p.name, p.position) for p in registered_panels()] == ORDER


def test_registry_refuses_taken_names_and_positions() -> None:
    reg = PanelRegistry()
    reg.register("a", 10, _render_none)
    reg.register("a", 10, _render_none)  # the same function again (a module reload)
    with pytest.raises(ValueError, match="name"):
        reg.register("a", 20, _render_none)
    with pytest.raises(ValueError, match="name"):
        reg.register("a", 10, _render_other)
    with pytest.raises(ValueError, match="position"):
        reg.register("b", 10, _render_other)
    reg.register("b", 5, _render_other)
    assert [p.name for p in reg.ordered()] == ["b", "a"]


def test_absent_sections_draw_nothing() -> None:
    page = render_report_html(load_report(MOCK))
    ids = _panel_ids(page)
    for pid, _ in SECTION_PANELS.values():
        assert pid not in ids
        assert f'id="{pid}"' not in page


def test_present_sections_draw_their_frame_in_place() -> None:
    # Tail risk (E7a) has a React panel only; the static report has none.
    assert set(SECTION_PANELS) | {"tail_risk"} == set(SECTION_FILES)
    report = load_report(MOCK)
    for field in SECTION_PANELS:
        report = report_with_section(report, field)
    page = render_report_html(report)
    ids = _panel_ids(page)
    for pid, after in SECTION_PANELS.values():
        assert ids.index(pid) == ids.index(after) + 1, (pid, ids)
    # Sections whose fixture is still a contract placeholder draw the placeholder reason; a
    # feature that fills its fixture in drops out of the count (shrunk has two scopes).
    placeholder = "Placeholder (schema v3 contract)"
    expected = sum(
        json.dumps(section_payload(field)).count(placeholder) for field in SECTION_PANELS
    )
    assert page.count(placeholder) == expected


def test_panel_css_is_inlined_only_when_the_panel_draws(monkeypatch: pytest.MonkeyPatch) -> None:
    base = registered_panels()

    def drawn(report: FactorReport) -> str | None:
        return '<section class="panel" id="probe"></section>'

    css = ".probe-only{color:inherit}"
    for render, expected in ((drawn, True), (_render_none, False)):
        probe = PanelSpec(name="probe", position=9999, render=render, css=css)
        monkeypatch.setattr(render_module, "registered_panels", lambda p=probe: (*base, p))
        page = render_report_html(load_report(MOCK))
        assert (css in page) is expected
        assert ('id="probe"' in page) is expected
