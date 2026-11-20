"""Currency maths on return series: pure functions, no I/O (decision-reference-currency).

- ``convert(returns, fx_returns)``: a return in the asset's currency, measured in the reference
  currency: ``(1 + R)(1 + f) - 1``, where ``f`` is the return of one unit of the asset's currency
  in the reference currency over the same interval.
- ``hedge(returns, rf_local, cash_ref)``: a hedged return, ``R - rf_local + cash_ref`` (the
  asset's return above its own cash, plus cash of the reference currency).
- ``convert_series(...)``: ``convert`` plus the NaN policy. A date with no FX return is dropped
  from the subject and counted in the notice; a return is never filled. Equal currencies pass the
  series through untouched (no download, no copy of the values).

All series are decimals indexed by the interval end date.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class Converted:
    """A converted series, the number of dates dropped for lack of an FX return, and a notice."""

    returns: pd.Series
    dropped: int = 0
    notice: str | None = None


def convert(returns: pd.Series, fx_returns: pd.Series) -> pd.Series:
    """``(1 + R)(1 + f) - 1`` on the dates of ``returns``; NaN where ``f`` is missing."""
    f = fx_returns.reindex(returns.index)
    return ((1.0 + returns) * (1.0 + f) - 1.0).rename(returns.name)


def hedge(returns: pd.Series, rf_local: pd.Series, cash_ref: pd.Series) -> pd.Series:
    """``R - rf_local + cash_ref`` on the dates of ``returns``; NaN where a cash is missing."""
    local = rf_local.reindex(returns.index)
    ref = cash_ref.reindex(returns.index)
    return (returns - local + ref).rename(returns.name)


def convert_series(
    returns: pd.Series,
    from_ccy: str,
    to_ccy: str,
    fx_returns: Callable[[], pd.Series | None],
) -> Converted:
    """Convert ``returns`` from ``from_ccy`` to ``to_ccy``, dropping dates with no FX return.

    ``fx_returns`` is called only when the currencies differ. It returns the FX series or None
    (source down): ``ValueError`` is raised then, so the caller can answer 503 for the view.
    """
    if from_ccy.upper() == to_ccy.upper():
        return Converted(returns)
    fx = fx_returns()
    if fx is None:
        raise ValueError(f"no exchange rate from {from_ccy} to {to_ccy}")
    out = convert(returns, fx)
    missing = out.isna() & returns.notna()
    n = int(missing.sum())
    if n == 0:
        return Converted(out)
    notice = f"{n} dates had no {from_ccy}/{to_ccy} exchange rate and were dropped."
    return Converted(out[~missing], n, notice)
