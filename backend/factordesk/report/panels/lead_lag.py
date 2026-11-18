"""Static HTML panel of the ``lead_lag`` section (contract SC2.2).

Spec: ``docs/specs/lead-lag-betas.md``. Owned by the feature branch, which replaces the placeholder
body. Registered at position 510 as ``lead_lag``. Placeholder: nothing when the section is
absent; when present, the panel frame with the empty state if its status is not ``ok``.
"""

from __future__ import annotations

from factordesk.report.panel_registry import register_panel
from factordesk.report.render_html import empty_state, panel_head, panel_section
from factordesk.report.schema import FactorReport

PANEL_ID = "lead-lag"
TITLE = "Timing-adjusted betas (lead-lag)"
QUESTION = "Does part of the exposure show up on the factors' previous or next day?"


def render_lead_lag_panel(report: FactorReport) -> str | None:
    """The panel's HTML, or ``None`` when the section was not computed."""
    section = report.lead_lag
    if section is None:
        return None
    body = empty_state(section.reason or "") if section.status != "ok" else ""
    return panel_section(PANEL_ID, panel_head(PANEL_ID, TITLE, QUESTION), body)


register_panel("lead_lag", 510, render_lead_lag_panel)
