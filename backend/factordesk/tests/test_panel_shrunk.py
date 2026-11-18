"""Static HTML panel of the shrunk-betas section (spec SB5, SB6; contract SC2.4, SC3.3)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from factordesk.report import FactorReport, load_report, render_report_html
from factordesk.report.panels.shrunk import (
    CAPTION,
    CSS,
    LEGEND_TEXT,
    MOVED_WORD,
    NEXT_STEP,
    NEXT_STEP_FAILED,
    NO_VISIBLE_PULL,
    POWER_HEADING,
    render_shrunk_panel,
)
from factordesk.report.render_html import esc
from factordesk.report.sections.shrunk import LABEL_TEXT
from factordesk.tests.fixtures.sections import report_with_section

MOCK = Path(__file__).parent / "fixtures" / "mock_report.json"


def _report() -> FactorReport:
    return report_with_section(load_report(MOCK), "shrunk_betas")


def _edited(edit: Any) -> FactorReport:
    """The fixture report with ``edit(list_of_section_dicts)`` applied, validated again."""
    payload: dict[str, Any] = json.loads(_report().model_dump_json())
    edit(payload["shrunk_betas"])
    return FactorReport.model_validate_json(json.dumps(payload))


def _panel(report: FactorReport) -> str:
    html = render_shrunk_panel(report)
    assert html is not None
    return html


def _scope(html: str, scope_id: str) -> str:
    m = re.search(
        rf'<div class="shr-scope[^"]*" id="{scope_id}">'
        r'.*?(?=<div class="shr-scope|<div class="foot"|$)',
        html,
        re.S,
    )
    assert m is not None
    return m.group(0)


def _text(html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))


def test_absent_section_draws_nothing() -> None:
    assert render_shrunk_panel(load_report(MOCK)) is None
    assert 'id="shrunk"' not in render_report_html(load_report(MOCK))


def test_panel_sits_in_the_page_with_its_css() -> None:
    page = render_report_html(_report())
    assert '<section class="panel" id="shrunk"' in page
    assert CSS in page
    assert page.index('id="exposures"') < page.index('id="shrunk"') < page.index('id="returns"')


def test_full_sample_numbers() -> None:
    row = re.search(
        r'<tr[^>]*id="shrunk-full-Mkt-RF".*?</tr>', _scope(_panel(_report()), "shrunk-full"), re.S
    )
    assert row is not None
    cells = _text(row.group(0))
    for printed in ("+1.009", "0.007", "[+0.996, +1.022]", "0.1%"):
        assert printed in cells
    assert cells.count("+1.009") == 2  # OLS beta and shrunk beta


def test_latest_window_numbers_and_marker() -> None:
    scope = _scope(_panel(_report()), "shrunk-latest")
    mkt = re.search(r'<tr[^>]*id="shrunk-latest-Mkt-RF".*?</tr>', scope, re.S)
    assert mkt is not None
    cells = _text(mkt.group(0))
    for printed in ("+1.484", "0.222", "+1.227", "[+0.929, +1.526]", "53.0%"):
        assert printed in cells
    assert 'class="dm"' in mkt.group(0)  # pull of 53% draws the hollow diamond
    cma = _text(re.search(r'<tr[^>]*id="shrunk-latest-CMA".*?</tr>', scope, re.S).group(0))  # type: ignore[union-attr]
    assert "80.3%" in cma


def test_scope_headings() -> None:
    page = _panel(_report())
    assert "<h3>Full sample (559 days)</h3>" in page
    assert "<h3>Latest 252-day window</h3>" in page
    assert page.index("Full sample") < page.index("Latest 252-day window")


def test_table_columns() -> None:
    scope = _scope(_panel(_report()), "shrunk-full")
    heads = re.findall(r'<th[^>]*scope="col"[^>]*>(.*?)</th>', scope.split("shr-power")[0], re.S)
    assert [_text(h).strip() for h in heads] == [
        "Factor",
        "OLS beta",
        "se",
        "Shrunk beta",
        "95% credible interval",
        "Pull",
    ]


def test_no_visible_pull_line_for_the_long_sample_only() -> None:
    html = _panel(_report())
    assert _scope(html, "shrunk-full").count(NO_VISIBLE_PULL) == 1
    assert NO_VISIBLE_PULL not in _scope(html, "shrunk-latest")
    assert NO_VISIBLE_PULL == (
        "Shrinkage moves no beta by a visible amount: this sample is long enough."
    )
    # nothing in the long sample reaches the threshold, so it draws no diamond
    assert 'class="dm"' not in _scope(html, "shrunk-full")


def test_marker_threshold_is_five_percent() -> None:
    def edit(sections: list[dict[str, Any]]) -> None:
        pulls = [0.0499, 0.05, 1.7, -0.2, 0.9]
        for beta, pull in zip(sections[1]["betas"], pulls, strict=True):
            beta["pull"] = pull

    scope = _scope(_panel(_edited(edit)), "shrunk-latest")
    marked = [
        f
        for f in ("Mkt-RF", "SMB", "HML", "RMW", "CMA")
        if 'class="dm"'
        in re.search(rf'<tr[^>]*id="shrunk-latest-{f}".*?</tr>', scope, re.S).group(0)  # type: ignore[union-attr]
    ]
    assert marked == ["SMB", "HML", "CMA"]
    assert "100.0%" in scope  # clipped to 1
    assert "0.0%" in scope  # clipped to 0


def test_power_statements_are_a_list_under_their_heading() -> None:
    html = _panel(_report())
    latest = _scope(html, "shrunk-latest")
    assert POWER_HEADING == "What the test behind the reliable tags could detect"
    assert f'<h4 class="shr-power-h">{POWER_HEADING}</h4>' in latest
    report = _report()
    assert report.shrunk_betas is not None
    for section in report.shrunk_betas:
        scope = _scope(html, f"shrunk-{'full' if section.scope == 'full_sample' else 'latest'}")
        items = re.findall(r"<li>(.*?)</li>", scope.split('class="shr-power"')[1], re.S)
        assert items == [esc(p.text or "") for p in section.power]
    assert "would take more than 50 years" in latest
    assert "is already detectable" in _scope(html, "shrunk-full")


def test_moved_away_beta_has_a_word_and_a_glyph() -> None:
    scope = _scope(_panel(_report()), "shrunk-latest")
    smb = re.search(r'<tr[^>]*id="shrunk-latest-SMB".*?</tr>', scope, re.S)
    assert smb is not None
    assert MOVED_WORD in _text(smb.group(0))
    assert "<svg" in smb.group(0)
    assert "+0.563" in _text(smb.group(0))
    assert esc(LABEL_TEXT["L-CORR-MOVE"]) in smb.group(0)
    assert scope.count(MOVED_WORD) == 1  # only SMB moved away
    assert MOVED_WORD == "Moved away from typical"


def test_moved_away_shows_only_where_the_pull_marker_is_drawn() -> None:
    """A moved-away flag on a row with a negligible pull draws neither the word nor L-CORR-MOVE."""

    def edit(sections: list[dict[str, Any]]) -> None:
        sections[0]["betas"][2]["moved_away"] = True  # HML, pull 0.0007 in the full sample
        sections[0]["labels"].append("L-CORR-MOVE")
        sections[1]["betas"][1]["pull"] = 0.04  # SMB: moved away, but pull below 0.05

    html = _panel(_edited(edit))
    assert MOVED_WORD not in html
    foot = html[html.index('<div class="foot">') :]
    assert esc(LABEL_TEXT["L-CORR-MOVE"]) not in foot

    # the flag and the label come back once a visible pull carries them
    def back(sections: list[dict[str, Any]]) -> None:
        edit(sections)
        sections[1]["betas"][1]["pull"] = 0.05

    again = _panel(_edited(back))
    assert again.count(MOVED_WORD) == 1
    assert esc(LABEL_TEXT["L-CORR-MOVE"]) in again[again.index('<div class="foot">') :]


def test_labels_are_footnote_texts() -> None:
    html = _panel(_report())
    foot = html[html.index('<div class="foot">') :]
    for key in ("L-SHRINK", "L-SHRINK-PRIOR", "L-CRED", "L-MDE", "L-CORR-MOVE"):
        assert esc(LABEL_TEXT[key]) in foot
    assert "Descriptive, in-sample, not predictive." in foot
    assert "<details" in foot and "How this is computed" in foot
    assert "49 industry and 75 size portfolios" in foot
    assert "0.764" in foot  # a prior spread value


def test_corr_move_label_only_when_listed() -> None:
    def edit(sections: list[dict[str, Any]]) -> None:
        sections[1]["labels"] = [k for k in sections[1]["labels"] if k != "L-CORR-MOVE"]

    foot = _panel(_edited(edit))
    foot = foot[foot.index('<div class="foot">') :]
    assert esc(LABEL_TEXT["L-CORR-MOVE"]) not in foot


def _not_ok(sections: list[dict[str, Any]]) -> None:
    sections[1].update(
        status="insufficient_data",
        reason="The latest window has too few rows: 120 of 252 needed.",
        prior=None,
        betas=[],
        power=[],
    )


def test_not_ok_scope_shows_reason_and_one_next_step() -> None:
    html = _panel(_edited(_not_ok))
    latest = _scope(html, "shrunk-latest")
    assert 'class="empty"' in latest
    assert "The latest window has too few rows: 120 of 252 needed." in latest
    assert latest.count("empty-do") == 1 and NEXT_STEP in latest
    assert "<table" not in latest
    # the other scope still draws, and so does the footnote
    assert 'id="shrunk-full-Mkt-RF"' in html
    assert '<div class="foot">' in html


def test_next_step_depends_on_the_status() -> None:
    def failed(sections: list[dict[str, Any]]) -> None:
        _not_ok(sections)
        sections[1]["status"] = "failed"

    latest = _scope(_panel(_edited(failed)), "shrunk-latest")
    assert NEXT_STEP_FAILED in latest and NEXT_STEP not in latest
    assert NEXT_STEP_FAILED == (
        "Run the report again; if it repeats, check the factor data in Data and audit."
    )


def test_every_scope_not_ok_draws_frame_and_empty_states_only() -> None:
    def edit(sections: list[dict[str, Any]]) -> None:
        for s in sections:
            s.update(status="failed", reason="Prior files missing.", prior=None, betas=[], power=[])

    html = _panel(_edited(edit))
    assert html.count('class="empty"') == 2
    assert "<table" not in html
    assert '<div class="foot">' not in html
    assert 'class="legend"' not in html


def test_html_is_escaped() -> None:
    evil = '<script>alert("x")</script> & <b>'

    def edit(sections: list[dict[str, Any]]) -> None:
        _not_ok(sections)
        sections[1]["reason"] = evil
        sections[0]["power"][0]["text"] = evil

    html = _panel(_edited(edit))
    assert "<script>" not in html
    assert "<b>" not in html
    assert html.count("&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt; &amp; &lt;b&gt;") == 2


def test_missing_power_text_renders_an_empty_cell() -> None:
    def edit(sections: list[dict[str, Any]]) -> None:
        sections[0]["power"][1]["text"] = None

    html = _panel(_edited(edit))
    assert "None" not in html


def test_prior_sentence_reads_as_in_the_react_panel() -> None:
    foot = _panel(_report())
    foot = foot[foot.index('<div class="foot">') :]
    assert (
        "Prior centre and spread per factor: Mkt-RF 1.000 and 0.209; SMB 0.000 and 0.764; "
        "HML 0.000 and 0.341; RMW 0.000 and 0.329; CMA 0.000 and 0.254. "
        "The spread comes from 49 industry and 75 size portfolios, 2016-09-21 to 2026-09-30."
    ) in foot
    # the descriptive label is the footnote; the model labels sit in the fold, after the prior
    assert foot.index("Descriptive, in-sample, not predictive.") < foot.index("<details")
    assert foot.index("Prior centre and spread") < foot.index(esc(LABEL_TEXT["L-SHRINK"]))


def test_shared_wording_is_fixed() -> None:
    """The words the React panel repeats (pinned there too): change both or neither."""
    html = _panel(_report())
    assert LEGEND_TEXT == "Pulled 5% or more toward typical"
    assert (
        NO_VISIBLE_PULL
        == "Shrinkage moves no beta by a visible amount: this sample is long enough."
    )
    assert NEXT_STEP == "Widen the date range and run the report again."
    assert f'<caption class="vh">{CAPTION}</caption>' in html
    assert CAPTION == (
        "OLS and shrunk betas with standard errors, 95% credible intervals and pull; "
        "a marker is drawn only where the pull is at least 5%"
    )
    assert (
        "Pull is the share of the way from the OLS beta to its typical value: 0% means no move, "
        "100% means all the way."
    ) in html


def test_no_monospace_and_no_all_caps_eyebrow() -> None:
    html = _panel(_report())
    for banned in ("monospace", "ui-monospace", "<code", "<pre", "<kbd", "<samp", "text-transform"):
        assert banned not in html
        assert banned not in CSS
    assert "letter-spacing" not in CSS
    for visible in re.findall(r">([^<>]+)<", html):
        letters = re.sub(r"[^A-Za-z]", "", visible)
        # all-caps words are the factor names and abbreviations only
        if len(letters) > 4 and letters.isupper():
            raise AssertionError(f"all-caps text: {visible!r}")


def test_marker_never_relies_on_colour_alone() -> None:
    html = _panel(_report())
    assert "color:#" not in CSS and "rgb(" not in CSS  # tokens only
    legend = re.search(r'<ul class="legend".*?</ul>', html, re.S)
    assert legend is not None
    assert "Pulled 5% or more toward typical" in _text(legend.group(0))
