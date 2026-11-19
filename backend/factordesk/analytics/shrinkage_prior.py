"""The reference prior of the shrunk betas: centre and method-of-moments spread (SB2).

Centre ``m0 = (1, 0, 0, 0, 0)``: a stock that behaves like the market portfolio. Spread ``tau`` is
the dispersion of true betas around ``m0`` across public Ken French portfolio cross-sections, by a
Vasicek-style method of moments (SB2.2):

1. window: the 2520 French rows ending at ``T_end``; a portfolio with any missing value in the
   window is dropped and counted;
2. per portfolio: excess return on the five factors, OLS with intercept, HAC with ``L(2520)``;
3. ``tau_c,j^2 = mean_i (b_ij - m0_j)^2 - mean_i V_i,jj``, per cross-section ``c``;
4. ``tau_j = max(tau_A,j, tau_B,j, 0.05)``, a negative raw value counting as 0 before the maximum.

Point-in-time: only rows dated ``<= T_end`` enter (SB2.3, TSB16, TSB17).

Pure: no I/O, no clock, no randomness. Inputs are not mutated.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Literal

import numpy as np
import pandas as pd
from numpy.typing import NDArray

from factordesk.analytics.regression import hac_lags, ols_hac
from factordesk.analytics.sample import FACTOR_CODES, FRENCH_COLUMNS, DegenerateInputError

FloatArray = NDArray[np.float64]

CENTRE: tuple[float, ...] = (1.0, 0.0, 0.0, 0.0, 0.0)
"""Prior centre: Mkt-RF 1, the style betas 0 (SB2.1)."""
TAU_FLOOR = 0.05
"""Smallest prior standard deviation: a degenerate cross-section cannot make it dogmatic."""
WINDOW_ROWS = 2520
"""French rows (about ten years) ending at ``T_end`` that the prior uses (SB2.2 step 1)."""
MIN_PORTFOLIOS = 40
"""Fewer usable portfolios than this in a cross-section: too small (SB7.1)."""

SOURCE_REFERENCE = "reference_ff_portfolios_v1"

CROSS_SECTIONS: dict[str, tuple[str, ...]] = {
    "industry49": ("ind49_daily",),
    "size_char75": ("me_bm25_daily", "me_op25_daily", "me_inv25_daily"),
}
"""Cross-section name -> dataset keys whose value-weighted columns make it up (SB2.2 table)."""


@dataclass(frozen=True)
class PortfolioFits:
    """Betas and HAC variances of the portfolios of one cross-section, in column order."""

    names: tuple[str, ...]
    betas: FloatArray
    """``(P, 5)``."""
    beta_var: FloatArray
    """``(P, 5)``: ``V_i,jj``, the HAC variance of each beta."""


@dataclass(frozen=True)
class PriorEstimate:
    """The prior and what it was built from (SB7.2 ``ShrinkagePrior``, minus the dataset stamps)."""

    source: Literal["reference_ff_portfolios_v1"]
    centre: FloatArray
    tau: FloatArray
    tau_by_cross_section: dict[str, FloatArray]
    """``sqrt(max(raw, 0))`` per cross-section, before the maximum and the floor."""
    n_portfolios: dict[str, int]
    n_dropped: dict[str, int]
    window_start: date
    window_end: date
    window_rows: int


@dataclass(frozen=True)
class PriorFailure:
    """The prior cannot be built (SB7.1)."""

    status: Literal["insufficient_data", "failed"]
    code: str
    message: str


def usable_columns(frame: pd.DataFrame, window_dates: pd.DatetimeIndex) -> tuple[pd.DataFrame, int]:
    """Portfolio columns with a value on every window date, and how many columns were dropped.

    Dates the portfolio file lacks count as missing, so a file that does not cover the window
    drops every column. Nothing is filled (CODING_STANDARDS section 3).
    """
    window = frame.reindex(window_dates)
    complete = ~window.isna().any(axis=0)
    kept = window.loc[:, complete.to_numpy(dtype=bool)]
    return kept, int(window.shape[1] - kept.shape[1])


def fit_portfolios(
    excess: pd.DataFrame, factors: FloatArray, lags: int | None = None
) -> PortfolioFits:
    """OLS with intercept and HAC on every column of ``excess`` against ``factors`` (SB2.2 step 2).

    ``lags`` defaults to ``L(rows)``. A column whose return does not vary has no usable
    regression and is left out. ``excess`` columns are excess returns, decimals.
    """
    rows = excess.shape[0]
    n_lags = hac_lags(rows) if lags is None else lags
    names: list[str] = []
    betas: list[FloatArray] = []
    variances: list[FloatArray] = []
    values = excess.to_numpy(dtype=np.float64)
    for i, name in enumerate(excess.columns):
        try:
            fit = ols_hac(values[:, i], factors, lags=n_lags)
        except DegenerateInputError:
            continue
        names.append(str(name))
        betas.append(fit.params[1:])
        variances.append(np.diag(fit.cov)[1:])
    k = factors.shape[1]
    return PortfolioFits(
        names=tuple(names),
        betas=np.array(betas, dtype=np.float64).reshape(len(names), k),
        beta_var=np.array(variances, dtype=np.float64).reshape(len(names), k),
    )


def raw_tau_squared(fits: PortfolioFits, centre: FloatArray) -> FloatArray:
    """``mean_i (b_ij - m0_j)^2 - mean_i V_i,jj`` per factor (SB2.2 step 3); may be negative."""
    spread: FloatArray = np.mean((fits.betas - centre) ** 2, axis=0)
    sampling: FloatArray = np.mean(fits.beta_var, axis=0)
    return spread - sampling


def combine_tau(
    raw: Sequence[FloatArray], floor: float = TAU_FLOOR
) -> tuple[FloatArray, list[FloatArray]]:
    """``tau = max over cross-sections of sqrt(max(raw, 0))``, raised to ``floor`` (SB2.2 step 4).

    Returns ``(tau, per_cross_section)`` where the second item holds each cross-section's
    ``sqrt(max(raw, 0))``.
    """
    per = [np.sqrt(np.maximum(np.asarray(r, dtype=np.float64), 0.0)) for r in raw]
    tau = np.maximum(np.max(np.vstack(per), axis=0), floor)
    return tau, per


def window_dates(factor_dates: pd.DatetimeIndex, t_end: date) -> pd.DatetimeIndex:
    """The ``WINDOW_ROWS`` factor dates ending at the last date ``<= t_end`` (fewer if the file is
    shorter). Only rows dated ``<= t_end`` are looked at."""
    upto = factor_dates[factor_dates <= pd.Timestamp(t_end)]
    return upto[-WINDOW_ROWS:]


def estimate_prior(
    factor_frame: pd.DataFrame,
    portfolios: Mapping[str, pd.DataFrame],
    t_end: date,
    *,
    cross_sections: Mapping[str, tuple[str, ...]] = CROSS_SECTIONS,
) -> PriorEstimate | PriorFailure:
    """The reference prior for a report ending at ``t_end`` (SB2.2, SB2.3).

    ``factor_frame`` is the French frame (``Mkt-RF`` ... ``RF``, decimals), ``portfolios`` the
    daily portfolio returns by dataset key (decimals, NaN for missing). Rows dated after ``t_end``
    are never read. Returns a ``PriorFailure`` when a dataset is missing
    (``prior_unavailable``) or the window or a cross-section is too small
    (``prior_cross_section_too_small``).
    """
    missing = sorted(
        key for keys in cross_sections.values() for key in keys if key not in portfolios
    )
    if missing:
        return PriorFailure(
            "failed",
            "prior_unavailable",
            "the Ken French portfolio files needed for the prior are not available "
            f"(missing: {', '.join(missing)})",
        )
    dates = window_dates(pd.DatetimeIndex(factor_frame.index), t_end)
    if len(dates) < WINDOW_ROWS:
        return PriorFailure(
            "insufficient_data",
            "prior_cross_section_too_small",
            f"only {len(dates)} factor rows end at {t_end}; the prior needs {WINDOW_ROWS}",
        )
    window = factor_frame.loc[dates]
    factors = window.loc[:, [c for c in FRENCH_COLUMNS if c != "RF"]].to_numpy(dtype=np.float64)
    if factors.shape[1] != len(FACTOR_CODES) or not bool(np.isfinite(factors).all()):
        return PriorFailure("failed", "prior_unavailable", "the factor window has missing values")
    rf = window["RF"].to_numpy(dtype=np.float64)
    centre = np.array(CENTRE, dtype=np.float64)

    raw: list[FloatArray] = []
    counts: dict[str, int] = {}
    dropped: dict[str, int] = {}
    for name, keys in cross_sections.items():
        usable: list[pd.DataFrame] = []
        n_dropped = 0
        for key in keys:
            kept, lost = usable_columns(portfolios[key], dates)
            usable.append(kept)
            n_dropped += lost
        counts[name] = sum(frame.shape[1] for frame in usable)
        dropped[name] = n_dropped
        if counts[name] < MIN_PORTFOLIOS:
            return PriorFailure(
                "insufficient_data",
                "prior_cross_section_too_small",
                f"only {counts[name]} usable portfolios in the {name} cross-section "
                f"({n_dropped} dropped for missing values); at least {MIN_PORTFOLIOS} are needed",
            )
        excess = pd.concat(usable, axis=1).sub(rf, axis=0)
        fits = fit_portfolios(excess, factors)
        counts[name] = len(fits.names)
        if counts[name] < MIN_PORTFOLIOS:
            return PriorFailure(
                "insufficient_data",
                "prior_cross_section_too_small",
                f"only {counts[name]} portfolios of the {name} cross-section could be fitted; "
                f"at least {MIN_PORTFOLIOS} are needed",
            )
        raw.append(raw_tau_squared(fits, centre))

    tau, per = combine_tau(raw)
    return PriorEstimate(
        source=SOURCE_REFERENCE,
        centre=centre,
        tau=tau,
        tau_by_cross_section=dict(zip(cross_sections, per, strict=True)),
        n_portfolios=counts,
        n_dropped=dropped,
        window_start=dates[0].date(),
        window_end=dates[-1].date(),
        window_rows=len(dates),
    )
