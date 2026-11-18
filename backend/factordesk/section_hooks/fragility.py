"""Pipeline hook of the FragilitySection section (docs/specs/fragility-score.md; contract SC2.1).

Owned by the feature branch. Contract placeholder: the feature is not built yet, so the hook
returns ``None`` and the report field stays ``null``. The statistics belong in
``analytics/fragility.py``; this hook only turns the context into the section model.
"""

from __future__ import annotations

from factordesk.report.sections.fragility import FragilitySection
from factordesk.section_hooks.context import SectionContext


def build_fragility(ctx: SectionContext) -> FragilitySection | None:
    """Build the section from the finished core report, or ``None`` when it is not computed."""
    return None
