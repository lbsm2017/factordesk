"""Throwaway generator for the report design prototype.

Reads the mock fixture (JSON only), writes one self-contained HTML page next to this file.
Standard library only; imports nothing from the project and modifies nothing outside
``docs/design/prototype/``.

    uv run --no-project python docs/design/prototype/build_prototype.py
    uv run --no-project python docs/design/prototype/build_prototype.py --empty   # empty-state demo
    uv run --no-project python docs/design/prototype/build_prototype.py --controls # dashboard controls mock
"""

from __future__ import annotations

import base64
import copy
import html
import json
import math
import re
import sys
from datetime import date, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
FIXTURE = ROOT / "backend" / "factordesk" / "tests" / "fixtures" / "mock_report.json"
FONTS = HERE / "fonts"

MINUS = "−"
THIN = " "
FACTORS = ("Mkt-RF", "SMB", "HML", "RMW", "CMA")
PLAIN = {
    "Mkt-RF": "Market",
    "SMB": "Size",
    "HML": "Value",
    "RMW": "Profitability",
    "CMA": "Investment",
}
SLOT = {name: i + 1 for i, name in enumerate(FACTORS)}

e = html.escape


# ----------------------------------------------------------------------------- formatting
def sgn(x: float, d: int = 3) -> str:
    """Signed number with a true minus sign; zero prints unsigned."""
    s = f"{abs(x):,.{d}f}"
    if float(s.replace(",", "")) == 0:
        return s
    return ("+" if x > 0 else MINUS) + s


def num(x: float, d: int = 3) -> str:
    s = f"{abs(x):,.{d}f}"
    return (MINUS + s) if x < 0 and float(s.replace(",", "")) != 0 else s


def pct(x: float, d: int = 2, signed: bool = True) -> str:
    return (sgn if signed else num)(x * 100, d) + "%"


def tstat(z: float) -> str:
    return num(z, 0) if abs(z) >= 100 else num(z, 1)


def pval(p: float) -> str:
    return "<0.001" if p < 0.001 else f"{p:.3f}"


def d_long(s: str) -> str:
    d = date.fromisoformat(s)
    return f"{d.day} {d.strftime('%b')} {d.year}"


def d_short(s: str) -> str:
    d = date.fromisoformat(s)
    return f"{d.strftime('%b')} {d.year}"


# ----------------------------------------------------------------------------- scales
def nice_step(span: float, target: int = 4) -> float:
    raw = span / max(target, 1)
    mag = 10 ** math.floor(math.log10(raw))
    for m in (1, 2, 2.5, 5, 10):
        if raw <= m * mag:
            return m * mag
    return 10 * mag


def nice_domain(lo: float, hi: float, target: int = 4) -> tuple[float, float, list[float]]:
    if hi - lo < 1e-12:
        hi, lo = hi + 0.5, lo - 0.5
    step = nice_step(hi - lo, target)
    nlo = math.floor(lo / step - 1e-9) * step
    nhi = math.ceil(hi / step + 1e-9) * step
    ticks = []
    t = nlo
    while t <= nhi + step / 2:
        ticks.append(round(t, 10))
        t += step
    return nlo, nhi, ticks


def pos(v: float, lo: float, hi: float) -> float:
    return round((v - lo) / (hi - lo) * 100, 3)


# ----------------------------------------------------------------------------- small pieces
def footnote(text: str, more: str = "") -> str:
    """One visible line or two; the method detail folds into a native <details> (open in print)."""
    if not more:
        return f'<p class="foot">{text}</p>'
    return (
        f'<div class="foot"><p>{text}</p><details class="how"><summary>How this is computed</summary>'
        f"<p>{more}</p></details></div>"
    )


def panel_head(pid: str, title: str, question: str, extra: str = "") -> str:
    return (
        f'<header class="panel-head"><div><h2 id="{pid}-t">{e(title)}</h2>'
        f'<p class="q">{e(question)}</p></div>{extra}</header>'
    )


def empty_state(reason: str, action: str) -> str:
    return (
        '<div class="empty" role="note"><p class="empty-what">'
        f"{e(reason)}</p><p class=\"empty-do\">{e(action)}</p></div>"
    )


def edge(x: float) -> str:
    """Tick labels at the plot edges are anchored inward so they never overflow."""
    return "edge-l" if x < 3 else ("edge-r" if x > 97 else "")


def axis_row(ticks: list[float], lo: float, hi: float, fmt, ncols: int) -> str:
    k0 = next((k for k, t in enumerate(ticks) if abs(t) < 1e-12), 0)  # the zero label always survives thinning
    labels = "".join(
        f'<span class="{edge(pos(t, lo, hi))}{" alt" if ((k - k0) % 2 and len(ticks) > 5) else ""}" style="left:{pos(t, lo, hi)}%">{fmt(t)}</span>'
        for k, t in enumerate(ticks)
    )
    return (
        f'<tr class="axis-row" aria-hidden="true"><td></td><td class="axis">{labels}</td>'
        f'<td colspan="{ncols}"></td></tr>'
    )


def grid_lines(ticks: list[float], lo: float, hi: float, zero: bool = True) -> str:
    out = []
    for t in ticks:
        cls = "zero" if (zero and abs(t) < 1e-12) else "grid"
        out.append(f'<line class="{cls}" x1="{pos(t, lo, hi)}%" x2="{pos(t, lo, hi)}%" y1="0" y2="100%"/>')
    return "".join(out)


def bar(v: float, lo: float, hi: float, cls: str) -> str:
    a, b = sorted((pos(0.0, lo, hi), pos(v, lo, hi)))
    return f'<rect class="{cls}" x="{a}%" y="32%" width="{max(b - a, 0.0)}%" height="36%" rx="2"/>'


# ----------------------------------------------------------------------------- panels
WARN_PLAIN = {
    "residual_reversal": "Prices look out of step with the factor data, so R\u00b2 is probably understated and residual volatility overstated.",
    "short_history": "The history is short, so the betas rest on a small sample.",
    "audit_errors": "The price audit found errors, so the headline numbers are not interpretable until they are explained; see Data and audit.",
}
GLYPH_WARN = (
    '<svg class="glyph" aria-hidden="true" viewBox="0 0 16 16"><path d="M8 1.5 15 14.5H1z"/>'
    '<path class="cut" d="M8 6v4M8 11.6v1"/></svg>'
)


def range_line(r: dict) -> str:
    d = r["data"]
    s = f"Analysed {d_long(d['actual_start'])} to {d_long(d['actual_end'])}, {d['n_obs']:,} trading days."
    if d["uncovered"]["n"]:
        s += f" The last {d['uncovered']['n']} price days are charted but not analysed."
    return s


def header(r: dict, controls: bool = False) -> str:
    d = r["data"]
    ws = r["warnings"]
    chips = (
        f'<span class="chip">Factor data ends {d_long(d["factors_last_date"])} '
        f'({d["factors_days_behind"]} days ago)</span>'
    )
    if ws:
        chips += f'<a class="chip warn" href="#notice">{len(ws)} warning{"" if len(ws) == 1 else "s"}</a>'
    top = (
        f'<div class="mast-top"><h1><span class="ticker">{e(r["ticker"])}</span>'
        f'<span class="what">Fama&#8211;French five-factor profile</span></h1>'
        f'<p class="mast-meta">{chips}</p></div>'
    )
    notice = ""
    if ws:
        summ = " ".join(WARN_PLAIN.get(w["code"], w["message"]) for w in ws[:2])
        more = "".join(f"<li>{e(w['message'])}</li>" for w in ws)
        notice = (
            f'<aside class="notice" id="notice" aria-label="Data quality">{GLYPH_WARN}'
            f'<div><p class="notice-sum"><span class="vh">Warning: </span>{e(summ)}</p>'
            f'<details class="how"><summary>Details</summary><ul>{more}</ul></details></div></aside>'
        )
    line = "" if controls else f'<p class="coverage">{e(range_line(r))}</p>'
    return f"""
<header class="masthead">
  {top}
  {line}
  {notice}
</header>"""


def equation(r: dict) -> str:
    g = r["regression"]
    if g["status"] != "ok":
        return ""
    terms = []
    a_ns = g["alpha_tag"] != "reliable"
    a = g["alpha_annual"]
    terms.append(
        f'<a class="term{" ns" if a_ns else ""}" href="#ret-alpha">'
        f'<span class="m">{"" if a >= 0 else MINUS}{num(abs(a) * 100, 2)}%</span>'
        f'<span class="ann"><span>alpha, a year</span>'
        f'<span>{"not significant" if a_ns else "significant"}, t {tstat(g["alpha_z"])}</span></span></a>'
    )
    for f in g["factors"]:
        ns = f["tag"] != "reliable"
        b = f["beta"]
        terms.append(
            f'<a class="term{" ns" if ns else ""}" href="#beta-{f["name"]}">'
            f'<span class="m"><span class="op">{"+" if b >= 0 else MINUS}</span>{num(abs(b), 3)}'
            f'<span class="fn">{e(f["name"])}</span></span>'
            f'<span class="ann"><span>{PLAIN[f["name"]].lower()}</span>'
            f'<span>{"not significant" if ns else "significant"}, t {tstat(f["z"])}</span></span></a>'
        )
    terms.append(
        '<span class="term eps"><span class="m"><span class="op">+</span><var>&#949;</var></span>'
        f'<span class="ann"><span>residual</span><span>{pct(g["sigma_e_annual"], 1, False)} a year</span></span></span>'
    )
    label = "Fitted model: daily excess return equals " + ", ".join(
        [f"alpha {pct(a)} a year"] + [f"{sgn(f['beta'])} times {f['name']}" for f in g["factors"]]
    ) + ", plus a residual."
    return f"""
<figure class="model" aria-label="{e(label)}">
  <div class="eq">
    <span class="lhs" aria-hidden="true"><var>r</var><span class="op">&#8722;</span><var>r</var><sub>f</sub><span class="op eqs">=</span></span>
    <span class="terms">{''.join(terms)}</span>
  </div>
  <figcaption>The fitted daily model, in-sample. Faded terms are not statistically significant. Select a term to see its detail.</figcaption>
</figure>"""


def kpis(r: dict) -> str:
    g, d = r["regression"], r["data"]
    if g["status"] != "ok":
        return f'<section class="kpis" aria-label="Headline statistics">{empty_state(g["reason"], "Widen the date range and run the report again.")}</section>'
    a_ns = g["alpha_tag"] != "reliable"
    # Validation F4: with audit errors the fitted tiles are muted and alpha makes no significance claim.
    audit_errors = d["audit_status"] == "errors"
    fit_cls = "ns" if audit_errors else ""
    if audit_errors:
        alpha_note, a_ns = "Not interpretable: the price audit found errors", True
    else:
        alpha_note = "Not distinguishable from zero" if a_ns else "Distinguishable from zero at 5%"
    excl = d["n_excluded"]
    cells = [
        ("Alpha, a year", pct(g["alpha_annual"]), alpha_note, "ns" if a_ns else ""),
        ("R&#178;", f"{g['r2']:.4f}", "Share of daily variance the factors explain", fit_cls),
        ("Residual volatility", pct(g["sigma_e_annual"], 1, False), "A year, left unexplained by the factors", fit_cls),
        ("Observations", f"{d['n_obs']:,}", f"Trading days; {excl} excluded" if excl else "Trading days; none excluded", ""),
        ("Analysed range", f"{d_short(d['actual_start'])} to {d_short(d['actual_end'])}",
         f"Requested {d_long(d['requested_start'])} to {d_long(d['requested_end'])}", "dates"),
    ]
    body = "".join(
        f'<div class="kpi {cls}"><dt>{lab}</dt><dd class="v">{val}</dd><dd class="n">{e(note)}</dd></div>'
        for lab, val, note, cls in cells
    )
    return f'<section class="kpis" aria-label="Headline statistics"><dl>{body}</dl></section>'


def date_ticks(dates: list[str], months: tuple[int, ...] = (1, 4, 7, 10)) -> list[tuple[int, str, bool]]:
    """Index of the first trading day of each quarter; bool = major (January)."""
    out, seen = [], set()
    for i, s in enumerate(dates):
        d = date.fromisoformat(s)
        key = (d.year, d.month)
        if d.month in months and key not in seen and d.day <= 7:
            seen.add(key)
            out.append((i, f"{d.strftime('%b')} {d.year}", d.month == 1))
    return out


def path_xy(xs: list[float], ys: list[float]) -> str:
    return "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in zip(xs, ys))


def price_panel(r: dict) -> str:
    p = r["price_series"]
    dates, px = p["dates"], p["adj_close"]
    pts = [(i, v) for i, v in enumerate(px) if v is not None]
    head = panel_head("price", "Price", "How has the price moved over the window? Shaded days are not in the analysis.")
    if len(pts) < 2:
        return f'<section class="panel" aria-labelledby="price-t">{head}{empty_state("No prices were returned for this ticker and window.", "Check the ticker symbol or choose a later start date.")}</section>'
    cov = p["factor_coverage_end"]
    cut = max((i for i, s in enumerate(dates) if s <= cov), default=len(dates) - 1)
    lo, hi, ticks = nice_domain(min(v for _, v in pts), max(v for _, v in pts), 4)
    n = len(dates) - 1
    H = 100.0
    X = lambda i: i / n * 1000  # noqa: E731
    Y = lambda v: H - (v - lo) / (hi - lo) * H  # noqa: E731
    main = [(X(i), Y(v)) for i, v in pts if i <= cut]
    tail = [(X(i), Y(v)) for i, v in pts if i >= cut]
    grid = "".join(f'<line class="grid" x1="0" x2="1000" y1="{Y(t):.2f}" y2="{Y(t):.2f}"/>' for t in ticks)
    start_i = next((i for i, s in enumerate(dates) if s >= r["data"]["actual_start"]), 0)
    shade = ""
    if cut < n:
        shade += (
            f'<rect class="tailzone" x="{X(cut):.1f}" y="0" width="{1000 - X(cut):.1f}" height="100"/>'
            f'<line class="cutline" x1="{X(cut):.1f}" x2="{X(cut):.1f}" y1="0" y2="100"/>'
        )
    if start_i > 0:
        shade += (
            f'<rect class="tailzone" x="0" y="0" width="{X(start_i):.1f}" height="100"/>'
            f'<line class="cutline" x1="{X(start_i):.1f}" x2="{X(start_i):.1f}" y1="0" y2="100"/>'
        )
    svg = (
        f'<svg class="line-svg" viewBox="0 0 1000 100" preserveAspectRatio="none" aria-hidden="true">{shade}{grid}'
        f'<path class="price-line" d="{path_xy(*zip(*main))}"/>'
        + (f'<path class="price-tail" d="{path_xy(*zip(*tail))}"/>' if len(tail) > 1 else "")
        + "</svg>"
    )
    ylab = "".join(f'<span class="yl" style="top:{Y(t):.2f}%">{t:,.0f}</span>' for t in ticks)
    xt = date_ticks(dates)
    xlab = "".join(
        f'<span class="xl{" minor" if not major else ""} {edge(X(i) / 10)}" style="left:{X(i) / 10:.2f}%">{lab}</span>' for i, lab, major in xt
    )
    tail_lab = (
        f'<span class="zone-label">Not analysed: factor data ends {d_long(cov)}</span>' if cut < n else ""
    )
    if start_i > 0:
        tail_lab += f'<span class="zone-label l">Not analysed: before {d_long(dates[start_i])}</span>'
    d = r["data"]
    first, last_in, last = px[pts[0][0]], px[cut], pts[-1][1]
    u = d["uncovered"]
    rows = [
        ("First", d_long(dates[pts[0][0]]), f"{first:,.2f}"),
        ("End of factor data", d_long(dates[cut]), f"{last_in:,.2f}"),
        ("Latest", d_long(dates[pts[-1][0]]), f"{last:,.2f}"),
    ]
    side = "".join(f'<tr><th scope="row">{a}<span class="sub">{b}</span></th><td class="num">{c}</td></tr>' for a, b, c in rows)
    if u["n"] and u["compounded_return"] is not None:
        side += (
            f'<tr class="muted-row"><th scope="row">After factor data<span class="sub">{u["n"]} days, raw, not analysed</span></th>'
            f'<td class="num">{pct(u["compounded_return"])}</td></tr>'
        )
    return f"""
<section class="panel" id="price" aria-labelledby="price-t">
  {head}
  <div class="price-wrap">
    <div class="plot price-plot">{svg}<div class="ylabels" aria-hidden="true">{ylab}</div>{tail_lab}<div class="xlabels" aria-hidden="true">{xlab}</div></div>
    <table class="side"><caption class="vh">Price points</caption>
      <thead class="vh"><tr><th scope="col">Point</th><th scope="col">Adjusted close</th></tr></thead><tbody>{side}</tbody></table>
  </div>
  {footnote(f"Adjusted close from {e(d['price_source'])}, for context only; no statistic uses the price line.")}
</section>"""


def exposures_panel(r: dict) -> str:
    g, ab = r["regression"], r["average_beta"]
    head = panel_head("beta", "Factor exposures", "What is this stock exposed to, and how sure are we?")
    if g["status"] != "ok":
        return f'<section class="panel" id="exposures" aria-labelledby="beta-t">{head}{empty_state(g["reason"], "Widen the date range and run the report again.")}</section>'
    avg = {f["name"]: f["mean"] for f in ab["factors"]} if ab["status"] == "ok" else {}
    vals = [v for f in g["factors"] for v in (f["ci_low"], f["ci_high"], f["beta"])] + [0.0]
    lo, hi, ticks = nice_domain(min(vals), max(vals), 5)
    rows = []
    for f in g["factors"]:
        ns = f["tag"] != "reliable"
        b = f["beta"]
        cls = ("pos" if b >= 0 else "neg") + (" faded" if ns else "")
        whisk = (
            f'<line class="ci" x1="{pos(f["ci_low"], lo, hi)}%" x2="{pos(f["ci_high"], lo, hi)}%" y1="50%" y2="50%"/>'
        )
        if pos(f["ci_high"], lo, hi) - pos(f["ci_low"], lo, hi) >= 1.2:  # caps only when the interval is wide enough to read
            whisk += (
                f'<line class="ci" x1="{pos(f["ci_low"], lo, hi)}%" x2="{pos(f["ci_low"], lo, hi)}%" y1="46.5%" y2="53.5%"/>'
                f'<line class="ci" x1="{pos(f["ci_high"], lo, hi)}%" x2="{pos(f["ci_high"], lo, hi)}%" y1="46.5%" y2="53.5%"/>'
            )
        tip = (
            f"{f['name']}: beta {sgn(b)}, 95% interval {sgn(f['ci_low'])} to {sgn(f['ci_high'])}, "
            f"t {tstat(f['z'])}, adjusted p {pval(f['p_adj_bh'])}"
        )
        a = avg.get(f["name"])
        if a is not None:
            whisk += (
                f'<svg class="avgm" x="{pos(a, lo, hi)}%" y="50%" overflow="visible" aria-hidden="true">'
                '<path d="M0 -3.6 3.6 0 0 3.6-3.6 0z"/></svg>'
            )
        rows.append(
            f'<tr id="beta-{f["name"]}" class="{"ns" if ns else ""}" tabindex="-1">'
            f'<th scope="row"><span class="fname">{e(f["name"])}</span><span class="sub">{PLAIN[f["name"]]}</span></th>'
            f'<td class="plot-cell"><svg class="bar-svg" aria-hidden="true"><title>{e(tip)}</title>'
            f"{grid_lines(ticks, lo, hi)}{bar(b, lo, hi, cls)}{whisk}</svg></td>"
            f'<td class="num strong">{sgn(b)}</td><td class="num">{tstat(f["z"])}</td>'
            f'<td class="num sig">{"No" if ns else "Yes"}</td>'
            f'<td class="num">{sgn(a) if a is not None else "&#8211;"}</td></tr>'
        )
    reading = exposure_reading(g)
    legend = (
        '<ul class="legend" aria-label="Legend">'
        '<li><svg class="sw" aria-hidden="true"><rect class="pos" width="14" height="10" rx="2"/></svg>Positive</li>'
        '<li><svg class="sw" aria-hidden="true"><rect class="neg" width="14" height="10" rx="2"/></svg>Negative</li>'
        '<li><svg class="sw" aria-hidden="true"><rect class="pos faded" x="0.5" y="0.5" width="13" height="9" rx="2"/></svg>Faded: not significant</li>'
        '<li><svg class="sw" aria-hidden="true"><line class="ci" x1="1" x2="15" y1="5" y2="5"/><line class="ci" x1="1" x2="1" y1="3.5" y2="6.5"/><line class="ci" x1="15" x2="15" y1="3.5" y2="6.5"/></svg>95% interval</li>'
        f'<li><svg class="sw" aria-hidden="true"><path class="avgm-sw" d="M8 1.4 11.6 5 8 8.6 4.4 5z"/></svg>Average {ab.get("window", 252)}d beta</li>'
        "</ul>"
    )
    return f"""
<section class="panel" id="exposures" aria-labelledby="beta-t">
  {panel_head("beta", "Factor exposures", "What is this stock exposed to, and how sure are we?", legend)}
  <p class="reading">{reading}</p>
  <table class="bars cols-4">
    <caption class="vh">Full-sample factor betas with 95% intervals, t-statistics, significance and average rolling beta</caption>
    <thead><tr><th scope="col">Factor</th><th scope="col" class="plot-h"><span class="vh">Chart</span></th>
      <th scope="col" class="num">Beta</th><th scope="col" class="num">t</th><th scope="col" class="num"><span class="long">Significant</span><span class="short" aria-hidden="true">Sig.</span></th>
      <th scope="col" class="num">Avg {ab.get('window', 252)}d</th></tr></thead>
    <tbody>{''.join(rows)}</tbody>
    <tfoot>{axis_row(ticks, lo, hi, lambda t: sgn(t, 2) if t else "0", 4)}</tfoot>
  </table>
  {footnote("In-sample, descriptive, not predictive. Significant means the adjusted p is below 0.05.", f"OLS on daily excess returns with Newey&#8211;West standard errors ({g['hac_lags']} lags). Significant means the Benjamini&#8211;Hochberg adjusted p is below 0.05 across the {g['bh_family_size']} betas. The diamond and the Avg {ab.get('window', 252)}d column are the mean of the overlapping rolling estimates.")}
</section>"""


TILT = {
    "SMB": ("small companies", "large companies"),
    "HML": ("value stocks", "growth stocks"),
    "RMW": ("highly profitable firms", "weakly profitable firms"),
    "CMA": ("firms that invest conservatively", "firms that invest aggressively"),
}


def exposure_reading(g: dict) -> str:
    parts, quiet = [], []
    for f in g["factors"]:
        n, b = f["name"], f["beta"]
        if f["tag"] != "reliable":
            quiet.append(f"{PLAIN[n].lower()} ({n})")
            continue
        if n == "Mkt-RF":
            if abs(b - 1) < 0.1:
                parts.append(f"moves roughly one-for-one with the market (beta {num(b)})")
            elif b > 1:
                parts.append(f"amplifies market moves (beta {num(b)})")
            else:
                parts.append(f"moves less than the market (beta {num(b)})")
        else:
            parts.append(f"leans toward {TILT[n][0 if b > 0 else 1]} ({n} {sgn(b)})")
    s = ""
    if parts:
        s = "Over this window the stock " + (", ".join(parts[:-1]) + " and " + parts[-1] if len(parts) > 1 else parts[0]) + "."
    if quiet:
        q = ", ".join(quiet[:-1]) + " or " + quiet[-1] if len(quiet) > 1 else quiet[0]
        s += f" There is no clear tilt to {q}."
    return e(s).replace("&#x27;", "'")


def return_panel(r: dict) -> str:
    rc, g = r["return_contribution"], r["regression"]
    head_args = ("ret", "Where the return came from", "How much of the average yearly return does each factor explain?")
    if rc["status"] != "ok":
        return f'<section class="panel" id="returns" aria-labelledby="ret-t">{panel_head(*head_args)}{empty_state(rc["reason"], "Widen the date range and run the report again.")}</section>'
    tags = {f["name"]: f["tag"] for f in g["factors"]}
    items = [(n, PLAIN[n], rc["factors"][n], tags.get(n) != "reliable", "factor") for n in FACTORS]
    items.append(("Alpha", "Unexplained average", rc["alpha"], g["alpha_tag"] != "reliable", "alpha"))
    items.append(("Residual", "Zero by construction", rc["residual"], False, "resid"))
    total = rc["total_annualised_mean_excess_return"]
    vals = [x[2] for x in items] + [total, 0.0]
    lo, hi, ticks = nice_domain(min(vals), max(vals), 5)
    rows = []
    for n, plain, v, ns, kind in items:
        if kind == "resid":
            cls = "hatch"
        else:
            cls = ("pos" if v >= 0 else "neg") + (" faded" if ns else "")
        rid = "ret-alpha" if kind == "alpha" else f"ret-{n}"
        sig = "&#8211;" if kind == "resid" else ("No" if ns else "Yes")
        rows.append(
            f'<tr id="{rid}" class="{"ns" if ns else ""} {kind}" tabindex="-1"><th scope="row"><span class="fname">{e(n)}</span><span class="sub">{plain}</span></th>'
            f'<td class="plot-cell"><svg class="bar-svg" aria-hidden="true"><title>{e(n)}: {pct(v)} a year</title>{grid_lines(ticks, lo, hi)}{bar(v, lo, hi, cls)}</svg></td>'
            f'<td class="num strong">{pct(v)}</td><td class="num sig">{sig}</td></tr>'
        )
    tx = pos(total, lo, hi)
    z0 = pos(0.0, lo, hi)
    rows.append(
        f'<tr class="total"><th scope="row"><span class="fname">Total</span><span class="sub">Mean excess return</span></th>'
        f'<td class="plot-cell"><svg class="bar-svg" aria-hidden="true"><title>Total: {pct(total)} a year</title>{grid_lines(ticks, lo, hi)}'
        f'<line class="total-line" x1="{min(z0, tx)}%" x2="{max(z0, tx)}%" y1="50%" y2="50%"/>'
        f'<line class="total-cap" x1="{tx}%" x2="{tx}%" y1="22%" y2="78%"/></svg></td>'
        f'<td class="num strong">{pct(total)}</td><td class="num"></td></tr>'
    )
    mkt = rc["factors"]["Mkt-RF"]
    reading = (
        f"Of the {pct(total, 2, False)} average excess return a year, market exposure accounts for {pct(mkt, 2, False)}. "
        f"Alpha adds {pct(rc['alpha'])}{', but it is not significant' if g['alpha_tag'] != 'reliable' else ''}."
    )
    memo = "".join(f"<li>{e(m)}</li>" for m in rc["memo"])
    legend = (
        '<ul class="legend" aria-label="Legend">'
        '<li><svg class="sw" aria-hidden="true"><rect class="pos" width="14" height="10" rx="2"/></svg>Adds</li>'
        '<li><svg class="sw" aria-hidden="true"><rect class="neg" width="14" height="10" rx="2"/></svg>Subtracts</li>'
        '<li><svg class="sw" aria-hidden="true"><rect class="pos faded" x="0.5" y="0.5" width="13" height="9" rx="2"/></svg>Faded: not significant</li>'
        '<li><svg class="sw" aria-hidden="true"><rect class="hatch" width="14" height="10" rx="2"/></svg>Residual</li>'
        '<li><svg class="sw" aria-hidden="true"><line class="total-line" x1="0" x2="13" y1="5" y2="5"/><line class="total-cap" x1="13" x2="13" y1="0" y2="10"/></svg>Total</li>'
        "</ul>"
    )
    return f"""
<section class="panel" id="returns" aria-labelledby="ret-t">
  {panel_head(*head_args, legend)}
  <p class="reading">{e(reading)}</p>
  <table class="bars cols-2">
    <caption class="vh">Return contribution per factor, alpha and residual, percent a year, with the total</caption>
    <thead><tr><th scope="col">Component</th><th scope="col" class="plot-h"><span class="vh">Chart</span></th>
      <th scope="col" class="num">% a year</th><th scope="col" class="num"><span class="long">Significant</span><span class="short" aria-hidden="true">Sig.</span></th></tr></thead>
    <tbody>{''.join(rows)}</tbody>
    <tfoot>{axis_row(ticks, lo, hi, lambda t: pct(t, 0 if abs(t * 100 - round(t * 100)) < 1e-9 else 1) if t else "0%", 2)}</tfoot>
  </table>
  <div class="memo"><h3>Not in the sum</h3><ul>{memo}</ul></div>
  {footnote("In-sample, descriptive, not predictive. The rows add up exactly to the total.", "Each factor's share is its full-sample beta times the factor's average return, times 252. Arithmetic, not compounded.")}
</section>"""


def risk_panel(r: dict) -> str:
    rk = r["risk_contribution"]
    head_args = ("risk", "Where the risk comes from", "What share of the day-to-day variance does each factor drive?")
    if rk["status"] != "ok":
        return f'<section class="panel" id="risk" aria-labelledby="risk-t">{panel_head(*head_args)}{empty_state(rk["reason"], "Widen the date range and run the report again.")}</section>'
    det = {d["name"]: d for d in rk["details"]}
    shares = {**rk["factors"], "Idiosyncratic": rk["idiosyncratic"]}
    lo, hi, ticks = nice_domain(min(0.0, min(shares.values())), max(1.0, max(shares.values())), 4)
    rows = []
    for n in rk["order"]:
        v = shares[n]
        if n == "Idiosyncratic":
            cls, plain, extra = "hatch", "Stock-specific", '<td class="num">&#8211;</td><td class="num">&#8211;</td><td class="num">&#8211;</td>'
            tip = f"Idiosyncratic: {pct(v, 2, False)} of variance"
            mob = "Not explained by the factors"
        else:
            dd = det[n]
            cls, plain = f"cat c{SLOT[n]}", PLAIN[n]
            extra = (
                f'<td class="num">{sgn(dd["beta"])}</td><td class="num">{pct(dd["sigma_annual"], 1, False)}</td>'
                f'<td class="num">{sgn(dd["rho_sys"], 2)}</td>'
            )
            tip = (
                f"{n}: {pct(v, 2, False)} of variance = exposure {sgn(dd['beta'])} x volatility "
                f"{pct(dd['sigma_annual'], 1, False)} x correlation {sgn(dd['rho_sys'], 2)} with the factor-driven return"
            )
            mob = f"Beta {sgn(dd['beta'])}, vol {pct(dd['sigma_annual'], 1, False)}, corr {sgn(dd['rho_sys'], 2)}"
        rows.append(
            f'<tr class="{"idio" if n == "Idiosyncratic" else ""}"><th scope="row"><span class="fname">'
            + (f'<svg class="key" aria-hidden="true"><rect class="cat c{SLOT[n]}" width="8" height="8" rx="1"/></svg>' if n in SLOT else
               '<svg class="key" aria-hidden="true"><rect class="hatch" width="8" height="8" rx="1"/></svg>')
            + f'{e(n)}</span><span class="sub">{plain}</span><span class="sub mob">{e(mob)}</span></th>'
            f'<td class="plot-cell"><svg class="bar-svg" aria-hidden="true"><title>{e(tip)}</title>{grid_lines(ticks, lo, hi)}{bar(v, lo, hi, cls)}</svg></td>'
            f'<td class="num strong">{pct(v, 2, v < 0)}</td>{extra}</tr>'
        )
    sent = " ".join(e(s) for s in rk["sentences"])
    top = rk["order"][0]
    reading = (
        f"{e(top)} drives {pct(shares[top], 1, False)} of the variance; stock-specific risk is "
        f"{pct(rk['idiosyncratic'], 1, False)}. Total volatility is {pct(rk['total_vol_annual'], 1, False)} a year. {sent}"
    )
    return f"""
<section class="panel" id="risk" aria-labelledby="risk-t">
  {panel_head(*head_args)}
  <p class="reading">{reading}</p>
  <table class="bars cols-4 risk">
    <caption class="vh">Share of variance per factor and stock-specific, with exposure, factor volatility and correlation</caption>
    <thead><tr><th scope="col">Source</th><th scope="col" class="plot-h"><span class="vh">Chart</span></th>
      <th scope="col" class="num">Share</th><th scope="col" class="num">Beta</th><th scope="col" class="num">Factor vol</th>
      <th scope="col" class="num">Corr.</th></tr></thead>
    <tbody>{''.join(rows)}</tbody>
    <tfoot>{axis_row(ticks, lo, hi, lambda t: pct(t, 0, False) if t >= 0 else pct(t, 0), 4)}</tfoot>
  </table>
  {footnote("In-sample, descriptive, not predictive. Shares add to 100% and can be negative when a factor offsets the others.", "Euler decomposition of variance: share = beta &#215; factor vol &#215; correlation with the factor-driven return, divided by total vol.")}
</section>"""


def _quantile(xs: list[float], q: float) -> float:
    s = sorted(xs)
    k = (len(s) - 1) * q
    f = math.floor(k)
    c = min(f + 1, len(s) - 1)
    return s[f] + (s[c] - s[f]) * (k - f)


def rolling_block(w: dict, avg: dict | None) -> str:
    dates = w["dates"]
    n = len(dates) - 1
    z = w["ci_z"]
    series = {}
    for name in FACTORS:
        b, s = w["betas"].get(name, []), w["se"].get(name, [])
        pts = [(i, b[i], s[i]) for i in range(len(b)) if b[i] is not None and s[i] is not None]
        series[name] = pts
    spans = []
    for pts in series.values():
        if pts:
            spans.append(max(v + z * s for _, v, s in pts) - min(v - z * s for _, v, s in pts))
    span = max(spans) * 1.08 if spans else 1.0
    i0 = min((pts[0][0] for pts in series.values() if pts), default=0)
    xt = [t for t in date_ticks(dates) if t[0] >= i0]
    rows = []
    for name in FACTORS:
        pts = series[name]
        if not pts:
            continue
        mid = (max(v + z * s for _, v, s in pts) + min(v - z * s for _, v, s in pts)) / 2
        lo, hi = mid - span / 2, mid + span / 2
        X = lambda i: (i - i0) / max(n - i0, 1) * 1000  # noqa: E731
        Y = lambda v: 100 - (v - lo) / (hi - lo) * 100  # noqa: E731
        step = 2 if len(pts) > 400 else 1
        sp = pts[::step] + ([pts[-1]] if (len(pts) - 1) % step else [])
        up = [(X(i), Y(v + z * s)) for i, v, s in sp]
        dn = [(X(i), Y(v - z * s)) for i, v, s in sp][::-1]
        band = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in up + dn) + "Z"
        line = path_xy([X(i) for i, _, _ in sp], [Y(v) for _, v, _ in sp])
        zero = f'<line class="zero" x1="0" x2="1000" y1="{Y(0):.2f}" y2="{Y(0):.2f}"/>' if lo < 0 < hi else ""
        vgrid = "".join(f'<line class="grid" x1="{X(i):.1f}" x2="{X(i):.1f}" y1="0" y2="100"/>' for i, _, major in xt if major)
        svg = (
            f'<svg class="line-svg" viewBox="0 0 1000 100" preserveAspectRatio="none" aria-hidden="true">{vgrid}{zero}'
            f'<path class="band c{SLOT[name]}" d="{band}"/><path class="rline c{SLOT[name]}" d="{line}"/></svg>'
        )
        # y labels: top and bottom of the row's range, plus zero when visible
        yl = [(hi, "top"), (lo, "bot")] + ([(0.0, "mid")] if lo < 0 < hi and min(abs(hi), abs(lo)) > span * 0.22 else [])
        ylab = "".join(f'<span class="yl {c}" style="top:{Y(t):.2f}%">{sgn(t, 2) if abs(t) > 1e-9 else "0"}</span>' for t, c in yl)
        vals = [v for _, v, _ in pts]
        latest = vals[-1]
        a = (avg or {}).get(name)
        if a and a.get("mean") is not None:
            mean, p10, p90 = a["mean"], a["p10"], a["p90"]
        else:
            mean, p10, p90 = sum(vals) / len(vals), _quantile(vals, 0.1), _quantile(vals, 0.9)
        if a and a.get("sd") is not None:
            sd, vmin, vmax, shp = a["sd"], a["min"], a["max"], a["share_positive"]
        else:
            sd = math.sqrt(sum((v - mean) ** 2 for v in vals) / max(len(vals) - 1, 1))
            vmin, vmax, shp = min(vals), max(vals), sum(1 for v in vals if v > 0) / len(vals)
        tip = f"Spread {num(sd)}, lowest {sgn(vmin)}, highest {sgn(vmax)}, above zero in {shp * 100:.0f}% of windows"
        rows.append(
            f'<tr><th scope="row"><span class="fname"><svg class="key" aria-hidden="true"><rect class="cat c{SLOT[name]}" width="8" height="8" rx="1"/></svg>{e(name)}</span>'
            f'<span class="sub">{PLAIN[name]}</span></th>'
            f'<td class="plot-cell"><div class="plot mini">{svg}<div class="ylabels" aria-hidden="true">{ylab}</div></div></td>'
            f'<td class="num strong">{sgn(latest)}</td><td class="num">{sgn(mean)}</td>'
            f'<td class="num range" title="{e(tip)}">{sgn(p10, 2)} to {sgn(p90, 2)}</td></tr>'
        )
    xlab = "".join(
        f'<span class="xl{" minor" if not major else ""} {edge((i - i0) / max(n - i0, 1) * 100)}" style="left:{(i - i0) / max(n - i0, 1) * 100:.2f}%">{lab}</span>' for i, lab, major in xt
    )
    win = w["window"]
    return f"""
<div class="win w-{win}">
  <p class="print-only win-cap">{win}-day window</p>
  <table class="bars cols-3 rolling">
    <caption class="vh">Rolling {win}-day betas per factor with pointwise 95% band; latest, average and middle 80% of the estimates</caption>
    <thead><tr><th scope="col">Factor</th><th scope="col" class="plot-h"><span class="vh">Chart</span></th>
      <th scope="col" class="num">Latest</th><th scope="col" class="num">Average</th><th scope="col" class="num">Middle 80%</th></tr></thead>
    <tbody>{''.join(rows)}</tbody>
    <tfoot><tr class="axis-row" aria-hidden="true"><td></td><td class="axis time">{xlab}</td><td colspan="3"></td></tr></tfoot>
  </table>
  <p class="foot">Each point uses the previous {win} trading days, so the chart starts at the first full window, {d_long(dates[i0])}. Latest is stamped {d_long(dates[-1])}.</p>
</div>"""


def rolling_panel(r: dict) -> str:
    wins = sorted(r["rolling"], key=lambda w: w["window"])
    ab = r["average_beta"]
    primary = ab.get("window", 252)
    head_args = ("roll", "Exposure over time", "Have the exposures been stable, or did they drift?")
    ok = [w for w in wins if w["status"] == "ok"]
    if not ok:
        reason = wins[0]["reason"] if wins else "No rolling windows were computed."
        return f'<section class="panel" id="rolling" aria-labelledby="roll-t">{panel_head(*head_args)}{empty_state(reason, "Rolling betas need more trading days than the window length. Choose an earlier start date.")}</section>'
    avg = {f["name"]: f for f in ab["factors"]} if ab["status"] == "ok" else {}
    radios, labels, blocks, css_rules = [], [], [], []
    for w in wins:
        k = w["window"]
        checked = " checked" if k == primary else ""
        radios.append(f'<input class="vh win-radio" type="radio" name="window" id="win-{k}" value="{k}"{checked}>')
        labels.append(f'<label for="win-{k}">{k} days</label>')
        if w["status"] == "ok":
            blocks.append(rolling_block(w, avg if k == primary else None))
        else:
            blocks.append(f'<div class="win w-{k}">{empty_state(w["reason"], "Choose an earlier start date or the shorter window.")}</div>')
    toggle = f'<div class="seg" role="group" aria-label="Rolling window length"><span class="seg-lab" aria-hidden="true">Window</span><span class="seg-btns">{"".join(labels)}</span></div>'
    return f"""
{''.join(radios)}
<section class="panel" id="rolling" aria-labelledby="roll-t">
  {panel_head(*head_args, toggle)}
  {''.join(blocks)}
  {footnote("In-sample, descriptive, not predictive. The band is a pointwise 95% interval.", "About 1 point in 20 falls outside the band even when the true beta is constant. Overlapping windows share most of their data. Every row uses the same vertical span, centred on its own values, so wiggles compare across factors.")}
</section>"""


def data_section(r: dict) -> str:
    d, g = r["data"], r["regression"]
    rows = [
        ("Requested", f"{d_long(d['requested_start'])} to {d_long(d['requested_end'])}"),
        ("Analysed", f"{d_long(d['actual_start'])} to {d_long(d['actual_end'])}, {d['n_obs']:,} trading days"),
        ("Excluded inside the range", f"{d['n_excluded']}" + (" (" + ", ".join(f"{v} {k.replace('_', ' ')}" for k, v in d["excluded_by_reason"].items()) + ")" if d["excluded_by_reason"] else "")),
        ("Dropped after factor data", f"{d['dropped_price_dates_after_factors']} price days"),
        ("Dropped before factor data", f"{d['dropped_price_dates_before_factors']} price days"),
        ("Factor data ends", f"{d_long(d['factors_last_date'])}, {d['factors_days_behind']} days before the report"),
        ("Factor file downloaded", d["factors_downloaded_at"].replace("T", " ").replace("Z", " UTC") if d["factors_downloaded_at"] else "Injected, not downloaded"),
        ("Prices", d["price_source"]),
        ("Factors", d["factors_source_url"]),
    ]
    dl = "".join(f"<div><dt>{e(a)}</dt><dd>{e(b)}</dd></div>" for a, b in rows)
    sev_glyph = {
        "info": '<svg class="glyph" aria-hidden="true" viewBox="0 0 16 16"><circle cx="8" cy="8" r="6.5"/><path class="cut" d="M8 7v4.5M8 4.6v.9"/></svg>',
        "warning": '<svg class="glyph" aria-hidden="true" viewBox="0 0 16 16"><path d="M8 1.5 15 14.5H1z"/><path class="cut" d="M8 6v4M8 11.6v1"/></svg>',
        "error": '<svg class="glyph" aria-hidden="true" viewBox="0 0 16 16"><rect x="2" y="2" width="12" height="12" rx="1"/><path class="cut" d="M5.5 5.5l5 5M10.5 5.5l-5 5"/></svg>',
    }
    finds = "".join(
        f'<li class="sev-{f["severity"]}">{sev_glyph[f["severity"]]}<span class="sev">{f["severity"].capitalize()}</span>'
        f'<span class="msg">{e(f["message"])}'
        + (f' <span class="dates">({", ".join(d_long(x) for x in f["dates"])})</span>' if f["dates"] else "")
        + "</span></li>"
        for f in d["audit_findings"]
    ) or '<li class="sev-none"><span class="msg">No findings. Prices passed every check.</span></li>'
    notes = "".join(f"<li>{e(n)}</li>" for n in r["notes"])
    labels = "".join(f"<li>{e(v)}</li>" for k, v in r["label_text"].items() if k in ("L-VINTAGE",))
    reg = regression_table(g)
    return f"""
<section class="panel data" id="data" aria-labelledby="data-t">
  {panel_head("data", "Data and audit", "What went into these numbers, and what was left out?")}
  <div class="data-grid">
    <div><h3>Coverage</h3><dl class="facts">{dl}</dl></div>
    <div>
      <h3>Audit findings</h3><ul class="findings">{finds}</ul>
      <h3>Caveats</h3><ul class="notes">{notes}{labels}</ul>
    </div>
  </div>
  {reg}
  {footnote("Audit findings are reported, never acted on: no price is changed or removed because of them.")}
</section>"""


def regression_table(g: dict) -> str:
    if g["status"] != "ok":
        return ""
    vif = g["vif"]
    rows = [
        f'<tr class="{"ns" if g["alpha_tag"] != "reliable" else ""}"><th scope="row">Alpha, a year</th><td class="num">{pct(g["alpha_annual"])}</td>'
        f'<td class="num">{pct(g["alpha_se_annual"], 2, False)}</td><td class="num">{tstat(g["alpha_z"])}</td><td class="num">{pval(g["alpha_p"])}</td>'
        f'<td class="num">single test</td><td class="num">{pct(g["alpha_ci_low_annual"])} to {pct(g["alpha_ci_high_annual"])}</td><td class="num">&#8211;</td>'
        f'<td class="num sig">{"No" if g["alpha_tag"] != "reliable" else "Yes"}</td></tr>'
    ]
    for f in g["factors"]:
        ns = f["tag"] != "reliable"
        rows.append(
            f'<tr class="{"ns" if ns else ""}"><th scope="row">{e(f["name"])}</th><td class="num">{sgn(f["beta"])}</td><td class="num">{num(f["se"], 4)}</td>'
            f'<td class="num">{tstat(f["z"])}</td><td class="num">{pval(f["p"])}</td><td class="num">{pval(f["p_adj_bh"])}</td>'
            f'<td class="num">{sgn(f["ci_low"])} to {sgn(f["ci_high"])}</td><td class="num">{vif.get(f["name"], 0):.2f}</td>'
            f'<td class="num sig">{"No" if ns else "Yes"}</td></tr>'
        )
    return f"""
  <h3>Regression detail</h3>
  <div class="scroll-x" tabindex="0" role="region" aria-label="Regression detail table, scrolls sideways">
  <table class="reg">
    <thead><tr><th scope="col">Term</th><th scope="col" class="num">Estimate</th><th scope="col" class="num">Std. error</th><th scope="col" class="num">t</th>
    <th scope="col" class="num">p</th><th scope="col" class="num">p, adjusted</th><th scope="col" class="num">95% interval</th><th scope="col" class="num">VIF</th><th scope="col" class="num"><span class="long">Significant</span><span class="short" aria-hidden="true">Sig.</span></th></tr></thead>
    <tbody>{''.join(rows)}</tbody>
  </table></div>
  <p class="foot">R&#178; {g['r2']:.4f}, adjusted {g['adj_r2']:.4f}. Residual volatility {pct(g['sigma_e_annual'], 2, False)} a year. Newey&#8211;West lags {g['hac_lags']}. Condition number of the factor correlation matrix {g['condition_number']:.2f}.</p>"""


# ----------------------------------------------------------------------------- page
def font_faces() -> str:
    def b64(name: str) -> str:
        return base64.b64encode((FONTS / name).read_bytes()).decode("ascii")

    return (
        "@font-face{font-family:'Instrument Sans';font-style:normal;font-weight:400 700;font-display:block;"
        f"src:url(data:font/woff2;base64,{b64('instrument-sans.woff2')}) format('woff2')}}\n"
        "@font-face{font-family:'STIX Two Text';font-style:normal;font-weight:400;font-display:block;"
        f"src:url(data:font/woff2;base64,{b64('stix-r.woff2')}) format('woff2')}}\n"
        "@font-face{font-family:'STIX Two Text';font-style:italic;font-weight:400;font-display:block;"
        "unicode-range:U+0041-005A,U+0061-007A;"
        f"src:url(data:font/woff2;base64,{b64('stix-il.woff2')}) format('woff2')}}\n"
        "@font-face{font-family:'STIX Two Text';font-style:italic;font-weight:400;font-display:block;"
        "unicode-range:U+03B1,U+03B2,U+03B5,U+03C1,U+03C3;"
        f"src:url(data:font/woff2;base64,{b64('stix-ig.woff2')}) format('woff2')}}\n"
    )


CSS = (HERE / "report.css").read_text(encoding="utf-8") if (HERE / "report.css").exists() else ""


def controls_bar(r: dict) -> str:
    """Dashboard-only controls (design mock). The static report shows range_line() instead."""
    d = r["data"]
    n = d["n_obs"]
    presets = [("YTD", 1), ("1Y", 252), ("3Y", 756), ("5Y", 1260), ("Full history", 0)]
    chips, off = [], []
    for lab, need in presets:
        dis = need > n
        if dis:
            off.append(lab)
        chips.append(
            f'<label class="chip-opt{" off" if dis else ""}"><input type="radio" name="range" value="{lab}"'
            f'{" disabled" if dis else ""}{" checked" if lab == "Full history" else ""}><span>{lab}</span></label>'
        )
    why = (
        f'<p class="ctl-why" id="ctl-why">{" and ".join(off)} need more trading days than {e(r["ticker"])} has in this '
        f"sample ({n:,}). Choose a shorter range.</p>"
        if off
        else ""
    )
    return f"""
<section class="controls" aria-label="Report controls">
  <form class="ctl-row" onsubmit="return false">
    <div class="ctl-search"><label class="vh" for="tk">Ticker</label>
      <input id="tk" type="text" value="{e(r['ticker'])}" autocomplete="off" spellcheck="false" aria-describedby="ctl-why">
      <button type="button" class="btn">Factor it</button></div>
    <fieldset class="ctl-range"><legend class="vh">Date range</legend>
      <span class="chips">{''.join(chips)}</span>
      <span class="ctl-custom"><label>From <input type="date" value="{d['actual_start']}" max="{d['factors_last_date']}"></label>
      <label>To <input type="date" value="{d['actual_end']}" max="{d['factors_last_date']}"></label></span>
    </fieldset>
  </form>
  <p class="ctl-label"><b>{e(range_line(r))}</b> Factor data ends {d_long(d['factors_last_date'])}, so later dates cannot be chosen.</p>
  {why}
</section>"""


def page(r: dict, controls: bool = False) -> str:
    hatch_defs = (
        '<svg class="defs" width="0" height="0" aria-hidden="true" focusable="false"><defs>'
        '<pattern id="hatch" patternUnits="userSpaceOnUse" width="5" height="5" patternTransform="rotate(45)">'
        '<rect class="hatch-bg" width="5" height="5"/><rect class="hatch-ink" width="1.6" height="5"/></pattern>'
        "</defs></svg>"
    )
    body = "\n".join(
        [
            hatch_defs,
            '<main class="report">',
            controls_bar(r) if controls else "",
            header(r, controls),
            equation(r),
            kpis(r),
            price_panel(r),
            exposures_panel(r),
            return_panel(r),
            risk_panel(r),
            rolling_panel(r),
            data_section(r),
            f'<footer class="colophon"><p>factordesk report, schema v{e(r["schema_version"])}, generated {gen_stamp(r)}. '
            "Descriptive statistics on past data; nothing here is a forecast or advice.</p></footer>",
            "</main>",
        ]
    )
    body = add_roles(body)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light dark">
<title>{e(r['ticker'])} factor profile</title>
<style>
{font_faces()}
{CSS}
</style>
</head>
<body>
{body}
</body>
</html>
"""


def gen_stamp(r: dict) -> str:
    g = datetime.fromisoformat(r["generated_at"].replace("Z", "+00:00"))
    return f"{g.day} {g.strftime('%b %Y, %H:%M')} UTC"


def add_roles(body: str) -> str:
    """Explicit table roles: narrow screens restyle rows as grids, which can drop native semantics."""
    def fix(m: re.Match[str]) -> str:
        t = m.group(0)
        t = t.replace('<table class="bars', '<table role="table" class="bars')
        t = re.sub(r"<tr(?=[ >])", '<tr role="row"', t)
        t = t.replace('<th scope="row"', '<th role="rowheader" scope="row"').replace('<th scope="col"', '<th role="columnheader" scope="col"')
        t = re.sub(r"<td(?=[ >])", '<td role="cell"', t)
        t = re.sub(r"<(thead|tbody|tfoot)>", lambda g: f'<{g.group(1)} role="rowgroup">', t)
        return t
    return re.sub(r'<table class="bars.*?</table>', fix, body, flags=re.S)


def make_empty(r: dict) -> dict:
    """Mutate a copy of the fixture so every statistic reports insufficient data."""
    x = copy.deepcopy(r)
    msg = "Not enough data: the sample has 41 trading days and this needs at least 504."
    for key in ("regression", "return_contribution", "risk_contribution", "average_beta"):
        x[key]["status"] = "insufficient_data"
        x[key]["reason"] = msg
    for w in x["rolling"]:
        w["status"] = "insufficient_data"
        w["reason"] = f"Not enough data: a {w['window']}-day window needs at least {w['window']} trading days; the sample has 41."
    return x


def main() -> None:
    r = json.loads(FIXTURE.read_text(encoding="utf-8"))
    empty = "--empty" in sys.argv
    controls = "--controls" in sys.argv
    if empty:
        r = make_empty(r)
    out = HERE / ("report-empty.html" if empty else "report-controls.html" if controls else "report.html")
    out.write_text(page(r, controls), encoding="utf-8", newline="\n")
    print(f"wrote {out} ({out.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
