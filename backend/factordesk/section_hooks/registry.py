"""Which optional section runs for which subject (next-stage spec, Technical design).

Each hook of the schema v3 contract gets one ``HookSpec``: the report field it fills, the hook
itself, and the subject kinds (``sources``), frequencies and factor models it supports.
``run_hooks`` calls the hooks in panel-call order and leaves the field ``None`` (the section is
hidden) when the subject is outside a hook's declaration, so a daily-only statistic never runs on
monthly data and never needs a frequency check of its own.

Declarations:

* performance: every subject, every frequency, every model.
* alpha strip: every subject, every frequency, every model (it needs the momentum factor in the
  sample and leaves its field ``None`` without it).
* world beta: daily only (ACWI and IEUR prices are daily), every model.
* tail risk (VaR and CVaR): every subject, every frequency, every model.
* portfolio backtest: portfolio subjects only (it describes the backtest behind the series).
* macro sensitivities (E4): every subject, every frequency, every model (a separate regression;
  daily funds, compounded to month-ends for a monthly subject).
* lead-lag, shrunk betas, fragility, residual alpha analysis, Kalman betas: daily and FF5 only.
  Their methods are built on trading-day windows (252-row windows, 5-day blocks, a lag of one
  trading day, an FF5 prior) and on the five factors, and are not defined for monthly data or
  another model yet. Under FF6 they are hidden; the FF5 report is unchanged.
* shrunk betas are also hidden for a portfolio: the prior is "a stock that behaves like the
  market" (Mkt-RF 1, the other betas 0) and its spread comes from portfolios of stocks, so it is
  the wrong reference for a mix of bonds, commodities and equities. The other FF5 sections
  read only the return series and stay for a portfolio.

The hooks are looked up by module attribute at call time, so a test may replace one.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass

from factordesk.analytics.sample import Frequency
from factordesk.analytics.subject import FREQUENCIES, SUBJECT_KINDS, SubjectKind
from factordesk.section_hooks import alpha_strip as alpha_strip_hook
from factordesk.section_hooks import fragility as fragility_hook
from factordesk.section_hooks import kalman as kalman_hook
from factordesk.section_hooks import lead_lag as lead_lag_hook
from factordesk.section_hooks import macro as macro_hook
from factordesk.section_hooks import performance as performance_hook
from factordesk.section_hooks import portfolio_backtest as portfolio_backtest_hook
from factordesk.section_hooks import residual_alpha as residual_alpha_hook
from factordesk.section_hooks import shrunk as shrunk_hook
from factordesk.section_hooks import tail_risk as tail_risk_hook
from factordesk.section_hooks import world_beta as world_beta_hook
from factordesk.section_hooks.context import FACTOR_MODELS, FactorModel, SectionContext

logger = logging.getLogger(__name__)

SLOW_SECTION_SECONDS = 1.0
"""A section that takes longer than this is named in the log."""

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
NOT_PORTFOLIO: frozenset[SubjectKind] = frozenset({"ticker", "upload"})
PORTFOLIO: frozenset[SubjectKind] = frozenset({"portfolio"})
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
        NOT_PORTFOLIO,
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
    HookSpec(
        "alpha_strip",
        lambda ctx: alpha_strip_hook.build_alpha_strip(ctx),
        ALL_SOURCES,
        ALL_FREQUENCIES,
        ALL_MODELS,
    ),
    HookSpec(
        "portfolio_backtest",
        lambda ctx: portfolio_backtest_hook.build_portfolio_backtest(ctx),
        PORTFOLIO,
        ALL_FREQUENCIES,
        ALL_MODELS,
    ),
    HookSpec(
        "macro",
        lambda ctx: macro_hook.build_macro(ctx),
        ALL_SOURCES,
        ALL_FREQUENCIES,
        ALL_MODELS,
    ),
)
"""Every optional section, in the order the hooks run (the order of the contract's pipeline)."""


def run_hooks(ctx: SectionContext, hooks: tuple[HookSpec, ...] = HOOKS) -> dict[str, object | None]:
    """Each hook's section by report field; ``None`` for a hook that does not apply.

    Logs one INFO line with the number of sections built and the seconds they took, and one more
    line for every section that took longer than ``SLOW_SECTION_SECONDS``.
    """
    kind, frequency = ctx.subject.kind, ctx.subject.frequency
    out: dict[str, object | None] = {}
    slow: list[tuple[str, float]] = []
    started = time.perf_counter()
    for spec in hooks:
        if not spec.applies(kind, frequency, ctx.model):
            out[spec.field] = None
            continue
        began = time.perf_counter()
        out[spec.field] = spec.build(ctx)
        took = time.perf_counter() - began
        if took > SLOW_SECTION_SECONDS:
            slow.append((spec.field, took))
    built = sum(1 for value in out.values() if value is not None)
    logger.info("Sections built: %d in %.1f s", built, time.perf_counter() - started)
    for name, took in slow:
        logger.info("Slow section %s: %.1f s", name, took)
    return out
