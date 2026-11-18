"""Command-line interface.

Usage::

    factordesk report TICKER [--out DIR] [--open] [--json]
    factordesk factors refresh
    factordesk factors status

Exit codes: 0 success; 1 data problem (unknown ticker, too little history, invalid factor
file, inputs that cannot support a regression); 2 usage error; 3 network failure; 4 output
location refused or not writable. Every failure prints exactly one line on stderr.
"""

from __future__ import annotations

import argparse
import logging
import sys
import webbrowser
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pandas as pd

from factordesk.analytics.sample import DegenerateInputError, InsufficientHistoryError
from factordesk.config import get_settings
from factordesk.data.factors import (
    FactorDataError,
    FactorDownloadError,
    FactorStatus,
    factor_status,
    load_ff5_daily,
)
from factordesk.data.prices import PriceDataError, PriceProvider, validate_ticker

EXIT_OK = 0
EXIT_DATA = 1
EXIT_USAGE = 2
EXIT_NETWORK = 3
EXIT_OUTPUT = 4

PROG = "factordesk"

logger = logging.getLogger(__name__)


def _err(message: str) -> None:
    print(f"{PROG}: error: {message}", file=sys.stderr)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=PROG,
        description="Fama-French 5-factor analysis of one ticker's daily returns.",
        epilog="Exit codes: 0 ok, 1 data problem, 2 usage, 3 network, 4 output location.",
    )
    sub = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")

    rep = sub.add_parser("report", help="build the factor report for a ticker")
    rep.add_argument("ticker", help="ticker symbol, e.g. SPY")
    rep.add_argument(
        "--out",
        type=Path,
        default=None,
        help="output directory (default: current directory); never the data cache",
    )
    rep.add_argument("--open", action="store_true", help="open the HTML report in a browser")
    rep.add_argument("--json", action="store_true", help="also write the report as JSON")

    fac = sub.add_parser("factors", help="manage the cached Fama-French factor file")
    fac_sub = fac.add_subparsers(dest="factors_command", required=True, metavar="ACTION")
    fac_sub.add_parser("refresh", help="download the latest factor file now")
    fac_sub.add_parser("status", help="show the cached factor file's coverage and age")
    return parser


def _inside(path: Path, parent: Path) -> bool:
    return path.resolve().is_relative_to(parent.resolve())


def _print_status(status: FactorStatus) -> None:
    downloaded = status.last_download_at.isoformat() if status.last_download_at else "unknown"
    print(f"Factors: Fama-French 5 factors, daily, {status.first_date} to {status.last_date}")
    print(
        f"Age: {status.days_behind} days behind today"
        + (" (stale: older than 40 days)" if status.stale else "")
    )
    print(f"Downloaded: {downloaded}")
    print(f"Source: {status.source_url}")


def _cmd_factors(action: str, now: datetime) -> int:
    if action == "status":
        status = factor_status(now=now)
        if status is None:
            _err("no factor data cached; run 'factordesk factors refresh'")
            return EXIT_DATA
        _print_status(status)
        return EXIT_OK
    try:
        load_ff5_daily(refresh=True, now=now)
    except (FactorDownloadError, httpx.HTTPError, OSError) as exc:
        _err(f"could not download the factor file ({exc}); check your network connection")
        return EXIT_NETWORK
    except FactorDataError as exc:
        _err(f"the downloaded factor file failed validation ({exc}); the cache was kept")
        return EXIT_DATA
    status = factor_status(now=now)
    if status is None:  # pragma: no cover - a successful refresh always writes the cache
        _err("refresh finished but no factor data is cached")
        return EXIT_DATA
    print("Factor file refreshed.")
    _print_status(status)
    return EXIT_OK


def _cmd_report(
    args: argparse.Namespace,
    price_provider: PriceProvider | None,
    factors: pd.DataFrame | None,
    now: datetime,
) -> int:
    # Imported here: yfinance is heavy and only the report command needs it.
    from yfinance.exceptions import YFException  # pyright: ignore[reportMissingTypeStubs]

    from factordesk.pipeline import build_report
    from factordesk.report import dump_report, write_report

    try:
        symbol = validate_ticker(str(args.ticker))
    except PriceDataError:
        _err(
            f"invalid ticker {args.ticker!r}: use 1-12 letters, digits or . ^ = - "
            "(for example SPY or BRK-B)"
        )
        return EXIT_DATA

    out_dir: Path = args.out if args.out is not None else Path.cwd()
    data_dir = Path(get_settings().data_dir)
    if _inside(out_dir, data_dir):
        _err(f"refusing to write into the data cache folder {data_dir}; choose another --out")
        return EXIT_OUTPUT

    try:
        report = build_report(symbol, price_provider=price_provider, factors=factors, now=now)
    except InsufficientHistoryError as exc:
        _err(
            f"{symbol} has {exc.n} daily returns that line up with the factor data; at least "
            f"{exc.required} (about two years) are required"
        )
        return EXIT_DATA
    except DegenerateInputError as exc:
        _err(f"cannot analyse {symbol}: {exc.reason}")
        return EXIT_DATA
    except PriceDataError as exc:
        _err(f"{exc}. Check the symbol; if it is right, check your network connection")
        return EXIT_DATA
    except FactorDataError as exc:
        _err(f"the factor file failed validation ({exc})")
        return EXIT_DATA
    except (FactorDownloadError, httpx.HTTPError, OSError) as exc:
        _err(f"network problem while fetching data ({exc}); check your connection")
        return EXIT_NETWORK
    except YFException as exc:
        _err(f"Yahoo Finance refused the request ({exc}); try again later")
        return EXIT_NETWORK
    except (ValueError, ArithmeticError) as exc:
        # Last resort (D30): a numerical or validation error that no rule above anticipated
        # must still end as one line, never a traceback. The traceback goes to the debug log.
        logger.debug("report for %s failed", symbol, exc_info=True)
        message = " ".join(str(exc).split()) or type(exc).__name__
        _err(f"could not compute the report for {symbol}: {message}")
        return EXIT_DATA

    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        html_path = write_report(report, out_dir / f"{symbol}_report.html")
        written = [html_path]
        if args.json:
            json_path = out_dir / f"{symbol}_report.json"
            dump_report(report, json_path)
            written.append(json_path)
    except OSError as exc:
        _err(f"could not write the report to {out_dir} ({exc})")
        return EXIT_OUTPUT

    r2 = report.regression.r2
    print(
        f"{symbol}: n = {report.data.n_obs}, {report.data.actual_start} to "
        f"{report.data.actual_end} (factors through {report.data.factors_last_date}); "
        f"R2 = {'n/a' if r2 is None else f'{r2:.4f}'}"
    )
    for path in written:
        print(f"Wrote {path}")
    if args.open:
        webbrowser.open(html_path.resolve().as_uri())
    return EXIT_OK


def main(
    argv: Sequence[str] | None = None,
    *,
    price_provider: PriceProvider | None = None,
    factors: pd.DataFrame | None = None,
    now: datetime | None = None,
) -> int:
    """Entry point. Providers, factors and the clock are injectable for offline tests."""
    if not logging.getLogger().handlers:
        logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
    parser = _parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:  # argparse exits on --help (0) and on usage errors (2)
        return int(exc.code) if isinstance(exc.code, int) else EXIT_USAGE
    when = now if now is not None else datetime.now(UTC)
    if args.command == "factors":
        return _cmd_factors(str(args.factors_command), when)
    return _cmd_report(args, price_provider, factors, when)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
