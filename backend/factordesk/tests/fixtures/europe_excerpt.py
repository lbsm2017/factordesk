"""Small invented excerpts in the layout of the Ken French Developed Europe files (offline tests).

The layout is copied from the real files (``Europe_5_Factors_CSV.zip``,
``Europe_Mom_Factor_CSV.zip`` and the two ``Daily`` files): a preamble that names the Bloomberg
database, a header that starts with a comma, rows whose cells are padded with blanks before the
comma, the momentum column called ``WML``, and for monthly files an annual block. The numbers are
made up (a fixed pattern, percent as published); no real factor data is kept in the repository.
"""

from __future__ import annotations

_PREAMBLE = """\
This file was created using the 202609 Bloomberg database.

Missing data are indicated by -99.99.



"""

_FIVE = ("Mkt-RF", "SMB", "HML", "RMW", "CMA", "RF")


def _cell(value: float) -> str:
    return f"{value:<8.2f}"


def _five(stamp: str, k: int, rf: float) -> str:
    """One five-factor row: five invented factor values and ``rf`` (percent)."""
    vals = [((k * m) % 17 - 8) / 2.0 for m in (3, 5, 7, 11, 13)] + [rf]
    return f"{stamp:<10},{','.join(_cell(v) for v in vals)}".rstrip()


def _mom(stamp: str, k: int) -> str:
    return f"{stamp:<10},{_cell(((k * 9) % 19 - 9) / 2.0)}".rstrip()


EUROPE5_MONTHLY_2020 = (
    _PREAMBLE
    + f",{','.join(_FIVE)}\n"
    + "\n".join(_five(f"2020{m:02d}", m, 0.05) for m in range(1, 13))
    + "\n\n\n\n Annual Factors: January-December\n"
    + f",{','.join(_FIVE)}\n"
    + _five("2019", 1, 2.1)
    + "\n"
    + _five("2020", 2, 0.6)
    + "\n"
)

EUROPE_MOM_MONTHLY_2020 = (
    _PREAMBLE
    + ",WML\n"
    + "\n".join(_mom(f"2020{m:02d}", m) for m in range(1, 13))
    + "\n\n\n\n Annual Factors: January-December\n"
    + ",WML\n"
    + _mom("2019", 3)
    + "\n"
    + _mom("2020", 4)
    + "\n"
)

_APRIL_DAYS = [1, 2, 3, 6, 7, 8, 9, 10, 14, 15, 16, 17, 20, 21, 22, 23, 24, 27, 28, 29, 30]

EUROPE5_DAILY_APR_2020 = (
    _PREAMBLE
    + f",{','.join(_FIVE)}\n"
    + "\n".join(_five(f"202004{d:02d}", d, 0.01) for d in _APRIL_DAYS)
    + "\n"
)

EUROPE_MOM_DAILY_APR_2020 = (
    _PREAMBLE + ",WML\n" + "\n".join(_mom(f"202004{d:02d}", d) for d in _APRIL_DAYS) + "\n"
)
