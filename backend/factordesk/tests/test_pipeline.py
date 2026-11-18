"""End-to-end ``build_report`` tests (test-oracle T35, T105-T107, T109, T115)."""

from __future__ import annotations

import json
import math
import warnings
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, cast

import pytest

from factordesk.analytics.regression import run_regression
from factordesk.analytics.rolling import rolling_betas
from factordesk.analytics.sample import FACTOR_CODES, InsufficientHistoryError, build_sample
from factordesk.data.factors import load_ff5_daily
from factordesk.data.prices import PriceDataError, YFinanceProvider
from factordesk.pipeline import assemble_report, build_report
from factordesk.report import (
    FACTOR_NAMES,
    FactorReport,
    dump_report,
    load_report,
    render_report_html,
)
from factordesk.report.schema import STATISTIC_MODELS, SampleInfo
from factordesk.tests.fixtures.dgp import StaticProvider, dgp_a, rng_for

NOW = datetime(2026, 11, 18, 15, 0, tzinfo=UTC)


def _report(n: int = 2520, tail: int = 0, test_number: int = 107) -> FactorReport:
    d = dgp_a(rng_for(test_number), n=n + tail)
    factors = d.factors.iloc[:n]
    return build_report("syn", StaticProvider(d.history), factors=factors, now=NOW)


def test_build_report_end_to_end() -> None:
    d = dgp_a(rng_for(107), n=2550)
    provider = StaticProvider(d.history)
    rep = build_report("syn", provider, factors=d.factors.iloc[:2520], now=NOW)
    assert provider.calls == ["SYN"]
    assert rep.ticker == "SYN"
    assert rep.generated_at == NOW
    assert rep.data.n_obs == 2520
    assert rep.data.actual_start == date(2010, 1, 4)
    assert rep.data.actual_end == rep.data.factors_last_date == d.dates[2519].date()
    assert rep.data.dropped_price_dates_after_factors == 30 == rep.data.uncovered.n
    assert rep.data.requested_end == d.dates[-1].date()
    assert rep.data.factors_downloaded_at is None
    assert rep.data.audit_status == "clean"
    assert rep.regression.hac_lags == 8 and rep.regression.bh_family_size == 5
    assert [f.name for f in rep.regression.factors] == list(FACTOR_NAMES)
    assert [w.window for w in rep.rolling] == [126, 252]
    for w in rep.rolling:
        assert w.n_stamps == 2520 - w.window + 1
        assert w.betas["Mkt-RF"][w.window - 2] is None
        assert w.betas["Mkt-RF"][w.window - 1] is not None
        assert w.window_start[w.window - 1] == rep.data.actual_start
    assert rep.average_beta.window == 252 and rep.average_beta.n_stamps == 2269
    assert rep.return_contribution.memo[0].startswith("Not covered by factor data: 30 trading")
    assert rep.risk_contribution.order[-1] == "Idiosyncratic"
    codes = {w.code for w in rep.warnings}
    assert "factor_data_lag" in codes and "short_history" not in codes
    assert any("survivor" in n.lower() for n in rep.notes)
    page = render_report_html(rep)
    assert "SYN" in page and "Not in the sum" in page


def test_t35_refusal_and_short_history_warning() -> None:
    d = dgp_a(rng_for(35), n=503)
    with pytest.raises(InsufficientHistoryError) as info:
        build_report("syn", StaticProvider(d.history), factors=d.factors, now=NOW)
    assert (info.value.n, info.value.required) == (503, 504)
    rep = _report(n=504, test_number=35)
    assert "short_history" in {w.code for w in rep.warnings}


def test_build_report_validates_inputs() -> None:
    d = dgp_a(rng_for(107), n=600)
    provider = StaticProvider(d.history)
    with pytest.raises(PriceDataError):
        build_report("../etc", provider, factors=d.factors, now=NOW)
    assert provider.calls == []
    with pytest.raises(ValueError, match="timezone-aware"):
        build_report("SYN", provider, factors=d.factors, now=datetime(2026, 11, 18))


def test_requested_range_reaches_every_sample() -> None:
    d = dgp_a(rng_for(108), n=1300)
    factors = d.factors.iloc[:1280]
    start, end = date(2011, 2, 1), date(2014, 6, 30)
    rep = build_report(
        "syn", StaticProvider(d.history), factors=factors, now=NOW, start=start, end=end
    )
    stats = [
        rep.regression,
        *rep.rolling,
        rep.average_beta,
        rep.return_contribution,
        rep.risk_contribution,
        rep.residual_diagnostics,
        rep.quality_gate,
        rep.five_day_regression,
    ]
    for stat in stats:
        assert (stat.sample.requested_start, stat.sample.requested_end) == (start, end)
    assert (rep.data.requested_start, rep.data.requested_end) == (start, end)
    assert rep.data.actual_start is not None and rep.data.actual_start >= start
    assert rep.data.actual_end is not None and rep.data.actual_end <= end
    assert rep.data.uncovered.n == 0
    expected = build_sample(d.history, factors, start, end)
    assert rep.data.n_obs == expected.n
    # assemble_report takes the same keywords
    direct = assemble_report(
        "SYN",
        d.history,
        factors,
        now=NOW,
        factors_downloaded_at=None,
        start=start,
        end=end,
    )
    assert direct == rep


def test_default_range_is_the_whole_history() -> None:
    d = dgp_a(rng_for(108), n=700)
    factors = d.factors.iloc[:680]
    default = build_report("syn", StaticProvider(d.history), factors=factors, now=NOW)
    explicit = build_report(
        "syn",
        StaticProvider(d.history),
        factors=factors,
        now=NOW,
        start=d.dates[0].date(),
        end=d.dates[-1].date(),
    )
    assert default == explicit
    assert default.data.requested_start == d.dates[0].date()
    assert default.data.requested_end == d.dates[-1].date()


def _is_statistic(value: object) -> bool:
    return isinstance(value, STATISTIC_MODELS)


def test_t105_sample_metadata_everywhere() -> None:
    required = {"status", "reason", "sample"}
    for model in STATISTIC_MODELS:
        assert required <= set(model.model_fields), model.__name__
        assert model.model_fields["sample"].annotation in (SampleInfo, "SampleInfo")
    assert {
        "n",
        "start",
        "end",
        "requested_start",
        "requested_end",
        "n_excluded",
        "excluded",
        "factor_vintage",
    } <= set(SampleInfo.model_fields)
    rep = _report(n=600)
    stats = [
        rep.regression,
        *rep.rolling,
        rep.average_beta,
        rep.return_contribution,
        rep.risk_contribution,
        rep.residual_diagnostics,
        rep.quality_gate,
        rep.five_day_regression,
    ]
    assert all(_is_statistic(s) for s in stats)
    # Every statistic-typed field of the report is covered by the list above.
    for name in FactorReport.model_fields:
        value = getattr(rep, name)
        items: list[object] = cast(list[object], value) if isinstance(value, list) else [value]
        if any(_is_statistic(v) for v in items):
            assert name in {
                "regression",
                "rolling",
                "average_beta",
                "return_contribution",
                "risk_contribution",
                "residual_diagnostics",
                "quality_gate",
                "five_day_regression",
            }


def _walk_floats(value: Any) -> list[float]:
    if isinstance(value, float):
        return [value]
    if isinstance(value, dict):
        return [x for v in value.values() for x in _walk_floats(v)]  # pyright: ignore[reportUnknownVariableType]
    if isinstance(value, list):
        return [x for v in value for x in _walk_floats(v)]  # pyright: ignore[reportUnknownVariableType]
    return []


def test_t106_no_nan_in_json() -> None:
    rep = _report(n=600, tail=10, test_number=106)
    payload = rep.model_dump(mode="json")
    text = json.dumps(payload, allow_nan=False)
    assert "NaN" not in text and "Infinity" not in text
    assert all(math.isfinite(x) for x in _walk_floats(payload))
    for stat in [rep.regression, *rep.rolling, rep.average_beta]:
        if stat.status != "ok":
            assert stat.reason


def test_t107_identities_survive_the_round_trip(tmp_path: Path) -> None:
    rep = _report()
    path = tmp_path / "r.json"
    path.write_text(rep.model_dump_json(), encoding="utf-8")
    back = FactorReport.model_validate_json(path.read_text(encoding="utf-8"))
    assert back == rep
    rc = back.return_contribution
    parts = [v for v in rc.factors.values() if v is not None]
    assert rc.alpha is not None and rc.residual is not None
    assert rc.total_annualised_mean_excess_return is not None
    lhs = sum(parts) + rc.alpha + rc.residual
    assert abs(lhs - rc.total_annualised_mean_excess_return) <= 1e-10
    rk = back.risk_contribution
    shares = [v for v in rk.factors.values() if v is not None]
    assert rk.idiosyncratic is not None
    assert abs(sum(shares) + rk.idiosyncratic - 1.0) <= 1e-10
    assert back.regression.r2 is not None
    assert abs((1 - rk.idiosyncratic) - back.regression.r2) <= 1e-10


def test_t128_json_precision_and_size(tmp_path: Path) -> None:
    d = dgp_a(rng_for(128), n=900)
    rep = build_report("syn", StaticProvider(d.history), factors=d.factors, now=NOW)
    sample = build_sample(d.history, d.factors)
    for window in rep.rolling:
        ref = rolling_betas(sample, window.window)
        for code, name in zip(FACTOR_CODES, FACTOR_NAMES, strict=True):
            for kind, series, exact in (
                ("beta", window.betas[name], ref.betas[code]),
                ("se", window.se[name], ref.se[code]),
            ):
                assert len(series) == len(exact)
                for value, true in zip(series, exact.to_numpy(), strict=True):
                    if value is None:
                        assert math.isnan(true)
                        continue
                    assert value == float(f"{value:.6g}"), (kind, value)
                    assert abs(value - true) <= 5e-6 * abs(true), (kind, value, true)
    # Everything else is exact.
    reg = run_regression(sample)
    assert rep.regression.alpha_annual == reg.alpha_ann
    assert [f.beta for f in rep.regression.factors] == [float(b) for b in reg.betas]
    path = tmp_path / "r.json"
    dump_report(rep, path)
    text = path.read_text(encoding="utf-8")
    assert "\n " not in text and text.count("\n") == 1
    assert load_report(path) == rep


def test_rolling_bands_match_se() -> None:
    rep = _report(n=700)
    w = rep.rolling[1]
    i = 400
    beta, se = w.betas["HML"][i], w.se["HML"][i]
    assert beta is not None and se is not None and se > 0
    assert w.ci_z == pytest.approx(1.959963984540054, rel=1e-15)


@pytest.mark.live
def test_live_spy(tmp_path: Path) -> None:
    """``build_report("SPY")`` on live data: T109 bounds and T115 identities (network).

    T109 specifies the sample 2010-01-04 to the factor last date, so its bounds are checked on
    that sample. The full-history report (from 1993) gets the identities, and its lower R2 must
    come with the residual quality gate of methodology M3.6 (non-synchronous closes before
    about 2009), which the report itself discloses.
    """
    factors = load_ff5_daily(data_dir=tmp_path)
    provider = YFinanceProvider(cache_dir=tmp_path / "prices")
    rep = build_report("SPY", provider, factors=factors)

    # T109 on the oracle's sample.
    history = provider.fetch("SPY")
    reg = run_regression(build_sample(history, factors, date(2010, 1, 4)))
    b = dict(zip(reg.names, (float(x) for x in reg.betas), strict=True))
    assert 0.93 <= b["Mkt-RF"] <= 1.05
    assert -0.30 <= b["SMB"] <= 0.0
    assert abs(b["HML"]) <= 0.20 and abs(b["RMW"]) <= 0.20 and abs(b["CMA"]) <= 0.20
    assert reg.fit.rsquared >= 0.97
    assert abs(reg.alpha_ann) <= 0.02
    assert reg.fit.nobs >= 3000
    if reg.alpha_tag == "reliable":
        warnings.warn(f"SPY alpha since 2010 tagged reliable: {reg.alpha_ann:+.4f}", stacklevel=1)

    # Full-history report: sanity, audit and identities (T115).
    rg = rep.regression
    full = {f.name: f.beta for f in rg.factors}
    assert full["Mkt-RF"] is not None and 0.93 <= full["Mkt-RF"] <= 1.05
    assert full["SMB"] is not None and full["SMB"] < 0
    assert rg.r2 is not None
    if rg.r2 < 0.97:  # T109's bound; below it the report must say why (M3.6)
        assert rep.quality_gate.fired is True
        assert rep.warnings[0].code == "residual_reversal"
        assert rep.five_day_regression.status == "ok"
        assert rep.five_day_regression.r2 is not None and rep.five_day_regression.r2 >= 0.97
    assert rep.data.n_obs >= 3000
    assert rep.data.audit_status != "errors"
    rc, rk = rep.return_contribution, rep.risk_contribution
    assert rc.identity_residual is not None and abs(rc.identity_residual) <= 1e-10
    assert rk.sums_to_one_residual is not None and abs(rk.sums_to_one_residual) <= 1e-10
    json.dumps(rep.model_dump(mode="json"), allow_nan=False)
