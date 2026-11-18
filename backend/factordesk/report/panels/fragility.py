"""Static HTML panel of the ``fragility`` section (contract SC2.1).

Spec: ``docs/specs/fragility-score.md``. Owned by the feature branch, which replaces the placeholder
body. Registered at position 530 as ``fragility``. Placeholder: nothing when the section is
absent; when present, the panel frame with the empty state if its status is not ``ok``.
"""

from __future__ import annotations

from factordesk.report.panel_registry import register_panel
from factordesk.report.render_html import empty_state, panel_head, panel_section
from factordesk.report.schema import FactorReport

PANEL_ID = "fragility"
TITLE = "Fragility"
QUESTION = "How many trading days does each significant result rest on?"


def render_fragility_panel(report: FactorReport) -> str | None:
    """The panel's HTML, or ``None`` when the section was not computed."""
    section = report.fragility
    if section is None:
        return None
    body = empty_state(section.reason or "") if section.status != "ok" else ""
    return panel_section(PANEL_ID, panel_head(PANEL_ID, TITLE, QUESTION), body)


register_panel("fragility", 530, render_fragility_panel)
