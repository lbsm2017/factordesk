"""Macro sensitivities (epic E4): analytics, FRED loader, hook and report. All data is synthetic,
no network.

Run ``uv run python -m factordesk.tests.test_macro`` to regenerate the synthetic fixture
``fixtures/sections/macro.json`` (a daily ticker report); the frontend reads the same file.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from statistics import NormalDist

import numpy as np
import pandas as pd
import pytest

from factordesk.analytics.macro import (
    FACTORS,
    LEG_TICKERS,
    MIN_ROWS,
    TooFewRowsError,
    build_design,
    daily_leg_returns,
    fit_macro,
    monthly_leg_returns,
    run_macro,
    summed_beta,
)
from factordesk.analytics.regression import ols_hac
from factordesk.analytics.sample import build_sample, build_subject_sample
from factordesk.analytics.subject import subject_from_history, subject_from_monthly_returns
from factordesk.data.fred import (
    DOLLAR_SERIES,
    FredError,
    load_fred_series,
    parse_fred_csv,
)
from factordesk.data.prices import PriceHistory
from factordesk.pipeline import assemble_report, assemble_subject_report
from factordesk.report import FactorReport
from factordesk.report.sections.macro import MODEL_NOTE, USD_UNAVAILABLE
from factordesk.section_hooks.context import (
    DollarInput,
    MacroInput,
    SectionInputs,
    WorldBenchmarkInput,
)
from factordesk.section_hooks.macro import FUNDS_UNAVAILABLE, load_dollar
from factordesk.section_hooks.registry import HOOKS
from factordesk.tests.fixtures.dgp import FloatArray, default_rf, dgp_a, price_history, rng_for
from factordesk.tests.test_subject import monthly_case

NOW = datetime(2026, 11, 19, 12, 0, tzinfo=UTC)
FIXTURE = Path(__file__).parent / "fixtures" / "sections" / "macro.json"

# True betas of the synthetic subject: Mkt-RF, TERM, DEF, COMM, INFL, USD (same day), USD (lag).
BETAS = np.array([0.9, 0.4, 0.25, 0.3, -0.5, 0.35, 0.15])
SIGMA_E = 0.003


@dataclass(frozen=True)
class MacroCase:
    stock: PriceHistory
    factors: pd.DataFrame
    funds: dict[str, PriceHistory]
    dollar: pd.Series
    dates: pd.DatetimeIndex
    z: FloatArray
    """Daily draws of TERM, DEF, COMM, INFL and USD, one row per date."""
    rf: FloatArray


def make_macro_case(
    test_number: int, *, n: int = 2000, betas: FloatArray = BETAS, lag_in_y: bool = True
) -> MacroCase:
    """The subject's excess return follows ``betas`` on the six factors (and the dollar's lag)."""
    rng = rng_for(test_number)
    base = dgp_a(rng, n=n)
    rf = default_rf(n)
    corr = np.eye(5)
    corr[0, 1] = corr[1, 0] = 0.5  # TERM and DEF
    corr[3, 4] = corr[4, 3] = -0.3  # INFL and USD
    sd = np.array([0.003, 0.002, 0.008, 0.002, 0.004])
    z = rng.multivariate_normal(np.zeros(5), np.outer(sd, sd) * corr, size=n)
    term, dspread, comm, infl, usd = z.T
    usd_prev = np.concatenate([[0.0], usd[:-1]])
    mkt = base.factors["Mkt-RF"].to_numpy(dtype=np.float64)
    x = np.column_stack([mkt, term, dspread, comm, infl, usd, usd_prev if lag_in_y else 0 * usd])
    y = x @ betas + rng.normal(0.0, SIGMA_E, size=n)
    stock = price_history(rf + y, base.dates, ticker="STK")
    ief = rf + term
    iei = rf + 0.0002
    funds = {
        "IEF": price_history(ief, base.dates, ticker="IEF"),
        "LQD": price_history(ief + dspread, base.dates, ticker="LQD"),
        "DBC": price_history(rf + comm, base.dates, ticker="DBC"),
        "IEI": price_history(iei, base.dates, ticker="IEI"),
        "TIP": price_history(iei + infl, base.dates, ticker="TIP"),
    }
    origin = pd.Timestamp("2009-12-31")
    dollar = pd.Series(
        100.0 * np.concatenate([[1.0], np.cumprod(1.0 + usd)]),
        index=pd.DatetimeIndex([origin, *base.dates], name="date"),
        name=DOLLAR_SERIES,
    )
    return MacroCase(stock, base.factors, funds, dollar, base.dates, z, rf)


def levels_of(case: MacroCase) -> dict[str, pd.Series]:
    return {t: h.frame["adj_close"] for t, h in case.funds.items()}


def macro_input(case: MacroCase, *, dollar: DollarInput | None = None) -> MacroInput:
    return MacroInput(
        funds={t: WorldBenchmarkInput(history=h) for t, h in case.funds.items()},
        dollar=dollar or DollarInput(levels=case.dollar),
    )


def run_case(case: MacroCase, *, with_dollar: bool = True):  # noqa: ANN201 - local result pair
    sample = build_sample(case.stock, case.factors)
    calendar = pd.DatetimeIndex(case.stock.frame.index)
    return run_macro(sample, calendar, levels_of(case), case.dollar if with_dollar else None)


def report_of(case: MacroCase, inputs: SectionInputs | None) -> FactorReport:
    return assemble_report(
        "STK",
        case.stock,
        case.factors,
        now=NOW,
        factors_downloaded_at=None,
        section_inputs=inputs,
    )


# ----------------------------------------------------------------------- known betas (daily)
def test_known_betas_are_recovered_inside_their_intervals() -> None:
    _, fit = run_case(make_macro_case(8101))
    rows = {r.code: r for r in fit.rows}
    assert [r.code for r in fit.rows] == [f.code for f in FACTORS]
    truth = {
        "mkt_rf": 0.9,
        "term": 0.4,
        "def": 0.25,
        "comm": 0.3,
        "infl": -0.5,
        "usd": 0.35 + 0.15,  # the summed dollar beta
    }
    for code, beta in truth.items():
        row = rows[code]
        assert row.ci_low < beta < row.ci_high, (code, row.beta, row.ci_low, row.ci_high)
        assert abs(row.beta - beta) < 0.06, code
        assert row.tag == "reliable" and row.p < 1e-6
    assert fit.t_df is None and fit.nobs == 1999
    assert 0.9 < fit.adj_r2 <= fit.r2 < 1.0


def test_an_unrelated_factor_is_not_reliable() -> None:
    betas = BETAS.copy()
    betas[3] = 0.0  # no commodity exposure
    _, fit = run_case(make_macro_case(8102, betas=betas))
    comm = next(r for r in fit.rows if r.code == "comm")
    assert abs(comm.beta) < 3 * comm.se and comm.tag == "noise"


def test_the_factor_columns_follow_their_definitions() -> None:
    case = make_macro_case(8103, n=800)
    sample = build_sample(case.stock, case.factors)
    design = build_design(
        sample, pd.DatetimeIndex(case.stock.frame.index), levels_of(case), case.dollar
    )
    term, dspread, comm, infl, usd = case.z.T
    k = design.n
    assert k == 799  # the first day has no lagged dollar return
    skip = 800 - k
    cols = dict(zip(design.codes, design.x.T, strict=True))
    np.testing.assert_allclose(cols["term"], term[skip:], atol=1e-12)
    np.testing.assert_allclose(cols["def"], dspread[skip:], atol=1e-12)
    np.testing.assert_allclose(cols["comm"], comm[skip:], atol=1e-12)
    np.testing.assert_allclose(cols["infl"], infl[skip:], atol=1e-12)
    np.testing.assert_allclose(cols["usd"], usd[skip:], atol=1e-12)
    assert design.usd_lag is not None
    np.testing.assert_allclose(design.usd_lag, usd[:-1], atol=1e-12)


# --------------------------------------------------------------------------- lag-sum SE
def test_summed_dollar_se_is_the_hac_covariance_formula() -> None:
    case = make_macro_case(8104, n=1500)
    design, fit = run_case(case)
    usd = next(r for r in fit.rows if r.code == "usd")
    assert design.usd_lag is not None
    x = np.column_stack([design.x, design.usd_lag])
    ols = ols_hac(design.y, x)
    u, lag = 1 + design.codes.index("usd"), 1 + len(design.codes)
    v = ols.cov
    expected = math.sqrt(v[u, u] + v[lag, lag] + 2.0 * v[u, lag])
    assert usd.se == pytest.approx(expected, rel=1e-12)
    assert usd.beta == pytest.approx(ols.params[u] + ols.params[lag], rel=1e-12)
    assert usd.beta_same_day == pytest.approx(ols.params[u]) and usd.beta_lag == pytest.approx(
        ols.params[lag]
    )
    assert usd.t == pytest.approx(usd.beta / usd.se)
    # The cross term matters: leaving it out gives a different standard error.
    assert abs(math.sqrt(v[u, u] + v[lag, lag]) - usd.se) > 1e-9 * usd.se


def test_summed_beta_helper_on_a_hand_checked_covariance() -> None:
    params = np.array([0.0, 2.0, 3.0])
    cov = np.array([[1.0, 0.0, 0.0], [0.0, 4.0, 1.0], [0.0, 1.0, 9.0]])
    beta, se = summed_beta(params, cov, 1, 2)
    assert beta == 5.0 and se == pytest.approx(math.sqrt(4 + 9 + 2))


def test_without_the_dollar_there_is_no_lag_term_and_no_usd_row() -> None:
    design, fit = run_case(make_macro_case(8105, n=900), with_dollar=False)
    assert design.usd_lag is None and "usd" not in design.codes
    assert [r.code for r in fit.rows] == ["mkt_rf", "term", "def", "comm", "infl"]
    assert design.n == 900


# ------------------------------------------------------------------------------------ VIF
def test_every_row_has_a_vif_and_a_correlation_matrix_comes_with_it() -> None:
    _, fit = run_case(make_macro_case(8106))
    for row in fit.rows:
        assert math.isfinite(row.vif) and row.vif >= 1.0
    by = {r.code: r.vif for r in fit.rows}
    assert by["term"] > by["comm"] > 0.99 or by["def"] > by["comm"]  # TERM/DEF are correlated
    k = len(fit.codes)
    assert fit.correlation.shape == (k, k)
    np.testing.assert_allclose(np.diag(fit.correlation), 1.0)
    assert fit.correlation[1, 2] > 0.3  # TERM and DEF, built correlated


def test_vif_matches_the_existing_collinearity_code() -> None:
    from factordesk.analytics.regression import collinearity

    design, fit = run_case(make_macro_case(8107, n=600))
    ref = collinearity(design.x, [f.name for f in FACTORS])
    for row, f in zip(fit.rows, FACTORS, strict=True):
        assert row.vif == pytest.approx(ref.vif[f.name], rel=1e-12)


# ---------------------------------------------------------------------- leg returns (daily)
def test_daily_leg_return_needs_the_same_previous_date() -> None:
    cal = pd.bdate_range("2020-01-01", periods=8)
    lv = pd.Series(100.0 * 1.01 ** np.arange(8), index=cal)
    lv = lv.drop(cal[3])  # the leg has no row for the 4th day
    ret = daily_leg_returns(lv, pd.DatetimeIndex(cal))
    assert list(ret.index) == list(cal[1:])
    assert math.isnan(ret[cal[3]])  # no price that day
    assert math.isnan(ret[cal[4]])  # its previous row is two days back: not the same interval
    assert ret[cal[2]] == pytest.approx(0.01) and ret[cal[5]] == pytest.approx(0.01)


# ----------------------------------------------------------------------- monthly compounding
def _daily_levels(first: str, last: str, seed: int) -> tuple[pd.Series, pd.Series]:
    days = pd.bdate_range(first, last)
    r = np.random.default_rng(seed).normal(0.0003, 0.004, size=len(days) - 1)
    lv = pd.Series(100.0 * np.concatenate([[1.0], np.cumprod(1.0 + r)]), index=days)
    return lv, pd.Series(r, index=days[1:])


def test_monthly_leg_return_is_the_product_of_its_daily_returns() -> None:
    lv, daily = _daily_levels("2019-12-27", "2021-06-30", 5)  # starts in a partial month
    month_ends = pd.date_range("2020-01-31", "2021-06-30", freq="ME")
    monthly = monthly_leg_returns(lv, month_ends)
    by_month = (1.0 + daily).groupby(pd.DatetimeIndex(daily.index).to_period("M")).prod() - 1.0
    for stamp in month_ends:
        assert monthly[stamp] == pytest.approx(by_month[stamp.to_period("M")], rel=1e-9)
    # December 2019 is only partly in the history, so it has no return; January 2020 does.
    assert math.isnan(monthly_leg_returns(lv, pd.DatetimeIndex(["2019-12-31"])).iloc[0])


def test_a_missing_month_gives_nan_for_it_and_the_next_month() -> None:
    lv, _ = _daily_levels("2020-01-01", "2020-06-30", 6)
    lv = lv[(lv.index < "2020-03-01") | (lv.index > "2020-03-31")]  # no March prices
    month_ends = pd.date_range("2020-02-29", "2020-06-30", freq="ME")
    ret = monthly_leg_returns(lv, month_ends)
    assert ret[pd.Timestamp("2020-02-29")] == ret[pd.Timestamp("2020-02-29")]  # finite
    assert math.isnan(ret[pd.Timestamp("2020-03-31")])
    assert math.isnan(ret[pd.Timestamp("2020-04-30")])  # the previous month has no level
    assert math.isfinite(ret[pd.Timestamp("2020-05-31")])


def test_monthly_spreads_are_taken_after_compounding() -> None:
    n = 120
    returns, factors, _ = monthly_case(n, 31, start="2005-01-31")
    month_ends = pd.DatetimeIndex(returns.index)
    days = pd.bdate_range("2004-12-01", month_ends[-1])
    rng = np.random.default_rng(32)
    daily: dict[str, pd.Series] = {}
    levels: dict[str, pd.Series] = {}
    for t in LEG_TICKERS:
        r = rng.normal(0.0002, 0.003, size=len(days) - 1)
        levels[t] = pd.Series(100.0 * np.concatenate([[1.0], np.cumprod(1.0 + r)]), index=days)
        daily[t] = pd.Series(r, index=days[1:])

    def comp(t: str) -> pd.Series:
        s = (1.0 + daily[t]).groupby(pd.DatetimeIndex(daily[t].index).to_period("M")).prod() - 1.0
        return pd.Series(s.reindex(month_ends.to_period("M")).to_numpy(), index=month_ends)

    subject = subject_from_monthly_returns(returns, label="Fund")
    sample = build_subject_sample(subject, factors)
    design = build_design(sample, subject.calendar, levels, None)
    assert design.usd_lag is None and design.frequency == "monthly"
    rf = sample.rf
    cols = dict(zip(design.codes, design.x.T, strict=True))
    np.testing.assert_allclose(cols["term"], (comp("IEF") - rf).to_numpy()[-design.n :], atol=1e-12)
    np.testing.assert_allclose(
        cols["def"], (comp("LQD") - comp("IEF")).to_numpy()[-design.n :], atol=1e-12
    )
    np.testing.assert_allclose(
        cols["infl"], (comp("TIP") - comp("IEI")).to_numpy()[-design.n :], atol=1e-12
    )
    # The spread of compounded returns is not the compounded spread of daily returns.
    daily_spread = (1.0 + (daily["LQD"] - daily["IEF"])).groupby(
        pd.DatetimeIndex(daily["LQD"].index).to_period("M")
    ).prod() - 1.0
    assert not np.allclose(
        cols["def"], daily_spread.reindex(month_ends.to_period("M")).to_numpy()[-design.n :]
    )


def test_a_monthly_subject_uses_student_t_and_no_lag_term() -> None:
    n = 120
    returns, factors, _ = monthly_case(n, 33, start="2005-01-31")
    month_ends = pd.DatetimeIndex(returns.index)
    days = pd.bdate_range("2004-12-01", month_ends[-1])
    rng = np.random.default_rng(34)
    levels = {
        t: pd.Series(
            100.0
            * np.concatenate([[1.0], np.cumprod(1.0 + rng.normal(0.0002, 0.003, len(days) - 1))]),
            index=days,
        )
        for t in LEG_TICKERS
    }
    dollar = pd.Series(
        100.0 * np.concatenate([[1.0], np.cumprod(1.0 + rng.normal(0.0, 0.002, len(days) - 1))]),
        index=days,
    )
    subject = subject_from_monthly_returns(returns, label="Fund")
    report = assemble_subject_report(
        subject,
        factors,
        now=NOW,
        factors_downloaded_at=None,
        section_inputs=SectionInputs(
            macro=MacroInput(
                funds={t: WorldBenchmarkInput(history=_history(t, lv)) for t, lv in levels.items()},
                dollar=DollarInput(levels=dollar),
            )
        ),
    )
    macro = report.macro
    assert macro is not None and macro.status == "ok" and macro.frequency == "monthly"
    assert macro.t_reference == "student_t" and macro.usd_lag_note is None
    assert all(r.beta_lag is None and r.beta_same_day is None for r in macro.rows)
    assert [r.code for r in macro.rows][-1] == "usd"
    assert macro.n_obs == n  # window: every month has all legs (legs start before the subject)
    # The Student-t p-value is wider than the normal one for the same t.
    normal = NormalDist()
    for r in macro.rows:
        assert r.p >= 2.0 * (1.0 - normal.cdf(abs(r.t))) - 1e-12


def _history(ticker: str, levels: pd.Series) -> PriceHistory:
    frame = pd.DataFrame(
        {
            "close": levels.to_numpy(),
            "adj_close": levels.to_numpy(),
            "dividends": 0.0,
            "splits": 0.0,
        },
        index=pd.DatetimeIndex(levels.index, name="date"),
    )
    return PriceHistory(ticker, frame, NOW, "synthetic")


# ------------------------------------------------------------------------------- FRED parse
CSV = "observation_date,DTWEXBGS\n2024-01-02,120.5\n2024-01-03,.\n2024-01-04,121.0\n2024-01-05,\n"


def test_fred_dot_and_empty_cells_are_nan() -> None:
    s = parse_fred_csv(CSV, "DTWEXBGS")
    assert list(s.index) == list(
        pd.to_datetime(["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"])
    )
    assert s.iloc[0] == 120.5 and s.iloc[2] == 121.0
    assert math.isnan(s.iloc[1]) and math.isnan(s.iloc[3])
    assert s.dtype == "float64"


def test_fred_old_date_header_still_parses() -> None:
    s = parse_fred_csv("DATE,DTWEXBGS\n2024-01-02,100.0\n", "DTWEXBGS")
    assert len(s) == 1


@pytest.mark.parametrize(
    "text",
    [
        "<html><body>Service unavailable</body></html>",
        "observation_date,OTHER\n2024-01-02,1.0\n",
        "observation_date,DTWEXBGS\n2024-01-02,.\n",
        "observation_date,DTWEXBGS\n2024-01-03,1.0\n2024-01-02,1.0\n",
        "observation_date,DTWEXBGS\nnot a date,1.0\n",
        "observation_date,DTWEXBGS\n2024-01-02,abc\n",
        "",
    ],
)
def test_fred_bad_files_raise(text: str) -> None:
    with pytest.raises(FredError):
        parse_fred_csv(text, "DTWEXBGS")


def test_fred_is_cached_per_day(tmp_path: Path) -> None:
    calls: list[str] = []

    def fetch(series: str) -> str:
        calls.append(series)
        return CSV

    first = load_fred_series(data_dir=tmp_path, now=NOW, fetch=fetch)
    second = load_fred_series(data_dir=tmp_path, now=NOW, fetch=fetch)
    assert calls == ["DTWEXBGS"] and first.note is None
    pd.testing.assert_series_equal(first.values, second.values)
    assert (tmp_path / "fred" / "DTWEXBGS_2026-11-19.csv").is_file()


def test_fred_failure_falls_back_to_an_older_cache_then_raises(tmp_path: Path) -> None:
    def boom(series: str) -> str:
        raise FredError("network error")

    with pytest.raises(FredError, match="network error"):
        load_fred_series(data_dir=tmp_path, now=NOW, fetch=boom)
    load_fred_series(data_dir=tmp_path, now=datetime(2026, 11, 18, tzinfo=UTC), fetch=lambda s: CSV)
    old = load_fred_series(data_dir=tmp_path, now=NOW, fetch=boom)
    assert old.note is not None and "2026-11-18" in old.note
    assert len(old.values) == 4


def test_fred_rejects_a_series_id_that_is_not_an_id(tmp_path: Path) -> None:
    with pytest.raises(FredError):
        load_fred_series("../x", data_dir=tmp_path, now=NOW, fetch=lambda s: CSV)


def test_load_dollar_never_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import factordesk.section_hooks.macro as hook

    def unreachable(*args: object, **kwargs: object) -> None:
        raise FredError("DTWEXBGS: download failed after 2 attempts (network error)")

    monkeypatch.setattr(hook, "load_fred_series", unreachable)
    got = load_dollar(data_dir=tmp_path, now=NOW)
    assert got.levels is None and got.unavailable_reason is not None

    def odd(*args: object, **kwargs: object) -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr(hook, "load_fred_series", odd)
    assert load_dollar(data_dir=tmp_path, now=NOW).levels is None


# ------------------------------------------------------------------------- hook and report
def test_the_hook_is_registered_for_every_source_frequency_and_model() -> None:
    spec = next(s for s in HOOKS if s.field == "macro")
    for kind in ("ticker", "upload", "portfolio"):
        for freq in ("daily", "monthly"):
            for model in ("ff5", "ff6"):
                assert spec.applies(kind, freq, model)  # pyright: ignore[reportArgumentType]


def test_a_report_without_the_input_has_no_macro_key() -> None:
    case = make_macro_case(8111, n=600)
    report = report_of(case, None)
    assert report.macro is None
    assert "macro" not in json.loads(report.model_dump_json())


def test_the_daily_section_reports_betas_window_vif_and_the_note() -> None:
    case = make_macro_case(8112, n=1200)
    report = report_of(case, SectionInputs(macro=macro_input(case)))
    s = report.macro
    assert s is not None and s.status == "ok" and s.reason is None
    assert (
        s.model_note
        == MODEL_NOTE
        == (
            "Separate regression. Raw betas: correlated factors share explanatory power. "
            "Not the headline alpha."
        )
    )
    assert s.frequency == "daily" and s.t_reference == "normal" and s.usd_included
    assert s.usd_note is None and s.usd_lag_note is not None
    assert [r.label for r in s.rows] == [
        "Market",
        "Rates",
        "Credit",
        "Commodities",
        "Inflation",
        "US dollar",
    ]
    assert s.rows[2].note == "credit minus rates, not duration-matched"
    assert s.rows[4].note == "breakeven proxy"
    assert all(r.vif >= 1.0 for r in s.rows)
    assert s.correlation_codes == [r.code for r in s.rows]
    assert len(s.correlation) == 6 and all(len(row) == 6 for row in s.correlation)
    assert s.n_obs == 1199 and s.sample.n == 1199 and s.n_sample == 1200
    assert s.sample.start is not None and s.sample.end is not None
    assert s.r2 is not None and s.adj_r2 is not None and s.adj_r2 <= s.r2
    assert {leg.ticker for leg in s.legs} == {*LEG_TICKERS, DOLLAR_SERIES}
    assert all(leg.first_date == date(2009, 12, 31) for leg in s.legs)
    # The report round-trips through JSON and the section is written.
    again = FactorReport.model_validate_json(report.model_dump_json())
    assert again.macro == s


def test_the_window_starts_at_the_latest_first_date_of_the_legs() -> None:
    case = make_macro_case(8113, n=1000)
    late = case.dates[300]
    tip = price_history(
        case.funds["TIP"].total_returns.to_numpy()[300:], case.dates[300:], case.dates[299], "TIP"
    )
    funds = {**case.funds, "TIP": tip}
    inputs = MacroInput(
        funds={t: WorldBenchmarkInput(history=h) for t, h in funds.items()},
        dollar=DollarInput(levels=case.dollar),
    )
    s = report_of(case, SectionInputs(macro=inputs)).macro
    assert s is not None and s.status == "ok"
    assert s.sample.start == late.date() and s.window_limited_by == "TIP"
    assert s.n_obs == 700 and s.n_sample == 1000
    first = {leg.ticker: leg.first_date for leg in s.legs}
    assert first["TIP"] == case.dates[299].date() and first["IEF"] == date(2009, 12, 31)


def test_an_unavailable_dollar_index_gives_a_section_without_usd() -> None:
    case = make_macro_case(8114, n=900)
    inputs = macro_input(case, dollar=DollarInput(levels=None, unavailable_reason="network error"))
    s = report_of(case, SectionInputs(macro=inputs)).macro
    assert s is not None and s.status == "ok"
    assert s.usd_included is False and s.usd_note == USD_UNAVAILABLE == "dollar index unavailable"
    assert [r.code for r in s.rows] == ["mkt_rf", "term", "def", "comm", "infl"]
    assert s.usd_lag_note is None and s.n_obs == 900
    assert all(leg.ticker != DOLLAR_SERIES for leg in s.legs)


def test_a_stale_dollar_copy_is_noted_but_used() -> None:
    case = make_macro_case(8115, n=900)
    inputs = macro_input(
        case, dollar=DollarInput(levels=case.dollar, note="used the copy of 2026-11-18")
    )
    s = report_of(case, SectionInputs(macro=inputs)).macro
    assert s is not None and s.usd_included and s.usd_note == "used the copy of 2026-11-18"


def test_a_fund_that_cannot_be_fetched_fails_the_section_with_its_name() -> None:
    case = make_macro_case(8116, n=900)
    funds = {t: WorldBenchmarkInput(history=h) for t, h in case.funds.items()}
    funds["DBC"] = WorldBenchmarkInput(history=None, unavailable_reason="rate limited")
    funds["TIP"] = WorldBenchmarkInput(history=None, unavailable_reason="rate limited")
    s = report_of(
        case, SectionInputs(macro=MacroInput(funds=funds, dollar=DollarInput(levels=case.dollar)))
    ).macro
    assert s is not None and s.status == "failed" and s.rows == []
    assert s.reason == FUNDS_UNAVAILABLE.format(funds="DBC, TIP")


def test_too_few_common_rows_is_insufficient_data() -> None:
    case = make_macro_case(8117, n=700)
    cut = 700 - 200
    short = {
        t: price_history(h.total_returns.to_numpy()[cut:], case.dates[cut:], case.dates[cut - 1], t)
        for t, h in case.funds.items()
    }
    inputs = MacroInput(
        funds={t: WorldBenchmarkInput(history=h) for t, h in short.items()},
        dollar=DollarInput(levels=case.dollar),
    )
    s = report_of(case, SectionInputs(macro=inputs)).macro
    assert s is not None and s.status == "insufficient_data" and s.rows == []
    assert str(MIN_ROWS["daily"]) in (s.reason or "")
    with pytest.raises(TooFewRowsError):
        sample = build_sample(case.stock, case.factors)
        run_macro(
            sample,
            pd.DatetimeIndex(case.stock.frame.index),
            {t: h.frame["adj_close"] for t, h in short.items()},
            case.dollar,
        )


def test_a_constant_fund_fails_the_section_with_a_reason() -> None:
    case = make_macro_case(8118, n=700)
    flat = price_history(np.zeros(700), case.dates, ticker="IEI")
    funds = {t: WorldBenchmarkInput(history=h) for t, h in case.funds.items()}
    funds["IEF"] = WorldBenchmarkInput(history=price_history(case.rf, case.dates, ticker="IEF"))
    funds["IEI"] = WorldBenchmarkInput(history=flat)
    funds["TIP"] = WorldBenchmarkInput(
        history=price_history(np.zeros(700), case.dates, ticker="TIP")
    )
    s = report_of(
        case, SectionInputs(macro=MacroInput(funds=funds, dollar=DollarInput(levels=case.dollar)))
    ).macro
    assert s is not None and s.status == "failed" and s.reason is not None
    assert s.rows == [] and s.r2 is None


def test_ticker_subject_and_plain_returns_give_the_same_section() -> None:
    case = make_macro_case(8119, n=900)
    inputs = SectionInputs(macro=macro_input(case))
    a = report_of(case, inputs).macro
    subject = subject_from_history(case.stock)
    b = assemble_subject_report(
        subject, case.factors, now=NOW, factors_downloaded_at=None, section_inputs=inputs
    ).macro
    assert a == b and a is not None


def test_fit_macro_is_deterministic_and_does_not_mutate_inputs() -> None:
    case = make_macro_case(8120, n=800)
    sample = build_sample(case.stock, case.factors)
    design = build_design(
        sample, pd.DatetimeIndex(case.stock.frame.index), levels_of(case), case.dollar
    )
    x_before = design.x.copy()
    a, b = fit_macro(design), fit_macro(design)
    assert a.rows == b.rows and a.r2 == b.r2 and a.lags == b.lags
    np.testing.assert_array_equal(a.correlation, b.correlation)
    np.testing.assert_array_equal(design.x, x_before)


if __name__ == "__main__":  # regenerate the shared fixture
    c = make_macro_case(8199, n=720)
    r = report_of(c, SectionInputs(macro=macro_input(c)))
    assert r.macro is not None
    FIXTURE.write_text(
        json.dumps(r.macro.model_dump(mode="json"), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {FIXTURE}")
