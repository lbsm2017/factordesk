"""Static HTML panel of the residual section (methodology R8, contract SC7)."""

from __future__ import annotations

import html
import json
import re
from pathlib import Path
from typing import Any

from factordesk.report import load_report, render_report_html
from factordesk.report.panel_registry import registered_panels
from factordesk.report.panels.residual_alpha import (
    NEXT_STEP,
    PANEL_CSS,
    PIT_NEXT_STEP,
    render_residual_alpha_panel,
)
from factordesk.report.schema import FactorReport
from factordesk.report.sections.residual_alpha import RESIDUAL_LABEL_TEXT
from factordesk.tests.fixtures.sections import report_with_section, section_payload

MOCK = Path(__file__).parent / "fixtures" / "mock_report.json"
MINUS = "−"


def _mock() -> FactorReport:
    return load_report(MOCK)


def _with(payload: dict[str, Any]) -> FactorReport:
    data = json.loads(_mock().model_dump_json())
    data["residual"] = payload
    return FactorReport.model_validate_json(json.dumps(data))


def _fixture() -> dict[str, Any]:
    payload = section_payload("residual")
    assert isinstance(payload, dict)
    return json.loads(json.dumps(payload))


def _panel(report: FactorReport) -> str:
    out = render_residual_alpha_panel(report)
    assert out is not None
    return out


def _text(markup: str) -> str:
    """Visible text: tags dropped, entities decoded, white space collapsed."""
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", markup)))


def _null_numbers(obj: dict[str, Any], keep: set[str]) -> dict[str, Any]:
    """``obj`` with every field outside ``keep`` set to None (a statistic that is not ok)."""
    return {k: (v if k in keep else None) for k, v in obj.items()}


STAT_KEEP = {"status", "reason", "sample", "labels", "caption", "basis", "beta_window"}


def _pit_insufficient(payload: dict[str, Any]) -> dict[str, Any]:
    """The payload as a short span produces it: point-in-time parts insufficient."""
    reason = "Point-in-time residual needs at least 756 trading days; this period has 559."
    pit = _null_numbers(payload["point_in_time"], STAT_KEEP)
    pit.update(status="insufficient_data", reason=reason, wiped_out=False)
    payload["point_in_time"] = pit
    chart = payload["chart"]
    n = len(chart["dates"])
    chart.update(
        point_in_time_status="insufficient_data",
        point_in_time_reason=reason,
        comparison_start=None,
        in_sample_compare=[None] * n,
        point_in_time_compare=[None] * n,
    )
    gap = _null_numbers(payload["gap"], STAT_KEEP)
    gap.update(status="insufficient_data", reason=reason)
    payload["gap"] = gap
    years = payload["calendar_years"]
    for y in years["years"]:
        y.update(
            n_point_in_time=0,
            point_in_time_partial=True,
            point_in_time_sum=None,
            point_in_time_noise_sd=None,
        )
    diag = _null_numbers(
        payload["diagnostics"][1], STAT_KEEP | {"ljung_box_lags", "arch_lags"}
    )
    diag.update(status="insufficient_data", reason=reason, findings=[])
    payload["diagnostics"][1] = diag
    return payload


def test_absent_section_draws_nothing() -> None:
    assert render_residual_alpha_panel(_mock()) is None
    assert 'id="residual"' not in render_report_html(_mock())


def test_panel_is_in_place_and_brings_its_css() -> None:
    page = render_report_html(report_with_section(_mock(), "residual"))
    assert 'id="residual"' in page
    assert PANEL_CSS in page
    assert PANEL_CSS not in render_report_html(_mock())
    spec = next(p for p in registered_panels() if p.name == "residual_alpha")
    assert spec.position == 710


def test_fixture_numbers_are_printed() -> None:
    text = _text(_panel(report_with_section(_mock(), "residual")))
    for expected in (
        "+27.2%",
        "15.4% to 39.1%",
        "4.51",
        "+25.4%",
        "8.0% to 42.9%",
        "2.86",
        "10.3%",
        "10.9%",
        "2.64",
        "2.33",
        "+80.8%",
        "+35.3%",
        "56.7%",
        "55.0%",
        f"{MINUS}6.5%",
        f"{MINUS}6.4%",
        "22 Dec 2025",
        "12 Jan 2026",
        "19 May 2026",
        "+0.4%",
        "100% kept",
        "97.7%",
        "+32.2%",
        "+23.5%",
        f"{MINUS}8.7%",
        "p = 0.477",
        "reliable",
    ):
        assert expected in text, expected
    assert (
        "In-sample alpha holds up out-of-sample with point-in-time betas (100% kept) and is "
        "distinguishable from zero. This rules out hindsight in the betas, not luck."
    ) in text
    assert (
        "What did this stock return beyond its factor exposures, and does it hold up without "
        "hindsight?"
    ) in text
    assert "2 of 2 separate one-year windows show an alpha different from zero" in text


def test_calendar_year_sums_are_in_the_cells() -> None:
    markup = _panel(report_with_section(_mock(), "residual"))
    for number in ("0.1703", "0.3001", "0.1778", "0.1337", "0.1320"):
        assert f"Sum {number}" in markup, number
    text = _text(markup)
    for year in ("2024", "2025", "2026"):
        assert year in text
    assert "+17.0%" in text and "+30.0%" in text and "+17.8%" in text


def test_caveats_are_exact_and_in_order() -> None:
    report = report_with_section(_mock(), "residual")
    assert report.residual is not None
    text = _text(_panel(report))
    caveats = report.residual.caveats
    assert len(caveats) == 5
    positions = [text.index(c) for c in caveats]
    assert positions == sorted(positions)


def test_labels_sit_in_the_fold() -> None:
    markup = _panel(report_with_section(_mock(), "residual"))
    fold = markup[markup.index('<details class="how">') :]
    assert "How this is computed" in fold
    text = _text(fold)
    for key in ("L-INSAMPLE", "L-PIT", "L-DESC-PIT", "L-HEDGE"):
        assert RESIDUAL_LABEL_TEXT[key] in text, key


def test_chart_draws_the_three_lines_and_the_rolling_band() -> None:
    markup = _panel(report_with_section(_mock(), "residual"))
    for cls in ("full", "same", "pit", "roll"):
        assert f'<path class="ra-l {cls}"' in markup, cls
    assert markup.count('<path class="ra-band"') == 1
    # A comparison line is null before the anchor, so its path starts to the right of zero.
    pit = re.search(r'<path class="ra-l pit" d="M([\d.]+),', markup)
    full = re.search(r'<path class="ra-l full" d="M([\d.]+),', markup)
    assert pit is not None and full is not None
    assert float(full.group(1)) == 0.0 and float(pit.group(1)) > 100.0
    assert "Warm-up: the first 252 trading days" in _text(markup)


def test_severity_is_a_word_and_a_glyph() -> None:
    markup = _panel(report_with_section(_mock(), "residual"))
    assert '<span class="ra-sev">Info</span>' in markup
    assert '<circle cx="8" cy="8" r="6.5"/>' in markup.split('class="notice ra-banner"')[1]
    payload = _fixture()
    payload["gap"].update(
        verdict="mostly_disappears", severity="warning", message="In-sample alpha mostly gone."
    )
    warned = _panel(_with(payload))
    banner = warned.split('class="notice ra-banner"')[1].split("</div>")[0]
    assert '<span class="ra-sev">Warning</span>' in banner
    assert "M8 1.5 15 14.5H1z" in banner
    assert "In-sample alpha mostly gone." in banner


def test_failed_and_not_applicable_show_the_reason_and_no_numbers() -> None:
    for status, reason in (
        (
            "failed",
            "Residual analysis is unavailable because the regression could not be computed.",
        ),
        ("not_applicable", "The fit is exact, so there is no residual."),
    ):
        payload = _fixture()
        payload.update(status=status, reason=reason)
        markup = _panel(_with(payload))
        assert 'class="empty"' in markup
        assert reason in markup and NEXT_STEP in markup
        assert "<table" not in markup and "<svg" not in markup
        text = _text(markup)
        assert not re.search(r"\d+\.\d%", text)
        assert "Residual return" in text  # title and question stay
        assert "What did this stock return" in text


def test_point_in_time_insufficient_keeps_the_in_sample_parts() -> None:
    payload = _pit_insufficient(_fixture())
    markup = _panel(_with(payload))
    text = _text(markup)
    reason = payload["point_in_time"]["reason"]
    assert "+27.2%" in text and "4.51" in text and "+80.8%" in text
    assert reason in text and PIT_NEXT_STEP in text
    assert "+25.4%" not in text and "2.86" not in text
    assert "Survival of the alpha" not in text and 'class="notice ra-banner"' not in markup
    assert '<path class="ra-l full"' in markup
    assert '<path class="ra-l pit"' not in markup and '<path class="ra-l same"' not in markup
    assert "Warm-up" not in text
    assert "n/a" in text  # the calendar-year point-in-time cells
    # The in-sample findings stay; the point-in-time ones give way to the reason.
    assert "No clear day-to-day correlation" in text


def test_gap_without_verdict_is_handled() -> None:
    # A gap that is not ok while the point-in-time part is: shown as a quiet reason.
    payload = _fixture()
    gap = _null_numbers(payload["gap"], STAT_KEEP)
    gap.update(status="insufficient_data", reason="The comparison needs more days.")
    payload["gap"] = gap
    text = _text(_panel(_with(payload)))
    assert "The comparison needs more days." in text
    assert "100% kept" not in text


def test_text_is_escaped() -> None:
    payload = _fixture()
    attack = '<script>alert("x")</script> & <b>'
    payload["question"] = attack
    payload["caveats"][0] = attack
    payload["gap"]["message"] = attack
    payload["warnings"] = [{"code": "other", "message": attack}]
    payload["split_half"]["caption"] = attack
    payload["diagnostics"][0]["findings"][0] = attack
    markup = _panel(_with(payload))
    assert "<script>" not in markup and "<b>" not in markup
    assert html.escape(attack, quote=True) in markup
    failed = _fixture()
    failed.update(status="failed", reason=attack)
    assert "<script>" not in _panel(_with(failed))


def test_true_minus_only() -> None:
    markup = _panel(report_with_section(_mock(), "residual"))
    text = _text(re.sub(r'title="[^"]*"', "", markup))
    assert MINUS in text
    # A hyphen before a digit is fine inside an ISO date or a range of words, never as a sign.
    assert not re.search(r"(?<![\w-])-\d", text)
    assert not re.search(r"(?<![\w-])-\.\d", text)


def test_no_monospace_and_no_all_caps_eyebrow() -> None:
    markup = _panel(report_with_section(_mock(), "residual"))
    for source in (markup, PANEL_CSS):
        lowered = source.lower()
        assert "monospace" not in lowered and "ui-mono" not in lowered
        assert "text-transform" not in lowered
        assert "<code" not in lowered and "<kbd" not in lowered
    for piece in re.findall(r">([^<>]+)<", markup):
        words = piece.strip()
        assert not (len(words) > 3 and words.upper() == words and words.isalpha()), words
    assert 'class="eyebrow"' not in markup


def test_whole_report_renders_with_the_panel() -> None:
    page = render_report_html(report_with_section(_mock(), "residual"))
    ids = re.findall(r'<section class="panel[^"]*" id="([^"]+)"', page)
    assert ids.index("residual") == ids.index("risk") + 1
