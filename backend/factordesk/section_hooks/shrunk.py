"""Pipeline hook of the ShrunkBetas section (docs/specs/shrunk-betas.md; contract SC2.4).

Owned by the feature branch. Contract placeholder: the feature is not built yet, so the hook
returns ``None`` and the report field stays ``null``, and no portfolio file is fetched. The
statistics belong in ``analytics/shrinkage.py`` and ``analytics/shrinkage_prior.py``, the
portfolio-file parser in ``data/portfolios.py``.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime

import pandas as pd

from factordesk.report.sections.shrunk import ShrunkBetas
from factordesk.section_hooks.context import SectionContext


def build_shrunk_betas(ctx: SectionContext) -> list[ShrunkBetas] | None:
    """One section per scope (``full_sample``, ``latest_window``), or ``None`` when not computed."""
    return None


def load_shrinkage_inputs(now: datetime, *, offline: bool) -> Mapping[str, pd.DataFrame] | None:
    """The portfolio frames of the prior (SB2.2) by dataset key; ``None`` when not fetched."""
    return None
