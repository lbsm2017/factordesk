"""Pipeline hooks of the optional report sections (schema v3 contract, SC3.2).

One module per feature, each owned by its feature branch:

* ``fragility.py``: ``build_fragility``
* ``lead_lag.py``: ``build_lead_lag``
* ``kalman.py``: ``build_kalman_betas``
* ``shrunk.py``: ``build_shrunk_betas`` and ``load_shrinkage_inputs``
* ``residual_alpha.py``: ``build_residual_analysis``

``pipeline.assemble_report`` calls every hook with one ``SectionContext``. A hook returns its
section, or ``None`` when the feature does not run. It does not raise for data reasons: it returns
the section with ``status = "failed"`` and a reason.
"""

from __future__ import annotations

from datetime import datetime

from factordesk.section_hooks.context import SectionInputs
from factordesk.section_hooks.shrunk import load_shrinkage_inputs


def load_section_inputs(now: datetime, *, offline: bool) -> SectionInputs:
    """Fetch the extra data of the sections that need some (``offline``: fetch nothing)."""
    return SectionInputs(shrinkage_portfolios=load_shrinkage_inputs(now, offline=offline))
