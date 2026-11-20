"""Pipeline hook of the TailRiskSection section (VaR and CVaR, next-stage spec E7).

The statistics are in ``analytics/tail_risk.py``; this hook runs them on the subject's returns at
the subject's own frequency, with the default seed, and turns the result into the section model.
Only the returns on the dates of the analysed sample are used (the rows of ``ctx.sample``, the
same rows as every other section), so the section agrees with every other section on which days
it describes and ``series.n_obs`` equals ``sample.n``. Returns inside the window that the sample
excluded (no factor row, a multi-day return, a missing price or factor) are not used. Missing
returns (``NaN`` where a level is missing) are dropped as well. The hook never raises for
data reasons: a series with fewer than 12 returns gives ``insufficient_data``; a series the
statistics refuse (constant, a return at or below -100%) gives ``failed`` with the reason.

``by_horizon`` repeats the analysis at every horizon of the subject: a daily subject gets daily,
monthly and quarterly, a monthly subject gets monthly and quarterly (no daily). The coarser
horizons use non-overlapping compounded returns of complete calendar months or quarters built from
the same sample rows (``complete_period_returns``), never a square-root-of-time scaling. The
horizon equal to the subject's frequency is the top-level result itself. A horizon with fewer than
12 complete periods, or one the statistics refuse, is listed with its status and reason.
"""

from __future__ import annotations

import logging
from typing import Literal

import pandas as pd

from factordesk.analytics.tail_risk import (
    MIN_OBS,
    FloatArray,
    TailFigure,
    TailRisk,
    complete_period_returns,
    tail_risk,
)
from factordesk.report.sections.tail_risk import (
    TailBand,
    TailFigureInfo,
    TailHorizon,
    TailRiskSection,
    TailSeriesStats,
)
from factordesk.section_hooks.context import SectionContext

logger = logging.getLogger(__name__)

INSUFFICIENT = (
    "Insufficient data: VaR and CVaR need at least {min_obs} {unit}; this series has {n}."
)
UNITS = {
    "daily": "daily returns",
    "monthly": "monthly returns",
    "quarterly": "quarterly returns",
}
HORIZONS: dict[str, tuple[Literal["daily", "monthly", "quarterly"], ...]] = {
    "daily": ("daily", "monthly", "quarterly"),
    "monthly": ("monthly", "quarterly"),
}
"""The horizons of each subject frequency, finest first."""
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


def _series(result: TailRisk) -> TailSeriesStats:
    return TailSeriesStats(
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
    )


def _horizon_ok(result: TailRisk) -> TailHorizon:
    return TailHorizon(
        horizon=result.frequency,
        status="ok",
        reason=None,
        series=_series(result),
        figures=[_figure(f) for f in result.figures],
    )


def _horizon_not_ok(
    horizon: Literal["daily", "monthly", "quarterly"],
    status: Literal["insufficient_data", "failed"],
    reason: str,
) -> TailHorizon:
    return TailHorizon(horizon=horizon, status=status, reason=reason, series=None, figures=None)


def _horizon(horizon: Literal["daily", "monthly", "quarterly"], values: FloatArray) -> TailHorizon:
    """One horizon from its periodic returns; never raises for data reasons."""
    if len(values) < MIN_OBS:
        reason = INSUFFICIENT.format(min_obs=MIN_OBS, unit=UNITS[horizon], n=len(values))
        return _horizon_not_ok(horizon, "insufficient_data", reason)
    try:
        return _horizon_ok(tail_risk(values, horizon))
    except ValueError as exc:
        logger.warning("tail risk refused the %s series: %s", horizon, exc)
        return _horizon_not_ok(horizon, "failed", f"{FAILED} ({exc})")
    except Exception:  # a statistic must never block the report
        logger.exception("tail risk raised at the %s horizon", horizon)
        return _horizon_not_ok(horizon, "failed", FAILED)


def _by_horizon(
    ctx: SectionContext,
    returns: pd.Series,
    default: TailRisk,
    frequency: Literal["daily", "monthly"],
) -> list[TailHorizon]:
    """Every horizon of the subject; the subject's own one is the default result."""
    out: list[TailHorizon] = []
    for horizon in HORIZONS[frequency]:
        if horizon == frequency:
            out.append(_horizon_ok(default))
            continue
        try:
            coarse = complete_period_returns(
                returns.index.to_numpy(dtype="datetime64[D]"),
                returns.to_numpy(dtype=float),
                ctx.subject.returns.index.to_numpy(dtype="datetime64[D]"),
                "quarterly" if horizon == "quarterly" else "monthly",
                "daily" if frequency == "daily" else "monthly",
            )
        except Exception:  # a statistic must never block the report
            logger.exception("tail risk could not build the %s returns", horizon)
            out.append(_horizon_not_ok(horizon, "failed", FAILED))
            continue
        out.append(_horizon(horizon, coarse.returns))
    return out


def _section(
    result: TailRisk,
    ctx: SectionContext,
    returns: pd.Series,
    frequency: Literal["daily", "monthly"],
) -> TailRiskSection:
    return TailRiskSection(
        status="ok",
        reason=None,
        sample=ctx.sample_info(None),
        frequency=frequency,
        series=_series(result),
        figures=[_figure(f) for f in result.figures],
        by_horizon=_by_horizon(ctx, returns, result, frequency),
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
    returns = ctx.subject.returns
    returns = returns[returns.index.isin(ctx.sample.ret.dropna().index)].dropna()
    if len(returns) < MIN_OBS:
        unit = "daily returns" if frequency == "daily" else "monthly returns"
        return _not_ok(
            ctx,
            "insufficient_data",
            INSUFFICIENT.format(min_obs=MIN_OBS, unit=unit, n=len(returns)),
        )
    try:
        result = tail_risk(returns.to_numpy(dtype=float), frequency)
        return _section(result, ctx, returns, frequency)
    except ValueError as exc:  # a constant series, a return of -100% or worse, non-finite values
        logger.warning("tail risk refused the series: %s", exc)
        return _not_ok(ctx, "failed", f"{FAILED} ({exc})")
    except Exception:  # a statistic must never block the report
        logger.exception("tail risk raised; the tail risk section is marked failed")
        return _not_ok(ctx, "failed", FAILED)
