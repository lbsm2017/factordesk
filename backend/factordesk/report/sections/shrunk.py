"""Shrunk (Bayesian) betas section.

Spec: ``docs/specs/shrunk-betas.md`` (SB7.2 schema, SB7.1 status values); contract SC2.4.

The report field ``shrunk_betas`` holds a list: one ``ShrunkBetas`` per scope, ``full_sample``
then ``latest_window`` (SD7). Each entry is the OLS betas of one regression pulled toward a stated
prior, with the 95% credible interval, the share each beta was pulled, and a power statement per
factor. OLS stays primary everywhere (SD3): nothing here is a test, a tag or a family (SD5).

Differences from the spec text, all from the contract: ``factor`` holds display names (SC6 item
12); the module sits here and not in ``schema.py`` (SC6 item 9); label texts live in
``SHRUNK_SECTION.label_text`` (SC6 item 10). A section whose status is not ``ok`` carries no
float, so its ``prior``, ``betas`` and ``power`` are empty (SC1 item 3); the numeric fields of
``ShrunkBeta`` are therefore always filled in an ``ok`` section.
"""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import Field, model_validator

from factordesk.report.base import FACTOR_NAMES, FrozenModel, SectionModel, SectionSpec

FactorName = Literal["Mkt-RF", "SMB", "HML", "RMW", "CMA"]
ShrunkLabel = Literal["L-DESC", "L-SHRINK", "L-SHRINK-PRIOR", "L-CRED", "L-CORR-MOVE", "L-MDE"]
Scope = Literal["full_sample", "latest_window"]
PriorSource = Literal["reference_ff_portfolios_v1", "peer_empirical_bayes_v1"]

LABEL_TEXT: dict[str, str] = {
    "L-SHRINK": (
        "Pulled toward typical: each beta is moved toward the beta of the market portfolio "
        "(Mkt-RF 1, others 0), more when it is noisy. How far depends on how much betas differ "
        "across Ken French industry and size portfolios. A model-based view, not a test; the "
        "bars show the estimates from this stock's data."
    ),
    "L-SHRINK-PRIOR": (
        "Prior: centre 1 for Mkt-RF and 0 for the other betas, spread from the Ken French "
        "industry and size portfolios (values in the table). Portfolios differ less than single "
        "stocks, so this pull may be too strong for unusual stocks."
    ),
    "L-CRED": (
        "95% credible interval under the stated prior; based on the HAC (Newey-West) "
        "uncertainty of the estimate."
    ),
    "L-CORR-MOVE": (
        "Moved away from its typical value because it is estimated jointly with correlated factors."
    ),
    "L-MDE": (
        "Smallest beta that the test behind the reliable tags would detect with 80% power, after "
        "correcting for testing 5 betas. It describes that test, not the shrunk estimate, and "
        "assumes the standard error keeps shrinking like one over the square root of the data."
    ),
}
"""Footnote keys of this section (proposed for M0.9, SB6) and their texts."""


class DatasetStamp(FrozenModel):
    """Vintage of one portfolio file behind the prior (SB2.3, methodology-datasets D5)."""

    key: str = Field(description="Dataset key, e.g. ind49_daily.")
    crsp_stamp: str | None = Field(description='CRSP database stamp of the file ("202609").')
    sha256: str | None
    last_modified: str | None = Field(description="HTTP Last-Modified header at download.")


class ShrinkagePrior(FrozenModel):
    """The prior the betas were pulled toward (SB2) and what it was estimated from."""

    source: PriorSource
    centre: list[float] = Field(description="Prior centre m0, one per factor, canonical order.")
    tau: list[float] = Field(description="Prior standard deviation per factor.")
    tau_by_cross_section: dict[str, list[float]] | None = Field(
        description="Spread of each cross-section before the maximum and the floor."
    )
    n_portfolios: dict[str, int] = Field(description="Usable portfolios per cross-section.")
    window_start: date
    window_end: date = Field(description="The last French row used: not after the sample end.")
    window_rows: int = Field(ge=1)
    datasets: list[DatasetStamp]
    fallback_reason: str | None = Field(description="Why a peer prior fell back to this one.")

    @model_validator(mode="after")
    def _five_factors(self) -> ShrinkagePrior:
        if len(self.centre) != 5 or len(self.tau) != 5:
            raise ValueError("centre and tau need one value per factor")
        if any(t <= 0.0 for t in self.tau):
            raise ValueError("tau must be positive")
        return self


class ShrunkBeta(FrozenModel):
    """One factor: the OLS beta and the beta pulled toward the prior."""

    factor: FactorName
    beta_ols: float
    se_hac: float = Field(description="Newey-West standard error of the OLS beta.")
    beta_shrunk: float | None
    sd_post: float | None = Field(description="Posterior standard deviation.")
    cred95_low: float | None
    cred95_high: float | None
    pull: float | None = Field(
        description="Share of the way pulled toward the prior centre (S_w[j, j]), unclipped."
    )
    moved_away: bool | None = Field(
        description="True when the shrunk beta moved away from its centre (L-CORR-MOVE)."
    )


class PowerStatement(FrozenModel):
    """What the test behind the tags can detect for one factor (SB5)."""

    factor: FactorName
    mde80: float | None = Field(description="Smallest beta detected with 80% power.")
    alpha_level: float = Field(description="Level behind the MDE: 0.01 (5 betas).")
    delta: float = Field(description="Beta size the years-to-detect figure asks about.")
    extra_years_to_detect_delta: float | None = Field(
        description="More years of similar data needed to detect delta; null for Mkt-RF."
    )
    text: str | None


class ShrunkBetas(SectionModel):
    """OLS betas pulled toward a stated prior, with a power statement per factor (SB0.1)."""

    scope: Scope
    window: int | None = Field(description="Rows of the latest window; null for the full sample.")
    hac_lags: int = Field(ge=0, description="Newey-West lags of the regression shrunk.")
    prior: ShrinkagePrior | None
    betas: list[ShrunkBeta]
    power: list[PowerStatement]
    labels: list[ShrunkLabel]

    @model_validator(mode="after")
    def _shape(self) -> ShrunkBetas:
        if (self.scope == "latest_window") != (self.window is not None):
            raise ValueError("window is set exactly for the latest_window scope")
        if self.status == "ok":
            if self.prior is None:
                raise ValueError("an ok section needs its prior")
            for factors in ([b.factor for b in self.betas], [p.factor for p in self.power]):
                if factors != list(FACTOR_NAMES):
                    raise ValueError("one row per factor, in canonical order")
            if any(
                v is None
                for b in self.betas
                for v in (b.beta_shrunk, b.sd_post, b.cred95_low, b.cred95_high, b.pull)
            ):
                raise ValueError("an ok section fills every shrunk value")
        elif self.prior is not None or self.betas or self.power:
            raise ValueError("a section that is not ok carries no prior, betas or power")
        return self


SHRUNK_SECTION = SectionSpec(
    report_field="shrunk_betas", model=ShrunkBetas, many=True, label_text=LABEL_TEXT
)
