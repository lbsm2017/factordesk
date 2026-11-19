"""Ken French data library: one loader for the factor files, daily or monthly.

Each file is described by a ``FrenchDataset`` entry in ``DATASETS`` (zip name, frequency, the
exact column header, row floor and plausibility bounds), so a new factor file is one entry, not
new code. Today: the Fama-French five factors, monthly, and the momentum factor (``Mom``), daily
and monthly. The daily five-factor file keeps its own loader (``data.factors.load_ff5_daily``),
which this module does not change. ``load_ff6`` joins ``Mom`` to the five factors of either
frequency (``join_momentum``).

File layout (all factor files of the library share it): a free-text preamble; a header line that
starts with a comma (``,Mkt-RF,SMB,HML,RMW,CMA,RF``); one block of data rows whose first field is
the date (``YYYYMMDD`` daily, ``YYYYMM`` monthly); for monthly files a second block of annual rows
(``  2025, ...``, four-digit years) under the title "Annual Factors: January-December"; a
copyright line. Only the first block is read. The annual block is skipped because its four-digit
dates never match the monthly row pattern; any later block of six-digit (or eight-digit) rows is
refused as a malformed file.

Values are percent in the file and decimals here. ``-99.99`` and ``-999`` mark a missing value
and become NaN, never filled. Monthly rows are stamped with the calendar month-end
(``196307`` -> 1963-07-31), the convention ``analytics.sample`` aligns monthly returns on, and must
cover consecutive months.

The parser is pure (bytes in, frame out). The cached loader takes the clock, the HTTP fetcher and
the data directory as arguments, like ``data/factors.py``, so tests never touch the network. The
cache policy is the daily file's: refresh when there is no cache, on request, or when the data are
more than 40 days behind and the last attempt was over 12 hours ago; a failed automatic refresh
serves the cached copy. No factor data is committed to the repository.
"""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
import logging
import os
import re
import tempfile
import time
import zipfile
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any, Literal, cast

import httpx
import numpy as np
import pandas as pd

from factordesk.config import get_settings
from factordesk.data.factors import (
    ALL_COLUMNS,
    SOURCE_URL,
    FactorDataError,
    FactorDownloadError,
    FactorError,
    factor_status,
    load_ff5_daily,
)

logger = logging.getLogger(__name__)

Frequency = Literal["daily", "monthly"]

BASE_URL = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/"
SENTINELS: tuple[float, ...] = (-99.99, -999.0)
MAX_DECOMPRESSED_BYTES = 20 * 1024 * 1024
STALE_AFTER_DAYS = 40
RETRY_ATTEMPT_GAP = timedelta(hours=12)
DOWNLOAD_RETRIES = 3
DOWNLOAD_TIMEOUT_S = 30.0

_ZIP_MAGIC = b"PK\x03\x04"
_UTF8_BOM = b"\xef\xbb\xbf"
_ROW_PATTERN: dict[Frequency, re.Pattern[str]] = {
    "daily": re.compile(r"^\s*\d{8}\s*,"),
    "monthly": re.compile(r"^\s*\d{6}\s*,"),
}
_DATE_FORMAT: dict[Frequency, str] = {"daily": "%Y%m%d", "monthly": "%Y%m"}
_STAMP = re.compile(r"\b(\d{6})\s+CRSP\s+database", re.IGNORECASE)
_USER_AGENT = "factordesk-factor-loader/0.1"


@dataclass(frozen=True)
class FrenchDataset:
    """One factor file of the library and what a valid copy of it looks like."""

    key: str
    """Cache and lookup key, e.g. ``"ff5_monthly"``."""
    filename: str
    """Zip file name under ``BASE_URL``."""
    frequency: Frequency
    columns: tuple[str, ...]
    """The header tokens after the leading comma, exactly and in order (``RF`` included when the
    file has it). The returned frame has these column names."""
    min_rows: int
    """Fewer data rows than this means a truncated or wrong file."""
    max_abs_factor: float
    """Largest plausible absolute value of a factor column, decimal (a loose sanity bound)."""
    rf_bounds: tuple[float, float] = (-0.005, 0.03)
    """Plausible range of the ``RF`` column, decimal per period; unused when there is no RF."""
    aliases: Mapping[str, str] = field(default_factory=lambda: {})
    """Header token -> canonical column name, for files that renamed a column."""

    @property
    def url(self) -> str:
        return BASE_URL + self.filename


MOM = "Mom"
"""Column name of the momentum factor in the library's files and in the frames returned here."""
_MOM_ALIASES: Mapping[str, str] = {"MOM": MOM, "UMD": MOM, "Momentum": MOM}
"""Header spellings accepted for ``Mom`` (the preamble of the daily file says "MOM"; other
sources say "UMD"). Every token is stripped of blanks first, so ``",Mom   "`` also
matches."""

DATASETS: dict[str, FrenchDataset] = {
    "ff5_monthly": FrenchDataset(
        key="ff5_monthly",
        filename="F-F_Research_Data_5_Factors_2x3_CSV.zip",
        frequency="monthly",
        columns=("Mkt-RF", "SMB", "HML", "RMW", "CMA", "RF"),
        min_rows=600,
        max_abs_factor=1.0,
    ),
    # Momentum (research C1). Mom is a long-short spread with no RF column, so nothing is ever
    # subtracted from it. The daily file starts 1926-11-03, the monthly one 1927-01; the worst
    # values on record are about -18.5% (daily) and -52.6% (monthly, 1932), inside the bounds.
    "mom_daily": FrenchDataset(
        key="mom_daily",
        filename="F-F_Momentum_Factor_daily_CSV.zip",
        frequency="daily",
        columns=(MOM,),
        min_rows=20_000,
        max_abs_factor=0.5,
        aliases=_MOM_ALIASES,
    ),
    "mom_monthly": FrenchDataset(
        key="mom_monthly",
        filename="F-F_Momentum_Factor_CSV.zip",
        frequency="monthly",
        columns=(MOM,),
        min_rows=1_000,
        max_abs_factor=1.0,
        aliases=_MOM_ALIASES,
    ),
}
"""Every factor file this module can load, by key."""

Fetcher = Callable[[str], tuple[bytes, str | None]]
"""``fetch(url) -> (content, Last-Modified header)``; raises ``FactorDownloadError``."""

_LAST_ATTEMPT: dict[Path, datetime] = {}


# --------------------------------------------------------------------------- parsing
def extract_csv(raw_zip: bytes, max_bytes: int = MAX_DECOMPRESSED_BYTES) -> bytes:
    """The single CSV member of an in-memory zip, with a decompressed-size cap."""
    try:
        zf = zipfile.ZipFile(io.BytesIO(raw_zip))
    except zipfile.BadZipFile as exc:
        raise FactorDataError(f"factor download is not a valid zip file: {exc}") from exc
    with zf:
        members = [i for i in zf.infolist() if i.filename.lower().endswith(".csv")]
        if len(members) != 1:
            raise FactorDataError(f"expected one .csv member in the zip, found {len(members)}")
        if members[0].file_size > max_bytes:
            raise FactorDataError(f"factor CSV is above the {max_bytes} byte cap")
        with zf.open(members[0]) as fh:
            data = fh.read(max_bytes + 1)  # do not trust the declared size
    if len(data) > max_bytes:
        raise FactorDataError(f"factor CSV is above the {max_bytes} byte cap")
    return data


def _period_index(stamps: list[str], frequency: Frequency) -> pd.DatetimeIndex:
    """Daily stamps as dates; monthly ``YYYYMM`` stamps as calendar month-ends."""
    parsed = pd.to_datetime(stamps, format=_DATE_FORMAT[frequency])
    if frequency == "monthly":
        parsed = parsed + pd.offsets.MonthEnd(0)
    return pd.DatetimeIndex(parsed.to_numpy(), name="date")


def parse_french_block(
    raw: bytes,
    dataset: FrenchDataset,
    *,
    min_rows: int | None = None,
    today: date | None = None,
) -> pd.DataFrame:
    """Parse the first data block of a French factor file (or its zip) into decimal returns.

    Pure and offline. ``raw`` is the CSV bytes (latin-1) or the zip holding it. ``min_rows``
    overrides the dataset's floor (tests read short excerpts). No clock is read: the "last date
    in the future" check runs only when ``today`` is given. The frame carries the CRSP vintage
    stamp of the preamble, when present, in ``frame.attrs["crsp_stamp"]``. Raises
    ``FactorDataError`` on any structural or validation problem.
    """
    floor = dataset.min_rows if min_rows is None else min_rows
    if raw.startswith(_ZIP_MAGIC):
        raw = extract_csv(raw)
    raw = raw.removeprefix(_UTF8_BOM)
    lines = raw.decode("latin-1").splitlines()
    stamp_match = next((m for ln in lines[:20] if (m := _STAMP.search(ln))), None)

    header_idx = next((i for i, ln in enumerate(lines) if ln.strip().startswith(",")), None)
    if header_idx is None:
        raise FactorDataError(
            f"{dataset.key}: no header row (a line starting with a comma) in the factor file"
        )
    tokens = [c.strip() for c in lines[header_idx].split(",")][1:]  # also strips no-break spaces
    trailing_empty = 0
    while tokens and not tokens[-1]:  # a header that ends in a comma
        tokens.pop()
        trailing_empty += 1
    tokens = [dataset.aliases.get(t, t) for t in tokens]
    if tokens != list(dataset.columns):
        raise FactorDataError(
            f"{dataset.key}: unexpected columns {tokens}; expected exactly "
            f"{list(dataset.columns)} in this order"
        )

    pattern = _ROW_PATTERN[dataset.frequency]
    records: list[tuple[int, list[str]]] = []
    block_ended = False
    for line_no, ln in enumerate(lines[header_idx + 1 :], start=header_idx + 2):
        if pattern.match(ln):
            if block_ended:
                raise FactorDataError(
                    f"{dataset.key}: unexpected second block of {dataset.frequency} rows "
                    f"(line {line_no})"
                )
            parts = [p.strip() for p in ln.split(",")]
            if (
                trailing_empty
                and len(parts) > len(dataset.columns) + 1
                and not any(parts[len(dataset.columns) + 1 :])
            ):  # rows that end in the same trailing comma as the header
                parts = parts[: len(dataset.columns) + 1]
            if len(parts) != len(dataset.columns) + 1:
                raise FactorDataError(
                    f"{dataset.key}: row on line {line_no} has {len(parts)} fields, expected "
                    f"{len(dataset.columns) + 1}"
                )
            records.append((line_no, parts))
        elif records and ln.strip():
            block_ended = True  # the annual block, or the copyright line, starts here
    if len(records) < floor:
        raise FactorDataError(
            f"{dataset.key}: only {len(records)} data rows; at least {floor} required"
        )

    values = np.empty((len(records), len(dataset.columns)), dtype=np.float64)
    for row, (line_no, parts) in enumerate(records):
        try:
            _period_index([parts[0]], dataset.frequency)  # strict calendar date or month
        except ValueError as exc:
            raise FactorDataError(
                f"{dataset.key}: invalid date {parts[0]!r} on line {line_no}"
            ) from exc
        try:
            values[row] = [float(v) for v in parts[1:]]  # an empty cell is not a number
        except ValueError as exc:
            raise FactorDataError(
                f"{dataset.key}: non-numeric value on line {line_no}: {exc}"
            ) from exc
    index = _period_index([parts[0] for _, parts in records], dataset.frequency)
    sentinel = np.isin(values, SENTINELS)
    if sentinel.any():
        logger.warning(
            "%s: %d missing-value sentinels set to NaN", dataset.key, int(sentinel.sum())
        )
    values[sentinel] = np.nan
    frame = pd.DataFrame(values / 100.0, index=index, columns=list(dataset.columns))
    _validate(frame, dataset, today)
    frame.attrs = {"key": dataset.key, "crsp_stamp": stamp_match.group(1) if stamp_match else None}
    return frame


def _validate(frame: pd.DataFrame, dataset: FrenchDataset, today: date | None) -> None:
    index = pd.DatetimeIndex(frame.index)
    if index.has_duplicates:
        raise FactorDataError(
            f"{dataset.key}: duplicate date {index[index.duplicated()][0].date()}"
        )
    if not index.is_monotonic_increasing:
        bad = index[1:][np.asarray(index[1:] < index[:-1])][0]
        raise FactorDataError(f"{dataset.key}: dates are not increasing (at {bad.date()})")
    if dataset.frequency == "monthly" and len(index) > 1:
        months = index.to_period("M").asi8
        gaps = np.flatnonzero(np.diff(months) != 1)
        if gaps.size:
            after = pd.Timestamp(index[int(gaps[0])]).date()
            raise FactorDataError(f"{dataset.key}: months are not consecutive (after {after})")
    factor_cols = [c for c in dataset.columns if c != "RF"]
    factor_values = frame.loc[:, factor_cols].to_numpy(dtype=np.float64)
    finite = factor_values[np.isfinite(factor_values)]
    if finite.size and float(np.max(np.abs(finite))) > dataset.max_abs_factor:
        raise FactorDataError(
            f"{dataset.key}: factor value {float(np.max(np.abs(finite))):.4f} outside "
            f"[-{dataset.max_abs_factor}, {dataset.max_abs_factor}] (decimal)"
        )
    if "RF" in frame.columns:
        rf = frame["RF"].to_numpy(dtype=np.float64)
        lo, hi = dataset.rf_bounds
        if bool(((rf < lo) | (rf > hi)).any()):
            raise FactorDataError(f"{dataset.key}: RF outside [{lo}, {hi}] (decimal per period)")
    last = pd.Timestamp(index[-1]).date()
    if today is not None and last > today + timedelta(days=1):
        raise FactorDataError(f"{dataset.key}: last date {last} is in the future (today {today})")


# --------------------------------------------------------------------------- download
def http_get(url: str) -> tuple[bytes, str | None]:
    """Download ``url`` with retries; returns the content and its ``Last-Modified`` header.

    A 401 is not retried (the library asking for authentication is not transient).
    """
    last_error = "unknown error"
    headers = {"User-Agent": _USER_AGENT}
    for attempt in range(DOWNLOAD_RETRIES + 1):
        if attempt:
            time.sleep(2.0**attempt)
        try:
            with httpx.Client(
                timeout=DOWNLOAD_TIMEOUT_S, follow_redirects=True, headers=headers
            ) as client:
                resp = client.get(url)
        except httpx.HTTPError as exc:
            last_error = f"network error: {exc!r}"
            continue
        if resp.status_code == 401:
            raise FactorDownloadError(
                f"HTTP 401 Unauthorized from {url}: the French data library is requiring "
                "authentication; this is not a transient error, so it was not retried"
            )
        if resp.status_code == 429 or resp.status_code >= 500:
            last_error = f"HTTP {resp.status_code}"
            continue
        if resp.status_code >= 400:
            raise FactorDownloadError(f"HTTP {resp.status_code} error downloading {url}")
        return resp.content, resp.headers.get("last-modified")
    raise FactorDownloadError(
        f"failed to download {url} after {DOWNLOAD_RETRIES + 1} attempts: {last_error}"
    )


# --------------------------------------------------------------------------- cache
def _dir(data_dir: Path | None) -> Path:
    base = data_dir if data_dir is not None else get_settings().data_dir
    return Path(base) / "factors" / "french"


def _atomic_write(path: Path, payload: bytes) -> None:
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(payload)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def _read_cache(fdir: Path, key: str) -> tuple[pd.DataFrame, dict[str, Any]] | None:
    try:
        meta: Any = json.loads((fdir / f"{key}.json").read_text(encoding="utf-8"))
        frame = pd.read_parquet(fdir / f"{key}.parquet")
    except (OSError, ValueError) as exc:
        if (fdir / f"{key}.parquet").exists():
            logger.warning("Could not read the %s cache: %s", key, exc)
        return None
    if not isinstance(meta, dict):
        return None
    frame.index = pd.DatetimeIndex(frame.index, name="date")
    return frame, cast(dict[str, Any], meta)


def _stamped(frame: pd.DataFrame, meta: Mapping[str, Any]) -> pd.DataFrame:
    """The frame with its vintage in ``attrs`` (key, source, download time, hash, CRSP stamp)."""
    frame.attrs = {
        k: meta.get(k)
        for k in ("key", "source_url", "downloaded_at", "last_modified", "sha256", "crsp_stamp")
    }
    return frame


def _refresh(fdir: Path, dataset: FrenchDataset, now: datetime, fetch: Fetcher) -> pd.DataFrame:
    """Download, validate and atomically replace the cache; the cache is untouched on error."""
    _LAST_ATTEMPT[fdir / dataset.key] = now
    raw_zip, last_modified = fetch(dataset.url)
    frame = parse_french_block(raw_zip, dataset, today=now.astimezone(UTC).date())
    fdir.mkdir(parents=True, exist_ok=True)
    crsp_stamp = frame.attrs.get("crsp_stamp")
    buf = io.BytesIO()
    frame.attrs = {}
    frame.to_parquet(buf)
    meta: dict[str, Any] = {
        "key": dataset.key,
        "source_url": dataset.url,
        "downloaded_at": now.astimezone(UTC).isoformat(),
        "last_modified": last_modified,
        "sha256": hashlib.sha256(raw_zip).hexdigest(),
        "crsp_stamp": crsp_stamp,
        "rows": len(frame),
        "first_date": cast(pd.Timestamp, frame.index[0]).date().isoformat(),
        "last_date": cast(pd.Timestamp, frame.index[-1]).date().isoformat(),
    }
    # Parquet first, then meta; each replace is atomic and both payloads exist before either
    # file is touched, as for the daily factor file.
    _atomic_write(fdir / f"{dataset.key}.parquet", buf.getvalue())
    _atomic_write(fdir / f"{dataset.key}.json", json.dumps(meta, indent=2).encode("utf-8"))
    return _stamped(frame, meta)


def _stale(meta: Mapping[str, Any], now: datetime) -> bool:
    try:
        last = date.fromisoformat(str(meta["last_date"]))
    except (KeyError, ValueError):
        return True
    return (now.astimezone(UTC).date() - last).days > STALE_AFTER_DAYS


def _retry_allowed(fdir: Path, key: str, meta: Mapping[str, Any], now: datetime) -> bool:
    attempts: list[datetime] = []
    last = _LAST_ATTEMPT.get(fdir / key)
    if last is not None:
        attempts.append(last)
    if meta.get("downloaded_at"):
        with contextlib.suppress(ValueError):
            attempts.append(datetime.fromisoformat(str(meta["downloaded_at"])))
    return not attempts or now - max(attempts) > RETRY_ATTEMPT_GAP


# --------------------------------------------------------------------------- public API
def load_french(
    key: str,
    *,
    refresh: bool = False,
    data_dir: Path | None = None,
    now: datetime | None = None,
    fetch: Fetcher | None = None,
) -> pd.DataFrame:
    """The factor file ``key`` of ``DATASETS`` (decimals, French column names), from the cache.

    Downloads when there is no cache, when ``refresh`` is True, or when the cached data are more
    than 40 days behind ``now`` and the last attempt was over 12 hours ago. A failed forced or
    first download raises (``FactorError``); a failed automatic refresh logs a warning and
    returns the cached data. The vintage is in ``frame.attrs``.
    """
    if key not in DATASETS:
        raise KeyError(f"unknown French dataset {key!r}; known: {', '.join(DATASETS)}")
    dataset = DATASETS[key]
    now = now or datetime.now(UTC)
    getter = http_get if fetch is None else fetch
    fdir = _dir(data_dir)
    cached = _read_cache(fdir, key)
    if cached is None or refresh:
        return _refresh(fdir, dataset, now, getter)
    frame, meta = cached
    if _stale(meta, now) and _retry_allowed(fdir, key, meta, now):
        try:
            return _refresh(fdir, dataset, now, getter)
        except (FactorError, httpx.HTTPError, OSError) as exc:
            logger.warning("Automatic refresh of %s failed (%s); serving the cache", key, exc)
    return _stamped(frame, meta)


def load_ff5_monthly(
    refresh: bool = False,
    data_dir: Path | None = None,
    now: datetime | None = None,
    fetch: Fetcher | None = None,
) -> pd.DataFrame:
    """Fama-French five factors and RF, monthly (decimals, stamped at calendar month-ends)."""
    return load_french("ff5_monthly", refresh=refresh, data_dir=data_dir, now=now, fetch=fetch)


# --------------------------------------------------------------------------- FF6 (FF5 + Mom)
def _month_end_dates(index: pd.DatetimeIndex) -> bool:
    days = np.asarray(index.day, dtype=np.int64)
    return bool((days == np.asarray(index.days_in_month, dtype=np.int64)).all())


def _check_index(frame: pd.DataFrame, what: str) -> pd.DatetimeIndex:
    index = frame.index
    if not isinstance(index, pd.DatetimeIndex) or len(index) == 0:
        raise ValueError(f"{what}: needs a non-empty DatetimeIndex")
    if not index.is_unique or not index.is_monotonic_increasing:
        raise ValueError(f"{what}: dates must be unique and increasing")
    return index


def join_momentum(ff5: pd.DataFrame, mom: pd.DataFrame) -> pd.DataFrame:
    """The FF6 factor frame: the five factors and RF of ``ff5`` with ``Mom`` joined on date.

    Pure. Both frames have one frequency (daily, or monthly stamped at calendar month-ends) and
    the library's column names. ``Mom`` is a long-short spread and is copied as published: RF is
    never subtracted from it. The result covers the common window, from the later first date to
    the earlier last date of the two files, on the dates of the five-factor file. A five-factor
    date without a ``Mom`` value keeps ``Mom`` as NaN (never filled), so the sample builder
    excludes it with the reason "factor value missing".

    ``attrs`` records both vintages (``"ff5"``, ``"mom"``: the input frames' ``attrs``), the window
    (``"first_date"``, ``"last_date"``), which file ends it (``"ends_with"``: ``"ff5"``,
    ``"mom"`` or ``"both"``), ``"mom_missing_rows"`` (window dates of the five-factor file with
    no ``Mom`` value) and ``"mom_rows_without_ff5"`` (``Mom`` dates in the window that the
    five-factor file does not have; they are dropped).
    """
    ff5_index = _check_index(ff5, "five-factor frame")
    mom_index = _check_index(mom, "momentum frame")
    missing = [c for c in ALL_COLUMNS if c not in ff5.columns]
    if missing:
        raise ValueError(f"five-factor frame is missing columns {missing}")
    if MOM in ff5.columns:
        raise ValueError("the five-factor frame already has a Mom column")
    if MOM not in mom.columns:
        raise ValueError(f"momentum frame has no {MOM!r} column")
    monthly = _month_end_dates(ff5_index)
    if len(ff5_index) > 2 and len(mom_index) > 2 and monthly != _month_end_dates(mom_index):
        raise ValueError("the five-factor and momentum frames have different frequencies")

    first = max(ff5_index[0], mom_index[0])
    ff5_last, mom_last = ff5_index[-1], mom_index[-1]
    last = min(ff5_last, mom_last)
    if first > last:
        raise FactorDataError(
            f"the five-factor ({ff5_index[0].date()} to {ff5_last.date()}) and momentum "
            f"({mom_index[0].date()} to {mom_last.date()}) files do not overlap"
        )
    window = ff5.loc[(ff5_index >= first) & (ff5_index <= last), list(ALL_COLUMNS)]
    window = window.astype("float64")
    mom_values = mom[MOM].astype("float64")
    out = window.copy()
    out[MOM] = mom_values.reindex(window.index)
    out.index = pd.DatetimeIndex(out.index, name="date")

    in_window = mom_index[(mom_index >= first) & (mom_index <= last)]
    mom_only = int(len(in_window.difference(pd.DatetimeIndex(window.index))))
    n_missing = int(out[MOM].isna().sum())
    if mom_only or n_missing:
        logger.warning(
            "FF6 join: %d five-factor dates without Mom (kept as NaN), %d Mom dates without "
            "five-factor data (dropped)",
            n_missing,
            mom_only,
        )
    ends_with = "both" if ff5_last == mom_last else ("ff5" if ff5_last < mom_last else "mom")
    out.attrs = {
        "key": "ff6_monthly" if monthly else "ff6_daily",
        "ff5": dict(ff5.attrs),
        "mom": dict(mom.attrs),
        "first_date": pd.Timestamp(out.index[0]).date().isoformat(),
        "last_date": pd.Timestamp(out.index[-1]).date().isoformat(),
        "ends_with": ends_with,
        "mom_missing_rows": n_missing,
        "mom_rows_without_ff5": mom_only,
    }
    return out


def _ff5_daily_vintage(data_dir: Path | None, now: datetime | None) -> dict[str, Any]:
    status = factor_status(data_dir, now)
    if status is None:
        return {"key": "ff5_daily", "source_url": SOURCE_URL}
    return {
        "key": "ff5_daily",
        "source_url": status.source_url,
        "downloaded_at": (
            status.last_download_at.isoformat() if status.last_download_at is not None else None
        ),
        "first_date": status.first_date.isoformat(),
        "last_date": status.last_date.isoformat(),
    }


def load_ff6(
    frequency: Frequency,
    *,
    refresh: bool = False,
    data_dir: Path | None = None,
    now: datetime | None = None,
    fetch: Fetcher | None = None,
) -> pd.DataFrame:
    """FF5 + RF + ``Mom`` at ``frequency`` (decimals), from the caches (``join_momentum``).

    Daily: the five factors come from ``data.factors.load_ff5_daily`` (its own download path;
    ``fetch`` is not used for it) and ``Mom`` from ``"mom_daily"``. Monthly: ``"ff5_monthly"`` and
    ``"mom_monthly"``. Each file follows its own cache policy. The frame ends at the earlier last
    date of the two files; both vintages are in ``attrs`` (see ``join_momentum``).
    """
    if frequency == "daily":
        ff5 = load_ff5_daily(refresh=refresh, data_dir=data_dir, now=now).copy(deep=False)
        ff5.attrs.clear()
        ff5.attrs.update(_ff5_daily_vintage(data_dir, now))
        mom_key = "mom_daily"
    elif frequency == "monthly":
        ff5 = load_ff5_monthly(refresh=refresh, data_dir=data_dir, now=now, fetch=fetch)
        mom_key = "mom_monthly"
    else:
        raise ValueError(f"unknown frequency {frequency!r}; use 'daily' or 'monthly'")
    mom = load_french(mom_key, refresh=refresh, data_dir=data_dir, now=now, fetch=fetch)
    return join_momentum(ff5, mom)
