"""Contrast table for the rev 3 prototype tokens (stdlib only). Light theme only.

Reads the token block at the top of report-v3.css and prints the WCAG 2 contrast ratio of every
text/background pair the stylesheet uses, plus the UI pairs (controls, switch track, chart marks)
that need 3:1. Exit code 1 if any pair fails.

    python docs/design/prototype/contrast_v3.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CSS = (HERE / "report-v3.css").read_text(encoding="utf-8")


def tokens() -> dict[str, str]:
    m = re.search(r":root\s*\{(.*?)\}", CSS, flags=re.S)
    if not m:
        sys.exit("token block not found")
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
PAIRS = [
    ("ink", "page", 4.5, "header text on the grey page"),
    ("ink", "surface", 4.5, "body text, verdict headline"),
    ("ink-2", "page", 4.5, "header subline"),
    ("ink-2", "surface", 4.5, "secondary text in panels"),
    ("ink-3", "surface", 4.5, "axis labels, footnotes"),
    ("ink-3", "soft", 4.5, "labels over the not-analysed zone"),
    ("accent", "surface", 4.5, "links, Details, How this is computed"),
    ("accent", "page", 4.5, "links on the page"),
    ("accent", "accent-50", 4.5, "targeted table row"),
    ("ink", "accent-50", 4.5, "targeted table row text"),
    ("on-accent", "accent", 4.5, "selected segment, primary button"),
    ("pos", "surface", 4.5, "positive labels"),
    ("neg", "surface", 4.5, "negative labels, worst fall"),
    ("caution", "surface", 4.5, "warning label, demo note"),
    ("caution", "page", 4.5, "warnings link in the header"),
    ("rail-text", "rail", 4.5, "rail text"),
    ("rail-2", "rail", 4.5, "rail secondary text"),
    ("rail-cyan", "rail", 4.5, "current section"),
    ("rail-cyan", "rail-hover", 4.5, "current section on its highlight"),
    ("rail-text", "rail-hover", 4.5, "hovered section"),
    ("rail", "rail-cyan", 4.5, "Factor it, selected range"),
    ("rail-field-text", "rail-field", 4.5, "inputs in the rail"),
    ("control-line", "surface", 3.0, "UI: segment and input borders"),
    ("rail-track", "rail", 3.0, "UI: switch track off, segment border in the rail"),
    ("rail-cyan", "rail", 3.0, "UI: switch track on, rail focus ring"),
    ("accent", "surface", 3.0, "UI: focus ring, verdict rule"),
    ("caution", "surface", 3.0, "UI: data-quality note rule"),
    ("pos", "surface", 3.0, "UI: positive bars"),
    ("neg", "surface", 3.0, "UI: negative bars"),
    ("ink", "surface", 3.0, "UI: estimate dots, meters"),
    ("axis", "surface", 3.0, "UI: zero line"),
]


def main() -> None:
    t = tokens()
    ok = True
    print(f"{'foreground':<16}{'background':<12}{'fg':>9}{'bg':>9}{'ratio':>8}{'min':>6}  use")
    for fg, bg, need, use in PAIRS:
        r = ratio(t[fg], t[bg])
        ok &= r >= need
        print(f"{fg:<16}{bg:<12}{t[fg]:>9}{t[bg]:>9}{r:>8.2f}{need:>6.1f}  {use}{'' if r >= need else '  FAIL'}")
    print("\nall pairs pass" if ok else "\nsome pairs fail")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
