"""Pipeline hook of the PerformanceSection section (schema v3 contract; sixth optional section).

The statistics are in ``analytics/performance.py``; this hook turns the analysis sample into the
section model. It reads only the context (``ctx.sample``, ``ctx.history``, ``ctx.sample_info``),
never changes a core section and never raises for data reasons: a sample the statistics cannot use
gives a section with ``status = "failed"`` and a reason; a very short sample gives
``insufficient_data``.
"""

from __future__ import annotations

import logging

import pandas as pd

from factordesk.analytics.performance import (
    MIN_OBS,
    DrawdownEpisode,
    InsufficientObservations,
    PerformanceResult,
    performance_stats,
)
from factordesk.report.sections.performance import (
    DrawdownEpisodeInfo,
    DrawdownSeries,
    PerformanceDrawdown,
    PerformancePeriods,
    PerformanceReturns,
    PerformanceSection,
    PerformanceSharpe,
)
from factordesk.section_hooks.context import SectionContext

logger = logging.getLogger(__name__)

INSUFFICIENT = (
    "Insufficient data: performance needs at least {min_obs} daily observations; this sample "
    "has {n}."
)
FAILED = "Performance could not be computed because of a problem in the return data."


def _episode(e: DrawdownEpisode) -> DrawdownEpisodeInfo:
    return DrawdownEpisodeInfo(
        depth=e.depth,
        peak_date=e.peak_date,
        trough_date=e.trough_date,
        recovery_date=e.recovery_date,
        days_peak_to_trough=e.days_peak_to_trough,
        days_trough_to_recovery=e.days_trough_to_recovery,
    )


SERIES_DECIMALS = 4


def _series(result: PerformanceResult) -> DrawdownSeries:
    """Dates and drawdown values (4 decimals; ``+ 0.0`` turns a rounded ``-0.0`` into ``0.0``)."""
    return DrawdownSeries(
        dates=list(result.drawdown_dates),
        values=[round(v, SERIES_DECIMALS) + 0.0 for v in result.drawdown_values],
    )


def _section(result: PerformanceResult, ctx: SectionContext) -> PerformanceSection:
    lo, hi = result.sharpe_ci95 if result.sharpe_ci95 is not None else (None, None)
    worst = result.episodes[0] if result.episodes else None
    return PerformanceSection(
        status="ok",
        reason=None,
        sample=ctx.sample_info(None),
        periods=PerformancePeriods(
            n_days=result.n, start=result.start, end=result.end, years=result.years
        ),
        returns=PerformanceReturns(
            cagr=result.cagr,
            cumulative_return=result.cumulative_return,
            mean_return_annual=result.mean_return_annual,
        ),
        volatility_annual=result.volatility_annual,
        sharpe=PerformanceSharpe(
            ratio_annual=result.sharpe_annual,
            ratio_daily=result.sharpe_daily,
            mean_excess_annual=result.mean_excess_annual,
            sharpe_se_iid=result.sharpe_se_iid,
            ci95_low=lo,
            ci95_high=hi,
            ci_includes_zero=None if lo is None or hi is None else bool(lo <= 0.0 <= hi),
        ),
        drawdown=PerformanceDrawdown(
            max_drawdown=result.max_drawdown,
            peak_date=None if worst is None else worst.peak_date,
            trough_date=None if worst is None else worst.trough_date,
            recovery_date=None if worst is None else worst.recovery_date,
            days_peak_to_trough=None if worst is None else worst.days_peak_to_trough,
            days_trough_to_recovery=None if worst is None else worst.days_trough_to_recovery,
            episodes=[_episode(e) for e in result.episodes],
            series=_series(result),
        ),
    )


def _not_ok(ctx: SectionContext, status: str, reason: str) -> PerformanceSection:
    return PerformanceSection.model_validate(
        {
            "status": status,
            "reason": reason,
            "sample": ctx.sample_info(None),
            "periods": None,
            "returns": None,
            "volatility_annual": None,
            "sharpe": None,
            "drawdown": None,
        }
    )


def _origin(ctx: SectionContext) -> pd.Timestamp | None:
    """The price date before the first analysed return: where the return path starts at 1.0."""
    index = pd.DatetimeIndex(ctx.history.frame.index)
    first = pd.Timestamp(ctx.sample.ret.index[0])
    pos = int(index.searchsorted(first))
    return pd.Timestamp(index[pos - 1]) if pos > 0 else None


def build_performance(ctx: SectionContext) -> PerformanceSection | None:
    """The performance section of the analysis sample (never ``None`` once built)."""
    sample = ctx.sample
    try:
        result = performance_stats(sample.ret, sample.rf, origin=_origin(ctx))
        return _section(result, ctx)
    except InsufficientObservations as exc:
        return _not_ok(ctx, "insufficient_data", INSUFFICIENT.format(min_obs=MIN_OBS, n=exc.n))
    except Exception:  # a statistic must never block the report
        logger.exception("performance raised; the performance section is marked failed")
        return _not_ok(ctx, "failed", FAILED)
