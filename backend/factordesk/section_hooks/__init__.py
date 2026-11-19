"""Pipeline hooks of the optional report sections (schema v3 contract, SC3.2).

One module per feature, each owned by its feature branch:

* ``fragility.py``: ``build_fragility``
* ``lead_lag.py``: ``build_lead_lag``
* ``kalman.py``: ``build_kalman_betas``
* ``shrunk.py``: ``build_shrunk_betas`` and ``load_shrinkage_inputs``
* ``residual_alpha.py``: ``build_residual_analysis``
* ``world_beta.py``: ``build_world_beta`` and ``load_world_benchmark``

``pipeline.assemble_subject_report`` calls every hook with one ``SectionContext`` through
``registry.run_hooks``, which skips a hook whose ``HookSpec`` does not cover the subject's kind,
frequency or factor model (the field stays ``None``). A hook returns its section, or ``None`` when
the feature does not run. It does not raise for data reasons: it returns the section with
``status = "failed"`` and a reason.
"""

from __future__ import annotations

from datetime import date, datetime

from factordesk.analytics.world_beta import EUROPE_TICKER
from factordesk.data.prices import PriceProvider
from factordesk.section_hooks.context import SectionInputs
from factordesk.section_hooks.shrunk import load_shrinkage_inputs
from factordesk.section_hooks.world_beta import load_world_benchmark


def load_section_inputs(
    now: datetime,
    *,
    offline: bool,
    factor_last_date: date | None = None,
    price_provider: PriceProvider | None = None,
) -> SectionInputs:
    """Fetch the extra data of the sections that need some (``offline``: fetch nothing).

    ``factor_last_date`` is the last date of the factor file: portfolio files that end before it
    count as stale, so every entry point keeps them on the factor vintage (SB10.4 question 2).
    ``price_provider`` is the provider the report uses: ACWI for the world beta comes through it
    (one cache refresh at most per run); without one the world beta does not run.
    """
    return SectionInputs(
        shrinkage_portfolios=load_shrinkage_inputs(
            now, offline=offline, factor_last_date=factor_last_date
        ),
        world_benchmark=(
            None if offline or price_provider is None else load_world_benchmark(price_provider)
        ),
        europe_benchmark=(
            None
            if offline or price_provider is None
            else load_world_benchmark(price_provider, EUROPE_TICKER)
        ),
    )
