"""Static HTML panel of the ``world_beta`` section (docs/validation/world-beta-handoff WB3).

Registered at position 505 as ``world_beta``, element id ``world-beta``, right after the factor
exposures (500) and before lead-lag (510): it reads the betas against a second market once the
factor betas have been seen. The React page uses the same position.

The panel is the plain comparison sentence, a table (against the world, ACWI; against Europe,
IEUR; against the US market on the same days) and a footnote about the proxies and the timing
caveat, with the method folded under "How this is computed". The Europe row appears when the
``europe`` block is ``ok``; when its days differ from the ACWI days, a fourth row gives the US
market beta on the Europe days. A Europe block that is not ``ok`` shows its reason in a sentence
and the rest of the panel is unchanged. It uses the existing static classes only.
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
from factordesk.report.sections.world_beta import (
    WORLD_BETA_SECTION,
    BetaFit,
    ProxyBeta,
    WorldBetaSection,
)

PANEL_ID = "world-beta"
TITLE = "World beta (quick estimate)"
QUESTION = "How much does this stock move with the world market, next to the US market?"
NEXT_STEP_SHORT = "Choose a longer date range and run the report again."
NEXT_STEP_FAILED = "Run the report again later; the rest of the report is not affected."
NEXT_STEP_UNFIXABLE = "The rest of the report is not affected."
DEFAULT_DESC = "Descriptive, in-sample, not predictive."
ROW_WORLD = "Against the world (ACWI)"
ROW_US = "Against the US market, same days"
ROW_EUROPE = "Europe"
ROW_EUROPE_SUB = "IEUR, MSCI Europe stand-in"
ROW_US_EUROPE = "Against the US market, same days as Europe"
CAPTION = "Beta, 95% interval, R squared and days of the stock against ACWI and the US market"
CAPTION_EUROPE = (
    "Beta, 95% interval, R squared and days of the stock against ACWI, Europe (IEUR) and the "
    "US market"
)
PROXY_SHORT = "ACWI is an ETF used as a stand-in for the MSCI ACWI index."
EUROPE_PROXY = (
    "Europe uses IEUR, the iShares Core MSCI Europe ETF, as a stand-in for the MSCI Europe "
    "index in the same way; its history starts in June 2014, so it covers fewer days than ACWI "
    "for a long analysis."
)

CSS = "table.reg.wb{min-width:0}"


def _interval(fit: BetaFit) -> str:
    return f"[{fmt_num(fit.ci_low, 2)}, {fmt_num(fit.ci_high, 2)}]"


def _row(label: str, fit: BetaFit, days: str, sub: str = "") -> str:
    tag = f' <span class="sub">{esc(sub)}</span>' if sub else ""
    return (
        f'<tr><th scope="row">{esc(label)}{tag}</th>'
        f'<td class="num strong">{esc(fmt_num(fit.beta, 2))}</td>'
        f'<td class="num">{esc(_interval(fit))}</td>'
        f'<td class="num">{esc(fmt_num(fit.r2, 2))}</td>'
        f'<td class="num">{esc(days)}</td></tr>'
    )


def _europe_ok(s: WorldBetaSection) -> ProxyBeta | None:
    """The Europe block when it carries a result, else ``None``."""
    e = s.europe
    if e is None or e.status != "ok" or e.benchmark is None or e.us_market is None:
        return None
    return e


def _rows(s: WorldBetaSection) -> str:
    """The table rows: world, Europe, then the US market on the same days."""
    rows: list[str] = []
    europe = _europe_ok(s)
    if s.world is not None and s.us_market is not None:
        rows.append(_row(ROW_WORLD, s.world, f"{s.sample.n:,}"))
    if europe is not None and europe.benchmark is not None and europe.us_market is not None:
        rows.append(_row(ROW_EUROPE, europe.benchmark, f"{europe.n_days:,}", ROW_EUROPE_SUB))
    if s.us_market is not None:
        rows.append(_row(ROW_US, s.us_market, "same"))
    if europe is not None and europe.us_market is not None and europe.us_market != s.us_market:
        rows.append(_row(ROW_US_EUROPE, europe.us_market, f"{europe.n_days:,}"))
    return "".join(rows)


def _table(rows: str, caption: str) -> str:
    return (
        '<div class="scroll-x" tabindex="0" role="region" aria-label="World beta and US market '
        'beta, scrolls sideways"><table class="reg wb">'
        f'<caption class="vh">{esc(caption)}</caption>'
        '<thead><tr><th scope="col">Beta against</th><th scope="col" class="num">Beta</th>'
        '<th scope="col" class="num">95% interval</th><th scope="col" class="num">R squared</th>'
        '<th scope="col" class="num">Days</th></tr></thead>'
        f"<tbody>{rows}</tbody></table></div>"
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


def _how_europe(e: ProxyBeta) -> list[str]:
    first = date_long(e.start) if e.start else "n/a"
    last = date_long(e.end) if e.end else "n/a"
    extra = [
        f"The Europe row is the same regression with IEUR in place of ACWI, on its own "
        f"{e.n_days:,} days, {first} to {last}: the days of the analysed sample that IEUR also "
        "has. When those days differ from the ACWI days, the US market beta on them is shown in "
        "its own row."
    ]
    if e.n_not_in_benchmark:
        extra.append(
            f"{e.n_not_in_benchmark:,} days of the analysed sample were left out of the Europe "
            "row because IEUR has no usable return for them (it started later, or a day is "
            "missing)."
        )
    extra.extend(e.audit_warnings)
    return extra


def _foot(report: FactorReport, s: WorldBetaSection, world: BetaFit | None) -> str:
    texts = {**WORLD_BETA_SECTION.label_text, **report.label_text}
    sentences = [texts.get("L-DESC", DEFAULT_DESC)]
    sentences += [texts[k] for k in s.labels if k != "L-DESC" and k in texts]
    if s.europe is not None:
        sentences.append(EUROPE_PROXY)
    if s.acwi_last_date is not None:
        sentences.append(f"ACWI data ends {date_long(s.acwi_last_date)}.")
    if s.acwi_note:
        sentences.append(s.acwi_note)
    if s.europe is not None and s.europe.last_date is not None:
        sentences.append(f"IEUR data ends {date_long(s.europe.last_date)}.")
    if s.europe is not None and s.europe.note:
        sentences.append(s.europe.note)
    more = _how(s, world) if world is not None else []
    europe = _europe_ok(s)
    if europe is not None:
        more = more + _how_europe(europe)
    return footnote(" ".join(sentences), more)


def _europe_reading(s: WorldBetaSection) -> str:
    """The sentence about the Europe block: its comparison, or why there is no row."""
    e = s.europe
    if e is None:
        return ""
    if e.status == "ok" and e.comparison_text is not None:
        return f'<p class="reading">Europe: {esc(e.comparison_text)}</p>'
    return f'<p class="reading">Europe row not shown: {esc(e.reason or "")}</p>'


def render_world_beta_panel(report: FactorReport) -> str | None:
    """The panel's HTML, or ``None`` when the section was not computed."""
    s = report.world_beta
    if s is None:
        return None
    head = panel_head(PANEL_ID, TITLE, QUESTION)
    if s.status != "ok" or s.world is None or s.us_market is None:
        if s.status == "insufficient_data":
            step = NEXT_STEP_SHORT
        elif s.acwi_first_date is None:  # the fund's prices were not fetched: trying again can help
            step = NEXT_STEP_FAILED
        else:  # the prices came but cannot be used; running the report again changes nothing
            step = NEXT_STEP_UNFIXABLE
        body = empty_state(s.reason or "", step)
        if _europe_ok(s) is not None:  # the world fund failed alone: Europe still shows
            body += _europe_reading(s) + _table(_rows(s), CAPTION_EUROPE)
        elif s.europe is not None:
            body += _europe_reading(s)
        return panel_section(PANEL_ID, head, body + _foot(report, s, None))
    body = (
        f'<p class="reading">{esc(s.comparison_text)}</p>'
        + _europe_reading(s)
        + _table(_rows(s), CAPTION_EUROPE if _europe_ok(s) else CAPTION)
        + _foot(report, s, s.world)
    )
    return panel_section(PANEL_ID, head, body)


register_panel("world_beta", 505, render_world_beta_panel, css=CSS)
