"""Company name and currency: the Yahoo metadata read, its cache, the currency check (roadmap
N1), the schema field, the suggestions, the API error, the CLI message and the static header.

Offline: ``YFinanceProvider`` gets an injected ``info`` function, clock, sleep and jitter, and
the API tests use fake providers over synthetic prices. No test reads the network.
"""

from __future__ import annotations

import json
from collections.abc import Generator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Protocol, cast

import httpx
import pandas as pd
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from factordesk import cli
from factordesk.api.deps import AppDeps
from factordesk.api.main import create_app
from factordesk.data.prices import (
    SECURITY_MAX_AGE,
    PriceHistory,
    Security,
    UnsupportedCurrencyError,
    YFinanceProvider,
    check_currency,
    exchange_label,
    read_cached_security,
    security_from_info,
    security_of,
)
from factordesk.data.throttle import BatchSettings
from factordesk.pipeline import assemble_report, build_report
from factordesk.report import load_report
from factordesk.report.render_html import render_report_html
from factordesk.report.schema import (
    SCHEMA_VERSION,
    SUPPORTED_SCHEMA_VERSIONS,
    ApiError,
    DataInfo,
    FactorReport,
    SecurityInfo,
    TickerSuggestions,
)
from factordesk.tests.fixtures.dgp import StaticProvider, dgp_a, rng_for
from factordesk.tests.test_api_report import FakeFactors

FIXTURES = Path(__file__).parent / "fixtures"
MOCK = FIXTURES / "mock_report.json"
MOCK_V3 = FIXTURES / "mock_report_v3.json"
MOCK_V4 = FIXTURES / "mock_report_v4.json"

NOW = datetime(2026, 11, 18, 15, 0, tzinfo=UTC)
USD = Security(name="Zoom Communications, Inc.", currency="USD", exchange="NasdaqGS")
EUR = Security(name="SAP SE", currency="EUR", exchange="XETRA")
PENCE = Security(name="Vodafone Group", currency="GBp", exchange="LSE")


# ------------------------------------------------------------------------------ test doubles
class FakeClock:
    def __init__(self) -> None:
        self.t = 0.0
        self.sleeps: list[float] = []

    def monotonic(self) -> float:
        return self.t

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.t += seconds


class ZeroJitter:
    def uniform(self, a: float, b: float) -> float:
        return a


class YFRateLimitError(Exception):
    """Same class name as yfinance's exception; the code must not import the real one."""

    def __init__(self) -> None:
        super().__init__("Too Many Requests. Rate limited. Try after a while.")


class FakeInfo:
    """A stand-in for ``Ticker.get_info``: serves ``reply`` or raises the queued exceptions."""

    def __init__(
        self, reply: Mapping[str, object] | None = None, errors: list[Exception] | None = None
    ) -> None:
        self.reply: Mapping[str, object] = reply if reply is not None else {}
        self.errors = list(errors or [])
        self.calls: list[str] = []

    def __call__(self, ticker: str) -> Mapping[str, object]:
        self.calls.append(ticker)
        if self.errors:
            raise self.errors.pop(0)
        return self.reply


ZM_INFO: dict[str, object] = {
    "longName": "Zoom Communications, Inc.",
    "shortName": "Zoom Comm",
    "currency": "USD",
    "exchange": "NMS",
    "fullExchangeName": "NasdaqGS",
    "quoteType": "EQUITY",
}


@dataclass
class Rig:
    provider: YFinanceProvider
    info: FakeInfo
    clock: FakeClock
    now: list[datetime]
    cache_dir: Path

    @property
    def path(self) -> Path:
        return self.cache_dir / "ZM_security.json"


def make_rig(tmp_path: Path, info: FakeInfo, *, max_attempts: int = 3, breaker: int = 3) -> Rig:
    clock = FakeClock()
    now = [NOW]
    provider = YFinanceProvider(
        cache_dir=tmp_path / "prices",
        now=lambda: now[0],
        settings=BatchSettings(
            chunk_size=5,
            max_workers=1,
            min_interval_seconds=0.0,
            max_attempts=max_attempts,
            breaker_threshold=breaker,
        ),
        info=info,
        monotonic=clock.monotonic,
        sleep=clock.sleep,
        rng=ZeroJitter(),
    )
    return Rig(provider, info, clock, now, tmp_path / "prices")


# --------------------------------------------------------------------------- reading the answer
def test_name_is_the_long_name_then_the_short_name() -> None:
    both = security_from_info({"longName": "Long Inc.", "shortName": "Short"})
    assert both is not None and both.name == "Long Inc."
    short_only = security_from_info({"shortName": "Short", "currency": "USD"})
    assert short_only is not None and short_only.name == "Short"
    blank_long = security_from_info({"longName": "  ", "shortName": "Short"})
    assert blank_long is not None and blank_long.name == "Short"


def test_exchange_is_the_readable_name_then_the_code() -> None:
    full = security_from_info({"exchange": "NMS", "fullExchangeName": "NasdaqGS"})
    assert full is not None and full.exchange == "NASDAQ"
    code = security_from_info({"exchange": "NYQ"})
    assert code is not None and code.exchange == "NYSE"
    other = security_from_info({"exchange": "LSE"})
    assert other is not None and other.exchange == "LSE"


@pytest.mark.parametrize(
    ("raw", "label"),
    [
        *[(v, "NASDAQ") for v in ("NMS", "NGM", "NCM", "NasdaqGS", "NasdaqGM", "NasdaqCM")],
        *[(v, "NYSE") for v in ("NYQ", "NYSE")],
        *[(v, "NYSE American") for v in ("ASE", "NYSE American")],
        *[(v, "NYSE Arca") for v in ("PCX", "NYSEArca", "NYSE Arca")],
        *[(v, "Cboe BZX") for v in ("BTS", "Cboe BZX", "BATS")],
        ("XETRA", "XETRA"),
    ],
)
def test_exchange_label_table(raw: str, label: str) -> None:
    assert exchange_label(raw) == label


def test_exchange_label_keeps_none() -> None:
    assert exchange_label(None) is None


def test_a_cache_file_with_the_raw_exchange_is_mapped_on_read(tmp_path: Path) -> None:
    rig = make_rig(tmp_path, FakeInfo(ZM_INFO))
    rig.cache_dir.mkdir(parents=True)
    rig.path.write_text(
        json.dumps({"fetched_at": NOW.isoformat(), "name": "Zoom", "exchange": "NasdaqGS"}),
        encoding="utf-8",
    )
    found = read_cached_security(rig.cache_dir, "ZM")
    assert found is not None and found.exchange == "NASDAQ"


def test_missing_currency_stays_none_and_the_rest_is_kept() -> None:
    found = security_from_info({"longName": "No Currency Co", "quoteType": "EQUITY"})
    assert found == Security(
        name="No Currency Co", currency=None, exchange=None, quote_type="EQUITY"
    )


@pytest.mark.parametrize("info", [{}, {"trailingPegRatio": None}, {"longName": 5, "currency": ""}])
def test_an_answer_with_none_of_the_fields_is_nothing(info: dict[str, object]) -> None:
    assert security_from_info(info) is None


# ------------------------------------------------------------------------------- fetch_security
def test_fetch_security_returns_and_caches_the_record(tmp_path: Path) -> None:
    rig = make_rig(tmp_path, FakeInfo(ZM_INFO))
    found = rig.provider.fetch_security("zm")
    assert found == Security("Zoom Communications, Inc.", "USD", "NASDAQ", "EQUITY")
    stored = json.loads(rig.path.read_text(encoding="utf-8"))
    assert stored["fetched_at"] == NOW.isoformat()
    assert stored["name"] == "Zoom Communications, Inc." and stored["currency"] == "USD"
    assert rig.info.calls == ["ZM"]


def test_a_fresh_cache_is_a_hit_without_a_request(tmp_path: Path) -> None:
    rig = make_rig(tmp_path, FakeInfo(ZM_INFO))
    first = rig.provider.fetch_security("ZM")
    rig.now[0] = NOW + SECURITY_MAX_AGE - timedelta(minutes=1)
    assert rig.provider.fetch_security("ZM") == first
    assert rig.info.calls == ["ZM"]


def test_a_cache_older_than_seven_days_is_refreshed(tmp_path: Path) -> None:
    rig = make_rig(tmp_path, FakeInfo(ZM_INFO))
    rig.provider.fetch_security("ZM")
    rig.info.reply = {**ZM_INFO, "longName": "Zoom Communications, Renamed"}
    rig.now[0] = NOW + SECURITY_MAX_AGE + timedelta(seconds=1)
    refreshed = rig.provider.fetch_security("ZM")
    assert refreshed is not None and refreshed.name == "Zoom Communications, Renamed"
    assert rig.info.calls == ["ZM", "ZM"]
    stored = json.loads(rig.path.read_text(encoding="utf-8"))
    assert stored["fetched_at"] == rig.now[0].isoformat()


def test_a_stale_record_is_kept_when_the_refresh_fails(tmp_path: Path) -> None:
    rig = make_rig(tmp_path, FakeInfo(ZM_INFO))
    first = rig.provider.fetch_security("ZM")
    rig.info.errors = cast(list[Exception], [RuntimeError("boom")])
    rig.now[0] = NOW + timedelta(days=30)
    assert rig.provider.fetch_security("ZM") == first


def test_the_cache_sits_next_to_prices_and_is_not_a_price_file(tmp_path: Path) -> None:
    from factordesk.api.routes_factors import cached_tickers

    rig = make_rig(tmp_path, FakeInfo(ZM_INFO))
    rig.provider.fetch_security("ZM")
    assert rig.path.parent == rig.provider.cache_dir
    assert cached_tickers(rig.cache_dir) == {}


def test_an_unreadable_cache_is_ignored_and_refetched(tmp_path: Path) -> None:
    rig = make_rig(tmp_path, FakeInfo(ZM_INFO))
    rig.cache_dir.mkdir(parents=True)
    rig.path.write_text("{not json", encoding="utf-8")
    assert read_cached_security(rig.cache_dir, "ZM") is None
    assert rig.provider.fetch_security("ZM") == Security(
        "Zoom Communications, Inc.", "USD", "NASDAQ", "EQUITY"
    )
    assert rig.info.calls == ["ZM"]


def test_an_answer_without_fields_returns_none_and_is_not_cached(tmp_path: Path) -> None:
    rig = make_rig(tmp_path, FakeInfo({}))
    assert rig.provider.fetch_security("ZM") is None
    assert not rig.path.exists()


def test_an_invalid_ticker_makes_no_request(tmp_path: Path) -> None:
    rig = make_rig(tmp_path, FakeInfo(ZM_INFO))
    assert rig.provider.fetch_security("../etc") is None
    assert rig.info.calls == []


def test_a_rate_limited_read_returns_none_after_the_same_attempts(tmp_path: Path) -> None:
    rig = make_rig(
        tmp_path,
        FakeInfo(errors=[YFRateLimitError(), YFRateLimitError(), YFRateLimitError()]),
        max_attempts=3,
        breaker=5,
    )
    assert rig.provider.fetch_security("ZM") is None
    assert len(rig.info.calls) == 3
    assert rig.clock.sleeps == [2.0, 4.0]  # the price backoff schedule: 2 s, then 4 s
    assert not rig.path.exists()


def test_the_breaker_stops_a_read_early(tmp_path: Path) -> None:
    rig = make_rig(
        tmp_path,
        FakeInfo(errors=cast(list[Exception], [YFRateLimitError()] * 5)),
        max_attempts=5,
        breaker=2,
    )
    assert rig.provider.fetch_security("ZM") is None
    assert len(rig.info.calls) == 2


def test_a_transient_error_is_retried_then_succeeds(tmp_path: Path) -> None:
    rig = make_rig(tmp_path, FakeInfo(ZM_INFO, errors=[TimeoutError("slow")]))
    found = rig.provider.fetch_security("ZM")
    assert found is not None and found.currency == "USD"
    assert len(rig.info.calls) == 2


def test_an_unexpected_exception_returns_none(tmp_path: Path) -> None:
    rig = make_rig(tmp_path, FakeInfo(errors=[KeyError("quoteType")]))
    assert rig.provider.fetch_security("ZM") is None
    assert len(rig.info.calls) == 1


def test_read_cached_security_ignores_age_and_never_reads_the_network(tmp_path: Path) -> None:
    rig = make_rig(tmp_path, FakeInfo(ZM_INFO))
    assert read_cached_security(rig.cache_dir, "ZM") is None
    rig.provider.fetch_security("ZM")
    rig.now[0] = NOW + timedelta(days=400)
    found = read_cached_security(rig.cache_dir, "ZM")
    assert found is not None and found.name == "Zoom Communications, Inc."
    assert rig.info.calls == ["ZM"]


# ----------------------------------------------------------------------------------- security_of
def test_security_of_is_none_without_the_capability_or_on_failure() -> None:
    class NoMetadata:
        def fetch(self, ticker: str) -> object: ...

    class Raising:
        def fetch_security(self, ticker: str) -> Security | None:
            raise RuntimeError("boom")

    class WrongType:
        def fetch_security(self, ticker: str) -> object:
            return {"name": "x"}

    class Good:
        def fetch_security(self, ticker: str) -> Security | None:
            return USD

    assert security_of(NoMetadata(), "ZM") is None
    assert security_of(Raising(), "ZM") is None
    assert security_of(WrongType(), "ZM") is None
    assert security_of(Good(), "ZM") == USD


# --------------------------------------------------------------------------------- currency rule
@pytest.mark.parametrize("security", [None, Security(), Security(name="Only A Name"), USD])
def test_unknown_or_us_dollar_currency_is_accepted(security: Security | None) -> None:
    check_currency("ZM", security)
    check_currency("ZM", Security(currency=" usd "))


@pytest.mark.parametrize("currency", ["EUR", "GBP", "GBp", "GBX", "JPY", "CAD"])
def test_a_known_other_currency_is_refused_with_a_plain_message(currency: str) -> None:
    with pytest.raises(UnsupportedCurrencyError) as raised:
        check_currency("SAP.DE", Security(currency=currency))
    message = str(raised.value)
    assert "US dollars" in message and "SAP.DE" in message and currency in message
    assert message.startswith("Only tickers quoted in US dollars are supported for now")
    assert raised.value.ticker == "SAP.DE" and raised.value.currency == currency


# ------------------------------------------------------------------------------------------ schema
def test_the_mock_report_carries_the_demo_security() -> None:
    rep = load_report(MOCK)
    assert rep.schema_version == SCHEMA_VERSION == "4"
    assert SUPPORTED_SCHEMA_VERSIONS == ("3", "4")
    assert rep.data.security == SecurityInfo(name="Example Corp", currency="USD", exchange="NASDAQ")
    assert FactorReport.model_validate_json(rep.model_dump_json()) == rep


def test_the_security_field_is_optional_and_all_its_parts_too() -> None:
    assert SecurityInfo() == SecurityInfo(name=None, currency=None, exchange=None)
    data = load_report(MOCK).data.model_dump()
    del data["security"]
    assert DataInfo.model_validate(data).security is None


@pytest.mark.parametrize("fixture", [MOCK_V3, MOCK_V4])
def test_older_fixtures_without_the_field_still_load(fixture: Path) -> None:
    payload = json.loads(fixture.read_text(encoding="utf-8"))
    assert "security" not in payload["data"]
    old = load_report(fixture)
    assert old.data.security is None
    assert old.schema_version == payload["schema_version"]
    current = load_report(MOCK)
    stripped = current.model_copy(
        update={
            "schema_version": old.schema_version,
            "data": current.data.model_copy(update={"security": None}),
        }
    )
    assert old == stripped


# ------------------------------------------------------------------------------------- pipeline
@pytest.fixture(scope="module")
def synthetic() -> tuple[PriceHistory, pd.DataFrame]:
    d = dgp_a(rng_for(910), n=800)
    return d.history, d.factors.iloc[:780]


def _assemble(
    synthetic: tuple[PriceHistory, pd.DataFrame], security: Security | None
) -> FactorReport:
    history, factors = synthetic
    return assemble_report(
        "SYN", history, factors, now=NOW, factors_downloaded_at=None, security=security
    )


def test_assemble_report_records_the_security(synthetic: tuple[PriceHistory, pd.DataFrame]) -> None:
    rep = _assemble(synthetic, USD)
    assert rep.data.security == SecurityInfo(
        name="Zoom Communications, Inc.", currency="USD", exchange="NasdaqGS"
    )
    assert rep.schema_version == "4"


@pytest.mark.parametrize("security", [None, Security(quote_type="EQUITY")])
def test_assemble_report_without_usable_metadata_has_no_security(
    synthetic: tuple[PriceHistory, pd.DataFrame], security: Security | None
) -> None:
    assert _assemble(synthetic, security).data.security is None


def test_an_unknown_currency_is_accepted(synthetic: tuple[PriceHistory, pd.DataFrame]) -> None:
    rep = _assemble(synthetic, Security(name="No Currency Co"))
    assert rep.data.security == SecurityInfo(name="No Currency Co")


@pytest.mark.parametrize("security", [EUR, PENCE])
def test_assemble_report_refuses_a_known_other_currency(
    synthetic: tuple[PriceHistory, pd.DataFrame], security: Security
) -> None:
    with pytest.raises(UnsupportedCurrencyError, match="US dollars"):
        _assemble(synthetic, security)


class MetadataProvider(StaticProvider):
    """``StaticProvider`` that also answers the metadata read."""

    def __init__(self, history: PriceHistory, security: Security | None) -> None:
        super().__init__(history)
        self.security = security
        self.security_calls: list[str] = []

    def fetch_security(self, ticker: str) -> Security | None:
        self.security_calls.append(ticker)
        return self.security


def test_build_report_refuses_before_downloading_prices(
    synthetic: tuple[PriceHistory, pd.DataFrame],
) -> None:
    history, factors = synthetic
    provider = MetadataProvider(history, EUR)
    with pytest.raises(UnsupportedCurrencyError):
        build_report("SAP.DE", price_provider=provider, factors=factors, now=NOW)
    assert provider.security_calls == ["SAP.DE"] and provider.calls == []


def test_build_report_accepts_us_dollars_and_unknown(
    synthetic: tuple[PriceHistory, pd.DataFrame],
) -> None:
    history, factors = synthetic
    named = build_report(
        "ZM", price_provider=MetadataProvider(history, USD), factors=factors, now=NOW
    )
    assert named.data.security is not None and named.data.security.name == USD.name
    unknown = build_report(
        "ZM", price_provider=MetadataProvider(history, None), factors=factors, now=NOW
    )
    assert unknown.data.security is None


def test_a_provider_without_metadata_still_builds(
    synthetic: tuple[PriceHistory, pd.DataFrame],
) -> None:
    history, factors = synthetic
    rep = build_report("ZM", price_provider=StaticProvider(history), factors=factors, now=NOW)
    assert rep.data.security is None


def test_the_us_factors_note_matches_the_behaviour(
    synthetic: tuple[PriceHistory, pd.DataFrame],
) -> None:
    note = " ".join(_assemble(synthetic, None).notes)
    assert "does not check the ticker's currency" not in note
    assert "refused" in note


# ------------------------------------------------------------------------------------------ CLI
def test_cli_prints_the_message_and_exits_with_the_data_code(
    synthetic: tuple[PriceHistory, pd.DataFrame],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    class StubSettings:
        data_dir = tmp_path / "cache"

    monkeypatch.setattr(cli, "get_settings", lambda: StubSettings())
    history, factors = synthetic
    provider = MetadataProvider(history, PENCE)
    code = cli.main(
        ["report", "VOD.L", "--out", str(tmp_path / "out")],
        price_provider=provider,
        factors=factors,
        now=NOW,
    )
    err = capsys.readouterr().err
    assert code == cli.EXIT_DATA
    assert err.count("\n") == 1 and err.startswith("factordesk: error: ")
    assert "US dollars" in err and "VOD.L" in err and "GBp" in err
    assert not (tmp_path / "out" / "VOD.L_report.html").exists()


# ---------------------------------------------------------------------------------------- API
class ApiClient(Protocol):
    def get(self, url: str) -> httpx.Response: ...


@contextmanager
def serve(app: FastAPI) -> Generator[ApiClient]:
    with TestClient(app) as test_client:  # pyright: ignore[reportUnknownVariableType]
        yield cast(ApiClient, test_client)


def make_app(tmp_path: Path, provider: MetadataProvider, *, n: int = 800) -> FastAPI:
    d = dgp_a(rng_for(911), n=n)
    fake = FakeFactors(d.factors.iloc[: n - 30])
    deps = AppDeps(
        price_provider=provider,
        load_factors=fake.load,
        factor_status=fake.read_status,
        now=lambda: NOW,
        data_dir=tmp_path,
        static_dir=None,
    )
    return create_app(deps)


@pytest.fixture
def history() -> PriceHistory:
    return dgp_a(rng_for(911), n=800).history


def error_of(response: httpx.Response, status: int, code: str) -> ApiError:
    assert response.status_code == status, response.text
    error = ApiError.model_validate(response.json())
    assert error.code == code
    for text in (error.message, error.action):
        assert text.endswith(".") and "Traceback" not in text
    return error


def test_the_api_refuses_a_non_us_dollar_ticker_in_the_error_envelope(
    tmp_path: Path, history: PriceHistory
) -> None:
    provider = MetadataProvider(history, EUR)
    app = make_app(tmp_path, provider)
    with serve(app) as client:
        for path in (
            "/api/report/SAP.DE",
            "/api/report/SAP.DE?range=3Y",
            "/api/report/SAP.DE/ranges",
        ):
            error = error_of(client.get(path), 422, "unsupported_currency")
            assert "US dollars" in error.message
            assert "SAP.DE" in error.message and "EUR" in error.message
    assert provider.calls == []  # no price history was downloaded


def test_the_api_builds_a_report_with_the_name_and_currency(
    tmp_path: Path, history: PriceHistory
) -> None:
    provider = MetadataProvider(history, USD)
    app = make_app(tmp_path, provider)
    with serve(app) as client:
        response = client.get("/api/report/ZM")
        assert response.status_code == 200, response.text
        data = FactorReport.model_validate_json(response.text).data
        assert data.security == SecurityInfo(
            name="Zoom Communications, Inc.", currency="USD", exchange="NasdaqGS"
        )
        assert client.get("/api/report/ZM/ranges").status_code == 200
    assert provider.security_calls == ["ZM"]  # one read, shared by both endpoints


def test_the_api_accepts_an_unknown_currency_and_retries_the_read_next_time(
    tmp_path: Path, history: PriceHistory
) -> None:
    provider = MetadataProvider(history, None)
    app = make_app(tmp_path, provider)
    with serve(app) as client:
        first = client.get("/api/report/ZM?range=3Y")
        second = client.get("/api/report/ZM?range=5Y")
        for response in (first, second):
            assert response.status_code == 200, response.text
            assert FactorReport.model_validate_json(response.text).data.security is None
    assert provider.security_calls == ["ZM", "ZM"]  # a missing answer is not remembered


def test_the_static_download_carries_the_header_line(tmp_path: Path, history: PriceHistory) -> None:
    app = make_app(tmp_path, MetadataProvider(history, USD))
    with serve(app) as client:
        page = client.get("/api/report/ZM/html")
        assert page.status_code == 200, page.text
        assert "Zoom Communications, Inc. Listed on NasdaqGS, priced in US dollars." in page.text


# -------------------------------------------------------------------------------- suggestions
def test_suggestions_carry_cached_names_and_never_hit_the_network(
    tmp_path: Path, history: PriceHistory
) -> None:
    prices = tmp_path / "prices"
    prices.mkdir()
    for name in ("SPY_2026-11-18.parquet", "SPXL_2026-11-17.parquet", "ZM_2026-11-16.parquet"):
        (prices / name).write_bytes(b"")
    stamp = NOW.isoformat()
    (prices / "SPY_security.json").write_text(
        json.dumps({"fetched_at": stamp, "name": "SPDR S&P 500 ETF Trust", "currency": "USD"}),
        encoding="utf-8",
    )
    (prices / "ZM_security.json").write_text("{broken", encoding="utf-8")
    provider = MetadataProvider(history, USD)
    app = make_app(tmp_path, provider)
    with serve(app) as client:
        body = TickerSuggestions.model_validate_json(client.get("/api/tickers").text)
        names = {item.ticker: item.name for item in body.items}
        assert names == {"SPY": "SPDR S&P 500 ETF Trust", "SPXL": None, "ZM": None}
        raw = client.get("/api/tickers?q=sp").json()["items"]
        assert raw[0] == {
            "ticker": "SPY",
            "last_fetched": "2026-11-18",
            "name": "SPDR S&P 500 ETF Trust",
        }
        assert raw[1]["name"] is None
    assert provider.calls == [] and provider.security_calls == []


# ------------------------------------------------------------------------------- static header
def _header_of(report: FactorReport) -> str:
    page = render_report_html(report)
    start = page.index('<header class="masthead">')
    return page[start : page.index("</header>", start)]


def test_the_static_header_writes_name_exchange_and_currency_as_a_sentence() -> None:
    header = _header_of(load_report(MOCK))
    assert '<p class="coverage">Example Corp. Listed on NASDAQ, priced in US dollars.</p>' in header
    assert header.index("Example Corp") < header.index("Analysed")  # under the ticker, first


@pytest.mark.parametrize(
    ("security", "expected"),
    [
        (None, None),
        (SecurityInfo(), None),
        (SecurityInfo(name="Only Name"), "Only Name."),
        (SecurityInfo(currency="USD"), "Priced in US dollars."),
        (SecurityInfo(currency="EUR"), "Priced in EUR."),
        (SecurityInfo(exchange="NYSEArca"), "Listed on NYSE Arca."),
        (SecurityInfo(name="Foo Inc.", exchange="NASDAQ"), "Foo Inc. Listed on NASDAQ."),
        (
            SecurityInfo(name="A & B <Co>", currency="USD"),
            "A &amp; B &lt;Co&gt;. Priced in US dollars.",
        ),
    ],
)
def test_the_static_header_line_uses_only_what_is_known(
    security: SecurityInfo | None, expected: str | None
) -> None:
    mock = load_report(MOCK)
    report = mock.model_copy(update={"data": mock.data.model_copy(update={"security": security})})
    header = _header_of(report)
    lines = header.count('<p class="coverage">')
    if expected is None:
        assert lines == 1  # only the range line
        assert "Example Corp" not in header
    else:
        assert lines == 2
        assert f'<p class="coverage">{expected}</p>' in header


def test_nothing_else_in_the_static_page_changed() -> None:
    mock = load_report(MOCK)
    bare = mock.model_copy(update={"data": mock.data.model_copy(update={"security": None})})
    with_name = render_report_html(mock)
    without = render_report_html(bare)
    assert (
        with_name.replace(
            '<p class="coverage">Example Corp. Listed on NASDAQ, priced in US dollars.</p>', ""
        )
        == without
    )
