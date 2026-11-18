"""Lead-lag (Dimson, with a Scholes-Williams cross-check) betas section.

Spec: ``docs/specs/lead-lag-betas.md`` (LL6.6 schema, LL6.4 status values); contract SC2.2.

Placeholder of the schema v3 contract: only ``status``, ``reason`` and ``sample``. The lead-lag
feature adds the LL6.6 fields here and its nested models (``LeadLagTrigger``, ``TimingTest``,
``LeadLagBeta``, ``LeadLagAlpha``, ``JointWald``, ``SWCrossCheck``) in this file, its label key
``L-LEADLAG`` to ``LEAD_LAG_SECTION.label_text``, and nothing to ``schema.py``.
"""

from __future__ import annotations

from factordesk.report.base import SectionModel, SectionSpec


class LeadLagSection(SectionModel):
    """Timing-adjusted betas: same-day plus previous- and next-day factor coefficients (LL0.1)."""


LEAD_LAG_SECTION = SectionSpec(report_field="lead_lag", model=LeadLagSection)
