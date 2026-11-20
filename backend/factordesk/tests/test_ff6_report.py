"""FF6 reports and the alpha strip in the pipeline (E1, E9a).

The ticker cases reuse the golden fixture (``make_case(3001, n=720)``) with a synthetic momentum
column added to the factor frame. An FF5 report built on that frame must equal the golden file in
every node except the added ``alpha_strip`` section.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime

import numpy as np
import pandas as pd
import pytest

from factordesk.analytics.model_comparison import compare_models
from factordesk.analytics.models import MODEL_ORDER
from factordesk.analytics.sample import build_subject_sample
from factordesk.analytics.subject import subject_from_monthly_returns
from factordesk.data.prices import Security
from factordesk.pipeline import NOTE_FF6, assemble_report, assemble_subject_report
from factordesk.report.render_html import (
    _slot,  # pyright: ignore[reportPrivateUsage]
    render_report_html,
)
from factordesk.report.schema import FactorReport
from factordesk.report.sections.alpha_strip import CAPTION, MODEL_NOTES
from factordesk.section_hooks.context import SectionInputs, WorldBenchmarkInput
from factordesk.tests.test_subject import monthly_case
from factordesk.tests.test_ticker_golden import GOLDEN, json_differences
from factordesk.tests.test_world_beta import make_case

NOW = datetime(2026, 11, 18, 15, 0, tzinfo=UTC)
SECURITY = Security(name="Example Corp", currency="USD", exchange="NASDAQ")
FF5_ONLY = ("lead_lag", "shrunk_betas", "fragility", "residual", "kalman_betas")


def with_mom(
    factors: pd.DataFrame, seed: int, missing_tail: int = 0, sd: float = 0.007
) -> pd.DataFrame:
    """``factors`` plus a ``Mom`` column (synthetic); the last ``missing_tail`` values are NaN."""
    rng = np.random.default_rng(seed)
    mom = rng.normal(0.0003, sd, size=len(factors))
    if missing_tail:
        mom[-missing_tail:] = np.nan
    out = factors.copy()
    out["Mom"] = mom
    return out


def ticker_report(model: str = "ff5", missing_tail: int = 0) -> FactorReport:
    case = make_case(3001, n=720)
    return assemble_report(
        "STK",
        case.stock,
        with_mom(case.factors, 77, missing_tail),
        now=NOW,
        factors_downloaded_at=None,
        section_inputs=SectionInputs(world_benchmark=WorldBenchmarkInput(history=case.bench)),
        security=SECURITY,
        model=model,  # pyright: ignore[reportArgumentType]
    )


def monthly_report(model: str = "ff5", n: int = 72) -> FactorReport:
    returns, factors, _ = monthly_case(n, 11)
    subject = subject_from_monthly_returns(returns, label="Example Fund")
    return assemble_subject_report(
        subject,
        with_mom(factors, 78, sd=0.03),
        model,  # pyright: ignore[reportArgumentType]
        now=NOW,
        factors_downloaded_at=None,
    )


# ----------------------------------------------------------------------------- FF5 unchanged
def test_ff5_report_on_the_ff6_frame_equals_the_golden_file_plus_the_strip() -> None:
    payload = json.loads(ticker_report("ff5").model_dump_json())
    assert "model" not in payload  # FF5 is not written
    strip = payload.pop("alpha_strip")
    assert strip["status"] == "ok" and strip["model"] == "ff5"
    expected = json.loads(GOLDEN.read_text(encoding="utf-8"))
    differences = json_differences(payload, expected)
    assert not differences, "\n".join(differences[:20])


def test_ff5_report_without_momentum_has_no_strip() -> None:
    case = make_case(3001, n=720)
    report = assemble_report("STK", case.stock, case.factors, now=NOW, factors_downloaded_at=None)
    assert report.alpha_strip is None
    assert "alpha_strip" not in json.loads(report.model_dump_json())


# ----------------------------------------------------------------------------- FF6
def test_ff6_ticker_report_uses_six_factors_and_hides_ff5_only_sections() -> None:
    report = ticker_report("ff6")
    names = [f.name for f in report.regression.factors]
    assert names == ["Mkt-RF", "SMB", "HML", "RMW", "CMA", "Mom"]
    assert report.regression.bh_family_size == 6
    assert "across the 6 betas" in report.regression.caption
    assert report.model == "ff6"
    assert json.loads(report.model_dump_json())["model"] == "ff6"
    for field in FF5_ONLY:
        assert getattr(report, field) is None, field
    assert report.world_beta is not None and report.performance is not None
    assert list(report.return_contribution.factors) == names
    assert [d.name for d in report.risk_contribution.details] == names
    ok = [w for w in report.rolling if w.status == "ok"]
    assert ok and all(list(w.betas) == names for w in ok)
    assert [a.name for a in report.average_beta.factors] == names
    assert NOTE_FF6 in report.notes
    strip = report.alpha_strip
    assert strip is not None and strip.model == "ff6"
    assert strip.model_note == MODEL_NOTES["ff6"]
    # The FF6 row of the strip is the report's own regression on the same rows.
    ff6 = strip.rows[-1]
    assert ff6.model == "ff6" and strip.n_dropped == 0
    assert ff6.alpha_annual == pytest.approx(report.regression.alpha_annual, rel=1e-10)
    assert ff6.r2 == pytest.approx(report.regression.r2, rel=1e-10)


def test_report_notes_carry_the_french_stamp_notice() -> None:
    returns, factors, _ = monthly_case(72, 11)
    subject = subject_from_monthly_returns(returns, label="Example Fund")
    frame = with_mom(factors, 78, sd=0.03)
    frame.attrs = {
        "ff5": {"crsp_stamp": "202609"},
        "mom": {"crsp_stamp": "202608"},
        "last_date": "2026-09-30",
        "mom_last_date": "2026-08-31",
    }
    report = assemble_subject_report(
        subject,
        frame,
        "ff5",
        now=NOW,
        factors_downloaded_at=None,  # pyright: ignore[reportArgumentType]
    )
    assert any("2026-08-31" in note for note in report.notes)
    assert any("202608" in note for note in report.notes)
    assert not any("CRSP release" in note for note in monthly_report().notes)


def test_ff6_differs_from_ff5_only_where_the_model_enters() -> None:
    ff5, ff6 = ticker_report("ff5"), ticker_report("ff6")
    assert ff5.data == ff6.data
    assert ff5.regression.alpha_annual != ff6.regression.alpha_annual
    assert ff5.alpha_strip is not None and ff6.alpha_strip is not None
    assert ff5.alpha_strip.rows == ff6.alpha_strip.rows


def test_ff6_needs_the_momentum_column() -> None:
    case = make_case(3001, n=720)
    with pytest.raises(ValueError, match="momentum"):
        assemble_report(
            "STK", case.stock, case.factors, now=NOW, factors_downloaded_at=None, model="ff6"
        )


def test_unknown_model_is_refused() -> None:
    with pytest.raises(ValueError, match="unknown factor model"):
        ticker_report("ff4")


def test_rows_without_momentum_end_the_ff6_sample_and_are_counted_by_the_ff5_strip() -> None:
    ff5 = ticker_report("ff5", missing_tail=10)
    ff6 = ticker_report("ff6", missing_tail=10)
    assert ff6.data.n_obs == ff5.data.n_obs - 10
    assert ff6.data.factors_last_date < ff5.data.factors_last_date
    assert ff6.data.uncovered.n == ff5.data.uncovered.n + 10
    assert ff5.alpha_strip is not None and ff5.alpha_strip.n_dropped == 10
    assert ff5.alpha_strip.n_obs == ff5.data.n_obs - 10
    assert ff6.alpha_strip is not None and ff6.alpha_strip.n_dropped == 0


# ----------------------------------------------------------------------------- alpha strip
def test_strip_rows_are_the_four_models_in_fixed_order_with_the_e9a_caption() -> None:
    strip = ticker_report("ff5").alpha_strip
    assert strip is not None
    assert [r.model for r in strip.rows] == list(MODEL_ORDER)
    assert [r.label for r in strip.rows] == ["CAPM", "FF3", "FF5", "FF6"]
    assert [len(r.factors) for r in strip.rows] == [1, 3, 5, 6]
    assert strip.caption == CAPTION
    assert strip.caption == (
        "A higher R² does not make a model more correct. Alpha depends on the model."
    )
    assert strip.model_note == MODEL_NOTES["ff5"]
    assert strip.t_reference == "normal"


def test_model_notes_use_associational_wording() -> None:
    for note in MODEL_NOTES.values():
        assert "co-moved with" in note
        assert "assumes" in note and "leaves out" in note
        for banned in ("driven by", "earned from", "caused", "explains"):
            assert banned not in note


def test_monthly_strip_uses_student_t_like_the_main_regression() -> None:
    report = monthly_report("ff5")
    strip = report.alpha_strip
    assert strip is not None and strip.t_reference == "student_t"
    ff5 = next(r for r in strip.rows if r.model == "ff5")
    assert ff5.alpha_p == pytest.approx(report.regression.alpha_p, rel=1e-9)
    assert ff5.alpha_annual == pytest.approx(report.regression.alpha_annual, rel=1e-10)


def test_monthly_ff6_report_uses_n_minus_7() -> None:
    report = monthly_report("ff6")
    assert report.regression.factors[-1].name == "Mom"
    assert "n / (n - 7)" in report.regression.caption
    assert any("n - 7 degrees of freedom" in note for note in report.notes)
    assert report.alpha_strip is not None and report.alpha_strip.model == "ff6"


def test_strip_matches_compare_models_on_the_report_sample() -> None:
    returns, factors, _ = monthly_case(72, 11)
    subject = subject_from_monthly_returns(returns, label="Example Fund")
    sample = build_subject_sample(subject, with_mom(factors, 78, sd=0.03))
    direct = compare_models(sample, small_sample=True)
    strip = monthly_report("ff5").alpha_strip
    assert strip is not None
    for row, ref in zip(strip.rows, direct.models, strict=True):
        assert row.alpha_t == pytest.approx(ref.alpha_t, rel=1e-12)
        assert row.adj_r2 == pytest.approx(ref.rsquared_adj, rel=1e-12)


# ----------------------------------------------------------------------------- static export
def test_ff6_html_export_colours_mom_with_slot_6_and_names_the_model() -> None:
    page = render_report_html(ticker_report("ff6"))
    assert "Fama&#8211;French six-factor profile (five factors plus momentum)" in page
    assert "five-factor profile" not in page
    assert re.search(r'cat c6"[^<]*(?:<[^>]*>){0,6}[^<]*Mom', page)
    assert "rect.c6 { fill: var(--f6); }" in page and "--f6: #7048b8" in page
    ff5 = render_report_html(ticker_report("ff5"))
    assert "Fama&#8211;French five-factor profile" in ff5 and "cat c6" not in ff5


def test_static_slots_put_mom_sixth() -> None:
    assert _slot("Mom", ["Mkt-RF", "Mom"]) == 6
    assert _slot("CMA", []) == 5
    assert _slot("Mkt-RF", []) == 1
