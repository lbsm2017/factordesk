"""Screenshots and layout measurements for the rev 3 prototype (stdlib + headless Chrome CLI).

Builds screenshot variants of report-v3.html with build_prototype_v3.py (switches pre-checked),
then calls Chrome's own --screenshot and --dump-dom. No browser automation library is needed.

    python docs/design/prototype/shoot_v3.py              # every shot listed in SHOTS
    python docs/design/prototype/shoot_v3.py measure      # scroll width and height at 390, 1024, 1440

Set CHROME to the browser binary if it is not at the default Windows path.
Variant pages and the Chrome profile go to a temporary folder, not to the repository.
"""

from __future__ import annotations

import os
import re
import struct
import subprocess
import zlib
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
CHROME = os.environ.get("CHROME", r"C:\Program Files\Google\Chrome\Application\chrome.exe")
TMP = Path(tempfile.mkdtemp(prefix="fd-shots-"))

MEASURE = """<script>addEventListener('load',()=>{const d=document.documentElement;
const v=d.scrollWidth+'x'+d.clientWidth+'x'+d.scrollHeight;
const m=document.createElement('meta');m.id='fd-measure';m.content=v;document.head.appendChild(m);
if(parent!==window)parent.postMessage(v,'*');});</script>"""

# Chrome's headless window on Windows is at least 500 px wide, so narrower viewports are
# rendered in an iframe of the exact width and the PNG is cropped afterwards (pure Python).
MIN_WINDOW = 500
FRAME = """<!doctype html><html><head><meta charset="utf-8"><style>html,body{{margin:0;background:#FFFFFF}}
iframe{{display:block;border:0;width:{w}px;height:{h}px}}</style>
<script>addEventListener('message',e=>{{const m=document.createElement('meta');m.id='fd-measure';m.content=e.data;document.head.appendChild(m);}});</script>
</head><body><iframe src="{src}" title="Prototype at {w} px"></iframe></body></html>"""

# name, width, height (None = full page), switches, only these sections (crop), extra CSS
SHOTS = [
    ("shot_v3_1920_light", 1920, 1080, "", None),
    ("shot_v3_1440_light", 1440, 900, "", None),
    ("shot_v3_1440_dark", 1440, 900, "dark", None),
    ("shot_v3_1440_stats_on", 1440, 900, "stats", None),
    ("shot_v3_1024_light", 1024, 768, "", None),
    ("shot_v3_390_light", 390, 844, "", None),
    ("shot_v3_390_drawer", 390, 844, "menu", None),
    ("shot_v3_1440_full_light", 1440, None, "", None),
    ("shot_v3_1440_full_dark", 1440, None, "dark", None),
    ("shot_v3_390_full_light", 390, None, "", None),
    ("shot_v3_crop_drivers", 1440, None, "", "drivers,world"),
    ("shot_v3_crop_exposures_stats_off", 1440, None, "", "exposures,returns"),
    ("shot_v3_crop_exposures_stats_on", 1440, None, "stats", "exposures,returns"),
    ("shot_v3_crop_performance", 1440, None, "", "price,performance"),
    ("shot_v3_crop_risk_rolling", 1440, None, "", "risk,rolling"),
    ("shot_v3_crop_deeper", 1440, None, "", "residual,kalman,shrunk"),
    ("shot_v3_crop_audit_stats_on", 1440, None, "stats", "data,detail"),
    ("shot_v3_1440_empty", 1440, 900, "", None),
    ("shot_v3_390_crop_tables", 390, None, "", "exposures,risk"),
]


def variant(name: str, on: str, only: str | None, measure: bool = False, empty: bool = False) -> Path:
    out = TMP / f"{name}.html"
    args = [sys.executable, str(HERE / "build_prototype_v3.py"), "--out", str(out)]
    if on:
        args += ["--on", on]
    if empty:
        args.append("--empty")
    subprocess.run(args, check=True, capture_output=True)
    html = out.read_text(encoding="utf-8")
    extra = ""
    if only:
        keep = ", ".join(f"#{s}" for s in only.split(","))
        extra += f"<style>main > :not({keep}) {{ display: none !important; }} main > :is({keep}):first-of-type {{ margin-top: 0; }}</style>"
    if measure:
        extra += MEASURE
    out.write_text(html.replace("</head>", extra + "</head>", 1), encoding="utf-8")
    return out


def chrome(*args: str) -> str:
    base = [CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--force-device-scale-factor=1",
            "--no-first-run", f"--user-data-dir={TMP / 'profile'}", "--virtual-time-budget=4000"]
    res = subprocess.run(base + list(args), capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
    return res.stdout


def framed(page: Path, w: int, h: int) -> Path:
    out = page.with_name(page.stem + f"-frame{w}x{h}.html")
    out.write_text(FRAME.format(w=w, h=h, src=page.as_uri()), encoding="utf-8")
    return out


def measure(page: Path, width: int, height: int = 900) -> tuple[int, int, int]:
    target, win = page, width
    if width < MIN_WINDOW:
        target, win = framed(page, width, height), MIN_WINDOW
    dom = chrome(f"--window-size={win},{height}", "--allow-file-access-from-files", "--dump-dom", target.as_uri())
    m = re.search(r'id="fd-measure" content="(\d+)x(\d+)x(\d+)"', dom)
    if not m:
        raise SystemExit("measurement meta not found in the dumped DOM")
    sw, cw, sh = (int(x) for x in m.groups())
    return sw, cw, sh


def _png_rows(data: bytes) -> tuple[int, int, int, list[bytearray]]:
    """Decode an 8-bit, non-interlaced RGB or RGBA PNG into unfiltered rows."""
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    i, idat, w = 8, b"", 0
    while i < len(data):
        n = struct.unpack(">I", data[i:i + 4])[0]
        kind, body = data[i + 4:i + 8], data[i + 8:i + 8 + n]
        if kind == b"IHDR":
            w, h, depth, ctype, _, _, inter = struct.unpack(">IIBBBBB", body)
            assert depth == 8 and ctype in (2, 6) and inter == 0, "unsupported PNG"
            bpp = 4 if ctype == 6 else 3
        elif kind == b"IDAT":
            idat += body
        i += 12 + n
    raw = zlib.decompress(idat)
    stride = w * bpp
    rows, prev = [], bytearray(stride)
    for y in range(h):
        f = raw[y * (stride + 1)]
        line = bytearray(raw[y * (stride + 1) + 1:(y + 1) * (stride + 1)])
        if f == 1:
            for x in range(bpp, stride):
                line[x] = (line[x] + line[x - bpp]) & 255
        elif f == 2:
            line = bytearray((a + b) & 255 for a, b in zip(line, prev))
        elif f == 3:
            for x in range(stride):
                left = line[x - bpp] if x >= bpp else 0
                line[x] = (line[x] + ((left + prev[x]) >> 1)) & 255
        elif f == 4:
            for x in range(stride):
                a = line[x - bpp] if x >= bpp else 0
                b, c = prev[x], (prev[x - bpp] if x >= bpp else 0)
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                line[x] = (line[x] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        rows.append(line)
        prev = line
    return w, h, bpp, rows


def crop_png(path: Path, width: int) -> None:
    """Keep the left ``width`` pixels of a PNG (stdlib only: zlib + struct)."""
    w, h, bpp, rows = _png_rows(path.read_bytes())
    raw = b"".join(b"\x00" + bytes(r[: width * bpp]) for r in rows)

    def chunk(kind: bytes, body: bytes) -> bytes:
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", width, h, 8, 6 if bpp == 4 else 2, 0, 0, 0)
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def shoot() -> None:
    only_names = [a for a in sys.argv[1:] if a.startswith("shot_")]
    for name, w, h, on, only in SHOTS:
        if only_names and name not in only_names:
            continue
        page = variant(name, on, only, measure=h is None, empty="empty" in name)
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
    for w in (390, 1024, 1440):
        for on in ("", "stats", "menu"):
            page = variant(f"m{w}{on}", on, None, measure=True)
            sw, cw, sh = measure(page, w, 844)
            print(f"width {w:>4} {on or 'default':<8} scrollWidth {sw} clientWidth {cw} scrollHeight {sh} "
                  f"{'OK' if sw <= cw else 'HORIZONTAL SCROLL'}")


if __name__ == "__main__":
    report_measures() if "measure" in sys.argv else shoot()
