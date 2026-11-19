"""Static HTML panel of the ``alpha_strip`` section (E1, E9a).

Registered at position 502 as ``alpha_strip``, right after the exposures. One table row per model
in the fixed order CAPM, FF3, FF5, FF6: alpha a year, its t-statistic, R² and adjusted R². No row
is ranked, marked or highlighted. The fixed caption sits under the table, then the note of the
report's model and the count of rows the strip left out.
"""

from __future__ import annotations

from factordesk.report.panel_registry import register_panel
from factordesk.report.render_html import (
    empty_state,
    esc,
    fmt_num,
    fmt_pct,
    fmt_tstat,
    panel_head,
    panel_section,
)
from factordesk.report.schema import FactorReport
from factordesk.report.sections.alpha_strip import AlphaStrip

PANEL_ID = "alpha-strip"
TITLE = "Alpha across models"
QUESTION = "How does alpha change when the model has more factors?"
HEADINGS = ("Model", "Alpha a year", "t", "R²", "Adjusted R²")


def dropped_text(n_dropped: int) -> str:
    """The count of sample rows the strip left out."""
    if n_dropped == 0:
        return "No rows of the sample were left out."
    rows = "row" if n_dropped == 1 else "rows"
    return (
        f"{n_dropped} {rows} of the sample left out: a factor of one of the models has no value "
        "there, so every model uses the same rows."
    )


def _table(section: AlphaStrip) -> str:
    heads = "".join(f'<th scope="col" class="num">{esc(h)}</th>' for h in HEADINGS[1:])
    rows = "".join(
        f'<tr><th scope="row">{esc(r.label)}</th>'
        f'<td class="num">{esc(fmt_pct(r.alpha_annual))}</td>'
        f'<td class="num">{esc(fmt_tstat(r.alpha_t))}</td>'
        f'<td class="num">{esc(fmt_num(r.r2, 3))}</td>'
        f'<td class="num">{esc(fmt_num(r.adj_r2, 3))}</td></tr>'
        for r in section.rows
    )
    label = "Alpha, t, R² and adjusted R² of each model on the same rows"
    return (
        f'<div class="scroll-x" tabindex="0" role="region" aria-label="{esc(label)}, scrolls '
        f'sideways"><table class="reg"><caption class="vh">{esc(label)}</caption><thead><tr>'
        f'<th scope="col">{esc(HEADINGS[0])}</th>{heads}</tr></thead><tbody>{rows}</tbody>'
        "</table></div>"
    )


def render_alpha_strip_panel(report: FactorReport) -> str | None:
    """The panel's HTML, or ``None`` when the section was not computed."""
    section = report.alpha_strip
    if section is None:
        return None
    head = panel_head(PANEL_ID, TITLE, QUESTION)
    if section.status != "ok":
        return panel_section(PANEL_ID, head, empty_state(section.reason or ""))
    body = (
        f"<p>{esc(section.intro)}</p>"
        + _table(section)
        + f'<div class="foot"><p>{esc(section.caption)}</p>'
        f"<p>{esc(section.model_note)}</p><p>{esc(dropped_text(section.n_dropped))}</p></div>"
    )
    return panel_section(PANEL_ID, head, body)


register_panel("alpha_strip", 502, render_alpha_strip_panel)
