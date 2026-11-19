"""Pipeline hook of the alpha strip (E1): CAPM, FF3, FF5 and FF6 on the same rows.

The statistics are in ``analytics/model_comparison.py``. The strip needs the momentum factor: a
sample built on a factor frame without ``Mom`` (an FF5 frame passed straight to the pure core)
gives ``None``, so the section is left out of the report. The API always loads the FF6 frame, so
every report it serves carries the strip. A monthly subject uses the small-sample variant, as its
main regression does. A design the fit cannot use gives ``status = "failed"`` with a reason; the
hook never raises for data reasons.
"""

from __future__ import annotations

import logging

from factordesk.analytics.model_comparison import ModelComparison, compare_models
from factordesk.analytics.sample import DISPLAY_NAMES, DegenerateInputError
from factordesk.report.base import SampleInfo
from factordesk.report.sections.alpha_strip import (
    CAPTION,
    MODEL_NOTES,
    STRIP_INTRO,
    AlphaStrip,
    AlphaStripRow,
)
from factordesk.section_hooks.context import SectionContext

logger = logging.getLogger(__name__)

FAILED = "The alpha strip could not be computed: {reason}."


def _rows(comparison: ModelComparison) -> list[AlphaStripRow]:
    return [
        AlphaStripRow(
            model=row.model,
            label=row.label,
            factors=[DISPLAY_NAMES[c] for c in row.codes],
            alpha_annual=row.alpha_ann,
            alpha_se_annual=row.alpha_se_ann,
            alpha_t=row.alpha_t,
            alpha_p=row.alpha_p,
            r2=row.rsquared,
            adj_r2=row.rsquared_adj,
        )
        for row in comparison.models
    ]


def build_alpha_strip(ctx: SectionContext) -> AlphaStrip | None:
    """The alpha strip of the report, or ``None`` when the sample carries no momentum factor."""
    sample = ctx.sample
    if "mom" not in sample.factor_codes:
        return None
    base = ctx.sample_info()
    try:
        comparison = compare_models(sample, small_sample=sample.frequency != "daily")
    except (DegenerateInputError, ValueError) as exc:
        logger.info("alpha strip not computed for %s: %s", ctx.ticker, exc)
        reason = str(getattr(exc, "reason", exc)).rstrip(".")
        dropped = int((~sample.complete_rows(("mom",))).sum())
        return AlphaStrip(
            status="failed",
            reason=FAILED.format(reason=reason),
            sample=base,
            n_obs=0,
            n_dropped=dropped,
            hac_lags=0,
            t_reference=None,
            rows=[],
            model=ctx.model,
            caption=CAPTION,
            intro=STRIP_INTRO,
            model_note=MODEL_NOTES[ctx.model],
        )
    info: SampleInfo = base.model_copy(
        update={"n": comparison.nobs, "start": comparison.start, "end": comparison.end}
    )
    return AlphaStrip(
        status="ok",
        reason=None,
        sample=info,
        n_obs=comparison.nobs,
        n_dropped=comparison.n_dropped,
        hac_lags=comparison.lags,
        t_reference="normal" if comparison.models[0].t_df is None else "student_t",
        rows=_rows(comparison),
        model=ctx.model,
        caption=CAPTION,
        intro=STRIP_INTRO,
        model_note=MODEL_NOTES[ctx.model],
    )
