"""Contrast table for the rev 3 prototype tokens (stdlib only).

Reads the token blocks at the top of report-v3.css (light, then dark), and prints the WCAG 2
contrast ratio of every text/background pair the stylesheet uses, plus the UI-boundary pairs
(controls, switch track, chart marks) that need 3:1.

    python docs/design/prototype/contrast_v3.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CSS = (HERE / "report-v3.css").read_text(encoding="utf-8")


def block(marker: str) -> dict[str, str]:
    """Custom properties of the first rule whose selector contains ``marker``."""
    m = re.search(re.escape(marker) + r"[^{]*\{(.*?)\}", CSS, flags=re.S)
    if not m:
        sys.exit(f"token block {marker!r} not found")
    return dict(re.findall(r"--([\w-]+):\s*(#[0-9a-fA-F]{6})", m.group(1)))


def lum(h: str) -> float:
    def ch(c: float) -> float:
        c /= 255
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (int(h[i : i + 2], 16) for i in (1, 3, 5))
    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)


def ratio(a: str, b: str) -> float:
    la, lb = sorted((lum(a), lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


# (foreground token, background token, minimum, what uses it)
TEXT = [
    ("ink", "page", 4.5, "header text on the grey page"),
    ("ink", "surface", 4.5, "body text in panels"),
    ("ink", "soft", 4.5, "text in soft boxes"),
    ("ink", "hi-50", 4.5, "verdict headline on the band"),
    ("hi", "hi-50", 4.5, "indigo text on the band"),
    ("ink-2", "page", 4.5, "secondary text on the page"),
    ("ink-2", "surface", 4.5, "secondary text in panels"),
    ("ink-2", "hi-50", 4.5, "verdict basis line"),
    ("ink-3", "surface", 4.5, "axis labels, footnotes"),
    ("ink-3", "soft", 4.5, "muted text in soft boxes"),
    ("accent", "surface", 4.5, "links, How this is computed"),
    ("accent", "page", 4.5, "links on the page"),
    ("accent", "accent-50", 4.5, "teal text on the teal tint"),
    ("ink", "accent-50", 4.5, "world tile, callouts"),
    ("on-accent", "accent", 4.5, "selected segment, primary button"),
    ("pos", "surface", 4.5, "positive words"),
    ("pos", "pos-50", 4.5, "positive pill"),
    ("neg", "surface", 4.5, "negative values"),
    ("neg", "neg-50", 4.5, "negative pill"),
    ("caution", "caution-50", 4.5, "notice band label, warning chip"),
    ("ink", "caution-50", 4.5, "notice band text"),
    ("slate", "slate-50", 4.5, "neutral pill"),
    ("rail-text", "rail", 4.5, "rail text"),
    ("rail-2", "rail", 4.5, "rail secondary text"),
    ("rail-cyan", "rail", 4.5, "current section, switch on"),
    ("rail-cyan", "rail-hover", 4.5, "current section on its highlight"),
    ("rail-text", "rail-hover", 4.5, "hovered section"),
    ("rail", "rail-cyan", 4.5, "Factor it button, selected range"),
    ("rail-field-text", "rail-field", 4.5, "inputs in the rail"),
]
UI = [
    ("control-line", "surface", 3.0, "segment and input borders"),
    ("rail-track", "rail", 3.0, "switch track, off"),
    ("rail-cyan", "rail", 3.0, "switch track on, rail focus ring"),
    ("accent", "surface", 3.0, "focus ring in the canvas"),
    ("accent", "page", 3.0, "focus ring on the page"),
    ("pos", "surface", 3.0, "positive bars"),
    ("neg", "surface", 3.0, "negative bars"),
    ("hi", "surface", 3.0, "estimate dots, meters"),
    ("axis", "surface", 3.0, "zero line"),
]


def table(name: str, tokens: dict[str, str]) -> bool:
    ok = True
    print(f"\n{name}")
    print(f"{'foreground':<14}{'background':<12}{'fg':>9}{'bg':>9}{'ratio':>8}{'min':>6}  use")
    for group in (TEXT, UI):
        for fg, bg, need, use in group:
            if fg not in tokens or bg not in tokens:
                print(f"{fg:<14}{bg:<12}  missing token")
                ok = False
                continue
            r = ratio(tokens[fg], tokens[bg])
            flag = "" if r >= need else "  FAIL"
            ok &= r >= need
            print(f"{fg:<14}{bg:<12}{tokens[fg]:>9}{tokens[bg]:>9}{r:>8.2f}{need:>6.1f}  {use}{flag}")
    return ok


light = block(":root")
dark = {**light, **block(":root[data-theme=\"dark\"]")}
good = table("Light theme", light) & table("Dark theme", dark)
print("\nall pairs pass" if good else "\nsome pairs fail")
sys.exit(0 if good else 1)
