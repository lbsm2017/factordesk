"""Static HTML panel of the ``residual`` section (contract SC2.5).

Spec: ``docs/methodology-residual-analysis.md``. Owned by the feature branch, which replaces
the placeholder body. Registered at position 710 as ``residual_alpha``. Placeholder: nothing when
the section is absent; when present, the panel frame with the empty state if its status is not
``ok``.
"""

from __future__ import annotations

from factordesk.report.panel_registry import register_panel
from factordesk.report.render_html import empty_state, panel_head, panel_section
from factordesk.report.schema import FactorReport

PANEL_ID = "residual"
TITLE = "Residual return"
QUESTION = (
    "What did this stock return beyond its factor exposures, and does it hold up without hindsight?"
)


def render_residual_alpha_panel(report: FactorReport) -> str | None:
    """The panel's HTML, or ``None`` when the section was not computed."""
    section = report.residual
    if section is None:
        return None
    body = empty_state(section.reason or "") if section.status != "ok" else ""
    return panel_section(PANEL_ID, panel_head(PANEL_ID, TITLE, QUESTION), body)


register_panel("residual_alpha", 710, render_residual_alpha_panel)
