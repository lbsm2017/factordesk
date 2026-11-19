"""Pipeline hook of the KalmanBetaSeries section (docs/specs/kalman-betas.md; contract SC2.3).

The statistics are in ``analytics/kalman.py``; this module turns the analysis sample into the
section model. It reads only the context (``ctx.sample``, ``ctx.gate``, ``ctx.sample_info``),
never changes a core section and never raises for data reasons: a sample the filter cannot use
gives a section with ``status = "failed"`` and a reason.

Status and reason strings (spec KB8.3):

* ``insufficient_data``: "Insufficient data: Kalman betas need at least 504 rows; this sample has
  {n} (kalman_needs_504_rows)."
* ``failed``: "... first 21 rows ... (singular_burn_in)" or "... factor covariance ...
  (singular_factor_covariance)", or the input check message when a value is not finite.
* ``failed`` also covers any other error of the filter ("... unexpected error ... (kalman_error)")
  and a result with a non-finite value or a section that does not validate ("... not usable ...
  (kalman_invalid_output)"). The hook logs the exception and the report still builds.
"""

from __future__ import annotations

import logging
import math

import numpy as np
import pandas as pd
from numpy.typing import NDArray

from factordesk.analytics.kalman import (
    BURN_IN_ROWS,
    REESTIMATE_EVERY,
    TRAINING_ROWS,
    KalmanResult,
    kalman_betas,
)
from factordesk.analytics.regression import A
from factordesk.analytics.sample import DISPLAY_NAMES, FACTOR_CODES
from factordesk.report.base import SampleInfo
from factordesk.report.sections.kalman import (
    KalmanBetaSeries,
    KalmanLabelKey,
    KalmanLatest,
    KalmanVintage,
)
from factordesk.section_hooks.context import SectionContext

FloatArray = NDArray[np.float64]

logger = logging.getLogger(__name__)

SIG_DIGITS = 6
"""Series are rounded to 6 significant digits, as the rolling betas are (methodology D31)."""

_NOT_OK_REASONS: dict[str, str] = {
    "kalman_needs_504_rows": (
        "Insufficient data: Kalman betas need at least {need} rows; this sample has {n} "
        "(kalman_needs_504_rows)."
    ),
    "singular_burn_in": (
        "The first {burn} rows do not identify the intercept and the five betas (the factor "
        "matrix is singular or nearly so), so the Kalman betas are not reported "
        "(singular_burn_in)."
    ),
    "singular_factor_covariance": (
        "The factor covariance is singular or nearly so, so the Kalman betas are not reported "
        "(singular_factor_covariance)."
    ),
}


def _sig(value: float) -> float:
    """6 significant digits, as the series (so ``latest`` equals the last series value)."""
    return float(f"{float(value):.{SIG_DIGITS}g}")


def _round(values: FloatArray) -> list[float | None]:
    """6 significant digits; NaN (warm-up) becomes ``None``."""
    return [None if math.isnan(v) else float(f"{v:.{SIG_DIGITS}g}") for v in values.tolist()]


def _by_factor(matrix: FloatArray) -> dict[str, list[float | None]]:
    return {DISPLAY_NAMES[code]: _round(matrix[:, k]) for k, code in enumerate(FACTOR_CODES)}


def _labels(gate_fired: bool) -> list[KalmanLabelKey]:
    return ["L-KF", "L-KBAND", "L-KTAIL"] if gate_fired else ["L-KF", "L-KBAND"]


def _require_finite(result: KalmanResult) -> None:
    """Raise ``ValueError`` when a stamped value of an ``ok`` result is NaN or infinite.

    Warm-up rows (``vintage_index == -1``) are NaN by design; everything else a panel reads must be
    finite, or ``_round`` would turn a NaN into a silent gap.
    """
    stamped = result.vintage_index >= 0
    series = (result.alpha[stamped], *(m[stamped] for m in (result.betas, result.band_low)))
    series += (result.band_high[stamped], result.latest_sd)
    if not stamped.any() or not all(bool(np.isfinite(a).all()) for a in series):
        raise ValueError("the filter returned a non-finite value")
    if not all(math.isfinite(v.lam) and math.isfinite(v.resid_var) for v in result.vintages):
        raise ValueError("the filter returned a non-finite hyperparameter")


def not_ok_section(
    status: str, reason: str, info: SampleInfo, error_model: str = "gaussian"
) -> KalmanBetaSeries:
    """A section with no series (``insufficient_data`` or ``failed``)."""
    return KalmanBetaSeries.model_validate(
        {
            "status": status,
            "reason": reason,
            "sample": info.model_dump(),
            "model": "rw_betas_const_alpha_v1",
            "error_model": error_model,
            "burn_in_rows": BURN_IN_ROWS,
            "training_rows": TRAINING_ROWS,
            "reestimate_every": REESTIMATE_EVERY,
            "dates": [],
            "alpha": [],
            "betas": {},
            "band_low": {},
            "band_high": {},
            "vintage_index": [],
            "vintages": [],
            "latest": {},
            "labels": [],
            "warnings": [],
        }
    )


def section_from_result(
    result: KalmanResult,
    dates: pd.DatetimeIndex,
    info: SampleInfo,
    *,
    gate_fired: bool,
) -> KalmanBetaSeries:
    """The section model of a ``KalmanResult`` on the sample dates (pure)."""
    if result.status != "ok":
        code = result.reason or ""
        template = _NOT_OK_REASONS.get(code, "{code}")
        reason = template.format(need=TRAINING_ROWS, n=result.n, burn=BURN_IN_ROWS, code=code)
        return not_ok_section(result.status, reason, info, result.error_model)
    _require_finite(result)
    stamps = [pd.Timestamp(ts).date() for ts in dates]
    vintages = [
        KalmanVintage(
            index=v.index,
            estimated_through=stamps[v.rows - 1],
            rows=v.rows,
            lam=v.lam,
            lam_at_bound=v.lam_at_bound,
            resid_var=v.resid_var,
            resid_vol_ann=math.sqrt(A * v.resid_var),
            w_eq=v.w_eq,
            valid_from=stamps[v.valid_from - 1],
            valid_to=stamps[v.valid_to - 1],
        )
        for v in result.vintages
    ]
    last = result.n - 1
    latest = {
        DISPLAY_NAMES[code]: KalmanLatest(
            beta=_sig(result.betas[last, k]),
            sd=_sig(result.latest_sd[k]),
            band_low=_sig(result.band_low[last, k]),
            band_high=_sig(result.band_high[last, k]),
        )
        for k, code in enumerate(FACTOR_CODES)
    }
    return KalmanBetaSeries(
        status="ok",
        reason=None,
        sample=info,
        model="rw_betas_const_alpha_v1",
        error_model=result.error_model,
        burn_in_rows=BURN_IN_ROWS,
        training_rows=TRAINING_ROWS,
        reestimate_every=REESTIMATE_EVERY,
        dates=stamps,
        alpha=_round(result.alpha),
        betas=_by_factor(result.betas),
        band_low=_by_factor(result.band_low),
        band_high=_by_factor(result.band_high),
        vintage_index=[None if v < 0 else int(v) for v in result.vintage_index.tolist()],
        vintages=vintages,
        latest=latest,
        labels=_labels(gate_fired),
        warnings=list(result.warnings),
    )


def build_kalman_betas(ctx: SectionContext) -> KalmanBetaSeries | None:
    """The Kalman betas of the analysis sample (``None`` is never returned once built)."""
    sample = ctx.sample
    y = sample.xret.to_numpy(dtype=np.float64)
    f = sample.factors.loc[:, list(FACTOR_CODES)].to_numpy(dtype=np.float64)
    info = ctx.sample_info(None)
    try:
        result = kalman_betas(y, f)
    except ValueError as exc:  # non-finite input: the sample builder never produces it
        return not_ok_section("failed", f"The Kalman betas could not be computed ({exc}).", info)
    except Exception:  # any other error of the filter must not stop the report (SC3.2)
        logger.exception("kalman_betas raised; the Kalman section is marked failed")
        return not_ok_section(
            "failed",
            "The Kalman betas could not be computed because of an unexpected error (kalman_error).",
            info,
        )
    gate_fired = ctx.gate is not None and ctx.gate.fired
    try:
        return section_from_result(
            result, pd.DatetimeIndex(sample.xret.index), info, gate_fired=gate_fired
        )
    except Exception:  # a non-finite value or a section that does not validate
        logger.exception("the Kalman result could not be turned into a section")
        return not_ok_section(
            "failed",
            "The Kalman betas were computed but the result is not usable (kalman_invalid_output).",
            info,
            result.error_model,
        )
