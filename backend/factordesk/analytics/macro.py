"""Macro sensitivities: a separate regression on market, rates, credit, commodity, inflation and
dollar factors (spec section "Factors", epic E4; research C2, C3, C4 and G3).

The excess return of the subject is regressed on

* ``mkt_rf``: the French market excess return, as in the headline model;
* ``term``: IEF minus RF (intermediate Treasuries over cash);
* ``def``: LQD minus IEF (credit minus rates, not duration-matched);
* ``comm``: DBC minus RF (broad commodities over cash);
* ``infl``: TIP minus IEI (TIPS over duration-matched Treasuries, a breakeven proxy);
* ``usd``: the simple return of the Fed nominal broad dollar index (FRED ``DTWEXBGS``); a
  positive beta means the subject gains when the dollar strengthens.

All are simple returns on the subject's dates. The betas are raw: the factors are correlated and
share explanatory power, so a single beta is not "the" exposure. This is not the headline model
and its intercept is not the headline alpha. VIF and the correlation matrix show the overlap.

Timing. A daily leg return counts only when the leg's previous price date is the subject's
previous date (so it spans the same interval; a missing price is never filled). The dollar index
is a noon New York fixing, while US funds close at 4 pm, so a daily regression adds the
previous day's dollar return and reports the summed dollar beta; its standard error is
``sqrt(v00 + v11 + 2 v01)`` from the HAC covariance. A monthly regression compounds each leg to
the month-end first (the month-end level over the previous month-end level), takes the spreads
from those compounded returns, and has no lag term.

Inference is ``regression.ols_hac`` (Newey-West; the small-sample scaling and Student-t for
monthly subjects). The tag is the Benjamini-Hochberg rule of the headline betas applied to the
factors of this regression. The window starts at the latest first date among the legs.

Pure: no I/O, no clock. Inputs are not mutated.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass

import numpy as np
import pandas as pd
from numpy.typing import NDArray

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
from factordesk.analytics.sample import AnalysisSample, Frequency

FloatArray = NDArray[np.float64]

LEG_TICKERS: tuple[str, ...] = ("IEF", "LQD", "DBC", "TIP", "IEI")
"""The funds behind the bond, credit, commodity and inflation factors (Yahoo adjusted close)."""
MIN_ROWS: dict[Frequency, int] = {"daily": 252, "monthly": 36}
"""Fewest rows of the regression: one trading year, or three years of months."""


class TooFewRowsError(ValueError):
    """Fewer rows than ``MIN_ROWS`` have a value for the subject and every factor."""


@dataclass(frozen=True)
class MacroFactor:
    """One factor of the regression: its code, display name, plain label and definition."""

    code: str
    name: str
    label: str
    definition: str
    note: str | None = None


FACTORS: tuple[MacroFactor, ...] = (
    MacroFactor("mkt_rf", "Mkt-RF", "Market", "French market excess return"),
    MacroFactor("term", "TERM", "Rates", "IEF minus RF"),
    MacroFactor(
        "def",
        "DEF",
        "Credit",
        "LQD minus IEF",
        "credit minus rates, not duration-matched",
    ),
    MacroFactor("comm", "COMM", "Commodities", "DBC minus RF"),
    MacroFactor("infl", "INFL", "Inflation", "TIP minus IEI", "breakeven proxy"),
    MacroFactor(
        "usd",
        "USD",
        "US dollar",
        "Fed nominal broad dollar index (FRED DTWEXBGS), simple return",
        "positive beta: gains when the dollar strengthens",
    ),
)
BY_CODE: dict[str, MacroFactor] = {f.code: f for f in FACTORS}
USD_LAG_NOTE = (
    "The index is a noon New York fixing, so a daily regression adds the previous day's return "
    "and reports the summed beta."
)


# ------------------------------------------------------------------------------ leg returns
def _previous_dates(index: pd.DatetimeIndex) -> pd.Series:
    """For every date but the first, the date of the row before it."""
    return pd.Series(index[:-1], index=index[1:])


def _clean_levels(levels: pd.Series) -> pd.Series:
    lv = levels.astype("float64")
    return lv.where(lv > 0)  # a zero or negative level is missing, as for prices (M1.3)


def daily_leg_returns(levels: pd.Series, calendar: pd.DatetimeIndex) -> pd.Series:
    """Simple daily returns of ``levels`` on ``calendar[1:]``, NaN where not comparable.

    A return on date ``t`` is kept only when the level series has a finite level at ``t`` and at
    its own previous row, and that previous row is dated ``calendar``'s previous date: the leg and
    the subject then span the same interval. A missing level is never filled.
    """
    lv = _clean_levels(levels)
    idx = pd.DatetimeIndex(lv.index)
    ret = lv / lv.shift(1) - 1.0
    target = pd.DatetimeIndex(calendar[1:])
    leg_prev = _previous_dates(idx).reindex(target)
    own_prev = _previous_dates(pd.DatetimeIndex(calendar)).reindex(target)
    same = (leg_prev == own_prev).to_numpy(dtype=bool)
    values = ret.reindex(target).to_numpy(dtype=np.float64)
    values = np.where(same, values, np.nan)
    return pd.Series(values, index=target, dtype="float64")


def monthly_leg_returns(levels: pd.Series, month_ends: pd.DatetimeIndex) -> pd.Series:
    """Compounded monthly returns of ``levels`` on ``month_ends``, NaN where not available.

    The return of month ``m`` is ``level(m) / level(m - 1) - 1``, the levels being the last finite
    ones inside each calendar month: the product of that month's daily returns. A month, or its
    previous month, without a level gives NaN (a fund's first, partial month is therefore left
    out). ``month_ends`` must be consecutive calendar month-ends for the previous-month rule.
    """
    lv = _clean_levels(levels).dropna()
    period = pd.DatetimeIndex(lv.index).to_period("M")
    last = lv.groupby(period).last()
    earlier = pd.Series(last.to_numpy(), index=last.index + 1)  # each level, one month later
    ret = last / earlier.reindex(last.index) - 1.0  # NaN where the previous month has no level
    wanted = pd.DatetimeIndex(month_ends).to_period("M")
    values = ret.reindex(wanted).to_numpy(dtype=np.float64)
    return pd.Series(values, index=pd.DatetimeIndex(month_ends), dtype="float64")


def leg_returns(levels: pd.Series, calendar: pd.DatetimeIndex, frequency: Frequency) -> pd.Series:
    """The return series of one leg on the subject's dates (daily or compounded monthly)."""
    if frequency == "monthly":
        return monthly_leg_returns(levels, pd.DatetimeIndex(calendar[1:]))
    return daily_leg_returns(levels, calendar)


# ----------------------------------------------------------------------------------- design
@dataclass(frozen=True)
class MacroDesign:
    """The aligned rows of the regression: only rows where every column has a value."""

    dates: pd.DatetimeIndex
    y: FloatArray
    """Excess return of the subject."""
    codes: tuple[str, ...]
    """Factor codes of the columns of ``x``, in ``FACTORS`` order (``usd`` last when present)."""
    x: FloatArray
    """One column per code (the dollar's same-day return)."""
    usd_lag: FloatArray | None
    """The previous day's dollar return (daily subjects with the dollar), else None."""
    n_sample: int
    """Rows of the analysis sample before the legs were required."""
    frequency: Frequency

    @property
    def n(self) -> int:
        return len(self.dates)


def build_design(
    sample: AnalysisSample,
    calendar: pd.DatetimeIndex,
    levels: Mapping[str, pd.Series],
    dollar: pd.Series | None,
) -> MacroDesign:
    """The factors on the sample's rows; ``levels`` holds the five fund price series.

    ``calendar`` is the subject's calendar (origin first). ``dollar`` is the index level series
    (NaN where FRED has no value) or None to run without it. Raises ``KeyError`` for a missing
    fund. The rows kept are those where the excess return and every column are finite.
    """
    freq = sample.frequency
    rets = {t: leg_returns(levels[t], calendar, freq) for t in LEG_TICKERS}
    rows = pd.DatetimeIndex(sample.xret.index)
    rf = sample.rf.to_numpy(dtype=np.float64)
    cols: dict[str, FloatArray] = {
        "mkt_rf": sample.factors["mkt_rf"].to_numpy(dtype=np.float64),
        "term": rets["IEF"].reindex(rows).to_numpy(dtype=np.float64) - rf,
        "def": rets["LQD"].reindex(rows).to_numpy(dtype=np.float64)
        - rets["IEF"].reindex(rows).to_numpy(dtype=np.float64),
        "comm": rets["DBC"].reindex(rows).to_numpy(dtype=np.float64) - rf,
        "infl": rets["TIP"].reindex(rows).to_numpy(dtype=np.float64)
        - rets["IEI"].reindex(rows).to_numpy(dtype=np.float64),
    }
    lag: FloatArray | None = None
    if dollar is not None:
        usd = leg_returns(dollar, calendar, freq)
        cols["usd"] = usd.reindex(rows).to_numpy(dtype=np.float64)
        if freq == "daily":
            previous = _previous_dates(pd.DatetimeIndex(calendar)).reindex(rows)
            lag = usd.reindex(pd.DatetimeIndex(previous)).to_numpy(dtype=np.float64)
    codes = tuple(f.code for f in FACTORS if f.code in cols)
    x: FloatArray = np.column_stack([cols[c] for c in codes]).astype(np.float64)
    y = sample.xret.to_numpy(dtype=np.float64)
    keep = np.isfinite(y) & np.isfinite(x).all(axis=1)
    if lag is not None:
        keep &= np.isfinite(lag)
    return MacroDesign(
        dates=pd.DatetimeIndex(rows[np.flatnonzero(keep)]),
        y=y[keep],
        codes=codes,
        x=x[keep],
        usd_lag=None if lag is None else lag[keep],
        n_sample=sample.n,
        frequency=freq,
    )


# -------------------------------------------------------------------------------------- fit
@dataclass(frozen=True)
class MacroRow:
    """One factor's result. The dollar row holds the summed same-day and lag beta (daily)."""

    code: str
    beta: float
    se: float
    t: float
    p: float
    ci_low: float
    ci_high: float
    tag: Tag
    vif: float
    beta_same_day: float | None = None
    beta_lag: float | None = None


@dataclass(frozen=True)
class MacroFit:
    rows: tuple[MacroRow, ...]
    codes: tuple[str, ...]
    nobs: int
    lags: int
    r2: float
    adj_r2: float
    t_df: int | None
    """Student-t degrees of freedom (monthly); None for the normal reference."""
    correlation: FloatArray
    """Correlation matrix of the factor columns, in ``codes`` order."""
    start: pd.Timestamp
    end: pd.Timestamp


def summed_beta(params: FloatArray, cov: FloatArray, i: int, j: int) -> tuple[float, float]:
    """``params[i] + params[j]`` and its standard error ``sqrt(v_ii + v_jj + 2 v_ij)``."""
    var = float(cov[i, i] + cov[j, j] + 2.0 * cov[i, j])
    return float(params[i] + params[j]), math.sqrt(max(var, 0.0))


def fit_macro(design: MacroDesign) -> MacroFit:
    """OLS with Newey-West errors on the design. Raises ``DegenerateInputError`` on a singular
    design (``ols_hac``) and ``ValueError`` with too few rows."""
    small = design.frequency == "monthly"
    x = design.x if design.usd_lag is None else np.column_stack([design.x, design.usd_lag])
    names = [BY_CODE[c].name for c in design.codes] + (
        [] if design.usd_lag is None else ["USD (previous day)"]
    )
    fit = ols_hac(design.y, x, names=names, small_sample=small)
    k = len(design.codes)
    betas = [float(b) for b in fit.params[1 : 1 + k]]
    ses = [float(s) for s in fit.bse[1 : 1 + k]]
    same_day: dict[str, float] = {}
    lag_part: dict[str, float] = {}
    if design.usd_lag is not None:
        u = 1 + design.codes.index("usd")
        lag_i = 1 + k
        total, se = summed_beta(fit.params, fit.cov, u, lag_i)
        betas[k - 1], ses[k - 1] = total, se
        same_day["usd"], lag_part["usd"] = float(fit.params[u]), float(fit.params[lag_i])
    t_stat = [b / s for b, s in zip(betas, ses, strict=True)]
    z = np.asarray(t_stat, dtype=np.float64)
    pvals = two_sided_p(z) if fit.t_df is None else two_sided_t_p(z, fit.t_df)
    q = Z_975 if fit.t_df is None else t_975(fit.t_df)
    tags = significance_tags([float(p) for p in pvals])
    cc = collinearity(design.x, [BY_CODE[c].name for c in design.codes])
    rows = tuple(
        MacroRow(
            code=code,
            beta=betas[i],
            se=ses[i],
            t=t_stat[i],
            p=float(pvals[i]),
            ci_low=betas[i] - q * ses[i],
            ci_high=betas[i] + q * ses[i],
            tag=tags[i],
            vif=cc.vif[BY_CODE[code].name],
            beta_same_day=same_day.get(code),
            beta_lag=lag_part.get(code),
        )
        for i, code in enumerate(design.codes)
    )
    assert cc.correlation is not None  # set by ``collinearity``: the matrix is computed once
    correlation = cc.correlation
    return MacroFit(
        rows=rows,
        codes=design.codes,
        nobs=fit.nobs,
        lags=fit.lags,
        r2=fit.rsquared,
        adj_r2=fit.rsquared_adj,
        t_df=fit.t_df,
        correlation=correlation,
        start=pd.Timestamp(design.dates[0]),
        end=pd.Timestamp(design.dates[-1]),
    )


def run_macro(
    sample: AnalysisSample,
    calendar: pd.DatetimeIndex,
    levels: Mapping[str, pd.Series],
    dollar: pd.Series | None,
) -> tuple[MacroDesign, MacroFit]:
    """Build the design and fit it. Raises ``TooFewRowsError`` when fewer than ``MIN_ROWS`` rows
    remain and ``DegenerateInputError`` when the design is singular."""
    design = build_design(sample, calendar, levels, dollar)
    floor = MIN_ROWS[design.frequency]
    if design.n < floor:
        raise TooFewRowsError(
            f"only {design.n} rows have a value for the subject and every macro factor; "
            f"at least {floor} are needed"
        )
    return design, fit_macro(design)
