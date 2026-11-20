"""EUR overnight rate, EUR cash returns and FX returns (no network: downloads are replaced)."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from factordesk.data.ecb import EcbError, load_ecb_series
from factordesk.data.fx import (
    FRED_QUOTES,
    SOURCE_ECB,
    SOURCE_FRED,
    FxResult,
    credit,
    fx_returns,
)
from factordesk.data.rates import (
    FRED_CREDIT,
    FRED_ESTR_SERIES,
    cash_returns,
    load_eur_overnight,
)

NOW = datetime(2026, 11, 20, 12, 0, tzinfo=UTC)
LATER = datetime(2026, 11, 21, 12, 0, tzinfo=UTC)
TOL = 1e-12


def ecb_csv(values: dict[str, float]) -> str:
    rows = "\n".join(f"K,{d},{v}" for d, v in values.items())
    return f"KEY,TIME_PERIOD,OBS_VALUE\n{rows}\n"


def fred_csv(series_id: str, values: dict[str, float | None]) -> str:
    rows = "\n".join(f"{d},{'.' if v is None else v}" for d, v in values.items())
    return f"observation_date,{series_id}\n{rows}\n"


def down(*_args: str) -> str:
    raise EcbError("simulated outage")


def day_index(*days: str) -> pd.DatetimeIndex:
    return pd.DatetimeIndex(pd.to_datetime(list(days)))


def rate_series(values: dict[str, float]) -> pd.Series:
    return pd.Series(values, dtype="float64").rename(index=pd.Timestamp)


# ---------------------------------------------------------------- EUR overnight rate


def test_splice_uses_eonia_before_october_2019_and_estr_from_then(tmp_path: Path) -> None:
    eonia = ecb_csv({"2019-09-27": -0.452, "2019-09-30": -0.451, "2019-10-01": -0.464})
    estr = ecb_csv({"2019-09-30": -9.0, "2019-10-01": -0.549, "2019-10-02": -0.551})

    def fetch(flow: str, key: str) -> str:
        return eonia if flow == "EON" else estr

    res = load_eur_overnight(data_dir=tmp_path, now=NOW, fetch_ecb=fetch)
    assert res.rate is not None and res.notice is None
    assert res.credit is not None and "ECB Data Portal" in res.credit
    expected = {
        "2019-09-27": -0.00452,  # EONIA, percent turned into a decimal, no spread
        "2019-09-30": -0.00451,
        "2019-10-01": -0.00549,  # euro STR replaces EONIA on the splice date
        "2019-10-02": -0.00551,
    }
    assert list(res.rate.index) == [pd.Timestamp(d) for d in expected]
    np.testing.assert_allclose(res.rate.to_numpy(), list(expected.values()), rtol=0, atol=TOL)


def test_cash_accrues_act_360_over_a_weekend() -> None:
    rate = rate_series({"2024-03-07": 0.04, "2024-03-08": 0.02, "2024-03-11": 0.03})
    ret = cash_returns(rate, day_index("2024-03-08", "2024-03-11"))
    # The Friday rate runs Friday to Monday: 3 calendar days.
    assert ret.iloc[0] == pytest.approx(0.02 * 3 / 360, abs=TOL)
    assert ret.index[0] == pd.Timestamp("2024-03-11")


def test_cash_compounds_each_business_day_across_a_gap() -> None:
    rate = rate_series({"2024-03-07": 0.01, "2024-03-08": 0.02, "2024-03-11": 0.03})
    # Dates skip Friday and Monday (a holiday gap): Thursday -> Tuesday, 5 calendar days.
    ret = cash_returns(rate, day_index("2024-03-07", "2024-03-12"))
    expected = (1 + 0.01 / 360) * (1 + 0.02 * 3 / 360) * (1 + 0.03 * 1 / 360) - 1
    assert ret.iloc[0] == pytest.approx(expected, abs=TOL)
    # Splitting the gap in two steps gives the same compounded growth.
    two = cash_returns(rate, day_index("2024-03-07", "2024-03-08", "2024-03-12"))
    assert (1 + two).prod() - 1 == pytest.approx(expected, abs=TOL)


def test_cash_is_nan_outside_the_rate_window() -> None:
    rate = rate_series({"2024-03-07": 0.01, "2024-03-08": 0.02})
    ret = cash_returns(rate, day_index("2024-03-05", "2024-03-07", "2024-03-12", "2024-03-20"))
    assert np.isnan(ret.iloc[0])  # starts before the first rate date
    assert ret.iloc[1] == pytest.approx((1 + 0.01 / 360) * (1 + 0.02 * 4 / 360) - 1, abs=TOL)
    assert np.isnan(ret.iloc[2])  # ends more than 5 days after the last rate date


def test_overnight_falls_back_to_fred_with_a_notice(tmp_path: Path) -> None:
    fred = fred_csv(
        FRED_ESTR_SERIES, {"2019-10-01": -0.549, "2019-10-02": None, "2019-10-03": -0.55}
    )

    def fetch_fred(series_id: str) -> str:
        assert series_id == FRED_ESTR_SERIES
        return fred

    res = load_eur_overnight(data_dir=tmp_path, now=NOW, fetch_ecb=down, fetch_fred=fetch_fred)
    assert res.rate is not None
    assert res.credit == FRED_CREDIT
    assert res.notice is not None and "FRED" in res.notice and "2019-10-01" in res.notice
    assert list(res.rate.index) == [pd.Timestamp("2019-10-01"), pd.Timestamp("2019-10-03")]
    assert res.rate.iloc[0] == pytest.approx(-0.00549, abs=TOL)


def test_overnight_returns_none_and_a_notice_when_every_source_is_down(tmp_path: Path) -> None:
    def fred_down(_series_id: str) -> str:
        raise OSError("no network")

    res = load_eur_overnight(data_dir=tmp_path, now=NOW, fetch_ecb=down, fetch_fred=fred_down)
    assert res.rate is None and res.credit is None
    assert res.notice is not None and "unavailable" in res.notice


def test_overnight_without_eonia_starts_at_the_splice_date(tmp_path: Path) -> None:
    estr = ecb_csv({"2019-09-30": -9.0, "2019-10-01": -0.549})

    def fetch(flow: str, key: str) -> str:
        if flow == "EON":
            raise EcbError("simulated outage")
        return estr

    res = load_eur_overnight(data_dir=tmp_path, now=NOW, fetch_ecb=fetch)
    assert res.rate is not None and res.notice is not None and "EONIA" in res.notice
    assert list(res.rate.index) == [pd.Timestamp("2019-10-01")]


def test_ecb_cache_is_reused_within_a_day_and_old_copy_serves_an_outage(tmp_path: Path) -> None:
    calls: list[str] = []

    def fetch(flow: str, key: str) -> str:
        calls.append(key)
        return ecb_csv({"2024-01-02": 3.9})

    first, note1 = load_ecb_series(
        "EST", "B.X", scale=0.01, data_dir=tmp_path, now=NOW, fetch=fetch
    )
    again, note2 = load_ecb_series("EST", "B.X", scale=0.01, data_dir=tmp_path, now=NOW, fetch=down)
    assert calls == ["B.X"] and note1 is None and note2 is None  # second call hit the cache
    assert first.iloc[0] == pytest.approx(0.039, abs=TOL) and again.equals(first)
    # Next day, the download fails: the old copy is used and the notice says so.
    old, note3 = load_ecb_series("EST", "B.X", scale=0.01, data_dir=tmp_path, now=LATER, fetch=down)
    assert old.equals(first)
    assert note3 is not None and "2026-11-20" in note3
    # No cache at all: the error is raised.
    with pytest.raises(EcbError):
        load_ecb_series("EST", "B.Y", data_dir=tmp_path, now=LATER, fetch=down)


# ---------------------------------------------------------------- FX returns

DATES = day_index("2024-04-29", "2024-04-30", "2024-05-01", "2024-05-02", "2024-05-03")


def ecb_fetcher(per_eur: dict[str, dict[str, float]]) -> Callable[[str, str], str]:
    """A fake ECB download: ``per_eur[ccy][date]`` is units of ccy per 1 EUR."""

    def fetch(flow: str, key: str) -> str:
        assert flow == "EXR"
        return ecb_csv(per_eur[key.split(".")[1]])

    return fetch


def fred_fetcher(table: dict[str, dict[str, float | None]]) -> Callable[[str], str]:
    def fetch(series_id: str) -> str:
        return fred_csv(series_id, table[series_id])

    return fetch


def test_ecb_quote_direction_and_target_holiday_carry(tmp_path: Path) -> None:
    # 2024-05-01 is a TARGET holiday: the ECB publishes no rate that day.
    usd = {"2024-04-29": 1.07, "2024-04-30": 1.08, "2024-05-02": 1.10, "2024-05-03": 1.09}
    jpy = {"2024-04-29": 166.0, "2024-04-30": 168.0, "2024-05-02": 170.0, "2024-05-03": 169.0}
    fetch = ecb_fetcher({"USD": usd, "JPY": jpy})
    eur_usd = fx_returns("EUR", "USD", DATES, data_dir=tmp_path, now=NOW, fetch_ecb=fetch)
    assert eur_usd.source == SOURCE_ECB and eur_usd.notice is None and eur_usd.series is not None
    # EUR in USD = the ECB quote (USD per EUR) itself.
    expected = [1.08 / 1.07, 1.08 / 1.08, 1.10 / 1.08, 1.09 / 1.10]
    np.testing.assert_allclose(eur_usd.series.to_numpy(), np.array(expected) - 1, rtol=0, atol=TOL)
    # Holiday carry: the return on 2024-05-01 is exactly 0.
    assert eur_usd.series[pd.Timestamp("2024-05-01")] == 0.0
    # JPY is quoted per EUR, so JPY in EUR = 1 / quote (the opposite direction).
    jpy_eur = fx_returns("JPY", "EUR", DATES, data_dir=tmp_path, now=NOW, fetch_ecb=fetch)
    assert jpy_eur.series is not None
    expected = [(1 / 168) / (1 / 166), 1.0, (1 / 170) / (1 / 168), (1 / 169) / (1 / 170)]
    np.testing.assert_allclose(jpy_eur.series.to_numpy(), np.array(expected) - 1, rtol=0, atol=TOL)


def test_ecb_cross_rate_equals_the_ratio_of_the_two_legs(tmp_path: Path) -> None:
    usd = {
        d: 1.05 + 0.01 * i
        for i, d in enumerate(["2024-04-29", "2024-04-30", "2024-05-02", "2024-05-03"])
    }
    gbp = {d: 0.85 - 0.004 * i for i, d in enumerate(usd)}
    fetch = ecb_fetcher({"USD": usd, "GBP": gbp})

    def run(ccy: str, ref: str) -> FxResult:
        return fx_returns(ccy, ref, DATES, data_dir=tmp_path, now=NOW, fetch_ecb=fetch)

    gbp_usd = run("GBP", "USD").series
    eur_usd = run("EUR", "USD").series
    gbp_eur = run("GBP", "EUR").series
    assert gbp_usd is not None and eur_usd is not None and gbp_eur is not None
    # GBP in USD = (GBP in EUR) x (EUR in USD), so the growth factors multiply.
    np.testing.assert_allclose(
        (1 + gbp_usd).to_numpy(), ((1 + gbp_eur) * (1 + eur_usd)).to_numpy(), rtol=0, atol=TOL
    )
    # And the ECB-quoted value: GBP/USD = USD per EUR / GBP per EUR.
    level = pd.Series(usd).rename(index=pd.Timestamp) / pd.Series(gbp).rename(index=pd.Timestamp)
    assert (1 + gbp_usd[pd.Timestamp("2024-04-30")]) == pytest.approx(
        level[pd.Timestamp("2024-04-30")] / level[pd.Timestamp("2024-04-29")], abs=TOL
    )


def test_same_currency_is_identity_and_needs_no_download(tmp_path: Path) -> None:
    for ccy in ("USD", "EUR", "gbp"):
        res = fx_returns(ccy, ccy, DATES, data_dir=tmp_path, now=NOW, fetch_ecb=down)
        assert res.series is not None and res.notice is None
        assert (res.series == 0.0).all() and len(res.series) == len(DATES) - 1


def test_unsupported_currency_gives_a_notice(tmp_path: Path) -> None:
    res = fx_returns("XYZ", "USD", DATES, data_dir=tmp_path, now=NOW, fetch_ecb=down)
    assert res.series is None and res.notice is not None and "XYZ" in res.notice


def test_fallback_to_fred_names_the_source_and_respects_quote_direction(tmp_path: Path) -> None:
    table: dict[str, dict[str, float | None]] = {
        "DEXUSEU": {
            "2024-04-29": 1.07,
            "2024-04-30": 1.08,
            "2024-05-01": 1.09,
            "2024-05-02": 1.10,
            "2024-05-03": 1.09,
        },
        "DEXUSUK": {
            "2024-04-29": 1.25,
            "2024-04-30": 1.26,
            "2024-05-01": 1.27,
            "2024-05-02": 1.25,
            "2024-05-03": 1.24,
        },
        # US holiday-style gap: no fixing on 2024-05-01 (carried forward).
        "DEXJPUS": {
            "2024-04-29": 157.0,
            "2024-04-30": 158.0,
            "2024-05-01": None,
            "2024-05-02": 153.0,
            "2024-05-03": 154.0,
        },
    }
    assert FRED_QUOTES["EUR"][1] == "usd_per_unit" and FRED_QUOTES["JPY"][1] == "units_per_usd"
    fred = fred_fetcher(table)

    def run(ccy: str, ref: str) -> FxResult:
        return fx_returns(
            ccy, ref, DATES, data_dir=tmp_path, now=NOW, fetch_ecb=down, fetch_fred=fred
        )

    eur = run("EUR", "USD")  # a USD-per-unit series
    assert eur.source == SOURCE_FRED and eur.series is not None
    assert eur.notice is not None and SOURCE_FRED in eur.notice and "ECB" in eur.notice
    assert credit(eur.source) is not None and "H.10" in (credit(eur.source) or "")
    np.testing.assert_allclose(
        eur.series.to_numpy(),
        [1.08 / 1.07 - 1, 1.09 / 1.08 - 1, 1.10 / 1.09 - 1, 1.09 / 1.10 - 1],
        rtol=0,
        atol=TOL,
    )
    jpy = run("JPY", "USD")  # a units-per-USD series: inverted
    assert jpy.series is not None
    # Holiday: the previous fixing (158) is carried, so 2024-05-01 is 0 and 2024-05-02 moves.
    np.testing.assert_allclose(
        jpy.series.to_numpy(),
        [157 / 158 - 1, 0.0, 158 / 153 - 1, 153 / 154 - 1],
        rtol=0,
        atol=TOL,
    )
    # Cross rate through USD: GBP in EUR = (1 + GBP in USD) / (1 + EUR in USD) - 1.
    gbp_usd = run("GBP", "USD").series
    gbp_eur = run("GBP", "EUR").series
    assert gbp_usd is not None and gbp_eur is not None and eur.series is not None
    np.testing.assert_allclose(
        (1 + gbp_eur).to_numpy(), ((1 + gbp_usd) / (1 + eur.series)).to_numpy(), rtol=0, atol=TOL
    )


def test_fx_returns_none_and_a_notice_when_both_sources_are_down(tmp_path: Path) -> None:
    def fred_down(_series_id: str) -> str:
        raise OSError("no network")

    res = fx_returns(
        "GBP", "EUR", DATES, data_dir=tmp_path, now=NOW, fetch_ecb=down, fetch_fred=fred_down
    )
    assert res.series is None and res.source is None
    assert res.notice is not None and "unavailable" in res.notice


def test_fx_downloads_once_per_day_per_series(tmp_path: Path) -> None:
    calls: list[str] = []
    usd = {"2024-04-29": 1.07, "2024-04-30": 1.08, "2024-05-02": 1.10}
    inner = ecb_fetcher({"USD": usd})

    def fetch(flow: str, key: str) -> str:
        calls.append(key)
        return inner(flow, key)

    results = [
        fx_returns("EUR", "USD", DATES, data_dir=tmp_path, now=NOW, fetch_ecb=fetch)
        for _ in range(3)
    ]
    assert calls == ["D.USD.EUR.SP00.A"]
    last = results[-1].series
    assert last is not None and not np.isnan(last.to_numpy()[1:]).any()
