"""Pipeline hook of the ResidualAnalysis section.

Spec: docs/methodology-residual-analysis.md; contract SC2.5.

Owned by the feature branch. Contract placeholder: the feature is not built yet, so the hook
returns ``None`` and the report field stays ``null``. The statistics belong in
``analytics/residual.py`` and ``analytics/residual_stability.py``; this hook only turns the
context into the section model.
"""

from __future__ import annotations

from factordesk.report.sections.residual_alpha import ResidualAnalysis
from factordesk.section_hooks.context import SectionContext


def build_residual_analysis(ctx: SectionContext) -> ResidualAnalysis | None:
    """Build the section from the finished core report, or ``None`` when it is not computed."""
    return None
