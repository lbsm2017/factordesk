"""Render a ``FactorReport`` as one self-contained HTML file.

No scripts, no external fonts, stylesheets or images: inline CSS plus inline SVG built here.
Output is deterministic for a given report (nothing reads the clock or the environment).
Every dynamic string goes through ``html.escape``.
"""

from __future__ import annotations

import html
import math
from collections.abc import Callable, Sequence
from datetime import date
from pathlib import Path

from factordesk.report.schema import (
    FACTOR_NAMES,
    LABEL_TEXT,
    FactorReport,
    FactorStat,
    PriceSeries,
    RollingWindow,
)

FOOT = LABEL_TEXT["L-DESC"]
IDIO = "Idiosyncratic"
EXCLUSION_TEXT = {
    "multi_day_return": "return spans several factor days",
    "no_factor_row": "date not in the factor file",
    "price_missing": "price missing",
    "factor_missing": "factor value missing",
}
WIDE = "wide"
NARROW = "narrow"

# --------------------------------------------------------------------------------------------
# Styles. Tokens live on :root; the light theme is selected by prefers-color-scheme.
# Factor colours: Okabe-Ito hues (blue, orange, reddish purple, yellow) plus a neutral grey, kept
# away from the red/green pair that is reserved for sign. Light-theme values are darkened to keep
# >= 3:1 against the white surface.
# --------------------------------------------------------------------------------------------
CSS = """
:root{
  color-scheme:dark;
  --bg:#0e1115;--surface:#14181e;--surface-2:#191e25;--border:#2a313b;--grid:#222932;
  --ink:#dde2e9;--ink-2:#a3adba;--ink-3:#8791a0;
  --accent:#8fa8c8;--pos:#4cc38a;--neg:#f0705f;--warn:#e3ad3a;
  --f0:#56b4e9;--f1:#e69f00;--f2:#cc79a7;--f3:#e8df4a;--f4:#aab3bf;
  --tail:rgba(160,172,188,.10);
  --mono:ui-monospace,"Cascadia Mono","SF Mono",SFMono-Regular,Menlo,Consolas,monospace;
  --sans:system-ui,-apple-system,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif;
}
@media (prefers-color-scheme:light){
  :root{
    color-scheme:light;
    --bg:#f2f4f6;--surface:#ffffff;--surface-2:#f7f8fa;--border:#d3d8df;--grid:#e6e9ed;
    --ink:#1a2027;--ink-2:#46515f;--ink-3:#5b6676;
    --accent:#3f5f86;--pos:#14764a;--neg:#b3362a;--warn:#855600;
    --f0:#0072b2;--f1:#b86800;--f2:#a8508a;--f3:#8d8300;--f4:#5b6572;
    --tail:rgba(60,72,88,.07);
  }
}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--ink);font:13px/1.45 var(--sans)}
.num,td.n,th.n{font-family:var(--mono);font-variant-numeric:tabular-nums}
.sr-only{position:absolute;width:1px;height:1px;margin:-1px;padding:0;overflow:hidden;
  clip:rect(0 0 0 0);white-space:nowrap;border:0}
.wrap{max-width:1680px;margin:0 auto;padding:12px 16px 32px}
.top{display:flex;flex-wrap:wrap;align-items:baseline;gap:6px 16px;padding:4px 0 12px;
  border-bottom:1px solid var(--border);margin-bottom:12px}
.brand{font-size:12px;color:var(--ink-3);letter-spacing:.04em}
.brand i{display:inline-block;width:8px;height:8px;background:var(--accent);margin-right:6px}
h1{margin:0;font:600 22px/1.1 var(--mono);letter-spacing:.02em}
.top .meta{display:flex;flex-wrap:wrap;gap:4px 14px;color:var(--ink-2);font-size:12px;
  margin-left:auto}
.top .meta b{font-weight:500;color:var(--ink)}
.badge{display:inline-block;border:1px solid var(--border);padding:0 6px;font:11px/18px var(--mono);
  color:var(--ink-2);background:var(--surface-2)}
.badge.warn{color:var(--warn);border-color:var(--warn)}
a.badge{text-decoration:none}
a.badge:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
ul.list.cap{margin-top:6px}
.badge.ok{color:var(--ink-2)}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:1px;
  background:var(--border);border:1px solid var(--border);margin-bottom:12px}
.kpi{background:var(--surface);padding:8px 10px;min-width:0}
.kpi .l{font-size:11px;color:var(--ink-3);letter-spacing:.03em}
.kpi .v{font:500 19px/1.3 var(--mono);font-variant-numeric:tabular-nums;white-space:nowrap}
.kpi .v.sm{font-size:14px;line-height:1.75}
.kpi .s{font:11px/1.3 var(--mono);color:var(--ink-2);font-variant-numeric:tabular-nums}
.pos{color:var(--pos)}.neg{color:var(--neg)}.zero{color:var(--ink-2)}.warn{color:var(--warn)}
.callout{background:var(--surface);border:1px solid var(--warn);border-left-width:3px;
  padding:8px 10px;margin-bottom:12px;font-size:12.5px}
.callout p{margin:0}.callout p+p{margin-top:4px;color:var(--ink-2);font-size:11.5px}
.callout b{color:var(--warn);font-weight:600}
.callout a{color:var(--accent)}
.callout a:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.grid{display:grid;gap:12px;margin-bottom:12px}
.g-main{grid-template-columns:minmax(0,1.9fr) minmax(0,1fr)}
.g-two{grid-template-columns:minmax(0,1fr) minmax(0,1fr)}
.g-data{grid-template-columns:minmax(0,1fr) minmax(0,1fr)}
.panel{background:var(--surface);border:1px solid var(--border);min-width:0;display:flex;
  flex-direction:column}
.panel>header{display:flex;justify-content:space-between;align-items:baseline;gap:8px;
  padding:8px 10px;border-bottom:1px solid var(--border)}
.panel h2{margin:0;font:600 12.5px/1.3 var(--sans);letter-spacing:.03em}
.panel .sub{font-size:11px;color:var(--ink-3)}
.panel .body{padding:8px 10px;flex:1;min-width:0}
.panel .cap{margin:6px 0 0;font-size:11.5px;color:var(--ink-2)}
.panel .foot{margin:0;padding:5px 10px;border-top:1px solid var(--border);font-size:11px;
  color:var(--ink-3)}
.chart{display:block;width:100%;height:auto}
.v-narrow{display:none}
.g-two .chart{max-width:640px}
.p-betas .chart{max-width:560px}
@media (max-width:640px){.v-wide{display:none}.v-narrow{display:block}}
.t{font:11px var(--mono);fill:var(--ink-2)}
.tv{font:11px var(--mono);fill:var(--ink)}
.tm{font:10.5px var(--mono);fill:var(--ink-3)}
.tp{fill:var(--pos)}.tn{fill:var(--neg)}
.axis{stroke:var(--grid);stroke-width:1;fill:none}
.zero-line{stroke:var(--ink-3);stroke-width:1}
.fc0{fill:var(--f0)}.fc1{fill:var(--f1)}.fc2{fill:var(--f2)}.fc3{fill:var(--f3)}.fc4{fill:var(--f4)}
.sk0{stroke:var(--f0)}.sk1{stroke:var(--f1)}.sk2{stroke:var(--f2)}.sk3{stroke:var(--f3)}
.sk4{stroke:var(--f4)}
.empty{border:1px dashed var(--border);color:var(--ink-3);padding:18px 10px;text-align:center;
  font-size:12px}
.sm-grid{display:grid;gap:12px;grid-template-columns:repeat(auto-fill,minmax(250px,1fr))}
.card{border:1px solid var(--border);background:var(--surface-2);min-width:0}
.card header{display:flex;justify-content:space-between;align-items:baseline;gap:6px;
  padding:5px 8px;border-bottom:1px solid var(--border);font-size:12px}
.card header b{font-weight:600}
.card header span.r{font:10.5px var(--mono);color:var(--ink-2);text-align:right}
.sw{display:inline-block;width:9px;height:9px;margin-right:6px;vertical-align:baseline}
.sw0{background:var(--f0)}.sw1{background:var(--f1)}.sw2{background:var(--f2)}
.sw3{background:var(--f3)}.sw4{background:var(--f4)}
.card .cb{padding:4px 4px 2px}
dl.kv{display:grid;grid-template-columns:max-content minmax(0,1fr);gap:3px 14px;margin:0}
dl.kv dt{color:var(--ink-3)}
dl.kv dd{margin:0;font-family:var(--mono);font-variant-numeric:tabular-nums;
  overflow-wrap:anywhere}
h3{margin:12px 0 4px;font:600 11.5px var(--sans);color:var(--ink-2);letter-spacing:.03em}
h3:first-child{margin-top:0}
ul.list{margin:0;padding:0;list-style:none}
ul.list li{padding:4px 0;border-top:1px solid var(--grid)}
ul.list li:first-child{border-top:0}
.sev{display:inline-block;min-width:54px;margin-right:6px;font:11px var(--mono);color:var(--ink-3)}
.sev.warning,.sev.error{color:var(--warn)}
.tablewrap{overflow-x:auto}
table.dt{border-collapse:collapse;width:100%;font-size:12px}
table.dt th,table.dt td{padding:4px 8px;border-bottom:1px solid var(--grid);text-align:right;
  white-space:nowrap}
table.dt th:first-child,table.dt td:first-child{text-align:left}
table.dt th{color:var(--ink-3);font-weight:500}
table.dt td.rd,table.dt th.rd{text-align:left}
table.dt td.rd{white-space:normal;min-width:260px;color:var(--ink-2)}
.legend{display:flex;flex-wrap:wrap;gap:2px 14px;font-size:11.5px;color:var(--ink-2);
  margin:6px 0 0}
.legend .hatch{display:inline-block;width:12px;height:9px;margin-right:5px;
  border:1px solid var(--ink-3);
  background:repeating-linear-gradient(45deg,var(--ink-3) 0 1px,transparent 1px 4px)}
@media (max-width:1000px){.g-main,.g-two,.g-data{grid-template-columns:minmax(0,1fr)}}
@media (max-width:640px){
  .wrap{padding:8px 16px 24px}
  .top .meta{margin-left:0}
  h1{font-size:20px}
}
@media print{body{background:#fff}}
""".strip()


# --------------------------------------------------------------------------------------------
# Small formatting helpers
# --------------------------------------------------------------------------------------------
def esc(value: object) -> str:
    """HTML-escape any value (quotes included)."""
    return html.escape(str(value), quote=True)


def _fin(x: float | None) -> float | None:
    """Return ``x`` if it is a finite number, else None (handles None, NaN and +/-inf)."""
    if x is None or not math.isfinite(x):
        return None
    return float(x)


def _sign_fmt(
    x: float | None, digits: int, scale: float = 1.0, suffix: str = ""
) -> tuple[str, str]:
    """Format with an explicit +/- glyph. Returns (text, css class: pos|neg|zero)."""
    v = _fin(x)
    if v is None:
        return "n/a", "zero"
    s = f"{v * scale:.{digits}f}"
    body = s.lstrip("-")
    if not body.strip("0."):
        return f"{body}{suffix}", "zero"
    if s.startswith("-"):
        return f"-{body}{suffix}", "neg"
    return f"+{body}{suffix}", "pos"


def _signed_html(x: float | None, digits: int, scale: float = 1.0, suffix: str = "") -> str:
    """Sign-coloured number as an HTML span."""
    text, cls = _sign_fmt(x, digits, scale, suffix)
    return f'<span class="num {cls}">{esc(text)}</span>'


def _plain(x: float | None, digits: int, scale: float = 1.0, suffix: str = "") -> str:
    """Unsigned-colour number, ``n/a`` when not finite."""
    v = _fin(x)
    if v is None:
        return "n/a"
    return f"{v * scale:.{digits}f}{suffix}"


def _pval(x: float | None) -> str:
    """P-value with a floor so tiny values read as '<0.001'."""
    v = _fin(x)
    if v is None:
        return "n/a"
    return "<0.001" if v < 0.001 else f"{v:.3f}"


def _n(x: float) -> str:
    """Compact coordinate formatting for SVG."""
    s = f"{x:.1f}"
    return s[:-2] if s.endswith(".0") else s


def _empty(message: str) -> str:
    """Explicit 'insufficient data' state."""
    return f'<div class="empty" role="status">Insufficient data: {esc(message)}</div>'


def _decimals_for(step: float) -> int:
    """Smallest number of decimals that represents ``step`` exactly."""
    for d in range(0, 7):
        if abs(round(step, d) - step) < 1e-9 * max(1.0, abs(step)):
            return d
    return 6


def _nice_ticks(lo: float, hi: float, n: int = 4) -> tuple[list[float], float]:
    """Round-number ticks inside [lo, hi]. Returns (ticks, step); empty if not finite."""
    if not (math.isfinite(lo) and math.isfinite(hi)) or hi < lo:
        return [], 1.0
    if hi == lo:
        pad = abs(lo) * 0.05 or 1.0
        lo, hi = lo - pad, hi + pad
    span = hi - lo
    base = 10.0 ** (math.floor(math.log10(span / max(n, 1))) - 1)
    step = base * 100.0
    for m in (1.0, 2.0, 2.5, 5.0, 10.0, 20.0, 25.0, 50.0, 100.0):
        if span / (m * base) <= n + 0.5:
            step = m * base
            break
    first = math.ceil(lo / step - 1e-9)
    last = math.floor(hi / step + 1e-9)
    return [k * step for k in range(first, last + 1)], step


def _scale(d0: float, d1: float, r0: float, r1: float) -> Callable[[float], float]:
    """Linear scale; a degenerate domain maps to the middle of the range."""
    if d1 == d0:
        mid = (r0 + r1) / 2
        return lambda _v: mid
    k = (r1 - r0) / (d1 - d0)
    return lambda v: r0 + (v - d0) * k


def _path(points: Sequence[tuple[float, float] | None]) -> str:
    """SVG path data; ``None`` entries break the line (warm-up gaps)."""
    parts: list[str] = []
    pen = False
    for p in points:
        if p is None:
            pen = False
            continue
        parts.append(f"{'L' if pen else 'M'}{_n(p[0])} {_n(p[1])}")
        pen = True
    return " ".join(parts)


def _decimate[T](items: list[T], max_n: int) -> list[T]:
    """Deterministic stride decimation that always keeps the last element."""
    if len(items) <= max_n or max_n < 2:
        return items
    stride = math.ceil(len(items) / max_n)
    out = items[::stride]
    if out[-1] is not items[-1]:
        out.append(items[-1])
    return out


def _date_ticks(d0: date, d1: date, max_ticks: int) -> list[tuple[date, str]]:
    """Calendar ticks (years for long spans, months for short ones)."""
    days = (d1 - d0).days
    if days <= 0:
        return [(d0, d0.isoformat())]
    ticks: list[tuple[date, str]] = []
    years = days / 365.25
    if years >= 3:
        step = max(1, math.ceil(years / max_ticks))
        y = d0.year + (0 if d0 == date(d0.year, 1, 1) else 1)
        while y <= d1.year:
            ticks.append((date(y, 1, 1), str(y)))
            y += step
    else:
        months = days / 30.4
        step = next((k for k in (1, 2, 3, 6, 12) if months / k <= max_ticks), 12)
        y, m = d0.year, d0.month + (0 if d0.day == 1 else 1)
        m += (-(m - 1)) % step  # align to month 1, 1+step, ...
        while True:
            y, m = y + (m - 1) // 12, (m - 1) % 12 + 1
            cur = date(y, m, 1)
            if cur > d1:
                break
            ticks.append((cur, f"{y}-{m:02d}"))
            m += step
    return ticks


def _fidx(name: str, order: Sequence[str]) -> int:
    """Colour slot (0-4) for a factor: canonical position, else order of appearance."""
    if name in FACTOR_NAMES:
        return FACTOR_NAMES.index(name)
    return order.index(name) % 5 if name in order else 0


def _factor_order(report: FactorReport) -> list[str]:
    """Factor names in display order."""
    names = [f.name for f in report.regression.factors]
    return names or list(report.return_contribution.factors)


def _foot(report: FactorReport, caption: str, labels: Sequence[str]) -> str:
    """Panel footnote: the section caption followed by its standard labels (M0.9)."""
    texts = [report.label_text.get(k, LABEL_TEXT.get(k, "")) for k in labels]
    return " ".join(t for t in [caption, *texts] if t)


def _reliable(s: FactorStat) -> bool:
    return s.tag == "reliable"


def _ci_excludes_zero(s: FactorStat) -> bool:
    lo, hi = _fin(s.ci_low), _fin(s.ci_high)
    return lo is not None and hi is not None and (lo > 0 or hi < 0)


def _svg_open(w: float, h: float, uid: str, title: str) -> str:
    """Opening tag + accessible title. The title doubles as the aria-label."""
    return (
        f'<svg class="chart" viewBox="0 0 {_n(w)} {_n(h)}" role="img" aria-label="{esc(title)}" '
        f'aria-labelledby="{uid}-t"><title id="{uid}-t">{esc(title)}</title>'
    )


def _variants(builder: Callable[[int, str], str], wide: int, narrow: int, uid: str) -> str:
    """Emit a wide and a narrow rendering; CSS shows the one that suits the viewport."""
    w = builder(wide, f"{uid}-w")
    n = builder(narrow, f"{uid}-n")
    if w.startswith('<div class="empty"'):
        return w
    return f'<div class="v-wide">{w}</div><div class="v-narrow">{n}</div>'


def _panel(
    title: str, sub: str, body: str, foot: str | None = FOOT, cls: str = "", pid: str = ""
) -> str:
    """Standard bordered panel with optional footnote."""
    ident = f' id="{pid}"' if pid else ""
    sub_html = f'<span class="sub">{esc(sub)}</span>' if sub else ""
    foot_html = f'<p class="foot">{esc(foot)}</p>' if foot else ""
    return (
        f'<section class="panel {cls}"{ident}><header><h2>{esc(title)}</h2>{sub_html}</header>'
        f'<div class="body">{body}</div>{foot_html}</section>'
    )


# --------------------------------------------------------------------------------------------
# Charts
# --------------------------------------------------------------------------------------------
def _price_svg(ps: PriceSeries, ticker: str, w: int, uid: str) -> str:
    """Adjusted-close line; points after factor coverage are muted and labelled."""
    pts = [
        (d, v)
        for d, v in zip(ps.dates, ps.adj_close, strict=True)
        if _fin(v) is not None and v is not None
    ]
    if len(pts) < 2:
        return _empty("fewer than two price points")
    narrow = w < 500
    h = 190 if narrow else 270
    ml, mr, mt, mb = (40 if narrow else 48), 10, 10, 22
    d0, d1 = pts[0][0], pts[-1][0]
    xs = _scale(d0.toordinal(), d1.toordinal(), ml, w - mr)
    vals = [v for _, v in pts]
    ticks, _step = _nice_ticks(min(vals), max(vals), 4 if not narrow else 3)
    lo = min(min(vals), ticks[0] if ticks else min(vals))
    hi = max(max(vals), ticks[-1] if ticks else max(vals))
    if hi == lo:
        lo, hi = lo - 1, hi + 1
    ys = _scale(lo, hi, h - mb, mt)
    dec = _decimals_for(_step) if ticks else 0
    out = [_svg_open(w, h, uid, f"{ticker} adjusted close price over time")]
    for tv in ticks:
        y = ys(tv)
        out.append(f'<line class="axis" x1="{ml}" x2="{w - mr}" y1="{_n(y)}" y2="{_n(y)}"/>')
        out.append(
            f'<text class="tm" x="{ml - 6}" y="{_n(y + 3.5)}" text-anchor="end">{tv:.{dec}f}</text>'
        )
    for dt, label in _date_ticks(d0, d1, 4 if narrow else 7):
        x = xs(dt.toordinal())
        anchor = "end" if x > w - 24 else "middle"
        out.append(
            f'<line class="axis" x1="{_n(x)}" x2="{_n(x)}" y1="{h - mb}" y2="{h - mb + 4}"/>'
        )
        out.append(
            f'<text class="tm" x="{_n(x)}" y="{h - 6}" text-anchor="{anchor}">{esc(label)}</text>'
        )
    cov = ps.factor_coverage_end
    main = [(xs(d.toordinal()), ys(v)) for d, v in pts if d <= cov]
    tail = [(xs(d.toordinal()), ys(v)) for d, v in pts if d >= cov]
    if main and len(pts) > len(main):
        # tail starts from the last covered point so the line is continuous
        tail = [main[-1]] + [(xs(d.toordinal()), ys(v)) for d, v in pts if d > cov]
    if len(tail) > 1 and main:
        x_cov = main[-1][0]
        tail_mid = sum(y for _, y in tail) / len(tail)
        # keep the label clear of the line: bottom if the tail runs high, top otherwise
        label_y = h - mb - 6 if tail_mid < (mt + h - mb) / 2 else mt + 12
        out.append(
            f'<rect x="{_n(x_cov)}" y="{mt}" width="{_n(w - mr - x_cov)}" height="{h - mb - mt}" '
            'fill="var(--tail)"/>'
        )
        out.append(
            f'<line x1="{_n(x_cov)}" x2="{_n(x_cov)}" y1="{mt}" y2="{h - mb}" '
            'stroke="var(--ink-3)" stroke-dasharray="2 3"/>'
        )
        out.append(
            f'<text class="tm" x="{w - mr - 4}" y="{label_y}" text-anchor="end">'
            "no factor data</text>"
        )
    elif not main:
        out.append(
            f'<rect x="{ml}" y="{mt}" width="{w - mr - ml}" height="{h - mb - mt}" '
            'fill="var(--tail)"/>'
        )
        tail = [(xs(d.toordinal()), ys(v)) for d, v in pts]
    if len(main) > 1:
        out.append(
            f'<path d="{_path(_decimate(main, 700))}" fill="none" stroke="var(--ink)" '
            'stroke-width="1.5" stroke-linejoin="round"/>'
        )
    if len(tail) > 1:
        out.append(
            f'<path d="{_path(_decimate(tail, 300))}" fill="none" stroke="var(--ink-3)" '
            'stroke-width="1.5" stroke-dasharray="4 3" stroke-linejoin="round"/>'
        )
    out.append("</svg>")
    return "".join(out)


def _stat_points(stat: FactorStat, avg: float | None) -> list[float]:
    """Finite x-values a beta row needs on the axis."""
    cands = [stat.beta, stat.ci_low, stat.ci_high, avg, 0.0]
    return [v for v in (_fin(c) for c in cands) if v is not None]


def _betas_svg(report: FactorReport, w: int, uid: str) -> str:
    """Diverging beta bars, 95% CI whiskers, hatched when not BH-significant, avg marker."""
    stats = report.regression.factors
    if not stats or all(_fin(s.beta) is None for s in stats):
        return _empty("no factor betas available")
    order = _factor_order(report)
    avg_map = {a.name: _fin(a.mean) for a in report.average_beta.factors}
    allv = [v for s in stats for v in _stat_points(s, avg_map.get(s.name))]
    m = max(abs(v) for v in allv) * 1.08 or 1.0
    narrow = w < 400
    lc, rc = 50, (112 if narrow else 124)  # room for "z +151.8 reliable" right of the plot
    rowh, top, bot = 40, 6, 22
    h = top + rowh * len(stats) + bot
    xs = _scale(-m, m, lc, w - rc)
    out = [_svg_open(w, h, uid, "Factor betas with 95% confidence intervals")]
    out.append("<defs>")
    for i in range(5):
        out.append(
            f'<pattern id="{uid}-h{i}" width="5" height="5" patternUnits="userSpaceOnUse" '
            f'patternTransform="rotate(45)"><line x1="0" y1="0" x2="0" y2="5" class="sk{i}" '
            'stroke-width="1.8"/></pattern>'
        )
    out.append("</defs>")
    ticks, step = _nice_ticks(-m, m, 4)
    dec = _decimals_for(step) if ticks else 1
    for tv in ticks:
        x = xs(tv)
        out.append(f'<line class="axis" x1="{_n(x)}" x2="{_n(x)}" y1="{top}" y2="{h - bot}"/>')
        label = f"{tv:.{dec}f}" if abs(tv) > 1e-12 else "0"
        out.append(f'<text class="tm" x="{_n(x)}" y="{h - 7}" text-anchor="middle">{label}</text>')
    out.append(
        f'<line class="zero-line" x1="{_n(xs(0))}" x2="{_n(xs(0))}" y1="{top}" y2="{h - bot}"/>'
    )
    for r, s in enumerate(stats):
        i = _fidx(s.name, order)
        cy = top + rowh * r + 17
        out.append(f'<text class="tv" x="2" y="{_n(cy + 4)}">{esc(s.name)}</text>')
        beta = _fin(s.beta)
        if beta is None:
            out.append(
                f'<text class="tm" x="{w - 2}" y="{_n(cy + 4)}" text-anchor="end">n/a</text>'
            )
            continue
        x0, x1 = sorted((xs(0), xs(beta)))
        bw = max(x1 - x0, 1.0)
        tip = (
            f"{s.name}: beta {_plain(s.beta, 4)}, 95% CI {_plain(s.ci_low, 4)} to "
            f"{_plain(s.ci_high, 4)}, p {_pval(s.p)}, BH-adjusted p {_pval(s.p_adj_bh)}"
        )
        if not _reliable(s) and _ci_excludes_zero(s):
            tip += "; not significant after correcting for testing 5 betas"
        if _reliable(s):
            out.append(
                f'<rect class="fc{i}" x="{_n(x0)}" y="{_n(cy - 8)}" width="{_n(bw)}" height="16">'
                f"<title>{esc(tip)}</title></rect>"
            )
        else:
            out.append(
                f'<rect class="sk{i}" x="{_n(x0)}" y="{_n(cy - 8)}" width="{_n(bw)}" height="16" '
                f'fill="url(#{uid}-h{i})" stroke-width="1" stroke-opacity=".85">'
                f"<title>{esc(tip)}</title></rect>"
            )
        lo, hi = _fin(s.ci_low), _fin(s.ci_high)
        if lo is not None and hi is not None:
            xl, xh = xs(lo), xs(hi)
            for stroke, sw in (("var(--surface)", 3.6), ("var(--ink)", 1.3)):
                out.append(
                    f'<path d="M{_n(xl)} {_n(cy)}H{_n(xh)}M{_n(xl)} {_n(cy - 4)}V{_n(cy + 4)}'
                    f'M{_n(xh)} {_n(cy - 4)}V{_n(cy + 4)}" stroke="{stroke}" '
                    f'stroke-width="{sw}" fill="none"/>'
                )
        avg = avg_map.get(s.name)
        if avg is not None:
            ax = xs(avg)
            out.append(
                f'<path d="M{_n(ax)} {_n(cy + 9)}l4 4.5l-4 4.5l-4 -4.5z" fill="var(--surface)" '
                'stroke="var(--ink)" stroke-width="1.3"/>'
            )
        text, cls = _sign_fmt(beta, 3)
        out.append(
            f'<text class="t {"tp" if cls == "pos" else "tn" if cls == "neg" else ""}" '
            f'x="{w - 2}" y="{_n(cy - 2)}" text-anchor="end">{esc(text)}</text>'
        )
        z_text, _ = _sign_fmt(s.z, 1)
        tag = "reliable" if _reliable(s) else "noise"
        out.append(
            f'<text class="tm" x="{w - 2}" y="{_n(cy + 11)}" text-anchor="end">'
            f"z {esc(z_text)} {tag}</text>"
        )
    out.append("</svg>")
    return "".join(out)


def _betas_table(report: FactorReport) -> str:
    """Visually hidden data table: the accessible equivalent of the betas chart."""
    avg_map = {a.name: a for a in report.average_beta.factors}
    rows: list[str] = []
    for s in report.regression.factors:
        a = avg_map.get(s.name)
        rows.append(
            "<tr>"
            f"<th scope='row'>{esc(s.name)}</th><td>{_plain(s.beta, 4)}</td>"
            f"<td>{_plain(s.ci_low, 4)} to {_plain(s.ci_high, 4)}</td>"
            f"<td>{_pval(s.p)}</td><td>{_pval(s.p_adj_bh)}</td>"
            f"<td>{'reliable' if _reliable(s) else 'noise'}</td>"
            f"<td>{_plain(a.mean if a else None, 4)}</td></tr>"
        )
    return (
        '<div class="sr-only"><table id="betas-data"><caption>Full-sample factor betas</caption>'
        "<thead><tr><th>Factor</th><th>Beta</th><th>95% CI</th><th>p</th><th>BH-adjusted p</th>"
        f"<th>Result</th><th>Mean rolling {report.average_beta.window}d beta</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table></div>"
    )


def _extent_axis(
    lo: float, hi: float, a0: float, a1: float, n: int
) -> tuple[Callable[[float], float], list[float], int]:
    """Scale for [lo, hi] (ticks included) with its tick values and decimals."""
    ticks, step = _nice_ticks(lo, hi, n)
    if ticks:
        lo, hi = min(lo, ticks[0]), max(hi, ticks[-1])
    return _scale(lo, hi, a0, a1), ticks, _decimals_for(step) if ticks else 1


def _waterfall_svg(report: FactorReport, w: int, uid: str) -> str:
    """Horizontal waterfall: each factor, then alpha, summing to the annualised mean excess."""
    rc = report.return_contribution
    order = _factor_order(report)
    rows: list[tuple[str, float | None, int | None, str]] = [
        (n, _fin(rc.factors.get(n)), _fidx(n, order), "factor") for n in order
    ]
    rows.append(("Alpha", _fin(rc.alpha), None, "alpha"))
    total = _fin(rc.total_annualised_mean_excess_return)
    if all(v is None for _, v, _, _ in rows) and total is None:
        return _empty("no return attribution available")
    # cumulative bounds
    bounds: list[tuple[float, float] | None] = []
    cum = 0.0
    for _, v, _, _ in rows:
        if v is None:
            bounds.append(None)
            continue
        bounds.append((cum, cum + v))
        cum += v
    extent = [0.0, cum] + ([total] if total is not None else [])
    extent += [b for pair in bounds if pair for b in pair]
    lo, hi = min(extent) * 100, max(extent) * 100
    if hi - lo < 1e-9:
        lo, hi = lo - 1, hi + 1
    lo, hi = lo - (hi - lo) * 0.03, hi + (hi - lo) * 0.03
    narrow = w < 400
    lc, rcw = 52, 64
    rowh, top, bot = 28, 4, 22
    n_rows = len(rows) + 1
    h = top + rowh * n_rows + bot
    xs, ticks, dec = _extent_axis(lo, hi, lc, w - rcw, 3 if narrow else 5)
    out = [_svg_open(w, h, uid, "Annualised return contribution by factor, alpha and total")]
    for tv in ticks:
        x = xs(tv)
        out.append(f'<line class="axis" x1="{_n(x)}" x2="{_n(x)}" y1="{top}" y2="{h - bot}"/>')
        out.append(
            f'<text class="tm" x="{_n(x)}" y="{h - 7}" text-anchor="middle">{tv:.{dec}f}%</text>'
        )
    out.append(
        f'<line class="zero-line" x1="{_n(xs(0))}" x2="{_n(xs(0))}" y1="{top}" y2="{h - bot}"/>'
    )
    prev_end: tuple[float, float] | None = None
    for r, (name, v, idx, kind) in enumerate(rows):
        cy = top + rowh * r + rowh / 2
        out.append(f'<text class="tv" x="2" y="{_n(cy + 4)}">{esc(name)}</text>')
        pair = bounds[r]
        if v is None or pair is None:
            out.append(
                f'<text class="tm" x="{w - 2}" y="{_n(cy + 4)}" text-anchor="end">n/a</text>'
            )
            continue
        xa, xb = xs(pair[0] * 100), xs(pair[1] * 100)
        x0, x1 = sorted((xa, xb))
        fill = f"fc{idx}" if idx is not None else ""
        style = ' fill="var(--accent)"' if kind == "alpha" else ""
        out.append(
            f'<rect class="{fill}" x="{_n(x0)}" y="{_n(cy - 8)}" width="{_n(max(x1 - x0, 1))}" '
            f'height="16"{style}/>'
        )
        if prev_end is not None:
            out.append(
                f'<line x1="{_n(prev_end[0])}" x2="{_n(xa)}" y1="{_n(prev_end[1])}" '
                f'y2="{_n(cy - 8)}" stroke="var(--ink-3)" stroke-width="1" '
                'stroke-dasharray="2 2"/>'
            )
        prev_end = (xb, cy + 8)
        text, cls = _sign_fmt(v, 2, 100, "%")
        out.append(
            f'<text class="t {"tp" if cls == "pos" else "tn" if cls == "neg" else ""}" '
            f'x="{w - 2}" y="{_n(cy + 4)}" text-anchor="end">{esc(text)}</text>'
        )
    # total row
    cy = top + rowh * len(rows) + rowh / 2
    out.append(
        f'<line x1="2" x2="{w - 2}" y1="{_n(cy - rowh / 2)}" y2="{_n(cy - rowh / 2)}" '
        'stroke="var(--border)"/>'
    )
    out.append(f'<text class="tv" x="2" y="{_n(cy + 4)}" font-weight="600">Total</text>')
    if total is None:
        out.append(f'<text class="tm" x="{w - 2}" y="{_n(cy + 4)}" text-anchor="end">n/a</text>')
    else:
        x0, x1 = sorted((xs(0), xs(total * 100)))
        out.append(
            f'<rect x="{_n(x0)}" y="{_n(cy - 8)}" width="{_n(max(x1 - x0, 1))}" height="16" '
            'fill="var(--ink-2)"/>'
        )
        text, cls = _sign_fmt(total, 2, 100, "%")
        out.append(
            f'<text class="tv {"tp" if cls == "pos" else "tn" if cls == "neg" else ""}" '
            f'x="{w - 2}" y="{_n(cy + 4)}" text-anchor="end" font-weight="600">{esc(text)}</text>'
        )
    out.append("</svg>")
    return "".join(out)


def _risk_svg(report: FactorReport, w: int, uid: str) -> str:
    """Horizontal bars of variance share, sorted, with an idiosyncratic row."""
    rk = report.risk_contribution
    order = _factor_order(report)
    items: list[tuple[str, float | None, int | None]] = [
        (n, _fin(rk.factors.get(n)), _fidx(n, order)) for n in order
    ]
    if all(v is None for _, v, _ in items) and _fin(rk.idiosyncratic) is None:
        return _empty("no risk attribution available")
    # Factors by share descending (ties: canonical order), idiosyncratic always last (M7).
    rank = {name: i for i, name in enumerate(rk.order)}
    items.sort(key=lambda it: (it[1] is None, rank.get(it[0], len(rank)), -(it[1] or 0.0)))
    items.append((IDIO, _fin(rk.idiosyncratic), None))
    detail = {d.name: d for d in rk.details}
    vals = [v * 100 for _, v, _ in items if v is not None]
    lo, hi = min(0.0, min(vals)), max(0.0, max(vals))
    if hi - lo < 1e-9:
        hi = lo + 1
    hi = hi + (hi - lo) * 0.03
    lo = lo - (hi - lo) * 0.03 if lo < 0 else lo
    lc, rcw = 86, 52
    rowh, top, bot = 28, 4, 22
    h = top + rowh * len(items) + bot
    xs, ticks, dec = _extent_axis(lo, hi, lc, w - rcw, 3 if w < 400 else 5)
    out = [_svg_open(w, h, uid, "Share of total variance by factor and idiosyncratic")]
    for tv in ticks:
        x = xs(tv)
        out.append(f'<line class="axis" x1="{_n(x)}" x2="{_n(x)}" y1="{top}" y2="{h - bot}"/>')
        out.append(
            f'<text class="tm" x="{_n(x)}" y="{h - 7}" text-anchor="middle">{tv:.{dec}f}%</text>'
        )
    out.append(
        f'<line class="zero-line" x1="{_n(xs(0))}" x2="{_n(xs(0))}" y1="{top}" y2="{h - bot}"/>'
    )
    for r, (name, v, idx) in enumerate(items):
        cy = top + rowh * r + rowh / 2
        out.append(f'<text class="tv" x="2" y="{_n(cy + 4)}">{esc(name)}</text>')
        if v is None:
            out.append(
                f'<text class="tm" x="{w - 2}" y="{_n(cy + 4)}" text-anchor="end">n/a</text>'
            )
            continue
        x0, x1 = sorted((xs(0), xs(v * 100)))
        bw = max(x1 - x0, 1.0)
        d = detail.get(name)
        tip = f"{name}: {v * 100:.2f}% of variance"
        if d is not None:
            tip += (
                f"; beta {_plain(d.beta, 3)}, factor volatility {_plain(d.sigma_annual, 1, 100)}%"
                f" a year, correlation with the systematic return {_plain(d.rho_sys, 2)}"
            )
        if idx is None:
            out.append(
                f'<rect x="{_n(x0)}" y="{_n(cy - 8)}" width="{_n(bw)}" height="16" fill="none" '
                f'stroke="var(--ink-2)" stroke-dasharray="3 2"><title>{esc(tip)}</title></rect>'
            )
        else:
            out.append(
                f'<rect class="fc{idx}" x="{_n(x0)}" y="{_n(cy - 8)}" width="{_n(bw)}" '
                f'height="16"><title>{esc(tip)}</title></rect>'
            )
        label = f"{v * 100:.2f}"
        if label == "-0.00":
            label = "0.00"
        cls = ' class="t tn"' if label.startswith("-") else ' class="t"'
        out.append(f'<text{cls} x="{w - 2}" y="{_n(cy + 4)}" text-anchor="end">{label}%</text>')
    out.append("</svg>")
    return "".join(out)


def _rolling_svg(
    name: str, idx: int, wins: list[RollingWindow], full_beta: float | None, uid: str
) -> str:
    """One small multiple: all windows overlaid for a single factor (thicker = longer window)."""
    w, h = 320, 132
    ml, mr, mt, mb = 36, 8, 8, 20
    series: list[tuple[int, list[tuple[date, float | None]]]] = []
    band: list[tuple[date, float, float]] = []
    for win in sorted(wins, key=lambda x: -x.window):
        beta = win.betas.get(name)
        if beta is None:
            continue
        series.append((win.window, [(d, _fin(v)) for d, v in zip(win.dates, beta, strict=True)]))
        se = win.se.get(name)
        z = win.ci_z
        if not band and se is not None and z is not None:  # band for the longest window only
            for d, b, s in zip(win.dates, beta, se, strict=True):
                bv, sv = _fin(b), _fin(s)
                if bv is not None and sv is not None:
                    band.append((d, bv - z * sv, bv + z * sv))
    finite = [(d, v) for _, s in series for d, v in s if v is not None]
    if len(finite) < 2:
        return f'<div class="empty" role="status">Insufficient data: {esc(name)} warm-up</div>'
    dates = [d for d, _ in finite]
    d0, d1 = min(dates), max(dates)
    vals = [v for _, v in finite] + [x for _, lo, hi in band for x in (lo, hi)]
    if full_beta is not None:
        vals.append(full_beta)
    ys, ticks, dec = _extent_axis(min(vals), max(vals), h - mb, mt, 3)
    xs = _scale(d0.toordinal(), d1.toordinal(), ml, w - mr)
    out = [
        _svg_open(
            w,
            h,
            uid,
            f"Rolling beta to {name}, windows of "
            + " and ".join(str(s[0]) for s in series)
            + " trading days",
        )
    ]
    for tv in ticks:
        y = ys(tv)
        out.append(f'<line class="axis" x1="{ml}" x2="{w - mr}" y1="{_n(y)}" y2="{_n(y)}"/>')
        out.append(
            f'<text class="tm" x="{ml - 5}" y="{_n(y + 3.5)}" text-anchor="end">{tv:.{dec}f}</text>'
        )
    for dt, label in _date_ticks(d0, d1, 4):
        x = xs(dt.toordinal())
        out.append(
            f'<text class="tm" x="{_n(x)}" y="{h - 6}" '
            f'text-anchor="{"end" if x > w - 24 else "middle"}">{esc(label)}</text>'
        )
    if len(band) > 1:
        thin = _decimate(band, 400)
        upper = [(xs(d.toordinal()), ys(hi)) for d, _, hi in thin]
        lower = [(xs(d.toordinal()), ys(lo)) for d, lo, _ in reversed(thin)]
        out.append(
            f'<path d="{_path([*upper, *lower])} Z" class="fc{idx}" fill-opacity=".16" '
            'stroke="none"/>'
        )
    if full_beta is not None:
        y = ys(full_beta)
        out.append(
            f'<line x1="{ml}" x2="{w - mr}" y1="{_n(y)}" y2="{_n(y)}" stroke="var(--ink-3)" '
            'stroke-dasharray="2 3"/>'
        )
    for rank, (_, s) in enumerate(series):
        pts = [None if v is None else (xs(d.toordinal()), ys(v)) for d, v in s]
        width, op = ("1.8", "1") if rank == 0 else ("1", ".55")
        out.append(
            f'<path d="{_path(_decimate(pts, 500))}" fill="none" class="sk{idx}" '
            f'stroke-width="{width}" stroke-opacity="{op}" stroke-linejoin="round"/>'
        )
    out.append("</svg>")
    return "".join(out)


# --------------------------------------------------------------------------------------------
# Sections
# --------------------------------------------------------------------------------------------
def _audit_counts(report: FactorReport) -> tuple[int, int, int]:
    """(errors, warnings, infos)."""
    f = report.data.audit_findings
    return (
        sum(1 for x in f if x.severity == "error"),
        sum(1 for x in f if x.severity == "warning"),
        sum(1 for x in f if x.severity == "info"),
    )


def _header(report: FactorReport) -> str:
    """Ticker, as-of, factor data end and data-lag badge."""
    d = report.data
    as_of = report.generated_at.date()
    lag = (as_of - d.factors_last_date).days
    tone = "ok" if lag <= 40 else "warn"
    word = "current" if lag <= 40 else "lagging"
    n_warn = len(report.warnings)
    warn_badge = (
        f'<a class="badge warn" href="#warnings">{n_warn} warning{"s" if n_warn != 1 else ""}</a>'
        if n_warn
        else ""
    )
    return (
        '<header class="top"><span class="brand"><i></i>factordesk</span>'
        f"<h1>{esc(report.ticker)}</h1>"
        '<span class="brand">Fama-French 5-factor report</span>'
        '<div class="meta">'
        f'<span>As of <b class="num">{esc(as_of.isoformat())}</b></span>'
        f'<span>Factors through <b class="num">{esc(d.factors_last_date.isoformat())}</b></span>'
        f'<span class="badge {tone}" title="Days between report date and last factor date">'
        f"Data lag {lag}d &middot; {word}</span>{warn_badge}</div></header>"
    )


def _kpis(report: FactorReport) -> str:
    """KPI strip."""
    rg, d = report.regression, report.data
    errs, warns, infos = _audit_counts(report)
    if errs:
        audit, tone, sub = f"{errs} error{'s' if errs != 1 else ''}", "warn", f"{warns} warn"
    elif warns:
        audit, tone, sub = f"{warns} warning{'s' if warns != 1 else ''}", "warn", f"{infos} info"
    else:
        audit, tone, sub = "Clean", "zero", f"{infos} info"
    z_text, _ = _sign_fmt(rg.alpha_z, 2)
    alpha_tag = rg.alpha_tag or "n/a"

    def tile(label: str, value: str, sub_html: str, small: bool = False) -> str:
        cls = "v sm" if small else "v"
        return (
            f'<div class="kpi"><div class="l">{esc(label)}</div><div class="{cls}">{value}</div>'
            f'<div class="s">{sub_html}</div></div>'
        )

    return (
        '<div class="kpis">'
        + tile(
            "Alpha, annualised",
            _signed_html(rg.alpha_annual, 2, 100, "%"),
            f"z {esc(z_text)} &middot; p {_pval(rg.alpha_p)} &middot; {esc(alpha_tag)}",
        )
        + tile("R²", f'<span class="num">{_plain(rg.r2, 4)}</span>', "explained variance")
        + tile(
            "Residual vol",
            f'<span class="num">{_plain(rg.sigma_e_annual, 2, 100, "%")}</span>',
            f"adj. R² {_plain(rg.adj_r2, 4)}",
        )
        + tile(
            "Observations",
            f'<span class="num">{d.n_obs:,}</span>',
            f"HAC lags {rg.hac_lags}",
        )
        + tile(
            "Window",
            f'<span class="num">{esc(d.actual_start.isoformat())}</span>',
            f"to {esc(d.actual_end.isoformat())}",
            small=True,
        )
        + tile("Data audit", f'<span class="num {tone}">{esc(audit)}</span>', esc(sub), small=True)
        + "</div>"
    )


def _gate_callout(report: FactorReport) -> str:
    """Visible caveat when the residual quality gate fired (methodology M3.6)."""
    gate, five = report.quality_gate, report.five_day_regression
    if not gate.fired or not gate.message:
        return ""
    detail = ""
    if five.status == "ok":
        z_text, _ = _sign_fmt(five.alpha_z, 2)
        detail = (
            f"<p>5-day estimate ({five.n_blocks:,} blocks): alpha "
            f"{esc(_sign_fmt(five.alpha_annual, 2, 100, '%')[0])} a year, z {esc(z_text)}, "
            f"p {_pval(five.alpha_p)}, {esc(five.alpha_tag or 'n/a')}; R² {_plain(five.r2, 4)}. "
            'Full table under <a href="#detail">Regression detail</a>.</p>'
        )
    elif five.reason:
        detail = f"<p>5-day estimate: {esc(five.reason)}.</p>"
    return (
        '<div class="callout" role="note" id="quality">'
        f"<p><b>Data quality.</b> {esc(gate.message)}</p>{detail}</div>"
    )


def _price_panel(report: FactorReport) -> str:
    """Price chart with the post-coverage tail muted."""
    ps = report.price_series
    body = _variants(lambda w, u: _price_svg(ps, report.ticker, w, u), 760, 340, "px")
    tail_n = sum(1 for d in ps.dates if d > ps.factor_coverage_end)
    cap = (
        f"Muted dashed tail: {tail_n} price days after factor coverage "
        f"({esc(ps.factor_coverage_end.isoformat())}); not used in any statistic."
        if tail_n
        else "Price history is fully covered by factor data."
    )
    return _panel(
        f"{report.ticker} adjusted close",
        "price units",
        body + f'<p class="cap">{cap}</p>',
        foot="Adjusted for splits and dividends. Charted for context only.",
        pid="price",
    )


def _betas_panel(report: FactorReport) -> str:
    """Betas panel with legend, interpretation of reliable betas, and hidden table."""
    rg = report.regression
    body = _variants(lambda w, u: _betas_svg(report, w, u), 440, 340, "bt")
    legend = (
        '<div class="legend"><span>Bar: full-sample beta</span><span>Line: 95% HAC CI</span>'
        f"<span>&#9671; mean rolling {report.average_beta.window}d beta</span>"
        '<span><i class="hatch"></i>noise (not significant after BH)</span></div>'
    )
    flagged = [s.name for s in rg.factors if not _reliable(s) and _ci_excludes_zero(s)]
    extra = (
        f'<p class="cap">{esc(", ".join(flagged))}: the interval excludes zero, but the beta is '
        "not significant after correcting for testing 5 betas.</p>"
        if flagged
        else ""
    )
    return _panel(
        "Factor betas",
        "full sample, decimal sensitivity",
        body + legend + extra + _betas_table(report),
        foot=_foot(report, rg.caption, rg.labels),
        cls="p-betas",
        pid="betas",
    )


def _return_panel(report: FactorReport) -> str:
    """Return contribution waterfall, the identity check and the memo rows."""
    rc = report.return_contribution
    res = _fin(rc.identity_residual)
    resid = _fin(rc.residual)
    cap = "Factors + alpha + residual = total."
    if resid is not None:
        cap += f" Residual {resid:.1e} (0 by construction)."
    if res is not None:
        cap += f" Identity check {res:.1e}."
    memo = "".join(f"<li>{esc(m)}</li>" for m in rc.memo)
    body = _variants(lambda w, u: _waterfall_svg(report, w, u), 560, 340, "wf")
    return _panel(
        "Return contribution",
        "% per year of mean excess return",
        body
        + f'<p class="cap">{esc(cap)}</p>'
        + (f'<h3>Memo (not part of any sum)</h3><ul class="list cap">{memo}</ul>' if memo else ""),
        foot=_foot(report, rc.caption, rc.labels),
        pid="return",
    )


def _risk_panel(report: FactorReport) -> str:
    """Risk contribution bars plus the M7 sentences."""
    rk = report.risk_contribution
    res = _fin(rk.sums_to_one_residual)
    cap = "Euler shares of variance; idiosyncratic shown last."
    if res is not None:
        cap += f" Sum check {res:.1e}."
    vol = _fin(rk.total_vol_annual)
    if vol is not None:
        cap += f" Total volatility {vol * 100:.2f}% a year."
    sentences = "".join(f"<li>{esc(t)}</li>" for t in rk.sentences)
    body = _variants(lambda w, u: _risk_svg(report, w, u), 560, 340, "rk")
    return _panel(
        "Risk contribution",
        "share of total variance",
        body
        + f'<p class="cap">{esc(cap)}</p>'
        + (f'<ul class="list cap">{sentences}</ul>' if sentences else ""),
        foot=_foot(report, rk.caption, rk.labels),
        pid="risk",
    )


def _average_table(report: FactorReport) -> str:
    """Average-beta table (M5): distribution of the primary window's rolling betas."""
    ab = report.average_beta
    if ab.status != "ok" or not ab.factors:
        return _empty(ab.reason or "no average beta")
    rows = "".join(
        f"<tr><td>{esc(a.name)}</td><td class='n'>{_signed_html(a.full_sample_beta, 3)}</td>"
        f"<td class='n'>{_signed_html(a.mean, 3)}</td><td class='n'>{_plain(a.sd, 3)}</td>"
        f"<td class='n'>{_plain(a.p10, 3)}</td><td class='n'>{_plain(a.p90, 3)}</td>"
        f"<td class='n'>{_plain(a.min, 3)}</td><td class='n'>{_plain(a.max, 3)}</td>"
        f"<td class='n'>{_plain(a.share_positive, 0, 100, '%')}</td></tr>"
        for a in ab.factors
    )
    return (
        f"<h3>Average {ab.window}-day beta ({ab.n_stamps:,} windows)</h3>"
        '<div class="tablewrap"><table class="dt"><thead><tr><th>Factor</th><th>Full sample</th>'
        "<th>Mean</th><th>SD</th><th>P10</th><th>P90</th><th>Min</th><th>Max</th>"
        f"<th>Share &gt; 0</th></tr></thead><tbody>{rows}</tbody></table></div>"
        f'<p class="cap">{esc(ab.caption)}</p>'
    )


def _rolling_panel(report: FactorReport) -> str:
    """Rolling-beta small multiples with the pointwise band, plus the average-beta table."""
    wins = [w for w in report.rolling if w.dates]
    order = _factor_order(report)
    missing = "".join(
        f'<p class="cap">{w.window}-day window: {esc(w.reason)}.</p>'
        for w in report.rolling
        if w.status != "ok" and w.reason
    )
    if not wins or not order:
        return _panel(
            "Rolling betas", "", _empty("no rolling-beta series") + missing, pid="rolling"
        )
    full = {s.name: _fin(s.beta) for s in report.regression.factors}
    longest = max(wins, key=lambda w: w.window)
    cards: list[str] = []
    for n, name in enumerate(order):
        idx = _fidx(name, order)
        series = longest.betas.get(name, [])
        last = next((v for v in reversed(series) if _fin(v) is not None), None)
        now_txt = _sign_fmt(last, 2)[0]
        full_txt = _sign_fmt(full.get(name), 2)[0]
        right = f"{longest.window}d last {now_txt} &middot; full {full_txt}"
        svg = _rolling_svg(name, idx, wins, full.get(name), f"ro{n}")
        cards.append(
            f'<div class="card"><header><b><i class="sw sw{idx}"></i>{esc(name)}</b>'
            f'<span class="r">{right}</span></header><div class="cb">{svg}</div></div>'
        )
    by_len = sorted(wins, key=lambda w: -w.window)
    legend = (
        '<div class="legend"><span>Thick line: '
        + esc(" / ".join(f"{w.window}d" for w in by_len[:1]))
        + " with its 95% band</span><span>Thin, lighter: "
        + esc(" / ".join(f"{w.window}d" for w in by_len[1:]) or "n/a")
        + "</span><span>Dashed: full-sample beta</span>"
        "<span>Gaps: warm-up (trailing windows only)</span></div>"
    )
    caption = longest.caption + (
        " The thin "
        + ", ".join(f"{w.window}-day" for w in by_len[1:])
        + " line works the same way."
        if len(by_len) > 1
        else ""
    )
    return _panel(
        "Rolling betas",
        "trailing windows, trading days",
        f'<div class="sm-grid">{"".join(cards)}</div>{legend}{missing}{_average_table(report)}',
        foot=_foot(report, caption, longest.labels),
        pid="rolling",
    )


def _dates_text(dates: Sequence[date], limit: int = 6) -> str:
    """Up to ``limit`` ISO dates, then a count of the rest."""
    if not dates:
        return ""
    shown = ", ".join(d.isoformat() for d in dates[:limit])
    more = len(dates) - limit
    return f" Dates: {shown}" + (f" and {more} more." if more > 0 else ".")


def _data_panel(report: FactorReport) -> str:
    """Requested vs actual dates, exclusions, uncovered tail, audit findings, caveats."""
    d = report.data
    reasons = ", ".join(
        f"{EXCLUSION_TEXT.get(k, k)} {v}" for k, v in sorted(d.excluded_by_reason.items())
    )
    unc = d.uncovered
    tail = (
        f"{unc.n:,} days, {esc(unc.first)} to {esc(unc.last)}; raw compounded return "
        f"{_plain(unc.compounded_return, 2, 100, '%')}"
        if unc.n
        else "none"
    )
    downloaded = (
        esc(d.factors_downloaded_at.strftime("%Y-%m-%d %H:%M")) + " UTC"
        if d.factors_downloaded_at
        else "not recorded (factors supplied directly)"
    )
    kv = (
        '<dl class="kv">'
        f"<dt>Requested</dt><dd>{esc(d.requested_start)} to {esc(d.requested_end)}</dd>"
        f"<dt>Actual sample</dt><dd>{esc(d.actual_start)} to {esc(d.actual_end)}</dd>"
        f"<dt>Observations</dt><dd>{d.n_obs:,}</dd>"
        f"<dt>Excluded rows</dt><dd>{d.n_excluded:,}{' (' + esc(reasons) + ')' if reasons else ''}"
        "</dd>"
        f"<dt>After factor data</dt><dd>{tail}</dd>"
        f"<dt>Before factor data</dt><dd>{d.dropped_price_dates_before_factors:,} days</dd>"
        f"<dt>Factors through</dt><dd>{esc(d.factors_last_date)} "
        f"({d.factors_days_behind} days before the report date)</dd>"
        f"<dt>Factors downloaded</dt><dd>{downloaded}</dd>"
        f"<dt>Price source</dt><dd>{esc(d.price_source)}</dd>"
        f"<dt>Factor source</dt><dd>{esc(d.factors_source_url)}</dd>"
        f"<dt>Schema</dt><dd>v{esc(report.schema_version)}, generated "
        f"{esc(report.generated_at.strftime('%Y-%m-%d %H:%M'))} UTC</dd></dl>"
    )
    if d.audit_findings:
        items = "".join(
            f'<li><span class="sev {esc(f.severity)}">{esc(f.severity)}</span>'
            f'<span class="num">{esc(f.code)}</span> {esc(f.message)}'
            f"{esc(_dates_text(f.dates))}</li>"
            for f in d.audit_findings
        )
        findings = f'<ul class="list">{items}</ul>'
    else:
        findings = '<p class="cap">No audit findings.</p>'
    warnings = (
        '<ul class="list">'
        + "".join(
            f'<li><span class="sev warning">{esc(w.code)}</span> {esc(w.message)}</li>'
            for w in report.warnings
        )
        + "</ul>"
        if report.warnings
        else '<p class="cap">No warnings.</p>'
    )
    notes = (
        '<ul class="list">' + "".join(f"<li>{esc(n)}</li>" for n in report.notes) + "</ul>"
        if report.notes
        else '<p class="cap">No caveats supplied.</p>'
    )
    left = _panel("Data coverage", "requested vs actual", kv, foot=None, pid="data")
    right = _panel(
        "Warnings, audit and caveats",
        f"audit: {d.audit_status}",
        f'<h3 id="warnings">Warnings</h3>{warnings}<h3>Audit findings</h3>{findings}'
        f"<h3>Caveats</h3>{notes}",
        foot=None,
        pid="audit",
    )
    return f'<div class="grid g-data">{left}{right}</div>'


def _detail_panel(report: FactorReport) -> str:
    """Full regression table, including VIF and collinearity notes."""
    rg = report.regression
    rows: list[str] = []
    a_z, _ = _sign_fmt(rg.alpha_z, 2)
    a_ci = (
        f"{_plain(rg.alpha_ci_low_annual, 2, 100, '%')} to "
        f"{_plain(rg.alpha_ci_high_annual, 2, 100, '%')}"
    )
    rows.append(
        "<tr><td>Alpha (annual)</td>"
        f'<td class="n">{_signed_html(rg.alpha_annual, 2, 100, "%")}</td>'
        f'<td class="n">{_plain(rg.alpha_se_annual, 2, 100, "%")}</td>'
        f'<td class="n">{esc(a_z)}</td><td class="n">{_pval(rg.alpha_p)}</td>'
        f'<td class="n">single test</td><td class="n">{esc(a_ci)}</td><td class="n">n/a</td>'
        f'<td class="n">{esc(rg.alpha_tag or "n/a")}</td></tr>'
    )
    for s in rg.factors:
        ci = f"{_plain(s.ci_low, 3)} to {_plain(s.ci_high, 3)}"
        vif = _plain(rg.vif.get(s.name), 2)
        rows.append(
            f"<tr><td>{esc(s.name)}</td><td class='n'>{_signed_html(s.beta, 4)}</td>"
            f"<td class='n'>{_plain(s.se, 4)}</td>"
            f"<td class='n'>{esc(_sign_fmt(s.z, 2)[0])}</td><td class='n'>{_pval(s.p)}</td>"
            f"<td class='n'>{_pval(s.p_adj_bh)}</td><td class='n'>{esc(ci)}</td>"
            f"<td class='n'>{vif}</td><td class='n'>{esc(s.tag or 'n/a')}</td></tr>"
        )
    table = (
        '<div class="tablewrap"><table class="dt"><thead><tr><th>Term</th><th>Coef</th>'
        "<th>HAC se</th><th>z</th><th>p</th><th>p (BH)</th><th>95% CI</th><th>VIF</th>"
        f"<th>Tag</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div>"
    )
    pairs = ", ".join(f"{p.a}/{p.b} {p.corr:+.2f}" for p in rg.high_corr_pairs)
    cap = (
        f"R² {_plain(rg.r2, 4)}, adjusted {_plain(rg.adj_r2, 4)}; residual volatility "
        f"{_plain(rg.sigma_e_annual, 2, 100, '%')} a year. Newey-West lags {rg.hac_lags}. "
        f"Condition number of the factor correlation matrix {_plain(rg.condition_number, 2)}"
        + (f"; pairs with |correlation| above 0.6: {pairs}." if pairs else ".")
    )
    sentence = f'<p class="cap">{esc(rg.alpha_sentence)}</p>' if rg.alpha_sentence else ""
    reads = [s.interpretation for s in rg.factors if s.interpretation]
    reading = (
        "<h3>Reading the reliable betas</h3>"
        '<ul class="list cap">' + "".join(f"<li>{esc(t)}</li>" for t in reads) + "</ul>"
        if reads
        else ""
    )
    return _panel(
        "Regression detail",
        "OLS with intercept, Newey-West HAC standard errors",
        table
        + f'<p class="cap">{esc(cap)}</p>'
        + sentence
        + reading
        + _five_day_table(report)
        + _diagnostics_table(report),
        foot=_foot(report, rg.caption, rg.labels),
        pid="detail",
    )


def _five_day_table(report: FactorReport) -> str:
    """The 5-day estimate of M3.6, shown only when the quality gate fired."""
    five = report.five_day_regression
    if five.status != "ok":
        return ""
    a_ci = (
        f"{_plain(five.alpha_ci_low_annual, 2, 100, '%')} to "
        f"{_plain(five.alpha_ci_high_annual, 2, 100, '%')}"
    )
    rows = [
        "<tr><td>Alpha (annual)</td>"
        f'<td class="n">{_signed_html(five.alpha_annual, 2, 100, "%")}</td>'
        f'<td class="n">{_plain(five.alpha_se_annual, 2, 100, "%")}</td>'
        f'<td class="n">{esc(_sign_fmt(five.alpha_z, 2)[0])}</td>'
        f'<td class="n">{_pval(five.alpha_p)}</td><td class="n">single test</td>'
        f'<td class="n">{esc(a_ci)}</td><td class="n">{esc(five.alpha_tag or "n/a")}</td></tr>'
    ]
    for s in five.factors:
        rows.append(
            f"<tr><td>{esc(s.name)}</td><td class='n'>{_signed_html(s.beta, 4)}</td>"
            f"<td class='n'>{_plain(s.se, 4)}</td>"
            f"<td class='n'>{esc(_sign_fmt(s.z, 2)[0])}</td><td class='n'>{_pval(s.p)}</td>"
            f"<td class='n'>{_pval(s.p_adj_bh)}</td>"
            f"<td class='n'>{esc(f'{_plain(s.ci_low, 3)} to {_plain(s.ci_high, 3)}')}</td>"
            f"<td class='n'>{esc(s.tag or 'n/a')}</td></tr>"
        )
    cap = (
        f"{five.caption} R² {_plain(five.r2, 4)}, residual volatility "
        f"{_plain(five.sigma_e_annual, 2, 100, '%')} a year, Newey-West lags {five.hac_lags}."
    )
    return (
        f"<h3>5-day estimate ({five.n_blocks:,} blocks)</h3>"
        '<div class="tablewrap"><table class="dt"><thead><tr><th>Term</th><th>Coef</th>'
        "<th>HAC se</th><th>z</th><th>p</th><th>p (BH)</th><th>95% CI</th><th>Tag</th>"
        f"</tr></thead><tbody>{''.join(rows)}</tbody></table></div>"
        f'<p class="cap">{esc(cap)}</p>'
    )


def _diagnostics_table(report: FactorReport) -> str:
    """Residual diagnostics of M3.5 with their plain-language readings."""
    rd = report.residual_diagnostics
    if rd.status != "ok":
        return f"<h3>Residual diagnostics</h3>{_empty(rd.reason or 'not available')}"
    rows = [
        "<tr><td>Lag-1 autocorrelation</td>"
        f'<td class="n">{esc(_sign_fmt(rd.lag1_autocorrelation, 3)[0])}</td>'
        f'<td class="n">z {esc(_sign_fmt(rd.lag1_z, 1)[0])}</td>'
        f'<td class="n">{_pval(rd.lag1_p)}</td>'
        f'<td class="rd">{esc(rd.lag1_reading or "")}</td></tr>'
    ]
    for t in rd.tests:
        rows.append(
            f"<tr><td>{esc(t.name)}</td><td class='n'>{_plain(t.statistic, 2)}</td>"
            f"<td class='n'>{'' if t.df is None else f'df {t.df}'}</td>"
            f"<td class='n'>{_pval(t.p)}</td><td class='rd'>{esc(t.reading)}</td></tr>"
        )
    return (
        "<h3>Residual diagnostics</h3>"
        '<div class="tablewrap"><table class="dt"><thead><tr><th>Test</th><th>Statistic</th>'
        '<th>Reference</th><th>p</th><th class="rd">Reading</th></tr></thead>'
        f"<tbody>{''.join(rows)}</tbody></table></div>"
        f'<p class="cap">{esc(rd.note)} {esc(rd.caption)}</p>'
    )


def render_report_html(report: FactorReport) -> str:
    """Render ``report`` as a single self-contained HTML document (no external resources)."""
    title = f"{report.ticker} factor report"
    main = (
        '<div class="grid g-main">'
        f"{_price_panel(report)}{_betas_panel(report)}</div>"
        f'<div class="grid g-two">{_return_panel(report)}{_risk_panel(report)}</div>'
        f'<div class="grid" style="grid-template-columns:minmax(0,1fr)">'
        f"{_rolling_panel(report)}</div>"
        f"{_data_panel(report)}"
        f'<div class="grid" style="grid-template-columns:minmax(0,1fr)">'
        f"{_detail_panel(report)}</div>"
    )
    return (
        '<!doctype html>\n<html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>{esc(title)}</title><style>{CSS}</style></head>"
        f'<body><div class="wrap">{_header(report)}{_kpis(report)}{_gate_callout(report)}'
        f"<main>{main}</main></div>"
        "</body></html>\n"
    )


def write_report(report: FactorReport, path: str | Path) -> Path:
    """Render and write the HTML file (UTF-8, LF line endings); returns the written path."""
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(render_report_html(report).encode("utf-8"))
    return out
