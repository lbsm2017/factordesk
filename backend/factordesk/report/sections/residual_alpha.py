"""Residual (alpha) analysis section.

Spec: ``docs/methodology-residual-analysis.md`` (R7 schema, R8 panel), oracle
``docs/test-oracle-residual-analysis.md``; contract SC2.5.

Placeholder of the schema v3 contract: only ``status``, ``reason`` and ``sample``. The residual
feature adds the R7.8 container fields here and its nested models (``ResidualStats``,
``ResidualChart``, ``ResidualGap``, ``RollingResidualAlpha``, ``AlphaWindow``,
``NonOverlappingAlpha``, ``SplitHalfAlpha``, ``ResidualYear``, ``ResidualYears``,
``ResidualAlphaDiagnostics``) in this file. R7.7's ``ResidualDiagnostics`` is renamed
``ResidualAlphaDiagnostics`` because ``schema.ResidualDiagnostics`` (M3.5) exists. Its statistic
models go into ``RESIDUAL_ALPHA_SECTION.statistic_models`` and its label keys (``L-INSAMPLE``,
``L-PIT``, ``L-DESC-PIT``, ``L-HEDGE``) into ``RESIDUAL_ALPHA_SECTION.label_text``.
"""

from __future__ import annotations

from factordesk.report.base import SectionModel, SectionSpec


class ResidualAnalysis(SectionModel):
    """Residual return with in-sample and point-in-time betas, gap, stability (R0.1)."""


RESIDUAL_ALPHA_SECTION = SectionSpec(report_field="residual", model=ResidualAnalysis)
