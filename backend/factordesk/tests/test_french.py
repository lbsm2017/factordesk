"""Generic Ken French loader (``data/french.py``): monthly parser, compounding check, cache.

Offline: the French rows come from the verbatim excerpts in ``fixtures/french_excerpt.py``.
"""

from __future__ import annotations

import dataclasses
import io
import zipfile
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from factordesk.data import french
from factordesk.data.factors import FactorDataError, FactorDownloadError, parse_french_csv
from factordesk.data.french import DATASETS, FrenchDataset, load_french, parse_french_block
from factordesk.tests.fixtures.french_excerpt import FF5_DAILY_2020Q2, FF5_MONTHLY_2020

FF5_MONTHLY = DATASETS["ff5_monthly"]
NOW = datetime(2021, 1, 20, 12, 0, tzinfo=UTC)
BP = 1e-4


def _monthly(text: str = FF5_MONTHLY_2020, today: date | None = None) -> pd.DataFrame:
    return parse_french_block(text.encode("latin-1"), FF5_MONTHLY, min_rows=1, today=today)


def _zip(text: str, name: str = "F-F_Research_Data_5_Factors_2x3.csv") -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(name, text.encode("latin-1"))
    return buf.getvalue()


# ----------------------------------------------------------------------------- parser
def test_monthly_block_is_read_and_the_annual_block_skipped() -> None:
    frame = _monthly()
    assert list(frame.columns) == ["Mkt-RF", "SMB", "HML", "RMW", "CMA", "RF"]
    assert len(frame) == 12  # the annual rows 2019 and 2020 are not read
    expected_index = pd.date_range("2020-01-31", periods=12, freq="ME", name="date")
    assert list(frame.index) == list(expected_index)
    assert frame.index.name == "date"
    assert frame.loc["2020-03-31", "Mkt-RF"] == pytest.approx(-0.1335, abs=1e-15)
    assert frame.loc["2020-12-31", "SMB"] == pytest.approx(0.0493, abs=1e-15)
    assert frame.loc["2020-04-30", "RF"] == 0.0
    assert frame.attrs["crsp_stamp"] == "202609"
    assert frame.to_numpy().dtype == np.float64


def test_zip_input_is_accepted() -> None:
    frame = parse_french_block(_zip(FF5_MONTHLY_2020), FF5_MONTHLY, min_rows=1)
    pd.testing.assert_frame_equal(frame, _monthly())


def test_row_floor_of_the_dataset_applies() -> None:
    with pytest.raises(FactorDataError, match="only 12 data rows; at least 600"):
        parse_french_block(FF5_MONTHLY_2020.encode("latin-1"), FF5_MONTHLY)


@pytest.mark.parametrize(
    ("old", "new", "message"),
    [
        (",Mkt-RF,SMB,HML,RMW,CMA,RF\n202001", ",Mkt-RF,SMB,HML,CMA,RMW,RF\n202001", "columns"),
        ("202003,  -13.35", "202013,  -13.35", "invalid date '202013'"),
        ("202005,    5.59,    1.92,   -5.00,    0.96,   -3.16,    0.01\n", "", "consecutive"),
        ("202002,   -8.15", "202002, -108.15", "outside"),
        ("    1.19,    0.12\n202004", "    1.19,    3.12\n202004", "RF outside"),
        ("202006,    2.44,    1.95", "202006,    2.44,        ", "non-numeric"),
        ("202006,    2.44,    1.95,", "202006,    2.44,    1.95,    1.95,", "fields"),
        (
            "\nCopyright",
            "\n202101,    1.0,    1.0,    1.0,    1.0,    1.0,    0.01\nCopyright",
            "second",
        ),
    ],
)
def test_malformed_monthly_files_are_refused(old: str, new: str, message: str) -> None:
    assert FF5_MONTHLY_2020.count(old) == 1
    with pytest.raises(FactorDataError, match=message):
        _monthly(FF5_MONTHLY_2020.replace(old, new))


def test_sentinels_become_nan() -> None:
    text = FF5_MONTHLY_2020.replace("202007,    5.83", "202007,  -99.99")
    frame = _monthly(text)
    values = frame.to_numpy(dtype=np.float64)
    assert np.isnan(values[6, 0])  # July, Mkt-RF
    assert int(np.isnan(values).sum()) == 1


def test_a_last_month_in_the_future_is_refused() -> None:
    with pytest.raises(FactorDataError, match="in the future"):
        _monthly(today=date(2020, 11, 15))
    assert len(_monthly(today=date(2021, 1, 1))) == 12


def test_a_new_factor_file_is_one_dataset_entry() -> None:
    """Momentum's layout (``,Mom`` with padding, YYYYMM rows, an annual block) needs no code."""
    mom = FrenchDataset(
        key="mom_monthly",
        filename="F-F_Momentum_Factor_CSV.zip",
        frequency="monthly",
        columns=("Mom",),
        min_rows=1,
        max_abs_factor=1.0,
    )
    text = (
        "This file was created using the 202609 CRSP database.  It\n"
        "contains a momentum factor.\n\n"
        "Missing data are indicated by -99.99 or -999.\n\n"
        ",Mom   \n192701,   0.57\n192702,  -1.51\n\n"
        "Annual Factors:\nJanuary-December \n,Mom\n  1927,  24.52\n"
    )
    frame = parse_french_block(text.encode("latin-1"), mom)
    assert list(frame.columns) == ["Mom"]
    np.testing.assert_allclose(frame["Mom"].to_numpy(), [0.0057, -0.0151], rtol=0, atol=1e-15)
    assert list(pd.DatetimeIndex(frame.index)) == [
        pd.Timestamp("1927-01-31"),
        pd.Timestamp("1927-02-28"),
    ]


# ----------------------------------------------------------------------------- compounding
def test_compounded_daily_market_matches_the_monthly_file_within_5_bp() -> None:
    """``prod(1 + Mkt-RF_d + RF_d) - 1`` against ``Mkt-RF_m + RF_m`` over April-June 2020.

    The French monthly market return is built from monthly CRSP returns with weights fixed at
    the start of the month, the daily one from daily returns re-weighted every day, so the two
    only agree approximately. A second, larger source of difference is the daily RF, which the
    daily file prints to 0.01% a day: over a month that rounding alone can reach about
    ``n_days x 0.005% = 10 bp``. Measured on the full 202609 vintage (1963-07 to 2026-09), the
    total-return difference exceeds 5 bp in 338 of 759 months, but once each file's own RF is
    taken out (second assertion) only 14 of 759 months exceed 5 bp (median 1.0 bp).

    The excerpt is April to June 2020, when the one-month bill rate was about zero, so the RF
    rounding cannot enter and the check isolates the market-index construction. Both checks are
    asserted on every month of the excerpt.
    """
    daily = parse_french_csv(FF5_DAILY_2020Q2.encode("latin-1"), min_rows=1)
    monthly = _monthly()
    d_index = pd.DatetimeIndex(daily.index)
    d_mkt = daily["Mkt-RF"].to_numpy(dtype=np.float64)
    d_rf = daily["RF"].to_numpy(dtype=np.float64)
    m_index = pd.DatetimeIndex(monthly.index)
    m_mkt = monthly["Mkt-RF"].to_numpy(dtype=np.float64)
    m_rf = monthly["RF"].to_numpy(dtype=np.float64)
    checked: list[int] = []
    for month in (4, 5, 6):
        rows = np.asarray((d_index.year == 2020) & (d_index.month == month), dtype=bool)
        assert 19 <= int(rows.sum()) <= 23
        (pos,) = np.flatnonzero(np.asarray((m_index.year == 2020) & (m_index.month == month)))
        total_d = float((1.0 + d_mkt[rows] + d_rf[rows]).prod()) - 1.0
        rf_d = float((1.0 + d_rf[rows]).prod()) - 1.0
        total_m = float(m_mkt[pos] + m_rf[pos])
        assert abs(total_d - total_m) < 5 * BP, (month, (total_d - total_m) / BP)
        assert abs((total_d - rf_d) - float(m_mkt[pos])) < 5 * BP, month
        checked.append(month)
    assert checked == [4, 5, 6]
    assert len(daily) == 63  # every daily row of the excerpt was used


# ----------------------------------------------------------------------------- cache
class FakeFetch:
    def __init__(self, payload: bytes | None) -> None:
        self.payload = payload
        self.calls: list[str] = []

    def __call__(self, url: str) -> tuple[bytes, str | None]:
        self.calls.append(url)
        if self.payload is None:
            raise FactorDownloadError("offline")
        return self.payload, "Wed, 06 Jan 2021 10:00:00 GMT"


@pytest.fixture
def short_floor(monkeypatch: pytest.MonkeyPatch) -> None:
    """The excerpt has 12 rows; the real file needs 600."""
    monkeypatch.setitem(DATASETS, "ff5_monthly", dataclasses.replace(FF5_MONTHLY, min_rows=1))
    monkeypatch.setattr(french, "_LAST_ATTEMPT", {})


@pytest.mark.usefixtures("short_floor")
def test_first_load_downloads_and_caches(tmp_path: Path) -> None:
    fetch = FakeFetch(_zip(FF5_MONTHLY_2020))
    frame = load_french("ff5_monthly", data_dir=tmp_path, now=NOW, fetch=fetch)
    assert fetch.calls == [FF5_MONTHLY.url]
    assert len(frame) == 12
    assert frame.attrs["source_url"] == FF5_MONTHLY.url
    assert frame.attrs["crsp_stamp"] == "202609"
    assert (tmp_path / "factors" / "french" / "ff5_monthly.parquet").exists()
    assert not (tmp_path / "factors" / "meta.json").exists()  # the daily cache is not touched

    again = load_french("ff5_monthly", data_dir=tmp_path, now=NOW, fetch=FakeFetch(None))
    pd.testing.assert_frame_equal(again, frame)


@pytest.mark.usefixtures("short_floor")
def test_stale_cache_is_refreshed_and_a_failed_refresh_serves_the_cache(tmp_path: Path) -> None:
    load_french("ff5_monthly", data_dir=tmp_path, now=NOW, fetch=FakeFetch(_zip(FF5_MONTHLY_2020)))
    later = NOW + timedelta(days=60)  # 80 days after the last month: stale
    failing = FakeFetch(None)
    frame = load_french("ff5_monthly", data_dir=tmp_path, now=later, fetch=failing)
    assert failing.calls == [FF5_MONTHLY.url]
    assert len(frame) == 12
    # Within 12 hours of the failed attempt no new download is tried.
    blocked = FakeFetch(None)
    load_french("ff5_monthly", data_dir=tmp_path, now=later + timedelta(hours=1), fetch=blocked)
    assert blocked.calls == []


@pytest.mark.usefixtures("short_floor")
def test_forced_or_first_download_failures_raise(tmp_path: Path) -> None:
    with pytest.raises(FactorDownloadError):
        load_french("ff5_monthly", data_dir=tmp_path, now=NOW, fetch=FakeFetch(None))
    load_french("ff5_monthly", data_dir=tmp_path, now=NOW, fetch=FakeFetch(_zip(FF5_MONTHLY_2020)))
    with pytest.raises(FactorDownloadError):
        load_french("ff5_monthly", data_dir=tmp_path, now=NOW, fetch=FakeFetch(None), refresh=True)


def test_unknown_dataset_key() -> None:
    with pytest.raises(KeyError, match="ff5_monthly"):
        load_french("nope")


@pytest.mark.live
def test_live_ff5_monthly(tmp_path: Path) -> None:
    frame = french.load_ff5_monthly(data_dir=tmp_path)
    assert frame.index[0] == pd.Timestamp("1963-07-31")
    assert len(frame) >= 600
    pd.testing.assert_series_equal(
        frame.loc["2020-01-31":"2020-12-31", "Mkt-RF"],
        _monthly()["Mkt-RF"],
        check_freq=False,
    )
