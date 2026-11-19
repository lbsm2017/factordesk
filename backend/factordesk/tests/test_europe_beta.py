"""Europe block of the world beta section: IEUR through the same hook, cache and panel as ACWI.

Identifiers TEB01-TEB20 (docs/registry/tests.jsonl). All data is synthetic; no network.
"""

from __future__ import annotations

import dataclasses
import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from pydantic import ValidationError

from factordesk.analytics.world_beta import (
    BENCHMARK_TICKER,
    EUROPE_TICKER,
    MIN_OVERLAP,
    PROXIES,
    single_factor_beta,
)
from factordesk.data.prices import PriceDataError, PriceHistory, YFinanceProvider
from factordesk.pipeline import assemble_report
from factordesk.report import FactorReport, load_report
from factordesk.report.base import iter_floats
from factordesk.report.panels.world_beta import render_world_beta_panel
from factordesk.report.render_html import esc
from factordesk.report.sections.world_beta import ProxyBeta, WorldBetaSection
from factordesk.section_hooks import load_section_inputs
from factordesk.section_hooks.context import SectionInputs, WorldBenchmarkInput
from factordesk.section_hooks.world_beta import (
    EUROPE_UNAVAILABLE_REASON,
    UNAVAILABLE_REASON,
    load_world_benchmark,
)
from factordesk.tests.fixtures.dgp import price_history
from factordesk.tests.fixtures.sections import report_with_section
from factordesk.tests.test_section_world_beta import (
    NOW,
    Fake,
    _yahoo_provider,  # pyright: ignore[reportPrivateUsage]
    no_portfolios,
)
from factordesk.tests.test_world_beta import Case, make_case

MOCK = Path(__file__).parent / "fixtures" / "mock_report.json"


def europe_bench(case: Case, seed: int, rows: int | None = None) -> PriceHistory:
    """An IEUR history on the dates of ``case``: its own independent daily returns.

    ``rows`` keeps only the last ``rows`` price rows (a fund that started later).
    """
    rng = np.random.default_rng(seed)
    z = rng.normal(0.0004, 0.009, size=len(case.dates))
    ret = case.rf + z
    history = price_history(ret, case.dates, ticker=EUROPE_TICKER)
    if rows is None:
        return history
    k = rows - 1
    return price_history(ret[-k:], case.dates[-k:], case.dates[-k - 1], EUROPE_TICKER)


def report_for(
    case: Case, world: WorldBenchmarkInput | None, europe: WorldBenchmarkInput | None
) -> FactorReport:
    return assemble_report(
        "STK",
        case.stock,
        case.factors,
        now=NOW,
        factors_downloaded_at=None,
        section_inputs=SectionInputs(world_benchmark=world, europe_benchmark=europe),
    )


def section_of(case: Case, europe: WorldBenchmarkInput | None) -> WorldBetaSection:
    report = report_for(case, WorldBenchmarkInput(history=case.bench), europe)
    assert report.world_beta is not None
    return report.world_beta


def europe_input(case: Case, seed: int = 9, rows: int | None = None) -> WorldBenchmarkInput:
    return WorldBenchmarkInput(history=europe_bench(case, seed, rows))


# ------------------------------------------------------------------------- the proxy list
def test_teb01_the_constant_list_names_both_proxies() -> None:
    assert PROXIES == (("world", "ACWI", "MSCI ACWI"), ("europe", "IEUR", "MSCI Europe"))
    assert (BENCHMARK_TICKER, EUROPE_TICKER) == ("ACWI", "IEUR")


def test_teb02_the_list_drives_both_blocks_from_the_same_computation() -> None:
    case = make_case(8002, n=900)
    s = section_of(case, europe_input(case))
    assert s.status == "ok" and s.europe is not None and s.europe.status == "ok"
    assert (s.proxy, s.europe.proxy, s.europe.label) == ("ACWI", "IEUR", "MSCI Europe")
    # The Europe block is what the ACWI fields would be for the IEUR history: same shape,
    # its own same-days US market fit and comparison.
    same_days = section_of(
        dataclasses.replace(case, bench=europe_bench(case, 9)), None
    )  # the ACWI path, fed with the IEUR history
    e = s.europe
    assert e.benchmark is not None and same_days.world is not None
    assert e.benchmark == same_days.world
    assert e.us_market == same_days.us_market
    assert e.comparison == same_days.comparison and e.hac_lags == same_days.hac_lags
    assert e.n_days == same_days.sample.n and e.first_date == same_days.acwi_first_date
    assert e.comparison_text is not None and "Europe" in e.comparison_text
    assert "world" not in e.comparison_text


def test_teb03_europe_beta_matches_plain_numpy() -> None:
    case = make_case(8003, n=900)
    s = section_of(case, europe_input(case))
    assert s.europe is not None and s.europe.benchmark is not None
    ieur = europe_bench(case, 9).total_returns.to_numpy()[-len(case.rf) :]
    x = np.asarray(ieur - case.rf, dtype=np.float64)
    y = case.y
    slope = float(np.polyfit(x, y, 1)[0])
    assert s.europe.benchmark.beta == pytest.approx(slope, abs=1e-9)
    ref = single_factor_beta(y, x, "IEUR")
    assert s.europe.benchmark.se == pytest.approx(ref.se_hac, abs=1e-12)


def test_teb04_a_missing_europe_input_leaves_the_block_null_and_acwi_unchanged() -> None:
    case = make_case(8004)
    without = section_of(case, None)
    assert without.europe is None
    with_europe = section_of(case, europe_input(case))
    a, b = without.model_dump(exclude={"europe"}), with_europe.model_dump(exclude={"europe"})
    assert a == b  # every ACWI field is unchanged by the Europe block


# ------------------------------------------------------------------------- europe fails alone
def test_teb05_a_failed_europe_fetch_leaves_acwi_ok() -> None:
    case = make_case(8005)
    down = WorldBenchmarkInput(history=None, unavailable_reason="Could not reach Yahoo for IEUR.")
    s = section_of(case, down)
    assert s.status == "ok" and s.world is not None and s.reason is None
    assert s.europe is not None and s.europe.status == "failed"
    assert s.europe.reason == EUROPE_UNAVAILABLE_REASON
    assert s.europe.note == "Could not reach Yahoo for IEUR."
    assert s.europe.benchmark is None and s.europe.first_date is None
    assert s.acwi_note is None  # the ACWI note is its own


@pytest.mark.parametrize(
    ("rows", "status"), [(MIN_OVERLAP + 1, "ok"), (MIN_OVERLAP, "insufficient_data")]
)
def test_teb06_europe_needs_252_common_days(rows: int, status: str) -> None:
    case = make_case(8006, n=900)
    s = section_of(case, europe_input(case, rows=rows))
    assert s.status == "ok"  # the ACWI fit is not touched
    assert s.europe is not None and s.europe.status == status
    if status == "insufficient_data":
        assert s.europe.reason is not None and "IEUR" in s.europe.reason
        assert str(MIN_OVERLAP - 1) in s.europe.reason and "252" in s.europe.reason
        assert s.europe.benchmark is None and s.europe.us_market is None
        assert s.europe.n_days == MIN_OVERLAP - 1


def test_teb07_a_fund_that_starts_after_the_analysis_starts_still_fits() -> None:
    # IEUR has half the days of the sample (as a 2014 fund against a 2008 analysis).
    case = make_case(8007, n=900)
    s = section_of(case, europe_input(case, rows=451))
    assert s.europe is not None and s.europe.status == "ok"
    assert s.europe.n_days == 450 < s.sample.n == 900
    assert s.europe.n_not_in_benchmark == 450
    assert s.europe.us_market is not None and s.us_market is not None
    assert s.europe.us_market != s.us_market  # its own same-days US fit


def test_teb08_audit_errors_in_ieur_fail_only_the_europe_block() -> None:
    case = make_case(8008, n=900)
    history = europe_bench(case, 9)
    frame = history.frame.copy()
    frame.loc[frame.index[300], "adj_close"] = -1.0
    bad = WorldBenchmarkInput(history=dataclasses.replace(history, frame=frame))
    s = section_of(case, bad)
    assert s.status == "ok"
    assert s.europe is not None and s.europe.status == "failed" and s.europe.reason is not None
    assert "IEUR" in s.europe.reason and "Europe beta is not computed" in s.europe.reason


def test_teb09_acwi_failing_alone_leaves_europe_ok() -> None:
    case = make_case(8009)
    down = WorldBenchmarkInput(history=None, unavailable_reason="offline")
    report = report_for(case, down, europe_input(case))
    s = report.world_beta
    assert s is not None and s.status == "failed" and s.reason == UNAVAILABLE_REASON
    assert s.world is None and s.europe is not None and s.europe.status == "ok"


# ------------------------------------------------------------------------- loader and cache
def test_teb10_load_section_inputs_fetches_both_proxies_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("factordesk.section_hooks.load_shrinkage_inputs", no_portfolios)
    fake = Fake(make_case(8010).bench)
    inputs = load_section_inputs(NOW, offline=False, price_provider=fake)
    assert fake.calls == ["ACWI", "IEUR"]
    assert inputs.world_benchmark is not None and inputs.europe_benchmark is not None
    offline = load_section_inputs(NOW, offline=True, price_provider=fake)
    assert offline.europe_benchmark is None and fake.calls == ["ACWI", "IEUR"]


def test_teb11_loader_never_raises_for_ieur() -> None:
    fake = Fake(error=PriceDataError("No price data returned for 'IEUR'"))
    loaded = load_world_benchmark(fake, EUROPE_TICKER)
    assert fake.calls == ["IEUR"] and loaded.history is None
    assert loaded.unavailable_reason is not None and "IEUR" in loaded.unavailable_reason


def test_teb12_real_provider_caches_ieur_beside_acwi_and_serves_a_stale_cache(
    tmp_path: Path,
) -> None:
    case = make_case(8012, n=900)
    ieur = europe_bench(case, 9)
    cold = load_world_benchmark(_yahoo_provider(tmp_path, ieur, fail=True), EUROPE_TICKER)
    assert cold.history is None and cold.unavailable_reason is not None
    old = datetime(2026, 11, 12, 15, 0, tzinfo=UTC)

    def raw(ticker: str) -> pd.DataFrame:
        return _yahoo_provider(tmp_path, ieur, False)._download(ticker)  # pyright: ignore[reportPrivateUsage]

    YFinanceProvider(cache_dir=tmp_path / "prices", now=lambda: old, download=raw).fetch("IEUR")
    assert list((tmp_path / "prices").glob("IEUR_*.parquet"))
    warm = load_world_benchmark(_yahoo_provider(tmp_path, ieur, fail=True), EUROPE_TICKER)
    assert warm.history is not None
    assert warm.note is not None and warm.note.startswith("IEUR data ends ")


# ------------------------------------------------------------------------- the schema
def test_teb13_europe_block_validates_and_serialises() -> None:
    case = make_case(8013)
    s = section_of(case, europe_input(case))
    dumped = json.loads(s.model_dump_json())
    assert all(np.isfinite(v) for v in iter_floats(dumped))
    assert WorldBetaSection.model_validate_json(s.model_dump_json()) == s
    assert not list(iter_floats(dumped["europe"]["audit_warnings"]))
    assert s.model_dump_json().count('"benchmark"') == 1


def test_teb14_block_status_rules_are_enforced() -> None:
    case = make_case(8014)
    ok = json.loads(section_of(case, europe_input(case)).model_dump_json())["europe"]
    with pytest.raises(ValidationError, match="reason must be None"):
        ProxyBeta.model_validate_json(json.dumps({**ok, "status": "failed"}))
    bad = {**ok, "status": "insufficient_data", "reason": "short"}
    with pytest.raises(ValidationError, match="carries no fits"):
        ProxyBeta.model_validate_json(json.dumps(bad))
    with pytest.raises(ValidationError, match="ok block fills"):
        ProxyBeta.model_validate_json(json.dumps({**ok, "benchmark": None}))
    with pytest.raises(ValidationError, match="both set or both null"):
        ProxyBeta.model_validate_json(json.dumps({**ok, "first_date": None}))


def test_teb15_old_files_without_a_europe_key_still_load() -> None:
    case = make_case(8015)
    payload = json.loads(section_of(case, None).model_dump_json())
    payload.pop("europe")
    assert WorldBetaSection.model_validate_json(json.dumps(payload)).europe is None


# ------------------------------------------------------------------------- the static panel
def rows_of(html: str) -> int:
    return html.count('<tr><th scope="row">')


def test_teb16_panel_renders_three_rows_with_the_europe_sub_label_and_footnote() -> None:
    report = report_with_section(load_report(MOCK), "world_beta")
    html = render_world_beta_panel(report)
    assert html is not None and rows_of(html) == 3
    assert "Against the world (ACWI)" in html and "Against the US market, same days" in html
    assert 'Europe <span class="sub">IEUR, MSCI Europe stand-in</span>' in html
    row = '<tr><th scope="row">'
    assert (
        html.index(f"{row}Against the world")
        < html.index(f"{row}Europe")
        < html.index(f"{row}Against the US")
    )
    assert "stand-in for the MSCI ACWI index" in html
    assert "stand-in for the MSCI Europe index" in html and "June 2014" in html
    assert "IEUR data ends 30 Sep 2026." in html
    assert report.world_beta is not None and report.world_beta.europe is not None
    text = report.world_beta.europe.comparison_text
    assert text is not None and esc(text) in html


def test_teb17_panel_adds_a_fourth_row_when_the_europe_days_differ() -> None:
    case = make_case(8017, n=900)
    s = section_of(case, europe_input(case, rows=451))
    report = report_with_section(load_report(MOCK), "world_beta").model_copy(
        update={"world_beta": s}
    )
    html = render_world_beta_panel(report)
    assert html is not None and rows_of(html) == 4
    assert "Against the US market, same days as Europe" in html and "450" in html


def test_teb18_panel_without_europe_is_the_two_row_panel() -> None:
    base = report_with_section(load_report(MOCK), "world_beta")
    assert base.world_beta is not None
    report = base.model_copy(
        update={"world_beta": base.world_beta.model_copy(update={"europe": None})}
    )
    html = render_world_beta_panel(report)
    assert html is not None and rows_of(html) == 2
    assert "IEUR" not in html and "June 2014" not in html


def test_teb19_panel_names_a_failed_europe_block_and_keeps_the_acwi_rows() -> None:
    case = make_case(8019)
    down = WorldBenchmarkInput(history=None, unavailable_reason="Could not reach Yahoo for IEUR.")
    s = section_of(case, down)
    report = report_with_section(load_report(MOCK), "world_beta").model_copy(
        update={"world_beta": s}
    )
    html = render_world_beta_panel(report)
    assert html is not None and rows_of(html) == 2
    assert "Europe row not shown" in html and esc(EUROPE_UNAVAILABLE_REASON) in html


def test_teb20_panel_shows_europe_when_acwi_fails_alone() -> None:
    case = make_case(8020)
    down = WorldBenchmarkInput(history=None, unavailable_reason="offline")
    s = report_for(case, down, europe_input(case)).world_beta
    assert s is not None
    report = report_with_section(load_report(MOCK), "world_beta").model_copy(
        update={"world_beta": s}
    )
    html = render_world_beta_panel(report)
    assert html is not None and esc(UNAVAILABLE_REASON) in html
    assert "Against the world (ACWI)" not in html and 'Europe <span class="sub">' in html
