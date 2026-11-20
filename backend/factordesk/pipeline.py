"""End-to-end report builder: data layer -> analysis sample -> analytics -> ``FactorReport``.

Order of work: factor data, then prices (repeated dates collapsed to their first bar and
recorded), the price audit, the aligned sample (M2), the full-sample regression (M3), its
residual diagnostics and quality gate with the 5-day estimate when the gate fires (M3.5-M3.6),
rolling betas (M4) and average beta (M5), return and risk contribution (M6.1, M6.4, M7), and
last the optional sections of the schema v3 contract, one hook each (``section_hooks/``,
``docs/specs/schema-v3-contract.md`` SC3.2).

Every report runs on a ``ReturnSubject`` (``analytics/subject.py``): ``assemble_subject_report``
is the engine and ``assemble_report`` (a ticker's price history) wraps it. A monthly subject is
regressed on the French monthly factors with ``periods = 12``; the sections built on trading
days do not apply to it: the rolling windows, the average beta and the residual quality gate
(with its 5-day estimate) report ``not_applicable`` with a reason, and the daily-only optional
sections are hidden by the hook registry (``section_hooks/registry.py``).
The factor model is FF5 (default) or FF6 (FF5 plus momentum, E1). Under FF6 every core section
uses the six factors, the sample is built on the dates where momentum exists, and the sections
defined for the five factors only are hidden by the hook registry; the FF5 report is unchanged.
Providers, the factor frame and the clock are injectable so the whole path runs offline in
tests. Inputs that cannot support a regression raise ``DegenerateInputError`` (D30).
"""

from __future__ import annotations

import dataclasses
import math
from collections.abc import Iterable, Mapping, Sequence
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
from factordesk.analytics.models import model_codes
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
    AnalysisSample,
    build_subject_sample,
)
from factordesk.analytics.subject import ReturnSubject, subject_from_history
from factordesk.data import factors as factor_data
from factordesk.data import french
from factordesk.data.audit import AuditReport, audit_levels, audit_prices
from factordesk.data.french import FactorSet
from factordesk.data.prices import (
    SUPPORTED_CURRENCY,
    PriceHistory,
    PriceProvider,
    Security,
    UnsupportedCurrencyError,
    YFinanceProvider,
    check_currency,
    collapse_duplicate_dates,
    security_of,
    validate_ticker,
)
from factordesk.report.schema import (
    AuditFinding,
    AuditStatus,
    AverageBeta,
    AverageBetaPanel,
    CorrPair,
    CurrencyInfo,
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
    SecurityInfo,
    Severity,
    Status,
    SubjectInfo,
    UncoveredTail,
    report_label_text,
)
from factordesk.report.sections.kalman import L_KTAIL_SERIES
from factordesk.section_hooks import load_section_inputs
from factordesk.section_hooks.context import (
    FACTOR_MODELS,
    CoreSections,
    FactorModel,
    SectionContext,
    SectionInputs,
)
from factordesk.section_hooks.registry import run_hooks

STALE_AFTER_DAYS = factor_data.STALE_AFTER_DAYS

NOTE_VINTAGE = "Uses the current Fama-French data vintage; historical factor values can be revised."
NOTE_SURVIVORSHIP = (
    "Only tickers that exist today can be analysed. Results for survivors are not "
    "representative of companies that were delisted."
)
NOTE_US_FACTORS = (
    "The factors are US Fama-French factors in USD. Applied to a non-US stock or a non-USD "
    "price series, betas mix factor exposure with currency and local-market effects. A ticker "
    "that Yahoo reports in another currency is refused; when Yahoo reports no currency, the "
    "ticker is analysed without that check."
)
NOTE_EUROPE_FACTORS = (
    "The factors are Developed Europe Fama-French factors from the Ken French data library, "
    "built in US dollars with the US one-month Treasury bill as the risk-free rate; they start "
    "in July 1990. A stock that does not trade in Europe mixes factor exposure with currency "
    "and local-market effects. A ticker that Yahoo reports in another currency is refused; when "
    "Yahoo reports no currency, the ticker is analysed without that check. The shrunk-betas "
    "section is left out because its prior comes from US factor portfolios."
)
NOTE_EUROPE_FACTORS_SERIES = (
    "The factors are Developed Europe Fama-French factors from the Ken French data library, "
    "built in US dollars with the US one-month Treasury bill as the risk-free rate; they start "
    "in July 1990. The returns are taken to be in the report's currency."
)
NOTE_EUROPE_WORLD_BETA = (
    "The market factor of the world beta section's comparison row is the Europe market factor "
    "in this report; the row is still labelled US market."
)
NOTE_DESC = "Every statistic is descriptive and in-sample, not predictive."
NOTE_US_FACTORS_SERIES = (
    "The factors are US Fama-French factors in USD, and the returns are taken to be in US "
    "dollars. Returns in another currency would mix factor exposure with currency effects."
)
NOTE_MONTHLY_TEMPLATE = (
    "Monthly data: the regression uses the Fama-French monthly factors and annualises with 12 "
    "periods a year. The Newey-West HAC covariance is scaled by n / (n - {k}), and p-values, "
    "intervals and tags use Student-t with n - {k} degrees of freedom; they remain approximate "
    "for records of 36 to 60 months."
)
"""Note of a monthly report; ``k`` is the number of parameters (6 for FF5, 7 for FF6)."""
NOTE_MONTHLY = NOTE_MONTHLY_TEMPLATE.format(k=6)
"""The monthly note of an FF5 report."""
NOTE_FF6 = (
    "Model: FF6, the five Fama-French factors plus momentum (Mom). The sample ends on the last "
    "date both factor files cover. Sections defined for the five-factor model only are not shown."
)
MOM_COLUMN = french.MOM
"""Column of the momentum factor in the French frame (``data.french.load_ff6``)."""

FACTOR_SOURCE_URL: dict[str, str] = {
    "daily": factor_data.SOURCE_URL,
    "monthly": french.DATASETS["ff5_monthly"].url,
}
"""The French file behind each frequency (the FF5 model, US factors)."""
EUROPE_SOURCE_URL: dict[str, str] = {
    "daily": french.DATASETS["europe5_daily"].url,
    "monthly": french.DATASETS["europe5_monthly"].url,
}
"""The French file behind each frequency for the Europe factor set."""

_UNIT: dict[str, str] = {"daily": "trading days", "monthly": "months"}
_SUBJECT_NOUN: dict[str, str] = {
    "ticker": "stock",
    "upload": "track record",
    "portfolio": "portfolio",
}

NOT_DAILY_ROLLING = (
    "rolling betas use windows of {window} trading days and are computed for daily returns "
    "only; this report is on monthly returns"
)
NOT_DAILY_AVERAGE = (
    "the average beta summarises the {window}-day rolling betas, which are computed for daily "
    "returns only; this report is on monthly returns"
)
NOT_DAILY_GATE = (
    "the residual quality gate looks for daily closing prices that are not synchronous with the "
    "factor data; it does not apply to monthly returns"
)
NOT_DAILY_FIVE_DAY = (
    "the 5-day estimate is computed only when the residual quality gate fires, and the gate "
    "does not apply to monthly returns"
)

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
    n_betas = len(reg.names)
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
        f"Newey-West HAC standard errors with {fit.lags} lags, "
        + (
            "normal reference distribution. "
            if fit.t_df is None
            else f"scaled by n / (n - {n_betas + 1}), Student-t reference with {fit.t_df} "
            "degrees of freedom. "
        )
        + "Betas are tagged reliable when significant after a Benjamini-Hochberg correction "
        f"across the {n_betas} betas (q = 0.05); alpha is a single test at 5%. Bars show the 95% "
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
        betas={DISPLAY_NAMES[c]: _series(rb.betas[c], warm) for c in rb.betas.columns},
        se={DISPLAY_NAMES[c]: _series(rb.se[c], warm) for c in rb.se.columns},
    )


def _not_applicable_rolling(window: int, info: SampleInfo, reason: str) -> RollingWindow:
    return RollingWindow(
        status="not_applicable",
        reason=reason,
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


def _not_applicable_average(window: int, info: SampleInfo, reason: str) -> AverageBetaPanel:
    return AverageBetaPanel(
        status="not_applicable",
        reason=reason,
        sample=info,
        labels=_labels("L-DESC", "L-OVERLAP"),
        caption=f"Average of overlapping {window}-day estimates.",
        window=window,
        n_stamps=0,
        factors=[],
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
    sample: AnalysisSample,
    reg: FullSampleRegression,
    info: SampleInfo,
    *,
    subject_noun: str = "stock",
) -> ReturnContribution:
    ra = return_contribution_for(sample, reg)
    return ReturnContribution(
        status="ok",
        reason=None,
        sample=info,
        labels=_labels("L-DESC", "L-ARITH"),
        caption=(
            f"Annualised (x{reg.periods}) means over the sample, using full-sample betas. Alpha, "
            "the residual and the memo rows are shown separately; nothing is folded into alpha."
        ),
        factors={k: _finite(v) for k, v in ra.contributions.items()},
        alpha=_finite(ra.alpha_ann),
        residual=_finite(ra.residual_ann),
        total_annualised_mean_excess_return=_finite(ra.total_ann),
        identity_residual=_finite(ra.identity_residual),
        memo=memo_rows(
            sample.uncovered,
            sample.excluded,
            sample.factor_last_date,
            unit=_UNIT[sample.frequency],
            subject=subject_noun,
        ),
    )


def _risk_section(
    sample: AnalysisSample, reg: FullSampleRegression, info: SampleInfo
) -> RiskContribution:
    rk = risk_contribution_for(sample, reg)
    shares = [float(s) for s in rk.shares]
    sigma_ann = rk.sigma_ann
    details = [
        RiskFactorDetail(
            name=rk.names[i],
            share=_finite(shares[i]),
            beta=_finite(rk.betas[i]),
            sigma_annual=_finite(sigma_ann[i]),
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


def _price_section(subject: ReturnSubject, coverage_end: date) -> PriceSeries:
    """The subject's levels for the chart: adjusted close of a ticker, NAV or growth index else."""
    adj = subject.levels.to_numpy(dtype=np.float64)
    return PriceSeries(
        dates=_dates(subject.calendar),
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


def _diagnostics_section(
    diag: DiagnosticsResult | None, info: SampleInfo, *, gate_applies: bool = True
) -> ResidualDiagnostics:
    caption = (
        "Diagnostics of the full-sample regression residuals, each at a nominal 5% and not "
        "corrected for multiple testing."
    )
    if gate_applies:
        caption += " Only the lag-1 autocorrelation feeds the residual quality gate."
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


def _gate_section(
    gate: GateResult | None, info: SampleInfo, not_applicable: str = _EXACT_FIT_REASON
) -> QualityGate:
    caption = (
        f"Fires when the lag-1 autocorrelation of the residuals is below {RHO_GATE} and its "
        f"robust z is below {Z_GATE:.0f}: part of each day's residual then reverses the next "
        "day, typical of closing prices that are not synchronous with the factor data. A "
        "pre-specified heuristic, applied to every ticker."
    )
    if gate is None:
        return QualityGate(
            status="not_applicable",
            reason=not_applicable,
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
    five: MultiDayFit | None,
    gate: GateResult | None,
    n: int,
    info: SampleInfo,
    not_applicable: str | None = None,
) -> MultiDayRegression:
    caption = (
        f"Sums of daily returns over non-overlapping blocks of {HORIZON} trading days, starting "
        "at the first day of the sample; same regression and Newey-West HAC errors as the daily "
        f"one, alpha annualised as 252/{HORIZON} times the block intercept. Computed because the "
        "residual quality gate "
        "fired: summing over 5 days lets most of a reversing price error cancel."
    )
    if not_applicable is not None:
        return _five_day_empty("not_applicable", not_applicable, info, caption)
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
    names = list(five.names)
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
    if sample.short_history and sample.frequency == "daily":
        out.append(
            ReportWarning(
                code="short_history",
                message=(
                    f"Only {sample.n} daily observations (fewer than 750, about 3 years): "
                    "estimates are imprecise."
                ),
            )
        )
    elif sample.short_history:
        out.append(
            ReportWarning(
                code="short_history",
                message=(
                    f"Only {sample.n} monthly observations (fewer than {sample.warn_obs}, "
                    f"{sample.warn_obs // 12} years): estimates are imprecise, and the "
                    "Newey-West z-statistics are only approximate at this length."
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
    # A monthly record says so only when months are cut off; daily reports keep their rule.
    cut_off = sample.uncovered.n > 0 or sample.frequency == "daily"
    if days_behind > STALE_AFTER_DAYS and cut_off:
        out.append(
            ReportWarning(
                code="factor_data_lag",
                message=(
                    f"Factor data ends {sample.factor_last_date}, {days_behind} days before the "
                    "report date (the French library publishes with a lag of about a month). "
                    f"{sample.uncovered.n} later "
                    f"{'price days' if sample.frequency == 'daily' else 'months'} are not "
                    "analysed."
                ),
            )
        )
    return out


_QUOTE_TYPE_LABELS = {"ETF": "ETF", "EQUITY": "Equity"}
"""Yahoo ``quoteType`` values shown as a badge; any other type is left out."""


def _security_info(security: Security | None) -> SecurityInfo | None:
    if security is None or (security.name, security.currency, security.exchange) == (None,) * 3:
        return None
    return SecurityInfo(
        name=security.name,
        currency=security.currency,
        exchange=security.exchange,
        quote_type=_QUOTE_TYPE_LABELS.get((security.quote_type or "").upper()),
    )


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
    security: Security | None = None,
    model: FactorModel = "ff5",
    reference_currency: str = SUPPORTED_CURRENCY,
    currency: CurrencyInfo | None = None,
    converted: bool = False,
    audit_history: PriceHistory | None = None,
    factor_set: FactorSet = french.DEFAULT_FACTOR_SET,
) -> FactorReport:
    """Pure part of ``build_report``: everything after the data has been fetched.

    ``start`` and ``end`` are the requested range (M2); None means the first return date and
    the last price date. They are reported as given, so nothing is clipped silently.
    ``section_inputs`` holds extra data for the optional sections (None: none). ``security`` is
    the Yahoo metadata of the ticker (None: unknown); a known currency other than USD raises
    ``UnsupportedCurrencyError`` (roadmap N1, an unknown currency does not). A wrapper over
    ``assemble_subject_report`` with the daily ticker subject of ``history``; ``model`` is FF5
    (default) or FF6, which needs the ``Mom`` column of ``data.french.load_ff6``.
    ``converted`` says the caller already converted ``history`` and ``factor_frame`` to
    ``reference_currency`` (the listing currency is then not refused); ``currency`` is the
    report's ``currency`` block for a reference other than USD. ``audit_history`` is the price
    history the audit reads when ``history`` was converted: the audit checks the prices as the
    exchange lists them, because a conversion breaks the link between ``Close``, ``Adj Close``
    and each dividend (None: audit ``history``). ``factor_set`` says which regional factor set
    ``factor_frame`` holds (``"us"``, or ``"europe"``: the report then names it); the frame must
    already be that set's.
    """
    if not converted:
        check_currency(ticker, security)
    history = unique_dates(history)
    subject = subject_from_history(
        history,
        label=ticker,
        currency=reference_currency
        if converted
        else (None if security is None else security.currency),
    )
    return assemble_subject_report(
        subject,
        factor_frame,
        model,
        now=now,
        factors_downloaded_at=factors_downloaded_at,
        windows=windows,
        primary_window=primary_window,
        start=start,
        end=end,
        section_inputs=section_inputs,
        security=security,
        reference_currency=reference_currency,
        currency=currency,
        audit_history=audit_history,
        factor_set=factor_set,
    )


def _subject_audit(
    subject: ReturnSubject, audit_history: PriceHistory | None = None
) -> AuditReport:
    """The price audit of a ticker, the level audit otherwise, plus the subject's own findings.

    A ticker is audited on ``audit_history`` (its unconverted prices) when given."""
    if subject.history is not None:
        audited = subject.history if audit_history is None else unique_dates(audit_history)
        audit = audit_prices(audited.frame, duplicate_dates=audited.duplicate_dates)
    else:
        audit = audit_levels(subject.levels, subject.frequency)
    if not subject.findings:
        return audit
    findings = audit.findings + subject.findings
    return dataclasses.replace(
        audit, findings=findings, ok=not any(f.severity == "error" for f in findings)
    )


def _subject_info(subject: ReturnSubject) -> SubjectInfo | None:
    """The report's ``subject`` block: ``None`` (left out of the JSON) for a ticker."""
    if subject.kind == "ticker":
        return None
    gross_net = subject.meta.get("gross_net")
    return SubjectInfo(
        kind=subject.kind,
        label=subject.label,
        frequency=subject.frequency,
        periods=subject.periods,
        source=subject.source,
        gross_net=gross_net if gross_net == "gross" or gross_net == "net" else None,
        currency=subject.currency,
    )


def _check_subject_currency(subject: ReturnSubject, reference: str) -> None:
    """The subject must be in the reference currency of the factors; an unknown one passes."""
    currency = subject.currency
    if currency is not None and currency.strip().upper() != reference:
        raise UnsupportedCurrencyError(subject.label, currency.strip())


def _model_frame(factor_frame: pd.DataFrame, model: FactorModel) -> pd.DataFrame:
    """The factor frame the report's sample is built on.

    FF5: the frame as given (a ``Mom`` column, when present, rides along for the alpha strip and
    never removes a row). FF6: the rows where ``Mom`` exists, so every sample row has all six
    factors; dates after the last momentum value become the uncovered tail. ``ValueError`` when
    the frame has no ``Mom`` column.
    """
    if model == "ff5":
        return factor_frame
    if MOM_COLUMN not in factor_frame.columns:
        raise ValueError(
            "the FF6 model needs the momentum factor (column 'Mom' of data.french.load_ff6)"
        )
    keep = factor_frame[MOM_COLUMN].notna().to_numpy(dtype=bool)
    if bool(keep.all()):
        return factor_frame
    out = factor_frame.loc[keep]
    out.attrs = dict(factor_frame.attrs)
    return out


def _label_text(present: Mapping[str, object | None], subject: ReturnSubject) -> dict[str, str]:
    """``report_label_text``, with the footnotes worded for the subject: a ticker keeps its own
    wording, a portfolio or an uploaded record says "series"."""
    texts = report_label_text(present)
    if subject.kind != "ticker" and "L-KTAIL" in texts:
        texts["L-KTAIL"] = L_KTAIL_SERIES
    return texts


def assemble_subject_report(
    subject: ReturnSubject,
    factor_frame: pd.DataFrame,
    model: FactorModel = "ff5",
    *,
    now: datetime,
    factors_downloaded_at: datetime | None,
    windows: Sequence[int] = WINDOWS,
    primary_window: int = PRIMARY_WINDOW,
    start: date | None = None,
    end: date | None = None,
    section_inputs: SectionInputs | None = None,
    security: Security | None = None,
    reference_currency: str = SUPPORTED_CURRENCY,
    currency: CurrencyInfo | None = None,
    audit_history: PriceHistory | None = None,
    factor_set: FactorSet = french.DEFAULT_FACTOR_SET,
) -> FactorReport:
    """The report of any return subject: the engine behind every mode.

    ``factor_frame`` is the French frame of the subject's frequency (``load_ff5_daily`` or
    ``data.french.load_ff5_monthly``, or ``data.french.load_ff6`` with the ``Mom`` column; French
    column names, decimals). ``model`` is the factor model: ``"ff5"`` or ``"ff6"`` (FF5 plus
    momentum, which needs the ``Mom`` column; its sample keeps the dates where ``Mom`` exists).
    A frame with ``Mom`` also gives the alpha strip under FF5; the FF5 sections do not change.
    Annualised figures use ``subject.periods``.
    ``reference_currency`` is the currency of the subject and of ``factor_frame`` (the caller
    converts both); ``currency`` is the report's ``currency`` block when it is not USD.
    A ticker subject's report is exactly ``assemble_report``'s. A subject in a known currency
    other than the reference raises ``UnsupportedCurrencyError``; fewer aligned rows than the
    frequency's floor raise ``InsufficientHistoryError`` (daily 504, monthly 36).
    ``audit_history`` is the unconverted price history of a ticker subject, audited in place of
    ``subject.history`` (None: audit ``subject.history``). ``factor_set`` names the regional
    factor set ``factor_frame`` holds, "us" (default) or "europe"; it changes the source link,
    the notes and the report's ``factor_set`` field (left out for "us"), nothing else: every
    section reads the frame it is given.
    """
    french.check_factor_set(factor_set)
    if model not in FACTOR_MODELS:
        raise ValueError(f"unknown factor model {model!r}; use 'ff5' or 'ff6'")
    codes = model_codes(model)
    _check_subject_currency(subject, reference_currency)
    is_daily = subject.frequency == "daily"
    periods = subject.periods
    audit = _subject_audit(subject, audit_history)
    model_frame = _model_frame(factor_frame, model)
    sample = build_subject_sample(subject, model_frame, start, end)
    vintage = FactorVintage(last_date=sample.factor_last_date, downloaded_at=factors_downloaded_at)
    info = _sample_info(sample, vintage)
    first_fit = run_regression(sample, periods=periods, codes=codes, small_sample=not is_daily)
    factor_values = sample.factor_columns(codes).to_numpy(dtype=np.float64)
    diag = (
        None
        if exact_fit(first_fit.fit.rsquared)
        else residual_diagnostics(first_fit.fit.resid, factor_values, subject.frequency)
    )
    gate = None if diag is None or not is_daily else quality_gate(diag.lag1)
    five = multi_day_regression(sample, codes=codes) if gate is not None and gate.fired else None
    reg = apply_gate(first_fit, five) if five is not None else first_fit

    all_windows = sorted(set(windows) | {primary_window})
    if is_daily:
        rolling_by_w = {w: rolling_betas(sample, w, codes) for w in all_windows}
        rolling_sections = [
            _rolling_section(rb, _sample_info(sample, vintage, w))
            if sample.n >= w
            else _insufficient_rolling(w, sample.n, _sample_info(sample, vintage, w))
            for w, rb in rolling_by_w.items()
        ]
        primary = rolling_by_w[primary_window]
        primary_ok = next(s.status == "ok" for s in rolling_sections if s.window == primary_window)
        average = _average_section(
            primary, reg, _sample_info(sample, vintage, primary_window), primary_ok
        )
    else:
        rolling_by_w = {}
        rolling_sections = [
            _not_applicable_rolling(
                w, _sample_info(sample, vintage, w), NOT_DAILY_ROLLING.format(window=w)
            )
            for w in all_windows
        ]
        average = _not_applicable_average(
            primary_window,
            _sample_info(sample, vintage, primary_window),
            NOT_DAILY_AVERAGE.format(window=primary_window),
        )
    days_behind = (now.date() - sample.factor_last_date).days

    price_source = (
        f"{subject.history.source} (Adj Close)"
        if subject.history is not None
        else f"{subject.source} ({subject.frequency} returns)"
    )
    data = DataInfo(
        requested_start=sample.requested_start,
        requested_end=sample.requested_end,
        actual_start=sample.start,
        actual_end=sample.end,
        n_obs=sample.n,
        factors_last_date=sample.factor_last_date,
        factors_downloaded_at=factors_downloaded_at,
        factors_days_behind=days_behind,
        factors_source_url=(EUROPE_SOURCE_URL if factor_set == "europe" else FACTOR_SOURCE_URL)[
            subject.frequency
        ],
        price_source=price_source,
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
        security=_security_info(security),
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
        average_beta=average,
        return_contribution=_return_section(
            sample, reg, info, subject_noun=_SUBJECT_NOUN[subject.kind]
        ),
        risk_contribution=_risk_section(sample, reg, info),
        residual_diagnostics=_diagnostics_section(diag, info, gate_applies=is_daily),
        quality_gate=(
            _gate_section(gate, info) if is_daily else _gate_section(None, info, NOT_DAILY_GATE)
        ),
        five_day_regression=_five_day_section(
            five, gate, sample.n, info, None if is_daily else NOT_DAILY_FIVE_DAY
        ),
        price_series=_price_section(subject, sample.factor_last_date),
    )
    ctx = SectionContext(
        ticker=subject.label,
        now=now,
        history=subject.history,
        factor_frame=model_frame,
        sample=sample,
        vintage=vintage,
        audit=audit,
        daily=first_fit,
        regression=reg,
        diagnostics=diag,
        gate=gate,
        five_day=five,
        rolling=rolling_by_w,
        primary_window=primary_window,
        core=core,
        inputs=section_inputs if section_inputs is not None else SectionInputs(),
        make_sample_info=lambda window: _sample_info(sample, vintage, window),
        subject=subject,
        model=model,
    )
    # Optional sections (schema v3 contract SC3.2), in panel-call order. Each hook sees only the
    # core; a hook outside its HookSpec (subject kind, frequency, model) leaves its field None.
    present = run_hooks(ctx)
    europe = factor_set == "europe"
    if subject.kind == "ticker":
        notes = [
            NOTE_DESC,
            NOTE_VINTAGE,
            NOTE_EUROPE_FACTORS if europe else NOTE_US_FACTORS,
            NOTE_SURVIVORSHIP,
        ]
        if europe and present.get("world_beta") is not None:
            notes.append(NOTE_EUROPE_WORLD_BETA)
    else:
        notes = [
            NOTE_DESC,
            NOTE_VINTAGE,
            NOTE_EUROPE_FACTORS_SERIES if europe else NOTE_US_FACTORS_SERIES,
        ]
    if not is_daily:
        notes.append(NOTE_MONTHLY_TEMPLATE.format(k=len(codes) + 1))
    if model == "ff6":
        notes.append(NOTE_FF6)
    notes.extend(french.stamp_notices(factor_frame.attrs))
    return FactorReport.model_validate(
        {
            "ticker": subject.label,
            "subject": _subject_info(subject),
            "currency": currency,
            "model": "ff6" if model == "ff6" else None,
            "factor_set": "europe" if europe else None,
            "generated_at": now,
            "data": core.data,
            "regression": core.regression,
            "rolling": list(core.rolling),
            "average_beta": core.average_beta,
            "return_contribution": core.return_contribution,
            "risk_contribution": core.risk_contribution,
            "residual_diagnostics": core.residual_diagnostics,
            "quality_gate": core.quality_gate,
            "five_day_regression": core.five_day_regression,
            "price_series": core.price_series,
            "warnings": _warnings(sample, reg, audit, days_behind, gate),
            "notes": notes,
            "label_text": _label_text(present, subject),
            **present,
        }
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
    Raises ``PriceDataError`` (bad or unknown ticker), ``UnsupportedCurrencyError`` (Yahoo
    reports a currency other than USD; checked before the price history is downloaded),
    ``FactorError`` (factor data unavailable), ``InsufficientHistoryError`` (fewer than 504
    aligned rows) or ``DegenerateInputError`` (price that does not move, singular factor
    design; D30).
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
    security = security_of(provider, symbol)
    check_currency(symbol, security)
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
        security=security,
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
