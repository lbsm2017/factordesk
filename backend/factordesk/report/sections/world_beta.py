"""World beta (quick estimate) section: the stock against the iShares MSCI ACWI ETF.

Definition: ``docs/validation/world-beta-handoff-2026-11-18.md`` (WB1) and
``analytics/world_beta.py``. Contract note for the sixth section:
``docs/validation/world-beta-contract-note-2026-11-18.md``.

The report field ``world_beta`` holds one section. ``world`` is the single-factor regression of
the stock's daily excess returns on ACWI's daily excess returns; ``us_market`` is the same days
against the US market factor ``Mkt-RF``. ``comparison`` reads the two intervals in plain words.

Statuses: ``ok``; ``insufficient_data`` (fewer than 252 common days); ``failed`` (the ACWI price
audit found errors, the benchmark return does not vary, or another error), including the
case where ACWI could not be fetched and no cache exists (reason "ACWI price data could not be
fetched", the cause in ``acwi_note``, both ACWI dates ``None``). The report always builds. A
cached history that is stale because the refresh failed is still ``ok``; ``acwi_note`` says where
it ends.
A section that is not ``ok`` carries no float, so ``world`` and ``us_market`` are then ``None``.

``sample`` describes the common days: ``n``, ``start`` and ``end`` are the overlap with ACWI;
the requested range and the exclusions are those of the analysis sample.
"""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import Field, model_validator

from factordesk.report.base import FrozenModel, SectionModel, SectionSpec

WorldBetaLabel = Literal["L-DESC", "L-WORLD-PROXY", "L-WORLD-ASYNC"]
ComparisonKey = Literal["about_the_same", "higher_against_the_world", "lower_against_the_world"]

LABEL_TEXT: dict[str, str] = {
    "L-WORLD-PROXY": (
        "ACWI is the iShares MSCI ACWI ETF (an exchange-traded fund), used here as a stand-in "
        "for the MSCI ACWI index, which has no free daily data. It is priced in US dollars on a US "
        "exchange at the same close as US stocks."
    ),
    "L-WORLD-ASYNC": (
        "A quick estimate, not a full model. ACWI holds mostly non-US stocks whose markets close "
        "earlier than the US, so same-day co-movement with a US stock can be understated; this is "
        "not corrected here. A stock with a short history has a wide interval."
    ),
}
"""Footnote keys of this section and their texts."""


class BetaFit(FrozenModel):
    """One single-factor regression of the stock's excess return, with Newey-West inference."""

    beta: float
    se_hac: float = Field(ge=0.0, description="Newey-West standard error of the beta (M0.5).")
    ci95_low: float = Field(description="Normal 95% interval of the beta, lower end.")
    ci95_high: float = Field(description="Normal 95% interval of the beta, upper end.")
    r2: float = Field(ge=0.0, le=1.0 + 1e-12, description="R squared of the regression.")
    correlation: float = Field(
        ge=-1.0 - 1e-12, le=1.0 + 1e-12, description="Correlation of the two excess returns."
    )
    alpha_annual: float = Field(description="Intercept times 252, as a decimal a year.")
    alpha_t: float | None = Field(description="HAC t of the intercept; null on an exact fit.")

    @model_validator(mode="after")
    def _interval_orders(self) -> BetaFit:
        if self.ci95_low > self.ci95_high:
            raise ValueError("ci95_low is above ci95_high")
        return self


class WorldBetaSection(SectionModel):
    """The quick beta against ACWI next to the beta against the US market, on the same days."""

    benchmark: Literal["ACWI"] = Field(description="Yahoo ticker of the world proxy.")
    hac_lags: int | None = Field(description="Newey-West lags of both regressions; null if none.")
    n_sample: int = Field(ge=0, description="Rows of the analysis sample.")
    n_not_in_benchmark: int = Field(
        ge=0, description="Rows of the analysis sample with no usable ACWI return."
    )
    acwi_first_date: date | None = Field(
        description="First date of the ACWI price history used; null if there is none."
    )
    acwi_last_date: date | None = Field(
        description="Last date of the ACWI price history used; null if there is none."
    )
    acwi_note: str | None = Field(
        description="Set when the ACWI refresh failed: where the cached history ends, or why "
        "there is none."
    )
    audit_warnings: list[str] = Field(description="Warnings of the ACWI price audit (M1.4).")
    world: BetaFit | None = Field(description="Against the world: ACWI, excess of RF.")
    us_market: BetaFit | None = Field(description="Against the US market, same days.")
    comparison: ComparisonKey | None
    comparison_text: str | None = Field(description="The plain reading of the comparison.")
    labels: list[WorldBetaLabel]

    @model_validator(mode="after")
    def _shape(self) -> WorldBetaSection:
        parts = (self.world, self.us_market, self.comparison, self.comparison_text, self.hac_lags)
        if self.status == "ok":
            if any(p is None for p in parts):
                raise ValueError("an ok section fills both fits, the comparison and the lags")
        elif any(p is not None for p in parts):
            raise ValueError("a section that is not ok carries no fits or comparison")
        if (self.acwi_first_date is None) != (self.acwi_last_date is None):
            raise ValueError("the first and last ACWI date are both set or both null")
        if self.status == "ok" and self.acwi_last_date is None:
            raise ValueError("an ok section has ACWI dates")
        if (
            self.acwi_first_date is not None
            and self.acwi_last_date is not None
            and self.acwi_first_date > self.acwi_last_date
        ):
            raise ValueError("acwi_first_date is after acwi_last_date")
        return self


WORLD_BETA_SECTION = SectionSpec(
    report_field="world_beta", model=WorldBetaSection, label_text=LABEL_TEXT
)
