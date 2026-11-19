"""Portfolio backtest section: how the portfolio's return series was made (spec S2-5).

``PortfolioBacktestSection`` is the optional ``FactorReport.portfolio_backtest`` field. It is
written only for a portfolio subject (``POST /api/report/portfolio``) and left out of the JSON
when ``None``, so a ticker or upload report is byte-identical to one written before it existed.

It describes the backtest, not a regression: the window it ran on, the instruments that limit
that window, the rebalances, what trading cost, the survivorship warning and the target weights.
The factor regression of the report runs on the portfolio's net daily returns over the part of
this window the factor data and the requested range cover (see ``sample``).

Weights are decimal fractions. ``weights`` lists every instrument with a target above 0, as the
user entered it; with ``unallocated_weight`` (held in USD cash) they add up to 1. The section has
no footnote keys of its own and no nested ``StatisticModel``.
"""

from __future__ import annotations

from datetime import date

from pydantic import Field, model_validator

from factordesk.report.base import FrozenModel, SectionModel, SectionSpec


class TargetWeightRow(FrozenModel):
    """One instrument and its target weight."""

    label: str = Field(description="Display name of the instrument (a sub-asset class line).")
    ticker: str | None = Field(description="Yahoo ticker; None for a USD cash instrument.")
    weight: float = Field(gt=0.0, le=1.0, description="Target weight as a decimal fraction.")


class PortfolioBacktestSection(SectionModel):
    """The backtest behind a portfolio report. Status is always ``ok`` when the section exists."""

    window_start: date = Field(description="First day with a portfolio return.")
    window_end: date = Field(description="Last day with a portfolio return.")
    start_limited_by: list[str] = Field(
        description="Instruments whose history starts latest and so set the window start "
        "(several on a tie)."
    )
    end_limited_by: list[str] = Field(
        description="Instruments whose history ends earliest and so set the window end. USD cash "
        "ends with the factor file, so it can set the end."
    )
    n_instruments: int = Field(ge=1, description="Instruments with a target weight above 0.")
    n_rebalances: int = Field(
        ge=0, description="Month-end closes at which the weights were reset to target."
    )
    cost_bps: float = Field(ge=0.0, description="Cost per unit of turnover, basis points.")
    total_cost: float = Field(
        ge=0.0,
        description="Sum over the window of the cost paid at each rebalance, as a fraction of "
        "the portfolio value at that close.",
    )
    average_turnover: float = Field(
        ge=0.0,
        description="Mean one-way turnover of a rebalance, as a fraction of the portfolio; 0 "
        "when there was no rebalance.",
    )
    unallocated_weight: float = Field(
        ge=0.0, le=1.0, description="Weight left over by the targets; held in USD cash."
    )
    survivorship_note: str = Field(description="Fixed warning carried by every backtest.")
    weights: list[TargetWeightRow] = Field(description="Target weights, in tree order.")

    @model_validator(mode="after")
    def _window_ordered(self) -> PortfolioBacktestSection:
        if self.window_start > self.window_end:
            raise ValueError("window_start is after window_end")
        return self


PORTFOLIO_BACKTEST_SECTION = SectionSpec(
    report_field="portfolio_backtest", model=PortfolioBacktestSection
)
