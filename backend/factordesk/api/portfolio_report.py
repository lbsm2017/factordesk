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
from factordesk.section_hooks.context import (
    HoldingsInput,
    HoldingsNode,
    PortfolioBacktestInput,
    SectionInputs,
)

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
    groups: tuple[tuple[str, str], ...] = ()
    """``(id, label)`` of the asset class and the sub-asset class that hold the instrument."""

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
            groups = ((ac.id, ac.label), (sub.id, sub.label))
            for item in sub.children:
                if item.weight <= 0.0:
                    continue
                if item.kind == "cash" or item.ticker is None:
                    rows.append(PlanRow(None, item.label, None, item.weight, groups))
                    continue
                try:
                    ticker = validate_ticker(item.ticker)
                except PriceDataError as exc:
                    raise _invalid(
                        f"{item.ticker!r} is not a valid ticker.",
                        "Use 1 to 12 letters, digits or . ^ = - (for example SPY or BRK-B); a "
                        "ticker cannot start with a dot.",
                    ) from exc
                if ticker not in tickers:
                    tickers.append(ticker)
                rows.append(PlanRow(LEAF_PREFIX + item.id, item.label, ticker, item.weight, groups))
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
@dataclass(frozen=True)
class CommonReturns:
    """The backtest inputs built on the common calendar of the weighted instruments."""

    leaf_ret: pd.DataFrame
    """One column per leaf: the simple return between consecutive common dates."""
    rf: pd.Series
    """The risk-free rate compounded over the same intervals; NaN where the factor file ends."""
    calendar: pd.DatetimeIndex
    """The common price dates, the origin first."""
    n_dropped: int
    """Dates inside the common span on which at least one instrument had no price."""
    start_keys: tuple[str, ...]
    """Leaves whose first price is the latest: they set the start of the common calendar."""
    end_keys: tuple[str, ...]
    """Leaves whose last price is the earliest: they set the end of the common calendar."""


def _adjusted_close(history: PriceHistory) -> pd.Series:
    """Adjusted close with one row per date; a missing or non-positive price is left out."""
    from factordesk.pipeline import unique_dates

    adj = unique_dates(history).frame["adj_close"].astype("float64")
    return adj[adj > 0].dropna()


def _compounded_rf(rf: pd.Series, calendar: pd.DatetimeIndex) -> pd.Series:
    """``prod(1 + rf)`` over each ``(calendar[i-1], calendar[i]]`` minus 1, indexed by
    ``calendar[1:]``. NaN when the interval ends past the last or before the first ``rf`` date,
    so cash ends the window where the factor file ends."""
    clean = rf.dropna()
    if clean.empty:
        return pd.Series(np.nan, index=calendar[1:], name="rf")
    level = (1.0 + clean).cumprod()
    pos = np.asarray(level.index.searchsorted(calendar, side="right")) - 1
    values = np.where(pos >= 0, level.to_numpy()[np.maximum(pos, 0)], 1.0)
    ratio = values[1:] / values[:-1] - 1.0
    outside = (calendar[1:] > level.index[-1]) | (calendar[1:] < level.index[0])
    ratio[np.asarray(outside)] = np.nan
    return pd.Series(ratio, index=calendar[1:], name="rf")


def _common_returns(
    plan: PortfolioPlan, histories: dict[str, PriceHistory], rf: pd.Series
) -> CommonReturns:
    """Returns of every weighted leaf between consecutive dates all of them have a price on.

    A day on which one instrument has no price is skipped for all of them, so that instrument's
    return over the gap is compounded into the next common day (adjusted close over adjusted
    close, not a sum of daily returns). Raises ``ApiException`` (422) when the instruments share
    fewer than two price dates.
    """
    prices: dict[str, pd.Series] = {}
    for row in plan.holdings:
        assert row.key is not None and row.ticker is not None
        prices[row.key] = _adjusted_close(histories[row.ticker])
    labels = _labels(plan)
    common: pd.DatetimeIndex | None = None
    for series in prices.values():
        idx = pd.DatetimeIndex(series.index)
        common = idx if common is None else common.intersection(idx)
    assert common is not None
    common = pd.DatetimeIndex(common.sort_values(), name="date")
    if len(common) < 2:
        raise _no_common_period(prices, labels)
    span = (common[0], common[-1])
    union = common
    for series in prices.values():
        union = union.union(pd.DatetimeIndex(series.index))
    in_span = int(((union >= span[0]) & (union <= span[1])).sum())
    frame = pd.DataFrame(
        {key: series.loc[common].pct_change().iloc[1:] for key, series in prices.items()}
    )
    frame.index = pd.DatetimeIndex(frame.index, name="date")
    first = {k: s.index[0] for k, s in prices.items()}
    last = {k: s.index[-1] for k, s in prices.items()}
    return CommonReturns(
        start_keys=tuple(k for k in prices if first[k] == max(first.values())),
        end_keys=tuple(k for k in prices if last[k] == min(last.values())),
        leaf_ret=frame,
        rf=_compounded_rf(rf, common),
        calendar=common,
        n_dropped=in_span - len(common),
    )


def _no_common_period(prices: dict[str, pd.Series], labels: dict[str, str]) -> ApiException:
    firsts = {k: _day(s.index[0]) for k, s in prices.items()}
    lasts = {k: _day(s.index[-1]) for k, s in prices.items()}
    late = max(firsts, key=lambda k: firsts[k])
    early = min(lasts, key=lambda k: lasts[k])
    if firsts[late] > lasts[early]:
        return _invalid(
            f"The instruments share no trading period: {labels[late]} starts on "
            f"{firsts[late]:%d %b %Y}, after {labels[early]} ends on {lasts[early]:%d %b %Y}.",
            "Remove an instrument with a short history, or choose proxies that cover the same "
            "years.",
        )
    return _invalid(
        "The instruments share fewer than two trading days with a price for every one of them.",
        "Remove an instrument with a short history, or choose proxies that cover the same years.",
    )


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


def _limiting(
    keys: tuple[str, ...],
    bt_keys: tuple[str, ...],
    bt_edge: date,
    own_edge: date,
    labels: dict[str, str],
) -> tuple[str, ...]:
    """Display names of what limits one edge of the window.

    ``keys`` are the instruments that limit the common price calendar, ``bt_keys`` the backtest's
    own answer, which adds USD cash (its risk-free rate ends with the factor file). Cash alone
    limits an edge when the window is cut inside the common calendar.
    """
    if CASH_ID not in bt_keys:
        return tuple(labels[k] for k in keys)
    if bt_edge != own_edge:
        return (labels[CASH_ID],)
    return (*(labels[k] for k in keys), labels[CASH_ID])


GROUP_PREFIX = "g:"
"""Group ids of the holdings table are ``g:<tree id>``, so they cannot clash with a leaf id."""


def _holdings_nodes(plan: PortfolioPlan) -> tuple[HoldingsNode, ...]:
    """The groups and holdings of the backtest in tree order, each group before its members.

    Rows are in tree order already, so a group is listed when its first member appears. A group
    that holds only cash instruments, or nothing above 0, is not listed.
    """
    nodes: list[HoldingsNode] = []
    listed: set[str] = set()
    for row in plan.holdings:
        assert row.key is not None
        path: tuple[str, ...] = ()
        for depth, (group_id, label) in enumerate(row.groups):
            parent = path[-1] if path else None
            path = (*path, GROUP_PREFIX + group_id)
            if path[-1] not in listed:
                listed.add(path[-1])
                nodes.append(HoldingsNode(path[-1], "group", label, None, parent, depth, path))
        assert path, "an instrument sits in at least one group"
        nodes.append(
            HoldingsNode(row.key, "holding", row.name, row.ticker, path[-1], len(path), path)
        )
    return tuple(nodes)


def _summary(
    plan: PortfolioPlan, bt: BacktestResult, common: CommonReturns, labels: dict[str, str]
) -> PortfolioBacktestInput:
    days = pd.DatetimeIndex(bt.rebalance_dates)
    on_rebalance = bt.turnover[bt.turnover.index.isin(days)]
    average = float(on_rebalance.mean()) if len(days) else 0.0
    return PortfolioBacktestInput(
        window_start=bt.start,
        window_end=bt.end,
        start_limited_by=_limiting(
            common.start_keys,
            bt.start_leaves,
            bt.start,
            _day(common.leaf_ret.index[0]),
            labels,
        ),
        end_limited_by=_limiting(
            common.end_keys, bt.end_leaves, bt.end, _day(common.leaf_ret.index[-1]), labels
        ),
        n_dates_dropped=common.n_dropped,
        n_instruments=len(plan.rows),
        n_rebalances=len(bt.rebalance_dates),
        cost_bps=bt.cost_bps,
        total_cost=float(bt.cost.sum()),
        average_turnover=average,
        unallocated_weight=plan.unallocated,
        survivorship_note=bt.survivorship_note,
        weights=tuple((row.name, row.ticker, row.weight) for row in plan.rows),
        holdings=HoldingsInput(bt, _holdings_nodes(plan)),
    )


def _subject(plan: PortfolioPlan, bt: BacktestResult, common: pd.DatetimeIndex) -> ReturnSubject:
    """The daily portfolio subject: net returns on the backtest window.

    The calendar's origin is the last common price date before the window; the level index is
    growth of 100 from it.
    """
    index = pd.DatetimeIndex(bt.ret.index)
    origin = pd.Timestamp(common[int(common.searchsorted(index[0])) - 1]).normalize()
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
    common = _common_returns(plan, histories, rf)
    frame = common.leaf_ret
    weights = {row.key: row.weight for row in plan.holdings if row.key is not None}
    labels = _labels(plan)
    try:
        bt = run_backtest(frame, weights, common.rf, plan.cost_bps)
    except ValueError as exc:
        cash_held = sum(weights.values()) < 1.0 - WEIGHT_TOLERANCE
        seen = rf.dropna().index
        span = (_day(seen[0]), _day(seen[-1])) if cash_held and len(seen) else None
        raise _window_refusal(exc, frame, span, labels) from exc
    return _subject(plan, bt, common.calendar), _summary(plan, bt, common, labels)


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
