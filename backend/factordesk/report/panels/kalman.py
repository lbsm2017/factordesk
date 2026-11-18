"""Static HTML panel of the ``kalman_betas`` section (contract SC2.3).

Spec: ``docs/specs/kalman-betas.md`` (KB5 band, KB8.3 outputs and labels); design:
``docs/design/report-design.md`` (revision 2). Registered at position 810 as ``kalman``.

The panel is a table of five small multiples, one row per factor, drawn like the rolling panel:
the filtered beta line with its model-based 95% band, then fixed number columns Latest, sd and the
band as text. Below it a table of the yearly re-estimates (vintages). Every row uses the same
vertical span, centred on its own values. The first 503 rows of the series are warm-up (null), so
each chart starts at the first estimate. A section that is not ``ok`` shows its reason as the
empty state, with one next step and no numbers.

Payload: each series is thinned to about 300 points (min-max, so spikes survive) before it is
written as an SVG path; the whole panel stays well under 100 kB for any sample length.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from datetime import date

from factordesk.report.panel_registry import register_panel
from factordesk.report.render_html import (
    PLAIN,
    date_long,
    empty_state,
    esc,
    fmt_pct,
    fmt_signed,
    footnote,
    panel_head,
    panel_section,
)
from factordesk.report.schema import FACTOR_NAMES, FactorReport
from factordesk.report.sections.kalman import (
    KALMAN_SECTION,
    WARNING_TEXT,
    KalmanBetaSeries,
    KalmanVintage,
)

PANEL_ID = "kalman"
TITLE = "Kalman-filter betas"
QUESTION = "How did the exposures move, using only data up to each date?"

MAX_POINTS = 300
"""Points per series after thinning (the thinned series has at most this many plus two)."""

NEXT_STEP = {
    "insufficient_data": (
        "This view needs a longer history. Choose an earlier start date so the sample has at "
        "least {rows} trading days."
    ),
    "failed": (
        "Check the price and factor data for gaps or constant values, or choose a different "
        "date range."
    ),
}

BOUND_WORDS = {
    "upper": "at its upper limit: the filter follows daily noise",
    "zero": "at zero: no drift found",
}

CSS = """
.bars.cols-3.kalman .plot.mini { margin-left: 52px; }
.bars.kalman .kx { position: relative; height: 26px; margin-left: 52px; }
@media screen and (max-width: 719px) {
  .bars.cols-3.kalman tr { grid-template-columns: minmax(0, 1fr) 52px 52px 122px; }
  .bars.cols-3.kalman .plot.mini { margin-left: 44px; }
  .bars.kalman .kx { margin-left: 0; }
}
.kalman-vintages { margin-top: var(--s-2); }
.kalman-vintages .reg { min-width: 640px; }
.kalman-vintages td.num .sub { white-space: nowrap; }
"""

Point = tuple[int, float, float, float]
"""One estimate: row index, beta, band low, band high."""


def _decimate(points: list[Point]) -> list[Point]:
    """Min-max thinning by beta: each bucket keeps its lowest and highest point, in order."""
    n = len(points)
    if n <= MAX_POINTS:
        return points
    size = math.ceil(n / (MAX_POINTS // 2))
    keep = {0, n - 1}
    for lo in range(0, n, size):
        idx = range(lo, min(lo + size, n))
        keep.add(min(idx, key=lambda i: points[i][1]))
        keep.add(max(idx, key=lambda i: points[i][1]))
    return [points[i] for i in sorted(keep)]


def _path(points: Sequence[tuple[float, float]]) -> str:
    return "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in points)


def _edge(x: float) -> str:
    """Tick labels at the plot edges are anchored inward so they never overflow."""
    return "edge-l" if x < 3 else ("edge-r" if x > 97 else "")


def _year_ticks(d0: date, d1: date) -> list[date]:
    """1 January of each calendar year inside the span, thinned so labels never collide."""
    years = [date(y, 1, 1) for y in range(d0.year + 1, d1.year + 1)]
    years = [d for d in years if d0 < d <= d1]
    step = max(1, math.ceil(len(years) / 7))
    return years[::step]


def _sd(value: float) -> str:
    """A standard deviation to three significant digits (0.0736, 0.126)."""
    if not math.isfinite(value):
        return "n/a"
    if value <= 0:
        return "0"
    digits = max(0, 2 - math.floor(math.log10(value)))
    return f"{value:.{digits}f}"


def _lam(value: float) -> str:
    """The drift rate as a plain decimal to two significant digits (0.00000095)."""
    if not math.isfinite(value):
        return "n/a"
    if value <= 0:
        return "0"
    digits = max(0, 1 - math.floor(math.log10(value)))
    return f"{value:.{digits}f}"


def _slot(name: str) -> int:
    return FACTOR_NAMES.index(name) + 1 if name in FACTOR_NAMES else 1


def _empty_panel(section: KalmanBetaSeries) -> str:
    step = NEXT_STEP.get(section.status, NEXT_STEP["failed"]).format(rows=section.training_rows)
    return empty_state(section.reason or "The Kalman-filter betas were not computed.", step)


def _chart_rows(section: KalmanBetaSeries) -> tuple[list[str], str, date] | None:
    """Table rows, the date axis cell and the first plotted date; None when nothing is drawn."""
    dates = section.dates
    series: dict[str, list[Point]] = {}
    for name in section.betas:
        pts: list[Point] = []
        for i, (b, lo, hi) in enumerate(
            zip(section.betas[name], section.band_low[name], section.band_high[name], strict=True)
        ):
            if b is not None and lo is not None and hi is not None:
                pts.append((i, b, lo, hi))
        if pts:
            series[name] = pts
    if not series:
        return None
    span = max(
        max(max(p[3] for p in pts) - min(p[2] for p in pts) for pts in series.values()) * 1.08,
        1e-9,
    )
    i0 = min(pts[0][0] for pts in series.values())
    o0 = dates[i0].toordinal()
    o1 = max(dates[-1].toordinal(), o0 + 1)

    def pct_of(d: date) -> float:
        return (d.toordinal() - o0) / (o1 - o0) * 100

    ticks = _year_ticks(dates[i0], dates[-1])
    marks = [v.valid_from for v in section.vintages[1:] if dates[i0] < v.valid_from <= dates[-1]]
    guides = "".join(
        f'<line class="grid" x1="{pct_of(d) * 10:.1f}" x2="{pct_of(d) * 10:.1f}" y1="0" y2="100"/>'
        for d in ticks
    ) + "".join(
        f'<line class="cutline" x1="{pct_of(d) * 10:.1f}" x2="{pct_of(d) * 10:.1f}" '
        'y1="0" y2="100"/>'
        for d in marks
    )
    rows: list[str] = []
    for name, pts in series.items():
        mid = (max(p[3] for p in pts) + min(p[2] for p in pts)) / 2
        lo_v, hi_v = mid - span / 2, mid + span / 2

        def y_of(v: float, lo_v: float = lo_v, hi_v: float = hi_v) -> float:
            return 100 - (v - lo_v) / (hi_v - lo_v) * 100

        sp = _decimate(pts)
        xs = [pct_of(dates[p[0]]) * 10 for p in sp]
        upper = [(x, y_of(p[3])) for x, p in zip(xs, sp, strict=True)]
        lower = [(x, y_of(p[2])) for x, p in zip(xs, sp, strict=True)][::-1]
        band = _path(upper + lower) + "Z"
        line = _path([(x, y_of(p[1])) for x, p in zip(xs, sp, strict=True)])
        zero = (
            f'<line class="zero" x1="0" x2="1000" y1="{y_of(0):.2f}" y2="{y_of(0):.2f}"/>'
            if lo_v < 0 < hi_v
            else ""
        )
        c = _slot(name)
        label = f"Kalman-filter beta to {name}, with a 95 percent band"
        svg = (
            '<svg class="line-svg" viewBox="0 0 1000 100" preserveAspectRatio="none" role="img" '
            f'aria-label="{esc(label)}">{guides}{zero}<path class="band c{c}" d="{band}"/>'
            f'<path class="rline c{c}" d="{line}"/></svg>'
        )
        yl = [(hi_v, "top"), (lo_v, "bot")]
        if lo_v < 0 < hi_v and min(abs(hi_v), abs(lo_v)) > span * 0.35:
            yl.append((0.0, "mid"))
        ylab = "".join(
            f'<span class="yl {k}" style="top:{y_of(t):.2f}%">'
            f"{fmt_signed(t, 2) if abs(t) > 1e-9 else '0'}</span>"
            for t, k in yl
        )
        latest = section.latest[name]
        plain = PLAIN.get(name, "")
        sub = f'<span class="sub">{esc(plain)}</span>' if plain else ""
        key = (
            f'<svg class="key" aria-hidden="true"><rect class="cat c{c}" width="8" height="8" '
            'rx="1"/></svg>'
        )
        rows.append(
            f'<tr><th scope="row"><span class="fname">{key}{esc(name)}</span>{sub}</th>'
            f'<td class="plot-cell"><div class="plot mini">{svg}'
            f'<div class="ylabels" aria-hidden="true">{ylab}</div></div></td>'
            f'<td class="num strong">{esc(fmt_signed(latest.beta))}</td>'
            f'<td class="num">{esc(_sd(latest.sd))}</td>'
            f'<td class="num range">{esc(fmt_signed(latest.band_low))} to '
            f"{esc(fmt_signed(latest.band_high))}</td></tr>"
        )
    xlab = "".join(
        f'<span class="xl {_edge(pct_of(d))}" style="left:{pct_of(d):.2f}%">{d.year}</span>'
        for d in ticks
    )
    return rows, xlab, dates[i0]


def _vintage_row(v: KalmanVintage) -> str:
    bound = BOUND_WORDS.get(v.lam_at_bound, "")
    flag = f'<span class="sub">{esc(bound)}</span>' if bound else ""
    window = "n/a" if v.w_eq is None else f"{v.w_eq:,.0f}"
    return (
        f'<tr><th scope="row">{v.rows:,}</th>'
        f'<td class="num">{esc(_lam(v.lam))}{flag}</td>'
        f'<td class="num">{esc(window)}</td>'
        f'<td class="num">{esc(fmt_pct(v.resid_vol_ann, 1, signed=False))}</td>'
        f'<td class="num"><time datetime="{v.valid_from.isoformat()}">'
        f"{esc(date_long(v.valid_from))}</time></td>"
        f'<td class="num"><time datetime="{v.valid_to.isoformat()}">'
        f"{esc(date_long(v.valid_to))}</time></td></tr>"
    )


def _vintage_table(section: KalmanBetaSeries) -> str:
    heads = (
        "Rows used",
        "Drift rate",
        "Equivalent window, days",
        "Residual volatility, a year",
        "Valid from",
        "Valid to",
    )
    cols = "".join(f'<th scope="col">{esc(h)}</th>' for h in heads)
    body = "".join(_vintage_row(v) for v in section.vintages)
    label = "Yearly re-estimates of the drift rate"
    return (
        "<h3>Yearly re-estimates</h3>"
        '<div class="scroll-x kalman-vintages" tabindex="0" role="region" '
        f'aria-label="{esc(label)}, scrolls sideways"><table class="reg"><thead><tr>{cols}'
        f"</tr></thead><tbody>{body}</tbody></table></div>"
    )


def _fold(section: KalmanBetaSeries) -> list[str]:
    texts = KALMAN_SECTION.label_text
    more = [texts[k] for k in section.labels if k in texts and k != "L-KTAIL"]
    more.append(
        "Every row uses the same vertical span, centred on its own values, so wiggles compare "
        "across factors."
    )
    more.append(
        "The drift rate is the weight the filter gives to a new day. It is re-estimated each "
        "year from the data up to that date, and the equivalent window is the rolling window "
        "that would smooth about as much. Each row of the table gives the estimate in force "
        "between its two dates."
    )
    more.extend(texts[k] for k in section.labels if k == "L-KTAIL" and k in texts)
    more.extend(WARNING_TEXT.get(w, w) for w in section.warnings)
    return more


def render_kalman_panel(report: FactorReport) -> str | None:
    """The panel's HTML, or ``None`` when the section was not computed."""
    section = report.kalman_betas
    if section is None:
        return None
    head = panel_head(PANEL_ID, TITLE, QUESTION)
    drawn = _chart_rows(section) if section.status == "ok" else None
    if drawn is None:
        body = (
            _empty_panel(section)
            if section.status != "ok"
            else empty_state(
                "No estimate yet: every date is still in warm-up.",
                "Choose an earlier start date so the sample is longer.",
            )
        )
        return panel_section(PANEL_ID, head, body)
    rows, xlab, first = drawn
    table = (
        '<table class="bars cols-3 rolling kalman">'
        '<caption class="vh">Kalman-filter beta per factor with a model-based 95% band; '
        "latest value, its standard deviation and the band</caption>"
        '<thead><tr><th scope="col">Factor</th><th scope="col" class="plot-h">'
        '<span class="vh">Chart</span></th><th scope="col" class="num">Latest</th>'
        '<th scope="col" class="num" title="Model standard deviation of the latest beta">sd</th>'
        '<th scope="col" class="num">95% band</th>'
        f"</tr></thead><tbody>{''.join(rows)}</tbody>"
        '<tfoot><tr class="axis-row" aria-hidden="true"><td></td>'
        f'<td class="axis time"><div class="kx">{xlab}</div></td><td colspan="3"></td>'
        "</tr></tfoot></table>"
    )
    visible = (
        f"Each point uses only data up to its date, so the chart starts at the first estimate, "
        f"{date_long(first)}. Latest is stamped {date_long(section.dates[-1])}. Dashed vertical "
        "lines mark the yearly re-estimates, where a line can jump."
    )
    note = footnote(visible, _fold(section))
    return panel_section(PANEL_ID, head, table + _vintage_table(section) + note)


register_panel("kalman", 810, render_kalman_panel, css=CSS)
