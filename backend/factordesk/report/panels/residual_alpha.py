"""Static HTML panel of the ``residual`` section (contract SC2.5, SC7).

Spec: ``docs/methodology-residual-analysis.md`` R8 (the wording below is the specification's, and
the React panel uses the same words). Registered at position 710 as ``residual_alpha``, element id
``residual``. Design: ``docs/design/report-design.md`` (colour is evidence, charts are tables,
sentence case, no monospace). The panel is quiet: the fitted equation stays the one bold element,
so every mark here is ink, grey or a dash pattern; the three lines differ by weight and dashes.

Contents, top to bottom: the in-sample against point-in-time table, the cumulative chart with its
table, the gap statement, the stability block (rolling alpha, one-year windows, split halves,
calendar years), the diagnostics findings, the caveats and warnings, and a folded "How this is
computed". A section that is not ``ok`` shows its reason as the empty state and no numbers. A
point-in-time part that is ``insufficient_data`` leaves the in-sample parts and shows its reason in
place of its column and lines.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from datetime import date

from factordesk.report.base import ReportWarning
from factordesk.report.panel_registry import register_panel
from factordesk.report.render_html import (
    GLYPHS,
    MINUS,
    MONTHS,
    date_long,
    empty_state,
    esc,
    fmt_num,
    fmt_pct,
    fmt_pval,
    fmt_signed,
    panel_head,
    panel_section,
)
from factordesk.report.schema import FactorReport
from factordesk.report.sections.residual_alpha import (
    QUESTION,
    RESIDUAL_LABEL_TEXT,
    ResidualAlphaDiagnostics,
    ResidualAnalysis,
    ResidualStats,
)

PANEL_ID = "residual"
TITLE = "Residual return"
NEXT_STEP = "Choose a longer date range or another ticker, then run the report again."
PIT_NEXT_STEP = "Choose a shorter beta window or a longer period."
WARMUP_CAPTION = (
    "Warm-up: the first {w} trading days are used to estimate the first point-in-time betas."
)
UNCOVERED_MEMO = (
    "No factor data after {last}: the residual is unknown for the last {n} trading days."
)
EXCLUDED_NOTE = "Skips {n} excluded days (listed under sample details)."
STABILITY_CAUTION = (
    "The halves and calendar years are fixed in advance. If you search for the year or split date "
    "that looks best, the p-values stop meaning what they say: with 10 years to choose from, the "
    "best year has a nominal p below 0.05 about 40% of the time even when nothing changed."
)
YEARS_READING = (
    "A year within two noise standard deviations of zero is ordinary for a stock with no alpha."
)
FOLD_LABELS = (
    "L-DESC-PIT",
    "L-INSAMPLE",
    "L-PIT",
    "L-HEDGE",
    "L-VINTAGE",
    "L-BAND",
    "L-OVERLAP",
)
READING = {
    "Residual return a year": (
        "What the stock earned per year beyond its factor exposures, alpha included. In-sample it "
        "equals the regression alpha exactly."
    ),
    "t-statistic": (
        "Distance of the residual return from zero in standard errors. Between -2 and 2 (p above "
        "0.05), you cannot tell it from zero."
    ),
    "Residual volatility a year": (
        "How much the stock moves for reasons the five factors do not explain. Higher volatility "
        "makes alpha harder to measure."
    ),
    "Information ratio": (
        "Residual return per unit of residual risk. Do not compare it with a total-return Sharpe "
        "ratio."
    ),
    "Cumulative, compounded": (
        "What the daily-rebalanced paper hedge compounded to, before costs."
    ),
    "Compound growth a year": "Lower than the residual return by about half the residual variance.",
    "Hit rate": (
        "Share of days the residual was positive. Near 50% is normal; it says how often, not how "
        "much."
    ),
    "Largest fall": "Worst fall of the cumulative residual line from a previous high.",
    "Skew": "Below 0: rare large residual losses. Above 0: rare large gains, often earnings days.",
    "Excess kurtosis": (
        "Above 0: more extreme days than a normal distribution. Intervals are then approximate."
    ),
}
"""Reading rules of R3.5, shown as tooltips on the row names."""

PANEL_CSS = """
.ra-tab {
  width: 100%;
  max-width: 760px;
  border-collapse: collapse;
  table-layout: fixed;
  margin-top: var(--s-3);
}
.ra-tab.kv { max-width: 600px; }
.ra-tab thead th {
  font-size: var(--fs-1);
  font-weight: 500;
  color: var(--ink-2);
  text-align: right;
  padding: 0 0 6px var(--s-3);
  border-bottom: 1px solid var(--border);
  vertical-align: bottom;
}
.ra-tab thead th:first-child { text-align: left; padding-left: 0; }
.ra-tab tbody th {
  text-align: left;
  font-weight: 400;
  padding: 8px var(--s-3) 8px 0;
  border-bottom: 1px solid var(--grid);
  vertical-align: top;
}
.ra-tab td {
  text-align: right;
  padding: 8px 0 8px var(--s-3);
  border-bottom: 1px solid var(--grid);
  vertical-align: top;
  overflow-wrap: anywhere;
}
.ra-tab tr:last-child > * { border-bottom: 0; }
.ra-tab th.vals { width: 220px; }
.ra-tab th.nar { width: 92px; }
.ra-tab th.mid { width: 132px; }
.ra-main { display: block; color: var(--ink); font-weight: 520; }
.ra-sub {
  display: block;
  font-size: var(--fs-1);
  color: var(--ink-3);
  line-height: 1.4;
  font-weight: 400;
}
.ra-tag { margin-left: var(--s-2); font-size: var(--fs-1); font-weight: 560; color: var(--ink-2); }
.ra-tab td.ra-reason {
  text-align: left;
  color: var(--ink-2);
  background: var(--sunk);
  padding: var(--s-3) var(--s-4);
  border-bottom: 0;
}
.ra-next { margin-top: var(--s-1); color: var(--ink-3); }
.ra-key {
  display: inline-block;
  vertical-align: middle;
  width: 22px;
  height: 8px;
  margin-right: 8px;
  overflow: visible;
}
.ra-lab { display: block; }
.ra-banner { margin-top: var(--s-4); }
.ra-sev { font-weight: 640; margin-right: var(--s-2); }
.ra-note {
  margin-top: var(--s-3);
  max-width: 76ch;
  color: var(--ink-2);
  font-size: var(--fs-1);
  line-height: 1.45;
}
.ra-lead { margin-top: var(--s-4); max-width: 76ch; }
.ra-plot { height: 220px; margin: var(--s-4) 0 34px 52px; border-bottom: 1px solid var(--axis); }
.ra-plot.short { height: 150px; }
.line-svg .ra-l { fill: none; }
.line-svg .ra-l.full { stroke: var(--ink-3); stroke-width: 1.5; }
.line-svg .ra-l.same { stroke: var(--ink-2); stroke-width: 1.75; stroke-dasharray: 6 4; }
.line-svg .ra-l.pit { stroke: var(--ink); stroke-width: 2; }
.line-svg .ra-l.roll { stroke: var(--ink); stroke-width: 1.75; }
.line-svg path.ra-band { stroke: none; fill: var(--ink-3); fill-opacity: 0.16; }
.ra-zone { fill: var(--grid); }
.ra-key-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px var(--s-4);
  margin-top: var(--s-3);
  font-size: var(--fs-1);
  color: var(--ink-2);
}
.ra-key-list li { display: inline-flex; align-items: center; }
.ra-key line { stroke-width: 2; }
.ra-key .ra-l.full { stroke: var(--ink-3); stroke-width: 1.5; }
.ra-key .ra-l.same { stroke: var(--ink-2); stroke-dasharray: 5 3; }
.ra-key .ra-l.pit { stroke: var(--ink); stroke-width: 2.5; }
.ra-find { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 0 var(--s-6); }
.ra-find h4 { margin: var(--s-3) 0 var(--s-1); font-size: var(--fs-2); font-weight: 600; }
.ra-find li { padding: 7px 0; border-bottom: 1px solid var(--grid); max-width: 60ch; }
.ra-find li:last-child { border-bottom: 0; }
@media screen and (max-width: 719px) {
  .ra-tab th.vals { width: 36%; }
  .ra-tab th.nar { width: 74px; }
  .ra-tab th.mid { width: 92px; }
  .ra-plot { margin-left: 44px; height: 180px; }
  .ra-plot.short { height: 130px; }
  .ra-find { grid-template-columns: 1fr; }
}
@media print {
  .ra-tab, .ra-plot, .notice { break-inside: avoid; }
}
"""


# ------------------------------------------------------------------------------- small formats
def _pct(x: float | None, digits: int = 1) -> str:
    """Signed percent with a true minus."""
    return fmt_pct(x, digits)


def _pct_plain(x: float | None, digits: int = 1) -> str:
    """Percent without the plus sign (a true minus when negative)."""
    return fmt_pct(x, digits, signed=False)


def _round5(x: float) -> int:
    """Magnitude of a ratio in percent, to the nearest 5 points, halves away from zero (TR18)."""
    return int(abs(x * 100) / 5 + 0.5 + 1e-9) * 5


def _kept(ratio: float | None) -> str:
    """The survival ratio in words: ``100% kept``, ``more than 200% kept``, or a reversed sign."""
    if ratio is None or not math.isfinite(ratio):
        return "n/a"
    if ratio > 2:
        return "more than 200% kept"
    pts = _round5(ratio)
    if ratio < 0 and pts > 0:
        return f"{MINUS}{pts}% kept (the sign reversed)"
    return f"{pts}% kept"


def _share(q: float | None) -> str:
    """A share of the full-period alpha, to the nearest 5 points."""
    if q is None or not math.isfinite(q):
        return "n/a"
    if q > 2:
        return "more than 200%"
    pts = _round5(q)
    return f"{MINUS if q < 0 and pts > 0 else ''}{pts}%"


def _span(a: date | None, b: date | None) -> str:
    if a is None or b is None:
        return "n/a"
    return f"{date_long(a)} to {date_long(b)}"


def _cell(main: str, *subs: str, extra: str = "") -> str:
    """A value with quieter lines under it; ``extra`` is trusted markup after the value."""
    inner = f'<span class="ra-main">{esc(main)}{extra}</span>'
    inner += "".join(f'<span class="ra-sub">{esc(s)}</span>' for s in subs if s)
    return inner


def _td(inner: str, title: str = "") -> str:
    tip = f' title="{esc(title)}"' if title else ""
    return f"<td{tip}>{inner}</td>"


def _table(caption: str, head: str, body: str, *, kv: bool = False) -> str:
    """A ruled table with a hidden caption."""
    cls = "ra-tab kv" if kv else "ra-tab"
    thead = f"<thead><tr>{head}</tr></thead>" if head else ""
    return (
        f'<table class="{cls}"><caption class="vh">{esc(caption)}</caption>{thead}'
        f"<tbody>{body}</tbody></table>"
    )


def _kv_rows(rows: Sequence[tuple[str, str]]) -> str:
    return "".join(f'<tr><th scope="row">{esc(a)}</th>{_td(b)}</tr>' for a, b in rows)


def _reason_block(reason: str | None, next_step: str = "") -> str:
    nxt = f'<p class="ra-next">{esc(next_step)}</p>' if next_step else ""
    return f"<p>{esc(reason or 'Not available.')}</p>{nxt}"


def _caption(text: str | None) -> str:
    return f'<p class="ra-note">{esc(text)}</p>' if text else ""


# ------------------------------------------------------------------------------- the table
def _drawdown_cell(stats: ResidualStats) -> str:
    if stats.max_drawdown is None:
        return _cell("n/a")
    subs: list[str] = []
    if stats.max_drawdown_trough is None:
        subs.append("No fall from a previous high.")
    else:
        top = stats.max_drawdown_peak
        peak = "the start" if top is None else date_long(top)
        rec = (
            f"recovered {date_long(stats.max_drawdown_recovery)}"
            if stats.max_drawdown_recovery
            else "not recovered"
        )
        subs.append(f"Peak {peak}, trough {date_long(stats.max_drawdown_trough)}, {rec}.")
    if stats.noise_drawdown_reference is not None:
        ref = _pct_plain(stats.noise_drawdown_reference)
        subs.append(f"Noise alone typically falls about {ref}.")
    return _cell(_pct(stats.max_drawdown), *subs)


def _interval(low: float | None, high: float | None, digits: int = 1, pct: bool = True) -> str:
    if low is None or high is None:
        return ""
    if pct:
        return f"95% interval {_pct_plain(low, digits)} to {_pct_plain(high, digits)}"
    return f"95% interval {fmt_num(low, digits)} to {fmt_num(high, digits)}"


def _column_cells(stats: ResidualStats) -> list[str]:
    """The cells of one column, in the row order of ``_ROW_LABELS``."""
    s = stats.sample
    tag = f'<span class="ra-tag">{esc(stats.tag)}</span>' if stats.tag else ""
    return [
        _cell(_span(s.start, s.end), f"{s.n} trading days"),
        _cell(
            _pct(stats.residual_return_annual),
            _interval(stats.residual_return_ci_low_annual, stats.residual_return_ci_high_annual),
        ),
        _cell(fmt_num(stats.z, 2), extra=tag),
        _cell(_pct_plain(stats.residual_vol_annual)),
        _cell(
            fmt_num(stats.information_ratio, 2),
            _interval(stats.information_ratio_ci_low, stats.information_ratio_ci_high, 2, False),
        ),
        _cell(_pct(stats.cumulative_return)),
        _cell(_pct(stats.compound_growth_annual)),
        _cell(_pct_plain(stats.hit_rate)),
        _drawdown_cell(stats),
        _cell(fmt_signed(stats.skew, 2)),
        _cell(fmt_signed(stats.excess_kurtosis, 2)),
    ]


_ROW_LABELS = (
    "Period",
    "Residual return a year",
    "t-statistic",
    "Residual volatility a year",
    "Information ratio",
    "Cumulative, compounded",
    "Compound growth a year",
    "Hit rate",
    "Largest fall",
    "Skew",
    "Excess kurtosis",
)


def _compare_table(section: ResidualAnalysis) -> str:
    """In-sample against point-in-time; a column that is not ``ok`` shows its reason instead."""
    cols: list[list[str] | str] = []
    for stats, nxt in ((section.in_sample, ""), (section.point_in_time, PIT_NEXT_STEP)):
        if stats.status == "ok":
            cols.append(_column_cells(stats))
        else:
            step = nxt if stats.status == "insufficient_data" else ""
            cols.append(_reason_block(stats.reason, step))
    rows: list[str] = []
    for i, name in enumerate(_ROW_LABELS):
        tip = READING.get(name, "")
        tip_attr = f' title="{esc(tip)}"' if tip else ""
        cells = [f'<th scope="row"{tip_attr}>{esc(name)}</th>']
        for col in cols:
            if isinstance(col, str):
                if i == 0:
                    cells.append(f'<td class="ra-reason" rowspan="{len(_ROW_LABELS)}">{col}</td>')
            else:
                cells.append(_td(col[i]))
        rows.append(f"<tr>{''.join(cells)}</tr>")
    head = (
        '<th scope="col" class="c1"><span class="vh">Measure</span></th>'
        '<th scope="col" class="vals">In-sample (static betas)</th>'
        '<th scope="col" class="vals">'
        f"Point-in-time (trailing {section.beta_window}-day betas)</th>"
    )
    return _table(
        "Residual return of the stock, in-sample against point-in-time", head, "".join(rows)
    )


# ------------------------------------------------------------------------------- chart helpers
def _nice_domain(lo: float, hi: float, target: int = 4) -> tuple[float, float, list[float]]:
    """A round range around ``lo`` and ``hi`` with its tick values."""
    raw = max(hi - lo, 1e-9) / target
    mag = 10 ** math.floor(math.log10(raw))
    step = next(m * mag for m in (1, 2, 2.5, 5, 10) if m * mag >= raw - 1e-12)
    lo_n = math.floor(lo / step + 1e-9) * step
    hi_n = math.ceil(hi / step - 1e-9) * step
    n = round((hi_n - lo_n) / step)
    return lo_n, hi_n, [lo_n + k * step for k in range(n + 1)]


def _tick_text(t: float, step: float) -> str:
    whole = abs(step * 100 - round(step * 100)) < 1e-9
    return fmt_pct(0.0 if abs(t) < 1e-12 else t, 0 if whole else 1)


def _date_ticks(d0: date, d1: date) -> list[tuple[date, str, bool]]:
    """Calendar ticks (date, label, major): quarterly for short spans, yearly for long ones."""
    months = max((d1 - d0).days, 1) / 30.44
    step = next((k for k in (3, 6, 12, 24, 60) if months / k <= 8), 120)
    out: list[date] = []
    y, m = d0.year, d0.month
    while date(y, m, 1) <= d1:
        aligned = (m - 1) % step == 0 if step < 12 else (m == 1 and y % (step // 12) == 0)
        if aligned and date(y, m, 1) >= d0:
            out.append(date(y, m, 1))
        m += 1
        if m > 12:
            y, m = y + 1, 1
    ticks: list[tuple[date, str, bool]] = []
    for i, cur in enumerate(out):
        label = f"{MONTHS[cur.month - 1]} {cur.year}" if step < 12 else str(cur.year)
        ticks.append((cur, label, i % 2 == 0 or len(out) <= 4))
    return ticks


def _keep_indices(n: int, limit: int = 400) -> list[int]:
    """Every k-th index so at most about ``limit`` remain; the last one always stays."""
    if n <= limit:
        return list(range(n))
    idx = list(range(0, n, math.ceil(n / limit)))
    if idx[-1] != n - 1:
        idx.append(n - 1)
    return idx


def _path(xs: Sequence[float], ys: Sequence[float | None]) -> str:
    """An SVG path through the points; a missing value starts a new segment."""
    parts: list[str] = []
    pen = False
    for x, y in zip(xs, ys, strict=True):
        if y is None:
            pen = False
            continue
        parts.append(f"{'L' if pen else 'M'}{x:.1f},{y:.1f}")
        pen = True
    return " ".join(parts)


def _edge(x: float) -> str:
    """Tick labels at the plot edges are anchored inward so they never overflow."""
    return "edge-l" if x < 3 else ("edge-r" if x > 97 else "")


def _plot(
    dates: Sequence[date],
    lines: Sequence[tuple[str, Sequence[float | None]]],
    label: str,
    *,
    band: tuple[Sequence[float | None], Sequence[float | None]] | None = None,
    zone_to: date | None = None,
    cut_at: date | None = None,
    short: bool = False,
) -> str:
    """A line chart on the dates with a zero line, a y axis in percent and a time axis.

    ``lines`` are (css class, values). The x range starts at the first date with any value.
    """
    n = len(dates)
    first = next((i for i in range(n) if any(v[i] is not None for _, v in lines)), 0)
    idx = [first + i for i in _keep_indices(n - first)]
    o0 = dates[first].toordinal()
    o1 = max(dates[-1].toordinal(), o0 + 1)

    def x_of(d: date) -> float:
        return (d.toordinal() - o0) / (o1 - o0) * 1000

    series = [v for _, v in lines] + (list(band) if band is not None else [])
    values = [0.0] + [x for seq in series for x in seq[first:] if x is not None]
    lo, hi, ticks = _nice_domain(min(values), max(values))
    step = ticks[1] - ticks[0] if len(ticks) > 1 else 1.0

    def y_of(v: float) -> float:
        return 100 - (v - lo) / (hi - lo) * 100

    def _y(v: float | None) -> float | None:
        return None if v is None else y_of(v)

    xs = [x_of(dates[i]) for i in idx]
    grid = "".join(
        f'<line class="grid" x1="0" x2="1000" y1="{y_of(t):.2f}" y2="{y_of(t):.2f}"/>'
        for t in ticks
        if abs(t) > 1e-12
    )
    zero = f'<line class="zero" x1="0" x2="1000" y1="{y_of(0):.2f}" y2="{y_of(0):.2f}"/>'
    zone = ""
    if zone_to is not None and dates[first] < zone_to:
        zone = f'<rect class="ra-zone" x="0" y="0" width="{x_of(zone_to):.1f}" height="100"/>'
    cut = ""
    if cut_at is not None:
        cx = x_of(cut_at)
        cut = f'<line class="cutline" x1="{cx:.1f}" x2="{cx:.1f}" y1="0" y2="100"/>'
    band_path = ""
    if band is not None:
        pts: list[tuple[float, float, float]] = []
        for x, i in zip(xs, idx, strict=True):
            low_v, high_v = band[0][i], band[1][i]
            if low_v is not None and high_v is not None:
                pts.append((x, low_v, high_v))
        if pts:
            upper = [(x, y_of(h)) for x, _, h in pts]
            lower = [(x, y_of(low)) for x, low, _ in reversed(pts)]
            poly = " L".join(f"{x:.1f},{y:.1f}" for x, y in upper + lower)
            band_path = f'<path class="ra-band" d="M{poly}Z"/>'
    paths = "".join(
        f'<path class="ra-l {esc(cls)}" d="{_path(xs, [_y(v[i]) for i in idx])}"/>'
        for cls, v in lines
    )
    svg = (
        '<svg class="line-svg" viewBox="0 0 1000 100" preserveAspectRatio="none" role="img" '
        f'aria-label="{esc(label)}">{zone}{grid}{zero}{band_path}{cut}{paths}</svg>'
    )
    ylabels = "".join(
        f'<span class="yl" style="top:{y_of(t):.2f}%">{esc(_tick_text(t, step))}</span>'
        for t in ticks
    )
    xlabels = "".join(
        f'<span class="xl{"" if major else " minor"} {_edge(x_of(d) / 10)}" '
        f'style="left:{x_of(d) / 10:.2f}%">{esc(lab)}</span>'
        for d, lab, major in _date_ticks(dates[first], dates[-1])
    )
    return (
        f'<div class="plot ra-plot{" short" if short else ""}">{svg}'
        f'<div class="ylabels" aria-hidden="true">{ylabels}</div>'
        f'<div class="xlabels" aria-hidden="true">{xlabels}</div></div>'
    )


def _key(cls: str) -> str:
    return (
        '<svg class="ra-key" aria-hidden="true" viewBox="0 0 22 8"><line class="ra-l '
        f'{cls}" x1="0" x2="22" y1="4" y2="4"/></svg>'
    )


def _last(values: Sequence[float | None]) -> float | None:
    return next((v for v in reversed(values) if v is not None), None)


# ------------------------------------------------------------------------------- the chart block
def _line_row(cls: str, name: str, start: date, cells: Sequence[str]) -> str:
    return (
        f'<tr><th scope="row"><span class="ra-lab">{_key(cls)}{esc(name)}</span>'
        f'<span class="ra-sub">from {esc(date_long(start))}</span></th>'
        + "".join(_td(c) for c in cells)
        + "</tr>"
    )


def _chart_block(section: ResidualAnalysis) -> str:
    ch = section.chart
    if ch.status != "ok" or not ch.dates:
        return empty_state(ch.reason or "The chart is not available.")
    anchor = ch.comparison_start if ch.point_in_time_status == "ok" else None
    lines: list[tuple[str, Sequence[float | None]]] = [("full", ch.in_sample_full)]
    label = "Cumulative residual return, compounded daily: in-sample for the whole period"
    if anchor is not None:
        lines += [("same", ch.in_sample_compare), ("pit", ch.point_in_time_compare)]
        label += ", and in-sample and point-in-time on the same days"
    plot = _plot(ch.dates, lines, label, zone_to=anchor, cut_at=anchor)
    legend = [f"<li>{_key('full')}In-sample, whole period</li>"]
    if anchor is not None:
        legend += [
            f"<li>{_key('same')}In-sample, same days as point-in-time</li>",
            f"<li>{_key('pit')}Point-in-time</li>",
        ]
    ins, pit, gap = section.in_sample, section.point_in_time, section.gap
    rows = [
        _line_row(
            "full",
            "In-sample, whole period",
            ch.dates[0],
            [
                _cell(_pct(_last(ch.in_sample_full))),
                _cell(_pct(ins.residual_return_annual)),
                _cell(fmt_num(ins.z, 2)),
            ],
        )
    ]
    if anchor is not None:
        rows.append(
            _line_row(
                "same",
                "In-sample, same days",
                anchor,
                [
                    _cell(_pct(_last(ch.in_sample_compare))),
                    _cell(_pct(gap.in_sample_same_days_annual)),
                    _cell("n/a"),
                ],
            )
        )
        rows.append(
            _line_row(
                "pit",
                "Point-in-time",
                anchor,
                [
                    _cell(_pct(_last(ch.point_in_time_compare))),
                    _cell(_pct(pit.residual_return_annual)),
                    _cell(fmt_num(pit.z, 2)),
                ],
            )
        )
    else:
        nxt = PIT_NEXT_STEP if ch.point_in_time_status == "insufficient_data" else ""
        reason = _reason_block(ch.point_in_time_reason or pit.reason, nxt)
        rows.append(
            '<tr><th scope="row"><span class="ra-lab">Point-in-time</span></th>'
            f'<td class="ra-reason" colspan="3">{reason}</td></tr>'
        )
    head = (
        '<th scope="col" class="c1">Line</th>'
        '<th scope="col" class="mid">Cumulative at the end</th>'
        '<th scope="col" class="mid">Residual return a year</th>'
        '<th scope="col" class="nar">t-statistic</th>'
    )
    table = _table(
        "Cumulative residual return at the end of each line, with the yearly residual return "
        "and its t-statistic",
        head,
        "".join(rows),
    )
    notes = [ch.caption]
    if anchor is not None:
        notes.append(WARMUP_CAPTION.format(w=section.beta_window) + " Shaded on the chart.")
    if ch.n_uncovered and ch.uncovered_from is not None:
        last = ch.sample.factor_vintage.last_date
        notes.append(UNCOVERED_MEMO.format(last=date_long(last), n=ch.n_uncovered))
    if ch.n_excluded_in_span:
        notes.append(EXCLUDED_NOTE.format(n=ch.n_excluded_in_span))
    return (
        f'<ul class="ra-key-list" aria-label="Legend">{"".join(legend)}</ul>{plot}{table}'
        + "".join(_caption(t) for t in notes)
    )


def _gap_block(section: ResidualAnalysis) -> str:
    gap = section.gap
    if gap.status != "ok":
        if section.point_in_time.status == "ok":
            return _caption(gap.reason)
        return ""
    sev = gap.severity or "info"
    verdict = (
        f'<div class="notice ra-banner" role="note">{GLYPHS.get(sev, "")}'
        f'<p class="notice-sum"><span class="ra-sev">{esc(sev.capitalize())}</span>'
        f"{esc(gap.message or '')}</p></div>"
    )
    rows = [
        ("Days compared", _cell(_span(gap.sample.start, gap.sample.end), f"{gap.sample.n} days")),
        ("In-sample betas, same days", _cell(f"{_pct(gap.in_sample_same_days_annual)} a year")),
        ("Point-in-time betas", _cell(f"{_pct(gap.point_in_time_annual)} a year")),
        (
            "Gap",
            _cell(
                f"{_pct(gap.gap_annual)} a year",
                f"Approximate: z {fmt_num(gap.gap_z, 2)}, p {fmt_pval(gap.gap_p)}.",
            ),
        ),
        (
            "Share of the full-period alpha earned on these days",
            _cell(_share(gap.comparison_share_of_alpha)),
        ),
        ("Survival of the alpha with point-in-time betas", _cell(_kept(gap.survival_ratio))),
    ]
    table = _table(
        "Same-days comparison of in-sample and point-in-time residual return",
        "",
        _kv_rows(rows),
        kv=True,
    )
    return f"{verdict}{table}{_caption(gap.caption)}"


# ------------------------------------------------------------------------------- stability
def _rolling_block(section: ResidualAnalysis) -> str:
    r = section.rolling_alpha
    if r.status != "ok" or not r.dates:
        return empty_state(r.reason or "The rolling alpha is not available.")
    present: list[tuple[int, float, float | None, float | None]] = []
    for i, (a, lo, hi) in enumerate(
        zip(r.alpha_annual, r.ci_low_annual, r.ci_high_annual, strict=True)
    ):
        if a is not None:
            present.append((i, a, lo, hi))
    plot = _plot(
        r.dates,
        [("roll", r.alpha_annual)],
        "Rolling one-year alpha with a pointwise 95 percent band",
        band=(r.ci_low_annual, r.ci_high_annual),
        short=True,
    )
    rows: list[tuple[str, str]] = []
    if present:
        i, a, lo, hi = present[-1]
        alphas = [p[1] for p in present]
        ends = date_long(r.dates[i])
        band = f"Pointwise band {_pct_plain(lo)} to {_pct_plain(hi)}, ending {ends}."
        rows.append(("Latest one-year alpha", _cell(f"{_pct(a)} a year", band)))
        rows.append(
            ("Lowest and highest", _cell(f"{_pct_plain(min(alphas))} to {_pct_plain(max(alphas))}"))
        )
    rows.append(
        (
            "Windows whose band excludes zero",
            _cell(_pct_plain(r.share_excluding_zero), "A descriptive count, not a test."),
        )
    )
    table = _table("Rolling one-year alpha, summary of the estimates", "", _kv_rows(rows), kv=True)
    return f"{plot}{table}{_caption(r.caption)}"


def _windows_block(section: ResidualAnalysis) -> str:
    na = section.non_overlapping
    if na.status != "ok":
        return empty_state(na.reason or "The one-year windows are not available.")
    lead = (
        f"{na.n_reliable} of {na.family_size} separate one-year windows show an alpha different "
        f"from zero, after correcting for testing {na.family_size} windows."
    )
    rows = "".join(
        f'<tr><th scope="row">{esc(_span(w.start, w.end))}'
        f'<span class="ra-sub">{w.n} days</span></th>'
        + _td(_cell(_pct(w.alpha_annual), f"std. error {_pct_plain(w.se_annual)}"))
        + _td(_cell(fmt_num(w.z, 2), f"p {fmt_pval(w.p)}"))
        + _td(_cell(fmt_pval(w.p_adj_bh)))
        + _td(_cell(w.tag or "n/a"))
        + "</tr>"
        for w in na.windows
    )
    head = (
        '<th scope="col" class="c1">Window</th><th scope="col" class="mid">Alpha a year</th>'
        '<th scope="col" class="nar">z</th><th scope="col" class="nar">Adjusted p</th>'
        '<th scope="col" class="nar">Reading</th>'
    )
    table = _table(
        "Separate one-year windows: alpha, standard error, z, p, adjusted p and reading",
        head,
        rows,
    )
    return f'<p class="ra-lead">{esc(lead)}</p>{table}{_caption(na.caption)}'


def _split_block(section: ResidualAnalysis) -> str:
    sh = section.split_half
    if sh.status != "ok":
        return empty_state(sh.reason or "The split-half alphas are not available.")

    def half(
        a: date, b: date, n: int, alpha: float | None, lo: float | None, hi: float | None
    ) -> str:
        return _td(_cell(_pct(alpha), _interval(lo, hi), f"{_span(a, b)}, {n} days"))

    first = half(
        sh.first_start,
        sh.first_end,
        sh.n_first,
        sh.alpha_first_annual,
        sh.alpha_first_ci_low_annual,
        sh.alpha_first_ci_high_annual,
    )
    second = half(
        sh.second_start,
        sh.second_end,
        sh.n_second,
        sh.alpha_second_annual,
        sh.alpha_second_ci_low_annual,
        sh.alpha_second_ci_high_annual,
    )
    head = (
        '<th scope="col" class="c1"><span class="vh">Measure</span></th>'
        '<th scope="col" class="vals">First half</th><th scope="col" class="vals">Second half</th>'
    )
    table = _table(
        "Alpha in each half of the period",
        head,
        f'<tr><th scope="row">Alpha a year</th>{first}{second}</tr>',
    )
    lead = (
        f"Second-half alpha minus first-half alpha: {_pct(sh.difference_annual)} a year "
        f"(p = {fmt_pval(sh.difference_p)})."
    )
    return f'<p class="ra-lead">{esc(lead)}</p>{table}{_caption(sh.caption)}'


def _years_block(section: ResidualAnalysis) -> str:
    cy = section.calendar_years
    if cy.status != "ok" or not cy.years:
        return empty_state(cy.reason or "The calendar-year sums are not available.")
    rows: list[str] = []
    for y in cy.years:
        part = ", part year" if y.partial else ""
        ins = _td(
            _cell(_pct(y.in_sample_sum), f"noise {_pct_plain(y.in_sample_noise_sd)}"),
            f"Sum {y.in_sample_sum:.4f}, noise standard deviation {y.in_sample_noise_sd:.4f}",
        )
        if y.point_in_time_sum is None or y.point_in_time_noise_sd is None:
            pit = _td(_cell("n/a", "No point-in-time days."))
        else:
            sd = y.point_in_time_noise_sd
            pit = _td(
                _cell(
                    _pct(y.point_in_time_sum), f"noise {_pct_plain(sd)}, {y.n_point_in_time} days"
                ),
                f"Sum {y.point_in_time_sum:.4f}, noise standard deviation {sd:.4f}",
            )
        rows.append(
            f'<tr><th scope="row">{y.year}<span class="ra-sub">{y.n} days{part}</span></th>'
            f"{ins}{pit}</tr>"
        )
    head = (
        '<th scope="col" class="c1">Year</th><th scope="col" class="vals">In-sample sum</th>'
        '<th scope="col" class="vals">Point-in-time sum</th>'
    )
    table = _table("Sum of daily residual returns in each calendar year", head, "".join(rows))
    return f"{table}{_caption(cy.caption)}{_caption(YEARS_READING)}"


# ------------------------------------------------------------------------------- diagnostics
_TESTS = (("Ljung-Box", "ljung_box_p"), ("Jarque-Bera", "jarque_bera_p"), ("ARCH", "arch_lm_p"))


def _findings(d: ResidualAlphaDiagnostics, title: str) -> str:
    if d.status != "ok":
        return f"<div><h4>{esc(title)}</h4>{empty_state(d.reason or 'Not available.')}</div>"
    with_p = len(d.findings) == len(_TESTS)
    items: list[str] = []
    for i, text in enumerate(d.findings):
        p = f" ({_TESTS[i][0]} p = {fmt_pval(getattr(d, _TESTS[i][1]))})" if with_p else ""
        items.append(f"<li>{esc(text)}{esc(p)}</li>")
    return f"<div><h4>{esc(title)}</h4><ul>{''.join(items)}</ul></div>"


def _diagnostics_block(section: ResidualAnalysis) -> str:
    names = {"in_sample": "In-sample", "point_in_time": "Point-in-time"}
    cols = "".join(_findings(d, names[d.basis]) for d in section.diagnostics)
    if not cols:
        return ""
    cap = next((d.caption for d in section.diagnostics if d.caption), None)
    return f'<div class="ra-find">{cols}</div>{_caption(cap)}'


# ------------------------------------------------------------------------------- the panel
def _warnings(warnings: Sequence[ReportWarning]) -> tuple[str, str]:
    """(banner above the table for a wipe-out, list under the caveats for every other warning)."""
    banner = "".join(
        f'<div class="notice ra-banner" role="note">{GLYPHS["warning"]}'
        f'<p class="notice-sum"><span class="ra-sev">Warning</span>{esc(w.message)}</p></div>'
        for w in warnings
        if w.code == "residual_wipeout"
    )
    items = "".join(f"<li>{esc(w.message)}</li>" for w in warnings if w.code != "residual_wipeout")
    return banner, (f'<ul class="notes">{items}</ul>' if items else "")


def _fold(section: ResidualAnalysis, report: FactorReport) -> str:
    paras: list[str | None] = [section.in_sample.caption]
    if section.point_in_time.status == "ok":
        paras.append(section.point_in_time.caption)
    for key in FOLD_LABELS:
        paras.append(report.label_text.get(key) or RESIDUAL_LABEL_TEXT.get(key, ""))
    seen: list[str] = []
    for text in paras:
        if text and text not in seen:
            seen.append(text)
    inner = "".join(f"<p>{esc(p)}</p>" for p in seen)
    return (
        '<div class="foot"><details class="how"><summary>How this is computed</summary>'
        f"{inner}</details></div>"
    )


def render_residual_alpha_panel(report: FactorReport) -> str | None:
    """The panel's HTML, or ``None`` when the section was not computed."""
    section = report.residual
    if section is None:
        return None
    head = panel_head(PANEL_ID, TITLE, section.question or QUESTION)
    if section.status != "ok":
        reason = section.reason or "Residual analysis is unavailable."
        return panel_section(PANEL_ID, head, empty_state(reason, NEXT_STEP))
    banner, other_warnings = _warnings(section.warnings)
    caveats = "".join(f"<li>{esc(c)}</li>" for c in section.caveats)
    body = (
        f"{banner}"
        "<h3>In-sample against point-in-time</h3>"
        f"{_compare_table(section)}"
        "<h3>Cumulative residual return</h3>"
        f"{_chart_block(section)}"
        f"{_gap_block(section)}"
        "<h3>Is the alpha stable?</h3>"
        f"{_rolling_block(section)}"
        f"{_windows_block(section)}"
        f"{_split_block(section)}"
        f"{_years_block(section)}"
        f"{_caption(STABILITY_CAUTION)}"
        "<h3>Checks on the residual returns</h3>"
        f"{_diagnostics_block(section)}"
        "<h3>What to keep in mind</h3>"
        f'<ul class="notes">{caveats}</ul>{other_warnings}'
        f"{_fold(section, report)}"
    )
    return panel_section(PANEL_ID, head, body)


register_panel("residual_alpha", 710, render_residual_alpha_panel, css=PANEL_CSS)
