"""World beta (quick estimate) section: the stock against the iShares MSCI ACWI ETF.

Definition: ``docs/validation/world-beta-handoff-2026-11-18.md`` (WB1) and
``analytics/world_beta.py``. Contract note for the sixth section:
``docs/validation/world-beta-contract-note-2026-11-18.md``.

The report field ``world_beta`` holds one section. ``world`` is the single-factor regression of
the stock's daily excess returns on ACWI's daily excess returns; ``us_market`` is the same days
against the US market factor ``Mkt-RF``. ``comparison`` reads the two intervals in plain words.

Statuses: ``ok``; ``insufficient_data`` (fewer than 252 common days); ``failed`` (the ACWI price
audit found errors, the benchmark return does not vary, or another error), including the
case where ACWI could not be fetched and no cache exists (reason "The world fund's prices could not
be fetched.", the cause in ``acwi_note``, both ACWI dates ``None``). The report always builds. A
cached history that is stale because the refresh failed is still ``ok``; ``acwi_note`` says where
it ends.
A section that is not ``ok`` carries no float, so ``world`` and ``us_market`` are then ``None``.

``europe`` (additive, 2026-11-19) repeats the computation for the Europe proxy IEUR (iShares Core
MSCI Europe ETF, USD, history from June 2014) as a nested ``ProxyBeta`` with its own status and
reason. It does not change the status of the section, which stays that of the ACWI fields.

``sample`` describes the common days: ``n``, ``start`` and ``end`` are the overlap with ACWI;
the requested range and the exclusions are those of the analysis sample.
"""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import Field, model_validator

from factordesk.report.base import FrozenModel, SectionModel, SectionSpec, Status

WorldBetaLabel = Literal["L-DESC", "L-WORLD-PROXY", "L-WORLD-ASYNC"]
ComparisonKey = Literal["about_the_same", "higher", "lower"]

LABEL_TEXT: dict[str, str] = {
    "L-WORLD-PROXY": (
        "ACWI is the iShares MSCI ACWI ETF (an exchange-traded fund), used here as a stand-in "
        "for the MSCI ACWI index, which has no free daily data. It is priced in US dollars on a US "
        "exchange at the same close as US stocks."
    ),
    "L-WORLD-ASYNC": (
        "A quick estimate, not a full model. ACWI includes many non-US stocks (their share "
        "varies over time) whose markets close earlier than the US, so same-day co-movement with "
        "a US stock can be understated; this is not corrected here. A stock with a short history "
        "has a wide interval."
    ),
}
"""Footnote keys of this section and their texts."""


class BetaFit(FrozenModel):
    """One single-factor regression of the stock's excess return, with Newey-West inference."""

    beta: float
    se: float = Field(ge=0.0, description="Newey-West standard error of the beta (M0.5).")
    ci_low: float = Field(description="Normal 95% interval of the beta, lower end.")
    ci_high: float = Field(description="Normal 95% interval of the beta, upper end.")
    r2: float = Field(ge=0.0, le=1.0 + 1e-12, description="R squared of the regression.")
    correlation: float = Field(
        ge=-1.0 - 1e-12, le=1.0 + 1e-12, description="Correlation of the two excess returns."
    )
    alpha_annual: float = Field(description="Intercept times 252, as a decimal a year.")
    alpha_t: float | None = Field(description="HAC t of the intercept; null on an exact fit.")

    @model_validator(mode="after")
    def _interval_orders(self) -> BetaFit:
        if self.ci_low > self.ci_high:
            raise ValueError("ci_low is above ci_high")
        return self


class ProxyBeta(FrozenModel):
    """The quick beta against one more proxy (Europe: IEUR), with its own status.

    Holds what the ACWI fields of ``WorldBetaSection`` hold, for one proxy: the beta against the
    proxy and against the US market on the same days, the comparison, the days and the price
    history it rests on. It answers for its own numbers: a block that is not ``ok`` has no fit.
    """

    status: Status
    reason: str | None = Field(description="Human-readable reason when status is not 'ok'.")
    label: str = Field(description="Index the proxy stands in for, for example 'MSCI Europe'.")
    proxy: str = Field(description="Yahoo ticker of the proxy fund, for example 'IEUR'.")
    n_days: int = Field(ge=0, description="Days common to the analysis sample and the proxy.")
    start: date | None = Field(description="First of those common days.")
    end: date | None = Field(description="Last of those common days.")
    hac_lags: int | None = Field(description="Newey-West lags of both regressions; null if none.")
    n_not_in_benchmark: int = Field(
        ge=0, description="Rows of the analysis sample with no usable proxy return."
    )
    first_date: date | None = Field(
        description="First date of the proxy price history used; null if there is none."
    )
    last_date: date | None = Field(
        description="Last date of the proxy price history used; null if there is none."
    )
    note: str | None = Field(
        description="Set when the proxy refresh failed: where the cached history ends, or why "
        "there is none."
    )
    audit_warnings: list[str] = Field(description="Warnings of the proxy price audit (M1.4).")
    benchmark: BetaFit | None = Field(description="Against the proxy fund, excess of RF.")
    us_market: BetaFit | None = Field(description="Against the US market, same days.")
    comparison: ComparisonKey | None = Field(
        description="Proxy beta against the US market beta: about_the_same when the two 95% "
        "intervals overlap, otherwise higher or lower (a reading of the intervals, not a test)."
    )
    comparison_text: str | None = Field(description="The plain reading of the comparison.")

    @model_validator(mode="after")
    def _shape(self) -> ProxyBeta:
        if (self.status == "ok") != (self.reason is None):
            raise ValueError("reason must be None exactly when status is 'ok'")
        parts = (
            self.benchmark,
            self.us_market,
            self.comparison,
            self.comparison_text,
            self.hac_lags,
        )
        if self.status == "ok":
            if any(p is None for p in parts) or self.last_date is None:
                raise ValueError("an ok block fills both fits, the comparison, the lags and dates")
        elif any(p is not None for p in parts):
            raise ValueError("a block that is not ok carries no fits or comparison")
        if (self.first_date is None) != (self.last_date is None):
            raise ValueError("the first and last proxy date are both set or both null")
        if (
            self.first_date is not None
            and self.last_date is not None
            and self.first_date > self.last_date
        ):
            raise ValueError("first_date is after last_date")
        return self


class WorldBetaSection(SectionModel):
    """The quick beta against ACWI next to the beta against the US market, on the same days."""

    proxy: Literal["ACWI"] = Field(description="Yahoo ticker of the world proxy.")
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
    comparison: ComparisonKey | None = Field(
        description="World beta against the US market beta: about_the_same when the two 95% "
        "intervals overlap, otherwise higher or lower (a reading of the intervals, not a test)."
    )
    comparison_text: str | None = Field(description="The plain reading of the comparison.")
    europe: ProxyBeta | None = Field(
        default=None,
        description="The same quick beta against the Europe proxy (IEUR, stand-in for MSCI "
        "Europe), with its own status and reason; null when it was not computed. The section "
        "status is that of the ACWI fields above, so a failed Europe block never changes it.",
    )
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
