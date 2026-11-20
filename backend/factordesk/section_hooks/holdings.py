"""Pipeline hook of the HoldingsSection (sprint 3, S3-10).

Reads ``ctx.inputs.portfolio_backtest.holdings``, which ``api.portfolio_report`` fills from the
backtest result and the tree. It attributes the backtest over the analysed window of the report
(the exact days of the analysis sample, as the factor regression sees it: a day the sample left
out does not count) and rolls the
leaves up through the tree. Returns ``None`` (the section is hidden) when there is no such input,
so a subject that is not a backtested portfolio never gets one.
"""

from __future__ import annotations

from collections.abc import Mapping

import pandas as pd

from factordesk.analytics.backtest import CASH_ID
from factordesk.analytics.portfolio_attribution import COST_ID, GroupPath, attribute, roll_up
from factordesk.report.sections.holdings import HoldingKind, HoldingRow, HoldingsSection
from factordesk.section_hooks.context import SectionContext

CASH_LABEL = "USD cash"
COST_LABEL = "Trading cost"


def _row(
    row_id: str,
    kind: HoldingKind,
    label: str,
    *,
    depth: int,
    parent_id: str | None,
    contribution: float,
    risk_share: float | None,
    target_weight: float | None = None,
    end_weight: float | None = None,
    ticker: str | None = None,
) -> HoldingRow:
    return HoldingRow(
        id=row_id,
        kind=kind,
        label=label,
        ticker=ticker,
        depth=depth,
        parent_id=parent_id,
        target_weight=target_weight,
        end_weight=end_weight,
        contribution=contribution,
        risk_share=risk_share,
    )


def build_holdings(ctx: SectionContext) -> HoldingsSection | None:
    """The holdings table of a portfolio subject, or ``None`` without a backtest input."""
    info = ctx.inputs.portfolio_backtest
    if info is None or info.holdings is None:
        return None
    bt, nodes = info.holdings.backtest, info.holdings.nodes
    start, end = ctx.sample.start, ctx.sample.end
    att = attribute(bt, days=pd.DatetimeIndex(ctx.sample.ret.index))

    # Every backtest leaf has a path: a holding sits under its groups, cash under the whole
    # portfolio only (the backtest has one cash leaf).
    paths: dict[str, GroupPath] = {n.id: n.path for n in nodes if n.kind == "holding"}
    paths[CASH_ID] = ()
    last = bt.drifted_weights.loc[: pd.Timestamp(end)].iloc[-1]

    def totals(values: Mapping[str, float]) -> Mapping[GroupPath, float]:
        return roll_up({k: values[k] for k in paths}, paths).totals

    contribution = totals(att.contribution)
    target = totals(bt.target_weights)
    ending = totals({k: float(last[k]) for k in paths})
    share = att.risk_share
    risk = None if share is None else totals(share)

    def leaf_share(row_id: str) -> float | None:
        return None if share is None else share[row_id]

    rows: list[HoldingRow] = []
    for node in nodes:
        if node.kind == "group":
            rows.append(
                _row(
                    node.id,
                    "group",
                    node.label,
                    depth=node.depth,
                    parent_id=node.parent_id,
                    target_weight=target[node.path],
                    end_weight=ending[node.path],
                    contribution=contribution[node.path],
                    risk_share=None if risk is None else risk[node.path],
                )
            )
        else:
            rows.append(
                _row(
                    node.id,
                    "holding",
                    node.label,
                    depth=node.depth,
                    parent_id=node.parent_id,
                    ticker=node.ticker,
                    target_weight=bt.target_weights[node.id],
                    end_weight=float(last[node.id]),
                    contribution=att.contribution[node.id],
                    risk_share=leaf_share(node.id),
                )
            )
    rows.append(
        _row(
            CASH_ID,
            "cash",
            CASH_LABEL,
            depth=0,
            parent_id=None,
            target_weight=bt.target_weights[CASH_ID],
            end_weight=float(last[CASH_ID]),
            contribution=att.contribution[CASH_ID],
            risk_share=leaf_share(CASH_ID),
        )
    )
    rows.append(
        _row(
            COST_ID,
            "cost",
            COST_LABEL,
            depth=0,
            parent_id=None,
            contribution=att.contribution[COST_ID],
            risk_share=leaf_share(COST_ID),
        )
    )
    return HoldingsSection(
        status="ok",
        reason=None,
        sample=ctx.sample_info(None),
        window_start=start,
        window_end=end,
        n_days=len(att.daily_contribution),
        total_return=att.total_return,
        risk_share_reason=att.risk_share_reason,
        rows=rows,
    )
