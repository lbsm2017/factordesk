"""End-to-end report builder: data layer -> analysis sample -> analytics -> ``FactorReport``.

Order of work: factor data, then prices (repeated dates collapsed to their first bar and
recorded), the price audit, the aligned sample (M2), the full-sample regression (M3), its
residual diagnostics and quality gate with the 5-day estimate when the gate fires (M3.5-M3.6),
rolling betas (M4) and average beta (M5), return and risk contribution (M6.1, M6.4, M7), and
last the optional sections of the schema v3 contract, one hook each (``section_hooks/``,
``docs/specs/schema-v3-contract.md`` SC3.2).
Providers, the factor frame and the clock are injectable so the whole path runs offline in
tests. Inputs that cannot support a regression raise ``DegenerateInputError`` (D30).
"""

from __future__ import annotations

import dataclasses
import math
from collections.abc import Iterable, Sequence
from datetime import UTC, date, datetime

import numpy as np
import pandas as pd

from factordesk.analytics.attribution import (
    memo_rows,
    return_contribution_for,
    risk_contribution_for,
    risk_order,
    risk_sentences,
)
from factordesk.analytics.diagnostics import (
    HORIZON,
    MIN_BLOCKS,
    RHO_GATE,
    Z_GATE,
    ChiSquareTest,
    DiagnosticsResult,
    GateResult,
    MultiDayFit,
    apply_gate,
    exact_fit,
    multi_day_regression,
    quality_gate,
    residual_diagnostics,
)
from factordesk.analytics.diagnostics import (
    NOTE as DIAGNOSTICS_NOTE,
)
from factordesk.analytics.regression import Z_975, FullSampleRegression, run_regression
from factordesk.analytics.rolling import (
    PRIMARY_WINDOW,
    WINDOWS,
    RollingBetas,
    average_beta,
    rolling_betas,
)
from factordesk.analytics.sample import (
    DISPLAY_NAMES,
    FACTOR_CODES,
    AnalysisSample,
    build_sample,
)
from factordesk.data import factors as factor_data
from factordesk.data.audit import AuditReport, audit_prices
from factordesk.data.prices import (
    PriceHistory,
    PriceProvider,
    YFinanceProvider,
    collapse_duplicate_dates,
    validate_ticker,
)
from factordesk.report.schema import (
    AuditFinding,
    AuditStatus,
    AverageBeta,
    AverageBetaPanel,
    CorrPair,
    DataInfo,
    DiagnosticCode,
    DiagnosticTest,
    ExcludedRow,
    FactorReport,
    FactorStat,
    FactorVintage,
    LabelKey,
    MultiDayRegression,
    PriceSeries,
    QualityGate,
    Regression,
    ReportWarning,
    ResidualDiagnostics,
    ReturnContribution,
    RiskContribution,
    RiskFactorDetail,
    RollingWindow,
    SampleInfo,
    Severity,
    Status,
    UncoveredTail,
    report_label_text,
)
from factordesk.section_hooks import fragility as fragility_hook
from factordesk.section_hooks import kalman as kalman_hook
from factordesk.section_hooks import lead_lag as lead_lag_hook
from factordesk.section_hooks import load_section_inputs
from factordesk.section_hooks import residual_alpha as residual_alpha_hook
from factordesk.section_hooks import shrunk as shrunk_hook
from factordesk.section_hooks import world_beta as world_beta_hook
from factordesk.section_hooks.context import CoreSections, SectionContext, SectionInputs

STALE_AFTER_DAYS = factor_data.STALE_AFTER_DAYS

NOTE_VINTAGE = "Uses the current Fama-French data vintage; historical factor values can be revised."
NOTE_SURVIVORSHIP = (
    "Only tickers that exist today can be analysed. Results for survivors are not "
    "representative of companies that were delisted."
)
NOTE_US_FACTORS = (
    "The factors are US Fama-French factors in USD. Applied to a non-US stock or a non-USD "
    "price series, betas mix factor exposure with currency and local-market effects; this "
    "version does not check the ticker's currency."
)
NOTE_DESC = "Every statistic is descriptive and in-sample, not predictive."

_SEVERITY: dict[str, Severity] = {"info": "info", "warn": "warning", "error": "error"}


# ----------------------------------------------------------------------------- helpers
def _finite(x: float) -> float:
    """A statistic that must exist: fail loudly rather than serialise NaN (M0.7)."""
    v = float(x)
    if not math.isfinite(v):
        raise ArithmeticError(f"non-finite statistic {v!r} in an 'ok' result")
    return v


def _optional_finite(x: float | None) -> float | None:
    """None stays None (status not_applicable at field level); numbers must be finite."""
    return None if x is None else _finite(x)


ROLLING_SIG_DIGITS = 6
"""Significant digits kept for per-stamp rolling series in the report (M14, D31)."""


def _round_sig(x: float, digits: int = ROLLING_SIG_DIGITS) -> float:
    """``x`` rounded to ``digits`` significant digits (relative error at most 5e-6 for 6)."""
    return float(f"{x:.{digits}g}")


def _series(values: Iterable[float], warmup: int) -> list[float | None]:
    """Rolling series, rounded to 6 significant digits; NaN only in the first ``warmup`` rows."""
    out: list[float | None] = []
    for i, v in enumerate(values):
        fv = float(v)
        if math.isfinite(fv):
            out.append(_round_sig(fv))
        elif i < warmup:
            out.append(None)
        else:
            raise ArithmeticError(f"non-finite rolling value after warm-up at position {i}")
    return out


def _dates(index: pd.Index) -> list[date]:
    return [pd.Timestamp(ts).date() for ts in index]


def _sample_info(
    sample: AnalysisSample, vintage: FactorVintage, window: int | None = None
) -> SampleInfo:
    return SampleInfo(
        n=sample.n,
        start=sample.start,
        end=sample.end,
        requested_start=sample.requested_start,
        requested_end=sample.requested_end,
        window=window,
        n_excluded=len(sample.excluded),
        excluded=[ExcludedRow(date=e.date, reason=e.reason) for e in sample.excluded],
        factor_vintage=vintage,
    )


def _labels(*keys: LabelKey) -> list[LabelKey]:
    return list(keys)


def _audit_status(report: AuditReport) -> AuditStatus:
    severities = {f.severity for f in report.findings}
    if "error" in severities:
        return "errors"
    if "warn" in severities:
        return "warnings"
    return "clean"


# ----------------------------------------------------------------------------- sections
def _regression_section(
    reg: FullSampleRegression, info: SampleInfo, gate_fired: bool = False
) -> Regression:
    fit = reg.fit
    factors = [
        FactorStat(
            name=reg.names[i],
            beta=_finite(fit.params[i + 1]),
            se=_finite(fit.bse[i + 1]),
            z=_finite(fit.zvalues[i + 1]),
            p=_finite(fit.pvalues[i + 1]),
            p_adj_bh=_finite(reg.beta_p_adj[i]),
            ci_low=_finite(fit.ci_low[i + 1]),
            ci_high=_finite(fit.ci_high[i + 1]),
            tag=reg.beta_tags[i],
            interpretation=reg.interpretations[i],
        )
        for i in range(len(reg.names))
    ]
    col = reg.collinearity
    caption = (
        f"In-sample: uses the whole window ({info.start} to {info.end}, n = {info.n}). "
        f"Newey-West HAC standard errors with {fit.lags} lags, normal reference distribution. "
        "Betas are tagged reliable when significant after a Benjamini-Hochberg correction "
        "across the 5 betas (q = 0.05); alpha is a single test at 5%. Bars show the 95% "
        "interval for each beta on its own (not adjusted for multiple testing)."
    )
    if gate_fired:
        caption += (
            " The residual quality gate fired, so a coefficient is tagged reliable only if the "
            "daily and the 5-day tests both reject."
        )
    return Regression(
        status="ok",
        reason=None,
        sample=info,
        labels=_labels("L-DESC"),
        caption=caption,
        alpha_annual=_finite(reg.alpha_ann),
        alpha_se_annual=_finite(reg.alpha_se_ann),
        alpha_z=_finite(fit.zvalues[0]),
        alpha_p=_finite(fit.pvalues[0]),
        alpha_ci_low_annual=_finite(reg.alpha_ci_ann[0]),
        alpha_ci_high_annual=_finite(reg.alpha_ci_ann[1]),
        alpha_tag=reg.alpha_tag,
        alpha_sentence=reg.alpha_sentence,
        r2=_finite(fit.rsquared),
        adj_r2=_finite(fit.rsquared_adj),
        sigma_e_annual=_finite(reg.sigma_e_ann),
        hac_lags=fit.lags,
        bh_family_size=len(reg.names),
        factors=factors,
        vif={k: _finite(v) for k, v in col.vif.items()},
        condition_number=_finite(col.kappa),
        high_corr_pairs=[CorrPair(a=a, b=b, corr=_finite(c)) for a, b, c in col.high_corr_pairs],
    )


def _rolling_section(rb: RollingBetas, info: SampleInfo) -> RollingWindow:
    warm = rb.window - 1
    estimated = rb.betas.iloc[warm:].notna().all(axis=1).to_numpy(dtype=bool)
    if not estimated.all():
        bad = pd.DatetimeIndex(rb.betas.index[warm:][~estimated])
        return RollingWindow(
            status="failed",
            reason=(
                f"{len(bad)} of {len(estimated)} windows of {rb.window} days have a factor "
                "matrix that is singular or nearly so (a factor is constant within the window "
                f"or a combination of the others; first window ending {bad[0].date()}); rolling "
                "betas for this window length are not reported"
            ),
            sample=info,
            labels=_labels("L-DESC", "L-BAND", "L-OVERLAP"),
            caption=f"Each point uses the previous {rb.window} trading days, ending on that date.",
            window=rb.window,
            n_stamps=0,
            hac_lags=0,
            ci_z=None,
            dates=[],
            window_start=[],
            betas={},
            se={},
        )
    window_start: list[date | None] = [
        None if pd.isna(ts) else pd.Timestamp(ts).date() for ts in rb.window_start
    ]
    caption = (
        f"Each point uses the previous {rb.window} trading days, ending on that date "
        f"(exactly {rb.window} rows of the sample, HAC lags {rb.lags}). The first "
        f"{rb.window - 1} days have no estimate (warm-up)."
    )
    return RollingWindow(
        status="ok",
        reason=None,
        sample=info,
        labels=_labels("L-DESC", "L-BAND", "L-OVERLAP"),
        caption=caption,
        window=rb.window,
        n_stamps=rb.n_stamps,
        hac_lags=rb.lags,
        ci_z=Z_975,
        dates=_dates(rb.betas.index),
        window_start=window_start,
        betas={DISPLAY_NAMES[c]: _series(rb.betas[c], warm) for c in FACTOR_CODES},
        se={DISPLAY_NAMES[c]: _series(rb.se[c], warm) for c in FACTOR_CODES},
    )


def _insufficient_rolling(window: int, n: int, info: SampleInfo) -> RollingWindow:
    return RollingWindow(
        status="insufficient_data",
        reason=f"{n} rows in the sample, fewer than the window of {window}",
        sample=info,
        labels=_labels("L-DESC", "L-BAND", "L-OVERLAP"),
        caption=f"Each point uses the previous {window} trading days, ending on that date.",
        window=window,
        n_stamps=0,
        hac_lags=0,
        ci_z=None,
        dates=[],
        window_start=[],
        betas={},
        se={},
    )


def _average_section(
    rb: RollingBetas, reg: FullSampleRegression, info: SampleInfo, rolling_ok: bool = True
) -> AverageBetaPanel:
    if not rolling_ok or rb.n_stamps < 2:
        return AverageBetaPanel(
            status="failed" if rolling_ok is False else "insufficient_data",
            reason=(
                f"the {rb.window}-day rolling betas could not be estimated in every window"
                if rolling_ok is False
                else f"fewer than 2 windows of {rb.window} days"
            ),
            sample=info,
            labels=_labels("L-DESC", "L-OVERLAP"),
            caption=f"Average of overlapping {rb.window}-day estimates.",
            window=rb.window,
            n_stamps=0,
            factors=[],
        )
    stats = average_beta(rb)
    n_stamps = stats[0].n_stamps
    caption = (
        f"Average of {n_stamps} overlapping {rb.window}-day estimates. The spread shows how "
        "exposure moved over time; it is not a standard error. The average of rolling betas "
        "generally differs from the full-sample beta."
    )
    return AverageBetaPanel(
        status="ok",
        reason=None,
        sample=info,
        labels=_labels("L-DESC", "L-OVERLAP"),
        caption=caption,
        window=rb.window,
        n_stamps=n_stamps,
        factors=[
            AverageBeta(
                name=s.name,
                full_sample_beta=_finite(reg.betas[i]),
                mean=_finite(s.mean),
                sd=_finite(s.sd),
                p10=_finite(s.p10),
                p90=_finite(s.p90),
                min=_finite(s.min),
                max=_finite(s.max),
                share_positive=_finite(s.share_positive),
            )
            for i, s in enumerate(stats)
        ],
    )


def _return_section(
    sample: AnalysisSample, reg: FullSampleRegression, info: SampleInfo
) -> ReturnContribution:
    ra = return_contribution_for(sample, reg)
    return ReturnContribution(
        status="ok",
        reason=None,
        sample=info,
        labels=_labels("L-DESC", "L-ARITH"),
        caption=(
            "Annualised (x252) means over the sample, using full-sample betas. Alpha, the "
            "residual and the memo rows are shown separately; nothing is folded into alpha."
        ),
        factors={k: _finite(v) for k, v in ra.contributions.items()},
        alpha=_finite(ra.alpha_ann),
        residual=_finite(ra.residual_ann),
        total_annualised_mean_excess_return=_finite(ra.total_ann),
        identity_residual=_finite(ra.identity_residual),
        memo=memo_rows(sample.uncovered, sample.excluded, sample.factor_last_date),
    )


def _risk_section(
    sample: AnalysisSample, reg: FullSampleRegression, info: SampleInfo
) -> RiskContribution:
    rk = risk_contribution_for(sample, reg)
    shares = [float(s) for s in rk.shares]
    sqrt_a = math.sqrt(252)
    details = [
        RiskFactorDetail(
            name=rk.names[i],
            share=_finite(shares[i]),
            beta=_finite(rk.betas[i]),
            sigma_annual=_finite(sqrt_a * rk.sigma[i]),
            rho_sys=_optional_finite(rk.rho_sys[i]),
        )
        for i in range(len(rk.names))
    ]
    return RiskContribution(
        status="ok",
        reason=None,
        sample=info,
        labels=_labels("L-DESC"),
        caption=f"Shares of variance over {info.start} to {info.end}; they add to 100%.",
        factors={rk.names[i]: _finite(shares[i]) for i in range(len(rk.names))},
        idiosyncratic=_finite(rk.idio_share),
        sums_to_one_residual=_finite(rk.sums_to_one_residual),
        total_vol_annual=_finite(rk.vol_ann),
        order=risk_order(rk.names, shares),
        details=details,
        sentences=risk_sentences(
            rk.names, [float(b) for b in rk.betas], shares, list(reg.beta_tags)
        ),
    )


def _price_section(history: PriceHistory, coverage_end: date) -> PriceSeries:
    adj = history.frame["adj_close"].to_numpy(dtype=np.float64)
    return PriceSeries(
        dates=_dates(history.frame.index),
        adj_close=[float(v) if math.isfinite(v) else None for v in adj],
        factor_coverage_end=coverage_end,
    )


_TEST_NAMES: dict[DiagnosticCode, str] = {
    "ljung_box": "Ljung-Box",
    "robust_breusch_godfrey": "Robust Breusch-Godfrey",
    "arch_lm": "ARCH-LM",
    "jarque_bera": "Jarque-Bera",
    "durbin_watson": "Durbin-Watson",
}


_EXACT_FIT_REASON = (
    "the regression fits the data exactly (1 - R² below 1e-12), so the residuals are rounding "
    "noise and residual diagnostics mean nothing"
)


def _diagnostics_section(diag: DiagnosticsResult | None, info: SampleInfo) -> ResidualDiagnostics:
    caption = (
        "Diagnostics of the full-sample regression residuals, each at a nominal 5% and not "
        "corrected for multiple testing. Only the lag-1 autocorrelation feeds the residual "
        "quality gate."
    )
    if diag is None:
        return ResidualDiagnostics(
            status="not_applicable",
            reason=_EXACT_FIT_REASON,
            sample=info,
            labels=_labels("L-DESC"),
            caption=caption,
            lag1_autocorrelation=None,
            lag1_se=None,
            lag1_z=None,
            lag1_p=None,
            lag1_reading=None,
            tests=[],
            note=DIAGNOSTICS_NOTE,
        )
    chi: dict[DiagnosticCode, ChiSquareTest] = {
        "ljung_box": diag.ljung_box,
        "robust_breusch_godfrey": diag.robust_bg,
        "arch_lm": diag.arch_lm,
        "jarque_bera": diag.jarque_bera,
    }
    tests = [
        DiagnosticTest(
            code=code,
            name=_TEST_NAMES[code],
            statistic=_finite(t.statistic),
            df=t.df,
            p=_finite(t.p),
            reading=diag.readings[code],
        )
        for code, t in chi.items()
    ]
    tests.append(
        DiagnosticTest(
            code="durbin_watson",
            name=_TEST_NAMES["durbin_watson"],
            statistic=_finite(diag.durbin_watson),
            df=None,
            p=None,
            reading=diag.readings["durbin_watson"],
        )
    )
    return ResidualDiagnostics(
        status="ok",
        reason=None,
        sample=info,
        labels=_labels("L-DESC"),
        caption=caption,
        lag1_autocorrelation=_finite(diag.lag1.rho),
        lag1_se=_finite(diag.lag1.se),
        lag1_z=_finite(diag.lag1.z),
        lag1_p=_finite(diag.lag1.p),
        lag1_reading=diag.readings["lag1_autocorrelation"],
        tests=tests,
        note=diag.note,
    )


def _gate_section(gate: GateResult | None, info: SampleInfo) -> QualityGate:
    caption = (
        f"Fires when the lag-1 autocorrelation of the residuals is below {RHO_GATE} and its "
        f"robust z is below {Z_GATE:.0f}: part of each day's residual then reverses the next "
        "day, typical of closing prices that are not synchronous with the factor data. A "
        "pre-specified heuristic, applied to every ticker."
    )
    if gate is None:
        return QualityGate(
            status="not_applicable",
            reason=_EXACT_FIT_REASON,
            sample=info,
            labels=_labels("L-DESC"),
            caption=caption,
            rho_threshold=None,
            z_threshold=None,
            lag1_autocorrelation=None,
            lag1_z=None,
            fired=None,
            noise_share=None,
            message=None,
        )
    return QualityGate(
        status="ok",
        reason=None,
        sample=info,
        labels=_labels("L-DESC"),
        caption=caption,
        rho_threshold=RHO_GATE,
        z_threshold=Z_GATE,
        lag1_autocorrelation=_finite(gate.rho),
        lag1_z=_finite(gate.z),
        fired=gate.fired,
        noise_share=_finite(gate.noise_share),
        message=gate.message,
    )


def _five_day_empty(
    status: Status, reason: str, info: SampleInfo, caption: str
) -> MultiDayRegression:
    return MultiDayRegression(
        status=status,
        reason=reason,
        sample=info,
        labels=_labels("L-DESC"),
        caption=caption,
        horizon_days=HORIZON,
        n_blocks=0,
        n_rows_unused=0,
        blocks_start=None,
        blocks_end=None,
        alpha_annual=None,
        alpha_se_annual=None,
        alpha_z=None,
        alpha_p=None,
        alpha_ci_low_annual=None,
        alpha_ci_high_annual=None,
        alpha_tag=None,
        r2=None,
        adj_r2=None,
        sigma_e_annual=None,
        hac_lags=0,
        bh_family_size=0,
        factors=[],
    )


def _five_day_section(
    five: MultiDayFit | None, gate: GateResult | None, n: int, info: SampleInfo
) -> MultiDayRegression:
    caption = (
        f"Sums of daily returns over non-overlapping blocks of {HORIZON} trading days, starting "
        "at the first day of the sample; same regression and Newey-West HAC errors as the daily "
        f"one, alpha annualised as 252/{HORIZON} times the block intercept. Computed because the "
        "residual quality gate "
        "fired: summing over 5 days lets most of a reversing price error cancel."
    )
    if gate is None:
        return _five_day_empty(
            "not_applicable",
            "the residual quality gate was not evaluated (exact fit)",
            info,
            caption,
        )
    if not gate.fired:
        return _five_day_empty(
            "not_applicable", "the residual quality gate did not fire", info, caption
        )
    if five is None:
        return _five_day_empty(
            "insufficient_data",
            f"{n // HORIZON} blocks of {HORIZON} days, fewer than {MIN_BLOCKS}",
            info,
            caption,
        )
    fit = five.fit
    names = [DISPLAY_NAMES[c] for c in FACTOR_CODES]
    factors = [
        FactorStat(
            name=names[i],
            beta=_finite(fit.params[i + 1]),
            se=_finite(fit.bse[i + 1]),
            z=_finite(fit.zvalues[i + 1]),
            p=_finite(fit.pvalues[i + 1]),
            p_adj_bh=_finite(five.beta_p_adj[i]),
            ci_low=_finite(fit.ci_low[i + 1]),
            ci_high=_finite(fit.ci_high[i + 1]),
            tag=five.beta_tags[i],
            interpretation=None,
        )
        for i in range(len(names))
    ]
    return MultiDayRegression(
        status="ok",
        reason=None,
        sample=info,
        labels=_labels("L-DESC"),
        caption=(
            caption + f" Blocks: {five.n_blocks} ({five.first_date} to {five.last_date}); "
            f"{five.n_unused} final day(s) not in a full block are not used."
        ),
        horizon_days=five.horizon,
        n_blocks=five.n_blocks,
        n_rows_unused=five.n_unused,
        blocks_start=five.first_date,
        blocks_end=five.last_date,
        alpha_annual=_finite(five.alpha_ann),
        alpha_se_annual=_finite(five.alpha_se_ann),
        alpha_z=_finite(fit.zvalues[0]),
        alpha_p=_finite(fit.pvalues[0]),
        alpha_ci_low_annual=_finite(five.alpha_ci_ann[0]),
        alpha_ci_high_annual=_finite(five.alpha_ci_ann[1]),
        alpha_tag=five.alpha_tag,
        r2=_finite(fit.rsquared),
        adj_r2=_finite(fit.rsquared_adj),
        sigma_e_annual=_finite(five.sigma_e_ann),
        hac_lags=fit.lags,
        bh_family_size=len(names),
        factors=factors,
    )


def _warnings(
    sample: AnalysisSample,
    reg: FullSampleRegression,
    audit: AuditReport,
    days_behind: int,
    gate: GateResult | None = None,
) -> list[ReportWarning]:
    out: list[ReportWarning] = []
    if gate is not None and gate.fired and gate.message:
        out.append(ReportWarning(code="residual_reversal", message=gate.message))
    if sample.short_history:
        out.append(
            ReportWarning(
                code="short_history",
                message=(
                    f"Only {sample.n} daily observations (fewer than 750, about 3 years): "
                    "estimates are imprecise."
                ),
            )
        )
    out.extend(ReportWarning(code="collinearity", message=m) for m in reg.collinearity.warnings)
    n_err = sum(1 for f in audit.findings if f.severity == "error")
    n_warn = sum(1 for f in audit.findings if f.severity == "warn")
    if n_err:
        out.append(
            ReportWarning(
                code="audit_errors",
                message=(
                    f"The price audit reported {n_err} error finding(s); see Audit findings. "
                    "The analysis still uses Adj Close as published, so a single bad row can "
                    "dominate alpha, the betas and R²: treat the headline numbers as not "
                    "interpretable until the findings are explained."
                ),
            )
        )
    elif n_warn:
        out.append(
            ReportWarning(
                code="audit_warnings",
                message=(
                    f"The price audit reported {n_warn} warning finding(s); see Audit findings."
                ),
            )
        )
    if days_behind > STALE_AFTER_DAYS:
        out.append(
            ReportWarning(
                code="factor_data_lag",
                message=(
                    f"Factor data ends {sample.factor_last_date}, {days_behind} days before the "
                    "report date (the French library publishes with a lag of about a month). "
                    f"{sample.uncovered.n} later price days are not analysed."
                ),
            )
        )
    return out


def _excluded_by_reason(sample: AnalysisSample) -> dict[str, int]:
    counts: dict[str, int] = {}
    for e in sample.excluded:
        counts[e.reason] = counts.get(e.reason, 0) + 1
    return counts


# ----------------------------------------------------------------------------- public API
def assemble_report(
    ticker: str,
    history: PriceHistory,
    factor_frame: pd.DataFrame,
    *,
    now: datetime,
    factors_downloaded_at: datetime | None,
    windows: Sequence[int] = WINDOWS,
    primary_window: int = PRIMARY_WINDOW,
    start: date | None = None,
    end: date | None = None,
    section_inputs: SectionInputs | None = None,
) -> FactorReport:
    """Pure part of ``build_report``: everything after the data has been fetched.

    ``start`` and ``end`` are the requested range (M2); None means the first return date and
    the last price date. They are reported as given, so nothing is clipped silently.
    ``section_inputs`` holds extra data for the optional sections (None: none).
    """
    history = unique_dates(history)
    audit = audit_prices(history.frame, duplicate_dates=history.duplicate_dates)
    sample = build_sample(history, factor_frame, start, end)
    vintage = FactorVintage(last_date=sample.factor_last_date, downloaded_at=factors_downloaded_at)
    info = _sample_info(sample, vintage)
    daily = run_regression(sample)
    factor_values = sample.factors.loc[:, list(FACTOR_CODES)].to_numpy(dtype=np.float64)
    diag = (
        None
        if exact_fit(daily.fit.rsquared)
        else residual_diagnostics(daily.fit.resid, factor_values)
    )
    gate = None if diag is None else quality_gate(diag.lag1)
    five = multi_day_regression(sample) if gate is not None and gate.fired else None
    reg = apply_gate(daily, five) if five is not None else daily

    rolling_by_w = {w: rolling_betas(sample, w) for w in sorted(set(windows) | {primary_window})}
    rolling_sections = [
        _rolling_section(rb, _sample_info(sample, vintage, w))
        if sample.n >= w
        else _insufficient_rolling(w, sample.n, _sample_info(sample, vintage, w))
        for w, rb in rolling_by_w.items()
    ]
    primary = rolling_by_w[primary_window]
    primary_ok = next(s.status == "ok" for s in rolling_sections if s.window == primary_window)
    days_behind = (now.date() - sample.factor_last_date).days

    data = DataInfo(
        requested_start=sample.requested_start,
        requested_end=sample.requested_end,
        actual_start=sample.start,
        actual_end=sample.end,
        n_obs=sample.n,
        factors_last_date=sample.factor_last_date,
        factors_downloaded_at=factors_downloaded_at,
        factors_days_behind=days_behind,
        factors_source_url=factor_data.SOURCE_URL,
        price_source=f"{history.source} (Adj Close)",
        dropped_price_dates_after_factors=sample.uncovered.n,
        dropped_price_dates_before_factors=sample.n_before_factors,
        n_excluded=len(sample.excluded),
        excluded_by_reason=_excluded_by_reason(sample),
        uncovered=UncoveredTail(
            n=sample.uncovered.n,
            first=sample.uncovered.first,
            last=sample.uncovered.last,
            factor_last_date=sample.factor_last_date,
            compounded_return=sample.uncovered.compounded_return,
        ),
        audit_status=_audit_status(audit),
        audit_findings=[
            AuditFinding(
                code=f.code,
                severity=_SEVERITY[f.severity],
                message=f.message,
                dates=list(f.dates),
            )
            for f in audit.findings
        ],
    )
    core = CoreSections(
        data=data,
        regression=_regression_section(reg, info, gate is not None and gate.fired),
        rolling=rolling_sections,
        average_beta=_average_section(
            primary, reg, _sample_info(sample, vintage, primary_window), primary_ok
        ),
        return_contribution=_return_section(sample, reg, info),
        risk_contribution=_risk_section(sample, reg, info),
        residual_diagnostics=_diagnostics_section(diag, info),
        quality_gate=_gate_section(gate, info),
        five_day_regression=_five_day_section(five, gate, sample.n, info),
        price_series=_price_section(history, sample.factor_last_date),
    )
    ctx = SectionContext(
        ticker=ticker,
        now=now,
        history=history,
        factor_frame=factor_frame,
        sample=sample,
        vintage=vintage,
        audit=audit,
        daily=daily,
        regression=reg,
        diagnostics=diag,
        gate=gate,
        five_day=five,
        rolling=rolling_by_w,
        primary_window=primary_window,
        core=core,
        inputs=section_inputs if section_inputs is not None else SectionInputs(),
        make_sample_info=lambda window: _sample_info(sample, vintage, window),
    )
    # Optional sections (schema v3 contract SC3.2), in panel order. Each hook sees only the core.
    lead_lag = lead_lag_hook.build_lead_lag(ctx)
    shrunk_betas = shrunk_hook.build_shrunk_betas(ctx)
    fragility = fragility_hook.build_fragility(ctx)
    world_beta = world_beta_hook.build_world_beta(ctx)
    residual = residual_alpha_hook.build_residual_analysis(ctx)
    kalman_betas = kalman_hook.build_kalman_betas(ctx)
    present: dict[str, object | None] = {
        "lead_lag": lead_lag,
        "shrunk_betas": shrunk_betas,
        "fragility": fragility,
        "world_beta": world_beta,
        "residual": residual,
        "kalman_betas": kalman_betas,
    }
    return FactorReport(
        ticker=ticker,
        generated_at=now,
        data=core.data,
        regression=core.regression,
        rolling=list(core.rolling),
        average_beta=core.average_beta,
        return_contribution=core.return_contribution,
        risk_contribution=core.risk_contribution,
        residual_diagnostics=core.residual_diagnostics,
        quality_gate=core.quality_gate,
        five_day_regression=core.five_day_regression,
        price_series=core.price_series,
        warnings=_warnings(sample, reg, audit, days_behind, gate),
        notes=[NOTE_DESC, NOTE_VINTAGE, NOTE_US_FACTORS, NOTE_SURVIVORSHIP],
        label_text=report_label_text(present),
        lead_lag=lead_lag,
        shrunk_betas=shrunk_betas,
        fragility=fragility,
        world_beta=world_beta,
        residual=residual,
        kalman_betas=kalman_betas,
    )


def build_report(
    ticker: str,
    price_provider: PriceProvider | None = None,
    factors: pd.DataFrame | None = None,
    now: datetime | None = None,
    *,
    start: date | None = None,
    end: date | None = None,
    section_inputs: SectionInputs | None = None,
) -> FactorReport:
    """Fetch factors and prices for ``ticker`` and build the validated ``FactorReport``.

    ``factors`` is a frame shaped like ``data.factors.load_ff5_daily()`` (French column names,
    decimals); when None the cached French file is loaded (and refreshed when stale). ``now``
    must be timezone-aware; it stamps ``generated_at`` and drives the data-lag figures.
    ``start`` and ``end`` limit the requested range (None: the whole price history).
    ``section_inputs`` is the extra data of the optional sections; None fetches it through
    ``section_hooks.load_section_inputs`` (nothing is fetched when ``factors`` is injected).
    Raises ``PriceDataError`` (bad or unknown ticker), ``FactorError`` (factor data
    unavailable), ``InsufficientHistoryError`` (fewer than 504 aligned rows) or
    ``DegenerateInputError`` (price that does not move, singular factor design; D30).
    """
    if now is None:
        now = datetime.now(UTC)
    if now.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    now_utc = now.astimezone(UTC)
    symbol = validate_ticker(ticker)

    downloaded_at: datetime | None = None
    if factors is None:
        factor_frame = factor_data.load_ff5_daily(now=now_utc)
        status = factor_data.factor_status(now=now_utc)
        downloaded_at = _as_utc(status.last_download_at) if status is not None else None
    else:
        factor_frame = factors

    provider: PriceProvider = (
        price_provider if price_provider is not None else YFinanceProvider(now=lambda: now_utc)
    )
    history = provider.fetch(symbol)
    inputs = (
        section_inputs
        if section_inputs is not None
        else load_section_inputs(
            now_utc,
            offline=factors is not None,
            factor_last_date=pd.Timestamp(factor_frame.index[-1]).date(),
            price_provider=provider,
        )
    )
    return assemble_report(
        symbol,
        history,
        factor_frame,
        now=now_utc,
        factors_downloaded_at=downloaded_at,
        start=start,
        end=end,
        section_inputs=inputs,
    )


def unique_dates(history: PriceHistory) -> PriceHistory:
    """Collapse repeated dates a provider returned (first bar kept) and record them (D29)."""
    frame, repeated = collapse_duplicate_dates(history.frame)
    if not repeated:
        return history
    recorded = tuple(sorted(set(history.duplicate_dates) | set(repeated)))
    return dataclasses.replace(history, frame=frame, duplicate_dates=recorded)


def _as_utc(ts: datetime | None) -> datetime | None:
    """Normalise a stored download time to aware UTC (naive values are taken as UTC)."""
    if ts is None:
        return None
    return ts.replace(tzinfo=UTC) if ts.utcoffset() is None else ts.astimezone(UTC)
