"""Hatch build hook: refuse to build a wheel that has no dashboard in it.

The page is built by Node (``npm --prefix frontend run build:package`` copies it into
``backend/factordesk/web``). This hook does not run Node itself: someone installing from the
source archive may have no Node, and a silent wheel without a page is the failure to prevent.
Editable installs (``uv sync``) skip the check so a fresh checkout still installs.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from hatchling.builders.hooks.plugin.interface import BuildHookInterface

WEB_INDEX = Path("backend") / "factordesk" / "web" / "index.html"


class WebBundleHook(BuildHookInterface):  # type: ignore[type-arg]
    PLUGIN_NAME = "custom"

    def initialize(self, version: str, build_data: dict[str, Any]) -> None:
        if self.target_name != "wheel" or version != "standard":
            return
        if not (Path(self.root) / WEB_INDEX).is_file():
            raise RuntimeError(
                f"{WEB_INDEX} is missing, so the wheel would have no dashboard. "
                "Run 'npm --prefix frontend ci' and 'npm --prefix frontend run build:package' "
                "first (see docs/release-checklist.md)."
            )
