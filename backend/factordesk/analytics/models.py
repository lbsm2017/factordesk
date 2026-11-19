"""The factor models a regression can use (E1): CAPM, FF3, FF5 and FF6.

Each model is a tuple of factor codes in canonical order. FF6 is FF5 plus the Ken French
momentum factor ``mom`` (Fama & French 2018; Carhart 1997 added momentum as a fourth factor).
``mom`` is a long-short spread, so, like the other spreads, it enters the regression as published;
only the subject's return has RF subtracted.

Pure constants; no I/O.
"""

from __future__ import annotations

from typing import Literal

from factordesk.analytics.sample import FACTOR_CODES

ModelName = Literal["capm", "ff3", "ff5", "ff6"]

MODELS: dict[ModelName, tuple[str, ...]] = {
    "capm": ("mkt_rf",),
    "ff3": ("mkt_rf", "smb", "hml"),
    "ff5": FACTOR_CODES,
    "ff6": (*FACTOR_CODES, "mom"),
}
"""Model name -> factor codes, canonical order."""

MODEL_ORDER: tuple[ModelName, ...] = ("capm", "ff3", "ff5", "ff6")
"""Display order: by number of factors. An order of presentation, not a ranking."""

MODEL_LABELS: dict[ModelName, str] = {"capm": "CAPM", "ff3": "FF3", "ff5": "FF5", "ff6": "FF6"}


def model_codes(model: str) -> tuple[str, ...]:
    """The factor codes of ``model``; ``ValueError`` for an unknown name."""
    if model not in MODELS:
        raise ValueError(f"unknown factor model {model!r}; known: {', '.join(MODEL_ORDER)}")
    return MODELS[model]
