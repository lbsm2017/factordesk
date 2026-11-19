"""Historical performance section: growth, volatility, Sharpe ratio and drawdowns.

Contract: ``docs/specs/schema-v3-contract.md`` (a sixth optional section, see
``docs/validation/performance-contract-note-2026-11-18.md``); definitions in
``analytics/performance.py``. ``PerformanceSection`` is the optional ``FactorReport.performance``
field (``None`` when the feature did not run). Every number is computed over the analysed sample,
the same periods as the regression (trading days, or months when ``subject.periods`` = 12).
Annualised figures use ``P`` observations a year: 252, or ``subject.periods`` when the report
has a subject block. Decimals throughout (0.1 is 10%).

The section has no footnote keys of its own and no nested ``StatisticModel``: its parts are plain
objects answered for by the section's ``status``.
"""

from __future__ import annotations

from datetime import date

from pydantic import Field, model_validator

from factordesk.report.base import FrozenModel, SectionModel, SectionSpec


class PerformancePeriods(FrozenModel):
    """The analysed span."""

    n_days: int = Field(
        ge=0,
        description="Periods of the analysed sample (trading days, or months when "
        "subject.periods = 12).",
    )
    start: date = Field(description="First analysed date.")
    end: date = Field(description="Last analysed date.")
    years: float = Field(
        description="n_days / P, with P the observations a year (252, or subject.periods)."
    )


class PerformanceReturns(FrozenModel):
    """Growth of the subject over the window (simple total returns per period, M1.3)."""

    cagr: float = Field(
        description="Compound annual growth rate: prod(1 + r)^(P / n) - 1, with P the "
        "observations a year (252, or subject.periods)."
    )
    cumulative_return: float = Field(description="prod(1 + r) - 1 over the window.")
    mean_return_annual: float = Field(
        description="Arithmetic mean of the periodic returns times P (252, or subject.periods); "
        "ignores compounding."
    )


class PerformanceSharpe(FrozenModel):
    """Sharpe ratio of the periodic excess returns (subject return minus the factor file's RF)."""

    ratio_annual: float | None = Field(
        description="sqrt(P) x mean(excess) / sd(excess), ddof 1, with P the observations a year "
        "(252, or subject.periods); None when the excess returns do not vary (the ratio is not "
        "defined)."
    )
    ratio_daily: float | None = Field(
        description="Ratio per period, mean(excess) / sd(excess): per trading day, or per month "
        "when subject.periods = 12 (the name is kept for compatibility); None as above."
    )
    mean_excess_annual: float = Field(
        description="P x mean of the periodic excess returns (P = 252, or subject.periods)."
    )
    sharpe_se_iid: float | None = Field(
        description="Approximate standard error of the annual ratio, sqrt(P) x sqrt((1 + "
        "ratio_daily^2 / 2) / n) (Lo 2002), P = 252 or subject.periods. Assumes independent, "
        "identically distributed returns."
    )
    ci95_low: float | None = Field(description="ratio_annual - 1.96 x sharpe_se_iid.")
    ci95_high: float | None = Field(description="ratio_annual + 1.96 x sharpe_se_iid.")
    ci_includes_zero: bool | None = Field(
        description="True when the 95% interval contains 0; None when the ratio is not defined."
    )


class DrawdownEpisodeInfo(FrozenModel):
    """One fall of the compounded return path from a running peak, and its recovery."""

    depth: float = Field(description="Trough value / peak value - 1; negative.")
    peak_date: date
    trough_date: date
    recovery_date: date | None = Field(
        description="First date after the trough where the path regains the peak; None when it "
        "has not."
    )
    days_peak_to_trough: int = Field(
        ge=1,
        description="Periods from peak to trough (trading days, or months when "
        "subject.periods = 12).",
    )
    days_trough_to_recovery: int | None = Field(
        description="Periods from trough to recovery (trading days, or months when "
        "subject.periods = 12); None when not recovered."
    )


class DrawdownSeries(FrozenModel):
    """The fall from the running peak at every date of the compounded return path, for a chart."""

    dates: list[date] = Field(
        description="The path origin (the price date before the first analysed return), then "
        "each analysed date."
    )
    values: list[float] = Field(
        description="Value / running peak - 1 on each date, rounded to 4 decimals; 0.0 at a new "
        "high, never positive. Same length as dates."
    )

    @model_validator(mode="after")
    def _same_length(self) -> DrawdownSeries:
        if len(self.dates) != len(self.values):
            raise ValueError("dates and values must have the same length")
        return self


class PerformanceDrawdown(FrozenModel):
    """Maximum drawdown and the deepest episodes."""

    max_drawdown: float = Field(
        le=0.0, ge=-1.0, description="Deepest fall from a running peak; 0 when the path never fell."
    )
    peak_date: date | None = Field(description="None when there was no drawdown.")
    trough_date: date | None
    recovery_date: date | None = Field(description="None when not recovered or no drawdown.")
    days_peak_to_trough: int | None = Field(
        description="Periods from peak to trough (trading days, or months when "
        "subject.periods = 12); None when there was no drawdown."
    )
    days_trough_to_recovery: int | None = Field(
        description="Periods from trough to recovery (trading days, or months when "
        "subject.periods = 12); None when not recovered or no drawdown."
    )
    episodes: list[DrawdownEpisodeInfo] = Field(
        description="Up to five distinct, non-overlapping episodes, deepest first; the first "
        "equals the maximum drawdown. Empty when there was no drawdown."
    )
    series: DrawdownSeries = Field(
        description="Drawdown at each analysed date (trading days, or month-ends when "
        "subject.periods = 12)."
    )


class PerformanceSection(SectionModel):
    """Historical return, volatility, Sharpe ratio and maximum drawdown of the analysed subject.

    Descriptive and in-sample: it says what happened over the window, not what will happen.
    Statuses: ``ok``; ``insufficient_data`` (fewer than 60 observations); ``failed``.
    """

    periods: PerformancePeriods | None
    returns: PerformanceReturns | None
    volatility_annual: float | None = Field(
        description="sqrt(P) x sample sd (ddof 1) of the periodic simple returns, with P the "
        "observations a year (252, or subject.periods)."
    )
    sharpe: PerformanceSharpe | None
    drawdown: PerformanceDrawdown | None

    @model_validator(mode="after")
    def _parts_present_exactly_when_ok(self) -> PerformanceSection:
        """An ``ok`` section holds every part; any other status holds none."""
        parts = (self.periods, self.returns, self.volatility_annual, self.sharpe, self.drawdown)
        if (self.status == "ok") != all(part is not None for part in parts):
            raise ValueError("every part is present exactly when status is 'ok'")
        if self.status != "ok" and any(part is not None for part in parts):
            raise ValueError("a section that is not ok holds no part")
        return self


PERFORMANCE_SECTION = SectionSpec(report_field="performance", model=PerformanceSection)
