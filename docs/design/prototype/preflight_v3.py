"""Mechanical slop pre-flight for the rev 3 prototype (stdlib only).

Counts, from report-v3.css and report-v3.html:
  accent hue families, grey families, distinct radii against the stated rule, emoji in the page,
  gradients, shadows, filled capsules outside the switch, duplicate labels for one intent,
  and boxes nested inside other boxes in the content area.

    python docs/design/prototype/preflight_v3.py      # exit 1 if any count misses its target
"""

from __future__ import annotations

import colorsys
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

HERE = Path(__file__).resolve().parent
CSS = (HERE / "report-v3.css").read_text(encoding="utf-8")
HTML = (HERE / "report-v3.html").read_text(encoding="utf-8")
BODY = HTML.split("<body>", 1)[1]

EVIDENCE = {"pos", "neg", "neg-50", "caution"}           # semantic colours, not accents
FACTOR = {"f1", "f2", "f3", "f4", "f5"}                  # chart identity, not accents
RADII_RULE = {"10px", "6px", "4px", "2px", "999px"}      # panels, controls, inner, marks, switch
SVG_RX_RULE = {"2", "6"}                                 # chart marks, keys, icons 2; product mark 6
APPROVED = ("Clear evidence", "Could be noise")
VARIANTS = [">Clear<", ">Yes<", ">No<", ">Significant<", "Not significant", "statistically clear",
            "No clear change", ">Moved<", "How sure:", ">Not clear<"]
CONTROLS = {"seg", "btn", "field", "skip", "linkbtn", "meter", "track", "thumb", "scrim"}  # controls, chart marks


def tokens() -> dict[str, str]:
    m = re.search(r":root\s*\{(.*?)\}", CSS, flags=re.S)
    return dict(re.findall(r"--([\w-]+):\s*(#[0-9a-fA-F]{6})", m.group(1)))


def hls(h: str) -> tuple[float, float, float]:
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (1, 3, 5))
    return colorsys.rgb_to_hls(r, g, b)


def chroma(h: str) -> float:
    v = [int(h[i:i + 2], 16) for i in (1, 3, 5)]
    return (max(v) - min(v)) / 255


def families(hues: list[float], gap: float = 25.0) -> int:
    out: list[float] = []
    for h in sorted(hues):
        if not out or min(abs(h - o) % 360 for o in out) > gap:
            out.append(h)
    return len(out)


def main() -> None:
    t = tokens()
    rows = []

    accents = {k: v for k, v in t.items() if k not in EVIDENCE | FACTOR and chroma(v) >= 0.25}
    acc_hues = [hls(v)[0] * 360 for v in accents.values()]
    tints = {k: v for k, v in t.items() if k.startswith("accent-") and k not in accents}
    rows.append(("Accent hue families", families(acc_hues + [hls(v)[0] * 360 for v in tints.values()]), 1,
                 ", ".join(f"{k} {v}" for k, v in {**accents, **tints}.items())))

    greys = {k: v for k, v in t.items() if k not in EVIDENCE | FACTOR and k not in accents and k not in tints
             and v.upper() not in ("#FFFFFF", "#000000")}
    warm = [k for k, v in greys.items() if not 150 <= hls(v)[0] * 360 <= 270]
    rows.append(("Grey families", 1 + (1 if warm else 0), 1,
                 f"{len(greys)} neutrals, all cool (hue 150 to 270)" if not warm else "warm: " + ", ".join(warm)))

    var = {k: v for k, v in re.findall(r"--(r-[\w-]+):\s*([0-9.]+px)", CSS)}
    radii = set()
    for v in re.findall(r"border-radius:\s*([^;]+);", CSS):
        for part in v.split():
            m = re.match(r"var\(--([\w-]+)\)", part)
            radii.add(var.get(m.group(1), part) if m else part)
    off = sorted(radii - RADII_RULE)
    rx = set(re.findall(r'<rect\b[^>]*\brx="([0-9.]+)"', BODY))  # corner radii only, not ellipses
    rows.append(("Distinct CSS radii (outside the rule)", len(off), 0, f"used: {', '.join(sorted(radii))}" + (f"; off-rule: {off}" if off else "")))
    rows.append(("Distinct SVG rx (outside the rule)", len(rx - SVG_RX_RULE), 0, f"used: {', '.join(sorted(rx)) or 'none'}"))

    emoji = re.findall("[\U0001F300-\U0001FAFF☀-➿⭐✨]", BODY)
    rows.append(("Emoji in the page", len(emoji), 0, ""))
    rows.append(("Gradients", len(re.findall(r"gradient\(", CSS + BODY)), 0, ""))
    rows.append(("Shadows", len(re.findall(r"(box-shadow|text-shadow|drop-shadow)", CSS + BODY)), 0, ""))

    capsules = []
    for sel, body in re.findall(r"([^{}]+)\{([^{}]*)\}", CSS):
        if re.search(r"border-radius:\s*(var\(--r-round\)|999px)", body) and re.search(r"background:", body):
            if not re.search(r"\.(track|thumb)\b", sel):
                capsules.append(sel.strip())
    rows.append(("Filled capsules outside the switch", len(capsules), 0, "; ".join(capsules)))
    pills = len(re.findall(r'class="[^"]*\bpill\b', BODY))
    rows.append(("Pill elements in the page", pills, 0, ""))

    found = [v for v in VARIANTS if v in BODY]
    rows.append(("Duplicate labels for significance", len(found), 0,
                 f"approved: {', '.join(f'{a} x{BODY.count(a)}' for a in APPROVED)}" + (f"; also found: {found}" if found else "")))

    boxes = set()
    for sel, body in re.findall(r"([^{}]+)\{([^{}]*)\}", CSS):
        boxy = re.search(r"(?<!-)border:\s*[^;]*solid", body) or re.search(r"(?<![-\w])background:\s*(?!none|transparent)", body)
        for cls in re.findall(r"^\s*\.([\w-]+)\s*$", sel.replace(",", "\n"), flags=re.M):
            if boxy and cls not in CONTROLS:
                boxes.add(cls)

    class Walk(HTMLParser):
        void = {"input", "br", "meta", "img", "line", "rect", "circle", "path", "hr"}

        def __init__(self) -> None:
            super().__init__()
            self.stack: list[tuple[str, bool]] = []
            self.in_main = 0
            self.nested: list[str] = []

        def handle_starttag(self, tag, attrs):
            cls = set((dict(attrs).get("class") or "").split())
            box = bool(cls & boxes)
            if tag == "main":
                self.in_main += 1
            if self.in_main and box and any(b for _, b in self.stack):
                self.nested.append(" ".join(sorted(cls & boxes)))
            if tag not in self.void:
                self.stack.append((tag, box))

        def handle_endtag(self, tag):
            if tag == "main":
                self.in_main -= 1
            for i in range(len(self.stack) - 1, -1, -1):
                if self.stack[i][0] == tag:
                    del self.stack[i:]
                    break

    w = Walk()
    w.feed(BODY)
    rows.append(("Nested boxes in the content", len(w.nested), 0,
                 f"box classes: {', '.join(sorted(boxes))}" + (f"; nested: {sorted(set(w.nested))}" if w.nested else "")))

    em = BODY.count("—")
    dots = len(re.findall(r"\s·\s", BODY))
    rows.append(("Em dashes in copy", em, 0, ""))
    rows.append(("Middle-dot meta strings", dots, 0, ""))
    weights = sorted(set(re.findall(r"font-weight:\s*(\d+)", CSS)))
    heavy = [x for x in weights if int(x) > 600]
    rows.append(("Weights above 600 (ticker only)", len(heavy), 1, f"weights used: {', '.join(weights)}"))

    ok = True
    print(f"{'check':<42}{'count':>6}{'target':>8}  detail")
    for name, n, target, detail in rows:
        good = n <= target if target else n == 0
        ok &= good
        print(f"{name:<42}{n:>6}{target:>8}  {detail}{'' if good else '  FIX'}")
    print("\npre-flight passes" if ok else "\npre-flight fails")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
