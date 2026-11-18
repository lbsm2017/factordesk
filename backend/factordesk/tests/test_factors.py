"""Offline tests for the factor data layer, plus one live test against the French library."""

from __future__ import annotations

import io
import json
import logging
import zipfile
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import cast

import numpy as np
import pandas as pd
import pytest

from factordesk.data import factors
from factordesk.data.factors import (
    FACTOR_COLUMNS,
    FactorDataError,
    FactorDownloadError,
    factor_status,
    load_ff5_daily,
    parse_french_csv,
)

HEADER = ",Mkt-RF,SMB,HML,RMW,CMA,RF"
LAST_DATE = date(2026, 9, 30)
NOW = datetime(2026, 11, 18, 12, 0, tzinfo=UTC)  # 49 days after LAST_DATE


def make_csv(
    n_rows: int = 6,
    last: date = LAST_DATE,
    header: str = HEADER,
    sentinel_row: bool = True,
    scale: float = 1.0,
) -> bytes:
    """Synthetic file mimicking the real layout: description, blank, header, rows, footer."""
    days = pd.bdate_range(end=pd.Timestamp(last), periods=n_rows)
    lines = [
        "This file was created by CMPT_ME_BEME_OP_INV_RETS_DAILY using the 202609 CRSP database.",
        "The 1-month TBill return is from Ibbotson and Associates, Inc.",
        "",
        header,
    ]
    for i, d in enumerate(days):
        v = (np.arange(5) + 1 + i) * 0.1 * scale
        cells = [*(f"{x:7.2f}" for x in v), f"{0.02:7.3f}"]  # RF 0.02% a day, as in the real file
        if sentinel_row and i == 1:
            cells[2] = "-99.99".rjust(7)
        lines.append(f"{d:%Y%m%d}," + ",".join(cells))
    lines += ["", "Copyright 2026 Kenneth R. French", ""]
    return ("\r\n".join(lines)).encode("latin-1")


def make_zip(csv: bytes, name: str = "F-F_Research_Data_5_Factors_2x3_daily.CSV") -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(name, csv)
    return buf.getvalue()


@pytest.fixture(autouse=True)
def _small_min_rows(monkeypatch: pytest.MonkeyPatch) -> None:  # pyright: ignore[reportUnusedFunction]
    monkeypatch.setattr(factors, "MIN_ROWS", 1)
    monkeypatch.setattr(factors, "_sleep", _no_sleep)
    factors._LAST_ATTEMPT.clear()  # pyright: ignore[reportPrivateUsage]


def _no_sleep(_seconds: float) -> None:
    return None


class FakeDownload:
    def __init__(self, payload: bytes | Exception) -> None:
        self.payload = payload
        self.calls = 0

    def __call__(self, url: str = factors.SOURCE_URL) -> tuple[bytes, str | None]:
        self.calls += 1
        if isinstance(self.payload, Exception):
            raise self.payload
        return self.payload, "Wed, 01 Oct 2026 00:00:00 GMT"


def install(monkeypatch: pytest.MonkeyPatch, payload: bytes | Exception) -> FakeDownload:
    fake = FakeDownload(payload)
    monkeypatch.setattr(factors, "_download", fake)
    return fake


# ------------------------------------------------------------------ parsing


def test_parse_basic_layout() -> None:
    df = parse_french_csv(make_csv())
    assert list(df.columns) == [*FACTOR_COLUMNS, "RF"]
    assert df.index.name == "date"
    idx = cast(pd.DatetimeIndex, df.index)
    assert idx.tz is None
    assert df.index.is_monotonic_increasing and df.index.is_unique
    assert (df.dtypes == "float64").all()
    assert len(df) == 6
    assert cast(pd.Timestamp, df.index[-1]).date() == LAST_DATE
    assert idx.equals(idx.normalize())


def test_parse_percent_to_decimal() -> None:
    df = parse_french_csv(make_csv())
    first = df.iloc[0]
    assert first["Mkt-RF"] == pytest.approx(0.001)  # 0.10 percent
    assert first["RF"] == pytest.approx(0.0002)  # 0.02 percent


def _text(rows: list[str], header: str = HEADER, footer: bool = True) -> bytes:
    lines = [
        "This file was created by CMPT_ME_BEME_OP_INV_RETS_DAILY using the 202609 CRSP database.",
        "The 1-month TBill return is from Ibbotson and Associates, Inc.",
        "Second preamble line.",
        "Third preamble line.",
        "",
        "",
        header,
        *rows,
    ]
    if footer:
        lines += ["", "Copyright 2026 Kenneth R. French"]
    return "\r\n".join(lines).encode("latin-1")


ROWS = [
    "19630701,   -0.67,    0.00,   -0.34,   -0.01,    0.16,    0.012",
    "19630702,    0.79,   -0.26,    0.26,   -0.07,   -0.20,    0.012",
    "19630703,    0.63,   -0.17,   -0.09,    0.18,   -0.34,    0.012",
]


def test_t01_header_with_leading_spaces() -> None:
    df = parse_french_csv(_text(ROWS, header="  ,Mkt-RF,SMB,HML,RMW,CMA,RF"))
    assert list(df.columns) == [*FACTOR_COLUMNS, "RF"] and len(df) == 3


def test_t03_exact_values() -> None:
    first = parse_french_csv(_text(ROWS)).iloc[0]
    assert abs(first["Mkt-RF"] - (-0.0067)) <= 1e-15
    assert abs(first["RMW"] - (-0.0001)) <= 1e-15
    assert abs(first["RF"] - 0.00012) <= 1e-15


@pytest.mark.parametrize(
    "header", [",Mkt-RF,SMB,HML,CMA,RF", ",Mkt-RF,SMB,CMA,RMW,HML,RF", ",RF,CMA,RMW,HML,SMB,Mkt-RF"]
)
def test_t02_wrong_or_reordered_header_raises(header: str) -> None:
    with pytest.raises(FactorDataError, match="Unexpected factor columns") as info:
        parse_french_csv(_text(ROWS, header=header))
    assert header.split(",")[1] in str(info.value)  # names the tokens found


def test_t06_second_data_block_raises() -> None:
    raw = _text(ROWS) + b"\r\n20260101,    0.10,    0.10,    0.10,    0.10,    0.10,    0.010"
    with pytest.raises(FactorDataError, match="unexpected second data block"):
        parse_french_csv(raw)


def test_t07_invalid_calendar_date_names_its_line() -> None:
    rows = [ROWS[0], "20230230,    0.79,   -0.26,    0.26,   -0.07,   -0.20,    0.012"]
    with pytest.raises(FactorDataError, match="line 9"):
        parse_french_csv(_text(rows))


def test_t07_decreasing_dates_raise() -> None:
    with pytest.raises(FactorDataError, match="strictly increasing"):
        parse_french_csv(_text([ROWS[1], ROWS[0], ROWS[2]]))


@pytest.mark.parametrize(
    "row",
    [
        "19630704,   75.00,    0.00,   -0.34,   -0.01,    0.16,    0.012",
        "19630704,    0.10,    0.00,   -0.34,   -0.01,    0.16,    0.500",
        "19630704,    0.10,    0.00,   -0.34,   -0.01,    0.16,   -0.020",
    ],
)
def test_t10_value_bounds(row: str) -> None:
    with pytest.raises(FactorDataError, match="outside"):
        parse_french_csv(_text([*ROWS, row]))


def test_t116_empty_cell_raises_with_line() -> None:
    rows = [ROWS[0], "19630702,    0.79,        ,    0.26,   -0.07,   -0.20,    0.012"]
    with pytest.raises(FactorDataError, match="line 9"):
        parse_french_csv(_text(rows))


def test_t116_parser_reads_no_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    class Exploding:
        @staticmethod
        def now(tz: object = None) -> datetime:
            raise AssertionError("the parser must not read the clock")

    monkeypatch.setattr(factors, "datetime", Exploding)
    far = make_csv(last=date(2030, 1, 31))
    assert len(parse_french_csv(far)) == 6
    with pytest.raises(FactorDataError, match="future"):
        parse_french_csv(far, today=date(2029, 12, 1))
    assert len(parse_french_csv(far, today=date(2030, 1, 30))) == 6


def test_t116_sentinel_is_logged_with_date_and_column(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING, logger="factordesk.data.factors"):
        parse_french_csv(make_csv())
    assert "HML" in caplog.text and "sentinel" in caplog.text


def test_t11_revision_tolerance(caplog: pytest.LogCaptureFixture) -> None:
    old = parse_french_csv(_text(ROWS))
    values = old.to_numpy(copy=True)
    values[0, 0] += 0.0001  # one published digit (0.01%)
    values[1, 1] += 1e-6  # rounding noise, below half a digit
    new = pd.DataFrame(values, index=old.index, columns=old.columns)
    with caplog.at_level(logging.WARNING, logger="factordesk.data.factors"):
        factors._log_revisions(old, new)  # pyright: ignore[reportPrivateUsage]
    assert "1 historical values changed" in caplog.text
    assert "max abs difference 0.0001" in caplog.text
    assert "1963-07-01" in caplog.text


def test_parse_sentinel_becomes_nan_not_zero() -> None:
    df = parse_french_csv(make_csv())
    assert np.isnan(df.iloc[1]["HML"])
    assert int(df.isna().to_numpy().sum()) == 1
    assert not (df == -0.9999).to_numpy().any()


def test_parse_sentinel_999() -> None:
    raw = make_csv().replace(b" -99.99", b"   -999")
    df = parse_french_csv(raw)
    assert np.isnan(df.iloc[1]["HML"])


def test_parse_header_detection_ignores_description_commas() -> None:
    raw = make_csv().replace(b"The 1-month", b"Note, with a comma: the 1-month")
    df = parse_french_csv(raw)
    assert len(df) == 6


def test_parse_footer_ignored() -> None:
    df = parse_french_csv(make_csv())
    assert len(df) == 6  # copyright line and blank lines produced no rows


def test_parse_bad_column_set_raises() -> None:
    with pytest.raises(FactorDataError, match="Unexpected factor columns"):
        parse_french_csv(make_csv(header=",Mkt-RF,SMB,HML,RMW,XXX,RF"))
    with pytest.raises(FactorDataError, match="Unexpected factor columns"):
        parse_french_csv(make_csv(header=",Mkt-RF,SMB,HML,RF"))


def test_parse_missing_header_raises() -> None:
    with pytest.raises(FactorDataError, match="No header"):
        parse_french_csv(b"just some text\r\n20260101, 1, 2, 3, 4, 5, 6\r\n")


def test_parse_min_rows_enforced() -> None:
    with pytest.raises(FactorDataError, match="at least 15000"):
        parse_french_csv(make_csv(), min_rows=15_000)


def test_parse_duplicate_dates_raise() -> None:
    lines = make_csv().decode("latin-1").split("\r\n")
    pos = next(i for i, ln in enumerate(lines) if ln.startswith("20260930"))
    raw = "\r\n".join([*lines[: pos + 1], lines[pos], *lines[pos + 1 :]]).encode("latin-1")
    with pytest.raises(FactorDataError, match="Duplicate date"):
        parse_french_csv(raw)


def test_parse_future_date_raises() -> None:
    future = NOW.date() + timedelta(days=60)
    with pytest.raises(FactorDataError, match="future"):
        parse_french_csv(make_csv(last=future), today=NOW.date())


def test_refresh_rejects_a_future_last_date(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    install(monkeypatch, make_zip(make_csv(last=NOW.date() + timedelta(days=60))))
    with pytest.raises(FactorDataError, match="future"):
        load_ff5_daily(data_dir=tmp_path, now=NOW)


def test_parse_out_of_range_raises() -> None:
    with pytest.raises(FactorDataError, match="outside"):
        parse_french_csv(make_csv(scale=200.0))


def test_parse_non_numeric_raises() -> None:
    raw = make_csv().replace(b"0.10", b"abcd", 1)
    with pytest.raises(FactorDataError, match="Non-numeric"):
        parse_french_csv(raw)


def test_parse_accepts_zip_bytes() -> None:
    df = parse_french_csv(make_zip(make_csv()))
    assert len(df) == 6


# ------------------------------------------------------------------ zip safety


def test_zip_bomb_cap() -> None:
    payload = make_zip(b"0" * 5_000_000, name="bomb.csv")
    assert len(payload) < 50_000  # tiny on the wire
    with pytest.raises(FactorDataError, match="cap"):
        factors._extract_csv_from_zip(payload, max_bytes=10_000)  # pyright: ignore[reportPrivateUsage]


def test_zip_bomb_cap_via_parse() -> None:
    payload = make_zip(b"0" * (21 * 1024 * 1024), name="bomb.csv")
    with pytest.raises(FactorDataError, match="cap"):
        parse_french_csv(payload)


def test_zip_with_multiple_csv_members_raises() -> None:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("a.csv", make_csv())
        zf.writestr("b.CSV", make_csv())
    with pytest.raises(FactorDataError, match="exactly one"):
        parse_french_csv(buf.getvalue())


def test_zip_without_csv_member_raises() -> None:
    with pytest.raises(FactorDataError, match="exactly one"):
        parse_french_csv(make_zip(make_csv(), name="data.txt"))


def test_corrupt_zip_raises() -> None:
    with pytest.raises(FactorDataError, match="valid zip"):
        parse_french_csv(b"PK\x03\x04 this is not really a zip")


# ------------------------------------------------------------------ cache, refresh, status


def test_first_load_downloads_and_caches(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = install(monkeypatch, make_zip(make_csv()))
    df = load_ff5_daily(data_dir=tmp_path, now=NOW)
    assert fake.calls == 1
    assert len(df) == 6
    fdir = tmp_path / "factors"
    assert (fdir / "ff5_daily.parquet").exists()
    meta = json.loads((fdir / "meta.json").read_text(encoding="utf-8"))
    assert meta["source_url"] == factors.SOURCE_URL
    assert meta["rows"] == 6
    assert meta["first_date"] == df.index[0].date().isoformat()  # pyright: ignore[reportUnknownMemberType]
    assert meta["last_date"] == "2026-09-30"
    assert meta["last_download_at"] == NOW.isoformat()
    assert meta["last_modified"] == "Wed, 01 Oct 2026 00:00:00 GMT"
    assert len(meta["sha256"]) == 64
    assert [p.name for p in fdir.iterdir() if p.suffix == ".tmp"] == []


def test_cached_roundtrip_preserves_nan_and_index(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fresh = NOW - timedelta(days=1)
    fake = install(monkeypatch, make_zip(make_csv(last=fresh.date())))
    first = load_ff5_daily(data_dir=tmp_path, now=NOW)
    second = load_ff5_daily(data_dir=tmp_path, now=NOW)
    assert fake.calls == 1  # fresh data: second call served from cache
    pd.testing.assert_frame_equal(first, second)
    assert second.index.name == "date"
    assert np.isnan(second.iloc[1]["HML"])


def test_failed_download_leaves_cache_untouched(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    install(monkeypatch, make_zip(make_csv()))
    load_ff5_daily(data_dir=tmp_path, now=NOW)
    pq = tmp_path / "factors" / "ff5_daily.parquet"
    meta = tmp_path / "factors" / "meta.json"
    before = (pq.read_bytes(), meta.read_bytes())

    install(monkeypatch, FactorDownloadError("boom"))
    with pytest.raises(FactorDownloadError):
        load_ff5_daily(refresh=True, data_dir=tmp_path, now=NOW)
    assert (pq.read_bytes(), meta.read_bytes()) == before


def test_failed_validation_leaves_cache_untouched(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    install(monkeypatch, make_zip(make_csv()))
    load_ff5_daily(data_dir=tmp_path, now=NOW)
    pq = tmp_path / "factors" / "ff5_daily.parquet"
    meta = tmp_path / "factors" / "meta.json"
    before = (pq.read_bytes(), meta.read_bytes())

    install(monkeypatch, make_zip(make_csv(header=",A,B,C,D,E,F")))
    with pytest.raises(FactorDataError):
        load_ff5_daily(refresh=True, data_dir=tmp_path, now=NOW)
    assert (pq.read_bytes(), meta.read_bytes()) == before


def test_failed_atomic_replace_keeps_old_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    install(monkeypatch, make_zip(make_csv()))
    load_ff5_daily(data_dir=tmp_path, now=NOW)
    fdir = tmp_path / "factors"
    before = ((fdir / "ff5_daily.parquet").read_bytes(), (fdir / "meta.json").read_bytes())

    def boom(src: object, dst: object) -> None:
        raise OSError("simulated crash during replace")

    install(monkeypatch, make_zip(make_csv(n_rows=8)))
    monkeypatch.setattr(factors.os, "replace", boom)
    with pytest.raises(OSError, match="simulated"):
        load_ff5_daily(refresh=True, data_dir=tmp_path, now=NOW)
    monkeypatch.undo()
    after = ((fdir / "ff5_daily.parquet").read_bytes(), (fdir / "meta.json").read_bytes())
    assert after == before
    assert [p.name for p in fdir.iterdir() if p.suffix == ".tmp"] == []


def test_no_cache_and_failed_download_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    install(monkeypatch, FactorDownloadError("offline"))
    with pytest.raises(FactorDownloadError):
        load_ff5_daily(data_dir=tmp_path, now=NOW)
    assert factor_status(tmp_path, now=NOW) is None


def test_status_none_when_nothing_cached(tmp_path: Path) -> None:
    assert factor_status(tmp_path, now=NOW) is None


def test_status_reporting(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    install(monkeypatch, make_zip(make_csv()))
    df = load_ff5_daily(data_dir=tmp_path, now=NOW)
    st = factor_status(tmp_path, now=NOW)
    assert st is not None
    assert st.last_date == LAST_DATE
    assert st.first_date == cast(pd.Timestamp, df.index[0]).date()
    assert st.days_behind == (NOW.date() - LAST_DATE).days == 49
    assert st.last_download_at == NOW
    assert st.source_url == factors.SOURCE_URL
    assert st.stale is True

    fresh = factor_status(tmp_path, now=datetime(2026, 11, 9, tzinfo=UTC))
    assert fresh is not None and fresh.days_behind == 40 and fresh.stale is False  # not > 40


def test_status_falls_back_to_parquet_without_meta(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    install(monkeypatch, make_zip(make_csv()))
    load_ff5_daily(data_dir=tmp_path, now=NOW)
    (tmp_path / "factors" / "meta.json").unlink()
    st = factor_status(tmp_path, now=NOW)
    assert st is not None
    assert st.last_date == LAST_DATE and st.last_download_at is None


# ------------------------------------------------------------------ staleness policy


def seed_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, downloaded_at: datetime) -> None:
    install(monkeypatch, make_zip(make_csv()))
    load_ff5_daily(data_dir=tmp_path, now=downloaded_at)
    factors._LAST_ATTEMPT.clear()  # pyright: ignore[reportPrivateUsage]


def test_stale_and_old_attempt_auto_refreshes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seed_cache(tmp_path, monkeypatch, NOW - timedelta(hours=13))
    fake = install(monkeypatch, make_zip(make_csv(n_rows=8)))
    df = load_ff5_daily(data_dir=tmp_path, now=NOW)
    assert fake.calls == 1
    assert len(df) == 8


def test_stale_but_recent_attempt_does_not_refresh(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seed_cache(tmp_path, monkeypatch, NOW - timedelta(hours=11))
    fake = install(monkeypatch, make_zip(make_csv(n_rows=8)))
    df = load_ff5_daily(data_dir=tmp_path, now=NOW)
    assert fake.calls == 0
    assert len(df) == 6


def test_not_stale_does_not_refresh(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    seed_cache(tmp_path, monkeypatch, NOW - timedelta(days=30))
    fake = install(monkeypatch, make_zip(make_csv(n_rows=8)))
    later = datetime(2026, 11, 9, tzinfo=UTC)  # exactly 40 days behind: not stale
    load_ff5_daily(data_dir=tmp_path, now=later)
    assert fake.calls == 0


def test_forced_refresh_ignores_policy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    seed_cache(tmp_path, monkeypatch, NOW - timedelta(minutes=1))
    fake = install(monkeypatch, make_zip(make_csv(n_rows=8)))
    df = load_ff5_daily(refresh=True, data_dir=tmp_path, now=NOW)
    assert fake.calls == 1 and len(df) == 8


def test_auto_refresh_failure_serves_cache_and_stays_stale(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    seed_cache(tmp_path, monkeypatch, NOW - timedelta(days=2))
    fake = install(monkeypatch, FactorDownloadError("HTTP 503"))
    with caplog.at_level(logging.WARNING, logger="factordesk.data.factors"):
        df = load_ff5_daily(data_dir=tmp_path, now=NOW)
    assert len(df) == 6
    assert "Automatic factor refresh failed" in caplog.text
    st = factor_status(tmp_path, now=NOW)
    assert st is not None and st.stale is True
    # The failed attempt gates a retry for 12 hours.
    load_ff5_daily(data_dir=tmp_path, now=NOW + timedelta(hours=1))
    assert fake.calls == 1
    load_ff5_daily(data_dir=tmp_path, now=NOW + timedelta(hours=13))
    assert fake.calls == 2


def test_revision_warning_logged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    install(monkeypatch, make_zip(make_csv()))
    load_ff5_daily(data_dir=tmp_path, now=NOW)
    install(monkeypatch, make_zip(make_csv(scale=1.5)))
    with caplog.at_level(logging.WARNING, logger="factordesk.data.factors"):
        load_ff5_daily(refresh=True, data_dir=tmp_path, now=NOW)
    assert "revised" in caplog.text
    assert "max abs difference" in caplog.text


def test_identical_refresh_logs_no_revision(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    install(monkeypatch, make_zip(make_csv()))
    load_ff5_daily(data_dir=tmp_path, now=NOW)
    with caplog.at_level(logging.WARNING, logger="factordesk.data.factors"):
        load_ff5_daily(refresh=True, data_dir=tmp_path, now=NOW)
    assert "revised" not in caplog.text


# ------------------------------------------------------------------ download error handling


class _Resp:
    def __init__(self, status: int, content: bytes = b"", headers: dict[str, str] | None = None):
        self.status_code = status
        self.content = content
        self.headers = headers or {}


def _patch_client(monkeypatch: pytest.MonkeyPatch, responses: list[_Resp]) -> list[int]:
    calls: list[int] = []

    class FakeClient:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        def __enter__(self) -> FakeClient:
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def get(self, url: str) -> _Resp:
            calls.append(1)
            return responses[min(len(calls) - 1, len(responses) - 1)]

    monkeypatch.setattr(factors.httpx, "Client", FakeClient)
    return calls


def test_download_401_distinct_and_not_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _patch_client(monkeypatch, [_Resp(401)])
    with pytest.raises(FactorDownloadError, match="401"):
        factors._download()  # pyright: ignore[reportPrivateUsage]
    assert len(calls) == 1


def test_download_404_not_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _patch_client(monkeypatch, [_Resp(404)])
    with pytest.raises(FactorDownloadError, match="HTTP 404"):
        factors._download()  # pyright: ignore[reportPrivateUsage]
    assert len(calls) == 1


def test_download_retries_5xx_then_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _patch_client(
        monkeypatch, [_Resp(503), _Resp(502), _Resp(200, b"zip", {"last-modified": "x"})]
    )
    content, lm = factors._download()  # pyright: ignore[reportPrivateUsage]
    assert (content, lm) == (b"zip", "x")
    assert len(calls) == 3


def test_download_gives_up_after_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _patch_client(monkeypatch, [_Resp(500)])
    with pytest.raises(FactorDownloadError, match="after 4 attempts"):
        factors._download()  # pyright: ignore[reportPrivateUsage]
    assert len(calls) == 4


# ------------------------------------------------------------------ live


@pytest.mark.live
def test_live_french_download(tmp_path: Path) -> None:
    df = load_ff5_daily(refresh=True, data_dir=tmp_path)
    st = factor_status(tmp_path)
    assert st is not None
    assert st.last_date >= date(2026, 1, 1)
    assert st.first_date == date(1963, 7, 1)
    assert list(df.columns) == [*FACTOR_COLUMNS, "RF"]
    assert len(df) >= 15_000
    assert df.index.is_monotonic_increasing and df.index.is_unique
    assert df["Mkt-RF"].abs().max() < 0.2
    assert df["RF"].abs().max() < 0.01
