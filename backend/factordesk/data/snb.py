"""Swiss National Bank data portal series download, with a per-day disk cache.

``load_snb_series(cube, item)`` returns one daily series of a cube as floats on a date index,
times ``scale`` (SNB rates come in percent, so the rate loaders use ``scale=0.01``). The file is
cached per day (``<data_dir>/snb/<cube>_<item>_<YYYY-MM-DD>.csv``). The download has an 8 s
timeout and two tries; a failure is remembered for the rest of the day (in memory), and the latest
cached file of any day is then used with a notice. With no cache, ``SnbError`` is raised.

The URL is ``https://data.snb.ch/api/cube/<cube>/data/csv/en?fromDate=1999-01-01&dimSel=D0(<item>)``.
``fromDate`` is required: without it the portal answers with the last few observations only. The
body is a semicolon-separated file: a few header lines (``CubeId``, ``PublishingDate``), a blank
line, then ``"Date";"D0";"Value"`` rows. Days without a value have an empty ``Value``.
"""

from __future__ import annotations

import io
import logging
import re
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pandas as pd

from factordesk.config import get_settings
from factordesk.data.fred import ATTEMPTS, TIMEOUT_S, atomic_write, cached_files

logger = logging.getLogger(__name__)

SNB_URL = "https://data.snb.ch/api/cube/{cube}/data/csv/en?fromDate={start}&dimSel=D0({item})"
HISTORY_START = "1999-01-01"
_USER_AGENT = "factordesk-snb-loader/0.1"

_FAILED: dict[tuple[str, str, str], str] = {}
"""Downloads that failed, with the reason, by (data folder, day, scope). The scope is ``*`` for
the whole SNB host (network error, timeout, HTTP 5xx: one outage costs one wait per day) or a
series name (HTTP 4xx: only that series is wrong)."""


class SnbError(Exception):
    """An SNB series cannot be downloaded or read, and no cached copy exists."""

    def __init__(self, message: str, *, host_down: bool = False) -> None:
        super().__init__(message)
        self.host_down = host_down


def parse_snb_csv(text: str, name: str, scale: float = 1.0) -> pd.Series:
    """The ``Value`` column of an SNB cube file, times ``scale``, by ``Date`` (daily cubes)."""
    lines = text.lstrip("﻿").splitlines()
    start = next((i for i, line in enumerate(lines) if line.startswith('"Date"')), None)
    if start is None:
        raise SnbError(f"{name}: the file has no data header")
    try:
        frame = pd.read_csv(
            io.StringIO("\n".join(lines[start:])), sep=";", usecols=["Date", "Value"]
        )
        dates = pd.DatetimeIndex(pd.to_datetime(frame["Date"], format="%Y-%m-%d"))
        values = frame["Value"].astype("float64").to_numpy() * scale
    except (ValueError, KeyError, pd.errors.ParserError, pd.errors.EmptyDataError) as exc:
        raise SnbError(f"{name}: the file cannot be read ({exc})") from exc
    series = pd.Series(values, index=dates.rename("date"), name=name).dropna()
    if series.empty or series.index.has_duplicates or not series.index.is_monotonic_increasing:
        raise SnbError(f"{name}: no value, or dates repeated or out of order")
    return series


def download_csv(cube: str, item: str) -> str:
    url = SNB_URL.format(cube=cube, item=item, start=HISTORY_START)
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
        if 400 <= resp.status_code < 500:  # a wrong cube or item: retrying cannot help
            raise SnbError(f"{cube}/{item}: HTTP {resp.status_code}")
        if resp.status_code >= 500:
            last = f"HTTP {resp.status_code}"
            continue
        return resp.text
    raise SnbError(
        f"{cube}/{item}: download failed after {ATTEMPTS} attempts ({last})", host_down=True
    )


def load_snb_series(
    cube: str,
    item: str,
    *,
    scale: float = 1.0,
    data_dir: Path | None = None,
    now: datetime | None = None,
    fetch: Callable[[str, str], str] | None = None,
    cache_only: bool = False,
) -> tuple[pd.Series, str | None]:
    """One SNB series and a notice (set when an older cached copy was used). Raises ``SnbError``
    when today's cache, the download and every older cache all fail. ``fetch`` replaces the
    download (tests). With ``cache_only`` nothing is downloaded: any cached copy is used."""
    name = f"{cube}_" + re.sub(r"[^A-Za-z0-9]", "", item)
    base = data_dir if data_dir is not None else get_settings().data_dir
    sdir = Path(base) / "snb"
    day = (now or datetime.now(UTC)).astimezone(UTC).date().isoformat()
    today_file = sdir / f"{name}_{day}.csv"
    if today_file.is_file():
        try:
            return parse_snb_csv(today_file.read_text("utf-8"), name, scale), None
        except (SnbError, OSError):
            logger.warning("Unreadable SNB cache %s; downloading again", today_file.name)
    host_memo = (str(sdir), day, "*")
    series_memo = (str(sdir), day, name)
    reason = _FAILED.get(host_memo) or _FAILED.get(series_memo)
    if cache_only:
        reason = "not downloaded"
    elif reason is None:
        try:
            text = (fetch or download_csv)(cube, item)
            values = parse_snb_csv(text, name, scale)
        except Exception as exc:  # a failing network layer must not stop the report
            reason = str(exc) if isinstance(exc, SnbError) else f"{type(exc).__name__}: {exc}"
            whole_host = not isinstance(exc, SnbError) or exc.host_down
            _FAILED[host_memo if whole_host else series_memo] = reason
        else:
            try:
                atomic_write(today_file, text)
                for old in cached_files(sdir, name):
                    if old != today_file:
                        old.unlink(missing_ok=True)
            except OSError:
                logger.warning("Could not write the SNB cache for %s", name, exc_info=True)
            return values, None
    for path in reversed(cached_files(sdir, name)):
        try:
            values = parse_snb_csv(path.read_text("utf-8"), name, scale)
        except (SnbError, OSError):
            continue
        stamp = path.stem.rsplit("_", 1)[-1]
        return (
            values,
            f"The Swiss National Bank could not be reached ({reason}); used the copy of {stamp}.",
        )
    raise SnbError(reason)
