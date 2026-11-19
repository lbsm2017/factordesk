"""World beta section: schema, hook statuses, pipeline wiring, API and static panel.

Identifiers TWB20-TWB52 (docs/registry/tests.jsonl). All data is synthetic; no network.
"""

from __future__ import annotations

import dataclasses
import json
from datetime import UTC, date, datetime
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from pydantic import ValidationError

from factordesk.analytics.world_beta import MIN_OVERLAP, single_factor_beta
from factordesk.data.prices import (
    HistoryRefresh,
    PriceDataError,
    PriceHistory,
    YFinanceProvider,
)
from factordesk.data.throttle import BatchSettings
from factordesk.pipeline import assemble_report, build_report
from factordesk.report import FactorReport, load_report, render_report_html
from factordesk.report.base import iter_floats
from factordesk.report.panels.world_beta import render_world_beta_panel
from factordesk.report.render_html import esc
from factordesk.report.schema import LABEL_TEXT, SECTIONS, report_label_text
from factordesk.report.sections.world_beta import (
    LABEL_TEXT as WORLD_LABELS,
)
from factordesk.report.sections.world_beta import WorldBetaSection
from factordesk.section_hooks import load_section_inputs
from factordesk.section_hooks.context import DollarInput, SectionInputs, WorldBenchmarkInput
from factordesk.section_hooks.world_beta import UNAVAILABLE_REASON, load_world_benchmark
from factordesk.tests.fixtures.dgp import StaticProvider, default_rf, dgp_a, price_history, rng_for
from factordesk.tests.fixtures.sections import report_with_section
from factordesk.tests.test_api_report import make_world, serve
from factordesk.tests.test_world_beta import BENCH_BETA, Case, make_case, overlap_of

NOW = datetime(2026, 11, 18, 15, 0, tzinfo=UTC)
MOCK = Path(__file__).parent / "fixtures" / "mock_report.json"


def report_for(case: Case, benchmark: WorldBenchmarkInput | None, **kwargs: object) -> FactorReport:
    return assemble_report(
        "STK",
        case.stock,
        case.factors,
        now=NOW,
        factors_downloaded_at=None,
        section_inputs=SectionInputs(world_benchmark=benchmark),
        **kwargs,  # type: ignore[arg-type]
    )


def section_for(case: Case) -> WorldBetaSection:
    report = report_for(case, WorldBenchmarkInput(history=case.bench))
    assert report.world_beta is not None
    return report.world_beta


# ------------------------------------------------------------------------- the ok section
def test_twb20_ok_section_holds_both_fits_on_the_same_days() -> None:
    case = make_case(720)
    s = section_for(case)
    assert s.status == "ok" and s.reason is None and s.proxy == "ACWI"
    assert s.world is not None and s.us_market is not None
    assert s.sample.n == s.n_sample  # the benchmark covers every day
    assert s.sample.start is not None and s.sample.end is not None
    assert s.world.ci_low < BENCH_BETA < s.world.ci_high
    # The US-market regression runs on the very same days: recompute it from the sample.
    report = report_for(case, WorldBenchmarkInput(history=case.bench))
    mkt = report.regression  # the five-factor fit is a different model; check the single factor
    assert mkt.status == "ok"
    sample_rows = s.sample.n
    mkt_rf = case.factors["Mkt-RF"].to_numpy()[-sample_rows:]
    y = case.y[-sample_rows:]
    ref = single_factor_beta(y, mkt_rf)
    assert s.us_market.beta == pytest.approx(ref.beta, abs=1e-12)
    assert s.us_market.se == pytest.approx(ref.se_hac, abs=1e-12)
    assert s.hac_lags == ref.lags
    assert s.comparison == "higher"  # world beta 1.3, independent US factor ~0
    assert s.acwi_last_date == case.bench.frame.index[-1].date()
    assert s.acwi_note is None and s.n_not_in_benchmark == s.n_sample - s.sample.n


def test_twb21_section_serialises_without_non_finite_numbers() -> None:
    s = section_for(make_case(721))
    dumped = json.loads(s.model_dump_json())
    assert all(np.isfinite(v) for v in iter_floats(dumped))
    assert WorldBetaSection.model_validate_json(s.model_dump_json()) == s


def test_twb22_labels_and_footnote_texts_join_the_report_only_when_present() -> None:
    case = make_case(722)
    with_section = report_for(case, WorldBenchmarkInput(history=case.bench))
    without = report_for(case, None)
    assert without.world_beta is None
    for key, text in WORLD_LABELS.items():
        assert with_section.label_text[key] == text and key not in without.label_text
    assert report_label_text({"world_beta": object()}) == {**LABEL_TEXT, **WORLD_LABELS}
    assert "world_beta" in [s.report_field for s in SECTIONS]


def test_twb23_caveats_are_plain_sentences() -> None:
    proxy, asynchronous = WORLD_LABELS["L-WORLD-PROXY"], WORLD_LABELS["L-WORLD-ASYNC"]
    assert "stand-in for the MSCI ACWI index" in proxy and "ETF" in proxy
    assert "close earlier than the US" in asynchronous
    assert "understated" in asynchronous and "not corrected" in asynchronous
    assert "a quick estimate, not a full model" in asynchronous.lower()
    assert "short history has a wide interval" in asynchronous
    for text in (proxy, asynchronous):
        assert "will " not in text and "expect" not in text  # no claim about the future


# ------------------------------------------------------------------------------- statuses
@pytest.mark.parametrize(
    ("returns", "status"), [(MIN_OVERLAP, "ok"), (MIN_OVERLAP - 1, "insufficient_data")]
)
def test_twb24_overlap_of_252_is_ok_and_251_is_insufficient(returns: int, status: str) -> None:
    case = make_case(724, bench_rows=returns + 1)
    s = section_for(case)
    assert s.status == status and s.sample.n == returns
    if status == "insufficient_data":
        assert s.reason is not None and str(returns) in s.reason and "252" in s.reason
        assert s.world is None and s.us_market is None and s.comparison is None


def test_twb25_non_ok_sections_carry_no_numbers() -> None:
    s = section_for(make_case(725, bench_rows=100))
    assert s.status == "insufficient_data"
    dumped = s.model_dump(exclude={"sample"})
    assert not list(iter_floats(dumped, skip_nested_status=True))
    ok_payload = json.loads(section_for(make_case(725)).model_dump_json())
    bad = {**json.loads(s.model_dump_json()), "world": ok_payload["world"]}
    with pytest.raises(ValidationError, match="numeric values are present"):
        WorldBetaSection.model_validate_json(json.dumps(bad))


def test_twb26_constant_benchmark_returns_fail_with_a_reason_not_nan() -> None:
    case = make_case(726)
    flat = price_history(case.rf, case.dates, ticker="ACWI")  # return = RF: zero excess
    s = section_for(dataclasses.replace(case, bench=flat))
    assert s.status == "failed"
    assert s.reason is not None and "does not vary" in s.reason
    assert s.world is None and s.us_market is None


def test_twb27_audit_errors_in_acwi_fail_the_section() -> None:
    case = make_case(727)
    frame = case.bench.frame.copy()
    frame.iloc[600, frame.columns.get_loc("adj_close")] = -5.0  # type: ignore[call-overload]
    s = section_for(dataclasses.replace(case, bench=dataclasses.replace(case.bench, frame=frame)))
    assert s.status == "failed"
    assert s.reason is not None and "price history has errors" in s.reason
    assert "left out until the history is corrected" in s.reason
    assert s.world is None


def _longer_bench(seed: int, first_stock_row: int) -> Case:
    """The stock starts at row ``first_stock_row`` of ACWI's history: older ACWI rows are outside
    the overlap. The stock's first return is on ACWI row ``first_stock_row + 1``, so that return
    rests on ACWI rows ``first_stock_row`` and later."""
    case = make_case(seed)
    stock = dataclasses.replace(case.stock, frame=case.stock.frame.iloc[first_stock_row:])
    return dataclasses.replace(case, stock=stock)


def _with_bad_bench_price(case: Case, row: int) -> Case:
    """A recorded dividend the adjusted close does not carry: an audit error dated at ``row``
    (``distribution_mismatch``) that leaves every return finite, so no day is dropped by it."""
    frame = case.bench.frame.copy()
    close = float(frame.iloc[row, frame.columns.get_loc("close")])  # type: ignore[call-overload]
    # 4 basis points of the price: above the per-event tolerance, below the calendar-year one.
    frame.iloc[row, frame.columns.get_loc("dividends")] = 4e-4 * close  # type: ignore[call-overload]
    return dataclasses.replace(case, bench=dataclasses.replace(case.bench, frame=frame))


def test_twb27b_audit_errors_before_the_overlap_become_a_note_not_a_failure() -> None:
    case = _with_bad_bench_price(_longer_bench(7270, 600), 300)  # years before the stock starts
    s = section_for(case)
    assert s.status == "ok" and s.world is not None
    outside = [w for w in s.audit_warnings if "outside the days used" in w]
    assert len(outside) == 1 and "do not affect this beta" in outside[0]


def test_twb27c_the_row_before_the_first_overlap_return_is_inside_the_window() -> None:
    base = _longer_bench(7271, 600)
    _, overlap = overlap_of(base)
    first_row = int(pd.DatetimeIndex(base.bench.frame.index).get_loc(overlap.dates[0]))  # type: ignore[arg-type]
    # The first return of the overlap rests on the ACWI price one row before its date.
    on_the_edge = section_for(_with_bad_bench_price(base, first_row - 1))
    assert on_the_edge.status == "failed"
    assert on_the_edge.reason is not None and "price history has errors" in on_the_edge.reason
    just_outside = section_for(_with_bad_bench_price(base, first_row - 2))
    assert just_outside.status == "ok"  # no return of the overlap uses that price
    assert any("outside the days used" in w for w in just_outside.audit_warnings)


def test_twb27d_audit_errors_after_the_overlap_become_a_note_too() -> None:
    case = make_case(7272)
    short = dataclasses.replace(case.stock, frame=case.stock.frame.iloc[:-30])
    case = _with_bad_bench_price(dataclasses.replace(case, stock=short), len(case.bench.frame) - 5)
    s = section_for(case)
    assert s.status == "ok"
    assert any("outside the days used" in w for w in s.audit_warnings)


def test_twb27e_an_audit_error_inside_the_overlap_fails_with_its_own_step_in_the_panel() -> None:
    case = _with_bad_bench_price(make_case(7273), 700)
    report = report_for(case, WorldBenchmarkInput(history=case.bench))
    assert report.world_beta is not None and report.world_beta.status == "failed"
    html = render_world_beta_panel(report)
    assert html is not None
    assert "price history has errors" in html
    assert "Run the report again later" not in html  # trying again cannot correct the history
    assert "The rest of the report is not affected." in html


def test_twb28_acwi_audit_warnings_are_carried() -> None:
    case = make_case(728)
    frame = case.bench.frame.drop(case.bench.frame.index[800:812])  # 12 missing business days
    s = section_for(dataclasses.replace(case, bench=dataclasses.replace(case.bench, frame=frame)))
    assert s.status == "ok"  # a warning does not stop the section
    assert any("gap" in w for w in s.audit_warnings)  # the audit the stock's prices get


def test_twb29_nan_inside_the_overlap_is_dropped_not_propagated() -> None:
    case = make_case(729)
    frame = case.bench.frame.copy()
    frame.iloc[1000, frame.columns.get_loc("adj_close")] = np.nan  # type: ignore[call-overload]
    s = section_for(dataclasses.replace(case, bench=dataclasses.replace(case.bench, frame=frame)))
    assert s.status in ("ok", "failed")
    if s.status == "ok":
        assert s.n_not_in_benchmark >= 2


def test_twb30_fetch_failure_without_a_cache_is_a_failed_section_and_the_report_builds() -> None:
    case = make_case(730)
    bench = WorldBenchmarkInput(history=None, unavailable_reason="Could not reach Yahoo for ACWI.")
    report = report_for(case, bench)
    s = report.world_beta
    assert s is not None and s.status == "failed" and s.reason == UNAVAILABLE_REASON
    assert s.acwi_first_date is None and s.acwi_last_date is None
    assert s.acwi_note == "Could not reach Yahoo for ACWI."
    assert report.regression.status == "ok"  # the rest of the report is untouched
    assert render_report_html(report)


def test_twb31_stale_cache_stays_ok_with_the_note_and_the_last_date() -> None:
    case = make_case(731)
    note = "ACWI data ends 2026-09-30; the refresh did not complete (offline)."
    s = report_with_note(case, note)
    assert s.status == "ok" and s.acwi_note == note
    assert s.acwi_last_date == case.bench.frame.index[-1].date()


def report_with_note(case: Case, note: str) -> WorldBetaSection:
    report = report_for(case, WorldBenchmarkInput(history=case.bench, note=note))
    assert report.world_beta is not None
    return report.world_beta


# --------------------------------------------------------------------------- the loader
class Fake:
    def __init__(self, history: PriceHistory | None = None, error: Exception | None = None) -> None:
        self.history, self.error = history, error
        self.calls: list[str] = []

    def fetch(self, ticker: str) -> PriceHistory:
        self.calls.append(ticker)
        if self.error is not None:
            raise self.error
        assert self.history is not None
        return dataclasses.replace(self.history, ticker=ticker)


def test_twb32_loader_asks_the_provider_for_acwi_once() -> None:
    case = make_case(732)
    fake = Fake(case.bench)
    loaded = load_world_benchmark(fake)
    assert fake.calls == ["ACWI"] and loaded.history is not None and loaded.note is None


@pytest.mark.parametrize(
    ("error", "needle"),
    [
        (PriceDataError("No price data returned for 'ACWI'"), "No price data"),
        (ConnectionError("offline"), "ConnectionError"),
        (RuntimeError("Too Many Requests"), "limiting requests"),
        (ValueError("anything else"), "anything else"),
    ],
)
def test_twb33_loader_never_raises(error: Exception, needle: str) -> None:
    loaded = load_world_benchmark(Fake(error=error))
    assert loaded.history is None and loaded.unavailable_reason is not None
    assert needle in loaded.unavailable_reason


def test_twb34_loader_uses_the_incremental_refresh_when_the_provider_has_one() -> None:
    case = make_case(734)

    class Incremental(Fake):
        def fetch_incremental(self, ticker: str) -> HistoryRefresh:
            self.calls.append(f"incremental:{ticker}")
            assert self.history is not None
            return HistoryRefresh(self.history, "stale", "ACWI data ends 2026-09-30; offline.")

    fake = Incremental(case.bench)
    loaded = load_world_benchmark(fake)
    assert fake.calls == ["incremental:ACWI"]
    assert loaded.note == "ACWI data ends 2026-09-30; offline."


def _yahoo_provider(tmp_path: Path, history: PriceHistory, fail: bool) -> YFinanceProvider:
    """A real ``YFinanceProvider`` whose downloads serve ``history`` (or fail)."""

    def raw(start: date | None) -> pd.DataFrame:
        if fail:
            raise ConnectionError("offline")
        f = history.frame.copy()
        f = f if start is None else f.loc[f.index >= pd.Timestamp(start)]
        f.index = pd.DatetimeIndex(f.index, name="Date").tz_localize("America/New_York")
        f.columns = pd.Index(
            [{"close": "Close", "adj_close": "Adj Close"}.get(c, c.title()) for c in f.columns]
        )
        return f.rename(columns={"Splits": "Stock Splits"})

    return YFinanceProvider(
        cache_dir=tmp_path / "prices",
        now=lambda: NOW,
        settings=BatchSettings(1, 1, 0.0, 1, 3),
        download=lambda ticker: raw(None),
        download_since=lambda ticker, start: raw(start),
        sleep=lambda _s: None,
    )


def test_twb35_real_provider_cold_failure_is_unavailable_and_warm_failure_is_stale(
    tmp_path: Path,
) -> None:
    case = make_case(735, n=900)
    cold = load_world_benchmark(_yahoo_provider(tmp_path, case.bench, fail=True))
    assert cold.history is None and cold.unavailable_reason is not None
    # A cache from an earlier day, then a failed refresh: the section is built from the cache.
    old = datetime(2026, 11, 12, 15, 0, tzinfo=UTC)
    seeded = YFinanceProvider(
        cache_dir=tmp_path / "prices",
        now=lambda: old,
        download=lambda t: _yahoo_provider(tmp_path, case.bench, False)._download(t),  # pyright: ignore[reportPrivateUsage]
    )
    seeded.fetch("ACWI")
    warm = load_world_benchmark(_yahoo_provider(tmp_path, case.bench, fail=True))
    assert warm.history is not None
    assert warm.note is not None and warm.note.startswith("ACWI data ends ")


# ------------------------------------------------------------------------- the wiring
def no_portfolios(*args: object, **kwargs: object) -> None:
    """Stands in for the Ken French portfolio loader: no network in these tests."""
    return None


def no_dollar(*args: object, **kwargs: object) -> DollarInput:
    """Stands in for the FRED dollar index loader: no network in these tests."""
    return DollarInput(levels=None, unavailable_reason="offline")


def test_twb36_load_section_inputs_fetches_acwi_through_the_given_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("factordesk.section_hooks.load_shrinkage_inputs", no_portfolios)
    monkeypatch.setattr("factordesk.section_hooks.macro.load_dollar", no_dollar)
    fake = Fake(make_case(736).bench)
    inputs = load_section_inputs(NOW, offline=False, price_provider=fake)
    assert fake.calls[:2] == ["ACWI", "IEUR"] and inputs.world_benchmark is not None
    assert fake.calls[2:] == ["IEF", "LQD", "DBC", "TIP", "IEI"]  # the macro section's funds
    # Offline (factors injected) or without a provider: nothing is fetched.
    offline = load_section_inputs(NOW, offline=True, price_provider=fake)
    assert offline.world_benchmark is None and len(fake.calls) == 7
    assert load_section_inputs(NOW, offline=False).world_benchmark is None


def test_twb37_build_report_fills_the_section_through_the_pipeline_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case = make_case(737)
    monkeypatch.setattr("factordesk.section_hooks.load_shrinkage_inputs", no_portfolios)
    monkeypatch.setattr("factordesk.section_hooks.macro.load_dollar", no_dollar)

    def load_factors(**kwargs: object) -> pd.DataFrame:
        return case.factors

    def no_status(**kwargs: object) -> None:
        return None

    monkeypatch.setattr("factordesk.pipeline.factor_data.load_ff5_daily", load_factors)
    monkeypatch.setattr("factordesk.pipeline.factor_data.factor_status", no_status)

    class Two:
        def __init__(self) -> None:
            self.calls: list[str] = []

        def fetch(self, ticker: str) -> PriceHistory:
            self.calls.append(ticker)
            source = case.bench if ticker == "ACWI" else case.stock
            return dataclasses.replace(source, ticker=ticker)

    provider = Two()
    report = build_report("STK", provider, now=NOW)
    # one extra fetch per proxy and run, then the five funds of the macro section
    assert provider.calls == ["STK", "ACWI", "IEUR", "IEF", "LQD", "DBC", "TIP", "IEI"]
    assert report.world_beta is not None and report.world_beta.status == "ok"


def test_twb38_injected_factors_keep_the_cli_offline() -> None:
    case = make_case(738)
    fake = Fake(case.bench)
    report = build_report("STK", StaticProvider(case.stock), factors=case.factors, now=NOW)
    assert report.world_beta is None and fake.calls == []


def test_twb39_api_report_includes_the_section_and_refreshes_every_build(tmp_path: Path) -> None:
    from factordesk.api.main import create_app

    world = make_world(tmp_path)
    d = dgp_a(rng_for(739), n=1400)
    rf = default_rf(1400)
    x = np.random.default_rng(5).normal(0.0004, 0.009, size=1400)
    bench = price_history(rf + x, d.dates, ticker="ACWI")
    calls: list[int] = []

    def loader() -> WorldBenchmarkInput:
        calls.append(1)
        return WorldBenchmarkInput(history=bench)

    deps = dataclasses.replace(world.service.deps, load_world_benchmark=loader)
    with serve(create_app(deps)) as client:
        first = client.get("/api/report/SYN")
        other = client.get("/api/report/SYN?range=3Y")
        assert first.status_code == 200 and other.status_code == 200
        assert FactorReport.model_validate_json(first.text).world_beta is not None
        assert len(calls) == 2  # on every report build (a repeated key is served from memory)
        assert client.get("/api/report/SYN").status_code == 200 and len(calls) == 2


# ------------------------------------------------------------------------- the schema
def test_twb40_world_beta_is_none_by_default_and_for_old_files() -> None:
    assert load_report(MOCK).world_beta is None
    assert json.loads(MOCK.read_text(encoding="utf-8"))["world_beta"] is None


def test_twb41_status_rules_are_enforced() -> None:
    s = section_for(make_case(741))
    payload = json.loads(s.model_dump_json())
    cases = (
        ({**payload, "status": "unavailable"}, "Input should be"),  # not an M0.7 value
        ({**payload, "status": "failed"}, "reason must be None"),  # failed needs a reason
        ({**payload, "reason": "x"}, "reason must be None"),  # ok must not carry a reason
        ({**payload, "world": None}, "fills both fits"),  # ok needs both fits
        ({**payload, "acwi_first_date": "2030-01-01"}, "is after"),  # first after last
        ({**payload, "acwi_last_date": None}, "both set or both null"),  # one date only
    )
    for bad, message in cases:
        with pytest.raises(ValidationError, match=message):
            WorldBetaSection.model_validate_json(json.dumps(bad))


# ---------------------------------------------------------------------------- the panel
def test_twb42_absent_section_renders_nothing() -> None:
    assert render_world_beta_panel(load_report(MOCK)) is None
    assert 'id="world-beta"' not in render_report_html(load_report(MOCK))


def test_twb43_ok_panel_shows_three_rows_the_sentence_and_the_footnotes() -> None:
    report = report_with_section(load_report(MOCK), "world_beta")
    html = render_world_beta_panel(report)
    assert html is not None and 'id="world-beta"' in html
    assert "World beta (quick estimate)" in html
    assert html.count("<tbody><tr>") == 1 and html.count('<tr><th scope="row">') == 3
    assert "Against the world (ACWI)" in html and "Against the US market, same days" in html
    assert "R squared" in html and "95% interval" in html and "Days" in html
    assert report.world_beta is not None
    assert report.world_beta.comparison_text is not None
    assert report.world_beta.comparison_text.replace("'", "&#x27;") in html
    assert '<details class="how"><summary>How this is computed</summary>' in html
    assert "stand-in for the MSCI ACWI index" in html and "not a full model" in html
    assert "ACWI data ends 30 Sep 2026." in html
    assert html.index("Against the world") < html.index("How this is computed")
    assert "<style" not in html and "color:" not in html  # existing classes only


def test_twb44_panel_sits_right_after_the_factor_exposures() -> None:
    page = render_report_html(report_with_section(load_report(MOCK), "world_beta"))
    ids = [m for m in __import__("re").findall(r'<section class="panel[^"]*" id="([^"]+)"', page)]
    assert ids.index("world-beta") == ids.index("exposures") + 1


def test_twb45_panel_shows_the_stale_note_and_the_reason_of_a_failed_section() -> None:
    base = report_with_section(load_report(MOCK), "world_beta")
    assert base.world_beta is not None
    stale = base.model_copy(
        update={
            "world_beta": base.world_beta.model_copy(
                update={"acwi_note": "ACWI data ends 2026-09-30; offline."}
            )
        }
    )
    html = render_world_beta_panel(stale)
    assert html is not None and "ACWI data ends 2026-09-30; offline." in html

    failed = json.loads(base.world_beta.model_dump_json())
    failed.update(
        status="failed",
        reason=UNAVAILABLE_REASON,
        world=None,
        us_market=None,
        comparison=None,
        comparison_text=None,
        hac_lags=None,
        acwi_first_date=None,
        acwi_last_date=None,
        acwi_note="Could not reach Yahoo for ACWI.",
        europe=None,
    )
    section = WorldBetaSection.model_validate_json(json.dumps(failed))
    report = base.model_copy(update={"world_beta": section})
    html = render_world_beta_panel(report)
    assert html is not None
    assert esc(UNAVAILABLE_REASON) in html and "Could not reach Yahoo for ACWI." in html
    assert "<table" not in html and "ACWI data ends" not in html.replace("Could not", "")


def test_twb46_comparison_sentences_reach_the_panel_for_every_outcome() -> None:
    # Overlapping intervals and disjoint intervals, through the real hook.
    same = section_for(make_case(746, beta=1.0))  # US factor independent: world ~1.0 vs US ~0
    assert same.comparison is not None
    higher = section_for(make_case(747, beta=BENCH_BETA))
    assert higher.comparison == "higher"
    assert higher.comparison_text is not None
    assert higher.comparison_text.startswith("Higher against the world")
    assert "do not overlap" in higher.comparison_text
