"""Alpha strip section: alpha under CAPM, FF3, FF5 and FF6 on the same rows (E1, E9a).

Definitions: ``analytics/model_comparison.py``. ``AlphaStrip`` is the optional
``FactorReport.alpha_strip`` field. It is left out of the JSON when ``None`` (not written as
``null``), so a report built without the momentum factor is byte-identical to one written before
the section existed.

Each row is one model, fitted on the same rows: the annualised alpha, its Newey-West HAC
t-statistic and p-value, R² and adjusted R². The rows are in a fixed order, by number of factors;
the order is not a ranking and nothing marks a "best" model (E9a). ``n_dropped`` counts the sample
rows the strip leaves out because a model lacks a value there (a missing momentum value).

``model`` is the factor model of the report (FF5 or FF6) and ``model_note`` the fixed note that
says what that model assumes and what it leaves out (E9a). ``caption`` is the fixed caption under
the strip. The section has no footnote keys of its own and no nested ``StatisticModel``.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from factordesk.report.base import FrozenModel, SectionModel, SectionSpec

StripModel = Literal["capm", "ff3", "ff5", "ff6"]
ReportModel = Literal["ff5", "ff6"]

CAPTION = "A higher R² does not make a model more correct. Alpha depends on the model."
"""Fixed caption under the strip (E9a)."""

STRIP_INTRO = (
    "Alpha of four factor models fitted on the same rows. The models are listed by number of "
    "factors; the order is not a ranking."
)

MODEL_NOTES: dict[ReportModel, str] = {
    "ff5": (
        "FF5 assumes the excess return moved linearly with five factors (the market, size, "
        "value, profitability and investment) with exposures that stayed the same over the "
        "window. It leaves out momentum, industry, currency and every other factor not in the "
        "list: a return that co-moved with a left-out factor shows up in alpha or in the "
        "residual."
    ),
    "ff6": (
        "FF6 is FF5 plus momentum (recent winners minus recent losers). It assumes the excess "
        "return moved linearly with these six factors, with exposures that stayed the same over "
        "the window. It leaves out industry, currency and every other factor not in the list: a "
        "return that co-moved with a left-out factor shows up in alpha or in the residual."
    ),
}
"""Fixed model note of each report model (E9a): what it assumes and what it leaves out."""


class AlphaStripRow(FrozenModel):
    """One model's alpha on the common rows. Not ranked against the other rows."""

    model: StripModel
    label: str = Field(description='Display label: "CAPM", "FF3", "FF5" or "FF6".')
    factors: list[str] = Field(description="Display names of the model's factors, in order.")
    alpha_annual: float = Field(description="Intercept times P (252, or subject.periods).")
    alpha_se_annual: float = Field(ge=0.0, description="HAC standard error of alpha_annual.")
    alpha_t: float = Field(description="HAC t-statistic of the intercept (not annualised).")
    alpha_p: float = Field(
        ge=0.0,
        le=1.0,
        description="Two-sided p-value of alpha_t: normal reference for daily subjects, "
        "Student-t with n - k degrees of freedom for monthly subjects.",
    )
    r2: float = Field(description="R squared of the model on the common rows.")
    adj_r2: float = Field(description="Adjusted R squared of the model on the common rows.")


class AlphaStrip(SectionModel):
    """The alpha strip: one row per model, all on the same rows, in a fixed order."""

    model: ReportModel = Field(description="Factor model of the report.")
    caption: str = Field(description="Fixed caption under the strip.")
    intro: str = Field(description="What the strip shows, in one sentence.")
    model_note: str = Field(description="What the report's model assumes and leaves out.")
    n_obs: int = Field(ge=0, description="Common rows every model is fitted on.")
    n_dropped: int = Field(
        ge=0, description="Sample rows left out because a model lacks a value there."
    )
    hac_lags: int = Field(ge=0, description="Newey-West lag of every fit.")
    t_reference: Literal["normal", "student_t"] | None = Field(
        description="Reference distribution of the p-values; None when not computed."
    )
    rows: list[AlphaStripRow] = Field(description="CAPM, FF3, FF5, FF6, in that order.")

    @model_validator(mode="after")
    def _rows_match_status(self) -> AlphaStrip:
        if self.status == "ok" and not self.rows:
            raise ValueError("an ok alpha strip needs its rows")
        if self.status != "ok" and self.rows:
            raise ValueError("a not-ok alpha strip carries no rows")
        return self


ALPHA_STRIP_SECTION = SectionSpec(report_field="alpha_strip", model=AlphaStrip)
