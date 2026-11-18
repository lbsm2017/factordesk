"""Schema, fixture, hook and status tests of the ``kalman_betas`` section (contract SC2.3).

The fixture ``fixtures/sections/kalman.json`` is a synthetic section (1,300 rows ending
2026-09-30, drifting betas from seed 20261118 + 640), not data of any ticker.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from factordesk.report.base import FACTOR_NAMES
from factordesk.report.schema import FactorReport, load_report
from factordesk.report.sections.kalman import (
    KALMAN_SECTION,
    WARNING_TEXT,
    KalmanBetaSeries,
)
from factordesk.tests.fixtures.sections import report_with_section, section_payload

MOCK = Path(__file__).parent / "fixtures" / "mock_report.json"
N_FIXTURE = 1300


def _payload() -> dict[str, Any]:
    value = section_payload("kalman_betas")
    assert isinstance(value, dict)
    return json.loads(json.dumps(value))


def _model(payload: dict[str, Any]) -> KalmanBetaSeries:
    return KalmanBetaSeries.model_validate_json(json.dumps(payload))


# ---------------------------------------------------------------------------- the fixture
def test_fixture_validates_round_trips_and_attaches_to_the_mock_report() -> None:
    section = _model(_payload())
    assert section.status == "ok" and section.reason is None
    assert KalmanBetaSeries.model_validate_json(section.model_dump_json()) == section
    report = report_with_section(load_report(MOCK), "kalman_betas")
    assert report.kalman_betas == section
    assert FactorReport.model_validate_json(report.model_dump_json()) == report
    # nothing else in the report changes
    assert report.model_copy(update={"kalman_betas": None}) == load_report(MOCK)


def test_fixture_shape_and_nulls() -> None:
    s = _model(_payload())
    assert s.model == "rw_betas_const_alpha_v1" and s.error_model == "gaussian"
    assert (s.burn_in_rows, s.training_rows, s.reestimate_every) == (21, 504, 252)
    assert len(s.dates) == N_FIXTURE and s.sample.n == N_FIXTURE
    assert s.dates[-1].isoformat() == "2026-09-30"
    assert tuple(s.betas) == FACTOR_NAMES == tuple(s.latest)
    assert [v is None for v in s.vintage_index] == [i < 503 for i in range(N_FIXTURE)]
    assert all(series[502] is None and series[503] is not None for series in s.betas.values())
    assert [v.rows for v in s.vintages] == [504, 756, 1008, 1260]
    assert s.vintage_index[503] == 0 and s.vintage_index[754] == 0 and s.vintage_index[755] == 1
    assert s.vintage_index[-1] == 3
    assert s.vintages[0].valid_from == s.dates[503] and s.vintages[-1].valid_to == s.dates[-1]
    assert s.labels == ["L-KF", "L-KBAND", "L-KTAIL"]
    assert set(s.labels) <= set(KALMAN_SECTION.label_text)


def test_fixture_has_no_nan_and_latest_matches_the_series() -> None:
    s = _model(_payload())
    text = s.model_dump_json()
    assert "NaN" not in text and "Infinity" not in text
    json.loads(text, parse_constant=_reject_constant)
    for name in FACTOR_NAMES:
        last = s.latest[name]
        assert last.beta == s.betas[name][-1]
        assert last.band_low == pytest.approx(s.band_low[name][-1], rel=1e-5)
        assert last.band_high == pytest.approx(s.band_high[name][-1], rel=1e-5)
        assert last.sd == pytest.approx((last.band_high - last.beta) / 1.959964, rel=1e-4)
        assert math.isfinite(last.sd) and last.sd > 0


def _reject_constant(name: str) -> float:
    raise AssertionError(f"non-finite JSON constant {name}")


def test_ex_ante_is_the_previous_filtered_beta() -> None:
    s = _model(_payload())
    for name in FACTOR_NAMES:
        assert s.ex_ante_betas[name][503] is None
        assert s.ex_ante_betas[name][504:] == s.betas[name][503:-1]


# ---------------------------------------------------------------------------- schema rules
def test_section_is_registered_with_its_labels() -> None:
    assert KALMAN_SECTION.report_field == "kalman_betas"
    assert KALMAN_SECTION.model is KalmanBetaSeries and not KALMAN_SECTION.many
    assert set(KALMAN_SECTION.label_text) == {"L-KF", "L-KBAND", "L-KTAIL"}
    assert set(WARNING_TEXT) == {"kalman_lambda_at_upper_bound"}


def test_a_misaligned_series_is_refused() -> None:
    p = _payload()
    p["betas"]["SMB"] = p["betas"]["SMB"][:-1]
    with pytest.raises(ValidationError):
        _model(p)


def test_factor_keys_must_be_the_display_names_in_order() -> None:
    p = _payload()
    p["betas"] = dict(reversed(list(p["betas"].items())))
    with pytest.raises(ValidationError):
        _model(p)
    p = _payload()
    p["band_low"]["mkt_rf"] = p["band_low"].pop("Mkt-RF")
    with pytest.raises(ValidationError):
        _model(p)


def test_warm_up_nulls_must_line_up_with_the_vintage_index() -> None:
    p = _payload()
    p["alpha"][10] = 0.0001
    with pytest.raises(ValidationError):
        _model(p)
    p = _payload()
    p["betas"]["HML"][600] = None
    with pytest.raises(ValidationError):
        _model(p)


def test_a_beta_outside_its_band_is_refused() -> None:
    p = _payload()
    p["band_high"]["CMA"][700] = p["betas"]["CMA"][700] - 0.5
    with pytest.raises(ValidationError):
        _model(p)


def test_unknown_warning_and_label_are_refused() -> None:
    p = _payload()
    p["warnings"] = ["something_else"]
    with pytest.raises(ValidationError):
        _model(p)
    p = _payload()
    p["labels"] = ["L-DESC"]
    with pytest.raises(ValidationError):
        _model(p)
    p = _payload()
    p["warnings"] = ["kalman_lambda_at_upper_bound"]
    assert _model(p).warnings == ["kalman_lambda_at_upper_bound"]


def test_nan_is_refused_everywhere() -> None:
    p = _payload()
    p["betas"]["Mkt-RF"][800] = float("nan")
    with pytest.raises(ValidationError):
        _model(p)
    p = _payload()
    p["vintages"][0]["lam"] = float("inf")
    with pytest.raises(ValidationError):
        _model(p)


def _not_ok(status: str, reason: str | None) -> dict[str, Any]:
    p = _payload()
    p.update(
        status=status,
        reason=reason,
        dates=[],
        alpha=[],
        vintage_index=[],
        vintages=[],
        latest={},
        labels=[],
        warnings=[],
    )
    for key in ("betas", "band_low", "band_high", "ex_ante_betas"):
        p[key] = {}
    return p


@pytest.mark.parametrize("status", ["insufficient_data", "failed"])
def test_a_not_ok_section_is_empty_and_has_a_reason(status: str) -> None:
    s = _model(_not_ok(status, "A reason."))
    assert s.status == status and s.reason == "A reason." and s.dates == []
    with pytest.raises(ValidationError):
        _model(_not_ok(status, None))
    kept = _not_ok(status, "A reason.")
    kept["dates"] = _payload()["dates"]
    with pytest.raises(ValidationError):
        _model(kept)


def test_an_ok_section_has_a_reason_of_none_and_enough_rows() -> None:
    p = _payload()
    p["reason"] = "not allowed"
    with pytest.raises(ValidationError):
        _model(p)
    short = _payload()
    short["dates"] = short["dates"][:100]
    with pytest.raises(ValidationError):
        _model(short)
