"""Pipeline hook of the TailRiskSection section (VaR and CVaR, next-stage spec E7).

The statistics are in ``analytics/tail_risk.py``; this hook runs them on the subject's returns at
the subject's own frequency, with the default seed, and turns the result into the section model.
Missing returns (``NaN`` where a level is missing) are dropped first. The hook never raises for
data reasons: a series with fewer than 12 returns gives ``insufficient_data``; a series the
statistics refuse (constant, a return at or below -100%) gives ``failed`` with the reason.
"""

from __future__ import annotations

import logging

from factordesk.analytics.tail_risk import MIN_OBS, TailFigure, TailRisk, tail_risk
from factordesk.report.sections.tail_risk import (
    TailBand,
    TailFigureInfo,
    TailRiskSection,
    TailSeriesStats,
)
from factordesk.section_hooks.context import SectionContext

logger = logging.getLogger(__name__)

INSUFFICIENT = (
    "Insufficient data: VaR and CVaR need at least {min_obs} {unit}; this series has {n}."
)
FAILED = "VaR and CVaR could not be computed because of a problem in the return data."


def _figure(f: TailFigure) -> TailFigureInfo:
    return TailFigureInfo(
        method=f.method,
        measure=f.measure,
        level=f.level,
        value=f.value,
        reason=f.reason,
        indicative=f.indicative,
        band=None
        if f.band is None
        else TailBand(low=f.band.low, high=f.band.high, resamples=f.band.resamples),
        band_quality=f.band_quality,
        band_reason=f.band_reason,
        tail_count=f.tail_count,
        expected_tail_obs=f.expected_tail_obs,
    )


def _section(result: TailRisk, ctx: SectionContext) -> TailRiskSection:
    return TailRiskSection(
        status="ok",
        reason=None,
        sample=ctx.sample_info(None),
        frequency=result.frequency,
        series=TailSeriesStats(
            n_obs=result.n_obs,
            mean=result.mean,
            std=result.std,
            skewness=result.skewness,
            excess_kurtosis=result.excess_kurtosis,
            bootstrap=result.bootstrap,
            mean_block_length=result.mean_block_length,
            n_resamples=result.n_resamples,
            band_level=result.band_level,
            seed=result.seed,
        ),
        figures=[_figure(f) for f in result.figures],
    )


def _not_ok(ctx: SectionContext, status: str, reason: str) -> TailRiskSection:
    return TailRiskSection.model_validate(
        {
            "status": status,
            "reason": reason,
            "sample": ctx.sample_info(None),
            "frequency": None,
            "series": None,
            "figures": None,
        }
    )


def build_tail_risk(ctx: SectionContext) -> TailRiskSection | None:
    """The tail risk section of the subject's returns (never ``None`` once built)."""
    frequency = ctx.subject.frequency
    returns = ctx.subject.returns.dropna()
    if len(returns) < MIN_OBS:
        unit = "daily returns" if frequency == "daily" else "monthly returns"
        return _not_ok(
            ctx,
            "insufficient_data",
            INSUFFICIENT.format(min_obs=MIN_OBS, unit=unit, n=len(returns)),
        )
    try:
        return _section(tail_risk(returns.to_numpy(dtype=float), frequency), ctx)
    except ValueError as exc:  # a constant series, a return of -100% or worse, non-finite values
        logger.warning("tail risk refused the series: %s", exc)
        return _not_ok(ctx, "failed", f"{FAILED} ({exc})")
    except Exception:  # a statistic must never block the report
        logger.exception("tail risk raised; the tail risk section is marked failed")
        return _not_ok(ctx, "failed", FAILED)
