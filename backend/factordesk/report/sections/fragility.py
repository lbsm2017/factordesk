"""Fragility score section: how many trading days a significance call rests on.

Spec: ``docs/specs/fragility-score.md`` (FR9.2 schema, FR9.1 status values); contract SC2.1.

Placeholder of the schema v3 contract: only ``status``, ``reason`` and ``sample``. The fragility
feature adds the FR9.2 fields here and its nested models (``FlipCount``, ``RemovedDay``,
``LoyoTable``, ``LoyoRow``, ``InfluenceLists``, ``InfluentialDay``) in this file, its label key
``L-FRAGILITY`` to ``FRAGILITY_SECTION.label_text``, and nothing to ``schema.py``.
"""

from __future__ import annotations

from factordesk.report.base import SectionModel, SectionSpec


class FragilitySection(SectionModel):
    """Flip counts, leave-one-year-out table and influential days (FR0.1). In-sample, ``T_end``."""


FRAGILITY_SECTION = SectionSpec(report_field="fragility", model=FragilitySection)
