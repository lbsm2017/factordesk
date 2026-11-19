"""Golden snapshot of the single-ticker report (E0-T1).

Locks today's ticker-mode output so a refactor can prove it stays byte-identical. The report is
built offline by the pure core ``assemble_report`` from a synthetic stock (``make_case(3001,
n=720)``), with the world-beta benchmark input and a USD security so the four hook sections
(world beta, performance, residual alpha, Kalman betas) are filled as in the API. The full
``FactorReport`` is serialised with ``model_dump_json`` (the serializer of ``dump_report`` and
the API) and compared as exact text with the golden file.

Time-varying fields: none are excluded. ``now`` is passed in, so ``generated_at`` and the data-lag
figures are fixed; ``factors_downloaded_at`` is None. Nothing else in the report reads the clock.

To regenerate the golden file after an intended change, run once with the environment variable
``FACTORDESK_UPDATE_GOLDEN=1`` (e.g. ``FACTORDESK_UPDATE_GOLDEN=1 uv run pytest
backend/factordesk/tests/test_ticker_golden.py``), then review the diff of the golden file.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path

from factordesk.data.prices import Security
from factordesk.pipeline import assemble_report
from factordesk.section_hooks.context import SectionInputs, WorldBenchmarkInput
from factordesk.tests.test_world_beta import make_case

GOLDEN = Path(__file__).parent / "fixtures" / "golden" / "ticker_report.json"
NOW = datetime(2026, 11, 18, 15, 0, tzinfo=UTC)
SECURITY = Security(name="Example Corp", currency="USD", exchange="NASDAQ")


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


def test_ticker_report_matches_golden() -> None:
    actual = _ticker_report_json()
    if os.environ.get("FACTORDESK_UPDATE_GOLDEN") == "1":
        GOLDEN.parent.mkdir(parents=True, exist_ok=True)
        GOLDEN.write_bytes(actual.encode("utf-8"))
    expected = GOLDEN.read_bytes().decode("utf-8")
    assert actual == expected
