"""Golden snapshot of the single-ticker report (E0-T1).

Locks today's ticker-mode output so a refactor can prove it stays identical. The report is built
offline by the pure core ``assemble_report`` from a synthetic stock (``make_case(3001, n=720)``),
with the world-beta benchmark input and a USD security so the four hook sections (world beta,
performance, residual alpha, Kalman betas) are filled as in the API. The full ``FactorReport`` is
serialised with ``model_dump_json`` (the serializer of ``dump_report`` and the API) and compared
with the golden file.

Comparison (cross-platform CI): both texts are parsed as JSON and compared node by node. Object
keys (and their order), strings, integers, booleans and nulls must be exactly equal, and the JSON
type of every node must match (an integer never equals a float). Floats must agree within a
relative tolerance of 1e-12 or an absolute tolerance of 1e-15, whichever is larger: the last bits
of a float may differ between BLAS builds and CPUs, while any real change of a statistic, a
rounding rule or a text is far larger. There is no second, looser check to fall back to.

Time-varying fields: none are excluded. ``now`` is passed in, so ``generated_at`` and the data-lag
figures are fixed; ``factors_downloaded_at`` is None. Nothing else in the report reads the clock.

To regenerate the golden file after an intended change, run once with the environment variable
``FACTORDESK_UPDATE_GOLDEN=1`` (e.g. ``FACTORDESK_UPDATE_GOLDEN=1 uv run pytest
backend/factordesk/tests/test_ticker_golden.py``), then review the diff of the golden file.
"""

from __future__ import annotations

import json
import math
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import pytest

from factordesk.data.prices import Security
from factordesk.pipeline import assemble_report
from factordesk.section_hooks.context import SectionInputs, WorldBenchmarkInput
from factordesk.tests.test_world_beta import make_case

GOLDEN = Path(__file__).parent / "fixtures" / "golden" / "ticker_report.json"
NOW = datetime(2026, 11, 18, 15, 0, tzinfo=UTC)
SECURITY = Security(name="Example Corp", currency="USD", exchange="NASDAQ")

REL_TOL = 1e-12
ABS_TOL = 1e-15


def _ticker_report_json() -> str:
    case = make_case(3001, n=720)
    report = assemble_report(
        "STK",
        case.stock,
        case.factors,
        now=NOW,
        factors_downloaded_at=None,
        section_inputs=SectionInputs(world_benchmark=WorldBenchmarkInput(history=case.bench)),
        security=SECURITY,
    )
    return report.model_dump_json() + "\n"


def _kind(value: object) -> str:
    """The JSON type of a parsed node (``bool`` is checked before ``int``, its base class)."""
    if value is None:
        return "null"
    for kind, typ in (("bool", bool), ("int", int), ("float", float), ("string", str)):
        if isinstance(value, typ):
            return kind
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    raise TypeError(f"not a JSON value: {type(value).__name__}")


def json_differences(actual: object, expected: object, path: str = "$") -> list[str]:
    """Every place where ``actual`` and ``expected`` (parsed JSON) differ, as readable lines.

    Exact on structure, keys (in order), strings, integers, booleans and nulls; floats within
    ``max(REL_TOL * max(|a|, |b|), ABS_TOL)``.
    """
    ka, ke = _kind(actual), _kind(expected)
    if ka != ke:
        return [f"{path}: type {ka} != {ke} ({actual!r} vs {expected!r})"]
    if isinstance(actual, dict) and isinstance(expected, dict):
        a_obj = cast(dict[str, object], actual)
        e_obj = cast(dict[str, object], expected)
        if list(a_obj) != list(e_obj):
            return [f"{path}: keys {list(a_obj)} != {list(e_obj)}"]
        out: list[str] = []
        for key, value in e_obj.items():
            out += json_differences(a_obj[key], value, f"{path}.{key}")
        return out
    if isinstance(actual, list) and isinstance(expected, list):
        a_arr = cast(list[object], actual)
        e_arr = cast(list[object], expected)
        if len(a_arr) != len(e_arr):
            return [f"{path}: length {len(a_arr)} != {len(e_arr)}"]
        out = []
        for i, (a, e) in enumerate(zip(a_arr, e_arr, strict=True)):
            out += json_differences(a, e, f"{path}[{i}]")
        return out
    if isinstance(actual, float) and isinstance(expected, float):
        if not (math.isfinite(actual) and math.isfinite(expected)):
            return [] if actual == expected else [f"{path}: {actual!r} != {expected!r}"]
        tol = max(REL_TOL * max(abs(actual), abs(expected)), ABS_TOL)
        if abs(actual - expected) > tol:
            return [f"{path}: {actual!r} != {expected!r} (|diff| {abs(actual - expected):.3e})"]
        return []
    return [] if actual == expected else [f"{path}: {actual!r} != {expected!r}"]


def test_ticker_report_matches_golden() -> None:
    actual = _ticker_report_json()
    if os.environ.get("FACTORDESK_UPDATE_GOLDEN") == "1":
        GOLDEN.parent.mkdir(parents=True, exist_ok=True)
        GOLDEN.write_bytes(actual.encode("utf-8"))
    expected = GOLDEN.read_bytes().decode("utf-8")
    parsed_actual: object = json.loads(actual)
    parsed_expected: object = json.loads(expected)
    differences = json_differences(parsed_actual, parsed_expected)
    assert not differences, f"{len(differences)} difference(s):\n" + "\n".join(differences[:20])


@pytest.mark.parametrize(
    ("actual", "expected", "equal"),
    [
        (1.0, 1.0 + 1e-13, True),
        (1.0, 1.0 + 1e-11, False),
        (0.0, 1e-16, True),
        (0.0, 1e-14, False),
        (1, 1.0, False),
        (True, 1, False),
        ("a", "a", True),
        ("a", "b", False),
        (None, None, True),
        ({"a": 1, "b": 2}, {"b": 2, "a": 1}, False),
        ([1.0, 2.0], [1.0], False),
        ({"x": [0.1, {"y": "z"}]}, {"x": [0.1, {"y": "z"}]}, True),
    ],
)
def test_json_comparison_rules(actual: object, expected: object, equal: bool) -> None:
    assert (not json_differences(actual, expected)) is equal
