"""What a section hook receives from ``assemble_report`` (schema v3 contract, SC3.2).

The context is built once, after every core section is finished. Hooks read it; they never
mutate it, never change a core section, and never read another feature's section.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime

import pandas as pd

from factordesk.analytics.diagnostics import DiagnosticsResult, GateResult, MultiDayFit
from factordesk.analytics.regression import FullSampleRegression
from factordesk.analytics.rolling import RollingBetas
from factordesk.analytics.sample import AnalysisSample
from factordesk.data.audit import AuditReport
from factordesk.data.prices import PriceHistory
from factordesk.report.schema import (
    AverageBetaPanel,
    DataInfo,
    FactorVintage,
    MultiDayRegression,
    PriceSeries,
    QualityGate,
    Regression,
    ResidualDiagnostics,
    ReturnContribution,
    RiskContribution,
    RollingWindow,
    SampleInfo,
)


@dataclass(frozen=True)
class SectionInputs:
    """Data a section needs that ``assemble_report`` does not already have.

    ``build_report`` fills it through ``section_hooks.load_section_inputs``; tests pass it in.
    """

    shrinkage_portfolios: Mapping[str, pd.DataFrame] | None = None
    """Ken French portfolio return frames for the shrunk-betas prior, by dataset key (SB2.2).
    Owned by the shrunk-betas feature."""


@dataclass(frozen=True)
class CoreSections:
    """The finished core sections of the report, as they will appear in ``FactorReport``."""

    data: DataInfo
    regression: Regression
    rolling: Sequence[RollingWindow]
    average_beta: AverageBetaPanel
    return_contribution: ReturnContribution
    risk_contribution: RiskContribution
    residual_diagnostics: ResidualDiagnostics
    quality_gate: QualityGate
    five_day_regression: MultiDayRegression
    price_series: PriceSeries


@dataclass(frozen=True)
class SectionContext:
    """Everything a section hook may use. Built by ``pipeline.assemble_report``."""

    ticker: str
    now: datetime
    history: PriceHistory
    """Prices after repeated dates were collapsed (D29)."""
    factor_frame: pd.DataFrame
    """The whole French factor frame (for the French calendar of lead-lag LL2.2)."""
    sample: AnalysisSample
    """The aligned analysis sample ``S`` (M2)."""
    vintage: FactorVintage
    audit: AuditReport
    daily: FullSampleRegression
    """The M3.1 daily fit, before the quality gate."""
    regression: FullSampleRegression
    """The fit behind the reported tags (after the gate, M3.6)."""
    diagnostics: DiagnosticsResult | None
    gate: GateResult | None
    five_day: MultiDayFit | None
    rolling: Mapping[int, RollingBetas]
    """Rolling betas by window, including the primary window (M4)."""
    primary_window: int
    core: CoreSections
    inputs: SectionInputs
    make_sample_info: Callable[[int | None], SampleInfo]

    def sample_info(self, window: int | None = None) -> SampleInfo:
        """``SampleInfo`` of the analysis sample, with ``window`` as its trailing-window length."""
        return self.make_sample_info(window)
