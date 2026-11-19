"""Pipeline hook of the ResidualAnalysis section.

Spec: docs/methodology-residual-analysis.md; contract SC2.5.

The statistics are computed in ``analytics/residual.py`` and ``analytics/residual_stability.py``;
this hook turns the context into the section model (R7): sample metadata, labels, captions (R7.9),
caveats (R8.5) and warnings. It never changes a core section and never raises for data reasons: a
failed regression gives a section with ``status = "failed"`` (R8.4), a short span gives a
point-in-time part with ``insufficient_data`` (R3.6).
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date

import numpy as np
from numpy.typing import NDArray

from factordesk.analytics.residual import (
    ARCH_LAGS,
    LB_LAGS,
    DiagnosticsSummary,
    GapStats,
    ResidualResult,
    ResidualSummary,
    residual_analysis,
)
from factordesk.analytics.residual_stability import (
    WINDOW,
    NonOverlappingResult,
    RollingAlphaSeries,
    SplitHalfResult,
    YearRow,
    calendar_years,
    non_overlapping_alpha,
    rolling_alpha,
    split_half_alpha,
)
from factordesk.analytics.rolling import RollingBetas, rolling_betas
from factordesk.analytics.subject import SubjectKind
from factordesk.report.base import ReportWarning, SampleInfo, Status
from factordesk.report.sections.residual_alpha import (
    QUESTION,
    AlphaWindow,
    NonOverlappingAlpha,
    ResidualAlphaDiagnostics,
    ResidualAnalysis,
    ResidualBasis,
    ResidualChart,
    ResidualGap,
    ResidualLabelKey,
    ResidualStats,
    ResidualYear,
    ResidualYears,
    RollingResidualAlpha,
    SplitHalfAlpha,
)
from factordesk.section_hooks.context import SectionContext

FloatArray = NDArray[np.float64]

REGRESSION_FAILED = "Residual analysis is unavailable because the regression could not be computed."
"""R8.4 state text; also the section reason."""
EXACT_FIT_REASON = (
    "The regression fits the data exactly, so the residuals are rounding noise and residual "
    "analysis means nothing."
)
NESTED_REGRESSION_FAILED = "Full-sample regression unavailable"
"""R3.6: reason of every nested statistic when the M3 regression is not ok."""
ROLLING_SIG_DIGITS = 6
"""Per-stamp series (the chart lines and the rolling alpha) keep 6 significant digits in the
report (M14, D31); the statistics of the section keep full precision."""

LABELS_IN_SAMPLE: list[ResidualLabelKey] = ["L-DESC", "L-INSAMPLE", "L-VINTAGE"]
LABELS_PIT: list[ResidualLabelKey] = ["L-DESC-PIT", "L-PIT", "L-VINTAGE"]
LABELS_CHART: list[ResidualLabelKey] = ["L-INSAMPLE", "L-PIT", "L-HEDGE", "L-VINTAGE"]
LABELS_GAP: list[ResidualLabelKey] = ["L-INSAMPLE", "L-PIT", "L-VINTAGE"]
LABELS_ROLLING: list[ResidualLabelKey] = ["L-DESC", "L-BAND", "L-OVERLAP"]
LABELS_TABLE: list[ResidualLabelKey] = ["L-DESC", "L-INSAMPLE", "L-VINTAGE"]
LABELS_YEARS: list[ResidualLabelKey] = ["L-DESC", "L-INSAMPLE", "L-PIT"]
LABELS_DIAG_IN_SAMPLE: list[ResidualLabelKey] = ["L-DESC", "L-INSAMPLE"]
LABELS_DIAG_PIT: list[ResidualLabelKey] = ["L-DESC-PIT", "L-PIT"]


def caveats(window: int, kind: SubjectKind = "ticker") -> list[str]:
    """R8.5, in display order, ``{W}`` filled. The first line says "the stock's return" for a
    ticker and "the return" for a portfolio or an uploaded record."""
    what = "the stock's return" if kind == "ticker" else "the return"
    return [
        f"You see {what} after removing what its five factor exposures explain. It includes alpha.",
        "In-sample: betas are fitted on this same period, so the in-sample line always drifts by "
        "the regression alpha. A line ending above zero is not evidence of skill; check the "
        "t-statistic.",
        f"Point-in-time: each day uses betas from the previous {window} trading days only. It "
        "removes hindsight in the betas, but it uses the same days, so it cannot rule out luck.",
        "The lines compound a paper long-short hedge, rebalanced daily, before trading costs, "
        "financing and borrowing fees.",
        "Past residual return does not predict future residual return.",
    ]


def _round_sig(x: float) -> float:
    return float(f"{x:.{ROLLING_SIG_DIGITS}g}")


def _series(values: FloatArray) -> list[float | None]:
    return [None if np.isnan(v) else _round_sig(float(v)) for v in values]


def _line(values: Sequence[float | None]) -> list[float | None]:
    """A chart line at 6 significant digits (relative error at most 5e-6), gaps kept."""
    return [None if v is None else _round_sig(v) for v in values]


def _span_info(
    base: SampleInfo, dates: Sequence[date], first: int, window: int | None, last: int | None = None
) -> SampleInfo:
    """``SampleInfo`` of rows ``first .. last`` (0-based, inclusive) of ``S``."""
    end_idx = len(dates) - 1 if last is None else last
    n = max(end_idx - first + 1, 0)
    start = dates[first] if n > 0 else None
    end = dates[end_idx] if n > 0 else None
    excluded = [
        e for e in base.excluded if start is not None and end is not None and start <= e.date <= end
    ]
    return base.model_copy(
        update={
            "n": n,
            "start": start,
            "end": end,
            "window": window,
            "n_excluded": len(excluded),
            "excluded": excluded,
        }
    )


def _stats(
    s: ResidualSummary,
    basis: ResidualBasis,
    window: int | None,
    info: SampleInfo,
    labels: list[ResidualLabelKey],
    caption: str,
) -> ResidualStats:
    return ResidualStats(
        status=s.status,
        reason=s.reason,
        sample=info,
        labels=labels,
        caption=caption,
        basis=basis,
        beta_window=window,
        hac_lags=s.hac_lags,
        residual_return_annual=s.residual_return_annual,
        residual_return_se_annual=s.residual_return_se_annual,
        residual_return_ci_low_annual=s.residual_return_ci_low_annual,
        residual_return_ci_high_annual=s.residual_return_ci_high_annual,
        z=s.z,
        p=s.p,
        tag=s.tag,
        residual_vol_annual=s.residual_vol_annual,
        information_ratio=s.information_ratio,
        information_ratio_ci_low=s.information_ratio_ci_low,
        information_ratio_ci_high=s.information_ratio_ci_high,
        cumulative_return=s.cumulative_return,
        compound_growth_annual=s.compound_growth_annual,
        hit_rate=s.hit_rate,
        max_drawdown=s.max_drawdown,
        max_drawdown_peak=s.max_drawdown_peak,
        max_drawdown_trough=s.max_drawdown_trough,
        max_drawdown_recovery=s.max_drawdown_recovery,
        noise_drawdown_reference=s.noise_drawdown_reference,
        skew=s.skew,
        excess_kurtosis=s.excess_kurtosis,
        wiped_out=s.wiped_out,
    )


def _gap(
    g: GapStats, message: str | None, window: int, info: SampleInfo, caption: str
) -> ResidualGap:
    return ResidualGap(
        status=g.status,
        reason=g.reason,
        sample=info,
        labels=LABELS_GAP,
        caption=caption,
        beta_window=window,
        in_sample_same_days_annual=g.in_sample_same_days_annual,
        point_in_time_annual=g.point_in_time_annual,
        gap_annual=g.gap_annual,
        gap_se_annual=g.gap_se_annual,
        gap_z=g.gap_z,
        gap_p=g.gap_p,
        comparison_share_of_alpha=g.comparison_share_of_alpha,
        survival_ratio=g.survival_ratio,
        verdict=g.verdict,
        severity=g.severity,
        message=message,
    )


def _chart(r: ResidualResult, info: SampleInfo, caption: str) -> ResidualChart:
    ok = r.in_sample.status == "ok"
    n = len(r.dates)
    full: list[float | None] = _line(r.chart.in_sample_full) if ok else [None] * n
    pit = r.point_in_time
    return ResidualChart(
        status="ok" if ok else r.in_sample.status,
        reason=None if ok else r.in_sample.reason,
        sample=info,
        labels=LABELS_CHART,
        caption=caption,
        dates=list(r.dates),
        in_sample_full=full,
        comparison_start=r.chart.comparison_start,
        in_sample_compare=_line(r.chart.in_sample_compare),
        point_in_time_compare=_line(r.chart.point_in_time_compare),
        point_in_time_status=pit.status,
        point_in_time_reason=pit.reason,
        n_excluded_in_span=r.chart.n_excluded_in_span,
        n_uncovered=r.chart.n_uncovered,
        uncovered_from=r.chart.uncovered_from,
    )


def _diagnostics(
    d: DiagnosticsSummary, basis: ResidualBasis, info: SampleInfo
) -> ResidualAlphaDiagnostics:
    return ResidualAlphaDiagnostics(
        status=d.status,
        reason=d.reason,
        sample=info,
        labels=LABELS_DIAG_IN_SAMPLE if basis == "in_sample" else LABELS_DIAG_PIT,
        caption="Informational checks at the 5% level, not corrected for multiple testing.",
        basis=basis,
        ljung_box_lags=LB_LAGS,
        ljung_box_stat=d.ljung_box_stat,
        ljung_box_p=d.ljung_box_p,
        jarque_bera_stat=d.jarque_bera_stat,
        jarque_bera_p=d.jarque_bera_p,
        arch_lags=ARCH_LAGS,
        arch_lm_stat=d.arch_lm_stat,
        arch_lm_p=d.arch_lm_p,
        findings=list(d.findings),
    )


def _rolling_section(
    series: RollingAlphaSeries, dates: Sequence[date], info: SampleInfo
) -> RollingResidualAlpha:
    ok = series.n_stamps > 0
    none: list[float | None] = [None] * len(dates)
    return RollingResidualAlpha(
        status="ok" if ok else "insufficient_data",
        reason=None if ok else f"At least {WINDOW} trading days are needed for a rolling alpha.",
        sample=info,
        labels=LABELS_ROLLING,
        caption=(
            "Each point uses the previous 252 trading days, ending on that date; alpha and betas "
            "are both refitted in each window."
        ),
        window=WINDOW,
        hac_lags=series.hac_lags,
        n_stamps=series.n_stamps,
        dates=list(dates),
        alpha_annual=_series(series.alpha_annual) if ok else none,
        ci_low_annual=_series(series.ci_low_annual) if ok else none,
        ci_high_annual=_series(series.ci_high_annual) if ok else none,
        share_excluding_zero=series.share_excluding_zero if ok else None,
    )


def _non_overlapping(
    res: NonOverlappingResult, dates: Sequence[date], info: SampleInfo
) -> NonOverlappingAlpha:
    windows = [
        AlphaWindow(
            start=w.start,
            end=w.end,
            n=w.n,
            alpha_annual=w.alpha_annual,
            se_annual=w.se_annual,
            z=w.z,
            p=w.p,
            p_adj_bh=w.p_adj_bh,
            tag=w.tag,
        )
        for w in res.windows
    ]
    return NonOverlappingAlpha(
        status=res.status,
        reason=res.reason,
        sample=info,
        labels=LABELS_TABLE,
        caption=(
            f"Separate one-year windows counted back from {dates[-1]}. Corrected for testing "
            f"{res.family_size} windows (Benjamini-Hochberg)."
        ),
        window=WINDOW,
        family_size=res.family_size,
        n_reliable=res.n_reliable,
        windows=windows,
    )


def _split_half(res: SplitHalfResult, info: SampleInfo) -> SplitHalfAlpha:
    return SplitHalfAlpha(
        status=res.status,
        reason=res.reason,
        sample=info,
        labels=LABELS_TABLE,
        caption=(
            "One split, fixed in advance at the middle of the period. Betas are refitted in "
            "each half."
        ),
        first_start=res.first_start,
        first_end=res.first_end,
        second_start=res.second_start,
        second_end=res.second_end,
        n_first=res.n_first,
        n_second=res.n_second,
        hac_lags=res.hac_lags,
        alpha_first_annual=res.alpha_first_annual,
        alpha_first_ci_low_annual=res.alpha_first_ci_low_annual,
        alpha_first_ci_high_annual=res.alpha_first_ci_high_annual,
        alpha_second_annual=res.alpha_second_annual,
        alpha_second_ci_low_annual=res.alpha_second_ci_low_annual,
        alpha_second_ci_high_annual=res.alpha_second_ci_high_annual,
        difference_annual=res.difference_annual,
        difference_se_annual=res.difference_se_annual,
        difference_z=res.difference_z,
        difference_p=res.difference_p,
    )


def _years(rows: Sequence[YearRow], window: int, info: SampleInfo) -> ResidualYears:
    return ResidualYears(
        status="ok",
        reason=None,
        sample=info,
        labels=LABELS_YEARS,
        caption=(
            "Sum of daily residual returns within the year (not compounded). In-sample column: "
            f"betas from the whole period. Point-in-time column: betas from the previous {window} "
            "days."
        ),
        years=[
            ResidualYear(
                year=y.year,
                n=y.n,
                partial=y.partial,
                in_sample_sum=y.in_sample_sum,
                in_sample_noise_sd=y.in_sample_noise_sd,
                n_point_in_time=y.n_point_in_time,
                point_in_time_partial=y.point_in_time_partial,
                point_in_time_sum=y.point_in_time_sum,
                point_in_time_noise_sd=y.point_in_time_noise_sd,
            )
            for y in rows
        ],
    )


def _stats_caption(basis: ResidualBasis, window: int, start: date | None, end: date | None) -> str:
    if basis == "in_sample":
        return (
            "Residual return = excess return minus factor exposures, alpha included. In-sample: "
            f"betas fitted on {start} to {end}, so the residual return equals the regression "
            "alpha exactly."
        )
    head = (
        f"Residual return with each day's betas estimated from the previous {window} trading "
        "days only."
    )
    if start is None:
        return f"{head} This period has no days after the {window}-day warm-up."
    return f"{head} Covers {start} to {end}; the first {window} days are warm-up."


def _chart_caption(r: ResidualResult, window: int) -> str:
    if r.chart.comparison_start is None:
        text = (
            "Cumulative residual return, compounded daily, with betas fitted on the whole "
            "period (in-sample)."
        )
    else:
        text = (
            "Cumulative residual return, compounded daily. Both lines start at zero on "
            f"{r.chart.comparison_start} and cover the same days. In-sample uses betas fitted "
            f"on the whole period; point-in-time uses betas from the previous {window} days."
        )
    if r.chart.n_excluded_in_span:
        text += f" Skips {r.chart.n_excluded_in_span} excluded days (listed under sample details)."
    return text


def _gap_caption(start: date | None, end: date | None) -> str:
    days = (
        "Same days for both series."
        if start is None
        else f"Same days ({start} to {end}) for both series."
    )
    return (
        f"{days} Out-of-sample here refers to the betas; both series share the same days and "
        "stock-specific news."
    )


def _warnings(r: ResidualResult) -> list[ReportWarning]:
    seen: list[date] = []
    for d in r.wipeouts:
        if d not in seen:
            seen.append(d)
    return [
        ReportWarning(
            code="residual_wipeout",
            message=f"The hedged position lost all its capital on {d}; later days are not "
            "compounded.",
        )
        for d in seen
    ]


def build_section(
    r: ResidualResult, rolling_252: RollingBetas, ctx: SectionContext
) -> ResidualAnalysis:
    """The section for a computed ``ResidualResult`` (the regression is ok)."""
    w = r.window
    dates = list(r.dates)
    base = ctx.sample_info(None)
    info_s = _span_info(base, dates, 0, None)
    info_c = _span_info(base, dates, min(w, len(dates)), w)
    info_rolling = _span_info(base, dates, 0, WINDOW)
    n_windows = len(dates) // WINDOW
    info_j = _span_info(base, dates, len(dates) - n_windows * WINDOW, WINDOW)
    end = dates[-1]
    return ResidualAnalysis(
        status="ok",
        reason=None,
        sample=info_s,
        question=QUESTION,
        beta_window=w,
        in_sample=_stats(
            r.in_sample,
            "in_sample",
            None,
            info_s,
            LABELS_IN_SAMPLE,
            _stats_caption("in_sample", w, dates[0], end),
        ),
        point_in_time=_stats(
            r.point_in_time,
            "point_in_time",
            w,
            info_c,
            LABELS_PIT,
            _stats_caption("point_in_time", w, info_c.start, end),
        ),
        gap=_gap(r.gap, r.gap_message, w, info_c, _gap_caption(info_c.start, end)),
        chart=_chart(r, info_s, _chart_caption(r, w)),
        rolling_alpha=_rolling_section(rolling_alpha(rolling_252), dates, info_rolling),
        non_overlapping=_non_overlapping(non_overlapping_alpha(rolling_252, dates), dates, info_j),
        split_half=_split_half(split_half_alpha(ctx.sample), info_s),
        calendar_years=_years(calendar_years(dates, r.u, r.u_tilde), w, info_s),
        diagnostics=[
            _diagnostics(r.diagnostics_in_sample, "in_sample", info_s),
            _diagnostics(r.diagnostics_point_in_time, "point_in_time", info_c),
        ],
        caveats=caveats(w, ctx.subject.kind),
        warnings=_warnings(r),
    )


def failed_section(ctx: SectionContext, window: int) -> ResidualAnalysis:
    """R8.4: the regression could not be computed, so nothing is shown (every statistic failed)."""
    return unavailable_section(ctx, window, "failed", REGRESSION_FAILED, NESTED_REGRESSION_FAILED)


def unavailable_section(
    ctx: SectionContext, window: int, status: Status, reason: str, why: str
) -> ResidualAnalysis:
    """A section whose nested statistics all carry ``status`` and the reason ``why``."""
    info = ctx.sample_info(None)
    failed: Status = status
    summary = ResidualSummary(status=failed, reason=why, n=0)
    first, last = ctx.sample.start, ctx.sample.end
    return ResidualAnalysis(
        status=failed,
        reason=reason,
        sample=info,
        question=QUESTION,
        beta_window=window,
        in_sample=_stats(summary, "in_sample", None, info, LABELS_IN_SAMPLE, why),
        point_in_time=_stats(summary, "point_in_time", window, info, LABELS_PIT, why),
        gap=_gap(GapStats(status=failed, reason=why), None, window, info, why),
        chart=ResidualChart(
            status=failed,
            reason=why,
            sample=info,
            labels=LABELS_CHART,
            caption=why,
            dates=[],
            in_sample_full=[],
            comparison_start=None,
            in_sample_compare=[],
            point_in_time_compare=[],
            point_in_time_status=failed,
            point_in_time_reason=why,
            n_excluded_in_span=0,
            n_uncovered=0,
            uncovered_from=None,
        ),
        rolling_alpha=RollingResidualAlpha(
            status=failed,
            reason=why,
            sample=info,
            labels=LABELS_ROLLING,
            caption=why,
            window=WINDOW,
            hac_lags=0,
            n_stamps=0,
            dates=[],
            alpha_annual=[],
            ci_low_annual=[],
            ci_high_annual=[],
            share_excluding_zero=None,
        ),
        non_overlapping=NonOverlappingAlpha(
            status=failed,
            reason=why,
            sample=info,
            labels=LABELS_TABLE,
            caption=why,
            window=WINDOW,
            family_size=0,
            n_reliable=0,
            windows=[],
        ),
        split_half=_split_half(
            SplitHalfResult(
                status=failed,
                reason=why,
                first_start=first,
                first_end=first,
                second_start=last,
                second_end=last,
                n_first=0,
                n_second=0,
            ),
            info,
        ),
        calendar_years=ResidualYears(
            status=failed, reason=why, sample=info, labels=LABELS_YEARS, caption=why, years=[]
        ),
        diagnostics=[
            _diagnostics(DiagnosticsSummary(status=failed, reason=why), "in_sample", info),
            _diagnostics(DiagnosticsSummary(status=failed, reason=why), "point_in_time", info),
        ],
        caveats=caveats(window, ctx.subject.kind),
        warnings=[],
    )


def build_residual_analysis(ctx: SectionContext) -> ResidualAnalysis | None:
    """Build the section from the finished core report (always present once built)."""
    window = ctx.primary_window
    if ctx.core.regression.status != "ok":
        return failed_section(ctx, window)
    if ctx.diagnostics is None:  # the fit is exact (M3.5): the residuals are rounding noise
        return unavailable_section(
            ctx, window, "not_applicable", EXACT_FIT_REASON, EXACT_FIT_REASON
        )
    rolling_w = ctx.rolling[window] if window in ctx.rolling else rolling_betas(ctx.sample, window)
    rolling_252 = (
        ctx.rolling[WINDOW] if WINDOW in ctx.rolling else rolling_betas(ctx.sample, WINDOW)
    )
    result = residual_analysis(ctx.sample, ctx.regression, rolling_w, exact_fit=False)
    return build_section(result, rolling_252, ctx)
