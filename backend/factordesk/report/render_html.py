"""Render a ``FactorReport`` as one self-contained HTML file.

The design is specified in ``docs/design/report-design.md`` (revision 2). No scripts and no
external requests: the stylesheet (``report.css``) and the fonts (``fonts/*.woff2``, base64) are
inlined, charts are inline SVG or positioned HTML. Output is deterministic for a given report
(nothing reads the clock or the environment). Every dynamic string goes through ``html.escape``.
"""

from __future__ import annotations

import base64
import html
import math
import re
from collections.abc import Callable, Sequence
from datetime import date
from functools import lru_cache
from pathlib import Path

from factordesk.report.schema import (
    FACTOR_NAMES,
    FactorReport,
    FactorStat,
    RollingWindow,
)

HERE = Path(__file__).resolve().parent
FONTS_DIR = HERE / "fonts"
CSS_PATH = HERE / "report.css"

MINUS = "−"
IDIO = "Idiosyncratic"
PLAIN = {
    "Mkt-RF": "Market",
    "SMB": "Size",
    "HML": "Value",
    "RMW": "Profitability",
    "CMA": "Investment",
}
EXCLUSION_TEXT = {
    "multi_day_return": "return spans several factor days",
    "no_factor_row": "date not in the factor file",
    "price_missing": "price missing",
    "factor_missing": "factor value missing",
}
TILT = {
    "SMB": ("small companies", "large companies"),
    "HML": ("value stocks", "growth stocks"),
    "RMW": ("highly profitable firms", "weakly profitable firms"),
    "CMA": ("firms that invest conservatively", "firms that invest aggressively"),
}
WARN_PLAIN = {
    "residual_reversal": (
        "Prices look out of step with the factor data, so R² and residual volatility are "
        "probably understated."
    ),
    "short_history": "The history is short, so the betas rest on a small sample.",
    "collinearity": "Some factors move together in this sample, so single betas are less precise.",
    "audit_errors": (
        "The price audit found errors, so the headline numbers are not interpretable until "
        "they are explained; see Data and audit."
    ),
    "audit_warnings": "The price audit flagged some unusual price moves; see Data and audit.",
    "factor_data_lag": (
        "The factor data stops before the latest prices, so the newest days are charted but "
        "not analysed."
    ),
}
MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
HAC_DEFAULT_Z = 1.959963984540054

GLYPH_WARN = (
    '<svg class="glyph" aria-hidden="true" viewBox="0 0 16 16"><path d="M8 1.5 15 14.5H1z"/>'
    '<path class="cut" d="M8 6v4M8 11.6v1"/></svg>'
)
GLYPHS = {
    "info": (
        '<svg class="glyph" aria-hidden="true" viewBox="0 0 16 16"><circle cx="8" cy="8" r="6.5"/>'
        '<path class="cut" d="M8 7v4.5M8 4.6v.9"/></svg>'
    ),
    "warning": GLYPH_WARN,
    "error": (
        '<svg class="glyph" aria-hidden="true" viewBox="0 0 16 16"><rect x="2" y="2" width="12" '
        'height="12" rx="1"/><path class="cut" d="M5.5 5.5l5 5M10.5 5.5l-5 5"/></svg>'
    ),
}
HATCH_DEFS = (
    '<svg class="defs" width="0" height="0" aria-hidden="true" focusable="false"><defs>'
    '<pattern id="hatch" patternUnits="userSpaceOnUse" width="5" height="5" '
    'patternTransform="rotate(45)"><rect class="hatch-bg" width="5" height="5"/>'
    '<rect class="hatch-ink" width="1.6" height="5"/></pattern></defs></svg>'
)


# --------------------------------------------------------------------------------------------
# Assets: stylesheet and fonts, read once from the package directory
# --------------------------------------------------------------------------------------------
def _font_url(name: str) -> str:
    raw = (FONTS_DIR / name).read_bytes()
    return f"url(data:font/woff2;base64,{base64.b64encode(raw).decode('ascii')}) format('woff2')"


@lru_cache(maxsize=1)
def font_faces() -> str:
    """``@font-face`` rules with the WOFF2 files inlined as base64."""
    return (
        "@font-face{font-family:'Instrument Sans';font-style:normal;font-weight:400 700;"
        f"font-display:block;src:{_font_url('instrument-sans.woff2')}}}\n"
        "@font-face{font-family:'STIX Two Text';font-style:normal;font-weight:400;"
        f"font-display:block;src:{_font_url('stix-r.woff2')}}}\n"
        "@font-face{font-family:'STIX Two Text';font-style:italic;font-weight:400;"
        "font-display:block;unicode-range:U+0041-005A,U+0061-007A;"
        f"src:{_font_url('stix-il.woff2')}}}\n"
        "@font-face{font-family:'STIX Two Text';font-style:italic;font-weight:400;"
        "font-display:block;unicode-range:U+03B1,U+03B2,U+03B5,U+03C1,U+03C3;"
        f"src:{_font_url('stix-ig.woff2')}}}\n"
    )


@lru_cache(maxsize=1)
def base_css() -> str:
    """The shared stylesheet text."""
    return CSS_PATH.read_text(encoding="utf-8")


def _window_css(windows: Sequence[int]) -> str:
    """Radio-driven show/hide rules for the rolling windows (no JavaScript)."""
    show = ", ".join(f"#win-{k}:checked ~ #rolling .w-{k}" for k in windows)
    lab = ", ".join(f'#win-{k}:checked ~ #rolling label[for="win-{k}"]' for k in windows)
    foc = ", ".join(f'#win-{k}:focus-visible ~ #rolling label[for="win-{k}"]' for k in windows)
    if not windows:
        return ""
    return (
        f"#rolling .win{{display:none}}\n{show}{{display:block}}\n"
        f"{lab}{{background:var(--ink);color:var(--surface);border-color:var(--ink)}}\n"
        f"{foc}{{outline:2px solid var(--focus);outline-offset:2px;position:relative;z-index:1}}\n"
    )


# --------------------------------------------------------------------------------------------
# Formatting
# --------------------------------------------------------------------------------------------
def esc(value: object) -> str:
    """HTML-escape any value (quotes included)."""
    return html.escape(str(value), quote=True)


def _fin(x: float | None) -> float | None:
    """Return ``x`` if it is a finite number, else None (handles None, NaN and +/-inf)."""
    if x is None or not math.isfinite(x):
        return None
    return float(x)


def _sgn(x: float | None, digits: int = 3, scale: float = 1.0, suffix: str = "") -> str:
    """Signed number: ``+`` or a true minus on every value, zero unsigned, ``n/a`` if missing."""
    v = _fin(x)
    if v is None:
        return "n/a"
    s = f"{abs(v * scale):,.{digits}f}"
    if float(s.replace(",", "")) == 0:
        return s + suffix
    return ("+" if v > 0 else MINUS) + s + suffix


def _num(x: float | None, digits: int = 3, scale: float = 1.0, suffix: str = "") -> str:
    """Unsigned-style number (true minus when negative), ``n/a`` if missing."""
    v = _fin(x)
    if v is None:
        return "n/a"
    s = f"{abs(v * scale):,.{digits}f}"
    neg = v < 0 and float(s.replace(",", "")) != 0
    return (MINUS if neg else "") + s + suffix


def _pct(x: float | None, digits: int = 2, signed: bool = True) -> str:
    """Decimal as a percentage."""
    return (_sgn if signed else _num)(x, digits, 100.0, "%")


def _tstat(z: float | None) -> str:
    v = _fin(z)
    if v is None:
        return "n/a"
    return _num(v, 0) if abs(v) >= 100 else _num(v, 1)


def _pval(x: float | None) -> str:
    """P-value with a floor so tiny values read as '<0.001'."""
    v = _fin(x)
    if v is None:
        return "n/a"
    return "<0.001" if v < 0.001 else f"{v:.3f}"


def _d_long(d: date) -> str:
    return f"{d.day} {MONTHS[d.month - 1]} {d.year}"


def _d_short(d: date) -> str:
    return f"{MONTHS[d.month - 1]} {d.year}"


def _plural(n: int, one: str, many: str) -> str:
    return f"{n} {one if n == 1 else many}"


# --------------------------------------------------------------------------------------------
# Scales and ticks
# --------------------------------------------------------------------------------------------
def _nice_step(span: float, target: int = 4) -> float:
    raw = span / max(target, 1)
    mag = 10 ** math.floor(math.log10(raw))
    for m in (1, 2, 2.5, 5, 10):
        if raw <= m * mag:
            return m * mag
    return 10 * mag


def _nice_domain(lo: float, hi: float, target: int = 4) -> tuple[float, float, list[float]]:
    """A round-number domain covering [lo, hi], with its tick values."""
    if hi - lo < 1e-12:
        hi, lo = hi + 0.5, lo - 0.5
    step = _nice_step(hi - lo, target)
    nlo = math.floor(lo / step - 1e-9) * step
    nhi = math.ceil(hi / step + 1e-9) * step
    ticks: list[float] = []
    t = nlo
    while t <= nhi + step / 2:
        ticks.append(round(t, 10))
        t += step
    return nlo, nhi, ticks


def _pos(v: float, lo: float, hi: float) -> float:
    """Position of ``v`` in [lo, hi] as a percentage."""
    return round((v - lo) / (hi - lo) * 100, 3)


def _decimals(values: Sequence[float]) -> int:
    """Fewest decimals (0-4) that print every value exactly enough for an axis label."""
    for d in range(0, 5):
        if all(abs(round(v, d) - v) < 1e-9 * max(1.0, abs(v)) for v in values):
            return d
    return 4


def _decimate[T](items: list[T], max_n: int) -> list[T]:
    """Deterministic stride decimation that always keeps the last element."""
    if len(items) <= max_n or max_n < 2:
        return items
    stride = math.ceil(len(items) / max_n)
    out = items[::stride]
    if out[-1] is not items[-1]:
        out.append(items[-1])
    return out


def _quantile(xs: list[float], q: float) -> float:
    s = sorted(xs)
    k = (len(s) - 1) * q
    f = math.floor(k)
    c = min(f + 1, len(s) - 1)
    return s[f] + (s[c] - s[f]) * (k - f)


def _date_ticks(d0: date, d1: date) -> list[tuple[date, str, bool]]:
    """Calendar ticks as (date, label, major). Quarterly for short spans, yearly for long ones."""
    months = max((d1 - d0).days, 1) / 30.44
    step = next((k for k in (3, 6, 12, 24, 60, 120) if months / k <= 14), 120)
    out: list[date] = []
    y, m = d0.year, d0.month
    while True:
        aligned = (m - 1) % step == 0 if step < 12 else (m == 1 and y % (step // 12) == 0)
        cur = date(y, m, 1)
        if cur > d1:
            break
        if aligned and cur >= d0:
            out.append(cur)
        m += 1
        if m > 12:
            y, m = y + 1, 1
    ticks: list[tuple[date, str, bool]] = []
    for i, cur in enumerate(out):
        if step < 12:
            ticks.append((cur, _d_short(cur), cur.month == 1))
        else:
            ticks.append((cur, str(cur.year), i % 2 == 0 or len(out) <= 6))
    return ticks


def _edge(x: float) -> str:
    """Tick labels at the plot edges are anchored inward so they never overflow."""
    return "edge-l" if x < 3 else ("edge-r" if x > 97 else "")


def _path_xy(points: Sequence[tuple[float, float]]) -> str:
    return "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in points)


# --------------------------------------------------------------------------------------------
# Factor helpers
# --------------------------------------------------------------------------------------------
def _factor_order(report: FactorReport) -> list[str]:
    """Factor names in display order."""
    names = [f.name for f in report.regression.factors]
    return names or list(report.return_contribution.factors)


def _slot(name: str, order: Sequence[str]) -> int:
    """Colour slot 1-5: canonical position, else order of appearance."""
    if name in FACTOR_NAMES:
        return FACTOR_NAMES.index(name) + 1
    return order.index(name) % 5 + 1 if name in order else 1


def _plain_name(name: str) -> str:
    return PLAIN.get(name, "")


def _sub(text: str, cls: str = "") -> str:
    return f'<span class="sub{" " + cls if cls else ""}">{esc(text)}</span>' if text else ""


def _is_reliable(s: FactorStat) -> bool:
    return s.tag == "reliable"


def _label_texts(report: FactorReport, keys: Sequence[str], skip: str = "L-DESC") -> list[str]:
    """Standard footnote texts for ``keys`` (M0.9), without the one shown in the open."""
    return [report.label_text[k] for k in keys if k != skip and k in report.label_text]


def _desc(report: FactorReport) -> str:
    """The standard 'descriptive, in-sample' sentence that opens most footnotes."""
    return report.label_text.get("L-DESC", "Descriptive, in-sample, not predictive.")


# --------------------------------------------------------------------------------------------
# Small pieces
# --------------------------------------------------------------------------------------------
def _footnote(text: str, more: Sequence[str] = ()) -> str:
    """One or two visible sentences; method detail folds into a native ``<details>``."""
    paras = "".join(f"<p>{esc(m)}</p>" for m in more if m)
    if not paras:
        return f'<p class="foot">{esc(text)}</p>'
    return (
        f'<div class="foot"><p>{esc(text)}</p><details class="how"><summary>How this is '
        f"computed</summary>{paras}</details></div>"
    )


def _panel_head(pid: str, title: str, question: str, extra: str = "") -> str:
    return (
        f'<header class="panel-head"><div><h2 id="{pid}-t">{esc(title)}</h2>'
        f'<p class="q">{esc(question)}</p></div>{extra}</header>'
    )


def _empty(what: str, action: str = "") -> str:
    """Empty state: the reason in ink, one next step in a quieter colour."""
    do = f'<p class="empty-do">{esc(action)}</p>' if action else ""
    return f'<div class="empty" role="note"><p class="empty-what">{esc(what)}</p>{do}</div>'


def _nodata(what: str, action: str = "") -> str:
    """Empty state for a gap the renderer itself found."""
    return _empty(f"Insufficient data: {what}", action)


def _section(pid: str, head: str, body: str) -> str:
    return f'<section class="panel" id="{pid}" aria-labelledby="{pid}-t">{head}{body}</section>'


def _legend(items: Sequence[str]) -> str:
    inner = "".join(f"<li>{i}</li>" for i in items)
    return f'<ul class="legend" aria-label="Legend">{inner}</ul>'


def _sw_rect(cls: str, faded: bool = False) -> str:
    if faded:
        return (
            f'<svg class="sw" aria-hidden="true"><rect class="{cls} faded" x="0.5" y="0.5" '
            'width="13" height="9" rx="2"/></svg>'
        )
    return (
        f'<svg class="sw" aria-hidden="true"><rect class="{cls}" width="14" height="10" '
        'rx="2"/></svg>'
    )


def _axis_row(
    ticks: list[float], lo: float, hi: float, fmt: Callable[[float], str], ncols: int
) -> str:
    k0 = next((k for k, t in enumerate(ticks) if abs(t) < 1e-12), 0)  # the zero label survives
    labels = "".join(
        f'<span class="{_edge(_pos(t, lo, hi))}'
        f'{" alt" if ((k - k0) % 2 and len(ticks) > 5) else ""}" '
        f'style="left:{_pos(t, lo, hi)}%">{esc(fmt(t))}</span>'
        for k, t in enumerate(ticks)
    )
    return (
        f'<tr class="axis-row" aria-hidden="true"><td></td><td class="axis">{labels}</td>'
        f'<td colspan="{ncols}"></td></tr>'
    )


def _grid_lines(ticks: list[float], lo: float, hi: float) -> str:
    out: list[str] = []
    for t in ticks:
        cls = "zero" if abs(t) < 1e-12 else "grid"
        p = _pos(t, lo, hi)
        out.append(f'<line class="{cls}" x1="{p}%" x2="{p}%" y1="0" y2="100%"/>')
    return "".join(out)


def _bar(v: float, lo: float, hi: float, cls: str) -> str:
    a, b = sorted((_pos(0.0, lo, hi), _pos(v, lo, hi)))
    return f'<rect class="{cls}" x="{a}%" y="32%" width="{max(b - a, 0.0)}%" height="36%" rx="2"/>'


def _bar_cell(title: str, ticks: list[float], lo: float, hi: float, marks: str = "") -> str:
    return (
        f'<td class="plot-cell"><svg class="bar-svg" aria-hidden="true"><title>{esc(title)}</title>'
        f"{_grid_lines(ticks, lo, hi)}{marks}</svg></td>"
    )


def _name_cell(name: str, plain: str, key: str = "", mob: str = "") -> str:
    return (
        f'<th scope="row"><span class="fname">{key}{esc(name)}</span>{_sub(plain)}'
        f"{_sub(mob, 'mob')}</th>"
    )


def _key_swatch(cls: str) -> str:
    return (
        f'<svg class="key" aria-hidden="true"><rect class="{cls}" width="8" height="8" '
        'rx="1"/></svg>'
    )


def _sig_head() -> str:
    return (
        '<th scope="col" class="num"><span class="long">Significant</span>'
        '<span class="short" aria-hidden="true">Sig.</span></th>'
    )


# --------------------------------------------------------------------------------------------
# Header, notice, equation, KPI strip
# --------------------------------------------------------------------------------------------
def _range_line(report: FactorReport) -> str:
    d = report.data
    s = (
        f"Analysed {_d_long(d.actual_start)} to {_d_long(d.actual_end)}, "
        f"{_plural(d.n_obs, 'trading day', 'trading days')}."
    )
    tail_n = d.uncovered.n
    if tail_n == 1:
        s += " The last price day is charted but not analysed."
    elif tail_n:
        s += f" The last {tail_n} price days are charted but not analysed."
    # The price day just before the first return is that return's base price, not a gap.
    head_n = max(sum(1 for x in report.price_series.dates if x < d.actual_start) - 1, 0)
    if head_n == 1:
        s += " The first price day is also not analysed."
    elif head_n:
        s += f" The first {head_n} price days are also not analysed."
    return s


def _notice_items(report: FactorReport) -> list[tuple[str, str]]:
    """(code, message) for every warning, including the quality-gate caveat when it fired."""
    items = [(w.code, w.message) for w in report.warnings]
    gate = report.quality_gate
    if gate.fired and gate.message and not any(c == "residual_reversal" for c, _ in items):
        items.insert(0, ("residual_reversal", gate.message))
    return items


def _gate_detail(report: FactorReport) -> str:
    """The 5-day estimate line shown under the notice's Details (methodology M3.6)."""
    gate, five = report.quality_gate, report.five_day_regression
    if not gate.fired:
        return ""
    if five.status == "ok":
        return (
            f"<p>5-day estimate ({five.n_blocks:,} blocks): alpha {esc(_pct(five.alpha_annual))} "
            f"a year, t {esc(_tstat(five.alpha_z))}, p {_pval(five.alpha_p)}, "
            f"{esc(five.alpha_tag or 'n/a')}; R² {_num(five.r2, 4)}. "
            'The full table is under <a href="#detail">Regression detail</a>.</p>'
        )
    if five.reason:
        return f"<p>5-day estimate: {esc(five.reason)}.</p>"
    return ""


def _notice(report: FactorReport, items: list[tuple[str, str]]) -> str:
    if not items:
        return ""
    plain: list[str] = []
    for code, message in items:
        text = WARN_PLAIN.get(code, message)
        if text not in plain:
            plain.append(text)
    summary = " ".join(plain[:2])
    if len(plain) > 2:
        summary += f" {len(plain) - 2} more are listed under Details."
    more = "".join(f"<li>{esc(m)}</li>" for _, m in items)
    return (
        f'<aside class="notice" id="notice" aria-label="Data quality">{GLYPH_WARN}'
        f'<div><p class="notice-sum"><span class="vh">Warning: </span>{esc(summary)}</p>'
        f'<details class="how"><summary>Details</summary><ul>{more}</ul>'
        f"{_gate_detail(report)}</details></div></aside>"
    )


def _header(report: FactorReport) -> str:
    d = report.data
    items = _notice_items(report)
    ago = _plural(d.factors_days_behind, "day", "days")
    chips = f'<span class="chip">Factor data ends {_d_long(d.factors_last_date)} ({ago} ago)</span>'
    if items:
        chips += (
            f'<a class="chip warn" href="#notice">{_plural(len(items), "warning", "warnings")}</a>'
        )
    return (
        '<header class="masthead"><div class="mast-top"><h1>'
        f'<span class="ticker">{esc(report.ticker)}</span>'
        '<span class="what">Fama&#8211;French five-factor profile</span></h1>'
        f'<p class="mast-meta">{chips}</p></div>'
        f'<p class="coverage">{esc(_range_line(report))}</p>{_notice(report, items)}</header>'
    )


def _equation(report: FactorReport) -> str:
    g = report.regression
    alpha = _fin(g.alpha_annual)
    betas = [(s, _fin(s.beta)) for s in g.factors]
    if g.status != "ok" or alpha is None or not betas or any(b is None for _, b in betas):
        return ""
    sigma = _fin(g.sigma_e_annual)
    alpha_ns = g.alpha_tag != "reliable"
    terms = [
        f'<a class="term{" ns" if alpha_ns else ""}" href="#ret-alpha">'
        f'<span class="m">{"" if alpha >= 0 else MINUS}{_num(abs(alpha), 2, 100.0, "%")}</span>'
        f'<span class="ann"><span>alpha, a year</span>'
        f"<span>{'not significant' if alpha_ns else 'significant'}, t {_tstat(g.alpha_z)}"
        "</span></span></a>"
    ]
    for s, b in betas:
        assert b is not None
        ns = not _is_reliable(s)
        plain = _plain_name(s.name).lower() or s.name
        terms.append(
            f'<a class="term{" ns" if ns else ""}" href="#beta-{esc(s.name)}">'
            f'<span class="m"><span class="op">{"+" if b >= 0 else MINUS}</span>'
            f'{_num(abs(b), 3)}<span class="fn">{esc(s.name)}</span></span>'
            f'<span class="ann"><span>{esc(plain)}</span>'
            f"<span>{'not significant' if ns else 'significant'}, t {_tstat(s.z)}</span>"
            "</span></a>"
        )
    resid = f"{_pct(sigma, 1, False)} a year" if sigma is not None else "n/a"
    terms.append(
        '<span class="term eps"><span class="m"><span class="op">+</span><var>&#949;</var></span>'
        f'<span class="ann"><span>residual</span><span>{esc(resid)}</span></span></span>'
    )
    label = (
        "Fitted model: daily excess return equals "
        + ", ".join(
            [f"alpha {_pct(alpha)} a year"] + [f"{_sgn(b)} times {s.name}" for s, b in betas]
        )
        + ", plus a residual."
    )
    return (
        f'<figure class="model" aria-label="{esc(label)}"><div class="eq">'
        '<span class="lhs" aria-hidden="true"><var>r</var><span class="op">&#8722;</span>'
        '<var>r</var><sub>f</sub><span class="op eqs">=</span></span>'
        f'<span class="terms">{"".join(terms)}</span></div>'
        "<figcaption>The fitted daily model, in-sample. Faded terms are not statistically "
        "significant. Select a term to see its detail.</figcaption></figure>"
    )


def _kpis(report: FactorReport) -> str:
    g, d = report.regression, report.data
    if g.status != "ok":
        body = _empty(
            g.reason or "The regression could not be computed.",
            "Widen the date range and run the report again.",
        )
        return f'<section class="kpis" aria-label="Headline statistics">{body}</section>'
    # Validation F4: with audit errors one bad row can dominate every fitted number, so the
    # fitted tiles are muted and alpha carries no significance claim (the values stay shown).
    audit_errors = d.audit_status == "errors"
    fit_cls = "ns" if audit_errors else ""
    if audit_errors:
        alpha_note, alpha_cls = "Not interpretable: the price audit found errors", "ns"
    elif g.alpha_tag == "reliable":
        alpha_note, alpha_cls = "Distinguishable from zero at 5%", ""
    elif g.alpha_tag == "noise":
        alpha_note, alpha_cls = "Not distinguishable from zero", "ns"
    else:
        alpha_note, alpha_cls = "Significance not available", "ns"
    excl = (
        f"Trading days; {d.n_excluded} excluded" if d.n_excluded else "Trading days; none excluded"
    )
    cells = [
        ("Alpha, a year", esc(_pct(g.alpha_annual)), alpha_note, alpha_cls),
        ("R&#178;", esc(_num(g.r2, 4)), "Share of daily variance the factors explain", fit_cls),
        (
            "Residual volatility",
            esc(_pct(g.sigma_e_annual, 1, False)),
            "A year, left unexplained by the factors",
            fit_cls,
        ),
        ("Observations", f"{d.n_obs:,}", excl, ""),
        (
            "Analysed range",
            f"{_d_short(d.actual_start)} to {_d_short(d.actual_end)}",
            f"Requested {_d_long(d.requested_start)} to {_d_long(d.requested_end)}",
            "dates",
        ),
    ]
    body = "".join(
        f'<div class="kpi {cls}"><dt>{lab}</dt><dd class="v">{val}</dd>'
        f'<dd class="n">{esc(note)}</dd></div>'
        for lab, val, note, cls in cells
    )
    return f'<section class="kpis" aria-label="Headline statistics"><dl>{body}</dl></section>'


# --------------------------------------------------------------------------------------------
# Panel 4: price
# --------------------------------------------------------------------------------------------
def _price_panel(report: FactorReport) -> str:
    ps, d = report.price_series, report.data
    head = _panel_head(
        "price",
        "Price",
        "How has the price moved over the window? Shaded days are not in the analysis.",
    )
    pts: list[tuple[date, float]] = []
    for dt, raw in zip(ps.dates, ps.adj_close, strict=True):
        v = _fin(raw)
        if v is not None:
            pts.append((dt, v))
    if len(pts) < 2:
        body = _nodata(
            "fewer than two price points were returned for this ticker and window.",
            "Check the ticker symbol or choose a later start date.",
        )
        return _section("price", head, body)

    cov = ps.factor_coverage_end
    cut = max((k for k, (dt, _) in enumerate(pts) if dt <= cov), default=-1)
    start_k = next((k for k, (dt, _) in enumerate(pts) if dt >= d.actual_start), 0)
    lo, hi, ticks = _nice_domain(min(v for _, v in pts), max(v for _, v in pts), 4)
    o0 = pts[0][0].toordinal()
    span = max(pts[-1][0].toordinal() - o0, 1)

    def x_of(dt: date) -> float:
        return (dt.toordinal() - o0) / span * 1000

    def y_of(v: float) -> float:
        return 100 - (v - lo) / (hi - lo) * 100

    grid = "".join(
        f'<line class="grid" x1="0" x2="1000" y1="{y_of(t):.2f}" y2="{y_of(t):.2f}"/>'
        for t in ticks
    )
    shade = ""
    labels = ""
    if cut == -1:  # nothing is covered: the whole window is not analysed
        shade += '<rect class="tailzone" x="0" y="0" width="1000" height="100"/>'
        labels += f'<span class="zone-label">Not analysed: factor data ends {_d_long(cov)}</span>'
    else:
        if cut < len(pts) - 1:
            xc = x_of(pts[cut][0])
            shade += (
                f'<rect class="tailzone" x="{xc:.1f}" y="0" width="{1000 - xc:.1f}" height="100"/>'
                f'<line class="cutline" x1="{xc:.1f}" x2="{xc:.1f}" y1="0" y2="100"/>'
            )
            labels += (
                f'<span class="zone-label">Not analysed: factor data ends {_d_long(cov)}</span>'
            )
        if 2 <= start_k <= cut:  # one earlier day is only the base price of the first return
            xs0 = x_of(pts[start_k][0])
            shade += (
                f'<rect class="tailzone" x="0" y="0" width="{xs0:.1f}" height="100"/>'
                f'<line class="cutline" x1="{xs0:.1f}" x2="{xs0:.1f}" y1="0" y2="100"/>'
            )
            labels += (
                f'<span class="zone-label l">Not analysed: before {_d_long(pts[start_k][0])}</span>'
            )
    two = labels.count("zone-label") == 2
    main = [(x_of(dt), y_of(v)) for dt, v in pts[: cut + 1]]
    tail = [(x_of(dt), y_of(v)) for dt, v in pts[max(cut, 0) :]]
    paths = ""
    if len(main) > 1:
        paths += f'<path class="price-line" d="{_path_xy(_decimate(main, 700))}"/>'
    if len(tail) > 1:
        paths += f'<path class="price-tail" d="{_path_xy(_decimate(tail, 300))}"/>'
    label = f"{report.ticker} adjusted close price over time"
    svg = (
        f'<svg class="line-svg" viewBox="0 0 1000 100" preserveAspectRatio="none" role="img" '
        f'aria-label="{esc(label)}">{shade}{grid}{paths}</svg>'
    )
    dec = _decimals(ticks)
    ylab = "".join(
        f'<span class="yl" style="top:{y_of(t):.2f}%">{t:,.{dec}f}</span>' for t in ticks
    )
    xlab = "".join(
        f'<span class="xl{"" if major else " minor"} {_edge(x_of(dt) / 10)}" '
        f'style="left:{x_of(dt) / 10:.2f}%">{esc(lab)}</span>'
        for dt, lab, major in _date_ticks(pts[0][0], pts[-1][0])
    )
    rows = [("First", pts[0][0], pts[0][1])]
    if cut >= 0:
        rows.append(("End of factor data", pts[cut][0], pts[cut][1]))
    rows.append(("Latest", pts[-1][0], pts[-1][1]))
    side = "".join(
        f'<tr><th scope="row">{a}<span class="sub">{_d_long(b)}</span></th>'
        f'<td class="num">{c:,.2f}</td></tr>'
        for a, b, c in rows
    )
    u = d.uncovered
    if u.n and _fin(u.compounded_return) is not None:
        side += (
            '<tr class="muted-row"><th scope="row">After factor data'
            f'<span class="sub">{u.n} days, raw, not analysed</span></th>'
            f'<td class="num">{esc(_pct(u.compounded_return))}</td></tr>'
        )
    foot = _footnote(
        f"Adjusted close from {d.price_source}, for context only; no statistic uses the price line."
    )
    return (
        f'<section class="panel" id="price" aria-labelledby="price-t">{head}'
        '<div class="price-wrap">'
        f'<div class="plot price-plot{" two" if two else ""}">{svg}'
        f'<div class="ylabels" aria-hidden="true">{ylab}</div>{labels}'
        f'<div class="xlabels" aria-hidden="true">{xlab}</div></div>'
        '<table class="side"><caption class="vh">Price points</caption>'
        '<thead class="vh"><tr><th scope="col">Point</th><th scope="col">Adjusted close</th>'
        f"</tr></thead><tbody>{side}</tbody></table></div>{foot}</section>"
    )


# --------------------------------------------------------------------------------------------
# Panel 5: factor exposures
# --------------------------------------------------------------------------------------------
def _exposure_reading(stats: Sequence[FactorStat]) -> str:
    parts: list[str] = []
    quiet: list[str] = []
    for s in stats:
        b = _fin(s.beta)
        if b is None:
            continue
        if not _is_reliable(s):
            quiet.append(f"{_plain_name(s.name).lower() or s.name} ({s.name})")
            continue
        if s.name == "Mkt-RF":
            if abs(b - 1) < 0.1:
                parts.append(f"moves roughly one-for-one with the market (beta {_num(b)})")
            elif b > 1:
                parts.append(f"amplifies market moves (beta {_num(b)})")
            else:
                parts.append(f"moves less than the market (beta {_num(b)})")
        elif s.name in TILT:
            parts.append(f"leans toward {TILT[s.name][0 if b > 0 else 1]} ({s.name} {_sgn(b)})")
        else:
            parts.append(f"has a reliable exposure to {s.name} ({_sgn(b)})")
    text = ""
    if parts:
        joined = ", ".join(parts[:-1]) + " and " + parts[-1] if len(parts) > 1 else parts[0]
        text = f"Over this window the stock {joined}."
    if quiet:
        q = ", ".join(quiet[:-1]) + " or " + quiet[-1] if len(quiet) > 1 else quiet[0]
        text += f" There is no clear tilt to {q}."
    return text.strip()


def _exposures_panel(report: FactorReport) -> str:
    g, ab = report.regression, report.average_beta
    q = "What is this stock exposed to, and how sure are we?"
    head = _panel_head("beta", "Factor exposures", q)
    stats = g.factors
    if g.status != "ok" or not stats or all(_fin(s.beta) is None for s in stats):
        body = (
            _empty(g.reason, "Widen the date range and run the report again.")
            if g.reason
            else _nodata("no factor betas available.")
        )
        return _section("exposures", head, body)
    win = ab.window
    avg = {a.name: _fin(a.mean) for a in ab.factors} if ab.status == "ok" else {}
    vals = [0.0]
    for s in stats:
        cands = (_fin(s.beta), _fin(s.ci_low), _fin(s.ci_high), avg.get(s.name))
        vals += [v for v in cands if v is not None]
    lo, hi, ticks = _nice_domain(min(vals), max(vals), 5)
    rows: list[str] = []
    for s in stats:
        ns = not _is_reliable(s)
        b = _fin(s.beta)
        marks = ""
        tip = f"{s.name}: no estimate"
        if b is not None:
            cls = ("pos" if b >= 0 else "neg") + (" faded" if ns else "")
            marks = _bar(b, lo, hi, cls)
            ci_lo, ci_hi = _fin(s.ci_low), _fin(s.ci_high)
            tip = (
                f"{s.name}: beta {_sgn(b)}, 95% interval {_sgn(ci_lo)} to {_sgn(ci_hi)}, "
                f"t {_tstat(s.z)}, adjusted p {_pval(s.p_adj_bh)}"
            )
            if ci_lo is not None and ci_hi is not None:
                pl, ph = _pos(ci_lo, lo, hi), _pos(ci_hi, lo, hi)
                marks += f'<line class="ci" x1="{pl}%" x2="{ph}%" y1="50%" y2="50%"/>'
                if ph - pl >= 1.2:  # caps only when the interval is wide enough to read
                    for p in (pl, ph):
                        marks += f'<line class="ci" x1="{p}%" x2="{p}%" y1="46.5%" y2="53.5%"/>'
            a = avg.get(s.name)
            if a is not None:
                marks += (
                    f'<svg class="avgm" x="{_pos(a, lo, hi)}%" y="50%" overflow="visible" '
                    'aria-hidden="true"><path d="M0 -3.6 3.6 0 0 3.6-3.6 0z"/></svg>'
                )
        a = avg.get(s.name)
        rows.append(
            f'<tr id="beta-{esc(s.name)}" class="{"ns" if ns else ""}" tabindex="-1">'
            f"{_name_cell(s.name, _plain_name(s.name))}{_bar_cell(tip, ticks, lo, hi, marks)}"
            f'<td class="num strong">{esc(_sgn(b))}</td><td class="num">{esc(_tstat(s.z))}</td>'
            f'<td class="num sig">{"No" if ns else "Yes"}</td>'
            f'<td class="num">{esc(_sgn(a)) if a is not None else "&#8211;"}</td></tr>'
        )
    legend = _legend(
        [
            _sw_rect("pos") + "Positive",
            _sw_rect("neg") + "Negative",
            _sw_rect("pos", True) + "Faded: not significant",
            '<svg class="sw" aria-hidden="true"><line class="ci" x1="1" x2="15" y1="5" y2="5"/>'
            '<line class="ci" x1="1" x2="1" y1="3.5" y2="6.5"/>'
            '<line class="ci" x1="15" x2="15" y1="3.5" y2="6.5"/></svg>95% interval',
            '<svg class="sw" aria-hidden="true"><path class="avgm-sw" d="M8 1.4 11.6 5 8 8.6 '
            f'4.4 5z"/></svg>Average {win}d beta',
        ]
    )
    reading = _exposure_reading(stats)
    reading_html = f'<p class="reading">{esc(reading)}</p>' if reading else ""
    fold = [
        "Reliable means the Benjamini-Hochberg adjusted p is below 0.05 (Yes in the Significant "
        "column); noise means it is not (No, shown faded).",
        g.caption,
        f"The diamond and the Avg {win}d column are the mean of the overlapping rolling estimates.",
        *_label_texts(report, g.labels),
    ]
    return (
        f'<section class="panel" id="exposures" aria-labelledby="beta-t">'
        f"{_panel_head('beta', 'Factor exposures', q, legend)}{reading_html}"
        '<table class="bars cols-4"><caption class="vh">Full-sample factor betas with 95% '
        "intervals, t-statistics, significance and average rolling beta</caption>"
        '<thead><tr><th scope="col">Factor</th><th scope="col" class="plot-h">'
        '<span class="vh">Chart</span></th><th scope="col" class="num">Beta</th>'
        f'<th scope="col" class="num">t</th>{_sig_head()}'
        f'<th scope="col" class="num">Avg {win}d</th></tr></thead>'
        f"<tbody>{''.join(rows)}</tbody>"
        f"<tfoot>{_axis_row(ticks, lo, hi, lambda t: _sgn(t, 2) if t else '0', 4)}</tfoot></table>"
        f"{_footnote(_desc(report) + ' Significant means the adjusted p is below 0.05.', fold)}"
        "</section>"
    )


# --------------------------------------------------------------------------------------------
# Panel 6: where the return came from
# --------------------------------------------------------------------------------------------
def _return_panel(report: FactorReport) -> str:
    rc, g = report.return_contribution, report.regression
    q = "How much of the average yearly return does each factor explain?"
    head = _panel_head("ret", "Where the return came from", q)
    order = _factor_order(report)
    tags = {f.name: f.tag for f in g.factors}
    items: list[tuple[str, str, float | None, bool, str]] = [
        (n, _plain_name(n), _fin(rc.factors.get(n)), tags.get(n) != "reliable", "factor")
        for n in order
    ]
    alpha_ns = g.alpha_tag != "reliable"
    items.append(("Alpha", "Unexplained average", _fin(rc.alpha), alpha_ns, "alpha"))
    items.append(("Residual", "Zero by construction", _fin(rc.residual), False, "resid"))
    total = _fin(rc.total_annualised_mean_excess_return)
    finite = [v for _, _, v, _, _ in items if v is not None]
    if rc.status != "ok" or (not finite and total is None):
        body = (
            _empty(rc.reason, "Widen the date range and run the report again.")
            if rc.reason
            else _nodata("no return attribution available.")
        )
        return _section("returns", head, body)
    extent = [*finite, 0.0, total or 0.0]
    lo, hi, ticks = _nice_domain(min(extent), max(extent), 5)
    rows: list[str] = []
    for n, plain, v, ns, kind in items:
        marks = ""
        if v is not None:
            cls = ("pos" if v >= 0 else "neg") + (" faded" if ns else "")
            if kind == "resid":
                cls = "hatch"
            marks = _bar(v, lo, hi, cls)
        rid = "ret-alpha" if kind == "alpha" else f"ret-{esc(n)}"
        sig = "&#8211;" if kind == "resid" else ("No" if ns else "Yes")
        rows.append(
            f'<tr id="{rid}" class="{"ns" if ns else ""} {kind}" tabindex="-1">'
            f"{_name_cell(n, plain)}"
            f"{_bar_cell(f'{n}: {_pct(v)} a year', ticks, lo, hi, marks)}"
            f'<td class="num strong">{esc(_pct(v))}</td><td class="num sig">{sig}</td></tr>'
        )
    tmarks = ""
    if total is not None:
        z0, tx = _pos(0.0, lo, hi), _pos(total, lo, hi)
        tmarks = (
            f'<line class="total-line" x1="{min(z0, tx)}%" x2="{max(z0, tx)}%" y1="50%" y2="50%"/>'
            f'<line class="total-cap" x1="{tx}%" x2="{tx}%" y1="22%" y2="78%"/>'
        )
    rows.append(
        '<tr class="total"><th scope="row"><span class="fname">Total</span>'
        '<span class="sub">Mean excess return</span></th>'
        f"{_bar_cell(f'Total: {_pct(total)} a year', ticks, lo, hi, tmarks)}"
        f'<td class="num strong">{esc(_pct(total))}</td><td class="num"></td></tr>'
    )
    mkt = _fin(rc.factors.get("Mkt-RF"))
    reading = ""
    if total is not None and mkt is not None:
        alpha_ns = ", but it is not significant" if g.alpha_tag != "reliable" else ""
        reading = (
            f"Of the {_pct(total, 2, False)} average excess return a year, market exposure "
            f"accounts for {_pct(mkt, 2, False)}. Alpha adds {_pct(rc.alpha)}{alpha_ns}."
        )
    legend = _legend(
        [
            _sw_rect("pos") + "Adds",
            _sw_rect("neg") + "Subtracts",
            _sw_rect("pos", True) + "Faded: not significant",
            '<svg class="sw" aria-hidden="true"><rect class="hatch" width="14" height="10" '
            'rx="2"/></svg>Residual',
            '<svg class="sw" aria-hidden="true"><line class="total-line" x1="0" x2="13" y1="5" '
            'y2="5"/><line class="total-cap" x1="13" x2="13" y1="0" y2="10"/></svg>Total',
        ]
    )
    memo = "".join(f"<li>{esc(m)}</li>" for m in rc.memo)
    checks: list[str] = []
    resid = _fin(rc.residual)
    if resid is not None:
        checks.append(f"Residual {resid:.1e} (zero by construction).")
    ident = _fin(rc.identity_residual)
    if ident is not None:
        checks.append(f"Identity check {ident:.1e}.")
    fold = [
        rc.caption,
        "Each factor's share is its full-sample beta times the factor's average return, "
        "times 252. Arithmetic, not compounded.",
        *_label_texts(report, rc.labels),
        " ".join(checks),
    ]
    return (
        f'<section class="panel" id="returns" aria-labelledby="ret-t">'
        f"{_panel_head('ret', 'Where the return came from', q, legend)}"
        + (f'<p class="reading">{esc(reading)}</p>' if reading else "")
        + '<table class="bars cols-2"><caption class="vh">Return contribution per factor, alpha '
        "and residual, percent a year, with the total</caption>"
        '<thead><tr><th scope="col">Component</th><th scope="col" class="plot-h">'
        '<span class="vh">Chart</span></th><th scope="col" class="num">% a year</th>'
        f"{_sig_head()}</tr></thead><tbody>{''.join(rows)}</tbody>"
        f"<tfoot>{_axis_row(ticks, lo, hi, _return_tick, 2)}</tfoot></table>"
        + (f'<div class="memo"><h3>Not in the sum</h3><ul>{memo}</ul></div>' if memo else "")
        + _footnote(f"{_desc(report)} The rows add up exactly to the total.", fold)
        + "</section>"
    )


def _return_tick(t: float) -> str:
    if not t:
        return "0%"
    return _pct(t, 0 if abs(t * 100 - round(t * 100)) < 1e-9 else 1)


# --------------------------------------------------------------------------------------------
# Panel 7: where the risk comes from
# --------------------------------------------------------------------------------------------
def _risk_panel(report: FactorReport) -> str:
    rk = report.risk_contribution
    q = "What share of the day-to-day variance does each factor drive?"
    head = _panel_head("risk", "Where the risk comes from", q)
    order = _factor_order(report)
    shares: dict[str, float | None] = {n: _fin(v) for n, v in rk.factors.items()}
    shares[IDIO] = _fin(rk.idiosyncratic)
    names = [n for n in rk.order if n in shares]
    names += [n for n in shares if n not in names and n != IDIO]
    if IDIO not in names:
        names.append(IDIO)
    finite = [v for v in shares.values() if v is not None]
    if rk.status != "ok" or not finite:
        body = (
            _empty(rk.reason, "Widen the date range and run the report again.")
            if rk.reason
            else _nodata("no risk attribution available.")
        )
        return _section("risk", head, body)
    det = {d.name: d for d in rk.details}
    lo, hi, ticks = _nice_domain(min(0.0, min(finite)), max(1.0, max(finite)), 4)
    rows: list[str] = []
    for n in names:
        v = shares.get(n)
        dd = det.get(n)
        if n == IDIO:
            cls, plain, key = "hatch", "Stock-specific", _key_swatch("hatch")
            cells = '<td class="num">&#8211;</td>' * 3
            tip = f"Idiosyncratic: {_pct(v, 2, False)} of variance"
            mob = "Not explained by the factors"
        else:
            cls = f"cat c{_slot(n, order)}"
            plain, key = _plain_name(n), _key_swatch(cls)
            if dd is None:
                cells = '<td class="num">n/a</td>' * 3
                tip, mob = f"{n}: {_pct(v, 2, False)} of variance", ""
            else:
                cells = (
                    f'<td class="num">{esc(_sgn(dd.beta))}</td>'
                    f'<td class="num">{esc(_pct(dd.sigma_annual, 1, False))}</td>'
                    f'<td class="num">{esc(_sgn(dd.rho_sys, 2))}</td>'
                )
                tip = (
                    f"{n}: {_pct(v, 2, False)} of variance = exposure {_sgn(dd.beta)} x "
                    f"volatility {_pct(dd.sigma_annual, 1, False)} x correlation "
                    f"{_sgn(dd.rho_sys, 2)} with the factor-driven return"
                )
                mob = (
                    f"Beta {_sgn(dd.beta)}, vol {_pct(dd.sigma_annual, 1, False)}, "
                    f"corr {_sgn(dd.rho_sys, 2)}"
                )
        marks = _bar(v, lo, hi, cls) if v is not None else ""
        neg = v is not None and v < 0
        rows.append(
            f'<tr class="{"idio" if n == IDIO else ""}">{_name_cell(n, plain, key, mob)}'
            f"{_bar_cell(tip, ticks, lo, hi, marks)}"
            f'<td class="num strong">{esc(_pct(v, 2, neg))}</td>{cells}</tr>'
        )
    top = next((n for n in names if n != IDIO and shares.get(n) is not None), None)
    vol = _fin(rk.total_vol_annual)
    reading = ""
    if top is not None:
        reading = f"{top} drives {_pct(shares[top], 1, False)} of the variance; "
        reading += f"stock-specific risk is {_pct(shares[IDIO], 1, False)}."
        if vol is not None:
            reading += f" Total volatility is {_pct(vol, 1, False)} a year."
        reading += "".join(f" {s}" for s in rk.sentences)
    sum_res = _fin(rk.sums_to_one_residual)
    checks = f"Sum check {sum_res:.1e}." if sum_res is not None else ""
    fold = [
        rk.caption,
        "Euler decomposition of variance: share = beta x factor volatility x correlation with "
        "the factor-driven return, divided by total volatility.",
        *_label_texts(report, rk.labels),
        checks,
    ]
    return (
        f'<section class="panel" id="risk" aria-labelledby="risk-t">{head}'
        + (f'<p class="reading">{esc(reading)}</p>' if reading else "")
        + '<table class="bars cols-4 risk"><caption class="vh">Share of variance per factor and '
        "stock-specific, with exposure, factor volatility and correlation</caption>"
        '<thead><tr><th scope="col">Source</th><th scope="col" class="plot-h">'
        '<span class="vh">Chart</span></th><th scope="col" class="num">Share</th>'
        '<th scope="col" class="num">Beta</th><th scope="col" class="num">Factor vol</th>'
        '<th scope="col" class="num">Corr.</th></tr></thead>'
        f"<tbody>{''.join(rows)}</tbody>"
        f"<tfoot>{_axis_row(ticks, lo, hi, lambda t: _pct(t, 0, t < 0), 4)}</tfoot></table>"
        + _footnote(
            f"{_desc(report)} Shares add to 100% and can be negative when a factor offsets "
            "the others.",
            fold,
        )
        + "</section>"
    )


# --------------------------------------------------------------------------------------------
# Panel 8: exposure over time
# --------------------------------------------------------------------------------------------
def _rolling_block(
    w: RollingWindow,
    order: list[str],
    avg: dict[str, tuple[float, float, float, float, float, float]],
) -> str:
    """One window: five rows (line and band, then Latest, Average, Middle 80%)."""
    dates = w.dates
    z = _fin(w.ci_z) or HAC_DEFAULT_Z
    series: dict[str, list[tuple[int, float, float]]] = {}
    for name in order:
        pts: list[tuple[int, float, float]] = []
        for i, (b, s) in enumerate(zip(w.betas.get(name, []), w.se.get(name, []), strict=False)):
            bv, sv = _fin(b), _fin(s)
            if bv is not None and sv is not None:
                pts.append((i, bv, sv))
        if pts:
            series[name] = pts
    if not series:
        return _nodata(f"every {w.window}-day estimate is still in warm-up (no full window).")
    spans = [
        max(v + z * s for _, v, s in p) - min(v - z * s for _, v, s in p) for p in series.values()
    ]
    span = max(max(spans) * 1.08, 1e-9)
    i0 = min(p[0][0] for p in series.values())
    o0 = dates[i0].toordinal()
    o1 = max(dates[-1].toordinal(), o0 + 1)

    def x_of(i: int) -> float:
        return (dates[i].toordinal() - o0) / (o1 - o0) * 1000

    ticks = _date_ticks(dates[i0], dates[-1])

    def x_of_date(d: date) -> float:
        return (d.toordinal() - o0) / (o1 - o0) * 100  # percent of the plot width

    rows: list[str] = []
    for name, pts in series.items():
        mid = (max(v + z * s for _, v, s in pts) + min(v - z * s for _, v, s in pts)) / 2
        lo, hi = mid - span / 2, mid + span / 2

        def y_of(v: float, lo: float = lo, hi: float = hi) -> float:
            return 100 - (v - lo) / (hi - lo) * 100

        sp = _decimate(pts, 400)
        upper = [(x_of(i), y_of(v + z * s)) for i, v, s in sp]
        lower = [(x_of(i), y_of(v - z * s)) for i, v, s in sp][::-1]
        band = _path_xy(upper + lower) + "Z"
        line = _path_xy([(x_of(i), y_of(v)) for i, v, _ in sp])
        zero = (
            f'<line class="zero" x1="0" x2="1000" y1="{y_of(0):.2f}" y2="{y_of(0):.2f}"/>'
            if lo < 0 < hi
            else ""
        )
        vgrid = "".join(
            f'<line class="grid" x1="{x_of_date(d) * 10:.1f}" x2="{x_of_date(d) * 10:.1f}" '
            'y1="0" y2="100"/>'
            for d, _, major in ticks
            if major and d.month == 1
        )
        c = _slot(name, order)
        svg = (
            '<svg class="line-svg" viewBox="0 0 1000 100" preserveAspectRatio="none" role="img" '
            f'aria-label="{esc(f"Rolling {w.window}-day beta to {name}, with a 95 percent band")}">'
            f'{vgrid}{zero}<path class="band c{c}" d="{band}"/>'
            f'<path class="rline c{c}" d="{line}"/></svg>'
        )
        yl = [(hi, "top"), (lo, "bot")]
        if lo < 0 < hi and min(abs(hi), abs(lo)) > span * 0.22:
            yl.append((0.0, "mid"))
        ylab = "".join(
            f'<span class="yl {k}" style="top:{y_of(t):.2f}%">'
            f"{_sgn(t, 2) if abs(t) > 1e-9 else '0'}</span>"
            for t, k in yl
        )
        vals = [v for _, v, _ in pts]
        latest = vals[-1]
        if name in avg:
            mean, p10, p90, sd, vmin, vmax = avg[name]
            shp = sum(1 for v in vals if v > 0) / len(vals)
        else:
            mean = sum(vals) / len(vals)
            p10, p90 = _quantile(vals, 0.1), _quantile(vals, 0.9)
            sd = math.sqrt(sum((v - mean) ** 2 for v in vals) / max(len(vals) - 1, 1))
            vmin, vmax = min(vals), max(vals)
            shp = sum(1 for v in vals if v > 0) / len(vals)
        tip = (
            f"Spread {_num(sd)}, lowest {_sgn(vmin)}, highest {_sgn(vmax)}, above zero in "
            f"{shp * 100:.0f}% of windows"
        )
        rows.append(
            f'<tr><th scope="row"><span class="fname">{_key_swatch(f"cat c{c}")}{esc(name)}'
            f"</span>{_sub(_plain_name(name))}</th>"
            f'<td class="plot-cell"><div class="plot mini">{svg}'
            f'<div class="ylabels" aria-hidden="true">{ylab}</div></div></td>'
            f'<td class="num strong">{esc(_sgn(latest))}</td><td class="num">{esc(_sgn(mean))}</td>'
            f'<td class="num range" title="{esc(tip)}">{esc(_sgn(p10, 2))} to '
            f"{esc(_sgn(p90, 2))}</td></tr>"
        )
    xlab = "".join(
        f'<span class="xl{"" if major else " minor"} '
        f'{_edge(x_of_date(d))}" style="left:{x_of_date(d):.2f}%">{esc(lab)}</span>'
        for d, lab, major in ticks
    )
    k = w.window
    return (
        f'<div class="win w-{k}"><p class="print-only win-cap">{k}-day window</p>'
        '<table class="bars cols-3 rolling">'
        f'<caption class="vh">Rolling {k}-day betas per factor with a pointwise 95% band; '
        "latest, average and middle 80% of the estimates</caption>"
        '<thead><tr><th scope="col">Factor</th><th scope="col" class="plot-h">'
        '<span class="vh">Chart</span></th><th scope="col" class="num">Latest</th>'
        '<th scope="col" class="num">Average</th><th scope="col" class="num">Middle 80%</th>'
        f"</tr></thead><tbody>{''.join(rows)}</tbody>"
        '<tfoot><tr class="axis-row" aria-hidden="true"><td></td>'
        f'<td class="axis time">{xlab}</td><td colspan="3"></td></tr></tfoot></table>'
        f'<p class="foot">Each point uses the previous {k} trading days, so the chart starts at '
        f"the first full window, {_d_long(dates[i0])}. Latest is stamped {_d_long(dates[-1])}."
        "</p></div>"
    )


def _rolling_panel(report: FactorReport) -> str:
    wins = sorted(report.rolling, key=lambda x: x.window)
    ab = report.average_beta
    q = "Have the exposures been stable, or did they drift?"
    head = _panel_head("roll", "Exposure over time", q)
    order = _factor_order(report)
    ok = [w for w in wins if w.status == "ok" and w.dates]
    if not ok or not order:
        reason = next((w.reason for w in wins if w.reason), None)
        body = (
            _empty(
                reason,
                "Rolling betas need more trading days than the window length. "
                "Choose an earlier start date.",
            )
            if reason
            else _nodata("no rolling-beta series.")
        )
        return _section("rolling", head, body)
    primary = ab.window if any(w.window == ab.window for w in ok) else max(w.window for w in ok)
    avg: dict[str, tuple[float, float, float, float, float, float]] = {}
    if ab.status == "ok":
        for a in ab.factors:
            parts = (a.mean, a.p10, a.p90, a.sd, a.min, a.max)
            if all(_fin(p) is not None for p in parts):
                avg[a.name] = (
                    float(a.mean or 0.0),
                    float(a.p10 or 0.0),
                    float(a.p90 or 0.0),
                    float(a.sd or 0.0),
                    float(a.min or 0.0),
                    float(a.max or 0.0),
                )
    radios: list[str] = []
    labels: list[str] = []
    blocks: list[str] = []
    for w in wins:
        k = w.window
        radios.append(
            f'<input class="vh win-radio" type="radio" name="window" id="win-{k}" value="{k}"'
            f"{' checked' if k == primary else ''}>"
        )
        labels.append(f'<label for="win-{k}">{k} days</label>')
        if w.status == "ok" and w.dates:
            blocks.append(_rolling_block(w, order, avg if k == ab.window else {}))
        else:
            what = w.reason or f"The {k}-day window could not be computed."
            action = "Choose an earlier start date or the shorter window."
            blocks.append(f'<div class="win w-{k}">{_empty(what, action)}</div>')
    toggle = (
        '<div class="seg" role="group" aria-label="Rolling window length"><span class="seg-lab" '
        f'aria-hidden="true">Window</span><span class="seg-btns">{"".join(labels)}</span></div>'
    )
    captions = [w.caption for w in ok if w.caption]
    fold = [
        *captions[:1],
        "Every row uses the same vertical span, centred on its own values, so wiggles compare "
        "across factors.",
        *_label_texts(report, ok[0].labels),
    ]
    return (
        f"{''.join(radios)}"
        f'<section class="panel" id="rolling" aria-labelledby="roll-t">'
        f"{_panel_head('roll', 'Exposure over time', q, toggle)}"
        f"{''.join(blocks)}"
        f"{_footnote(f'{_desc(report)} The band is a pointwise 95% interval.', fold)}</section>"
    )


# --------------------------------------------------------------------------------------------
# Panel 9: data and audit, regression detail
# --------------------------------------------------------------------------------------------
def _dates_text(dates: Sequence[date], limit: int = 6) -> str:
    """Up to ``limit`` dates, then a count of the rest."""
    if not dates:
        return ""
    shown = ", ".join(_d_long(d) for d in dates[:limit])
    more = len(dates) - limit
    return f" ({shown}" + (f" and {more} more)" if more > 0 else ")")


def _data_panel(report: FactorReport) -> str:
    d = report.data
    q = "What went into these numbers, and what was left out?"
    reasons = ", ".join(
        f"{v} {EXCLUSION_TEXT.get(k, k)}" for k, v in sorted(d.excluded_by_reason.items())
    )
    unc = d.uncovered
    after = f"{unc.n} price days (raw return {_pct(unc.compounded_return)}, not analysed)"
    downloaded = (
        d.factors_downloaded_at.strftime("%Y-%m-%d %H:%M") + " UTC"
        if d.factors_downloaded_at
        else "Injected, not downloaded"
    )
    facts = [
        ("Requested", f"{_d_long(d.requested_start)} to {_d_long(d.requested_end)}"),
        (
            "Analysed",
            f"{_d_long(d.actual_start)} to {_d_long(d.actual_end)}, "
            f"{_plural(d.n_obs, 'trading day', 'trading days')}",
        ),
        ("Excluded inside the range", f"{d.n_excluded}" + (f" ({reasons})" if reasons else "")),
        ("After factor data", after if unc.n else "none"),
        ("Before factor data", f"{d.dropped_price_dates_before_factors} price days"),
        (
            "Factor data ends",
            f"{_d_long(d.factors_last_date)}, {d.factors_days_behind} days before the report",
        ),
        ("Factor file downloaded", downloaded),
        ("Prices", d.price_source),
        ("Factors", d.factors_source_url),
    ]
    dl = "".join(f"<div><dt>{esc(a)}</dt><dd>{esc(b)}</dd></div>" for a, b in facts)
    finds = "".join(
        f'<li class="sev-{esc(f.severity)}">{GLYPHS.get(f.severity, "")}'
        f'<span class="sev">{esc(f.severity.capitalize())}</span>'
        f'<span class="msg">{esc(f.message)}'
        f'<span class="dates">{esc(_dates_text(f.dates))}</span></span></li>'
        for f in d.audit_findings
    ) or (
        '<li class="sev-none"><span class="msg">No findings. Prices passed every check.</span></li>'
    )
    notes = "".join(f"<li>{esc(n)}</li>" for n in report.notes)
    vintage = report.label_text.get("L-VINTAGE")
    if vintage and vintage not in report.notes:
        notes += f"<li>{esc(vintage)}</li>"
    return (
        f'<section class="panel data" id="data" aria-labelledby="data-t">'
        f"{_panel_head('data', 'Data and audit', q)}"
        '<div class="data-grid"><div><h3>Coverage</h3>'
        f'<dl class="facts">{dl}</dl></div><div><h3>Audit findings</h3>'
        f'<ul class="findings">{finds}</ul><h3>Caveats</h3><ul class="notes">{notes}</ul></div>'
        "</div>"
        + _footnote("Audit findings are reported, never acted on: no price is changed or removed.")
        + "</section>"
    )


def _reg_table(label: str, heads: Sequence[str], rows: Sequence[str], rd: int | None = None) -> str:
    cols = "".join(
        f'<th scope="col" class="{"rd" if i == rd else "num"}">{esc(h)}</th>'
        for i, h in enumerate(heads)
        if i > 0
    )
    return (
        f'<div class="scroll-x" tabindex="0" role="region" aria-label="{esc(label)}, scrolls '
        f'sideways"><table class="reg"><thead><tr><th scope="col">{esc(heads[0])}</th>{cols}'
        f"</tr></thead><tbody>{''.join(rows)}</tbody></table></div>"
    )


def _term_rows(
    alpha_ann: float | None,
    alpha_se: float | None,
    alpha_z: float | None,
    alpha_p: float | None,
    alpha_ci: tuple[float | None, float | None],
    alpha_tag: str | None,
    stats: Sequence[FactorStat],
    vif: dict[str, float | None] | None,
) -> list[str]:
    a_ns = alpha_tag != "reliable"
    ci = f"{_pct(alpha_ci[0])} to {_pct(alpha_ci[1])}"
    rows = [
        f'<tr class="{"ns" if a_ns else ""}"><th scope="row">Alpha, a year</th>'
        f'<td class="num">{esc(_pct(alpha_ann))}</td>'
        f'<td class="num">{esc(_pct(alpha_se, 2, False))}</td>'
        f'<td class="num">{esc(_tstat(alpha_z))}</td><td class="num">{_pval(alpha_p)}</td>'
        f'<td class="num">single test</td><td class="num">{esc(ci)}</td>'
        + ('<td class="num">&#8211;</td>' if vif is not None else "")
        + f'<td class="num sig">{"No" if a_ns else "Yes"}</td></tr>'
    ]
    for s in stats:
        ns = not _is_reliable(s)
        vif_cell = (
            f'<td class="num">{esc(_num(vif.get(s.name), 2))}</td>' if vif is not None else ""
        )
        rows.append(
            f'<tr class="{"ns" if ns else ""}"><th scope="row">{esc(s.name)}</th>'
            f'<td class="num">{esc(_sgn(s.beta))}</td><td class="num">{esc(_num(s.se, 4))}</td>'
            f'<td class="num">{esc(_tstat(s.z))}</td><td class="num">{_pval(s.p)}</td>'
            f'<td class="num">{_pval(s.p_adj_bh)}</td>'
            f'<td class="num">{esc(_sgn(s.ci_low))} to {esc(_sgn(s.ci_high))}</td>'
            f'{vif_cell}<td class="num sig">{"No" if ns else "Yes"}</td></tr>'
        )
    return rows


def _detail_panel(report: FactorReport) -> str:
    rg = report.regression
    head = _panel_head(
        "detail",
        "Regression detail",
        "OLS with an intercept and Newey-West standard errors.",
    )
    if rg.status != "ok":
        return _section("detail", head, _empty(rg.reason or "The regression is not available."))
    heads = [
        "Term",
        "Estimate",
        "Std. error",
        "t",
        "p",
        "p, adjusted",
        "95% interval",
        "VIF",
        "Significant",
    ]
    table = _reg_table(
        "Regression detail table",
        heads,
        _term_rows(
            rg.alpha_annual,
            rg.alpha_se_annual,
            rg.alpha_z,
            rg.alpha_p,
            (rg.alpha_ci_low_annual, rg.alpha_ci_high_annual),
            rg.alpha_tag,
            rg.factors,
            rg.vif,
        ),
    )
    pairs = ", ".join(f"{p.a}/{p.b} {_sgn(p.corr, 2)}" for p in rg.high_corr_pairs)
    sentence = f'<p class="reading">{esc(rg.alpha_sentence)}</p>' if rg.alpha_sentence else ""
    reads = [s.interpretation for s in rg.factors if s.interpretation]
    reading = (
        '<h3 class="reg-title">Reading the significant betas</h3><ul class="notes">'
        + "".join(f"<li>{esc(t)}</li>" for t in reads)
        + "</ul>"
        if reads
        else ""
    )
    foot = _footnote(
        f"R² {_num(rg.r2, 4)}, adjusted {_num(rg.adj_r2, 4)}. Residual volatility "
        f"{_pct(rg.sigma_e_annual, 2, False)} a year. Newey-West lags {rg.hac_lags}.",
        [
            rg.caption,
            f"Condition number of the factor correlation matrix {_num(rg.condition_number, 2)}"
            + (f"; pairs with |correlation| above 0.6: {pairs}." if pairs else "."),
            *_label_texts(report, rg.labels),
        ],
    )
    return (
        f'<section class="panel" id="detail" aria-labelledby="detail-t">{head}{table}{sentence}'
        f"{reading}{_five_day_table(report)}{_diagnostics_table(report)}{foot}</section>"
    )


def _five_day_table(report: FactorReport) -> str:
    """The 5-day estimate of M3.6, shown only when the quality gate fired."""
    five = report.five_day_regression
    if five.status != "ok":
        return ""
    heads = [
        "Term",
        "Estimate",
        "Std. error",
        "t",
        "p",
        "p, adjusted",
        "95% interval",
        "Significant",
    ]
    table = _reg_table(
        "5-day estimate table",
        heads,
        _term_rows(
            five.alpha_annual,
            five.alpha_se_annual,
            five.alpha_z,
            five.alpha_p,
            (five.alpha_ci_low_annual, five.alpha_ci_high_annual),
            five.alpha_tag,
            five.factors,
            None,
        ),
    )
    cap = (
        f"{five.caption} R² {_num(five.r2, 4)}, residual volatility "
        f"{_pct(five.sigma_e_annual, 2, False)} a year, Newey-West lags {five.hac_lags}."
    )
    return (
        f'<h3 class="reg-title">5-day estimate ({five.n_blocks:,} blocks)</h3>{table}'
        f'<p class="foot">{esc(cap)}</p>'
    )


def _diagnostics_table(report: FactorReport) -> str:
    """Residual diagnostics of M3.5 with their plain-language readings."""
    rd = report.residual_diagnostics
    if rd.status != "ok":
        return '<h3 class="reg-title">Residual diagnostics</h3>' + _empty(
            rd.reason or "Not available."
        )
    rows = [
        "<tr><th scope='row'>Lag-1 autocorrelation</th>"
        f'<td class="num">{esc(_sgn(rd.lag1_autocorrelation))}</td>'
        f'<td class="num">z {esc(_tstat(rd.lag1_z))}</td><td class="num">{_pval(rd.lag1_p)}</td>'
        f'<td class="rd">{esc(rd.lag1_reading or "")}</td></tr>'
    ]
    for t in rd.tests:
        rows.append(
            f"<tr><th scope='row'>{esc(t.name)}</th><td class=\"num\">{esc(_num(t.statistic, 2))}"
            f'</td><td class="num">{"" if t.df is None else f"df {t.df}"}</td>'
            f'<td class="num">{_pval(t.p)}</td><td class="rd">{esc(t.reading)}</td></tr>'
        )
    table = _reg_table(
        "Residual diagnostics table", ["Test", "Statistic", "Reference", "p", "Reading"], rows, rd=4
    )
    return (
        f'<h3 class="reg-title">Residual diagnostics</h3>{table}'
        f'<p class="foot">{esc(rd.note)} {esc(rd.caption)}</p>'
    )


# --------------------------------------------------------------------------------------------
# Page
# --------------------------------------------------------------------------------------------
def _add_roles(body: str) -> str:
    """Explicit table roles: narrow screens restyle rows as grids, which can drop semantics."""

    def fix(m: re.Match[str]) -> str:
        t = m.group(0)
        t = t.replace('<table class="bars', '<table role="table" class="bars')
        t = re.sub(r"<tr(?=[ >])", '<tr role="row"', t)
        t = t.replace('<th scope="row"', '<th role="rowheader" scope="row"')
        t = t.replace('<th scope="col"', '<th role="columnheader" scope="col"')
        t = re.sub(r"<td(?=[ >])", '<td role="cell"', t)
        return re.sub(r"<(thead|tbody|tfoot)>", lambda g: f'<{g.group(1)} role="rowgroup">', t)

    return re.sub(r'<table class="bars.*?</table>', fix, body, flags=re.S)


def _colophon(report: FactorReport) -> str:
    g = report.generated_at
    stamp = f"{g.day} {MONTHS[g.month - 1]} {g.year}, {g:%H:%M} UTC"
    return (
        f'<footer class="colophon"><p>factordesk report, schema v{esc(report.schema_version)}, '
        f"generated {stamp}. Descriptive statistics on past data; nothing here is a forecast "
        "or advice.</p></footer>"
    )


def render_report_html(report: FactorReport) -> str:
    """Render ``report`` as a single self-contained HTML document (no external resources)."""
    title = f"{report.ticker} factor profile"
    windows = [w.window for w in report.rolling]
    body = "\n".join(
        [
            HATCH_DEFS,
            '<main class="report">',
            _header(report),
            _equation(report),
            _kpis(report),
            _price_panel(report),
            _exposures_panel(report),
            _return_panel(report),
            _risk_panel(report),
            _rolling_panel(report),
            _data_panel(report),
            _detail_panel(report),
            _colophon(report),
            "</main>",
        ]
    )
    return (
        '<!doctype html>\n<html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<meta name="color-scheme" content="light dark">'
        f"<title>{esc(title)}</title><style>\n{font_faces()}{base_css()}\n"
        f"{_window_css(windows)}</style></head>\n<body>\n{_add_roles(body)}\n</body></html>\n"
    )


def write_report(report: FactorReport, path: str | Path) -> Path:
    """Render and write the HTML file (UTF-8, LF line endings); returns the written path."""
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(render_report_html(report).encode("utf-8"))
    return out
