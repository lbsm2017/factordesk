"""Building blocks shared by ``schema.py`` and the optional report sections.

These definitions were moved here unchanged from ``schema.py`` so that the section modules under
``report/sections/`` can use them without importing ``schema.py``, which imports the sections.
``schema.py`` re-exports every public name, so ``from factordesk.report.schema import SampleInfo``
keeps working. The conventions in the ``schema.py`` docstring apply to every model here.

``SectionModel`` and ``SectionSpec`` are the extension points of the schema v3 contract
(``docs/specs/schema-v3-contract.md``, SC1 and SC3.1).
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

FACTOR_NAMES: tuple[str, ...] = ("Mkt-RF", "SMB", "HML", "RMW", "CMA")
"""Canonical Fama-French 5-factor display names and order (ties are broken by this order)."""

Severity = Literal["info", "warning", "error"]
Status = Literal["ok", "insufficient_data", "not_applicable", "failed"]
Tag = Literal["reliable", "noise"]
ExclusionReason = Literal[
    "multi_day_return",
    "no_factor_row",
    "price_missing",
    "factor_missing",
    "lead_after_sample_end",
]
"""Why a row is outside a statistic's sample. ``lead_after_sample_end`` is used only by the
lead-lag section (its next factor day is after the sample end; lead-lag spec LL2.2)."""
LabelKey = Literal["L-DESC", "L-ARITH", "L-BAND", "L-OVERLAP", "L-EXPL", "L-PROXY", "L-VINTAGE"]

LABEL_TEXT: dict[str, str] = {
    "L-DESC": "Descriptive, in-sample, not predictive.",
    "L-ARITH": "Arithmetic contributions (not compounded); they add up exactly.",
    "L-BAND": (
        "Pointwise 95% band. Even with a constant true beta, about 1 point in 20 falls outside."
    ),
    "L-OVERLAP": "Overlapping windows: consecutive values share most of their data.",
    "L-EXPL": "Exploratory long-run link, not a trading signal.",
    "L-PROXY": "Return-based proxy, not a valuation spread.",
    "L-VINTAGE": (
        "Uses the current Fama-French data vintage; historical factor values can be revised."
    ),
}
"""Standard footnote texts, methodology M0.9. Keys are referenced by ``labels`` fields."""


class FrozenModel(BaseModel):
    """Base class: immutable, strict types, unknown keys rejected, NaN/inf rejected."""

    # Fields with a default are always present in a serialised report, so the output schema (and the
    # generated frontend types) lists them as required.
    model_config = ConfigDict(
        frozen=True,
        strict=True,
        extra="forbid",
        allow_inf_nan=False,
        json_schema_serialization_defaults_required=True,
    )


# ------------------------------------------------------------------------------ sample metadata
class ExcludedRow(FrozenModel):
    """One return row left out of the analysis sample, with the reason (M2)."""

    date: date
    reason: ExclusionReason


class FactorVintage(FrozenModel):
    """Which French file the numbers come from (M0.8)."""

    last_date: date = Field(description="Last date in the French factor file.")
    downloaded_at: datetime | None = Field(
        description="UTC time the file was downloaded; None when the factors were injected."
    )


class SampleInfo(FrozenModel):
    """Sample metadata carried by every statistic (M0.8)."""

    n: int = Field(ge=0, description="Rows of the analysis sample used.")
    start: date | None = Field(description="Actual first date used.")
    end: date | None = Field(description="Actual last date used (the stamp of in-sample stats).")
    requested_start: date
    requested_end: date
    window: int | None = Field(description="Trailing-window length in rows, if any.")
    n_excluded: int = Field(ge=0)
    excluded: list[ExcludedRow]
    factor_vintage: FactorVintage

    @model_validator(mode="after")
    def _count_matches(self) -> SampleInfo:
        """``n_excluded`` must equal the number of listed rows."""
        if self.n_excluded != len(self.excluded):
            raise ValueError("n_excluded must equal len(excluded)")
        return self


def iter_floats(value: object, *, skip_nested_status: bool = False) -> Iterator[float]:
    """Every float reachable inside a dumped model (dicts and lists walked recursively).

    With ``skip_nested_status``, a dict below the top level that has its own ``status`` key is not
    entered: such an object is checked against its own status (contract SC6 item 6).
    """
    yield from _walk_floats(value, skip_nested_status, top=True)


def _walk_floats(value: object, skip_nested_status: bool, *, top: bool) -> Iterator[float]:
    if isinstance(value, float):
        yield value
    elif isinstance(value, dict):
        mapping = cast(dict[object, object], value)
        if skip_nested_status and not top and "status" in mapping:
            return
        for v in mapping.values():
            yield from _walk_floats(v, skip_nested_status, top=False)
    elif isinstance(value, list):
        for v in cast(list[object], value):
            yield from _walk_floats(v, skip_nested_status, top=False)


class StatisticModel(FrozenModel):
    """Common fields of every statistic (M14)."""

    status: Status
    reason: str | None = Field(description="Human-readable reason when status is not 'ok'.")
    sample: SampleInfo
    labels: list[LabelKey] = Field(description="Standard footnotes that apply (keys of M0.9).")
    caption: str = Field(description="Section-specific label text (methodology wording).")

    @model_validator(mode="after")
    def _status_consistent(self) -> StatisticModel:
        """``reason`` is required iff not ok; not-ok statistics carry no numbers (M0.7)."""
        if (self.status == "ok") != (self.reason is None):
            raise ValueError("reason must be None exactly when status is 'ok'")
        if self.status != "ok":
            dumped = self.model_dump(exclude={"sample"})
            if any(True for _ in iter_floats(dumped)):
                raise ValueError(f"status {self.status!r} but numeric values are present")
        return self


class ReportWarning(FrozenModel):
    """A report-level warning (short history, collinearity, audit status, data lag, ...)."""

    code: str
    message: str


# ------------------------------------------------------------------ optional sections (contract)
class SectionModel(FrozenModel):
    """Base of every optional report section (schema v3 contract, SC1 item 3).

    Carries the three fields every statistic carries (``CODING_STANDARDS.md`` section 5). A
    section whose status is not ``ok`` holds no float, except inside a nested object that has its
    own ``status`` (that object answers for its own numbers).
    """

    status: Status
    reason: str | None = Field(description="Human-readable reason when status is not 'ok'.")
    sample: SampleInfo

    @model_validator(mode="after")
    def _section_status_consistent(self) -> SectionModel:
        """``reason`` is required iff not ok; a not-ok section carries no numbers of its own."""
        if (self.status == "ok") != (self.reason is None):
            raise ValueError("reason must be None exactly when status is 'ok'")
        if self.status != "ok":
            dumped = self.model_dump(exclude={"sample"})
            if any(True for _ in iter_floats(dumped, skip_nested_status=True)):
                raise ValueError(f"status {self.status!r} but numeric values are present")
        return self


@dataclass(frozen=True)
class SectionSpec:
    """How one optional section plugs into ``FactorReport`` (schema v3 contract, SC3.1).

    Each module under ``report/sections/`` defines exactly one instance; ``schema.SECTIONS``
    collects them.
    """

    report_field: str
    """Name of the ``FactorReport`` field that holds the section (``None`` when not computed)."""
    model: type[SectionModel]
    """The section's model."""
    many: bool = False
    """True when the field holds a list of ``model`` (one entry per scope)."""
    statistic_models: tuple[type[StatisticModel], ...] = ()
    """Nested full statistics of the section; added to ``schema.STATISTIC_MODELS`` (T105)."""
    label_text: Mapping[str, str] = field(default_factory=lambda: dict[str, str]())
    """Footnote keys of this section and their texts (not in ``LABEL_TEXT``)."""
