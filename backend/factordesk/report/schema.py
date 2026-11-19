"""Typed ``FactorReport``: the single payload between analytics and every renderer.

Conventions (apply to every model in this module; see ``docs/methodology.md`` M0 and M14):

* Returns, betas, contributions and shares are **decimals** (0.05 means 5%), never percents.
* ``*_annual`` values are annualised with ``A = 252`` (arithmetic, M0.4) and stated per year.
* Dates are ISO ``YYYY-MM-DD`` in JSON; ``generated_at`` is a timezone-aware UTC timestamp.
* Any statistic that could not be computed is ``None`` (JSON ``null``) with a ``status`` other
  than ``"ok"`` and a ``reason``. NaN and infinity are rejected on construction, so they can
  never be serialised (M0.7).
* Every statistic carries ``status``, ``reason``, ``sample`` (``SampleInfo``, M0.8), the keys
  of its standard footnotes (M0.9) and a section-specific ``caption``.
* Models are frozen and strict: no silent coercion, no unknown keys.
* JSON files are written without indentation, and the per-stamp rolling series (betas and
  their standard errors) are rounded to 6 significant digits when the report is built (relative
  error at most 5e-6, far below their standard errors; methodology M14, D31). Every other
  number keeps full precision.

Version 3 adds ``residual_diagnostics`` (M3.5), ``quality_gate`` and ``five_day_regression``
(M3.6). When the gate fires, ``regression`` tags follow the conjunction rule of M3.6.

Version 4 is the schema v3 contract (``docs/specs/schema-v3-contract.md``): five optional
sections, each defined in its own module under ``report/sections/`` and ``None`` when not computed
(``lead_lag``, ``shrunk_betas``, ``fragility``, ``residual``, ``kalman_betas``), and the exclusion
reason ``lead_after_sample_end``. Version 3 files still load (SC5). The shared building blocks
(``SampleInfo``, the statistic base, the status and label types) live in ``report/base.py`` and
are re-exported here.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator, model_validator

from factordesk.report.base import FACTOR_NAMES as FACTOR_NAMES
from factordesk.report.base import LABEL_TEXT as LABEL_TEXT
from factordesk.report.base import ExcludedRow as ExcludedRow
from factordesk.report.base import ExclusionReason as ExclusionReason
from factordesk.report.base import FactorVintage as FactorVintage
from factordesk.report.base import FrozenModel as FrozenModel
from factordesk.report.base import LabelKey as LabelKey
from factordesk.report.base import ReportWarning as ReportWarning
from factordesk.report.base import SampleInfo as SampleInfo
from factordesk.report.base import SectionModel as SectionModel
from factordesk.report.base import SectionSpec as SectionSpec
from factordesk.report.base import Severity as Severity
from factordesk.report.base import StatisticModel as StatisticModel
from factordesk.report.base import Status as Status
from factordesk.report.base import Tag as Tag
from factordesk.report.sections.fragility import FRAGILITY_SECTION, FragilitySection
from factordesk.report.sections.kalman import KALMAN_SECTION, KalmanBetaSeries
from factordesk.report.sections.lead_lag import LEAD_LAG_SECTION, LeadLagSection
from factordesk.report.sections.residual_alpha import RESIDUAL_ALPHA_SECTION, ResidualAnalysis
from factordesk.report.sections.shrunk import SHRUNK_SECTION, ShrunkBetas

SCHEMA_VERSION = "5"
"""Version written by this code: 4 plus the optional ``data.security`` (contract SC5)."""

SUPPORTED_SCHEMA_VERSIONS: tuple[str, ...] = ("3", "4", "5")
"""Versions this code reads. Version 3 files have no optional sections and version 3 and 4 files
have no ``data.security``; they load unchanged (the new fields are absent, so ``None``)."""

AuditStatus = Literal["clean", "warnings", "errors"]

SECTIONS: tuple[SectionSpec, ...] = (
    LEAD_LAG_SECTION,
    SHRUNK_SECTION,
    FRAGILITY_SECTION,
    RESIDUAL_ALPHA_SECTION,
    KALMAN_SECTION,
)
"""The optional sections of the schema v3 contract, in panel order (contract SC3.1, SC4)."""


# ------------------------------------------------------------------------------ data provenance
class AuditFinding(FrozenModel):
    """One data-quality finding from the price audit (reported, never acted on)."""

    code: str = Field(description="Stable machine-readable code, e.g. 'large_return'.")
    severity: Severity
    message: str = Field(description="User-facing explanation in plain English.")
    dates: list[date] = Field(
        default_factory=lambda: [], description="Dates the finding refers to (may be empty)."
    )


class UncoveredTail(FrozenModel):
    """Price dates after the last factor date (M2 step 6). Never part of any statistic."""

    n: int = Field(ge=0, description="Trading days after the factor file's last date.")
    first: date | None
    last: date | None
    factor_last_date: date
    compounded_return: float | None = Field(
        description="Raw (not excess) compounded return over those days; None if n = 0 or a "
        "price is missing."
    )


class SecurityInfo(FrozenModel):
    """What Yahoo says the ticker is; every field is None when Yahoo did not say."""

    name: str | None = Field(default=None, description="Company or fund name.")
    currency: str | None = Field(
        default=None, description="Quote currency as Yahoo reports it, e.g. 'USD' or 'GBp'."
    )
    exchange: str | None = Field(default=None, description="Exchange name, e.g. 'NasdaqGS'.")


class DataInfo(FrozenModel):
    """Provenance and coverage of the data behind the report."""

    requested_start: date
    requested_end: date
    actual_start: date = Field(description="First date of the analysis sample.")
    actual_end: date = Field(description="Last date of the analysis sample.")
    n_obs: int = Field(ge=0, description="Rows in the analysis sample.")
    factors_last_date: date = Field(description="Last date for which French factor data exists.")
    factors_downloaded_at: datetime | None = Field(
        description="UTC download time of the factor file; None when injected."
    )
    factors_days_behind: int = Field(description="Days from factors_last_date to the report date.")
    factors_source_url: str
    price_source: str = Field(description="Price provider label, e.g. 'yfinance (Adj Close)'.")
    dropped_price_dates_after_factors: int = Field(
        ge=0, description="Price dates after factors_last_date that could not enter the sample."
    )
    dropped_price_dates_before_factors: int = Field(
        ge=0, description="Price dates before the factor file's first date."
    )
    n_excluded: int = Field(ge=0, description="Rows inside the range excluded (see reasons).")
    excluded_by_reason: dict[str, int]
    uncovered: UncoveredTail
    audit_status: AuditStatus
    audit_findings: list[AuditFinding] = Field(default_factory=lambda: [])
    security: SecurityInfo | None = Field(
        default=None,
        description="Company name, currency and exchange from Yahoo metadata; None when the "
        "read failed or the report is older than schema version 5.",
    )


# ------------------------------------------------------------------------------ regression (M3)
class FactorStat(FrozenModel):
    """Full-sample OLS coefficient for one factor. ``beta`` is a unitless sensitivity."""

    name: str
    beta: float | None
    se: float | None = Field(description="Newey-West HAC standard error of beta.")
    z: float | None = Field(description="HAC z-statistic (normal reference distribution).")
    p: float | None = Field(description="Two-sided p-value, unadjusted.")
    p_adj_bh: float | None = Field(description="Benjamini-Hochberg adjusted p (family of 5).")
    ci_low: float | None = Field(description="Lower bound of the unadjusted 95% HAC interval.")
    ci_high: float | None = Field(description="Upper bound of the unadjusted 95% HAC interval.")
    tag: Tag | None = Field(description="'reliable' when BH rejects at q = 0.05, else 'noise'.")
    interpretation: str | None = Field(
        description="Plain-English reading; generated only for reliable betas."
    )


class CorrPair(FrozenModel):
    """A factor pair whose sample correlation exceeds 0.6 in absolute value (M3.4)."""

    a: str
    b: str
    corr: float


class Regression(StatisticModel):
    """Full-sample excess-return regression ``y = alpha + sum(b_i f_i) + e`` (M3)."""

    alpha_annual: float | None = Field(description="Annualised alpha, decimal per year (x252).")
    alpha_se_annual: float | None
    alpha_z: float | None
    alpha_p: float | None
    alpha_ci_low_annual: float | None
    alpha_ci_high_annual: float | None
    alpha_tag: Tag | None = Field(
        description="'reliable' iff alpha_p < 0.05 (single test); when the quality gate fired, "
        "also the 5-day alpha p must be below 0.05 (M3.6)."
    )
    alpha_sentence: str | None = Field(
        description="Explanation shown when |alpha| >= 3% a year but p >= 0.05 (M3.2)."
    )
    r2: float | None
    adj_r2: float | None
    sigma_e_annual: float | None = Field(description="Residual volatility, sqrt(252) x sd.")
    hac_lags: int = Field(ge=0, description="Newey-West lag length L(n).")
    bh_family_size: int = Field(ge=0, description="Number of betas in the BH family (F1).")
    factors: list[FactorStat]
    vif: dict[str, float | None] = Field(description="Variance inflation factor per factor.")
    condition_number: float | None = Field(
        description="sqrt(max/min eigenvalue) of the 5x5 factor correlation matrix over the "
        "sample (M3.4). Not statsmodels' results.condition_number, which is computed on the raw "
        "design including the constant and is large even for uncorrelated daily factors."
    )
    high_corr_pairs: list[CorrPair]


# ------------------------------------------------------------------------------ diagnostics (M3.5)
DiagnosticCode = Literal[
    "ljung_box", "robust_breusch_godfrey", "arch_lm", "jarque_bera", "durbin_watson"
]


class DiagnosticTest(FrozenModel):
    """One residual diagnostic (M3.5). Informational: never drives tags or alerts."""

    code: DiagnosticCode
    name: str = Field(description="Display name.")
    statistic: float | None
    df: int | None = Field(
        description="Degrees of freedom of the chi-square reference; None for Durbin-Watson."
    )
    p: float | None = Field(description="Nominal p-value, not corrected; None for Durbin-Watson.")
    reading: str = Field(description="Plain-language reading of the result.")


class ResidualDiagnostics(StatisticModel):
    """Diagnostics of the full-sample regression residuals (M3.5)."""

    lag1_autocorrelation: float | None = Field(
        description="sum e_t e_{t-1} / sum e_t^2 over the full-sample residuals."
    )
    lag1_se: float | None = Field(description="Heteroskedasticity-robust standard error.")
    lag1_z: float | None
    lag1_p: float | None = Field(description="Two-sided normal p-value of lag1_z.")
    lag1_reading: str | None
    tests: list[DiagnosticTest]
    note: str = Field(description="HAC is used whatever the tests show.")


class QualityGate(StatisticModel):
    """Residual quality gate for non-synchronous prices (M3.6)."""

    rho_threshold: float | None = Field(description="Fires when lag-1 autocorrelation < this.")
    z_threshold: float | None = Field(description="... and its robust z < this.")
    lag1_autocorrelation: float | None
    lag1_z: float | None
    fired: bool | None
    noise_share: float | None = Field(
        description="min(1, -2 x lag-1 autocorrelation): share of residual variance that is a "
        "price error reversing the next day, under the simple model of M3.6."
    )
    message: str | None = Field(description="The caveat shown in the report when fired.")


class MultiDayRegression(StatisticModel):
    """Regression on sums over non-overlapping 5-day blocks (M3.6); only when the gate fired."""

    horizon_days: int = Field(ge=0, description="Block length in trading days (5).")
    n_blocks: int = Field(ge=0)
    n_rows_unused: int = Field(ge=0, description="Rows after the last full block (0-4).")
    blocks_start: date | None
    blocks_end: date | None
    alpha_annual: float | None = Field(description="(252 / horizon) x block intercept.")
    alpha_se_annual: float | None
    alpha_z: float | None
    alpha_p: float | None
    alpha_ci_low_annual: float | None
    alpha_ci_high_annual: float | None
    alpha_tag: Tag | None = Field(description="'reliable' iff alpha_p < 0.05.")
    r2: float | None
    adj_r2: float | None
    sigma_e_annual: float | None = Field(description="sqrt(252 / horizon) x sd of residuals.")
    hac_lags: int = Field(ge=0, description="Newey-West lags L(n_blocks).")
    bh_family_size: int = Field(ge=0, description="Betas in BH family F9.")
    factors: list[FactorStat]


# ------------------------------------------------------------------------------ rolling (M4, M5)
class RollingWindow(StatisticModel):
    """Trailing-window betas. ``betas[name][i]`` belongs to ``dates[i]``; None during warm-up.

    Each stamp uses exactly ``window`` rows of the sample ending on (and including) its date.
    The pointwise 95% band is ``beta +/- ci_z * se``.
    """

    window: int = Field(gt=0, description="Window length in trading days (e.g. 126 or 252).")
    n_stamps: int = Field(ge=0, description="Number of stamps, n - window + 1.")
    hac_lags: int = Field(ge=0, description="Newey-West lags L(window).")
    ci_z: float | None = Field(
        description="Normal quantile for the pointwise 95% band; None when status is not 'ok'."
    )
    dates: list[date]
    window_start: list[date | None] = Field(description="First date of each stamp's window.")
    betas: dict[str, list[float | None]] = Field(
        description="Rolling betas per stamp, rounded to 6 significant digits (D31)."
    )
    se: dict[str, list[float | None]] = Field(
        description="HAC standard errors per stamp, rounded to 6 significant digits (D31)."
    )

    @model_validator(mode="after")
    def _lengths_match(self) -> RollingWindow:
        """Every series must be aligned one-to-one with ``dates``."""
        n = len(self.dates)
        if len(self.window_start) != n:
            raise ValueError("window_start must align with dates")
        for kind, block in (("beta", self.betas), ("se", self.se)):
            for name, series in block.items():
                if len(series) != n:
                    raise ValueError(
                        f"rolling {kind} series '{name}' has {len(series)} points "
                        f"but there are {n} dates"
                    )
        return self


class AverageBeta(FrozenModel):
    """Distribution of the rolling betas of the primary window for one factor (M5)."""

    name: str
    full_sample_beta: float | None
    mean: float | None
    sd: float | None = Field(description="Standard deviation (ddof = 1); not a standard error.")
    p10: float | None
    p90: float | None
    min: float | None
    max: float | None
    share_positive: float | None = Field(description="Share of stamps with beta > 0.")


class AverageBetaPanel(StatisticModel):
    """Average beta over all stamps of the primary window (M5). Stamped at the sample end."""

    window: int = Field(gt=0)
    n_stamps: int = Field(ge=0)
    factors: list[AverageBeta]


# ------------------------------------------------------------------------------ attribution (M6)
class ReturnContribution(StatisticModel):
    """Static arithmetic return attribution, annualised decimals (M6.1, M6.4).

    ``sum(factors) + alpha + residual == total_annualised_mean_excess_return`` up to
    ``identity_residual``. Memo rows are outside every sum.
    """

    factors: dict[str, float | None] = Field(description="252 x beta_i x mean(f_i) per factor.")
    alpha: float | None = Field(description="252 x alpha (daily intercept).")
    residual: float | None = Field(description="252 x mean(residual); 0 by construction.")
    total_annualised_mean_excess_return: float | None
    identity_residual: float | None = Field(
        description="total - (sum(factors) + alpha + residual); float error only (~1e-17)."
    )
    memo: list[str] = Field(description="Memo rows: uncovered dates and excluded rows (D8).")


class RiskFactorDetail(FrozenModel):
    """Exposure x volatility x correlation view of one factor's risk share (M7)."""

    name: str
    share: float | None = Field(description="Euler share of variance RC_i (may be negative).")
    beta: float | None
    sigma_annual: float | None = Field(description="Factor volatility, sqrt(252) x sd.")
    rho_sys: float | None = Field(
        description="Correlation of the factor with the systematic return beta'f."
    )


class RiskContribution(StatisticModel):
    """Euler risk decomposition over the full sample (M7). Shares may be negative."""

    factors: dict[str, float | None] = Field(description="RC_i, share of variance per factor.")
    idiosyncratic: float | None = Field(description="sigma2_e / V with sigma2_e = SSR/(n-1).")
    sums_to_one_residual: float | None = Field(
        description="1 - (sum(factors) + idiosyncratic); float error only."
    )
    total_vol_annual: float | None = Field(description="sqrt(252 x V).")
    order: list[str] = Field(
        description="Display order: factors by share descending, then 'Idiosyncratic'."
    )
    details: list[RiskFactorDetail]
    sentences: list[str] = Field(description="Disagreement / offset sentences (M7).")


# ------------------------------------------------------------------------------ price + report
class PriceSeries(FrozenModel):
    """Adjusted close for charting only (never used for regression here)."""

    dates: list[date]
    adj_close: list[float | None] = Field(description="Adjusted close in price units.")
    factor_coverage_end: date = Field(
        description="Last date with factor data; later points are drawn muted."
    )

    @model_validator(mode="after")
    def _lengths_match(self) -> PriceSeries:
        """Dates and prices must be aligned one-to-one."""
        if len(self.dates) != len(self.adj_close):
            raise ValueError("price dates and adj_close must have equal length")
        return self


class FactorReport(FrozenModel):
    """Everything the UI or an exported file needs to describe one ticker's factor exposures."""

    schema_version: str = SCHEMA_VERSION
    ticker: str
    generated_at: datetime = Field(description="Timezone-aware UTC timestamp.")
    data: DataInfo
    regression: Regression
    rolling: list[RollingWindow] = Field(description="One entry per window, e.g. 126 and 252.")
    average_beta: AverageBetaPanel
    return_contribution: ReturnContribution
    risk_contribution: RiskContribution
    residual_diagnostics: ResidualDiagnostics
    quality_gate: QualityGate
    five_day_regression: MultiDayRegression
    price_series: PriceSeries
    warnings: list[ReportWarning] = Field(default_factory=lambda: [])
    notes: list[str] = Field(
        default_factory=lambda: [],
        description="User-facing caveats: in-sample, US factors, survivorship, vintage.",
    )
    label_text: dict[str, str] = Field(
        default_factory=lambda: dict(LABEL_TEXT), description="Footnote texts by label key."
    )
    # Optional sections of the schema v3 contract (docs/specs/schema-v3-contract.md), in panel
    # order. None: the feature did not run for this report (always None in version 3 files).
    lead_lag: LeadLagSection | None = Field(
        default=None, description="Lead-lag betas (docs/specs/lead-lag-betas.md)."
    )
    shrunk_betas: list[ShrunkBetas] | None = Field(
        default=None,
        description="Shrunk betas, one entry per scope: full sample, then latest window "
        "(docs/specs/shrunk-betas.md).",
    )
    fragility: FragilitySection | None = Field(
        default=None, description="Fragility score (docs/specs/fragility-score.md)."
    )
    residual: ResidualAnalysis | None = Field(
        default=None,
        description="Residual alpha analysis (docs/methodology-residual-analysis.md).",
    )
    kalman_betas: KalmanBetaSeries | None = Field(
        default=None, description="Kalman-filter betas (docs/specs/kalman-betas.md)."
    )

    @field_validator("schema_version")
    @classmethod
    def _supported_version(cls, value: str) -> str:
        """Only versions this code can read (contract SC5)."""
        if value not in SUPPORTED_SCHEMA_VERSIONS:
            raise ValueError(
                f"schema_version {value!r} is not supported; supported versions: "
                + ", ".join(SUPPORTED_SCHEMA_VERSIONS)
            )
        return value

    @model_validator(mode="after")
    def _sections_need_version_4(self) -> FactorReport:
        """A version 3 file has no optional sections."""
        if self.schema_version == "3":
            present = [s.report_field for s in SECTIONS if getattr(self, s.report_field)]
            if present:
                raise ValueError(f"a version 3 report cannot hold {', '.join(present)}")
        return self

    @model_validator(mode="after")
    def _security_needs_version_5(self) -> FactorReport:
        """A version 3 or 4 file has no ``data.security``."""
        if self.schema_version in ("3", "4") and self.data.security is not None:
            raise ValueError(f"a version {self.schema_version} report cannot hold data.security")
        return self

    @model_validator(mode="after")
    def _utc_timestamp(self) -> FactorReport:
        """``generated_at`` must be timezone-aware with a zero UTC offset."""
        if self.generated_at.utcoffset() != timedelta(0):
            raise ValueError("generated_at must be timezone-aware UTC")
        return self


# ------------------------------------------------- API envelope (not part of FactorReport)

RangePreset = Literal["3Y", "5Y", "FULL"]
RANGE_PRESETS: tuple[RangePreset, ...] = ("3Y", "5Y", "FULL")
"""Range presets in display order (dashboard spec DB2.2; owner decision of 2026-11-18 dropped
YTD and 1Y)."""

ErrorCode = Literal[
    "invalid_ticker",
    "unknown_ticker",
    "bad_range",
    "insufficient_history",
    "degenerate_input",
    "unsupported_currency",
    "factor_data_invalid",
    "network",
    "upstream_refused",
    "not_found",
    "internal",
    "bad_request",
]
"""Error codes of the local API (dashboard spec DB2.3). ``bad_request`` covers any other
malformed request parameter."""


class Health(FrozenModel):
    """Liveness answer; reads no disk and no network."""

    status: Literal["ok"]
    version: str
    schema_version: str


class FactorDataStatus(FrozenModel):
    """Coverage and age of the cached Fama-French file; ``available`` is False when none."""

    available: bool
    first_date: date | None
    last_date: date | None
    days_behind: int | None
    last_download_at: datetime | None
    stale: bool | None
    source_url: str


class TickerSuggestion(FrozenModel):
    ticker: str
    last_fetched: date
    name: str | None = Field(
        default=None, description="Company name when its metadata is already cached."
    )


class TickerSuggestions(FrozenModel):
    items: list[TickerSuggestion]


class RangeOption(FrozenModel):
    """One range preset for one ticker; ``reason`` is None exactly when ``available``."""

    preset: RangePreset
    start: date | None
    n_obs: int
    available: bool
    reason: str | None

    @model_validator(mode="after")
    def _reason_iff_unavailable(self) -> RangeOption:
        if self.available != (self.reason is None):
            raise ValueError("reason must be None exactly when the option is available")
        return self


class RangeOptions(FrozenModel):
    """Availability of every preset for one ticker (always three, in preset order)."""

    ticker: str
    first_return_date: date
    last_price_date: date
    factors_last_date: date
    min_obs: int
    options: list[RangeOption]

    @model_validator(mode="after")
    def _presets_in_order(self) -> RangeOptions:
        if tuple(option.preset for option in self.options) != RANGE_PRESETS:
            raise ValueError("options must hold every preset exactly once, in preset order")
        return self


class ApiError(FrozenModel):
    """Every error body: ``message`` says what went wrong, ``action`` what to do."""

    code: ErrorCode
    message: str
    action: str


STATISTIC_MODELS: tuple[type[StatisticModel], ...] = (
    Regression,
    RollingWindow,
    AverageBetaPanel,
    ReturnContribution,
    RiskContribution,
    ResidualDiagnostics,
    QualityGate,
    MultiDayRegression,
    *(model for spec in SECTIONS for model in spec.statistic_models),
)
"""Every statistic model in the report (each carries status, reason and SampleInfo): the core
statistics, then the nested statistics of the optional sections."""


def report_label_text(
    present: Mapping[str, object | None], sections: Sequence[SectionSpec] = SECTIONS
) -> dict[str, str]:
    """``LABEL_TEXT`` plus the footnote texts of every section whose value is not ``None``.

    ``present`` maps report field names to the section values (contract SC1 item 5).
    """
    out = dict(LABEL_TEXT)
    for spec in sections:
        if present.get(spec.report_field) is not None:
            out.update(spec.label_text)
    return out


def report_json_schema() -> dict[str, object]:
    """Return the JSON Schema of ``FactorReport`` (for frontend type generation and docs)."""
    return FactorReport.model_json_schema()


def load_report(path: str | Path) -> FactorReport:
    """Read and validate a report previously written as JSON (UTF-8).

    Reads every version in ``SUPPORTED_SCHEMA_VERSIONS``. A version 3 file loads with the optional
    sections ``None`` and keeps ``schema_version == "3"``.
    """
    return FactorReport.model_validate_json(Path(path).read_text(encoding="utf-8"))


def dump_report(report: FactorReport, path: str | Path) -> None:
    """Write ``report`` as compact UTF-8 JSON (one line, LF-terminated; D31)."""
    payload = report.model_dump_json() + "\n"
    Path(path).write_bytes(payload.encode("utf-8"))
