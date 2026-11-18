"""Residual (alpha) analysis section.

Spec: ``docs/methodology-residual-analysis.md`` (R7 schema, R8 panel), oracle
``docs/test-oracle-residual-analysis.md``; contract SC2.5.

``ResidualAnalysis`` is the optional ``FactorReport.residual`` field (``None`` when the feature did
not run). It holds the residual return of the analysed ticker twice, once with in-sample betas and
once with point-in-time betas, a same-days gap with its verdict, the cumulative chart series,
stability tables and residual diagnostics. R7.7's ``ResidualDiagnostics`` is named
``ResidualAlphaDiagnostics`` here because ``schema.ResidualDiagnostics`` (M3.5) exists (contract
SC6 item 4). The statistic models are listed in ``RESIDUAL_ALPHA_SECTION.statistic_models`` and the
four label keys of R7.1 in its ``label_text``.

Proposals for ``docs/methodology.md`` (the owner folds them in; contract SC6 item 11): the list
P1-P12 of ``docs/methodology-residual-analysis.md`` R9.2, plus (P13) the owner's wording decision of
2026-11-18, which this section applies: user text says "holds up out-of-sample" where the
specification said "survives", so the verdict copy of R4.8 for ``survives_not_significant`` and
``survives`` differs from the specification table (the codes do not change).
"""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import Field, model_validator

from factordesk.report.base import (
    FrozenModel,
    ReportWarning,
    SectionModel,
    SectionSpec,
    Severity,
    StatisticModel,
    Status,
    Tag,
)

ResidualBasis = Literal["in_sample", "point_in_time"]
GapVerdict = Literal[
    "no_reliable_alpha",
    "point_in_time_only",
    "concentrated_in_warmup",
    "reversed",
    "mostly_disappears",
    "survives_not_significant",
    "survives",
]
ResidualLabelKey = Literal[
    "L-DESC",
    "L-BAND",
    "L-OVERLAP",
    "L-VINTAGE",
    "L-INSAMPLE",
    "L-PIT",
    "L-DESC-PIT",
    "L-HEDGE",
]
"""Footnote keys the residual statistics may carry: the standard ones they use and their own."""

RESIDUAL_LABEL_TEXT: dict[str, str] = {
    "L-INSAMPLE": "In-sample: betas are fitted on this same period.",
    "L-PIT": "Point-in-time: each day uses betas estimated only from earlier days.",
    "L-DESC-PIT": "Descriptive and point-in-time, not predictive.",
    "L-HEDGE": (
        "Compounded daily: a paper long-short hedge, rebalanced daily, before trading costs, "
        "financing and borrowing fees."
    ),
}
"""R7.1: texts of the four keys this section adds."""

QUESTION = (
    "What did this stock return beyond its factor exposures, and does it hold up without hindsight?"
)
"""R8.1 subtitle."""


class _ResidualStatistic(StatisticModel):
    """A statistic of this section: its footnote keys may include the section's own."""

    labels: list[ResidualLabelKey]  # type: ignore[assignment]  # pyright: ignore[reportIncompatibleVariableOverride]


# ----------------------------------------------------------------------------- R7.3 statistics
class ResidualStats(_ResidualStatistic):
    """Summary of one residual series (R3). In-sample: span S. Point-in-time: span S_c."""

    basis: ResidualBasis
    beta_window: int | None = Field(description="None for in_sample; W for point_in_time.")
    hac_lags: int | None = Field(description="In-sample: L(n) of M3; point-in-time: L(m_c).")
    residual_return_annual: float | None = Field(description="Decimal per year, A x mean.")
    residual_return_se_annual: float | None
    residual_return_ci_low_annual: float | None
    residual_return_ci_high_annual: float | None
    z: float | None
    p: float | None = Field(description="Two-sided, normal reference.")
    tag: Tag | None
    residual_vol_annual: float | None
    information_ratio: float | None = Field(description="Per square root of a year.")
    information_ratio_ci_low: float | None = Field(description="Approximate (R3.3).")
    information_ratio_ci_high: float | None
    cumulative_return: float | None = Field(description="Compounded over the span (R2).")
    compound_growth_annual: float | None = Field(description="Q^(A/m) - 1.")
    hit_rate: float | None
    max_drawdown: float | None
    max_drawdown_peak: date | None = Field(description="None: the start of the span, or no fall.")
    max_drawdown_trough: date | None
    max_drawdown_recovery: date | None = Field(description="None: not recovered, or no fall.")
    noise_drawdown_reference: float | None
    skew: float | None
    excess_kurtosis: float | None
    wiped_out: bool = Field(description="R2.6: a daily residual of -100% or worse.")

    @model_validator(mode="after")
    def _basis_and_numbers(self) -> ResidualStats:
        """Window only for point-in-time; an ok statistic has its headline numbers."""
        if self.basis == "in_sample" and self.beta_window is not None:
            raise ValueError("an in-sample statistic has no beta window")
        if self.basis == "point_in_time" and self.beta_window is None:
            raise ValueError("a point-in-time statistic names its beta window")
        if self.status == "ok":
            required = (
                self.hac_lags,
                self.residual_return_annual,
                self.residual_return_se_annual,
                self.z,
                self.p,
                self.tag,
                self.residual_vol_annual,
                self.cumulative_return,
                self.hit_rate,
                self.max_drawdown,
            )
            if any(v is None for v in required):
                raise ValueError("an ok residual statistic must carry its headline numbers")
        elif self.wiped_out:
            raise ValueError("only an ok statistic can be wiped out")
        return self


# ----------------------------------------------------------------------------- R7.4 chart
class ResidualChart(_ResidualStatistic):
    """Cumulative (compounded) residual lines on the dates of S (R2.3)."""

    dates: list[date]
    in_sample_full: list[float | None]
    comparison_start: date | None = Field(description="Date of row W (anchor); None if PIT not ok.")
    in_sample_compare: list[float | None]
    point_in_time_compare: list[float | None]
    point_in_time_status: Status
    point_in_time_reason: str | None
    n_excluded_in_span: int = Field(ge=0)
    n_uncovered: int = Field(ge=0)
    uncovered_from: date | None

    @model_validator(mode="after")
    def _lists_align(self) -> ResidualChart:
        """R7.4 validators."""
        n = len(self.dates)
        for name in ("in_sample_full", "in_sample_compare", "point_in_time_compare"):
            if len(getattr(self, name)) != n:
                raise ValueError(f"{name} must have the length of dates")
        if (self.point_in_time_status == "ok") != (self.point_in_time_reason is None):
            raise ValueError("point_in_time_reason must be None exactly when its status is ok")
        if (self.n_uncovered == 0) != (self.uncovered_from is None):
            raise ValueError("uncovered_from is set exactly when n_uncovered is positive")
        if self.status == "ok" and any(v is None for v in self.in_sample_full):
            raise ValueError("an ok chart has no gap in the full in-sample line")
        if self.point_in_time_status != "ok":
            both = (*self.in_sample_compare, *self.point_in_time_compare)
            if self.comparison_start is not None or any(v is not None for v in both):
                raise ValueError("comparison lines are empty unless the point-in-time part is ok")
            return self
        if self.comparison_start is None or self.comparison_start not in self.dates:
            raise ValueError("comparison_start must be one of the dates")
        anchor = self.dates.index(self.comparison_start)
        for line in (self.in_sample_compare, self.point_in_time_compare):
            if any(v is not None for v in line[:anchor]) or line[anchor] != 0.0:
                raise ValueError("comparison lines are None before the anchor and 0.0 at it")
            if any(v is None for v in line[anchor + 1 :]):
                raise ValueError("comparison lines have a value after the anchor")
        return self


# ----------------------------------------------------------------------------- R7.5 gap
class ResidualGap(_ResidualStatistic):
    """Same-days comparison of in-sample and point-in-time residual returns on S_c (R4.7)."""

    beta_window: int
    in_sample_same_days_annual: float | None
    point_in_time_annual: float | None
    gap_annual: float | None
    gap_se_annual: float | None = Field(description="Approximate (R4.7).")
    gap_z: float | None
    gap_p: float | None
    comparison_share_of_alpha: float | None = Field(description="q; None if alpha_ann is 0.")
    survival_ratio: float | None = Field(description="s; None if the same-days return is 0.")
    verdict: GapVerdict | None = Field(description="None exactly when status is not ok.")
    severity: Severity | None
    message: str | None = Field(description="The R4.8 copy, filled.")

    @model_validator(mode="after")
    def _verdict_matches_status(self) -> ResidualGap:
        present = (self.verdict, self.severity, self.message)
        if (self.status == "ok") != all(v is not None for v in present):
            raise ValueError("verdict, severity and message are present exactly when ok")
        if self.status != "ok" and any(v is not None for v in present):
            raise ValueError("a not-ok gap has no verdict")
        return self


# ----------------------------------------------------------------------------- R7.6 stability
class RollingResidualAlpha(_ResidualStatistic):
    """Trailing 252-row alpha from M4 (R5.1). Lists align with dates; None in warm-up."""

    window: int
    hac_lags: int
    n_stamps: int
    dates: list[date]
    alpha_annual: list[float | None]
    ci_low_annual: list[float | None]
    ci_high_annual: list[float | None]
    share_excluding_zero: float | None = Field(description="Descriptive, not a test (R5.1).")

    @model_validator(mode="after")
    def _lists_align(self) -> RollingResidualAlpha:
        n = len(self.dates)
        for line in (self.alpha_annual, self.ci_low_annual, self.ci_high_annual):
            if len(line) != n:
                raise ValueError("series must have the length of dates")
        return self


class AlphaWindow(FrozenModel):
    """One disjoint one-year window of family FR1."""

    start: date
    end: date
    n: int
    alpha_annual: float | None
    se_annual: float | None
    z: float | None
    p: float | None
    p_adj_bh: float | None
    tag: Tag | None


class NonOverlappingAlpha(_ResidualStatistic):
    """Family FR1 (R5.2): disjoint 252-row windows tiled from the end of S."""

    window: int
    family_size: int
    n_reliable: int
    windows: list[AlphaWindow] = Field(description="Most recent first.")

    @model_validator(mode="after")
    def _family(self) -> NonOverlappingAlpha:
        if self.family_size != len(self.windows) or self.n_reliable > self.family_size:
            raise ValueError("family_size must equal the number of windows")
        return self


class SplitHalfAlpha(_ResidualStatistic):
    """One prespecified split at the middle of S (R5.3)."""

    first_start: date
    first_end: date
    second_start: date
    second_end: date
    n_first: int
    n_second: int
    hac_lags: int | None
    alpha_first_annual: float | None
    alpha_first_ci_low_annual: float | None
    alpha_first_ci_high_annual: float | None
    alpha_second_annual: float | None
    alpha_second_ci_low_annual: float | None
    alpha_second_ci_high_annual: float | None
    difference_annual: float | None
    difference_se_annual: float | None
    difference_z: float | None
    difference_p: float | None


class ResidualYear(FrozenModel):
    """One calendar year of residual sums."""

    year: int
    n: int
    partial: bool = Field(description="n < 200.")
    in_sample_sum: float
    in_sample_noise_sd: float
    n_point_in_time: int
    point_in_time_partial: bool
    point_in_time_sum: float | None = Field(description="None if no point-in-time rows.")
    point_in_time_noise_sd: float | None


class ResidualYears(_ResidualStatistic):
    """Calendar-year residual sums (R5.4). Arithmetic within-year sums, no tests."""

    years: list[ResidualYear] = Field(description="Ascending; empty unless status is ok.")


# ----------------------------------------------------------------------------- R7.7 diagnostics
class ResidualAlphaDiagnostics(_ResidualStatistic):
    """Ljung-Box, Jarque-Bera and ARCH checks of one residual series (R6)."""

    basis: ResidualBasis
    ljung_box_lags: int
    ljung_box_stat: float | None
    ljung_box_p: float | None
    jarque_bera_stat: float | None
    jarque_bera_p: float | None
    arch_lags: int
    arch_lm_stat: float | None
    arch_lm_p: float | None
    findings: list[str] = Field(description="One plain sentence per test (R6); empty if not ok.")


# ----------------------------------------------------------------------------- R7.8 container
class ResidualAnalysis(SectionModel):
    """Residual return with in-sample and point-in-time betas, gap, stability (R0.1).

    ``status`` is ``ok`` when the M3 regression is ok and ``failed`` otherwise (R8.4); the nested
    statistics have their own statuses (point-in-time ``insufficient_data`` for a short span).
    """

    question: str = Field(description="R8.1 subtitle.")
    beta_window: int = Field(description="W, the report's beta window.")
    in_sample: ResidualStats
    point_in_time: ResidualStats
    gap: ResidualGap
    chart: ResidualChart
    rolling_alpha: RollingResidualAlpha
    non_overlapping: NonOverlappingAlpha
    split_half: SplitHalfAlpha
    calendar_years: ResidualYears
    diagnostics: list[ResidualAlphaDiagnostics] = Field(description="[in_sample, point_in_time].")
    caveats: list[str] = Field(description="R8.5, in display order.")
    warnings: list[ReportWarning]


RESIDUAL_ALPHA_SECTION = SectionSpec(
    report_field="residual",
    model=ResidualAnalysis,
    statistic_models=(
        ResidualStats,
        ResidualChart,
        ResidualGap,
        RollingResidualAlpha,
        NonOverlappingAlpha,
        SplitHalfAlpha,
        ResidualYears,
        ResidualAlphaDiagnostics,
    ),
    label_text=RESIDUAL_LABEL_TEXT,
)
