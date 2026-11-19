"""Screenshots and layout measurements for the rev 4 prototype (stdlib + headless Chrome CLI).

Builds variant pages with build_prototype_v4.py into a temporary folder and calls Chrome's own
--screenshot; the frame, crop and measurement helpers come from shoot_v3.py, unchanged.

    python docs/design/prototype/shoot_v4.py               # every shot in SHOTS, both variants
    python docs/design/prototype/shoot_v4.py shot_v4a_1440 # only the named shots
    python docs/design/prototype/shoot_v4.py measure       # horizontal overflow check at 390, 1024, 1440, 1920
"""

from __future__ import annotations

import subprocess
import sys

from shoot_v3 import HERE, MEASURE, MIN_WINDOW, TMP, chrome, crop_png, framed, measure

# suffix, width, height (None = full page), switches, only these grid panels (crop)
SHOTS = [
    ("1440", 1440, 900, "", None),
    ("1440_full", 1440, None, "", None),
    ("1920", 1920, 1080, "", None),
    ("1024", 1024, 768, "", None),
    ("1024_full", 1024, None, "", None),
    ("390", 390, 844, "", None),
    ("390_full", 390, None, "", None),
    ("390_crop_tables", 390, None, "", "performance,exposures,rolling,kalman"),
    ("1440_stats_on", 1440, 900, "stats", None),
    ("1440_full_stats_on", 1440, None, "stats", None),
]


def variant_page(name: str, v: str, on: str, measure_it: bool, only: str | None = None) -> object:
    out = TMP / f"{name}.html"
    args = [sys.executable, str(HERE / "build_prototype_v4.py"), "--variant", v, "--out", str(out)]
    if on:
        args += ["--on", on]
    subprocess.run(args, check=True, capture_output=True)
    extra = MEASURE if measure_it else ""
    if only:
        keep = ", ".join(f"#{x}" for x in only.split(","))
        extra += (f"<style>.page-head, .abar, .sumbar, .kpis, .colophon {{ display: none !important; }} "
                  f".grid > :not({keep}):not(:has({keep})), .stack > :not({keep}) {{ display: none !important; }}</style>")
    if extra:
        html = out.read_text(encoding="utf-8")
        out.write_text(html.replace("</head>", extra + "</head>", 1), encoding="utf-8")
    return out


def shoot() -> None:
    only = [a for a in sys.argv[1:] if a.startswith("shot_")]
    for v in ("a", "b"):
        for suffix, w, h, on, crop in SHOTS:
            name = f"shot_v4{v}_{suffix}"
            if only and name not in only:
                continue
            page = variant_page(name, v, on, h is None, crop)
            if h is None:
                h = measure(page, w)[2]
            out = HERE / f"{name}.png"
            if w < MIN_WINDOW:
                chrome(f"--window-size={MIN_WINDOW},{h}", "--allow-file-access-from-files", f"--screenshot={out}", framed(page, w, h).as_uri())
                crop_png(out, w)
            else:
                chrome(f"--window-size={w},{h}", f"--screenshot={out}", page.as_uri())
            print(f"{out}  {w}x{h}")


def report_measures() -> None:
    for v in ("a", "b"):
        for w in (390, 1024, 1440, 1920):
            for on in ("", "stats"):
                page = variant_page(f"m{v}{w}{on}", v, on, True)
                sw, cw, sh = measure(page, w, 844)
                print(f"v4{v} width {w:>4} {on or 'default':<8} scrollWidth {sw} clientWidth {cw} scrollHeight {sh} "
                      f"{'OK' if sw <= cw else 'HORIZONTAL SCROLL'}")


if __name__ == "__main__":
    report_measures() if "measure" in sys.argv else shoot()
