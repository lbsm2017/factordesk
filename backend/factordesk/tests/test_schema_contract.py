"""Schema v3 contract tests (``docs/specs/schema-v3-contract.md`` SC9): optional sections,
version handling, placeholder fixtures, section status rules and the pipeline hooks."""

from __future__ import annotations

import json
import types
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Union, get_args, get_origin

import pytest
from pydantic import ValidationError

from factordesk.pipeline import assemble_report
from factordesk.report import FactorReport, dump_report, load_report, render_report_html
from factordesk.report.base import FrozenModel, SectionModel, SectionSpec, Status
from factordesk.report.schema import (
    LABEL_TEXT,
    SCHEMA_VERSION,
    SECTIONS,
    STATISTIC_MODELS,
    SUPPORTED_SCHEMA_VERSIONS,
    SampleInfo,
    report_label_text,
)
from factordesk.section_hooks import fragility as fragility_hook
from factordesk.section_hooks.context import SectionContext, SectionInputs
from factordesk.tests.fixtures.dgp import dgp_a, rng_for
from factordesk.tests.fixtures.sections import (
    SECTION_FILES,
    report_with_section,
    section_payload,
)

FIXTURES = Path(__file__).parent / "fixtures"
MOCK = FIXTURES / "mock_report.json"
MOCK_V3 = FIXTURES / "mock_report_v3.json"
NOW = datetime(2026, 11, 18, 15, 0, tzinfo=UTC)

SECTION_FIELDS = (
    "world_beta",
    "performance",
    "lead_lag",
    "shrunk_betas",
    "fragility",
    "residual",
    "kalman_betas",
    "tail_risk",
)
"""The eight optional fields, in panel order (contract SC2, SC4; performance and world beta are
additions to the five of the contract, see docs/validation/performance-contract-note-2026-11-18.md
and docs/validation/world-beta-contract-note-2026-11-18.md)."""


def _optional_parts(annotation: Any) -> tuple[Any, ...]:
    """The members of ``X | None`` (both union spellings), without ``None``."""
    assert get_origin(annotation) in (Union, types.UnionType), annotation
    args = get_args(annotation)
    assert type(None) in args, annotation
    return tuple(a for a in args if a is not type(None))


# ----------------------------------------------------------------------------- fields and specs
def test_sections_are_the_eight_optional_fields() -> None:
    assert tuple(spec.report_field for spec in SECTIONS) == SECTION_FIELDS
    for spec in SECTIONS:
        info = FactorReport.model_fields[spec.report_field]
        assert info.default is None and not info.is_required(), spec.report_field
        (member,) = _optional_parts(info.annotation)
        if spec.many:
            assert get_origin(member) is list and get_args(member) == (spec.model,)
        else:
            assert member is spec.model
        assert issubclass(spec.model, SectionModel)
    # They are the last fields, so a version 3 payload is a prefix of the version 4 layout.
    assert tuple(FactorReport.model_fields)[-len(SECTIONS) :] == SECTION_FIELDS


def test_section_models_carry_status_reason_and_sample() -> None:
    for spec in SECTIONS:
        fields = spec.model.model_fields
        assert {"status", "reason", "sample"} <= set(fields), spec.model.__name__
        assert fields["sample"].annotation in (SampleInfo, "SampleInfo")
        assert fields["reason"].is_required()
    core = STATISTIC_MODELS[:8]
    assert [m.__name__ for m in core] == [
        "Regression",
        "RollingWindow",
        "AverageBetaPanel",
        "ReturnContribution",
        "RiskContribution",
        "ResidualDiagnostics",
        "QualityGate",
        "MultiDayRegression",
    ]
    assert STATISTIC_MODELS[8:] == tuple(m for s in SECTIONS for m in s.statistic_models)


def test_section_label_keys_are_unique() -> None:
    seen = set(LABEL_TEXT)
    for spec in SECTIONS:
        for key in spec.label_text:
            assert key.startswith("L-"), key
            assert key not in seen, key
            seen.add(key)


def test_report_label_text_adds_only_present_sections() -> None:
    absent = {spec.report_field: None for spec in SECTIONS}
    assert report_label_text(absent) == LABEL_TEXT
    extra = SectionSpec(
        report_field="fragility", model=SECTIONS[2].model, label_text={"L-TEST": "Test text."}
    )
    assert report_label_text({"fragility": None}, sections=(extra,)) == LABEL_TEXT
    present = report_label_text({"fragility": object()}, sections=(extra,))
    assert present == {**LABEL_TEXT, "L-TEST": "Test text."}


# ----------------------------------------------------------------------------- versions
def test_mock_fixture_is_version_4_with_null_sections() -> None:
    rep = load_report(MOCK)
    assert rep.schema_version == SCHEMA_VERSION == "4"
    assert SUPPORTED_SCHEMA_VERSIONS == ("3", "4")
    for name in SECTION_FIELDS:
        assert getattr(rep, name) is None
    payload = json.loads(MOCK.read_text(encoding="utf-8"))
    for name in SECTION_FIELDS:
        assert name in payload and payload[name] is None


def test_mock_fixture_round_trips(tmp_path: Path) -> None:
    rep = load_report(MOCK)
    out = tmp_path / "r.json"
    dump_report(rep, out)
    assert out.read_bytes() == MOCK.read_bytes()
    assert FactorReport.model_validate_json(rep.model_dump_json()) == rep


def test_version_3_file_still_loads() -> None:
    old = load_report(MOCK_V3)
    payload = json.loads(MOCK_V3.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "3"
    assert not set(SECTION_FIELDS) & set(payload)
    assert old.schema_version == "3"
    for name in SECTION_FIELDS:
        assert getattr(old, name) is None
    # Apart from the version, the old file holds exactly the current mock report.
    current = load_report(MOCK)  # the mock also carries data.security
    stripped = current.data.model_copy(update={"security": None})
    expected = current.model_copy(update={"schema_version": "3", "data": stripped})
    assert old == expected
    assert "schema v3," in render_report_html(old)


@pytest.mark.parametrize("version", ["2", "5", "6", "", "v4"])
def test_unknown_versions_are_refused(version: str) -> None:
    text = MOCK.read_text(encoding="utf-8").replace(
        '"schema_version":"4"', f'"schema_version":"{version}"'
    )
    with pytest.raises(ValidationError, match="supported"):
        FactorReport.model_validate_json(text)


def test_version_3_file_cannot_carry_a_section() -> None:
    payload = json.loads(MOCK_V3.read_text(encoding="utf-8"))
    payload["fragility"] = section_payload("fragility")
    with pytest.raises(ValidationError, match="version 3"):
        FactorReport.model_validate_json(json.dumps(payload))


# ----------------------------------------------------------------------------- placeholder fixtures
def test_every_section_has_a_fixture_that_validates() -> None:
    assert set(SECTION_FILES) == set(SECTION_FIELDS)
    base = load_report(MOCK)
    for spec in SECTIONS:
        rep = report_with_section(base, spec.report_field)
        value = getattr(rep, spec.report_field)
        items = value if spec.many else [value]
        assert items and all(isinstance(v, spec.model) for v in items)
        assert FactorReport.model_validate_json(rep.model_dump_json()) == rep
        # Nothing else changes, except the section's own footnote texts.
        assert rep.label_text == {**base.label_text, **spec.label_text}
        stripped = rep.model_copy(update={spec.report_field: None, "label_text": base.label_text})
        assert stripped == base


def test_label_fixture_equals_the_section_specs() -> None:
    from factordesk.tests.fixtures.sections import section_labels

    for spec in SECTIONS:
        assert section_labels(spec.report_field) == dict(spec.label_text), spec.report_field


# ----------------------------------------------------------------------------- status rules
class _Nested(FrozenModel):
    status: Status
    value: float | None


class _Probe(SectionModel):
    figure: float | None = None
    nested: _Nested | None = None


def _sample() -> SampleInfo:
    return load_report(MOCK).regression.sample


def test_section_status_and_reason_must_agree() -> None:
    _Probe(status="ok", reason=None, sample=_sample(), figure=1.5)
    with pytest.raises(ValidationError, match="reason"):
        _Probe(status="ok", reason="why", sample=_sample())
    with pytest.raises(ValidationError, match="reason"):
        _Probe(status="failed", reason=None, sample=_sample())


def test_not_ok_section_carries_no_number_of_its_own() -> None:
    with pytest.raises(ValidationError, match="numeric"):
        _Probe(status="not_applicable", reason="Not shown.", sample=_sample(), figure=0.1)
    # A nested object with its own status answers for its own numbers (contract SC6 item 6).
    probe = _Probe(
        status="not_applicable",
        reason="Not shown.",
        sample=_sample(),
        nested=_Nested(status="ok", value=0.25),
    )
    assert probe.nested is not None and probe.nested.value == 0.25
    with pytest.raises(ValidationError):
        _Probe(status="ok", reason=None, sample=_sample(), figure=float("nan"))


# ----------------------------------------------------------------------------- pipeline hooks
def _assemble(**kwargs: Any) -> FactorReport:
    d = dgp_a(rng_for(3001), n=600)
    return assemble_report(
        "SYN", d.history, d.factors, now=NOW, factors_downloaded_at=None, **kwargs
    )


BUILT_SECTIONS: tuple[str, ...] = ("performance", "residual", "kalman_betas", "tail_risk")
"""Fields whose feature is built: the offline pipeline fills them. Each feature branch adds its
field.

Shrunk fills only online (from the portfolio files) and world_beta only when the ACWI history
is supplied (``SectionInputs.world_benchmark``, fetched online), so the offline pipeline leaves
both absent. Performance needs only the price history, so the offline pipeline fills it.
"""


def test_pipeline_leaves_unbuilt_sections_absent() -> None:
    rep = _assemble()
    assert rep.schema_version == SCHEMA_VERSION
    for name in SECTION_FIELDS:
        assert (getattr(rep, name) is not None) is (name in BUILT_SECTIONS), name
    present = {name: getattr(rep, name) for name in SECTION_FIELDS}
    assert rep.label_text == report_label_text(present)
    if not BUILT_SECTIONS:
        assert rep.label_text == LABEL_TEXT


def test_hooks_get_the_finished_core_report(monkeypatch: pytest.MonkeyPatch) -> None:
    baseline = _assemble()
    seen: list[SectionContext] = []
    placeholder = report_with_section(load_report(MOCK), "fragility").fragility

    def fake(ctx: SectionContext) -> Any:
        seen.append(ctx)
        return placeholder

    monkeypatch.setattr(fragility_hook, "build_fragility", fake)
    inputs = SectionInputs()
    rep = _assemble(section_inputs=inputs)
    (ctx,) = seen
    assert rep.fragility == placeholder
    assert ctx.inputs is inputs
    assert ctx.core.regression == rep.regression
    assert list(ctx.core.rolling) == rep.rolling
    assert ctx.core.quality_gate == rep.quality_gate
    assert ctx.sample.n == rep.data.n_obs == 600
    assert ctx.sample_info(None) == rep.regression.sample
    assert ctx.sample_info(126).window == 126
    assert ctx.primary_window in ctx.rolling
    # The section is added without touching any core section.
    assert rep.model_copy(update={"fragility": None}) == baseline
