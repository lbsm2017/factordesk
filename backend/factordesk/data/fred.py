"""FRED series download: the Fed nominal broad dollar index for the macro section (E4).

The public CSV of one series is ``https://fred.stlouisfed.org/graph/fredgraph.csv?id=<SERIES>``:
a header line ``observation_date,<SERIES>`` (older files say ``DATE``) and one line per day. FRED
writes a missing value as ``.``; it is read as NaN and never filled. The file is cached per day
next to the price cache (``<data_dir>/fred/<SERIES>_<YYYY-MM-DD>.csv``), so one report build per
day downloads it at most once. When the download fails, the latest cached file of any day is used
and the result says so; with no cache, ``FredError`` is raised and the caller decides what to do
(the macro section runs without the dollar and says so).

``DTWEXBGS`` is the Federal Reserve nominal broad U.S. dollar index (26 trade-weighted
currencies, public domain, daily from 2006-01-02). It is a noon New York fixing. A positive
change means the dollar strengthened.
"""

from __future__ import annotations

import io
import logging
import os
import re
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import httpx
import numpy as np
import pandas as pd

from factordesk.config import get_settings

logger = logging.getLogger(__name__)

DOLLAR_SERIES = "DTWEXBGS"
"""FRED id of the Federal Reserve nominal broad U.S. dollar index."""
FRED_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={series}"
TIMEOUT_S = 8.0
ATTEMPTS = 2
_USER_AGENT = "factordesk-fred-loader/0.1"
_SERIES_RE = re.compile(r"^[A-Z0-9_]{1,32}$")
_DATE_COLUMNS = ("observation_date", "DATE")


_FAILED: dict[tuple[str, str, str], str] = {}
"""Downloads that failed, by (data folder, series, day), with the reason. In memory only: a failed
download is not tried again for the rest of the day, so a FRED outage costs one wait, not one per
report. A new day or a new process tries again."""


class FredError(Exception):
    """The series cannot be downloaded or read, and no cached copy exists."""


@dataclass(frozen=True)
class FredSeries:
    """One FRED series: the values by date (NaN where FRED has ``.``) and where they came from."""

    series_id: str
    values: pd.Series
    """Float values on a tz-naive, normalised, increasing, unique date index; NaN for ``.``."""
    note: str | None = None
    """Set when the download failed and an older cached file was used."""


def parse_fred_csv(text: str, series_id: str) -> pd.Series:
    """The values of a ``fredgraph.csv`` body; ``.`` (and an empty cell) is NaN.

    Raises ``FredError`` for a body that is not that file (an HTML error page, a missing column,
    unreadable dates or numbers, no usable value, a repeated or unordered date).
    """
    try:
        frame = pd.read_csv(io.StringIO(text), dtype=str, keep_default_na=False)
    except (pd.errors.ParserError, pd.errors.EmptyDataError) as exc:
        raise FredError(f"{series_id}: the file is not a CSV ({exc})") from exc
    date_col = next((c for c in _DATE_COLUMNS if c in frame.columns), None)
    if date_col is None or series_id not in frame.columns:
        raise FredError(f"{series_id}: the file has no {series_id} column")
    raw = frame[series_id].str.strip()
    raw = raw.where(~raw.isin(["", "."]), other="nan")
    try:
        values = raw.astype("float64")
        dates = pd.DatetimeIndex(pd.to_datetime(frame[date_col], format="%Y-%m-%d"), name="date")
    except (ValueError, TypeError) as exc:
        raise FredError(f"{series_id}: a date or a value cannot be read ({exc})") from exc
    series = pd.Series(values.to_numpy(dtype=np.float64), index=dates, name=series_id)
    if series.index.has_duplicates or not series.index.is_monotonic_increasing:
        raise FredError(f"{series_id}: dates are repeated or not in increasing order")
    if not np.isfinite(series.to_numpy()).any():
        raise FredError(f"{series_id}: the file holds no value")
    return series.astype("float64")


def _fetch(series_id: str) -> str:
    """Download the CSV text; raises ``FredError`` after ``ATTEMPTS`` failed tries."""
    url = FRED_URL.format(series=series_id)
    last = "unknown error"
    for _ in range(ATTEMPTS):
        try:
            with httpx.Client(
                timeout=TIMEOUT_S, follow_redirects=True, headers={"User-Agent": _USER_AGENT}
            ) as client:
                resp = client.get(url)
        except httpx.HTTPError as exc:
            last = f"network error: {exc!r}"
            continue
        if resp.status_code >= 400:
            last = f"HTTP {resp.status_code}"
            continue
        return resp.text
    raise FredError(f"{series_id}: download failed after {ATTEMPTS} attempts ({last})")


def _dir(data_dir: Path | None) -> Path:
    base = data_dir if data_dir is not None else get_settings().data_dir
    return Path(base) / "fred"


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".", suffix=".tmp")
    os.close(fd)
    tmp = Path(tmp_name)
    try:
        tmp.write_text(text, encoding="utf-8", newline="\n")
        os.replace(tmp, path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


def _cached_files(fdir: Path, series_id: str) -> list[Path]:
    """Cache files of the series, newest day last."""
    pattern = re.compile(rf"^{re.escape(series_id)}_\d{{4}}-\d{{2}}-\d{{2}}\.csv$")
    if not fdir.is_dir():
        return []
    return sorted(p for p in fdir.iterdir() if pattern.fullmatch(p.name))


def load_fred_series(
    series_id: str = DOLLAR_SERIES,
    *,
    data_dir: Path | None = None,
    now: datetime | None = None,
    fetch: Callable[[str], str] | None = None,
) -> FredSeries:
    """The series, from today's cache, else downloaded (and cached), else the latest old cache.

    Raises ``FredError`` when none of the three works. ``fetch`` replaces the download (tests).
    """
    if not _SERIES_RE.fullmatch(series_id):
        raise FredError(f"{series_id!r} is not a FRED series id")
    stamp = (now or datetime.now(UTC)).astimezone(UTC).date()
    fdir = _dir(data_dir)
    today_file = fdir / f"{series_id}_{stamp.isoformat()}.csv"
    if today_file.is_file():
        try:
            return FredSeries(series_id, parse_fred_csv(today_file.read_text("utf-8"), series_id))
        except (FredError, OSError):
            logger.warning("Unreadable FRED cache %s; downloading again", today_file.name)
    memo = (str(fdir), series_id, stamp.isoformat())
    if memo in _FAILED:
        return _from_old_cache(fdir, series_id, _FAILED[memo])
    try:
        text = (fetch or _fetch)(series_id)
        values = parse_fred_csv(text, series_id)
    except FredError as exc:
        _FAILED[memo] = str(exc)
        return _from_old_cache(fdir, series_id, str(exc))
    except Exception as exc:  # a failing injected or network layer must not stop the report
        logger.warning("FRED %s download failed", series_id, exc_info=True)
        reason = f"{type(exc).__name__}: {exc}"
        _FAILED[memo] = reason
        return _from_old_cache(fdir, series_id, reason)
    try:
        _atomic_write(today_file, text)
        for old in _cached_files(fdir, series_id):
            if old != today_file:
                old.unlink(missing_ok=True)
    except OSError:
        logger.warning("Could not write the FRED cache for %s", series_id, exc_info=True)
    return FredSeries(series_id, values)


def _from_old_cache(fdir: Path, series_id: str, why: str) -> FredSeries:
    for path in reversed(_cached_files(fdir, series_id)):
        try:
            values = parse_fred_csv(path.read_text("utf-8"), series_id)
        except (FredError, OSError):
            continue
        day = path.stem.rsplit("_", 1)[-1]
        return FredSeries(
            series_id, values, note=f"FRED could not be reached ({why}); used the copy of {day}."
        )
    raise FredError(why)
