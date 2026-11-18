"""Section fixtures of the schema v3 contract (``docs/specs/schema-v3-contract.md`` SC2).

One JSON file per optional section, holding the value of that ``FactorReport`` field: one section
object, or a list of them for ``shrunk_betas``. The contract ships placeholders (status, reason and
sample only, synthetic data). Each feature branch replaces its own file with a synthetic section of
the real shape; nothing else here changes. The frontend reads the same files through
``frontend/src/test/sectionFixtures.ts``.
"""

from __future__ import annotations

import json
from pathlib import Path

from factordesk.report.schema import FactorReport

HERE = Path(__file__).resolve().parent

SECTION_FILES: dict[str, str] = {
    "lead_lag": "lead_lag.json",
    "shrunk_betas": "shrunk.json",
    "fragility": "fragility.json",
    "residual": "residual_alpha.json",
    "kalman_betas": "kalman.json",
}
"""``FactorReport`` field name -> fixture file in this folder."""


def section_payload(report_field: str) -> object:
    """The parsed JSON value of one section fixture."""
    return json.loads((HERE / SECTION_FILES[report_field]).read_text(encoding="utf-8"))


def report_with_section(report: FactorReport, report_field: str) -> FactorReport:
    """``report`` with the fixture of ``report_field`` attached (validated through JSON)."""
    payload = json.loads(report.model_dump_json())
    payload[report_field] = section_payload(report_field)
    return FactorReport.model_validate_json(json.dumps(payload))
