"""Holdings section: what each holding, group, cash and trading cost did for a portfolio.

``HoldingsSection`` is the optional ``FactorReport.holdings`` field. Like ``portfolio_backtest``,
it is written only for a portfolio subject (``POST /api/report/portfolio``) and left out of the
JSON when ``None``, so a ticker or upload report is byte-identical to one written before it
existed.

The window is the analysed window of the report: the first and last day of the analysis sample,
the days the factor regression uses. It can be shorter than the backtest (a range preset, the end
of the factor file). Over that window:

* ``target_weight`` is the weight the portfolio rebalances to;
* ``end_weight`` is the weight on the last day, after drift and before any rebalance that day;
* ``contribution`` is the Frongello-linked contribution to the portfolio's net return
  (``analytics.portfolio_attribution``); the rows with no parent add up to ``total_return``;
* ``risk_share`` is the ex-post share of the portfolio's variance,
  ``Cov(contribution_i, portfolio) / Var(portfolio)``, on daily returns. A share can be negative.
  The rows with no parent add up to 1.

Rows are in tree order, a group before its members. An asset class has ``depth`` 0, a sub-asset
class 1 and a holding 2; ``parent_id`` names the group that contains a row. A group row is the sum
of its members (``roll_up``). Cash and trading cost are rows of their own at depth 0 with no
parent; cash holds every USD cash instrument and the unallocated weight, as in the backtest.
"""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import Field, model_validator

from factordesk.report.base import FrozenModel, SectionModel, SectionSpec

HoldingKind = Literal["group", "holding", "cash", "cost"]


class HoldingRow(FrozenModel):
    """One line of the holdings table."""

    id: str = Field(
        description="Unique in the section. A holding is i:<tree id>, a group g:<tree id>; cash "
        "and trading cost are cash and cost."
    )
    kind: HoldingKind
    label: str = Field(description="Display name of the holding, group, cash or cost line.")
    ticker: str | None = Field(description="Yahoo ticker of a holding; None for every other row.")
    depth: int = Field(
        ge=0, le=2, description="0 asset class, cash or cost; 1 sub-asset class; 2 holding."
    )
    parent_id: str | None = Field(
        description="Id of the group that contains the row; None at depth 0."
    )
    target_weight: float | None = Field(
        description="Weight the portfolio rebalances to; None for the trading cost row."
    )
    end_weight: float | None = Field(
        description="Weight on the last day of the window, after drift; None for the cost row."
    )
    contribution: float = Field(
        description="Frongello-linked contribution to the portfolio's net return over the "
        "window, as a decimal fraction (negative for the cost row)."
    )
    risk_share: float | None = Field(
        description="Ex-post share of the portfolio's variance; None when the section's "
        "risk_share_reason says it is not defined."
    )


class HoldingsSection(SectionModel):
    """The holdings table of a portfolio report. Status is always ``ok`` when it exists."""

    window_start: date = Field(description="First day of the analysed window.")
    window_end: date = Field(description="Last day of the analysed window.")
    n_days: int = Field(ge=1, description="Daily portfolio returns in the window.")
    total_return: float = Field(
        description="Net compounded return of the portfolio over the window; the contributions "
        "of the rows with no parent add up to it."
    )
    risk_share_reason: str | None = Field(
        description="Plain-words reason when no risk share is defined; None when they are."
    )
    rows: list[HoldingRow] = Field(description="Table rows in tree order, then cash, then cost.")

    @model_validator(mode="after")
    def _consistent(self) -> HoldingsSection:
        if self.window_start > self.window_end:
            raise ValueError("window_start is after window_end")
        known: set[str] = set()
        for row in self.rows:
            if row.id in known:
                raise ValueError(f"row id {row.id!r} is used twice")
            if (row.parent_id is None) != (row.depth == 0):
                raise ValueError(f"row {row.id!r}: parent_id is None exactly at depth 0")
            if row.parent_id is not None and row.parent_id not in known:
                raise ValueError(f"row {row.id!r}: its parent must come first in the list")
            known.add(row.id)
        if (self.risk_share_reason is None) != all(row.risk_share is not None for row in self.rows):
            raise ValueError("risk_share_reason is None exactly when every row has a risk share")
        return self


HOLDINGS_SECTION = SectionSpec(report_field="holdings", model=HoldingsSection)
