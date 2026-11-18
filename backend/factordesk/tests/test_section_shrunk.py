"""Shrunk-betas section: schema, fixture, hook and static panel (spec SB7; contract SC2.4, SC9).

The synthetic fixture ``fixtures/sections/shrunk.json`` is built by ``build_fixture_sections`` here:
rerun ``python -m factordesk.tests.test_section_shrunk`` to rewrite it. ``test_fixture_is_current``
fails when the file and the builder disagree.
"""

from __future__ import annotations

import ast
import dataclasses
import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest
from pydantic import ValidationError

from factordesk.analytics.shrinkage import (
    DELTA,
    POWER_ALPHA,
    any_visible_pull,
    posterior,
    power_statements,
)
from factordesk.analytics.shrinkage_prior import PriorEstimate, estimate_prior
from factordesk.data.portfolios import PortfolioError
from factordesk.pipeline import assemble_report
from factordesk.report import FactorReport
from factordesk.report.base import FACTOR_NAMES, SampleInfo, iter_floats
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
from factordesk.section_hooks import load_section_inputs
from factordesk.section_hooks import shrunk as shrunk_hook
from factordesk.section_hooks.context import SectionContext, SectionInputs
from factordesk.section_hooks.shrunk import NEEDED_KEYS, vintage_problem
from factordesk.tests.fixtures.dgp import dgp_a
from factordesk.tests.fixtures.sections import SECTION_FILES, report_with_section
from factordesk.tests.test_api_report import make_world, serve

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


# ------------------------------------------------------------------------------- hook (SB7.1)
NOW = datetime(2026, 11, 18, 15, 0, tzinfo=UTC)
TAU_TRUE = np.array([0.2, 0.5, 0.3, 0.3, 0.25])


def make_portfolios(
    factor_frame: pd.DataFrame,
    rng: np.random.Generator,
    *,
    per_file: tuple[int, int, int, int] = (50, 15, 15, 15),
    stamp: str | None = "202609",
) -> dict[str, pd.DataFrame]:
    """Synthetic portfolio frames on the dates of ``factor_frame`` (decimals, vintage in attrs)."""
    f = factor_frame.loc[:, list(FACTOR_NAMES)].to_numpy()
    rf = factor_frame["RF"].to_numpy()
    out: dict[str, pd.DataFrame] = {}
    for key, count in zip(NEEDED_KEYS, per_file, strict=True):
        beta = M0 + TAU_TRUE * rng.standard_normal((count, 5))
        e = rng.normal(0.0, 0.004, size=(len(f), count))
        frame = pd.DataFrame(
            rf[:, None] + f @ beta.T + e,
            index=factor_frame.index,
            columns=[f"{key}_{i}" for i in range(count)],
        )
        frame.attrs = {"key": key, "crsp_stamp": stamp, "sha256": "ab" * 32, "last_modified": "x"}
        out[key] = frame
    return out


@dataclass
class Run:
    report: FactorReport
    baseline: FactorReport
    ctx: SectionContext
    portfolios: dict[str, pd.DataFrame]


def run_report(
    portfolios: Mapping[str, pd.DataFrame] | None = None,
    *,
    n: int = 2520,
    seed: int = 701,
    primary_window: int = 252,
    tweak_ctx: Callable[[SectionContext], SectionContext] | None = None,
) -> Run:
    """A DGP-A report with and without the portfolio inputs, and the context the hook saw."""
    d = dgp_a(np.random.default_rng(20261118 + seed), n=n)
    rng = np.random.default_rng(20261118 + seed + 1)
    pf = make_portfolios(d.factors, rng) if portfolios is None else dict(portfolios)
    seen: list[SectionContext] = []
    original = shrunk_hook.build_shrunk_betas

    def spy(ctx: SectionContext) -> list[ShrunkBetas] | None:
        seen.append(ctx)
        return original(tweak_ctx(ctx) if tweak_ctx is not None else ctx)

    kwargs: dict[str, Any] = {
        "now": NOW,
        "factors_downloaded_at": None,
        "primary_window": primary_window,
    }
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(shrunk_hook, "build_shrunk_betas", spy)
        report = assemble_report(
            "SYN",
            d.history,
            d.factors,
            section_inputs=SectionInputs(shrinkage_portfolios=pf),
            **kwargs,
        )
        baseline = assemble_report("SYN", d.history, d.factors, **kwargs)
    return Run(report, baseline, seen[0], pf)


@pytest.fixture(scope="module")
def run() -> Run:
    return run_report()


def test_no_inputs_means_the_feature_did_not_run(run: Run) -> None:
    assert run.baseline.shrunk_betas is None
    assert set(SHRUNK_LABELS).isdisjoint(run.baseline.label_text)


def test_two_scopes_built_from_the_reported_regressions(run: Run) -> None:
    sections = run.report.shrunk_betas
    assert sections is not None and [s.scope for s in sections] == ["full_sample", "latest_window"]
    full, latest = sections
    assert full.status == latest.status == "ok" and full.reason is None
    reg = run.report.regression
    # full sample: the OLS betas and HAC se of M3, and its lag rule L(n)
    assert [b.beta_ols for b in full.betas] == [f.beta for f in reg.factors]
    assert [b.se_hac for b in full.betas] == [f.se for f in reg.factors]
    assert full.hac_lags == reg.hac_lags == 8 and full.window is None
    assert full.sample.window is None and full.sample.n == 2520
    # latest window: the last stamp of the primary rolling window, L(W)
    roll = next(r for r in run.report.rolling if r.window == 252)
    assert latest.window == 252 and latest.hac_lags == roll.hac_lags == 4
    assert latest.sample.window == 252
    for b in latest.betas:
        last_beta = roll.betas[b.factor][-1]
        last_se = roll.se[b.factor][-1]
        assert last_beta is not None and last_se is not None
        assert b.beta_ols == pytest.approx(last_beta, rel=1e-5, abs=1e-6)  # rolling is 6 digits
        assert b.se_hac == pytest.approx(last_se, rel=1e-5)
    for section in sections:
        assert section.prior is not None
        for b in section.betas:
            assert b.cred95_low is not None and b.cred95_high is not None
            assert b.beta_shrunk is not None and b.sd_post is not None and b.pull is not None
            assert b.cred95_low < b.beta_shrunk < b.cred95_high
            half = (b.cred95_high - b.cred95_low) / 2
            assert half == pytest.approx(1.959964 * b.sd_post, rel=1e-6)
            assert b.sd_post <= b.se_hac * (1 + 1e-9)  # the prior only adds information
        assert [p.factor for p in section.power] == list(FACTOR_NAMES)
        assert section.power[0].extra_years_to_detect_delta is None
        assert all(p.alpha_level == 0.01 and p.delta == 0.05 for p in section.power)
    # the shorter sample is the noisier one, so it is pulled more
    assert max(b.pull or 0 for b in latest.betas) > max(b.pull or 0 for b in full.betas)


def test_prior_in_the_section_is_the_one_estimated_from_the_inputs(run: Run) -> None:
    assert run.report.shrunk_betas is not None
    prior = run.report.shrunk_betas[0].prior
    assert prior is not None
    assert run.report.shrunk_betas[1].prior == prior
    est = estimate_prior(run.ctx.factor_frame, run.portfolios, run.ctx.sample.end)
    assert isinstance(est, PriorEstimate)
    assert prior.tau == [float(v) for v in est.tau]
    assert prior.centre == [1.0, 0.0, 0.0, 0.0, 0.0]
    assert prior.n_portfolios == {"industry49": 50, "size_char75": 45}
    assert prior.window_end == run.ctx.sample.end and prior.window_rows == 2520
    assert [d.key for d in prior.datasets] == list(NEEDED_KEYS)
    assert {d.crsp_stamp for d in prior.datasets} == {"202609"}
    assert prior.datasets[0].sha256 == "ab" * 32
    assert prior.fallback_reason is None


def test_posterior_in_the_section_matches_a_hand_recomputation(run: Run) -> None:
    assert run.report.shrunk_betas is not None
    full = run.report.shrunk_betas[0]
    assert full.prior is not None
    v = run.ctx.regression.fit.cov[1:, 1:]
    b = run.ctx.regression.fit.params[1:]
    tau2 = np.array(full.prior.tau) ** 2
    v_post = np.linalg.inv(np.linalg.inv(v) + np.diag(1 / tau2))
    b_post = v_post @ (np.linalg.inv(v) @ b + np.array(full.prior.centre) / tau2)
    weight = v_post @ np.diag(1 / tau2)
    for j, beta in enumerate(full.betas):
        assert beta.beta_shrunk == pytest.approx(float(b_post[j]), abs=1e-10)
        assert beta.sd_post == pytest.approx(float(np.sqrt(v_post[j, j])), rel=1e-9)
        assert beta.pull == pytest.approx(float(weight[j, j]), abs=1e-10)


def test_tsb18_ols_numbers_and_tags_are_untouched(run: Run) -> None:
    skip = {"shrunk_betas", "label_text"}
    assert run.report.model_dump(exclude=skip) == run.baseline.model_dump(exclude=skip)
    assert run.report.model_dump_json(exclude=skip) == run.baseline.model_dump_json(exclude=skip)
    assert [f.tag for f in run.report.regression.factors] == [
        f.tag for f in run.baseline.regression.factors
    ]
    assert set(run.baseline.label_text) < set(run.report.label_text)
    assert set(run.report.label_text) - set(run.baseline.label_text) == set(SHRUNK_LABELS)


def test_tsb18_nothing_outside_the_feature_imports_shrinkage() -> None:
    root = Path(__file__).resolve().parents[1]
    own = {
        "analytics/shrinkage.py",
        "analytics/shrinkage_prior.py",
        "section_hooks/shrunk.py",
        "report/sections/shrunk.py",
        "report/panels/shrunk.py",
    }
    offenders: list[str] = []
    for path in root.rglob("*.py"):
        rel = path.relative_to(root).as_posix()
        if rel.startswith("tests/") or rel in own:
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            names: list[str] = []
            if isinstance(node, ast.ImportFrom):
                names = [node.module or "", *(a.name for a in node.names)]
            elif isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            if any(n.rsplit(".", 1)[-1] in ("shrinkage", "shrinkage_prior") for n in names):
                offenders.append(rel)
    assert offenders == []
    for rel in ("analytics/attribution.py", "analytics/regression.py", "analytics/rolling.py"):
        assert "shrinkage" not in (root / rel).read_text(encoding="utf-8")


def test_payload_has_no_nan_or_infinity(run: Run) -> None:
    json.dumps(json.loads(run.report.model_dump_json()), allow_nan=False)
    FactorReport.model_validate_json(run.report.model_dump_json())


# ---- statuses (SB7.1, TSB19)
def _sections(result: Run) -> list[ShrunkBetas]:
    assert result.report.shrunk_betas is not None
    return result.report.shrunk_betas


def _assert_null_numbers(section: ShrunkBetas) -> None:
    assert section.prior is None and section.betas == [] and section.power == []
    dumped = section.model_dump(mode="json", exclude={"sample"})
    assert not any(True for _ in iter_floats(dumped))


def _unchanged(result: Run) -> bool:
    skip = {"shrunk_betas", "label_text"}
    return result.report.model_dump(exclude=skip) == result.baseline.model_dump(exclude=skip)


def test_tsb19_missing_portfolio_file_is_prior_unavailable() -> None:
    d = dgp_a(np.random.default_rng(20261118 + 702), n=2520)
    pf = make_portfolios(d.factors, np.random.default_rng(1))
    del pf["me_op25_daily"]
    result = run_report(pf, seed=702)
    for section in _sections(result):
        assert section.status == "failed"
        assert "prior_unavailable" in (section.reason or "")
        assert "me_op25_daily" in (section.reason or "")
        _assert_null_numbers(section)
    assert _sections(result)[0].hac_lags == 8 and _sections(result)[1].hac_lags == 4
    assert _unchanged(result)  # the rest of the report is unaffected
    assert all(s.status == "failed" for s in _sections(run_report({}, seed=702)))


def test_tsb19_vintage_mismatch_by_stamp_and_by_last_date() -> None:
    d = dgp_a(np.random.default_rng(20261118 + 703), n=2520)
    pf = make_portfolios(d.factors, np.random.default_rng(2))
    pf["ind49_daily"].attrs["crsp_stamp"] = "202608"
    stamped = _sections(run_report(pf, seed=703))
    for s in stamped:
        assert s.status == "failed" and "prior_vintage_mismatch" in (s.reason or "")
    assert "202608" in (stamped[0].reason or "")
    _assert_null_numbers(stamped[0])

    pf = make_portfolios(d.factors, np.random.default_rng(2))
    pf["me_inv25_daily"] = pf["me_inv25_daily"].iloc[:-1]
    late = _sections(run_report(pf, seed=703))
    for s in late:
        assert s.status == "failed" and "prior_vintage_mismatch" in (s.reason or "")
    assert "me_inv25_daily" in (late[0].reason or "")


def test_vintage_problem_unit_cases() -> None:
    d = dgp_a(np.random.default_rng(5), n=600)
    pf = make_portfolios(d.factors, np.random.default_rng(5))
    assert vintage_problem(pf, d.factors) is None
    factors = d.factors.copy()
    factors.attrs["crsp_stamp"] = "202609"
    assert vintage_problem(pf, factors) is None
    factors.attrs["crsp_stamp"] = "202610"
    assert "different CRSP releases" in (vintage_problem(pf, factors) or "")
    unstamped = make_portfolios(d.factors, np.random.default_rng(5), stamp=None)
    assert vintage_problem(unstamped, d.factors) is None  # last dates still agree


def test_tsb19_too_few_portfolios_is_insufficient_data() -> None:
    d = dgp_a(np.random.default_rng(20261118 + 704), n=2520)
    pf = make_portfolios(d.factors, np.random.default_rng(3), per_file=(39, 15, 15, 15))
    sections = _sections(run_report(pf, seed=704))
    assert all(s.status == "insufficient_data" for s in sections)
    assert all("prior_cross_section_too_small" in (s.reason or "") for s in sections)
    _assert_null_numbers(sections[0])


def test_short_factor_window_is_insufficient_data() -> None:
    sections = _sections(run_report(n=2200, seed=705))
    assert all(s.status == "insufficient_data" for s in sections)
    assert "prior_cross_section_too_small" in (sections[0].reason or "")


def test_singular_covariance_is_failed() -> None:
    result = run_report(seed=706)
    fit = result.ctx.regression.fit
    cov = fit.cov.copy()
    cov[1:, 1:] = np.ones((5, 5)) * 1e-4 + np.eye(5) * 1e-30
    est = estimate_prior(result.ctx.factor_frame, result.portfolios, result.ctx.sample.end)
    assert isinstance(est, PriorEstimate)
    section = shrunk_hook._section(  # pyright: ignore[reportPrivateUsage]
        "full_sample",
        None,
        dataclasses.replace(fit, cov=cov),
        shrunk_hook._prior_model(est, result.portfolios),  # pyright: ignore[reportPrivateUsage]
        est,
        result.ctx.sample_info(None),
    )
    assert section.status == "failed" and "singular_covariance" in (section.reason or "")
    _assert_null_numbers(section)


def test_statuses_are_inherited_from_the_underlying_regression() -> None:
    def broken(ctx: SectionContext) -> SectionContext:
        bad_reg = ctx.core.regression.model_copy(
            update={"status": "insufficient_data", "reason": "too short"}
        )
        bad_roll = [
            r.model_copy(update={"status": "failed", "reason": "singular windows"})
            if r.window == ctx.primary_window
            else r
            for r in ctx.core.rolling
        ]
        return dataclasses.replace(
            ctx, core=dataclasses.replace(ctx.core, regression=bad_reg, rolling=bad_roll)
        )

    sections = _sections(run_report(seed=707, tweak_ctx=broken))
    assert [(s.status, s.reason) for s in sections] == [
        ("insufficient_data", "too short"),
        ("failed", "singular windows"),
    ]
    assert all(s.prior is None and s.betas == [] for s in sections)


def test_window_longer_than_the_sample_is_insufficient_for_the_latest_window() -> None:
    full, latest = _sections(run_report(n=2520, seed=708, primary_window=3000))
    assert full.status == "ok"
    assert latest.status == "insufficient_data" and "3000" in (latest.reason or "")
    assert latest.window == 3000


def test_the_hook_does_not_mutate_the_context_or_the_inputs() -> None:
    result = run_report(seed=709)
    before = {k: v.copy() for k, v in result.portfolios.items()}
    factors_before = result.ctx.factor_frame.copy()
    shrunk_hook.build_shrunk_betas(result.ctx)
    for key, frame in before.items():
        pd.testing.assert_frame_equal(result.portfolios[key], frame)
        assert result.portfolios[key].attrs == frame.attrs
    pd.testing.assert_frame_equal(result.ctx.factor_frame, factors_before)


# ---- loader and dashboard wiring
def test_offline_loader_fetches_nothing(tmp_path: Path) -> None:
    def boom(url: str) -> tuple[bytes, str | None]:
        raise AssertionError("an offline load must not download")

    assert (
        shrunk_hook.load_shrinkage_inputs(NOW, offline=True, data_dir=tmp_path, fetch=boom) is None
    )
    assert load_section_inputs(NOW, offline=True).shrinkage_portfolios is None
    assert not (tmp_path / "portfolios").exists()


def test_online_loader_with_nothing_available_returns_an_empty_mapping(tmp_path: Path) -> None:
    def refuse(url: str) -> tuple[bytes, str | None]:
        raise PortfolioError("offline")

    got = shrunk_hook.load_shrinkage_inputs(NOW, offline=False, data_dir=tmp_path, fetch=refuse)
    assert got == {}  # the hook then reports prior_unavailable


def test_dashboard_passes_the_section_inputs_to_the_report(tmp_path: Path) -> None:
    world = make_world(tmp_path, n=2600, cut=30, test_number=451)
    pf = make_portfolios(world.factors.frame, np.random.default_rng(4))
    calls: list[datetime] = []

    def loader(now: datetime) -> SectionInputs:
        calls.append(now)
        return SectionInputs(shrinkage_portfolios=pf)

    world.service.deps = dataclasses.replace(world.service.deps, load_section_inputs=loader)
    with serve(world.app) as client:
        first = client.get("/api/report/SYN")
        second = client.get("/api/report/SYN?range=5Y")
    assert first.status_code == 200, first.text
    sections = first.json()["shrunk_betas"]
    assert [s["scope"] for s in sections] == ["full_sample", "latest_window"]
    assert sections[0]["status"] == "ok"
    assert second.status_code == 200 and second.json()["shrunk_betas"][0]["status"] == "ok"
    assert len(calls) == 1  # loaded once per vintage and day, shared by both reports


def test_dashboard_without_a_loader_leaves_the_section_null(tmp_path: Path) -> None:
    world = make_world(tmp_path, test_number=452)
    with serve(world.app) as client:
        body = client.get("/api/report/SYN").json()
    assert body["shrunk_betas"] is None


if __name__ == "__main__":
    write_fixture()
