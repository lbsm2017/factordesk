"""The reference currency of one request: exchange rates, euro cash and the notes they leave.

``CurrencySources`` holds the three loaders (injected, like ``AppDeps``: tests pass fakes, the
real ones are ``default_sources``). ``CurrencyContext`` wraps them for one reference currency:
it turns a source that is down into a 503 for the EUR view only (the USD view never builds a
context unless a listing needs conversion) and collects the notices for the report's
``currency`` block.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import pandas as pd

from factordesk.analytics.currency import convert_factors
from factordesk.api.errors import ApiException
from factordesk.data import fx, rates
from factordesk.report.schema import CurrencyInfo, ReferenceCurrency

FxLoader = Callable[[str, str, pd.DatetimeIndex], fx.FxResult]
ATTR = "currency_trace"
"""Key in ``DataFrame.attrs`` of a converted factor frame: its notes and sources (a cached frame
brings them along)."""


@dataclass(frozen=True)
class CurrencySources:
    """``fx_prices(ccy, ref, dates)``, ``fx_returns(ccy, ref, dates)`` and ``eur_rate()``."""

    fx_prices: FxLoader
    fx_returns: FxLoader
    eur_rate: Callable[[], rates.RateResult]


def default_sources(data_dir: Path) -> CurrencySources:
    """The real ECB and FRED loaders, caching under ``data_dir``."""

    def now() -> datetime:
        return datetime.now(UTC)

    return CurrencySources(
        fx_prices=lambda c, r, d: fx.fx_prices(c, r, d, data_dir=data_dir, now=now()),
        fx_returns=lambda c, r, d: fx.fx_returns(c, r, d, data_dir=data_dir, now=now()),
        eur_rate=lambda: rates.load_eur_overnight(data_dir=data_dir, now=now()),
    )


def unavailable(why: str) -> ApiException:
    return ApiException(
        "network",
        f"The EUR view needs exchange rates and the euro cash rate, and they are unavailable: "
        f"{why.rstrip('.')}.",
        "Switch to USD, which does not need them, or try again later.",
    )


class CurrencyContext:
    """Rates and notices for one reference currency (``ref``)."""

    def __init__(self, ref: ReferenceCurrency, sources: CurrencySources | None) -> None:
        self.ref = ref
        self.sources = sources
        self.notes: list[str] = []
        self.fx_source: str | None = None
        self.rate_credit: str | None = None
        self._rate: rates.RateResult | None = None

    def _need(self) -> CurrencySources:
        if self.sources is None:
            raise unavailable("this server has no exchange-rate source")
        return self.sources

    def note(self, text: str | None) -> None:
        if text and text not in self.notes:
            self.notes.append(text)

    def _fx(self, loader: FxLoader, ccy: str, dates: pd.DatetimeIndex) -> pd.Series:
        result = loader(ccy, self.ref, dates)
        if result.series is None:
            raise unavailable(result.notice or "no source answered")
        self.note(result.notice)
        self.fx_source = result.source or self.fx_source
        return result.series

    def prices(self, ccy: str, dates: pd.DatetimeIndex) -> pd.Series:
        """Price of one ``ccy`` in the reference currency on ``dates`` (503 when no source)."""
        return self._fx(self._need().fx_prices, ccy, dates)

    def returns(self, ccy: str, dates: pd.DatetimeIndex) -> pd.Series:
        """Return of one ``ccy`` in the reference currency, indexed by ``dates[1:]``."""
        return self._fx(self._need().fx_returns, ccy, dates)

    def cash(self, dates: pd.DatetimeIndex) -> pd.Series:
        """Euro cash return over each interval of ``dates``, indexed by ``dates[1:]``."""
        if self._rate is None:
            self._rate = self._need().eur_rate()
        if self._rate.rate is None:
            raise unavailable(self._rate.notice or "no source answered")
        self.note(self._rate.notice)
        self.rate_credit = self._rate.credit or self.rate_credit
        return rates.cash_returns(self._rate.rate, dates)

    def factors(self, frame: pd.DataFrame) -> pd.DataFrame:
        """``frame`` in the reference currency (one conversion step; see ``convert_factors``)."""
        if ATTR in frame.attrs:  # already converted (a cached frame)
            self.absorb(frame)
            return frame
        dates = pd.DatetimeIndex(frame.index)
        mark = len(self.notes)
        fx_ret = self.returns("USD", dates)
        cash = self.cash(dates)
        out = convert_factors(frame, fx_ret, cash)
        n = len(frame) - len(out)
        if n:
            self.note(
                f"{n} factor dates before the {self.ref} series start or after its last "
                "rate were left out; nothing was filled."
            )
        out.attrs[ATTR] = {
            "notes": self.notes[mark:],
            "fx_source": self.fx_source,
            "rate_credit": self.rate_credit,
        }
        return out

    def absorb(self, frame: pd.DataFrame) -> None:
        """Take the notes and sources a converted frame carries."""
        trace = cast(dict[str, Any] | None, frame.attrs.get(ATTR))
        if trace:
            for text in cast(list[str], trace.get("notes", [])):
                self.note(text)
            self.fx_source = cast(str | None, trace.get("fx_source")) or self.fx_source
            self.rate_credit = cast(str | None, trace.get("rate_credit")) or self.rate_credit

    def info(self) -> CurrencyInfo:
        """The report's ``currency`` block."""
        assert self.ref == "EUR"
        return CurrencyInfo(
            reference="EUR",
            fx_source=fx.credit(self.fx_source),
            rate_source=self.rate_credit,
            notes=list(self.notes),
        )
