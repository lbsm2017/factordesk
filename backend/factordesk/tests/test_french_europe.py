"""Developed Europe factor files (S4-2): parser, loader and the factor-set choice of the loaders.

Offline: the rows come from the invented excerpts in ``fixtures/europe_excerpt.py``.
"""

from __future__ import annotations

import dataclasses
import io
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from factordesk.data import french
from factordesk.data.french import (
    DATASETS,
    join_momentum,
    load_ff5_monthly,
    load_ff6,
    load_french,
    parse_french_block,
    stamp_notices,
)
from factordesk.tests.fixtures.europe_excerpt import (
    EUROPE5_DAILY_APR_2020,
    EUROPE5_MONTHLY_2020,
    EUROPE_MOM_DAILY_APR_2020,
    EUROPE_MOM_MONTHLY_2020,
)

NOW = datetime(2021, 1, 20, 12, 0, tzinfo=UTC)
KEYS = ("europe5_daily", "europe5_monthly", "europe_mom_daily", "europe_mom_monthly")


def _zip(text: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("file.csv", text.encode("latin-1"))
    return buf.getvalue()


def _parse(text: str, key: str) -> pd.DataFrame:
    return parse_french_block(text.encode("latin-1"), DATASETS[key], min_rows=1)


def test_dataset_entries_name_the_europe_files() -> None:
    assert DATASETS["europe5_daily"].filename == "Europe_5_Factors_Daily_CSV.zip"
    assert DATASETS["europe5_monthly"].filename == "Europe_5_Factors_CSV.zip"
    assert DATASETS["europe_mom_daily"].filename == "Europe_Mom_Factor_Daily_CSV.zip"
    assert DATASETS["europe_mom_monthly"].filename == "Europe_Mom_Factor_CSV.zip"
    for key in KEYS:
        assert DATASETS[key].url.startswith(french.BASE_URL)
    assert DATASETS["europe5_monthly"].columns == DATASETS["ff5_monthly"].columns


def test_monthly_five_factors_are_read_and_the_annual_block_skipped() -> None:
    frame = _parse(EUROPE5_MONTHLY_2020, "europe5_monthly")
    assert list(frame.columns) == ["Mkt-RF", "SMB", "HML", "RMW", "CMA", "RF"]
    assert len(frame) == 12
    assert list(frame.index) == list(pd.date_range("2020-01-31", periods=12, freq="ME"))
    assert frame.loc["2020-01-31", "Mkt-RF"] == pytest.approx(-2.5 / 100, abs=1e-15)
    assert frame["RF"].eq(0.0005).all()
    assert frame.attrs["crsp_stamp"] == "202609"
    assert frame.attrs["stamp_source"] == "BLOOMBERG"


def test_wml_column_is_read_as_mom() -> None:
    monthly = _parse(EUROPE_MOM_MONTHLY_2020, "europe_mom_monthly")
    daily = _parse(EUROPE_MOM_DAILY_APR_2020, "europe_mom_daily")
    assert list(monthly.columns) == ["Mom"] and len(monthly) == 12
    assert list(daily.columns) == ["Mom"] and len(daily) == 21
    assert monthly.loc["2020-02-29", "Mom"] == pytest.approx(4.5 / 100, abs=1e-15)
    assert monthly.to_numpy().dtype == np.float64


def test_daily_five_factors_are_read() -> None:
    frame = _parse(EUROPE5_DAILY_APR_2020, "europe5_daily")
    assert len(frame) == 21
    assert frame.index[0] == pd.Timestamp("2020-04-01")
    assert frame.index[-1] == pd.Timestamp("2020-04-30")
    assert frame["RF"].eq(0.0001).all()


def test_zip_input_and_row_floor() -> None:
    parsed = parse_french_block(_zip(EUROPE5_MONTHLY_2020), DATASETS["europe5_monthly"], min_rows=1)
    pd.testing.assert_frame_equal(parsed, _parse(EUROPE5_MONTHLY_2020, "europe5_monthly"))
    with pytest.raises(french.FactorDataError, match="only 12 data rows; at least 400"):
        parse_french_block(EUROPE5_MONTHLY_2020.encode("latin-1"), DATASETS["europe5_monthly"])


def test_an_unexpected_header_is_refused() -> None:
    wrong = EUROPE_MOM_MONTHLY_2020.replace(",WML", ",SMB", 1)
    with pytest.raises(french.FactorDataError, match="columns"):
        _parse(wrong, "europe_mom_monthly")


def test_check_factor_set() -> None:
    assert french.check_factor_set("europe") == "europe"
    with pytest.raises(ValueError, match="factor set"):
        french.check_factor_set("asia")


# ----------------------------------------------------------------------------- loader
class _Fetch:
    def __init__(self, payloads: dict[str, bytes]) -> None:
        self.payloads = payloads
        self.calls: list[str] = []

    def __call__(self, url: str) -> tuple[bytes, str | None]:
        self.calls.append(url)
        return self.payloads[url], None


@pytest.fixture
def short_floors(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in KEYS:
        monkeypatch.setitem(DATASETS, key, dataclasses.replace(DATASETS[key], min_rows=1))
    monkeypatch.setattr(french, "_LAST_ATTEMPT", {})


def _europe_fetch() -> _Fetch:
    return _Fetch(
        {
            DATASETS["europe5_daily"].url: _zip(EUROPE5_DAILY_APR_2020),
            DATASETS["europe5_monthly"].url: _zip(EUROPE5_MONTHLY_2020),
            DATASETS["europe_mom_daily"].url: _zip(EUROPE_MOM_DAILY_APR_2020),
            DATASETS["europe_mom_monthly"].url: _zip(EUROPE_MOM_MONTHLY_2020),
        }
    )


@pytest.mark.usefixtures("short_floors")
def test_load_french_caches_a_europe_file(tmp_path: Path) -> None:
    fetch = _europe_fetch()
    frame = load_french("europe5_monthly", data_dir=tmp_path, now=NOW, fetch=fetch)
    assert fetch.calls == [DATASETS["europe5_monthly"].url]
    assert frame.attrs["source_url"] == DATASETS["europe5_monthly"].url
    assert frame.attrs["stamp_source"] == "BLOOMBERG"
    assert (tmp_path / "factors" / "french" / "europe5_monthly.parquet").exists()
    again = load_french("europe5_monthly", data_dir=tmp_path, now=NOW, fetch=_Fetch({}))
    pd.testing.assert_frame_equal(again, frame)


@pytest.mark.usefixtures("short_floors")
def test_load_ff5_monthly_takes_the_factor_set(tmp_path: Path) -> None:
    fetch = _europe_fetch()
    frame = load_ff5_monthly(data_dir=tmp_path, now=NOW, fetch=fetch, factor_set="europe")
    assert fetch.calls == [DATASETS["europe5_monthly"].url]
    assert len(frame) == 12
    with pytest.raises(ValueError, match="factor set"):
        load_ff5_monthly(data_dir=tmp_path, now=NOW, fetch=fetch, factor_set="asia")  # type: ignore[arg-type]


@pytest.mark.usefixtures("short_floors")
@pytest.mark.parametrize("frequency", ["monthly", "daily"])
def test_load_ff6_europe_joins_the_four_files(tmp_path: Path, frequency: str) -> None:
    fetch = _europe_fetch()
    ff6 = load_ff6(
        frequency,  # type: ignore[arg-type]
        data_dir=tmp_path,
        now=NOW,
        fetch=fetch,
        factor_set="europe",
    )
    five = "europe5_" + frequency
    mom = "europe_mom_" + frequency
    assert sorted(fetch.calls) == sorted([DATASETS[five].url, DATASETS[mom].url])
    assert list(ff6.columns) == ["Mkt-RF", "SMB", "HML", "RMW", "CMA", "RF", "Mom"]
    assert len(ff6) == (12 if frequency == "monthly" else 21)
    assert not ff6.isna().any().any()
    assert ff6.attrs["factor_set"] == "europe"
    assert ff6.attrs["ff5"]["source_url"] == DATASETS[five].url
    assert ff6.attrs["mom"]["source_url"] == DATASETS[mom].url
    assert stamp_notices(ff6.attrs) == []  # same vintage in both files


def test_stamp_notice_names_the_bloomberg_release() -> None:
    ff5 = _parse(EUROPE5_MONTHLY_2020, "europe5_monthly")
    older = EUROPE_MOM_MONTHLY_2020.replace("202609 Bloomberg", "202608 Bloomberg")
    mom = _parse(older, "europe_mom_monthly")
    notes = stamp_notices(join_momentum(ff5, mom, "europe").attrs)
    assert len(notes) == 1
    assert "202609 Bloomberg release" in notes[0] and "202608" in notes[0]


def test_join_momentum_defaults_to_the_us_set() -> None:
    ff5 = _parse(EUROPE5_MONTHLY_2020, "europe5_monthly")
    mom = _parse(EUROPE_MOM_MONTHLY_2020, "europe_mom_monthly")
    assert join_momentum(ff5, mom).attrs["factor_set"] == "us"
    with pytest.raises(ValueError, match="factor set"):
        join_momentum(ff5, mom, "asia")  # type: ignore[arg-type]
