"""Ken French portfolio-file parser and cache (spec SB11: TSB09 parser part, TSB11; SB2.3 vintage).

Fixtures are small synthetic files in the library's layout (preamble, three titled blocks, latin-1).
"""

from __future__ import annotations

import dataclasses
import io
import json
import zipfile
from datetime import UTC, date, datetime
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from factordesk import cli
from factordesk.api.main import create_app
from factordesk.data import portfolios as pf
from factordesk.data.factors import FactorDownloadError, FactorStatus
from factordesk.data.portfolios import (
    DATASETS,
    PortfolioError,
    extract_csv,
    load_portfolio_frames,
    parse_portfolio_csv,
    refresh_portfolio_frames,
)
from factordesk.tests.test_api_basic import (
    FakeFactors,
    assert_api_error,
    make_deps,
    make_status,
    serve,
)

NOW = datetime(2026, 11, 18, 12, 0, tzinfo=UTC)
REAL_GAP_S = pf.DOWNLOAD_GAP_S


def _block(title: str, names: list[str], rows: list[tuple[str, list[str]]]) -> str:
    head = "," + ",".join(names)
    body = "\n".join(f"{d},{','.join(v)}" for d, v in rows)
    return f"  {title}\n{head}\n{body}\n\n"


def _csv(
    n_rows: int = 6,
    names: tuple[str, ...] = ("Agric", "Food ", "Soda"),
    *,
    vw_shift: float = 0.0,
    stamp: str = "202609",
) -> bytes:
    dates = [str(20260101 + i) for i in range(n_rows)]
    vw = [
        (d, [f"{vw_shift + 0.1 * (i + j):.2f}" for j in range(len(names))])
        for i, d in enumerate(dates)
    ]
    ew = [(d, ["9.99"] * len(names)) for d in dates]
    nf = [(d, ["100"] * len(names)) for d in dates]
    text = (
        f" This file was created by CMPT_IND_RETS_DAILY using the {stamp} CRSP database. "
        "It\x92s a fixture.\n\n"
        + _block("Average Value Weighted Returns -- Daily", list(names), vw)
        + _block("Average Equal Weighted Returns -- Daily", list(names), ew)
        + _block("Number of Firms in Portfolios", list(names), nf)
        + " \xa9 2026 Eugene F. Fama and Kenneth R. French\n"
    )
    return text.encode("latin-1")


def _zip(payload: bytes, name: str = "x.csv") -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(name, payload)
    return buf.getvalue()


# ------------------------------------------------------------------------------------- parser
def test_tsb11_reads_only_the_value_weighted_block() -> None:
    parsed = parse_portfolio_csv(_csv(), min_rows=1)
    assert list(parsed.frame.columns) == ["Agric", "Food", "Soda"]
    assert len(parsed.frame) == 6
    # Values are percent in the file: 0.10 -> 0.001. Equal-weighted 9.99 and counts never enter.
    assert parsed.frame.iloc[1, 0] == pytest.approx(0.001)
    assert float(np.nanmax(parsed.frame.to_numpy())) < 0.02
    assert parsed.crsp_stamp == "202609"
    assert parsed.frame.index.name == "date"


def test_tsb11_other_titles_select_other_blocks() -> None:
    parsed = parse_portfolio_csv(
        _csv(), title="Average Equal Weighted Returns -- Daily", min_rows=1
    )
    assert float(parsed.frame.to_numpy()[0, 0]) == pytest.approx(0.0999)


def test_tsb11_latin1_preamble_and_zip_input() -> None:
    raw = _csv()
    with pytest.raises(UnicodeDecodeError):
        raw.decode("utf-8")  # the fixture has non-UTF-8 bytes, like the ME_OP file
    from_zip = parse_portfolio_csv(_zip(raw), min_rows=1)
    assert from_zip.frame.equals(parse_portfolio_csv(raw, min_rows=1).frame)


def test_tsb11_missing_block_and_bad_header() -> None:
    with pytest.raises(PortfolioError, match="not found"):
        parse_portfolio_csv(b"nothing here\n", min_rows=1)
    bad = b"  Average Value Weighted Returns -- Daily\nAgric,Food\n20260101,1,2\n"
    with pytest.raises(PortfolioError, match="no header"):
        parse_portfolio_csv(bad, min_rows=1)


def test_tsb09_sentinels_become_nan_and_real_values_stay() -> None:
    raw = _csv().decode("latin-1")
    lines = raw.splitlines()
    vw_first = next(i for i, ln in enumerate(lines) if ln.startswith("20260101,"))
    lines[vw_first] = "20260101,-99.99,-999,-9.99"
    lines[vw_first + 1] = "20260102,-0.50,0.25,-99.99"
    parsed = parse_portfolio_csv("\n".join(lines).encode("latin-1"), min_rows=1)
    first = parsed.frame.iloc[0]
    assert np.isnan(first["Agric"]) and np.isnan(first["Food"])
    assert first["Soda"] == pytest.approx(-0.0999)
    second = parsed.frame.iloc[1]
    assert second["Agric"] == pytest.approx(-0.005)
    assert np.isnan(second["Soda"])
    assert int(parsed.frame.isna().sum().sum()) == 3


def test_parser_validation_errors() -> None:
    good = _csv().decode("latin-1")
    first_row = next(ln for ln in good.splitlines() if ln.startswith("20260101,"))
    with pytest.raises(PortfolioError, match="at least"):
        parse_portfolio_csv(good.encode("latin-1"), min_rows=7)
    short = good.replace(first_row, "20260101,1.0,2.0", 1)
    with pytest.raises(PortfolioError, match="fields"):
        parse_portfolio_csv(short.encode("latin-1"), min_rows=1)
    bad_date = good.replace("20260101,", "20260230,", 1)
    with pytest.raises(PortfolioError, match="bad value"):
        parse_portfolio_csv(bad_date.encode("latin-1"), min_rows=1)
    dup = good.replace("20260102,", "20260101,", 1)
    with pytest.raises(PortfolioError, match="strictly increasing"):
        parse_portfolio_csv(dup.encode("latin-1"), min_rows=1)
    huge = good.replace(first_row, "20260101,9999.0,1.0,1.0", 1)
    with pytest.raises(PortfolioError, match="implausibly"):
        parse_portfolio_csv(huge.encode("latin-1"), min_rows=1)
    twice = good.replace("Food ", "Agric", 1)
    with pytest.raises(PortfolioError, match="repeated"):
        parse_portfolio_csv(twice.encode("latin-1"), min_rows=1)


def test_extract_csv_rejects_bad_zips() -> None:
    with pytest.raises(PortfolioError, match="not a valid zip"):
        extract_csv(b"PK\x03\x04junk")
    two = io.BytesIO()
    with zipfile.ZipFile(two, "w") as zf:
        zf.writestr("a.csv", b"1")
        zf.writestr("b.csv", b"2")
    with pytest.raises(PortfolioError, match="found 2"):
        extract_csv(two.getvalue())
    with pytest.raises(PortfolioError, match="cap"):
        extract_csv(_zip(b"x" * 100), max_bytes=10)


def test_stamp_is_none_without_a_preamble_stamp() -> None:
    raw = _csv().decode("latin-1").replace("202609 CRSP database", "a database")
    assert parse_portfolio_csv(raw.encode("latin-1"), min_rows=1).crsp_stamp is None


# ---------------------------------------------------------------------------------- cache
@pytest.fixture(autouse=True)
def _reset_attempts(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pf, "_LAST_ATTEMPT", {})
    monkeypatch.setattr(pf, "DOWNLOAD_GAP_S", 0.001)  # keep the tests fast; see the gap test
    monkeypatch.setattr(pf, "MIN_ROWS", 1)
    monkeypatch.setattr(pf, "parse_portfolio_csv", _parse_small)


def _parse_small(raw: bytes, **kw: object) -> pf.ParsedPortfolios:
    return parse_portfolio_csv(raw, min_rows=1)


class FakeFetch:
    def __init__(self, payload: bytes | None = None, *, fail: bool = False) -> None:
        self.payload = _zip(_csv()) if payload is None else payload
        self.fail = fail
        self.urls: list[str] = []

    def __call__(
        self, url: str, if_modified_since: str | None = None
    ) -> tuple[bytes | None, str | None]:
        self.urls.append(url)
        if self.fail:
            raise PortfolioError("offline")
        return self.payload, "Tue, 27 Oct 2026 12:00:00 GMT"


def test_download_caches_and_stamps_each_frame(tmp_path: Path) -> None:
    fetch = FakeFetch()
    frames = load_portfolio_frames(tmp_path, NOW, fetch)
    assert set(frames) == set(DATASETS)
    assert len(fetch.urls) == 4 and all(u.startswith(pf.BASE_URL) for u in fetch.urls)
    attrs = frames["ind49_daily"].attrs
    assert attrs["crsp_stamp"] == "202609"
    assert len(attrs["sha256"]) == 64
    assert attrs["last_modified"] == "Tue, 27 Oct 2026 12:00:00 GMT"
    meta = json.loads((tmp_path / "portfolios" / "ind49_daily.json").read_text(encoding="utf-8"))
    assert meta["rows"] == 6 and meta["last_date"] == "2026-01-06"


def test_fresh_cache_is_used_without_a_download(tmp_path: Path) -> None:
    load_portfolio_frames(tmp_path, datetime(2026, 1, 20, tzinfo=UTC), FakeFetch())
    again = FakeFetch()
    frames = load_portfolio_frames(tmp_path, datetime(2026, 1, 21, tzinfo=UTC), again)
    assert again.urls == []
    assert frames["me_op25_daily"].attrs["crsp_stamp"] == "202609"
    assert frames["me_op25_daily"].shape == (6, 3)


def test_stale_cache_refreshes_once_per_twelve_hours(tmp_path: Path) -> None:
    load_portfolio_frames(tmp_path, datetime(2026, 1, 20, tzinfo=UTC), FakeFetch())
    stale_now = datetime(2026, 11, 18, 12, tzinfo=UTC)
    failing = FakeFetch(fail=True)
    frames = load_portfolio_frames(tmp_path, stale_now, failing)
    assert len(failing.urls) == 4 and set(frames) == set(DATASETS)  # served from the cache
    again = FakeFetch(fail=True)
    load_portfolio_frames(tmp_path, stale_now.replace(hour=13), again)
    assert again.urls == []  # the retry gate holds for 12 hours
    later = FakeFetch()
    load_portfolio_frames(tmp_path, stale_now.replace(hour=13) + pd.Timedelta(hours=12), later)
    assert len(later.urls) == 4


def test_failed_first_download_leaves_the_key_out(tmp_path: Path) -> None:
    frames = load_portfolio_frames(tmp_path, NOW, FakeFetch(fail=True))
    assert frames == {}
    assert not (tmp_path / "portfolios").exists() or not list((tmp_path / "portfolios").iterdir())


def test_bad_download_does_not_replace_a_good_cache(tmp_path: Path) -> None:
    load_portfolio_frames(tmp_path, datetime(2026, 1, 20, tzinfo=UTC), FakeFetch())
    path = tmp_path / "portfolios" / "ind49_daily.parquet"
    before = path.read_bytes()
    broken = FakeFetch(payload=_zip(b"not a portfolio file"))
    frames = load_portfolio_frames(tmp_path, datetime(2026, 11, 18, tzinfo=UTC), broken)
    assert path.read_bytes() == before
    assert set(frames) == set(DATASETS)


def test_subset_of_keys() -> None:
    assert set(DATASETS) == {"ind49_daily", "me_bm25_daily", "me_op25_daily", "me_inv25_daily"}


# -------------------------------------------------------------------------------- freshness
class SinceFetch(FakeFetch):
    """``FakeFetch`` that records the ``If-Modified-Since`` it was given and can answer 304."""

    def __init__(self, payload: bytes | None = None, *, not_modified: bool = False) -> None:
        super().__init__(payload)
        self.not_modified = not_modified
        self.since: list[str | None] = []

    def __call__(
        self, url: str, if_modified_since: str | None = None
    ) -> tuple[bytes | None, str | None]:
        self.since.append(if_modified_since)
        if self.not_modified and if_modified_since is not None:
            self.urls.append(url)
            return None, if_modified_since
        return super().__call__(url, if_modified_since)


class Sleeps:
    def __init__(self) -> None:
        self.calls: list[float] = []

    def __call__(self, seconds: float) -> None:
        self.calls.append(seconds)


JAN = datetime(2026, 1, 20, tzinfo=UTC)


def test_cached_files_are_refreshed_when_the_factor_vintage_moves_on(tmp_path: Path) -> None:
    load_portfolio_frames(tmp_path, JAN, FakeFetch())  # cache ends 2026-01-06
    later = JAN + pd.Timedelta(days=2)
    same = FakeFetch()
    load_portfolio_frames(tmp_path, later, same, factor_last_date=date(2026, 1, 6))
    assert same.urls == []  # the factor file ends on the same day: one vintage
    newer = FakeFetch()
    pauses = Sleeps()
    # inside the 12 hour gate nothing is downloaded, even for a newer factor file
    load_portfolio_frames(
        tmp_path, JAN + pd.Timedelta(hours=1), newer, factor_last_date=date(2026, 2, 3)
    )
    assert newer.urls == []
    load_portfolio_frames(tmp_path, later, newer, factor_last_date=date(2026, 2, 3), sleep=pauses)
    assert len(newer.urls) == 4
    assert pauses.calls == [pf.DOWNLOAD_GAP_S] * 3  # one after the other, with a pause between


def test_stale_file_is_checked_with_the_cached_last_modified(tmp_path: Path) -> None:
    load_portfolio_frames(tmp_path, JAN, FakeFetch())
    path = tmp_path / "portfolios" / "ind49_daily.parquet"
    before = path.read_bytes()
    sha_before = json.loads((path.with_suffix(".json")).read_text(encoding="utf-8"))["sha256"]
    fetch = SinceFetch(not_modified=True)
    stale_now = datetime(2026, 11, 18, 12, tzinfo=UTC)
    frames = load_portfolio_frames(tmp_path, stale_now, fetch, sleep=Sleeps())
    assert set(frames) == set(DATASETS)
    assert fetch.since == ["Tue, 27 Oct 2026 12:00:00 GMT"] * 4
    assert path.read_bytes() == before  # not transferred again, not rewritten
    meta = json.loads(path.with_suffix(".json").read_text(encoding="utf-8"))
    assert meta["sha256"] == sha_before and meta["downloaded_at"].startswith("2026-11-18")
    assert frames["ind49_daily"].attrs["sha256"] == sha_before


def test_refresh_checks_every_file_one_after_the_other_and_updates_the_stamps(
    tmp_path: Path,
) -> None:
    load_portfolio_frames(tmp_path, JAN, FakeFetch())
    fetch = SinceFetch(payload=_zip(_csv(n_rows=8, vw_shift=1.0)))
    pauses = Sleeps()
    now = JAN + pd.Timedelta(hours=1)  # the 12 hour gate does not apply to a manual refresh
    frames = refresh_portfolio_frames(tmp_path, now, fetch, sleep=pauses)
    assert len(fetch.urls) == 4 and pauses.calls == [pf.DOWNLOAD_GAP_S] * 3
    assert all(since is not None for since in fetch.since)
    assert frames["ind49_daily"].shape == (8, 3)
    meta = json.loads((tmp_path / "portfolios" / "ind49_daily.json").read_text(encoding="utf-8"))
    assert meta["rows"] == 8 and meta["last_date"] == "2026-01-08"
    assert meta["downloaded_at"].startswith("2026-01-20T01")
    again = load_portfolio_frames(tmp_path, now, FakeFetch(fail=True))
    assert again["ind49_daily"].shape == (8, 3)  # what the refresh wrote is what is served


def test_refresh_fails_with_a_plain_sentence_and_stops_at_the_first_failure(
    tmp_path: Path,
) -> None:
    load_portfolio_frames(tmp_path, JAN, FakeFetch())
    path = tmp_path / "portfolios" / "ind49_daily.parquet"
    before = path.read_bytes()
    failing = SinceFetch()
    failing.fail = True
    pauses = Sleeps()
    with pytest.raises(PortfolioError) as caught:
        refresh_portfolio_frames(tmp_path, JAN + pd.Timedelta(hours=2), failing, sleep=pauses)
    message = str(caught.value)
    assert message.startswith("The Ken French portfolio files could not be downloaded")
    assert "network connection" in message and message.endswith(".")
    assert len(failing.urls) == 1 and pauses.calls == []  # the site is not hammered
    assert path.read_bytes() == before  # the cache is untouched


def test_refresh_with_a_broken_file_keeps_the_cache(tmp_path: Path) -> None:
    load_portfolio_frames(tmp_path, JAN, FakeFetch())
    path = tmp_path / "portfolios" / "ind49_daily.parquet"
    before = path.read_bytes()
    with pytest.raises(PortfolioError):
        refresh_portfolio_frames(
            tmp_path, JAN + pd.Timedelta(hours=2), SinceFetch(payload=_zip(b"junk")), sleep=Sleeps()
        )
    assert path.read_bytes() == before


# ----------------------------------------------------------- wiring: CLI, API and default deps
def test_cli_factor_refresh_refreshes_the_portfolio_files_too(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    order: list[str] = []
    status = FactorStatus(date(2026, 9, 30), date(1963, 7, 1), 49, NOW, "u", True)

    def fake_load(refresh: bool = False, now: datetime | None = None) -> pd.DataFrame:
        order.append("factors")
        return pd.DataFrame()

    def fake_portfolios(
        data_dir: Path, now: datetime, *a: object, **k: object
    ) -> dict[str, object]:
        order.append(f"portfolios:{data_dir.name}")
        return {}

    monkeypatch.setattr(cli, "get_settings", lambda: SimpleNamespace(data_dir=tmp_path / "d"))
    monkeypatch.setattr(cli, "load_ff5_daily", fake_load)

    def factor_status_stub(**kwargs: object) -> FactorStatus:
        return status

    monkeypatch.setattr(cli, "factor_status", factor_status_stub)

    monkeypatch.setattr(cli, "refresh_portfolio_frames", fake_portfolios)
    assert cli.main(["factors", "refresh"], now=NOW) == cli.EXIT_OK
    assert order == ["factors", "portfolios:d"]
    out = capsys.readouterr().out
    assert (
        "Factor file refreshed." in out and "Portfolio files for the shrunk betas refreshed." in out
    )

    def unreachable(*a: object, **k: object) -> dict[str, object]:
        raise PortfolioError("The Ken French portfolio files could not be downloaded (offline).")

    monkeypatch.setattr(cli, "refresh_portfolio_frames", unreachable)
    assert cli.main(["factors", "refresh"], now=NOW) == cli.EXIT_NETWORK
    err = capsys.readouterr().err
    assert err.count("\n") == 1 and "could not be downloaded" in err
    assert "The factor file was refreshed." in err


def test_api_refresh_runs_the_portfolio_refresh_after_the_factor_download(tmp_path: Path) -> None:
    order: list[str] = []
    fake = FakeFactors(make_status())
    deps, _, _ = make_deps(tmp_path, fake)
    original = fake.load

    def load(refresh: bool, now: datetime) -> pd.DataFrame:
        order.append("factors")
        return original(refresh, now)

    def record_portfolios(now: datetime) -> None:
        order.append("portfolios")

    deps = dataclasses.replace(
        deps,
        load_factors=load,
        refresh_portfolios=record_portfolios,
    )
    with serve(create_app(deps)) as client:
        response = client.post("/api/factors/refresh")
    assert response.status_code == 200 and response.json()["last_date"] == "2026-10-31"
    assert order == ["factors", "portfolios"]


def test_api_refresh_reports_unreachable_portfolio_files_as_a_network_error(
    tmp_path: Path,
) -> None:
    deps, _, _ = make_deps(tmp_path)

    def unreachable(now: datetime) -> None:
        raise FactorDownloadError("The Ken French portfolio files could not be downloaded.")

    deps = dataclasses.replace(deps, refresh_portfolios=unreachable)
    with serve(create_app(deps)) as client:
        assert_api_error(client.post("/api/factors/refresh"), 503, "network")


def test_default_deps_wire_the_portfolio_refresh_and_the_loader(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from factordesk.api import deps as deps_module
    from factordesk.section_hooks import shrunk as hook_module

    monkeypatch.setattr(deps_module, "get_settings", lambda: SimpleNamespace(data_dir=tmp_path))
    deps = deps_module.default_deps()
    assert deps.refresh_portfolios is not None and deps.load_section_inputs is not None
    seen: list[Path | None] = []

    def failing(now: datetime, *, data_dir: Path | None = None, fetch: object = None) -> None:
        seen.append(data_dir)
        raise PortfolioError("The Ken French portfolio files could not be downloaded (x).")

    monkeypatch.setattr(hook_module, "refresh_shrinkage_inputs", failing)
    with pytest.raises(FactorDownloadError, match="could not be downloaded"):
        deps.refresh_portfolios(NOW)
    assert seen == [tmp_path.resolve()]


def test_the_real_pause_between_downloads_is_at_least_a_second() -> None:
    assert REAL_GAP_S >= 1.0
