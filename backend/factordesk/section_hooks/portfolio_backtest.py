"""Pipeline hook of the PortfolioBacktestSection (spec S2-5).

Reads ``ctx.inputs.portfolio_backtest``, which ``api.portfolio_report`` fills from the backtest
result, and turns it into the section. Returns ``None`` (the section is hidden) when there is no
such input, so a subject that is not a backtested portfolio never gets one. Never raises.
"""

from __future__ import annotations

from factordesk.report.sections.portfolio_backtest import (
    PortfolioBacktestSection,
    TargetWeightRow,
)
from factordesk.section_hooks.context import SectionContext


def _data_note(n_dropped: int) -> str | None:
    if n_dropped == 0:
        return None
    days = "day" if n_dropped == 1 else "days"
    return (
        f"{n_dropped} trading {days} without a price for every instrument were skipped; the "
        "return of each instrument over a gap is compounded into the next day all of them have."
    )


def build_portfolio_backtest(ctx: SectionContext) -> PortfolioBacktestSection | None:
    """The backtest summary of a portfolio subject, or ``None`` without a backtest input."""
    info = ctx.inputs.portfolio_backtest
    if info is None:
        return None
    return PortfolioBacktestSection(
        status="ok",
        reason=None,
        sample=ctx.sample_info(None),
        window_start=info.window_start,
        window_end=info.window_end,
        start_limited_by=list(info.start_limited_by),
        end_limited_by=list(info.end_limited_by),
        n_instruments=info.n_instruments,
        n_rebalances=info.n_rebalances,
        n_dates_dropped=info.n_dates_dropped,
        data_note=_data_note(info.n_dates_dropped),
        cost_bps=info.cost_bps,
        total_cost=info.total_cost,
        average_turnover=info.average_turnover,
        unallocated_weight=info.unallocated_weight,
        unallocated_currency="EUR" if info.unallocated_currency == "EUR" else None,
        survivorship_note=info.survivorship_note,
        weights=[
            TargetWeightRow(label=label, ticker=ticker, weight=weight)
            for label, ticker, weight in info.weights
        ],
    )
