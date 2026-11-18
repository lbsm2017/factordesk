"""Shrunk betas, residual alpha and Kalman betas present in one report (schema v3 contract SC9).

The three features build on separate branches and meet on ``integrate/features``. These tests
check that they coexist: the schema round trip, the static page in registry order, and that one
section failing alone leaves the other two exactly as they were.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import pytest

from factordesk.pipeline import assemble_report
from factordesk.report import load_report, render_report_html
from factordesk.report.base import SectionModel
from factordesk.report.panel_registry import registered_panels
from factordesk.report.schema import FactorReport
from factordesk.section_hooks import kalman as kalman_hook
from factordesk.section_hooks import residual_alpha as residual_hook
from factordesk.section_hooks.context import SectionContext
from factordesk.tests.fixtures.dgp import dgp_a, rng_for
from factordesk.tests.fixtures.sections import report_with_section, section_labels

MOCK = Path(__file__).parent / "fixtures" / "mock_report.json"
NOW = datetime(2026, 11, 18, 15, 0, tzinfo=UTC)

FIELDS = ("shrunk_betas", "residual", "kalman_betas")
PANEL_NAME = {"shrunk_betas": "shrunk", "residual": "residual_alpha", "kalman_betas": "kalman"}
PANEL_ID = {"shrunk_betas": "shrunk", "residual": "residual", "kalman_betas": "kalman"}


def _all_three() -> FactorReport:
    """The mock report with the fixture of each of the three sections attached."""
    report = load_report(MOCK)
    for field in FIELDS:
        report = report_with_section(report, field)
    return report


def _pipeline_report() -> FactorReport:
    """A pipeline report: the residual and Kalman hooks fill their fields, shrunk is attached.

    Shrunk fills only online (from the portfolio files), so its fixture stands in for it.
    """
    d = dgp_a(rng_for(3001), n=600)
    report = assemble_report("SYN", d.history, d.factors, now=NOW, factors_downloaded_at=None)
    assert report.residual is not None and report.kalman_betas is not None
    assert report.shrunk_betas is None
    return report_with_section(report, "shrunk_betas")


def _panel_html(report: FactorReport) -> dict[str, str | None]:
    return {spec.name: spec.render(report) for spec in registered_panels()}


def test_three_sections_round_trip_through_the_schema() -> None:
    report = _all_three()
    assert all(getattr(report, field) is not None for field in FIELDS)
    again = FactorReport.model_validate_json(report.model_dump_json())
    assert again == report


def test_three_sections_keep_their_footnote_texts() -> None:
    report = _all_three()
    for field in FIELDS:
        for key, text in section_labels(field).items():
            assert report.label_text[key] == text, key


def test_three_panels_render_once_in_registry_order() -> None:
    page = render_report_html(_all_three())
    ids = re.findall(r'<section class="panel[^"]*" id="([^"]+)"', page)
    for field in FIELDS:
        assert ids.count(PANEL_ID[field]) == 1, (field, ids)
    # Contract SC4: shrunk 520, residual 710, Kalman 810.
    assert ids.index("exposures") < ids.index("shrunk") < ids.index("returns")
    assert ids.index("risk") < ids.index("residual") < ids.index("rolling")
    assert ids.index("rolling") < ids.index("kalman") < ids.index("data")


@pytest.mark.parametrize("field", FIELDS)
def test_each_section_renders_alone(field: str) -> None:
    page = render_report_html(report_with_section(load_report(MOCK), field))
    assert f'id="{PANEL_ID[field]}"' in page
    for other in FIELDS:
        if other != field:
            assert f'id="{PANEL_ID[other]}"' not in page


def _fail_shrunk(monkeypatch: pytest.MonkeyPatch) -> FactorReport:
    payload = json.loads(_pipeline_report().model_dump_json())
    for entry in payload["shrunk_betas"]:
        entry.update(
            status="failed",
            reason="The prior is unavailable (prior_unavailable).",
            prior=None,
            betas=[],
            power=[],
        )
    return FactorReport.model_validate_json(json.dumps(payload))


def _fail_residual(monkeypatch: pytest.MonkeyPatch) -> FactorReport:
    def failed(ctx: SectionContext) -> object:
        return residual_hook.failed_section(ctx, ctx.primary_window)

    monkeypatch.setattr(residual_hook, "build_residual_analysis", failed)
    return _pipeline_report()


def _fail_kalman(monkeypatch: pytest.MonkeyPatch) -> FactorReport:
    def boom(*args: object, **kwargs: object) -> object:
        raise RuntimeError("internal failure")

    monkeypatch.setattr(kalman_hook, "kalman_betas", boom)
    return _pipeline_report()


FAILERS: dict[str, Callable[[pytest.MonkeyPatch], FactorReport]] = {
    "shrunk_betas": _fail_shrunk,
    "residual": _fail_residual,
    "kalman_betas": _fail_kalman,
}


@pytest.mark.parametrize("field", FIELDS)
def test_one_section_failing_alone_leaves_the_others_intact(
    field: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    baseline = _pipeline_report()
    before = _panel_html(baseline)

    broken = FAILERS[field](monkeypatch)

    # The failed section says so in the schema and on the page, and the file still round-trips.
    failed: Any = getattr(broken, field)
    entries = cast(list[SectionModel], failed if isinstance(failed, list) else [failed])
    assert all(entry.status == "failed" and entry.reason for entry in entries), field
    assert FactorReport.model_validate_json(broken.model_dump_json()) == broken
    assert f'id="{PANEL_ID[field]}"' in render_report_html(broken)

    # Every other section, and its panel, is exactly what it was without the failure.
    after = _panel_html(broken)
    assert after[PANEL_NAME[field]] != before[PANEL_NAME[field]]
    for other in FIELDS:
        if other != field:
            assert getattr(broken, other) == getattr(baseline, other), other
            assert after[PANEL_NAME[other]] == before[PANEL_NAME[other]], other
    # Core numbers do not move either (SC1 item 8).
    assert broken.regression == baseline.regression
    assert broken.rolling == baseline.rolling
