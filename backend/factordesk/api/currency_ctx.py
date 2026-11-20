"""The reference currency of one request: exchange rates, euro cash and the notes they leave.

``CurrencySources`` holds the loaders (injected, like ``AppDeps``: tests pass fakes, the
real ones are ``default_sources``). ``CurrencyContext`` wraps them for one reference currency:
it turns a source that is down into a 503 for the EUR view only (the USD view never builds a
context unless a listing needs conversion) and collects the notices for the report's
``currency`` block.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime
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
    """``fx_prices(ccy, ref, dates)``, ``fx_returns(ccy, ref, dates)``, ``eur_rate()`` and
    ``chf_rate()`` (SARON; ``None``: the CHF Cash line keeps its ETF proxy)."""

    fx_prices: FxLoader
    fx_returns: FxLoader
    eur_rate: Callable[[], rates.RateResult]
    chf_rate: Callable[[], rates.RateResult] | None = None


def default_sources(data_dir: Path) -> CurrencySources:
    """The real ECB and FRED loaders, caching under ``data_dir``."""

    def now() -> datetime:
        return datetime.now(UTC)

    return CurrencySources(
        fx_prices=lambda c, r, d: fx.fx_prices(c, r, d, data_dir=data_dir, now=now()),
        fx_returns=lambda c, r, d: fx.fx_returns(c, r, d, data_dir=data_dir, now=now()),
        eur_rate=lambda: rates.load_eur_overnight(data_dir=data_dir, now=now()),
        chf_rate=lambda: rates.load_chf_overnight(data_dir=data_dir, now=now()),
    )


def unavailable(why: str) -> ApiException:
    return ApiException(
        "network",
        f"The exchange rates or the euro cash rate this report needs are unavailable: "
        f"{why.rstrip('.')}.",
        "Try again later, or switch to USD if the instrument is quoted in US dollars.",
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
        self.chf_credit: str | None = None
        self.chf_noted = False
        """True when the CHF Cash line left a notice (SARON used, or the fallback to FXF)."""
        self._chf: pd.Series | None = None
        self._chf_probed = False
        self._dropped = pd.DatetimeIndex([])
        """Factor dates left out by every conversion of this request (one set, or two when the
        macro, energy and world beta sections read the US frame); see ``info``."""

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

    def chf_ready(self) -> bool:
        """True when the CHF Cash line can earn SARON in this view: the rate loaded and the
        franc's exchange rate answers. Otherwise a notice is left and the line keeps its ETF
        proxy (FXF); this never raises. A server without a CHF source answers False silently."""
        if not self._chf_probed:
            self._chf_probed = True
            self._chf = self._load_chf()
        return self._chf is not None

    def _load_chf(self) -> pd.Series | None:
        if self.sources is None or self.sources.chf_rate is None:
            return None
        result = self.sources.chf_rate()
        if result.rate is None:
            self.note(f"{result.notice or 'SARON is unavailable.'} The CHF Cash line uses FXF.")
            self.chf_noted = True
            return None
        try:  # the franc's rate must answer too, else the line cannot be converted
            self.returns("CHF", pd.date_range(end=pd.Timestamp.now().normalize(), periods=2))
        except ApiException as exc:
            self.note(f"{exc.message} The CHF Cash line uses FXF.")
            self.chf_noted = True
            return None
        self.note(result.notice)
        self.chf_credit = result.credit
        self.chf_noted = True
        self.note(f"The CHF Cash line earns SARON, converted to {self.ref}; not hedged.")
        return result.rate

    def chf_cash(self, dates: pd.DatetimeIndex) -> pd.Series:
        """CHF cash return over each interval of ``dates``, in francs, indexed by ``dates[1:]``.
        Call after ``chf_ready`` answered True."""
        assert self._chf is not None
        return rates.cash_returns(self._chf, dates)

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
        # the first date has no return interval in any conversion: not a loss worth a notice
        dropped = pd.DatetimeIndex(frame.index[1:].difference(out.index))
        self._dropped = self._dropped.union(dropped)
        out.attrs[ATTR] = {
            "notes": self.notes[mark:],
            "dropped": tuple(dropped),  # not an Index: pandas compares attrs with ==
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
            dropped = cast(tuple[pd.Timestamp, ...], trace.get("dropped", ()))
            if dropped:
                self._dropped = self._dropped.union(pd.DatetimeIndex(dropped))
            self.fx_source = cast(str | None, trace.get("fx_source")) or self.fx_source
            self.rate_credit = cast(str | None, trace.get("rate_credit")) or self.rate_credit

    def info(self, window: tuple[date, date] | None = None) -> CurrencyInfo:
        """The report's ``currency`` block.

        ``window`` is the span the analysis covers (first and last day, both included). The
        factor dates the conversion left out (before the euro series start, after its last
        rate) are reported once, and only the ones inside that span: the rest do not touch the
        analysis. Without a window the notice is not given.
        """
        if window is not None and len(self._dropped):
            lo, hi = pd.Timestamp(window[0]), pd.Timestamp(window[1])
            n = int(((self._dropped >= lo) & (self._dropped <= hi)).sum())
            if n:
                noun, verb = ("date", "was") if n == 1 else ("dates", "were")
                self.note(
                    f"{n} factor {noun} before the {self.ref} series start or after its last "
                    f"rate {verb} left out; nothing was filled."
                )
        credits = [c for c in (self.rate_credit, self.chf_credit) if c]
        return CurrencyInfo(
            reference=cast(ReferenceCurrency, self.ref),
            fx_source=fx.credit(self.fx_source),
            rate_source=" ".join(credits) or None,
            notes=list(self.notes),
        )


def clip_window(first: date | None, last: date | None, lo: date, hi: date) -> tuple[date, date]:
    """The requested range (``None``: open edge) cut to the dates ``lo..hi`` the subject has."""
    return (lo if first is None else max(first, lo), hi if last is None else min(last, hi))
