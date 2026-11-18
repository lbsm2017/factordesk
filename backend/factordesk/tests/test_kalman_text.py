"""One wording for the static and the React Kalman panel (``report/kalman_text.json``).

The JSON file is the source; the React panel imports a checked-in copy
(``frontend/src/text/kalman.json``). The frontend test compares the same two files, so a change on
one side that is not copied to the other fails on both.
"""

from __future__ import annotations

import html as html_lib
import json
import re
from pathlib import Path
from typing import Any, cast

import pytest

from factordesk.report import load_report
from factordesk.report.kalman_text import TEXT_PATH, fill, kalman_text
from factordesk.report.panels.kalman import render_kalman_panel
from factordesk.report.schema import FactorReport
from factordesk.report.sections.kalman import WARNING_TEXT
from factordesk.tests.fixtures.sections import section_payload

MOCK = Path(__file__).parent / "fixtures" / "mock_report.json"
FRONTEND_COPY = Path(__file__).resolve().parents[3] / "frontend" / "src" / "text" / "kalman.json"


def _flat(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [s for v in cast(list[object], value) for s in _flat(v)]
    if isinstance(value, dict):
        return [s for v in cast(dict[str, object], value).values() for s in _flat(v)]
    raise AssertionError(f"unexpected JSON value {value!r}")


def _payload() -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(json.dumps(section_payload("kalman_betas"))))


def _report(**changes: Any) -> FactorReport:
    payload = _payload()
    payload.update(changes)
    doc = json.loads(load_report(MOCK).model_dump_json())
    doc["kalman_betas"] = payload
    return FactorReport.model_validate_json(json.dumps(doc))


def _visible(html: str) -> str:
    return html_lib.unescape(re.sub(r"<[^>]+>", " ", html))


def _squash(text: str) -> str:
    return " ".join(text.split())


def test_every_string_is_plain_text() -> None:
    for text in _flat(kalman_text()):
        assert text == text.strip() and text
        assert "<" not in text and "  " not in text


def test_placeholders_are_the_known_ones() -> None:
    known = {"first", "last", "rows"}
    for text in _flat(kalman_text()):
        assert set(re.findall(r"\{(\w+)\}", text)) <= known


def test_warning_texts_of_the_section_come_from_the_file() -> None:
    assert kalman_text()["warnings"] == WARNING_TEXT


def test_frontend_copy_is_equal_to_the_source() -> None:
    if not FRONTEND_COPY.parent.is_dir():
        pytest.skip("the frontend folder is not part of this checkout")
    assert FRONTEND_COPY.read_text(encoding="utf-8") == TEXT_PATH.read_text(encoding="utf-8"), (
        "frontend/src/text/kalman.json differs from backend/factordesk/report/kalman_text.json: "
        "copy the backend file over it"
    )


def test_ok_panel_prints_every_chosen_text() -> None:
    text = kalman_text()
    vintages = _payload()["vintages"]
    vintages[1].update({"lam": 0.01, "lam_at_bound": "upper", "w_eq": 20.0})
    vintages[2].update({"lam": 0.0, "lam_at_bound": "zero", "w_eq": None})
    report = _report(vintages=vintages, warnings=["kalman_lambda_at_upper_bound"])
    html = render_kalman_panel(report)
    assert html is not None
    seen = _squash(_visible(html)) + " " + html_lib.unescape(html)
    section = report.kalman_betas
    assert section is not None
    must = [
        text["title"],
        text["question"],
        text["reading"],
        *text["legend"],
        *text["beta_heads"].values(),
        text["sd_title"],
        text["vintage_title"],
        *text["vintage_heads"],
        text["window_none"],
        *text["bound"].values(),
        *text["fold"].values(),
        *text["warnings"].values(),
    ]
    for s in must:
        assert s in seen, s
    caption = fill(text["table_caption"], last="")
    assert caption.split("latest at ")[0] in seen
    first = section.dates[503]
    visible = fill(
        text["footnote"],
        first=f"{first.day} {first:%b %Y}",
        last=f"{section.dates[-1].day} {section.dates[-1]:%b %Y}",
        rows=section.training_rows,
    )
    assert visible in seen


@pytest.mark.parametrize(
    ("status", "step_key"), [("insufficient_data", "insufficient_data"), ("failed", "failed")]
)
def test_empty_states_print_the_chosen_next_steps(status: str, step_key: str) -> None:
    empty: dict[str, Any] = {
        "status": status,
        "reason": "r",
        "dates": [],
        "alpha": [],
        "betas": {},
        "band_low": {},
        "band_high": {},
        "vintage_index": [],
        "vintages": [],
        "latest": {},
        "labels": [],
        "warnings": [],
    }
    html = render_kalman_panel(_report(**empty))
    assert html is not None
    step = fill(kalman_text()["empty"][step_key], rows=504)
    assert step in html_lib.unescape(html)


def test_warm_up_wording() -> None:
    n = len(_payload()["dates"])
    null = [None] * n
    factors = ["Mkt-RF", "SMB", "HML", "RMW", "CMA"]
    html = render_kalman_panel(
        _report(
            alpha=null,
            vintage_index=null,
            betas={k: null for k in factors},
            band_low={k: null for k in factors},
            band_high={k: null for k in factors},
        )
    )
    assert html is not None
    empty = kalman_text()["empty"]
    assert empty["warm_up_reason"] in html and empty["warm_up_step"] in html
