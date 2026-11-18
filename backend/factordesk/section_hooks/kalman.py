"""Pipeline hook of the KalmanBetaSeries section (docs/specs/kalman-betas.md; contract SC2.3).

Owned by the feature branch. Contract placeholder: the feature is not built yet, so the hook
returns ``None`` and the report field stays ``null``. The statistics belong in
``analytics/kalman.py``; this hook only turns the context into the section model.
"""

from __future__ import annotations

from factordesk.report.sections.kalman import KalmanBetaSeries
from factordesk.section_hooks.context import SectionContext


def build_kalman_betas(ctx: SectionContext) -> KalmanBetaSeries | None:
    """Build the section from the finished core report, or ``None`` when it is not computed."""
    return None
