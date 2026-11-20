"""Energy and carbon section: sensitivities to oil, gas and carbon prices, controlled for the
market (Sprint 3, item S3-8; definitions in ``analytics/energy.py``).

``EnergySection`` is the optional ``FactorReport.energy`` field. It is left out of the JSON when
``None`` (not written as ``null``), so a report built without it is byte-identical to one written
before the section existed. It is additive and does not change the schema version (contract SC5).

Two models, each one regression with Newey-West errors:

* ``long_model``: market, oil and gas, on the analysed window;
* ``carbon_model``: market, oil, gas and carbon (KRBN), from KRBN's first date. It is ``None``
  when the window holds less than two years of carbon data (``carbon_note`` says why) or KRBN
  prices are unavailable.

Each model has one row per leg (raw beta, standard error, t, p, tag, VIF) and a gas robustness
fit: the same regression without the five rows (days or months) with the largest absolute gas
return, with its own gas beta and t. Gas returns are extremely fat-tailed and nothing is
winsorised. A model names the leg that limits its window only when that leg starts on or after
the subject's own start (the macro rule).

A section whose FRED series are unavailable has status ``failed`` and a reason: the panel shows
the notice and the rest of the report is unaffected.
"""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import Field, model_validator

from factordesk.report.base import FrozenModel, SectionModel, SectionSpec, Tag

EnergyCode = Literal["mkt_rf", "oil", "gas", "co2"]

MODEL_NOTE = (
    "Separate regression, not the headline model. Sensitivities are raw and describe "
    "co-movement in this window, not a forecast."
)
"""Fixed note under the section."""
CARBON_LABEL = "short sample, since Aug 2020, mainly EU carbon"
"""Label of the carbon model (KRBN starts in July 2020 and holds mainly EU allowances)."""
GAS_NOTE_DAILY = (
    "Daily gas sensitivities are descriptive: gas moves are extremely fat-tailed, so a few "
    "days can drive the result."
)
"""Shown for a daily subject, which has the fat-tailed daily gas returns."""
GAS_NOTE_MONTHLY = (
    "Gas moves are fat-tailed: read the gas sensitivity together with the one that leaves out "
    "the five largest gas months."
)
FRED_UNAVAILABLE = (
    "The Brent or Henry Hub price series could not be fetched from FRED, so the energy and "
    "carbon section is not shown."
)


class EnergyRow(FrozenModel):
    """One leg of an energy regression."""

    code: EnergyCode
    name: str = Field(description='Display name: "Mkt-RF", "OIL", "GAS", "CO2".')
    label: str = Field(description="Plain label: Market, Oil, Natural gas, Carbon.")
    definition: str = Field(description="How the leg is built.")
    note: str | None = Field(description="Caveat on the leg.")
    beta: float = Field(description="Raw sensitivity: excess return per 1.00 of the leg return.")
    se: float = Field(ge=0.0, description="Newey-West HAC standard error of beta.")
    t: float = Field(description="HAC t-statistic of beta.")
    p: float = Field(ge=0.0, le=1.0, description="Two-sided p-value of t.")
    ci_low: float = Field(description="Lower end of the 95% interval, beta - q * se.")
    ci_high: float = Field(description="Upper end of the 95% interval, beta + q * se.")
    tag: Tag = Field(
        description="Reliable when the Benjamini-Hochberg rule of the headline betas rejects "
        "zero across the legs of this model."
    )
    vif: float = Field(ge=1.0, description="Variance inflation factor among the legs.")


class GasRobustness(FrozenModel):
    """The gas sensitivity of the same model fitted without the largest gas moves."""

    beta: float = Field(description="Gas beta without the excluded rows.")
    se: float = Field(ge=0.0)
    t: float
    p: float = Field(ge=0.0, le=1.0)
    n_excluded: int = Field(ge=0, description="Rows left out: the largest absolute gas returns.")
    excluded_dates: list[date] = Field(description="Dates of the rows left out, largest first.")
    n_obs: int = Field(ge=0, description="Rows of this second fit.")


class EnergyModel(FrozenModel):
    """One regression of the section."""

    key: Literal["long", "carbon"]
    title: str = Field(description='"Market, oil and gas" or "Market, oil, gas and carbon".')
    label: str | None = Field(description="Short-sample label of the carbon model; None otherwise.")
    n_obs: int = Field(ge=0, description="Rows of the regression.")
    start: date = Field(description="First date of the regression.")
    end: date = Field(description="Last date of the regression.")
    hac_lags: int = Field(ge=0, description="Newey-West lag of the fit.")
    t_reference: Literal["normal", "student_t"]
    r2: float
    adj_r2: float
    rows: list[EnergyRow] = Field(description="Market, oil, gas (and carbon).")
    gas_robust: GasRobustness
    window_limited_by: str | None = Field(
        description="The leg whose first date starts the window, when it is later than the "
        "subject's own start; None otherwise."
    )


class EnergyLeg(FrozenModel):
    """One price series behind a leg, with its first date."""

    ticker: str = Field(description="FRED series id or Yahoo ticker.")
    code: EnergyCode
    role: str = Field(description='What it feeds, for example "OIL = log change of Brent".')
    first_date: date | None = Field(description="First price date; None when not fetched.")


class EnergySection(SectionModel):
    """Sensitivity to oil, gas and carbon prices, after the market."""

    model_note: str = Field(description="Fixed note: separate regression, raw sensitivities.")
    gas_note: str = Field(description="Caveat on the fat-tailed gas leg.")
    frequency: Literal["daily", "monthly"]
    n_sample: int = Field(ge=0, description="Rows of the analysis sample before the legs.")
    long_model: EnergyModel | None = Field(description="Market, oil, gas; None unless ok.")
    carbon_model: EnergyModel | None = Field(
        description="Market, oil, gas, carbon; None when hidden (see carbon_note)."
    )
    carbon_note: str | None = Field(description="Why the carbon model is not shown; None if shown.")
    legs: list[EnergyLeg] = Field(description="The series behind the legs, with first dates.")

    @model_validator(mode="after")
    def _models_match_status(self) -> EnergySection:
        if self.status == "ok" and self.long_model is None:
            raise ValueError("an ok energy section needs its long model")
        if self.status != "ok" and (self.long_model is not None or self.carbon_model is not None):
            raise ValueError("a not-ok energy section carries no model")
        if self.long_model is not None and self.long_model.key != "long":
            raise ValueError("long_model must have key 'long'")
        if self.carbon_model is not None:
            if self.carbon_model.key != "carbon":
                raise ValueError("carbon_model must have key 'carbon'")
            if self.carbon_note is not None:
                raise ValueError("a shown carbon model has no carbon_note")
        return self


ENERGY_SECTION = SectionSpec(report_field="energy", model=EnergySection)
