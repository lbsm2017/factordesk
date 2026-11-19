"""Alpha strip: alpha under CAPM, FF3, FF5 and FF6 on the same rows (E1, research A3).

For each model the strip reports the annualised alpha, its Newey-West HAC t-statistic, R² and
adjusted R². Every model is fitted on the same rows: those where the excess return and every
factor of every model requested have a value. The HAC lag is the rule ``floor(4 (n/100)^(2/9))``
of that common ``n``, so it is the same for all models. Alpha shrinking as factors are added is the
diagnostic (for example, alpha that goes once momentum is in the model).

The models are returned in the order asked for (by default by number of factors). Nothing here
ranks them or marks a "best" one: a higher R² does not make a model more correct, and alpha
depends on the model (E9a).

The fit is ``regression.ols_hac``, the same estimator as the full-sample regression, so the FF5
row equals ``run_regression`` on the same rows. HAC t-statistics are asymptotic (normal
reference); for 36 to 60 monthly rows they are approximate (research A3).

Pure: no I/O, no clock, no randomness. Inputs are not mutated.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

import numpy as np
import pandas as pd

from factordesk.analytics.models import MODEL_LABELS, MODEL_ORDER, MODELS, ModelName, model_codes
from factordesk.analytics.regression import (
    Tag,
    alpha_tag,
    hac_lags,
    ols_hac,
    resolve_periods,
)
from factordesk.analytics.sample import DISPLAY_NAMES, AnalysisSample


@dataclass(frozen=True)
class ModelAlpha:
    """One model's row of the strip. Annualised figures use ``ModelComparison.periods``."""

    model: ModelName
    label: str
    """Display label: "CAPM", "FF3", "FF5" or "FF6"."""
    codes: tuple[str, ...]
    alpha: float
    """Intercept per period (per day or per month)."""
    alpha_ann: float
    """``periods x alpha`` (arithmetic, M0.4)."""
    alpha_se_ann: float
    """``periods x`` the HAC standard error of the intercept."""
    alpha_t: float
    """HAC t-statistic of the intercept (``alpha / se``; scale-free, so not annualised)."""
    alpha_p: float
    """Two-sided p-value of ``alpha_t`` against the normal distribution."""
    alpha_tag: Tag
    """``"reliable"`` when ``alpha_p < 0.05`` (the single-test rule of M3.2)."""
    rsquared: float
    rsquared_adj: float
    nobs: int
    """Rows of the fit; the same for every model of one comparison."""


@dataclass(frozen=True)
class ModelComparison:
    """The alpha strip: one row per model, all fitted on the same rows. Not ranked."""

    models: tuple[ModelAlpha, ...]
    nobs: int
    lags: int
    """Newey-West lag of every fit (``hac_lags(nobs)``)."""
    periods: int
    """Observations a year used to annualise (252 daily, 12 monthly)."""
    start: date
    end: date
    n_dropped: int
    """Sample rows left out because a model lacked a value on them (0 for a sample built on one
    factor frame, whose rows already have every factor)."""

    def by_model(self, model: str) -> ModelAlpha:
        """The row of ``model``; ``KeyError`` when it was not compared."""
        for row in self.models:
            if row.model == model:
                return row
        raise KeyError(model)


def _check_models(models: Sequence[str]) -> tuple[ModelName, ...]:
    out: list[ModelName] = []
    for m in models:
        if m not in MODELS:
            raise ValueError(f"unknown factor model {m!r}; known: {', '.join(MODEL_ORDER)}")
        if m in out:
            raise ValueError(f"model {m!r} is listed twice")
        out.append(m)
    if not out:
        raise ValueError("no model to compare")
    return tuple(out)


def compare_models(
    sample: AnalysisSample,
    periods: int | None = None,
    *,
    models: Sequence[str] = MODEL_ORDER,
) -> ModelComparison:
    """Alpha, its HAC t-statistic, R² and adjusted R² of each model on the same rows.

    ``models`` defaults to CAPM, FF3, FF5 and FF6; FF6 needs a sample built on the FF6 factor
    frame (``data.french.load_ff6``), else ``ValueError``. ``periods`` defaults to the sample's
    own (252 daily, 12 monthly) and any other value raises (``regression.resolve_periods``).
    Raises ``DegenerateInputError`` when a model's design is singular, and ``ValueError`` when
    there are no more common rows than the largest model has parameters.
    """
    periods = resolve_periods(sample, periods)
    names = _check_models(models)
    union: list[str] = []
    for m in names:
        union.extend(c for c in model_codes(m) if c not in union)
    factors = sample.factor_columns(union)
    y_all = sample.xret.to_numpy(dtype=np.float64)
    f_all = factors.to_numpy(dtype=np.float64)
    common = np.isfinite(y_all) & np.isfinite(f_all).all(axis=1)
    n = int(common.sum())
    if n == 0:
        raise ValueError("no row has the excess return and every factor of every model")
    y = y_all[common]
    lags = hac_lags(n)

    rows: list[ModelAlpha] = []
    for m in names:
        codes = model_codes(m)
        cols = [union.index(c) for c in codes]
        fit = ols_hac(y, f_all[common][:, cols], lags=lags, names=[DISPLAY_NAMES[c] for c in codes])
        a = float(fit.params[0])
        rows.append(
            ModelAlpha(
                model=m,
                label=MODEL_LABELS[m],
                codes=codes,
                alpha=a,
                alpha_ann=periods * a,
                alpha_se_ann=periods * float(fit.bse[0]),
                alpha_t=float(fit.zvalues[0]),
                alpha_p=float(fit.pvalues[0]),
                alpha_tag=alpha_tag(float(fit.pvalues[0])),
                rsquared=fit.rsquared,
                rsquared_adj=fit.rsquared_adj,
                nobs=fit.nobs,
            )
        )
    index = pd.DatetimeIndex(sample.xret.index)
    positions = np.flatnonzero(common)
    first, last = index[int(positions[0])], index[int(positions[-1])]
    return ModelComparison(
        models=tuple(rows),
        nobs=n,
        lags=lags,
        periods=periods,
        start=pd.Timestamp(first).date(),
        end=pd.Timestamp(last).date(),
        n_dropped=len(y_all) - n,
    )
