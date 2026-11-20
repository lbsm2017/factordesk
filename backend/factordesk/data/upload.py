"""A monthly track record from a CSV upload: parse and validate, in memory only.

The file has a header with two columns, ``date`` and ``return``. A date is ``YYYY-MM-DD`` or
``YYYY-MM`` and is moved to its month-end; a return is a decimal (``0.012`` is 1.2%). Every
refusal is an ``UploadError`` whose message names the row or month at fault. Nothing here reads
or writes a file: the caller passes the bytes.
"""

from __future__ import annotations

import csv
import io
import math
from datetime import datetime
from typing import Literal

import pandas as pd

MAX_UPLOAD_BYTES = 1024 * 1024
"""Largest request body accepted (1 MB); a 40-year monthly record is about 10 KB."""
DEFAULT_NAME = "Uploaded track record"
MAX_NAME_LENGTH = 80
MAX_ECHO = 40
"""Longest cell text echoed back in a message; longer text is cut and ends with an ellipsis."""
GrossNet = Literal["gross", "net"]
_COLUMNS = ("date", "return")


class UploadError(ValueError):
    """The uploaded file or its form fields cannot be used; ``str(exc)`` is a plain sentence."""


def clean_name(name: str | None) -> str:
    """The display name: trimmed, control characters removed, capped; a default when empty."""
    text = "".join(ch for ch in (name or "") if ch.isprintable()).strip()
    return text[:MAX_NAME_LENGTH].rstrip() or DEFAULT_NAME


def parse_gross_net(value: str | None) -> GrossNet | None:
    """``gross``, ``net`` or nothing (empty means unknown); anything else is refused."""
    text = (value or "").strip().lower()
    if text == "":
        return None
    if text == "gross" or text == "net":
        return text
    raise UploadError("gross_net must be gross or net")


def _cut(text: str, limit: int = MAX_ECHO) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _shown(text: str) -> str:
    """``text`` as it is echoed in a message: quoted, and cut at ``MAX_ECHO`` characters."""
    return repr(_cut(text))


def _decode(raw: bytes) -> str:
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise UploadError(
            "the file is not UTF-8 text; save it as CSV (UTF-8) with a date and a return column"
        ) from exc


def _rows(text: str) -> list[tuple[int, list[str]]]:
    """The non-blank rows, each with its line number in the file (blank lines count)."""
    sample = text[:4096]
    delimiter = ";" if sample.count(";") > sample.count(",") else ","
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    rows = [
        (reader.line_num, [cell.strip() for cell in row])
        for row in reader
        if any(cell.strip() for cell in row)
    ]
    if not rows:
        raise UploadError("the file is empty")
    return rows


def _date(text: str, line: int) -> pd.Timestamp:
    """A ``YYYY-MM-DD`` date as written, or the month-end of a ``YYYY-MM`` month."""
    try:
        if len(text) <= 7:
            month = pd.Timestamp(datetime.strptime(text, "%Y-%m"))
            return pd.Timestamp(month + pd.offsets.MonthEnd(0))
        stamp = datetime.fromisoformat(text)
    except ValueError:
        raise UploadError(
            f"line {line}: {_shown(text)} is not a date; write dates as YYYY-MM-DD or YYYY-MM"
        ) from None
    if stamp.tzinfo is not None:
        raise UploadError(f"line {line}: {_shown(text)} has a time zone; write dates without one")
    return pd.Timestamp(stamp).normalize()


def _number(text: str, line: int) -> float:
    if text == "":
        raise UploadError(f"line {line}: the return is missing")
    if "%" in text:
        raise UploadError(
            f"line {line}: {_shown(text)} is a percentage; "
            "write returns as decimals (0.012 for 1.2%)"
        )
    try:
        value = float(text.replace(",", ".") if text.count(",") == 1 and "." not in text else text)
    except ValueError:
        raise UploadError(
            f"line {line}: {_shown(text)} is not a number; "
            "write returns as decimals (0.012 for 1.2%)"
        ) from None
    if not math.isfinite(value):
        raise UploadError(f"line {line}: the return {_shown(text)} is not a finite number")
    return value


def parse_monthly_csv(raw: bytes) -> pd.Series:
    """The returns of a ``date,return`` CSV, indexed by the dates as written (tz-naive; a
    ``YYYY-MM`` month is dated at its month-end).

    Refuses a missing or extra column, an unreadable date or return and an empty return. Month
    rules (gaps, repeated months, a return at or below -100%) are checked by
    ``subject_from_monthly_returns``, which also moves each date to its month-end.
    """
    rows = _rows(_decode(raw))
    first_line, first = rows[0]
    header = [cell.lower() for cell in first]
    if sorted(header) != sorted(_COLUMNS):
        found = ", ".join(_cut(cell) for cell in first)
        if len(found) > 80:
            found = found[:79] + "…"
        raise UploadError(
            f"line {first_line}: the first row must name two columns, date and return "
            f"(found: {found or 'nothing'})"
        )
    at_date, at_return = header.index("date"), header.index("return")
    body = rows[1:]
    if not body:
        raise UploadError("the file has a header but no rows")
    dates: list[pd.Timestamp] = []
    values: list[float] = []
    for number, row in body:
        if len(row) != 2:
            raise UploadError(f"line {number}: expected 2 columns, found {len(row)}")
        dates.append(_date(row[at_date], number))
        values.append(_number(row[at_return], number))
    return pd.Series(values, index=pd.DatetimeIndex(dates, name="date"), dtype="float64")
