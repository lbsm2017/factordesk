"""Ken French data library: one loader for the factor files, daily or monthly.

Each file is described by a ``FrenchDataset`` entry in ``DATASETS`` (zip name, frequency, the
exact column header, row floor and plausibility bounds), so a new factor file is one entry, not
new code. Today: the Fama-French five factors, monthly. The momentum factor (``Mom``, daily and
monthly) and others are added the same way. The daily five-factor file keeps its own loader
(``data.factors.load_ff5_daily``), which this module does not change.

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
from factordesk.data.factors import FactorDataError, FactorDownloadError, FactorError

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


DATASETS: dict[str, FrenchDataset] = {
    "ff5_monthly": FrenchDataset(
        key="ff5_monthly",
        filename="F-F_Research_Data_5_Factors_2x3_CSV.zip",
        frequency="monthly",
        columns=("Mkt-RF", "SMB", "HML", "RMW", "CMA", "RF"),
        min_rows=600,
        max_abs_factor=1.0,
    ),
}
"""Every factor file this module can load, by key. Momentum is meant to join as
``"mom_daily"`` (``F-F_Momentum_Factor_daily_CSV.zip``, columns ``("Mom",)``) and
``"mom_monthly"`` (``F-F_Momentum_Factor_CSV.zip``): one entry each, no code change."""

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
    lines = raw.decode("latin-1").splitlines()
    stamp_match = next((m for ln in lines[:20] if (m := _STAMP.search(ln))), None)

    header_idx = next((i for i, ln in enumerate(lines) if ln.strip().startswith(",")), None)
    if header_idx is None:
        raise FactorDataError(
            f"{dataset.key}: no header row (a line starting with a comma) in the factor file"
        )
    tokens = [c.strip() for c in lines[header_idx].split(",")][1:]
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
