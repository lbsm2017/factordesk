"""Generator for the dashboard visual target, rev 4: two variants from one generator.

    a  Tearsheet:          compact title row with a type badge, an analysis bar, then a Summary
                           panel (verdict sentence, key metrics table beside the price chart).
    b  Compact dashboard:  a one-line summary bar, a strip of six key figures, then two-up panels.

Both share report-v4.css, the sidebar, the panel and table vocabulary and every section below the
summary; only the summary and the order of the panels differ. Reads the mock fixture (JSON only)
and writes self-contained HTML next to this file. Standard library only; the plain-language rules,
demo values and computation helpers are imported from the rev 3 and rev 2 generators, which stay
unchanged.

    python docs/design/prototype/build_prototype_v4.py                    # report-v4a.html and report-v4b.html
    python docs/design/prototype/build_prototype_v4.py --variant a        # one variant
    python docs/design/prototype/build_prototype_v4.py --variant b --on stats,menu --out PATH
"""

from __future__ import annotations

import html
import json
import math
import sys
from pathlib import Path

import build_prototype_v3 as v3
from build_prototype import FACTORS, MINUS, PLAIN, SLOT, WARN_PLAIN, _quantile, d_long, edge, nice_domain, num, path_xy, pct, pos, pval, sgn, tstat

HERE = Path(__file__).resolve().parent
FIXTURE = v3.FIXTURE
CSS = (HERE / "report-v4.css").read_text(encoding="utf-8")
e = html.escape

SECURITY = v3.SECURITY
TYPE = {"SPY": "ETF", "ZM": "Equity"}  # demo values; the schema has no security type yet
CURRENCY_PLAIN = v3.CURRENCY_PLAIN
PERFORMANCE, WORLD = v3.PERFORMANCE, v3.WORLD
NOTE_SHORT = {
    "residual_reversal": "Daily prices partly reverse the next day, so R² is probably understated.",
    "short_history": "Short history: the betas rest on a small sample.",
    "audit_errors": "The price audit found errors; read Data and audit first.",
}

# column header tooltips: the explanations live here, not under every number
TIP = {
    "value": "Over the analysed range",
    "reading": "Clear evidence: the 95% interval excludes zero after correcting for testing five betas at once. Could be noise: it does not.",
    "t": "t-statistic with Newey-West standard errors",
    "ci": "95% confidence interval",
    "ret": "Compound growth rate a year, dividends reinvested, before costs and taxes",
    "vol": "Standard deviation of daily returns, scaled to a year",
    "sharpe": "Average return above the risk-free rate divided by volatility, a year",
    "mdd": "Largest fall from a previous high, close to close",
    "alpha": "Return a year that the five factor exposures do not explain",
    "r2": "Share of daily moves explained by the five factors",
    "resid": "Volatility a year of the part of returns the factors do not explain",
    "bmkt": "Exposure to the US stock market factor (Fama-French Mkt-RF), from the five-factor model",
    "bacwi": "Exposure to the ACWI ETF, used as a stand-in for the MSCI ACWI index; one-factor estimate, demo value",
    "beta": "Sensitivity to the factor: +1 means a one-for-one move",
    "padj": "p-value adjusted for testing five betas at once (Benjamini-Hochberg)",
    "avg": "Mean of the rolling 252-day betas",
    "meaning": "Which way the exposure leans, in plain words",
}


# ----------------------------------------------------------------------------- small pieces
ICON = {**v3.ICON, "info": '<circle cx="10" cy="10" r="7"/><path d="M10 9v5M10 6.3v.2"/>'}


def icon(name: str) -> str:
    return f'<svg class="icon" viewBox="0 0 20 20" aria-hidden="true">{ICON[name]}</svg>'


def th(label: str, tip: str = "", cls: str = "") -> str:
    t = f' title="{e(TIP.get(tip, tip))}"' if tip else ""
    c = f' class="{cls}"' if cls else ""
    return f'<th scope="col"{c}{t}>{label}</th>'


def reading(ok: bool | None, yes: str = "Clear evidence", no: str = "Could be noise") -> str:
    if ok is None:
        return '<td class="rd na" title="No test applies">&#8211;</td>'
    return f'<td class="rd {"yes" if ok else "no"}">{yes if ok else no}</td>'


def how(text: str) -> str:
    return f'<details class="how"><summary>How this is computed</summary><p>{text}</p></details>'


def panel(pid: str, title: str, body: str, meta: str = "", take: str = "", span: str = "", foot: str = "") -> str:
    m = f'<div class="pm">{meta}</div>' if meta else ""
    t = f'<p class="take">{take}</p>' if take else ""
    return (f'<section class="panel {span}" id="{pid}" aria-labelledby="{pid}-t">'
            f'<header class="ph"><h2 id="{pid}-t">{e(title)}</h2>{m}</header>{t}{body}{foot}</section>')


def gridlines_v(ticks: list[float], lo: float, hi: float) -> str:
    return "".join(f'<line class="{"z" if abs(t) < 1e-12 else "gl"}" x1="{pos(t, lo, hi)}%" x2="{pos(t, lo, hi)}%" y1="-4" y2="24"/>' for t in ticks)


def hbar(v: float, lo: float, hi: float, cls: str = "b") -> str:
    a, b = sorted((pos(0.0, lo, hi), pos(v, lo, hi)))
    return f'<rect class="{cls}" x="{a}%" y="4" width="{max(b - a, 0.3)}%" height="12" rx="2"/>'


def whisker(l: float, h: float, lo: float, hi: float) -> str:
    x1, x2 = pos(l, lo, hi), pos(h, lo, hi)
    out = f'<line class="ci" x1="{x1}%" x2="{x2}%" y1="10" y2="10"/>'
    if x2 - x1 > 1.2:
        out += f'<line class="ci" x1="{x1}%" x2="{x1}%" y1="6" y2="14"/><line class="ci" x1="{x2}%" x2="{x2}%" y1="6" y2="14"/>'
    return out


def bsvg(inner: str, ticks: list[float], lo: float, hi: float, tip: str = "") -> str:
    t = f"<title>{e(tip)}</title>" if tip else ""
    return f'<td class="bc"><svg class="bsvg" aria-hidden="true">{t}{gridlines_v(ticks, lo, hi)}{inner}</svg></td>'


def tick(t: float) -> str:
    if abs(t) < 1e-12:
        return "0"
    s = f"{abs(t):.2f}".rstrip("0").rstrip(".")
    return ("+" if t > 0 else MINUS) + s


def axis_row(ticks: list[float], lo: float, hi: float, fmt=tick) -> str:
    kept = [t for t in ticks if abs(t) < 1e-12]
    for t in sorted((t for t in ticks if 3 <= pos(t, lo, hi) <= 97), key=abs):
        if all(abs(pos(t, lo, hi) - pos(k, lo, hi)) >= 30 for k in kept):
            kept.append(t)
    labels = "".join(f'<span class="{edge(pos(t, lo, hi))}" style="left:{pos(t, lo, hi)}%">{fmt(t)}</span>' for t in sorted(kept))
    return f'<tfoot><tr class="axis" aria-hidden="true"><td></td><td class="ax bc"><div>{labels}</div></td></tr></tfoot>'


def fname(n: str) -> str:
    return f'{PLAIN[n]}<span class="code">{e(n)}</span>'


def time_labels(dates: list[str], X, lo_i: int = 0, gap: float = 14.0) -> str:
    return v3.time_labels([t for t in v3.date_ticks(dates) if t[0] >= lo_i], X, gap)


def chart(svg: str, ylabels: str, xlabels: str, extra: str = "", style: str = "") -> str:
    st = f' style="{style}"' if style else ""
    return (f'<div class="chart"{st}><svg class="csvg" viewBox="0 0 1000 100" preserveAspectRatio="none" aria-hidden="true">{svg}</svg>'
            f'<div class="yls" aria-hidden="true">{ylabels}</div><div class="xls" aria-hidden="true">{xlabels}</div>{extra}</div>')


def share(x: float) -> str:
    return v3.share(x)


# ----------------------------------------------------------------------------- derived values
def cut_index(r: dict) -> int:
    p = r["price_series"]
    return max((i for i, s in enumerate(p["dates"]) if s <= p["factor_coverage_end"]), default=len(p["dates"]) - 1)


def r2_word(r2: float) -> str:
    return "Very high" if r2 >= 0.9 else "High" if r2 >= 0.6 else "Moderate" if r2 >= 0.3 else "Low"


def resid_word(idio: float) -> str:
    return "Low" if idio < 0.1 else "Moderate" if idio < 0.4 else "High"


def metrics(r: dict) -> dict:
    """Every number the summary needs, keyed once so both variants read the same values."""
    g, rk, d = r["regression"], r["risk_contribution"], r["data"]
    p = PERFORMANCE[r["ticker"]]
    w = WORLD[r["ticker"]]
    fs = {f["name"]: f for f in g["factors"]}
    mk = fs["Mkt-RF"]
    slo, shi = v3.sharpe_interval(p["sharpe"], p["years"])
    idio = rk["idiosyncratic"]
    rec = p["recovered"]
    return {
        "ret": p["ret"], "vol": p["vol"], "sharpe": p["sharpe"], "s_lo": slo, "s_hi": shi, "s_ok": slo > 0,
        "mdd": p["mdd"], "peak": p["peak"], "trough": p["trough"], "rec": rec,
        "alpha": g["alpha_annual"], "a_t": g["alpha_z"], "a_lo": g["alpha_ci_low_annual"], "a_hi": g["alpha_ci_high_annual"],
        "a_ok": g["alpha_tag"] == "reliable", "r2": g["r2"], "adj_r2": g["adj_r2"], "resid": g["sigma_e_annual"], "idio": idio,
        "bm": mk["beta"], "bm_t": mk["z"], "bm_lo": mk["ci_low"], "bm_hi": mk["ci_high"], "bm_ok": mk["tag"] == "reliable",
        "bw": w["acwi"][0], "bw_lo": w["acwi"][1], "bw_hi": w["acwi"][2], "bw_ok": w["acwi"][1] > 0 or w["acwi"][2] < 0,
        "bw_t": w["acwi"][0] / ((w["acwi"][2] - w["acwi"][1]) / (2 * 1.96)),
        "n": d["n_obs"], "start": d["actual_start"], "end": d["actual_end"],
    }


def dd_text(m: dict) -> str:
    rec = f"recovered {d_long(m['rec'])}" if m["rec"] else "not yet recovered"
    return f"Peak {d_long(m['peak'])}, low {d_long(m['trough'])}, {rec}"


# ----------------------------------------------------------------------------- sidebar and top bar
NAV = [
    ("summary", "Summary"), ("performance", "Drawdown"), ("price", "Price"), ("exposures", "Factor exposures"),
    ("world", "World beta"), ("returns", "Return sources"), ("risk", "Risk sources"), ("rolling", "Exposure over time"),
    ("residual", "Beyond the factors"), ("kalman", "Tracked day by day"), ("shrunk", "Adjusted for noise"),
    ("data", "Data and audit"), ("detail", "Regression detail"),
]
NAV_ICON = {"summary": "summary", "performance": "performance", "price": "price", "exposures": "exposures", "world": "world",
            "returns": "returns", "risk": "risk", "rolling": "rolling", "residual": "residual", "kalman": "kalman",
            "shrunk": "shrunk", "data": "data", "detail": "detail"}


def sidebar(r: dict, order: list[str]) -> str:
    d = r["data"]
    history = v3.HISTORY_YEARS.get(r["ticker"], 50.0)
    ranges = [("3Y", 3), ("5Y", 5), ("10Y", 10), ("Full history", 0)]
    seg = "".join(
        f'<label><input type="radio" name="range" value="{k}"{" checked" if k == "Full history" else ""}'
        f'{" disabled" if y and y > history else ""}><span>{k}</span></label>' for k, y in ranges
    )
    labels = dict(NAV)
    items = []
    for sid in order:
        if sid == "residual":
            items.append('<li class="nav-sub" aria-hidden="true">Deeper checks</li>')
        cur = ' aria-current="true"' if sid == "summary" else ""
        items.append(f'<li><a href="#{sid}"{cur}>{icon(NAV_ICON[sid])}<span>{e(labels[sid])}</span></a></li>')
    excl = d["n_excluded"]
    return f"""
<aside class="side" id="sidebar" aria-label="Controls and sections">
  <div class="side-scroll">
    <div class="side-top"><a class="mark" href="#summary">{v3.MARK}<span translate="no">factordesk</span></a>
      <label class="drawer-close" for="nav-open">{icon("close")}<span class="vh">Close menu</span></label></div>
    <form class="side-group" role="search" onsubmit="return false">
      <label class="side-label" for="tk">Ticker</label>
      <div class="search"><input class="field" id="tk" name="ticker" type="text" value="{e(r['ticker'])}" placeholder="e.g. AAPL" autocomplete="off" autocapitalize="characters" spellcheck="false" translate="no">
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
      <p class="side-note">Factor data <b>to {d_long(d['factors_last_date'])}</b>, {d['factors_days_behind']} days old</p>
      <button class="linkbtn" type="button">{icon("refresh")}Check for newer data</button>
    </div>
    <div class="side-group">
      <label class="switch"><input type="checkbox" role="switch" id="sw-stats"><span class="track"><span class="thumb"></span></span>
        <span class="switch-text">Show statistics<span class="sw-hint">t, p-values, intervals</span></span></label>
    </div>
    <nav class="side-group nav" aria-label="Sections">
      <ol>{''.join(items)}</ol>
    </nav>
  </div>
</aside>"""


def topbar(r: dict) -> str:
    return f"""
<header class="topbar">
  <label class="menu-btn" for="nav-open">{icon("menu")}<span class="vh">Open menu</span></label>
  <a class="mark" href="#summary">{v3.MARK}<span translate="no">factordesk</span></a>
  <p class="where"><b>{e(r['ticker'])}</b></p>
</header>
<label class="scrim" for="nav-open" aria-hidden="true"></label>"""


# ----------------------------------------------------------------------------- page header (both variants)
def page_head(r: dict, listing_extra: str = "") -> str:
    s = SECURITY.get(r["ticker"], {})
    cur = CURRENCY_PLAIN.get(s.get("currency", ""), s.get("currency", ""))
    name = f'<span class="nm" translate="no">{e(s["name"])}</span>' if s.get("name") else ""
    badge = f'<span class="badge" title="Security type">{e(TYPE[r["ticker"]])}</span>' if r["ticker"] in TYPE else ""
    listing = f"Listed on {e(s.get('exchange', ''))}, priced in {e(cur)}{listing_extra}"
    return f"""
<header class="page-head">
  <h1><span class="tk" translate="no">{e(r['ticker'])}</span>{name}</h1>{badge}
  <div class="head-actions"><a class="btn quiet" href="#" download="{e(r['ticker'])}-factor-report.html">{icon("download")}Download report</a></div>
  <p class="listing">{listing}</p>
</header>"""


def notes_line(r: dict, short: bool = False) -> str:
    ws = r["warnings"]
    if not ws:
        return ""
    src = NOTE_SHORT if short else v3.NOTICE_PLAIN
    txt = " ".join(e(src.get(w["code"], WARN_PLAIN.get(w["code"], w["message"]))) for w in ws[:2])
    n = len(ws)
    return (f'<p class="notes-line" role="note">{icon("warn")}<span><b>{n} data note{"s" if n > 1 else ""}:</b> {txt} '
            f'<a href="#data">Details</a></span></p>')


# ----------------------------------------------------------------------------- variant a: analysis bar + summary
def analysis_bar(r: dict) -> str:
    d = r["data"]
    return f"""
<dl class="abar" aria-label="Analysis settings">
  <div><dt>Analysis period</dt><dd>{d_long(d['actual_start'])} to {d_long(d['actual_end'])}</dd></div>
  <div><dt>Observations</dt><dd>{d['n_obs']:,} trading days</dd></div>
  <div><dt>Factor data</dt><dd>To {d_long(d['factors_last_date'])}</dd></div>
  <div><dt>Benchmark</dt><dd title="ACWI ETF, a stand-in for the MSCI ACWI index" class="tip">ACWI</dd></div>
</dl>"""


def kv_row(label: str, tip: str, value: str, read: str, t: str = "", ci: str = "", vcls: str = "") -> str:
    na = '<span class="na">&#8211;</span>'
    return (f'<tr><th scope="row"><span class="tip" title="{e(TIP[tip])}">{label}</span></th>'
            f'<td class="num v{" " + vcls if vcls else ""}">{value}</td>{read}'
            f'<td class="num stat">{t or na}</td><td class="num stat">{ci or na}</td></tr>')


def key_metrics_table(r: dict) -> str:
    m = metrics(r)
    rec_read = (f'<td class="rd ok" title="{e(dd_text(m))}">Recovered</td>' if m["rec"]
                else f'<td class="rd bad" title="{e(dd_text(m))}">Not recovered</td>')
    word = lambda s: f'<td class="rd no">{s}</td>'  # noqa: E731
    rows = [
        '<tr class="grp"><th scope="rowgroup" colspan="5">Performance</th></tr>',
        kv_row("Annualised return", "ret", pct(m["ret"], 1), reading(None)),
        kv_row("Volatility", "vol", pct(m["vol"], 1, False), reading(None)),
        kv_row("Sharpe ratio", "sharpe", num(m["sharpe"], 2), reading(m["s_ok"]), "", f"{num(m['s_lo'], 2)} to {num(m['s_hi'], 2)}"),
        kv_row("Max drawdown", "mdd", pct(m["mdd"], 1), rec_read, vcls="neg-v"),
        '<tr class="grp"><th scope="rowgroup" colspan="5">Factor model</th></tr>',
        kv_row("Alpha (annual)", "alpha", pct(m["alpha"]), reading(m["a_ok"]), tstat(m["a_t"]), f"{pct(m['a_lo'], 1)} to {pct(m['a_hi'], 1)}"),
        kv_row("R&#178;", "r2", share(m["r2"]), word(r2_word(m["r2"]))),
        kv_row("Residual volatility", "resid", pct(m["resid"], 1, False), word(resid_word(m["idio"]))),
        kv_row("Beta to US market", "bmkt", num(m["bm"], 2), reading(m["bm_ok"]), tstat(m["bm_t"]), f"{num(m['bm_lo'], 2)} to {num(m['bm_hi'], 2)}"),
        kv_row("Beta to ACWI", "bacwi", num(m["bw"], 2), reading(m["bw_ok"]), tstat(m["bw_t"]), f"{num(m['bw_lo'], 2)} to {num(m['bw_hi'], 2)}"),
    ]
    return f"""
<div class="tw"><table class="tbl kv">
  <caption class="vh">Key metrics over the analysed range</caption>
  <thead><tr>{th("Metric")}{th("Value", "value", "num")}{th("Reading", "reading")}{th("t", "t", "num stat")}{th("95% interval", "ci", "num stat")}</tr></thead>
  <tbody>{''.join(rows)}</tbody>
</table></div>
<p class="tnote">Annualised from daily data. ACWI is an ETF used as a stand-in for the MSCI ACWI index. Performance and ACWI figures are demo values.</p>"""


def price_chart(r: dict, shade_analysed: bool) -> tuple[str, str]:
    """(chart html, one-line note). Variant a shades the analysed window; b shades nothing and greys the tail."""
    p, d = r["price_series"], r["data"]
    dates, px = p["dates"], p["adj_close"]
    pts = [(i, v) for i, v in enumerate(px) if v is not None]
    cut = cut_index(r)
    lo, hi, ticks = nice_domain(min(v for _, v in pts), max(v for _, v in pts), 4)
    n = len(dates) - 1
    X = lambda i: i / n * 1000  # noqa: E731
    Y = lambda v: 100 - (v - lo) / (hi - lo) * 100  # noqa: E731
    i0 = next((i for i, s in enumerate(dates) if s >= d["actual_start"]), 0)
    grid = "".join(f'<line class="gl" x1="0" x2="1000" y1="{Y(t):.2f}" y2="{Y(t):.2f}"/>' for t in ticks)
    shade = f'<rect class="an" x="{X(i0):.1f}" y="0" width="{X(cut) - X(i0):.1f}" height="100"/>' if shade_analysed else ""
    cutl = f'<line class="cut" x1="{X(cut):.1f}" x2="{X(cut):.1f}" y1="0" y2="100"/>' if cut < n else ""
    main = [(X(i), Y(v)) for i, v in pts if i <= cut]
    tail = [(X(i), Y(v)) for i, v in pts if i >= cut]
    svg = (f"{shade}{grid}{cutl}<path class=\"px\" d=\"{path_xy(*zip(*main))}\"/>"
           + (f'<path class="px-tail" d="{path_xy(*zip(*tail))}"/>' if len(tail) > 1 else ""))
    ylab = "".join(f'<span style="top:{Y(t):.2f}%">{t:,.0f}</span>' for t in ticks)
    xlab = time_labels(dates, lambda i: X(i) / 10)
    first, at_cut = pts[0][1], px[cut]
    chg = at_cut / first - 1
    u = d["uncovered"]
    note = (f"{'Up' if chg >= 0 else 'Down'} {pct(abs(chg), 1, False)} over the analysed window."
            + (f" The last {u['n']} trading days are charted but not analysed." if u["n"] else ""))
    return chart(svg, ylab, xlab), note


def price_key(shade: bool) -> str:
    an = '<li><svg class="sw" aria-hidden="true"><rect class="an" width="14" height="10"/></svg>Analysed window</li>' if shade else ""
    return (f'<ul class="key" aria-label="Legend"><li><svg class="sw" aria-hidden="true"><line class="ln" x1="0" x2="14" y1="5" y2="5"/></svg>Adjusted close, USD</li>{an}'
            '<li><svg class="sw" aria-hidden="true"><line class="cut" x1="7" x2="7" y1="0" y2="10" style="stroke:var(--accent);stroke-dasharray:2 2"/></svg>End of factor data</li></ul>')


def summary_a(r: dict) -> str:
    d = r["data"]
    ch, note = price_chart(r, True)
    body = f"""
<p class="verdict">{e(v3.verdict_sentence(r))}</p>
{notes_line(r)}
<div class="sum-grid">
  <div><h3>Key metrics</h3>{key_metrics_table(r)}</div>
  <figure class="sum-chart" id="price" aria-labelledby="price-t">
    <div class="chart-head"><h3 id="price-t">Price</h3>{price_key(True)}</div>
    {ch}
    <figcaption class="chart-note">{e(note)}</figcaption>
  </figure>
</div>"""
    return panel("summary", "Summary", body, meta=f"{d_long(d['actual_start'])} to {d_long(d['actual_end'])}. Past data, not a forecast.")


# ----------------------------------------------------------------------------- variant b: summary bar + KPI strip + price panel
def summary_bar(r: dict) -> str:
    return f"""
<section class="sumbar" id="summary" aria-label="Summary">
  <p class="verdict">{e(v3.verdict_sentence(r))}</p>
  {notes_line(r, short=True)}
</section>"""


def kpi(label: str, tip: str, value: str, sub: str = "", sub_cls: str = "", stat: str = "", vcls: str = "") -> str:
    s = f'<dd class="ks {sub_cls}">{sub}</dd>' if sub else ""
    st = f'<dd class="stat">{stat}</dd>' if stat else ""
    return (f'<div class="kpi"><dt><span class="tip" title="{e(TIP[tip])}">{label}</span></dt>'
            f'<dd class="kv{" " + vcls if vcls else ""}">{value}</dd>{s}{st}</div>')


def kpi_strip(r: dict) -> str:
    m = metrics(r)
    yes = lambda ok: ("Clear evidence", "rd yes") if ok else ("Could be noise", "rd no")  # noqa: E731
    s_w, s_c = yes(m["s_ok"])
    a_w, a_c = yes(m["a_ok"])
    cells = [
        kpi("Annualised return", "ret", pct(m["ret"], 1), "Dividends reinvested"),
        kpi("Volatility", "vol", pct(m["vol"], 1, False), f"Residual {pct(m['resid'], 1, False)}"),
        kpi("Sharpe ratio", "sharpe", num(m["sharpe"], 2), s_w, s_c, f"95% {num(m['s_lo'], 2)} to {num(m['s_hi'], 2)}"),
        kpi("Max drawdown", "mdd", pct(m["mdd"], 1), f"Recovered {d_long(m['rec'])}" if m["rec"] else "Not recovered",
            "rd ok" if m["rec"] else "rd bad", vcls="neg-v"),
        kpi("Alpha (annual)", "alpha", pct(m["alpha"]), a_w, a_c, f"t {tstat(m['a_t'])}<br>95% {pct(m['a_lo'], 1)} to {pct(m['a_hi'], 1)}"),
        kpi("R&#178;", "r2", share(m["r2"]), f"Beta to market {num(m['bm'], 2)}", "", f"Adjusted {m['adj_r2']:.4f}"),
    ]
    return f'<dl class="kpis" aria-label="Key figures">{"".join(cells)}</dl>'


def price_panel_b(r: dict, span: str) -> str:
    p, d = r["price_series"], r["data"]
    dates, px = p["dates"], p["adj_close"]
    ch, note = price_chart(r, True)
    cut = cut_index(r)
    pts = [(i, v) for i, v in enumerate(px) if v is not None]
    u = d["uncovered"]
    rows = [
        ("First", d_long(dates[pts[0][0]]), f"{pts[0][1]:,.2f}"),
        ("End of factor data", d_long(dates[cut]), f"{px[cut]:,.2f}"),
        ("Latest", d_long(dates[pts[-1][0]]), f"{pts[-1][1]:,.2f}"),
    ]
    body_rows = "".join(f'<tr><th scope="row">{a}</th><td>{b}</td><td class="num v">{c}</td></tr>' for a, b, c in rows)
    if u["n"] and u["compounded_return"] is not None:
        body_rows += f'<tr><th scope="row">After factor data</th><td>{u["n"]} days, not analysed</td><td class="num">{pct(u["compounded_return"], 1)}</td></tr>'
    tbl = (f'<div class="tw"><table class="tbl pts"><caption class="vh">Price points</caption><thead><tr>{th("Point")}{th("Date")}'
           f'{th("Close, USD", "", "num")}</tr></thead><tbody>{body_rows}</tbody></table></div>')
    body = f'<div class="chart-head">{price_key(True)}</div>{ch}{tbl}'
    return panel("price", "Price", body, meta="Adjusted close", take=e(note), span=span,
                 foot=how(f"Adjusted close from {e(d['price_source'])}, for context only; no statistic uses the price line."))


# ----------------------------------------------------------------------------- drawdown (both variants)
def drawdown_parts(r: dict) -> tuple[str, str, str]:
    perf = PERFORMANCE[r["ticker"]]
    p = r["price_series"]
    dates, px = p["dates"], p["adj_close"]
    cut = cut_index(r)
    raw = v3.drawdown_series(px, cut)
    worst = min(x for x in raw if x is not None)
    k = perf["mdd"] / worst if worst < 0 else 1.0  # demo: scale the mock shape to the keyed depth
    dd = [None if x is None else max(x * k, -0.99) for x in raw]
    eps = v3.episodes(dd, dates[: cut + 1])[:3]
    lo, _, ticks = nice_domain(min(x for x in dd if x is not None), 0.0, 4)
    ticks = [t for t in ticks if t <= 1e-12]
    X = lambda i: i / max(cut, 1) * 1000  # noqa: E731
    Y = lambda v: v / lo * 100  # noqa: E731
    pts = [(X(i), Y(x)) for i, x in enumerate(dd) if x is not None]
    area = "M0,0 L" + " L".join(f"{x:.1f},{y:.1f}" for x, y in pts) + f" L{pts[-1][0]:.1f},0Z"
    grid = "".join(f'<line class="gl" x1="0" x2="1000" y1="{Y(t):.2f}" y2="{Y(t):.2f}"/>' for t in ticks if t < 0)
    svg = f'{grid}<path class="dd-a" d="{area}"/><path class="dd-l" d="{path_xy(*zip(*pts))}"/><line class="z" x1="0" x2="1000" y1="0" y2="0"/>'
    ylab = "".join(f'<span style="top:{Y(t):.2f}%">{pct(t, 0) if t else "0%"}</span>' for t in ticks)
    xlab = time_labels(dates[: cut + 1], lambda i: X(i) / 10)
    ch = chart(svg, ylab, xlab)
    rows = "".join(
        f'<tr><td class="num v neg-v">{pct(z["depth"], 1)}</td><td>{d_long(z["peak_d"])}</td><td class="hide-s">{d_long(z["trough_d"])}</td>'
        f'<td>{d_long(z["rec_d"]) if z["rec_d"] else "Not yet"}</td>'
        f'<td class="num hide-s">{(z["rec"] if z["rec"] is not None else cut) - max(z["peak"], 0)}</td></tr>'
        for z in eps
    )
    tbl = (f'<div class="tw"><table class="tbl dd"><caption class="vh">The three largest falls from a peak</caption>'
           f'<thead><tr>{th("Fall", "mdd", "num")}{th("Peak")}{th("Low", "", "hide-s")}{th("Recovered")}{th("Days", "Trading days from peak to recovery, or to the end of the data", "num hide-s")}</tr></thead>'
           f'<tbody>{rows}</tbody></table></div>')
    m = metrics(r)
    meta = f"Max drawdown {pct(m['mdd'], 1)}"
    return ch, tbl, meta


DD_HOW = how("Each day's distance below the highest adjusted close so far, over the analysed range. Return a year is the compound "
             "growth rate; volatility is the standard deviation of daily returns times the square root of 252; the Sharpe ratio is "
             "the average excess return over the risk-free rate divided by volatility, and its interval uses the Lo (2002) approximation. "
             "Demo values: the fixture has no performance block yet; the chart reuses the mock price shape.")


def drawdown_panel(r: dict, span: str, split: bool) -> str:
    ch, tbl, meta = drawdown_parts(r)
    m = metrics(r)
    take = e(dd_text(m) + ".")
    if split:
        body = f'<div class="split c84"><div>{ch}</div><div><h3>Largest falls</h3>{tbl}</div></div>'
    else:
        body = f'{ch}<h3>Largest falls</h3>{tbl}'
    return panel("performance", "Drawdown", body, meta=meta, take=take, span=span, foot=DD_HOW)


# ----------------------------------------------------------------------------- factor exposures
def exposures_panel(r: dict, span: str) -> str:
    g, ab = r["regression"], r["average_beta"]
    avg = {f["name"]: f["mean"] for f in ab["factors"]} if ab["status"] == "ok" else {}
    vals = [v for f in g["factors"] for v in (f["ci_low"], f["ci_high"], f["beta"])] + [0.0]
    lo, hi, ticks = nice_domain(min(vals), max(vals), 5)
    rows = []
    for f in g["factors"]:
        ok, b = f["tag"] == "reliable", f["beta"]
        inner = hbar(b, lo, hi, "b" if ok else "b ns") + whisker(f["ci_low"], f["ci_high"], lo, hi)
        a = avg.get(f["name"])
        if a is not None:
            inner += f'<rect class="avg stat" x="{pos(a, lo, hi)}%" y="2" width="2" height="16" transform="translate(-1 0)"/>'
        meaning = v3.card_text(f)[0]
        tip = f"{PLAIN[f['name']]}: beta {sgn(b)}, 95% interval {sgn(f['ci_low'])} to {sgn(f['ci_high'])}"
        rows.append(
            f'<tr id="beta-{f["name"]}" class="{"" if ok else "ns"}"><th scope="row">{fname(f["name"])}</th>'
            f'{bsvg(inner, ticks, lo, hi, tip)}<td class="num v">{sgn(b, 2)}</td>{reading(ok)}'
            f'<td class="hide-s">{e(meaning)}</td>'
            f'<td class="num stat">{tstat(f["z"])}</td><td class="num stat">{pval(f["p_adj_bh"])}</td>'
            f'<td class="num stat">{sgn(f["ci_low"], 2)} to {sgn(f["ci_high"], 2)}</td>'
            f'<td class="num stat">{sgn(a, 2) if a is not None else "&#8211;"}</td></tr>'
        )
    win = ab.get("window", 252)
    key = ('<ul class="key bkey" aria-label="Legend"><li><svg class="sw" aria-hidden="true"><rect class="b" width="14" height="10" rx="2"/></svg>Clear evidence</li>'
           '<li><svg class="sw" aria-hidden="true"><rect class="b ns" width="14" height="10" rx="2"/></svg>Could be noise</li>'
           '<li><svg class="sw" aria-hidden="true"><line class="ci" x1="0" x2="14" y1="5" y2="5"/><line class="ci" x1="0" x2="0" y1="2" y2="8"/><line class="ci" x1="14" x2="14" y1="2" y2="8"/></svg>95% interval</li>'
           f'<li class="stat"><svg class="sw" aria-hidden="true"><rect class="avg" x="6" y="0" width="2" height="10"/></svg>Average over {win}-day windows</li></ul>')
    body = f"""
<div class="tw"><table class="tbl bars">
  <caption class="vh">Factor betas over the analysed range, with 95% intervals</caption>
  <thead><tr>{th("Factor")}<th scope="col" class="bc"><span class="vh">Chart</span></th>{th("Beta", "beta", "num")}{th("Reading", "reading")}{th("Meaning", "meaning", "hide-s")}
  {th("t", "t", "num stat")}{th("p, adj.", "padj", "num stat")}{th("95% interval", "ci", "num stat")}{th(f"Avg {win}d", "avg", "num stat")}</tr></thead>
  <tbody>{''.join(rows)}</tbody>
  {axis_row(ticks, lo, hi)}
</table></div>
{key}"""
    fs = {f["name"]: f for f in g["factors"]}
    clear = [PLAIN[n].lower() for n in ("SMB", "HML", "RMW", "CMA") if fs[n]["tag"] == "reliable"]
    take = (f"Market beta {num(fs['Mkt-RF']['beta'], 2)}." + (f" Clear but small tilts: {v3.and_list(clear)}." if clear else " No clear tilt."))
    return panel("exposures", "Factor exposures", body, meta="Five-factor model, daily", take=e(take), span=span,
                 foot=how(f"OLS on daily excess returns with Newey-West standard errors ({g['hac_lags']} lags). Clear evidence means the "
                          f"Benjamini-Hochberg adjusted p is below 0.05 across the {g['bh_family_size']} betas. In-sample and descriptive, not predictive."))


def world_panel(r: dict, span: str) -> str:
    w = WORLD[r["ticker"]]
    rows_in = [("ACWI", "ACWI ETF, a stand-in for the MSCI ACWI index", w["acwi"], w["acwi_r2"]), ("US market", "Fama-French market factor, Mkt-RF", w["us"], w["us_r2"])]
    vals = [v for _, _, t, _ in rows_in for v in t] + [0.0]
    lo, hi, ticks = nice_domain(min(vals), max(vals), 4)
    rows = "".join(
        f'<tr><th scope="row"><span class="tip" title="{sub}">{lab}</span></th>'
        f'{bsvg(whisker(l, h, lo, hi) + f"<circle class=\"dot\" cx=\"{pos(b, lo, hi)}%\" cy=\"10\" r=\"4.5\"/>", ticks, lo, hi)}'
        f'<td class="num v">{num(b, 2)}</td><td class="num stat">{num(l, 2)} to {num(h, 2)}</td><td class="num">{r2:.2f}</td></tr>'
        for lab, sub, (b, l, h), r2 in rows_in
    )
    (bw, lw, hw), (bu, lu, hu) = w["acwi"], w["us"]
    overlap = lw <= hu and lu <= hw
    take = (f"About the same against the world as against the US market." if overlap
            else f"{'Higher' if bw > bu else 'Lower'} against the world than against the US market.")
    body = f"""
<div class="tw"><table class="tbl bars">
  <caption class="vh">Beta against the world and against the US market, with 95% intervals and R squared</caption>
  <thead><tr>{th("Against")}<th scope="col" class="bc"><span class="vh">Chart</span></th>{th("Beta", "beta", "num")}{th("95% interval", "ci", "num stat")}{th("R&#178;", "r2", "num")}</tr></thead>
  <tbody>{rows}</tbody>
  {axis_row(ticks, lo, hi)}
</table></div>"""
    return panel("world", "World beta", body, meta=f"{w['days']:,} days, one-factor", take=e(take), span=span,
                 foot=how("One-factor regression of daily excess returns on the ACWI ETF's excess returns, over the same days as the US market row, "
                          "with Newey-West intervals. The ACWI ETF stands in for the MSCI ACWI index; a quick estimate, not a full model. "
                          "Demo values: the fixture has no world beta yet."))


# ----------------------------------------------------------------------------- return and risk sources
def returns_panel(r: dict, span: str) -> str:
    rc, g = r["return_contribution"], r["regression"]
    tags = {f["name"]: f["tag"] for f in g["factors"]}
    items = [(fname(n), rc["factors"][n], tags.get(n) == "reliable") for n in FACTORS]
    items.append(('Alpha<span class="code">beyond the factors</span>', rc["alpha"], g["alpha_tag"] == "reliable"))
    total = rc["total_annualised_mean_excess_return"]
    vals = [x[1] for x in items] + [total, 0.0]
    lo, hi, ticks = nice_domain(min(vals), max(vals), 5)
    rows = "".join(
        f'<tr class="{"" if ok else "ns"}"><th scope="row">{lab}</th>{bsvg(hbar(v, lo, hi, "b" if ok else "b ns"), ticks, lo, hi)}'
        f'<td class="num v">{pct(v)}</td>{reading(ok)}</tr>'
        for lab, v, ok in items
    )
    rows += (f'<tr class="total"><th scope="row">Total above cash</th>{bsvg(hbar(total, lo, hi), ticks, lo, hi)}'
             f'<td class="num">{pct(total)}</td><td></td></tr>')
    memo = "".join(f"<li>{e(x)}</li>" for x in rc["memo"])
    mkt = rc["factors"]["Mkt-RF"]
    take = f"Market exposure accounts for {pct(mkt, 1)} of the {pct(total, 1)} average yearly return above cash."
    body = f"""
<div class="tw"><table class="tbl bars">
  <caption class="vh">Return contribution per factor and beyond the factors, percent a year, with the total</caption>
  <thead><tr>{th("Source")}<th scope="col" class="bc"><span class="vh">Chart</span></th>{th("A year", "Arithmetic average, percent a year", "num")}{th("Reading", "reading")}</tr></thead>
  <tbody>{rows}</tbody>
  {axis_row(ticks, lo, hi, lambda t: pct(t, 0) if t else "0%")}
</table></div>"""
    return panel("returns", "Return sources", body, meta="Percent a year", take=e(take), span=span,
                 foot=f'<details class="how"><summary>How this is computed</summary><p>Each factor\'s share is its beta times the factor\'s '
                      f'average return, times 252; arithmetic, not compounded. The rows add up exactly to the total. Not in the sum:</p><ul>{memo}</ul></details>')


def risk_panel(r: dict, span: str) -> str:
    rk = r["risk_contribution"]
    det = {d["name"]: d for d in rk["details"]}
    shares = {**rk["factors"], "Idiosyncratic": rk["idiosyncratic"]}
    low = min(shares.values())
    lo, hi, ticks = nice_domain(low if low < -0.02 else 0.0, max(1.0, max(shares.values())), 4)
    rows = []
    na = '<td class="num stat"><span class="na">&#8211;</span></td>'
    for n in rk["order"]:
        v = shares[n]
        if n == "Idiosyncratic":
            lab, cls, extra = 'Specific<span class="code">not explained</span>', "b idio", na * 3
        else:
            dd = det[n]
            lab, cls = fname(n), "b"
            extra = (f'<td class="num stat">{sgn(dd["beta"], 2)}</td><td class="num stat">{pct(dd["sigma_annual"], 1, False)}</td>'
                     f'<td class="num stat">{sgn(dd["rho_sys"], 2)}</td>')
        rows.append(f'<tr><th scope="row">{lab}</th>{bsvg(hbar(v, lo, hi, cls), ticks, lo, hi)}<td class="num v">{pct(v, 1, v < 0)}</td>{extra}</tr>')
    top = rk["order"][0]
    take = f"{PLAIN.get(top, top)} drives {share(shares[top])} of the variance; {share(rk['idiosyncratic'])} is specific to {r['ticker']}."
    body = f"""
<div class="tw"><table class="tbl bars">
  <caption class="vh">Share of variance per factor and specific to the security</caption>
  <thead><tr>{th("Source")}<th scope="col" class="bc"><span class="vh">Chart</span></th>{th("Share", "Share of the variance of daily returns", "num")}
  {th("Beta", "beta", "num stat")}{th("Factor vol.", "Volatility of the factor a year", "num stat")}{th("Corr.", "Correlation with the factor-driven return", "num stat")}</tr></thead>
  <tbody>{''.join(rows)}</tbody>
  {axis_row(ticks, lo, hi, lambda t: pct(t, 0, False) if t >= 0 else pct(t, 0))}
</table></div>"""
    return panel("risk", "Risk sources", body, meta=f"Total volatility {pct(rk['total_vol_annual'], 1, False)}", take=e(take), span=span,
                 foot=how("Euler decomposition of variance: share = beta &#215; factor volatility &#215; correlation with the factor-driven return, "
                          "divided by total volatility. Shares add to 100% and can be negative when a factor offsets the others."))


# ----------------------------------------------------------------------------- exposure over time
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
        zero = f'<line class="z" x1="0" x2="1000" y1="{Y(0):.2f}" y2="{Y(0):.2f}"/>' if lo < 0 < hi else ""
        svg = (f'<svg class="csvg" viewBox="0 0 1000 100" preserveAspectRatio="none" aria-hidden="true"><line class="base" x1="0" x2="1000" y1="100" y2="100"/>{zero}'
               f'<path class="band c{SLOT[name]}" d="{band}"/><path class="rl c{SLOT[name]}" d="{line}"/></svg>')
        vals = [v for _, v, _ in pts]
        a = (avg or {}).get(name)
        mean, p10, p90 = ((a["mean"], a["p10"], a["p90"]) if a and a.get("mean") is not None
                          else (sum(vals) / len(vals), _quantile(vals, 0.1), _quantile(vals, 0.9)))
        rows.append(
            f'<tr><th scope="row">{fname(name)}</th><td class="bc"><div class="mini">{svg}</div></td>'
            f'<td class="num v">{sgn(vals[-1], 2)}</td><td class="num hide-s">{sgn(mean, 2)}</td><td class="num stat">{sgn(p10, 2)} to {sgn(p90, 2)}</td></tr>'
        )
    xt = [t for t in v3.date_ticks(dates) if t[0] >= i0]
    xlab = v3.time_labels(xt, lambda i: X(i) / 10, gap=28)
    win = w["window"]
    return f"""
<div class="win w-{win}"><div class="tw"><table class="tbl roll">
  <caption class="vh">Rolling {win}-day betas per factor with a 95% band; latest and average</caption>
  <thead><tr>{th("Factor")}<th scope="col" class="bc"><span class="vh">Chart</span></th>{th("Latest", "Beta over the most recent window", "num")}{th("Average", "Mean over all windows", "num hide-s")}{th("Middle 80%", "Range of the middle 80% of window betas", "num stat")}</tr></thead>
  <tbody>{''.join(rows)}</tbody>
  <tfoot><tr class="axis" aria-hidden="true"><td></td><td class="ax bc"><div>{xlab}</div></td></tr></tfoot>
</table></div>
<p class="foot">Each point uses the previous {win} trading days; the chart starts at the first full window, {d_long(dates[i0])}. Every row spans {num(span, 2)} in beta, so wiggles compare across factors.</p></div>"""


def rolling_panel(r: dict, span: str, win126: bool = False) -> str:
    wins = sorted(r["rolling"], key=lambda w: w["window"])
    ab = r["average_beta"]
    primary = 126 if win126 else ab.get("window", 252)
    avg = {f["name"]: f for f in ab["factors"]} if ab["status"] == "ok" else {}
    seg = "".join(f'<label><input type="radio" name="window" id="win-{w["window"]}" value="{w["window"]}"{" checked" if w["window"] == primary else ""}>'
                  f'<span>{w["window"]} days</span></label>' for w in wins)
    blocks = "".join(rolling_block(w, avg if w["window"] == ab.get("window", 252) else None) for w in wins if w["status"] == "ok")
    mk = avg.get("Mkt-RF")
    widest = max(((f["p90"] - f["p10"]), n) for n, f in avg.items()) if avg else (0, "")
    take = (f"Steady: the market beta stayed between {num(mk['p10'], 2)} and {num(mk['p90'], 2)} in most windows; no other beta moved by more than {num(widest[0], 2)}."
            if mk and widest[0] < 0.15 else f"{PLAIN.get(widest[1], 'One')} exposure moved the most over time.")
    meta = f'<div class="seg" role="radiogroup" aria-label="Rolling window length">{seg}</div>'
    return panel("rolling", "Exposure over time", blocks, meta=meta, take=e(take), span=span,
                 foot=how("Each line is the beta re-estimated over a moving window; the shaded band is a pointwise 95% interval, so about "
                          "1 point in 20 falls outside it even when the true beta is constant. Overlapping windows share most of their data."))


# ----------------------------------------------------------------------------- deeper checks
def residual_panel(r: dict, span: str) -> str:
    w = next((w for w in r["rolling"] if w["window"] == 252 and w["status"] == "ok"), None)
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
    grid = "".join(f'<line class="{"z" if abs(t) < 1e-12 else "gl"}" x1="0" x2="1000" y1="{Y(t):.2f}" y2="{Y(t):.2f}"/>' for t in ticks)
    svg = f'{grid}<path class="band ink" d="{band}"/><path class="rl ink" d="{line}"/>'
    ylab = "".join(f'<span style="top:{Y(t):.2f}%">{pct(t, 0) if t else "0%"}</span>' for t in ticks)
    xt = [(i - i0, lab, major) for i, lab, major in v3.date_ticks(dates) if i >= i0]
    xlab = v3.time_labels(xt, lambda k: X(k) / 10)
    facts = [
        ("Windows clear of zero", f"{clear * 100:.0f}%", "Share of 252-day windows whose band excludes zero; about 5% is expected by chance", reading(False)),
        ("First half, second half", "+1.4%, +0.2%", "Leftover return a year in each half of the sample", reading(False)),
        ("Best calendar year", "2024, +0.6%", "Partial year; no year is clear of noise", reading(False)),
    ]
    rows = "".join(f'<tr><th scope="row"><span class="tip" title="{e(t)}">{a_}</span></th><td class="num v">{b}</td>{rd}</tr>' for a_, b, t, rd in facts)
    tbl = (f'<div class="tw"><table class="tbl"><caption class="vh">Return beyond the factors over time, in figures</caption>'
           f'<thead><tr>{th("Measure")}{th("Value", "", "num")}{th("Reading", "reading")}</tr></thead><tbody>{rows}</tbody></table></div>')
    body = f'<div class="split c84"><div>{chart(svg, ylab, xlab)}</div><div>{tbl}</div></div>'
    return panel("residual", "Return beyond the factors over time", body, meta="Rolling 252 days, percent a year",
                 take="No stretch shows a reliable return beyond the factors; the leftover return wanders around zero.", span=span,
                 foot=how("Rolling 252-day regressions of daily excess returns with Newey-West intervals; the split-half test compares the two "
                          "halves of the sample. Windows overlap, so the share of windows is descriptive, not a test. Demo values: the mock fixture has no residual section."))


def dot_table(caption: str, head: str, rows: str, ticks, lo, hi) -> str:
    return (f'<div class="tw"><table class="tbl bars"><caption class="vh">{caption}</caption><thead><tr>{th("Factor")}'
            f'<th scope="col" class="bc"><span class="vh">Chart</span></th>{head}</tr></thead><tbody>{rows}</tbody>{axis_row(ticks, lo, hi)}</table></div>')


def kalman_panel(r: dict, span: str) -> str:
    w = next((w for w in r["rolling"] if w["window"] == 126 and w["status"] == "ok"), None)
    fs = {f["name"]: f for f in r["regression"]["factors"]}
    lam = {"Mkt-RF": 0.0004, "SMB": 0.0, "HML": 0.0011, "RMW": 0.0, "CMA": 0.0}
    data = []
    for n in FACTORS:
        b = [v for v in w["betas"][n] if v is not None][-1]
        s = [v for v in w["se"][n] if v is not None][-1] * 0.85
        kb = 0.6 * b + 0.4 * fs[n]["beta"]
        data.append((n, kb, kb - 1.96 * s, kb + 1.96 * s, fs[n]["beta"]))
    vals = [v for _, k, l, h, o in data for v in (l, h, o)] + [0.0]
    lo, hi, ticks = nice_domain(min(vals), max(vals), 5)
    rows = ""
    for n, kb, l, h, o in data:
        inside = l <= o <= h
        inner = (whisker(l, h, lo, hi) + f'<circle class="ring" cx="{pos(o, lo, hi)}%" cy="10" r="4.5"/>'
                 f'<circle class="dot" cx="{pos(kb, lo, hi)}%" cy="10" r="4"/>')
        rows += (f'<tr><th scope="row">{fname(n)}</th>{bsvg(inner, ticks, lo, hi)}<td class="num v">{sgn(kb, 2)}</td><td class="num">{sgn(o, 2)}</td>'
                 f'<td class="num stat">{sgn(l, 2)} to {sgn(h, 2)}</td><td class="num stat">{lam[n]:.4f}</td>{reading(not inside, "Moved", "Could be noise")}</tr>')
    head = (f'{th("Latest", "Latest day-by-day beta", "num")}{th("Full", "Full-sample beta", "num")}{th("Band", "95% band of the latest beta", "num stat")}'
            f'{th("Drift", "Estimated day-to-day variance of the beta", "num stat")}{th("Change", "Moved: the full-sample beta lies outside the latest band")}')
    key = ('<ul class="key bkey" aria-label="Legend"><li><svg class="sw" aria-hidden="true"><circle class="dot" cx="7" cy="5" r="4"/></svg>Latest, tracked day by day</li>'
           '<li><svg class="sw" aria-hidden="true"><circle class="ring" cx="7" cy="5" r="4"/></svg>Full sample</li></ul>')
    return panel("kalman", "Exposure tracked day by day", dot_table("Latest day-by-day beta with its band, against the full-sample beta", head, rows, ticks, lo, hi) + key,
                 meta="Kalman filter", take="No exposure has moved clearly away from its full-sample value.", span=span,
                 foot=how("Random-walk betas with a constant alpha, estimated by a Kalman filter and re-estimated every 252 rows after a 504-row "
                          "training period. Demo values: the mock fixture has no Kalman section."))


def shrunk_panel(r: dict, span: str) -> str:
    prior = {"Mkt-RF": 1.0, "SMB": 0.15, "HML": 0.05, "RMW": 0.08, "CMA": 0.04}
    tau = 0.12
    data = []
    for f in r["regression"]["factors"]:
        wgt = f["se"] ** 2 / (f["se"] ** 2 + tau ** 2)
        data.append((f["name"], f["beta"], f["beta"] + (prior[f["name"]] - f["beta"]) * wgt, prior[f["name"]], wgt))
    vals = [v for _, o, s, p, _ in data for v in (o, s, p)] + [0.0]
    lo, hi, ticks = nice_domain(min(vals), max(vals), 5)
    biggest = max(abs(s - o) for _, o, s, _, _ in data)
    rows = ""
    for n, o, s, p, wgt in data:
        inner = (f'<line class="pull" x1="{pos(o, lo, hi)}%" x2="{pos(s, lo, hi)}%" y1="10" y2="10"/>'
                 f'<line class="prior" x1="{pos(p, lo, hi)}%" x2="{pos(p, lo, hi)}%" y1="4" y2="16"/>'
                 f'<circle class="ring" cx="{pos(o, lo, hi)}%" cy="10" r="4.5"/><circle class="dot" cx="{pos(s, lo, hi)}%" cy="10" r="3.5"/>')
        rows += (f'<tr><th scope="row">{fname(n)}</th>{bsvg(inner, ticks, lo, hi)}<td class="num">{sgn(o, 2)}</td><td class="num v">{sgn(s, 2)}</td>'
                 f'<td class="num">{sgn(s - o, 3)}</td><td class="num stat">{wgt * 100:.1f}%</td></tr>')
    head = (f'{th("Measured", "Full-sample beta", "num")}{th("Adjusted", "Beta pulled toward a typical value", "num")}'
            f'{th("Change", "", "num")}{th("Pull", "Weight on the typical value", "num stat")}')
    key = ('<ul class="key bkey" aria-label="Legend"><li><svg class="sw" aria-hidden="true"><circle class="ring" cx="7" cy="5" r="4"/></svg>Measured</li>'
           '<li><svg class="sw" aria-hidden="true"><circle class="dot" cx="7" cy="5" r="3.5"/></svg>Adjusted</li>'
           '<li><svg class="sw" aria-hidden="true"><line class="prior" x1="7" x2="7" y1="0" y2="10"/></svg>Typical value</li></ul>')
    take = (f"Pulling toward typical values changes the betas by at most {num(biggest, 3)}, so the measured betas stand."
            if biggest < 0.02 else f"Pulling toward typical values moves some betas by up to {num(biggest, 2)}.")
    return panel("shrunk", "Exposures adjusted for noise", dot_table("Measured betas against betas pulled toward typical values", head, rows, ticks, lo, hi) + key,
                 meta="Bayesian shrinkage", take=e(take), span=span,
                 foot=how("Shrinkage toward a prior from Fama-French portfolio betas; the pull is the posterior weight on the prior. "
                          "Demo values: the mock fixture has no shrunk section."))


# ----------------------------------------------------------------------------- data and audit, regression detail
def data_panel(r: dict, span: str) -> str:
    d = r["data"]
    cov = [
        ("Requested", f"{d_long(d['requested_start'])} to {d_long(d['requested_end'])}"),
        ("Analysed", f"{d_long(d['actual_start'])} to {d_long(d['actual_end'])}, {d['n_obs']:,} trading days"),
        ("Left out inside the range", v3.plural(d["n_excluded"], "day") + (" (a return spanning several factor days)" if d["excluded_by_reason"].get("multi_day_return") else "")),
        ("After the factor data", v3.plural(d["dropped_price_dates_after_factors"], "price day") + ", charted but not analysed"),
        ("Factor data ends", f"{d_long(d['factors_last_date'])}, {d['factors_days_behind']} days before the report"),
        ("Factor file downloaded", d_long(d["factors_downloaded_at"][:10]) if d["factors_downloaded_at"] else "Injected, not downloaded"),
        ("Prices", d["price_source"]),
        ("Factors", "Ken French Data Library, 5 factors daily"),
    ]
    rows = "".join(f'<tr><th scope="row">{e(a)}</th><td>{e(b)}</td></tr>' for a, b in cov)
    sev = {"info": ("info", "Info"), "warning": ("warn", "Warning"), "error": ("neg", "Error")}
    finds = "".join(
        f'<li><span class="sev {sev[f["severity"]][0]}">{sev[f["severity"]][1]}</span><span>{e(f["message"])}'
        + (f' ({", ".join(d_long(x) for x in f["dates"])})' if f["dates"] else "") + "</span></li>"
        for f in d["audit_findings"]
    ) or '<li><span class="sev info">Info</span><span>No findings. Prices passed every check.</span></li>'
    notes = "".join(f"<li>{e(v3.NOTICE_PLAIN.get(w['code'], w['message']))}</li>" for w in r["warnings"])
    notes += "".join(f"<li>{e(n)}</li>" for n in r["notes"]) + f"<li>{e(r['label_text'].get('L-VINTAGE', ''))}</li>"
    nwarn = sum(1 for f in d["audit_findings"] if f["severity"] in ("warning", "error"))
    body = f"""
<div class="split c66">
  <div><h3>Coverage</h3><div class="tw"><table class="tbl kvt"><caption class="vh">Data coverage</caption><tbody>{rows}</tbody></table></div></div>
  <div><h3>Audit findings</h3><ul class="findings">{finds}</ul><h3 style="margin-top:16px">Keep in mind</h3><ul class="notes">{notes}</ul></div>
</div>"""
    meta = f"{v3.plural(nwarn, 'audit warning') if nwarn else 'No audit warnings'}, {v3.plural(len(r['warnings']), 'data note')}"
    return panel("data", "Data and audit", body, meta=meta, span=span,
                 foot=how("Audit findings are reported, never acted on: no price is changed or removed because of them."))


def detail_panel(r: dict, span: str) -> str:
    g = r["regression"]
    vif = g["vif"]
    na = '<span class="na">&#8211;</span>'
    rows = [
        f'<tr class="{"" if g["alpha_tag"] == "reliable" else "ns"}"><th scope="row">Alpha<span class="code">a year</span></th>'
        f'<td class="num v">{pct(g["alpha_annual"])}</td>{reading(g["alpha_tag"] == "reliable")}<td class="num stat">{pct(g["alpha_se_annual"], 2, False)}</td>'
        f'<td class="num stat">{tstat(g["alpha_z"])}</td><td class="num stat">{pval(g["alpha_p"])}</td><td class="num stat">{na}</td>'
        f'<td class="num stat">{pct(g["alpha_ci_low_annual"])} to {pct(g["alpha_ci_high_annual"])}</td><td class="num stat">{na}</td></tr>'
    ]
    for f in g["factors"]:
        ok = f["tag"] == "reliable"
        rows.append(
            f'<tr class="{"" if ok else "ns"}"><th scope="row">{fname(f["name"])}</th>'
            f'<td class="num v">{sgn(f["beta"])}</td>{reading(ok)}<td class="num stat">{num(f["se"], 4)}</td><td class="num stat">{tstat(f["z"])}</td>'
            f'<td class="num stat">{pval(f["p"])}</td><td class="num stat">{pval(f["p_adj_bh"])}</td>'
            f'<td class="num stat">{sgn(f["ci_low"])} to {sgn(f["ci_high"])}</td><td class="num stat">{vif.get(f["name"], 0):.2f}</td></tr>'
        )
    five = r.get("five_day_regression") or {}
    five_line = (f' Five-day check: {five["n_blocks"]} blocks give alpha {pct(five["alpha_annual"])} a year (p {pval(five["alpha_p"])}) '
                 f'and R&#178; {five["r2"]:.4f}.') if five.get("status") == "ok" else ""
    body = f"""
<div class="tw"><table class="tbl reg"><caption class="vh">Regression estimates and evidence for each term</caption>
  <thead><tr>{th("Term")}{th("Estimate", "", "num")}{th("Reading", "reading")}{th("Std. error", "Newey-West standard error", "num stat")}{th("t", "t", "num stat")}
  {th("p", "Unadjusted p-value", "num stat")}{th("p, adj.", "padj", "num stat")}{th("95% interval", "ci", "num stat")}{th("VIF", "Variance inflation factor", "num stat")}</tr></thead>
  <tbody>{''.join(rows)}</tbody></table></div>
<p class="foot"><span class="plain-only">Turn on Show statistics for standard errors, t, p-values, intervals and VIF. </span>
<span class="stat">R&#178; {g['r2']:.4f}, adjusted {g['adj_r2']:.4f}. Residual volatility {pct(g['sigma_e_annual'], 2, False)} a year. Newey-West lags {g['hac_lags']}. Condition number {g['condition_number']:.2f}.{five_line}</span></p>"""
    return panel("detail", "Regression detail", body, meta=f"{r['data']['n_obs']:,} daily observations", span=span)


# ----------------------------------------------------------------------------- page
def font_face() -> str:
    return v3.font_face()


def gen_stamp(r: dict) -> str:
    return v3.gen_stamp(r)


def content(r: dict, variant: str, on: set[str]) -> tuple[str, list[str]]:
    w126 = "win126" in on
    if variant == "a":
        parts = [
            page_head(r), analysis_bar(r), '<div class="grid">', summary_a(r),
            drawdown_panel(r, "", split=True),
            exposures_panel(r, ""), world_panel(r, ""),
            returns_panel(r, "s-6"), risk_panel(r, "s-6"),
            rolling_panel(r, "", w126),
            residual_panel(r, ""), kalman_panel(r, "s-6x"), shrunk_panel(r, "s-6x"),
            data_panel(r, ""), detail_panel(r, ""), "</div>",
        ]
        order = ["summary", "price", "performance", "exposures", "world", "returns", "risk", "rolling", "residual", "kalman", "shrunk", "data", "detail"]
    else:
        d = r["data"]
        extra = (f". Analysed {d_long(d['actual_start'])} to {d_long(d['actual_end'])}, {d['n_obs']:,} trading days. "
                 f"Factor data to {d_long(d['factors_last_date'])}. Past data, not a forecast.")
        parts = [
            page_head(r, extra), summary_bar(r), kpi_strip(r), '<div class="grid">',
            price_panel_b(r, "s-6"), drawdown_panel(r, "s-6", split=False),
            f'<div class="stack s-7">{exposures_panel(r, "")}{returns_panel(r, "")}</div>',
            f'<div class="stack s-5">{world_panel(r, "")}{risk_panel(r, "")}</div>',
            rolling_panel(r, "", w126),
            residual_panel(r, ""), kalman_panel(r, "s-6x"), shrunk_panel(r, "s-6x"),
            data_panel(r, ""), detail_panel(r, ""), "</div>",
        ]
        order = ["summary", "price", "performance", "exposures", "returns", "world", "risk", "rolling", "residual", "kalman", "shrunk", "data", "detail"]
    return "\n".join(parts), order


def page(r: dict, variant: str, on: set[str]) -> str:
    main, order = content(r, variant, on)
    colophon = (f'<footer class="colophon"><p>factordesk report, schema v{e(str(r["schema_version"]))}, generated {gen_stamp(r)}. '
                "Descriptive statistics on past data; nothing here is a forecast or advice. Demo values are marked where they appear.</p></footer>")
    body = f"""<a class="skip" href="#summary">Skip to the report</a>
<input class="vh" type="checkbox" id="nav-open" aria-controls="sidebar" aria-label="Menu">
{topbar(r)}
{sidebar(r, order)}
<div class="canvas"><main id="main">{main}{colophon}</main></div>"""
    for key, el in (("stats", "sw-stats"), ("menu", "nav-open")):
        if key in on:
            body = body.replace(f'id="{el}"', f'id="{el}" checked', 1)
    name = SECURITY.get(r["ticker"], {}).get("name", "")
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light">
<meta name="theme-color" content="#141A33">
<title>{e(r['ticker'])} factor profile{f" - {e(name)}" if name else ""}</title>
<style>
{font_face()}
{CSS}
</style>
</head>
<body class="v-{variant}">
{body}
</body>
</html>
"""


def main() -> None:
    args = sys.argv[1:]
    r = json.loads(FIXTURE.read_text(encoding="utf-8"))
    on = set(args[args.index("--on") + 1].split(",")) if "--on" in args else set()
    variants = [args[args.index("--variant") + 1]] if "--variant" in args else ["a", "b"]
    for v in variants:
        out = Path(args[args.index("--out") + 1]) if "--out" in args and len(variants) == 1 else HERE / f"report-v4{v}.html"
        out.write_text(page(r, v, on), encoding="utf-8", newline="\n")
        print(f"wrote {out} ({out.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
