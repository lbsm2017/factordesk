"""Pipeline hook of the WorldBetaSection (docs/validation/world-beta-handoff-2026-11-18.md).

``load_world_benchmark`` fetches the ACWI price history through the provider the pipeline uses
(refreshing the cache by the new days only when the provider can) and never raises: a benchmark
that cannot be fetched becomes a ``WorldBenchmarkInput`` with a reason. ``build_world_beta`` reads
the context and that input and nothing else. It returns ``None`` only when the feature did not
run (no benchmark input: factors were injected or the loader stayed offline). Otherwise it returns
a section with a status of M0.7: ``ok`` (also on a stale cache, with ``acwi_note``),
``insufficient_data``, or ``failed`` (the ACWI audit found errors, ACWI could not be fetched and
no cache exists, or any other error). It never raises for data reasons, never changes a core
section and never blocks the report (CODING_STANDARDS section 8).
"""

from __future__ import annotations

import dataclasses
import logging
from datetime import date

import pandas as pd

from factordesk.analytics.regression import hac_lags
from factordesk.analytics.sample import DegenerateInputError
from factordesk.analytics.world_beta import (
    BENCHMARK_TICKER,
    MIN_OVERLAP,
    BetaEstimate,
    align_overlap,
    compare_betas,
    single_factor_beta,
)
from factordesk.data.audit import audit_prices
from factordesk.data.prices import (
    IncrementalPriceProvider,
    PriceDataError,
    PriceHistory,
    PriceProvider,
    collapse_duplicate_dates,
)
from factordesk.data.throttle import RATE_LIMIT_MESSAGE, is_rate_limited
from factordesk.report.base import SampleInfo, Status
from factordesk.report.sections.world_beta import BetaFit, WorldBetaLabel, WorldBetaSection
from factordesk.section_hooks.context import SectionContext, WorldBenchmarkInput

logger = logging.getLogger(__name__)

UNAVAILABLE_REASON = "ACWI price data could not be fetched"
"""Reason of the failed section when ACWI cannot be fetched and no cache exists."""

_LABELS: list[WorldBetaLabel] = ["L-DESC", "L-WORLD-PROXY", "L-WORLD-ASYNC"]


def load_world_benchmark(provider: PriceProvider) -> WorldBenchmarkInput:
    """The ACWI history from ``provider``, or why it is not available. Never raises.

    A provider with ``fetch_incremental`` (``YFinanceProvider``) serves the cache and downloads
    only the days after its last date; any other provider is asked for the whole history.
    """
    try:
        if isinstance(provider, IncrementalPriceProvider):
            refresh = provider.fetch_incremental(BENCHMARK_TICKER)
            return WorldBenchmarkInput(history=refresh.history, note=refresh.note)
        return WorldBenchmarkInput(history=provider.fetch(BENCHMARK_TICKER))
    except PriceDataError as exc:
        return WorldBenchmarkInput(history=None, unavailable_reason=str(exc))
    except Exception as exc:  # network, rate limit or anything else: the report still builds
        logger.warning("ACWI could not be fetched", exc_info=True)
        reason = RATE_LIMIT_MESSAGE if is_rate_limited(exc) else f"{type(exc).__name__}: {exc}"
        return WorldBenchmarkInput(history=None, unavailable_reason=reason)


def _fit(e: BetaEstimate) -> BetaFit:
    return BetaFit(
        beta=e.beta,
        se_hac=e.se_hac,
        ci95_low=e.ci_low,
        ci95_high=e.ci_high,
        r2=e.r2,
        correlation=e.correlation,
        alpha_annual=e.alpha_annual,
        alpha_t=e.alpha_t,
    )


def _overlap_info(
    info: SampleInfo, n: int, start: pd.Timestamp | None, end: pd.Timestamp | None
) -> SampleInfo:
    """The analysis sample's metadata with ``n``, ``start`` and ``end`` of the common days."""
    return info.model_copy(
        update={
            "n": n,
            "start": None if start is None else start.date(),
            "end": None if end is None else end.date(),
        }
    )


def build_world_beta(ctx: SectionContext) -> WorldBetaSection | None:
    """The section, or ``None`` when the feature did not run (no benchmark input)."""
    bench = ctx.inputs.world_benchmark
    if bench is None:
        return None
    info = ctx.sample_info(None)
    history = None if bench.history is None else _unique(bench.history)
    first: date | None = None
    last: date | None = None
    if history is not None:
        frame_index = pd.DatetimeIndex(history.frame.index)
        first, last = frame_index[0].date(), frame_index[-1].date()

    def section(
        status: Status,
        reason: str | None,
        *,
        n: int = 0,
        start: pd.Timestamp | None = None,
        end: pd.Timestamp | None = None,
        n_missing: int | None = None,
        warnings: list[str] | None = None,
        world: BetaFit | None = None,
        us: BetaFit | None = None,
        comparison: tuple[str, str] | None = None,
        lags: int | None = None,
    ) -> WorldBetaSection:
        return WorldBetaSection.model_validate(
            {
                "status": status,
                "reason": reason,
                "sample": _overlap_info(info, n, start, end),
                "benchmark": BENCHMARK_TICKER,
                "hac_lags": lags,
                "n_sample": ctx.sample.n,
                "n_not_in_benchmark": ctx.sample.n if n_missing is None else n_missing,
                "acwi_first_date": first,
                "acwi_last_date": last,
                "acwi_note": bench.note if bench.history is not None else bench.unavailable_reason,
                "audit_warnings": warnings or [],
                "world": world,
                "us_market": us,
                "comparison": None if comparison is None else comparison[0],
                "comparison_text": None if comparison is None else comparison[1],
                "labels": _LABELS,
            }
        )

    if history is None:
        return section("failed", UNAVAILABLE_REASON)
    try:
        audit = audit_prices(history.frame, duplicate_dates=history.duplicate_dates)
        warnings = [f.message for f in audit.findings if f.severity == "warn"]
        errors = [f for f in audit.findings if f.severity == "error"]
        if errors:
            codes = ", ".join(sorted({f.code for f in errors}))
            return section(
                "failed",
                f"The {BENCHMARK_TICKER} price audit found errors ({codes}), so its returns "
                "cannot be trusted and the world beta is not computed.",
                warnings=warnings,
            )
        overlap = align_overlap(ctx.sample, pd.DatetimeIndex(ctx.history.frame.index), history)
        start = overlap.dates[0] if overlap.n else None
        end = overlap.dates[-1] if overlap.n else None
        if overlap.n < MIN_OVERLAP:
            return section(
                "insufficient_data",
                f"Only {overlap.n} days are common to the analysis sample and "
                f"{BENCHMARK_TICKER}; at least {MIN_OVERLAP} (one trading year) are needed.",
                n=overlap.n,
                start=start,
                end=end,
                n_missing=overlap.n_without_benchmark,
                warnings=warnings,
            )
        world = single_factor_beta(overlap.stock_xret, overlap.bench_xret)
        us = single_factor_beta(overlap.stock_xret, overlap.mkt_rf)
        return section(
            "ok",
            None,
            n=overlap.n,
            start=start,
            end=end,
            n_missing=overlap.n_without_benchmark,
            warnings=warnings,
            world=_fit(world),
            us=_fit(us),
            comparison=compare_betas(world, us),
            lags=hac_lags(overlap.n),
        )
    except DegenerateInputError as exc:
        return section("failed", f"The world beta could not be computed: {exc.reason}.")
    except Exception as exc:  # any other error: the section says so, the report still builds
        logger.warning("world beta failed", exc_info=True)
        return section("failed", f"The world beta could not be computed ({exc}).")


def _unique(history: PriceHistory) -> PriceHistory:
    """Collapse repeated dates the provider returned (first bar kept) and record them (D29)."""
    frame, repeated = collapse_duplicate_dates(history.frame)
    if not repeated:
        return history
    recorded = tuple(sorted(set(history.duplicate_dates) | set(repeated)))
    return dataclasses.replace(history, frame=frame, duplicate_dates=recorded)
