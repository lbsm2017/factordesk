"""Static HTML panel of the ``shrunk_betas`` section (contract SC2.4).

Spec: ``docs/specs/shrunk-betas.md``. Owned by the feature branch, which replaces the placeholder
body. Registered at position 520 as ``shrunk``. The field holds one section per scope.
Placeholder: nothing when the field is absent; when present, the panel frame with an empty state
for each scope whose status is not ``ok``.
"""

from __future__ import annotations

from factordesk.report.panel_registry import register_panel
from factordesk.report.render_html import empty_state, panel_head, panel_section
from factordesk.report.schema import FactorReport

PANEL_ID = "shrunk"
TITLE = "Pulled toward typical"
QUESTION = (
    "How far would a stated prior move each beta, and how much data would detect a small one?"
)


def render_shrunk_panel(report: FactorReport) -> str | None:
    """The panel's HTML, or ``None`` when the section was not computed."""
    sections = report.shrunk_betas
    if sections is None:
        return None
    body = "".join(empty_state(s.reason or "") for s in sections if s.status != "ok")
    return panel_section(PANEL_ID, panel_head(PANEL_ID, TITLE, QUESTION), body)


register_panel("shrunk", 520, render_shrunk_panel)
