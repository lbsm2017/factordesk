"""Tail risk section: value at risk (VaR) and expected shortfall (CVaR) of the analysed series.

Definitions and conventions: ``analytics/tail_risk.py`` and the spec section "E7: VaR and CVaR"
(``docs/specs/next-stage-track-record-and-portfolio.md``). ``TailRiskSection`` is the optional
``FactorReport.tail_risk`` field (``None`` when the feature did not run). It is additive and does
not change the schema version (contract SC5).

The top-level figures are at the series' own frequency: one day for a daily series, one month for
a monthly one, with no scaling to another horizon. ``by_horizon`` (optional) adds the same
figures for each horizon the series supports: daily, monthly and quarterly for a daily series,
monthly and quarterly for a monthly one. A coarser horizon is built from the finer returns by
compounding complete calendar months or quarters that do not overlap; nothing is scaled with the
square root of time. A loss is a positive fraction of value (0.02 is a 2%
loss); a negative figure means even the tail was a gain. A figure that is not available has
``value = None`` and says why in ``reason``. Bands are percentile bootstrap bands with the level
in ``series.band_level``.

The section has no footnote keys of its own. Its ``sample`` is the factor-regression sample of the
report; the series behind the figures is described by ``series.n_obs``: the subject's returns on
exactly the dates of that sample, so ``series.n_obs`` equals ``sample.n``.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from factordesk.report.base import FrozenModel, SectionModel, SectionSpec

TailMethod = Literal["historical", "gaussian", "cornish_fisher"]
TailMeasure = Literal["var", "cvar"]
TailBandQuality = Literal["validated", "approximate"]


class TailBand(FrozenModel):
    """A percentile bootstrap band around one figure."""

    low: float = Field(description="Lower end of the band, as a fraction of value.")
    high: float = Field(description="Upper end of the band, as a fraction of value.")
    resamples: int = Field(
        ge=1, description="Bootstrap resamples behind the band (those inside the valid range)."
    )


class TailFigureInfo(FrozenModel):
    """One VaR or CVaR figure: one method, one measure, one confidence level."""

    method: TailMethod
    measure: TailMeasure
    level: float = Field(
        description="Confidence level: 0.99 for VaR and 0.975 for CVaR; monthly series also 0.95."
    )
    value: float | None = Field(
        description="Loss as a positive fraction of value; None when the figure is not available "
        "(then reason says why)."
    )
    reason: str | None = Field(
        description="Why value is None; or, with indicative = true, the caveat on the value."
    )
    indicative: bool = Field(
        description="True for a Cornish-Fisher figure whose expansion is not monotone on "
        "[-3.5, 3.5], or that differs from the historical figure by more than 50% of it: the "
        "value is shown, as an indication only (reason says which)."
    )
    band: TailBand | None = Field(description="Bootstrap band; None when none is shown.")
    band_quality: TailBandQuality | None = Field(
        description="validated: the band covered about its nominal level on simulated normal "
        "data. approximate: it covered less (it tends to be narrow). None without a band."
    )
    band_reason: str | None = Field(
        description="Why band is None although value is not; None otherwise."
    )
    tail_count: int | None = Field(
        ge=0,
        description="Observations with a loss at or beyond this method's VaR at this level; None "
        "when the figure is not available.",
    )
    expected_tail_obs: float = Field(
        ge=0.0, description="Observations expected in the tail: n x (1 - level)."
    )


class TailSeriesStats(FrozenModel):
    """The series behind the figures and the bootstrap settings."""

    n_obs: int = Field(ge=1, description="Returns used (days, months or quarters).")
    mean: float = Field(description="Sample mean of the periodic simple returns.")
    std: float = Field(description="Sample standard deviation (ddof 1) of the returns.")
    skewness: float = Field(description="Moment estimator of skewness.")
    excess_kurtosis: float = Field(description="Moment estimator of excess kurtosis.")
    bootstrap: Literal["iid", "stationary"] = Field(
        description="iid for monthly and quarterly series; stationary block bootstrap for daily "
        "series."
    )
    mean_block_length: float | None = Field(
        description="Mean block length of the stationary bootstrap; None for the iid bootstrap."
    )
    n_resamples: int = Field(ge=1, description="Bootstrap resamples drawn.")
    band_level: float = Field(description="Coverage of the bands (0.9 is a 90% band).")
    seed: int = Field(description="Random seed of the bootstrap.")


TailHorizonName = Literal["daily", "monthly", "quarterly"]


class TailHorizon(FrozenModel):
    """The tail risk figures of one horizon (one day, one month or one quarter).

    Statuses: ``ok``; ``insufficient_data`` (fewer than 12 complete periods); ``failed`` (the
    periodic returns have no usable tail statistic). A horizon that is not ok holds no part.
    """

    horizon: TailHorizonName
    status: Literal["ok", "insufficient_data", "failed"]
    reason: str | None = Field(description="Why the horizon has no figures; None when ok.")
    series: TailSeriesStats | None
    figures: list[TailFigureInfo] | None = Field(
        description="Same order as TailRiskSection.figures; the 95% rows exist for monthly and "
        "quarterly horizons only."
    )

    @model_validator(mode="after")
    def _parts_present_exactly_when_ok(self) -> TailHorizon:
        """An ``ok`` horizon holds every part and no reason; any other holds a reason only."""
        parts = (self.series, self.figures)
        if (self.status == "ok") != all(part is not None for part in parts):
            raise ValueError("every part is present exactly when status is 'ok'")
        if self.status == "ok" and self.reason is not None:
            raise ValueError("reason must be None when status is 'ok'")
        if self.status != "ok" and (self.reason is None or any(p is not None for p in parts)):
            raise ValueError("a horizon that is not ok holds a reason and no part")
        return self


class TailRiskSection(SectionModel):
    """VaR and CVaR by three methods, with bootstrap bands.

    Statuses: ``ok``; ``insufficient_data`` (fewer than 12 returns); ``failed`` (the series has no
    usable tail statistic, for example it is constant).
    """

    frequency: Literal["daily", "monthly"] | None = Field(
        description="Frequency of the series; the figures are at this horizon."
    )
    series: TailSeriesStats | None
    figures: list[TailFigureInfo] | None = Field(
        description="Every figure: levels in the order VaR 99%, CVaR 97.5%, then (monthly only) "
        "VaR 95% and CVaR 95%; within a level historical, Gaussian, Cornish-Fisher."
    )
    by_horizon: list[TailHorizon] | None = Field(
        default=None,
        exclude_if=lambda value: value is None,
        description="The figures of every horizon the series supports, in the order daily, "
        "monthly, quarterly (daily only for a daily series). The horizon that equals `frequency` "
        "repeats the top-level figures exactly. Absent (not null) for a section that is not ok, or "
        "in reports made before this field existed.",
    )

    @model_validator(mode="after")
    def _parts_present_exactly_when_ok(self) -> TailRiskSection:
        """An ``ok`` section holds every part; any other status holds none."""
        parts = (self.frequency, self.series, self.figures)
        if (self.status == "ok") != all(part is not None for part in parts):
            raise ValueError("every part is present exactly when status is 'ok'")
        if self.status != "ok" and any(part is not None for part in parts):
            raise ValueError("a section that is not ok holds no part")
        return self


TAIL_RISK_SECTION = SectionSpec(report_field="tail_risk", model=TailRiskSection)
