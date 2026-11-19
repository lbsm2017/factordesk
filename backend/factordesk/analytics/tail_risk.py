"""Value at risk and expected shortfall (CVaR) of one return series (E7a).

Spec: ``docs/specs/next-stage-track-record-and-portfolio.md`` section "E7: VaR and CVaR";
research notes ``docs/research/next-stage-research.md`` section D.

Conventions
-----------
* Input is a series of **simple** returns at its own frequency (1 day or 1 month). Results stay
  at that frequency: there is no square-root-of-time scaling.
* A loss is ``L = -r``. VaR and CVaR are reported as **positive fractions of value** when the
  tail is a loss (a negative figure means even the tail is a gain).
* ``level`` is the confidence level (0.99); ``p = 1 - level`` is the tail probability and
  ``z_p = Phi^-1(p)`` is negative.
* Levels: 99% VaR and 97.5% CVaR for every series; monthly series also get 95% VaR and 95% CVaR.

Methods
-------
* **Historical.** ``VaR = -r_(k)`` with ``k = ceil(n p)``, where ``r_(1) <= ... <= r_(n)`` are
  the sorted returns. This is the inverse of the empirical CDF, ``inf{x : F_n(x) >= p}``
  (Hyndman-Fan type 1); no interpolation. CVaR is the mean loss of the observations at or beyond
  VaR (``r <= r_(k)``, ties included). When the expected tail count ``n p`` is below 3 the figure
  is n/a.
* **Gaussian.** ``VaR = -(mu + z_p sigma)`` and ``CVaR = -mu + sigma phi(z_p) / p``, with the
  sample mean and the sample standard deviation (``ddof = 1``).
* **Cornish-Fisher (modified).** Zangari (1996) / Favre & Galeano (2002):
  ``g = z + (z^2 - 1) S/6 + (z^3 - 3z) K/24 - (2z^3 - 5z) S^2/36`` at ``z = z_p``, and
  ``mVaR = -(mu + g sigma)``. ``S`` and ``K`` are the moment estimators of skewness and excess
  kurtosis, ``m3 / m2^1.5`` and ``m4 / m2^2 - 3`` with ``m_k`` the central sample moments (as in
  PerformanceAnalytics); ``mu`` and ``sigma`` are as in the Gaussian method, so the two methods
  coincide when ``S = K = 0``.

  Modified CVaR is Boudt, Peterson & Croux (2008, *Journal of Risk* 11(2), eq. for mES): the
  tail mean of the standardised Edgeworth density below ``g``, divided by ``p``,
  ``mES = -mu - sigma min(E_G, g)``. It is floored at the modified VaR of the same level.

  Validity guard (Maillard 2012, "A User's Guide to the Cornish Fisher Expansion", SSRN 1997178):
  the expansion is a quantile only where the map ``z -> g(z)`` is increasing. Its derivative is
  the quadratic ``g'(z) = (K/8 - S^2/6) z^2 + (S/3) z + 1 - K/8 + 5 S^2/36``. Two checks:

  * **Local** (decides n/a): ``g'(z) > 0`` on the range the figure uses, ``[z_p, 0]`` for VaR
    (the map from the centre out to the quantile) and ``[-4, z_p]`` for CVaR (the tail it
    averages). If it fails the figure is n/a with the reason :data:`CF_INVALID`.
  * **Global** (Maillard's domain): ``g'(z) > 0`` for every real ``z``, which holds iff
    ``a > 0`` and ``b^2 - 4 a c < 0`` (or ``a = b = 0 < c``). A figure that passes the local
    check but not the global one keeps its value with ``indicative=True`` and the reason
    :data:`CF_INDICATIVE`. Any negative excess kurtosis below ``4 S^2 / 3`` makes ``a < 0``,
    so such samples are always indicative.

Uncertainty
-----------
Each figure gets a 90% percentile bootstrap band, from 1,000 resamples by default and a fixed
seed. Monthly series use the iid bootstrap. Daily series use the stationary bootstrap of
Politis & Romano (1994, *JASA* 89) with circular wrapping. Its mean block length is chosen by
the automatic rule of Politis & White (2004, *Econometric Reviews* 23) with the correction of
Patton, Politis & White (2009), applied to the absolute demeaned returns, because volatility
clustering, not return autocorrelation, is the dependence that moves tail measures. The length
is floored at 1 and capped at ``min(3 sqrt(n), n / 3)``.

For Cornish-Fisher, resamples that fall outside the valid range are dropped from the band;
``Band.resamples`` says how many were used.

The bands are plain percentile intervals. On simulated normal data (see the slow coverage
test) Gaussian and historical VaR bands cover about 86-90%; historical CVaR and Cornish-Fisher
bands under-cover (about 75-85%), as percentile bootstraps of tail means and of higher moments
do on small tails. Read them as lower bounds on the uncertainty.

Pure: no I/O, no clock. Randomness only through the ``seed`` argument. Inputs are not mutated.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from statistics import NormalDist
from typing import Literal

import numpy as np
from numpy.typing import ArrayLike, NDArray
from scipy.special import ndtr  # pyright: ignore[reportMissingTypeStubs, reportUnknownVariableType]

FloatArray = NDArray[np.float64]
Frequency = Literal["daily", "monthly"]
Method = Literal["historical", "gaussian", "cornish_fisher"]
Measure = Literal["var", "cvar"]

METHODS: tuple[Method, ...] = ("historical", "gaussian", "cornish_fisher")
LEVELS: dict[Frequency, tuple[tuple[Measure, float], ...]] = {
    "daily": (("var", 0.99), ("cvar", 0.975)),
    "monthly": (("var", 0.99), ("cvar", 0.975), ("var", 0.95), ("cvar", 0.95)),
}
"""The (measure, confidence level) pairs reported for each frequency."""

MIN_EXPECTED_TAIL = 3.0
"""A historical figure needs at least this many expected tail observations ``n (1 - level)``."""
CF_Z_LOW = -4.0
"""Lower end of the interval on which the Cornish-Fisher map must be increasing."""
CF_INVALID = "outside the valid range of the expansion (Maillard 2012)"
CF_INDICATIVE = "outside the global validity domain (Maillard 2012); indicative only"
MIN_OBS = 12
"""Fewer observations are refused: the moments behind the parametric methods are meaningless."""

_BATCH = 100
"""Resamples evaluated together, to bound memory on long daily series."""
_SQRT_2PI = math.sqrt(2.0 * math.pi)


# ----------------------------------------------------------------------------- results
@dataclass(frozen=True)
class Band:
    """Percentile bootstrap band ``[low, high]`` and the number of resamples behind it."""

    low: float
    high: float
    resamples: int


@dataclass(frozen=True)
class TailFigure:
    """One VaR or CVaR figure: one method, one measure, one confidence level.

    ``value`` is a positive fraction of value for a loss, or None when the figure is n/a; then
    ``reason`` says why. A Cornish-Fisher figure outside Maillard's global domain keeps its value
    with ``indicative=True`` and the caveat in ``reason``. ``tail_count`` is the number of
    observations with a loss at or beyond this method's VaR at ``level`` (for the historical
    method, the observations the figure is computed from). ``expected_tail_obs`` is
    ``n (1 - level)``.
    """

    method: Method
    measure: Measure
    level: float
    value: float | None
    reason: str | None
    band: Band | None
    tail_count: int | None
    expected_tail_obs: float
    indicative: bool = False


@dataclass(frozen=True)
class TailRisk:
    """All figures of one series, with the moments and bootstrap settings behind them."""

    frequency: Frequency
    n_obs: int
    mean: float
    std: float
    skewness: float
    excess_kurtosis: float
    bootstrap: Literal["iid", "stationary"]
    mean_block_length: float | None
    n_resamples: int
    band_level: float
    seed: int
    figures: tuple[TailFigure, ...]

    def figure(self, method: Method, measure: Measure, level: float) -> TailFigure:
        """The figure for ``(method, measure, level)``; KeyError if it is not reported."""
        for f in self.figures:
            if f.method == method and f.measure == measure and math.isclose(f.level, level):
                return f
        raise KeyError((method, measure, level))


# ----------------------------------------------------------------------------- formulas
def tail_probability(level: float) -> float:
    """``1 - level`` with the floating-point dust removed (``1 - 0.99`` is not 0.01)."""
    if not 0.5 < level < 1.0:
        raise ValueError(f"confidence level must be in (0.5, 1), got {level}")
    return round(1.0 - level, 12)


def historical_rank(n: int, level: float) -> int:
    """``k = ceil(n p)``: the 1-based order statistic that is the historical VaR quantile."""
    p = tail_probability(level)
    return max(1, math.ceil(n * p - 1e-9))


def cornish_fisher_quantile(z: ArrayLike, skew: ArrayLike, exkurt: ArrayLike) -> FloatArray:
    """Zangari / Favre-Galeano Cornish-Fisher quantile ``g(z)`` of a standardised variable."""
    z_ = np.asarray(z, dtype=np.float64)
    s = np.asarray(skew, dtype=np.float64)
    k = np.asarray(exkurt, dtype=np.float64)
    return (
        z_
        + (z_**2 - 1.0) * s / 6.0
        + (z_**3 - 3.0 * z_) * k / 24.0
        - (2.0 * z_**3 - 5.0 * z_) * s**2 / 36.0
    )


def cornish_fisher_monotone(
    skew: ArrayLike, exkurt: ArrayLike, z_high: float, z_low: float = CF_Z_LOW
) -> NDArray[np.bool_]:
    """True where ``g'(z) > 0`` for every ``z`` in ``[z_low, z_high]`` (the validity guard).

    ``g'(z) = a z^2 + b z + c`` with ``a = K/8 - S^2/6``, ``b = S/3``, ``c = 1 - K/8 + 5 S^2/36``.
    Its minimum on the interval is at an end point or, when ``a > 0``, at the vertex ``-b/2a``.
    """
    s = np.asarray(skew, dtype=np.float64)
    k = np.asarray(exkurt, dtype=np.float64)
    a = k / 8.0 - s**2 / 6.0
    b = s / 3.0
    c = 1.0 - k / 8.0 + 5.0 * s**2 / 36.0

    def deriv(z: FloatArray | float) -> FloatArray:
        return np.asarray(a * z**2 + b * z + c, dtype=np.float64)

    lowest = np.minimum(deriv(z_low), deriv(z_high))
    with np.errstate(divide="ignore", invalid="ignore"):
        vertex = np.where(a > 0.0, -b / (2.0 * a), np.nan)
    inside = (vertex > z_low) & (vertex < z_high)
    lowest = np.where(inside, np.minimum(lowest, deriv(np.nan_to_num(vertex))), lowest)
    return np.asarray(np.isfinite(lowest) & (lowest > 0.0))


def cornish_fisher_globally_monotone(skew: ArrayLike, exkurt: ArrayLike) -> NDArray[np.bool_]:
    """True where ``g'(z) > 0`` for every real ``z`` (Maillard's domain of validity).

    With ``g'(z) = a z^2 + b z + c`` (see :func:`cornish_fisher_monotone`) this is ``a > 0`` and
    ``b^2 - 4 a c < 0``, or the degenerate ``a = b = 0`` with ``c > 0``.
    """
    s = np.asarray(skew, dtype=np.float64)
    k = np.asarray(exkurt, dtype=np.float64)
    a = k / 8.0 - s**2 / 6.0
    b = s / 3.0
    c = 1.0 - k / 8.0 + 5.0 * s**2 / 36.0
    proper: NDArray[np.bool_] = np.asarray((a > 0.0) & (b**2 - 4.0 * a * c < 0.0))
    flat: NDArray[np.bool_] = np.asarray(np.equal(a, 0.0) & np.equal(b, 0.0) & (c > 0.0))
    return proper | flat


def cornish_fisher_range(measure: Measure, level: float) -> tuple[float, float]:
    """The ``z`` range the local guard checks: ``[z_p, 0]`` for VaR, ``[-4, z_p]`` for CVaR."""
    z = NormalDist().inv_cdf(tail_probability(level))
    return (z, 0.0) if measure == "var" else (CF_Z_LOW, z)


def _normal_partial_moments(h: FloatArray, top: int) -> list[FloatArray]:
    """``J_q(h) = int_{-inf}^h x^q phi(x) dx`` for ``q = 0..top``.

    ``J_0 = Phi(h)``, ``J_1 = -phi(h)``, ``J_q = -h^(q-1) phi(h) + (q-1) J_(q-2)``.
    """
    pdf = np.exp(-0.5 * h**2) / _SQRT_2PI
    cdf = np.asarray(ndtr(h), dtype=np.float64)
    moments: list[FloatArray] = [cdf, -pdf]
    for q in range(2, top + 1):
        moments.append(-(h ** (q - 1)) * pdf + (q - 1) * moments[q - 2])
    return moments


def modified_tail_mean(g: ArrayLike, p: float, skew: ArrayLike, exkurt: ArrayLike) -> FloatArray:
    """Boudt, Peterson & Croux (2008): ``E[X | X <= g]`` under the Edgeworth density, over ``p``.

    The standardised Edgeworth density is ``phi(x) [1 + S/6 He3 + K/24 He4 + S^2/72 He6]``, so
    ``E_G = (1/p) [J1 + S/6 (J4 - 3 J2) + K/24 (J5 - 6 J3 + 3 J1)
    + S^2/72 (J7 - 15 J5 + 45 J3 - 15 J1)]`` evaluated at ``g``.
    """
    h = np.asarray(g, dtype=np.float64)
    s = np.asarray(skew, dtype=np.float64)
    k = np.asarray(exkurt, dtype=np.float64)
    j = _normal_partial_moments(h, 7)
    total = (
        j[1]
        + s / 6.0 * (j[4] - 3.0 * j[2])
        + k / 24.0 * (j[5] - 6.0 * j[3] + 3.0 * j[1])
        + s**2 / 72.0 * (j[7] - 15.0 * j[5] + 45.0 * j[3] - 15.0 * j[1])
    )
    return np.asarray(total / p, dtype=np.float64)


# ----------------------------------------------------------------------------- per-sample core
@dataclass(frozen=True)
class _Moments:
    mean: FloatArray
    std: FloatArray
    skew: FloatArray
    exkurt: FloatArray


def _moments(x: FloatArray) -> _Moments:
    """Row-wise moments of a ``(rows, n)`` array (see the module docstring for the estimators)."""
    n = x.shape[1]
    mu = x.mean(axis=1)
    d = x - mu[:, None]
    m2 = (d**2).mean(axis=1)
    m3 = (d**3).mean(axis=1)
    m4 = (d**4).mean(axis=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        skew = m3 / m2**1.5
        exkurt = m4 / m2**2 - 3.0
    std = np.sqrt(m2 * n / (n - 1))
    return _Moments(mu, std, skew, exkurt)


def _gaussian(m: _Moments, measure: Measure, p: float) -> FloatArray:
    z = NormalDist().inv_cdf(p)
    if measure == "var":
        return -(m.mean + z * m.std)
    return -m.mean + m.std * (math.exp(-0.5 * z * z) / _SQRT_2PI) / p


def _cornish_fisher(
    m: _Moments, measure: Measure, p: float
) -> tuple[FloatArray, NDArray[np.bool_]]:
    """(value, valid) per row; value is NaN where the local guard trips."""
    z = NormalDist().inv_cdf(p)
    z_low, z_high = cornish_fisher_range(measure, 1.0 - p)
    valid = cornish_fisher_monotone(m.skew, m.exkurt, z_high=z_high, z_low=z_low)
    g = cornish_fisher_quantile(z, m.skew, m.exkurt)
    if measure == "var":
        value = -(m.mean + g * m.std)
    else:
        tail = np.minimum(modified_tail_mean(g, p, m.skew, m.exkurt), g)  # floor at mVaR
        value = -(m.mean + tail * m.std)
    return np.where(valid, value, np.nan), valid


def _historical(sorted_rows: FloatArray, measure: Measure, level: float) -> FloatArray:
    k = historical_rank(sorted_rows.shape[1], level)
    q = sorted_rows[:, k - 1]
    if measure == "var":
        return -q
    in_tail = sorted_rows <= q[:, None]
    return -(np.where(in_tail, sorted_rows, 0.0).sum(axis=1) / in_tail.sum(axis=1))


def _var_of(method: Method, x_sorted: FloatArray, m: _Moments, level: float) -> FloatArray:
    p = tail_probability(level)
    if method == "historical":
        return _historical(x_sorted, "var", level)
    if method == "gaussian":
        return _gaussian(m, "var", p)
    # Unguarded: the tail count of a CVaR figure needs the mVaR even where VaR itself is n/a.
    g = cornish_fisher_quantile(NormalDist().inv_cdf(p), m.skew, m.exkurt)
    return -(m.mean + g * m.std)


def _evaluate(x: FloatArray, freq: Frequency) -> dict[tuple[Method, Measure, float], FloatArray]:
    """Every figure for every row of ``x`` (rows are samples); NaN marks a tripped CF guard."""
    x_sorted = np.sort(x, axis=1)
    m = _moments(x)
    out: dict[tuple[Method, Measure, float], FloatArray] = {}
    for measure, level in LEVELS[freq]:
        p = tail_probability(level)
        out[("historical", measure, level)] = _historical(x_sorted, measure, level)
        out[("gaussian", measure, level)] = _gaussian(m, measure, p)
        out[("cornish_fisher", measure, level)] = _cornish_fisher(m, measure, p)[0]
    return out


# ----------------------------------------------------------------------------- bootstrap
def politis_white_block_length(x: ArrayLike) -> float:
    """Stationary-bootstrap mean block length of Politis & White (2004), as corrected by
    Patton, Politis & White (2009). Floored at 1, capped at ``min(3 sqrt(n), n / 3)``.

    * ``K_N = max(5, ceil(log10 n))``, ``m_max = ceil(sqrt n) + K_N``, critical value
      ``2 sqrt(log10 n / n)``.
    * ``m_hat`` is the smallest lag after which ``K_N`` consecutive autocorrelations are all
      insignificant; ``M = min(2 max(m_hat, 1), m_max)``.
    * Flat-top window ``lambda(t) = 1`` for ``|t| <= 1/2``, ``2 (1 - |t|)`` up to 1.
    * ``G = sum lambda(k/M) |k| R(k)``, ``g(0) = sum lambda(k/M) R(k)`` over ``|k| <= M``,
      ``D_SB = 2 g(0)^2`` and ``b = (2 G^2 / D_SB)^(1/3) n^(1/3)``.
    """
    v = np.asarray(x, dtype=np.float64)
    n = v.size
    b_max = math.ceil(min(3.0 * math.sqrt(n), n / 3.0))
    e = v - v.mean()
    k_n = max(5, math.ceil(math.log10(n)))
    m_max = math.ceil(math.sqrt(n)) + k_n
    cv = 2.0 * math.sqrt(math.log10(n) / n)
    acov = np.array(
        [float(e[k:] @ e[: n - k]) / n if k < n else 0.0 for k in range(m_max + k_n + 1)]
    )
    if acov[0] <= 0.0:
        return 1.0
    rho = np.abs(acov / acov[0])
    m_hat: int | None = None
    for m in range(m_max + 1):
        if np.all(rho[m + 1 : m + 1 + k_n] < cv):
            m_hat = m
            break
    big_m = m_max if m_hat is None else min(2 * max(m_hat, 1), m_max)
    lags = np.arange(1, big_m + 1)
    t = lags / big_m
    lam = np.where(t <= 0.5, 1.0, 2.0 * (1.0 - t))
    g_sum = float(2.0 * np.sum(lam * lags * acov[1 : big_m + 1]))
    g0 = float(acov[0] + 2.0 * np.sum(lam * acov[1 : big_m + 1]))
    d_sb = 2.0 * g0**2
    if d_sb <= 0.0:
        return 1.0
    b = (2.0 * g_sum**2 / d_sb) ** (1.0 / 3.0) * n ** (1.0 / 3.0)
    return float(min(max(b, 1.0), b_max))


def stationary_bootstrap_indices(
    rng: np.random.Generator, n: int, resamples: int, mean_block_length: float
) -> NDArray[np.int64]:
    """``(resamples, n)`` indices of the Politis-Romano stationary bootstrap.

    A new block starts at each position with probability ``1 / mean_block_length`` (always at
    position 0), at a uniform random index; within a block indices advance by one, wrapping.
    """
    new = rng.random((resamples, n)) < 1.0 / mean_block_length
    new[:, 0] = True
    starts = rng.integers(0, n, size=(resamples, n))
    pos = np.arange(n)
    block_start = np.maximum.accumulate(np.where(new, pos, 0), axis=1)
    origin = np.take_along_axis(starts, block_start, axis=1)
    return np.asarray((origin + pos - block_start) % n, dtype=np.int64)


def _resample(
    x: FloatArray,
    freq: Frequency,
    n_resamples: int,
    seed: int,
    block: float | None,
) -> dict[tuple[Method, Measure, float], FloatArray]:
    rng = np.random.default_rng(seed)
    n = x.size
    chunks: list[dict[tuple[Method, Measure, float], FloatArray]] = []
    done = 0
    while done < n_resamples:
        size = min(_BATCH, n_resamples - done)
        if block is None:
            idx = rng.integers(0, n, size=(size, n))
        else:
            idx = stationary_bootstrap_indices(rng, n, size, block)
        chunks.append(_evaluate(x[idx], freq))
        done += size
    return {key: np.concatenate([c[key] for c in chunks]) for key in chunks[0]}


# ----------------------------------------------------------------------------- entry point
def tail_risk(
    returns: Sequence[float] | FloatArray,
    frequency: Frequency,
    *,
    n_resamples: int = 1000,
    seed: int = 0,
    band_level: float = 0.90,
    mean_block_length: float | None = None,
) -> TailRisk:
    """VaR and CVaR of a simple-return series by the historical, Gaussian and Cornish-Fisher
    methods, with bootstrap bands. See the module docstring for every convention.

    ``mean_block_length`` overrides the Politis-White rule for daily series and is ignored for
    monthly series. Raises ValueError on fewer than :data:`MIN_OBS` observations, non-finite
    values, returns at or below -100%, or a constant series.
    """
    if frequency not in LEVELS:
        raise ValueError(f"frequency must be 'daily' or 'monthly', got {frequency!r}")
    x = np.array(returns, dtype=np.float64).ravel()
    n = x.size
    if n < MIN_OBS:
        raise ValueError(f"tail risk needs at least {MIN_OBS} returns, got {n}")
    if not np.all(np.isfinite(x)):
        raise ValueError("returns must be finite")
    if np.any(x <= -1.0):
        raise ValueError("simple returns must be above -100%")
    if np.ptp(x) == 0.0:
        raise ValueError("returns are constant: tail risk is undefined")
    if n_resamples < 1:
        raise ValueError("n_resamples must be positive")
    if not 0.0 < band_level < 1.0:
        raise ValueError("band_level must be in (0, 1)")

    if frequency == "daily":
        block = (
            float(mean_block_length)
            if mean_block_length is not None
            else politis_white_block_length(np.abs(x - x.mean()))
        )
        if block < 1.0:
            raise ValueError("mean_block_length must be at least 1")
    else:
        block = None

    row = x[None, :]
    point = _evaluate(row, frequency)
    boot = _resample(x, frequency, n_resamples, seed, block)
    m = _moments(row)
    x_sorted = np.sort(row, axis=1)
    tail_q = ((1.0 - band_level) / 2.0, (1.0 + band_level) / 2.0)

    figures: list[TailFigure] = []
    for measure, level in LEVELS[frequency]:
        p = tail_probability(level)
        expected = n * p
        for method in METHODS:
            value = float(point[(method, measure, level)][0])
            reason: str | None = None
            indicative = False
            if method == "historical" and expected < MIN_EXPECTED_TAIL - 1e-9:
                reason = f"{expected:.1f} expected tail observations"
            elif method == "cornish_fisher" and math.isnan(value):
                reason = CF_INVALID
            if reason is not None:
                figures.append(
                    TailFigure(method, measure, level, None, reason, None, None, expected)
                )
                continue
            if method == "cornish_fisher" and not bool(
                cornish_fisher_globally_monotone(m.skew[0], m.exkurt[0])
            ):
                indicative = True
                reason = CF_INDICATIVE
            draws = boot[(method, measure, level)]
            draws = draws[np.isfinite(draws)]
            band = None
            if draws.size:
                low, high = np.quantile(draws, tail_q)
                band = Band(float(low), float(high), int(draws.size))
            var = float(_var_of(method, x_sorted, m, level)[0])
            count = int(np.count_nonzero(x <= -var))
            figures.append(
                TailFigure(method, measure, level, value, reason, band, count, expected, indicative)
            )

    return TailRisk(
        frequency=frequency,
        n_obs=n,
        mean=float(m.mean[0]),
        std=float(m.std[0]),
        skewness=float(m.skew[0]),
        excess_kurtosis=float(m.exkurt[0]),
        bootstrap="iid" if block is None else "stationary",
        mean_block_length=block,
        n_resamples=n_resamples,
        band_level=band_level,
        seed=seed,
        figures=tuple(figures),
    )
