"""The report of a portfolio tree: flatten, fetch, backtest, analyse (spec S2-3 and S2-5).

``plan_of`` turns a validated ``PortfolioTree`` into a ``PortfolioPlan``: the instruments with a
weight above 0 (a template row at 0% never reaches the price fetch or the backtest, so it cannot
limit the window), the tickers to fetch (a ticker used on two lines is fetched once and its leaves
stay separate), and the SHA-256 of the canonical tree JSON that keys the in-memory cache.
``build_portfolio_report`` runs the backtest and the report engine on the fetched histories and is
blocking (run it in a worker). Every refusal is an ``ApiException`` with HTTP 422.

Nothing here is written to disk, and nothing logs a portfolio name, label or weight.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from typing import cast

import numpy as np
import pandas as pd

from factordesk.analytics.backtest import CASH_ID, WEIGHT_TOLERANCE, BacktestResult, run_backtest
from factordesk.analytics.sample import DegenerateInputError, InsufficientHistoryError
from factordesk.analytics.subject import LEVEL_BASE, ReturnSubject
from factordesk.api import ranges
from factordesk.api.errors import ApiException, one_line, to_api_exception
from factordesk.api.portfolio_models import PortfolioTree, load_library
from factordesk.data.prices import (
    BatchPriceProvider,
    PriceDataError,
    PriceFailure,
    PriceHistory,
    PriceProvider,
    validate_ticker,
)
from factordesk.report.schema import FactorModel, FactorReport, RangePreset
from factordesk.section_hooks.context import PortfolioBacktestInput, SectionInputs

CASH_LABEL = "USD cash (risk-free rate)"
RF_COLUMN = "RF"
LEAF_PREFIX = "i:"
"""Backtest leaf ids are ``i:<instrument id>``, so no instrument id can clash with ``CASH_ID``."""
PRICE_SOURCE = "Yahoo adjusted close"


@dataclass(frozen=True)
class PlanRow:
    """One instrument with a weight above 0, in tree order."""

    key: str | None
    """Backtest leaf id; ``None`` for a USD cash instrument (it goes to the cash leaf)."""
    name: str
    ticker: str | None
    weight: float

    @property
    def label(self) -> str:
        return self.name if self.ticker is None else f"{self.name} ({self.ticker})"


@dataclass(frozen=True)
class PortfolioPlan:
    name: str
    cost_bps: float
    rows: tuple[PlanRow, ...]
    unallocated: float
    tickers: tuple[str, ...]
    """The distinct tickers to fetch, upper case, in first-use order."""
    digest: str
    """SHA-256 of the canonical tree JSON (the cache key)."""

    @property
    def holdings(self) -> tuple[PlanRow, ...]:
        return tuple(row for row in self.rows if row.key is not None)


def _invalid(message: str, action: str) -> ApiException:
    return ApiException("invalid_portfolio", message, action)


def canonical_digest(tree: PortfolioTree) -> str:
    """SHA-256 (hex) of the tree as canonical JSON: sorted keys, no spaces."""
    text = json.dumps(tree.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def plan_of(tree: PortfolioTree) -> PortfolioPlan:
    """Flatten the tree to the instruments that take part in the backtest.

    Refuses (422) a library line that does not exist and a portfolio with no holding above 0.
    The size, the total and the proxy rules are the tree model's own validation.
    """
    lines = {line.id for line in load_library().lines}
    rows: list[PlanRow] = []
    tickers: list[str] = []
    for ac in tree.root.children:
        for sub in ac.children:
            if sub.library_id not in lines:
                raise _invalid(
                    f"The line {sub.label!r} is not in the Asset Class Library.",
                    "Add the line from the library picker.",
                )
            for item in sub.children:
                if item.weight <= 0.0:
                    continue
                if item.kind == "cash" or item.ticker is None:
                    rows.append(PlanRow(None, item.label, None, item.weight))
                    continue
                ticker = validate_ticker(item.ticker)
                if ticker not in tickers:
                    tickers.append(ticker)
                rows.append(PlanRow(LEAF_PREFIX + item.id, item.label, ticker, item.weight))
    if not any(row.key is not None for row in rows):
        raise _invalid(
            "The portfolio holds no instrument with a ticker and a weight above 0.",
            "Give at least one instrument a weight above 0. USD cash alone is not a backtest.",
        )
    return PortfolioPlan(
        name=tree.name,
        cost_bps=tree.cost_bps,
        rows=tuple(rows),
        unallocated=tree.remainder,
        tickers=tuple(tickers),
        digest=canonical_digest(tree),
    )


# ------------------------------------------------------------------------------------ prices
def _failure_refusal(failures: Sequence[PriceFailure]) -> ApiException:
    missing = [f.ticker for f in failures if f.reason in ("invalid_ticker", "no_data")]
    if missing:
        who = ", ".join(missing)
        return ApiException(
            "unknown_ticker",
            f"No prices were returned for {who}.",
            "Check the ticker symbols, or choose another instrument for that line.",
            status=422,
        )
    first = failures[0]
    if first.reason == "network":
        return ApiException(
            "network",
            "factordesk could not reach Yahoo Finance for the prices.",
            "Check your network connection, then try again.",
        )
    if first.reason in ("rate_limited", "skipped_rate_limited"):
        return ApiException(
            "upstream_refused",
            "Yahoo Finance refused the request.",
            "Wait a minute, then try again.",
        )
    return ApiException(
        "internal",
        f"The prices could not be fetched: {one_line(first.message)}.",
        "Try again. If it happens again, report it with this page's address.",
    )


def fetch_histories(provider: PriceProvider, tickers: Sequence[str]) -> dict[str, PriceHistory]:
    """The price history of every ticker (blocking), through ``fetch_many`` when the provider
    has it. A ticker with no usable data is a 422 naming it; a rate limit or a network failure is
    a 503."""
    if callable(getattr(provider, "fetch_many", None)):
        result = cast(BatchPriceProvider, provider).fetch_many(list(tickers))
        histories: dict[str, PriceHistory] = dict(result.histories)
        failures: list[PriceFailure] = list(result.failures)
    else:  # a provider without batch download (a test fake)
        histories = {}
        failures = []
        for ticker in tickers:
            try:
                histories[ticker] = provider.fetch(ticker)
            except PriceDataError as exc:
                failures.append(PriceFailure(ticker, "no_data", str(exc)))
    if failures:
        raise _failure_refusal(failures)
    return histories


# ----------------------------------------------------------------------------------- backtest
def _leaf_frame(plan: PortfolioPlan, histories: dict[str, PriceHistory]) -> pd.DataFrame:
    from factordesk.pipeline import unique_dates

    returns: dict[str, pd.Series] = {}
    for row in plan.holdings:
        assert row.key is not None and row.ticker is not None
        returns[row.key] = unique_dates(histories[row.ticker]).total_returns.rename(row.key)
    frame = pd.DataFrame(returns)
    frame.index = pd.DatetimeIndex(frame.index, name="date")
    return frame


def _labels(plan: PortfolioPlan) -> dict[str, str]:
    labels = {row.key: row.label for row in plan.holdings if row.key is not None}
    labels[CASH_ID] = CASH_LABEL
    return labels


def _day(value: object) -> date:
    return pd.Timestamp(cast(str, value)).date()


def _window_refusal(
    exc: ValueError,
    frame: pd.DataFrame,
    cash_span: tuple[date, date] | None,
    labels: dict[str, str],
) -> ApiException:
    """The 422 for a backtest that cannot run: no common period, or a hole inside it."""
    text = str(exc)
    if "share no common date" in text:
        firsts: dict[str, date] = {}
        lasts: dict[str, date] = {}
        for key in frame.columns:
            seen = frame[key].dropna().index
            if len(seen):
                firsts[str(key)], lasts[str(key)] = _day(seen[0]), _day(seen[-1])
        if cash_span is not None:
            firsts[CASH_ID], lasts[CASH_ID] = cash_span
        late = max(firsts, key=lambda k: firsts[k])
        early = min(lasts, key=lambda k: lasts[k])
        return _invalid(
            f"The instruments share no trading period: {labels[late]} starts on "
            f"{firsts[late]:%d %b %Y}, after {labels[early]} ends on {lasts[early]:%d %b %Y}.",
            "Remove an instrument with a short history, or choose proxies that cover the same "
            "years.",
        )
    for key, label in labels.items():
        text = text.replace(repr(key), label)
    return _invalid(
        f"The backtest cannot run: {one_line(text)}.",
        "Remove the instrument named, or choose another proxy for it.",
    )


def _plural(n: int) -> str:
    return f"{n} instrument" if n == 1 else f"{n} instruments"


def _summary(
    plan: PortfolioPlan, bt: BacktestResult, labels: dict[str, str]
) -> PortfolioBacktestInput:
    days = pd.DatetimeIndex(bt.rebalance_dates)
    on_rebalance = bt.turnover[bt.turnover.index.isin(days)]
    average = float(on_rebalance.mean()) if len(days) else 0.0
    return PortfolioBacktestInput(
        window_start=bt.start,
        window_end=bt.end,
        start_limited_by=tuple(labels[k] for k in bt.start_leaves),
        end_limited_by=tuple(labels[k] for k in bt.end_leaves),
        n_instruments=len(plan.rows),
        n_rebalances=len(bt.rebalance_dates),
        cost_bps=bt.cost_bps,
        total_cost=float(bt.cost.sum()),
        average_turnover=average,
        unallocated_weight=plan.unallocated,
        survivorship_note=bt.survivorship_note,
        weights=tuple((row.name, row.ticker, row.weight) for row in plan.rows),
    )


def _subject(
    plan: PortfolioPlan, bt: BacktestResult, leaf_index: pd.DatetimeIndex
) -> ReturnSubject:
    """The daily portfolio subject: net returns on the backtest window.

    The calendar's origin is the last date before the window in the leaves' own calendar (or the
    business day before when there is none); the level index is growth of 100 from it.
    """
    index = pd.DatetimeIndex(bt.ret.index)
    pos = int(leaf_index.searchsorted(index[0]))
    origin = (
        pd.Timestamp(leaf_index[pos - 1]) if pos > 0 else index[0] - pd.offsets.BDay(1)
    ).normalize()
    calendar = pd.DatetimeIndex([origin, *index], name="date")
    values = bt.ret.to_numpy(dtype=np.float64)
    levels = pd.Series(
        LEVEL_BASE * np.concatenate([[1.0], np.cumprod(1.0 + values)]),
        index=calendar,
        name=plan.name,
    )
    return ReturnSubject(
        kind="portfolio",
        label=plan.name,
        frequency="daily",
        returns=pd.Series(values, index=index, name=plan.name),
        calendar=calendar,
        levels=levels,
        source=f"backtest of {_plural(len(plan.rows))} ({PRICE_SOURCE})",
        currency="USD",
    )


def backtest_portfolio(
    plan: PortfolioPlan, histories: dict[str, PriceHistory], rf: pd.Series
) -> tuple[ReturnSubject, PortfolioBacktestInput]:
    """Run the backtest of the plan and build its subject and summary (pure; blocking).

    ``rf`` is the daily risk-free rate in decimals (the French ``RF`` column). The backtest runs
    on the whole common window of the instruments with a weight above 0; USD cash, at ``rf``,
    joins it only when some weight is held there. A refusal is an ``ApiException`` (422).
    """
    frame = _leaf_frame(plan, histories)
    weights = {row.key: row.weight for row in plan.holdings if row.key is not None}
    labels = _labels(plan)
    try:
        bt = run_backtest(frame, weights, rf, plan.cost_bps)
    except ValueError as exc:
        cash_held = sum(weights.values()) < 1.0 - WEIGHT_TOLERANCE
        seen = rf.dropna().index
        span = (_day(seen[0]), _day(seen[-1])) if cash_held and len(seen) else None
        raise _window_refusal(exc, frame, span, labels) from exc
    return _subject(plan, bt, pd.DatetimeIndex(frame.index)), _summary(plan, bt, labels)


def build_portfolio_report(
    plan: PortfolioPlan,
    histories: dict[str, PriceHistory],
    factor_frame: pd.DataFrame,
    model: FactorModel,
    *,
    now: datetime,
    factors_downloaded_at: datetime | None,
    preset: RangePreset | None,
    start: date | None,
    end: date | None,
    inputs: SectionInputs | None,
) -> FactorReport:
    """Backtest the plan and analyse the net daily returns (blocking; run in a worker).

    The range cuts the analysis sample, as for a ticker; the backtest itself always runs on the
    whole common window.
    """
    from factordesk.pipeline import assemble_subject_report

    if RF_COLUMN not in factor_frame.columns:
        raise ValueError("the factor frame has no RF column for the USD cash leaf")
    subject, summary = backtest_portfolio(plan, histories, factor_frame[RF_COLUMN])
    cov = ranges.Coverage(
        first_return_date=summary.window_start,
        last_price_date=summary.window_end,
        factors_last_date=_day(factor_frame.index[-1]),
    )
    first_day, last_day = ranges.resolve(preset, start, end, cov)
    section_inputs = dataclasses.replace(inputs or SectionInputs(), portfolio_backtest=summary)
    try:
        return assemble_subject_report(
            subject,
            factor_frame,
            model,
            now=now,
            factors_downloaded_at=factors_downloaded_at,
            start=first_day,
            end=last_day,
            section_inputs=section_inputs,
        )
    except InsufficientHistoryError as exc:
        raise to_api_exception(exc, subject.label) from exc
    except DegenerateInputError as exc:
        raise ApiException(
            "degenerate_input",
            f"Cannot analyse {subject.label}: {one_line(exc.reason)}.",
            "Check that the portfolio does not sit entirely in USD cash.",
        ) from exc
