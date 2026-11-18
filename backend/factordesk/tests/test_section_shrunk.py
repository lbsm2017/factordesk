"""Shrunk-betas section: schema, fixture, hook and static panel (spec SB7; contract SC2.4, SC9).

The synthetic fixture ``fixtures/sections/shrunk.json`` is built by ``build_fixture_sections`` here:
rerun ``python -m factordesk.tests.test_section_shrunk`` to rewrite it. ``test_fixture_is_current``
fails when the file and the builder disagree.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from pydantic import ValidationError

from factordesk.analytics.shrinkage import (
    DELTA,
    POWER_ALPHA,
    any_visible_pull,
    posterior,
    power_statements,
)
from factordesk.report import FactorReport
from factordesk.report.base import FACTOR_NAMES, SampleInfo
from factordesk.report.schema import LABEL_TEXT, report_label_text
from factordesk.report.sections.shrunk import (
    LABEL_TEXT as SHRUNK_LABELS,
)
from factordesk.report.sections.shrunk import (
    SHRUNK_SECTION,
    DatasetStamp,
    PowerStatement,
    ShrinkagePrior,
    ShrunkBeta,
    ShrunkBetas,
)
from factordesk.tests.fixtures.sections import SECTION_FILES, report_with_section

FIXTURES = Path(__file__).parent / "fixtures"
MOCK = FIXTURES / "mock_report.json"
TAU = np.array([0.209, 0.764, 0.341, 0.329, 0.254])
M0 = np.array([1.0, 0.0, 0.0, 0.0, 0.0])
FIXTURE_CORR = np.eye(5)
for _i, _j, _c in ((1, 2, 0.5), (1, 3, 0.5), (2, 3, 0.4), (2, 4, 0.5)):
    FIXTURE_CORR[_i, _j] = FIXTURE_CORR[_j, _i] = _c
"""Correlation of the estimates in the latest-window fixture: SMB is estimated jointly with the
strongly pulled HML and RMW, as in the RDDT example (spec SB8.2), so it moves away from 0."""


def validate(payload: dict[str, Any]) -> ShrunkBetas:
    """Validate through JSON text, as the API does (the models are strict about dates)."""
    return ShrunkBetas.model_validate_json(json.dumps(payload))


# ----------------------------------------------------------------------------- the builder
def synthetic_prior() -> ShrinkagePrior:
    return ShrinkagePrior(
        source="reference_ff_portfolios_v1",
        centre=[float(v) for v in M0],
        tau=[float(v) for v in TAU],
        tau_by_cross_section={
            "industry49": [0.209, 0.408, 0.341, 0.281, 0.254],
            "size_char75": [0.063, 0.764, 0.329, 0.329, 0.221],
        },
        n_portfolios={"industry49": 49, "size_char75": 75},
        window_start=date(2016, 9, 21),
        window_end=date(2026, 9, 30),
        window_rows=2520,
        datasets=[
            DatasetStamp(key=key, crsp_stamp="202609", sha256=None, last_modified=None)
            for key in (
                "synthetic_ind49_daily",
                "synthetic_me_bm25_daily",
                "synthetic_me_op25_daily",
                "synthetic_me_inv25_daily",
            )
        ],
        fallback_reason=None,
    )


def make_section(
    sample: SampleInfo,
    scope: str,
    b: list[float],
    se: list[float],
    n: int,
    hac_lags: int,
    window: int | None,
    prior: ShrinkagePrior,
    corr: np.ndarray[Any, Any] | None = None,
) -> ShrunkBetas:
    """An ok section from OLS betas and standard errors (the real analytics, synthetic input)."""
    se_v = np.array(se)
    cov = np.outer(se_v, se_v) * (np.eye(5) if corr is None else corr)
    post = posterior(np.array(b), cov, np.array(prior.centre), np.array(prior.tau))
    power = power_statements(se, n, FACTOR_NAMES)
    labels: list[str] = ["L-DESC", "L-SHRINK", "L-SHRINK-PRIOR", "L-CRED", "L-MDE"]
    if any(post.moved_away):
        labels.append("L-CORR-MOVE")
    return validate(
        {
            "status": "ok",
            "reason": None,
            "sample": sample.model_copy(update={"window": window}).model_dump(mode="json"),
            "scope": scope,
            "window": window,
            "hac_lags": hac_lags,
            "prior": prior.model_dump(mode="json"),
            "betas": [
                {
                    "factor": FACTOR_NAMES[j],
                    "beta_ols": b[j],
                    "se_hac": se[j],
                    "beta_shrunk": float(post.b_post[j]),
                    "sd_post": float(post.sd_post[j]),
                    "cred95_low": float(post.cred_low[j]),
                    "cred95_high": float(post.cred_high[j]),
                    "pull": float(post.pull[j]),
                    "moved_away": post.moved_away[j],
                }
                for j in range(5)
            ],
            "power": [
                {
                    "factor": p.factor,
                    "mde80": p.mde80,
                    "alpha_level": POWER_ALPHA,
                    "delta": DELTA,
                    "extra_years_to_detect_delta": p.extra_years,
                    "text": p.text,
                }
                for p in power
            ],
            "labels": labels,
        }
    )


def build_fixture_sections(sample: SampleInfo) -> list[ShrunkBetas]:
    """Synthetic fixture: a long sample with no visible pull, then a short window with large pulls.

    The first entry uses standard errors like SPY's full-sample ones (spec SB8.1), the second like
    RDDT's (SB8.2). The dataset keys start with ``synthetic_``: no real portfolio data is shipped.
    """
    prior = synthetic_prior()
    full = make_section(
        sample,
        "full_sample",
        [1.0093, -0.1476, 0.0071, 0.0878, 0.0607],
        [0.0066, 0.0062, 0.0087, 0.0094, 0.0112],
        n=sample.n,
        hac_lags=6,
        window=None,
        prior=prior,
    )
    latest = make_section(
        sample,
        "latest_window",
        [1.484, 0.309, -1.015, -0.828, -0.155],
        [0.222, 0.263, 0.292, 0.358, 0.543],
        n=252,
        hac_lags=4,
        window=252,
        prior=prior,
        corr=FIXTURE_CORR,
    )
    return [full, latest]


def fixture_text(sample: SampleInfo) -> str:
    sections = build_fixture_sections(sample)
    return "[" + ",".join(s.model_dump_json() for s in sections) + "]"


def mock_sample() -> SampleInfo:
    payload = json.loads(MOCK.read_text(encoding="utf-8"))
    return SampleInfo.model_validate_json(json.dumps(payload["regression"]["sample"]))


def write_fixture() -> None:
    path = FIXTURES / "sections" / SECTION_FILES["shrunk_betas"]
    path.write_text(fixture_text(mock_sample()), encoding="utf-8", newline="\n")


def mock_report() -> FactorReport:
    return FactorReport.model_validate_json(MOCK.read_text(encoding="utf-8"))


def fixture_sections() -> list[ShrunkBetas]:
    return report_with_section(mock_report(), "shrunk_betas").shrunk_betas or []


# ---------------------------------------------------------------------------------------- schema
def test_fixture_is_current() -> None:
    on_disk = (FIXTURES / "sections" / SECTION_FILES["shrunk_betas"]).read_text(encoding="utf-8")
    assert on_disk == fixture_text(mock_sample())


def test_fixture_validates_round_trips_and_has_both_scopes() -> None:
    report = report_with_section(mock_report(), "shrunk_betas")
    assert report.shrunk_betas is not None
    assert [s.scope for s in report.shrunk_betas] == ["full_sample", "latest_window"]
    assert [s.window for s in report.shrunk_betas] == [None, 252]
    again = FactorReport.model_validate_json(report.model_dump_json())
    assert again == report
    json.loads(report.model_dump_json())  # strict JSON, no NaN or infinity
    for section in report.shrunk_betas:
        assert [b.factor for b in section.betas] == list(FACTOR_NAMES)
        assert [p.factor for p in section.power] == list(FACTOR_NAMES)
        assert section.prior is not None and section.prior.source == "reference_ff_portfolios_v1"
        assert all(d.key.startswith("synthetic_") for d in section.prior.datasets)


def test_fixture_shows_both_display_states() -> None:
    full, latest = fixture_sections()
    assert not any_visible_pull([b.pull for b in full.betas if b.pull is not None])
    assert any_visible_pull([b.pull for b in latest.betas if b.pull is not None])
    assert [b.factor for b in latest.betas if b.moved_away] == ["SMB"]
    assert "L-CORR-MOVE" in latest.labels and "L-CORR-MOVE" not in full.labels


def test_section_spec_is_registered_with_its_labels() -> None:
    assert SHRUNK_SECTION.report_field == "shrunk_betas" and SHRUNK_SECTION.many
    assert SHRUNK_SECTION.model is ShrunkBetas
    assert set(SHRUNK_LABELS) == {"L-SHRINK", "L-SHRINK-PRIOR", "L-CRED", "L-CORR-MOVE", "L-MDE"}
    assert not set(SHRUNK_LABELS) & set(LABEL_TEXT)
    assert set(SHRUNK_LABELS) <= set(report_label_text({"shrunk_betas": [object()]}))
    assert set(SHRUNK_LABELS).isdisjoint(report_label_text({"shrunk_betas": None}))
    assert "Mkt-RF 1, others 0" in SHRUNK_LABELS["L-SHRINK"]


def _ok(**changes: Any) -> dict[str, Any]:
    section = json.loads(fixture_sections()[0].model_dump_json())
    section.update(changes)
    return section


def _not_ok(status: str, reason: str) -> dict[str, Any]:
    return _ok(status=status, reason=reason, prior=None, betas=[], power=[])


@pytest.mark.parametrize("status", ["insufficient_data", "failed", "not_applicable"])
def test_not_ok_section_carries_no_numbers(status: str) -> None:
    section = validate(_not_ok(status, "a reason"))
    assert section.prior is None and section.betas == [] and section.power == []
    assert section.status == status


def test_status_rules() -> None:
    with pytest.raises(ValidationError, match="reason"):
        validate(_ok(reason="why"))
    with pytest.raises(ValidationError, match="reason"):
        validate(_not_ok("failed", "x") | {"reason": None})
    with pytest.raises(ValidationError, match="numeric values"):
        validate(_ok(status="failed", reason="x"))
    with pytest.raises(ValidationError, match="needs its prior"):
        validate(_ok(prior=None))
    with pytest.raises(ValidationError, match="canonical order"):
        validate(_ok(betas=_ok()["betas"][:4]))
    with pytest.raises(ValidationError, match="canonical order"):
        validate(_ok(power=list(reversed(_ok()["power"]))))


def test_scope_and_window_go_together() -> None:
    with pytest.raises(ValidationError, match="window is set"):
        validate(_ok(scope="latest_window", window=None))
    with pytest.raises(ValidationError, match="window is set"):
        validate(_ok(scope="full_sample", window=252))
    with pytest.raises(ValidationError):
        validate(_ok(scope="rolling"))


def test_ok_section_fills_every_shrunk_value() -> None:
    betas = _ok()["betas"]
    betas[2]["pull"] = None
    with pytest.raises(ValidationError, match="fills every shrunk value"):
        validate(_ok(betas=betas))


def test_strictness_nan_codes_and_unknown_keys() -> None:
    betas = _ok()["betas"]
    betas[0]["beta_ols"] = float("nan")
    with pytest.raises(ValidationError):
        validate(_ok(betas=betas))
    betas = _ok()["betas"]
    betas[0]["factor"] = "mkt_rf"  # codes stay inside the backend (contract SC1 item 6)
    with pytest.raises(ValidationError):
        validate(_ok(betas=betas))
    with pytest.raises(ValidationError):
        validate(_ok(extra_field=1))
    with pytest.raises(ValidationError):
        validate(_ok(labels=["L-NOPE"]))
    prior = _ok()["prior"]
    prior["tau"][1] = 0.0
    with pytest.raises(ValidationError, match="positive"):
        ShrinkagePrior.model_validate_json(json.dumps(prior))
    prior = _ok()["prior"]
    prior["centre"] = prior["centre"][:4]
    with pytest.raises(ValidationError, match="one value per factor"):
        ShrinkagePrior.model_validate_json(json.dumps(prior))


def test_nested_models_have_the_spec_fields() -> None:
    assert set(ShrunkBeta.model_fields) == {
        "factor", "beta_ols", "se_hac", "beta_shrunk", "sd_post", "cred95_low", "cred95_high",
        "pull", "moved_away",
    }  # fmt: skip
    assert set(PowerStatement.model_fields) == {
        "factor", "mde80", "alpha_level", "delta", "extra_years_to_detect_delta", "text",
    }  # fmt: skip
    assert set(ShrinkagePrior.model_fields) == {
        "source", "centre", "tau", "tau_by_cross_section", "n_portfolios", "window_start",
        "window_end", "window_rows", "datasets", "fallback_reason",
    }  # fmt: skip
    assert set(DatasetStamp.model_fields) == {"key", "crsp_stamp", "sha256", "last_modified"}
    assert set(ShrunkBetas.model_fields) == {
        "status", "reason", "sample", "scope", "window", "hac_lags", "prior", "betas", "power",
        "labels",
    }  # fmt: skip


def test_version_3_reports_cannot_hold_the_section() -> None:
    payload = json.loads(MOCK.read_text(encoding="utf-8"))
    payload["schema_version"] = "3"
    payload["shrunk_betas"] = [json.loads(s.model_dump_json()) for s in fixture_sections()]
    with pytest.raises(ValidationError, match="version 3"):
        FactorReport.model_validate_json(json.dumps(payload))


if __name__ == "__main__":
    write_fixture()
