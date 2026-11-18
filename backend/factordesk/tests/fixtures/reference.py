"""Typed wrappers around the statsmodels reference calls used as oracles in the tests.

statsmodels ships no type stubs; every untyped call is confined to this module. The HAC call
is exactly the reference call of methodology M0.5, with every option explicit.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import statsmodels.api as sm  # pyright: ignore[reportMissingTypeStubs]
from numpy.typing import NDArray
from statsmodels.regression.rolling import RollingOLS  # pyright: ignore[reportMissingTypeStubs]
from statsmodels.stats.outliers_influence import (  # pyright: ignore[reportMissingTypeStubs]
    variance_inflation_factor,  # pyright: ignore[reportUnknownVariableType]
)

FloatArray = NDArray[np.float64]

_sm: Any = sm
_rolling_ols: Any = RollingOLS
_vif: Any = variance_inflation_factor  # pyright: ignore[reportUnknownVariableType]


def _arr(x: Any) -> FloatArray:
    return np.asarray(x, dtype=np.float64)


def add_constant(f: FloatArray) -> FloatArray:
    """``sm.add_constant(F, has_constant="add")`` (constant first)."""
    return _arr(_sm.add_constant(np.asarray(f, dtype=np.float64), has_constant="add"))


@dataclass(frozen=True)
class RefFit:
    params: FloatArray
    bse: FloatArray
    pvalues: FloatArray
    conf_int: FloatArray
    cov: FloatArray
    rsquared: float
    rsquared_adj: float


def _fit(res: Any) -> RefFit:
    return RefFit(
        params=_arr(res.params),
        bse=_arr(res.bse),
        pvalues=_arr(res.pvalues),
        conf_int=_arr(res.conf_int()),
        cov=_arr(res.cov_params()),
        rsquared=float(res.rsquared),
        rsquared_adj=float(res.rsquared_adj),
    )


def hac_fit(y: FloatArray, f: FloatArray, lags: int) -> RefFit:
    """Reference HAC call of M0.5."""
    res = _sm.OLS(np.asarray(y, dtype=np.float64), add_constant(f)).fit(
        cov_type="HAC", cov_kwds={"maxlags": lags, "use_correction": False}, use_t=False
    )
    return _fit(res)


def ols_fit(y: FloatArray, f: FloatArray) -> RefFit:
    """Plain OLS with the default (nonrobust) covariance."""
    return _fit(_sm.OLS(np.asarray(y, dtype=np.float64), add_constant(f)).fit())


def rolling_params(y: FloatArray, f: FloatArray, window: int) -> FloatArray:
    """``RollingOLS(window=W)`` parameters, NaN before the first full window."""
    res = _rolling_ols(np.asarray(y, dtype=np.float64), add_constant(f), window=window).fit()
    return _arr(res.params)


def vif_with_constant(f: FloatArray, j: int) -> float:
    """``variance_inflation_factor`` on exog that includes the constant (factor ``j``)."""
    return float(_vif(add_constant(f), j + 1))


def hac_fit_missing_raise(y: FloatArray, f: FloatArray, lags: int) -> RefFit:
    """Reference HAC call of M0.5 with ``missing="raise"`` and the kernel named explicitly."""
    res = _sm.OLS(np.asarray(y, dtype=np.float64), add_constant(f), missing="raise").fit(
        cov_type="HAC",
        cov_kwds={"maxlags": lags, "kernel": "bartlett", "use_correction": False},
        use_t=False,
    )
    return _fit(res)


@dataclass(frozen=True)
class RefDiagnostics:
    acf1: float
    ljung_box_stat: float
    ljung_box_p: float
    arch_lm: float
    arch_lm_p: float
    jb_stat: float
    jb_p: float
    jb_skew: float
    jb_kurtosis: float
    durbin_watson: float
    robust_bg_stat: float
    robust_bg_p: float


def residual_reference(e: FloatArray, f: FloatArray, bg_lags: int = 10) -> RefDiagnostics:
    """Direct statsmodels calls for the M3.5 diagnostics (and an HC0 Wald for robust BG)."""
    from statsmodels.stats.diagnostic import (  # pyright: ignore[reportMissingTypeStubs]
        acorr_ljungbox,  # pyright: ignore[reportUnknownVariableType]
        het_arch,  # pyright: ignore[reportUnknownVariableType]
    )
    from statsmodels.stats.stattools import (  # pyright: ignore[reportMissingTypeStubs]
        durbin_watson,  # pyright: ignore[reportUnknownVariableType]
        jarque_bera,  # pyright: ignore[reportUnknownVariableType]
    )
    from statsmodels.tsa.stattools import (  # pyright: ignore[reportMissingTypeStubs]
        acf,  # pyright: ignore[reportUnknownVariableType]
    )

    _acf: Any = acf  # pyright: ignore[reportUnknownVariableType]
    _het_arch: Any = het_arch  # pyright: ignore[reportUnknownVariableType]

    ev = np.asarray(e, dtype=np.float64)
    fv = np.asarray(f, dtype=np.float64)
    lb: Any = acorr_ljungbox(ev, lags=[10], model_df=0)
    arch: Any = _het_arch(ev, nlags=5, result_object=True)
    jb: Any = jarque_bera(ev)
    a1: Any = _acf(ev, nlags=1, fft=False)
    n = len(ev)
    lagged = [ev[bg_lags - lag : n - lag] for lag in range(1, bg_lags + 1)]
    z = np.column_stack([np.ones(n - bg_lags), fv[bg_lags:], *lagged])
    aux: Any = _sm.OLS(ev[bg_lags:], z, missing="raise").fit(cov_type="HC0")
    r = np.zeros((bg_lags, z.shape[1]))
    r[:, -bg_lags:] = np.eye(bg_lags)
    wald: Any = aux.wald_test(r, scalar=True, use_f=False)
    return RefDiagnostics(
        acf1=float(a1[1]),
        ljung_box_stat=float(lb["lb_stat"].iloc[0]),
        ljung_box_p=float(lb["lb_pvalue"].iloc[0]),
        arch_lm=float(arch.lm),
        arch_lm_p=float(arch.lmpval),
        jb_stat=float(jb[0]),
        jb_p=float(jb[1]),
        jb_skew=float(jb[2]),
        jb_kurtosis=float(jb[3]),
        durbin_watson=float(durbin_watson(ev)),
        robust_bg_stat=float(wald.statistic),
        robust_bg_p=float(wald.pvalue),
    )
