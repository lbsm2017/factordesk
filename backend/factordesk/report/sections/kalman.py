"""Kalman-filter (time-varying) betas section.

Spec: ``docs/specs/kalman-betas.md`` (KB8.3 outputs, status values and schema); contract SC2.3.

``KalmanBetaSeries`` holds one daily series of filtered betas (random-walk betas, constant alpha)
with a model-based 95% band, on one shared date axis. Every value stamped at a date uses only rows
up to that date (spec KB0.3). The series is an additional view beside the rolling betas: nothing
downstream uses it. The smoothed retrospective view is not part of version 1 (spec KB10.4 Q4), so
there is no ``KalmanRetrospective`` model.

Series are rounded to 6 significant digits, as the rolling betas are (methodology D31); the
hyperparameters in ``vintages`` keep full precision. Warm-up positions (rows before the first
stamp at row 504) are ``None``, never NaN. A section whose status is not ``ok`` carries empty
series.
"""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import Field, model_validator

from factordesk.report.base import FACTOR_NAMES, FrozenModel, SectionModel, SectionSpec
from factordesk.report.kalman_text import kalman_text

KalmanLabelKey = Literal["L-KF", "L-KBAND", "L-KTAIL"]
"""Footnote keys of this section (texts in ``KALMAN_SECTION.label_text``)."""
KalmanErrorModel = Literal["gaussian", "student_t5"]
LambdaBound = Literal["zero", "upper", "none"]

WARNING_UPPER_BOUND = "kalman_lambda_at_upper_bound"
WARNING_TEXT: dict[str, str] = dict(kalman_text()["warnings"])
"""Warning codes a section can carry, with the sentence a panel shows (``kalman_text.json``)."""

L_KF = (
    "Kalman-filter beta: each point uses only data up to that date. It follows gradual changes "
    "smoothly, but reacts slowly to sudden changes; compare with the 126-day line. The drift rate "
    "is re-estimated once a year from past data, so the line can jump at those dates (marked)."
)
L_KBAND = (
    "Model-based 95% band. It assumes normal, independent daily errors with constant variance and "
    "treats the estimated drift rate as known. It is not a Newey-West (HAC) interval and is not "
    "comparable to the rolling-beta bands. After a sudden change it is too narrow."
)
L_KTAIL = (
    "Daily price changes for this ticker partly reverse the next day (see the data-quality "
    "check). The filter ignores that, so the band is too narrow for this ticker."
)

_BAND_SLACK = 1e-5
"""Rounding to 6 significant digits may move a value by 5e-6 relative; bands tolerate that."""


class KalmanVintage(FrozenModel):
    """Hyperparameters of one yearly re-estimate (spec KB2.4). Vintage ``j`` uses rows
    ``1 .. rows`` only and supplies the stamps from ``valid_from`` to ``valid_to``."""

    index: int = Field(ge=0)
    estimated_through: date = Field(description="Date of the last row used (row ``rows``).")
    rows: int = Field(ge=1, description="Rows ``1 .. rows`` of the sample were used.")
    lam: float = Field(ge=0, description="Signal-to-noise ratio lambda (0: no drift detected).")
    lam_at_bound: LambdaBound = Field(
        description="'zero' when lambda is 0, 'upper' at the largest grid value 1e-2, else 'none'."
    )
    resid_var: float = Field(ge=0, description="Residual variance R_hat, decimal^2 per day.")
    resid_vol_ann: float = Field(ge=0, description="sqrt(252 R_hat): residual volatility a year.")
    w_eq: float | None = Field(
        description="Equivalent rolling window 2 / sqrt(lambda) in rows; null when lambda is 0."
    )
    valid_from: date
    valid_to: date


class KalmanLatest(FrozenModel):
    """The filtered beta of one factor at the last date, with its model standard deviation."""

    beta: float
    sd: float = Field(ge=0, description="Model standard deviation sqrt(R_hat P_jj).")
    band_low: float
    band_high: float


class KalmanBetaSeries(SectionModel):
    """Filtered (point-in-time) Kalman betas per date, with model-based bands (spec KB0.1).

    Status values (spec KB8.3): ``ok``; ``insufficient_data`` when the sample has fewer than 504
    rows; ``failed`` when the first 21 rows do not identify the model (``singular_burn_in``) or a
    factor covariance is singular (``singular_factor_covariance``). The reason of a not-ok
    section names the code in parentheses.
    """

    model: Literal["rw_betas_const_alpha_v1"] = Field(
        description="Random-walk betas, constant alpha, one scalar signal-to-noise ratio."
    )
    error_model: KalmanErrorModel
    burn_in_rows: int = Field(description="Rows of the initial OLS fit (21).")
    training_rows: int = Field(description="Rows of the first estimate and first stamp (504).")
    reestimate_every: int = Field(description="Rows between re-estimates (252).")
    dates: list[date] = Field(description="Shared date axis: every row of the analysis sample.")
    alpha: list[float | None] = Field(description="Filtered alpha, decimal per day.")
    betas: dict[str, list[float | None]] = Field(
        description="Filtered beta per factor (display names), aligned with ``dates``."
    )
    band_low: dict[str, list[float | None]]
    band_high: dict[str, list[float | None]]
    ex_ante_betas: dict[str, list[float | None]] = Field(
        description="Predicted beta for explaining each date, from rows before it only."
    )
    vintage_index: list[int | None] = Field(description="Vintage that produced each stamp.")
    vintages: list[KalmanVintage]
    latest: dict[str, KalmanLatest] = Field(description="Per factor, at the last date.")
    labels: list[KalmanLabelKey]
    warnings: list[str] = Field(description="Codes of ``WARNING_TEXT``.")

    @model_validator(mode="after")
    def _consistent(self) -> KalmanBetaSeries:
        """Shapes, warm-up nulls and band order (an ``ok`` section); empty otherwise."""
        keyed = (self.betas, self.band_low, self.band_high, self.ex_ante_betas)
        if self.status != "ok":
            empty = (
                not self.dates
                and not self.alpha
                and not self.vintage_index
                and not self.vintages
                and not self.latest
                and all(not series for series in keyed)
            )
            if not empty:
                raise ValueError("a section that is not ok carries no series")
            return self
        n = len(self.dates)
        if n < self.training_rows:
            raise ValueError("an ok section has at least training_rows dates")
        if len(self.alpha) != n or len(self.vintage_index) != n:
            raise ValueError("alpha and vintage_index must align with dates")
        for mapping in keyed:
            if tuple(mapping) != FACTOR_NAMES:
                raise ValueError(f"series keys must be {FACTOR_NAMES}")
            if any(len(series) != n for series in mapping.values()):
                raise ValueError("every series must align with dates")
        if tuple(self.latest) != FACTOR_NAMES:
            raise ValueError(f"latest keys must be {FACTOR_NAMES}")
        if not self.vintages:
            raise ValueError("an ok section has at least one vintage")
        stamped = [v is not None for v in self.vintage_index]
        if stamped != [a is not None for a in self.alpha]:
            raise ValueError("alpha must be null exactly where vintage_index is null")
        for name in FACTOR_NAMES:
            beta, low, high = self.betas[name], self.band_low[name], self.band_high[name]
            if stamped != [b is not None for b in beta]:
                raise ValueError(f"{name}: betas must be null exactly where vintage_index is null")
            if [b is not None for b in low] != stamped or [b is not None for b in high] != stamped:
                raise ValueError(f"{name}: band must be null exactly where betas are")
            for b, lo, hi in zip(beta, low, high, strict=True):
                if b is None or lo is None or hi is None:
                    continue
                slack = _BAND_SLACK * max(1.0, abs(b))
                if not lo - slack <= b <= hi + slack:
                    raise ValueError(f"{name}: a beta lies outside its band")
        unknown = [w for w in self.warnings if w not in WARNING_TEXT]
        if unknown:
            raise ValueError(f"unknown warning codes {unknown}")
        return self


KALMAN_SECTION = SectionSpec(
    report_field="kalman_betas",
    model=KalmanBetaSeries,
    label_text={"L-KF": L_KF, "L-KBAND": L_KBAND, "L-KTAIL": L_KTAIL},
)
