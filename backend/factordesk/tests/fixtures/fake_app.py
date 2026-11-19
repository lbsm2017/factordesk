"""A runnable fake backend for the browser smoke test (dashboard spec DB8.2, ticket T10).

``create`` is a uvicorn app factory::

    uv run uvicorn factordesk.tests.fixtures.fake_app:create --factory --port 8765

It builds the real application (``create_app``) with fake collaborators: a price provider that
serves one synthetic history (``dgp_a``) for any ticker except ``XYZ``, a factor frame cut 30
rows before the price end (with a synthetic momentum column for FF6 and the alpha strip), a monthly
factor frame for the upload route (also with momentum), a fixed clock and an
empty temporary data directory. It serves the
built page from ``frontend/dist``. Nothing here reads the real data directory or the network, and
the output is the same on every run.
"""

from __future__ import annotations

import dataclasses
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
from fastapi import FastAPI

from factordesk.api import routes_upload
from factordesk.api.deps import AppDeps
from factordesk.api.main import create_app
from factordesk.data import factors as factors_module
from factordesk.data.factors import FactorStatus
from factordesk.data.prices import PriceDataError, PriceHistory
from factordesk.tests.fixtures.dgp import dgp_a, rng_for
from factordesk.tests.test_subject import monthly_case

UNKNOWN_TICKER = "XYZ"
"""The one ticker the fake provider refuses, as Yahoo does for an unknown symbol."""

N_PRICES = 2520
FACTOR_CUT = 30
TEST_NUMBER = 1000
DOWNLOADED = datetime(2020, 1, 20, 8, 30, tzinfo=UTC)
MONTHLY_START = "2015-01-31"
MONTHLY_MONTHS = 96
"""The fake monthly factor file covers January 2015 to December 2022; the upload e2e test sends
84 months from January 2015."""
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
    _, monthly, _ = monthly_case(MONTHLY_MONTHS, 21, start=MONTHLY_START)
    monthly.attrs = {"downloaded_at": DOWNLOADED.isoformat()}

    monthly_ff6 = _with_mom(monthly, 0.03)
    daily_ff6 = _with_mom(factors, 0.007)

    def load_monthly(**_kwargs: object) -> pd.DataFrame:
        return monthly

    def load_monthly_ff6(frequency: str, **_kwargs: object) -> pd.DataFrame:
        return monthly_ff6

    # The upload route never reaches the network.
    routes_upload.load_ff5_monthly = load_monthly
    routes_upload.load_ff6 = load_monthly_ff6
    deps = AppDeps(
        price_provider=FakeProvider(d.history),
        load_factors=lambda refresh, at: factors,
        factor_status=lambda at: status,
        now=lambda: now,
        data_dir=data_dir,
        static_dir=FRONTEND_DIST,
        load_ff6=lambda at: daily_ff6,
    )
    return create_app(deps)


def _with_mom(frame: pd.DataFrame, sd: float) -> pd.DataFrame:
    """``frame`` plus a synthetic momentum column ``Mom`` (fixed seed), attrs kept."""
    out = frame.copy()
    out["Mom"] = np.random.default_rng(TEST_NUMBER + 1).normal(0.0, sd, size=len(frame))
    out.attrs = dict(frame.attrs)
    return out
