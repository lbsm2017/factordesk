"""Pipeline hook of the energy and carbon section (Sprint 3, S3-8): sensitivities to oil, gas and
carbon prices in a separate regression (``analytics/energy.py``).

``load_energy_input`` fetches Brent and Henry Hub through ``data.fred`` (cached per day) and KRBN
through the provider the pipeline uses (the same incremental refresh and cache as the macro
funds). It never raises: a FRED series that cannot be fetched becomes a ``SeriesInput`` with a
reason, and KRBN becomes a ``WorldBenchmarkInput`` with a reason. ``build_energy`` reads the
context and that input and nothing else. It returns ``None`` only when the feature did not run
(no energy input).

Soft fail. When Brent or Henry Hub is unavailable the section has status ``failed`` and a notice;
the panel shows the notice and the report is not blocked. A missing KRBN removes only the carbon
model, with a note. Too few rows give ``insufficient_data``; a singular design gives ``failed``.
The hook never raises for data reasons, never changes a core section and never blocks the report
(CODING_STANDARDS section 8).
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from pathlib import Path

import pandas as pd

from factordesk.analytics.energy import (
    CARBON_TICKER,
    EnergyFit,
    EnergyResult,
    factors_of,
    run_energy,
)
from factordesk.analytics.macro import TooFewRowsError
from factordesk.analytics.sample import DegenerateInputError
from factordesk.data.fred import BRENT_SERIES, HENRY_HUB_SERIES, FredError, load_fred_series
from factordesk.data.prices import PriceProvider, collapse_duplicate_dates
from factordesk.report.base import SampleInfo, Status
from factordesk.report.sections.energy import (
    EUR_MODEL_NOTE,
    FRED_UNAVAILABLE,
    GAS_NOTE_DAILY,
    GAS_NOTE_MONTHLY,
    MODEL_NOTE,
    EnergyLeg,
    EnergyModel,
    EnergyRow,
    EnergySection,
    GasRobustness,
    carbon_label,
)
from factordesk.section_hooks.context import (
    EnergyInput,
    SectionContext,
    SeriesInput,
    WorldBenchmarkInput,
)
from factordesk.section_hooks.world_beta import load_world_benchmark

logger = logging.getLogger(__name__)

ROLES: dict[str, str] = {
    BRENT_SERIES: "OIL = log change of the Brent spot price",
    HENRY_HUB_SERIES: "GAS = log change of the Henry Hub spot price",
    CARBON_TICKER: "CO2 = KRBN total return minus RF",
}
EUR_ROLES: dict[str, str] = {
    BRENT_SERIES: "OIL = log change of the Brent spot price, in US dollars",
    HENRY_HUB_SERIES: "GAS = log change of the Henry Hub spot price, in US dollars",
    CARBON_TICKER: "CO2 = KRBN total return in euros minus the euro cash rate",
}
LEG_CODES: dict[str, str] = {BRENT_SERIES: "oil", HENRY_HUB_SERIES: "gas", CARBON_TICKER: "co2"}
TITLES: dict[str, str] = {
    "long": "Market, oil and gas",
    "carbon": "Market, oil, gas and carbon",
}


def load_fred_levels(
    series_id: str, *, data_dir: Path | None = None, now: datetime | None = None
) -> SeriesInput:
    """The levels of one FRED series or why there are none. Never raises."""
    try:
        found = load_fred_series(series_id, data_dir=data_dir, now=now)
    except FredError as exc:
        logger.warning("FRED %s could not be fetched: %s", series_id, exc)
        return SeriesInput(levels=None, unavailable_reason=str(exc))
    except Exception as exc:  # anything else: the report still builds without the section
        logger.warning("FRED %s failed", series_id, exc_info=True)
        return SeriesInput(levels=None, unavailable_reason=f"{type(exc).__name__}: {exc}")
    return SeriesInput(levels=found.values, note=found.note)


def load_energy_input(
    provider: PriceProvider, *, data_dir: Path | None = None, now: datetime | None = None
) -> EnergyInput:
    """Brent, Henry Hub and the KRBN history. Never raises."""
    return EnergyInput(
        oil=load_fred_levels(BRENT_SERIES, data_dir=data_dir, now=now),
        gas=load_fred_levels(HENRY_HUB_SERIES, data_dir=data_dir, now=now),
        carbon=load_world_benchmark(provider, CARBON_TICKER),
    )


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
    finite = series.where(series > 0).dropna()
    return None if finite.empty else pd.Timestamp(finite.index[0]).date()


def _carbon_levels(bench: WorldBenchmarkInput) -> pd.Series | None:
    if bench.history is None:
        return None
    frame, _ = collapse_duplicate_dates(bench.history.frame)
    return frame["adj_close"].astype("float64")


def _legs(levels: dict[str, pd.Series | None], euro: bool = False) -> list[EnergyLeg]:
    roles = EUR_ROLES if euro else ROLES
    return [
        EnergyLeg(
            ticker=ticker,
            code=LEG_CODES[ticker],  # pyright: ignore[reportArgumentType]
            role=roles[ticker],
            first_date=None if (lv := levels.get(ticker)) is None else _first_date(lv),
        )
        for ticker in (BRENT_SERIES, HENRY_HUB_SERIES, CARBON_TICKER)
    ]


def _limiting_leg(
    legs: list[EnergyLeg], codes: tuple[str, ...], first_row: date, subject_start: date
) -> str | None:
    """The series with the latest first date among the model's legs, only when it starts on or
    after the subject (the macro rule: a series that starts before the subject limits nothing)."""
    dated = [leg for leg in legs if leg.code in codes and leg.first_date is not None]
    if not dated or first_row <= subject_start:
        return None
    latest = max(dated, key=lambda leg: leg.first_date or date.min)
    if latest.first_date is None or latest.first_date < subject_start:
        return None
    return latest.ticker


def _model(
    key: str, fit: EnergyFit, legs: list[EnergyLeg], subject_start: date, euro: bool = False
) -> EnergyModel:
    by_code = factors_of(euro)
    rows = [
        EnergyRow.model_validate(
            {
                "code": r.code,
                "name": by_code[r.code].name,
                "label": by_code[r.code].label,
                "definition": by_code[r.code].definition,
                "note": by_code[r.code].note,
                "beta": r.beta,
                "se": r.se,
                "t": r.t,
                "p": r.p,
                "ci_low": r.ci_low,
                "ci_high": r.ci_high,
                "tag": r.tag,
                "vif": max(r.vif, 1.0),
            }
        )
        for r in fit.rows
    ]
    g = fit.gas_robust
    return EnergyModel.model_validate(
        {
            "key": key,
            "title": TITLES[key],
            "label": carbon_label(fit.start.date()) if key == "carbon" else None,
            "n_obs": fit.nobs,
            "start": fit.start.date(),
            "end": fit.end.date(),
            "hac_lags": fit.lags,
            "t_reference": "normal" if fit.t_df is None else "student_t",
            "r2": fit.r2,
            "adj_r2": fit.adj_r2,
            "rows": [r.model_dump() for r in rows],
            "gas_robust": GasRobustness(
                beta=g.beta,
                se=g.se,
                t=g.t,
                p=g.p,
                n_excluded=g.n_excluded,
                excluded_dates=[d.date() for d in g.excluded_dates],
                n_obs=g.nobs,
            ).model_dump(),
            "window_limited_by": _limiting_leg(legs, fit.codes, fit.start.date(), subject_start),
        }
    )


def build_energy(ctx: SectionContext) -> EnergySection | None:
    """The section, or ``None`` when the feature did not run (no energy input)."""
    energy = ctx.inputs.energy
    if energy is None:
        return None
    reference = ctx.inputs.reference
    eur = reference is not None
    frequency = ctx.subject.frequency
    base = ctx.sample_info(None)

    def block(
        status: Status,
        reason: str | None,
        legs: list[EnergyLeg],
        *,
        result: EnergyResult | None = None,
        carbon_note: str | None = None,
    ) -> EnergySection:
        notes = [
            f"{name}: {s.note}"
            for name, s in (("Brent", energy.oil), ("Henry Hub", energy.gas))
            if s.note
        ]
        long_model = (
            None if result is None else _model("long", result.long, legs, ctx.sample.start, eur)
        )
        carbon_model = (
            None
            if result is None or result.carbon is None
            else _model("carbon", result.carbon, legs, ctx.sample.start, eur)
        )
        fit = None if result is None else result.long
        return EnergySection.model_validate(
            {
                "status": status,
                "reason": reason,
                "sample": _info(
                    base,
                    0 if fit is None else fit.nobs,
                    None if fit is None else fit.start,
                    None if fit is None else fit.end,
                ),
                "model_note": EUR_MODEL_NOTE if eur else MODEL_NOTE,
                "gas_note": GAS_NOTE_DAILY if frequency == "daily" else GAS_NOTE_MONTHLY,
                "frequency": frequency,
                "n_sample": ctx.sample.n if result is None else result.n_sample,
                "long_model": None if long_model is None else long_model.model_dump(),
                "carbon_model": None if carbon_model is None else carbon_model.model_dump(),
                "carbon_note": carbon_note if carbon_model is None else None,
                "fred_note": " ".join(notes) if notes else None,
                "legs": [leg.model_dump() for leg in legs],
            }
        )

    carbon = _carbon_levels(energy.carbon)
    legs = _legs(
        {
            BRENT_SERIES: energy.oil.levels,
            HENRY_HUB_SERIES: energy.gas.levels,
            CARBON_TICKER: carbon,
        },
        eur,
    )
    if energy.oil.levels is None or energy.gas.levels is None:
        return block("failed", FRED_UNAVAILABLE, legs)
    fx = None
    if reference is not None:
        try:
            fx = reference.fx_returns(ctx.subject.calendar)
        except Exception:  # the exchange rates are down: the section says so
            logger.warning("energy section: no USD/EUR rate", exc_info=True)
            return block(
                "failed",
                "The energy regression needs the USD/EUR rate and it is unavailable.",
                legs,
            )
    try:
        result = run_energy(
            ctx.sample, ctx.subject.calendar, energy.oil.levels, energy.gas.levels, carbon, fx
        )
    except TooFewRowsError as exc:
        return block("insufficient_data", f"The energy regression needs more data: {exc}.", legs)
    except DegenerateInputError as exc:
        return block(
            "failed",
            f"The energy regression could not be computed: {exc.reason.rstrip('.')}.",
            legs,
        )
    except Exception as exc:  # any other error: the section says so, the report still builds
        logger.warning("energy section failed", exc_info=True)
        return block("failed", f"The energy regression could not be computed ({exc}).", legs)
    return block("ok", None, legs, result=result, carbon_note=result.carbon_note)


__all__ = ["build_energy", "load_energy_input", "load_fred_levels"]
