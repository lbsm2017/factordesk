"""Static HTML panel of the ``shrunk_betas`` section (contract SC2.4).

Spec: ``docs/specs/shrunk-betas.md`` (SB5 power wording, SB6 display rules). Registered at position
520 as ``shrunk``. The field holds one section per scope, ``full_sample`` then ``latest_window``.

Per scope that is ``ok``: a table (OLS beta, standard error, shrunk beta, 95% credible interval,
pull) and, beneath it, the power statement of each factor. A hollow diamond marks a shrunk beta
only when its pull is at least ``PULL_DISPLAY_THRESHOLD``; when no pull reaches it the panel says
so in one line (SB6 rule 2). The words "Moved away from typical" and the label L-CORR-MOVE show only
on a row whose diamond is drawn. A scope that is not ``ok`` shows the model's ``reason`` and one
next step. The chart is a table (design principle 2); no mark relies on colour.

The words of this panel are the words of the React panel (``ShrunkBetasPanel.tsx``): both are
pinned by a test on each side, so a change here needs the same change there.
"""

from __future__ import annotations

from collections.abc import Sequence

from factordesk.analytics.shrinkage import any_visible_pull, display_pull
from factordesk.report.panel_registry import register_panel
from factordesk.report.render_html import (
    empty_state,
    esc,
    fmt_num,
    fmt_pct,
    fmt_signed,
    panel_head,
    panel_section,
)
from factordesk.report.schema import FactorReport
from factordesk.report.sections.shrunk import SHRUNK_SECTION, ShrunkBeta, ShrunkBetas

PANEL_ID = "shrunk"
TITLE = "Pulled toward typical"
QUESTION = (
    "How far would a stated prior move each beta, and how much data would detect a small one?"
)
NO_VISIBLE_PULL = "Shrinkage moves no beta by a visible amount: this sample is long enough."
NEXT_STEP = "Widen the date range and run the report again."
NEXT_STEP_FAILED = "Run the report again; if it repeats, check the factor data in Data and audit."
POWER_HEADING = "What the test behind the reliable tags could detect"
LEGEND_TEXT = "Pulled 5% or more toward typical"
MOVED_WORD = "Moved away from typical"
CAPTION = (
    "OLS and shrunk betas with standard errors, 95% credible intervals and pull; a marker is "
    "drawn only where the pull is at least 5%"
)
CROSS_SECTION_WORDS = {"industry49": "industry", "size_char75": "size"}
DEFAULT_DESC = "Descriptive, in-sample, not predictive."
PULL_NOTE = (
    "Pull is the share of the way from the OLS beta to its typical value: 0% means no move, "
    "100% means all the way."
)
SCOPE_ID = {"full_sample": "shrunk-full", "latest_window": "shrunk-latest"}

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
    ".shr-power-h{margin:var(--s-4) 0 var(--s-1);font-size:var(--fs-1);font-weight:560;"
    "color:var(--ink-2)}"
    ".shr-power{max-width:76ch;font-size:var(--fs-1);color:var(--ink-2);line-height:1.45}"
    ".shr-power li{padding:2px 0}"
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
    if s.scope == "latest_window":
        return f"Latest {s.window}-day window" if s.window is not None else "Latest window"
    return f"Full sample ({s.sample.n:,} days)"


def _next_step(s: ShrunkBetas) -> str:
    return NEXT_STEP if s.status == "insufficient_data" else NEXT_STEP_FAILED


def _is_visible(pull: float | None) -> bool:
    return pull is not None and any_visible_pull([pull])


def _moved_shown(b: ShrunkBeta) -> bool:
    """The word and the label L-CORR-MOVE belong to rows whose pull marker is drawn."""
    return _is_visible(b.pull) and b.moved_away is True


def _pull_text(pull: float | None) -> str:
    return "n/a" if pull is None else fmt_pct(display_pull(pull), 1, signed=False)


def _beta_rows(s: ShrunkBetas, moved_title: str) -> str:
    rows: list[str] = []
    for b in s.betas:
        visible = _is_visible(b.pull)
        moved = ""
        if _moved_shown(b):
            moved = (
                f'<span class="moved" title="{esc(moved_title)}">{_AWAY_GLYPH}{MOVED_WORD}</span>'
            )
        rows.append(
            f'<tr role="row" id="{SCOPE_ID[s.scope]}-{esc(b.factor)}">'
            f'<th role="rowheader" scope="row">{esc(b.factor)}</th>'
            f'<td role="cell" class="num strong" data-l="OLS">'
            f"{esc(fmt_signed(b.beta_ols))}</td>"
            f'<td role="cell" class="num" data-l="se">{esc(fmt_num(b.se_hac))}</td>'
            f'<td role="cell" class="num strong sh" data-l="Shrunk">'
            f"{_DIAMOND if visible else ''}{esc(fmt_signed(b.beta_shrunk))}{moved}</td>"
            f'<td role="cell" class="num" data-l="95% credible interval">'
            f"[{esc(fmt_signed(b.cred95_low))}, {esc(fmt_signed(b.cred95_high))}]</td>"
            f'<td role="cell" class="num{"" if visible else " quiet"}" data-l="Pull">'
            f"{esc(_pull_text(b.pull))}</td></tr>"
        )
    return "".join(rows)


def _beta_table(s: ShrunkBetas, moved_title: str) -> str:
    scope = _scope_title(s)
    return (
        f'<div class="scroll-x" tabindex="0" role="region" aria-label="{esc(scope)}, shrunk '
        'betas, scrolls sideways"><table class="reg shr" role="table">'
        f'<caption class="vh">{CAPTION}</caption>'
        '<thead role="rowgroup"><tr role="row"><th role="columnheader" scope="col">Factor</th>'
        '<th role="columnheader" scope="col" class="num">OLS beta</th>'
        '<th role="columnheader" scope="col" class="num"><abbr title="Newey-West standard error '
        'of the OLS beta">se</abbr></th><th role="columnheader" scope="col" class="num">Shrunk '
        'beta</th><th role="columnheader" scope="col" class="num">95% credible interval</th>'
        '<th role="columnheader" scope="col" class="num">Pull</th></tr></thead>'
        f'<tbody role="rowgroup">{_beta_rows(s, moved_title)}</tbody></table></div>'
    )


def _power_list(s: ShrunkBetas) -> str:
    items = "".join(f"<li>{esc(p.text)}</li>" for p in s.power if p.text)
    if not items:
        return ""
    title = esc(_scope_title(s))
    return (
        f'<h4 class="shr-power-h">{POWER_HEADING}</h4>'
        f'<ul class="shr-power" aria-label="Power statements, {title}">{items}</ul>'
    )


def _scope_html(s: ShrunkBetas, *, first: bool, moved_title: str) -> str:
    head = (
        f'<div class="shr-scope{" first" if first else ""}" id="{SCOPE_ID[s.scope]}">'
        f"<h3>{esc(_scope_title(s))}</h3>"
    )
    if s.status != "ok":
        what = s.reason or "Insufficient data: no shrunk betas available."
        return head + empty_state(what, _next_step(s)) + "</div>"
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
        + _power_list(s)
        + "</div>"
    )


def _prior_sentence(ok: Sequence[ShrunkBetas]) -> str:
    """Prior centre and spread per factor, and where the spread comes from (one sentence pair)."""
    source = next((x for x in ok if x.prior is not None), None)
    if source is None or source.prior is None:
        return ""
    prior = source.prior
    per_factor = "; ".join(
        f"{b.factor} {fmt_num(c)} and {fmt_num(t)}"
        for b, c, t in zip(source.betas, prior.centre, prior.tau, strict=False)
    )
    sizes = " and ".join(
        f"{n} {CROSS_SECTION_WORDS.get(k, k)}" for k, n in prior.n_portfolios.items()
    )
    return (
        f"Prior centre and spread per factor: {per_factor}. "
        f"The spread comes from {sizes} portfolios, {prior.window_start} to {prior.window_end}."
    )


def _footnote_html(texts: dict[str, str], ok: Sequence[ShrunkBetas]) -> str:
    desc = texts.get("L-DESC", DEFAULT_DESC)
    moved = any(_moved_shown(b) for s in ok for b in s.betas)
    keys = list(dict.fromkeys(k for s in ok for k in s.labels))
    parts = [_prior_sentence(ok)] + [
        texts[k] for k in keys if k != "L-DESC" and k in texts and (moved or k != "L-CORR-MOVE")
    ]
    how = " ".join(p for p in parts if p)
    details = (
        f'<details class="how"><summary>How this is computed</summary><p>{esc(how)}</p></details>'
        if how
        else ""
    )
    return f'<div class="foot"><p>{esc(desc)}</p>{details}</div>'


def render_shrunk_panel(report: FactorReport) -> str | None:
    """The panel's HTML, or ``None`` when the section was not computed."""
    sections = report.shrunk_betas
    if sections is None:
        return None
    texts = {**SHRUNK_SECTION.label_text, **report.label_text}
    ok = [s for s in sections if s.status == "ok"]
    legend = ""
    if any(_is_visible(b.pull) for s in ok for b in s.betas):
        legend = f'<ul class="legend" aria-label="Legend"><li>{_DIAMOND}{LEGEND_TEXT}</li></ul>'
    moved_title = texts.get("L-CORR-MOVE", "")
    body = "".join(
        _scope_html(s, first=i == 0, moved_title=moved_title) for i, s in enumerate(sections)
    )
    foot = _footnote_html(texts, ok) if ok else ""
    return panel_section(PANEL_ID, panel_head(PANEL_ID, TITLE, QUESTION, legend), body + foot)


register_panel("shrunk", 520, render_shrunk_panel, css=CSS)
