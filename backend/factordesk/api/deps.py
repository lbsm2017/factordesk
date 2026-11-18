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
from factordesk.data.factors import FactorStatus, factor_status, load_ff5_daily
from factordesk.data.prices import PriceProvider, YFinanceProvider

if TYPE_CHECKING:
    from factordesk.section_hooks.context import SectionInputs

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
    load_section_inputs: Callable[[datetime], SectionInputs] | None = None
    """Extra data of the optional report sections (the portfolio files of the shrunk betas),
    loaded once per day and vintage. ``None``: none, so those sections are not computed."""

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

    def status(now: datetime) -> FactorStatus | None:
        return factor_status(data_dir=data_dir, now=now)

    def section_inputs(now: datetime) -> SectionInputs:
        from factordesk.section_hooks.context import SectionInputs
        from factordesk.section_hooks.shrunk import load_shrinkage_inputs

        return SectionInputs(
            shrinkage_portfolios=load_shrinkage_inputs(now, offline=False, data_dir=data_dir)
        )

    return AppDeps(
        price_provider=YFinanceProvider(cache_dir=data_dir / "prices", now=utc_now),
        load_factors=load_factors,
        factor_status=status,
        now=utc_now,
        data_dir=data_dir,
        static_dir=static_dir,
        load_section_inputs=section_inputs,
    )
