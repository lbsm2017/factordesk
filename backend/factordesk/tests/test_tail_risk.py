"""VaR and CVaR (E7a): ``analytics/tail_risk.py``.

Spec: ``docs/specs/next-stage-track-record-and-portfolio.md`` section "E7: VaR and CVaR",
verification list.
"""

from __future__ import annotations

import math
import statistics
from statistics import NormalDist

import numpy as np
import pandas as pd
import pytest
from scipy import integrate  # pyright: ignore[reportMissingTypeStubs]

from factordesk.analytics.tail_risk import (
    CF_FAR_FROM_HISTORICAL,
    CF_INDICATIVE,
    CF_INVALID,
    CF_VAR_NA,
    CF_Z_INDICATIVE,
    LEVELS,
    Frequency,
    Measure,
    Method,
    band_quality,
    complete_period_returns,
    cornish_fisher_monotone,
    cornish_fisher_quantile,
    cornish_fisher_range,
    historical_rank,
    min_expected_tail,
    modified_tail_mean,
    politis_white_block_length,
    stationary_bootstrap_indices,
    tail_risk,
)

N = NormalDist()
Z99 = N.inv_cdf(0.99)
Z975 = N.inv_cdf(0.975)


def _normal(seed: int, n: int, mu: float = 0.005, sd: float = 0.04) -> list[float]:
    return [float(v) for v in np.random.default_rng(seed).normal(mu, sd, n)]


def _mesokurtic_symmetric(mu: float, scale: float, copies: int) -> list[float]:
    """``mu + scale * {-1, 1, 0, 0, 0, 0}``: sample skewness 0 and excess kurtosis 0 exactly."""
    return [mu + scale * v for v in (-1.0, 1.0, 0.0, 0.0, 0.0, 0.0) * copies]


# ----------------------------------------------------------------------------- Gaussian
def test_gaussian_var_is_mean_minus_z_sigma() -> None:
    x = [0.012, -0.034, 0.021, 0.005, -0.017, 0.041, -0.052, 0.009, 0.015, -0.006, 0.027, -0.011]
    mu = statistics.mean(x)
    sigma = statistics.stdev(x)
    r = tail_risk(x, "monthly", n_resamples=50)
    assert r.figure("gaussian", "var", 0.99).value == pytest.approx(-(mu - Z99 * sigma), abs=1e-15)
    z95 = N.inv_cdf(0.95)
    assert r.figure("gaussian", "var", 0.95).value == pytest.approx(-(mu - z95 * sigma), abs=1e-15)
    es = -mu + sigma * N.pdf(Z975) / 0.025
    assert r.figure("gaussian", "cvar", 0.975).value == pytest.approx(es, abs=1e-15)
    # Basel's near-equivalence under normality: 2.326 sigma versus 2.338 sigma.
    assert N.pdf(Z975) / 0.025 == pytest.approx(2.3378, abs=1e-4)


# ----------------------------------------------------------------------------- Cornish-Fisher
def test_cornish_fisher_equals_gaussian_without_skew_or_excess_kurtosis() -> None:
    x = _mesokurtic_symmetric(0.004, 0.05, copies=4)
    r = tail_risk(x, "monthly", n_resamples=50)
    assert r.skewness == pytest.approx(0.0, abs=1e-12)
    assert r.excess_kurtosis == pytest.approx(0.0, abs=1e-12)
    for measure, level in LEVELS["monthly"]:
        cf = r.figure("cornish_fisher", measure, level).value
        gauss = r.figure("gaussian", measure, level).value
        assert cf is not None and gauss is not None
        assert cf == pytest.approx(gauss, abs=1e-12)
    for p in (0.01, 0.025, 0.05):
        z = N.inv_cdf(p)
        assert float(cornish_fisher_quantile(z, 0.0, 0.0)) == z
        assert float(modified_tail_mean(z, p, 0.0, 0.0)) == pytest.approx(-N.pdf(z) / p, rel=1e-13)


def test_cornish_fisher_quantile_formula() -> None:
    z, s, k = -2.0, -0.6, 1.5
    expected = z + (z**2 - 1) * s / 6 + (z**3 - 3 * z) * k / 24 - (2 * z**3 - 5 * z) * s**2 / 36
    assert float(cornish_fisher_quantile(z, s, k)) == pytest.approx(expected, abs=1e-15)
    assert expected == pytest.approx(-2.0 - 0.3 - 0.125 + 0.06, abs=1e-12)


@pytest.mark.parametrize(("s", "k"), [(-0.5, 1.0), (0.3, 2.0), (-1.0, 4.0)])
def test_modified_tail_mean_matches_edgeworth_integral(s: float, k: float) -> None:
    def density(x: float) -> float:
        he3 = x**3 - 3 * x
        he4 = x**4 - 6 * x**2 + 3
        he6 = x**6 - 15 * x**4 + 45 * x**2 - 15
        return N.pdf(x) * (1 + s / 6 * he3 + k / 24 * he4 + s**2 / 72 * he6)

    def first_moment(x: float) -> float:
        return x * density(x)

    p = 0.025
    g = float(cornish_fisher_quantile(N.inv_cdf(p), s, k))
    quad = integrate.quad(first_moment, -math.inf, g)  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    numeric = float(quad[0]) / p  # pyright: ignore[reportUnknownArgumentType]
    assert float(modified_tail_mean(g, p, s, k)) == pytest.approx(numeric, rel=1e-9)


def test_guard_direct_cases() -> None:
    z99 = N.inv_cdf(0.01)
    assert bool(cornish_fisher_monotone(-0.3, 1.0, z_high=z99))
    assert bool(cornish_fisher_monotone(0.0, 0.0, z_high=z99))
    # Heavy left skew: g'(-4) = -8.67 + 2.67 + 1.43 < 0.
    assert not bool(cornish_fisher_monotone(-2.0, 1.0, z_high=z99))
    # Platykurtic: the cubic term bends the map back in the far tail.
    assert not bool(cornish_fisher_monotone(0.0, -1.0, z_high=z99))
    # Kurtosis so large that g'(0) < 0 is still increasing on [-4, z_0.01] (local check).
    assert bool(cornish_fisher_monotone(0.0, 12.0, z_high=z99))


def test_guard_matches_a_brute_force_grid() -> None:
    rng = np.random.default_rng(7)
    s = rng.uniform(-3.0, 3.0, 4000)
    k = rng.uniform(-2.0, 25.0, 4000)
    z_high = N.inv_cdf(0.025)
    fast = cornish_fisher_monotone(s, k, z_high=z_high)
    grid = np.linspace(-4.0, z_high, 4001)[:, None]
    deriv = (k / 8 - s**2 / 6) * grid**2 + (s / 3) * grid + 1 - k / 8 + 5 * s**2 / 36
    brute = deriv.min(axis=0) > 0
    # The grid can miss a vertex minimum by a hair; allow a handful of borderline cases.
    assert np.count_nonzero(fast != brute) <= 3
    assert np.all(~fast[~brute] | (deriv.min(axis=0)[~brute] > -1e-4))
    assert 0.2 < fast.mean() < 0.95


def test_guard_trips_on_heavy_skew_and_passes_on_mild_data() -> None:
    skewed = [0.01] * 59 + [-0.5]
    r = tail_risk(skewed, "monthly", n_resamples=50)
    assert r.skewness < -7.0
    for measure, level in LEVELS["monthly"]:
        f = r.figure("cornish_fisher", measure, level)
        assert f.value is None and f.band is None and f.tail_count is None
        assert f.reason == CF_INVALID or (measure == "cvar" and f.reason == CF_VAR_NA)
    mild = _normal(3, 240)
    r = tail_risk(mild, "monthly", n_resamples=50)
    assert abs(r.skewness) < 0.5 and 0.0 < r.excess_kurtosis < 1.0
    for measure, level in LEVELS["monthly"]:
        f = r.figure("cornish_fisher", measure, level)
        assert f.value is not None and f.reason is None and not f.indicative


def test_guard_ranges_per_measure() -> None:
    z99 = N.inv_cdf(0.01)
    assert cornish_fisher_range("var", 0.99) == (z99, 0.0)
    assert cornish_fisher_range("cvar", 0.975) == (-4.0, N.inv_cdf(0.025))


def test_negative_excess_kurtosis_keeps_99_var() -> None:
    r = tail_risk(_normal(0, 240), "monthly", n_resamples=200)
    assert r.excess_kurtosis < 0.0
    f = r.figure("cornish_fisher", "var", 0.99)
    assert f.value is not None and f.reason is None and not f.indicative
    assert f.band is not None and f.tail_count is not None


_WIDE = {"z_high": CF_Z_INDICATIVE, "z_low": -CF_Z_INDICATIVE}


def test_indicative_rule_is_monotonicity_on_plus_minus_3_5() -> None:
    # Excess kurtosis 9 with no skew: g'(0) = 1 - 9/8 < 0, though the tails are fine.
    assert not bool(cornish_fisher_monotone(0.0, 9.0, **_WIDE))
    assert bool(cornish_fisher_monotone(0.0, -0.1, **_WIDE))
    assert bool(cornish_fisher_monotone(0.2, -0.3, **_WIDE))


def test_indicative_rate_on_normal_samples_is_low() -> None:
    # Seed 7 as in the module docstring; the rate over 4,000 samples is 0.083.
    rng = np.random.default_rng(7)
    flagged = 0
    for _ in range(200):
        r = tail_risk(rng.normal(0.006, 0.045, 120), "monthly", n_resamples=1)
        bends = not bool(cornish_fisher_monotone(r.skewness, r.excess_kurtosis, **_WIDE))
        shown = [f for f in r.figures if f.method == "cornish_fisher" and f.value is not None]
        assert all(f.indicative == bends for f in shown)
        flagged += bends
    assert flagged / 200 < 0.10


def test_high_kurtosis_daily_cvar_is_indicative() -> None:
    x = np.random.default_rng(1).standard_t(4, size=2500) * 0.01
    r = tail_risk(x, "daily", n_resamples=200)
    assert r.excess_kurtosis == pytest.approx(22.2, abs=0.1)
    # g'(0) = 1 - K/8 + 5 S^2/36 < 0: the map from the centre to z_0.01 is not increasing.
    var = r.figure("cornish_fisher", "var", 0.99)
    assert var.value is None and var.reason == CF_INVALID and not var.indicative
    # The CVaR guard on [-4, z_0.025] passes on its own, but a CVaR next to an n/a VaR is n/a too.
    z_low, z_high = cornish_fisher_range("cvar", 0.975)
    assert bool(cornish_fisher_monotone(r.skewness, r.excess_kurtosis, z_high=z_high, z_low=z_low))
    cvar = r.figure("cornish_fisher", "cvar", 0.975)
    assert cvar.value is None and cvar.reason == CF_VAR_NA and not cvar.indicative


@pytest.mark.parametrize("seed", range(8))
def test_modified_cvar_at_least_modified_var(seed: int) -> None:
    rng = np.random.default_rng(seed)
    x = 0.03 * rng.standard_t(5, 120) - 0.01 * rng.exponential(1.0, 120)
    r = tail_risk(x, "monthly", n_resamples=200, seed=seed)
    var = r.figure("cornish_fisher", "var", 0.95)
    cvar = r.figure("cornish_fisher", "cvar", 0.95)
    if var.value is not None and cvar.value is not None:
        assert cvar.value >= var.value
        assert cvar.band is not None and var.band is not None
        assert cvar.band.high >= var.band.low


def test_modified_cvar_floor_binds() -> None:
    # Positive skew inside the valid range: the raw Boudt tail mean lies above g, so the
    # reported modified CVaR is the floor, the modified VaR.
    s, k, p = 0.9, 4.5, 0.05
    g = float(cornish_fisher_quantile(N.inv_cdf(p), s, k))
    assert bool(cornish_fisher_monotone(s, k, z_high=N.inv_cdf(p)))
    assert float(modified_tail_mean(g, p, s, k)) > g


# ----------------------------------------------------------------------------- historical
def test_historical_matches_order_statistics_daily() -> None:
    x = _normal(11, 300, mu=0.0003, sd=0.011)
    srt = sorted(x)
    r = tail_risk(x, "daily", n_resamples=50)
    # 99%: n p = 3, k = 3. 97.5%: n p = 7.5, k = ceil(7.5) = 8.
    assert historical_rank(300, 0.99) == 3
    assert historical_rank(300, 0.975) == 8
    var = r.figure("historical", "var", 0.99)
    assert var.value == -srt[2]
    assert var.tail_count == 3
    cvar = r.figure("historical", "cvar", 0.975)
    assert cvar.value == pytest.approx(-sum(srt[:8]) / 8, abs=1e-16)
    assert cvar.tail_count == 8


def test_historical_matches_order_statistics_monthly() -> None:
    x = _normal(5, 120)
    srt = sorted(x)
    r = tail_risk(x, "monthly", n_resamples=50)
    # 95%: n p = 6 exactly, k = 6 (no floating-point spill to 7).
    assert historical_rank(120, 0.95) == 6
    assert r.figure("historical", "var", 0.95).value == -srt[5]
    assert r.figure("historical", "cvar", 0.95).value == pytest.approx(-sum(srt[:6]) / 6, abs=1e-16)
    assert r.figure("historical", "cvar", 0.975).value == pytest.approx(
        -sum(srt[:3]) / 3, abs=1e-16
    )
    assert r.figure("historical", "var", 0.99).reason == "1.2 expected tail observations"


def test_historical_cvar_includes_ties_at_the_quantile() -> None:
    x = [-0.05, -0.03, -0.03, -0.03] + [0.01 * i for i in range(56)]
    r = tail_risk(x, "monthly", n_resamples=50)
    var = r.figure("historical", "var", 0.95)  # k = 3: the -3% loss
    cvar = r.figure("historical", "cvar", 0.95)
    assert var.value == 0.03
    assert cvar.value == pytest.approx((0.05 + 3 * 0.03) / 4, abs=1e-16)
    assert cvar.tail_count == 4


def test_historical_is_na_at_36_months_for_99() -> None:
    r = tail_risk(_normal(2, 36), "monthly", n_resamples=50)
    f = r.figure("historical", "var", 0.99)
    assert f.value is None and f.band is None and f.tail_count is None
    assert f.expected_tail_obs == pytest.approx(0.36)
    assert f.reason == "0.4 expected tail observations"
    assert r.figure("historical", "cvar", 0.975).reason == "0.9 expected tail observations"
    assert r.figure("historical", "var", 0.95).reason == "1.8 expected tail observations"
    assert r.figure("gaussian", "var", 0.99).value is not None
    # 40 months reach the monthly 95% minimum of 2 expected tail months: shown.
    srt = sorted(_normal(2, 40))
    r40 = tail_risk(_normal(2, 40), "monthly", n_resamples=50)
    assert historical_rank(40, 0.95) == 2
    assert r40.figure("historical", "var", 0.95).value == -srt[1]
    assert r40.figure("historical", "cvar", 0.95).value == pytest.approx(
        -(srt[0] + srt[1]) / 2, abs=1e-16
    )
    assert r40.figure("historical", "var", 0.95).band is not None
    # The other levels keep the minimum of 3: 97.5% at 40 months is 1.0 expected.
    assert r40.figure("historical", "cvar", 0.975).reason == "1.0 expected tail observations"
    r39 = tail_risk(_normal(2, 39), "monthly", n_resamples=50)
    # 1.95 is not shown as "2.0", which would read as meeting the minimum.
    assert r39.figure("historical", "var", 0.95).reason == "1.95 expected tail observations"


def test_min_expected_tail_rule() -> None:
    assert min_expected_tail("monthly", 0.95) == 2.0
    assert min_expected_tail("monthly", 0.99) == 3.0
    assert min_expected_tail("monthly", 0.975) == 3.0
    assert min_expected_tail("daily", 0.99) == 3.0
    assert min_expected_tail("daily", 0.975) == 3.0


# ----------------------------------------------------------------------------- shape and inputs
def test_levels_per_frequency_and_signs() -> None:
    daily = tail_risk(_normal(1, 500, 0.0004, 0.01), "daily", n_resamples=50)
    assert {(f.measure, f.level) for f in daily.figures} == {("var", 0.99), ("cvar", 0.975)}
    assert len(daily.figures) == 6
    assert daily.bootstrap == "stationary" and daily.mean_block_length is not None
    monthly = tail_risk(_normal(1, 120), "monthly", n_resamples=50)
    assert len(monthly.figures) == 12
    assert monthly.bootstrap == "iid" and monthly.mean_block_length is None
    for f in daily.figures + monthly.figures:
        assert f.value is None or f.value > 0.0  # losses are positive
    with pytest.raises(KeyError):
        daily.figure("historical", "var", 0.95)


@pytest.mark.parametrize(
    "bad",
    [[0.01] * 11, [0.01] * 20, [0.01] * 19 + [math.nan], [0.01] * 19 + [-1.0]],
)
def test_bad_inputs_are_refused(bad: list[float]) -> None:
    with pytest.raises(ValueError):
        tail_risk(bad, "monthly")


# ----------------------------------------------------------------------------- bootstrap
def test_bootstrap_is_reproducible_with_a_seed() -> None:
    x = _normal(9, 400, 0.0003, 0.01)
    a = tail_risk(x, "daily", n_resamples=200, seed=42)
    b = tail_risk(x, "daily", n_resamples=200, seed=42)
    c = tail_risk(x, "daily", n_resamples=200, seed=43)
    assert a == b
    assert a.figures != c.figures
    m1 = tail_risk(x[:120], "monthly", n_resamples=200, seed=42)
    assert m1 == tail_risk(x[:120], "monthly", n_resamples=200, seed=42)
    for f in a.figures:
        assert f.band is not None and f.value is not None
        assert f.band.resamples == 200 or f.method == "cornish_fisher"
        assert f.band.low <= f.band.high


def test_stationary_indices_have_the_requested_mean_block_length() -> None:
    rng = np.random.default_rng(0)
    idx = stationary_bootstrap_indices(rng, 1000, 50, 8.0)
    assert idx.shape == (50, 1000)
    assert idx.min() >= 0 and idx.max() < 1000
    breaks = np.count_nonzero(np.diff(idx, axis=1) % 1000 != 1)
    mean_len = idx.size / (breaks + idx.shape[0])
    assert mean_len == pytest.approx(8.0, rel=0.1)


def test_block_length_rule() -> None:
    rng = np.random.default_rng(4)
    iid = rng.normal(size=2000)
    assert politis_white_block_length(iid) < 3.0
    ar = np.zeros(2000)
    eps = rng.normal(size=2000)
    for t in range(1, 2000):
        ar[t] = 0.8 * ar[t - 1] + eps[t]
    b = politis_white_block_length(ar)
    assert 8.0 < b <= math.ceil(3 * math.sqrt(2000))


@pytest.mark.slow
def test_band_coverage_on_simulated_normal_data() -> None:
    """Coverage of the true figure by the 90% percentile band.

    "validated" bands (Gaussian, historical VaR) cover close to 90%. "approximate" bands
    (historical CVaR, Cornish-Fisher) under-cover on small tails (about 75-85% measured), so
    they get a wider, documented floor.
    """
    cases: tuple[tuple[Frequency, int, float, float, int], ...] = (
        ("daily", 600, 0.0004, 0.01, 150),
        ("monthly", 240, 0.006, 0.045, 300),
    )
    for freq, n, mu, sd, reps in cases:
        rng = np.random.default_rng(123)
        hits: dict[tuple[Method, Measure, float], list[bool]] = {}
        for i in range(reps):
            x = rng.normal(mu, sd, n)
            r = tail_risk(x, freq, seed=i, n_resamples=400)
            for f in r.figures:
                if f.band is None:
                    continue
                p = round(1.0 - f.level, 12)
                z = N.inv_cdf(p)
                true = -(mu + z * sd) if f.measure == "var" else -mu + sd * N.pdf(z) / p
                hits.setdefault((f.method, f.measure, f.level), []).append(
                    f.band.low <= true <= f.band.high
                )
        for key, v in hits.items():
            method, measure, level = key
            coverage = float(np.mean(v))
            assert len(v) >= reps // 2
            floor = 0.84 if band_quality(method, measure) == "validated" else 0.70
            assert floor <= coverage <= 0.96, (freq, method, measure, level, coverage)


def test_cornish_fisher_band_withheld_below_80_percent_valid_resamples() -> None:
    r = tail_risk(_normal(0, 36), "monthly", n_resamples=200)
    cvar = r.figure("cornish_fisher", "cvar", 0.975)
    assert cvar.value is not None and cvar.band is None
    assert cvar.band_reason == (
        "only 147 of 200 resamples inside the valid range of the expansion (minimum 80%)"
    )
    var = r.figure("cornish_fisher", "var", 0.99)
    assert var.band is not None and var.band_reason is None
    assert 160 <= var.band.resamples < 200
    for f in r.figures:
        if f.method != "cornish_fisher":
            assert f.band_reason is None


def test_band_quality_labels() -> None:
    r = tail_risk(_normal(1, 240), "monthly", n_resamples=200)
    for f in r.figures:
        if f.band is None:
            assert f.band_quality is None
            continue
        if f.method == "gaussian" or (f.method == "historical" and f.measure == "var"):
            assert f.band_quality == "validated"
        else:
            assert f.band_quality == "approximate"
    assert r.figure("gaussian", "cvar", 0.975).band_quality == "validated"
    assert r.figure("historical", "var", 0.95).band_quality == "validated"
    assert r.figure("historical", "cvar", 0.95).band_quality == "approximate"
    assert r.figure("cornish_fisher", "var", 0.99).band_quality == "approximate"
    na = tail_risk(_normal(1, 36), "monthly", n_resamples=50).figure("historical", "var", 0.99)
    assert na.band is None and na.band_quality is None


# ----------------------------------------------------------------------------- S3-7 fixes
def _heavy_tailed_cases() -> list[tuple[Frequency, list[float]]]:
    """Series of both frequencies with heavy tails, so that the guards and the flag both trip."""
    cases: list[tuple[Frequency, list[float]]] = []
    for seed in range(12):
        rng = np.random.default_rng(100 + seed)
        cases.append(("daily", [float(v) for v in rng.standard_t(3, 1500) * 0.01]))
        cases.append(("monthly", [float(v) for v in rng.standard_t(3, 60) * 0.03]))
        cases.append(("monthly", [float(v) for v in rng.standard_t(5, 120) * 0.03 + 0.004]))
    return cases


def test_cornish_fisher_cvar_is_na_whenever_its_var_is_na() -> None:
    tripped = 0
    for freq, x in _heavy_tailed_cases():
        r = tail_risk(x, freq, n_resamples=20)
        var_levels = [lv for measure, lv in LEVELS[freq] if measure == "var"]
        for measure, level in LEVELS[freq]:
            if measure != "cvar":
                continue
            needed = [lv for lv in var_levels if lv >= level - 1e-9]
            if not any(r.figure("cornish_fisher", "var", lv).value is None for lv in needed):
                continue
            tripped += 1
            f = r.figure("cornish_fisher", "cvar", level)
            assert f.value is None and f.band is None and f.tail_count is None
            assert f.reason in (CF_VAR_NA, CF_INVALID) and not f.indicative
    assert tripped > 0


def _cf_far_from_historical(cf: float, hist: float, std: float) -> bool:
    return abs(cf - hist) > CF_FAR_FROM_HISTORICAL * max(abs(hist), std)


def test_cornish_fisher_is_indicative_when_far_from_the_historical_figure() -> None:
    far = near = 0
    for freq, x in _heavy_tailed_cases():
        r = tail_risk(x, freq, n_resamples=20)
        for measure, level in LEVELS[freq]:
            hist = r.figure("historical", measure, level).value
            cf = r.figure("cornish_fisher", measure, level)
            if hist is None or cf.value is None:
                continue
            bends = cf.reason is not None and CF_INDICATIVE in cf.reason
            is_far = _cf_far_from_historical(cf.value, hist, r.std)
            text = f"far from historical ({cf.value:.1%} vs {hist:.1%})"
            assert cf.indicative == (bends or is_far)
            assert (cf.reason is not None and text in cf.reason) == is_far
            if is_far:
                far += 1
                assert abs(cf.value - hist) > CF_FAR_FROM_HISTORICAL * max(abs(hist), r.std) - 1e-15
            else:
                near += 1
    assert far > 0 and near > 0


def test_low_volatility_positive_drift_is_rarely_flagged_far_from_historical() -> None:
    """Near-zero historical figures (mean 0.35%, sd 0.2%) must not flag a correct model."""
    rng = np.random.default_rng(31)
    flagged = shown = 0
    for _ in range(100):
        r = tail_risk(rng.normal(0.0035, 0.002, 60), "monthly", n_resamples=1)
        for measure, level in LEVELS["monthly"]:
            hist = r.figure("historical", measure, level).value
            cf = r.figure("cornish_fisher", measure, level)
            if hist is None or cf.value is None:
                continue
            shown += 1
            flagged += cf.reason is not None and "far from historical" in cf.reason
    assert shown > 0
    assert flagged / shown < 0.10


# ----------------------------------------------------------------------------- horizons
def _daily_returns(start: str, end: str, seed: int = 5) -> pd.Series:
    """Business-day returns, a few percent of a point a day, stamped on the dates."""
    dates = pd.bdate_range(start, end)
    rng = np.random.default_rng(seed)
    return pd.Series(rng.normal(0.0004, 0.01, len(dates)), index=dates)


def _arrays(s: pd.Series) -> tuple[np.ndarray, np.ndarray]:
    return s.index.to_numpy(dtype="datetime64[D]"), s.to_numpy(dtype=float)


def period_label(stamp: object, freq: str) -> str:
    """``2020-03`` (monthly) or ``2020Q1`` (quarterly) of a date."""
    t = pd.Timestamp(stamp)  # pyright: ignore[reportArgumentType]
    return f"{t.year}-{t.month:02d}" if freq == "M" else f"{t.year}Q{(t.month - 1) // 3 + 1}"


def period_groups(s: pd.Series, freq: str) -> dict[str, list[float]]:
    """The returns of each calendar period, in date order (independent of the code under test)."""
    groups: dict[str, list[float]] = {}
    for stamp, value in s.items():
        groups.setdefault(period_label(stamp, freq), []).append(float(value))
    return groups


def compounded(s: pd.Series, freq: str, keep: list[str]) -> list[float]:
    """``prod(1 + r) - 1`` of the listed periods."""
    groups = period_groups(s, freq)
    return [math.prod(1.0 + r for r in groups[k]) - 1.0 for k in keep]


def test_daily_returns_compound_into_complete_calendar_months_only() -> None:
    s = _daily_returns("2019-12-09", "2021-02-26")  # starts mid December, ends Friday 26 Feb
    dates, values = _arrays(s)
    out = complete_period_returns(dates, values, dates, "monthly", "daily")
    # December 2019 starts after its first days (and the history has no earlier row).
    # February 2021 ends within four days of the month end, so it counts.
    months = [str(p) for p in pd.period_range("2020-01", "2021-02", freq="M")]
    assert list(out.labels) == months
    np.testing.assert_allclose(out.returns, compounded(s, "M", months), rtol=0, atol=1e-14)


def test_the_last_month_is_dropped_when_the_data_stop_early_in_it() -> None:
    s = _daily_returns("2019-11-01", "2021-02-12")
    dates, values = _arrays(s)
    out = complete_period_returns(dates, values, dates, "monthly", "daily")
    assert out.labels[-1] == "2021-01" and "2021-02" not in out.labels
    assert out.labels[0] == "2019-12"  # November 2019 is the first month of the history: dropped


def test_months_are_complete_when_the_subject_continues_beyond_the_sample() -> None:
    full = _daily_returns("2019-06-03", "2021-06-30")
    sample = full.loc["2020-01-01":"2020-12-15"]
    out = complete_period_returns(
        *_arrays(sample), full.index.to_numpy(dtype="datetime64[D]"), "monthly", "daily"
    )  # noqa: E501
    # January 2020 has history before it; December 2020 is cut in the middle by the window.
    months = [f"2020-{m:02d}" for m in range(1, 12)]
    assert list(out.labels) == months
    np.testing.assert_allclose(out.returns, compounded(full, "M", months), rtol=0, atol=1e-14)


def test_a_month_with_an_excluded_day_is_left_out_not_patched() -> None:
    full = _daily_returns("2019-06-03", "2021-06-30")
    hole = full.index[full.index.get_loc(pd.Timestamp("2020-03-18"))]
    sample = full.drop(hole)
    out = complete_period_returns(
        *_arrays(sample), full.index.to_numpy(dtype="datetime64[D]"), "monthly", "daily"
    )  # noqa: E501
    assert "2020-03" not in out.labels and "2020-02" in out.labels and "2020-04" in out.labels


def test_daily_returns_compound_into_non_overlapping_complete_quarters() -> None:
    s = _daily_returns("2018-02-01", "2021-05-14")
    dates, values = _arrays(s)
    out = complete_period_returns(dates, values, dates, "quarterly", "daily")
    quarters = [f"{y}Q{q}" for y in (2018, 2019, 2020) for q in (1, 2, 3, 4)][1:]
    quarters.append("2021Q1")
    assert list(out.labels) == quarters  # 2018Q1 starts late, 2021Q1 is complete, 2021Q2 is not
    expected = compounded(s, "Q", list(out.labels))
    np.testing.assert_allclose(out.returns, expected, rtol=0, atol=1e-14)
    # Non-overlapping: every day is in at most one period, so the compounded periods multiply to
    # the compounded days they cover.
    covered = [r for k in out.labels for r in period_groups(s, "Q")[k]]
    assert math.isclose(
        float(np.prod(1.0 + out.returns)), math.prod(1.0 + r for r in covered), rel_tol=1e-12
    )


def test_monthly_returns_compound_into_complete_quarters() -> None:
    dates = pd.date_range("2015-01-31", periods=30, freq="ME")
    m = pd.Series(np.random.default_rng(3).normal(0.006, 0.04, 30), index=dates)
    sample = m.drop(m.index[7])  # August 2015 missing: 2015Q3 is incomplete
    out = complete_period_returns(
        *_arrays(sample), dates.to_numpy(dtype="datetime64[D]"), "quarterly", "monthly"
    )
    quarters = [f"{y}Q{q}" for y in (2015, 2016, 2017) for q in (1, 2, 3, 4)][:10]
    quarters.remove("2015Q3")
    assert list(out.labels) == quarters
    np.testing.assert_allclose(out.returns, compounded(m, "Q", quarters), rtol=0, atol=1e-14)


def test_an_empty_sample_has_no_periods() -> None:
    empty = np.zeros(0, dtype="datetime64[D]")
    out = complete_period_returns(empty, np.zeros(0), empty, "monthly", "daily")
    assert out.labels == () and out.returns.size == 0


def test_quarterly_series_use_the_iid_bootstrap_and_the_95_rows() -> None:
    x = _normal(8, 48, 0.02, 0.07)
    r = tail_risk(x, "quarterly", n_resamples=200)
    assert r.frequency == "quarterly" and r.bootstrap == "iid" and r.mean_block_length is None
    keys = [(f.measure, f.level) for f in r.figures if f.method == "gaussian"]
    assert keys == [("var", 0.99), ("cvar", 0.975), ("var", 0.95), ("cvar", 0.95)]
    # 48 x 5% = 2.4 expected tail quarters: the 95% VaR is shown, the 99% one is n/a.
    assert r.figure("historical", "var", 0.95).value is not None
    h99 = r.figure("historical", "var", 0.99)
    assert h99.value is None and h99.reason == "0.5 expected tail observations"
    assert min_expected_tail("quarterly", 0.95) == min_expected_tail("monthly", 0.95) == 2.0
    assert min_expected_tail("quarterly", 0.99) == 3.0
