"""Stability tests TR23-TR28 (``docs/test-oracle-residual-analysis.md`` section 5).

Targets ``analytics/residual_stability.py``.
"""

from __future__ import annotations

import math
from datetime import date
from functools import cache
from typing import Any, cast

import numpy as np
import pandas as pd
import pytest
from numpy.typing import NDArray
from statsmodels.stats.multitest import (  # pyright: ignore[reportMissingTypeStubs]
    multipletests,  # pyright: ignore[reportUnknownVariableType]
)

from factordesk.analytics.regression import Z_975, A, bh_adjust
from factordesk.analytics.residual_stability import (
    calendar_years,
    non_overlapping_alpha,
    rolling_alpha,
    split_half_alpha,
)
from factordesk.analytics.rolling import rolling_betas
from factordesk.analytics.sample import FACTOR_CODES
from factordesk.tests.fixtures.dgp import BETA, dgp_a
from factordesk.tests.fixtures.dgp_residual import (
    Analysis,
    analyse,
    dgp_r0,
    dgp_residual,
    ols_reference,
    rng_tr,
    with_constant,
)

FloatArray = NDArray[np.float64]
_multipletests = cast(Any, multipletests)


@cache
def _dgp_a(k: int, n: int = 2520, window: int = 252) -> Analysis:
    return analyse(dgp_a(rng_tr(k), n=n), window)


def _dates(a: Analysis) -> list[date]:
    return [pd.Timestamp(t).date() for t in a.sample.xret.index]


def _rel(a: float, b: float) -> float:
    return abs(a - b) / abs(b)


def test_tr23_rolling_alpha() -> None:
    a = _dgp_a(23)
    rb = a.rolling
    ra = rolling_alpha(rb)
    alpha = rb.alpha.to_numpy()
    se = rb.alpha_se.to_numpy()
    np.testing.assert_allclose(ra.alpha_annual, 252 * alpha, rtol=1e-12, equal_nan=True)
    np.testing.assert_allclose(
        ra.ci_low_annual, 252 * (alpha - Z_975 * se), rtol=1e-12, equal_nan=True
    )
    np.testing.assert_allclose(
        ra.ci_high_annual, 252 * (alpha + Z_975 * se), rtol=1e-12, equal_nan=True
    )
    assert np.all(np.isnan(ra.alpha_annual[:251])) and not np.isnan(ra.alpha_annual[251])
    assert ra.n_stamps == 2269 and ra.hac_lags == 4
    index = a.sample.xret.index
    for i in range(251, 2520, 53):
        assert rb.window_start.iloc[i] == index[i - 251]
    live = ~np.isnan(ra.alpha_annual)
    count = int(np.count_nonzero(live & ((ra.ci_low_annual > 0) | (ra.ci_high_annual < 0))))
    assert ra.share_excluding_zero == count / 2269
    # Fixed window (RD9): the module accepts only the 252-row fit.
    with pytest.raises(ValueError, match="252"):
        rolling_alpha(rolling_betas(a.sample, 126))


def test_tr24_non_overlapping_tiling_and_bh() -> None:
    a = _dgp_a(24)
    dates = _dates(a)
    res = non_overlapping_alpha(a.rolling, dates)
    assert res.status == "ok" and res.family_size == 10 and len(res.windows) == 10
    ends = [dates.index(w.end) + 1 for w in res.windows]  # 1-based rows
    starts = [dates.index(w.start) + 1 for w in res.windows]
    assert ends == [2520 - 252 * j for j in range(10)]
    assert starts == [e - 251 for e in ends] and starts[-1] == 1
    assert all(w.n == 252 for w in res.windows)
    y = a.sample.xret.to_numpy(dtype=np.float64)
    f = a.sample.factors.loc[:, list(FACTOR_CODES)].to_numpy(dtype=np.float64)
    alpha = a.rolling.alpha.to_numpy()
    se = a.rolling.alpha_se.to_numpy()
    for w, e in zip(res.windows, ends, strict=True):
        i = e - 1
        assert w.alpha_annual == A * alpha[i] and w.se_annual == A * se[i]
        assert w.z == alpha[i] / se[i]
        ref = ols_reference(y[i - 251 : i + 1], with_constant(f[i - 251 : i + 1]), 4)
        assert _rel(w.alpha_annual, A * float(ref.params[0])) <= 1e-10
        assert _rel(w.se_annual, A * float(ref.bse[0])) <= 1e-10
        assert _rel(w.p, float(ref.pvalues[0])) <= 1e-10
    p = [w.p for w in res.windows]
    reject = np.asarray(_multipletests(p, alpha=0.05, method="fdr_bh")[0], dtype=bool)
    adj = np.asarray(_multipletests(p, alpha=0.05, method="fdr_bh")[1], dtype=np.float64)
    np.testing.assert_allclose([w.p_adj_bh for w in res.windows], adj, rtol=1e-12)
    assert res.n_reliable == int(np.sum(reject))

    long = analyse(dgp_a(rng_tr(24), n=2600))
    d2 = _dates(long)
    r2 = non_overlapping_alpha(long.rolling, d2)
    assert r2.family_size == 10
    assert r2.windows[0].end == d2[-1] and d2.index(r2.windows[-1].start) == 80

    rej, _ = bh_adjust([0.001, 0.02, 0.04, 0.5])
    assert sum(rej) == 2


def test_tr25_recent_alpha_is_found() -> None:
    n = 2520
    alpha = np.zeros(n)
    alpha[1764:] = 0.0035
    a = analyse(dgp_residual(rng_tr(25), n, alpha=alpha, sigma_e=0.008))
    res = non_overlapping_alpha(a.rolling, _dates(a))
    assert [w.tag for w in res.windows[:3]] == ["reliable"] * 3
    assert res.n_reliable >= 3


@pytest.mark.slow
def test_tr26_family_rate_under_zero_alpha() -> None:
    reps, hits = 1000, 0
    for rep in range(reps):
        d = dgp_r0(rng_tr(26, rep))
        a = analyse(d)
        hits += non_overlapping_alpha(a.rolling, _dates(a)).n_reliable >= 1
    assert hits / reps <= 0.10


def test_tr27_split_half_alpha() -> None:
    a = _dgp_a(27, n=2521)
    res = split_half_alpha(a.sample)
    assert (res.n_first, res.n_second) == (1260, 1261)
    y = a.sample.xret.to_numpy(dtype=np.float64)
    f = a.sample.factors.loc[:, list(FACTOR_CODES)].to_numpy(dtype=np.float64)
    n1 = 1260
    one = ols_reference(y[:n1], with_constant(f[:n1]), 8)
    two = ols_reference(y[n1:], with_constant(f[n1:]), 8)
    assert res.alpha_first_annual is not None and res.alpha_second_annual is not None
    # Absolute: an alpha near zero has no useful relative scale (oracle 0.1, identities).
    assert abs(res.alpha_first_annual - 252 * float(one.params[0])) <= 1e-10
    assert abs(res.alpha_second_annual - 252 * float(two.params[0])) <= 1e-10
    g = (np.arange(len(y)) >= n1).astype(np.float64)
    design = np.column_stack([np.ones(len(y)), f, g, f * g[:, None]])
    pooled = ols_reference(y, design, 8)
    assert res.hac_lags == 8
    assert res.difference_z is not None and res.difference_p is not None
    assert _rel(res.difference_z, float(pooled.tvalues[6])) <= 1e-10
    assert _rel(res.difference_p, float(pooled.pvalues[6])) <= 1e-10
    r_matrix = np.zeros((1, design.shape[1]))
    r_matrix[0, 0] = r_matrix[0, 6] = 1.0
    se2 = float(pooled.t_test(r_matrix).sd[0, 0])
    assert res.alpha_second_ci_high_annual is not None
    assert (
        _rel((res.alpha_second_ci_high_annual - res.alpha_second_annual) / (A * Z_975), se2)
        <= 1e-10
    )

    alpha = np.zeros(2520)
    alpha[1260:] = 0.002
    b = analyse(dgp_residual(rng_tr(27), 2520, alpha=alpha, sigma_e=0.008, beta=BETA))
    shift = split_half_alpha(b.sample)
    assert shift.difference_p is not None and shift.difference_p < 0.05
    assert shift.difference_annual is not None and shift.difference_se_annual is not None
    assert abs(shift.difference_annual - 0.504) <= 4 * shift.difference_se_annual


def test_tr28_calendar_year_table() -> None:
    a = _dgp_a(28)
    r = a.result
    rows = calendar_years(r.dates, r.u, r.u_tilde)
    assert [y.year for y in rows] == list(range(2010, 2020))
    assert [y.year for y in rows if y.partial] == [2019] and rows[-1].n == 174
    alpha_hat, e_hat = a.reg.alpha, a.reg.fit.resid
    years = np.array([d.year for d in r.dates])
    assert abs(sum(y.in_sample_sum for y in rows) - 2520 * alpha_hat) <= 1e-10
    for y in rows:
        m62 = y.n * alpha_hat + float(e_hat[years == y.year].sum())
        assert abs(y.in_sample_sum - m62) <= 1e-10
    assert rows[0].n_point_in_time == 8 and rows[0].point_in_time_partial
    assert all(y.n_point_in_time == y.n for y in rows[1:])
    assert r.u_tilde is not None
    span = r.u_tilde[252:]
    pit_sums = [y.point_in_time_sum for y in rows]
    assert all(v is not None for v in pit_sums)
    assert abs(sum(cast(list[float], pit_sums)) - len(span) * float(span.mean())) <= 1e-10
    sd_u, sd_p = float(np.std(r.u, ddof=1)), float(np.std(span, ddof=1))
    for y in rows:
        assert _rel(y.in_sample_noise_sd, sd_u * math.sqrt(y.n)) <= 1e-12
        assert y.point_in_time_noise_sd is not None
        assert _rel(y.point_in_time_noise_sd, sd_p * math.sqrt(y.n_point_in_time)) <= 1e-12

    b = _dgp_a(28, window=504)
    rb = b.result
    assert rb.u_tilde is not None
    rows504 = calendar_years(rb.dates, rb.u, rb.u_tilde)
    assert rows504[0].n_point_in_time == 0 and rows504[0].point_in_time_sum is None
    assert rows504[1].n_point_in_time == 16
