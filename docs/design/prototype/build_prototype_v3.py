"""Generator for the dashboard v2 visual target (rev 3 prototype).

Reads the mock fixture (JSON only) and writes one self-contained HTML page next to this file:
fixed sidebar with controls and section navigation, outcome-first summary (verdict band,
historical performance, factor cards), then the evidence panels. The switches, segmented
controls and the mobile drawer work without JavaScript (CSS :has and native inputs).

Standard library only. Formatting and scale helpers are imported from the rev 2 generator,
which stays unchanged. Nothing outside docs/design/prototype/ is written.

    python docs/design/prototype/build_prototype_v3.py                 # report-v3.html
    python docs/design/prototype/build_prototype_v3.py --empty         # report-v3-empty.html
    python docs/design/prototype/build_prototype_v3.py --on dark,stats --out PATH
        (--on pre-checks inputs for screenshots: dark, stats, menu, win126)
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

from build_prototype import date_ticks as _date_ticks
from build_prototype import (  # rev 2 helpers, unchanged
    FACTORS,
    MINUS,
    PLAIN,
    SLOT,
    TILT,
    WARN_PLAIN,
    _quantile,
    d_long,
    edge,
    make_empty,
    nice_domain,
    num,
    path_xy,
    pct,
    pos,
    pval,
    sgn,
    tstat,
)

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
FIXTURE = ROOT / "backend" / "factordesk" / "tests" / "fixtures" / "mock_report.json"
FONTS = HERE / "fonts"
CSS = (HERE / "report-v3.css").read_text(encoding="utf-8")

e = html.escape

# ----------------------------------------------------------------------------- demo data, keyed by ticker
# The report schema has no security name yet (plan: data.security). Demo values only.
SECURITY = {
    "SPY": {"name": "SPDR S&P 500 ETF Trust", "exchange": "NYSE Arca", "currency": "USD"},
    "ZM": {"name": "Zoom Communications Inc.", "exchange": "Nasdaq", "currency": "USD"},
}
CURRENCY_PLAIN = {"USD": "US dollars"}

# Historical performance over the analysed range (owner addition). Keyed, not computed.
PERFORMANCE = {
    "ZM": {"ret": 0.064, "vol": 0.521, "sharpe": 0.09, "mdd": -0.832,
           "peak": "2021-10-18", "trough": "2022-12-30", "recovered": None, "years": 1254 / 252},
    "SPY": {"ret": 0.128, "vol": 0.176, "sharpe": 0.58, "mdd": -0.245,
            "peak": "2025-07-14", "trough": "2026-06-18", "recovered": "2026-08-03", "years": 559 / 252},
}

# World beta against the ACWI ETF (owner addition). Keyed, not computed.
WORLD = {
    "ZM": {"acwi": (1.31, 1.05, 1.57), "acwi_r2": 0.34, "us": (1.42, 1.12, 1.72), "us_r2": 0.38, "days": 1254},
    "SPY": {"acwi": (1.05, 1.01, 1.09), "acwi_r2": 0.91, "us": (1.00, 0.99, 1.01), "us_r2": 0.99, "days": 559},
}

# Notice band: one short plain line per warning, so two warnings fit in two lines.
NOTICE_PLAIN = {
    "residual_reversal": "Daily prices partly reverse the next day, so R\u00b2 is probably understated.",
    "short_history": "The history is short, so the betas rest on a small sample.",
    "audit_errors": "The price audit found errors; see Data and audit before reading the numbers.",
}

PILL = {
    "SMB": ("Small companies", "Large companies"),
    "HML": ("Value stocks", "Growth stocks"),
    "RMW": ("Profitable firms", "Weakly profitable firms"),
    "CMA": ("Conservative investors", "Aggressive investors"),
}
NO_TILT = {
    "SMB": "No clear lean toward small or large companies.",
    "HML": "No clear lean toward value or growth stocks.",
    "RMW": "No clear lean toward more or less profitable firms.",
    "CMA": "No clear lean toward conservative or aggressive investors.",
}


# ----------------------------------------------------------------------------- icons (inline, stroke)
ICON = {
    "search": '<circle cx="8.5" cy="8.5" r="5.5"/><path d="m13 13 4.5 4.5"/>',
    "refresh": '<path d="M16 9.5A6.5 6.5 0 1 1 13.6 4.5"/><path d="M16 3v4h-4"/>',
    "download": '<path d="M10 3v10M6 9.5l4 4 4-4"/><path d="M3.5 15.5v1h13v-1"/>',
    "menu": '<path d="M3 5.5h14M3 10h14M3 14.5h14"/>',
    "close": '<path d="m5 5 10 10M15 5 5 15"/>',
    "warn": '<path d="M10 2.8 18 16.8H2z"/><path d="M10 8v4M10 14.4v.3"/>',
    # section icons for the rail
    "summary": '<path d="M3 15a7 7 0 0 1 14 0"/><path d="m10 15 3.5-4.5"/>',
    "drivers": '<path d="M3 6h14M3 14h14"/><circle cx="7.5" cy="6" r="2"/><circle cx="12.5" cy="14" r="2"/>',
    "world": '<circle cx="10" cy="10" r="7"/><path d="M3 10h14M10 3c2.4 2.2 2.4 11.8 0 14M10 3c-2.4 2.2-2.4 11.8 0 14"/>',
    "price": '<path d="M3 16.5h14"/><path d="m3.5 12.5 4-4 3 3 6-6"/>',
    "performance": '<path d="M3 4.5h14"/><path d="m3.5 4.5 4 6.5 3-3 6 7"/>',
    "exposures": '<path d="M4 5h8M4 10h12M4 15h5"/>',
    "returns": '<path d="M10 2.5v15"/><path d="M13.5 6H8.3a2.2 2.2 0 0 0 0 4.4h3.4a2.2 2.2 0 0 1 0 4.4H6"/>',
    "risk": '<path d="M2.5 10c1.8-4.5 3.7-4.5 5.5 0s3.7 4.5 5.5 0c.9-2.2 2.2-3.3 4-2.5"/>',
    "rolling": '<circle cx="10" cy="10" r="7"/><path d="M10 6v4l3 2"/>',
    "residual": '<path d="M10 3v8M6 7h8M6 15.5h8"/>',
    "kalman": '<path d="M2.5 10h3.5l2-5 4 10 2-5h3.5"/>',
    "shrunk": '<circle cx="10" cy="10" r="7"/><circle cx="10" cy="10" r="3"/>',
    "data": '<ellipse cx="10" cy="5" rx="6" ry="2.5"/><path d="M4 5v10c0 1.4 2.7 2.5 6 2.5s6-1.1 6-2.5V5M4 10c0 1.4 2.7 2.5 6 2.5s6-1.1 6-2.5"/>',
    "detail": '<rect x="3" y="4" width="14" height="12" rx="1.5"/><path d="M3 8h14M8.5 8v8"/>',
}


def icon(name: str, label: str = "") -> str:
    aria = f'role="img" aria-label="{e(label)}"' if label else 'aria-hidden="true"'
    return f'<svg class="icon" viewBox="0 0 20 20" {aria}>{ICON[name]}</svg>'


MARK = (
    '<svg viewBox="0 0 28 28" aria-hidden="true"><rect class="m-bg" width="28" height="28" rx="7"/>'
    '<rect class="m-bar" x="7" y="13" width="3" height="8" rx="1.5"/><rect class="m-bar" x="12.5" y="7" width="3" height="14" rx="1.5"/>'
    '<rect class="m-bar" x="18" y="10.5" width="3" height="10.5" rx="1.5"/></svg>'
)


# ----------------------------------------------------------------------------- small helpers
def date_ticks(dates: list[str]) -> list[tuple[int, str, bool]]:
    """Quarterly ticks; only January and the first tick carry the year, so labels never crowd."""
    out = _date_ticks(dates)
    return [(i, lab if (major or k == 0) else lab.split()[0], major) for k, (i, lab, major) in enumerate(out)]


def time_labels(xt: list[tuple[int, str, bool]], xpct, gap: float = 16.0) -> str:
    """HTML labels for a time axis; January ticks win, a label closer than ``gap`` % to a kept one is dropped."""
    kept: list[tuple[float, str, bool]] = []
    for i, lab, major in sorted(xt, key=lambda t: not t[2]):
        x = xpct(i)
        if all(abs(x - k[0]) >= gap for k in kept):
            kept.append((x, lab, major))
    return "".join(
        f'<span class="xl {edge(x)}" style="left:{x:.2f}%">{lab}</span>' for x, lab, _ in sorted(kept)
    )


def plural(n: int, one: str, many: str | None = None) -> str:
    return f"{n:,} {one if n == 1 else (many or one + 's')}"


def and_list(xs: list[str], last: str = "and") -> str:
    if len(xs) <= 1:
        return "".join(xs)
    return ", ".join(xs[:-1]) + f" {last} " + xs[-1]


def p1(x: float, signed: bool = False) -> str:
    """Percent with one decimal; signed adds + or a true minus."""
    return pct(x, 1, signed)


def share(x: float) -> str:
    """A share of 100%, one decimal, more when it would print as 100.0% or 0.0%."""
    v = x * 100
    d = 2 if (v > 99.95 or 0 < v < 0.05) else 1
    return f"{v:.{d}f}%"


def stat(text: str, tag: str = "span") -> str:
    return f'<{tag} class="stat">{text}</{tag}>'


def how(text: str, more: str = "", label: str = "How this is computed") -> str:
    if not more:
        return f'<p class="foot">{text}</p>'
    return (
        f'<div><p class="foot">{text}</p><details class="more"><summary>{label}</summary>'
        f"<p>{more}</p></details></div>"
    )


def empty_state(reason: str, action: str) -> str:
    return f'<div class="empty" role="note"><p class="empty-what">{e(reason)}</p><p class="empty-do">{e(action)}</p></div>'


def sec(sid: str, title: str, outcome: str, main: str, side: str = "", two: bool | str = True, extra: str = "") -> str:
    """two=True: two-up from 1440 px; two="xl": two-up from 1760 px (tables with many number columns)."""
    body = f'<div class="sec-main">{main}</div>' + (f'<div class="sec-side">{side}</div>' if side else "")
    layout = (" two-xl" if two == "xl" else " two") if (two and side) else ""
    return f"""
<section class="sec" id="{sid}" aria-labelledby="{sid}-t">
  <header class="sec-head"><div><h2 id="{sid}-t">{e(title)}</h2><p class="outcome">{outcome}</p></div>{extra}</header>
  <div class="sec-body{layout}">{body}</div>
</section>"""


def sec_empty(sid: str, title: str, reason: str, action: str) -> str:
    return sec(sid, title, "Not enough data for this section.", empty_state(reason, action), two=False)


def grid_lines(ticks: list[float], lo: float, hi: float) -> str:
    return "".join(
        f'<line class="{"zero" if abs(t) < 1e-12 else "grid"}" x1="{pos(t, lo, hi)}%" x2="{pos(t, lo, hi)}%" y1="0" y2="100%"/>'
        for t in ticks
    )


def bar(v: float, lo: float, hi: float, cls: str) -> str:
    a, b = sorted((pos(0.0, lo, hi), pos(v, lo, hi)))
    return f'<rect class="{cls}" x="{a}%" y="31%" width="{max(b - a, 0.0)}%" height="38%" rx="3"/>'


def axis_row(ticks: list[float], lo: float, hi: float, fmt, ncols: int = 0) -> str:
    """Tick labels under the plot column. A label closer than 20% of the width to a kept one is
    dropped (zero always stays). No trailing cells, so hidden statistics columns stay collapsed."""
    kept: list[float] = [t for t in ticks if abs(t) < 1e-12]
    ticks = [t for t in ticks if 4 <= pos(t, lo, hi) <= 96 or abs(t) < 1e-12]
    for t in sorted(ticks, key=abs):
        if all(abs(pos(t, lo, hi) - pos(k, lo, hi)) >= 20 for k in kept):
            kept.append(t)
    labels = "".join(
        f'<span class="{edge(pos(t, lo, hi))}" style="left:{pos(t, lo, hi)}%">{fmt(t)}</span>' for t in sorted(kept)
    )
    return f'<tr class="axis-row" aria-hidden="true"><td></td><td class="axis"><div>{labels}</div></td></tr>'


def tick(t: float) -> str:
    """Signed tick label with the fewest decimals that keep it exact (0.25 stays 0.25)."""
    if abs(t) < 1e-12:
        return "0"
    s = f"{abs(t):.2f}".rstrip("0").rstrip(".")
    return ("+" if t > 0 else MINUS) + s


def sure_word(tag: str | None) -> str:
    return "Clear evidence" if tag == "reliable" else "Could be noise"


def word_cell(reliable: bool) -> str:
    return f'<td class="word {"yes" if reliable else "no"}">{"Clear" if reliable else "Could be noise"}</td>'


# ----------------------------------------------------------------------------- plain-language rules
def market_phrase(b: float) -> str:
    if b < 0:
        return "moves against the market"
    if abs(b - 1) < 0.1:
        return "moves almost one-for-one with the market"
    if b > 1:
        return f"moves more than the market ({num(b, 2)} times as much)"
    return f"moves less than the market ({num(b, 2)} times as much)"


def verdict_sentence(r: dict) -> str:
    """One plain headline from simple rules; never claims more than the statistics support."""
    g, t = r["regression"], r["ticker"]
    if g["status"] != "ok":
        return f"There is not enough data to profile {t} over this range yet."
    fs = {f["name"]: f for f in g["factors"]}
    mk = fs["Mkt-RF"]
    parts = [market_phrase(mk["beta"]) if mk["tag"] == "reliable" else "shows no clear link to the market"]
    tilts = [TILT[n][0 if fs[n]["beta"] > 0 else 1] for n in ("SMB", "HML", "RMW", "CMA")
             if fs[n]["tag"] == "reliable" and abs(fs[n]["beta"]) >= 0.1]
    if tilts:
        parts.append("leans toward " + and_list(tilts))
    a = g["alpha_annual"]
    if r["data"]["audit_status"] == "errors":
        tail = "its return beyond those exposures cannot be judged until the price errors are explained"
    elif g["alpha_tag"] == "reliable" and a > 0:
        tail = f"earns a reliable {p1(a)} a year beyond what those exposures explain"
    elif g["alpha_tag"] == "reliable":
        tail = f"trails what those exposures explain by a reliable {p1(-a)} a year"
    else:
        tail = "shows no reliable return beyond what those exposures explain"
    return f"{t} " + ", ".join(parts) + f", and {tail}."


def card_text(f: dict) -> tuple[str, str, str]:
    """(pill text, pill class, plain sentence) for one factor card."""
    n, b, ok = f["name"], f["beta"], f["tag"] == "reliable"
    if n == "Mkt-RF":
        if not ok:
            return "No clear link", "neu", "No clear link to the US stock market."
        if b < 0:
            return "Against the market", "neg", "Tends to fall when the US stock market rises."
        if abs(b - 1) < 0.1:
            return "With the market", "pos", "Moves almost one-for-one with the US stock market."
        if b > 1:
            return "Amplifies the market", "pos", f"Moves {num(b, 2)} times as much as the US stock market."
        return "Calmer than the market", "pos", f"Moves {num(b, 2)} times as much as the US stock market."
    if not ok:
        return "No clear tilt", "neu", NO_TILT[n]
    side = 0 if b > 0 else 1
    size = "A slight lean" if abs(b) < 0.1 else ("A lean" if abs(b) < 0.3 else "A strong lean")
    return PILL[n][side], ("pos" if b > 0 else "neg"), f"{size} toward {TILT[n][side]}."


# ----------------------------------------------------------------------------- sidebar and top bar
def sidebar(r: dict, nav: list[tuple[str, str, str]]) -> str:
    d = r["data"]
    ranges = [("3Y", False), ("5Y", False), ("Full history", True)]
    seg = "".join(
        f'<label><input type="radio" name="range" value="{k}"{" checked" if c else ""}><span>{k}</span></label>' for k, c in ranges
    )
    items = []
    for sid, label, badge in nav:
        if sid == "residual":
            items.append('<li class="nav-sub" aria-hidden="true">Deeper checks</li>')
        cur = ' aria-current="true"' if sid == "summary" else ""
        b = f'<span class="count"><span aria-hidden="true">{e(badge.split()[0])}</span><span class="vh">, {e(badge)}</span></span>' if badge else ""
        items.append(f'<li><a href="#{sid}"{cur}>{icon(sid)}<span class="lab">{e(label)}</span>{b}</a></li>')
    excl = d["n_excluded"]
    return f"""
<aside class="side" id="sidebar" aria-label="Controls and sections">
  <div class="side-scroll">
    <div class="side-top"><a class="mark" href="#summary">{MARK}<span translate="no">factordesk</span></a>
      <label class="drawer-close" for="nav-open">{icon("close")}<span class="vh">Close menu</span></label></div>
    <form class="side-group" role="search" onsubmit="return false">
      <label class="side-label" for="tk">Ticker</label>
      <div class="search"><input class="field" id="tk" name="ticker" type="text" value="{e(r['ticker'])}" placeholder="e.g. AAPL…" autocomplete="off" autocapitalize="characters" spellcheck="false" translate="no">
        <button class="btn" type="submit">Factor it</button></div>
    </form>
    <fieldset class="side-group">
      <legend class="side-label">Date range</legend>
      <div class="seg fill" role="radiogroup" aria-label="Date range preset">{seg}</div>
      <div class="dates">
        <label>From<input class="field" name="from" type="date" value="{d['actual_start']}" max="{d['factors_last_date']}"></label>
        <label>To<input class="field" name="to" type="date" value="{d['actual_end']}" max="{d['factors_last_date']}"></label>
      </div>
      <p class="side-note" aria-live="polite">Analysed <b>{d_long(d['actual_start'])} to {d_long(d['actual_end'])}</b>, {d['n_obs']:,} trading days{f", {excl} left out" if excl else ""}.</p>
    </fieldset>
    <div class="side-group">
      <p class="side-label">Factor data</p>
      <p class="side-note"><b>Up to {d_long(d['factors_last_date'])}</b>, {d['factors_days_behind']} days old</p>
      <button class="linkbtn" type="button">{icon("refresh")}Check for newer data</button>
    </div>
    <div class="side-group">
      <label class="switch"><input type="checkbox" role="switch" id="sw-stats"><span class="track"><span class="thumb"></span></span>
        <span class="switch-text">Show statistics<span class="sw-hint">Tests, p-values, intervals</span></span></label>
      <label class="switch"><input type="checkbox" role="switch" id="sw-dark"><span class="track"><span class="thumb"></span></span>
        <span class="switch-text">Dark theme</span></label>
    </div>
    <nav class="side-group nav" aria-label="Sections">
      <p class="side-label">Sections</p>
      <ol>{''.join(items)}</ol>
    </nav>
  </div>
  <div class="side-foot"><a class="btn quiet block" href="report-v3.html" download="{e(r['ticker'])}-factor-report.html">{icon("download")}Download report</a></div>
</aside>"""


def topbar(r: dict) -> str:
    d = r["data"]
    return f"""
<header class="topbar">
  <label class="menu-btn" for="nav-open">{icon("menu")}<span class="vh">Open menu</span></label>
  <a class="mark" href="#summary">{MARK}<span translate="no">factordesk</span></a>
  <p class="where"><b>{e(r['ticker'])}</b></p>
</header>
<label class="scrim" for="nav-open" aria-hidden="true"></label>"""


# ----------------------------------------------------------------------------- summary: header, verdict, notice, performance
def header(r: dict) -> str:
    d, ws = r["data"], r["warnings"]
    s = SECURITY.get(r["ticker"], {})
    name = f'<span class="name" translate="no">{e(s["name"])}</span>' if s.get("name") else ""
    listing = ""
    if s.get("exchange"):
        cur = CURRENCY_PLAIN.get(s.get("currency", ""), s.get("currency", ""))
        listing = f'<p class="listing">Listed on {e(s["exchange"])}, priced in {e(cur)}</p>'
    chips = f'<span class="chip"><span class="dot" aria-hidden="true"></span>Factor data to {d_long(d["factors_last_date"])}</span>'
    if ws:
        chips += f'<a class="chip warn" href="#notice">{icon("warn")}{plural(len(ws), "warning")}</a>'
    return f"""
<div class="head">
  <div><h1><span class="ticker" translate="no">{e(r['ticker'])}</span>{name}</h1>{listing}</div>
  <div class="chips">{chips}</div>
</div>"""


def alpha_range_svg(g: dict) -> str:
    lo_ci, hi_ci, a = g["alpha_ci_low_annual"], g["alpha_ci_high_annual"], g["alpha_annual"]
    lo, hi = min(lo_ci, 0.0), max(hi_ci, 0.0)
    x = lambda v: pos(v, lo, hi) * 0.96 + 2  # noqa: E731
    z = x(0.0)
    return (
        '<svg class="range-svg" aria-hidden="true">'
        f'<line class="z" x1="{z}%" x2="{z}%" y1="2" y2="26"/>'
        f'<line class="rng" x1="{x(lo_ci)}%" x2="{x(hi_ci)}%" y1="14" y2="14"/>'
        f'<circle class="pt" cx="{x(a)}%" cy="14" r="6"/></svg>'
        f'<div class="range-labels" aria-hidden="true"><span style="left:{x(lo_ci)}%">{pct(lo_ci, 1)}</span>'
        f'<span class="zl" style="left:{z}%">0</span><span class="end" style="left:{x(hi_ci)}%">{pct(hi_ci, 1)}</span></div>'
        f'<p class="vh">Likely range {pct(lo_ci, 1)} to {pct(hi_ci, 1)} a year.</p>'
    )


def verdict(r: dict) -> str:
    g, d, rk = r["regression"], r["data"], r["risk_contribution"]
    line = verdict_sentence(r)
    basis = (
        f"{d['n_obs']:,} trading days, {d_long(d['actual_start'])} to {d_long(d['actual_end'])}. "
        "Past data, not a forecast."
    ) if g["status"] == "ok" else "The summary appears once the range holds enough trading days."
    if g["status"] != "ok":
        tiles = empty_state(g["reason"], "Widen the date range in the sidebar and run the report again.")
    else:
        a, ns = g["alpha_annual"], g["alpha_tag"] != "reliable"
        errors = d["audit_status"] == "errors"
        a_word = ("Not interpretable" if errors else "Could be noise" if ns else "Clear evidence")
        a_pill = "neu" if (ns or errors) else ("pos" if a > 0 else "neg")
        a_text = (
            "The price audit found errors, so this cannot be judged yet." if errors else
            "Not distinguishable from zero: the likely range includes zero." if ns else
            f"A reliable return {'above' if a > 0 else 'below'} what the factor exposures explain."
        )
        r2 = g["r2"]
        total = rk["total_vol_annual"] if rk["status"] == "ok" else None
        idio = rk["idiosyncratic"] if rk["status"] == "ok" else None
        risk_text = (
            f"Out of {p1(total)} total volatility a year; the factors account for the rest." if total else
            "A year, left unexplained by the factors."
        )
        tiles = f"""
  <div class="tiles">
    <section class="tile" aria-labelledby="t-alpha">
      <h3 id="t-alpha">Beyond its risks</h3>
      <p class="v{' quiet' if ns else ''}">{pct(a)}<small>a year</small></p>
      <span class="pill {a_pill}">{a_word}</span>
      <div class="instrument">{alpha_range_svg(g)}</div>
      <p>{a_text}</p>
      {stat(f"t {tstat(g['alpha_z'])}, p {pval(g['alpha_p'])}, 95% interval {pct(g['alpha_ci_low_annual'])} to {pct(g['alpha_ci_high_annual'])}", "p")}
    </section>
    <section class="tile" aria-labelledby="t-r2">
      <h3 id="t-r2">How much the model explains</h3>
      <p class="v">{share(r2)}<small>of daily moves</small></p>
      <div class="instrument"><div class="meter" role="meter" aria-valuemin="0" aria-valuemax="100" aria-valuenow="{r2 * 100:.1f}" aria-label="Share of daily moves explained"><span style="width:{r2 * 100:.2f}%"></span></div>
        <div class="meter-key"><span>Explained by the factors</span><span>Specific</span></div></div>
      <p><b>{share(r2)}</b> of daily moves; <b>{share(1 - r2)}</b> is specific to the stock.</p>
      {stat(f"R&#178; {r2:.4f}, adjusted {g['adj_r2']:.4f}", "p")}
    </section>
    <section class="tile" aria-labelledby="t-risk">
      <h3 id="t-risk">Stock-specific risk</h3>
      <p class="v">{p1(g['sigma_e_annual'])}<small>a year</small></p>
      <div class="instrument"><div class="meter idio" role="meter" aria-valuemin="0" aria-valuemax="100" aria-valuenow="{(idio or 0) * 100:.1f}" aria-label="Stock-specific share of variance"><span style="width:{max((idio or 0) * 100, 1.2):.2f}%"></span></div>
        <div class="meter-key"><span>{share(idio) if idio is not None else ''} of the variance</span><span>Total {p1(total) if total else ''}</span></div></div>
      <p>{risk_text}</p>
      {stat(f"Residual volatility {pct(g['sigma_e_annual'], 2, False)} a year; idiosyncratic share {share(idio) if idio is not None else '&#8211;'} of variance", "p")}
    </section>
  </div>"""
    return f"""
<section class="verdict" aria-labelledby="verdict-t">
  <h2 class="vh" id="verdict-t">Verdict</h2>
  <p class="verdict-line">{e(line)}</p>
  <p class="verdict-basis">{e(basis)}</p>
  {tiles}
</section>"""


def notice(r: dict) -> str:
    ws = r["warnings"]
    if not ws:
        return ""
    first = NOTICE_PLAIN.get(ws[0]["code"], WARN_PLAIN.get(ws[0]["code"], ws[0]["message"]))
    rest = " ".join(NOTICE_PLAIN.get(w["code"], WARN_PLAIN.get(w["code"], w["message"])) for w in ws[1:2])
    more = "".join(f"<li>{e(w['message'])}</li>" for w in ws)
    return f"""
<aside class="notice" id="notice" aria-label="Data quality">{icon("warn")}
  <div><p class="notice-sum"><b>Read with care.</b> {e(first)}<br>{e(rest)}</p>
  <details class="more"><summary>Details</summary><ul>{more}</ul></details></div>
</aside>"""


def sharpe_interval(sr: float, years: float) -> tuple[float, float]:
    """Approximate 95% interval of an annual Sharpe ratio (Lo 2002, iid returns)."""
    se = math.sqrt((1 + 0.5 * sr * sr) / max(years, 1e-9))
    return sr - 1.96 * se, sr + 1.96 * se


def performance_strip(r: dict) -> str:
    p = PERFORMANCE.get(r["ticker"])
    if not p:
        return ""
    d = r["data"]
    lo, hi = sharpe_interval(p["sharpe"], p["years"])
    sure = "Clear evidence" if lo > 0 else "Could be noise"
    rec = f"recovered {d_long(p['recovered'])}" if p["recovered"] else "not yet recovered"
    cells = [
        ("perf-ret", pct(p["ret"], 1), "Return a year (compound)", "Dividends reinvested, before costs and taxes.", ""),
        ("perf-vol", p1(p["vol"]), "Volatility a year", "How widely the daily price swings, scaled to a year.", ""),
        ("perf-sr", num(p["sharpe"], 2), "Sharpe ratio: return per unit of risk, above the risk-free rate",
         "", stat(f"95% interval {num(lo, 2)} to {num(hi, 2)}: <b>{sure.lower()}</b>", "p")),
        ("perf-dd", pct(p["mdd"], 1), "Worst fall from a peak",
         f"{d_long(p['peak'])} to {d_long(p['trough'])}, {rec}.", ""),
    ]
    body = "".join(
        f'<div class="perf"><dt class="vh">{e(lab)}</dt><dd class="pv{" neg" if cid == "perf-dd" else ""}">{val}</dd>'
        f'<dd class="pl">{e(lab)}</dd>' + (f'<dd class="pn">{e(note)}</dd>' if note else "") + (f"<dd>{extra}</dd>" if extra else "") + "</div>"
        for cid, val, lab, note, extra in cells
    )
    return f"""
<section class="perf-strip" aria-labelledby="perf-t">
  <div class="perf-head"><h2 id="perf-t">How it performed</h2><p>{d_long(d['actual_start'])} to {d_long(d['actual_end'])}. Past results, not a forecast. <a href="#performance">See the drawdowns</a></p></div>
  <dl class="perf-row">{body}</dl>
</section>"""


# ----------------------------------------------------------------------------- what drives it: factor cards + world tile
def strength_svg(b: float, cls: str) -> str:
    lim = 1.5
    x = lambda v: 50 + max(-lim, min(lim, v)) / lim * 46  # noqa: E731
    a, c = sorted((50.0, x(b)))
    if c - a < 0.6:
        c = a + 0.6
    return (
        '<svg class="strength" aria-hidden="true">'
        '<line class="base" x1="4%" x2="96%" y1="11" y2="11"/>'
        f'<line class="fill {cls}" x1="{a:.2f}%" x2="{c:.2f}%" y1="11" y2="11"/>'
        f'<line class="tick" x1="{x(-1):.2f}%" x2="{x(-1):.2f}%" y1="5" y2="17"/>'
        '<line class="tick" x1="50%" x2="50%" y1="2" y2="20"/>'
        f'<line class="tick" x1="{x(1):.2f}%" x2="{x(1):.2f}%" y1="5" y2="17"/></svg>'
    )


def factor_card(f: dict, lead: bool = False) -> str:
    ok = f["tag"] == "reliable"
    pill, pcls, text = card_text(f)
    fill = ("pos" if f["beta"] >= 0 else "neg") if ok else "ns"
    cls = f"card {pcls if ok else 'ns'}" + (" lead" if lead else "")
    head = f'<h3>{PLAIN[f["name"]]}<span class="code stat">{e(f["name"])}</span></h3>'
    beta = f'<p class="beta">{sgn(f["beta"], 2)}<small>beta</small></p>'
    bar_ = f'<div class="strength-wrap">{strength_svg(f["beta"], fill)}</div>'
    txt = f'<div class="card-text"><span class="pill {pcls}">{e(pill)}</span><p>{e(text)}</p></div>'
    sure = f'<p class="sure">How sure: <b>{sure_word(f["tag"])}</b>{stat(f", t {tstat(f["z"])}")}</p>'
    if lead:
        return (f'<a class="{cls}" href="#beta-{f["name"]}"><div class="lead-a">{head}{beta}{bar_}</div>'
                f'<div class="lead-b">{txt}{sure}</div></a>')
    return f'<a class="{cls}" href="#beta-{f["name"]}">{head}{beta}{bar_}{txt}{sure}</a>'


def drivers(r: dict) -> str:
    g = r["regression"]
    w = WORLD.get(r["ticker"])
    world = ""
    if w:
        b, lo, hi = w["acwi"]
        world = (
            f'<a class="world-tile" href="#world"><span class="wt-l">Beta against the world</span>'
            f'<span class="wt-v">{num(b, 2)}</span><span class="wt-r">Likely range {num(lo, 2)} to {num(hi, 2)}, '
            f'against the ACWI fund</span><span class="wt-more">Compare with the US market</span></a>'
        )
    if g["status"] != "ok":
        body = empty_state(g["reason"], "Widen the date range in the sidebar and run the report again.")
    else:
        fs = {f["name"]: f for f in g["factors"]}
        body = (f'<div class="drivers-top">{factor_card(fs["Mkt-RF"], lead=True)}{world}</div>'
                f'<div class="cards">{"".join(factor_card(fs[n]) for n in ("SMB", "HML", "RMW", "CMA"))}</div>')
    return f"""
<section class="sec drivers" id="drivers" aria-labelledby="drivers-t">
  <div class="drivers-head"><div><h2 id="drivers-t" class="ph">What drives it</h2>
    <p>Five factors on one shared scale from &#8722;1.5 to +1.5; the centre line is zero. Select a factor for its detail.</p></div></div>
  {body}
</section>"""


def world_panel(r: dict) -> str:
    w = WORLD.get(r["ticker"])
    if not w:
        return ""
    rows_in = [
        ("Against the world", "ACWI, MSCI All Country World stand-in", w["acwi"], w["acwi_r2"]),
        ("Against the US market", "Fama&#8211;French market, same days", w["us"], w["us_r2"]),
    ]
    vals = [v for _, _, t, _ in rows_in for v in t] + [0.0]
    lo, hi, ticks = nice_domain(min(vals), max(vals), 4)
    rows = []
    for lab, sub, (b, l, h), r2 in rows_in:
        rows.append(
            f'<tr><th scope="row"><span class="fname">{lab}</span><span class="sub">{sub}</span></th>'
            f'<td class="plot-cell"><svg class="bar-svg" aria-hidden="true">{grid_lines(ticks, lo, hi)}'
            f'<line class="ci" x1="{pos(l, lo, hi)}%" x2="{pos(h, lo, hi)}%" y1="50%" y2="50%"/>'
            f'<line class="ci" x1="{pos(l, lo, hi)}%" x2="{pos(l, lo, hi)}%" y1="40%" y2="60%"/>'
            f'<line class="ci" x1="{pos(h, lo, hi)}%" x2="{pos(h, lo, hi)}%" y1="40%" y2="60%"/>'
            f'<circle class="dot-new" cx="{pos(b, lo, hi)}%" cy="50%" r="6"/></svg></td>'
            f'<td class="num strong">{num(b, 2)}</td><td class="num">{num(l, 2)} to {num(h, 2)}</td>'
            f'<td class="num">{r2:.2f}</td><td class="num">{w["days"]:,}</td></tr>'
        )
    (bw, lw, hw), (bu, lu, hu) = w["acwi"], w["us"]
    overlap = lw <= hu and lu <= hw
    t = r["ticker"]
    outcome = (
        f"{t} moves about the same against the world as against the US market ({num(bw, 2)} and {num(bu, 2)})."
        if overlap else
        f"{t} moves {'more' if bw > bu else 'less'} against the world ({num(bw, 2)}) than against the US market ({num(bu, 2)})."
    )
    main = f"""
  <table class="bars world">
    <caption class="vh">Beta against the world and against the US market, with 95% intervals, R squared and days</caption>
    <thead><tr><th scope="col">Against</th><th scope="col" class="plot-h"><span class="vh">Chart</span></th>
      <th scope="col" class="num">Beta</th><th scope="col" class="num w-wide">95% interval</th><th scope="col" class="num">R&#178;</th><th scope="col" class="num">Days</th></tr></thead>
    <tbody>{''.join(rows)}</tbody>
    <tfoot>{axis_row(ticks, lo, hi, tick)}</tfoot>
  </table>"""
    side = (
        f'<p class="reading">A beta of 1 means the stock moved one-for-one with that index. The intervals '
        f'{"overlap, so the two betas are about the same" if overlap else "do not overlap"}.</p>'
        + how("ACWI is an ETF used as a stand-in for the MSCI ACWI index; a quick estimate, not a full model.",
              "One-factor regression of daily excess returns on the ACWI ETF's excess returns, over the same days as the "
              "US market row, with Newey&#8211;West intervals.")
        + '<p class="demo">Demo values: the fixture has no world beta yet.</p>'
    )
    return sec("world", "World beta (quick estimate)", e(outcome), main, side, two="xl")


# ----------------------------------------------------------------------------- price and performance
def price_panel(r: dict) -> str:
    p, d = r["price_series"], r["data"]
    dates, px = p["dates"], p["adj_close"]
    pts = [(i, v) for i, v in enumerate(px) if v is not None]
    if len(pts) < 2:
        return sec_empty("price", "Price", "No prices were returned for this ticker and window.", "Check the ticker symbol or choose a later start date.")
    cov = p["factor_coverage_end"]
    cut = max((i for i, s in enumerate(dates) if s <= cov), default=len(dates) - 1)
    lo, hi, ticks = nice_domain(min(v for _, v in pts), max(v for _, v in pts), 4)
    n = len(dates) - 1
    X = lambda i: i / n * 1000  # noqa: E731
    Y = lambda v: 100 - (v - lo) / (hi - lo) * 100  # noqa: E731
    main_l = [(X(i), Y(v)) for i, v in pts if i <= cut]
    tail = [(X(i), Y(v)) for i, v in pts if i >= cut]
    grid = "".join(f'<line class="grid" x1="0" x2="1000" y1="{Y(t):.2f}" y2="{Y(t):.2f}"/>' for t in ticks)
    shade = ""
    if cut < n:
        shade = (f'<rect class="tailzone" x="{X(cut):.1f}" y="0" width="{1000 - X(cut):.1f}" height="100"/>'
                 f'<line class="cutline" x1="{X(cut):.1f}" x2="{X(cut):.1f}" y1="0" y2="100"/>')
    svg = (
        f'<svg class="line-svg" viewBox="0 0 1000 100" preserveAspectRatio="none" aria-hidden="true">{shade}{grid}'
        f'<path class="price-line" d="{path_xy(*zip(*main_l))}"/>'
        + (f'<path class="price-tail" d="{path_xy(*zip(*tail))}"/>' if len(tail) > 1 else "") + "</svg>"
    )
    ylab = "".join(f'<span class="yl" style="top:{Y(t):.2f}%">{t:,.0f}</span>' for t in ticks)
    xlab = time_labels(date_ticks(dates), lambda i: X(i) / 10)
    zone = f'<span class="zone-label">Not analysed: after {d_long(cov)}</span>' if cut < n else ""
    first, at_cut, last = pts[0][1], px[cut], pts[-1][1]
    chg = at_cut / first - 1
    u = d["uncovered"]
    side_rows = [
        ("First", d_long(dates[pts[0][0]]), f"{first:,.2f}", ""),
        ("End of factor data", d_long(dates[cut]), f"{at_cut:,.2f}", ""),
        ("Latest", d_long(dates[pts[-1][0]]), f"{last:,.2f}", ""),
    ]
    if u["n"] and u["compounded_return"] is not None:
        side_rows.append(("After factor data", f"{u['n']} days, not analysed", pct(u["compounded_return"]), "muted-row"))
    side_t = "".join(
        f'<tr class="{c}"><th scope="row">{a}<span class="sub">{b}</span></th><td>{v}</td></tr>' for a, b, v, c in side_rows
    )
    outcome = f"{e(r['ticker'])} {'rose' if chg >= 0 else 'fell'} {p1(abs(chg))} over the analysed window."
    if u["n"]:
        outcome += f" The last {u['n']} days are shown but not analysed."
    main = (f'<div class="plot price-plot">{svg}<div class="ylabels" aria-hidden="true">{ylab}</div>{zone}'
            f'<div class="xlabels" aria-hidden="true">{xlab}</div></div>')
    side = (
        f'<table class="side-table"><caption class="vh">Price points</caption><tbody>{side_t}</tbody></table>'
        + how(f"Adjusted close from {e(d['price_source'])}, for context only; no statistic uses the price line.")
    )
    return sec("price", "Price", outcome, main, side)


def drawdown_series(px: list[float | None], upto: int) -> list[float | None]:
    out, peak = [], None
    for v in px[: upto + 1]:
        if v is None:
            out.append(None)
            continue
        peak = v if peak is None or v > peak else peak
        out.append(v / peak - 1)
    return out


def episodes(dd: list[float | None], dates: list[str]) -> list[dict]:
    """Peak-to-trough episodes of an underwater series, deepest first."""
    eps, cur = [], None
    for i, x in enumerate(dd):
        if x is None:
            continue
        if x < 0 and cur is None:
            cur = {"peak": i - 1, "trough": i, "depth": x, "rec": None}
        elif x < 0:
            if x < cur["depth"]:
                cur["depth"], cur["trough"] = x, i
        elif cur is not None:
            cur["rec"] = i
            eps.append(cur)
            cur = None
    if cur:
        eps.append(cur)
    eps.sort(key=lambda z: z["depth"])
    return [{**z, "peak_d": dates[max(z["peak"], 0)], "trough_d": dates[z["trough"]],
             "rec_d": dates[z["rec"]] if z["rec"] is not None else None} for z in eps]


def performance_panel(r: dict) -> str:
    perf = PERFORMANCE.get(r["ticker"])
    p = r["price_series"]
    dates, px = p["dates"], p["adj_close"]
    if not perf or sum(v is not None for v in px) < 2:
        return ""
    cut = max((i for i, s in enumerate(dates) if s <= p["factor_coverage_end"]), default=len(dates) - 1)
    raw = drawdown_series(px, cut)
    worst = min(x for x in raw if x is not None)
    k = perf["mdd"] / worst if worst < 0 else 1.0  # demo: scale the mock shape to the keyed depth
    dd = [None if x is None else max(x * k, -0.99) for x in raw]
    eps = episodes(dd, dates[: cut + 1])[:3]
    lo, _, ticks = nice_domain(min(x for x in dd if x is not None), 0.0, 4)
    ticks = [t for t in ticks if t <= 1e-12]
    hi = 0.0
    n = cut
    X = lambda i: i / max(n, 1) * 1000  # noqa: E731
    Y = lambda v: (v - hi) / (lo - hi) * 100  # noqa: E731
    pts = [(X(i), Y(x)) for i, x in enumerate(dd) if x is not None]
    area = "M0,0 L" + " L".join(f"{x:.1f},{y:.1f}" for x, y in pts) + f" L{pts[-1][0]:.1f},0Z"
    grid = "".join(f'<line class="grid" x1="0" x2="1000" y1="{Y(t):.2f}" y2="{Y(t):.2f}"/>' for t in ticks if t < 0)
    svg = (
        f'<svg class="line-svg" viewBox="0 0 1000 100" preserveAspectRatio="none" aria-hidden="true">{grid}'
        f'<path class="uw-area" d="{area}"/><path class="uw-line" d="{path_xy(*zip(*pts))}"/>'
        '<line class="zero" x1="0" x2="1000" y1="0" y2="0"/></svg>'
    )
    ylab = "".join(f'<span class="yl" style="top:{Y(t):.2f}%">{pct(t, 0) if t else "0%"}</span>' for t in ticks)
    xlab = time_labels(date_ticks(dates[: cut + 1]), lambda i: X(i) / 10)
    rows = "".join(
        f'<tr><td>{pct(z["depth"], 1)}</td><td>{d_long(z["peak_d"])}</td><td>{d_long(z["trough_d"])}</td>'
        f'<td>{d_long(z["rec_d"]) if z["rec_d"] else "Not yet"}</td>'
        f'<td>{plural((z["rec"] if z["rec"] is not None else cut) - max(z["peak"], 0), "day")}</td></tr>'
        for z in eps
    )
    lo_s, hi_s = sharpe_interval(perf["sharpe"], perf["years"])
    rec = "and has since recovered" if perf["recovered"] else "and has not recovered yet"
    outcome = (
        f"The worst fall was {pct(-perf['mdd'], 1, False)} from {d_long(perf['peak'])} to {d_long(perf['trough'])}, {rec}."
    )
    main = f"""
  <div class="plot uw-plot">{svg}<div class="ylabels" aria-hidden="true">{ylab}</div><div class="xlabels" aria-hidden="true">{xlab}</div></div>
  <div class="scroll-x" tabindex="0" role="region" aria-label="Largest falls from a peak">
  <table class="tbl dd"><caption class="vh">The three largest falls from a peak</caption>
    <thead><tr><th scope="col">Fall</th><th scope="col">Peak</th><th scope="col">Lowest point</th><th scope="col">Back at the peak</th><th scope="col">Length</th></tr></thead>
    <tbody>{rows}</tbody></table></div>"""
    side = f"""
  <dl class="perf-list">
    <div><dt>Return a year (compound)</dt><dd>{pct(perf['ret'], 1)}</dd></div>
    <div><dt>Volatility a year</dt><dd>{p1(perf['vol'])}</dd></div>
    <div><dt>Sharpe ratio</dt><dd>{num(perf['sharpe'], 2)}{stat(f'<span class="sub">95% interval {num(lo_s, 2)} to {num(hi_s, 2)}</span>')}</dd></div>
    <div><dt>Worst fall from a peak</dt><dd>{pct(perf['mdd'], 1)}</dd></div>
  </dl>
  <p class="reading">The shaded area shows how far the price stood below its previous high on each day.</p>
  {how("Total return from adjusted closes over the analysed range; before costs and taxes.",
       "Return a year is the compound growth rate. Volatility is the standard deviation of daily returns times the square root of 252. "
       "The Sharpe ratio is the average excess return over the risk-free rate divided by volatility; its interval uses the Lo (2002) approximation.")}
  <p class="demo">Demo values: the fixture has no performance block yet; the chart reuses the mock price shape.</p>"""
    return sec("performance", "Performance", e(outcome), main, side)


# ----------------------------------------------------------------------------- exposures, returns, risk
def exposures_panel(r: dict) -> str:
    g, ab = r["regression"], r["average_beta"]
    if g["status"] != "ok":
        return sec_empty("exposures", "Factor exposures", g["reason"], "Widen the date range and run the report again.")
    win = ab.get("window", 252)
    avg = {f["name"]: f["mean"] for f in ab["factors"]} if ab["status"] == "ok" else {}
    vals = [v for f in g["factors"] for v in (f["ci_low"], f["ci_high"], f["beta"])] + [0.0]
    lo, hi, ticks = nice_domain(min(vals), max(vals), 5)
    rows = []
    for f in g["factors"]:
        ns, b = f["tag"] != "reliable", f["beta"]
        cls = ("pos" if b >= 0 else "neg") + (" faded" if ns else "")
        l, h = pos(f["ci_low"], lo, hi), pos(f["ci_high"], lo, hi)
        whisk = f'<line class="ci" x1="{l}%" x2="{h}%" y1="50%" y2="50%"/>'
        if h - l >= 1.2:
            whisk += (f'<line class="ci" x1="{l}%" x2="{l}%" y1="44%" y2="56%"/>'
                      f'<line class="ci" x1="{h}%" x2="{h}%" y1="44%" y2="56%"/>')
        a = avg.get(f["name"])
        if a is not None:
            whisk += (f'<svg class="avgm" x="{pos(a, lo, hi)}%" y="50%" overflow="visible" aria-hidden="true">'
                      '<path d="M0 -4 4 0 0 4-4 0z"/></svg>')
        tip = f"{f['name']}: beta {sgn(b)}, 95% interval {sgn(f['ci_low'])} to {sgn(f['ci_high'])}, t {tstat(f['z'])}"
        rows.append(
            f'<tr id="beta-{f["name"]}" class="{"ns" if ns else ""}" tabindex="-1">'
            f'<th scope="row"><span class="fname">{PLAIN[f["name"]]}</span><span class="sub">{e(f["name"])}</span></th>'
            f'<td class="plot-cell"><svg class="bar-svg" aria-hidden="true"><title>{e(tip)}</title>'
            f"{grid_lines(ticks, lo, hi)}{bar(b, lo, hi, cls)}{whisk}</svg></td>"
            f'<td class="num strong">{sgn(b)}</td>{word_cell(not ns)}'
            f'<td class="num stat">{tstat(f["z"])}</td><td class="num stat">{pval(f["p_adj_bh"])}</td>'
            f'<td class="num stat">{sgn(a) if a is not None else "&#8211;"}</td></tr>'
        )
    fs = {f["name"]: f for f in g["factors"]}
    mk = fs["Mkt-RF"]
    clear = [PLAIN[n].lower() for n in ("SMB", "HML", "RMW", "CMA") if fs[n]["tag"] == "reliable"]
    noise = [PLAIN[n].lower() for n in ("SMB", "HML", "RMW", "CMA") if fs[n]["tag"] != "reliable"]
    small = all(abs(fs[n]["beta"]) < 0.2 for n in ("SMB", "HML", "RMW", "CMA") if fs[n]["tag"] == "reliable")
    outcome = (f"The market dominates: {e(r['ticker'])} {market_phrase(mk['beta'])}." if mk["tag"] == "reliable"
               else "There is no clear link to the market.")
    if clear:
        outcome += f" The {and_list(clear)} tilt{'s are' if len(clear) > 1 else ' is'} clear{' but small' if small else ''}"
        outcome += f"; {and_list(noise)} could be noise." if noise else "."
    legend = (
        '<ul class="legend" aria-label="Legend">'
        '<li><svg class="sw" aria-hidden="true"><rect class="pos" width="14" height="10" rx="2"/></svg>Positive</li>'
        '<li><svg class="sw" aria-hidden="true"><rect class="neg" width="14" height="10" rx="2"/></svg>Negative</li>'
        '<li><svg class="sw" aria-hidden="true"><rect class="pos faded" x="0.5" y="0.5" width="13" height="9" rx="2"/></svg>Pale: could be noise</li>'
        '<li><svg class="sw" aria-hidden="true"><line class="ci" x1="1" x2="15" y1="5" y2="5"/><line class="ci" x1="1" x2="1" y1="3" y2="7"/><line class="ci" x1="15" x2="15" y1="3" y2="7"/></svg>Likely range</li>'
        f'<li><svg class="sw" aria-hidden="true"><path class="avgm-sw" d="M8 1 12 5 8 9 4 5z"/></svg>Average over {win}-day windows</li></ul>'
    )
    main = f"""
  <table class="bars exp">
    <caption class="vh">Full-sample factor betas with likely ranges and how sure we are</caption>
    <thead><tr><th scope="col">Factor</th><th scope="col" class="plot-h"><span class="vh">Chart</span></th>
      <th scope="col" class="num">Beta</th><th scope="col" class="num w-word">How sure</th>
      <th scope="col" class="num stat">t</th><th scope="col" class="num stat">p, adjusted</th><th scope="col" class="num stat">Avg {win}d</th></tr></thead>
    <tbody>{''.join(rows)}</tbody>
    <tfoot>{axis_row(ticks, lo, hi, tick)}</tfoot>
  </table>"""
    side = (
        legend
        + f'<p class="reading">A beta of +1 on the market means the stock moved one-for-one with it. Bars to the right of zero are positive exposures; the whisker is the likely range.</p>'
        + how("In-sample, descriptive, not predictive. Clear evidence means the adjusted p is below 0.05.",
              f"OLS on daily excess returns with Newey&#8211;West standard errors ({g['hac_lags']} lags). Clear means the "
              f"Benjamini&#8211;Hochberg adjusted p is below 0.05 across the {g['bh_family_size']} betas. The diamond is the mean of the overlapping {win}-day estimates.")
    )
    return sec("exposures", "Factor exposures", outcome, main, side)


def return_panel(r: dict) -> str:
    rc, g = r["return_contribution"], r["regression"]
    if rc["status"] != "ok":
        return sec_empty("returns", "Where the return came from", rc["reason"], "Widen the date range and run the report again.")
    tags = {f["name"]: f["tag"] for f in g["factors"]}
    items = [(PLAIN[n], n, rc["factors"][n], tags.get(n) != "reliable", "factor") for n in FACTORS]
    items.append(("Beyond the factors", "Alpha", rc["alpha"], g["alpha_tag"] != "reliable", "alpha"))
    total = rc["total_annualised_mean_excess_return"]
    vals = [x[2] for x in items] + [total, 0.0]
    lo, hi, ticks = nice_domain(min(vals), max(vals), 5)
    rows = []
    for plain, code, v, ns, kind in items:
        cls = ("pos" if v >= 0 else "neg") + (" faded" if ns else "")
        rid = "ret-alpha" if kind == "alpha" else f"ret-{code}"
        rows.append(
            f'<tr id="{rid}" class="{"ns" if ns else ""}" tabindex="-1"><th scope="row"><span class="fname">{plain}</span><span class="sub">{e(code)}</span></th>'
            f'<td class="plot-cell"><svg class="bar-svg" aria-hidden="true"><title>{e(plain)}: {pct(v)} a year</title>{grid_lines(ticks, lo, hi)}{bar(v, lo, hi, cls)}</svg></td>'
            f'<td class="num strong">{pct(v)}</td>{word_cell(not ns)}</tr>'
        )
    tx, z0 = pos(total, lo, hi), pos(0.0, lo, hi)
    rows.append(
        f'<tr class="total"><th scope="row"><span class="fname">Total</span><span class="sub">Average return above cash</span></th>'
        f'<td class="plot-cell"><svg class="bar-svg" aria-hidden="true">{grid_lines(ticks, lo, hi)}'
        f'<line class="total-line" x1="{min(z0, tx)}%" x2="{max(z0, tx)}%" y1="50%" y2="50%"/>'
        f'<line class="total-cap" x1="{tx}%" x2="{tx}%" y1="24%" y2="76%"/></svg></td>'
        f'<td class="num strong">{pct(total)}</td><td class="word"></td></tr>'
    )
    mkt = rc["factors"]["Mkt-RF"]
    a_ns = g["alpha_tag"] != "reliable"
    outcome = (f"Market exposure accounts for {p1(mkt)} of the {p1(total)} average yearly return; "
               f"the {pct(rc['alpha'], 1)} left over {'is not reliably different from zero' if a_ns else 'is a reliable return beyond the factors'}.")
    memo = "".join(f"<li>{e(m)}</li>" for m in rc["memo"])
    main = f"""
  <table class="bars ret">
    <caption class="vh">Return contribution per factor and beyond the factors, percent a year, with the total</caption>
    <thead><tr><th scope="col">Source</th><th scope="col" class="plot-h"><span class="vh">Chart</span></th>
      <th scope="col" class="num">A year</th><th scope="col" class="num w-word">How sure</th></tr></thead>
    <tbody>{''.join(rows)}</tbody>
    <tfoot>{axis_row(ticks, lo, hi, lambda t: pct(t, 0) if t else "0%", 2)}</tfoot>
  </table>"""
    side = (
        '<p class="reading">Each bar is the part of the average yearly return that one exposure explains. The bars add up to the total.</p>'
        + f'<div class="callout"><h3>Not in the sum</h3><ul>{memo}</ul></div>'
        + how("In-sample, descriptive, not predictive. The rows add up exactly to the total.",
              "Each factor's share is its full-sample beta times the factor's average return, times 252. Arithmetic, not compounded.")
    )
    return sec("returns", "Where the return came from", e(outcome), main, side)


def risk_panel(r: dict) -> str:
    rk = r["risk_contribution"]
    if rk["status"] != "ok":
        return sec_empty("risk", "Where the risk comes from", rk["reason"], "Widen the date range and run the report again.")
    det = {d["name"]: d for d in rk["details"]}
    shares = {**rk["factors"], "Idiosyncratic": rk["idiosyncratic"]}
    low = min(shares.values())
    lo, hi, ticks = nice_domain(low if low < -0.02 else 0.0, max(1.0, max(shares.values())), 4)
    rows = []
    for n in rk["order"]:
        v = shares[n]
        if n == "Idiosyncratic":
            cls, plain, code = "hatch", "Specific to the stock", "Not explained by the factors"
            extra = '<td class="num stat">&#8211;</td><td class="num stat">&#8211;</td><td class="num stat">&#8211;</td>'
            key = '<svg class="key" aria-hidden="true"><rect class="hatch" width="10" height="10" rx="2"/></svg>'
        else:
            dd = det[n]
            cls, plain, code = f"cat c{SLOT[n]}", PLAIN[n], n
            extra = (f'<td class="num stat">{sgn(dd["beta"])}</td><td class="num stat">{p1(dd["sigma_annual"])}</td>'
                     f'<td class="num stat">{sgn(dd["rho_sys"], 2)}</td>')
            key = f'<svg class="key" aria-hidden="true"><rect class="c{SLOT[n]}" width="10" height="10" rx="2"/></svg>'
        rows.append(
            f'<tr><th scope="row"><span class="fname">{key}{plain}</span><span class="sub">{e(code)}</span></th>'
            f'<td class="plot-cell"><svg class="bar-svg" aria-hidden="true">{grid_lines(ticks, lo, hi)}{bar(v, lo, hi, cls)}</svg></td>'
            f'<td class="num strong">{pct(v, 2, v < 0)}</td>{extra}</tr>'
        )
    top = rk["order"][0]
    outcome = (f"The {PLAIN.get(top, top).lower()} drives {share(shares[top])} of the day-to-day swings; "
               f"{share(rk['idiosyncratic'])} is specific to {e(r['ticker'])}.")
    main = f"""
  <table class="bars risk">
    <caption class="vh">Share of variance per factor and stock-specific</caption>
    <thead><tr><th scope="col">Source</th><th scope="col" class="plot-h"><span class="vh">Chart</span></th>
      <th scope="col" class="num">Share</th><th scope="col" class="num stat">Beta</th><th scope="col" class="num stat">Factor vol</th><th scope="col" class="num stat">Corr.</th></tr></thead>
    <tbody>{''.join(rows)}</tbody>
    <tfoot>{axis_row(ticks, lo, hi, lambda t: pct(t, 0, False) if t >= 0 else pct(t, 0), 4)}</tfoot>
  </table>"""
    side = (
        f'<p class="reading">Total volatility is {p1(rk["total_vol_annual"])} a year. Shares add to 100% and can be negative when a factor offsets the others.</p>'
        + how("In-sample, descriptive, not predictive.",
              "Euler decomposition of variance: share = beta &#215; factor vol &#215; correlation with the factor-driven return, divided by total vol.")
    )
    return sec("risk", "Where the risk comes from", outcome, main, side)


# ----------------------------------------------------------------------------- rolling
def rolling_block(w: dict, avg: dict | None) -> str:
    dates, z = w["dates"], w["ci_z"]
    n = len(dates) - 1
    series = {}
    for name in FACTORS:
        b, s = w["betas"].get(name, []), w["se"].get(name, [])
        series[name] = [(i, b[i], s[i]) for i in range(len(b)) if b[i] is not None and s[i] is not None]
    spans = [max(v + z * s for _, v, s in p) - min(v - z * s for _, v, s in p) for p in series.values() if p]
    span = max(spans) * 1.08 if spans else 1.0
    i0 = min((p[0][0] for p in series.values() if p), default=0)
    xt = [t for t in date_ticks(dates) if t[0] >= i0]
    X = lambda i: (i - i0) / max(n - i0, 1) * 1000  # noqa: E731
    rows = []
    for name in FACTORS:
        pts = series[name]
        if not pts:
            continue
        mid = (max(v + z * s for _, v, s in pts) + min(v - z * s for _, v, s in pts)) / 2
        lo, hi = mid - span / 2, mid + span / 2
        Y = lambda v: 100 - (v - lo) / (hi - lo) * 100  # noqa: E731
        step = 2 if len(pts) > 400 else 1
        sp = pts[::step] + ([pts[-1]] if (len(pts) - 1) % step else [])
        up = [(X(i), Y(v + z * s)) for i, v, s in sp]
        dn = [(X(i), Y(v - z * s)) for i, v, s in sp][::-1]
        band = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in up + dn) + "Z"
        line = path_xy([X(i) for i, _, _ in sp], [Y(v) for _, v, _ in sp])
        zero = f'<line class="zero" x1="0" x2="1000" y1="{Y(0):.2f}" y2="{Y(0):.2f}"/>' if lo < 0 < hi else ""
        vgrid = "".join(f'<line class="grid" x1="{X(i):.1f}" x2="{X(i):.1f}" y1="0" y2="100"/>' for i, _, major in xt if major)
        svg = (f'<svg class="line-svg" viewBox="0 0 1000 100" preserveAspectRatio="none" aria-hidden="true">{vgrid}{zero}'
               f'<path class="band c{SLOT[name]}" d="{band}"/><path class="rline c{SLOT[name]}" d="{line}"/></svg>')
        yl = [(hi, "top"), (lo, "bot")]
        ylab = "".join(f'<span class="yl {c}" style="top:{Y(t):.2f}%">{sgn(t, 2) if abs(t) > 1e-9 else "0"}</span>' for t, c in yl)
        vals = [v for _, v, _ in pts]
        a = (avg or {}).get(name)
        if a and a.get("mean") is not None:
            mean, p10, p90 = a["mean"], a["p10"], a["p90"]
        else:
            mean, p10, p90 = sum(vals) / len(vals), _quantile(vals, 0.1), _quantile(vals, 0.9)
        rows.append(
            f'<tr><th scope="row"><span class="fname"><svg class="key" aria-hidden="true"><rect class="c{SLOT[name]}" width="10" height="10" rx="2"/></svg>{PLAIN[name]}</span>'
            f'<span class="sub">{e(name)}</span></th>'
            f'<td class="plot-cell"><div class="plot mini">{svg}<div class="ylabels" aria-hidden="true">{ylab}</div></div></td>'
            f'<td class="num strong">{sgn(vals[-1])}</td><td class="num">{sgn(mean)}</td>'
            f'<td class="num stat">{sgn(p10, 2)} to {sgn(p90, 2)}</td></tr>'
        )
    xlab = time_labels(xt, lambda i: X(i) / 10, gap=20)
    win = w["window"]
    return f"""
<div class="win w-{win}">
  <table class="bars rolling">
    <caption class="vh">Rolling {win}-day betas per factor with a 95% band; latest and average</caption>
    <thead><tr><th scope="col">Factor</th><th scope="col" class="plot-h"><span class="vh">Chart</span></th>
      <th scope="col" class="num">Latest</th><th scope="col" class="num">Average</th><th scope="col" class="num stat w-wide">Middle 80%</th></tr></thead>
    <tbody>{''.join(rows)}</tbody>
    <tfoot><tr class="axis-row" aria-hidden="true"><td></td><td class="axis time"><div style="margin-left:60px">{xlab}</div></td></tr></tfoot>
  </table>
  <p class="foot">Each point uses the previous {win} trading days; the chart starts at the first full window, {d_long(dates[i0])}.</p>
</div>"""


def rolling_panel(r: dict, win126: bool = False) -> str:
    wins = sorted(r["rolling"], key=lambda w: w["window"])
    ab = r["average_beta"]
    primary = 126 if win126 else ab.get("window", 252)
    ok = [w for w in wins if w["status"] == "ok"]
    if not ok:
        return sec_empty("rolling", "Exposure over time", wins[0]["reason"] if wins else "No rolling windows were computed.",
                         "Rolling betas need more trading days than the window length. Choose an earlier start date.")
    avg = {f["name"]: f for f in ab["factors"]} if ab["status"] == "ok" else {}
    seg = "".join(
        f'<label><input type="radio" name="window" id="win-{w["window"]}" value="{w["window"]}"{" checked" if w["window"] == primary else ""}><span>{w["window"]} days</span></label>'
        for w in wins
    )
    blocks = "".join(
        rolling_block(w, avg if w["window"] == ab.get("window", 252) else None) if w["status"] == "ok"
        else f'<div class="win w-{w["window"]}">{empty_state(w["reason"], "Choose an earlier start date or the shorter window.")}</div>'
        for w in wins
    )
    mk = avg.get("Mkt-RF")
    widest = max(((f["p90"] - f["p10"]), n) for n, f in avg.items()) if avg else (0, "")
    if mk and widest[0] < 0.15:
        outcome = (f"The exposures were steady: in most windows the market beta stayed between {num(mk['p10'], 2)} "
                   f"and {num(mk['p90'], 2)}, and no other beta moved by more than {num(widest[0], 2)}.")
    elif widest[1]:
        outcome = f"The {PLAIN[widest[1]].lower()} exposure moved the most over time; the others were steadier."
    else:
        outcome = "See how each exposure moved over time."
    extra = f'<div class="seg" role="radiogroup" aria-label="Rolling window length">{seg}</div>'
    main = blocks
    side = (
        '<p class="reading">Each line is the beta re-estimated over a moving window. A flat line means a stable exposure; the shaded band is the likely range.</p>'
        + how("In-sample, descriptive, not predictive. The band is a pointwise 95% interval.",
              "About 1 point in 20 falls outside the band even when the true beta is constant. Overlapping windows share most of their data. "
              "Every row uses the same vertical span, centred on its own values, so wiggles compare across factors.")
    )
    return sec("rolling", "Exposure over time", e(outcome), main, side, two="xl", extra=extra)


# ----------------------------------------------------------------------------- condensed demo panels
def residual_panel(r: dict) -> str:
    """Condensed residual-alpha panel. The mock fixture has no residual section: demo values."""
    w = next((w for w in r["rolling"] if w["window"] == 252 and w["status"] == "ok"), None)
    if not w or r["regression"]["status"] != "ok":
        return ""
    dates = w["dates"]
    i0 = next(i for i, b in enumerate(w["betas"]["Mkt-RF"]) if b is not None)
    idx = list(range(i0, len(dates)))
    a = [0.008 + 0.022 * math.sin((i - i0) / 46) + 0.006 * math.sin((i - i0) / 9) for i in idx]
    half = [0.055 - 0.01 * math.cos((i - i0) / 60) for i in idx]
    clear = sum(1 for v, h in zip(a, half) if v - h > 0 or v + h < 0) / len(a)
    lo, hi, ticks = nice_domain(min(v - h for v, h in zip(a, half)), max(v + h for v, h in zip(a, half)), 4)
    n = len(idx) - 1
    X = lambda k: k / max(n, 1) * 1000  # noqa: E731
    Y = lambda v: 100 - (v - lo) / (hi - lo) * 100  # noqa: E731
    up = [(X(k), Y(v + h)) for k, (v, h) in enumerate(zip(a, half))]
    dn = [(X(k), Y(v - h)) for k, (v, h) in enumerate(zip(a, half))][::-1]
    band = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in up + dn) + "Z"
    line = path_xy([X(k) for k in range(len(a))], [Y(v) for v in a])
    grid = "".join(f'<line class="{"zero" if abs(t) < 1e-12 else "grid"}" x1="0" x2="1000" y1="{Y(t):.2f}" y2="{Y(t):.2f}"/>' for t in ticks)
    svg = (f'<svg class="line-svg" viewBox="0 0 1000 100" preserveAspectRatio="none" aria-hidden="true">{grid}'
           f'<path class="band hi" d="{band}"/><path class="rline hi" d="{line}"/></svg>')
    ylab = "".join(f'<span class="yl" style="top:{Y(t):.2f}%">{pct(t, 0) if t else "0%"}</span>' for t in ticks)
    xt = [(i - i0, lab, major) for i, lab, major in date_ticks(dates) if i >= i0]
    xlab = time_labels(xt, lambda k: X(k) / 10)
    years = [("2024", "partial, 100 days", 0.006, 0.011), ("2025", "250 days", 0.003, 0.009), ("2026", "partial, 188 days", -0.001, 0.010)]
    yrows = "".join(
        f'<tr><th scope="row">{y}<span class="sub">{note}</span></th><td>{pct(s, 1)}</td><td class="stat">{pct(sd, 1, False)}</td>'
        f'<td class="word {"no"}">Could be noise</td></tr>'
        for y, note, s, sd in years
    )
    outcome = "No stretch of the window shows a reliable return beyond the factors; the leftover return wanders around zero."
    main = f"""
  <div class="plot alpha">{svg}<div class="ylabels" aria-hidden="true">{ylab}</div><div class="xlabels" aria-hidden="true">{xlab}</div></div>
  <dl class="facts-row">
    <div class="fact"><dt>Windows clear of zero</dt><dd>{clear * 100:.0f}%</dd><dd class="small">of 252-day windows; about 5% is expected by chance</dd></div>
    <div class="fact"><dt>First half, second half</dt><dd>+1.4%, +0.2%</dd><dd class="small">a year; the change could be noise{stat(", p 0.61")}</dd></div>
    <div class="fact"><dt>Best calendar year</dt><dd>2024, +0.6%</dd><dd class="small">partial year; no year is clear of noise</dd></div>
  </dl>"""
    side = (
        '<p class="reading">The leftover return is what the factors do not explain. A line that stays inside its band around zero means no reliable extra return.</p>'
        + '<details class="more"><summary>By calendar year</summary>'
        + f'<table class="tbl"><thead><tr><th scope="col">Year</th><th scope="col">Leftover</th><th scope="col" class="stat">Noise, sd</th><th scope="col">How sure</th></tr></thead><tbody>{yrows}</tbody></table></details>'
        + how("In-sample, descriptive. Windows overlap, so the share of windows is descriptive, not a test.",
              "Rolling 252-day regressions of daily excess returns with Newey&#8211;West intervals; the split-half test compares the two halves of the sample.")
        + '<p class="demo">Demo values: the mock fixture has no residual section.</p>'
    )
    return sec("residual", "Return beyond the factors over time", outcome, main, side)


def dot_row(label: str, code: str, lo: float, hi: float, ticks: list[float], parts: str, cells: str, rid: str = "") -> str:
    return (
        f'<tr{f" id={chr(34)}{rid}{chr(34)}" if rid else ""}><th scope="row"><span class="fname">{label}</span><span class="sub">{e(code)}</span></th>'
        f'<td class="plot-cell"><svg class="bar-svg" aria-hidden="true">{grid_lines(ticks, lo, hi)}{parts}</svg></td>{cells}</tr>'
    )


def kalman_panel(r: dict) -> str:
    """Condensed Kalman panel: latest day-by-day beta against the full-sample beta. Demo values."""
    w = next((w for w in r["rolling"] if w["window"] == 126 and w["status"] == "ok"), None)
    g = r["regression"]
    if not w or g["status"] != "ok":
        return ""
    fs = {f["name"]: f for f in g["factors"]}
    lam = {"Mkt-RF": 0.0004, "SMB": 0.0, "HML": 0.0011, "RMW": 0.0, "CMA": 0.0}
    rows_d = []
    for n in FACTORS:
        b = [v for v in w["betas"][n] if v is not None][-1]
        s = [v for v in w["se"][n] if v is not None][-1] * 0.85
        kb = 0.6 * b + 0.4 * fs[n]["beta"]
        rows_d.append((n, kb, kb - 1.96 * s, kb + 1.96 * s, fs[n]["beta"]))
    vals = [v for _, k, l, h, o in rows_d for v in (l, h, o)] + [0.0]
    lo, hi, ticks = nice_domain(min(vals), max(vals), 5)
    rows = []
    moved = []
    for n, kb, l, h, o in rows_d:
        inside = l <= o <= h
        if not inside:
            moved.append(PLAIN[n].lower())
        parts = (f'<line class="ci" x1="{pos(l, lo, hi)}%" x2="{pos(h, lo, hi)}%" y1="50%" y2="50%"/>'
                 f'<circle class="dot-ols" cx="{pos(o, lo, hi)}%" cy="50%" r="5"/>'
                 f'<circle class="dot-new" cx="{pos(kb, lo, hi)}%" cy="50%" r="5"/>')
        cells = (f'<td class="num strong">{sgn(kb)}</td><td class="num">{sgn(o)}</td>'
                 f'<td class="num stat">{sgn(l, 2)} to {sgn(h, 2)}</td><td class="num stat">{lam[n]:.4f}</td>'
                 f'<td class="word {"no" if inside else "yes"}">{"No clear change" if inside else "Moved"}</td>')
        rows.append(dot_row(PLAIN[n], n, lo, hi, ticks, parts, cells))
    outcome = ("None of the exposures has moved clearly away from its full-sample value."
               if not moved else f"The {and_list(moved)} exposure{'s have' if len(moved) > 1 else ' has'} moved away from the full-sample value.")
    main = f"""
  <table class="bars kalman">
    <caption class="vh">Latest day-by-day beta with its band, against the full-sample beta</caption>
    <thead><tr><th scope="col">Factor</th><th scope="col" class="plot-h"><span class="vh">Chart</span></th>
      <th scope="col" class="num">Latest</th><th scope="col" class="num">Full sample</th><th scope="col" class="num stat w-wide">Band</th><th scope="col" class="num stat">Drift</th><th scope="col" class="num w-word">Changed?</th></tr></thead>
    <tbody>{''.join(rows)}</tbody>
    <tfoot>{axis_row(ticks, lo, hi, tick)}</tfoot>
  </table>"""
    side = (
        '<ul class="legend" aria-label="Legend"><li><svg class="sw" aria-hidden="true"><circle class="dot-new" cx="8" cy="5" r="5"/></svg>Latest, tracked day by day</li>'
        '<li><svg class="sw" aria-hidden="true"><circle class="dot-ols" cx="8" cy="5" r="4.5"/></svg>Full sample</li></ul>'
        + '<p class="reading">A filter updates each beta every day as new prices arrive. When the hollow dot sits inside the band, the exposure has not clearly changed.</p>'
        + how("Descriptive; the band is the model's 95% range for the latest day.",
              "Random-walk betas with a constant alpha, estimated by a Kalman filter and re-estimated every 252 rows after a 504-row training period.")
        + '<p class="demo">Demo values: the mock fixture has no Kalman section.</p>'
    )
    return sec("kalman", "Exposure tracked day by day", e(outcome), main, side, two="xl")


def shrunk_panel(r: dict) -> str:
    """Condensed shrunk-beta panel: measured against adjusted toward typical values. Demo values."""
    g = r["regression"]
    if g["status"] != "ok":
        return ""
    prior = {"Mkt-RF": 1.0, "SMB": 0.15, "HML": 0.05, "RMW": 0.08, "CMA": 0.04}
    tau = 0.12
    rows_d = []
    for f in g["factors"]:
        wgt = f["se"] ** 2 / (f["se"] ** 2 + tau ** 2)
        s = f["beta"] + (prior[f["name"]] - f["beta"]) * wgt
        rows_d.append((f["name"], f["beta"], s, prior[f["name"]], wgt))
    vals = [v for _, o, s, p, _ in rows_d for v in (o, s, p)] + [0.0]
    lo, hi, ticks = nice_domain(min(vals), max(vals), 5)
    rows = []
    biggest = max(abs(s - o) for _, o, s, _, _ in rows_d)
    for n, o, s, p, wgt in rows_d:
        parts = (f'<line class="pull" x1="{pos(o, lo, hi)}%" x2="{pos(s, lo, hi)}%" y1="50%" y2="50%"/>'
                 f'<line class="tick-prior" x1="{pos(p, lo, hi)}%" x2="{pos(p, lo, hi)}%" y1="30%" y2="70%"/>'
                 f'<circle class="dot-ols" cx="{pos(o, lo, hi)}%" cy="50%" r="5"/><circle class="dot-new" cx="{pos(s, lo, hi)}%" cy="50%" r="4"/>')
        cells = (f'<td class="num">{sgn(o)}</td><td class="num strong">{sgn(s)}</td><td class="num">{sgn(s - o)}</td>'
                 f'<td class="num stat">{wgt * 100:.1f}%</td>')
        rows.append(dot_row(PLAIN[n], n, lo, hi, ticks, parts, cells))
    outcome = (f"Pulling the betas toward typical values changes them by at most {num(biggest, 3)}, so the measured betas stand."
               if biggest < 0.02 else f"Pulling toward typical values moves some betas by up to {num(biggest, 2)}; read those with care.")
    main = f"""
  <table class="bars shrunk">
    <caption class="vh">Measured betas against betas pulled toward typical values</caption>
    <thead><tr><th scope="col">Factor</th><th scope="col" class="plot-h"><span class="vh">Chart</span></th>
      <th scope="col" class="num">Measured</th><th scope="col" class="num">Adjusted</th><th scope="col" class="num">Change</th><th scope="col" class="num stat">Pull</th></tr></thead>
    <tbody>{''.join(rows)}</tbody>
    <tfoot>{axis_row(ticks, lo, hi, tick)}</tfoot>
  </table>"""
    side = (
        '<ul class="legend" aria-label="Legend"><li><svg class="sw" aria-hidden="true"><circle class="dot-ols" cx="8" cy="5" r="4.5"/></svg>Measured</li>'
        '<li><svg class="sw" aria-hidden="true"><circle class="dot-new" cx="8" cy="5" r="4"/></svg>Adjusted</li>'
        '<li><svg class="sw" aria-hidden="true"><line class="tick-prior" x1="8" x2="8" y1="0" y2="10"/></svg>Typical value</li></ul>'
        + '<p class="reading">Noisy betas are pulled toward what is typical for US stocks. Precise betas barely move; that is the case here.</p>'
        + how("Descriptive; a check on noise, not a forecast.",
              "Bayesian shrinkage toward a prior from Fama&#8211;French portfolio betas; the pull is the posterior weight on the prior.")
        + '<p class="demo">Demo values: the mock fixture has no shrunk section.</p>'
    )
    return sec("shrunk", "Exposures adjusted for noise", e(outcome), main, side, two="xl")


# ----------------------------------------------------------------------------- data and audit, regression detail
def data_panel(r: dict) -> str:
    d = r["data"]
    rows = [
        ("Requested", f"{d_long(d['requested_start'])} to {d_long(d['requested_end'])}"),
        ("Analysed", f"{d_long(d['actual_start'])} to {d_long(d['actual_end'])}, {d['n_obs']:,} trading days"),
        ("Left out inside the range", plural(d["n_excluded"], "day") + (" (a return spanning several factor days)" if d["excluded_by_reason"].get("multi_day_return") else "")),
        ("After the factor data", plural(d["dropped_price_dates_after_factors"], "price day") + ", charted but not analysed"),
        ("Factor data ends", f"{d_long(d['factors_last_date'])}, {d['factors_days_behind']} days before the report"),
        ("Factor file downloaded", d_long(d["factors_downloaded_at"][:10]) if d["factors_downloaded_at"] else "Injected, not downloaded"),
        ("Prices", d["price_source"]),
        ("Factors", d["factors_source_url"]),
    ]
    dl = "".join(f"<div><dt>{e(a)}</dt><dd>{e(b)}</dd></div>" for a, b in rows)
    sev = {"info": ("neu", "Info"), "warning": ("acc", "Warning"), "error": ("neg", "Error")}
    sev["warning"] = ("warn", "Warning")
    finds = "".join(
        f'<li><span class="pill {sev[f["severity"]][0]}">{sev[f["severity"]][1]}</span><span>{e(f["message"])}'
        + (f' <span class="when">({", ".join(d_long(x) for x in f["dates"])})</span>' if f["dates"] else "") + "</span></li>"
        for f in d["audit_findings"]
    ) or "<li><span>No findings. Prices passed every check.</span></li>"
    notes = "".join(f"<li>{e(n)}</li>" for n in r["notes"]) + f"<li>{e(r['label_text'].get('L-VINTAGE', ''))}</li>"
    nwarn = sum(1 for f in d["audit_findings"] if f["severity"] in ("warning", "error"))
    outcome = (f"{d['n_obs']:,} trading days were analysed; {plural(d['n_excluded'], 'day')} {'was' if d['n_excluded'] == 1 else 'were'} left out "
               f"and the price audit raised {plural(nwarn, 'warning') if nwarn else 'no warnings'}.")
    main = f"""
  <div class="data-grid">
    <div><h3>Coverage</h3><dl class="facts">{dl}</dl></div>
    <div><h3>Audit findings</h3><ul class="findings">{finds}</ul>
      <h3 style="margin-top:24px">Keep in mind</h3><ul class="notes">{notes}</ul></div>
  </div>"""
    return sec("data", "Data and audit", e(outcome), main + how("Audit findings are reported, never acted on: no price is changed or removed because of them."), two=False)


def detail_panel(r: dict) -> str:
    g = r["regression"]
    if g["status"] != "ok":
        return ""
    vif = g["vif"]
    rows = [
        f'<tr class="{"ns" if g["alpha_tag"] != "reliable" else ""}"><th scope="row">Beyond the factors<span class="sub">Alpha, a year</span></th>'
        f'<td>{pct(g["alpha_annual"])}</td><td class="stat">{pct(g["alpha_se_annual"], 2, False)}</td><td class="stat">{tstat(g["alpha_z"])}</td>'
        f'<td class="stat">{pval(g["alpha_p"])}</td><td class="stat">single test</td>'
        f'<td class="stat">{pct(g["alpha_ci_low_annual"])} to {pct(g["alpha_ci_high_annual"])}</td><td class="stat">&#8211;</td>'
        f'{word_cell(g["alpha_tag"] == "reliable")}</tr>'
    ]
    for f in g["factors"]:
        ok = f["tag"] == "reliable"
        rows.append(
            f'<tr id="d-{f["name"]}" class="{"" if ok else "ns"}"><th scope="row">{PLAIN[f["name"]]}<span class="sub">{e(f["name"])}</span></th>'
            f'<td>{sgn(f["beta"])}</td><td class="stat">{num(f["se"], 4)}</td><td class="stat">{tstat(f["z"])}</td>'
            f'<td class="stat">{pval(f["p"])}</td><td class="stat">{pval(f["p_adj_bh"])}</td>'
            f'<td class="stat">{sgn(f["ci_low"])} to {sgn(f["ci_high"])}</td><td class="stat">{vif.get(f["name"], 0):.2f}</td>{word_cell(ok)}</tr>'
        )
    clear = [PLAIN[f["name"]] if k == 0 else PLAIN[f["name"]].lower()
             for k, f in enumerate(x for x in g["factors"] if x["tag"] == "reliable")]
    noise = [PLAIN[f["name"]].lower() for f in g["factors"] if f["tag"] != "reliable"]
    outcome = (f"{and_list(clear)} {'are' if len(clear) > 1 else 'is'} statistically clear; "
               f"{and_list(noise + (['the return beyond the factors'] if g['alpha_tag'] != 'reliable' else []))} could be noise.")
    five = r.get("five_day_regression") or {}
    five_line = ""
    if five.get("status") == "ok":
        five_line = (f'<p class="foot stat">Five-day check: {five["n_blocks"]} blocks of 5 days give alpha {pct(five["alpha_annual"])} a year '
                     f'(p {pval(five["alpha_p"])}) and R&#178; {five["r2"]:.4f}; the betas agree with the daily fit.</p>')
    main = f"""
  <p class="plain-only reading">Turn on <b>Show statistics</b> in the sidebar to see standard errors, t-statistics, p-values, intervals and VIF.</p>
  <div class="scroll-x" tabindex="0" role="region" aria-label="Regression detail table">
  <table class="tbl reg"><caption class="vh">Regression estimates and evidence for each term</caption>
    <thead><tr><th scope="col">Term</th><th scope="col">Estimate</th><th scope="col" class="stat">Std. error</th><th scope="col" class="stat">t</th>
    <th scope="col" class="stat">p</th><th scope="col" class="stat">p, adjusted</th><th scope="col" class="stat">95% interval</th><th scope="col" class="stat">VIF</th><th scope="col">How sure</th></tr></thead>
    <tbody>{''.join(rows)}</tbody></table></div>
  <p class="foot stat">R&#178; {g['r2']:.4f}, adjusted {g['adj_r2']:.4f}. Residual volatility {pct(g['sigma_e_annual'], 2, False)} a year. Newey&#8211;West lags {g['hac_lags']}. Condition number {g['condition_number']:.2f}.</p>
  {five_line}"""
    return sec("detail", "Regression detail", e(outcome), main, two=False)


# ----------------------------------------------------------------------------- page
def font_face() -> str:
    b64 = base64.b64encode((FONTS / "ibm-plex-sans.woff2").read_bytes()).decode("ascii")
    return ("@font-face{font-family:'IBM Plex Sans';font-style:normal;font-weight:400 700;font-display:block;"
            f"src:url(data:font/woff2;base64,{b64}) format('woff2')}}\n")


def add_roles(body: str) -> str:
    """Explicit table roles: narrow screens restyle bar-table rows as grids."""
    def fix(m: re.Match[str]) -> str:
        t = m.group(0).replace('<table class="bars', '<table role="table" class="bars')
        t = re.sub(r"<tr(?=[ >])", '<tr role="row"', t)
        t = t.replace('<th scope="row"', '<th role="rowheader" scope="row"').replace('<th scope="col"', '<th role="columnheader" scope="col"')
        t = re.sub(r"<td(?=[ >])", '<td role="cell"', t)
        t = re.sub(r"<(thead|tbody|tfoot)>", lambda g: f'<{g.group(1)} role="rowgroup">', t)
        cap = re.search(r'<caption class="vh">(.*?)</caption>', t)
        label = cap.group(1) if cap else "Table"
        return f'<div class="tbl-wrap" role="region" tabindex="0" aria-label="{label}">{t}</div>'
    return re.sub(r'<table class="bars.*?</table>', fix, body, flags=re.S)


def gen_stamp(r: dict) -> str:
    g = datetime.fromisoformat(r["generated_at"].replace("Z", "+00:00"))
    return f"{g.day} {g.strftime('%b %Y, %H:%M')} UTC"


def page(r: dict, on: set[str]) -> str:
    nwarn = len(r["data"]["audit_findings"])
    nav = [
        ("summary", "Summary", ""), ("drivers", "What drives it", ""), ("world", "World beta", ""),
        ("price", "Price", ""), ("performance", "Performance", ""), ("exposures", "Factor exposures", ""),
        ("returns", "Return sources", ""), ("risk", "Risk sources", ""),
        ("rolling", "Exposure over time", ""), ("residual", "Beyond the factors", ""),
        ("kalman", "Tracked day by day", ""), ("shrunk", "Adjusted for noise", ""),
        ("data", "Data and audit", f"{nwarn} findings" if nwarn else ""), ("detail", "Regression detail", ""),
    ]
    hatch = ('<svg class="defs" width="0" height="0" aria-hidden="true" focusable="false"><defs>'
             '<pattern id="hatch" patternUnits="userSpaceOnUse" width="5" height="5" patternTransform="rotate(45)">'
             '<rect class="hatch-bg" width="5" height="5"/><rect class="hatch-ink" width="1.6" height="5"/></pattern></defs></svg>')
    main = "\n".join([
        f'<section id="summary" aria-label="Summary">{header(r)}{verdict(r)}{notice(r)}{performance_strip(r)}</section>',
        drivers(r), world_panel(r), price_panel(r), performance_panel(r), exposures_panel(r), return_panel(r),
        risk_panel(r), rolling_panel(r, "win126" in on), residual_panel(r), kalman_panel(r), shrunk_panel(r),
        data_panel(r), detail_panel(r),
        f'<footer class="colophon"><p>factordesk report, schema v{e(str(r["schema_version"]))}, generated {gen_stamp(r)}. '
        "Descriptive statistics on past data; nothing here is a forecast or advice.</p></footer>",
    ])
    body = add_roles(f"""<a class="skip" href="#summary">Skip to the report</a>
{hatch}
<input class="vh" type="checkbox" id="nav-open" aria-controls="sidebar" aria-label="Menu">
{topbar(r)}
{sidebar(r, nav)}
<div class="canvas"><main id="main">{main}</main></div>""")
    for key, el in (("dark", "sw-dark"), ("stats", "sw-stats"), ("menu", "nav-open")):
        if key in on:
            body = body.replace(f'id="{el}"', f'id="{el}" checked', 1)
    sec_name = SECURITY.get(r["ticker"], {}).get("name", "")
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light dark">
<meta name="theme-color" content="#141A33">
<title>{e(r['ticker'])} factor profile{f" - {e(sec_name)}" if sec_name else ""}</title>
<style>
{font_face()}
{CSS}
</style>
</head>
<body>
{body}
</body>
</html>
"""


def main() -> None:
    args = sys.argv[1:]
    r = json.loads(FIXTURE.read_text(encoding="utf-8"))
    empty = "--empty" in args
    on = set(args[args.index("--on") + 1].split(",")) if "--on" in args else set()
    if empty:
        r = make_empty(r)
    out = Path(args[args.index("--out") + 1]) if "--out" in args else HERE / ("report-v3-empty.html" if empty else "report-v3.html")
    out.write_text(page(r, on), encoding="utf-8", newline="\n")
    print(f"wrote {out} ({out.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
