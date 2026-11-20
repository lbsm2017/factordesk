"""Energy and carbon sensitivities (Sprint 3, S3-8): analytics, loader, hook and report. All data
is synthetic, no network. Expected values come from the data (an independent refit, an
independent VIF), never from literals, and floats are compared with a tolerance.

Run ``uv run python -m factordesk.tests.test_energy`` to regenerate the synthetic fixture
``fixtures/sections/energy.json`` (a daily ticker report); the frontend reads the same file.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from factordesk.analytics.energy import (
    CARBON_CODES,
    FACTORS,
    LONG_CODES,
    MIN_CARBON_ROWS,
    MIN_ROWS,
    SPIKE_ROWS,
    EnergyColumns,
    build_columns,
    design_of,
    fit_energy,
    run_energy,
    spike_positions,
)
from factordesk.analytics.macro import TooFewRowsError
from factordesk.analytics.regression import ols_hac, two_sided_p, two_sided_t_p
from factordesk.analytics.sample import AnalysisSample, build_sample, build_subject_sample
from factordesk.analytics.subject import subject_from_history, subject_from_monthly_returns
from factordesk.data.fred import BRENT_SERIES, HENRY_HUB_SERIES, FredError
from factordesk.data.prices import PriceHistory
from factordesk.pipeline import assemble_report, assemble_subject_report
from factordesk.report import FactorReport
from factordesk.report.sections.energy import (
    CARBON_LABEL,
    FRED_UNAVAILABLE,
    GAS_NOTE_DAILY,
    GAS_NOTE_MONTHLY,
)
from factordesk.section_hooks.context import (
    EnergyInput,
    SectionInputs,
    SeriesInput,
    WorldBenchmarkInput,
)
from factordesk.section_hooks.energy import load_energy_input, load_fred_levels
from factordesk.section_hooks.registry import HOOKS
from factordesk.tests.fixtures.dgp import FloatArray, default_rf, dgp_a, price_history, rng_for
from factordesk.tests.test_subject import monthly_case

NOW = datetime(2026, 11, 20, 12, 0, tzinfo=UTC)
FIXTURE = Path(__file__).parent / "fixtures" / "sections" / "energy.json"
ORIGIN = pd.Timestamp("2009-12-31")

# True betas of the synthetic subject: Mkt-RF, OIL, GAS, CO2.
BETAS = np.array([0.9, 0.2, 0.02, 0.1])
SIGMA_E = 0.003
TOL = 1e-9


@dataclass(frozen=True)
class EnergyCase:
    stock: PriceHistory
    factors: pd.DataFrame
    oil_levels: pd.Series
    gas_levels: pd.Series
    krbn: PriceHistory
    dates: pd.DatetimeIndex
    oil: FloatArray
    """Daily log returns of the oil leg, one per date."""
    gas: FloatArray
    co2: FloatArray
    """KRBN return minus RF, one per date (KRBN prices start at ``krbn_start``)."""
    rf: FloatArray


def _levels(log_returns: FloatArray, dates: pd.DatetimeIndex, start: float) -> pd.Series:
    values = start * np.exp(np.concatenate([[0.0], np.cumsum(log_returns)]))
    return pd.Series(values, index=pd.DatetimeIndex([ORIGIN, *dates], name="date"))


def make_energy_case(test_number: int, *, n: int = 1500, krbn_start: int = 0) -> EnergyCase:
    """The subject follows ``BETAS`` on market, oil, gas and carbon. Gas is fat-tailed (Student-t
    with 2.5 degrees of freedom) with five planted spikes. KRBN prices start ``krbn_start`` rows
    after the subject's first return."""
    rng = rng_for(test_number)
    base = dgp_a(rng, n=n)
    rf = default_rf(n)
    oil = rng.normal(0.0, 0.015, size=n)
    gas = 0.012 * rng.standard_t(2.5, size=n)
    for k, size in zip((50, 400, 700, 900, 1200), (1.2, -0.9, 0.8, 1.0, -1.1), strict=True):
        if k < n:
            gas[k] = size
    co2 = rng.normal(0.0, 0.02, size=n) + 0.3 * base.factors["Mkt-RF"].to_numpy()
    mkt = base.factors["Mkt-RF"].to_numpy(dtype=np.float64)
    x = np.column_stack([mkt, oil, gas, co2])
    y = x @ BETAS + rng.normal(0.0, SIGMA_E, size=n)
    stock = price_history(rf + y, base.dates, ticker="STK")
    krbn_ret = rf + co2
    k = krbn_start
    krbn = price_history(
        krbn_ret[k:],
        base.dates[k:],
        first_date=ORIGIN if k == 0 else base.dates[k - 1],
        ticker="KRBN",
    )
    return EnergyCase(
        stock=stock,
        factors=base.factors,
        oil_levels=_levels(oil, base.dates, 60.0),
        gas_levels=_levels(gas, base.dates, 3.0),
        krbn=krbn,
        dates=base.dates,
        oil=oil,
        gas=gas,
        co2=co2,
        rf=rf,
    )


def energy_input(
    case: EnergyCase,
    *,
    oil: SeriesInput | None = None,
    gas: SeriesInput | None = None,
    carbon: WorldBenchmarkInput | None = None,
) -> EnergyInput:
    return EnergyInput(
        oil=oil or SeriesInput(levels=case.oil_levels),
        gas=gas or SeriesInput(levels=case.gas_levels),
        carbon=carbon or WorldBenchmarkInput(history=case.krbn),
    )


def report_of(case: EnergyCase, inputs: SectionInputs | None) -> FactorReport:
    return assemble_report(
        "STK",
        case.stock,
        case.factors,
        now=NOW,
        factors_downloaded_at=None,
        section_inputs=inputs,
    )


def columns_of(case: EnergyCase, *, with_carbon: bool = True) -> EnergyColumns:
    sample = build_sample(case.stock, case.factors)
    calendar = pd.DatetimeIndex(case.stock.frame.index)
    carbon = case.krbn.frame["adj_close"] if with_carbon else None
    return build_columns(sample, calendar, case.oil_levels, case.gas_levels, carbon)


def independent_vif(x: FloatArray) -> FloatArray:
    """VIF of each column from its own R squared against the others (plain least squares)."""
    out = np.empty(x.shape[1])
    for j in range(x.shape[1]):
        others = np.column_stack([np.ones(len(x)), np.delete(x, j, axis=1)])
        coef, *_ = np.linalg.lstsq(others, x[:, j], rcond=None)
        resid = x[:, j] - others @ coef
        total = x[:, j] - x[:, j].mean()
        out[j] = 1.0 / (1.0 - (1.0 - float(resid @ resid) / float(total @ total)))
    return out


# --------------------------------------------------------------------------------- the legs
def test_the_legs_follow_their_definitions() -> None:
    case = make_energy_case(8301, n=800)
    cols = columns_of(case)
    assert cols.n_sample == 800 and cols.frequency == "daily"
    np.testing.assert_allclose(cols.oil, case.oil, atol=1e-12)  # log return of the Brent level
    np.testing.assert_allclose(cols.gas, case.gas, atol=1e-12)
    np.testing.assert_allclose(cols.co2, case.co2, atol=1e-12)  # KRBN return minus RF
    np.testing.assert_allclose(cols.mkt, case.factors["Mkt-RF"].to_numpy(), atol=0)
    assert np.isnan(columns_of(case, with_carbon=False).co2).all()  # no KRBN: no CO2 leg


def test_a_missing_fred_day_removes_that_day_and_the_next() -> None:
    case = make_energy_case(8302, n=600)
    lv = case.oil_levels.drop(case.dates[100])
    sample = build_sample(case.stock, case.factors)
    cols = build_columns(
        sample, pd.DatetimeIndex(case.stock.frame.index), lv, case.gas_levels, None
    )
    bad = np.flatnonzero(np.isnan(cols.oil))
    assert list(bad) == [100, 101]
    design = design_of(cols, LONG_CODES)
    assert design.n == 598 and case.dates[100] not in design.dates


def test_a_non_positive_price_is_a_missing_price() -> None:
    case = make_energy_case(8303, n=600)
    lv = case.gas_levels.copy()
    lv.iloc[200] = -1.0
    sample = build_sample(case.stock, case.factors)
    cols = build_columns(
        sample, pd.DatetimeIndex(case.stock.frame.index), case.oil_levels, lv, None
    )
    assert int(np.isnan(cols.gas).sum()) == 2 and np.isfinite(cols.gas[:198]).all()


# -------------------------------------------------------------------------------- the fits
def test_known_betas_are_recovered_inside_their_intervals() -> None:
    case = make_energy_case(8304, n=2000)
    sample = build_sample(case.stock, case.factors)
    result = run_energy(
        sample,
        pd.DatetimeIndex(case.stock.frame.index),
        case.oil_levels,
        case.gas_levels,
        case.krbn.frame["adj_close"],
    )
    assert [r.code for r in result.long.rows] == list(LONG_CODES)
    assert result.carbon is not None and [r.code for r in result.carbon.rows] == list(CARBON_CODES)
    assert result.long.t_df is None and result.long.nobs == 2000
    # CO2 moves with the market, so the long model (without it) biases the market beta: only its
    # oil and gas rows are compared with the truth there.
    for fit, truth, skip in ((result.long, BETAS[:3], 1), (result.carbon, BETAS, 0)):
        for row, beta in list(zip(fit.rows, truth, strict=False))[skip:]:
            assert row.ci_low < beta < row.ci_high, (row.code, row.beta, row.ci_low, row.ci_high)
    assert [f.code for f in FACTORS] == ["mkt_rf", "oil", "gas", "co2"]
    oil = result.long.rows[1]
    assert oil.tag == "reliable" and oil.p < 1e-6


def test_every_leg_has_a_vif_that_matches_an_independent_computation() -> None:
    case = make_energy_case(8305, n=1500)
    sample = build_sample(case.stock, case.factors)
    result = run_energy(
        sample,
        pd.DatetimeIndex(case.stock.frame.index),
        case.oil_levels,
        case.gas_levels,
        case.krbn.frame["adj_close"],
    )
    assert result.carbon is not None and result.carbon_design is not None
    for fit, design in ((result.long, result.long_design), (result.carbon, result.carbon_design)):
        expected = independent_vif(design.x)
        assert len(fit.rows) == design.x.shape[1]
        for row, vif in zip(fit.rows, expected, strict=True):
            assert math.isfinite(row.vif) and row.vif >= 1.0
            assert row.vif == pytest.approx(vif, rel=1e-9)


def test_the_section_reports_the_vif_of_each_leg() -> None:
    case = make_energy_case(8306, n=1200)
    s = report_of(case, SectionInputs(energy=energy_input(case))).energy
    assert s is not None and s.long_model is not None and s.carbon_model is not None
    for model in (s.long_model, s.carbon_model):
        design = design_of(columns_of(case), [r.code for r in model.rows])
        expected = independent_vif(design.x)
        assert [r.code for r in model.rows] == list(
            LONG_CODES if model.key == "long" else CARBON_CODES
        )
        np.testing.assert_allclose([r.vif for r in model.rows], expected, rtol=1e-9)


# --------------------------------------------------------------- gas robustness (5 rows)
def test_the_robustness_beta_leaves_out_exactly_five_rows_and_refits() -> None:
    case = make_energy_case(8307, n=1500)
    design = design_of(columns_of(case), LONG_CODES)
    fit = fit_energy(design)
    g = fit.gas_robust
    gas = design.x[:, LONG_CODES.index("gas")]
    top = np.argsort(-np.abs(gas), kind="stable")[:SPIKE_ROWS]
    assert g.n_excluded == SPIKE_ROWS == 5 and len(g.excluded_dates) == 5
    assert g.nobs == design.n - 5 == fit.nobs - 5
    assert list(g.excluded_dates) == [design.dates[i] for i in top]
    # The planted spikes are the five largest moves.
    assert set(design.dates[top]) == {case.dates[k] for k in (50, 400, 700, 900, 1200)}
    keep = np.ones(design.n, dtype=bool)
    keep[top] = False
    ref = ols_hac(design.y[keep], design.x[keep], small_sample=False)
    i = 1 + LONG_CODES.index("gas")
    assert g.beta == pytest.approx(float(ref.params[i]), rel=TOL, abs=1e-15)
    assert g.se == pytest.approx(float(ref.bse[i]), rel=TOL)
    assert g.t == pytest.approx(float(ref.params[i] / ref.bse[i]), rel=TOL)
    assert g.p == pytest.approx(float(two_sided_p(np.array([g.t]))[0]), rel=TOL, abs=1e-15)
    # Nothing is winsorised: the main fit is the plain fit on every row.
    full = ols_hac(design.y, design.x, small_sample=False)
    assert fit.rows[2].beta == pytest.approx(float(full.params[i]), rel=TOL)
    assert g.beta != fit.rows[2].beta


def test_the_carbon_model_has_its_own_robustness_fit() -> None:
    case = make_energy_case(8308, n=1500)
    cols = columns_of(case)
    long_fit = fit_energy(design_of(cols, LONG_CODES))
    carbon_fit = fit_energy(design_of(cols, CARBON_CODES))
    assert long_fit.gas_robust.n_excluded == carbon_fit.gas_robust.n_excluded == 5
    assert long_fit.gas_robust.beta != carbon_fit.gas_robust.beta


def test_a_monthly_subject_leaves_out_five_months_and_uses_student_t() -> None:
    sample, calendar, oil, gas, krbn = monthly_world(8309, n=120, krbn_months=100)
    result = run_energy(sample, calendar, oil, gas, krbn)
    fit = result.long
    assert fit.t_df is not None and fit.t_df == fit.nobs - 4  # intercept and three legs
    g = fit.gas_robust
    assert g.n_excluded == 5 and g.nobs == fit.nobs - 5
    design = result.long_design
    gas_col = design.x[:, 2]
    top = np.argsort(-np.abs(gas_col), kind="stable")[:5]
    keep = np.ones(design.n, dtype=bool)
    keep[top] = False
    ref = ols_hac(design.y[keep], design.x[keep], small_sample=True)
    assert g.beta == pytest.approx(float(ref.params[3]), rel=TOL, abs=1e-15)
    assert ref.t_df is not None
    t = float(ref.params[3] / ref.bse[3])
    assert g.t == pytest.approx(t, rel=TOL)
    assert g.p == pytest.approx(float(two_sided_t_p(np.array([t]), ref.t_df)[0]), rel=TOL)


def test_spike_positions_take_the_largest_absolute_values_earlier_row_first() -> None:
    gas = np.array([0.1, -0.5, 0.5, 0.2, -0.3, 0.05, 0.4])
    assert spike_positions(gas, 3) == [1, 2, 6]
    assert len(spike_positions(gas)) == 5


# ------------------------------------------------------------- the carbon model and its window
def test_the_carbon_model_starts_at_krbns_first_date_and_names_it_as_the_limit() -> None:
    case = make_energy_case(8310, n=1500, krbn_start=700)
    s = report_of(case, SectionInputs(energy=energy_input(case))).energy
    assert s is not None and s.status == "ok"
    assert s.long_model is not None and s.carbon_model is not None
    assert s.carbon_model.label == CARBON_LABEL == "short sample, since Aug 2020, mainly EU carbon"
    assert s.long_model.label is None and s.carbon_note is None
    assert s.long_model.n_obs == 1500 and s.carbon_model.n_obs == 800
    assert s.carbon_model.start == case.dates[700].date()
    assert s.long_model.start == case.dates[0].date()
    first = {leg.ticker: leg.first_date for leg in s.legs}
    assert first["KRBN"] == case.dates[699].date()  # the leading price date
    assert s.carbon_model.window_limited_by == "KRBN"
    assert s.long_model.window_limited_by is None  # Brent and Henry Hub start before the subject


def test_a_leg_that_starts_before_the_subject_limits_nothing() -> None:
    case = make_energy_case(8311, n=900, krbn_start=0)
    s = report_of(case, SectionInputs(energy=energy_input(case))).energy
    assert s is not None and s.carbon_model is not None
    assert s.carbon_model.window_limited_by is None and s.long_model is not None
    assert s.long_model.window_limited_by is None


def test_the_long_model_names_the_gas_leg_when_it_starts_after_the_subject() -> None:
    case = make_energy_case(8312, n=1200)
    late = case.gas_levels.iloc[300:]  # Henry Hub history begins 300 rows in
    s = report_of(
        case, SectionInputs(energy=energy_input(case, gas=SeriesInput(levels=late)))
    ).energy
    assert s is not None and s.long_model is not None
    assert s.long_model.window_limited_by == HENRY_HUB_SERIES
    assert s.long_model.start == case.dates[300].date() and s.long_model.n_obs == 900


def test_the_carbon_model_is_hidden_with_fewer_than_two_years_of_data() -> None:
    n = 1500
    assert MIN_CARBON_ROWS == {"daily": 504, "monthly": 24}
    for carbon_rows, shown in (
        (MIN_CARBON_ROWS["daily"] - 1, False),
        (MIN_CARBON_ROWS["daily"], True),
    ):
        case = make_energy_case(8313, n=n, krbn_start=n - carbon_rows)
        s = report_of(case, SectionInputs(energy=energy_input(case))).energy
        assert s is not None and s.status == "ok" and s.long_model is not None
        assert (s.carbon_model is not None) is shown, carbon_rows
        if shown:
            assert s.carbon_model is not None and s.carbon_model.n_obs == carbon_rows
            assert s.carbon_note is None
        else:
            assert s.carbon_note is not None and str(carbon_rows) in s.carbon_note
            assert "2 years" in s.carbon_note
        assert s.long_model.n_obs == n  # the long model never loses rows to KRBN


def test_a_monthly_carbon_model_needs_24_months() -> None:
    for months, shown in ((23, False), (24, True)):
        sample, calendar, oil, gas, krbn = monthly_world(8314, n=120, krbn_months=months + 1)
        result = run_energy(sample, calendar, oil, gas, krbn)
        assert (result.carbon is not None) is shown, months
        if shown:
            assert result.carbon is not None and result.carbon.nobs == months
        else:
            assert result.carbon_note is not None and "months" in result.carbon_note


def test_without_krbn_prices_only_the_carbon_model_is_left_out() -> None:
    case = make_energy_case(8315, n=900)
    down = WorldBenchmarkInput(history=None, unavailable_reason="rate limited")
    s = report_of(case, SectionInputs(energy=energy_input(case, carbon=down))).energy
    assert s is not None and s.status == "ok" and s.long_model is not None
    assert s.carbon_model is None and s.carbon_note is not None and "KRBN" in s.carbon_note
    assert {leg.ticker: leg.first_date for leg in s.legs}["KRBN"] is None


# --------------------------------------------------------------------------- soft fail (FRED)
@pytest.mark.parametrize("down", ["oil", "gas"])
def test_a_missing_fred_series_hides_the_section_with_a_notice(down: str) -> None:
    case = make_energy_case(8316, n=900)
    gone = SeriesInput(levels=None, unavailable_reason="network error")
    inputs = energy_input(case, **{down: gone})  # pyright: ignore[reportArgumentType]
    report = report_of(case, SectionInputs(energy=inputs))  # the report is still built
    s = report.energy
    assert s is not None and s.status == "failed" and s.reason == FRED_UNAVAILABLE
    assert s.long_model is None and s.carbon_model is None
    assert report.regression is not None
    again = FactorReport.model_validate_json(report.model_dump_json())
    assert again.energy == s


def test_load_fred_levels_never_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import factordesk.section_hooks.energy as hook

    def unreachable(*args: object, **kwargs: object) -> None:
        raise FredError("DCOILBRENTEU: download failed after 2 attempts (network error)")

    monkeypatch.setattr(hook, "load_fred_series", unreachable)
    got = load_fred_levels(BRENT_SERIES, data_dir=tmp_path, now=NOW)
    assert got.levels is None and got.unavailable_reason is not None

    def odd(*args: object, **kwargs: object) -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr(hook, "load_fred_series", odd)
    assert load_fred_levels(HENRY_HUB_SERIES, data_dir=tmp_path, now=NOW).levels is None


def test_load_energy_input_fetches_both_series_and_krbn(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import factordesk.section_hooks.energy as hook

    case = make_energy_case(8317, n=300)
    asked: list[str] = []

    def fake_fred(series: str, **kwargs: object) -> object:
        asked.append(series)
        raise FredError("offline")

    class Provider:
        def fetch(self, ticker: str) -> PriceHistory:
            asked.append(ticker)
            return case.krbn

    monkeypatch.setattr(hook, "load_fred_series", fake_fred)
    got = load_energy_input(Provider(), data_dir=tmp_path, now=NOW)
    assert asked == [BRENT_SERIES, HENRY_HUB_SERIES, "KRBN"]
    assert got.oil.levels is None and got.gas.levels is None and got.carbon.history is not None


def test_too_few_rows_is_insufficient_data() -> None:
    case = make_energy_case(8318, n=700)
    short = case.oil_levels.iloc[
        700 - (MIN_ROWS["daily"] - 1) :
    ]  # Brent starts 251 rows from the end
    s = report_of(
        case, SectionInputs(energy=energy_input(case, oil=SeriesInput(levels=short)))
    ).energy
    assert s is not None and s.status == "insufficient_data" and s.long_model is None
    assert s.carbon_model is None and str(MIN_ROWS["daily"]) in (s.reason or "")
    with pytest.raises(TooFewRowsError):
        sample = build_sample(case.stock, case.factors)
        run_energy(sample, pd.DatetimeIndex(case.stock.frame.index), short, case.gas_levels, None)


def test_a_constant_oil_price_fails_the_section_with_a_reason() -> None:
    case = make_energy_case(8319, n=700)
    flat = pd.Series(60.0, index=case.oil_levels.index)
    s = report_of(
        case, SectionInputs(energy=energy_input(case, oil=SeriesInput(levels=flat)))
    ).energy
    assert s is not None and s.status == "failed" and s.reason is not None
    assert s.long_model is None and s.carbon_model is None


# ------------------------------------------------------------------------- hook and report
def test_the_hook_is_registered_for_every_source_frequency_and_model() -> None:
    spec = next(s for s in HOOKS if s.field == "energy")
    assert [s.field for s in HOOKS][-2:] == ["macro", "energy"]  # the panel follows macro
    for kind in ("ticker", "upload", "portfolio"):
        for freq in ("daily", "monthly"):
            for model in ("ff5", "ff6"):
                assert spec.applies(kind, freq, model)  # pyright: ignore[reportArgumentType]


def test_a_report_without_the_input_has_no_energy_key() -> None:
    case = make_energy_case(8320, n=600)
    report = report_of(case, None)
    assert report.energy is None
    assert "energy" not in json.loads(report.model_dump_json())


def test_the_daily_section_reports_models_notes_and_the_gas_caveat() -> None:
    case = make_energy_case(8321, n=1200, krbn_start=300)
    report = report_of(case, SectionInputs(energy=energy_input(case)))
    s = report.energy
    assert s is not None and s.status == "ok" and s.reason is None
    assert s.frequency == "daily" and s.gas_note == GAS_NOTE_DAILY and "descriptive" in s.gas_note
    assert s.long_model is not None and s.carbon_model is not None
    assert [r.label for r in s.long_model.rows] == ["Market", "Oil", "Natural gas"]
    assert [r.label for r in s.carbon_model.rows] == ["Market", "Oil", "Natural gas", "Carbon"]
    assert s.long_model.t_reference == "normal" and s.long_model.title == "Market, oil and gas"
    assert s.sample.n == s.long_model.n_obs == 1200 and s.n_sample == 1200
    assert all(r.vif >= 1.0 for r in s.long_model.rows + s.carbon_model.rows)
    assert (
        s.long_model.gas_robust.n_excluded == 5 and len(s.long_model.gas_robust.excluded_dates) == 5
    )
    assert {leg.ticker for leg in s.legs} == {BRENT_SERIES, HENRY_HUB_SERIES, "KRBN"}
    assert s.long_model.start == s.sample.start and s.long_model.end == s.sample.end
    again = FactorReport.model_validate_json(report.model_dump_json())
    assert again.energy == s


def test_ticker_subject_and_plain_returns_give_the_same_section() -> None:
    case = make_energy_case(8322, n=900, krbn_start=100)
    inputs = SectionInputs(energy=energy_input(case))
    a = report_of(case, inputs).energy
    subject = subject_from_history(case.stock)
    b = assemble_subject_report(
        subject, case.factors, now=NOW, factors_downloaded_at=None, section_inputs=inputs
    ).energy
    assert a == b and a is not None


def test_a_monthly_report_has_the_section() -> None:
    n = 120
    returns, factors, _ = monthly_case(n, 41, start="2005-01-31")
    subject = subject_from_monthly_returns(returns, label="Fund")
    days = pd.bdate_range("2004-12-01", pd.DatetimeIndex(returns.index)[-1])
    rng = np.random.default_rng(42)

    def level(scale: float, start: float) -> pd.Series:
        r = rng.normal(0.0, scale, size=len(days) - 1)
        return pd.Series(start * np.exp(np.concatenate([[0.0], np.cumsum(r)])), index=days)

    krbn = level(0.01, 20.0)
    krbn_history = PriceHistory(
        "KRBN",
        pd.DataFrame(
            {"close": krbn, "adj_close": krbn, "dividends": 0.0, "splits": 0.0},
            index=pd.DatetimeIndex(krbn.index, name="date"),
        ),
        NOW,
        "synthetic",
    )
    inputs = EnergyInput(
        oil=SeriesInput(levels=level(0.02, 60.0)),
        gas=SeriesInput(levels=level(0.03, 3.0)),
        carbon=WorldBenchmarkInput(history=krbn_history),
    )
    report = assemble_subject_report(
        subject,
        factors,
        now=NOW,
        factors_downloaded_at=None,
        section_inputs=SectionInputs(energy=inputs),
    )
    s = report.energy
    assert s is not None and s.status == "ok" and s.frequency == "monthly"
    assert s.gas_note == GAS_NOTE_MONTHLY
    assert s.long_model is not None and s.long_model.t_reference == "student_t"
    assert s.long_model.n_obs == n and s.long_model.gas_robust.n_obs == n - 5
    assert (
        s.carbon_model is not None and s.carbon_model.n_obs == n
    )  # KRBN starts before the subject


# ------------------------------------------------------------------------- monthly helpers
def monthly_world(
    test_number: int, *, n: int, krbn_months: int
) -> tuple[AnalysisSample, pd.DatetimeIndex, pd.Series, pd.Series, pd.Series]:
    """A monthly subject (``n`` month-ends) with daily oil, gas and KRBN levels. KRBN has prices
    for its last ``krbn_months`` calendar months only (its first month is partial, so it gives
    ``krbn_months - 1`` monthly returns)."""
    returns, factors, _ = monthly_case(n, test_number, start="2005-01-31")
    subject = subject_from_monthly_returns(returns, label="Fund")
    sample = build_subject_sample(subject, factors)
    month_ends = pd.DatetimeIndex(returns.index)
    days = pd.bdate_range("2004-12-01", month_ends[-1])
    rng = np.random.default_rng(test_number + 1)

    def level(scale: float, start: float, first: pd.Timestamp | None = None) -> pd.Series:
        r = rng.normal(0.0, scale, size=len(days) - 1)
        s = pd.Series(start * np.exp(np.concatenate([[0.0], np.cumsum(r)])), index=days)
        return s if first is None else s[s.index >= first]

    first_month = month_ends[-krbn_months].to_period("M").to_timestamp()
    return (
        sample,
        subject.calendar,
        level(0.02, 60.0),
        level(0.05, 3.0),
        level(0.01, 20.0, first_month),
    )


def test_monthly_legs_are_compounded_to_month_ends_before_the_log() -> None:
    sample, calendar, oil, gas, _ = monthly_world(8330, n=60, krbn_months=1)
    assert sample.frequency == "monthly"
    cols = build_columns(sample, calendar, oil, gas, None)
    last_level: dict[pd.Period, float] = {}
    for stamp, value in zip(
        pd.DatetimeIndex(oil.index), oil.to_numpy(dtype=np.float64), strict=True
    ):
        last_level[stamp.to_period("M")] = float(value)  # sorted index: the last level wins
    wanted = pd.DatetimeIndex(sample.xret.index).to_period("M")
    expected = [math.log(last_level[p] / last_level[p - 1]) for p in wanted]
    np.testing.assert_allclose(cols.oil, expected, atol=1e-12)


if __name__ == "__main__":  # regenerate the shared fixture
    c = make_energy_case(8399, n=720, krbn_start=200)
    r = report_of(c, SectionInputs(energy=energy_input(c)))
    assert r.energy is not None
    FIXTURE.write_text(
        json.dumps(r.energy.model_dump(mode="json"), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {FIXTURE}")
