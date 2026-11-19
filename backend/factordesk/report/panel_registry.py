"""Ordered panel registry of the static HTML report (schema v3 contract, SC3.3 and SC4).

Every panel of ``render_report_html`` registers here with a name and a position; the page draws
them in position order. The core panels register in ``render_html.py``; each optional section's
panel registers in its own module under ``report/panels/``, which ``registered_panels`` imports
once. Adding or filling a panel therefore never edits a shared list.

A render function returns the panel's HTML, or ``None`` when there is nothing to draw (an absent
optional section). ``None`` adds nothing to the page, not even a line break, and the panel's CSS
is left out with it.
"""

from __future__ import annotations

import importlib
from collections.abc import Callable
from dataclasses import dataclass

from factordesk.report.schema import FactorReport

PanelRenderer = Callable[[FactorReport], str | None]

FEATURE_PANELS_PACKAGE = "factordesk.report.panels"
"""Package whose import registers the panels of the optional sections."""


@dataclass(frozen=True)
class PanelSpec:
    """One registered panel."""

    name: str
    """Stable name, the same as in the React registry (``panelRegistry.ts``)."""
    position: int
    """Place on the page; lower comes first. Positions are fixed in contract SC4."""
    render: PanelRenderer
    css: str = ""
    """Extra stylesheet text, inlined after the base stylesheet when the panel draws."""


class PanelRegistry:
    """Panels by name. A name or a position can be taken only once."""

    def __init__(self) -> None:
        self._specs: dict[str, PanelSpec] = {}

    def register(
        self, name: str, position: int, render: PanelRenderer, *, css: str = ""
    ) -> PanelSpec:
        """Add a panel. Registering the same function again (a module reload) replaces it."""
        current = self._specs.get(name)
        if current is not None and (
            current.position != position or _origin(current.render) != _origin(render)
        ):
            raise ValueError(f"panel name {name!r} is already registered")
        for other in self._specs.values():
            if other.name != name and other.position == position:
                raise ValueError(f"panel position {position} is already taken by {other.name!r}")
        spec = PanelSpec(name=name, position=position, render=render, css=css)
        self._specs[name] = spec
        return spec

    def ordered(self) -> tuple[PanelSpec, ...]:
        """Every registered panel, by position."""
        return tuple(sorted(self._specs.values(), key=lambda spec: spec.position))


def _origin(render: PanelRenderer) -> tuple[str, str]:
    """Where a render function is defined (module and qualified name)."""
    return (
        getattr(render, "__module__", ""),
        getattr(render, "__qualname__", repr(render)),
    )


REGISTRY = PanelRegistry()
"""The registry ``render_report_html`` draws from."""


def register_panel(name: str, position: int, render: PanelRenderer, *, css: str = "") -> PanelSpec:
    """Register a panel of the static report (see ``PanelRegistry.register``)."""
    return REGISTRY.register(name, position, render, css=css)


def registered_panels() -> tuple[PanelSpec, ...]:
    """Every panel of the static report in page order, the optional sections' panels included."""
    importlib.import_module(FEATURE_PANELS_PACKAGE)
    return REGISTRY.ordered()
