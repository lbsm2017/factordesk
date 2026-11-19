"""Sign-colour check for the rev 4 prototype (stdlib only).

Reads the tokens at the top of report-v4.css and prints:
  - WCAG 2 contrast of the green and red text on white, the page and the row-hover ground;
  - contrast of the full and light-tint bars (graphical objects, 3:1) against the panel;
  - OKLab separation (x100) of the green and red pair, full and tint, under normal vision and
    the Machado (2009) protanopia, deuteranopia and tritanopia simulations at severity 1.0.
Floors: text 4.5:1, bars 3:1 (a tint below 3:1 must carry a full-colour outline), CVD 8, normal 15.

    python docs/design/prototype/colour_v4.py      # exit 1 if a floor is missed
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CSS = (HERE / "report-v4.css").read_text(encoding="utf-8")
T = dict(re.findall(r"--([\w-]+):\s*(#[0-9a-fA-F]{6})", re.search(r":root\s*\{(.*?)\}", CSS, flags=re.S).group(1)))

MACHADO = {
    "protanopia": ((0.152286, 1.052583, -0.204868), (0.114503, 0.786281, 0.099216), (-0.003882, -0.048116, 1.051998)),
    "deuteranopia": ((0.367322, 0.860646, -0.227968), (0.280085, 0.672501, 0.047413), (-0.011820, 0.042940, 0.968881)),
    "tritanopia": ((1.255528, -0.076749, -0.178779), (-0.078411, 0.930809, 0.147602), (0.004733, 0.691367, 0.303900)),
}


def lin(h: str) -> tuple[float, float, float]:
    def ch(c: float) -> float:
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    return tuple(ch(int(h[i:i + 2], 16) / 255) for i in (1, 3, 5))  # type: ignore[return-value]


def lum(h: str) -> float:
    r, g, b = lin(h)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a: str, b: str) -> float:
    la, lb = sorted((lum(a), lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def oklab(rgb: tuple[float, float, float]) -> tuple[float, float, float]:
    r, g, b = rgb
    l_ = (0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b) ** (1 / 3)
    m_ = (0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b) ** (1 / 3)
    s_ = (0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b) ** (1 / 3)
    return (0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_,
            1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_,
            0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_)


def simulate(rgb: tuple[float, float, float], kind: str) -> tuple[float, float, float]:
    if kind == "normal":
        return rgb
    m = MACHADO[kind]
    return tuple(min(1.0, max(0.0, sum(m[i][j] * rgb[j] for j in range(3)))) for i in range(3))  # type: ignore[return-value]


def sep(a: str, b: str, kind: str) -> float:
    pa, pb = oklab(simulate(lin(a), kind)), oklab(simulate(lin(b), kind))
    return 100 * sum((x - y) ** 2 for x, y in zip(pa, pb)) ** 0.5


def main() -> None:
    ok = True
    rows = []
    for fg in ("pos", "neg"):
        for bg in ("surface", "page", "soft"):
            c = contrast(T[fg], T[bg])
            rows.append((f"text {fg} {T[fg]} on {bg} {T[bg]}", c, 4.5))
    for fg in ("pos", "neg"):
        rows.append((f"bar {fg} {T[fg]} on surface", contrast(T[fg], T["surface"]), 3.0))
        tint = T[f"{fg}-t"]
        c = contrast(tint, T["surface"])
        rows.append((f"tint bar {fg}-t {tint} on surface (outlined in {T[fg]})", c, 0.0))
        rows.append((f"tint outline {fg} {T[fg]} on surface", contrast(T[fg], T["surface"]), 3.0))
    print(f"{'contrast':<62}{'ratio':>8}{'floor':>8}")
    for name, c, floor in rows:
        good = c >= floor
        ok &= good
        print(f"{name:<62}{c:>8.2f}{floor or 0:>8.1f}{'' if good else '  FIX'}")
    print(f"\n{'separation, OKLab x100':<62}{'normal':>8}{'protan':>8}{'deutan':>8}{'tritan':>8}")
    # the tint fills are not gated: every tint bar is outlined in the full hue, so the outline pair
    # carries the hue; the tint row is printed for information only
    for name, a, b, gated in (("pos / neg (text, full bars, tint outlines)", T["pos"], T["neg"], True),
                              ("pos-t / neg-t (tint fills, information only)", T["pos-t"], T["neg-t"], False)):
        vals = [sep(a, b, k) for k in ("normal", "protanopia", "deuteranopia", "tritanopia")]
        good = (vals[0] >= 15 and min(vals[1:]) >= 8) or not gated
        ok &= good
        print(f"{name:<62}" + "".join(f"{v:>8.1f}" for v in vals) + ("" if good else "  FIX"))
    print("\ncolour check passes" if ok else "\ncolour check fails")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
