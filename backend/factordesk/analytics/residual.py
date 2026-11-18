"""Residual (alpha) analysis: in-sample and point-in-time residual returns (methodology R1-R4, R6).

Spec: ``docs/methodology-residual-analysis.md``; oracle ``docs/test-oracle-residual-analysis.md``.

* ``u_t = y_t - beta_hat' f_t`` is the in-sample residual return (R1): the OLS residual plus
  alpha.
* ``u_tilde_t = y_t - beta_tilde_t' f_t`` is the point-in-time residual return (R4): the betas of
  day ``t`` come from the ``W`` rows ending on ``t-1`` (``rolling.ex_ante_betas``), so nothing
  estimated with day ``t`` or a later day enters day ``t``.
* The cumulative (compounded) lines, the summary statistics, the same-days gap with its verdict
  and the residual diagnostics are computed here. Stability (rolling alpha, non-overlapping
  windows, split halves, calendar years) lives in ``residual_stability.py``.

Pure: no I/O, no clock, no randomness. Inputs are not mutated. Rows excluded from the sample have
no residual and are never filled; a non-finite input is a contract violation (``ValueError``).
Whether a window can be fitted is decided upstream by ``rolling.rolling_ols_hac`` (a window that
fails the M3.1 design guard carries NaN betas, which ``point_in_time_residual`` reports as
``UnfittedWindowError``).
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any, Literal, cast

import numpy as np
import pandas as pd
from numpy.typing import NDArray
from statsmodels.stats.diagnostic import (  # pyright: ignore[reportMissingTypeStubs]
    acorr_ljungbox,  # pyright: ignore[reportUnknownVariableType]
    het_arch,  # pyright: ignore[reportUnknownVariableType]
)
from statsmodels.stats.stattools import (  # pyright: ignore[reportMissingTypeStubs]
    jarque_bera,  # pyright: ignore[reportUnknownVariableType]
)

from factordesk.analytics.regression import (
    ALPHA_LEVEL,
    Z_975,
    ZERO_SD_RELATIVE,
    A,
    FullSampleRegression,
    Tag,
    alpha_tag,
    hac_lags,
    hac_meat,
    two_sided_p,
)
from factordesk.analytics.rolling import RollingBetas, ex_ante_betas
from factordesk.analytics.sample import FACTOR_CODES, AnalysisSample
from factordesk.rounding import round_to_five_points

FloatArray = NDArray[np.float64]
Status = Literal["ok", "insufficient_data", "not_applicable", "failed"]
GapVerdictCode = Literal[
    "no_reliable_alpha",
    "point_in_time_only",
    "concentrated_in_warmup",
    "reversed",
    "mostly_disappears",
    "survives_not_significant",
    "survives",
]
VerdictSeverity = Literal["info", "warning"]

MIN_PIT_ROWS = 252
"""Minimum comparison span ``m_c = n - W`` for point-in-time statistics (R3.6, RD5)."""
SURVIVAL_THRESHOLD = 0.5
"""``s < 0.5`` means "mostly disappears" (R4.8, RD8)."""
WARMUP_SHARE_THRESHOLD = 0.5
"""``q < 0.5`` means the alpha was earned mainly in the warm-up (R4.8, RD8)."""
LB_LAGS = 10
ARCH_LAGS = 5
DRAG_CAP = 2.0
"""A survival ratio above this prints as "more than 200%" (R4.7)."""

_ljungbox = cast(Callable[..., Any], acorr_ljungbox)
_het_arch = cast(Callable[..., Any], het_arch)
_jarque_bera = cast(Callable[..., Any], jarque_bera)


class UnfittedWindowError(ValueError):
    """A trailing window after the warm-up could not be fitted (M3.1 design guard)."""


# ----------------------------------------------------------------------------- series (R1, R4)
def _check_finite(name: str, values: FloatArray) -> None:
    if not bool(np.isfinite(values).all()):
        raise ValueError(f"{name} must be finite; excluded rows are removed upstream, never filled")


def in_sample_residual(y: FloatArray, factors: FloatArray, betas: FloatArray) -> FloatArray:
    """``u_t = y_t - beta_hat' f_t`` on the rows of ``S`` (R1.1). ``y`` is the excess return."""
    yv = np.asarray(y, dtype=np.float64)
    f = np.asarray(factors, dtype=np.float64)
    b = np.asarray(betas, dtype=np.float64)
    _check_finite("y", yv)
    _check_finite("factors", f)
    _check_finite("betas", b)
    return np.asarray(yv - f @ b, dtype=np.float64)


def point_in_time_betas(rolling: RollingBetas) -> FloatArray:
    """``beta_tilde_t = beta_hat_{t-1}``, shape ``(n, 5)``; NaN on the ``W`` warm-up rows (R4.1)."""
    return ex_ante_betas(rolling).to_numpy(dtype=np.float64)


def point_in_time_residual(y: FloatArray, factors: FloatArray, rolling: RollingBetas) -> FloatArray:
    """``u_tilde_t = y_t - beta_tilde_t' f_t`` for rows ``W+1 .. n``; NaN on rows ``1 .. W`` (R4.1).

    ``rolling`` is the M4 result for window ``W`` on the same sample; it is not refitted.
    """
    yv = np.asarray(y, dtype=np.float64)
    f = np.asarray(factors, dtype=np.float64)
    _check_finite("y", yv)
    _check_finite("factors", f)
    w = rolling.window
    n = len(yv)
    if n <= w:
        raise ValueError(f"point-in-time residual needs more than {w} rows, got {n}")
    beta_tilde = point_in_time_betas(rolling)
    live = beta_tilde[w:]
    if not bool(np.isfinite(live).all()):
        raise UnfittedWindowError(
            f"a trailing {w}-day window could not be fitted (singular factor design)"
        )
    out = np.full(n, np.nan, dtype=np.float64)
    out[w:] = yv[w:] - np.einsum("ij,ij->i", live, f[w:])
    return out


# ----------------------------------------------------------------------------- cumulative (R2)
@dataclass(frozen=True)
class CompoundPath:
    """The residual wealth index ``Q_j`` (``Q_0 = 1`` is not stored) and the wipe-out row."""

    wealth: FloatArray
    wipe_out: int | None
    """Position of the first row with ``1 + x <= 0`` (R2.6); ``Q`` is 0 from there on."""

    @property
    def cumulative(self) -> FloatArray:
        """``CR_j = Q_j - 1``."""
        return np.asarray(self.wealth - 1.0, dtype=np.float64)


def compound_path(x: FloatArray) -> CompoundPath:
    """``Q_j = prod (1 + x_i)`` with the wipe-out rule of R2.6."""
    xv = np.asarray(x, dtype=np.float64)
    _check_finite("x", xv)
    growth = 1.0 + xv
    dead = np.flatnonzero(growth <= 0.0)
    wealth = np.cumprod(growth)
    wipe: int | None = None
    if dead.size:
        wipe = int(dead[0])
        wealth[wipe:] = 0.0
    return CompoundPath(wealth=np.asarray(wealth, dtype=np.float64), wipe_out=wipe)


@dataclass(frozen=True)
class DrawdownInfo:
    """Maximum drawdown of a wealth path that starts at ``Q_0 = 1`` (R3.1)."""

    depth: float
    peak: date | None
    """``None``: the start of the span (``Q_0``), or no drawdown."""
    trough: date | None
    recovery: date | None


def max_drawdown(wealth: FloatArray, dates: Sequence[date]) -> DrawdownInfo:
    """``min_j (Q_j / max_{i<=j} Q_i - 1)`` with ``Q_0 = 1`` included, and its three dates."""
    full = np.concatenate([[1.0], np.asarray(wealth, dtype=np.float64)])
    running = np.maximum.accumulate(full)
    dd = full / running - 1.0
    trough = int(np.argmin(dd))
    depth = float(dd[trough])
    if depth == 0.0:
        return DrawdownInfo(depth=0.0, peak=None, trough=None, recovery=None)
    peak_level = running[trough]
    peak = int(np.flatnonzero(full[: trough + 1] == peak_level)[-1])
    after = np.flatnonzero(full[trough + 1 :] >= peak_level)
    recovery = trough + 1 + int(after[0]) if after.size else None
    return DrawdownInfo(
        depth=depth,
        peak=None if peak == 0 else dates[peak - 1],
        trough=dates[trough - 1],
        recovery=None if recovery is None else dates[recovery - 1],
    )


def noise_drawdown_reference(vol_annual: float, m: int) -> float:
    """``-(1 - exp(-sqrt(pi/2) sigma sqrt(m/A)))``: the drawdown of pure noise (R3.4)."""
    return -(1.0 - math.exp(-math.sqrt(math.pi / 2.0) * vol_annual * math.sqrt(m / A)))


# ----------------------------------------------------------------------------- statistics (R3)
@dataclass(frozen=True)
class LocationTest:
    """Inference on the mean daily residual, annualised (R3.2)."""

    hac_lags: int
    mean_annual: float
    se_annual: float
    ci_low_annual: float
    ci_high_annual: float
    z: float
    p: float
    tag: Tag


def hac_location_test(x: FloatArray) -> LocationTest:
    """OLS of ``x`` on a constant with Newey-West HAC, lags ``L(m)`` (R3.2).

    Equals ``sm.OLS(x, ones).fit(cov_type="HAC", cov_kwds={"maxlags": L, "use_correction": False},
    use_t=False)``: the constant-only case of ``regression.ols_hac``.
    """
    xv = np.asarray(x, dtype=np.float64)
    _check_finite("x", xv)
    m = len(xv)
    lags = hac_lags(m)
    mean = float(xv.mean())
    meat = float(hac_meat((xv - mean)[:, None], lags)[0, 0])
    se = math.sqrt(meat) / m
    z = mean / se
    p = float(two_sided_p(np.array([z]))[0])
    return LocationTest(
        hac_lags=lags,
        mean_annual=A * mean,
        se_annual=A * se,
        ci_low_annual=A * (mean - Z_975 * se),
        ci_high_annual=A * (mean + Z_975 * se),
        z=z,
        p=p,
        tag=alpha_tag(p),
    )


def regression_location(reg: FullSampleRegression) -> LocationTest:
    """The in-sample location test: the M3 alpha test, copied, not recomputed (R3.2, RD2)."""
    fit = reg.fit
    return LocationTest(
        hac_lags=fit.lags,
        mean_annual=reg.alpha_ann,
        se_annual=reg.alpha_se_ann,
        ci_low_annual=reg.alpha_ci_ann[0],
        ci_high_annual=reg.alpha_ci_ann[1],
        z=float(fit.zvalues[0]),
        p=float(fit.pvalues[0]),
        tag=reg.alpha_tag,
    )


@dataclass(frozen=True)
class ResidualSummary:
    """R3.1 summary of one residual series. Every number is ``None`` unless ``status == "ok"``."""

    status: Status
    reason: str | None
    n: int
    hac_lags: int | None = None
    residual_return_annual: float | None = None
    residual_return_se_annual: float | None = None
    residual_return_ci_low_annual: float | None = None
    residual_return_ci_high_annual: float | None = None
    z: float | None = None
    p: float | None = None
    tag: Tag | None = None
    residual_vol_annual: float | None = None
    information_ratio: float | None = None
    information_ratio_ci_low: float | None = None
    information_ratio_ci_high: float | None = None
    cumulative_return: float | None = None
    compound_growth_annual: float | None = None
    hit_rate: float | None = None
    max_drawdown: float | None = None
    max_drawdown_peak: date | None = None
    max_drawdown_trough: date | None = None
    max_drawdown_recovery: date | None = None
    noise_drawdown_reference: float | None = None
    skew: float | None = None
    excess_kurtosis: float | None = None
    wiped_out: bool = False
    wipe_out_date: date | None = None


def unavailable_summary(status: Status, reason: str, n: int = 0) -> ResidualSummary:
    """A summary that holds no number (not ok)."""
    return ResidualSummary(status=status, reason=reason, n=n)


def central_moments(x: FloatArray) -> tuple[float, float]:
    """``(skew, excess kurtosis)`` from central moments with divisor ``m`` (R3.1)."""
    xv = np.asarray(x, dtype=np.float64)
    c = xv - xv.mean()
    m2 = float(np.mean(c**2))
    m3 = float(np.mean(c**3))
    m4 = float(np.mean(c**4))
    return m3 / m2**1.5, m4 / m2**2 - 3.0


def is_constant(x: FloatArray) -> bool:
    """True when the series has (numerically) zero spread."""
    xv = np.asarray(x, dtype=np.float64)
    if xv.size < 2:
        return True
    top = float(np.max(np.abs(xv)))
    sd = float(np.std(xv, ddof=1))
    return sd <= ZERO_SD_RELATIVE * top if top > 0.0 else True


def summarise(x: FloatArray, dates: Sequence[date], location: LocationTest) -> ResidualSummary:
    """Summary statistics of a residual series ``x`` over its span (R3.1).

    ``location`` carries the inference on the mean: the M3 alpha test for the in-sample series,
    ``hac_location_test(x)`` for the point-in-time series. ``dates`` are the dates of ``x``.
    """
    xv = np.asarray(x, dtype=np.float64)
    _check_finite("x", xv)
    m = len(xv)
    if len(dates) != m:
        raise ValueError("x and dates must have the same length")
    if is_constant(xv):
        return unavailable_summary("not_applicable", "residual is constant", m)
    path = compound_path(xv)
    wiped = path.wipe_out is not None
    vol = math.sqrt(A) * float(np.std(xv, ddof=1))
    skew, kurt = central_moments(xv)
    dd = max_drawdown(path.wealth, dates)
    final = float(path.wealth[-1])
    growth = -1.0 if wiped else final ** (A / m) - 1.0
    return ResidualSummary(
        status="ok",
        reason=None,
        n=m,
        hac_lags=location.hac_lags,
        residual_return_annual=location.mean_annual,
        residual_return_se_annual=location.se_annual,
        residual_return_ci_low_annual=location.ci_low_annual,
        residual_return_ci_high_annual=location.ci_high_annual,
        z=location.z,
        p=location.p,
        tag=location.tag,
        residual_vol_annual=vol,
        information_ratio=location.mean_annual / vol,
        information_ratio_ci_low=location.ci_low_annual / vol,
        information_ratio_ci_high=location.ci_high_annual / vol,
        cumulative_return=final - 1.0,
        compound_growth_annual=growth,
        hit_rate=float(np.count_nonzero(xv > 0.0)) / m,
        max_drawdown=dd.depth,
        max_drawdown_peak=dd.peak,
        max_drawdown_trough=dd.trough,
        max_drawdown_recovery=dd.recovery,
        noise_drawdown_reference=noise_drawdown_reference(vol, m),
        skew=skew,
        excess_kurtosis=kurt,
        wiped_out=wiped,
        wipe_out_date=None if path.wipe_out is None else dates[path.wipe_out],
    )


# ----------------------------------------------------------------------------- gap, verdict (R4)
@dataclass(frozen=True)
class GapStats:
    """Same-days comparison on ``S_c`` (R4.7). Numbers are ``None`` unless ``status == "ok"``."""

    status: Status
    reason: str | None
    in_sample_same_days_annual: float | None = None
    point_in_time_annual: float | None = None
    gap_annual: float | None = None
    gap_se_annual: float | None = None
    gap_z: float | None = None
    gap_p: float | None = None
    comparison_share_of_alpha: float | None = None
    survival_ratio: float | None = None
    verdict: GapVerdictCode | None = None
    severity: VerdictSeverity | None = None


@dataclass(frozen=True)
class Verdict:
    """The decision of R4.8 with the two ratios it used."""

    code: GapVerdictCode
    severity: VerdictSeverity
    comparison_share: float | None
    """``q = a_c / alpha_ann``; ``None`` if ``alpha_ann = 0``."""
    survival_ratio: float | None
    """``s = a_pit / a_c``; ``None`` if ``a_c = 0``."""


def decide_verdict(
    alpha_ann: float,
    p_is: float,
    a_c: float,
    a_pit: float,
    p_pit: float,
    *,
    in_sample_reliable: bool | None = None,
) -> Verdict:
    """First matching rule of R4.8 (G1-G7). Thresholds are fixed (RD8).

    ``in_sample_reliable`` is the quality-gated alpha tag of the in-sample regression
    (``reg.alpha_tag == "reliable"``): the same tag the in-sample column shows, so the chip and
    the verdict cannot disagree. When it is left out the daily p-value ``p_is`` decides.
    """
    q = None if alpha_ann == 0.0 else a_c / alpha_ann
    s = None if a_c == 0.0 else a_pit / a_c
    is_reliable = p_is < ALPHA_LEVEL if in_sample_reliable is None else in_sample_reliable
    code: GapVerdictCode
    if not is_reliable and p_pit >= ALPHA_LEVEL:
        code = "no_reliable_alpha"
    elif not is_reliable:
        code = "point_in_time_only"
    elif alpha_ann * a_c <= 0.0 or (q is not None and q < WARMUP_SHARE_THRESHOLD):
        code = "concentrated_in_warmup"
    elif s is not None and s < 0.0:
        code = "reversed"
    elif s is not None and s < SURVIVAL_THRESHOLD:
        code = "mostly_disappears"
    elif p_pit >= ALPHA_LEVEL:
        code = "survives_not_significant"
    else:
        code = "survives"
    severity: VerdictSeverity = "warning" if code in ("reversed", "mostly_disappears") else "info"
    return Verdict(code=code, severity=severity, comparison_share=q, survival_ratio=s)


def percent_text(value: float) -> str:
    """``+1.8%``: signed percentage with one decimal (R4.8 copy)."""
    return f"{value * 100:+.1f}%"


def ratio_text(ratio: float) -> str:
    """A survival ratio as a percentage rounded to 5 points (half away from zero), capped (R4.7)."""
    if ratio > DRAG_CAP:
        return "more than 200%"
    points = round_to_five_points(ratio)
    return f"{'-' if ratio < 0 and points > 0 else ''}{points}%"


def verdict_message(
    code: GapVerdictCode,
    *,
    a_c: float,
    a_pit: float,
    survival_ratio: float | None,
    window: int,
    warmup_start: date,
    warmup_end: date,
) -> str:
    """The exact copy of R4.8 for ``code``, placeholders filled.

    Wording follows the owner's decision of 2026-11-18: user text says "holds up out-of-sample"
    where the specification said "survives".
    """
    s_text = "" if survival_ratio is None else ratio_text(survival_ratio)
    if code == "no_reliable_alpha":
        return "Neither residual return can be told apart from zero. Read both lines as noise."
    if code == "point_in_time_only":
        sign = "positive" if a_pit > 0 else "negative"
        return (
            f"The point-in-time residual return is reliably {sign} ({percent_text(a_pit)} a year), "
            "but the full-period alpha is not. This usually means the betas moved; check the "
            "Exposures tab."
        )
    if code == "concentrated_in_warmup":
        return (
            f"Most of the in-sample alpha comes from the first {window} trading days "
            f"({warmup_start} to {warmup_end}), before any point-in-time residual exists. You "
            "cannot check it here."
        )
    if code == "reversed":
        return (
            "In-sample alpha does not hold up out-of-sample: with point-in-time betas the "
            f"residual return has the opposite sign ({percent_text(a_pit)} a year against "
            f"{percent_text(a_c)} on the same days)."
        )
    if code == "mostly_disappears":
        return (
            "In-sample alpha mostly disappears out-of-sample: point-in-time betas keep "
            f"{s_text} of it ({percent_text(a_pit)} a year against {percent_text(a_c)} on the "
            "same days)."
        )
    if code == "survives_not_significant":
        return (
            f"Most of the in-sample alpha holds up out-of-sample ({s_text} kept with "
            "point-in-time betas), but the point-in-time residual return cannot be told apart "
            "from zero."
        )
    return (
        f"In-sample alpha holds up out-of-sample with point-in-time betas ({s_text} kept) and is "
        "distinguishable from zero. This rules out hindsight in the betas, not luck."
    )


def gap_statistics(
    u: FloatArray,
    u_tilde: FloatArray | None,
    window: int,
    reg: FullSampleRegression,
    pit: ResidualSummary,
    dates: Sequence[date],
) -> tuple[GapStats, str | None]:
    """R4.7 and R4.8 on the comparison span (rows ``W+1 .. n``); also returns the verdict copy.

    ``u`` and ``u_tilde`` have the length of ``S``; ``u_tilde`` is NaN on the warm-up rows and
    ``None`` when the point-in-time series is not available. ``pit`` is the point-in-time
    summary: when it is not ok the gap is not ok either, with the same reason.
    """
    if pit.status != "ok" or u_tilde is None:
        return GapStats(status=pit.status, reason=pit.reason or "no point-in-time series"), None
    uc = np.asarray(u, dtype=np.float64)[window:]
    pc = np.asarray(u_tilde, dtype=np.float64)[window:]
    gap = uc - pc
    a_c = A * float(uc.mean())
    a_pit = A * float(pc.mean())
    if is_constant(gap):
        gap_test: LocationTest | None = None
    else:
        gap_test = hac_location_test(gap)
    assert pit.p is not None
    verdict = decide_verdict(
        reg.alpha_ann,
        float(reg.fit.pvalues[0]),
        a_c,
        a_pit,
        pit.p,
        in_sample_reliable=reg.alpha_tag == "reliable",
    )
    message = verdict_message(
        verdict.code,
        a_c=a_c,
        a_pit=a_pit,
        survival_ratio=verdict.survival_ratio,
        window=window,
        warmup_start=dates[0],
        warmup_end=dates[window - 1],
    )
    return (
        GapStats(
            status="ok",
            reason=None,
            in_sample_same_days_annual=a_c,
            point_in_time_annual=a_pit,
            gap_annual=a_c - a_pit,
            gap_se_annual=None if gap_test is None else gap_test.se_annual,
            gap_z=None if gap_test is None else gap_test.z,
            gap_p=None if gap_test is None else gap_test.p,
            comparison_share_of_alpha=verdict.comparison_share,
            survival_ratio=verdict.survival_ratio,
            verdict=verdict.code,
            severity=verdict.severity,
        ),
        message,
    )


# ----------------------------------------------------------------------------- diagnostics (R6)
FINDING_LB = (
    "Residual returns are correlated from day to day. The t-statistics allow for this.",
    "No clear day-to-day correlation in residual returns.",
)
FINDING_JB = (
    "Residual returns have more extreme days than a normal distribution. Intervals are "
    "approximate.",
    "No clear departure from a normal distribution.",
)
FINDING_ARCH = (
    "Residual volatility comes in clusters: calm and turbulent periods alternate. One volatility "
    "number averages them.",
    "No clear clustering of residual volatility.",
)


@dataclass(frozen=True)
class DiagnosticsSummary:
    """R6 tests on a demeaned residual series. Numbers are ``None`` unless ``status == "ok"``."""

    status: Status
    reason: str | None
    ljung_box_stat: float | None = None
    ljung_box_p: float | None = None
    jarque_bera_stat: float | None = None
    jarque_bera_p: float | None = None
    arch_lm_stat: float | None = None
    arch_lm_p: float | None = None
    findings: tuple[str, ...] = ()


def series_diagnostics(demeaned: FloatArray) -> DiagnosticsSummary:
    """Ljung-Box (lag 10), Jarque-Bera and Engle ARCH (5 lags) on a series with mean zero (R6).

    The caller demeans: Engle's test uses squares and is not invariant to a constant.
    """
    e = np.asarray(demeaned, dtype=np.float64)
    _check_finite("demeaned residual", e)
    if is_constant(e):
        return DiagnosticsSummary(status="not_applicable", reason="residual is constant")
    lb: Any = _ljungbox(e, lags=[LB_LAGS], return_df=True)
    lb_stat = float(lb["lb_stat"].iloc[0])
    lb_p = float(lb["lb_pvalue"].iloc[0])
    jb: Any = _jarque_bera(e)
    jb_stat, jb_p = float(jb[0]), float(jb[1])
    arch: Any = _het_arch(e, nlags=ARCH_LAGS, ddof=0, store=False, result_object=True)
    arch_stat, arch_p = float(arch.lm), float(arch.lmpval)
    findings = (
        FINDING_LB[0] if lb_p < ALPHA_LEVEL else FINDING_LB[1],
        FINDING_JB[0] if jb_p < ALPHA_LEVEL else FINDING_JB[1],
        FINDING_ARCH[0] if arch_p < ALPHA_LEVEL else FINDING_ARCH[1],
    )
    return DiagnosticsSummary(
        status="ok",
        reason=None,
        ljung_box_stat=lb_stat,
        ljung_box_p=lb_p,
        jarque_bera_stat=jb_stat,
        jarque_bera_p=jb_p,
        arch_lm_stat=arch_stat,
        arch_lm_p=arch_p,
        findings=findings,
    )


# ----------------------------------------------------------------------------- orchestration
@dataclass(frozen=True)
class ResidualChartSeries:
    """The three cumulative lines of R2.3 on the dates of ``S`` (``None``: no value)."""

    in_sample_full: tuple[float, ...]
    comparison_start: date | None
    in_sample_compare: tuple[float | None, ...]
    point_in_time_compare: tuple[float | None, ...]
    n_excluded_in_span: int
    n_uncovered: int
    uncovered_from: date | None


@dataclass(frozen=True)
class ResidualResult:
    """Everything the residual section shows that comes from the two residual series."""

    window: int
    dates: tuple[date, ...]
    u: FloatArray
    u_tilde: FloatArray | None
    """Length ``n``, NaN on the warm-up rows; ``None`` when the point-in-time series is not ok."""
    in_sample: ResidualSummary
    point_in_time: ResidualSummary
    gap: GapStats
    gap_message: str | None
    chart: ResidualChartSeries
    diagnostics_in_sample: DiagnosticsSummary
    diagnostics_point_in_time: DiagnosticsSummary
    wipeouts: tuple[date, ...]
    """Dates of the wipe-outs of the in-sample and the point-in-time series (R2.6), if any."""


def pit_unavailable_reason(window: int, n: int) -> str:
    """R3.6 reason when the comparison span is shorter than 252 rows."""
    return (
        f"Point-in-time residual needs at least {window + MIN_PIT_ROWS} trading days; this "
        f"period has {n}."
    )


def _compare_line(x: FloatArray, window: int, n: int) -> tuple[float | None, ...]:
    """Anchor ``0.0`` at row ``W``, ``None`` before, compounded ``CR`` of ``x[W:]`` after (R2.3)."""
    path = compound_path(x[window:])
    line = (*([None] * (window - 1)), 0.0, *(float(v) for v in path.cumulative))
    assert len(line) == n
    return line


def _date_list(index: pd.Index) -> tuple[date, ...]:
    return tuple(pd.Timestamp(ts).date() for ts in index)


def residual_analysis(
    sample: AnalysisSample, reg: FullSampleRegression, rolling: RollingBetas, *, exact_fit: bool
) -> ResidualResult:
    """The in-sample and point-in-time residual analysis of one sample (R1-R4, R6).

    ``reg`` is the full-sample regression whose alpha the in-sample column copies (R3.2);
    ``rolling`` is the M4 result for ``W = beta_window`` (its window is ``W``). ``exact_fit``
    says the regression fits to rounding (M3.5), so residual diagnostics are not applicable.
    """
    y = sample.xret.to_numpy(dtype=np.float64)
    f = sample.factors.loc[:, list(FACTOR_CODES)].to_numpy(dtype=np.float64)
    n = len(y)
    w = rolling.window
    dates = _date_list(sample.xret.index)
    u = in_sample_residual(y, f, reg.betas)
    in_sample = summarise(u, dates, regression_location(reg))

    u_tilde: FloatArray | None = None
    pit: ResidualSummary
    if n - w < MIN_PIT_ROWS:
        pit = unavailable_summary("insufficient_data", pit_unavailable_reason(w, n), max(n - w, 0))
    else:
        try:
            u_tilde = point_in_time_residual(y, f, rolling)
        except UnfittedWindowError as err:
            pit = unavailable_summary("failed", str(err), n - w)
        else:
            span = u_tilde[w:]
            if is_constant(span):
                pit = unavailable_summary("not_applicable", "residual is constant", n - w)
                u_tilde = None
            else:
                pit = summarise(span, dates[w:], hac_location_test(span))

    gap, message = gap_statistics(u, u_tilde, w, reg, pit, dates)

    in_path = compound_path(u)
    full_line = tuple(float(v) for v in in_path.cumulative)
    pit_ok = pit.status == "ok" and u_tilde is not None
    chart = ResidualChartSeries(
        in_sample_full=full_line,
        comparison_start=dates[w - 1] if pit_ok else None,
        in_sample_compare=_compare_line(u, w, n) if pit_ok else (None,) * n,
        point_in_time_compare=(
            _compare_line(u_tilde, w, n) if pit_ok and u_tilde is not None else (None,) * n
        ),
        n_excluded_in_span=sum(1 for ex in sample.excluded if dates[0] <= ex.date <= dates[-1]),
        n_uncovered=sample.uncovered.n,
        uncovered_from=sample.uncovered.first,
    )

    diag_in = (
        DiagnosticsSummary(
            status="not_applicable",
            reason=(
                "the regression fits the data exactly, so the residuals are rounding noise and "
                "residual diagnostics mean nothing"
            ),
        )
        if exact_fit
        else series_diagnostics(np.asarray(reg.fit.resid, dtype=np.float64))
    )
    if u_tilde is not None and pit.status == "ok":
        span = u_tilde[w:]
        diag_pit = series_diagnostics(span - float(span.mean()))
    else:
        diag_pit = DiagnosticsSummary(status=pit.status, reason=pit.reason)

    wipeouts = tuple(d for d in (in_sample.wipe_out_date, pit.wipe_out_date) if d is not None)
    return ResidualResult(
        window=w,
        dates=dates,
        u=u,
        u_tilde=u_tilde,
        in_sample=in_sample,
        point_in_time=pit,
        gap=gap,
        gap_message=message,
        chart=chart,
        diagnostics_in_sample=diag_in,
        diagnostics_point_in_time=diag_pit,
        wipeouts=wipeouts,
    )
