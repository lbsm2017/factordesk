"""Rounding rules shared by the analytics and the report, so one number prints one way."""

from __future__ import annotations

import math

HALF_TOLERANCE = 1e-9
"""A ratio within this of a half point counts as the half point (``0.4749999999999999``)."""


def round_to_five_points(ratio: float) -> int:
    """The magnitude of ``ratio`` in percent, to the nearest 5 points, halves away from zero.

    12.5% gives 15, 37.5% gives 40. The sign is not part of the result: the caller decides how to
    print it. A ratio a hair below a half point in binary (``0.475 * a / a``) rounds as the half
    point, so the verdict message, the table and the React panel never disagree.
    """
    return math.floor(abs(ratio) * 100.0 / 5.0 + 0.5 + HALF_TOLERANCE) * 5
