"""Kalman-filter (time-varying) betas section.

Spec: ``docs/specs/kalman-betas.md`` (KB8.3 outputs, status values and schema); contract SC2.3.

Placeholder of the schema v3 contract: only ``status``, ``reason`` and ``sample``. The Kalman
feature adds the KB8.3 fields of ``KalmanBetaSeries`` here and its nested models
(``KalmanVintage``, the ``latest`` entry, and ``KalmanRetrospective`` only if the owner ships the
smoothed view) in this file, its label keys (``L-KF``, ``L-KBAND``, ...) to
``KALMAN_SECTION.label_text``, and nothing to ``schema.py``.
"""

from __future__ import annotations

from factordesk.report.base import SectionModel, SectionSpec


class KalmanBetaSeries(SectionModel):
    """Filtered (point-in-time) Kalman betas per date, with model-based bands (KB0.1)."""


KALMAN_SECTION = SectionSpec(report_field="kalman_betas", model=KalmanBetaSeries)
