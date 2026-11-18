"""Static HTML panel of the ``world_beta`` section (docs/validation/world-beta-handoff WB3).

Registered at position 540 as ``world_beta``, element id ``world-beta``. It follows the three
panels that qualify the betas of Exposures (lead-lag 510, shrunk 520, fragility 530) and comes
before Return contribution: it reads the market beta of Exposures against a second market, so it
sits with them, after the panels that qualify the five-factor betas themselves.

The panel is the plain comparison sentence, a two-row table (against the world, ACWI; against the
US market on the same days), and a footnote about the proxy and the timing caveat, with the method
folded under "How this is computed". It uses the existing static classes only.
"""

from __future__ import annotations

from factordesk.report.panel_registry import register_panel
from factordesk.report.render_html import (
    date_long,
    empty_state,
    esc,
    fmt_num,
    fmt_pct,
    footnote,
    panel_head,
    panel_section,
)
from factordesk.report.schema import FactorReport
from factordesk.report.sections.world_beta import WORLD_BETA_SECTION, BetaFit, WorldBetaSection

PANEL_ID = "world-beta"
TITLE = "World beta (quick estimate)"
QUESTION = "How much does this stock move with the world market, next to the US market?"
NEXT_STEP_SHORT = "Choose a longer date range and run the report again."
NEXT_STEP_FAILED = "Run the report again later; the rest of the report is not affected."
DEFAULT_DESC = "Descriptive, in-sample, not predictive."
ROW_WORLD = "Against the world (ACWI)"
ROW_US = "Against the US market, same days"
CAPTION = "Beta, 95% interval, R squared and days of the stock against ACWI and the US market"
PROXY_SHORT = "ACWI is an ETF used as a stand-in for the MSCI ACWI index."

CSS = "table.reg.wb{min-width:0}"


def _interval(fit: BetaFit) -> str:
    return f"[{fmt_num(fit.ci95_low, 2)}, {fmt_num(fit.ci95_high, 2)}]"


def _row(label: str, fit: BetaFit, days: str) -> str:
    return (
        f'<tr><th scope="row">{esc(label)}</th>'
        f'<td class="num strong">{esc(fmt_num(fit.beta, 2))}</td>'
        f'<td class="num">{esc(_interval(fit))}</td>'
        f'<td class="num">{esc(fmt_num(fit.r2, 2))}</td>'
        f'<td class="num">{esc(days)}</td></tr>'
    )


def _table(s: WorldBetaSection, world: BetaFit, us: BetaFit) -> str:
    days = f"{s.sample.n:,}"
    return (
        '<div class="scroll-x" tabindex="0" role="region" aria-label="World beta and US market '
        'beta, scrolls sideways"><table class="reg wb">'
        f'<caption class="vh">{esc(CAPTION)}</caption>'
        '<thead><tr><th scope="col">Beta against</th><th scope="col" class="num">Beta</th>'
        '<th scope="col" class="num">95% interval</th><th scope="col" class="num">R squared</th>'
        '<th scope="col" class="num">Days</th></tr></thead>'
        f"<tbody>{_row(ROW_WORLD, world, days)}{_row(ROW_US, us, 'same')}</tbody></table></div>"
    )


def _how(s: WorldBetaSection, world: BetaFit) -> list[str]:
    first = date_long(s.sample.start) if s.sample.start else "n/a"
    last = date_long(s.sample.end) if s.sample.end else "n/a"
    alpha = (
        f"Alpha against the world is {fmt_pct(world.alpha_annual)} a year"
        + (f" (HAC t {fmt_num(world.alpha_t, 1)})" if world.alpha_t is not None else "")
        + "; it is secondary and is not the point of this panel."
    )
    method = (
        "Each beta is the slope of a regression of the stock's daily excess return (return minus "
        "the daily US risk-free rate) on one daily excess return, with an intercept: ACWI's in "
        "the first row, the US market factor Mkt-RF of the Fama-French file in the second. Both "
        f"use the same {s.sample.n:,} days, {first} to {last}: the days of the analysed sample "
        "that ACWI also has. Standard errors are Newey-West (HAC) with "
        f"{s.hac_lags} lags; intervals are 95% and normal."
    )
    reading = (
        "The comparison says 'about the same' when the two intervals overlap, and otherwise "
        "which beta is higher; it is a reading of the intervals, not a test."
    )
    extra = [method, reading, alpha]
    if s.n_not_in_benchmark:
        extra.append(
            f"{s.n_not_in_benchmark:,} days of the analysed sample were left out because ACWI "
            "has no usable return for them (it started later, or a day is missing)."
        )
    extra.extend(s.audit_warnings)
    return extra


def _foot(report: FactorReport, s: WorldBetaSection, world: BetaFit | None) -> str:
    texts = {**WORLD_BETA_SECTION.label_text, **report.label_text}
    sentences = [texts.get("L-DESC", DEFAULT_DESC)]
    sentences += [texts[k] for k in s.labels if k != "L-DESC" and k in texts]
    if s.acwi_last_date is not None:
        sentences.append(f"ACWI data ends {date_long(s.acwi_last_date)}.")
    if s.acwi_note:
        sentences.append(s.acwi_note)
    more = _how(s, world) if world is not None else []
    return footnote(" ".join(sentences), more)


def render_world_beta_panel(report: FactorReport) -> str | None:
    """The panel's HTML, or ``None`` when the section was not computed."""
    s = report.world_beta
    if s is None:
        return None
    head = panel_head(PANEL_ID, TITLE, QUESTION)
    if s.status != "ok" or s.world is None or s.us_market is None:
        step = NEXT_STEP_SHORT if s.status == "insufficient_data" else NEXT_STEP_FAILED
        body = empty_state(s.reason or "", step)
        return panel_section(PANEL_ID, head, body + _foot(report, s, None))
    body = (
        f'<p class="reading">{esc(s.comparison_text)}</p>'
        + _table(s, s.world, s.us_market)
        + _foot(report, s, s.world)
    )
    return panel_section(PANEL_ID, head, body)


register_panel("world_beta", 540, render_world_beta_panel, css=CSS)
