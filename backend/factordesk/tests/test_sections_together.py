"""Every optional section present in one report (schema v3 contract SC9).

The features build on separate branches and meet on an integration branch. These tests check that
they coexist: a report carrying the shrunk betas, residual alpha, Kalman betas, performance and
world beta sections, and ``data.security``, round-trips through the schema; the static page draws
the panels once each in registry order; and one section failing alone leaves the others (and the
core numbers) exactly as they were.

Shrunk fills only online (from the portfolio files), so its fixture stands in for it in the
pipeline report. The other four sections come from the real hooks on synthetic data.
"""

from __future__ import annotations

import functools
import json
import re
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import pytest

from factordesk.data.prices import Security
from factordesk.pipeline import assemble_report
from factordesk.report import load_report, render_report_html
from factordesk.report.base import SectionModel
from factordesk.report.panel_registry import registered_panels
from factordesk.report.schema import FactorReport, SecurityInfo
from factordesk.section_hooks import kalman as kalman_hook
from factordesk.section_hooks import performance as performance_hook
from factordesk.section_hooks import residual_alpha as residual_hook
from factordesk.section_hooks.context import SectionContext, SectionInputs, WorldBenchmarkInput
from factordesk.tests.fixtures.sections import report_with_section, section_labels
from factordesk.tests.test_world_beta import make_case

MOCK = Path(__file__).parent / "fixtures" / "mock_report.json"
NOW = datetime(2026, 11, 18, 15, 0, tzinfo=UTC)
SECURITY = Security(name="Example Corp", currency="USD", exchange="NASDAQ")

FIELDS = ("world_beta", "performance", "shrunk_betas", "residual", "kalman_betas")
"""The sections under test, in registry order."""
PANEL_NAME = {
    "world_beta": "world_beta",
    "performance": "performance",
    "shrunk_betas": "shrunk",
    "residual": "residual_alpha",
    "kalman_betas": "kalman",
}
PANEL_ID = {
    "world_beta": "world-beta",
    "performance": "performance",
    "shrunk_betas": "shrunk",
    "residual": "residual",
    "kalman_betas": "kalman",
}


def _all_sections() -> FactorReport:
    """The mock report (it carries ``data.security``) with the fixture of each section attached."""
    report = load_report(MOCK)
    for field in FIELDS:
        report = report_with_section(report, field)
    return report


def _pipeline_report(benchmark: WorldBenchmarkInput | None = None) -> FactorReport:
    """A pipeline report: four hooks fill their fields, the shrunk fixture is attached.

    ``benchmark`` is the ACWI input of the world beta; None is a healthy history.
    """
    case = make_case(3001, n=720)
    report = assemble_report(
        "STK",
        case.stock,
        case.factors,
        now=NOW,
        factors_downloaded_at=None,
        section_inputs=SectionInputs(
            world_benchmark=benchmark or WorldBenchmarkInput(history=case.bench)
        ),
        security=SECURITY,
    )
    assert report.shrunk_betas is None
    return report_with_section(report, "shrunk_betas")


@functools.cache
def _baseline() -> FactorReport:
    report = _pipeline_report()
    for field in FIELDS:
        assert getattr(report, field) is not None, field
    assert report.data.security == SecurityInfo(
        name="Example Corp", currency="USD", exchange="NASDAQ"
    )
    return report


def _panel_html(report: FactorReport) -> dict[str, str | None]:
    return {spec.name: spec.render(report) for spec in registered_panels()}


def _panel_ids(page: str) -> list[str]:
    return re.findall(r'<section class="panel[^"]*" id="([^"]+)"', page)


def test_all_sections_round_trip_through_the_schema() -> None:
    report = _all_sections()
    assert all(getattr(report, field) is not None for field in FIELDS)
    assert report.data.security is not None
    again = FactorReport.model_validate_json(report.model_dump_json())
    assert again == report
    assert again.schema_version == "4"


def test_the_pipeline_report_round_trips_with_every_section() -> None:
    report = _baseline()
    assert FactorReport.model_validate_json(report.model_dump_json()) == report


def test_all_sections_keep_their_footnote_texts() -> None:
    report = _all_sections()
    for field in FIELDS:
        for key, text in section_labels(field).items():
            assert report.label_text[key] == text, key


EXPECTED_ORDER = [
    "world-beta",
    "price",
    "performance",
    "exposures",
    "shrunk",
    "returns",
    "risk",
    "residual",
    "rolling",
    "kalman",
    "data",
]
"""Registry positions: world beta 350, price 400, performance 450, exposures 500, shrunk 520,
returns 600, risk 700, residual 710, rolling 800, Kalman 810, data 900."""


def test_all_panels_render_once_in_registry_order() -> None:
    page = render_report_html(_all_sections())
    ids = _panel_ids(page)
    for field in FIELDS:
        assert ids.count(PANEL_ID[field]) == 1, (field, ids)
    assert [i for i in ids if i in EXPECTED_ORDER] == EXPECTED_ORDER
    assert "Example Corp" in page  # the company line of the static header


def test_the_pipeline_report_renders_every_panel_in_registry_order() -> None:
    page = render_report_html(_baseline())
    ids = _panel_ids(page)
    assert [i for i in ids if i in EXPECTED_ORDER] == EXPECTED_ORDER
    assert "Example Corp" in page


@pytest.mark.parametrize("field", FIELDS)
def test_each_section_renders_alone(field: str) -> None:
    page = render_report_html(report_with_section(load_report(MOCK), field))
    assert f'id="{PANEL_ID[field]}"' in page
    for other in FIELDS:
        if other != field:
            assert f'id="{PANEL_ID[other]}"' not in page


def _fail_shrunk(monkeypatch: pytest.MonkeyPatch) -> FactorReport:
    payload = json.loads(_baseline().model_dump_json())
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


def _boom(*args: object, **kwargs: object) -> object:
    raise RuntimeError("internal failure")


def _fail_kalman(monkeypatch: pytest.MonkeyPatch) -> FactorReport:
    monkeypatch.setattr(kalman_hook, "kalman_betas", _boom)
    return _pipeline_report()


def _fail_performance(monkeypatch: pytest.MonkeyPatch) -> FactorReport:
    monkeypatch.setattr(performance_hook, "performance_stats", _boom)
    return _pipeline_report()


def _fail_world_beta(monkeypatch: pytest.MonkeyPatch) -> FactorReport:
    unavailable = WorldBenchmarkInput(history=None, unavailable_reason="The fund could not be read.")
    return _pipeline_report(unavailable)


FAILERS: dict[str, Callable[[pytest.MonkeyPatch], FactorReport]] = {
    "world_beta": _fail_world_beta,
    "performance": _fail_performance,
    "shrunk_betas": _fail_shrunk,
    "residual": _fail_residual,
    "kalman_betas": _fail_kalman,
}


@pytest.mark.parametrize("field", FIELDS)
def test_one_section_failing_alone_leaves_the_others_intact(
    field: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    baseline = _baseline()
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
    # Core numbers and the company name do not move either (SC1 item 8).
    assert broken.regression == baseline.regression
    assert broken.rolling == baseline.rolling
    assert broken.data.security == baseline.data.security
