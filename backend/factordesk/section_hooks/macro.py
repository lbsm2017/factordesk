"""Pipeline hook of the macro section (epic E4): rates, credit, commodity, inflation and dollar
sensitivities in a separate regression (``analytics/macro.py``).

``load_macro_input`` fetches the five fund histories through the provider the pipeline uses (the
same incremental refresh and cache as the world beta proxies) and the Fed broad dollar index
through ``data.fred`` (cached per day). It never raises: a fund that cannot be fetched becomes a
``WorldBenchmarkInput`` with a reason, and a dollar index that cannot be fetched becomes a
``DollarInput`` with a reason. ``build_macro`` reads the context and that input and nothing else.
It returns ``None`` only when the feature did not run (no macro input). A missing dollar index
gives a section without the dollar row and the note "dollar index unavailable"; a missing fund,
too few rows or a singular design gives ``insufficient_data`` or ``failed`` with a reason. The
hook never raises for data reasons, never changes a core section and never blocks the report
(CODING_STANDARDS section 8).
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from pathlib import Path

import pandas as pd

from factordesk.analytics.currency import EuroLegs
from factordesk.analytics.macro import (
    EUR_USD_LAG_NOTE,
    LEG_TICKERS,
    USD_LAG_NOTE,
    MacroFit,
    TooFewRowsError,
    factors_of,
    run_macro,
)
from factordesk.analytics.sample import DegenerateInputError
from factordesk.data.fred import DOLLAR_SERIES, FredError, load_fred_series
from factordesk.data.prices import PriceProvider, collapse_duplicate_dates
from factordesk.report.base import SampleInfo, Status
from factordesk.report.sections.macro import (
    EUR_MODEL_NOTE,
    MODEL_NOTE,
    USD_UNAVAILABLE,
    MacroLeg,
    MacroRow,
    MacroSection,
)
from factordesk.section_hooks.context import (
    DollarInput,
    MacroInput,
    SectionContext,
    WorldBenchmarkInput,
)
from factordesk.section_hooks.world_beta import load_world_benchmark

logger = logging.getLogger(__name__)

ROLES: dict[str, str] = {
    "IEF": "TERM = IEF minus RF; DEF = LQD minus IEF",
    "LQD": "DEF = LQD minus IEF",
    "DBC": "COMM = DBC minus RF",
    "TIP": "INFL = TIP minus IEI",
    "IEI": "INFL = TIP minus IEI",
    DOLLAR_SERIES: "USD = daily return of the Fed nominal broad dollar index",
}
EUR_ROLES: dict[str, str] = {
    "IEF": "TERM = IEF minus the US dollar cash rate, in euros; DEF = LQD minus IEF, in euros",
    "LQD": "DEF = LQD minus IEF, in euros",
    "DBC": "COMM = DBC in euros minus the euro cash rate",
    "TIP": "INFL = TIP minus IEI, in euros",
    "IEI": "INFL = TIP minus IEI, in euros",
}
EUR_USD_TICKER = "USD/EUR"
EURO_VIEW_START = date(1999, 1, 4)
"""First ECB reference rate (the EUR view starts in January 1999): the USD/EUR leg's first date."""
EUR_USD_ROLE = (
    "USD = return of the US dollar measured in euros (euro reference rate, see the currency footer)"
)
FUNDS_UNAVAILABLE = "The prices of {funds} could not be fetched."


def load_dollar(*, data_dir: Path | None = None, now: datetime | None = None) -> DollarInput:
    """The dollar index levels or why there are none. Never raises."""
    try:
        found = load_fred_series(DOLLAR_SERIES, data_dir=data_dir, now=now)
    except FredError as exc:
        logger.warning("The dollar index could not be fetched: %s", exc)
        return DollarInput(levels=None, unavailable_reason=str(exc))
    except Exception as exc:  # anything else: the report still builds without the dollar
        logger.warning("The dollar index failed", exc_info=True)
        return DollarInput(levels=None, unavailable_reason=f"{type(exc).__name__}: {exc}")
    return DollarInput(levels=found.values, note=found.note)


def load_macro_input(
    provider: PriceProvider, *, data_dir: Path | None = None, now: datetime | None = None
) -> MacroInput:
    """The five fund histories and the dollar index. Never raises."""
    funds = {t: load_world_benchmark(provider, t) for t in LEG_TICKERS}
    return MacroInput(funds=funds, dollar=load_dollar(data_dir=data_dir, now=now))


def _info(
    info: SampleInfo, n: int, start: pd.Timestamp | None, end: pd.Timestamp | None
) -> SampleInfo:
    return info.model_copy(
        update={
            "n": n,
            "start": None if start is None else start.date(),
            "end": None if end is None else end.date(),
        }
    )


def _first_date(series: pd.Series) -> date | None:
    finite = series.dropna()
    return None if finite.empty else pd.Timestamp(finite.index[0]).date()


def _levels(bench: WorldBenchmarkInput) -> pd.Series | None:
    if bench.history is None:
        return None
    frame, _ = collapse_duplicate_dates(bench.history.frame)
    return frame["adj_close"].astype("float64")


def _legs(
    funds: dict[str, pd.Series | None], dollar: pd.Series | None, euro: EuroLegs | None = None
) -> list[MacroLeg]:
    roles = ROLES if euro is None else EUR_ROLES
    out = [
        MacroLeg(
            ticker=t,
            role=roles[t],
            first_date=None if (lv := funds.get(t)) is None else _first_date(lv),
        )
        for t in LEG_TICKERS
    ]
    if euro is not None:
        out.append(MacroLeg(ticker=EUR_USD_TICKER, role=EUR_USD_ROLE, first_date=EURO_VIEW_START))
    elif dollar is not None:
        out.append(
            MacroLeg(
                ticker=DOLLAR_SERIES, role=ROLES[DOLLAR_SERIES], first_date=_first_date(dollar)
            )
        )
    return out


def _rows(fit: MacroFit, euro: bool = False) -> list[MacroRow]:
    out: list[MacroRow] = []
    by_code = factors_of(euro)
    for r in fit.rows:
        f = by_code[r.code]
        out.append(
            MacroRow.model_validate(
                {
                    "code": r.code,
                    "name": f.name,
                    "label": f.label,
                    "definition": f.definition,
                    "note": f.note,
                    "beta": r.beta,
                    "se": r.se,
                    "t": r.t,
                    "p": r.p,
                    "ci_low": r.ci_low,
                    "ci_high": r.ci_high,
                    "tag": r.tag,
                    "vif": max(r.vif, 1.0),
                    "beta_same_day": r.beta_same_day,
                    "beta_lag": r.beta_lag,
                }
            )
        )
    return out


def _limiting_leg(legs: list[MacroLeg], first_row: date, subject_start: date) -> str | None:
    """The fund with the latest first date, only when it starts on or after the subject.

    A fund that starts before the subject limits nothing: the first row of a daily regression is
    always dropped for the dollar lag, which is not the fund's doing.
    """
    dated = [leg for leg in legs if leg.first_date is not None]
    if not dated or first_row <= subject_start:
        return None
    latest = max(dated, key=lambda leg: leg.first_date or date.min)
    if latest.first_date is None or latest.first_date < subject_start:
        return None
    return latest.ticker


def build_macro(ctx: SectionContext) -> MacroSection | None:
    """The section, or ``None`` when the feature did not run (no macro input)."""
    macro = ctx.inputs.macro
    if macro is None:
        return None
    reference = ctx.inputs.reference
    eur = reference is not None
    frequency = ctx.subject.frequency
    base = ctx.sample_info(None)

    def block(
        status: Status,
        reason: str | None,
        *,
        legs: list[MacroLeg],
        usd_included: bool,
        usd_note: str | None,
        n: int = 0,
        n_sample: int | None = None,
        start: pd.Timestamp | None = None,
        end: pd.Timestamp | None = None,
        fit: MacroFit | None = None,
        limited_by: str | None = None,
    ) -> MacroSection:
        return MacroSection.model_validate(
            {
                "status": status,
                "reason": reason,
                "sample": _info(base, n, start, end),
                "model_note": EUR_MODEL_NOTE if eur else MODEL_NOTE,
                "n_obs": n,
                "n_sample": ctx.sample.n if n_sample is None else n_sample,
                "frequency": frequency,
                "hac_lags": 0 if fit is None else fit.lags,
                "t_reference": None
                if fit is None
                else ("normal" if fit.t_df is None else "student_t"),
                "r2": None if fit is None else fit.r2,
                "adj_r2": None if fit is None else fit.adj_r2,
                "rows": [] if fit is None else _rows(fit, eur),
                "correlation_codes": [] if fit is None else list(fit.codes),
                "correlation": []
                if fit is None
                else [[float(v) for v in row] for row in fit.correlation],
                "legs": [leg.model_dump() for leg in legs],
                "window_limited_by": limited_by,
                "usd_included": usd_included,
                "usd_note": usd_note,
                "usd_lag_note": None
                if fit is None or frequency != "daily" or "usd" not in fit.codes
                else (EUR_USD_LAG_NOTE if eur else USD_LAG_NOTE),
            }
        )

    levels = {t: _levels(macro.funds[t]) if t in macro.funds else None for t in LEG_TICKERS}
    euro: EuroLegs | None = None
    if reference is None:
        dollar = macro.dollar.levels
        usd_note = USD_UNAVAILABLE if dollar is None else macro.dollar.note
    else:  # EUR view: the dollar leg is the USD/EUR return, not the Fed index
        dollar = None
        usd_note = None
        try:
            euro = EuroLegs(reference.fx_returns(ctx.subject.calendar), reference.usd_rf)
        except Exception:  # the exchange rates are down: the section says so
            logger.warning("macro section: no USD/EUR rate", exc_info=True)
            return block(
                "failed",
                "The macro regression needs the USD/EUR rate and it is unavailable.",
                legs=_legs(levels, None),
                usd_included=False,
                usd_note=None,
            )
    legs = _legs(levels, dollar, euro)
    usd_on = euro is not None or dollar is not None
    missing = [t for t in LEG_TICKERS if levels[t] is None]
    if missing:
        return block(
            "failed",
            FUNDS_UNAVAILABLE.format(funds=", ".join(missing)),
            legs=legs,
            usd_included=usd_on,
            usd_note=usd_note,
        )
    present = {t: lv for t, lv in levels.items() if lv is not None}
    try:
        design, fit = run_macro(ctx.sample, ctx.subject.calendar, present, dollar, euro)
    except TooFewRowsError as exc:
        return block(
            "insufficient_data",
            f"The macro regression needs more data: {exc}.",
            legs=legs,
            usd_included=usd_on,
            usd_note=usd_note,
        )
    except DegenerateInputError as exc:
        return block(
            "failed",
            f"The macro regression could not be computed: {exc.reason.rstrip('.')}.",
            legs=legs,
            usd_included=usd_on,
            usd_note=usd_note,
        )
    except Exception as exc:  # any other error: the section says so, the report still builds
        logger.warning("macro section failed", exc_info=True)
        return block(
            "failed",
            f"The macro regression could not be computed ({exc}).",
            legs=legs,
            usd_included=usd_on,
            usd_note=usd_note,
        )
    return block(
        "ok",
        None,
        legs=legs,
        usd_included=usd_on,
        usd_note=usd_note,
        n=fit.nobs,
        n_sample=design.n_sample,
        start=fit.start,
        end=fit.end,
        fit=fit,
        limited_by=_limiting_leg(legs, fit.start.date(), ctx.sample.start),
    )


__all__ = ["build_macro", "load_dollar", "load_macro_input"]
