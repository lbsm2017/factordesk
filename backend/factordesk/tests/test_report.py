"""Schema and HTML renderer tests. All data here is synthetic and labelled MOCK."""

from __future__ import annotations

import math
import random
import re
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

from factordesk.report import (
    FACTOR_NAMES,
    FactorReport,
    dump_report,
    load_report,
    render_report_html,
    report_json_schema,
    write_report,
)
from factordesk.report.schema import (
    LABEL_TEXT,
    AuditFinding,
    AverageBeta,
    AverageBetaPanel,
    DataInfo,
    DiagnosticTest,
    ExcludedRow,
    FactorStat,
    FactorVintage,
    MultiDayRegression,
    PriceSeries,
    QualityGate,
    Regression,
    ReportWarning,
    ResidualDiagnostics,
    ReturnContribution,
    RiskContribution,
    RiskFactorDetail,
    RollingWindow,
    SampleInfo,
    UncoveredTail,
)

FIXTURE = Path(__file__).parent / "fixtures" / "mock_report.json"


def _body(page: str) -> str:
    """The page without its stylesheet (which embeds base64 fonts)."""
    return re.sub(r"<style>.*?</style>", "", page, flags=re.S)


SOURCE_URL = "https://example.invalid/factors.zip"
Z = 1.959963984540054


def _bdays(end: date, n: int) -> list[date]:
    """The last ``n`` weekdays up to and including ``end`` (or the weekday before it)."""
    out: list[date] = []
    d = end
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d)
        d -= timedelta(days=1)
    return out[::-1]


def _p_from_z(z: float) -> float:
    """Two-sided normal p-value, rounded to 12 significant digits.

    ``math.erfc`` comes from the platform C library and differs in the last bit between glibc
    and the Windows runtime, so the unrounded value would make the committed fixture
    platform-dependent. Twelve digits are far above any displayed precision.
    """
    return float(f"{math.erfc(abs(z) / math.sqrt(2)):.12g}")


def _bh(ps: list[float]) -> list[float]:
    """Benjamini-Hochberg adjusted p-values."""
    m = len(ps)
    order = sorted(range(m), key=lambda i: ps[i])
    adj = [0.0] * m
    prev = 1.0
    for rank in range(m, 0, -1):
        i = order[rank - 1]
        prev = min(prev, ps[i] * m / rank)
        adj[i] = prev
    return adj


def build_mock_report() -> FactorReport:
    """Deterministic SPY-like MOCK report with ~560 trading days of synthetic data."""
    rng = random.Random(20261118)
    n = 560
    factor_end = date(2026, 9, 30)
    price_end = date(2026, 11, 13)
    f_days = _bdays(factor_end, n)
    tail_days = [d for d in _bdays(price_end, n + 30) if d > factor_end]
    all_days = f_days + tail_days

    px: list[float | None] = []
    p = 480.0
    for _ in all_days:
        p *= 1 + rng.gauss(0.0006, 0.009)
        px.append(round(p, 2))

    vintage = FactorVintage(last_date=factor_end, downloaded_at=datetime(2026, 11, 1, tzinfo=UTC))
    excluded = [ExcludedRow(date=f_days[100], reason="multi_day_return")]
    used = [d for d in f_days if d != f_days[100]]

    def info(window: int | None = None) -> SampleInfo:
        return SampleInfo(
            n=len(used),
            start=used[0],
            end=used[-1],
            requested_start=date(2024, 11, 1),
            requested_end=price_end,
            window=window,
            n_excluded=len(excluded),
            excluded=excluded,
            factor_vintage=vintage,
        )

    betas = {"Mkt-RF": 0.998, "SMB": -0.141, "HML": 0.012, "RMW": 0.027, "CMA": -0.009}
    ses = {"Mkt-RF": 0.0021, "SMB": 0.0102, "HML": 0.0098, "RMW": 0.0121, "CMA": 0.0143}
    zs = {k: betas[k] / ses[k] for k in betas}
    ps = [_p_from_z(zs[k]) for k in FACTOR_NAMES]
    padj = _bh(ps)
    stats = [
        FactorStat(
            name=k,
            beta=betas[k],
            se=ses[k],
            z=zs[k],
            p=ps[i],
            p_adj_bh=padj[i],
            ci_low=betas[k] - Z * ses[k],
            ci_high=betas[k] + Z * ses[k],
            tag="reliable" if padj[i] <= 0.05 else "noise",
            interpretation=(f"MOCK reading of {k}." if padj[i] <= 0.05 else None),
        )
        for i, k in enumerate(FACTOR_NAMES)
    ]

    rolling: list[RollingWindow] = []
    for win, noise in ((126, 0.035), (252, 0.018)):
        series: dict[str, list[float | None]] = {}
        se_series: dict[str, list[float | None]] = {}
        for k in FACTOR_NAMES:
            vals: list[float | None] = []
            sev: list[float | None] = []
            for i in range(len(used)):
                if i < win - 1:
                    vals.append(None)
                    sev.append(None)
                else:
                    wave = math.sin(i / 60 + len(k)) * noise * (4 if k != "Mkt-RF" else 0.4)
                    vals.append(round(betas[k] + wave + rng.gauss(0, noise / 4), 4))
                    sev.append(round(ses[k] * math.sqrt(len(used) / win), 5))
            series[k] = vals
            se_series[k] = sev
        rolling.append(
            RollingWindow(
                status="ok",
                reason=None,
                sample=info(win),
                labels=["L-DESC", "L-BAND", "L-OVERLAP"],
                caption=f"Each point uses the previous {win} trading days, ending on that date.",
                window=win,
                n_stamps=len(used) - win + 1,
                hac_lags=4,
                ci_z=Z,
                dates=used,
                window_start=[None if i < win - 1 else used[i - win + 1] for i in range(len(used))],
                betas=series,
                se=se_series,
            )
        )

    avg: list[AverageBeta] = []
    for k in FACTOR_NAMES:
        tail = sorted(v for v in rolling[1].betas[k] if v is not None)
        mean = sum(tail) / len(tail)
        sd = math.sqrt(sum((v - mean) ** 2 for v in tail) / (len(tail) - 1))
        avg.append(
            AverageBeta(
                name=k,
                full_sample_beta=betas[k],
                mean=mean,
                sd=sd,
                p10=tail[len(tail) // 10],
                p90=tail[(9 * len(tail)) // 10],
                min=tail[0],
                max=tail[-1],
                share_positive=sum(1 for v in tail if v > 0) / len(tail),
            )
        )

    mean_f = {"Mkt-RF": 0.00046, "SMB": -0.00005, "HML": 0.00002, "RMW": 0.00012, "CMA": 0.00001}
    contrib: dict[str, float | None] = {k: betas[k] * mean_f[k] * 252 for k in FACTOR_NAMES}
    total = 0.1264
    alpha = total - sum(v for v in contrib.values() if v is not None)
    rc = ReturnContribution(
        status="ok",
        reason=None,
        sample=info(),
        labels=["L-DESC", "L-ARITH"],
        caption="Annualised (x252) means over the sample, using full-sample betas.",
        factors=contrib,
        alpha=alpha,
        residual=0.0,
        total_annualised_mean_excess_return=total,
        identity_residual=total - alpha - sum(v for v in contrib.values() if v is not None),
        memo=[
            f"Not covered by factor data: {len(tail_days)} trading days after {factor_end}; "
            "stock return +1.23% (compounded, raw, not excess). Not attributed.",
            "Excluded rows: 1 (return spans several factor days: 1).",
        ],
    )
    shares = {"Mkt-RF": 0.9941, "SMB": 0.0009, "HML": -0.0002, "RMW": 0.0004, "CMA": 0.0001}
    idio = 1 - sum(shares.values())
    rk = RiskContribution(
        status="ok",
        reason=None,
        sample=info(),
        labels=["L-DESC"],
        caption=f"Shares of variance over {used[0]} to {used[-1]}; they add to 100%.",
        factors=dict(shares),
        idiosyncratic=idio,
        sums_to_one_residual=1 - (sum(shares.values()) + idio),
        total_vol_annual=0.17,
        order=[*sorted(shares, key=lambda k: -shares[k]), "Idiosyncratic"],
        details=[
            RiskFactorDetail(name=k, share=shares[k], beta=betas[k], sigma_annual=0.1, rho_sys=0.5)
            for k in FACTOR_NAMES
        ],
        sentences=["MOCK: SMB ranks #2 by risk but only #4 by beta size."],
    )
    reg = Regression(
        status="ok",
        reason=None,
        sample=info(),
        labels=["L-DESC"],
        caption="In-sample: uses the whole window. MOCK.",
        alpha_annual=alpha,
        alpha_se_annual=0.012,
        alpha_z=0.84,
        alpha_p=_p_from_z(0.84),
        alpha_ci_low_annual=alpha - Z * 0.012,
        alpha_ci_high_annual=alpha + Z * 0.012,
        alpha_tag="noise",
        alpha_sentence=None,
        r2=0.9987,
        adj_r2=0.9987,
        sigma_e_annual=0.006,
        hac_lags=6,
        bh_family_size=5,
        factors=stats,
        vif={"Mkt-RF": 1.12, "SMB": 1.34, "HML": 2.05, "RMW": 1.88, "CMA": 2.41},
        condition_number=2.7,
        high_corr_pairs=[],
    )
    diag = ResidualDiagnostics(
        status="ok",
        reason=None,
        sample=info(),
        labels=["L-DESC"],
        caption="Residual diagnostics of the full-sample regression. MOCK.",
        lag1_autocorrelation=-0.31,
        lag1_se=0.05,
        lag1_z=-6.2,
        lag1_p=_p_from_z(-6.2),
        lag1_reading="MOCK: lag-1 autocorrelation of the residuals is -0.31.",
        tests=[
            DiagnosticTest(
                code="ljung_box",
                name="Ljung-Box",
                statistic=88.0,
                df=10,
                p=1e-14,
                reading="MOCK: Ljung-Box rejects.",
            ),
            DiagnosticTest(
                code="robust_breusch_godfrey",
                name="Robust Breusch-Godfrey",
                statistic=41.0,
                df=10,
                p=1.1e-5,
                reading="MOCK: robust test rejects.",
            ),
            DiagnosticTest(
                code="arch_lm",
                name="ARCH-LM",
                statistic=120.0,
                df=5,
                p=4e-24,
                reading="MOCK: volatility clustering present.",
            ),
            DiagnosticTest(
                code="jarque_bera",
                name="Jarque-Bera",
                statistic=900.0,
                df=2,
                p=1e-190,
                reading="MOCK: fat tails.",
            ),
            DiagnosticTest(
                code="durbin_watson",
                name="Durbin-Watson",
                statistic=2.62,
                df=None,
                p=None,
                reading="MOCK: above 2.",
            ),
        ],
        note="MOCK: HAC standard errors are used whatever these tests show.",
    )
    gate = QualityGate(
        status="ok",
        reason=None,
        sample=info(),
        labels=["L-DESC"],
        caption="Residual quality gate (M3.6). MOCK.",
        rho_threshold=-0.2,
        z_threshold=-4.0,
        lag1_autocorrelation=-0.31,
        lag1_z=-6.2,
        fired=True,
        noise_share=0.62,
        message=(
            "MOCK: Daily price changes partly reverse the next day: the lag-1 autocorrelation "
            "of the regression residuals is -0.31 (robust z -6.2)."
        ),
    )
    five_stats = [
        s.model_copy(update={"interpretation": None, "se": (s.se or 0.0) * 2}) for s in stats
    ]
    five = MultiDayRegression(
        status="ok",
        reason=None,
        sample=info(),
        labels=["L-DESC"],
        caption="Sums of daily returns over non-overlapping blocks of 5 trading days. MOCK.",
        horizon_days=5,
        n_blocks=len(used) // 5,
        n_rows_unused=len(used) % 5,
        blocks_start=used[0],
        blocks_end=used[5 * (len(used) // 5) - 1],
        alpha_annual=alpha * 0.9,
        alpha_se_annual=0.02,
        alpha_z=alpha * 0.9 / 0.02,
        alpha_p=_p_from_z(alpha * 0.9 / 0.02),
        alpha_ci_low_annual=alpha * 0.9 - Z * 0.02,
        alpha_ci_high_annual=alpha * 0.9 + Z * 0.02,
        alpha_tag="noise",
        r2=0.9991,
        adj_r2=0.9990,
        sigma_e_annual=0.004,
        hac_lags=4,
        bh_family_size=5,
        factors=five_stats,
    )
    data = DataInfo(
        requested_start=date(2024, 11, 1),
        requested_end=price_end,
        actual_start=used[0],
        actual_end=used[-1],
        n_obs=len(used),
        factors_last_date=factor_end,
        factors_downloaded_at=datetime(2026, 11, 1, tzinfo=UTC),
        factors_days_behind=49,
        factors_source_url=SOURCE_URL,
        price_source="MOCK price source (Adj Close)",
        dropped_price_dates_after_factors=len(tail_days),
        dropped_price_dates_before_factors=0,
        n_excluded=1,
        excluded_by_reason={"multi_day_return": 1},
        uncovered=UncoveredTail(
            n=len(tail_days),
            first=tail_days[0],
            last=tail_days[-1],
            factor_last_date=factor_end,
            compounded_return=0.0123,
        ),
        audit_status="warnings",
        audit_findings=[
            AuditFinding(code="mock_info", severity="info", message="MOCK: no splits in window."),
            AuditFinding(
                code="mock_gap",
                severity="warning",
                message="MOCK: one 4-day gap in the series.",
                dates=[f_days[200]],
            ),
        ],
    )
    return FactorReport(
        ticker="SPY",
        generated_at=datetime(2026, 11, 18, 9, 30, tzinfo=UTC),
        data=data,
        regression=reg,
        rolling=rolling,
        average_beta=AverageBetaPanel(
            status="ok",
            reason=None,
            sample=info(252),
            labels=["L-DESC", "L-OVERLAP"],
            caption="Average of overlapping 252-day estimates. MOCK.",
            window=252,
            n_stamps=len(used) - 251,
            factors=avg,
        ),
        return_contribution=rc,
        risk_contribution=rk,
        residual_diagnostics=diag,
        quality_gate=gate,
        five_day_regression=five,
        price_series=PriceSeries(dates=all_days, adj_close=px, factor_coverage_end=factor_end),
        warnings=[
            ReportWarning(code="residual_reversal", message=gate.message or ""),
            ReportWarning(code="short_history", message="MOCK: short history."),
        ],
        notes=[
            "MOCK DATA: synthetic numbers for layout testing, not a real SPY analysis.",
            "In-sample and descriptive, not predictive.",
            "US Fama-French factors; non-US tickers load on them imperfectly.",
        ],
        label_text=dict(LABEL_TEXT),
    )


# ---------------------------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------------------------
def test_fixture_matches_builder() -> None:
    assert load_report(FIXTURE) == build_mock_report()


def test_schema_round_trip(tmp_path: Path) -> None:
    rep = build_mock_report()
    out = tmp_path / "r.json"
    dump_report(rep, out)
    assert load_report(out) == rep
    assert FactorReport.model_validate_json(rep.model_dump_json()) == rep


def test_schema_is_frozen_strict_and_versioned() -> None:
    rep = build_mock_report()
    assert rep.schema_version == "3"
    with pytest.raises(ValidationError):
        rep.ticker = "QQQ"  # type: ignore[misc]
    with pytest.raises(ValidationError):
        FactorReport.model_validate_json(rep.model_dump_json().replace('"ticker"', '"tickr"'))
    assert "properties" in report_json_schema()


def test_schema_rejects_misaligned_and_naive() -> None:
    rep0 = build_mock_report()
    with pytest.raises(ValidationError):
        RollingWindow.model_validate(
            {**rep0.rolling[0].model_dump(), "betas": {"SMB": [None, 0.1]}}
        )
    with pytest.raises(ValidationError):
        PriceSeries(dates=[date(2026, 1, 1)], adj_close=[], factor_coverage_end=date(2026, 1, 1))
    rep = build_mock_report()
    with pytest.raises(ValidationError):
        FactorReport.model_validate_json(
            rep.model_dump_json().replace("2026-11-18T09:30:00Z", "2026-11-18T09:30:00")
        )


# ---------------------------------------------------------------------------------------------
# Renderer
# ---------------------------------------------------------------------------------------------
def test_render_is_deterministic_and_self_contained() -> None:
    rep = build_mock_report()
    a, b = render_report_html(rep), render_report_html(rep)
    assert a == b
    assert "<script" not in a
    assert "<link" not in a
    assert "@import" not in a
    # the only url() values are the embedded fonts (data URIs) and fragment references
    assert "url(" not in re.sub(r"url\((#|data:font/woff2;base64,)", "", a)
    # the only URL in the document is the user-supplied factor source, shown as text
    assert a.count(SOURCE_URL) == 1
    assert not re.search(r"https?://", a.replace(SOURCE_URL, ""))
    assert 'role="img"' in a and "<title" in a and "aria-label" in a
    assert 'id="beta-SMB"' in a  # the bar tables carry the numbers


def test_render_contains_key_content() -> None:
    page = render_report_html(build_mock_report())
    for needle in (
        "SPY",
        "MOCK DATA",
        "Factor exposures",
        "Where the return came from",
        "Where the risk comes from",
        "Exposure over time",
        "Not in the sum",
    ):
        assert needle in page
    assert LABEL_TEXT["L-DESC"] in page
    assert LABEL_TEXT["L-ARITH"] in page and LABEL_TEXT["L-BAND"] in page
    assert "Factor data ends 30 Sep 2026 (49 days ago)" in page
    assert "Generated" not in page.split("<footer")[0]  # the generated time is in the colophon


def test_render_escapes_injected_html() -> None:
    rep = build_mock_report()
    evil = "<script>alert(1)</script>"
    rep2 = rep.model_copy(
        update={
            "notes": [evil],
            "ticker": '"><img src=x onerror=1>',
            "data": rep.data.model_copy(
                update={
                    "audit_findings": [
                        AuditFinding(code="<b>", severity="error", message="a & b <i>x</i>")
                    ]
                }
            ),
        }
    )
    page = render_report_html(rep2)
    assert evil not in page
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in page
    assert "<img" not in page
    assert "a &amp; b &lt;i&gt;" in page


def test_render_handles_empty_rolling_and_series() -> None:
    rep = build_mock_report()
    empty = rep.model_copy(
        update={
            "rolling": [],
            "price_series": PriceSeries(
                dates=[], adj_close=[], factor_coverage_end=date(2026, 9, 30)
            ),
            "average_beta": rep.average_beta.model_copy(
                update={"factors": [], "status": "insufficient_data", "reason": "MOCK"}
            ),
        }
    )
    page = render_report_html(empty)
    assert page.count("Insufficient data") >= 2
    only_warmup = rep.model_copy(
        update={
            "rolling": [
                RollingWindow.model_validate(
                    {
                        **rep.rolling[1].model_dump(),
                        "dates": [date(2026, 1, 2), date(2026, 1, 5)],
                        "window_start": [None, None],
                        "betas": {k: [None, None] for k in FACTOR_NAMES},
                        "se": {k: [None, None] for k in FACTOR_NAMES},
                    }
                )
            ]
        }
    )
    assert "warm-up" in render_report_html(only_warmup)


def test_render_handles_nan_none_and_zero_range() -> None:
    rep = build_mock_report()
    nan = float("nan")
    bad_stats = [
        s.model_copy(update={"beta": nan, "se": None, "z": nan, "ci_low": nan, "ci_high": None})
        for s in rep.regression.factors
    ]
    flat = PriceSeries.model_construct(
        dates=[date(2026, 1, 2), date(2026, 1, 5), date(2026, 1, 6)],
        adj_close=[100.0, nan, 100.0],
        factor_coverage_end=date(2026, 1, 5),
    )
    bad = rep.model_copy(
        update={
            "regression": rep.regression.model_copy(
                update={"factors": bad_stats, "r2": nan, "alpha_annual": None, "vif": {}}
            ),
            "return_contribution": rep.return_contribution.model_copy(
                update={
                    "factors": {},
                    "alpha": nan,
                    "total_annualised_mean_excess_return": None,
                    "identity_residual": None,
                }
            ),
            "risk_contribution": rep.risk_contribution.model_copy(
                update={
                    "factors": {},
                    "idiosyncratic": None,
                    "sums_to_one_residual": nan,
                    "details": [],
                    "order": [],
                }
            ),
            "price_series": flat,
        }
    )
    page = _body(render_report_html(bad))
    assert "nan" not in page.lower().replace("financ", "")
    assert "inf" not in re.sub(r"info|infl|inferred", "", page.lower())
    assert "n/a" in page
    assert "Insufficient data" in page


def test_render_all_prices_beyond_factor_coverage_and_single_point() -> None:
    rep = build_mock_report()
    ps = rep.price_series.model_copy(update={"factor_coverage_end": date(2000, 1, 1)})
    page = render_report_html(rep.model_copy(update={"price_series": ps}))
    assert "Not analysed: factor data ends 1 Jan 2000" in page
    assert page.count('class="tailzone"') == 1  # the whole window is shaded
    one = PriceSeries(
        dates=[date(2026, 1, 2)], adj_close=[1.0], factor_coverage_end=date(2026, 1, 2)
    )
    assert "Insufficient data" in render_report_html(rep.model_copy(update={"price_series": one}))


def test_write_report(tmp_path: Path) -> None:
    out = write_report(build_mock_report(), tmp_path / "sub" / "r.html")
    raw = out.read_bytes()
    assert raw.startswith(b"<!doctype html>")
    crlf = bytes([13, 10])
    assert crlf not in raw  # LF line endings on every platform
    dump_report(build_mock_report(), tmp_path / "r.json")
    assert crlf not in (tmp_path / "r.json").read_bytes()


def test_schema_rejects_nan_and_inconsistent_status() -> None:
    nan = float("nan")
    with pytest.raises(ValidationError):
        PriceSeries(dates=[date(2026, 1, 2)], adj_close=[nan], factor_coverage_end=date(2026, 1, 2))
    rep = build_mock_report()
    with pytest.raises(ValidationError):
        RiskContribution.model_validate(
            {**rep.risk_contribution.model_dump(), "idiosyncratic": float("inf")}
        )
    with pytest.raises(ValidationError):  # not ok but numbers present
        Regression.model_validate(
            {**rep.regression.model_dump(), "status": "insufficient_data", "reason": "x"}
        )
    with pytest.raises(ValidationError):  # ok must not carry a reason
        Regression.model_validate({**rep.regression.model_dump(), "reason": "x"})


def test_dump_is_compact_and_round_trips(tmp_path: Path) -> None:
    rep = build_mock_report()
    out = tmp_path / "r.json"
    dump_report(rep, out)
    text = out.read_text(encoding="utf-8")
    assert text.endswith("\n") and text.count("\n") == 1  # one line, no indentation
    assert load_report(out) == rep


def test_render_shows_gate_callout_and_diagnostics() -> None:
    page = render_report_html(build_mock_report())
    notice = page.split('id="notice"')[1].split("</aside>")[0]
    assert "<details" in notice and "Details" in notice
    assert "MOCK: Daily price changes partly reverse the next day" in notice
    assert "5-day estimate (111 blocks)" in notice
    assert "Residual diagnostics" in page and "Robust Breusch-Godfrey" in page
    assert "5-day estimate" in page and "blocks of 5 trading days" in page
    assert "MOCK: HAC standard errors are used whatever these tests show." in page


def test_render_without_gate_has_no_callout() -> None:
    rep = build_mock_report()
    quiet_gate = rep.quality_gate.model_copy(update={"fired": False, "message": None})
    quiet_five = MultiDayRegression(
        status="not_applicable",
        reason="the residual quality gate did not fire",
        sample=rep.five_day_regression.sample,
        labels=["L-DESC"],
        caption="MOCK",
        horizon_days=5,
        n_blocks=0,
        n_rows_unused=0,
        blocks_start=None,
        blocks_end=None,
        alpha_annual=None,
        alpha_se_annual=None,
        alpha_z=None,
        alpha_p=None,
        alpha_ci_low_annual=None,
        alpha_ci_high_annual=None,
        alpha_tag=None,
        r2=None,
        adj_r2=None,
        sigma_e_annual=None,
        hac_lags=0,
        bh_family_size=0,
        factors=[],
    )
    quiet = rep.model_copy(
        update={
            "quality_gate": quiet_gate,
            "five_day_regression": quiet_five,
            "warnings": rep.warnings[1:],
        }
    )
    page = render_report_html(quiet)
    assert "5-day estimate" not in page.split("Regression detail")[0]
    assert "MOCK: Daily price changes partly reverse the next day" not in page
    assert "Residual diagnostics" in page
    assert "5-day estimate" not in page


def test_render_failed_rolling_window_shows_reason() -> None:
    rep = build_mock_report()
    failed = RollingWindow(
        status="failed",
        reason="MOCK: 5 of 435 windows have a singular factor matrix",
        sample=rep.rolling[0].sample,
        labels=["L-DESC", "L-BAND", "L-OVERLAP"],
        caption="MOCK",
        window=126,
        n_stamps=0,
        hac_lags=0,
        ci_z=None,
        dates=[],
        window_start=[],
        betas={},
        se={},
    )
    page = render_report_html(rep.model_copy(update={"rolling": [failed, rep.rolling[1]]}))
    assert "MOCK: 5 of 435 windows have a singular factor matrix" in page


def test_signs_use_glyphs() -> None:
    body = _body(render_report_html(build_mock_report()))
    assert re.search(r'class="num strong">[+−][0-9]', body)  # + or a true minus
    assert 'class="num strong">-' not in body  # no ASCII hyphen as a minus
    assert not re.search(r"[+−]0\.0+(?![0-9])", body)  # zero prints unsigned
    assert 'class="num pos"' not in body and 'class="num neg"' not in body  # text has no colour


# ---------------------------------------------------------------------------------------------
# Report design, revision 2 (docs/design/report-design.md)
# ---------------------------------------------------------------------------------------------
def _beta_row(page: str, name: str) -> str:
    m = re.search(rf'<tr[^>]*id="beta-{name}".*?</tr>', page, flags=re.S)
    assert m is not None
    return m.group(0)


def test_render_width_cap_fonts_and_no_monospace() -> None:
    page = render_report_html(build_mock_report())
    assert "max-width: 1216px" in page
    assert "1680" not in page
    assert "monospace" not in page.lower() and "--mono" not in page
    assert page.count("font/woff2;base64,") == 4  # Instrument Sans plus three STIX subsets
    assert "font-variant-numeric: tabular-nums" in page
    assert "details.how::details-content" in page  # print unfolds the method text


def test_render_five_kpi_cells() -> None:
    page = render_report_html(build_mock_report())
    kpis = page.split('aria-label="Headline statistics"')[1].split("</section>")[0]
    assert len(re.findall(r'<div class="kpi[ "]', kpis)) == 5
    for label in ("Alpha, a year", "Residual volatility", "Observations", "Analysed range"):
        assert label in kpis
    assert "Data audit" not in kpis and "Adjusted R" not in kpis


def test_render_header_chips_and_notice_details() -> None:
    page = render_report_html(build_mock_report())
    assert page.count('class="chip') == 2  # factor data end, warnings
    assert 'href="#notice"' in page and "2 warnings" in page
    notice = page.split('id="notice"')[1].split("</aside>")[0]
    assert "Prices look out of step with the factor data" in notice  # plain, by warning code
    assert '<details class="how"><summary>Details</summary>' in notice
    assert "MOCK: short history." in notice  # the raw message sits behind Details
    rep = build_mock_report()
    odd = rep.model_copy(update={"warnings": [ReportWarning(code="new_code", message="MOCK raw.")]})
    summary = render_report_html(odd).split('class="notice-sum"')[1].split("</p>")[0]
    assert "MOCK raw." in summary  # unknown codes fall back to the message
    quiet = rep.model_copy(
        update={
            "warnings": [],
            "quality_gate": rep.quality_gate.model_copy(update={"fired": False}),
        }
    )
    assert 'id="notice"' not in render_report_html(quiet)


def test_render_rolling_five_rows_three_number_columns() -> None:
    page = render_report_html(build_mock_report())
    assert "sm-grid" not in page and "Average 252-day beta" not in page
    for k in (126, 252):
        block = page.split(f'<div class="win w-{k}">')[1].split("</table>")[0]
        assert block.count('class="plot mini"') == 5
        assert block.count('<th role="columnheader" scope="col" class="num">') == 3
        assert block.count('<td role="cell" class="num') == 15
        for head in ("Latest", "Average", "Middle 80%"):
            assert head in block
    tip = re.search(r'class="num range" title="([^"]+)"', page)
    assert tip is not None and "lowest" in tip.group(1) and "above zero" in tip.group(1)
    assert 'id="win-126"' in page and 'id="win-252" value="252" checked' in page


def test_render_interval_caps_are_short_and_omitted_when_narrow() -> None:
    rep = build_mock_report()
    row = _beta_row(render_report_html(rep), "SMB")
    caps = re.findall(r'y1="46\.5%" y2="53\.5%"', row)
    assert len(caps) == 2
    assert (53.5 - 46.5) / 100 * 44 <= 3.5  # 3 px on a 44 px row
    tight = [
        s.model_copy(update={"ci_low": (s.beta or 0) - 0.0005, "ci_high": (s.beta or 0) + 0.0005})
        if s.name == "SMB"
        else s
        for s in rep.regression.factors
    ]
    page = render_report_html(
        rep.model_copy(update={"regression": rep.regression.model_copy(update={"factors": tight})})
    )
    assert 'y1="46.5%"' not in _beta_row(page, "SMB")
    assert 'y1="46.5%"' in _beta_row(page, "HML")


def test_render_average_beta_diamond_sits_on_the_bar_row() -> None:
    page = render_report_html(build_mock_report())
    for name in FACTOR_NAMES:
        row = _beta_row(page, name)
        m = re.search(r'<svg class="avgm" x="[^"]+%" y="50%"', row)
        assert m is not None  # centred on the row, not below the bar
        assert row.index('<rect class="') < m.start() < row.index("</svg></td>")
    assert "M0 -3.6 3.6 0 0 3.6-3.6 0z" in page  # a 7 px diamond
    assert "Average 252d beta" in page
    assert page.count("noise means") == 1  # reliable and noise are defined once


def test_render_price_shades_both_non_analysed_ends() -> None:
    rep = build_mock_report()
    ps = rep.price_series
    early = _bdays(ps.dates[0] - timedelta(days=1), 30)
    longer = PriceSeries(
        dates=[*early, *ps.dates],
        adj_close=[*[400.0] * 30, *ps.adj_close],
        factor_coverage_end=ps.factor_coverage_end,
    )
    both = render_report_html(rep.model_copy(update={"price_series": longer}))
    assert both.count('class="tailzone"') == 2 and both.count('class="cutline"') == 2
    assert "Not analysed: before 8 Aug 2024" in both
    assert "Not analysed: factor data ends 30 Sep 2026" in both
    assert 'class="tailzone" x="0"' in both  # the left band starts at the plot edge
    only_right = render_report_html(rep)
    assert only_right.count('class="tailzone"') == 1 and "Not analysed: before" not in only_right
    assert "How has the price moved over the window? Shaded days are not in the analysis." in both
