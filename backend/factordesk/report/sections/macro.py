"""Macro sensitivities section: a separate regression on market, rates, credit, commodity,
inflation and dollar factors (epic E4; definitions in ``analytics/macro.py``).

``MacroSection`` is the optional ``FactorReport.macro`` field. It is left out of the JSON when
``None`` (not written as ``null``), so a report built without it is byte-identical to one written
before the section existed. It is additive and does not change the schema version (contract SC5).

One row per factor with the raw beta, its Newey-West HAC standard error, t-statistic, p-value
(normal reference for daily subjects, Student-t for monthly ones), the reliable/noise tag of the
headline betas, and the variance inflation factor. The dollar row of a daily subject is the sum of
the same-day and previous-day betas, with the standard error of the sum. R² and adjusted R² are
those of the whole regression. ``correlation`` is the factor correlation matrix (for the
details). ``legs`` lists each fund behind a factor with its first price date; the window starts at
the latest of those dates or the subject's start, whichever is later.

The dollar index may be unavailable (FRED not reachable): the section then runs without the
dollar row and ``usd_note`` says so. ``model_note`` is the fixed note under the section.
"""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import Field, model_validator

from factordesk.report.base import FrozenModel, SectionModel, SectionSpec, Tag

MacroCode = Literal["mkt_rf", "term", "def", "comm", "infl", "usd"]

MODEL_NOTE = (
    "Separate regression. Raw betas: correlated factors share explanatory power. "
    "Not the headline alpha."
)
"""Fixed note under the section."""
USD_UNAVAILABLE = "dollar index unavailable"
"""Shown in place of the dollar row when the FRED download failed and no copy exists."""


class MacroRow(FrozenModel):
    """One factor of the macro regression."""

    code: MacroCode
    name: str = Field(description='Display name: "Mkt-RF", "TERM", "DEF", "COMM", "INFL", "USD".')
    label: str = Field(
        description="Plain label: Market, Rates, Credit, Commodities, Inflation, US dollar."
    )
    definition: str = Field(description='How the factor is built, for example "IEF minus RF".')
    note: str | None = Field(description="Caveat on the factor, for example the DEF label.")
    beta: float = Field(description="Raw beta (the summed same-day and lag beta for the dollar).")
    se: float = Field(ge=0.0, description="Newey-West HAC standard error of beta.")
    t: float = Field(description="HAC t-statistic of beta.")
    p: float = Field(ge=0.0, le=1.0, description="Two-sided p-value of t.")
    ci_low: float = Field(description="Lower end of the 95% interval, beta - q * se.")
    ci_high: float = Field(description="Upper end of the 95% interval, beta + q * se.")
    tag: Tag = Field(
        description="Reliable when the Benjamini-Hochberg rule of the headline betas "
        "rejects zero across the factors of this regression."
    )
    vif: float = Field(ge=1.0, description="Variance inflation factor among the factors.")
    beta_same_day: float | None = Field(
        description="Dollar row of a daily subject: the same-day part of the summed beta."
    )
    beta_lag: float | None = Field(
        description="Dollar row of a daily subject: the previous-day part of the summed beta."
    )


class MacroLeg(FrozenModel):
    """One fund behind a factor, with its first price date."""

    ticker: str
    role: str = Field(description='What it feeds, for example "TERM = IEF minus RF".')
    first_date: date | None = Field(description="First price date; None when not fetched.")


class MacroSection(SectionModel):
    """The macro sensitivities: one row per factor, one regression."""

    model_note: str = Field(description="Fixed note: separate regression, raw betas, not alpha.")
    n_obs: int = Field(ge=0, description="Rows of the regression.")
    n_sample: int = Field(ge=0, description="Rows of the analysis sample before the funds.")
    frequency: Literal["daily", "monthly"]
    hac_lags: int = Field(ge=0, description="Newey-West lag of the fit.")
    t_reference: Literal["normal", "student_t"] | None = Field(
        description="Reference distribution of the p-values; None when not computed."
    )
    r2: float | None = Field(description="R squared of the regression.")
    adj_r2: float | None = Field(description="Adjusted R squared of the regression.")
    rows: list[MacroRow] = Field(
        description="Market, rates, credit, commodities, inflation, dollar."
    )
    correlation_codes: list[MacroCode] = Field(
        description="Factors of the correlation matrix, in row and column order."
    )
    correlation: list[list[float]] = Field(description="Correlation matrix of the factors.")
    legs: list[MacroLeg] = Field(description="The funds behind the factors, with first dates.")
    window_limited_by: str | None = Field(
        description="The fund whose first date starts the window, when it is later than the "
        "subject's own start; None otherwise."
    )
    usd_included: bool = Field(description="False when the dollar index was unavailable.")
    usd_note: str | None = Field(
        description="Why the dollar row is missing, or a note on the dollar series."
    )
    usd_lag_note: str | None = Field(
        description="Explains the summed dollar beta of a daily subject; None for monthly."
    )

    @model_validator(mode="after")
    def _rows_match_status(self) -> MacroSection:
        if self.status == "ok" and not self.rows:
            raise ValueError("an ok macro section needs its rows")
        if self.status != "ok" and self.rows:
            raise ValueError("a not-ok macro section carries no rows")
        if len(self.correlation) != len(self.correlation_codes) or any(
            len(r) != len(self.correlation_codes) for r in self.correlation
        ):
            raise ValueError("the correlation matrix must be square, one row per code")
        return self


MACRO_SECTION = SectionSpec(report_field="macro", model=MacroSection)
