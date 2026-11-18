"""Static HTML panel of the ``shrunk_betas`` section (contract SC2.4).

Spec: ``docs/specs/shrunk-betas.md`` (SB5 power wording, SB6 display rules). Registered at position
520 as ``shrunk``. The field holds one section per scope, ``full_sample`` then ``latest_window``.

Per scope that is ``ok``: a table (OLS beta, standard error, shrunk beta, 95% credible interval,
pull) and, beneath it, the power statement of each factor. A hollow diamond marks a shrunk beta
only when its pull is at least ``PULL_DISPLAY_THRESHOLD``; when no pull reaches it the panel says
so in one line (SB6 rule 2). A scope that is not ``ok`` shows the model's ``reason`` and one next
step. The chart is a table (design principle 2); no mark relies on colour.
"""

from __future__ import annotations

from collections.abc import Sequence

from factordesk.analytics.shrinkage import PULL_DISPLAY_THRESHOLD, any_visible_pull, display_pull
from factordesk.report.panel_registry import register_panel
from factordesk.report.render_html import (
    date_long,
    empty_state,
    esc,
    fmt_num,
    fmt_pct,
    fmt_signed,
    panel_head,
    panel_section,
)
from factordesk.report.schema import FactorReport
from factordesk.report.sections.shrunk import SHRUNK_SECTION, ShrinkagePrior, ShrunkBetas

PANEL_ID = "shrunk"
TITLE = "Pulled toward typical"
QUESTION = (
    "How far would a stated prior move each beta, and how much data would detect a small one?"
)
NO_VISIBLE_PULL = "Shrinkage moves no beta by a visible amount: this sample is long enough."
NEXT_STEP = "Widen the date range and run the report again."
PULL_NOTE = (
    "Pull is the share of the way from the OLS beta to its typical value: 0% means no move, "
    "100% means all the way."
)
SCOPE_ID = {"full_sample": "shrunk-full", "latest_window": "shrunk-latest"}
FOLDED_LABELS = ("L-SHRINK-PRIOR", "L-CRED", "L-MDE", "L-CORR-MOVE")

CSS = (
    ".shr-scope{margin-top:var(--s-5)}"
    ".shr-scope.first{margin-top:var(--s-4)}"
    ".panel .shr-scope h3{margin:0}"
    ".shr-scope .reading{margin:var(--s-3) 0 var(--s-2)}"
    "table.reg.shr{table-layout:fixed;min-width:760px}"
    ".shr thead th:nth-child(2){width:96px}"
    ".shr thead th:nth-child(3){width:84px}"
    ".shr thead th:nth-child(4){width:200px}"
    ".shr thead th:nth-child(5){width:190px}"
    ".shr thead th:nth-child(6){width:84px}"
    ".shr th abbr{text-decoration:none;cursor:help}"
    ".shr td.num.quiet{color:var(--ink-3)}"
    ".shr .moved{display:flex;align-items:center;justify-content:flex-end;gap:4px;"
    "font-size:var(--fs-1);font-weight:400;color:var(--ink-2)}"
    ".shr .moved .glyph{transform:none}"
    ".dm{display:inline-block;width:11px;height:11px;margin-right:6px;vertical-align:-1px;"
    "fill:none;stroke:var(--ink-3);stroke-width:1.5;stroke-linejoin:round}"
    ".legend .dm{margin-right:0}"
    ".shr-note{margin-top:var(--s-2);font-size:var(--fs-1);color:var(--ink-3);max-width:76ch}"
    ".shr-power{width:100%;table-layout:fixed;border-collapse:collapse;margin-top:var(--s-4)}"
    ".shr-power thead th{font-size:var(--fs-1);font-weight:500;color:var(--ink-2);text-align:left;"
    "padding:0 0 6px;border-bottom:1px solid var(--border);vertical-align:bottom}"
    ".shr-power thead th.num{text-align:right;width:172px}"
    ".shr-power thead th:first-child{width:var(--label-w)}"
    ".shr-power thead th:last-child{padding-left:var(--s-3)}"
    ".shr-power tbody th{text-align:left;font-weight:560;padding:7px var(--s-3) 7px 0;"
    "vertical-align:top}"
    ".shr-power tbody td{padding:7px 0 7px var(--s-3);vertical-align:top;color:var(--ink-2)}"
    ".shr-power tbody td.num{text-align:right;color:var(--ink);font-weight:560;white-space:nowrap}"
    ".shr-power tbody tr+tr>*{border-top:1px solid var(--grid)}"
    ".shr-prior{margin-top:var(--s-2);border-collapse:collapse;font-size:var(--fs-1);"
    "color:var(--ink-2)}"
    ".shr-prior th,.shr-prior td{padding:2px var(--s-4) 2px 0;text-align:left;font-weight:400}"
    ".shr-prior td.num,.shr-prior th.num{text-align:right}"
    "@media screen and (max-width:719px){"
    "table.reg.shr{min-width:0}"
    ".shr,.shr tbody,.shr thead{display:block}"
    ".shr thead{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0)}"
    ".shr tbody tr{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));"
    "column-gap:var(--s-3);row-gap:var(--s-1);padding:10px 0;border-bottom:1px solid var(--grid)}"
    ".shr tbody th{grid-column:1 / -1;padding:0;border:0;font-weight:560}"
    ".shr tbody td{display:block;padding:0;border:0;text-align:left}"
    ".shr tbody td::before{content:attr(data-l);display:block;font-size:var(--fs-1);"
    "font-weight:400;color:var(--ink-3)}"
    ".shr tbody td.sh .moved{justify-content:flex-start;white-space:normal}"
    ".shr-power,.shr-power tbody{display:block}"
    ".shr-power thead{display:none}"
    ".shr-power tbody tr{display:grid;grid-template-columns:minmax(0,1fr) auto;"
    "column-gap:var(--s-3);padding:8px 0}"
    ".shr-power tbody tr+tr{border-top:1px solid var(--grid)}"
    ".shr-power tbody tr>*{border:0!important;padding:0}"
    ".shr-power tbody td:last-child{grid-column:1 / -1;margin-top:2px}"
    ".shr-power tbody td.num::before{content:'Smallest beta detected ';font-weight:400;"
    "color:var(--ink-3)}"
    "}"
)

_DIAMOND = (
    '<svg class="dm" aria-hidden="true" viewBox="0 0 12 12"><path d="M6 1 11 6 6 11 1 6z"/></svg>'
)
_AWAY_GLYPH = (
    '<svg class="glyph" aria-hidden="true" viewBox="0 0 16 16"><path d="M2 8h11"/>'
    '<path class="cut" d="M9 4l4 4-4 4"/></svg>'
)


def _scope_title(s: ShrunkBetas) -> str:
    if s.scope == "latest_window" and s.window is not None:
        return f"Latest {s.window}-day window"
    return "Full sample"


def _scope_sub(s: ShrunkBetas) -> str:
    """Where the regression came from, in words (the section keeps its own sample metadata)."""
    n, start, end = s.sample.n, s.sample.start, s.sample.end
    if s.scope == "latest_window":
        tail = f", ending {date_long(end)}" if end is not None else ""
        return f"The latest window of the rolling regression{tail}."
    span = f", {date_long(start)} to {date_long(end)}" if start and end else ""
    return f"The whole sample: {n:,} daily returns{span}."


def _is_visible(pull: float | None) -> bool:
    return pull is not None and any_visible_pull([pull])


def _pull_text(pull: float | None) -> str:
    return "n/a" if pull is None else fmt_pct(display_pull(pull), 1, signed=False)


def _beta_rows(s: ShrunkBetas, moved_title: str) -> str:
    rows: list[str] = []
    for b in s.betas:
        visible = _is_visible(b.pull)
        moved = ""
        if b.moved_away:
            moved = (
                f'<span class="moved" title="{esc(moved_title)}">'
                f"{_AWAY_GLYPH}Moved away from typical</span>"
            )
        rows.append(
            f'<tr role="row" id="{SCOPE_ID[s.scope]}-{esc(b.factor)}">'
            f'<th role="rowheader" scope="row">{esc(b.factor)}</th>'
            f'<td role="cell" class="num strong" data-l="OLS beta">'
            f"{esc(fmt_signed(b.beta_ols))}</td>"
            f'<td role="cell" class="num" data-l="se">{esc(fmt_num(b.se_hac))}</td>'
            f'<td role="cell" class="num strong sh" data-l="Shrunk beta">'
            f"{_DIAMOND if visible else ''}{esc(fmt_signed(b.beta_shrunk))}{moved}</td>"
            f'<td role="cell" class="num" data-l="95% credible interval">'
            f"{esc(fmt_signed(b.cred95_low))} to {esc(fmt_signed(b.cred95_high))}</td>"
            f'<td role="cell" class="num{"" if visible else " quiet"}" data-l="Pull">'
            f"{esc(_pull_text(b.pull))}</td></tr>"
        )
    return "".join(rows)


def _beta_table(s: ShrunkBetas, moved_title: str) -> str:
    scope = _scope_title(s)
    return (
        f'<div class="scroll-x" tabindex="0" role="region" aria-label="{esc(scope)}, shrunk '
        'betas, scrolls sideways"><table class="reg shr" role="table">'
        f'<caption class="vh">{esc(scope)}: OLS and shrunk betas with standard errors, 95% '
        "credible intervals and pull</caption>"
        '<thead role="rowgroup"><tr role="row"><th role="columnheader" scope="col">Factor</th>'
        '<th role="columnheader" scope="col" class="num">OLS beta</th>'
        '<th role="columnheader" scope="col" class="num"><abbr title="Newey-West standard error '
        'of the OLS beta">se</abbr></th><th role="columnheader" scope="col" class="num">Shrunk '
        'beta</th><th role="columnheader" scope="col" class="num">95% credible interval</th>'
        '<th role="columnheader" scope="col" class="num">Pull</th></tr></thead>'
        f'<tbody role="rowgroup">{_beta_rows(s, moved_title)}</tbody></table></div>'
    )


def _power_table(s: ShrunkBetas) -> str:
    rows = "".join(
        f'<tr><th scope="row">{esc(p.factor)}</th>'
        f'<td class="num">{esc(fmt_num(p.mde80))}</td><td>{esc(p.text or "")}</td></tr>'
        for p in s.power
    )
    return (
        f'<table class="shr-power"><caption class="vh">{esc(_scope_title(s))}: smallest beta '
        "each factor could detect, and what that means</caption>"
        '<thead><tr><th scope="col">Factor</th>'
        '<th scope="col" class="num">Smallest beta detected</th>'
        '<th scope="col">What that means</th></tr></thead>'
        f"<tbody>{rows}</tbody></table>"
    )


def _scope_html(s: ShrunkBetas, *, first: bool, moved_title: str) -> str:
    head = (
        f'<div class="shr-scope{" first" if first else ""}" id="{SCOPE_ID[s.scope]}">'
        f'<h3>{esc(_scope_title(s))}</h3><span class="sub">{esc(_scope_sub(s))}</span>'
    )
    if s.status != "ok":
        what = s.reason or "Insufficient data: no shrunk betas available."
        return head + empty_state(what, NEXT_STEP) + "</div>"
    reading = (
        ""
        if any(_is_visible(b.pull) for b in s.betas)
        else f'<p class="reading">{esc(NO_VISIBLE_PULL)}</p>'
    )
    return (
        head
        + reading
        + _beta_table(s, moved_title)
        + f'<p class="shr-note">{esc(PULL_NOTE)}</p>'
        + _power_table(s)
        + "</div>"
    )


def _prior_html(prior: ShrinkagePrior, names: Sequence[str]) -> str:
    rows = "".join(
        f'<tr><th scope="row">{esc(n)}</th><td class="num">{esc(fmt_signed(c))}</td>'
        f'<td class="num">{esc(fmt_num(t))}</td></tr>'
        for n, c, t in zip(names, prior.centre, prior.tau, strict=True)
    )
    counts = prior.n_portfolios
    industry = next((v for k, v in counts.items() if k.startswith("industry")), None)
    size = next((v for k, v in counts.items() if k.startswith("size")), None)
    source = ""
    if industry is not None and size is not None:
        source = (
            f"<p>The spread comes from {industry} industry and {size} size portfolios, "
            f"{esc(date_long(prior.window_start))} to {esc(date_long(prior.window_end))}.</p>"
        )
    return (
        f'{source}<table class="shr-prior"><caption class="vh">Prior centre and spread per '
        'factor</caption><thead><tr><th scope="col">Factor</th><th scope="col" class="num">'
        'Centre</th><th scope="col" class="num">Spread</th></tr></thead>'
        f"<tbody>{rows}</tbody></table>"
    )


def _footnote_html(texts: dict[str, str], ok: Sequence[ShrunkBetas]) -> str:
    desc = texts.get("L-DESC", "Descriptive, in-sample, not predictive.")
    shown = {k for s in ok for k in s.labels} | {"L-SHRINK-PRIOR"}
    folded = "".join(f"<p>{esc(texts[k])}</p>" for k in FOLDED_LABELS if k in shown and k in texts)
    priors: list[tuple[ShrinkagePrior, list[str]]] = []
    for s in ok:
        if s.prior is None:
            continue
        for known, scopes in priors:
            if known.centre == s.prior.centre and known.tau == s.prior.tau:
                scopes.append(_scope_title(s))
                break
        else:
            priors.append((s.prior, [_scope_title(s)]))
    names = [b.factor for b in ok[0].betas]
    for prior, scopes in priors:
        who = f"<p>Prior for: {esc(', '.join(scopes))}.</p>" if len(priors) > 1 else ""
        folded += who + _prior_html(prior, names)
    return (
        f'<div class="foot"><p>{esc(desc)} {esc(texts.get("L-SHRINK", ""))}</p>'
        f'<details class="how"><summary>How this is computed</summary>{folded}</details></div>'
    )


def render_shrunk_panel(report: FactorReport) -> str | None:
    """The panel's HTML, or ``None`` when the section was not computed."""
    sections = report.shrunk_betas
    if sections is None:
        return None
    texts = {**SHRUNK_SECTION.label_text, **report.label_text}
    ok = [s for s in sections if s.status == "ok"]
    legend = ""
    if any(_is_visible(b.pull) for s in ok for b in s.betas):
        legend = (
            '<ul class="legend" aria-label="Legend"><li>'
            f"{_DIAMOND}Pulled {PULL_DISPLAY_THRESHOLD:.0%} or more toward typical</li></ul>"
        )
    moved_title = texts.get("L-CORR-MOVE", "")
    body = "".join(
        _scope_html(s, first=i == 0, moved_title=moved_title) for i, s in enumerate(sections)
    )
    foot = _footnote_html(texts, ok) if ok else ""
    return panel_section(PANEL_ID, panel_head(PANEL_ID, TITLE, QUESTION, legend), body + foot)


register_panel("shrunk", 520, render_shrunk_panel, css=CSS)
