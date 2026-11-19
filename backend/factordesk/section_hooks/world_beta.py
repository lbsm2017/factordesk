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
    EUROPE_WORDS,
    MIN_OVERLAP,
    PROXIES,
    WORDS,
    BetaEstimate,
    Comparison,
    Overlap,
    align_overlap,
    compare_betas,
    single_factor_beta,
)
from factordesk.data.audit import AuditFinding, audit_prices
from factordesk.data.prices import (
    IncrementalPriceProvider,
    PriceDataError,
    PriceHistory,
    PriceProvider,
    collapse_duplicate_dates,
)
from factordesk.data.throttle import RATE_LIMIT_MESSAGE, is_rate_limited
from factordesk.report.base import SampleInfo, Status
from factordesk.report.sections.world_beta import (
    BetaFit,
    ProxyBeta,
    WorldBetaLabel,
    WorldBetaSection,
)
from factordesk.section_hooks.context import SectionContext, WorldBenchmarkInput

logger = logging.getLogger(__name__)

UNAVAILABLE_REASON = "The world fund's prices could not be fetched."
"""Reason of the failed section when ACWI cannot be fetched and no cache exists."""
EUROPE_UNAVAILABLE_REASON = "The Europe fund's prices could not be fetched."
"""Reason of the Europe block when IEUR cannot be fetched and no cache exists."""
_UNAVAILABLE = {"world": UNAVAILABLE_REASON, "europe": EUROPE_UNAVAILABLE_REASON}
_WORDS: dict[str, dict[Comparison, str]] = {"world": WORDS, "europe": EUROPE_WORDS}
_NOUN = {"world": "world", "europe": "Europe"}

_LABELS: list[WorldBetaLabel] = ["L-DESC", "L-WORLD-PROXY", "L-WORLD-ASYNC"]


def load_world_benchmark(
    provider: PriceProvider, ticker: str = BENCHMARK_TICKER
) -> WorldBenchmarkInput:
    """The history of ``ticker`` (ACWI unless another proxy is named) or why it is not available.

    Never raises. A provider with ``fetch_incremental`` (``YFinanceProvider``) serves the cache
    and downloads only the days after its last date; any other provider is asked for the whole
    history.
    """
    try:
        if isinstance(provider, IncrementalPriceProvider):
            refresh = provider.fetch_incremental(ticker)
            return WorldBenchmarkInput(history=refresh.history, note=refresh.note)
        return WorldBenchmarkInput(history=provider.fetch(ticker))
    except PriceDataError as exc:
        return WorldBenchmarkInput(history=None, unavailable_reason=str(exc))
    except Exception as exc:  # network, rate limit or anything else: the report still builds
        logger.warning("%s could not be fetched", ticker, exc_info=True)
        reason = RATE_LIMIT_MESSAGE if is_rate_limited(exc) else f"{type(exc).__name__}: {exc}"
        return WorldBenchmarkInput(history=None, unavailable_reason=reason)


def _fit(e: BetaEstimate) -> BetaFit:
    return BetaFit(
        beta=e.beta,
        se=e.se_hac,
        ci_low=e.ci_low,
        ci_high=e.ci_high,
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
    """The section, or ``None`` when the feature did not run (no benchmark input).

    The same computation runs for every proxy of ``PROXIES``. The ACWI result fills the flat
    fields and decides the status of the section; the Europe result is the nested ``europe``
    block with its own status, so one proxy failing never changes the other.
    """
    inputs = {"world": ctx.inputs.world_benchmark, "europe": ctx.inputs.europe_benchmark}
    if inputs["world"] is None:
        return None
    blocks: dict[str, ProxyBeta | None] = {}
    for key, ticker, label in PROXIES:
        bench = inputs[key]
        blocks[key] = None if bench is None else _proxy_block(ctx, bench, key, ticker, label)
    acwi, europe = blocks["world"], blocks["europe"]
    assert acwi is not None
    return WorldBetaSection.model_validate(
        {
            "status": acwi.status,
            "reason": acwi.reason,
            "sample": _overlap_info(
                ctx.sample_info(None),
                acwi.n_days,
                None if acwi.start is None else pd.Timestamp(acwi.start),
                None if acwi.end is None else pd.Timestamp(acwi.end),
            ),
            "proxy": acwi.proxy,
            "hac_lags": acwi.hac_lags,
            "n_sample": ctx.sample.n,
            "n_not_in_benchmark": acwi.n_not_in_benchmark,
            "acwi_first_date": acwi.first_date,
            "acwi_last_date": acwi.last_date,
            "acwi_note": acwi.note,
            "audit_warnings": acwi.audit_warnings,
            "world": acwi.benchmark,
            "us_market": acwi.us_market,
            "comparison": acwi.comparison,
            "comparison_text": acwi.comparison_text,
            "europe": europe,
            "labels": _LABELS,
        }
    )


def _proxy_block(
    ctx: SectionContext, bench: WorldBenchmarkInput, key: str, ticker: str, label: str
) -> ProxyBeta:
    """The quick beta of the stock against one proxy fund (``key`` is its entry of ``PROXIES``).

    Never raises for data reasons: the block carries the status and the reason.
    """
    history = None if bench.history is None else _unique(bench.history)
    first: date | None = None
    last: date | None = None
    if history is not None:
        frame_index = pd.DatetimeIndex(history.frame.index)
        first, last = frame_index[0].date(), frame_index[-1].date()

    def block(
        status: Status,
        reason: str | None,
        *,
        n: int = 0,
        start: pd.Timestamp | None = None,
        end: pd.Timestamp | None = None,
        n_missing: int | None = None,
        warnings: list[str] | None = None,
        fit: BetaFit | None = None,
        us: BetaFit | None = None,
        comparison: tuple[str, str] | None = None,
        lags: int | None = None,
    ) -> ProxyBeta:
        return ProxyBeta.model_validate(
            {
                "status": status,
                "reason": reason,
                "label": label,
                "proxy": ticker,
                "n_days": n,
                "start": None if start is None else start.date(),
                "end": None if end is None else end.date(),
                "hac_lags": lags,
                "n_not_in_benchmark": ctx.sample.n if n_missing is None else n_missing,
                "first_date": first,
                "last_date": last,
                "note": bench.note if bench.history is not None else bench.unavailable_reason,
                "audit_warnings": warnings or [],
                "benchmark": fit,
                "us_market": us,
                "comparison": None if comparison is None else comparison[0],
                "comparison_text": None if comparison is None else comparison[1],
            }
        )

    noun = _NOUN[key]
    if history is None:
        return block("failed", _UNAVAILABLE[key])
    try:
        audit = audit_prices(history.frame, duplicate_dates=history.duplicate_dates)
        warnings = [f.message for f in audit.findings if f.severity == "warn"]
        errors = [f for f in audit.findings if f.severity == "error"]
        overlap = align_overlap(ctx.sample, pd.DatetimeIndex(ctx.history.frame.index), history)
        start = overlap.dates[0] if overlap.n else None
        end = overlap.dates[-1] if overlap.n else None
        used = _days_used(pd.DatetimeIndex(history.frame.index), overlap)
        inside = [e for e in errors if _touches(e, used)]
        if inside:
            codes = ", ".join(sorted({e.code for e in inside}))
            return block(
                "failed",
                f"The {ticker} price history has errors on days this section uses "
                f"({codes}), so its returns cannot be trusted and the {noun} beta is not "
                "computed. The section is left out until the history is corrected.",
                warnings=warnings,
            )
        outside = [e for e in errors if e not in inside]
        if outside and used is not None:
            codes = ", ".join(sorted({e.code for e in outside}))
            warnings.append(
                f"The {ticker} price audit found errors ({codes}) on dates outside the "
                f"days used here ({used[0]} to {used[1]}), so they do not affect this beta."
            )
        elif outside:
            codes = ", ".join(sorted({e.code for e in outside}))
            warnings.append(
                f"The {ticker} price audit found errors ({codes}); no day is common "
                "to the analysis sample and the fund, so none of them affects a beta."
            )
        if overlap.n < MIN_OVERLAP:
            return block(
                "insufficient_data",
                f"Only {overlap.n} days are common to the analysis sample and "
                f"{ticker}; at least {MIN_OVERLAP} (one trading year) are needed.",
                n=overlap.n,
                start=start,
                end=end,
                n_missing=overlap.n_without_benchmark,
                warnings=warnings,
            )
        fit = single_factor_beta(overlap.stock_xret, overlap.bench_xret, ticker)
        us = single_factor_beta(overlap.stock_xret, overlap.mkt_rf)
        return block(
            "ok",
            None,
            n=overlap.n,
            start=start,
            end=end,
            n_missing=overlap.n_without_benchmark,
            warnings=warnings,
            fit=_fit(fit),
            us=_fit(us),
            comparison=compare_betas(fit, us, _WORDS[key]),
            lags=hac_lags(overlap.n),
        )
    except DegenerateInputError as exc:
        return block("failed", f"The {noun} beta could not be computed: {exc.reason}.")
    except Exception as exc:  # any other error: the block says so, the report still builds
        logger.warning("%s beta failed", ticker, exc_info=True)
        return block("failed", f"The {noun} beta could not be computed ({exc}).")


def _days_used(bench_index: pd.DatetimeIndex, overlap: Overlap) -> tuple[date, date] | None:
    """First and last ACWI price date the overlap's returns rest on, or ``None`` if no day.

    The first return of the overlap needs the ACWI price of the row before its date.
    """
    if not overlap.n:
        return None
    first = int(bench_index.get_indexer(pd.DatetimeIndex([overlap.dates[0]]))[0])
    start = bench_index[max(first - 1, 0)]
    return start.date(), overlap.dates[-1].date()


def _touches(finding: AuditFinding, used: tuple[date, date] | None) -> bool:
    """True when an audit error can change a return used by the beta.

    An error with no date cannot be placed, so it counts. A calendar-year drift is stamped on the
    last row of its year and spoils that whole year.
    """
    if not finding.dates:
        return True
    if used is None:
        return False
    first, last = used
    if finding.code == "calendar_year_drift":
        return any(first.year <= d.year <= last.year for d in finding.dates)
    return any(first <= d <= last for d in finding.dates)


def _unique(history: PriceHistory) -> PriceHistory:
    """Collapse repeated dates the provider returned (first bar kept) and record them (D29)."""
    frame, repeated = collapse_duplicate_dates(history.frame)
    if not repeated:
        return history
    recorded = tuple(sorted(set(history.duplicate_dates) | set(repeated)))
    return dataclasses.replace(history, frame=frame, duplicate_dates=recorded)
