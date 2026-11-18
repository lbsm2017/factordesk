"""The words of the Kalman-filter betas panel, in one place for both renderers.

``kalman_text.json`` holds every sentence, header and flag that the static panel
(``panels/kalman.py``) and the React panel (``KalmanPanel.tsx``) print themselves. The React side
imports a checked-in copy, ``frontend/src/text/kalman.json``; a test on each side asserts that the
two files are equal. The longer label texts (L-KF, L-KBAND, L-KTAIL) travel in the report payload
and are not repeated here. Placeholders are written ``{name}``; ``fill`` replaces them.
"""

from __future__ import annotations

import json
from functools import cache
from pathlib import Path
from typing import Any, cast

TEXT_PATH = Path(__file__).with_name("kalman_text.json")


@cache
def kalman_text() -> dict[str, Any]:
    """The decoded JSON file (read once)."""
    return cast(dict[str, Any], json.loads(TEXT_PATH.read_text(encoding="utf-8")))


def fill(template: str, **values: object) -> str:
    """Replace each ``{name}`` in ``template`` by ``str(values[name])``; other braces stay."""
    for key, value in values.items():
        template = template.replace("{" + key + "}", str(value))
    return template
