"""Static HTML panel of the ``kalman_betas`` section (contract SC2.3).

Spec: ``docs/specs/kalman-betas.md``. Owned by the feature branch, which replaces the placeholder
body. Registered at position 810 as ``kalman``. Placeholder: nothing when the section is
absent; when present, the panel frame with the empty state if its status is not ``ok``.
"""

from __future__ import annotations

from factordesk.report.panel_registry import register_panel
from factordesk.report.render_html import empty_state, panel_head, panel_section
from factordesk.report.schema import FactorReport

PANEL_ID = "kalman"
TITLE = "Kalman-filter betas"
QUESTION = (
    "How did the exposures move, using only data up to each date?"
)


def render_kalman_panel(report: FactorReport) -> str | None:
    """The panel's HTML, or ``None`` when the section was not computed."""
    section = report.kalman_betas
    if section is None:
        return None
    body = empty_state(section.reason or "") if section.status != "ok" else ""
    return panel_section(PANEL_ID, panel_head(PANEL_ID, TITLE, QUESTION), body)


register_panel("kalman", 810, render_kalman_panel)
