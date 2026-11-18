"""Ken French daily portfolio files for the prior of the shrunk betas (spec SB2.2, SB2.3).

Four zip files from the data library: the 49 industry portfolios and the three 5x5 size-sorted
sets (ME x BE/ME, ME x OP, ME x INV). Each holds several blocks (value-weighted returns,
equal-weighted returns, number of firms); only the block titled "Average Value Weighted Returns --
Daily" is read. Values are percent in the file and decimals here; ``-99.99`` and ``-999`` mark a
missing value and become NaN, never filled.

The parser is pure (bytes in, frame out). The cached download takes the clock, the HTTP fetcher and
the data directory as arguments, like ``data/factors.py``, so tests never touch the network. Each
returned frame carries its vintage (CRSP stamp, SHA-256, ``Last-Modified``) in ``frame.attrs``.
No portfolio data is committed to the repository.
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
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any, cast

import httpx
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

BASE_URL = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/"
DATASETS: dict[str, str] = {
    "ind49_daily": "49_Industry_Portfolios_daily_CSV.zip",
    "me_bm25_daily": "25_Portfolios_5x5_Daily_CSV.zip",
    "me_op25_daily": "25_Portfolios_ME_OP_5x5_daily_CSV.zip",
    "me_inv25_daily": "25_Portfolios_ME_INV_5x5_daily_CSV.zip",
}
"""Dataset key -> zip file name under ``BASE_URL`` (spec SB2.2 table)."""

VALUE_WEIGHTED_TITLE = "Average Value Weighted Returns -- Daily"
MIN_ROWS = 10_000
MAX_DECOMPRESSED_BYTES = 40 * 1024 * 1024
STALE_AFTER_DAYS = 40
RETRY_ATTEMPT_GAP = timedelta(hours=12)
DOWNLOAD_RETRIES = 3
DOWNLOAD_TIMEOUT_S = 60.0
SENTINELS: tuple[float, ...] = (-99.99, -999.0)
MAX_ABS_RETURN = 5.0
"""Largest plausible absolute daily portfolio return, decimal (a loose sanity bound)."""

_ZIP_MAGIC = b"PK\x03\x04"
_DATA_ROW = re.compile(r"^\s*\d{8}\s*,")
_STAMP = re.compile(r"\b(\d{6})\s+CRSP\s+database", re.IGNORECASE)
_USER_AGENT = "factordesk-portfolio-loader/0.1"

Fetcher = Callable[[str], tuple[bytes, str | None]]
"""``fetch(url) -> (content, Last-Modified header)``; raises ``PortfolioError`` on failure."""

_LAST_ATTEMPT: dict[Path, datetime] = {}


class PortfolioError(Exception):
    """A portfolio file is malformed, fails validation, or could not be downloaded."""


@dataclass(frozen=True)
class ParsedPortfolios:
    """The value-weighted block of one file."""

    frame: pd.DataFrame
    """Decimal daily returns, ``date`` index, one column per portfolio (NaN where missing)."""
    crsp_stamp: str | None
    """``YYYYMM`` of "the 202609 CRSP database" in the preamble, if present."""


def extract_csv(raw_zip: bytes, max_bytes: int = MAX_DECOMPRESSED_BYTES) -> bytes:
    """The single CSV member of an in-memory zip, with a decompressed-size cap."""
    try:
        zf = zipfile.ZipFile(io.BytesIO(raw_zip))
    except zipfile.BadZipFile as exc:
        raise PortfolioError(f"portfolio download is not a valid zip file: {exc}") from exc
    with zf:
        members = [i for i in zf.infolist() if i.filename.lower().endswith(".csv")]
        if len(members) != 1:
            raise PortfolioError(f"expected one .csv member in the zip, found {len(members)}")
        if members[0].file_size > max_bytes:
            raise PortfolioError(f"portfolio CSV is above the {max_bytes} byte cap")
        with zf.open(members[0]) as fh:
            data = fh.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise PortfolioError(f"portfolio CSV is above the {max_bytes} byte cap")
    return data


def parse_portfolio_csv(
    raw: bytes, *, title: str = VALUE_WEIGHTED_TITLE, min_rows: int = MIN_ROWS
) -> ParsedPortfolios:
    """Parse one block of a French portfolio CSV (or the zip holding it) into decimal returns.

    Pure and offline. ``raw`` is the CSV (latin-1: the preamble of some files holds a non-ASCII
    apostrophe) or its zip. Only the block whose title line equals ``title`` is read; the other
    blocks (equal-weighted, number of firms) never enter. Raises ``PortfolioError``.
    """
    if raw.startswith(_ZIP_MAGIC):
        raw = extract_csv(raw)
    lines = raw.decode("latin-1").splitlines()
    stamp = None
    preamble = next((m for ln in lines[:20] if (m := _STAMP.search(ln))), None)
    if preamble is not None:
        stamp = preamble.group(1)

    start = next((i for i, ln in enumerate(lines) if ln.strip() == title), None)
    if start is None:
        raise PortfolioError(f"block {title!r} not found in the portfolio file")
    header_idx = next((i for i in range(start + 1, len(lines)) if lines[i].strip()), None)
    if header_idx is None or not lines[header_idx].strip().startswith(","):
        raise PortfolioError(f"no header row (a line starting with a comma) after {title!r}")
    names = [c.strip() for c in lines[header_idx].split(",")][1:]
    if not names or any(not nm for nm in names) or len(set(names)) != len(names):
        raise PortfolioError("portfolio header has empty or repeated names")

    stamps: list[str] = []
    rows: list[list[float]] = []
    for line_no, ln in enumerate(lines[header_idx + 1 :], start=header_idx + 2):
        if not _DATA_ROW.match(ln):
            if stamps:
                break  # the block ended at the first non-data line
            if ln.strip():
                raise PortfolioError(f"unexpected text before the data rows (line {line_no})")
            continue
        parts = [p.strip() for p in ln.split(",")]
        if len(parts) != len(names) + 1:
            raise PortfolioError(
                f"row on line {line_no} has {len(parts)} fields, expected {len(names) + 1}"
            )
        try:
            date(int(parts[0][:4]), int(parts[0][4:6]), int(parts[0][6:8]))
            rows.append([float(v) for v in parts[1:]])
        except ValueError as exc:
            raise PortfolioError(f"bad value on line {line_no}: {exc}") from exc
        stamps.append(parts[0])
    if len(rows) < min_rows:
        raise PortfolioError(f"block {title!r} has {len(rows)} rows; at least {min_rows} required")

    values = np.array(rows, dtype=np.float64)
    values[np.isin(values, SENTINELS)] = np.nan
    values = values / 100.0
    index = pd.DatetimeIndex(pd.to_datetime(stamps, format="%Y%m%d").to_numpy(), name="date")
    if not (index.is_unique and index.is_monotonic_increasing):
        raise PortfolioError("portfolio dates are not unique and strictly increasing")
    if bool((np.abs(values[np.isfinite(values)]) > MAX_ABS_RETURN).any()):
        raise PortfolioError("a portfolio return is implausibly large; check the file")
    return ParsedPortfolios(pd.DataFrame(values, index=index, columns=names), stamp)


# --------------------------------------------------------------------------- download and cache
def http_fetch(url: str) -> tuple[bytes, str | None]:
    """Download ``url`` with retries; returns the content and its ``Last-Modified`` header."""
    last_error = "unknown error"
    for attempt in range(DOWNLOAD_RETRIES + 1):
        if attempt:
            time.sleep(2.0**attempt)
        try:
            with httpx.Client(
                timeout=DOWNLOAD_TIMEOUT_S,
                follow_redirects=True,
                headers={"User-Agent": _USER_AGENT},
            ) as client:
                resp = client.get(url)
        except httpx.HTTPError as exc:
            last_error = f"network error: {exc!r}"
            continue
        if resp.status_code == 429 or resp.status_code >= 500:
            last_error = f"HTTP {resp.status_code}"
            continue
        if resp.status_code >= 400:
            raise PortfolioError(f"HTTP {resp.status_code} error downloading {url}")
        return resp.content, resp.headers.get("last-modified")
    raise PortfolioError(f"failed to download {url}: {last_error}")


def _dir(data_dir: Path) -> Path:
    return Path(data_dir) / "portfolios"


def _atomic_write(path: Path, payload: bytes) -> None:
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(payload)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def _read_cache(pdir: Path, key: str) -> tuple[pd.DataFrame, dict[str, Any]] | None:
    try:
        meta_raw: Any = json.loads((pdir / f"{key}.json").read_text(encoding="utf-8"))
        frame = pd.read_parquet(pdir / f"{key}.parquet")
    except (OSError, ValueError):
        return None
    if not isinstance(meta_raw, dict):
        return None
    frame.index = pd.DatetimeIndex(frame.index, name="date")
    return frame, cast(dict[str, Any], meta_raw)


def _stamped(frame: pd.DataFrame, key: str, meta: Mapping[str, Any]) -> pd.DataFrame:
    frame.attrs = {
        "key": key,
        "crsp_stamp": meta.get("crsp_stamp"),
        "sha256": meta.get("sha256"),
        "last_modified": meta.get("last_modified"),
    }
    return frame


def _refresh(pdir: Path, key: str, now: datetime, fetch: Fetcher) -> pd.DataFrame:
    _LAST_ATTEMPT[pdir / key] = now
    raw_zip, last_modified = fetch(BASE_URL + DATASETS[key])
    parsed = parse_portfolio_csv(raw_zip)
    pdir.mkdir(parents=True, exist_ok=True)
    buf = io.BytesIO()
    parsed.frame.to_parquet(buf)
    meta: dict[str, Any] = {
        "key": key,
        "source_url": BASE_URL + DATASETS[key],
        "downloaded_at": now.astimezone(UTC).isoformat(),
        "last_modified": last_modified,
        "sha256": hashlib.sha256(raw_zip).hexdigest(),
        "crsp_stamp": parsed.crsp_stamp,
        "rows": len(parsed.frame),
        "first_date": cast(pd.Timestamp, parsed.frame.index[0]).date().isoformat(),
        "last_date": cast(pd.Timestamp, parsed.frame.index[-1]).date().isoformat(),
    }
    _atomic_write(pdir / f"{key}.parquet", buf.getvalue())
    _atomic_write(pdir / f"{key}.json", json.dumps(meta, indent=2).encode("utf-8"))
    return _stamped(parsed.frame, key, meta)


def _stale(meta: Mapping[str, Any], now: datetime) -> bool:
    try:
        last = date.fromisoformat(str(meta["last_date"]))
    except (KeyError, ValueError):
        return True
    return (now.astimezone(UTC).date() - last).days > STALE_AFTER_DAYS


def _retry_allowed(pdir: Path, key: str, meta: Mapping[str, Any] | None, now: datetime) -> bool:
    attempts: list[datetime] = []
    last = _LAST_ATTEMPT.get(pdir / key)
    if last is not None:
        attempts.append(last)
    if meta is not None and meta.get("downloaded_at"):
        with contextlib.suppress(ValueError):
            attempts.append(datetime.fromisoformat(str(meta["downloaded_at"])))
    return not attempts or now - max(attempts) > RETRY_ATTEMPT_GAP


def load_portfolio_frames(
    data_dir: Path,
    now: datetime,
    fetch: Fetcher | None = None,
    keys: tuple[str, ...] = tuple(DATASETS),
) -> dict[str, pd.DataFrame]:
    """The cached portfolio frames by dataset key, downloading what is missing or stale.

    A file that is cached and at most 40 days behind ``now`` is used as is. A stale or absent file
    is downloaded at most once every 12 hours (per process); when that fails, the cached copy is
    served if there is one, and otherwise the key is left out. The caller decides what a missing key
    means (the prior is then unavailable); this function never raises for data reasons.
    """
    getter = http_fetch if fetch is None else fetch
    pdir = _dir(data_dir)
    out: dict[str, pd.DataFrame] = {}
    for key in keys:
        cached = _read_cache(pdir, key)
        meta = None if cached is None else cached[1]
        if cached is not None and meta is not None and not _stale(meta, now):
            out[key] = _stamped(cached[0], key, meta)
            continue
        if _retry_allowed(pdir, key, meta, now):
            try:
                out[key] = _refresh(pdir, key, now, getter)
                continue
            except (PortfolioError, httpx.HTTPError, OSError) as exc:
                logger.warning("Portfolio file %s could not be refreshed: %s", key, exc)
        if cached is not None and meta is not None:
            out[key] = _stamped(cached[0], key, meta)
    return out
