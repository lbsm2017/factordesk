"""Schema, fixture, hook and status tests of the ``kalman_betas`` section (contract SC2.3).

The fixture ``fixtures/sections/kalman.json`` is a synthetic section (1,300 rows ending
2026-09-30, drifting betas from seed 20261118 + 640), not data of any ticker.
"""

from __future__ import annotations

import json
import math
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from factordesk.analytics import kalman as kalman_module
from factordesk.analytics.kalman import kalman_betas
from factordesk.pipeline import assemble_report
from factordesk.report.base import FACTOR_NAMES
from factordesk.report.schema import FactorReport, load_report
from factordesk.report.sections.kalman import (
    KALMAN_SECTION,
    WARNING_TEXT,
    KalmanBetaSeries,
)
from factordesk.section_hooks import kalman as kalman_hook
from factordesk.section_hooks.context import SectionContext
from factordesk.section_hooks.kalman import section_from_result
from factordesk.tests.fixtures.dgp import Synthetic, dgp_a, dgp_n, rng_for
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


# ---------------------------------------------------------------------------- pipeline hook
NOW = datetime(2026, 11, 18, 15, 0, tzinfo=UTC)
ANALYTICS = Path(kalman_module.__file__).parent


def _report(d: Synthetic) -> FactorReport:
    return assemble_report("SYN", d.history, d.factors, now=NOW, factors_downloaded_at=None)


def _section(report: FactorReport) -> KalmanBetaSeries:
    assert report.kalman_betas is not None
    return report.kalman_betas


@pytest.fixture(scope="module")
def dgp_report() -> FactorReport:
    return _report(dgp_a(rng_for(650), n=800))


def test_hook_fills_the_section_from_the_analysis_sample(dgp_report: FactorReport) -> None:
    s = _section(dgp_report)
    assert s.status == "ok" and s.sample == dgp_report.regression.sample
    assert len(s.dates) == dgp_report.data.n_obs == 800
    d = dgp_a(rng_for(650), n=800)
    result = kalman_betas(d.ret - d.rf, d.f)
    for k, name in enumerate(FACTOR_NAMES):
        expected = [None if math.isnan(v) else float(f"{v:.6g}") for v in result.betas[:, k]]
        assert s.betas[name] == expected
    assert [v.rows for v in s.vintages] == [504, 756] and s.error_model == "gaussian"
    assert s.vintages[0].estimated_through == s.dates[503]
    assert s.vintages[0].resid_vol_ann == pytest.approx(math.sqrt(252 * s.vintages[0].resid_var))
    assert dgp_report.quality_gate.fired is False and s.labels == ["L-KF", "L-KBAND"]
    for key in ("L-KF", "L-KBAND", "L-KTAIL"):
        assert key in dgp_report.label_text
    assert s.warnings == []


def test_series_are_rounded_to_six_significant_digits_and_json_has_no_nan(
    dgp_report: FactorReport,
) -> None:
    s = _section(dgp_report)
    values = [v for series in s.betas.values() for v in series if v is not None]
    assert values and all(float(f"{v:.6g}") == v for v in values)
    json.loads(dgp_report.model_dump_json(), parse_constant=_reject_constant)


def test_gate_that_fires_adds_the_tail_label() -> None:
    d = dgp_n(rng_for(651), n=800)
    report = _report(d)
    assert report.quality_gate.fired is True
    assert _section(report).labels == ["L-KF", "L-KBAND", "L-KTAIL"]


def test_n_504_gives_exactly_one_stamp() -> None:
    s = _section(_report(dgp_a(rng_for(652), n=504)))
    assert s.status == "ok" and len(s.dates) == 504
    assert sum(v is not None for v in s.vintage_index) == 1 and s.vintage_index[503] == 0
    assert len(s.vintages) == 1 and s.vintages[0].valid_from == s.vintages[0].valid_to
    assert all(series[503] is not None for series in s.betas.values())
    assert all(series[503] is None for series in s.ex_ante_betas.values())


def test_singular_burn_in_is_a_failed_section() -> None:
    d = dgp_a(rng_for(653), n=600)
    f = d.f.copy()
    f[:21, 1] = 0.0005  # a constant factor over rows 1..21 duplicates the intercept
    s = _section(_report(dgp_a(rng_for(653), n=600, f=f)))
    assert s.status == "failed" and s.reason is not None and "singular_burn_in" in s.reason
    assert s.dates == [] and s.vintages == [] and s.labels == []
    assert s.sample.n == 600


def test_insufficient_sample_reason_names_the_code() -> None:
    d = dgp_a(rng_for(654), n=520)
    result = kalman_betas((d.ret - d.rf)[:503], d.f[:503])
    info = _section(_report(d)).sample
    s = section_from_result(result, d.dates[:503], info, gate_fired=False)
    assert s.status == "insufficient_data" and s.reason is not None
    assert "kalman_needs_504_rows" in s.reason and "503" in s.reason
    assert s.betas == {} and s.latest == {}


def test_a_failure_of_the_input_check_becomes_a_failed_section(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def boom(*args: object, **kwargs: object) -> object:
        raise ValueError("returns and factors must be finite")

    monkeypatch.setattr(kalman_hook, "kalman_betas", boom)
    s = _section(_report(dgp_a(rng_for(655), n=520)))
    assert s.status == "failed" and s.reason is not None and "finite" in s.reason


def test_tkb23_no_core_number_changes(monkeypatch: pytest.MonkeyPatch) -> None:
    d = dgp_a(rng_for(656), n=700)
    with_hook = _report(d)

    def absent(ctx: SectionContext) -> None:
        return None

    monkeypatch.setattr(kalman_hook, "build_kalman_betas", absent)
    without = _report(d)
    assert without.kalman_betas is None and with_hook.kalman_betas is not None
    stripped = with_hook.model_copy(update={"kalman_betas": None, "label_text": without.label_text})
    assert stripped == without
    assert stripped.model_dump_json() == without.model_dump_json()  # bitwise, as written


def test_tkb23_downstream_statistics_do_not_import_kalman() -> None:
    for path in sorted(ANALYTICS.glob("*.py")):
        if path.name in ("kalman.py", "__init__.py"):
            continue
        assert "kalman" not in path.read_text(encoding="utf-8").lower(), path.name
