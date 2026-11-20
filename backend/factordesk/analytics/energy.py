"""Energy and carbon sensitivities: a separate regression on the market and the oil, gas and
carbon price legs (Sprint 3, item S3-8; measured in ``docs/research/energy-factor-spike.md``).

The excess return of the subject is regressed on

* ``mkt_rf``: the French market excess return, as in the headline model;
* ``oil``: the log return of the Brent spot price (FRED ``DCOILBRENTEU``);
* ``gas``: the log return of the Henry Hub spot price (FRED ``DHHNGSP``);
* ``co2``: KRBN total return minus RF (Yahoo; KRBN holds mainly EU carbon allowances).

Broad commodities (COMM) are not part of the model: they correlate +0.6 to +0.8 with oil and
would raise its VIF to about 3 for no gain (spike, section 2).

Two models, both with Newey-West errors (``regression.ols_hac``; the small-sample scaling and
Student-t for a monthly subject, as in the macro section):

* the long model on market, oil and gas, over the rows where the subject and those legs have a
  value;
* the carbon model on market, oil, gas and CO2, over the rows of the long model where KRBN also
  has a value. KRBN starts in July 2020, so it is a short sample. It is hidden when it has fewer
  than two years of rows (``MIN_CARBON_ROWS``).

No lag terms: the spike tested 20 and found none that matter.

Gas robustness. The Henry Hub return is extremely fat-tailed (excess kurtosis 115 daily): five
days hold 31% of the sum of squared gas returns. Each model is therefore fitted twice: on all
rows, and without the ``SPIKE_ROWS`` rows with the largest absolute gas return. The second gas
beta (with its t) is reported next to the first. Nothing is winsorised and no row is changed:
the five rows are left out of the second fit and the Newey-West lag chain is not re-spaced.

Timing is the macro rule: a daily leg return counts only when the leg's previous price date is the
subject's previous date; a missing price is never filled (a missing FRED day removes that day and
the next). A monthly regression compounds each leg to the month-end first.

Pure: no I/O, no clock. Inputs are not mutated.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
import pandas as pd
from numpy.typing import NDArray

from factordesk.analytics.macro import TooFewRowsError, leg_returns
from factordesk.analytics.regression import (
    Z_975,
    Tag,
    collinearity,
    ols_hac,
    significance_tags,
    t_975,
    two_sided_p,
    two_sided_t_p,
)
from factordesk.analytics.sample import AnalysisSample, DegenerateInputError, Frequency

FloatArray = NDArray[np.float64]

MIN_ROWS: dict[Frequency, int] = {"daily": 252, "monthly": 36}
"""Fewest rows of the long model: one trading year, or three years of months (as for macro)."""
MIN_CARBON_ROWS: dict[Frequency, int] = {"daily": 504, "monthly": 24}
"""Fewest rows of the carbon model: two years of trading days, or 24 months."""
SPIKE_ROWS = 5
"""Rows with the largest absolute gas return left out of the robustness fit (days or months)."""


@dataclass(frozen=True)
class EnergyFactor:
    """One column of the regression: its code, display name, plain label and definition."""

    code: str
    name: str
    label: str
    definition: str
    note: str | None = None


FACTORS: tuple[EnergyFactor, ...] = (
    EnergyFactor("mkt_rf", "Mkt-RF", "Market", "French market excess return"),
    EnergyFactor("oil", "OIL", "Oil", "log change of the Brent spot price (FRED DCOILBRENTEU)"),
    EnergyFactor(
        "gas",
        "GAS",
        "Natural gas",
        "log change of the Henry Hub spot price (FRED DHHNGSP)",
        "very large one-off moves",
    ),
    EnergyFactor(
        "co2",
        "CO2",
        "Carbon",
        "KRBN total return minus RF",
        "mainly EU carbon",
    ),
)
BY_CODE: dict[str, EnergyFactor] = {f.code: f for f in FACTORS}
LONG_CODES: tuple[str, ...] = ("mkt_rf", "oil", "gas")
CARBON_CODES: tuple[str, ...] = ("mkt_rf", "oil", "gas", "co2")
CARBON_TICKER = "KRBN"
"""The fund behind the carbon leg (Yahoo adjusted close)."""


# ----------------------------------------------------------------------------------- design
@dataclass(frozen=True)
class EnergyColumns:
    """The legs on the sample's rows. A leg with no value on a row holds NaN there."""

    dates: pd.DatetimeIndex
    y: FloatArray
    mkt: FloatArray
    oil: FloatArray
    gas: FloatArray
    co2: FloatArray
    """All NaN when KRBN prices are missing."""
    n_sample: int
    frequency: Frequency


def _log(returns: pd.Series, rows: pd.DatetimeIndex) -> FloatArray:
    """The log of one plus the simple returns on ``rows`` (NaN stays NaN)."""
    simple = returns.reindex(rows).to_numpy(dtype=np.float64)
    return np.asarray(np.log1p(simple), dtype=np.float64)


def build_columns(
    sample: AnalysisSample,
    calendar: pd.DatetimeIndex,
    oil_levels: pd.Series,
    gas_levels: pd.Series,
    carbon_levels: pd.Series | None,
) -> EnergyColumns:
    """The four legs on the sample's rows (``calendar`` is the subject's calendar, origin first).

    Oil and gas are log returns of the spot prices; CO2 is the simple KRBN return minus RF, NaN
    everywhere without KRBN prices. A non-positive price is a missing price.
    """
    freq = sample.frequency
    rows = pd.DatetimeIndex(sample.xret.index)
    rf = sample.rf.to_numpy(dtype=np.float64)
    if carbon_levels is None:
        co2 = np.full(len(rows), np.nan, dtype=np.float64)
    else:
        co2 = (
            leg_returns(carbon_levels, calendar, freq).reindex(rows).to_numpy(dtype=np.float64) - rf
        )
    return EnergyColumns(
        dates=rows,
        y=sample.xret.to_numpy(dtype=np.float64),
        mkt=sample.factors["mkt_rf"].to_numpy(dtype=np.float64),
        oil=_log(leg_returns(oil_levels, calendar, freq), rows),
        gas=_log(leg_returns(gas_levels, calendar, freq), rows),
        co2=co2,
        n_sample=sample.n,
        frequency=freq,
    )


@dataclass(frozen=True)
class EnergyDesign:
    """The rows of one model: only rows where the subject and every column have a value."""

    dates: pd.DatetimeIndex
    y: FloatArray
    codes: tuple[str, ...]
    x: FloatArray
    """One column per code."""
    frequency: Frequency

    @property
    def n(self) -> int:
        return len(self.dates)


def design_of(columns: EnergyColumns, codes: Sequence[str]) -> EnergyDesign:
    """The rows of ``columns`` where the subject and the legs named in ``codes`` are finite."""
    by_code: dict[str, FloatArray] = {
        "mkt_rf": columns.mkt,
        "oil": columns.oil,
        "gas": columns.gas,
        "co2": columns.co2,
    }
    x: FloatArray = np.column_stack([by_code[c] for c in codes]).astype(np.float64)
    keep = np.isfinite(columns.y) & np.isfinite(x).all(axis=1)
    return EnergyDesign(
        dates=pd.DatetimeIndex(columns.dates[np.flatnonzero(keep)]),
        y=columns.y[keep],
        codes=tuple(codes),
        x=x[keep],
        frequency=columns.frequency,
    )


# -------------------------------------------------------------------------------------- fit
@dataclass(frozen=True)
class EnergyRow:
    """One leg's result."""

    code: str
    beta: float
    se: float
    t: float
    p: float
    ci_low: float
    ci_high: float
    tag: Tag
    vif: float


@dataclass(frozen=True)
class GasRobust:
    """The gas beta of the model fitted without the rows of the largest absolute gas return."""

    beta: float
    se: float
    t: float
    p: float
    n_excluded: int
    excluded_dates: tuple[pd.Timestamp, ...]
    nobs: int


@dataclass(frozen=True)
class EnergyFit:
    rows: tuple[EnergyRow, ...]
    codes: tuple[str, ...]
    nobs: int
    lags: int
    r2: float
    adj_r2: float
    t_df: int | None
    """Student-t degrees of freedom (monthly); None for the normal reference."""
    gas_robust: GasRobust
    start: pd.Timestamp
    end: pd.Timestamp


def spike_positions(gas: FloatArray, count: int = SPIKE_ROWS) -> list[int]:
    """Positions of the ``count`` rows with the largest ``|gas|``, largest first (a tie goes to
    the earlier row)."""
    order = np.argsort(-np.abs(gas), kind="stable")
    return [int(i) for i in order[:count]]


def fit_energy(design: EnergyDesign, *, spike_rows: int = SPIKE_ROWS) -> EnergyFit:
    """OLS with Newey-West errors on the design, then the gas beta again without the
    ``spike_rows`` rows with the largest ``|gas|``.

    Raises ``DegenerateInputError`` on a singular design (``ols_hac``) and ``ValueError`` when
    too few rows are left for the second fit.
    """
    small = design.frequency == "monthly"
    names = [BY_CODE[c].name for c in design.codes]
    fit = ols_hac(design.y, design.x, names=names, small_sample=small)
    betas = [float(b) for b in fit.params[1:]]
    ses = [float(s) for s in fit.bse[1:]]
    z = np.asarray([b / s for b, s in zip(betas, ses, strict=True)], dtype=np.float64)
    pvals = two_sided_p(z) if fit.t_df is None else two_sided_t_p(z, fit.t_df)
    q = Z_975 if fit.t_df is None else t_975(fit.t_df)
    tags = significance_tags([float(p) for p in pvals])
    cc = collinearity(design.x, names)
    rows = tuple(
        EnergyRow(
            code=code,
            beta=betas[i],
            se=ses[i],
            t=float(z[i]),
            p=float(pvals[i]),
            ci_low=betas[i] - q * ses[i],
            ci_high=betas[i] + q * ses[i],
            tag=tags[i],
            vif=cc.vif[BY_CODE[code].name],
        )
        for i, code in enumerate(design.codes)
    )
    g = design.codes.index("gas")
    dropped = spike_positions(design.x[:, g], spike_rows)
    kept = np.ones(design.n, dtype=bool)
    kept[dropped] = False
    again = ols_hac(design.y[kept], design.x[kept], names=names, small_sample=small)
    gb, gs = float(again.params[1 + g]), float(again.bse[1 + g])
    gt = np.asarray([gb / gs], dtype=np.float64)
    gp = two_sided_p(gt) if again.t_df is None else two_sided_t_p(gt, again.t_df)
    robust = GasRobust(
        beta=gb,
        se=gs,
        t=float(gt[0]),
        p=float(gp[0]),
        n_excluded=len(dropped),
        excluded_dates=tuple(pd.Timestamp(design.dates[i]) for i in dropped),
        nobs=again.nobs,
    )
    return EnergyFit(
        rows=rows,
        codes=design.codes,
        nobs=fit.nobs,
        lags=fit.lags,
        r2=fit.rsquared,
        adj_r2=fit.rsquared_adj,
        t_df=fit.t_df,
        gas_robust=robust,
        start=pd.Timestamp(design.dates[0]),
        end=pd.Timestamp(design.dates[-1]),
    )


@dataclass(frozen=True)
class EnergyResult:
    """The long model, and the carbon model when it can be shown (else ``carbon_note`` says why)."""

    long_design: EnergyDesign
    long: EnergyFit
    carbon_design: EnergyDesign | None
    carbon: EnergyFit | None
    carbon_note: str | None
    n_sample: int


def _unit(frequency: Frequency) -> str:
    return "months" if frequency == "monthly" else "trading days"


def run_energy(
    sample: AnalysisSample,
    calendar: pd.DatetimeIndex,
    oil_levels: pd.Series,
    gas_levels: pd.Series,
    carbon_levels: pd.Series | None,
) -> EnergyResult:
    """Build the legs and fit both models.

    Raises ``TooFewRowsError`` when the long model has fewer than ``MIN_ROWS`` rows and
    ``DegenerateInputError`` when its design is singular. The carbon model never raises: with
    fewer than ``MIN_CARBON_ROWS`` rows, without KRBN prices or with a singular design it is left
    out and ``carbon_note`` says why.
    """
    cols = build_columns(sample, calendar, oil_levels, gas_levels, carbon_levels)
    long_design = design_of(cols, LONG_CODES)
    floor = MIN_ROWS[cols.frequency]
    if long_design.n < floor:
        raise TooFewRowsError(
            f"only {long_design.n} rows have a value for the subject, oil and gas; "
            f"at least {floor} are needed"
        )
    long_fit = fit_energy(long_design)
    carbon_design: EnergyDesign | None = None
    carbon_fit: EnergyFit | None = None
    note: str | None = None
    if carbon_levels is None:
        note = "The KRBN prices could not be fetched, so the carbon model is not shown."
    else:
        candidate = design_of(cols, CARBON_CODES)
        need = MIN_CARBON_ROWS[cols.frequency]
        if candidate.n < need:
            note = (
                f"The carbon model is hidden: this window holds only {candidate.n} "
                f"{_unit(cols.frequency)} of carbon data, and at least 2 years are needed."
            )
        else:
            try:
                carbon_fit = fit_energy(candidate)
                carbon_design = candidate
            except (DegenerateInputError, ValueError):  # never lose the long model to carbon
                note = "The carbon model could not be computed on this window."
    return EnergyResult(
        long_design=long_design,
        long=long_fit,
        carbon_design=carbon_design,
        carbon=carbon_fit,
        carbon_note=note,
        n_sample=cols.n_sample,
    )
