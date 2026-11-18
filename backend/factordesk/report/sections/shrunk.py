"""Shrunk (Bayesian) betas section.

Spec: ``docs/specs/shrunk-betas.md`` (SB7.2 schema, SB7.1 status values); contract SC2.4.

The report field ``shrunk_betas`` holds a list: one ``ShrunkBetas`` per scope, ``full_sample``
then ``latest_window`` (SD7). Placeholder of the schema v3 contract: only ``status``, ``reason``
and ``sample``. The shrunk-betas feature adds the SB7.2 fields here and its nested models
(``ShrinkagePrior``, ``DatasetStamp``, ``ShrunkBeta``, ``PowerStatement``) in this file, its label
keys (``L-SHRINK``, ``L-SHRINK-PRIOR``, ``L-CRED``, ``L-CORR-MOVE``, ``L-MDE``) to
``SHRUNK_SECTION.label_text``, and nothing to ``schema.py``.
"""

from __future__ import annotations

from factordesk.report.base import SectionModel, SectionSpec


class ShrunkBetas(SectionModel):
    """OLS betas pulled toward a stated prior, with a power statement per factor (SB0.1)."""


SHRUNK_SECTION = SectionSpec(report_field="shrunk_betas", model=ShrunkBetas, many=True)
