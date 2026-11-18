"""Fama-French 5-factor daily data: download, parse, validate, cache.

The source is Ken French's data library. Values in the file are percent; this module returns
decimals. Missing-value sentinels become NaN and are never filled.
"""

from __future__ import annotations

import hashlib
import io
import json
import logging
import os
import re
import tempfile
import time
import zipfile
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any, cast

import httpx
import numpy as np
import pandas as pd

from factordesk.config import get_settings

logger = logging.getLogger(__name__)

FACTOR_COLUMNS: tuple[str, ...] = ("Mkt-RF", "SMB", "HML", "RMW", "CMA")
ALL_COLUMNS: tuple[str, ...] = (*FACTOR_COLUMNS, "RF")

SOURCE_URL = (
    "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/"
    "F-F_Research_Data_5_Factors_2x3_daily_CSV.zip"
)

MIN_ROWS = 15_000
MAX_DECOMPRESSED_BYTES = 20 * 1024 * 1024
STALE_AFTER_DAYS = 40
RETRY_ATTEMPT_GAP = timedelta(hours=12)
DOWNLOAD_RETRIES = 3
DOWNLOAD_TIMEOUT_S = 30.0
REVISION_TOLERANCE = 5e-5
"""A cell is revised when it moves by more than half of the last published digit (M1.1)."""
SENTINELS: tuple[float, ...] = (-99.99, -999.0)
MAX_ABS_FACTOR = 0.5
"""Largest plausible absolute daily factor return, decimal (M1.1 step 8)."""
RF_BOUNDS: tuple[float, float] = (-0.0001, 0.002)
"""Plausible daily risk-free rate, decimal (M1.1 step 8)."""

_ZIP_MAGIC = b"PK\x03\x04"
_DATA_ROW = re.compile(r"^\s*\d{8}\s*,")
_USER_AGENT = "factordesk-factor-loader/0.1"

# Last attempt (success or failure) per cache directory, for the 12 h retry gate within a process.
_LAST_ATTEMPT: dict[Path, datetime] = {}


class FactorError(Exception):
    """Base class for factor data-layer errors."""


class FactorDataError(FactorError):
    """The factor file is malformed or fails validation."""


class FactorDownloadError(FactorError):
    """The factor file could not be downloaded."""


@dataclass(frozen=True)
class FactorStatus:
    last_date: date
    first_date: date
    days_behind: int
    last_download_at: datetime | None
    source_url: str
    stale: bool


# --------------------------------------------------------------------------- parsing


def _extract_csv_from_zip(raw_zip: bytes, max_bytes: int = MAX_DECOMPRESSED_BYTES) -> bytes:
    """Return the single CSV member of an in-memory zip, enforcing a decompressed-size cap."""
    try:
        zf = zipfile.ZipFile(io.BytesIO(raw_zip))
    except zipfile.BadZipFile as exc:
        raise FactorDataError(f"Factor download is not a valid zip file: {exc}") from exc
    with zf:
        members = [i for i in zf.infolist() if i.filename.lower().endswith(".csv")]
        if len(members) != 1:
            names = [i.filename for i in zf.infolist()]
            raise FactorDataError(
                f"Expected exactly one .csv member in the factor zip, found {len(members)}: {names}"
            )
        info = members[0]
        if info.file_size > max_bytes:
            raise FactorDataError(
                f"Factor CSV declares {info.file_size} bytes decompressed, above the "
                f"{max_bytes} byte cap"
            )
        # Do not trust the declared size: bound the actual read as well.
        with zf.open(info) as fh:
            data = fh.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise FactorDataError(f"Factor CSV exceeds the {max_bytes} byte decompressed cap")
    return data


def parse_french_csv(
    raw: bytes, *, min_rows: int | None = None, today: date | None = None
) -> pd.DataFrame:
    """Parse the French 5-factor daily CSV (or the zip containing it) into decimal returns.

    Pure and offline (methodology M1.1): ``raw`` is the CSV bytes; zip bytes are also accepted
    and read in memory. No clock is read: the "last date in the future" check runs only when
    ``today`` is given. Raises FactorDataError on any structural or validation problem.
    """
    min_rows = MIN_ROWS if min_rows is None else min_rows
    if raw.startswith(_ZIP_MAGIC):
        raw = _extract_csv_from_zip(raw)
    text = raw.decode("latin-1")
    lines = text.splitlines()

    # M1.1 step 3: the first line whose stripped text starts with a comma; exact tokens in order.
    header_idx = next((i for i, ln in enumerate(lines) if ln.strip().startswith(",")), None)
    if header_idx is None:
        raise FactorDataError("No header row (a line starting with a comma) found in factor file")
    tokens = [c.strip() for c in lines[header_idx].split(",")]
    if tokens != ["", *ALL_COLUMNS]:
        raise FactorDataError(
            f"Unexpected factor columns {tokens[1:]}; expected exactly {list(ALL_COLUMNS)} "
            "in this order"
        )

    # Steps 4-5: one contiguous block of data rows; anything that looks like data after the
    # block has ended is a second block, not more rows.
    records: list[tuple[int, list[str]]] = []
    block_ended = False
    for line_no, ln in enumerate(lines[header_idx + 1 :], start=header_idx + 2):
        if _DATA_ROW.match(ln):
            if block_ended:
                raise FactorDataError(f"unexpected second data block (line {line_no})")
            parts = [p.strip() for p in ln.split(",")]
            if len(parts) != len(ALL_COLUMNS) + 1:
                raise FactorDataError(
                    f"Row on line {line_no} has {len(parts)} fields, expected "
                    f"{len(ALL_COLUMNS) + 1}: {ln.strip()!r}"
                )
            records.append((line_no, parts))
        elif records and ln.strip():
            block_ended = True
    if len(records) < min_rows:
        raise FactorDataError(
            f"Factor file has only {len(records)} data rows; at least {min_rows} required"
        )

    rows: list[list[float]] = []
    for line_no, parts in records:
        stamp = parts[0]
        try:  # strict YYYYMMDD calendar date (the regex guarantees 8 digits)
            date(int(stamp[:4]), int(stamp[4:6]), int(stamp[6:8]))
        except ValueError as exc:
            raise FactorDataError(f"Invalid date {stamp!r} on line {line_no}") from exc
        try:
            rows.append([float(v) for v in parts[1:]])  # an empty cell is not a number (step 6)
        except ValueError as exc:
            raise FactorDataError(f"Non-numeric value on line {line_no}: {exc}") from exc
    values = np.array(rows, dtype="float64")

    dates = pd.to_datetime([parts[0] for _, parts in records], format="%Y%m%d")
    index = pd.DatetimeIndex(dates.to_numpy(), name="date")
    sentinel = np.isin(values, SENTINELS)
    if sentinel.any():
        cells = [
            f"{records[int(i)][1][0]} {ALL_COLUMNS[int(j)]}"
            for i, j in zip(*np.nonzero(sentinel), strict=True)
        ]
        logger.warning("French missing-value sentinels set to NaN: %s", ", ".join(cells))
    values[sentinel] = np.nan
    values = values / 100.0
    df = pd.DataFrame(values, index=index, columns=list(ALL_COLUMNS)).astype("float64")

    # Step 8: dates strictly increasing and unique; value bounds.
    if df.index.has_duplicates:
        dup = df.index[df.index.duplicated()][0]
        raise FactorDataError(f"Duplicate date in factor file: {dup.date()}")
    if not df.index.is_monotonic_increasing:
        bad = df.index[1:][np.asarray(df.index[1:] < df.index[:-1])][0]
        raise FactorDataError(f"Factor dates are not strictly increasing (at {bad.date()})")
    factor_values = df.loc[:, list(FACTOR_COLUMNS)].to_numpy()
    if bool((np.abs(factor_values) > MAX_ABS_FACTOR).any()):
        worst = float(np.nanmax(np.abs(factor_values)))
        raise FactorDataError(
            f"Factor value {worst:.4f} outside [-{MAX_ABS_FACTOR}, {MAX_ABS_FACTOR}] (decimal)"
        )
    rf = df["RF"].to_numpy()
    if bool(((rf < RF_BOUNDS[0]) | (rf > RF_BOUNDS[1])).any()):
        raise FactorDataError(f"RF outside {list(RF_BOUNDS)} (decimal per day)")

    last = cast(pd.Timestamp, df.index[-1]).date()
    if today is not None and last > today + timedelta(days=1):
        raise FactorDataError(f"Last factor date {last} is in the future (today is {today})")
    return df


# --------------------------------------------------------------------------- download


def _sleep(seconds: float) -> None:
    time.sleep(seconds)


def _download(url: str = SOURCE_URL) -> tuple[bytes, str | None]:
    """Download the zip; returns (content, Last-Modified header)."""
    last_error: str = "unknown error"
    headers = {"User-Agent": _USER_AGENT}
    for attempt in range(DOWNLOAD_RETRIES + 1):
        if attempt:
            _sleep(2.0**attempt)
        try:
            with httpx.Client(
                timeout=DOWNLOAD_TIMEOUT_S, follow_redirects=True, headers=headers
            ) as client:
                resp = client.get(url)
        except httpx.HTTPError as exc:
            last_error = f"network error: {exc!r}"
            logger.warning("Factor download attempt %d failed: %s", attempt + 1, last_error)
            continue
        if resp.status_code == 401:
            raise FactorDownloadError(
                f"HTTP 401 Unauthorized from {url}: the French data library is requiring "
                "authentication; this is not a transient error, so it was not retried"
            )
        if resp.status_code == 429 or resp.status_code >= 500:
            last_error = f"HTTP {resp.status_code}"
            logger.warning("Factor download attempt %d failed: %s", attempt + 1, last_error)
            continue
        if resp.status_code >= 400:
            raise FactorDownloadError(f"HTTP {resp.status_code} error downloading {url}")
        return resp.content, resp.headers.get("last-modified")
    raise FactorDownloadError(
        f"Failed to download {url} after {DOWNLOAD_RETRIES + 1} attempts: {last_error}"
    )


# --------------------------------------------------------------------------- cache


def _resolve_dir(data_dir: Path | None) -> Path:
    base = data_dir if data_dir is not None else get_settings().data_dir
    return Path(base) / "factors"


def _parquet_path(fdir: Path) -> Path:
    return fdir / "ff5_daily.parquet"


def _meta_path(fdir: Path) -> Path:
    return fdir / "meta.json"


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _read_meta(fdir: Path) -> dict[str, Any] | None:
    try:
        loaded: Any = json.loads(_meta_path(fdir).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return cast(dict[str, Any], loaded) if isinstance(loaded, dict) else None


def _read_cached_frame(fdir: Path) -> pd.DataFrame | None:
    path = _parquet_path(fdir)
    if not path.exists():
        return None
    try:
        df = pd.read_parquet(path)
    except Exception as exc:  # corrupt cache must not crash callers; treated as absent
        logger.warning("Could not read factor cache %s: %s", path, exc)
        return None
    df.index = pd.DatetimeIndex(df.index, name="date")
    return df


def _atomic_write_bytes(path: Path, payload: bytes) -> None:
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(payload)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def _write_cache(
    fdir: Path,
    df: pd.DataFrame,
    raw_zip: bytes,
    last_modified: str | None,
    now: datetime,
) -> None:
    fdir.mkdir(parents=True, exist_ok=True)
    buf = io.BytesIO()
    df.to_parquet(buf)
    first = cast(pd.Timestamp, df.index[0]).date()
    last = cast(pd.Timestamp, df.index[-1]).date()
    meta: dict[str, Any] = {
        "last_download_at": now.astimezone(UTC).isoformat(),
        "source_url": SOURCE_URL,
        "last_modified": last_modified,
        "sha256": hashlib.sha256(raw_zip).hexdigest(),
        "rows": len(df),
        "first_date": first.isoformat(),
        "last_date": last.isoformat(),
    }
    # Parquet first, then meta; each replace is atomic. Both payloads are fully built before
    # either file is touched, so a serialization failure cannot corrupt the cache.
    _atomic_write_bytes(_parquet_path(fdir), buf.getvalue())
    _atomic_write_bytes(_meta_path(fdir), json.dumps(meta, indent=2).encode("utf-8"))


def _log_revisions(old: pd.DataFrame, new: pd.DataFrame) -> None:
    common = old.index.intersection(new.index)  # pyright: ignore[reportUnknownMemberType]
    if len(common) == 0:
        return
    o = old.loc[common, list(ALL_COLUMNS)].to_numpy(dtype="float64")
    n = new.loc[common, list(ALL_COLUMNS)].to_numpy(dtype="float64")
    nan_changed = np.isnan(o) != np.isnan(n)
    both = ~np.isnan(o) & ~np.isnan(n)
    diff = np.where(both, np.abs(n - o), 0.0)
    value_changed = diff > REVISION_TOLERANCE
    changed_mask = nan_changed | value_changed
    changed = int(changed_mask.sum())
    if changed:
        rows = np.flatnonzero(changed_mask.any(axis=1))
        first = cast(pd.Timestamp, common[rows[0]]).date()
        last = cast(pd.Timestamp, common[rows[-1]]).date()
        logger.warning(
            "French factor data revised: %d historical values changed over %d overlapping dates "
            "(max abs difference %.3g; revised dates %s to %s)",
            changed,
            len(common),
            float(diff[value_changed].max()) if value_changed.any() else 0.0,
            first,
            last,
        )


def _refresh(fdir: Path, now: datetime) -> pd.DataFrame:
    """Download, validate, and atomically replace the cache. Leaves the cache intact on error."""
    _LAST_ATTEMPT[fdir] = now
    raw_zip, last_modified = _download(SOURCE_URL)
    df = parse_french_csv(raw_zip, today=now.astimezone(UTC).date())
    old = _read_cached_frame(fdir)
    if old is not None:
        _log_revisions(old, df)
    _write_cache(fdir, df, raw_zip, last_modified, now)
    return df


# --------------------------------------------------------------------------- public API


def _status_from(
    first: date, last: date, last_dl: datetime | None, source_url: str, now: datetime
) -> FactorStatus:
    days_behind = (now.astimezone(UTC).date() - last).days
    return FactorStatus(
        last_date=last,
        first_date=first,
        days_behind=days_behind,
        last_download_at=last_dl,
        source_url=source_url,
        stale=days_behind > STALE_AFTER_DAYS,
    )


def factor_status(data_dir: Path | None = None, now: datetime | None = None) -> FactorStatus | None:
    """Describe the cached factor data, or None if nothing is cached.

    ``stale`` reflects data age only (more than 40 days behind today). It stays True after a
    failed refresh; the 12 h retry gate is applied separately when deciding whether to refresh.
    """
    now = now or _utcnow()
    fdir = _resolve_dir(data_dir)
    meta = _read_meta(fdir)
    try:
        if meta is not None and _parquet_path(fdir).exists():
            dl_raw = meta.get("last_download_at")
            return _status_from(
                date.fromisoformat(str(meta["first_date"])),
                date.fromisoformat(str(meta["last_date"])),
                datetime.fromisoformat(str(dl_raw)) if dl_raw else None,
                str(meta.get("source_url", SOURCE_URL)),
                now,
            )
    except (KeyError, ValueError):
        logger.warning("Factor meta.json is malformed; falling back to the parquet cache")
    df = _read_cached_frame(fdir)
    if df is None or df.empty:
        return None
    return _status_from(
        cast(pd.Timestamp, df.index[0]).date(),
        cast(pd.Timestamp, df.index[-1]).date(),
        None,
        SOURCE_URL,
        now,
    )


def _should_auto_refresh(fdir: Path, status: FactorStatus, now: datetime) -> bool:
    if not status.stale:
        return False
    attempts = [t for t in (_LAST_ATTEMPT.get(fdir), status.last_download_at) if t is not None]
    if not attempts:
        return True
    return now - max(attempts) > RETRY_ATTEMPT_GAP


def load_ff5_daily(
    refresh: bool = False, data_dir: Path | None = None, now: datetime | None = None
) -> pd.DataFrame:
    """Load Fama-French 5 factors (daily, decimals), downloading when needed.

    Refreshes when there is no cache, when ``refresh`` is True, or when the cache is more than
    40 days behind and the last attempt was over 12 h ago. A failed forced or first download
    raises; a failed automatic refresh logs a warning and returns the cached data.
    """
    now = now or _utcnow()
    fdir = _resolve_dir(data_dir)
    cached = _read_cached_frame(fdir)
    status = factor_status(data_dir, now) if cached is not None else None

    if cached is None or status is None:
        return _refresh(fdir, now)
    if refresh:
        return _refresh(fdir, now)
    if _should_auto_refresh(fdir, status, now):
        try:
            return _refresh(fdir, now)
        except (FactorError, httpx.HTTPError, OSError) as exc:
            logger.warning(
                "Automatic factor refresh failed (%s); serving cached data through %s "
                "(%d days behind)",
                exc,
                status.last_date,
                status.days_behind,
            )
    return cached
