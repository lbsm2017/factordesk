"""What a section hook receives from ``assemble_report`` (schema v3 contract, SC3.2).

The context is built once, after every core section is finished. Hooks read it; they never
mutate it, never change a core section, and never read another feature's section.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal

import pandas as pd

from factordesk.analytics.backtest import BacktestResult
from factordesk.analytics.diagnostics import DiagnosticsResult, GateResult, MultiDayFit
from factordesk.analytics.regression import FullSampleRegression
from factordesk.analytics.rolling import RollingBetas
from factordesk.analytics.sample import AnalysisSample
from factordesk.analytics.subject import ReturnSubject
from factordesk.data.audit import AuditReport
from factordesk.data.prices import PriceHistory
from factordesk.report.schema import (
    AverageBetaPanel,
    DataInfo,
    FactorModel,
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

FACTOR_MODELS: tuple[FactorModel, ...] = ("ff5", "ff6")


@dataclass(frozen=True)
class WorldBenchmarkInput:
    """The price history of a world beta proxy (ACWI, IEUR), or why there is none.

    ``history`` is ``None`` when the proxy could not be fetched (``unavailable_reason`` says why).
    ``note`` is set when the refresh failed and the cached history was used.
    """

    history: PriceHistory | None
    unavailable_reason: str | None = None
    note: str | None = None


USD_CASH_LEAF = "usd_cash"
"""Backtest leaf of the USD cash instruments in the EUR view (their return is converted); the
unallocated weight stays in the backtest's own cash leaf, which is euro cash in that view."""


@dataclass(frozen=True)
class HoldingsNode:
    """One group or holding of the portfolio tree, as the holdings table lists it."""

    id: str
    """A holding: its backtest leaf id (``i:<tree id>``). A group: ``g:<tree id>``."""
    kind: Literal["group", "holding"]
    label: str
    ticker: str | None
    parent_id: str | None
    """The group that contains this node; ``None`` for an asset class."""
    depth: int
    """0 for an asset class, 1 for a sub-asset class, 2 for a holding."""
    path: tuple[str, ...]
    """Group ids from the asset class down to this node's own group. For a group the path ends
    with its own id; for a holding it is the path of its parent group."""


@dataclass(frozen=True)
class HoldingsInput:
    """The backtest and the tree layout the holdings section is built from.

    ``nodes`` are the groups and the holdings that took part in the backtest, in tree order (a
    group before its members). A group with no holding above 0 is not listed. Cash and the
    trading cost are not nodes: the backtest has one cash leaf, and the section adds both as rows
    of their own.
    """

    backtest: BacktestResult
    nodes: tuple[HoldingsNode, ...]


@dataclass(frozen=True)
class PortfolioBacktestInput:
    """What the backtest of a portfolio subject says about itself (read by the
    ``portfolio_backtest`` hook; built by ``api.portfolio_report``).

    Leaf names are display labels. ``weights`` holds ``(label, ticker or None, weight)`` for every
    instrument with a target above 0; with ``unallocated_weight`` they add up to 1.
    """

    window_start: date
    window_end: date
    start_limited_by: tuple[str, ...]
    end_limited_by: tuple[str, ...]
    n_instruments: int
    n_rebalances: int
    n_dates_dropped: int
    cost_bps: float
    total_cost: float
    average_turnover: float
    unallocated_weight: float
    survivorship_note: str
    weights: tuple[tuple[str, str | None, float], ...]
    holdings: HoldingsInput | None = None
    """The backtest and tree layout behind the holdings section (read by the ``holdings`` hook)."""
    unallocated_currency: str | None = None
    """``"EUR"`` when the unallocated weight is held as euro cash (the EUR view); ``None``: USD."""


@dataclass(frozen=True)
class DollarInput:
    """The Fed broad dollar index (FRED ``DTWEXBGS``) levels, or why there are none.

    ``levels`` is ``None`` when the series could not be fetched and no cached copy exists
    (``unavailable_reason`` says why); the macro section then runs without the dollar.
    ``note`` is set when an older cached copy was used.
    """

    levels: pd.Series | None
    unavailable_reason: str | None = None
    note: str | None = None


@dataclass(frozen=True)
class MacroInput:
    """The data of the macro section: five fund histories and the dollar index.

    ``funds`` maps a Yahoo ticker (IEF, LQD, DBC, TIP, IEI) to its history or the reason it is
    missing, as for the world beta proxies.
    """

    funds: Mapping[str, WorldBenchmarkInput]
    dollar: DollarInput


@dataclass(frozen=True)
class SeriesInput:
    """The levels of one FRED series, or why there are none (same shape as ``DollarInput``).

    ``levels`` is ``None`` when the series could not be fetched and no cached copy exists.
    ``note`` is set when an older cached copy was used.
    """

    levels: pd.Series | None
    unavailable_reason: str | None = None
    note: str | None = None


@dataclass(frozen=True)
class EnergyInput:
    """The data of the energy section: Brent and Henry Hub spot prices and the KRBN history.

    ``carbon`` is the KRBN history (or the reason it is missing), as for the macro funds.
    """

    oil: SeriesInput
    gas: SeriesInput
    carbon: WorldBenchmarkInput


@dataclass(frozen=True)
class ReferenceInput:
    """What the macro and energy sections need in the EUR view.

    ``fx_returns(calendar)`` is the return of one US dollar in euros over each interval of the
    subject's calendar (origin first), indexed by ``calendar[1:]``. ``usd_rf`` is the French
    (US dollar) risk-free return on the factor frame's dates; the euro frame's ``RF`` is euro cash.
    """

    fx_returns: Callable[[pd.DatetimeIndex], pd.Series]
    usd_rf: pd.Series


@dataclass(frozen=True)
class SectionInputs:
    """Data a section needs that ``assemble_report`` does not already have.

    ``build_report`` fills it through ``section_hooks.load_section_inputs``; tests pass it in.
    """

    shrinkage_portfolios: Mapping[str, pd.DataFrame] | None = None
    """Ken French portfolio return frames for the shrunk-betas prior, by dataset key (SB2.2).
    Owned by the shrunk-betas feature."""
    world_benchmark: WorldBenchmarkInput | None = None
    """ACWI prices for the world beta; ``None``: not fetched, the section does not run.
    Owned by the world-beta feature."""
    europe_benchmark: WorldBenchmarkInput | None = None
    """IEUR prices for the Europe block of the world beta; ``None``: not fetched, the block is
    null. Owned by the world-beta feature."""
    portfolio_backtest: PortfolioBacktestInput | None = None
    """The backtest summary of a portfolio subject; ``None`` for every other subject."""
    macro: MacroInput | None = None
    """Fund prices and the dollar index of the macro section; ``None``: not fetched, the section
    does not run. Owned by the macro feature."""
    energy: EnergyInput | None = None
    """Brent, Henry Hub and KRBN of the energy section; ``None``: not fetched, the section does
    not run. Owned by the energy feature."""
    reference: ReferenceInput | None = None
    """The EUR view of the macro and energy sections; ``None``: the US-dollar view."""


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
    """Everything a section hook may use. Built by ``pipeline.assemble_subject_report``.

    A hook runs only for the subjects, frequencies and models its ``HookSpec`` declares
    (``section_hooks/registry.py``), so a daily-only hook never sees a monthly context.
    """

    ticker: str
    """The subject's label (the ticker symbol in ticker mode)."""
    now: datetime
    history: PriceHistory | None
    """Prices after repeated dates were collapsed (D29); ``None`` unless the subject is a
    ticker. Hooks that need dates use ``subject.calendar``."""
    factor_frame: pd.DataFrame
    """The whole French factor frame (for the French calendar of lead-lag LL2.2)."""
    sample: AnalysisSample
    """The aligned analysis sample ``S`` (M2)."""
    vintage: FactorVintage
    audit: AuditReport
    daily: FullSampleRegression
    """The M3.1 fit at the subject's own frequency, before the quality gate (daily data only)."""
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
    subject: ReturnSubject
    """What the report is about: kind, frequency, returns, calendar, levels."""
    model: FactorModel = "ff5"

    def sample_info(self, window: int | None = None) -> SampleInfo:
        """``SampleInfo`` of the analysis sample, with ``window`` as its trailing-window length."""
        return self.make_sample_info(window)
