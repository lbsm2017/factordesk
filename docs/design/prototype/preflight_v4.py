"""Mechanical slop pre-flight for the rev 4 prototype (stdlib only).

Counts, from report-v4.css and both variant pages (report-v4a.html, report-v4b.html):
  accent hue families, grey families, radii against the shape rule, emoji, gradients, shadows,
  pills outside the segmented control, duplicate labels for one intent, boxes nested inside boxes,
  hero headlines, em dashes, all-caps text, text under 14 px, and the contrast of every text pair.

    python docs/design/prototype/preflight_v4.py      # exit 1 if any count misses its target
"""

from __future__ import annotations

import colorsys
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

HERE = Path(__file__).resolve().parent
CSS = (HERE / "report-v4.css").read_text(encoding="utf-8")
PAGES = {v: (HERE / f"report-v4{v}.html").read_text(encoding="utf-8").split("<body", 1)[1] for v in ("a", "b")}

EVIDENCE = {"pos", "neg", "neg-50", "caution"}
FACTOR = {"f1", "f2", "f3", "f4", "f5"}
RADII_RULE = {"8px", "6px", "4px", "2px", "999px"}
SVG_RX_RULE = {"2", "6"}
APPROVED = ("Clear evidence", "Could be noise")
VARIANTS = [">Clear<", ">Yes<", ">No<", ">Significant<", "Not significant", "statistically clear", ">Not clear<", "How sure"]
CONTROLS = {"seg", "btn", "field", "skip", "linkbtn", "track", "thumb", "scrim", "badge"}
TEXT_PAIRS = [  # (foreground, background) tokens that carry text
    ("ink", "surface"), ("ink-2", "surface"), ("ink", "page"), ("ink-2", "page"), ("ink-2", "soft"),
    ("accent", "surface"), ("accent", "page"), ("on-accent", "accent"), ("pos", "surface"), ("neg", "surface"),
    ("caution", "surface"), ("rail-text", "rail"), ("rail-2", "rail"), ("rail-cyan", "rail"), ("rail", "rail-cyan"),
    ("rail-2", "rail-hover"), ("rail-cyan", "rail-hover"),
]


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


def lum(h: str) -> float:
    def ch(c: float) -> float:
        c /= 255
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (int(h[i:i + 2], 16) for i in (1, 3, 5))
    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)


def ratio(a: str, b: str) -> float:
    la, lb = sorted((lum(a), lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def nested_boxes(body: str, boxes: set[str]) -> list[str]:
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
    w.feed(body)
    return w.nested


def main() -> None:
    t = tokens()
    rows = []
    both = "".join(PAGES.values())

    accents = {k: v for k, v in t.items() if k not in EVIDENCE | FACTOR and chroma(v) >= 0.25}
    tints = {k: v for k, v in t.items() if k.startswith("accent-")}
    hues = [hls(v)[0] * 360 for v in {**accents, **tints}.values()]
    rows.append(("Accent hue families", families(hues), 1, ", ".join(f"{k} {v}" for k, v in {**accents, **tints}.items())))

    greys = {k: v for k, v in t.items() if k not in EVIDENCE | FACTOR and k not in accents and k not in tints
             and v.upper() not in ("#FFFFFF", "#000000")}
    warm = [k for k, v in greys.items() if not 150 <= hls(v)[0] * 360 <= 270]
    rows.append(("Grey families", 1 + (1 if warm else 0), 1,
                 f"{len(greys)} neutrals, all cool (hue 150 to 270)" if not warm else "warm: " + ", ".join(warm)))

    var = dict(re.findall(r"--(r-[\w-]+):\s*([0-9.]+px)", CSS))
    radii = set()
    for v in re.findall(r"border-radius:\s*([^;]+);", CSS):
        for part in v.split():
            m = re.match(r"var\(--([\w-]+)\)", part)
            radii.add(var.get(m.group(1), part) if m else part)
    off = sorted(radii - RADII_RULE)
    rows.append(("Radii outside the shape rule", len(off), 0, f"used: {', '.join(sorted(radii))}"))
    rx = set(re.findall(r'<rect\b[^>]*\brx="([0-9.]+)"', both))
    rows.append(("SVG rx outside the rule", len(rx - SVG_RX_RULE), 0, f"used: {', '.join(sorted(rx)) or 'none'}"))

    rows.append(("Emoji", len(re.findall("[\U0001F300-\U0001FAFF☀-➿⭐✨]", both)), 0, ""))
    rows.append(("Gradients", len(re.findall(r"gradient\(", CSS + both)), 0, ""))
    rows.append(("Shadows", len(re.findall(r"(box-shadow|text-shadow|drop-shadow)", CSS + both)), 0, ""))

    pills = []
    for sel, body in re.findall(r"([^{}]+)\{([^{}]*)\}", CSS):
        if re.search(r"border-radius:\s*(var\(--r-round\)|999px)", body) and not re.search(r"\.(track|thumb)\b", sel):
            pills.append(sel.strip())
    pills += re.findall(r'class="[^"]*\b(pill|chip|tag)\b', both)
    rows.append(("Pills outside the segmented control and switch", len(pills), 0, "; ".join(pills)))

    found = [v for v in VARIANTS if v in both]
    rows.append(("Duplicate labels for one intent", len(found), 0,
                 f"approved: {', '.join(f'{a} x{both.count(a)}' for a in APPROVED)}" + (f"; also found: {found}" if found else "")))

    boxes = set()
    for sel, body in re.findall(r"([^{}]+)\{([^{}]*)\}", CSS):
        boxy = re.search(r"(?<!-)border:\s*[^;]*solid", body) or re.search(r"(?<![-\w])background:\s*(?!none|transparent)", body)
        for cls in re.findall(r"^\s*\.([\w-]+)\s*$", sel.replace(",", "\n"), flags=re.M):
            if boxy and cls not in CONTROLS:
                boxes.add(cls)
    for v, body in PAGES.items():
        n = nested_boxes(body, boxes)
        rows.append((f"Nested boxes, v4{v}", len(n), 0, f"box classes: {', '.join(sorted(boxes))}" + (f"; nested: {sorted(set(n))}" if n else "")))

    sizes = [int(x) for x in re.findall(r"--fs-[\w-]+:\s*(\d+)px", CSS)]
    h1 = int(re.search(r"--fs-title:\s*(\d+)px", CSS).group(1))
    sub = int(re.search(r"--fs-sub:\s*(\d+)px", CSS).group(1))
    hero = len(re.findall(r'class="[^"]*\b(hero|verdict-line|headline)\b', both)) + (1 if h1 > 28 else 0)
    rows.append(("Hero headlines (or a title above 28 px)", hero, 0, f"page title {h1} px; verdict set at {sub} px"))
    small = [s for s in sizes if s < 14] + [int(x) for x in re.findall(r"font-size:\s*(\d+)px", CSS) if int(x) < 14]
    rows.append(("Text sizes under 14 px", len(small), 0, f"scale: {', '.join(str(s) for s in sorted(set(sizes)))}"))
    rows.append(("Em dashes", both.count("\u2014") + both.count("&mdash;") + both.count("&#8212;"), 0, ""))
    rows.append(("All-caps text-transform outside the ticker field", len(re.findall(r"text-transform:\s*uppercase", CSS)) - 1, 0, ""))

    fails = [(a, b, round(ratio(t[a], t[b]), 2)) for a, b in TEXT_PAIRS if ratio(t[a], t[b]) < 4.5]
    rows.append(("Text pairs under 4.5:1", len(fails), 0, f"{len(TEXT_PAIRS)} pairs checked" + (f"; {fails}" if fails else "")))

    ok = True
    print(f"{'check':<52}{'count':>6}{'target':>8}  detail")
    for name, n, target, detail in rows:
        good = n <= target
        ok &= good
        print(f"{name:<52}{n:>6}{target:>8}  {detail}{'' if good else '  FIX'}")
    print("\npre-flight passes" if ok else "\npre-flight fails")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
