"""Residual analysis tests TR01-TR22, TR29-TR37 (``docs/test-oracle-residual-analysis.md``).

Targets ``analytics/residual.py``. Seeds follow oracle 0.1 (``rng_tr``). Schema, label and copy
tests (TR38, TR39) are in ``test_section_residual_alpha.py``; the stability tests (TR23-TR28) in
``test_residual_stability.py``; TR35 (static scan) covers both modules and lives here.
"""

from __future__ import annotations

import ast
import dataclasses
import math
from datetime import date, timedelta
from functools import cache
from pathlib import Path
from typing import Any, cast

import numpy as np
import pandas as pd
import pytest
from numpy.typing import NDArray
from statsmodels.stats.diagnostic import (  # pyright: ignore[reportMissingTypeStubs]
    acorr_ljungbox,  # pyright: ignore[reportUnknownVariableType]
    het_arch,  # pyright: ignore[reportUnknownVariableType]
)
from statsmodels.stats.stattools import (  # pyright: ignore[reportMissingTypeStubs]
    jarque_bera,  # pyright: ignore[reportUnknownVariableType]
)

from factordesk.analytics import residual as res_mod
from factordesk.analytics.diagnostics import residual_diagnostics
from factordesk.analytics.regression import A, ols_hac
from factordesk.analytics.residual import (
    ARCH_LAGS,
    FINDING_ARCH,
    FINDING_JB,
    FINDING_LB,
    LB_LAGS,
    central_moments,
    compound_path,
    decide_verdict,
    hac_location_test,
    in_sample_residual,
    noise_drawdown_reference,
    point_in_time_betas,
    series_diagnostics,
    summarise,
    verdict_message,
)
from factordesk.analytics.rolling import ex_ante_betas, rolling_betas
from factordesk.analytics.sample import FACTOR_CODES, build_sample
from factordesk.tests.fixtures.dgp import (
    dgp_a,
    factor_frame,
    price_history,
)
from factordesk.tests.fixtures.dgp_residual import (
    Analysis,
    analyse,
    analyse_sample,
    dgp_r0,
    dgp_rb,
    dgp_residual,
    dgp_rplus,
    dgp_rt,
    location_reference,
    rng_tr,
    with_constant,
)

FloatArray = NDArray[np.float64]
PACKAGE = Path(__file__).resolve().parents[1]
_ljungbox = cast(Any, acorr_ljungbox)
_het_arch = cast(Any, het_arch)
_jarque_bera = cast(Any, jarque_bera)


@cache
def _dgp_a(k: int, n: int = 2520, window: int = 252) -> Analysis:
    return analyse(dgp_a(rng_tr(k), n=n), window)


def _days(n: int) -> list[date]:
    return [date(2020, 1, 1) + timedelta(days=i) for i in range(n)]


def _rel(a: float, b: float) -> float:
    return abs(a - b) / abs(b)


def _y_f(a: Analysis) -> tuple[FloatArray, FloatArray]:
    y = a.sample.xret.to_numpy(dtype=np.float64)
    f = a.sample.factors.loc[:, list(FACTOR_CODES)].to_numpy(dtype=np.float64)
    return y, f


# ----------------------------------------------------------------------------- 1. in-sample
def test_tr01_residual_identities() -> None:
    a = _dgp_a(1)
    y, f = _y_f(a)
    u = a.result.u
    n = len(y)
    alpha_hat = a.reg.alpha
    e_hat = a.reg.fit.resid
    assert float(np.max(np.abs(u - (alpha_hat + e_hat)))) <= 1e-14
    assert abs(A * float(u.mean()) - a.reg.alpha_ann) <= 1e-10
    assert abs(float(u.sum()) - n * alpha_hat) <= 1e-10
    for i in range(5):
        assert abs(float(np.corrcoef(u, f[:, i])[0, 1])) <= 1e-10
    assert _rel(math.sqrt(A) * float(np.std(u, ddof=1)), a.reg.sigma_e_ann) <= 1e-12


def test_tr02_in_sample_statistics_are_the_regressions() -> None:
    a = _dgp_a(2)
    s, reg = a.result.in_sample, a.reg
    assert s.residual_return_annual == reg.alpha_ann
    assert s.residual_return_se_annual == reg.alpha_se_ann
    assert s.residual_return_ci_low_annual == reg.alpha_ci_ann[0]
    assert s.residual_return_ci_high_annual == reg.alpha_ci_ann[1]
    assert s.z == float(reg.fit.zvalues[0])
    assert s.p == float(reg.fit.pvalues[0])
    assert s.tag == reg.alpha_tag
    assert s.hac_lags == 8
    assert s.residual_vol_annual is not None and s.information_ratio is not None
    assert _rel(s.residual_vol_annual, reg.sigma_e_ann) <= 1e-12
    assert _rel(s.information_ratio, reg.alpha_ann / reg.sigma_e_ann) <= 1e-12


def _fbar_term(f: FloatArray) -> float:
    fbar = f.mean(axis=0)
    sigma_pop = np.cov(f.T, ddof=0)
    return float(fbar @ np.linalg.solve(sigma_pop, fbar))


def test_tr03_variance_factor_of_the_intercept() -> None:
    a = _dgp_a(3)
    _, f = _y_f(a)
    n = len(f)
    x = with_constant(f)
    inv = np.linalg.inv(x.T @ x)
    term = _fbar_term(f)
    assert term > 0
    assert _rel(float(inv[0, 0]), (1.0 + term) / n) <= 1e-10


def test_tr04_information_ratio_and_t_statistic() -> None:
    a = _dgp_a(4)
    y, f = _y_f(a)
    n = len(y)
    from factordesk.tests.fixtures.reference import ols_fit

    ref = ols_fit(y, f)
    z_ols = float(ref.params[0] / ref.bse[0])
    ir = a.result.in_sample.information_ratio
    assert ir is not None
    expected = (
        (ir / math.sqrt(A))
        * math.sqrt(n)
        * math.sqrt((n - 6) / (n - 1))
        / math.sqrt(1.0 + _fbar_term(f))
    )
    assert _rel(z_ols, expected) <= 1e-10


# ----------------------------------------------------------------------------- 2. cumulative
def _summ(x: list[float]) -> res_mod.ResidualSummary:
    xv = np.array(x, dtype=np.float64)
    return summarise(xv, _days(len(x)), hac_location_test(xv))


def test_tr05_hand_examples() -> None:
    d = _days(4)
    s = _summ([0.10, -0.10, 0.0, 0.2222222222222222])
    assert s.cumulative_return == pytest.approx(0.21, abs=1e-12)
    assert s.hit_rate == 0.5
    assert s.max_drawdown == pytest.approx(-0.1, abs=1e-12)
    assert (s.max_drawdown_peak, s.max_drawdown_trough, s.max_drawdown_recovery) == (
        d[0],
        d[1],
        d[3],
    )
    assert s.compound_growth_annual == pytest.approx(1.21**63 - 1.0, rel=1e-10)
    path = compound_path(np.array([0.10, -0.10, 0.0, 0.2222222222222222]))
    np.testing.assert_allclose(path.wealth, [1.1, 0.99, 0.99, 1.21], atol=1e-12)
    np.testing.assert_allclose(path.cumulative, [0.1, -0.01, -0.01, 0.21], atol=1e-12)

    b = _summ([-0.05, 0.02, 0.04])
    assert b.max_drawdown == pytest.approx(-0.05, abs=1e-12)
    assert b.max_drawdown_peak is None
    assert b.max_drawdown_trough == d[0] and b.max_drawdown_recovery == d[2]

    c = _summ([0.01, 0.02])
    assert c.max_drawdown == 0.0
    assert (c.max_drawdown_peak, c.max_drawdown_trough, c.max_drawdown_recovery) == (
        None,
        None,
        None,
    )

    dd = _summ([0.1, -0.2])
    assert dd.max_drawdown == pytest.approx(-0.2, abs=1e-12)
    assert (dd.max_drawdown_peak, dd.max_drawdown_trough, dd.max_drawdown_recovery) == (
        d[0],
        d[1],
        None,
    )

    e = _summ([0.1, 0.0, -0.1])
    assert e.max_drawdown_peak == d[1]
    assert e.max_drawdown == pytest.approx(-0.1, abs=1e-12)


def test_tr06_product_relation_anchors_and_rebasing() -> None:
    a = _dgp_a(6)
    r, w = a.result, 252
    u, ut = r.u, r.u_tilde
    assert ut is not None
    full = np.array(r.chart.in_sample_full)
    np.testing.assert_allclose(1.0 + full, np.cumprod(1.0 + u), rtol=1e-12, atol=0)
    assert abs(float(np.log1p(full[-1])) - float(np.sum(np.log1p(u)))) <= 1e-10
    ins, pit = r.chart.in_sample_compare, r.chart.point_in_time_compare
    assert all(v is None for v in ins[: w - 1]) and all(v is None for v in pit[: w - 1])
    assert ins[w - 1] == 0.0 and pit[w - 1] == 0.0
    assert all(v is not None for v in ins[w:]) and all(v is not None for v in pit[w:])
    assert r.chart.comparison_start == date(2010, 12, 21) == r.dates[w - 1]
    ins_v = np.array(ins[w:], dtype=np.float64)
    pit_v = np.array(pit[w:], dtype=np.float64)
    np.testing.assert_allclose(
        1.0 + ins_v, (1.0 + full[w:]) / (1.0 + full[w - 1]), rtol=1e-12, atol=0
    )
    np.testing.assert_allclose(1.0 + pit_v, np.cumprod(1.0 + ut[w:]), rtol=1e-12, atol=0)
    assert r.in_sample.cumulative_return == full[-1]
    assert r.point_in_time.cumulative_return == pit_v[-1]


def test_tr07_compounding_drag_inequality() -> None:
    r = _dgp_a(7).result
    assert r.u_tilde is not None
    for x, s in ((r.u, r.in_sample), (r.u_tilde[252:], r.point_in_time)):
        m = len(x)
        lhs = abs(
            A * float(np.mean(np.log1p(x))) - A * float(np.mean(x)) + 126 * float(np.mean(x**2))
        )
        bound = A * float(np.mean(np.abs(x) ** 3 / (3.0 * (1.0 - np.abs(x)) ** 3)))
        assert lhs <= bound + 1e-12
        assert s.residual_vol_annual is not None and s.compound_growth_annual is not None
        rhs = s.residual_vol_annual**2 * (m - 1) / (2 * m) + 126 * float(np.mean(x)) ** 2
        assert _rel(126 * float(np.mean(x**2)), rhs) <= 1e-12
        assert (
            _rel(1.0 + s.compound_growth_annual, math.exp(A * float(np.mean(np.log1p(x))))) <= 1e-12
        )


def test_tr08_annualisation_of_the_ratio_and_its_interval() -> None:
    r = _dgp_a(8).result
    assert r.u_tilde is not None
    for x, s in ((r.u, r.in_sample), (r.u_tilde[252:], r.point_in_time)):
        assert s.information_ratio is not None and s.residual_return_annual is not None
        assert s.residual_vol_annual is not None
        assert s.information_ratio_ci_low is not None and s.information_ratio_ci_high is not None
        assert s.residual_return_ci_low_annual is not None
        assert s.residual_return_ci_high_annual is not None
        direct = math.sqrt(A) * float(np.mean(x)) / float(np.std(x, ddof=1))
        assert (
            _rel(s.information_ratio, direct) <= 1e-12 or abs(s.information_ratio - direct) < 1e-12
        )
        assert _rel(s.information_ratio, s.residual_return_annual / s.residual_vol_annual) <= 1e-12
        assert (
            _rel(
                s.information_ratio_ci_low, s.residual_return_ci_low_annual / s.residual_vol_annual
            )
            <= 1e-12
        )
        assert (
            _rel(
                s.information_ratio_ci_high,
                s.residual_return_ci_high_annual / s.residual_vol_annual,
            )
            <= 1e-12
        )
    assert noise_drawdown_reference(0.25, 2520) == pytest.approx(-0.6287322670, abs=1e-9)


def test_tr09_skew_and_kurtosis() -> None:
    skew, kurt = central_moments(np.array([1.0, 2.0, 3.0, 10.0]))
    assert skew == pytest.approx(1.0182337649, abs=1e-9)
    assert kurt == pytest.approx(-0.7696, abs=1e-9)
    r = _dgp_a(9).result
    assert r.u_tilde is not None
    for x, s in ((r.u, r.in_sample), (r.u_tilde[252:], r.point_in_time)):
        jb = _jarque_bera(x)
        assert s.skew is not None and s.excess_kurtosis is not None
        assert abs(s.skew - float(jb[2])) <= 1e-12
        assert abs(s.excess_kurtosis - (float(jb[3]) - 3.0)) <= 1e-12


def test_tr10_wipe_out_rule() -> None:
    d = _days(3)
    x = np.array([0.1, -1.2, 0.05])
    path = compound_path(x)
    np.testing.assert_allclose(path.cumulative, [0.1, -1.0, -1.0], atol=1e-15)
    s = summarise(x, d, hac_location_test(x))
    assert s.wiped_out and s.wipe_out_date == d[1]
    assert s.compound_growth_annual == -1.0 and s.max_drawdown == -1.0
    assert s.residual_return_annual == pytest.approx(A * float(x.mean()), abs=1e-12)
    assert compound_path(np.array([-1.0, 0.1])).wipe_out == 0
    assert compound_path(np.array([-0.999, 0.1])).wipe_out is None


def test_tr11_excluded_rows_are_skipped_not_filled() -> None:
    d = dgp_a(rng_tr(11))
    hist = d.history
    frame = hist.frame.drop(hist.frame.index[[600, 1400, 2100]])
    hist2 = dataclasses.replace(hist, frame=frame)
    sample = build_sample(hist2, d.factors)
    assert [e.reason for e in sample.excluded] == ["multi_day_return"] * 3
    a = analyse_sample(sample)
    r = a.result
    assert r.dates == tuple(pd.Timestamp(t).date() for t in sample.xret.index)
    assert len(r.dates) == 2520 - 6
    assert r.chart.n_excluded_in_span == 3
    assert not np.any(r.u == 0.0)
    assert r.u_tilde is not None and not np.any(r.u_tilde[252:] == 0.0)
    np.testing.assert_allclose(
        np.array(r.chart.in_sample_full), np.cumprod(1.0 + r.u) - 1.0, rtol=1e-12, atol=0
    )


# ----------------------------------------------------------------------------- 3. point-in-time
@pytest.mark.parametrize("window", [126, 252, 504])
def test_tr12_exact_lag_and_window(window: int) -> None:
    a = _dgp_a(12, window=window)
    y, f = _y_f(a)
    n = len(y)
    ut = a.result.u_tilde
    assert ut is not None
    assert np.all(np.isnan(ut[:window])) and not np.any(np.isnan(ut[window:]))
    assert n - window == a.result.point_in_time.n
    rng = rng_tr(12)
    rows = rng.integers(window, n, size=5)  # 0-based index t' = row t - 1, window..n-1
    x = with_constant(f)
    bt = point_in_time_betas(a.rolling)
    for t in rows:
        lo, hi = int(t) - window, int(t)  # rows t-W .. t-1 (1-based) = indices lo .. hi-1
        coef = np.linalg.lstsq(x[lo:hi], y[lo:hi], rcond=None)[0]
        np.testing.assert_allclose(bt[t], coef[1:], rtol=1e-10, atol=1e-12)
        assert abs(ut[t] - (y[t] - bt[t] @ f[t])) <= 1e-12
    # Off-by-one guard: betas whose window contains day t give a different residual.
    wrong = y[window:] - np.einsum(
        "ij,ij->i", a.rolling.betas.to_numpy(dtype=np.float64)[window:], f[window:]
    )
    assert float(np.max(np.abs(ut[window:] - wrong))) > 1e-6
    np.testing.assert_array_equal(bt, ex_ante_betas(rolling_betas(a.sample, window)).to_numpy())


def _unattributed(a: Analysis) -> float:
    """``U = A mean(y) - sum Dyn_i`` over ``S_dyn`` of M6.3, from its definition."""
    y, f = _y_f(a)
    w = a.rolling.window
    bt = point_in_time_betas(a.rolling)[w:]
    dyn = A * (bt * f[w:]).mean(axis=0)
    return A * float(y[w:].mean()) - float(dyn.sum())


@pytest.mark.parametrize("window", [126, 252, 504])
def test_tr13_equals_the_tilt_timing_unattributed_row(window: int) -> None:
    a = _dgp_a(13, window=window)
    assert a.result.point_in_time.residual_return_annual is not None
    assert abs(a.result.point_in_time.residual_return_annual - _unattributed(a)) <= 1e-10


def test_tr14_hac_reference_calls_and_gap_construction() -> None:
    a = _dgp_a(14)
    r = a.result
    ut = r.u_tilde
    assert ut is not None
    span = ut[252:]
    m = len(span)
    assert m == 2268
    mean, se, p = location_reference(span, 8)
    s = r.point_in_time
    assert s.residual_return_se_annual is not None and s.z is not None and s.p is not None
    assert _rel(s.residual_return_se_annual / A, se) <= 1e-10
    assert _rel(s.z, mean / se) <= 1e-10 and _rel(s.p, p) <= 1e-10
    assert s.hac_lags == 8
    gap = r.u[252:] - span
    g = r.gap
    assert g.status == "ok" and g.gap_annual is not None
    assert g.in_sample_same_days_annual is not None and g.point_in_time_annual is not None
    assert abs(g.gap_annual - (g.in_sample_same_days_annual - g.point_in_time_annual)) <= 1e-12
    gm, gse, gp = location_reference(gap, 8)
    assert g.gap_se_annual is not None and g.gap_z is not None and g.gap_p is not None
    assert _rel(g.gap_se_annual / A, gse) <= 1e-10
    assert _rel(g.gap_z, gm / gse) <= 1e-10 and _rel(g.gap_p, gp) <= 1e-10
    assert abs(g.in_sample_same_days_annual - A * float(r.u[252:].mean())) <= 1e-12
    assert g.in_sample_same_days_annual != a.reg.alpha_ann


def _perturbed_analysis() -> tuple[Analysis, Analysis, int]:
    from factordesk.tests.test_lookahead import (
        T_STAR,
        _perturbed,  # pyright: ignore[reportPrivateUsage]
    )

    hist, fac, hist2, fac2 = _perturbed(False)
    return (
        analyse_sample(build_sample(hist, fac)),
        analyse_sample(build_sample(hist2, fac2)),
        T_STAR,
    )


def test_tr15a_perturbation_after_t_star() -> None:
    a, b, t_star = _perturbed_analysis()
    w = 252
    ba, bb = point_in_time_betas(a.rolling), point_in_time_betas(b.rolling)
    # beta_tilde for rows up to t*+1 uses rows <= t* only.
    np.testing.assert_allclose(ba[: t_star + 1], bb[: t_star + 1], atol=1e-12, rtol=0)
    ua, ub = a.result.u_tilde, b.result.u_tilde
    assert ua is not None and ub is not None
    np.testing.assert_allclose(ua[:t_star], ub[:t_star], atol=1e-12, rtol=0, equal_nan=True)
    ca = np.array(a.result.chart.point_in_time_compare[:t_star], dtype=np.float64)
    cb = np.array(b.result.chart.point_in_time_compare[:t_star], dtype=np.float64)
    np.testing.assert_allclose(ca, cb, atol=1e-12, rtol=0, equal_nan=True)
    for attr in ("alpha", "alpha_se"):
        np.testing.assert_allclose(
            getattr(a.rolling, attr).to_numpy()[:t_star],
            getattr(b.rolling, attr).to_numpy()[:t_star],
            atol=1e-12,
            rtol=0,
            equal_nan=True,
        )
    # Teeth: day t*+1 itself and the in-sample series do change.
    assert abs(ua[t_star] - ub[t_star]) > 1e-6
    assert abs(a.result.u[0] - b.result.u[0]) > 1e-8
    assert w == a.rolling.window


def test_tr15b_row_change() -> None:
    a = _dgp_a(15)
    y, f = _y_f(a)
    row = 1499  # row 1500
    xret = a.sample.xret.copy()
    factors = a.sample.factors.copy()
    xret.iloc[row] *= 10.0
    factors.iloc[row] = factors.iloc[row] * 10.0
    b = analyse_sample(dataclasses.replace(a.sample, xret=xret, factors=factors))
    bta, btb = point_in_time_betas(a.rolling), point_in_time_betas(b.rolling)
    np.testing.assert_array_equal(bta[row], btb[row])
    assert a.result.u_tilde is not None and b.result.u_tilde is not None
    np.testing.assert_array_equal(a.result.u_tilde[:row], b.result.u_tilde[:row])
    y2, f2 = y.copy(), f.copy()
    y2[row] *= 10.0
    f2[row] *= 10.0
    assert abs(b.result.u_tilde[row] - (y2[row] - btb[row] @ f2[row])) <= 1e-12


def test_tr15c_truncation() -> None:
    d = dgp_a(rng_tr(15))
    t_star = 1800
    full = analyse(d)
    hist = dataclasses.replace(d.history, frame=d.history.frame.iloc[: t_star + 1])
    trunc = analyse_sample(build_sample(hist, d.factors.iloc[:t_star]))
    assert trunc.sample.end == full.sample.xret.index[t_star - 1].date()
    uf, ut = full.result.u_tilde, trunc.result.u_tilde
    assert uf is not None and ut is not None
    np.testing.assert_allclose(uf[:t_star], ut, atol=1e-12, rtol=0, equal_nan=True)
    assert full.result.chart.comparison_start == trunc.result.chart.comparison_start
    cf = np.array(full.result.chart.point_in_time_compare[:t_star], dtype=np.float64)
    ct = np.array(trunc.result.chart.point_in_time_compare, dtype=np.float64)
    np.testing.assert_allclose(cf, ct, atol=1e-12, rtol=0, equal_nan=True)
    assert trunc.result.dates[-1] == trunc.sample.end


def test_tr16_warmup_and_short_history() -> None:
    a = _dgp_a(16, n=504)
    assert a.result.point_in_time.status == "ok"
    assert a.result.point_in_time.n == 252 and a.result.point_in_time.hac_lags == 4
    assert _dgp_a(16, n=504, window=126).result.point_in_time.n == 378

    b = _dgp_a(16, n=755, window=504)
    r = b.result
    pit = r.point_in_time
    assert pit.status == "insufficient_data"
    assert (
        pit.reason == "Point-in-time residual needs at least 756 trading days; this period has 755."
    )
    assert pit.residual_return_annual is None and pit.z is None and pit.hac_lags is None
    assert all(v is None for v in r.chart.in_sample_compare + r.chart.point_in_time_compare)
    assert r.chart.comparison_start is None and len(r.chart.in_sample_full) == 755
    assert r.gap.status == "insufficient_data" and r.gap.verdict is None
    assert r.diagnostics_point_in_time.status == "insufficient_data"
    assert r.in_sample.status == "ok" and r.diagnostics_in_sample.status == "ok"

    c = _dgp_a(16, n=756, window=504)
    assert c.result.point_in_time.status == "ok" and c.result.point_in_time.n == 252


@pytest.mark.parametrize(
    ("case", "inputs", "expected", "severity"),
    [
        (1, (0.125, 0.20, 0.125, 0.0625, 0.30), "no_reliable_alpha", "info"),
        (2, (0.125, 0.20, 0.125, 0.0625, 0.01), "point_in_time_only", "info"),
        (3, (0.125, 0.05, 0.125, 0.125, 0.01), "point_in_time_only", "info"),
        (4, (0.125, 0.01, 0.0625 - 2**-20, 0.0625, 0.01), "concentrated_in_warmup", "info"),
        (5, (0.125, 0.01, -0.03125, 0.0625, 0.01), "concentrated_in_warmup", "info"),
        (6, (0.125, 0.01, 0.0, 0.0625, 0.01), "concentrated_in_warmup", "info"),
        (7, (0.125, 0.01, 0.0625, -0.0078125, 0.60), "reversed", "warning"),
        (8, (0.125, 0.01, 0.125, 0.0625 - 2**-20, 0.30), "mostly_disappears", "warning"),
        (9, (0.125, 0.01, 0.125, 0.0625, 0.30), "survives_not_significant", "info"),
        (10, (0.125, 0.01, 0.125, 0.109375, 0.01), "survives", "info"),
        (11, (-0.125, 0.01, -0.125, -0.109375, 0.01), "survives", "info"),
        (12, (0.125, 0.01, 0.125, 0.0625, 0.05), "survives_not_significant", "info"),
    ],
)
def test_tr17_verdict_decision_table(
    case: int, inputs: tuple[float, float, float, float, float], expected: str, severity: str
) -> None:
    v = decide_verdict(*inputs)
    assert (v.code, v.severity) == (expected, severity), case
    if case == 6:
        assert v.survival_ratio is None


def test_tr18_verdict_copy() -> None:
    dates = [date(2010, 1, 4), date(2010, 12, 21)]
    kw: dict[str, Any] = {"window": 252, "warmup_start": dates[0], "warmup_end": dates[1]}
    assert verdict_message(
        "mostly_disappears", a_c=0.04, a_pit=0.018, survival_ratio=0.018 / 0.04, **kw
    ) == (
        "In-sample alpha mostly disappears out-of-sample: point-in-time betas keep 45% of it "
        "(+1.8% a year against +4.0% on the same days)."
    )
    assert verdict_message(
        "point_in_time_only", a_c=0.0, a_pit=-0.052, survival_ratio=None, **kw
    ) == (
        "The point-in-time residual return is reliably negative (-5.2% a year), but the "
        "full-period alpha is not. This usually means the betas moved; check the Exposures section."
    )
    assert "(more than 200% kept)" in verdict_message(
        "survives", a_c=0.04, a_pit=0.1, survival_ratio=2.5, **kw
    )
    g3 = verdict_message("concentrated_in_warmup", a_c=0.0, a_pit=0.0, survival_ratio=None, **kw)
    assert "the first 252 trading days (2010-01-04 to 2010-12-21)" in g3
    a = _dgp_a(18)
    assert a.result.dates[0] == dates[0] and a.result.dates[251] == dates[1]
    for text in (
        verdict_message("survives", a_c=0.1, a_pit=0.09, survival_ratio=0.9, **kw),
        verdict_message("survives_not_significant", a_c=0.1, a_pit=0.09, survival_ratio=0.9, **kw),
    ):
        assert "survive" not in text  # owner decision 4: "holds up out-of-sample"


# ----------------------------------------------------------------------------- 4. known truth
def test_tr19_strong_stable_alpha_holds_up() -> None:
    a = analyse(dgp_rplus(rng_tr(19)))
    r, reg = a.result, a.reg
    s, p = r.in_sample, r.point_in_time
    assert abs(reg.alpha_ann - 0.3024) <= 4 * reg.alpha_se_ann
    assert p.residual_return_annual is not None and p.residual_return_se_annual is not None
    assert abs(p.residual_return_annual - 0.3024) <= 4 * p.residual_return_se_annual
    assert r.gap.verdict == "survives"
    assert r.gap.survival_ratio is not None and 0.85 <= r.gap.survival_ratio <= 1.15
    assert s.residual_vol_annual is not None and p.residual_vol_annual is not None
    ratio = p.residual_vol_annual / s.residual_vol_annual
    assert 0.989 <= ratio <= 1.033
    assert abs(p.residual_vol_annual - 0.12825) <= 0.0076
    assert r.gap.gap_annual is not None and abs(r.gap.gap_annual) <= 0.03


def test_tr20_zero_alpha_fixed_seed() -> None:
    a = analyse(dgp_r0(rng_tr(20)))
    r = a.result
    assert r.point_in_time.z is not None and abs(r.point_in_time.z) <= 4
    assert abs(float(r.u.sum()) - len(r.u) * a.reg.alpha) <= 1e-10
    assert r.chart.in_sample_full[-1] != 0.0


@pytest.mark.slow
def test_tr20_zero_alpha_monte_carlo() -> None:
    reps = 1000
    pit_rej = is_rej = big = surv = bad = 0
    gaps: list[float] = []
    for rep in range(reps):
        a = analyse(dgp_r0(rng_tr(20, rep)))
        r = a.result
        assert r.point_in_time.p is not None and r.gap.gap_annual is not None
        pit_rej += r.point_in_time.p < 0.05
        is_rej += a.reg.alpha_tag == "reliable"
        big += abs(a.reg.alpha_ann) >= 0.03
        surv += r.gap.verdict == "survives"
        bad += r.gap.verdict in ("reversed", "mostly_disappears")
        gaps.append(r.gap.gap_annual)
    assert 0.026 <= pit_rej / reps <= 0.074
    assert 0.026 <= is_rej / reps <= 0.074
    assert 0.564 <= big / reps <= 0.672
    assert 0.013 <= surv / reps <= 0.074
    assert bad <= 5
    assert 0.0070 <= float(np.std(gaps, ddof=1)) <= 0.0105


def _exposure_slope(a: Analysis, series: FloatArray, lo: int, hi: int) -> tuple[float, float]:
    """Market slope of ``series[lo:hi]`` on ``[1, F]`` with HAC ``L(hi - lo)`` (TR21)."""
    _, f = _y_f(a)
    fit = ols_hac(series[lo:hi], f[lo:hi])
    return float(fit.params[1]), float(fit.bse[1])


def test_tr21_structural_break() -> None:
    a = analyse(dgp_rb(rng_tr(21)))
    r = a.result
    assert r.u_tilde is not None
    assert 0.90 <= float(a.reg.betas[0]) <= 1.10
    for lo, hi, sign in ((1512, 2520, 1.0), (252, 1260, -1.0)):
        c, se = _exposure_slope(a, r.u, lo, hi)
        assert 0.35 <= sign * c <= 0.65
        assert sign * c / se >= 8
        cp, sep = _exposure_slope(a, r.u_tilde, lo, hi)
        assert abs(cp) <= 4 * sep
    assert float(np.std(r.u_tilde[1512:], ddof=1) / np.std(r.u[1512:], ddof=1)) <= 0.93


def test_tr22_hindsight_alpha_disappears() -> None:
    a = analyse(dgp_rt(rng_tr(22)))
    r = a.result
    assert a.reg.alpha_tag == "reliable"
    assert r.gap.verdict in {"mostly_disappears", "reversed"}
    assert r.gap.survival_ratio is not None and r.gap.survival_ratio < 0.5
    assert r.u_tilde is not None
    x = np.concatenate([r.u_tilde[252:1260], r.u_tilde[1512:]])
    assert abs(hac_location_test(x).z) <= 4


# ----------------------------------------------------------------------------- 6. avoid list
def test_tr29_uncovered_tail() -> None:
    d = dgp_a(rng_tr(29), n=2550)
    last = d.factors.index[2519]
    fac = d.factors.iloc[:2520]
    full = analyse_sample(build_sample(d.history, fac))
    cut = dataclasses.replace(d.history, frame=d.history.frame.iloc[:2521])
    clean = analyse_sample(build_sample(cut, fac))
    rf, rc = full.result, clean.result
    assert rf.dates[-1] == pd.Timestamp(last).date()
    assert rf.chart.n_uncovered == 30
    assert (
        rf.chart.uncovered_from == pd.Timestamp(d.factors.index[2519] + pd.offsets.BDay(1)).date()
    )
    assert rc.chart.n_uncovered == 0 and rc.chart.uncovered_from is None
    np.testing.assert_array_equal(rf.u, rc.u)
    assert rf.u_tilde is not None and rc.u_tilde is not None
    np.testing.assert_array_equal(rf.u_tilde, rc.u_tilde)
    assert rf.in_sample == rc.in_sample and rf.point_in_time == rc.point_in_time
    assert rf.chart.in_sample_full == rc.chart.in_sample_full
    assert rf.gap == rc.gap


def test_tr30_no_fill_with_zero() -> None:
    d = dgp_a(rng_tr(30))
    clean = build_sample(d.history, d.factors)
    frame = d.history.frame.copy()
    for pos in (300, 900, 1500):
        frame.loc[frame.index[pos], "adj_close"] = np.nan
    fac = d.factors.copy()
    for pos, col in ((400, "HML"), (1100, "Mkt-RF"), (2000, "RF")):
        fac.loc[fac.index[pos], col] = np.nan
    s = build_sample(dataclasses.replace(d.history, frame=frame), fac)
    a = analyse_sample(s)
    removed = clean.xret.index.difference(s.xret.index)
    keep = ~clean.xret.index.isin(removed)
    reduced = dataclasses.replace(
        clean,
        xret=clean.xret[keep],
        ret=clean.ret[keep],
        rf=clean.rf[keep],
        factors=clean.factors[keep],
    )
    b = analyse_sample(reduced)
    assert len(removed) > 0
    y = s.xret.to_numpy(dtype=np.float64)
    assert not np.any(a.result.u == y)
    np.testing.assert_allclose(a.result.u, b.result.u, atol=1e-10, rtol=0)
    assert a.result.u_tilde is not None and b.result.u_tilde is not None
    np.testing.assert_allclose(
        a.result.u_tilde, b.result.u_tilde, atol=1e-10, rtol=0, equal_nan=True
    )
    bad = np.array([0.01, np.nan, 0.02])
    with pytest.raises(ValueError, match="finite"):
        in_sample_residual(bad, np.ones((3, 5)), np.ones(5))
    with pytest.raises(ValueError, match="finite"):
        in_sample_residual(np.ones(3), np.full((3, 5), np.nan), np.ones(5))


def test_tr31_rf_is_subtracted() -> None:
    n = 2520
    d = dgp_residual(rng_tr(31), n, alpha=0.0, sigma_e=0.0024, rf=np.full(n, 0.0004))
    a = analyse(d)
    _, f = _y_f(a)
    expected = (a.sample.ret.to_numpy() - 0.0004) - f @ a.reg.betas
    assert float(np.max(np.abs(a.result.u - expected))) <= 1e-15
    assert a.result.in_sample.z is not None and abs(a.result.in_sample.z) <= 4
    assert a.result.point_in_time.z is not None and abs(a.result.point_in_time.z) <= 4


def test_tr32_off_by_one_windows() -> None:
    from factordesk.analytics.residual_stability import non_overlapping_alpha

    a = _dgp_a(32)
    n = a.sample.n
    index = a.sample.xret.index
    for window in (126, 252, 504):
        rb = rolling_betas(a.sample, window)
        starts = rb.window_start
        for i in range(window - 1, n, 97):
            assert starts.iloc[i] == index[i - window + 1]
            assert (i - (i - window + 1) + 1) == window
        # The point-in-time betas of row t are the stamp t-1, window ending on t-1.
        bt = point_in_time_betas(rb)
        np.testing.assert_array_equal(bt[window], rb.betas.to_numpy()[window - 1])
    dates = [t.date() for t in index]
    no = non_overlapping_alpha(a.rolling, dates)
    ends = [dates.index(w.end) for w in no.windows]
    assert all(w.n == 252 for w in no.windows)
    assert all(dates.index(w.end) - dates.index(w.start) + 1 == 252 for w in no.windows)
    assert all(e1 - e2 == 252 for e1, e2 in zip(ends, ends[1:], strict=False))


def test_tr33_compounded_and_arithmetic_values_are_not_mixed() -> None:
    from factordesk.analytics.residual_stability import calendar_years

    a = _dgp_a(33)
    r = a.result
    years = calendar_years(r.dates, r.u, r.u_tilde)
    assert abs(sum(y.in_sample_sum for y in years) - len(r.u) * a.reg.alpha) <= 1e-10
    ys = np.array([d.year for d in r.dates])
    compounded = sum(float(np.prod(1.0 + r.u[ys == y]) - 1.0) for y in sorted(set(ys)))
    total = float(np.prod(1.0 + r.u) - 1.0)
    assert abs(compounded - total) > 1e-6
    s = r.in_sample
    assert s.residual_return_annual is not None and s.compound_growth_annual is not None
    assert s.residual_return_annual - s.compound_growth_annual > 1e-3


def test_tr34_extreme_rows_kept() -> None:
    d = dgp_a(rng_tr(34))
    ret = d.ret.copy()
    ret[1499] += 0.60
    hist = price_history(ret, d.dates)
    sample = build_sample(hist, factor_frame(d.f, d.rf, d.dates))
    a = analyse_sample(sample)
    y, f = _y_f(a)
    r = a.result
    assert sample.n == 2520
    assert abs(r.u[1499] - (y[1499] - a.reg.betas @ f[1499])) <= 1e-12
    assert r.u_tilde is not None
    bt = point_in_time_betas(a.rolling)
    assert abs(r.u_tilde[1499] - (y[1499] - bt[1499] @ f[1499])) <= 1e-12
    assert r.u[1499] > 0.5
    full = np.array(r.chart.in_sample_full)
    assert abs((1 + full[1499]) / (1 + full[1498]) - 1.0 - r.u[1499]) <= 1e-12
    assert r.in_sample.hit_rate == float(np.count_nonzero(r.u > 0)) / len(r.u)


def test_tr35_static_scan() -> None:
    problems: list[str] = []
    for name in ("residual.py", "residual_stability.py"):
        tree = ast.parse((PACKAGE / "analytics" / name).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
                continue
            attr = node.func.attr
            if attr in {"fillna", "dropna", "clip", "nan_to_num"}:
                problems.append(f"{name}:{node.lineno} {attr}")
            if attr == "shift":
                first = node.args[0] if node.args else None
                if not (isinstance(first, ast.Constant) and first.value == 1):
                    problems.append(f"{name}:{node.lineno} shift")
    assert problems == []


# ----------------------------------------------------------------------------- 7. diagnostics
def test_tr36_reference_calls_and_demeaning() -> None:
    a = analyse(dgp_rplus(rng_tr(36)))
    r = a.result
    e_hat = a.reg.fit.resid
    d = r.diagnostics_in_sample
    lb = _ljungbox(e_hat, lags=[10], return_df=True)
    jb = _jarque_bera(e_hat)
    arch = _het_arch(e_hat, nlags=5, ddof=0, store=False, result_object=True)
    assert d.ljung_box_stat is not None and d.ljung_box_p is not None
    assert d.jarque_bera_stat is not None and d.jarque_bera_p is not None
    assert d.arch_lm_stat is not None and d.arch_lm_p is not None
    assert _rel(d.ljung_box_stat, float(lb["lb_stat"].iloc[0])) <= 1e-12
    assert _rel(d.ljung_box_p, float(lb["lb_pvalue"].iloc[0])) <= 1e-12
    assert _rel(d.jarque_bera_stat, float(jb[0])) <= 1e-12
    assert _rel(d.jarque_bera_p, float(jb[1])) <= 1e-12
    assert _rel(d.arch_lm_stat, float(arch.lm)) <= 1e-12
    assert _rel(d.arch_lm_p, float(arch.lmpval)) <= 1e-12
    _, f = _y_f(a)
    m35 = residual_diagnostics(e_hat, f)
    assert _rel(d.ljung_box_stat, m35.ljung_box.statistic) <= 1e-12
    assert _rel(d.jarque_bera_stat, m35.jarque_bera.statistic) <= 1e-12
    assert (LB_LAGS, ARCH_LAGS) == (10, 5)

    assert r.u_tilde is not None
    span = r.u_tilde[252:]
    dm = span - span.mean()
    p = r.diagnostics_point_in_time
    arch_p = _het_arch(dm, nlags=5, ddof=0, store=False, result_object=True)
    raw = _het_arch(span, nlags=5, ddof=0, store=False, result_object=True)
    lb_p = _ljungbox(dm, lags=[10], return_df=True)
    assert p.arch_lm_stat is not None and p.ljung_box_stat is not None
    assert _rel(p.arch_lm_stat, float(arch_p.lm)) <= 1e-12
    assert _rel(p.ljung_box_stat, float(lb_p["lb_stat"].iloc[0])) <= 1e-12
    assert abs(float(raw.lm) - float(arch_p.lm)) > 1e-6  # teeth: demeaning matters
    for diag in (d, p):
        assert diag.ljung_box_p is not None and diag.jarque_bera_p is not None
        assert diag.arch_lm_p is not None
        assert diag.findings == (
            FINDING_LB[0 if diag.ljung_box_p < 0.05 else 1],
            FINDING_JB[0 if diag.jarque_bera_p < 0.05 else 1],
            FINDING_ARCH[0 if diag.arch_lm_p < 0.05 else 1],
        )


def _garch_errors(rng: np.random.Generator, n: int) -> FloatArray:
    e = np.empty(n)
    h = 0.012**2
    z = rng.standard_normal(n)
    prev = 0.0
    for t in range(n):
        h = 0.05 * 0.012**2 + 0.10 * prev**2 + 0.85 * h if t else 0.012**2
        e[t] = math.sqrt(h) * z[t]
        prev = e[t]
    return e


def test_tr37_diagnostics_behaviour() -> None:
    rng = rng_tr(37)
    g = analyse(dgp_residual(rng, alpha=0.0, e=_garch_errors(rng, 2520)))
    d = g.result.diagnostics_in_sample
    assert d.arch_lm_p is not None and d.arch_lm_p < 1e-3
    assert d.findings[2] == FINDING_ARCH[0]
    t5 = rng.standard_t(5, size=2520) * 0.012 / math.sqrt(5.0 / 3.0)
    s = analyse(dgp_residual(rng, alpha=0.0, e=t5))
    assert s.result.diagnostics_in_sample.jarque_bera_p is not None
    assert s.result.diagnostics_in_sample.jarque_bera_p < 1e-3


@pytest.mark.slow
def test_tr37_arch_size_with_fat_tails() -> None:
    reps, hits = 400, 0
    for rep in range(reps):
        rng = rng_tr(37, rep)
        e = rng.standard_t(5, size=2520) * 0.012 / math.sqrt(5.0 / 3.0)
        d = series_diagnostics(e - e.mean())
        assert d.arch_lm_p is not None
        hits += d.arch_lm_p < 0.05
    assert hits / reps <= 0.05 + 3.5 * math.sqrt(0.0475 / reps)


# ----------------------------------------------------------------------------- validator additions
# Added by the independent validation (docs/reviews/residual-alpha-validation-2026-11-18.md):
# each test kills a mutant that every other test let through.
def test_tr17_both_p_values_exactly_at_the_level() -> None:
    """``p_is = p_pit = 0.05``: neither is below 0.05, so G1 applies.

    Without this case a G1 written with ``>`` instead of ``>=`` passes every other test.
    """
    v = decide_verdict(0.125, 0.05, 0.125, 0.0625, 0.05)
    assert (v.code, v.severity) == ("no_reliable_alpha", "info")


def test_tr18_message_rounds_half_points_away_from_zero() -> None:
    """R4.8: ratios to the nearest 5 points, halves away from zero, in the verdict copy too.

    Dyadic ratios are exact in binary, so 12.5% and 37.5% are true half points.
    """
    kw: dict[str, Any] = {
        "window": 252,
        "warmup_start": date(2010, 1, 4),
        "warmup_end": date(2010, 12, 21),
    }
    g5 = verdict_message("mostly_disappears", a_c=0.04, a_pit=0.005, survival_ratio=0.125, **kw)
    assert "point-in-time betas keep 15% of it" in g5
    g5 = verdict_message("mostly_disappears", a_c=0.04, a_pit=0.015, survival_ratio=0.375, **kw)
    assert "point-in-time betas keep 40% of it" in g5
    g6 = verdict_message(
        "survives_not_significant", a_c=0.04, a_pit=0.045, survival_ratio=1.125, **kw
    )
    assert "(115% kept with point-in-time betas)" in g6


# ----------------------------------------------------------------------------- after validation
def test_verdict_uses_the_gated_alpha_tag() -> None:
    """F1: when the quality gate tags the in-sample alpha 'noise', the verdict agrees with it.

    The daily p-value is far below 0.05 here, but the gated tag says 'noise': the verdict must not
    read the in-sample alpha as reliable (no 'distinguishable from zero' next to a 'noise' chip).
    """
    a = analyse(dgp_rplus(rng_tr(19)))
    assert a.reg.alpha_tag == "reliable" and a.reg.fit.pvalues[0] < 0.05
    assert a.result.gap.verdict == "survives"
    gated = dataclasses.replace(a.reg, alpha_tag="noise")
    r = res_mod.residual_analysis(a.sample, gated, a.rolling, exact_fit=False)
    assert r.in_sample.tag == "noise"
    assert r.gap.verdict == "point_in_time_only"
    assert r.gap_message is not None and "distinguishable from zero" not in r.gap_message
    # the tag and the verdict also agree on the rules, not only on the real run
    v = decide_verdict(0.125, 0.01, 0.125, 0.109375, 0.01, in_sample_reliable=False)
    assert v.code == "point_in_time_only"
    v = decide_verdict(0.125, 0.01, 0.125, 0.109375, 0.30, in_sample_reliable=False)
    assert v.code == "no_reliable_alpha"
    v = decide_verdict(0.125, 0.20, 0.125, 0.109375, 0.01, in_sample_reliable=True)
    assert v.code == "survives"
