"""ECB Data Portal (SDMX REST) series download, with a per-day disk cache.

``load_ecb_series(flow, key)`` returns one series as floats on a date index, times ``scale``
(the euro STR and EONIA come in percent, so they use ``scale=0.01``; exchange rates use 1.0).
The file is cached per day (``<data_dir>/ecb/<flow>_<key>_<YYYY-MM-DD>.csv``). The download has an
8 s timeout and two tries; a failure is remembered for the rest of the day (in memory), and the
latest cached file of any day is then used with a notice. With no cache, ``EcbError`` is raised.
The URL is ``https://data-api.ecb.europa.eu/service/data/<flow>/<key>?format=csvdata``.
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

ECB_URL = "https://data-api.ecb.europa.eu/service/data/{flow}/{key}?format=csvdata&detail=dataonly"
_USER_AGENT = "factordesk-ecb-loader/0.1"

_FAILED: dict[tuple[str, str, str], str] = {}
"""Downloads that failed, by (data folder, series name, day), with the reason."""


class EcbError(Exception):
    """An ECB series cannot be downloaded or read, and no cached copy exists."""


def parse_ecb_csv(text: str, name: str, scale: float = 1.0) -> pd.Series:
    """The ``OBS_VALUE`` column of an ECB ``csvdata`` body, times ``scale``, by ``TIME_PERIOD``."""
    try:
        frame = pd.read_csv(io.StringIO(text), usecols=["TIME_PERIOD", "OBS_VALUE"])
        dates = pd.DatetimeIndex(pd.to_datetime(frame["TIME_PERIOD"], format="%Y-%m-%d"))
        values = frame["OBS_VALUE"].astype("float64").to_numpy() * scale
    except (ValueError, KeyError, pd.errors.ParserError, pd.errors.EmptyDataError) as exc:
        raise EcbError(f"{name}: the file cannot be read ({exc})") from exc
    series = pd.Series(values, index=dates.rename("date"), name=name).dropna()
    if series.empty or series.index.has_duplicates or not series.index.is_monotonic_increasing:
        raise EcbError(f"{name}: no value, or dates repeated or out of order")
    return series


def _fetch(flow: str, key: str) -> str:
    url = ECB_URL.format(flow=flow, key=key)
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
    raise EcbError(f"{key}: download failed after {ATTEMPTS} attempts ({last})")


def load_ecb_series(
    flow: str,
    key: str,
    *,
    scale: float = 1.0,
    data_dir: Path | None = None,
    now: datetime | None = None,
    fetch: Callable[[str, str], str] | None = None,
) -> tuple[pd.Series, str | None]:
    """One ECB series and a notice (set when an older cached copy was used). Raises ``EcbError``
    when today's cache, the download and every older cache all fail. ``fetch`` replaces the
    download (tests)."""
    name = f"{flow}_" + re.sub(r"[^A-Za-z0-9]", "", key)
    base = data_dir if data_dir is not None else get_settings().data_dir
    edir = Path(base) / "ecb"
    day = (now or datetime.now(UTC)).astimezone(UTC).date().isoformat()
    today_file = edir / f"{name}_{day}.csv"
    if today_file.is_file():
        try:
            return parse_ecb_csv(today_file.read_text("utf-8"), name, scale), None
        except (EcbError, OSError):
            logger.warning("Unreadable ECB cache %s; downloading again", today_file.name)
    memo = (str(edir), name, day)
    reason = _FAILED.get(memo)
    if reason is None:
        try:
            text = (fetch or _fetch)(flow, key)
            values = parse_ecb_csv(text, name, scale)
        except Exception as exc:  # a failing network layer must not stop the report
            reason = str(exc) if isinstance(exc, EcbError) else f"{type(exc).__name__}: {exc}"
            _FAILED[memo] = reason
        else:
            try:
                atomic_write(today_file, text)
                for old in cached_files(edir, name):
                    if old != today_file:
                        old.unlink(missing_ok=True)
            except OSError:
                logger.warning("Could not write the ECB cache for %s", name, exc_info=True)
            return values, None
    for path in reversed(cached_files(edir, name)):
        try:
            values = parse_ecb_csv(path.read_text("utf-8"), name, scale)
        except (EcbError, OSError):
            continue
        stamp = path.stem.rsplit("_", 1)[-1]
        return values, f"The ECB could not be reached ({reason}); used the copy of {stamp}."
    raise EcbError(reason)
