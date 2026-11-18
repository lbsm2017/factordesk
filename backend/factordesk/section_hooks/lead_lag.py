"""Pipeline hook of the LeadLagSection section (docs/specs/lead-lag-betas.md; contract SC2.2).

Owned by the feature branch. Contract placeholder: the feature is not built yet, so the hook
returns ``None`` and the report field stays ``null``. The statistics belong in
``analytics/lead_lag.py``; this hook only turns the context into the section model.
"""

from __future__ import annotations

from factordesk.report.sections.lead_lag import LeadLagSection
from factordesk.section_hooks.context import SectionContext


def build_lead_lag(ctx: SectionContext) -> LeadLagSection | None:
    """Build the section from the finished core report, or ``None`` when it is not computed."""
    return None
