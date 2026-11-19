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

LABEL_FILE = "label_text.json"
"""Footnote texts of each section (``{report_field: {key: text}}``), the texts the pipeline adds to
``FactorReport.label_text`` when that section is present. A test keeps it equal to the section
specs; the frontend reads the same file."""

SECTION_FILES: dict[str, str] = {
    "performance": "performance.json",
    "lead_lag": "lead_lag.json",
    "shrunk_betas": "shrunk.json",
    "fragility": "fragility.json",
    "world_beta": "world_beta.json",
    "residual": "residual_alpha.json",
    "kalman_betas": "kalman.json",
    "tail_risk": "tail_risk.json",
}
"""``FactorReport`` field name -> fixture file in this folder."""


def section_payload(report_field: str) -> object:
    """The parsed JSON value of one section fixture."""
    return json.loads((HERE / SECTION_FILES[report_field]).read_text(encoding="utf-8"))


def section_labels(report_field: str) -> dict[str, str]:
    """The footnote texts a report gets when ``report_field`` is present."""
    labels = json.loads((HERE / LABEL_FILE).read_text(encoding="utf-8"))
    return dict(labels.get(report_field, {}))


def report_with_section(report: FactorReport, report_field: str) -> FactorReport:
    """``report`` with the fixture of ``report_field`` attached (validated through JSON).

    ``label_text`` gains the section's footnote texts, as in a pipeline report (SC1 item 5).
    """
    payload = json.loads(report.model_dump_json())
    payload[report_field] = section_payload(report_field)
    payload["label_text"] = {**payload["label_text"], **section_labels(report_field)}
    return FactorReport.model_validate_json(json.dumps(payload))
