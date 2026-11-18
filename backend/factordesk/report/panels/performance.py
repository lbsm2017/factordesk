"""Static HTML panel of the ``performance`` section (schema v3 contract; sixth optional section).

Registered at position 450 as ``performance``, element id ``performance``: right after Price. The
price panel plots the path of the stock; the four numbers here read straight off that path (growth,
swings, worst fall), and they come before the factor panels that explain where the return came
from. Positions between the numbers of contract SC4 are free for later panels, and 450 changes no
existing position.

Contents, top to bottom: a four-cell strip in the style of the headline strip (Return a year,
Volatility a year, Sharpe ratio, Worst fall), one sentence on the window, a small table of the five
largest falls, one footnote, and a folded "How this is computed". Everything described is past
data; the panel says nothing about the future. A section that is not ``ok`` shows its reason as the
empty state and no numbers. Only existing classes and tokens are used (the panel's stylesheet
only changes the strip from five to four cells); a larger visual redesign will restyle it.
"""

from __future__ import annotations

from factordesk.report.panel_registry import register_panel
from factordesk.report.render_html import (
    date_long,
    empty_state,
    esc,
    fmt_num,
    fmt_pct,
    panel_head,
    panel_section,
)
from factordesk.report.schema import FactorReport
from factordesk.report.sections.performance import (
    DrawdownEpisodeInfo,
    PerformanceDrawdown,
    PerformanceSection,
)

PANEL_ID = "performance"
TITLE = "Performance"
QUESTION = "How has the stock performed over the analysed window?"
NEXT_STEP = "Choose a longer date range or another ticker, then run the report again."
FOOTNOTE = "Past performance does not predict future performance."
NOTES = {
    "return": "Compound growth over the window",
    "volatility": "Typical size of daily swings, scaled to a year",
    "sharpe": "Return above the risk-free rate per unit of risk; the interval {verb} zero",
    "sharpe_undefined": "Not defined: the daily returns do not vary",
    "no_fall": "No fall from an earlier high",
}
"""Short lines under the four values."""
HOW = (
    "The window is the analysed sample: the same trading days as the factor regression, so it "
    "moves with the date range. Returns are simple daily total returns from adjusted close.",
    "Return a year is the compound annual growth rate: the product of one plus each daily "
    "return, raised to 252 divided by the number of days, minus one. The total return over the "
    "window and the average daily return times 252 are the two other ways to state the same "
    "history.",
    "Volatility a year is the sample standard deviation of daily returns times the square root "
    "of 252.",
    "The Sharpe ratio is the average daily excess return (stock return minus the risk-free rate "
    "of the factor file) divided by its standard deviation, times the square root of 252. The "
    "95% interval is the ratio plus or minus 1.96 standard errors. The standard error is the "
    "approximate closed form of Lo (2002); it assumes independent, identically distributed daily "
    "returns, so it ignores autocorrelation, fat tails and volatility clustering, and the "
    "interval is approximate. The ratio is not defined when the daily returns do not vary.",
    "Worst fall is the largest drop of the compounded return path (starting at 1) from a running "
    "high. An episode runs from a high until the path first regains it; the table lists the five "
    "deepest, which do not overlap. Days are trading days of the analysed sample.",
)
HEADINGS = ("Fall", "Peak", "Trough", "Recovered", "Peak to trough", "Trough to recovery")
HEADING_NOTE = "Largest falls"

CSS = """
#performance .kpis dl { grid-template-columns: repeat(4, minmax(0, 1fr)); }
#performance .perf-line { margin-top: var(--s-3); color: var(--ink-2); max-width: 76ch; }
#performance .perf-table-title { margin-top: var(--s-5); }
@media screen and (max-width: 719px) {
  #performance .kpis dl { grid-template-columns: 1fr 1fr; }
  #performance .kpi:last-child { grid-column: auto; border-left: 1px solid var(--grid); }
}
@media print {
  #performance .kpis dl { grid-template-columns: repeat(4, 1fr); }
  #performance .kpi:nth-child(n+4) { border-top: 0; }
  #performance .kpi:nth-child(4) { border-left: 1px solid var(--grid); }
}
"""


def _days(n: int | None) -> str:
    return "n/a" if n is None else f"{n:,}"


def _fall_note(dd: PerformanceDrawdown) -> str:
    if dd.peak_date is None or dd.trough_date is None:
        return NOTES["no_fall"]
    text = f"Peak {date_long(dd.peak_date)}, trough {date_long(dd.trough_date)}, "
    if dd.recovery_date is None:
        return text + "not recovered"
    return text + f"recovered {date_long(dd.recovery_date)}"


def _cells(section: PerformanceSection) -> list[tuple[str, str, str, str]]:
    returns, sharpe, dd = section.returns, section.sharpe, section.drawdown
    assert returns is not None and sharpe is not None and dd is not None
    if sharpe.ratio_annual is None or sharpe.ci_includes_zero is None:
        sharpe_value, sharpe_note, sharpe_cls = "n/a", NOTES["sharpe_undefined"], "ns"
    else:
        verb = "includes" if sharpe.ci_includes_zero else "does not include"
        sharpe_value = fmt_num(sharpe.ratio_annual, 2)
        sharpe_note, sharpe_cls = NOTES["sharpe"].format(verb=verb), ""
    return [
        ("Return a year", fmt_pct(returns.cagr, 1), NOTES["return"], ""),
        (
            "Volatility a year",
            fmt_pct(section.volatility_annual, 1, signed=False),
            NOTES["volatility"],
            "",
        ),
        ("Sharpe ratio", sharpe_value, sharpe_note, sharpe_cls),
        ("Worst fall", fmt_pct(dd.max_drawdown, 1), _fall_note(dd), ""),
    ]


def _strip(section: PerformanceSection) -> str:
    body = "".join(
        f'<div class="kpi {cls}"><dt>{esc(lab)}</dt><dd class="v">{esc(val)}</dd>'
        f'<dd class="n">{esc(note)}</dd></div>'
        for lab, val, note, cls in _cells(section)
    )
    return f'<div class="kpis" aria-label="Performance statistics"><dl>{body}</dl></div>'


def _window_line(section: PerformanceSection) -> str:
    periods, returns, sharpe = section.periods, section.returns, section.sharpe
    assert periods is not None and returns is not None and sharpe is not None
    parts = [
        f"Over {periods.years:.1f} years ({periods.n_days:,} trading days, "
        f"{date_long(periods.start)} to {date_long(periods.end)}) the stock returned "
        f"{fmt_pct(returns.cumulative_return, 1)} in total; the average daily return times 252 "
        f"is {fmt_pct(returns.mean_return_annual, 1)}."
    ]
    if sharpe.ci95_low is not None and sharpe.ci95_high is not None:
        parts.append(
            f"The 95% interval of the Sharpe ratio runs from {fmt_num(sharpe.ci95_low, 2)} to "
            f"{fmt_num(sharpe.ci95_high, 2)}; it is approximate and assumes independent daily "
            "returns."
        )
    return f'<p class="perf-line">{esc(" ".join(parts))}</p>'


def _episode_row(e: DrawdownEpisodeInfo) -> str:
    recovered = "not recovered" if e.recovery_date is None else date_long(e.recovery_date)
    cells = [
        fmt_pct(e.depth, 1),
        date_long(e.peak_date),
        date_long(e.trough_date),
        recovered,
        _days(e.days_peak_to_trough),
        _days(e.days_trough_to_recovery),
    ]
    tds = "".join(f'<td class="num">{esc(c)}</td>' for c in cells[1:])
    return f'<tr><th scope="row">{esc(cells[0])}</th>{tds}</tr>'


def _table(dd: PerformanceDrawdown) -> str:
    if not dd.episodes:
        return ""
    heads = "".join(f'<th scope="col" class="num">{esc(h)}</th>' for h in HEADINGS[1:])
    rows = "".join(_episode_row(e) for e in dd.episodes)
    label = "Largest falls from a high, deepest first"
    return (
        f'<h3 class="reg-title perf-table-title">{esc(HEADING_NOTE)}</h3>'
        f'<div class="scroll-x" tabindex="0" role="region" aria-label="{esc(label)}, scrolls '
        f'sideways"><table class="reg"><caption class="vh">{esc(label)}</caption><thead><tr>'
        f'<th scope="col">{esc(HEADINGS[0])}</th>{heads}</tr></thead><tbody>{rows}</tbody>'
        "</table></div>"
    )


def _foot() -> str:
    paras = "".join(f"<p>{esc(p)}</p>" for p in HOW)
    return (
        f'<div class="foot"><p>{esc(FOOTNOTE)}</p><details class="how"><summary>How this is '
        f"computed</summary>{paras}</details></div>"
    )


def render_performance_panel(report: FactorReport) -> str | None:
    """The panel's HTML, or ``None`` when the section was not computed."""
    section = report.performance
    if section is None:
        return None
    head = panel_head(PANEL_ID, TITLE, QUESTION)
    if section.status != "ok":
        return panel_section(PANEL_ID, head, empty_state(section.reason or "", NEXT_STEP))
    assert section.drawdown is not None
    body = _strip(section) + _window_line(section) + _table(section.drawdown) + _foot()
    return panel_section(PANEL_ID, head, body)


register_panel("performance", 450, render_performance_panel, css=CSS)
