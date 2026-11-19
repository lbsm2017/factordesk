"""Momentum files and the FF6 factor frame (E1): ``mom_daily``, ``mom_monthly``, ``join_momentum``.

Offline: the French rows come from the verbatim excerpts in ``fixtures/french_excerpt.py`` (the
202609 vintage). The expected values below are typed from the published files, so the parser is
checked against the source and not against itself.
"""

from __future__ import annotations

import dataclasses
import io
import zipfile
from datetime import UTC, date, datetime
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from factordesk.data import french
from factordesk.data.factors import SOURCE_URL, FactorDataError, FactorStatus, parse_french_csv
from factordesk.data.french import DATASETS, MOM, join_momentum, load_ff6, parse_french_block
from factordesk.tests.fixtures.french_excerpt import (
    FF5_DAILY_2020Q2,
    FF5_MONTHLY_2020,
    MOM_DAILY_2020Q2,
    MOM_MONTHLY_2020,
)

MOM_MONTHLY = DATASETS["mom_monthly"]
MOM_DAILY = DATASETS["mom_daily"]
FF5_MONTHLY = DATASETS["ff5_monthly"]
NOW = datetime(2021, 1, 20, 12, 0, tzinfo=UTC)

# Mom, percent, 2020-01 .. 2020-12, as published (F-F_Momentum_Factor_CSV.zip, 202609 vintage).
MOM_2020_PCT = [6.02, -0.25, 8.20, -5.61, 0.15, -0.87, 7.70, 0.43, 3.18, -3.10, -12.60, -2.26]


def _parse(text: str, dataset: french.FrenchDataset) -> pd.DataFrame:
    return parse_french_block(text.encode("latin-1"), dataset, min_rows=1)


def _zip(text: str, name: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(name, text.encode("latin-1"))
    return buf.getvalue()


# ----------------------------------------------------------------------------- datasets
def test_momentum_dataset_entries() -> None:
    assert MOM_MONTHLY.url.endswith("/ftp/F-F_Momentum_Factor_CSV.zip")
    assert MOM_DAILY.url.endswith("/ftp/F-F_Momentum_Factor_daily_CSV.zip")
    assert MOM_MONTHLY.columns == MOM_DAILY.columns == (MOM,) == ("Mom",)
    assert (MOM_MONTHLY.frequency, MOM_DAILY.frequency) == ("monthly", "daily")
    assert "RF" not in MOM_MONTHLY.columns  # a spread: no risk-free column, nothing subtracted


def test_monthly_momentum_rows_equal_the_published_file() -> None:
    frame = _parse(MOM_MONTHLY_2020, MOM_MONTHLY)
    assert list(frame.columns) == ["Mom"]
    assert list(frame.index) == list(pd.date_range("2020-01-31", periods=12, freq="ME"))
    np.testing.assert_allclose(
        frame["Mom"].to_numpy(), np.array(MOM_2020_PCT) / 100.0, rtol=0, atol=1e-15
    )
    assert frame.loc["2020-11-30", "Mom"] == pytest.approx(-0.1260, abs=1e-15)
    assert frame.attrs["crsp_stamp"] == "202609"
    assert frame.attrs["key"] == "mom_monthly"


def test_daily_momentum_rows_equal_the_published_file() -> None:
    frame = _parse(MOM_DAILY_2020Q2, MOM_DAILY)
    index = pd.DatetimeIndex(frame.index)
    assert len(frame) == 63  # every trading day of 2020-Q2, as in the five-factor daily file
    assert (index[0], index[-1]) == (pd.Timestamp("2020-04-01"), pd.Timestamp("2020-06-30"))
    published = {
        "2020-04-01": 0.18,
        "2020-04-02": -0.97,
        "2020-04-17": -5.51,
        "2020-04-29": -4.76,
        "2020-06-29": -2.60,
        "2020-06-30": 1.20,
    }
    for day, pct in published.items():
        assert frame.loc[day, "Mom"] == pytest.approx(pct / 100.0, abs=1e-15), day
    assert frame.attrs["crsp_stamp"] == "202609"
    five = parse_french_csv(FF5_DAILY_2020Q2.encode("latin-1"), min_rows=1)
    assert index.equals(pd.DatetimeIndex(five.index))  # same trading calendar


@pytest.mark.parametrize(
    "header", [",Mom", ",Mom   ", "   ,  Mom  ", ",MOM", ",UMD", ",Mom\xa0", "\t,Mom\t"]
)
def test_momentum_header_is_parsed_defensively(header: str) -> None:
    text = MOM_MONTHLY_2020.replace("\n,Mom\n202001", f"\n{header}\n202001", 1)
    assert text != MOM_MONTHLY_2020 or header == ",Mom"
    pd.testing.assert_frame_equal(_parse(text, MOM_MONTHLY), _parse(MOM_MONTHLY_2020, MOM_MONTHLY))


def test_a_utf8_byte_order_mark_is_ignored() -> None:
    raw = b"\xef\xbb\xbf" + MOM_MONTHLY_2020.encode("latin-1")
    frame = parse_french_block(raw, MOM_MONTHLY, min_rows=1)
    pd.testing.assert_frame_equal(frame, _parse(MOM_MONTHLY_2020, MOM_MONTHLY))


def test_a_trailing_comma_on_header_and_rows_is_tolerated() -> None:
    lines = MOM_MONTHLY_2020.split("\n")
    out = [
        ln + "," if ln == ",Mom" or (ln[:6].isdigit() and ln.startswith("2020")) else ln
        for ln in lines
    ]
    pd.testing.assert_frame_equal(
        _parse("\n".join(out), MOM_MONTHLY), _parse(MOM_MONTHLY_2020, MOM_MONTHLY)
    )


@pytest.mark.parametrize(
    ("old", "new", "message"),
    [
        ("\n,Mom\n202001", "\n,Mom,SMB\n202001", "columns"),
        ("\n,Mom\n202001", "\n,Momentum2\n202001", "columns"),
        ("202003,   8.20", "202003, 180.20", "outside"),
        ("202003,   8.20", "202003,   8.20,  1.00", "fields"),
        ("202005,   0.15\n", "", "consecutive"),
    ],
)
def test_malformed_momentum_files_are_refused(old: str, new: str, message: str) -> None:
    text = MOM_MONTHLY_2020.replace(old, new, 1)
    assert text != MOM_MONTHLY_2020
    with pytest.raises(FactorDataError, match=message):
        _parse(text, MOM_MONTHLY)


def test_momentum_row_floors() -> None:
    with pytest.raises(FactorDataError, match="only 12 data rows; at least 1000"):
        parse_french_block(MOM_MONTHLY_2020.encode("latin-1"), MOM_MONTHLY)
    with pytest.raises(FactorDataError, match="only 63 data rows; at least 20000"):
        parse_french_block(MOM_DAILY_2020Q2.encode("latin-1"), MOM_DAILY)


def test_momentum_sentinel_becomes_nan() -> None:
    text = MOM_MONTHLY_2020.replace("202006,  -0.87", "202006, -99.99", 1)
    frame = _parse(text, MOM_MONTHLY)
    missing = pd.DatetimeIndex(frame.index)[frame["Mom"].isna().to_numpy()]
    assert list(missing) == [pd.Timestamp("2020-06-30")]


# ----------------------------------------------------------------------------- join
def test_monthly_join_keeps_both_files_as_published() -> None:
    ff5 = _parse(FF5_MONTHLY_2020, FF5_MONTHLY)
    mom = _parse(MOM_MONTHLY_2020, MOM_MONTHLY)
    ff6 = join_momentum(ff5, mom)
    assert list(ff6.columns) == ["Mkt-RF", "SMB", "HML", "RMW", "CMA", "RF", "Mom"]
    pd.testing.assert_frame_equal(ff6.drop(columns="Mom"), ff5, check_names=False)
    # Mom is a spread: copied as published, RF never subtracted.
    np.testing.assert_array_equal(ff6["Mom"].to_numpy(), mom["Mom"].to_numpy())
    assert ff6.loc["2020-03-31", "Mom"] == pytest.approx(0.0820, abs=1e-15)
    assert ff6.attrs["ff5"]["key"] == "ff5_monthly"
    assert ff6.attrs["mom"]["key"] == "mom_monthly"
    assert ff6.attrs["ff5"]["crsp_stamp"] == ff6.attrs["mom"]["crsp_stamp"] == "202609"
    assert ff6.attrs["ends_with"] == "both"
    assert (ff6.attrs["first_date"], ff6.attrs["last_date"]) == ("2020-01-31", "2020-12-31")
    assert ff6.attrs["key"] == "ff6_monthly"


@pytest.mark.parametrize("shorter", ["mom", "ff5"])
def test_join_ends_at_the_earlier_last_date(shorter: str) -> None:
    ff5 = _parse(FF5_MONTHLY_2020, FF5_MONTHLY)
    mom = _parse(MOM_MONTHLY_2020, MOM_MONTHLY)
    if shorter == "mom":
        mom = mom.loc[:"2020-10-31"]
    else:
        ff5 = ff5.loc[:"2020-09-30"]
    ff6 = join_momentum(ff5, mom)
    expected_last = "2020-10-31" if shorter == "mom" else "2020-09-30"
    assert pd.Timestamp(ff6.index[-1]) == pd.Timestamp(expected_last)
    assert ff6.attrs["last_date"] == expected_last
    assert ff6.attrs["ends_with"] == shorter
    assert not ff6.isna().any().any()


def test_join_starts_at_the_later_first_date() -> None:
    ff5 = _parse(FF5_MONTHLY_2020, FF5_MONTHLY).loc["2020-04-30":]
    mom = _parse(MOM_MONTHLY_2020, MOM_MONTHLY)
    ff6 = join_momentum(ff5, mom)
    assert pd.Timestamp(ff6.index[0]) == pd.Timestamp("2020-04-30")
    assert len(ff6) == 9


def test_daily_join_on_the_trading_calendar() -> None:
    ff5 = parse_french_csv(FF5_DAILY_2020Q2.encode("latin-1"), min_rows=1)
    mom = _parse(MOM_DAILY_2020Q2, MOM_DAILY)
    ff6 = join_momentum(ff5, mom)
    assert len(ff6) == 63
    assert ff6.attrs["key"] == "ff6_daily"
    assert ff6.loc["2020-04-17", "Mom"] == pytest.approx(-0.0551, abs=1e-15)
    assert ff6.loc["2020-04-17", "Mkt-RF"] == pytest.approx(0.0273, abs=1e-15)


def test_a_missing_momentum_date_stays_nan_and_is_counted() -> None:
    ff5 = parse_french_csv(FF5_DAILY_2020Q2.encode("latin-1"), min_rows=1)
    mom = _parse(MOM_DAILY_2020Q2, MOM_DAILY).drop(index=pd.Timestamp("2020-05-12"))
    ff6 = join_momentum(ff5, mom)
    assert len(ff6) == 63
    missing = pd.DatetimeIndex(ff6.index)[ff6["Mom"].isna().to_numpy()]
    assert list(missing) == [pd.Timestamp("2020-05-12")]
    assert ff6.attrs["mom_missing_rows"] == 1
    assert ff6.attrs["mom_rows_without_ff5"] == 0


def test_join_refuses_mixed_frequencies_and_no_overlap() -> None:
    ff5_m = _parse(FF5_MONTHLY_2020, FF5_MONTHLY)
    mom_d = _parse(MOM_DAILY_2020Q2, MOM_DAILY)
    with pytest.raises(ValueError, match="different frequencies"):
        join_momentum(ff5_m, mom_d)
    mom_m = _parse(MOM_MONTHLY_2020, MOM_MONTHLY)
    with pytest.raises(FactorDataError, match="do not overlap"):
        join_momentum(ff5_m.loc[:"2020-03-31"], mom_m.loc["2020-06-30":])


# ----------------------------------------------------------------------------- loader
class _Fetch:
    def __init__(self, payloads: dict[str, bytes]) -> None:
        self.payloads = payloads
        self.calls: list[str] = []

    def __call__(self, url: str) -> tuple[bytes, str | None]:
        self.calls.append(url)
        return self.payloads[url], None


def test_load_ff6_monthly_records_both_vintages(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(DATASETS, "ff5_monthly", dataclasses.replace(FF5_MONTHLY, min_rows=1))
    monkeypatch.setitem(DATASETS, "mom_monthly", dataclasses.replace(MOM_MONTHLY, min_rows=1))
    monkeypatch.setattr(french, "_LAST_ATTEMPT", {})
    fetch = _Fetch(
        {
            FF5_MONTHLY.url: _zip(FF5_MONTHLY_2020, "F-F_Research_Data_5_Factors_2x3.csv"),
            MOM_MONTHLY.url: _zip(MOM_MONTHLY_2020.replace("202012,  -2.26\n", ""), "m.csv"),
        }
    )
    ff6 = load_ff6("monthly", data_dir=tmp_path, now=NOW, fetch=fetch)
    assert sorted(fetch.calls) == sorted([FF5_MONTHLY.url, MOM_MONTHLY.url])
    assert len(ff6) == 11  # Mom ends one month earlier
    assert ff6.attrs["ends_with"] == "mom"
    for part, url in (("ff5", FF5_MONTHLY.url), ("mom", MOM_MONTHLY.url)):
        vintage = ff6.attrs[part]
        assert vintage["source_url"] == url
        assert vintage["crsp_stamp"] == "202609"
        assert vintage["sha256"] and vintage["downloaded_at"]
    with pytest.raises(ValueError, match="frequency"):
        load_ff6("weekly", data_dir=tmp_path, now=NOW, fetch=fetch)  # type: ignore[arg-type]


def test_load_ff6_daily_uses_the_daily_five_factor_loader(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ff5 = parse_french_csv(FF5_DAILY_2020Q2.encode("latin-1"), min_rows=1)
    status = FactorStatus(
        last_date=date(2020, 6, 30),
        first_date=date(2020, 4, 1),
        days_behind=204,
        last_download_at=NOW,
        source_url=SOURCE_URL,
        stale=True,
    )

    def fake_ff5_daily(**_: object) -> pd.DataFrame:
        return ff5

    def fake_status(*_: object) -> FactorStatus:
        return status

    monkeypatch.setattr(french, "load_ff5_daily", fake_ff5_daily)
    monkeypatch.setattr(french, "factor_status", fake_status)
    monkeypatch.setitem(DATASETS, "mom_daily", dataclasses.replace(MOM_DAILY, min_rows=1))
    monkeypatch.setattr(french, "_LAST_ATTEMPT", {})
    fetch = _Fetch({MOM_DAILY.url: _zip(MOM_DAILY_2020Q2, "d.csv")})
    ff6 = load_ff6("daily", data_dir=tmp_path, now=NOW, fetch=fetch)
    assert fetch.calls == [MOM_DAILY.url]
    assert len(ff6) == 63 and ff6.attrs["ends_with"] == "both"
    assert ff6.attrs["ff5"]["key"] == "ff5_daily"
    assert ff6.attrs["ff5"]["source_url"] == SOURCE_URL
    assert ff6.attrs["ff5"]["downloaded_at"] == NOW.isoformat()
    assert ff6.attrs["mom"]["source_url"] == MOM_DAILY.url
    assert ff5.attrs == {}  # the five-factor frame given by the loader is not modified
