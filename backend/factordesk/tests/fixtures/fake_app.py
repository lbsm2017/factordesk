"""A runnable fake backend for the browser smoke test (dashboard spec DB8.2, ticket T10).

``create`` is a uvicorn app factory::

    uv run uvicorn factordesk.tests.fixtures.fake_app:create --factory --port 8765

It builds the real application (``create_app``) with fake collaborators: a price provider that
serves one synthetic history (``dgp_a``) for any ticker except ``XYZ``, a factor frame cut 30
rows before the price end, a fixed clock and an empty temporary data directory. It serves the
built page from ``frontend/dist``. Nothing here reads the real data directory or the network, and
the output is the same on every run.
"""

from __future__ import annotations

import dataclasses
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pandas as pd
from fastapi import FastAPI

from factordesk.api.deps import AppDeps
from factordesk.api.main import create_app
from factordesk.data import factors as factors_module
from factordesk.data.factors import FactorStatus
from factordesk.data.prices import PriceDataError, PriceHistory
from factordesk.tests.fixtures.dgp import dgp_a, rng_for

UNKNOWN_TICKER = "XYZ"
"""The one ticker the fake provider refuses, as Yahoo does for an unknown symbol."""

N_PRICES = 2520
FACTOR_CUT = 30
TEST_NUMBER = 1000
DOWNLOADED = datetime(2020, 1, 20, 8, 30, tzinfo=UTC)
FRONTEND_DIST = Path(__file__).resolve().parents[4] / "frontend" / "dist"


class FakeProvider:
    """Serves one fixed history for every ticker but ``UNKNOWN_TICKER``."""

    def __init__(self, history: PriceHistory) -> None:
        self.history = history

    def fetch(self, ticker: str) -> PriceHistory:
        if ticker == UNKNOWN_TICKER:
            raise PriceDataError(f"No price data returned for {ticker!r} (invalid or delisted?)")
        return dataclasses.replace(self.history, ticker=ticker)


def _day(value: object) -> datetime:
    return pd.Timestamp(str(value)).to_pydatetime().replace(tzinfo=UTC)


def create() -> FastAPI:
    """The fake application. Takes no arguments so uvicorn can call it as a factory."""
    d = dgp_a(rng_for(TEST_NUMBER), n=N_PRICES)
    factors = d.factors.iloc[: N_PRICES - FACTOR_CUT]
    now = _day(d.history.frame.index[-1]).replace(hour=15) + timedelta(days=1)
    first = _day(factors.index[0]).date()
    last = _day(factors.index[-1]).date()
    behind = (now.date() - last).days
    status = FactorStatus(
        last_date=last,
        first_date=first,
        days_behind=behind,
        last_download_at=DOWNLOADED,
        source_url=factors_module.SOURCE_URL,
        stale=behind > factors_module.STALE_AFTER_DAYS,
    )
    data_dir = Path(tempfile.mkdtemp(prefix="factordesk-fake-"))
    deps = AppDeps(
        price_provider=FakeProvider(d.history),
        load_factors=lambda refresh, at: factors,
        factor_status=lambda at: status,
        now=lambda: now,
        data_dir=data_dir,
        static_dir=FRONTEND_DIST,
    )
    return create_app(deps)
