"""Everything the API needs from the outside world, injected (dashboard spec DB1).

``AppDeps`` holds the price provider, the factor loader and status reader, the clock and the
directories. Tests build it from fakes; ``default_deps`` wires the real data layer. Importing
this module reads no disk and no network.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd

from factordesk.config import get_settings
from factordesk.data.factors import (
    FactorDownloadError,
    FactorStatus,
    factor_status,
    load_ff5_daily,
)
from factordesk.data.prices import PriceProvider, YFinanceProvider

if TYPE_CHECKING:
    from factordesk.section_hooks.context import MacroInput, SectionInputs, WorldBenchmarkInput

logger = logging.getLogger(__name__)


def utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class AppDeps:
    """Injected collaborators of the API.

    ``load_factors(refresh, now)`` returns the factor frame (downloading when asked or
    needed). ``factor_status(now)`` describes the cached file, or None when nothing is cached.
    """

    price_provider: PriceProvider
    load_factors: Callable[[bool, datetime], pd.DataFrame]
    factor_status: Callable[[datetime], FactorStatus | None]
    now: Callable[[], datetime]
    data_dir: Path
    static_dir: Path | None
    max_workers: int = 2
    report_cache_size: int = 32
    refresh_portfolios: Callable[[datetime], None] | None = None
    """Checks the portfolio files against the site; runs after a factor refresh. Raises
    ``FactorDownloadError`` when they cannot be refreshed. ``None``: nothing to refresh."""
    load_section_inputs: Callable[[datetime], SectionInputs] | None = None
    """Extra data of the optional report sections (the portfolio files of the shrunk betas),
    loaded once per day and vintage. ``None``: none, so those sections are not computed."""
    load_world_benchmark: Callable[[], WorldBenchmarkInput] | None = None
    """The ACWI history of the world beta, refreshed by the new days on every report build (the
    refresh makes no network call while the cache holds the latest completed trading day).
    Never raises. ``None``: not wired, so the world beta is not computed."""
    load_europe_benchmark: Callable[[], WorldBenchmarkInput] | None = None
    """The IEUR history of the Europe block of the world beta, refreshed like the ACWI one.
    Never raises. ``None``: not wired, so the Europe block is null."""
    load_macro: Callable[[], MacroInput] | None = None
    """The fund histories and the dollar index of the macro section, refreshed like the world
    beta proxies (the dollar file is cached per day). Never raises. ``None``: not wired, so the
    macro section is not computed."""
    load_ff6: Callable[[datetime], pd.DataFrame] | None = None
    """The daily FF6 frame (FF5 + RF + ``Mom``, ``data.french.load_ff6("daily")``). It feeds the
    FF6 model and the alpha strip of every report. May raise ``FactorError``: an FF6 report then
    fails, an FF5 report falls back to ``load_factors`` without the strip. ``None``: not wired, so
    FF6 is refused and FF5 reports have no alpha strip."""

    def __post_init__(self) -> None:
        if self.max_workers < 1:
            raise ValueError("max_workers must be at least 1")
        if self.report_cache_size < 1:
            raise ValueError("report_cache_size must be at least 1")


def default_deps(static_dir: Path | None = None) -> AppDeps:
    """Wire the real providers, the UTC clock and the configured data directory."""
    data_dir = Path(get_settings().data_dir).resolve()
    logger.info("factordesk data directory: %s", data_dir)

    def load_factors(refresh: bool, now: datetime) -> pd.DataFrame:
        return load_ff5_daily(refresh=refresh, data_dir=data_dir, now=now)

    def load_ff6_daily(now: datetime) -> pd.DataFrame:
        from factordesk.data.french import load_ff6

        return load_ff6("daily", data_dir=data_dir, now=now)

    def status(now: datetime) -> FactorStatus | None:
        return factor_status(data_dir=data_dir, now=now)

    def section_inputs(now: datetime) -> SectionInputs:
        from factordesk.section_hooks.context import SectionInputs
        from factordesk.section_hooks.shrunk import load_shrinkage_inputs

        status = factor_status(data_dir=data_dir, now=now)
        return SectionInputs(
            shrinkage_portfolios=load_shrinkage_inputs(
                now,
                offline=False,
                data_dir=data_dir,
                factor_last_date=None if status is None else status.last_date,
            )
        )

    def refresh_portfolios(now: datetime) -> None:
        from factordesk.data.portfolios import PortfolioError
        from factordesk.section_hooks.shrunk import refresh_shrinkage_inputs

        try:
            refresh_shrinkage_inputs(now, data_dir=data_dir)
        except PortfolioError as exc:
            raise FactorDownloadError(str(exc)) from exc

    price_provider = YFinanceProvider(cache_dir=data_dir / "prices", now=utc_now)

    def world_benchmark() -> WorldBenchmarkInput:
        from factordesk.section_hooks.world_beta import load_world_benchmark

        return load_world_benchmark(price_provider)

    def europe_benchmark() -> WorldBenchmarkInput:
        from factordesk.analytics.world_beta import EUROPE_TICKER
        from factordesk.section_hooks.world_beta import load_world_benchmark

        return load_world_benchmark(price_provider, EUROPE_TICKER)

    def macro() -> MacroInput:
        from factordesk.section_hooks.macro import load_macro_input

        return load_macro_input(price_provider, data_dir=data_dir, now=utc_now())

    return AppDeps(
        price_provider=price_provider,
        load_factors=load_factors,
        factor_status=status,
        now=utc_now,
        data_dir=data_dir,
        static_dir=static_dir,
        refresh_portfolios=refresh_portfolios,
        load_section_inputs=section_inputs,
        load_world_benchmark=world_benchmark,
        load_europe_benchmark=europe_benchmark,
        load_macro=macro,
        load_ff6=load_ff6_daily,
    )
