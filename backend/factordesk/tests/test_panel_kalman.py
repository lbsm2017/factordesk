"""Static HTML panel of the ``kalman_betas`` section (spec ``kalman-betas.md``, design rev 2)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, cast

import pytest

from factordesk.report import load_report, render_report_html
from factordesk.report.panels.kalman import render_kalman_panel
from factordesk.report.schema import FACTOR_NAMES, FactorReport
from factordesk.tests.fixtures.sections import report_with_section, section_payload

MOCK = Path(__file__).parent / "fixtures" / "mock_report.json"
MINUS = "−"


@pytest.fixture(scope="module")
def base() -> FactorReport:
    return load_report(MOCK)


@pytest.fixture(scope="module")
def report(base: FactorReport) -> FactorReport:
    return report_with_section(base, "kalman_betas")


@pytest.fixture(scope="module")
def panel(report: FactorReport) -> str:
    html = render_kalman_panel(report)
    assert html is not None
    return html


def _with(base: FactorReport, **changes: Any) -> FactorReport:
    payload: dict[str, Any] = json.loads(json.dumps(section_payload("kalman_betas")))
    payload.update(changes)
    doc = json.loads(base.model_dump_json())
    doc["kalman_betas"] = payload
    return FactorReport.model_validate_json(json.dumps(doc))


def _not_ok(base: FactorReport, status: str, reason: str) -> FactorReport:
    empty: dict[str, Any] = {
        "status": status,
        "reason": reason,
        "dates": [],
        "alpha": [],
        "betas": {},
        "band_low": {},
        "band_high": {},
        "ex_ante_betas": {},
        "vintage_index": [],
        "vintages": [],
        "latest": {},
        "labels": [],
        "warnings": [],
    }
    return _with(base, **empty)


def _text(html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))


def _row(panel: str, factor: str) -> str:
    m = re.search(rf'<tr><th scope="row">.*?{re.escape(factor)}</span>.*?</tr>', panel, re.S)
    assert m is not None
    return m.group(0)


def test_absent_section_draws_nothing(base: FactorReport) -> None:
    assert base.kalman_betas is None
    assert render_kalman_panel(base) is None


def test_ok_panel_has_five_rows_question_and_registered_in_page(report: FactorReport) -> None:
    page = render_report_html(report)
    assert 'id="kalman"' in page and "Kalman-filter betas" in page
    assert "How did the exposures move, using only data up to each date?" in page
    panel = render_kalman_panel(report)
    assert panel is not None
    for name in FACTOR_NAMES:
        assert _row(panel, name)
    assert panel.count('class="rline c') == 5 and panel.count('class="band c') == 5
    for slot in range(1, 6):
        assert f'class="rline c{slot}"' in panel


def test_latest_numbers_as_printed(panel: str) -> None:
    mkt = _text(_row(panel, "Mkt-RF"))
    assert "1.154" in mkt and "0.0736" in mkt and "1.010 to +1.298" in mkt
    smb = _text(_row(panel, "SMB"))
    assert "0.722" in smb and "0.126" in smb and "0.475 to +0.969" in smb
    hml = _text(_row(panel, "HML"))
    assert f"{MINUS}0.329" in hml and f"{MINUS}0.652 to {MINUS}0.006" in hml
    assert "0.396" in _text(_row(panel, "RMW"))
    cma = _text(_row(panel, "CMA"))
    assert "0.623" in cma and "0.226" in cma and "0.180 to +1.066" in cma


def test_vintage_table_numbers_as_printed(panel: str) -> None:
    body = re.search(r"<h3>Yearly re-estimates</h3>.*?</table>", panel, re.S)
    assert body is not None
    text = _text(body.group(0))
    for needle in ("504", "756", "1,008", "1,260"):
        assert needle in text
    for lam in ("0.00000095", "0.0000055", "0.000012", "0.000011"):
        assert lam in text
    for window in ("2,052", "854", "580", "611"):
        assert window in text
    for vol in ("18.4%", "18.7%", "19.0%"):
        assert vol in text
    for d in ("12 Sep 2023", "29 Aug 2024", "18 Aug 2025", "5 Aug 2026"):
        assert d in text
    assert 'datetime="2023-09-12"' in body.group(0)
    assert "at its upper limit" not in text  # no vintage of the fixture is at a bound


def test_warm_up_nulls_do_not_draw(report: FactorReport, panel: str) -> None:
    full = report.kalman_betas
    assert full is not None
    first = next(i for i, b in enumerate(full.betas["Mkt-RF"]) if b is not None)
    assert first == 503
    # The date axis starts at the first estimate: its date is in the caption, an earlier one is not.
    assert f"starts at the first estimate, {full.dates[first].day} " in panel
    # No point is drawn left of the first estimate: every path starts at x = 0.0.
    for d in re.findall(r'<path class="rline c\d" d="M([\d.]+),', panel):
        assert float(d) == 0.0
    # The line ends at the right edge (the last date).
    for d in re.findall(r'<path class="rline c\d" d="([^"]+)"', panel):
        assert d.rsplit(" L", 1)[1].startswith("1000.0,")


def test_warm_up_only_section_shows_an_empty_state(base: FactorReport) -> None:
    payload = cast(dict[str, Any], section_payload("kalman_betas"))
    n = len(payload["dates"])
    null = [None] * n
    changes: dict[str, Any] = {
        "alpha": null,
        "vintage_index": null,
        "betas": {k: null for k in FACTOR_NAMES},
        "band_low": {k: null for k in FACTOR_NAMES},
        "band_high": {k: null for k in FACTOR_NAMES},
        "ex_ante_betas": {k: null for k in FACTOR_NAMES},
    }
    html = render_kalman_panel(_with(base, **changes))
    assert html is not None and "No estimate yet" in html
    assert "<svg" not in html.split("</header>")[1]


@pytest.mark.parametrize(
    ("status", "reason", "step"),
    [
        ("insufficient_data", "kalman_needs_504_rows: 300 rows.", "at least 504 trading days"),
        ("failed", "singular_burn_in: the first 21 rows do not identify the model.", "Check the"),
    ],
)
def test_not_ok_statuses_show_the_reason_and_no_numbers(
    base: FactorReport, status: str, reason: str, step: str
) -> None:
    html = render_kalman_panel(_not_ok(base, status, reason))
    assert html is not None
    assert reason in html and step in html
    assert 'class="empty"' in html and html.count('class="empty-do"') == 1
    after_head = html.split("</header>")[1]
    assert "<svg" not in after_head and "<table" not in after_head
    assert not re.search(r"\d\.\d", after_head.replace(reason, "").replace(step, ""))


def test_not_ok_page_still_renders(base: FactorReport) -> None:
    page = render_report_html(_not_ok(base, "failed", "singular_burn_in"))
    assert 'id="kalman"' in page


def test_lambda_at_bound_is_flagged_in_words(base: FactorReport) -> None:
    payload = cast(dict[str, Any], section_payload("kalman_betas"))
    vintages = json.loads(json.dumps(payload["vintages"]))
    vintages[1].update({"lam": 0.01, "lam_at_bound": "upper", "w_eq": 20.0})
    vintages[2].update({"lam": 0.0, "lam_at_bound": "zero", "w_eq": None})
    html = render_kalman_panel(
        _with(base, vintages=vintages, warnings=["kalman_lambda_at_upper_bound"])
    )
    assert html is not None
    text = _text(html)
    assert "at its upper limit: the filter follows daily noise" in text
    assert "at zero: no drift found" in text
    # The model's warning sentence sits in the folded "How this is computed" part.
    fold = html.split("<details", 1)[1]
    assert "the filter follows daily noise; the estimate is not meaningful" in fold
    assert "kalman_lambda_at_upper_bound" not in html


def test_labels_and_fold_texts(panel: str) -> None:
    fold = panel.split("<details", 1)[1]
    assert "How this is computed" in fold
    assert "Kalman-filter beta: each point uses only data up to that date." in fold
    assert "Model-based 95% band." in fold
    assert "partly reverse the next day" in fold
    assert "Every row uses the same vertical span" in fold
    assert "kalman_lambda_at_upper_bound" not in panel
    assert "reacts slowly to sudden changes" not in panel.split("<details", 1)[0]


def test_same_vertical_span_for_every_row(panel: str) -> None:
    labels: dict[str, tuple[float, float]] = {}
    for name in FACTOR_NAMES:
        row = _row(panel, name)
        top = re.search(r'class="yl top"[^>]*>([^<]+)<', row)
        bot = re.search(r'class="yl bot"[^>]*>([^<]+)<', row)
        assert top is not None and bot is not None
        labels[name] = (
            float(top.group(1).replace(MINUS, "-")),
            float(bot.group(1).replace(MINUS, "-")),
        )
    spans = [round(t - b, 1) for t, b in labels.values()]
    assert max(spans) - min(spans) <= 0.02


def test_true_minus_only(panel: str) -> None:
    visible = re.sub(r"<[^>]+>", "", panel)
    assert not re.search(r"(?<![\w-])-\d", visible)


def test_no_monospace_no_all_caps_eyebrow(panel: str) -> None:
    from factordesk.report.panels import kalman

    assert "monospace" not in panel.lower() and "monospace" not in kalman.CSS.lower()
    assert "text-transform" not in kalman.CSS and "letter-spacing" not in kalman.CSS
    assert "font-family" not in kalman.CSS
    for words in re.findall(r">([^<>]{3,})<", panel):
        assert not re.fullmatch(r"[A-Z][A-Z \-]{3,}", words.strip())


def test_html_is_escaped(base: FactorReport) -> None:
    reason = '<script>alert("x")</script> & <b>bold</b>'
    html = render_kalman_panel(_not_ok(base, "failed", reason))
    assert html is not None
    assert "<script>" not in html and "<b>" not in html
    assert "&lt;script&gt;" in html and "&amp;" in html


def test_payload_is_small_for_1300_rows(panel: str) -> None:
    paths = re.findall(r' d="([^"]+)"', panel)
    assert len(paths) == 10
    assert max(len(p) for p in paths) < 9_000
    assert len(panel) < 80_000
    for d in re.findall(r'<path class="rline c\d" d="([^"]+)"', panel):
        assert d.count(" L") + 1 <= 302


def test_panel_css_is_added_to_the_page_only_when_drawn(
    base: FactorReport, report: FactorReport
) -> None:
    assert ".kalman-vintages" in render_report_html(report)
    assert ".kalman-vintages" not in render_report_html(base)
