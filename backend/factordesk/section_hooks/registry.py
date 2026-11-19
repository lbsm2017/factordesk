"""Which optional section runs for which subject (next-stage spec, Technical design).

Each hook of the schema v3 contract gets one ``HookSpec``: the report field it fills, the hook
itself, and the subject kinds (``sources``), frequencies and factor models it supports.
``run_hooks`` calls the hooks in panel-call order and leaves the field ``None`` (the section is
hidden) when the subject is outside a hook's declaration, so a daily-only statistic never runs on
monthly data and never needs a frequency check of its own.

Declarations:

* performance: every subject, every frequency, every model.
* world beta: daily only (ACWI and IEUR prices are daily), every model.
* tail risk (VaR and CVaR): every subject, every frequency, every model.
* lead-lag, shrunk betas, fragility, residual alpha analysis, Kalman betas: daily and FF5 only.
  Their methods are built on trading-day windows (252-row windows, 5-day blocks, a lag of one
  trading day, an FF5 prior) and are not defined for monthly data or another model yet.

The hooks are looked up by module attribute at call time, so a test may replace one.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from factordesk.analytics.sample import Frequency
from factordesk.analytics.subject import FREQUENCIES, SUBJECT_KINDS, SubjectKind
from factordesk.section_hooks import fragility as fragility_hook
from factordesk.section_hooks import kalman as kalman_hook
from factordesk.section_hooks import lead_lag as lead_lag_hook
from factordesk.section_hooks import performance as performance_hook
from factordesk.section_hooks import residual_alpha as residual_alpha_hook
from factordesk.section_hooks import shrunk as shrunk_hook
from factordesk.section_hooks import tail_risk as tail_risk_hook
from factordesk.section_hooks import world_beta as world_beta_hook
from factordesk.section_hooks.context import FACTOR_MODELS, FactorModel, SectionContext

Hook = Callable[[SectionContext], object | None]


@dataclass(frozen=True)
class HookSpec:
    """One optional section: its report field, its hook and where it applies."""

    field: str
    """The ``FactorReport`` field the hook fills."""
    build: Hook
    sources: frozenset[SubjectKind]
    frequencies: frozenset[Frequency]
    models: frozenset[FactorModel]

    def applies(self, kind: SubjectKind, frequency: Frequency, model: FactorModel) -> bool:
        """True when the hook supports this subject kind, frequency and model."""
        return kind in self.sources and frequency in self.frequencies and model in self.models


ALL_SOURCES: frozenset[SubjectKind] = frozenset(SUBJECT_KINDS)
ALL_FREQUENCIES: frozenset[Frequency] = frozenset(FREQUENCIES)
DAILY: frozenset[Frequency] = frozenset({"daily"})
ALL_MODELS: frozenset[FactorModel] = frozenset(FACTOR_MODELS)
FF5_ONLY: frozenset[FactorModel] = frozenset({"ff5"})

HOOKS: tuple[HookSpec, ...] = (
    HookSpec(
        "performance",
        lambda ctx: performance_hook.build_performance(ctx),
        ALL_SOURCES,
        ALL_FREQUENCIES,
        ALL_MODELS,
    ),
    HookSpec(
        "lead_lag", lambda ctx: lead_lag_hook.build_lead_lag(ctx), ALL_SOURCES, DAILY, FF5_ONLY
    ),
    HookSpec(
        "shrunk_betas",
        lambda ctx: shrunk_hook.build_shrunk_betas(ctx),
        ALL_SOURCES,
        DAILY,
        FF5_ONLY,
    ),
    HookSpec(
        "fragility",
        lambda ctx: fragility_hook.build_fragility(ctx),
        ALL_SOURCES,
        DAILY,
        FF5_ONLY,
    ),
    HookSpec(
        "world_beta",
        lambda ctx: world_beta_hook.build_world_beta(ctx),
        ALL_SOURCES,
        DAILY,
        ALL_MODELS,
    ),
    HookSpec(
        "residual",
        lambda ctx: residual_alpha_hook.build_residual_analysis(ctx),
        ALL_SOURCES,
        DAILY,
        FF5_ONLY,
    ),
    HookSpec(
        "kalman_betas",
        lambda ctx: kalman_hook.build_kalman_betas(ctx),
        ALL_SOURCES,
        DAILY,
        FF5_ONLY,
    ),
    HookSpec(
        "tail_risk",
        lambda ctx: tail_risk_hook.build_tail_risk(ctx),
        ALL_SOURCES,
        ALL_FREQUENCIES,
        ALL_MODELS,
    ),
)
"""Every optional section, in the order the hooks run (the order of the contract's pipeline)."""


def run_hooks(ctx: SectionContext, hooks: tuple[HookSpec, ...] = HOOKS) -> dict[str, object | None]:
    """Each hook's section by report field; ``None`` for a hook that does not apply."""
    kind, frequency = ctx.subject.kind, ctx.subject.frequency
    return {
        spec.field: spec.build(ctx) if spec.applies(kind, frequency, ctx.model) else None
        for spec in hooks
    }
